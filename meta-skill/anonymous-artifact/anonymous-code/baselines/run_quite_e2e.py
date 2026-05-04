#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""QUITE numeric end-to-end parse-and-solve experiment.

Pipeline:
  natural-language QUITE premises -> one compiled BN factor spec per network
  natural-language evidence/query -> structured assignments per query
  deterministic DSL variable elimination -> probability answer

The default mode uses QUITE's node/state/parent scaffold while extracting CPT
probabilities from natural-language premises. This is a pragmatic first external
E2E check: it tests natural-language CPT extraction and reusable per-network
solving without making the model rediscover arbitrary variable names from
scratch.
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
from dsl.core_ops import condition, marginalize, multiply
from dsl.types import Factor


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


def usage_dict(usage_obj: Any) -> Dict[str, Any]:
    usage = accumulate_usage(usage_obj)
    usage["cost_usd"] = float(getattr(usage_obj, "cost", 0) or 0)
    return usage


def zero_usage() -> Dict[str, Any]:
    return {"prompt_tokens": 0, "completion_tokens": 0, "cost_usd": 0.0}


def combine_usage(rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    return {
        "prompt_tokens": sum(int(r.get("prompt_tokens", 0)) for r in rows),
        "completion_tokens": sum(int(r.get("completion_tokens", 0)) for r in rows),
        "cost_usd": sum(float(r.get("cost_usd", 0.0)) for r in rows),
    }


def extract_json(text: str) -> Optional[Any]:
    text = text.strip()
    match = re.search(r"```(?:json)?\s*(.*?)```", text, flags=re.S)
    if match:
        text = match.group(1).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    start = text.find("{")
    end = text.rfind("}")
    if start >= 0 and end > start:
        try:
            return json.loads(text[start : end + 1])
        except json.JSONDecodeError:
            return None
    return None


def canonical_key(text: Any) -> str:
    return re.sub(r"[^a-z0-9]+", "", str(text).lower())


def canonicalize(value: Any, allowed: List[str]) -> Optional[str]:
    text = str(value).strip()
    if text in allowed:
        return text
    lowered = {v.lower(): v for v in allowed}
    if text.lower() in lowered:
        return lowered[text.lower()]
    compact = {canonical_key(v): v for v in allowed}
    return compact.get(canonical_key(text))


def wilson_ci(k: int, n: int) -> Tuple[float, float]:
    if n == 0:
        return 0.0, 1.0
    z = 1.96
    p = k / n
    denom = 1 + z**2 / n
    center = (p + z**2 / (2 * n)) / denom
    margin = z * math.sqrt(p * (1 - p) / n + z**2 / (4 * n**2)) / denom
    return max(0.0, center - margin), min(1.0, center + margin)


def _domain_sizes(factors: List[Factor]) -> Dict[str, int]:
    sizes: Dict[str, int] = {}
    for factor in factors:
        for idx, var in enumerate(factor.variables):
            vals = {key[idx] for key in factor.table}
            sizes[var] = max(sizes.get(var, 0), len(vals))
    return sizes


def _estimated_join_size(factors: List[Factor], var: str, domain_sizes: Dict[str, int]) -> int:
    scope: List[str] = []
    for factor in factors:
        if var not in factor.variables:
            continue
        for v in factor.variables:
            if v not in scope:
                scope.append(v)
    size = 1
    for v in scope:
        size *= max(1, domain_sizes.get(v, 1))
    return size


def _eliminate_one(factors: List[Factor], var: str) -> List[Factor]:
    relevant = [f for f in factors if var in f.variables]
    irrelevant = [f for f in factors if var not in f.variables]
    if not relevant:
        return irrelevant
    product = multiply(relevant)
    irrelevant.append(marginalize(product, {var}))
    return irrelevant


def dsl_posterior_distribution(
    factors: List[Factor],
    query_var: str,
    query_states: List[str],
    evidence: Dict[str, str],
) -> Tuple[Dict[str, float], float]:
    conditioned = [condition(f, evidence) for f in factors]
    if any(len(f.table) == 0 for f in conditioned):
        return {}, 0.0

    all_vars = set()
    for factor in conditioned:
        all_vars.update(factor.variables)

    eliminate = set(all_vars) - {query_var} - set(evidence.keys())
    current = conditioned
    while eliminate:
        domain_sizes = _domain_sizes(current)
        var = min(
            eliminate,
            key=lambda v: (
                _estimated_join_size([f for f in current if v in f.variables], v, domain_sizes),
                v,
            ),
        )
        current = _eliminate_one(current, var)
        eliminate.remove(var)

    product_factor = multiply(current)
    evidence_prob = sum(product_factor.table.values())
    if evidence_prob <= 1e-12 or not math.isfinite(evidence_prob):
        return {}, evidence_prob

    posterior = {state: 0.0 for state in query_states}
    if query_var not in product_factor.variables:
        return posterior, evidence_prob

    q_idx = product_factor.variables.index(query_var)
    for vals, prob in product_factor.table.items():
        state = vals[q_idx]
        if state in posterior:
            posterior[state] += prob
    return {state: prob / evidence_prob for state, prob in posterior.items()}, evidence_prob


def load_networks(names: Optional[List[str]], mode: str, limit_networks: Optional[int]) -> List[Dict[str, Any]]:
    if not QUITE_DIR.exists():
        raise FileNotFoundError(f"QUITE data not found: {QUITE_DIR}")
    paths = sorted(QUITE_DIR.glob("*.json"))
    if names:
        wanted = {n if n.endswith(".json") else f"{n}.json" for n in names}
        paths = [p for p in paths if p.name in wanted]
    if limit_networks is not None:
        paths = paths[:limit_networks]
    premise_key = "numeric_premises" if mode == "numeric" else "wep_based_premises"
    networks = []
    for path in paths:
        data = json.loads(path.read_text())
        networks.append(
            {
                "name": path.stem,
                "nodes": data["nodes"],
                "connectivity": data["connectivity"],
                "premises": data[premise_key],
                "pairs": data["evidence_query_pairs"],
                "mode": mode,
            }
        )
    return networks


def scaffold_missing_parents(network: Dict[str, Any]) -> List[Tuple[str, str]]:
    nodes = {n["name"] for n in network["nodes"]}
    missing = []
    for row in network["connectivity"]:
        child = row["node"]
        for parent in row.get("incoming", []):
            if parent != child and parent not in nodes:
                missing.append((child, parent))
    return missing


def has_valid_gold(pair: Dict[str, Any]) -> bool:
    try:
        answer = float(pair["answer"])
    except (KeyError, TypeError, ValueError):
        return False
    return 0.0 <= answer <= 1.0 and math.isfinite(answer)


def compile_prompt(network: Dict[str, Any], use_scaffold: bool) -> str:
    premises = "\n".join(f"{p['id']}. {p['content']}" for p in network["premises"])
    fewshot = """Extraction examples:

Example A -- complement from negated state:
Allowed child states: ["yes", "no"].
Text: "The probability of a baby being free from birth asphyxia is 0.9, whereas experiencing birth asphyxia is 0.1."
JSON row: {"when": {}, "probs": {"yes": 0.1, "no": 0.9}}

Example B -- no X when X is a listed positive state:
Allowed child states: ["PFC", "TGA", "Fallot", "PAIVS", "TAPVD", "Lung"].
Text: "If no birth asphyxia, there is a 97% probability of no PFC, 34% chance of TGA, 30% Fallot, 23% PAIVS, 95% no TAPVD, and 95% no lung conditions."
JSON row: {"when": {"BirthAsphyxia": "no"}, "probs": {"PFC": 0.03, "TGA": 0.34, "Fallot": 0.30, "PAIVS": 0.23, "TAPVD": 0.05, "Lung": 0.05}}

Example C -- equal remaining probability:
Allowed child states: ["ZERO", "LOW", "NORMAL", "HIGH"].
Text: "ZERO with likelihood 97%, whereas LOW, NORMAL and HIGH have equal likelihood."
JSON row probs: {"ZERO": 0.97, "LOW": 0.01, "NORMAL": 0.01, "HIGH": 0.01}

Example D -- asymmetric 'respectively' wording:
Allowed child states: ["ZERO", "LOW", "NORMAL", "HIGH"].
Text: "HIGH in 40 out of 100 cases, LOW or NORMAL in 29 respectively 30 cases, and ZERO in 1 case."
JSON row probs: {"ZERO": 0.01, "LOW": 0.29, "NORMAL": 0.30, "HIGH": 0.40}
"""
    if use_scaffold:
        scaffold = {
            "nodes": network["nodes"],
            "connectivity": network["connectivity"],
        }
        scaffold_text = (
            "You are given this node/state/parent scaffold. Use it to choose exact "
            "node names, state names, and parent order:\n"
            f"{json.dumps(scaffold, ensure_ascii=False, indent=2)}\n\n"
        )
    else:
        scaffold_text = "Infer all node names, states, and parents from the premises.\n\n"

    return f"""You are compiling a Bayesian network from natural-language probability premises.

{scaffold_text}Read the premises and extract the complete conditional probability tables.
Do not answer any query. Do not add explanations.
Work carefully but silently: identify parent assignments, map each text phrase
to one allowed child state, audit every row sum, then output JSON only.

Return ONLY valid JSON with this schema:
{{
  "nodes": ["NodeName", ...],
  "states": {{"NodeName": ["state1", "state2", ...]}},
  "cpts": {{
    "NodeName": {{
      "parents": ["Parent1", ...],
      "rows": [
        {{"when": {{"Parent1": "state", "...": "..."}}, "probs": {{"state1": 0.1, "state2": 0.9}}}}
      ]
    }}
  }}
}}

Rules:
- Use exact node names and state names from the scaffold when provided.
- Never invent states such as "no PFC" unless that exact state appears in the scaffold.
- If the scaffold accidentally lists a node as its own parent, treat that as a
  scaffold typo and infer the real parent set from the premises.
- For root nodes, include exactly one row with "when": {{}}.
- For non-root nodes, include one row per parent-state combination.
- Each row's probabilities must cover every state of the child node and sum to 1.
- Convert percentages to decimals: 95% -> 0.95, 2.5% -> 0.025.
- Convert "x out of 100 cases" to x/100, "impossible" to 0, and "certain" to 1.
- If a premise says two states have equal remaining probability, split it exactly.
- If a premise says multiple unnamed states have equal remaining probability,
  divide the leftover probability by the number of named leftover states.
- If the listed child states are positive labels and a premise says "no X",
  "not X", "free from X", or "without X", assign 1 - p to the positive
  state X unless an explicit "no X" state is listed. Do not invent negated states.
- For mutually exclusive disease/status variables, phrases like "95% no lung
  conditions" mean the listed Lung state has probability 0.05, not 0.95.
- Do not fix row-sum mistakes by arbitrary normalization. Re-read the premise
  and correct the state mapping. Every probability must be justified by text.

{fewshot}

PREMISES:
{premises}
"""


def query_prompt(network: Dict[str, Any], states: Dict[str, List[str]], pair: Dict[str, Any]) -> str:
    allowed = {
        "nodes": [{"name": node, "states": vals} for node, vals in states.items()],
    }
    return f"""You are a parser for a compiled Bayesian-network solver.

Map the natural-language evidence and query to exact variable assignments using ONLY the allowed node/state names.
Return ONLY valid JSON:
{{
  "evidence": {{"NodeName": "state", "...": "..."}},
  "query": {{"variable": "NodeName", "state": "state"}}
}}

Rules:
- If a variable has binary states like ["yes", "no"] or ["TRUE", "FALSE"], a query asking whether the condition holds ("having", "being", "is", "has") usually asks for "yes" or "TRUE"; a negated query asks for "no" or "FALSE".
- The query.state must be one of the listed states for query.variable. Never output placeholders such as "state".
- Evidence values must also be exact listed states.

Allowed nodes and states:
{json.dumps(allowed, ensure_ascii=False, indent=2)}

Evidence sentences:
{json.dumps(pair['evidences'], ensure_ascii=False, indent=2)}

Query sentence:
{pair['query']}
"""


def factors_from_compiled(compiled: Dict[str, Any], network: Dict[str, Any]) -> Tuple[List[Factor], Dict[str, List[str]], Dict[str, List[str]]]:
    gold_nodes = [n["name"] for n in network["nodes"]]
    node_alias = {n: n for n in gold_nodes}
    for raw_node in compiled.get("nodes", []):
        canon = canonicalize(raw_node, gold_nodes)
        if canon is not None:
            node_alias[str(raw_node)] = canon

    states: Dict[str, List[str]] = {}
    for raw_node, raw_states in compiled.get("states", {}).items():
        node = canonicalize(raw_node, gold_nodes)
        if node is None or not isinstance(raw_states, list):
            continue
        scaffold_states = next((n["states"] for n in network["nodes"] if n["name"] == node), [])
        vals = []
        for raw_state in raw_states:
            state = canonicalize(raw_state, scaffold_states)
            if state is not None and state not in vals:
                vals.append(state)
        if vals:
            states[node] = vals
    for n in network["nodes"]:
        states.setdefault(n["name"], list(n["states"]))

    expected_parents = {
        r["node"]: [p for p in r.get("incoming", []) if p != r["node"]]
        for r in network["connectivity"]
    }
    scaffold_had_self_loop = {
        r["node"]
        for r in network["connectivity"]
        if r["node"] in r.get("incoming", [])
    }
    factors: List[Factor] = []
    cpts = compiled.get("cpts", {})
    if not isinstance(cpts, dict):
        raise ValueError("compiled cpts must be an object")

    for gold_node in gold_nodes:
        raw_cpt = None
        for key, val in cpts.items():
            if canonicalize(key, gold_nodes) == gold_node:
                raw_cpt = val
                break
        if raw_cpt is None:
            raise ValueError(f"missing CPT for {gold_node}")
        if not isinstance(raw_cpt, dict):
            raise ValueError(f"CPT for {gold_node} must be an object")

        parents = []
        for raw_parent in raw_cpt.get("parents", expected_parents.get(gold_node, [])):
            parent = canonicalize(raw_parent, gold_nodes)
            if parent is None:
                raise ValueError(f"unknown parent {raw_parent} for {gold_node}")
            parents.append(parent)
        expected = expected_parents.get(gold_node)
        if expected is not None and parents != expected and gold_node not in scaffold_had_self_loop:
            # Parent order matters for factor keys; prefer a clean scaffold order.
            parents = expected

        table: Dict[tuple, float] = {}
        rows = raw_cpt.get("rows")
        if not isinstance(rows, list):
            raise ValueError(f"CPT for {gold_node} missing rows")
        for row in rows:
            if not isinstance(row, dict):
                continue
            when_raw = row.get("when", {})
            probs_raw = row.get("probs", {})
            if not isinstance(when_raw, dict) or not isinstance(probs_raw, dict):
                continue

            when: Dict[str, str] = {}
            for parent in parents:
                raw_val = None
                for raw_parent_key, candidate in when_raw.items():
                    if canonicalize(raw_parent_key, gold_nodes) == parent:
                        raw_val = candidate
                        break
                if raw_val is None:
                    raise ValueError(f"row for {gold_node} missing parent {parent}")
                val = canonicalize(raw_val, states[parent])
                if val is None:
                    raise ValueError(f"unknown state {raw_val} for parent {parent}")
                when[parent] = val

            probs: Dict[str, float] = {}
            for raw_state, raw_prob in probs_raw.items():
                state = canonicalize(raw_state, states[gold_node])
                if state is None:
                    raise ValueError(f"unknown state {raw_state} for {gold_node}")
                probs[state] = float(raw_prob)
            for state in states[gold_node]:
                table[(state,) + tuple(when[p] for p in parents)] = float(probs.get(state, 0.0))

        if not table:
            raise ValueError(f"empty factor for {gold_node}")
        factors.append(Factor(variables=[gold_node] + parents, table=table))

    return factors, states, expected_parents


def validate_row_sums(factors: List[Factor], states: Dict[str, List[str]]) -> List[str]:
    errors = []
    for factor in factors:
        node = factor.variables[0]
        parents = factor.variables[1:]
        buckets: Dict[tuple, float] = {}
        for key, prob in factor.table.items():
            parent_key = key[1:]
            buckets[parent_key] = buckets.get(parent_key, 0.0) + float(prob)
        for parent_key, total in buckets.items():
            if abs(total - 1.0) > 0.025:
                errors.append(f"{node}|{parents}={parent_key} sums to {total:.4f}")
    return errors[:10]


async def call_json(client: AsyncOpenAI, model: str, prompt: str, max_tokens: int, temperature: float = 0.0) -> Tuple[Optional[Any], str, Dict[str, Any], Optional[str]]:
    try:
        resp = await client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=max_tokens,
            temperature=temperature,
        )
        raw = resp.choices[0].message.content or ""
        return extract_json(raw), raw, usage_dict(resp.usage), None
    except Exception as exc:
        return None, "", zero_usage(), str(exc)[:500]


