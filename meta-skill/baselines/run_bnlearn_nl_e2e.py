#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""bnlearn natural-language E2E tests.

Default pipeline:
  bnlearn natural-language query -> GPT-4o-mini extracts registry key/evidence
  -> deterministic DSL backend loads the registered bnlearn network and solves
  -> compare MAP state.

Stress-test pipeline:
  bnlearn network rendered as text -> GPT-4o-mini extracts a structured BN spec
  -> deterministic DSL variable-elimination backend solves -> compare MAP state.

The full-CPT mode is intentionally not the main bnlearn backend claim. It
measures whether a cheap LLM can copy large multi-valued CPTs from text into a
structured spec, which becomes impractical for larger public BNs.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import math
import os
import random
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import httpx
from openai import AsyncOpenAI

SCRIPT_DIR = Path(__file__).parent
RESULTS_DIR = SCRIPT_DIR / "results"

sys.path.insert(0, str(SCRIPT_DIR.parent))
sys.path.insert(0, str(SCRIPT_DIR))

from baselines._artifact_schema import accumulate_usage, save_artifact
from baselines.run_bnlearn_held_out import NETWORKS, format_bn_problem, generate_queries_from_network
from dsl.types import Factor
from baselines.verify_bnlearn_dsl_100 import dsl_posterior_distribution, wilson_ci


FULL_CPT_PROMPT = """You are a lossless parser for Bayesian-network inference problems.

Read the network text below and copy it into a structured JSON object. Do NOT
compute the posterior. Your only job is exact extraction.

Return ONLY valid JSON with this schema:
{
  "nodes": ["NodeName", ...],
  "states": {"NodeName": ["state1", "state2", ...], ...},
  "cpts": {
    "NodeName": {
      "parents": ["Parent1", ...],
      "rows": [
        {"when": {"Parent1": "value", ...}, "probs": {"state1": 0.1, "state2": 0.9}}
      ]
    }
  },
  "evidence": {"ObservedNode": "observed_state", ...},
  "query_variable": "NodeName"
}

Rules:
- Copy node names, state names, and evidence values exactly as written.
- For a root-node CPT, use exactly one row with "when": {}.
- For a conditional CPT, create one row for every "Given ..." line.
- Every probability in the input must appear in the JSON.
- Do not add explanations, markdown, or comments.

NETWORK TEXT:
<<PROBLEM>>
"""


REGISTRY_PROMPT = """You are the router/parser for a registered Bayesian-network solver.

The solver can load exactly these public bnlearn networks:
- asia
- child
- insurance
- alarm

Read the query text below. Return ONLY valid JSON with this schema:
{
  "network": "asia|child|insurance|alarm",
  "evidence": {"ObservedNode": "observed_state", ...},
  "query_variable": "NodeName"
}

Rules:
- Copy network names, node names, and evidence values exactly as written.
- Do not compute probabilities.
- Do not add explanations, markdown, or comments.

QUERY TEXT:
<<PROBLEM>>
"""


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


def combine_usage(items: List[Dict[str, Any]]) -> Dict[str, Any]:
    return {
        "prompt_tokens": sum(int(x.get("prompt_tokens", 0)) for x in items),
        "completion_tokens": sum(int(x.get("completion_tokens", 0)) for x in items),
        "cost_usd": sum(float(x.get("cost_usd", 0.0)) for x in items),
    }


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


def gold_map_states(query: Dict[str, Any], tol: float = 1e-9) -> List[str]:
    posterior = query.get("gold_posterior", {})
    if not posterior:
        return [query["gold_answer"]]
    best = max(float(v) for v in posterior.values())
    return [state for state, prob in posterior.items() if best - float(prob) <= tol]


