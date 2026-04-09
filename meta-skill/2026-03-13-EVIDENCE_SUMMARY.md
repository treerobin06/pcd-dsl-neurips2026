# Evidence Summary — 当前已有的全部实验证据

> **最后更新**: 2026-04-09（补充 Evidence 18-20，更新 NB 数据为 n=200，更新偏好 PCD 为 NL Parse）

## 系统架构

**目标**: LLM 的概率推理瓶颈在于计算能力而非理解能力。通过自动归纳可验证的确定性 solver 来弥补这一缺陷。

**系统链路**: Samples → LLM Inductor → TaskSpec (IR) → Deterministic Compiler → Verified Solver

**核心组件**:
- **DSL**: 7 core typed ops + 3 family macros，覆盖 3 个推理 family
- **TaskSpec**: 声明式 JSON 规范，描述任务的数学结构
- **Compiler**: TaskSpec → Solver，确定性编译，compiler(gold_spec) = gold_solver
- **Inductor**: LLM (GPT-4o-mini) 分析 3-5 个样本 → 输出 TaskSpec
- **Verifier**: 3-Gate 验证 (Code Sanity → Ground Truth → Reference Match)

## Evidence 1: 23 策略消融实验 (Flight, 624 样本)

**结论**: LLM 概率推理准确率随辅助信息增加而显著提升，但有天花板。

| 方法类型 | 代表策略 | R5 准确率 | 说明 |
|---------|---------|:---------:|------|
| Oracle (理论上限) | Bayesian Assistant | 74.8% | 确定性精确计算 |
| 最佳注入策略 | user_separate | 74.8% (=Oracle) | 100% 服从率 |
| Tool calling | tool_use | 73.2% | Function Calling API |
| 数学分析注入 | full_math | 64.1% | 完整后验+推荐 |
| LLM baseline | 无辅助 | 36.6% | 纯 LLM |
| 纯 COT | cot_reflect 等 | 32-33% | 低于 baseline |
| 随机基线 | random | 33.3% | 三选一 |

**关键发现**:
- user_separate 达到 Oracle 上限 → LLM 100% 跟从正确的外部推荐
- 纯 COT 完全无效 → LLM 无法通过自省完成概率计算
- user_separate (60.8%) vs Oracle (74.8%) 的 gap = 13.8pp → decision following 也是问题

## Evidence 2: 跨任务泛化 (3 个 family)

| Family | 任务 | 数据集 | DSL Solver 准确率 |
|--------|------|--------|:--:|
| hypothesis_enumeration | 偏好学习 | Flight (624) | 74.8% (=Oracle) |
| hypothesis_enumeration | 偏好学习 | Hotel (124 dev) | user_separate 59.4% > baseline 36.8% |
| conjugate_update | Bandit | TextBandit (4 configs) | sidecar = Oracle |
| variable_elimination | BN 推断 | BLInD (900) | 100% (MAE=0.000) |

## Evidence 3: DSL 等价性验证

| 数据集 | 样本数 | DSL Solver vs Original Solver | 最大误差 |
|--------|:------:|:----------------------------:|:--------:|
| Flight | 250 | 250/250 (100%) | 0.0 |
| BLInD | 900 | 900/900 (100%) | 0.0 |
| Bandit | 50 updates | 50/50 (100%) | 0.0 |

## Evidence 4: LOO 泛化验证 (Inductor)

Inductor 在**从未见过**的数据集上测试，所有 6 个 held-out 数据集**第 1 轮**即通过全部验证。

| 数据集 | 维度 | Family 正确 | Features 正确 | Values 正确 | Gate 3 Match |
|--------|:----:|:-----------:|:------------:|:-----------:|:------------:|
| Hotel (4D) | 4 | ✓ | ✓ | ✓ | 100% |
| Flight-2F | 2 | ✓ | ✓ | ✓ | 100% |
| Flight-3F | 3 | ✓ | ✓ | ✓ | 100% |
| Flight-5F | 5 | ✓ | ✓ | ✓ | 100% |
| Flight-6F | 6 | ✓ | ✓ | ✓ | 100% |
| BLInD depth-OOD | - | ✓ | - | - | 100% all depths |

## Evidence 5: PAL Baseline (LLM → Python 代码)

### 偏好学习 (Flight, 624 样本, GPT-4o-mini)

| 方法 | R5 准确率 | 代码成功率 |
|------|:---------:|:--------:|
| Our DSL+Compiler | **74.8%** | - |
| LLM baseline (直接回答) | 36.6% | - |
| PAL (LLM→Python) | **29.3%** | 65.9% |

