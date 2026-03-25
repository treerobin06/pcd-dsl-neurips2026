# Inducing Verifiable Probabilistic Solvers for LLM Reasoning

## 项目概述

论文核心：LLM 能理解概率问题（Parse ~98%）但无法可靠执行概率计算（Compute ~22%），也能正确使用计算结果做决策（Decide 100%）。我们提出概率 DSL + 确定性编译器 + verifier-guided inductor，让便宜模型 (GPT-4o-mini) 自动为新任务生成经过验证的 exact solver。

**论文 Framing**: LLM 擅长归纳概率程序，不擅长可靠执行概率计算。我们的 DSL+Compiler 是一个可验证的概率 meta-skill 接口——诊断瓶颈、形式化消除、注入结果。

## 代码结构

```
meta-skill/
├── dsl/                        # 概率 DSL 库
│   ├── types.py                # 类型系统（Probability, Distribution, Factor 等）
│   ├── core_ops.py             # 7 个核心运算（normalize, multiply_dist, marginalize 等）
│   └── family_macros.py        # 3 个 family macro（softmax_pref, beta_bernoulli, ve_query）
├── taskspec/
│   ├── schema.py               # TaskSpec JSON schema（声明式 IR）
│   └── compiler.py             # TaskSpec → Solver 确定性编译器
├── inductor/
│   ├── inductor.py             # LLM 分析样本 → TaskSpec
│   ├── refiner.py              # Verifier 反馈 → self-refine 循环
│   └── prompts/                # Induction prompt 模板
├── verifier/
│   └── gates.py                # 3-Gate 验证（Code Sanity / Ground Truth / Reference Match）
├── solvers/                    # Gold reference solvers
│   ├── preference_solver.py    # 偏好学习（hypothesis_enumeration）
│   ├── bn_solver.py            # BN 推断（variable_elimination）
│   └── bandit_solver.py        # Bandit（conjugate_update）
├── baselines/                  # Baseline 实验
│   ├── run_pcd_experiment.py   # Parse/Compute/Decide 因果诊断
│   ├── run_pal_experiment.py   # PAL baseline（LLM → Python）
│   ├── run_compile_time_baseline.py  # Compile-time matched baseline
│   └── results/                # 实验结果 JSON
├── tests/                      # 40+ 测试
│   ├── test_dsl.py             # DSL 单元测试 + 等价性验证
│   ├── test_compiler.py        # Compiler 测试
│   ├── test_equivalence_full.py  # 全量等价性
│   ├── test_inductor_e2e.py    # Inductor 端到端（需 API）
│   ├── test_loo_induction.py   # LOO 泛化验证（需 API）
│   └── test_gate3_ablation.py  # Gate 3 off ablation（需 API）
├── DESIGN.md                   # 系统架构设计
├── ROADMAP.md                  # 执行路线图
├── CONTEXT.md                  # 资源路径索引
└── 2026-03-13-EVIDENCE_SUMMARY.md  # 全部实验证据汇总
```

## 常用命令

```bash
# 全部本地测试（不需要 API）
cd meta-skill && python -m pytest tests/test_dsl.py tests/test_compiler.py tests/test_equivalence_full.py -v

# 需要 LLM API 的测试
cd meta-skill && python -m pytest tests/test_inductor_e2e.py -v
cd meta-skill && python -m pytest tests/test_loo_induction.py -v
cd meta-skill && python tests/test_gate3_ablation.py

# PCD 因果诊断
cd meta-skill/baselines && python run_pcd_experiment.py --task both --model openai/gpt-4o-mini --n 200
cd meta-skill/baselines && python run_pcd_experiment.py --task bn --model anthropic/claude-sonnet-4

# PAL baseline
cd meta-skill/baselines && python run_pal_experiment.py --task bn --model openai/gpt-4o-mini

# Compile-time baseline
cd meta-skill/baselines && python run_compile_time_baseline.py --model openai/gpt-5.4 --task bn --k 5
```

## 核心架构

```
新任务样本 (3-5 个)
       │
       ▼
┌─────────────────┐
│  LLM Inductor   │  分析样本 → 输出 TaskSpec (JSON)
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
│  3-Gate Verifier │  Gate 1: Code Sanity → Gate 2: Ground Truth → Gate 3: Reference Match
└────────┬────────┘
         │
    pass → 输出 verified solver
    fail → diagnostics 反馈 Inductor → self-refine
```

- **DSL**: 7 core ops + 3 family macros，macros 是 core ops 的语法糖
- **TaskSpec**: 声明式 JSON，LLM 只需填写字段，不写代码
- **Compiler**: 确定性编译，`compiler(gold_spec) == gold_solver`
- **Gate 3 是可选的**: Gate 1+2 即可保证正确性（已通过 ablation 验证）

