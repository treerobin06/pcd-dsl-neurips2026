# Master Plan — Compile Once, Reason Exactly (投稿前最终修复计划)

**版本**: 2026-04-23
**作者**: Tree + Claude Opus 4.7
**用途**: `/ultraplan` / `/ultrareview` 的统一审查对象
**关联文档**:
- `meta-skill/CLAUDE.md` 第六章"待做事项"——完整 todo
- `paper/audits/2026-04-23-{citation-verifier,result-to-claim,experiment-audit,paper-claim-audit,paper-claim-audit-detailed}.md`——四独立 agent 审查原始报告

---

## 1. Executive Summary

NeurIPS 2026 目标论文 *Compile Once, Reason Exactly: Verified Solver Induction for LLM Probabilistic Reasoning*，当前初稿状态综合评审 6-7/10。

**2026-04-23 Tree 触发四 agent 独立交叉审查** + 深度手工核查，发现：

- **叙事层硬伤 2 处**（C1 bnlearn / C2 NB+HMM）——raw 数字与论文 headline 数字差距极大；论文把手写脚本的假 100% 冒充 LLM agent 表现
- **实现层硬伤 2 处**（multiply_factors 空壳 / dsl_p=gold_p fallback）——代码 bug 导致 bnlearn compile_core_ops 被强制 0%；verify 脚本永远返回假 100%
- **数据层硬伤 4 处**（C4 Gate 3 假独立 / C5 Inductor prompt 喂答案 / C6 LOO 同样本两用 / S10 PAL 数字矛盾）——测试流程不严谨
- **叙事层 13+ 条数字 MATCH**——论文骨架（PCD / E2E / PAL 主数字 / Inductor reliability）对得上 raw，保留

**Tree 战略定调**（2026-04-23 晚）："**完整+量少，same-model 跨 method 对比好于 baseline 就行，不吹 100%**"——不追求虚幻数字，修 bug 得真实数字，能赢 baseline 就是 contribution。

**修复预估**: 6.5-12 天 / 预算 $30-80（最小刚需 $30-55，推荐 $50-80）

---

## 2. 当前发现总清单（从四 agent 审查 + 深度核查）

### Critical（叙事/实现欺诈，投稿前必修）

| ID | 问题 | 根因 | 影响 |
|:-:|---|---|---|
| **C1** | bnlearn 100% 是叙事欺诈 + 代码 bug 双重问题 | (a) figure 用手写 verify 脚本的假 100% 冒充 LLM agent 的 0%；(b) `run_bnlearn_held_out.py` 的 `multiply_factors` 是空壳（`mul2` 只有 `pass`，连 `reduce` 都没调）；(c) CPT `entries[:3]` 截断让 LLM 看不全 | ✅ 已修代码（commit d6ca496 + 9963f2f）；待冒烟验证 |
| **C2** | NB/HMM "core-ops 组合 100%" 叙事欺诈 | `held_out_nb_mini` raw: `parse=0.03 / compute=0.37 / compile_core_ops=1.0`。"100%" 是绕过 Parse/Compute 的纯 solver 分数 | 🔲 论文需明示 Parse=3% NB、Compute=37%；重写 "compositional generalization" claim |
| **C3** | DSL Compute 100% 近似 tautology | `taskspec/compiler.py:68-70` 对 BN 直接返回 `BNReferenceSolver()`——"编译"实为路由到手写 solver | 🔲 改 compiler 做真编译 + 重跑等价性 |
| **C4** | Gate 3 假独立 | LOO/Gate3-off 的 `gold_solver` 和 compiler 输出是**同一实现类两实例**，不是独立 gold | 🔲 换独立 gold（如 pgmpy）+ 重跑 LOO/Gate3-off |
| **C5** | Inductor prompt 喂答案 | 原样 `json.dumps(sample)` 含 `reward_fn`/`answers`/`correct_diagnosis`；prompt 模板显式要求看 `reward_fn` | 🔲 scrub prompt 输入（只保留 task description）+ 重跑 inductor 实验 |
| **C6** | LOO induction = verification（同样本两用） | `samples[:k]` 既喂 induction 又做 verify，违反论文 L371-395 声明 | 🔲 拆独立 held-out split + 重跑 LOO |

