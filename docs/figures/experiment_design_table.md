# experiment_design_table

Proposed experiment: Heavy Flow Default Start.

This is a design table only. No experiment result is claimed.

| Component | Definition |
|---|---|
| Control | Current Heavy Flow configuration process before sorting starts. |
| Variant | Default Top 20, default settings, one-click start, with later adjustment still available. |
| Required Events | `experiment_exposed`, `heavy_config_viewed`, `default_start_clicked`, `config_changed`, `sorting_started`, `ranking_completed`, `ranking_abandoned` |
| Primary Metric | Completed sessions / experiment exposure sessions. |
| Secondary Metrics | Start rate, start-to-completion rate, average duration, average comparison count, result-page actions. |
| Guardrail Metrics | Abnormal exit rate, error rate, configuration change rate, post-completion result-page dwell. |
| Pre-launch Requirements | One exposure maps to one variant; session-level stable assignment; predefined stopping rules and sample thresholds; no early winner claim from interim fluctuations. |
