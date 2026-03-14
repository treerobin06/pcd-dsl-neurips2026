"""
DSL Layer 2: Family Macros（推断族宏）

每个 macro 由 core ops 组合而成，对应一种推断范式。
数学上都是 posterior ∝ prior × likelihood 的实例化。

Macro 清单:
1. softmax_pref_likelihood — 假设枚举（偏好学习）
2. beta_bernoulli_update  — 共轭更新（多臂赌博机）
3. ve_query               — 变量消除（贝叶斯网络推断）
"""

import re
import numpy as np
from itertools import product as itertools_product
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

from .types import Distribution, Factor, HypothesisSpace, Evidence
from .core_ops import (
    condition,
    multiply,
    marginalize,
    normalize,
    enumerate_hypotheses,
    expectation,
    argmax,
)


# ═══════════════════════════════════════════════════════════════════════════
# 1. softmax_pref_likelihood — 假设枚举（偏好学习）
# ═══════════════════════════════════════════════════════════════════════════

def softmax_pref_likelihood(
    prior: Distribution,
    choice_idx: int,
    option_features: List[List[float]],
    temperature: float = 1.0,
) -> Distribution:
    """Softmax 偏好似然更新

    posterior(h) ∝ prior(h) × P(choice | h, options)
    P(choice=i | h, options) = softmax(utility(option_i, h) / temperature)

    对应 BayesianSidecar.update() 的操作。

    Args:
        prior: 当前后验分布（support 为偏好向量元组）
        choice_idx: 用户选择的选项索引
        option_features: 每个选项的特征向量 [[f1,f2,...], ...]
        temperature: softmax 温度

    Returns:
        更新后的后验分布
    """
    # 向量化计算: options (n_opts, dim), hypotheses (n_hyp, dim)
    opts = np.array(option_features, dtype=np.float64)
    hyps = np.array(prior.support, dtype=np.float64)
    # utilities: (n_opts, n_hyp)
    utilities = opts @ hyps.T

    # 数值稳定 softmax
    scaled = utilities / temperature
    scaled -= scaled.max(axis=0, keepdims=True)
    exp_u = np.exp(scaled)
    probs = exp_u / exp_u.sum(axis=0, keepdims=True)

    # likelihood: P(choice | h)
    likelihoods = probs[choice_idx]

    # posterior ∝ prior × likelihood
    new_probs = prior.probs * likelihoods
    total = new_probs.sum()
    if total > 0:
        new_probs /= total
    else:
        new_probs = np.ones(len(prior)) / len(prior)

    return Distribution(support=list(prior.support), probs=new_probs)


# ═══════════════════════════════════════════════════════════════════════════
# 2. beta_bernoulli_update — 共轭更新（多臂赌博机）
# ═══════════════════════════════════════════════════════════════════════════

def beta_bernoulli_update(
    alpha: np.ndarray,
    beta_params: np.ndarray,
    arm: int,
    reward: int,
) -> Tuple[np.ndarray, np.ndarray]:
    """Beta-Bernoulli 共轭更新

    观测到 arm 的 reward 后更新后验：
      alpha[arm] += reward
      beta[arm] += (1 - reward)

    对应 BanditSidecar.update() 的操作。

    Args:
        alpha: 所有臂的 Beta 分布 α 参数
        beta_params: 所有臂的 Beta 分布 β 参数
        arm: 选择的臂 (0-indexed)
        reward: 0 或 1

    Returns:
        (new_alpha, new_beta) 更新后的参数
    """
    new_alpha = alpha.copy()
    new_beta = beta_params.copy()
    new_alpha[arm] += reward
    new_beta[arm] += (1 - reward)
    return new_alpha, new_beta


def beta_posterior_mean(alpha: np.ndarray, beta_params: np.ndarray) -> np.ndarray:
    """Beta 分布的后验均值: α / (α + β)"""
    return alpha / (alpha + beta_params)


def beta_recommend(alpha: np.ndarray, beta_params: np.ndarray) -> int:
    """基于后验均值推荐最佳臂"""
    means = beta_posterior_mean(alpha, beta_params)
    return int(np.argmax(means))


def beta_thompson_sample(alpha: np.ndarray, beta_params: np.ndarray) -> int:
    """Thompson Sampling: 从后验采样"""
    samples = np.array([
        np.random.beta(alpha[i], beta_params[i])
        for i in range(len(alpha))
    ])
    return int(np.argmax(samples))


# ═══════════════════════════════════════════════════════════════════════════
# 3. ve_query — 变量消除（贝叶斯网络推断）
# ═══════════════════════════════════════════════════════════════════════════

def ve_query(
    factors: List[Factor],
    query_vars: Dict[str, Any],
    evidence: Dict[str, Any],
) -> float:
    """变量消除查询

    计算 P(query_vars | evidence)

    对应 BNSolver._variable_elimination() 的操作。

    Args:
        factors: 所有 CPT 因子列表
        query_vars: 查询变量赋值 {var: value}
        evidence: 证据变量赋值 {var: value}

    Returns:
        查询概率值
    """
    # 1. 条件化：应用证据
    conditioned = [condition(f, evidence) for f in factors]

    # 2. 确定需要消除的变量
    all_vars: Set[str] = set()
    for f in conditioned:
        all_vars.update(f.variables)
    eliminate = all_vars - set(query_vars.keys()) - set(evidence.keys())

    # 3. 逐一消除变量
    current_factors = conditioned
    for var in eliminate:
        current_factors = _eliminate_one(current_factors, var)

    # 4. 合并剩余因子
    product = multiply(current_factors)

    # 5. 归一化并提取查询概率
    total = sum(product.table.values())
    if total == 0:
        return 0.0

    target_prob = 0.0
    for vals, prob in product.table.items():
        match = True
        for i, var in enumerate(product.variables):
            if var in query_vars and vals[i] != query_vars[var]:
                match = False
                break
        if match:
            target_prob += prob

    return target_prob / total


