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
    type: str  # discrete_hypothesis_space | beta_conjugate | bayesian_network
    # hypothesis_enumeration 特有
    hypothesis: str = ""  # linear_preference_weights
    features: List[str] = field(default_factory=list)
    values_per_feature: List[float] = field(default_factory=list)
    # beta_conjugate 特有
    n_arms: int = 0
    prior_alpha: float = 1.0
    prior_beta: float = 1.0
    # bayesian_network 特有
    # (BN 结构从数据中解析，不在 TaskSpec 中硬编码)


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
        valid_families = {"hypothesis_enumeration", "conjugate_update", "variable_elimination"}
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

        return errors
