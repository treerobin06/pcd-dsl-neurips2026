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
    """贝叶斯网络推断 solver — 基于 DSL 原语

    C3 真重构 (2026-04-24): __init__ 现在接 spec config，让 spec 真参与编译。
    在此之前 _compile_bn(spec) 直接 `return BNReferenceSolver()` 完全忽略 spec
    （Codex CRITICAL 1 + paper-claim-audit-detailed 标为身份危机）。
    """

    SUPPORTED_INFERENCE_METHODS = {"variable_elimination"}
    SUPPORTED_INPUT_FORMATS = {"blind_text", "factors_dict"}
    SUPPORTED_PRECISION = {"float64"}

    def __init__(
        self,
        inference_method: str = "variable_elimination",
        input_format: str = "blind_text",
        numerical_precision: str = "float64",
    ):
        """构造 BN solver。

        Args:
            inference_method: ve | (future: junction_tree, sampling)
            input_format: blind_text (BLInD CSV 文本) | factors_dict (预解析的 Factor list)
            numerical_precision: float64 | (future: mpfr 任意精度)

        Raises:
            ValueError: 不支持的配置 — 这是 C3 真编译的关键，spec 内容
                决定 solver 的实际行为而非 routing 到唯一实现
        """
        if inference_method not in self.SUPPORTED_INFERENCE_METHODS:
            raise ValueError(
                f"BN inference_method '{inference_method}' not yet supported. "
                f"Supported: {sorted(self.SUPPORTED_INFERENCE_METHODS)}. "
                f"This is intentional: spec content drives solver dispatch (C3 fix)."
            )
        if input_format not in self.SUPPORTED_INPUT_FORMATS:
            raise ValueError(
                f"BN input_format '{input_format}' not supported. "
                f"Supported: {sorted(self.SUPPORTED_INPUT_FORMATS)}."
            )
        if numerical_precision not in self.SUPPORTED_PRECISION:
            raise ValueError(
                f"BN numerical_precision '{numerical_precision}' not supported. "
                f"Supported: {sorted(self.SUPPORTED_PRECISION)}."
            )

        self.inference_method = inference_method
        self.input_format = input_format
        self.numerical_precision = numerical_precision

    def solve_from_text(
        self,
        context: str,
        query: str,
        graph: str,
    ) -> Optional[float]:
        """从 BLInD 格式文本求解（input_format="blind_text" 路径）

        Args:
            context: CPT 自然语言描述
            query: 查询字符串
            graph: 图结构字符串

        Returns:
            查询概率值
        """
        if self.input_format != "blind_text":
            raise ValueError(
                f"solve_from_text requires input_format='blind_text', "
                f"but solver was compiled with input_format='{self.input_format}'"
            )
        # 解析 BN 结构
        nodes, parents = parse_bn_graph(graph)
        # 解析 CPT → Factor 列表
        factors = parse_bn_cpt(context, parents)
        # 解析查询
        query_vars, evidence = parse_bn_query(query)

        if not query_vars:
            return None

        # 用 DSL ve_query 计算（inference_method = "variable_elimination"）
        return ve_query(factors, query_vars, evidence)

    def solve_from_factors(
        self,
        factors,
        query_vars,
        evidence,
    ) -> Optional[float]:
        """从预解析的 Factor list 求解（input_format="factors_dict" 路径）"""
        if self.input_format != "factors_dict":
            raise ValueError(
                f"solve_from_factors requires input_format='factors_dict', "
                f"but solver was compiled with input_format='{self.input_format}'"
            )
        if not query_vars:
            return None
        return ve_query(factors, query_vars, evidence)
