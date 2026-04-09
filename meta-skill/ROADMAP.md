# 执行路线图

> **⚠️ 历史文档** — 创建于 2026-03-12。Phase A/B/C 已全部执行完毕，MVP 退出条件已满足。**项目当前状态和待办事项请阅读 `meta-skill/CLAUDE.md`。**

**创建日期**: 2026-03-12
**重写日期**: 2026-03-13（战略讨论后）
**状态**: 已完成（所有里程碑已达成）

---

## 总体路线

```
Phase A: Gold Reference Solvers       Phase B: 核心贡献              Phase C: 论文
[========================]            [==================]           [==========]
 Week 1-3                              Week 4-5                      Week 5-7

A-0改造 → A-1酒店 → A-2 Bandit → A-3 BLInD │ B-1 DSL → B-2 TaskSpec → B-3 Inductor → B-4 Eval
                                              │         ← 关键路径 →
```

**论文核心贡献在 Phase B**。Phase A 提供 gold reference + DSL 设计经验。

---

## Phase A: Gold Reference Solvers（~3 周）

### A-0: 代码基础改造

**目标**: 通用化实验基础设施 + dev/test 分离

| 任务 | 改动内容 | 预估 |
|---|---|---|
| A-0-1 | `run_sidecar_experiment.py` 添加 `--dataset` 参数 | 3h |
| A-0-2 | `format_round_prompt()` 动态提取 entity 名 | 3h |
| A-0-3 | `FEATURE_NL_MAP` 添加 hotel + 自动推断 feature_dim | 2h |
| A-0-4 | `extract_choice()` 通用化 | 2h |
| A-0-5 | dev/test 分离（固定 seed 随机分层切分，20/80） | 2h |
| A-0-6 | 回归测试 | 1h |

---

### A-1: Hotel 实验 [P1] — 2-3 天

**Solver**: 复用 BayesianSidecar，改配置
**实验**: 统一 baseline matrix（LLM alone / CoT / Sidecar exact / Sidecar wrong / Oracle）
**样本**: dev 125 + test 499 × 5 轮
**产出**: 跨领域泛化证据 + 第一个 gold reference solver

**同时记录**：在写 solver 过程中，标注哪些代码是 "task-specific"、哪些是 "可复用"。这些笔记直接输入 Phase B DSL 设计。

---

### A-2: TextBandit 实验 [P2] — 5-7 天

**新建 BanditSidecar**（Beta-Bernoulli conjugate update）

```python
class BanditSidecar:
    def __init__(self, n_arms):
        self.alpha = np.ones(n_arms)  # Beta 先验
        self.beta = np.ones(n_arms)

    def update(self, arm, reward):
        self.alpha[arm] += reward
        self.beta[arm] += (1 - reward)

    def recommend(self):
        means = self.alpha / (self.alpha + self.beta)
        return int(np.argmax(means))
```

**实验**: 统一 baseline matrix + Thompson Sampling 对比
**配置**: 2/3/4/5 arm × 100 trials × 25 rounds
**产出**: 跨范式泛化证据 + 第二个 gold reference solver

---

### A-3: BLInD 实验 [P3] — 5-7 天

**新建 BNSolver**（variable elimination）

```python
class BNSolver:
    def parse_bn(self, context_text, graph_text):
        """从 BLInD 数据解析出 BN 结构 + CPT"""
        ...

    def solve(self, query_var, evidence, dag, cpts):
        """变量消除求精确条件概率（可用 pgmpy）"""
        ...
```

**实验**: 统一 baseline matrix + Noisy Sidecar 对比
**产出**: 最纯粹概率推理证据 + 第三个 gold reference solver

---

### A-3.5: 识别性实验 — 2-3 天

在 Flight + 1-2 个新数据集上跑 Parse/Compute/Decide 分解：
- 设计 evaluation harness（gold intermediate state 生成）
- 跑分解实验
- 整理已有 23 策略为证据链

---

## Phase B: 核心贡献 — DSL + Inductor（~2 周）← 关键路径

### B-1: DSL 提取（3-4 天）

从 3 个 gold reference solvers 提取共性：

**产出**:
- `dsl/core_ops.py`: 8 个 core typed ops
- `dsl/family_macros.py`: 4 个 family macros
- `dsl/types.py`: Distribution, Factor, HypothesisSpace 等类型
- 单元测试：每个 op/macro 独立测试

**关键约束**: DSL 在此步冻结。后续 held-out eval 不允许回来改 DSL。

---

### B-2: TaskSpec + Compiler（3-4 天）

