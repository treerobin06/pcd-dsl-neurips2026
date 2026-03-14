#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Compile-time Matched Baseline 实验

与我们 DSL+Compiler 方案的公平对比：
- 两者都只在 compile time 使用 LLM（看 k=5 个样本）
- 两者都生成确定性 solver（test time 不调 LLM）
- Baseline 额外允许 self-repair（更宽松）

协议:
1. 选 k=5 个 train 样本（BN 按 depth 分层）
2. 让 frontier LLM 写通用 Python solver
3. Self-repair: 在 train 样本上测试 → 反馈错误 → 修复（最多 max_repairs 轮）
4. 最终 solver 在全 test set 上评测
5. 报告准确率 vs DSL+Compiler

用法:
  # BN 推断
  python run_compile_time_baseline.py --task bn --model openai/gpt-5.4

  # 偏好学习
  python run_compile_time_baseline.py --task preference --model openai/gpt-5.4

  # 两个任务
  python run_compile_time_baseline.py --task both --model openai/gpt-5.4 --max-repairs 5
"""

import os
import sys
import json
import re
import asyncio
import argparse
import csv
import subprocess
import tempfile
import random
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
FLIGHT_DATA = PROJECT_ROOT / "bayes" / "data" / "eval" / "interaction" / "flight.jsonl"
BLIND_DATA = PROJECT_ROOT / "BLInD" / "datasets" / "Base_1000_examples.csv"
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
        http_client=httpx.AsyncClient(proxy=proxy, timeout=300),
    )


# ==========================================
# 代码执行
# ==========================================
def execute_python_code(code: str, timeout: int = 60) -> Tuple[bool, str, str]:
    """安全执行 Python 代码，返回 (success, stdout, stderr)"""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False, encoding="utf-8") as f:
        f.write(code)
        tmp_path = f.name
    try:
        result = subprocess.run(
            [sys.executable, tmp_path],
            capture_output=True, text=True, timeout=timeout,
            env={
                "PATH": os.environ.get("PATH", ""),
                "PYTHONPATH": "",
                "SYSTEMROOT": os.environ.get("SYSTEMROOT", ""),
                "TEMP": os.environ.get("TEMP", ""),
                "TMP": os.environ.get("TMP", ""),
            },
        )
        return result.returncode == 0, result.stdout.strip(), result.stderr.strip()
    except subprocess.TimeoutExpired:
        return False, "", "TIMEOUT (exceeded 60s)"
    except Exception as e:
        return False, "", str(e)
    finally:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass


def extract_code_block(response: str) -> str:
    """从 LLM 响应中提取 Python 代码块"""
    pattern = r"```(?:python)?\s*\n(.*?)```"
    matches = re.findall(pattern, response, re.DOTALL)
    if matches:
        # 取最长的代码块（通常是完整实现）
        return max(matches, key=len).strip()
    if "def solve" in response or "import " in response:
        return response.strip()
    return ""


# ==========================================
# BN 任务: Compile-time Baseline
# ==========================================

def load_bn_data() -> List[Dict]:
    """加载 BLInD 数据"""
    with open(BLIND_DATA, encoding="utf-8") as f:
        return list(csv.DictReader(f))


def select_bn_train_examples(rows: List[Dict], k: int = 5) -> List[Dict]:
    """按 depth 分层选 k 个训练样本"""
    by_depth = {}
    for r in rows:
        d = int(r.get("depth", 2))
        if d not in by_depth:
            by_depth[d] = []
        by_depth[d].append(r)

    # 从 depth 2-6 各选 1 个（覆盖简单到中等）
    selected = []
    for d in sorted(by_depth.keys())[:k]:
        selected.append(random.choice(by_depth[d]))
    # 不够 k 个则补充
    while len(selected) < k:
        remaining = [r for r in rows if r not in selected]
        selected.append(random.choice(remaining))
    return selected[:k]


def build_bn_compile_prompt(train_examples: List[Dict]) -> str:
    """构建 BN compile-time baseline 的 prompt"""
    examples_str = ""
    for i, ex in enumerate(train_examples):
        examples_str += f"""
--- Example {i+1} (depth={ex.get('depth', '?')}) ---
context: \"\"\"{ex['contexts']}\"\"\"
graph: \"{ex['graph']}\"
query: \"{ex['query']}\"
correct_answer: {ex['answers']}
"""

    return f"""You are an expert programmer. Your task is to write a SINGLE Python function that can solve ANY Bayesian Network conditional probability problem in the format below.

