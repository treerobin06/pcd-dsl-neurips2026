# Codex Review Report — 2026-04-28 战略层（Plan + Paper + Code）

**审查类型**: D + C + E2（Plan + Paper post-pivot + Code with research context）
**审查重点**: Tree 4 问 — (1) 下一步进度方向是否正确；(2) 论文现状是否合理；(3) 今天 15 commits framing pivot 是否合理；(4) 还有哪些必须做的
**Codex MCP**: `gpt-5.5` xhigh, sandbox `danger-full-access`, approval `never`
**git HEAD**: `33160306` (branch `review/2026-04-23-audit-findings`)
**前置 baseline**: 2026-04-23 Codex review 三轮持续下降 5→4.5→4/10，3 条 CRITICAL 未解（C3 身份危机 / artifact discipline / C5+C6+S2 代码层零动作）

---

## Round 1 — 2026-04-28T19:02 UTC

**Codex threadId**: `019dd047-aa69-79d1-a8b1-f56a028a1172` (Reviewer Memory 用)

### 评分

**paper-quality 7 维**（每项 / 平均）:

| 维度 | Codex |
|---|:-:|
| framing-clarity | 5/10 |
| evidence-strength | 4/10 |
| narrative-coherence | 5/10 |
| novelty-articulation | 5/10 |
| related-work-positioning | 6/10 |
| claim-data-fit | 3/10 |
| reproducibility | 4/10 |
| **Average** | **4.6/10** |

**plan-soundness 5 维**:

| 维度 | Codex |
|---|:-:|
| completeness | 6/10 |
| prioritization | 7/10 |
| cost-benefit | 4/10 |
| risk-awareness | 6/10 |
| executability | 5/10 |
| **Average** | **5.6/10** |

**对比 baseline**: paper-quality 4.6（持平 04-23 round 3 的 4.0）；plan-soundness 5.6（首次评分，无 baseline）

---

### 问题列表（debated 后最终判定）

