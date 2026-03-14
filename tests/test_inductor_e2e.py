#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
端到端测试: Inductor → Compiler → Verifier

使用真实数据样本测试完整流程。
每个 inference family 各测一次。
"""

import sys
import os
import json
import csv
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "bayes", "bayesclaudecode"))

from inductor.refiner import induce_and_verify
from solvers.preference_solver import PreferenceSolver
from solvers.bandit_solver import BanditSolver
from solvers.bn_solver import BNReferenceSolver


def test_flight_induction():
    """Flight 偏好学习 — 完整 induction 流程"""
    data_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
        "bayes", "data", "eval", "interaction", "flight.jsonl"
    )
    if not os.path.exists(data_path):
        print(f"[跳过] 数据不存在: {data_path}")
        return

    with open(data_path, encoding="utf-8") as f:
        samples = [json.loads(line) for line in f][:10]

    gold = PreferenceSolver(
        feature_dim=4,
        preference_values=[-1.0, -0.5, 0.0, 0.5, 1.0],
    )

    print("\n=== Flight Induction ===")
    spec, result, rounds = induce_and_verify(
        samples, gold_solver=gold, max_rounds=3, max_samples=3,
    )

    print(f"\n结果: {'PASS' if result.passed else 'FAIL'} (用了 {rounds} 轮)")
    if spec:
        print(f"TaskSpec: {json.dumps(spec.to_dict(), indent=2)}")
    return result.passed


def test_blind_induction():
    """BLInD BN 推断 — 完整 induction 流程"""
    data_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
        "BLInD", "datasets", "Base_1000_examples.csv"
    )
    if not os.path.exists(data_path):
        print(f"[跳过] 数据不存在: {data_path}")
        return

    with open(data_path, encoding="utf-8") as f:
        rows = list(csv.DictReader(f))[:10]

    gold = BNReferenceSolver()

    print("\n=== BLInD Induction ===")
    spec, result, rounds = induce_and_verify(
        rows, gold_solver=gold, max_rounds=3, max_samples=3,
    )

    print(f"\n结果: {'PASS' if result.passed else 'FAIL'} (用了 {rounds} 轮)")
    if spec:
        print(f"TaskSpec: {json.dumps(spec.to_dict(), indent=2)}")
    return result.passed


if __name__ == "__main__":
    print("=" * 60)
    print("端到端 Inductor 测试")
    print("=" * 60)

    results = {}
    results["flight"] = test_flight_induction()
    results["blind"] = test_blind_induction()

    print("\n" + "=" * 60)
    print("汇总")
    print("=" * 60)
    for task, passed in results.items():
        status = "PASS" if passed else ("FAIL" if passed is not None else "SKIP")
        print(f"  {task}: {status}")
