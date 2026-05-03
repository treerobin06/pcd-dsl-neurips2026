# External Dataset Table Plan, 2026-05-03

## Goal

Build one reviewer-facing external-evidence table that makes VSI look broad
without diluting the main story. The table should emphasize the same mechanism:
LLMs can parse or specify probabilistic structure, but direct computation and
per-instance code generation are unreliable or expensive; VSI amortizes a
validated solver route.

## Recommended Paper Shape

Use a compact main-text row or paragraph for QUITE, then put the larger matrix in
the appendix.

Main-paper message:

> On an external QUITE registered-network hard-compute split, VSI reaches
> 25/25 within 0.05 with GPT-4o-mini, while direct answering reaches 8/25 and
> PAL reaches 5/25; even GPT-5.4 PAL reaches 21/25 but costs 300x more than
> VSI with GPT-4o-mini on this smoke split.

Appendix table columns:

| Dataset / family | Setting | LLM role in VSI | Direct 4o-mini | PAL 4o-mini | Direct 5.4 | PAL 5.4 | VSI 4o-mini | Time / cost note | Use |
|---|---|---|---:|---:|---:|---:|---:|---|---|

Keep "Use" explicit: Main / Appendix / Boundary / Related work only.

## Candidate Dataset Matrix

| Candidate | Local status | Fit to VSI claim | Current evidence | Recommendation |
|---|---|---|---|---|
| Flight preference | Done | Core natural-language preference interface | Flight E2E 74.3%, oracle 74.4% | Main table already |
| Hotel preference | Done | Same preference family, different domain | Hotel E2E 77.4%, solver agreement 96.0% | Main single-family table |
| TextBandit-style | Done | Bandit update / Bayesian posterior update | 96.0% E2E | Main single-family table |
| BLInD | Done | Synthetic BN depth stress; compute bottleneck | Backend 900/900; PCD depth collapse | Main diagnostic/backend |
| bnlearn | Done | External real BN backend stress | Backend 400/400; registered E2E 79/80 strict | Main/appendix |
| NB/HMM adversarial | Done | Untemplated no-macro style families | 90.8% / 97.6% pooled | Main held-out table |
| QUITE registered hard-compute | Done smoke | Best new external evidence: parse simple, compute hard | Clean 25-query split matrix complete | Add appendix table; optionally one main paragraph |
| QUITE larger registered split | Not run | Stronger version of same claim | Need all-network smoke; likely cheap for VSI | NICE: run VSI-only or direct-mini sampled smoke |
| QUITE raw-premise compile | Exploratory only | Too much premise parsing noise; less clean | 5.4 raw compile 82.2% full-ish, hard split 55.6% | Appendix only if needed; not main |
| DeLLMa | Done negative pilot | Different problem: distribution estimation from sparse context, not exact discrete inference | Direct 40%; compile near random | Boundary paragraph only, not big table |
| LLM-BI | Downloaded | Related work / code, no benchmark-style dataset found locally | `llm_pymc.py` + paper PDF only | Related work only unless we manually create tasks |
| DisCIPL/self-steering | Downloaded | Not probabilistic posterior inference; steering/control target | Code/evals exist, task mismatch | Related work only |

## Immediate Smoke Queue

Do these only after explicit approval, because they use API.

### S1. QUITE registered all-network VSI smoke

- Purpose: see whether the clean 25-query result scales beyond hand-picked hard
  networks without running expensive baselines.
- System: `run_quite_registered_e2e.py` extended with an `all` preset.
- Model: GPT-4o-mini only.
- Size: 30 QUITE networks, one or a few finite queries per network first.
- Estimated cost: usually under $0.05 for VSI query parsing, because premises are
  not repeated.
- Success gate: >90% within 0.05, with failures attributable to query parsing or
  Problog semantics rather than backend computation.

### S2. QUITE registered hard-compute clean, larger baseline sample

- Purpose: make the direct/PAL comparison less "25 examples only".
- System: same hard-compute-clean networks, expand from 25 to 50 or 75 queries if
  enough clean finite queries are available.
- Models:
  - Direct: GPT-4o-mini and GPT-5.4.
  - PAL: GPT-4o-mini first; GPT-5.4 only if mini result is still clearly bad.
- Estimated cost:
  - Direct 4o-mini, 75 queries: ~$0.08.
  - Direct 5.4, 75 queries: ~$0.65.
  - PAL 4o-mini, 75 queries: ~$0.13 and 7-10 minutes.
  - PAL 5.4, 75 queries: ~$2.50 and 7-10 minutes.
- Success gate: VSI remains near exact; direct remains substantially lower; PAL
  either lower or much more expensive.

### S3. QUITE raw-premise compile sanity

- Purpose: decide whether raw natural-language premise induction is worth
  mentioning.
- Status: current exploratory results are mixed; this is not the cleanest story.
- Recommendation: defer unless reviewers explicitly demand open-ended premise
  induction. It risks distracting from the registered-solver claim.

## Proposed Appendix Table Draft

| Dataset / split | n | Direct 4o-mini | PAL 4o-mini | Direct 5.4 | PAL 5.4 | VSI 4o-mini | Notes |
|---|---:|---:|---:|---:|---:|---:|---|
| NB adversarial NL | 600 | 23.3% structured direct | -- | -- | -- | 90.8% | Pooled over five seeds |
| HMM adversarial NL | 500 | 40.0% structured direct | -- | -- | -- | 97.6% | Pooled over five seeds |
| bnlearn real BNs | 400 | -- | 17.5% stress | -- | 23.3% stress | 100.0% backend | Finite-query backend check |
| QUITE hard-compute clean | 25 | 32.0% | 20.0% | 56.0% | 84.0% | 100.0% | External registered BN split |

The QUITE row should include time/cost either in a second appendix table or in a
footnote:

- VSI 4o-mini: 5.3s, $0.0026
- Direct 4o-mini: 7.4s, $0.0271
- PAL 4o-mini: 140.4s, $0.0428
- Direct 5.4: 9.5s, $0.2129
- PAL 5.4: 129.6s, $0.8389

## Decision

Yes, add QUITE. Do not adapt every related repository. The best next move is a
controlled QUITE expansion, then a single external-evidence appendix table. LLM-BI
and DisCIPL should strengthen related work, not experiments. DeLLMa should remain
a boundary result unless the paper needs an explicit "not all decision tasks are
finite discrete inference" paragraph.