**产出**:
- `taskspec/schema.py`: TaskSpec JSON schema + 验证器
- `taskspec/examples/`: 3 个 gold TaskSpec（手写，对应 3 个 gold solver）
- `taskspec/compiler.py`: TaskSpec → Solver 确定性编译器
- 验证: compiler(gold_taskspec) 输出的 solver 与手写 solver 100% 等价

---

### B-3: Solver Inductor + Verifier（4-5 天）

**产出**:
- `inductor/inductor.py`: LLM 分析样本 → 输出 TaskSpec
- `inductor/refiner.py`: verifier 诊断 → self-refine 循环（最多 3 轮）
- `verifier/gates.py`: 4 关验证
- Leave-One-Out 在 3 个真实任务上测试

**LOO 测试**:
| 留出 | 已知 | 测试 |
|------|------|------|
| Hotel | Flight + TextBandit + BLInD | 同 family 不同 domain |
| TextBandit | Flight/Hotel + BLInD | 不同 family (conjugate) |
| BLInD | Flight/Hotel + TextBandit | 不同 family (VE) |

---

### B-4: 合成 Benchmark（3-4 天）

**产出**:
- 每个 family 200+ 合成实例
- 3 种 OOD 配置（Param / Paraphrase / Structure）
- Out-of-DSL 负例（HMM, POMDP 等）
- Nearest-Template baseline 实现（防御攻击点）

---

## Phase C: 论文撰写（~2 周，与 Phase B 后半段并行）

### C-1: 论文主体

- Introduction: computation bottleneck + unified DSL + solver induction
- Method: DSL + TaskSpec + Inductor + Verifier
- Experiments: 真实任务 baseline matrix + LOO + 合成 benchmark + 识别性实验
- Analysis: computation bottleneck 分解 + failure mode 分析
- Related Work: 4 段定位

### C-2: DeLLMa（如果时间够）

- 第 4 个 inference family
- 加入 LOO 和合成 benchmark

---

## 关键里程碑

| 里程碑 | 完成条件 | 论文价值 | 阶段 |
|---|---|---|---|
| M1: Hotel 实验 | 统一 matrix + gold solver | 跨领域证据 | Phase A |
| M2: TextBandit 实验 | 统一 matrix + gold solver | 跨范式证据 | Phase A |
| M3: BLInD 实验 | 统一 matrix + gold solver | 纯概率推理证据 | Phase A |
| M3.5: 识别性实验 | parse/compute/decide 分解 | claim 支撑 | Phase A |
| **M4: DSL 冻结** | **core ops + macros + 单测通过** | **框架贡献** | **Phase B** |
| **M5: Compiler 通过** | **gold TaskSpec → solver = gold solver** | **可验证性** | **Phase B** |
| **M6: Inductor LOO** | **held-out 任务 verifier pass** | **核心贡献** | **Phase B** |
| **M7: 合成 Benchmark** | **200+/family, 3 OOD** | **统计力度** | **Phase B** |
| **论文可投稿** | **M1-M7** | | |
| M8: DeLLMa | 第 4 个 family | 更完整覆盖 | Stretch |

---

## MVP 退出条件

**必须完成才能投稿**：
- [ ] 3 个真实任务统一 baseline matrix（test set, Bootstrap CI）
- [ ] 3 个 gold reference solvers
- [ ] DSL 冻结 + Compiler 通过
- [ ] Inductor LOO: 至少 2/3 真实任务 verifier pass
- [ ] 合成 benchmark: 200+/family, verifier pass rate > 70%
- [ ] Human edits 指标报告
- [ ] Nearest-Template baseline 对比
- [ ] 识别性实验: 至少 2 个数据集 parse/compute/decide
- [ ] Out-of-DSL 负例拒绝测试
- [ ] Flight 74.8% test set 重跑确认

**明确不需要**（Stretch）：
- DeLLMa 实验
- 多特征扩展
- 完整 self-refine 闭环（1 轮 refine 即可）
- Skill 包装

---

## Kill Switch

**评估时间点**: Phase B 第 10 天（约 Week 5 结束）

**触发条件**（满足任一即触发）：
- Inductor 在 held-out 真实任务上 verifier pass rate < 30%
- Human edits > 50% solver 代码
- Nearest-Template baseline 与 Inductor 无显著差异

**回退方案**:
- 论文标题改为: "Diagnosing and Augmenting LLM Probabilistic Reasoning: A DSL-Based Analysis"
- 保留: DSL + TaskSpec + gold solvers + computation bottleneck 诊断 + baseline matrix
- 降级: Inductor 改为 "semi-automatic generation with human guidance"
- 定位: Findings/Workshop 但仍有完整贡献（DSL + 诊断分析）
