# ReSACO

A from-scratch implementation of **ReSACO** (Reptile-based Soft Actor-Critic
for Offloading) from *"ReSACO: A Meta Reinforcement Learning Method for Fast
Offloading in Mobile Edge Computing"* (Kim & Yu, IEEE CLOUD 2025) -- a
Reptile meta-learning loop wrapped around a discrete-action Soft
Actor-Critic agent that decides, per task, whether to run it on the
**device**, an **edge** server, or the **cloud**.

It has three parts:

1. **`resaco/`** -- the AI model itself: networks, replay buffer, SAC-Update
   (Algorithm 3), the Reptile Outer/Inner Loop meta-training (Algorithms
   1-2), and the Deployment Phase (Algorithm 4), plus the four baselines
   the paper compares against (SAC without meta-init, DDPG, A2C, A3C).
2. **`bridge/inference_server.py`** -- a small TCP server that serves all
   five trained policies (ReSACO + the four baselines) for live offloading
   decisions, keyed by name, and keeps the off-policy ones (ReSACO, SAC,
   DDPG) learning online from real outcomes (Algorithm 4 in production).
3. Integration with **EdgeCloudSim**: `../EdgeCloudSim/src/edu/boun/edgecloudsim/applications/resaco/`
   is a full EdgeCloudSim application (its own `ReSACOMainApp`,
   `ReSACOEdgeOrchestrator`, etc., mirroring the existing `three_tier` app)
   whose orchestrator calls into this bridge for every offloading decision.
   `three_tier` itself is untouched -- `resaco` only *reuses* its generic,
   unmodified `ThreeTierNetworkModel` / `ThreeTierMobileServerManager`.
   Listing all five algorithms as `orchestrator_policies` runs all five
   through the *real* CloudSim discrete-event simulation in the same
   EdgeCloudSim experiment -- a much more meaningful comparison than
   `compare_algorithms.py`'s lightweight toy environment (see below).

## Quick start

```
python -m venv venv
venv/bin/pip install -r requirements.txt        # Linux/Mac; use venv\Scripts\pip on Windows

venv/bin/python scripts/train_meta.py            # -> checkpoints/theta_star.pt (ReSACO)
venv/bin/python scripts/train_baselines.py       # -> checkpoints/{sac_no_meta,ddpg,a2c,a3c}.pt

venv/bin/python bridge/inference_server.py       # leave running in its own terminal

# in another terminal:
cd ../EdgeCloudSim/scripts/ReSACO
./compile.sh
./run_scenarios.sh 4 1                           # 4 parallel processes, 1 iteration
```

That's ReSACO and all four paper baselines trained, served, and run
through the real EdgeCloudSim/CloudSim simulation end to end. See
"Compare" and "Serve to EdgeCloudSim" below for what each piece is
actually doing, and the Known limitations section before treating the
numbers as validated results.

## Layout

```
resaco/
  config.py          Table II metadata ranges + Section V-B-1 hyperparameters
  scenario.py         randomized scenario (metadata) sampling
  env.py               lightweight 3-tier offload environment (state/action/reward, Section III)
  networks.py          discrete Actor + twin Critic (Fig. 3)
  replay_buffer.py      replay buffer D
  sac.py               SACAgent: SAC-Update (Algorithm 3, Eq. 9-13)
  reptile.py            Outer Loop / Inner Loop meta-training (Algorithm 1-2, Eq. 8)
  deploy.py             DeploymentAgent: Deployment Phase (Algorithm 4)
  baselines/
    ddpg.py             DDPG, discrete-adapted (softmax-relaxed actor output fed to the critic)
    a2c.py               synchronous Advantage Actor-Critic
    a3c.py               asynchronous A3C (shared global net, threaded workers, Hogwild!-style updates)

bridge/
  inference_server.py    TCP ACT/OUTCOME server wrapping a DeploymentAgent

scripts/
  train_meta.py          run Algorithm 1 -> checkpoints/theta_star.pt
  train_baselines.py     train SAC(no meta-init)/DDPG/A2C/A3C with the same step budget as ReSACO
  compare_algorithms.py  Section V-C style comparison across MD counts -> checkpoints/comparison.csv
  plot_convergence.py    Section V-B / Fig. 5 style meta-init vs. random-init convergence plot

checkpoints/  (gitignored) trained weights + training/comparison/convergence logs and plots
```

## Setup

```
python -m venv venv
venv\Scripts\pip install -r requirements.txt      # Windows
./venv/bin/pip install -r requirements.txt        # Linux/Mac
```

## Train

```
python scripts/train_meta.py          # ReSACO meta-training (Algorithm 1); ~1-2 min at paper defaults (M=10, K=300, N=50)
python scripts/train_baselines.py     # SAC(no meta-init)/DDPG/A2C/A3C, same total env-step budget (K*N)
```

Both scripts accept `--help` for scaled-down smoke-test runs (fewer
scenarios/iterations).

## Convergence (Fig. 5 reproduction)

```
python scripts/plot_convergence.py
```

