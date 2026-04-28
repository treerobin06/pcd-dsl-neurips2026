# Codex Review Report — 2026-04-23 论文修改计划整体独立审查

**审查类型**: Template D（计划/方案）主 + C（论文）+ B（实验）交叉
**开始时间**: 2026-04-23 22:45 CST
**参数**: MAX_ROUNDS=3, PASS_THRESHOLD=7, AUTO_FIX=false, CODEX_TIMEOUT=10min
**Codex MCP 配置**: model=`gpt-5.4`, sandbox=`danger-full-access`, approval-policy=`never`, config=`{"model_reasoning_effort": "xhigh"}`

## 审查重点

Tree 要求评估 **"整个对论文后续修改的定调"**——包括修改计划、实验安排、行文方向是否可行合理。特别关注 master plan §9 列出的 **12 个战略决策点**（战略 3 条 + 战术 3 条 + 叙事 3 条 + 风险 2 条 + 流程 1 条）。

**Tree 战略**: "完整+量少，same-model 跨 method > 跨模型挑最好，不追求 100%"。目标：把论文从当前 FAIL/HIGH 状态拉到 submittable contribution。

## 被审查对象（绝对路径）

### 主审对象
- `/Users/robin/Desktop/taoyao/bayes/meta-skill/paper/audits/2026-04-23-master-plan.md` (271 行，含 12 战略决策点)

### 4 agent audit 报告
- `/Users/robin/Desktop/taoyao/bayes/meta-skill/paper/audits/2026-04-23-citation-verifier.md`
- `/Users/robin/Desktop/taoyao/bayes/meta-skill/paper/audits/2026-04-23-result-to-claim.md`
- `/Users/robin/Desktop/taoyao/bayes/meta-skill/paper/audits/2026-04-23-experiment-audit.md`
- `/Users/robin/Desktop/taoyao/bayes/meta-skill/paper/audits/2026-04-23-paper-claim-audit.md`
- `/Users/robin/Desktop/taoyao/bayes/meta-skill/paper/audits/2026-04-23-paper-claim-audit-detailed.md` (214 行 46-claim 精确审查)

### todo 权威
- `/Users/robin/Desktop/taoyao/bayes/meta-skill/CLAUDE.md` (第六章"待做事项"含 6 Critical + 12 Serious + 工作量估算)

### 论文
- `/Users/robin/Desktop/taoyao/bayes/meta-skill/paper/main.tex`

### 关键代码（已修 + 待修）
- `/Users/robin/Desktop/taoyao/bayes/meta-skill/baselines/run_bnlearn_held_out.py` (✅ 已修 multiply_factors + CPT 截断)
- `/Users/robin/Desktop/taoyao/bayes/meta-skill/baselines/verify_bnlearn_dsl_100.py` (✅ 已修 dsl_p=gold_p fallback)
- `/Users/robin/Desktop/taoyao/bayes/meta-skill/inductor/prompts/induction_prompt.md` (🔲 C5: 喂答案)
- `/Users/robin/Desktop/taoyao/bayes/meta-skill/tests/test_loo_induction.py` (🔲 C6: samples[:k] 两用)
- `/Users/robin/Desktop/taoyao/bayes/meta-skill/verifier/gates.py` (🔲 Gate 2 无阈值 / Gate 3 假独立)
- `/Users/robin/Desktop/taoyao/bayes/meta-skill/taskspec/compiler.py` (🔲 C3: BN 分支直接 return reference solver)

### Raw results
- `/Users/robin/Desktop/taoyao/bayes/meta-skill/baselines/results/*.json`

---

## Round 1 — 2026-04-23 22:50 CST

**Codex threadId**: `019dbb42-8ea7-71f0-a3a4-01c37107de50`
**Codex 评分**: **5/10**
**总体评价**: 这份 master plan 比当前论文本身诚实得多，也准确抓住了最高置信度的问题簇（C1/C2/C5/C6）。但它仍把一个"先决定论文要缩到什么 scope"的问题写成线性修补计划；按现版本直接执行，风险仍然过高。

### 问题列表

| # | 严重 | 问题 | 位置 | Claude 判定 | 处置 |
|---|---|---|---|---|---|
| 1 | **CRITICAL** | C3 被当"修 compiler"处理，但它其实是论文身份问题——当前 BN "compile" 本质就是 `return BNReferenceSolver()`。需先在"降 scope 为 verified deterministic backend" vs "真重构 TaskSpec+compiler 让 BN spec 参与编译"中显式二选一 | master plan C3（L37）/ compiler.py:25 / main.tex:335 | AGREE | Round 2 必须让 Tree 明确二选一写回 plan |
| 2 | **CRITICAL** | plan §7 风险表没给"C5/C6/S2 修完后主结果大幅掉点"准备 Plan B（kill-switch），而泄漏/重叠/空 gate 在 inductor.py:28、induction_prompt.md:17、test_loo_induction.py:79、gates.py:195 均已存在 | §7 L214 / §5.2 cluster | AGREE | 加 kill-switch 条款：若 scrubbed/disjoint 后 LOO, 40/40, k=1 低于阈值则撤 headline / 降 appendix / 改标题 |
| 3 | **CRITICAL** | plan 没把 "artifact discipline" 设为阻断条件。S12 只是补充；但 `run_bnlearn_held_out.py:726` 只保存 overall，而 `paper/scripts/generate_figure3a_bnlearn.py:33` 硬编码 `our_dsl=[100,100,100,100]`——是失信核心 | S12 L57 / figure 脚本 | AGREE | 先定统一 raw schema（含 tokens/cost/model_id 强制字段）再允许任何新数字进论文 |
| 4 | **MAJOR** | "same-model" 叙事方向对，但只有在 S4（metric harmonization）变成**先决条件**才成立。当前 compile/PCD、PAL、E2E 比较口径不一致 | S4 L49 / run_compile_time_baseline.py:419, run_pal_experiment.py:185, run_e2e_experiment.py:295 | AGREE | 分成 "solver-agreement" 和 "user-choice" 两张表，不要混成一张"公平比较"主表 |
| 5 | **MAJOR** | bnlearn N=15/net 只能做 smoke test。按 Wilson n=15 半宽仍 ~19-22pp，不够 per-network 主图 | Layer 2 L155 | AGREE | per-network 柱状图至少回到 30-50 q/net；否则只报 overall |
| 6 | **MAJOR** | Mixed E2E N=300 能撑 pooled headline，但 50/family 不足以撑强 per-family claim | Layer 2 (2.6) | AGREE | per-family breakdown 写成 descriptive，不写"某家族显著优于" |
| 7 | **MAJOR** | 时间线内部矛盾（master plan 前文 6.5-12 天 vs timeline 7.5-10.5 天），而 CLAUDE.md 已承认 C2/C3/C4 单独 2-4 天。乐观 | §8 L227 / CLAUDE.md:241 | AGREE | 改两阶段 go/no-go 计划而非线性 schedule |
| 8 | **MAJOR** | **§9 只有 6 个决策点不是 12 个**——审查要求的 12 决策点 plan 实际没写完整 | master plan §9 L242 | AGREE（事实错误） | Round 2+ 需补 7-12：标题 scope / artifact schema / metric policy / bnlearn 最终 N / LOO reliability 是否保主位 |
| 9 | **MINOR** | CI 政策不统一（Clopper-Pearson/Wilson/bootstrap 并存） | compute_ci.py:1 / verify_bnlearn_dsl_100.py:19 / run_e2e_experiment.py:308 | AGREE | 每类实验固定一种，文中只写一次 |
| 10 | **MINOR** | 风险表"Mixed E2E <60 极不可能"无证据 | §7 L219 | AGREE | 改成真实风险项 + 降级方案 |
| 11 | **MINOR** | 成本计划没解决新 rerun 如何留下 token/cost trace | Layer 2 表 | AGREE | 所有新 JSON 强制记录 prompt_tokens/completion_tokens/total_cost/model_id |
| 12 | **SUGGESTION** | 执行顺序应为：artifact schema + C5/C6/S2 + tiny rerun → 决定 title/scope → full reruns → rewrite | 全局 | AGREE | 改执行顺序 |
| 13 | **SUGGESTION** | 若 C3 不真修 / C2 只保留窄化版，标题和 abstract 应提前降调 | Layer 0 / §6 | AGREE | 降 scope 先行 |

