"""Mixed-family End-to-End Benchmark — Tree 2026-04-28 4-level taxonomy Level 2.

3 families shuffled (BLInD BN + NB synthetic + HMM synthetic):
- Mini agent sees NL sample, doesn't know family in advance
- Must: identify family + emit TaskSpec + compile_solver + run + compare gold

Per sample metrics:
- Family identification accuracy (correct family vs ground truth label)
- Overall E2E accuracy (final prediction matches gold)
- Conditional accuracy (given correct family ID, downstream pipeline acc)
- Failure mode breakdown (parse_fail / wrong_family / spec_validate / compile_err / solve_err / wrong_answer)

Async sema=25.
"""

import sys
import os
import json
import time
import asyncio
import csv
import random
from math import sqrt
from typing import Dict, List

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import httpx
from openai import AsyncOpenAI

from baselines.run_held_out_family import generate_naive_bayes_problem
from baselines.run_hmm_held_out import generate_hmm_problem
from baselines.run_nl_e2e_standard import nb_nl_sample, hmm_nl_sample
from inductor.inductor import (
    _load_prompt_template,
    _format_samples,
    _parse_taskspec_response,
)
from taskspec.compiler import compile_solver

MODEL = "openai/gpt-4o-mini"
SEMA = 25
N_PER_FAMILY = 30

EXPECTED_FAMILY = {
    "blind": "variable_elimination",
    "nb": "naive_bayes",
    "hmm": "hmm_forward",
}


# ─── BLInD adapter ─────────────────────────────────────────────────────

def blind_nl_sample(row: Dict) -> Dict:
    """BLInD CSV row → NL sample (already NL by design)."""
    return {
        "task_description": "Bayesian network probability inference. Compute the queried marginal probability given the network structure and the conditional probability tables.",
        "contexts": row["contexts"],
        "query": row["query"],
        "graph": row["graph"],
    }


def load_blind(n: int = 30, seed: int = 4000) -> List[Dict]:
    path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "..", "data", "external", "BLInD", "datasets", "Base_1000_examples.csv",
    )
    rows = []
    with open(path) as f:
        for r in csv.DictReader(f):
            rows.append(r)
    rng = random.Random(seed)
    rng.shuffle(rows)
    return rows[:n]


# ─── Inductor + runner ────────────────────────────────────────────────

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


async def run_one(client, sema, family_label: str, sample: Dict, gold, source_data: Dict = None):
    """Run one mixed E2E sample. Returns dict with detailed metrics."""
    async with sema:
        spec = await induce_async(client, sample, MODEL)
        emitted_family = spec.inference_family if spec else None
        expected_family = EXPECTED_FAMILY[family_label]
        family_correct = emitted_family == expected_family
        pred = None
        failure_mode = None

        if spec is None:
            failure_mode = "spec_parse_fail"
        elif not family_correct:
            failure_mode = f"wrong_family:{emitted_family}"
        else:
            errors = spec.validate()
            if errors:
                failure_mode = f"spec_validate_fail:{errors[0][:60]}"
            else:
                try:
                    solver = compile_solver(spec)
                except Exception as e:
                    failure_mode = f"compile_err:{str(e)[:60]}"
                else:
                    try:
                        if family_label == "nb":
                            obs_str = {
                                s: ("present" if v else "absent")
                                for s, v in source_data["patient_symptoms"].items()
                            }
                            pred = solver.predict(obs_str)
                        elif family_label == "hmm":
                            pred, _ = solver.predict_with_scores(source_data["obs_sequence"])
                        elif family_label == "blind":
                            pred = solver.solve_from_text(
                                sample["contexts"], sample["query"], sample["graph"]
                            )
                    except Exception as e:
                        failure_mode = f"solve_err:{str(e)[:60]}"

        # Compare to gold
        if pred is not None:
            if family_label == "blind":
                ok = isinstance(pred, (int, float)) and abs(pred - gold) < 0.01
            else:
                ok = pred == gold
            if not ok and failure_mode is None:
                failure_mode = "wrong_answer"
        else:
            ok = False

        return {
            "family_label": family_label,
            "expected_family": expected_family,
            "emitted_family": emitted_family,
            "family_correct": family_correct,
            "pred": str(pred) if pred is not None else None,
            "gold": str(gold),
            "ok": ok,
            "failure_mode": failure_mode,
        }


# ─── Wilson CI ────────────────────────────────────────────────────────

def wilson(k, n):
    if n == 0:
        return (0, 1)
    z = 1.96
    p = k / n
    denom = 1 + z ** 2 / n
    center = (p + z ** 2 / (2 * n)) / denom
    margin = z * sqrt(p * (1 - p) / n + z ** 2 / (4 * n ** 2)) / denom
    return (max(0, center - margin), min(1, center + margin))


