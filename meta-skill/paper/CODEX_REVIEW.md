# Codex Review Report

**审查类型**: 论文审查 (Template C)
**审查对象**: `main.tex` — Compile Once, Reason Exactly
**审查方式**: 5 路并行审查（Codex GPT-5.4 + 4 个 Claude Opus subagent）
**开始时间**: 2026-03-15

---

## Round 1 — 2026-03-15

(Round 1 内容省略，见 git history)

---

## Round 2 — 2026-03-18（附录扩充专项审查）

**Codex 评分**: 7/10
**来源**: Codex (GPT-5.4, xhigh reasoning) + Claude 预审

### 审查焦点

论文附录目前内容较少，有大量实验数据尚未放入。本轮聚焦：哪些内容最应该加入附录。

### 问题列表

| # | 严重程度 | 问题 | Claude 判定 | 处置 |
|---|---------|------|------------|------|
| 1 | CRITICAL | 缺 Inductor Reliability + LOO 泛化详细表格，100% 会被当 cherry-pick | TBD | |
| 2 | CRITICAL | 缺可审计的成本表 + amortization 曲线，310×/970× 无法验证 | TBD | |
| 3 | CRITICAL | Compile-time baseline 中 harness IndentationError 影响公平性 | TBD | |
| 4 | MAJOR | App D 只有 protocol 没有完整 PCD 结果，证据宽度不够 | TBD | |
| 5 | MAJOR | App C 策略消融只有分类列举，缺完整主表和服从率机制分析 | TBD | |
| 6 | MAJOR | 缺完整 prompt 模板，可复现性不足 | TBD | |
| 7 | MINOR | DeLLMa 负面结果应单独成节作为边界条件 | TBD | |
| 8 | SUGGESTION | 附录按 claim 组织而非零散材料；图从 60+ 精选 4-6 张 | TBD | |

### Codex 原始回复
<details><summary>展开</summary>

**总体评价**
主线很强：你们不是只报一个更高分，而是给出"诊断瓶颈 -> 设计 DSL/编译器 -> 归纳 exact solver -> 获得低成本 100%"的完整因果链。问题在于，当前附录没有把最容易被审稿人攻击的三处补齐：稳定性/非 cherry-pick、成本核算、baseline 公平性；这会让结果显得"太干净"。

**评分**: 7/10

**CRITICAL 1: Inductor Reliability and LOO Generalization**
审稿人一定会问：100% 是否只是一次 lucky run、一个 prompt、一个 seed。你现在最该补的是 20 次重复 × 2 families、temperature 0.7、R1 通过率、k=1 vs k=3/5、以及 6 个 held-out 数据集的逐数据集明细表。表里不要只放 final accuracy，要放 Family / Features / Values 是否识别正确、TaskSpec 是否 gold match、是否 first-round pass。

**CRITICAL 2: Cost Accounting and Amortization**
审稿人第二个必问问题是：310x / 970x / 3600x 到底怎么算的，是否把 compile-once 的一次性成本藏掉了。你需要一张可审计的成本表：每个方法的 #calls、input/output tokens、unit price、one-time induction cost、marginal per-query cost。最重要的是再加一张 cost vs #queries 的 amortization / break-even 曲线。

**CRITICAL 3: Baseline Fairness Audit**
GPT-4o 的 compile-time baseline 失败里包含 harness 的 IndentationError 拼接边界 bug。只要审稿人抓住这一点，就可以说"不是模型不会写 solver，而是你们 baseline 工程不稳"。建议修复 harness 重跑，或把失败分成四类报告。

**MAJOR 4: Full PCD Results Across Models and Depths**
应把现有 App D 扩成完整结果节，包含 6 个模型的 Parse/Compute/Decide，BN depth 2-10 的 Compute|GoldParse 明细表。

**MAJOR 5: Full Strategy Ablation and Compliance Mechanism**
需要完整主表：18+ strategies × GPT-4o-mini 的 accuracy / adherence / R1-R5 / 95% CI；跨模型对比表；adherence vs accuracy 散点图。

**MAJOR 6: Exact Prompts and Verifier Feedback Format**
PCD 三阶段 prompt、inductor prompt、verifier 反馈格式全部放出。

**MINOR 7: Boundary Cases / Negative Results**
DeLLMa 负面结果值得放，但只应作为边界条件。

**SUGGESTION: 附录组织方式**
按 claim 组织：(1) Tasks/setup, (2) DSL/compiler/TaskSpec formalism, (3) PCD protocol + full results, (4) induction ablations, (5) reliability + LOO + external validation, (6) cost accounting + baseline fairness audit, (7) full prompts/artifacts。图从 60+ 精选 4-6 张。

</details>

### Claude 预审结果

(待补充)
