#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Direct LLM baseline on the QUITE Bayesian-inference corpus.

QUITE is not one of our native evaluation families. This runner only produces a
related-work sanity baseline: given QUITE's natural-language premises, evidence,
and query, ask the same LLM to return a probability directly.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import math
import os
import re
import sys
import time
from pathlib import Path
from typing import Any, Dict, List

import httpx
from openai import AsyncOpenAI

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from _artifact_schema import accumulate_usage, save_artifact


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


def extract_json(text: str) -> Dict[str, Any] | None:
    text = text.strip()
    match = re.search(r"```(?:json)?\s*(.*?)```", text, flags=re.S)
    if match:
        text = match.group(1).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", text, flags=re.S)
        if not match:
            return None
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            return None


def load_items(modes: List[str], limit_per_mode: int | None = None) -> List[Dict[str, Any]]:
    if not QUITE_DIR.exists():
        raise FileNotFoundError(f"QUITE data not found: {QUITE_DIR}")
    items: List[Dict[str, Any]] = []
    for path in sorted(QUITE_DIR.glob("*.json")):
        data = json.loads(path.read_text())
        for mode in modes:
            premise_key = "numeric_premises" if mode == "numeric" else "wep_based_premises"
            premises = [p["content"] for p in data[premise_key]]
            pairs = data["evidence_query_pairs"]
            if limit_per_mode is not None:
                pairs = pairs[:limit_per_mode]
            for pair in pairs:
                items.append(
                    {
                        "network": path.stem,
                        "mode": mode,
                        "pair_id": pair["id"],
                        "premises": premises,
                        "evidences": pair["evidences"],
                        "query": pair["query"],
                        "gold": float(pair["answer"]),
                        "reasoning_types": pair.get("reasoning_types", []),
                    }
                )
    return items


def prompt_for(item: Dict[str, Any]) -> str:
    premise_text = "\n".join(f"- {p}" for p in item["premises"])
    evidence_text = "\n".join(f"- {e}" for e in item["evidences"]) or "- None"
    return f"""You are answering a Bayesian-network inference query from natural-language probability premises.

Use the premises as the model definition. Condition on the evidence, answer the query, and return a probability between 0 and 1.

Premises:
{premise_text}

Evidence:
{evidence_text}

Query:
{item['query']}

Return ONLY JSON:
{{"probability": 0.0, "brief_reason": "one short sentence"}}
"""


async def run_one(client: AsyncOpenAI, sema: asyncio.Semaphore, model: str, item: Dict[str, Any]) -> Dict[str, Any]:
    async with sema:
        try:
            resp = await client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": prompt_for(item)}],
                max_tokens=512,
                temperature=0.0,
            )
            raw = resp.choices[0].message.content or ""
            parsed = extract_json(raw)
            prob = None
            parse_error = None
            if parsed is None:
                parse_error = "json_parse_failed"
            else:
                prob = parsed.get("probability")
                try:
                    prob = float(prob)
                except (TypeError, ValueError):
                    parse_error = "probability_not_numeric"
                    prob = None
            usage = accumulate_usage(resp.usage)
            usage["cost_usd"] = float(getattr(resp.usage, "cost", 0) or 0)
        except Exception as exc:
            raw = ""
            parsed = None
            prob = None
            parse_error = str(exc)[:300]
            usage = {"prompt_tokens": 0, "completion_tokens": 0, "cost_usd": 0.0}

        gold = item["gold"]
        abs_error = abs(prob - gold) if prob is not None and math.isfinite(prob) else None
        return {
            **{k: item[k] for k in ["network", "mode", "pair_id", "gold", "reasoning_types"]},
            "pred": prob,
            "abs_error": abs_error,
            "within_0_01": abs_error is not None and abs_error <= 0.01,
            "within_0_05": abs_error is not None and abs_error <= 0.05,
            "parse_error": parse_error,
            "response_json": parsed,
            "raw_response": raw,
            "usage": usage,
        }


def summarize(rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    valid = [r for r in rows if r["abs_error"] is not None]
    n = len(rows)
    valid_n = len(valid)
    mae = sum(r["abs_error"] for r in valid) / valid_n if valid else None
    rmse = math.sqrt(sum(r["abs_error"] ** 2 for r in valid) / valid_n) if valid else None
    return {
        "n": n,
        "valid": valid_n,
        "parse_errors": n - valid_n,
        "within_0_01": sum(r["within_0_01"] for r in rows),
        "within_0_01_rate": sum(r["within_0_01"] for r in rows) / n if n else 0.0,
        "within_0_05": sum(r["within_0_05"] for r in rows),
        "within_0_05_rate": sum(r["within_0_05"] for r in rows) / n if n else 0.0,
        "mae": mae,
        "rmse": rmse,
    }


async def main() -> None:
    parser = argparse.ArgumentParser(description="Direct LLM baseline on QUITE")
    parser.add_argument("--model", default=os.environ.get("MODEL", "openai/gpt-4o-mini"))
    parser.add_argument("--modes", nargs="+", default=["numeric"], choices=["numeric", "wep"])
    parser.add_argument("--limit-per-mode", type=int, default=None)
    parser.add_argument("--sema", type=int, default=int(os.environ.get("SEMA", "20")))
    args = parser.parse_args()

    items = load_items(args.modes, args.limit_per_mode)
    client = make_client()
    sema = asyncio.Semaphore(args.sema)
    t0 = time.time()
    print(f"=== QUITE direct baseline | model={args.model} modes={args.modes} n={len(items)} ===")
    rows = await asyncio.gather(*(run_one(client, sema, args.model, item) for item in items))
    elapsed = time.time() - t0

    by_mode = {mode: summarize([r for r in rows if r["mode"] == mode]) for mode in args.modes}
    summary = {"overall": summarize(rows), **by_mode}
    print(f"Elapsed: {elapsed:.1f}s")
    for name, s in summary.items():
        print(
            f"{name}: valid {s['valid']}/{s['n']}, "
            f"<=0.01 {s['within_0_01']}/{s['n']}={s['within_0_01_rate']*100:.1f}%, "
            f"<=0.05 {s['within_0_05']}/{s['n']}={s['within_0_05_rate']*100:.1f}%, "
            f"MAE={s['mae']}"
        )

    prompt_tokens = sum(r["usage"]["prompt_tokens"] for r in rows)
    completion_tokens = sum(r["usage"]["completion_tokens"] for r in rows)
    total_cost_usd = sum(r["usage"].get("cost_usd", 0.0) for r in rows)
    out = {
        "experiment": "QUITE direct natural-language probability baseline",
        "model": args.model,
        "config": vars(args),
        "elapsed_sec": elapsed,
        "summary": summary,
        "results": rows,
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    model_tag = args.model.replace("/", "_")
    modes_tag = "-".join(args.modes)
    out_path = RESULTS_DIR / f"quite_direct_{modes_tag}_{model_tag}_{time.strftime('%Y%m%d_%H%M%S')}.json"
    save_artifact(
        out_path,
        out,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        total_cost_usd=total_cost_usd if total_cost_usd > 0 else None,
        model_id=args.model,
        extra_meta={
            "script": "baselines/run_quite_direct_baseline.py",
            "n_total": len(items),
            "modes": args.modes,
        },
    )
    print(f"Saved: {out_path}")


if __name__ == "__main__":
    asyncio.run(main())
