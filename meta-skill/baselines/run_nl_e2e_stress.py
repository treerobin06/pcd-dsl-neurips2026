"""Adversarial NL E2E for NB and HMM held-out families.

Tree 2026-04-28 决策: stress problem config (大 n) 无效——mini 5/5 全对，因为
mini 只做 parse + family ID, compiler 精确求解。要让数字降到 93-97%, 必须
增加 mini parse 的难度——adversarial NL design.

Adversarial NL 设计三招:
1. **Hedge phrasing** — "around 85%" / "approximately 70%" / "~30%" / "low chance"
2. **Distractor** — 无关 context 注释 ("Note: this is X" / "In clinical practice...")
3. **Order shuffle** — symptom 顺序与 likelihood 表不同 + present/absent 写法多变
   ("not noted" / "absent" / "not present")

期望 mini 错 1-3/30 → 27-29/30 = 90-97% (Wilson [80, 99]).

vs standard NL E2E 50/50 = 100% [92.9, 100] 形成对比.

Async sema=25.
"""

import sys
import os
import json
import time
import asyncio
import random
import math
from math import sqrt
from typing import Dict, List

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
N = 60


# ─── Hedge utilities ───────────────────────────────────────────────────

def hedge_pct(p: float, rng: random.Random) -> str:
    """Hedge 表述, 总是带精确数字, mix verbal-with-pct + approx + tilde + around + range."""
    pct = round(p * 100)
    style = rng.choices(
        ["range", "verbal_with_pct", "approx", "tilde", "around"],
        weights=[0.05, 0.30, 0.30, 0.20, 0.15],
    )[0]
    if style == "range":
        delta = rng.choice([3, 5])  # narrow range, 不太狠
        lo = max(0, pct - delta)
        hi = min(100, pct + delta)
        return f"between {lo}% and {hi}%"
    elif style == "verbal_with_pct":
        if p >= 0.85:
            return rng.choice([f"very common (~{pct}%)", f"highly likely (~{pct}%)"])
        elif p >= 0.65:
            return rng.choice([f"frequent (~{pct}%)", f"common (~{pct}%)"])
        elif p >= 0.4:
            return rng.choice([f"moderate (~{pct}%)", f"about half (~{pct}%)"])
        elif p >= 0.2:
            return rng.choice([f"uncommon (~{pct}%)", f"infrequent (~{pct}%)"])
        else:
            return rng.choice([f"rare (~{pct}%)", f"unusual (~{pct}%)"])
    elif style == "approx":
        return f"approximately {pct}%"
    elif style == "tilde":
        return f"~{pct}%"
    else:
        return f"around {pct}%"


NB_DISTRACTORS = [
    "Note: this is a teaching diagnostic panel, not for clinical use.",
    "In clinical practice, comorbidities can complicate diagnosis.",
    "(Symptoms not in this panel are not considered for diagnosis.)",
    "Each disease may also have other symptoms not listed here.",
    "Many patients show atypical presentations.",
]

HMM_DISTRACTORS = [
    "Note: this model assumes stationary transitions.",
    "(Real weather has more states than modeled here.)",
    "Each transition is conditionally independent of past states.",
    "Observations may be noisy due to measurement error.",
]


# ─── Adversarial NL builders ───────────────────────────────────────────

