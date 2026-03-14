#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Held-out Inference Family 实验 — Naive Bayes 医学诊断

验证目标: DSL core ops 能否泛化到从未见过的第 4 个 inference family。
当前 DSL 有 3 个 macro（hypothesis_enumeration, conjugate_update, variable_elimination），
恰好对应 3 个 benchmark。本实验用 Naive Bayes 医学诊断——一个全新的推理任务——
测试 LLM 能否用 core ops 组合出正确 solver，而不依赖预定义 macro。

实验条件:
  A. Direct Answer — LLM 直接给出诊断
  B. Compile-time Free Code — LLM 写自由 Python solver
  C. Core-ops Constrained — LLM 写 solver 但只能用 DSL core ops
  D. PCD 诊断 — Parse/Compute/Decide 分阶段测试

用法:
  python run_held_out_family.py --model openai/gpt-5.4 --n 50
  python run_held_out_family.py --model openai/gpt-4o-mini --n 50 --mode all
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
from itertools import product as iterproduct

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
# 数据生成: Naive Bayes 医学诊断
# ==========================================

# 疾病和症状库
DISEASES_POOL = [
    "Common Cold", "Influenza", "COVID-19", "Allergic Rhinitis",
    "Bronchitis", "Pneumonia", "Strep Throat", "Sinusitis",
    "Asthma Exacerbation", "Gastroenteritis",
]

SYMPTOMS_POOL = [
    "Fever", "Cough", "Runny Nose", "Fatigue", "Headache",
    "Sore Throat", "Body Aches", "Shortness of Breath",
    "Sneezing", "Nausea", "Diarrhea", "Chest Pain",
    "Loss of Taste", "Congestion", "Chills",
]


def generate_naive_bayes_problem(
    n_diseases: int = 4,
    n_symptoms: int = 5,
    seed: int = 0,
) -> Dict[str, Any]:
    """生成一个 Naive Bayes 医学诊断问题"""
    rng = random.Random(seed)

    # 选择疾病和症状
    diseases = rng.sample(DISEASES_POOL, min(n_diseases, len(DISEASES_POOL)))
    symptoms = rng.sample(SYMPTOMS_POOL, min(n_symptoms, len(SYMPTOMS_POOL)))

    # 生成先验概率 (Dirichlet-like)
    raw_priors = [rng.uniform(0.05, 0.5) for _ in diseases]
    total = sum(raw_priors)
    priors = {d: round(p / total, 3) for d, p in zip(diseases, raw_priors)}
    # 确保和为 1
    diff = 1.0 - sum(priors.values())
    priors[diseases[0]] = round(priors[diseases[0]] + diff, 3)

    # 生成条件概率 P(symptom | disease)
    # 让某些症状对某些疾病有高概率，增加区分度
    likelihoods = {}
    for d in diseases:
        likelihoods[d] = {}
        for s in symptoms:
            # 每个疾病有 1-2 个"标志性"症状（高概率）
            p = rng.uniform(0.05, 0.95)
            likelihoods[d][s] = round(p, 2)

    # 选择真实疾病并生成患者症状
    true_disease = rng.choice(diseases)
    patient_symptoms = {}
    for s in symptoms:
        p = likelihoods[true_disease][s]
        patient_symptoms[s] = rng.random() < p  # True = 有症状

    # 计算 gold posterior
    log_posteriors = {}
    for d in diseases:
        log_p = math.log(priors[d])
        for s in symptoms:
            p_s_given_d = likelihoods[d][s]
            if patient_symptoms[s]:
                log_p += math.log(max(p_s_given_d, 1e-10))
            else:
                log_p += math.log(max(1.0 - p_s_given_d, 1e-10))
        log_posteriors[d] = log_p

    # Normalize (log-sum-exp)
    max_log = max(log_posteriors.values())
    exp_sum = sum(math.exp(lp - max_log) for lp in log_posteriors.values())
    posteriors = {d: math.exp(lp - max_log) / exp_sum for d, lp in log_posteriors.items()}

    gold_diagnosis = max(posteriors, key=posteriors.get)
    gold_posterior = {d: round(p, 6) for d, p in posteriors.items()}

    return {
        "diseases": diseases,
        "symptoms": symptoms,
        "priors": priors,
        "likelihoods": likelihoods,
        "patient_symptoms": patient_symptoms,
        "true_disease": true_disease,
        "gold_diagnosis": gold_diagnosis,
        "gold_posterior": gold_posterior,
        "n_diseases": n_diseases,
        "n_symptoms": n_symptoms,
        "seed": seed,
    }


