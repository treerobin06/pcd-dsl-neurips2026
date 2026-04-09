"""
Gold Reference Solver: 多臂赌博机（TextBandit）

Inference Family: Conjugate Update
Macro: beta_bernoulli_update

只调用 DSL 原语，功能等价于 BanditSidecar。
"""

import numpy as np
from typing import List

from dsl import argmax
from dsl.family_macros import (
    beta_bernoulli_update,
    beta_posterior_mean,
    beta_recommend,
    beta_thompson_sample,
)


class BanditSolver:
    """多臂赌博机 solver — 基于 DSL 原语"""

    def __init__(self, n_arms: int, prior_alpha: float = 1.0, prior_beta: float = 1.0):
        self.n_arms = n_arms
        self.alpha = np.full(n_arms, prior_alpha)
        self.beta_params = np.full(n_arms, prior_beta)

    def update(self, arm: int, reward: int):
        """观测后更新后验"""
        self.alpha, self.beta_params = beta_bernoulli_update(
            self.alpha, self.beta_params, arm, reward
        )

    def recommend(self) -> int:
        """推荐后验均值最高的臂"""
        return beta_recommend(self.alpha, self.beta_params)

    def thompson_sample(self) -> int:
        """Thompson Sampling"""
        return beta_thompson_sample(self.alpha, self.beta_params)

    def get_posterior_means(self) -> np.ndarray:
        """所有臂的后验均值"""
        return beta_posterior_mean(self.alpha, self.beta_params)

    def reset(self):
        """重置"""
        self.alpha = np.ones(self.n_arms)
        self.beta_params = np.ones(self.n_arms)
