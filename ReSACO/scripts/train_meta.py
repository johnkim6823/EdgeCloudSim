"""Run the ReSACO Meta-Learning Phase (Algorithm 1) and save theta*.

Usage:
    python scripts/train_meta.py [--scenarios M] [--outer K] [--inner N] [--out PATH]

Defaults reproduce the paper's Section V-B-1 setup (M=10, K=300, N=50), but
these can be scaled down for a quick smoke test.
"""

import argparse
import os
import sys

import torch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from resaco import config
from resaco.reptile import outer_loop
from resaco.scenario import sample_scenario_pool


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--scenarios", type=int, default=config.NUM_META_SCENARIOS)
    parser.add_argument("--outer", type=int, default=config.NUM_OUTER_ITERATIONS)
    parser.add_argument("--inner", type=int, default=config.NUM_INNER_SAC_UPDATES)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--out", type=str, default=os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "checkpoints", "theta_star.pt"))
    args = parser.parse_args()

    os.makedirs(os.path.dirname(args.out), exist_ok=True)

    print(f"Sampling {args.scenarios} meta-training scenarios (Table II ranges)...")
    scenarios = sample_scenario_pool(args.scenarios, seed=args.seed)
    for i, s in enumerate(scenarios):
        print(f"  S{i}: devices={s.number_of_mobile_devices} "
              f"interarrival={s.poisson_interarrival:.1f}s "
              f"vm_util(edge/cloud/mobile)={s.vm_utilization_on_edge:.1f}/"
              f"{s.vm_utilization_on_cloud:.2f}/{s.vm_utilization_on_mobile:.1f}")

    print(f"\nRunning Outer Loop: K={args.outer} outer iterations, "
          f"N={args.inner} inner SAC updates per iteration...")
    reward_log = []
    theta_star = outer_loop(
        scenarios,
        num_outer_iterations=args.outer,
        num_inner_updates=args.inner,
        seed=args.seed,
        progress_every=max(1, args.outer // 15),
        reward_log=reward_log,
    )

    torch.save(theta_star, args.out)
    print(f"\nSaved meta-learned parameter theta* -> {args.out}")
    if reward_log:
        print(f"Reward trend (avg greedy reward per logged iter): "
              f"first={reward_log[0]:.3f} last={reward_log[-1]:.3f}")


if __name__ == "__main__":
    main()
