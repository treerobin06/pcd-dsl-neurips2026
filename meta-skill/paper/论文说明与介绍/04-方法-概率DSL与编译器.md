# 方法：概率 DSL 与确定性编译器

> 关联文档：[[05-方法-TaskSpec与归纳器]] | [[06-方法-三门验证器]] | [[01-论文概述与核心思想]]

---

## 概述

方法部分是论文的技术核心，包含四个组件：
1. **概率 DSL**（本文档）—— 定义了可用的运算
2. **确定性编译器**（本文档）—— 将 TaskSpec 编译为求解器
3. **TaskSpec**（见 [[05-方法-TaskSpec与归纳器]]）—— 声明式中间表示
4. **验证器**（见 [[06-方法-三门验证器]]）—— 验证编译结果的正确性

---

## 概率 DSL 设计

DSL（Domain-Specific Language）采用两层设计：底层的 **7 个核心运算** + 上层的 **3 个 Family Macro**。

### 类型系统（4 种核心类型）

| 类型                | 含义       | 存储方式                                   |
| ----------------- | -------- | -------------------------------------- |
| `Distribution`    | 有限离散概率分布 | 对齐的 values 和 probabilities 数组（非负，和为 1） |
| `Factor`          | 多变量概率因子  | 变量赋值元组 → 非负实数的映射                       |
| `HypothesisSpace` | 假设空间     | 各维度值列表的笛卡尔积，或显式枚举                      |
| `Evidence`        | 观测数据     | 通用容器（BN 的变量赋值、偏好学习的选择索引等）              |

### 7 个核心运算

每个运算都有精确的类型签名：