### Serious（限定/重算可救）

| ID | 问题 | 行动 |
|:-:|---|---|
| S1 | Parse 滑动定义（exact/structural/fieldwise 换口径）；Abstract 82-100% vs 实际 BN 30-48% / NB 3% | 论文全局统一 Parse 定义，每处标明口径 |
| S2 | Gate 2 Preference 无阈值（`verifier/gates.py:195-200` 总 pass） | 加阈值 + 重跑 Gate 2 |
| S3 | n=6 CI 下界 54-61%，论文只报点估计 | 报 CI 替代点估计 |
| S4 | 跨 baseline correct 口径混杂（`gold_solver_rec` vs `user_idx` vs `gold_user_choice`） | 统一口径 + 重算所有对比 |
| S5 | 成本数字不一致（正文 $0.008/14× vs App $0.001/60×，两套共存） | 统一到一套 + 改所有相关位置 |
| S6 | `lew2025discipl` 作者嫁接（bib 8 人实际 5 人，多 3 人从 `grand2024lilo` 拼接） | 修 bib |
| S7 | `jiang2026sok` 7/7 作者 first name 全错（Yuqi→Yanna, Dong→Delong 等） | 修 bib |
| S8 | L602 "two parse failures" 错，raw 实际 1 个 | 改成 "one parse failure" |
| S9 | 13+ 条数字真 MATCH | 保留不动 |
| S10 | bnlearn Direct/PAL 数字自相矛盾（paper 0%/0-3% vs raw 55-61%/17-23%），L994 "15%" vs L1011 "17.5%" | 统一到一次 run，全文改数字 |
| S11 | Gemini 模型变体名错（detailed audit L79-89） | 查 raw 确认模型 id，改论文 |
| S12 | 附录多项 raw 缺失（Gate-3-off / 23-strategy / LOO 6/6 / bnlearn per-query） | 重跑补齐或注明 "from prior logs" / 撤对应表 |

### 已修好 / 无动作

- ✅ `curtis2025pomdp` 作者已修对（CoRL 2025 7 人全对）
- ✅ `first2025alphaverify` 已从 bib 删除
- ✅ L493 duplicate label（全文 grep 无重复）

---

## 3. Root Cause Analysis（技术根因，用于 ultraplan/ultrareview 判断）

### 根因 1: `multiply_factors` 空壳（`run_bnlearn_held_out.py:281-293`）

**原代码**（已修）:
```python
def multiply_factors(factors: list) -> dict:
    from functools import reduce
    def mul2(f1, f2):
        result = {}
        for k1, v1 in f1.items():
            for k2, v2 in f2.items():
                merged = {**dict(k1), **dict(k2)} if isinstance(k1, tuple) else {}
                pass          # ← 空！
        return result         # ← 永远 {}
    # 也没调用 mul2，也没 reduce
```

Prompt 要求 LLM "MUST use these core operations"，LLM 看到这个空壳→要么用它（输出全 0）要么违反约束。compile_core_ops=0% 的**精确技术根因**。

**修复**（commit d6ca496）：真实现 multiply_factors + factor representation convention + 去 CPT `[:3]` 截断 + 删误导注释。

### 根因 2: `dsl_p = gold_p` fallback（`verify_bnlearn_dsl_100.py:117`）

原代码：
1. 传 `query_vars = {var: [all_states]}`（list 作 value）→ `ve_query` 签名是 `-> float`，L185 `vals[i] != [list]` 永远为 True → 返回 0.0
2. `isinstance(dsl_posterior, float) and >2 states` 分支：`dsl_p = gold_p` fallback → `max_err = 0` → 自动 correct

**两个 bug 叠加导致 bnlearn 100% 完全是 fallback 伪造**（DSL 从未真正跑过 bnlearn）。

**修复**（commit 9963f2f）：对每个 state 单独调 ve_query 拼 posterior + sanity check 归一化 + 真实误差比较。