| # | 严重度 | 问题 | path:line evidence | Claude 判定 | 处置 |
|:-:|---|---|---|---|---|
| 1 | **CRITICAL** → **MAJOR**（debate 后降）| 论文 abstract `main.tex:82` "reaches 100% across all five tested inference families" 没"given structured spec input" 限定，仍读作 NL E2E。Held-out table caption L551 已 scoped 为 "spec-emission + deterministic-compile route" — 这部分诚实。**残留问题：abstract 没同步缩窄 + Table 3 caption 写 n=200/n=100 但今天唯一 auditable 100% 是 n=50/n=50** | `paper/main.tex:82`, `:551`, `:553-558`; `baselines/results/declarative_spec_route_paper_n50_async_*.json:7-9` n=50/50 | AGREE | abstract 加 "given structured spec input"; Table 3 caption n 改 50/50 或重跑 200/100 |
| 2 | **CRITICAL** → **MAJOR**（debate 后降）| NB 真实泛化未捍卫。Difficulty-var hard config = 18/50=36%，medium = 25/50=50%（**commit msg `6fb5b05` 写 27/50=54% 不一致**）。这些数字尚未进 paper（`rg "nb_medium\|54%" paper/main.tex` 无命中）— 但若进 paper 必须用 raw 真实值，且需要在 paper 显示这个 graceful degradation | `baselines/results/declarative_spec_route_nb_medium_*.json:7-10` (n=50, correct=25); `baselines/results/declarative_spec_route_paper_n50_difficulty_var_*.json` (NB hard 18/50) | AGREE | medium 数字必须 25/50=50% 不是 commit msg 的 54%；进 paper 时显示 graceful degradation 是好事而非掩盖 |
| 3 | **CRITICAL** | Artifact discipline **基础设施已存在但未 enforced**。`baselines/_artifact_schema.py:39-47, 95-150` 已实现 REQUIRED_META_FIELDS 校验，但今天所有 5 个 mandatory raw JSON（n50 async / difficulty_var / nb_medium / 2× bnlearn）**全部 fail validation — 缺整个 _meta 块**。Codex 04-23 的 C9 在 04-28 无新进展 | `baselines/_artifact_schema.py:39-47`; 5 个 result JSON `top keys` 无 `_meta` | AGREE | 所有新 run 必须经 `save_artifact()` 写入；现有 5 个 JSON 重生成或在 paper 标注 "evidence not yet schema-enforced" |
| 4 | **CRITICAL** | NB / HMM 不被 verifier gates.py 支持 — 今天新加 family 的"verified" framing**不覆盖**`gates.py:147,156` 的 `_gate2_ground_truth` 没有 naive_bayes / hmm_forward 分支（dispatch 只有 hypothesis_enumeration / conjugate_update / variable_elimination） | `verifier/gates.py:147-158` | AGREE | 加 `_gate2_nb` 和 `_gate2_hmm` 用 hand-gold sanity test |
| 5 | **MAJOR** | C3 身份危机**仅部分修复**。`compiler.py:82-99` 不再字面 `return BNReferenceSolver()`，而是把 `bn_inference_method/input_format/numerical_precision` 传进去 — 但**结构仍住在 parser/solver 而非 spec**；不同 BN spec 编出的 solver 大部分逻辑相同。从"零参与"到"3 个配置参数"是改进，不是完全修复 | `taskspec/compiler.py:82-99`, `solvers/bn_solver.py:70` | AGREE | reviewer 30 秒攻击 vector 仍在；要么真重构（2-4 天），要么 abstract 显式承认是 "verified deterministic backend with family-level dispatch" |
| 6 | **MAJOR** | Paper 内部 PAL 数字 contradictory。L440 "PAL drops to 0-3% for all $\geq$20-node networks"; 但 L1008 appendix Table 同一指标 "Overall 17.5% / 23.3%"。L991 又说 "PAL 15% overall"。**3 处不同位置 3 套数字**（来自不同 run JSON 还是叙述偷换？） | `main.tex:440`, `:991`, `:1008` | AGREE | 必须统一到一次 raw run 的数字；rg "PAL drops\|17.5\|15%\|23.3" 现在 4+ 处冲突 |
| 7 | **MAJOR** | TaskSpec serialization 与 pivot 不一致。`schema.py:91-120` 的 `to_dict()` 只 dump BN family 的 3 个字段，**漏 NB 6 字段 + HMM 5 字段**；preference / bandit 序列化也带 BN-only 字段污染。`tests/test_compiler::test_roundtrip` 当前 fail | `taskspec/schema.py:91-120`, `tests/test_compiler.py:186` (assert fail) | AGREE — 但 changelog 5.x 已记 P2 待修；Codex 坚持 reviewer-risk 不因 documentation 降低 | 投稿前必修；schema by-family 过滤或 family-specific subclass |
| 8 | **MAJOR** | Abstract / Intro 仍 oversell vs 可 audit 数据。"five families / 100% / over 1,150 instances" — NB+HMM evidence = structured-route n=50+50；NL E2E pending；1,150 是 BLInD 900 + Flight 250（CLAUDE.md 已认错"approximate"应改 1,150 — 这个**已修了**） | `main.tex:75`, `:112`, `:117`; result JSON nb.n=50 vs paper n=200 | AGREE | abstract 必须区分"component-level structured-input route" vs "NL E2E full pipeline" |
| 9 | **MAJOR** | Cost claim 不可 audit，正文/附录两套不一致 — `\$0.008/14×/310×` (main) vs `\$0.001/60×/2500×` (appendix)。raw artifact **无 token/cost metadata**（5 个 JSON 全无 `_meta`），所有 cost 数字都没 source-of-truth | `main.tex:83`, `:1131`; raw JSON missing `_meta.usage` | AGREE | enforce `_meta.prompt_tokens/completion_tokens/total_cost_usd` 后才能讨论 cost claim 怎么写 |
| 10 | **MAJOR** | P0+P1+P2 plan 对 "general probabilistic reasoning agent" claim 不充分。**显式排除**: Level 3 non-Bayesian rejection (GSM8K/MMLU)、Level 4 macro reuse vs compose、cross-model E2E。即便 P0+P1+P2 全部 80% 跑出，"general agent" 的攻击面仍未防 | `~/.claude/plans/mossy-beaming-sky.md:268-275` Out of Scope | AGREE | 至少加 rejection 测试（10 GSM8K / 10 MMLU 看是否拒绝转 spec）+ macro-compose-vs-route 区分 + 1 个非 mini 鲁棒性 sweep |
| 11 | **MINOR** | NB solver 真用 DSL ops，但 `predict()` bypass DSL `argmax`（直接用 `Distribution.map_value()`）；只有 `predict_with_scores()` 用 `argmax()`。HMM 大部分用 DSL ops，但 `_normalize_factor()` 是手写归一化（`hmm_solver.py:136-144`） | `solvers/nb_solver.py:124-126`, `:171-179`; `solvers/hmm_solver.py:121, 132, 136-144` | AGREE | 加 `tests/test_nb_hmm_core_ops.py` 含 hand-gold 验证 + op-trace assertion |
| 12 | **SUGGESTION** | Self-evolving registry 是诚实标 future work / 不连主流程。`dsl/macros_library.py` + `dsl/macros/*.py` 仅作为 vision sketch，paper L703 也写"future work" — **OK as-is** | `dsl/macros_library.py:1`, `main.tex:703-706` | AGREE | 保持 limitations / future work；不要再扩 claim |