async def compile_network(
    client: AsyncOpenAI,
    sema: asyncio.Semaphore,
    model: str,
    network: Dict[str, Any],
    use_scaffold: bool,
    max_tokens: int,
) -> Dict[str, Any]:
    async with sema:
        parsed, raw, usage, error = await call_json(
            client,
            model,
            compile_prompt(network, use_scaffold=use_scaffold),
            max_tokens=max_tokens,
        )
        result: Dict[str, Any] = {
            "network": network["name"],
            "ok": False,
            "usage": usage,
            "raw_response": raw[:2000],
            "parse_error": error,
        }
        if error:
            return result
        if not isinstance(parsed, dict):
            result["parse_error"] = "json_parse_failed"
            return result
        try:
            factors, states, parents = factors_from_compiled(parsed, network)
            row_errors = validate_row_sums(factors, states)
            if row_errors:
                result["parse_error"] = "row_sum_validation_failed"
                result["row_errors"] = row_errors
                result["compiled_json"] = parsed
                return result
            result.update({
                "ok": True,
                "compiled_json": parsed,
                "states": states,
                "parents": parents,
                "n_factors": len(factors),
                "n_entries": sum(len(f.table) for f in factors),
            })
            result["_factors"] = factors
        except Exception as exc:
            result["parse_error"] = str(exc)[:500]
            result["compiled_json"] = parsed
        return result