def format_problem_natural_language(problem: Dict) -> str:
    """将问题格式化为自然语言描述"""
    lines = []
    lines.append("You are a medical diagnostic AI. Based on the following medical knowledge and patient symptoms, determine the most likely diagnosis.\n")

    # 先验
    lines.append("## Disease Prevalence (Prior Probabilities)")
    for d in problem["diseases"]:
        lines.append(f"- {d}: {problem['priors'][d]*100:.1f}%")

    # 条件概率
    lines.append("\n## Symptom Probabilities by Disease")
    for d in problem["diseases"]:
        lines.append(f"\nIf the patient has **{d}**:")
        for s in problem["symptoms"]:
            p = problem["likelihoods"][d][s]
            lines.append(f"  - {s}: {p*100:.0f}% chance")

    # 患者症状
    lines.append("\n## Patient Presentation")
    present = [s for s, v in problem["patient_symptoms"].items() if v]
    absent = [s for s, v in problem["patient_symptoms"].items() if not v]
    if present:
        lines.append(f"Symptoms PRESENT: {', '.join(present)}")
    if absent:
        lines.append(f"Symptoms ABSENT: {', '.join(absent)}")

    return "\n".join(lines)


def generate_dataset(n_problems: int, seed: int = 42,
                     difficulty: str = "mixed") -> List[Dict]:
    """生成完整数据集"""
    problems = []
    rng = random.Random(seed)

    for i in range(n_problems):
        if difficulty == "easy":
            n_d, n_s = 3, 4
        elif difficulty == "hard":
            n_d, n_s = 6, 8
        elif difficulty == "mixed":
            n_d = rng.choice([3, 4, 5, 6])
            n_s = rng.choice([4, 5, 6, 7, 8])
        else:
            n_d, n_s = 4, 5

        p = generate_naive_bayes_problem(
            n_diseases=n_d,
            n_symptoms=n_s,
            seed=seed * 10000 + i,
        )
        p["problem_id"] = i
        problems.append(p)

    return problems


# ==========================================
# 条件 A: Direct Answer
# ==========================================

async def direct_answer(client: AsyncOpenAI, model: str, problem: Dict) -> Dict:
    """LLM 直接给出诊断"""
    nl = format_problem_natural_language(problem)
    prompt = f"""{nl}

## Task
Based on Bayesian reasoning, compute the posterior probability of each disease given the patient's symptoms, then identify the most likely diagnosis.

Use Bayes' theorem with the Naive Bayes assumption (symptoms are conditionally independent given the disease):
P(Disease | Symptoms) ∝ P(Disease) × ∏ P(Symptom_i | Disease)

For absent symptoms, use P(Symptom absent | Disease) = 1 - P(Symptom present | Disease).

**Output format**: Respond with ONLY a JSON object:
{{"diagnosis": "Disease Name", "posteriors": {{"Disease1": 0.xx, "Disease2": 0.xx, ...}}}}
"""
    try:
        resp = await client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=1024,
            temperature=0.0,
        )
        text = resp.choices[0].message.content.strip()
        # 解析 JSON
        import re
        m = re.search(r'\{.*\}', text, re.DOTALL)
        if m:
            result = json.loads(m.group())
            diagnosis = result.get("diagnosis", "")
            return {"diagnosis": diagnosis, "raw": text, "error": None}
        return {"diagnosis": "", "raw": text, "error": "no_json"}
    except Exception as e:
        return {"diagnosis": "", "raw": "", "error": str(e)}


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
        examples += f"\n--- Example {i+1} (diseases={p['n_diseases']}, symptoms={p['n_symptoms']}) ---\n"
        examples += f"diseases: {p['diseases']}\n"
        examples += f"priors: {json.dumps(p['priors'])}\n"
        examples += f"likelihoods: {json.dumps(p['likelihoods'])}\n"
        examples += f"patient_symptoms: {json.dumps(p['patient_symptoms'])}\n"
        examples += f"correct_diagnosis: {p['gold_diagnosis']}\n"
        examples += f"correct_posteriors: {json.dumps(p['gold_posterior'])}\n"

    core_ops_section = ""
    if use_core_ops:
        core_ops_section = """
## Available Core Operations (you MUST use these)

You have access to the following typed operations. Your solver MUST be composed from these operations:

```python
def normalize(unnormalized: dict) -> dict:
    \"\"\"Normalize a dict of {key: float} to sum to 1.0\"\"\"
    total = sum(unnormalized.values())
    return {k: v/total for k, v in unnormalized.items()} if total > 0 else unnormalized

def multiply_factors(factors: list) -> dict:
    \"\"\"Element-wise multiply a list of dicts with same keys\"\"\"
    result = dict(factors[0])
    for f in factors[1:]:
        for k in result:
            result[k] *= f.get(k, 1.0)
    return result

def enumerate_space(items: list) -> list:
    \"\"\"Return the list of items to enumerate over\"\"\"
    return list(items)

def condition(distribution: dict, evidence_key: str, evidence_val, cpt: dict) -> dict:
    \"\"\"Condition a distribution on evidence using a CPT\"\"\"
    result = {}
    for k, p in distribution.items():
        likelihood = cpt.get(k, {}).get(evidence_key, 0.5)
        if not evidence_val:
            likelihood = 1.0 - likelihood
        result[k] = p * likelihood
    return result

def expectation(distribution: dict, utility_fn) -> float:
    \"\"\"Compute E[utility] under distribution\"\"\"
    return sum(p * utility_fn(k) for k, p in distribution.items())

def argmax(scores: dict) -> str:
    \"\"\"Return key with highest value\"\"\"
    return max(scores, key=scores.get)
```

Your solver function MUST call these operations. Do NOT implement your own probability calculations from scratch.
"""

    constraint = "only Python stdlib (no numpy/scipy)" if not use_core_ops else "ONLY the core operations defined above"

    return f"""You are an expert programmer. Write a Python function that solves Naive Bayes medical diagnosis problems.

## Task Description

Given:
- A list of diseases with prior probabilities
- Conditional probabilities P(symptom | disease) for each symptom and disease
- A patient's observed symptoms (present/absent)

Compute:
- Posterior P(disease | symptoms) using Naive Bayes: P(D|S) ∝ P(D) × ∏ P(s_i|D)
- For absent symptoms: P(symptom absent | D) = 1 - P(symptom present | D)
- Return the most likely diagnosis
{core_ops_section}
## Examples
{examples}

## Requirements

Write a complete Python script that:
1. Defines `def solve(diseases, priors, likelihoods, patient_symptoms) -> tuple`:
   - diseases: list of disease names
   - priors: dict {{disease: prior_probability}}
   - likelihoods: dict {{disease: {{symptom: P(symptom|disease)}}}}
   - patient_symptoms: dict {{symptom: bool (True=present)}}
   - Returns: (diagnosis: str, posteriors: dict)
2. Uses {constraint}
3. Tests on examples above, printing results as JSON

Write the COMPLETE code now:"""


