# Codex Review Report

**审查类型**: 实验结果分析 + 研究方向规划 (Template A + B)
**审查重点**: 分析目前 7 项实验证据的完备性，评估当前 claim 的支撑强度，规划下一步最高 ROI 的研究方向
**开始时间**: 2026-03-14 00:45
**Codex 模型**: GPT-5.4 (xhigh reasoning)

---

## Round 1 — 2026-03-14 00:50

**Codex 评分**: 6.7/10 (+0.7 from previous 6/10)
**Claude 预审评分**: 6/10
**来源**: Codex + Claude 预审

### 交叉验证：双方共识

| # | 严重程度 | 问题 | 双方 | Claude 判定 | 处置 |
|---|---------|------|------|------------|------|
| 1 | CRITICAL | **Semantic Parse 定义 cherry-pick**: BN 排除 edges(51%) 和 evidence(65%)，overall parse 只有 34%，被包装成 98.4% | 双方 | **AGREE** | 需修复 |
| 2 | CRITICAL | **缺外部 benchmark**: 所有任务自建，reviewer 质疑外部效度 | 双方 | **AGREE** | 需做实验 |
| 3 | CRITICAL | **compile-time matched baseline 缺失**: PAL 是 per-instance，不够公平 | 双方 | **AGREE** | 需做实验 |
| 4 | MAJOR | **Claim 需收窄**: "bottleneck is computation not understanding" 走得太远，应改为 "after task extraction, dominant residual bottleneck is computation" | 双方 | **AGREE** | 修改措辞 |
| 5 | MAJOR | **Preference Parse=82% 不够强**: 18% 理解错误不可忽视，只能作 supporting evidence | 双方 | **AGREE** | 承认局限 |

### 仅 Codex 提到的问题

| # | 严重程度 | 问题 | Claude 判定 | 理由 |
|---|---------|------|------------|------|
| 6 | CRITICAL | **Construct validity**: gold parse 同时改变了语义和表示形式，gain 可能来自 reformatting 而非修复理解 | **AGREE** | 很好的洞察——compute prompt 比原始 NL 更结构化，确实混杂了 "format scaffolding" 效应 |
| 7 | MAJOR | **需要 component-wise intervention**: 分别替换 edges、evidence、full parse，测对 compute 的影响 | **PARTIALLY_AGREE** | 好主意但工作量大，可以简化为"在 parse 全对子集中看 compute" |
| 8 | MAJOR | **Supervision/coverage 需报清楚**: DSL 是看过哪些任务设计的，failure rate 是多少 | **AGREE** | 高 ROI，文档工作 |
| 9 | SUGGESTION | **Figure 设计**: 左图 line plot (3 lines + gap shading)，右图 grouped bars | **AGREE** | 采纳 |

### 仅 Claude 预审提到的问题

| # | 严重程度 | 问题 | Claude 判定 | 理由 |
|---|---------|------|------------|------|
| 10 | CRITICAL | **单模型 PCD**: 只在 GPT-4o-mini 上做，reviewer 说"弱模型才有这问题" | **AGREE** | 需要至少一个强模型补充 |
| 11 | MAJOR | **"Wrong posterior" 对照缺失**: 没测过给错误 compute 的结果 | **PARTIALLY_AGREE** | 有 random_rec 控制组(36.3%)做了部分回答，但 PCD 框架内确实缺 |
| 12 | SUGGESTION | **Conditional analysis**: 在 parse 全对子集中看 compute accuracy | **AGREE** | 高 ROI，直接从现有数据计算 |

### 优先级排序分歧

| | Codex | Claude 预审 | Claude 主进程判断 |
|---|---|---|---|
| #1 优先 | c) compile-time baseline | 多模型 PCD | **c) compile-time baseline** (同意 Codex) |
| #2 优先 | a) 外部 benchmark | 外部 benchmark | **a) 外部 benchmark** (共识) |
| #3 优先 | h) component-wise intervention | reusable PAL | **多模型 PCD** (取 Claude 的，因为直接回答最常见攻击) |
| #4 优先 | e) coverage 报告 | - | **e) coverage 报告** (高 ROI 低成本) |

**判断理由**: Codex 把多模型 PCD 降到 #5 的论点是"如果 c 用 frontier model 做就部分回答了"——但实际上 c 和多模型 PCD 回答的是不同的问题。c 回答"你的方法 vs 让强模型自己写 solver"，多模型 PCD 回答"理解-计算分离 pattern 是否跨模型成立"。两者都重要，但 PCD 是论文核心 claim 的直接证据，应优先于 component-wise intervention。

### 可立即从现有数据计算的分析 (Step C)

Codex 和 Claude 都建议从现有数据做 **conditional analysis**（parse 全对子集中的 compute accuracy），以及更透明的 parse 报告。这不需要新 API 调用。

