# Compile Once, Reason Exactly — Paper-to-Evidence Audit

Audit scope: `paper/main.tex` plus raw files under `baselines/results/`, with `baselines/run_*.py` read only to understand metric computation and split definitions.

## SUMMARY

- Total quantitative claims extracted: 46
- `exact_match` / `rounding_ok`: 23
- `number_mismatch` / `config_mismatch` / `aggregation_mismatch`: 11
- `scope_overclaim` / needs scope limiter: 6
- `missing_evidence` / `ambiguous_mapping`: 6
- Overall verdict: `FAIL`

Why `FAIL`:

1. The paper repeatedly states BN Parse is high (`>=95%`, `82--100%`, `>=96%`) even though the saved BN `parse_accuracy` is only `30.6%` (GPT-5.4), `30.6%` (Sonnet 4), `33.9%` (GPT-4o-mini), and `48.3%` (GPT-4o).
2. Cost numbers are internally inconsistent: the main text/figure use `\$0.008`, `\$0.11`, `14x`, `310x`, while `cost_analysis.md` and Appendix cost table use `\$0.001`, `\$0.06`, `60x`, `2500x`.
3. The bnlearn section mixes incompatible claims: text says PAL drops to `0--3%` for both models and Direct Answer is `0%`, but the saved bnlearn summaries show PAL overall `17.5%` / `23.3%` and Direct overall `55.0%` / `60.8%`.
4. The E2E error analysis is wrong: the saved details show `1` JSON parse failure plus `1` successful parse that still disagrees with the gold solver; the paper says the whole `0.2%` gap is from `two` malformed-JSON parse failures.
5. Several appendix tables/claims have no corresponding raw result file in `baselines/results/` at all: LOO `6/6`, Gate-3-off ablation, equivalence on `1,200` instances, TextBandit numbers, and the full 23-strategy/content-channel appendix.

## CRITICAL ISSUES

1. **BN Parse headline is wrong under the paper’s own metric definition.**
   - Paper: lines 108, 130, 176 say Parse is `82--100%`, `>=95%`, or `>=96%`.
   - Definition: line 169 says BN Parse is correct only when **all** fields match.
   - Raw evidence:
     - `baselines/results/pcd_openai_gpt-5.4_20260313_192813.json:bn.parse_accuracy = 0.30666666666666664`
     - `baselines/results/pcd_openai_gpt-4o-mini_20260313_182537.json:bn.parse_accuracy = 0.3388888888888889`
     - `baselines/results/pcd_openai_gpt-4o_20260313_193258.json:bn.parse_accuracy = 0.48333333333333334`
     - `baselines/results/pcd_anthropic_claude-sonnet-4_20260313_213010.json:bn.parse_accuracy = 0.3055555555555556`
   - Why wrong: the paper is presenting exact BN Parse as near-perfect, but the saved raw exact-match metric is roughly `31--48%`, not `>=95%`.
   - Suggested fix: either change the prose to “some BN subfields (variables/edges/CPTs) are high, but exact Parse is much lower” or change the formal metric/terminology everywhere.

2. **Held-out caption/text directly contradict the held-out table.**
   - Paper: line 553 caption says “Parse and Decide remain `>=98%`”; line 576 says “Parse `>=99%` and Decide `>=98%`”.
   - Raw evidence:
     - `baselines/results/held_out_nb_openai_gpt-4o-mini_205problems_20260314_225603.json:pcd.parse_accuracy = 0.03`
     - `baselines/results/held_out_nb_openai_gpt-4o-mini_205problems_20260314_225603.json:pcd.compute_accuracy = 0.37`
     - `baselines/results/held_out_hmm_openai_gpt-4o-mini_105problems_20260314_214139.json:pcd.parse_accuracy = 1.0`
   - Why wrong: NB mini Parse is `3.0%`, not `>=98%`; the table itself already shows `3.0%`.
   - Suggested fix: rewrite the caption/text to “Decide stays high (`98--100%`), while Parse varies sharply across held-out families (`3--100%`).”

