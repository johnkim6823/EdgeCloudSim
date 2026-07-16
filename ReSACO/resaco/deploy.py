"""Deployment Phase (Algorithm 4): rapid adaptation of a trained parameter
to a live environment, plus a "frozen" (inference-only) variant for
on-policy baselines that don't have a well-defined single-transition
online-update rule.

These wrap the object the Java-side inference bridge
(bridge/inference_server.py) uses at runtime -- one instance per served
algorithm (ReSACO, SAC baseline, DDPG baseline, A2C baseline, A3C baseline).
"""

import torch

from . import config


class DeploymentAgent:
    """Wraps any off-policy agent -- anything exposing
    select_action(state, greedy), a .replay_buffer with .push(...), and
    .update() (SACAgent and DDPGAgent both qualify) -- for live serving
    with online learning (Algorithm 4): copy trained params in, then keep
    adapting from real reported outcomes via an incremental update per
    transition.

    Without `save_path`, theta_adapt only ever lives in memory -- every bit
    of online adaptation is lost the moment the bridge process restarts,
    which defeats the point of Algorithm 4 being "online" at all. Passing
    `save_path` (+ `autosave_every`) makes report_outcome() persist
    theta_adapt back to disk every N successful updates, and `save()` can
    also be called directly (e.g. from a shutdown handler) to flush
    whatever's been learned so far.
    """

    def __init__(self, agent, params: dict = None, save_path: str = None,
                 autosave_every: int = 50):
        self.agent = agent
        if params is not None:
            self.agent.load_params(params)  # theta* -> theta_adapt (line 1)
        self._pending = {}  # correlate an in-flight decision with its later outcome
        self.save_path = save_path
        self.autosave_every = autosave_every
        self._updates_since_save = 0

    def select_action(self, state, request_id, greedy: bool = False) -> int:
        action = self.agent.select_action(state, greedy=greedy)
        self._pending[request_id] = (state, action)
        return action

    def report_outcome(self, request_id, reward: float, next_state, done: bool = False,
                        min_buffer_before_update: int = config.BATCH_SIZE):
        """Called once a task's real outcome (success/failure, service time)
        is known. Stores the transition and triggers an incremental
        SAC-Update-style step, i.e. the online part of Algorithm 4. Every
        `autosave_every` updates (if `save_path` was given), the adapted
        parameters are flushed to disk so a crash or restart only loses at
        most that many updates' worth of progress instead of all of it.

        Returns None if request_id is unknown (nothing to do -- e.g. this
        decision was never actually made through select_action, or its
        outcome was already reported once). Otherwise returns a dict with
        "recorded": True and an "update" key holding the update result (or
        None if the replay buffer isn't full enough yet to update) --
        callers must check "recorded", not truthiness of the whole result,
        since a recorded-but-not-yet-updated outcome is still real work done.
        """
        if request_id not in self._pending:
            return None
        state, action = self._pending.pop(request_id)
        self.agent.replay_buffer.push(state, action, reward, next_state, float(done))
        update_result = None
        if len(self.agent.replay_buffer) >= min_buffer_before_update:
            update_result = self.agent.update()
            self._updates_since_save += 1
            if self.save_path and self.autosave_every and self._updates_since_save >= self.autosave_every:
                self.save()
        return {"recorded": True, "update": update_result}

    def save(self) -> bool:
        """Flushes theta_adapt to `self.save_path`. Returns False (no-op)
        if no save_path was configured."""
        if not self.save_path:
            return False
        torch.save(self.agent.get_params(), self.save_path)
        self._updates_since_save = 0
        return True

    def state_dict(self):
        return self.agent.get_params()


class FrozenPolicyAgent:
    """Wraps an on-policy agent (A2CAgent, including the A3C-trained
    global network, which is saved in A2CAgent-compatible form) for
    inference-only serving. On-policy methods don't have a natural
    single-transition online-update rule the way off-policy methods do
    (their gradient estimator needs an on-policy rollout, not an
    arbitrarily-delayed, possibly-out-of-order outcome callback from the
    simulator), so report_outcome here is a no-op: the served policy stays
    exactly as trained by scripts/train_baselines.py.
    """

    def __init__(self, agent, params: dict = None):
        self.agent = agent
        if params is not None:
            self.agent.load_params(params)
        self._seen = set()  # request ids we actually decided, for accurate IGNORED reporting

    def select_action(self, state, request_id, greedy: bool = True) -> int:
        self._seen.add(request_id)
        return self.agent.select_action(state, greedy=greedy)

    def report_outcome(self, request_id, reward: float, next_state, done: bool = False):
        if request_id not in self._seen:
            return None
        self._seen.discard(request_id)
        return {"recorded": False, "update": None}

    def save(self) -> bool:
        """Never anything to persist -- the served policy never changes
        after training. Present only so callers can treat every agent
        uniformly (e.g. a shutdown handler calling .save() on all of them)."""
        return False

    def state_dict(self):
        return self.agent.get_params()
