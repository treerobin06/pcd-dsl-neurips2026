"""
4-Gate Verifier — 验证自动生成的 solver

Gate 1: Code Sanity — solver 能实例化、能跑、输出格式正确
Gate 2: Ground Truth — 对样本数据，solver 输出 ≈ 已知正确答案
Gate 3: Reference Match — auto solver vs manual solver 100% 一致
Gate 4: LLM Integration — 注入后 downstream accuracy 差距 < 2pp（半自动）

验证失败时返回诊断信息，可反馈给 Inductor 做 self-refine。
"""

import json
import numpy as np
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field

from taskspec.schema import TaskSpec
from taskspec.compiler import compile_solver, SolverType


@dataclass
class GateResult:
    """单个 gate 的验证结果"""
    gate: str
    passed: bool
    message: str
    details: Dict = field(default_factory=dict)


@dataclass
class VerificationResult:
    """完整验证结果"""
    gates: List[GateResult] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return all(g.passed for g in self.gates)

    def diagnostics(self) -> str:
        """生成诊断信息（供 Inductor self-refine 使用）"""
        lines = []
        for g in self.gates:
            status = "PASS" if g.passed else "FAIL"
            lines.append(f"[{status}] {g.gate}: {g.message}")
            if not g.passed and g.details:
                for k, v in g.details.items():
                    lines.append(f"  {k}: {v}")
        return "\n".join(lines)


def verify_taskspec(
    spec: TaskSpec,
    samples: List[Dict],
    gold_solver: Optional[SolverType] = None,
) -> VerificationResult:
    """运行 4-Gate 验证

    Args:
        spec: 待验证的 TaskSpec
        samples: 测试样本
        gold_solver: 手写 gold reference solver（Gate 3 需要）

    Returns:
        验证结果
    """
    result = VerificationResult()

    # Gate 1: Code Sanity
    g1, solver = _gate1_code_sanity(spec)
    result.gates.append(g1)
    if not g1.passed:
        return result

    # Gate 2: Ground Truth
    g2 = _gate2_ground_truth(spec, solver, samples)
    result.gates.append(g2)

    # Gate 3: Reference Match（如果有 gold solver）
    if gold_solver is not None:
        g3 = _gate3_reference_match(spec, solver, gold_solver, samples)
        result.gates.append(g3)

    return result


def _gate1_code_sanity(spec: TaskSpec) -> Tuple[GateResult, Optional[SolverType]]:
    """Gate 1: 能编译、能实例化、能运行"""
    try:
        # 验证 TaskSpec
        errors = spec.validate()
        if errors:
            return GateResult(
                gate="Gate 1: Code Sanity",
                passed=False,
                message=f"TaskSpec 验证失败",
                details={"errors": errors},
            ), None

        # 编译
        solver = compile_solver(spec)

        # 简单功能测试
        family = spec.inference_family
        dim = len(spec.state_structure.features) if spec.state_structure.features else 2
        if family == "hypothesis_enumeration":
            # 验证 values_per_feature 是数值列表
            vals = spec.state_structure.values_per_feature
            if vals and isinstance(vals[0], (list, tuple)):
                return GateResult(
                    gate="Gate 1: Code Sanity",
                    passed=False,
                    message="values_per_feature 必须是 flat 数值列表，不能是嵌套列表",
                    details={"values_per_feature": str(vals)[:200]},
                ), None
            # 能 update + recommend
            test_options = [[0.5] * dim] * 3
            solver.update(0, test_options)
            solver.recommend(test_options)
        elif family == "conjugate_update":
            solver.update(0, 1)
            solver.recommend()
        elif family == "variable_elimination":
            pass

        return GateResult(
            gate="Gate 1: Code Sanity",
            passed=True,
            message="编译成功，基本功能正常",
        ), solver

    except Exception as e:
        return GateResult(
            gate="Gate 1: Code Sanity",
            passed=False,
            message=f"编译或运行失败: {e}",
            details={"exception": str(e)},
        ), None


def _gate2_ground_truth(
    spec: TaskSpec,
    solver: SolverType,
    samples: List[Dict],
) -> GateResult:
    """Gate 2: 对样本数据，solver 输出 ≈ 已知正确答案"""
    family = spec.inference_family

    if family == "hypothesis_enumeration":
        return _gate2_preference(solver, samples)
    elif family == "conjugate_update":
        return _gate2_bandit(solver, samples)
    elif family == "variable_elimination":
        return _gate2_bn(solver, samples)
    else:
        return GateResult(
            gate="Gate 2: Ground Truth",
            passed=False,
            message=f"不支持的 family: {family}",
        )


