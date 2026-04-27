#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Held-out 实验 — bnlearn 经典贝叶斯网络（非合成、公开数据集）

使用 pgmpy 加载 bnlearn repository 的标准 BN 网络（Asia, Alarm, Insurance, Child），
随机生成推理 query，测试 DSL core ops 能否正确求解。

这些网络是 PGM 社区的 gold standard：
- Asia (8 nodes): 肺病诊断
- Child (20 nodes): 新生儿疾病
- Insurance (27 nodes): 汽车保险评估
- Alarm (37 nodes): ICU 患者监护

用法:
  python run_bnlearn_held_out.py --model openai/gpt-4o-mini --queries-per-net 30
  python run_bnlearn_held_out.py --model openai/gpt-5.4 --queries-per-net 30
"""

import os
import sys
import json
import random
import asyncio
import argparse
import subprocess
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Tuple
from datetime import datetime

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

# pgmpy 0.1.26 + xgboost-without-libomp 修复 (2026-04-27)
# 必须在 import pgmpy 之前 monkey-patch xgboost stub。详见 _pgmpy_compat.py
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _pgmpy_compat  # noqa: F401

import httpx
from openai import AsyncOpenAI
from pgmpy.utils import get_example_model
from pgmpy.inference import VariableElimination

SCRIPT_DIR = Path(__file__).parent
RESULTS_DIR = SCRIPT_DIR / "results"


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
# 从 bnlearn 网络生成推理问题
# ==========================================

def generate_queries_from_network(
    net_name: str,
    n_queries: int,
    seed: int = 42,
) -> List[Dict[str, Any]]:
    """从 pgmpy 网络生成随机推理 query"""
    model = get_example_model(net_name)
    ve = VariableElimination(model)
    nodes = list(model.nodes())
    rng = random.Random(seed)

    # 收集每个节点的状态名和 CPT
    node_states = {}
    cpts = {}
    for node in nodes:
        cpd = model.get_cpds(node)
        node_states[node] = cpd.state_names[node]
        # 提取 CPT 为 dict 格式
        parents = list(cpd.get_evidence())
        if not parents:
            # 根节点：P(node)
            vals = cpd.values.flatten()
            cpts[node] = {
                "parents": [],
                "probabilities": {s: float(vals[i]) for i, s in enumerate(node_states[node])}
            }
        else:
            # 有父节点：P(node | parents)
            parent_states_list = [cpd.state_names[p] for p in parents]
            from itertools import product as iterproduct
            parent_combos = list(iterproduct(*parent_states_list))

            # Flatten the values array for safe indexing
            vals = cpd.values.reshape(len(node_states[node]), -1)

            cpt_entries = []
            for col_idx, combo in enumerate(parent_combos):
                entry = dict(zip(parents, combo))
                for row_idx, state in enumerate(node_states[node]):
                    entry[f"P({node}={state})"] = float(vals[row_idx, col_idx])
                cpt_entries.append(entry)
            cpts[node] = {
                "parents": parents,
                "entries": cpt_entries
            }

    # 提取网络边
    edges = [(str(u), str(v)) for u, v in model.edges()]

    queries = []
    for i in range(n_queries):
        # 随机选 query variable
        query_var = rng.choice(nodes)

        # 随机选 1-3 个 evidence variables（非 query）
        other_nodes = [n for n in nodes if n != query_var]
        n_evidence = rng.randint(1, min(3, len(other_nodes)))
        evidence_vars = rng.sample(other_nodes, n_evidence)

        # 随机选 evidence 值
        evidence = {}
        for ev in evidence_vars:
            evidence[ev] = rng.choice(node_states[ev])

        # 用 pgmpy 计算 gold answer
        try:
            result = ve.query([query_var], evidence=evidence)
            gold_posterior = {}
            for idx, state in enumerate(node_states[query_var]):
                gold_posterior[state] = round(float(result.values[idx]), 6)
            gold_answer = max(gold_posterior, key=gold_posterior.get)
        except Exception as e:
            continue  # 跳过不可推理的 query

        queries.append({
            "query_id": i,
            "network": net_name,
            "n_nodes": len(nodes),
            "n_edges": len(edges),
            "nodes": nodes,
            "edges": edges,
            "node_states": node_states,
            "query_variable": query_var,
            "evidence": evidence,
            "gold_answer": gold_answer,
            "gold_posterior": gold_posterior,
        })

    return queries, cpts


def format_bn_problem(query: Dict, cpts: Dict) -> str:
    """格式化为自然语言 BN 推理问题"""
    lines = []
    lines.append(f"## Bayesian Network: {query['network']} ({query['n_nodes']} variables, {query['n_edges']} edges)\n")

    lines.append("### Network Structure (directed edges):")
    for u, v in query["edges"]:
        lines.append(f"  {u} -> {v}")

    lines.append("\n### Conditional Probability Tables:")
    for node in query["nodes"]:
        cpt = cpts[node]
        if not cpt["parents"]:
            lines.append(f"\nP({node}):")
            for state, prob in cpt["probabilities"].items():
                lines.append(f"  P({node}={state}) = {prob:.4f}")
        else:
            lines.append(f"\nP({node} | {', '.join(cpt['parents'])}):")
            for entry in cpt["entries"]:
                parent_str = ", ".join(f"{p}={entry[p]}" for p in cpt["parents"])
                prob_str = ", ".join(
                    f"P({node}={s})={entry[f'P({node}={s})']:.4f}"
                    for s in query["node_states"][node]
                )
                lines.append(f"  Given {parent_str}: {prob_str}")

    lines.append(f"\n### Evidence:")
    for var, val in query["evidence"].items():
        lines.append(f"  {var} = {val}")

    lines.append(f"\n### Query: P({query['query_variable']} | evidence)")

    return "\n".join(lines)


# ==========================================
# Direct Answer
# ==========================================

async def direct_answer(client: AsyncOpenAI, model: str, query: Dict, cpts: Dict) -> Dict:
    nl = format_bn_problem(query, cpts)
    prompt = f"""{nl}

