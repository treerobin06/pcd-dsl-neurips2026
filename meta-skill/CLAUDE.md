# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

# PCD-DSL: Verified Solver Induction for LLM Probabilistic Reasoning

> **最后更新**: 2026-04-09
> **论文标题**: Compile Once, Reason Exactly: Verified Solver Induction for LLM Probabilistic Reasoning
> **目标会议**: NeurIPS 2026
> **当前状态**: 论文已完成初稿，综合评审 6-7/10，准备最终打磨或补实验

---

## 一、核心思想（一段话版本）

LLM 能理解概率问题（Parse ≥95%）、能使用计算结果做决策（Decide 100%），但无法可靠执行概率计算（Compute 22-78%），且随问题复杂度增加崩溃到个位数。我们提出 PCD 诊断框架定位这一瓶颈，并用 typed DSL（7 core ops + 3 macros）+ 确定性编译器 + 3-Gate 验证器实现 "compile-once" 范式：LLM 只做一次 family-level 的结构归纳（输出 TaskSpec JSON），之后所有实例用编译出的 solver 确定性求解，零 LLM 成本。最便宜的 GPT-4o-mini 即可达到 100% compute 精确度。

---

## 二、系统架构

```
新任务样本 (1-5 个)
       │
       ▼
┌─────────────────┐
│  LLM Inductor   │  分析样本 → 输出 TaskSpec (JSON)
│  (GPT-4o-mini)  │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Deterministic   │  TaskSpec → Solver（从 DSL 原语组合）
│  Compiler        │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  3-Gate Verifier │  Gate 1: Code Sanity → Gate 2: Ground Truth → Gate 3: Reference Match (可选)
└────────┬────────┘
         │
    pass → 部署 verified solver（零 LLM 成本）
    fail → diagnostics 反馈 Inductor → self-refine（最多 3 轮）
```

### DSL 两层结构

**Layer 1 — Core Typed Ops (7 个)**：`condition`, `multiply`, `marginalize`, `normalize`, `enumerate_hypotheses`, `expectation`, `argmax`

**Layer 2 — Family Macros (3 个语法糖)**：`softmax_pref`（假设枚举）、`beta_bernoulli`（共轭更新）、`ve_query`（变量消除）。Macros 非必需——held-out HMM 仅用 core ops 达到 100%。

---

## 三、已完成实验与证据（18 项）

| # | Evidence | 核心结论 | 数据规模 |
|---|----------|---------|---------|
| 1 | 23 策略消融 (Flight) | user_separate 74.8% = Oracle；纯 CoT 无效（≤33%） | 624 样本 × 5 轮 |
| 2 | 跨任务泛化 | Flight/Hotel/Bandit/BLInD 四个 family 全部 100% solver 精度 | 1,800+ 实例 |
| 3 | DSL 等价性 | DSL solver = 原始 solver，max error = 0.0 | 1,200 实例 |
| 4 | LOO 泛化 | 6/6 held-out 数据集第 1 轮通过全部验证门 | 6 数据集 |
| 5 | PAL baseline | BN: PAL 26.4% vs Our 100%；偏好: PAL 29.3% vs Our 74.8% | 900+624 |
| 6 | 多模型 baseline | 最强模型 Opus=56.6% 仍远低于 Oracle 74.8% | 6 模型 |
| 7 | PCD 因果诊断 (BN) | Parse 96-100% / Compute 3-82% (depth-dependent) / Decide 100% | 900 样本 |
| 8 | 多模型 PCD | 6 模型 × 3 厂商全部展现相同 Parse 高/Compute 低/Decide 高 模式 | 6 模型 |
| 9 | Compile-time baseline | GPT-5.4=100%, GPT-4o=0%, Our(mini)=100% | 900 样本 |
| 10 | Gate 3 Off ablation | 6/6 通过，Gate 3 非必需，无数据泄漏 | 6 数据集 |
| 11 | Claude Sonnet PCD | Parse=100%, Compute=64%, Decide=100%（偏好学习） | 200 样本 |
| 12 | **偏好学习 NL Parse** | 自然语言输入 Parse 89.5% / Compute 30.5% / Decide 100% | 200 样本 |
| 13 | **端到端链路** | E2E 74.3% [70.9%,77.8%] ≈ Gold 74.4%，特征提取~100% | 624 样本 |
| 14 | DeLLMa 负面结果 | Compile-time solver ≈ 随机基线，精确刻画适用边界 | 20 样本 |
| 15 | Held-out NB (n=200) | Core-ops 100%, PCD: Compute 37-64.5% | 200 样本 |
| 16 | Held-out HMM (n=100) | Core-ops 100%, 顺序时序推理无需 macro | 100 样本 |
| 17 | Cost curve | Our $0.008 vs PAL $2.50 (310×) vs Compile GPT-5.4 $0.11 (14×) | — |
| 18 | bnlearn 真实网络 | ≥20 节点 PAL→0%, Our→100% | 120 queries |

