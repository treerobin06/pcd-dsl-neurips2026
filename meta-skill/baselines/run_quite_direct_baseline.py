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
from typing import Any, Dict, List, Optional

import httpx
from openai import AsyncOpenAI

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from _artifact_schema import accumulate_usage, save_artifact


SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parents[1]
QUITE_DIR = REPO_ROOT / "data" / "external" / "QUITE" / "data" / "quite-corpus" / "data"
RESULTS_DIR = SCRIPT_DIR / "results"

HARD_COMPUTE_STATIC_PRESETS = {
    "hard-compute": {
        "mildew0": [4, 18, 5],
        "insurance1": [16, 18, 7],
        "hailfinder0": [5, 15, 7],
        "water1": [1, 7, 2],
        "sachs1": [9, 4, 2],
        "phytophthora1": [16, 5, 2],
    },
    "hard-compute-clean": {
        "mildew0": [4, 18, 5, 10, 19],
        "insurance1": [16, 18, 7, 9, 12],
        "hailfinder0": [5, 15, 7, 14, 8],
        "water1": [1, 7, 2, 3, 4],
        "sachs1": [9, 4, 2, 0, 6],
    },
}

PRESET_NAMES = [
    "hard-compute",
    "hard-compute-clean",
    "hard-compute-expanded-50",
    "hard-compute-expanded-75",
    "all-network-3",
]

HARD_COMPUTE_NETWORKS = ["mildew0", "insurance1", "hailfinder0", "water1", "sachs1"]


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


def extract_json(text: str) -> Optional[Dict[str, Any]]:
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


def has_valid_gold(pair: Dict[str, Any]) -> bool:
    try:
        answer = float(pair["answer"])
    except (KeyError, TypeError, ValueError):
        return False
    return 0.0 <= answer <= 1.0 and math.isfinite(answer)


def valid_query_ids(network: str) -> List[int]:
    path = QUITE_DIR / f"{network}.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    qids = []
    for pair in data["evidence_query_pairs"]:
        if has_valid_gold(pair):
            qids.append(int(pair["id"]))
    return sorted(qids)


def all_network_query_plan(k_per_network: int = 3) -> Dict[str, List[int]]:
    plan = {}
    for path in sorted(QUITE_DIR.glob("*.json")):
        qids = valid_query_ids(path.stem)
        if qids:
            plan[path.stem] = qids[:k_per_network]
    return plan


def hard_compute_expanded_plan(target_n: int) -> Dict[str, List[int]]:
    clean = HARD_COMPUTE_STATIC_PRESETS["hard-compute-clean"]
    plan: Dict[str, List[int]] = {network: list(clean[network]) for network in HARD_COMPUTE_NETWORKS}
    used = sum(len(qids) for qids in plan.values())
    while used < target_n:
        changed = False
        for network in HARD_COMPUTE_NETWORKS:
            if used >= target_n:
                break
            for qid in valid_query_ids(network):
                if qid in plan[network]:
                    continue
                plan[network].append(qid)
                used += 1
                changed = True
                break
        if not changed:
            break
    return plan


def get_query_plan(preset: Optional[str]) -> Optional[Dict[str, List[int]]]:
    if preset is None:
        return None
    if preset in HARD_COMPUTE_STATIC_PRESETS:
        return HARD_COMPUTE_STATIC_PRESETS[preset]
    if preset == "all-network-3":
        return all_network_query_plan(k_per_network=3)
    if preset == "hard-compute-expanded-50":
        return hard_compute_expanded_plan(50)
    if preset == "hard-compute-expanded-75":
        return hard_compute_expanded_plan(75)
    raise ValueError(f"Unknown preset: {preset}")


def load_items(
    modes: List[str],
    limit_per_mode: Optional[int] = None,
    networks: Optional[List[str]] = None,
    query_limit_per_network: Optional[int] = None,
    query_plan: Optional[Dict[str, List[int]]] = None,
    include_invalid_gold: bool = False,
) -> List[Dict[str, Any]]:
    if not QUITE_DIR.exists():
        raise FileNotFoundError(f"QUITE data not found: {QUITE_DIR}")
    items: List[Dict[str, Any]] = []
    wanted = None
    if query_plan:
        wanted = {f"{name}.json" for name in query_plan}
    elif networks:
        wanted = {n if n.endswith(".json") else f"{n}.json" for n in networks}
    for path in sorted(QUITE_DIR.glob("*.json")):
        if wanted is not None and path.name not in wanted:
            continue
        data = json.loads(path.read_text())
        for mode in modes:
            premise_key = "numeric_premises" if mode == "numeric" else "wep_based_premises"
            premises = [p["content"] for p in data[premise_key]]
            pairs = data["evidence_query_pairs"]
            if not include_invalid_gold:
                pairs = [pair for pair in pairs if has_valid_gold(pair)]
            if query_plan is not None:
                qids = query_plan[path.stem]
                by_id = {int(pair["id"]): pair for pair in pairs}
                pairs = [by_id[qid] for qid in qids if qid in by_id]
            if query_limit_per_network is not None:
                pairs = pairs[:query_limit_per_network]
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
                if prob is not None and not (0.0 <= prob <= 1.0 and math.isfinite(prob)):
                    parse_error = "probability_out_of_range"
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
    parser.add_argument("--networks", nargs="*", default=None)
    parser.add_argument("--query-limit-per-network", type=int, default=None)
    parser.add_argument("--preset", choices=PRESET_NAMES, default=None)
    parser.add_argument("--limit-total", type=int, default=None)
    parser.add_argument("--include-invalid-gold", action="store_true")
    parser.add_argument("--sema", type=int, default=int(os.environ.get("SEMA", "20")))
    args = parser.parse_args()

    query_plan = get_query_plan(args.preset)
    items = load_items(
        args.modes,
        args.limit_per_mode,
        networks=args.networks,
        query_limit_per_network=args.query_limit_per_network,
        query_plan=query_plan,
        include_invalid_gold=args.include_invalid_gold,
    )
    if args.limit_total is not None:
        items = items[: args.limit_total]
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
        "query_plan": query_plan,
        "elapsed_sec": elapsed,
        "summary": summary,
        "results": rows,
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    model_tag = args.model.replace("/", "_")
    modes_tag = "-".join(args.modes)
    preset_tag = args.preset.replace("-", "_") if args.preset else "all"
    out_path = RESULTS_DIR / f"quite_direct_{modes_tag}_{preset_tag}_{model_tag}_{time.strftime('%Y%m%d_%H%M%S')}.json"
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
            "preset": args.preset,
            "limit_total": args.limit_total,
        },
    )
    print(f"Saved: {out_path}")


if __name__ == "__main__":
    asyncio.run(main())
