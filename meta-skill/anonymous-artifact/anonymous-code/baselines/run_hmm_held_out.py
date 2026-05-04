#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Held-out Inference Family 实验 — Hidden Markov Model (HMM) Forward Filtering

验证目标: DSL core ops 能否泛化到一个 genuinely different inference family。
HMM 的 forward algorithm 用 iterated (multiply + marginalize) 实现，
与现有 3 个 macro（hypothesis_enumeration, conjugate_update, variable_elimination）
在计算结构上真正不同：它需要 sequential temporal reasoning。

实验条件:
  A. Direct Answer — LLM 直接给出最可能的隐藏状态
  B. Compile-time Free Code — LLM 写自由 Python solver
  C. Core-ops Constrained — LLM 写 solver 但只能用 DSL core ops
  D. PCD 诊断 — Parse/Compute/Decide 分阶段测试

用法:
  python run_hmm_held_out.py --model openai/gpt-4o-mini --n 105
  python run_hmm_held_out.py --model openai/gpt-5.4 --n 105 --mode all
"""

import os
import sys
import json
import math
import random
import asyncio
import argparse
import subprocess
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Tuple
from datetime import datetime

# 修复 Windows 控制台编码
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

import httpx
from openai import AsyncOpenAI

SCRIPT_DIR = Path(__file__).parent
RESULTS_DIR = SCRIPT_DIR / "results"


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
# 数据生成: HMM Forward Filtering
# ==========================================

# 状态和观测名称库（有语义意义，方便 LLM 理解）
STATE_THEMES = [
    {
        "name": "Weather",
        "states": ["Sunny", "Cloudy", "Rainy"],
        "observations": ["Umbrella", "No_Umbrella", "Sunglasses"],
    },
    {
        "name": "Health",
        "states": ["Healthy", "Fever", "Flu"],
        "observations": ["Normal_Temp", "High_Temp", "Cough", "No_Symptoms"],
    },
    {
        "name": "Market",
        "states": ["Bull", "Bear", "Stable"],
        "observations": ["Up", "Down", "Flat", "Volatile"],
    },
    {
        "name": "Mood",
        "states": ["Happy", "Neutral", "Sad", "Anxious"],
        "observations": ["Smiling", "Quiet", "Crying", "Restless", "Normal"],
    },
    {
        "name": "Traffic",
        "states": ["Free_Flow", "Moderate", "Congested"],
        "observations": ["Fast", "Slow", "Stopped", "Normal_Speed"],
    },
]


def generate_hmm_problem(
    n_states: int = 3,
    n_obs: int = 3,
    seq_length: int = 5,
    seed: int = 0,
) -> Dict[str, Any]:
    """生成一个 HMM forward filtering 问题"""
    rng = random.Random(seed)

    # 选择主题或生成通用名称
    theme = rng.choice(STATE_THEMES)
    states = theme["states"][:n_states]
    if len(states) < n_states:
        states = [f"S{i}" for i in range(n_states)]
    observations = theme["observations"][:n_obs]
    if len(observations) < n_obs:
        observations = [f"O{i}" for i in range(n_obs)]

    # 初始分布 π
    raw_pi = [rng.uniform(0.1, 1.0) for _ in range(n_states)]
    total = sum(raw_pi)
    initial_dist = {s: round(p / total, 4) for s, p in zip(states, raw_pi)}

    # 转移矩阵 A[from_state][to_state]
    transition = {}
    for s_from in states:
        raw = [rng.uniform(0.05, 1.0) for _ in range(n_states)]
        total = sum(raw)
        transition[s_from] = {s_to: round(p / total, 4) for s_to, p in zip(states, raw)}

    # 发射矩阵 B[state][observation]
    emission = {}
    for s in states:
        raw = [rng.uniform(0.05, 1.0) for _ in range(n_obs)]
        total = sum(raw)
        emission[s] = {o: round(p / total, 4) for o, p in zip(observations, raw)}

    # 生成观测序列
    # 先采样真实隐藏状态序列
    true_states = []
    current = rng.choices(states, weights=[initial_dist[s] for s in states])[0]
    true_states.append(current)

    for _ in range(seq_length - 1):
        weights = [transition[current][s] for s in states]
        current = rng.choices(states, weights=weights)[0]
        true_states.append(current)

    # 从隐藏状态采样观测
    obs_sequence = []
    for t_state in true_states:
        weights = [emission[t_state][o] for o in observations]
        obs = rng.choices(observations, weights=weights)[0]
        obs_sequence.append(obs)

    # Gold answer: Forward algorithm 计算 P(last state | observations)
    gold_posterior = forward_algorithm(
        states, observations, initial_dist, transition, emission, obs_sequence
    )
    gold_state = max(gold_posterior, key=gold_posterior.get)

    return {
        "theme": theme["name"],
        "states": states,
        "observations": observations,
        "initial_dist": initial_dist,
        "transition": transition,
        "emission": emission,
        "obs_sequence": obs_sequence,
        "true_states": true_states,
        "gold_state": gold_state,
        "gold_posterior": {s: round(p, 6) for s, p in gold_posterior.items()},
        "n_states": n_states,
        "n_obs": n_obs,
        "seq_length": seq_length,
        "seed": seed,
    }


def forward_algorithm(
    states: List[str],
    observations: List[str],
    initial_dist: Dict[str, float],
    transition: Dict[str, Dict[str, float]],
    emission: Dict[str, Dict[str, float]],
    obs_sequence: List[str],
) -> Dict[str, float]:
    """HMM Forward Algorithm — 计算 P(last state | observations)

    使用 DSL 概念实现：iterated (multiply + marginalize + normalize)
    """
    # 初始化: alpha[s] = pi(s) * B(s, obs[0])
    alpha = {}
    for s in states:
        alpha[s] = initial_dist.get(s, 0) * emission.get(s, {}).get(obs_sequence[0], 0)

    # 归一化避免下溢
    total = sum(alpha.values())
    if total > 0:
        alpha = {s: p / total for s, p in alpha.items()}

    # 前向传播
    for t in range(1, len(obs_sequence)):
        new_alpha = {}
        for s_to in states:
            # 求和: sum_s_from alpha[s_from] * A[s_from][s_to]
            prob = sum(
                alpha.get(s_from, 0) * transition.get(s_from, {}).get(s_to, 0)
                for s_from in states
            )
            # 乘以发射概率
            prob *= emission.get(s_to, {}).get(obs_sequence[t], 0)
            new_alpha[s_to] = prob

        # 归一化
        total = sum(new_alpha.values())
        if total > 0:
            new_alpha = {s: p / total for s, p in new_alpha.items()}
        alpha = new_alpha

    return alpha


def format_hmm_natural_language(problem: Dict) -> str:
    """将 HMM 问题格式化为自然语言"""
    lines = []
    lines.append(f"You are analyzing a Hidden Markov Model about {problem['theme']}.\n")

    lines.append(f"## Hidden States: {', '.join(problem['states'])}")
    lines.append(f"## Observable Signals: {', '.join(problem['observations'])}\n")

    lines.append("## Initial State Probabilities")
    for s, p in problem["initial_dist"].items():
        lines.append(f"  - P({s}) = {p}")

    lines.append("\n## State Transition Probabilities")
    for s_from in problem["states"]:
        for s_to in problem["states"]:
            p = problem["transition"][s_from][s_to]
            lines.append(f"  - P({s_to} | previous={s_from}) = {p}")

    lines.append("\n## Emission Probabilities")
    for s in problem["states"]:
        for o in problem["observations"]:
            p = problem["emission"][s][o]
            lines.append(f"  - P(observe {o} | state={s}) = {p}")

    lines.append(f"\n## Observed Sequence (length {len(problem['obs_sequence'])})")
    for i, obs in enumerate(problem["obs_sequence"]):
        lines.append(f"  Time {i+1}: {obs}")

    return "\n".join(lines)


def generate_dataset(n_problems: int, seed: int = 42) -> List[Dict]:
    """生成完整数据集"""
    problems = []
    rng = random.Random(seed)

    for i in range(n_problems):
        n_s = rng.choice([3, 3, 4, 4, 5])
        n_o = rng.choice([3, 3, 4, 4, 5])
        seq_len = rng.choice([4, 5, 6, 7, 8])

        p = generate_hmm_problem(
            n_states=n_s,
            n_obs=n_o,
            seq_length=seq_len,
            seed=seed * 10000 + i,
        )
        p["problem_id"] = i
        problems.append(p)

    return problems


# ==========================================
# 条件 A: Direct Answer
# ==========================================

async def direct_answer(client: AsyncOpenAI, model: str, problem: Dict) -> Dict:
    """LLM 直接给出最可能的隐藏状态"""
    nl = format_hmm_natural_language(problem)
    prompt = f"""{nl}

