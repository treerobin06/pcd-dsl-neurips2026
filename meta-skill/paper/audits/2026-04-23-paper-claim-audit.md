# Paper Claim Audit — 2026-04-23

**审查者**: Claude Opus 4.7 (1M) + GPT-5.4 Codex MCP xhigh 独立并行
**论文**: `paper/main.tex` (Compile Once, Reason Exactly, NeurIPS 2026)
**审查范围**: Abstract / Intro / Table 2 / Table 3 / Fig 2 / Fig 3 / Sec 5-6 / Conclusion / Cost Appendix

## Summary

- 验证具体数字声称 **~30 条**，匹配 raw JSON **13 条**，scope/framing 误导 **5 条**，成本数字内部不一致 **1 条**，论文有细节 raw 不存储 **4 条**，明显 mismatch 待处理 **3 条**
- 审查方式：Codex x 1 次（80s 预算内返回 10 条结论）+ Claude fallback（Grep + Python JSON 核对）
- 完整度：**聚焦区域完成**（Abstract / Intro / Table 2-3 / Fig 2-3 / Sec 5-6 / Cost App / Conclusion）
- **总体评定**: **FAIL**——主位 100% 声明 scope 不匹配 raw，成本数字正文 vs 附录不一致，bnlearn per-network 论文有但 raw 缺，Parse 声明与 Table 3 caption 明显冲突

---

## 严重不匹配（数字对不上 raw）

| # | main.tex 行号 | 论文声称 | raw 实际 | raw 文件 | 差距 | 建议 |
|---|---|---|---|---|---|---|
| M1 | L108 | "Parse accuracy is 82--100% on **primary** task families" | BN task Parse 实际：mini=33.9% / 4o=48.3% / 5.4=30.7% / Sonnet=30.6%（`n=900` exact-match Parse） | `pcd_openai_gpt-{4o-mini,4o,5.4}_20260313_*.json` / `pcd_anthropic_claude-sonnet-4_20260313_213010.json` | BN Parse 远低于 82%，若 "primary" 包含 BN 这条严重误导 | 要么明确 "82-100% 仅指 Preference 任务"；要么合并报 BN exact vs fieldwise Parse 两档；Codex 同时指认为 MISMATCH |
| M2 | L553 caption + L576 | Table 3 caption + body: "Parse and Decide remain ≥98%" | GPT-4o-mini NB Parse = **3%**（n=200 raw 确认 0.03） | `held_out_nb_openai_gpt-4o-mini_205problems_20260314_225603.json` (`pcd.parse_accuracy=0.03`) | 3% vs ≥98% 是定性矛盾，caption 和 table 细胞公然冲突 | L583 Anomalies 段已承认，但 caption 仍全称声明——caption 应改为 "Parse ≥99% **except mini on NB at 3% (see Anomalies)**"；或 caption 明确 "primary metric = Core-ops Constrained accuracy"，让 PCD 分项退到表底 |
| M3 | L82 / L117 / L444 / L722 | 多处: "GPT-4o-mini produces solvers that achieve 100% compute-stage accuracy on **all tested BN benchmarks**, including real-world networks with up to 37 nodes" | **raw 中没有任何一份 `bnlearn_*.json` 存储 "mini DSL=100% on all 4 networks" 的结果**——Codex 独立确认同问题（Claim 1）。唯一带 compile 字段的 mini bnlearn 是 `compile_core_ops=0/120, compile_free=0/120`（均为 0） | `bnlearn_openai_gpt-4o-mini_*.json` 全部 6 份 | raw 层没有兑现"mini DSL 在 4 个 bnlearn 网络 100%"的证据——这对应 CLAUDE.md Critical Blocker **C1** (bnlearn 100% fallback 伪造) | 重跑 bnlearn 并在 raw JSON 里写入 per-network DSL 结果；在 raw 确认前，撤掉 "on all tested BN benchmarks including up to 37 nodes" 的全称或标为"待重跑" |

## Scope / Framing 问题（数字对但 framing 误导）

