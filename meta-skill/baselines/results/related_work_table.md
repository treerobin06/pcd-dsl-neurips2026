# Related Work 对比表

> 生成日期: 2026-03-13
> 用途: 论文 Related Work 定位，对比 PCD 框架与已有方法

## 一、方法对比表

| 方法 | 范式 | 代码类型 | 执行方式 | 推断器 | 自修复 | 诊断 | 目标域 |
|------|------|---------|---------|--------|--------|------|--------|
| **PAL** (Gao et al., ICML 2023) | Instance-level: 每题生成一段程序 | 任意 Python | 直接执行 Python 解释器 | 通用 (Python runtime) | 无 | 无 | 数学/符号/算法推理 |
| **PoT** (Chen et al., TMLR 2023) | Instance-level: 每题生成思维程序 | 任意 Python (含 SymPy 等库) | 直接执行 Python 解释器 | 通用 (Python runtime) | 无 | 无 | 数值推理 (数学应用题/金融QA) |
| **SatLM** (Ye et al., NeurIPS 2023) | Instance-level: 每题生成声明式规约 | 特定形式语言 (SAT/FOL 声明) | 编译为 SAT 公式 + 求解器 | 领域特定 (Z3/自动定理证明器) | 无 (未提及错误反馈循环) | 无 | 逻辑/约束满足/算术 |
| **Logic-LM** (Pan et al., EMNLP Findings 2023) | Instance-level: 每题翻译为符号逻辑 | 特定形式语言 (FOL/Prolog/逻辑程序) | 编译 + 符号求解器执行 | 领域特定 (Prolog/Pyke 等逻辑求解器) | 编译器反馈: 错误信息 → LLM 修正符号化结果 | 无 | 逻辑推理 (ProofWriter/FOLIO/AR-LSAT) |
| **Logic.py** (Kesseli et al., arXiv 2025) | Instance-level: 每题生成 DSL 程序 | Typed DSL (基于 Python 语法的逻辑 DSL) | 编译为 C → CBMC 模型检验 (SAT/SMT) | 领域特定 (CBMC 约束求解器) | 无 (语法错误不反馈，约束不可满足时直接重试) | 无 | 逻辑 (Zebra Logic Puzzles/CSP) |
| **Toolformer** (Schick et al., NeurIPS 2023) | Instance-level: 模型自主决定调用 API | API 调用 (计算器/搜索/QA 等) | 直接执行外部 API | 通用 (多种外部工具) | 无 (自监督训练时筛选有用 API 调用) | 无 | 通用 (算术/QA/翻译/事实查询) |
| **BLInD** (Nafar et al., AAAI 2025) | Instance-level: 每题生成推理程序/ProbLog | 任意 Python 或 ProbLog | 直接执行 / ProbLog 推断引擎 | 领域特定 (ProbLog 概率逻辑编程) | 无 | 无 | 概率推理 (贝叶斯网络精确推断) |
| **QUITE** (Schrader et al., EMNLP 2024) | Instance-level: 评估 + 逻辑模型对比 | ProbLog / 直接 LLM 回答 | ProbLog 概率推断引擎 | 领域特定 (ProbLog) | 无 (benchmark 本身不含修复机制) | 无 | 概率推理 (贝叶斯推断: 因果/证据/解释消除) |
| **Ours (PCD + DSL Induction)** | **Family-level**: 从少量样本归纳出 TaskSpec → 编译为通用 solver | **Typed DSL** (7 core ops + 4 family macros) | **确定性编译** + 4-Gate 验证 | **领域特定** (概率 DSL: VE/共轭更新/假设枚举/经验估计) | **Verifier 反馈**: Gate 1-2 诊断信息 → Inductor self-refine (最多 3 轮) | **系统化 PCD**: Parse 98% / Compute 22% / Decide 100% 精确定位瓶颈 | 概率/决策 (BN 推断/偏好学习/bandit/EU 最大化) |

## 二、关键区别总结

### 范式维度: Instance-level vs Family-level

所有已有方法都是 **instance-level**: 每遇到一个新问题，LLM 就重新生成一段程序/规约。我们的方法是 **family-level solver induction**: LLM 从 3-5 个样本中归纳出一个 TaskSpec，编译器一次性生成一个可复用的 solver，该 solver 适用于该 inference family 的所有实例。

### 代码类型维度: 任意代码 vs 受限 DSL

- PAL/PoT 生成任意 Python，灵活但不可验证
- SatLM/Logic-LM/Logic.py 使用特定形式语言（SAT/FOL/逻辑 DSL），可验证但域限于逻辑
- 我们使用 **typed 概率 DSL**，既受限（可验证、可编译）又覆盖多种概率推断 family

### 自修复维度

- 大多数方法无自修复机制
- Logic-LM 有编译器错误反馈 → LLM 修正（但仅修正符号翻译）
- 我们有 **4-Gate Verifier** 反馈循环: Code Sanity / Ground Truth / Reference Match / Integration，诊断信息精确指导 Inductor 修正 TaskSpec

### 诊断维度: PCD 独有贡献

已有方法均无系统化诊断。我们的 **PCD (Parse/Compute/Decide) 因果分析** 是独有的：
- 精确定位 LLM 概率推理的瓶颈在 Compute 阶段（22%），而非 Parse（98%）或 Decide（100%）
- 这一诊断直接动机化了"将计算外包给确定性 solver"的方法设计

## 三、QUITE Benchmark 详细调研

### 基本信息

