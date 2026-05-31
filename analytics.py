from __future__ import annotations

import uuid
from collections import Counter
from datetime import datetime, timezone
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
    return get_secret("PUBLIC_APP_URL").rstrip("/")


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
            "select": "event_name,created_at,session_id,challenge_id,template_id,mode,payload",
            "order": "created_at.desc",
            "limit": str(max(1, min(limit, 2000))),
        },
    )
    return result if isinstance(result, list) else []


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
    events = fetch_recent_events(2000)
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