3. **Cost numbers are inconsistent across the paper and unsupported by stored usage.**
   - Paper main claims: lines 83, 539, 592, 722 use `\$0.008`, `\$0.11`, `14x`, `310x`.
   - Raw evidence used in repo:
     - `baselines/results/cost_analysis.md:21` says DSL total cost is `~$0.001`
     - `baselines/results/cost_analysis.md:29` says GPT-5.4 compile-time total cost is `~$0.04-0.08`
     - `baselines/results/cost_analysis.md:47` says PAL GPT-4o-mini total cost is `$0.97`
     - `baselines/results/cost_analysis.md:41` says Direct GPT-5.4 total cost is `$3.60`
   - Appendix claim: lines 1147--1150 use `\$0.001`, `\$0.06`, `\$2.50`, `60x`, `2500x`.
   - Why wrong: the main text and Appendix are using incompatible cost baselines, and no saved JSON/JSONL contains token usage or actual billed cost to adjudicate which is correct.
   - Suggested fix: pick one methodology, store prompt/completion token counts per run, and regenerate every cost/ratio number from those stored fields.

4. **bnlearn scaling prose overclaims and conflicts with saved summaries.**
   - Paper:
     - line 442 says PAL on `>=20`-node networks is `0--3%` for **both** models
     - line 539 says Direct Answer is `0%`
     - line 594 says the DSL is “the only method that produces correct answers”
   - Raw evidence:
     - `baselines/results/bnlearn_openai_gpt-4o-mini_20260315_211540.json:pal.accuracy = 0.175`
     - `baselines/results/bnlearn_openai_gpt-5.4_20260315_211432.json:pal.accuracy = 0.23333333333333334`
     - `baselines/results/bnlearn_openai_gpt-4o-mini_20260315_004339.json:direct.accuracy = 0.55`
     - `baselines/results/bnlearn_openai_gpt-5.4_20260314_235817.json:direct.accuracy = 0.6083333333333333`
     - `baselines/results/bnlearn_openai_gpt-5.4_20260314_235817.json:compile_free.accuracy = 0.6083333333333333`
   - Why wrong: the saved bnlearn summaries do not support “Direct Answer to 0%” or “only method that produces correct answers”; even the PAL section’s per-network cells are not saved in JSON, so those exact cell values are not reproducible from the provided raw files.
   - Suggested fix: save per-query bnlearn details with network labels, then rewrite the prose to the exact supported scope.

5. **The paper mixes two different GPT-4o-mini bnlearn PAL runs.**
   - Paper:
     - line 994 says GPT-4o-mini PAL is `15%` overall
     - Table line 1011 says GPT-4o-mini PAL is `17.5%` overall
   - Raw evidence:
     - `baselines/results/bnlearn_openai_gpt-4o-mini_20260315_204336.json:pal.accuracy = 0.15`
     - `baselines/results/bnlearn_openai_gpt-4o-mini_20260315_211540.json:pal.accuracy = 0.175`
   - Why wrong: the paper is citing two different runs without saying so.
   - Suggested fix: choose one run and use it consistently, or report both with seeds / reruns explicitly.

6. **The Gemini row uses a different model variant than the model name stated in the paper/protocol.**
   - Paper:
     - Table lines 195 / 1198 say `Gemini 3.1`
     - line 877 lists `google/gemini-3.1-pro`
   - Raw evidence:
     - `baselines/results/pcd_google_gemini-3.1-pro-preview_20260313_221431.json:preference.compute_accuracy = 0.685`
     - `baselines/results/pcd_google_gemini-3.1-pro_20260313_215527.json:preference.compute_accuracy = 0.0`
   - Why wrong: the only saved file matching the paper’s `69%` row is the **preview** model, not `google/gemini-3.1-pro`.
   - Suggested fix: rename the row to the exact model identifier actually used or explain the run-selection/exclusion rule.