PAL 比 LLM 直接回答低 7.3pp。

### BN 推断 (BLInD, 900 样本, GPT-4o-mini)

| Depth | PAL 准确率 | 代码成功率 | Our DSL |
|:-----:|:---------:|:--------:|:-------:|
| 2 | 93% | 100% | 100% |
| 3 | 68% | 99% | 100% |
| 4 | 35% | 92% | 100% |
| 5 | 19% | 79% | 100% |
| 6 | 10% | 78% | 100% |
| 7 | 5% | 68% | 100% |
| 8 | 5% | 55% | 100% |
| 9 | 1% | 51% | 100% |
| 10 | 2% | 57% | 100% |
| **总体** | **26.4%** | 75.4% | **100%** |

## Evidence 6: 多模型 Baseline

| 模型 | R5 准确率 (无辅助) |
|------|:---------:|
| claude-opus-4.6 | 56.6% |
| gemini-3.1-pro | 54.8% |
| gpt-5.4 | 49.2% |
| gpt-4o | 44.7% |
| gpt-4o-mini | 36.6% |
| 随机基线 | 33.3% |

即使最强模型 (claude-opus-4.6) 也只有 56.6%，远低于 Oracle 74.8%。

## Evidence 7: Parse/Compute/Decide 因果诊断

将 LLM 错误分解为三个阶段，逐阶段注入 gold 数据隔离错误来源。

### 偏好学习 (Flight, 200 样本, GPT-4o-mini)

| 阶段 | 准确率 | 说明 |
|------|:------:|------|
| Parse (structural) | **82.0%** | LLM 能正确提取特征、观测、选项 |
| Compute\|GoldParse | **27.5%** | 给正确结构化输入，LLM 仍算不对 |
| Decide\|GoldPosterior | **100.0%** | 给正确 EU，LLM 100% 选对 |

### BN 推断 (BLInD, 900 样本, GPT-4o-mini)

| Depth | Semantic Parse | Compute\|GoldParse | Decide | Gap (Parse-Compute) |
|:-----:|:---------:|:--------:|:------:|:---:|
| 2 | 100% | 82% | 100% | +18% |
| 3 | 97% | 49% | 100% | +48% |
| 4 | 99% | 30% | 100% | +69% |
| 5 | 97% | 11% | 100% | +86% |
| 6 | 100% | 12% | 100% | +88% |
| 7 | 99% | 8% | 100% | +91% |
| 8 | 96% | 4% | 100% | +92% |
| 9 | 99% | 2% | 100% | +97% |
| 10 | 99% | 3% | 100% | +96% |
| **总体** | **98.4%** | **22.3%** | **100%** | **+76.1%** |

Semantic Parse = 变量识别 (100%) + CPT 提取 (98.4%) + 查询解析 (100%)

**核心结论**: LLM 完全理解概率推理问题的结构 (Semantic Parse 98.4%)，也能正确使用计算结果做决策 (Decide 100%)，但无法自己执行概率计算 (Compute 22-28%)。Parse 在所有 depth 上保持 96-100%，而 Compute 从 82% 崩溃到 2%。**瓶颈明确在计算而非理解。**

---

## Evidence 8: 多模型 PCD — 计算瓶颈跨模型普遍存在

在 GPT-4o 和 GPT-5.4 上重跑 PCD，验证"瓶颈在计算"的结论不限于弱模型。

### 偏好学习 (Flight, 200 样本)

| 模型 | Parse | Compute\|GoldParse | Decide |
|------|:-----:|:---------:|:------:|
| GPT-4o-mini | 82.0% | 27.5% | 100% |
| GPT-4o | 100.0% | 29.5% | 100% |
| **GPT-5.4** | **100.0%** | **40.0%** | **100%** |

**关键发现**: 即使 GPT-5.4（当前最强模型）理解 100% 完美，计算仍只有 40%——远低于 Oracle 74.8%。模型越强 Compute 越高（mini 27.5% → 4o 29.5% → 5.4 40%），但扩展速度远不够。

### BN 推断 (BLInD, 900 样本) — Compute|GoldParse by depth

| Depth | GPT-4o-mini | GPT-4o | GPT-5.4 | Claude Sonnet 4 |
|:-----:|:-----------:|:------:|:-------:|:--------------:|
| 2 | 82% | 82% | 81% | 82% |
| 3 | 49% | 56% | 56% | 55% |
| 4 | 30% | 34% | 41% | 37% |
| 5 | 11% | 17% | 24% | 24% |
| 6 | 12% | 11% | 20% | 15% |
| 7 | 8% | 11% | 23% | 19% |
| 8 | 4% | 3% | 13% | 9% |
| 9 | 2% | 5% | 12% | 12% |
| 10 | 3% | 5% | 11% | 9% |
| **总体** | **22.3%** | **24.9%** | **31.2%** | **29.1%** |

