"""统一 raw artifact schema (C9 修复, 2026-04-24)

Codex review 发现全仓 `rg prompt_tokens / completion_tokens / total_cost`
零命中，导致论文 cost claim 无 raw 支撑。本模块强制所有新 run_*.py
通过 save_artifact() 保存结果，确保每个 raw JSON 含完整 _meta。

用法:
    from _artifact_schema import save_artifact, accumulate_usage

    # 在 LLM 调用累加 token usage
    total = {"prompt_tokens": 0, "completion_tokens": 0}
    for resp in responses:
        u = accumulate_usage(resp.usage)
        total["prompt_tokens"] += u["prompt_tokens"]
        total["completion_tokens"] += u["completion_tokens"]

    # 保存 artifact（_meta 强制存在，缺字段抛错）
    save_artifact(
        path="results/bnlearn_gpt4o_mini_xxxx.json",
        data={"compile_core_ops": {...}, "pcd": {...}},
        prompt_tokens=total["prompt_tokens"],
        completion_tokens=total["completion_tokens"],
        total_cost_usd=estimated_cost(model_id, total),
        model_id="openai/gpt-4o-mini",
    )

paper/scripts/generate_figure*.py 应从这些 _meta 字段读 cost / token
计数，禁止硬编码。
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from typing import Any, Dict, Optional


# 强制字段 — 不全则 save_artifact 抛 ValueError
REQUIRED_META_FIELDS = {
    "prompt_tokens",
    "completion_tokens",
    "total_cost_usd",
    "model_id",
    "git_commit",
    "timestamp_utc",
}


# OpenRouter 主要模型每百万 token 价格 (USD, 2026-04-24 估算)
# 真实价格随时间变化；只用于计算 total_cost_usd 的近似值。
# 调用方覆盖优先：调 save_artifact 时传精确 total_cost_usd 即可。
_MODEL_PRICING = {
    "openai/gpt-4o-mini": (0.15, 0.60),
    "openai/gpt-4o": (2.50, 10.00),
    "openai/gpt-5.4": (15.00, 60.00),
    "anthropic/claude-sonnet-4": (3.00, 15.00),
    "anthropic/claude-opus-4-6": (15.00, 75.00),
    "google/gemini-3.1-pro": (2.50, 10.00),
}


def estimate_cost_usd(model_id: str, prompt_tokens: int, completion_tokens: int) -> float:
    """基于 OpenRouter 估算价格估算 cost。模型未知时返回 0.0（调用方应用 -1 fallback）。"""
    pricing = _MODEL_PRICING.get(model_id)
    if pricing is None:
        return -1.0  # 未知模型，调用方决定如何处理
    in_per_m, out_per_m = pricing
    return (prompt_tokens / 1_000_000) * in_per_m + (completion_tokens / 1_000_000) * out_per_m


def accumulate_usage(usage_obj) -> Dict[str, int]:
    """从 OpenAI/OpenRouter usage 对象提取 token 计数（safe to None）"""
    if usage_obj is None:
        return {"prompt_tokens": 0, "completion_tokens": 0}
    return {
        "prompt_tokens": getattr(usage_obj, "prompt_tokens", 0) or 0,
        "completion_tokens": getattr(usage_obj, "completion_tokens", 0) or 0,
    }


def _git_commit() -> str:
    """当前 HEAD 的 SHA（短 8 位）；非 git 仓库或失败时返回 'unknown'"""
    import subprocess
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--short=8", "HEAD"],
            capture_output=True, text=True, timeout=2,
        )
        return result.stdout.strip() if result.returncode == 0 else "unknown"
    except Exception:
        return "unknown"


def save_artifact(
    path: str,
    data: Dict[str, Any],
    *,
    prompt_tokens: int,
    completion_tokens: int,
    total_cost_usd: Optional[float] = None,
    model_id: str,
    extra_meta: Optional[Dict[str, Any]] = None,
) -> None:
    """写 raw artifact，强制 _meta schema。

    Args:
        path: 输出 JSON 路径（绝对或相对 cwd）
        data: 实验结果主体（任意 dict）
        prompt_tokens: 累计 input tokens
        completion_tokens: 累计 output tokens
        total_cost_usd: 累计 USD 成本；None 时根据 model_id + tokens 估算
        model_id: e.g. "openai/gpt-4o-mini"
        extra_meta: 可选额外元数据（seed / dataset / config 等）

    Raises:
        ValueError: 必填 _meta 字段缺失
    """
    if total_cost_usd is None:
        total_cost_usd = estimate_cost_usd(model_id, prompt_tokens, completion_tokens)

    artifact = dict(data)
    if "_meta" in artifact:
        # 已有 _meta（不太可能），合并
        meta = dict(artifact["_meta"])
    else:
        meta = {}
    meta.update({
        "prompt_tokens": int(prompt_tokens),
        "completion_tokens": int(completion_tokens),
        "total_cost_usd": float(total_cost_usd),
        "model_id": str(model_id),
        "git_commit": _git_commit(),
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
    })
    if extra_meta:
        meta.update(extra_meta)
    artifact["_meta"] = meta

    # Schema 自检
    missing = REQUIRED_META_FIELDS - set(meta.keys())
    if missing:
        raise ValueError(
            f"Artifact _meta missing required fields: {missing}. "
            f"All run_*.py must use save_artifact() to enforce C9 discipline."
        )

    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, "w") as f:
        json.dump(artifact, f, indent=2, default=str)


def validate_artifact(path: str) -> Dict[str, Any]:
    """读取并校验 artifact 满足 C9 schema。

    Returns:
        {"ok": bool, "missing": [field], "meta": dict or None}
    """
    if not os.path.exists(path):
        return {"ok": False, "missing": ["<file not found>"], "meta": None}
    with open(path) as f:
        data = json.load(f)
    meta = data.get("_meta")
    if meta is None:
        return {"ok": False, "missing": ["_meta entire block"], "meta": None}
    missing = REQUIRED_META_FIELDS - set(meta.keys())
    return {"ok": not missing, "missing": sorted(missing), "meta": meta}


if __name__ == "__main__":
    # 自检冒烟（C9 fix）
    import tempfile
    import sys

    tmp = tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False)
    tmp.close()

    save_artifact(
        path=tmp.name,
        data={"accuracy": 0.74, "n_correct": 740, "n_total": 1000},
        prompt_tokens=12345,
        completion_tokens=6789,
        model_id="openai/gpt-4o-mini",
        extra_meta={"seed": 2026, "dataset": "smoke-test"},
    )

    result = validate_artifact(tmp.name)
    if result["ok"]:
        print(f"[C9 smoke] PASS: artifact valid, meta={result['meta']}")
    else:
        print(f"[C9 smoke] FAIL: missing {result['missing']}")
        sys.exit(1)

    # 反向: 故意构造缺字段的 artifact 应被 validate 拒
    with open(tmp.name, "w") as f:
        json.dump({"accuracy": 0.5, "_meta": {"prompt_tokens": 100}}, f)
    result = validate_artifact(tmp.name)
    expected_missing = {"completion_tokens", "total_cost_usd", "model_id", "git_commit", "timestamp_utc"}
    if not result["ok"] and set(result["missing"]) == expected_missing:
        print(f"[C9 reverse] PASS: validate catches missing fields {result['missing']}")
    else:
        print(f"[C9 reverse] FAIL: ok={result['ok']}, missing={result['missing']}")
        sys.exit(1)

    os.unlink(tmp.name)
    print("\nAll C9 smoke checks passed.")
