# Film Sort Metrics Contract

本文定义 Film Sort Product Analytics Case Study 使用的核心指标口径。除非特别说明，转化类指标优先使用 session-level 去重口径，event count 只用于描述动作频次，不用于冒充用户转化。

## 1. Scope

适用范围：

- 匿名产品分析、激活漏斗、模板表现、结果页分享/下载行为分析。
- 数据来源包括 `analytics_events`、Admin Analytics HTML 导出、`docs/data_inventory.md` 与 `docs/event_taxonomy.md` 中记录的代码口径。
- 本文不定义收入、长期留存、LTV 或严格实验显著性结论。

## 2. Core Analysis Unit

核心分析单位为 `session_id`。同一个 session 内多次触发同一事件时，转化率只计为 1 个转化 session；动作频次指标可以保留 event count。

当前数据不使用手机号、邮箱、精确身份信息或原始用户身份作为分析单位。若后续需要跨 session 留存，应先设计匿名且稳定的 `anonymous_user_id`，并明确隐私边界。

## 3. Metric Definitions

| Metric | Definition | Unit | Notes |
|---|---|---|---|
| Start Rate | `unique sessions with sorting_started / eligible exposure sessions` | session | 分母随场景变化：全站可用 visit 或 home render，Light/Heavy path 使用对应入口 session。 |
| Completion Rate | `unique sessions with ranking_completed / unique sessions with sorting_started` | session | 用于衡量已经开始排序后的完成情况。 |
| Completed Sessions / Exposed Sessions | `unique sessions with ranking_completed / eligible exposed sessions` | session | 用于整体激活漏斗，不等同于 event count。 |
| Unique Share Conversion | `unique completed sessions with share_copied / unique completed sessions` | session | 需要 session fact table 能可靠连接 completed 与 share 行为；当前导出报告不把拆分后的唯一分享转化作为核心结论。 |
| Unique Poster Download Conversion | `unique completed sessions with poster_downloaded / unique completed sessions` | session | 同上，需要去重后的 completed session 分母。 |
| Behavior Action Frequency | `event count / completed event count` 或 `event count / completed sessions` | event/session | 只描述动作频次，不代表独立用户转化。 |

## 4. Data Quality Controls

### Completed Without Start

如果一个 session 有 `ranking_completed` 但没有 `sorting_started`：

- 不直接删除记录；
- 在 session fact table 中标记为 funnel anomaly；
- 对开始到完成转化率，默认排除或单独列示；
- 对内容完成量，可以作为历史兼容事件保留，但需注明口径。

### Completed Before Start

如果同一 session 的完成时间早于开始时间：

- 标记为 timestamp anomaly；
- 不进入需要顺序约束的漏斗；
- 可用于检查客户端上报时序、历史事件兼容或重复 session 问题。

### Source Missing

`source`、`utm_source`、`utm_medium`、`utm_campaign` 缺失时：

- 归为 `unknown`；
- 不把 `unknown` 与任一渠道合并；
- 不基于 source 缺失严重的分组做强结论。

### Multiple Variants

若同一个 session 同时出现多个 `variant_id` 或多个实验分组：

- 标记为 variant conflict；
- 不进入严格 A/B 实验效果分析；
- 只可用于描述历史配置或排查分流稳定性。

### Legacy and V2 Boundary

历史兼容事件与 V2 session fact table 可以共同用于宏观盘点，但核心产品结论需要优先使用 V2 session-level 口径。若 Legacy 与 V2 事件覆盖范围不一致，必须在分析中注明边界，并将结论降级为观察性信号或初步信号。

## 5. Current Limitations

- 当前导出报告可支持激活漏斗、Light/Heavy path 对照、模板规模与完成率观察。
- 当前导出报告不能严谨拆出完成 session 中唯一分享、唯一下载的独立转化率，因此分享/下载只作为事件频次信号。
- 当前不支持长期留存、LTV 或严格因果判断。
- 实验分析需要新增稳定曝光事件、session 级固定分流、预设停止条件和样本阈值。
