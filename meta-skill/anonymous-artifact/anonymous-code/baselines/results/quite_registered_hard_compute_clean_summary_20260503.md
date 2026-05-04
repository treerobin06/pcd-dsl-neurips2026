# QUITE Registered Hard-Compute Clean Smoke

Date: 2026-05-03

Split: `hard-compute-clean`, 25 numeric QUITE queries from 5 networks
(`mildew0`, `insurance1`, `hailfinder0`, `water1`, `sachs1`).
Metric: probability within absolute error <= 0.05.

| Method | Model | Accuracy | MAE | Time | Cost | Token usage | Raw artifact |
|---|---:|---:|---:|---:|---:|---:|---|
| Registered E2E (ours) | GPT-4o-mini | 25/25 = 100.0% | 0.002185 | 5.3s | $0.002558 | 12,072 / 1,245 | `quite_registered_hard_compute_openai_gpt-4o-mini_20260503_203938.json` |
| Registered E2E (ours) | GPT-5.4 | 25/25 = 100.0% | 0.002185 | 6.6s | $0.042747 | 12,047 / 842 | `quite_registered_hard_compute_openai_gpt-5.4_20260503_204744.json` |
| Direct answer | GPT-4o-mini | 8/25 = 32.0% | 0.285851 | 7.4s | $0.027093 | 182,472 / 881 | `quite_direct_numeric_openai_gpt-4o-mini_20260503_204745.json` |
| Direct answer | GPT-5.4 | 14/25 = 56.0% | 0.091095 | 9.5s | $0.212937 | 182,447 / 1,452 | `quite_direct_numeric_openai_gpt-5.4_20260503_204814.json` |
| PAL codegen | GPT-4o-mini | 5/25 = 20.0% | 0.283910 | 140.4s | $0.042766 | 182,847 / 30,845 | `quite_registered_hard_compute_pal_openai_gpt-4o-mini_20260503_205025.json` |
| PAL codegen | GPT-5.4 | 21/25 = 84.0% | 0.004853 | 129.6s | $0.838895 | 182,822 / 46,384 | `quite_registered_hard_compute_pal_openai_gpt-5.4_20260503_205244.json` |

Interpretation: this split isolates compute-heavy posterior inference after
network registration. The registered solver pays only the lightweight query
parser cost at runtime, while direct and PAL repeatedly consume the full
natural-language premise context.
