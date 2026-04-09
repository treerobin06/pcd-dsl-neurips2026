#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
快速测试: CLadder 因果推断 + POMDP Tiger Problem

目的: 验证 DSL core ops 能否覆盖这两类新任务，
以及 inductor（core-ops constrained code gen）能否成功。

CLadder:
  Rung 1 (关联): P(Y|X) — 标准 VE，应该能过
  Rung 2 (介入): P(Y|do(X)) — 需要截断因子化，可能失败

POMDP Tiger:
  信念更新 + 决策 — 操作链最长(7-8步)，可能失败
"""

import os
import sys
import json
import math
import asyncio
import subprocess
import tempfile
from typing import Dict, List, Tuple

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

import httpx
from openai import AsyncOpenAI

# OpenRouter 客户端
def get_client() -> AsyncOpenAI:
    api_key = os.environ.get("OPENROUTER_API_KEY")
    proxy = os.environ.get("HTTPS_PROXY", os.environ.get("HTTP_PROXY", "http://127.0.0.1:7897"))
    return AsyncOpenAI(
        base_url="https://openrouter.ai/api/v1",
        api_key=api_key,
        http_client=httpx.AsyncClient(proxy=proxy, timeout=300),
    )


# =============================================
# DSL Core Ops 定义（给 LLM 的参考文档）
# =============================================
CORE_OPS_DOC = """
# DSL Core Operations (7 typed ops)

Available functions (import from dsl.core_ops):

1. normalize(factor: Dict) -> Dict
   Divides all values by their sum. Returns a probability distribution.

2. multiply_factors(factors: List[Dict]) -> Dict
   Pointwise product of factors, aligning shared variables.
   Each factor is {(var_assignments_tuple): value, ...}

3. marginalize(factor: Dict, variables: Set[str]) -> Dict
   Sums out the specified variables from a factor.

4. condition(factor: Dict, evidence: Dict[str, Any]) -> Dict
   Retains only entries consistent with the evidence.

5. enumerate_hypotheses(dimensions: Dict[str, List]) -> List[Dict]
   Generates all combinations from a Cartesian product of dimension values.

6. expectation(distribution: Dict, func) -> float
   Computes E_p[f(x)] = sum(p(x) * f(x) for x in support).

7. argmax(scores: Dict) -> Any
   Returns the key with the highest value.

