# version2.8

## Summary

v2.8 修正后台看板历史事件读取窗口过小的问题：后台主读取不再默认只覆盖最近 50,000 条事件，而是提升到最多 1,000,000 条事件。

这次不改时间范围筛选逻辑。“最近 7 天”“最近 30 天”“全部历史”“自定义”仍保持原有行为；变化只发生在后台从 Supabase 拉取 `analytics_events` 的总数据窗口。

## 背景

后台看板原来的 `fetch_all_events()` 配置为：

```python
def fetch_all_events(page_size: int = 1000, max_rows: int = 50000)
```

它会按 `created_at.desc` 分页读取事件。事件总量超过 50,000 后，最旧的一批事件会被挤出本地统计窗口，即使界面选择“全部历史”，实际也只能统计最近 50,000 条内的数据。

这会让早期版本、早期日期、旧渠道或旧片单的数据看起来越来越少。

## Key Changes

- 在 `analytics.py` 新增后台读取常量：
  - `ADMIN_EVENT_PAGE_SIZE = 1000`
  - `ADMIN_EVENT_MAX_ROWS = 1_000_000`
- `fetch_all_events()` 默认改为：

```python
def fetch_all_events(page_size: int = ADMIN_EVENT_PAGE_SIZE, max_rows: int = ADMIN_EVENT_MAX_ROWS)
```

- 仍然按 1000 条一页分页读取，直到 Supabase 返回空页、返回不足一页，或达到 1,000,000 条上限。
- 不修改“最近 30 天”的默认筛选，也不修改后台 tab 内各类展示条数。
- `release_history.py` 当前版本更新为 v2.8，并把 v2.7 固化进历史版本时间线。

## Data Compatibility

- 不需要数据库迁移。
- 不改变 `analytics_events` 表结构。
- 不改变已有事件 payload。
- 不改变公开首页指标 `fetch_public_metrics()` 的最近 1000 条读取逻辑。
- 如果事件总量超过 1,000,000 条，后台仍会只统计最近 1,000,000 条，需要后续再做按日期分段查询或服务端聚合。

## 风险说明

- 读取 1,000,000 条事件会比 50,000 条慢，尤其是首次打开后台或点击“刷新数据缓存”后。
- Streamlit 缓存仍保留 300 秒，避免每次页面交互都重新读取全量窗口。
- 如果 Supabase 项目、网络或 Streamlit 资源吃紧，后续可以再改成按日期范围分页读取，而不是先拉全量再本地过滤。

## 版本元信息

- `APP_VERSION = "v2.8"`
- `APP_RELEASE_ID = "v2.8-admin-million-event-history"`
- `APP_RELEASE_NAME = "后台看板百万事件读取"`
- `APP_RELEASED_AT = "2026-06-17T20:38:30+08:00"`

## 测试清单

- `fetch_all_events()` 默认 `max_rows` 为 `1_000_000`。
- `fetch_all_events()` 仍按 `page_size=1000` 分页读取。
- 后台时间范围筛选逻辑保持不变。
- `release_history.py` 当前版本显示为 v2.8。
- README 版本更新区新增 v2.8。

## 回归命令

```bash
python -m py_compile merged_douban_ranker_v3.py import_store.py analytics.py release_history.py
git diff --check
```
