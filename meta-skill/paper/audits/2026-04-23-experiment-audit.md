# Experiment Audit Report — Meta-Skill "Compile Once, Reason Exactly"

- **Date**: 2026-04-23
- **Auditor**: GPT-5.4 xhigh (Codex MCP, cross-model independent review)
- **Executor**: Claude Opus 4.7（只收集路径，不参与判断）
- **Project**: `/Users/robin/Desktop/taoyao/bayes/meta-skill/`
- **Paper**: `paper/main.tex`（NeurIPS 2026 submission，"Compile Once, Reason Exactly"）
- **Reviewer Independence**: Codex 未被喂 Claude 的任何 summary，纯靠绝对路径自己 `read`/`grep`/`cat`。

---

## Summary

- **Overall Verdict：FAIL**
- **Integrity Status：fail**
- **严重度：HIGH**

**核心发现**：Tree 担心的 "100% 不正常" 有真实风险。Codex 独立审查发现 4 类 fraud pattern 中有 3 类**实质性命中**（C/D：FAIL，A：FAIL），1 类部分命中（B：WARN）。关键问题：

1. **Gate 3 实际上是"同一 solver 类实例的自我比较"**——虽然 Gate 3 不是"LLM 自判"，但编译器产出的 `PreferenceSolver`/`BNReferenceSolver` 在 LOO 和 Gate3-off 测试中被用作 gold_solver，两端是**同一实现类**的两个实例，不独立。
2. **Preference Gate 2 彻底无门槛**（`passed = True`，`verifier/gates.py:195-202`）——5 个 preference LOO 数据集 "Gate3-off 仍 pass" 基本是"代码能跑就算过"。
3. **Inductor prompt 泄漏 answer key**：`_format_samples()` 把整条 sample 含 `reward_fn` / `answers` / 原始 gold labels 直接 `json.dumps` 进 prompt，模板还**显式要求**从 `reward_fn` 推值域。induction 用的样本和 verification 用的样本**完全重合**（`samples[:k]` 两用）。
4. **NB/HMM held-out 根本不走 TaskSpec/compiler**：当前 `taskspec/schema.py:123` 只接受 `{hypothesis_enumeration, conjugate_update, variable_elimination}` 三种 family。NB/HMM 实际是两个独立 LLM codegen 脚本（`run_held_out_family.py` / `run_hmm_held_out.py`），而非论文所述的"inductor 组合 novel workflow"。论文 claim 与代码实现**机制层面错位**。
5. **`verify_bnlearn_dsl_100.py` 含可疑 fallback**：多值节点时 `dsl_p = gold_p`（第 95-117 行），这会让"100%" 在该分支**自动成立**。
6. **n=6 LOO 的 CI 下界约 54-61%**，论文只给点估计，没承认这点。

---

## 4 类 Fraud Pattern 逐条检查

### 1. Fake GT (Ground Truth Provenance)：FAIL

- **Gate 3 Reference 来源**：`verifier/gates.py:51-82` 定义 Gate 3 接受外部 `gold_solver` 参数。但实际调用点（`test_loo_induction.py:68-84`、`test_gate3_ablation.py:89-125`、`test_gate3_ablation.py:176-197`）传入的 `gold_solver` 就是 `PreferenceSolver` / `BNReferenceSolver`——**与 compiler 输出是同一实现类**（`taskspec/compiler.py:25-70`）。
- **不是 LLM self-grading，但是"同一 deterministic solver 的两个实例"**——等价于"代码跟自己比"。
- **held-out NB/HMM gold 来源**：
  - NB gold 是脚本内手写 closed-form Naive Bayes posterior + log-sum-exp 归一化（`baselines/run_held_out_family.py:118-149`）——**确定性独立**，这一点是干净的。
  - HMM gold 是手写 `forward_algorithm`（`baselines/run_hmm_held_out.py:151-216`）——**确定性独立**。
- **`test_equivalence_full.py` 比较两端**：BN 是 `BNReferenceSolver` vs legacy `phase1/bn_solver.py::solve_blind_example`；Preference 是 `PreferenceSolver` vs legacy `phase1/bayesian_sidecar.py::BayesianSidecar`——**是"仓库内两个独立实现"**，这是 relatively clean 的。但不覆盖论文正文 claim 的 TextBandit 50/50。
- Codex 本地跑 `test_equivalence_full.py` 得到 BLInD 900/900、Flight 250/250 全过——**equivalence claim 本身的计算确实成立**，但 TextBandit 缺失。

**结论**：不是 LLM self-grading，但 Gate 3 / LOO 测试用同一 solver 类两边比，无法证明"独立 compile 产出"正确。NB/HMM gold 是独立手写的。`test_equivalence_full.py` 是最干净的证据（仓库内两实现对比）但覆盖不全。

