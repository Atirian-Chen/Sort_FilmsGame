from __future__ import annotations

import uuid
from collections import Counter
from datetime import date, datetime, timedelta, timezone
from statistics import median
from typing import Any, Dict, List, Optional, Tuple

import requests
import streamlit as st


EVENT_PAGE_VIEW = "page_view"
EVENT_CHALLENGE_OPENED = "challenge_opened"
EVENT_RANKING_STARTED = "ranking_started"
EVENT_RANKING_COMPLETED = "ranking_completed"
EVENT_POSTER_DOWNLOADED = "poster_downloaded"
EVENT_SHARE_LINK_COPIED = "share_link_copied"

TRACKED_EVENTS = [
    EVENT_PAGE_VIEW,
    EVENT_CHALLENGE_OPENED,
    EVENT_RANKING_STARTED,
    EVENT_RANKING_COMPLETED,
    EVENT_POSTER_DOWNLOADED,
    EVENT_SHARE_LINK_COPIED,
]

DEFAULT_PUBLIC_APP_URL = "https://sortfilmsgamegit.streamlit.app"
ADMIN_EVENT_SELECT = "event_name,created_at,session_id,challenge_id,template_id,mode,source_channel,payload"

EVENT_LABELS = {
    EVENT_PAGE_VIEW: "访问",
    EVENT_CHALLENGE_OPENED: "打开片单",
    EVENT_RANKING_STARTED: "开始整理",
    EVENT_RANKING_COMPLETED: "完成名单",
    EVENT_POSTER_DOWNLOADED: "下载海报",
    EVENT_SHARE_LINK_COPIED: "复制分享",
}

MAIN_FUNNEL_STEPS = [
    (EVENT_PAGE_VIEW, "访问"),
    (EVENT_RANKING_STARTED, "开始整理"),
    (EVENT_RANKING_COMPLETED, "完成名单"),
    (EVENT_SHARE_LINK_COPIED, "复制分享"),
    (EVENT_POSTER_DOWNLOADED, "下载海报"),
]

SHARED_FUNNEL_STEPS = [
    (EVENT_CHALLENGE_OPENED, "打开片单"),
    (EVENT_RANKING_STARTED, "开始整理"),
    (EVENT_RANKING_COMPLETED, "完成名单"),
    (EVENT_SHARE_LINK_COPIED, "复制分享"),
]


def get_secret(name: str, default: str = "") -> str:
    try:
        value = st.secrets.get(name, default)
    except Exception:
        return default
    return str(value or default).strip()


def get_supabase_config() -> Tuple[str, str]:
    url = get_secret("SUPABASE_URL")
    key = get_secret("SUPABASE_ANON_KEY")
    return url.rstrip("/"), key


def analytics_enabled() -> bool:
    url, key = get_supabase_config()
    return bool(url and key)


def get_admin_token() -> str:
    return get_secret("ADMIN_DASHBOARD_TOKEN")


def get_public_app_url() -> str:
    return (get_secret("PUBLIC_APP_URL") or DEFAULT_PUBLIC_APP_URL).rstrip("/")


def get_session_id() -> str:
    if "anon_session_id" not in st.session_state:
        st.session_state["anon_session_id"] = uuid.uuid4().hex
    return str(st.session_state["anon_session_id"])