## Task
Compute the posterior distribution P({query['query_variable']} | evidence) using Variable Elimination.
Show the most likely value.

**Output ONLY JSON**: {{"answer": "most_likely_value", "posterior": {{"val1": 0.xx, ...}}}}"""

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
            pred = result.get("answer", "")
            return {"prediction": pred, "error": None}
        return {"prediction": "", "error": "no_json"}
    except Exception as e:
        return {"prediction": "", "error": str(e)}


# ==========================================
# Compile-time Solver
# ==========================================

def execute_python_code(code: str, timeout: int = 60) -> Tuple[bool, str, str]:
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


def build_compile_prompt(train_queries: List[Dict], cpts_list: List[Dict], use_core_ops: bool = False) -> str:
    examples = ""
    for i, (q, cpts) in enumerate(zip(train_queries, cpts_list)):
        examples += f"\n--- Example {i+1} ({q['network']}, {q['n_nodes']} nodes) ---\n"
        examples += f"nodes: {q['nodes']}\n"
        examples += f"edges: {q['edges']}\n"
        examples += f"node_states: {json.dumps(q['node_states'])}\n"
        examples += f"query_variable: {q['query_variable']}\n"
        examples += f"evidence: {json.dumps(q['evidence'])}\n"
        examples += f"correct_answer: {q['gold_answer']}\n"
        examples += f"correct_posterior: {json.dumps(q['gold_posterior'])}\n"
        # CPT 完整表示（C1 修复：原代码 `entries[:3]` 截断让 LLM 看不到完整 CPT 结构）
        cpt_full = {}
        for node, cpt in cpts.items():
            if not cpt["parents"]:
                cpt_full[node] = {"parents": [], "probs": cpt["probabilities"]}
            else:
                cpt_full[node] = {"parents": cpt["parents"], "entries": cpt["entries"]}
        examples += f"cpts: {json.dumps(cpt_full, default=str)}\n"

    core_ops_section = ""
    if use_core_ops:
        core_ops_section = """
## Available Core Operations (you MUST use these)

```python
def normalize(unnormalized: dict) -> dict:
    total = sum(unnormalized.values())
    return {k: v/total for k, v in unnormalized.items()} if total > 0 else unnormalized

def multiply_factors(factors: list) -> dict:
    \"\"\"Multiply a list of factor dicts. Each factor is {tuple_of_(var,val)_pairs: probability}.\"\"\"
    if not factors:
        return {(): 1.0}
    result = factors[0]
    for f in factors[1:]:
        new_result = {}
        for k1, v1 in result.items():
            d1 = dict(k1)
            for k2, v2 in f.items():
                d2 = dict(k2)
                merged = dict(d1)
                conflict = False
                for var, val in d2.items():
                    if var in merged and merged[var] != val:
                        conflict = True
                        break
                    merged[var] = val
                if not conflict:
                    key = tuple(sorted(merged.items()))
                    new_result[key] = new_result.get(key, 0) + v1 * v2
        result = new_result
    return result

def marginalize(factor: dict, var_to_remove: str) -> dict:
    \"\"\"Sum out a variable from a factor\"\"\"
    result = {}
    for assignment, prob in factor.items():
        reduced = tuple((v, s) for v, s in assignment if v != var_to_remove)
        result[reduced] = result.get(reduced, 0) + prob
    return result

def condition(factor: dict, evidence: dict) -> dict:
    \"\"\"Keep only entries consistent with evidence\"\"\"
    result = {}
    for assignment, prob in factor.items():
        adict = dict(assignment)
        if all(adict.get(v) == val for v, val in evidence.items() if v in adict):
            result[assignment] = prob
    return result

def argmax(scores: dict) -> str:
    return max(scores, key=scores.get)
```