**严重度分布**: CRITICAL 2 / MAJOR 8 / MINOR 1 / SUGGESTION 1（debate 前 CRITICAL 4 / MAJOR 6 / MINOR 1 / SUGGESTION 1）

---

### 辩论记录

<details><summary>分歧 #1: NB medium 27/50 vs 25/50 严重度</summary>

**Codex Round 1 原文**:
> CRITICAL: NB generalization is not defended. The paper says solvers handle varying feature counts, but today's difficulty run collapses to 18/50 and medium file is 25/50, **not the commit/message 27/50**.

**Claude 反驳**: nb_medium 数字尚未进 paper（`rg "nb_medium\|54%" paper/main.tex` 无命中），是否应降级到 MAJOR。

**Codex 回复（PARTIAL，撤一半）**:
> PARTIAL — downgrade that specific point to MAJOR. `nb_medium` is not in `paper/main.tex`. So the right finding is: raw evidence contradicts commit-log narrative; paper must not import 54%.
> Separate concern remains: paper claims NB n=200, 3-6 diseases, 4-8 symptoms at `main.tex:544-555`, while today's auditable 100% raw artifact is only n=50.

**结果**: 严重度 MAJOR；新增子点 — Table 3 的 n=200 vs raw n=50 是独立的 claim-data 不匹配，必须 reconcile

</details>

<details><summary>分歧 #2: Held-out 100% framing 是否真的 inflate</summary>

**Codex Round 1 原文**: CRITICAL — 100% framing inflates structured-input component success into broad "framework 100%"

**Claude 反驳**: L551 caption 已经显式 "spec-emission + deterministic-compile route"，是 scope-aware；abstract L82 也说 "with our framework"。是否应区分"caption 已 scoped" vs "abstract 仍 broad"？

**Codex 回复（PARTIAL，部分撤）**:
> PARTIAL — I withdraw the claim that the held-out table caption hides the route. `main.tex:551` is explicitly scoped.
> The remaining issue is narrower: abstract `main.tex:82` still says "reaches 100% across all five tested inference families" broadly, and the table's n=200/n=100 claim is not supported by the mandatory n=50/n=50 raw file. Downgrade from broad CRITICAL to MAJOR.

**结果**: 严重度 MAJOR；具体行动 — abstract 必须加 "given structured spec input" 限定 + Table 3 caption n 必须对齐 raw

</details>

<details><summary>分歧 #3: artifact discipline 严重度</summary>

**Codex Round 1 原文**: CRITICAL — Artifact discipline still broken

**Claude 反驳**: `_artifact_schema.py` 已经存在并实现 `REQUIRED_META_FIELDS` 校验，是"基础设施已建好但未 migration"，是否应改 phrasing？

**Codex 回复（PARTIAL，phrasing 改但严重度不变）**:
> PARTIAL — phrasing update, severity unchanged. The correct finding is "infrastructure exists but is not enforced/migrated." I still rate it CRITICAL for submission evidence because all five mandatory raw JSONs currently fail validation.

**结果**: 严重度 CRITICAL 维持；phrasing 改"基础设施未 enforced"

</details>

<details><summary>分歧 #4: test_roundtrip 已被 changelog 记录是否降 MINOR</summary>

