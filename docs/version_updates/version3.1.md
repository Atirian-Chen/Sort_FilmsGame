# version3.1

## Summary

v3.1 为豆瓣已看和非模板自备片单补充完成结果前 10 名埋点，并在后台新增模板片单内容统计与冠军榜宣传海报。

## 埋点调整

- 模板片单完成事件保持原有口径：继续写入 `payload.winner`，不新增 `top_items`。
- 豆瓣已看完成后写入 `payload.top_items = ranked[:10]`。
- 非模板自备片单完成后写入 `payload.top_items = ranked[:10]`。
- 豆瓣高分不新增 `top_items`。
- 不修改 Supabase schema，继续使用 `analytics_events.payload`。

`top_items` 最多保存 10 个字符串，用于后续内容偏好分析；完整候选项、完整排名、姓名、联系方式和原始 user_agent 仍会被过滤。

## 后台内容统计

后台新增 “内容统计” tab，只统计模板片单：

- 事件：`ranking_completed`
- 条件：`mode == "自备片单"`，`template_id` 非空
- 冠军来源：`payload.winner`
- 输出：模板名、`template_id`、完成数、可统计冠军数、冠军 Top3、最近完成时间

豆瓣已看、自定义片单、豆瓣高分和没有 `winner` 的历史事件不会进入内容统计榜单。

## 冠军榜海报

- 后台会基于内容统计生成 PNG 海报。
- 海报默认展示完成数最高的前 8 个模板片单。
- 每行展示一个模板片单及冠军次数最多的前三名，前三名电影带海报缩略图。
- 海报说明标注“仅统计模板片单，冠军来自 winner 字段”。
- 新增设计预览图：`promo_assets/content_stats_poster_preview_v3_1.png`。

## 版本元信息

- `APP_VERSION = "v3.1"`
- `APP_RELEASE_ID = "v3.1-template-content-stats"`
- `APP_RELEASE_NAME = "模板内容统计与冠军榜海报"`
- `APP_RELEASED_AT = "2026-06-24T02:00:01+08:00"`

## 测试清单

- 豆瓣已看完成事件包含 `top_items`，长度最多 10。
- 非模板自备片单完成事件包含 `top_items`，长度最多 10。
- 模板片单完成事件不新增 `top_items`，仍保留 `winner`。
- 豆瓣高分完成事件不新增 `top_items`。
- admin 页面出现 “内容统计” tab。
- 内容统计只展示模板片单，并且冠军 Top3 只来自 `winner`。
- 后台宣传海报可以预览和下载。
- 本地预览图已生成：`promo_assets/content_stats_poster_preview_v3_1.png`。

## 回归命令

```bash
python -m py_compile merged_douban_ranker_v3.py analytics.py experiments.py launch_copy.py release_history.py
git diff --check
```
