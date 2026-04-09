def solve(context: str, graph: str, query: str) -> float:
    import re
    from collections import defaultdict
    from itertools import product

    # Parse the context to extract probabilities
    cpt = defaultdict(dict)
    for line in context.strip().split('.'):
        line = line.strip()
        if not line:
            continue
        # Match the pattern for conditional probabilities
        match = re.match(r'If (.+?), then (.+?) with probability of ([\d.]+)%', line)
        if match:
            condition, outcome, prob = match.groups()
            prob = float(prob) / 100.0
            condition_vars = condition.split(' and ')
            outcome_var = outcome.split()[0]
            # Store the probabilities in the CPT
            cpt[outcome_var][tuple(condition_vars)] = prob
        else:
            # Match the pattern for unconditional probabilities
            match = re.match(r'(.+?) is (true|false) with probability of ([\d.]+)%', line)
            if match:
                var, state, prob = match.groups()
                prob = float(prob) / 100.0
                cpt[var][()] = prob if state == 'true' else 1 - prob

    # Parse the graph to extract the structure
    edges = graph.split('|')
    parents = defaultdict(list)
    for edge in edges:
        edge = edge.strip()
        if '->' in edge:
            parent, child = edge.split('->')
            parent = parent.strip()[1:-1].split(',') if parent.strip() else []
            child = child.strip()
            parents[child].extend(parent)

    # Parse the query
    query_match = re.match(r'What is the probability that (.+?) given that (.+?)\?', query)
    if query_match:
        query_vars, evidence_str = query_match.groups()
        evidence = {}
        for ev in evidence_str.split(' and '):
            var, state = ev.split(' is ')
            evidence[var.strip()] = state.strip() == 'true'
    else:
        query_match = re.match(r'What is the probability that (.+?)\?', query)
        query_vars = query_match.group(1)
        evidence = {}

    query_vars = query_vars.split(' and ')
    
    # Function to compute the joint probability
    def joint_probability(evidence):
        # Create a list of all variable combinations
        all_vars = list(cpt.keys())
        all_combinations = product([True, False], repeat=len(all_vars))
        total_prob = 0.0
        
        for combination in all_combinations:
            assignment = dict(zip(all_vars, combination))
            # Check if the assignment satisfies the evidence
            if all(assignment.get(var) == value for var, value in evidence.items()):
                prob = 1.0
                for var in all_vars:
                    if var in parents:
                        parent_values = tuple(assignment[parent] for parent in parents[var])
                        prob *= cpt[var].get(parent_values, 0)
                    else:
                        prob *= cpt[var][()]
                total_prob += prob
        return total_prob

    # Calculate the probability of the query given the evidence
    evidence_combination = {var: value for var, value in evidence.items() if var in cpt}
    
    # Calculate P(query | evidence)
    joint_query_evidence = joint_probability({**evidence_combination, **{var: True for var in query_vars}})
    joint_evidence = joint_probability(evidence_combination)
    
    if joint_evidence == 0:
        return 0.0  # Avoid division by zero
    return joint_query_evidence / joint_evidence

