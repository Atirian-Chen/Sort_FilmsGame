from __future__ import annotations

import base64
import hashlib
import json
import zlib
from dataclasses import dataclass
from typing import Any, Dict, List, Optional
from urllib.parse import quote

from analytics import analytics_enabled, get_public_app_url, supabase_request


@dataclass
class Challenge:
    id: str
    theme: str
    mode: str
    items: List[str]
    top_k: Optional[int]
    seed_text: str
    source: str
    template_id: str = ""


def make_challenge_id(theme: str, items: List[str], seed_text: str = "") -> str:
    raw = "|".join([theme.strip(), seed_text.strip(), "||".join(items)])
    digest = hashlib.sha1(raw.encode("utf-8")).hexdigest()[:10]
    return f"mv-{digest}"


def normalize_items(items: List[str]) -> List[str]:
    normalized: List[str] = []
    seen = set()
    for item in items:
        value = str(item).strip()
        if value and value not in seen:
            normalized.append(value)
            seen.add(value)
    return normalized


def challenge_from_template(template: Dict[str, Any]) -> Challenge:
    return Challenge(
        id=str(template["id"]),
        theme=str(template["theme"]),
        mode="自备片单",
        items=normalize_items(list(template.get("items", []))),
        top_k=int(template.get("top_k") or 0) or None,
        seed_text=str(template.get("seed_text") or template["id"]),
        source=str(template.get("source") or "builtin"),
        template_id=str(template["id"]),
    )


def save_challenge(
    *,
    theme: str,
    mode: str,
    items: List[str],
    top_k: Optional[int],
    seed_text: str,
    source: str,
) -> Optional[Challenge]:
    clean_items = normalize_items(items)
    if len(clean_items) < 2:
        return None

    challenge_id = make_challenge_id(theme, clean_items, seed_text)
    challenge = Challenge(
        id=challenge_id,
        theme=theme.strip() or "电影审美名单",
        mode=mode,
        items=clean_items,
        top_k=top_k,
        seed_text=seed_text.strip(),
        source=source,
        template_id="",
    )

    if analytics_enabled():
        body = {
            "id": challenge.id,
            "theme": challenge.theme,
            "mode": challenge.mode,
            "items": challenge.items,
            "top_k": challenge.top_k,
            "seed_text": challenge.seed_text,
            "source": challenge.source,
        }
        supabase_request(
            "POST",
            "challenge_sets",
            params={"on_conflict": "id"},
            json_body=body,
            prefer="resolution=merge-duplicates,return=minimal",
        )

    return challenge


def fetch_challenge(challenge_id: str) -> Optional[Challenge]:
    if not challenge_id or not analytics_enabled():
        return None
    result = supabase_request(
        "GET",
        "challenge_sets",
        params={
            "id": f"eq.{challenge_id}",
            "select": "id,theme,mode,items,top_k,seed_text,source,use_count",
            "limit": "1",
        },
    )
    if not isinstance(result, list) or not result:
        return None

    row = result[0]
    items = normalize_items(row.get("items") or [])
    if len(items) < 2:
        return None

    return Challenge(
        id=str(row.get("id") or challenge_id),
        theme=str(row.get("theme") or "电影审美名单"),
        mode=str(row.get("mode") or "自备片单"),
        items=items,
        top_k=int(row["top_k"]) if row.get("top_k") else None,
        seed_text=str(row.get("seed_text") or challenge_id),
        source=str(row.get("source") or "shared"),
    )


def encode_fallback_payload(challenge: Challenge) -> str:
    payload = {
        "theme": challenge.theme,
        "mode": challenge.mode,
        "items": challenge.items,
        "top_k": challenge.top_k,
        "seed_text": challenge.seed_text,
        "source": challenge.source,
    }
    raw = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    compressed = zlib.compress(raw, level=9)
    return base64.urlsafe_b64encode(compressed).decode("ascii").rstrip("=")


def decode_fallback_payload(payload: str) -> Optional[Challenge]:
    if not payload:
        return None
    try:
        padded = payload + "=" * (-len(payload) % 4)
        raw = zlib.decompress(base64.urlsafe_b64decode(padded.encode("ascii")))
        data = json.loads(raw.decode("utf-8"))
        items = normalize_items(data.get("items") or [])
        if len(items) < 2:
            return None
        return Challenge(
            id=make_challenge_id(str(data.get("theme") or ""), items, str(data.get("seed_text") or "")),
            theme=str(data.get("theme") or "电影审美名单"),
            mode=str(data.get("mode") or "自备片单"),
            items=items,
            top_k=int(data["top_k"]) if data.get("top_k") else None,
            seed_text=str(data.get("seed_text") or ""),
            source=str(data.get("source") or "payload"),
        )
    except Exception:
        return None


def build_challenge_url(challenge: Challenge, *, use_payload_fallback: bool = False) -> str:
    base_url = get_public_app_url()
    prefix = base_url or ""
    if use_payload_fallback:
        return f"{prefix}?payload={quote(encode_fallback_payload(challenge))}"
    return f"{prefix}?list={quote(challenge.id)}"


def build_template_url(template_id: str) -> str:
    base_url = get_public_app_url()
    prefix = base_url or ""
    return f"{prefix}?list={quote(template_id)}"