## Task Description

Each problem has:
- `context`: Natural language CPT descriptions, e.g., "If X is True, then Y is True with probability of 70%..."
- `graph`: DAG structure, e.g., "('X',) -> Y | () -> X" (means X is parent of Y, X has no parents)
- `query`: A conditional probability query, e.g., "What is the probability that Y is True given that X is False?"

The function must:
1. Parse the natural language context to extract CPTs (conditional probability tables)
2. Parse the graph to extract the DAG structure (parent-child relationships)
3. Parse the query to extract the query variable, query value, and evidence
4. Compute the EXACT conditional probability using variable elimination or equivalent
5. Return a float

## Examples
{examples_str}

## Requirements

Write a complete, self-contained Python script that:
1. Defines `def solve(context: str, graph: str, query: str) -> float`
2. Handles any number of variables and any DAG depth
3. Only uses Python stdlib (no numpy/scipy/pgmpy — everything from scratch)
4. At the end, prints the results of running solve() on each example above, one per line (just the number)

The function must handle:
- Variables named like n0, n1, n2, ...
- Binary variables (True/False)
- Probabilities given as percentages ("39%") or decimals
- Evidence conditions ("given that X is True")
- Marginal queries (no evidence)

Write the COMPLETE code now:"""


def build_bn_repair_prompt(code: str, errors: List[Dict]) -> str:
    """构建 BN self-repair prompt"""
    error_str = ""
    for e in errors:
        error_str += f"""
Example (depth={e.get('depth', '?')}):
  context: "{e['context'][:200]}..."
  query: "{e['query']}"
  expected: {e['expected']}
  got: {e.get('got', 'ERROR')}
  error: {e.get('error', 'wrong answer')}
"""

    return f"""Your previous solver code had errors on some examples:

## Errors
{error_str}

## Your Previous Code
```python
{code}
```

Please fix the code. Output the COMPLETE fixed Python script (not just the diff).
The script should still define `solve(context, graph, query) -> float` and print results for the test examples at the end."""


def build_bn_test_harness(solver_code: str, test_rows: List[Dict]) -> str:
    """构建 BN 测试代码：solver + 批量测试"""
    # 提取 solve 函数（去掉末尾的测试代码）
    lines = solver_code.split("\n")
    # 找到 solve 函数定义及其之后所有的函数/类定义
    func_lines = []
    in_function = False
    for line in lines:
        # 跳过 if __name__ == "__main__" 块和末尾测试代码
        if line.strip().startswith("if __name__"):
            break
        if line.strip().startswith("# Test") or line.strip().startswith("# Run"):
            # 可能是测试代码的开始
            if not line.strip().startswith("# Run solve") and "def " not in line:
                # 检查后面是否是测试调用
                pass
        func_lines.append(line)

    # 去掉末尾的直接调用（print(solve(...)...)）
    while func_lines and func_lines[-1].strip().startswith(("print(", "result", "answer")):
        func_lines.pop()
    while func_lines and not func_lines[-1].strip():
        func_lines.pop()

    solver_only = "\n".join(func_lines)

    # 序列化测试数据
    test_data = []
    for r in test_rows:
        test_data.append({
            "context": r["contexts"],
            "graph": r["graph"],
            "query": r["query"],
            "answer": float(r["answers"]),
            "depth": int(r.get("depth", 0)),
        })

    harness = f"""{solver_only}

import json, sys

test_data = json.loads('''{json.dumps(test_data)}''')

results = []
for i, td in enumerate(test_data):
    try:
        pred = solve(td["context"], td["graph"], td["query"])
        pred = float(pred)
        err = abs(pred - td["answer"])
        results.append({{"idx": i, "pred": pred, "gold": td["answer"], "depth": td["depth"], "correct": err < 0.01, "error": err}})
    except Exception as e:
        results.append({{"idx": i, "pred": None, "gold": td["answer"], "depth": td["depth"], "correct": False, "error": str(e)}})