### 全模型偏好学习 PCD 汇总

| 模型 | Parse | Compute\|GoldParse | Decide |
|------|:-----:|:---------:|:------:|
| GPT-4o-mini | 82% | 28% | 100% |
| GPT-4o | 100% | 30% | 100% |
| GPT-5.4 | 100% | 40% | 100% |
| Claude Sonnet 4 | 100% | 64% | 100% |
| Gemini 3.1 Pro | 100% | 69% | 100% |
| Claude Opus 4.6 | 100% | 78% | 100% |
| **Our DSL (mini)** | — | **100%** | — |

---

## 四、论文审查历史与评分

| 日期 | 审查类型 | 评分 | 关键问题 |
|------|---------|------|---------|
| 03-13 | 设计方案 (Codex R1-R2) | 6→8/10 | claim 识别性、MetaGenerator scope、baseline matrix |
| 03-13 | Story/投稿策略 (Codex R3) | 6/10 | template matching 攻击、novelty 锚定 |
| 03-14 | 证据完备性 (Codex) | 6.7/10 | Semantic Parse cherry-pick、外部 benchmark |
| 03-14 | 实验设计+贡献 (Codex R2) | 5.5→6.5/10 | GPT-5.4 compile=100% 削弱必要性、Gate 3 泄漏 |
| 03-15 | 论文审查 (Codex R2) | 7/10 | 附录缺 reliability/cost 详表 |
| 03-30 | 综合评审 (7-agent) | 6/10 | 引用错误、100% 需限定、ProbLog baseline 缺 |

**审查共识的核心 framing**：主贡献是 "verified compile-time solver induction with cheap models"（可靠+廉价+可验证），不是 "only we can do it"。

---

## 五、战略决策（2026-04-09 Codex + Claude 共识）

### 叙事决策

| 问题 | 决策 | 理由 |
|------|------|------|
| **主叙事** | 保持 "diagnose bottleneck → compile-once → verified exact" | 干净利落，NeurIPS problem-first 风格 |
| **Skill 术语** | **不用**作为主叙事，仅在 Related Work 轻触 | 会引发与 EvoSkills/SoK 的不公平比较，定位漂移 |
| **Self-Evolving** | **不用**这个词，用 "compositional generalization" 或 "no-macro composition" | HMM 是 one-shot composition，不是迭代进化；overclaim 风险 |
| **Related Work 引用** | 加一句桥接 + 引 SoK/EvoSkills | "Our typed operators and verified macros can be interpreted as a domain-specific skill library for exact probabilistic reasoning" |

### 架构改进（最高优先级论文改动）

当前问题：Inductor 是黑箱，论文只有 15 行描述。HMM/NB 的 core-ops composition 路径（核心 novelty）完全没有展开。

**要做的改动**：
1. **Figure 1 加 Inductor zoom-in inset**：展示 recognize → compose/reuse → emit spec 三步
2. **Section 4.4 展开 3 段**：family recognition + composition path (HMM case study) + route analysis
3. **加 Route Analysis 表**：每个 family 走的路径（macro reuse vs core-ops composition）

| Family | Matching Macro | Path | Composition |
|--------|:-------------:|------|-------------|
| Flight/Hotel | `softmax_pref` | Macro reuse | 直接复用 |
| TextBandit | `beta_bernoulli` | Macro reuse | 直接复用 |
| BLInD/bnlearn | `ve_query` | Macro reuse | 直接复用 |
| **Naive Bayes** | **None** | **Core-ops** | `enumerate → multiply → normalize → expectation → argmax` |
| **HMM Forward** | **None** | **Core-ops** | `iterated(multiply → marginalize → normalize)` over time |

**Codex 评分预测**：这一改动可将评分从 6.9 → 7.7/10。

---

## 六、待做事项（按优先级排序）

### 2026-04-23 最新讨论：100% framing + Mixed E2E