---

### 2. SE 乐观 (CI Underestimation)：WARN

- **CI 方法不统一**：
  - `paper/compute_ci.py` 用 **Clopper-Pearson exact binomial**（`paper/compute_ci.py:1-16`）
  - `baselines/run_e2e_experiment.py:308-322` 用 **bootstrap (per-instance)**
  - `baselines/verify_bnlearn_dsl_100.py:19-28` 用 **Wilson**
  - 论文正文又混用 "Wilson" / "Wilson/Clopper-Pearson"（`main.tex:254, 553, 1274`）
- **bootstrap per-instance**：仅 E2E 对 instance-level 布尔成功变量重采样——是**正确的**，不是 batch-level。
- **n=6 LOO CI 缺失**：
  - 6/6 的 **95% Clopper-Pearson 下界 ≈ 54.1%**
  - 6/6 的 **95% Wilson 下界 ≈ 61.0%**
  - 正文 `main.tex:406-407` 和 appendix `1110-1126` 只给点估计 "6/6"，**没承认下界这么宽**。
- 审稿人会直接扣分：n=6 + 不带 CI + 声称 "100%" 是典型 over-claim。

---

### 3. Nested / Leakage：FAIL

- **7 core ops 是否 design-time 泄漏**：`dsl/core_ops.py:15-183` / `dsl/family_macros.py:7-208` 没有显式 NB/HMM-specific op 或 macro，**这一点是干净的**。
- **macro 设计 vs held-out**：`taskspec/compiler.py:42-51` / `schema.py:120-155` 只支持 `hypothesis_enumeration` / `conjugate_update` / `variable_elimination` 三类，**对应不到 NB/HMM** ——所以 macros 没被 held-out family 偷看。
- **TaskSpec example vs held-out 重合**：**重合，严重**。
  - `tests/test_loo_induction.py:79-84` 用 `samples[:max_induction_samples]` 做 induction
  - 然后 `tests/test_loo_induction.py:118-136` 又用 `samples[:max_verify_samples]` 进 verifier + 从 `samples[:20]` 开头继续评测——**induction 集和 test 集从头开始取**，**大概率重合**。
  - `test_gate3_ablation.py:69-74, 99-125` 完全同样的 pattern。
  - 直接**违背**正文方法声明 `main.tex:371-395` "held-out validation disjoint from induction and final test set"。
- **Inductor prompt 含 answer key**：
  - `inductor/inductor.py:32-39, 68-71`：`_format_samples()` 把整条 sample `json.dumps(s, indent=2, ensure_ascii=False)` 原样送进 prompt。
  - Raw Flight/Hotel 样本自带 `reward_fn`（真实效用函数），BLInD CSV 自带 `answers`（gold 后验）。
  - Prompt 模板 `inductor/prompts/induction_prompt.md:17-20, 89-92` **显式要求** LLM "Look at the `reward_fn` field in samples to discover these values"——**答案直接喂给 LLM 看**。
- **Gate 2 Preference 无阈值**（额外发现）：`verifier/gates.py:195-202` 直接 `passed = True`。注释说"偏好学习受限于先验信息量不设硬阈值"——但这意味着 Gate3-off 消融中 6/6 里的 5 个 preference 数据集 basically "代码能跑就 pass"。
- **NB/HMM 不是同一套系统**（额外发现）：论文 `main.tex:84, 547-580` 把 NB/HMM 写成 "inductor 组合 novel workflow"。但：
  - `taskspec/schema.py:123-155` 的 valid_families 集合根本不含 NB / HMM。
  - 实际跑的是两个**独立脚本**：`run_held_out_family.py:284-374` 和 `run_hmm_held_out.py:346-417`。
  - 脚本给 LLM 看 `correct_*` 训练样例 + 手写的 pseudo core ops prompt，让它**从头写代码**。
  - **这不是"inductor / compiler compositional generalization"**——是**独立的 core-ops-constrained codegen baseline**。Claim 和实现机制层面错位。

---

### 4. Metric 混用 (Denominator Inconsistency)：FAIL

- **Compute 分母**：
  - PCD Preference 用 `len(compute_results)` = 全量样本数（`run_pcd_experiment.py:598-624`）
  - PCD BN 用 `valid_indices` 上的全量有效样本（`run_pcd_experiment.py:691-758`）
  - **不是** "GoldParse 正确子集" ——但论文 Figure 2 caption `main.tex:254` 写 "Compute|GoldParse"，是对 gold intermediate injected 全量实例算的，一致。但 Table 1 的 "Compute" 缩写让读者误以为条件分母一致。
