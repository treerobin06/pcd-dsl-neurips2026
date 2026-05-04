You are extracting structured data from natural language hotel descriptions for a preference learning task.

A user is choosing hotels across multiple rounds. Each hotel is described in natural language with 4 features: distance to downtown, price, star rating, and amenities.

Your task: extract the raw numeric value for each feature from each hotel description.

**Extraction rules:**
- distance_miles: numeric miles from "distance to downtown" (e.g., "3 miles" -> 3)
- price: integer dollars without $ sign (e.g., "$550" -> 550)
- rating_stars: integer star rating (e.g., "4 stars" -> 4)
- amenities_count: count the listed amenities. The possible amenities are free parking, free breakfast, pool, and gym. Count only amenities explicitly listed.

Here are {n_rounds} rounds of hotel options. In rounds 1-{n_history}, the user's choice is marked.

{rounds_block}

Output a JSON object with EXACTLY this format:
```json
{{
  "rounds": [
    {{
      "options": [
        {{"distance_miles": <float>, "price": <int>, "rating_stars": <int>, "amenities_count": <int>}},
        ...
      ]
    }},
    ...
  ]
}}
```

**Output ONLY the JSON inside a ```json``` block. No explanation.**
