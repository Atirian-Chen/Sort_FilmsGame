# version3.6

## Summary

v3.6 为首页轻量片单增加基于真实匿名访问的自动排序和三日轮换。首页固定展示 9 份；片单模板保存在代码中，日统计与运行状态保存在 Supabase。

本版本同时为新增的 24 份轮换模板补齐代表电影海报，最终 32 份轻量片单都使用仓库内静态缩略图。

## Daily Ranking

- 北京时间 03:00 作为日切边界，03:00 后首个首页访问触发维护 RPC。
- 昨日访问量使用 `list_opened` / `challenge_opened` 的去重 `session_id`。
- 新上架片单置顶保护 24 小时，其余按昨日访问降序排列。
- 当天第一次结算后固定 active roster 与 `display_rank`，同一统计日的后续 RPC 只读取已保存状态。
- RPC 失败时依次回退到上次 Supabase roster 和静态 9 份。

## Three-day Rotation

- 每满 3 个完整统计日，移除近 3 日访问最少的 3 份片单。
- 每轮从候选池加入导演、演员、类型片单各 1 份。
- 新片单积累至少 3 个统计日后才参与淘汰；下架片单冷却 21 天后可再次候选。
- 长期休眠后恢复只执行一轮，不连续补跑多个轮换周期。

## Candidate Catalog

- 保留原 8 份片单，并将斯皮尔伯格片单作为第 9 份初始展示。
- 新增的 24 份轮换模板仍为导演、演员、类型各 8 份；初始状态中 1 份 active、23 份候选。
- 全量 32 份模板继续支持 `?list=<template_id>` 直链；从首页下架不会破坏旧链接。

## Poster Coverage

- 沿用轻量片单原有的代表电影海报样式，不生成片单概念封面。
- 新增 24 张 `136×192` RGB WebP，连同原有 8 张共覆盖全部 32 份模板，单张不超过 20 KB。
- `promo_assets/generate_builtin_list_thumbnails.py` 默认只生成缺失文件，支持显式覆盖和联系表检查。
- 页面运行时只读取 `assets/builtin_list_thumbnails/`，不会为卡片实时请求豆瓣或 IMDb。

## Supabase

- 新增 `light_list_catalog_state`、`light_list_daily_stats`、`light_list_rotation_runs`。
- 新增 `get_home_light_list_roster()`、`read_home_light_list_roster()`、`get_light_list_rotation_history()` RPC。
- 使用 advisory lock、主键和轮换记录保证首访并发下的幂等性。
- 部署前需执行 `supabase/migrations/20260629_light_list_auto_rotation.sql`。

## Admin

- 新增“轻量片单维护”tab。
- 展示当前顺序、昨日/近 3 日访问、新品状态、最后/下一轮日期和轮换历史。
- “重新读取维护状态”只清缓存并重跑幂等维护，不支持人工强制淘汰。

## Version Metadata

- `APP_VERSION = "v3.6"`
- `APP_RELEASE_ID = "v3.6-light-list-auto-rotation"`
- `APP_RELEASE_NAME = "轻量片单自动排序与轮换"`
- `APP_RELEASED_AT = "2026-06-29T14:21:07+08:00"`

## Regression Commands

```bash
python -m py_compile merged_douban_ranker_v3.py analytics.py experiments.py challenge_store.py import_store.py launch_copy.py light_list_catalog.py light_list_runtime.py release_history.py promo_assets/generate_builtin_list_thumbnails.py
python -m unittest tests.test_light_list_catalog -v
git diff --check
```
