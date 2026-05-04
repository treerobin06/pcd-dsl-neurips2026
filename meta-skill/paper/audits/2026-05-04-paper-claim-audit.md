# Paper Claim Audit - 2026-05-04
Auditor: Codex (zero-context, GPT-5.5)
Paper: meta-skill/paper/main.tex
Submit deadline: May 6 (NeurIPS 2026)

## Verdicts (#1-#12)

| # | Claim | Verdict | Raw source | Notes |
|---|---|---|---|---|
| 1 | Mixed 90.4/89.7 | MATCH | `baselines/results/all_family_mixed_e2e_openai_gpt-4o-mini_20260502_221603.json` + `baselines/results/adversarial_nl_e2e_multiseed_summary_20260503_183611.json` | Mixed raw has 548/600 supported, 598/650 overall. Replacing its NB/HMM 200/200 with one hard split 110/120 + 98/100 gives 556/620 supported = 89.7% and 606/670 overall = 90.4%. Wilson CIs recompute to [87.0,91.8] and [88.0,92.4]. |
| 2 | NB/HMM adversarial NL E2E pooled 90.8/97.6 | MATCH | `baselines/results/adversarial_nl_e2e_multiseed_summary_20260503_183611.json` | Pooled NB 545/600 = 90.8%; pooled HMM 488/500 = 97.6%. |
| 3 | NB/HMM direct baseline 44/32 | MATCH | `baselines/results/held_out_nb_openai_gpt-4o-mini_205problems_20260314_225603.json`; `baselines/results/held_out_hmm_openai_gpt-4o-mini_105problems_20260314_214139.json` | Direct baseline matches 88/200 = 44.0% and 32/100 = 32.0%. User-suggested `structured_direct_*102910.json` is a different structured-output direct baseline and matches the paper's 23.3/40.0 row, not this row. |
| 4 | bnlearn DSL backend 400/400 [99.0,100.0] | MATCH | `baselines/results/bnlearn_dsl_100q_seed2026_20260502.json` | `_overall.correct=400`, `_overall.total=400`; Wilson 95% CI = [99.0488,100.0], rounds to [99.0,100.0]. |
| 5 | bnlearn registry NL E2E 79/80, tie-aware 80/80 | MATCH | `baselines/results/bnlearn_registry_e2e_80q_gpt4omini_20260503.json` | Summary 79/80 = 98.8%, CI [93.3,99.8]. The sole strict failure is Child query `HypDistrib` with posterior Equal=0.5, Unequal=0.5; tie-aware summary is 80/80. |
| 6 | bnlearn PAL stress-test 17.5/23.3 and both 0% on Alarm | UNVERIFIED | `baselines/results/bnlearn_openai_gpt-4o-mini_20260315_211540.json`; `baselines/results/bnlearn_openai_gpt-5.4_20260315_211432.json` | Overall PAL 21/120 = 17.5% and 28/120 = 23.3% match. However these raw JSON files only contain overall PAL totals and `n_test_*`; they do not contain per-network correct counts, so Alarm=0%, Asia=90%, Child=0%, Insurance=3% cannot be verified from raw. |
| 7 | QUITE registered VSI 72/75 and baselines | MATCH | `baselines/results/quite_registered_hard_compute_expanded_75_openai_gpt-4o-mini_20260503_213142.json`; `quite_direct_numeric_hard_compute_expanded_75_*`; `quite_registered_pal_hard_compute_expanded_75_*` | VSI 72/75 = 96.0%, RMSE/MAE field reported as `mae=0.005890...`, time 16.9s, cost $0.0083. Direct 4o-mini 27/75 = 36.0%; direct 5.4 45/75 = 60.0%; PAL 4o-mini 18/75 = 24.0%; PAL 5.4 66/75 = 88.0%. |
| 8 | Flight E2E 624, 74.3, oracle 74.4, solver 99.8 | MATCH | `baselines/results/e2e_openai_gpt-4o-mini_20260325_101317.json` | `n_samples=624`, `e2e_accuracy=0.743178`, raw `e2e_ci_95=[0.70947,0.77849]`, `gold_pipeline_accuracy=0.743590`, `gold_solver_match=0.998395`. |
| 9 | Hotel E2E 124, 77.4, oracle 75.0, cost 0.0556 | MATCH | `baselines/results/e2e_hotel_openai_gpt-4o-mini_20260502_213825.json` | `n_samples=124`, `e2e_accuracy=0.774194`, raw `e2e_ci_95=[0.70161,0.85484]`, `gold_pipeline_accuracy=0.75`, cost `total_cost_usd=0.05555055`. |
| 10 | TextBandit-style E2E 100, 96.0, cost 0.0292, time 45.3, failures observation-count | MATCH | `baselines/results/textbandit_e2e_openai_gpt-4o-mini_20260502_213919.json` | `e2e_correct=96`, `n_samples=100`, Wilson [90.2,98.4], cost `0.0291597`, elapsed `45.2509`, `failure_modes={'observation_count': 4}`. |
| 11 | Cost claims $0.008, PAL 310x, GPT-5.4 compile-time 14x | UNVERIFIED | `baselines/results/cost_analysis.md`; `compile_time_openai_gpt-5.4_20260313_193122.json`; `pal_openai_gpt-5.4_20260315_200846.json` | The paper's $0.008/$0.11/$2.50 values and 14x/310x ratios are not present as raw token/cost fields in the BLInD compile-time or PAL JSON. `cost_analysis.md` is an older derived estimate and says ~$0.001 and 60x, not the paper values. Ratio arithmetic is internally consistent if the paper values are assumed, but raw provenance is missing. |
| 12 | NB/HMM pooled CI consistency | MATCH | `baselines/results/adversarial_nl_e2e_multiseed_summary_20260503_183611.json` | Wilson 95% for 545/600 is [88.257,92.890] -> [88.3,92.9]. Wilson 95% for 488/500 is [95.852,98.622] -> [95.9,98.6]. |

