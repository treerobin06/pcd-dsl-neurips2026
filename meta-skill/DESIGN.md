# Inducing Verifiable Probabilistic Solvers for LLM Reasoning

> **⚠️ 历史文档** — 创建于 2026-03-12，记录了早期设计决策。实际实现与此文档有多处差异（如 4-Gate→3-Gate、8 ops→7 ops、DeLLMa solver 未构建）。**项目当前状态请阅读 `meta-skill/CLAUDE.md`。**

**创建日期**: 2026-03-12
**重写日期**: 2026-03-13（Codex Review Round 1-2 + 战略讨论后）
**状态**: 历史文档（设计已执行完毕，实际实现以代码和 CLAUDE.md 为准）

---

## 一、核心问题与动机

### 问题

LLM 在概率推理任务上表现很差（GPT-4 在 BN 推断上仅 7%，在多臂赌博机上 ~31%，在偏好学习上 ~37%）。已有工作各自提出了 task-specific 的解决方案（BLInD→ProbLog, DeLLMa→4步pipeline, Bayesian Teaching→微调），但**每换一个任务就要重新设计工具**。

### 核心洞察

这些看似不同的概率推理任务（BN 推断、bandit 决策、偏好学习、期望效用最大化）在数学上共享同一个骨架：**posterior ∝ prior × likelihood → decision = argmax(expected utility)**。差异仅在于：
- **状态空间结构**不同（离散假设枚举 vs 连续共轭 vs 因子图 vs 经验分布）
- **观测模型**不同（softmax 选择 vs 伯努利反馈 vs 条件概率表 vs 历史频率）
- **决策规则**不同（EU 最大化 vs posterior mean vs 精确概率回答）

### 论文 Claim

> 在结构化概率推理任务中，LLM 的性能瓶颈主要来自不可靠的概率计算。我们提出一个**受限的概率 DSL** 和 **verifier-guided solver induction system**，将任务描述自动编译为可执行 solver，再将精确推断结果注回 LLM，在 4 种 inference family 上显著提升决策质量。

### 已有证据（Flight 数据集 23 策略梯度）

- baseline = 36.5%（LLM 自己算）→ cot_only ≈ 40%（知道方法但算错）→ full_math = 68%（给计算结果）→ user_separate = 74.8%（接近 Oracle）→ tool_use = 73.2%（LLM 主动调用工具）

---

## 二、方法：Verifier-Guided Probabilistic Solver Induction

### 2.1 总体架构

```
新任务样本 (几条)
       │
       ▼
┌─────────────────┐
│  Solver Inductor │  LLM 分析样本，输出结构化 TaskSpec
│  (LLM-powered)   │
└────────┬────────┘
         │ TaskSpec (声明式 JSON/AST)
         ▼
┌─────────────────┐
│  Deterministic   │  根据 TaskSpec 从 DSL 原语组合出 solver
│  Compiler        │
└────────┬────────┘
         │ Solver Code (只调用 DSL 原语)
         ▼
┌─────────────────┐
│  4-Gate Verifier │  Code Sanity → Ground Truth → Reference Match → Integration
└────────┬────────┘
         │ pass / fail + diagnostics
         ▼
    pass? → 输出 solver
    fail? → diagnostics 反馈给 Inductor → self-refine TaskSpec
```

**关键设计决策**：
- LLM 负责**结构化归纳**（TaskSpec），不负责写代码
- 编译器负责**代码生成**（确定性、可验证）
- 这样贡献落在 "induction + verification"，而非 "prompted codegen + tests"

### 2.2 Probabilistic DSL（两层）

> **审查共识**: 不要把算子和 solver macro 混在一起都叫 "primitive"。分为 core typed ops 和 family macros。

#### Layer 1: Core Typed Ops（底层算子）

