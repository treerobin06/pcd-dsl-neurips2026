import math
import itertools


PREFERENCE_VALUES = [-1.0, -0.5, 0.0, 0.5, 1.0]
TEMPERATURE = 1.0


def dot(a, b):
    return sum(x * y for x, y in zip(a, b))


def softmax_probs(utilities, temperature=1.0):
    scaled = [u / temperature for u in utilities]
    m = max(scaled)
    exps = [math.exp(x - m) for x in scaled]
    s = sum(exps)
    return [e / s for e in exps]


def all_weight_hypotheses(n_features):
    return list(itertools.product(PREFERENCE_VALUES, repeat=n_features))


def solve(features, rounds_history, current_options):
    n_features = len(features)
    hypotheses = all_weight_hypotheses(n_features)

    # Uniform prior
    posterior = {w: 1.0 for w in hypotheses}

    # Bayesian updates from observed choices
    for rnd in rounds_history:
        options = rnd["options"]
        chosen_idx = rnd["chosen_idx"]

        new_posterior = {}
        total = 0.0

        for w, prior_prob in posterior.items():
            utilities = [dot(w, option) for option in options]
            probs = softmax_probs(utilities, temperature=TEMPERATURE)
            likelihood = probs[chosen_idx]
            post = prior_prob * likelihood
            new_posterior[w] = post
            total += post

        # Normalize
        if total == 0.0:
            # Fallback to uniform if numerical underflow somehow collapses all mass
            uniform = 1.0 / len(hypotheses)
            posterior = {w: uniform for w in hypotheses}
        else:
            posterior = {w: p / total for w, p in new_posterior.items()}

    # Expected utility under posterior for current options
    expected_utilities = [0.0, 0.0, 0.0]
    for w, prob in posterior.items():
        for i, option in enumerate(current_options):
            expected_utilities[i] += prob * dot(w, option)

    best_idx = max(range(3), key=lambda i: expected_utilities[i])
    return best_idx


