#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
DeLLMa 农业决策实验：直接回答 vs 生成 Python solver

对比三种方式在 DeLLMa 农业决策任务上的表现：
1. Direct: 模型直接选择最佳水果
2. Compile-time: 模型写一个通用 Python solver
3. (后续) DSL: 用我们的 inductor

用法:
  python run_dellma_experiment.py --model openai/gpt-5.4 --n 20
  python run_dellma_experiment.py --model anthropic/claude-opus-4-6 --n 20
  python run_dellma_experiment.py --model openai/gpt-4o-mini --n 20 --mode both
"""

import os
import sys
import json
import asyncio
import argparse
import random
import traceback
from itertools import combinations
from typing import List, Dict, Tuple, Optional

# OpenRouter API
import httpx

OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY", "")
OPENROUTER_BASE = "https://openrouter.ai/api/v1"

# DeLLMa 数据路径
DELLMA_ROOT = os.path.join(os.path.dirname(__file__), "..", "..", "DeLLMa")

# 7 种水果 (DeLLMa 2021)
FRUITS = ['apple', 'avocado', 'grape', 'grapefruit', 'lemon', 'peach', 'pear']

# 2021 年统计 (模型可见)
STATS_2021 = {
    'apple': {'yield': '19,000 LB / ACRE', 'price': '0.244 $ / LB'},
    'avocado': {'yield': '2.87 TONS / ACRE', 'price': '2,430 $ / TON'},
    'grape': {'yield': '6.92 TONS / ACRE', 'price': '908 $ / TON'},
    'grapefruit': {'yield': '457 BOXES / ACRE', 'price': '24.33 $ / BOX'},
    'lemon': {'yield': '428 BOXES / ACRE', 'price': '23.3 $ / BOX'},
    'peach': {'yield': '13.7 TONS / ACRE', 'price': '763 $ / TON'},
    'pear': {'yield': '15.6 TONS / ACRE', 'price': '565 $ / TON'},
}

# 2022 年实际 utility (ground truth)
UTILITY_2022 = {
    'apple': 18000 * 0.3,       # 5400
    'avocado': 2.97 * 3530,     # 10484.1
    'grape': 6.7 * 1010,        # 6767
    'grapefruit': 432 * 9.59,   # 4142.88
    'lemon': 485 * 15.59,       # 7561.15
    'peach': 12.9 * 891,        # 11493.9
    'pear': 17.1 * 640,         # 10944
}

# 2021 年 utility (用于 sanity check)
UTILITY_2021 = {
    'apple': 19000 * 0.244,     # 4636
    'avocado': 2.87 * 2430,     # 6974.1
    'grape': 6.92 * 908,        # 6283.36
    'grapefruit': 457 * 24.33,  # 11118.81
    'lemon': 428 * 23.3,        # 9972.4
    'peach': 13.7 * 763,        # 10453.1
    'pear': 15.6 * 565,         # 8814
}

# 状态信念 (从 DeLLMa cache 提取的简化版)
STATE_BELIEFS = None  # 从 farmer_2021_states.json 加载


def load_usda_report():
    """加载 USDA 报告摘要"""
    report_path = os.path.join(DELLMA_ROOT, "data", "agriculture", "reports", "fruit-sept-2021.txt")
    if os.path.exists(report_path):
        with open(report_path, 'r', encoding='utf-8', errors='replace') as f:
            text = f.read()
        # 截取前 2000 字符以控制 prompt 长度
        return text[:2000] + "..." if len(text) > 2000 else text
    return "(USDA report not available)"


def get_ground_truth(fruits: List[str]) -> Tuple[int, str]:
    """根据 2022 年实际数据返回最佳选择"""
    utilities = [UTILITY_2022[f] for f in fruits]
    best_idx = utilities.index(max(utilities))
    return best_idx, fruits[best_idx]


def format_stats_table(fruits: List[str]) -> str:
    """格式化 2021 年统计表"""
    lines = ["Fruit | Yield per Acre | Price per Unit | Estimated Utility (2021)"]
    lines.append("-" * 70)
    for f in fruits:
        s = STATS_2021[f]
        u = UTILITY_2021[f]
        lines.append(f"{f.capitalize():12} | {s['yield']:20} | {s['price']:15} | ${u:,.0f}")
    return "\n".join(lines)


async def call_llm(model: str, messages: list, temperature: float = 0.0) -> str:
    """调用 OpenRouter API"""
    async with httpx.AsyncClient(
        base_url=OPENROUTER_BASE,
        headers={"Authorization": f"Bearer {OPENROUTER_API_KEY}"},
        timeout=120.0,
    ) as client:
        resp = await client.post("/chat/completions", json={
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": 2000,
        })
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"]


async def direct_answer(model: str, fruits: List[str], usda_report: str) -> int:
    """方式 1: 直接回答"""
    stats_table = format_stats_table(fruits)
    prompt = f"""You are an agricultural expert helping a California farmer decide what fruit to plant next year to maximize profit (utility = yield × price per acre).

Here is the USDA fruit market report from September 2021:
{usda_report[:1500]}

Here are the 2021 California statistics for the available fruits:
{stats_table}