print(json.dumps(results))
"""
    return harness


# ==========================================
# 偏好学习任务: Compile-time Baseline
# ==========================================

def load_preference_data() -> List[Dict]:
    """加载 Flight 偏好数据"""
    with open(FLIGHT_DATA, encoding="utf-8") as f:
        return [json.loads(line) for line in f]


def select_preference_train_examples(samples: List[Dict], k: int = 5) -> List[Dict]:
    """随机选 k 个训练样本"""
    return random.sample(samples, min(k, len(samples)))


def format_preference_example(sample: Dict, idx: int) -> str:
    """格式化一个偏好学习样本作为 compile-time 训练示例"""
    features = sample["features"]
    rounds = sample["rounds"]
    rounds_numpy = sample["rounds_numpy"]
    n_features = len(features)

    lines = [f"--- Example {idx+1} ---"]
    lines.append(f"features: {features}")
    lines.append(f"preference_values: [-1.0, -0.5, 0.0, 0.5, 1.0]")
    lines.append(f"true_weights: {sample.get('reward_fn', 'hidden')}")
    lines.append("")

    # R1-R4 历史
    for r_idx in range(min(len(rounds) - 1, 4)):
        r = rounds[r_idx]
        opts = rounds_numpy[r_idx]
        chosen = r["user_idx"]
        lines.append(f"Round {r_idx + 1}:")
        for o_idx, opt in enumerate(opts):
            opt_str = ", ".join(f"{features[j]}={opt[j]:.2f}" for j in range(n_features))
            marker = " <-- USER CHOSE" if o_idx == chosen else ""
            lines.append(f"  Option {o_idx}: [{opt_str}]{marker}")

    # R5 选项
    last_round = rounds_numpy[len(rounds) - 1]
    lines.append(f"\nRound 5 (predict):")
    for o_idx, opt in enumerate(last_round):
        opt_str = ", ".join(f"{features[j]}={opt[j]:.2f}" for j in range(n_features))
        lines.append(f"  Option {o_idx}: [{opt_str}]")

    # 正确答案（使用 gold solver）
    from solvers.preference_solver import PreferenceSolver
    solver = PreferenceSolver(feature_dim=n_features, preference_values=[-1.0, -0.5, 0.0, 0.5, 1.0], temperature=1.0)
    for r_idx in range(min(len(rounds) - 1, 4)):
        r = rounds[r_idx]
        solver.update(r["user_idx"], rounds_numpy[r_idx])
    gold_rec = solver.recommend(last_round)
    lines.append(f"\ncorrect_recommendation: Option {gold_rec}")

    return "\n".join(lines)


def build_preference_compile_prompt(train_examples: List[Dict]) -> str:
    """构建偏好学习 compile-time baseline 的 prompt"""
    examples_str = ""
    for i, ex in enumerate(train_examples):
        examples_str += format_preference_example(ex, i) + "\n\n"

    return f"""You are an expert programmer. Your task is to write a Python function that solves Bayesian preference learning problems.

## Task Description

A user has hidden linear preference weights over features. Each weight is drawn from [-1.0, -0.5, 0.0, 0.5, 1.0].
The user sees 3 options per round and picks the one maximizing their weighted sum (with softmax noise, temperature=1.0).

Given R1-R4 history (which option the user chose), predict the best option for R5 using Bayesian posterior inference:
1. Start with uniform prior over all possible weight vectors (5^n_features hypotheses)
2. For each round, update posterior: P(w|choice) ∝ P(choice|w) * P(w)
   where P(choice=i|w) = softmax(EU_i / temperature) and EU_i = w · features_i
3. For R5, compute expected utility of each option under the posterior
4. Recommend the option with highest expected utility

## Examples
{examples_str}

## Requirements

Write a complete, self-contained Python script that:
1. Defines `def solve(features, rounds_history, current_options) -> int`
   - features: list of feature names (e.g., ["departure_time", "duration", "number_of_stops", "price"])
   - rounds_history: list of dicts, each with "options" (list of 3 feature vectors as lists) and "chosen_idx" (int)
   - current_options: list of 3 feature vectors as lists
   - Returns: int (0, 1, or 2) — the recommended option index
2. Implements full Bayesian posterior update with enumeration over all hypotheses
3. Only uses Python stdlib + math (no numpy/scipy)
4. At the end, tests on the examples above and prints the recommended option for each