**Factor representation convention**: each factor is a dict whose keys are
tuples of (variable_name, value) pairs in sorted order, and values are
probabilities. E.g. P(A=a1,B=b1)=0.3 becomes {(('A','a1'),('B','b1')): 0.3}.

Your solver MUST use these core operations for factor manipulation. Do NOT
use pgmpy or any external inference library. The core operations above are
fully implemented — call them directly rather than reimplementing them.
"""

    constraint = "only Python stdlib (no pgmpy/numpy/scipy)" if not use_core_ops else "ONLY the core operations above"

    return f"""You are an expert programmer. Write a Python solver for Bayesian Network variable elimination queries.

## Task
Given a Bayesian Network (nodes, edges, CPTs, node_states) and a query (query_variable, evidence),
compute P(query_variable | evidence) using Variable Elimination.

The solver should work on ANY BN structure, not just the examples shown.
{core_ops_section}
## Examples
{examples}

## Requirements
Write a complete Python script that:
1. Defines `def solve(nodes, edges, node_states, cpts, query_variable, evidence) -> tuple`:
   - cpts: dict mapping node -> {{"parents": [...], "entries": [...]}} or {{"parents": [], "probs": {{...}}}}
   - Returns: (answer: str, posterior: dict)
2. Uses {constraint}
3. Implements proper Variable Elimination with factor operations

Write the COMPLETE code now:"""


def extract_code_block(response: str) -> str:
    import re
    matches = re.findall(r"```(?:python)?\s*\n(.*?)```", response, re.DOTALL)
    if matches:
        return max(matches, key=len).strip()
    # 处理 response 以 ```python 开头、以 ``` 结尾的情况
    stripped = response.strip()
    if stripped.startswith("```"):
        # 去掉第一行的 ```python 和最后的 ```
        lines = stripped.split("\n")
        if lines[0].strip().startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        return "\n".join(lines).strip()
    if "def solve" in response or "import " in response:
        return stripped
    return ""


def build_test_harness(solver_code: str, test_queries: List[Dict], cpts_map: Dict) -> str:
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
    for q in test_queries:
        net = q["network"]
        test_data.append({
            "nodes": q["nodes"],
            "edges": q["edges"],
            "node_states": q["node_states"],
            "cpts": cpts_map[net],
            "query_variable": q["query_variable"],
            "evidence": q["evidence"],
            "gold_answer": q["gold_answer"],
        })

    # 序列化 CPT（需要处理 tuple keys）
    test_json = json.dumps(test_data, default=str)

    return f"""{solver_only}

import json, sys

test_data = json.loads('''{test_json}''')

results = []
for i, td in enumerate(test_data):
    try:
        ans, post = solve(td["nodes"], td["edges"], td["node_states"],
                          td["cpts"], td["query_variable"], td["evidence"])
        results.append({{"idx": i, "pred": ans, "gold": td["gold_answer"], "correct": ans == td["gold_answer"]}})
    except Exception as e:
        results.append({{"idx": i, "pred": None, "gold": td["gold_answer"], "correct": False, "error": str(e)}})

