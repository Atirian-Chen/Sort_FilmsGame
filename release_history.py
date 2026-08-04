from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, Iterable, Optional


APP_VERSION = "v3.10"
APP_RELEASE_ID = "v3.10-abtest-decision-and-next-wave"
APP_RELEASE_NAME = "A/B 实验收口与下一轮漏斗测试"
APP_RELEASED_AT = "2026-08-05T03:19:49+08:00"


# Version starts are based on the first push/deploy commit of each feature phase
# on the GitHub branch codex/atirian_auto.
RELEASE_TIMELINE = [
    {
        "app_version": "v1.0",
        "release_id": "v1.0-public-launch",
        "release_name": "公开发布版",
        "released_at": "2026-06-01T01:10:36+08:00",
        "commit": "e50a779",
    },
    {
        "app_version": "v1.1",
        "release_id": "v1.1-poster-mobile",
        "release_name": "海报、二维码和移动端优化",
        "released_at": "2026-06-01T03:01:59+08:00",
        "commit": "80b9556",
    },
    {
        "app_version": "v1.2",
        "release_id": "v1.2-home-promo",
        "release_name": "首页和宣传素材优化",
        "released_at": "2026-06-02T00:08:18+08:00",
        "commit": "543732a",
    },
    {
        "app_version": "v1.3",
        "release_id": "v1.3-douban-collect",
        "release_name": "豆瓣已看总榜",
        "released_at": "2026-06-02T16:29:39+08:00",
        "commit": "935e610",
    },
    {
        "app_version": "v1.4",
        "release_id": "v1.4-local-draft",
        "release_name": "浏览器本地自动保存",
        "released_at": "2026-06-03T13:45:25+08:00",
        "commit": "0056f77",
    },
    {
        "app_version": "v1.5",
        "release_id": "v1.5-bookmarklet-import",
        "release_name": "豆瓣已看书签导入",
        "released_at": "2026-06-05T03:10:17+08:00",
        "commit": "a5ad774",
    },
    {
        "app_version": "v1.6",
        "release_id": "v1.6-rating-filter-readme",
        "release_name": "豆瓣已看评分筛选与 README 重写",
        "released_at": "2026-06-07T06:44:10+08:00",
        "commit": "3e0f9c8",
    },
    {
        "app_version": "v1.7",
        "release_id": "v1.7-admin-dashboard",
        "release_name": "后台数据看板 v1",
        "released_at": "2026-06-08T03:59:31+08:00",
        "commit": "1aa917b",
    },
    {
        "app_version": "v1.8",
        "release_id": "v1.8-year-filter-promo",
        "release_name": "豆瓣已看标记年份筛选与推广素材",
        "released_at": "2026-06-09T20:45:46+08:00",
        "commit": "6ec8572",
    },
    {
        "app_version": "v1.9",
        "release_id": "v1.9-conversion-ui",
        "release_name": "首页与结果页转化优化",
        "released_at": "2026-06-11T14:56:14+08:00",
        "commit": "c731491",
    },
    {
        "app_version": "v2.0",
        "release_id": "v2.0-admin-v2-ab",
        "release_name": "后台看板 v2 与 A/B 实验基础设施",
        "released_at": "2026-06-12T02:12:39+08:00",
        "commit": "0c8352b",
    },
    {
        "app_version": "v2.1",
        "release_id": "v2.1-instrumentation-dashboard",
        "release_name": "新版埋点与后台看板优化",
        "released_at": "2026-06-13T14:01:48+08:00",
        "commit": "4e7b66e",
    },
    {
        "app_version": "v2.2",
        "release_id": "v2.2-fandom-lists",
        "release_name": "新增王家卫/新海诚/迪士尼片单",
        "released_at": "2026-06-13T15:03:41+08:00",
        "commit": "6133044",
    },
    {
        "app_version": "v2.3",
        "release_id": "v2.3-home-load-version-analytics",
        "release_name": "首页加载优化与版本分析",
        "released_at": "2026-06-13T21:42:19+08:00",
        "commit": "5508735",
    },
    {
        "app_version": "v2.4",
        "release_id": "v2.4-version-dashboard",
        "release_name": "后台看板版本数据分析",
        "released_at": "2026-06-13T22:14:02+08:00",
        "commit": "abb13d0",
    },
    {
        "app_version": "v2.5",
        "release_id": "v2.5-dashboard-social-fix",
        "release_name": "后台缺失值修正与同好联系方式",
        "released_at": "2026-06-13T23:43:43+08:00",
        "commit": "5294b59",
    },
    {
        "app_version": "v2.6",
        "release_id": "v2.6-result-peer-entry",
        "release_name": "结果页好友推荐入口优化",
        "released_at": "2026-06-14T01:10:20+08:00",
        "commit": "",
    },
    {
        "app_version": "v2.7",
        "release_id": "v2.7-douban-media-filter-edit-preview",
        "release_name": "豆瓣已看类型筛选与片单预编辑",
        "released_at": "2026-06-17T18:50:06+08:00",
        "commit": "b02bd84",
    },
    {
        "app_version": "v2.8",
        "release_id": "v2.8-admin-million-event-history",
        "release_name": "后台看板百万事件读取",
        "released_at": "2026-06-17T20:38:30+08:00",
        "commit": "de8a00d",
    },
    {
        "app_version": "v2.9",
        "release_id": "v2.9-douban-import-tutorial-link",
        "release_name": "豆瓣导入详细教程入口",
        "released_at": "2026-06-23T19:52:00+08:00",
        "commit": "18132b2",
    },
    {
        "app_version": "v2.10",
        "release_id": "v2.10-builtin-card-poster-experiment",
        "release_name": "轻量片单海报 A/B 实验",
        "released_at": "2026-06-23T22:34:11+08:00",
        "commit": "",
    },
    {
        "app_version": "v3.1",
        "release_id": "v3.1-template-content-stats",
        "release_name": "模板内容统计与冠军榜海报",
        "released_at": "2026-06-24T02:00:01+08:00",
        "commit": "",
    },
    {
        "app_version": "v3.2",
        "release_id": "v3.2-experiment-rollout-dashboard",
        "release_name": "实验收口与后台分析优化",
        "released_at": "2026-06-25T18:22:38+08:00",
        "commit": "",
    },
    {
        "app_version": "v3.4",
        "release_id": "v3.4-post-render-action-experiments",
        "release_name": "渲染后行动率 A/B 实验",
        "released_at": "2026-06-27T03:08:50+08:00",
        "commit": "",
    },
    {
        "app_version": "v3.5",
        "release_id": "v3.5-post-render-action-creative-experiments",
        "release_name": "创意型渲染后行动率实验",
        "released_at": "2026-06-27T20:56:19+08:00",
        "commit": "",
    },
    {
        "app_version": "v3.6",
        "release_id": "v3.6-light-list-auto-rotation",
        "release_name": "轻量片单自动排序与轮换",
        "released_at": "2026-06-29T14:21:07+08:00",
        "commit": "556e9e7",
    },
    {
        "app_version": "v3.7",
        "release_id": "v3.7-top100-ranking-poster",
        "release_name": "Top 10 / Top 100 结果海报",
        "released_at": "2026-07-03T16:40:50+08:00",
        "commit": "",
    },
    {
        "app_version": "v3.8",
        "release_id": "v3.8-abtest-funnel-recovery",
        "release_name": "漏斗修复与新一轮 A/B 实验",
        "released_at": "2026-07-24T18:09:16+08:00",
        "commit": "401a63b",
    },
    {
        "app_version": "v3.9",
        "release_id": "v3.9-english-core-flow",
        "release_name": "中英文切换与英文核心流程",
        "released_at": "2026-07-27T20:56:52+08:00",
        "commit": "5e0aa48",
    },
    {
        "app_version": APP_VERSION,
        "release_id": APP_RELEASE_ID,
        "release_name": APP_RELEASE_NAME,
        "released_at": APP_RELEASED_AT,
        "commit": "",
    },
]


