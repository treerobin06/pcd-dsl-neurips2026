"""
Self-Refine 循环 — Inductor → Verifier → 诊断反馈 → 重新推断

最多 3 轮。如果 Gate 1-2 不通过，将诊断信息反馈给 Inductor 重试。
"""

from typing import Dict, List, Optional, Tuple

from taskspec.schema import TaskSpec
from taskspec.compiler import compile_solver, SolverType
from verifier.gates import verify_taskspec, VerificationResult
from inductor.inductor import induce_taskspec, induce_with_refinement


def induce_and_verify(
    samples: List[Dict],
    gold_solver: Optional[SolverType] = None,
    model_id: str = "openai/gpt-4o-mini",
    max_rounds: int = 3,
    max_samples: int = 5,
) -> Tuple[Optional[TaskSpec], VerificationResult, int]:
    """运行 Inductor + Verifier self-refine 循环

    Args:
        samples: 样本数据
        gold_solver: 手写 gold solver（Gate 3 需要）
        model_id: LLM 模型
        max_rounds: 最大 refine 轮数
        max_samples: Inductor 使用的最大样本数

    Returns:
        (TaskSpec, VerificationResult, rounds_used) — TaskSpec 可能为 None
    """
    diagnostics = ""

    for round_idx in range(max_rounds):
        print(f"  [Inductor] 第 {round_idx + 1}/{max_rounds} 轮")

        # 推断 TaskSpec
        if round_idx == 0:
            spec = induce_taskspec(
                samples, model_id=model_id,
                max_samples=max_samples,
            )
        else:
            spec = induce_with_refinement(
                samples, diagnostics=diagnostics,
                model_id=model_id, max_samples=max_samples,
            )

        if spec is None:
            print(f"  [Inductor] TaskSpec 解析失败")
            diagnostics = "TaskSpec JSON 解析失败，请确保输出有效的 JSON 格式。"
            continue

        print(f"  [Inductor] 推断: family={spec.inference_family}, task={spec.task_name}")

        # 验证
        result = verify_taskspec(spec, samples, gold_solver)
        print(f"  [Verifier] {result.diagnostics()}")

        if result.passed:
            print(f"  [OK] 验证通过 (第 {round_idx + 1} 轮)")
            return spec, result, round_idx + 1

        # 准备诊断反馈
        diagnostics = result.diagnostics()

    # 所有轮次用完
    print(f"  [FAIL] {max_rounds} 轮后仍未通过验证")
    return spec, result, max_rounds