**问题**：论文里 100% 指标密度过高（DSL 等价性 / LOO 6/6 / Compute 100% / Held-out NB+HMM / bnlearn / Our DSL mini），审稿人第一眼会起疑 "cherry-picked / too clean"。Tree 担心所有指标都是 100% 不正常。

**共识（2026-04-23 讨论）**：
- 100% 分两类——**A 设计保证型**（确定性编译器 + 精确推理的数学性质，是 "compile once, reason exactly" 核心卖点，不能弱化）vs **B 需限定型**（scope 不清、n 太小，容易被攻击）
- **不能全换成端到端**，否则 "compile once, reason exactly" 标题和卖点同时塌
- 正确策略三件套：**把 E2E 数字放主位 + 所有 100% 加 scope 限定 + 扩端到端实验**

**老师建议的关键补实验**：所有数据集混合后完整 agent 端到端效果（Mixed E2E）——同时解决 100% 怀疑 + 论文从"per-family solver 集合"升级为"general probabilistic reasoning agent"。
- 预期落点 **65-82%**，围绕 **74%** 附近（基于 Flight E2E 74.3% + Parse 85-100% + Compute 100% 推算）
- 这个"不那么漂亮"的数字比一堆 100% 的可信度高一个数量级

### 2026-04-23 晚 Tree 确立新战略（投稿前最终方向）

**原则**："**完整+量少，比 same-model baseline 好就行，不追求 100%**"。

**具体意思**：
- 端到端覆盖优先于单实验堆样本（bnlearn 15q/net 即可，不需要 100q/net）
- 论文叙事要建立在 **"Our method + same model > PAL/direct + same model"** 公平对比上，不吹 100%
- 承认 Parse 在大 BN 上有瓶颈，不遮掩
- 修实验 bug（特别是 bnlearn `multiply_factors` 空壳）+ 补 Mixed E2E 端到端 + 论文改写法——**三件套一起做**

**实验规模（按"完整+量少"重设计）**：
- bnlearn: 4 nets × 15q × 5 modes × (mini+5.4) = 600 调用 ≈ $8-15
- Inductor scrubbed: 80 调用（mini）≈ $0.2
- Mixed E2E: mini 300 + 5.4 300 对照 = 600 ≈ $7-12
- Multi-model NL Parse: 3 模型 × 50 = 150 ≈ $2-4
- PAL self-repair: 300 (mini) ≈ $0.5
- Codex 审查 × 3 轮: ~15 调用 ≈ $10-20
- **本地 0 成本**: DSL verify / 等价性 / LOO dump JSON / test_equivalence_full

**预算分层**：
- **最小刚需**（不重跑 PCD 6 模型）：$30-55
- **推荐**：$50-80
- **完整含 PCD 重跑**：$100-180（>$100 需 Tree 明示同意）

**API 渠道**：OpenRouter（主力，所有论文实验）+ Codex MCP（独立审查，gpt-5.4 xhigh）+ 本机 Python + pgmpy（零成本）

### 2026-04-23 审查发现：三 agent 并行审查结果（Critical Blockers）⚠️

**审查方式**：`citation-verifier` / `result-to-claim` / `experiment-audit` / `paper-claim-audit` **四 agent 独立并行审查**，互不看 summary。四 agent 交叉印证确认不是单一 reviewer 误判。（第 4 agent 首次运行 1:48 后卡在写报告阶段被 kill，重启加 25 分钟硬限后 11 分钟完成）

**报告位置**：`paper/audits/2026-04-23-{citation-verifier,result-to-claim,experiment-audit,paper-claim-audit}.md`

**总体结论**：**FAIL / 严重度 HIGH**。Codex 独立判定 6 条核心 claim 中 **0 YES / 4 PARTIAL / 2 NO**。12 条 100% claim 归因 **1 A / 5 B / 6 C**。paper-claim-audit 独立核验 31 条数字，13+ 条 MATCH。

### 2026-04-23 晚 Tree 质疑后深度核查（关键）

Tree 直觉"这些实验我之前都跑通过"→ 深挖 `baselines/results/` + `data/eval/` + `tests/` 重新定性：

**agent 说对的 + 且更严重的**：
- **C1 bnlearn**: 不止是 fallback bug——raw JSON 显示 LLM 端到端 bnlearn 实验**真实结果 compile_core_ops=0% (failed) / compute=0%**，figure 里的 100% 只能来自 `verify_bnlearn_dsl_100.py` 的假 100%。**叙事欺诈：两套脚本产物混用，挑好看的**
- **C2 NB/HMM**: `held_out_nb_mini_205.json` raw 实锤 `parse=0.03 / compute=0.37 / compile_core_ops=1.0`。论文 "Parse ≥95%" 选择性忽略 NB Parse=3%；"core-ops 100%" 是绕过 Parse/Compute 的纯 solver 分数

