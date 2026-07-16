import numpy as np

from resaco.replay_buffer import ReplayBuffer


def test_push_and_len():
    buf = ReplayBuffer(capacity=100)
    assert len(buf) == 0
    for i in range(10):
        buf.push(state=[i] * 4, action=i % 3, reward=-1.0, next_state=[i + 1] * 4, done=0.0)
    assert len(buf) == 10


def test_capacity_evicts_oldest():
    buf = ReplayBuffer(capacity=5)
    for i in range(8):
        buf.push(state=[i], action=0, reward=0.0, next_state=[i], done=0.0)
    assert len(buf) == 5


def test_sample_shapes():
    buf = ReplayBuffer(capacity=100)
    for i in range(20):
        buf.push(state=[i, i, i], action=i % 4, reward=float(i), next_state=[i + 1] * 3, done=0.0)
    state, action, reward, next_state, done = buf.sample(8)
    assert state.shape == (8, 3)
    assert action.shape == (8,)
    assert reward.shape == (8,)
    assert next_state.shape == (8, 3)
    assert done.shape == (8,)
    assert isinstance(state, np.ndarray)


def test_sample_caps_at_buffer_length():
    buf = ReplayBuffer(capacity=100)
    for i in range(3):
        buf.push(state=[i], action=0, reward=0.0, next_state=[i], done=0.0)
    state, *_ = buf.sample(64)
    assert state.shape[0] == 3
