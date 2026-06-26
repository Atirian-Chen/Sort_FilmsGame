# Film Sort Analytics Data Inventory

## Repository Findings

- Event tracking module: `analytics.py`.
- Supabase config and REST helpers: `analytics.py:get_supabase_config`, `supabase_headers`, `supabase_request`, `track_event`.
- Main event trigger locations: `merged_douban_ranker_v3.py`, especially app load, list open/select, sorting start, comparison, completion, result, share, QR, and poster download handlers.
- Analytics dashboard location: `merged_douban_ranker_v3.py:5517` with helper logic in `analytics.py`.
- Database schema source: `supabase_schema.sql`.
- Database-verified analytics table: `analytics_events`.
- Related Supabase tables: `challenge_sets`, `imported_movie_lists`, `peer_match_contacts`.
- No committed analytics mock/sample-data fixture was found in the repository.

### Current Data Tables and Fields

Database-verified top-level fields in `analytics_events`:

- `id`
- `created_at`
- `event_name`
- `session_id`
- `challenge_id`
- `mode`
- `template_id`
- `source_channel`
- `payload`

Code-inferred and sampled payload fields include:

- Routing and attribution: `page`, `route`, `source`, `utm_source`, `utm_medium`, `utm_campaign`, `entry_surface`
- List and mode context: `list_id`, `template_id`, `mode`, `list_source`, `list_size`, `total`, `item_count`, `top_k`
- Sorting behavior: `comparison_count`, `comparisons`, `ranked_count`, `skipped_count`, `defers`, `has_seed`, `blind_mode`, `side_shuffle`
- Result/share context: `winner`, `top_items`, `poster_type`, `surface`
- Environment and release context: `device_type`, `app_version`, `release_id`, `release_name`, `released_at`
- Experiment context, when present: `experiment_id`, `variant_id`, `experiments`
- Home diagnostics: `render_elapsed_ms`, `home_layout_order`

### Current Metrics Logic

- Summary metrics: `analytics.py:build_admin_summary`.
- Funnel rows: `analytics.py:build_funnel_rows`.
- Home load diagnostics: `analytics.py:build_home_load_metrics`.
- List/template performance: `analytics.py:build_list_metrics`, `build_template_content_stats`.
- Channel performance: `analytics.py:build_channel_metrics`.
- Experiment grouping: `analytics.py:build_experiment_metrics`.
- Recent event table masking: `analytics.py:flatten_event_for_table`.

## Existing Events

| Event Name | Status | Notes |
|---|---|---|
| `visit` | implemented | Canonical page/app visit event. |
| `home_content_rendered` | implemented | Home content render completion signal. |
| `experiment_exposed` | implemented | True experiment UI exposure event added in v3.3; used as strict experiment denominator. |
| `list_opened` | implemented | Canonical list-open event; may be called through legacy alias in app code. |
| `list_selected` | implemented | Heavy-path/mode selection signal. |
| `sorting_started` | implemented | Canonical sorting start event; may be called through legacy alias in app code. |
| `comparison_made` | implemented | Pairwise decision event. |
| `ranking_completed` | implemented | Completion event. |
| `result_viewed` | implemented | Result page viewed after completion. |
| `qr_viewed` | implemented | QR-visible result poster event. |
| `poster_downloaded` | implemented | Poster download click. |
| `share_copied` | implemented | Share/link/caption copy event; may be called through legacy alias in app code. |
| `page_view` | legacy compatible | Normalized to `visit`. |
| `challenge_opened` | legacy compatible | Normalized to `list_opened`. |
| `ranking_started` | legacy compatible | Normalized to `sorting_started`. |
| `share_link_copied` | legacy compatible | Normalized to `share_copied`. |

## Existing Dimensions

- Time: `created_at`.
- Template/list: `template_id`, `challenge_id`, `payload.template_id`, `payload.list_id`.
- Movie/list size: `payload.list_size`, `payload.total`, `payload.item_count`.
- Device: `payload.device_type`, with coarse values and possible `unknown`.
- Source/channel: `source_channel`, `payload.source`, `payload.utm_source`, `payload.utm_medium`, `payload.utm_campaign`.
- Page/route: `payload.page`, `payload.route`, `payload.entry_surface`.
- Session: `session_id`; export only masked or hashed values.
- Mode/settings: `mode`, `payload.mode`, `payload.top_k`, `payload.blind_mode`, `payload.side_shuffle`, `payload.has_seed`.
- Experiment, when present: `payload.experiment_id`, `payload.variant_id`, `payload.experiments`.
- Release/version: `payload.app_version`, `payload.release_id`, `payload.release_name`, `payload.released_at`.

## Data Gaps

- No stable cross-session anonymous user ID; long-term retention cannot be measured reliably.
- No explicit `is_internal_test`; test traffic cannot be separated cleanly.
- No explicit abandonment event; abandonment stage must not be claimed precisely.
- No general sorting duration field; only home render elapsed time exists.
- No sanitized referrer/domain field; channel analysis is limited to explicit source/UTM parameters.
- Historical experiment rows may lack `experiment_exposed`; assignment/variant payload is not the same as verified UI exposure.
- Payload fields are not guaranteed on every historical row.

## Immediate Analytics Scope

- Session-based funnel from visit/home render or list open/select to sorting start, completion, and share/download.
- Start-to-completion and completion-to-share/download conversion.
- Template/list performance using normalized `list_id`, `template_id`, `challenge_id`, and `mode`.
- Channel and UTM performance using current attribution fields.
- Device split as a directional metric using `payload.device_type`.
- Movie/list size versus completion and comparison count, for rows with `list_size` or aliases.
- Home render diagnostics using `home_content_rendered` and `render_elapsed_ms`.
- Content stats for template completions where `winner` exists.

## Deferred Analytics Scope

- Exact sorting drop-off position, pending `ranking_progress` or `ranking_abandoned`.
- Long-term retention, pending a privacy-reviewed stable anonymous user ID.
- Strict A/B experiment analysis, pending explicit exposure events and sample-size guardrails.
- User lifecycle value, because no account, revenue, or stable user identity exists.
- Precise referrer/domain attribution, pending sanitized referrer capture.

## Recommended Step 2

- Add minimal test-traffic isolation: `is_internal_test` in payload or a documented source convention.
- Add `ranking_progress` or `ranking_abandoned` with only aggregate progress fields.
- Use `experiment_exposed` as the denominator for new experiments; keep historical assigned-session metrics diagnostic only.
- Add sanitized `referrer_domain` if channel analysis needs non-UTM attribution.
- Consider a privacy-reviewed `anonymous_user_id` only if retention becomes a required analysis goal.