| # | 行号 | 问题 | 修复建议 |
|---|---|---|---|
| S1 | L82 Abstract / L117 Intro / L198 Table 2 / L434 / L444 / L592 / L670 Conclusion | 12 处左右 "100%" 未加 **"on compute stage, conditional on correct parsing"** 限定。主位 100% 密度过高，与 end-to-end 74.3% 形成 framing gap（CLAUDE.md 2026-04-23 讨论里 Tree 已经关注到的 100% 怀疑问题） | 所有 Compute Stage 100% 后加 "(compute stage, conditional on gold parse)"；所有 DSL-integration 100% 后加 "(compiled solver, deterministic)" |
| S2 | L407 / L768 Appendix | "All 6 LOO pass ... 100% match" 但 raw 里只有 NB + HMM 的 held_out 文件（4 份），**Hotel / Flight-2F/3F/5F/6F / BLInD-OOD 的 LOO raw 文件缺失**——App Table 1121-1126 全打 checkmark 但 raw JSON 不在 `baselines/results/` | 补存 LOO 6 数据集 raw JSON 到 `baselines/results/loo_*.json`，或在正文明确 "LOO results reproducible via `tests/test_loo_induction.py`" |
| S3 | L169 定义 / L184 Table 2 caption 说 "Parse is scored correct only when all fields match"；但 Codex 查 BN Parse=30-48% 表明此口径；**而 L108 同一术语 Parse 的声明 "82-100%" 明显用了另一口径** | Parse 定义在正文滑动，CLAUDE.md Serious S1 已列出 | 全局统一"exact structural Parse" vs "field-wise Parse" 定义，每次出现 Parse 数字时注明 "exact" or "fieldwise"；Abstract+Intro 建议换成 "structural Parse ≥95% on Preference / 30-48% on BN (exact match)"，不要混报 |
| S4 | L339 | "maximum absolute error below 10⁻¹² across all 1,200 test instances: Flight 250, BLInD 900, TextBandit 50" | **Codex 独立确认 MISSING_RAW**：`tests/test_equivalence_full.py` 只编码 BLInD 900 + Flight 250 = 1,150；TextBandit 50 block 不存在于 test 代码里。论文 1,200 的 50 TextBandit 部分**没有可核 raw 证据** | 要么补 TextBandit 50 等价性验证并存 raw；要么改报 "1,150 test instances: Flight 250 + BLInD 900" |
| S5 | L601 | E2E `74.3% [70.9%, 77.8%]` | raw 完全匹配（Codex 确认 MATCH）——但 L602 "gold solver match 99.8%" 与 raw `0.998395...` 匹配，"2 parse failures" 对应 raw `parse_success_rate=0.9984`（624 中 1 条 fail，不是 2 条）。**L602 "the remaining 0.2% gap traces to two parse failures" — raw 是 1 条 parse failure** | 改为 "1 parse failure" 或核查 0.998395 vs 0.99836 差异来源 |

## 其他发现

### F1 成本数字正文 vs 附录不一致（Codex 确认 INCONSISTENT）

| 位置 | our DSL cost | Compile-time (5.4) cost | 声称 ratio | 实算 ratio |
|---|---|---|---|---|
| L525-527 Fig 3 (body) | $0.008 | $0.11 | 14× | $0.11 / $0.008 = 13.75× ≈ 14× ✓ |
| L539 Fig 3 caption | $0.008 | $0.11 | 14× | 同上 ✓ |
| L592 Sec 5.4 | $0.008 | $0.11 (对 PAL $2.50 = 310×) | 310× | $2.50/$0.008 = 312× ≈ 310× ✓ |
| L722 Conclusion | — | — | 14× / 310× | 继承正文数字 ✓ |
| **L1135 / L1147 / L1158 Appendix** | **$0.001** | **$0.06** | **60×** | $0.06 / $0.001 = **60×** ✓ |
| `cost_analysis.md:19` | $0.00075 ≈ $0.001 | — | — | 与附录一致 |

**问题**：正文用 $0.008（inflated）报 14×，附录用 $0.001（真实）报 60×。两套数字都内部自洽，但 **Fig 3 / Abstract / Sec 5.4 的 14× 与 Appendix 的 60× 互相矛盾**——同一对比声称不同倍数。CLAUDE.md 2026-04-23 Serious S5 已列此问题。

