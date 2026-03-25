# Bayesian Teaching 研究项目

## 项目概述

基于论文 "Bayesian Teaching Enables Probabilistic Reasoning in Large Language Models" (Qiu et al., 2026, Nature Communications)，研究如何提升 LLM 的概率推理能力。

**核心研究方向 — 贝叶斯旁路注入 (Bayesian Sidecar Injection)**：不微调 LLM 本身，通过在 prompt 或工具调用中注入纯算法贝叶斯助手的分析结果，提升任意闭源/开源模型的概率推理能力。

## 当前进展 (2026-03-25 更新)

### 已完成实验

| # | 实验 | 样本 | 模型 | 策略数 | 状态 |
|---|------|------|------|--------|------|
| 0 | [[Baseline实验结果汇总\|Baseline 多模型评测]] | 624 | 5+ 模型 | 1 (无注入) | 已完成 |
| 1 | Phase 1 快速验证 | 50 | gpt-4o-mini | 5 | 已完成 |
| 2 | [[Phase2旁路注入实验分析报告\|Phase 2 全量实验]] | 624 | 3 模型 | 6 | 已完成 |
| 3 | [[COT补充实验分析报告\|COT 补充实验]] | 624 | gpt-4o-mini | 7 | 已完成 |
| 4 | [[Tool-Calling内容消融实验报告\|Tool Calling 消融实验]] | 624 | gpt-4o-mini | 5 | 已完成 |
| 5 | PCD 诊断（6 模型 × 偏好学习 + BN） | 200+900 | 6 模型 | — | 已完成 |
| 6 | 求解器诱导 + DSL 等价性 | 2,118 | — | — | 已完成 |
| 7 | 46 模型大规模 Baseline | 624 | 46 模型 | 1 | 已完成 |
| 8 | **偏好学习 NL Parse 重做** | 200 | gpt-4o-mini | — | **2026-03-25 完成** |

### 2026-03-25 重要变更

**偏好学习 Parse 实验已从数值化输入改为自然语言输入**。原实验给 LLM 看 `departure_time=0.50` 这样的数字，新实验给 LLM 看 `departure time: 02:00 PM, duration: 30 min, price: $370` 这样的自然语言。新结果：Parse 89.5% / Compute 30.5% / Decide 100%，核心结论不变。

### 待做
- [ ] 多模型 NL Parse（GPT-4o/5.4/Claude Sonnet 重跑偏好学习 NL Parse）
- [x] 端到端链路实验（NL → LLM Parse → 求解器 → 答案的完整准确率）— E2E 74.3% ≈ Gold 74.4%
- [ ] NeurIPS 论文更新偏好学习 Parse 数据
- [ ] Fig 2 + Fig 3(a) 合并评估
- [ ] 贵模型旁路注入实验（gpt-4o, claude-sonnet-4）
- [ ] 跨任务泛化测试（酒店/网购）

---

## 一、数据集

> 详见 [[数据集说明]]

- **来源**: 论文官方 Zenodo 数据集
- **主实验数据**: `bayes/data/eval/interaction/flight.jsonl`（624 条 × 5 轮交互）
- **任务**: 航班推荐 — 用户有隐藏偏好（4 个特征的线性权重），每轮从 3 个航班中选择，LLM 需推断偏好并推荐
- **特征**: departure_time, duration, number_of_stops, price
- **偏好值**: {-1, -0.5, 0, 0.5, 1}，624 = 5⁴ - 1 种不同偏好函数的完全覆盖

其他数据集（未使用）：hotel.jsonl（酒店推荐）、webshop/（网购）、flight_human.jsonl（真人偏好）

---

## 二、实验总览

### 全 18 策略统一排名（GPT-4o-mini, 624 样本 × 5 轮）

