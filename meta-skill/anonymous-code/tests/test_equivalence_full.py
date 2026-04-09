#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
全量等价性验证：DSL Solver vs 原始 Solver

在真实数据集上验证:
1. BNReferenceSolver vs BNSolver — 900 个 BLInD 样本
2. PreferenceSolver vs BayesianSidecar — flight 数据集前 50 个样本
"""

import sys
import os
import csv
import json
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "bayes", "bayesclaudecode"))

from solvers.bn_solver import BNReferenceSolver
from solvers.preference_solver import PreferenceSolver


def test_bn_full():
    """BLInD 900 题全量验证"""
    data_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
        "BLInD", "datasets", "Base_1000_examples.csv"
    )
    if not os.path.exists(data_path):
        print(f"[跳过] BLInD 数据不存在: {data_path}")
        return

    from bn_solver import solve_blind_example

    with open(data_path, encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    new_solver = BNReferenceSolver()
    match_count = 0
    total = len(rows)

    for i, row in enumerate(rows):
        old_result = solve_blind_example(row["contexts"], row["query"], row["graph"])
        new_result = new_solver.solve_from_text(row["contexts"], row["query"], row["graph"])

        if old_result is not None and new_result is not None:
            if abs(old_result - new_result) < 1e-10:
                match_count += 1
            else:
                print(f"  [不一致] 样本 {i}: old={old_result:.6f}, new={new_result:.6f}")

    print(f"BLInD 等价性: {match_count}/{total} ({match_count/total*100:.1f}%)")
    assert match_count == total, f"有 {total - match_count} 个样本不一致"


def test_preference_full():
    """Flight 数据集前 50 样本全量验证"""
    data_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
        "bayes", "data", "eval", "interaction", "flight.jsonl"
    )
    if not os.path.exists(data_path):
        print(f"[跳过] Flight 数据不存在: {data_path}")
        return

    from bayesian_sidecar import BayesianSidecar

    with open(data_path, encoding="utf-8") as f:
        samples = [json.loads(line) for line in f][:50]

    match_count = 0
    total = 0

    for sample in samples:
        pref_vals = sorted(set(float(v) for v in sample["reward_fn"]))
        pref_vals = [-1.0, -0.5, 0.0, 0.5, 1.0]  # flight 数据集完整值域
        dim = len(sample["features"])

        old = BayesianSidecar(feature_dim=dim, preference_values=pref_vals)
        new = PreferenceSolver(feature_dim=dim, preference_values=pref_vals)

        for r_idx, (round_data, round_numpy) in enumerate(
            zip(sample["rounds"], sample["rounds_numpy"])
        ):
            user_choice = round_data["user_idx"]
            options = round_numpy

            old.update(user_choice, options)
            new.update(user_choice, options)

            # 验证后验完全一致
            max_diff = np.max(np.abs(old.posterior - new.posterior.probs))
            if max_diff > 1e-10:
                print(f"  [不一致] 样本 {sample['idx']} 轮 {r_idx}: max_diff={max_diff}")
            else:
                match_count += 1
            total += 1

            # 验证推荐一致
            old_rec = old.recommend(options)
            new_rec = new.recommend(options)
            assert old_rec == new_rec, f"推荐不一致: 样本 {sample['idx']} 轮 {r_idx}"

    print(f"Flight 等价性: {match_count}/{total} ({match_count/total*100:.1f}%)")
    assert match_count == total


if __name__ == "__main__":
    print("=" * 60)
    print("全量等价性验证")
    print("=" * 60)

    print("\n--- BLInD (BN 推断) ---")
    test_bn_full()

    print("\n--- Flight (偏好学习) ---")
    test_preference_full()

    print("\n全部通过!")
