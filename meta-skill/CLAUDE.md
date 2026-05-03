# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

# PCD-DSL: Verified Solver Induction for LLM Probabilistic Reasoning

> **最后更新**: 2026-05-03
> **论文标题**: Compile Once, Reason Exactly: Verified Solver Induction for LLM Probabilistic Reasoning
> **目标会议**: NeurIPS 2026
> **当前状态**: 投稿收口中；核心 E2E 补实验已完成并写入论文/Overleaf，Figure 1 已更新为 reusable-registry 架构版；mixed 主表已改保守 aggregate；剩 claim/citation audit、数字一致性 sweep、post-audit final push

---

## 2026-05-02 最新权威状态（接手先读）

本节覆盖 2026-04-23/04-28 的旧 TODO。旧审查记录仍保留在下文作背景，但后续执行以本节为准。

### 已完成

- **官方 NeurIPS 2026 模板更新完成**：`paper/neurips_2026.sty` 已替换为官方版，新增 `paper/neurips_2026.tex` 和 `paper/checklist.tex`，`main.tex` 已 `\input{checklist.tex}`，`sync_overleaf.sh` 已同步这些文件。
- **Overleaf 已推送**：`paper/sync_overleaf.sh push` 成功，Overleaf 端最新 commit 为 `3557058 Sync from local 2026-05-03 18:08`（包含 reusable-registry Figure 1、conservative mixed table、NB/HMM 原始 hard-split 计数、verifier/theory/LOO 降调、Method 中 theorem-like 公式瘦身，以及 2026-05-03 reviewer-facing LLM-assembled solver framing / PCD Compute 口径修正 / Scope and Future Work 弱点措辞硬化 / Bayesian Teaching no-finetuning contrast / teacher-draft abstract fusion；模板更新最早推送 commit 为 `d28bf6b`）。
- **Schema roundtrip bug 已修复**：`taskspec/schema.py` 的 `to_dict()` 已按 `inference_family` 过滤字段，避免 BN-only 字段污染 preference/bandit。验证：`.venv/bin/python3 -m unittest tests.test_compiler -v` 当前 13/13 OK。
- **NB/HMM adversarial NL E2E 已在论文主表保留**：GPT-4o-mini，NB 91.7% [85.3, 95.4]，HMM 98.0% [93.0, 99.4]。这是 full natural-language pipeline，不是单纯 backend check。
- **Hotel E2E 已跑全量**：`n=124`，Parse 100.0%，E2E 77.4% [70.2, 85.5]，gold solver match 96.0%，cost $0.0556。Raw: `baselines/results/e2e_hotel_openai_gpt-4o-mini_20260502_213825.json`。
- **TextBandit-style E2E 已跑全量**：`n=100`，Parse/spec 96.0%，E2E 96.0% [90.2, 98.4]，4 个失败均为 observation-count omission，cost $0.0292。Raw: `baselines/results/textbandit_e2e_openai_gpt-4o-mini_20260502_213919.json`。
- **All-family mixed E2E 已跑全量并进论文**：GPT-4o-mini，100 examples × 6 supported families + 50 unsupported，总计 650。Raw mixed runner 为 overall 598/650 = 92.0%、supported 548/600 = 91.3%、router 650/650 = 100.0%；但论文主表已删除全 100 的 Route acc. 列，并用 NB/HMM adversarial NL harder split 原始计数对齐（NB 110/120，HMM 98/100），保守 aggregate 改为 overall 606/670 = 90.4% [88.0, 92.4]、supported 556/620 = 89.7% [87.0, 91.8]。Raw: `baselines/results/all_family_mixed_e2e_openai_gpt-4o-mini_20260502_221603.json` + `baselines/results/adversarial_nl_e2e_20260428_172402.json`。
- **旧 mixed sanity 已从论文删除**：`mixed_e2e_20260502_205650/205957.json` 的 BLInD+NB+HMM 90/90=100，以及 `mixed_open_set_e2e_20260502_211440/211531.json` 的 open-set 50/50=100，只能作历史 sanity，不得作为主结果。
- **论文已做大幅重写**：abstract/intro/evidence map/held-out table/single-family E2E/all-family mixed/limitations 均已按“分层证据 + 完整 E2E”更新。
- **2026-05-02 小修已进 `paper/main.tex`**：补了 E2E raw artifact provenance appendix，TaskSpec schema appendix 已加入 `naive_bayes` / `hmm_forward` 字段，PAL/bnlearn 主文措辞已改为具体网络结果，未使用的 `\todo` macro 已删除；Method 中 `inductor recurrence / verifier indicator / empirical risk` 三个 theorem-like 公式已删除，改为 prose + Algorithm。本地 `latexmk -g -pdf` 编译通过，`main.pdf` 30 页，无 undefined citation/reference/overfull。
- **Figure 1 已重做为架构图**：`figures/figure1_overview.png` 已删去左侧 PCD 面板，改为 router/scope gate + compile-once induction/backend + reusable solver registry 三层架构；图中不再出现 `PCD` / `THREE-GATE` / `100%` / `self-evolving`，caption 已同步改为 router-mediated reuse 叙事。当前本地正式图备份为 `figures/figure1_registry_imagen.png`；`figures/figure1_architecture_imagen.png` 是上一版 self-evolving 标题图，不建议使用；旧 `figures/figure1_imagen.png` 是更素的单线 pipeline，`figures/figure1_imagen_alt.png` 因底部英文有 typo，不建议使用。PaperBanana 2026-05-02 新任务超过 10 分钟无输出后终止；旧 `fig1_paperbanana_*.png` 仍含 PCD/three-gate，不得使用。`sync_overleaf.sh` 已加入 `figures/figure1_overview.png`，后续 push 会同步图。
- **2026-05-02 contribution wording patch 已完成**：self-evolving 已降为 future extension；Figure 1 标题/底层改为 `Reusable Solver Registry`；Method 新增 router/reusable registry 段；two-gate verifier 已限定为 primary deploy checks；NB/HMM 改称 structured-spec/backend sanity；LOO 6/6 降为 engineering sanity；mixed 主表删除 Route acc. 全 100 列并改报保守 aggregate 90.4% / 89.7%。2026-05-02 进一步做公式瘦身：删除 Method 中 `inductor recurrence / verifier indicator / empirical risk` 三个 theorem-like 公式，改成 prose + Algorithm；保留 PCD metric 公式和 DSL/op 定义公式作为诊断与接口锚点。
- **2026-05-02 bnlearn 核心 claim 已恢复并补 raw**：Tree 确认 bnlearn 是核心贡献后，不再撤掉 backend 100%。`verify_bnlearn_dsl_100.py` 在 2026-04-27 父节点顺序修复基础上，新增零概率 evidence skip、一次性 posterior VE、indexed/sparse factor multiply 和统一 `_meta` artifact；最新 raw `baselines/results/bnlearn_dsl_100q_seed2026_20260502.json` 为 4 个 bnlearn 网络各 100 条 finite query，Overall **400/400 = 100.0% [99.0,100.0]**，schema valid，0 API 成本。`paper/main.tex` 已改为：bnlearn 支撑 **structured deterministic backend exactness**，同时 PAL/LLM Compute 120-query stress test 仍显示大网络 codegen/compute 崩溃；明确不 claim bnlearn natural-language E2E。`run_bnlearn_held_out.py` 也同步修 `cpd.variables[1:]` 和 zero-prob evidence 过滤，避免未来 LLM/PAL 重跑混入旧 bug。
- **2026-05-03 bnlearn registry-supported NL E2E sanity 已补**：新增 `baselines/run_bnlearn_nl_e2e.py`，默认 registry 模式让 GPT-4o-mini 只解析 registered network/evidence/query，再用 deterministic DSL backend 求解；full-CPT 模式保留为压力测试（Asia/Child 可跑，Insurance 单题因超长 JSON parse fail，不作为主结果）。正式 raw `baselines/results/bnlearn_registry_e2e_80q_gpt4omini_20260503.json`：严格单标签 **79/80 = 98.8% [93.3,99.8]**，唯一 mismatch 是 Child `HypDistrib` 的 exact MAP tie（Equal=0.5, Unequal=0.5），tie-aware **80/80**，cost $0.0045。论文只作为 bounded registry sanity，不改主 claim。
- **2026-05-03 reviewer-gap 实验批次已跑完（暂不写进论文）**：按 Tree “先把 raw 都跑完，具体怎么加再讨论”的要求，补了 structured-output direct baseline、NB/HMM adversarial NL E2E 5 seed、NB/HMM inductor reliability、router 派生指标、QUITE direct baseline，并下载 QUITE / LLM-BI / DisCIPL-self-steering 相关代码数据。Manifest: `baselines/results/reviewer_gap_experiment_manifest_20260503.md`。关键 raw：structured direct `baselines/results/structured_direct_openai_gpt-4o-mini_20260503_102910.json`（overall **69/320=21.6%**；NB **23.3%**，HMM **40.0%**，BLInD depth-10 **1.0%**）；multi-seed E2E summary `baselines/results/adversarial_nl_e2e_multiseed_summary_20260503_183611.json`（NB pooled **545/600=90.8%**，HMM **488/500=97.6%**，overall **1033/1100=93.9%**）；reliability `baselines/results/inductor_reliability_nb_hmm_openai_gpt-4o-mini_20260503_183835.json`（first-pass **95/100=95.0%**，final **96/100=96.0%**）；QUITE direct `baselines/results/quite_direct_numeric-wep_openai_gpt-4o-mini_20260503_184206.json`（1154/1154 parsed，within 0.05 **27.7%**，MAE **0.365**）。验证：`python3 tests/test_dsl.py` 25/25 OK，`python3 tests/test_compiler.py` 13/13 OK，`python3 tests/test_equivalence_full.py` BLInD 900/900 + Flight 250/250 OK，`git diff --check` OK。

