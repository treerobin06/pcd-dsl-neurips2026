#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
端到端链路实验: NL → LLM Parse → PreferenceSolver → 推荐

验证完整 pipeline 的准确率:
  自然语言航班描述 → LLM 提取原始特征 → 确定性归一化 → DSL Solver 推荐 → 对比 gold

用法:
  # 快速验证（10 样本）
  python run_e2e_experiment.py --n 10

  # 完整实验（200 样本）
  python run_e2e_experiment.py --n 200

  # 指定模型
  python run_e2e_experiment.py --n 200 --model openai/gpt-4o

  # 多模型
  python run_e2e_experiment.py --n 200 --model openai/gpt-4o-mini openai/gpt-4o openai/gpt-5.4
"""

import os
import sys
import json
import re
import asyncio
import argparse
import warnings
import numpy as np

warnings.filterwarnings("ignore", category=RuntimeWarning)
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from datetime import datetime

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

import httpx
from openai import AsyncOpenAI

# ==========================================
# 路径
# ==========================================
SCRIPT_DIR = Path(__file__).parent
PROJECT_ROOT = SCRIPT_DIR.parent.parent
PROMPT_DIR = SCRIPT_DIR / "prompts"
FLIGHT_DATA = PROJECT_ROOT / "data" / "eval" / "interaction" / "flight.jsonl"
RESULTS_DIR = SCRIPT_DIR / "results"

sys.path.insert(0, str(SCRIPT_DIR.parent))


# ==========================================
# OpenRouter 客户端
# ==========================================
def get_client() -> AsyncOpenAI:
    api_key = os.environ.get("OPENROUTER_API_KEY")
    if not api_key:
        raise RuntimeError("OPENROUTER_API_KEY 环境变量未设置")
    proxy = os.environ.get("HTTPS_PROXY", os.environ.get("HTTP_PROXY", "http://127.0.0.1:7897"))
    return AsyncOpenAI(
        base_url="https://openrouter.ai/api/v1",
        api_key=api_key,
        http_client=httpx.AsyncClient(proxy=proxy, timeout=120),
    )


# ==========================================
# LLM 调用
# ==========================================
async def call_llm(
    client: AsyncOpenAI,
    model: str,
    prompt: str,
    semaphore: asyncio.Semaphore,
    max_tokens: int = 4096,
) -> Tuple[bool, str]:
    async with semaphore:
        try:
            resp = await client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=max_tokens,
                temperature=0.0,
            )
            text = resp.choices[0].message.content or ""
            return True, text
        except Exception as e:
            return False, f"API error: {e}"


def extract_json(text: str) -> Optional[Dict]:
    """从 LLM 响应中提取 JSON"""
    m = re.search(r'```(?:json)?\s*\n(.*?)```', text, re.DOTALL)
    if m:
        try:
            return json.loads(m.group(1).strip())
        except json.JSONDecodeError:
            pass
    try:
        return json.loads(text.strip())
    except json.JSONDecodeError:
        pass
    m = re.search(r'\{.*\}', text, re.DOTALL)
    if m:
        try:
            return json.loads(m.group(0))
        except json.JSONDecodeError:
            pass
    return None


# ==========================================
# 归一化规则（从数据逆向工程确认）
# ==========================================
# departure_time: 06:00 AM (0.0) → 10:00 PM (1.0), 线性映射
# duration: 30 min (0.0) → 1200 min/20hr (1.0)
# stops: 0→0.0, 1→0.5, 2→1.0
# price: $100 (0.0) → $1000 (1.0)

def normalize_departure(hour_decimal: float) -> float:
    """24小时制小时数 → [0,1]。6.0→0.0, 22.0→1.0"""
    return max(0.0, min(1.0, (hour_decimal - 6.0) / 16.0))


def normalize_duration(minutes: float) -> float:
    """分钟数 → [0,1]。30→0.0, 1200→1.0"""
    return max(0.0, min(1.0, (minutes - 30.0) / 1170.0))


def normalize_stops(stops: int) -> float:
    """经停次数 → [0,1]"""
    return max(0.0, min(1.0, stops / 2.0))


def normalize_price(price: float) -> float:
    """美元价格 → [0,1]。100→0.0, 1000→1.0"""
    return max(0.0, min(1.0, (price - 100.0) / 900.0))


def normalize_features(raw: Dict) -> List[float]:
    """将 LLM 提取的原始特征归一化到 [0,1]"""
    dep = normalize_departure(float(raw.get("departure_hour", 0)))
    dur = normalize_duration(float(raw.get("duration_min", 0)))
    stp = normalize_stops(int(raw.get("stops", 0)))
    prc = normalize_price(float(raw.get("price", 0)))
    return [dep, dur, stp, prc]


def round_to_grid(val: float, grid_step: float = 0.1) -> float:
    """四舍五入到最近的网格点（数据集特征值是 0.1 步长）"""
    return round(round(val / grid_step) * grid_step, 4)


# ==========================================
# Prompt 构建
# ==========================================
def build_e2e_parse_prompt(sample: Dict) -> str:
    """构建端到端 NL Parse prompt"""
    template = (PROMPT_DIR / "e2e_parse_preference.md").read_text(encoding="utf-8")
    rounds = sample["rounds"]
    n_rounds = len(rounds)
    n_history = n_rounds - 1

    # 构建所有 round 的 NL 描述
    rounds_lines = []
    for r_idx in range(n_rounds):
        r = rounds[r_idx]
        is_history = r_idx < n_history
        if is_history:
            rounds_lines.append(f"Round {r_idx + 1} (user chose Flight {r['user_idx'] + 1}):")
        else:
            rounds_lines.append(f"Round {r_idx + 1} (current round, no choice yet):")
        for o_idx, opt_text in enumerate(r["options"]):
            marker = " <-- USER CHOSE THIS" if (is_history and o_idx == r["user_idx"]) else ""
            rounds_lines.append(f"  {opt_text}{marker}")
        rounds_lines.append("")

    return template.format(
        n_rounds=n_rounds,
        n_history=n_history,
        rounds_block="\n".join(rounds_lines),
    )


# ==========================================
# Gold pipeline 计算
# ==========================================
def compute_gold_pipeline(sample: Dict) -> Dict:
    """用 gold 特征跑 PreferenceSolver，返回 gold recommendation"""
    from solvers.preference_solver import PreferenceSolver

    rounds = sample["rounds"]
    rounds_numpy = sample["rounds_numpy"]
    pref_values = [-1.0, -0.5, 0.0, 0.5, 1.0]

    solver = PreferenceSolver(
        feature_dim=4,
        preference_values=pref_values,
        temperature=1.0,
    )

    # R1-R4 更新
    for r_idx in range(min(len(rounds) - 1, 4)):
        solver.update(rounds[r_idx]["user_idx"], rounds_numpy[r_idx])

    # R5 推荐
    r5_opts = rounds_numpy[len(rounds) - 1]
    gold_rec = solver.recommend(r5_opts)
    gold_user = rounds[-1]["user_idx"]

    return {
        "gold_solver_rec": gold_rec,
        "gold_user_choice": gold_user,
        "gold_match": gold_rec == gold_user,
    }


# ==========================================
# E2E pipeline: LLM parse → normalize → solver
# ==========================================
def run_parsed_pipeline(
    parsed_data: Dict,
    sample: Dict,
) -> Dict:
    """用 LLM 解析结果跑 PreferenceSolver"""
    from solvers.preference_solver import PreferenceSolver

    rounds = sample["rounds"]
    parsed_rounds = parsed_data.get("rounds", [])
    n_rounds = len(rounds)
    pref_values = [-1.0, -0.5, 0.0, 0.5, 1.0]

    if len(parsed_rounds) != n_rounds:
        return {"success": False, "error": f"round count mismatch: {len(parsed_rounds)} vs {n_rounds}"}

    solver = PreferenceSolver(
        feature_dim=4,
        preference_values=pref_values,
        temperature=1.0,
    )

    # 归一化所有 round 的特征
    normalized_rounds = []
    feature_errors = []  # 跟踪每个特征的归一化误差
    for r_idx in range(n_rounds):
        pr = parsed_rounds[r_idx]
        opts = pr.get("options", [])
        if len(opts) != 3:
            return {"success": False, "error": f"round {r_idx+1} option count: {len(opts)}"}

        norm_opts = []
        for o_idx, raw_opt in enumerate(opts):
            norm = normalize_features(raw_opt)
            # 四舍五入到网格（数据集用 0.1 步长）
            norm = [round_to_grid(v) for v in norm]
            norm_opts.append(norm)

            # 计算与 gold 的特征误差
            gold_feat = sample["rounds_numpy"][r_idx][o_idx]
            for f_idx in range(4):
                feature_errors.append({
                    "round": r_idx + 1,
                    "option": o_idx,
                    "feature_idx": f_idx,
                    "parsed": norm[f_idx],
                    "gold": gold_feat[f_idx],
                    "error": abs(norm[f_idx] - gold_feat[f_idx]),
                })

        normalized_rounds.append(norm_opts)

    # R1-R4 更新
    for r_idx in range(min(n_rounds - 1, 4)):
        solver.update(rounds[r_idx]["user_idx"], normalized_rounds[r_idx])

    # R5 推荐
    rec = solver.recommend(normalized_rounds[-1])
    gold_user = rounds[-1]["user_idx"]

    # gold solver
    gold_info = compute_gold_pipeline(sample)

    # 特征匹配统计
    total_features = len(feature_errors)
    exact_match = sum(1 for e in feature_errors if e["error"] < 0.001)
    close_match = sum(1 for e in feature_errors if e["error"] <= 0.05)

    return {
        "success": True,
        "e2e_recommendation": rec,
        "gold_user_choice": gold_user,
        "gold_solver_rec": gold_info["gold_solver_rec"],
        "e2e_correct": rec == gold_user,
        "e2e_matches_gold_solver": rec == gold_info["gold_solver_rec"],
        "feature_exact_match": exact_match / total_features if total_features > 0 else 0,
        "feature_close_match": close_match / total_features if total_features > 0 else 0,
        "feature_errors": feature_errors,
    }


# ==========================================
# Bootstrap CI
# ==========================================
def bootstrap_ci(values: List[bool], n_boot: int = 2000, alpha: float = 0.05) -> Tuple[float, float, float]:
    """Bootstrap 95% CI"""
    arr = np.array(values, dtype=float)
    mean = arr.mean()
    if len(arr) < 2:
        return mean, mean, mean
    boot_means = []
    rng = np.random.default_rng(42)
    for _ in range(n_boot):
        sample = rng.choice(arr, size=len(arr), replace=True)
        boot_means.append(sample.mean())
    boot_means = sorted(boot_means)
    lo = boot_means[int(n_boot * alpha / 2)]
    hi = boot_means[int(n_boot * (1 - alpha / 2))]
    return mean, lo, hi


# ==========================================
# 主实验
# ==========================================
async def run_e2e(
    model: str,
    n_samples: int,
    concurrency: int,
) -> Dict:
    """运行端到端链路实验"""
    if not FLIGHT_DATA.exists():
        print(f"  [跳过] 数据文件不存在: {FLIGHT_DATA}")
        return {}

    with open(FLIGHT_DATA, encoding="utf-8") as f:
        samples = [json.loads(line) for line in f]
    if n_samples > 0:
        samples = samples[:n_samples]

    print(f"\n{'='*60}")
    print(f"端到端链路实验: NL → LLM Parse → Solver → Answer")
    print(f"模型: {model}, 样本数: {len(samples)}, 并发: {concurrency}")
    print(f"{'='*60}")

    # 1. Gold pipeline baseline
    print("  [1/3] 计算 Gold Pipeline baseline...")
    gold_results = [compute_gold_pipeline(s) for s in samples]
    gold_acc = sum(1 for g in gold_results if g["gold_match"]) / len(gold_results)
    print(f"    Gold Pipeline (solver with gold features): {gold_acc*100:.1f}%")

    # 2. LLM Parse
    print(f"  [2/3] LLM NL Parse（{len(samples)} 样本）...")
    client = get_client()
    sem = asyncio.Semaphore(concurrency)

    prompts = [build_e2e_parse_prompt(s) for s in samples]
    tasks = [call_llm(client, model, p, sem) for p in prompts]
    responses = await asyncio.gather(*tasks)

    # 3. E2E Pipeline
    print("  [3/3] 运行 E2E Pipeline...")
    e2e_results = []
    parse_failures = 0
    for i, (ok, text) in enumerate(responses):
        if not ok:
            e2e_results.append({"success": False, "error": "api_error", "raw_response": text[:200]})
            parse_failures += 1
            continue

        parsed = extract_json(text)
        if parsed is None:
            e2e_results.append({"success": False, "error": "json_parse_error", "raw_response": text[:500]})
            parse_failures += 1
            continue

        result = run_parsed_pipeline(parsed, samples[i])
        if not result["success"]:
            parse_failures += 1
        e2e_results.append(result)

    # ==========================================
    # 汇总
    # ==========================================
    successful = [r for r in e2e_results if r.get("success", False)]
    n_success = len(successful)
    n_total = len(e2e_results)

    # E2E 准确率（成功样本中）
    e2e_correct_list = [r["e2e_correct"] for r in successful]
    e2e_acc, e2e_lo, e2e_hi = bootstrap_ci(e2e_correct_list) if e2e_correct_list else (0, 0, 0)

    # 与 gold solver 的一致性
    solver_match_list = [r["e2e_matches_gold_solver"] for r in successful]
    solver_match, sm_lo, sm_hi = bootstrap_ci(solver_match_list) if solver_match_list else (0, 0, 0)

    # 特征匹配
    avg_exact = np.mean([r["feature_exact_match"] for r in successful]) if successful else 0
    avg_close = np.mean([r["feature_close_match"] for r in successful]) if successful else 0

    # 按特征维度统计误差
    feature_names = ["departure_time", "duration", "stops", "price"]
    per_feature_exact = {fn: 0.0 for fn in feature_names}
    per_feature_count = {fn: 0 for fn in feature_names}
    for r in successful:
        for fe in r["feature_errors"]:
            fn = feature_names[fe["feature_idx"]]
            per_feature_count[fn] += 1
            if fe["error"] < 0.001:
                per_feature_exact[fn] += 1
    per_feature_acc = {}
    for fn in feature_names:
        if per_feature_count[fn] > 0:
            per_feature_acc[fn] = per_feature_exact[fn] / per_feature_count[fn]
        else:
            per_feature_acc[fn] = 0.0

    # 打印结果
    print(f"\n  {'='*50}")
    print(f"  结果汇总")
    print(f"  {'='*50}")
    print(f"  Parse 成功率:        {n_success}/{n_total} ({n_success/n_total*100:.1f}%)")
    print(f"  Gold Pipeline:       {gold_acc*100:.1f}%")
    print(f"  E2E 准确率:          {e2e_acc*100:.1f}% [{e2e_lo*100:.1f}%, {e2e_hi*100:.1f}%]")
    print(f"  与 Gold Solver 一致: {solver_match*100:.1f}% [{sm_lo*100:.1f}%, {sm_hi*100:.1f}%]")
    print(f"  特征精确匹配率:      {avg_exact*100:.1f}%")
    print(f"  特征近似匹配率(±0.05): {avg_close*100:.1f}%")
    print(f"\n  各特征精确匹配率:")
    for fn in feature_names:
        print(f"    {fn:<20} {per_feature_acc[fn]*100:.1f}%")

    # 保存结果
    RESULTS_DIR.mkdir(exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    model_tag = model.replace("/", "_")

    summary = {
        "experiment": "e2e_pipeline",
        "model": model,
        "n_samples": n_total,
        "timestamp": ts,
        "parse_success_rate": n_success / n_total,
        "gold_pipeline_accuracy": gold_acc,
        "e2e_accuracy": e2e_acc,
        "e2e_ci_95": [e2e_lo, e2e_hi],
        "gold_solver_match": solver_match,
        "gold_solver_match_ci_95": [sm_lo, sm_hi],
        "feature_exact_match": avg_exact,
        "feature_close_match": avg_close,
        "per_feature_exact_match": per_feature_acc,
    }

    summary_path = RESULTS_DIR / f"e2e_{model_tag}_{ts}.json"
    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)
    print(f"\n  汇总保存: {summary_path}")

    # 保存详细结果
    details_path = RESULTS_DIR / f"e2e_{model_tag}_{ts}_details.json"
    # 去除 feature_errors（太大），保留关键字段
    details_slim = []
    for r in e2e_results:
        d = {k: v for k, v in r.items() if k != "feature_errors"}
        details_slim.append(d)
    with open(details_path, "w", encoding="utf-8") as f:
        json.dump(details_slim, f, indent=2, ensure_ascii=False)
    print(f"  详细保存: {details_path}")

    return summary


# ==========================================
# 入口
# ==========================================
async def main():
    parser = argparse.ArgumentParser(description="端到端链路实验")
    parser.add_argument("--model", "-m", nargs="+", default=["openai/gpt-4o-mini"],
                        help="模型列表")
    parser.add_argument("--n", "-n", type=int, default=200, help="样本数 (0=全部)")
    parser.add_argument("--concurrency", "-c", type=int, default=30, help="并发数")
    args = parser.parse_args()

    results = {}
    for model in args.model:
        r = await run_e2e(model, args.n, args.concurrency)
        results[model] = r

    # 多模型对比
    if len(results) > 1:
        print(f"\n{'='*60}")
        print("多模型对比")
        print(f"{'='*60}")
        print(f"  {'模型':<35} {'E2E':>8} {'Gold':>8} {'Parse%':>8}")
        print(f"  {'-'*59}")
        for model, r in results.items():
            if r:
                print(f"  {model:<35} {r['e2e_accuracy']*100:>7.1f}% {r['gold_pipeline_accuracy']*100:>7.1f}% {r['parse_success_rate']*100:>7.1f}%")


if __name__ == "__main__":
    asyncio.run(main())
