# Figure/Table and Experiment Plan, 2026-05-03

## Current Diagnosis

The paper currently has 18 `table` environments, 1 `captionof{table}`, 4
`figure*` environments, and 1 `captionof{figure}`. The main story is strong but
the visual system is still too table-heavy and partially redundant:

- Main text already has a good overview figure, but it lacks a method zoom-in
  that shows how VSI turns a few examples into a TaskSpec, typed operations, and
  a reusable solver.
- Several main-text tables and figures repeat the same E2E numbers:
  held-out NB/HMM table, single-family E2E table, mixed E2E table, and the E2E
  composition figure.
- Appendix tables are useful for reproducibility, but many can be consolidated:
  artifact provenance, cost accounting, inductor reliability, LOO checks,
  PAL-depth detail, and bnlearn detail currently feel like separate fragments.
- Cost/time evidence is under-used. The new QUITE hard-compute split is
  especially valuable because it gives accuracy, wall-clock time, and API cost
  under the same query plan.

## Table vs Figure Rule for This Paper

Use figures for patterns reviewers should understand in 5 seconds:

- PCD bottleneck: Parse/Decide high, Compute low.
- Scaling failure: compute/codegen degrades with depth/network size.
- Cost/time Pareto: compile-once pays once; PAL/direct pay per query.
- End-to-end coverage: many families, realistic non-100 accuracies.

Use tables for exact claims and auditability:

- Accuracy with `n`, CI, and metric definitions.
- Multi-column comparisons where time, cost, tokens, and artifacts matter.
- Reproducibility manifests and prompt/schema details.
- Negative/boundary cases where nuance matters.

Do not convert everything to bar charts. For NeurIPS, a clean mix works best:
2--3 high-signal figures in the main text, 2--3 compact main tables, and detailed
appendix tables.

## Recommended Main-Text Visual Plan

### Figure 1: Overview Architecture

Keep current `figure1_overview.png`, but caption should explicitly say
`VSI` and `LLM-assembled solver specification`.

Purpose:
- First-viewport mental model.
- Shows router, induction, validation, registry, and reuse.

### Figure 2: VSI Method Zoom-In

Add a new method figure in Section 4, after the TaskSpec paragraph.

Suggested panels:

1. Few family examples.
2. LLM inductor assembles a TaskSpec.
3. TaskSpec snippet with `inference_family`, `state_structure`,
   `observation_model`, and `decision_rule`.
4. Compiler lowers to typed atoms:
   `condition -> multiply -> marginalize -> normalize -> expectation/argmax`.
5. Deploy checks and registry reuse.

Why this matters:
- It directly answers the "is this just a hand-written solver?" concern.
- It makes the LLM contribution visible without overclaiming raw Python codegen.
- It complements Figure 1: Figure 1 is system architecture; Figure 2 is the
  induction/compilation mechanism.

Best implementation:
- Use deterministic vector/TikZ or carefully edited generated bitmap.
- Avoid putting long text in image-generation output. Use short labels and let
  the caption explain.

### Figure 3: PCD Bottleneck and Scaling

Merge the current PCD preference table + BN-depth plot into one two-panel figure:

- Panel A: PCD heatmap or grouped bars for Parse / Compute / Decide across 6
  models on Flight.
- Panel B: Compute accuracy vs BN depth, already present.

Move the exact six-model PCD table to appendix.

Why:
- The point is the pattern, not every cell.
- Reviewers will remember "Compute is the only failing stage" faster from a
  figure than from a table.

### Figure 4: Compute-Hard External Robustness and Cost/Time

Replace or expand current scaling/cost figure with a three-panel evidence figure:

- Panel A: bnlearn network-size stress, current bar chart.
- Panel B: BLInD cost--accuracy Pareto, current scatter.
- Panel C: QUITE hard-compute clean, showing accuracy plus cost/time.

For QUITE, use either:

- grouped bars for accuracy by method/model, with a small callout showing time
  and cost; or
- a scatter plot: x = cost or time (log), y = accuracy, marker = method/model.

This is one of the best new pieces of evidence because PAL 5.4 is reasonably
strong but much more expensive, while VSI is exact and cheap on the same split.

### Figure 5 or Table 2: E2E Coverage

Do not keep both a large E2E table and a redundant E2E bar chart in the main
text. Choose one:

Preferred:
- One compact main table: family, setting, n, direct/baseline, VSI, note.
- Optional small horizontal bar figure only if page space allows.

The table is better here because `n`, CI, family role, and diagnostic notes
matter. A bar chart alone hides the important caveats.

## Recommended Main Tables

### Main Table A: Held-Out / E2E Coverage

Merge current `tab:held_out`, `tab:single_family_e2e`, and
`tab:all_family_mixed` into one "E2E coverage" table.

Columns:

| Family / stream | Setting | n | Baseline | VSI | Note |

Rows:
- Flight
- Hotel
- TextBandit-style
- Naive Bayes adversarial
- HMM adversarial
- Mixed supported aggregate
- Overall including unsupported rejection

Keep BLInD/bnlearn backend out of this table; those are compute/backend stress,
not natural-language E2E.

### Main Table B: External Compute-Hard Comparison

Add QUITE as the external comparison table, either main or appendix depending on
space. If main text has room, this is worth a compact table:

