# version3.10

## Summary

v3.10 closes every v3.8 online A/B experiment using the Admin report through 2026-08-04, preserves the selected product directions, and launches five new single-variable experiments across the activation, setup, completion, and sharing funnel. The detailed data review, scope, metrics, guardrails, and decision rules are in [the 2026-08-05 A/B review](../abtest_review_2026-08-05.md).

## Closed experiments and default product behavior

All four records have `status = "paused"`, an `ended_at` timestamp, and a `decision_variant_id` in `experiments.py`.

- `home_featured_quick_start_v1` → `control`: keep the existing grid; do not pin a single classic-sci-fi card.
- `heavy_default_start_v1` → `recommended_top10`: keep the editable Top 10 quick-start recommendation on the Douban watched-list setup page.
- `sorting_scope_rescue_v1` → `offer_top10`: keep the progress-preserving Top 10 rescue during a long ranking.
- `result_share_bundle_v1` → `quick_share_bundle`: keep the compact Top 10 poster and “guess the winner” share bundle.

The first conclusion meets the documented strict-exposure volume threshold. The other three selections are product directions based on low-volume directional evidence, not claims of statistical significance.

## Active experiments

| Experiment | Single changed variable | Primary metric |
|---|---|---|
| `home_card_cta_copy_v1` | Built-in card footer CTA: `开始整理` vs `先排 Top N` | `exposed_builtin_card_open_rate` |
| `custom_list_scope_hint_v1` | Long custom-list effort explanation absent vs present | `exposed_start_rate` |
| `douban_collect_scope_default_v1` | New watched-list configuration default: Top 20 vs Top 10 | `exposed_start_rate` |
| `sorting_progress_framing_v1` | Neutral remaining-count sentence vs outcome-framed sentence | `exposed_completion_rate` |
| `result_share_cta_copy_v1` | Share-bundle primary CTA wording | `exposed_share_or_poster_rate` |

All use a stable session split at 50/50 among eligible traffic. Review only after 14 days, 100 exposed sessions per variant, and 25 primary-metric conversions per variant. Until then, report results as directional.

## Analytics and compatibility

- `experiment_exposed` remains the strict denominator; assigned sessions are diagnostic only.
- Added `exposed_builtin_card_opened_sessions` and `exposed_builtin_card_open_rate` so the home-card experiment has an outcome specific to its actual surface.
- The Admin experiment table displays the new exposed-card-open metric and its label.
- No new event type, database table, migration, public API, URL format, or stored challenge format was introduced. Existing v3.8 RLS policy support is sufficient.

## Version metadata

- `APP_VERSION = "v3.10"`
- `APP_RELEASE_ID = "v3.10-abtest-decision-and-next-wave"`
- `APP_RELEASE_NAME = "A/B 实验收口与下一轮漏斗测试"`
- `APP_RELEASED_AT = "2026-08-05T03:19:49+08:00"`

## Regression commands

```bash
python -m py_compile merged_douban_ranker_v3.py analytics.py experiments.py release_history.py
python -m unittest discover -s tests -v
git diff --check
```
