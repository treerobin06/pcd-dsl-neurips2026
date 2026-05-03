#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Reliability of adversarial NB/HMM TaskSpec induction.

This runner measures a narrow but reviewer-facing question: when the LLM sees an
adversarial natural-language instance from a held-out probabilistic family, how
often does it emit a compilable TaskSpec that solves the instance on the first
try, and how often does a short diagnostic refinement recover it?
"""

from __future__ import annotations

import argparse
import asyncio
import os
import random
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Tuple

import httpx
from openai import AsyncOpenAI

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from _artifact_schema import accumulate_usage, save_artifact
from baselines.run_held_out_family import generate_naive_bayes_problem
from baselines.run_hmm_held_out import generate_hmm_problem
from baselines.run_nl_e2e_stress import nb_adversarial_sample, hmm_adversarial_sample, wilson
from inductor.inductor import _format_samples, _load_prompt_template, _parse_taskspec_response
from taskspec.compiler import compile_solver


RESULTS_DIR = Path(__file__).parent / "results"


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
    load_dotenv(Path(__file__).resolve().parents[1] / ".env")
    api_key = os.environ.get("OPENROUTER_API_KEY")
    if not api_key:
        raise RuntimeError("OPENROUTER_API_KEY is not set")
    proxy = os.environ.get("HTTPS_PROXY", os.environ.get("HTTP_PROXY", "http://127.0.0.1:7897"))
    return AsyncOpenAI(
        base_url="https://openrouter.ai/api/v1",
        api_key=api_key,
        http_client=httpx.AsyncClient(proxy=proxy, timeout=300),
    )


def build_prompt(sample: Dict[str, Any], diagnostics: str = "") -> str:
    template = _load_prompt_template()
    prompt = template.replace("{samples}", _format_samples([sample], max_samples=1))
    if diagnostics:
        prompt += (
            "\n\n## Previous Attempt Diagnostics\n\n"
            "Your previous TaskSpec failed verification. Here are the diagnostics:\n\n"
            f"{diagnostics}\n\n"
            "Please fix the TaskSpec based on these diagnostics. Output ONLY the corrected JSON."
        )
    return prompt


async def induce_once(
    client: AsyncOpenAI,
    model: str,
    sample: Dict[str, Any],
    temperature: float,
    diagnostics: str = "",
) -> Tuple[Any, Dict[str, float], str | None]:
    try:
        resp = await client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": build_prompt(sample, diagnostics)}],
            max_tokens=4096,
            temperature=temperature,
        )
        usage = accumulate_usage(resp.usage)
        usage["cost_usd"] = float(getattr(resp.usage, "cost", 0) or 0)
        spec = _parse_taskspec_response(resp.choices[0].message.content or "")
        return spec, usage, None
    except Exception as exc:
        return None, {"prompt_tokens": 0, "completion_tokens": 0, "cost_usd": 0.0}, str(exc)[:300]


def verify_nb(spec: Any, problem: Dict[str, Any]) -> Tuple[bool, str, Dict[str, Any]]:
    if spec is None:
        return False, "parse_failed", {}
    if spec.inference_family != "naive_bayes":
        return False, f"wrong_family:{spec.inference_family}", {"family": spec.inference_family}
    errors = spec.validate()
    if errors:
        return False, "validate_failed", {"errors": errors}
    try:
        solver = compile_solver(spec)
        obs = {s: ("present" if v else "absent") for s, v in problem["patient_symptoms"].items()}
        pred = solver.predict(obs)
    except Exception as exc:
        return False, "compile_or_solve_failed", {"exception": str(exc)[:300]}
    ok = pred == problem["gold_diagnosis"]
    return ok, "ok" if ok else "wrong_answer", {"pred": pred, "gold": problem["gold_diagnosis"]}


def verify_hmm(spec: Any, problem: Dict[str, Any]) -> Tuple[bool, str, Dict[str, Any]]:
    if spec is None:
        return False, "parse_failed", {}
    if spec.inference_family != "hmm_forward":
        return False, f"wrong_family:{spec.inference_family}", {"family": spec.inference_family}
    errors = spec.validate()
    if errors:
        return False, "validate_failed", {"errors": errors}
    try:
        solver = compile_solver(spec)
        pred, scores = solver.predict_with_scores(problem["obs_sequence"])
    except Exception as exc:
        return False, "compile_or_solve_failed", {"exception": str(exc)[:300]}
    ok = pred == problem["gold_state"]
    return ok, "ok" if ok else "wrong_answer", {"pred": pred, "gold": problem["gold_state"], "scores": scores}


def diagnostics_from(status: str, details: Dict[str, Any]) -> str:
    if not details:
        return f"Verification failed with status={status}."
    return f"Verification failed with status={status}; details={details}."


async def run_trial(
    client: AsyncOpenAI,
    sema: asyncio.Semaphore,
    family: str,
    i: int,
    model: str,
    max_rounds: int,
    temperature: float,
    nb_base_seed: int,
    hmm_base_seed: int,
) -> Dict[str, Any]:
    async with sema:
        if family == "nb":
            seed = nb_base_seed + i
            problem = generate_naive_bayes_problem(n_diseases=4, n_symptoms=6, seed=seed)
            sample = nb_adversarial_sample(problem, random.Random(seed + 99999))
            verifier = verify_nb
        elif family == "hmm":
            seed = hmm_base_seed + i
            problem = generate_hmm_problem(n_states=4, n_obs=5, seq_length=8, seed=seed)
            sample = hmm_adversarial_sample(problem, random.Random(seed + 99999))
            verifier = verify_hmm
        else:
            raise ValueError(f"unknown family: {family}")

        attempts: List[Dict[str, Any]] = []
        diagnostics = ""
        final_ok = False
        final_status = "not_run"
        final_details: Dict[str, Any] = {}
        usage_total = {"prompt_tokens": 0, "completion_tokens": 0, "cost_usd": 0.0}

        for round_idx in range(max_rounds):
            spec, usage, api_err = await induce_once(
                client,
                model=model,
                sample=sample,
                temperature=temperature if round_idx == 0 else min(temperature, 0.3),
                diagnostics=diagnostics,
            )
            usage_total["prompt_tokens"] += usage["prompt_tokens"]
            usage_total["completion_tokens"] += usage["completion_tokens"]
            usage_total["cost_usd"] += usage.get("cost_usd", 0.0)

            if api_err:
                ok, status, details = False, "api_error", {"error": api_err}
            else:
                ok, status, details = verifier(spec, problem)

            attempts.append(
                {
                    "round": round_idx + 1,
                    "ok": ok,
                    "status": status,
                    "details": details,
                    "family": getattr(spec, "inference_family", None) if spec else None,
                }
            )
            final_ok, final_status, final_details = ok, status, details
            if ok:
                break
            diagnostics = diagnostics_from(status, details)

        return {
            "family": family,
            "i": i,
            "seed": seed,
            "first_pass": attempts[0]["ok"] if attempts else False,
            "final_ok": final_ok,
            "rounds_used": len(attempts),
            "final_status": final_status,
            "final_details": final_details,
            "attempts": attempts,
            "usage": usage_total,
        }


def summarize(rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    n = len(rows)
    first = sum(1 for r in rows if r["first_pass"])
    final = sum(1 for r in rows if r["final_ok"])
    first_ci = wilson(first, n)
    final_ci = wilson(final, n)
    failure_counts: Dict[str, int] = {}
    for r in rows:
        if not r["final_ok"]:
            failure_counts[r["final_status"]] = failure_counts.get(r["final_status"], 0) + 1
    return {
        "n": n,
        "first_pass_correct": first,
        "first_pass_rate": first / n if n else 0.0,
        "first_pass_wilson_95ci": first_ci,
        "final_correct": final,
        "final_rate": final / n if n else 0.0,
        "final_wilson_95ci": final_ci,
        "failure_counts": dict(sorted(failure_counts.items())),
    }


async def main() -> None:
    parser = argparse.ArgumentParser(description="NB/HMM adversarial inductor reliability")
    parser.add_argument("--model", default=os.environ.get("MODEL", "openai/gpt-4o-mini"))
    parser.add_argument("--n-nb", type=int, default=50)
    parser.add_argument("--n-hmm", type=int, default=50)
    parser.add_argument("--nb-base-seed", type=int, default=7000)
    parser.add_argument("--hmm-base-seed", type=int, default=8000)
    parser.add_argument("--max-rounds", type=int, default=2)
    parser.add_argument("--temperature", type=float, default=0.7)
    parser.add_argument("--sema", type=int, default=int(os.environ.get("SEMA", "10")))
    args = parser.parse_args()

    client = make_client()
    sema = asyncio.Semaphore(args.sema)
    t0 = time.time()
    print(
        "=== NB/HMM inductor reliability | "
        f"model={args.model} nb={args.n_nb} hmm={args.n_hmm} "
        f"max_rounds={args.max_rounds} temp={args.temperature} ==="
    )

    tasks = [
        run_trial(client, sema, "nb", i, args.model, args.max_rounds, args.temperature, args.nb_base_seed, args.hmm_base_seed)
        for i in range(args.n_nb)
    ] + [
        run_trial(client, sema, "hmm", i, args.model, args.max_rounds, args.temperature, args.nb_base_seed, args.hmm_base_seed)
        for i in range(args.n_hmm)
    ]
    rows = await asyncio.gather(*tasks)
    elapsed = time.time() - t0

    by_family = {
        "nb": summarize([r for r in rows if r["family"] == "nb"]),
        "hmm": summarize([r for r in rows if r["family"] == "hmm"]),
    }
    overall = summarize(rows)

    print(f"Elapsed: {elapsed:.1f}s")
    for name, summary in [("overall", overall), *by_family.items()]:
        print(
            f"{name}: first {summary['first_pass_correct']}/{summary['n']}="
            f"{summary['first_pass_rate']*100:.1f}%, final "
            f"{summary['final_correct']}/{summary['n']}={summary['final_rate']*100:.1f}%"
        )

    prompt_tokens = sum(r["usage"]["prompt_tokens"] for r in rows)
    completion_tokens = sum(r["usage"]["completion_tokens"] for r in rows)
    total_cost_usd = sum(r["usage"].get("cost_usd", 0.0) for r in rows)
    out = {
        "experiment": "NB/HMM adversarial TaskSpec induction reliability",
        "model": args.model,
        "config": vars(args),
        "elapsed_sec": elapsed,
        "summary": {"overall": overall, **by_family},
        "results": rows,
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    model_tag = args.model.replace("/", "_")
    out_path = RESULTS_DIR / f"inductor_reliability_nb_hmm_{model_tag}_{time.strftime('%Y%m%d_%H%M%S')}.json"
    save_artifact(
        out_path,
        out,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        total_cost_usd=total_cost_usd if total_cost_usd > 0 else None,
        model_id=args.model,
        extra_meta={
            "script": "baselines/run_inductor_reliability_nb_hmm.py",
            "n_nb": args.n_nb,
            "n_hmm": args.n_hmm,
            "max_rounds": args.max_rounds,
            "temperature": args.temperature,
        },
    )
    print(f"Saved: {out_path}")


if __name__ == "__main__":
    asyncio.run(main())