**agent 说错的（降级）**：
- **~~C7 LOO raw 缺失~~ → Serious**: 数据集全在 `data/eval/heldout/`（Hotel + flight_2/3/5/6/7_features + flight_full，共 16MB）——Tree 的记忆对。问题只是 `test_loo_induction.py` 用 pytest 没 dump JSON，重跑就补上
- **~~C8 TextBandit 50~~ → Serious**: 确认 test_equivalence_full 只有 BLInD 900 + Flight ~250 = 1,150；paper "1,200" 是 approximate 不精确，改数字即可

**中间状态**：
- pgmpy 1.0 `from pgmpy.inference import VariableElimination` import 极慢（10+ 分钟未完成，Monitor 超时），bnlearn 冒烟因此卡住。**C1 修复的重跑方案需要换：用 BIFReader 读本地 BIF + 自写 VE 绕过 pgmpy.inference**，或者等它 import 慢慢完成

#### Critical Blockers（6 条，投稿前必须全修）

- [ ] **C1 bnlearn 100% 是叙事欺诈 + 代码 bug 双重问题** — 2026-04-23 深挖发现：
   - **真相 1（叙事）**：`baselines/results/bnlearn_*.json` 里 LLM 端到端 bnlearn 实验真实 direct=55-61% / compile_free=0-61% / **compile_core_ops=0% (failed)** / compute=0%。paper figure `our_dsl=[100,100,100,100]` 只可能来自 `verify_bnlearn_dsl_100.py` 的 fallback 假 100%——两个脚本产物混用，挑好看的
   - **真相 2（代码）**：`run_bnlearn_held_out.py:281-293` 的 `multiply_factors` **根本没实现**——`mul2` 循环体只有 `pass`，而 `multiply_factors` 连 `mul2` 都没调用，空壳！这就是 `compile_core_ops=0%` 的**直接技术根因**：LLM 被 prompt 约束必须用这个 core op，但 core op 是坏的，LLM 进死胡同
   - **真相 3（CPT 截断）**：L269 `cpt["entries"][:3]` 只给 LLM 前 3 个 entry，大 BN（alarm 37 节点）有几百条，LLM 根本看不全结构
   - **行动（零成本 → 有成本）**：(a) 修 `multiply_factors` 实现 + 去 CPT 截断 + 删"Simplified..."误导注释；(b) 小规模冒烟（asia + 10 queries × mini）看 compile_core_ops 从 0% 能跳到多少；(c) 修 `verify_bnlearn_dsl_100.py` fallback（已完成）并重跑得 DSL 数学正确性真实数字；(d) 全量重跑 bnlearn（4 nets × 15 q × mini+5.4 ≈ $8-15）；(e) 论文改叙事：承认 Inductor 结构提取瓶颈 + 展示 "Our core-ops > Free-code, same model" + 明确区分"DSL 数学正确性 100%"与"LLM 端到端"是两层