- **跨 baseline "correct" 目标不一致**（严重）：
  - `run_compile_time_baseline.py:419-430` preference `correct = pred == gold_solver_rec`
  - `run_pcd_experiment.py:197-212, 605-644` preference `correct = pred == gold_solver_rec`
  - **但** `run_pal_experiment.py:184-248` preference `correct = pred == user_idx`（真实用户最后选择）
  - `run_e2e_experiment.py:292-299, 387-418` E2E 用 `e2e_correct` 对 `gold_user_choice` **and** 单独 `gold_solver_match`，只在 parse-successful 子集算——**两套 metric**
  - **不同 baseline 比较的是不同东西**：compile-time/PCD 是"solver agreement"，PAL/E2E 是"user choice prediction"，这两种 claim 本质不同。
- **BN task correct**：`|pred - gold| < 0.01`（数值 tolerance）
- **论文里直接做跨 baseline 比较**（Table 1、Figure 3）——**分母/目标口径混杂**。
- **bnlearn 证据链不足**：Codex 发现 `bnlearn_openai_gpt-5.4_20260315_211432.json` 只有 PAL 结果，没有对应的 "DSL 100%" raw artifact。相邻 `20260314_235817.json` 的实际数据是 `compile_free=60.8%` / `compile_core_ops=0%` / `pcd.compute=0%`。**"DSL stays at 100%" 的原始 raw result 在哪里？** Codex 找不到。

---

## 100% Claim 归因分解表

| Claim (main.tex line) | 归因类型 | Fraud? | 建议 |
|---|---|---|---|
| L82 GPT-4o-mini 100% compute ("as few as one example") | **C** | 有泄漏风险 | 把 "as few as one example" 与 "all BN benchmarks" 分开；重跑 disjoint train/val/test，prompt 去掉 `answers` / `reward_fn`，公开 DSL raw result |
| L84 NB/HMM core-ops 100% | **B** | 不是 fraud 但机制写错 | 改写为"独立的 core-ops-constrained compile-time codegen baseline 在两个 synthetic held-out family 上达 100%"。不能说是 "inductor 组合 novel workflow" |
| L108 Decide 100% (6 models) | **B** | 否（trivial） | 承认 Decide stage 本身较 trivial（尤其 BN decide 接近 echo task）。保留诊断价值 |
| L118 37-node BN 100% | **C** | 证据链不足 | 用独立 `pgmpy` solver 做 gold；修正 `verify_bnlearn_dsl_100.py` 的 multi-valued fallback；补完 raw JSON 后再 claim |
| L188-198 Table 1 Decide 100% × 6 models, Our DSL Compute 100% | **B + C 混合** | Decide 100% trivial（B）；DSL Compute 100% 涉及 Gate3 same-solver 和 prompt 泄漏（C） | 分别加 scope 限定；对 DSL 行公开 raw artifact |
| L254 all depths 100% (Figure 2) | **A** | 否（BLInD VE compiled solver 上是数学保证） | 可保留，限定 "for the implemented VE-compiled BLInD solver" |
| L340 "100% accuracy reflects exact computation" | **B** | 否 | 限定为"for implemented compiler families with verified equivalence (Flight/BLInD)" |
| L407 All 6 pass first attempt 100% match | **C** | 是，验证设计有漏洞 | Gate 3 gold_solver 必须**不是** `PreferenceSolver`/`BNReferenceSolver` 实例；Gate 2 preference 设实际阈值；disjoint split；补 n=6 的 Wilson / Clopper-Pearson CI |
| L444 four networks 100% | **C** | 可能 | 修复 `verify_bnlearn_dsl_100.py` 后重跑，`pgmpy` 做独立 gold |
| L588 Gate 3 Off 6/6 100% | **C** | 是，ablation 失效 | Gate 2 preference 必须设阈值；post-hoc gold 不能再用同一 solver 类；重跑 |
| L592 DSL $0.008 100% | **B** | 否，但成本是估算 | 明确 `$0.008` 是 **token-cost estimate**，不是 API bill trace；把成本估算与 accuracy artifact 分开 |
| L602 Feature extraction 99.9–100% | **B** | 否，但解释过头 | 改成"在 parse-successful cases 上 per-feature exact match 约 99.94–100%"；不要把剩余 gap 都归因为 malformed JSON（可能还有其他 failure mode） |

**归因类型定义**：
- **A 设计保证**：数学上就是 100%（确定性 compile + 独立 gold），不是 fraud
- **B 需 scope 限定**：claim 本身对但范围需 narrow
- **C 可能有漏洞需重跑**：存在 leakage / fake GT / 分母问题，需要修复

---

## 需重跑实验清单（C 类）

