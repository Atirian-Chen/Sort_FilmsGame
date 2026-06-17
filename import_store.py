from __future__ import annotations

import json
import re
import secrets
from dataclasses import dataclass
from datetime import date
from typing import Any, Dict, List, Optional
from urllib.parse import quote

from analytics import analytics_enabled, get_public_app_url, get_supabase_config, supabase_request


IMPORT_TABLE = "imported_movie_lists"
IMPORT_ID_RE = re.compile(r"^db-[a-z0-9]{12,32}$")
MEDIA_TYPE_MOVIE = "movie"
MEDIA_TYPE_SERIES = "series"
MEDIA_TYPE_UNKNOWN = "unknown"
MEDIA_TYPE_VALUES = (MEDIA_TYPE_MOVIE, MEDIA_TYPE_SERIES, MEDIA_TYPE_UNKNOWN)
MEDIA_TYPE_ALIASES = {
    "movie": MEDIA_TYPE_MOVIE,
    "film": MEDIA_TYPE_MOVIE,
    "电影": MEDIA_TYPE_MOVIE,
    "tv": MEDIA_TYPE_SERIES,
    "series": MEDIA_TYPE_SERIES,
    "show": MEDIA_TYPE_SERIES,
    "drama": MEDIA_TYPE_SERIES,
    "剧集": MEDIA_TYPE_SERIES,
    "电视剧": MEDIA_TYPE_SERIES,
    "unknown": MEDIA_TYPE_UNKNOWN,
    "未知": MEDIA_TYPE_UNKNOWN,
}


@dataclass
class ImportedMovieList:
    id: str
    entries: List[Dict[str, Any]]
    items: List[str]
    poster_url_map: Dict[str, str]
    rating_map: Dict[str, int]
    rated_at_map: Dict[str, str]
    media_type_map: Dict[str, str]
    has_rating_data: bool = False
    has_rated_at_data: bool = False
    has_media_type_data: bool = False
    source: str = "douban_bookmarklet"


def make_import_id() -> str:
    return f"db-{secrets.token_hex(8)}"


def clean_import_id(import_id: str) -> str:
    value = str(import_id or "").strip().lower()
    return value if IMPORT_ID_RE.match(value) else ""


def clean_rating(value: Any) -> Optional[int]:
    if value is None or value == "":
        return None
    try:
        rating = int(value)
    except (TypeError, ValueError):
        return None
    return rating if 1 <= rating <= 5 else None


def clean_media_type(value: Any) -> str:
    text = str(value or "").strip().lower()
    return MEDIA_TYPE_ALIASES.get(text, MEDIA_TYPE_UNKNOWN)


def clean_collect_date(value: Any) -> Optional[str]:
    text = str(value or "").strip()
    if not text:
        return None
    match = re.search(r"((?:19|20)\d{2})[-./年](\d{1,2})[-./月](\d{1,2})(?:日)?", text)
    if not match:
        return None
    try:
        return date(int(match.group(1)), int(match.group(2)), int(match.group(3))).isoformat()
    except ValueError:
        return None


def normalize_import_entries(entries: List[Any]) -> List[Dict[str, Any]]:
    normalized: List[Dict[str, Any]] = []
    seen = set()
    for entry in entries:
        title = ""
        poster_url = ""
        subject_id = ""
        rating: Optional[int] = None
        rated_at: Optional[str] = None
        media_type = MEDIA_TYPE_UNKNOWN
        has_rating_key = False
        has_rated_at_key = False
        has_media_type_key = False
        if isinstance(entry, dict):
            title = str(entry.get("title") or "").strip()
            poster_url = str(entry.get("poster_url") or entry.get("poster") or "").strip()
            subject_id = str(entry.get("subject_id") or entry.get("subject") or "").strip()
            has_rating_key = "rating" in entry
            rating = clean_rating(entry.get("rating"))
            has_rated_at_key = "rated_at" in entry or "collect_date" in entry or "date" in entry
            rated_at = clean_collect_date(entry.get("rated_at") or entry.get("collect_date") or entry.get("date"))
            has_media_type_key = "media_type" in entry or "type" in entry or "category" in entry
            media_type = clean_media_type(entry.get("media_type") or entry.get("type") or entry.get("category"))
        else:
            title = str(entry or "").strip()
        title = re.sub(r"\s+", " ", title)
        if not title or title in seen:
            continue
        seen.add(title)
        item: Dict[str, Any] = {"title": title, "poster_url": poster_url}
        if subject_id:
            item["subject_id"] = subject_id
        if has_rating_key:
            item["rating"] = rating
        if has_rated_at_key:
            item["rated_at"] = rated_at
        if has_media_type_key:
            item["media_type"] = media_type
        normalized.append(item)
    return normalized[:1500]


