"""
DSL Layer 1: Core Typed Ops（底层算子）

8 个核心算子，覆盖所有概率推理任务的基本操作。
所有 family macro 由这些算子组合而成。
"""

import numpy as np
from itertools import product as itertools_product
from typing import Any, Callable, Dict, List, Set, Tuple

from .types import Distribution, Factor, HypothesisSpace


# ─── 1. condition ────────────────────────────────────────────────────────────

def condition(factor: Factor, evidence: Dict[str, Any]) -> Factor:
    """条件化：将 factor 中与 evidence 不一致的条目移除

    Args:
        factor: 输入因子
        evidence: 变量赋值 {var_name: value}

    Returns:
        新的 factor，只保留与 evidence 一致的条目
    """
    new_table = {}
    for vals, prob in factor.table.items():
        consistent = True
        for i, var in enumerate(factor.variables):
            if var in evidence and vals[i] != evidence[var]:
                consistent = False
                break
        if consistent:
            new_table[vals] = prob
    return Factor(variables=list(factor.variables), table=new_table)


# ─── 2. multiply ────────────────────────────────────────────────────────────

def multiply(factors: List[Factor]) -> Factor:
    """因子乘积：将多个因子相乘，共享变量对齐

    Args:
        factors: 因子列表

    Returns:
        乘积因子
    """
    if not factors:
        return Factor(variables=[], table={(): 1.0})
    result = factors[0]
    for i in range(1, len(factors)):
        result = _multiply_two(result, factors[i])
    return result


def _multiply_two(f1: Factor, f2: Factor) -> Factor:
    """两个因子相乘"""
    # 合并变量（保序）
    all_vars = list(f1.variables)
    for v in f2.variables:
        if v not in all_vars:
            all_vars.append(v)

    new_table = {}
    for vals1, prob1 in f1.table.items():
        for vals2, prob2 in f2.table.items():
            # 检查共享变量一致性
            combined = {}
            consistent = True
            for i, v in enumerate(f1.variables):
                combined[v] = vals1[i]
            for i, v in enumerate(f2.variables):
                if v in combined:
                    if combined[v] != vals2[i]:
                        consistent = False
                        break
                else:
                    combined[v] = vals2[i]

            if consistent:
                new_vals = tuple(combined[v] for v in all_vars)
                new_table[new_vals] = new_table.get(new_vals, 0) + prob1 * prob2

    return Factor(variables=all_vars, table=new_table)


# ─── 3. marginalize ─────────────────────────────────────────────────────────

def marginalize(factor: Factor, eliminate_vars: Set[str]) -> Factor:
    """边缘化：对指定变量求和消除

    Args:
        factor: 输入因子
        eliminate_vars: 要消除的变量集合

    Returns:
        消除指定变量后的因子
    """
    keep_indices = [i for i, v in enumerate(factor.variables) if v not in eliminate_vars]
    new_vars = [factor.variables[i] for i in keep_indices]

    new_table: Dict[tuple, float] = {}
    for vals, prob in factor.table.items():
        new_vals = tuple(vals[i] for i in keep_indices)
        new_table[new_vals] = new_table.get(new_vals, 0) + prob

    return Factor(variables=new_vars, table=new_table)


# ─── 4. normalize ───────────────────────────────────────────────────────────

def normalize(factor: Factor) -> Distribution:
    """归一化：将因子转为概率分布

    对于单变量因子，support = 各值；对于多变量因子，support = 赋值元组。

    Args:
        factor: 输入因子

    Returns:
        归一化后的概率分布
    """
    entries = list(factor.table.items())
    if not entries:
        return Distribution(support=[], probs=np.array([]))

    support = [k if len(k) > 1 else k[0] for k, _ in entries]
    probs = np.array([v for _, v in entries], dtype=np.float64)
    total = probs.sum()
    if total > 0:
        probs /= total

    return Distribution(support=support, probs=probs)


# ─── 5. enumerate_hypotheses ────────────────────────────────────────────────

def enumerate_hypotheses(space: HypothesisSpace) -> List[Any]:
    """枚举假设空间中的所有假设

    Args:
        space: 假设空间定义

    Returns:
        所有假设的列表
    """
    if space.explicit_list:
        return list(space.explicit_list)
    return list(itertools_product(*space.dimensions))


# ─── 6. expectation ─────────────────────────────────────────────────────────

def expectation(dist: Distribution, func: Callable[[Any], float]) -> float:
    """计算分布上的期望值

    E[f(x)] = Σ p(x) * f(x)

    Args:
        dist: 概率分布
        func: 值函数 f(x) → scalar

    Returns:
        期望值
    """
    values = np.array([func(v) for v in dist.support], dtype=np.float64)
    return float(np.dot(dist.probs, values))


# ─── 7. argmax ──────────────────────────────────────────────────────────────

def argmax(scores: Dict[Any, float]) -> Any:
    """返回得分最高的键

    Args:
        scores: {action: score} 映射

    Returns:
        得分最高的 action
    """
    return max(scores, key=scores.get)
