#!/usr/bin/env python3
"""Structured-output direct-answer baselines.

This isolates the reviewer concern "maybe JSON constraints, not the compiled
solver, explain the E2E gain."  The LLM must return a strict JSON answer, but
it receives no compiled solver and must perform the probabilistic computation
itself.
"""

from __future__ import annotations

import argparse
import asyncio
import csv
import json
import os
import random
import re
import sys
import time
from datetime import datetime, timezone
from math import sqrt
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import httpx
from openai import AsyncOpenAI

SCRIPT_DIR = Path(__file__).parent
PROJECT_ROOT = SCRIPT_DIR.parent.parent
RESULTS_DIR = SCRIPT_DIR / "results"

sys.path.insert(0, str(SCRIPT_DIR.parent))
sys.path.insert(0, str(SCRIPT_DIR))

from baselines._artifact_schema import accumulate_usage, save_artifact
from baselines.run_held_out_family import generate_naive_bayes_problem
from baselines.run_hmm_held_out import generate_hmm_problem
from baselines.run_mixed_e2e import blind_nl_sample
from baselines.run_nl_e2e_stress import nb_adversarial_sample, hmm_adversarial_sample


def load_dotenv_if_present() -> None:
    env_path = SCRIPT_DIR.parent / ".env"
    if not env_path.exists():
        return
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip("'\""))


def get_client() -> AsyncOpenAI:
    load_dotenv_if_present()
    api_key = os.environ.get("OPENROUTER_API_KEY")
    if not api_key:
        raise RuntimeError("OPENROUTER_API_KEY 环境变量未设置")
    proxy = os.environ.get("HTTPS_PROXY", os.environ.get("HTTP_PROXY", "http://127.0.0.1:7897"))
    return AsyncOpenAI(
        base_url="https://openrouter.ai/api/v1",
        api_key=api_key,
        http_client=httpx.AsyncClient(proxy=proxy, timeout=300),
    )


def usage_dict(usage_obj: Any) -> Dict[str, Any]:
    usage = accumulate_usage(usage_obj)
    usage["cost_usd"] = float(getattr(usage_obj, "cost", 0) or 0)
    return usage


def zero_usage() -> Dict[str, Any]:
    return {"prompt_tokens": 0, "completion_tokens": 0, "cost_usd": 0.0}


def extract_json_obj(text: str) -> Optional[Dict[str, Any]]:
    match = re.search(r"```(?:json)?\s*\n(.*?)```", text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(1).strip())
        except json.JSONDecodeError:
            pass
    try:
        return json.loads(text.strip())
    except json.JSONDecodeError:
        pass
    start = text.find("{")
    end = text.rfind("}")
    if start >= 0 and end > start:
        try:
            return json.loads(text[start : end + 1])
        except json.JSONDecodeError:
            pass
    return None


def parse_probability(value: Any) -> Optional[float]:
    if isinstance(value, (int, float)):
        x = float(value)
    elif isinstance(value, str):
        nums = re.findall(r"-?\d+(?:\.\d+)?", value)
        if not nums:
            return None
        x = float(nums[-1])
    else:
        return None
    if x > 1.0 and x <= 100.0:
        x /= 100.0
    if x < 0.0 or x > 1.0:
        return None
    return x


def norm_label(x: Any) -> str:
    return re.sub(r"\s+", " ", str(x or "")).strip().lower()


def wilson(k: int, n: int) -> Tuple[float, float]:
    if n == 0:
        return (0.0, 1.0)
    z = 1.96
    p = k / n
    denom = 1 + z ** 2 / n
    center = (p + z ** 2 / (2 * n)) / denom
    margin = z * sqrt(p * (1 - p) / n + z ** 2 / (4 * n ** 2)) / denom
    return (max(0.0, center - margin), min(1.0, center + margin))


def load_blind_depth(n: int, seed: int, depth: Optional[int]) -> List[Dict[str, Any]]:
    path = PROJECT_ROOT / "data" / "external" / "BLInD" / "datasets" / "Base_1000_examples.csv"
    rows: List[Dict[str, Any]] = []
    with path.open(encoding="utf-8") as f:
        for row in csv.DictReader(f):
            if depth is None or int(row.get("depth", -1)) == depth:
                rows.append(row)
    rng = random.Random(seed)
    rng.shuffle(rows)
    return rows[:n]