**Codex Round 1 原文**: MAJOR — TaskSpec serialization 与 pivot 不一致

**Claude 反驳**: changelog 5.x 已记为 P2 Open Question，Tree 已知；是否降 MINOR？

**Codex 回复（STILL DISAGREE）**:
> STILL DISAGREE on downgrading to MINOR for submission. Yes, Tree already documents it. But because the paper leans on TaskSpec as a clean typed interface, a broken roundtrip/schema side effect remains MAJOR until fixed. Documentation lowers surprise, not reviewer risk.

**结果**: 严重度 MAJOR 维持 — 投稿前必修

</details>

---

### 04-23 baseline → 04-28 解决度

| 04-23 Critical | 状态 | 证据 |
|---|---|---|
| C3 身份危机 (compile = routing) | **PARTIAL FIX** | `compiler.py:82-99` 加 3 个 BN 配置字段；spec 真参与编译 — 但结构主体仍住 parser/solver。攻击 vector 30 秒仍可下 |
| C5 answer leakage | **MOSTLY RESOLVED**（main path）| `inductor/refiner.py::_scrub_sample()` 已删 reward_fn/answers/correct_*。Legacy baselines 脚本仍未 audit |
| C6 train/verify overlap | **PARTIAL** | `verify_samples` 路径存在；但 fallback 仍 reuse samples 当 verify |
| S2 vacuous Gate 2 | **PARTIAL** | preference threshold 0.30 加好；bandit 仍 always-pass；NB/HMM 完全不在 dispatch 里 |
| Artifact discipline (C9) | **STILL OPEN, NEW EVIDENCE OF EVASION** | `_artifact_schema.py` 写好但 04-28 五个 raw JSON 一个都没用 |
| Claim-first artifact-later 病根 | **STILL OPEN** | abstract / table claim 仍领先于 auditable raw（n=200 vs n=50） |

**判决**: 04-23 Codex 三轮 5→4.5→4 持续下降的核心病根 — 病灶仍在，但 **表层有改进**（NB/HMM solver 真合成；framing 在 caption 层面诚实化；删 Gate 3 是好事）。"病根未除"的预测兑现：04-28 评分 4.6 ≈ 04-23 round 3 的 4.0，未持续下降但也未上行。

---

### Suspicions to carry forward (Round 2 prepend)

| # | Suspicion | 状态 | 核查钩子 |
|---|---|---|---|
| S1 | C3 identity crisis — compile 真做 synthesis 还是仍 routing | STILL SUSPICIOUS | `rg -n "BNReferenceSolver\|solve_from_text\|solve_from_factors" taskspec/compiler.py solvers/bn_solver.py` — 看不同 BN spec 是否 compile 出**结构不同**的 solver |
| S2 | Artifact discipline 是否 enforced | NEW EVIDENCE OF EVASION | `for f in baselines/results/*20260428*.json; do python3 -c "import json,sys; d=json.load(open(sys.argv[1])); print(sys.argv[1], '_meta' in d)" "$f"; done` |
| S3 | C5 leakage main path 干净 / legacy 是否 audited | RESOLVED main / STILL SUSPICIOUS legacy | `rg -n "correct_diagnosis\|correct_state\|reward_fn\|answers" inductor baselines` |
| S4 | C6 disjoint verification | STILL SUSPICIOUS | `rg -n "verify_samples\|samples\[:max\|samples\[max" inductor tests` |
| S5 | Gate 2 vacuity for NB/HMM/Bandit | STILL SUSPICIOUS | `rg -n "passed=True\|不支持的 family\|naive_bayes\|hmm_forward" verifier/gates.py` |
| S6 | Structured-route vs NL-E2E 区分 in paper | NEW EVIDENCE OF EVASION | 比较 `paper/main.tex` 表格 n 与 JSON `.nb.n / .hmm.n`；abstract 是否加了 "given structured input" |
| S7 | NB robustness — paper 显示 50/100% only or 也 confess medium=50% / hard=36% | NEW EVIDENCE OF EVASION | grep "difficulty\|graceful\|36\|50%" paper/main.tex |
| S8 | Cost trace metadata | STILL SUSPICIOUS | `rg -n "prompt_tokens\|completion_tokens\|total_cost\|_meta" baselines/results paper/main.tex` |
| S9 | Schema consistency | NEW EVIDENCE OF EVASION | `.venv/bin/python3 -m unittest tests.test_compiler -v 2>&1 \| grep -E "FAIL\|test_roundtrip"` |
| S10 | PAL 数字内部一致性 | NEW EVIDENCE OF EVASION | `rg "PAL drops\|17\.5\|23\.3\|0--3%\|15%\|fails entirely" paper/main.tex` |

