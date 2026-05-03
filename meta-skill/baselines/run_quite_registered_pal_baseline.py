#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""PAL baseline on the QUITE registered hard-compute split.

The split is identical to ``run_quite_registered_e2e.py``. PAL still receives
the natural-language QUITE premises and must generate per-instance Python code
to compute the posterior, so this is a direct test of per-query code generation
under parse-simple / compute-hard QUITE cases.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import math
import os
import re
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import httpx
from openai import AsyncOpenAI

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from _artifact_schema import accumulate_usage, save_artifact
from run_quite_direct_baseline import HARD_COMPUTE_PRESETS


SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parents[1]
QUITE_DIR = REPO_ROOT / "data" / "external" / "QUITE" / "data" / "quite-corpus" / "data"
RESULTS_DIR = SCRIPT_DIR / "results"


def load_dotenv(path: Path) -> None:
    if not path.exists():
        return
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def make_client() -> AsyncOpenAI:
    load_dotenv(REPO_ROOT / "meta-skill" / ".env")
    api_key = os.environ.get("OPENROUTER_API_KEY")
    if not api_key:
        raise RuntimeError("OPENROUTER_API_KEY is not set")
    proxy = os.environ.get("HTTPS_PROXY", os.environ.get("HTTP_PROXY", "http://127.0.0.1:7897"))
    return AsyncOpenAI(
        base_url="https://openrouter.ai/api/v1",
        api_key=api_key,
        http_client=httpx.AsyncClient(proxy=proxy, timeout=300),
    )


def extract_code_block(text: str) -> str:
    match = re.search(r"```(?:python)?\s*(.*?)```", text, flags=re.S)
    if match:
        return match.group(1).strip()
    if "print(" in text or "import " in text or "def " in text:
        return text.strip()
    return ""


def extract_probability(stdout: str) -> Optional[float]:
    stdout = stdout.strip()
    if not stdout:
        return None
    try:
        obj = json.loads(stdout)
        if isinstance(obj, dict):
            value = obj.get("probability", obj.get("answer", obj.get("p")))
            return float(value)
        return float(obj)
    except Exception:
        pass
    numbers = re.findall(r"[-+]?(?:\d*\.\d+|\d+)(?:[eE][-+]?\d+)?", stdout)
    if not numbers:
        return None
    try:
        return float(numbers[-1])
    except ValueError:
        return None


def execute_python(code: str, timeout: int) -> Tuple[bool, str, str]:
    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False, encoding="utf-8") as f:
        f.write(code)
        tmp_path = f.name
    try:
        result = subprocess.run(
            [sys.executable, tmp_path],
            capture_output=True,
            text=True,
            timeout=timeout,
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
    except Exception as exc:
        return False, "", str(exc)
    finally:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass


def load_items(query_plan: Dict[str, List[int]]) -> List[Dict[str, Any]]:
    items: List[Dict[str, Any]] = []
    for network, qids in query_plan.items():
        data = json.loads((QUITE_DIR / f"{network}.json").read_text(encoding="utf-8"))
        premises = [p["content"] for p in data["numeric_premises"]]
        by_id = {int(pair["id"]): pair for pair in data["evidence_query_pairs"]}
        for qid in qids:
            pair = by_id[qid]
            answer = float(pair["answer"])
            if not (0 <= answer <= 1 and math.isfinite(answer)):
                continue
            items.append(
                {
                    "network": network,
                    "pair_id": qid,
                    "premises": premises,
                    "evidences": pair.get("evidences", []),
                    "query": pair["query"],
                    "gold": answer,
                    "reasoning_types": pair.get("reasoning_types", []),
                }
            )
    return items


def pal_prompt(item: Dict[str, Any]) -> str:
    premise_text = "\n".join(f"- {p}" for p in item["premises"])
    evidence_text = "\n".join(f"- {e}" for e in item["evidences"]) or "- None"
    return f"""Write a self-contained Python program that computes one Bayesian-network posterior probability exactly enough for evaluation.

Use only the probability premises below. Do not guess from prior knowledge.
The program may enumerate all hidden variable assignments or implement variable
elimination. It must finally print a single JSON object:
{{"probability": <number between 0 and 1>}}

Premises:
{premise_text}

Evidence:
{evidence_text}

Query:
{item['query']}

Return ONLY Python code in one code block.
"""


def usage_dict(usage_obj: Any) -> Dict[str, Any]:
    usage = accumulate_usage(usage_obj)
    usage["cost_usd"] = float(getattr(usage_obj, "cost", 0) or 0)
    return usage


async def run_one(
    client: AsyncOpenAI,
    sema: asyncio.Semaphore,
    model: str,
    item: Dict[str, Any],
    timeout: int,
) -> Dict[str, Any]:
    async with sema:
        try:
            resp = await client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": pal_prompt(item)}],
                max_tokens=4096,
                temperature=0.0,
            )
            raw = resp.choices[0].message.content or ""
            usage = usage_dict(resp.usage)
        except Exception as exc:
            return {
                **{k: item[k] for k in ["network", "pair_id", "gold", "reasoning_types"]},
                "pred": None,
                "abs_error": None,
                "within_0_01": False,
                "within_0_05": False,
                "code_ok": False,
                "failure_mode": "api_error",
                "error": str(exc)[:500],
                "usage": {"prompt_tokens": 0, "completion_tokens": 0, "cost_usd": 0.0},
                "stdout": "",
                "stderr": "",
                "code": "",
                "raw_response": "",
            }

    code = extract_code_block(raw)
    if not code:
        success, stdout, stderr = False, "", "no_code_block"
    else:
        success, stdout, stderr = execute_python(code, timeout=timeout)
    pred = extract_probability(stdout) if success else None
    if pred is not None and not (0.0 <= pred <= 1.0 and math.isfinite(pred)):
        pred = None
    abs_error = abs(pred - item["gold"]) if pred is not None else None
    failure_mode = None
    if not success:
        failure_mode = "exec_failed"
    elif pred is None:
        failure_mode = "no_numeric_probability"
    elif abs_error is not None and abs_error > 0.05:
        failure_mode = "wrong_probability"
    return {
        **{k: item[k] for k in ["network", "pair_id", "gold", "reasoning_types"]},
        "pred": pred,
        "abs_error": abs_error,
        "within_0_01": abs_error is not None and abs_error <= 0.01,
        "within_0_05": abs_error is not None and abs_error <= 0.05,
        "code_ok": success and pred is not None,
        "failure_mode": failure_mode,
        "error": stderr[:1000],
        "usage": usage,
        "stdout": stdout[:1000],
        "stderr": stderr[:1000],
        "code": code,
        "raw_response": raw,
    }


