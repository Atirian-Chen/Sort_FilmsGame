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
- `home_content_rendered`

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
- `render_elapsed_ms`
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

## 新版分层漏斗

后台 “漏斗分析” tab 同时展示新版 session 漏斗和历史兼容事件数漏斗。

新版 session 漏斗采用逐步收敛口径：只有进入上一步的匿名 session，才会进入下一步分母。这样可以避免改埋点前的旧数据因为缺少上游事件，错误拉低新版漏斗转化率。

### 总漏斗（当前埋点）

`home_content_rendered -> list_opened/list_selected -> sorting_started -> ranking_completed -> share_copied/poster_downloaded`

这个漏斗从 `home_content_rendered` 起算，只统计确认看到首页核心内容的当前埋点 session。改埋点前没有 `home_content_rendered` 的历史访问不会进入这个漏斗分母。

### 轻量片单漏斗

`list_opened -> sorting_started -> ranking_completed -> share_copied/poster_downloaded`

轻量片单指从内置片单或分享片单链接直接打开后进入整理的链路，例如 `?list=`、`?challenge=`、`?payload=`。当前口径只统计 canonical `list_opened`，不会把旧的 `challenge_opened` 历史兼容事件混进新版分母。

### 重链路漏斗

`list_selected -> sorting_started -> ranking_completed -> share_copied/poster_downloaded`

重链路指需要进入参数页再开始整理的链路，例如豆瓣已看、自备片单，以及通过参数页配置的豆瓣高分。当前没有单独的 `parameter_page_viewed` 事件，因此 `list_selected` 作为“进入填参数 / 配置页”的代理信号；`sorting_started` 表示用户真正完成配置并进入排序。

### 历史兼容事件数漏斗

历史兼容漏斗仍然保留，用于查看旧数据趋势和整体事件量。但它是事件次数口径，会兼容 `page_view`、`challenge_opened`、`ranking_started`、`share_link_copied` 等历史事件，不建议用来判断新版分步漏斗的精确流失。

## 首页加载诊断

为了判断首页流失更可能发生在加载中还是看到内容之后，v2 增加诊断事件：

- `visit`：普通首页访问开始。
- `home_content_rendered`：Streamlit 服务端完成首页核心内容渲染。
- `list_opened/list_selected/sorting_started`：用户在首页渲染后发生片单动作。

后台 “首页加载诊断” tab 会按匿名 session 统计：

- 首页访问 session
- 内容已渲染 session
- 加载中流失 session：有 `visit`，但没有 `home_content_rendered`，也没有片单动作。
- 渲染后未行动 session：有 `home_content_rendered`，但没有继续打开/选择片单或开始整理。
- 平均、P75、P90 服务端渲染耗时。

说明：`home_content_rendered` 是服务端渲染完成信号，不等同于浏览器真实 FCP/LCP。如果后续需要更精确的前端性能监控，需要增加客户端 beacon 或前端性能 SDK。

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
