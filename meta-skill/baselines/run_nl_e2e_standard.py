"""Standard config NL E2E for NB and HMM held-out families.

Tree 2026-04-28 决策: hard/medium difficulty variation 不放 paper (effect 不好稀释 contribution).
Standard config (NB n_dis=4 n_sym=5 / HMM n_states=3 n_obs=4 seq_length=5) 跑 NL E2E
显示真"NL→answer 端到端泛化" 数字 (期望 90%+).

Pipeline per sample:
  NL task description (no structured CPT dict)
    → mini emit TaskSpec via inductor
    → compile_solver instantiates {NBSolver|HMMSolver}
    → solver runs 5 dsl ops (condition+multiply+marginalize+normalize+argmax)
    → predict
    → compare to gold

This is **真 NL E2E** (LLM parses NL CPT/likelihoods/transition/emission tables),
not structured-input component evaluation.

Async sema=25 (CLAUDE.md 强制并发规则).
"""

import sys
import os
import json
import time
import asyncio
from math import sqrt
from typing import Dict

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import httpx
from openai import AsyncOpenAI

from baselines.run_held_out_family import generate_naive_bayes_problem
from baselines.run_hmm_held_out import generate_hmm_problem
from inductor.inductor import (
    _load_prompt_template,
    _format_samples,
    _parse_taskspec_response,
)
from taskspec.compiler import compile_solver

MODEL = "openai/gpt-4o-mini"
SEMA = 25
N = 50  # per family (paper-grade)


# ─── NL sample builders ────────────────────────────────────────────────

def nb_nl_sample(problem: Dict) -> Dict:
    """Build NL natural-language sample from synthetic NB problem.

    No structured CPT dict — mini must parse priors / likelihoods / observed
    from natural language text fields.
    """
    diseases = problem["diseases"]
    priors = problem["priors"]
    likelihoods = problem["likelihoods"]
    patient = problem["patient_symptoms"]
    symptoms = problem["symptoms"]

    diseases_text = "Diseases: " + ", ".join(
        f"{d} (prior {priors[d]:.3f})" for d in diseases
    )
    # Show BOTH present and absent probabilities so spec covers both values
    lik_lines = []
    for d in diseases:
        parts = []
        for s in symptoms:
            p_present = likelihoods[d][s]
            p_absent = 1.0 - p_present
            parts.append(f"{s} (present {p_present:.2f}, absent {p_absent:.2f})")
        lik_lines.append(f"- {d}: " + "; ".join(parts))
    likelihoods_text = "P(symptom value | disease) — each symptom has 'present' and 'absent' values:\n" + "\n".join(lik_lines)
    # Use 'present'/'absent' consistently (matches likelihoods_text values)
    observed_text = "Patient observation: " + ", ".join(
        f"{s} {'present' if v else 'absent'}" for s, v in patient.items()
    )
    return {
        "task_description": "Identify the most likely disease from observed patient symptoms.",
        "background": "We consider candidate diseases with prior probabilities. For each disease, we know the conditional probability of each symptom being present.",
        "diseases_text": diseases_text,
        "likelihoods_text": likelihoods_text,
        "observed_text": observed_text,
    }


def hmm_nl_sample(problem: Dict) -> Dict:
    """Build NL natural-language sample from synthetic HMM problem."""
    states = problem["states"]
    obs_set = problem["observations"]
    initial = problem["initial_dist"]
    transition = problem["transition"]
    emission = problem["emission"]
    obs_seq = problem["obs_sequence"]

    initial_text = "Initial probabilities: " + ", ".join(
        f"P({s})={initial[s]:.3f}" for s in states
    )
    trans_lines = []
    for s_from in states:
        nexts = ", ".join(
            f"P({s_to}|{s_from})={transition[s_from][s_to]:.3f}" for s_to in states
        )
        trans_lines.append(f"  from {s_from}: {nexts}")
    transition_text = "Transitions:\n" + "\n".join(trans_lines)
    emit_lines = []
    for s in states:
        emits = ", ".join(f"P({o}|{s})={emission[s][o]:.3f}" for o in obs_set)
        emit_lines.append(f"  in {s}: {emits}")
    emission_text = "Emissions:\n" + "\n".join(emit_lines)
    obs_text = "Observed sequence (in order): " + ", ".join(obs_seq)
    return {
        "task_description": "Predict the most likely hidden state at the final time step in a Hidden Markov Model.",
        "states_text": "Hidden states: {" + ", ".join(states) + "}",
        "observations_set_text": "Observation alphabet: {" + ", ".join(obs_set) + "}",
        "initial_text": initial_text,
        "transition_text": transition_text,
        "emission_text": emission_text,
        "obs_sequence_text": obs_text,
    }


# ─── Inductor async ────────────────────────────────────────────────────

async def induce_async(client: AsyncOpenAI, sample: Dict, model_id: str):
    template = _load_prompt_template()
    samples_text = _format_samples([sample], max_samples=1)
    prompt = template.replace("{samples}", samples_text)
    try:
        resp = await client.chat.completions.create(
            model=model_id,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=4096,
            temperature=0.0,
        )
        return _parse_taskspec_response(resp.choices[0].message.content or "")
    except Exception:
        return None


# ─── Per-task runners ──────────────────────────────────────────────────