## Task
Using the HMM Forward Algorithm, compute the probability distribution over the LAST hidden state given the full observed sequence.

The Forward Algorithm works as follows:
1. Initialize: alpha_1(s) = P(s) × P(obs_1 | s) for each state s
2. For each subsequent time step t:
   alpha_t(s) = P(obs_t | s) × sum_over_prev_states[ alpha_(t-1)(prev) × P(s | prev) ]
3. Normalize at each step to avoid numerical underflow
4. The final alpha values give P(last_state | all_observations)

**Output format**: Respond with ONLY a JSON object:
{{"most_likely_state": "StateName", "posterior": {{"State1": 0.xx, "State2": 0.xx, ...}}}}
"""
    try:
        resp = await client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=2048,
            temperature=0.0,
        )
        text = resp.choices[0].message.content.strip()
        import re
        m = re.search(r'\{.*\}', text, re.DOTALL)
        if m:
            result = json.loads(m.group())
            pred = result.get("most_likely_state", "")
            return {"prediction": pred, "raw": text, "error": None}
        return {"prediction": "", "raw": text, "error": "no_json"}
    except Exception as e:
        return {"prediction": "", "raw": "", "error": str(e)}


# ==========================================
# 条件 B/C: Compile-time Solver
# ==========================================

def execute_python_code(code: str, timeout: int = 60) -> Tuple[bool, str, str]:
    """安全执行 Python 代码"""
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
        return False, "", "TIMEOUT"
    except Exception as e:
        return False, "", str(e)
    finally:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass


def build_compile_prompt(train_problems: List[Dict], use_core_ops: bool = False) -> str:
    """构建 compile-time prompt"""
    examples = ""
    for i, p in enumerate(train_problems):
        examples += f"\n--- Example {i+1} ({p['n_states']} states, {p['n_obs']} observations, seq_len={p['seq_length']}) ---\n"
        examples += f"states: {p['states']}\n"
        examples += f"observations: {p['observations']}\n"
        examples += f"initial_dist: {json.dumps(p['initial_dist'])}\n"
        examples += f"transition: {json.dumps(p['transition'])}\n"
        examples += f"emission: {json.dumps(p['emission'])}\n"
        examples += f"obs_sequence: {p['obs_sequence']}\n"
        examples += f"correct_state: {p['gold_state']}\n"
        examples += f"correct_posterior: {json.dumps(p['gold_posterior'])}\n"

    core_ops_section = ""
    if use_core_ops:
        core_ops_section = """
