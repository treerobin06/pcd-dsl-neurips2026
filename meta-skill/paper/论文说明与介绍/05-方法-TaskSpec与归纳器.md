# 方法：TaskSpec 与归纳器

> 关联文档：[[04-方法-概率DSL与编译器]] | [[06-方法-三门验证器]] | [[09-实验-泛化测试]]

---

## TaskSpec：声明式中间表示

### 设计理念

TaskSpec 是连接 LLM 和编译器的**桥梁**：
- LLM 的输出 = TaskSpec（JSON 文档）
- 编译器的输入 = TaskSpec

核心设计选择：**LLM 不写 Python 等通用可执行代码**。但具体行为因场景而异：

- **已有 Macro 的家族**（Flight/BN/Bandit）：LLM 只需填写声明式 JSON 模板的字段（推理家族、状态结构、观测模型等），编译器自动匹配对应的 Macro 展开为核心运算。这是纯粹的"填模板"。
- **没有 Macro 的新家族**（如 HMM/NB）：LLM 需要用 7 个核心运算**自行组合出计算流程**。例如 HMM 前向滤波需要构造 `multiply → marginalize → normalize` 的时间轴循环——这个组合模式没有预定义的 Macro。此时 LLM 做的事更接近**受约束的程序合成**（在 7 个类型化原语范围内编排运算序列），而非简单填字段。

总结：LLM 的输出始终是结构化的 JSON/DSL 表达式（不是任意 Python），但对新家族而言，归纳难度显著高于对已知家族的模板填写。

### Schema 详解（6 个顶层字段）

| 字段 | 类型 | 含义 | 示例值 |
|------|------|------|--------|
| `task_name` | string | 描述性名称 | "Flight Preference Learning" |
| `inference_family` | enum | 推理家族 | `hypothesis_enumeration` / `conjugate_update` / `variable_elimination` |

**state_structure（状态结构）**:

| 子字段 | 类型 | 含义 |
|--------|------|------|
| `type` | enum | `discrete_hypothesis_space` / `beta_conjugate` / `bayesian_network` |
| `features` | list[str] | 特征名（仅 hypothesis enum.） |
| `values_per_feature` | list[float] | 偏好权重值 |
| `n_arms` | int | 臂数（仅 conjugate） |

**observation_model（观测模型）**:

| 子字段 | 类型 | 含义 |
|--------|------|------|
| `type` | enum | `softmax_choice` / `bernoulli_reward` / `cpt_given` |
| `temperature` | float | Softmax 温度（默认 1.0） |

**decision_rule（决策规则）**:

| 子字段 | 类型 | 含义 |
|--------|------|------|
| `type` | enum | `argmax_expected_utility` / `argmax_posterior_mean` / `exact_probability` |

**data_format（数据格式）**:

| 子字段 | 类型 | 含义 |
|--------|------|------|
| `rounds` | enum | `sequential` / `single_shot` |
| `options_per_round` | int | 每轮选项数 |
| `feedback` | enum | `chosen_option_index` / `binary_reward` / `none` |

### 编译器的一致性检查

编译器在编译前会检查字段之间的逻辑一致性：
- `hypothesis_enumeration` 必须搭配 `softmax_choice` 和 `argmax_expected_utility`
- `conjugate_update` 必须搭配 `bernoulli_reward` 和 `argmax_posterior_mean`
- 违反则返回诊断信息给归纳器进行自我修正

### TaskSpec 示例

给定 3 个航班推荐样本后，GPT-4o-mini 生成的 TaskSpec：

```json
{
  "task_name": "Flight Preference Learning",
  "inference_family": "hypothesis_enumeration",
  "state_structure": {
    "type": "discrete_hypothesis_space",
    "features": ["departure_time", "duration", "stops", "price"],
    "values_per_feature": [-1.0, -0.5, 0.0, 0.5, 1.0]
  },
  "observation_model": {
    "type": "softmax_choice",
    "temperature": 1.0
  },
  "decision_rule": {
    "type": "argmax_expected_utility"
  },
  "data_format": {
    "rounds": "sequential",
    "options_per_round": 3,
    "feedback": "chosen_option_index"
  }
}
```

编译器读取这个规格后会：
1. 枚举所有 $5^4 = 625$ 个权重向量
2. 用 softmax 似然在每轮用户选择后更新后验
3. 推荐使期望效用最大化的选项

---

## 归纳器（Inductor）

### 工作流程

```
输入: 1 个及以上任务样本（论文实验用 3-5 个，k=1 已验证可行） + TaskSpec Schema 定义
  ↓
LLM (GPT-4o-mini, temperature=0) 分析样本结构
  ↓
输出: 完整的 TaskSpec JSON
  ↓
编译器编译 → 验证器验证
  ↓ (如果失败)
诊断反馈 → LLM 修正 TaskSpec → 重新编译验证（最多 3 轮）
```

### 归纳器 Prompt 设计

