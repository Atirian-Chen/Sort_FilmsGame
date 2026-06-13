from __future__ import annotations

import uuid
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timedelta, timezone
from statistics import median
from typing import Any, Callable, Dict, Iterable, List, Optional, Set, Tuple, Union

import requests
import streamlit as st

from release_history import get_current_release_context, get_release_for_event, release_label


EVENT_VISIT = "visit"
EVENT_LIST_OPENED = "list_opened"
EVENT_LIST_SELECTED = "list_selected"
EVENT_SORTING_STARTED = "sorting_started"
EVENT_COMPARISON_MADE = "comparison_made"
EVENT_RANKING_COMPLETED = "ranking_completed"
EVENT_POSTER_DOWNLOADED = "poster_downloaded"
EVENT_SHARE_COPIED = "share_copied"
EVENT_RESULT_VIEWED = "result_viewed"
EVENT_QR_VIEWED = "qr_viewed"
EVENT_HOME_CONTENT_RENDERED = "home_content_rendered"

# Backward-compatible names used by older app code and historical rows.
LEGACY_EVENT_PAGE_VIEW = "page_view"
LEGACY_EVENT_CHALLENGE_OPENED = "challenge_opened"
LEGACY_EVENT_RANKING_STARTED = "ranking_started"
LEGACY_EVENT_SHARE_LINK_COPIED = "share_link_copied"

EVENT_PAGE_VIEW = EVENT_VISIT
EVENT_CHALLENGE_OPENED = EVENT_LIST_OPENED
EVENT_RANKING_STARTED = EVENT_SORTING_STARTED
EVENT_SHARE_LINK_COPIED = EVENT_SHARE_COPIED

LEGACY_EVENT_MAP = {
    LEGACY_EVENT_PAGE_VIEW: EVENT_VISIT,
    LEGACY_EVENT_CHALLENGE_OPENED: EVENT_LIST_OPENED,
    LEGACY_EVENT_RANKING_STARTED: EVENT_SORTING_STARTED,
    LEGACY_EVENT_SHARE_LINK_COPIED: EVENT_SHARE_COPIED,
}

TRACKED_EVENTS = [
    EVENT_VISIT,
    EVENT_LIST_OPENED,
    EVENT_LIST_SELECTED,
    EVENT_SORTING_STARTED,
    EVENT_COMPARISON_MADE,
    EVENT_RANKING_COMPLETED,
    EVENT_POSTER_DOWNLOADED,
    EVENT_SHARE_COPIED,
    EVENT_RESULT_VIEWED,
    EVENT_QR_VIEWED,
    EVENT_HOME_CONTENT_RENDERED,
]
LEGACY_TRACKED_EVENTS = list(LEGACY_EVENT_MAP)

DEFAULT_PUBLIC_APP_URL = "https://sortfilmsgamegit.streamlit.app"
ADMIN_EVENT_SELECT = "event_name,created_at,session_id,challenge_id,template_id,mode,source_channel,payload"

EVENT_LABELS = {
    EVENT_VISIT: "访问",
    EVENT_LIST_OPENED: "打开片单",
    EVENT_LIST_SELECTED: "选择片单",
    EVENT_SORTING_STARTED: "开始整理",
    EVENT_COMPARISON_MADE: "完成一次取舍",
    EVENT_RANKING_COMPLETED: "完成名单",
    EVENT_POSTER_DOWNLOADED: "下载海报",
    EVENT_SHARE_COPIED: "复制分享",
    EVENT_RESULT_VIEWED: "查看结果",
    EVENT_QR_VIEWED: "查看二维码",
    EVENT_HOME_CONTENT_RENDERED: "首页内容已渲染",
    LEGACY_EVENT_PAGE_VIEW: "访问",
    LEGACY_EVENT_CHALLENGE_OPENED: "打开片单",
    LEGACY_EVENT_RANKING_STARTED: "开始整理",
    LEGACY_EVENT_SHARE_LINK_COPIED: "复制分享",
}

MAIN_FUNNEL_STEPS: List[Tuple[Union[str, Tuple[str, ...]], str]] = [
    (EVENT_VISIT, "访问"),
    ((EVENT_LIST_OPENED, EVENT_LIST_SELECTED), "打开/选择片单"),
    (EVENT_SORTING_STARTED, "开始整理"),
    (EVENT_RANKING_COMPLETED, "完成名单"),
    ((EVENT_SHARE_COPIED, EVENT_POSTER_DOWNLOADED), "复制分享/下载海报"),
]

SHARED_FUNNEL_STEPS: List[Tuple[Union[str, Tuple[str, ...]], str]] = [
    (EVENT_LIST_OPENED, "打开片单"),
    (EVENT_SORTING_STARTED, "开始整理"),
    (EVENT_RANKING_COMPLETED, "完成名单"),
    ((EVENT_SHARE_COPIED, EVENT_POSTER_DOWNLOADED), "复制分享/下载海报"),
]

CURRENT_TOTAL_FUNNEL_STEPS: List[Tuple[Union[str, Tuple[str, ...]], str]] = [
    (EVENT_HOME_CONTENT_RENDERED, "首页内容已渲染"),
    ((EVENT_LIST_OPENED, EVENT_LIST_SELECTED), "打开/选择片单"),
    (EVENT_SORTING_STARTED, "实际开始整理"),
    (EVENT_RANKING_COMPLETED, "完成名单"),
    ((EVENT_SHARE_COPIED, EVENT_POSTER_DOWNLOADED), "分享/下载海报"),
]

LIGHT_LIST_FUNNEL_STEPS: List[Tuple[Union[str, Tuple[str, ...]], str]] = [
    (EVENT_LIST_OPENED, "打开轻量片单"),
    (EVENT_SORTING_STARTED, "实际开始整理"),
    (EVENT_RANKING_COMPLETED, "完成名单"),
    ((EVENT_SHARE_COPIED, EVENT_POSTER_DOWNLOADED), "分享/下载海报"),
]

HEAVY_LIST_FUNNEL_STEPS: List[Tuple[Union[str, Tuple[str, ...]], str]] = [
    (EVENT_LIST_SELECTED, "进入填参数/配置页"),
    (EVENT_SORTING_STARTED, "实际开始整理"),
    (EVENT_RANKING_COMPLETED, "完成名单"),
    ((EVENT_SHARE_COPIED, EVENT_POSTER_DOWNLOADED), "分享/下载海报"),
]