**核心结论**: 所有模型（含非 OpenAI）都展现相同的 depth-dependent 退化模式。GPT-5.4 (frontier) 仅比 GPT-4o-mini 好 9pp (31% vs 22%)，depth=10 仍有 89% 错误率。**模型扩展无法解决计算瓶颈。**

---

## Evidence 9: Compile-time Matched Baseline — 编译一次 vs 逐题调用

公平对比：给 LLM 同样 5 个样本（compile-time），让它写一个通用 Python solver，测试全量。

### BN 推断 (BLInD, 900 样本)

| 编码模型 | BN 准确率 | Self-repair | 方式 |
|---------|:---------:|:----------:|------|
| Our DSL+Compiler (GPT-4o-mini) | **100%** | 不需要 | compile-time, 确定性编译 |
| Compile-time (GPT-5.4) | **100%** | 1 轮成功 | compile-time, 自由代码 |
| **Compile-time (GPT-4o)** | **0%** | **5 轮全败** | compile-time, 自由代码 |
| **Compile-time (GPT-4o-mini)** | **0%** | **5 轮全败** | compile-time, 自由代码 |
| LLM 直接算 (GPT-5.4) | 31.2% | — | per-instance |
| PAL per-instance (GPT-4o-mini) | 26.4% | — | per-instance |

### 偏好学习 (Flight, 624 样本)

| 方法 | 准确率 (vs Oracle) | 准确率 (vs user) |
|------|:---------:|:---------:|
| Our DSL+Compiler (GPT-4o-mini) | 100% | **74.8%** |
| Compile-time (GPT-5.4) | 100% | **74.8%** |
| PAL per-instance (GPT-4o-mini) | — | 29.3% |

**关键发现**:
1. **写出正确的概率计算代码需要 frontier 级能力**：只有 GPT-5.4 成功，GPT-4o 和 GPT-4o-mini 即使 5 轮 self-repair 也完全失败
2. **我们的 DSL+Compiler 用 GPT-4o-mini 就达到 100%**：因为模型只需理解任务结构（输出 TaskSpec），编译器确定性地处理计算部分
3. **Compile-time vs per-instance**: 无论用哪种 compile-time 方法（DSL 或代码生成），都远优于 per-instance 方法

---

## Evidence 10: Gate 3 Off Ablation — 系统不依赖 benchmark 标签

完全关闭 Gate 3 (Reference Match)，仅用 Gate 1 (Code Sanity) + Gate 2 (Ground Truth) 验证。

| 数据集 | Gate 3 | 通过 | 轮次 | Solver 准确率 | vs Gold 一致率 |
|--------|:------:|:----:|:----:|:------------:|:-------------:|
| Hotel (4D) | **OFF** | Y | 1 | 75.0% | **100%** |
| Flight-2F | **OFF** | Y | 1 | 85.0% | **100%** |
| Flight-3F | **OFF** | Y | 1 | 85.0% | **100%** |
| Flight-5F | **OFF** | Y | 1 | 80.0% | **100%** |
| Flight-6F | **OFF** | Y | 1 | 75.0% | **100%** |
| BLInD (depth 2-10) | **OFF** | Y | 1 | 100.0% | **100%** |

**核心结论**: 6/6 全部通过。Gate 3 不是系统正确性的必要条件。即使完全不参考 benchmark 标签（gold solver），inductor + compiler 仍然产出 100% 正确的 solver。**不存在数据泄漏依赖。**

---

## Evidence 11: 非 OpenAI 模型 PCD — Claude Sonnet 4 (全量完成)

在 Claude Sonnet 4 上运行 PCD，验证计算瓶颈不限于 OpenAI 模型。

### 偏好学习 (Flight, 200 样本)
| 阶段 | Claude Sonnet 4 |
|------|:-:|
| Parse | 100.0% |
| Compute\|GoldParse | 64.0% |
| Decide | 100.0% |

### BN 推断 (BLInD, 900 样本)
- Compute\|GoldParse 总体: 29.1%
- 按 depth: 82%→55%→37%→24%→15%→19%→9%→12%→9%
- Decide: 100%

**核心结论**: Claude Sonnet 展现与 GPT 系完全相同的 Parse 高 / Compute 低 / Decide 高 模式。计算瓶颈跨模型厂商普遍存在。

---

## Evidence 12: GPT-5.4 偏好学习 PCD — 最强模型仍有计算瓶颈