7. **The E2E residual-gap explanation is factually wrong.**
   - Paper: line 602 says “The remaining `0.2%` gap traces to two parse failures from malformed JSON, not extraction errors.”
   - Raw evidence:
     - `baselines/results/e2e_openai_gpt-4o-mini_20260325_101317.json:parse_success_rate = 0.9983974358974359` (`623/624`)
     - `baselines/results/e2e_openai_gpt-4o-mini_20260325_101317.json:gold_solver_match = 0.9983948635634029` (computed over successful parses only)
     - `baselines/results/e2e_openai_gpt-4o-mini_20260325_101317_details.json[291].e2e_matches_gold_solver = false`
     - `baselines/results/e2e_openai_gpt-4o-mini_20260325_101317_details.json[291].feature_exact_match = 0.9833333333333333`
   - Why wrong: there is `1` JSON parse failure, not `2`, and there is also `1` successful parse with imperfect feature extraction that changes the solver output.
   - Suggested fix: say “There is one malformed-JSON parse failure and one successful parse with a feature extraction error that changes the solver recommendation.”

8. **Core appendix evidence is missing from the provided raw-results directory.**
   - Missing raw files for:
     - equivalence claim on `1,200` instances and `0.0` max error (lines 339, 765)
     - LOO `6/6` first-attempt claims (lines 405--407, 768, 1109--1126)
     - Gate-3-off ablation (lines 588, 768)
     - TextBandit/bandit claims (lines 76, 100, 141, 750--752)
     - 23-strategy appendix and content-channel table (lines 614--616, 774--850)
   - Why wrong: with the currently provided raw files, these claims cannot be audited end-to-end.
   - Suggested fix: add the missing result JSON/JSONL files or remove/de-scope the unsupported appendix material.

## 100% CLAIMS INVENTORY

- `[C]` line 82: “100% compute-stage accuracy on all tested BN benchmarks” — central empirical claim, but no dedicated DSL BN result JSON is present; scope is also too broad.
- `[B]` line 84: “two held-out inference families ... reach 100%” — supported by held-out NB/HMM raw files, but should be scoped to `NB n=200` and `HMM n=100`.
- `[C]` line 108: “Decide accuracy is 100%” — true for preference and BLInD PCD, but held-out HMM mini is `98%`; wording needs scope.
- `[C]` line 118: “PAL fails entirely, while our compiled solver stays at 100%” — PAL does not “fail entirely” on the saved bnlearn summaries; DSL 100% lacks raw bnlearn JSON.
- `[C]` line 123: “compiled solver maintains 100% on `>=20`-node networks” — empirical, but the saved raw bnlearn files do not contain a DSL field.
- `[B]` lines 175, 184, 1188: “Decide = 100% for every/all models” — supported for preference PCD on `n=200`, but should be tied to that table only.
- `[C]` lines 176 / 130: “Parse and Decide `>=95%`/`>=96%`” — false for exact BN Parse.
- `[C]` line 198 / 254 / 434 / 539 / 592 / 722 / 963 / 995 / 1011 / 1147: multiple DSL `100%` BN claims — central but not backed by a dedicated DSL BN result JSON in `baselines/results/`.
- `[B]` lines 320, 553, 563--564, 575: held-out core-ops and unconstrained-code `100%` — supported on saved held-out test sets; needs explicit `NB n=200`, `HMM n=100` scope.
- `[C]` lines 407, 588, 702, 768, 1110--1126: LOO `6/6`, `100%`, first-attempt claims — no raw LOO result file provided.
- `[B]` lines 710, 1087, 1100--1103: reliability `20/20`, `40/40`, `100%` — supported, but this is still a small-`N` empirical run and should remain clearly scoped.

## PARSE RATE CROSS-CHECK

