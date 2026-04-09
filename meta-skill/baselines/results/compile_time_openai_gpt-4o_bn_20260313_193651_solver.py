import re
from collections import defaultdict
from itertools import product

def parse_context(context):
    cpt = defaultdict(dict)
    prior_probs = {}
    
    # Extract prior probabilities
    prior_pattern = re.compile(r"(\w+) is (true|false) with probability of (\d+)%")
    for match in prior_pattern.finditer(context):
        var, val, prob = match.groups()
        prob = float(prob) / 100
        prior_probs[var] = prob if val == 'true' else 1 - prob
    
    # Extract conditional probabilities
    cond_pattern = re.compile(r"If (.+) then (\w+) is (true|false) with probability of (\d+)%")
    for match in cond_pattern.finditer(context):
        conditions, var, val, prob = match.groups()
        prob = float(prob) / 100
        conditions = tuple(sorted((cond.split()[0], cond.split()[2] == 'true') for cond in conditions.split(', ')))
        cpt[var][conditions] = prob if val == 'true' else 1 - prob
    
    return cpt, prior_probs

def parse_graph(graph):
    dag = defaultdict(list)
    for edge in graph.split(' | '):
        parents, child = edge.split(' -> ')
        parents = eval(parents)
        dag[child].extend(parents)
    return dag

def parse_query(query):
    query_pattern = re.compile(r"What is the probability that (.+) given that (.+)\?")
    match = query_pattern.match(query)
    if match:
        query_vars, evidence = match.groups()
        query_vars = tuple(sorted((var.split()[0], var.split()[2] == 'true') for var in query_vars.split(' and ')))
        evidence = tuple(sorted((var.split()[0], var.split()[2] == 'true') for var in evidence.split(' and ')))
    else:
        query_vars = tuple(sorted((var.split()[0], var.split()[2] == 'true') for var in query.split(' and ')))
        evidence = ()
    return query_vars, evidence

def variable_elimination(cpt, prior_probs, dag, query_vars, evidence):
    all_vars = set(dag.keys()).union(*dag.values())
    hidden_vars = all_vars - {var for var, _ in query_vars} - {var for var, _ in evidence}
    
    def joint_prob(assignment):
        prob = 1.0
        for var, val in assignment.items():
            if var in prior_probs:
                prob *= prior_probs[var] if val else 1 - prior_probs[var]
            else:
                parents = tuple((p, assignment[p]) for p in dag[var])
                prob *= cpt[var][parents] if val else 1 - cpt[var][parents]
        return prob
    
    def sum_out(var, factors):
        new_factors = []
        for factor in factors:
            if var in factor:
                new_factor = defaultdict(float)
                for assignment in factor:
                    new_assignment = tuple((v, val) for v, val in assignment if v != var)
                    new_factor[new_assignment] += factor[assignment]
                new_factors.append(new_factor)
            else:
                new_factors.append(factor)
        return new_factors
    
    factors = []
    for var in all_vars:
        if var in prior_probs:
            factors.append({((var, True),): prior_probs[var], ((var, False),): 1 - prior_probs[var]})
        else:
            for parents, prob in cpt[var].items():
                factor = {}
                for parent_vals in product([True, False], repeat=len(parents)):
                    assignment = tuple(sorted(parents + ((var, True),)))
                    factor[assignment] = prob if all(val for _, val in parent_vals) else 1 - prob
                factors.append(factor)
    
    for var in hidden_vars:
        factors = sum_out(var, factors)
    
    final_factor = factors[0]
    for factor in factors[1:]:
        new_factor = defaultdict(float)
        for assignment1 in final_factor:
            for assignment2 in factor:
                if all(v1 == v2 and val1 == val2 for (v1, val1), (v2, val2) in zip(assignment1, assignment2) if v1 == v2):
                    new_assignment = tuple(sorted(set(assignment1).union(assignment2)))
                    new_factor[new_assignment] += final_factor[assignment1] * factor[assignment2]
        final_factor = new_factor
    
    query_prob = 0.0
    evidence_prob = 0.0
    for assignment, prob in final_factor.items():
        if all(assignment.get(var) == val for var, val in query_vars):
            if all(assignment.get(var) == val for var, val in evidence):
                query_prob += prob
        if all(assignment.get(var) == val for var, val in evidence):
            evidence_prob += prob
    
    return query_prob / evidence_prob if evidence_prob > 0 else 0.0

def solve(context: str, graph: str, query: str) -> float:
    cpt, prior_probs = parse_context(context)
    dag = parse_graph(graph)
    query_vars, evidence = parse_query(query)
    return variable_elimination(cpt, prior_probs, dag, query_vars, evidence)

