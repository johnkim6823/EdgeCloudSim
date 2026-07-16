"""Lightweight three-layer MEC offloading environment.

This reimplements the state/action/reward/failure model described in the
ReSACO paper (Section III "System Model" and Section IV-A-2 "Inner Loop")
as a compact, self-contained simulator. It is used to train (meta-train and
adapt) the SAC agent quickly without needing the full CloudSim event engine.
The physical tier parameters (VM MIPS/cores, bandwidths) mirror
EdgeCloudSim's scripts/three_tier config so behaviour stays consistent with
the Java simulator this agent will later be plugged into.

State:  s_t = (L, U, D, mu_d, mu_e1..mu_eN, mu_c, b_wlan, b_man, b_wan)
Action: a_t in {0..N+1}: 0 = device, 1..N = edge servers, N+1 = cloud
Reward: r_t = -T on success (Eq. 9), -(Tmax+1) on failure
"""

import random
from dataclasses import dataclass

import numpy as np

from . import config
from .scenario import Scenario


@dataclass
class Task:
    length: float          # L, million instructions (MI)
    data_upload: float     # U, Kb
    data_download: float   # D, Kb
    required_core: int


class MECOffloadEnv:
    """One "MD" generating tasks against N edge servers + 1 cloud + itself.

    Utilization of every VM is tracked as a percentage (0-100). Assigning a
    task occupies vm_utilization_on_X percent of the chosen VM for the
    duration of its processing time; capacity is freed once the task
    finishes. This mirrors EdgeCloudSim's CpuUtilizationModel_Custom /
    getTotalUtilizationOfCpu admission-control logic closely enough for
    training purposes.
    """

    def __init__(self, scenario: Scenario, num_edge_servers: int = config.NUM_EDGE_SERVERS,
                 seed: int = None):
        self.scenario = scenario
        self.n_edge = num_edge_servers
        self.rng = random.Random(seed)

        # utilization[0] = single mobile VM, utilization[1..N] = one
        # representative VM per edge server (least-loaded proxy), utilization[-1] = cloud
        self.mu_mobile = 0.0
        self.mu_edge = [0.0] * self.n_edge
        self.mu_cloud = 0.0

        # (utilization_delta, release_time) queues so occupied capacity is
        # freed once a task's processing time elapses.
        self.clock = 0.0
        self._pending_release = []  # list of (release_time, layer, index, delta)

        self.current_task: Task = None
        self._current_state = None

    # ------------------------------------------------------------------
    def _sample_task(self) -> Task:
        s = self.scenario
        length = self.rng.uniform(*_jitter_range(s.task_length, 0.3))
        upload = self.rng.uniform(*_jitter_range(s.data_upload, 0.3))
        download = self.rng.uniform(*_jitter_range(s.data_download, 0.3))
        return Task(length=max(length, 1.0), data_upload=max(upload, 1.0),
                    data_download=max(download, 1.0), required_core=s.required_core)

    def _bandwidth(self) -> tuple:
        """Sample current available bandwidth (Mbps), degraded by load."""
        wlan = config.WLAN_BANDWIDTH_MBPS * (1.0 - 0.5 * self.rng.random())
        man = config.MAN_BANDWIDTH_MBPS * (1.0 - 0.5 * self.rng.random())
        wan = config.WAN_BANDWIDTH_MBPS * (1.0 - 0.5 * self.rng.random())
        return wlan, man, wan

    def _release_expired(self):
        still_pending = []
        for release_time, layer, index, delta in self._pending_release:
            if release_time <= self.clock:
                if layer == "mobile":
                    self.mu_mobile = max(0.0, self.mu_mobile - delta)
                elif layer == "edge":
                    self.mu_edge[index] = max(0.0, self.mu_edge[index] - delta)
                elif layer == "cloud":
                    self.mu_cloud = max(0.0, self.mu_cloud - delta)
            else:
                still_pending.append((release_time, layer, index, delta))
        self._pending_release = still_pending

    def _build_state(self, task: Task, bw) -> np.ndarray:
        wlan, man, wan = bw
        return np.array(
            [task.length, task.data_upload, task.data_download, self.mu_mobile]
            + list(self.mu_edge)
            + [self.mu_cloud, wlan, man, wan],
            dtype=np.float32,
        )

    def reset(self) -> np.ndarray:
        self.clock = 0.0
        self.mu_mobile = 0.0
        self.mu_edge = [0.0] * self.n_edge
        self.mu_cloud = 0.0
        self._pending_release = []
        self.current_task = self._sample_task()
        bw = self._bandwidth()
        self._current_bw = bw
        self._current_state = self._build_state(self.current_task, bw)
        return self._current_state

    # ------------------------------------------------------------------
    def step(self, action: int):
        """Apply the offloading decision for the current task, return
        (next_state, reward, done, info)."""
        self._release_expired()
        task = self.current_task
        s = self.scenario
        wlan, man, wan = self._current_bw

        if action == 0:
            layer, index = "mobile", 0
            mu_required = s.vm_utilization_on_mobile
            mu_current = self.mu_mobile
            mips = config.MOBILE_VM_MIPS
            delay = self._transfer_delay(task, wlan)
        elif 1 <= action <= self.n_edge:
            layer, index = "edge", action - 1
            mu_required = s.vm_utilization_on_edge
            mu_current = self.mu_edge[index]
            mips = config.EDGE_VM_MIPS
            delay = self._transfer_delay(task, wlan) + self._transfer_delay(task, man) * 0.1
        else:
            layer, index = "cloud", 0
            mu_required = s.vm_utilization_on_cloud
            mu_current = self.mu_cloud
            mips = config.CLOUD_VM_MIPS
            delay = self._transfer_delay(task, wlan) + self._transfer_delay(task, wan)

        network_fail = delay > config.TMAX_SECONDS
        vm_fail = (mu_current + mu_required) > 100.0

        if network_fail or vm_fail:
            reward = -(config.TMAX_SECONDS + 1.0)
            done_info = {"failed": True, "network_fail": network_fail, "vm_fail": vm_fail}
            service_time = None
        else:
            process_time = task.length / mips  # T_process(i) ~= L_i / mu*  (paper Eq. after (1))
            service_time = process_time + delay
            self._occupy(layer, index, mu_required, process_time)
            reward = -service_time
            done_info = {"failed": False, "service_time": service_time, "delay": delay}

        # advance the environment clock by the per-task Poisson inter-arrival time
        self.clock += self.rng.expovariate(1.0 / max(s.poisson_interarrival, 0.1))

        self.current_task = self._sample_task()
        self._current_bw = self._bandwidth()
        next_state = self._build_state(self.current_task, self._current_bw)
        self._current_state = next_state

        return next_state, reward, False, done_info

    def _occupy(self, layer, index, mu_required, process_time):
        release_time = self.clock + process_time
        self._pending_release.append((release_time, layer, index, mu_required))
        if layer == "mobile":
            self.mu_mobile += mu_required
        elif layer == "edge":
            self.mu_edge[index] += mu_required
        elif layer == "cloud":
            self.mu_cloud += mu_required

    @staticmethod
    def _transfer_delay(task: Task, bandwidth_mbps: float) -> float:
        if bandwidth_mbps <= 0:
            return float("inf")
        data_mbit = (task.data_upload + task.data_download) / 1000.0 * 8.0
        return config.WAN_PROPAGATION_DELAY + data_mbit / bandwidth_mbps


def _jitter_range(center: float, frac: float):
    lo = max(center * (1 - frac), 1.0)
    hi = center * (1 + frac)
    return lo, hi