def build_test_harness(solver_code: str, test_problems: List[Dict]) -> str:
    """构建测试 harness"""
    # 提取 solver 部分（去掉末尾测试代码）
    lines = solver_code.split("\n")
    func_lines = []
    for line in lines:
        if line.strip().startswith("if __name__"):
            break
        func_lines.append(line)
    # 去掉末尾的 print/test 语句
    while func_lines and func_lines[-1].strip().startswith(("print(", "result", "answer", "test", "#")):
        func_lines.pop()
    while func_lines and not func_lines[-1].strip():
        func_lines.pop()
    solver_only = "\n".join(func_lines)

    test_data = []
    for p in test_problems:
        test_data.append({
            "diseases": p["diseases"],
            "priors": p["priors"],
            "likelihoods": p["likelihoods"],
            "patient_symptoms": p["patient_symptoms"],
            "gold_diagnosis": p["gold_diagnosis"],
        })

    return f"""{solver_only}

import json, sys

test_data = json.loads('''{json.dumps(test_data)}''')

results = []
for i, td in enumerate(test_data):
    try:
        diag, posteriors = solve(td["diseases"], td["priors"], td["likelihoods"], td["patient_symptoms"])
        results.append({{"idx": i, "pred": diag, "gold": td["gold_diagnosis"], "correct": diag == td["gold_diagnosis"]}})
    except Exception as e:
        results.append({{"idx": i, "pred": None, "gold": td["gold_diagnosis"], "correct": False, "error": str(e)}})

print(json.dumps(results))
"""


def extract_code_block(response: str) -> str:
    """从 LLM 响应中提取代码块"""
    import re
    matches = re.findall(r"```(?:python)?\s*\n(.*?)```", response, re.DOTALL)
    if matches:
        return max(matches, key=len).strip()
    if "def solve" in response:
        return response.strip()
    return ""


