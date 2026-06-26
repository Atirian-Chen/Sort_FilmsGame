# 从首页曝光到完成分享：Film Sort 用户激活漏斗诊断与低摩擦排序策略

## Executive Summary

Film Sort 把“给一组电影排出个人偏好顺序”拆成连续 1v1 取舍，并在完成后生成可分享结果。本案例分析 2026-06-01 至 2026-06-25 的匿名行为数据，覆盖 102,885 个事件、9,576 个 session，核心问题是优先优化首页价值表达、Heavy Path 配置流程，还是排序任务成本。已验证观察包括：用户看到首页后到开始排序之间存在摩擦；Heavy Flow 从配置到开始的门槛更高；较大任务规模与较低完成率相关。P0 建议是验证 Heavy Flow 默认配置与一键开始。本文不把观察性结果写成因果结论。

## 1. Product Context and Business Question

Film Sort 帮助用户完成电影偏好排序：用户不必一次性手动排列完整榜单，只需不断在两部电影之间做选择，最后得到个人排序、结果海报和分享内容。

当前路径可分为 Light Flow 与 Heavy Flow。Light Flow 面向内置快速片单，用户打开模板后可以较快开始；Heavy Flow 面向豆瓣已看导入、自定义片单或更重的配置场景，开始前需要选择、确认或调整片单。两条路径的用户意图不同，不能直接当作实验组比较。

本案例回答的问题是：下一步应该优先优化首页价值表达、Heavy Path 配置流程，还是排序任务成本。

## 2. Data Scope, Privacy and Methodology

分析窗口为 2026-06-01 至 2026-06-25。数据来自已导出的 Admin Analytics HTML 报告，并引用 [metrics_contract.md](metrics_contract.md)、[data_inventory.md](data_inventory.md)、[event_taxonomy.md](event_taxonomy.md) 的定义。窗口内共有 102,885 个事件、9,576 个 unique sessions、1,752 次 sorting starts、612 次 ranking completions、110 次 share-copy events 和 187 次 poster-download events。

本分析只使用匿名聚合数据，session 是核心分析单位。转化指标按去重 session 计算，event count 只用于动作频次。Legacy 与 V2 埋点并存，首页渲染与全部历史 visit 不能完全对齐；source、device、experiment variant 因缺失或传播不稳定，未用于核心结论。分享/下载在旧导出中只作为事件频次信号；v3.3 起后台拆分为用户转化率和平均动作次数。

## 3. Metric Definitions and Data Quality Controls

核心指标沿用 [metrics_contract.md](metrics_contract.md)：

| Metric | Definition | Use |
|---|---|---|
| 开始率 | 去重 `sorting_started` session / 合格曝光或入口 session | 判断用户是否愿意进入排序。 |
| 完成率 | 去重 `ranking_completed` session / 去重 `sorting_started` session | 判断开始后的任务完成情况。 |
| 完成用户数 / 曝光用户数 | 去重完成 session / 去重曝光 session | 判断整体激活效率。 |
| Unique Share Conversion | 完成后分享的去重 session / 完成 session | 当前导出报告不足以严谨计算。 |
| Unique Poster Download Conversion | 完成后下载的去重 session / 完成 session | 当前导出报告不足以严谨计算。 |
| 行为动作频次 | 分享、下载、比较等 event count / 完成事件或完成 session | 描述动作强度，不代表用户转化。 |

不使用 event count 冒充用户转化，因为同一 session 可能多次比较、复制或下载。`completed without start` 会被标为漏斗异常，不进入严格开始到完成转化。source 缺失归为 `unknown`，多 variant session 不进入实验效果分析。当前局限包括 Legacy/V2 覆盖不完全、source 传播不稳定、结果页资产行为缺少唯一 session 转化。

## 4. Finding 1: Activation Friction Happens After Users See the Product

V2 当前总漏斗显示，`home_content_rendered` 有 3,457 个 session，进入 `list_opened/list_selected` 的 session 为 1,571，step conversion 为 45.4%；进入 `sorting_started` 的 session 为 256，相对上一阶段为 16.3%；完成 `ranking_completed` 的 session 为 37。详见 [activation_funnel.md](figures/activation_funnel.md)。该漏斗只适用于有 `home_content_rendered` 的 V2 当前埋点窗口，不可与 Light/Heavy/Legacy 漏斗相加。

由于首页渲染与后续行动数据不能和全部历史 visit 完全对齐，该结论应视为“初步信号”。在可审计的 V2 范围内，问题更可能发生在用户看到首页内容之后：是否理解产品价值、是否找到合适入口、是否愿意承担排序成本。首页加载性能不是唯一或首要解释，优先方向应是价值表达、入口设计和任务成本提示。

## 5. Finding 2: Heavy Path Has a Higher Start Barrier