def summarize(rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    n = len(rows)
    valid = [r for r in rows if r["abs_error"] is not None]
    by_network: Dict[str, Dict[str, Any]] = {}
    for row in rows:
        b = by_network.setdefault(row["network"], {"n": 0, "correct": 0, "code_ok": 0, "failures": {}})
        b["n"] += 1
        b["correct"] += int(row["within_0_05"])
        b["code_ok"] += int(row["code_ok"])
        if not row["within_0_05"]:
            key = row["failure_mode"] or "unknown"
            b["failures"][key] = b["failures"].get(key, 0) + 1
    return {
        "n": n,
        "code_ok": sum(r["code_ok"] for r in rows),
        "code_ok_rate": sum(r["code_ok"] for r in rows) / n if n else 0.0,
        "within_0_01": sum(r["within_0_01"] for r in rows),
        "within_0_01_rate": sum(r["within_0_01"] for r in rows) / n if n else 0.0,
        "within_0_05": sum(r["within_0_05"] for r in rows),
        "within_0_05_rate": sum(r["within_0_05"] for r in rows) / n if n else 0.0,
        "mae": sum(r["abs_error"] for r in valid) / len(valid) if valid else None,
        "by_network": by_network,
    }


async def main() -> None:
    parser = argparse.ArgumentParser(description="QUITE hard-compute PAL baseline")
    parser.add_argument("--model", default=os.environ.get("MODEL", "openai/gpt-4o-mini"))
    parser.add_argument("--preset", choices=sorted(HARD_COMPUTE_PRESETS), default="hard-compute-clean")
    parser.add_argument("--sema", type=int, default=4)
    parser.add_argument("--timeout", type=int, default=20)
    args = parser.parse_args()

    query_plan = HARD_COMPUTE_PRESETS[args.preset]
    items = load_items(query_plan)
    client = make_client()
    sema = asyncio.Semaphore(args.sema)
    t0 = time.time()
    print(f"=== QUITE hard-compute PAL | model={args.model} preset={args.preset} n={len(items)} ===")
    rows = await asyncio.gather(*(run_one(client, sema, args.model, item, args.timeout) for item in items))
    elapsed = time.time() - t0
    summary = summarize(rows)
    prompt_tokens = sum(r["usage"].get("prompt_tokens", 0) for r in rows)
    completion_tokens = sum(r["usage"].get("completion_tokens", 0) for r in rows)
    total_cost_usd = sum(r["usage"].get("cost_usd", 0.0) for r in rows)
    print(f"Elapsed: {elapsed:.1f}s")
    print(
        f"code_ok {summary['code_ok']}/{summary['n']}={summary['code_ok_rate']*100:.1f}%, "
        f"<=0.05 {summary['within_0_05']}/{summary['n']}={summary['within_0_05_rate']*100:.1f}%, "
        f"MAE={summary['mae']}"
    )
    print(f"Total cost: ${total_cost_usd:.6f}")

    out = {
        "experiment": "QUITE hard-compute PAL baseline",
        "model": args.model,
        "config": vars(args),
        "query_plan": query_plan,
        "elapsed_sec": elapsed,
        "summary": summary,
        "results": rows,
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    model_tag = args.model.replace("/", "_")
    out_path = RESULTS_DIR / f"quite_registered_hard_compute_pal_{model_tag}_{time.strftime('%Y%m%d_%H%M%S')}.json"
    save_artifact(
        out_path,
        out,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        total_cost_usd=total_cost_usd if total_cost_usd > 0 else None,
        model_id=args.model,
        extra_meta={
            "script": "baselines/run_quite_registered_pal_baseline.py",
            "n_queries": len(rows),
            "preset": args.preset,
        },
    )
    print(f"Saved: {out_path}")


if __name__ == "__main__":
    asyncio.run(main())