## 当前状态与已有证据（13 项）

| # | Evidence | 结论 | 状态 |
|---|----------|------|------|
| 1 | 23 策略消融 | user_separate 74.8% = Oracle，纯 COT 无效 | 完成 |
| 2 | 跨任务泛化 | Flight/Hotel/Bandit/BLInD 四个 family 100% | 完成 |
| 3 | DSL 等价性 | DSL solver = 原始 solver，误差 0.0 | 完成 |
| 4 | LOO 泛化 | 6/6 held-out 数据集第 1 轮通过 | 完成 |
| 5 | PAL baseline | PAL=26.4% vs Our=100% (BN) | 完成 |
| 6 | 多模型 baseline | claude-opus 56.6%, gpt-5.4 49.2%，都远低 Oracle | 完成 |
| 7 | PCD 因果诊断 (BN) | Parse 96-100% / Compute 11-81% / Decide 100% — 瓶颈在计算 | 完成 |
| 8 | 多模型 PCD | GPT-4o-mini/4o/5.4/Sonnet/Gemini/Opus 全部展现相同退化模式 | 完成 |
| 9 | Compile-time BL | GPT-5.4=100%, GPT-4o=0%, Our(mini)=100% | 完成 |
| 10 | Gate 3 Off | 6/6 通过，Gate 3 非必需，无数据泄漏 | 完成 |
| 11 | 非 OpenAI PCD | Claude Sonnet: Parse=100%, Compute=64%, Decide=100% | 完成 |
| 12 | **偏好学习 NL Parse** | **Parse 89.5% / Compute 30.5% / Decide 100%（从自然语言提取，非数值化输入）** | **2026-03-25 完成** |
| 13 | **端到端链路实验** | **E2E 74.3% [70.9%,77.8%] ≈ Gold Pipeline 74.4%，特征提取~100%，与Gold Solver 99.8%一致** | **2026-03-25 完成** |

### 2026-03-25 重要变更：偏好学习 Parse 实验重做

**问题**：原 Parse 实验给 LLM 的输入是已数值化的特征（`rounds_numpy` 格式如 `departure_time=0.50`），不是 Nature 原文使用的自然语言（`departure time: 02:00 PM`）。Parse 测试几乎 trivial——LLM 只需看正负号。

**修改**：重写 `pcd_parse_preference.md` 和 `build_pref_parse_prompt()`，改用 `rounds[].options` 的原始自然语言格式。LLM 现在需要从 "02:00 PM" 提取为 14.0、从 "$370" 提取为 370 等。

**新结果**（GPT-4o-mini, 200 样本）：Parse 89.5% / Compute 30.5% / Decide 100%。核心结论"瓶颈在计算"不变。

**修改文件**：
- `baselines/prompts/pcd_parse_preference.md`（重写模板）
- `baselines/run_pcd_experiment.py`（`build_pref_parse_prompt` 改用 NL, `eval_pref_parse` 改用近似数值匹配, `compute_preference_gold` 加入 `_sample_rounds`, 数据路径修正）

## Codex Review 评分

- **Round 1** (证据完备性): 6.7/10
- **Round 2** (实验设计+贡献): 5.5/10 → reframe 后 6.5/10
- **目标**: 7+/10 (NeurIPS borderline)

## 待补实验（按优先级）

1. ~~**偏好学习 NL Parse**~~ — ✅ 已完成 (2026-03-25)
2. **多模型 NL Parse** — 用 GPT-4o / GPT-5.4 / Claude Sonnet 重跑偏好学习 NL Parse，验证跨模型一致性
3. ~~**端到端链路实验**~~ — ✅ 已完成 (2026-03-25)：E2E 74.3% ≈ Gold 74.4%
4. **Fig 2 + Fig 3(a) 合并** — 考虑将 BLInD depth 曲线与 bnlearn 扩展性柱状图合成一个 Figure
5. **DSL ablation** — 无 macros / 无 verifier / 无 self-refine 的对比
6. **NeurIPS 论文更新** — 偏好学习 Parse 数据更新为 NL 版本，明确区分"Compute 精确度"和"端到端精确度"

## 与父项目的关系

- **父项目**: `bayes/`（Phase 1 贝叶斯旁路注入，23 种策略消融）
- **共享数据**: `bayes/data/eval/interaction/`（Flight, Hotel）
- **共享代码**: `bayes/bayesclaudecode/`（BayesianSidecar, PromptInjector）
- **外部数据**: `BLInD/`（BN 推断 900 题），`TextBandit/`（多臂赌博机）

## 编码规范

- 继承父项目：中文注释、asyncio 并发、OpenRouter API
- 新代码放 `meta-skill/` 目录下
- DSL 原语有完整类型标注和单元测试
- Gold reference solvers 只调用 DSL 原语