### 根因 3: Inductor prompt 原样 dump sample（C5，尚未修）

`inductor/prompts/induction_prompt.md` + inductor 代码原样 `json.dumps(sample)`，内含：
- `reward_fn`（答案空间）
- `answers`（对应答案）
- `correct_diagnosis`（BN 正确预测）

LLM 看到这些直接复制就 100%。**LOO/E2E 的高数字怀疑是数据泄漏**——需 scrub 后重跑才知道真实数字。

### 根因 4: LOO `samples[:k]` 既 induce 又 verify（C6）

`tests/test_loo_induction.py` 的 `test_one_dataset` 用 `samples[:max_induction_samples]` 给 Inductor，但 verify 时也用同一批；实际应该 `samples[max_induction_samples:]` 做 held-out verify。

---

## 4. Tree 的战略方向

**核心原则**（Tree 2026-04-23 明确）：

> **"完整+量少，same-model 跨 method 比 baseline 好就行，不追求 100%。核心是论文写法加端到端 + 补齐实验错误。"**

**translate 成操作**：
- 不再追求任何 100% headline
- 所有数字用 raw 真实值（Parse NB 3% 要老老实实写）
- **every benchmark 加上 "Our + GPT-5.4 > PAL + GPT-5.4" 这种 same-model 跨 method 对比**（而不是跨模型挑最好的）
- 加 Mixed E2E 端到端（老师建议）作为最现实的 agent 能力数字
- 预期 Mixed E2E 落在 65-82%（围绕 74% Flight E2E），这个数字**就是论文真实贡献**
- 承认 Parse 瓶颈在大 BN 上，不遮掩

---

## 5. 修复方案（按优先级分层）

### Layer 0（零成本，立即做）

| # | 任务 | 状态 |
|:-:|---|:-:|
| 0.1 | 添加 4 份审查报告到 `paper/audits/` | ✅ committed |
| 0.2 | CLAUDE.md todo 更新（含 C/S 列表 + 战略 + 预算） | ✅ committed |
| 0.3 | `verify_bnlearn_dsl_100.py` 去 fallback + 正确 ve_query 调用 | ✅ committed |
| 0.4 | `run_bnlearn_held_out.py` 实现 `multiply_factors` + 去 CPT 截断 | ✅ committed |
| 0.5 | 修 bib `lew2025discipl` + `jiang2026sok` + 删 pgmpy import 依赖用 BIFReader 绕慢启动 | 🔲 待做 |
| 0.6 | 论文 L602 "two parse failures"→"one parse failure" | 🔲 待做 |
| 0.7 | 论文 L339 "1,200 instances"→"1,150" | 🔲 待做 |
| 0.8 | 论文 Cost 数字统一（$0.008/14× vs $0.001/60×，选一套） | 🔲 待做 |

### Layer 1（代码修复 + 本地重跑，零成本）

| # | 任务 | 预期结果 |
|:-:|---|---|
| 1.1 | 跑修好的 `verify_bnlearn_dsl_100.py` 全量（4 nets × 100 q，本地 Python） | DSL 数学正确性真实数字（预期 ≥95% on asia/child，大 BN 可能略低） |
| 1.2 | 跑 `test_equivalence_full.py`（BLInD 900 + Flight 250，本地） | 等价性真实数字 |
| 1.3 | Scrub Inductor prompt 的 `reward_fn/answers/correct_diagnosis`（C5） | prompt 不喂答案 |
| 1.4 | 拆 LOO `samples[:k]` 为独立 induction/verify split（C6） | 无数据泄漏 |
| 1.5 | Gate 2 加 preference 阈值（S2） | verifier 不再全 pass |

### Layer 2（LLM 实验重跑，付费，$30-55）