### 当前最高优先级 TODO

1. ~~Self-evolving 降调为未来愿景~~ ✅ 2026-05-02 已完成：只保留 reusable registry 主叙事，automatic self-evolving macro library 放 Future Work。
2. ~~Router / scope gate 方法段补齐~~ ✅ 2026-05-02 已完成：Method 增加 bounded router + reusable registry 段。
3. ~~Verifier claim 对齐~~ ✅ 2026-05-02 已完成：正文限定 two-gate 为 primary deploy checks；NB/HMM 改为 backend/reference sanity。
4. ~~Composition / generalization 降调~~ ✅ 2026-05-02 已完成：NB/HMM 改成 explicit TaskSpec + core-op-backed routes。
5. ~~理论公式降调~~ ✅ 2026-05-02 已完成：删除 Method 里 theorem-like 的 inductor/verifier/risk 公式，保留 PCD metrics + DSL/op definitions。
6. ~~LOO raw 决策~~ ✅ 2026-05-02 已完成：降调为 engineering sanity，不作为主 contribution；暂不重跑。
7. **剩余数字一致性 sweep**：PAL/bnlearn 主文措辞与 `\todo` macro 已修；还需全篇 sweep S5/S8/S10、成本倍数、baseline wording 等小数字。
8. **Claim/citation audit**：所有 contribution/theory wording patch 完后跑一次 zero-context paper-claim-audit，再做 citation-verifier。特别核 `lew2025discipl`、`schick2023toolformer`、匿名/代码发布 statement。
9. **最终机械收口**：本地 `latexmk -g -pdf`/grep 已通过一次，Figure 1 架构版和公式瘦身已编译通过并推 Overleaf；完成 claim/citation audit 后再 clean compile，并做 post-audit final push。
10. **主仓库整理**：当前 main repo 有大量 uncommitted/untracked results/scripts/paper changes；提交前需筛选保留新 full artifacts，旧 too-good mixed 仅归档或不进证据链。
11. **2026-05-03 叙事一致性 sweep（新增）**：正文已把“hand-written/backend/macro selector”风险表述改为“LLM-assembled TaskSpec / compiled solver / reusable templates”，并把 “all-family” 改为 “mixed input streams”；Abstract/Intro/Related Work 已补 Bayesian Teaching 对比，明确 Qiu et al. 的 Flight/Hotel 路线是 targeted fine-tuning，而本文固定模型权重，让 off-the-shelf LLM 写和组装可复用 `TaskSpec`，通过 deploy check 后复用 validated solver。Abstract 已融合老师版结构，保留 natural-language interface、per-instance tool-use contrast、compile-time vs run-time、three complementary evaluations，但不引入 `VSI/VSD` 新缩写。剩余待办：
   - **Figure 1 图中文字二次优化**：当前图整体正确，但图中仍有 “Validated Solver / LLM Inductor emit declarative TaskSpec” 这类中性表述；如继续打磨，建议改成 “Validated LLM-Assembled Solver / assemble solver spec” 以避免 reviewer 误解为手写 solver。
   - **图例和附录短标签 sweep**：主文仍有少量压缩标签如 “Our DSL / DSL backend”，空间允许时统一成 “LLM-assembled DSL solver / compiled solver”；若会造成图表拥挤，可保留短标签但 caption 必须解释清楚。
   - **真实性边界**：可以强 claim “LLM 组装 solver specification / route / typed-atom composition，deploy check 后复用”，但不要写成“raw Python solver source 全由 LLM 生成”。可信边界是：人定义 typed atoms/compiler 语义，LLM 选择并参数化组合，compiled solver 通过验证后缓存复用。
   - **PCD Compute 口径**：Preference Compute 的 prompt 输出 recommendation，不是完整 posterior 数值；论文必须表述为“self-computed posterior/EU implied recommendation”，BN/HMM/NB 概率型任务才是数值 posterior tolerance。
   - **最终 grep 口径**：投稿前 grep `all-family|six supported families|built-in macro|no-macro|macro selector|hand-computed|deterministic backend|three inference families|recommendation index|Gold expected utilities`，确保不会再出现会被 AI reviewer 直接复制成 weakness 的旧措辞。

