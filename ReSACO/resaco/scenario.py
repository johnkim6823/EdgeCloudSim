"""Scenario (metadata) sampling, matching Table II of the ReSACO paper."""

from dataclasses import dataclass
import random

from . import config


@dataclass
class Scenario:
    """A single metadata configuration S_k used by the Outer Loop."""

    usage_percentage: float
    poisson_interarrival: float
    delay_sensitivity: float
    active_period: float
    idle_period: float
    data_upload: float
    data_download: float
    task_length: float
    vm_utilization_on_edge: float
    vm_utilization_on_cloud: float
    vm_utilization_on_mobile: float
    number_of_mobile_devices: int

    @property
    def required_core(self) -> int:
        return config.REQUIRED_CORE


def sample_scenario(rng: random.Random = random) -> Scenario:
    """Randomly sample a scenario within the ranges of Table II.

    vm_utilization_on_edge is fixed to be ten times vm_utilization_on_cloud,
    exactly as stated in the paper (Section V-A-1).
    """
    r = config.METADATA_RANGES
    vm_cloud = rng.uniform(*r["vm_utilization_on_cloud"])
    vm_edge = vm_cloud * 10.0

    return Scenario(
        usage_percentage=rng.uniform(*r["usage_percentage"]),
        poisson_interarrival=rng.uniform(*r["poisson_interarrival"]),
        delay_sensitivity=rng.uniform(*r["delay_sensitivity"]),
        active_period=rng.uniform(*r["active_period"]),
        idle_period=rng.uniform(*r["idle_period"]),
        data_upload=rng.uniform(*r["data_upload"]),
        data_download=rng.uniform(*r["data_download"]),
        task_length=rng.uniform(*r["task_length"]),
        vm_utilization_on_edge=vm_edge,
        vm_utilization_on_cloud=vm_cloud,
        vm_utilization_on_mobile=rng.uniform(*r["vm_utilization_on_mobile"]),
        number_of_mobile_devices=int(rng.uniform(*r["number_of_mobile_devices"])),
    )


def sample_scenario_pool(num_scenarios: int, seed: int = None):
    rng = random.Random(seed)
    return [sample_scenario(rng) for _ in range(num_scenarios)]
