# Probabilistic Solver Induction

You are a probabilistic reasoning expert. Your task is to analyze sample data from a probabilistic reasoning task and produce a **TaskSpec** — a structured JSON specification that fully describes the task's mathematical structure.

## Available Inference Families

Your TaskSpec must use exactly one of these inference families:

### 1. `hypothesis_enumeration`
**When to use**: The task involves inferring hidden preferences/parameters from sequential choices. There's a discrete set of possible hypotheses (e.g., preference weight vectors), and each observation updates beliefs via Bayesian inference.

**Key signals**:
- Multiple rounds of interaction with user choices
- Options have feature vectors
- Goal is to predict what the user prefers

**state_structure**: `discrete_hypothesis_space` with features and values_per_feature
  - `features`: list of feature names (e.g., from option descriptions or data fields)
  - `values_per_feature`: a **flat list of numeric values** representing possible preference weights. Default to `[-1.0, -0.5, 0.0, 0.5, 1.0]` (a symmetric 5-point grid commonly used in preference-learning benchmarks). If the task description or numeric features in `rounds[*].options` clearly suggest a different range, use that. Do NOT rely on any 'reward_fn' / 'answers' / 'correct_*' field — these have been removed for held-out evaluation (C5 fix).
  - IMPORTANT: `values_per_feature` must be numeric (float), NOT categorical strings.
**observation_model**: `softmax_choice` (user picks option proportional to exp(utility))
**decision_rule**: `argmax_expected_utility`

### 2. `conjugate_update`
**When to use**: The task involves repeated binary trials on multiple independent options (arms). Each arm has an unknown success probability, updated via Beta-Bernoulli conjugate updates.

**Key signals**:
- Multiple arms/options to try
- Binary feedback (win/lose, success/failure)
- Goal is to identify the best arm

**state_structure**: `beta_conjugate` with n_arms
**observation_model**: `bernoulli_reward`
**decision_rule**: `argmax_posterior_mean`

### 3. `variable_elimination`
**When to use**: The task involves computing exact probabilities in a Bayesian network. The network structure (DAG) and conditional probability tables (CPTs) are given.

**Key signals**:
- Directed acyclic graph with nodes and edges
- Conditional probability tables given as text
- Query asks for P(X|Y) or P(X,Y)

**state_structure**: `bayesian_network` with three optional config fields:
  - `bn_inference_method`: `"variable_elimination"` (default; only one supported currently)
  - `bn_input_format`: `"blind_text"` (default, BLInD CSV format) | `"factors_dict"` (pre-parsed Factor list)
  - `bn_numerical_precision`: `"float64"` (default; mpfr/任意精度 future)

These fields drive compiler dispatch (C3 真重构 2026-04-24): different config produces different solver. Defaults are fine for most BLInD-style tasks; only override when the task description specifies otherwise.
**observation_model**: `cpt_given`
**decision_rule**: `exact_probability`

### 4. `naive_bayes` (held-out family, no macro — composes 5 core ops)
**When to use**: The task gives a discrete class label set (e.g. diseases, sentiments, document categories) and a set of observed feature values. Goal: infer most likely class via P(c | features) ∝ P(c) × ∏_j P(f_j | c).

**Key signals**:
- A list of class labels (e.g. `diseases`, `categories`)
- For each class, P(feature | class) CPT given (e.g. `likelihoods[disease][symptom]`)
- Optional `priors` over classes
- Observed feature values to predict from

**state_structure**: `naive_bayes_classes` with:
  - `nb_classes`: list of class labels
  - `nb_feature_likelihoods`: nested dict `{feature_name: {feature_value: {class: prob}}}` — full CPT
    - For binary features (e.g. symptom present/absent), include both `True`/`False` (or `present`/`absent`) entries
    - String keys throughout (LLM should normalize feature values to consistent strings)
  - `nb_prior`: optional `{class: prob}` (empty = uniform)

**observation_model**: `feature_independence` (NB assumption: features conditionally independent given class)
**decision_rule**: `argmax_class_posterior`

The compiler instantiates `NBSolver` which composes condition + multiply + marginalize + normalize + argmax (no LLM in the loop at solve time).

### 5. `hmm_forward` (held-out family, no macro — composes 5 ops with iteration)
**When to use**: The task involves a sequence of observations from a hidden state model (HMM). Goal: filter posterior P(s_T | o_0, ..., o_T) over hidden states given the observed sequence.

**Key signals**:
- Discrete hidden state set (e.g. `sunny`/`rainy`, POS tags)
- Discrete observation set (e.g. `umbrella`/`no_umbrella`, words)
- Initial state distribution + transition CPT P(s_t | s_{t-1}) + emission CPT P(o | s)
- A sequence of observations to filter over

**state_structure**: `hmm_states` with:
  - `hmm_states`: list of hidden state names
  - `hmm_observations`: list of observation values
  - `hmm_initial`: `{state: pi(state)}`
  - `hmm_transition`: `{prev_state: {next_state: P(next|prev)}}`
  - `hmm_emission`: `{state: {observation: P(obs|state)}}`

**observation_model**: `discrete_emission`
**decision_rule**: `filter_posterior`

The compiler instantiates `HMMSolver` which uses the same 5 ops as NB but iterates `multiply → marginalize → normalize` over the time axis (a sequential pattern absent from any built-in macro).

## TaskSpec Schema

```json
{
  "task_name": "string — descriptive name",
  "inference_family": "hypothesis_enumeration | conjugate_update | variable_elimination | naive_bayes | hmm_forward",
  "state_structure": {
    "type": "discrete_hypothesis_space | beta_conjugate | bayesian_network | naive_bayes_classes | hmm_states",
    "hypothesis": "what each hypothesis represents (for hypothesis_enumeration)",
    "features": ["feature names (for hypothesis_enumeration)"],
    "values_per_feature": [possible values each feature weight can take],
    "n_arms": number of arms (for conjugate_update),
    "prior_alpha": 1.0,
    "prior_beta": 1.0
  },
  "observation_model": {
    "type": "softmax_choice | bernoulli_reward | cpt_given",
    "temperature": 1.0,
    "input": "description of what is observed"
  },
  "decision_rule": {
    "type": "argmax_expected_utility | argmax_posterior_mean | exact_probability",
    "utility": "what utility/score function to use"
  },
  "data_format": {
    "rounds": "sequential | single_shot",
    "options_per_round": number,
    "feedback": "chosen_option_index | binary_reward | none"
  }
}
```

## Instructions

1. Examine the provided sample data carefully
2. Identify which inference family matches the task structure
3. Extract all parameters (features, value ranges, number of arms, etc.)
4. Output a valid TaskSpec JSON

## Important Notes

- For `hypothesis_enumeration`: the `values_per_feature` field must be a **flat list** of **numeric values** (floats). Default to the symmetric 5-point grid `[-1.0, -0.5, 0.0, 0.5, 1.0]` unless the task description specifies otherwise. The `reward_fn`/`answers`/`correct_*` fields have been removed from samples (C5 fix); inferring values from those fields is no longer valid.
- For `conjugate_update`: the `n_arms` field should be the number of arms/machines/options.
- For `variable_elimination`: the BN structure is parsed from data at runtime, so `features` and `values_per_feature` can be empty.
- All `values_per_feature` entries must be numbers, never strings or nested lists.

**Output ONLY the JSON object, no explanation.**

## Sample Data

{samples}
