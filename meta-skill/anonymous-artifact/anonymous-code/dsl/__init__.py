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

# 注意: dsl/macros_library.py 是 self-evolving vision 的 architecture sketch
# **未连接主流程**——故意不在此 import / __all__ 中导出。论文里只在
# Figure 1 / Discussion 提一嘴，不当作已实现 feature。

__all__ = [
    # 类型
    "Distribution", "Factor", "HypothesisSpace", "Evidence",
    # Core Ops
    "condition", "multiply", "marginalize", "normalize",
    "enumerate_hypotheses", "expectation", "argmax",
    # Family Macros
    "softmax_pref_likelihood", "beta_bernoulli_update", "ve_query",
]
