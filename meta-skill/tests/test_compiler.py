#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Compiler 测试

验证:
1. TaskSpec 验证器正确拒绝非法 spec
2. Compiler 从 gold TaskSpec 编译出正确类型的 solver
3. 编译出的 solver 与手写 gold solver 功能等价
"""

import sys
import os
import json
import unittest
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "phase1"))

from taskspec.schema import TaskSpec
from taskspec.compiler import compile_solver
from solvers.preference_solver import PreferenceSolver
from solvers.bandit_solver import BanditSolver
from solvers.bn_solver import BNReferenceSolver


EXAMPLES_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "taskspec", "examples"
)


class TestTaskSpecValidation(unittest.TestCase):
    """TaskSpec 验证测试"""

    def test_valid_flight(self):
        with open(os.path.join(EXAMPLES_DIR, "flight.json")) as f:
            spec = TaskSpec.from_dict(json.load(f))
        errors = spec.validate()
        self.assertEqual(errors, [])

    def test_valid_bandit(self):
        with open(os.path.join(EXAMPLES_DIR, "bandit.json")) as f:
            spec = TaskSpec.from_dict(json.load(f))
        errors = spec.validate()
        self.assertEqual(errors, [])

    def test_valid_blind(self):
        with open(os.path.join(EXAMPLES_DIR, "blind.json")) as f:
            spec = TaskSpec.from_dict(json.load(f))
        errors = spec.validate()
        self.assertEqual(errors, [])

    def test_invalid_family(self):
        spec = TaskSpec(
            task_name="test",
            inference_family="unknown",
            state_structure=TaskSpec.from_dict(json.load(open(os.path.join(EXAMPLES_DIR, "flight.json")))).state_structure,
            observation_model=TaskSpec.from_dict(json.load(open(os.path.join(EXAMPLES_DIR, "flight.json")))).observation_model,
            decision_rule=TaskSpec.from_dict(json.load(open(os.path.join(EXAMPLES_DIR, "flight.json")))).decision_rule,
            data_format=TaskSpec.from_dict(json.load(open(os.path.join(EXAMPLES_DIR, "flight.json")))).data_format,
        )
        errors = spec.validate()
        self.assertTrue(len(errors) > 0)

    def test_mismatched_family_and_state(self):
        """hypothesis_enumeration 但 state_structure.type = beta_conjugate → 报错"""
        with open(os.path.join(EXAMPLES_DIR, "flight.json")) as f:
            d = json.load(f)
        d["state_structure"]["type"] = "beta_conjugate"
        spec = TaskSpec.from_dict(d)
        errors = spec.validate()
        self.assertTrue(len(errors) > 0)


class TestCompilerOutput(unittest.TestCase):
    """Compiler 输出类型测试"""

    def test_flight_compiles_to_preference_solver(self):
        with open(os.path.join(EXAMPLES_DIR, "flight.json")) as f:
            spec = TaskSpec.from_dict(json.load(f))
        solver = compile_solver(spec)
        self.assertIsInstance(solver, PreferenceSolver)
        self.assertEqual(solver.feature_dim, 4)
        self.assertEqual(solver.preference_values, [-1.0, -0.5, 0.0, 0.5, 1.0])

    def test_bandit_compiles_to_bandit_solver(self):
        with open(os.path.join(EXAMPLES_DIR, "bandit.json")) as f:
            spec = TaskSpec.from_dict(json.load(f))
        solver = compile_solver(spec)
        self.assertIsInstance(solver, BanditSolver)
        self.assertEqual(solver.n_arms, 5)

    def test_blind_compiles_to_bn_solver(self):
        with open(os.path.join(EXAMPLES_DIR, "blind.json")) as f:
            spec = TaskSpec.from_dict(json.load(f))
        solver = compile_solver(spec)
        self.assertIsInstance(solver, BNReferenceSolver)

    def test_invalid_spec_raises(self):
        with open(os.path.join(EXAMPLES_DIR, "flight.json")) as f:
            d = json.load(f)
        d["state_structure"]["type"] = "beta_conjugate"
        spec = TaskSpec.from_dict(d)
        with self.assertRaises(ValueError):
            compile_solver(spec)


class TestCompilerEquivalence(unittest.TestCase):
    """Compiler 输出 solver 与手写 gold solver 等价性"""

    def test_preference_equivalence(self):
        """compiler(flight.json) 的 solver 与手写 PreferenceSolver 功能一致"""
        with open(os.path.join(EXAMPLES_DIR, "flight.json")) as f:
            spec = TaskSpec.from_dict(json.load(f))
        compiled = compile_solver(spec)
        manual = PreferenceSolver(
            feature_dim=4,
            preference_values=[-1.0, -0.5, 0.0, 0.5, 1.0],
            temperature=1.0,
        )

        rng = np.random.default_rng(42)
        for _ in range(5):
            options = rng.uniform(0, 1, (3, 4)).tolist()
            choice = rng.integers(3)
            compiled.update(choice, options)
            manual.update(choice, options)

            np.testing.assert_allclose(
                compiled.posterior.probs, manual.posterior.probs, atol=1e-10
            )
            self.assertEqual(compiled.recommend(options), manual.recommend(options))

    def test_bandit_equivalence(self):
        """compiler(bandit.json) 的 solver 与手写 BanditSolver 功能一致"""
        with open(os.path.join(EXAMPLES_DIR, "bandit.json")) as f:
            spec = TaskSpec.from_dict(json.load(f))
        compiled = compile_solver(spec)
        manual = BanditSolver(n_arms=5)

        rng = np.random.default_rng(42)
        for _ in range(20):
            arm = rng.integers(5)
            reward = rng.integers(2)
            compiled.update(arm, reward)
            manual.update(arm, reward)

            np.testing.assert_allclose(
                compiled.get_posterior_means(), manual.get_posterior_means(), atol=1e-10
            )
            self.assertEqual(compiled.recommend(), manual.recommend())

    def test_bn_equivalence(self):
        """compiler(blind.json) 的 solver 与手写 BNReferenceSolver 功能一致"""
        with open(os.path.join(EXAMPLES_DIR, "blind.json")) as f:
            spec = TaskSpec.from_dict(json.load(f))
        compiled = compile_solver(spec)
        manual = BNReferenceSolver()

        context = (
            "If n1 is True, then n0 is True with probability of 80%. "
            "If n1 is True, then n0 is False with probability of 20%. "
            "If n1 is False, then n0 is True with probability of 35%. "
            "If n1 is False, then n0 is False with probability of 65%. "
            "n1 is true with probability of 55%."
        )
        query = "What is the probability that n0 is True given that n1 is False?"
        graph = "('n1',) -> n0 | () -> n1"

        r1 = compiled.solve_from_text(context, query, graph)
        r2 = manual.solve_from_text(context, query, graph)
        self.assertAlmostEqual(r1, r2, places=10)


class TestSerializationRoundtrip(unittest.TestCase):
    """TaskSpec 序列化/反序列化往返测试"""

    def test_roundtrip(self):
        for fname in ["flight.json", "bandit.json", "blind.json"]:
            with open(os.path.join(EXAMPLES_DIR, fname)) as f:
                original = json.load(f)
            spec = TaskSpec.from_dict(original)
            roundtripped = spec.to_dict()
            self.assertEqual(original, roundtripped, f"{fname} 序列化往返不一致")


if __name__ == "__main__":
    unittest.main()
