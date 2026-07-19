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
   DDPG) learning online from real outcomes (Algorithm 4 in production),
   periodically flushing that online adaptation back to disk so it survives
   a bridge restart (see "Online-learning persistence" below).
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
  config.py          device-count range + Section V-B-1 hyperparameters
  scenario.py         AppProfile x device-count scenario sampling (see "Scenarios" below)
  env.py               lightweight 3-tier offload environment (state/action/reward, Section III)
  networks.py          discrete Actor + twin Critic (Fig. 3)
  replay_buffer.py      replay buffer D
  normalize.py          fixed per-feature state normalization (see "Convergence" below)
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

tests/                  pytest suite -- see "Tests" below

checkpoints/  (gitignored) trained weights + training/comparison/convergence logs and plots
              theta_star.pt/sac_no_meta.pt/ddpg.pt never change after training;
              online adaptation instead accumulates in a sibling
              "<name>_adapted.pt" file written by the bridge (see below)
```

## Setup

```
python -m venv venv
venv\Scripts\pip install -r requirements.txt      # Windows
./venv/bin/pip install -r requirements.txt        # Linux/Mac
```

`requirements.txt` is version-pinned to what's actually been tested here
(including `pytest`, for the test suite below) -- a plain `pip install -r
requirements.txt` reproduces the same dependency versions every time
instead of whatever happens to be latest on the day you install.

## Tests

```
python -m pytest tests/          # from inside ReSACO/, with venv active
```

Also runs automatically on every push/PR via
`../.github/workflows/tests.yml` (a separate CI job runs
`scripts/tests/` too), so a regression here shows up without anyone
having to remember to run `pytest` locally.

44 tests, ~3-4 seconds, no GPU/network/trained-checkpoint dependency
(agents are freshly constructed per test; `test_bridge.py` writes throwaway
fake checkpoints to `tmp_path` rather than touching `checkpoints/`).
Coverage is weighted toward regression protection for the bugs found and
fixed this session -- each is a real prior failure mode, not a
hypothetical:
- `test_sac.py` -- `sac_update_loop` must perform exactly N real gradient
  updates even when N < `BATCH_SIZE` (the exact condition that made the
  Reptile Inner Loop a silent no-op; see "Convergence" above).
- `test_reptile.py` -- an end-to-end check that the Outer Loop actually
  moves `theta` away from its random initialization.
- `test_normalize.py`, `test_env.py` -- the state-normalization fix and
  the device-tier delay/background-contention fixes.
- `test_baselines.py` -- DDPG/A2C/A3C each use their own tuned learning
  rate, not SAC's.
- `test_deploy.py`, `test_bridge.py` -- the online-learning persistence
  (autosave-every-N-updates, resume-from-adapted-checkpoint on restart).
- `test_replay_buffer.py` -- basic sanity coverage for the one piece of
  shared state every agent depends on.
- `test_scenario.py` -- the four real app profiles are present and match
  `applications.xml`, and `sample_scenario_pool`'s app-type mix roughly
  tracks each profile's `usage_percentage` (see "Scenarios" below).

Not covered: the Java side, the TCP wire protocol end-to-end (covered
manually -- see this file's protocol section -- not by an automated
socket test), and anything requiring a trained checkpoint (convergence
quality, actual tier-selection behavior) -- those are evaluated by
actually running `train_meta.py`/`plot_convergence.py`/
`compare_algorithms.py`, not asserted on in a fast unit test.

## Scenarios

Every meta-training scenario now picks one of the four *real* application
types (`scripts/{ReSACO,three_tier}/config/applications.xml`'s
`AUGMENTED_REALITY`, `HEALTH_APP`, `HEAVY_COMP_APP`, `INFOTAINMENT_APP`,
mirrored exactly in `scenario.py`'s `APP_PROFILES`), weighted by that
app's real `usage_percentage` -- matching how EdgeCloudSim's own
`IdleActiveLoadGenerator` assigns each mobile device exactly one app type
for the whole simulation. `env.py`'s `_sample_task()` then draws task
length / upload / download size from an exponential distribution around
that app's own mean, exactly like `IdleActiveLoadGenerator`'s
`ExponentialDistribution`, not a bounded uniform jitter.

**Fixed this pass:** the previous version sampled task_length,
data_upload/download, poisson_interarrival, delay_sensitivity,
active/idle period, and vm_utilization_on_* from a single abstract
"Table II range" -- a homogeneous task profile no real simulation run
ever actually uses. It also meaningfully understated task variety: the
old task_length range topped out at 10000, while `HEAVY_COMP_APP`'s real
mean is 45000 -- so the training distribution never included the kind of
long, expensive task the real deployment generates roughly a fifth of the
time. `number_of_mobile_devices` is still randomized per scenario (Table
II's range, 200-2000) since it's a genuinely free environmental
condition no config file fixes.

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

**Result, run locally:** the two curves still do **not** clearly reproduce
the paper's shape (meta-init starting higher and converging within a
handful of episodes) -- at the paper's own Table II defaults (K=300, N=50,
M=10), meta-init and random-init end up statistically close on a fresh
held-out scenario (overall mean reward across 300 episodes: meta-init
-1.95 vs. random-init -1.92 in one local run). This is no longer because
training silently does nothing (see "Fixed" below) -- it now measurably
learns -- but M=10 meta-training scenarios refined by Reptile's
deliberately small per-iteration step (`META_LR`) just isn't much signal
to generalize from onto a *new* scenario at this budget. A local test with
an 8x larger budget (`python scripts/train_meta.py --outer 1200 --inner
100`) did produce a policy with a much lower failure rate against a fixed
evaluation set (0.6% vs. 19.7% at the K=300/N=50 default) -- but it also
fully collapsed onto always picking the device tier regardless of state,
which avoids contention-driven failures but forfeits the throughput edge
and cloud offer when they're *not* contended. Getting a genuinely
scenario-adaptive policy (not collapsed to one dominant action either way)
most likely needs some combination of a larger/more diverse meta-training
scenario pool, entropy-coefficient tuning, or reward shaping -- none of
which this pass attempted. The script itself is a correct, working
reproduction of the paper's *procedure*.

**Fixed this pass** (previously the training pipeline was silently
producing an untrained network no matter how long you ran it -- see
`resaco/sac.py`, `resaco/env.py`, `resaco/normalize.py`,
`resaco/config.py`):
- `sac_update_loop`'s inner-loop transition count (N=50, Algorithm 2) was
  smaller than `BATCH_SIZE` (64), so `update()` silently never fired
  during Reptile's Inner Loop -- every outer iteration's `theta_k` came
  back byte-identical to `theta`, so `theta_star.pt` was just its random
  initialization after all 300 outer iterations, no matter what. Fixed by
  warming the replay buffer up to `batch_size` *before* starting the N
  counted (and now guaranteed-real) update steps.
- The raw state vector mixes wildly different physical scales (task
  length ~1500-10000, utilization 0-150%, bandwidth 0-200 Mbps) with no
  normalization, feeding straight into a plain MLP -- in practice this
  caused the actor to collapse onto one or two fixed actions almost
  independent of the actual state. Fixed via `resaco/normalize.py`, a
  small fixed (not learned) per-feature scale applied identically at
  train and serve time. Isolated before/after test on one fixed
  high-contention scenario: 34.2% task failure rate before
  normalization, 0.2% after, with the agent correctly learning to prefer
  the device tier once state scale stopped drowning it out.
- The device (mobile) tier incorrectly incurred the same WLAN transfer
  delay as the edge tier, even though local execution never sends data
  anywhere -- this alone made device strictly dominated by edge in nearly
  every case. Fixed: local execution now has zero network delay.
- `number_of_mobile_devices` was sampled into every scenario but never
  actually consumed anywhere in `env.py` -- a 200-device and a
  2,000-device scenario looked identical to the agent. Fixed by injecting
  a Poisson-sampled batch of background tasks from the scenario's other
  devices into the shared edge/cloud pools every step (see
  `env._inject_background_load`), so `mu_edge`/`mu_cloud` -- which the
  agent does observe -- now actually rise with device count.
- DDPG/A2C/A3C blindly reused SAC's `ACTOR_LR`/`CRITIC_LR`. Fixed: DDPG
  now gets its own (faster-critic) learning rates typical for that
  algorithm family (`DDPG_ACTOR_LR`/`DDPG_CRITIC_LR`), and A2C/A3C share
  their own on-policy learning rate (`A2C_LR`) instead.

## Compare (fast, toy environment)

```
python scripts/compare_algorithms.py
```

Sweeps mobile-device count 200-2,000 (step 200) and reports completion
rate, average service/processing time, network delay, and failure
breakdown per algorithm, mirroring the paper's Fig. 6/7 and Table III.
Writes `checkpoints/comparison.csv`. Runs in seconds, but see the caveat
below -- for a real comparison, use the EdgeCloudSim route instead.

The printed "Table III style" summary reports ReSACO's service-time
improvement as a relative percentage (a duration, essentially never at/near
zero, so relative-percent is meaningful there), but its network/VM failure
rate improvement as an absolute **percentage-point** difference (`pp`) --
those are already bounded in [0, 100], and a relative-percent formula blows
up whenever a baseline's rate is at or near zero (division by ~0), which is
common here since network failures never happen in this env.

**Caveat:** `env.py` is a compact, self-contained reimplementation of the
paper's state/action/reward formulas (Section III) used to train and
compare agents quickly -- it is *not* the full CloudSim discrete-event
simulation. The device-count sweep now injects real background contention
into the shared edge/cloud pools proportional to device count (not just an
interarrival-time scaling factor -- see the "Fixed this pass" list above),
and the resulting trend is qualitatively correct: completion rate falls
smoothly as device count rises (ReSACO/SAC/DDPG go from ~90% completion at
200 devices to ~47% at 2,000; A2C/A3C, served frozen/on-policy, degrade
much more gracefully, ~100% down to ~80-99%).

That said, the comparison numbers still do **not** reproduce the paper's
specific finding that ReSACO wins across the board -- at the paper's
Table II default training budget, ReSACO/SAC/DDPG actually show the
*highest* VM-failure rates of the five (e.g. 53% vs. A3C's 0.4% at 2,000
devices), consistent with the same under-trained-at-default-budget
limitation described in "Convergence" above. This pipeline is a correct,
runnable reproduction of the algorithms and evaluation *structure*, with a
now-meaningful device-count contention signal; matching the paper's
specific quantitative claims needs more meta-training budget/tuning than
the fast, paper-matched defaults spend by design. Scaling up
`--steps`/`--outer`/`--inner` would be the next step toward a truer
reproduction.

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

**Fixed this pass:** `ReSACOStateBuilder.build()` (Java side) was sending
`b_wlan`/`b_man`/`b_wan` straight from `SimSettings.getWlanBandwidth()` and
friends -- whose JavaDoc claims "Mbps unit" but which actually return the
config file's Mbps value pre-multiplied by 1000 for internal Kbps-based
delay math. `resaco/config.py` and everything trained against it
(including `normalize.py`'s fixed scale factors) are in Mbps, so this real
EdgeCloudSim-integrated path -- the one this whole project exists to
enable -- was feeding the served policy bandwidth values ~1000x anything
it ever saw during training, on 3 of its 18 state dimensions, on every
single decision. Fixed by dividing by 1000 in `ReSACOStateBuilder.java`.
Verified both that it compiles and, by running a real scenario against a
logging stand-in bridge, that the wire values now read `200.0 0.0 15.0`
(Mbps) instead of `200000.0 0.0 15000.0` (Kbps).

Separately (not fixed this pass): even with the unit corrected, these
values are still *static* -- read once from the config file, never
reflecting live network congestion -- whereas `env.py`'s training-time
`_bandwidth()` randomly degrades bandwidth every step, so the model
learned to treat bandwidth *variation* as informative. In real deployment
these 3 dimensions are constant, so that signal is simply unavailable
there. `ThreeTierNetworkModel` does track live per-access-point client
counts (`wlanClients[]`/`wanClients[]`) that feed its own MM1-queue delay
model -- surfacing a congestion proxy derived from those instead of the
static config value would be the natural next step.

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
`ReSACOBridgeClient` also applies a 10s read timeout on every request, so a
bridge that's up but hung (as opposed to down/refusing connections, which
was already handled) can't block the simulation forever either -- a
timed-out request is treated the same as any other connection failure.

The bridge server itself locks per-algo, not with one lock shared across
all five -- RESACO/SAC_BASELINE/DDPG_BASELINE/A2C_BASELINE/A3C_BASELINE
each have completely independent state (own networks, own replay buffer),
so there was never a reason for e.g. RESACO's training step or its
autosave's blocking `torch.save()` to hold up a concurrent `ACT`/`OUTCOME`
for a different algo. A single global lock did exactly that; each algo
now only ever waits on its own lock.

Protocol (newline-delimited, one request per line):

```
ACT <algo> <request_id> <L> <U> <D> <mu_d> <mu_e1> ... <mu_eN> <mu_c> <bwlan> <bman> <bwan>
    -> "<action_int>"        0=device, 1..N=edge server, N+1=cloud
                              <algo> in {RESACO, SAC_BASELINE, DDPG_BASELINE, A2C_BASELINE, A3C_BASELINE}

