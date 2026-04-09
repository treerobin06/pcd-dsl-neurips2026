import re
import ast
import itertools

def solve(context: str, graph: str, query: str) -> float:
    def to_bool(s):
        s = s.strip().lower()
        if s == "true":
            return True
        if s == "false":
            return False
        raise ValueError(f"Invalid boolean value: {s}")

    def parse_prob(s):
        s = s.strip()
        if s.endswith("%"):
            return float(s[:-1]) / 100.0
        return float(s)

    def parse_graph(graph_str):
        parents = {}
        vars_seen = set()
        parts = [p.strip() for p in graph_str.split("|") if p.strip()]
        for part in parts:
            if "->" not in part:
                raise ValueError(f"Bad graph part: {part}")
            left, right = part.split("->", 1)
            left = left.strip()
            right = right.strip()
            child = right
            if not re.fullmatch(r"n\d+", child):
                raise ValueError(f"Bad graph part: {part}")
            try:
                plist = ast.literal_eval(left)
            except Exception:
                raise ValueError(f"Bad graph part: {part}")
            if isinstance(plist, str):
                plist = (plist,)
            plist = tuple(plist)
            parents[child] = plist
            vars_seen.add(child)
            for p in plist:
                vars_seen.add(p)
        for v in vars_seen:
            parents.setdefault(v, ())
        return parents

    def topo_sort(parents):
        remaining = set(parents.keys())
        done = set()
        order = []
        while remaining:
            progressed = False
            for v in list(remaining):
                if all(p in done for p in parents[v]):
                    order.append(v)
                    done.add(v)
                    remaining.remove(v)
                    progressed = True
            if not progressed:
                raise ValueError("Graph is not a DAG")
        return order

    def parse_context(context_str, parents):
        raw = context_str.strip()
        sentences = [s.strip() for s in re.split(r"\.\s*", raw) if s.strip()]

        cpts = {v: {} for v in parents}

        cond_pat = re.compile(
            r"^If\s+(.+?),\s*then\s+(n\d+)\s+is\s+(True|False)\s+with\s+probability\s+of\s+([0-9]*\.?[0-9]+%?)$",
            re.I
        )
        marg_pat = re.compile(
            r"^(n\d+)\s+is\s+(True|False)\s+with\s+probability\s+of\s+([0-9]*\.?[0-9]+%?)$",
            re.I
        )
        assign_pat = re.compile(r"^(n\d+)\s+is\s+(True|False)$", re.I)

        for sent in sentences:
            m = cond_pat.match(sent)
            if m:
                conds_text, var, val_text, prob_text = m.groups()
                val = to_bool(val_text)
                prob = parse_prob(prob_text)

                cond_map = {}
                cond_parts = re.split(r"\s+and\s+", conds_text.strip(), flags=re.I)
                for cp in cond_parts:
                    mm = assign_pat.match(cp.strip())
                    if not mm:
                        raise ValueError(f"Bad condition in context: {cp}")
                    pv, pval = mm.groups()
                    cond_map[pv] = to_bool(pval)

                key = tuple(cond_map[p] for p in parents[var])
                cpts[var].setdefault(key, {})[val] = prob
                continue

            m = marg_pat.match(sent)
            if m:
                var, val_text, prob_text = m.groups()
                val = to_bool(val_text)
                prob = parse_prob(prob_text)
                cpts[var].setdefault((), {})[val] = prob
                continue

            raise ValueError(f"Could not parse context sentence: {sent}")

        final_cpts = {}
        for var in parents:
            final_cpts[var] = {}
            entries = cpts[var]
            if not entries:
                raise ValueError(f"Missing CPT for variable {var}")
            for key, dist in entries.items():
                if True in dist and False in dist:
                    final_cpts[var][key] = {True: dist[True], False: dist[False]}
                elif True in dist:
                    final_cpts[var][key] = {True: dist[True], False: 1.0 - dist[True]}
                elif False in dist:
                    final_cpts[var][key] = {False: dist[False], True: 1.0 - dist[False]}
                else:
                    raise ValueError(f"Missing CPT distribution for {var} {key}")
        return final_cpts

    def parse_assignments(text):
        text = text.strip()
        if not text:
            return {}
        parts = re.split(r"\s+and\s+", text, flags=re.I)
        out = {}
        pat = re.compile(r"^(n\d+)\s+is\s+(True|False)$", re.I)
        for part in parts:
            m = pat.match(part.strip())
            if not m:
                raise ValueError(f"Bad assignment: {part}")
            var, val = m.groups()
            out[var] = to_bool(val)
        return out

    def parse_query(query_str):
        m = re.match(r"^What\s+is\s+the\s+probability\s+that\s+(.+?)\?$", query_str.strip(), re.I)
        if not m:
            raise ValueError(f"Bad query: {query_str}")
        body = m.group(1).strip()
        if re.search(r"\s+given\s+that\s+", body, flags=re.I):
            lhs, rhs = re.split(r"\s+given\s+that\s+", body, maxsplit=1, flags=re.I)
            return parse_assignments(lhs), parse_assignments(rhs)
        return parse_assignments(body), {}

    parents = parse_graph(graph)
    order = topo_sort(parents)
    cpts = parse_context(context, parents)
    query_assign, evidence = parse_query(query)

    for k, v in evidence.items():
        if k in query_assign and query_assign[k] != v:
            return 0.0

    def joint_probability(full_assignment):
        p = 1.0
        for var in order:
            key = tuple(full_assignment[parent] for parent in parents[var])
            p *= cpts[var][key][full_assignment[var]]
        return p

    all_vars = order

    def probability_of(partial_assignment):
        fixed = dict(partial_assignment)
        unspecified = [v for v in all_vars if v not in fixed]
        total = 0.0
        for vals in itertools.product([False, True], repeat=len(unspecified)):
            full = dict(fixed)
            for var, val in zip(unspecified, vals):
                full[var] = val
            total += joint_probability(full)
        return total

    numerator_assign = dict(evidence)
    numerator_assign.update(query_assign)

    numerator = probability_of(numerator_assign)
    denominator = probability_of(evidence) if evidence else 1.0

    if denominator == 0.0:
        raise ZeroDivisionError("Evidence has zero probability")

    return numerator / denominator


