"""Reproduce the Section V-C style comparison: ReSACO vs. SAC (no
meta-init), DDPG, A2C, A3C as the number of mobile devices increases from
200 to 2,000 in steps of 200 (Fig. 6/7 and Table III of the paper).

resaco/env.py models a single agent-controlled MD's task stream, but the
other (devices - 1) MDs' contention is real, not just approximated: every
step, env._inject_background_load admits a Poisson-sampled batch of
background tasks straight into the shared edge/cloud pools, scaled by
device count -- so bumping device_count here (scenario_for_device_count)
just updates number_of_mobile_devices and env.py's own background-load
injection does the rest, without requiring a full multi-agent simulator.

Usage:
    python scripts/compare_algorithms.py [--episode-steps N] [--seed S]
"""

import argparse
import csv
import os
import sys
from dataclasses import replace

import torch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from resaco import config
from resaco.env import MECOffloadEnv
from resaco.sac import SACAgent
from resaco.baselines.ddpg import DDPGAgent
from resaco.baselines.a2c import A2CAgent
from resaco.scenario import sample_scenario


DEVICE_COUNTS = list(range(200, 2001, 200))

ALGORITHMS = {
    "ReSACO": ("theta_star.pt", lambda params: _load(SACAgent(), params)),
    "SAC": ("sac_no_meta.pt", lambda params: _load(SACAgent(), params)),
    "DDPG": ("ddpg.pt", lambda params: _load(DDPGAgent(), params)),
    "A2C": ("a2c.pt", lambda params: _load(A2CAgent(), params)),
    "A3C": ("a3c.pt", lambda params: _load(A2CAgent(), params)),
}


def _load(agent, params):
    agent.load_params(params)
    return agent


def evaluate(agent, scenario, episode_steps, seed):
    env = MECOffloadEnv(scenario, seed=seed)
    state = env.reset()

    service_times, process_times, network_delays = [], [], []
    completed = failed_network = failed_vm = 0

    for _ in range(episode_steps):
        action = agent.select_action(state, greedy=True)
        state, reward, done, info = env.step(action)
        if info["failed"]:
            if info.get("network_fail"):
                failed_network += 1
            if info.get("vm_fail"):
                failed_vm += 1
        else:
            completed += 1
            service_times.append(info["service_time"])
            network_delays.append(info["delay"])
            process_times.append(info["service_time"] - info["delay"])

    total = completed + failed_network + failed_vm
    avg = lambda xs: (sum(xs) / len(xs)) if xs else float("nan")
    return {
        "completion_rate": completed / total if total else float("nan"),
        "network_fail_rate": failed_network / total if total else float("nan"),
        "vm_fail_rate": failed_vm / total if total else float("nan"),
        "avg_service_time": avg(service_times),
        "avg_processing_time": avg(process_times),
        "avg_network_delay": avg(network_delays),
    }


def scenario_for_device_count(base_scenario, device_count):
    """Device count alone now drives real background contention (see
    env._inject_background_load, whose background_devices = count - 1) --
    no need to also artificially scale poisson_interarrival like an
    earlier version of this function did before that existed."""
    return replace(base_scenario, number_of_mobile_devices=device_count)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--episode-steps", type=int, default=500)
    parser.add_argument("--seed", type=int, default=123)
    parser.add_argument("--checkpoints-dir", type=str, default=os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "checkpoints"))
    parser.add_argument("--out-csv", type=str, default=os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "checkpoints", "comparison.csv"))
    args = parser.parse_args()

    agents = {}
    for name, (filename, loader) in ALGORITHMS.items():
        path = os.path.join(args.checkpoints_dir, filename)
        if not os.path.exists(path):
            print(f"WARNING: {path} not found, skipping {name}. "
                  f"Run train_meta.py / train_baselines.py first.")
            continue
        params = torch.load(path, map_location="cpu")
        agents[name] = loader(params)

    if not agents:
        print("No trained checkpoints found. Nothing to compare.")
        return

    base_scenario = sample_scenario(__import__("random").Random(args.seed))

    rows = []
    for device_count in DEVICE_COUNTS:
        scenario = scenario_for_device_count(base_scenario, device_count)
        for name, agent in agents.items():
            metrics = evaluate(agent, scenario, args.episode_steps, seed=args.seed + device_count)
            row = {"algorithm": name, "devices": device_count, **metrics}
            rows.append(row)
            print(f"devices={device_count:5d}  {name:8s}  "
                  f"completion={metrics['completion_rate']*100:6.2f}%  "
                  f"service_time={metrics['avg_service_time']:.3f}s  "
                  f"net_fail={metrics['network_fail_rate']*100:5.2f}%  "
                  f"vm_fail={metrics['vm_fail_rate']*100:5.2f}%")

    os.makedirs(os.path.dirname(args.out_csv), exist_ok=True)
    with open(args.out_csv, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
    print(f"\nSaved comparison table -> {args.out_csv}")

    def pct_improve(base, resaco):
        """Relative percent improvement -- fine for service_time, a positive
        duration essentially never at/near zero."""
        if base in (0, None) or base != base:
            return float("nan")
        return (base - resaco) / base * 100

    def pct_point_diff(base, resaco):
        """Absolute percentage-point difference (base - resaco), for
        network_fail_rate/vm_fail_rate -- both already bounded in [0, 100].
        A relative percent-improvement formula blows up for these: it's NaN
        whenever a baseline's rate is exactly 0 (common here -- network
        failures never happen in this env) and explodes to absurd values
        (e.g. -13150%) whenever the baseline is merely close to 0."""
        if base is None or base != base or resaco is None or resaco != resaco:
            return float("nan")
        return base - resaco

    # Table III style: ReSACO's improvement over each baseline at the
    # highest device count.
    if "ReSACO" in agents:
        last = {r["algorithm"]: r for r in rows if r["devices"] == DEVICE_COUNTS[-1]}
        if "ReSACO" in last:
            print(f"\nReSACO improvement at {DEVICE_COUNTS[-1]} devices (Table III style):")
            print(f"{'Algorithm':10s} {'Service Time':>14s} {'Net Fail (pp)':>14s} {'VM Fail (pp)':>13s}")
            resaco_row = last["ReSACO"]
            for name, row in last.items():
                if name == "ReSACO":
                    continue
                st = pct_improve(row["avg_service_time"], resaco_row["avg_service_time"])
                nf = pct_point_diff(row["network_fail_rate"], resaco_row["network_fail_rate"])
                vf = pct_point_diff(row["vm_fail_rate"], resaco_row["vm_fail_rate"])
                print(f"{name:10s} {st:13.1f}% {nf:13.1f}pp {vf:12.1f}pp")


if __name__ == "__main__":
    main()