def summarize_by_key(results: List[Dict[str, Any]], key: str = "ok") -> Dict[str, Any]:
    by_network: Dict[str, Dict[str, Any]] = {}
    for result in results:
        net = result["network"]
        row = by_network.setdefault(net, {"correct": 0, "total": 0, "failures": {}})
        row["total"] += 1
        row["correct"] += int(result.get(key, False))
        if not result.get(key, False):
            mode = result.get("failure_mode") or "unknown"
            row["failures"][mode] = row["failures"].get(mode, 0) + 1

    total = len(results)
    correct = sum(1 for r in results if r.get(key, False))
    for row in by_network.values():
        lo, hi = wilson_ci(row["correct"], row["total"])
        row["accuracy"] = row["correct"] / row["total"] if row["total"] else 0.0
        row["ci_lo"] = lo
        row["ci_hi"] = hi
    lo, hi = wilson_ci(correct, total)
    return {
        "correct": correct,
        "total": total,
        "accuracy": correct / total if total else 0.0,
        "ci_lo": lo,
        "ci_hi": hi,
        "by_network": by_network,
    }


def format_registry_problem(query: Dict[str, Any]) -> str:
    """Render the part a registry-backed solver expects from a user query."""
    lines = [
        f"Registered Bayesian network: {query['network']}",
        f"The network has {query['n_nodes']} variables and {query['n_edges']} directed edges.",
        "",
        "Observed evidence:",
    ]
    for var, val in query["evidence"].items():
        lines.append(f"- {var} = {val}")
    lines.extend([
        "",
        f"Question: Which state of {query['query_variable']} is most likely after conditioning on the evidence?",
        f"Equivalent query: P({query['query_variable']} | evidence)",
    ])
    return "\n".join(lines)


def canonicalize(value: Any, allowed: List[str]) -> Optional[str]:
    text = str(value).strip()
    if text in allowed:
        return text
    lowered = {str(v).strip().lower(): v for v in allowed}
    return lowered.get(text.lower())


def canonicalize_node(value: Any, allowed: List[str]) -> Optional[str]:
    return canonicalize(value, allowed)


def factors_from_parsed(parsed: Dict[str, Any], gold_nodes: List[str]) -> Tuple[List[Factor], Dict[str, List[str]]]:
    nodes_raw = parsed.get("nodes")
    cpts_raw = parsed.get("cpts")
    states_raw = parsed.get("states")
    if not isinstance(nodes_raw, list) or not isinstance(cpts_raw, dict) or not isinstance(states_raw, dict):
        raise ValueError("parsed JSON missing nodes/states/cpts")

    node_map: Dict[str, str] = {}
    for node in nodes_raw:
        canon = canonicalize_node(node, gold_nodes)
        if canon is None:
            raise ValueError(f"unknown node: {node}")
        node_map[str(node)] = canon
    for node in gold_nodes:
        node_map[node] = node

    state_domains: Dict[str, List[str]] = {}
    for raw_node, raw_states in states_raw.items():
        node = canonicalize_node(raw_node, gold_nodes)
        if node is None or not isinstance(raw_states, list):
            continue
        vals = [str(x).strip() for x in raw_states]
        if vals:
            state_domains[node] = vals

    factors: List[Factor] = []
    for raw_node, raw_cpt in cpts_raw.items():
        node = canonicalize_node(raw_node, gold_nodes)
        if node is None:
            raise ValueError(f"unknown CPT node: {raw_node}")
        if not isinstance(raw_cpt, dict):
            raise ValueError(f"CPT for {node} is not an object")
        parents = []
        for parent in raw_cpt.get("parents", []):
            canon_parent = canonicalize_node(parent, gold_nodes)
            if canon_parent is None:
                raise ValueError(f"unknown parent {parent} for {node}")
            parents.append(canon_parent)
        rows = raw_cpt.get("rows")
        if not isinstance(rows, list):
            raise ValueError(f"CPT for {node} missing rows")

        table: Dict[tuple, float] = {}
        observed_states = set(state_domains.get(node, []))
        for row in rows:
            if not isinstance(row, dict):
                continue
            when_raw = row.get("when", {})
            probs_raw = row.get("probs", {})
            if not isinstance(when_raw, dict) or not isinstance(probs_raw, dict):
                continue
            when: Dict[str, str] = {}
            for raw_parent, raw_val in when_raw.items():
                parent = canonicalize_node(raw_parent, gold_nodes)
                if parent is None:
                    raise ValueError(f"unknown parent in row: {raw_parent}")
                domain = state_domains.get(parent)
                val = canonicalize(raw_val, domain) if domain else str(raw_val).strip()
                if val is None:
                    raise ValueError(f"unknown state {raw_val} for parent {parent}")
                when[parent] = val

            missing_parents = [p for p in parents if p not in when]
            if missing_parents:
                raise ValueError(f"CPT row for {node} missing parents {missing_parents}")

            node_domain = state_domains.get(node, list(map(str, probs_raw.keys())))
            for raw_state, raw_prob in probs_raw.items():
                state = canonicalize(raw_state, node_domain)
                if state is None:
                    raise ValueError(f"unknown state {raw_state} for node {node}")
                prob = float(raw_prob)
                observed_states.add(state)
                if prob != 0.0:
                    key = (state,) + tuple(when[p] for p in parents)
                    table[key] = prob

        if not table:
            raise ValueError(f"CPT for {node} produced empty factor")
        state_domains[node] = list(state_domains.get(node, observed_states))
        factors.append(Factor(variables=[node] + parents, table=table))

    factor_nodes = {f.variables[0] for f in factors}
    missing = [node for node in gold_nodes if node not in factor_nodes]
    if missing:
        raise ValueError(f"missing CPTs for {missing[:5]}")
    return factors, state_domains


