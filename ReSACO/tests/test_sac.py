"""Regression tests for the Reptile Inner Loop bug: sac_update_loop's
num_transitions (N, Algorithm 2) used to silently produce zero real
gradient updates whenever N < BATCH_SIZE, because a fresh agent's replay
buffer starts empty and update() no-ops until it reaches batch_size. Since
the Reptile Inner Loop creates a brand-new SACAgent every outer iteration
and (at the paper's Table II defaults) calls it with N=50 < BATCH_SIZE=64,
theta_star.pt was silently never trained at all. See ReSACO/README.md's
"Convergence" section for the full writeup.
"""

import copy

import torch

from resaco import config
from resaco.env import MECOffloadEnv
from resaco.sac import SACAgent
from resaco.scenario import Scenario


def _make_scenario():
    return Scenario(
        usage_percentage=20.0, poisson_interarrival=8.0, delay_sensitivity=0.5,
        active_period=30.0, idle_period=30.0, data_upload=200.0, data_download=200.0,
        task_length=3000.0, vm_utilization_on_edge=10.0, vm_utilization_on_cloud=1.0,
        vm_utilization_on_mobile=10.0, number_of_mobile_devices=500,
    )


def test_sac_update_loop_performs_exactly_n_updates_even_when_n_below_batch_size():
    assert config.NUM_INNER_SAC_UPDATES < config.BATCH_SIZE, (
        "this test's whole point is exercising N < batch_size, matching the paper's "
        "Table II defaults (N=50, batch_size=64) -- if this ever stops holding, the "
        "warm-up fix is no longer being exercised by this test"
    )
    env = MECOffloadEnv(_make_scenario(), seed=1)
    agent = SACAgent()

    stats = agent.sac_update_loop(env, num_transitions=config.NUM_INNER_SAC_UPDATES)

    assert len(stats) == config.NUM_INNER_SAC_UPDATES
    assert all(s is not None for s in stats)
    # warm-up (up to batch_size) + the N counted transitions, none dropped
    assert len(agent.replay_buffer) == config.BATCH_SIZE + config.NUM_INNER_SAC_UPDATES


def test_sac_update_loop_actually_changes_network_weights():
    env = MECOffloadEnv(_make_scenario(), seed=2)
    agent = SACAgent()
    params_before = copy.deepcopy(agent.get_params())

    agent.sac_update_loop(env, num_transitions=config.NUM_INNER_SAC_UPDATES)

    params_after = agent.get_params()
    actor_changed = any(
        not torch.equal(params_before["actor"][k], params_after["actor"][k])
        for k in params_before["actor"]
    )
    assert actor_changed, "actor weights are byte-identical after training -- no real update happened"


def test_update_returns_none_below_batch_size():
    agent = SACAgent()
    agent.replay_buffer.push([0.0] * config.STATE_DIM, 0, -1.0, [0.0] * config.STATE_DIM, 0.0)
    assert agent.update() is None


def test_select_action_within_action_space():
    agent = SACAgent()
    state = [1.0] * config.STATE_DIM
    for _ in range(20):
        action = agent.select_action(state, greedy=False)
        assert 0 <= action < config.ACTION_DIM
    greedy_action = agent.select_action(state, greedy=True)
    assert 0 <= greedy_action < config.ACTION_DIM