## MISMATCH details (each one needs a fix)

None among the 12 audited items.

## UNVERIFIED items (raw not found / blocker)

- #6 bnlearn PAL per-network breakdown:
  - Paper lines: `paper/main.tex:374`, `paper/main.tex:541`, `paper/main.tex:1024`, `paper/main.tex:1040-1045`.
  - Search attempted: `ls baselines/results | grep -Ei 'pal|bnlearn|bn_'`.
  - Files found: `bnlearn_openai_gpt-4o-mini_20260315_211540.json` and `bnlearn_openai_gpt-5.4_20260315_211432.json`.
  - Blocker: these files verify only overall PAL totals, not per-network percentages or Alarm=0%.

- #11 BLInD cost claims:
  - Paper lines: `paper/main.tex:439`, `paper/main.tex:442`, `paper/main.tex:448`, `paper/main.tex:541`, `paper/main.tex:1147`, `paper/main.tex:1159-1162`, `paper/main.tex:1170`.
  - Search attempted: `rg -n "\\$0\\.008|0\\.008|310|14\\\\times|14x|0\\.11|\\$2\\.50|2\\.50|total_cost_usd" baselines/results paper/main.tex`.
  - Files checked: `baselines/results/cost_analysis.md`, `baselines/results/compile_time_openai_gpt-5.4_20260313_193122.json`, `baselines/results/pal_openai_gpt-5.4_20260315_200846.json`.
  - Blocker: compile-time and PAL JSON files contain accuracy/repair stats but no token/cost metadata. The only cost analysis file uses older `$0.001` / `60x` values, so it cannot verify the paper's `$0.008` / `14x` / `310x` claim.

## Suspicions to carry forward

- Re-run a focused grep before submission: `rg -n "0\\.008|0\\.11|2\\.50|310|14\\\\times|60\\\\times|0\\.001" paper/main.tex baselines/results/cost_analysis.md baselines/results/*.json`.
- Add or locate raw cost metadata for the BLInD cost curve. Current compile-time/PAL JSONs do not record `prompt_tokens`, `completion_tokens`, or `total_cost_usd`.
- Add or locate bnlearn PAL per-network details. Current bnlearn PAL JSONs do not support the table cells `Asia 90%`, `Child 0%`, `Insurance 3%`, `Alarm 0%`.
- Clarify the mixed aggregate provenance in paper or artifact notes: the 90.4/89.7 aggregate uses a single hard split 110/120 + 98/100, not the 5-seed pooled NB/HMM numbers.
- Spot-check after cite-only edits: `rg -n "Direct answer|Structured JSON direct|Mixed supported stream|QUITE|bnlearn" paper/main.tex` and verify the table captions still describe the exact source files.

## Verdict

NEEDS-FIX-MINOR