def sanitize_payload(payload: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    if not payload:
        return {}

    blocked_keys = {
        "items",
        "options",
        "ranked",
        "ranking",
        "source_options",
        "custom_options",
        "user_name",
    }
    safe: Dict[str, Any] = {}
    for key, value in payload.items():
        if key in blocked_keys:
            continue
        if isinstance(value, (str, int, float, bool)) or value is None:
            safe[key] = value
        elif isinstance(value, list):
            safe[key] = [item for item in value if isinstance(item, (str, int, float, bool))][:20]
        elif isinstance(value, dict):
            safe[key] = {
                str(k): v
                for k, v in value.items()
                if isinstance(v, (str, int, float, bool)) and str(k) not in blocked_keys
            }
    return safe


def supabase_headers(prefer: str = "") -> Dict[str, str]:
    _, key = get_supabase_config()
    headers = {
        "apikey": key,
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
    }
    if prefer:
        headers["Prefer"] = prefer
    return headers


def supabase_rest_url(table: str) -> str:
    url, _ = get_supabase_config()
    return f"{url}/rest/v1/{table}"


def supabase_request(method: str, table: str, *, params: Optional[Dict[str, str]] = None, json_body: Any = None, prefer: str = "") -> Any:
    if not analytics_enabled():
        return None
    try:
        response = requests.request(
            method,
            supabase_rest_url(table),
            params=params,
            json=json_body,
            headers=supabase_headers(prefer),
            timeout=8,
        )
        response.raise_for_status()
        if response.text:
            return response.json()
        return None
    except Exception:
        return None


def track_event(
    event_name: str,
    *,
    challenge_id: str = "",
    mode: str = "",
    template_id: str = "",
    source_channel: str = "",
    payload: Optional[Dict[str, Any]] = None,
) -> bool:
    if event_name not in TRACKED_EVENTS or not analytics_enabled():
        return False

    body = {
        "event_name": event_name,
        "session_id": get_session_id(),
        "challenge_id": challenge_id or None,
        "mode": mode or None,
        "template_id": template_id or None,
        "source_channel": source_channel or None,
        "payload": sanitize_payload(payload),
    }
    result = supabase_request("POST", "analytics_events", json_body=body, prefer="return=minimal")
    return result is not None or analytics_enabled()


def track_once(key: str, event_name: str, **kwargs: Any) -> bool:
    state_key = f"tracked_once_{key}"
    if st.session_state.get(state_key):
        return False
    st.session_state[state_key] = True
    return track_event(event_name, **kwargs)


def fetch_recent_events(limit: int = 1000) -> List[Dict[str, Any]]:
    result = supabase_request(
        "GET",
        "analytics_events",
        params={
            "select": ADMIN_EVENT_SELECT,
            "order": "created_at.desc",
            "limit": str(max(1, min(limit, 2000))),
        },
    )
    return result if isinstance(result, list) else []


@st.cache_data(show_spinner=False, ttl=300)
def fetch_all_events(page_size: int = 1000, max_rows: int = 50000) -> List[Dict[str, Any]]:
    if not analytics_enabled():
        return []

    page_size = max(100, min(page_size, 1000))
    max_rows = max(page_size, max_rows)
    events: List[Dict[str, Any]] = []
    offset = 0
    while offset < max_rows:
        result = supabase_request(
            "GET",
            "analytics_events",
            params={
                "select": ADMIN_EVENT_SELECT,
                "order": "created_at.desc",
                "limit": str(page_size),
                "offset": str(offset),
            },
        )
        if not isinstance(result, list) or not result:
            break
        events.extend(result)
        if len(result) < page_size:
            break
        offset += page_size
    return events[:max_rows]


def _payload(event: Dict[str, Any]) -> Dict[str, Any]:
    payload = event.get("payload")
    return payload if isinstance(payload, dict) else {}


def _event_date(event: Dict[str, Any]) -> Optional[date]:
    value = str(event.get("created_at", ""))[:10]
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None


def _number(value: Any) -> Optional[float]:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value)
        except ValueError:
            return None
    return None