def factors_from_registered_cpts(
    cpts: Dict[str, Any],
    node_states: Dict[str, List[str]],
    nodes: List[str],
) -> Tuple[List[Factor], Dict[str, List[str]]]:
    """Convert registered pgmpy-derived CPTs to DSL factors."""
    factors: List[Factor] = []
    state_domains = {node: list(node_states[node]) for node in nodes}
    for node in nodes:
        cpt = cpts[node]
        parents = list(cpt["parents"])
        table: Dict[tuple, float] = {}
        if not parents:
            for state in state_domains[node]:
                prob = float(cpt["probabilities"][state])
                if prob != 0.0:
                    table[(state,)] = prob
        else:
            for entry in cpt["entries"]:
                parent_values = tuple(entry[parent] for parent in parents)
                for state in state_domains[node]:
                    prob = float(entry[f"P({node}={state})"])
                    if prob != 0.0:
                        table[(state,) + parent_values] = prob
        factors.append(Factor(variables=[node] + parents, table=table))
    return factors, state_domains


def solve_parsed(parsed: Dict[str, Any], query: Dict[str, Any]) -> Tuple[str, Dict[str, float]]:
    gold_nodes = list(query["nodes"])
    factors, state_domains = factors_from_parsed(parsed, gold_nodes)
    query_var = canonicalize_node(parsed.get("query_variable"), gold_nodes)
    if query_var is None:
        raise ValueError(f"unknown query variable: {parsed.get('query_variable')}")
    evidence_raw = parsed.get("evidence", {})
    if not isinstance(evidence_raw, dict):
        raise ValueError("evidence must be an object")

    evidence: Dict[str, str] = {}
    for raw_node, raw_val in evidence_raw.items():
        node = canonicalize_node(raw_node, gold_nodes)
        if node is None:
            raise ValueError(f"unknown evidence node: {raw_node}")
        val = canonicalize(raw_val, state_domains.get(node, []))
        if val is None:
            raise ValueError(f"unknown evidence state {raw_val} for {node}")
        evidence[node] = val

    query_states = state_domains.get(query_var)
    if not query_states:
        raise ValueError(f"no states for query variable {query_var}")
    posterior, evidence_prob = dsl_posterior_distribution(factors, query_var, query_states, evidence)
    if evidence_prob <= 1e-12 or not posterior:
        raise ValueError("zero-probability evidence or empty posterior")
    pred = max(posterior, key=posterior.get)
    return pred, posterior