---

### Strongest sink vector（Codex 30 秒攻击模拟）

> "This is a hand-written family router plus solver library; the LLM emits a structured config, and the reported 100% is not NL end-to-end."

**仍未捍卫**。Mini-direct-fails (44%/32%) vs framework-100% framing 只有在 paper visibly 多次声明 "100% NB/HMM is structured-input/component-level, not full NL reasoning" 才诚实。当前 caption 做到了 (L551)；abstract (L82) 还没做到。

---

### Codex 原始回复（verbatim）

<details><summary>Round 1 完整回复（展开 ~2400 字）</summary>

```
**Verdict: Direction B.** The framing pivot is the right direction, but the plan and paper still need revision before this can survive a serious NeurIPS review. Today's commits were reasonable as triage, not as ship-ready evidence.

**Scores**
| Area | Score |
|---|---:|
| framing-clarity | 5/10 |
| evidence-strength | 4/10 |
| narrative-coherence | 5/10 |
| novelty-articulation | 5/10 |
| related-work-positioning | 6/10 |
| claim-data-fit | 3/10 |
| reproducibility | 4/10 |
| **paper average** | **4.6/10** |

| Plan area | Score |
|---|---:|
| completeness | 6/10 |
| prioritization | 7/10 |
| cost-benefit | 4/10 |
| risk-awareness | 6/10 |
| executability | 5/10 |
| **plan average** | **5.6/10** |

**Findings**
| Severity | Finding | Evidence | Verification hook |
|---|---|---|---|
| CRITICAL | The paper still inflates structured-input component success into broad "framework 100%" framing. The plan itself admits only Flight is true NL→answer E2E. | mossy-beaming-sky.md:12, main.tex:82, main.tex:551 | Add separate rows for `structured TaskSpec route` vs `NL E2E full pipeline`; require raw NL E2E artifacts. |
| CRITICAL | NB generalization is not defended. The paper says solvers handle varying feature counts, but today's difficulty run collapses to 18/50 and medium file is 25/50, not the commit/message 27/50. | main.tex:329, declarative_spec_route_paper_n50_difficulty_var...json:6, declarative_spec_route_nb_medium...json:7 | jq accuracies. |
| CRITICAL | Artifact discipline is still broken. The helper requires `_meta`, but all five mandatory raw result JSONs lack it. | baselines/_artifact_schema.py:39, result files start directly with experiment fields | Run `validate_artifact` over all `*20260428*.json`. |
| CRITICAL | NB/HMM are not actually supported by the verifier gates, so the "verified" framing does not cover today's new headline families. | verifier/gates.py:147, :156 | Construct NB/HMM TaskSpec and call verify_taskspec; returns unsupported-family failure at Gate 2. |
| MAJOR | C3 identity crisis only partially resolved. compiler.py no longer literally returns default BNReferenceSolver(), but it still dispatches to hand-written solvers/macros, not synthesized solver structure. | compiler.py:82, bn_solver.py:70 | Compare different BN TaskSpecs: most structure still lives in parser/solver, not compiled representation. |
| MAJOR | Paper has internal bnlearn/PAL contradictions. Main text says PAL drops to 0-3% / fails entirely, but appendix table has mini PAL 17.5% overall and Child/Insurance nonzero. | main.tex:440, :537, :1003 | rg PAL drops|fails entirely|17.5|23.3|15% paper/main.tex |
| MAJOR | TaskSpec serialization/schema is inconsistent with the pivot. to_dict() drops NB/HMM fields and injects BN-only fields; compiler roundtrip test fails. | schema.py:91, :184 | python3 -m unittest tests.test_compiler -v fails test_roundtrip |
| MAJOR | Abstract/intro still oversell "five families / 100% / over 1,150 instances" relative to available evidence. NB/HMM evidence is structured route n=50+50; NL E2E pending. | main.tex:75, :112; result JSON :7, :467 | Require paper audit table mapping every numeric claim to raw artifact path and n. |
| MAJOR | Cost claims not auditable and internally inconsistent: $0.008/14×/310× vs $0.001/60×/2500×. Raw artifacts lack token/cost metadata. | main.tex:83, :1131 | rg \$0.008|\$0.001|60×|310×|2500 paper/main.tex; enforce _meta.usage |
| MAJOR | P0+P1+P2 directionally right but insufficient for "general probabilistic reasoning agent." Plan explicitly excludes Level 3 non-Bayesian rejection, Level 4 macro reuse/routing, cross-model E2E. | mossy-beaming-sky.md:268 | Add rejection tests, macro-compose-vs-route tests, one non-mini robustness sweep. |
| MINOR | NB solver really uses DSL ops, but predict() bypasses DSL argmax. HMM mostly uses DSL ops but has hand-coded per-step factor normalization. | nb_solver.py:143, :176, hmm_solver.py:136 | Add tests/test_nb_hmm_core_ops.py with hand gold and op-trace assertions. |
| SUGGESTION | Self-evolving registry honestly scoped as future work and not connected to pipeline. Acceptable if paper keeps it non-claimy. | macros_library.py:1, main.tex:703 | Keep in limitations/future work only; do not count as evidence. |

**Previous Codex Review Resolution**
| Item | Status |
|---|---|
| C3 身份危机 | STILL OPEN / partial fix |
| C5 answer leakage | Mostly RESOLVED for main inductor path |
| C6 train/verify overlap | PARTIAL |
| S2 vacuous Gate 2 | PARTIAL |
| Artifact discipline | STILL OPEN, new evidence of evasion |
| Claim-first root | STILL OPEN |

**Strongest Sink Vector**
A reviewer can still say in 30 seconds: "This is a hand-written family router plus solver library; the LLM emits a structured config, and the reported 100% is not NL end-to-end." That attack is not yet defended. The mini-direct-fails / framework-100% framing is only honest if the paper says, visibly and repeatedly, that the 100% NB/HMM result is structured input/component-level.

**Bottom Line**
Direction B: the E2E rollout plan is the right next move, but revise it before execution. Add artifact-schema enforcement, NB/HMM verifier support, checked-in NB/HMM math tests, honest structured-vs-NL table separation, at least one rejection/non-Bayesian test, macro reuse-vs-compose evidence, and larger or clearly scoped n. The $0.36/~5h estimate is plausible only for API spend on happy-path scripts; not realistic for defensible NeurIPS-grade evidence and paper cleanup.
```

