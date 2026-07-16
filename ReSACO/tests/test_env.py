from resaco import config
from resaco.env import MECOffloadEnv, _SATURATION_CEILING
from resaco.scenario import Scenario


def _make_scenario(number_of_mobile_devices=1, poisson_interarrival=10.0,
                    vm_utilization_on_mobile=10.0, vm_utilization_on_edge=10.0,
                    vm_utilization_on_cloud=1.0, task_length=3000.0):
    return Scenario(
        usage_percentage=20.0,
        poisson_interarrival=poisson_interarrival,
        delay_sensitivity=0.5,
        active_period=30.0,
        idle_period=30.0,
        data_upload=200.0,
        data_download=200.0,
        task_length=task_length,
        vm_utilization_on_edge=vm_utilization_on_edge,
        vm_utilization_on_cloud=vm_utilization_on_cloud,
        vm_utilization_on_mobile=vm_utilization_on_mobile,
        number_of_mobile_devices=number_of_mobile_devices,
    )


def test_reset_returns_correct_state_dim():
    env = MECOffloadEnv(_make_scenario(), seed=1)
    state = env.reset()
    assert state.shape == (config.STATE_DIM,)


def test_device_tier_has_zero_network_delay():
    # A single-device scenario (no background contention) with low mobile
    # utilization per task should never vm_fail on the device tier either,
    # isolating the delay component.
    env = MECOffloadEnv(_make_scenario(number_of_mobile_devices=1, vm_utilization_on_mobile=5.0), seed=2)
    env.reset()
    _, reward, _, info = env.step(0)  # action 0 = device
    assert not info["failed"]
    assert info["delay"] == 0.0


def test_device_tier_reward_is_pure_processing_time():
    env = MECOffloadEnv(_make_scenario(number_of_mobile_devices=1, vm_utilization_on_mobile=5.0,
                                        task_length=4000.0), seed=3)
    env.reset()
    # _sample_task() jitters task_length by +/-30%, so read back the actual
    # sampled length step() will use rather than assuming it equals the
    # scenario's nominal task_length exactly.
    actual_task_length = env.current_task.length
    _, reward, _, info = env.step(0)
    expected_process_time = actual_task_length / config.MOBILE_VM_MIPS
    assert abs(info["service_time"] - expected_process_time) < 1e-6
    assert reward == -info["service_time"]


def test_background_contention_scales_with_device_count():
    low = MECOffloadEnv(_make_scenario(number_of_mobile_devices=2, poisson_interarrival=5.0), seed=4)
    high = MECOffloadEnv(_make_scenario(number_of_mobile_devices=2000, poisson_interarrival=5.0), seed=4)
    low.reset()
    high.reset()
    for _ in range(20):
        low.step(0)
        high.step(0)
    assert sum(high.mu_edge) > sum(low.mu_edge)
    assert high.mu_cloud > low.mu_cloud


def test_background_contention_never_exceeds_saturation_ceiling():
    env = MECOffloadEnv(_make_scenario(number_of_mobile_devices=2000, poisson_interarrival=1.0), seed=5)
    env.reset()
    for _ in range(50):
        env.step(0)
    assert all(mu <= _SATURATION_CEILING for mu in env.mu_edge)
    assert env.mu_cloud <= _SATURATION_CEILING


def test_zero_background_devices_is_a_no_op():
    env = MECOffloadEnv(_make_scenario(number_of_mobile_devices=1), seed=6)
    assert env._background_devices == 0
    env.reset()
    for _ in range(20):
        env.step(0)  # device tier never touches mu_edge/mu_cloud
    assert sum(env.mu_edge) == 0.0
    assert env.mu_cloud == 0.0