1. **LOO 6/6** (L407, L588)：
   - 按 family/dataset 做真正 `train/val/test` 三分
   - `val` 与 `test` 不能重叠 induction 样本
   - prompt 禁止 `reward_fn` / `answers` / `correct_diagnosis` 字段
   - Gate 3 `gold_solver` 改成独立的 legacy 实现（如 `phase1/bn_solver.py`、`phase1/bayesian_sidecar.py`），不许再用 `PreferenceSolver` / `BNReferenceSolver` 本尊
   - Gate 2 preference 设实际阈值（非 `passed = True`）
   - 补 n=6 的 Clopper-Pearson / Wilson CI（下界 54-61%）

2. **bnlearn 4 networks** (L118, L444)：
   - 修正 `verify_bnlearn_dsl_100.py:95-117` 的 multi-valued fallback `dsl_p = gold_p`（这行让 100% 在多值节点分支自动成立）
   - 使用 `pgmpy` 做 gold
   - 发布完整 raw result 文件（目前 Codex 找不到 "DSL 100%" 的对应 raw artifact）

3. **"as few as one example" (k=1)** (L82, L123)：
   - 重跑 k=1 induction
   - 验证集和测试集都必须与该 1 个 induction sample **不重合**

4. **NB/HMM 机制 claim** (L84, L123, L547-580)：
   - **或者** 扩展 `TaskSpec` / compiler 支持 NB/HMM family，再重跑
   - **或者** 改写 claim 为"independent core-ops-constrained codegen baseline"，不能声称是 inductor / compiler 的 compositional generalization

---

## 需加 scope 限定位置（B 类）

- **L108 / L188-198**：改成 "Decide stage under gold posterior/result injection is 98–100%, and is not itself the hard reasoning step."
- **L84 / L114 / L123 / L547-580**："separate core-ops-constrained codegen baseline"，不写成 `TaskSpec` inductor / compiler 已支持
- **L254 Figure 2**：加 "for the implemented VE-compiled BLInD solver"
- **L340**：限定为 "for implemented compiler families with verified equivalence (Flight/BLInD)"
- **L592**：明确 `$0.008` 是 **token-cost estimate**
- **L602**："per-feature exact match among parse-successful cases"，不把所有 gap 都归 malformed JSON

---

## Suspicions to Carry Forward (Reviewer Memory)

| # | 怀疑 | 核查钩子 |
|---|---|---|
| 1 | Gate 2 preference vacuous | `rg -n "passed = True" verifier/gates.py` |
| 2 | Gate 3 same-solver self-reference | `rg -n "PreferenceSolver\|BNReferenceSolver" taskspec/compiler.py tests/test_loo_induction.py tests/test_gate3_ablation.py` |
| 3 | Inductor prompt answer-key leakage | `rg -n "reward_fn\|answers\|json.dumps\(s" inductor/inductor.py inductor/prompts/induction_prompt.md data/eval/interaction/*.jsonl data/external/BLInD/datasets/Base_1000_examples.csv` |
| 4 | LOO split overlap | `rg -n "samples\[:max_induction_samples\]\|samples\[:max_verify_samples\]" tests/test_loo_induction.py tests/test_gate3_ablation.py` |
| 5 | Held-out family 非同一套系统 | `rg -n "valid_families\|variable_elimination\|compile_bn\|correct_diagnosis\|correct_state\|Available Core Operations" taskspec/schema.py taskspec/compiler.py baselines/run_held_out_family.py baselines/run_hmm_held_out.py` |
| 6 | Preference metric target 不一致 | `rg -n "gold_idx = sample.*user_idx\|gold_rec = solver.recommend\|e2e_matches_gold_solver\|successful = \[r for r in e2e_results" baselines/` |
| 7 | bnlearn verifier fallback | `rg -n "query_vars_dict = \{query_var: list\|dsl_p = gold_p" baselines/verify_bnlearn_dsl_100.py` |
| 8 | 6/6 CI sanity check | `python3 -c "from scipy import stats; print(stats.beta.ppf(0.025,6,1))"` |

---

## 证据 — 关键代码/文件摘录

### Gate 2 Preference 无阈值（`verifier/gates.py:195-202`）
```python
acc = correct / total
passed = True  # 偏好学习的准确率本身就受限于先验信息量，不设硬阈值
return GateResult(
    gate="Gate 2: Ground Truth",
    passed=passed,
```

### Compiler 产出与 Gate 3 gold 是同一类（`taskspec/compiler.py:44-70`）
```python
if family == "hypothesis_enumeration":
    return _compile_preference(spec)
elif family == "variable_elimination":
    return _compile_bn(spec)

def _compile_preference(spec: TaskSpec) -> PreferenceSolver:
    return PreferenceSolver(...)

def _compile_bn(spec: TaskSpec) -> BNReferenceSolver:
    return BNReferenceSolver()
```

