"""
Gold Reference Solver: Naive Bayes 分类（held-out family）

Inference Family: naive_bayes
Composition (no macro): condition + multiply + normalize + argmax

C2 修复 (2026-04-28): 之前 NB 实验靠 LLM codegen — LLM 写 Python 代码字符串
然后 subprocess 执行（见 baselines/run_held_out_family.py:255 execute_python_code）。
那个 compile_core_ops=1.0 数据**不是真用 7 core ops 组合**——是 LLM 写代码
import 了 ops 名字然后用 dict + 标量乘法实现 NB。

本 solver 是**确定性 Python**（不是 LLM 生成的）真用 dsl/core_ops 组合：
P(c | observed_features) ∝ P(c) × ∏_j P(f_j = obs | c)
= condition(P(f_j | c), {f_j: obs_value})  → likelihood factor over class
× multiply across all features + prior
→ normalize → posterior over class
→ argmax → predicted class

LLM Inductor 输出 declarative TaskSpec（含 classes / feature_likelihoods / prior），
Compiler 实例化 NBSolver；LLM 不写代码，只 fill spec。
"""

import numpy as np
from typing import Dict, List, Optional

from dsl import (
    Distribution,
    Factor,
    condition,
    multiply,
    marginalize,
    normalize,
    argmax,
)


class NBSolver:
    """Naive Bayes 分类 solver — 真用 4 个 dsl/core_ops 组合实现。

    数学:
      P(c | f_1=v_1, ..., f_J=v_J) ∝ P(c) × ∏_j P(f_j = v_j | c)

    实现策略 (核心 ops 调用链):
      1. 构造 prior factor (variables=[class])
      2. 对每个 feature j: 构造 P(f_j | class) 的 Factor (variables=[f_j, class])
      3. condition 每个 likelihood factor 在观察值上 → 仅含 class variable 的 Factor
      4. multiply 所有条件化 likelihoods + prior → joint Factor (variables=[class])
      5. normalize → posterior Distribution
      6. argmax → MAP class

    Args:
        classes: 类别名列表（任意 hashable，typically 字符串）
        feature_likelihoods: nested dict
            {feature_name: {feature_value: {class_name: prob}}}
            i.e. P(f_j = v | c) 完整 CPT
        prior: Optional class prior dict {class: prob}; default uniform
    """

    CLASS_VAR = "_nb_class"

    def __init__(
        self,
        classes: List[str],
        feature_likelihoods: Dict[str, Dict[str, Dict[str, float]]],
        prior: Optional[Dict[str, float]] = None,
    ):
        if not classes:
            raise ValueError("NBSolver: classes 不能为空")
        if not feature_likelihoods:
            raise ValueError("NBSolver: feature_likelihoods 不能为空")

        self.classes = list(classes)
        self.feature_names = list(feature_likelihoods.keys())
        self.feature_likelihoods = feature_likelihoods

        # 校验：每个 feature 的 CPT 必须含全部 classes
        for fname, cpt in feature_likelihoods.items():
            if not cpt:
                raise ValueError(f"NBSolver: feature '{fname}' CPT 为空")
            for fval, vrow in cpt.items():
                missing = set(self.classes) - set(vrow.keys())
                if missing:
                    raise ValueError(
                        f"NBSolver: feature '{fname}' value '{fval}' 缺类别 {missing}"
                    )

        # Prior factor: P(class)
        if prior is None:
            prior_arr = np.ones(len(self.classes)) / len(self.classes)
            prior_dict = dict(zip(self.classes, prior_arr.tolist()))
        else:
            missing = set(self.classes) - set(prior.keys())
            if missing:
                raise ValueError(f"NBSolver: prior 缺类别 {missing}")
            prior_dict = {c: float(prior[c]) for c in self.classes}

        self.prior_factor = Factor(
            variables=[self.CLASS_VAR],
            table={(c,): p for c, p in prior_dict.items()},
        )

        # Likelihood factors: per feature, P(f_j | class)
        # Factor variables=[feature_name, class_var]
        self.likelihood_factors: Dict[str, Factor] = {}
        for fname in self.feature_names:
            cpt = feature_likelihoods[fname]
            table = {}
            for fval, class_probs in cpt.items():
                for c, p in class_probs.items():
                    table[(fval, c)] = float(p)
            self.likelihood_factors[fname] = Factor(
                variables=[fname, self.CLASS_VAR],
                table=table,
            )

    def predict(self, observed_features: Dict[str, str]) -> str:
        """从观察特征预测最可能类别。

        Args:
            observed_features: {feature_name: observed_value}

        Returns:
            predicted class name (with highest posterior probability)
        """
        post = self.predict_proba(observed_features)
        return post.map_value()

    def predict_proba(self, observed_features: Dict[str, str]) -> Distribution:
        """返回 class 后验分布（用 ops 真组合）。

        Pipeline:
          factors = [prior_factor]
          for f_j, v_j in observed:
              cond_j = condition(likelihood_j, {f_j: v_j})  # → Factor over class
              factors.append(cond_j)
          joint = multiply(factors)                         # → Factor over class
          posterior = normalize(joint)                      # → Distribution
        """
        if not observed_features:
            # 无观测时返回 prior 归一化
            return normalize(self.prior_factor)

        # Step 1: 收集 prior + 每个观察特征的条件化似然
        factors: List[Factor] = [self.prior_factor]
        for fname, fval in observed_features.items():
            if fname not in self.likelihood_factors:
                raise ValueError(f"NBSolver: 未知 feature '{fname}'")
            full_factor = self.likelihood_factors[fname]
            # condition 仅过滤 table 条目，但 Factor.variables 仍含 fname
            cond_factor = condition(full_factor, {fname: fval})
            if not cond_factor.table:
                raise ValueError(
                    f"NBSolver: feature '{fname}' 不含 value '{fval}'"
                )
            factors.append(cond_factor)

        # Step 2: 因子相乘 — joint Factor 含 [CLASS_VAR, fname1, fname2, ...]
        joint = multiply(factors)

        # Step 3: marginalize 掉所有 feature variables（已 condition 固定，残留 var 名）
        # 真用 marginalize op：从 [CLASS_VAR, fname1, ...] 投影到 [CLASS_VAR]
        feature_vars = set(observed_features.keys())
        if feature_vars:
            joint = marginalize(joint, feature_vars)

        # Step 4: 归一化 → Distribution over class
        posterior = normalize(joint)

        return posterior

    def predict_with_scores(
        self, observed_features: Dict[str, str]
    ) -> tuple:
        """同 predict 但返回 (class, posterior_probs_dict)"""
        post = self.predict_proba(observed_features)
        scores = {c: float(post.prob_of(c)) for c in self.classes}
        # 用 dsl/core_ops argmax 取 most likely
        best = argmax(scores)
        return best, scores

    def reset(self):
        """NB 是 stateless per query, no-op"""
        pass
