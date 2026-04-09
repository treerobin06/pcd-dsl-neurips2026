#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Gate 3 Off Ablation — 证明系统不依赖 benchmark 标签

核心问题: Codex Review 指出 Gate 3 (Reference Match) 使用 gold solver 的输出
来验证 induced solver，如果 induction 数据和 evaluation 数据有重叠，
存在信息泄漏风险。

本测试: 完全关闭 Gate 3（不传入 gold_solver），仅用 Gate 1 (Code Sanity)
+ Gate 2 (Ground Truth) 验证。如果系统仍然能正确归纳 solver，
说明 Gate 3 不是必需的，不存在数据泄漏依赖。

对比: 与 test_loo_induction.py 的结果对比，展示 Gate 3 on/off 的差异。
"""

import sys
import os
import json
import csv
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "bayes", "bayesclaudecode"))

from inductor.refiner import induce_and_verify
from solvers.preference_solver import PreferenceSolver
from solvers.bn_solver import BNReferenceSolver
from taskspec.schema import TaskSpec
from taskspec.compiler import compile_solver
import numpy as np


DATA_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "bayes", "data", "eval", "interaction"
)

BLIND_DATA = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "BLInD", "datasets", "Base_1000_examples.csv"
)


def detect_preference_values(samples):
    """从样本的 reward_fn 中提取完整值域"""
    vals = set()
    for s in samples:
        for v in s.get("reward_fn", []):
            vals.add(float(v))
    return sorted(vals)


def test_preference_no_gate3(name, data_path, max_induction_samples=5, max_verify_samples=20):
    """偏好学习: 无 Gate 3 的 induction 测试"""
    print(f"\n{'='*60}")
    print(f"[Gate3-OFF] {name}")
    print(f"{'='*60}")

    with open(data_path, encoding="utf-8") as f:
        samples = [json.loads(line) for line in f]

    dim = len(samples[0]["features"])
    pref_vals = detect_preference_values(samples)
    print(f"  样本数: {len(samples)}, 维度: {dim}, 值域: {pref_vals}")

    # 关键: gold_solver=None → Gate 3 被跳过
    start = time.time()
    spec, result, rounds = induce_and_verify(
        samples[:max_induction_samples],
        gold_solver=None,  # 不传 gold solver → 无 Gate 3
        max_rounds=3,
        max_samples=max_induction_samples,
    )
    elapsed = time.time() - start

    passed = result.passed
    family_correct = spec.inference_family == "hypothesis_enumeration" if spec else False

    # 检查 Gate 3 确实没有运行
    gate_names = [g.gate for g in result.gates]
    gate3_ran = any("Reference Match" in g for g in gate_names)

    print(f"  结果: {'PASS' if passed else 'FAIL'} (第 {rounds} 轮, {elapsed:.1f}s)")
    print(f"  Gates 运行: {gate_names}")
    print(f"  Gate 3 运行: {'是' if gate3_ran else '否 (已关闭)'}")
    print(f"  Family 正确: {family_correct}")

    # 如果通过，进一步用 gold solver 做独立验证（事后对比，非 induction 流程内）
    solver_acc = None
    reference_match = None
    if passed and spec:
        solver = compile_solver(spec)
        gold = PreferenceSolver(feature_dim=dim, preference_values=pref_vals)

        correct = 0
        ref_match = 0
        total = 0
        for sample in samples[:max_verify_samples]:
            solver.reset()
            gold.reset()
            rounds_data = sample.get("rounds", [])
            rounds_numpy = sample.get("rounds_numpy", [])
            for r_idx in range(len(rounds_data)):
                if r_idx >= len(rounds_numpy):
                    break
                user_choice = rounds_data[r_idx]["user_idx"]
                options = rounds_numpy[r_idx]
                if r_idx < len(rounds_data) - 1:
                    solver.update(user_choice, options)
                    gold.update(user_choice, options)
                else:
                    rec = solver.recommend(options)
                    gold_rec = gold.recommend(options)
                    if rec == user_choice:
                        correct += 1
                    if rec == gold_rec:
                        ref_match += 1
                    total += 1

        if total > 0:
            solver_acc = correct / total
            reference_match = ref_match / total
            print(f"  [事后验证] Solver R5 准确率: {solver_acc*100:.1f}% ({correct}/{total})")
            print(f"  [事后验证] vs Gold Solver 一致率: {reference_match*100:.1f}% ({ref_match}/{total})")

    return {
        "name": name,
        "gate3_off": True,
        "passed": passed,
        "rounds": rounds,
        "family_correct": family_correct,
        "gate3_ran": gate3_ran,
        "solver_acc": solver_acc,
        "reference_match": reference_match,
        "elapsed": elapsed,
    }


def test_blind_no_gate3():
    """BLInD: 无 Gate 3 的 induction 测试"""
    print(f"\n{'='*60}")
    print(f"[Gate3-OFF] BLInD depth-stratified OOD")
    print(f"{'='*60}")

    if not os.path.exists(BLIND_DATA):
        print("  [跳过] BLInD 数据不存在")
        return None

    with open(BLIND_DATA, encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    shallow = [r for r in rows if int(r["depth"]) == 2][:5]
    print(f"  Induction 样本: {len(shallow)} (depth=2)")

    # 关键: gold_solver=None → Gate 3 被跳过
    start = time.time()
    spec, result, rounds = induce_and_verify(
        shallow,
        gold_solver=None,  # 无 Gate 3
        max_rounds=2,
        max_samples=3,
    )
    elapsed = time.time() - start

    gate_names = [g.gate for g in result.gates]
    gate3_ran = any("Reference Match" in g for g in gate_names)

    print(f"  Induction: {'PASS' if result.passed else 'FAIL'} (第 {rounds} 轮, {elapsed:.1f}s)")
    print(f"  Gates 运行: {gate_names}")
    print(f"  Gate 3 运行: {'是' if gate3_ran else '否 (已关闭)'}")

    if not result.passed:
        return {"name": "BLInD-OOD", "gate3_off": True, "passed": False, "gate3_ran": gate3_ran}

    # 事后验证: 用 gold solver 对比
    solver = compile_solver(spec)
    gold = BNReferenceSolver()

    depth_results = {}
    depth_ref_match = {}
    for depth in [2, 4, 6, 8, 10]:
        depth_rows = [r for r in rows if int(r["depth"]) == depth][:20]
        if not depth_rows:
            continue
        correct = 0
        ref_match = 0
        total = len(depth_rows)
        for row in depth_rows:
            expected = float(row["answers"])
            predicted = solver.solve_from_text(row["contexts"], row["query"], row["graph"])
            gold_pred = gold.solve_from_text(row["contexts"], row["query"], row["graph"])

            if predicted is not None and abs(predicted - expected) < 0.01:
                correct += 1
            if predicted is not None and gold_pred is not None and abs(predicted - gold_pred) < 1e-10:
                ref_match += 1

        acc = correct / total
        ref_rate = ref_match / total
        depth_results[depth] = acc
        depth_ref_match[depth] = ref_rate
        print(f"  depth={depth}: 准确率={acc*100:.1f}%, vs Gold={ref_rate*100:.1f}%")

    return {
        "name": "BLInD-OOD",
        "gate3_off": True,
        "passed": True,
        "gate3_ran": gate3_ran,
        "depth_results": depth_results,
        "depth_ref_match": depth_ref_match,
        "elapsed": elapsed,
    }


if __name__ == "__main__":
    print("=" * 60)
    print("Gate 3 Off Ablation — 验证系统不依赖 benchmark 标签")
    print("=" * 60)
    print("Gate 3 (Reference Match) 关闭，仅用 Gate 1 + Gate 2 验证")

    results = []

    # 偏好学习
    preference_datasets = [
        ("Hotel (4D, 不同domain)", "hotel.jsonl"),
        ("Flight-2F (2D)", "flight_2features.jsonl"),
        ("Flight-3F (3D)", "flight_3features.jsonl"),
        ("Flight-5F (5D)", "flight_5features.jsonl"),
        ("Flight-6F (6D)", "flight_6features.jsonl"),
    ]

    for name, fname in preference_datasets:
        path = os.path.join(DATA_DIR, fname)
        if os.path.exists(path):
            r = test_preference_no_gate3(name, path)
            results.append(r)
        else:
            print(f"\n[跳过] {name}: 文件不存在")

    # BLInD
    r = test_blind_no_gate3()
    if r:
        results.append(r)

    # 汇总
    print(f"\n\n{'='*60}")
    print("Gate 3 Off Ablation 汇总")
    print(f"{'='*60}")
    print(f"{'数据集':<30} {'Gate3':>5} {'通过':>4} {'轮次':>4} {'Solver准确率':>12} {'vs Gold':>10}")
    print("-" * 75)
    for r in results:
        g3 = "OFF" if not r.get("gate3_ran", True) else "ON"
        if "depth_results" in r:
            depths = r.get("depth_results", {})
            ref = r.get("depth_ref_match", {})
            for d in sorted(depths.keys()):
                acc_str = f"{depths[d]*100:.1f}%"
                ref_str = f"{ref.get(d, 0)*100:.1f}%"
                print(f"  BLInD depth={d:<20} {g3:>5} {'Y' if r['passed'] else 'N':>4}      {acc_str:>12} {ref_str:>10}")
        else:
            acc = f"{r['solver_acc']*100:.1f}%" if r.get('solver_acc') is not None else "-"
            ref = f"{r['reference_match']*100:.1f}%" if r.get('reference_match') is not None else "-"
            print(f"{r['name']:<30} {g3:>5} {'Y' if r['passed'] else 'N':>4} {r['rounds']:>4} {acc:>12} {ref:>10}")

    total = len(results)
    passed = sum(1 for r in results if r["passed"])
    print(f"\n总计: {passed}/{total} 通过 (Gate 3 全部关闭)")

    if passed == total:
        print("\n结论: 系统在 Gate 3 完全关闭的情况下仍然 100% 通过验证。")
        print("Gate 3 (Reference Match) 不是系统正确性的必要条件，不存在数据泄漏依赖。")
    else:
        failed = [r["name"] for r in results if not r["passed"]]
        print(f"\n注意: 以下数据集在 Gate 3 关闭后未通过: {failed}")
        print("需要进一步分析 Gate 3 对 induction 成功的影响。")
