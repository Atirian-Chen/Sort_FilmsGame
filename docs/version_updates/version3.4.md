# version3.4

## Summary

v3.4 上线 3 个围绕“渲染后行动率”的 A/B 实验。目标是在首页内容已经完成渲染后，提升用户继续打开/选择片单或开始整理的比例。

主指标：

```text
exposed_action_rate = exposed sessions 中发生 list_opened / list_selected / sorting_started 的 session / exposed sessions
```

## Active Experiments

### post_render_hero_value_v1

- Surface：`hero_cta`
- Control：原首屏表达，强调慢慢排出电影审美名单。
- Variant：结果预览表达，强调从现成片单开始，并明确完成后会得到冠军、Top 排名、海报和分享链接。
- Hypothesis：更具体的结果预览能减少“看完首页但不知道下一步做什么”的流失。

### quick_list_card_framing_v1

- Surface：`quick_list_cards`
- Control：卡片展示“推荐理由”和“开始整理”。
- Variant：卡片展示“适合现在开始”、更低成本的说明，以及“先排 Top N”行动提示。
- Hypothesis：把卡片从解释型文案改为行动型文案，能提升内置片单打开率和首页渲染后行动率。

### douban_collect_entry_cta_v1

- Surface：`douban_collect_spotlight`
- Control：豆瓣已看总榜叙事。
- Variant：强调只需要豆瓣 ID、下一步先预览候选电影，再开始整理。
- Hypothesis：降低用户对豆瓣已看入口的心理成本，提升从首页进入配置页的比例。

## Analytics

- 新增实验全部使用 `experiment_exposed` 作为严格曝光分母。
- `analytics.py` 的实验聚合新增：
  - `exposed_action_sessions`
  - `exposed_action_rate`
- Admin 实验表新增“曝光后行动”和“曝光后行动率”列。

## Version Metadata

- `APP_VERSION = "v3.4"`
- `APP_RELEASE_ID = "v3.4-post-render-action-experiments"`
- `APP_RELEASE_NAME = "渲染后行动率 A/B 实验"`
- `APP_RELEASED_AT = "2026-06-27T03:08:50+08:00"`

## Compatibility

- 不修改 Supabase schema。
- 不回写历史数据。
- `home_layout_order_v1` 和 `builtin_card_poster_v1` 保持 paused，继续用于历史复盘。

## Regression Commands

```bash
python -m py_compile merged_douban_ranker_v3.py analytics.py experiments.py challenge_store.py import_store.py launch_copy.py release_history.py
git diff --check
```