**修复**：二选一：
- (a) 全文统一用 $0.001 / $0.06 / 60×（附录口径）→ 所有 Fig 3 / Abstract / Sec 5.4 改 14× 为 60×、改 $0.008 为 $0.001
- (b) 全文统一用 $0.008 / $0.11 / 14×（正文口径）→ 改 Appendix Table 1147-1151 与 L1135 为 $0.008

### F2 bnlearn App Table 有 per-network 但 raw 只有 overall（Codex 确认 MISSING_RAW）

| 位置 | 声称 | raw 存储 |
|---|---|---|
| L1006-1011 App Table | Asia/Child/Ins/Alarm 各自 PAL 27%/20%/23%/0% (mini) 和 90%/0%/3%/0% (5.4) | `bnlearn_openai_gpt-{mini,5.4}_*.json` **只存 overall**（`pal.accuracy=0.1750` 和 `0.2333`），networks 字段只有 name list 不含 per-net PAL 数字 |
| L442 正文 | "PAL with GPT-5.4 still reaches 90% on Asia" | 没在 raw JSON 找到 90%（Codex MISSING_RAW） |
| L478-481 Fig 3 coordinates | 硬编码每网络 PAL 数字入 TikZ | 同样绕开了 raw JSON |

**验证**：`python3 -c "import json; d=json.load(open('bnlearn_openai_gpt-5.4_20260315_211432.json')); print(d['pal'])"` → `{'accuracy': 0.2333, 'n_correct': 28, 'n_total': 120, 'code_success_rate': 0.275}`——只有 overall。

**对照**：App Table overall (L1011) 确实 17.5%（mini）/23.3%（5.4）——**与 raw `0.1750` / `0.2333` 精确匹配**。所以 overall 是真的，per-network 是 raw 缺存储——可能在 details JSON 里，也可能重构时丢了。对应 Critical Blocker **C1**。

**修复**：重跑 bnlearn 输出 per-network 到 raw JSON，或从现有 `pal_openai_*_bn_*_details.jsonl` 里 group-by 还原 per-network。

### F3 Fig 3(b) 数据点 vs Fig 3(a) / App Table L978 overall 数字自洽

| 数据 | Fig 3(b) L527 | App Table L978 | raw file | 状态 |
|---|---|---|---|---|
| PAL GPT-5.4 BLInD overall | $2.50, 98.1% | 98.1% | `pal_openai_gpt-5.4_20260315_200846.json` `accuracy=0.9811` | MATCH ✓ |
| PAL GPT-4o-mini BLInD | $0.84, 26% | 26.4% | `pal_openai_gpt-4o-mini_20260313_161931.json` `accuracy=0.2644` | MATCH ✓ (图上 26% 和表里 26.4% 轻微 rounding 差) |
| PAL depth-10 (mini) | — | 2% | raw `depth 10: 2/100` | MATCH ✓ |
| PAL depth-10 (5.4) | — | 96% | raw `depth 10: 96/100` | MATCH ✓ |
| Direct GPT-5.4 BLInD | $3.60, 31% | — | `cost_analysis.md:42` 31.2% | MATCH ✓ |

Figure 3 和 App Table L968-978 的数字与 raw 一致。

### F4 Table 2 PCD Preference 六模型 vs raw 核对（Codex 未测但 Claude 核过）

| 论文声称 (L192-196) | raw 实际 | 文件 |
|---|---|---|
| GPT-4o-mini Parse 82% / Compute 28% | Parse=0.82 / Compute=0.275 | `pcd_openai_gpt-4o-mini_20260313_175446.json` |
| GPT-4o Parse 100% / Compute 30% | Parse=1.0 / Compute=0.295 | `pcd_openai_gpt-4o_20260313_191642.json` |
| GPT-5.4 Parse 100% / Compute 40% | Parse=1.0 / Compute=0.4 | `pcd_openai_gpt-5.4_20260313_215141.json` |
| Sonnet 4 Parse 100% / Compute 64% | Parse=1.0 / Compute=0.64 | `pcd_anthropic_claude-sonnet-4_20260313_211844.json` |
| Gemini 3.1 Parse 100% / Compute 69% | Parse=1.0 / Compute=0.685 | `pcd_google_gemini-3.1-pro-preview_20260313_221431.json` |
| Opus 4.6 Parse 100% / Compute 78% | Parse=1.0 / Compute=0.775 | `pcd_anthropic_claude-opus-4-6_20260313_220117.json` |