Based on this information, which single fruit should the farmer plant to maximize expected profit next year (2022)?

Available options (choose exactly one number):
"""
    for i, f in enumerate(fruits):
        prompt += f"{i+1}. {f.capitalize()}\n"

    prompt += "\nRespond with ONLY the number of your choice (e.g., '1' or '2')."

    try:
        response = await call_llm(model, [{"role": "user", "content": prompt}])
        # 解析选择
        for line in response.strip().split('\n'):
            line = line.strip().strip('.')
            for i in range(len(fruits)):
                if line == str(i+1) or line.startswith(f"{i+1}.") or line.startswith(f"{i+1} "):
                    return i
            # 尝试匹配水果名
            for i, f in enumerate(fruits):
                if f.lower() in line.lower():
                    return i
        # fallback: 找第一个数字
        import re
        nums = re.findall(r'\d+', response[:50])
        if nums:
            n = int(nums[0]) - 1
            if 0 <= n < len(fruits):
                return n
        return -1
    except Exception as e:
        print(f"    API error: {e}")
        return -1


async def compile_time_solver(model: str, all_problems: List[List[str]], usda_report: str, max_repair: int = 3) -> Optional[callable]:
    """方式 2: 让模型写一个通用 Python solver"""
    # 给 3 个训练样例
    train_examples = []
    for fruits in all_problems[:3]:
        gt_idx, gt_fruit = get_ground_truth(fruits)
        stats_table = format_stats_table(fruits)
        train_examples.append({
            "fruits": fruits,
            "stats": stats_table,
            "answer": gt_fruit,
            "answer_idx": gt_idx,
        })

    examples_text = ""
    for i, ex in enumerate(train_examples):
        examples_text += f"""
Example {i+1}:
Fruits: {ex['fruits']}
Stats:
{ex['stats']}
Best choice: {ex['answer']} (index {ex['answer_idx']})
"""

    prompt = f"""You are writing a Python function to solve agricultural decision-making problems.

Task: Given a list of fruits and their 2021 statistics (yield per acre, price per unit), predict which fruit will have the highest utility (yield × price) in 2022.

Here is the USDA report context:
{usda_report[:1000]}

Here are some training examples:
{examples_text}

Write a Python function called `predict_best_fruit(fruits, stats_2021)` that:
1. Takes a list of fruit names and a dict of their 2021 stats
2. Analyzes the data and predicts which fruit will maximize utility in 2022
3. Returns the index (0-based) of the best fruit

The stats_2021 dict has format: {{"apple": {{"yield_val": 19000, "yield_unit": "LB", "price_val": 0.244, "price_unit": "LB"}}, ...}}

Your function should handle the analysis internally. You can use any standard Python libraries.