# ─── Main ─────────────────────────────────────────────────────────────

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

    # Build task list
    tasks = []
    # NB
    for i in range(N_PER_FAMILY):
        p = generate_naive_bayes_problem(n_diseases=4, n_symptoms=5, seed=4100 + i)
        sample = nb_nl_sample(p)
        tasks.append(("nb", sample, p["gold_diagnosis"], p))
    # HMM
    for i in range(N_PER_FAMILY):
        p = generate_hmm_problem(n_states=3, n_obs=4, seq_length=5, seed=4200 + i)
        sample = hmm_nl_sample(p)
        tasks.append(("hmm", sample, p["gold_state"], p))
    # BLInD
    blind_rows = load_blind(n=N_PER_FAMILY)
    for row in blind_rows:
        sample = blind_nl_sample(row)
        gold = float(row["answers"])
        tasks.append(("blind", sample, gold, None))

    # Shuffle (Tree wants real Mixed)
    rng = random.Random(2026)
    rng.shuffle(tasks)

    print(f"=== Mixed-family E2E | sema={SEMA} | n_total={len(tasks)} | model={MODEL} ===")
    family_counts = {}
    for fam, *_ in tasks:
        family_counts[fam] = family_counts.get(fam, 0) + 1
    for fam, c in sorted(family_counts.items()):
        print(f"  {fam}: {c}")

    t0 = time.time()
    results = await asyncio.gather(
        *[run_one(client, sema, fam, samp, g, src) for fam, samp, g, src in tasks]
    )
    elapsed = time.time() - t0

    # Per-family aggregate
    by_family = {}
    for r in results:
        f = r["family_label"]
        if f not in by_family:
            by_family[f] = {"n": 0, "family_correct": 0, "e2e_correct": 0}
        by_family[f]["n"] += 1
        if r["family_correct"]:
            by_family[f]["family_correct"] += 1
        if r["ok"]:
            by_family[f]["e2e_correct"] += 1

    n_total = len(results)
    fc_total = sum(r["family_correct"] for r in results)
    oc_total = sum(r["ok"] for r in results)

    print(f"\nElapsed: {elapsed:.1f}s")
    print(f"\n--- Per-family (Family ID acc / Overall E2E acc) ---")
    for fam in ["blind", "nb", "hmm"]:
        if fam in by_family:
            d = by_family[fam]
            fc_lo, fc_hi = wilson(d["family_correct"], d["n"])
            oc_lo, oc_hi = wilson(d["e2e_correct"], d["n"])
            print(
                f"  {fam:6s}  n={d['n']}  "
                f"FamID={d['family_correct']}/{d['n']} = {d['family_correct']*100/d['n']:.1f}% [{fc_lo*100:.1f}, {fc_hi*100:.1f}]  "
                f"E2E={d['e2e_correct']}/{d['n']} = {d['e2e_correct']*100/d['n']:.1f}% [{oc_lo*100:.1f}, {oc_hi*100:.1f}]"
            )
    fc_lo, fc_hi = wilson(fc_total, n_total)
    oc_lo, oc_hi = wilson(oc_total, n_total)
    print(
        f"  TOTAL  n={n_total}  "
        f"FamID={fc_total}/{n_total} = {fc_total*100/n_total:.1f}% [{fc_lo*100:.1f}, {fc_hi*100:.1f}]  "
        f"E2E={oc_total}/{n_total} = {oc_total*100/n_total:.1f}% [{oc_lo*100:.1f}, {oc_hi*100:.1f}]"
    )

    # Failure mode breakdown
    fm_counts = {}
    for r in results:
        if r["failure_mode"]:
            key = r["failure_mode"].split(":")[0]
            fm_counts[key] = fm_counts.get(key, 0) + 1
    print(f"\n--- Failure mode breakdown (total failures: {n_total - oc_total}) ---")
    for fm, c in sorted(fm_counts.items(), key=lambda x: -x[1]):
        print(f"  {fm}: {c}")

    out = {
        "experiment": "C2 Mixed-family E2E benchmark (Tree 2026-04-28 Level 2)",
        "model": MODEL,
        "concurrency": SEMA,
        "elapsed_sec": elapsed,
        "families": list(family_counts.keys()),
        "n_per_family": N_PER_FAMILY,
        "n_total": n_total,
        "overall": {
            "family_id_correct": fc_total,
            "family_id_acc": fc_total / n_total,
            "family_id_wilson95": list(wilson(fc_total, n_total)),
            "e2e_correct": oc_total,
            "e2e_acc": oc_total / n_total,
            "e2e_wilson95": list(wilson(oc_total, n_total)),
        },
        "per_family": by_family,
        "failure_modes": fm_counts,
        "results": results,
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    out_path = f"baselines/results/mixed_e2e_{time.strftime('%Y%m%d_%H%M%S')}.json"
    with open(out_path, "w") as f:
        json.dump(out, f, indent=2)
    print(f"\nSaved: {out_path}")


if __name__ == "__main__":
    asyncio.run(main())