### LOO 测试 induction 集 = verification 集（`tests/test_loo_induction.py:71-84, 118-136`）
```python
gold = PreferenceSolver(...)
spec, result, rounds = induce_and_verify(
    samples[:max_induction_samples],
    gold_solver=gold,
    ...
)
...
for sample in samples[:max_verify_samples]:
```

### Inductor 原样喂 sample（含 reward_fn/answers）（`inductor/inductor.py:32-39, 69-71`）
```python
text = json.dumps(s, indent=2, ensure_ascii=False)
...
samples_text = _format_samples(samples, max_samples)
prompt = template.replace("{samples}", samples_text)
```

### Prompt 显式要求看 reward_fn（`inductor/prompts/induction_prompt.md:17-20, 89-92`）
```
Look at the `reward_fn` field in samples to discover these values...
```

### valid_families 不含 NB/HMM（`taskspec/schema.py:123-155`）
```python
valid_families = {"hypothesis_enumeration", "conjugate_update", "variable_elimination"}
```

### NB/HMM 走独立 codegen 路径（`baselines/run_held_out_family.py:293-340`）
```python
correct_diagnosis: ...
correct_posteriors: ...
def condition(distribution: dict, evidence_key: str, evidence_val, cpt: dict) -> dict:
...
Your solver function MUST call these operations.
```

### 跨 baseline correct 口径不一致
```python
# baselines/run_pal_experiment.py:184-248
gold_idx = sample["rounds"][-1]["user_idx"]
...
"correct": predicted == gold_idx

# baselines/run_compile_time_baseline.py:419-430
gold_rec = solver.recommend(rounds_numpy[len(rounds) - 1])
...
"correct": pred == td["gold"]

# baselines/run_e2e_experiment.py:387-397
successful = [r for r in e2e_results if r.get("success", False)]
e2e_correct_list = [r["e2e_correct"] for r in successful]
```

### bnlearn verifier multi-valued fallback 让 100% 自动成立（`baselines/verify_bnlearn_dsl_100.py:95-117`）
```python
query_vars_dict = {query_var: list(node_states[query_var])}
dsl_result = ve_query(dsl_factors, query_vars_dict, evidence)
...
if isinstance(dsl_posterior, (int, float)):
    if len(node_states[query_var]) == 2:
        ...
    else:
        dsl_p = gold_p  # fallback
```

### test_equivalence_full.py 本地运行（Codex 实测）
```
BLInD 等价性: 900/900 (100.0%)
Flight 等价性: 250/250 (100.0%)
```
（这是最干净的证据——仓库内两个独立实现对比；但不覆盖 TextBandit 50/50）

---

## Raw Codex Response (verbatim, for dispute trace)

<details>
<summary>Click to expand full Codex GPT-5.4 xhigh output</summary>