| Method | Model | Acc. | Time | Cost |

Rows:
- VSI GPT-4o-mini: 25/25, 5.3s, $0.0026
- Direct GPT-4o-mini: 8/25, 7.4s, $0.0271
- PAL GPT-4o-mini: 5/25, 140.4s, $0.0428
- Direct GPT-5.4: 14/25, 9.5s, $0.2129
- PAL GPT-5.4: 21/25, 129.6s, $0.8389

This table is unusually strong because it supports three claims at once:
accuracy, cost, and amortized reuse.

### Main Table C: Route / Task Family Map

Keep a small route table, but make it more contribution-oriented:

| Family | Solver assembly | Reuse status | Evidence |

This can replace the current `Inference families` appendix table and the route
table if tightened.

## Appendix Consolidation Plan

### Appendix A: Experimental Manifest

Merge:

- current Reproducibility Summary
- Cost Accounting
- QUITE hard-compute clean summary
- artifact paths

One table:

| Result | Artifact | Script | n | Model | Time | Cost | Tokens |

For old legacy runs where time/cost are not recorded, write `legacy/not recorded`
rather than estimating exact wall-clock time. Cost can be estimated only when
token metadata exists.

### Appendix B: Detailed PCD Tables

Move exact PCD preference and BN-depth tables here.

Main text keeps the figure; appendix keeps exact numbers.

### Appendix C: Reliability / LOO Checks

Merge three current tables:

- Inductor reliability Flight/BN
- Adversarial NB/HMM reliability
- LOO implementation check

One table with columns:

| Check | Families | Trials / datasets | First pass | Final | Notes |

This removes the "100% table pile-up" feeling.

### Appendix D: Schema and Prompts

Keep TaskSpec schema and prompt summary, but shorten captions and avoid making
them look like primary evidence. These are reproducibility details.

### Appendix E: Failure Analysis

Keep compile-time baseline failure analysis and PAL failure examples. This is
useful when reviewers ask why PAL is not enough.

## Cost/Time Data Policy

For new experiments:

- Always store `_meta.prompt_tokens`, `_meta.completion_tokens`,
  `_meta.total_cost_usd`, `elapsed_sec`, model id, query plan, and script.
- Always report wall-clock time and cost for direct/PAL/VSI comparisons when
  the same split is used.

For old experiments:

- If `_meta.total_cost_usd` exists, use it.
- If usage tokens exist but cost does not, compute an estimate and label it
  `estimated`.
- If elapsed time is missing, do not reconstruct it from timestamps. Mark it
  `not recorded`.
- If a key cost claim depends on a legacy run, rerun a focused smoke with the new
  artifact schema instead of inventing numbers.

## Dataset Experiment Plan

### Must Add

1. QUITE hard-compute clean row in appendix or main table.
   - Already done for n=25.
   - Strong enough to cite as smoke; can be expanded if space/time permits.

2. QUITE registered all-network VSI smoke.
   - Purpose: show this is not only five hand-picked networks.
   - Run GPT-4o-mini only first.
   - Use 1--3 finite queries per network.
   - Expected cost: <$0.05.

3. QUITE hard-compute expanded comparison.
   - Expand clean split from 25 to 50/75 if enough clean queries exist.
   - Run Direct 4o-mini, Direct 5.4, PAL 4o-mini.
   - Only run PAL 5.4 if PAL 4o-mini is weak or if we want the strongest
     baseline in the appendix.
   - Expected cost if including PAL 5.4 at 75 queries: roughly $2--3.

### Nice to Have

4. QUITE raw-premise compile sanity.
   - Risky and less clean because premise parsing becomes the bottleneck.
   - Use appendix only; do not let it muddy the main claim.

5. DeLLMa boundary table.
   - Keep as "out of scope / distribution estimation" boundary evidence.
   - Do not include in the main positive table.

### Do Not Adapt Now

6. LLM-BI.
   - Local material is code/PDF, not a benchmark-style dataset.
   - Use related work.

7. DisCIPL/self-steering.
   - Different target: text steering/control, not exact probabilistic posterior
     inference.
   - Use related work only.

## Execution Order

1. Make a figure/table inventory PR patch:
   - Add QUITE row to appendix manifest.
   - Add cost/time table or figure.
   - Consolidate reliability/LOO tables.

2. Run QUITE all-network VSI smoke.
   - Stop if parser/problog semantics produce many non-compute failures.

3. Run QUITE expanded hard-compute comparison.
   - Start with Direct 4o-mini / 5.4 and PAL 4o-mini.
   - Decide whether PAL 5.4 expansion is needed after seeing PAL 4o-mini.

4. Build VSI method zoom-in figure.
   - Draft deterministic vector version first.
   - Optionally generate an illustrative bitmap, but keep text labels short and
     manually check every word.

5. Rewrite main Experiments section around the new visual order:
   - Diagnostic bottleneck.
   - Compile-once solver vs per-instance codegen.
   - Untemplated and natural-language E2E.
   - External QUITE cost/time evidence.

6. Final appendix cleanup:
   - Tables grouped by purpose.
   - No raw artifact path table in the main text.
   - Every numeric claim either points to a raw artifact or is clearly marked
     as legacy/estimated.
