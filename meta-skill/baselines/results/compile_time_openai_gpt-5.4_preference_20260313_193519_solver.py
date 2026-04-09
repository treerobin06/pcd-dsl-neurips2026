import math
import itertools


PREFERENCE_VALUES = [-1.0, -0.5, 0.0, 0.5, 1.0]
TEMPERATURE = 1.0


def dot(a, b):
    return sum(x * y for x, y in zip(a, b))


def softmax(values, temperature=1.0):
    scaled = [v / temperature for v in values]
    m = max(scaled)
    exps = [math.exp(v - m) for v in scaled]
    s = sum(exps)
    return [e / s for e in exps]


def solve(features, rounds_history, current_options) -> int:
    n_features = len(features)

    # Enumerate all possible weight hypotheses
    hypotheses = list(itertools.product(PREFERENCE_VALUES, repeat=n_features))

    # Uniform prior
    posterior = {w: 1.0 for w in hypotheses}

    # Bayesian posterior updates from observed choices
    for round_data in rounds_history:
        options = round_data["options"]
        chosen_idx = round_data["chosen_idx"]

        new_posterior = {}
        total = 0.0

        for w in hypotheses:
            utilities = [dot(w, option) for option in options]
            probs = softmax(utilities, temperature=TEMPERATURE)
            likelihood = probs[chosen_idx]
            updated = posterior[w] * likelihood
            new_posterior[w] = updated
            total += updated

        # Normalize
        if total == 0.0:
            # Fallback to uniform if numerical underflow somehow occurs
            uniform = 1.0 / len(hypotheses)
            posterior = {w: uniform for w in hypotheses}
        else:
            posterior = {w: new_posterior[w] / total for w in hypotheses}

    # Compute posterior expected utility for each current option
    expected_utilities = []
    for option in current_options:
        eu = 0.0
        for w in hypotheses:
            eu += posterior[w] * dot(w, option)
        expected_utilities.append(eu)

    best_idx = max(range(len(current_options)), key=lambda i: expected_utilities[i])
    return best_idx


if __name__ == "__main__":
    examples = [
        {
            "name": "Example 1",
            "features": ["departure_time", "duration", "number_of_stops", "price"],
            "rounds_history": [
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
            ],
            "current_options": [
                [0.40, 0.20, 0.00, 0.90],
                [0.40, 0.00, 0.00, 1.00],
                [0.70, 1.00, 0.50, 0.50],
            ],
            "correct": 2,
        },
        {
            "name": "Example 2",
            "features": ["departure_time", "duration", "number_of_stops", "price"],
            "rounds_history": [
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
            ],
            "current_options": [
                [0.60, 0.10, 0.00, 0.10],
                [0.70, 0.40, 0.00, 0.80],
                [0.40, 0.00, 0.50, 0.20],
            ],
            "correct": 2,
        },
        {
            "name": "Example 3",
            "features": ["departure_time", "duration", "number_of_stops", "price"],
            "rounds_history": [
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
            ],
            "current_options": [
                [0.70, 0.90, 0.00, 0.60],
                [0.60, 0.80, 0.00, 1.00],
                [0.40, 0.00, 0.00, 1.00],
            ],
            "correct": 0,
        },
        {
            "name": "Example 4",
            "features": ["departure_time", "duration", "number_of_stops", "price"],
            "rounds_history": [
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
            ],
            "current_options": [
                [0.20, 0.70, 1.00, 0.00],
                [0.00, 0.70, 0.00, 0.20],
                [0.20, 0.60, 1.00, 0.40],
            ],
            "correct": 1,
        },
        {
            "name": "Example 5",
            "features": ["departure_time", "duration", "number_of_stops", "price"],
            "rounds_history": [
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
            ],
            "current_options": [
                [0.70, 0.40, 0.50, 0.40],
                [0.40, 0.80, 0.50, 0.20],
                [0.30, 0.40, 0.00, 1.00],
            ],
            "correct": 2,
        },
    ]

    for ex in examples:
        pred = solve(ex["features"], ex["rounds_history"], ex["current_options"])
        print(f"{ex['name']}: recommended Option {pred} (correct: Option {ex['correct']})")