| 阶段 | GPT-5.4 |
|------|:-:|
| Parse | 100.0% |
| Compute\|GoldParse | 40.0% |
| Decide | 100.0% |

**核心结论**: GPT-5.4（当前最强模型）理解 100% 完美，但概率计算只有 40%——60% 的计算都算错。我们用 GPT-4o-mini + DSL 达到 100%。

---

## Evidence 13: Opus 4.6 + Gemini 3.1 Pro 偏好 PCD

| 模型 | Parse | Compute\|GoldParse | Decide |
|------|:-----:|:---------:|:------:|
| Claude Opus 4.6 | 100.0% | **77.5%** | 100% |
| Gemini 3.1 Pro | 100.0% | **68.5%** | 100% |

**核心结论**: 即使当前最强模型 Opus (77.5%) 仍有 22.5% 计算错误。跨 3 厂商 (OpenAI/Anthropic/Google) 6 模型全部展现同一 Parse 完美 / Compute 不足 / Decide 完美 模式。

---

## Evidence 14: DeLLMa 农业决策 — 负面结果 (scope 界定)

| 模型 | Direct Answer | Compile-time Solver | Random Baseline |
|------|:-----:|:---------:|:------:|
| GPT-4o-mini | 40.0% | 0% (failed) | 29.1% |
| GPT-5.4 | 40.0% | 29.4% | 29.1% |
| Claude Opus 4.6 | 40.0% | 17.6% | 29.1% |

**核心结论**: Compile-time solver ≈ 随机基线。DeLLMa 是**预测**任务（预测未来农产品价格），不是纯**计算**任务。我们的方法适用于 computation-bottlenecked 任务，不适用于 prediction-bottlenecked 任务。此负面结果精确刻画了方法的适用边界。

---

## 全模型偏好学习 PCD 汇总

> **2026-03-25 更新**: Parse 数据已改用自然语言输入（NL Parse），GPT-4o-mini Parse 从 82%→89.5%。论文 Table 1 使用更新后的数据。Compute/Decide 不受影响。

| 模型 | Parse (NL) | Compute\|GoldParse | Decide |
|------|:-----:|:---------:|:------:|
| GPT-4o-mini | 82% (NL: 89.5%) | 28% | 100% |
| GPT-4o | 100% | 30% | 100% |
| GPT-5.4 | 100% | 40% | 100% |
| Claude Sonnet 4 | 100% | 64% | 100% |
| Gemini 3.1 Pro | 100% | 69% | 100% |
| Claude Opus 4.6 | 100% | 78% | 100% |
| Our DSL+Compiler (mini) | — | **100%** | — |

模型越强 Compute 越高（28% → 78%），但即使最强模型也有 22% 错误率。DSL+mini 直接 100%。

注：GPT-4o ~ Opus 的 NL Parse 尚未重跑，仍为原始数值化输入的结果。待做：多模型 NL Parse。

---

## Evidence 15: Held-out Family — Naive Bayes 医学诊断 (n=200)

> **2026-03-14 更新**: 从 n=20 扩展到 n=200，数据更可靠。

在从未见过的第 4 个 inference family 上验证。NB 不属于现有 3 个 macro 的任何一个。

### 主要结果 (n=200)

| 条件 | GPT-4o-mini | GPT-5.4 |
|------|:-----------:|:-------:|
| Direct Answer | 44.0% | 68.5% |
| Unconstrained Code Gen. | **100.0%** | **100.0%** |
| Core-ops Constrained | **100.0%** | **100.0%** |

### PCD 诊断

| 阶段 | GPT-4o-mini | GPT-5.4 |
|------|:-----------:|:-------:|
| Parse | 3.0% [1,8] | 100.0% [98,100] |
| Compute\|GoldParse | 37.0% [30,44] | 64.5% [58,71] |
| Decide\|GoldPosterior | 100.0% [98,100] | 100.0% [98,100] |

*mini Parse=3% 因为需精确提取大量浮点数（4-6 疾病 × 5-8 症状的 CPT），单个数值误差即 fail。

**核心结论**: PCD 模式在 held-out family 完美复现；core ops alone = 100%，macro 非必需。

---

## Evidence 16: Related Work 对比表

见 `baselines/results/related_work_table.md`。

系统性对比 PAL / PoT / SatLM / Logic-LM / Logic.py / BLInD / QUITE / Toolformer。

核心区分：
- **粒度**: 我们是 per-family（compile once），其他全部 per-instance
- **代码类型**: Typed DSL vs 任意 Python/声明式
- **诊断**: PCD 是唯一系统化的 LLM 错误分解框架
- **验证**: 3-Gate verifier（其他最多有编译器检查）

