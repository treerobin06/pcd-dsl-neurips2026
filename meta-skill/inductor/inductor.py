"""
Solver Inductor — LLM 分析样本，推断 TaskSpec

输入: DSL 文档 + TaskSpec schema + 几条样本
输出: TaskSpec JSON

Inductor 只负责填写 TaskSpec 的字段，不允许输出任意代码。
"""

import os
import json
import re
from typing import Dict, List, Optional
from openai import OpenAI

from taskspec.schema import TaskSpec


# 加载 prompt 模板
_PROMPT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "prompts")


def _load_prompt_template() -> str:
    with open(os.path.join(_PROMPT_DIR, "induction_prompt.md"), encoding="utf-8") as f:
        return f.read()


# C5 修复 (2026-04-24): 防止 Inductor 看到 ground-truth 答案字段。
# 4-agent audit + Codex review 发现原代码 json.dumps(s) 把
# reward_fn/answers/correct_*/user_idx 喂给 LLM，导致 LOO/E2E/reliability 虚高。
_ANSWER_KEYS = {
    "reward_fn", "answers", "gold_answer", "gold_posterior", "gold_user_choice",
    "correct_answer", "correct_diagnosis", "correct_state", "correct_posterior",
    "correct_arm", "correct_user_choice", "user_idx", "user_choice",
    "true_arm", "true_label", "label", "gold",
}


def _scrub_sample(obj):
    """递归移除答案字段，让 Inductor 看不到 ground truth。

    应用于 list 元素和 dict value（rounds 是 list of dict 含 user_idx）。
    """
    if isinstance(obj, dict):
        return {k: _scrub_sample(v) for k, v in obj.items() if k not in _ANSWER_KEYS}
    if isinstance(obj, list):
        return [_scrub_sample(item) for item in obj]
    return obj


def _format_samples(samples: List[Dict], max_samples: int = 5) -> str:
    """格式化样本数据供 LLM 分析（已 scrub 答案字段，C5 修复）"""
    selected = samples[:max_samples]
    parts = []
    for i, s in enumerate(selected):
        parts.append(f"### Sample {i+1}")
        text = json.dumps(_scrub_sample(s), indent=2, ensure_ascii=False)
        if len(text) > 3000:
            text = text[:3000] + "\n... (truncated)"
        parts.append(text)
    return "\n\n".join(parts)


def induce_taskspec(
    samples: List[Dict],
    model_id: str = "openai/gpt-4o-mini",
    max_samples: int = 5,
    temperature: float = 0.0,
) -> Optional[TaskSpec]:
    """从样本数据推断 TaskSpec

    Args:
        samples: 样本数据列表
        model_id: 使用的 LLM 模型
        max_samples: 最多使用几个样本
        temperature: LLM 温度

    Returns:
        推断出的 TaskSpec，解析失败返回 None
    """
    api_key = os.environ.get("OPENROUTER_API_KEY")
    if not api_key:
        raise RuntimeError("OPENROUTER_API_KEY 未设置")

    client = OpenAI(
        api_key=api_key,
        base_url="https://openrouter.ai/api/v1",
    )

    # 构造 prompt
    template = _load_prompt_template()
    samples_text = _format_samples(samples, max_samples)
    prompt = template.replace("{samples}", samples_text)

    # 调用 LLM
    response = client.chat.completions.create(
        model=model_id,
        messages=[{"role": "user", "content": prompt}],
        max_tokens=2048,
        temperature=temperature,
    )

    text = response.choices[0].message.content.strip()
    return _parse_taskspec_response(text)


def _parse_taskspec_response(text: str) -> Optional[TaskSpec]:
    """从 LLM 输出中解析 TaskSpec JSON"""
    # 尝试提取 JSON 块
    # 模式 1: ```json ... ```
    m = re.search(r'```(?:json)?\s*\n?(.*?)\n?```', text, re.DOTALL)
    if m:
        json_str = m.group(1).strip()
    else:
        # 模式 2: 直接是 JSON
        json_str = text.strip()

    try:
        d = json.loads(json_str)
        return TaskSpec.from_dict(d)
    except (json.JSONDecodeError, KeyError, TypeError) as e:
        print(f"[Inductor] TaskSpec 解析失败: {e}")
        return None


def induce_with_refinement(
    samples: List[Dict],
    diagnostics: str = "",
    model_id: str = "openai/gpt-4o-mini",
    max_samples: int = 5,
    temperature: float = 0.0,
) -> Optional[TaskSpec]:
    """带诊断反馈的 TaskSpec 推断（self-refine 循环用）

    Args:
        samples: 样本数据
        diagnostics: 上一轮验证的诊断信息（空=首次推断）
        model_id: LLM 模型
        max_samples: 最多样本数
        temperature: 温度

    Returns:
        推断的 TaskSpec
    """
    api_key = os.environ.get("OPENROUTER_API_KEY")
    if not api_key:
        raise RuntimeError("OPENROUTER_API_KEY 未设置")

    client = OpenAI(
        api_key=api_key,
        base_url="https://openrouter.ai/api/v1",
    )

    template = _load_prompt_template()
    samples_text = _format_samples(samples, max_samples)
    prompt = template.replace("{samples}", samples_text)

    if diagnostics:
        prompt += (
            f"\n\n## Previous Attempt Diagnostics\n\n"
            f"Your previous TaskSpec failed verification. Here are the diagnostics:\n\n"
            f"{diagnostics}\n\n"
            f"Please fix the TaskSpec based on these diagnostics. Output ONLY the corrected JSON."
        )

    response = client.chat.completions.create(
        model=model_id,
        messages=[{"role": "user", "content": prompt}],
        max_tokens=2048,
        temperature=temperature,
    )

    text = response.choices[0].message.content.strip()
    return _parse_taskspec_response(text)