def nb_adversarial_sample(problem: Dict, rng: random.Random) -> Dict:
    """Adversarial NL for NB: hedge + distractor + shuffle."""
    diseases = list(problem["diseases"])
    symptoms = list(problem["symptoms"])
    priors = problem["priors"]
    likelihoods = problem["likelihoods"]
    patient = problem["patient_symptoms"]

    # 1. Diseases text — priors with hedge
    disease_lines = []
    rng.shuffle(diseases)  # 打乱顺序!
    for d in diseases:
        disease_lines.append(f"{d}: prior probability {hedge_pct(priors[d], rng)}")
    diseases_text = "Diseases under consideration:\n- " + "\n- ".join(disease_lines)

    # 2. Likelihoods text — hedge + distractor
    lik_lines = []
    for d in diseases:
        # 把 symptoms 顺序也打乱
        shuffled_symptoms = list(symptoms)
        rng.shuffle(shuffled_symptoms)
        parts = []
        for s in shuffled_symptoms:
            p_present = likelihoods[d][s]
            p_absent = 1.0 - p_present
            parts.append(
                f"{s}: present with probability {hedge_pct(p_present, rng)} "
                f"(absent with probability {hedge_pct(p_absent, rng)})"
            )
        lik_lines.append(f"In **{d}** patients, symptom probabilities are: " + "; ".join(parts) + ".")

    # 加 1-2 个 distractor 段落
    distractor1 = rng.choice(NB_DISTRACTORS)
    distractor2 = rng.choice([d for d in NB_DISTRACTORS if d != distractor1])
    likelihoods_text = (
        "P(symptom value | disease) — extracted from medical literature. "
        f"{distractor1}\n\n" + "\n".join(lik_lines) + f"\n\n{distractor2}"
    )

    # 3. Observed text — present/absent 写法多变 + 打乱顺序
    observed_phrases = {
        True: ["present", "noted", "observed", "confirmed"],
        False: ["absent", "not present", "not noted", "denied"],
    }
    shuffled_obs = list(symptoms)
    rng.shuffle(shuffled_obs)
    obs_parts = []
    for s in shuffled_obs:
        v = patient[s]
        phrase = rng.choice(observed_phrases[v])
        obs_parts.append(f"{s} {phrase}")
    observed_text = "Patient observation: " + "; ".join(obs_parts) + "."

    return {
        "task_description": "Identify the most likely disease from observed patient symptoms.",
        "background": "We consider candidate diseases with prior probabilities. For each disease, we know the conditional probability of each symptom being present.",
        "diseases_text": diseases_text,
        "likelihoods_text": likelihoods_text,
        "observed_text": observed_text,
    }


def hmm_adversarial_sample(problem: Dict, rng: random.Random) -> Dict:
    """Adversarial NL for HMM: hedge + distractor + shuffle."""
    states = list(problem["states"])
    obs_set = list(problem["observations"])
    initial = problem["initial_dist"]
    transition = problem["transition"]
    emission = problem["emission"]
    obs_seq = problem["obs_sequence"]

    # 1. Initial — hedge + shuffle
    rng.shuffle(states)
    initial_lines = [f"P({s}) = {hedge_pct(initial[s], rng)}" for s in states]
    initial_text = "Initial state probabilities at time 0: " + "; ".join(initial_lines) + "."

    # 2. Transitions — hedge + shuffle + distractor
    distractor = rng.choice(HMM_DISTRACTORS)
    trans_lines = []
    for s_from in states:
        shuffled_to = list(states)
        rng.shuffle(shuffled_to)
        nexts = ", ".join(
            f"P({s_to}|{s_from}) = {hedge_pct(transition[s_from][s_to], rng)}"
            for s_to in shuffled_to
        )
        trans_lines.append(f"  When current state is {s_from}, next-state distribution: {nexts}")
    transition_text = f"State transition matrix. {distractor}\n" + "\n".join(trans_lines)

    # 3. Emissions — hedge + shuffle
    emit_lines = []
    for s in states:
        shuffled_obs_set = list(obs_set)
        rng.shuffle(shuffled_obs_set)
        emits = ", ".join(
            f"P({o}|{s}) = {hedge_pct(emission[s][o], rng)}" for o in shuffled_obs_set
        )
        emit_lines.append(f"  Emitted from state {s}: {emits}")
    emission_text = "Emission probabilities:\n" + "\n".join(emit_lines)

    obs_text = (
        "Sequence of observations recorded in temporal order: "
        + " → ".join(obs_seq)
        + "."
    )

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

async def run_nb_adversarial(client, sema, i):
    async with sema:
        # 略大: n_dis=4, n_sym=6 + adversarial NL
        p = generate_naive_bayes_problem(n_diseases=4, n_symptoms=6, seed=7000 + i)
        rng = random.Random(7000 + i + 99999)  # 独立 rng for adversarial
        sample = nb_adversarial_sample(p, rng)
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
            "seed": 7000 + i,
            "family": family,
            "pred": pred,
            "gold": p["gold_diagnosis"],
            "ok": ok,
            "err": err,
            "sample_preview": sample["likelihoods_text"][:200],
        }