Reproduces Section V-B's convergence comparison: starting from a new,
held-out test scenario (not in `train_meta.py`'s training pool), it
continually adapts for 300 episodes (each episode = 50 SAC-Update steps,
matching "each episode represents one Outer Loop iteration") from two
initializations -- `theta_star.pt` (meta-init) vs. a fresh random SAC
agent (random-init) -- tracking the greedy-evaluation reward after every
episode, min-max normalized onto the same 0-1 scale as the paper's Fig. 5.
Saves `checkpoints/convergence.png` + `.csv`.

**Result, run locally:** the two curves do **not** reproduce the paper's
shape. The paper expects meta-init to start higher and converge within a
handful of episodes, with random-init starting low and catching up slowly.
In practice here, random-init stays consistently *better* than meta-init
across all 300 episodes, and meta-init shows no visible improving trend.
This is consistent with the same theta_star bias noted in "Compare"
below and in `EdgeCloudSim/README.md`'s ReSACO section (the small-scale
toy-environment meta-training converged to a narrow policy -- e.g. it
essentially never picks the device tier -- that transfers poorly to a
genuinely new scenario). The script itself is a correct, working
reproduction of the paper's *procedure*; the *result* needs a
better-trained `theta_star.pt` (more meta-training scenarios/iterations,
a stronger `env.py` contention model) before it demonstrates the paper's
claimed advantage.

## Compare (fast, toy environment)

```
python scripts/compare_algorithms.py
```

Sweeps mobile-device count 200-2,000 (step 200) and reports completion
rate, average service/processing time, network delay, and failure
breakdown per algorithm, mirroring the paper's Fig. 6/7 and Table III.
Writes `checkpoints/comparison.csv`. Runs in seconds, but see the caveat
below -- for a real comparison, use the EdgeCloudSim route instead.

**Caveat:** `env.py` is a compact, self-contained reimplementation of the
paper's state/action/reward formulas (Section III) used to train and
compare agents quickly -- it is *not* the full CloudSim discrete-event
simulation, and the device-count sweep approximates rising contention via
an interarrival-time scaling factor rather than truly simulating thousands
of concurrent devices. At the default (small) training budget, the
comparison numbers do **not** reliably reproduce the paper's specific
finding that ReSACO wins across the board (in local test runs A3C
occasionally beat ReSACO on service time) -- this pipeline is a correct,
runnable reproduction of the algorithms and evaluation *structure*, not a
validated performance benchmark. Scaling up `--steps`/`--outer`/`--inner`
and strengthening the contention model in `env.py` would be the next step
toward a truer reproduction.

## Compare (real CloudSim simulation, via EdgeCloudSim)

```
python bridge/inference_server.py          # loads all 5 checkpoints from checkpoints/
```

Then, from `EdgeCloudSim/scripts/ReSACO/`, run the ReSACO application
(see `EdgeCloudSim/README.md`'s "ReSACO" section) with
`orchestrator_policies=RESACO,SAC_BASELINE,DDPG_BASELINE,A2C_BASELINE,A3C_BASELINE`
(the default). EdgeCloudSim runs each policy as its own scenario over the
real CloudSim discrete-event engine, so this drives all five algorithms
through identical device/edge/cloud topologies, network models and task
workloads -- a far more faithful comparison than the toy `env.py` sweep
above. Results land as regular EdgeCloudSim per-policy log/CSV files
(`scripts/ReSACO/output/...`), one directory per policy.

## Serve to EdgeCloudSim (Deployment Phase / Algorithm 4)

`bridge/inference_server.py` loads whichever of the five checkpoints exist
under `checkpoints/` (`theta_star.pt`, `sac_no_meta.pt`, `ddpg.pt`,
`a2c.pt`, `a3c.pt`) and serves them all simultaneously, selected per
request by an `<algo>` name (`RESACO`, `SAC_BASELINE`, `DDPG_BASELINE`,
`A2C_BASELINE`, `A3C_BASELINE`) that EdgeCloudSim's `ReSACOEdgeOrchestrator`
fills in from its own `orchestrator_policies` config value -- so one bridge
process backs every policy in a single EdgeCloudSim run. Missing
checkpoints are served as randomly-initialized (untrained) policies rather
than refused, so the simulation stays runnable even before every baseline
is trained.

Every task's offloading decision is sent to the bridge over TCP (`ACT`),
and every task's real outcome is reported back (`OUTCOME`). For the
off-policy algorithms (ReSACO, SAC, DDPG) this triggers an incremental
online update (Algorithm 4); the on-policy baselines (A2C, A3C) don't have
a well-defined single-transition update rule, so they're served frozen --
exactly the policy `train_baselines.py` produced. If the bridge or the
requested algorithm's checkpoint is unavailable, EdgeCloudSim falls back to
a static EDGE_PRIORITY-style heuristic instead of crashing the simulation.

Protocol (newline-delimited, one request per line):

```
ACT <algo> <request_id> <L> <U> <D> <mu_d> <mu_e1> ... <mu_eN> <mu_c> <bwlan> <bman> <bwan>
    -> "<action_int>"        0=device, 1..N=edge server, N+1=cloud
                              <algo> in {RESACO, SAC_BASELINE, DDPG_BASELINE, A2C_BASELINE, A3C_BASELINE}

OUTCOME <algo> <request_id> <reward> <done:0|1> <next_state...>
    -> "OK" | "IGNORED"      IGNORED means request_id was never seen by ACT for this algo
                              (e.g. the bridge was down/restarted at decision time)
```

## Known limitations

- `env.py` models a single device's task stream against shared edge/cloud
  capacity pools; it is a research/training aid, not a literal multi-agent
  discrete-event simulation.
- `a3c.py` uses Python threads sharing one process (not
  `torch.multiprocessing`), so it's algorithmically faithful to A3C's
  shared-model/async-gradient structure but doesn't get true multi-core
  parallelism (the GIL serializes it).
- The EdgeCloudSim bridge (`ReSACOBridgeClient`) and the Python
  `DeploymentAgent._pending` dict accumulate a handful of orphaned entries
  for tasks still in-flight when a scenario's simulation clock is cut off
  before they complete; negligible over a normal experiment run, but if
  the bridge process is kept alive across many long-running experiments,
  consider restarting it periodically.