### 12 决策点判断（Codex 只读到 6 条显式 + 补 6 条必须补）

| # | 决策点 | Codex 判定 | 理由（1 句）|
|---|---|:-:|---|
| 1 | same-model 跨 method > 跨模型挑最好 | **YES** | NeurIPS 更买 controlled comparison；前提是 S4 先修 |
| 2 | bnlearn 叙事选 C（都报，硬分层） | **YES** | DSL 数学正确性 vs agent 能力**不能再混成一个数字** |
| 3 | 撤 C2 compositional generalization claim | **YES** | Parse=3% 已使故事塌了；最多保留为"core-ops-constrained codegen on synthetic NB/HMM" |
| 4 | Mixed E2E 65-70% 够不够 support | **DEPENDS** | 足以撑一个诚实 scoped paper；不足以挽救当前强版本 story |
| 5 | $30-55 预算够吗 | **DEPENDS** | 够最小诚实修补；不够同时 C3/C4 级重构 + 全套高可信 rerun |
| 6 | 撤掉 vs 重跑附录表 | **DEPENDS** | 便宜核心的重跑；无法 regenerate 的撤，不要"from prior logs"当主证据 |
| 7 | 本轮把 C3 押注为"大重构后继续原 story"? | **NO** | 应先 scope down，否则时间线整体重开 |
| 8 | 所有新实验强制输出结构化 raw artifact | **YES** | 没有 raw 就没有 claim |
| 9 | same-model 主表以 metric harmonization 为 blocking 前提 | **YES** | 否则仍然不公平比较 |
| 10 | bnlearn 15q/net 做最终主图 | **NO** | 只够 preflight / smoke test |
| 11 | LOO 6/6 + reliability 40/40 放 headline | **DEPENDS** | 即便 survives 也只适合 supporting，不该再做 headline |
| 12 | C2/C3 只部分修 → 标题和 contribution 同步降 scope | **YES** | 否则 reviewer 会认为"语言降调结构不降调" |

### 亮点（Codex）

1. 不再试图硬保假 100%，方向正确，准确抓住最高置信度 C1/C2/C5/C6
2. same-model + Mixed E2E 战略转向正确，符合 NeurIPS 审稿文化
3. 保留确实对得上的 raw 数字（13+ 条 MATCH），有工程判断力

### 致命问题（Codex verdict）

**存在，唯一核心致命点**：这份 plan 还没先决定"这篇论文到底要缩成什么样"。

**verdict**: 作为 scoped-down salvage plan **可执行**；作为保住当前强标题/强 contribution 的终极修复计划 **不可执行**。

### Suspicions to carry forward（Round 2 跨轮记账）

- `[suspicion-1]`: C1 只修了 multiply_factors/CPT 截断，但 `compile_core_ops` 仍可能爬不起来。**核查钩子**：Round 2 跑 `python3 -c "import json,glob,os; [print(os.path.basename(f), json.load(open(f)).get('compile_core_ops')) for f in sorted(glob.glob('baselines/results/bnlearn_*.json'))]"`
- `[suspicion-2]`: bnlearn Figure 3a 可能继续从硬编码或 stdout 拼，而不是从 raw artifact 生成。**核查钩子**：`rg -n "our_dsl|pal_54|pal_mini|direct" paper/scripts/generate_figure3a_bnlearn.py baselines/run_bnlearn_held_out.py`
- `[suspicion-3]`: prompt scrub 可能只删显眼字段，仍保留 `reward_fn/answers/correct_*`。**核查钩子**：`rg -n "reward_fn|answers|correct_diagnosis|correct_state|correct_posterior|json.dumps" inductor/inductor.py inductor/prompts/induction_prompt.md baselines/run_held_out_family.py baselines/run_hmm_held_out.py`
- `[suspicion-4]`: LOO 可能换说法仍有样本重叠。**核查钩子**：`rg -n "samples\[:max_induction_samples\]|samples\[:max_verify_samples\]|samples\[max_induction_samples:" tests/test_loo_induction.py tests/test_gate3_ablation.py`
- `[suspicion-5]`: Gate 2 preference 可能从"永远 pass"改成仍 vacuous 的超低阈值。**核查钩子**：`rg -n "passed = True|acc >=|threshold" verifier/gates.py`
- `[suspicion-6]`: same-model 表面公平实际仍混 `gold_solver_rec` / `user_idx` / `gold_user_choice`。**核查钩子**：`rg -n "gold_solver_rec|gold_user_choice|user_idx|e2e_correct|gold_match" baselines/run_* paper/main.tex`
- `[suspicion-7]`: C3 可能只是把代码挪位置，BN 仍 route 到 `BNReferenceSolver`。**核查钩子**：`rg -n "return BNReferenceSolver|variable_elimination" taskspec/compiler.py taskspec/schema.py`
- `[suspicion-8]`: Mixed E2E 可能被偷偷缩样本量，或 pooled result 掩盖 family failure。**核查钩子**：`rg -n "n_samples|per_family|family_recognition|overall_accuracy" baselines/run_e2e_experiment.py baselines/results/e2e_*.json`
- `[suspicion-9]`: 成本数字可能再次只存在 paper prose 没有 token trace。**核查钩子**：`rg -n "prompt_tokens|completion_tokens|total_cost|usage" baselines/results/*.json baselines/run_*`
- `[suspicion-10]`: LOO / Gate3-off / equivalence / 23-strategy 仍然没有结构化 raw。**核查钩子**：`ls baselines/results | rg 'loo|gate3|equiv|strategy|content|bandit|textbandit'`

### Codex 原始回复 (verbatim)

<details><summary>展开完整 Codex 原文（Round 1）</summary>

