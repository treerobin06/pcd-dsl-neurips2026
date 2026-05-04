You are analyzing a preference learning task. A user has hidden preferences over {n_features} features: {feature_names}. Each feature has a numeric weight from the set {preference_values}. The user always picks the option that maximizes their weighted utility (utility = sum of weight_i * feature_value_i).

You have observed {n_history} rounds of the user's choices:

{history_block}

Now the user sees these options:
{current_options}

Extract the structured data needed for Bayesian inference. Output a JSON object with EXACTLY this format:
```json
{{
  "n_features": <int>,
  "feature_names": [<str>, ...],
  "preference_values": [<float>, ...],
  "observations": [
    {{"round": 1, "chosen_idx": <int>, "option_features": [[<float>, ...], ...]}},
    ...
  ],
  "current_options": [[<float>, ...], ...]
}}
```

For "preference_values", use the weight values given above: {preference_values}.

**Output ONLY the JSON inside a ```json``` block. No explanation.**
