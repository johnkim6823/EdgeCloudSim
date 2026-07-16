"""Tests for the online-learning persistence added to DeploymentAgent
(autosave-every-N-updates, manual save(), resume-friendly no-op when no
save_path is configured) and FrozenPolicyAgent's always-a-no-op save()."""

import os

from resaco import config
from resaco.baselines.a2c import A2CAgent
from resaco.deploy import DeploymentAgent, FrozenPolicyAgent
from resaco.sac import SACAgent


def _drive_transitions(wrapper, n):
    state = [0.5] * config.STATE_DIM
    next_state = [0.6] * config.STATE_DIM
    for i in range(n):
        request_id = f"r{i}"
        wrapper.select_action(state, request_id=request_id)
        wrapper.report_outcome(request_id, -1.0, next_state, False)


def test_deployment_agent_autosaves_after_threshold(tmp_path):
    save_path = str(tmp_path / "adapted.pt")
    agent = DeploymentAgent(SACAgent(), save_path=save_path, autosave_every=3)

    # update() (and so autosave counting) only starts firing once the
    # replay buffer reaches BATCH_SIZE -- push well past that plus the
    # autosave threshold.
    _drive_transitions(agent, config.BATCH_SIZE + 5)

    assert os.path.exists(save_path)


def test_deployment_agent_without_save_path_is_a_no_op():
    agent = DeploymentAgent(SACAgent())
    assert agent.save() is False


def test_deployment_agent_manual_save(tmp_path):
    save_path = str(tmp_path / "manual.pt")
    agent = DeploymentAgent(SACAgent(), save_path=save_path, autosave_every=10_000)
    assert agent.save() is True
    assert os.path.exists(save_path)


def test_deployment_agent_report_outcome_unknown_request_returns_none():
    agent = DeploymentAgent(SACAgent())
    assert agent.report_outcome("never-seen", -1.0, [0.0] * config.STATE_DIM) is None


def test_deployment_agent_report_outcome_duplicate_is_ignored():
    agent = DeploymentAgent(SACAgent())
    state = [0.5] * config.STATE_DIM
    agent.select_action(state, request_id="r1")
    first = agent.report_outcome("r1", -1.0, state, False)
    second = agent.report_outcome("r1", -1.0, state, False)
    assert first is not None
    assert second is None


def test_frozen_policy_agent_never_saves():
    agent = FrozenPolicyAgent(A2CAgent())
    assert agent.save() is False


def test_frozen_policy_agent_report_outcome_is_a_no_op():
    agent = FrozenPolicyAgent(A2CAgent())
    state = [0.5] * config.STATE_DIM
    action = agent.select_action(state, request_id="r1")
    assert 0 <= action < config.ACTION_DIM

    result = agent.report_outcome("r1", -1.0, state, False)
    assert result == {"recorded": False, "update": None}
    # the request was consumed by the first report -- reporting again is unknown
    assert agent.report_outcome("r1", -1.0, state, False) is None
