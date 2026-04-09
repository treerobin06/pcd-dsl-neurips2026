# Codex Review Report — Round 3

**审查类型**: 研究方向 + 论文策略审查
**审查重点**: Story 怎么讲能发顶会
**开始时间**: 2026-03-13 20:00
**审查者**: Codex (GPT-5.4 xhigh) + Claude Opus 预审

---

## Round 1 — 2026-03-13 20:00

**Codex 评分**: 6/10 (borderline accept for ICLR/ACL)
**来源**: Codex + Claude 预审（双线并行完成）

### 双方共识（高置信度）

| # | 严重程度 | 问题 | 双方一致 |
|---|---------|------|---------|
| 1 | **CRITICAL** | "Template matching" 攻击：3 个 macro 对应 3 个 family，inductor 本质是分类+填槽 | ✅ 双方均指出 |
| 2 | **CRITICAL** | DSL post-hoc 设计嫌疑：3 个 family 刚好覆盖 3 类任务 | ✅ 双方均指出 |
| 3 | **CRITICAL** | Evaluation scale 太小：3 family, 6 LOO tasks，统计力度不足 | ✅ 双方均指出 |
| 4 | **MAJOR** | Baseline 不完整：缺 PAL/PoT/ProbLog 等 neuro-symbolic 对比 | ✅ 双方均指出 |
| 5 | **MAJOR** | Inductor 统计可信度：N=6, pass@1=100% 没有统计意义 | ✅ 双方均指出 |

### Codex 独有问题

| # | 严重程度 | 问题 | Claude 判定 |
|---|---------|------|------------|
| 6 | **CRITICAL** | "computation bottleneck" claim 没有因果隔离——需要 Parse/Compute/Decide 三段式诊断 | **AGREE** — 这是最核心的科学贡献点 |
| 7 | **MAJOR** | Verifier 可能有 data leakage：induction/verification/evaluation 数据要不重叠 | **AGREE** — 需要严格拆分三套数据 |
| 8 | **MAJOR** | user_separate 60.8% vs Oracle 74.8% 的 gap 说明 decision following 也是问题 | **AGREE** — claim 需要从 "the bottleneck" 改为 "a major bottleneck" |
| 9 | **MINOR** | 论文结构应问题驱动（Q1/Q2/Q3），不要从 DSL 入手 | **AGREE** — 很好的写作建议 |

### Claude 独有问题

| # | 严重程度 | 问题 | 独立判断 |
|---|---------|------|---------|
| 10 | **MAJOR** | 需要 compositional task 证明不是 template matching（组合两个 macro） | 很好的建议，直接回应攻击点 1 |
| 11 | **MAJOR** | DSL coverage analysis 缺失：需要从教科书采样分析覆盖率 | 可行且有价值 |
| 12 | **MINOR** | 建议加 MATH/MMLU 概率子集作为外部验证 | 值得考虑 |

### Story 建议汇总

**Codex**: "LLM 能恢复任务结构但无法稳定执行概率推断。用 TaskSpec/DSL 把 task-level semantics 编译成 reusable solver。" → 三问题驱动: Q1 LLM 哪里错? Q2 能否从样本归纳 solver? Q3 跨 family/domain 复用?

**Claude**: "Neuro-symbolic program synthesis for probabilistic reasoning. 解耦理解与计算。" → 关键词: verified, program synthesis

**共识叙事**: 不要对立 "computation vs understanding"，而是讲 "LLM 擅长结构提取，弱于概率计算；我们自动 induce + verify 可复用的精确 solver"

### Venue 建议

| Venue | Codex | Claude | 综合判断 |
|-------|-------|--------|---------|
| **ICLR** | 首选 ✅ | 次选 | 如果补 causal diagnosis + baselines + 2 外部 benchmark |
| **ACL/EMNLP** | 次选 | 首选 ✅ | NLP venue 对 LLM reasoning 更友好，benchmark 数量要求宽松 |
| **NeurIPS** | 不推荐 | 需完成 P0+P1 | 对 generality/theory 要求太高 |
| **ICML** | 不推荐 | 不推荐 | 偏理论 |

### 亮点（双方认可）

1. **方法链条干净**: DSL → TaskSpec → Compiler → Inductor → Verifier 是 reviewer 能快速理解的 system abstraction
2. **23 策略梯度**: baseline < COT < full_math < tool_use < separate < oracle 这条阶梯本身就是好 figure
3. **两个 family 打穿**: BLInD MAE=0.000, TextBandit sidecar=oracle，说明在 VE 和 conjugate update 上不是小修补

### 致命问题

**无根本性方法学漏洞**。但 claim-evidence mismatch 可能导致 reject：如果坚持 "computation is THE bottleneck" + "solver induction" 而不补 causal diagnosis、强 baseline、外部 benchmark，会被定性为 "benchmark-specific schema extraction plus privileged answer injection"。

---

## Critical Path（三件最重要的事）

按 Codex 建议的优先级：

### 1. Computation-vs-Understanding Intervention（最关键）
- Parse Acc: LLM 能否正确抽取变量/证据/动作空间
- Compute Acc | gold parse: 给金标准 state，LLM 自己算 posterior
- Decide Acc | gold posterior: 给正确 posterior，LLM 选答案
- 这个实验直接支撑核心 claim

### 2. 冻结 DSL 后上外部 Benchmark
- CausalBN-Bench（ASIA/ALARM 经典 BN）— 无需新 family，最能证明 VE 不是为 BLInD 定制
- DeLLMa（农业/股票决策）— 如果能用小 extension 支持，显著加强 generality
- Compositional task — 组合两个 macro，防御 template matching 攻击

### 3. 强 Baseline 对比
- LLM → Python/NumPy
- LLM → ProbLog/pgmpy
- PAL (Program-Aided Language Models)
- PoT (Program of Thought)
- Structured extractor + handwritten compiler

---

## Claude 评价

Codex 的审查非常深入且具体，尤其是以下几点我完全赞同：
- **因果诊断**是核心——没有它，"computation bottleneck" claim 无法站住
- **问题驱动的论文结构**（Q1/Q2/Q3）比技术驱动更好
- **claim 降级**从 "the bottleneck" 到 "a major bottleneck" 是必要的
- **数据三套拆分**（induction/verification/test）是严谨性要求

本轮不需要辩论——所有问题都是合理且可操作的。