## Available Core Operations (you MUST use these)

```python
def normalize(unnormalized: dict) -> dict:
    total = sum(unnormalized.values())
    return {k: v/total for k, v in unnormalized.items()} if total > 0 else unnormalized

def multiply_factors(factor_a: dict, factor_b: dict) -> dict:
    \"\"\"Element-wise multiply two dicts with same keys\"\"\"
    return {k: factor_a.get(k, 0) * factor_b.get(k, 0) for k in set(factor_a) | set(factor_b)}

def marginalize(joint: dict, sum_over_keys, transition_fn) -> dict:
    \"\"\"Marginalize: new[s_to] = sum_over_keys sum(joint[s_from] * transition_fn(s_from, s_to))\"\"\"
    result = {}
    for s_from, p_from in joint.items():
        for s_to, p_trans in transition_fn(s_from).items():
            result[s_to] = result.get(s_to, 0) + p_from * p_trans
    return result

def argmax(scores: dict) -> str:
    return max(scores, key=scores.get)
```

Your solver MUST use these operations. Do NOT implement your own probability calculations from scratch.
"""

    constraint = "only Python stdlib (no numpy/scipy)" if not use_core_ops else "ONLY the core operations defined above"

    return f"""You are an expert programmer. Write a Python function that solves HMM Forward Filtering problems.