### 1. 总体评价（1-2 句）
这份 master plan 比当前论文本身诚实得多，也准确抓住了最高置信度的问题簇，尤其是 C1/C2/C5/C6。
但它仍把一个"先决定论文要缩到什么 scope"的问题，写成了一个线性修补计划；按现版本直接执行，风险仍然过高。

### 2. 评分：5/10

### 3. 关键问题清单
**CRITICAL**
- `CRITICAL`：C3 被当成"修一下 compiler"处理，但它其实是论文身份问题。[master plan C3](</Users/robin/Desktop/taoyao/bayes/meta-skill/paper/audits/2026-04-23-master-plan.md:37>)、[compiler](</Users/robin/Desktop/taoyao/bayes/meta-skill/taskspec/compiler.py:25>)、[main.tex 方法段](</Users/robin/Desktop/taoyao/bayes/meta-skill/paper/main.tex:335>)放在一起看，当前 BN "compile"本质上就是 `return BNReferenceSolver()`。建议修复路径：先显式二选一，再做实验。
  1. 论文降 scope，承认这是"verified deterministic backend / family router"。
  2. 真正重构 `TaskSpec` + compiler，让 BN spec 内容参与编译。
- `CRITICAL`：plan 没有为 C5/C6/S2 修完后"主结果大幅掉点"准备 Plan B。[风险表](</Users/robin/Desktop/taoyao/bayes/meta-skill/paper/audits/2026-04-23-master-plan.md:214>)没有覆盖这一点；而泄漏/重叠/空 gate 直接存在于 [inductor](</Users/robin/Desktop/taoyao/bayes/meta-skill/inductor/inductor.py:28>)、[prompt](</Users/robin/Desktop/taoyao/bayes/meta-skill/inductor/prompts/induction_prompt.md:17>)、[LOO](</Users/robin/Desktop/taoyao/bayes/meta-skill/tests/test_loo_induction.py:79>)、[Gate 2](</Users/robin/Desktop/taoyao/bayes/meta-skill/verifier/gates.py:195>)。建议修复路径：把"若 scrubbed/disjoint 后 LOO、40/40、k=1 掉到阈值以下，则撤 headline/降到 appendix/改标题"的 kill-switch 写进 plan。
- `CRITICAL`：这份 plan 仍未把"artifact discipline"设为阻断条件，而这正是当前 repo 失信的核心原因。[S12](</Users/robin/Desktop/taoyao/bayes/meta-skill/paper/audits/2026-04-23-master-plan.md:57>)只是补充说明；但 [bnlearn 脚本只保存 overall](</Users/robin/Desktop/taoyao/bayes/meta-skill/baselines/run_bnlearn_held_out.py:726>)，而 [Figure 3a 脚本硬编码 `our_dsl=[100,100,100,100]`](</Users/robin/Desktop/taoyao/bayes/meta-skill/paper/scripts/generate_figure3a_bnlearn.py:33>)。建议修复路径：先定义统一 raw schema，再允许任何新数字进论文。

**MAJOR**
- `MAJOR`：`same-model` 叙事方向是对的，但只有在 S4 变成"先决条件"时才成立。[master plan S4](</Users/robin/Desktop/taoyao/bayes/meta-skill/paper/audits/2026-04-23-master-plan.md:49>)；当前 compile/PCD、PAL、E2E 实际比较目标并不一致：[compile baseline](</Users/robin/Desktop/taoyao/bayes/meta-skill/baselines/run_compile_time_baseline.py:419>)、[PAL](</Users/robin/Desktop/taoyao/bayes/meta-skill/baselines/run_pal_experiment.py:185>)、[E2E](</Users/robin/Desktop/taoyao/bayes/meta-skill/baselines/run_e2e_experiment.py:295>)。建议修复路径：先统一成两张表，`solver-agreement` 和 `user-choice` 分开，不要混成一张"公平比较"主表。
- `MAJOR`：`完整+量少` 的原则对，但当前具体 N 分配并不都能撑主叙事。[Layer 2](</Users/robin/Desktop/taoyao/bayes/meta-skill/paper/audits/2026-04-23-master-plan.md:155>)里 `bnlearn 15q/net` 只能做 smoke test，做 per-network 主图太薄；我按 Wilson 算，`n=15` 时半宽大约仍在 `19-22pp`。建议修复路径：bnlearn 若保留分网络柱状图，至少回到 `30-50 q/net`；否则只报 overall，不报 per-net bars。
- `MAJOR`：Mixed E2E `N=300` 可以支撑一个 pooled headline，但 `50/family` 不足以支撑强 per-family claim。建议修复路径：把 per-family breakdown 写成 descriptive，不写"某家族显著优于某家族"。
- `MAJOR`：时间线和预算偏乐观且内部自相矛盾。[master plan 前文](</Users/robin/Desktop/taoyao/bayes/meta-skill/paper/audits/2026-04-23-master-plan.md:25>)写 `6.5-12 天`，[timeline](</Users/robin/Desktop/taoyao/bayes/meta-skill/paper/audits/2026-04-23-master-plan.md:227>)写 `7.5-10.5 天`；而 [CLAUDE.md](</Users/robin/Desktop/taoyao/bayes/meta-skill/CLAUDE.md:241>) 已经承认 C2/C3/C4 单独就可能吃掉 `2-4 天`。建议修复路径：改成两阶段 go/no-go 计划，而不是一条线性 schedule。
- `MAJOR`：你让我评"12 个决策点"，但 [§9 实际只有 6 条](</Users/robin/Desktop/taoyao/bayes/meta-skill/paper/audits/2026-04-23-master-plan.md:242>)。这不是小事，说明 plan 还没把真正决定成败的分叉点写完整。建议修复路径：补上缺失决策，尤其是标题 scope、artifact schema、metric policy、bnlearn 最终 N、LOO/reliability 是否保主位。

**MINOR**
- `MINOR`：CI 政策还没真正统一。[Clopper-Pearson 脚本](</Users/robin/Desktop/taoyao/bayes/meta-skill/paper/compute_ci.py:1>)、[Wilson](</Users/robin/Desktop/taoyao/bayes/meta-skill/baselines/verify_bnlearn_dsl_100.py:19>)、[bootstrap](</Users/robin/Desktop/taoyao/bayes/meta-skill/baselines/run_e2e_experiment.py:308>)并存。建议修复路径：每类实验固定一种，文中只写一次。
- `MINOR`：风险表里 "Mixed E2E <60 极不可能" 这个判断没有证据支撑。[master plan](</Users/robin/Desktop/taoyao/bayes/meta-skill/paper/audits/2026-04-23-master-plan.md:219>) 建议改成真实风险项，并写对应降级方案。
- `MINOR`：预算计划解决了论文里的旧成本矛盾，但还没解决"新 rerun 如何留下 token/cost trace"。建议修复路径：所有新结果 JSON 强制记录 `prompt_tokens/completion_tokens/total_cost/model_id`.

**SUGGESTION**
- `SUGGESTION`：执行顺序应改成 `artifact schema + C5/C6/S2 + tiny rerun -> decide title/scope -> full reruns -> rewrite`，不要先把 Layer 2 全铺开。
- `SUGGESTION`：如果 C3 不真修、C2 只保留窄化版本，标题和 abstract 应提前降调，不要拖到最后一轮。