| 排名 | 策略 | 类型 | 准确率 | R5 | 服从率 | 调用率 | 实验来源 |
|------|------|------|--------|-----|--------|--------|---------|
| 1 | **tool_use** | 工具调用 | **58.3%** | 73.2% | 89.9% | ~100% | COT 补充 |
| 2 | **tool_nl_pref_rec** | 工具调用 | **56.8%** | 70.4% | 85.9% | 99.6% | Tool 消融 |
| 3 | **tool_direct_rec** | 工具调用 | **53.5%** | 68.8% | 81.6% | 99.4% | Tool 消融 |
| 4 | full_math | Prompt 注入 | 49.9% | 64.1% | 67.7% | - | Phase 2 |
| 5 | cot_then_math | 混合策略 | 49.5% | 58.3% | 68.7% | - | COT 补充 |
| 6 | tool_nl_pref | 工具调用 | 41.8% | 42.1% | 43.0% | 99.4% | Tool 消融 |
| 7 | math_then_cot | 混合策略 | 40.9% | 54.2% | 49.0% | - | COT 补充 |
| 8 | nl_pref_rec | Prompt 注入 | 38.8% | 37.5% | 51.3% | - | Phase 2 |
| 9 | tool_empty | 工具控制组 | 37.1% | 37.8% | 37.1% | 99.2% | Tool 消融 |
| 10 | baseline | 对照组 | 36.6% | 36.5% | 36.9% | - | Phase 2 |
| 11 | tool_random_rec | 工具控制组 | 36.3% | 37.7% | 36.0% | 99.3% | Tool 消融 |
| 12 | direct_rec | Prompt 注入 | 34.8% | 33.5% | 39.5% | - | Phase 2 |
| 13 | random_rec | 对照组 | 33.5% | 30.4% | 33.7% | - | Phase 2 |
| 14~18 | 纯 COT (4种) + few_shot | 纯 COT | 32~33% | 29~32% | 31~33% | - | COT 补充 |

### 注入策略全览（18 种）

#### Phase 2: 外部算法注入（6 种） ^phase2-strategies
| 策略 | 注入内容 |
|------|---------|
| baseline | 无注入（对照组） |
| direct_rec | 仅推荐 "Bayesian analysis suggests Flight X" |
| nl_preference | 自然语言偏好描述 |
| nl_pref_rec | 自然语言偏好 + 推荐 |
| full_math | 完整数学分析（权重、概率、期望效用） |
| random_rec | 随机推荐控制组 |

#### COT 补充实验（7 种） ^cot-strategies
| 策略 | 方向 | 做法 |
|------|------|------|
| cot_reflect | 纯提示词 | 要求 LLM 先分析用户偏好模式再选择 |
| cot_bayesian | 纯提示词 | 教 LLM 贝叶斯更新步骤（不给结果） |
| few_shot | 纯提示词 | 给 2 个偏好推理范例 |
| tool_use | 工具调用 | function calling API，LLM 自主调用贝叶斯工具 |
| cot_then_math | 混合 | 两步对话：先 COT 再展示 full_math |
| cot_self_consistency | 混合 | 5 路并发推理 + 多数投票 |
| math_then_cot | 混合 | 先展示 full_math，再批判性评估 |

#### Tool Calling 内容消融（5 种） ^tool-ablation-strategies
| 策略 | 工具返回内容 | 对应 Prompt 版本 |
|------|-------------|-----------------|
| tool_direct_rec | 仅推荐 | direct_rec |
| tool_nl_pref | 自然语言偏好 | nl_preference |
| tool_nl_pref_rec | 偏好 + 推荐 | nl_pref_rec |
| tool_random_rec | 随机推荐 | random_rec |
| tool_empty | "无法提供建议" | 无 |

---

## 三、各实验详细结果

### 实验 0: Baseline 多模型评测

> 详见 [[Baseline实验结果汇总]] [[全模型Baseline对比总结]]

624 样本，无任何注入，测试各模型的"裸"概率推理能力。

| 模型 | 准确率 | 备注 |
|------|--------|------|
| gpt-4o | 44.68% | 最佳 |
| gpt-5.2 | 43.49% | |
| gpt-4.1 | 37.44% | |
| gpt-4o-mini | 37.02% | 后续实验主力模型 |
| gpt-4.1-nano | 31.70% | 低于随机基线 |
| 随机基线 | 33.33% | |

### 实验 2: Phase 2 全量旁路注入

> 详见 [[Phase2旁路注入实验分析报告]] [[Phase2实验报告_20260307]]
> 设计文档 [[贝叶斯旁路注入-设计文档]] [[贝叶斯旁路注入-实施计划]]

624 样本 × 3 模型 × 6 策略。核心发现：

1. **full_math 在所有模型上最佳**: gpt-4o-mini +13.3pp, deepseek +12.7pp, qwen +2.6pp
2. **random_rec 控制组有效**: 与 baseline 无显著差异，排除盲目服从假说
3. **模型可教性差异巨大**: gpt-4o-mini >> deepseek >> qwen
4. **贝叶斯助手自身 R5 准确率 74.8%**，gpt-4o-mini + full_math 利用到 64.1%