async def run_query(
    client: AsyncOpenAI,
    sema: asyncio.Semaphore,
    model: str,
    network: Dict[str, Any],
    compile_result: Dict[str, Any],
    pair: Dict[str, Any],
    max_tokens: int,
) -> Dict[str, Any]:
    async with sema:
        base = {
            "network": network["name"],
            "pair_id": pair["id"],
            "gold": float(pair["answer"]),
            "reasoning_types": pair.get("reasoning_types", []),
        }
        if not compile_result.get("ok"):
            return {
                **base,
                "ok_0_01": False,
                "ok_0_05": False,
                "pred": None,
                "abs_error": None,
                "failure_mode": "compile_failed",
                "usage": zero_usage(),
            }
        parsed, raw, usage, error = await call_json(
            client,
            model,
            query_prompt(network, compile_result["states"], pair),
            max_tokens=max_tokens,
        )
        if error or not isinstance(parsed, dict):
            return {
                **base,
                "ok_0_01": False,
                "ok_0_05": False,
                "pred": None,
                "abs_error": None,
                "failure_mode": "query_json_parse_failed" if not error else "query_api_error",
                "query_parse_error": error,
                "raw_response": raw[:1000],
                "usage": usage,
            }

        try:
            q = parsed.get("query", {})
            query_var = canonicalize(q.get("variable"), list(compile_result["states"].keys()))
            if query_var is None:
                raise ValueError(f"unknown query variable {q.get('variable')}")
            query_state = canonicalize(q.get("state"), compile_result["states"][query_var])
            if query_state is None:
                raise ValueError(f"unknown query state {q.get('state')} for {query_var}")

            evidence: Dict[str, str] = {}
            for raw_node, raw_state in parsed.get("evidence", {}).items():
                node = canonicalize(raw_node, list(compile_result["states"].keys()))
                if node is None:
                    raise ValueError(f"unknown evidence node {raw_node}")
                state = canonicalize(raw_state, compile_result["states"][node])
                if state is None:
                    raise ValueError(f"unknown evidence state {raw_state} for {node}")
                evidence[node] = state

            posterior, evidence_prob = dsl_posterior_distribution(
                compile_result["_factors"],
                query_var,
                compile_result["states"][query_var],
                evidence,
            )
            if evidence_prob <= 1e-12 or query_state not in posterior:
                raise ValueError("zero-probability evidence or missing query state")
            pred = float(posterior[query_state])
            abs_error = abs(pred - float(pair["answer"]))
            return {
                **base,
                "ok_0_01": abs_error <= 0.01,
                "ok_0_05": abs_error <= 0.05,
                "pred": pred,
                "abs_error": abs_error,
                "query_var": query_var,
                "query_state": query_state,
                "evidence": evidence,
                "posterior": posterior,
                "evidence_prob": evidence_prob,
                "failure_mode": None if abs_error <= 0.05 else "wrong_probability",
                "response_json": parsed,
                "raw_response": raw[:1000],
                "usage": usage,
            }
        except Exception as exc:
            return {
                **base,
                "ok_0_01": False,
                "ok_0_05": False,
                "pred": None,
                "abs_error": None,
                "failure_mode": "query_or_solve_failed",
                "query_parse_error": str(exc)[:500],
                "response_json": parsed,
                "raw_response": raw[:1000],
                "usage": usage,
            }


