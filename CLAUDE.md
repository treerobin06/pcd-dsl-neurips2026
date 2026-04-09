# Bayesian Teaching 研究项目

> **最后更新**: 2026-04-09

## 项目概述

基于论文 "Bayesian Teaching Enables Probabilistic Reasoning in Large Language Models" (Qiu et al., 2026, Nature Communications)，研究如何提升 LLM 的概率推理能力。

**当前核心工作 → `meta-skill/`**：NeurIPS 2026 论文 "Compile Once, Reason Exactly"。详细状态请阅读 **`meta-skill/CLAUDE.md`**。

---

## 项目结构

```
bayes/
├── meta-skill/          ← 【当前核心】NeurIPS 论文 + DSL/Compiler/Inductor/Verifier 系统
│   ├── CLAUDE.md        ← 项目权威文档（优先阅读这个）
│   ├── dsl/             # 概率 DSL（7 core ops + 3 macros）
│   ├── taskspec/        # TaskSpec IR + 确定性编译器
│   ├── inductor/        # LLM 归纳器
│   ├── verifier/        # 3-Gate 验证器
│   ├── solvers/         # Gold reference solvers
│   ├── baselines/       # PCD/PAL/Compile-time/E2E 实验
│   ├── tests/           # 测试套件
│   └── paper/           # NeurIPS 论文 (main.tex)
├── bayesclaudecode/     # Phase 1：23 策略旁路注入消融实验（已完成，提供 Evidence 1/6）
├── data/                # 共享数据集（Flight 624 条, Hotel 124 条）
├── 文档/                # Phase 1 实验报告和设计文档（Obsidian 格式）
├── BLInD/               # 外部数据：BN 推断 900 题
├── TextBandit/          # 外部数据：多臂赌博机
├── DeLLMa/              # 外部数据：农业决策（边界测试）
├── thesis/              # 毕业论文
└── LLM服从性研究/        # 服从性分析（辅助研究）
```

---

## Phase 1（已完成）：贝叶斯旁路注入

**核心发现**：通过 23 种策略的系统消融（624 样本 × 5 轮），证明了：
- LLM 概率推理准确率随辅助信息增加而单调提升（33% → 74.8%）
- 纯 CoT 完全无效（≤33%，低于随机基线）
- Tool calling > Prompt injection（同内容 +8~18pp）
- user_separate = Oracle = 74.8%（LLM 100% 跟从正确推荐）

这些发现直接驱动了 Phase 2 的设计：既然 LLM 能理解但不能计算，就把计算外包给确定性 solver。

**代码**: `bayesclaudecode/`
**实验报告**: `文档/` 目录下的 Obsidian 笔记

### 策略排名（GPT-4o-mini, 624 样本）

| 排名 | 策略 | 类型 | 准确率 |
|------|------|------|--------|
| 1 | tool_use | 工具调用 | 58.3% |
| 2 | tool_nl_pref_rec | 工具调用 | 56.8% |
| 3 | tool_direct_rec | 工具调用 | 53.5% |
| 4 | full_math | Prompt 注入 | 49.9% |
| 5 | cot_then_math | 混合 | 49.5% |
| ... | ... | ... | ... |
| 10 | baseline | 对照组 | 36.6% |
| 14-18 | 纯 COT (4种) | 纯 COT | 32-33% |

完整 18 策略表、Content×Channel 矩阵、各实验详细结果见 `文档/` 目录。

---

## Phase 2（进行中）：Compile-Once Solver Induction

**→ 详见 `meta-skill/CLAUDE.md`**

核心方法：PCD 诊断 + typed DSL + 确定性编译器 + 3-Gate 验证器

关键成果：
- 6 模型 × 3 厂商的一致 PCD 模式（Parse 高/Compute 低/Decide 高）
- GPT-4o-mini 通过 DSL 达到 100% compute 精确度（$0.008）
- 5 个 inference family（含 2 个 held-out）全部 100%
- E2E 74.3% ≈ Gold 74.4%

---

## 评估指标

1. **准确率 (Accuracy)**: LLM 选择与用户最优一致的比例
2. **服从率 (Compliance)**: LLM 选择与贝叶斯推荐一致的比例
3. **PCD**: Parse / Compute|GoldParse / Decide|GoldPosterior
4. **Bootstrap 95% CI**: 2000 次重采样

**贝叶斯助手 Oracle**: R1: 30.3% → R5: 74.8%

---

## 飞书文档

- **文档 ID**: `AcOIdoE0Gop4mexsificXAWbnNg`
- **文件夹 Token**: `Y59JfVFEClsLKqdXViOcA3h6n0d`

## 编码规范

- 注释语言：中文
- Phase 1 代码在 `bayesclaudecode/`，Phase 2 代码在 `meta-skill/`
- 并发优先：asyncio + AsyncOpenAI
- API 统一走 OpenRouter
- 用 `python3` 不用 `python`