### 实验 3: COT 补充实验

> 详见 [[COT补充实验分析报告]]
> 设计文档 [[COT补充实验-设计文档]] [[COT补充实验-实施计划]]

624 样本 × gpt-4o-mini × 7 新策略。核心发现：

1. **tool_use (Function Calling) 最优**: 58.3%，比 full_math 高 8.4pp
2. **纯 COT 完全无效**: 4 种纯 COT 策略均低于 baseline
3. **主动工具调用 >> 被动信息注入**: LLM 主动请求的信息利用率更高
4. **COT 顺序影响大**: cot_then_math (49.5%) >> math_then_cot (40.9%)

### 实验 4: Tool Calling 内容消融

> 详见 [[Tool-Calling内容消融实验报告]]
> 设计文档 [[Tool-Calling内容消融实验-设计文档]] [[Tool-Calling内容消融实验-实施计划]]

624 样本 × gpt-4o-mini × 5 新 tool_* 策略。核心发现：

1. **通道增益因内容而异**: 中等内容获益最大 (direct_rec: +18.7pp)，最丰富反而最小 (full_math: +8.4pp)
2. **对无用内容几乎无增益**: tool_random_rec (+2.8pp) ≈ tool_empty ≈ baseline
3. **服从率是关键中介**: Function calling 将 direct_rec 服从率从 39.5% 提升到 81.6%
4. **工具调用率不受返回质量影响**: 所有 tool_* 策略调用率均 ~99%
5. **简单内容即可接近最优**: tool_nl_pref_rec (56.8%) 接近 tool_use (58.3%)

**2D 内容 × 通道矩阵:**

| 内容 | Prompt | Function Calling | 通道增益 |
|------|--------|-----------------|---------|
| random_rec | 33.5% | 36.3% | +2.8pp |
| direct_rec | 34.8% | **53.5%** | **+18.7pp** |
| nl_preference | 32.5% | 41.8% | +9.4pp |
| nl_pref_rec | 38.8% | **56.8%** | **+18.0pp** |
| full_math | 49.9% | **58.3%** | +8.4pp |

---

## 四、评估指标

1. **准确率 (Accuracy)**: LLM 选择与用户最优航班一致的比例
2. **服从率 (Compliance/Follow Rate)**: LLM 选择与贝叶斯推荐一致的比例
3. **FwC/FwW**: 贝叶斯正确/错误时的服从率，校准分 = FwC - FwW
4. **工具调用率 (Tool Call Rate)**: LLM 选择调用工具的比例（仅 tool_* 策略）
5. **Bootstrap 95% CI**: 2000 次重采样的置信区间

**贝叶斯助手 Oracle 表现:** R1: 30.3% → R2: 56.6% → R3: 65.9% → R4: 70.2% → R5: 74.8%

---

## 五、文档索引

### 论文与背景

| 文档 | 内容简介 |
|------|---------|
| [[论文详细介绍]] | 原论文 (Qiu et al., 2026) 的完整解读：研究动机、Bayesian Teaching 方法、实验设计、主要发现 |
| [[引用分析报告]] | 引用本论文的 12 篇后续工作的分类分析：概率推理、人格模拟、主动学习等方向 |
| [[论文评审报告]] | 对某篇 LLM 综述论文的学术评审练习 |
| [[代码与数据生成说明]] | 原论文开源资源（GitHub/Zenodo）+ 贝叶斯助手算法的数学原理 |

### 数据

| 文档 | 内容简介 |
|------|---------|
| [[数据集说明]] | flight.jsonl 的生成方式、字段含义（idx/reward_fn/features/rounds/rounds_numpy）、624 = 5⁴-1 的完全覆盖设计 |
| [[数据分析总结]] | 数据文件层次结构、train/eval 划分、各评估数据集的统计信息 |

### 实验计划

| 文档 | 内容简介 |
|------|---------|
| [[实验计划_全面版]] | 49 模型全面 benchmark 方案（未全部执行） |
| [[实验计划_千问版]] | 以千问系列为主 + 经典对照的精简方案 |
| [[实验差距分析]] | 已完成实验与计划之间的 gap analysis |

### 实验报告