| # | 运算 | 类型签名 | 数学定义 |
|---|------|---------|---------|
| 1 | `condition` | Factor × Evidence → Factor | $\phi'(\mathbf{x}) = \phi(\mathbf{x})$ 若 $\mathbf{x}$ 与证据一致，否则 0 |
| 2 | `multiply` | Factor × ... × Factor → Factor | $\phi'(\mathbf{x}) = \prod_i \phi_i(\mathbf{x}_{\text{Scope}(\phi_i)})$ |
| 3 | `marginalize` | Factor × VarSet → Factor | $\phi'(\mathbf{x}') = \sum_{\mathbf{v}} \phi(\mathbf{x}', \mathbf{v})$ |
| 4 | `normalize` | Factor → Distribution | $p(x) = \phi(x) / \sum_{x'} \phi(x')$ |
| 5 | `enumerate_hypotheses` | HypothesisSpace → Set | $\bigtimes_{d=1}^D \mathcal{V}_d$ |
| 6 | `expectation` | Distribution × Function → Real | $\sum_x p(x) \cdot f(x)$ |
| 7 | `argmax` | Map → Key | $\arg\max_j v_j$ |

这 7 个运算被设计为**离散概率推理的最小构建块**。论文声称它们覆盖了所有测试的推理家族，包括两个 held-out 家族（NB 和 HMM）。

### 3 个 Family Macro（语法糖）

Macro 不提供新的计算能力，只是将常见模式包装为更高层的抽象：

#### Macro 1: `softmax_pref`（假设枚举 + softmax 似然）

用于偏好学习，组合路径：
```
enumerate → multiply (softmax likelihoods) → normalize → expectation → argmax
```

数学表示：
$$p(\theta | \mathbf{c}_{1:T}) = \frac{p(\theta) \prod_{t=1}^T P(c_t | \theta, \mathbf{X}_t)}{\sum_{\theta'} p(\theta') \prod_{t=1}^T P(c_t | \theta', \mathbf{X}_t)}$$

其中 softmax 选择概率：
$$P(c_t | \theta, \mathbf{X}_t) = \frac{\exp(\theta^\top \mathbf{x}_{c_t})}{\sum_j \exp(\theta^\top \mathbf{x}_{j,t})}$$

#### Macro 2: `beta_bernoulli`（共轭更新）

用于多臂赌博机，组合路径：
```
condition → normalize → argmax
```

Beta 分布的共轭更新：$\text{Beta}(\alpha + s, \beta + f)$

#### Macro 3: `ve_query`（变量消元）

用于 BN 推断，组合路径：
```
condition (证据) → multiply (所有 CPT 因子) → marginalize (隐变量) → normalize
```

数学表示：
$$P(Q=q | \mathbf{E}=\mathbf{e}) = \frac{1}{Z} \sum_{\mathbf{H}} \prod_{i=1}^n \phi_i(\mathbf{x}_i)\Big|_{\mathbf{E}=\mathbf{e}, Q=q}$$

### Macro 不是必需的

这是论文的一个重要声明：**Macro 只是语法糖，核心运算本身就足够**。

证据：在 held-out 的 HMM 前向滤波任务上（没有对应的 Macro），归纳器用核心运算组合出了一个新的计算序列（迭代 multiply-marginalize-normalize），同样达到 100% 准确率。

详见 [[09-实验-泛化测试]]。

---

## 确定性编译器

### 设计原则

编译器将 TaskSpec（声明式 JSON）翻译为可执行的求解器。关键特性：

1. **确定性**: 相同的 TaskSpec → 相同的求解器 → 相同的输出
2. **只使用 DSL 原语**: 编译出的求解器只调用上述 7 个核心运算
3. **一致性检查**: 编译前验证 TaskSpec 字段之间的逻辑一致性

### 编译过程

**已有 Macro 的家族**（标准流程）:
```
TaskSpec (JSON)
     │
     ├─ inference_family: "hypothesis_enumeration"
     │   → 调用 softmax_pref macro
     │   → 展开为: enumerate → multiply → normalize → expectation → argmax
     │
     ├─ inference_family: "conjugate_update"
     │   → 调用 beta_bernoulli macro
     │   → 展开为: condition → normalize → argmax
     │
     └─ inference_family: "variable_elimination"
         → 调用 ve_query macro
         → 展开为: condition → multiply → marginalize → normalize
```

**没有 Macro 的新家族**（如 NB、HMM）:

TaskSpec 的 `inference_family` enum 只有上述 3 个值，不包含 NB 或 HMM。对于这类新家族，LLM 归纳器需要直接用 7 个核心运算组合出计算流程（受约束的程序合成），而非选择已有的 Macro。例如 HMM 前向滤波被组合为时间轴上的 `multiply → marginalize → normalize` 迭代循环——这个模式在任何已有 Macro 中都不存在。论文将此作为 DSL 泛化能力的关键证据（详见 [[09-实验-泛化测试]]）。

### 等价性验证

编译器产生的求解器与独立实现的 gold reference solver 进行了交叉验证：

| 数据集 | 测试实例数 | 最大绝对误差 | 额外交叉验证 |
|--------|-----------|-------------|-------------|
| Flight | 250 | 0.0 | — |
| BLInD | 900 | 0.0 | pgmpy (Python PGM 库) |
| TextBandit | 50 | 0.0 | — |
| **总计** | **1,200** | **0.0** | |

"0.0 最大误差"意味着编译器输出与 gold solver 在所有 1,200 个实例上完全一致（考虑浮点精度）。

> **注意**：这是经验验证而非形式化正确性证明。论文在 Limitations 中明确指出了这一点。

---

## 系统架构图

```
                    ┌─────────────────┐
                    │ 1 个及以上任务样本  │
                    └────────┬────────┘
                             │
                    ┌────────▼────────┐
                    │   LLM Inductor   │  ← GPT-4o-mini, 一次性调用
                    │  (分析 → TaskSpec) │
                    └────────┬────────┘
                             │
                    ┌────────▼────────┐
                    │    TaskSpec      │  ← 声明式 JSON
                    │  (IR 中间表示)    │
                    └────────┬────────┘
                             │
                    ┌────────▼────────┐     ┌──────────────┐
                    │  确定性编译器     │────▶│  三门验证器    │
                    │  (TaskSpec→求解器) │◀───│  (G1/G2/G3)  │
                    └────────┬────────┘     └──────────────┘
                             │                  refine ↑
                             │                         │
                    ┌────────▼────────┐           失败时反馈
                    │  精确求解器      │
                    │  (无 LLM 依赖)   │
                    └─────────────────┘
```

编译器在这个架构中扮演**确定性转换层**的角色：它保证了 TaskSpec 到求解器的映射是可预测、可验证的。

---

## 代码对应

项目中的实际代码位置：

| 组件 | 文件路径 |
|------|---------|
| 类型系统 | `meta-skill/dsl/types.py` |
| 7 个核心运算 | `meta-skill/dsl/core_ops.py` |
| 3 个 Family Macro | `meta-skill/dsl/family_macros.py` |
| 编译器 | `meta-skill/taskspec/compiler.py` |
| DSL 单元测试 | `meta-skill/tests/test_dsl.py` |
| 编译器测试 | `meta-skill/tests/test_compiler.py` |
| 等价性验证 | `meta-skill/tests/test_equivalence_full.py` |
