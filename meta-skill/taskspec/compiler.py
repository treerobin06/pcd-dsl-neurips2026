"""
TaskSpec Compiler — 从 TaskSpec 确定性地编译出 Solver

编译器是纯确定性的：相同的 TaskSpec 总是产生相同的 solver。
LLM 负责归纳 TaskSpec，编译器负责代码生成。

支持的 inference family:
- hypothesis_enumeration → PreferenceSolver
- conjugate_update → BanditSolver
- variable_elimination → BNReferenceSolver
"""

from typing import Union

from .schema import TaskSpec
from solvers.preference_solver import PreferenceSolver
from solvers.bandit_solver import BanditSolver
from solvers.bn_solver import BNReferenceSolver


# Compiler 输出的 solver 类型
SolverType = Union[PreferenceSolver, BanditSolver, BNReferenceSolver]


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
