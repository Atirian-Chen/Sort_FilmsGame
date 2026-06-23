# version2.10

## Summary

v2.10 删除豆瓣电脑导入助手中没有实际价值的手动复制折叠栏，并为首页 8 份内置轻量片单增加预制海报 A/B 实验。

## 豆瓣导入助手调整

- 删除“拖不动？手动复制导入按钮代码”整栏。
- 删除其中的书签名称复制和 JavaScript 代码复制按钮。
- 保留“导入我的豆瓣已看”主书签按钮。
- 保留“详细导入教程”外链。
- 不修改书签导入、Supabase 存储或豆瓣读取逻辑。

## 代表电影映射

| 片单 | 代表电影 | 静态资源 |
| --- | --- | --- |
| 豆瓣高分片单 | 肖申克的救赎 | `douban-top50.webp` |
| 诺兰作品序列 | 星际穿越 | `nolan.webp` |
| 宫崎骏动画手记 | 千与千寻 | `miyazaki.webp` |
| 新海诚动画电影榜 | 你的名字。 | `shinkai.webp` |
| 华语高分片单 | 霸王别姬 | `chinese-highscore.webp` |
| 王家卫电影榜 | 花样年华 | `wong-kar-wai.webp` |
| 迪士尼动画长片榜 | 疯狂动物城 | `disney-animation.webp` |
| 两个人的观影名单 | 泰坦尼克号 | `couple-debate.webp` |

所有资源位于 `assets/builtin_list_thumbnails/`，尺寸为 `136×192` WebP，单张约 3.6–7.9 KB。页面运行时只读取这些仓库资源并转成 data URI，不调用豆瓣、IMDb 或运行时海报缓存。

## A/B 实验

- 实验 ID：`builtin_card_poster_v1`
- 状态：`active`
- 流量：100%
- 分桶比例：1:1
- `control`：纯文字卡片。
- `poster`：卡片右上角显示约 `68×96` 的代表电影海报。

`home_layout_order_v1` 保持 active，两个实验独立分桶并形成 2×2 组合。卡片链接携带：

- `entry_surface=home_builtin_card`
- `exp_home_layout_order_v1=<variant>`
- `exp_builtin_card_poster_v1=<variant>`

实验模块只恢复当前配置中存在的 active variant，非法参数会被忽略并回到稳定哈希分桶。

## 指标口径

- 首页曝光：`home_content_rendered` session。
- 内置片单打开：`entry_surface=home_builtin_card` 的 `list_opened` session。
- 卡片打开率：内置片单打开 session / 首页曝光 session。
- 次指标：开始整理率、完成率、分享率和海报下载率。

后台“A/B 实验表现”会新增首页曝光、内置片单打开和卡片打开率三列。

## 版本元信息

- `APP_VERSION = "v2.10"`
- `APP_RELEASE_ID = "v2.10-builtin-card-poster-experiment"`
- `APP_RELEASE_NAME = "轻量片单海报 A/B 实验"`
- `APP_RELEASED_AT = "2026-06-23T22:34:11+08:00"`

## 测试清单

- 8 张 WebP 均为 `136×192` 且小于 20 KB。
- 控制组不渲染 `.challenge-card-poster`。
- 实验组渲染 8 张正确海报。
- 桌面三列和 390px 移动单列布局无文字、海报或按钮重叠。
- 卡片链接携带两个实验版本和 `entry_surface`。
- `?list=` 页面恢复原实验分桶。
- 事件 payload 同时包含两个 active 实验。
- 后台实验表显示首页曝光、内置片单打开和卡片打开率。
- 豆瓣导入助手不再显示手动复制折叠栏。

## 回归命令

```bash
python -m py_compile merged_douban_ranker_v3.py analytics.py experiments.py launch_copy.py release_history.py
git diff --check
```