Write the COMPLETE code now:"""


def build_preference_test_harness(solver_code: str, test_samples: List[Dict]) -> str:
    """构建偏好学习测试代码"""
    # 提取 solver 函数部分
    lines = solver_code.split("\n")
    func_lines = []
    for line in lines:
        if line.strip().startswith("if __name__"):
            break
        func_lines.append(line)
    while func_lines and func_lines[-1].strip().startswith(("print(", "result", "answer", "test")):
        func_lines.pop()
    while func_lines and not func_lines[-1].strip():
        func_lines.pop()
    solver_only = "\n".join(func_lines)

    # 准备测试数据
    test_data = []
    from solvers.preference_solver import PreferenceSolver
    for s in test_samples:
        features = s["features"]
        rounds = s["rounds"]
        rounds_numpy = s["rounds_numpy"]
        n_features = len(features)

        # 构建历史
        history = []
        for r_idx in range(min(len(rounds) - 1, 4)):
            r = rounds[r_idx]
            opts = rounds_numpy[r_idx]
            history.append({
                "options": [[round(v, 4) for v in opt] for opt in opts],
                "chosen_idx": r["user_idx"],
            })

        # 当前选项
        current = [[round(v, 4) for v in opt] for opt in rounds_numpy[len(rounds) - 1]]

        # Gold 答案
        solver = PreferenceSolver(feature_dim=n_features, preference_values=[-1.0, -0.5, 0.0, 0.5, 1.0], temperature=1.0)
        for r_idx in range(min(len(rounds) - 1, 4)):
            solver.update(rounds[r_idx]["user_idx"], rounds_numpy[r_idx])
        gold_rec = solver.recommend(rounds_numpy[len(rounds) - 1])

        test_data.append({
            "features": features,
            "history": history,
            "current": current,
            "gold": gold_rec,
        })

    harness = f"""{solver_only}

import json, sys

test_data = json.loads('''{json.dumps(test_data)}''')

results = []
for i, td in enumerate(test_data):
    try:
        pred = solve(td["features"], td["history"], td["current"])
        pred = int(pred)
        results.append({{"idx": i, "pred": pred, "gold": td["gold"], "correct": pred == td["gold"]}})
    except Exception as e:
        results.append({{"idx": i, "pred": None, "gold": td["gold"], "correct": False, "error": str(e)}})