---

## Evidence 17: Cost Curve

见 `baselines/results/cost_analysis.md`。

| 方法 | 模型 | BN 准确率 | 总成本 | 相对成本 |
|------|------|:---------:|:------:|:--------:|
| **Our DSL+Compiler** | mini | **100%** | **$0.001** | **1×** |
| Compile-time | GPT-5.4 | 100% | $0.06 | 60× |
| Per-instance Direct | GPT-5.4 | 31.2% | $3.60 | 3600× |
| Per-instance PAL | mini | 26.4% | $0.97 | 970× |

DSL 比 per-instance 便宜 3600×，且准确率从 31% 提到 100%。

---

## Evidence 18: Held-out Family — HMM Forward Filtering (n=100)

HMM 需要顺序时序推理（iterated multiply-marginalize-normalize over time axis），所有 3 个 training macro 都不包含此模式。

| 条件 | GPT-4o-mini | GPT-5.4 |
|------|:-----------:|:-------:|
| Direct Answer | 32.0% | 61.0% |
| Unconstrained Code Gen. | **100.0%** | **100.0%** |
| Core-ops Constrained | **100.0%** | **100.0%** |

| 阶段 | GPT-4o-mini | GPT-5.4 |
|------|:-----------:|:-------:|
| Parse | 100.0% | 99.0% [95,100] |
| Compute\|GoldParse | 27.0% [19,37] | 53.0% [43,63] |
| Decide\|GoldPosterior | 98.0% [93,100] | 100.0% |

**核心结论**: 归纳器从 core ops 构造了全新的运算序列（非已有 macro），确认 DSL 的组合泛化能力。

---

## Evidence 19: 偏好学习 NL Parse (2026-03-25)

原 Parse 实验使用已数值化的特征（如 `departure_time=0.50`），几乎 trivial。新实验改用自然语言（如 `departure time: 02:00 PM, price: $370`），LLM 需从文本提取数值。

| 阶段 | GPT-4o-mini (n=200) |
|------|:-------------------:|
| Parse (NL) | **89.5%** |
| Compute\|GoldParse | 30.5% |
| Decide | 100% |

核心结论"瓶颈在计算"不变。待做：其他模型的 NL Parse。

---

## Evidence 20: 端到端 Pipeline 验证 (2026-03-25)

完整链路：GPT-4o-mini 读自然语言航班描述 → 提取数值特征 → 编译的 PreferenceSolver → 推荐。

| 指标 | 结果 |
|------|:----:|
| E2E 准确率 | **74.3%** [70.9%, 77.8%] |
| Gold-feature Oracle | 74.4% |
| 特征提取准确率 | 99.9-100% per feature |
| 与 Gold Solver 一致率 | 99.8% |

vs 最佳 prompt-based（tool-calling 58.3%），compile-once pipeline 高 16pp。

---

## Evidence 21: bnlearn 真实世界网络 (120 queries)

4 个标准 bnlearn 网络：Asia (8 nodes), Child (20, multi-valued), Insurance (27, 52 edges), Alarm (37, 46 edges)。

| 网络 | PAL (mini) | PAL (5.4) | Compute\|Gold | Our DSL |
|------|:----------:|:---------:|:-------------:|:-------:|
| Asia (8) | 27% | 90% | 0% | **100%** |
| Child (20) | 20% | 0% | 0% | **100%** |
| Insurance (27) | 23% | 3% | 0% | **100%** |
| Alarm (37) | 0% | 0% | 0% | **100%** |

≥20 节点时 PAL 崩溃到 0-3%，Our DSL 用同一个 ve_query macro 保持 100%。

---

## 尚缺的 Evidence

1. ~~全部 1-17 已完成~~
2. ~~HMM held-out~~ **已完成 (Evidence 18)**
3. ~~NL Parse~~ **已完成 (Evidence 19，仅 GPT-4o-mini)**
4. ~~E2E Pipeline~~ **已完成 (Evidence 20)**
5. ~~bnlearn 外部验证~~ **已完成 (Evidence 21)**
6. **多模型 NL Parse**: GPT-4o/5.4/Claude Sonnet 重跑偏好学习 NL Parse
7. **QUITE Benchmark** (EMNLP 2024): 外部 BN benchmark，增强外部效度
8. **PAL + self-repair**: 给 PAL 加 3 轮 self-repair 公平对比
9. **bnlearn 扩样**: 30→100 query/网络
10. **DSL Ablation (细化)**: no macros-only / no verifier / no self-refine