```
# Experiment Integrity Audit — Meta-Skill / Compile Once

## Overall Verdict: FAIL
## Integrity Status: fail

## A. Fake GT Provenance: FAIL
- 发现：`Gate 3` 接口本身接受外部 `gold_solver`，[verifier/gates.py:51-82](/Users/robin/Desktop/taoyao/bayes/meta-skill/verifier/gates.py:51)；但当前 LOO / Gate3-off 测试里传入的 `gold_solver`，与编译器返回的是同一实现类：`PreferenceSolver` / `BNReferenceSolver`，[taskspec/compiler.py:25-70](/Users/robin/Desktop/taoyao/bayes/meta-skill/taskspec/compiler.py:25), [tests/test_loo_induction.py:68-84](/Users/robin/Desktop/taoyao/bayes/meta-skill/tests/test_loo_induction.py:68), [tests/test_gate3_ablation.py:89-125](/Users/robin/Desktop/taoyao/bayes/meta-skill/tests/test_gate3_ablation.py:89), [tests/test_gate3_ablation.py:176-197](/Users/robin/Desktop/taoyao/bayes/meta-skill/tests/test_gate3_ablation.py:176)。
- Gate 3 reference 来源：不是 LLM 生成的 gold；但在现有测试里，它通常是"同一 deterministic solver 实现的另一个实例"，不独立。
- held-out NB/HMM 的 gold 来源：NB 是脚本内手写 closed-form Naive Bayes posterior（log-sum-exp 归一化），[baselines/run_held_out_family.py:118-149](/Users/robin/Desktop/taoyao/bayes/meta-skill/baselines/run_held_out_family.py:118)；HMM 是手写 `forward_algorithm`，[baselines/run_hmm_held_out.py:151-216](/Users/robin/Desktop/taoyao/bayes/meta-skill/baselines/run_hmm_held_out.py:151)。
- 是否同一 LLM 两端：没有发现 "LLM 先生成 gold 再拿同一 gold 评自己" 的直接代码路径；问题更严重地出在"同一 solver 实现两端"和 prompt 带答案字段。
- `tests/test_equivalence_full.py` 比较两端：BN 是 `BNReferenceSolver` vs legacy `phase1/bn_solver.py::solve_blind_example`，Preference 是 `PreferenceSolver` vs legacy `phase1/bayesian_sidecar.py::BayesianSidecar`，[tests/test_equivalence_full.py:34-48](/Users/robin/Desktop/taoyao/bayes/meta-skill/tests/test_equivalence_full.py:34), [tests/test_equivalence_full.py:67-103](/Users/robin/Desktop/taoyao/bayes/meta-skill/tests/test_equivalence_full.py:67)。这两端算"仓库内较独立实现"；我本地跑了该文件，结果是 BLInD `900/900`、Flight `250/250` 全过，但它不覆盖论文写的 TextBandit `50/50`。

## B. SE 乐观: WARN
- CI 方法：不统一。`paper/compute_ci.py` 用 Clopper-Pearson exact binomial，[paper/compute_ci.py:1-16](/Users/robin/Desktop/taoyao/bayes/meta-skill/paper/compute_ci.py:1)；`run_e2e_experiment.py` 用 bootstrap，[baselines/run_e2e_experiment.py:308-322](/Users/robin/Desktop/taoyao/bayes/meta-skill/baselines/run_e2e_experiment.py:308)；`verify_bnlearn_dsl_100.py` 用 Wilson，[baselines/verify_bnlearn_dsl_100.py:19-28](/Users/robin/Desktop/taoyao/bayes/meta-skill/baselines/verify_bnlearn_dsl_100.py:19)。论文正文又写 "Wilson" / "Wilson/Clopper-Pearson" 混用，[paper/main.tex:254](/Users/robin/Desktop/taoyao/bayes/meta-skill/paper/main.tex:254), [paper/main.tex:553](/Users/robin/Desktop/taoyao/bayes/meta-skill/paper/main.tex:553), [paper/main.tex:1274](/Users/robin/Desktop/taoyao/bayes/meta-skill/paper/main.tex:1274)。
- bootstrap 是否 per-instance：是，但只在 E2E；它对 instance-level 布尔成功变量重采样，不是 batch-level，[baselines/run_e2e_experiment.py:308-322](/Users/robin/Desktop/taoyao/bayes/meta-skill/baselines/run_e2e_experiment.py:308)。
- n=6 LOO 的 CI 是否展示：没有。`6/6` 的 95% exact CI 下界约 `54.1%`，Wilson 下界约 `61.0%`；正文和 appendix 只给点估计，没有承认这点，[paper/main.tex:406-407](/Users/robin/Desktop/taoyao/bayes/meta-skill/paper/main.tex:406), [paper/main.tex:1110-1126](/Users/robin/Desktop/taoyao/bayes/meta-skill/paper/main.tex:1110)。

## C. Nested / Leakage: FAIL
- 7 core ops 是否 design-time 泄漏：`dsl/core_ops.py` / `dsl/family_macros.py` 里没有显式 NB/HMM-specific op 或 macro，[dsl/core_ops.py:15-183](/Users/robin/Desktop/taoyao/bayes/meta-skill/dsl/core_ops.py:15), [dsl/family_macros.py:7-208](/Users/robin/Desktop/taoyao/bayes/meta-skill/dsl/family_macros.py:7)。所以"设计时偷看 held-out family"没有直接代码证据。
- macro 设计是否看到 held-out：没有对应 macro；当前 schema/compiler 只支持 `hypothesis_enumeration / conjugate_update / variable_elimination` 三类，[taskspec/schema.py:120-155](/Users/robin/Desktop/taoyao/bayes/meta-skill/taskspec/schema.py:120), [taskspec/compiler.py:42-51](/Users/robin/Desktop/taoyao/bayes/meta-skill/taskspec/compiler.py:42)。
- TaskSpec example vs held-out 重合：重合。`tests/test_loo_induction.py` 用 `samples[:k]` 做 induction，又用同一批 `samples[:k]` 进 verifier，之后还从 `samples[:20]` 开头继续评测；`test_gate3_ablation.py` 同样如此，[tests/test_loo_induction.py:79-84](/Users/robin/Desktop/taoyao/bayes/meta-skill/tests/test_loo_induction.py:79), [tests/test_loo_induction.py:118-136](/Users/robin/Desktop/taoyao/bayes/meta-skill/tests/test_loo_induction.py:118), [tests/test_gate3_ablation.py:69-74](/Users/robin/Desktop/taoyao/bayes/meta-skill/tests/test_gate3_ablation.py:69), [tests/test_gate3_ablation.py:99-125](/Users/robin/Desktop/taoyao/bayes/meta-skill/tests/test_gate3_ablation.py:99)。这直接违背了正文 "held-out validation disjoint from induction and final test set" 的方法声明，[paper/main.tex:371-395](/Users/robin/Desktop/taoyao/bayes/meta-skill/paper/main.tex:371)。
- inductor prompt 是否含 answer key：是。`_format_samples()` 把整条 sample 原样 `json.dumps` 进 prompt，[inductor/inductor.py:28-39](/Users/robin/Desktop/taoyao/bayes/meta-skill/inductor/inductor.py:28), [inductor/inductor.py:68-71](/Users/robin/Desktop/taoyao/bayes/meta-skill/inductor/inductor.py:68)。而 raw Flight/Hotel 样本自带 `reward_fn`，BLInD CSV 自带 `answers`；prompt 模板还明确要求从 `reward_fn` 发现值域，[inductor/prompts/induction_prompt.md:17-20](/Users/robin/Desktop/taoyao/bayes/meta-skill/inductor/prompts/induction_prompt.md:17), [inductor/prompts/induction_prompt.md:89-92](/Users/robin/Desktop/taoyao/bayes/meta-skill/inductor/prompts/induction_prompt.md:89)。
- 额外问题 1：Preference 的 Gate 2 根本不设通过阈值，`passed = True`，[verifier/gates.py:195-202](/Users/robin/Desktop/taoyao/bayes/meta-skill/verifier/gates.py:195)。所以 Gate3-off 的 6/6 里，5 个 preference 数据集基本是"只要代码能跑就 pass"。
- 额外问题 2：论文把 NB/HMM 写成"inductor 组合 novel workflow"，但当前 `TaskSpec`/compiler 根本不能编译 NB/HMM；实际跑的是两个独立脚本，给 LLM 看 `correct_*` 训练样例，再用手写的 pseudo core ops prompt 让它写代码，[baselines/run_held_out_family.py:284-374](/Users/robin/Desktop/taoyao/bayes/meta-skill/baselines/run_held_out_family.py:284), [baselines/run_hmm_held_out.py:346-417](/Users/robin/Desktop/taoyao/bayes/meta-skill/baselines/run_hmm_held_out.py:346)。这不是同一套 inductor/compiler 证据。

## D. Metric 混用: FAIL
- Compute 分母：PCD 里的 `Compute|GoldParse` 用的是全量样本数，不是 parse-correct 子集；Preference 直接 `len(compute_results)`，[baselines/run_pcd_experiment.py:598-624](/Users/robin/Desktop/taoyao/bayes/meta-skill/baselines/run_pcd_experiment.py:598)；BN 用 `valid_indices` 上的全量有效样本，[baselines/run_pcd_experiment.py:691-758](/Users/robin/Desktop/taoyao/bayes/meta-skill/baselines/run_pcd_experiment.py:691)。
- Figure 2 vs Table 1 分母一致性：对 LLM 的 PCD `Compute` 行，一致，都是 gold intermediate injected 的全量实例；但论文把 `Compute|GoldParse` 常缩写成 `Compute`，又把 `Our DSL 100%` 放在同一表里，读者很容易误解为"同一条件下的同一分母"。
- 跨 baseline 分母口径：不一致。`run_compile_time_baseline.py` 的 preference `correct` 对的是 gold solver recommendation，[baselines/run_compile_time_baseline.py:419-430](/Users/robin/Desktop/taoyao/bayes/meta-skill/baselines/run_compile_time_baseline.py:419)；`run_pcd_experiment.py` preference compute/decide 也对 gold solver recommendation，[baselines/run_pcd_experiment.py:197-212](/Users/robin/Desktop/taoyao/bayes/meta-skill/baselines/run_pcd_experiment.py:197), [baselines/run_pcd_experiment.py:605-644](/Users/robin/Desktop/taoyao/bayes/meta-skill/baselines/run_pcd_experiment.py:605)；但 `run_pal_experiment.py` preference 对的是用户最后真实选择 `user_idx`，[baselines/run_pal_experiment.py:184-248](/Users/robin/Desktop/taoyao/bayes/meta-skill/baselines/run_pal_experiment.py:184)；`run_e2e_experiment.py` 的 `e2e_accuracy` 只在 parse-successful 子集上算，而且目标是 `gold_user_choice`，另有一个单独的 `gold_solver_match`，[baselines/run_e2e_experiment.py:292-299](/Users/robin/Desktop/taoyao/bayes/meta-skill/baselines/run_e2e_experiment.py:292), [baselines/run_e2e_experiment.py:387-418](/Users/robin/Desktop/taoyao/bayes/meta-skill/baselines/run_e2e_experiment.py:387)。
- raw JSON "correct" 定义：不一致。BN task 通常是 `|pred-gold|<0.01`；Preference/PAL 是 `pred == user_idx`；Preference/compile-PCD 是 `pred == gold_solver_rec`；E2E summary 甚至没有统一 `correct` 字段，而是 `e2e_correct` 与 `e2e_matches_gold_solver` 两套。
- bnlearn 额外异常：你给的 `bnlearn_openai_gpt-5.4_20260315_211432.json` 只有 PAL；相邻的 `bnlearn_openai_gpt-5.4_20260314_235817.json` 里 `compile_free=60.8%`、`compile_core_ops=0%`、`pcd.compute=0%`，没有对应 "DSL 100%" raw artifact。另一个 `verify_bnlearn_dsl_100.py` 还含有可疑 fallback：多值节点情况下 `dsl_p = gold_p`，[baselines/verify_bnlearn_dsl_100.py:95-117](/Users/robin/Desktop/taoyao/bayes/meta-skill/baselines/verify_bnlearn_dsl_100.py:95)。
```