| Paper location | Paper claim | Raw evidence | Status |
|---|---|---|---|
| Abstract line 77 | “over 95% accuracy on ... parsing the structure” | Preference exact Parse is `82--100%`; BN exact Parse is `30.6--48.3%` (`pcd_*:*.parse_accuracy`) | `number_mismatch` |
| Intro line 108 | “Parse accuracy is 82--100% on primary task families” | Preference yes; BN no (`0.3067`, `0.3389`, `0.4833`, `0.3056`) | `number_mismatch` |
| Fig. 1 caption line 130 | “22--78% vs >=95% on Parse and Decide” | Decide mostly yes; exact BN Parse no | `number_mismatch` |
| Section text line 176 | “BN Parse stays >=96%” | `parse_by_depth` for GPT-5.4 is `81,56,38,25,19,23,13,11,10` | `number_mismatch` |
| Preference table lines 191--196 | Parse `82/100/100/100/100/100` | Supported by `pcd_*_preference.json:preference.parse_accuracy` | `exact_match` |
| Held-out caption/text lines 553, 576 | Parse `>=98%` / `>=99%` | NB mini Parse is `3.0%` | `number_mismatch` |

## COST CONSISTENCY

- Main-paper cost story:
  - line 83 / 592 / 722: `14x` vs compile-time GPT-5.4, `310x` vs PAL
  - Fig. 2(b) lines 525--530 / 539: `\$0.008` DSL, `\$0.11` compile-time GPT-5.4, `\$2.50` PAL GPT-5.4
- Saved repo cost story:
  - `baselines/results/cost_analysis.md:21` DSL total `~$0.001`
  - `baselines/results/cost_analysis.md:29` GPT-5.4 compile-time `~$0.04-0.08`
  - `paper/main.tex:1147-1150` Appendix cost table says `\$0.001`, `\$0.06`, `\$2.50`, `60x`, `2500x`
- Audit finding:
  - `\$0.008` and `\$0.11` do not match the saved repo cost accounting.
  - `14x` is compatible with `0.11 / 0.008`, while `60x` is compatible with `0.06 / 0.001`; both cannot be true for the same setup.
  - No raw JSON/JSONL stores usage/token counts, so the cost claims are not reproducible from saved evidence.

## ALL CLAIMS

Grouped when one line states a vector of related numbers.

