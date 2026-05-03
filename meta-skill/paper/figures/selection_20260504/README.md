# Figure selection notes (2026-05-04)

This folder collects the Figure 1 and Figure 3 candidates generated during the VSI figure redesign pass.

## Contact sheets

- `figure1_shortlist_contact.png`: six Figure 1 candidates worth comparing.
- `figure3_shortlist_contact.png`: seven Figure 3 candidates worth comparing.
- `figure1_all_contact.png`: all collected Figure 1-like source images.
- `figure3_all_contact.png`: all collected Figure 3-like method images.

## Figure 1 shortlist

| File | Verdict | Notes |
|---|---:|---|
| `figure1/shortlist/00_current_original.png` | 8/10 | Clearest and safest current overview. Slightly less modern, but the story is stable and the three levels read well. |
| `figure1/shortlist/01_styleA_three_lane.png` | 8/10 | Strong modern replacement candidate. Clear registry lookup, hit/miss, and full-width registry. A little more mechanical than original. |
| `figure1/shortlist/02_styleD2_balanced_registry.png` | 8.5/10 | Best generated Figure 1 candidate visually. It fixes the lower-left emptiness and makes registry reuse clear. Slight risk: generated text/details should be checked closely before final use. |
| `figure1/shortlist/03_styleB_registry_hub.png` | 7/10 | Nice central registry idea, but the figure becomes more like a lifecycle diagram and loses the crisp three-level paper structure. |
| `figure1/shortlist/04_styleC_hero_stream.png` | 6.5/10 | More visual/hero-like, but the right side dominates and it feels less like a precise NeurIPS method overview. |
| `figure1/shortlist/05_prior_lane_candidate_b.png` | 7/10 | Clean lane idea, but it duplicates Figure 3 too much and has less balanced spacing than D2. |

**Recommendation for Figure 1:** keep `00_current_original` as the main-text figure. It is not the flashiest candidate, but it is the least likely to be misread: Figure 1 should explain the full routed system and registry, while Figure 3 explains VSI's internal route assembly. `02_styleD2_balanced_registry` remains the best modern backup, but its dense labels and `evidence signature` wording are easier to overinterpret.

## Figure 3 shortlist

| File | Verdict | Notes |
|---|---:|---|
| `figure3/shortlist/00_three_panel_candidate_b.png` | 8/10 | Best conservative fallback. Strong outer three-panel structure and readable. Needs caption wording that the route is an example, not a universal fixed sequence. |
| `figure3/shortlist/01_style1_clean_schematic.png` | 7.5/10 | Similar to candidate B, slightly more polished but the bottom legend adds clutter. |
| `figure3/shortlist/02_style2_assembly_canvas.png` | 7/10 | Good visual metaphor for route assembly, but too much empty space in the compiled PDF. |
| `figure3/shortlist/03_compact_assembly_current_bad_semantics.png` | 5/10 | Do not use. It looks compact, but it implies the seven operations form a fixed ordered pipeline, which is not our method. |
| `figure3/shortlist/04_flexible_route_graph.png` | 7/10 | Semantically better: route graph plus unordered palette. But without large outer panels it feels less organized. |
| `figure3/shortlist/05_three_panel_unordered_palette.png` | 8/10 | Best semantic candidate: keeps the three big NeurIPS-style panels and shows an unordered primitive palette plus a chosen route graph. Slightly less visually elegant than candidate B. |
| `figure3/shortlist/06_paperbanana_method_architecture.png` | 6/10 | Clear but slide-like and too literal. Useful as a content reference, not final paper art. |

**Recommendation for Figure 3:** use `05_three_panel_unordered_palette`. It is the best content match because it shows a chosen route graph above an unordered typed primitive palette, so reviewers are less likely to think the seven operations are a fixed hand-written pipeline. `00_three_panel_candidate_b` is the polished backup, but it needs a careful caption because its route row looks more sequential.

## Current paper state

After the final crop/scale pass, `main.tex` points to:

- Figure 1: `figures/figure1_overview_no_title_no_footer.png`
- Figure 3: `figures/figure3_vsi_unordered_palette_y90.png`

The older compact Figure 3 target is not recommended because it can be read as a fixed operation pipeline.

Final exported copies for manual inspection are in `figures/final_20260504/`:

- `figure1_final.png`
- `figure3_final.png`