### 4. 12 决策点逐一判断（master plan §9）
注：我在 [§9](</Users/robin/Desktop/taoyao/bayes/meta-skill/paper/audits/2026-04-23-master-plan.md:242>) 只读到 6 条显式决策点；7-12 是这份 plan 目前缺失、但必须补上的决策。

1. `YES`：`same-model 跨 method > 跨模型挑最好` 是对的。NeurIPS 更买 controlled comparison；但前提是先修 S4，把 metric 和 target 对齐。
2. `YES`：bnlearn 叙事应选 `C`，两者都报，但必须硬分层。`DSL math correctness` 和 `agent capability` 不能再混成一个数字。
3. `YES`：当前版本的 compositional generalization 主 claim 应撤。最多保留成"separate core-ops-constrained codegen baseline on synthetic NB/HMM"。
4. `DEPENDS`：Mixed E2E 若最终 `65-70%`，足以支撑一个更诚实、更现实的 scoped paper；不足以单独挽救当前强版本 story。
5. `DEPENDS`：`$30-55` 够做最小诚实修补，不够同时完成真正的 C3/C4 级修复和全套高可信 rerun。
6. `DEPENDS`：便宜且核心的表可以重跑；无法 clean regenerate 的 appendix 表建议直接撤，不要再写 "from prior logs" 当主证据。
7. `NO`：本轮不应把 C3 作为"大重构后继续原 story"来押注。更现实的是先 scope down；除非你愿意把时间线整体重开。
8. `YES`：所有新实验都必须强制输出结构化 raw artifact。没有 raw，就没有 claim。
9. `YES`：same-model 主表必须以 metric harmonization 为 blocking prerequisite。否则仍然是不公平比较。
10. `NO`：`bnlearn 15q/net` 不够做最终 per-network 主图。它只够 preflight / smoke test。
11. `DEPENDS`：LOO `6/6` 和 reliability `40/40` 即便 survives，也更适合作为 supporting evidence，不该再放 headline。
12. `YES`：如果 C2/C3 只部分修复，标题和 contribution 必须一起降 scope；否则 reviewer 会认为你在"语言降调，结构不降调"。

### 5. 亮点（2-3 点）
- 这份 plan 至少不再试图硬保假 100%，这一点方向是对的，而且它准确抓住了最高置信度的交叉共识问题：C1/C2/C5/C6。
- `same-model` + `Mixed E2E` 的战略转向是正确的，比继续堆最漂亮单点数字更符合 NeurIPS 审稿文化。
- plan 没有把论文当成"全盘推翻"，而是保留了确实对得上的 raw 数字，这说明它有一定工程判断力。

### 6. 致命问题
存在，而且只有一个核心致命点：这份 plan 还没有先决定"这篇论文到底要缩成什么样"。
我的 verdict 是：`作为 scoped-down salvage plan，可执行；作为保住当前强标题/强 contribution 的终极修复计划，不可执行。`

### 7. Suspicions to carry forward
（见上方主表，verbatim 保留）

</details>

---

## Round 2 — 2026-04-23 23:10 CST

**Codex 评分**: **4.5/10** (vs Round 1 的 5/10，**下降 0.5**)
**变化理由**: 上轮 10 条 suspicion **0 条 resolved**；其中 bnlearn Figure 3a 从"可疑"升级成"有硬编码证据"（NEW EVIDENCE OF EVASION）。再加上 Mixed E2E 和成本 trace 都还没代码级支撑，对 plan 可执行性比 Round 1 更悲观。

### Master plan 变更检查
- mtime: `2026-04-23 22:30:41 +0800`
- git: `3ea62de docs: add master plan consolidating audit findings + fix strategy`
- **判定**: 未改动（AUTO_FIX=false 符合，本轮仍审同一版）

### Suspicion 核查结果汇总

| # | 状态 | 关键证据 |
|---|---|---|
| 1 | **STILL SUSPICIOUS** | bnlearn raw 里 `compile_core_ops` 依旧 0%，且 schema 不统一（部分文件无此字段） |
| 2 | **🚨 NEW EVIDENCE OF EVASION** | `paper/scripts/generate_figure3a_bnlearn.py:33` 仍硬编码 `our_dsl=[100,100,100,100]`；`run_bnlearn_held_out.py:726` 把 per-network PAL 只打 stdout 不落 JSON |
| 3 | **STILL SUSPICIOUS** | `inductor/inductor.py:35` 仍 `json.dumps(s)`；`induction_prompt.md:19/89` 仍显式要求看 `reward_fn`；`run_held_out_family.py:293-294`、`run_hmm_held_out.py:357-358` 仍喂 `correct_*` |
| 4 | **STILL SUSPICIOUS** | `tests/test_loo_induction.py:80,118` 仍 `samples[:max_induction_samples]`/`samples[:max_verify_samples]` 两用；`test_gate3_ablation.py:70,99` 同样 |
| 5 | **STILL SUSPICIOUS** | `verifier/gates.py:196` 仍是 `passed = True`（preference vacuous pass）；BN 分支 L243 才有阈值 |
| 6 | **STILL SUSPICIOUS** | `run_compile_time_baseline.py:419` 用 solver gold；`run_pal_experiment.py:185` 用 `user_idx`；`run_e2e_experiment.py:295-298` 两套 gold 并存 |
| 7 | **STILL SUSPICIOUS** | `taskspec/compiler.py:70` 仍 `return BNReferenceSolver()` |
| 8 | **STILL SUSPICIOUS** | `run_e2e_experiment.py:340-341` 仍 `samples[:n_samples]` 截断；当前 e2e JSON 无 `per_family`/`family_recognition` 字段 |
| 9 | **STILL SUSPICIOUS** | `rg` `prompt_tokens|completion_tokens|total_cost|usage` 全仓返回 exit 1（无命中），成本 trace 基础设施根本不存在 |
| 10 | **STILL SUSPICIOUS** | `ls baselines/results | rg 'loo|gate3|equiv|strategy|content|bandit|textbandit'` 空——结构化 raw 缺口原样保留 |

### 本轮新发现

- **bnlearn 可复现性证据升级**：不仅 figure 脚本硬编码，`run_bnlearn_held_out.py:726` 还只把 per-network PAL 打到 stdout，**不写入 JSON**。即使重跑 Figure 3a 也仍然无法从 artifact 自动重建
- **Mixed E2E 实现工作量被低估**：`run_e2e_experiment.py` 目前只支持单 sample list + 截断采样，**没有 family mixing / family recognition / per-family summary 的输出字段**，master plan 把 Mixed E2E 当"跑一下"严重低估
- **结果 schema 混乱**：`bnlearn_*.json` 部分文件是 compile/direct，部分是 PAL-only，后续审计绘图继续依赖人工拼接，增加再次"表面修复实质绕过"的风险

### 致命问题状态

**未解决**。核心症结"先决定论文缩成什么样 + 先建 artifact 基础设施 + 再跑实验"的顺序完全没被采纳。代码层 C3/C5/C6/S2 没有任何动作（除已 commit 的 multiply_factors/fallback 修复外）。