# Test the function with the provided examples
if __name__ == "__main__":
    examples = [
        {
            "context": """If n1 is False, then n0 is True with probability of 96%. If n1 is False, then n0 is False with probability of 4%. If n1 is True, then n0 is True with probability of 76%. If n1 is True, then n0 is False with probability of 24%. n1 is true with probability of 11%. n1 is false with probability of 89%. """,
            "graph": "('n1',) -> n0 | () -> n1",
            "query": "What is the probability that n1 is False given that n0 is False?"
        },
        {
            "context": """n0 is true with probability of 32%. n0 is false with probability of 68%. If n0 is False, then n1 is True with probability of 69%. If n0 is False, then n1 is False with probability of 31%. If n0 is True, then n1 is True with probability of 98%. If n0 is True, then n1 is False with probability of 2%. If n0 is False, then n2 is True with probability of 70%. If n0 is False, then n2 is False with probability of 30%. If n0 is True, then n2 is True with probability of 97%. If n0 is True, then n2 is False with probability of 3%. """,
            "graph": "() -> n0 | ('n0',) -> n1 | ('n0',) -> n2",
            "query": "What is the probability that n1 is False given that n0 is False and n2 is True?"
        },
        {
            "context": """If n2 is False, then n0 is True with probability of 89%. If n2 is False, then n0 is False with probability of 11%. If n2 is True, then n0 is True with probability of 43%. If n2 is True, then n0 is False with probability of 57%. If n0 is False, then n1 is True with probability of 1%. If n0 is False, then n1 is False with probability of 99%. If n0 is True, then n1 is True with probability of 91%. If n0 is True, then n1 is False with probability of 9%. If n3 is False, then n2 is True with probability of 6%. If n3 is False, then n2 is False with probability of 94%. If n3 is True, then n2 is True with probability of 68%. If n3 is True, then n2 is False with probability of 32%. n3 is true with probability of 19%. n3 is false with probability of 81%. """,
            "graph": "('n2',) -> n0 | ('n0',) -> n1 | ('n3',) -> n2 | () -> n3",
            "query": "What is the probability that n1 is False and n2 is False given that n0 is False?"
        },
        {
            "context": """If n4 is False, then n0 is True with probability of 98%. If n4 is False, then n0 is False with probability of 2%. If n4 is True, then n0 is True with probability of 54%. If n4 is True, then n0 is False with probability of 46%. If n0 is False, then n1 is True with probability of 17%. If n0 is False, then n1 is False with probability of 83%. If n0 is True, then n1 is True with probability of 96%. If n0 is True, then n1 is False with probability of 4%. If n0 is False, then n2 is True with probability of 9%. If n0 is False, then n2 is False with probability of 91%. If n0 is True, then n2 is True with probability of 96%. If n0 is True, then n2 is False with probability of 4%. n3 is true with probability of 68%. n3 is false with probability of 32%. If n3 is False, then n4 is True with probability of 28%. If n3 is False, then n4 is False with probability of 72%. If n3 is True, then n4 is True with probability of 51%. If n3 is True, then n4 is False with probability of 49%. """,
            "graph": "('n4',) -> n0 | ('n0',) -> n1 | ('n0',) -> n2 | () -> n3 | ('n3',) -> n4",
            "query": "What is the probability that n1 is False given that n2 is True?"
        },
        {
            "context": """If n2 is False, then n0 is True with probability of 1%. If n2 is False, then n0 is False with probability of 99%. If n2 is True, then n0 is True with probability of 57%. If n2 is True, then n0 is False with probability of 43%. If n0 is False, then n1 is True with probability of 55%. If n0 is False, then n1 is False with probability of 45%. If n0 is True, then n1 is True with probability of 36%. If n0 is True, then n1 is False with probability of 64%. n2 is true with probability of 48%. n2 is false with probability of 52%. If n5 is False, then n3 is True with probability of 15%. If n5 is False, then n3 is False with probability of 85%. If n5 is True, then n3 is True with probability of 19%. If n5 is True, then n3 is False with probability of 81%. If n5 is False, then n4 is True with probability of 18%. If n5 is False, then n4 is False with probability of 82%. If n5 is True, then n4 is True with probability of 11%. If n5 is True, then n4 is False with probability of 89%. If n2 is False, then n5 is True with probability of 13%. If n2 is False, then n5 is False with probability of 87%. If n2 is True, then n5 is True with probability of 67%. If n2 is True, then n5 is False with probability of 33%. """,
            "graph": "('n2',) -> n0 | ('n0',) -> n1 | () -> n2 | ('n5',) -> n3 | ('n5',) -> n4 | ('n2',) -> n5",
            "query": "What is the probability that n4 is True given that n1 is False and n3 is False?"
        }
    ]

    for example in examples:
        result = solve(example['context'], example['graph'], example['query'])
        print(result)