# Abstract Claim Audit Report

**Date**: 2026-05-04  
**Scope**: `paper/main.tex` abstract only, lines 76--87  
**Method**: `paper-claim-audit` style paper-to-evidence check against raw JSON/CSV-backed results and executable equivalence tests. The fresh `mcp__codex__codex` reviewer tool was not available in this Codex thread, so this is an executor-run abstract-only audit rather than a zero-context cross-model audit.

## Overall Verdict: PASS

The abstract numbers are evidence-matched. I found no inflated percentage or arithmetic error. The previous wording-scope warning has been resolved by replacing the base-split direct numbers with a paired five-seed structured direct-compute baseline on the same adversarial NB/HMM task sets.

## Claims Verified

| # | Location | Abstract Claim | Evidence | Status |
|---|---|---|---|---|
| 1 | L78 | "Across six LLMs... Compute accuracy ranges from 28% to 78% on preference learning" | PCD preference raw files: GPT-4o-mini 55/200 = 27.5%, GPT-4o 59/200 = 29.5%, GPT-5.4 80/200 = 40.0%, Claude Sonnet 128/200 = 64.0% (or 135/200 = 67.5% in the earlier same-day run), Gemini 137/200 = 68.5%, Claude Opus 155/200 = 77.5%. Rounded range is 28%--78%. | rounding_ok |
| 2 | L78 | "falls to 3--11% on depth-10 Bayesian networks" | BLInD depth-10 compute from detail JSON: GPT-4o-mini 3/100 = 3%, GPT-4o 5/100 = 5%, GPT-5.4 11/100 = 11%, Claude Sonnet 9/100 = 9%. | exact_match |
| 3 | L83 | "evaluate VSI across preference learning, bandits, Bayesian networks, Naive Bayes, and HMM forward filtering" | Evidence exists across the paper/results: Flight/Hotel preference E2E, TextBandit E2E, BLInD/bnlearn Bayesian networks, NB/HMM adversarial E2E. | exact_match |
| 4 | L84 | "match references on 1,150 Flight/BLInD instances" | Re-ran `uv run python3 tests/test_equivalence_full.py`: BLInD 900/900 and Flight 250/250, total 1,150/1,150. | exact_match |
| 5 | L84 | "400 finite-query bnlearn checks" | `baselines/results/bnlearn_dsl_100q_seed2026_20260502.json`: `_overall.correct=400`, `_overall.total=400`, four networks x 100 finite queries. | exact_match |
| 6 | L84 | "on larger multi-valued bnlearn networks, the compiled solver remains exact while per-instance PAL frequently fails" | Compiled solver: 400/400 finite queries in `bnlearn_dsl_100q_seed2026_20260502.json`. PAL stress: `bnlearn_openai_gpt-5.4_20260315_211432.json` gives 28/120 = 23.3% overall; `bnlearn_openai_gpt-5.4_20260315_204433.json` gives 29/120 = 24.2%. | exact_match |
| 7 | L85 | "external QUITE... registered VSI path reaches 96.0%" | `baselines/results/quite_registered_hard_compute_expanded_75_openai_gpt-4o-mini_20260503_213142.json`: 72/75 within 0.05 = 96.0%, MAE 0.00589. | exact_match |
| 8 | L85 | "direct answering reaches 36.0%--60.0%" | QUITE direct raw: GPT-4o-mini `quite_direct_numeric_hard_compute_expanded_75_openai_gpt-4o-mini_20260503_213252.json` gives 27/75 = 36.0%; GPT-5.4 `quite_direct_numeric_hard_compute_expanded_75_openai_gpt-5.4_20260503_213312.json` gives 45/75 = 60.0%. | exact_match |
| 9 | L85 | "per-instance PAL reaches 24.0%--88.0%" | QUITE PAL raw: GPT-4o-mini `quite_registered_pal_hard_compute_expanded_75_openai_gpt-4o-mini_20260503_213758.json` gives 18/75 = 24.0%; GPT-5.4 `quite_registered_pal_hard_compute_expanded_75_openai_gpt-5.4_20260503_213922.json` gives 66/75 = 88.0%. | exact_match |
| 10 | L85 | "at substantially higher cost" | QUITE raw `_meta.total_cost_usd`: VSI $0.00827; direct GPT-4o-mini $0.04765; direct GPT-5.4 $0.23531; PAL GPT-4o-mini $0.11512; PAL GPT-5.4 $2.48970. | exact_match |
| 11 | L86 | "a paired direct-compute baseline reaches only 18.2% / 32.4%" | Five-seed paired raw summary: `baselines/results/adversarial_direct_multiseed_summary_20260503_225039.json`: NB 109/600 = 18.17%; HMM 162/500 = 32.4%. | rounding_ok |
| 12 | L86 | "to 90.8% / 97.6% on adversarial Naive Bayes and HMM tasks across five independently generated task sets" | `adversarial_nl_e2e_multiseed_summary_20260503_183611.json`: NB pooled 545/600 = 90.833%; HMM pooled 488/500 = 97.6%; `n_artifacts=5`. | rounding_ok |

## Issues / Suggested Fix

No remaining abstract-number issue found in this audit scope.

## Commands Run

```bash
uv run python3 tests/test_equivalence_full.py
uv run python3 baselines/run_structured_direct_baseline.py --model openai/gpt-4o-mini --n-nb 120 --n-hmm 100 --n-blind 0 --sema 20  # repeated for five paired seed sets
```

Output:

```text
BLInD 等价性: 900/900 (100.0%)
Flight 等价性: 250/250 (100.0%)
全部通过!
```