async def run_nb(client, sema, i):
    async with sema:
        p = generate_naive_bayes_problem(n_diseases=4, n_symptoms=5, seed=2000 + i)
        sample = nb_nl_sample(p)
        spec = await induce_async(client, sample, MODEL)
        family = spec.inference_family if spec else None
        pred = None
        err = None
        if spec and family == "naive_bayes":
            errors = spec.validate()
            if not errors:
                try:
                    solver = compile_solver(spec)
                    obs_str = {s: ("present" if v else "absent") for s, v in p["patient_symptoms"].items()}
                    pred = solver.predict(obs_str)
                except Exception as e:
                    err = str(e)[:120]
            else:
                err = f"validate_err:{errors}"
        elif spec is None:
            err = "spec_parse_fail"
        else:
            err = f"wrong_family:{family}"
        ok = pred == p["gold_diagnosis"]
        return {
            "i": i,
            "seed": 2000 + i,
            "family": family,
            "pred": pred,
            "gold": p["gold_diagnosis"],
            "ok": ok,
            "err": err,
        }


async def run_hmm(client, sema, i):
    async with sema:
        p = generate_hmm_problem(n_states=3, n_obs=4, seq_length=5, seed=3000 + i)
        sample = hmm_nl_sample(p)
        spec = await induce_async(client, sample, MODEL)
        family = spec.inference_family if spec else None
        pred = None
        err = None
        if spec and family == "hmm_forward":
            errors = spec.validate()
            if not errors:
                try:
                    solver = compile_solver(spec)
                    pred, _ = solver.predict_with_scores(p["obs_sequence"])
                except Exception as e:
                    err = str(e)[:120]
            else:
                err = f"validate_err:{errors}"
        elif spec is None:
            err = "spec_parse_fail"
        else:
            err = f"wrong_family:{family}"
        ok = pred == p["gold_state"]
        return {
            "i": i,
            "seed": 3000 + i,
            "family": family,
            "pred": pred,
            "gold": p["gold_state"],
            "ok": ok,
            "err": err,
        }


# ─── Wilson 95% CI ─────────────────────────────────────────────────────

def wilson(k, n):
    if n == 0:
        return (0, 1)
    z = 1.96
    p = k / n
    denom = 1 + z ** 2 / n
    center = (p + z ** 2 / (2 * n)) / denom
    margin = z * sqrt(p * (1 - p) / n + z ** 2 / (4 * n ** 2)) / denom
    return (max(0, center - margin), min(1, center + margin))


# ─── Main ──────────────────────────────────────────────────────────────

async def main():
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
    print(f"=== Standard NL E2E | sema={SEMA} | n={N}+{N} | model={MODEL} ===")
    t0 = time.time()
    nb_results, hmm_results = await asyncio.gather(
        asyncio.gather(*[run_nb(client, sema, i) for i in range(N)]),
        asyncio.gather(*[run_hmm(client, sema, i) for i in range(N)]),
    )
    elapsed = time.time() - t0
    n_nb = sum(r["ok"] for r in nb_results)
    n_hmm = sum(r["ok"] for r in hmm_results)
    nb_lo, nb_hi = wilson(n_nb, N)
    hmm_lo, hmm_hi = wilson(n_hmm, N)

    print(f"\nElapsed: {elapsed:.1f}s")
    print(f"NB NL E2E:  {n_nb}/{N} = {n_nb * 100 / N:.1f}% [{nb_lo * 100:.1f}, {nb_hi * 100:.1f}]")
    print(f"HMM NL E2E: {n_hmm}/{N} = {n_hmm * 100 / N:.1f}% [{hmm_lo * 100:.1f}, {hmm_hi * 100:.1f}]")

    print(f"\nNB failures: {N - n_nb}")
    for r in nb_results:
        if not r["ok"]:
            print(f"  i={r['i']} family={r['family']} pred={r['pred']} gold={r['gold']} err={r['err']}")
    print(f"\nHMM failures: {N - n_hmm}")
    for r in hmm_results:
        if not r["ok"]:
            print(f"  i={r['i']} family={r['family']} pred={r['pred']} gold={r['gold']} err={r['err']}")

    out = {
        "experiment": "C2 Standard NL E2E (Tree 2026-04-28: hard 不放 standard 显示泛化)",
        "model": MODEL,
        "route": "NL natural-language input → mini emit TaskSpec → compile → run",
        "config": {
            "nb": {"n_diseases": 4, "n_symptoms": 5},
            "hmm": {"n_states": 3, "n_obs": 4, "seq_length": 5},
        },
        "concurrency": SEMA,
        "elapsed_sec": elapsed,
        "nb_nl_e2e": {
            "n": N,
            "correct": n_nb,
            "wilson_95ci": [nb_lo, nb_hi],
            "results": nb_results,
        },
        "hmm_nl_e2e": {
            "n": N,
            "correct": n_hmm,
            "wilson_95ci": [hmm_lo, hmm_hi],
            "results": hmm_results,
        },
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    out_path = f"baselines/results/standard_nl_e2e_{time.strftime('%Y%m%d_%H%M%S')}.json"
    with open(out_path, "w") as f:
        json.dump(out, f, indent=2)
    print(f"\nSaved: {out_path}")


if __name__ == "__main__":
    asyncio.run(main())