归纳器接收以下内容：
1. 1 个及以上完整的任务样本（输入 + 正确输出；论文中用 3-5 个，但 k=1 已验证可行）
2. TaskSpec Schema 的完整定义（包括三种推理家族及其字段）
3. 指令：分析样本结构 → 确定推理家族 → 识别变量和似然模型 → 输出 TaskSpec JSON

Prompt 长度约 ~2k tokens，主要由 Schema 定义占据。

### 关键设计选择

| 设计选择 | 理由 |
|---------|------|
| 家族级归纳（不是实例级） | 同一推理家族内的问题共享相同的数学结构 |
| 约束在 DSL 原语内（不是任意代码） | 大幅降低 LLM 需要的能力门槛（已知家族填 JSON 字段，新家族在 7 个运算内组合） |
| 最少 1 个样本即可（实验中用 3-5 个） | k=1 已在 Flight 和 BN 上验证通过，多给几个更稳健 |
| Temperature=0 | 生产使用时追求确定性输出 |
| 最多 3 轮修正 | 实际中几乎不需要修正（见下面的可靠性数据） |

### 自我修正机制（Eq. 4）

论文将归纳器的迭代过程形式化为：

$$\hat{\tau}^{(r)} = \begin{cases}
I_\phi(\mathcal{D}_F^{(k)}) & r = 0 \\
I_\phi(\mathcal{D}_F^{(k)}, \text{diag}(V(C(\hat{\tau}^{(r-1)}), \mathcal{D}_{\text{val}}))) & r \geq 1
\end{cases}$$

其中 $V$ 是三门验证器，$C$ 是编译器。如果验证失败，诊断信息（哪个 Gate 失败、失败原因）会反馈给归纳器进行修正。

---

## 归纳器的可靠性数据

### 重复运行测试

| 家族 | 运行次数 | 成功率 | 平均轮数 | 平均时间 | 家族检测 |
|------|---------|--------|---------|---------|---------|
| Flight (hypothesis enum.) | 20 | 20/20 (100%) | 1.0 | 5.6s | 全部正确 |
| BN (variable elim.) | 20 | 20/20 (100%) | 1.0 | 4.8s | 全部正确 |
| **总计** | **40** | **40/40 (100%)** | **1.0** | **5.2s** | |

> 测试条件：GPT-4o-mini，temperature=0.7（故意提高随机性来测试鲁棒性）

所有 40 次试验都在**第一轮**通过验证，**不需要任何修正**。论文将高可靠性归因于：输出空间被约束为声明式 JSON，而非任意代码。

### 最少样本数测试

$k=1$ 个样本即可让归纳器在 Flight 和 BN 两个家族上生成有效的 TaskSpec。论文实验中用 $k=3-5$ 以确保鲁棒性，但**面对新问题时可以从 1 个样本开始**。

### Leave-One-Out 泛化测试

| 数据集 | 维度 | 家族检测 | 特征 | 值域 | Gate 3 | 轮数 |
|--------|------|---------|------|------|--------|------|
| Hotel (4D) | 4 | ✓ | ✓ | ✓ | 100% | 1 |
| Flight-2F | 2 | ✓ | ✓ | ✓ | 100% | 1 |
| Flight-3F | 3 | ✓ | ✓ | ✓ | 100% | 1 |
| Flight-5F | 5 | ✓ | ✓ | ✓ | 100% | 1 |
| Flight-6F | 6 | ✓ | ✓ | ✓ | 100% | 1 |
| BLInD depth-OOD | — | ✓ | — | — | 100% | 1 |

6 个 held-out 数据集全部在**第一轮**通过所有验证 Gate，与 gold solver 100% 一致。

---

## 与 PAL 的关键对比

| 对比维度 | PAL (Program-Aided LM) | 本文 DSL 方法 |
|---------|------------------------|-------------------|
| LLM 输出 | 任意 Python 代码 | 约束在 DSL 类型系统内的结构化输出（已知家族填 TaskSpec JSON，新家族组合 7 个核心运算） |
| 粒度 | 每个问题实例一次 | 每个推理家族一次 |
| 推理时 LLM 调用 | 每次都需要 | 不需要 |
| 最低模型要求 | GPT-5.4（写 VE 代码） | GPT-4o-mini |
| 在 ≥20 节点网络上 | 0-3% 准确率 | 100% |
| 成本 (BLInD 900题) | $2.50 (GPT-5.4) | $0.008 (GPT-4o-mini) |
| 失败模式 | 语法错误 + 逻辑错误 + 算法错误 | 已知家族：字段填写错误；新家族：运算组合错误（均可由验证器捕获） |

---

## 代码对应

| 组件 | 文件路径 |
|------|---------|
| TaskSpec Schema | `meta-skill/taskspec/schema.py` |
| 编译器 | `meta-skill/taskspec/compiler.py` |
| 归纳器 | `meta-skill/inductor/inductor.py` |
| 自我修正 | `meta-skill/inductor/refiner.py` |
| 归纳 Prompt 模板 | `meta-skill/inductor/prompts/` |
| 端到端测试 | `meta-skill/tests/test_inductor_e2e.py` |
| LOO 测试 | `meta-skill/tests/test_loo_induction.py` |
