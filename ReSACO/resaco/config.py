"""Hyperparameters and metadata ranges for ReSACO (Table II, Section V-A/V-B)."""

# ----------------------------------------------------------------------------
# Device / Edge / Cloud tier configuration (Section V-A-2, matches
# EdgeCloudSim's scripts/three_tier/config/default_config.properties and
# edge_devices.xml so the trained policy is consistent with the simulator).
# ----------------------------------------------------------------------------
NUM_EDGE_SERVERS = 10
VMS_PER_EDGE_SERVER = 8

MOBILE_VM_MIPS = 4000
MOBILE_VM_CORES = 1

EDGE_VM_MIPS = 10000
EDGE_VM_CORES = 2

CLOUD_VM_COUNT = 4
CLOUD_VM_MIPS = 100000
CLOUD_VM_CORES = 4

WLAN_BANDWIDTH_MBPS = 200
WAN_BANDWIDTH_MBPS = 15
MAN_BANDWIDTH_MBPS = 200
WAN_PROPAGATION_DELAY = 0.1
LAN_INTERNAL_DELAY = 0.005

# Delay threshold used by the network failure indicator F_network (Eq. 2).
TMAX_SECONDS = 5.0

# ----------------------------------------------------------------------------
# Metadata ranges used to build randomized training scenarios. Per-app-type
# task characteristics (task_length, data_upload/download, poisson_interarrival,
# delay_sensitivity, active/idle period, vm_utilization_on_*) now live in
# scenario.py's APP_PROFILES instead of being sampled from an abstract range
# here -- they mirror the applications.xml config every real simulation run
# actually uses. number_of_mobile_devices is the one thing that's still a
# genuinely free environmental condition (not fixed by any config file), so
# it's the only range left here.
# ----------------------------------------------------------------------------
METADATA_RANGES = {
    "number_of_mobile_devices": (200, 2000),
}

# ----------------------------------------------------------------------------
# State / action space (Section IV-A-2)
# state = {L, U, D, mu_d, mu_e1..mu_eN, mu_c, b_wlan, b_man, b_wan}
# action in {0, ..., N+1}: 0 = device, 1..N = edge servers, N+1 = cloud
# ----------------------------------------------------------------------------
STATE_DIM = 4 + NUM_EDGE_SERVERS + 1 + 3  # L,U,D,mu_d + mu_e(N) + mu_c + bwlan,bman,bwan
ACTION_DIM = NUM_EDGE_SERVERS + 2

# ----------------------------------------------------------------------------
# SAC / Reptile hyperparameters (Section V-B-1)
# ----------------------------------------------------------------------------
META_LR = 0.001          # alpha: Reptile meta learning rate
DISCOUNT_GAMMA = 0.99
ENTROPY_TAU = 0.2
REPLAY_BUFFER_SIZE = 100_000
BATCH_SIZE = 64
TARGET_SOFT_UPDATE_RHO = 0.995
CRITIC_LR = 3e-4
ACTOR_LR = 3e-4

NUM_META_SCENARIOS = 10   # M
NUM_OUTER_ITERATIONS = 300  # K
NUM_INNER_SAC_UPDATES = 50  # N

HIDDEN_SIZES = (128, 128)

# ----------------------------------------------------------------------------
# Baseline-specific hyperparameters (Section V-C). Only ReSACO and the
# SAC-no-meta-init baseline actually use SAC-Update, so only they use the
# SAC hyperparameters above; DDPG and A2C/A3C get their own learning rates
# tuned to what's typical for each algorithm family, instead of blindly
# reusing SAC's ACTOR_LR/CRITIC_LR.
# ----------------------------------------------------------------------------
# DDPG's critic conventionally learns faster than its actor (Lillicrap et
# al. 2015 uses 1e-3 critic / 1e-4 actor) so the critic can track a
# deterministic, faster-moving target.
DDPG_ACTOR_LR = 1e-4
DDPG_CRITIC_LR = 1e-3

# A2C/A3C are on-policy, single-short-rollout-per-update methods (no replay
# buffer to average noise out over) -- a single higher shared actor/critic
# LR is the typical choice for both (used here by both A2C and the A2CAgent
# A3C's global model gets wrapped into).
A2C_LR = 7e-4