| Op | 签名 | 说明 |
|---|---|---|
| `condition(dist, evidence)` | Distribution × Evidence → Distribution | 条件化 |
| `multiply(factors)` | List[Factor] → Factor | 因子乘积 |
| `marginalize(factor, vars)` | Factor × Set[Var] → Factor | 边缘化 |
| `normalize(factor)` | Factor → Distribution | 归一化 |
| `enumerate(space)` | HypothesisSpace → List[Hypothesis] | 枚举假设 |
| `estimate_dist(data, method)` | Data × Method → Distribution | 从数据估计分布 |
| `expectation(dist, func)` | Distribution × Function → Scalar | 期望值 |
| `argmax(values)` | Dict[Action, Scalar] → Action | 最优决策 |

#### Layer 2: Family Macros（推断后端）

| Macro | 组合方式 | 适用 Family |
|---|---|---|
| `softmax_pref_likelihood` | enumerate + multiply + normalize | Hypothesis Enumeration（偏好学习）|
| `beta_bernoulli_posterior` | condition（共轭更新快捷方式） | Conjugate Update（bandit）|
| `ve_query` | multiply + marginalize + normalize（变量消除） | Factor Operations（BN 推断）|
| `empirical_state_probs` | estimate_dist + normalize | Empirical Estimation（DeLLMa）|

**论文叙事**：所有 macro 在数学上都是 `posterior ∝ prior × likelihood` 的实例化。DSL 的价值在于把这个统一数学结构编码为可组合、可验证的程序组件。

### 2.3 TaskSpec IR（形式化任务描述）

```json
{
  "task_name": "hotel_preference_learning",
  "inference_family": "hypothesis_enumeration",
  "state_structure": {
    "type": "discrete_hypothesis_space",
    "hypothesis": "linear_preference_weights",
    "features": ["distance", "price", "rating", "amenities"],
    "values_per_feature": [-1, -0.5, 0, 0.5, 1]
  },
  "observation_model": {
    "type": "softmax_choice",
    "temperature": 1.0,
    "input": "user_choice_among_options"
  },
  "decision_rule": {
    "type": "argmax_expected_utility",
    "utility": "option_score_under_posterior_mean"
  },
  "data_format": {
    "rounds": "sequential",
    "options_per_round": 3,
    "feedback": "chosen_option_index"
  }
}
```

TaskSpec 是 **Inductor 和 Compiler 之间的接口**。Inductor 从样本推断出 TaskSpec，Compiler 根据 TaskSpec 确定性地组合 DSL 原语生成 solver。

### 2.4 Solver Inductor（LLM-powered）

Inductor 的输入：
- DSL 文档（所有 ops 和 macros 的签名+语义）
- TaskSpec schema（JSON schema + 各字段的含义）
- 新任务的 3-5 个样本

Inductor 的输出：
- TaskSpec JSON
- （可选）自定义 likelihood expression（在 DSL 的一个很小的声明式子语言内）

**不允许** Inductor 直接输出任意 Python 代码。它只能填写 TaskSpec 的字段和声明式表达式。

### 2.5 4-Gate Verifier

| Gate | 检查内容 | 自动化程度 |
|------|---------|-----------|
| 1. Code Sanity | solver 能实例化、能跑、输出格式正确 | 全自动 |
| 2. Ground Truth | 对样本数据，solver 输出 ≈ 已知正确答案 | 全自动 |
| 3. Reference Match | auto solver vs manual solver 100% 一致 | 全自动（需 gold reference）|
| 4. LLM Integration | 注入后 downstream accuracy 差距 < 2pp | 半自动（需跑 LLM） |

**Self-Refine 循环**：如果 Gate 1-2 不通过，verifier 诊断信息反馈给 Inductor，重新推断 TaskSpec。最多 3 轮。

---

## 三、目标数据集

### 3.1 真实任务（4 个 inference family）

