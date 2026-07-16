"""Reptile-based meta-training: Outer Loop (Algorithm 1) + Inner Loop (Algorithm 2)."""

import copy
import random

import torch

from . import config
from .env import MECOffloadEnv
from .sac import SACAgent


def _interpolate_params(theta, theta_k, alpha):
    """theta <- theta + alpha * (theta_k - theta)   (Eq. 8)"""
    new_theta = {}
    for group in theta:
        new_theta[group] = {}
        for key in theta[group]:
            new_theta[group][key] = theta[group][key] + alpha * (
                theta_k[group][key] - theta[group][key]
            )
    return new_theta


def inner_loop(theta, scenario, num_inner_updates: int, agent_kwargs=None, seed=None):
    """Algorithm 2: refine a local copy of theta on scenario `scenario` for
    `num_inner_updates` SAC iterations. Returns the refined local theta_k."""
    agent_kwargs = agent_kwargs or {}
    local_agent = SACAgent(**agent_kwargs)
    local_agent.load_params(theta)

    env = MECOffloadEnv(scenario, seed=seed)
    local_agent.sac_update_loop(env, num_transitions=num_inner_updates)

    return local_agent.get_params()


def outer_loop(
    scenarios,
    num_outer_iterations: int = config.NUM_OUTER_ITERATIONS,
    num_inner_updates: int = config.NUM_INNER_SAC_UPDATES,
    meta_lr: float = config.META_LR,
    agent_kwargs=None,
    seed: int = None,
    progress_every: int = 20,
    reward_log=None,
):
    """Algorithm 1: repeatedly sample a scenario, refine a local copy via
    the Inner Loop, and shift the global meta-parameter theta towards it.

    Returns the final meta-learned parameter theta*.
    """
    agent_kwargs = agent_kwargs or {}
    rng = random.Random(seed)

    global_agent = SACAgent(**agent_kwargs)
    theta = global_agent.get_params()

    for k in range(1, num_outer_iterations + 1):
        scenario = rng.choice(scenarios)
        theta_k = inner_loop(
            theta, scenario, num_inner_updates, agent_kwargs=agent_kwargs, seed=rng.randint(0, 2**31)
        )
        theta = _interpolate_params(theta, theta_k, meta_lr)

        if reward_log is not None or (progress_every and k % progress_every == 0):
            eval_agent = SACAgent(**agent_kwargs)
            eval_agent.load_params(theta)
            avg_reward = _evaluate(eval_agent, scenario, seed=rng.randint(0, 2**31))
            if reward_log is not None:
                reward_log.append(avg_reward)
            if progress_every and k % progress_every == 0:
                print(f"[Outer Loop] iter {k}/{num_outer_iterations} avg_reward={avg_reward:.3f}")

    return theta


def _evaluate(agent, scenario, num_steps: int = 50, seed=None):
    env = MECOffloadEnv(scenario, seed=seed)
    state = env.reset()
    total = 0.0
    for _ in range(num_steps):
        action = agent.select_action(state, greedy=True)
        state, reward, _, _ = env.step(action)
        total += reward
    return total / num_steps