### 更新的 Suspicions（Round 3 用）

沿用上轮 10 条 + 新增 2 条:

- `[suspicion-11]`: bnlearn runner 即使重跑，仍可能只把 per-network breakdown 打到 stdout 不落 JSON。**核查钩子**：`nl -ba baselines/run_bnlearn_held_out.py | sed -n '726,732p;761,767p'`
- `[suspicion-12]`: master plan 低估 Mixed E2E 新增实现工作量（family mixing + family recognition + per-family summary 三缺）。**核查钩子**：`nl -ba baselines/run_e2e_experiment.py | sed -n '330,341p;442,448p'`

### Codex 推荐下一步

1. 先停掉论文层改写，先补代码与 artifact：C5/C6/S2、bnlearn JSON schema、cost trace
2. 删除/禁用 `paper/scripts/generate_figure3a_bnlearn.py` 硬编码版本，强制图从 raw JSON 生成
3. 如果不准备真修 C3，尽快降标题和 contribution scope；否则继续写 master plan 只是拖延

### Codex 原始回复 (verbatim)

<details><summary>展开完整 Codex 原文（Round 2）</summary>

## Round 2

### Suspicion 核查逐条
[suspicion-1]: STILL SUSPICIOUS
  证据: 命令输出仍是 `bnlearn_openai_gpt-4o-mini_20260315_004339.json {'accuracy': 0.0, 'n_correct': 0, 'n_total': 120}`，`bnlearn_openai_gpt-5.4_20260314_235817.json {'accuracy': 0, 'n_correct': 0, 'n_total': 120, 'failed': True}`；其余两份 mini 和两份 5.4 bnlearn 文件是 PAL-only，`compile_core_ops=None`。
  结论: 现有 raw 里没有任何新证据表明 `compile_core_ops` 已从 0% 爬起来。更糟的是结果 schema 还不统一，有的文件存 `compile_core_ops`，有的根本没有该字段，审计性仍差。

[suspicion-2]: NEW EVIDENCE OF EVASION
  证据: [generate_figure3a_bnlearn.py](/Users/robin/Desktop/taoyao/bayes/meta-skill/paper/scripts/generate_figure3a_bnlearn.py:33) 仍硬编码 `our_dsl=[100,100,100,100]`, `pal_54=[90,0,3,0]`, `pal_mini=[27,20,23,0]`, `direct=[0,0,0,0]`；而 [run_bnlearn_held_out.py](/Users/robin/Desktop/taoyao/bayes/meta-skill/baselines/run_bnlearn_held_out.py:726) 只把 per-network PAL 打到 stdout，[同文件](/Users/robin/Desktop/taoyao/bayes/meta-skill/baselines/run_bnlearn_held_out.py:765) 保存的仍是 overall JSON。
  结论: 这已经不是"可能没接 raw"，而是明确存在"图从硬编码来、不是从 artifact 来"的证据。只要这个脚本还在用，bnlearn Figure 3a 就不具备可复现性。

[suspicion-3]: STILL SUSPICIOUS
  证据: [inductor/inductor.py](/Users/robin/Desktop/taoyao/bayes/meta-skill/inductor/inductor.py:35) 仍然 `json.dumps(s, ...)` 原样喂 sample；[induction_prompt.md](/Users/robin/Desktop/taoyao/bayes/meta-skill/inductor/prompts/induction_prompt.md:19) 和 [同文件](/Users/robin/Desktop/taoyao/bayes/meta-skill/inductor/prompts/induction_prompt.md:89) 仍显式要求看 `reward_fn`；held-out baseline 里 [run_held_out_family.py](/Users/robin/Desktop/taoyao/bayes/meta-skill/baselines/run_held_out_family.py:293) / [294](/Users/robin/Desktop/taoyao/bayes/meta-skill/baselines/run_held_out_family.py:294) 和 [run_hmm_held_out.py](/Users/robin/Desktop/taoyao/bayes/meta-skill/baselines/run_hmm_held_out.py:357) / [358](/Users/robin/Desktop/taoyao/bayes/meta-skill/baselines/run_hmm_held_out.py:358) 仍把 `correct_*` 放进 prompt。
  结论: prompt scrub 没发生。训练样例和 held-out codegen 两条线都还保留显式答案字段，Round 1 的泄漏判断原封不动成立。

[suspicion-4]: STILL SUSPICIOUS
  证据: [test_loo_induction.py](/Users/robin/Desktop/taoyao/bayes/meta-skill/tests/test_loo_induction.py:80) 仍用 `samples[:max_induction_samples]` 做 induction，[同文件](/Users/robin/Desktop/taoyao/bayes/meta-skill/tests/test_loo_induction.py:118) 仍用 `samples[:max_verify_samples]` 做 verify；[test_gate3_ablation.py](/Users/robin/Desktop/taoyao/bayes/meta-skill/tests/test_gate3_ablation.py:70) 和 [99](/Users/robin/Desktop/taoyao/bayes/meta-skill/tests/test_gate3_ablation.py:99) 同样如此。
  结论: 没有 split 修复，还是同样本两用。论文里 "disjoint validation" 的方法描述在代码里仍然不成立。

[suspicion-5]: STILL SUSPICIOUS
  证据: [verifier/gates.py](/Users/robin/Desktop/taoyao/bayes/meta-skill/verifier/gates.py:196) 仍是 `passed = True`；BN 分支才有 [243](/Users/robin/Desktop/taoyao/bayes/meta-skill/verifier/gates.py:243) `passed = acc >= 0.95`。
  结论: preference Gate 2 完全没改，依旧是 vacuous pass。任何基于 Gates 1-2 的 preference LOO / Gate3-off 结果都仍然不可信。

[suspicion-6]: STILL SUSPICIOUS
  证据: [run_compile_time_baseline.py](/Users/robin/Desktop/taoyao/bayes/meta-skill/baselines/run_compile_time_baseline.py:419) 用 solver 生成 `gold`；[run_pal_experiment.py](/Users/robin/Desktop/taoyao/bayes/meta-skill/baselines/run_pal_experiment.py:185) 用 `sample["rounds"][-1]["user_idx"]`；[run_e2e_experiment.py](/Users/robin/Desktop/taoyao/bayes/meta-skill/baselines/run_e2e_experiment.py:295) 同时保存 `gold_user_choice` 和 `gold_solver_rec`，并在 [297](/Users/robin/Desktop/taoyao/bayes/meta-skill/baselines/run_e2e_experiment.py:297)-[298](/Users/robin/Desktop/taoyao/bayes/meta-skill/baselines/run_e2e_experiment.py:298) 计算两套指标。
  结论: same-model 公平对比的前提条件仍未满足。不同 baseline 还在对不同 target 评分，主表一旦这么比，仍然是 apples-to-oranges。