| 项目 | 内容 |
|------|------|
| **论文全名** | QUITE: Quantifying Uncertainty in Natural Language Text in Bayesian Reasoning Scenarios |
| **作者** | Timo Pierre Schrader, Lukas Lange, Simon Razniewski, Annemarie Friedrich |
| **单位** | Bosch Center for AI / University of Augsburg / TU Dresden |
| **发表** | EMNLP 2024 Main Conference, pp. 2634-2652 |
| **arXiv** | https://arxiv.org/abs/2410.10449 |
| **ACL Anthology** | https://aclanthology.org/2024.emnlp-main.153/ |
| **GitHub** | https://github.com/boschresearch/quite-emnlp24 |
| **许可** | 代码 AGPL-3.0 / 数据 CC BY 4.0 |

### 数据集格式与规模

- **30 个真实世界贝叶斯网络**，涵盖不同主题领域
- **1,192 numeric premises + 1,192 WEP-based premises**（WEP = Words of Estimative Probability，如"很可能"/"不太可能"）
- **测试集**: 273 numeric premises, 273 WEP premises, 230 queries (92 causal, 62 evidential, 26 explaining-away)
- 每个实例包含: 前提 (CPT 自然语言描述) + 证据声明 + 概率查询 + 精确数值答案
- 数据集以 HuggingFace datasets 格式提供，4 个配置: `numeric-premises`, `wep-based-premises`, `evidence-query-pairs`, `additional-evidence-query-pairs`
- 额外提供数千条 silver standard QE pairs 供社区使用

### 任务类型

QUITE 是**纯概率计算**任务（不含预测/决策）:
- **因果推理 (Causal)**: 从观察到的原因推断效果的概率
- **证据推理 (Evidential)**: 从观察到的效果反向推断原因的概率
- **解释消除 (Explaining-away)**: 给定效果和一个原因，推断另一个原因的概率
- 答案格式: 精确数值概率估计（tolerance 10⁻⁴）

### 关键实验结果

- **ProbLog-FT** (Mistral-7B 微调做语义解析): 54.5% accuracy (numeric premises)
- **GPT-4 直接回答**: 37.1% accuracy
- **Oracle 实验**: 前提解析是主要错误来源
- **结论**: 逻辑/符号方法显著优于纯 LLM

### 与 BLInD 的区别

| 维度 | BLInD (AAAI 2025) | QUITE (EMNLP 2024) |
|------|-------------------|---------------------|
| **变量类型** | 二值 (True/False) | 多值分类变量 |
| **事件命名** | 虚拟事件 ("orange event", "purple event") | 真实世界主题 (医疗/天气等) |
| **不确定性表达** | 仅数值概率 | 数值概率 + 语言估计词 (WEP) |
| **BN 规模** | 2-10 个变量 | 30 个 BN，多种拓扑 |
| **推理类型** | 条件概率查询 | 因果/证据/解释消除三类 |
| **数据集规模** | 900 (GPT-3.5) / 180 (GPT-4) | 1,192+ premises, 230+ queries |
| **方法** | PAL, Monte Carlo, ProbLog | ProbLog-FT, 直接 LLM |
| **开源** | GitHub (HLR/BLInD) | GitHub (boschresearch/quite-emnlp24) + HuggingFace |

### 与 PCD 框架的兼容性分析

QUITE **可以**做 PCD 分解:
- **Parse**: 从自然语言前提中抽取 BN 结构 + CPT 数值 + 证据 + 查询变量
- **Compute**: 给定正确解析的 BN + 证据，执行精确概率推断（变量消除等）
- **Decide**: 直接输出概率值（在 QUITE 中 Decide 退化为 identity，因为答案就是概率本身）

**兼容性评估**: QUITE 的任务类型完全落在我们 DSL 的 `ve_query` (变量消除) family macro 范围内。它与 BLInD 属于同一个 inference family (Factor Operations)，但语言变化更丰富、变量更复杂。**可作为 held-out evaluation benchmark 验证 DSL 泛化性**，是补充 BLInD 的理想选择。

**需要注意的挑战**:
1. WEP-based premises 需要额外的"语言→数值"映射步骤（Parse 阶段更难）
2. 多值分类变量的 CPT 维度比 BLInD 的二值变量更大
3. 30 个不同主题的 BN 意味着更多的语言多样性

## 四、参考文献

| 缩写 | 完整引用 |
|------|---------|
| PAL | Gao et al. "PAL: Program-aided Language Models." ICML 2023. arXiv:2211.10435 |
| PoT | Chen et al. "Program of Thoughts Prompting: Disentangling Computation from Reasoning for Numerical Reasoning Tasks." TMLR 2023. arXiv:2211.12588 |
| SatLM | Ye et al. "SatLM: Satisfiability-Aided Language Models Using Declarative Prompting." NeurIPS 2023. arXiv:2305.09656 |
| Logic-LM | Pan et al. "Logic-LM: Empowering Large Language Models with Symbolic Solvers for Faithful Logical Reasoning." EMNLP Findings 2023. arXiv:2305.12295 |
| Logic.py | Kesseli et al. "Logic.py: Bridging the Gap between LLMs and Constraint Solvers." arXiv 2025. arXiv:2502.15776 |
| Toolformer | Schick et al. "Toolformer: Language Models Can Teach Themselves to Use Tools." NeurIPS 2023. arXiv:2302.04761 |
| BLInD | Nafar et al. "Reasoning over Uncertain Text by Generative Large Language Models." AAAI 2025. arXiv:2402.09614 |
| QUITE | Schrader et al. "QUITE: Quantifying Uncertainty in Natural Language Text in Bayesian Reasoning Scenarios." EMNLP 2024. arXiv:2410.10449 |
