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
    model_id: str = "openai/gpt-4o-mini",
    max_rounds: int = 3,
    max_samples: int = 5,
    verify_samples: Optional[List[Dict]] = None,
) -> Tuple[Optional[TaskSpec], VerificationResult, int]:
    """运行 Inductor + Verifier self-refine 循环（2-Gate Verifier）

    2026-04-28 framing pivot: gold_solver 参数已移除（Gate 3 删 → 不需要独立 gold）。

    Args:
        samples: 样本数据，给 Inductor 用
        model_id: LLM 模型
        max_rounds: 最大 refine 轮数
        max_samples: Inductor 使用的最大样本数
        verify_samples: (C6 修复, 2026-04-24) 用于 Verifier 的独立样本集；
            None 时回退到 samples 本身（向后兼容）。LOO / held-out 评估
            必须显式传与 samples 不重叠的子集，避免 train/test 泄漏。

    Returns:
        (TaskSpec, VerificationResult, rounds_used) — TaskSpec 可能为 None
    """
    diagnostics = ""
    verify_set = verify_samples if verify_samples is not None else samples

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

        # 验证（C6 修复：用独立 verify_set 而非 samples，防 train/test 泄漏）
        result = verify_taskspec(spec, verify_set)
        print(f"  [Verifier] {result.diagnostics()}")

        if result.passed:
            print(f"  [OK] 验证通过 (第 {round_idx + 1} 轮)")
            return spec, result, round_idx + 1

        # 准备诊断反馈
        diagnostics = result.diagnostics()

    # 所有轮次用完
    print(f"  [FAIL] {max_rounds} 轮后仍未通过验证")
    return spec, result, max_rounds