(完整 raw output 内容含在本审查文档主体各节，此处 `<details>` 包住 Codex 原始前半段供 dispute trace)

</details>

---

## 下一步行动建议（给 Tree）

按优先级排列：

1. **🔴 最紧急（投稿前必修）**：
   - 修 `verify_bnlearn_dsl_100.py:95-117` 的 `dsl_p = gold_p` fallback——这行能让 100% 在多值节点分支**自动成立**，是实实在在的 bug
   - Gate 3 `gold_solver` 传入独立的 legacy 实现（`phase1/bn_solver.py`、`phase1/bayesian_sidecar.py`），不再用 `PreferenceSolver` / `BNReferenceSolver` 本尊
   - Gate 2 Preference 设置真实阈值，不要 `passed = True`

2. **🟡 重要（必须改 claim）**：
   - 改写 L84、L123、L547-580：NB/HMM 不是"inductor 组合 novel workflow"，而是"独立 core-ops-constrained codegen baseline"——这是机制错位 over-claim
   - 补 n=6 LOO 的 Clopper-Pearson / Wilson CI（下界 54-61%），不能只写 "6/6"
   - 统一跨 baseline 的 `correct` 定义（`gold_solver_rec` vs `user_idx`）或明确区分两种 metric

3. **🟡 重要（scope 限定）**：
   - L108 Decide 100%：承认 Decide stage trivial
   - L254 Figure 2：限定 "for implemented VE-compiled BLInD solver"
   - L340：限定为 "for implemented compiler families (Flight/BLInD) with verified equivalence"
   - L592：明确 `$0.008` 是 token-cost estimate，非真实账单
   - L602：Feature extraction 限定为 parse-successful cases