- [ ] **C2 NB/HMM "core-ops 组合 100%" 是叙事欺诈** — 2026-04-23 raw JSON 印证：`held_out_nb_mini_205` 实际 `parse_accuracy=0.03 / compute_accuracy=0.37 / compile_core_ops=1.0`。意思是 **NB Parse 仅 3%、Compute 仅 37%**，所谓 "100% core-ops composition" 是**绕过 LLM 的 Parse/Compute 后的纯 solver 分数**，不是 agent 端到端能力。而且 `taskspec/schema.py` + `inductor/prompts/induction_prompt.md` 只支持 3 family，NB/HMM 走独立 codegen 脚本，不是论文 L371-395 声称的 "inductor 组合 novel workflow"；prompt 给的 helper 已 family-shaped（NB 的 `condition()`、HMM 的 `marginalize(transition_fn)`）不是通用 core ops。**行动**: 要么重构 inductor 让它真能 core-ops 组合，要么撤/改 "compositional generalization" claim，**同时把 Abstract/Intro "Parse ≥95%" 全部改为"primary families 82-100%, NB 3%"**
- [ ] **C3 DSL Compute 100% 近似 tautology** — `taskspec/compiler.py:68-70` 对 BN 直接忽略 spec 返回 `BNReferenceSolver()`，"编译"实为"路由到手写 solver"。**行动**: 改 compiler 做真编译 + 重跑 DSL 等价性测试
- [ ] **C4 Gate 3 假独立** — LOO/Gate3-off 的 `gold_solver` 和 compiler 输出是**同一实现类两实例**，不是独立 gold。**行动**: 换独立 gold（如 pgmpy）+ 重跑 LOO/Gate3-off
- [ ] **C5 Inductor prompt 喂答案** — 原样 `json.dumps(sample)` 含 `reward_fn` / `answers` / `correct_diagnosis`；prompt 模板还显式要求看 `reward_fn`。**行动**: scrub prompt 输入只保留 task description + 重跑所有 inductor 实验
- [ ] **C6 LOO induction = verification（同样本两用）** — `samples[:k]` 既喂 induction 又做 verify，违反论文 L371-395 声明。**行动**: 拆独立 held-out split + 重跑 LOO
- [x] ~~**C7 LOO 6 数据集 raw 完全缺失**~~ — **2026-04-23 重新定性为"数据管理问题"**：数据集 **完整存在** 于 `data/eval/heldout/`（Hotel + flight_2/3/5/6/7/full_features.json，共 16MB）。问题是 `tests/test_loo_induction.py` 是 **pytest 只打 stdout 不存 JSON**，App Table L1121-1126 的 6 个 100% + checkmark 没有结构化 raw 留存。**行动**: 重跑一次 test_loo_induction 并 dump JSON 到 `baselines/results/loo_*.json` 即可（降级到 Serious-tier）
- [x] ~~**C8 TextBandit 50 samples 不存在**~~ — **2026-04-23 重新定性为"论文数字不精确"**：确认 `test_equivalence_full.py` 只有 BLInD 900 + Flight 前 50×~5 rounds≈250 比对 = **1,150**，TextBandit 不在 test 里。但这不是 fraud，是 paper "1,200" 的 approximate 描述。**行动**: 改 main.tex L339 数字为 "1,150" 或 "over 1,100"（降级到 Serious-tier）

#### Serious（限定/重算可救，7 条）

- [ ] **S1 Parse ≥95% 滑动定义** — 在 exact/structural/fieldwise 间换口径；mini Preference Parse 实际 82%，BN exact Parse 30-48%。paper-claim-audit 精确定位：L108 "Parse 82-100% on primary families" 直接和 BN exact Parse 30-48% 冲突；Table 3 caption L553 "Parse ≥98%" vs cell mini NB Parse **3%** 公然矛盾（caption/body L576 都要改）。**行动**: 论文全局统一 Parse 定义并在每处标明具体口径
- [ ] **S2 Gate 2 Preference 无阈值** — `verifier/gates.py:195-200` 总是 pass，"6/6 通过"里 5 个是"代码能跑就过"。**行动**: 加阈值 + 重跑 Gate 2
- [ ] **S3 n=6 CI 下界 54-61%** — 论文只报点估计，应随 claim 给 CI
- [ ] **S4 跨 baseline "correct" 口径混杂** — `gold_solver_rec` vs `user_idx` vs `gold_user_choice` 混用。**行动**: 统一口径 + 重算所有对比
- [ ] **S5 成本数字不一致** — 正文/Abstract/Fig3/Sec 5.4 给 $0.008 + 14× 对比，App Table 给 $0.001 + 60× 对比，同一东西两套数字并存。**行动**: 统一到一套（含选择哪个源数据 + 改所有相关位置）
- [ ] **S6 引用 `lew2025discipl` 作者嫁接** — bib 列 8 人实际 5 人，多 3 人从 `grand2024lilo` 拼接。**行动**: 修 bib
- [ ] **S7 引用 `jiang2026sok` 7/7 作者 first name 全错** — Yuqi→Yanna / Dong→Delong 等，title/arXiv ID 对但作者全错。**行动**: 修 bib
- [ ] **S8 "two parse failures" 口径错** — main.tex L602 声称 "two parse failures"，raw `parse_success_rate=0.9984` 实际只有 **1** 个 failure（624 中 1）。**行动**: 改文字为 "one parse failure"
- [ ] **S9 31 条数字 13+ 条真 MATCH** — paper-claim-audit 确认 Table 2 六模型 PCD / Table 3 NB-HMM cells / Fig 2 depth 曲线 Wilson CI / Fig 3(b) cost 数据点 / E2E 74.3% / Depth-10 3-11% / Inductor reliability 40/40 / PAL 26.4% & 98.1% 等数字**对得上 raw**——不是全盘皆错，有基石。修复时**保留这 13+ 条**，只改 Critical/Serious 1-8 涉及的
- [ ] **S10 bnlearn Direct/PAL 数字自相矛盾** — detailed audit（原 paper-claim-audit 第一次跑产物，214 行）发现：Paper L442 说 "PAL drops to 0-3% for both models; Direct Answer to 0%"，但 raw 实际 PAL **17.5% / 23.3%**、Direct **55.0% / 60.8%**。Paper 自己不同位置还混用两套 mini PAL run 数字（L994 "15%" vs L1011 Table "17.5%"，来自两份不同 run JSON）。**行动**: 统一到一次 run，修正 L442 / L994 / L1011 的数字到 raw
- [ ] **S11 Gemini 模型变体名错** — 论文协议说某 Gemini 变体，raw 实际用另一个 variant（detailed audit L79-89 点名）。**行动**: 查 raw 确认模型字符串，改论文保持一致
- [ ] **S12 附录多项 raw 缺失** — Gate-3-off 消融、23-策略/Content×Channel 附录表、LOO 6/6、bnlearn per-query details 均无对应 `baselines/results/*.json`。**行动**: 重跑补齐或在论文撤对应表/注明"compiled from prior exp logs"