async def compile_time_solver(
    client: AsyncOpenAI,
    model: str,
    train_problems: List[Dict],
    test_problems: List[Dict],
    use_core_ops: bool = False,
    max_repairs: int = 3,
) -> Dict:
    """Compile-time solver 生成 + 测试"""
    mode_name = "core-ops" if use_core_ops else "free-code"
    print(f"\n  [Compile-time {mode_name}] 请求 {model} 编写 solver...")

    prompt = build_compile_prompt(train_problems, use_core_ops=use_core_ops)

    # 第一次生成
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

    # Self-repair 循环
    messages = [
        {"role": "user", "content": prompt},
        {"role": "assistant", "content": resp.choices[0].message.content or ""},
    ]

    for repair_round in range(max_repairs):
        # 在训练集上验证
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
                # 有错误，请求修复
                wrong = [r for r in results if not r.get("correct")]
                repair_msg = f"Your solver got {len(wrong)}/{n_total} wrong on training examples. Errors:\n"
                for w in wrong[:3]:
                    repair_msg += f"  Expected: {w['gold']}, Got: {w.get('pred', 'ERROR')}\n"
                repair_msg += f"\nYour code:\n```python\n{code}\n```\n\nFix the code. Output COMPLETE fixed script."
            except json.JSONDecodeError:
                repair_msg = f"Code output is not valid JSON. stdout: {stdout[:200]}\nstderr: {stderr[:200]}\n\nFix the code. Output COMPLETE script."
        else:
            print(f"    执行失败 (repair {repair_round}): {stderr[:100]}")
            repair_msg = f"Code execution failed.\nError: {stderr[:500]}\n\nYour code:\n```python\n{code}\n```\n\nFix the code. Output COMPLETE script."

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

    # 在全测试集上评测
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
                "code_length": len(code),
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
    """Parse 阶段: LLM 从自然语言中提取结构化数据"""
    nl = format_problem_natural_language(problem)
    prompt = f"""{nl}

## Task: Extract Structured Data

From the medical knowledge above, extract the following in JSON format:
1. "diseases": list of disease names
2. "priors": dict of {{disease: prior_probability}}
3. "likelihoods": dict of {{disease: {{symptom: P(symptom|disease)}}}}
4. "patient_symptoms": dict of {{symptom: true/false}}

Output ONLY the JSON object."""

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
            parsed = json.loads(m.group())
            # 验证 parse 正确性
            correct_diseases = set(problem["diseases"]) == set(parsed.get("diseases", []))
            correct_priors = True
            for d in problem["diseases"]:
                if abs(problem["priors"].get(d, 0) - parsed.get("priors", {}).get(d, -1)) > 0.01:
                    correct_priors = False
                    break
            correct_symptoms = True
            for s in problem["symptoms"]:
                if problem["patient_symptoms"].get(s) != parsed.get("patient_symptoms", {}).get(s):
                    correct_symptoms = False
                    break
            correct_likelihoods = True
            for d in problem["diseases"]:
                for s in problem["symptoms"]:
                    gold_l = problem["likelihoods"].get(d, {}).get(s, -1)
                    pred_l = parsed.get("likelihoods", {}).get(d, {}).get(s, -999)
                    if abs(gold_l - pred_l) > 0.02:
                        correct_likelihoods = False
                        break

            all_correct = correct_diseases and correct_priors and correct_symptoms and correct_likelihoods
            return {
                "correct": all_correct,
                "correct_diseases": correct_diseases,
                "correct_priors": correct_priors,
                "correct_symptoms": correct_symptoms,
                "correct_likelihoods": correct_likelihoods,
                "parsed": parsed,
            }
        return {"correct": False, "error": "no_json"}
    except Exception as e:
        return {"correct": False, "error": str(e)}


async def pcd_compute(client: AsyncOpenAI, model: str, problem: Dict) -> Dict:
    """Compute 阶段: 给 gold parse，LLM 自己计算 posterior"""
    prompt = f"""You are given the following EXACT structured data for a Naive Bayes medical diagnosis problem.

Diseases: {json.dumps(problem['diseases'])}
Prior probabilities: {json.dumps(problem['priors'])}
Likelihoods P(symptom|disease): {json.dumps(problem['likelihoods'])}
Patient symptoms (True=present, False=absent): {json.dumps(problem['patient_symptoms'])}

## Task
Compute the posterior probability of each disease using Naive Bayes:
P(Disease | Symptoms) ∝ P(Disease) × ∏ P(symptom_i | Disease)

For ABSENT symptoms, use: P(absent | Disease) = 1 - P(present | Disease)

Then normalize so posteriors sum to 1.0.

**Output ONLY a JSON**: {{"diagnosis": "most likely disease", "posteriors": {{"Disease1": 0.xxx, ...}}}}"""

    try:
        resp = await client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=1024,
            temperature=0.0,
        )
        text = resp.choices[0].message.content.strip()
        import re
        m = re.search(r'\{.*\}', text, re.DOTALL)
        if m:
            result = json.loads(m.group())
            pred_diag = result.get("diagnosis", "")
            correct = pred_diag == problem["gold_diagnosis"]
            return {"correct": correct, "diagnosis": pred_diag, "raw": text}
        return {"correct": False, "error": "no_json", "raw": text}
    except Exception as e:
        return {"correct": False, "error": str(e)}