def parse_release_datetime(value: Any) -> Optional[datetime]:
    text = str(value or "").strip()
    if not text:
        return None
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def _sorted_releases() -> list[Dict[str, str]]:
    return sorted(RELEASE_TIMELINE, key=lambda item: parse_release_datetime(item.get("released_at")) or datetime.min.replace(tzinfo=timezone.utc))


def get_current_release_context() -> Dict[str, str]:
    return {
        "app_version": APP_VERSION,
        "release_id": APP_RELEASE_ID,
        "release_name": APP_RELEASE_NAME,
        "released_at": APP_RELEASED_AT,
    }


def get_release_by_version(app_version: str) -> Optional[Dict[str, str]]:
    version = str(app_version or "").strip()
    for release in RELEASE_TIMELINE:
        if release.get("app_version") == version:
            return dict(release)
    return None


def get_release_for_timestamp(value: Any) -> Dict[str, str]:
    event_time = parse_release_datetime(value)
    releases = _sorted_releases()
    if not releases:
        return get_current_release_context()
    if event_time is None:
        return dict(releases[-1])

    current = releases[0]
    for release in releases:
        release_time = parse_release_datetime(release.get("released_at"))
        if release_time and release_time <= event_time:
            current = release
        elif release_time and release_time > event_time:
            break
    return dict(current)


def get_release_for_event(event: Dict[str, Any]) -> Dict[str, str]:
    payload = event.get("payload") if isinstance(event.get("payload"), dict) else {}
    explicit = get_release_by_version(str(payload.get("app_version") or ""))
    if explicit:
        return explicit
    return get_release_for_timestamp(event.get("created_at"))


def release_label(release: Dict[str, Any]) -> str:
    version = str(release.get("app_version") or "").strip()
    name = str(release.get("release_name") or "").strip()
    return f"{version} · {name}" if name else version


def iter_releases() -> Iterable[Dict[str, str]]:
    return _sorted_releases()
