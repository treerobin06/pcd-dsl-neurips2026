#!/usr/bin/env python3
"""All-family mixed NL E2E benchmark with routing and optional rejection.

This is the full mixed-family pipeline:

  NL sample -> router -> family-specific parser/spec inducer -> deterministic solver

Supported families:
- flight preference learning
- hotel preference learning
- TextBandit-style Beta-Bernoulli bandit
- BLInD Bayesian-network inference
- synthetic Naive Bayes
- synthetic HMM forward filtering

Unsupported samples are routed to an explicit reject branch.
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
FLIGHT_DATA = PROJECT_ROOT / "data" / "eval" / "interaction" / "flight.jsonl"
HOTEL_DATA = PROJECT_ROOT / "data" / "eval" / "interaction" / "hotel.jsonl"

sys.path.insert(0, str(SCRIPT_DIR.parent))
sys.path.insert(0, str(SCRIPT_DIR))

from baselines._artifact_schema import accumulate_usage, save_artifact
from baselines.run_e2e_experiment import (
    build_e2e_parse_prompt,
    extract_json as extract_preference_json,
    run_parsed_pipeline,
)
from baselines.run_held_out_family import generate_naive_bayes_problem
from baselines.run_hmm_held_out import generate_hmm_problem
from baselines.run_mixed_e2e import blind_nl_sample, load_blind
from baselines.run_mixed_open_set_e2e import unsupported_samples
from baselines.run_nl_e2e_standard import hmm_nl_sample, nb_nl_sample
from baselines.run_textbandit_e2e import (
    PROMPT as TEXTBANDIT_PROMPT,
    build_samples as build_textbandit_samples,
    extract_json as extract_textbandit_json,
    run_pipeline as run_textbandit_pipeline,
)
from inductor.inductor import (
    _format_samples,
    _load_prompt_template,
    _parse_taskspec_response,
)
from taskspec.compiler import compile_solver


SUPPORTED_FAMILIES = {
    "flight",
    "hotel",
    "textbandit",
    "blind",
    "nb",
    "hmm",
}

EXPECTED_SPEC_FAMILY = {
    "blind": "variable_elimination",
    "nb": "naive_bayes",
    "hmm": "hmm_forward",
}


ROUTER_PROMPT = """You are the front-end router for a verified probabilistic solver system.

Supported families:
- flight: preference learning from a user's historical choices among flights, with flight descriptions and marked past choices.
- hotel: preference learning from a user's historical choices among hotels, with hotel descriptions and marked past choices.
- textbandit: Beta-Bernoulli bandit from a text history of slot-machine pulls and binary rewards.
- blind: Bayesian-network probability inference, where a DAG/CPTs and query are given in text.
- nb: Naive Bayes classification, including diagnosis wording, when class/disease priors, feature/symptom likelihoods, and observed feature values are explicitly given.
- hmm: HMM forward filtering, with hidden states, initial distribution, transition CPT, emission CPT, and observation sequence.

Reject inputs that are outside scope or underspecified:
- continuous distributions or approximate inference
- missing priors, missing likelihoods/CPTs, or no query target
- ordinary math or non-probabilistic tasks
- prediction tasks where probabilities must be estimated from raw text/time series instead of being given. Do not reject a diagnosis/classification task merely because it is medical or predictive; if priors and likelihoods are given, route it as nb.

Return ONLY JSON:
{
  "decision": "supported" or "reject",
  "family": "flight" or "hotel" or "textbandit" or "blind" or "nb" or "hmm" or null,
  "confidence": number between 0 and 1,
  "reason": "short reason"
}

Input sample:
<<SAMPLE>>
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


def combine_usage(*items: Dict[str, Any]) -> Dict[str, Any]:
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


