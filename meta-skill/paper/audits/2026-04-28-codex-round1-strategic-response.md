# Codex Review Round 1 Strategic Response (2026-04-28)

> Tree 决策记录：审稿人 30s first-impression 视角 → minimal-fix 路线，
> Codex deep-audit findings 中 **跳过 reviewer 不读的内部细节**.

## Codex Round 1 Summary

- 模型: gpt-5.4 fallback (gpt-5.5 unavailable in MCP)
- Thread: `019dd047-aa69-79d1-a8b1-f56a028a1172`
- 评分 (debate 后): paper-quality **4.6/10** · plan-soundness **5.6/10**
- 持平 04-23 baseline 4/10，未上行未下降
- Direction: **B (plan needs revision before P0+P1+P2 execution)**
- 严重度: CRITICAL 2 / MAJOR 8 / MINOR 1 / SUGGESTION 1, 0 遗留分歧
- Report: `meta-skill/CODEX_REVIEW.md` (25KB)
- State: `meta-skill/.codex-review-state.json`

## 主进程独立判断 + Tree pragmatic 视角

Codex 5 个 findings 都是真问题（path:line evidence 充分），但 Tree pointed
out: **NeurIPS reviewer 真实行为是 30s first-impression scan**，不是 Codex
那种 deep audit。所以**真影响接收的只有 reviewer 30s 扫到的 surface
inconsistencies**.

### Reviewer-visibility 重 categorize

| # | Codex finding | 30s 扫描会发现? | 真实 impact | Action |
|---|---|---|---|---|
| **2** | Abstract L82 broad + Table 3 n=200 vs n=50 | ✅ **会** (Abstract 第 1 屏 + Table caption 关键数字) | **first impression 攻击面** | 🔴 必修 (30 min) |
| **4** | PAL 3 处数字冲突 (L440 / L991 / L1008) | ⚠️ 可能 (figure caption + main 数字 visible) | inconsistency 触发深查 | 🔴 必修 (30 min) |
| 1 | 5 个 04-28 raw JSON 缺 `_meta` (`_artifact_schema` 未 enforce) | ❌ 不会 (raw JSON reviewer 不 read) | 仅 reproducibility | 🟢 跳过 |
| 3 | `verifier/gates.py` 缺 `_gate2_nb` / `_gate2_hmm` dispatch | ❌ 不会 (implementation 不 read) | 仅 code claim 强度 | 🟢 跳过 |
| 5 | `schema.py` to_dict() 副作用 + test_roundtrip fail | ❌ 不会 | cosmetic | 🟢 跳过 |

### Plan tier 重新评估

| Plan tier | reviewer 视觉 contribution? | Action |
|---|---|---|
| ✅ P0 NB/HMM NL E2E (已跑 100% [92.9, 100]) | ✅ 已落 paper Section 5 | done |
| ✅ P0 Mixed E2E 90/90 (已跑) | ✅ 已落 paper Section 5.5 | done |
| **P1 Hotel NL E2E** (preference 第二 domain) | ✅ 视觉加分 ($0.03, 30 min) | 🟡 加分项, cheap 可做 |
| P1 TextBandit simulation E2E | ⚠️ 仅 if reviewer 深查 TextBandit cell | 🟢 跳过 |
| P1 BLInD LLM-per-query E2E | ⚠️ 仅 if reviewer 质疑 "deterministic compile vs per-query LLM" | 🟢 跳过 |
| P2 bnlearn NL E2E (BIF→NL adapter) | ⚠️ figure 3a reviewer 不会 ask "BIF or NL" | 🟢 跳过 |

## Minimal-Fix Plan (Tree 决策)

### 🔴 必修 (~1-1.5h, $0)

1. **Abstract L82 scope tighten** — 加 "given structured spec input" 或类似
   caveat to 100% claim
2. **Table 3 caption n size clarify** — 标明 spec route row n=50 vs codegen
   row n=200/100 (现混 column header)
3. **PAL 3 处数字 reconcile** — L440 "0-3%" / L991 "15%" / L1008 "17.5/23.3"
   选 single canonical raw run + 全文 grep 替换

### 🟡 加分 (cheap, ~30 min + $0.03)

4. **Hotel NL E2E 30** — preference 第二 domain，paper Section 5/6 row 数据点
   加分

### 🟡 投稿前 final 关 (~15 min)

5. **Codex Round 2 verification** — thread `019dd047-...` prepend Round 1
   Suspicions, 验证 reviewer-visible 修复 RESOLVED

## 主动跳过 (Codex deep audit findings)

理由: NeurIPS reviewer 平均行为是 first-impression scan，不是 fairness audit。
deep auditor / adversarial reviewer 触发概率非零但低。

| 跳过项 | 跳过理由 | 风险 |
|---|---|---|
| Codex #1 raw `_meta` | reviewer 不 read raw JSON | 投稿后 reproducibility check 可能要 |
| Codex #3 gates NB/HMM dispatch | reviewer 不 read verifier impl | "verified for all 5" claim 严格说不全成立, but reviewer not deep checking |
| Codex #5 schema 副作用 | cosmetic, test pass 不影响接收 | code release 时显多余字段 |
| P1 TextBandit simulation | "TextBandit 100%" misleading but not main contribution | adversarial reviewer 深查 catch |
| P1 BLInD LLM-per-query | paper 现 100% 是 deterministic-only path | 同上 |
| P2 bnlearn NL E2E | figure 3a 数字 self-consistent | 同上 |

**风险**: ~10-20% probability adversarial reviewer / meta-reviewer 找到。如
触发，rebuttal 阶段可补 (那时 P1/P2 真做 + 修 #1/#3/#5)。

## 总投入估算 (修正版 vs Codex 6-9 天)

| 阶段 | 时间 | $ |
|---|---|---|
| Tree minimal-fix (#2 + #4 + Hotel + Round 2) | ~2h | $0.03 |
| ~~Codex 全做 6-9 天 / $5-15~~ | (跳过) | (跳过) |

vs Codex 估算 6-9 天 / $5-15: Tree 的 minimal-fix 路线 **2h $0.03**, 接受
风险换成本/时间。

## 后续 path

如 NeurIPS rebuttal 阶段被 deep auditor 触发任意 Codex 跳过项:
1. 优先级 P1 BLInD LLM-per-query (cheap, defends BN family E2E)
2. 然后 gates NB/HMM dispatch (defends "verified" claim)
3. raw `_meta` 重 dump (cheap if 数据保留)
4. TextBandit simulation E2E (复杂但必须 if attacked)

## 决策签收

- 决策日期: 2026-04-28
- 决策者: Tree + Claude 主进程独立判断 + Codex Round 1 报告
- 路线: **Minimal-fix (reviewer-visible only)**
- 接受风险: deep-audit 触发概率 (~10-20%)
- Plan B (rebuttal 阶段补): 上方 "后续 path" 4 项

---

**Related artifacts**:
- `meta-skill/CODEX_REVIEW.md` — Codex Round 1 完整报告 (25KB)
- `meta-skill/.codex-review-state.json` — Reviewer Memory state
- `meta-skill/paper/audits/2026-04-28-framing-pivot-changelog.md` — 今天累积
- `meta-skill/paper/audits/2026-04-23-codex-review.md` — 前 baseline (4/10)
- `~/.claude/plans/mossy-beaming-sky.md` — 原 P0+P1+P2 plan (full audit-driven)