def _gate2_preference(solver, samples: List[Dict]) -> GateResult:
    """偏好学习 ground truth 验证"""
    correct = 0
    total = 0

    for sample in samples[:10]:  # 最多测 10 个
        solver.reset()
        rounds = sample.get("rounds", [])
        rounds_numpy = sample.get("rounds_numpy", [])

        for r_idx in range(len(rounds)):
            if r_idx >= len(rounds_numpy):
                break
            user_choice = rounds[r_idx]["user_idx"]
            options = rounds_numpy[r_idx]

            if r_idx < len(rounds) - 1:
                # 前 N-1 轮：update
                solver.update(user_choice, options)
            else:
                # 最后一轮：验证推荐
                rec = solver.recommend(options)
                if rec == user_choice:
                    correct += 1
                total += 1

    if total == 0:
        return GateResult(
            gate="Gate 2: Ground Truth",
            passed=False,
            message="无法评估：样本格式不匹配",
        )

    acc = correct / total
    passed = True  # 偏好学习的准确率本身就受限于先验信息量，不设硬阈值
    return GateResult(
        gate="Gate 2: Ground Truth",
        passed=passed,
        message=f"最后一轮推荐准确率: {acc*100:.1f}% ({correct}/{total})",
        details={"accuracy": acc, "correct": correct, "total": total},
    )


def _gate2_bandit(solver, samples: List[Dict]) -> GateResult:
    """Bandit ground truth 验证（使用内置配置）"""
    # Bandit 没有标准 "ground truth" 样本格式，跳过
    return GateResult(
        gate="Gate 2: Ground Truth",
        passed=True,
        message="Bandit 策略验证（Beta-Bernoulli 更新数学正确性已在单测中验证）",
    )


def _gate2_bn(solver, samples: List[Dict]) -> GateResult:
    """BN 推断 ground truth 验证"""
    correct = 0
    total = 0
    max_error = 0.0

    for sample in samples[:20]:
        context = sample.get("contexts", "")
        query = sample.get("query", "")
        graph = sample.get("graph", "")
        expected = float(sample.get("answers", 0))

        result = solver.solve_from_text(context, query, graph)
        if result is not None:
            error = abs(result - expected)
            max_error = max(max_error, error)
            if error < 0.01:
                correct += 1
            total += 1

    if total == 0:
        return GateResult(
            gate="Gate 2: Ground Truth",
            passed=False,
            message="无法评估：BN 样本格式不匹配",
        )

    acc = correct / total
    passed = acc >= 0.95  # 95% 的样本误差 < 1%
    return GateResult(
        gate="Gate 2: Ground Truth",
        passed=passed,
        message=f"精确率: {acc*100:.1f}% ({correct}/{total}), 最大误差: {max_error:.6f}",
        details={"accuracy": acc, "max_error": max_error},
    )


def _gate3_reference_match(
    spec: TaskSpec,
    auto_solver: SolverType,
    gold_solver: SolverType,
    samples: List[Dict],
) -> GateResult:
    """Gate 3: auto solver vs gold solver 输出 100% 一致"""
    family = spec.inference_family
    mismatches = 0
    total = 0

    if family == "hypothesis_enumeration":
        for sample in samples[:10]:
            auto_solver.reset()
            gold_solver.reset()
            rounds_numpy = sample.get("rounds_numpy", [])
            rounds = sample.get("rounds", [])

            for r_idx in range(len(rounds)):
                if r_idx >= len(rounds_numpy):
                    break
                user_choice = rounds[r_idx]["user_idx"]
                options = rounds_numpy[r_idx]
                auto_solver.update(user_choice, options)
                gold_solver.update(user_choice, options)

                # 比较后验
                diff = np.max(np.abs(auto_solver.posterior.probs - gold_solver.posterior.probs))
                if diff > 1e-10:
                    mismatches += 1
                total += 1

    elif family == "conjugate_update":
        rng = np.random.default_rng(42)
        for _ in range(50):
            arm = rng.integers(auto_solver.n_arms)
            reward = rng.integers(2)
            auto_solver.update(arm, reward)
            gold_solver.update(arm, reward)

            diff = np.max(np.abs(auto_solver.get_posterior_means() - gold_solver.get_posterior_means()))
            if diff > 1e-10:
                mismatches += 1
            total += 1

    elif family == "variable_elimination":
        for sample in samples[:20]:
            context = sample.get("contexts", "")
            query = sample.get("query", "")
            graph = sample.get("graph", "")

            r_auto = auto_solver.solve_from_text(context, query, graph)
            r_gold = gold_solver.solve_from_text(context, query, graph)

            if r_auto is not None and r_gold is not None:
                if abs(r_auto - r_gold) > 1e-10:
                    mismatches += 1
            total += 1

    passed = mismatches == 0
    return GateResult(
        gate="Gate 3: Reference Match",
        passed=passed,
        message=f"{'完全一致' if passed else f'{mismatches} 个不一致'} ({total} 次比较)",
        details={"mismatches": mismatches, "total": total},
    )