| 数据集 | Inference Family | Macro | 实现难度 | 优先级 |
|---|---|---|---|---|
| Flight/Hotel | Hypothesis Enumeration | `softmax_pref_likelihood` | 极简/已完成 | P1 |
| TextBandit | Conjugate Update | `beta_bernoulli_posterior` | 简单 | P2 |
| BLInD | Factor Operations (VE) | `ve_query` | 较难 | P3 |
| DeLLMa | Empirical Estimation | `empirical_state_probs` | 中等 | P4 (stretch) |

### 3.2 SOTA 参考

| 数据集 | SOTA 方法 | SOTA 结果 | LLM Baseline | 提升 |
|---|---|---|---|---|
| Flight | Bayesian Teaching (微调 Gemma 9B) | R5=76% | 37% | +39pp |
| Hotel | Bayesian Teaching (微调 Gemma 9B) | R5=66% | ~35% | +31pp |
| TextBandit | Thompson Sampling | 51.1% | ~31% | +20pp |
| BLInD | LLM→ProbLog→执行 | 97% | ~7% | +90pp |
| DeLLMa | DeLLMa-Pairs(64) | ~80% | ~55% | +25pp |

---

## 四、评估框架

### 4.1 统一 Baseline Matrix（每个真实任务必跑）

| 条件 | 说明 |
|------|------|
| LLM alone | 无注入 baseline |
| LLM + CoT | 让 LLM 自己推导 |
| LLM + Sidecar (auto) | 自动生成的 solver 注入 |
| LLM + Sidecar (manual) | 手写 solver 注入（gold reference） |
| LLM + Sidecar (wrong) | 注入错误结果同格式（信息预算对照） |
| Oracle solver | solver 直接给答案的理论上限 |
| Nearest-Template baseline | 模板选择 + slot filling（攻击点防御） |

### 4.2 Solver Induction 评测指标

| 指标 | 说明 | 为什么重要 |
|------|------|-----------|
| Generation Success | 生成的 solver 能跑通（Gate 1） | 基本可行性 |
| Verifier Pass Rate | 通过 4 关验证的比例 | 自动化质量 |
| TaskSpec Recovery | 推断的 TaskSpec 与 gold TaskSpec 的字段匹配率 | induction 质量 |
| Oracle Equivalence | auto solver vs manual solver 输出一致率 | 精确度 |
| Human Edits Needed | 修到正确需要改多少行 | 实际价值（关键指标） |
| Downstream Decision Gain | 注入后 LLM 准确率提升 | 端到端效果 |

### 4.3 合成 Benchmark（统计力度）

每个 inference family 200+ 实例，3 种 OOD 测试：

| OOD 类型 | 说明 | 示例 |
|----------|------|------|
| Param-OOD | 同任务族，不同参数范围 | BN: 更多变量/更深/更宽的 CPT 值域 |
| Paraphrase-OOD | 同 TaskSpec，不同语言表述 | "概率为 39%" vs "有 39% 的可能性" |
| Structure-OOD | 同 family，结构复杂度上升 | Bandit: 2臂→10臂; BN: depth 2→6 |

**Out-of-DSL 负例**：加入 DSL 不支持的任务（如连续状态空间 HMM、POMDP），要求系统识别"不会做"并拒绝，而非硬生成错误 solver。

### 4.4 识别性实验（Computation Bottleneck 分析）

| 指标 | 操作化定义 |
|------|-----------|
| Parse Acc | LLM 能否正确抽取变量/证据/动作空间 |
| Compute Acc \| gold parse | 给金标准 state，LLM 自己算 posterior |
| Decide Acc \| gold posterior | 给正确 posterior，LLM 选答案 |
| Wrong Control | 注入同格式同置信度但数值错误的结果 |

### 4.5 统计要求

- 固定 model version、temperature=0、seed
- Dev/test 分离：固定 seed 随机分层切分，20% dev / 80% test
- 策略设计在 dev 上，test 一次性报告
- Bootstrap 95% CI（2000 次重采样）
- 报 parse failure rate、API 成本、运行时间
- Flight 已有 74.8% 降级为探索性结果，test set 重跑

