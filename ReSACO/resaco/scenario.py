"""Scenario (metadata) sampling.

A Scenario now mirrors how EdgeCloudSim's IdleActiveLoadGenerator actually
assigns work: every mobile device is given exactly ONE app type for the
whole simulation (weighted by that app's usage_percentage), and that
device's tasks are then drawn from exponential distributions parameterized
by that single app's own poisson_interarrival/data_upload/data_download/
task_length -- never a different app type per task, and never the single
homogeneous "one profile for everything" distribution this module used to
sample from Table II's abstract ranges. See APP_PROFILES below.
"""

from dataclasses import dataclass
import random

from . import config


@dataclass
class AppProfile:
    """One application type's task-generation profile -- mirrors one
    <application> entry in scripts/{ReSACO,three_tier}/config/applications.xml
    exactly (both files are identical). Kept in sync by hand here rather
    than parsed from the XML at runtime: simpler, and a long training run
    shouldn't silently start reading a different config file mid-run if
    someone edits applications.xml later. If you change one, change both.
    """

    name: str
    usage_percentage: float
    poisson_interarrival: float
    delay_sensitivity: float
    active_period: float
    idle_period: float
    data_upload: float
    data_download: float
    task_length: float
    required_core: int
    vm_utilization_on_edge: float
    vm_utilization_on_cloud: float
    vm_utilization_on_mobile: float


# Mirrors scripts/ReSACO/config/applications.xml (== scripts/three_tier's,
# verified identical) -- the actual, fixed task mix every real simulation
# run uses, as opposed to Table II's abstract per-scenario ranges this
# module used to sample a single homogeneous task profile from.
APP_PROFILES = [
    AppProfile(
        name="AUGMENTED_REALITY", usage_percentage=30, poisson_interarrival=2,
        delay_sensitivity=0.9, active_period=40, idle_period=20,
        data_upload=1500, data_download=25, task_length=9000, required_core=1,
        vm_utilization_on_edge=6, vm_utilization_on_cloud=0.6, vm_utilization_on_mobile=20,
    ),
    AppProfile(
        name="HEALTH_APP", usage_percentage=20, poisson_interarrival=3,
        delay_sensitivity=0.7, active_period=45, idle_period=90,
        data_upload=20, data_download=1250, task_length=3000, required_core=1,
        vm_utilization_on_edge=2, vm_utilization_on_cloud=0.2, vm_utilization_on_mobile=10,
    ),
    AppProfile(
        name="HEAVY_COMP_APP", usage_percentage=20, poisson_interarrival=20,
        delay_sensitivity=0.1, active_period=60, idle_period=120,
        data_upload=2500, data_download=200, task_length=45000, required_core=1,
        vm_utilization_on_edge=30, vm_utilization_on_cloud=3, vm_utilization_on_mobile=50,
    ),
    AppProfile(
        name="INFOTAINMENT_APP", usage_percentage=30, poisson_interarrival=7,
        delay_sensitivity=0.3, active_period=30, idle_period=45,
        data_upload=25, data_download=1000, task_length=15000, required_core=1,
        vm_utilization_on_edge=10, vm_utilization_on_cloud=1, vm_utilization_on_mobile=25,
    ),
]


@dataclass
class Scenario:
    """A single deployment condition sampled for the Outer Loop: which of
    the four real app types this simulated device runs (app_profile) and
    how many other devices (number_of_mobile_devices) are contending for
    the same shared edge/cloud pools (see env.py's background-load
    injection). Meta-training diversity now comes from this app-type x
    device-count combination instead of randomizing task characteristics
    within an abstract range that didn't actually match any real app
    (e.g. the old Table II task_length range topped out at 10000, while
    the real HEAVY_COMP_APP's mean is 45000)."""

    app_profile: AppProfile
    number_of_mobile_devices: int


def sample_scenario(rng: random.Random = random) -> Scenario:
    """Picks one AppProfile weighted by its usage_percentage (matching
    IdleActiveLoadGenerator's per-device app-type assignment) and a
    random device count (Table II's range)."""
    r = config.METADATA_RANGES
    weights = [p.usage_percentage for p in APP_PROFILES]
    app_profile = rng.choices(APP_PROFILES, weights=weights, k=1)[0]
    return Scenario(
        app_profile=app_profile,
        number_of_mobile_devices=int(rng.uniform(*r["number_of_mobile_devices"])),
    )


def sample_scenario_pool(num_scenarios: int, seed: int = None):
    rng = random.Random(seed)
    return [sample_scenario(rng) for _ in range(num_scenarios)]