def normalize_route(obj: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    if not obj:
        return {"decision": "parse_fail", "family": None, "confidence": 0.0, "reason": ""}

    decision = str(obj.get("decision", "")).strip().lower()
    family_raw = obj.get("family")
    family = None if family_raw is None else str(family_raw).strip().lower()
    aliases = {
        "flight_preference": "flight",
        "flights": "flight",
        "hotel_preference": "hotel",
        "hotels": "hotel",
        "bandit": "textbandit",
        "text_bandit": "textbandit",
        "conjugate_update": "textbandit",
        "variable_elimination": "blind",
        "bayesian_network": "blind",
        "bn": "blind",
        "naive_bayes": "nb",
        "hmm_forward": "hmm",
        "hidden_markov_model": "hmm",
        "none": None,
        "null": None,
        "unsupported": None,
    }
    family = aliases.get(family, family)

    if decision in {"reject", "unsupported", "out_of_scope"}:
        decision = "reject"
        family = None
    elif decision in {"support", "supported", "route", "accept"}:
        decision = "supported"
    elif family in SUPPORTED_FAMILIES:
        decision = "supported"
    else:
        decision = "reject"
        family = None

    return {
        "decision": decision,
        "family": family if family in SUPPORTED_FAMILIES else None,
        "confidence": obj.get("confidence", None),
        "reason": str(obj.get("reason", ""))[:240],
    }


async def call_llm(
    client: AsyncOpenAI,
    model: str,
    prompt: str,
    max_tokens: int,
) -> Tuple[bool, str, Dict[str, Any]]:
    try:
        resp = await client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.0,
            max_tokens=max_tokens,
        )
        return True, resp.choices[0].message.content or "", usage_dict(resp.usage)
    except Exception as e:
        return False, f"API error: {e}", zero_usage()


async def route_async(
    client: AsyncOpenAI,
    model: str,
    sample: Dict[str, Any],
) -> Tuple[Dict[str, Any], Dict[str, Any], Optional[str], str]:
    prompt = ROUTER_PROMPT.replace("<<SAMPLE>>", json.dumps(sample, ensure_ascii=False, indent=2)[:14000])
    ok, text, usage = await call_llm(client, model, prompt, max_tokens=256)
    if not ok:
        return {"decision": "parse_fail", "family": None, "confidence": 0.0, "reason": ""}, usage, text[:200], text
    return normalize_route(extract_json_obj(text)), usage, None, text


async def induce_taskspec_async(
    client: AsyncOpenAI,
    model: str,
    sample: Dict[str, Any],
) -> Tuple[Any, Dict[str, Any], Optional[str], str]:
    template = _load_prompt_template()
    samples_text = _format_samples([sample], max_samples=1)
    prompt = template.replace("{samples}", samples_text)
    ok, text, usage = await call_llm(client, model, prompt, max_tokens=4096)
    if not ok:
        return None, usage, text[:200], text
    try:
        return _parse_taskspec_response(text), usage, None, text
    except Exception as e:
        return None, usage, str(e)[:200], text


def wilson(k: int, n: int) -> Tuple[float, float]:
    if n == 0:
        return (0.0, 1.0)
    z = 1.96
    p = k / n
    denom = 1 + z**2 / n
    center = (p + z**2 / (2 * n)) / denom
    margin = z * sqrt(p * (1 - p) / n + z**2 / (4 * n**2)) / denom
    return (max(0.0, center - margin), min(1.0, center + margin))


def load_jsonl(path: Path, n: int) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    with path.open(encoding="utf-8") as f:
        for line in f:
            rows.append(json.loads(line))
            if n > 0 and len(rows) >= n:
                break
    return rows


def render_preference_router_sample(sample: Dict[str, Any], dataset: str) -> Dict[str, Any]:
    option_label = "Flight" if dataset == "flight" else "Hotel"
    lines = [
        f"Preference-learning task over {option_label.lower()} choices.",
        "Historical rounds mark which option the user chose; the final round is the decision query.",
    ]
    rounds = sample["rounds"]
    n_history = len(rounds) - 1
    for r_idx, round_obj in enumerate(rounds, start=1):
        if r_idx <= n_history:
            lines.append(f"Round {r_idx} (user chose {option_label} {round_obj['user_idx'] + 1}):")
        else:
            lines.append(f"Round {r_idx} (current round, choose one option):")
        lines.extend(f"  {opt}" for opt in round_obj["options"])
    return {
        "task_description": f"{option_label} preference learning from natural-language option descriptions.",
        "text": "\n".join(lines),
    }