</details>

<details><summary>Codex Re-reply (debate round): Codex 撤回 / 坚持 4 个分歧</summary>

```
1. NB medium 27/50 vs 25/50: PARTIAL — downgrade to MAJOR. nb_medium not in main.tex (rg confirmed). Right finding: raw evidence contradicts commit-log narrative; paper must not import 54%. Separate concern remains: paper claims NB n=200, 3-6 diseases, 4-8 symptoms at main.tex:544-555, while auditable 100% raw is only n=50.

2. Inflation framing / L551 caption: PARTIAL — I withdraw that the held-out table caption hides the route. main.tex:551 is explicitly scoped to "spec-emission + deterministic-compile route." Remaining issue narrower: abstract main.tex:82 still says "reaches 100% across all five tested inference families" broadly, and table's n=200/n=100 claim not supported by mandatory n=50/n=50 raw. Downgrade from broad CRITICAL inflation to MAJOR claim-scope/data-support.

3. Artifact schema: PARTIAL — phrasing update, severity unchanged. _artifact_schema.py exists and enforces _meta fields at baselines/_artifact_schema.py:39-47, :95-150; correct finding is "infrastructure exists but is not enforced/migrated." I still rate CRITICAL for submission evidence because all five mandatory raw JSONs fail validation with missing _meta entire block.

4. test_compiler.test_roundtrip documented: STILL DISAGREE on downgrading to MINOR. Yes, Tree documents at framing-pivot-changelog.md:39-42 and :156-161, so not hidden and not evidence of evasion. But because paper leans on TaskSpec as a clean typed interface, a broken roundtrip/schema side effect remains MAJOR until fixed. Documentation lowers surprise, not reviewer risk.
```