### Codex 原始回复
<details><summary>展开</summary>

**总体评价**
这篇工作现在已经有了"方法成立 + 诊断有洞见"的雏形。Evidence 7 明显抬高了科学说服力，但论文当前最危险的点仍是：你们对 understanding 的 operationalization 还不够严，导致 strongest claim 比证据走得更远。

**评分**: 6.7/10

**关键建议**:
- Claim 收窄为 "after task extraction, the dominant residual bottleneck is exact computation"
- Semantic Parse 不要排除 edges/evidence，改为同时报 Full Parse 和 Decision-Sufficient Parse
- 做 representation-matched PCD: 只替换错误字段，分别测 +edges/+evidence/+full parse
- compile-time matched baseline 仍是 #1 must-have
- Figure: 两栏 line plot + gap bars，标题改为 "Task Extraction Remains Stable While Exact Computation Fails with Depth"

**优先级**: c > a > h(component-wise intervention) > e > b > g > d > f

**亮点**:
- Evidence 1 + 7 组合漂亮：user_separate=Oracle + Decide=100% 堵死了 decision failure 假说
- DSL equivalence + compiler + 3-Gate 给了罕见的 exactness story
- LOO + depth-OOD 让方法不只是单任务 hack

**致命问题**: 如果继续强版本 claim 且 Semantic Parse 排除 edges/evidence，足以导致 reject。收窄 claim + 补 c + a 后无致命 blocker。

</details>

---

## 即时可做的修复 (从现有数据)

### Conditional Analysis 结果

**BN: 在 parse 全对子集中的 Compute accuracy** — 直接回应 Semantic Parse cherry-pick 攻击

| Depth | Compute\|All (N=900) | Compute\|Full Parse Correct (N=305) | Compute\|Semantic+Evidence (N=580) |
|:-----:|:----:|:----:|:----:|
| 2 | 82% | **100%** (81/81) | 100% |
| 3 | 49% | **67%** (4/6) | 77% |
| 4 | 30% | **44%** (25/57) | 44% |
| 5 | 11% | **28%** (7/25) | 23% |
| 6 | 12% | **19%** (6/31) | 18% |
| 7 | 8% | **16%** (5/32) | 12% |
| 8 | 4% | **10%** (4/40) | 6% |
| 9 | 2% | **0%** (0/14) | 1.5% |
| 10 | 3% | **0%** (0/19) | 2.9% |

**关键洞察**: 即使在 parse 100% 正确（包括 edges 和 evidence）的子集中：
1. **Compute 仍然随 depth 急剧退化**（100% → 0%）
2. depth=9-10 上，**LLM 完全理解了 BN 结构但 0% 的计算正确率**
3. parse 全对后 compute 略高于总体（43% vs 22%），说明 parse 错误确实贡献了一部分 compute 错误
4. 但 **depth-dependent degradation pattern 完全保留**——这不是 parse 问题能解释的

**结论**: 这组数据让我们可以安全地说 "even when understanding is perfect, computation fails" — 比排除字段的 Semantic Parse 指标**更有说服力**。

### 推荐的论文报告方式

不要再用"Semantic Parse"这个包装。改为：
1. **主报告**: Compute|Full Parse Correct（最保守、最诚实）
2. **辅助报告**: 分字段 parse accuracy 表格（variables=100%, cpt=98.4%, query=100%, evidence=65%, edges=51%）
3. **Figure**: 两条线 — Parse 和 Compute|Parse Correct，展示 depth-dependent divergence

这样既不 cherry-pick，又保留了核心发现。

---

## Round 1 总结

**评分**: 6.7/10（Codex）/ 6/10（Claude 预审）
**停止条件**: 未达标（< 7/10），Round 1 完成

### 确认的行动清单（按优先级）

| 优先级 | 行动 | 回应的问题 | 预估耗时 | 预估费用 |
|:------:|------|-----------|---------|---------|
| **P0** | **Compile-time matched baseline**: 让 GPT-4o 看 3-5 个样本写 reusable Python solver + repair | #3 PAL 不公平 | 2 天 | ~$20 |
| **P0** | **外部 benchmark**: BLInD end-to-end baseline matrix | #2 无外部验证 | 2 天 | ~$30 |
| **P0** | **多模型 PCD**: 至少在 GPT-4o 上跑 PCD | #10 单模型 | 1 天 | ~$15 |
| **P1** | **Coverage/supervision 报告**: DSL 设计 effort、pass rate、reject rate | #8 | 0.5 天 | $0 |
| **P1** | **Claim 收窄**: "after task extraction, dominant residual bottleneck is computation" | #4 | 0.5 天 | $0 |
| **P2** | Verification ablation | - | 1 天 | ~$5 |
| **P2** | Compositional task | - | 1 天 | ~$10 |
| **P3** | ProbLog/pgmpy baseline | - | 1 天 | ~$5 |
