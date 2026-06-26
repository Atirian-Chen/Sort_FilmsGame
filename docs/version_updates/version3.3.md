# version3.3

## Summary

v3.3 是一次 Analytics metric contract cleanup。它不改变排序主流程，也不迁移数据库；重点是修正后台分析的解释边界：每张漏斗明确口径，分享/下载拆成用户转化率与动作频次，A/B 实验主分母改为真实曝光 session。

## Funnel Scope Cards

- Admin 漏斗页和一键 HTML 导出报告为四张漏斗新增口径卡片：
  - Current Total Funnel
  - Light List Funnel
  - Heavy Path Funnel
  - Legacy Event Count Funnel
- 每张卡片固定展示：适用版本、统计窗口、统计单位、是否只含该版本后事件、是否可横向比较。
- Current Total Funnel 只适用于有 `home_content_rendered` 的 V2 当前埋点 session。
- Light / Heavy 是不同路径诊断，不可相加，也不能当作因果比较。
- Legacy Event Count Funnel 是 event count 旧口径，只能作历史参考，不能和 session funnel 横向比较。

## Share and Poster Metrics

- 后台不再裸展示“分享率”这种含混指标。
- 分享拆成：
  - 分享用户转化率：至少 `share_copied` 一次的完成 session / 完成 session。
  - 平均分享动作次数：`share_copied` event count / 完成 session。
- 海报下载拆成：
  - 海报下载用户转化率：至少 `poster_downloaded` 一次的完成 session / 完成 session。
  - 平均海报下载次数：`poster_downloaded` event count / 完成 session。
- 总览、版本分析、每日趋势、分组表、实验分析和 HTML 导出同步使用拆分指标。

## Experiment Exposure Denominator

- 新增 canonical event：`experiment_exposed`。
- 事件只在实验控制的 UI surface 真实渲染时触发。
- 最小 payload 包含：
  - `experiment_id`
  - `variant_id`
  - `surface`
  - `app_version`
- 当前接入 surface：
  - `hero_cta`
  - `homepage_card`
- Admin 实验表新增：
  - Assigned sessions：事件 payload 带该 variant 的 session，仅作诊断。
  - Exposed sessions：触发 `experiment_exposed` 的去重 session，作为严格实验主分母。
  - 实验主指标：完成 session / exposed sessions。
- 历史实验没有 `experiment_exposed` 时，显示“真实曝光分母不可用”。

## Version Metadata

- `APP_VERSION = "v3.3"`
- `APP_RELEASE_ID = "v3.3-analytics-metric-contract"`
- `APP_RELEASE_NAME = "分析口径与实验曝光分母修正"`
- `APP_RELEASED_AT = "2026-06-27T00:00:00+08:00"`

## Compatibility

- 不修改 Supabase schema。
- 不回写历史数据。
- 保留旧内部字段兼容，但 UI 和文档不再使用单一“分享率”表达。
- 旧 HTML 导出不会自动改变，需要在 Admin 页面重新导出新版报告。

## Test Checklist

- Admin 漏斗页四张漏斗均显示口径卡片。
- HTML 导出中四张漏斗均显示口径卡片。
- 总览、每日趋势、版本分析、分组表和实验表显示拆分后的分享/下载指标。
- 没有完成 session 时，拆分指标显示 `---` 或不可用，不显示误导性 0%。
- 有 `experiment_exposed` 时，实验主指标使用 exposed sessions。
- 没有 `experiment_exposed` 的历史实验显示“真实曝光分母不可用”。

## Regression Commands

```bash
python -m py_compile merged_douban_ranker_v3.py analytics.py experiments.py challenge_store.py import_store.py launch_copy.py release_history.py
git diff --check
```
