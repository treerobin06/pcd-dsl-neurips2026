#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Registered-network QUITE hard-compute E2E.

This runner tests a different QUITE setting from raw-premise compilation:
the network is already registered from QUITE's structured Problog artifact,
and the LLM only parses short natural-language evidence/query text. The hard
part is then exact posterior computation on multi-valued factors.
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
from typing import Any, Dict, List, Optional, Tuple

import httpx
from openai import AsyncOpenAI

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from _artifact_schema import accumulate_usage, save_artifact
from dsl.types import Factor
from run_quite_direct_baseline import PRESET_NAMES, get_query_plan
from run_quite_e2e import dsl_posterior_distribution, wilson_ci


SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parents[1]
QUITE_JSON_DIR = REPO_ROOT / "data" / "external" / "QUITE" / "data" / "quite-corpus" / "data"
QUITE_PROBLOG_DIR = REPO_ROOT / "data" / "external" / "QUITE" / "data" / "quite-corpus" / "problog_data"
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


def extract_json(text: str) -> Optional[Dict[str, Any]]:
    text = text.strip()
    match = re.search(r"```(?:json)?\s*(.*?)```", text, flags=re.S)
    if match:
        text = match.group(1).strip()
    try:
        obj = json.loads(text)
        return obj if isinstance(obj, dict) else None
    except json.JSONDecodeError:
        pass
    start = text.find("{")
    end = text.rfind("}")
    if start >= 0 and end > start:
        try:
            obj = json.loads(text[start : end + 1])
            return obj if isinstance(obj, dict) else None
        except json.JSONDecodeError:
            return None
    return None


def usage_dict(usage_obj: Any) -> Dict[str, Any]:
    usage = accumulate_usage(usage_obj)
    usage["cost_usd"] = float(getattr(usage_obj, "cost", 0) or 0)
    return usage


def zero_usage() -> Dict[str, Any]:
    return {"prompt_tokens": 0, "completion_tokens": 0, "cost_usd": 0.0}


def split_top_level(text: str, sep: str) -> List[str]:
    parts: List[str] = []
    buf: List[str] = []
    depth = 0
    in_quote = False
    for ch in text:
        if ch == "'":
            in_quote = not in_quote
        elif not in_quote:
            if ch == "(":
                depth += 1
            elif ch == ")":
                depth -= 1
        if ch == sep and depth == 0 and not in_quote:
            parts.append("".join(buf).strip())
            buf = []
        else:
            buf.append(ch)
    if buf:
        parts.append("".join(buf).strip())
    return [p for p in parts if p]


def strip_arg(arg: str) -> str:
    arg = arg.strip()
    if len(arg) >= 2 and arg[0] == "'" and arg[-1] == "'":
        return arg[1:-1]
    return arg


def normalize_context(text: str) -> str:
    return re.sub(r"[^A-Za-z0-9]+", "_", text).strip("_")


def parse_atom(atom: str) -> Tuple[str, str]:
    atom = atom.strip()
    negated = False
    if atom.startswith("not "):
        negated = True
        atom = atom[4:].strip()
    match = re.match(r"\s*([A-Za-z_][A-Za-z0-9_]*)\((.*)\)\s*$", atom)
    if not match:
        bare = atom.strip()
        if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", bare):
            return bare, "FALSE" if negated else "TRUE"
        raise ValueError(f"cannot parse atom: {atom}")
    pred = match.group(1)
    args = [strip_arg(x) for x in split_top_level(match.group(2).strip(), ",")]
    if negated:
        return pred, "FALSE"
    if len(args) >= 2:
        if re.search(r"\d+:\d+", args[-1]):
            return f"{pred}_{normalize_context(args[-1])}", args[0]
        return pred, args[-1]
    if len(args) == 1 and args[0] in {"car", "person", "species"}:
        return pred, "TRUE"
    return pred, args[0] if args else "TRUE"


def parse_weighted_atom(text: str, fallback_pred: Optional[str] = None) -> Tuple[float, str, str]:
    prob_text, atom = text.split("::", 1)
    prob = float(prob_text.strip())
    atom = atom.strip()
    if fallback_pred is not None:
        state_only = re.fullmatch(r"\(([^()]+)\)", atom)
        if state_only:
            return prob, fallback_pred, strip_arg(state_only.group(1))
    pred, state = parse_atom(atom)
    return prob, pred, state


