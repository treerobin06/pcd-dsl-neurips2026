#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
DSL 单元测试 + Gold Reference Solver 等价性验证

测试分 3 部分:
1. Core Ops 基础功能
2. Family Macros 正确性
3. Gold Solver vs 原始 Solver 等价性
"""

import sys
import os
import unittest
import numpy as np

# 确保能导入项目模块
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
# 原始 solver 路径
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "phase1"))

from dsl import (
    Distribution, Factor, HypothesisSpace,
    condition, multiply, marginalize, normalize,
    enumerate_hypotheses, expectation, argmax,
)
from dsl.family_macros import (
    softmax_pref_likelihood,
    beta_bernoulli_update, beta_posterior_mean, beta_recommend,
    ve_query, parse_bn_graph, parse_bn_cpt, parse_bn_query,
)
from solvers.preference_solver import PreferenceSolver
from solvers.bandit_solver import BanditSolver
from solvers.bn_solver import BNReferenceSolver


# ═══════════════════════════════════════════════════════════════════════════
# Part 1: Core Ops 测试
# ═══════════════════════════════════════════════════════════════════════════

class TestDistribution(unittest.TestCase):
    """Distribution 类型测试"""

    def test_basic(self):
        d = Distribution(support=["A", "B", "C"], probs=np.array([0.5, 0.3, 0.2]))
        self.assertEqual(len(d), 3)
        self.assertAlmostEqual(d.prob_of("A"), 0.5)
        self.assertAlmostEqual(d.prob_of("B"), 0.3)
        self.assertAlmostEqual(d.prob_of("D"), 0.0)  # 不存在
        self.assertEqual(d.map_value(), "A")

    def test_entropy(self):
        # 均匀分布熵最大
        d_uniform = Distribution(support=[0, 1], probs=np.array([0.5, 0.5]))
        self.assertAlmostEqual(d_uniform.entropy(), 1.0)
        # 确定性分布熵为 0
        d_certain = Distribution(support=[0, 1], probs=np.array([1.0, 0.0]))
        self.assertAlmostEqual(d_certain.entropy(), 0.0)


class TestFactor(unittest.TestCase):
    """Factor 类型测试"""

    def test_basic(self):
        f = Factor(
            variables=["X"],
            table={(True,): 0.7, (False,): 0.3}
        )
        self.assertEqual(len(f.table), 2)
        domains = f.get_domains()
        self.assertEqual(domains["X"], {True, False})

    def test_dimension_validation(self):
        with self.assertRaises(ValueError):
            Factor(variables=["X", "Y"], table={(True,): 0.5})  # key 维度不匹配


class TestCondition(unittest.TestCase):
    """condition 算子测试"""

    def test_single_variable(self):
        f = Factor(
            variables=["X", "Y"],
            table={
                (True, True): 0.3,
                (True, False): 0.7,
                (False, True): 0.8,
                (False, False): 0.2,
            }
        )
        # 条件化 Y=True
        result = condition(f, {"Y": True})
        self.assertEqual(len(result.table), 2)
        self.assertAlmostEqual(result.table[(True, True)], 0.3)
        self.assertAlmostEqual(result.table[(False, True)], 0.8)

    def test_no_evidence(self):
        f = Factor(variables=["X"], table={(True,): 0.6, (False,): 0.4})
        result = condition(f, {})
        self.assertEqual(len(result.table), 2)


class TestMultiply(unittest.TestCase):
    """multiply 算子测试"""

    def test_independent_factors(self):
        f1 = Factor(variables=["X"], table={(True,): 0.6, (False,): 0.4})
        f2 = Factor(variables=["Y"], table={(True,): 0.7, (False,): 0.3})
        result = multiply([f1, f2])
        self.assertAlmostEqual(result.table[(True, True)], 0.42)
        self.assertAlmostEqual(result.table[(True, False)], 0.18)

    def test_shared_variables(self):
        f1 = Factor(
            variables=["X", "Y"],
            table={(True, True): 0.3, (True, False): 0.7, (False, True): 0.8, (False, False): 0.2}
        )
        f2 = Factor(variables=["Y"], table={(True,): 0.6, (False,): 0.4})
        result = multiply([f1, f2])
        self.assertAlmostEqual(result.table[(True, True)], 0.18)
        self.assertAlmostEqual(result.table[(True, False)], 0.28)

    def test_empty(self):
        result = multiply([])
        self.assertAlmostEqual(result.table[()], 1.0)


class TestMarginalize(unittest.TestCase):
    """marginalize 算子测试"""

    def test_sum_out(self):
        f = Factor(
            variables=["X", "Y"],
            table={
                (True, True): 0.3,
                (True, False): 0.2,
                (False, True): 0.4,
                (False, False): 0.1,
            }
        )
        result = marginalize(f, {"Y"})
        self.assertEqual(result.variables, ["X"])
        self.assertAlmostEqual(result.table[(True,)], 0.5)
        self.assertAlmostEqual(result.table[(False,)], 0.5)


class TestNormalize(unittest.TestCase):
    """normalize 算子测试"""

    def test_basic(self):
        f = Factor(variables=["X"], table={(True,): 3.0, (False,): 7.0})
        d = normalize(f)
        self.assertAlmostEqual(d.prob_of(True), 0.3)
        self.assertAlmostEqual(d.prob_of(False), 0.7)


class TestEnumerateHypotheses(unittest.TestCase):
    """enumerate_hypotheses 算子测试"""

    def test_cartesian(self):
        space = HypothesisSpace(dimensions=[[-1, 0, 1], [-1, 0, 1]])
        hyps = enumerate_hypotheses(space)
        self.assertEqual(len(hyps), 9)  # 3^2

    def test_explicit(self):
        space = HypothesisSpace(explicit_list=["a", "b", "c"])
        hyps = enumerate_hypotheses(space)
        self.assertEqual(hyps, ["a", "b", "c"])


class TestExpectation(unittest.TestCase):
    """expectation 算子测试"""

    def test_basic(self):
        d = Distribution(support=[1, 2, 3], probs=np.array([0.2, 0.5, 0.3]))
        result = expectation(d, lambda x: x)
        self.assertAlmostEqual(result, 2.1)

    def test_function(self):
        d = Distribution(support=[1, 2, 3], probs=np.array([1/3, 1/3, 1/3]))
        result = expectation(d, lambda x: x ** 2)
        self.assertAlmostEqual(result, (1 + 4 + 9) / 3)


class TestArgmax(unittest.TestCase):
    """argmax 算子测试"""

    def test_basic(self):
        scores = {0: 1.5, 1: 2.3, 2: 0.8}
        self.assertEqual(argmax(scores), 1)


# ═══════════════════════════════════════════════════════════════════════════
# Part 2: Family Macros 测试
# ═══════════════════════════════════════════════════════════════════════════

class TestSoftmaxPrefLikelihood(unittest.TestCase):
    """softmax_pref_likelihood macro 测试"""

    def test_update(self):
        # 2 个假设: (1,0) 偏好特征1, (0,1) 偏好特征2
        prior = Distribution(
            support=[(1, 0), (0, 1)],
            probs=np.array([0.5, 0.5])
        )
        # 选项: opt0=[0.8, 0.2], opt1=[0.2, 0.8]
        # 如果选了 opt0 → 应该更偏向假设 (1,0)
        posterior = softmax_pref_likelihood(
            prior, choice_idx=0,
            option_features=[[0.8, 0.2], [0.2, 0.8]],
            temperature=1.0,
        )
        self.assertGreater(posterior.prob_of((1, 0)), posterior.prob_of((0, 1)))


class TestBetaBernoulliUpdate(unittest.TestCase):
    """beta_bernoulli_update macro 测试"""

    def test_update(self):
        alpha = np.ones(3)
        beta_p = np.ones(3)
        # 臂 0 赢
        alpha, beta_p = beta_bernoulli_update(alpha, beta_p, arm=0, reward=1)
        self.assertAlmostEqual(alpha[0], 2.0)
        self.assertAlmostEqual(beta_p[0], 1.0)
        # 后验均值
        means = beta_posterior_mean(alpha, beta_p)
        self.assertAlmostEqual(means[0], 2/3)
        self.assertAlmostEqual(means[1], 0.5)


class TestVeQuery(unittest.TestCase):
    """ve_query macro 测试"""

    def test_simple_bn(self):
        # 简单 BN: A → B
        # P(A=T) = 0.6
        # P(B=T|A=T) = 0.9, P(B=T|A=F) = 0.2
        f_a = Factor(variables=["A"], table={(True,): 0.6, (False,): 0.4})
        f_b = Factor(
            variables=["B", "A"],
            table={
                (True, True): 0.9, (False, True): 0.1,
                (True, False): 0.2, (False, False): 0.8,
            }
        )
        # P(B=T) = 0.6*0.9 + 0.4*0.2 = 0.62
        result = ve_query([f_a, f_b], query_vars={"B": True}, evidence={})
        self.assertAlmostEqual(result, 0.62, places=6)

        # P(A=T|B=T) = 0.6*0.9 / 0.62 = 0.8709...
        result2 = ve_query([f_a, f_b], query_vars={"A": True}, evidence={"B": True})
        self.assertAlmostEqual(result2, 0.54 / 0.62, places=6)


class TestBNParsing(unittest.TestCase):
    """BN 文本解析测试"""

    def test_parse_graph(self):
        graph = "('n1',) -> n0 | () -> n1"
        nodes, parents = parse_bn_graph(graph)
        self.assertIn("n0", nodes)
        self.assertIn("n1", nodes)
        self.assertEqual(parents["n0"], ["n1"])
        self.assertEqual(parents["n1"], [])

    def test_parse_and_solve(self):
        graph = "('n1',) -> n0 | () -> n1"
        context = (
            "If n1 is True, then n0 is True with probability of 90%. "
            "If n1 is True, then n0 is False with probability of 10%. "
            "If n1 is False, then n0 is True with probability of 30%. "
            "If n1 is False, then n0 is False with probability of 70%. "
            "n1 is true with probability of 60%. "
            "n1 is false with probability of 40%."
        )
        nodes, parents = parse_bn_graph(graph)
        factors = parse_bn_cpt(context, parents)
        # P(n0=T) = 0.6*0.9 + 0.4*0.3 = 0.66
        result = ve_query(factors, {"n0": True}, {})
        self.assertAlmostEqual(result, 0.66, places=4)


# ═══════════════════════════════════════════════════════════════════════════
# Part 3: Gold Solver vs 原始 Solver 等价性
# ═══════════════════════════════════════════════════════════════════════════

class TestPreferenceSolverEquivalence(unittest.TestCase):
    """PreferenceSolver vs BayesianSidecar 等价性"""

    def test_equivalence(self):
        from bayesian_sidecar import BayesianSidecar

        pref_vals = [-1, 0, 1]
        dim = 2
        old = BayesianSidecar(feature_dim=dim, preference_values=pref_vals)
        new = PreferenceSolver(feature_dim=dim, preference_values=pref_vals)

        # 模拟 3 轮交互
        rng = np.random.default_rng(42)
        for _ in range(3):
            options = rng.uniform(0, 1, (3, dim)).tolist()
            choice = rng.integers(3)

            old.update(choice, options)
            new.update(choice, options)

            # 验证后验一致
            np.testing.assert_allclose(
                old.posterior, new.posterior.probs, atol=1e-10,
                err_msg="后验分布不一致"
            )

            # 验证推荐一致
            old_rec = old.recommend(options)
            new_rec = new.recommend(options)
            self.assertEqual(old_rec, new_rec, "推荐不一致")

            # 验证 EU 一致
            old_eus = old.get_expected_utilities(options)
            new_eus = new.get_expected_utilities(options)
            for i in range(3):
                self.assertAlmostEqual(old_eus[i], new_eus[i], places=10,
                    msg=f"选项 {i} EU 不一致")


class TestBanditSolverEquivalence(unittest.TestCase):
    """BanditSolver vs BanditSidecar 等价性"""

    def test_equivalence(self):
        from bandit_sidecar import BanditSidecar

        n_arms = 4
        old = BanditSidecar(n_arms)
        new = BanditSolver(n_arms)

        rng = np.random.default_rng(42)
        for _ in range(20):
            arm = rng.integers(n_arms)
            reward = rng.integers(2)

            old.update(arm, reward)
            new.update(arm, reward)

            # 验证后验均值一致
            np.testing.assert_allclose(
                old.get_posterior_means(), new.get_posterior_means(), atol=1e-10,
                err_msg="后验均值不一致"
            )

            # 验证推荐一致
            self.assertEqual(old.recommend(), new.recommend(), "推荐不一致")


class TestBNSolverEquivalence(unittest.TestCase):
    """BNReferenceSolver vs BNSolver 等价性"""

    def test_equivalence_simple(self):
        from bn_solver import solve_blind_example

        context = (
            "If n1 is True, then n0 is True with probability of 80%. "
            "If n1 is True, then n0 is False with probability of 20%. "
            "If n1 is False, then n0 is True with probability of 35%. "
            "If n1 is False, then n0 is False with probability of 65%. "
            "n1 is true with probability of 55%. "
            "n1 is false with probability of 45%."
        )
        query = "What is the probability that n0 is True given that n1 is False?"
        graph = "('n1',) -> n0 | () -> n1"

        old_result = solve_blind_example(context, query, graph)
        new_solver = BNReferenceSolver()
        new_result = new_solver.solve_from_text(context, query, graph)

        self.assertAlmostEqual(old_result, new_result, places=10,
            msg="BN 推断结果不一致")

    def test_equivalence_3node(self):
        from bn_solver import solve_blind_example

        context = (
            "If n1 is True, then n0 is True with probability of 70%. "
            "If n1 is True, then n0 is False with probability of 30%. "
            "If n1 is False, then n0 is True with probability of 20%. "
            "If n1 is False, then n0 is False with probability of 80%. "
            "If n0 is True, then n2 is True with probability of 90%. "
            "If n0 is True, then n2 is False with probability of 10%. "
            "If n0 is False, then n2 is True with probability of 40%. "
            "If n0 is False, then n2 is False with probability of 60%. "
            "n1 is true with probability of 60%. "
            "n1 is false with probability of 40%."
        )
        query = "What is the probability that n2 is True given that n1 is True?"
        graph = "('n1',) -> n0 | ('n0',) -> n2 | () -> n1"

        old_result = solve_blind_example(context, query, graph)
        new_solver = BNReferenceSolver()
        new_result = new_solver.solve_from_text(context, query, graph)

        self.assertAlmostEqual(old_result, new_result, places=10,
            msg="3 节点 BN 推断结果不一致")


if __name__ == "__main__":
    unittest.main()