</details>

---

### Bottom-line verdict

**Direction B**: Plan needs revision before execution.

**核心理由**:
1. 04-28 framing pivot 方向正确（NB/HMM 真合成 / Gate 3 删 / 删 pgmpy / mini-centric framing 是好的）但执行强度不够 — 04-23 三条 CRITICAL 仅 partial fix
2. P0+P1+P2 plan 是对的 next step，但 **3 个先决条件**未做：
   - **Pre-condition 1**: artifact schema enforcement（5 个现有 JSON 全部要么重生成要么标 "not yet schema-enforced"）
   - **Pre-condition 2**: NB/HMM verifier gates 支持（gates.py 加 dispatch + hand-gold sanity test）
   - **Pre-condition 3**: paper abstract + Table 3 caption 必须 reconcile claim-data 不一致（n=200 vs raw n=50；structured-route vs NL-E2E 区分）
3. P0+P1+P2 之外**还需补**:
   - L3 non-Bayesian rejection（10 GSM8K + 10 MMLU 看 mini 是否拒绝转 spec）
   - L4 macro reuse vs core-ops compose 显式区分
   - 至少 1 个非 mini cross-model E2E（gpt-5.4 跑同一 protocol 看 robustness）
4. **预算 $0.36 / 5h** 只够 P0+P1+P2 happy-path API 调用 — **不包括** 上述 3 个 pre-condition + 3 个补丁 + paper 重写。真实工作量更接近 **6-9 天 / $5-15** 才能达 NeurIPS 投稿水准

**Tree 当前 5 个待决策**:

1. abstract L82 "reaches 100% across all five families" 是否加 "given structured spec input" 限定 — **必须加**
2. Table 3 caption 的 n=200/100 是否重跑回 200/100 还是改写为 n=50/50（今天 raw 是 50） — **二选一今天能定**
3. C3 是否真重构（2-4 天）vs 接受 "verified deterministic backend with family-level dispatch" 降 scope — **影响标题**
4. P0+P1+P2 是否在 3 个 pre-condition 完成前先跑 — **建议不**，artifact schema 没 enforce 跑出的 raw 仍无 _meta，等于浪费 API 钱
5. cost claim 走 $0.008/14× 还是 $0.001/60×，是否在两套数字 reconcile 前先把 cost claim 全删

**最高 ROI 5 步**（按价值降序，应先于 P0+P1+P2）:

| # | 行动 | 工作量 | 解决的问题 |
|---|---|---|---|
| 1 | 5 个 raw JSON 经 `save_artifact` 重生成（≤ \$0.50 API） | 1h | C9 Artifact discipline + cost claim 数据基础 |
| 2 | abstract L82 + Table 3 caption + L82 n 限定文字改写（不动数字）| 30 min | CRITICAL → MAJOR：framing inflation + claim-data 不匹配 |
| 3 | gates.py 加 _gate2_nb / _gate2_hmm dispatch + hand-gold sanity | 1h | CRITICAL：NB/HMM not supported by verifier |
| 4 | PAL 数字 reconcile（rg "PAL drops\|17\.5\|0--3" → 决定一套 raw run）| 30 min | MAJOR：内部 contradictions |
| 5 | schema.py to_dict() by-family 过滤 + test_roundtrip 修 | 1-2h | MAJOR：TaskSpec interface 不干净 |

**Total preconditions**: ~5h work，**\$0.50 API** — 全部完成后再跑 P0+P1+P2。

---

## 路径

- **Report**: `/Users/robin/Desktop/taoyao/bayes/meta-skill/CODEX_REVIEW.md` (this file)
- **State**: `/Users/robin/Desktop/taoyao/bayes/meta-skill/.codex-review-state.json`
- **Codex thread (Reviewer Memory)**: `019dd047-aa69-79d1-a8b1-f56a028a1172`
- **Plan reviewed**: `/Users/robin/.claude/plans/mossy-beaming-sky.md`
- **Pivot changelog**: `paper/audits/2026-04-28-framing-pivot-changelog.md`
- **Previous review baseline**: `paper/audits/2026-04-23-codex-review.md`