async def run_hmm_adversarial(client, sema, i):
    async with sema:
        # 比 standard 略大: n_states=4, n_obs=5, seq_length=8 + adversarial NL
        p = generate_hmm_problem(n_states=4, n_obs=5, seq_length=8, seed=8000 + i)
        rng = random.Random(8000 + i + 99999)
        sample = hmm_adversarial_sample(p, rng)
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
            "seed": 8000 + i,
            "family": family,
            "pred": pred,
            "gold": p["gold_state"],
            "ok": ok,
            "err": err,
            "sample_preview": sample["transition_text"][:200],
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

    n_nb_target = int(os.environ.get("N_NB", "50"))
    n_hmm_target = int(os.environ.get("N_HMM", "60"))
    print(f"=== NL E2E ADVERSARIAL | sema={SEMA} | NB n={n_nb_target} | HMM n={n_hmm_target} | model={MODEL} ===")
    print(f"  NL design: hedge words + distractor + order shuffle (problem config slightly stressed)")
    t0 = time.time()
    nb_results, hmm_results = await asyncio.gather(
        asyncio.gather(*[run_nb_adversarial(client, sema, i) for i in range(n_nb_target)]),
        asyncio.gather(*[run_hmm_adversarial(client, sema, i) for i in range(n_hmm_target)]),
    )
    elapsed = time.time() - t0
    n_nb = sum(r["ok"] for r in nb_results)
    n_hmm = sum(r["ok"] for r in hmm_results)
    nb_lo, nb_hi = wilson(n_nb, n_nb_target)
    hmm_lo, hmm_hi = wilson(n_hmm, n_hmm_target)

    print(f"\nElapsed: {elapsed:.1f}s")
    print(f"NB adversarial NL E2E:  {n_nb}/{n_nb_target} = {n_nb*100/n_nb_target:.1f}% [{nb_lo*100:.1f}, {nb_hi*100:.1f}]")
    print(f"HMM adversarial NL E2E: {n_hmm}/{n_hmm_target} = {n_hmm*100/n_hmm_target:.1f}% [{hmm_lo*100:.1f}, {hmm_hi*100:.1f}]")

    print(f"\nNB failures ({n_nb_target - n_nb}):")
    for r in nb_results:
        if not r["ok"]:
            print(f"  i={r['i']} family={r['family']} pred={r['pred']} gold={r['gold']} err={r['err']}")

    print(f"\nHMM failures ({n_hmm_target - n_hmm}):")
    for r in hmm_results:
        if not r["ok"]:
            print(f"  i={r['i']} family={r['family']} pred={r['pred']} gold={r['gold']} err={r['err']}")

    out = {
        "experiment": "C2 NL E2E ADVERSARIAL (Tree 2026-04-28: hedge+distractor+shuffle + slight stress)",
        "model": MODEL,
        "route": "Adversarial NL → mini emit TaskSpec → compile → run",
        "config": {
            "nb": {"n_diseases": 4, "n_symptoms": 6, "nl_style": "adversarial"},
            "hmm": {"n_states": 4, "n_obs": 5, "seq_length": 8, "nl_style": "adversarial"},
        },
        "concurrency": SEMA,
        "elapsed_sec": elapsed,
        "nb_adversarial_e2e": {
            "n": n_nb_target,
            "correct": n_nb,
            "wilson_95ci": [nb_lo, nb_hi],
            "results": nb_results,
        },
        "hmm_adversarial_e2e": {
            "n": n_hmm_target,
            "correct": n_hmm,
            "wilson_95ci": [hmm_lo, hmm_hi],
            "results": hmm_results,
        },
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    out_path = f"baselines/results/adversarial_nl_e2e_{time.strftime('%Y%m%d_%H%M%S')}.json"
    with open(out_path, "w") as f:
        json.dump(out, f, indent=2)
    print(f"\nSaved: {out_path}")


if __name__ == "__main__":
    asyncio.run(main())