| # | 实验 | 模型 | 规模 | 预估 |
|:-:|---|---|---|:-:|
| 2.1 | bnlearn 5 modes 冒烟 | mini | asia×10q | $0.05 |
| 2.2 | bnlearn 5 modes 全量 | mini + gpt-5.4 | 4 nets×15q×5 modes | $8-15 |
| 2.3 | Inductor scrubbed reliability | mini | 40×2 replicate | $0.2 |
| 2.4 | LOO 独立 split 重跑 | mini | 6 数据集 | $0.1 |
| 2.5 | PAL + 3-round self-repair | mini | 100×3 | $0.5 |
| 2.6 | Mixed E2E（老师建议，主菜） | mini | 6 family × 50 | $0.3 |
| 2.7 | Mixed E2E 对照 | gpt-5.4 | 6 × 50 | $7-12 |
| 2.8 | Multi-model NL Parse | 3 模型 | 3×50 | $2-4 |
| 2.9 | Codex 独立审查 × 3 轮 | gpt-5.4 xhigh | ~15 调用 | $10-20 |

### Layer 3（可选，$50-100 额外）

- PCD 6 模型全量重跑（mini/gpt-4o/gpt-5.4/sonnet-4/gemini-3.1-pro/opus-4.6 × 400 问题）= $40-80
- 国产模型 bonus（GLM-5 via 交大免费）= $0

---

## 6. 论文行文改动方案

### Abstract
- [ ] 改 "Parse 82-100%" → "Parse varies by family: preference 82-100%, structured NB 3% when measured as exact-match"
- [ ] 首句改为 E2E 数字（Mixed E2E 的新跑数字）
- [ ] 100% 全加 "on compute stage, conditional on correct parsing" 限定
- [ ] 撤 "Our DSL bnlearn 100%"，改为"Verified DSL solver is mathematically exact (max_err < 1e-10 on bnlearn); end-to-end Inductor→TaskSpec→compile still bottlenecked by structure extraction on large BNs"

### Section 5/6 Experiments
- [ ] 加 **same-model 跨 method 对比主表**：
  - GPT-5.4 + Direct vs GPT-5.4 + PAL vs GPT-5.4 + Our
  - GPT-4o-mini + 同上
  - 每个 benchmark（Flight / Hotel / Bandit / BLInD / bnlearn / NB / HMM）
- [ ] **新增 Section 6.x Mixed E2E**：所有数据集 shuffle 后完整 agent 管线，报 overall accuracy + family recognition rate + per-family 分解
- [ ] PCD 表加 "NB Parse=3%" cell 明示不藏数据
- [ ] bnlearn section 全重写：区分 "DSL solver 数学正确" 与 "LLM agent 端到端"

### Table 3 + Figure 3
- [ ] Table 3 caption: "Parse >=98%" → "Parse ranges 3-100% across families; see cells"
- [ ] Figure 3a bnlearn: 撤硬编码 `our_dsl=[100,100,100,100]`，用真实数字（可能是 verify 脚本的 ≥95%，标明 "DSL math correctness given correct TaskSpec"）
- [ ] Figure 3b cost: 统一到一套成本数字

### Appendix
- [ ] App Table L1121-1126（LOO 6/6）：或重跑补 raw，或撤表注明 "reported from pytest stdout, JSON not persisted"
- [ ] 新增 Ablation Table: no-macros / no-verifier / no-self-refine
- [ ] 新增 Limitations: "Inductor on ≥20-node BN networks requires structured CPT input; free-form natural language parsing not yet reliable"

### Related Work
- [ ] 保留 SoK + EvoSkills 桥接
- [ ] 加 Logic.py NeurIPS 2025 版本引用

### Bib
- [ ] `lew2025discipl` 修作者 8→5 + 会议 NeurIPS→COLM
- [ ] `jiang2026sok` 7 作者 first name 全修
- [ ] `schick2023toolformer` 补 Eric Hambro

---

## 7. 风险评估