def summarize(rows: List[Dict[str, Any]], key: str) -> Dict[str, Any]:
    total = len(rows)
    correct = sum(1 for r in rows if r.get(key))
    lo, hi = wilson_ci(correct, total)
    valid = [r for r in rows if r.get("abs_error") is not None]
    by_network: Dict[str, Dict[str, Any]] = {}
    for row in rows:
        net = row["network"]
        bucket = by_network.setdefault(net, {"n": 0, "correct": 0, "failures": {}})
        bucket["n"] += 1
        bucket["correct"] += int(row.get(key, False))
        if not row.get(key, False):
            mode = row.get("failure_mode") or "unknown"
            bucket["failures"][mode] = bucket["failures"].get(mode, 0) + 1
    for bucket in by_network.values():
        n = bucket["n"]
        c = bucket["correct"]
        b_lo, b_hi = wilson_ci(c, n)
        bucket["rate"] = c / n if n else 0.0
        bucket["wilson_95ci"] = [b_lo, b_hi]
    return {
        "n": total,
        "correct": correct,
        "rate": correct / total if total else 0.0,
        "wilson_95ci": [lo, hi],
        "valid_numeric": len(valid),
        "mae": sum(r["abs_error"] for r in valid) / len(valid) if valid else None,
        "by_network": by_network,
    }


