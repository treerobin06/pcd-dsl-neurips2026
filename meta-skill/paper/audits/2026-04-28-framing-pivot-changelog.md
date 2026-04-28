# 2026-04-28 Framing Pivot — Changelog (累积式)

> **Pivot**: 3-Gate Verifier → 2-Gate；BN-method → Family-agnostic typed backend；新增 self-evolving library vision。
> **决策依据**: Codex review 持续 4/10 + Tree 三轮讨论。详见 [[project_neurips_paper_framing_pivot]] memory + [[2026-04-23-codex-review]] + [[2026-04-28-next-session-plan]].
> **使命**: 每次改完代码 / 跑完实验 / 出新数据，**回到本文档 append 改动 + 填数字 + 改 ✅**——后续改 main.tex 时按本文档逐项落实。

---

## 0. 4 根 Pillar 总纲

| 维度 | 旧 framing | 新 framing |
|---|---|---|
| 1 PCD 诊断 | 保留不动 | 保留不动 |
| 2 Backend | "Verified BN solver / inference method" | **Family-agnostic typed factor algebra** (跨 BN / preference / bandit / HMM / 未来) |
| 3 库演化 | (无) | **Self-evolving library** (Family + Op 双层累积) |
| 4 Verifier | 3-Gate (Code Sanity + GT + Reference Match) | **2-Gate Deployable** (Code Sanity + Ground Truth) |

**关键决策（不可违反）**:
- pgmpy **不进 paper**（避免"为什么不用 pgmpy"攻击面）。BN 数值正确性 evidence 用 BLInD 自带 GT (900 题, max_err < 1e-10)
- self-evolving 在 paper 里诚实标 "future work / architecture supports"，不可 overclaim

---

## 1. 已完成代码改动 ✅

### 1.1 删 Gate 3 + 简化 callers (2026-04-28)

| 文件 | 改动 | 状态 |
|---|---|---|
| `verifier/gates.py` | Module docstring 改 2-Gate (line 1-19) | ✅ |
| `verifier/gates.py` | `verify_taskspec` 删 `gold_solver` 参数 (line 51-83) | ✅ |
| `verifier/gates.py` | 删除 `_gate3_reference_match` 整个函数 (line 262-327) | ✅ |
| `inductor/refiner.py` | `induce_and_verify` 删 `gold_solver` 参数 + docstring | ✅ |
| `inductor/refiner.py` | 内部 `verify_taskspec` 调用删 `gold_solver` 参数 | ✅ |
| `tests/test_loo_induction.py` | 删 `gold = PreferenceSolver(...)` / `gold = BNReferenceSolver()` | ✅ |
| `tests/test_loo_induction.py` | `induce_and_verify(...)` 删 `gold_solver=gold` (preference + BLInD) | ✅ |
| `tests/test_gate3_ablation.py` | **整个文件删除** | ✅ |

**Sanity check** (2026-04-28 删 Gate 3 后):
- ✅ `tests/test_dsl.py` — 25/25 pass (7.8s)
- ⚠️ `tests/test_compiler.py` — 12/13 pass，**`test_roundtrip` fail 是 C3 (2026-04-24) 重构 schema 副作用**（preference family 序列化 dump 了不该有的 `bn_inference_method` 等 BN-only 字段）。**与本次 Gate 3 删除无关**——pre-existing bug。已加入 Open Questions 5.x 待修

---

## 2. 待做代码改动

