# Curated Results Manifest

This directory contains the result records used by the current paper. It is a
curated evidence package, not a full scratch-run dump.

## Main Natural-Language E2E

| Result group | Paper number | Files |
|---|---:|---|
| Flight E2E | 74.3% | `e2e_openai_gpt-4o-mini_20260325_101317.json`, `e2e_openai_gpt-4o-mini_20260325_101317_details.json` |
| Hotel E2E | 77.4% | `e2e_hotel_openai_gpt-4o-mini_20260502_213825.json`, `e2e_hotel_openai_gpt-4o-mini_20260502_213825_details.json` |
| TextBandit-style E2E | 96.0% | `textbandit_e2e_openai_gpt-4o-mini_20260502_213919.json` |
| Mixed E2E aggregate | 90.4% overall; 89.7% supported | `all_family_mixed_e2e_openai_gpt-4o-mini_20260502_221603.json`, `adversarial_nl_e2e_20260428_172402.json`, `router_metrics_20260503_102657.json` |

## Held-Out Naive Bayes / HMM

| Result group | Paper number | Files |
|---|---:|---|
| VSI adversarial NL E2E, five seeds | NB 90.8%; HMM 97.6% | `adversarial_nl_e2e_multiseed_summary_20260503_183611.json` plus the five `adversarial_nl_e2e_20260503_*.json` per-seed records |
| Paired structured direct baseline, five seeds | NB 18.2%; HMM 32.4% | `adversarial_direct_multiseed_summary_20260503_225039.json` plus the five `structured_direct_openai_gpt-4o-mini_20260503_*.json` per-seed records |
| Inductor reliability sanity | 96/100 final valid specs | `inductor_reliability_nb_hmm_openai_gpt-4o-mini_20260503_183835.json` |

## Backend, BLInD, bnlearn, and QUITE

| Result group | Paper number | Files |
|---|---:|---|
| bnlearn deterministic backend | 400/400 finite queries | `bnlearn_dsl_100q_seed2026_20260502.json` |
| bnlearn registry-supported NL sanity | 79/80 strict; 80/80 tie-aware | `bnlearn_registry_e2e_80q_gpt4omini_20260503.json` |
| bnlearn PAL/LLM stress | PAL collapses on larger networks | `bnlearn_openai_gpt-4o-mini_20260428_011143.json`, `bnlearn_openai_gpt-5.4_20260314_235817.json` |
| QUITE 75-query registered path | VSI 72/75 = 96.0% | `quite_registered_hard_compute_expanded_75_openai_gpt-4o-mini_20260503_213142.json` |
| QUITE direct baselines | 36.0% / 60.0% | `quite_direct_numeric_hard_compute_expanded_75_openai_gpt-4o-mini_20260503_213252.json`, `quite_direct_numeric_hard_compute_expanded_75_openai_gpt-5.4_20260503_213312.json` |
| QUITE PAL baselines | 24.0% / 88.0% | `quite_registered_pal_hard_compute_expanded_75_openai_gpt-4o-mini_20260503_213758.json`, `quite_registered_pal_hard_compute_expanded_75_openai_gpt-5.4_20260503_213922.json` |
| QUITE full-corpus direct context | 320/1154 = 27.7% | `quite_direct_numeric-wep_openai_gpt-4o-mini_20260503_184206.json` |

## PCD and Cost Evidence

| Result group | Files |
|---|---|
| Preference PCD across six models | `pcd_*_preference_*.json` and matching summaries listed in this directory |
| BLInD depth PCD across four models | `pcd_*_bn_*.json` and matching summaries listed in this directory |
| Compile-time code-generation baselines | `compile_time_*_20260313_*.json` and matching details |
| PAL baselines | `pal_openai_gpt-4o-mini_20260313_162719.json`, `pal_openai_gpt-5.4_20260315_200846.json` |
| Cost and external summaries | `cost_analysis.md`, `quite_external_expansion_summary_20260503.md`, `quite_registered_hard_compute_clean_summary_20260503.md`, `reviewer_gap_experiment_manifest_20260503.md` |

## Explicitly Excluded

The working repository also contains older or exploratory mixed-stream sanity
checks, QUITE scaffold runs, and declarative-route smoke tests. Those are not
reported in the paper and are intentionally absent from this release.