# Test the function with the provided examples
examples = [
    (
        """If n1 is False, then n0 is True with probability of 96%. If n1 is False, then n0 is False with probability of 4%. If n1 is True, then n0 is True with probability of 76%. If n1 is True, then n0 is False with probability of 24%. n1 is true with probability of 11%. n1 is false with probability of 89%.""",
        "('n1',) -> n0 | () -> n1",
        "What is the probability that n1 is False given that n0 is False?"
    ),
    (
        """n0 is true with probability of 32%. n0 is false with probability of 68%. If n0 is False, then n1 is True with probability of 69%. If n0 is False, then n1 is False with probability of 31%. If n0 is True, then n1 is True with probability of 98%. If n0 is True, then n1 is False with probability of 2%. If n0 is False, then n2 is True with probability of 70%. If n0 is False, then n2 is False with probability of 30%. If n0 is True, then n2 is True with probability of 97%. If n0 is True, then n2 is False with probability of 3%.""",
        "() -> n0 | ('n0',) -> n1 | ('n0',) -> n2",
        "What is the probability that n1 is False given that n0 is False and n2 is True?"
    ),
    (
        """If n2 is False, then n0 is True with probability of 89%. If n2 is False, then n0 is False with probability of 11%. If n2 is True, then n0 is True with probability of 43%. If n2 is True, then n0 is False with probability of 57%. If n0 is False, then n1 is True with probability of 1%. If n0 is False, then n1 is False with probability of 99%. If n0 is True, then n1 is True with probability of 91%. If n0 is True, then n1 is False with probability of 9%. If n3 is False, then n2 is True with probability of 6%. If n3 is False, then n2 is False with probability of 94%. If n3 is True, then n2 is True with probability of 68%. If n3 is True, then n2 is False with probability of 32%. n3 is true with probability of 19%. n3 is false with probability of 81%.""",
        "('n2',) -> n0 | ('n0',) -> n1 | ('n3',) -> n2 | () -> n3",
        "What is the probability that n1 is False and n2 is False given that n0 is False?"
    ),
    (
        """If n4 is False, then n0 is True with probability of 98%. If n4 is False, then n0 is False with probability of 2%. If n4 is True, then n0 is True with probability of 54%. If n4 is True, then n0 is False with probability of 46%. If n0 is False, then n1 is True with probability of 17%. If n0 is False, then n1 is False with probability of 83%. If n0 is True, then n1 is True with probability of 96%. If n0 is True, then n1 is False with probability of 4%. If n0 is False, then n2 is True with probability of 9%. If n0 is False, then n2 is False with probability of 91%. If n0 is True, then n2 is True with probability of 96%. If n0 is True, then n2 is False with probability of 4%. n3 is true with probability of 68%. n3 is false with probability of 32%. If n3 is False, then n4 is True with probability of 28%. If n3 is False, then n4 is False with probability of 72%. If n3 is True, then n4 is True with probability of 51%. If n3 is True, then n4 is False with probability of 49%.""",
        "('n4',) -> n0 | ('n0',) -> n1 | ('n0',) -> n2 | () -> n3 | ('n3',) -> n4",
        "What is the probability that n1 is False given that n2 is True?"
    ),
    (
        """If n2 is False, then n0 is True with probability of 1%. If n2 is False, then n0 is False with probability of 99%. If n2 is True, then n0 is True with probability of 57%. If n2 is True, then n0 is False with probability of 43%. If n0 is False, then n1 is True with probability of 55%. If n0 is False, then n1 is False with probability of 45%. If n0 is True, then n1 is True with probability of 36%. If n0 is True, then n1 is False with probability of 64%. n2 is true with probability of 48%. n2 is false with probability of 52%. If n5 is False, then n3 is True with probability of 15%. If n5 is False, then n3 is False with probability of 85%. If n5 is True, then n3 is True with probability of 19%. If n5 is True, then n3 is False with probability of 81%. If n5 is False, then n4 is True with probability of 18%. If n5 is False, then n4 is False with probability of 82%. If n5 is True, then n4 is True with probability of 11%. If n5 is True, then n4 is False with probability of 89%. If n2 is False, then n5 is True with probability of 13%. If n2 is False, then n5 is False with probability of 87%. If n2 is True, then n5 is True with probability of 67%. If n2 is True, then n5 is False with probability of 33%.""",
        "('n2',) -> n0 | ('n0',) -> n1 | () -> n2 | ('n5',) -> n3 | ('n5',) -> n4 | ('n2',) -> n5",
        "What is the probability that n4 is True given that n1 is False and n3 is False?"
    )
]

for context, graph, query in examples:
    print(solve(context, graph, query))