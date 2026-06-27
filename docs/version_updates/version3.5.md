# version3.5

## Summary

v3.5 在 v3.4 的 3 个 active 实验基础上，追加 2 个更偏动作型的“渲染后行动率”实验：零决策开排和首页先试一题。目标仍然是提升 `experiment_exposed` 后发生 `list_opened` / `list_selected` / `sorting_started` 的 session 比例。

## Active Experiments Added

### home_zero_decision_start_v1

- Surface：`zero_decision_start`
- Control：不显示新入口，但仍上报 `experiment_exposed`，作为严格曝光分母。
- Variant：在首页 step header 后展示“零决策开排”横条。
- 行为：按 `session_id` 稳定哈希，从内置片单池中选择一份片单，并链接到 `?list=<template_id>&entry_surface=home_zero_decision_start`。
- Hypothesis：去掉“先选哪份片单”的决策成本，可以提升首页渲染后的第一步行动。

### home_duel_teaser_v1

- Surface：`duel_teaser`
- Control：不显示试看题，但仍上报 `experiment_exposed`。
- Variant：在首页显示“千与千寻 vs 星际穿越”的二选一试看题。
- 行为：点击任意一侧都进入 `douban-top50`，链接带 `entry_surface=home_duel_teaser` 和 `teaser_choice=left/right`。
- Hypothesis：先让用户完成一次轻量选择，再进入完整排序，更容易把“观看首页”转成“实际行动”。

## Analytics

- 不修改 Supabase schema。
- `list_opened` payload 新增可选字段 `teaser_choice`，仅在首页试看题入口点击后写入。
- 两个新实验继续使用后台已有的 `exposed_action_rate` 作为主指标。

## Version Metadata

- `APP_VERSION = "v3.5"`
- `APP_RELEASE_ID = "v3.5-post-render-action-creative-experiments"`
- `APP_RELEASE_NAME = "创意型渲染后行动率实验"`
- `APP_RELEASED_AT = "2026-06-27T20:56:19+08:00"`

## Compatibility

- 不暂停 v3.4 已上线的 3 个 active 实验。
- 不改排序核心流程；两个入口都复用现有 `?list=` 打开内置片单的路径。
- 首页不实时联网抓电影海报；零决策横条只使用现有静态缩略图，缺失时自动纯文本展示。

## Regression Commands

```bash
python -m py_compile merged_douban_ranker_v3.py analytics.py experiments.py challenge_store.py import_store.py launch_copy.py release_history.py
git diff --check
```
