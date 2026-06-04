from __future__ import annotations

import json
import re
import secrets
from dataclasses import dataclass
from typing import Any, Dict, List, Optional
from urllib.parse import quote

from analytics import analytics_enabled, get_public_app_url, get_supabase_config, supabase_request


IMPORT_TABLE = "imported_movie_lists"
IMPORT_ID_RE = re.compile(r"^db-[a-z0-9]{12,32}$")


@dataclass
class ImportedMovieList:
    id: str
    items: List[str]
    poster_url_map: Dict[str, str]
    source: str = "douban_bookmarklet"


def make_import_id() -> str:
    return f"db-{secrets.token_hex(8)}"


def clean_import_id(import_id: str) -> str:
    value = str(import_id or "").strip().lower()
    return value if IMPORT_ID_RE.match(value) else ""


def normalize_import_entries(entries: List[Any]) -> List[Dict[str, str]]:
    normalized: List[Dict[str, str]] = []
    seen = set()
    for entry in entries:
        title = ""
        poster_url = ""
        if isinstance(entry, dict):
            title = str(entry.get("title") or "").strip()
            poster_url = str(entry.get("poster_url") or entry.get("poster") or "").strip()
        else:
            title = str(entry or "").strip()
        title = re.sub(r"\s+", " ", title)
        if not title or title in seen:
            continue
        seen.add(title)
        normalized.append({"title": title, "poster_url": poster_url})
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
        items=[entry["title"] for entry in clean_entries],
        poster_url_map={entry["title"]: entry["poster_url"] for entry in clean_entries if entry.get("poster_url")},
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
    entries = normalize_import_entries(row.get("items") or [])
    if len(entries) < 2:
        return None

    return ImportedMovieList(
        id=str(row.get("id") or clean_id),
        items=[entry["title"] for entry in entries],
        poster_url_map={entry["title"]: entry["poster_url"] for entry in entries if entry.get("poster_url")},
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
  const collectPath = () => /\\/people\\/[^/]+\\/collect/.test(location.pathname);
  const escapeHtml = (value) => String(value || "").replace(/[&<>"']/g, (ch) => ({{"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#039;"}}[ch]));
  const overlay = document.createElement("div");
  overlay.style.cssText = "position:fixed;z-index:2147483647;left:16px;right:16px;bottom:16px;padding:14px 16px;border-radius:10px;background:#1f2328;color:#fff;font:14px/1.5 system-ui,-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;box-shadow:0 12px 32px rgba(0,0,0,.28)";
  overlay.textContent = msg.preparing;
  document.body.appendChild(overlay);
  const update = (text) => {{ overlay.textContent = text; }};
  const parsePage = (doc, seen) => {{
    const rows = Array.from(doc.querySelectorAll("div.item.comment-item, div.item"));
    const entries = [];
    for (const item of rows) {{
      const titleEl = item.querySelector(".title a em") || item.querySelector(".title a") || item.querySelector("a.nbgnbg");
      const imgEl = item.querySelector("div.pic img") || item.querySelector("img");
      let title = cleanTitle((titleEl && (titleEl.getAttribute("title") || titleEl.textContent)) || (imgEl && imgEl.getAttribute("alt")) || "");
      if (!title) continue;
      if (seen.has(title)) {{
        const intro = (item.querySelector("li.intro") || {{ textContent: "" }}).textContent || "";
        const year = (intro.match(/(?:19|20)\\d{{2}}/) || [""])[0];
        if (year && !seen.has(`${{title}} (${{year}})`)) title = `${{title}} (${{year}})`;
      }}
      if (seen.has(title)) continue;
      seen.add(title);
      entries.push({{
        title,
        poster_url: (imgEl && (imgEl.getAttribute("src") || imgEl.getAttribute("data-src"))) || ""
      }});
    }}
    return entries;
  }};
  const pageUrl = (start) => `${{location.origin}}${{location.pathname}}?start=${{start}}&sort=time&type=all&filter=all&mode=grid`;
  (async () => {{
    try {{
      if (!/douban\\.com$/.test(location.hostname) || !collectPath()) {{
        alert(msg.openCollectFirst);
        overlay.remove();
        return;
      }}
      const seen = new Set();
      const entries = [];
      for (let start = 0; start < cfg.maxItems; start += cfg.pageSize) {{
        update(`${{msg.readingPage}} ${{Math.floor(start / cfg.pageSize) + 1}} ${{msg.pageSuffix}} ${{entries.length}} ${{msg.movieSuffix}}`);
        const response = await fetch(pageUrl(start), {{ credentials: "include" }});
        if (!response.ok) throw new Error(`${{msg.fetchFailed}}${{response.status}}`);
        const text = await response.text();
        const doc = new DOMParser().parseFromString(text, "text/html");
        const current = parsePage(doc, seen);
        if (!current.length) break;
        entries.push(...current);
        if (entries.length >= cfg.maxItems) break;
        if (!doc.querySelector("span.next a, .paginator .next a")) break;
        await sleep(420 + Math.floor(Math.random() * 360));
      }}
      if (entries.length < 2) throw new Error(msg.notEnough);
      const importId = makeId();
      update(`${{msg.creatingId}} ${{entries.length}} ${{msg.creatingIdSuffix}}${{importId}}`);
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
          item_count: entries.length,
          items: entries
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
