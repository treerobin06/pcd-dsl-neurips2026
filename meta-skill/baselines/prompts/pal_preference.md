# Preference Learning via Python Code

You are solving a preference learning task. A user has hidden preferences over {n_features} features: {feature_names}. Each feature has a numeric weight from the set {preference_values}. The user always picks the option with the highest weighted sum (utility = sum of weight_i * feature_value_i).

You have observed {n_history} rounds of the user's choices. In each round, the user was shown 3 options (each described by normalized feature values in [0, 1]) and picked one.

## Historical Data

{history_block}

## Current Round

Now the user sees these 3 options:
{current_options}

## Task

Write Python code (using only `numpy` and standard library) that:
1. Defines all possible preference weight vectors (Cartesian product of {preference_values} for {n_features} features)
2. Starts with a uniform prior over all weight vectors
3. For each historical round, updates the posterior using a softmax choice model: P(choice | weights) = exp(utility_of_chosen) / sum(exp(utility_of_each_option)), with temperature=1.0
4. Computes the expected utility of each current option under the posterior
5. Prints a single integer: the index (0, 1, or 2) of the recommended option

**Output ONLY the Python code inside a ```python``` block. No explanation.**