def solve_registered(parsed: Dict[str, Any], query: Dict[str, Any], cpts: Dict[str, Any]) -> Tuple[str, Dict[str, float], Dict[str, Any]]:
    gold_nodes = list(query["nodes"])
    network = canonicalize(parsed.get("network"), NETWORKS)
    if network != query["network"]:
        raise ValueError(f"wrong network: {parsed.get('network')}")

    query_var = canonicalize_node(parsed.get("query_variable"), gold_nodes)
    if query_var is None:
        raise ValueError(f"unknown query variable: {parsed.get('query_variable')}")

    factors, state_domains = factors_from_registered_cpts(cpts, query["node_states"], gold_nodes)
    evidence_raw = parsed.get("evidence", {})
    if not isinstance(evidence_raw, dict):
        raise ValueError("evidence must be an object")

    evidence: Dict[str, str] = {}
    for raw_node, raw_val in evidence_raw.items():
        node = canonicalize_node(raw_node, gold_nodes)
        if node is None:
            raise ValueError(f"unknown evidence node: {raw_node}")
        val = canonicalize(raw_val, state_domains.get(node, []))
        if val is None:
            raise ValueError(f"unknown evidence state {raw_val} for {node}")
        evidence[node] = val

    query_states = state_domains.get(query_var)
    if not query_states:
        raise ValueError(f"no states for query variable {query_var}")
    posterior, evidence_prob = dsl_posterior_distribution(factors, query_var, query_states, evidence)
    if evidence_prob <= 1e-12 or not posterior:
        raise ValueError("zero-probability evidence or empty posterior")
    pred = max(posterior, key=posterior.get)
    parsed_fields = {
        "network": network,
        "query_variable": query_var,
        "evidence": evidence,
    }
    return pred, posterior, parsed_fields


async def parse_full_cpt_one(
    client: AsyncOpenAI,
    model: str,
    query: Dict[str, Any],
    cpts: Dict[str, Any],
    keep_raw: bool,
) -> Dict[str, Any]:
    problem_text = format_bn_problem(query, cpts)
    prompt = FULL_CPT_PROMPT.replace("<<PROBLEM>>", problem_text)
    try:
        resp = await client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.0,
            max_tokens=12000,
        )
        text = resp.choices[0].message.content or ""
        usage = usage_dict(resp.usage)
    except Exception as e:
        return {
            "network": query["network"],
            "query_id": query["query_id"],
            "ok": False,
            "failure_mode": f"api:{str(e)[:160]}",
            "usage": zero_usage(),
        }

    parsed = extract_json_obj(text)
    if parsed is None:
        return {
            "network": query["network"],
            "query_id": query["query_id"],
            "ok": False,
            "failure_mode": "json_parse",
            "gold": query["gold_answer"],
            "usage": usage,
            "raw_response": text if keep_raw else None,
        }

    try:
        pred, posterior = solve_parsed(parsed, query)
        strict_answer_correct = pred == query["gold_answer"]
        tie_aware_answer_correct = pred in gold_map_states(query)
        correct = strict_answer_correct
        failure_mode = None if correct else "wrong_answer"
        if not strict_answer_correct and tie_aware_answer_correct:
            failure_mode = "gold_tie_strict_label_mismatch"
    except Exception as e:
        pred = None
        posterior = {}
        strict_answer_correct = False
        tie_aware_answer_correct = False
        correct = False
        failure_mode = f"solve_or_parse:{str(e)[:200]}"

    return {
        "network": query["network"],
        "query_id": query["query_id"],
        "ok": correct,
        "failure_mode": failure_mode,
        "strict_answer_correct": strict_answer_correct,
        "tie_aware_answer_correct": tie_aware_answer_correct,
        "tie_aware_ok": tie_aware_answer_correct,
        "pred": pred,
        "gold": query["gold_answer"],
        "gold_map_states": gold_map_states(query),
        "gold_posterior": query["gold_posterior"],
        "posterior": posterior,
        "evidence": query["evidence"],
        "query_variable": query["query_variable"],
        "usage": usage,
        "parsed_summary": {
            "n_nodes": len(parsed.get("nodes", [])) if isinstance(parsed, dict) else 0,
            "n_cpts": len(parsed.get("cpts", {})) if isinstance(parsed, dict) else 0,
        },
        "raw_response": text if keep_raw else None,
    }