These are PURE FUNCTIONS. No side effects, no LLM calls.
You can compose them freely to implement any discrete exact inference algorithm.
"""


# =============================================
# CLadder: 因果推断问题生成
# =============================================

def generate_cladder_problems() -> List[Dict]:
    """生成简单的因果推断问题（2-3变量BN）"""
    problems = []

    # === Rung 1: 关联查询 P(Y|X) ===
    # 简单 BN: X -> Y, P(X=1)=0.3, P(Y=1|X=1)=0.8, P(Y=1|X=0)=0.2
    problems.append({
        "rung": 1,
        "description": "Causal graph: X -> Y. P(X=1)=0.3. P(Y=1|X=1)=0.8, P(Y=1|X=0)=0.2. What is P(Y=1|X=1)?",
        "query": "P(Y=1|X=1)",
        "gold_answer": 0.8,
    })

    # Rung 1 with confounder: X <- Z -> Y, X -> Y
    # P(Z=1)=0.5, P(X=1|Z=1)=0.9, P(X=1|Z=0)=0.1
    # P(Y=1|X=1,Z=1)=0.9, P(Y=1|X=1,Z=0)=0.6, P(Y=1|X=0,Z=1)=0.4, P(Y=1|X=0,Z=0)=0.1
    # P(Y=1|X=1) = P(Y=1|X=1,Z=1)P(Z=1|X=1) + P(Y=1|X=1,Z=0)P(Z=0|X=1)
    pz1 = 0.5
    px1_z1, px1_z0 = 0.9, 0.1
    px1 = px1_z1 * pz1 + px1_z0 * (1 - pz1)  # 0.5
    pz1_x1 = px1_z1 * pz1 / px1  # 0.9
    py1_x1 = 0.9 * pz1_x1 + 0.6 * (1 - pz1_x1)  # 0.87

    problems.append({
        "rung": 1,
        "description": f"Causal graph: Z -> X, Z -> Y, X -> Y. P(Z=1)=0.5. P(X=1|Z=1)=0.9, P(X=1|Z=0)=0.1. P(Y=1|X=1,Z=1)=0.9, P(Y=1|X=1,Z=0)=0.6, P(Y=1|X=0,Z=1)=0.4, P(Y=1|X=0,Z=0)=0.1. What is P(Y=1|X=1)?",
        "query": "P(Y=1|X=1)",
        "gold_answer": round(py1_x1, 4),
    })

    # === Rung 2: 介入查询 P(Y|do(X)) ===
    # 同一个 confounder 图，但问 P(Y=1|do(X=1))
    # do(X=1): 删除 Z->X 边，固定 X=1
    # P(Y=1|do(X=1)) = sum_z P(Y=1|X=1,Z=z) * P(Z=z)
    #                = 0.9*0.5 + 0.6*0.5 = 0.75
    problems.append({
        "rung": 2,
        "description": f"Causal graph: Z -> X, Z -> Y, X -> Y. P(Z=1)=0.5. P(X=1|Z=1)=0.9, P(X=1|Z=0)=0.1. P(Y=1|X=1,Z=1)=0.9, P(Y=1|X=1,Z=0)=0.6, P(Y=1|X=0,Z=1)=0.4, P(Y=1|X=0,Z=0)=0.1. What is P(Y=1|do(X=1))? Note: do(X=1) means we intervene to set X=1, removing all incoming edges to X.",
        "query": "P(Y=1|do(X=1))",
        "gold_answer": 0.75,
    })

    # Rung 2: 另一个 do 查询
    # P(Y=1|do(X=0)) = 0.4*0.5 + 0.1*0.5 = 0.25
    problems.append({
        "rung": 2,
        "description": f"Causal graph: Z -> X, Z -> Y, X -> Y. Same parameters as above. What is P(Y=1|do(X=0))?",
        "query": "P(Y=1|do(X=0))",
        "gold_answer": 0.25,
    })

    return problems


# =============================================
# POMDP Tiger Problem 生成
# =============================================

def generate_tiger_problems() -> List[Dict]:
    """生成 Tiger Problem POMDP 实例"""
    problems = []

    # Tiger Problem 参数
    # States: tiger_left, tiger_right (uniform prior)
    # Actions: listen, open_left, open_right
    # Observations: hear_left, hear_right
    # P(hear_left | tiger_left) = 0.85, P(hear_right | tiger_left) = 0.15
    # P(hear_left | tiger_right) = 0.15, P(hear_right | tiger_right) = 0.85
    # Rewards: listen=-1, open_correct=+10, open_tiger=-100

    # 问题1: 1次听到后的信念状态
    # Prior: [0.5, 0.5], 听到 hear_left
    # Posterior: P(TL|HL) = 0.85*0.5 / (0.85*0.5 + 0.15*0.5) = 0.85
    problems.append({
        "type": "belief_update",
        "description": "Tiger Problem POMDP. States: {tiger_left, tiger_right}. Prior: uniform [0.5, 0.5]. Observation model: P(hear_left|tiger_left)=0.85, P(hear_right|tiger_left)=0.15, P(hear_left|tiger_right)=0.15, P(hear_right|tiger_right)=0.85. After action 'listen', observation is 'hear_left'. What is P(tiger_left)?",
        "query": "P(tiger_left | hear_left)",
        "gold_answer": 0.85,
    })

    # 问题2: 2次听到后的信念状态
    # 先听到 hear_left → belief=[0.85, 0.15]
    # 再听到 hear_left → P(TL) = 0.85*0.85 / (0.85*0.85 + 0.15*0.15) = 0.7225/0.745 ≈ 0.9698
    b2 = 0.85 * 0.85 / (0.85 * 0.85 + 0.15 * 0.15)
    problems.append({
        "type": "belief_update",
        "description": "Tiger Problem. Same parameters. After two 'listen' actions, both observations are 'hear_left'. What is P(tiger_left)?",
        "query": "P(tiger_left | hear_left, hear_left)",
        "gold_answer": round(b2, 4),
    })

    # 问题3: 基于信念的最优决策
    # 信念 [0.85, 0.15] 后:
    # E[open_left] = 0.85*(-100) + 0.15*(+10) = -83.5
    # E[open_right] = 0.85*(+10) + 0.15*(-100) = -6.5
    # E[listen] = -1
    # 最优: listen (因为 -1 > -6.5)
    problems.append({
        "type": "decision",
        "description": "Tiger Problem. Belief state: P(tiger_left)=0.85. Rewards: open_left when tiger_left=-100, open_left when tiger_right=+10, open_right when tiger_left=+10, open_right when tiger_right=-100, listen=-1. What is the optimal action?",
        "query": "argmax_a E[reward | belief, action=a]",
        "gold_answer": "listen",
    })

    # 问题4: 高信念下的决策
    # 信念 [0.97, 0.03]:
    # E[open_left] = 0.97*(-100) + 0.03*(+10) = -96.7
    # E[open_right] = 0.97*(+10) + 0.03*(-100) = 6.7
    # E[listen] = -1
    # 最优: open_right
    problems.append({
        "type": "decision",
        "description": "Tiger Problem. Belief state: P(tiger_left)=0.97. Same reward structure. What is the optimal action?",
        "query": "argmax_a E[reward | belief, action=a]",
        "gold_answer": "open_right",
    })

    return problems


# =============================================
# Core-ops constrained code generation + test
# =============================================

SOLVER_PROMPT_TEMPLATE = """You are given a set of probabilistic reasoning problems and a DSL with 7 core operations.
Your task: write a Python function `solve(problem: dict) -> float or str` that solves these problems
using ONLY the core operations listed below.

{core_ops_doc}

Here are example problems to learn from:
{examples}