## Task Description

Given a Hidden Markov Model with:
- A set of hidden states with initial probabilities
- A transition matrix P(next_state | current_state)
- An emission matrix P(observation | state)
- A sequence of observations

Compute the posterior P(last_hidden_state | all_observations) using the Forward Algorithm:
1. alpha_1(s) = P(s) * P(obs_1 | s), then normalize
2. For t = 2..T: alpha_t(s) = P(obs_t | s) * sum_prev[ alpha_(t-1)(prev) * P(s | prev) ], then normalize
3. Return the normalized final alpha as the posterior
{core_ops_section}
## Examples
{examples}

## Requirements

Write a complete Python script that:
1. Defines `def solve(states, initial_dist, transition, emission, obs_sequence) -> tuple`:
   - Returns: (most_likely_state: str, posterior: dict)
2. Uses {constraint}
3. Tests on examples above, printing results as JSON

Write the COMPLETE code now:"""


def extract_code_block(response: str) -> str:
    import re
    matches = re.findall(r"```(?:python)?\s*\n(.*?)```", response, re.DOTALL)
    if matches:
        return max(matches, key=len).strip()
    if "def solve" in response:
        return response.strip()
    return ""


def build_test_harness(solver_code: str, test_problems: List[Dict]) -> str:
    """构建测试 harness"""
    lines = solver_code.split("\n")
    func_lines = []
    for line in lines:
        if line.strip().startswith("if __name__"):
            break
        func_lines.append(line)
    while func_lines and func_lines[-1].strip().startswith(("print(", "result", "answer", "test", "#")):
        func_lines.pop()
    while func_lines and not func_lines[-1].strip():
        func_lines.pop()
    solver_only = "\n".join(func_lines)

    test_data = []
    for p in test_problems:
        test_data.append({
            "states": p["states"],
            "initial_dist": p["initial_dist"],
            "transition": p["transition"],
            "emission": p["emission"],
            "obs_sequence": p["obs_sequence"],
            "gold_state": p["gold_state"],
        })

    return f"""{solver_only}

import json, sys

test_data = json.loads('''{json.dumps(test_data)}''')

results = []
for i, td in enumerate(test_data):
    try:
        state, posterior = solve(td["states"], td["initial_dist"], td["transition"], td["emission"], td["obs_sequence"])
        results.append({{"idx": i, "pred": state, "gold": td["gold_state"], "correct": state == td["gold_state"]}})
    except Exception as e:
        results.append({{"idx": i, "pred": None, "gold": td["gold_state"], "correct": False, "error": str(e)}})