## 一、核心思想（一段话版本）

LLM 能理解概率问题、能使用计算结果做决策，但无法可靠执行概率计算，且随问题复杂度增加崩溃到个位数。我们提出 PCD 诊断框架定位这一瓶颈，并用 typed DSL（7 core ops + 3 macros）+ 确定性编译器 + 2-Gate 验证器实现 "compile-once" 范式：LLM 做 family-level 的结构归纳（输出 TaskSpec JSON），之后实例由编译出的 solver 确定性求解。当前论文必须严格区分两层：backend exactness 是“给定有效 TaskSpec 后”的条件性结果；NL E2E 结果单独报告（Flight/Hotel/TextBandit/NB/HMM/all-family mixed）。

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
│  2-Gate Verifier │  Gate 1: Code Sanity → Gate 2: Ground Truth
└────────┬────────┘
         │
    pass → 部署 verified solver（零 LLM 成本）
    fail → diagnostics 反馈 Inductor → self-refine（最多 3 轮）
```

### DSL 两层结构

**Layer 1 — Core Typed Ops (7 个)**：`condition`, `multiply`, `marginalize`, `normalize`, `enumerate_hypotheses`, `expectation`, `argmax`

**Layer 2 — Family Macros (3 个语法糖)**：`softmax_pref`（假设枚举）、`beta_bernoulli`（共轭更新）、`ve_query`（变量消除）。Macros 非必需——held-out HMM 仅用 core ops 达到 100%。

---

## 三、已完成实验与证据（2026-05-02 更新）

| # | Evidence | 核心结论 | 数据规模 |
|---|----------|---------|---------|
| 1 | 23 策略消融 (Flight) | user_separate 74.8% = Oracle；纯 CoT 无效（≤33%） | 624 样本 × 5 轮 |
| 2 | 跨任务泛化 | Flight/Hotel/Bandit/BLInD 四个 family 全部 100% solver 精度 | 1,800+ 实例 |
| 3 | DSL 等价性 | DSL solver = 原始 solver，max error = 0.0 | 1,150 实例 |
| 4 | LOO 泛化 | 历史结果 6/6；若继续保留在论文 appendix，需补 `loo_2gate_*.json` raw 或降调 | 6 数据集 |
| 5 | PAL baseline | BN: PAL 26.4% vs Our 100%；偏好: PAL 29.3% vs Our 74.8% | 900+624 |
| 6 | 多模型 baseline | 最强模型 Opus=56.6% 仍远低于 Oracle 74.8% | 6 模型 |
| 7 | PCD 因果诊断 (BN) | Parse 96-100% / Compute 3-82% (depth-dependent) / Decide 100% | 900 样本 |
| 8 | 多模型 PCD | 6 模型 × 3 厂商全部展现相同 Parse 高/Compute 低/Decide 高 模式 | 6 模型 |
| 9 | Compile-time baseline | GPT-5.4=100%, GPT-4o=0%, Our(mini)=100% | 900 样本 |
| 10 | Verifier framing | 2026-04-28 pivot 后正文采用 2-Gate；旧 Gate 3 / gate3 ablation 不再作为主实验 | — |
| 11 | Claude Sonnet PCD | Parse=100%, Compute=64%, Decide=100%（偏好学习） | 200 样本 |
| 12 | **偏好学习 NL Parse** | 自然语言输入 Parse 89.5% / Compute 30.5% / Decide 100% | 200 样本 |
| 13 | **Flight 单 family E2E** | E2E 74.3% [70.9%,77.8%] ≈ Gold 74.4%，特征提取~100% | 624 样本 |
| 14 | DeLLMa 负面结果 | Compile-time solver ≈ 随机基线，精确刻画适用边界 | 20 样本 |
| 15 | Held-out NB adversarial NL E2E | Direct 44.0%；ours 91.7% [85.3,95.4]，full NL parse + deterministic solve | 120/200 样本口径见论文表 |
| 16 | Held-out HMM adversarial NL E2E | Direct 32.0%；ours 98.0% [93.0,99.4]，full NL parse + deterministic solve | 100 样本 |
| 17 | Cost curve | Our $0.008 vs PAL $2.50 (310×) vs Compile GPT-5.4 $0.11 (14×) | — |
| 18 | bnlearn 真实网络 | Structured DSL backend 400/400 finite queries；PAL/LLM Compute 在 ≥20 节点明显失效；registry-supported NL E2E sanity 79/80 strict（tie-aware 80/80），不是 open-ended full-CPT NL induction | 400 backend + 120 PAL/PCD + 80 registry E2E |
| 19 | **Hotel 单 family E2E** | Parse 100.0%；E2E 77.4% [70.2,85.5]；gold solver match 96.0% | 124 样本 |
| 20 | **TextBandit-style 单 family E2E** | Parse/spec 96.0%；E2E 96.0% [90.2,98.4]；4 个失败均为 observation-count | 100 样本 |
| 21 | **All-family mixed E2E** | 主表改报保守 aggregate：Overall 90.4% [88.0,92.4]；supported 89.7%；Route acc. 全 100 列已删除，只作为 bounded sanity | 670 aggregate 样本 |

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

> **2026-05-02 状态提醒**：本章从 2026-04-23 审查延续而来，很多条目已经被后续实验/论文重写覆盖。执行前先看文件顶部“2026-05-02 最新权威状态”。当前不要再把 Mixed E2E 视为待跑；full all-family mixed 已完成，raw runner 为 92.0%，论文主表改报保守 aggregate 90.4%。也不要再跑或引用 `test_gate3_ablation.py`；two-gate pivot 后该方向已废弃。

### 2026-04-23 最新讨论：100% framing + Mixed E2E

**问题**：论文里 100% 指标密度过高（DSL 等价性 / LOO 6/6 / Compute 100% / Held-out NB+HMM / bnlearn / Our DSL mini），审稿人第一眼会起疑 "cherry-picked / too clean"。Tree 担心所有指标都是 100% 不正常。

**共识（2026-04-23 讨论）**：
- 100% 分两类——**A 设计保证型**（确定性编译器 + 精确推理的数学性质，是 "compile once, reason exactly" 核心卖点，不能弱化）vs **B 需限定型**（scope 不清、n 太小，容易被攻击）
- **不能全换成端到端**，否则 "compile once, reason exactly" 标题和卖点同时塌
- 正确策略三件套：**把 E2E 数字放主位 + 所有 100% 加 scope 限定 + 扩端到端实验**

**老师建议的关键补实验已完成**：所有数据集混合后完整 agent 端到端效果（Mixed E2E）已跑 full all-family version。
- 当前论文主表：670 条保守 aggregate，Overall **90.4%** [88.0,92.4]；Supported **89.7%** [87.0,91.8]；Route acc. 列已删除，router 650/650 只作 bounded sanity。
- 解释口径：这是 bounded family set 下的完整系统跑通结果，证明 router + parser/spec induction + compiler + solver 可组合；unsupported 只覆盖小型 synthetic open-set，不能 claim comprehensive open-world solvability detection。
- 旧 90/90=100 和 50/50=100 结果已从论文删除，避免“单独不到 100、混合反而 100”的怪感。

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
- Mixed E2E: **已完成 mini full all-family 650**，cost $0.372；gpt-5.4 对照目前不必要，除非 final audit 要求 cross-model robustness
- Multi-model NL Parse: 3 模型 × 50 = 150 ≈ $2-4
- PAL self-repair: 300 (mini) ≈ $0.5
- Codex 审查 × 3 轮: ~15 调用 ≈ $10-20
- **本地 0 成本**: DSL verify / 等价性 / LOO dump JSON / test_equivalence_full

**预算分层**：
- **最小刚需**（不重跑 PCD 6 模型）：$30-55
- **推荐**：$50-80
- **完整含 PCD 重跑**：$100-180（>$100 需 Tree 明示同意）

**API 渠道**：OpenRouter（主力，所有论文实验）+ Codex MCP（独立审查，gpt-5.4 xhigh）+ 本机 Python + pgmpy（零成本）

### 2026-04-24 Codex Review 3 轮独立审查结论（⚠️ 待 Tree 战略决策）

**报告**: `paper/audits/2026-04-23-codex-review.md` (503 行，3 轮 verbatim)
**分数趋势**: Round 1 **5/10** → Round 2 **4.5/10** → Round 3 **4/10**（**持续下降，非改进饱和**）
**Codex 核心判决**: Master plan 作为 **scoped-down salvage plan 可执行**；作为保原强标题/强 contribution 的终极修复 **不可执行**。

#### Codex 识别的 3 条 CRITICAL（三轮稳定立场）

1. **artifact discipline 未设硬门槛**（Round 2 升级为 "NEW EVIDENCE OF EVASION"）
   - `paper/scripts/generate_figure3a_bnlearn.py:33` 仍硬编码 `our_dsl=[100,100,100,100]`
   - `rg prompt_tokens` 全仓零命中——成本/token trace 基础设施整个不存在
   - **行动**: 先定统一 raw schema（含 tokens/cost/model_id 强制字段）再允许任何新数字进论文

2. **C3 身份危机**
   - `taskspec/compiler.py:70` 仍 `return BNReferenceSolver()` —— "compile" 实为路由
   - 原论文 "compile-once solver induction" 叙事在代码层**站不住**
   - **行动**: 必须二选一—— (a) 论文降 scope 承认这是 "verified deterministic backend / family router"，或 (b) 真重构 TaskSpec + compiler 让 BN spec 参与编译（Codex 说 b 至少 2-4 天独立工作）

3. **C5/C6/S2 代码层零动作**
   - `inductor/inductor.py:35` 仍 `json.dumps(s)` 喂整个 sample
   - `inductor/prompts/induction_prompt.md:17` 仍显示 `reward_fn`
   - `tests/test_loo_induction.py:80` 仍 `samples[:k]` 两用
   - `verifier/gates.py:196` 仍 `passed = True`
   - **论文声称的 disjoint validation / Inductor reliability / LOO 6/6 在代码里根本不成立**

#### 12 决策点 Codex 共识（YES 7 / NO 4 / DEPENDS 3）

| # | 决策点 | 判定 |
|:-:|---|:-:|
| 1 | same-model 跨 method > 跨模型挑最好 | **YES**（前提 S4 先修 metric harmonization）|
| 2 | bnlearn 叙事选 C（都报，硬分层）| **YES** |
| 3 | 撤 C2 compositional generalization claim | **YES**（最多保留为 "core-ops-constrained codegen on synthetic NB/HMM"）|
| 4 | Mixed E2E 65-70% 够不够 | **DEPENDS**（足以撑诚实 scoped；不足救当前强版）|
| 5 | $30-55 预算够不够 | **DEPENDS**（够最小修补；不够同时 C3/C4 重构 + 全套 rerun）|
| 6 | 撤 vs 重跑附录 | **DEPENDS**（便宜的重跑；无法 regenerate 的撤，不要 "from prior logs" 当主证据）|
| 7 | C3 后置保原 story | **NO**（应先 scope down）|
| 8 | 新实验强制结构化 raw artifact | **YES**（没 raw 没 claim）|
| 9 | same-model 主表以 metric harmonization 为前置 | **YES** |
| 10 | bnlearn 15q/net 做最终主图 | **NO**（只够 smoke test，per-network 至少回到 30-50q/net）|
| 11 | LOO 6/6 + reliability 40/40 放 headline | **DEPENDS**（即便 survives 也适合 supporting，不该再 headline）|
| 12 | C2/C3 部分修保原 scope | **NO**（reviewer 会认为"语言降调结构不降调"）|

#### 5 条遗留分歧（Tree 裁决）

1. **bnlearn 去留**：保留做"DSL 数学正确性 + LLM compile_core_ops 诚实数字"，还是整个撤？
2. **C3 真修 vs 降 scope**：2-4 天重构 compiler 让 BN spec 真参与编译，还是直接降 scope 承认是 family router？
3. **NB/HMM 保留形式**：撤、改为 synthetic-only、还是降为附录？
4. **成本 claim**：$0.008/14× vs $0.001/60× 统一到哪套？（没 token trace 前任何 claim 都站不住）
5. ~~**Mixed E2E 时机**：现在跑（怕 scope 定错白跑），还是等 scope 定后再跑？~~ **已执行并写入论文；后续只做 claim audit，不再重跑，除非发现脚本错误。**

#### Codex 最终推荐：**投稿策略选项 2**

**立即降 scope 到 "PCD + verified deterministic backend"**：
- 改标题（去掉 "compile once / solver induction" 强 framing）
- 改 Contributions（承认 compile 是 family routing，不是 general TaskSpec→solver 编译）
- 删除 unsupported evidence（LOO headline 数字、compositional generalization claim、bnlearn 冒充 100%）
- **既不是转投 2027，也不是硬保原版**

#### 元反思（Codex 金句，写入 CLAUDE 项目记忆）

> **"claim-first, artifact-later 工作方式是核心病根。没有 raw 就没有论文句子；没有统一 metric 就没有比较表；没有 clean split 就没有 generalization claim。"**

#### 🎯 Tree 2026-04-24 指导原则（已授权）

> **"如果不影响结论的小数字都可以改。"**

含义：保 contribution + 小数字修成 raw 真实值 + overclaim 加 scope 限定。**不是**"降 scope 重写整个 framing"（Codex option 2 太保守），也**不是**"硬保原版"（风险过高）。

**Tree 已授权可直接改（不需再确认）**：

✅ **档 1 — 细节数字修正**（1 天工作量，纯找替换）:
- L602 "two parse failures" → "one parse failure"（raw `parse_success_rate=0.9984` 624 中 1 个）
- L339 "1,200 instances" → "1,150 instances"（已完成，当前论文使用 1,150）
- 成本 $0.008/14× vs $0.001/60× 统一到一套（带 token trace 后决定哪套）
- bib 作者修正 S6 S7（`lew2025discipl`、`jiang2026sok`、`schick2023toolformer`）
- CI 政策统一：BN 用 Wilson、bootstrap 仅用于 E2E、全文注 1 处说明

⚠️ **档 2 — overclaim 降调**（1-2 天，改 framing 不改 contribution）:
- Abstract + Intro "Parse ≥95%" → "primary families 82-100%; structured NB-family 3%"
- Abstract "Our DSL bnlearn 100%" → "verified deterministic backend reproduces exact VE posteriors (max_err < 1e-10 on hand-crafted factors); end-to-end LLM inductor→compile on bnlearn remains open"
- "Compositional generalization" → "core-ops-constrained codegen on synthetic NB/HMM tasks"
- "compile-once solver induction" → 标题保留，但 Contribution #1 改成 "family-level TaskSpec induction with verified deterministic backend"
- 100% claim 全局加 "on the compute stage, conditional on correct parsing"

❌ **档 3 — 仍需 Tree 单独拍板**（影响结论存否，不在自动授权范围）:
- figure 硬编码 `our_dsl=[100,100,100,100]` 删除 / 改成真数字 / 撤 Figure 3a → 这条**改了等于撤 bnlearn 主 claim**
- Inductor prompt scrub `reward_fn/answers/correct_diagnosis` → 改了重跑可能 LOO/E2E/reliability 数字**大幅掉点**
- LOO `samples[:k]` 拆独立 split → 同上，可能数字变脸
- Gate 2 `passed = True` 加阈值 → "6/6" 可能变成 "X/6"

→ 档 3 每一条都涉及 headline 数字可能变化，**Tree 要在"能接受多少头条数字下跌"的基础上决定**

**执行顺序**（Tree 回来拍板档 3 之前可并行做）:
1. 档 1 全部改（任何时候都能做，不依赖其他）
2. 档 2 降调（改 main.tex framing，不动代码）
3. 档 3 逐条 Tree 决定 → 可能触发重跑实验

#### 待决策时需看的材料
- `paper/audits/2026-04-23-codex-review.md` — 完整 503 行（3 轮 verbatim + P0-P5 优先级表）
- `paper/audits/2026-04-23-master-plan.md` — 原计划
- 10 条 Suspicions carry-forward 逐一核查清单（report 底部）

#### Codex Review 引入的新 Critical 编号

- **C9**（新）**artifact discipline 硬门槛**: 所有新 raw JSON 必须含 `prompt_tokens / completion_tokens / total_cost / model_id`；figure 脚本禁止硬编码，只能从 raw 读。**加入到 Layer 0 作为其他实验的前置条件**。
- 原 C1-C8 保留，但**执行顺序**应按 Codex 建议改为：
  - Layer 0': artifact schema + C5/C6/S2 + tiny rerun → **决定 title/scope** → full reruns → rewrite
  - 原 plan 的 Layer 0/1/2 线性推进被 Codex 标为"风险过高"

---

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
- **~~C8 TextBandit 50~~ → Serious**: 确认 test_equivalence_full 只有 BLInD 900 + Flight ~250 = 1,150；paper "1,200" 是 approximate 不精确。2026-05-02 已改为 1,150。

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
- [x] ~~**C4 Gate 3 假独立**~~ — **2026-04-28 framing pivot 后已废弃 Gate 3**；当前 verifier 是 2-Gate（Code Sanity + Ground Truth）。不要再重跑 Gate3-off；若保留 LOO 表，只需补 2-Gate raw JSON 或撤表。
- [ ] **C5 Inductor prompt 喂答案** — 原样 `json.dumps(sample)` 含 `reward_fn` / `answers` / `correct_diagnosis`；prompt 模板还显式要求看 `reward_fn`。**行动**: scrub prompt 输入只保留 task description + 重跑所有 inductor 实验
- [ ] **C6 LOO induction = verification（同样本两用）** — `samples[:k]` 既喂 induction 又做 verify，违反论文 L371-395 声明。**行动**: 拆独立 held-out split + 重跑 LOO
- [x] ~~**C7 LOO 6 数据集 raw 完全缺失**~~ — **2026-04-23 重新定性为"数据管理问题"**：数据集 **完整存在** 于 `data/eval/heldout/`（Hotel + flight_2/3/5/6/7/full_features.json，共 16MB）。问题是 `tests/test_loo_induction.py` 是 **pytest 只打 stdout 不存 JSON**，App Table L1121-1126 的 6 个 100% + checkmark 没有结构化 raw 留存。**行动**: 重跑一次 test_loo_induction 并 dump JSON 到 `baselines/results/loo_*.json` 即可（降级到 Serious-tier）
- [x] ~~**C8 TextBandit 50 samples 不存在**~~ — **2026-04-23 重新定性为"论文数字不精确"**：确认 `test_equivalence_full.py` 只有 BLInD 900 + Flight 前 50×~5 rounds≈250 比对 = **1,150**，TextBandit 不在 test 里。但这不是 fraud，是 paper "1,200" 的 approximate 描述。2026-05-02 已在论文中改为 "1,150"。

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

**历史估计**：6.5-12 天才能真正达到投稿水准。2026-05-02 后 Mixed E2E 和 Figure 1 架构替换已完成，剩余时间主要花在论文一致性、LOO raw、claim/citation audit 和 final compile/push。

### P0：论文架构改动（无需新实验，最高 ROI）

- [x] **Inductor 架构展开** — Section 4.4 扩写为 3 步 + Route Analysis 表 ✅ 2026-04-09
- [x] **Related Work 加 Skill 文献桥接** — 引 SoK + EvoSkills ✅ 2026-04-09
- [x] **叙述对齐** — Intro/Contribution/Held-Out/Conclusion 全部呼应 compositional generalization ✅ 2026-04-09
- [x] **"given a new task" 统一** — 替换所有 "a few examples" ✅ 2026-04-09
- [x] **Figure 1 重新生成** — 去掉 PCD 左面板，改为 router/scope gate + compile-once backend + self-evolving registry 三层架构图；当前正式本地图为 Imagen 架构候选，PaperBanana 新跑挂起未产图 ✅ 2026-05-02
- [x] **Figure 1 caption 更新** — 匹配新的 router-mediated reuse 架构图 ✅ 2026-05-02
- [ ] **考虑加 Figure 2(a) PCD 柱状图** — 如果 Figure 1 不再展示 PCD
- [ ] **引用修复** — 全面检查 references.bib 准确性（`curtis2025pomdp`/`lew2025discipl`/`first2025alphaverify` 有编造作者名和会议错）
- [ ] **术语统一** — compile-once vs compile-time、free code vs unconstrained
- [ ] **100% 清单扫描与 framing 分类** — 扫 main.tex 所有 "100%" 位置，按 [A:设计保证 / B:需 scope 限定 / C:需补实验] 三类标注，逐条定修改方案（2026-04-23 新增）
- [ ] **所有 B 类 100% 加 scope 限定** — Compute "on the compute stage, conditional on correct parsing"；LOO "first-round pass rate 6/6, n=6 held-out datasets"；Abstract L82 / Intro L117 / Conclusion L670 全覆盖（2026-04-23 新增）
- [x] **Abstract / Table 1 主位改报 E2E** — Flight/Hotel/TextBandit + all-family mixed 已进入主文；100% backend 结果已限定为 conditional/structured-input evidence（2026-05-02）

### P1：需要补充的实验

| 实验 | 回应的攻击点 | 估计耗时 |
|------|-----------|---------|
| ~~Mixed E2E benchmark~~ **已完成** — all-family mixed raw runner 650 条 overall 92.0%，但论文主表用 NB/HMM hard split 原始计数改报保守 aggregate 670 条 overall 90.4%、supported 89.7%，Route acc. 列删除；raw: `all_family_mixed_e2e_openai_gpt-4o-mini_20260502_221603.json` | 100% claim 可疑 + agent 完整性 | ✅ |
| ~~Per-family E2E 矩阵~~ **基本完成** — Flight 74.3%、Hotel 77.4%、TextBandit-style 96.0%；BLInD/NB/HMM 在 mixed/held-out 表覆盖，注意区分 backend vs NL E2E | E2E 覆盖面不足 | ✅ |
| **多模型 NL Parse** — GPT-4o/5.4/Claude 重跑偏好学习 NL Parse | 跨模型一致性 | 1 天 |
| ~~**bnlearn 扩样 / registry sanity**~~ **已完成** — backend 100 query/网络；registry-supported NL E2E 80q strict 98.8%，tie-aware 100%；full-CPT 转录只保留为压力测试 | 测试集太小 + bnlearn E2E 边界 | ✅ |
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
│   └── gates.py             # 2-Gate 验证（Code Sanity + Ground Truth）
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
│   ├── test_equivalence_full.py  # 全量等价性（1,150 实例）
│   ├── test_inductor_e2e.py      # 归纳器端到端（需 API）
│   └── test_loo_induction.py     # LOO 泛化（需 API；若保留 appendix 表需补 raw JSON）
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
- `tests/` 的 API 测试（inductor_e2e, loo_induction）需要 `OPENROUTER_API_KEY`

### 测试分层

| 层 | 文件 | 需要 API | 运行时间 |
|----|------|:--------:|---------|
| 单元 | test_dsl.py, test_compiler.py | 否 | <1s |
| 集成 | test_equivalence_full.py | 否 | ~2s（加载数据） |
| E2E | test_inductor_e2e.py | 是 | ~30s |
| 泛化 | test_loo_induction.py | 是 | ~2min；若论文保留 LOO 表，需改成 dump JSON |

本地修改后至少跑前两层确认不破坏。

---

## 常用命令

```bash
# 全部本地测试（不需要 API；使用 unittest/direct script，不依赖 pytest）
cd meta-skill && .venv/bin/python3 tests/test_dsl.py
cd meta-skill && .venv/bin/python3 -m unittest tests.test_compiler -v
cd meta-skill && .venv/bin/python3 tests/test_equivalence_full.py