---

## 五、Related Work 定位

论文 related work 分四段：

| 段落 | 覆盖工作 | 我们的区别 |
|------|---------|-----------|
| Tool use & creation | Toolformer, CRAFT, LILO | 不是通用 tool，是**受限概率 DSL 上的 solver induction** |
| Solver-augmented reasoning | Logic-LM, SymbCoT | 不是翻成固定逻辑语言，是**归纳概率/决策 TaskSpec + solver** |
| Probabilistic reasoning with LLMs | BLInD, DeLLMa, Bayesian Teaching | 不是 task-specific pipeline，是**统一多种 inference family 的生成接口** |
| Library induction & autoformulation | LILO, OptimAI, AlphaOPT | Domain 更窄但 verification 更强，目标是概率 solver |

**投稿方向**：
- ACL → 强调 language → TaskSpec 和 faithful reasoning
- NeurIPS/ICML → 强调 program induction / autoformulation / verifier-guided search

---

## 六、风险管理

### 最大攻击点及防御

| Reviewer 攻击 | 防御措施 |
|--------------|---------|
| "这不是 solver induction，是 family classification + slot filling" | Nearest-template baseline 对比; 报 TaskSpec 字段级别的推断准确率; 复杂实例需要 non-trivial composition |
| "合成 benchmark 是模板反演" | 3 种 OOD 控制; paraphrase diversity; structure complexity scaling |
| "真实 benchmark 太小" | 合成 benchmark 补统计力度; 真实任务负责外部效度 |
| "DSL 是看着任务设计的" | DSL 冻结后再做 held-out eval; out-of-DSL 负例测拒绝能力 |

### Kill Switch

**触发条件**（Phase B 第 10 天评估）：
- Solver Inductor 在 held-out 真实任务上只能做到 template matching
- Human edits > 50% 的 solver 代码
- Verifier pass rate < 50%

**回退方案**：
- 论文改为 "强诊断分析 + 半自动 solver generation"
- 保留 DSL + TaskSpec + 手写 solver + computation bottleneck 分析
- 降级为 workshop/findings 但仍有完整贡献

---

## 七、文件结构

```
meta-skill/
├── DESIGN.md                    # 本文件
├── CONTEXT.md                   # 上下文索引
├── ROADMAP.md                   # 执行路线图
├── CODEX_REVIEW.md              # 审查记录
├── dsl/                         # Probabilistic DSL
│   ├── __init__.py
│   ├── core_ops.py              # Layer 1: Core typed ops
│   ├── family_macros.py         # Layer 2: Family macros
│   └── types.py                 # 类型定义 (Distribution, Factor, etc.)
├── taskspec/                    # TaskSpec IR
│   ├── schema.py                # TaskSpec JSON schema + 验证
│   ├── examples/                # 各任务的 gold TaskSpec
│   └── compiler.py              # TaskSpec → Solver 编译器
├── inductor/                    # Solver Inductor
│   ├── inductor.py              # LLM-powered TaskSpec 推断
│   ├── refiner.py               # Self-refine 循环
│   └── prompts/                 # Inductor prompt templates
├── verifier/                    # 4-Gate Verifier
│   ├── gates.py                 # 4 个验证关卡
│   └── diagnostics.py           # 诊断信息生成
├── solvers/                     # 手写 Gold Reference Solvers
│   ├── preference_solver.py     # Flight/Hotel
│   ├── bandit_solver.py         # TextBandit
│   ├── bn_solver.py             # BLInD
│   └── dellma_solver.py         # DeLLMa (stretch)
├── benchmarks/                  # 合成 Benchmark
│   ├── generators/              # 各 family 的合成数据生成器
│   └── ood_configs/             # OOD 测试配置
├── runner/                      # 实验运行器
│   ├── universal_runner.py
│   └── injection.py
├── tests/
└── results/
```
