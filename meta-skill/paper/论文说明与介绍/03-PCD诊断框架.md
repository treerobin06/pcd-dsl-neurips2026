# PCD 诊断框架

> 关联文档：[[02-研究动机与问题定义]] | [[04-方法-概率DSL与编译器]] | [[12-数据集详解]]

---

## 目的

PCD（Parse-Compute-Decide）是论文提出的**诊断框架**，目的是精确定位 LLM 概率推理失败的环节。它不是解决方案本身，而是为解决方案提供动机和证据。

---

## 三阶段设计

PCD 将概率推理分解为三个阶段，每个阶段有明确的输入、输出和评估方式：

### Stage 1: Parse（解析）

- **测试目标**: LLM 能否从自然语言问题中提取结构化信息
- **输入**: 完整的自然语言问题描述
- **输出**: 结构化 JSON（变量、边、CPT、查询变量、证据赋值等）
- **评分方式**: 所有字段与 gold parse 逐一比较，**全部正确才算通过**

**BN 推断的 Parse 输出示例**:
```json
{
  "variables": ["Rain", "Sprinkler", "WetGrass"],
  "edges": [["Rain", "WetGrass"], ["Sprinkler", "WetGrass"]],
  "cpts": {"Rain": {"()": [0.2, 0.8]}, ...},
  "query_var": "Rain",
  "query_val": 1,
  "evidence": {"WetGrass": 1}
}
```

**偏好学习的 Parse 输出示例**:
```json
{
  "features": ["departure_time", "duration", "stops", "price"],
  "observations": [
    {"options": [[14.0, 4.4, 1, 370], ...], "chosen": 2}
  ],
  "current_options": [[8.0, 2.5, 0, 520], ...]
}
```

> **重要细节**: 偏好学习的 Parse 实验在 2026-03-25 进行了重做。原实验给 LLM 的输入是已数值化的特征（如 `departure_time=0.50`），新实验改用自然语言（如 `departure time: 02:00 PM, price: $370`），LLM 需要自己完成从自然语言到数值的转换。

### Stage 2: Compute | GoldParse（计算 | 给定正确解析）

- **测试目标**: 在获得完美结构化输入的情况下，LLM 能否正确执行概率计算
- **输入**: **Gold（正确的）** 结构化表示（不是 LLM 自己解析的）
- **输出**: 精确的概率值或期望效用
- **评分方式**: 与 gold 计算结果比较，容差 $\epsilon = 0.01$

**关键设计**: 这里注入的是**正确的** Parse 结果，隔离了 Parse 阶段的误差，**纯粹测试 LLM 的计算能力**。

### Stage 3: Decide | GoldPosterior（决策 | 给定正确后验）

- **测试目标**: LLM 能否根据正确的计算结果做出正确决策
- **输入**: **Gold（正确的）** 后验分布或期望效用
- **输出**: 最优决策（选择哪个选项）
- **评分方式**: 与 gold 决策比较（精确匹配）

---

## Gold-Injection 干预方法

PCD 的核心方法论是 **Gold-Injection（注入正确中间结果）**：

```
正常流水线:  LLM_Parse(x) → LLM_Compute(parse_result) → LLM_Decide(compute_result)
                ↓ 可能出错        ↓ 可能出错              ↓ 可能出错

测试 Parse:  LLM_Parse(x) → 与 Gold 比较
测试 Compute: Gold_Parse → LLM_Compute(gold_parse) → 与 Gold 比较
测试 Decide:  Gold_Posterior → LLM_Decide(gold_posterior) → 与 Gold 比较
```

每个阶段使用**单独的 LLM 调用**，互不影响。这种干预设计确保：
- 测试 Compute 时，Parse 阶段的误差被完全消除
- 测试 Decide 时，Parse 和 Compute 的误差都被消除

---

## 形式化定义

论文给出了 PCD 的数学定义（Eq. 1-3）：