async def parse_registry_one(
    client: AsyncOpenAI,
    model: str,
    query: Dict[str, Any],
    cpts: Dict[str, Any],
    keep_raw: bool,
) -> Dict[str, Any]:
    problem_text = format_registry_problem(query)
    prompt = REGISTRY_PROMPT.replace("<<PROBLEM>>", problem_text)
    try:
        resp = await client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.0,
            max_tokens=512,
        )
        text = resp.choices[0].message.content or ""
        usage = usage_dict(resp.usage)
    except Exception as e:
        return {
            "network": query["network"],
            "query_id": query["query_id"],
            "ok": False,
            "failure_mode": f"api:{str(e)[:160]}",
            "usage": zero_usage(),
        }

    parsed = extract_json_obj(text)
    if parsed is None:
        return {
            "network": query["network"],
            "query_id": query["query_id"],
            "ok": False,
            "failure_mode": "json_parse",
            "gold": query["gold_answer"],
            "usage": usage,
            "raw_response": text if keep_raw else None,
        }

    try:
        pred, posterior, parsed_fields = solve_registered(parsed, query, cpts)
        parse_exact = (
            parsed_fields["network"] == query["network"]
            and parsed_fields["query_variable"] == query["query_variable"]
            and parsed_fields["evidence"] == query["evidence"]
        )
        strict_answer_correct = pred == query["gold_answer"]
        tie_aware_answer_correct = pred in gold_map_states(query)
        correct = parse_exact and strict_answer_correct
        failure_mode = None
        if not parse_exact:
            failure_mode = "parse_mismatch"
        elif not strict_answer_correct and tie_aware_answer_correct:
            failure_mode = "gold_tie_strict_label_mismatch"
        elif not strict_answer_correct:
            failure_mode = "wrong_answer"
    except Exception as e:
        pred = None
        posterior = {}
        parsed_fields = {}
        parse_exact = False
        strict_answer_correct = False
        tie_aware_answer_correct = False
        correct = False
        failure_mode = f"solve_or_parse:{str(e)[:200]}"

    return {
        "network": query["network"],
        "query_id": query["query_id"],
        "ok": correct,
        "failure_mode": failure_mode,
        "answer_correct": strict_answer_correct,
        "strict_answer_correct": strict_answer_correct,
        "tie_aware_answer_correct": tie_aware_answer_correct,
        "tie_aware_ok": parse_exact and tie_aware_answer_correct,
        "parse_exact": parse_exact,
        "pred": pred,
        "gold": query["gold_answer"],
        "gold_map_states": gold_map_states(query),
        "gold_posterior": query["gold_posterior"],
        "posterior": posterior,
        "evidence": query["evidence"],
        "query_variable": query["query_variable"],
        "parsed_fields": parsed_fields,
        "usage": usage,
        "raw_response": text if keep_raw else None,
    }


def build_query_set(networks: List[str], queries_per_net: int, seed: int) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    queries: List[Dict[str, Any]] = []
    cpts_by_net: Dict[str, Any] = {}
    for idx, net in enumerate(networks):
        net_queries, cpts = generate_queries_from_network(net, queries_per_net, seed=seed + idx * 1000)
        queries.extend(net_queries)
        cpts_by_net[net] = cpts
    return queries, cpts_by_net


def summarize(results: List[Dict[str, Any]]) -> Dict[str, Any]:
    return summarize_by_key(results, "ok")


