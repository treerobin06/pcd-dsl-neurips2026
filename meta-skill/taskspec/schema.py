"""
TaskSpec Schema — 声明式任务规范

TaskSpec 是 Inductor 和 Compiler 之间的接口。
Inductor 从样本归纳出 TaskSpec，Compiler 根据 TaskSpec 确定性地编译出 solver。

TaskSpec 定义了一个概率推理任务的完整数学结构：
- inference_family: 推断范式（决定选用哪个 family macro）
- state_structure: 状态空间定义
- observation_model: 观测/似然模型
- decision_rule: 决策规则
- data_format: 数据格式描述
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
import json


@dataclass
class StateStructure:
    """状态空间结构"""
    type: str  # discrete_hypothesis_space | beta_conjugate | bayesian_network | naive_bayes_classes | hmm_states
    # hypothesis_enumeration 特有
    hypothesis: str = ""  # linear_preference_weights
    features: List[str] = field(default_factory=list)
    values_per_feature: List[float] = field(default_factory=list)
    # beta_conjugate 特有
    n_arms: int = 0
    prior_alpha: float = 1.0
    prior_beta: float = 1.0
    # bayesian_network 特有 (C3 真重构 2026-04-24)
    # 实例级 DAG/CPT 仍 per-query 解析；schema 级配置参与编译。
    bn_inference_method: str = "variable_elimination"  # ve | (future: junction_tree, sampling)
    bn_input_format: str = "blind_text"  # blind_text | factors_dict
    bn_numerical_precision: str = "float64"  # float64 | (future: mpfr)
    # naive_bayes 特有 (C2 真 ops 组合 2026-04-28)
    # 实例级 classes / feature_likelihoods 通过 spec field 传 compiler
    nb_classes: List[str] = field(default_factory=list)
    # nb_feature_likelihoods: {fname: {fval: {class: prob}}}
    nb_feature_likelihoods: Dict[str, Any] = field(default_factory=dict)
    nb_prior: Dict[str, float] = field(default_factory=dict)  # optional, empty = uniform
    # hmm_forward 特有 (C2 2026-04-28)
    hmm_states: List[str] = field(default_factory=list)
    hmm_observations: List[str] = field(default_factory=list)
    # hmm_initial: {state: prob}
    hmm_initial: Dict[str, float] = field(default_factory=dict)
    # hmm_transition: {from_state: {to_state: prob}}
    hmm_transition: Dict[str, Dict[str, float]] = field(default_factory=dict)
    # hmm_emission: {state: {observation: prob}}
    hmm_emission: Dict[str, Dict[str, float]] = field(default_factory=dict)


@dataclass
class ObservationModel:
    """观测/似然模型"""
    type: str  # softmax_choice | bernoulli_reward | cpt_given
    temperature: float = 1.0
    input: str = ""  # 输入描述


@dataclass
class DecisionRule:
    """决策规则"""
    type: str  # argmax_expected_utility | argmax_posterior_mean | exact_probability
    utility: str = ""  # 效用函数描述


@dataclass
class DataFormat:
    """数据格式描述"""
    rounds: str = "sequential"  # sequential | single_shot
    options_per_round: int = 0
    feedback: str = ""  # chosen_option_index | binary_reward | none


@dataclass
class TaskSpec:
    """完整的任务规范"""
    task_name: str
    inference_family: str  # hypothesis_enumeration | conjugate_update | variable_elimination
    state_structure: StateStructure
    observation_model: ObservationModel
    decision_rule: DecisionRule
    data_format: DataFormat

    def to_dict(self) -> Dict[str, Any]:
        """序列化为字典"""
        return {
            "task_name": self.task_name,
            "inference_family": self.inference_family,
            "state_structure": {
                "type": self.state_structure.type,
                "hypothesis": self.state_structure.hypothesis,
                "features": self.state_structure.features,
                "values_per_feature": self.state_structure.values_per_feature,
                "n_arms": self.state_structure.n_arms,
                "prior_alpha": self.state_structure.prior_alpha,
                "prior_beta": self.state_structure.prior_beta,
                "bn_inference_method": self.state_structure.bn_inference_method,
                "bn_input_format": self.state_structure.bn_input_format,
                "bn_numerical_precision": self.state_structure.bn_numerical_precision,
            },
            "observation_model": {
                "type": self.observation_model.type,
                "temperature": self.observation_model.temperature,
                "input": self.observation_model.input,
            },
            "decision_rule": {
                "type": self.decision_rule.type,
                "utility": self.decision_rule.utility,
            },
            "data_format": {
                "rounds": self.data_format.rounds,
                "options_per_round": self.data_format.options_per_round,
                "feedback": self.data_format.feedback,
            },
        }

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent)

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> TaskSpec:
        """从字典反序列化"""
        return cls(
            task_name=d["task_name"],
            inference_family=d["inference_family"],
            state_structure=StateStructure(**d["state_structure"]),
            observation_model=ObservationModel(**d["observation_model"]),
            decision_rule=DecisionRule(**d["decision_rule"]),
            data_format=DataFormat(**d["data_format"]),
        )

    @classmethod
    def from_json(cls, s: str) -> TaskSpec:
        return cls.from_dict(json.loads(s))

    def validate(self) -> List[str]:
        """验证 TaskSpec 的合法性，返回错误列表"""
        errors = []
        valid_families = {
            "hypothesis_enumeration",
            "conjugate_update",
            "variable_elimination",
            "naive_bayes",      # C2 2026-04-28: 5-op compose via NBSolver
            "hmm_forward",      # C2 2026-04-28: 5-op compose via HMMSolver
        }
        if self.inference_family not in valid_families:
            errors.append(f"未知 inference_family: {self.inference_family}")

        if self.inference_family == "hypothesis_enumeration":
            if self.state_structure.type != "discrete_hypothesis_space":
                errors.append("hypothesis_enumeration 需要 state_structure.type = discrete_hypothesis_space")
            if not self.state_structure.features:
                errors.append("hypothesis_enumeration 需要 features 列表")
            if not self.state_structure.values_per_feature:
                errors.append("hypothesis_enumeration 需要 values_per_feature")
            if self.observation_model.type != "softmax_choice":
                errors.append("hypothesis_enumeration 需要 observation_model.type = softmax_choice")
            if self.decision_rule.type != "argmax_expected_utility":
                errors.append("hypothesis_enumeration 需要 decision_rule.type = argmax_expected_utility")

        elif self.inference_family == "conjugate_update":
            if self.state_structure.type != "beta_conjugate":
                errors.append("conjugate_update 需要 state_structure.type = beta_conjugate")
            if self.state_structure.n_arms <= 0:
                errors.append("conjugate_update 需要 n_arms > 0")
            if self.observation_model.type != "bernoulli_reward":
                errors.append("conjugate_update 需要 observation_model.type = bernoulli_reward")
            if self.decision_rule.type != "argmax_posterior_mean":
                errors.append("conjugate_update 需要 decision_rule.type = argmax_posterior_mean")

        elif self.inference_family == "variable_elimination":
            if self.state_structure.type != "bayesian_network":
                errors.append("variable_elimination 需要 state_structure.type = bayesian_network")
            if self.observation_model.type != "cpt_given":
                errors.append("variable_elimination 需要 observation_model.type = cpt_given")
            if self.decision_rule.type != "exact_probability":
                errors.append("variable_elimination 需要 decision_rule.type = exact_probability")

        elif self.inference_family == "naive_bayes":
            if self.state_structure.type != "naive_bayes_classes":
                errors.append("naive_bayes 需要 state_structure.type = naive_bayes_classes")
            if not self.state_structure.nb_classes:
                errors.append("naive_bayes 需要 nb_classes 列表")
            if not self.state_structure.nb_feature_likelihoods:
                errors.append("naive_bayes 需要 nb_feature_likelihoods (P(f_j|c) CPT)")

        elif self.inference_family == "hmm_forward":
            if self.state_structure.type != "hmm_states":
                errors.append("hmm_forward 需要 state_structure.type = hmm_states")
            if not self.state_structure.hmm_states:
                errors.append("hmm_forward 需要 hmm_states 列表")
            if not self.state_structure.hmm_initial:
                errors.append("hmm_forward 需要 hmm_initial 分布")
            if not self.state_structure.hmm_transition:
                errors.append("hmm_forward 需要 hmm_transition CPT")
            if not self.state_structure.hmm_emission:
                errors.append("hmm_forward 需要 hmm_emission CPT")

        return errors
