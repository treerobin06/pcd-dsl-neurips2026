#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
实验: Induction Examples 数量消融

测试不同数量的 induction examples {1, 2, 3, 5, 10} 对 inductor 成功率的影响。
在 BN inference 和 Preference Learning 上各跑一次。

解决审查问题 M7a: "缺少 induction examples 数量 ablation"
"""

import sys
import os
import json
import csv
import time
import argparse

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "phase1"))

from inductor.inductor import induce_taskspec
from inductor.refiner import induce_and_verify
from solvers.preference_solver import PreferenceSolver
from solvers.bn_solver import BNReferenceSolver
from taskspec.compiler import compile_solver
from verifier.gates import verify_taskspec

# 数据路径
DATA_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "data", "eval", "interaction"
)
BLIND_DATA = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "BLInD", "datasets", "Base_1000_examples.csv"
)

RESULTS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "results")


def load_flight_samples():
    path = os.path.join(DATA_DIR, "flight.jsonl")
    with open(path, encoding="utf-8") as f:
        return [json.loads(line) for line in f]


def load_bn_samples():
    with open(BLIND_DATA, encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    return [r for r in rows if int(r["depth"]) == 2]


def test_one_k(family, all_samples, gold_solver, k, model_id, n_repeats=3):
    """测试 k 个 induction examples 的效果，重复 n_repeats 次"""
    results = []
    for repeat in range(n_repeats):
        samples = all_samples[:k]
        start = time.time()

        spec = induce_taskspec(
            samples, model_id=model_id,
            max_samples=k, temperature=0.0,
        )

        if spec is None:
            results.append({
                "success": False, "rounds": 1,
                "elapsed": time.time() - start,
                "reason": "parse_failed",
            })
            continue

        result = verify_taskspec(spec, samples, gold_solver)
        elapsed = time.time() - start

        results.append({
            "success": result.passed,
            "rounds": 1,
            "elapsed": elapsed,
            "family_detected": spec.inference_family,
            "reason": None if result.passed else result.diagnostics(),
        })

    successes = sum(1 for r in results if r["success"])
    return {
        "k": k,
        "n_repeats": n_repeats,
        "successes": successes,
        "success_rate": successes / n_repeats,
        "trials": results,
    }


def run_ablation(family, model_id, k_values, n_repeats=3):
    """在一个 family 上测试不同 k 值"""
    print(f"\n{'='*60}")
    print(f"Examples 数量消融: {family}")
    print(f"模型: {model_id}, k 值: {k_values}")
    print(f"{'='*60}")

    if family == "flight":
        all_samples = load_flight_samples()
        gold = PreferenceSolver(feature_dim=4, preference_values=[-1.0, -0.5, 0.0, 0.5, 1.0])
    elif family == "bn":
        all_samples = load_bn_samples()
        gold = BNReferenceSolver()
    else:
        print(f"  未知 family: {family}")
        return None

    results = {}
    for k in k_values:
        if k > len(all_samples):
            print(f"  k={k} 超过可用样本数 ({len(all_samples)})，跳过")
            continue
        print(f"\n  k={k}...")
        res = test_one_k(family, all_samples, gold, k, model_id, n_repeats)
        results[k] = res
        print(f"    成功率: {res['successes']}/{res['n_repeats']} ({res['success_rate']*100:.0f}%)")

    return {
        "family": family,
        "model": model_id,
        "k_values": k_values,
        "results": results,
    }


def main():
    parser = argparse.ArgumentParser(description="Induction Examples 数量消融")
    parser.add_argument("--families", nargs="+", default=["flight", "bn"])
    parser.add_argument("--k-values", nargs="+", type=int, default=[1, 2, 3, 5, 10])
    parser.add_argument("--model", type=str, default="openai/gpt-4o-mini")
    parser.add_argument("--n-repeats", type=int, default=3,
                        help="每个 k 值重复次数（temperature=0 时 1 次即可）")
    args = parser.parse_args()

    all_results = {}
    for family in args.families:
        res = run_ablation(family, args.model, args.k_values, args.n_repeats)
        if res:
            all_results[family] = res

    # 保存
    os.makedirs(RESULTS_DIR, exist_ok=True)
    model_tag = args.model.replace("/", "_")
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    out_path = os.path.join(RESULTS_DIR, f"examples_ablation_{model_tag}_{timestamp}.json")

    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(all_results, f, indent=2, ensure_ascii=False)

    print(f"\n结果已保存: {out_path}")

    # 汇总表
    print(f"\n{'='*60}")
    print("汇总")
    print(f"{'='*60}")
    for family, fam_res in all_results.items():
        print(f"\n  {family}:")
        print(f"  {'k':>4} | {'成功率':>8}")
        print(f"  {'----':>4}-+-{'--------':>8}")
        for k, res in fam_res["results"].items():
            print(f"  {k:>4} | {res['success_rate']*100:>6.0f}%")


if __name__ == "__main__":
    main()
