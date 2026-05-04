# Ultrareview bundle for full NeurIPS paper review

This pull request is a review-only bundle for Claude `/ultrareview <PR#>`.
It is intentionally not a small patch review. The goal is to review the full current submission package for:

- NeurIPS-level contribution and positioning.
- Claim strength versus evidence.
- Abstract/title/intro coherence.
- Figure/table/caption clarity.
- Experimental fairness and possible reviewer objections.
- Citation and related-work coverage.
- Checklist, anonymity, reproducibility, and desk-reject risks.

Primary review targets:

- `paper/main_pdf_text.txt`: text extracted from the compiled 26-page PDF.
- `paper/main.tex`: current LaTeX source.
- `paper/references.bib`: bibliography used by the paper.
- `paper/checklist.tex`: NeurIPS checklist answers.
- `artifact/anonymous_artifact_README.md`: supplementary artifact overview.
- `artifact/anonymous_code_README.md`: anonymous code README.
- `artifact/RESULTS_MANIFEST.md`: curated experiment-result manifest.
- `artifact/anonymous_code_zip_listing.txt`: file listing of the anonymous supplement ZIP.
- `artifact/ANONYMIZATION.md`: anonymity notes for the supplement.

The actual current submission files in the source repository are:

- PDF: `meta-skill/paper/main.pdf`
- Supplement ZIP: `meta-skill/anonymous-code.zip`

Important review framing:

- The paper claims an end-to-end LLM-to-solver pipeline, not unconditional formal exactness over arbitrary raw natural language.
- Exactness is attributed to accepted compiled solvers over finite discrete task specifications.
- Natural-language routing, parsing, grounding, and TaskSpec induction are empirical components and are evaluated separately.
- Do not review this PR as a code-change patch; review it as the current full paper/submission snapshot.