print(json.dumps(results))
"""
    return harness


# ==========================================
# 通用: Compile + Self-Repair 循环
# ==========================================

async def compile_and_repair(
    client: AsyncOpenAI,
    model: str,
    task_name: str,
    compile_prompt: str,
    train_examples: List[Dict],
    build_repair_fn,
    validate_fn,
    max_repairs: int = 5,
) -> Tuple[str, List[Dict]]:
    """
    Compile-time 编译 + self-repair 循环

    Returns: (final_code, repair_history)
    """
    print(f"\n  [Compile] 请求 {model} 编写 {task_name} solver...")
    history = []

    # 第一次编译
    resp = await client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": compile_prompt}],
        max_tokens=16384,
        temperature=0.0,
    )
    code = extract_code_block(resp.choices[0].message.content or "")
    if not code:
        code = resp.choices[0].message.content or ""
    print(f"    生成代码: {len(code)} 字符")

    # 在训练样本上验证
    errors = validate_fn(code, train_examples)
    n_correct = sum(1 for e in errors if e.get("correct", False))
    n_total = len(errors)
    print(f"    训练集验证: {n_correct}/{n_total} 正确")
    history.append({"round": 0, "code_len": len(code), "train_correct": n_correct, "train_total": n_total})

    # Self-repair 循环
    messages = [
        {"role": "user", "content": compile_prompt},
        {"role": "assistant", "content": resp.choices[0].message.content or ""},
    ]

    for repair_round in range(1, max_repairs + 1):
        if n_correct == n_total:
            print(f"    训练集全对，跳过 repair")
            break

        wrong = [e for e in errors if not e.get("correct", False)]
        print(f"\n  [Repair {repair_round}/{max_repairs}] {len(wrong)} 个错误...")

        repair_prompt = build_repair_fn(code, wrong)
        messages.append({"role": "user", "content": repair_prompt})

        resp = await client.chat.completions.create(
            model=model,
            messages=messages,
            max_tokens=16384,
            temperature=0.0,
        )
        new_code = extract_code_block(resp.choices[0].message.content or "")
        if new_code:
            code = new_code

        messages.append({"role": "assistant", "content": resp.choices[0].message.content or ""})

        errors = validate_fn(code, train_examples)
        n_correct = sum(1 for e in errors if e.get("correct", False))
        print(f"    修复后验证: {n_correct}/{n_total} 正确")
        history.append({"round": repair_round, "code_len": len(code), "train_correct": n_correct, "train_total": n_total})

    return code, history


# 全局缓存最终 solver 代码
_final_codes = {}


# ==========================================
# BN: 验证函数
# ==========================================

def validate_bn_on_train(code: str, train_examples: List[Dict]) -> List[Dict]:
    """在训练样本上验证 BN solver"""
    # 构建测试 harness
    harness = build_bn_test_harness(code, train_examples)
    success, stdout, stderr = execute_python_code(harness, timeout=120)

    if not success:
        # 代码执行失败
        return [{
            "context": ex["contexts"][:200],
            "query": ex["query"],
            "expected": float(ex["answers"]),
            "depth": int(ex.get("depth", 0)),
            "got": "EXECUTION_ERROR",
            "error": stderr[:500],
            "correct": False,
        } for ex in train_examples]

    try:
        results = json.loads(stdout)
        # 把原始数据信息加回来
        for r, ex in zip(results, train_examples):
            r["context"] = ex["contexts"][:200]
            r["query"] = ex["query"]
            r["expected"] = float(ex["answers"])
            r["depth"] = int(ex.get("depth", 0))
        return results
    except json.JSONDecodeError:
        return [{
            "context": ex["contexts"][:200],
            "query": ex["query"],
            "expected": float(ex["answers"]),
            "depth": int(ex.get("depth", 0)),
            "got": "PARSE_ERROR",
            "error": f"Cannot parse output: {stdout[:200]}",
            "correct": False,
        } for ex in train_examples]


def validate_preference_on_train(code: str, train_examples: List[Dict]) -> List[Dict]:
    """在训练样本上验证偏好学习 solver"""
    harness = build_preference_test_harness(code, train_examples)
    success, stdout, stderr = execute_python_code(harness, timeout=120)

    if not success:
        return [{
            "expected": "?",
            "got": "EXECUTION_ERROR",
            "error": stderr[:500],
            "correct": False,
        } for _ in train_examples]

    try:
        results = json.loads(stdout)
        return results
    except json.JSONDecodeError:
        return [{
            "expected": "?",
            "got": "PARSE_ERROR",
            "error": f"Cannot parse output: {stdout[:200]}",
            "correct": False,
        } for _ in train_examples]


# ==========================================
# BN: 修复提示构建
# ==========================================

def build_bn_repair(code: str, errors: List[Dict]) -> str:
    """构建 BN 修复提示"""
    error_lines = []
    for e in errors[:5]:  # 最多展示 5 个错误
        error_lines.append(f"""
  depth={e.get('depth', '?')}:
    query: "{e.get('query', '?')}"
    expected: {e.get('expected', '?')}
    got: {e.get('got', e.get('pred', 'ERROR'))}
    error: {e.get('error', 'wrong answer')}""")

    return f"""Your solver has errors on {len(errors)} examples. Here are some:
{"".join(error_lines)}

Your current code:
```python
{code}
```

Fix the code. Common issues:
- Incorrect CPT parsing (percentages vs decimals, conditional vs marginal)
- Edge direction parsing in graph format
- Variable elimination implementation bugs
- Evidence handling

Output the COMPLETE fixed Python script."""


def build_preference_repair(code: str, errors: List[Dict]) -> str:
    """构建偏好学习修复提示"""
    error_lines = []
    for e in errors[:5]:
        error_lines.append(f"""
  expected: Option {e.get('gold', '?')}, got: Option {e.get('pred', 'ERROR')}
  error: {e.get('error', 'wrong recommendation')}""")

    return f"""Your solver has errors on {len(errors)} examples:
{"".join(error_lines)}

Your current code:
```python
{code}
```

Fix the code. Common issues:
- Hypothesis enumeration missing some weight combinations
- Softmax computation errors (overflow/underflow)
- Expected utility calculation bugs
- Prior update logic

