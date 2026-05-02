"""Open-set mixed-family E2E benchmark with explicit rejection.

This is a supporting experiment, not a headline claim. It checks whether a
front-end router can separate supported probabilistic families from inputs that
are underspecified or outside the DSL scope, then hand supported tasks to the
existing TaskSpec induction -> compiler -> solver pipeline.
"""

from __future__ import annotations

import asyncio
import csv
import json
import os
import random
import sys
import time
from math import sqrt
from typing import Any, Dict, List, Optional, Tuple

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import httpx
from openai import AsyncOpenAI

from baselines._artifact_schema import accumulate_usage, save_artifact
from baselines.run_held_out_family import generate_naive_bayes_problem
from baselines.run_hmm_held_out import generate_hmm_problem
from baselines.run_mixed_e2e import blind_nl_sample, load_blind
from baselines.run_nl_e2e_standard import nb_nl_sample, hmm_nl_sample
from inductor.inductor import (
    _format_samples,
    _load_prompt_template,
    _parse_taskspec_response,
)
from taskspec.compiler import compile_solver


MODEL = os.environ.get("MODEL", "openai/gpt-4o-mini")
SEMA = int(os.environ.get("SEMA", "10"))
N_PER_FAMILY = int(os.environ.get("N_PER_FAMILY", "10"))
N_UNSUPPORTED = int(os.environ.get("N_UNSUPPORTED", str(N_PER_FAMILY)))

SUPPORTED = {"blind", "nb", "hmm"}
EXPECTED_SPEC_FAMILY = {
    "blind": "variable_elimination",
    "nb": "naive_bayes",
    "hmm": "hmm_forward",
}


def load_dotenv_if_present() -> None:
    """Minimal .env loader so local runs do not need a shell source step."""
    env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env")
    if not os.path.exists(env_path):
        return
    with open(env_path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip().strip("'\""))


def usage_dict(usage_obj) -> Dict[str, Any]:
    usage = accumulate_usage(usage_obj)
    usage["cost_usd"] = float(getattr(usage_obj, "cost", 0) or 0)
    return usage


def combine_usage(*items: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "prompt_tokens": sum(int(x.get("prompt_tokens", 0)) for x in items),
        "completion_tokens": sum(int(x.get("completion_tokens", 0)) for x in items),
        "cost_usd": sum(float(x.get("cost_usd", 0.0)) for x in items),
    }


def extract_json(text: str) -> Optional[Dict[str, Any]]:
    start = text.find("{")
    end = text.rfind("}")
    if start < 0 or end <= start:
        return None
    try:
        return json.loads(text[start : end + 1])
    except json.JSONDecodeError:
        return None


