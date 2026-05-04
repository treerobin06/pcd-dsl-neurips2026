# QUITE External Expansion Summary (2026-05-03)

Purpose: test whether QUITE can strengthen the NeurIPS story without making the paper look hand-picked. The useful setting is a registered-network, parse-simple / compute-hard evaluation: the network is loaded from QUITE's structured Problog artifact, the LLM parses only short evidence/query text, and the deterministic backend performs exact inference.

## Hard-Compute Expanded Split

Split: `hard-compute-expanded-75`, 5 QUITE networks (`mildew0`, `insurance1`, `hailfinder0`, `water1`, `sachs1`), 75 total numeric queries. The 50-query row is the `hard-compute-expanded-50` prefix subset derived from the same 75-query raw runs.

Accuracy is within absolute posterior error `<= 0.05`.

| Method | Model | n=50 | n=75 | MAE (n=75) | Cost (n=75) | Time (n=75) | Raw artifact |
|---|---:|---:|---:|---:|---:|---:|---|
| VSI registered solver | GPT-4o-mini | 49/50 = 98.0% | 72/75 = 96.0% | 0.0059 | $0.0083 | 16.9s | `quite_registered_hard_compute_expanded_75_openai_gpt-4o-mini_20260503_213142.json` |
| Direct answer | GPT-4o-mini | 19/50 = 38.0% | 27/75 = 36.0% | 0.2478 | $0.0477 | 12.8s | `quite_direct_numeric_hard_compute_expanded_75_openai_gpt-4o-mini_20260503_213252.json` |
| Direct answer | GPT-5.4 | 32/50 = 64.0% | 45/75 = 60.0% | 0.0876 | $0.2353 | 33.4s | `quite_direct_numeric_hard_compute_expanded_75_openai_gpt-5.4_20260503_213312.json` |
| PAL code generation | GPT-4o-mini | 13/50 = 26.0% | 18/75 = 24.0% | 0.2816 | $0.1151 | 319.3s | `quite_registered_pal_hard_compute_expanded_75_openai_gpt-4o-mini_20260503_213758.json` |
| PAL code generation | GPT-5.4 | 44/50 = 88.0% | 66/75 = 88.0% | 0.0054 | $2.4897 | 402.9s | `quite_registered_pal_hard_compute_expanded_75_openai_gpt-5.4_20260503_213922.json` |

Recommended use: include this as a compact external-benchmark table or bar chart. It supports the claim that VSI is not just better than weak direct answering: even a stronger direct model and a strong PAL model trail the registered deterministic solver, while PAL is much slower and more expensive.

## All-Network Registered Smoke

Split: `all-network-3`, 30 QUITE networks, first 3 valid numeric queries per network, 90 total queries. This is deliberately not hand-picked.

| Method | Model | Result | Cost | Time | Raw artifact |
|---|---:|---:|---:|---:|---|
| VSI registered solver | GPT-4o-mini | 63/90 = 70.0% | $0.0094 | 19.2s | `quite_registered_all_network_3_openai_gpt-4o-mini_20260503_213145.json` |

Recommended use: keep as an appendix stress test or internal optimization target, not a main contribution table. It is useful for showing that the expanded QUITE setting was not cherry-picked, but the current parser/registry compatibility across every QUITE network is still uneven.

## LLM-BI Check

The public LLM-BI repository currently contains only `llm_pymc.py` and `paper.pdf`; no released benchmark dataset was found locally or in the upstream repository. The arXiv abstract describes two proof-of-concept Bayesian linear regression experiments rather than a reusable benchmark suite. Recommendation: cite LLM-BI in related work if useful, but do not add it as an experimental comparison unless we create a separate PyMC/continuous-inference benchmark, which is outside the finite-discrete exact-inference claim of VSI.

Sources checked:

- arXiv: `https://arxiv.org/abs/2508.08300`
- GitHub: `https://github.com/YongchaoHuang/llm_bi`

