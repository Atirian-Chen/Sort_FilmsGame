# version3.8

## Summary

v3.8 根据 2026-06-25 至 2026-07-24 的 Admin 聚合报告，停止 v3.4 / v3.5 的 5 个在跑实验，固化方向性胜出版本，并上线覆盖首页、重链路配置、排序过程和结果传播四个阶段的新一轮 A/B 实验。

报告期内共有 3,388 个独立 session。首页渲染完成率为 98.6%，但 70.7% 的已渲染 session 没有继续行动；重链路从配置页到实际开始仅 27.8%；轻量与重链路开始后的完成率分别为 23.3% 和 17.3%；完成后的分享/海报行动仍偏低。

## Previous Experiment Decisions

历史实验没有成功写入 `experiment_exposed`，因此以下结论只使用 assigned session、首页曝光 proxy 和下游结果作方向性判断，不声称统计显著：

| 实验 | 收口版本 | 主要依据 |
|---|---|---|
| `post_render_hero_value_v1` | `outcome_preview` | 行动 proxy 基本持平，完成率、分享和海报转化更高 |
| `quick_list_card_framing_v1` | `control` | 开始率基本持平，完成率和海报转化更高 |
| `douban_collect_entry_cta_v1` | `control` | 开始率与分享转化更高 |
| `home_zero_decision_start_v1` | `control` | 首页行动 proxy 与开始率更高 |
| `home_duel_teaser_v1` | `control` | 试看题提高开始率但降低完成率，首页行动 proxy 更低 |

结束时间统一记录为报告导出时间 `2026-07-24T18:00:55+08:00`。

## New Experiments

### 1. `home_featured_quick_start_v1`

- 问题：首页渲染后 70.7% 无行动。
- Control：保持现有片单网格。
- Variant：在首页增加“近期完成最多”的 `classic-scifi` 单一主行动，明确 12 部电影、Top 10 和结果海报收益。
- 主指标：曝光后行动率。

### 2. `heavy_default_start_v1`

- 问题：重链路配置页到实际开始仅 27.8%。
- Control：保留现有豆瓣已看配置与开始按钮。
- Variant：提供保留当前筛选、直接按推荐 Top 10 开排的主按钮。
- 主指标：曝光后开始率。

### 3. `sorting_scope_rescue_v1`

- 问题：开始后完成率低，P90 取舍次数达到 455.8。
- Control：长任务达到救援条件后保持原目标。
- Variant：完成至少 30 次取舍且预计剩余至少 40 次时，可保留当前进度并缩短为 Top 10。
- 主指标：曝光后完成率。

### 4. `result_share_bundle_v1`

- 问题：完成用户的分享与海报行动仍偏低。
- Control：保留现有海报与分享区。
- Variant：在结果顶部提供一键生成 Top 10 海报和复制猜冠军文案的紧凑分享包。
- 主指标：曝光后分享/海报率。

## Instrumentation Fix

- 根因：应用从 v3.3 起发送 `experiment_exposed`，但 Supabase anon insert policy 未把该事件加入允许列表，导致报告中所有实验的 Exposed sessions 为 0。
- `supabase_schema.sql` 已补充 `experiment_exposed`。
- 新增 migration `supabase/migrations/20260724_abtest_v38_events.sql`，同时允许：
  - `heavy_config_viewed`
  - `default_start_clicked`
  - `sorting_scope_reduced`
  - `result_share_prompt_clicked`
- `experiment_exposed` 改为同步确认写入成功后再标记当前 session 已上报；写入失败时后续重渲染会重试。
- 后台实验表同时展示曝光后行动、开始、完成和分享/海报四组 session 指标，并在配置表标明每个实验的主指标。

## Version Metadata

- `APP_VERSION = "v3.8"`
- `APP_RELEASE_ID = "v3.8-abtest-funnel-recovery"`
- `APP_RELEASE_NAME = "漏斗修复与新一轮 A/B 实验"`
- `APP_RELEASED_AT = "2026-07-24T18:09:16+08:00"`

## Deployment Requirement

应用代码上线前，必须先在 Supabase SQL Editor 执行：

```sql
supabase/migrations/20260724_abtest_v38_events.sql
```

如果未执行，产品功能仍可使用，但严格实验曝光与四个新交互事件无法写入，A/B 结果不可用于正式判断。

## Regression Commands

```bash
python -m py_compile merged_douban_ranker_v3.py analytics.py experiments.py release_history.py
python -m unittest tests.test_abtest_v38 tests.test_result_posters tests.test_light_list_catalog -v
git diff --check
```