Return ONLY the Python code, no explanations. The function must be self-contained."""

    for attempt in range(max_repair + 1):
        try:
            if attempt == 0:
                response = await call_llm(model, [{"role": "user", "content": prompt}])
            else:
                response = await call_llm(model, [
                    {"role": "user", "content": prompt},
                    {"role": "assistant", "content": prev_code},
                    {"role": "user", "content": f"代码执行出错:\n{error_msg}\n请修复并返回完整的 Python 函数代码。"},
                ])

            # 提取代码
            code = response
            if "```python" in code:
                code = code.split("```python")[1].split("```")[0]
            elif "```" in code:
                code = code.split("```")[1].split("```")[0]

            prev_code = code

            # 编译测试
            exec_globals = {}
            exec(code, exec_globals)
            if 'predict_best_fruit' not in exec_globals:
                error_msg = "函数 predict_best_fruit 未定义"
                continue

            fn = exec_globals['predict_best_fruit']

            # 用训练样例验证
            test_passed = True
            for ex in train_examples:
                stats = {}
                for f in ex['fruits']:
                    s = STATS_2021[f]
                    yield_parts = s['yield'].split()
                    price_parts = s['price'].split()
                    stats[f] = {
                        'yield_val': float(yield_parts[0].replace(',', '')),
                        'yield_unit': yield_parts[1],
                        'price_val': float(price_parts[0].replace(',', '')),
                        'price_unit': price_parts[1],
                    }
                try:
                    result = fn(ex['fruits'], stats)
                    if result != ex['answer_idx']:
                        error_msg = f"训练样例验证失败: predict({ex['fruits']}) = {result}, 期望 {ex['answer_idx']} ({ex['answer']})"
                        test_passed = False
                        break
                except Exception as e:
                    error_msg = f"运行时错误: {e}\n{traceback.format_exc()}"
                    test_passed = False
                    break

            if test_passed:
                print(f"    Solver 编译成功 (attempt {attempt+1})")
                return fn, code

        except Exception as e:
            error_msg = f"编译错误: {e}\n{traceback.format_exc()}"
            prev_code = code if 'code' in dir() else ""
            continue

    print(f"    Solver 编译失败 ({max_repair+1} 次尝试)")
    return None, None


async def run_experiment(model: str, n_problems: int = 20, mode: str = "both", seed: int = 42):
    """运行实验"""
    random.seed(seed)
    usda_report = load_usda_report()

    # 生成所有组合
    all_combs = []
    for k in range(2, len(FRUITS) + 1):
        all_combs.extend([list(c) for c in combinations(FRUITS, k)])

    # 随机采样
    if n_problems < len(all_combs):
        # 确保涵盖不同 size
        sampled = []
        for k in range(2, 8):
            size_combs = [c for c in all_combs if len(c) == k]
            n_per_size = max(1, n_problems // 6)
            sampled.extend(random.sample(size_combs, min(n_per_size, len(size_combs))))
        # 补齐到 n_problems
        remaining = [c for c in all_combs if c not in sampled]
        while len(sampled) < n_problems and remaining:
            sampled.append(remaining.pop(random.randint(0, len(remaining)-1)))
        test_problems = sampled[:n_problems]
    else:
        test_problems = all_combs

    print(f"\n{'='*60}")
    print(f"DeLLMa 农业决策实验")
    print(f"模型: {model}, 问题数: {len(test_problems)}")
    print(f"{'='*60}")

    results = {"model": model, "n_problems": len(test_problems)}

    # === 方式 1: 直接回答 ===
    if mode in ["direct", "both"]:
        print(f"\n  [1/2] Direct Answer...")
        direct_correct = 0
        direct_total = 0
        for i, fruits in enumerate(test_problems):
            gt_idx, gt_fruit = get_ground_truth(fruits)
            pred_idx = await direct_answer(model, fruits, usda_report)
            correct = pred_idx == gt_idx
            if correct:
                direct_correct += 1
            direct_total += 1
            if (i+1) % 5 == 0:
                print(f"    进度: {i+1}/{len(test_problems)}, 当前准确率: {direct_correct}/{direct_total} ({direct_correct/direct_total*100:.1f}%)")

        direct_acc = direct_correct / direct_total * 100
        print(f"    Direct Answer 准确率: {direct_correct}/{direct_total} ({direct_acc:.1f}%)")
        results["direct"] = {"correct": direct_correct, "total": direct_total, "accuracy": direct_acc}

    # === 方式 2: Compile-time Solver ===
    if mode in ["compile", "both"]:
        print(f"\n  [2/2] Compile-time Solver...")
        # 用前 3 个问题做训练, 后面的做测试
        train_problems = test_problems[:3]
        eval_problems = test_problems[3:]

        fn, code = await compile_time_solver(model, train_problems, usda_report)

        if fn is not None:
            compile_correct = 0
            compile_total = 0
            compile_errors = 0
            for i, fruits in enumerate(eval_problems):
                gt_idx, gt_fruit = get_ground_truth(fruits)
                stats = {}
                for f in fruits:
                    s = STATS_2021[f]
                    yield_parts = s['yield'].split()
                    price_parts = s['price'].split()
                    stats[f] = {
                        'yield_val': float(yield_parts[0].replace(',', '')),
                        'yield_unit': yield_parts[1],
                        'price_val': float(price_parts[0].replace(',', '')),
                        'price_unit': price_parts[1],
                    }
                try:
                    pred_idx = fn(fruits, stats)
                    if pred_idx == gt_idx:
                        compile_correct += 1
                except Exception:
                    compile_errors += 1
                compile_total += 1

            compile_acc = compile_correct / compile_total * 100 if compile_total > 0 else 0
            print(f"    Compile-time 准确率: {compile_correct}/{compile_total} ({compile_acc:.1f}%), 错误: {compile_errors}")
            results["compile"] = {
                "correct": compile_correct, "total": compile_total,
                "accuracy": compile_acc, "errors": compile_errors,
                "code": code[:500] if code else None,
            }
        else:
            print(f"    Compile-time: Solver 生成失败")
            results["compile"] = {"correct": 0, "total": len(eval_problems), "accuracy": 0, "failed": True}

    # 随机基线
    random_acc = sum(1.0/len(fruits) for fruits in test_problems) / len(test_problems) * 100
    results["random_baseline"] = random_acc
    print(f"\n  随机基线: {random_acc:.1f}%")

    # 保存结果
    result_path = os.path.join(os.path.dirname(__file__), "results",
                                f"dellma_{model.replace('/', '_')}_{len(test_problems)}problems.json")
    os.makedirs(os.path.dirname(result_path), exist_ok=True)
    with open(result_path, 'w') as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    print(f"\n  结果保存: {result_path}")

    return results


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", default="openai/gpt-4o-mini", help="模型 ID")
    parser.add_argument("--n", type=int, default=20, help="问题数量")
    parser.add_argument("--mode", default="both", choices=["direct", "compile", "both"])
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    results = asyncio.run(run_experiment(args.model, args.n, args.mode, args.seed))

    print(f"\n{'='*60}")
    print(f"DeLLMa 实验结果汇总 — {args.model}")
    print(f"{'='*60}")
    if "direct" in results:
        print(f"  Direct Answer:     {results['direct']['accuracy']:.1f}%")
    if "compile" in results:
        print(f"  Compile-time:      {results['compile']['accuracy']:.1f}%")
    print(f"  Random Baseline:   {results['random_baseline']:.1f}%")
