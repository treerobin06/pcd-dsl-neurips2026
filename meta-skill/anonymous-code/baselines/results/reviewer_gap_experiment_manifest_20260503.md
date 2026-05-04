# Reviewer-Gap Experiment Manifest, 2026-05-03

This batch collects raw evidence for reviewer-facing gaps before deciding which
results should enter the paper.

## New Raw Artifacts

| Experiment | Artifact | Main Result |
|---|---|---|
| Router metrics from existing full mixed run | `baselines/results/router_metrics_20260503_102657.json` | Route 650/650 = 100.0%; supported recall 600/600; unsupported reject 50/50 |
| Structured-output direct baseline | `baselines/results/structured_direct_openai_gpt-4o-mini_20260503_102910.json` | Overall 69/320 = 21.6%; NB 28/120 = 23.3%; HMM 40/100 = 40.0%; BLInD depth-10 1/100 = 1.0% |
| NB/HMM adversarial E2E seed 0 | `baselines/results/adversarial_nl_e2e_20260503_183047.json` | NB 111/120 = 92.5%; HMM 98/100 = 98.0% |
| NB/HMM adversarial E2E seed 1 | `baselines/results/adversarial_nl_e2e_20260503_183210.json` | NB 110/120 = 91.7%; HMM 98/100 = 98.0% |
| NB/HMM adversarial E2E seed 2 | `baselines/results/adversarial_nl_e2e_20260503_183332.json` | NB 109/120 = 90.8%; HMM 96/100 = 96.0% |
| NB/HMM adversarial E2E seed 3 | `baselines/results/adversarial_nl_e2e_20260503_183452.json` | NB 108/120 = 90.0%; HMM 99/100 = 99.0% |
| NB/HMM adversarial E2E seed 4 | `baselines/results/adversarial_nl_e2e_20260503_183611.json` | NB 107/120 = 89.2%; HMM 97/100 = 97.0% |
| NB/HMM adversarial E2E multi-seed summary | `baselines/results/adversarial_nl_e2e_multiseed_summary_20260503_183611.json` | Pooled NB 545/600 = 90.8%; HMM 488/500 = 97.6%; overall 1033/1100 = 93.9% |
| NB/HMM inductor reliability smoke | `baselines/results/inductor_reliability_nb_hmm_openai_gpt-4o-mini_20260503_183700.json` | First-pass/final 4/4 = 100.0% |
| NB/HMM inductor reliability full | `baselines/results/inductor_reliability_nb_hmm_openai_gpt-4o-mini_20260503_183835.json` | First-pass 95/100 = 95.0%; final 96/100 = 96.0%; NB final 47/50 = 94.0%; HMM final 49/50 = 98.0% |
| QUITE direct baseline smoke | `baselines/results/quite_direct_numeric_openai_gpt-4o-mini_20260503_184045.json` | Numeric smoke, 30 items; within 0.05: 10/30 = 33.3%; MAE 0.253 |
| QUITE direct baseline full | `baselines/results/quite_direct_numeric-wep_openai_gpt-4o-mini_20260503_184206.json` | 1154/1154 parsed; within 0.05: 320/1154 = 27.7%; MAE 0.365 |

## External Material Downloaded

| Source | Local Path | Notes |
|---|---|---|
| QUITE code/data | `data/external/QUITE` | 30 corpus JSON files, 577 evidence-query pairs |
| LLM-BI code/PDF | `data/external/LLM-BI/llm_bi` | Repository contains `llm_pymc.py` and `paper.pdf`, no benchmark-style dataset found |
| DisCIPL/self-steering code | `data/external/self-steering` | Framework code downloaded for related-work inspection |
| Related PDFs | `data/external/papers` | `llm-bi_2508.08300.pdf`, `quite_2410.10449.pdf`, `self_steering_discipl_2504.07081.pdf` |

## Verification

Commands run from `meta-skill`:

```bash
python3 -m py_compile baselines/run_nl_e2e_stress.py baselines/run_structured_direct_baseline.py baselines/summarize_router_metrics.py
python3 -m py_compile baselines/run_inductor_reliability_nb_hmm.py
python3 -m py_compile baselines/run_quite_direct_baseline.py
python3 tests/test_dsl.py
python3 tests/test_compiler.py
python3 tests/test_equivalence_full.py
```

Results: DSL 25/25 OK; compiler 13/13 OK; full equivalence BLInD 900/900 and
Flight 250/250 OK. Runtime warnings are pre-existing floating-point stress
warnings in utility-matrix tests.
