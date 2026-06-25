from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple
from urllib.parse import urlsplit, urlunsplit

import requests


REPO_ROOT = Path(__file__).resolve().parents[2]
SCHEMA_PATH = REPO_ROOT / "supabase_schema.sql"
ANALYTICS_MODULE_PATH = REPO_ROOT / "analytics.py"
SECRETS_PATH = REPO_ROOT / ".streamlit" / "secrets.toml"
SQL_PATH = REPO_ROOT / "analytics" / "sql" / "01_data_quality.sql"
SAMPLE_PATH = REPO_ROOT / "analytics" / "sample_data" / "analytics_events_sanitized_sample.csv"
TABLE_NAME = "analytics_events"
DEFAULT_LIMIT = 200
CORE_FIELDS = ("event_name", "created_at", "session_id", "payload")
SENSITIVE_KEY_PATTERN = re.compile(r"(token|secret|key|password|authorization|apikey|service_role)", re.IGNORECASE)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Safely inspect Film Sort analytics data without printing credentials or raw user identifiers.",
    )
    parser.add_argument("--dry-run", action="store_true", help="Check configuration and list planned checks without querying Supabase.")
    parser.add_argument("--limit", type=int, default=DEFAULT_LIMIT, help="Maximum event rows to sample. Default: 200.")
    parser.add_argument(
        "--export-sanitized-sample",
        action="store_true",
        help="Export a sanitized sample CSV to analytics/sample_data/analytics_events_sanitized_sample.csv.",
    )
    return parser.parse_args()


def _strip_quotes(value: str) -> str:
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
        return value[1:-1]
    return value


def read_streamlit_secret(name: str) -> str:
    if not SECRETS_PATH.exists():
        return ""
    try:
        import tomllib

        data = tomllib.loads(SECRETS_PATH.read_text(encoding="utf-8"))
        value = data.get(name, "")
        return str(value or "").strip()
    except Exception:
        pass
    pattern = re.compile(rf"^\s*{re.escape(name)}\s*=\s*(.+?)\s*$")
    try:
        for line in SECRETS_PATH.read_text(encoding="utf-8").splitlines():
            match = pattern.match(line)
            if match:
                return _strip_quotes(match.group(1)).strip()
    except OSError:
        return ""
    return ""


def get_config() -> Tuple[str, str, str]:
    url = (os.environ.get("SUPABASE_URL") or read_streamlit_secret("SUPABASE_URL")).strip().rstrip("/")
    key = (os.environ.get("SUPABASE_ANON_KEY") or read_streamlit_secret("SUPABASE_ANON_KEY")).strip()
    source = "environment variables" if os.environ.get("SUPABASE_URL") or os.environ.get("SUPABASE_ANON_KEY") else "streamlit secrets"
    if not url or not key:
        source = "unavailable"
    return url, key, source


def print_header(connection_mode: str, known_tables: Iterable[str]) -> None:
    print("[Analytics Inventory]")
    print(f"- connection mode: {connection_mode}")
    print(f"- known analytics table(s): {', '.join(known_tables) if known_tables else TABLE_NAME}")


def static_tables() -> List[str]:
    if not SCHEMA_PATH.exists():
        return [TABLE_NAME]
    text = SCHEMA_PATH.read_text(encoding="utf-8", errors="replace")
    tables = re.findall(r"create\s+table\s+if\s+not\s+exists\s+public\.([a-zA-Z0-9_]+)", text, flags=re.IGNORECASE)
    return sorted(set(tables)) or [TABLE_NAME]


def static_event_names() -> List[str]:
    if not ANALYTICS_MODULE_PATH.exists():
        return []
    text = ANALYTICS_MODULE_PATH.read_text(encoding="utf-8", errors="replace")
    names = re.findall(r'^\s*(?:LEGACY_)?EVENT_[A-Z0-9_]+\s*=\s*"([^"]+)"', text, flags=re.MULTILINE)
    return sorted(set(names))


def planned_checks() -> List[str]:
    return [
        "sample field names",
        "event_name distribution",
        "event_time range",
        "null rate for core fields",
        "distinct masked sessions in sample",
        "warnings for missing fields",
        "optional sanitized sample export",
    ]