def _eliminate_one(factors: List[Factor], var: str) -> List[Factor]:
    """消除一个变量：找到包含它的因子，相乘后在该变量上求和"""
    relevant = [f for f in factors if var in f.variables]
    irrelevant = [f for f in factors if var not in f.variables]

    if not relevant:
        return irrelevant

    # 相乘
    product = multiply(relevant)
    # 边缘化
    result = marginalize(product, {var})

    irrelevant.append(result)
    return irrelevant


# ═══════════════════════════════════════════════════════════════════════════
# 辅助：BN 文本解析（从 bn_solver.py 迁移）
# ═══════════════════════════════════════════════════════════════════════════

def parse_bn_graph(graph_str: str) -> Tuple[List[str], Dict[str, List[str]]]:
    """解析 BLInD 格式的图字符串

    格式: "('n1',) -> n0 | ('n0',) -> n1 | () -> n3"

    Returns:
        (nodes, parents) — 节点列表和父节点映射
    """
    parents: Dict[str, List[str]] = {}
    nodes: List[str] = []
    edges = graph_str.split(" | ")
    for edge in edges:
        edge = edge.strip()
        m = re.match(r'\(([^)]*)\)\s*->\s*(\w+)', edge)
        if not m:
            continue
        parents_str = m.group(1).strip()
        child = m.group(2).strip()

        if parents_str:
            parent_list = [
                p.strip().strip("'\"")
                for p in parents_str.split(",")
                if p.strip().strip("'\"")
            ]
        else:
            parent_list = []

        parents[child] = parent_list
        if child not in nodes:
            nodes.append(child)
        for p in parent_list:
            if p not in nodes:
                nodes.append(p)

    return nodes, parents


def parse_bn_cpt(
    context_str: str,
    parents: Dict[str, List[str]],
) -> List[Factor]:
    """解析 BLInD 格式的 CPT 文本，返回 Factor 列表

    每个节点的 CPT 转换为一个 Factor。

    Returns:
        Factor 列表，每个 Factor 的 variables = [node] + parents
    """
    # 先收集原始 CPT 数据
    cpts: Dict[str, Dict[tuple, Dict[bool, float]]] = {}
    sentences = re.split(r'\.\s*', context_str)

    for sent in sentences:
        sent = sent.strip()
        if not sent:
            continue

        # 模式 1: 有条件 "If X is V1 [and Y is V2], then Z is V3 with probability of P%"
        m = re.match(
            r'If\s+(.+?),\s*then\s+(\w+)\s+is\s+(True|False)\s+with\s+probability\s+of\s+([\d.]+)%',
            sent, re.IGNORECASE
        )
        if m:
            cond_str = m.group(1)
            child = m.group(2)
            child_val = m.group(3).lower() == "true"
            prob = float(m.group(4)) / 100.0

            conditions = {}
            cond_parts = re.findall(r'(\w+)\s+is\s+(True|False)', cond_str, re.IGNORECASE)
            for var, val in cond_parts:
                conditions[var] = val.lower() == "true"

            if child not in cpts:
                cpts[child] = {}
            parent_order = parents.get(child, [])
            parent_vals = tuple(conditions.get(p, True) for p in parent_order)
            if parent_vals not in cpts[child]:
                cpts[child][parent_vals] = {}
            cpts[child][parent_vals][child_val] = prob
            continue

        # 模式 2: 无条件 "n3 is true with probability of 52%"
        m2 = re.match(
            r'(?:The\s+probability\s+that\s+)?(\w+)\s+is\s+(true|false)\s+(?:is|with\s+probability\s+of)\s+([\d.]+)%',
            sent, re.IGNORECASE
        )
        if m2:
            node = m2.group(1)
            val = m2.group(2).lower() == "true"
            prob = float(m2.group(3)) / 100.0

            if node not in cpts:
                cpts[node] = {}
            if () not in cpts[node]:
                cpts[node][()] = {}
            cpts[node][()][val] = prob

    # 将 CPT 转为 Factor 列表
    factors = []
    for node, cpt in cpts.items():
        parent_list = parents.get(node, [])
        variables = [node] + parent_list
        table: Dict[tuple, float] = {}

        if not parent_list:
            p_true = cpt.get((), {}).get(True, 0.5)
            p_false = cpt.get((), {}).get(False, 1 - p_true)
            table[(True,)] = p_true
            table[(False,)] = p_false
        else:
            for parent_vals in itertools_product([True, False], repeat=len(parent_list)):
                probs = cpt.get(parent_vals, {})
                p_true = probs.get(True, 0.5)
                p_false = probs.get(False, 1 - p_true)
                table[(True,) + parent_vals] = p_true
                table[(False,) + parent_vals] = p_false

        factors.append(Factor(variables=variables, table=table))

    return factors


def parse_bn_query(query_str: str) -> Tuple[Dict[str, bool], Dict[str, bool]]:
    """解析查询字符串

    Returns:
        (query_vars, evidence) — {var: bool_value} 字典
    """
    parts = re.split(r'\s+given\s+that\s+', query_str, flags=re.IGNORECASE)

    query_vars = {}
    var_matches = re.findall(r'(\w+)\s+is\s+(True|False)', parts[0])
    for var, val in var_matches:
        query_vars[var] = val == "True"

    evidence = {}
    if len(parts) > 1:
        ev_matches = re.findall(r'(\w+)\s+is\s+(True|False)', parts[1])
        for var, val in ev_matches:
            evidence[var] = val == "True"

    return query_vars, evidence