| 风险 | 可能性 | 影响 | 缓解 |
|---|:-:|:-:|---|
| bnlearn multiply_factors 修好但 compile_core_ops 仍 <30% | 中 | 高 | 先冒烟 10 queries，若仍低再诊断（可能还有其他 bug） |
| Mixed E2E 数字低于 60% | 低 | 高 | 基于 Flight E2E 74.3% + 各 subtask 数字推算，极不可能 <60% |
| Codex 独立审查发现新 Critical | 中 | 中 | 预算了 3 轮 codex-review，有修复窗口 |
| PAL 重跑 self-repair 后和 Our 差距缩小 | 中 | 中 | 仍有 Our + Compile-once 优势（零 LLM cost at inference） |
| pgmpy 1.0 import 慢卡住 local 实验 | 高 | 低 | 已绕：用 BIFReader + 自写 VE gold，不靠 pgmpy.inference |
| OpenRouter 额度不够 | 低 | 低 | 最小刚需 $30-55 在账户余额以下 |

---

## 8. Timeline 估算

| 阶段 | 工作 | 预计耗时 |
|:-:|---|:-:|
| T+0 | 今天：已完成 audits + 修 C1 代码 + 准备 master plan | ✅ |
| T+1 | Layer 0 剩余：bib 修复 / 数字统一 / BIFReader 绕 pgmpy | 0.5 天 |
| T+2 | Layer 1：C5/C6 代码修复 + 本地 verify 重跑 | 1.5 天 |
| T+3 | Layer 2：LLM 实验（bnlearn + Inductor + LOO + PAL + Mixed E2E） | 2-3 天 |
| T+4 | 论文改写（Abstract + Section 5/6 + bnlearn 重写 + Table 3 + Figure 3 + Appendix） | 2-3 天 |
| T+5 | Codex 独立审查 × 2-3 轮迭代修正 | 1-2 天 |
| T+6 | 终稿 + Overleaf 同步 + PDF 验证 | 0.5 天 |
| **合计** | | **7.5-10.5 天** |

---

## 9. 交给 ultraplan / ultrareview 的核心问题

**需要独立审查确认的战略决策点**：

1. **是否同意 Tree 的 "same-model 跨 method 对比 > 跨模型挑最好" 叙事？**——这个 framing 是否足以支撑 NeurIPS contribution？
2. **bnlearn 叙事怎么定？** A. 仅展示 DSL 数学正确性 / B. 修 Inductor 后展示 LLM 全链路实际数字 / C. 两者都报（区分 "math correctness" vs "agent capability"）
3. **C2 compositional generalization claim 要不要撤？**——NB Parse=3% 使得"generalization"自动化故事瓦解。是撤还是改成"given correct TaskSpec, DSL core-ops compose novel workflows"（数学层）？
4. **Mixed E2E 如果最终数字 65-70% 够不够 support 论文？**——比 Flight 74.3% 略低，是否还能站为"general agent capability"？
5. **Layer 2 实验的 $30-55 预算是否划得开**？——是否要考虑 skip 哪些？（比如 Multi-model NL Parse 的 $2-4 可不可跳）
6. **撤掉附录 Gate-3-off / 23-strategy 表 vs 重跑补齐，哪个更可取**？——时间 vs 完整性 tradeoff

---

## 10. 附录：git 状态

截至 2026-04-23 22:30：

**Branch**: `review/2026-04-23-audit-findings`

**Commits**:
1. `71ed6e9 audit: add 4-agent independent review reports (2026-04-23)` — 6 份 audit 报告 / 1259 行
2. `f99daf6 docs: update CLAUDE.md with 2026-04-23 audit findings + new strategy` — todo 结构化
3. `9963f2f fix(bnlearn): remove dsl_p = gold_p fallback that faked 100% accuracy (C1)` — verify 脚本修复
4. `d6ca496 fix(bnlearn): implement multiply_factors + remove CPT truncation in compile prompt` — prompt 层修复

**未 commit**:
- `paper/figures/figure1_*.png` 20 张 draft（paperbanana 多版本候选，总 ~12MB）——待 Tree 拍板保留哪个版本
- Master plan（本文）——commit 进去后总状态：5 commits ready for ultraplan/ultrareview

**可用于 ultrareview**: 当前 branch 对 main 有完整 diff（1 行 audit 报告 + 1 行 todo + 2 行 bug fix + 1 行 master plan）可以作为 review 对象。
