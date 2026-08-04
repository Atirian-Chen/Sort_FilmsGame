# Film Sort A/B review — 2026-08-05

Source: the Admin report for `2026-07-06` to `2026-08-04`. All rates below use de-duplicated sessions and the report's stated funnel definitions. This document does not treat assigned sessions as experiment exposure.

## Decision summary

All four v3.8 experiments ended at `2026-08-05T03:19:49+08:00`. Their chosen experience is now the product default. The first decision has sufficient strict-exposure volume for a directional product decision; the other three remain explicitly directional because one or both variants have fewer than 100 exposed sessions.

| Ended experiment | Strict-exposure result | Chosen direction | Confidence and reason |
|---|---:|---|---|
| `home_featured_quick_start_v1` | Control: 157/348 actions (45.1%); featured card: 112/328 (34.1%) | Keep the existing grid; do not pin one sci-fi list | Clear primary-metric loss from the additional featured block. Both variants exceed 100 exposures and 25 actions. |
| `heavy_default_start_v1` | Control: 37/140 starts (26.4%); recommended Top 10: 44/150 (29.3%) | Keep the “quickly rank Top 10” recommendation | +2.9 pp on the primary metric while preserving an editable configuration. The difference is directional, not a significance claim. |
| `sorting_scope_rescue_v1` | Control: 13/52 completions (25.0%); offer Top 10: 17/61 (27.9%) | Keep the progress-preserving Top 10 rescue | +2.9 pp completion direction; samples are below 100 per variant. |
| `result_share_bundle_v1` | Control: 12/87 share/poster sessions (13.8%); bundle: 9/56 (16.1%) | Keep the compact Top 10 poster + invitation bundle | +2.3 pp direction; samples are below 100 per variant. |

## Current diagnosis

| Funnel stage | Observed fact | Diagnosis | Product response in v3.10 |
|---|---:|---|---|
| Home activation | 2,287 rendered home sessions; 785 opened/selected a list (34.3%) | The largest absolute loss is before a list is opened. A pinned list hurt rather than helped, so reduce ambiguity without replacing user choice. | Test only the CTA wording inside existing built-in list cards. |
| Heavy configuration | 729 heavy-entry sessions; 213 starts (29.2%) | Imported/watch-history ranking still has a high setup cost. | Keep the Top 10 quick-start and test the default selected scope separately. |
| Started ranking | 270 starts; 49 completions (18.1%). In the heavy path, only 44/213 completed (20.7%). | Long ranking work remains the main downstream friction. | Keep the Top 10 rescue; test progress framing and a long-custom-list scope explanation. |
| Result distribution | 11/49 completion sessions copied or downloaded (22.4%) | The product creates a result but the sharing reason is still weak. | Keep the bundle and test the single primary CTA wording. |
| Measurement / acquisition | 2,963 of 2,971 legacy funnel visits were `direct / unknown` | The product report cannot yet attribute most traffic to an external channel or creative. This is a measurement gap, not evidence that a landing-page change fixes acquisition. | Keep external campaigns separately tracked; do not use raw visit volume to judge these product experiments. |

The v3.8 versus v3.6 version comparison is encouraging but non-causal: post-render action rose 11.0 pp, completion rose 0.8 pp, and share-user conversion rose 1.6 pp, while render completion fell 3.1 pp and P90 render time increased 232 ms. Version changes and traffic composition were not randomized, so these values are diagnostic only.

## v3.10 experiment cards

Each active experiment has 100% eligible traffic split 50/50 with stable session assignment. A strict result uses `experiment_exposed` sessions as its denominator. Do not declare a winner before **14 days**, **100 exposed sessions per variant**, and **25 primary-metric conversions per variant**. Below that threshold, label the result directional. After the threshold, adopt a variant only when it improves the primary metric by at least 3 pp without a guardrail falling by more than 3 pp; otherwise keep the control and document the result as inconclusive.

| ID and surface | Audience / job | Hypothesis and one changed variable | Primary metric | Guardrails |
|---|---|---|---|---|
| `home_card_cta_copy_v1` — Chinese home built-in cards | Visitors who want a ready-made list but have not chosen one | “先排 Top N” will make the card's bounded task clearer than “开始整理”. **Only the footer CTA text changes.** | `exposed_builtin_card_open_rate` | Start rate and completion rate after exposure do not fall by >3 pp. |
| `custom_list_scope_hint_v1` — Chinese custom setup, 20+ films | People pasting a long personal list who need to judge effort | A factual Top 10 versus full-ranking effort comparison will increase starts without forcing a scope. **Only the explanatory hint changes.** | `exposed_start_rate` | Completion rate; proportion choosing a full ranking remains observable through `top_k` on start events. |
| `douban_collect_scope_default_v1` — Chinese watched-history setup | People with an already loaded public Douban watched list | Defaulting a new configuration to Top 10 will reduce setup cost more than Top 20. **Only the initial N value changes; it remains editable.** | `exposed_start_rate` | Completion rate and top-k distribution. |
| `sorting_progress_framing_v1` — Chinese sorting, after five choices | Active rankers considering whether to continue | Connecting the same estimated remaining choices to the final result will improve completion versus a neutral remaining-count sentence. **Only that one sentence changes.** | `exposed_completion_rate` | Scope-rescue usage and comparison count do not indicate coercive shortening. |
| `result_share_cta_copy_v1` — Chinese result share bundle | Finishers deciding whether to make a shareable artifact | A friend-oriented CTA will lead to more share/poster actions than a generic poster CTA. **Only the bundle's primary-button text changes.** | `exposed_share_or_poster_rate` | Ranking result, poster format, copy target, and bundle position are unchanged. |

## Implementation and review

- `experiments.py` is the experiment registry and contains the end times, decisions, active variants, stable assignment, and traffic allocation.
- `analytics.py` now calculates `exposed_builtin_card_open_rate`, making the first experiment's denominator and outcome match its actual card surface.
- The Admin experiment tab displays exposed action, start, completion, share/poster, and exposed built-in-card-open metrics. It remains the review source of record.
- No Supabase migration is required for v3.10: it uses existing `experiment_exposed`, funnel, and share/poster events already allowed by the v3.8 policy migration.