def save_imported_movie_list(entries: List[Any], *, source: str = "douban_bookmarklet") -> Optional[ImportedMovieList]:
    clean_entries = normalize_import_entries(entries)
    if len(clean_entries) < 2 or not analytics_enabled():
        return None

    import_id = make_import_id()
    body = {
        "id": import_id,
        "source": source,
        "items": clean_entries,
        "item_count": len(clean_entries),
    }
    supabase_request(
        "POST",
        IMPORT_TABLE,
        json_body=body,
        prefer="return=minimal",
    )
    return ImportedMovieList(
        id=import_id,
        entries=clean_entries,
        items=[entry["title"] for entry in clean_entries],
        poster_url_map={entry["title"]: entry["poster_url"] for entry in clean_entries if entry.get("poster_url")},
        rating_map={entry["title"]: int(entry["rating"]) for entry in clean_entries if entry.get("rating") is not None},
        rated_at_map={entry["title"]: str(entry["rated_at"]) for entry in clean_entries if entry.get("rated_at")},
        media_type_map={entry["title"]: str(entry["media_type"]) for entry in clean_entries if "media_type" in entry},
        has_rating_data=any("rating" in entry for entry in clean_entries),
        has_rated_at_data=any("rated_at" in entry for entry in clean_entries),
        has_media_type_data=any("media_type" in entry for entry in clean_entries),
        source=source,
    )


def fetch_imported_movie_list(import_id: str) -> Optional[ImportedMovieList]:
    clean_id = clean_import_id(import_id)
    if not clean_id or not analytics_enabled():
        return None

    result = supabase_request(
        "GET",
        IMPORT_TABLE,
        params={
            "id": f"eq.{clean_id}",
            "select": "id,items,source,item_count,created_at,expires_at",
            "limit": "1",
        },
    )
    if not isinstance(result, list) or not result:
        return None

    row = result[0]
    raw_entries = row.get("items") or []
    has_rating_data = any(isinstance(entry, dict) and "rating" in entry for entry in raw_entries)
    has_rated_at_data = any(isinstance(entry, dict) and "rated_at" in entry for entry in raw_entries)
    has_media_type_data = any(isinstance(entry, dict) and ("media_type" in entry or "type" in entry or "category" in entry) for entry in raw_entries)
    entries = normalize_import_entries(raw_entries)
    if len(entries) < 2:
        return None

    return ImportedMovieList(
        id=str(row.get("id") or clean_id),
        entries=entries,
        items=[entry["title"] for entry in entries],
        poster_url_map={entry["title"]: entry["poster_url"] for entry in entries if entry.get("poster_url")},
        rating_map={entry["title"]: int(entry["rating"]) for entry in entries if entry.get("rating") is not None},
        rated_at_map={entry["title"]: str(entry["rated_at"]) for entry in entries if entry.get("rated_at")},
        media_type_map={entry["title"]: str(entry["media_type"]) for entry in entries if "media_type" in entry},
        has_rating_data=has_rating_data,
        has_rated_at_data=has_rated_at_data,
        has_media_type_data=has_media_type_data,
        source=str(row.get("source") or "douban_bookmarklet"),
    )


def build_import_url(import_id: str) -> str:
    return f"{get_public_app_url()}?import={quote(clean_import_id(import_id) or import_id)}"