全部 MATCH（rounding_ok，ok 到整数位）。**但注意**：存在 Sonnet 4 早期重复运行 `pcd_anthropic_claude-sonnet-4_20260313_211356.json` Compute=0.675（67.5%），论文选用了 64.0%（20260313_211844 runs）——这是 **不同种子 / 不同天不同时刻重跑**，不是 cherry-pick 但用户应知晓该重复存在。

### F5 Duplicate label 检查

`grep -n "label{"` 全量扫描 → **无任何 duplicate label**（CLAUDE.md 里提到的 "L493 label 重复 bug" 已修）。

### F6 held-out NB/HMM Table 3 数字核对

| Table 3 cell | raw | 文件 |
|---|---|---|
| NB mini Direct 44% | 0.44 | `held_out_nb_openai_gpt-4o-mini_205problems_20260314_225603.json` `direct.accuracy=0.44` ✓ |
| NB 5.4 Direct 68.5% | 0.685 | `held_out_nb_openai_gpt-5.4_205problems_20260314_224533.json` `direct.accuracy=0.685` ✓ |
| NB Compile Free/Core 100/100 | 1.0/1.0 | 两份 NB raw `compile_free`/`compile_core_ops` 都 `accuracy=1.0, n=200/200` ✓ |
| NB mini Parse 3% / Compute 37% / Decide 100% | 0.03/0.37/1.0 | raw `pcd` 字段精确匹配 ✓ |
| NB 5.4 Parse 100% / Compute 64.5% / Decide 100% | 1.0/0.645/1.0 | 匹配 ✓ |
| HMM mini Direct 32% / Compute 27% / Decide 98% | 0.32/0.27/0.98 | `held_out_hmm_openai_gpt-4o-mini_*` ✓ |
| HMM 5.4 Direct 61% / Compute 53% / Decide 100% | 0.61/0.53/1.0 | `held_out_hmm_openai_gpt-5.4_*` ✓ |

Table 3 **数字层面全部 MATCH**；问题在 caption 的 "≥98%" 全称 scope（上面 M2）。

### F7 Depth-10 数字（Codex 确认 MATCH）

| 论文 | raw |
|---|---|
| L77/L261: GPT-5.4 11% | `pcd_openai_gpt-5.4_20260313_192813.json` depth 10 = 11/100 ✓ |
| L77: "3--11%" (三模型 range) | mini=3, 5.4=11, sonnet=9 → range [3, 11]；但 GPT-4o depth 10 = 5/100 **未纳入 range**（论文 Figure 2 只画三模型不画 4o），range 表述合理 |

---

## Claims 列表（核验快照）

