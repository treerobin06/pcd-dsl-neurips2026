#!/usr/bin/env python3
"""Debug: 对比 GPT-5.4 和 GPT-4o-mini 在 bnlearn 大 BN 上的 PAL 代码"""

import os
import sys
import json
import random
import asyncio
import subprocess
import tempfile
import re

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

import httpx
from openai import AsyncOpenAI

# 复用 bnlearn 的数据生成
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from run_bnlearn_held_out import generate_queries_from_network, format_bn_problem, execute_python_code, extract_code_block


def get_client():
    api_key = os.environ.get("OPENROUTER_API_KEY")
    proxy = os.environ.get("HTTPS_PROXY", os.environ.get("HTTP_PROXY", "http://127.0.0.1:7897"))
    return AsyncOpenAI(
        base_url="https://openrouter.ai/api/v1",
        api_key=api_key,
        http_client=httpx.AsyncClient(proxy=proxy, timeout=300),
    )


async def debug_one_query(client, model, query, cpts, idx):
    """在单个 query 上跑 PAL 并展示生成的代码"""
    nl = format_bn_problem(query, cpts)
    qvar = query['query_variable']
    prompt = (
        nl + "\n\n"
        "Write a Python program that computes the exact posterior distribution "
        "P(" + qvar + " | evidence) using variable elimination.\n"
        "The program should:\n"
        "1. Define all CPTs as dictionaries\n"
        "2. Implement variable elimination\n"
        "3. Print ONLY the most likely value of " + qvar + " as the last line\n\n```python\n"
    )

    try:
        resp = await client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=4096, temperature=0.0,
        )
        raw_resp = resp.choices[0].message.content or ""
        code = extract_code_block(raw_resp)
        if not code:
            code = raw_resp
    except Exception as e:
        return {"error": f"API: {e}", "code": None}

    # 执行
    success, stdout, stderr = execute_python_code(code, timeout=30)
    pred = stdout.strip().split("\n")[-1].strip() if stdout.strip() else ""
    correct = pred.lower() == str(query["gold_answer"]).lower()

    return {
        "correct": correct,
        "pred": pred,
        "gold": query["gold_answer"],
        "code_ok": success,
        "code_len": len(code),
        "code_first_200": code[:200],
        "stderr_first_200": stderr[:200] if stderr else "",
        "stdout": stdout[:200] if stdout else "",
    }


async def main():
    client = get_client()

    # 对每个网络取 3 个 query 做对比
    for net_name in ["insurance", "alarm", "child"]:
        queries, cpts = generate_queries_from_network(net_name, 6, seed=2026)
        test_queries = queries[3:6]  # 和实验用的同一批（跳过前 3 个 train）

        print(f"\n{'='*70}")
        print(f"网络: {net_name} ({queries[0]['n_nodes']} 节点, {queries[0]['n_edges']} 边)")
        print(f"{'='*70}")

        for i, q in enumerate(test_queries[:3]):
            print(f"\n--- Query {i}: P({q['query_variable']} | {q['evidence']}) ---")
            print(f"Gold answer: {q['gold_answer']}")

            for model in ["openai/gpt-4o-mini", "openai/gpt-5.4"]:
                r = await debug_one_query(client, model, q, cpts, i)
                model_short = model.split("/")[-1]
                status = "✓" if r.get("correct") else "✗"
                code_ok = "exec OK" if r.get("code_ok") else "exec FAIL"

                print(f"\n  [{model_short}] {status} pred={r.get('pred', '?')} | {code_ok} | code_len={r.get('code_len', '?')}")
                if not r.get("code_ok"):
                    print(f"    stderr: {r.get('stderr_first_200', '')}")
                print(f"    code start: {r.get('code_first_200', '')}")


if __name__ == "__main__":
    asyncio.run(main())
