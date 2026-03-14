#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Parse/Compute/Decide 因果诊断实验

将 LLM 概率推理错误分解为三个阶段：
1. Parse: 从自然语言中提取结构化问题表示 → 测理解能力
2. Compute|GoldParse: 给定正确的结构化输入，计算概率 → 测计算能力
3. Decide|GoldPosterior: 给定正确的计算结果，做出决策 → 测决策能力

核心假设：如果 Parse 高、Compute 低、Decide 高 → 瓶颈在计算而非理解

用法:
  # 快速验证（10 样本）
  python run_pcd_experiment.py --task preference --n 10

  # 偏好学习（200 样本）
  python run_pcd_experiment.py --task preference --n 200

  # BN 推断（全量 900 样本）
  python run_pcd_experiment.py --task bn

  # 两个任务
  python run_pcd_experiment.py --task both --n 100

  # 指定模型
  python run_pcd_experiment.py --task both --n 50 --model openai/gpt-4o
"""

import os
import sys
import json
import re
import time
import asyncio
import argparse
import csv
import numpy as np
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from datetime import datetime

# 修复 Windows 控制台编码
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

import httpx
from openai import AsyncOpenAI

# ==========================================
# 路径常量
# ==========================================
SCRIPT_DIR = Path(__file__).parent
PROJECT_ROOT = SCRIPT_DIR.parent.parent
PROMPT_DIR = SCRIPT_DIR / "prompts"

FLIGHT_DATA = PROJECT_ROOT / "bayes" / "data" / "eval" / "interaction" / "flight.jsonl"
BLIND_DATA = PROJECT_ROOT / "BLInD" / "datasets" / "Base_1000_examples.csv"
RESULTS_DIR = SCRIPT_DIR / "results"

# 添加 meta-skill 到 path（导入 DSL）
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
# 通用 LLM 调用
# ==========================================
async def call_llm(
    client: AsyncOpenAI,
    model: str,
    prompt: str,
    semaphore: asyncio.Semaphore,
    max_tokens: int = 4096,
) -> Tuple[bool, str]:
    """调用 LLM，返回 (success, response_text)"""
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
    # 尝试 ```json ... ``` 块
    m = re.search(r'```(?:json)?\s*\n(.*?)```', text, re.DOTALL)
    if m:
        try:
            return json.loads(m.group(1).strip())
        except json.JSONDecodeError:
            pass
    # 尝试直接解析
    try:
        return json.loads(text.strip())
    except json.JSONDecodeError:
        pass
    # 尝试找 { ... } 块
    m = re.search(r'\{.*\}', text, re.DOTALL)
    if m:
        try:
            return json.loads(m.group(0))
        except json.JSONDecodeError:
            pass
    return None


def extract_last_number(text: str) -> Optional[float]:
    """提取响应中最后一个数字"""
    lines = text.strip().split("\n")
    for line in reversed(lines):
        line = line.strip()
        try:
            return float(line)
        except ValueError:
            # 尝试在行内找数字
            nums = re.findall(r'[\d.]+', line)
            if nums:
                try:
                    return float(nums[-1])
                except ValueError:
                    continue
    return None


def extract_int(text: str) -> Optional[int]:
    """提取响应中的整数"""
    text = text.strip()
    # 直接尝试
    try:
        return int(text)
    except ValueError:
        pass
    # 最后一行
    lines = text.strip().split("\n")
    for line in reversed(lines):
        line = line.strip()
        m = re.search(r'\b(\d)\b', line)
        if m:
            return int(m.group(1))
    return None


# ==========================================
# 偏好学习: Gold 数据计算
# ==========================================
def compute_preference_gold(sample: Dict) -> Dict:
    """用 PreferenceSolver 计算 gold 数据"""
    from solvers.preference_solver import PreferenceSolver
    from dsl import Distribution, HypothesisSpace, enumerate_hypotheses

    features = sample["features"]
    rounds = sample["rounds"]
    rounds_numpy = sample["rounds_numpy"]
    n_features = len(features)
    pref_values = [-1.0, -0.5, 0.0, 0.5, 1.0]

    solver = PreferenceSolver(
        feature_dim=n_features,
        preference_values=pref_values,
        temperature=1.0,
    )

    # R1-R4 更新
    observations = []
    for r_idx in range(min(len(rounds) - 1, 4)):
        r = rounds[r_idx]
        opts = rounds_numpy[r_idx]
        solver.update(r["user_idx"], opts)
        observations.append({
            "round": r_idx + 1,
            "chosen_idx": r["user_idx"],
            "option_features": [[round(v, 4) for v in opt] for opt in opts],
        })

    # R5 选项和 gold 推荐
    current_opts = rounds_numpy[len(rounds) - 1]
    eus = solver.get_expected_utilities(current_opts)
    gold_rec = solver.recommend(current_opts)
    gold_user = rounds[-1]["user_idx"]

    return {
        "features": features,
        "n_features": n_features,
        "preference_values": pref_values,
        "observations": observations,
        "current_options": [[round(v, 4) for v in opt] for opt in current_opts],
        "gold_eus": {str(k): round(v, 6) for k, v in eus.items()},
        "gold_recommendation": gold_rec,
        "gold_user_choice": gold_user,
    }


# ==========================================
# BN: Gold 数据计算
# ==========================================
def compute_bn_gold(row: Dict) -> Dict:
    """用 BNReferenceSolver 计算 gold 数据，同时提取结构化 BN"""
    from dsl.family_macros import parse_bn_graph, parse_bn_cpt, parse_bn_query

    context = row["contexts"]
    graph = row["graph"]
    query = row["query"]
    gold_answer = float(row["answers"])
    depth = int(row.get("depth", 0))

    # 解析图结构
    nodes, parents = parse_bn_graph(graph)
    # 解析 CPT
    factors = parse_bn_cpt(context, parents)
    # 解析查询
    query_vars, evidence = parse_bn_query(query)

    # 结构化 CPT（供 compute prompt 使用）
    cpt_structured = {}
    for node in nodes:
        parent_list = parents.get(node, [])
        cpt_structured[node] = {"parents": parent_list, "rows": []}
        # 从 factors 中找到对应的 factor
        for f in factors:
            if f.variables[0] == node:
                if not parent_list:
                    p_true = f.table.get((True,), 0.5)
                    p_false = f.table.get((False,), 0.5)
                    cpt_structured[node]["rows"].append({
                        "parent_values": {},
                        "prob_true": round(p_true, 4),
                        "prob_false": round(p_false, 4),
                    })
                else:
                    from itertools import product as itertools_product
                    for pv in itertools_product([True, False], repeat=len(parent_list)):
                        key_true = (True,) + pv
                        key_false = (False,) + pv
                        p_true = f.table.get(key_true, 0.5)
                        p_false = f.table.get(key_false, 0.5)
                        pv_dict = {parent_list[i]: str(pv[i]) for i in range(len(parent_list))}
                        cpt_structured[node]["rows"].append({
                            "parent_values": pv_dict,
                            "prob_true": round(p_true, 4),
                            "prob_false": round(p_false, 4),
                        })
                break

    # 结构化边
    edges = []
    for child, plist in parents.items():
        for p in plist:
            edges.append([p, child])

    # 查询结构化
    query_var = list(query_vars.keys())[0] if query_vars else ""
    query_val = str(list(query_vars.values())[0]) if query_vars else ""
    evidence_str = {k: str(v) for k, v in evidence.items()}

    return {
        "variables": nodes,
        "edges": edges,
        "cpt_structured": cpt_structured,
        "query_variable": query_var,
        "query_value": query_val,
        "evidence": evidence_str,
        "gold_answer": gold_answer,
        "depth": depth,
    }


# ==========================================
# 偏好学习: 三阶段评估
# ==========================================

def build_pref_parse_prompt(sample: Dict) -> str:
    """构建偏好学习 Parse 阶段的 prompt"""
    template = (PROMPT_DIR / "pcd_parse_preference.md").read_text(encoding="utf-8")
    features = sample["features"]
    rounds = sample["rounds"]
    rounds_numpy = sample["rounds_numpy"]
    n_features = len(features)

    # 构建历史 block
    history_lines = []
    for r_idx in range(min(len(rounds) - 1, 4)):
        r = rounds[r_idx]
        opts = rounds_numpy[r_idx]
        chosen = r["user_idx"]
        history_lines.append(f"Round {r_idx + 1}:")
        for o_idx, opt in enumerate(opts):
            opt_str = ", ".join(f"{features[j]}={opt[j]:.2f}" for j in range(n_features))
            marker = " <-- USER CHOSE THIS" if o_idx == chosen else ""
            history_lines.append(f"  Option {o_idx}: [{opt_str}]{marker}")
        history_lines.append("")

    last_round = rounds_numpy[len(rounds) - 1]
    current_lines = []
    for o_idx, opt in enumerate(last_round):
        opt_str = ", ".join(f"{features[j]}={opt[j]:.2f}" for j in range(n_features))
        current_lines.append(f"Option {o_idx}: [{opt_str}]")

    pref_values = [-1.0, -0.5, 0.0, 0.5, 1.0]
    return template.format(
        n_features=n_features,
        feature_names=", ".join(features),
        preference_values=str(pref_values),
        n_history=min(len(rounds) - 1, 4),
        history_block="\n".join(history_lines),
        current_options="\n".join(current_lines),
    )


def build_pref_compute_prompt(gold: Dict) -> str:
    """构建偏好学习 Compute 阶段的 prompt（给 gold parse 数据）"""
    template = (PROMPT_DIR / "pcd_compute_preference.md").read_text(encoding="utf-8")
    n_features = gold["n_features"]
    features = gold["features"]
    pref_vals = gold["preference_values"]
    n_hyp = len(pref_vals) ** n_features

    # 格式化观测
    obs_lines = []
    for obs in gold["observations"]:
        opts_str = "\n".join(
            f"    Option {i}: {opt}"
            for i, opt in enumerate(obs["option_features"])
        )
        obs_lines.append(
            f"  Round {obs['round']}:\n{opts_str}\n"
            f"    User chose: Option {obs['chosen_idx']}"
        )

    # 格式化当前选项
    cur_lines = [
        f"  Option {i}: {opt}"
        for i, opt in enumerate(gold["current_options"])
    ]

    return template.format(
        n_features=n_features,
        feature_names=", ".join(features),
        preference_values=str(pref_vals),
        n_hypotheses=n_hyp,
        observations_formatted="\n".join(obs_lines),
        current_options_formatted="\n".join(cur_lines),
    )


def build_pref_decide_prompt(gold: Dict) -> str:
    """构建偏好学习 Decide 阶段的 prompt（给 gold EUs）"""
    template = (PROMPT_DIR / "pcd_decide_preference.md").read_text(encoding="utf-8")
    eus = gold["gold_eus"]
    eu_lines = [
        f"- Option {k}: Expected Utility = {v:.6f}"
        for k, v in sorted(eus.items())
    ]
    return template.format(eu_block="\n".join(eu_lines))


def eval_pref_parse(response: Dict, gold: Dict) -> Dict:
    """评估偏好学习 Parse 结果"""
    if response is None:
        return {"correct": False, "detail": "no_json", "scores": {}}

    scores = {}

    # 检查 n_features
    scores["n_features"] = response.get("n_features") == gold["n_features"]

    # 检查 feature_names（顺序无关）
    resp_names = set(response.get("feature_names", []))
    gold_names = set(gold["features"])
    scores["feature_names"] = resp_names == gold_names

    # 检查 preference_values
    resp_pv = sorted([float(x) for x in response.get("preference_values", [])])
    gold_pv = sorted(gold["preference_values"])
    scores["preference_values"] = resp_pv == gold_pv

    # 检查 observations
    resp_obs = response.get("observations", [])
    gold_obs = gold["observations"]
    obs_correct = 0
    for i, g_obs in enumerate(gold_obs):
        if i < len(resp_obs):
            r_obs = resp_obs[i]
            if r_obs.get("chosen_idx") == g_obs["chosen_idx"]:
                obs_correct += 1
    scores["observations_choice"] = obs_correct == len(gold_obs) if gold_obs else True

    # 检查 current_options（近似匹配）
    resp_cur = response.get("current_options", [])
    gold_cur = gold["current_options"]
    cur_match = len(resp_cur) == len(gold_cur)
    if cur_match and gold_cur:
        for rc, gc in zip(resp_cur, gold_cur):
            if len(rc) != len(gc):
                cur_match = False
                break
            for rv, gv in zip(rc, gc):
                if abs(float(rv) - float(gv)) > 0.05:
                    cur_match = False
                    break
    scores["current_options"] = cur_match

    # structural parse: 不含 preference_values
    structural_fields = ["n_features", "feature_names", "observations_choice", "current_options"]
    structural_correct = all(scores[f] for f in structural_fields)
    # 总体: 所有关键字段都正确
    all_correct = all(scores.values())
    return {"correct": all_correct, "structural_correct": structural_correct, "detail": "ok", "scores": scores}


# ==========================================
# BN: 三阶段评估
# ==========================================

def build_bn_parse_prompt(row: Dict) -> str:
    """构建 BN Parse 阶段的 prompt"""
    template = (PROMPT_DIR / "pcd_parse_bn.md").read_text(encoding="utf-8")
    return template.format(
        context=row["contexts"],
        graph=row["graph"],
        query=row["query"],
    )


def build_bn_compute_prompt(gold: Dict) -> str:
    """构建 BN Compute 阶段的 prompt（给 gold parse 数据）"""
    template = (PROMPT_DIR / "pcd_compute_bn.md").read_text(encoding="utf-8")

    # 格式化 CPT
    cpt_lines = []
    for var, cpt in gold["cpt_structured"].items():
        parents = cpt["parents"]
        if not parents:
            row = cpt["rows"][0]
            cpt_lines.append(f"P({var} = True) = {row['prob_true']}")
            cpt_lines.append(f"P({var} = False) = {row['prob_false']}")
        else:
            for row in cpt["rows"]:
                pv_str = ", ".join(f"{k}={v}" for k, v in row["parent_values"].items())
                cpt_lines.append(f"P({var} = True | {pv_str}) = {row['prob_true']}")
                cpt_lines.append(f"P({var} = False | {pv_str}) = {row['prob_false']}")
        cpt_lines.append("")

    # 格式化 evidence
    ev = gold["evidence"]
    if ev:
        ev_str = ", ".join(f"{k} = {v}" for k, v in ev.items())
    else:
        ev_str = "none"

    # 格式化 edges
    edges_str = ", ".join(f"{e[0]} -> {e[1]}" for e in gold["edges"])

    return template.format(
        variables=", ".join(gold["variables"]),
        edges=edges_str if edges_str else "none",
        cpt_formatted="\n".join(cpt_lines),
        query_var=gold["query_variable"],
        query_val=gold["query_value"],
        evidence_formatted=ev_str,
    )


def eval_bn_parse(response: Dict, gold: Dict) -> Dict:
    """评估 BN Parse 结果"""
    if response is None:
        return {"correct": False, "detail": "no_json", "scores": {}}

    scores = {}

    # 检查 variables（顺序无关）
    resp_vars = set(response.get("variables", []))
    gold_vars = set(gold["variables"])
    scores["variables"] = resp_vars == gold_vars

    # 检查 edges（顺序无关）
    resp_edges = {tuple(e) for e in response.get("edges", [])}
    gold_edges = {tuple(e) for e in gold["edges"]}
    scores["edges"] = resp_edges == gold_edges

    # 检查 query
    scores["query_variable"] = response.get("query_variable") == gold["query_variable"]
    scores["query_value"] = str(response.get("query_value", "")).capitalize() == gold["query_value"]

    # 检查 evidence
    resp_ev = {k: str(v).capitalize() for k, v in response.get("evidence", {}).items()}
    gold_ev = {k: str(v).capitalize() for k, v in gold["evidence"].items()}
    scores["evidence"] = resp_ev == gold_ev

    # 检查 CPT 值（容差 0.02）
    cpt_correct = True
    resp_cpts = response.get("cpts", {})
    gold_cpts = gold["cpt_structured"]
    for var, g_cpt in gold_cpts.items():
        if var not in resp_cpts:
            cpt_correct = False
            break
        r_cpt = resp_cpts[var]
        # 简化检查：比较 prob_true 值
        g_probs = sorted([r["prob_true"] for r in g_cpt["rows"]])
        r_rows = r_cpt.get("rows", [])
        r_probs = sorted([float(r.get("prob_true", 0)) for r in r_rows])
        if len(g_probs) != len(r_probs):
            cpt_correct = False
            break
        for gp, rp in zip(g_probs, r_probs):
            if abs(gp - rp) > 0.02:
                cpt_correct = False
                break
        if not cpt_correct:
            break
    scores["cpt_values"] = cpt_correct

    all_correct = all(scores.values())
    return {"correct": all_correct, "detail": "ok", "scores": scores}


# ==========================================
# 主实验逻辑
# ==========================================

async def run_preference_pcd(
    model: str,
    n_samples: int,
    concurrency: int,
) -> Dict:
    """运行偏好学习 Parse/Compute/Decide 实验"""
    if not FLIGHT_DATA.exists():
        print(f"  [跳过] 数据文件不存在: {FLIGHT_DATA}")
        return {}

    with open(FLIGHT_DATA, encoding="utf-8") as f:
        samples = [json.loads(line) for line in f]
    if n_samples > 0:
        samples = samples[:n_samples]

    print(f"\n{'='*60}")
    print(f"PCD 诊断: 偏好学习 (Flight)")
    print(f"模型: {model}, 样本数: {len(samples)}, 并发: {concurrency}")
    print(f"{'='*60}")

    # 1. 预计算 gold 数据
    print("  [1/4] 计算 gold 数据...")
    golds = [compute_preference_gold(s) for s in samples]

    client = get_client()
    sem = asyncio.Semaphore(concurrency)

    # 2. Stage 1: Parse
    print("  [2/4] Stage 1: Parse...")
    parse_prompts = [build_pref_parse_prompt(s) for s in samples]
    parse_tasks = [call_llm(client, model, p, sem) for p in parse_prompts]
    parse_responses = await asyncio.gather(*parse_tasks)

    parse_results = []
    for i, (ok, text) in enumerate(parse_responses):
        if not ok:
            parse_results.append({"correct": False, "detail": "api_error", "scores": {}})
        else:
            parsed = extract_json(text)
            result = eval_pref_parse(parsed, golds[i])
            parse_results.append(result)

    parse_acc = sum(1 for r in parse_results if r["correct"]) / len(parse_results)
    structural_parse_acc = sum(1 for r in parse_results if r.get("structural_correct", False)) / len(parse_results)
    # 各字段准确率
    field_accs = {}
    for field in ["n_features", "feature_names", "preference_values", "observations_choice", "current_options"]:
        field_accs[field] = sum(
            1 for r in parse_results if r["scores"].get(field, False)
        ) / len(parse_results)
    print(f"    Parse 全正确: {parse_acc*100:.1f}%")
    print(f"    Parse 结构化 (不含 pref_values): {structural_parse_acc*100:.1f}%")
    for k, v in field_accs.items():
        print(f"      {k}: {v*100:.1f}%")

    # 3. Stage 2: Compute | Gold Parse
    print("  [3/4] Stage 2: Compute | Gold Parse...")
    compute_prompts = [build_pref_compute_prompt(g) for g in golds]
    compute_tasks = [call_llm(client, model, p, sem, max_tokens=8192) for p in compute_prompts]
    compute_responses = await asyncio.gather(*compute_tasks)

    compute_results = []
    for i, (ok, text) in enumerate(compute_responses):
        gold_rec = golds[i]["gold_recommendation"]
        if not ok:
            compute_results.append({"correct": False, "predicted": -1, "gold": gold_rec, "error": "api"})
            continue
        # 提取推荐
        parsed = extract_json(text)
        if parsed and "recommendation" in parsed:
            pred = int(parsed["recommendation"])
        else:
            pred_val = extract_int(text)
            pred = pred_val if pred_val is not None else -1
        compute_results.append({
            "correct": pred == gold_rec,
            "predicted": pred,
            "gold": gold_rec,
        })

    compute_acc = sum(1 for r in compute_results if r["correct"]) / len(compute_results)
    print(f"    Compute 准确率: {compute_acc*100:.1f}%")

    # 4. Stage 3: Decide | Gold Posterior
    print("  [4/4] Stage 3: Decide | Gold Posterior...")
    decide_prompts = [build_pref_decide_prompt(g) for g in golds]
    decide_tasks = [call_llm(client, model, p, sem, max_tokens=256) for p in decide_prompts]
    decide_responses = await asyncio.gather(*decide_tasks)

    decide_results = []
    for i, (ok, text) in enumerate(decide_responses):
        gold_rec = golds[i]["gold_recommendation"]
        if not ok:
            decide_results.append({"correct": False, "predicted": -1, "gold": gold_rec})
            continue
        pred = extract_int(text)
        pred = pred if pred is not None else -1
        decide_results.append({
            "correct": pred == gold_rec,
            "predicted": pred,
            "gold": gold_rec,
        })

    decide_acc = sum(1 for r in decide_results if r["correct"]) / len(decide_results)
    print(f"    Decide 准确率: {decide_acc*100:.1f}%")

    # 汇总
    print(f"\n  {'阶段':<20} {'准确率':>10}")
    print(f"  {'-'*30}")
    print(f"  {'Parse (structural)':.<20} {structural_parse_acc*100:>9.1f}%")
    print(f"  {'Compute|GoldParse':.<20} {compute_acc*100:>9.1f}%")
    print(f"  {'Decide|GoldPost':.<20} {decide_acc*100:>9.1f}%")

    return {
        "task": "preference",
        "model": model,
        "n_samples": len(samples),
        "parse_accuracy": parse_acc,
        "structural_parse_accuracy": structural_parse_acc,
        "parse_field_accuracy": field_accs,
        "compute_accuracy": compute_acc,
        "decide_accuracy": decide_acc,
        "parse_details": parse_results,
        "compute_details": compute_results,
        "decide_details": decide_results,
    }


async def run_bn_pcd(
    model: str,
    n_samples: int,
    concurrency: int,
) -> Dict:
    """运行 BN 推断 Parse/Compute/Decide 实验"""
    if not BLIND_DATA.exists():
        print(f"  [跳过] BLInD 数据不存在: {BLIND_DATA}")
        return {}

    with open(BLIND_DATA, encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    if n_samples > 0:
        rows = rows[:n_samples]

    print(f"\n{'='*60}")
    print(f"PCD 诊断: BN 推断 (BLInD)")
    print(f"模型: {model}, 样本数: {len(rows)}, 并发: {concurrency}")
    print(f"{'='*60}")

    # 1. 预计算 gold 数据
    print("  [1/4] 计算 gold 数据...")
    golds = []
    for row in rows:
        try:
            golds.append(compute_bn_gold(row))
        except Exception as e:
            golds.append(None)
    valid_indices = [i for i, g in enumerate(golds) if g is not None]
    print(f"    有效样本: {len(valid_indices)}/{len(rows)}")

    client = get_client()
    sem = asyncio.Semaphore(concurrency)

    # 2. Stage 1: Parse
    print("  [2/4] Stage 1: Parse...")
    parse_prompts = [(i, build_bn_parse_prompt(rows[i])) for i in valid_indices]
    parse_tasks = [call_llm(client, model, p, sem) for _, p in parse_prompts]
    parse_raw = await asyncio.gather(*parse_tasks)

    parse_results = {}
    for (idx, _), (ok, text) in zip(parse_prompts, parse_raw):
        if not ok:
            parse_results[idx] = {"correct": False, "detail": "api_error", "scores": {}}
        else:
            parsed = extract_json(text)
            result = eval_bn_parse(parsed, golds[idx])
            parse_results[idx] = result

    parse_acc = sum(1 for r in parse_results.values() if r["correct"]) / len(parse_results) if parse_results else 0
    # 各字段准确率
    field_accs = {}
    for field in ["variables", "edges", "query_variable", "query_value", "evidence", "cpt_values"]:
        field_accs[field] = sum(
            1 for r in parse_results.values() if r["scores"].get(field, False)
        ) / len(parse_results) if parse_results else 0
    print(f"    Parse 全正确: {parse_acc*100:.1f}%")
    for k, v in field_accs.items():
        print(f"      {k}: {v*100:.1f}%")

    # 3. Stage 2: Compute | Gold Parse
    print("  [3/4] Stage 2: Compute | Gold Parse...")
    compute_prompts = [(i, build_bn_compute_prompt(golds[i])) for i in valid_indices]
    compute_tasks = [call_llm(client, model, p, sem, max_tokens=8192) for _, p in compute_prompts]
    compute_raw = await asyncio.gather(*compute_tasks)

    compute_results = {}
    for (idx, _), (ok, text) in zip(compute_prompts, compute_raw):
        gold_ans = golds[idx]["gold_answer"]
        depth = golds[idx]["depth"]
        if not ok:
            compute_results[idx] = {"correct": False, "predicted": None, "gold": gold_ans, "depth": depth, "error": "api"}
            continue
        pred = extract_last_number(text)
        if pred is not None:
            err = abs(pred - gold_ans)
            compute_results[idx] = {
                "correct": err < 0.01,
                "predicted": pred,
                "gold": gold_ans,
                "error_abs": err,
                "depth": depth,
            }
        else:
            compute_results[idx] = {"correct": False, "predicted": None, "gold": gold_ans, "depth": depth, "error": "no_number"}

    compute_acc = sum(1 for r in compute_results.values() if r["correct"]) / len(compute_results) if compute_results else 0
    print(f"    Compute 准确率: {compute_acc*100:.1f}%")

    # 按 depth 分组
    depth_stats = {}
    for r in compute_results.values():
        d = r.get("depth", 0)
        if d not in depth_stats:
            depth_stats[d] = {"total": 0, "correct": 0}
        depth_stats[d]["total"] += 1
        if r["correct"]:
            depth_stats[d]["correct"] += 1
    print(f"    按 depth 分组:")
    for d in sorted(depth_stats.keys()):
        s = depth_stats[d]
        dacc = s["correct"] / s["total"] if s["total"] > 0 else 0
        print(f"      depth={d}: {dacc*100:.1f}% ({s['correct']}/{s['total']})")

    # 4. Stage 3: Decide (BN 的 decide 是 trivial 的, 但仍然测试)
    # 对 BN，Decide = 给定 P(X=v|E) = p，问 X=v 是否更可能？
    print("  [4/4] Stage 3: Decide | Gold Posterior (trivial test)...")
    decide_results = {}
    decide_prompts_list = []
    for idx in valid_indices:
        gold = golds[idx]
        p = gold["gold_answer"]
        qvar = gold["query_variable"]
        qval = gold["query_value"]
        ev_str = ", ".join(f"{k}={v}" for k, v in gold["evidence"].items()) if gold["evidence"] else "no evidence"
        prompt = (
            f"The exact probability P({qvar} = {qval} | {ev_str}) = {p:.4f}.\n"
            f"Based on this, what is P({qvar} = {qval} | {ev_str})?\n"
            f"Output ONLY the probability as a decimal number."
        )
        decide_prompts_list.append((idx, prompt))
    decide_tasks = [call_llm(client, model, p, sem, max_tokens=256) for _, p in decide_prompts_list]
    decide_raw = await asyncio.gather(*decide_tasks)

    for (idx, _), (ok, text) in zip(decide_prompts_list, decide_raw):
        gold_ans = golds[idx]["gold_answer"]
        depth = golds[idx]["depth"]
        if not ok:
            decide_results[idx] = {"correct": False, "depth": depth}
            continue
        pred = extract_last_number(text)
        if pred is not None:
            err = abs(pred - gold_ans)
            decide_results[idx] = {"correct": err < 0.01, "predicted": pred, "gold": gold_ans, "depth": depth}
        else:
            decide_results[idx] = {"correct": False, "depth": depth}

    decide_acc = sum(1 for r in decide_results.values() if r["correct"]) / len(decide_results) if decide_results else 0
    print(f"    Decide 准确率: {decide_acc*100:.1f}%")

    # 汇总
    print(f"\n  {'阶段':<20} {'准确率':>10}")
    print(f"  {'-'*30}")
    print(f"  {'Parse':.<20} {parse_acc*100:>9.1f}%")
    print(f"  {'Compute|GoldParse':.<20} {compute_acc*100:>9.1f}%")
    print(f"  {'Decide|GoldPost':.<20} {decide_acc*100:>9.1f}%")

    # 按 depth 的 Parse vs Compute 对比
    parse_by_depth = {}
    for idx, r in parse_results.items():
        d = golds[idx]["depth"]
        if d not in parse_by_depth:
            parse_by_depth[d] = {"total": 0, "correct": 0}
        parse_by_depth[d]["total"] += 1
        if r["correct"]:
            parse_by_depth[d]["correct"] += 1

    print(f"\n  Parse vs Compute by depth:")
    print(f"  {'depth':>5} | {'Parse':>8} | {'Compute':>8} | {'gap':>8}")
    print(f"  {'-'*37}")
    for d in sorted(set(list(parse_by_depth.keys()) + list(depth_stats.keys()))):
        p_s = parse_by_depth.get(d, {"total": 0, "correct": 0})
        c_s = depth_stats.get(d, {"total": 0, "correct": 0})
        p_acc = p_s["correct"] / p_s["total"] * 100 if p_s["total"] > 0 else 0
        c_acc = c_s["correct"] / c_s["total"] * 100 if c_s["total"] > 0 else 0
        print(f"  {d:>5} | {p_acc:>7.1f}% | {c_acc:>7.1f}% | {p_acc - c_acc:>+7.1f}%")

    return {
        "task": "bn",
        "model": model,
        "n_samples": len(valid_indices),
        "parse_accuracy": parse_acc,
        "parse_field_accuracy": field_accs,
        "compute_accuracy": compute_acc,
        "compute_depth_stats": {str(k): v for k, v in depth_stats.items()},
        "decide_accuracy": decide_acc,
        "parse_by_depth": {str(k): v for k, v in parse_by_depth.items()},
        "parse_details": {str(k): v for k, v in parse_results.items()},
        "compute_details": {str(k): v for k, v in compute_results.items()},
        "decide_details": {str(k): v for k, v in decide_results.items()},
    }


async def main():
    parser = argparse.ArgumentParser(description="Parse/Compute/Decide 因果诊断实验")
    parser.add_argument("--task", choices=["preference", "bn", "both"], default="both")
    parser.add_argument("--model", "-m", default="openai/gpt-4o-mini")
    parser.add_argument("--n", type=int, default=0, help="样本数 (0=全部)")
    parser.add_argument("--concurrency", "-c", type=int, default=20)
    args = parser.parse_args()

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    all_results = {}

    if args.task in ("preference", "both"):
        result = await run_preference_pcd(args.model, args.n, args.concurrency)
        if result:
            all_results["preference"] = result

    if args.task in ("bn", "both"):
        result = await run_bn_pcd(args.model, args.n, args.concurrency)
        if result:
            all_results["bn"] = result

    # 保存结果
    if all_results:
        model_tag = args.model.replace("/", "_")
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        out_file = RESULTS_DIR / f"pcd_{model_tag}_{ts}.json"

        # 移除超大 details
        summary = {}
        for task_name, result in all_results.items():
            details = {}
            for key in list(result.keys()):
                if "details" in key:
                    details[key] = result.pop(key)
            summary[task_name] = result
            # 详细结果单独存
            detail_file = RESULTS_DIR / f"pcd_{model_tag}_{task_name}_{ts}_details.json"
            with open(detail_file, "w", encoding="utf-8") as f:
                json.dump(details, f, indent=2, ensure_ascii=False, default=str)
            print(f"\n详细结果: {detail_file}")

        with open(out_file, "w", encoding="utf-8") as f:
            json.dump(summary, f, indent=2, ensure_ascii=False, default=str)
        print(f"\n汇总结果: {out_file}")

    # 最终汇总表
    print(f"\n{'='*60}")
    print("Parse/Compute/Decide 因果诊断 — 最终汇总")
    print(f"{'='*60}")
    print(f"模型: {args.model}\n")
    print(f"{'任务':<15} {'Parse':>8} {'Compute':>10} {'Decide':>8} {'诊断':>20}")
    print(f"{'-'*65}")
    for task_name, result in all_results.items():
        p = result.get("structural_parse_accuracy", result["parse_accuracy"]) * 100
        c = result["compute_accuracy"] * 100
        d = result["decide_accuracy"] * 100
        # 诊断：Parse 高 + Compute 低 = 瓶颈在计算
        if p > 70 and c < 60 and d > 80:
            diag = "瓶颈在计算"
        elif p < 50:
            diag = "理解也有问题"
        elif d < 70:
            diag = "决策也有问题"
        else:
            diag = "待分析"
        print(f"{task_name:<15} {p:>7.1f}% {c:>9.1f}% {d:>7.1f}% {diag:>20}")

    print(f"\n核心论证: 如果 Parse 高 + Compute 低 + Decide 高 → 瓶颈在计算而非理解")


if __name__ == "__main__":
    asyncio.run(main())