def build_douban_bookmarklet() -> str:
    supabase_url, supabase_key = get_supabase_config()
    app_url = get_public_app_url()
    if not supabase_url or not supabase_key:
        return ""

    config = {
        "appUrl": app_url,
        "supabaseUrl": supabase_url,
        "supabaseKey": supabase_key,
        "table": IMPORT_TABLE,
        "maxItems": 1500,
        "pageSize": 15,
        "messages": {
            "preparing": "正在准备导入……",
            "openCollectFirst": "请先打开豆瓣电影的“看过”页面，再点击这个导入工具。",
            "readingPage": "正在读取第",
            "pageSuffix": "页，已找到",
            "movieSuffix": "部……",
            "fetchFailed": "豆瓣页面读取失败：",
            "notEnough": "没有读到足够的已看电影，请确认当前页面是公开可访问的“看过”页。",
            "creatingId": "已读取",
            "creatingIdSuffix": "部，正在生成片单 ID：",
            "saveFailed": "片单保存失败：",
            "success": "导入成功：",
            "opening": "正在打开电影审美名单……",
            "successAlert": "导入成功。片单 ID：",
            "mobileHint": "可以把下一页链接发到手机继续。",
            "failed": "导入失败：",
        },
    }
    config_json = json.dumps(config, ensure_ascii=True, separators=(",", ":"))
    script = f"""
(() => {{
  const cfg = {config_json};
  const msg = cfg.messages;
  const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));
  const makeId = () => {{
    const bytes = new Uint8Array(8);
    crypto.getRandomValues(bytes);
    return "db-" + Array.from(bytes, (b) => b.toString(16).padStart(2, "0")).join("");
  }};
  const cleanTitle = (value) => String(value || "").replace(/\\s+/g, " ").replace(/^\\u770b\\u8fc7\\s*/, "").trim();
  const normalizeDate = (value) => {{
    const match = String(value || "").match(/((?:19|20)\\d{{2}})[-./\\u5e74](\\d{{1,2}})[-./\\u6708](\\d{{1,2}})(?:\\u65e5)?/);
    if (!match) return null;
    const year = Number(match[1]);
    const month = Number(match[2]);
    const day = Number(match[3]);
    const parsed = new Date(Date.UTC(year, month - 1, day));
    if (parsed.getUTCFullYear() !== year || parsed.getUTCMonth() !== month - 1 || parsed.getUTCDate() !== day) return null;
    return String(year).padStart(4, "0") + "-" + String(month).padStart(2, "0") + "-" + String(day).padStart(2, "0");
  }};
  const collectPath = () => /\\/people\\/[^/]+\\/collect/.test(location.pathname);
  const escapeHtml = (value) => String(value || "").replace(/[&<>"']/g, (ch) => ({{"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#039;"}}[ch]));
  const overlay = document.createElement("div");
  overlay.style.cssText = "position:fixed;z-index:2147483647;left:16px;right:16px;bottom:16px;padding:14px 16px;border-radius:10px;background:#1f2328;color:#fff;font:14px/1.5 system-ui,-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;box-shadow:0 12px 32px rgba(0,0,0,.28)";
  overlay.textContent = msg.preparing;
  document.body.appendChild(overlay);
  const update = (text) => {{ overlay.textContent = text; }};
  const subjectIdFromHref = (href) => {{
    const match = String(href || "").match(/\\/subject\\/(\\d+)/);
    return match ? match[1] : "";
  }};
  const parsePage = (doc, seen, mediaType) => {{
    const rows = Array.from(doc.querySelectorAll("div.item.comment-item, div.item"));
    const entries = [];
    for (const item of rows) {{
      const titleEl = item.querySelector(".title a em") || item.querySelector(".title a") || item.querySelector("a.nbgnbg");
      const imgEl = item.querySelector("div.pic img") || item.querySelector("img");
      const linkEl = item.querySelector(".title a") || item.querySelector("a.nbgnbg");
      const subject_id = subjectIdFromHref(linkEl && linkEl.getAttribute("href"));
      const ratingEl = item.querySelector('span[class*="rating"]');
      const ratingClass = ratingEl ? Array.from(ratingEl.classList).join(" ") : "";
      const ratingMatch = ratingClass.match(/rating([1-5])-t/);
      const rating = ratingMatch ? Number(ratingMatch[1]) : null;
      const dateEl = item.querySelector(".date");
      const rated_at = normalizeDate((dateEl && dateEl.textContent) || item.textContent || "");
      let title = cleanTitle((titleEl && (titleEl.getAttribute("title") || titleEl.textContent)) || (imgEl && imgEl.getAttribute("alt")) || "");
      if (!title) continue;
      if (seen.has(title)) {{
        const intro = (item.querySelector("li.intro") || {{ textContent: "" }}).textContent || "";
        const year = (intro.match(/(?:19|20)\\d{{2}}/) || [""])[0];
        if (year && !seen.has(`${{title}} (${{year}})`)) title = `${{title}} (${{year}})`;
      }}
      const dedupeKey = subject_id ? `id:${{subject_id}}` : `title:${{mediaType}}:${{title}}`;
      if (seen.has(dedupeKey)) continue;
      seen.add(dedupeKey);
      seen.add(title);
      entries.push({{
        title,
        subject_id,
        poster_url: (imgEl && (imgEl.getAttribute("src") || imgEl.getAttribute("data-src"))) || "",
        rating,
        rated_at,
        media_type: mediaType
      }});
    }}
    return entries;
  }};
  const pageUrl = (start, doubanType) => `${{location.origin}}${{location.pathname}}?start=${{start}}&sort=time&type=${{doubanType}}&filter=all&mode=grid`;
  (async () => {{
    try {{
      if (!/douban\\.com$/.test(location.hostname) || !collectPath()) {{
        alert(msg.openCollectFirst);
        overlay.remove();
        return;
      }}
      const seen = new Set();
      const entries = [];
      const mediaTypes = [["movie", "movie"], ["tv", "series"]];
      for (const [doubanType, mediaType] of mediaTypes) {{
        for (let start = 0; start < cfg.maxItems; start += cfg.pageSize) {{
          update(`${{msg.readingPage}} ${{doubanType === "movie" ? "\\u7535\\u5f71" : "\\u5267\\u96c6"}} ${{Math.floor(start / cfg.pageSize) + 1}} ${{msg.pageSuffix}} ${{entries.length}} ${{msg.movieSuffix}}`);
          const response = await fetch(pageUrl(start, doubanType), {{ credentials: "include" }});
          if (!response.ok) throw new Error(`${{msg.fetchFailed}}${{response.status}}`);
          const text = await response.text();
          const doc = new DOMParser().parseFromString(text, "text/html");
          const current = parsePage(doc, seen, mediaType);
          if (!current.length) break;
          entries.push(...current);
          if (!doc.querySelector("span.next a, .paginator .next a")) break;
          await sleep(420 + Math.floor(Math.random() * 360));
        }}
      }}
      entries.sort((a, b) => String(b.rated_at || "").localeCompare(String(a.rated_at || "")));
      const savedEntries = entries.slice(0, cfg.maxItems);
      if (savedEntries.length < 2) throw new Error(msg.notEnough);
      const importId = makeId();
      update(`${{msg.creatingId}} ${{savedEntries.length}} ${{msg.creatingIdSuffix}}${{importId}}`);
      const saveResponse = await fetch(`${{cfg.supabaseUrl}}/rest/v1/${{cfg.table}}`, {{
        method: "POST",
        headers: {{
          "apikey": cfg.supabaseKey,
          "Authorization": `Bearer ${{cfg.supabaseKey}}`,
          "Content-Type": "application/json",
          "Prefer": "return=minimal"
        }},
        body: JSON.stringify({{
          id: importId,
          source: "douban_bookmarklet",
          item_count: savedEntries.length,
          items: savedEntries
        }})
      }});
      if (!saveResponse.ok) throw new Error(`${{msg.saveFailed}}${{saveResponse.status}}`);
      const target = `${{cfg.appUrl}}?import=${{encodeURIComponent(importId)}}`;
      overlay.innerHTML = `${{msg.success}}<strong>${{escapeHtml(importId)}}</strong><br>${{msg.opening}}`;
      alert(`${{msg.successAlert}}${{importId}}\\n${{msg.mobileHint}}`);
      location.href = target;
    }} catch (error) {{
      update(`${{msg.failed}}${{error.message || error}}`);
      alert(`${{msg.failed}}${{error.message || error}}`);
    }}
  }})();
}})();
"""
    minified = re.sub(r"\s+", " ", script).strip()
    return "javascript:" + quote(minified, safe="()[]{}!~*';:@&=+$,/?")