def normalize_route(obj: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    if not obj:
        return {"decision": "parse_fail", "family": None, "confidence": 0.0, "reason": ""}
    decision = str(obj.get("decision", "")).strip().lower()
    family = obj.get("family")
    family = None if family is None else str(family).strip().lower()
    aliases = {
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
    elif family in SUPPORTED:
        decision = "supported"
    else:
        decision = "reject"
        family = None
    return {
        "decision": decision,
        "family": family if family in SUPPORTED else None,
        "confidence": obj.get("confidence", None),
        "reason": str(obj.get("reason", ""))[:240],
    }


ROUTER_PROMPT = """You are the router for a verified probabilistic solver system.

Supported families:
- blind: Bayesian-network probability inference. The DAG/CPTs and query are given in text.
- nb: Naive Bayes classification. Class priors, feature likelihoods, and observed features are given.
- hmm: HMM forward filtering. Hidden states, initial distribution, transition CPT, emission CPT, and observation sequence are given.

Reject inputs that are outside scope or underspecified:
- continuous distributions or approximate inference
- missing priors, missing likelihoods/CPTs, or no query target
- ordinary math or non-probabilistic tasks
- prediction tasks where probabilities must be estimated from raw text/time series instead of being given

Return ONLY JSON:
{
  "decision": "supported" or "reject",
  "family": "blind" or "nb" or "hmm" or null,
  "confidence": number between 0 and 1,
  "reason": "short reason"
}

Input sample:
<<SAMPLE>>
"""


async def route_async(client: AsyncOpenAI, sample: Dict[str, Any]) -> Tuple[Dict[str, Any], Dict[str, Any], Optional[str]]:
    prompt = ROUTER_PROMPT.replace("<<SAMPLE>>", json.dumps(sample, ensure_ascii=False, indent=2)[:12000])
    try:
        resp = await client.chat.completions.create(
            model=MODEL,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=256,
            temperature=0.0,
        )
        usage = usage_dict(resp.usage)
        raw = resp.choices[0].message.content or ""
        return normalize_route(extract_json(raw)), usage, None
    except Exception as e:
        return {"decision": "parse_fail", "family": None, "confidence": 0.0, "reason": ""}, {
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "cost_usd": 0.0,
        }, str(e)[:200]


async def induce_async(client: AsyncOpenAI, sample: Dict[str, Any]) -> Tuple[Any, Dict[str, Any], Optional[str]]:
    template = _load_prompt_template()
    samples_text = _format_samples([sample], max_samples=1)
    prompt = template.replace("{samples}", samples_text)
    try:
        resp = await client.chat.completions.create(
            model=MODEL,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=4096,
            temperature=0.0,
        )
        return _parse_taskspec_response(resp.choices[0].message.content or ""), usage_dict(resp.usage), None
    except Exception as e:
        return None, {"prompt_tokens": 0, "completion_tokens": 0, "cost_usd": 0.0}, str(e)[:200]


def unsupported_samples(n: int) -> List[Tuple[str, Dict[str, Any], str, Dict[str, Any]]]:
    templates = [
        (
            "unsupported_continuous",
            {
                "task_description": "Infer the posterior over a continuous Gaussian mean.",
                "data": "Observations are real-valued: 1.2, 0.7, 2.4, -0.3. Prior mean and variance are not specified.",
                "query": "Compute the posterior distribution over the unknown mean.",
            },
            "continuous_or_missing_prior",
        ),
        (
            "unsupported_missing_probabilities",
            {
                "task_description": "Diagnose the most likely disease from symptoms.",
                "classes": ["flu", "cold", "allergy"],
                "observed": "fever present, cough present, rash absent",
                "note": "No disease priors or symptom likelihoods are provided.",
            },
            "missing_likelihoods",
        ),
        (
            "unsupported_prediction",
            {
                "task_description": "Choose the best stock to buy tomorrow from recent headlines and prices.",
                "market_notes": "Company A released a product, Company B missed earnings, Company C is volatile.",
                "query": "Estimate return probabilities and recommend the best stock.",
            },
            "prediction_bottleneck",
        ),
        (
            "unsupported_non_probability",
            {
                "task_description": "Arithmetic word problem.",
                "question": "A train travels 120 miles in 2 hours. What is its average speed?",
            },
            "not_probabilistic_inference",
        ),
    ]
    rows = []
    for i in range(n):
        label, sample, subtype = templates[i % len(templates)]
        rows.append(("unsupported", {**sample, "unsupported_id": i}, "reject", {"subtype": subtype, "template": label}))
    return rows


def build_tasks() -> List[Tuple[str, Dict[str, Any], Any, Optional[Dict[str, Any]]]]:
    tasks: List[Tuple[str, Dict[str, Any], Any, Optional[Dict[str, Any]]]] = []

    for i in range(N_PER_FAMILY):
        p = generate_naive_bayes_problem(n_diseases=4, n_symptoms=5, seed=5100 + i)
        tasks.append(("nb", nb_nl_sample(p), p["gold_diagnosis"], p))

    for i in range(N_PER_FAMILY):
        p = generate_hmm_problem(n_states=3, n_obs=4, seq_length=5, seed=5200 + i)
        tasks.append(("hmm", hmm_nl_sample(p), p["gold_state"], p))

    for row in load_blind(n=N_PER_FAMILY, seed=5300):
        tasks.append(("blind", blind_nl_sample(row), float(row["answers"]), None))

    tasks.extend(unsupported_samples(N_UNSUPPORTED))
    rng = random.Random(20260502)
    rng.shuffle(tasks)
    return tasks


async def run_one(
    client: AsyncOpenAI,
    sema: asyncio.Semaphore,
    family_label: str,
    sample: Dict[str, Any],
    gold: Any,
    source_data: Optional[Dict[str, Any]],
) -> Dict[str, Any]:
    async with sema:
        route, route_usage, route_err = await route_async(client, sample)
        induction_usage = {"prompt_tokens": 0, "completion_tokens": 0, "cost_usd": 0.0}
        spec_family = None
        pred = None
        failure_mode = None
        ok = False

        if family_label == "unsupported":
            ok = route["decision"] == "reject"
            failure_mode = None if ok else f"false_accept:{route.get('family')}"
            return {
                "family_label": family_label,
                "expected_route": "reject",
                "route": route,
                "spec_family": None,
                "pred": None,
                "gold": "reject",
                "ok": ok,
                "failure_mode": failure_mode,
                "usage": route_usage,
                "source_meta": source_data,
            }

        expected_route_family = family_label
        if route_err:
            failure_mode = f"router_api_error:{route_err}"
        elif route["decision"] != "supported":
            failure_mode = "false_reject"
        elif route["family"] != expected_route_family:
            failure_mode = f"wrong_route:{route.get('family')}"
        else:
            spec, induction_usage, api_err = await induce_async(client, sample)
            spec_family = spec.inference_family if spec else None
            expected_spec_family = EXPECTED_SPEC_FAMILY[family_label]
            if spec is None:
                failure_mode = f"spec_parse_fail:{api_err}" if api_err else "spec_parse_fail"
            elif spec_family != expected_spec_family:
                failure_mode = f"wrong_spec_family:{spec_family}"
            else:
                errors = spec.validate()
                if errors:
                    failure_mode = f"spec_validate_fail:{errors[0][:80]}"
                else:
                    try:
                        solver = compile_solver(spec)
                        if family_label == "nb":
                            obs_str = {
                                s: ("present" if v else "absent")
                                for s, v in source_data["patient_symptoms"].items()
                            }
                            pred = solver.predict(obs_str)
                        elif family_label == "hmm":
                            pred, _ = solver.predict_with_scores(source_data["obs_sequence"])
                        elif family_label == "blind":
                            pred = solver.solve_from_text(sample["contexts"], sample["query"], sample["graph"])
                    except Exception as e:
                        failure_mode = f"solve_or_compile_err:{str(e)[:80]}"

        if pred is not None:
            if family_label == "blind":
                ok = isinstance(pred, (int, float)) and abs(pred - gold) < 0.01
            else:
                ok = pred == gold
            if not ok and failure_mode is None:
                failure_mode = "wrong_answer"

        return {
            "family_label": family_label,
            "expected_route": expected_route_family,
            "route": route,
            "spec_family": spec_family,
            "pred": str(pred) if pred is not None else None,
            "gold": str(gold),
            "ok": ok,
            "failure_mode": failure_mode,
            "usage": combine_usage(route_usage, induction_usage),
            "source_meta": None,
        }


def wilson(k: int, n: int) -> Tuple[float, float]:
    if n == 0:
        return (0.0, 1.0)
    z = 1.96
    p = k / n
    denom = 1 + z**2 / n
    center = (p + z**2 / (2 * n)) / denom
    margin = z * sqrt(p * (1 - p) / n + z**2 / (4 * n**2)) / denom
    return (max(0.0, center - margin), min(1.0, center + margin))


async def main() -> None:
    load_dotenv_if_present()
    api_key = os.environ.get("OPENROUTER_API_KEY")
    if not api_key:
        raise RuntimeError("OPENROUTER_API_KEY 环境变量未设置")
    proxy = os.environ.get("HTTPS_PROXY", "http://127.0.0.1:7897")
    client = AsyncOpenAI(
        base_url="https://openrouter.ai/api/v1",
        api_key=api_key,
        http_client=httpx.AsyncClient(proxy=proxy, timeout=300),
    )
    sema = asyncio.Semaphore(SEMA)
    tasks = build_tasks()

    family_counts: Dict[str, int] = {}
    for family_label, *_ in tasks:
        family_counts[family_label] = family_counts.get(family_label, 0) + 1

    print(f"=== Mixed open-set E2E | n_total={len(tasks)} | model={MODEL} | sema={SEMA} ===")
    for fam, count in sorted(family_counts.items()):
        print(f"  {fam}: {count}")

    t0 = time.time()
    results = await asyncio.gather(*[run_one(client, sema, fam, sample, gold, src) for fam, sample, gold, src in tasks])
    elapsed = time.time() - t0

    by_family: Dict[str, Dict[str, int]] = {}
    for r in results:
        fam = r["family_label"]
        by_family.setdefault(fam, {"n": 0, "ok": 0, "routed_or_rejected": 0})
        by_family[fam]["n"] += 1
        by_family[fam]["ok"] += int(r["ok"])
        if fam == "unsupported":
            by_family[fam]["routed_or_rejected"] += int(r["route"]["decision"] == "reject")
        else:
            by_family[fam]["routed_or_rejected"] += int(r["route"]["decision"] == "supported" and r["route"]["family"] == fam)

    total_ok = sum(int(r["ok"]) for r in results)
    total_n = len(results)
    supported = [r for r in results if r["family_label"] != "unsupported"]
    unsupported = [r for r in results if r["family_label"] == "unsupported"]
    supported_ok = sum(int(r["ok"]) for r in supported)
    reject_ok = sum(int(r["ok"]) for r in unsupported)
    lo, hi = wilson(total_ok, total_n)

    print(f"\nElapsed: {elapsed:.1f}s")
    print(f"Open-set E2E: {total_ok}/{total_n} = {total_ok * 100 / total_n:.1f}% [{lo * 100:.1f}, {hi * 100:.1f}]")
    if supported:
        slo, shi = wilson(supported_ok, len(supported))
        print(f"Supported solve: {supported_ok}/{len(supported)} = {supported_ok * 100 / len(supported):.1f}% [{slo * 100:.1f}, {shi * 100:.1f}]")
    if unsupported:
        rlo, rhi = wilson(reject_ok, len(unsupported))
        print(f"Unsupported reject: {reject_ok}/{len(unsupported)} = {reject_ok * 100 / len(unsupported):.1f}% [{rlo * 100:.1f}, {rhi * 100:.1f}]")

    print("\n--- Per-family ---")
    for fam in ["blind", "nb", "hmm", "unsupported"]:
        if fam in by_family:
            d = by_family[fam]
            flo, fhi = wilson(d["ok"], d["n"])
            print(f"  {fam:12s} ok={d['ok']}/{d['n']} = {d['ok'] * 100 / d['n']:.1f}% [{flo * 100:.1f}, {fhi * 100:.1f}]")

    fm_counts: Dict[str, int] = {}
    for r in results:
        if r["failure_mode"]:
            key = r["failure_mode"].split(":")[0]
            fm_counts[key] = fm_counts.get(key, 0) + 1
    print("\n--- Failure modes ---")
    if not fm_counts:
        print("  none")
    for key, count in sorted(fm_counts.items(), key=lambda x: -x[1]):
        print(f"  {key}: {count}")

    prompt_tokens = sum(r["usage"]["prompt_tokens"] for r in results)
    completion_tokens = sum(r["usage"]["completion_tokens"] for r in results)
    total_cost_usd = sum(r["usage"].get("cost_usd", 0.0) for r in results)

    out = {
        "experiment": "Mixed open-set E2E with supported-family routing and unsupported rejection",
        "model": MODEL,
        "concurrency": SEMA,
        "elapsed_sec": elapsed,
        "n_per_supported_family": N_PER_FAMILY,
        "n_unsupported": N_UNSUPPORTED,
        "families": family_counts,
        "overall": {
            "open_set_correct": total_ok,
            "n_total": total_n,
            "open_set_acc": total_ok / total_n,
            "open_set_wilson95": list(wilson(total_ok, total_n)),
            "supported_correct": supported_ok,
            "n_supported": len(supported),
            "supported_acc": supported_ok / len(supported) if supported else None,
            "reject_correct": reject_ok,
            "n_unsupported": len(unsupported),
            "reject_acc": reject_ok / len(unsupported) if unsupported else None,
        },
        "per_family": by_family,
        "failure_modes": fm_counts,
        "results": results,
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    out_path = f"baselines/results/mixed_open_set_e2e_{time.strftime('%Y%m%d_%H%M%S')}.json"
    save_artifact(
        out_path,
        out,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        total_cost_usd=total_cost_usd if total_cost_usd > 0 else None,
        model_id=MODEL,
        extra_meta={
            "script": "baselines/run_mixed_open_set_e2e.py",
            "n_per_family": N_PER_FAMILY,
            "n_unsupported": N_UNSUPPORTED,
            "concurrency": SEMA,
        },
    )
    print(f"\nSaved: {out_path}")


if __name__ == "__main__":
    asyncio.run(main())