async def run(args: argparse.Namespace) -> Dict[str, Any]:
    client = get_client()
    queries, cpts_by_net = build_query_set(args.networks, args.queries_per_net, args.seed)
    if args.max_samples > 0:
        rng = random.Random(args.seed)
        rng.shuffle(queries)
        queries = queries[: args.max_samples]

    sema = asyncio.Semaphore(args.concurrency)

    async def wrapped(query: Dict[str, Any]) -> Dict[str, Any]:
        async with sema:
            if args.mode == "full-cpt":
                return await parse_full_cpt_one(client, args.model, query, cpts_by_net[query["network"]], args.keep_raw)
            return await parse_registry_one(client, args.model, query, cpts_by_net[query["network"]], args.keep_raw)

    print(
        f"Running bnlearn NL E2E: model={args.model}, "
        f"mode={args.mode}, networks={args.networks}, n={len(queries)}, concurrency={args.concurrency}",
        flush=True,
    )
    results: List[Dict[str, Any]] = []
    for i, coro in enumerate(asyncio.as_completed([wrapped(q) for q in queries]), start=1):
        result = await coro
        results.append(result)
        if i == 1 or i % max(1, args.progress_every) == 0 or i == len(queries):
            summary = summarize(results)
            print(
                f"  progress {i}/{len(queries)}: "
                f"{summary['correct']}/{summary['total']} = {summary['accuracy']*100:.1f}%",
                flush=True,
            )

    usage = combine_usage([r.get("usage", {}) for r in results])
    summary = summarize(results)
    tie_aware_summary = summarize_by_key(results, "tie_aware_ok")
    route = (
        "bnlearn text/CPT -> LLM structured BN spec -> deterministic DSL backend"
        if args.mode == "full-cpt"
        else "bnlearn NL query -> LLM registry/evidence/query parser -> deterministic DSL backend"
    )
    artifact = {
        "route": route,
        "mode": args.mode,
        "model": args.model,
        "queries_per_net": args.queries_per_net,
        "networks": args.networks,
        "seed": args.seed,
        "summary": summary,
        "tie_aware_summary": tie_aware_summary,
        "results": results,
    }

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    model_tag = args.model.replace("/", "_")
    mode_tag = args.mode.replace("-", "_")
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out = args.out or RESULTS_DIR / f"bnlearn_nl_e2e_{mode_tag}_{model_tag}_{ts}.json"
    save_artifact(
        str(out),
        artifact,
        prompt_tokens=usage["prompt_tokens"],
        completion_tokens=usage["completion_tokens"],
        total_cost_usd=usage["cost_usd"],
        model_id=args.model,
        extra_meta={
            "script": "baselines/run_bnlearn_nl_e2e.py",
            "mode": args.mode,
            "n_samples": len(results),
            "queries_per_net": args.queries_per_net,
            "networks": args.networks,
            "concurrency": args.concurrency,
        },
    )
    print(json.dumps(summary, indent=2))
    if tie_aware_summary != summary:
        print("Tie-aware summary:")
        print(json.dumps(tie_aware_summary, indent=2))
    print(f"Saved: {out}")
    return artifact


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="bnlearn NL E2E stress test")
    parser.add_argument("--model", default="openai/gpt-4o-mini")
    parser.add_argument("--mode", choices=["registry", "full-cpt"], default="registry")
    parser.add_argument("--networks", nargs="+", default=NETWORKS, choices=NETWORKS)
    parser.add_argument("--queries-per-net", type=int, default=10)
    parser.add_argument("--seed", type=int, default=2026)
    parser.add_argument("--max-samples", type=int, default=0)
    parser.add_argument("--concurrency", type=int, default=3)
    parser.add_argument("--progress-every", type=int, default=5)
    parser.add_argument("--keep-raw", action="store_true")
    parser.add_argument("--out", type=Path, default=None)
    return parser.parse_args()


if __name__ == "__main__":
    asyncio.run(run(parse_args()))