Output the COMPLETE fixed Python script."""


# ==========================================
# 主实验逻辑
# ==========================================

async def run_bn_compile_time(model: str, max_repairs: int, k_examples: int, n_test: int) -> Dict:
    """运行 BN compile-time baseline"""
    rows = load_bn_data()
    if n_test > 0:
        test_rows = rows[:n_test]
    else:
        test_rows = rows

    # 选训练样本（从测试集外选，或就从全集选——因为 solver 是通用的，训练集只用于验证）
    train = select_bn_train_examples(rows, k=k_examples)

    print(f"\n{'='*60}")
    print(f"Compile-time Baseline: BN 推断 (BLInD)")
    print(f"模型: {model}, 训练: {len(train)}, 测试: {len(test_rows)}, 最大修复: {max_repairs}")
    print(f"训练样本 depth: {[int(t.get('depth', 0)) for t in train]}")
    print(f"{'='*60}")

    client = get_client()

    # 编译 + 修复
    compile_prompt = build_bn_compile_prompt(train)
    final_code, repair_history = await compile_and_repair(
        client, model, "BN",
        compile_prompt, train,
        build_bn_repair,
        validate_bn_on_train,
        max_repairs=max_repairs,
    )

    _final_codes["bn"] = final_code

    # 在全测试集上评测
    print(f"\n  [Test] 在 {len(test_rows)} 个测试样本上评测...")
    batch_size = 100
    all_results = []
    for batch_start in range(0, len(test_rows), batch_size):
        batch = test_rows[batch_start:batch_start + batch_size]
        harness = build_bn_test_harness(final_code, batch)
        success, stdout, stderr = execute_python_code(harness, timeout=300)

        if success:
            try:
                batch_results = json.loads(stdout)
                # 修正 idx
                for r in batch_results:
                    r["idx"] += batch_start
                all_results.extend(batch_results)
            except json.JSONDecodeError:
                for i, r in enumerate(batch):
                    all_results.append({"idx": batch_start + i, "pred": None, "gold": float(r["answers"]),
                                        "depth": int(r.get("depth", 0)), "correct": False, "error": "json_parse"})
        else:
            for i, r in enumerate(batch):
                all_results.append({"idx": batch_start + i, "pred": None, "gold": float(r["answers"]),
                                    "depth": int(r.get("depth", 0)), "correct": False, "error": stderr[:200]})
        print(f"    batch {batch_start}-{batch_start+len(batch)}: {sum(1 for r in all_results[batch_start:] if r.get('correct', False))}/{len(batch)} 正确")

    # 汇总
    total_correct = sum(1 for r in all_results if r.get("correct", False))
    total = len(all_results)
    overall_acc = total_correct / total if total > 0 else 0

    # 按 depth 统计
    depth_stats = {}
    for r in all_results:
        d = r.get("depth", 0)
        if d not in depth_stats:
            depth_stats[d] = {"total": 0, "correct": 0}
        depth_stats[d]["total"] += 1
        if r.get("correct", False):
            depth_stats[d]["correct"] += 1

    print(f"\n  总体准确率: {overall_acc*100:.1f}% ({total_correct}/{total})")
    print(f"  按 depth:")
    for d in sorted(depth_stats.keys()):
        s = depth_stats[d]
        dacc = s["correct"] / s["total"] if s["total"] > 0 else 0
        print(f"    depth={d}: {dacc*100:.1f}% ({s['correct']}/{s['total']})")

    return {
        "task": "bn",
        "model": model,
        "method": "compile_time_baseline",
        "k_examples": k_examples,
        "max_repairs": max_repairs,
        "n_test": total,
        "overall_accuracy": overall_acc,
        "depth_stats": {str(k): v for k, v in depth_stats.items()},
        "repair_history": repair_history,
        "final_code_length": len(final_code),
        "results": all_results,
    }


async def run_preference_compile_time(model: str, max_repairs: int, k_examples: int, n_test: int) -> Dict:
    """运行偏好学习 compile-time baseline"""
    samples = load_preference_data()
    if n_test > 0:
        test_samples = samples[:n_test]
    else:
        test_samples = samples

    train = select_preference_train_examples(samples, k=k_examples)

    print(f"\n{'='*60}")
    print(f"Compile-time Baseline: 偏好学习 (Flight)")
    print(f"模型: {model}, 训练: {len(train)}, 测试: {len(test_samples)}, 最大修复: {max_repairs}")
    print(f"{'='*60}")

    client = get_client()

    compile_prompt = build_preference_compile_prompt(train)
    final_code, repair_history = await compile_and_repair(
        client, model, "Preference",
        compile_prompt, train,
        build_preference_repair,
        validate_preference_on_train,
        max_repairs=max_repairs,
    )

    _final_codes["preference"] = final_code

    # 在全测试集上评测
    print(f"\n  [Test] 在 {len(test_samples)} 个测试样本上评测...")
    batch_size = 50
    all_results = []
    for batch_start in range(0, len(test_samples), batch_size):
        batch = test_samples[batch_start:batch_start + batch_size]
        harness = build_preference_test_harness(final_code, batch)
        success, stdout, stderr = execute_python_code(harness, timeout=300)

        if success:
            try:
                batch_results = json.loads(stdout)
                for r in batch_results:
                    r["idx"] += batch_start
                all_results.extend(batch_results)
            except json.JSONDecodeError:
                for i in range(len(batch)):
                    all_results.append({"idx": batch_start + i, "pred": None, "gold": -1, "correct": False, "error": "json_parse"})
        else:
            for i in range(len(batch)):
                all_results.append({"idx": batch_start + i, "pred": None, "gold": -1, "correct": False, "error": stderr[:200]})
        n_batch_correct = sum(1 for r in all_results[batch_start:] if r.get("correct", False))
        print(f"    batch {batch_start}-{batch_start+len(batch)}: {n_batch_correct}/{len(batch)} 正确")

    total_correct = sum(1 for r in all_results if r.get("correct", False))
    total = len(all_results)
    overall_acc = total_correct / total if total > 0 else 0

    print(f"\n  总体准确率: {overall_acc*100:.1f}% ({total_correct}/{total})")

    return {
        "task": "preference",
        "model": model,
        "method": "compile_time_baseline",
        "k_examples": k_examples,
        "max_repairs": max_repairs,
        "n_test": total,
        "overall_accuracy": overall_acc,
        "repair_history": repair_history,
        "final_code_length": len(final_code),
        "results": all_results,
    }


async def main():
    parser = argparse.ArgumentParser(description="Compile-time Matched Baseline")
    parser.add_argument("--task", choices=["bn", "preference", "both"], default="both")
    parser.add_argument("--model", "-m", default="openai/gpt-5.4")
    parser.add_argument("--max-repairs", type=int, default=5, help="最大 self-repair 轮数")
    parser.add_argument("--k", type=int, default=5, help="训练样本数")
    parser.add_argument("--n", type=int, default=0, help="测试样本数 (0=全部)")
    parser.add_argument("--seed", type=int, default=42, help="随机种子")
    args = parser.parse_args()

    random.seed(args.seed)
    np.random.seed(args.seed)
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)

    all_results = {}

    if args.task in ("bn", "both"):
        result = await run_bn_compile_time(args.model, args.max_repairs, args.k, args.n)
        all_results["bn"] = result

    if args.task in ("preference", "both"):
        result = await run_preference_compile_time(args.model, args.max_repairs, args.k, args.n)
        all_results["preference"] = result

    # 保存结果
    model_tag = args.model.replace("/", "_")
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_file = RESULTS_DIR / f"compile_time_{model_tag}_{ts}.json"

    # 保存时去掉巨大的 results 列表到单独文件
    summary = {}
    for task_name, result in all_results.items():
        details = result.pop("results", [])
        summary[task_name] = result
        detail_file = RESULTS_DIR / f"compile_time_{model_tag}_{task_name}_{ts}_details.json"
        with open(detail_file, "w", encoding="utf-8") as f:
            json.dump(details, f, indent=2, ensure_ascii=False, default=str)
        print(f"\n详细结果: {detail_file}")

    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False, default=str)
    print(f"汇总结果: {out_file}")

    # 保存最终 solver 代码
    for task_name in all_results:
        if task_name in _final_codes:
            code_file = RESULTS_DIR / f"compile_time_{model_tag}_{task_name}_{ts}_solver.py"
            with open(code_file, "w", encoding="utf-8") as f:
                f.write(_final_codes[task_name])
            print(f"  {task_name} solver 代码: {code_file}")

    # 汇总表
    print(f"\n{'='*60}")
    print(f"Compile-time Matched Baseline — 最终汇总")
    print(f"{'='*60}")
    print(f"模型: {args.model}, 训练样本: {args.k}, 最大修复: {args.max_repairs}\n")

    # 对比表
    print(f"{'任务':<15} {'Compile-time BL':>15} {'Our DSL':>10} {'PAL (per-inst)':>15}")
    print(f"{'-'*60}")
    for task_name, result in all_results.items():
        ct_acc = result["overall_accuracy"] * 100
        # 已知数据
        if task_name == "bn":
            dsl_acc = 100.0
            pal_acc = 26.4
        else:
            dsl_acc = 74.8
            pal_acc = 29.3
        print(f"{task_name:<15} {ct_acc:>14.1f}% {dsl_acc:>9.1f}% {pal_acc:>14.1f}%")


if __name__ == "__main__":
    asyncio.run(main())