# Example 1
context1 = """If n1 is False, then n0 is True with probability of 96%. If n1 is False, then n0 is False with probability of 4%. If n1 is True, then n0 is True with probability of 76%. If n1 is True, then n0 is False with probability of 24%. n1 is true with probability of 11%. n1 is false with probability of 89%. """
graph1 = "('n1',) -> n0 | () -> n1"
query1 = "What is the probability that n1 is False given that n0 is False?"

# Example 2
context2 = """n0 is true with probability of 32%. n0 is false with probability of 68%. If n0 is False, then n1 is True with probability of 69%. If n0 is False, then n1 is False with probability of 31%. If n0 is True, then n1 is True with probability of 98%. If n0 is True, then n1 is False with probability of 2%. If n0 is False, then n2 is True with probability of 70%. If n0 is False, then n2 is False with probability of 30%. If n0 is True, then n2 is True with probability of 97%. If n0 is True, then n2 is False with probability of 3%. """
graph2 = "() -> n0 | ('n0',) -> n1 | ('n0',) -> n2"
query2 = "What is the probability that n1 is False given that n0 is False and n2 is True?"

# Example 3
context3 = """If n2 is False, then n0 is True with probability of 89%. If n2 is False, then n0 is False with probability of 11%. If n2 is True, then n0 is True with probability of 43%. If n2 is True, then n0 is False with probability of 57%. If n0 is False, then n1 is True with probability of 1%. If n0 is False, then n1 is False with probability of 99%. If n0 is True, then n1 is True with probability of 91%. If n0 is True, then n1 is False with probability of 9%. If n3 is False, then n2 is True with probability of 6%. If n3 is False, then n2 is False with probability of 94%. If n3 is True, then n2 is True with probability of 68%. If n3 is True, then n2 is False with probability of 32%. n3 is true with probability of 19%. n3 is false with probability of 81%. """
graph3 = "('n2',) -> n0 | ('n0',) -> n1 | ('n3',) -> n2 | () -> n3"
query3 = "What is the probability that n1 is False and n2 is False given that n0 is False?"

# Example 4
context4 = """If n4 is False, then n0 is True with probability of 98%. If n4 is False, then n0 is False with probability of 2%. If n4 is True, then n0 is True with probability of 54%. If n4 is True, then n0 is False with probability of 46%. If n0 is False, then n1 is True with probability of 17%. If n0 is False, then n1 is False with probability of 83%. If n0 is True, then n1 is True with probability of 96%. If n0 is True, then n1 is False with probability of 4%. If n0 is False, then n2 is True with probability of 9%. If n0 is False, then n2 is False with probability of 91%. If n0 is True, then n2 is True with probability of 96%. If n0 is True, then n2 is False with probability of 4%. n3 is true with probability of 68%. n3 is false with probability of 32%. If n3 is False, then n4 is True with probability of 28%. If n3 is False, then n4 is False with probability of 72%. If n3 is True, then n4 is True with probability of 51%. If n3 is True, then n4 is False with probability of 49%. """
graph4 = "('n4',) -> n0 | ('n0',) -> n1 | ('n0',) -> n2 | () -> n3 | ('n3',) -> n4"
query4 = "What is the probability that n1 is False given that n2 is True?"

# Example 5
context5 = """If n2 is False, then n0 is True with probability of 1%. If n2 is False, then n0 is False with probability of 99%. If n2 is True, then n0 is True with probability of 57%. If n2 is True, then n0 is False with probability of 43%. If n0 is False, then n1 is True with probability of 55%. If n0 is False, then n1 is False with probability of 45%. If n0 is True, then n1 is True with probability of 36%. If n0 is True, then n1 is False with probability of 64%. n2 is true with probability of 48%. n2 is false with probability of 52%. If n5 is False, then n3 is True with probability of 15%. If n5 is False, then n3 is False with probability of 85%. If n5 is True, then n3 is True with probability of 19%. If n5 is True, then n3 is False with probability of 81%. If n5 is False, then n4 is True with probability of 18%. If n5 is False, then n4 is False with probability of 82%. If n5 is True, then n4 is True with probability of 11%. If n5 is True, then n4 is False with probability of 89%. If n2 is False, then n5 is True with probability of 13%. If n2 is False, then n5 is False with probability of 87%. If n2 is True, then n5 is True with probability of 67%. If n2 is True, then n5 is False with probability of 33%. """
graph5 = "('n2',) -> n0 | ('n0',) -> n1 | () -> n2 | ('n5',) -> n3 | ('n5',) -> n4 | ('n2',) -> n5"
query5 = "What is the probability that n4 is True given that n1 is False and n3 is False?"

print(solve(context1, graph1, query1))
print(solve(context2, graph2, query2))
print(solve(context3, graph3, query3))
print(solve(context4, graph4, query4))
print(solve(context5, graph5, query5))