#### 已修好 / 无动作

- [x] ~~`curtis2025pomdp`~~ 作者已修对（CoRL 2025 7 人全对）
- [x] ~~`first2025alphaverify`~~ 已从 bib 删除

#### 修复工作量估算

| 分组 | 工作 | 耗时 |
|---|---|---|
| C1 + C6 + S2 | 简单代码改动 + 重跑对应实验 | 1-2 天 |
| C5 | scrub prompt + 重跑所有 inductor 实验 | 1-2 天 |
| C2 + C3 + C4 | 深度改动（可能撤 claim 或重构 inductor + compiler） | 2-4 天 |
| C7 + C8 | 补 LOO 6 数据集 raw（或撤 App Table）+ TextBandit 50 补样/改论文数字 | 1-2 天 |
| S1 / S3 / S4 / S5 / S8 | 叙事统一 + 重算对比 + Parse 定义修正 | 1-1.5 天 |
| S6 / S7 | bib 修复 | 0.5 天 |

**合计 6.5-12 天**才能真正达到投稿水准。Mixed E2E 应在所有 Critical 修完后才跑。

### P0：论文架构改动（无需新实验，最高 ROI）

- [x] **Inductor 架构展开** — Section 4.4 扩写为 3 步 + Route Analysis 表 ✅ 2026-04-09
- [x] **Related Work 加 Skill 文献桥接** — 引 SoK + EvoSkills ✅ 2026-04-09
- [x] **叙述对齐** — Intro/Contribution/Held-Out/Conclusion 全部呼应 compositional generalization ✅ 2026-04-09
- [x] **"given a new task" 统一** — 替换所有 "a few examples" ✅ 2026-04-09
- [ ] **Figure 1 重新生成** — 去掉 PCD 左面板，只保留 compile-once pipeline 全宽图（4K，PaperBanana）
- [ ] **Figure 1 caption 更新** — 匹配新的纯 pipeline 图
- [ ] **考虑加 Figure 2(a) PCD 柱状图** — 如果 Figure 1 不再展示 PCD
- [ ] **引用修复** — 全面检查 references.bib 准确性（`curtis2025pomdp`/`lew2025discipl`/`first2025alphaverify` 有编造作者名和会议错）
- [ ] **术语统一** — compile-once vs compile-time、free code vs unconstrained
- [ ] **100% 清单扫描与 framing 分类** — 扫 main.tex 所有 "100%" 位置，按 [A:设计保证 / B:需 scope 限定 / C:需补实验] 三类标注，逐条定修改方案（2026-04-23 新增）
- [ ] **所有 B 类 100% 加 scope 限定** — Compute "on the compute stage, conditional on correct parsing"；LOO "first-round pass rate 6/6, n=6 held-out datasets"；Abstract L82 / Intro L117 / Conclusion L670 全覆盖（2026-04-23 新增）
- [ ] **Abstract / Table 1 主位改报 E2E** — Flight E2E 74.3%（以及 Mixed E2E 跑完后的总数字）放首行，100% 作为分解诊断往后排（2026-04-23 新增）

### P1：需要补充的实验