def build_nb_task(i: int, base_seed: int) -> Dict[str, Any]:
    seed = base_seed + i
    problem = generate_naive_bayes_problem(n_diseases=4, n_symptoms=6, seed=seed)
    sample = nb_adversarial_sample(problem, random.Random(seed + 99999))
    allowed = list(problem["diseases"])
    prompt = f"""You are solving a Naive Bayes diagnosis task.

Read the task, compute the posterior probabilities yourself, and return ONLY JSON.
Do not write code. Do not call tools. The answer must be one of: {allowed}.

Required JSON schema:
{{
  "family": "naive_bayes",
  "answer": "one disease label from the allowed list",
  "posterior": {{"disease": probability}},
  "brief_reason": "short calculation summary"
}}

Task:
{json.dumps(sample, ensure_ascii=False, indent=2)}
"""
    return {
        "family": "nb",
        "i": i,
        "seed": seed,
        "prompt": prompt,
        "gold": problem["gold_diagnosis"],
        "source": {"problem": problem, "sample": sample},
    }


def build_hmm_task(i: int, base_seed: int) -> Dict[str, Any]:
    seed = base_seed + i
    problem = generate_hmm_problem(n_states=4, n_obs=5, seq_length=8, seed=seed)
    sample = hmm_adversarial_sample(problem, random.Random(seed + 99999))
    allowed = list(problem["states"])
    prompt = f"""You are solving a Hidden Markov Model forward-filtering task.

Read the task, run the forward algorithm yourself, and return ONLY JSON.
Do not write code. Do not call tools. The answer must be one of: {allowed}.

Required JSON schema:
{{
  "family": "hmm_forward",
  "answer": "one hidden state from the allowed list",
  "posterior": {{"state": probability}},
  "brief_reason": "short calculation summary"
}}

Task:
{json.dumps(sample, ensure_ascii=False, indent=2)}
"""
    return {
        "family": "hmm",
        "i": i,
        "seed": seed,
        "prompt": prompt,
        "gold": problem["gold_state"],
        "source": {"problem": problem, "sample": sample},
    }


def build_blind_task(i: int, row: Dict[str, Any]) -> Dict[str, Any]:
    sample = blind_nl_sample(row)
    prompt = f"""You are solving a Bayesian-network probability query.

Read the network, CPTs, evidence, and query. Compute the requested probability
yourself and return ONLY JSON. Do not write code. Do not call tools.

Required JSON schema:
{{
  "family": "variable_elimination",
  "answer_probability": number between 0 and 1,
  "brief_reason": "short calculation summary"
}}

Task:
{json.dumps(sample, ensure_ascii=False, indent=2)}
"""
    return {
        "family": "blind",
        "i": i,
        "seed": row.get("index", i),
        "prompt": prompt,
        "gold": float(row["answers"]),
        "source": {"row": row, "sample": sample},
    }


async def run_one(
    client: AsyncOpenAI,
    sema: asyncio.Semaphore,
    model: str,
    task: Dict[str, Any],
) -> Dict[str, Any]:
    async with sema:
        try:
            resp = await client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": task["prompt"]}],
                temperature=0.0,
                max_tokens=2048,
            )
            text = resp.choices[0].message.content or ""
            usage = usage_dict(resp.usage)
            api_error = None
        except Exception as e:
            text = ""
            usage = zero_usage()
            api_error = str(e)[:240]

    obj = extract_json_obj(text) if text else None
    pred: Any = None
    ok = False
    parse_error = None
    if obj is None:
        parse_error = api_error or "json_parse_fail"
    elif task["family"] == "blind":
        pred = parse_probability(obj.get("answer_probability", obj.get("answer")))
        ok = pred is not None and abs(float(pred) - float(task["gold"])) < 0.01
    else:
        pred = obj.get("answer", obj.get("diagnosis", obj.get("state")))
        ok = norm_label(pred) == norm_label(task["gold"])

    return {
        "family": task["family"],
        "i": task["i"],
        "seed": task["seed"],
        "pred": pred,
        "gold": task["gold"],
        "ok": bool(ok),
        "parse_error": parse_error,
        "response_json": obj,
        "raw_response": text[:4000],
        "usage": usage,
    }


