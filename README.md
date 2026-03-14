# Compile Once, Reason Exactly: Verified Solver Induction for LLM Probabilistic Reasoning

**Anonymous supplementary code for NeurIPS 2026 submission.**

## Overview

This repository contains the complete implementation of:
1. **PCD (Parse-Compute-Decide)** diagnostic framework for LLM probabilistic reasoning
2. **Typed probabilistic DSL** with 7 core operations and 3 family macros
3. **Deterministic compiler** translating TaskSpec (JSON) to exact solvers
4. **Verifier-guided inductor** using GPT-4o-mini for few-shot specification inference
5. **All baselines** (Direct Answer, PAL, Compile-time Code Generation)
6. **All experiments** including held-out families (Naive Bayes, HMM, bnlearn)

## Directory Structure

```
.
├── dsl/                    # Probabilistic DSL library
│   ├── types.py            # Type system (Distribution, Factor, HypothesisSpace, Evidence)
│   ├── core_ops.py         # 7 core operations (normalize, multiply, marginalize, ...)
│   └── family_macros.py    # 3 family macros (softmax_pref, beta_bernoulli, ve_query)
│
├── taskspec/               # Declarative intermediate representation
│   ├── schema.py           # TaskSpec JSON schema (dataclasses)
│   └── compiler.py         # TaskSpec → Solver deterministic compiler
│
├── inductor/               # LLM-based specification inductor
│   ├── inductor.py         # Few-shot TaskSpec inference via GPT-4o-mini
│   └── refiner.py          # Self-refinement loop with verifier feedback
│
├── verifier/               # 3-gate verification pipeline
│   └── gates.py            # Gate 1 (Code Sanity), Gate 2 (Ground Truth), Gate 3 (Reference Match)
│
├── solvers/                # Gold reference solvers (for verification)
│   ├── preference_solver.py    # Hypothesis enumeration (Flight/Hotel)
│   ├── bn_solver.py            # Variable elimination (BLInD)
│   └── bandit_solver.py        # Conjugate update (TextBandit)
│
├── baselines/              # All baseline experiments
│   ├── run_pcd_experiment.py           # PCD diagnostic (6 models x 3 vendors)
│   ├── run_pal_experiment.py           # PAL baseline (per-instance code gen)
│   ├── run_compile_time_baseline.py    # Compile-time code generation baseline
│   ├── run_held_out_family.py          # Held-out: Naive Bayes (n=200)
│   ├── run_hmm_held_out.py             # Held-out: HMM forward filtering (n=100)
│   ├── run_bnlearn_held_out.py         # External: bnlearn standard BN networks
│   ├── run_dellma_experiment.py        # Negative result: DeLLMa
│   └── results/                        # All experimental results (JSON)
│
└── tests/                  # Test suite
    ├── test_dsl.py                 # DSL unit tests
    ├── test_compiler.py            # Compiler tests
    ├── test_equivalence_full.py    # Full equivalence verification (1200 instances)
    ├── test_inductor_e2e.py        # End-to-end inductor test (requires API)
    ├── test_loo_induction.py       # Leave-one-out generalization (requires API)
    └── test_gate3_ablation.py      # Gate 3 ablation (requires API)
```

## Safety Note

Baseline experiments (PAL, compile-time code generation) execute LLM-generated Python code in subprocesses. While we limit the execution environment (no network access, restricted PATH), this is **not a sandbox**. We recommend running these experiments in a container or virtual machine if you have security concerns. The core DSL tests (`test_dsl.py`, `test_compiler.py`) do not execute any LLM-generated code and are safe to run directly.

## Setup

### Requirements

```bash
pip install httpx openai numpy
pip install pgmpy  # only for bnlearn experiments
```

### Environment Variables

```bash
export OPENROUTER_API_KEY="your-key"    # Required for LLM experiments
export HTTPS_PROXY="http://..."          # Optional, for proxy environments
```

## Running Experiments

### 1. Local tests (no API required)

```bash
# DSL unit tests + compiler tests + equivalence verification
python -m pytest tests/test_dsl.py tests/test_compiler.py tests/test_equivalence_full.py -v
```

### 2. PCD Diagnostic

```bash
# Preference learning (Flight, 200 samples)
python baselines/run_pcd_experiment.py --task preference --model openai/gpt-4o-mini --n 200

# Bayesian network inference (BLInD, 900 samples)
python baselines/run_pcd_experiment.py --task bn --model openai/gpt-5.4
```

### 3. Baselines

```bash
# PAL baseline
python baselines/run_pal_experiment.py --task bn --model openai/gpt-4o-mini

# Compile-time code generation
python baselines/run_compile_time_baseline.py --model openai/gpt-5.4 --task bn --k 5
```

### 4. Held-out Families

```bash
# Naive Bayes (n=205: 5 train + 200 test)
python baselines/run_held_out_family.py --model openai/gpt-4o-mini --n 205

# HMM Forward Filtering (n=105: 5 train + 100 test)
python baselines/run_hmm_held_out.py --model openai/gpt-5.4 --n 105

# bnlearn standard networks (Asia, Child, Insurance, Alarm)
python baselines/run_bnlearn_held_out.py --model openai/gpt-5.4 --queries-per-net 30
```

### 5. Inductor End-to-End

```bash
# Leave-one-out generalization test
python -m pytest tests/test_loo_induction.py -v

# Gate 3 ablation
python tests/test_gate3_ablation.py
```

## Key Results (pre-computed in `baselines/results/`)

| Experiment | Key Finding |
|------------|-------------|
| PCD (6 models) | Parse 82-100%, Compute 22-78%, Decide >=98% |
| BN depth curve | Compute collapses from 82% (depth 2) to 3% (depth 10) |
| PAL vs DSL | PAL 26.4% vs DSL 100% on BN inference |
| Compile-time | GPT-5.4: 100%, GPT-4o: 0%, GPT-4o-mini via DSL: 100% |
| Held-out NB (n=200) | Core-ops 100%, PCD Compute 37-64.5% |
| Held-out HMM (n=100) | Core-ops 100%, PCD Compute 27-53% |
| bnlearn (120 queries) | PCD Compute 0%, Decide 98-99% |
| DeLLMa (negative) | DSL 17-29% vs 29% baseline |

## License

MIT License. See individual dataset licenses in the paper appendix.