| 实验 | 回应的攻击点 | 估计耗时 |
|------|-----------|---------|
| **Mixed E2E benchmark（2026-04-23 新增，老师建议，P1 最高优先级）** — 所有数据集 shuffle 后完整 agent 管线：NL input → Inductor family-agnostic → compile → solve → decide；建议 6 family × 100 样本 × 3 seed + bootstrap CI；报 overall accuracy + family recognition rate + per-family 分解 | 100% claim 可疑 + "直接调 pgmpy 就行" + agent 完整性 | 1-2 天（含 pre-flight 冒烟），≈$5-10 |
| **Per-family E2E 矩阵（2026-04-23 新增）** — Hotel/TextBandit/BLInD 各自端到端实验（目前只有 Flight 74.3%），形成 E2E 诊断矩阵 | E2E 覆盖面不足 | 1 天 |
| **多模型 NL Parse** — GPT-4o/5.4/Claude 重跑偏好学习 NL Parse | 跨模型一致性 | 1 天 |
| **bnlearn 扩样** — 30→100 query/网络 | 测试集太小 | 0.5 天 |
| **PAL + self-repair** — 给 PAL 加 3 轮 self-repair | baseline 不公平 | 1 天 |

### P2：如果时间允许

| 实验 | 回应的攻击点 | 估计耗时 |
|------|-----------|---------|
| DSL ablation — no macros / no verifier / no self-refine | gain 来源不清 | 1 天 |
| ProbLog/pgmpy baseline | "直接调库就行" | 1 天 |
| QUITE benchmark | 外部效度 | 2 天 |

### 更长远方向（后续论文）

- 连续分布 + 近似推理（MCMC/VI 后端）
- 自动发现新 primitive（Level 3 skill evolution）
- 新 macro 蒸馏 + 库持久化 + 跨任务复用（真正的 self-evolving）
- 与 Agent 框架集成（solver as tool）

---

## 六、代码结构

```
meta-skill/
├── CLAUDE.md               ← 你在这里（项目唯一权威文档）
├── dsl/                     # 概率 DSL 库
│   ├── types.py             # 类型系统（Distribution, Factor, HypothesisSpace, Evidence）
│   ├── core_ops.py          # 7 个核心运算
│   └── family_macros.py     # 3 个 family macro
├── taskspec/
│   ├── schema.py            # TaskSpec JSON schema
│   └── compiler.py          # TaskSpec → Solver 确定性编译器
├── inductor/
│   ├── inductor.py          # LLM 分析样本 → TaskSpec
│   ├── refiner.py           # Verifier 反馈 → self-refine 循环
│   └── prompts/             # Induction prompt 模板
├── verifier/
│   └── gates.py             # 3-Gate 验证
├── solvers/                 # Gold reference solvers
│   ├── preference_solver.py # 偏好学习（hypothesis_enumeration）
│   ├── bn_solver.py         # BN 推断（variable_elimination）
│   └── bandit_solver.py     # Bandit（conjugate_update）
├── baselines/               # Baseline 实验
│   ├── run_pcd_experiment.py       # PCD 因果诊断
│   ├── run_pal_experiment.py       # PAL baseline
│   ├── run_compile_time_baseline.py # Compile-time baseline
│   ├── run_bnlearn_held_out.py     # bnlearn 外部验证
│   ├── run_hmm_held_out.py         # HMM held-out
│   ├── run_held_out_family.py      # NB held-out
│   ├── run_e2e_experiment.py       # 端到端实验
│   ├── run_dellma_experiment.py    # DeLLMa 边界测试
│   ├── run_inductor_reliability.py # 归纳器可靠性（20×2 runs）
│   ├── prompts/                    # 所有 prompt 模板
│   └── results/                    # 实验结果 JSON + 分析
├── tests/                   # 测试套件
│   ├── test_dsl.py          # DSL 单元测试 + 等价性
│   ├── test_compiler.py     # 编译器测试
│   ├── test_equivalence_full.py  # 全量等价性（1,200 实例）
│   ├── test_inductor_e2e.py      # 归纳器端到端（需 API）
│   ├── test_loo_induction.py     # LOO 泛化（需 API）
│   └── test_gate3_ablation.py    # Gate 3 消融（需 API）
├── paper/                   # 论文
│   ├── main.tex             # 主文件（NeurIPS 格式）
│   ├── references.bib       # 引用
│   ├── CLAUDE.md            # 论文目录规则 + Overleaf 同步日志
│   ├── CODEX_REVIEW.md      # 论文审查记录（7/10）
│   ├── 2026-03-30-综合评审报告.md  # 最新综合评审（6/10）
│   ├── 论文说明与介绍/       # 15 篇系统性审计文档（供第三方理解论文）
│   └── sync_overleaf.sh     # Overleaf 双向同步脚本
├── archive/                 # 历史文档（Codex Review 各轮记录）
├── DESIGN.md                # [历史] 早期设计文档
├── ROADMAP.md               # [历史] 执行路线图（已全部完成）
├── CONTEXT.md               # 资源路径索引
└── 2026-03-13-EVIDENCE_SUMMARY.md  # 全部实验证据汇总
```