[suspicion-7]: STILL SUSPICIOUS
  证据: [taskspec/compiler.py](/Users/robin/Desktop/taoyao/bayes/meta-skill/taskspec/compiler.py:68) 仍然 `_compile_bn`，并在 [70](/Users/robin/Desktop/taoyao/bayes/meta-skill/taskspec/compiler.py:70) 直接 `return BNReferenceSolver()`；schema 仍只知道 `variable_elimination` 这类 family，[taskspec/schema.py](/Users/robin/Desktop/taoyao/bayes/meta-skill/taskspec/schema.py:123)。
  结论: C3 没动。BN compiler 仍是 route-to-reference-solver，不是"TaskSpec 内容驱动的真实编译"。

[suspicion-8]: STILL SUSPICIOUS
  证据: [run_e2e_experiment.py](/Users/robin/Desktop/taoyao/bayes/meta-skill/baselines/run_e2e_experiment.py:340)-[341](/Users/robin/Desktop/taoyao/bayes/meta-skill/baselines/run_e2e_experiment.py:341) 仍可直接 `samples = samples[:n_samples]` 截断；结果文件只出现 `n_samples=5/200/624`，见 `e2e_*100406.json`, `e2e_*100715.json`, `e2e_*101317.json`；命令对 `per_family|family_recognition|overall_accuracy` 没有任何命中。
  结论: 当前代码和 raw artifact 都不支持 master plan 里承诺的 Mixed E2E 报告格式。不是"结果还没跑"，而是连统计字段都没设计出来。

[suspicion-9]: STILL SUSPICIOUS
  证据: 对 `baselines/results/*.json baselines/run_*` 执行 `rg -n "prompt_tokens|completion_tokens|total_cost|usage"` 返回空输出，exit code 1。
  结论: 成本 trace 基础设施仍不存在。即使现在重跑，也不会自动留下可审计的 token / usage / total_cost 证据，成本数字依旧只能靠 prose 或手算。

[suspicion-10]: STILL SUSPICIOUS
  证据: `ls baselines/results | rg 'loo|gate3|equiv|strategy|content|bandit|textbandit'` 返回空输出，exit code 1。
  结论: Round 1 指出的结构化 raw 缺口还在：LOO、Gate3-off、equiv、23-strategy、content-channel、TextBandit 结果文件依然没有落盘。

### 本轮新发现
- `bnlearn` 的可复现性问题比上轮更具体：不仅 figure 脚本硬编码，[run_bnlearn_held_out.py](/Users/robin/Desktop/taoyao/bayes/meta-skill/baselines/run_bnlearn_held_out.py:726) 还只把 per-network PAL 打印到 stdout，不写入 JSON。这意味着即使重跑，Figure 3a 也仍然没法从 artifact 自动重建。
- Mixed E2E 不是"补跑一个实验"那么简单。当前 [run_e2e_experiment.py](/Users/robin/Desktop/taoyao/bayes/meta-skill/baselines/run_e2e_experiment.py:330) 只支持单一 sample list + 截断采样，没有 family mixing、family recognition、per-family summary 的输出字段，master plan 低估了实现工作量。
- 结果 schema 仍不统一。`bnlearn_*.json` 有的文件是 compile/direct，有的是 PAL-only；这会让后续审计和绘图继续依赖人工拼接，增加再次"表面修复、实质绕过"的风险。

### Master plan 变更检查
mtime: `2026-04-23 22:30:41 +0800`
git log: `3ea62de docs: add master plan consolidating audit findings + fix strategy`
判定: 未改。`git status --short -- paper/audits/2026-04-23-master-plan.md` 为空，说明工作树里这份文件本轮也没有未提交改动。

### 重新评分
Round 2 得分: 4.5/10 (vs Round 1 的 5/10)
变化理由: 上轮的 10 条 suspicion 里 0 条 resolved；其中 bnlearn Figure 3a 从"可疑"升级成了"有硬编码证据"。再加上 Mixed E2E 和成本 trace 都还没有代码级支撑，所以我对这份 plan 的可执行性比 Round 1 更悲观。

### 更新的 Suspicions（给 Round 3 用）
（见上方，12 条）

### 致命问题状态
未解决

### 推荐下一步
1. 先停掉论文层改写，先补代码与 artifact：C5/C6/S2、bnlearn JSON schema、cost trace。
2. 删除或禁用 [paper/scripts/generate_figure3a_bnlearn.py](/Users/robin/Desktop/taoyao/bayes/meta-skill/paper/scripts/generate_figure3a_bnlearn.py:33) 的硬编码版本，强制图从 raw JSON 生成。
3. 如果不准备真修 C3，就尽快降标题和 contribution scope；否则继续写 master plan 只是拖延。

</details>

---

## Round 3 — Final Verdict — 2026-04-23 23:30 CST

**Codex 评分**: **4/10** (持续下降：5 → 4.5 → 4)
**分数下降原因**: 证据累积越多，plan 的 "claim-first, artifact-later" 病根越清晰；2 个 suspicion 已升级为 EVASION 状态
**停止原因**: 达到 MAX_ROUNDS=3

### Task A — 12 决策点终局 verdict

| # | 决策点 | Final Verdict | 理由（1 句）|
|---|---|:-:|---|
| 1 | same-model 跨 method > 跨模型挑最好 | **YES** | 在现有 cherry-pick、missing artifact、metric 混杂背景下，唯一还 defensible 的主叙事 |
| 2 | bnlearn 叙事采用"数学正确性 vs agent capability"双层拆分 | **YES** | compiler L68 + bnlearn raw + figure script L33 已证明两层混写导致失真 |
| 3 | 撤 C2 compositional generalization claim | **YES** | NB/HMM 走独立 codegen 脚本且 prompt 含 family-shaped helper，不是 shipped TaskSpec 路径上的 generalization |
| 4 | Mixed E2E 65-70% 够不够支撑论文 | **DEPENDS** | 够撑 downscoped 版本，不够原强版 story。前置条件：标题和 contribution 必须降 scope，C2/C3 headline 撤，per-family 只做 descriptive |
| 5 | $30-55 预算够吗 | **DEPENDS** | 够保守重跑和 scope-down rescue，不够同时清 C3 + artifact debt + metric harmonization + 鲁棒性。前置条件：不本轮真修 C3，unsupported appendix 直接砍，不扩多模型 bonus |
| 6 | 附录 unsupported 表"重跑补齐 vs 直接撤" | **YES** (直接撤) | 在 artifact discipline 缺失的状态下，撤比再做半干净重跑更安全 |
| 7 | C3 还能当"后置修补项"不影响原 story? | **NO** | 只要 BN compile 仍是直接 `return BNReferenceSolver()`，原 compile-once solver induction 叙事就站不住 |
| 8 | artifact discipline 设为硬门槛? | **YES** | 三轮下来最稳定的失败模式就是"论文先写，artifact 后补"，不改这条任何 rerun 都会再翻车 |
| 9 | metric harmonization 作为 same-model 主表 blocking prereq? | **YES** | 当前 compile/PAL/E2E 仍混 `gold_solver_rec`/`user_idx`/`gold_user_choice`，不统一就没有公平比较 |
| 10 | bnlearn 15q/net 做主图样本量? | **NO** | 只够 smoke test，不够 per-network 主图或 reviewer-facing scaling claim |
| 11 | LOO 6/6 + reliability 40/40 保留为 headline? | **NO** | 样本重叠、Gate 2 vacuous、raw 缺失三件事叠加后，只能 supporting evidence 不能主卖点 |
| 12 | C2/C3 只部分修，保原标题原 contribution? | **NO** | 核心机制退了但标题结构不退 = 语言降调结构不降调，reviewer 直接看穿 |

