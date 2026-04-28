"""
TaskSpec Compiler — 从 TaskSpec 确定性地编译出 Solver

编译器是纯确定性的：相同的 TaskSpec 总是产生相同的 solver。
LLM 负责归纳 TaskSpec，编译器负责代码生成。

支持的 inference family:
- hypothesis_enumeration → PreferenceSolver  (softmax_pref macro: 3 ops)
- conjugate_update → BanditSolver            (beta_bernoulli macro: 2 ops)
- variable_elimination → BNReferenceSolver   (ve_query macro: 4 ops)
- naive_bayes → NBSolver                     (no macro, 5 ops compose: C2 2026-04-28)
- hmm_forward → HMMSolver                    (no macro, 5 ops + iteration: C2 2026-04-28)
"""

from typing import Union

from .schema import TaskSpec
from solvers.preference_solver import PreferenceSolver
from solvers.bandit_solver import BanditSolver
from solvers.bn_solver import BNReferenceSolver
from solvers.nb_solver import NBSolver
from solvers.hmm_solver import HMMSolver


# Compiler 输出的 solver 类型
SolverType = Union[
    PreferenceSolver,
    BanditSolver,
    BNReferenceSolver,
    NBSolver,
    HMMSolver,
]


def compile_solver(spec: TaskSpec) -> SolverType:
    """从 TaskSpec 编译出 solver 实例

    Args:
        spec: 任务规范

    Returns:
        对应的 solver 实例

    Raises:
        ValueError: TaskSpec 验证失败或 inference_family 不支持
    """
    # 验证
    errors = spec.validate()
    if errors:
        raise ValueError(f"TaskSpec 验证失败: {'; '.join(errors)}")

    family = spec.inference_family

    if family == "hypothesis_enumeration":
        return _compile_preference(spec)
    elif family == "conjugate_update":
        return _compile_bandit(spec)
    elif family == "variable_elimination":
        return _compile_bn(spec)
    elif family == "naive_bayes":
        return _compile_nb(spec)
    elif family == "hmm_forward":
        return _compile_hmm(spec)
    else:
        raise ValueError(f"不支持的 inference_family: {family}")


def _compile_preference(spec: TaskSpec) -> PreferenceSolver:
    """编译偏好学习 solver"""
    return PreferenceSolver(
        feature_dim=len(spec.state_structure.features),
        preference_values=spec.state_structure.values_per_feature,
        temperature=spec.observation_model.temperature,
    )


def _compile_bandit(spec: TaskSpec) -> BanditSolver:
    """编译多臂赌博机 solver"""
    return BanditSolver(n_arms=spec.state_structure.n_arms)


def _compile_bn(spec: TaskSpec) -> BNReferenceSolver:
    """编译贝叶斯网络推断 solver

    C3 真重构 (2026-04-24): spec 内容真参与编译。原 `return BNReferenceSolver()`
    被 Codex CRITICAL 1 + 4-agent audit 标为身份危机—— "compile" 实为 routing。

    现在 spec.state_structure 的三个 BN 字段决定 solver 的实际配置:
    - bn_inference_method: ve / (future) junction_tree / sampling
    - bn_input_format: blind_text / factors_dict
    - bn_numerical_precision: float64 / (future) mpfr

    不同 spec 编译出不同 solver；不支持的配置 raise ValueError。
    """
    return BNReferenceSolver(
        inference_method=spec.state_structure.bn_inference_method,
        input_format=spec.state_structure.bn_input_format,
        numerical_precision=spec.state_structure.bn_numerical_precision,
    )


def _compile_nb(spec: TaskSpec) -> NBSolver:
    """编译 Naive Bayes solver（5 dsl ops compose, no macro）

    C2 真组合 (2026-04-28): NBSolver 用 condition + multiply + marginalize +
    normalize + argmax 实现 P(c|f) ∝ P(c) ∏_j P(f_j|c)。数学正确性 verified
    (max_err < 1e-9 vs 手算 gold)。LLM 只 emit spec, compiler 实例化 solver。
    """
    ss = spec.state_structure
    return NBSolver(
        classes=ss.nb_classes,
        feature_likelihoods=ss.nb_feature_likelihoods,
        prior=ss.nb_prior if ss.nb_prior else None,
    )


def _compile_hmm(spec: TaskSpec) -> HMMSolver:
    """编译 HMM forward filter solver（同 5 dsl ops + 迭代 over time）

    C2 真组合 (2026-04-28): HMMSolver 用同 5 ops 迭代实现 forward filter
    alpha_t(s) = P(o_t|s) × sum_{s'} alpha_{t-1}(s') × P(s|s')。数学正确性
    verified (max_err < 1e-9 vs numpy reference)。
    """
    ss = spec.state_structure
    return HMMSolver(
        states=ss.hmm_states,
        observations=ss.hmm_observations,
        initial=ss.hmm_initial,
        transition=ss.hmm_transition,
        emission=ss.hmm_emission,
    )
