You are extracting structured data from natural language flight descriptions for a preference learning task.

A user is choosing flights across multiple rounds. Each flight is described in natural language with 4 features: departure time, duration, number of stops, and price.

Your task: extract the raw numeric value for each feature from each flight description.

**Extraction rules:**
- departure_hour: convert to 24-hour decimal (e.g., "02:00 PM" → 14.0, "10:48 AM" → 10.8)
- duration_min: convert to total minutes (e.g., "4 hr 24 min" → 264, "30 min" → 30, "20 hr" → 1200)
- stops: integer (e.g., "0" → 0, "1" → 1, "2" → 2)
- price: integer dollars without $ sign (e.g., "$370" → 370, "$1000" → 1000)

Here are {n_rounds} rounds of flight options. In rounds 1-{n_history}, the user's choice is marked.

{rounds_block}

Output a JSON object with EXACTLY this format:
```json
{{
  "rounds": [
    {{
      "options": [
        {{"departure_hour": <float>, "duration_min": <int>, "stops": <int>, "price": <int>}},
        ...
      ]
    }},
    ...
  ]
}}
```

**Output ONLY the JSON inside a ```json``` block. No explanation.**