async def main() -> None:
    parser = argparse.ArgumentParser(description="QUITE compile-once E2E")
    parser.add_argument("--model", default=os.environ.get("MODEL", "openai/gpt-4o-mini"))
    parser.add_argument("--mode", choices=["numeric", "wep"], default="numeric")
    parser.add_argument("--networks", nargs="*", default=None)
    parser.add_argument("--limit-networks", type=int, default=None)
    parser.add_argument("--query-limit-per-network", type=int, default=None)
    parser.add_argument("--no-scaffold", action="store_true")
    parser.add_argument("--compile-sema", type=int, default=3)
    parser.add_argument("--query-sema", type=int, default=20)
    parser.add_argument("--compile-max-tokens", type=int, default=12000)
    parser.add_argument("--query-max-tokens", type=int, default=512)
    parser.add_argument("--include-invalid-gold", action="store_true")
    parser.add_argument("--include-malformed-scaffold", action="store_true")
    args = parser.parse_args()

    networks = load_networks(args.networks, mode=args.mode, limit_networks=args.limit_networks)
    skipped_malformed = []
    if not args.include_malformed_scaffold:
        kept = []
        for net in networks:
            missing = scaffold_missing_parents(net)
            if missing:
                skipped_malformed.append({"network": net["name"], "missing_parents": missing})
            else:
                kept.append(net)
        networks = kept

    skipped_invalid_pairs = 0
    if not args.include_invalid_gold:
        for net in networks:
            before = len(net["pairs"])
            net["pairs"] = [pair for pair in net["pairs"] if has_valid_gold(pair)]
            skipped_invalid_pairs += before - len(net["pairs"])

    if args.query_limit_per_network is not None:
        for net in networks:
            net["pairs"] = net["pairs"][: args.query_limit_per_network]
    client = make_client()
    t0 = time.time()
    print(
        "=== QUITE E2E | "
        f"model={args.model} mode={args.mode} networks={len(networks)} "
        f"queries={sum(len(n['pairs']) for n in networks)} scaffold={not args.no_scaffold} ==="
    )
    if skipped_malformed:
        print(f"Skipped malformed scaffolds: {len(skipped_malformed)}")
    if skipped_invalid_pairs:
        print(f"Skipped invalid gold answers: {skipped_invalid_pairs}")

    compile_sema = asyncio.Semaphore(args.compile_sema)
    compile_results = await asyncio.gather(
        *[
            compile_network(
                client,
                compile_sema,
                args.model,
                net,
                use_scaffold=not args.no_scaffold,
                max_tokens=args.compile_max_tokens,
            )
            for net in networks
        ]
    )
    compile_by_name = {r["network"]: r for r in compile_results}
    print(f"Compiled networks: {sum(r['ok'] for r in compile_results)}/{len(compile_results)}")
    for r in compile_results:
        if not r["ok"]:
            print(f"  compile fail {r['network']}: {r.get('parse_error')}")

    query_sema = asyncio.Semaphore(args.query_sema)
    query_tasks = []
    for net in networks:
        comp = compile_by_name[net["name"]]
        for pair in net["pairs"]:
            query_tasks.append(run_query(client, query_sema, args.model, net, comp, pair, args.query_max_tokens))
    query_results = await asyncio.gather(*query_tasks)
    elapsed = time.time() - t0

    summary_001 = summarize(query_results, "ok_0_01")
    summary_005 = summarize(query_results, "ok_0_05")
    print(f"Elapsed: {elapsed:.1f}s")
    print(
        f"within 0.01: {summary_001['correct']}/{summary_001['n']} = "
        f"{summary_001['rate']*100:.1f}%"
    )
    print(
        f"within 0.05: {summary_005['correct']}/{summary_005['n']} = "
        f"{summary_005['rate']*100:.1f}%, MAE={summary_005['mae']}"
    )

    usage_items = [r["usage"] for r in compile_results] + [r["usage"] for r in query_results]
    usage = combine_usage(usage_items)
    serializable_compile = []
    for r in compile_results:
        r2 = {k: v for k, v in r.items() if k != "_factors"}
        serializable_compile.append(r2)

    out = {
        "experiment": "QUITE numeric compile-once E2E",
        "model": args.model,
        "config": vars(args),
        "elapsed_sec": elapsed,
        "compile_summary": {
            "n": len(compile_results),
            "ok": sum(r["ok"] for r in compile_results),
            "failed": [r["network"] for r in compile_results if not r["ok"]],
            "skipped_malformed": skipped_malformed,
            "skipped_invalid_pairs": skipped_invalid_pairs,
        },
        "summary": {
            "within_0_01": summary_001,
            "within_0_05": summary_005,
        },
        "compile_results": serializable_compile,
        "query_results": query_results,
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    model_tag = args.model.replace("/", "_")
    scaffold_tag = "scaffold" if not args.no_scaffold else "raw"
    out_path = RESULTS_DIR / f"quite_e2e_{args.mode}_{scaffold_tag}_{model_tag}_{time.strftime('%Y%m%d_%H%M%S')}.json"
    save_artifact(
        out_path,
        out,
        prompt_tokens=usage["prompt_tokens"],
        completion_tokens=usage["completion_tokens"],
        total_cost_usd=usage["cost_usd"] if usage["cost_usd"] > 0 else None,
        model_id=args.model,
        extra_meta={
            "script": "baselines/run_quite_e2e.py",
            "n_networks": len(networks),
            "n_queries": len(query_results),
            "scaffold": not args.no_scaffold,
            "mode": args.mode,
        },
    )
    print(f"Saved: {out_path}")


if __name__ == "__main__":
    asyncio.run(main())
