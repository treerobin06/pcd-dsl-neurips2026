# Codex Review Report — Round 2 (实验设计 + Contribution)

**审查类型**: 实验设计审查 + Contribution 重要性评估 (Template A + B)
**审查重点**: 实验设计是否合理，contribution 是否重要
**开始时间**: 2026-03-14 04:00
**Codex 模型**: GPT-5.4 (xhigh reasoning)

---

## Round 1 — 2026-03-14 04:05

**Codex 评分**: 5.5/10
**Claude 预审**: 偏弱 NeurIPS，合适 AAAI
**来源**: Codex + Claude 预审

### 交叉验证

| # | 严重程度 | 问题 | 双方 | Claude 判定 | 处置 |
|---|---------|------|------|------------|------|
| 1 | CRITICAL | **GPT-5.4 compile-time=100% 自我削弱论文必要性**: reviewer 会说"问题随 scaling 自然解决" | 双方 | **PARTIALLY_AGREE** | 需重新 frame |
| 2 | CRITICAL | **3-Gate Verifier 泄漏**: Reference Match 用 benchmark 标签，verification/evaluation 未隔离 | 仅 Codex | **AGREE** | 需补 ablation + 隔离 |
| 3 | MAJOR | **Benchmark 覆盖面窄 + DSL 3 macros ≈ 3 benchmarks**: 看起来像 over-fitting | 双方 | **AGREE** | 需扩展或收窄 claim |
| 4 | MAJOR | **C1 (PCD) novelty 有限**: PAL/BLInD 已隐含此发现 | 双方 | **AGREE** | 降为 supporting |
| 5 | MAJOR | **缺 BLInD 原有 baseline**: MC/ProbLog 97-98% | 仅 Codex | **AGREE** | 需正面讨论 |
| 6 | MAJOR | **DSL ablation 缺失**: 分不清 DSL/verifier/macros 各自贡献 | 双方 | **AGREE** | 需做 ablation |
| 7 | MAJOR | **PCD 只用 OpenAI 模型** | 仅 Claude | **PARTIALLY_AGREE** | 至少加一个非 OpenAI |
| 8 | MAJOR | **"工程 vs 研究" 定位风险** | 仅 Claude | **PARTIALLY_AGREE** | framing 问题 |
| 9 | MINOR | **Semantic Parse cherry-pick 需完整报告** | 仅 Codex | **AGREE** | 改用 conditional analysis |
| 10 | MINOR | **Decide=100% 几乎 trivial** | 双方 | **AGREE** | 降低强调 |
| 11 | MINOR | **API 可重复性细节** | 仅 Codex | **AGREE** | 补充 |
| 12 | SUGGESTION | **论文主轴 C2，C1/C3 降为 supporting** | 仅 Codex | **AGREE** | 采纳 |

### 关键判定详解

#### Issue 1: GPT-5.4 compile-time 削弱必要性 — PARTIALLY_AGREE

**问题**: GPT-5.4 的 compile-time solver 达到 100%，说明 frontier model 可以不依赖 DSL 直接合成正确 solver。Reviewer 会说"模型扩展就能解决，你的方法是临时方案"。

**我的判断**: 需要 reframe 但不致命。

**证据**:
- GPT-4o 和 GPT-4o-mini compile-time code gen **完全失败** (0/900) — 不是所有模型都能写 solver
- 成本差距: GPT-4o-mini $0.15/1M vs GPT-5.4 $10/1M = **67x cheaper**
- GPT-5.4 初始代码也有 bug，需要 1 轮 repair — 不是一次性成功
- GPT-5.4 的 Python solver 没有形式验证 — corner case 无保证

**正确 framing**: "Our DSL+Compiler democratizes exact probabilistic solver synthesis — making it reliable with cheap models, auditable with 3-Gate verification, and robust regardless of model capability. While frontier models can occasionally achieve this through raw code generation, they do so unreliably and without formal guarantees."

#### Issue 2: 3-Gate Verifier 泄漏 — AGREE

**Codex 最锐利的洞察**。3-Gate Verifier 的 Gate 3 (Reference Match) 使用 gold solver 输出来验证 induced solver。如果：
1. Induction 使用 BLInD 子集 + Gate 3 验证
2. 然后在 BLInD 全集上报告准确率
那么 Gate 3 就相当于用了部分 benchmark 标签来 tune solver，存在信息泄漏。

**LOO 实验是干净的**: Hotel 数据从未被 inductor 看到。
**BLInD 需要说清楚**: induction 用了哪些样本，evaluation 用了哪些。

**需要的修补**:
1. 明确报告 induction/verification/evaluation 数据划分
2. 添加 "Gate 3 关闭" 的 ablation — 只用 Gate 1 + 2 能否工作？
3. 讨论 deployment 场景: 新任务上没有 reference solver 时如何工作