| # | Line | Location | Paper text (short) | Paper value | Evidence file | Evidence value | Status |
|---|---:|---|---|---|---|---|---|
| 1 | 76 | Abstract | Six models tested | `6` | `pcd_*` preference/BN files | OpenAI 3 + Anthropic 2 + Google 1 row families present; bandit raw missing | `missing_evidence` |
| 2 | 77 | Abstract | Parse/Decide >95; Compute 22--78; depth-10 3--11 | `>95`, `22--78`, `3--11` | `pcd_openai_gpt-4o-mini_20260313_175446.json:preference.compute_accuracy`; `pcd_anthropic_claude-opus-4-6_20260313_220117.json:preference.compute_accuracy`; `pcd_openai_gpt-4o-mini_20260313_182537.json:bn.compute_depth_stats.10.correct`; `pcd_anthropic_claude-sonnet-4_20260313_213010.json:bn.compute_depth_stats.10.correct`; `pcd_openai_gpt-5.4_20260313_192813.json:bn.compute_depth_stats.10.correct` | Compute range and `3--11` supported; exact BN Parse/Decide headline not | `number_mismatch` |
| 3 | 82 | Abstract | As few as one example; 100% on all BN benchmarks; up to 37 nodes | `1`, `100%`, `37` | `examples_ablation_openai_gpt-4o-mini_20260315_200023.json:flight.results.1.success_rate`; `...:bn.results.1.success_rate`; bnlearn raw directory has no dedicated DSL result JSON | `k=1` supported only for 1 trial on Flight/BN; central BN-100 claim lacks dedicated raw JSON | `missing_evidence` |
| 4 | 83 | Abstract | 14x lower than compile-time, 310x lower than PAL | `14x`, `310x` | `baselines/results/cost_analysis.md:21-29`; Appendix table lines 1147--1150 | Saved repo cost story implies `60x` and `2500x`, not `14x` and `310x` | `number_mismatch` |
| 5 | 84 | Abstract | Two held-out families, seven ops, 100% | `2`, `7`, `100%` | `held_out_nb_openai_gpt-4o-mini_205problems_20260314_225603.json:compile_core_ops.accuracy`; `held_out_hmm_openai_gpt-4o-mini_105problems_20260314_214139.json:compile_core_ops.accuracy` | `1.0` on NB `n=200` and HMM `n=100` | `exact_match` |
| 6 | 95 | Intro | Depth-10 BN wrong 89% of time | `89%` | `pcd_openai_gpt-5.4_20260313_192813.json:bn.compute_depth_stats.10.correct/total` | `11/100` correct => `89%` wrong | `exact_match` |
| 7 | 108 | Intro | Parse 82--100, Decide 100, Compute 22--78 | `82--100`, `100`, `22--78` | same as #2 | Compute range supported; exact BN Parse headline unsupported | `number_mismatch` |
| 8 | 109 | Intro | GPT-5.4 only 11% at depth 10 | `11%` | `pcd_openai_gpt-5.4_20260313_192813.json:bn.compute_depth_stats.10.correct/total` | `11/100 = 11%` | `exact_match` |
| 9 | 117 | Intro | 1,200+ instances; zero compute-stage errors; 14x lower cost | `1,200+`, `0`, `14x` | No `TextBandit` / equivalence raw file; cost mismatch as above | Central claim not reproducible from saved raw | `missing_evidence` |
| 10 | 118 | Intro | Real-world BN up to 37 nodes; PAL fails entirely; ours 100 | `37`, `100%` | `bnlearn_openai_gpt-5.4_20260315_211432.json:pal.accuracy`; `bnlearn_openai_gpt-4o-mini_20260315_211540.json:pal.accuracy` | PAL overall is nonzero; DSL bnlearn field missing | `scope_overclaim` |
| 11 | 130 | Fig. 1 caption | Parse/Decide >=95 vs Compute 22--78 | `>=95`, `22--78` | PCD raw as above | Compute range yes; Parse no | `number_mismatch` |
| 12 | 141-142 | Setup | `n=748`, `n=900`, `n=120`, `n=200`, `n=100` | dataset sizes | `e2e_openai_gpt-4o-mini_20260325_101317.json:n_samples`; held-out and bnlearn JSON `n_total`; no Hotel/TextBandit raw result file | Flight/BLInD/bnlearn/NB/HMM partially traceable; Hotel/TextBandit not | `missing_evidence` |
| 13 | 175 | PCD text | Preference Compute 28--78; Decide 100 | `28--78`, `100` | `pcd_openai_gpt-4o-mini_20260313_175446.json:preference.compute_accuracy`; `pcd_anthropic_claude-opus-4-6_20260313_220117.json:preference.compute_accuracy`; all pref `decide_accuracy` | `27.5--77.5`, rounded; Decide `1.0` | `rounding_ok` |
| 14 | 176 | PCD text | BN Compute ~82 to single digits; Parse >=96; Decide 100 | `~82`, `single digits`, `>=96`, `100` | `pcd_openai_gpt-5.4_20260313_192813.json:bn.compute_depth_stats`; `...:bn.parse_by_depth`; `...:bn.decide_accuracy` | Compute trend yes; GPT-5.4 depth-10 is `11`; exact BN Parse not `>=96` | `number_mismatch` |
| 15 | 184-198 | Table 1 | Preference PCD rows | table rows | `pcd_openai_gpt-4o-mini_20260313_175446.json`; `pcd_openai_gpt-4o_20260313_191642.json`; `pcd_openai_gpt-5.4_20260313_215141.json`; `pcd_anthropic_claude-sonnet-4_20260313_211844.json`; `pcd_google_gemini-3.1-pro-preview_20260313_221431.json`; `pcd_anthropic_claude-opus-4-6_20260313_220117.json` | Parse and Compute percentages match to rounding; Gemini uses preview file; “Our DSL 100%” lacks dedicated preference-DSL raw file | `config_mismatch` |
| 16 | 229-249, 254 | Fig. 2 / depth plot | BN compute-by-depth values for GPT-5.4, Sonnet 4, GPT-4o-mini | depth vectors | `pcd_openai_gpt-5.4_20260313_192813.json:bn.compute_depth_stats`; `pcd_anthropic_claude-sonnet-4_20260313_213010.json:bn.compute_depth_stats`; `pcd_openai_gpt-4o-mini_20260313_182537.json:bn.compute_depth_stats` | All plotted compute values match saved counts | `exact_match` |
| 17 | 223, 254 | Fig. 2 / depth plot | Our DSL 100 at every depth | `100%` | no DSL BLInD result JSON in `baselines/results/` | no direct raw file | `missing_evidence` |
| 18 | 260 | PCD text | 67x price increase buys only +9pp | `67x`, `9pp` | `pcd_openai_gpt-4o-mini_20260313_182537.json:bn.compute_accuracy`; `pcd_openai_gpt-5.4_20260313_192813.json:bn.compute_accuracy`; `cost_analysis.md:7-9` | `22.3 -> 31.2` is `+8.9pp`; saved pricing is `16.7x`, not `67x` | `number_mismatch` |
| 19 | 301-307 | Method | Seven core ops, three macros | `7`, `3` | paper DSL definitions; no separate raw result dependency | Internal paper count consistent | `exact_match` |
| 20 | 327 | TaskSpec example | `5^4 = 625` hypotheses | `625` | arithmetic from stated values | exact arithmetic | `exact_match` |
| 21 | 332, 377 | Method | up to 3 refinement rounds | `3` | `run_inductor_reliability.py` / algorithm text; no contradiction in raw | consistent with code | `exact_match` |
| 22 | 406-412 | LOO + reliability text | 6 datasets, 3 families, all 6 pass, 20 times/family, 40 trials, k=1, k=3--5 | `6`, `3`, `100%`, `20`, `40`, `1`, `3--5` | `inductor_reliability_openai_gpt-4o-mini_20260315_200258.json`; `examples_ablation_openai_gpt-4o-mini_20260315_200023.json`; no LOO raw file | Reliability + k=1 supported; LOO 6/6 claims not saved | `missing_evidence` |
| 23 | 432-434 | BLInD baseline text | PAL mini `93 -> 2`; PAL GPT-5.4 `98.1` overall and `96` at depth10; compile-time 5.4 succeeds after 1 repair; mini fails after 5; 900 problems | numbers listed | `pal_openai_gpt-4o-mini_20260313_161931.json:bn.depth_stats`; `pal_openai_gpt-5.4_20260315_200846.json:bn.accuracy`; `compile_time_openai_gpt-5.4_20260313_193122.json:bn.repair_history`; `compile_time_openai_gpt-4o-mini_20260313_193916.json:bn.repair_history` | matches | `exact_match` |
| 24 | 440-446 | bnlearn text | Asia/Child/Insurance/Alarm node/edge counts; PAL `0--3` for both models on `>=20`; <10% execute; DSL 100 | numbers listed | bnlearn summary JSONs have overall only; no per-network saved PAL detail; direct summaries nonzero | exact per-network/raw mapping missing, prose overclaims | `scope_overclaim` |
| 25 | 476-483, 539 | Fig. 3(a) | bnlearn bars: DSL 100; PAL 5.4 `90/0/3/0`; PAL mini `27/20/23/0`; Direct `0/0/0/0` | bar values | overall bnlearn summaries exist; per-network cells/direct bars do not | per-network/raw mapping absent; saved Direct summaries contradict 0-bars | `number_mismatch` |
| 26 | 507-530, 539 | Fig. 3(b) | `\$0.008,100`; `\$0.11,100`; `\$2.50,98.1`; `\$0.05,0`; `\$0.84,26.4`; `\$3.60,31.2` | point labels | `cost_analysis.md`; `pal_openai_gpt-5.4_20260315_200846.json:bn.accuracy`; `pal_openai_gpt-4o-mini_20260313_161931.json:bn.accuracy`; no raw Direct BLInD result file | cost numbers inconsistent; `31.2` has no saved Direct BLInD raw result | `number_mismatch` |
| 27 | 546-570 | Held-out table | NB/HMM direct, unconstrained, core-ops, Parse/Compute/Decide values | full table | held-out NB/HMM JSONs under `held_out_*` | task accuracies and most stage values match; NB-mini Parse CI `[1,8]` does not | `rounding_ok` |
| 28 | 553, 576 | Held-out caption/text | Parse/Decide >=98 / >=99 | `>=98`, `>=99` | `held_out_nb_openai_gpt-4o-mini_205problems_20260314_225603.json:pcd.parse_accuracy` | `3.0%` Parse for NB mini | `number_mismatch` |
| 29 | 588 | Gate 3 ablation | all 6 LOO still pass; 100% consistent | `6`, `100%` | no Gate-3-off raw result file | unverifiable from provided raw | `missing_evidence` |
| 30 | 592-594 | Cost and scaling | `\$0.008`, `\$0.11`, `14x`, `\$2.50`, `310x`, “only method” on bnlearn | numbers listed | `cost_analysis.md`; bnlearn summary JSONs | cost inconsistent; “only method” contradicted by saved `compile_free.accuracy = 0.6083` | `number_mismatch` |
| 31 | 601-603 | E2E main text | 624 samples, 74.3% [70.9,77.8], oracle 74.4, 99.8 solver-match, 0.2 gap from two parse fails, best prompt 58.3, +16pp | numbers listed | `e2e_openai_gpt-4o-mini_20260325_101317.json`; `..._details.json`; no 23-strategy raw file | accuracy/CI/oracle/99.8 match; “two parse failures” false; `58.3` baseline missing | `aggregation_mismatch` |
| 32 | 614-616 | 23-strategy summary | 23 strategies, 624 samples, `<=33`, `50--64`, `73`, `74.8` | numbers listed | no strategy raw file in `baselines/results/` | unverifiable | `missing_evidence` |
| 33 | 623 | DeLLMa analysis text | compile-time scores `17--29%` vs `29%` baseline across 3 models | `17--29`, `29` | `dellma_openai_gpt-4o-mini_20problems.json:compile.accuracy = 0`; `dellma_openai_gpt-5.4_20problems.json:compile.accuracy = 29.411764705882355`; `dellma_anthropic_claude-opus-4-6_20problems.json:compile.accuracy = 17.647058823529413`; `random_baseline = 29.13095238095239` | one model is `0%`, not in `17--29` range | `number_mismatch` |
| 34 | 630-632 | Scaling analysis | Compute `22--78`; GPT-5.4 depth10 `11`; PAL `98.1` and `310x`; no combo guarantees correctness | numbers listed | PCD + PAL raw files; cost mismatch as above | accuracy parts match; cost ratio not reproducible | `scope_overclaim` |
| 35 | 634 | bnlearn analysis | Compute 0; PAL collapses to `0--3` on `>=20` nodes; DSL stays 100 | `0`, `0--3`, `100` | bnlearn summaries save only overall PAL/direct and PCD compute 0 | compute 0 exact; PAL per-network + DSL 100 not saved | `missing_evidence` |
| 36 | 680, 702, 710 | Limitations | five families/eight datasets; Parse >=96 at all depths; 6/6 LOO; 20 runs/two families 100 success | numbers listed | held-out + reliability raw; no bandit/LOO raw; BN Parse raw contradicts `>=96` | mixed: reliability exact, Parse and LOO not | `number_mismatch` |
| 37 | 718-722 | Conclusion | six models, five task families, >2,000 test instances, BN 100, 14x, 310x | numbers listed | raw files support >2,000 only under some aggregation choices; 5-family/bandit evidence missing; cost mismatch remains | `ambiguous_mapping` |
| 38 | 750-755 | Appendix family table | `624/124`, `4 configs`, `900+120`, `200`, `100` | table values | Flight e2e `624`; bnlearn `120`; held-out `200/100`; no TextBandit/Hotel raw result file | partial only | `missing_evidence` |
| 39 | 765 | Appendix equivalence | `0.0` max error over `1,200` instances: `250/250`, `900/900`, `50/50` | numbers listed | no equivalence/raw TextBandit result file | unverifiable | `missing_evidence` |
| 40 | 768 | Appendix Gate-3-off | all `6` LOO datasets, `100%` gold match, first attempt | numbers listed | no raw LOO/Gate3 file | unverifiable | `missing_evidence` |
| 41 | 789-850 | 23-strategy + content×channel appendix tables | all table values, CIs, `r=0.97`, `+18.7pp`, `+8.6pp` | many | no raw strategy result file | unverifiable | `missing_evidence` |
| 42 | 963-978 | Appendix PAL depth table | depth rows, overall `26.4`, `98.1`, `99.6`, `100` | table rows | `pal_openai_gpt-4o-mini_20260313_161931.json:bn.depth_stats`; `pal_openai_gpt-5.4_20260315_200846.json:bn.depth_stats` | matches, except DSL 100 lacks dedicated raw BLInD JSON | `exact_match` |
| 43 | 990-995 | Appendix bnlearn text | Compute `0%` on all 120; Decide `99.2/98.3`; GPT-5.4 PAL `97` Asia and `0` elsewhere; GPT-4o-mini PAL `15%`; DSL `100` | numbers listed | `bnlearn_openai_gpt-5.4_20260314_235817.json:pcd.compute_accuracy/decide_accuracy`; `bnlearn_openai_gpt-4o-mini_20260315_004339.json:pcd.compute_accuracy/decide_accuracy`; PAL overall from `204336` and `211432`/`211540` | compute/decide exact; GPT-4o-mini overall mixes 15 and 17.5; per-network PAL/DSL not saved | `number_mismatch` |
| 44 | 1006-1011 | Appendix bnlearn table | per-network PAL rows + overall 17.5/23.3/0/100 | table rows | overall PAL/PCD values from bnlearn JSONs; per-network cells / DSL column not saved | overall exact; per-network + DSL not traceable | `missing_evidence` |
| 45 | 1100-1103 | Reliability table | `20/20`, `20/20`, `40/40`, avg rounds `1.0`, avg time `5.6/4.8/5.2`, “All correct” | table values | `inductor_reliability_openai_gpt-4o-mini_20260315_200258.json:flight.*`; `...:bn.*` | matches | `exact_match` |
| 46 | 1147-1158 | Appendix cost table | `\$0.001`, `\$0.06`, `\$0.014`, `\$2.50`, `\$0.97`, `\$3.60`, `1x`, `60x`, `970x`, `2500x`, `3600x`, break-even after `1` query | numbers listed | `cost_analysis.md:15-58`; `compile_time_*`, `pal_*` summaries support accuracies and call counts, but not actual token usage | internally consistent with `cost_analysis.md`, but not reproducible from stored usage | `ambiguous_mapping` |

