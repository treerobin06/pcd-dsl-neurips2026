#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Leave-One-Out 泛化验证

在 Inductor **从未见过** 的数据集上测试完整流程：
  samples → Inductor → TaskSpec → Compiler → Solver → Verifier

测试数据集:
- Hotel (4 features, 不同 domain)
- Flight 2/3/5/6/7/8-feature (不同维度)

验证的核心问题:
1. Inductor 能否正确识别 inference family？
2. 能否正确提取特征名和值域？
3. 编译出的 solver 能否正确推断？
"""

import sys
import os
import json
import csv
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "phase1"))

from inductor.refiner import induce_and_verify
from solvers.preference_solver import PreferenceSolver
from solvers.bn_solver import BNReferenceSolver
from taskspec.schema import TaskSpec
from taskspec.compiler import compile_solver
import numpy as np


DATA_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "data", "eval", "interaction"
)

BLIND_DATA = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "data", "external", "BLInD", "datasets", "Base_1000_examples.csv"
)


def detect_preference_values(samples):
    """从样本的 reward_fn 中提取完整值域"""
    vals = set()
    for s in samples:
        for v in s.get("reward_fn", []):
            vals.add(float(v))
    return sorted(vals)


def test_one_dataset(name, data_path, max_induction_samples=5, max_verify_samples=20):
    """测试单个数据集的 induction 流程"""
    print(f"\n{'='*60}")
    print(f"测试: {name}")
    print(f"{'='*60}")

    with open(data_path, encoding="utf-8") as f:
        samples = [json.loads(line) for line in f]

    print(f"  样本数: {len(samples)}")
    print(f"  features: {samples[0].get('features', '?')}")

    # 构造 gold solver
    pref_vals = detect_preference_values(samples)
    dim = len(samples[0]["features"])
    gold = PreferenceSolver(
        feature_dim=dim,
        preference_values=pref_vals,
    )
    print(f"  维度: {dim}, 值域: {pref_vals}")

    # C6 修复 (2026-04-24): 显式 disjoint train/test split
    induct_samples = samples[:max_induction_samples]
    verify_samples = samples[max_induction_samples:max_induction_samples + max_verify_samples]
    # 强制 disjoint check（按对象 id 而非内容相等）
    induct_ids = {id(s) for s in induct_samples}
    verify_ids = {id(s) for s in verify_samples}
    assert not (induct_ids & verify_ids), \
        f"C6 violation: induct/verify must be disjoint, overlap={len(induct_ids & verify_ids)}"
    if len(verify_samples) == 0:
        raise ValueError(f"Dataset {name} has only {len(samples)} samples; need >={max_induction_samples + 1} for disjoint LOO split")
    print(f"  Disjoint split: induct={len(induct_samples)}, verify={len(verify_samples)}")

    # 运行 Inductor
    start = time.time()
    spec, result, rounds = induce_and_verify(
        induct_samples,
        gold_solver=gold,
        max_rounds=3,
        max_samples=max_induction_samples,
        verify_samples=verify_samples,
    )
    elapsed = time.time() - start

    # 分析结果
    passed = result.passed
    family_correct = spec.inference_family == "hypothesis_enumeration" if spec else False
    features_correct = False
    values_correct = False

    if spec:
        expected_features = samples[0]["features"]
        actual_features = spec.state_structure.features
        features_correct = set(actual_features) == set(expected_features)

        actual_values = spec.state_structure.values_per_feature
        values_correct = set(actual_values) == set(pref_vals)

    print(f"\n  结果: {'PASS' if passed else 'FAIL'} (第 {rounds} 轮, {elapsed:.1f}s)")
    print(f"  Family 正确: {family_correct}")
    print(f"  Features 正确: {features_correct}")
    if spec:
        print(f"    期望: {samples[0]['features']}")
        print(f"    实际: {spec.state_structure.features}")
    print(f"  Values 正确: {values_correct}")
    if spec:
        print(f"    期望: {pref_vals}")
        print(f"    实际: {spec.state_structure.values_per_feature}")

    # 如果 spec 正确，进一步验证 solver 准确率
    solver_acc = None
    if passed and spec:
        solver = compile_solver(spec)
        correct = 0
        total = 0
        for sample in samples[:max_verify_samples]:
            solver.reset()
            rounds_data = sample.get("rounds", [])
            rounds_numpy = sample.get("rounds_numpy", [])
            for r_idx in range(len(rounds_data)):
                if r_idx >= len(rounds_numpy):
                    break
                user_choice = rounds_data[r_idx]["user_idx"]
                options = rounds_numpy[r_idx]
                if r_idx < len(rounds_data) - 1:
                    solver.update(user_choice, options)
                else:
                    rec = solver.recommend(options)
                    if rec == user_choice:
                        correct += 1
                    total += 1
        if total > 0:
            solver_acc = correct / total
            print(f"  Solver R5 准确率: {solver_acc*100:.1f}% ({correct}/{total})")

    return {
        "name": name,
        "passed": passed,
        "rounds": rounds,
        "family_correct": family_correct,
        "features_correct": features_correct,
        "values_correct": values_correct,
        "solver_acc": solver_acc,
        "elapsed": elapsed,
    }


def test_blind_depth_ood():
    """BLInD 不同 depth 的 OOD 测试"""
    print(f"\n{'='*60}")
    print(f"测试: BLInD depth-stratified OOD")
    print(f"{'='*60}")

    if not os.path.exists(BLIND_DATA):
        print("  [跳过] BLInD 数据不存在")
        return None

    with open(BLIND_DATA, encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    # 用 depth=2 的样本做 induction，在 depth=4,6,8 上验证
    shallow = [r for r in rows if int(r["depth"]) == 2][:5]
    # C6 修复 (2026-04-24): induction 内部 verify 也用 disjoint shallow 子集
    # （depth=2 后续 5 个样本，与 induction 集 disjoint）
    shallow_verify = [r for r in rows if int(r["depth"]) == 2][5:10]
    induct_ids = {id(s) for s in shallow}
    verify_ids = {id(s) for s in shallow_verify}
    assert not (induct_ids & verify_ids), "C6 violation: BLInD-OOD induct/verify overlap"
    gold = BNReferenceSolver()

    print(f"  Induction 样本: {len(shallow)} (depth=2), Disjoint verify: {len(shallow_verify)}")

    spec, result, rounds = induce_and_verify(
        shallow, gold_solver=gold, max_rounds=2, max_samples=3,
        verify_samples=shallow_verify,
    )

    print(f"  Induction: {'PASS' if result.passed else 'FAIL'} (第 {rounds} 轮)")

    if not result.passed:
        return {"name": "BLInD-OOD", "passed": False}

    # 在不同 depth 上验证
    solver = compile_solver(spec)
    depth_results = {}
    for depth in [2, 4, 6, 8, 10]:
        depth_rows = [r for r in rows if int(r["depth"]) == depth][:20]
        if not depth_rows:
            continue
        correct = 0
        total = len(depth_rows)
        for row in depth_rows:
            expected = float(row["answers"])
            predicted = solver.solve_from_text(row["contexts"], row["query"], row["graph"])
            if predicted is not None and abs(predicted - expected) < 0.01:
                correct += 1
        acc = correct / total
        depth_results[depth] = acc
        print(f"  depth={depth}: {acc*100:.1f}% ({correct}/{total})")

    return {"name": "BLInD-OOD", "passed": True, "depth_results": depth_results}


if __name__ == "__main__":
    print("=" * 60)
    print("Leave-One-Out 泛化验证")
    print("=" * 60)

    results = []

    # 偏好学习 family: 不同 domain 和维度
    preference_datasets = [
        ("Hotel (4D, 不同domain)", "hotel.jsonl"),
        ("Flight-2F (2D)", "flight_2features.jsonl"),
        ("Flight-3F (3D)", "flight_3features.jsonl"),
        ("Flight-5F (5D, 新特征bags)", "flight_5features.jsonl"),
        ("Flight-6F (6D)", "flight_6features.jsonl"),
    ]

    for name, fname in preference_datasets:
        path = os.path.join(DATA_DIR, fname)
        if os.path.exists(path):
            r = test_one_dataset(name, path)
            results.append(r)
        else:
            print(f"\n[跳过] {name}: 文件不存在")

    # BLInD depth OOD
    r = test_blind_depth_ood()
    if r:
        results.append(r)

    # 汇总
    print(f"\n\n{'='*60}")
    print("LOO 泛化验证汇总")
    print(f"{'='*60}")
    print(f"{'数据集':<30} {'通过':>4} {'轮次':>4} {'Family':>7} {'Features':>8} {'Values':>7} {'Solver':>7}")
    print("-" * 75)
    for r in results:
        if "depth_results" in r:
            # BLInD
            depths = r.get("depth_results", {})
            depth_str = " | ".join(f"d{d}={a*100:.0f}%" for d, a in sorted(depths.items()))
            print(f"{'BLInD-OOD':<30} {'Y' if r['passed'] else 'N':>4}    {depth_str}")
        else:
            acc = f"{r['solver_acc']*100:.0f}%" if r.get('solver_acc') is not None else "-"
            print(
                f"{r['name']:<30} "
                f"{'Y' if r['passed'] else 'N':>4} "
                f"{r['rounds']:>4} "
                f"{'Y' if r['family_correct'] else 'N':>7} "
                f"{'Y' if r['features_correct'] else 'N':>8} "
                f"{'Y' if r['values_correct'] else 'N':>7} "
                f"{acc:>7}"
            )

    total = len(results)
    passed = sum(1 for r in results if r["passed"])
    print(f"\n总计: {passed}/{total} 通过")