### Task B — 投稿建议

**选择**: **选项 2（降 scope 投 NeurIPS 2026）**

**理由**:
当前 scope 不能投。但也没必要直接判死到 2027，因为仍有一批真实成立的材料：
- PCD bottleneck 诊断（Table 2 六模型数字 MATCH raw）
- BLInD / Flight 的 deterministic equivalence（1,150 实例 max_err=0 真成立）
- 部分 E2E 结果（Flight 74.3%）
- 以及"verified backend"这条更窄的系统线

最合理的策略是立刻降标题、降 contribution、删 unsupported evidence，把 paper 改成：**"PCD 诊断 + verified deterministic backend for LLM probabilistic reasoning"**。

如果 Tree 不接受降 scope，才建议转 2027。但三选一里当前最优是选 2。

### Task C — Top 5 行动集（选 2 或 3 适用）

| 优先级 | 文件 / 动作 | 耗时 |
|---|---|---|
| **1** | `paper/main.tex` + Overleaf 同步：改标题、Abstract、Intro、Contributions，降 scope 到 "PCD + verified deterministic backend"；删 `compositional generalization` / `all tested BN benchmarks 100%` / `as few as one example` / `6/6 first attempt` 等强 claim | 0.5-1 天 |
| **2** | `paper/scripts/generate_figure3a_bnlearn.py`: 删硬编码 `our_dsl=[100,100,100,100]` 等 4 行；要么从 raw JSON 自动生成，要么整块砍掉换成保守 overall 描述 | 0.5 天 |
| **3** | `paper/main.tex`: 把 LOO / Gate3-off / k=1 reliability / held-out NB+HMM 从主证据链移除；NB/HMM 最多保留为 "separate codegen baseline"，不当核心 contribution | 0.5 天 |
| **4** | `baselines/run_bnlearn_held_out.py` + `baselines/results/`: 如果 Tree 坚持保留 bnlearn，先把 per-network 结果持久化进 JSON 再重跑 clean artifact；不做就从正文删 per-network bars | 0.5-1 天 |
| **5** | 硬分支决策：**(a)** 花 1-2 天真修 C5/C6/S2 + rerun（`inductor.py` + `induction_prompt.md` + `test_loo_induction.py` + `test_gate3_ablation.py` + `gates.py:196`），或 **(b)** 0.25 天把所有依赖这些代码的 generalization / reliability claim 从论文删掉 | 1-2 天 或 0.25 天 |

### Task D — 遗留分歧（交 Tree 裁决）

| # | 问题 | Codex 立场 | 反方立场 | 裁决方 |
|---|---|---|---|---|
| 1 | bnlearn 要不要留主论文 | 只有补出 clean raw artifact 后才值得留，否则宁可删 | bnlearn 是最强外部扩展性卖点，删了削弱 paper | **Tree** |
| 2 | C3 要不要现在真修 | 本轮不该押注，太晚太贵太风险 | 能快速 refactor compiler 也许还能保原标题 | **Tree** |
| 3 | NB/HMM 在 downscoped 版本保留吗 | 最多 separate codegen baseline，不能写 compositional generalization | 即便机制不纯，保留增加 novelty 感 | **Tree** |
| 4 | 成本 claim 要不要留主文 | 没 usage/token trace 就不该保留强成本比值 | 估算成本仍有叙事价值，可弱化措辞 | **Tree** |
| 5 | Mixed E2E 是否值得立刻投入 | 只有 paper downscope 完成后才值得作为加分项 | 可能是 2026 唯一能救 general-agent story 的实验 | **Tree / empirical data** |

### Task E — 元反思

三轮看下来，**没有看到真正的改进迹象**。核心病根不是单个 bug，而是 **"claim-first, artifact-later"** 的工作方式，加上不愿尽早做 scope surgery。Claude 的模式不是"恶意造假"，更像是不断尝试用局部措辞修补去保住原 headline。

**Tree 下一步最根本建议**（原话）：
> "没有 raw artifact，就没有论文句子；没有统一 metric，就没有比较表；没有 clean split，就没有 generalization claim。"

做不到这三条，就不要再把时间花在润色上。

### Final verdict summary

> 这篇东西还能救成一篇更窄、更诚实的 2026 submission，但绝对救不成当前这版强标题、强 contribution 的 NeurIPS 论文。

### Codex 原始回复 (verbatim)

<details><summary>展开完整 Codex 原文（Round 3）</summary>

## Round 3 — Final Verdict

### Task A: 12 决策点终局
1. 决策点 1: `same-model` 跨 method 对比是否应取代"跨模型挑最好"
  Final verdict: YES
  理由（1 句）: 在现有 cherry-pick、missing artifact、metric 混杂背景下，这是唯一还 defensible 的主叙事。

2. 决策点 2: bnlearn 叙事是否应采用"数学正确性 vs agent capability"双层拆分
  Final verdict: YES
  理由（1 句）: [compiler](</Users/robin/Desktop/taoyao/bayes/meta-skill/taskspec/compiler.py:68>)、[bnlearn raw](</Users/robin/Desktop/taoyao/bayes/meta-skill/baselines/results/bnlearn_openai_gpt-5.4_20260314_235817.json>)、[figure script](</Users/robin/Desktop/taoyao/bayes/meta-skill/paper/scripts/generate_figure3a_bnlearn.py:33>) 已经证明两层被混写才导致当前失真。

3. 决策点 3: C2 compositional generalization claim 要不要撤
  Final verdict: YES
  理由（1 句）: NB/HMM 仍走独立 codegen 脚本且 prompt 内含 family-shaped helper，不是 shipped TaskSpec/compiler 路径上的 generalization。

4. 决策点 4: 如果 Mixed E2E 最终是 `65-70%`，够不够支撑论文
  Final verdict: DEPENDS
  理由（1 句）: 这个数字只够支撑"downscoped、实践导向"的 paper，不够支撑原来那版强 solver-induction story。
  前置条件（如 DEPENDS 必填）: 标题与 contribution 必须降 scope，C2/C3 headline 必须撤，per-family 只做 descriptive report。

5. 决策点 5: Layer 2 的 `$30-55` 预算是否够
  Final verdict: DEPENDS
  理由（1 句）: 它够做保守重跑和 scope-down rescue，不够同时清掉 C3、artifact debt、metric harmonization 和全部鲁棒性证据。
  前置条件（如 DEPENDS 必填）: 不再尝试本轮真修 C3； unsupported appendix 直接砍；不再扩多模型 bonus 实验。

6. 决策点 6: 附录 unsupported 表格是"重跑补齐"还是"直接撤"
  Final verdict: YES
  理由（1 句）: 在当前 artifact discipline 缺失的状态下，撤掉 unsupported appendix 比再做半干净重跑更安全。