| 文档 | 内容简介 |
|------|---------|
| [[Baseline实验结果汇总]] | 46 个模型的 baseline 准确率排行榜（100 样本 × 5 轮） |
| [[全模型Baseline对比总结]] | 5 个核心模型的 624 样本 baseline 横向对比 + 学习曲线分析 |
| [[Phase2旁路注入实验分析报告]] | Phase 2 的完整分析：6 策略 × 3 模型、控制组验证、可教性排名、信任校准 |
| [[Phase2实验报告_20260307]] | Phase 2 的机器生成数据报告（表格为主） |
| [[Phase2实验报告_20260308]] | Phase 2 的补充报告 |
| [[COT补充实验分析报告]] | 13 种策略完整消融：纯 COT 无效、tool_use 最优、顺序效应分析、6 张图表 |
| [[Tool-Calling内容消融实验报告]] | **最新** — 内容×通道 2D 消融矩阵、服从率中介效应分析、6 张图表、逐步操作说明 |
| [[LLM服从性测试报告]] | 各策略 LLM 服从率的独立分析 |

### 设计文档

| 文档 | 内容简介 |
|------|---------|
| [[贝叶斯旁路注入-设计文档]] | Sidecar Injection 的整体架构：BayesianSidecar + PromptInjector + AsyncRunner |
| [[贝叶斯旁路注入-实施计划]] | 代码实施的逐步计划（TDD 风格） |
| [[COT补充实验-设计文档]] | 7 种 COT 策略的设计思路和预期假说 |
| [[COT补充实验-实施计划]] | COT 策略的代码实施步骤 |
| [[Tool-Calling内容消融实验-设计文档]] | 5 种 tool_* 策略的设计：统一工具定义、只变返回内容 |
| [[Tool-Calling内容消融实验-实施计划]] | Tool 消融策略的代码实施步骤 |

### 技术参考

| 文档 | 内容简介 |
|------|---------|
| [[Baseline运行指南]] | 如何运行 baseline 评估脚本（多种方式：OpenRouter/Gemini/HuggingFace/vLLM） |
| [[OpenRouter并行调用参考]] | OpenRouter API 的并发限制、重试策略、最佳实践 |

---

## 六、代码结构

```
bayes/bayesclaudecode/               # 主力实验代码
├── bayesian_sidecar.py              # 纯算法贝叶斯推理引擎（后验更新、推荐、偏好描述）
├── prompt_injector.py               # 18 种注入策略 + format_tool_response
├── run_sidecar_experiment.py        # asyncio 异步实验主脚本（断点续传、Bootstrap CI）
├── test_bayesian_sidecar.py         # 31 个测试
├── run_benchmark_parallel.py        # 多模型并行 baseline 评估
├── utils.py                         # 工具函数（数据加载、prompt 格式化、选择解析）
├── sidecar_results/                 # 实验结果
│   ├── charts/                      # 可视化图表（27+ 张）
│   ├── *__sidecar_*.json            # 各策略汇总结果
│   ├── *_details.jsonl              # 逐样本详细记录
│   ├── generate_cot_report.py       # COT 图表生成脚本
│   └── generate_tool_ablation_report.py  # Tool 消融图表生成脚本
└── sidecar_checkpoints/             # 断点续传文件
```

## 七、技术栈与关键命令

**技术栈:** Python 3, numpy, httpx, openai (AsyncOpenAI), asyncio, matplotlib

```bash
# 运行测试
cd bayes/bayesclaudecode && python test_bayesian_sidecar.py

# 运行旁路注入实验
python run_sidecar_experiment.py -m openai/gpt-4o-mini --strategies all --per-model 80

# 快速验证（10 样本）
python run_sidecar_experiment.py -n 10 -m openai/gpt-4o-mini --strategies tool_direct_rec tool_empty --per-model 10

# 列出所有策略
python run_sidecar_experiment.py --list-strategies

# 生成图表
cd sidecar_results && python generate_tool_ablation_report.py
```

## 八、飞书文档

- **文档名称**: Bayes 项目概览 — 贝叶斯教学与LLM概率推理
- **文档 ID**: `AcOIdoE0Gop4mexsificXAWbnNg`
- **所在文件夹 Token**: `Y59JfVFEClsLKqdXViOcA3h6n0d`

## 九、编码规范

- 注释语言：中文
- 新代码放在 `bayesclaudecode/` 目录下
- 每个功能点完成后提交 git
- 并发优先：使用 asyncio + AsyncOpenAI
- API 统一走 OpenRouter，并发不限制（付费用户）
