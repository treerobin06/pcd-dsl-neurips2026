# Anonymization and Curation Notes

Prepared on 2026-05-04 for anonymous review.

## Curation Policy

The public artifact is rebuilt from a whitelist rather than copied from the
working repository. It keeps code and result records needed to audit the current
paper, and omits files that are private, obsolete, or easy to misread as current
evidence.

## Removed From the Release

- `.env` files, API keys, proxy secrets, Overleaf remotes, and account-specific paths.
- Local caches and platform files: `.DS_Store`, `__pycache__`, `*.pyc`, virtual environments.
- Draft paper sources, Overleaf sync directories, generated PDFs, candidate figures, and image
  generation scratch outputs.
- Deprecated Gate-3 ablation files. The paper now uses a two-gate deploy check.
- Old mixed-stream sanity records with 100% results that are not reported in the paper.
- QUITE scaffold/debug runs and other failed or exploratory records that are not part of
  the current evidence chain.

## Included Result Groups

- PCD diagnostic summaries and details for preference learning and BLInD depth curves.
- Compile-time and PAL baselines used in the BLInD and bnlearn comparisons.
- Single-family Flight, Hotel, TextBandit-style natural-language E2E records.
- Five-seed adversarial Naive Bayes / HMM VSI E2E records and the paired direct baseline.
- Conservative mixed-stream E2E aggregate inputs.
- bnlearn 400-query deterministic backend check and 80-query registry-supported NL sanity.
- QUITE 75-query registered/direct/PAL comparison and the full-corpus direct context record.
- Minimal phase1 strategy-ablation summaries used by the appendix.

## Verification Performed

The release was checked for common secret and local-path patterns after rebuild.
The zip was created with macOS resource forks disabled and excludes cache/build files.