OUTCOME <algo> <request_id> <reward> <done:0|1> <next_state...>
    -> "OK" | "IGNORED"      IGNORED means request_id was never seen by ACT for this algo
                              (e.g. the bridge was down/restarted at decision time)

SAVE [<algo> [<path>]]
    -> "OK" | "ERROR ..."    no args: flush every persist-capable algo's live params to its
                              own "<checkpoint>_adapted.pt" (same thing autosave does)
                              algo only: flush just that algo's live params to its own adapted
                              path (ERROR if that algo has nothing to persist, e.g. A2C/A3C)
                              algo + path: dump that algo's current params to an arbitrary path
```

## Online-learning persistence

`DeploymentAgent` (ReSACO, SAC_BASELINE, DDPG_BASELINE -- the three
off-policy algorithms) keeps adapting `theta_adapt` in memory from every
`OUTCOME` the bridge receives. Without saving that anywhere, all of it
would be lost the moment the bridge process restarts, which would make
Algorithm 4's "online" adaptation pointless in practice. Instead:

- Every `--autosave-every` successful updates (default 50), the adapting
  agent flushes its current params to `checkpoints/<name>_adapted.pt` --
  e.g. `theta_star.pt` -> `theta_star_adapted.pt`. The original
  meta-trained/baseline-trained checkpoint is **never** overwritten, so
  it always stays available as a known-good fallback.
- On startup, `load_agents()` prefers the `*_adapted.pt` file over the
  original if one exists, so online adaptation accumulates across
  restarts instead of resetting to `theta_star.pt` every time. The
  startup log distinguishes `Resumed online-adapted checkpoints for: ...`
  from `Loaded trained checkpoints for: ...` so it's obvious which each
  algo did.
- On a clean shutdown (Ctrl+C, or `SIGTERM` on Linux/Mac), the bridge
  saves every agent one more time before exiting, so at most
  `autosave_every - 1` updates' worth of progress can ever be lost.
- A2C/A3C are served frozen (`FrozenPolicyAgent`) and never adapt, so
  they have nothing to persist -- `SAVE A2C_BASELINE`/`A3C_BASELINE`
  (with no explicit path) returns an error by design.

To reset online learning and go back to the original trained policy,
just delete the relevant `checkpoints/*_adapted.pt` file(s) and restart
the bridge.

```
python bridge/inference_server.py --autosave-every 50   # default; lower it for faster testing
```

## Known limitations

- `env.py` models a single agent-controlled device's task stream against
  shared edge/cloud capacity pools; other devices are represented as
  injected background load (see "Fixed this pass" above), not as literally
  simulated independent agents. It is a research/training aid, not a
  literal multi-agent discrete-event simulation.
- At the paper's Table II default training budget (M=10, K=300, N=50),
  the resulting policies (ReSACO and, to a lesser extent, SAC/DDPG) don't
  yet reliably show either a clear meta-init-vs-random-init advantage or a
  clear win over the on-policy baselines -- see "Convergence" and "Compare"
  above for the concrete numbers and what a larger budget does to them.
  The training pipeline itself is verified correct (gradients genuinely
  flow, and an isolated test showed the agent correctly learning to prefer
  the device tier when contention makes it the better choice); reaching
  paper-competitive numbers needs more meta-training budget/tuning than
  the fast, paper-matched defaults spend by design.
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