def fetch_events(url: str, key: str, limit: int) -> Optional[List[Dict[str, Any]]]:
    endpoint = f"{url}/rest/v1/{TABLE_NAME}"
    headers = {
        "apikey": key,
        "Authorization": f"Bearer {key}",
        "Accept": "application/json",
    }
    params = {
        "select": "id,created_at,event_name,session_id,challenge_id,mode,template_id,source_channel,payload",
        "order": "created_at.desc",
        "limit": str(max(1, min(limit, 2000))),
    }
    try:
        response = requests.get(endpoint, headers=headers, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()
    except Exception:
        return None
    return data if isinstance(data, list) else None


def mask_identifier(value: Any) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
    return f"sha256:{digest[:12]}"


def payload(event: Dict[str, Any]) -> Dict[str, Any]:
    value = event.get("payload")
    return value if isinstance(value, dict) else {}


def clean_referrer(value: Any) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    parts = urlsplit(text)
    if not parts.netloc:
        return text.split("?")[0][:120]
    return urlunsplit((parts.scheme, parts.netloc, parts.path[:120], "", ""))


def safe_scalar(value: Any) -> Any:
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    if isinstance(value, list):
        return json.dumps([item for item in value if isinstance(item, (str, int, float, bool))][:10], ensure_ascii=True)
    if isinstance(value, dict):
        safe = {
            str(key): nested
            for key, nested in value.items()
            if isinstance(nested, (str, int, float, bool)) and not SENSITIVE_KEY_PATTERN.search(str(key))
        }
        return json.dumps(safe, ensure_ascii=True, sort_keys=True)
    return str(value)[:120]


def sanitized_rows(events: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    payload_keys = [
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
        "item_count",
        "top_k",
        "comparison_count",
        "comparisons",
        "ranked_count",
        "skipped_count",
        "defers",
        "poster_type",
        "surface",
        "device_type",
        "experiment_id",
        "variant_id",
        "app_version",
        "release_id",
        "render_elapsed_ms",
        "home_layout_order",
        "entry_surface",
    ]
    for event in events:
        item = payload(event)
        row = {
            "event_time": event.get("created_at") or "",
            "event_name": event.get("event_name") or "",
            "session_hash": mask_identifier(event.get("session_id")),
            "challenge_id": event.get("challenge_id") or "",
            "template_id": event.get("template_id") or item.get("template_id") or "",
            "mode": event.get("mode") or item.get("mode") or "",
            "source_channel": event.get("source_channel") or item.get("source") or "",
        }
        for key in payload_keys:
            if key in item:
                row[f"payload_{key}"] = clean_referrer(item.get(key)) if key == "referrer" else safe_scalar(item.get(key))
        rows.append(row)
    return rows


def export_sanitized_sample(events: List[Dict[str, Any]]) -> None:
    rows = sanitized_rows(events)
    SAMPLE_PATH.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = sorted({key for row in rows for key in row.keys()})
    with SAMPLE_PATH.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    print(f"- sanitized sample export: {SAMPLE_PATH.relative_to(REPO_ROOT)}")


def summarize_events(events: List[Dict[str, Any]]) -> None:
    field_names = sorted({key for event in events for key in event.keys()})
    payload_field_names = sorted({key for event in events for key in payload(event).keys()})
    counts = Counter(str(event.get("event_name") or "missing") for event in events)
    times = [str(event.get("created_at") or "") for event in events if event.get("created_at")]
    masked_sessions = {mask_identifier(event.get("session_id")) for event in events if event.get("session_id")}

    print(f"- sampled rows: {len(events)}")
    print(f"- sampled field names: {', '.join(field_names) if field_names else '(none)'}")
    print(f"- sampled payload field names: {', '.join(payload_field_names) if payload_field_names else '(none)'}")
    print("- event_name distribution:")
    if counts:
        for name, count in counts.most_common(30):
            print(f"  - {name}: {count}")
    else:
        print("  - (empty)")
    print(f"- event_time range: {min(times)} -> {max(times)}" if times else "- event_time range: unavailable")
    print("- null rate for core fields:")
    total = len(events) or 1
    for field in CORE_FIELDS:
        missing = sum(1 for event in events if event.get(field) in (None, ""))
        print(f"  - {field}: {missing}/{len(events)} ({missing / total:.1%})")
    print(f"- number of distinct masked sessions in sample: {len(masked_sessions)}")

    expected_payload = ["route", "source", "device_type", "list_id", "list_size", "comparison_count", "app_version"]
    warnings = [field for field in expected_payload if field not in payload_field_names]
    if "id" not in field_names:
        warnings.append("id was not returned by the sample query")
    print("- warnings for missing fields:")
    if warnings:
        for warning in warnings:
            print(f"  - {warning}")
    else:
        print("  - none for expected sample fields")
    print("- suggested next analytics queries:")
    print(f"  - Run {SQL_PATH.relative_to(REPO_ROOT)} in Supabase SQL Editor for full data quality checks.")
    print("  - Use session-level funnel preview before building Step 2 funnel charts.")


def static_fallback(reason: str = "") -> None:
    tables = static_tables()
    print_header("local schema", tables)
    if reason:
        print(f"- database access unavailable: {reason}")
    events = static_event_names()
    print(f"- sampled field names: unavailable")
    print(f"- event_name distribution: unavailable")
    print(f"- event_time range: unavailable")
    print("- null rate for core fields: unavailable")
    print("- number of distinct masked sessions in sample: unavailable")
    print("- warnings for missing fields:")
    print("  - database access unavailable; using static schema/code scan only")
    print(f"- code-inferred event names: {', '.join(events) if events else '(none found)'}")
    print("- suggested next analytics queries:")
    print(f"  - Manually run {SQL_PATH.relative_to(REPO_ROOT)} in Supabase SQL Editor.")


def main() -> int:
    args = parse_args()
    limit = max(1, min(int(args.limit or DEFAULT_LIMIT), 2000))
    url, key, config_source = get_config()
    known_tables = static_tables()

    if args.dry_run:
        mode = "Supabase read-only (dry-run)" if url and key else "local schema (dry-run)"
        print_header(mode, known_tables)
        print(f"- config source: {config_source}")
        print(f"- planned sample limit: {limit}")
        print("- planned checks:")
        for check in planned_checks():
            print(f"  - {check}")
        if not url or not key:
            print("- database access unavailable: missing Supabase config")
            print(f"- manual SQL path: {SQL_PATH.relative_to(REPO_ROOT)}")
        return 0

    if not url or not key:
        static_fallback("missing Supabase config")
        return 0

    events = fetch_events(url, key, limit)
    if events is None:
        static_fallback("read-only query failed")
        return 0

    print_header("Supabase read-only", known_tables)
    summarize_events(events)
    if args.export_sanitized_sample:
        export_sanitized_sample(events)
    else:
        print("- sanitized sample export: not requested")
    return 0


if __name__ == "__main__":
    sys.exit(main())
