"""
DSL 类型定义

核心类型：
- Distribution: 离散概率分布（值 → 概率）
- Factor: 多变量概率因子（变量名列表 + 赋值元组 → 概率）
- HypothesisSpace: 假设空间定义（用于枚举）
- Evidence: 观测证据
"""

from __future__ import annotations

import numpy as np
from dataclasses import dataclass, field
from typing import Any, Dict, List, Tuple, Sequence, Hashable


# ─── Distribution ───────────────────────────────────────────────────────────

@dataclass
class Distribution:
    """离散概率分布

    存储方式: 两个对齐的数组
      - support: 支撑集（值列表，任意可哈希类型）
      - probs:   对应概率（numpy array, 非负, 和为 1）

    示例:
      Distribution(support=[(1,0), (0,1)], probs=np.array([0.7, 0.3]))
    """
    support: List[Any]
    probs: np.ndarray

    def __post_init__(self):
        self.probs = np.asarray(self.probs, dtype=np.float64)
        if len(self.support) != len(self.probs):
            raise ValueError(
                f"support 长度 ({len(self.support)}) != probs 长度 ({len(self.probs)})"
            )

    def prob_of(self, value: Any) -> float:
        """查询单个值的概率"""
        for i, v in enumerate(self.support):
            if v == value:
                return float(self.probs[i])
        return 0.0

    def map_value(self) -> Any:
        """返回 MAP（最大后验概率）值"""
        return self.support[int(np.argmax(self.probs))]

    def entropy(self) -> float:
        """信息熵"""
        p = self.probs[self.probs > 0]
        return float(-np.sum(p * np.log2(p)))

    def __len__(self) -> int:
        return len(self.support)

    def __repr__(self) -> str:
        n = len(self.support)
        if n <= 5:
            items = ", ".join(f"{v}: {p:.4f}" for v, p in zip(self.support, self.probs))
        else:
            items = ", ".join(f"{v}: {p:.4f}" for v, p in zip(self.support[:3], self.probs[:3]))
            items += f", ... ({n} total)"
        return f"Distribution({{{items}}})"


# ─── Factor ─────────────────────────────────────────────────────────────────

@dataclass
class Factor:
    """多变量概率因子

    存储方式:
      - variables: 变量名有序列表，如 ["X", "Y"]
      - table:     赋值元组 → 概率值，如 {(True, False): 0.3, ...}

    变量的值域从 table 的 key 中自动推断。

    示例:
      Factor(
          variables=["Rain", "Sprinkler"],
          table={(True, True): 0.01, (True, False): 0.99, ...}
      )
    """
    variables: List[str]
    table: Dict[tuple, float]

    def __post_init__(self):
        # 验证 table key 的维度
        for key in self.table:
            if len(key) != len(self.variables):
                raise ValueError(
                    f"table key {key} 维度 ({len(key)}) != variables 数量 ({len(self.variables)})"
                )

    def get_domains(self) -> Dict[str, set]:
        """推断每个变量的值域"""
        domains = {v: set() for v in self.variables}
        for key in self.table:
            for i, v in enumerate(self.variables):
                domains[v].add(key[i])
        return domains

    def __repr__(self) -> str:
        n = len(self.table)
        return f"Factor(vars={self.variables}, entries={n})"


# ─── HypothesisSpace ────────────────────────────────────────────────────────

@dataclass
class HypothesisSpace:
    """假设空间定义（用于枚举）

    支持多种构造：
    1. 笛卡尔积: dimensions=[[-1,0,1], [-1,0,1]] → 所有组合
    2. 显式列表: explicit_list=[(0,1), (1,0), ...]
    """
    dimensions: List[List[Any]] = field(default_factory=list)
    explicit_list: List[Any] = field(default_factory=list)

    def size(self) -> int:
        """假设空间大小"""
        if self.explicit_list:
            return len(self.explicit_list)
        result = 1
        for d in self.dimensions:
            result *= len(d)
        return result


# ─── Evidence ───────────────────────────────────────────────────────────────

@dataclass
class Evidence:
    """观测证据

    通用容器，不同推断族用不同字段：
    - assignments: 变量赋值 {var_name: value}（BN 推断用）
    - choice_idx: 选择的索引（偏好学习用）
    - option_features: 各选项特征矩阵（偏好学习用）
    - arm: 选择的臂编号（bandit 用）
    - reward: 观测到的奖励（bandit 用）
    """
    assignments: Dict[str, Any] = field(default_factory=dict)
    choice_idx: int = -1
    option_features: List[List[float]] = field(default_factory=list)
    arm: int = -1
    reward: float = 0.0
