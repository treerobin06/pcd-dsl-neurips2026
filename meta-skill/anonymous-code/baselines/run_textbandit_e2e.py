#!/usr/bin/env python3
"""TextBandit-style NL E2E benchmark.

The model reads a natural-language history of slot-machine pulls, emits a
TaskSpec plus parsed binary observations, then the deterministic compiler and
BanditSolver perform the Beta-Bernoulli updates and choose the posterior-mean
best arm.
"""

from __future__ import annotations

import argparse
import asyncio
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

sys.path.insert(0, str(SCRIPT_DIR.parent))

from baselines._artifact_schema import accumulate_usage, save_artifact
from solvers.bandit_solver import BanditSolver
from taskspec.compiler import compile_solver
from taskspec.schema import TaskSpec


PROMPT = """You are parsing a TextBandit-style decision problem.

The input is a natural-language history of slot-machine pulls. Each non-empty
line after "History:" and before "Question:" is exactly one observation; do
not skip or merge any history line. The words Round/Pull/Trial are synonyms.
Each feedback is binary: "won a token" means reward 1, and "lost" means reward
0.

Your task:
1. Emit a TaskSpec for a Beta-Bernoulli multi-armed bandit.
2. Extract every observed pull as an arm number and binary reward.

Return ONLY JSON with this exact shape:
{
  "task_spec": {
    "task_name": "textbandit_beta_bernoulli",
    "inference_family": "conjugate_update",
    "state_structure": {
      "type": "beta_conjugate",
      "n_arms": <number of slot machines>,
      "prior_alpha": 1.0,
      "prior_beta": 1.0
    },
    "observation_model": {
      "type": "bernoulli_reward",
      "temperature": 1.0,
      "input": "slot_machine_binary_feedback"
    },
    "decision_rule": {
      "type": "argmax_posterior_mean",
      "utility": "posterior_mean_reward_rate"
    },
    "data_format": {
      "rounds": "sequential",
      "options_per_round": <number of slot machines>,
      "feedback": "binary_reward"
    }
  },
  "observations": [
    {"arm": <1-based slot machine number>, "reward": 0 or 1}
  ]
}

Input:
{sample}
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
        http_client=httpx.AsyncClient(proxy=proxy, timeout=180),
    )


def extract_json(text: str) -> Optional[Dict[str, Any]]:
    m = re.search(r"```(?:json)?\s*\n(.*?)```", text, re.DOTALL)
    if m:
        try:
            return json.loads(m.group(1).strip())
        except json.JSONDecodeError:
            pass
    try:
        return json.loads(text.strip())
    except json.JSONDecodeError:
        pass
    m = re.search(r"\{.*\}", text, re.DOTALL)
    if m:
        try:
            return json.loads(m.group(0))
        except json.JSONDecodeError:
            pass
    return None


def wilson(k: int, n: int) -> Tuple[float, float]:
    if n == 0:
        return (0.0, 1.0)
    z = 1.96
    p = k / n
    denom = 1 + z**2 / n
    center = (p + z**2 / (2 * n)) / denom
    margin = z * sqrt(p * (1 - p) / n + z**2 / (4 * n**2)) / denom
    return (max(0.0, center - margin), min(1.0, center + margin))


def posterior_best_arm(n_arms: int, observations: List[Dict[str, int]]) -> Tuple[int, List[float]]:
    solver = BanditSolver(n_arms=n_arms)
    for obs in observations:
        solver.update(obs["arm"] - 1, obs["reward"])
    means = [float(x) for x in solver.get_posterior_means()]
    return int(solver.recommend()) + 1, means


def make_sample(i: int, rng: random.Random, min_history: int, max_history: int) -> Dict[str, Any]:
    for _ in range(200):
        n_arms = [2, 3, 4, 5][i % 4]
        probs = [rng.uniform(0.15, 0.85) for _ in range(n_arms)]
        history_len = rng.randint(min_history, max_history)
        observations: List[Dict[str, int]] = []

        # Pull each arm once first, then sample the remaining history.
        arm_order = list(range(1, n_arms + 1))
        rng.shuffle(arm_order)
        for arm in arm_order[: min(n_arms, history_len)]:
            reward = 1 if rng.random() < probs[arm - 1] else 0
            observations.append({"arm": arm, "reward": reward})
        while len(observations) < history_len:
            arm = rng.randint(1, n_arms)
            reward = 1 if rng.random() < probs[arm - 1] else 0
            observations.append({"arm": arm, "reward": reward})

        gold, means = posterior_best_arm(n_arms, observations)
        # Avoid exact posterior-mean ties, because tie-breaking is not the point.
        rounded = [round(x, 8) for x in means]
        if rounded.count(max(rounded)) == 1:
            break

    lines = [
        f"There are {n_arms} slot machines. Each play returns only textual feedback.",
        "Use the history below to choose the machine with the highest posterior mean reward rate.",
        "History:",
    ]
    for j, obs in enumerate(observations, start=1):
        feedback = "won a token" if obs["reward"] else "lost"
        phrasing = rng.choice([
            f"Round {j}: played Slot Machine {obs['arm']}; feedback: {feedback}.",
            f"Pull {j}: played Slot Machine {obs['arm']}; feedback: {feedback}.",
            f"Trial {j}: played Slot Machine {obs['arm']}; feedback: {feedback}.",
        ])
        lines.append(phrasing)
    lines.append("Question: Which slot machine should be played next?")

    return {
        "id": i,
        "n_arms": n_arms,
        "true_reward_probs_hidden": probs,
        "observations": observations,
        "gold_arm": gold,
        "gold_posterior_means": means,
        "text": "\n".join(lines),
    }


def build_samples(n: int, seed: int, min_history: int, max_history: int) -> List[Dict[str, Any]]:
    rng = random.Random(seed)
    return [make_sample(i, rng, min_history, max_history) for i in range(n)]


async def call_llm(client: AsyncOpenAI, model: str, prompt: str, sem: asyncio.Semaphore) -> Tuple[bool, str, Dict[str, Any]]:
    async with sem:
        try:
            resp = await client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.0,
                max_tokens=2048,
            )
            usage = accumulate_usage(resp.usage)
            usage["cost_usd"] = float(getattr(resp.usage, "cost", 0) or 0)
            return True, resp.choices[0].message.content or "", usage
        except Exception as e:
            return False, f"API error: {e}", {"prompt_tokens": 0, "completion_tokens": 0, "cost_usd": 0.0}


def normalize_observations(raw: Any) -> List[Dict[str, int]]:
    observations: List[Dict[str, int]] = []
    if not isinstance(raw, list):
        return observations
    for obs in raw:
        try:
            arm = int(obs.get("arm"))
            reward_raw = obs.get("reward")
            if isinstance(reward_raw, str):
                reward = 1 if reward_raw.strip().lower() in {"1", "won", "win", "success", "true"} else 0
            else:
                reward = int(reward_raw)
            observations.append({"arm": arm, "reward": 1 if reward else 0})
        except Exception:
            continue
    return observations


def run_pipeline(parsed: Dict[str, Any], sample: Dict[str, Any]) -> Dict[str, Any]:
    spec_obj = parsed.get("task_spec", parsed)
    observations = normalize_observations(parsed.get("observations", []))
    try:
        spec = TaskSpec.from_dict(spec_obj)
        errors = spec.validate()
        if errors:
            return {"success": False, "failure_mode": "spec_validate", "error": errors[0]}
        solver = compile_solver(spec)
    except Exception as e:
        return {"success": False, "failure_mode": "spec_compile", "error": str(e)[:240]}

    if len(observations) != len(sample["observations"]):
        return {
            "success": False,
            "failure_mode": "observation_count",
            "error": f"{len(observations)} vs {len(sample['observations'])}",
            "parsed_observations": observations,
        }

    obs_ok = observations == sample["observations"]
    try:
        for obs in observations:
            solver.update(obs["arm"] - 1, obs["reward"])
        pred = int(solver.recommend()) + 1
    except Exception as e:
        return {"success": False, "failure_mode": "solve", "error": str(e)[:240], "parsed_observations": observations}

    return {
        "success": True,
        "spec_family": spec.inference_family,
        "n_arms": spec.state_structure.n_arms,
        "observations_exact": obs_ok,
        "parsed_observations": observations,
        "pred_arm": pred,
        "gold_arm": sample["gold_arm"],
        "e2e_correct": pred == sample["gold_arm"],
        "posterior_means": [float(x) for x in solver.get_posterior_means()],
    }


async def main() -> None:
    parser = argparse.ArgumentParser(description="TextBandit-style NL E2E")
    parser.add_argument("--model", default="openai/gpt-4o-mini")
    parser.add_argument("--n", type=int, default=50)
    parser.add_argument("--concurrency", "-c", type=int, default=10)
    parser.add_argument("--seed", type=int, default=20260502)
    parser.add_argument("--min-history", type=int, default=8)
    parser.add_argument("--max-history", type=int, default=14)
    args = parser.parse_args()

    samples = build_samples(args.n, args.seed, args.min_history, args.max_history)
    client = get_client()
    sem = asyncio.Semaphore(args.concurrency)
    prompts = [PROMPT.replace("{sample}", s["text"]) for s in samples]

    print(f"=== TextBandit NL E2E | n={len(samples)} | model={args.model} | sema={args.concurrency} ===")
    t0 = time.time()
    responses = await asyncio.gather(*[call_llm(client, args.model, p, sem) for p in prompts])
    elapsed = time.time() - t0

    results = []
    for sample, (ok, text, usage) in zip(samples, responses):
        if not ok:
            result = {"success": False, "failure_mode": "api_error", "error": text[:240]}
        else:
            parsed = extract_json(text)
            if parsed is None:
                result = {"success": False, "failure_mode": "json_parse", "error": text[:500]}
            else:
                result = run_pipeline(parsed, sample)
        result.update({
            "id": sample["id"],
            "n_arms_gold": sample["n_arms"],
            "gold_arm": sample["gold_arm"],
            "gold_observations": sample["observations"],
            "gold_posterior_means": sample["gold_posterior_means"],
            "sample_text": sample["text"],
            "usage": usage,
        })
        if len(samples) <= 3:
            result["raw_response"] = text
        results.append(result)

    successes = [r for r in results if r.get("success")]
    correct = sum(int(r.get("e2e_correct", False)) for r in successes)
    obs_exact = sum(int(r.get("observations_exact", False)) for r in successes)
    total = len(results)
    lo, hi = wilson(correct, total)
    parse_success = len(successes) / total if total else 0

    failure_modes: Dict[str, int] = {}
    for r in results:
        if not r.get("success"):
            key = r.get("failure_mode", "unknown")
            failure_modes[key] = failure_modes.get(key, 0) + 1
        elif not r.get("e2e_correct"):
            failure_modes["wrong_answer"] = failure_modes.get("wrong_answer", 0) + 1

    print(f"Elapsed: {elapsed:.1f}s")
    print(f"Parse/compile success: {len(successes)}/{total} = {parse_success*100:.1f}%")
    print(f"Observation exact: {obs_exact}/{len(successes) if successes else 0}")
    print(f"E2E accuracy: {correct}/{total} = {correct/total*100:.1f}% [{lo*100:.1f}, {hi*100:.1f}]")
    print("Failure modes:", failure_modes if failure_modes else "none")

    if len(samples) <= 3:
        print("\n--- Raw smoke outputs ---")
        for r in results:
            print(f"\n[id={r['id']}] sample:\n{r['sample_text']}")
            print(f"raw_response:\n{r.get('raw_response', '')}")
            print(f"parsed_result: {json.dumps({k: r.get(k) for k in ['success','spec_family','n_arms','observations_exact','pred_arm','gold_arm','e2e_correct','failure_mode','error']}, ensure_ascii=False)}")

    prompt_tokens = sum(r["usage"]["prompt_tokens"] for r in results)
    completion_tokens = sum(r["usage"]["completion_tokens"] for r in results)
    total_cost_usd = sum(r["usage"].get("cost_usd", 0.0) for r in results)

    out = {
        "experiment": "textbandit_nl_e2e",
        "model": args.model,
        "n_samples": total,
        "concurrency": args.concurrency,
        "seed": args.seed,
        "history_range": [args.min_history, args.max_history],
        "elapsed_sec": elapsed,
        "parse_success_rate": parse_success,
        "observation_exact_rate": obs_exact / len(successes) if successes else 0,
        "e2e_correct": correct,
        "e2e_accuracy": correct / total if total else 0,
        "e2e_wilson95": list(wilson(correct, total)),
        "failure_modes": failure_modes,
        "results": results,
        "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }

    RESULTS_DIR.mkdir(exist_ok=True)
    model_tag = args.model.replace("/", "_")
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_path = RESULTS_DIR / f"textbandit_e2e_{model_tag}_{ts}.json"
    save_artifact(
        str(out_path),
        out,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        total_cost_usd=total_cost_usd if total_cost_usd > 0 else None,
        model_id=args.model,
        extra_meta={
            "script": "baselines/run_textbandit_e2e.py",
            "n_samples": total,
            "concurrency": args.concurrency,
        },
    )
    print(f"Saved: {out_path}")


if __name__ == "__main__":
    asyncio.run(main())
