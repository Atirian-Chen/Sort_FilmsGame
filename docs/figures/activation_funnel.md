# activation_funnel

Source: Film Sort Admin Analytics HTML export, 2026-06-01 to 2026-06-25.

- Data range: 2026-06-01 to 2026-06-25
- Applicable version: V2 current instrumentation with `home_content_rendered`; older visits without this event are excluded from the denominator
- Statistical unit: unique session
- Denominator: previous funnel stage session count
- Horizontal comparability: only comparable with the same Current Total Funnel definition and the same instrumentation era; do not add to Light/Heavy/Legacy funnels
- Scope note: current total funnel uses V2 session-level stages. It is not identical to all historical `visit` events.

| Funnel Stage | Event Definition | Sessions | Step Conversion | Overall Conversion | Dropoff From Previous |
|---|---|---:|---:|---:|---:|
| Home content rendered | `home_content_rendered` | 3,457 | 100.0% | 100.0% | 0 |
| List opened or selected | `list_opened` / `list_selected` | 1,571 | 45.4% | 45.4% | 1,886 |
| Sorting started | `sorting_started` | 256 | 16.3% | 7.4% | 1,315 |
| Ranking completed | `ranking_completed` | 37 | 14.5% | 1.1% | 219 |
| Share or download | `share_copied` / `poster_downloaded` | 13 | 35.1% | 0.4% | 24 |

Interpretation boundary: this table supports a session-level activation diagnosis for V2-tracked sessions. Because historical visit coverage and home render coverage are not fully aligned, it should be read as a product signal, not a complete causal attribution.