## SUSPICIONS TO CARRY FORWARD

- `grep -n "82--100\\%|>=95\\%|>=96\\%" paper/main.tex`
  - Reconcile every BN Parse headline against `pcd_*_bn*.json:bn.parse_accuracy` and `:bn.parse_by_depth`.
- `grep -n "\\$0.008\\|\\$0.11\\|14\\\\times\\|310\\\\times\\|\\$0.001\\|\\$0.06\\|60\\\\times\\|2500\\\\times" paper/main.tex baselines/results/cost_analysis.md`
  - Unify one cost methodology and store token usage in JSON.
- `grep -n "Gemini 3.1\\|gemini-3.1-pro" paper/main.tex`
  - Decide whether the correct evidence file is `pcd_google_gemini-3.1-pro-preview_20260313_221431.json` or whether the non-preview run should replace it.
- `grep -n "0--3\\%\\|fails entirely\\|Direct Answer to 0\\%" paper/main.tex`
  - Rebuild bnlearn Figure 3(a) from a saved per-query JSON, not from unsaved stdout.
- `grep -n "two parse failures\\|99.8\\% of instances\\|On all 624 samples" paper/main.tex`
  - Recompute E2E wording from `e2e_openai_gpt-4o-mini_20260325_101317.json` and `..._details.json`.
- `ls baselines/results | rg 'loo|gate3|strategy|content|bandit|textbandit|equiv'`
  - Missing result artifacts for LOO, Gate-3-off, 23-strategy/content-channel, TextBandit, and equivalence need to be added before a second audit.
