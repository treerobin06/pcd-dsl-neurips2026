#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
实验: Inductor 可靠性测试

对每个 task family 运行 inductor N 次（temperature>0），
统计成功率、平均轮次、amortized cost。

解决审查问题 C3: "Inductor 可靠性完全未量化"
"""

import sys
import os
import json
import csv
import time
import argparse
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "phase1"))

from inductor.refiner import induce_and_verify
from solvers.preference_solver import PreferenceSolver
from solvers.bn_solver import BNReferenceSolver
from taskspec.compiler import compile_solver

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


def load_flight_samples(n=5):
    """加载 Flight 偏好学习样本"""
    path = os.path.join(DATA_DIR, "flight.jsonl")
    with open(path, encoding="utf-8") as f:
        samples = [json.loads(line) for line in f]
    return samples[:n]


def load_bn_samples(n=5):
    """加载 BLInD BN 推断样本（depth=2）"""
    with open(BLIND_DATA, encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    shallow = [r for r in rows if int(r["depth"]) == 2]
    return shallow[:n]


def load_hotel_samples(n=5):
    """加载 Hotel 偏好学习样本"""
    path = os.path.join(DATA_DIR, "hotel.jsonl")
    if not os.path.exists(path):
        return None
    with open(path, encoding="utf-8") as f:
        samples = [json.loads(line) for line in f]
    return samples[:n]


def get_gold_solver(family):
    """获取对应 family 的 gold solver"""
    if family == "flight":
        return PreferenceSolver(
            feature_dim=4,
            preference_values=[-1.0, -0.5, 0.0, 0.5, 1.0],
        )
    elif family == "hotel":
        return PreferenceSolver(
            feature_dim=4,
            preference_values=[-1.0, -0.5, 0.0, 0.5, 1.0],
        )
    elif family == "bn":
        return BNReferenceSolver()
    return None


def run_single_trial(family, samples, gold_solver, model_id, max_rounds=3, max_samples=5, temperature=0.7):
    """运行单次 inductor trial"""
    start = time.time()

    # 注意：induce_and_verify 内部调用 induce_taskspec，
    # 我们需要通过猴子补丁或直接修改来传入 temperature
    # 由于 refiner 不支持 temperature 参数，我们直接用 inductor
    from inductor.inductor import induce_taskspec
    from verifier.gates import verify_taskspec

    diagnostics = ""
    spec = None
    result = None

    for round_idx in range(max_rounds):
        if round_idx == 0:
            spec = induce_taskspec(
                samples, model_id=model_id,
                max_samples=max_samples,
                temperature=temperature,
            )
        else:
            from inductor.inductor import induce_with_refinement
            spec = induce_with_refinement(
                samples, diagnostics=diagnostics,
                model_id=model_id, max_samples=max_samples,
                temperature=temperature,
            )

        if spec is None:
            diagnostics = "TaskSpec JSON 解析失败"
            continue

        result = verify_taskspec(spec, samples, gold_solver)

        if result.passed:
            elapsed = time.time() - start
            return {
                "success": True,
                "rounds": round_idx + 1,
                "elapsed": elapsed,
                "family": spec.inference_family if spec else None,
            }

        diagnostics = result.diagnostics()

    elapsed = time.time() - start
    return {
        "success": False,
        "rounds": max_rounds,
        "elapsed": elapsed,
        "family": spec.inference_family if spec else None,
        "diagnostics": diagnostics,
    }


def run_reliability_test(family, n_trials, model_id, max_samples=5, temperature=0.7):
    """对单个 family 运行 N 次 inductor"""
    print(f"\n{'='*60}")
    print(f"Inductor 可靠性测试: {family}")
    print(f"模型: {model_id}, 试次: {n_trials}, temperature: {temperature}")
    print(f"{'='*60}")

    # 加载数据
    if family == "flight":
        samples = load_flight_samples(max_samples)
    elif family == "hotel":
        samples = load_hotel_samples(max_samples)
        if samples is None:
            print("  [跳过] Hotel 数据不存在")
            return None
    elif family == "bn":
        samples = load_bn_samples(max_samples)
    else:
        print(f"  [跳过] 未知 family: {family}")
        return None

    gold = get_gold_solver(family)
    results = []

    for i in range(n_trials):
        print(f"\n  Trial {i+1}/{n_trials}...")
        trial = run_single_trial(
            family, samples, gold, model_id,
            max_rounds=3, max_samples=max_samples,
            temperature=temperature,
        )
        results.append(trial)
        status = "PASS" if trial["success"] else "FAIL"
        print(f"    {status} (轮次: {trial['rounds']}, 耗时: {trial['elapsed']:.1f}s)")

    # 统计
    successes = sum(1 for r in results if r["success"])
    success_rate = successes / n_trials
    avg_rounds = sum(r["rounds"] for r in results if r["success"]) / max(successes, 1)
    avg_elapsed = sum(r["elapsed"] for r in results) / n_trials

    summary = {
        "family": family,
        "model": model_id,
        "n_trials": n_trials,
        "temperature": temperature,
        "successes": successes,
        "success_rate": success_rate,
        "avg_rounds_on_success": round(avg_rounds, 2),
        "avg_elapsed_s": round(avg_elapsed, 1),
        "trials": results,
    }

    print(f"\n  {'='*40}")
    print(f"  成功率: {successes}/{n_trials} ({success_rate*100:.0f}%)")
    print(f"  成功时平均轮次: {avg_rounds:.2f}")
    print(f"  平均耗时: {avg_elapsed:.1f}s")

    return summary


def main():
    parser = argparse.ArgumentParser(description="Inductor 可靠性测试")
    parser.add_argument("--families", nargs="+", default=["flight", "bn"],
                        help="测试的 family 列表")
    parser.add_argument("--n-trials", type=int, default=20,
                        help="每个 family 的试次数")
    parser.add_argument("--model", type=str, default="openai/gpt-4o-mini",
                        help="Inductor 使用的模型")
    parser.add_argument("--max-samples", type=int, default=5,
                        help="Inductor 使用的最大样本数")
    parser.add_argument("--temperature", type=float, default=0.7,
                        help="LLM 温度（>0 以引入随机性）")
    args = parser.parse_args()

    all_results = {}

    for family in args.families:
        result = run_reliability_test(
            family, args.n_trials, args.model,
            max_samples=args.max_samples,
            temperature=args.temperature,
        )
        if result:
            all_results[family] = result

    # 保存结果
    os.makedirs(RESULTS_DIR, exist_ok=True)
    model_tag = args.model.replace("/", "_")
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    out_path = os.path.join(RESULTS_DIR, f"inductor_reliability_{model_tag}_{timestamp}.json")

    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(all_results, f, indent=2, ensure_ascii=False)

    print(f"\n结果已保存: {out_path}")

    # 汇总
    print(f"\n{'='*60}")
    print("汇总")
    print(f"{'='*60}")
    for family, res in all_results.items():
        print(f"  {family}: {res['successes']}/{res['n_trials']} "
              f"({res['success_rate']*100:.0f}%), "
              f"avg rounds={res['avg_rounds_on_success']:.1f}")


if __name__ == "__main__":
    main()
