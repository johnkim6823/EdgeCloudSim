"""TCP bridge that lets the Java EdgeCloudSim orchestrator use trained
ReSACO/baseline policies for live offloading decisions.

Serves all five algorithms compared in Section V-C of the paper at once,
each loaded from its own checkpoint and selected per-request by name --
this lets EdgeCloudSim run ReSACO, SAC (no meta-init), DDPG, A2C and A3C
as five separate `orchestrator_policies` in the *same* real CloudSim
simulation (scripts/ReSACO), instead of only the toy env used by
scripts/compare_algorithms.py.

Protocol (newline-delimited ASCII, one request per line):

  ACT <algo> <request_id> <L> <U> <D> <mu_d> <mu_e1> ... <mu_eN> <mu_c> <bwlan> <bman> <bwan>
      -> "<action_int>"
         action in {0..N+1}: 0=device, 1..N=edge server index, N+1=cloud

  OUTCOME <algo> <request_id> <reward> <done:0|1> <next_state...>
      -> "OK" | "IGNORED"
         IGNORED means request_id was never seen by ACT for this algo (e.g.
         the bridge was unreachable/restarted at decision time). ReSACO/SAC/
         DDPG (off-policy) turn this into an online SAC-Update/DDPG-update
         step (Algorithm 4); A2C/A3C (on-policy) just discard it -- their
         served policy is exactly what scripts/train_baselines.py produced.

  PING
      -> "PONG"

<algo> is one of RESACO, SAC_BASELINE, DDPG_BASELINE, A2C_BASELINE,
A3C_BASELINE. If that algorithm's checkpoint wasn't found at startup, ACT
returns "ERROR unknown algo ..." and the Java client falls back to its
static heuristic for that decision -- same as if the whole bridge were
unreachable.

A missing/unreachable server should never crash the simulator: the Java
client (ReSACOBridgeClient) falls back to a static policy on any I/O error.
"""

import argparse
import os
import socketserver
import sys
import threading

import torch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from resaco import config
from resaco.deploy import DeploymentAgent, FrozenPolicyAgent
from resaco.sac import SACAgent
from resaco.baselines.ddpg import DDPGAgent
from resaco.baselines.a2c import A2CAgent

# name -> (checkpoint filename, agent factory, wrapper factory)
ALGO_REGISTRY = {
    "RESACO": ("theta_star.pt", SACAgent, DeploymentAgent),
    "SAC_BASELINE": ("sac_no_meta.pt", SACAgent, DeploymentAgent),
    "DDPG_BASELINE": ("ddpg.pt", DDPGAgent, DeploymentAgent),
    "A2C_BASELINE": ("a2c.pt", A2CAgent, FrozenPolicyAgent),
    "A3C_BASELINE": ("a3c.pt", A2CAgent, FrozenPolicyAgent),
}

_agents = {}  # algo name -> DeploymentAgent | FrozenPolicyAgent
_lock = threading.Lock()


def _parse_floats(tokens):
    return [float(t) for t in tokens]


class Handler(socketserver.StreamRequestHandler):
    def handle(self):
        while True:
            try:
                raw = self.rfile.readline()
            except OSError:
                break
            if not raw:
                break
            line = raw.decode("utf-8").strip()
            if not line:
                continue
            try:
                response = self._dispatch(line)
            except Exception as exc:  # never let a bad request kill the server
                response = f"ERROR {exc}"
            try:
                self.wfile.write((response + "\n").encode("utf-8"))
            except OSError:
                break

    def _dispatch(self, line: str) -> str:
        parts = line.split()
        cmd = parts[0].upper()

        if cmd == "PING":
            return "PONG"

        if cmd == "ACT":
            algo, request_id = parts[1], parts[2]
            agent = _agents.get(algo)
            if agent is None:
                return f"ERROR unknown algo {algo}"
            state = _parse_floats(parts[3:])
            if len(state) != config.STATE_DIM:
                return f"ERROR expected {config.STATE_DIM} state values, got {len(state)}"
            with _lock:
                action = agent.select_action(state, request_id=request_id)
            return str(action)

        if cmd == "OUTCOME":
            algo, request_id = parts[1], parts[2]
            agent = _agents.get(algo)
            if agent is None:
                return f"ERROR unknown algo {algo}"
            reward = float(parts[3])
            done = bool(int(parts[4]))
            next_state = _parse_floats(parts[5:])
            with _lock:
                result = agent.report_outcome(request_id, reward, next_state, done)
            # result is None only when request_id was never seen by select_action
            # (e.g. the bridge was unreachable/restarted at decision time).
            return "OK" if result is not None else "IGNORED"

        if cmd == "SAVE":
            algo = parts[1] if len(parts) > 1 else None
            path = parts[2] if len(parts) > 2 else None
            agent = _agents.get(algo) if algo else None
            if agent and path:
                with _lock:
                    torch.save(agent.state_dict(), path)
                return "OK"
            return "ERROR missing algo/path"

        return f"ERROR unknown command {cmd}"


class ThreadingTCPServer(socketserver.ThreadingMixIn, socketserver.TCPServer):
    allow_reuse_address = True
    daemon_threads = True


def load_agents(checkpoints_dir: str):
    loaded, missing = [], []
    for algo, (filename, agent_cls, wrapper_cls) in ALGO_REGISTRY.items():
        path = os.path.join(checkpoints_dir, filename)
        agent = agent_cls()
        if os.path.exists(path):
            params = torch.load(path, map_location="cpu")
            _agents[algo] = wrapper_cls(agent, params)
            loaded.append(algo)
        else:
            # serve a randomly-initialized (untrained) policy rather than
            # refusing to serve the algo at all -- keeps the simulation
            # runnable even before all baselines are trained, at the cost
            # of that algo's decisions being meaningless until retrained.
            _agents[algo] = wrapper_cls(agent, None)
            missing.append(algo)
    return loaded, missing


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--checkpoints-dir", type=str, default=os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "checkpoints"))
    parser.add_argument("--host", type=str, default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()

    loaded, missing = load_agents(args.checkpoints_dir)
    if loaded:
        print(f"Loaded trained checkpoints for: {', '.join(loaded)}")
    if missing:
        print(f"WARNING: no checkpoint found for {', '.join(missing)} in {args.checkpoints_dir} "
              f"-- serving randomly-initialized (untrained) policies for them. "
              f"Run train_meta.py / train_baselines.py first.")

    server = ThreadingTCPServer((args.host, args.port), Handler)
    print(f"ReSACO inference/online-learning bridge listening on {args.host}:{args.port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