HOME_ENGAGEMENT_EVENTS = (
    EVENT_LIST_OPENED,
    EVENT_LIST_SELECTED,
    EVENT_SORTING_STARTED,
)

HEAVY_MODE_VALUES = {"豆瓣已看", "自备片单", "豆瓣高分"}
_ANALYTICS_EXECUTOR: Optional[ThreadPoolExecutor] = None


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


def canonical_event_name(event_name: Any) -> str:
    raw = str(event_name or "").strip()
    return LEGACY_EVENT_MAP.get(raw, raw)


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


def _format_percent(value: float) -> str:
    return f"{value:.1%}"


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


def _event_matches(event: Dict[str, Any], event_name: str) -> bool:
    return canonical_event_name(event.get("event_name")) == event_name


def _payload_number(payload: Dict[str, Any], *keys: str) -> Optional[float]:
    for key in keys:
        value = _number(payload.get(key))
        if value is not None:
            return value
    return None


def _payload_numbers(events: List[Dict[str, Any]], event_name: str, *keys: str) -> List[float]:
    values: List[float] = []
    for event in events:
        if not _event_matches(event, event_name):
            continue
        value = _payload_number(_payload(event), *keys)
        if value is not None:
            values.append(value)
    return values


def _safe_text(value: Any, default: str = "") -> str:
    text = str(value or "").strip()
    return text if text else default


def _clean_source(value: Any) -> str:
    text = _safe_text(value)
    return text[:80] if text else ""


def _event_source(event: Dict[str, Any]) -> str:
    payload = _payload(event)
    source = (
        _clean_source(payload.get("source"))
        or _clean_source(event.get("source_channel"))
        or _clean_source(payload.get("utm_source"))
        or "direct / unknown"
    )
    return source


def _event_utm_source(event: Dict[str, Any]) -> str:
    payload = _payload(event)
    return _clean_source(payload.get("utm_source")) or _event_source(event)


def _event_utm_medium(event: Dict[str, Any]) -> str:
    return _clean_source(_payload(event).get("utm_medium")) or "unknown"


def _event_utm_campaign(event: Dict[str, Any]) -> str:
    return _clean_source(_payload(event).get("utm_campaign")) or "unknown"


def _event_list_id(event: Dict[str, Any]) -> str:
    payload = _payload(event)
    return (
        _safe_text(payload.get("list_id"))
        or _safe_text(event.get("challenge_id"))
        or _safe_text(event.get("template_id"))
        or _safe_text(event.get("mode"))
        or "unknown"
    )


def _event_group_value(event: Dict[str, Any], group_key: str, include_unknown: bool) -> str:
    payload = _payload(event)
    if group_key in ("source", "source_channel"):
        value = _event_source(event)
    elif group_key == "utm_source":
        value = _event_utm_source(event)
    elif group_key == "utm_medium":
        value = _event_utm_medium(event)
    elif group_key == "utm_campaign":
        value = _event_utm_campaign(event)
    elif group_key in ("list_id", "challenge_id"):
        value = _event_list_id(event)
    elif group_key == "experiment_id":
        value = _safe_text(payload.get("experiment_id"))
    elif group_key == "variant_id":
        value = _safe_text(payload.get("variant_id"))
    elif group_key in payload:
        value = _safe_text(payload.get(group_key))
    else:
        value = _safe_text(event.get(group_key))

    if not value and include_unknown:
        return "unknown"
    return value


def _detect_device_type_from_headers() -> str:
    user_agent = ""
    try:
        headers = getattr(st, "context", None).headers
        user_agent = str(headers.get("user-agent", "") or "")
    except Exception:
        user_agent = ""
    lower = user_agent.lower()
    if not lower:
        return "unknown"
    if any(token in lower for token in ("mobile", "iphone", "android", "ipad", "phone")):
        return "mobile"
    return "desktop"


def _active_experiment_payload() -> Dict[str, Any]:
    try:
        from experiments import get_experiment_event_context

        context = get_experiment_event_context(get_session_id())
    except Exception:
        context = {}
    return context if isinstance(context, dict) else {}


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
        "name",
        "phone",
        "mobile",
        "email",
        "contact",
        "wechat",
        "ip",
        "ip_address",
        "user_agent",
    }
    safe: Dict[str, Any] = {}
    for key, value in payload.items():
        clean_key = str(key)
        if clean_key in blocked_keys:
            continue
        if isinstance(value, (str, int, float, bool)) or value is None:
            safe[clean_key] = value
        elif isinstance(value, list):
            safe[clean_key] = [item for item in value if isinstance(item, (str, int, float, bool))][:20]
        elif isinstance(value, dict):
            nested: Dict[str, Any] = {}
            for nested_key, nested_value in value.items():
                nested_key_text = str(nested_key)
                if nested_key_text in blocked_keys:
                    continue
                if isinstance(nested_value, (str, int, float, bool)) or nested_value is None:
                    nested[nested_key_text] = nested_value
            safe[clean_key] = nested
    return safe