def _avg(values: List[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def _rate(numerator: int, denominator: int) -> float:
    return numerator / denominator if denominator else 0.0


def _percentile(values: List[float], percentile: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    position = (len(ordered) - 1) * percentile
    lower = int(position)
    upper = min(lower + 1, len(ordered) - 1)
    weight = position - lower
    return ordered[lower] * (1 - weight) + ordered[upper] * weight


def _payload_numbers(events: List[Dict[str, Any]], event_name: str, key: str) -> List[float]:
    values: List[float] = []
    for event in events:
        if event.get("event_name") != event_name:
            continue
        value = _number(_payload(event).get(key))
        if value is not None:
            values.append(value)
    return values


def _format_percent(value: float) -> str:
    return f"{value:.1%}"


def filter_events_by_date(
    events: List[Dict[str, Any]],
    start_date: Optional[date],
    end_date: Optional[date],
) -> List[Dict[str, Any]]:
    filtered: List[Dict[str, Any]] = []
    for event in events:
        current = _event_date(event)
        if current is None:
            continue
        if start_date and current < start_date:
            continue
        if end_date and current > end_date:
            continue
        filtered.append(event)
    return filtered


def available_event_date_range(events: List[Dict[str, Any]]) -> Tuple[Optional[date], Optional[date]]:
    dates = [event_date for event in events if (event_date := _event_date(event))]
    if not dates:
        return None, None
    return min(dates), max(dates)


def build_admin_summary(events: List[Dict[str, Any]]) -> Dict[str, Any]:
    counts = Counter(str(event.get("event_name") or "") for event in events)
    sessions = {str(event.get("session_id")) for event in events if event.get("session_id")}
    completed = counts.get(EVENT_RANKING_COMPLETED, 0)
    started = counts.get(EVENT_RANKING_STARTED, 0)
    page_views = counts.get(EVENT_PAGE_VIEW, 0)
    copied = counts.get(EVENT_SHARE_LINK_COPIED, 0)
    posters = counts.get(EVENT_POSTER_DOWNLOADED, 0)

    comparisons = _payload_numbers(events, EVENT_RANKING_COMPLETED, "comparisons")
    totals = _payload_numbers(events, EVENT_RANKING_COMPLETED, "total")
    ranked_counts = _payload_numbers(events, EVENT_RANKING_COMPLETED, "ranked_count")
    skipped_counts = _payload_numbers(events, EVENT_RANKING_COMPLETED, "skipped_count")
    defers = _payload_numbers(events, EVENT_RANKING_COMPLETED, "defers")

    started_events = [event for event in events if event.get("event_name") == EVENT_RANKING_STARTED]
    blind_count = sum(1 for event in started_events if _payload(event).get("blind_mode") is True)
    shuffle_count = sum(1 for event in started_events if _payload(event).get("side_shuffle") is True)
    seed_count = sum(1 for event in started_events if _payload(event).get("has_seed") is True)
    shared_count = sum(1 for event in started_events if _payload(event).get("source") == "shared")

    return {
        "total_events": len(events),
        "unique_sessions": len(sessions),
        "counts": dict(counts),
        "page_views": page_views,
        "started": started,
        "completed": completed,
        "copied": copied,
        "posters": posters,
        "challenge_opened": counts.get(EVENT_CHALLENGE_OPENED, 0),
        "start_rate": _rate(started, page_views),
        "completion_rate": _rate(completed, started),
        "share_rate": _rate(copied, completed),
        "poster_rate": _rate(posters, completed),
        "avg_comparisons": _avg(comparisons),
        "median_comparisons": median(comparisons) if comparisons else 0.0,
        "p75_comparisons": _percentile(comparisons, 0.75),
        "p90_comparisons": _percentile(comparisons, 0.90),
        "avg_total": _avg(totals),
        "avg_ranked_count": _avg(ranked_counts),
        "avg_skipped_count": _avg(skipped_counts),
        "avg_defers": _avg(defers),
        "blind_mode_rate": _rate(blind_count, started),
        "side_shuffle_rate": _rate(shuffle_count, started),
        "seed_rate": _rate(seed_count, started),
        "shared_source_rate": _rate(shared_count, started),
    }


def build_funnel_rows(events: List[Dict[str, Any]], steps: List[Tuple[str, str]]) -> List[Dict[str, Any]]:
    counts = Counter(str(event.get("event_name") or "") for event in events)
    rows: List[Dict[str, Any]] = []
    first_count = counts.get(steps[0][0], 0) if steps else 0
    previous_count = 0
    for index, (event_name, label) in enumerate(steps):
        count = counts.get(event_name, 0)
        rows.append(
            {
                "step": label,
                "event_name": event_name,
                "count": count,
                "step_rate": 1.0 if index == 0 else _rate(count, previous_count),
                "overall_rate": 1.0 if index == 0 else _rate(count, first_count),
            }
        )
        previous_count = count
    return rows


def build_daily_metrics(events: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    buckets: Dict[str, Counter] = {}
    for event in events:
        event_date = _event_date(event)
        if event_date is None:
            continue
        key = event_date.isoformat()
        buckets.setdefault(key, Counter())
        buckets[key][str(event.get("event_name") or "")] += 1

    if not buckets:
        return []

    start = date.fromisoformat(min(buckets))
    end = date.fromisoformat(max(buckets))
    fill_all_dates = (end - start).days <= 370
    dates: List[date]
    if fill_all_dates:
        dates = [start + timedelta(days=offset) for offset in range((end - start).days + 1)]
    else:
        dates = [date.fromisoformat(value) for value in sorted(buckets)]

    rows: List[Dict[str, Any]] = []
    for current in dates:
        key = current.isoformat()
        counts = buckets.get(key, Counter())
        page_views = counts.get(EVENT_PAGE_VIEW, 0)
        started = counts.get(EVENT_RANKING_STARTED, 0)
        completed = counts.get(EVENT_RANKING_COMPLETED, 0)
        copied = counts.get(EVENT_SHARE_LINK_COPIED, 0)
        posters = counts.get(EVENT_POSTER_DOWNLOADED, 0)
        rows.append(
            {
                "date": key,
                EVENT_PAGE_VIEW: page_views,
                EVENT_CHALLENGE_OPENED: counts.get(EVENT_CHALLENGE_OPENED, 0),
                EVENT_RANKING_STARTED: started,
                EVENT_RANKING_COMPLETED: completed,
                EVENT_SHARE_LINK_COPIED: copied,
                EVENT_POSTER_DOWNLOADED: posters,
                "start_rate": _rate(started, page_views),
                "completion_rate": _rate(completed, started),
                "share_rate": _rate(copied, completed),
                "poster_rate": _rate(posters, completed),
            }
        )
    return rows


def _last_seen(events: List[Dict[str, Any]]) -> str:
    values = [str(event.get("created_at") or "") for event in events if event.get("created_at")]
    return max(values) if values else ""


def build_group_metrics(
    events: List[Dict[str, Any]],
    group_key: str,
    *,
    label_key: str,
    include_unknown: bool = False,
    include_winners: bool = False,
    top_n: int = 30,
) -> List[Dict[str, Any]]:
    grouped: Dict[str, List[Dict[str, Any]]] = {}
    for event in events:
        value = event.get(group_key)
        if not value:
            if not include_unknown:
                continue
            value = "未标记"
        grouped.setdefault(str(value), []).append(event)

    rows: List[Dict[str, Any]] = []
    for value, group_events in grouped.items():
        summary = build_admin_summary(group_events)
        completed_events = [event for event in group_events if event.get("event_name") == EVENT_RANKING_COMPLETED]
        winners = Counter(str(_payload(event).get("winner")) for event in completed_events if _payload(event).get("winner"))
        winner_text = "，".join(f"{name}({count})" for name, count in winners.most_common(3))
        row = {
            label_key: value,
            "total_events": summary["total_events"],
            "page_views": summary["page_views"],
            "challenge_opened": summary["challenge_opened"],
            "started": summary["started"],
            "completed": summary["completed"],
            "copied": summary["copied"],
            "posters": summary["posters"],
            "completion_rate": summary["completion_rate"],
            "share_rate": summary["share_rate"],
            "poster_rate": summary["poster_rate"],
            "avg_comparisons": summary["avg_comparisons"],
            "avg_total": summary["avg_total"],
            "last_seen": _last_seen(group_events),
        }
        if include_winners:
            row["top_winners"] = winner_text
        rows.append(row)

    rows.sort(key=lambda item: (int(item.get("completed", 0)), int(item.get("started", 0)), int(item.get("total_events", 0))), reverse=True)
    return rows[:top_n]


def build_payload_value_counts(
    events: List[Dict[str, Any]],
    event_name: str,
    payload_key: str,
    *,
    label_key: str,
    include_empty: bool = False,
    top_n: int = 20,
) -> List[Dict[str, Any]]:
    counter: Counter = Counter()
    for event in events:
        if event.get("event_name") != event_name:
            continue
        value = _payload(event).get(payload_key)
        if value in (None, ""):
            if not include_empty:
                continue
            value = "未标记"
        counter[str(value)] += 1
    return [{label_key: value, "count": count} for value, count in counter.most_common(top_n)]


def build_top_k_distribution(events: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    counter: Counter = Counter()
    for event in events:
        if event.get("event_name") != EVENT_RANKING_STARTED:
            continue
        value = _payload(event).get("top_k")
        counter["完整排序" if value in (None, "", 0) else f"Top {value}"] += 1
    return [{"top_k": value, "count": count} for value, count in counter.most_common(20)]


def build_histogram(values: List[float], buckets: List[float], *, label_key: str = "range") -> List[Dict[str, Any]]:
    if not values:
        return []
    rows: List[Dict[str, Any]] = []
    lower = 0.0
    for upper in buckets:
        count = sum(1 for value in values if lower <= value < upper)
        rows.append({label_key: f"{int(lower)}-{int(upper - 1)}", "count": count})
        lower = upper
    count = sum(1 for value in values if value >= lower)
    rows.append({label_key: f"{int(lower)}+", "count": count})
    return rows


def build_numeric_payload_histogram(
    events: List[Dict[str, Any]],
    event_name: str,
    payload_key: str,
    buckets: List[float],
    *,
    label_key: str = "range",
) -> List[Dict[str, Any]]:
    return build_histogram(_payload_numbers(events, event_name, payload_key), buckets, label_key=label_key)


def build_setting_rows(events: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    started_events = [event for event in events if event.get("event_name") == EVENT_RANKING_STARTED]
    started = len(started_events)
    settings = [
        ("盲排开启", sum(1 for event in started_events if _payload(event).get("blind_mode") is True)),
        ("左右随机开启", sum(1 for event in started_events if _payload(event).get("side_shuffle") is True)),
        ("使用顺序口令", sum(1 for event in started_events if _payload(event).get("has_seed") is True)),
        ("共享片单入口", sum(1 for event in started_events if _payload(event).get("source") == "shared")),
    ]
    return [{"setting": name, "count": count, "rate": _rate(count, started)} for name, count in settings]


def summarize_payload(payload: Dict[str, Any]) -> str:
    ordered_keys = [
        "total",
        "top_k",
        "ranked_count",
        "skipped_count",
        "comparisons",
        "defers",
        "surface",
        "poster_type",
        "blind_mode",
        "side_shuffle",
        "source",
        "winner",
    ]
    parts = []
    for key in ordered_keys:
        if key in payload and payload.get(key) not in (None, ""):
            parts.append(f"{key}={payload.get(key)}")
    return ", ".join(parts)


def flatten_event_for_table(event: Dict[str, Any]) -> Dict[str, Any]:
    session_id = str(event.get("session_id") or "")
    payload = _payload(event)
    return {
        "created_at": event.get("created_at") or "",
        "event": EVENT_LABELS.get(str(event.get("event_name") or ""), str(event.get("event_name") or "")),
        "event_name": event.get("event_name") or "",
        "session": session_id[-8:] if session_id else "",
        "mode": event.get("mode") or "",
        "source_channel": event.get("source_channel") or "",
        "template_id": event.get("template_id") or "",
        "challenge_id": event.get("challenge_id") or "",
        "payload_summary": summarize_payload(payload),
    }


def build_event_table_rows(events: List[Dict[str, Any]], limit: int = 500) -> List[Dict[str, Any]]:
    sorted_events = sorted(events, key=lambda event: str(event.get("created_at") or ""), reverse=True)
    return [flatten_event_for_table(event) for event in sorted_events[:limit]]


def build_admin_insights(events: List[Dict[str, Any]]) -> List[str]:
    if not events:
        return ["当前筛选范围内还没有事件。"]

    summary = build_admin_summary(events)
    insights = [
        f"主漏斗完成率为 {_format_percent(summary['completion_rate'])}，开始率为 {_format_percent(summary['start_rate'])}。",
    ]

    funnel = build_funnel_rows(events, MAIN_FUNNEL_STEPS)
    drops = []
    for previous, current in zip(funnel, funnel[1:]):
        lost = int(previous["count"]) - int(current["count"])
        drops.append((lost, previous["step"], current["step"], current["step_rate"]))
    if drops:
        lost, from_step, to_step, rate = max(drops, key=lambda item: item[0])
        insights.append(f"最大流失发生在「{from_step} -> {to_step}」，流失 {lost} 次，单步转化率 {_format_percent(rate)}。")

    source_rows = build_group_metrics(events, "source_channel", label_key="source_channel", include_unknown=True, top_n=10)
    qualified_sources = [row for row in source_rows if int(row.get("started", 0)) >= 3]
    if qualified_sources:
        best_source = max(qualified_sources, key=lambda row: float(row.get("completion_rate", 0)))
        insights.append(
            f"完成率最高的来源是「{best_source['source_channel']}」，完成率 {_format_percent(float(best_source['completion_rate']))}。"
        )

    template_rows = build_group_metrics(events, "template_id", label_key="template_id", include_winners=True, top_n=10)
    qualified_templates = [row for row in template_rows if int(row.get("started", 0)) >= 2]
    if qualified_templates:
        best_template = max(qualified_templates, key=lambda row: float(row.get("completion_rate", 0)))
        insights.append(
            f"完成率最高的模板是「{best_template['template_id']}」，完成 {int(best_template['completed'])} 次。"
        )

    if summary["completed"]:
        insights.append(
            f"完成用户平均作出 {summary['avg_comparisons']:.1f} 次取舍，P90 为 {summary['p90_comparisons']:.0f} 次。"
        )

    share_rows = build_payload_value_counts(events, EVENT_SHARE_LINK_COPIED, "surface", label_key="surface", include_empty=True, top_n=1)
    if share_rows:
        top_share = share_rows[0]
        insights.append(f"最常见的分享动作是「{top_share['surface']}」，共 {top_share['count']} 次。")

    return insights[:6]


def fetch_public_metrics() -> Dict[str, Any]:
    if not analytics_enabled():
        return {"enabled": False, "completed": 0, "today_users": 0, "avg_comparisons": 0.0}

    events = fetch_recent_events(1000)
    completed = [event for event in events if event.get("event_name") == EVENT_RANKING_COMPLETED]
    today = datetime.now(timezone.utc).date()
    today_sessions = {
        event.get("session_id") or event.get("payload", {}).get("session_hint") or event.get("challenge_id") or event.get("created_at")
        for event in events
        if str(event.get("created_at", ""))[:10] == today.isoformat()
    }
    comparisons = [
        float(event.get("payload", {}).get("comparisons", 0))
        for event in completed
        if isinstance(event.get("payload", {}).get("comparisons"), (int, float))
    ]
    avg = sum(comparisons) / len(comparisons) if comparisons else 0.0
    return {
        "enabled": True,
        "completed": len(completed),
        "today_users": len(today_sessions),
        "avg_comparisons": avg,
    }


def fetch_admin_metrics() -> Dict[str, Any]:
    events = fetch_all_events()
    counts = Counter(event.get("event_name") for event in events)
    template_counts = Counter(event.get("template_id") for event in events if event.get("template_id"))
    challenge_counts = Counter(event.get("challenge_id") for event in events if event.get("challenge_id"))
    started = max(1, counts.get(EVENT_RANKING_STARTED, 0))
    completed = counts.get(EVENT_RANKING_COMPLETED, 0)
    copied = counts.get(EVENT_SHARE_LINK_COPIED, 0)
    return {
        "enabled": analytics_enabled(),
        "counts": dict(counts),
        "completion_rate": completed / started,
        "share_rate": copied / max(1, completed),
        "top_templates": template_counts.most_common(8),
        "top_challenges": challenge_counts.most_common(8),
        "recent_events": events[:120],
    }
