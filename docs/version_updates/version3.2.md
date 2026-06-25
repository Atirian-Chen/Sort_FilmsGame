# version3.2

## Summary

v3.2 结束 `home_layout_order_v1` 和 `builtin_card_poster_v1` 两个 A/B 实验，并把胜出表现全量设为默认体验：首页先展示内置快速片单，内置片单卡片默认显示代表电影海报。后台实验分析同步升级为“已停止实验 / 正在进行的实验”两栏，便于继续复盘历史实验。

## 实验收口

- `home_layout_order_v1` 状态改为 `paused`，收口版本为 `builtin_first`。
- `builtin_card_poster_v1` 状态改为 `paused`，收口版本为 `poster`。
- 两个实验保留历史 variants、权重和配置，便于后台继续按历史事件分析。
- 新增实验元信息：`started_at`、`ended_at`、`decision_variant_id`。
- 停止后不再给新 session 分桶，旧链接中的实验 query 参数也不会覆盖当前默认体验。

## 默认体验

- 首页默认先展示内置快速片单，再展示豆瓣已看主推模块。
- 内置轻量片单卡默认显示预制代表电影海报。
- 内置片单卡链接只携带当前 active 实验参数；当前没有 active 实验，因此不会继续传播这两个已停止实验的分桶参数。

## 后台实验分析

- “实验分析” tab 改为两栏：已停止实验和正在进行的实验。
- 每个实验展示实验名、实验 ID、状态、总流量比例、variant 权重比例、开始时间、结束时间和收口版本。
- 分版本指标继续读取当前筛选时间范围内的历史事件 payload。
- 如果当前筛选范围没有某个实验的数据，会显示空态，不影响其他实验展示。

## 版本元信息

- `APP_VERSION = "v3.2"`
- `APP_RELEASE_ID = "v3.2-experiment-rollout-dashboard"`
- `APP_RELEASE_NAME = "实验收口与后台分析优化"`
- `APP_RELEASED_AT = "2026-06-25T18:22:38+08:00"`

## 测试清单

- 首页默认先显示内置快速片单，再显示豆瓣已看主推。
- 内置片单卡片默认显示代表电影海报。
- 带旧实验 query 参数的链接不会恢复 control 表现。
- admin “实验分析” tab 出现已停止实验 / 正在进行的实验两栏。
- `home_layout_order_v1` 和 `builtin_card_poster_v1` 出现在已停止实验栏，并显示比例、起止时间和收口版本。
- 没有 active 实验时，正在进行的实验栏显示空态。
- 历史 A/B 指标仍能按已有 payload 展示。

## 回归命令

```bash
python -m py_compile merged_douban_ranker_v3.py analytics.py experiments.py challenge_store.py import_store.py launch_copy.py release_history.py
git diff --check
```