def build_tasks(args: argparse.Namespace) -> List[Dict[str, Any]]:
    tasks: List[Dict[str, Any]] = []

    for sample in load_jsonl(FLIGHT_DATA, args.n_per_family):
        tasks.append({
            "family": "flight",
            "router_sample": render_preference_router_sample(sample, "flight"),
            "pipeline_sample": sample,
            "gold": sample["rounds"][-1]["user_idx"],
            "source_meta": {"dataset": "flight", "idx": sample.get("idx")},
        })

    for sample in load_jsonl(HOTEL_DATA, args.n_per_family):
        tasks.append({
            "family": "hotel",
            "router_sample": render_preference_router_sample(sample, "hotel"),
            "pipeline_sample": sample,
            "gold": sample["rounds"][-1]["user_idx"],
            "source_meta": {"dataset": "hotel", "idx": sample.get("idx")},
        })

    for sample in build_textbandit_samples(
        args.n_per_family,
        seed=args.textbandit_seed,
        min_history=args.min_history,
        max_history=args.max_history,
    ):
        tasks.append({
            "family": "textbandit",
            "router_sample": {
                "task_description": "TextBandit-style Beta-Bernoulli bandit from slot-machine pull history.",
                "text": sample["text"],
            },
            "pipeline_sample": sample,
            "gold": sample["gold_arm"],
            "source_meta": {"dataset": "textbandit", "id": sample["id"]},
        })

    for i in range(args.n_per_family):
        problem = generate_naive_bayes_problem(n_diseases=4, n_symptoms=5, seed=args.nb_seed + i)
        sample = nb_nl_sample(problem)
        tasks.append({
            "family": "nb",
            "router_sample": sample,
            "pipeline_sample": sample,
            "gold": problem["gold_diagnosis"],
            "source_data": problem,
            "source_meta": {"dataset": "nb", "seed": args.nb_seed + i},
        })

    for i in range(args.n_per_family):
        problem = generate_hmm_problem(n_states=3, n_obs=4, seq_length=5, seed=args.hmm_seed + i)
        sample = hmm_nl_sample(problem)
        tasks.append({
            "family": "hmm",
            "router_sample": sample,
            "pipeline_sample": sample,
            "gold": problem["gold_state"],
            "source_data": problem,
            "source_meta": {"dataset": "hmm", "seed": args.hmm_seed + i},
        })

    for row in load_blind(n=args.n_per_family, seed=args.blind_seed):
        sample = blind_nl_sample(row)
        tasks.append({
            "family": "blind",
            "router_sample": sample,
            "pipeline_sample": sample,
            "gold": float(row["answers"]),
            "source_meta": {"dataset": "blind"},
        })

    for _label, sample, gold, meta in unsupported_samples(args.n_unsupported):
        tasks.append({
            "family": "unsupported",
            "router_sample": sample,
            "pipeline_sample": sample,
            "gold": gold,
            "source_meta": meta,
        })

    rng = random.Random(args.shuffle_seed)
    rng.shuffle(tasks)
    return tasks


async def run_preference_branch(
    client: AsyncOpenAI,
    model: str,
    family: str,
    sample: Dict[str, Any],
    keep_raw: bool,
) -> Tuple[bool, Optional[Any], Dict[str, Any], Dict[str, Any], Optional[str]]:
    prompt = build_e2e_parse_prompt(sample, family)
    ok, text, usage = await call_llm(client, model, prompt, max_tokens=4096)
    raw_details = {"raw_branch_response": text} if keep_raw else {}
    if not ok:
        return False, None, usage, raw_details, text[:240]
    parsed = extract_preference_json(text)
    if parsed is None:
        return False, None, usage, raw_details, "json_parse"
    result = run_parsed_pipeline(parsed, sample, family)
    result.update(raw_details)
    if not result.get("success"):
        return False, None, usage, result, result.get("error", "parse_or_pipeline")
    return bool(result.get("e2e_correct")), result.get("e2e_recommendation"), usage, result, None