def summarize(rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    for family in sorted({r["family"] for r in rows}):
        fam_rows = [r for r in rows if r["family"] == family]
        k = sum(1 for r in fam_rows if r["ok"])
        n = len(fam_rows)
        lo, hi = wilson(k, n)
        out[family] = {
            "n": n,
            "correct": k,
            "accuracy": k / n if n else 0.0,
            "wilson_95ci": [lo, hi],
            "parse_failures": sum(1 for r in fam_rows if r.get("parse_error")),
        }
    k_all = sum(1 for r in rows if r["ok"])
    n_all = len(rows)
    lo, hi = wilson(k_all, n_all)
    out["overall"] = {"n": n_all, "correct": k_all, "accuracy": k_all / n_all, "wilson_95ci": [lo, hi]}
    return out


async def main_async(args: argparse.Namespace) -> None:
    client = get_client()
    tasks: List[Dict[str, Any]] = []
    for i in range(args.n_nb):
        tasks.append(build_nb_task(i, args.nb_base_seed))
    for i in range(args.n_hmm):
        tasks.append(build_hmm_task(i, args.hmm_base_seed))
    blind_rows = load_blind_depth(args.n_blind, args.blind_seed, args.blind_depth)
    for i, row in enumerate(blind_rows):
        tasks.append(build_blind_task(i, row))

    rng = random.Random(args.shuffle_seed)
    rng.shuffle(tasks)
    print(
        f"=== structured direct baseline | model={args.model} | "
        f"nb={args.n_nb} hmm={args.n_hmm} blind={len(blind_rows)} depth={args.blind_depth} ==="
    )
    started = time.time()
    sema = asyncio.Semaphore(args.sema)
    rows = await asyncio.gather(*[run_one(client, sema, args.model, task) for task in tasks])
    elapsed = time.time() - started
    summary = summarize(rows)

    for family, stats in summary.items():
        print(
            f"{family}: {stats['correct']}/{stats['n']} = {stats['accuracy']*100:.1f}%"
            if family != "overall"
            else f"overall: {stats['correct']}/{stats['n']} = {stats['accuracy']*100:.1f}%"
        )
    print(f"Elapsed: {elapsed:.1f}s")

    prompt_tokens = sum(int(r["usage"].get("prompt_tokens", 0)) for r in rows)
    completion_tokens = sum(int(r["usage"].get("completion_tokens", 0)) for r in rows)
    total_cost = sum(float(r["usage"].get("cost_usd", 0.0)) for r in rows)
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    path = RESULTS_DIR / f"structured_direct_{args.model.replace('/', '_')}_{ts}.json"
    save_artifact(
        str(path),
        {
            "experiment": "structured_output_direct_answer",
            "model": args.model,
            "elapsed_sec": elapsed,
            "config": vars(args),
            "summary": summary,
            "results": rows,
        },
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        total_cost_usd=total_cost if total_cost > 0 else None,
        model_id=args.model,
        extra_meta={
            "script": "baselines/run_structured_direct_baseline.py",
            "n_total": len(rows),
        },
    )
    print(f"Saved: {path}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Structured JSON direct-answer baseline")
    parser.add_argument("--model", default=os.environ.get("MODEL", "openai/gpt-4o-mini"))
    parser.add_argument("--n-nb", type=int, default=120)
    parser.add_argument("--n-hmm", type=int, default=100)
    parser.add_argument("--n-blind", type=int, default=100)
    parser.add_argument("--blind-depth", type=int, default=10)
    parser.add_argument("--nb-base-seed", type=int, default=7000)
    parser.add_argument("--hmm-base-seed", type=int, default=8000)
    parser.add_argument("--blind-seed", type=int, default=2026)
    parser.add_argument("--shuffle-seed", type=int, default=2026)
    parser.add_argument("--sema", type=int, default=int(os.environ.get("SEMA", "20")))
    args = parser.parse_args()
    asyncio.run(main_async(args))


if __name__ == "__main__":
    main()