---

## 七、架构关键细节

### 数据流

```
TaskSpec (JSON) ──→ compiler.py ──→ Solver 对象 ──→ solver.solve(instance)
                    │                                    │
                    │  根据 inference_family 选择:        │  返回: posterior / recommendation
                    │  hypothesis_enumeration → softmax_pref()
                    │  conjugate_update → beta_bernoulli()
                    │  variable_elimination → ve_query()
                    │  (无匹配 macro → 纯 core ops 组合)
```

### 模块依赖关系

- `dsl/` 是纯库，无外部依赖（只用 numpy）
- `solvers/` 调用 `dsl/` 的 ops 和 macros
- `taskspec/compiler.py` 根据 TaskSpec JSON 实例化 `solvers/`
- `inductor/` 调用 OpenRouter API，输出 TaskSpec JSON
- `verifier/gates.py` 调用 compiler + solvers 做验证
- `baselines/` 的实验脚本调用 `phase1/` 的 BayesianSidecar 做 gold reference（通过 sys.path）
- `tests/` 的 API 测试（inductor_e2e, loo_induction, gate3_ablation）需要 `OPENROUTER_API_KEY`

### 测试分层

| 层 | 文件 | 需要 API | 运行时间 |
|----|------|:--------:|---------|
| 单元 | test_dsl.py, test_compiler.py | 否 | <1s |
| 集成 | test_equivalence_full.py | 否 | ~2s（加载数据） |
| E2E | test_inductor_e2e.py | 是 | ~30s |
| 泛化 | test_loo_induction.py | 是 | ~2min |
| 消融 | test_gate3_ablation.py | 是 | ~2min |

本地修改后至少跑前两层确认不破坏。

---

## 常用命令

```bash
# 全部本地测试（不需要 API）
cd meta-skill && python3 -m pytest tests/test_dsl.py tests/test_compiler.py tests/test_equivalence_full.py -v

# 需要 LLM API 的测试
cd meta-skill && python3 -m pytest tests/test_inductor_e2e.py -v
cd meta-skill && python3 -m pytest tests/test_loo_induction.py -v

# PCD 因果诊断
cd meta-skill/baselines && python3 run_pcd_experiment.py --task both --model openai/gpt-4o-mini --n 200

# PAL baseline
cd meta-skill/baselines && python3 run_pal_experiment.py --task bn --model openai/gpt-4o-mini

# Compile-time baseline
cd meta-skill/baselines && python3 run_compile_time_baseline.py --model openai/gpt-5.4 --task bn --k 5

# 端到端实验
cd meta-skill/baselines && python3 run_e2e_experiment.py

# Overleaf 同步
cd meta-skill/paper && bash sync_overleaf.sh pull   # 拉取
cd meta-skill/paper && bash sync_overleaf.sh push   # 推送
```

---

## 与父项目的关系

本项目（`meta-skill/`）是 `bayes/` 项目的核心子项目：

- **Phase 1 `phase1/`**：23 种策略旁路注入消融实验。提供了 Evidence 1（策略梯度）和 Evidence 6（多模型 baseline）的数据。
- **共享数据**：`data/eval/interaction/`（Flight 624 条、Hotel 124 条）
- **外部数据**：`data/external/BLInD/`（BN 推断 900 题）、`data/external/TextBandit/`（多臂赌博机）、`data/external/DeLLMa/`

---

## 飞书文档

- **文档名称**: Bayes 项目概览 — 贝叶斯教学与LLM概率推理
- **文档 ID**: `AcOIdoE0Gop4mexsificXAWbnNg`
- **所在文件夹 Token**: `Y59JfVFEClsLKqdXViOcA3h6n0d`

---

## 编码规范

- 注释语言：中文
- 新代码放在 `meta-skill/` 目录下
- 并发优先：asyncio + AsyncOpenAI
- API 统一走 OpenRouter
- 每个功能点完成后 git commit
- 用 `python3` 不用 `python`
