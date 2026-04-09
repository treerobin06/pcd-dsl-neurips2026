You are analyzing a Bayesian Network inference problem.

**Network Description:**
{context}

**Network Structure:**
{graph}

**Query:**
{query}

Extract the structured information. Output a JSON object:
```json
{{
  "variables": ["var1", "var2", ...],
  "edges": [["parent", "child"], ...],
  "cpts": {{
    "variable_name": {{
      "parents": ["p1", "p2"],
      "rows": [
        {{"parent_values": {{"p1": "True", "p2": "False"}}, "prob_true": 0.39, "prob_false": 0.61}},
        ...
      ]
    }}
  }},
  "query_variable": "var",
  "query_value": "True or False",
  "evidence": {{"var": "value", ...}}
}}
```

For root nodes (no parents), use `"parents": []` and a single row with `"parent_values": {{}}`.

**Output ONLY the JSON inside a ```json``` block. No explanation.**