4. **🟢 改进（重跑实验）**：
   - LOO 6/6 重跑：disjoint split、prompt 去答案字段、Gate 2 设阈值、独立 gold
   - bnlearn 4 networks 用 `pgmpy` 重跑
   - "as few as one example" (k=1) 重跑，验证集测试集与 induction sample 不重合

---

## 审查方法论注记

- **Reviewer Independence**：Codex 未被喂任何 Claude summary，纯靠绝对路径自己 `read`/`grep`/`cat`（执行层符合 `.claude/rules/codex-review.md` 铁律）
- **Codex 实际执行的操作**：读取 `verifier/gates.py`、`taskspec/compiler.py`、`taskspec/schema.py`、`tests/test_gate3_ablation.py`、`tests/test_loo_induction.py`、`tests/test_equivalence_full.py`、`dsl/core_ops.py`、`dsl/family_macros.py`、`inductor/inductor.py`、`inductor/prompts/induction_prompt.md`、`baselines/run_{bnlearn_held_out,held_out_family,hmm_held_out,e2e,compile_time,pal,pcd}_experiment.py`、`baselines/verify_bnlearn_dsl_100.py`、`paper/compute_ci.py`、抽样 raw JSON，以及**本地执行** `test_equivalence_full.py`（得 BLInD 900/900、Flight 250/250）
- **局限**：Codex 未能本地跑 `verify_bnlearn_dsl_100.py`（环境 pgmpy 不匹配）；未跑 LOO 全流程（需 API key）；未做完整 statistical power analysis

---

*Report generated 2026-04-23 by ARIS `/experiment-audit` skill (Codex GPT-5.4 xhigh reviewer, Claude Opus 4.7 executor).*