print(json.dumps(results))
"""


async def compile_time_solver(
    client: AsyncOpenAI,
    model: str,
    train_problems: List[Dict],
    test_problems: List[Dict],
    use_core_ops: bool = False,
    max_repairs: int = 3,
) -> Dict:
    mode_name = "core-ops" if use_core_ops else "free-code"
    print(f"\n  [Compile-time {mode_name}] 请求 {model} 编写 HMM solver...")

    prompt = build_compile_prompt(train_problems, use_core_ops=use_core_ops)

    resp = await client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        max_tokens=8192,
        temperature=0.0,
    )
    code = extract_code_block(resp.choices[0].message.content or "")
    if not code:
        code = resp.choices[0].message.content or ""

    print(f"    生成代码: {len(code)} 字符")

    messages = [
        {"role": "user", "content": prompt},
        {"role": "assistant", "content": resp.choices[0].message.content or ""},
    ]

    for repair_round in range(max_repairs):
        harness = build_test_harness(code, train_problems)
        success, stdout, stderr = execute_python_code(harness, timeout=60)

        if success:
            try:
                results = json.loads(stdout)
                n_correct = sum(1 for r in results if r.get("correct"))
                n_total = len(results)
                print(f"    训练验证 (repair {repair_round}): {n_correct}/{n_total}")
                if n_correct == n_total:
                    break
                wrong = [r for r in results if not r.get("correct")]
                repair_msg = f"Your solver got {len(wrong)}/{n_total} wrong. Errors:\n"
                for w in wrong[:3]:
                    repair_msg += f"  Expected: {w['gold']}, Got: {w.get('pred', 'ERROR')}\n"
                repair_msg += f"\nFix the code. Output COMPLETE fixed script."
            except json.JSONDecodeError:
                repair_msg = f"Output is not valid JSON. stdout: {stdout[:200]}\nstderr: {stderr[:200]}\nFix the code."
        else:
            print(f"    执行失败 (repair {repair_round}): {stderr[:100]}")
            repair_msg = f"Code execution failed.\nError: {stderr[:500]}\n\nFix the code. Output COMPLETE script."

        messages.append({"role": "user", "content": repair_msg})
        resp = await client.chat.completions.create(
            model=model,
            messages=messages,
            max_tokens=8192,
            temperature=0.0,
        )
        new_code = extract_code_block(resp.choices[0].message.content or "")
        if new_code:
            code = new_code
        messages.append({"role": "assistant", "content": resp.choices[0].message.content or ""})

    # 测试
    print(f"    [Test] 测试 {len(test_problems)} 个问题...")
    harness = build_test_harness(code, test_problems)
    success, stdout, stderr = execute_python_code(harness, timeout=120)

    if success:
        try:
            results = json.loads(stdout)
            n_correct = sum(1 for r in results if r.get("correct"))
            accuracy = n_correct / len(results) if results else 0
            print(f"    准确率: {accuracy*100:.1f}% ({n_correct}/{len(results)})")
            return {
                "method": f"compile_time_{mode_name}",
                "accuracy": accuracy,
                "n_correct": n_correct,
                "n_total": len(results),
                "results": results,
            }
        except json.JSONDecodeError:
            pass

    print(f"    Solver 失败: {stderr[:200]}")
    return {
        "method": f"compile_time_{mode_name}",
        "accuracy": 0,
        "n_correct": 0,
        "n_total": len(test_problems),
        "failed": True,
        "error": stderr[:500],
    }


# ==========================================
# 条件 D: PCD 诊断
# ==========================================

async def pcd_parse(client: AsyncOpenAI, model: str, problem: Dict) -> Dict:
    """Parse: LLM 从自然语言中提取 HMM 结构"""
    nl = format_hmm_natural_language(problem)
    prompt = f"""{nl}

## Task: Extract Structured Data

Extract the HMM parameters from above in JSON format:
1. "states": list of hidden state names
2. "initial_dist": dict of {{state: probability}}
3. "transition": dict of {{from_state: {{to_state: probability}}}}
4. "emission": dict of {{state: {{observation: probability}}}}
5. "obs_sequence": list of observed values in order

Output ONLY the JSON object."""

    try:
        resp = await client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=4096,
            temperature=0.0,
        )
        text = resp.choices[0].message.content.strip()
        import re
        m = re.search(r'\{.*\}', text, re.DOTALL)
        if m:
            parsed = json.loads(m.group())
            # 验证关键字段
            correct_states = set(problem["states"]) == set(parsed.get("states", []))
            correct_obs = parsed.get("obs_sequence", []) == problem["obs_sequence"]
            correct_init = True
            for s in problem["states"]:
                if abs(problem["initial_dist"].get(s, 0) - parsed.get("initial_dist", {}).get(s, -1)) > 0.01:
                    correct_init = False
                    break
            all_correct = correct_states and correct_obs and correct_init
            return {"correct": all_correct, "parsed": parsed}
        return {"correct": False, "error": "no_json"}
    except Exception as e:
        return {"correct": False, "error": str(e)}


async def pcd_compute(client: AsyncOpenAI, model: str, problem: Dict) -> Dict:
    """Compute: 给 gold parse，LLM 计算 forward algorithm"""
    prompt = f"""You are given EXACT HMM parameters:

