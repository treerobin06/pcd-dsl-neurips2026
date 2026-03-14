"""
Gold Reference Solver: 偏好学习（Flight/Hotel）

Inference Family: Hypothesis Enumeration
Macro: softmax_pref_likelihood

只调用 DSL 原语，功能等价于 BayesianSidecar。
"""

import numpy as np
from typing import List, Tuple, Optional

from dsl import (
    Distribution,
    HypothesisSpace,
    enumerate_hypotheses,
    expectation,
    argmax,
)
from dsl.family_macros import softmax_pref_likelihood


class PreferenceSolver:
    """偏好学习 solver — 基于 DSL 原语"""

    def __init__(
        self,
        feature_dim: int = 4,
        preference_values: Optional[List[float]] = None,
        temperature: float = 1.0,
    ):
        if preference_values is None:
            preference_values = [-1, 0, 1]

        self.feature_dim = feature_dim
        self.preference_values = preference_values
        self.temperature = temperature

        # 用 DSL 枚举假设空间
        space = HypothesisSpace(
            dimensions=[preference_values] * feature_dim
        )
        hypotheses = enumerate_hypotheses(space)

        # 初始化均匀先验
        n = len(hypotheses)
        self.posterior = Distribution(
            support=hypotheses,
            probs=np.ones(n) / n,
        )

    def update(self, choice_idx: int, options: List[List[float]]):
        """根据用户选择更新后验"""
        self.posterior = softmax_pref_likelihood(
            prior=self.posterior,
            choice_idx=choice_idx,
            option_features=options,
            temperature=self.temperature,
        )

    def recommend(self, options: List[List[float]]) -> int:
        """推荐期望效用最高的选项"""
        eus = self.get_expected_utilities(options)
        return int(argmax(eus))

    def get_expected_utilities(self, options: List[List[float]]) -> dict:
        """计算每个选项的期望效用"""
        opts = np.array(options, dtype=np.float64)
        result = {}
        for i, opt in enumerate(options):
            # E[utility(option_i)] = Σ P(h) * (h · opt_i)
            eu = expectation(
                self.posterior,
                lambda h, o=np.array(opt): float(np.dot(h, o))
            )
            result[i] = eu
        return result

    def get_map_preference(self) -> Tuple:
        """MAP 偏好"""
        return self.posterior.map_value()

    def get_confidence(self) -> float:
        """MAP 置信度"""
        return float(np.max(self.posterior.probs))

    def get_weighted_preference(self) -> List[float]:
        """后验加权偏好向量"""
        hyps = np.array(self.posterior.support, dtype=np.float64)
        weighted = self.posterior.probs @ hyps
        return weighted.tolist()

    def reset(self):
        """重置"""
        n = len(self.posterior)
        self.posterior = Distribution(
            support=list(self.posterior.support),
            probs=np.ones(n) / n,
        )