async def run_textbandit_branch(
    client: AsyncOpenAI,
    model: str,
    sample: Dict[str, Any],
    keep_raw: bool,
) -> Tuple[bool, Optional[Any], Dict[str, Any], Dict[str, Any], Optional[str]]:
    prompt = TEXTBANDIT_PROMPT.replace("{sample}", sample["text"])
    ok, text, usage = await call_llm(client, model, prompt, max_tokens=2048)
    raw_details = {"raw_branch_response": text} if keep_raw else {}
    if not ok:
        return False, None, usage, raw_details, text[:240]
    parsed = extract_textbandit_json(text)
    if parsed is None:
        return False, None, usage, raw_details, "json_parse"
    result = run_textbandit_pipeline(parsed, sample)
    result.update(raw_details)
    if not result.get("success"):
        return False, None, usage, result, result.get("failure_mode", "parse_or_pipeline")
    return bool(result.get("e2e_correct")), result.get("pred_arm"), usage, result, None


async def run_taskspec_branch(
    client: AsyncOpenAI,
    model: str,
    family: str,
    sample: Dict[str, Any],
    source_data: Optional[Dict[str, Any]],
    gold: Any,
    keep_raw: bool,
) -> Tuple[bool, Optional[Any], Dict[str, Any], Dict[str, Any], Optional[str]]:
    spec, usage, api_err, raw_text = await induce_taskspec_async(client, model, sample)
    spec_family = spec.inference_family if spec else None
    details = {"spec_family": spec_family}
    if keep_raw:
        details["raw_branch_response"] = raw_text
    if spec is None:
        return False, None, usage, details, f"spec_parse:{api_err}" if api_err else "spec_parse"
    if spec_family != EXPECTED_SPEC_FAMILY[family]:
        return False, None, usage, details, f"wrong_spec_family:{spec_family}"
    errors = spec.validate()
    if errors:
        return False, None, usage, details, f"spec_validate:{errors[0][:100]}"

    try:
        solver = compile_solver(spec)
        if family == "nb":
            assert source_data is not None
            obs_str = {
                symptom: ("present" if value else "absent")
                for symptom, value in source_data["patient_symptoms"].items()
            }
            pred = solver.predict(obs_str)
            ok = pred == gold
        elif family == "hmm":
            assert source_data is not None
            pred, _ = solver.predict_with_scores(source_data["obs_sequence"])
            ok = pred == gold
        elif family == "blind":
            pred = solver.solve_from_text(sample["contexts"], sample["query"], sample["graph"])
            ok = isinstance(pred, (int, float)) and abs(pred - gold) < 0.01
        else:
            return False, None, usage, details, f"unsupported_taskspec_family:{family}"
    except Exception as e:
        return False, None, usage, details, f"solve_or_compile:{str(e)[:100]}"

    details["pred"] = pred
    return ok, pred, usage, details, None if ok else "wrong_answer"


async def run_one(
    client: AsyncOpenAI,
    sema: asyncio.Semaphore,
    model: str,
    task: Dict[str, Any],
    keep_raw: bool,
) -> Dict[str, Any]:
    async with sema:
        family = task["family"]
        route, route_usage, route_err, raw_route_response = await route_async(client, model, task["router_sample"])
        branch_usage = zero_usage()
        pred = None
        branch_details: Dict[str, Any] = {}
        failure_mode = None
        ok = False

        if family == "unsupported":
            ok = route["decision"] == "reject"
            failure_mode = None if ok else f"false_accept:{route.get('family')}"
        elif route_err:
            failure_mode = f"router_api_error:{route_err}"
        elif route["decision"] != "supported":
            failure_mode = "false_reject"
        elif route["family"] != family:
            failure_mode = f"wrong_route:{route.get('family')}"
        elif family in {"flight", "hotel"}:
            ok, pred, branch_usage, branch_details, branch_err = await run_preference_branch(
                client, model, family, task["pipeline_sample"], keep_raw
            )
            failure_mode = branch_err
        elif family == "textbandit":
            ok, pred, branch_usage, branch_details, branch_err = await run_textbandit_branch(
                client, model, task["pipeline_sample"], keep_raw
            )
            failure_mode = branch_err
        elif family in {"blind", "nb", "hmm"}:
            ok, pred, branch_usage, branch_details, branch_err = await run_taskspec_branch(
                client,
                model,
                family,
                task["pipeline_sample"],
                task.get("source_data"),
                task["gold"],
                keep_raw,
            )
            failure_mode = branch_err
        else:
            failure_mode = f"unknown_family:{family}"

        usage = combine_usage(route_usage, branch_usage)
        return {
            "family_label": family,
            "route": route,
            "raw_route_response": raw_route_response if keep_raw else None,
            "route_correct": (route["decision"] == "reject") if family == "unsupported" else (
                route["decision"] == "supported" and route["family"] == family
            ),
            "pred": None if pred is None else str(pred),
            "gold": str(task["gold"]),
            "ok": bool(ok),
            "failure_mode": failure_mode,
            "usage": usage,
            "branch_details": branch_details,
            "source_meta": task.get("source_meta"),
        }


