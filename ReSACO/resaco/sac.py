"""Soft Actor-Critic agent implementing SAC-Update (Algorithm 3).

Discrete-action SAC: since the offloading action space is finite, the
expectations in the soft Bellman target (Eq. 10) and the actor objective
(Eq. 12) are computed exactly as probability-weighted sums over the twin
critics' Q-value vectors, instead of Monte-Carlo sampling.
"""

import copy

import torch
import torch.nn.functional as F

from . import config
from .networks import Actor, Critic
from .normalize import normalize_state
from .replay_buffer import ReplayBuffer


class SACAgent:
    def __init__(self, state_dim=config.STATE_DIM, action_dim=config.ACTION_DIM,
                 hidden_sizes=config.HIDDEN_SIZES, device="cpu"):
        self.device = torch.device(device)
        self.state_dim = state_dim
        self.action_dim = action_dim

        self.actor = Actor(state_dim, action_dim, hidden_sizes).to(self.device)
        self.critic1 = Critic(state_dim, action_dim, hidden_sizes).to(self.device)
        self.critic2 = Critic(state_dim, action_dim, hidden_sizes).to(self.device)
        self.target_critic1 = copy.deepcopy(self.critic1)
        self.target_critic2 = copy.deepcopy(self.critic2)

        self.actor_optim = torch.optim.Adam(self.actor.parameters(), lr=config.ACTOR_LR)
        self.critic_optim = torch.optim.Adam(
            list(self.critic1.parameters()) + list(self.critic2.parameters()),
            lr=config.CRITIC_LR,
        )

        self.gamma = config.DISCOUNT_GAMMA
        self.tau = config.ENTROPY_TAU  # entropy temperature (paper's tau)
        self.rho = config.TARGET_SOFT_UPDATE_RHO

        self.replay_buffer = ReplayBuffer(config.REPLAY_BUFFER_SIZE)

    # ------------------------------------------------------------------
    # Parameter (de)serialization -- used by the Reptile Outer Loop to copy
    # theta -> theta_k and to apply theta <- theta + alpha*(theta_k - theta)
    # ------------------------------------------------------------------
    def get_params(self):
        return {
            "actor": copy.deepcopy(self.actor.state_dict()),
            "critic1": copy.deepcopy(self.critic1.state_dict()),
            "critic2": copy.deepcopy(self.critic2.state_dict()),
        }

    def load_params(self, params):
        self.actor.load_state_dict(params["actor"])
        self.critic1.load_state_dict(params["critic1"])
        self.critic2.load_state_dict(params["critic2"])
        self.target_critic1.load_state_dict(params["critic1"])
        self.target_critic2.load_state_dict(params["critic2"])

    # ------------------------------------------------------------------
    def select_action(self, state, greedy: bool = False) -> int:
        state_t = torch.as_tensor(normalize_state(state), dtype=torch.float32, device=self.device).unsqueeze(0)
        with torch.no_grad():
            if greedy:
                action = self.actor.act_greedy(state_t)
            else:
                action, _, _ = self.actor.sample(state_t)
        return int(action.item())

    # ------------------------------------------------------------------
    def update(self, batch_size: int = config.BATCH_SIZE):
        """One SAC-Update step (Algorithm 3, lines 8-12): sample a
        mini-batch, update critic, update actor, soft-update targets."""
        if len(self.replay_buffer) < batch_size:
            return None

        state, action, reward, next_state, done = self.replay_buffer.sample(batch_size)
        state = torch.as_tensor(normalize_state(state), dtype=torch.float32, device=self.device)
        action = torch.as_tensor(action, dtype=torch.long, device=self.device)
        reward = torch.as_tensor(reward, dtype=torch.float32, device=self.device)
        next_state = torch.as_tensor(normalize_state(next_state), dtype=torch.float32, device=self.device)
        done = torch.as_tensor(done, dtype=torch.float32, device=self.device)

        critic_loss = self._update_critic(state, action, reward, next_state, done)
        actor_loss = self._update_actor(state)
        self._soft_update_targets()

        return {"critic_loss": critic_loss, "actor_loss": actor_loss}

    def _update_critic(self, state, action, reward, next_state, done):
        with torch.no_grad():
            next_probs = self.actor.action_probs(next_state)
            next_log_probs = torch.log(next_probs + 1e-8)
            q1_next = self.target_critic1(next_state)
            q2_next = self.target_critic2(next_state)
            q_next = torch.min(q1_next, q2_next)
            # E_{a' ~ pi}[Q(s',a') - tau * log pi(a'|s')], exact discrete expectation
            v_next = (next_probs * (q_next - self.tau * next_log_probs)).sum(dim=-1)
            target = reward + self.gamma * (1.0 - done) * v_next  # Eq. (10)

        q1 = self.critic1(state).gather(1, action.unsqueeze(1)).squeeze(1)
        q2 = self.critic2(state).gather(1, action.unsqueeze(1)).squeeze(1)
        loss = F.mse_loss(q1, target) + F.mse_loss(q2, target)  # Eq. (11)

        self.critic_optim.zero_grad()
        loss.backward()
        self.critic_optim.step()
        return float(loss.item())

    def _update_actor(self, state):
        probs = self.actor.action_probs(state)
        log_probs = torch.log(probs + 1e-8)
        with torch.no_grad():
            q1 = self.critic1(state)
            q2 = self.critic2(state)
            q = torch.min(q1, q2)
        # maximize E_{a~pi}[Q(s,a) - tau*log pi(a|s)]  ==  minimize -(...)  (Eq. 12)
        actor_loss = (probs * (self.tau * log_probs - q)).sum(dim=-1).mean()

        self.actor_optim.zero_grad()
        actor_loss.backward()
        self.actor_optim.step()
        return float(actor_loss.item())

    def _soft_update_targets(self):
        with torch.no_grad():
            for target_param, param in zip(self.target_critic1.parameters(), self.critic1.parameters()):
                target_param.mul_(self.rho).add_(param, alpha=1 - self.rho)  # Eq. (13)
            for target_param, param in zip(self.target_critic2.parameters(), self.critic2.parameters()):
                target_param.mul_(self.rho).add_(param, alpha=1 - self.rho)

    # ------------------------------------------------------------------
    def sac_update_loop(self, env, num_transitions: int, greedy_action: bool = False,
                         batch_size: int = config.BATCH_SIZE):
        """Runs the full SAC-Update transition-collection loop (Algorithm 3):
        interact with `env` for `num_transitions` steps, storing transitions
        and performing one gradient update per step.

        `num_transitions` is meant to be "N inner SAC-Update iterations"
        (Algorithm 2's N) -- i.e. N real gradient steps. update() is a no-op
        until the replay buffer holds at least `batch_size` transitions, so
        a fresh agent (buffer starting at 0, as the Reptile Inner Loop
        creates every outer iteration) needs to collect `batch_size`
        transitions before the very first update can fire. Without this
        warm-up, a small N (e.g. N=50 < batch_size=64) would mean update()
        never fires at all during the whole call -- theta_k would come back
        byte-for-byte identical to theta, silently turning meta-training
        into a no-op. So the warm-up transitions here are collected but not
        counted against N, guaranteeing all N counted steps below actually
        perform a gradient update.
        """
        state = env.reset()
        while len(self.replay_buffer) < batch_size:
            action = self.select_action(state, greedy=greedy_action)
            next_state, reward, done, info = env.step(action)
            self.replay_buffer.push(state, action, reward, next_state, float(done))
            state = next_state

        stats = []
        for _ in range(num_transitions):
            action = self.select_action(state, greedy=greedy_action)
            next_state, reward, done, info = env.step(action)
            self.replay_buffer.push(state, action, reward, next_state, float(done))
            result = self.update(batch_size=batch_size)
            if result is not None:
                stats.append(result)
            state = next_state
        return stats