Heavy Flow 有 1,675 个 `list_selected` session，但只有 210 个进入 `sorting_started`，进入配置到实际开始的转化为 12.5%；其中 27 个完成，开始到完成为 12.9%。Light Flow 为 760 -> 760 -> 167，开始后完成为 22.0%。详见 [heavy_path_dropoff.md](figures/heavy_path_dropoff.md)。Light 与 Heavy 是不同入口路径诊断，不可相加，也不能当作随机实验比较。

这不是因果比较，因为 Heavy 用户可能有更大列表、更复杂目标和不同动机。但它支持一个可验证假设：默认配置、一键启动、后置调整可能降低 Heavy Path 的开始门槛。

## 6. Finding 3: Task Size Is a Plausible Completion Friction Signal

模板分析显示任务规模与完成率存在观察性关联。样本较充足的四个模板如下，详见 [task_size_vs_completion.md](figures/task_size_vs_completion.md)。

| Template | Starts | Completions | Completion Rate | Avg Size |
|---|---:|---:|---:|---:|
| `nolan` | 81 | 74 | 91.4% | 12.0 |
| `chinese-highscore` | 97 | 86 | 88.7% | 20.0 |
| `douban-top50` | 581 | 160 | 27.5% | 50.0 |
| `douban-collect` | 611 | 149 | 24.4% | 269.8 |

这不是因果证明。模板内容、用户动机、渠道和入口路径都可能造成混杂。下一步应通过 Quick Mode 或默认 Top 20 实验验证：降低默认任务规模是否能提升完成 session / 曝光 session。

## 7. Finding 4: Result Assets Need Session-Level Conversion Metrics

窗口内有 612 次 ranking completions、110 次 share-copy events、187 次 poster-download events。按旧导出的事件频次看，分享复制约为完成事件的 18.0%，海报下载约为 30.6%。这些是平均动作频次的近似信号，不是分享用户转化率或海报下载用户转化率。

但当前导出报告不能严谨拆出“完成 session 中唯一分享”和“完成 session 中唯一下载”。因此当前仅有事件频次信号，暂不作为核心产品结论。v3.3 后台已将这类指标拆为“至少一次动作的去重 session / 完成 session”和“动作事件数 / 完成 session”，后续新导出应优先使用拆分后的口径。

## 8. Recommendations and Prioritization

| Priority | Action | Problem Addressed | Hypothesis | Primary Metric | Guardrail Metric |
|---|---|---|---|---|---|
| P0 | Heavy Flow 默认配置 + 一键开始 | 配置到实际开始转化低 | 默认 Top 20 与一键开始可能降低开始门槛 | 完成 session / 实验曝光 session | 异常退出率、配置修改率、错误率 |
| P1 | Quick Mode / 默认小片单 + 预计耗时 | 大任务规模可能造成完成摩擦 | 小片单和耗时预期可能提升完成率 | ranking_completed / sorting_started | 平均比较次数、结果页行为 |
| P2 | 首页 CTA 与价值表达优化 | 首页渲染后到行动存在流失 | 更清楚的价值表达可能提升开始率 | sorting_started / home_content_rendered | 跳出信号、行为质量 |

## 9. Experiment Design: Heavy Flow Default Start

实验设计见 [experiment_design_table.md](figures/experiment_design_table.md)。Control 是当前配置流程；Variant 是默认 Top 20、默认设置、一键开始、后续可调整。

上线前需要采集：`experiment_exposed`、`heavy_config_viewed`、`default_start_clicked`、`config_changed`、`sorting_started`、`ranking_completed`、`ranking_abandoned`。Primary Metric 是完成 session / `experiment_exposed` session；assigned sessions 只能作为诊断分母。Secondary Metrics 包括开始率、开始到完成率、平均耗时、平均比较次数和结果页行为。Guardrails 包括异常退出率、错误率、配置修改率、完成后结果页停留。

实验上线前必须保证一次曝光只对应一个 variant、session 级稳定分流、预先定义停止条件和样本阈值，并且不因中途波动提前宣称胜出。

## 10. Limitations and Next Steps

本分析窗口有限，Legacy/V2 口径边界仍存在，source 数据传播不完整，模板样本量差异明显，观察性分析不能证明因果。当前也未完成长期留存、LTV 或严格 A/B 实验分析。

v3.3 已补充 `experiment_exposed`，后续新实验必须在对应 UI surface 真实渲染时使用它。下一步仍应补充 `ranking_abandoned`、`heavy_config_viewed`、`default_start_clicked`、`config_changed`，并稳定采集 `experiment_id`、`experiment_variant`、`is_internal_test`、可靠 source 和 result-page session fact 字段。完成这些基础后，再进入 Step 2 的正式漏斗分析与实验评估。