def summarize(results: List[Dict[str, Any]]) -> Dict[str, Any]:
    by_family: Dict[str, Dict[str, int]] = {}
    for result in results:
        fam = result["family_label"]
        by_family.setdefault(fam, {"n": 0, "route_correct": 0, "ok": 0})
        by_family[fam]["n"] += 1
        by_family[fam]["route_correct"] += int(result["route_correct"])
        by_family[fam]["ok"] += int(result["ok"])

    supported = [r for r in results if r["family_label"] != "unsupported"]
    unsupported = [r for r in results if r["family_label"] == "unsupported"]
    total_ok = sum(int(r["ok"]) for r in results)
    route_ok = sum(int(r["route_correct"]) for r in results)
    supported_ok = sum(int(r["ok"]) for r in supported)
    unsupported_ok = sum(int(r["ok"]) for r in unsupported)
    failure_modes: Dict[str, int] = {}
    for result in results:
        if result["failure_mode"]:
            key = str(result["failure_mode"]).split(":", 1)[0]
            failure_modes[key] = failure_modes.get(key, 0) + 1

    return {
        "n_total": len(results),
        "overall_correct": total_ok,
        "overall_acc": total_ok / len(results) if results else 0.0,
        "overall_wilson95": list(wilson(total_ok, len(results))),
        "route_correct": route_ok,
        "route_acc": route_ok / len(results) if results else 0.0,
        "route_wilson95": list(wilson(route_ok, len(results))),
        "supported_correct": supported_ok,
        "n_supported": len(supported),
        "supported_acc": supported_ok / len(supported) if supported else None,
        "supported_wilson95": list(wilson(supported_ok, len(supported))) if supported else None,
        "reject_correct": unsupported_ok,
        "n_unsupported": len(unsupported),
        "reject_acc": unsupported_ok / len(unsupported) if unsupported else None,
        "reject_wilson95": list(wilson(unsupported_ok, len(unsupported))) if unsupported else None,
        "per_family": by_family,
        "failure_modes": failure_modes,
    }


def print_summary(summary: Dict[str, Any]) -> None:
    lo, hi = summary["overall_wilson95"]
    rlo, rhi = summary["route_wilson95"]
    print(
        f"Overall all-family E2E: {summary['overall_correct']}/{summary['n_total']} = "
        f"{summary['overall_acc']*100:.1f}% [{lo*100:.1f}, {hi*100:.1f}]"
    )
    print(
        f"Router accuracy: {summary['route_correct']}/{summary['n_total']} = "
        f"{summary['route_acc']*100:.1f}% [{rlo*100:.1f}, {rhi*100:.1f}]"
    )
    if summary["n_supported"]:
        slo, shi = summary["supported_wilson95"]
        print(
            f"Supported solve: {summary['supported_correct']}/{summary['n_supported']} = "
            f"{summary['supported_acc']*100:.1f}% [{slo*100:.1f}, {shi*100:.1f}]"
        )
    if summary["n_unsupported"]:
        ulo, uhi = summary["reject_wilson95"]
        print(
            f"Unsupported reject: {summary['reject_correct']}/{summary['n_unsupported']} = "
            f"{summary['reject_acc']*100:.1f}% [{ulo*100:.1f}, {uhi*100:.1f}]"
        )
    print("\n--- Per-family ---")
    for fam in ["flight", "hotel", "textbandit", "blind", "nb", "hmm", "unsupported"]:
        if fam in summary["per_family"]:
            item = summary["per_family"][fam]
            olo, ohi = wilson(item["ok"], item["n"])
            print(
                f"  {fam:12s} route={item['route_correct']}/{item['n']} "
                f"ok={item['ok']}/{item['n']} = {item['ok']*100/item['n']:.1f}% "
                f"[{olo*100:.1f}, {ohi*100:.1f}]"
            )
    print("\n--- Failure modes ---")
    if not summary["failure_modes"]:
        print("  none")
    for key, count in sorted(summary["failure_modes"].items(), key=lambda x: -x[1]):
        print(f"  {key}: {count}")


