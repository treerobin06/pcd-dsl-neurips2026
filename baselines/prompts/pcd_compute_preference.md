Compute Bayesian posterior inference for a preference learning task.

**Setup:**
- {n_features} features: {feature_names}
- Each feature weight is from {preference_values}
- Total hypotheses: {n_hypotheses} (all combinations of weight values)
- Prior: uniform (1/{n_hypotheses} each)
- Choice model: P(choose option i | weights w) = exp(w·x_i) / sum_j exp(w·x_j), temperature=1.0

**Observed choices:**
{observations_formatted}

**Current options to evaluate:**
{current_options_formatted}

**Task:** For each current option, compute its Expected Utility:
  EU(option_i) = sum over all weight vectors w of: P(w|data) * dot(w, option_i_features)

Then recommend the option with the highest EU.

Output a JSON object:
```json
{{
  "recommendation": <int>
}}
```

Think step by step, then output the JSON on the last line inside a ```json``` block.