def parse_problog_registry(network: str) -> Tuple[List[Factor], Dict[str, List[str]], Dict[str, List[str]], Dict[str, Any]]:
    path = QUITE_PROBLOG_DIR / "premises" / f"{network}.pl"
    if not path.exists():
        raise FileNotFoundError(path)
    text = path.read_text(encoding="utf-8")
    rows: List[Tuple[str, Dict[str, str], Dict[str, float]]] = []
    state_sets: Dict[str, set] = {}
    parent_sets: Dict[str, List[str]] = {}

    statements = []
    current: List[str] = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("%"):
            continue
        current.append(stripped)
        if stripped.endswith("."):
            statements.append(" ".join(current).rstrip(".").strip())
            current = []

    for stmt in statements:
        stmt = re.sub(r"\.\s*:-", " :-", stmt)
        if ":-" in stmt:
            lhs, rhs = stmt.split(":-", 1)
            parents = {}
            for atom in split_top_level(rhs, ","):
                pred, state = parse_atom(atom)
                parents[pred] = state
                state_sets.setdefault(pred, set()).add(state)
        else:
            lhs = stmt
            parents = {}
        probs: Dict[str, float] = {}
        child_pred: Optional[str] = None
        for part in split_top_level(lhs, ";"):
            prob, pred, state = parse_weighted_atom(part, child_pred)
            child_pred = child_pred or pred
            if pred != child_pred:
                raise ValueError(f"mixed child predicates in {network}: {stmt}")
            probs[state] = prob
            state_sets.setdefault(pred, set()).add(state)
        if child_pred is None:
            continue
        for parent, state in parents.items():
            state_sets.setdefault(parent, set()).add(state)
        existing = parent_sets.setdefault(child_pred, [])
        for parent in parents.keys():
            if parent not in existing:
                existing.append(parent)
        rows.append((child_pred, parents, probs))

    states = {var: sorted(vals, key=str) for var, vals in state_sets.items()}
    grouped: Dict[str, List[Tuple[Dict[str, str], Dict[str, float]]]] = {}
    for child, parents, probs in rows:
        grouped.setdefault(child, []).append((parents, probs))

    factors: List[Factor] = []
    for child, child_rows in grouped.items():
        parents = parent_sets.get(child, [])
        table: Dict[tuple, float] = {}
        for when, probs in child_rows:
            if set(probs.keys()) == {"TRUE"} and "FALSE" not in states[child]:
                states[child].append("FALSE")
                states[child] = sorted(states[child], key=str)
            if set(probs.keys()) == {"TRUE"}:
                probs = {**probs, "FALSE": 1.0 - float(probs["TRUE"])}
            parent_key = tuple(when[parent] for parent in parents)
            for state in states[child]:
                table[(state,) + parent_key] = float(probs.get(state, 0.0))
        factors.append(Factor(variables=[child] + parents, table=table))
    metadata = {
        "n_vars": len(states),
        "n_factors": len(factors),
        "n_entries": sum(len(f.table) for f in factors),
        "max_parents": max((len(f.variables) - 1 for f in factors), default=0),
        "max_factor_entries": max((len(f.table) for f in factors), default=0),
    }
    return factors, states, parent_sets, metadata


def canonical_key(text: Any) -> str:
    return re.sub(r"[^a-z0-9]+", "", str(text).lower())


def canonicalize(value: Any, allowed: List[str]) -> Optional[str]:
    text = str(value).strip()
    if text in allowed:
        return text
    by_lower = {v.lower(): v for v in allowed}
    if text.lower() in by_lower:
        return by_lower[text.lower()]
    by_key = {canonical_key(v): v for v in allowed}
    key = canonical_key(text)
    if key in by_key:
        return by_key[key]
    if isinstance(value, (int, float)):
        for fmt in [f"{float(value):.1f}", f"{float(value):.2f}", f"{float(value):g}"]:
            if fmt in allowed:
                return fmt
    return None


def load_pairs(network: str, query_ids: List[int]) -> List[Dict[str, Any]]:
    data = json.loads((QUITE_JSON_DIR / f"{network}.json").read_text(encoding="utf-8"))
    wanted = set(query_ids)
    pairs = []
    for pair in data["evidence_query_pairs"]:
        if int(pair["id"]) not in wanted:
            continue
        answer = float(pair["answer"])
        if not (0 <= answer <= 1):
            continue
        pairs.append(
            {
                "network": network,
                "pair_id": int(pair["id"]),
                "evidences": pair.get("evidences", []),
                "query": pair["query"],
                "gold": answer,
                "reasoning_types": pair.get("reasoning_types", []),
            }
        )
    pairs.sort(key=lambda x: query_ids.index(x["pair_id"]))
    return pairs


