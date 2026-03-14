"""
概率推理 DSL — 两层架构

Layer 1: Core Typed Ops（底层算子）
Layer 2: Family Macros（推断族宏）

所有 gold reference solver 和 auto-induced solver 只允许调用本模块导出的接口。
"""

from .types import (
    Distribution,
    Factor,
    HypothesisSpace,
    Evidence,
)

from .core_ops import (
    condition,
    multiply,
    marginalize,
    normalize,
    enumerate_hypotheses,
    expectation,
    argmax,
)

from .family_macros import (
    softmax_pref_likelihood,
    beta_bernoulli_update,
    ve_query,
)

__all__ = [
    # 类型
    "Distribution", "Factor", "HypothesisSpace", "Evidence",
    # Core Ops
    "condition", "multiply", "marginalize", "normalize",
    "enumerate_hypotheses", "expectation", "argmax",
    # Family Macros
    "softmax_pref_likelihood", "beta_bernoulli_update", "ve_query",
]
