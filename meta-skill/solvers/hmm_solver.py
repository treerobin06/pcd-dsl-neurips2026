"""
Gold Reference Solver: HMM Forward Filter（held-out family）

Inference Family: hmm_forward
Composition (no macro): condition + multiply + marginalize + normalize + argmax
（迭代 multiply → marginalize over time）

C2 修复 (2026-04-28): HMM 之前实验靠 LLM codegen——见 baselines/run_hmm_held_out.py
LLM 写 Python 代码字符串再 subprocess 跑，并不真用 dsl/core_ops。
本 solver 是 **确定性 Python** 用 dsl/core_ops 真组合实现 HMM forward 滤波。

Algorithm:
  alpha_0(s) = pi(s) * P(o_0 | s)
  alpha_t(s) = P(o_t | s) * sum_{s'} alpha_{t-1}(s') * P(s | s')
  posterior(s_T | o_0, ..., o_T) = normalize(alpha_T)
"""

from typing import Dict, List, Sequence

from dsl import (
    Distribution,
    Factor,
    condition,
    multiply,
    marginalize,
    normalize,
    argmax,
)


def _rename(factor: Factor, var_map: Dict[str, str]) -> Factor:
    """Helper: rename variables in a Factor (table 不变，仅变量名映射)."""
    new_vars = [var_map.get(v, v) for v in factor.variables]
    return Factor(variables=new_vars, table=dict(factor.table))


class HMMSolver:
    """HMM forward filter — 真用 5 个 dsl/core_ops 组合实现.

    实现策略 (op 调用链):
      初始化 alpha_0:
        emission_factor(STATE, OBS) condition on obs_0 + marginalize OBS
            → factor over [STATE] (即 P(o_0 | s))
        multiply with initial_factor → factor over [STATE] (即 alpha_0)
      迭代 t = 1, ..., T-1:
        prev_alpha rename STATE → PREV_STATE
        multiply(prev_alpha, transition_factor) → factor over [PREV_STATE, STATE]
        marginalize PREV_STATE → factor over [STATE] (即 sum_{s'} alpha_{t-1}(s') P(s|s'))
        condition emission on o_t + marginalize OBS → factor over [STATE]
        multiply → 新 alpha
      Final:
        normalize(alpha_T) → Distribution over states
        argmax → MAP state at final time

    每步 alpha 做 normalize(table) 防数值下溢。
    """

    STATE_VAR = "_hmm_state"
    PREV_STATE_VAR = "_hmm_prev_state"
    OBS_VAR = "_hmm_obs"

    def __init__(
        self,
        states: List[str],
        observations: List[str],
        initial: Dict[str, float],
        transition: Dict[str, Dict[str, float]],
        emission: Dict[str, Dict[str, float]],
    ):
        if not states or not observations:
            raise ValueError("HMMSolver: states / observations 不能为空")

        self.states = list(states)
        self.observations = list(observations)

        for s in states:
            if s not in initial:
                raise ValueError(f"HMMSolver: initial 缺 state '{s}'")
            if s not in transition:
                raise ValueError(f"HMMSolver: transition 缺 state '{s}'")
            if s not in emission:
                raise ValueError(f"HMMSolver: emission 缺 state '{s}'")

        # Initial Factor: variables=[STATE]
        self.initial_factor = Factor(
            variables=[self.STATE_VAR],
            table={(s,): float(initial[s]) for s in states},
        )

        # Transition Factor: variables=[PREV_STATE, STATE]
        # P(s_t | s_{t-1})
        trans_table = {}
        for s_prev, next_dict in transition.items():
            for s_next, p in next_dict.items():
                trans_table[(s_prev, s_next)] = float(p)
        self.transition_factor = Factor(
            variables=[self.PREV_STATE_VAR, self.STATE_VAR],
            table=trans_table,
        )

        # Emission Factor: variables=[STATE, OBS]
        # P(o | s)
        emit_table = {}
        for s, obs_dict in emission.items():
            for o, p in obs_dict.items():
                emit_table[(s, o)] = float(p)
        self.emission_factor = Factor(
            variables=[self.STATE_VAR, self.OBS_VAR],
            table=emit_table,
        )

    def filter(self, obs_sequence: Sequence[str]) -> Distribution:
        """Forward filter — 返回 P(s_T | o_0, ..., o_T) Distribution."""
        if not obs_sequence:
            return normalize(self.initial_factor)

        # Step 0: alpha_0 = pi(s) × P(o_0 | s)
        emis_0 = condition(self.emission_factor, {self.OBS_VAR: obs_sequence[0]})
        emis_0 = marginalize(emis_0, {self.OBS_VAR})  # 投影到 [STATE]
        alpha = multiply([self.initial_factor, emis_0])
        alpha = self._normalize_factor(alpha)

        # 迭代 t = 1, ..., T-1
        for o_t in obs_sequence[1:]:
            alpha_prev = _rename(alpha, {self.STATE_VAR: self.PREV_STATE_VAR})
            joint = multiply([alpha_prev, self.transition_factor])
            alpha_pred = marginalize(joint, {self.PREV_STATE_VAR})

            emis_t = condition(self.emission_factor, {self.OBS_VAR: o_t})
            emis_t = marginalize(emis_t, {self.OBS_VAR})
            alpha = multiply([alpha_pred, emis_t])
            alpha = self._normalize_factor(alpha)

        return normalize(alpha)

    def _normalize_factor(self, factor: Factor) -> Factor:
        """Normalize Factor table (sum to 1) 防 underflow。"""
        total = sum(factor.table.values())
        if total <= 0:
            return factor
        return Factor(
            variables=list(factor.variables),
            table={k: v / total for k, v in factor.table.items()},
        )

    def predict_with_scores(self, obs_sequence: Sequence[str]) -> tuple:
        """返回 (MAP_state_at_final_time, posterior_dict)."""
        post = self.filter(obs_sequence)
        scores = {s: float(post.prob_of(s)) for s in self.states}
        best = argmax(scores)
        return best, scores

    def reset(self):
        pass