def parser_prompt(network: str, states: Dict[str, List[str]], pair: Dict[str, Any]) -> str:
    allowed = [{"variable": var, "states": vals} for var, vals in sorted(states.items())]
    evidence_text = "\n".join(f"- {e}" for e in pair["evidences"]) or "- None"
    return f"""You are the parser for a registered Bayesian-network solver.

The network "{network}" is already registered. Do not compute probabilities.
Map the short natural-language evidence and query into exact variable/state names.

Return ONLY valid JSON:
{{
  "evidence": {{"variable_name": "state", "...": "..."}},
  "query": {{"variable": "variable_name", "state": "state"}}
}}

Allowed variables and states:
{json.dumps(allowed, ensure_ascii=False, indent=2)}

Rules:
- Use only listed variable names and states.
- State names may be numeric strings such as "0.35", ranges such as "150-199",
  or labels such as "HIGH". Copy them exactly.
- If the question asks for "not X" and the listed states contain a negated
  complementary state, select that exact complementary state; otherwise select
  the positive state only when the question asks for X.
- Do not output placeholders.

Evidence:
{evidence_text}

Query:
{pair['query']}
"""


async def parse_query(
    client: AsyncOpenAI,
    sema: asyncio.Semaphore,
    model: str,
    network: str,
    states: Dict[str, List[str]],
    pair: Dict[str, Any],
) -> Dict[str, Any]:
    async with sema:
        try:
            resp = await client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": parser_prompt(network, states, pair)}],
                max_tokens=512,
                temperature=0.0,
            )
            raw = resp.choices[0].message.content or ""
            usage = usage_dict(resp.usage)
            parsed = extract_json(raw)
            return {"parsed": parsed, "raw_response": raw[:1000], "usage": usage, "error": None}
        except Exception as exc:
            return {"parsed": None, "raw_response": "", "usage": zero_usage(), "error": str(exc)[:300]}