print(json.dumps(results))
"""


async def compile_time_solver(
    client: AsyncOpenAI, model: str,
    train_queries: List[Dict], train_cpts: List[Dict],
    test_queries: List[Dict], cpts_map: Dict,
    use_core_ops: bool = False, max_repairs: int = 3,
) -> Dict:
    mode_name = "core-ops" if use_core_ops else "free-code"
    print(f"\n  [Compile-time {mode_name}] 请求 {model}...")

    prompt = build_compile_prompt(train_queries, train_cpts, use_core_ops)

    resp = await client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        max_tokens=16384,
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
        harness = build_test_harness(code, train_queries, cpts_map)
        success, stdout, stderr = execute_python_code(harness, timeout=120)

        if success:
            try:
                results = json.loads(stdout)
                n_correct = sum(1 for r in results if r.get("correct"))
                n_total = len(results)
                print(f"    训练验证 (repair {repair_round}): {n_correct}/{n_total}")
                if n_correct == n_total:
                    break
                wrong = [r for r in results if not r.get("correct")]
                repair_msg = f"Got {len(wrong)}/{n_total} wrong:\n"
                for w in wrong[:3]:
                    repair_msg += f"  Expected: {w['gold']}, Got: {w.get('pred', 'ERROR')}\n"
                    if 'error' in w:
                        repair_msg += f"  Error: {w['error']}\n"
                repair_msg += f"\nFix the code. Output COMPLETE script."
            except json.JSONDecodeError:
                repair_msg = f"Output not valid JSON. stdout: {stdout[:300]}\nstderr: {stderr[:300]}\nFix."
        else:
            print(f"    执行失败 (repair {repair_round}): {stderr[:150]}")
            repair_msg = f"Execution failed:\n{stderr[:800]}\n\nFix the code. Output COMPLETE script."

        messages.append({"role": "user", "content": repair_msg})
        resp = await client.chat.completions.create(
            model=model, messages=messages, max_tokens=16384, temperature=0.0,
        )
        new_code = extract_code_block(resp.choices[0].message.content or "")
        if new_code:
            code = new_code
        messages.append({"role": "assistant", "content": resp.choices[0].message.content or ""})

    # 测试
    print(f"    [Test] {len(test_queries)} queries...")
    harness = build_test_harness(code, test_queries, cpts_map)
    success, stdout, stderr = execute_python_code(harness, timeout=180)

    if success:
        try:
            results = json.loads(stdout)
            n_correct = sum(1 for r in results if r.get("correct"))
            accuracy = n_correct / len(results) if results else 0
            print(f"    准确率: {accuracy*100:.1f}% ({n_correct}/{len(results)})")
            return {"accuracy": accuracy, "n_correct": n_correct, "n_total": len(results)}
        except json.JSONDecodeError:
            pass

    print(f"    失败: {stderr[:200]}")
    return {"accuracy": 0, "n_correct": 0, "n_total": len(test_queries), "failed": True}


# ==========================================
# PCD 诊断
# ==========================================

async def pcd_compute(client: AsyncOpenAI, model: str, query: Dict, cpts: Dict) -> Dict:
    """Compute|GoldParse: 给 gold 网络结构，LLM 自己做 VE"""
    # 构建结构化输入
    cpt_text = ""
    for node in query["nodes"]:
        cpt = cpts[node]
        if not cpt["parents"]:
            cpt_text += f"\nP({node}): {json.dumps(cpt['probabilities'])}"
        else:
            cpt_text += f"\nP({node} | {', '.join(cpt['parents'])}):"
            for entry in cpt["entries"]:
                cpt_text += f"\n  {json.dumps(entry)}"

    prompt = f"""You are given EXACT Bayesian Network parameters:

Nodes: {json.dumps(query['nodes'])}
Edges: {json.dumps(query['edges'])}
Node states: {json.dumps(query['node_states'])}

Conditional Probability Tables:{cpt_text}

Evidence: {json.dumps(query['evidence'])}
Query: P({query['query_variable']} | evidence)

Compute the exact posterior using Variable Elimination. Show your work step by step.

**Output ONLY JSON at the end**: {{"answer": "most_likely_value", "posterior": {{"val1": 0.xx, ...}}}}"""

    try:
        resp = await client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=4096,
            temperature=0.0,
        )
        text = resp.choices[0].message.content.strip()
        import re
        m = re.search(r'\{[^{}]*"answer"[^{}]*\}', text, re.DOTALL)
        if m:
            result = json.loads(m.group())
            pred = result.get("answer", "")
            return {"correct": pred == query["gold_answer"], "prediction": pred}
        return {"correct": False, "error": "no_json"}
    except Exception as e:
        return {"correct": False, "error": str(e)}


async def pcd_decide(client: AsyncOpenAI, model: str, query: Dict) -> Dict:
    """Decide|GoldPosterior: 给 gold posterior，LLM 选答案"""
    prompt = f"""The Variable Elimination computation is complete. The posterior distribution is:

P({query['query_variable']} | evidence) = {json.dumps(query['gold_posterior'])}

Which value of {query['query_variable']} is most likely?