async def main() -> None:
    parser = argparse.ArgumentParser(description="All-family mixed NL E2E benchmark")
    parser.add_argument("--model", default="openai/gpt-4o-mini")
    parser.add_argument("--n-per-family", type=int, default=5)
    parser.add_argument("--n-unsupported", type=int, default=5)
    parser.add_argument("--concurrency", "-c", type=int, default=8)
    parser.add_argument("--shuffle-seed", type=int, default=20260502)
    parser.add_argument("--textbandit-seed", type=int, default=20260502)
    parser.add_argument("--nb-seed", type=int, default=6100)
    parser.add_argument("--hmm-seed", type=int, default=6200)
    parser.add_argument("--blind-seed", type=int, default=6300)
    parser.add_argument("--min-history", type=int, default=8)
    parser.add_argument("--max-history", type=int, default=14)
    parser.add_argument("--keep-raw", action="store_true", help="store raw router/parser LLM responses")
    args = parser.parse_args()

    client = get_client()
    sema = asyncio.Semaphore(args.concurrency)
    tasks = build_tasks(args)
    family_counts: Dict[str, int] = {}
    for task in tasks:
        family_counts[task["family"]] = family_counts.get(task["family"], 0) + 1

    print(f"=== All-family mixed E2E | n_total={len(tasks)} | model={args.model} | sema={args.concurrency} ===")
    for family, count in sorted(family_counts.items()):
        print(f"  {family}: {count}")

    t0 = time.time()
    results = await asyncio.gather(*[run_one(client, sema, args.model, task, args.keep_raw) for task in tasks])
    elapsed = time.time() - t0
    summary = summarize(results)

    print(f"\nElapsed: {elapsed:.1f}s")
    print_summary(summary)

    prompt_tokens = sum(int(r["usage"]["prompt_tokens"]) for r in results)
    completion_tokens = sum(int(r["usage"]["completion_tokens"]) for r in results)
    total_cost_usd = sum(float(r["usage"].get("cost_usd", 0.0)) for r in results)

    out = {
        "experiment": "all_family_mixed_nl_e2e",
        "model": args.model,
        "concurrency": args.concurrency,
        "elapsed_sec": elapsed,
        "n_per_family": args.n_per_family,
        "n_unsupported": args.n_unsupported,
        "families": family_counts,
        "overall": summary,
        "results": results,
        "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    RESULTS_DIR.mkdir(exist_ok=True)
    model_tag = args.model.replace("/", "_")
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_path = RESULTS_DIR / f"all_family_mixed_e2e_{model_tag}_{ts}.json"
    save_artifact(
        str(out_path),
        out,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        total_cost_usd=total_cost_usd if total_cost_usd > 0 else None,
        model_id=args.model,
        extra_meta={
            "script": "baselines/run_all_family_mixed_e2e.py",
            "n_per_family": args.n_per_family,
            "n_unsupported": args.n_unsupported,
            "concurrency": args.concurrency,
        },
    )
    print(f"\nTotal cost: ${total_cost_usd:.6f}")
    print(f"Saved: {out_path}")


if __name__ == "__main__":
    asyncio.run(main())
