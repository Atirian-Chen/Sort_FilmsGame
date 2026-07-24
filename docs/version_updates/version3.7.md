# version3.7

## Summary

v3.7 将结果页榜单海报拆成两个按需生成入口：带电影海报的 Top 10，以及不抓取电影海报的纯文字 Top 100。两种海报共享配色与二维码设置，并始终使用实际可靠排名。

## Poster Formats

- Top 10：`1080×1920`，最多十行，每行包含名次、电影海报和标题，Top 3 使用奖牌强调。
- Top 100：`1800×2400`，每列最多 25 行，根据实际数量使用 1–4 栏，Top 3 使用强调边框。
- 不足 10/100 名时显示真实 `Top N`；结果超过 100 名时注明“展示前 100 / 完整结果共 N 名”。
- 单个电影海报缺失时仅使用占位，不影响 Top 10 整图生成；Top 100 全程不请求电影海报。

## Result Page

- 保留“海报风格”和“二维码版本”，移除容易造成名单截断的尺寸选择。
- 新增“生成 Top 10 海报（带电影海报）”和“生成 Top 100 海报（无电影海报）”按钮。
- 海报采用独立签名与缓存；排名、风格或二维码改变后必须重新生成。
- Top 10、Top 100 和最纠结取舍海报使用标签页预览，并分别提供下载按钮。

## Analytics

- `poster_downloaded.payload.poster_type`：`result_top10` / `result_top100` / `contested_choice`。
- 榜单海报下载与二维码曝光增加 `poster_item_count`。
- 不修改 Supabase schema，后台现有动态 payload 分组直接兼容。

## Version Metadata

- `APP_VERSION = "v3.7"`
- `APP_RELEASE_ID = "v3.7-top100-ranking-poster"`
- `APP_RELEASE_NAME = "Top 10 / Top 100 结果海报"`
- `APP_RELEASED_AT = "2026-07-03T16:40:50+08:00"`

## Regression Commands

```bash
python -m py_compile merged_douban_ranker_v3.py analytics.py release_history.py
python -m unittest tests.test_result_posters tests.test_light_list_catalog -v
git diff --check
```