**Parse 准确率**:
$$\text{ParseAcc}_\phi = \frac{1}{|\mathcal{D}|}\sum_{x \in \mathcal{D}} \prod_{f \in \mathcal{F}} \mathbf{1}\{P_\phi^{(f)}(x) = s^{*(f)}\}$$

其中 $\mathcal{F}$ 是结构字段的索引（变量、边、CPT、查询、证据），**所有字段都匹配才算正确**。

**Compute 准确率**:
$$\text{CompAcc}_\phi = \frac{1}{|\mathcal{D}|}\sum_{x \in \mathcal{D}} \mathbf{1}\{\|C_\phi(\mathcal{P}^*(x)) - \mathcal{C}^*(\mathcal{P}^*(x))\|_\infty < \epsilon\}$$

注意这里输入的是 $\mathcal{P}^*(x)$（gold parse），不是 LLM 自己的 parse。

**Decide 准确率**:
$$\text{DecAcc}_\phi = \frac{1}{|\mathcal{D}|}\sum_{x \in \mathcal{D}} \mathbf{1}\{D_\phi(\mathcal{C}^*(s^*)) = a^*\}$$

---

## 诊断结果

### 偏好学习（Flight, 200 样本）

| 模型 | Parse | Compute\|Gold | Decide |
|------|-------|---------------|--------|
| GPT-4o-mini | 82% | 28% [21,34] | 100% |
| GPT-4o | 100% | 30% [23,36] | 100% |
| GPT-5.4 | 100% | 40% [33,47] | 100% |
| Sonnet 4 | 100% | 64% [57,71] | 100% |
| Gemini 3.1 | 100% | 69% [62,75] | 100% |
| Opus 4.6 | 100% | 78% [71,83] | 100% |
| **DSL 求解器** | — | **100%** | — |

> 方括号内为 95% Wilson 置信区间

### BN 推断（BLInD, 900 样本, 100/depth）

Compute|GoldParse 随网络深度急剧下降：

| 深度 | GPT-4o-mini | GPT-4o | GPT-5.4 | Sonnet 4 |
|------|-------------|--------|---------|----------|
| 2 | 82% | 82% | 81% | 82% |
| 5 | 11% | 17% | 24% | 24% |
| 10 | 3% | 5% | 11% | 9% |
| **整体** | **22.3%** | **24.9%** | **31.2%** | **29.1%** |

所有模型在所有深度上 Parse ≥ 96%，Decide = 100%。

---

## 诊断签名

论文将以下模式称为**计算瓶颈的诊断签名**：

$$\text{ParseAcc} \approx 1, \quad \text{DecAcc} \approx 1, \quad \text{CompAcc} \ll 1$$

这个签名在所有测试的模型和任务上都成立。

---

## 方法论注意事项（论文自己指出的）

1. **PCD 是干预性探针，不是因果识别**: 它展示了阶段隔离后的表现差异，但不构成严格的因果推断
2. **Compute|GoldParse 混淆了算法选择和算术执行**: LLM 可能选了错误的算法，也可能算术错了，PCD 无法区分这两者
3. **BN 深度与 token 数相关**: 更深的网络意味着更长的输入，这是一个混淆因素。但 Parse 准确率在所有深度上保持 ≥96%，暗示 token 长度本身不是主因
4. **Decide 分数可能偏高**: 因为决策面很简单（对期望效用取 argmax），这不一定代表 LLM 在复杂决策上也能保持 100%

---

## PCD 对方法设计的启示

PCD 的诊断结果直接**驱动了方法设计**：

```
PCD 发现: LLM 能理解结构，但不会计算
     ↓
设计原则: 让 LLM 做它擅长的（结构归纳），不做它不擅长的（计算）
     ↓
系统架构: LLM 只在编译时贡献一次（归纳 TaskSpec）
          所有计算由确定性求解器完成
```

详见 [[04-方法-概率DSL与编译器]]。
