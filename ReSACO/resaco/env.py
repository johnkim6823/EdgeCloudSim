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

import math
import random
from dataclasses import dataclass

import numpy as np

from . import config
from .scenario import Scenario


# Ceiling background-load injection saturates a tier's utilization at, so
# a heavily-contended scenario reads as "clearly over capacity" without the
# raw state feature growing unbounded as device count climbs into the
# thousands (see _inject_background_load).
_SATURATION_CEILING = 150.0


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

        # Background contention: the scenario's other (number_of_mobile_devices - 1)
        # devices also send tasks into the same shared edge/cloud utilization
        # pools this env's single agent-controlled stream targets. Without
        # this, number_of_mobile_devices would only ever affect training
        # through the poisson_interarrival scaling scripts/compare_algorithms.py
        # applies (which just polls the agent faster -- it never actually
        # raises shared-pool utilization on its own), so a low- and a
        # high-device-count scenario would look almost identical to the
        # agent. Injected every step as a Poisson-sampled batch of admitted
        # background tasks (see _inject_background_load), so mu_edge/mu_cloud
        # -- which the agent does observe in its state -- rise with device
        # count exactly the way real contention would.
        self._background_devices = max(self.scenario.number_of_mobile_devices - 1, 0)

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
            delay = 0.0  # local execution: no data ever leaves the device
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
        elapsed = self.rng.expovariate(1.0 / max(s.poisson_interarrival, 0.1))
        self.clock += elapsed
        self._inject_background_load(elapsed)

        self.current_task = self._sample_task()
        self._current_bw = self._bandwidth()
        next_state = self._build_state(self.current_task, self._current_bw)
        self._current_state = next_state

        return next_state, reward, False, done_info

    def _inject_background_load(self, elapsed: float):
        """Admits a Poisson-sampled batch of background tasks (from the
        scenario's other devices) straight into the edge/cloud pools,
        occupying capacity for their own process time exactly like an
        agent-admitted task. Batched into at most `n_edge + 1` _occupy()
        calls per step (not one call per background device) so cost stays
        independent of device count; the batch size itself still scales
        with it, which is what actually drives up mu_edge/mu_cloud.

        Split 80/20 between edge and cloud, mirroring a default
        edge-priority-style offloading mix, spread evenly across the N
        edge servers so no single server absorbs every other device's load.
        """
        if self._background_devices <= 0 or elapsed <= 0:
            return
        s = self.scenario
        rate = self._background_devices / max(s.poisson_interarrival, 0.1)
        n_arrivals = self._poisson_sample(rate * elapsed)
        if n_arrivals <= 0:
            return

        edge_share = int(round(n_arrivals * 0.8))
        cloud_share = n_arrivals - edge_share

        # A real, already-saturated server rejects excess arrivals rather
        # than piling up unbounded utilization debt -- cap injected load at
        # SATURATION_CEILING so a heavily-contended tier reads as "clearly
        # over capacity" without further inflating the raw state feature
        # (and destabilizing the critic) as device count climbs into the
        # thousands.
        if edge_share > 0 and self.n_edge > 0:
            per_server = edge_share / self.n_edge
            process_time = s.task_length / config.EDGE_VM_MIPS
            desired = per_server * s.vm_utilization_on_edge
            for index in range(self.n_edge):
                room = max(0.0, _SATURATION_CEILING - self.mu_edge[index])
                self._occupy("edge", index, min(desired, room), process_time)

        if cloud_share > 0:
            process_time = s.task_length / config.CLOUD_VM_MIPS
            desired = cloud_share * s.vm_utilization_on_cloud
            room = max(0.0, _SATURATION_CEILING - self.mu_cloud)
            self._occupy("cloud", 0, min(desired, room), process_time)

    def _poisson_sample(self, lam: float) -> int:
        """Knuth's algorithm for small lambda; normal approximation for
        large lambda (avoids the exponential-time blowup Knuth's algorithm
        hits once lam gets into the hundreds/thousands, which happens at
        the paper's upper device-count range)."""
        if lam <= 0:
            return 0
        if lam > 30:
            return max(0, int(round(self.rng.gauss(lam, math.sqrt(lam)))))
        limit = math.exp(-lam)
        k, p = 0, 1.0
        while True:
            k += 1
            p *= self.rng.random()
            if p <= limit:
                return k - 1

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