#### Issue 3: Benchmark 覆盖面 + DSL-Benchmark 同构 — AGREE

3 macros → 3 families → 3 benchmarks，确实有 over-fitting 嫌疑。两种应对:
- **扩展 (贵)**: 添加新 benchmark (CausalBN-Bench? DeLLMa?)
- **收窄 claim (免费)**: 明确说 DSL 覆盖"结构化概率推理任务的三个典型 family"，不宣称 general

### 行动清单（按优先级）

| 优先级 | 行动 | 回应问题 | 预估 |
|:------:|------|---------|------|
| **P0** | **Reframe 论文主轴**: C2 为核心，C1/C3 为 supporting。不宣称"只有我们能做到"，改为"可靠+廉价+可验证" | #1, #4, #8, #12 | 0 (写作) |
| **P0** | **Verification/Evaluation 隔离**: 明确数据划分 + Gate 3 off ablation | #2 | 1 天 |
| **P0** | **正面讨论 BLInD 原有 baselines**: MC/ProbLog 97-98%，我们的优势是 exact + cheap model + verified | #5 | 0 (写作) |
| **P1** | **DSL ablation**: (a) 无 macros (raw ops), (b) 无 verifier, (c) 无 reference match, (d) GPT-5.4 code gen + same verification budget | #6 | 1-2 天 |
| **P1** | **Claim 收窄**: "三个 typical families of structured probabilistic tasks"，不说 general | #3 | 0 (写作) |
| **P1** | **非 OpenAI PCD**: 至少在 Claude 或 Gemini 上跑一个 PCD | #7 | 0.5 天 |
| **P2** | **Conditional analysis 替代 Semantic Parse**: 用 Compute|Full Parse Correct 替代 cherry-picked metric | #9 | 0 (已有数据) |
| **P2** | **API 可重复性**: 温度=0, 种子固定, 报告调用日期, Bootstrap CI | #11 | 0.5 天 |

### Codex 原始回复
<details><summary>展开</summary>

**总体评价**
这题重要，而且方向是对的。近两年相关工作已经分别证明了：LLM 在概率/Bayesian 推理上持续失真；per-instance program execution、BN hybrid inference、ad hoc probabilistic model synthesis、以及 training-based Bayesian teaching 都能部分缓解问题。因此，你这篇最有价值的点不是"LLM+symbolic"本身，而是"用廉价模型做 few-shot compile-time spec induction，再由确定性编译器给出可审计的 exact solver"。如果 verifier protocol 是干净的，这有顶会潜力；如果不干净，这会被当成 benchmark-specific solver recovery 而拒掉。

**评分**: 5.5/10

**关键建议**:
- 把论文主轴改成 C2 = verified compile-time solver induction with cheap models
- C1 降为 mechanistic diagnosis, C3 降为 empirical validation
- 3-Gate Verifier 必须证明 verification 和 evaluation 严格隔离
- 正面讨论 BLInD MC/ProbLog 97-98% baseline
- 补 ablation: DSL without macros, without verifier, without reference match
- GPT-5.4 的 framing: "frontier model 偶尔能直接 synthesize solver，但 DSL+compiler 把这种能力压缩成便宜模型也能稳定复现、无需 self-repair、且更可审计"

**亮点**:
- 证据链很完整（9 项），比大多数 neuro-symbolic 论文严谨
- Evidence 9 是少见的真正 matched baseline
- Compile-once exactness 叙事很强

**致命问题**:
- 如果 Reference Match 是方法的一部分（用于 induction loop），则 verification 和 evaluation 没有隔离，所谓"形式保证"只是 benchmark-conditional
- 如果不修复，按 weak reject 处理

</details>

---

## Round 1 总结

**评分**: 5.5/10 (Codex)
**停止条件**: 未达标 (< 7/10)

### 最需要关注的两个问题

1. **3-Gate Verifier 隔离** — 这是本轮最严重的新发现。需要明确数据划分 + Gate 3 ablation
2. **论文 framing** — 主轴 C2 (verified compile-time solver induction with cheap models)，而不是三个等权贡献

### 关于 Codex 评分 5.5 vs 上轮 6.7 的说明

本轮审查聚焦于 contribution 重要性和实验设计合理性（更深层问题），上轮聚焦于证据完备性。5.5 反映的是 "目前的 framing 和实验设计在顶会标准下还有明显短板"，不是说证据变差了。主要扣分点:
- C1 novelty 被高估 (-0.5)
- 3-Gate 隔离问题 (-0.5)
- DSL 覆盖面 = benchmark 覆盖面 (-0.5)
- 缺 ablation (-0.5)
- GPT-5.4 framing 未处理 (-0.5)
