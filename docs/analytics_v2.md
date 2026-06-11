# 数据分析 v2 与实验埋点说明

## 概览

数据分析 v2 将 Sort_FilmsGame 从简单事件计数升级为可用于产品复盘的后台数据看板，覆盖激活分析、漏斗诊断、片单表现、渠道归因和轻量增长实验。

系统继续使用 Supabase `analytics_events` 保存匿名 session 事件。不采集姓名、手机号、联系方式、IP 地址或原始 user_agent。

## 标准事件名

- `visit`
- `list_opened`
- `list_selected`
- `sorting_started`
- `comparison_made`
- `ranking_completed`
- `poster_downloaded`
- `share_copied`
- `result_viewed`
- `qr_viewed`

## 历史事件兼容

后台聚合前会自动映射历史事件名：

- `page_view -> visit`
- `challenge_opened -> list_opened`
- `ranking_started -> sorting_started`
- `share_link_copied -> share_copied`

这样无需迁移旧数据，历史数据也可以继续在后台数据看板 v2 中使用。

## 事件结构

Supabase 物理表结构保持不变：

- `event_name`
- `created_at`，作为事件时间
- `session_id`，作为匿名 session ID
- `challenge_id`
- `template_id`
- `mode`
- `source_channel`
- `payload`

v2 新增的上下文字段写入经过过滤的 `payload`：

- `page`
- `route`
- `list_id`
- `template_id`
- `mode`
- `source`
- `utm_source`
- `utm_medium`
- `utm_campaign`
- `list_size`
- `comparison_count`
- `device_type`
- `experiment_id`
- `variant_id`
- `metadata`

payload 会屏蔽完整候选项、完整排名、用户名、手机号、邮箱、联系方式、IP 字段和原始 user_agent。

## 漏斗口径

主漏斗：

`visit -> list_opened/list_selected -> sorting_started -> ranking_completed -> share_copied/poster_downloaded`

后台数据看板 v2 展示：

- 每一步事件数
- 单步转化率
- 总体转化率
- 相邻步骤流失数
- 最大流失步骤
- 自动洞察文案

## 渠道归因

支持的 URL 参数：

- `source`
- `utm_source`
- `utm_medium`
- `utm_campaign`
- 兼容旧参数 `src`

归因优先级：

1. `source`
2. `utm_source`
3. `src`
4. `direct / unknown`

后台按渠道展示访问、开始、完成、复制分享和海报下载等指标。

## A/B 实验

实验配置位于 [experiments.py](../experiments.py)。

每个实验支持：

- `experiment_id`
- `status`
- `traffic_allocation`
- `variants`
- `variant_id`
- `variant_name`
- `config`

当前运行中的实验为 `home_layout_order_v1`，用于测试首页入口顺序：`control` 保持豆瓣已看主推在上，`builtin_first` 将豆瓣高分 / 诺兰等快速开始片单前置。`homepage_cta_v1` 已暂停，用来避免首页文案实验和布局实验互相干扰。匿名 session 会根据 `anonymous_session_id + experiment_id` 做稳定哈希分桶，因此同一个 session 会持续命中同一个版本。

事件中会记录 `experiment_id` 和 `variant_id`，后台可以按实验版本比较：

- 访问数
- 开始整理数
- 完成名单数
- 开始率
- 完成率
- 复制分享数
- 海报下载数

## 如何新增一个实验

大多数新实验只需要改 [experiments.py](../experiments.py)。

推荐流程：

1. 复制一个实验配置块。
2. 修改 `experiment_id`，例如 `default_list_v1`、`poster_preview_v1`、`quick_mode_entry_v1`。
3. 设置 `status`：
   - `active`：实验生效并进入分桶。
   - `paused`：实验暂停，不再进入新事件上下文。
4. 设置 `traffic_allocation`，例如 `0.5` 表示只让 50% 匿名 session 进入实验。
5. 在 `variants` 中配置多个版本，每个版本包含 `variant_id`、`variant_name`、`weight` 和 `config`。
6. 如果实验需要改变页面表现，在对应功能处调用：

```python
config = get_experiment_config(get_session_id(), "your_experiment_id", defaults={})
```

7. 如果实验只需要做标签记录，不改变页面表现，则不需要改业务代码；事件会自动带上所有 active 实验的分桶信息。

后台数据看板 v2 会自动读取事件 payload 中的 `experiments` 字典，因此新增实验后不需要再单独开发实验报表。

## 隐私说明

- 不需要登录。
- 匿名 session ID 是随机生成的，只用于产品行为分析。
- 后台事件表只展示截断后的 session 标识。
- 不展示、也不主动保存原始 user_agent。
- 事件 payload 不保存完整自定义片单或完整排名。