def _event_payload_context(
    *,
    challenge_id: str = "",
    mode: str = "",
    template_id: str = "",
    source_channel: str = "",
    payload: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    safe = sanitize_payload(payload)
    if challenge_id and "list_id" not in safe:
        safe["list_id"] = challenge_id
    if template_id and "template_id" not in safe:
        safe["template_id"] = template_id
    if mode and "mode" not in safe:
        safe["mode"] = mode
    if "source" not in safe:
        safe["source"] = source_channel or "direct / unknown"
    if "device_type" not in safe:
        safe["device_type"] = _detect_device_type_from_headers()

    for key, value in _active_experiment_payload().items():
        safe.setdefault(key, value)
    for key, value in get_current_release_context().items():
        safe.setdefault(key, value)

    if "metadata" not in safe:
        safe["metadata"] = {}
    return safe


def normalize_event(event: Dict[str, Any]) -> Dict[str, Any]:
    normalized = dict(event)
    original_name = str(normalized.get("event_name") or "")
    canonical_name = canonical_event_name(original_name)
    normalized["event_name"] = canonical_name
    payload = sanitize_payload(_payload(normalized))
    if original_name and original_name != canonical_name:
        payload.setdefault("legacy_event_name", original_name)

    if normalized.get("challenge_id") and "list_id" not in payload:
        payload["list_id"] = normalized.get("challenge_id")
    if normalized.get("template_id") and "template_id" not in payload:
        payload["template_id"] = normalized.get("template_id")
    if normalized.get("mode") and "mode" not in payload:
        payload["mode"] = normalized.get("mode")
    if normalized.get("source_channel") and "source" not in payload:
        payload["source"] = normalized.get("source_channel")

    if "comparison_count" not in payload and "comparisons" in payload:
        payload["comparison_count"] = payload.get("comparisons")
    if "list_size" not in payload:
        if "total" in payload:
            payload["list_size"] = payload.get("total")
        elif "item_count" in payload:
            payload["list_size"] = payload.get("item_count")

    payload.setdefault("source", _event_source({"source_channel": normalized.get("source_channel"), "payload": payload}))
    normalized["payload"] = payload
    return normalized


def normalize_events(events: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return [normalize_event(event) for event in events]


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


def get_analytics_executor() -> ThreadPoolExecutor:
    global _ANALYTICS_EXECUTOR
    if _ANALYTICS_EXECUTOR is None:
        _ANALYTICS_EXECUTOR = ThreadPoolExecutor(max_workers=2, thread_name_prefix="analytics-track")
    return _ANALYTICS_EXECUTOR


def _post_analytics_event(endpoint: str, headers: Dict[str, str], body: Dict[str, Any]) -> None:
    try:
        requests.post(endpoint, json=body, headers=headers, timeout=4).raise_for_status()
    except Exception:
        return


def track_event(
    event_name: str,
    *,
    challenge_id: str = "",
    mode: str = "",
    template_id: str = "",
    source_channel: str = "",
    payload: Optional[Dict[str, Any]] = None,
) -> bool:
    canonical_name = canonical_event_name(event_name)
    if canonical_name not in TRACKED_EVENTS or not analytics_enabled():
        return False
    url, key = get_supabase_config()
    if not url or not key:
        return False

    safe_payload = _event_payload_context(
        challenge_id=challenge_id,
        mode=mode,
        template_id=template_id,
        source_channel=source_channel,
        payload=payload,
    )
    body = {
        "event_name": canonical_name,
        "session_id": get_session_id(),
        "challenge_id": challenge_id or None,
        "mode": mode or None,
        "template_id": template_id or None,
        "source_channel": source_channel or safe_payload.get("source") or None,
        "payload": safe_payload,
    }
    endpoint = f"{url}/rest/v1/analytics_events"
    headers = supabase_headers("return=minimal")
    get_analytics_executor().submit(_post_analytics_event, endpoint, headers, body)
    return True


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
    return normalize_events(result) if isinstance(result, list) else []


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
    return normalize_events(events[:max_rows])


def filter_events_by_date(
    events: List[Dict[str, Any]],
    start_date: Optional[date],
    end_date: Optional[date],
) -> List[Dict[str, Any]]:
    filtered: List[Dict[str, Any]] = []
    for event in normalize_events(events):
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
    events = normalize_events(events)
    counts = Counter(str(event.get("event_name") or "") for event in events)
    sessions = {str(event.get("session_id")) for event in events if event.get("session_id")}

    visits = counts.get(EVENT_VISIT, 0)
    list_opened = counts.get(EVENT_LIST_OPENED, 0)
    list_selected = counts.get(EVENT_LIST_SELECTED, 0)
    open_or_select_list = list_opened + list_selected
    started = counts.get(EVENT_SORTING_STARTED, 0)
    completed = counts.get(EVENT_RANKING_COMPLETED, 0)
    copied = counts.get(EVENT_SHARE_COPIED, 0)
    posters = counts.get(EVENT_POSTER_DOWNLOADED, 0)

    comparisons = _payload_numbers(events, EVENT_RANKING_COMPLETED, "comparison_count", "comparisons")
    totals = _payload_numbers(events, EVENT_RANKING_COMPLETED, "list_size", "total", "item_count")
    ranked_counts = _payload_numbers(events, EVENT_RANKING_COMPLETED, "ranked_count")
    skipped_counts = _payload_numbers(events, EVENT_RANKING_COMPLETED, "skipped_count")
    defers = _payload_numbers(events, EVENT_RANKING_COMPLETED, "defers")

    started_events = [event for event in events if _event_matches(event, EVENT_SORTING_STARTED)]
    blind_count = sum(1 for event in started_events if _payload(event).get("blind_mode") is True)
    shuffle_count = sum(1 for event in started_events if _payload(event).get("side_shuffle") is True)
    seed_count = sum(1 for event in started_events if _payload(event).get("has_seed") is True)
    shared_count = sum(
        1
        for event in started_events
        if _payload(event).get("list_source") == "shared" or _payload(event).get("source") == "shared"
    )

    return {
        "total_events": len(events),
        "unique_sessions": len(sessions),
        "counts": dict(counts),
        "visits": visits,
        "page_views": visits,
        "list_opened": list_opened,
        "list_selected": list_selected,
        "open_or_select_list": open_or_select_list,
        "challenge_opened": list_opened,
        "started": started,
        "completed": completed,
        "copied": copied,
        "posters": posters,
        "start_rate": _rate(started, visits),
        "completion_rate": _rate(completed, started),
        "share_rate": _rate(copied, completed),
        "poster_rate": _rate(posters, completed),
        "avg_comparisons": _avg(comparisons),
        "median_comparisons": median(comparisons) if comparisons else 0.0,
        "p75_comparisons": _percentile(comparisons, 0.75),
        "p90_comparisons": _percentile(comparisons, 0.90),
        "avg_total": _avg(totals),
        "avg_list_size": _avg(totals),
        "avg_ranked_count": _avg(ranked_counts),
        "avg_skipped_count": _avg(skipped_counts),
        "avg_defers": _avg(defers),
        "blind_mode_rate": _rate(blind_count, started),
        "side_shuffle_rate": _rate(shuffle_count, started),
        "seed_rate": _rate(seed_count, started),
        "shared_source_rate": _rate(shared_count, started),
    }


def _event_session_id(event: Dict[str, Any]) -> str:
    return str(event.get("session_id") or "").strip()


def _is_legacy_compatible_event(event: Dict[str, Any]) -> bool:
    return bool(_payload(event).get("legacy_event_name"))


def _event_mode(event: Dict[str, Any]) -> str:
    payload = _payload(event)
    return _safe_text(event.get("mode")) or _safe_text(payload.get("mode"))


def _event_route(event: Dict[str, Any]) -> str:
    return _safe_text(_payload(event).get("route"))


def _is_heavy_entry_event(event: Dict[str, Any]) -> bool:
    return _event_matches(event, EVENT_LIST_SELECTED) and _event_mode(event) in HEAVY_MODE_VALUES


def _is_light_entry_event(event: Dict[str, Any]) -> bool:
    return _event_matches(event, EVENT_LIST_OPENED) and _event_route(event) == "list_open"


def _is_home_entry_visit(event: Dict[str, Any]) -> bool:
    if not _event_matches(event, EVENT_VISIT):
        return False
    payload = _payload(event)
    if str(payload.get("route") or "") != "home":
        return False
    return not any(
        bool(payload.get(key))
        for key in ("has_list", "has_payload", "has_import")
    )


def _session_set(events: Iterable[Dict[str, Any]]) -> set:
    return {session_id for event in events if (session_id := _event_session_id(event))}


def build_home_load_metrics(events: List[Dict[str, Any]]) -> Dict[str, Any]:
    events = normalize_events(events)
    home_visit_events = [event for event in events if _is_home_entry_visit(event)]
    rendered_events = [
        event
        for event in events
        if _event_matches(event, EVENT_HOME_CONTENT_RENDERED)
        and str(_payload(event).get("route") or "") == "home"
    ]
    engagement_events = [
        event
        for event in events
        if canonical_event_name(event.get("event_name")) in HOME_ENGAGEMENT_EVENTS
    ]

    visit_sessions = _session_set(home_visit_events)
    rendered_sessions = _session_set(rendered_events) & visit_sessions
    engaged_sessions = _session_set(engagement_events)

    pre_render_lost_sessions = visit_sessions - rendered_sessions - engaged_sessions
    rendered_no_action_sessions = rendered_sessions - engaged_sessions
    rendered_action_sessions = rendered_sessions & engaged_sessions

    matched_rendered_events = [event for event in rendered_events if _event_session_id(event) in rendered_sessions]
    render_times = _payload_numbers(matched_rendered_events, EVENT_HOME_CONTENT_RENDERED, "render_elapsed_ms", "home_render_elapsed_ms")

    return {
        "home_visit_sessions": len(visit_sessions),
        "home_render_event_count": len(rendered_events),
        "home_render_time_count": len(render_times),
        "home_rendered_sessions": len(rendered_sessions),
        "home_engaged_sessions": len(rendered_action_sessions),
        "pre_render_lost_sessions": len(pre_render_lost_sessions),
        "post_render_no_action_sessions": len(rendered_no_action_sessions),
        "render_completion_rate": _rate(len(rendered_sessions), len(visit_sessions)),
        "pre_render_loss_rate": _rate(len(pre_render_lost_sessions), len(visit_sessions)),
        "post_render_no_action_rate": _rate(len(rendered_no_action_sessions), len(rendered_sessions)),
        "post_render_action_rate": _rate(len(rendered_action_sessions), len(rendered_sessions)),
        "avg_render_elapsed_ms": _avg(render_times),
        "p75_render_elapsed_ms": _percentile(render_times, 0.75),
        "p90_render_elapsed_ms": _percentile(render_times, 0.90),
    }


def build_home_load_insight(metrics: Dict[str, Any]) -> str:
    visits = int(metrics.get("home_visit_sessions", 0))
    if not visits:
        return "当前筛选范围内没有普通首页访问，暂时无法判断首页加载流失。"
    if int(metrics.get("home_render_event_count", 0) or 0) <= 0:
        return (
            "当前筛选范围内没有 home_content_rendered 埋点，不能判断首页渲染完成率或加载中流失率。"
            "这通常表示数据来自加入首页加载埋点之前的版本，应解读为没有数据，而不是 0%。"
        )

    pre_render_rate = float(metrics.get("pre_render_loss_rate", 0.0))
    post_render_rate = float(metrics.get("post_render_no_action_rate", 0.0))
    render_rate = float(metrics.get("render_completion_rate", 0.0))
    p90_ms = float(metrics.get("p90_render_elapsed_ms", 0.0))

    if pre_render_rate > post_render_rate and pre_render_rate >= 0.1:
        return (
            f"当前更需要关注首页加载阶段：有 {_format_percent(pre_render_rate)} 的首页访问没有进入内容已渲染事件，"
            f"首页渲染完成率为 {_format_percent(render_rate)}，P90 服务端渲染耗时约 {p90_ms:.0f}ms。"
        )
    if post_render_rate >= 0.1:
        return (
            f"当前主要流失更像发生在看到首页内容之后：{_format_percent(post_render_rate)} 的已渲染 session "
            "没有继续打开/选择片单或开始整理，建议优先检查首屏价值表达、入口顺序和 CTA 成本。"
        )
    return (
        f"当前首页加载诊断较健康：首页渲染完成率为 {_format_percent(render_rate)}，"
        f"渲染后行动率为 {_format_percent(float(metrics.get('post_render_action_rate', 0.0)))}。"
    )


def build_version_metrics(events: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    normalized = normalize_events(events)
    grouped: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    releases: Dict[str, Dict[str, str]] = {}

    for event in normalized:
        release = get_release_for_event(event)
        version = str(release.get("app_version") or "unknown")
        grouped[version].append(event)
        releases[version] = release

    rows: List[Dict[str, Any]] = []
    for version, version_events in grouped.items():
        release = releases.get(version, {})
        sessions = _session_set(version_events)
        visit_sessions = _session_set(event for event in version_events if _event_matches(event, EVENT_VISIT))
        opened_sessions = _session_set(event for event in version_events if _event_matches(event, EVENT_LIST_OPENED))
        selected_sessions = _session_set(event for event in version_events if _event_matches(event, EVENT_LIST_SELECTED))
        started_sessions = _session_set(event for event in version_events if _event_matches(event, EVENT_SORTING_STARTED))
        completed_sessions = _session_set(event for event in version_events if _event_matches(event, EVENT_RANKING_COMPLETED))
        shared_sessions = _session_set(
            event
            for event in version_events
            if _event_matches(event, EVENT_SHARE_COPIED) or _event_matches(event, EVENT_POSTER_DOWNLOADED)
        )
        home_metrics = build_home_load_metrics(version_events)
        rows.append(
            {
                "app_version": version,
                "release_id": release.get("release_id", ""),
                "release_name": release.get("release_name", ""),
                "release_label": release_label(release),
                "released_at": release.get("released_at", ""),
                "commit": release.get("commit", ""),
                "first_event_at": min((str(event.get("created_at") or "") for event in version_events), default=""),
                "last_event_at": max((str(event.get("created_at") or "") for event in version_events), default=""),
                "events": len(version_events),
                "sessions": len(sessions),
                "visit_sessions": len(visit_sessions),
                "home_load_diagnostic_available": int(home_metrics.get("home_render_event_count", 0)) > 0,
                "home_render_event_count": int(home_metrics.get("home_render_event_count", 0)),
                "home_render_time_count": int(home_metrics.get("home_render_time_count", 0)),
                "home_rendered_sessions": int(home_metrics.get("home_rendered_sessions", 0)),
                "home_engaged_sessions": int(home_metrics.get("home_engaged_sessions", 0)),
                "pre_render_lost_sessions": int(home_metrics.get("pre_render_lost_sessions", 0)),
                "post_render_no_action_sessions": int(home_metrics.get("post_render_no_action_sessions", 0)),
                "home_render_rate": float(home_metrics.get("render_completion_rate", 0.0)),
                "pre_render_loss_rate": float(home_metrics.get("pre_render_loss_rate", 0.0)),
                "post_render_action_rate": float(home_metrics.get("post_render_action_rate", 0.0)),
                "post_render_no_action_rate": float(home_metrics.get("post_render_no_action_rate", 0.0)),
                "opened_or_selected_sessions": len(opened_sessions | selected_sessions),
                "started_sessions": len(started_sessions),
                "completed_sessions": len(completed_sessions),
                "shared_sessions": len(shared_sessions),
                "open_or_select_rate": _rate(len(opened_sessions | selected_sessions), len(visit_sessions)),
                "start_rate": _rate(len(started_sessions), len(visit_sessions)),
                "completion_rate": _rate(len(completed_sessions), len(started_sessions)),
                "share_rate": _rate(len(shared_sessions), len(completed_sessions)),
                "avg_render_elapsed_ms": float(home_metrics.get("avg_render_elapsed_ms", 0.0)),
                "p75_render_elapsed_ms": float(home_metrics.get("p75_render_elapsed_ms", 0.0)),
                "p90_render_elapsed_ms": float(home_metrics.get("p90_render_elapsed_ms", 0.0)),
            }
        )

    rows.sort(key=lambda item: parse_sortable_datetime(str(item.get("released_at") or "")), reverse=True)
    return rows


def parse_sortable_datetime(value: str) -> str:
    if not value:
        return ""
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return ""
    return parsed.isoformat()


def _step_event_names(step: Union[str, Tuple[str, ...], List[str]]) -> Tuple[str, ...]:
    if isinstance(step, str):
        return (step,)
    return tuple(str(item) for item in step)


def _event_in_step(event: Dict[str, Any], step: Union[str, Tuple[str, ...], List[str]]) -> bool:
    event_names = _step_event_names(step)
    return canonical_event_name(event.get("event_name")) in event_names


def build_session_funnel_rows(
    events: List[Dict[str, Any]],
    steps: List[Tuple[Union[str, Tuple[str, ...]], str]],
    *,
    current_only: bool = True,
    first_step_filter: Optional[Callable[[Dict[str, Any]], bool]] = None,
) -> List[Dict[str, Any]]:
    normalized = normalize_events(events)
    if current_only:
        normalized = [event for event in normalized if not _is_legacy_compatible_event(event)]

    if not steps:
        return []

    first_spec = steps[0][0]
    first_events = [
        event
        for event in normalized
        if _event_in_step(event, first_spec)
        and (first_step_filter(event) if first_step_filter else True)
    ]
    eligible_sessions = _session_set(first_events)
    previous_sessions: Set[str] = set()
    first_count = len(eligible_sessions)
    rows: List[Dict[str, Any]] = []

    for index, (event_spec, label) in enumerate(steps):
        step_events = [
            event
            for event in normalized
            if _event_in_step(event, event_spec)
            and _event_session_id(event) in eligible_sessions
            and (first_step_filter(event) if index == 0 and first_step_filter else True)
        ]
        step_sessions = _session_set(step_events)
        if index > 0:
            step_sessions = previous_sessions & step_sessions

        count = len(step_sessions)
        previous_count = first_count if index == 0 else len(previous_sessions)
        dropoff = 0 if index == 0 else max(0, previous_count - count)
        rows.append(
            {
                "step": label,
                "event_name": " / ".join(_step_event_names(event_spec)),
                "event_names": _step_event_names(event_spec),
                "count": count,
                "step_rate": 1.0 if index == 0 else _rate(count, previous_count),
                "overall_rate": 1.0 if index == 0 else _rate(count, first_count),
                "dropoff": dropoff,
                "unit": "session",
                "current_only": current_only,
            }
        )
        previous_sessions = step_sessions
    return rows


def build_current_total_funnel_rows(events: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return build_session_funnel_rows(events, CURRENT_TOTAL_FUNNEL_STEPS, current_only=True)


def build_light_list_funnel_rows(events: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return build_session_funnel_rows(
        events,
        LIGHT_LIST_FUNNEL_STEPS,
        current_only=True,
        first_step_filter=_is_light_entry_event,
    )


def build_heavy_list_funnel_rows(events: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return build_session_funnel_rows(
        events,
        HEAVY_LIST_FUNNEL_STEPS,
        current_only=True,
        first_step_filter=_is_heavy_entry_event,
    )


def build_funnel_instrumentation_summary(events: List[Dict[str, Any]]) -> Dict[str, Any]:
    normalized = normalize_events(events)
    legacy_events = [event for event in normalized if _is_legacy_compatible_event(event)]
    current_events = [event for event in normalized if not _is_legacy_compatible_event(event)]
    current_sessions = _session_set(current_events)
    legacy_sessions = _session_set(legacy_events)
    heavy_entry_events = [event for event in current_events if _is_heavy_entry_event(event)]
    light_entry_events = [event for event in current_events if _is_light_entry_event(event)]
    return {
        "total_events": len(normalized),
        "current_events": len(current_events),
        "legacy_events": len(legacy_events),
        "current_sessions": len(current_sessions),
        "legacy_sessions": len(legacy_sessions),
        "home_rendered_sessions": len(_session_set(event for event in current_events if _event_matches(event, EVENT_HOME_CONTENT_RENDERED))),
        "light_entry_sessions": len(_session_set(light_entry_events)),
        "heavy_entry_sessions": len(_session_set(heavy_entry_events)),
    }


def build_funnel_rows(events: List[Dict[str, Any]], steps: List[Tuple[Union[str, Tuple[str, ...]], str]]) -> List[Dict[str, Any]]:
    events = normalize_events(events)
    counts = Counter(str(event.get("event_name") or "") for event in events)
    rows: List[Dict[str, Any]] = []
    first_names = _step_event_names(steps[0][0]) if steps else ()
    first_count = sum(counts.get(name, 0) for name in first_names)
    previous_count = 0

    for index, (event_spec, label) in enumerate(steps):
        event_names = _step_event_names(event_spec)
        count = sum(counts.get(name, 0) for name in event_names)
        dropoff = 0 if index == 0 else max(0, previous_count - count)
        step_rate = 1.0 if index == 0 else min(1.0, _rate(count, previous_count))
        overall_rate = 1.0 if index == 0 else min(1.0, _rate(count, first_count))
        rows.append(
            {
                "step": label,
                "event_name": " / ".join(event_names),
                "event_names": event_names,
                "count": count,
                "step_rate": step_rate,
                "overall_rate": overall_rate,
                "dropoff": dropoff,
            }
        )
        previous_count = count
    return rows


def get_largest_funnel_drop(rows: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    if len(rows) < 2:
        return None
    drops: List[Dict[str, Any]] = []
    for previous, current in zip(rows, rows[1:]):
        drops.append(
            {
                "from_step": previous.get("step", ""),
                "to_step": current.get("step", ""),
                "dropoff": int(current.get("dropoff", 0)),
                "step_rate": float(current.get("step_rate", 0.0)),
            }
        )
    return max(drops, key=lambda item: item["dropoff"]) if drops else None


def build_funnel_insight(rows: List[Dict[str, Any]]) -> str:
    largest = get_largest_funnel_drop(rows)
    if not largest:
        return "当前漏斗数据不足，暂时无法识别最大流失环节。"
    return (
        f"当前最大流失环节为 {largest['from_step']} -> {largest['to_step']}，"
        f"单步转化率为 {_format_percent(largest['step_rate'])}，"
        "说明用户可能在该环节存在认知、入口或操作成本阻力。"
    )


def build_daily_metrics(events: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    events = normalize_events(events)
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
    dates = [start + timedelta(days=offset) for offset in range((end - start).days + 1)] if fill_all_dates else [date.fromisoformat(value) for value in sorted(buckets)]

    rows: List[Dict[str, Any]] = []
    for current in dates:
        key = current.isoformat()
        counts = buckets.get(key, Counter())
        visits = counts.get(EVENT_VISIT, 0)
        started = counts.get(EVENT_SORTING_STARTED, 0)
        completed = counts.get(EVENT_RANKING_COMPLETED, 0)
        copied = counts.get(EVENT_SHARE_COPIED, 0)
        posters = counts.get(EVENT_POSTER_DOWNLOADED, 0)
        rows.append(
            {
                "date": key,
                EVENT_VISIT: visits,
                EVENT_LIST_OPENED: counts.get(EVENT_LIST_OPENED, 0),
                EVENT_LIST_SELECTED: counts.get(EVENT_LIST_SELECTED, 0),
                EVENT_SORTING_STARTED: started,
                EVENT_RANKING_COMPLETED: completed,
                EVENT_SHARE_COPIED: copied,
                EVENT_POSTER_DOWNLOADED: posters,
                EVENT_HOME_CONTENT_RENDERED: counts.get(EVENT_HOME_CONTENT_RENDERED, 0),
                "start_rate": _rate(started, visits),
                "completion_rate": _rate(completed, started),
                "share_rate": _rate(copied, completed),
                "poster_rate": _rate(posters, completed),
            }
        )
    return rows


def _last_seen(events: List[Dict[str, Any]]) -> str:
    values = [str(event.get("created_at") or "") for event in events if event.get("created_at")]
    return max(values) if values else ""


def _group_events(events: List[Dict[str, Any]], group_key: str, include_unknown: bool = False) -> Dict[str, List[Dict[str, Any]]]:
    grouped: Dict[str, List[Dict[str, Any]]] = {}
    for event in normalize_events(events):
        value = _event_group_value(event, group_key, include_unknown)
        if not value and not include_unknown:
            continue
        grouped.setdefault(value or "unknown", []).append(event)
    return grouped


def _metric_row(value: str, group_events: List[Dict[str, Any]], label_key: str) -> Dict[str, Any]:
    summary = build_admin_summary(group_events)
    row = {
        label_key: value,
        "total_events": summary["total_events"],
        "visits": summary["visits"],
        "page_views": summary["visits"],
        "list_opened": summary["list_opened"],
        "list_selected": summary["list_selected"],
        "open_or_select_list": summary["open_or_select_list"],
        "challenge_opened": summary["list_opened"],
        "started": summary["started"],
        "completed": summary["completed"],
        "copied": summary["copied"],
        "posters": summary["posters"],
        "start_rate": summary["start_rate"],
        "completion_rate": summary["completion_rate"],
        "share_rate": summary["share_rate"],
        "poster_rate": summary["poster_rate"],
        "avg_comparisons": summary["avg_comparisons"],
        "avg_total": summary["avg_total"],
        "avg_list_size": summary["avg_list_size"],
        "last_seen": _last_seen(group_events),
    }
    return row


def build_group_metrics(
    events: List[Dict[str, Any]],
    group_key: str,
    *,
    label_key: str,
    include_unknown: bool = False,
    include_winners: bool = False,
    top_n: int = 30,
) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for value, group_events in _group_events(events, group_key, include_unknown=include_unknown).items():
        row = _metric_row(value, group_events, label_key)
        if include_winners:
            completed_events = [event for event in group_events if _event_matches(event, EVENT_RANKING_COMPLETED)]
            winners = Counter(str(_payload(event).get("winner")) for event in completed_events if _payload(event).get("winner"))
            row["top_winners"] = "，".join(f"{name}({count})" for name, count in winners.most_common(3))
        rows.append(row)

    rows.sort(key=lambda item: (int(item.get("completed", 0)), int(item.get("started", 0)), int(item.get("total_events", 0))), reverse=True)
    return rows[:top_n]


def build_list_metrics(events: List[Dict[str, Any]], *, sort_by: str = "completed", top_n: int = 100) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for value, group_events in _group_events(events, "list_id", include_unknown=True).items():
        sample = group_events[0] if group_events else {}
        payload = _payload(sample)
        row = _metric_row(value, group_events, "list_id")
        row["template_id"] = _safe_text(sample.get("template_id")) or _safe_text(payload.get("template_id"))
        row["mode"] = _safe_text(sample.get("mode")) or _safe_text(payload.get("mode"))
        rows.append(row)

    sort_key_map = {
        "completed": lambda item: (int(item.get("completed", 0)), int(item.get("started", 0))),
        "completion_rate": lambda item: (float(item.get("completion_rate", 0.0)), int(item.get("completed", 0))),
        "started": lambda item: (int(item.get("started", 0)), int(item.get("completed", 0))),
        "visits": lambda item: (int(item.get("visits", 0)), int(item.get("started", 0))),
    }
    rows.sort(key=sort_key_map.get(sort_by, sort_key_map["completed"]), reverse=True)
    return rows[:top_n]


def build_channel_metrics(events: List[Dict[str, Any]], *, top_n: int = 100) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    grouped: Dict[Tuple[str, str, str, str], List[Dict[str, Any]]] = {}
    for event in normalize_events(events):
        key = (_event_source(event), _event_utm_source(event), _event_utm_medium(event), _event_utm_campaign(event))
        grouped.setdefault(key, []).append(event)

    for (source, utm_source, utm_medium, utm_campaign), group_events in grouped.items():
        row = _metric_row(source, group_events, "source")
        row["utm_source"] = utm_source
        row["utm_medium"] = utm_medium
        row["utm_campaign"] = utm_campaign
        rows.append(row)

    rows.sort(key=lambda item: (int(item.get("visits", 0)), int(item.get("started", 0)), int(item.get("completed", 0))), reverse=True)
    return rows[:top_n]


def _event_experiment_pairs(event: Dict[str, Any]) -> List[Tuple[str, str]]:
    payload = _payload(event)
    pairs: List[Tuple[str, str]] = []

    experiments = payload.get("experiments")
    if isinstance(experiments, dict):
        for experiment_id, variant_value in experiments.items():
            if isinstance(variant_value, dict):
                variant_id = _safe_text(variant_value.get("variant_id"))
            else:
                variant_id = _safe_text(variant_value)
            experiment_id_text = _safe_text(experiment_id)
            if experiment_id_text and variant_id:
                pairs.append((experiment_id_text, variant_id))
    elif isinstance(experiments, list):
        for item in experiments:
            if not isinstance(item, dict):
                continue
            experiment_id = _safe_text(item.get("experiment_id"))
            variant_id = _safe_text(item.get("variant_id"))
            if experiment_id and variant_id:
                pairs.append((experiment_id, variant_id))

    experiment_id = _safe_text(payload.get("experiment_id"))
    variant_id = _safe_text(payload.get("variant_id"))
    if experiment_id and variant_id:
        pairs.append((experiment_id, variant_id))

    deduped: List[Tuple[str, str]] = []
    seen = set()
    for pair in pairs:
        if pair in seen:
            continue
        seen.add(pair)
        deduped.append(pair)
    return deduped


def build_experiment_metrics(events: List[Dict[str, Any]], *, top_n: int = 100) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    grouped: Dict[Tuple[str, str], List[Dict[str, Any]]] = {}
    for event in normalize_events(events):
        for experiment_id, variant_id in _event_experiment_pairs(event):
            grouped.setdefault((experiment_id, variant_id), []).append(event)

    for (experiment_id, variant_id), group_events in grouped.items():
        row = _metric_row(f"{experiment_id}:{variant_id}", group_events, "experiment_variant")
        row["experiment_id"] = experiment_id
        row["variant_id"] = variant_id
        rows.append(row)

    rows.sort(key=lambda item: (str(item.get("experiment_id")), int(item.get("visits", 0)), int(item.get("started", 0))), reverse=False)
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
    canonical_name = canonical_event_name(event_name)
    for event in normalize_events(events):
        if not _event_matches(event, canonical_name):
            continue
        value = _payload(event).get(payload_key)
        if value in (None, ""):
            if not include_empty:
                continue
            value = "unknown"
        counter[str(value)] += 1
    return [{label_key: value, "count": count} for value, count in counter.most_common(top_n)]


def build_top_k_distribution(events: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    counter: Counter = Counter()
    for event in normalize_events(events):
        if not _event_matches(event, EVENT_SORTING_STARTED):
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
    aliases = [payload_key]
    if payload_key == "comparisons":
        aliases.insert(0, "comparison_count")
    if payload_key == "total":
        aliases.insert(0, "list_size")
    return build_histogram(_payload_numbers(events, canonical_event_name(event_name), *aliases), buckets, label_key=label_key)


def build_setting_rows(events: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    started_events = [event for event in normalize_events(events) if _event_matches(event, EVENT_SORTING_STARTED)]
    started = len(started_events)
    settings = [
        ("盲排开启", sum(1 for event in started_events if _payload(event).get("blind_mode") is True)),
        ("左右随机开启", sum(1 for event in started_events if _payload(event).get("side_shuffle") is True)),
        ("使用顺序口令", sum(1 for event in started_events if _payload(event).get("has_seed") is True)),
        ("共享片单入口", sum(1 for event in started_events if _payload(event).get("list_source") == "shared" or _payload(event).get("source") == "shared")),
    ]
    return [{"setting": name, "count": count, "rate": _rate(count, started)} for name, count in settings]


def summarize_payload(payload: Dict[str, Any]) -> str:
    ordered_keys = [
        "page",
        "route",
        "list_id",
        "template_id",
        "mode",
        "source",
        "utm_source",
        "utm_medium",
        "utm_campaign",
        "list_size",
        "total",
        "top_k",
        "ranked_count",
        "skipped_count",
        "comparison_count",
        "comparisons",
        "defers",
        "surface",
        "poster_type",
        "device_type",
        "experiment_id",
        "variant_id",
        "experiments",
        "blind_mode",
        "side_shuffle",
        "winner",
    ]
    parts = []
    for key in ordered_keys:
        if key in payload and payload.get(key) not in (None, ""):
            parts.append(f"{key}={payload.get(key)}")
    return ", ".join(parts)


def flatten_event_for_table(event: Dict[str, Any]) -> Dict[str, Any]:
    event = normalize_event(event)
    session_id = str(event.get("session_id") or "")
    payload = _payload(event)
    experiment_pairs = _event_experiment_pairs(event)
    return {
        "event_time": event.get("created_at") or "",
        "event": EVENT_LABELS.get(str(event.get("event_name") or ""), str(event.get("event_name") or "")),
        "event_name": event.get("event_name") or "",
        "anonymous_session": session_id[-8:] if session_id else "",
        "mode": event.get("mode") or payload.get("mode") or "",
        "source": _event_source(event),
        "utm_medium": _event_utm_medium(event),
        "utm_campaign": _event_utm_campaign(event),
        "template_id": event.get("template_id") or payload.get("template_id") or "",
        "list_id": _event_list_id(event),
        "experiment_id": payload.get("experiment_id") or "",
        "variant_id": payload.get("variant_id") or "",
        "experiments": "，".join(f"{experiment_id}:{variant_id}" for experiment_id, variant_id in experiment_pairs),
        "payload_summary": summarize_payload(payload),
    }


def build_event_table_rows(events: List[Dict[str, Any]], limit: int = 500) -> List[Dict[str, Any]]:
    sorted_events = sorted(normalize_events(events), key=lambda event: str(event.get("created_at") or ""), reverse=True)
    return [flatten_event_for_table(event) for event in sorted_events[:limit]]


def build_admin_insights(events: List[Dict[str, Any]]) -> List[str]:
    events = normalize_events(events)
    if not events:
        return ["当前筛选范围内还没有事件。"]

    summary = build_admin_summary(events)
    insights = [
        f"当前开始率为 {_format_percent(summary['start_rate'])}，完成率为 {_format_percent(summary['completion_rate'])}。",
    ]

    funnel = build_funnel_rows(events, MAIN_FUNNEL_STEPS)
    insights.append(build_funnel_insight(funnel))

    source_rows = build_channel_metrics(events, top_n=10)
    qualified_sources = [row for row in source_rows if int(row.get("started", 0)) >= 3]
    if qualified_sources:
        best_source = max(qualified_sources, key=lambda row: float(row.get("completion_rate", 0)))
        insights.append(
            f"完成率最高的渠道是「{best_source['source']}」，完成率 {_format_percent(float(best_source['completion_rate']))}。"
        )

    list_rows = build_list_metrics(events, sort_by="completion_rate", top_n=10)
    qualified_lists = [row for row in list_rows if int(row.get("started", 0)) >= 2]
    if qualified_lists:
        best_list = max(qualified_lists, key=lambda row: float(row.get("completion_rate", 0)))
        insights.append(
            f"完成率最高的片单是「{best_list['list_id']}」，完成 {int(best_list['completed'])} 次。"
        )

    if summary["completed"]:
        insights.append(
            f"完成用户平均作出 {summary['avg_comparisons']:.1f} 次取舍，平均整理规模 {summary['avg_list_size']:.1f} 部。"
        )

    if summary["poster_rate"] > summary["share_rate"] and summary["completed"]:
        insights.append("海报下载率高于复制分享率，说明视觉化结果可能比纯链接分享更有传播吸引力。")

    return insights[:6]


def fetch_public_metrics() -> Dict[str, Any]:
    if not analytics_enabled():
        return {"enabled": False, "completed": 0, "today_users": 0, "avg_comparisons": 0.0}

    events = fetch_recent_events(1000)
    completed = [event for event in events if _event_matches(event, EVENT_RANKING_COMPLETED)]
    today = datetime.now(timezone.utc).date()
    today_sessions = {
        event.get("session_id") or event.get("payload", {}).get("session_hint") or event.get("challenge_id") or event.get("created_at")
        for event in events
        if str(event.get("created_at", ""))[:10] == today.isoformat()
    }
    comparisons = _payload_numbers(events, EVENT_RANKING_COMPLETED, "comparison_count", "comparisons")
    avg = sum(comparisons) / len(comparisons) if comparisons else 0.0
    return {
        "enabled": True,
        "completed": len(completed),
        "today_users": len(today_sessions),
        "avg_comparisons": avg,
    }


def fetch_admin_metrics() -> Dict[str, Any]:
    events = fetch_all_events()
    summary = build_admin_summary(events)
    template_counts = Counter(event.get("template_id") for event in events if event.get("template_id"))
    challenge_counts = Counter(_event_list_id(event) for event in events if _event_list_id(event) != "unknown")
    return {
        "enabled": analytics_enabled(),
        "counts": summary["counts"],
        "completion_rate": summary["completion_rate"],
        "share_rate": summary["share_rate"],
        "top_templates": template_counts.most_common(8),
        "top_challenges": challenge_counts.most_common(8),
        "recent_events": events[:120],
    }