States: {json.dumps(problem['states'])}
Initial distribution: {json.dumps(problem['initial_dist'])}
Transition matrix: {json.dumps(problem['transition'])}
Emission matrix: {json.dumps(problem['emission'])}
Observation sequence: {json.dumps(problem['obs_sequence'])}

## Task
Run the Forward Algorithm to compute P(last hidden state | all observations).

Steps:
1. alpha_1(s) = P(s) * P(obs_1 | s), normalize
2. For t=2..T: alpha_t(s) = P(obs_t|s) * sum_prev[ alpha_(t-1)(prev) * P(s|prev) ], normalize
3. Final alpha = posterior over last state

**Output ONLY JSON**: {{"most_likely_state": "name", "posterior": {{"S1": 0.xx, ...}}}}"""

    try:
        resp = await client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=4096,
            temperature=0.0,
        )
        text = resp.choices[0].message.content.strip()
        import re
        m = re.search(r'\{.*\}', text, re.DOTALL)
        if m:
            result = json.loads(m.group())
            pred = result.get("most_likely_state", "")
            correct = pred == problem["gold_state"]
            return {"correct": correct, "prediction": pred, "raw": text}
        return {"correct": False, "error": "no_json", "raw": text}
    except Exception as e:
        return {"correct": False, "error": str(e)}


async def pcd_decide(client: AsyncOpenAI, model: str, problem: Dict) -> Dict:
    """Decide: 给 gold posterior，LLM 选择最可能状态"""
    prompt = f"""The Forward Algorithm has been completed for a Hidden Markov Model.
The posterior probabilities for the LAST hidden state are:

{json.dumps(problem['gold_posterior'], indent=2)}

## Task
Which state is the most likely given the observations?

