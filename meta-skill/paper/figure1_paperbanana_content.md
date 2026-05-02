We propose a compile-once probabilistic reasoning pipeline for LLMs.
The figure should show only the solution pipeline, not the diagnostic PCD panel.

The pipeline begins with a small set of task-family examples. An LLM inductor
reads these examples, recognizes the inference family, and emits a declarative
TaskSpec rather than executable code. The TaskSpec records the inference family,
state structure, observation model, and decision rule.

A deterministic compiler lowers the TaskSpec into a solver implemented with
typed probabilistic operations, built-in macros, or core-op-backed routes.
A two-gate deploy check validates that the compiled solver executes and matches
available validation samples. Once validated, the solver can be persisted in a
reusable registry and reused for later tasks from the same family. At test time,
subsequent instances are solved by the deterministic backend with no LLM calls.

Important visual constraints:
- Do not include a PCD Diagnosis panel.
- Do not include a compute bottleneck panel.
- Do not write "THREE-GATE" or "3-Gate" anywhere.
- Use "Two-Gate Check" only.
- Do not claim open-ended 100% natural-language accuracy.
- Include a small scope note: backend exactness is conditional on a valid
  TaskSpec; natural-language E2E is reported separately.
- Use a clean NeurIPS-style academic diagram: white background, wide horizontal
  flow, rounded pastel boxes, minimal text, crisp readable labels.
