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

## 五、已知弱点与待做

### 论文打磨（无需新实验）

- [ ] 检查引用准确性（curtis2025pomdp 作者名、lew2025discipl 会议）
- [ ] 统一术语（compile-once vs compile-time、free code vs unconstrained）
- [ ] 确保 100% claim 都有 "compute stage" 限定

### 需要补充的实验（按 ROI 排序）

| 优先级 | 实验 | 回应的攻击点 | 估计耗时 |
|:------:|------|-----------|---------|
| P0 | **多模型 NL Parse** — GPT-4o/5.4/Claude 重跑偏好学习自然语言 Parse | 跨模型一致性 | 1 天 |
| P1 | **bnlearn 扩样** — 30→100 query/网络 | 测试集太小 | 0.5 天 |
| P1 | **PAL + self-repair** — 给 PAL 加 3 轮 self-repair | baseline 不公平 | 1 天 |
| P2 | **DSL ablation** — no macros / no verifier / no self-refine 对比 | gain 来源不清 | 1 天 |
| P2 | **ProbLog/pgmpy baseline** — 直接调 ProbLog/pgmpy | "直接调库就行" | 1 天 |
| P3 | **QUITE benchmark** — 30 个真实 BN，1,192 premises | 外部效度 | 2 天 |
| P3 | **贵模型旁路注入** — gpt-4o / claude-sonnet-4 | Phase 1 遗留 | 1 天 |

### 更长远方向

- 连续分布 + 近似推理（MCMC/VI 后端）
- 自动 DSL 扩展（发现新算子）
- 与 Agent 框架集成（solver as tool）
- 跨任务泛化（hotel/webshop）

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

## 七、常用命令

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

## 八、与父项目的关系

本项目（`meta-skill/`）是 `bayes/` 项目的核心子项目：

- **父项目 `bayes/bayesclaudecode/`**：Phase 1 贝叶斯旁路注入实验，23 种策略消融。提供了 Evidence 1（策略梯度）和 Evidence 6（多模型 baseline）的数据。
- **共享数据**：`bayes/data/eval/interaction/`（Flight 624 条、Hotel 124 条）
- **外部数据**：`BLInD/`（BN 推断 900 题）、`TextBandit/`（多臂赌博机）、`DeLLMa/`

---

## 九、飞书文档

- **文档名称**: Bayes 项目概览 — 贝叶斯教学与LLM概率推理
- **文档 ID**: `AcOIdoE0Gop4mexsificXAWbnNg`
- **所在文件夹 Token**: `Y59JfVFEClsLKqdXViOcA3h6n0d`

---

## 十、编码规范

- 注释语言：中文
- 新代码放在 `meta-skill/` 目录下
- 并发优先：asyncio + AsyncOpenAI
- API 统一走 OpenRouter
- 每个功能点完成后 git commit
- 用 `python3` 不用 `python`