async def main() -> None:
    parser = argparse.ArgumentParser(description="QUITE registered hard-compute E2E")
    parser.add_argument("--model", default=os.environ.get("MODEL", "openai/gpt-4o-mini"))
    parser.add_argument("--preset", choices=PRESET_NAMES, default="hard-compute-clean")
    parser.add_argument("--limit-total", type=int, default=None)
    parser.add_argument("--sema", type=int, default=12)
    args = parser.parse_args()

    query_plan = get_query_plan(args.preset)
    if query_plan is None:
        raise ValueError(f"Preset is required for registered QUITE E2E: {args.preset}")
    registries = {}
    for network in query_plan:
        factors, states, parents, meta = parse_problog_registry(network)
        registries[network] = {"factors": factors, "states": states, "parents": parents, "meta": meta}

    pairs = []
    for network, qids in query_plan.items():
        pairs.extend(load_pairs(network, qids))
    if args.limit_total is not None:
        pairs = pairs[: args.limit_total]

    client = make_client()
    sema = asyncio.Semaphore(args.sema)
    t0 = time.time()
    print(
        f"=== QUITE registered hard-compute E2E | model={args.model} "
        f"networks={len(query_plan)} queries={len(pairs)} ==="
    )
    parse_results = await asyncio.gather(
        *[
            parse_query(client, sema, args.model, pair["network"], registries[pair["network"]]["states"], pair)
            for pair in pairs
        ]
    )

    rows = []
    for pair, parsed_result in zip(pairs, parse_results):
        reg = registries[pair["network"]]
        states = reg["states"]
        parsed = parsed_result["parsed"]
        row = {
            **pair,
            "pred": None,
            "abs_error": None,
            "ok_0_01": False,
            "ok_0_05": False,
            "failure_mode": None,
            "usage": parsed_result["usage"],
            "raw_response": parsed_result["raw_response"],
            "response_json": parsed,
        }
        try:
            if parsed_result["error"]:
                raise ValueError("api_error: " + parsed_result["error"])
            if not isinstance(parsed, dict):
                raise ValueError("json_parse_failed")
            query = parsed.get("query", {})
            q_var = canonicalize(query.get("variable"), list(states.keys()))
            if q_var is None:
                raise ValueError(f"unknown query variable {query.get('variable')}")
            q_state = canonicalize(query.get("state"), states[q_var])
            if q_state is None:
                raise ValueError(f"unknown query state {query.get('state')} for {q_var}")
            evidence: Dict[str, str] = {}
            for raw_var, raw_state in parsed.get("evidence", {}).items():
                var = canonicalize(raw_var, list(states.keys()))
                if var is None:
                    raise ValueError(f"unknown evidence variable {raw_var}")
                state = canonicalize(raw_state, states[var])
                if state is None:
                    raise ValueError(f"unknown evidence state {raw_state} for {var}")
                evidence[var] = state
            posterior, evidence_prob = dsl_posterior_distribution(reg["factors"], q_var, states[q_var], evidence)
            if evidence_prob <= 1e-12 or q_state not in posterior:
                raise ValueError("zero evidence probability or missing query state")
            pred = float(posterior[q_state])
            abs_error = abs(pred - pair["gold"])
            row.update(
                {
                    "pred": pred,
                    "abs_error": abs_error,
                    "ok_0_01": abs_error <= 0.01,
                    "ok_0_05": abs_error <= 0.05,
                    "query_var": q_var,
                    "query_state": q_state,
                    "evidence": evidence,
                    "posterior": posterior,
                    "evidence_prob": evidence_prob,
                    "failure_mode": None if abs_error <= 0.05 else "wrong_probability",
                }
            )
        except Exception as exc:
            row["failure_mode"] = str(exc)[:300]
        rows.append(row)

    elapsed = time.time() - t0
    n = len(rows)
    c01 = sum(r["ok_0_01"] for r in rows)
    c05 = sum(r["ok_0_05"] for r in rows)
    valid = [r for r in rows if r["abs_error"] is not None]
    by_network: Dict[str, Dict[str, Any]] = {}
    for row in rows:
        b = by_network.setdefault(row["network"], {"n": 0, "correct_0_05": 0, "failures": {}})
        b["n"] += 1
        b["correct_0_05"] += int(row["ok_0_05"])
        if not row["ok_0_05"]:
            key = row["failure_mode"] or "unknown"
            key = key.split(":", 1)[0]
            b["failures"][key] = b["failures"].get(key, 0) + 1
    for b in by_network.values():
        b["rate_0_05"] = b["correct_0_05"] / b["n"] if b["n"] else 0.0
    lo, hi = wilson_ci(c05, n)
    summary = {
        "n": n,
        "within_0_01": c01,
        "within_0_01_rate": c01 / n if n else 0.0,
        "within_0_05": c05,
        "within_0_05_rate": c05 / n if n else 0.0,
        "within_0_05_wilson": [lo, hi],
        "valid_numeric": len(valid),
        "mae": sum(r["abs_error"] for r in valid) / len(valid) if valid else None,
        "by_network": by_network,
    }
    usage = {
        "prompt_tokens": sum(r["usage"].get("prompt_tokens", 0) for r in rows),
        "completion_tokens": sum(r["usage"].get("completion_tokens", 0) for r in rows),
        "cost_usd": sum(r["usage"].get("cost_usd", 0.0) for r in rows),
    }
    print(f"Elapsed: {elapsed:.1f}s")
    print(f"<=0.01 {c01}/{n}={c01/n*100:.1f}%, <=0.05 {c05}/{n}={c05/n*100:.1f}%, MAE={summary['mae']}")
    for net, b in by_network.items():
        print(f"  {net}: {b['correct_0_05']}/{b['n']}={b['rate_0_05']*100:.1f}% {b['failures']}")

    serializable_registry = {net: reg["meta"] for net, reg in registries.items()}
    out = {
        "experiment": "QUITE registered hard-compute E2E",
        "model": args.model,
        "config": vars(args),
        "query_plan": query_plan,
        "registry_metadata": serializable_registry,
        "elapsed_sec": elapsed,
        "summary": summary,
        "results": rows,
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    model_tag = args.model.replace("/", "_")
    preset_tag = args.preset.replace("-", "_")
    out_path = RESULTS_DIR / f"quite_registered_{preset_tag}_{model_tag}_{time.strftime('%Y%m%d_%H%M%S')}.json"
    save_artifact(
        out_path,
        out,
        prompt_tokens=usage["prompt_tokens"],
        completion_tokens=usage["completion_tokens"],
        total_cost_usd=usage["cost_usd"] if usage["cost_usd"] > 0 else None,
        model_id=args.model,
        extra_meta={
            "script": "baselines/run_quite_registered_e2e.py",
            "n_networks": len(query_plan),
            "n_queries": len(rows),
            "preset": args.preset,
            "limit_total": args.limit_total,
        },
    )
    print(f"Saved: {out_path}")


if __name__ == "__main__":
    asyncio.run(main())