| # | 位置 | 论文声称 | 匹配状态 | 备注 |
|---|---|---|---|---|
| 1 | L77 Abstract | "22--78% compute, 3--11% depth-10" | MATCH | raw 确认 |
| 2 | L77 Abstract | "95% parse and decide" | SCOPE_ISSUE | 仅对 Preference 成立，BN exact Parse 30-48% |
| 3 | L82 Abstract | "100% compute on all tested BN benchmarks up to 37 nodes" | MISSING_RAW | bnlearn DSL=100% 未在 raw 存储 (C1) |
| 4 | L83 Abstract | "14× lower cost" | INCONSISTENT | 与 App 60× 冲突 |
| 5 | L83 Abstract | "310× lower than PAL" | MATCH | arithmetic 自洽 |
| 6 | L84 Abstract | "100% on two held-out families" | MATCH | NB+HMM raw 确认 |
| 7 | L95 Intro | "89% wrong at depth-10" | MATCH | 100-11=89 from raw |
| 8 | L108 Intro | "Parse 82-100% on primary families" | MISMATCH | BN exact Parse 30-48% |
| 9 | L108 Intro | "Decide 100%" | MATCH | raw 确认 |
| 10 | L108 Intro | "Compute 22-78%" | MATCH | Preference range 27.5-77.5%，rounding ok |
| 11 | L117 Intro | "1,200+ instances zero compute errors" | MISSING_RAW | TextBandit 50 未在 tests/raw 中 (S4) |
| 12 | L119 Intro | "E2E 74% on preference" | MATCH | raw `e2e_accuracy=0.7432` ✓ |
| 13 | Table 2 L192-196 | 6 模型 Preference PCD 数字 | MATCH | 全部 rounding_ok |
| 14 | Fig 2 L223-250 | Compute-depth 3 模型曲线 | MATCH | 全部 Wilson CI 和点 match raw `compute_depth_stats` |
| 15 | L254 caption | "our DSL 100% at every depth" | SCOPE_ISSUE | 未加 "compute stage" scope (S1) |
| 16 | L260 | "67× price 9pp improvement" | MATCH（arithmetically） | 40-31=9 percentage points |
| 17 | L339 | "1,200 instances: Flight 250 + BLInD 900 + TextBandit 50" | MISSING_RAW | TextBandit 50 part not stored |
| 18 | Table 3 L553-571 | held-out NB+HMM 数字 | MATCH | raw 全部确认 |
| 19 | Table 3 caption L553 | "Parse ≥98%" | MISMATCH | mini NB Parse = 3% 违反 caption |
| 20 | L576 body | "Parse ≥99%" | MISMATCH | 同上 |
| 21 | L583 Anomalies | "mini NB 3% Parse" | MATCH | raw 一致 |
| 22 | L601 | "E2E 74.3% [70.9%,77.8%]" | MATCH | `e2e_accuracy=0.7432` + `e2e_ci_95=[0.70947,0.77849]` ✓ |
| 23 | L602 | "two parse failures" | MISMATCH | raw `parse_success_rate=0.9984` → 1 parse failure in 624 |
| 24 | L603 | "best prompt-based 58.3%" | MATCH (Appendix 确认 tool-calling 58%) |
| 25 | L615 | "23-strategy staircase: CoT ≤33%, tool 73%, direct 74.8%" | MATCH (CLAUDE.md Evidence 1 确认) |
| 26 | L623 | "DeLLMa 17-29% vs 29% baseline" | MATCH | `dellma_*.json` compile_free accuracy 0-29.4% |
| 27 | L631 | "PAL GPT-5.4 98.1% at 310× cost" | MATCH | `pal_5.4_BLInD.accuracy=0.9811` ✓ |
| 28 | L722 Conclusion | "14× / 310×" | INCONSISTENT | 与 Appendix 60× 冲突 |
| 29 | L990 App | "Both 5.4/mini 0% on bnlearn Compute\|GoldParse" | MATCH (paper 自己声称；raw 文件 `pcd` 字段缺对应 bnlearn PCD raw，仅 `compile_core_ops=0/120` 佐证) | 需额外 bnlearn PCD JSON 存证 |
| 30 | L1006-1011 App | Per-network PAL 数字 | MISSING_RAW | raw 只存 overall |
| 31 | L1100-1103 | Inductor 20×2 = 40/40 | MATCH | `inductor_reliability_*.json` 精确确认 |

---

## 关键修复建议（按优先级）

**Critical（投稿前必修）**:
1. **Table 3 caption L553 / body L576** 明确 "mini NB Parse=3% is an anomaly documented in §5.3, all other cells ≥98%"（或直接删 ≥98% 全称）
2. **成本数字统一**: 选 $0.001/60× 或 $0.008/14× 一套，不能两套并存（Abstract+Fig+Sec5.4 vs Appendix）
3. **L108 Intro** "Parse 82-100% on primary families" — 加 scope 限定为 Preference-only 或改报两套（Preference 82-100% exact + BN 30-48% exact / ≥96% fieldwise）
4. **bnlearn per-network raw 存储** — L442 / L1006-1011 的 mini/5.4 per-network PAL 和 DSL 100% 需要在 raw JSON 里存证（对应 CLAUDE.md Critical C1）

**Serious（scope/framing 加限定即可）**:
5. **所有 100% 声明加 scope 限定**："on compute stage, conditional on correct parsing"（CLAUDE.md 2026-04-23 P0 改动，已列入 TODO）
6. **L339 1,200 instances 里的 TextBandit 50** — 要么补 raw，要么改报 1,150
7. **L602 "two parse failures"** — 核对 624 中实际是 1 还是 2 parse fail（raw 是 1）