# 需要 LLM API 的测试
cd meta-skill && .venv/bin/python3 tests/test_inductor_e2e.py
cd meta-skill && .venv/bin/python3 tests/test_loo_induction.py

# PCD 因果诊断
cd meta-skill/baselines && ../.venv/bin/python3 run_pcd_experiment.py --task both --model openai/gpt-4o-mini --n 200

# PAL baseline
cd meta-skill/baselines && ../.venv/bin/python3 run_pal_experiment.py --task bn --model openai/gpt-4o-mini

# Compile-time baseline
cd meta-skill/baselines && ../.venv/bin/python3 run_compile_time_baseline.py --model openai/gpt-5.4 --task bn --k 5

# 端到端实验
cd meta-skill && .venv/bin/python3 baselines/run_e2e_experiment.py --dataset flight --n 624 --concurrency 10 --model openai/gpt-4o-mini
cd meta-skill && .venv/bin/python3 baselines/run_e2e_experiment.py --dataset hotel --n 124 --concurrency 10 --model openai/gpt-4o-mini
cd meta-skill && .venv/bin/python3 baselines/run_textbandit_e2e.py --n 100 --concurrency 10 --model openai/gpt-4o-mini
cd meta-skill && .venv/bin/python3 baselines/run_all_family_mixed_e2e.py --n-per-family 100 --n-unsupported 50 --concurrency 10 --model openai/gpt-4o-mini

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
- **批量 LLM 调用强制并发**: 任何 ≥5 次 LLM API 调用的脚本必须用 `asyncio` + `AsyncOpenAI` + `asyncio.Semaphore(20-30)` 控制并发上限, **绝不允许 sync `for` 循环串行调用**. 实测对比 (2026-04-28 Tree 提醒)：
  - sync loop, 100 calls × ~5-8s/call = **8-13 min** (慢, 不可接受)
  - async semaphore=10, 100 calls = **84 sec** (实测 NB+HMM 50+50)
  - async semaphore=25-30, 100 calls = **~30-40 sec** (进一步 2× 快)
  - 默认 sema=25, 复杂 prompt 或 OpenRouter rate limit 紧时降到 10
  - 模板：见 `baselines/run_pcd_experiment.py` 的 `asyncio.gather` + Semaphore 用法
- API 统一走 OpenRouter（环境变量 `OPENROUTER_API_KEY`，HTTPS_PROXY 默认 `http://127.0.0.1:7897`）
- **Python 解释器必用 `.venv/bin/python3` 不用 system `python3`**（system 是 3.9, pgmpy 0.1.26 因 PEP 604 `int | float` syntax 报错）
- 每个功能点完成后 git commit
- 用 `python3` 不用 `python`