Requirements:
1. Your function must work on ALL problems of this type
2. You may ONLY use basic Python + the 7 core operations above
3. Return a float (for probability queries) or str (for decision queries)
4. Implement the core ops yourself as simple Python functions (no imports needed)

Output ONLY the Python code, wrapped in ```python ... ```
"""


async def test_core_ops_solver(problems: List[Dict], task_name: str, model: str):
    """让 LLM 用 core ops 写 solver 并测试"""
    client = get_client()

    # 用前 2 个问题作为 examples，测试全部
    examples_text = json.dumps(problems[:2], indent=2, ensure_ascii=False)
    all_problems_text = json.dumps(problems, indent=2, ensure_ascii=False)

    prompt = SOLVER_PROMPT_TEMPLATE.format(
        core_ops_doc=CORE_OPS_DOC,
        examples=examples_text,
    )

    prompt += f"\n\nHere are ALL the problems to solve:\n{all_problems_text}"
    prompt += "\n\nWrite a solve(problem) function that handles all these problems correctly."

    print(f"\n{'='*60}")
    print(f"测试: {task_name} (model: {model})")
    print(f"{'='*60}")

    response = await client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        max_tokens=4096,
        temperature=0.0,
    )

    code = response.choices[0].message.content.strip()

    # 提取代码
    import re
    m = re.search(r'```python\s*\n(.*?)\n```', code, re.DOTALL)
    if m:
        code = m.group(1)

    print(f"\n生成的代码:")
    print(code[:500] + ("..." if len(code) > 500 else ""))

    # 执行测试
    correct = 0
    total = len(problems)
    results = []

    for i, problem in enumerate(problems):
        # 写入临时文件执行
        test_code = code + f"""

import json
problem = json.loads('''{json.dumps(problem)}''')
result = solve(problem)
print(f"RESULT:{{result}}")
"""
        try:
            with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False, encoding='utf-8') as f:
                f.write(test_code)
                tmp_path = f.name

            proc = subprocess.run(
                [sys.executable, tmp_path],
                capture_output=True, text=True, timeout=10,
            )

            if proc.returncode != 0:
                results.append({"problem": i, "status": "exec_error", "error": proc.stderr[:200]})
                print(f"  问题 {i} (Rung {problem.get('rung', '?')}): EXEC_ERROR")
                continue

            # 解析输出
            output = proc.stdout.strip()
            result_line = [l for l in output.split('\n') if l.startswith('RESULT:')]
            if not result_line:
                results.append({"problem": i, "status": "no_output"})
                print(f"  问题 {i}: NO_OUTPUT")
                continue

            result_str = result_line[-1].replace('RESULT:', '').strip()
            gold = problem["gold_answer"]

            if isinstance(gold, (int, float)):
                try:
                    pred = float(result_str)
                    is_correct = abs(pred - gold) < 0.02
                except ValueError:
                    is_correct = False
                    pred = result_str
            else:
                pred = result_str.lower().strip()
                is_correct = pred == str(gold).lower()

            if is_correct:
                correct += 1
            results.append({
                "problem": i,
                "status": "correct" if is_correct else "wrong",
                "pred": str(pred),
                "gold": str(gold),
            })
            rung = problem.get('rung', problem.get('type', '?'))
            status = "✓" if is_correct else f"✗ (pred={pred}, gold={gold})"
            print(f"  问题 {i} ({rung}): {status}")

        except subprocess.TimeoutExpired:
            results.append({"problem": i, "status": "timeout"})
            print(f"  问题 {i}: TIMEOUT")
        except Exception as e:
            results.append({"problem": i, "status": "error", "error": str(e)})
            print(f"  问题 {i}: ERROR {e}")
        finally:
            try:
                os.unlink(tmp_path)
            except:
                pass

    accuracy = correct / total if total > 0 else 0
    print(f"\n  准确率: {correct}/{total} ({accuracy*100:.0f}%)")

    return {
        "task": task_name,
        "model": model,
        "accuracy": accuracy,
        "correct": correct,
        "total": total,
        "results": results,
    }


async def main():
    model = "openai/gpt-4o-mini"

    cladder = generate_cladder_problems()
    tiger = generate_tiger_problems()

    # 并行测试两类任务
    r1, r2 = await asyncio.gather(
        test_core_ops_solver(cladder, "CLadder 因果推断", model),
        test_core_ops_solver(tiger, "POMDP Tiger Problem", model),
    )

    # 也测试 GPT-5.4
    r3, r4 = await asyncio.gather(
        test_core_ops_solver(cladder, "CLadder 因果推断", "openai/gpt-5.4"),
        test_core_ops_solver(tiger, "POMDP Tiger Problem", "openai/gpt-5.4"),
    )

    print(f"\n{'='*60}")
    print("汇总")
    print(f"{'='*60}")
    for r in [r1, r2, r3, r4]:
        print(f"  {r['task']} ({r['model']}): {r['correct']}/{r['total']} ({r['accuracy']*100:.0f}%)")


if __name__ == "__main__":
    asyncio.run(main())