**Minor**:
8. L260 "67× price 9pp" arithmetic 自洽，保留
9. L339 max error 10⁻¹² 断言——raw `tests/test_equivalence_full.py` 运行 log 是否保存？

---

## Raw Codex output

<details>
<summary>Codex MCP (gpt-5.4 xhigh, 80s budget) — 2026-04-23 21:38</summary>

```
1. MISSING_RAW | Across all 6 bnlearn_*.json files, none records "our DSL = 100%" for GPT-4o-mini on all 4 networks. The only mini file with compile fields has compile_core_ops=0/120 and compile_free=0/120; the other two mini files are PAL-only.

2. INCONSISTENT | Main text/Fig. 3 use $0.008 vs $0.11 and call it 14x; that arithmetic is fine (0.11/14≈0.0079) and $2.50/$0.008≈312x≈310x. But Appendix L1135/L1147 uses $0.001 vs $0.06, which implies 60x, not 14x.

3. INCONSISTENT | held_out_nb_openai_gpt-4o-mini_205problems_20260314_225603.json has pcd.parse_accuracy=0.03 and decide_accuracy=1.0. That matches the 3% table cell and contradicts the caption/body claim that Parse remains >=98%.

4. MISMATCH | The BN PCD raw files do not support "Parse accuracy is 82–100%": pcd_openai_gpt-4o-mini... has parse_accuracy=33.9%, pcd_openai_gpt-5.4... has 30.7%, and the saved Sonnet BN PCD file has 30.6%.

5. MATCH | Depth-10 BN compute is mini 3/100, GPT-5.4 11/100, and Sonnet 9/100. The paper's "3–11% on depth-10 networks" matches these raw PCD files.

6. MATCH | pal_openai_gpt-4o-mini_20260313_161931.json has bn.accuracy=0.264444... (238/900), i.e. 26.4%, matching the plotted 26% point. The $0.84 cost is not stored in that JSON.

7. MISSING_RAW | The saved bnlearn JSONs store only overall PAL accuracy plus network names/counts; they do not contain per-network Asia/Child/Insurance/Alarm PAL breakdowns for 4o-mini or GPT-5.4. The appendix has detail not present in raw JSON.

8. MATCH | e2e_openai_gpt-4o-mini_20260325_101317.json has e2e_accuracy=0.743178... and e2e_ci_95=[0.70947, 0.77849], which rounds to 74.3% [70.9%, 77.8%].

9. MISSING_RAW | No file under baselines/results/ confirms the exact 1,200 = Flight 250 + BLInD 900 + TextBandit 50 claim. tests/test_equivalence_full.py only encodes BLInD 900 and the first 50 Flight samples (250 round comparisons), with no TextBandit block.

10. MATCH | pcd_openai_gpt-5.4_20260313_192813.json has bn.compute_depth_stats["10"] = {total:100, correct:11}, i.e. 11%, matching L261/L95.
```

</details>

## Suspicions to carry forward（如需下一轮 re-audit）

- **TextBandit 50 equivalence claim (L339)**: `test_equivalence_full.py` 不包含 TextBandit block，"1,200" 实际只能证 1,150；要么补 test 要么改文
- **"89% wrong at depth-10" L95**: `nafar2025blind` 引用——论文引的 99% Parse 数字是来自 BLInD 论文还是我们自己 PCD？值得核 bib+原文
- **L624 "compile-time solvers score 17-29% on DeLLMa"**: `dellma_*.json` 显示 compile_free `accuracy=29.4%` (5.4) 和 `0%` (mini)，`compile_openai_gpt-4o-mini=0 (failed)` — 论文 17-29% 的 17% 端点从哪来？值得核
- **L990 "Both 5.4/mini 0% on bnlearn Compute\|GoldParse"**: raw 里没单独的 bnlearn PCD JSON，该声明用什么 raw 数据支撑？
- **L702 "6/6 LOO first attempt"**: raw `baselines/results/` 里只有 NB+HMM 两个 held_out 文件（4 份，mini+5.4 × NB+HMM），**Hotel/Flight-2F/3F/5F/6F/BLInD-OOD 的 LOO raw 完全缺失**——全部声称通过但无 raw 证据
