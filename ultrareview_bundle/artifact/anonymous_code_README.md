# Compile Once, Reason Exactly

Anonymous supplementary artifact for the NeurIPS 2026 submission.

This artifact contains the code, minimal data, prompt templates, and curated raw
result records needed to reproduce or audit the main experiments in the paper.
It is intentionally smaller than the working repository: scratch runs, obsolete
sanity checks, failed scaffold experiments, private sync files, API credentials,
and local build products are excluded.

## Layout

Extracting `anonymous-code.zip` creates three top-level directories:

```text
anonymous-code/        # VSI, PCD, baselines, tests, and result JSONs
data/                  # Minimal public/benchmark data used by the runners
phase1/                # Small compatibility layer for preference-learning checks
```

Run commands from `anonymous-code/`. Several runners use paths such as
`../data/external/BLInD/...`, so keep the three directories as siblings.

## What Is Included

- `dsl/`: typed probabilistic primitives and family macros.
- `taskspec/`: declarative TaskSpec schema and deterministic compiler.
- `solvers/`: reference and compiled solver implementations.
- `inductor/`: LLM-based TaskSpec induction and refinement utilities.
- `verifier/`: two-gate execution/reference validation utilities.
- `baselines/`: PCD, direct-answer, PAL, QUITE, bnlearn, mixed E2E, and VSI runners.
- `baselines/results/`: curated JSON records that correspond to the current paper.
- `tests/`: local unit/equivalence tests.
- `../data/`: Flight/Hotel, BLInD, QUITE, and TextBandit data required by the runners.
- `../phase1/`: minimal Bayesian Teaching compatibility code and strategy-ablation summaries.

## What Is Excluded

- API keys, `.env` files, Overleaf sync files, local absolute paths, and account metadata.
- Python caches, `.DS_Store`, virtual environments, and generated LaTeX artifacts.
- Deprecated Gate-3 ablations and old mixed-stream sanity checks that produced suspicious
  100% routing/e2e results and are not part of the current paper evidence chain.
- QUITE failed scaffold runs, debug scripts, and negative scratch experiments not reported
  in the paper.

## Setup

Python 3.12 is recommended.

```bash
cd anonymous-code
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
pip install -e .
```

API-based experiments use OpenRouter:

```bash
export OPENROUTER_API_KEY="your-openrouter-key"
export HTTPS_PROXY="http://127.0.0.1:7897"  # optional
```

No API key is needed for the local tests and deterministic backend checks.

## Local Checks

```bash
python3 tests/test_dsl.py
python3 -m unittest tests.test_compiler -v
python3 tests/test_equivalence_full.py
python3 baselines/verify_bnlearn_dsl_100.py --queries-per-net 100 --seed 2026
```

`verify_bnlearn_dsl_100.py` requires `pgmpy` and `scipy`; all other checks above
use only the local data and core Python/numpy stack.

## Reproducing Main Reported Experiments

The following commands regenerate the main experiment groups. API cost depends
on the model provider and gateway pricing at run time.

```bash
# PCD diagnostic
python3 baselines/run_pcd_experiment.py --task preference --model openai/gpt-4o-mini --n 200
python3 baselines/run_pcd_experiment.py --task bn --model openai/gpt-4o-mini

# Single-family natural-language E2E
python3 baselines/run_e2e_experiment.py --dataset flight --n 624 --concurrency 10 --model openai/gpt-4o-mini
python3 baselines/run_e2e_experiment.py --dataset hotel --n 124 --concurrency 10 --model openai/gpt-4o-mini
python3 baselines/run_textbandit_e2e.py --n 100 --concurrency 10 --model openai/gpt-4o-mini

# Held-out Naive Bayes / HMM E2E and paired direct baseline
python3 baselines/run_nl_e2e_stress.py --family nb --n 120 --seeds 5 --model openai/gpt-4o-mini
python3 baselines/run_nl_e2e_stress.py --family hmm --n 100 --seeds 5 --model openai/gpt-4o-mini
python3 baselines/run_structured_direct_baseline.py --seeds 5 --model openai/gpt-4o-mini

# Mixed stream and external QUITE split
python3 baselines/run_all_family_mixed_e2e.py --n-per-family 100 --n-unsupported 50 --concurrency 10 --model openai/gpt-4o-mini
python3 baselines/run_quite_registered_e2e.py --preset hard_compute_expanded_75 --model openai/gpt-4o-mini
python3 baselines/run_quite_direct_baseline.py --preset hard_compute_expanded_75 --model openai/gpt-4o-mini
python3 baselines/run_quite_registered_pal_baseline.py --preset hard_compute_expanded_75 --model openai/gpt-4o-mini
```

## Curated Result Records

`baselines/results/RESULTS_MANIFEST.md` maps the paper result groups to exact
JSON files. Each JSON artifact includes runner metadata, prompts or input
records where applicable, model identifiers, parsed outputs, and aggregate
metrics. The manifest is deliberately curated; it is not a dump of every scratch
run from the development repository.

## Safety Note

PAL and compile-time baselines execute LLM-generated Python in subprocesses.
Although the scripts restrict the execution environment, they are not a formal
sandbox. Run those baselines in a container or disposable environment if that is
important for your threat model. The VSI compiler tests and deterministic backend
checks do not execute model-generated code.

## License

Code is released under the MIT License. Dataset files remain under their
respective upstream licenses; included QUITE license and citation files are kept
under `../data/external/QUITE/`.