**Output ONLY JSON**: {{"answer": "value"}}"""

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
            pred = result.get("answer", "")
            return {"correct": pred == query["gold_answer"], "prediction": pred}
        return {"correct": False, "error": "no_json"}
    except Exception as e:
        return {"correct": False, "error": str(e)}


# ==========================================
# 主实验
# ==========================================

NETWORKS = ["asia", "child", "insurance", "alarm"]

async def run_experiment(model: str, queries_per_net: int, mode: str, seed: int):
    print(f"\n{'='*60}")
    print(f"bnlearn 经典 BN 网络 Held-out 实验")
    print(f"模型: {model}, 每网络 {queries_per_net} queries")
    print(f"{'='*60}")

    # 生成所有网络的 queries
    all_queries = []
    cpts_map = {}  # {net_name: {node: cpt_dict}}
    cpts_by_query = []

    for net_name in NETWORKS:
        queries, cpts = generate_queries_from_network(net_name, queries_per_net + 3, seed=seed)
        cpts_map[net_name] = cpts
        print(f"  {net_name}: {len(queries)} queries 生成")
        for q in queries:
            all_queries.append(q)
            cpts_by_query.append(cpts)

    # 分训练/测试（每个网络前 3 个做训练）
    train_queries = []
    train_cpts = []
    test_queries = []
    idx = 0
    for net_name in NETWORKS:
        net_queries = [q for q in all_queries if q["network"] == net_name]
        train_queries.extend(net_queries[:3])
        train_cpts.extend([cpts_map[net_name]] * min(3, len(net_queries)))
        test_queries.extend(net_queries[3:3 + queries_per_net])

    print(f"  训练: {len(train_queries)}, 测试: {len(test_queries)}")

    client = get_client()
    results = {"model": model, "queries_per_net": queries_per_net, "networks": NETWORKS}

    # Direct Answer
    if mode in ("all", "direct"):
        print(f"\n  [1] Direct Answer...")
        direct_results = []
        for i, q in enumerate(test_queries):
            r = await direct_answer(client, model, q, cpts_map[q["network"]])
            correct = r["prediction"] == q["gold_answer"]
            direct_results.append(correct)
            if (i + 1) % 20 == 0:
                acc = sum(direct_results) / len(direct_results)
                print(f"    进度: {i+1}/{len(test_queries)}, 准确率: {acc*100:.1f}%")

        results["direct"] = {
            "accuracy": sum(direct_results) / len(direct_results),
            "n_correct": sum(direct_results),
            "n_total": len(direct_results),
        }
        print(f"    Direct: {results['direct']['accuracy']*100:.1f}%")

    # Compile-time Free Code
    if mode in ("all", "compile"):
        print(f"\n  [2] Compile-time Free Code...")
        r = await compile_time_solver(
            client, model, train_queries[:5], train_cpts[:5],
            test_queries, cpts_map, use_core_ops=False,
        )
        results["compile_free"] = r

    # Core-ops Constrained
    if mode in ("all", "core_ops"):
        print(f"\n  [3] Core-ops Constrained...")
        r = await compile_time_solver(
            client, model, train_queries[:5], train_cpts[:5],
            test_queries, cpts_map, use_core_ops=True,
        )
        results["compile_core_ops"] = r

    # PAL (per-instance code generation)
    if mode in ("all", "pal"):
        print(f"\n  [PAL] Per-instance code generation...")
        pal_results = []
        pal_semaphore = asyncio.Semaphore(10)

        async def pal_one(q_idx, q):
            nl = format_bn_problem(q, cpts_map[q["network"]])
            qvar = q['query_variable']
            pal_prompt = (
                nl + "\n\n"
                "Write a Python program that computes the exact posterior distribution "
                "P(" + qvar + " | evidence) using variable elimination.\n"
                "The program should:\n"
                "1. Define all CPTs as dictionaries\n"
                "2. Implement variable elimination\n"
                "3. Print ONLY the most likely value of " + qvar + " as the last line "
                "(just the value name, nothing else)\n\n"
                "Output the complete Python code in a ```python code block."
            )
            async with pal_semaphore:
                try:
                    resp = await client.chat.completions.create(
                        model=model,
                        messages=[{"role": "user", "content": pal_prompt}],
                        max_tokens=4096, temperature=0.0,
                    )
                    code = extract_code_block(resp.choices[0].message.content or "")
                    if not code:
                        code = resp.choices[0].message.content or ""
                except Exception as e:
                    return {"correct": False, "error": "API: " + str(e)}

            success, stdout, stderr = execute_python_code(code, timeout=30)
            if not success:
                return {"correct": False, "error": "exec: " + stderr[:150], "code_ok": False}

            pred = stdout.strip().split("\n")[-1].strip() if stdout.strip() else ""
            correct = pred.lower() == str(q["gold_answer"]).lower()
            return {"correct": correct, "pred": pred, "gold": q["gold_answer"], "code_ok": True}

        tasks = [pal_one(i, q) for i, q in enumerate(test_queries)]
        pal_raw = await asyncio.gather(*tasks)

        for i, r in enumerate(pal_raw):
            pal_results.append(r.get("correct", False))
            if (i + 1) % 20 == 0:
                acc = sum(pal_results) / len(pal_results)
                print(f"    进度: {i+1}/{len(test_queries)}, 准确率: {acc*100:.1f}%")

        n_code_ok = sum(1 for r in pal_raw if r.get("code_ok", False))
        results["pal"] = {
            "accuracy": sum(pal_results) / len(pal_results),
            "n_correct": sum(pal_results),
            "n_total": len(pal_results),
            "code_success_rate": n_code_ok / len(pal_results) if pal_results else 0,
        }
        print(f"    PAL: {results['pal']['accuracy']*100:.1f}% (code success: {results['pal']['code_success_rate']*100:.1f}%)")

        # per-network PAL breakdown
        for net_name in NETWORKS:
            net_indices = [i for i, q in enumerate(test_queries) if q["network"] == net_name]
            if net_indices:
                net_correct = sum(1 for i in net_indices if pal_raw[i].get("correct", False))
                net_code_ok = sum(1 for i in net_indices if pal_raw[i].get("code_ok", False))
                print(f"      {net_name} ({len(net_indices)}q): {net_correct}/{len(net_indices)} ({net_correct/len(net_indices)*100:.0f}%), code ok: {net_code_ok}")

    # PCD (Compute + Decide only, skip Parse since structure is given)
    if mode in ("all", "pcd"):
        print(f"\n  [4] PCD (Compute + Decide)...")
        compute_results = []
        decide_results = []
        for i, q in enumerate(test_queries):
            cr = await pcd_compute(client, model, q, cpts_map[q["network"]])
            dr = await pcd_decide(client, model, q)
            compute_results.append(cr.get("correct", False))
            decide_results.append(dr.get("correct", False))
            if (i + 1) % 20 == 0:
                ca = sum(compute_results) / len(compute_results)
                da = sum(decide_results) / len(decide_results)
                print(f"    进度: {i+1}/{len(test_queries)}, Compute={ca*100:.0f}% Decide={da*100:.0f}%")

        results["pcd"] = {
            "compute_accuracy": sum(compute_results) / len(compute_results),
            "decide_accuracy": sum(decide_results) / len(decide_results),
            "n_total": len(compute_results),
        }
        print(f"    PCD: Compute={results['pcd']['compute_accuracy']*100:.1f}% Decide={results['pcd']['decide_accuracy']*100:.1f}%")

    # Per-network breakdown
    for net_name in NETWORKS:
        net_test = [q for q in test_queries if q["network"] == net_name]
        results[f"n_test_{net_name}"] = len(net_test)

    # 保存
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    model_tag = model.replace("/", "_")
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_file = RESULTS_DIR / f"bnlearn_{model_tag}_{ts}.json"
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    print(f"\n  保存: {out_file}")

    # 汇总
    print(f"\n{'='*60}")
    print(f"bnlearn Held-out 汇总 — {model}")
    print(f"{'='*60}")
    for key, val in results.items():
        if isinstance(val, dict) and "accuracy" in val:
            print(f"  {key}: {val['accuracy']*100:.1f}%")
        elif isinstance(val, dict) and "compute_accuracy" in val:
            print(f"  PCD: Compute={val['compute_accuracy']*100:.1f}% Decide={val['decide_accuracy']*100:.1f}%")

    return results


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="bnlearn 经典 BN 网络 Held-out")
    parser.add_argument("--model", "-m", default="openai/gpt-4o-mini")
    parser.add_argument("--queries-per-net", type=int, default=30)
    parser.add_argument("--mode", choices=["all", "direct", "compile", "core_ops", "pal", "pcd"], default="all")
    parser.add_argument("--seed", type=int, default=2026)
    args = parser.parse_args()

    asyncio.run(run_experiment(args.model, args.queries_per_net, args.mode, args.seed))