Output ONLY JSON: {{"most_likely_state": "StateName"}}"""

    try:
        resp = await client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=256,
            temperature=0.0,
        )
        text = resp.choices[0].message.content.strip()
        import re
        m = re.search(r'\{.*\}', text, re.DOTALL)
        if m:
            result = json.loads(m.group())
            pred = result.get("most_likely_state", "")
            correct = pred == problem["gold_state"]
            return {"correct": correct, "prediction": pred}
        return {"correct": False, "error": "no_json"}
    except Exception as e:
        return {"correct": False, "error": str(e)}


# ==========================================
# 主实验
# ==========================================

async def run_experiment(model: str, n_problems: int, mode: str, seed: int):
    print(f"\n{'='*60}")
    print(f"Held-out Family: HMM Forward Filtering")
    print(f"模型: {model}, 问题数: {n_problems}, 模式: {mode}")
    print(f"{'='*60}")

    all_problems = generate_dataset(n_problems, seed=seed)
    train_problems = all_problems[:5]
    test_problems = all_problems[5:]

    if len(test_problems) == 0:
        test_problems = all_problems
        train_problems = all_problems[:3]

    print(f"  训练: {len(train_problems)}, 测试: {len(test_problems)}")

    client = get_client()
    results = {"model": model, "n_problems": n_problems, "mode": mode, "family": "hmm"}

    # A: Direct Answer
    if mode in ("all", "direct"):
        print(f"\n  [1] Direct Answer...")
        direct_results = []
        for i, p in enumerate(test_problems):
            r = await direct_answer(client, model, p)
            correct = r["prediction"] == p["gold_state"]
            direct_results.append({"correct": correct, **r})
            if (i + 1) % 20 == 0:
                acc = sum(1 for x in direct_results if x["correct"]) / len(direct_results)
                print(f"    进度: {i+1}/{len(test_problems)}, 当前准确率: {acc*100:.1f}%")

        n_correct = sum(1 for r in direct_results if r["correct"])
        results["direct"] = {
            "accuracy": n_correct / len(direct_results),
            "n_correct": n_correct,
            "n_total": len(direct_results),
        }
        print(f"    Direct Answer 准确率: {results['direct']['accuracy']*100:.1f}%")

    # B: Compile-time Free Code
    if mode in ("all", "compile"):
        print(f"\n  [2] Compile-time Free Code...")
        ct_result = await compile_time_solver(
            client, model, train_problems, test_problems,
            use_core_ops=False, max_repairs=3,
        )
        results["compile_free"] = {
            "accuracy": ct_result["accuracy"],
            "n_correct": ct_result.get("n_correct", 0),
            "n_total": ct_result.get("n_total", len(test_problems)),
            "failed": ct_result.get("failed", False),
        }

    # C: Core-ops Constrained
    if mode in ("all", "core_ops"):
        print(f"\n  [3] Core-ops Constrained...")
        co_result = await compile_time_solver(
            client, model, train_problems, test_problems,
            use_core_ops=True, max_repairs=3,
        )
        results["compile_core_ops"] = {
            "accuracy": co_result["accuracy"],
            "n_correct": co_result.get("n_correct", 0),
            "n_total": co_result.get("n_total", len(test_problems)),
            "failed": co_result.get("failed", False),
        }

    # D: PCD
    if mode in ("all", "pcd"):
        print(f"\n  [4] PCD 诊断...")
        pcd_results = {"parse": [], "compute": [], "decide": []}

        for i, p in enumerate(test_problems):
            parse_r = await pcd_parse(client, model, p)
            compute_r = await pcd_compute(client, model, p)
            decide_r = await pcd_decide(client, model, p)
            pcd_results["parse"].append(parse_r)
            pcd_results["compute"].append(compute_r)
            pcd_results["decide"].append(decide_r)

            if (i + 1) % 20 == 0:
                pa = sum(1 for x in pcd_results["parse"] if x.get("correct")) / len(pcd_results["parse"])
                ca = sum(1 for x in pcd_results["compute"] if x.get("correct")) / len(pcd_results["compute"])
                da = sum(1 for x in pcd_results["decide"] if x.get("correct")) / len(pcd_results["decide"])
                print(f"    进度: {i+1}/{len(test_problems)}, Parse={pa*100:.0f}% Compute={ca*100:.0f}% Decide={da*100:.0f}%")

        parse_acc = sum(1 for r in pcd_results["parse"] if r.get("correct")) / len(pcd_results["parse"])
        compute_acc = sum(1 for r in pcd_results["compute"] if r.get("correct")) / len(pcd_results["compute"])
        decide_acc = sum(1 for r in pcd_results["decide"] if r.get("correct")) / len(pcd_results["decide"])

        results["pcd"] = {
            "parse_accuracy": parse_acc,
            "compute_accuracy": compute_acc,
            "decide_accuracy": decide_acc,
        }
        print(f"    PCD: Parse={parse_acc*100:.1f}% Compute={compute_acc*100:.1f}% Decide={decide_acc*100:.1f}%")

    # 保存
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    model_tag = model.replace("/", "_")
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_file = RESULTS_DIR / f"held_out_hmm_{model_tag}_{n_problems}problems_{ts}.json"
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    print(f"\n  结果保存: {out_file}")

    # 汇总
    print(f"\n{'='*60}")
    print(f"HMM Held-out 实验汇总 — {model}")
    print(f"{'='*60}")
    for key, val in results.items():
        if isinstance(val, dict) and "accuracy" in val:
            print(f"  {key}: {val['accuracy']*100:.1f}%")
        elif isinstance(val, dict) and "parse_accuracy" in val:
            print(f"  PCD: Parse={val['parse_accuracy']*100:.1f}% Compute={val['compute_accuracy']*100:.1f}% Decide={val['decide_accuracy']*100:.1f}%")

    return results


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Held-out Family: HMM Forward Filtering")
    parser.add_argument("--model", "-m", default="openai/gpt-4o-mini")
    parser.add_argument("--n", type=int, default=105, help="问题数量 (前5训练，其余测试)")
    parser.add_argument("--mode", choices=["all", "direct", "compile", "core_ops", "pcd"], default="all")
    parser.add_argument("--seed", type=int, default=2026)
    args = parser.parse_args()

    results = asyncio.run(run_experiment(args.model, args.n, args.mode, args.seed))
