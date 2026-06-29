from __future__ import annotations

from typing import Any, Dict, Iterable, List

from light_list_catalog import DEFAULT_HOME_LIGHT_LIST_IDS


EXPECTED_HOME_LIGHT_LIST_COUNT = 9


def resolve_home_light_list_state(
    roster_state: Any,
    known_template_ids: Iterable[str],
) -> Dict[str, Any]:
    known = {str(template_id) for template_id in known_template_ids}
    rows = roster_state.get("rows") if isinstance(roster_state, dict) else []
    source = str(roster_state.get("source") or "unavailable") if isinstance(roster_state, dict) else "unavailable"
    resolved_rows: List[Dict[str, Any]] = []
    seen = set()
    if isinstance(rows, list):
        for row in rows:
            if not isinstance(row, dict):
                continue
            template_id = str(row.get("template_id") or "").strip()
            if not template_id or template_id not in known or template_id in seen:
                continue
            seen.add(template_id)
            resolved_rows.append(dict(row))

    if len(resolved_rows) == EXPECTED_HOME_LIGHT_LIST_COUNT:
        resolved_rows.sort(
            key=lambda row: (
                int(row.get("display_rank", 0) or 0),
                str(row.get("template_id") or ""),
            )
        )
        return {
            "template_ids": [str(row["template_id"]) for row in resolved_rows],
            "metadata": {str(row["template_id"]): row for row in resolved_rows},
            "source": source,
        }

    fallback_ids = [template_id for template_id in DEFAULT_HOME_LIGHT_LIST_IDS if template_id in known]
    return {
        "template_ids": fallback_ids[:EXPECTED_HOME_LIGHT_LIST_COUNT],
        "metadata": {},
        "source": "static_fallback",
    }
