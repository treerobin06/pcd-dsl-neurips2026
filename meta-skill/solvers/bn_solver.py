"""
Gold Reference Solver: 贝叶斯网络推断（BLInD）

Inference Family: Factor Operations (Variable Elimination)
Macro: ve_query

只调用 DSL 原语，功能等价于 BNSolver。
"""

from typing import Optional

from dsl.family_macros import (
    ve_query,
    parse_bn_graph,
    parse_bn_cpt,
    parse_bn_query,
)


class BNReferenceSolver:
    """贝叶斯网络推断 solver — 基于 DSL 原语"""

    def solve_from_text(
        self,
        context: str,
        query: str,
        graph: str,
    ) -> Optional[float]:
        """从 BLInD 格式文本求解

        Args:
            context: CPT 自然语言描述
            query: 查询字符串
            graph: 图结构字符串

        Returns:
            查询概率值
        """
        # 解析 BN 结构
        nodes, parents = parse_bn_graph(graph)
        # 解析 CPT → Factor 列表
        factors = parse_bn_cpt(context, parents)
        # 解析查询
        query_vars, evidence = parse_bn_query(query)

        if not query_vars:
            return None

        # 用 DSL ve_query 计算
        return ve_query(factors, query_vars, evidence)