def run_examples():
    examples = []

    # Example 1
    features = ['departure_time', 'duration', 'number_of_stops', 'price']
    rounds_history = [
        {
            "options": [
                [0.80, 0.40, 0.50, 0.20],
                [0.90, 0.60, 0.50, 0.30],
                [0.40, 0.70, 1.00, 0.40],
            ],
            "chosen_idx": 2,
        },
        {
            "options": [
                [0.60, 1.00, 0.50, 0.20],
                [0.70, 0.20, 0.00, 0.30],
                [0.30, 0.20, 0.50, 0.60],
            ],
            "chosen_idx": 0,
        },
        {
            "options": [
                [0.30, 1.00, 0.00, 0.30],
                [0.10, 0.00, 1.00, 0.90],
                [0.40, 0.50, 0.00, 0.00],
            ],
            "chosen_idx": 0,
        },
        {
            "options": [
                [0.30, 0.40, 0.50, 0.40],
                [0.20, 0.90, 1.00, 1.00],
                [1.00, 0.70, 0.00, 0.10],
            ],
            "chosen_idx": 1,
        },
    ]
    current_options = [
        [0.40, 0.20, 0.00, 0.90],
        [0.40, 0.00, 0.00, 1.00],
        [0.70, 1.00, 0.50, 0.50],
    ]
    examples.append((features, rounds_history, current_options, 2))

    # Example 2
    features = ['departure_time', 'duration', 'number_of_stops', 'price']
    rounds_history = [
        {
            "options": [
                [0.00, 0.30, 0.00, 0.70],
                [0.70, 1.00, 0.50, 0.80],
                [0.40, 0.70, 0.00, 0.40],
            ],
            "chosen_idx": 0,
        },
        {
            "options": [
                [0.20, 0.10, 1.00, 0.70],
                [1.00, 0.50, 0.50, 0.80],
                [0.80, 0.10, 1.00, 0.40],
            ],
            "chosen_idx": 0,
        },
        {
            "options": [
                [0.80, 0.30, 0.50, 1.00],
                [0.30, 0.60, 1.00, 0.60],
                [0.40, 1.00, 1.00, 0.50],
            ],
            "chosen_idx": 1,
        },
        {
            "options": [
                [0.30, 0.20, 0.50, 0.80],
                [0.90, 0.00, 1.00, 0.00],
                [0.90, 0.10, 0.50, 0.10],
            ],
            "chosen_idx": 2,
        },
    ]
    current_options = [
        [0.60, 0.10, 0.00, 0.10],
        [0.70, 0.40, 0.00, 0.80],
        [0.40, 0.00, 0.50, 0.20],
    ]
    examples.append((features, rounds_history, current_options, 2))

    # Example 3
    features = ['departure_time', 'duration', 'number_of_stops', 'price']
    rounds_history = [
        {
            "options": [
                [0.80, 0.60, 1.00, 0.20],
                [0.40, 0.20, 1.00, 1.00],
                [0.90, 0.60, 1.00, 0.30],
            ],
            "chosen_idx": 0,
        },
        {
            "options": [
                [0.00, 0.70, 0.50, 0.70],
                [1.00, 0.00, 0.50, 0.70],
                [0.60, 0.90, 1.00, 0.80],
            ],
            "chosen_idx": 1,
        },
        {
            "options": [
                [0.40, 0.40, 0.50, 0.90],
                [0.00, 0.80, 0.50, 0.70],
                [0.30, 1.00, 0.00, 0.30],
            ],
            "chosen_idx": 2,
        },
        {
            "options": [
                [0.30, 0.10, 1.00, 1.00],
                [0.40, 0.40, 1.00, 0.50],
                [0.30, 0.60, 0.50, 0.50],
            ],
            "chosen_idx": 2,
        },
    ]
    current_options = [
        [0.70, 0.90, 0.00, 0.60],
        [0.60, 0.80, 0.00, 1.00],
        [0.40, 0.00, 0.00, 1.00],
    ]
    examples.append((features, rounds_history, current_options, 0))

    # Example 4
    features = ['departure_time', 'duration', 'number_of_stops', 'price']
    rounds_history = [
        {
            "options": [
                [0.70, 1.00, 0.00, 0.20],
                [0.30, 0.30, 1.00, 0.40],
                [0.30, 0.00, 1.00, 0.50],
            ],
            "chosen_idx": 0,
        },
        {
            "options": [
                [0.70, 0.40, 0.00, 0.80],
                [0.90, 0.90, 0.00, 0.50],
                [0.40, 0.40, 0.50, 0.80],
            ],
            "chosen_idx": 0,
        },
        {
            "options": [
                [0.10, 0.00, 1.00, 0.10],
                [0.20, 0.70, 0.50, 1.00],
                [0.10, 0.30, 0.50, 0.20],
            ],
            "chosen_idx": 2,
        },
        {
            "options": [
                [0.20, 0.20, 0.00, 0.20],
                [0.90, 0.00, 0.00, 0.60],
                [0.80, 0.90, 1.00, 1.00],
            ],
            "chosen_idx": 0,
        },
    ]
    current_options = [
        [0.20, 0.70, 1.00, 0.00],
        [0.00, 0.70, 0.00, 0.20],
        [0.20, 0.60, 1.00, 0.40],
    ]
    examples.append((features, rounds_history, current_options, 1))

    # Example 5
    features = ['departure_time', 'duration', 'number_of_stops', 'price']
    rounds_history = [
        {
            "options": [
                [0.60, 1.00, 0.50, 0.60],
                [0.50, 0.00, 1.00, 0.10],
                [0.00, 0.40, 0.00, 0.00],
            ],
            "chosen_idx": 0,
        },
        {
            "options": [
                [0.20, 0.50, 0.50, 1.00],
                [0.80, 0.40, 1.00, 0.50],
                [0.90, 0.00, 0.50, 0.80],
            ],
            "chosen_idx": 0,
        },
        {
            "options": [
                [0.20, 0.10, 0.50, 0.70],
                [0.20, 0.20, 1.00, 0.00],
                [1.00, 0.20, 0.50, 0.10],
            ],
            "chosen_idx": 0,
        },
        {
            "options": [
                [0.30, 0.90, 0.00, 0.40],
                [0.40, 1.00, 0.00, 0.70],
                [0.70, 0.40, 1.00, 0.20],
            ],
            "chosen_idx": 1,
        },
    ]
    current_options = [
        [0.70, 0.40, 0.50, 0.40],
        [0.40, 0.80, 0.50, 0.20],
        [0.30, 0.40, 0.00, 1.00],
    ]
    examples.append((features, rounds_history, current_options, 2))

    for i, (features, rounds_history, current_options, expected) in enumerate(examples, 1):
        pred = solve(features, rounds_history, current_options)
        print(f"Example {i}: recommended Option {pred} (expected Option {expected})")


if __name__ == "__main__":
    run_examples()