async def pcd_decide(client: AsyncOpenAI, model: str, problem: Dict) -> Dict:
    """Decide 阶段: 给 gold posterior，LLM 选择诊断"""
    prompt = f"""You are a medical AI. The Bayesian analysis has been completed. Here are the posterior probabilities for each disease:

{json.dumps(problem['gold_posterior'], indent=2)}

## Task
Based on these posterior probabilities, which disease is the most likely diagnosis?

Output ONLY a JSON: {{"diagnosis": "Disease Name"}}"""

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
            pred = result.get("diagnosis", "")
            correct = pred == problem["gold_diagnosis"]
            return {"correct": correct, "diagnosis": pred}
        return {"correct": False, "error": "no_json"}
    except Exception as e:
        return {"correct": False, "error": str(e)}


# ==========================================
# 主实验
# ==========================================

async def run_experiment(model: str, n_problems: int, mode: str, seed: int):
    """运行完整实验"""
    print(f"\n{'='*60}")
    print(f"Held-out Family: Naive Bayes 医学诊断")
    print(f"模型: {model}, 问题数: {n_problems}, 模式: {mode}")
    print(f"{'='*60}")

    # 生成数据
    all_problems = generate_dataset(n_problems, seed=seed, difficulty="mixed")
    train_problems = all_problems[:5]  # 前 5 个做训练
    test_problems = all_problems[5:]   # 其余做测试

    if len(test_problems) == 0:
        test_problems = all_problems  # 如果太少就全用
        train_problems = all_problems[:3]

    print(f"  训练: {len(train_problems)}, 测试: {len(test_problems)}")
    print(f"  难度分布: {[(p['n_diseases'], p['n_symptoms']) for p in test_problems[:5]]}...")

    client = get_client()
    results = {"model": model, "n_problems": n_problems, "mode": mode}

    # 条件 A: Direct Answer
    if mode in ("all", "direct"):
        print(f"\n  [1] Direct Answer...")
        direct_results = []
        for i, p in enumerate(test_problems):
            r = await direct_answer(client, model, p)
            correct = r["diagnosis"] == p["gold_diagnosis"]
            direct_results.append({"correct": correct, **r})
            if (i + 1) % 10 == 0:
                acc = sum(1 for x in direct_results if x["correct"]) / len(direct_results)
                print(f"    进度: {i+1}/{len(test_problems)}, 当前准确率: {acc*100:.1f}%")

        n_correct = sum(1 for r in direct_results if r["correct"])
        results["direct"] = {
            "accuracy": n_correct / len(direct_results),
            "n_correct": n_correct,
            "n_total": len(direct_results),
        }
        print(f"    Direct Answer 准确率: {results['direct']['accuracy']*100:.1f}%")

    # 条件 B: Compile-time Free Code
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

    # 条件 C: Core-ops Constrained
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

    # 条件 D: PCD 诊断
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

            if (i + 1) % 10 == 0:
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

    # 保存结果
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    model_tag = model.replace("/", "_")
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_file = RESULTS_DIR / f"held_out_nb_{model_tag}_{n_problems}problems_{ts}.json"
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    print(f"\n  结果保存: {out_file}")

    # 汇总
    print(f"\n{'='*60}")
    print(f"Held-out Family 实验汇总 — {model}")
    print(f"{'='*60}")
    for key, val in results.items():
        if isinstance(val, dict) and "accuracy" in val:
            print(f"  {key}: {val['accuracy']*100:.1f}%")
        elif isinstance(val, dict) and "parse_accuracy" in val:
            print(f"  PCD: Parse={val['parse_accuracy']*100:.1f}% Compute={val['compute_accuracy']*100:.1f}% Decide={val['decide_accuracy']*100:.1f}%")

    return results


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Held-out Family: Naive Bayes 医学诊断")
    parser.add_argument("--model", "-m", default="openai/gpt-4o-mini")
    parser.add_argument("--n", type=int, default=50, help="问题数量")
    parser.add_argument("--mode", choices=["all", "direct", "compile", "core_ops", "pcd"], default="all")
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    results = asyncio.run(run_experiment(args.model, args.n, args.mode, args.seed))