7. 决策点 7: C3 是否还能被当成"后置修补项"，而不影响原 story
  Final verdict: NO
  理由（1 句）: 只要 BN compile 仍是 [直接 `return BNReferenceSolver()`](</Users/robin/Desktop/taoyao/bayes/meta-skill/taskspec/compiler.py:70>)，原论文的 compile-once solver induction 叙事就站不住。

8. 决策点 8: 是否必须把 artifact discipline 设成硬门槛
  Final verdict: YES
  理由（1 句）: 三轮下来最稳定的失败模式就是"论文先写，artifact 后补"，不改这条任何 rerun 都会再翻车。

9. 决策点 9: 是否必须先做 metric harmonization，再做 `same-model` 主表
  Final verdict: YES
  理由（1 句）: 当前 compile/PAL/E2E 仍在混 `gold_solver_rec`、`user_idx`、`gold_user_choice`，不先统一就没有公平比较。

10. 决策点 10: `bnlearn 15q/net` 能不能作为主图样本量
  Final verdict: NO
  理由（1 句）: 这个 N 只够 smoke test，不够支撑 per-network 主图或 reviewer-facing scaling claim。

11. 决策点 11: LOO `6/6` 和 reliability `40/40` 还能不能保留为 headline
  Final verdict: NO
  理由（1 句）: [样本重叠](</Users/robin/Desktop/taoyao/bayes/meta-skill/tests/test_loo_induction.py:80>)、[Gate 2 vacuous](</Users/robin/Desktop/taoyao/bayes/meta-skill/verifier/gates.py:196>)、raw 缺失三件事叠加后，它们只能算 supporting evidence，不能算主卖点。

12. 决策点 12: 如果 C2/C3 只部分修复，是否还能保原标题和原 contribution
  Final verdict: NO
  理由（1 句）: 如果核心机制 claim 退了，但标题和 contribution 不退，那就是语言降调、结构不降调，审稿人会直接看穿。

### Task B: 投稿建议
选择: `2`

理由:
当前 scope 不能投。
但也没必要直接判死到 2027，因为你们手里仍有一批真实成立的材料：PCD bottleneck、BLInD/Flight 的 deterministic equivalence、部分 E2E、以及"verified backend"这条更窄的系统线。
所以最合理的策略不是"硬修原论文"，而是立刻降标题、降 contribution、删 unsupported evidence，把 paper 改成一篇更诚实的 "PCD 诊断 + verified deterministic backend for LLM probabilistic reasoning"。
如果 Tree 不接受这种降 scope，那我才建议转 2027；但在三选一里，当前最优是 `2`。

### Task C: Top 5 行动集（如选 2 或 3）
（见上方主表，verbatim 保留）

### Task D: 遗留分歧
（见上方主表，verbatim 保留）

### Task E: 元反思
三轮看下来，没有看到真正的改进迹象。
核心病根不是单个 bug，而是 `claim-first, artifact-later` 的工作方式，加上不愿尽早做 scope surgery。
Claude 的模式不是"恶意造假"，更像是不断尝试用局部措辞修补去保住原 headline。
Tree 下一步最根本的建议只有一条：`没有 raw artifact，就没有论文句子；没有统一 metric，就没有比较表；没有 clean split，就没有 generalization claim。`
如果做不到这三条，就不要再把时间花在润色上。

### Round 3 最终评分
4/10

### Final verdict summary
这篇东西还能救成一篇更窄、更诚实的 2026 submission，但绝对救不成当前这版强标题、强 contribution 的 NeurIPS 论文。

</details>

---

## 最终摘要

**轮次**: 3 / 3
**分数趋势**: Round 1: 5/10 → Round 2: 4.5/10 → Round 3: 4/10（**持续下降**）
**停止原因**: 达到 MAX_ROUNDS=3
**AUTO_FIX**: false（计划类审查，只审查不改文件）

### 已解决 / 共识项

**12 决策点达成共识（Codex 三轮稳定立场）**：
- **YES** (7 条)：决策点 1, 2, 3, 8, 9 + master plan §9 补充的 artifact discipline、metric harmonization
- **NO** (4 条)：决策点 7, 10, 11, 12（C3 后置 / 15q主图 / LOO headline / 部分修保原 scope）
- **DEPENDS** (3 条)：决策点 4, 5, 6（Mixed E2E 数字 / 预算 / 附录撤 vs 重跑——均需前置条件）

### 遗留分歧（5 条，请 Tree 裁决）

1. **bnlearn 要不要留主论文**（Codex: 没 clean raw 就删 / 反方: 外部扩展性卖点）
2. **C3 要不要现在真修**（Codex: 不押注 / 反方: 快速 refactor 能保原标题）
3. **NB/HMM 在 downscoped 版本保留吗**（Codex: 最多 separate codegen baseline / 反方: 保留增 novelty）
4. **成本 claim 留主文吗**（Codex: 无 token trace 就删 / 反方: 估算仍有叙事价值）
5. **Mixed E2E 立刻投入吗**（Codex: 先 downscope / 反方: 唯一救 general-agent story 的实验）

### 未处理 SUGGESTION

- Round 1 的两条 SUGGESTION（执行顺序调整 / C3 不真修则提前降调）被 Round 3 全面吸收为主决策
- 所有 12/13 问题（CRITICAL 3 + MAJOR 5 + MINOR 3 + SUGGESTION 2）**0 条 resolved**（plan 未改是预期的 AUTO_FIX=false，但 Codex 核查证实代码层也未改）

### 12 决策点最终共识（给 Tree 的 action-ready 速查）

见 Task A 终局表。Tree 可按此表逐条 ✅/❌ 决策。

### 推荐下一步行动（按优先级，综合三轮）

| 优先级 | 行动 | 耗时 | 理由 |
|---|---|---|---|
| **P0** | 【Tree 战略决策】接受降 scope 改投 2026 (选项 2) 或 转 2027 (选项 3) | 即刻 | 当前 scope 三轮都被判为"不可投" |
| **P1** | 改 `paper/main.tex` 标题 + Abstract + Contributions 降为 "PCD + verified deterministic backend"；删 4 条强 claim | 0.5-1 天 | Codex Task C.1 |
| **P2** | 删 `paper/scripts/generate_figure3a_bnlearn.py` 硬编码或从 raw 重建 Figure 3a | 0.5 天 | Round 2 NEW EVIDENCE OF EVASION |
| **P3** | 从主证据链移除 LOO + Gate3-off + k=1 reliability + NB/HMM | 0.5 天 | 决策点 11 verdict NO |
| **P4** | 硬分支：**(a)** 真修 C5/C6/S2 并 rerun (1-2 天) 或 **(b)** 从论文删 generalization/reliability claim (0.25 天) | 0.25 或 1-2 天 | 决策点 3, 11, 12 级联 |
| **P5** | 如保留 bnlearn：先落 per-network JSON artifact 再决定重跑 | 0.5-1 天 | 遗留分歧 1 |

**STATUS: COMPLETE**