- ✅ ~~`dsl/macros_library.py` self-evolving registry stub~~ — **VISION SKETCH (Option 2: Python module per file)**
  - 2026-04-28 Tree 决策演化：
    - 初版："自进化只是愿景，不需要真实现代码，只在架构图里提一嘴"
    - 加深："如果简单+快+出效果可以加，参考 Claude skill-creator 架构"
    - 终版：选 Option 2 (Python module per macro)，不是 JSON manifest
  - 实际产物：
    - `dsl/macros/` 目录 + `__init__.py`（package）
    - 3 个 builtin macro manifests as Python modules:
      - `softmax_pref_likelihood.py` (hypothesis_enumeration, ops=3)
      - `beta_bernoulli_update.py` (conjugate_update, ops=2)
      - `ve_query.py` (variable_elimination, ops=4)
    - `dsl/macros_library.py` 用 importlib 扫描 dsl/macros/*.py 加载 METADATA + fn
    - `register_macro_file()` 接口生成新 .py 模板（vision use case）
    - `dsl/macros/README.md` 详细说明加 macro 流程
  - **故意不连主流程**: dsl/__init__.py 不导出 macros_library，inductor/compiler/verifier 不依赖
  - 用途：paper Figure 1 + Discussion 引用作为 architecture sketch（"file-based, drop-in extensible Python module per file"）
  - Sanity ✓: python3 -m dsl.macros_library scan 出 3 manifests, fn callable 有效, 主 namespace 不污染
- [ ] **Task 3 (next-session)**: `tests/test_bn_pgmpy_equivalence.py` — internal sanity test
  - 4 networks (asia/child/insurance/alarm) × 100 query
  - `import _pgmpy_compat` 走 monkey-patch
  - DSL `ve_query` vs pgmpy `VariableElimination`，max_err < 1e-10
  - **不进 paper / 不进 references.bib**
- [ ] **Task 4**: NB/HMM 真用 7 core ops 组合（保留自 next-session-plan Task 2）
  - `solvers/nb_solver.py` + `solvers/hmm_solver.py` 真用 dsl/core_ops
  - 修 `taskspec/compiler.py` + `taskspec/schema.py` 加 family
  - 修 `inductor/prompts/induction_prompt.md` 加 family 描述
- [ ] **Task 5**: Mixed E2E benchmark（保留自 next-session-plan Task 5）

---

## 3. 待跑实验 + 数据待落地

每跑完一项，**回到本文档把状态改 ✅ + 填实际数字 + 标 raw JSON 路径**。

| 实验 | 目的 | 数据存放 | 状态 | 数字 |
|---|---|---|---|---|
| LOO 6 数据集（2-Gate） | 真实 first-pass rate（之前 vacuous 6/6） | `baselines/results/loo_2gate_*.json` | ⏳ 待跑 | — |
| BN pgmpy 等价（internal） | 内部 sanity check | `tests/test_bn_pgmpy_equivalence.py` stdout | ⏳ 待跑 | — |
| NB 真 op composition | 验证 contribution #3 | `baselines/results/nb_real_compose_*.json` | ⏳ 待跑 | — |
| HMM 真 op composition | 同上 | `baselines/results/hmm_real_compose_*.json` | ⏳ 待跑 | — |
| Mixed E2E (mini smoke 5) | pre-flight | `baselines/results/mixed_e2e_smoke_*.json` | ⏳ 待跑 | — |
| Mixed E2E (mini full 250) | 主结果 | `baselines/results/mixed_e2e_full_*.json` | ⏳ 待跑 | — |
| Mixed E2E (gpt-5.4 250) | 对照 | `baselines/results/mixed_e2e_54_*.json` | ⏳ 待跑 | — |

---

## 4. 论文待改清单（按 main.tex 行号）

> 每项改完打 ✅，附 commit hash 缩写。

### 4.1 Verifier framing: 3-Gate → 2-Gate ✅ (2026-04-28 push bfc8fcf)

- ✅ "three-gate verifier" 全文 5 处 replace_all → "two-gate verifier"
- ✅ L375 `\item Gate~3, Reference Match` item 删 + "If Gates 1--2 fail" → "If either gate fails"
- ✅ L284-288 verifier Eq2 删 G3 conjunct (`\;\wedge\; \underbrace{...}_{G_3...}`)
- ✅ L396 algorithm step `Gate3_Reference` 删
- ✅ L407 LOO claim "100% match to gold reference solvers" → "All 6 pass all verification gates" (删 100% gold match)
- ✅ L585-589 §"Ablation: Gate 3 is Not Required" **整段删**
- ✅ L760-770 Appendix `\section{DSL Equivalence and Gate 3 Ablation}` 改名 "DSL Equivalence" + Gate 3 Off 段改名 "LOO held-out validation" + 删 \label{app:gate3}
- ✅ L1110 LOO appendix `gold reference solver with 100% accuracy` 删
- ✅ L1117-1129 Table 删 "Gate 3" 列 (7→6 columns)
- 全文 grep "Gate 3 / gate3 / Reference Match / three-gate" → 无残留 ✓

### 4.2 pgmpy 引用从 paper 移除 ✅ (2026-04-28 push bfc8fcf)

- ✅ L339 "cross-checked against pgmpy~\citep{ankan2015pgmpy}" → "matched against BLInD dataset's ground-truth posteriors"
- ✅ L708 footnote 同上改写
- ✅ `references.bib` `ankan2015pgmpy` entry 保留（备用）
- 全文 grep "pgmpy / ankan2015" → 无残留 ✓

### 4.3 Family-agnostic typed backend framing — 已隐含在 L644/L652 (无需新加段)

- ✅ L644 "synthesis at the family level rather than per-instance"
- ✅ L652 "ProbLog targets BN inference only, while our DSL covers multiple inference families with the same seven typed primitives"
- ✅ L661 "Unlike general-purpose PPLs..., our DSL is intentionally narrow, covering discrete exact inference only"
- 已有段落已经清楚阐述 family-agnostic vs BN-specialized library 区别，**无需重写或新加 Section**

### 4.4 Self-evolving library — 1 句话嵌入 Discussion ✅ (2026-04-28 push bfc8fcf)

- ✅ L706 DSL Design and Verification 段加 1 句:
  > "The architecture is extensible: new families verified by the inductor--verifier loop can be persisted as reusable macros through a file-based registry (one Python module per macro under `dsl/macros/`), and new core operations with formal type signatures can extend the foundation; we leave full self-evolution---automatically growing the macro library across deployments---to future work."

### 4.5 Conclusion compositional gen scope qualifier ✅ (2026-04-28 push bfc8fcf)

- ✅ L725-726 改写: 加 "synthetic NB and HMM" scope + 加结尾"broader compositional generalization beyond these synthetic held-out tests remains an open question for future work"

### 4.4 Self-evolving library — 仅在架构图 + Discussion 提一嘴（不开 Section）

**Tree 2026-04-28 决策**: self-evolving 是 *vision / future work*，不需要真实现，
不开独立 Section，只在 Figure 1 + Discussion 一小段轻触：

- [ ] Figure 1 / Algorithm 1 架构图加 "→ persistent macro library" 箭头（family layer reuse 视觉化）
- [ ] Discussion 加 1 段（≤ 5 行）：
  > "The architecture supports a self-evolving macro library: new families verified
  > by the inductor-verifier loop can be persisted as reusable macros, and new core
  > ops with formal type signatures can extend the foundation. This evolution is left
  > to future work; see `dsl/macros_library.py` for the registry interface sketch."
- [ ] **不**写独立 Section / Subsection
- [ ] **不**跑 self-evolving experiment

### 4.5 Abstract / Intro / Conclusion 同步

- [ ] Abstract 改写：加 family-agnostic + self-evolving 两根支柱
- [ ] Intro Contribution list 同步 4-pillar
- [ ] Conclusion 收尾呼应 4-pillar
- [ ] 全文 grep "BN inference method" / "我们做了 BN solver" / "we propose a new BN solver" → 全部改写为 family-agnostic 角度

---

## 5. Open Questions（投稿前必须回答）

- [ ] Self-evolving section 在 paper 里放在哪 — Section 4.5 还是 §6 Discussion？倾向 Discussion 避免 overclaim
- [ ] BLInD GT 当 BN 数值 evidence 是否够强？是否需要补 1 个 hand-crafted "DSL VE vs analytical solution" example
- [ ] `references.bib` 移除哪些 BN-specialized library 引用（pgmpy/ProbLog/WebPPL/Pyro 引用策略统一）
- [ ] **C3 schema 副作用 bug**: `taskspec/schema.py` 给 BN family 加的 `bn_inference_method` / `bn_input_format` / `bn_numerical_precision` 字段在 preference / bandit family 序列化时也被 dump。修法：要么 to_json 按 family 过滤，要么 schema 改成 family-specific subclass。`tests/test_compiler.py::test_roundtrip` 当前 fail。优先级 P2（不影响主实验，但会让 reviewer 发现 schema 不干净）
