from __future__ import annotations

import csv
import html
import io
import json
import math
import random
import re
from datetime import datetime
from typing import Dict, List, Optional

import requests
import streamlit as st
from bs4 import BeautifulSoup
from PIL import Image, ImageDraw, ImageFont, UnidentifiedImageError

# =========================
# 基础配置
# =========================
DOUBAN_TOP250_URL = "https://movie.douban.com/top250"
DOUBAN_SUGGEST_URL = "https://movie.douban.com/j/subject_suggest"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/126.0 Safari/537.36"
    ),
    "Referer": "https://movie.douban.com/",
    "Accept": "application/json, text/plain, */*",
}

MODE_CUSTOM = "自定义模式"
MODE_DOUBAN = "豆瓣电影模式"

HISTORY_KEYS = [
    "remaining",
    "ranked",
    "current_item",
    "low",
    "high",
    "comparisons",
    "processed",
    "finished",
    "skipped_items",
    "top_k_boundary_check",
]


# =========================
# 通用兼容函数
# =========================
def safe_divider() -> None:
    try:
        st.divider()
    except AttributeError:
        st.markdown("---")


def rerun() -> None:
    try:
        st.rerun()
    except AttributeError:
        st.experimental_rerun()


def render_button_compat(
    label: str,
    key: str,
    use_container_width: bool = True,
    button_type: str = "secondary",
) -> bool:
    try:
        return st.button(label, key=key, use_container_width=use_container_width, type=button_type)
    except TypeError:
        return st.button(label, key=key)


def render_download_button_compat(label: str, data: bytes, file_name: str, mime: str, key: str) -> None:
    try:
        st.download_button(label, data=data, file_name=file_name, mime=mime, key=key, use_container_width=True)
    except TypeError:
        st.download_button(label, data=data, file_name=file_name, mime=mime, key=key)


def show_image_compat(image_data: bytes) -> bool:
    try:
        st.image(image_data, use_container_width=True)
        return True
    except TypeError:
        try:
            st.image(image_data, use_column_width=True)
            return True
        except Exception:
            return False
    except Exception:
        return False


def bordered_container():
    try:
        return st.container(border=True)
    except TypeError:
        return st.container()


def render_app_styles() -> None:
    st.markdown(
        """
        <style>
        .compact-status {
            display: grid;
            grid-template-columns: repeat(6, minmax(0, 1fr));
            gap: 8px;
            margin: 4px 0 14px;
        }
        .status-chip {
            border: 1px solid #e6e8ef;
            border-radius: 8px;
            padding: 8px 10px;
            background: #fff;
        }
        .status-label {
            color: #667085;
            font-size: 12px;
            line-height: 1.2;
        }
        .status-value {
            color: #151922;
            font-size: 16px;
            font-weight: 700;
            line-height: 1.35;
            margin-top: 2px;
        }
        .battle-head {
            display: flex;
            align-items: center;
            justify-content: space-between;
            gap: 12px;
            margin-bottom: 10px;
        }
        .battle-label {
            color: #475467;
            font-size: 13px;
            font-weight: 700;
        }
        .battle-title {
            color: #101828;
            font-size: clamp(20px, 3vw, 30px);
            font-weight: 800;
            line-height: 1.25;
            overflow-wrap: anywhere;
            margin: 6px 0 14px;
        }
        .poster-placeholder {
            min-height: 220px;
            border: 1px dashed #cfd4dc;
            border-radius: 8px;
            background: #f7f8fb;
            color: #667085;
            display: flex;
            align-items: center;
            justify-content: center;
            text-align: center;
            padding: 16px;
            margin-bottom: 10px;
        }
        .rank-card {
            border: 1px solid #e6e8ef;
            border-radius: 8px;
            padding: 10px 12px;
            margin: 8px 0;
            background: #fff;
        }
        .rank-card.top-rank {
            border-color: #c8d2ff;
            background: #f8f9ff;
        }
        .rank-num {
            display: inline-block;
            width: 44px;
            color: #4355db;
            font-weight: 800;
        }
        .rank-name {
            color: #151922;
            font-weight: 650;
            overflow-wrap: anywhere;
        }
        @media (max-width: 820px) {
            .compact-status {
                grid-template-columns: repeat(2, minmax(0, 1fr));
            }
            .battle-title {
                font-size: 22px;
            }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


# =========================
# 豆瓣数据相关
# =========================
@st.cache_data(show_spinner=False)
def fetch_douban_top_movies(limit: int) -> List[str]:
    limit = max(1, min(250, int(limit)))
    titles: List[str] = []

    for start in range(0, 250, 25):
        if len(titles) >= limit:
            break

        resp = requests.get(
            DOUBAN_TOP250_URL,
            params={"start": start, "filter": ""},
            headers=HEADERS,
            timeout=15,
        )
        resp.raise_for_status()

        soup = BeautifulSoup(resp.text, "html.parser")
        items = soup.select("div.item span.title:first-child")
        for item in items:
            title = item.get_text(strip=True)
            if title and title not in titles:
                titles.append(title)
                if len(titles) >= limit:
                    break

    return titles[:limit]


def normalize_image_bytes(image_bytes: bytes) -> Optional[bytes]:
    if not image_bytes:
        return None

    try:
        with Image.open(io.BytesIO(image_bytes)) as img:
            if img.mode not in ("RGB", "RGBA"):
                img = img.convert("RGB")
            output = io.BytesIO()
            img.save(output, format="PNG")
            return output.getvalue()
    except (UnidentifiedImageError, OSError, ValueError):
        return None


@st.cache_data(show_spinner=False)
def fetch_douban_poster_bytes(title: str) -> Optional[bytes]:
    try:
        resp = requests.get(
            DOUBAN_SUGGEST_URL,
            params={"q": title},
            headers=HEADERS,
            timeout=8,
        )
        resp.raise_for_status()
        data = resp.json()
    except Exception:
        return None

    if not data:
        return None

    item = None
    for it in data:
        if it.get("type") == "movie":
            item = it
            break
    if item is None:
        item = data[0]

    img_url = item.get("img")
    if not img_url or "movie_default_small" in img_url:
        return None

    try:
        img_resp = requests.get(img_url, headers=HEADERS, timeout=10)
        img_resp.raise_for_status()

        content_type = (img_resp.headers.get("Content-Type") or "").lower()
        if content_type and not content_type.startswith("image/"):
            return None

        return normalize_image_bytes(img_resp.content)
    except Exception:
        return None


def prepare_douban_candidates_ui(limit: int, warm_posters: bool) -> tuple[List[str], Dict[str, Optional[bytes]]]:
    text_holder = st.empty()
    progress_holder = st.empty()
    text_holder.caption("准备中...")
    bar = progress_holder.progress(0)

    movies = fetch_douban_top_movies(limit)
    if not movies:
        bar.progress(100)
        return [], {}

    poster_map: Dict[str, Optional[bytes]] = {}
    if warm_posters:
        total_steps = max(1, len(movies))
        for idx, title in enumerate(movies, 1):
            poster_map[title] = fetch_douban_poster_bytes(title)
            bar.progress(int(idx / total_steps * 100))
    else:
        bar.progress(100)

    return movies, poster_map


# =========================
# 排序逻辑
# =========================
def get_state_prefix() -> str:
    return "rank_app"


def k(name: str) -> str:
    return f"{get_state_prefix()}_{name}"


def init_ranking_state(
    *,
    mode: str,
    theme: str,
    options: List[str],
    top_k: Optional[int] = None,
    show_poster: bool = False,
    initial_poster_map: Optional[Dict[str, Optional[bytes]]] = None,
) -> None:
    opts = options[:]
    if len(opts) < 2:
        raise ValueError("候选项至少需要 2 个才能开始排序。")

    random.shuffle(opts)
    poster_map = dict(initial_poster_map or {})

    st.session_state[k("mode")] = mode
    st.session_state[k("theme")] = theme
    st.session_state[k("source_options")] = options[:]
    st.session_state[k("source_poster_map")] = poster_map.copy()
    st.session_state[k("total")] = len(opts)
    st.session_state[k("remaining")] = opts[1:]
    st.session_state[k("ranked")] = [opts[0]]
    st.session_state[k("current_item")] = None
    st.session_state[k("low")] = 0
    st.session_state[k("high")] = 0
    st.session_state[k("comparisons")] = 0
    st.session_state[k("processed")] = 1
    st.session_state[k("finished")] = False
    st.session_state[k("top_k_boundary_check")] = False
    st.session_state[k("started")] = True
    st.session_state[k("top_k")] = top_k
    st.session_state[k("show_poster")] = show_poster
    st.session_state[k("poster_map")] = poster_map
    st.session_state[k("history")] = []
    st.session_state[k("skipped_items")] = []
    st.session_state[k("share_poster_bytes")] = b""
    st.session_state[k("share_poster_signature")] = ""


def clear_ranking_state() -> None:
    for name in [
        "mode",
        "theme",
        "source_options",
        "source_poster_map",
        "total",
        "remaining",
        "ranked",
        "current_item",
        "low",
        "high",
        "comparisons",
        "processed",
        "finished",
        "top_k_boundary_check",
        "started",
        "top_k",
        "show_poster",
        "poster_map",
        "history",
        "skipped_items",
        "share_poster_bytes",
        "share_poster_signature",
    ]:
        st.session_state.pop(k(name), None)


def reset_same_config() -> None:
    mode = st.session_state.get(k("mode"))
    theme = st.session_state.get(k("theme"), "我的排序")
    options = st.session_state.get(k("source_options"), [])
    top_k = st.session_state.get(k("top_k"))
    show_poster = st.session_state.get(k("show_poster"), False)
    source_poster_map = st.session_state.get(k("source_poster_map"), {})

    if len(options) < 2:
        st.warning("候选项至少需要 2 个才能排序。")
        return

    init_ranking_state(
        mode=mode,
        theme=theme,
        options=options,
        top_k=top_k,
        show_poster=show_poster,
        initial_poster_map=source_poster_map,
    )
    rerun()


def get_history_snapshot() -> dict:
    snapshot = {}
    for name in HISTORY_KEYS:
        value = st.session_state.get(k(name))
        if isinstance(value, list):
            snapshot[name] = value[:]
        elif isinstance(value, dict):
            snapshot[name] = value.copy()
        else:
            snapshot[name] = value
    return snapshot


def push_history_snapshot() -> None:
    history = st.session_state.setdefault(k("history"), [])
    history.append(get_history_snapshot())
    st.session_state[k("history")] = history


def restore_history_snapshot(snapshot: dict) -> None:
    for name in HISTORY_KEYS:
        value = snapshot.get(name)
        if isinstance(value, list):
            st.session_state[k(name)] = value[:]
        elif isinstance(value, dict):
            st.session_state[k(name)] = value.copy()
        else:
            st.session_state[k(name)] = value
    st.session_state[k("share_poster_bytes")] = b""
    st.session_state[k("share_poster_signature")] = ""


def undo_last_step() -> None:
    history = st.session_state.get(k("history"), [])
    if not history:
        st.warning("已经没有可以撤销的步骤了。")
        return
    snapshot = history.pop()
    st.session_state[k("history")] = history
    restore_history_snapshot(snapshot)
    rerun()


def prepare_next_item() -> None:
    if st.session_state.get(k("current_item")) is None:
        remaining = st.session_state.get(k("remaining"), [])
        if remaining:
            current = remaining.pop(0)
            st.session_state[k("remaining")] = remaining
            st.session_state[k("current_item")] = current
            st.session_state[k("low")] = 0
            ranked_count = len(st.session_state[k("ranked")])
            top_k = st.session_state.get(k("top_k"))
            use_boundary_check = top_k is not None and ranked_count >= top_k
            st.session_state[k("top_k_boundary_check")] = use_boundary_check
            st.session_state[k("high")] = max(0, ranked_count - 1) if use_boundary_check else ranked_count
        else:
            st.session_state[k("finished")] = True


def add_skipped_item(item: Optional[str]) -> None:
    if not item:
        return
    skipped_items = st.session_state.get(k("skipped_items"), [])
    if item not in skipped_items:
        skipped_items.append(item)
    st.session_state[k("skipped_items")] = skipped_items


def handle_choice(prefer_left: bool) -> None:
    if st.session_state.get(k("finished"), False):
        return

    push_history_snapshot()

    st.session_state[k("comparisons")] += 1
    ranked = st.session_state[k("ranked")]

    if st.session_state.get(k("top_k_boundary_check"), False):
        st.session_state[k("top_k_boundary_check")] = False
        if prefer_left:
            if len(ranked) <= 1:
                ranked.insert(0, st.session_state[k("current_item")])
                st.session_state[k("ranked")] = ranked[:1]
                st.session_state[k("current_item")] = None
                st.session_state[k("processed")] += 1
            else:
                st.session_state[k("low")] = 0
                st.session_state[k("high")] = len(ranked) - 1
        else:
            st.session_state[k("current_item")] = None
            st.session_state[k("processed")] += 1
        rerun()
        return

    low = st.session_state[k("low")]
    high = st.session_state[k("high")]
    mid = (low + high) // 2

    if prefer_left:
        st.session_state[k("high")] = mid
    else:
        st.session_state[k("low")] = mid + 1

    if st.session_state[k("low")] >= st.session_state[k("high")]:
        insert_pos = st.session_state[k("low")]
        ranked.insert(insert_pos, st.session_state[k("current_item")])
        st.session_state[k("ranked")] = ranked
        st.session_state[k("current_item")] = None
        st.session_state[k("processed")] += 1

        top_k = st.session_state.get(k("top_k"))
        if top_k is not None and len(st.session_state[k("ranked")]) > top_k:
            st.session_state[k("ranked")].pop()

    rerun()


def handle_skip_current_item() -> None:
    if st.session_state.get(k("finished"), False):
        return
    current_item = st.session_state.get(k("current_item"))
    if not current_item:
        return

    push_history_snapshot()

    add_skipped_item(current_item)
    st.session_state[k("current_item")] = None
    st.session_state[k("top_k_boundary_check")] = False
    st.session_state[k("processed")] = st.session_state.get(k("processed"), 0) + 1
    rerun()


def handle_skip_opponent_item() -> None:
    if st.session_state.get(k("finished"), False):
        return

    ranked = st.session_state.get(k("ranked"), [])
    if not ranked:
        return

    low = st.session_state.get(k("low"), 0)
    high = st.session_state.get(k("high"), 0)
    boundary_check = st.session_state.get(k("top_k_boundary_check"), False)
    if high <= 0 and not boundary_check:
        return

    mid = get_current_opponent_index(ranked, low, high)
    if mid < 0 or mid >= len(ranked):
        return

    push_history_snapshot()

    opponent = ranked.pop(mid)
    st.session_state[k("ranked")] = ranked
    add_skipped_item(opponent)

    current_item = st.session_state.get(k("current_item"))
    if current_item is not None and len(ranked) == 0:
        st.session_state[k("ranked")] = [current_item]
        st.session_state[k("current_item")] = None
        st.session_state[k("low")] = 0
        st.session_state[k("high")] = 0
        st.session_state[k("top_k_boundary_check")] = False
        st.session_state[k("processed")] = st.session_state.get(k("processed"), 0) + 1
    else:
        st.session_state[k("top_k_boundary_check")] = False
        st.session_state[k("low")] = 0
        st.session_state[k("high")] = len(st.session_state.get(k("ranked"), []))

    rerun()


# =========================
# 工具函数
# =========================
def parse_options_text(text: str) -> List[str]:
    seen = set()
    options: List[str] = []
    for raw in text.splitlines():
        item = raw.strip()
        if not item:
            continue
        if item not in seen:
            options.append(item)
            seen.add(item)
    return options


def estimated_comparisons(total: int, top_k: Optional[int]) -> int:
    if total <= 1:
        return 0
    if top_k is None:
        return max(total - 1, int(sum(math.ceil(math.log2(i)) for i in range(2, total + 1))))
    top_k = max(1, min(top_k, total))
    base = sum(math.ceil(math.log2(i)) for i in range(2, min(top_k, total) + 1))
    extra = max(0, total - top_k) * (1 + max(0, math.ceil(math.log2(max(1, top_k - 1)))))
    return int(base + extra)


def estimated_remaining_comparisons(total: int, processed: int, top_k: Optional[int]) -> int:
    current_item = st.session_state.get(k("current_item"))
    ranked_count = len(st.session_state.get(k("ranked"), []))
    remaining_count = len(st.session_state.get(k("remaining"), []))

    current_cost = 0
    if current_item is not None:
        if st.session_state.get(k("top_k_boundary_check"), False):
            current_cost = 1
        else:
            interval = max(1, st.session_state.get(k("high"), 0) - st.session_state.get(k("low"), 0))
            current_cost = max(1, math.ceil(math.log2(interval))) if interval > 1 else 1

    if top_k is None:
        future_cost = sum(
            max(1, math.ceil(math.log2(max(2, ranked_count + i))))
            for i in range(1, remaining_count + 1)
        )
    else:
        future_cost = 0
        kept = ranked_count
        for _ in range(remaining_count):
            if kept < top_k:
                kept += 1
                future_cost += max(1, math.ceil(math.log2(max(2, kept))))
            else:
                future_cost += 1 + max(0, math.ceil(math.log2(max(1, top_k - 1))))

    return max(0, current_cost + future_cost)


def filter_items(items: List[str], query: str) -> List[str]:
    query = query.strip().lower()
    if not query:
        return items
    return [item for item in items if query in item.lower()]


def render_searchable_item_preview(items: List[str], search_key: str, empty_text: str = "还没有候选项。") -> None:
    if not items:
        st.write(empty_text)
        return

    query = st.text_input("搜索候选项", key=search_key, placeholder="输入关键词筛选")
    filtered = filter_items(items, query)
    display_items = filtered[:30]
    st.caption(f"显示 {len(display_items)} / {len(filtered)} 项；完整候选共 {len(items)} 项。")
    for i, item in enumerate(display_items, 1):
        st.write(f"{i}. {item}")
    if len(filtered) > len(display_items):
        st.caption("还有更多结果未显示，请继续输入关键词缩小范围。")


def build_export_payloads(
    *,
    theme: str,
    mode: str,
    ranked: List[str],
    skipped_items: List[str],
    top_k: Optional[int],
    comparisons: int,
) -> tuple[bytes, bytes, bytes]:
    generated_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    txt_lines = [
        theme,
        f"模式：{mode}",
        "类型：完整排序" if top_k is None else f"类型：Top {min(top_k, len(ranked))}",
        f"比较次数：{comparisons}",
        f"生成时间：{generated_at}",
        "",
        "排名结果：",
    ]
    txt_lines.extend(f"{idx}. {item}" for idx, item in enumerate(ranked, 1))
    if skipped_items:
        txt_lines.extend(["", "已剔除："])
        txt_lines.extend(f"- {item}" for item in skipped_items)
    txt_bytes = "\n".join(txt_lines).encode("utf-8-sig")

    csv_buffer = io.StringIO()
    writer = csv.writer(csv_buffer)
    writer.writerow(["rank", "item", "status"])
    for idx, item in enumerate(ranked, 1):
        writer.writerow([idx, item, "ranked"])
    for item in skipped_items:
        writer.writerow(["", item, "skipped"])
    csv_bytes = csv_buffer.getvalue().encode("utf-8-sig")

    json_bytes = json.dumps(
        {
            "theme": theme,
            "mode": mode,
            "top_k": top_k,
            "comparisons": comparisons,
            "generated_at": generated_at,
            "ranked": [{"rank": idx, "item": item} for idx, item in enumerate(ranked, 1)],
            "skipped_items": skipped_items,
        },
        ensure_ascii=False,
        indent=2,
    ).encode("utf-8")

    return txt_bytes, csv_bytes, json_bytes


def render_ranked_list(ranked: List[str]) -> None:
    for i, item in enumerate(ranked, 1):
        top_class = " top-rank" if i <= 3 else ""
        st.markdown(
            f"""
            <div class="rank-card{top_class}">
              <span class="rank-num">#{i:02d}</span>
              <span class="rank-name">{html.escape(item)}</span>
            </div>
            """,
            unsafe_allow_html=True,
        )


def get_poster_for_option(name: str) -> Optional[bytes]:
    poster_map = st.session_state.setdefault(k("poster_map"), {})
    if name in poster_map:
        return poster_map[name]

    poster_bytes = fetch_douban_poster_bytes(name)
    poster_map[name] = poster_bytes
    st.session_state[k("poster_map")] = poster_map
    return poster_bytes


def slugify_filename(text: str) -> str:
    cleaned = re.sub(r"[^\w\u4e00-\u9fff-]+", "_", text.strip())
    cleaned = re.sub(r"_+", "_", cleaned).strip("_")
    return cleaned or "ranking"


def load_font(size: int, bold: bool = False) -> ImageFont.ImageFont:
    candidates = [
        "C:/Windows/Fonts/msyhbd.ttc" if bold else "C:/Windows/Fonts/msyh.ttc",
        "C:/Windows/Fonts/simhei.ttf",
        "C:/Windows/Fonts/simsun.ttc",
        "/System/Library/Fonts/PingFang.ttc",
        "/System/Library/Fonts/STHeiti Medium.ttc",
        "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ]
    for font_path in candidates:
        try:
            return ImageFont.truetype(font_path, size=size)
        except Exception:
            continue
    return ImageFont.load_default()


def wrap_text(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.ImageFont, max_width: int) -> List[str]:
    if not text:
        return [""]
    lines: List[str] = []
    current = ""

    for ch in text:
        test = current + ch
        width = draw.textbbox((0, 0), test, font=font)[2]
        if current and width > max_width:
            lines.append(current)
            current = ch
        else:
            current = test

    if current:
        lines.append(current)
    return lines or [""]


def build_share_poster_signature(theme: str, ranked: List[str], skipped_items: List[str], top_k: Optional[int], mode: str) -> str:
    return "|".join(
        [
            theme,
            mode,
            "full" if top_k is None else f"top{top_k}",
            "ranked:" + "||".join(ranked),
            "skipped:" + "||".join(skipped_items),
        ]
    )


def generate_share_poster_bytes(theme: str, ranked: List[str], skipped_items: List[str], top_k: Optional[int], mode: str) -> bytes:
    width = 1080
    padding = 64
    line_height = 56

    measure_img = Image.new("RGB", (1, 1))
    measure_draw = ImageDraw.Draw(measure_img)

    title_font = load_font(52, bold=True)
    subtitle_font = load_font(26)
    item_font = load_font(34)
    small_font = load_font(22)

    max_text_width = width - padding * 2 - 120
    ranked_layout = []
    for item in ranked:
        wrapped = wrap_text(measure_draw, item, item_font, max_text_width)
        row_height = max(line_height, len(wrapped) * 40 + 12)
        ranked_layout.append((item, wrapped, row_height))

    skipped_lines: List[str] = []
    if skipped_items:
        joined = "、".join(skipped_items[:12])
        if len(skipped_items) > 12:
            joined += "……"
        skipped_lines = wrap_text(measure_draw, joined, small_font, width - padding * 2)

    content_height = padding + 78 + 54 + 28
    content_height += sum(row_height for _, _, row_height in ranked_layout)
    if skipped_items:
        content_height += 12 + 2 + 24 + 36 + len(skipped_lines) * 28
    height = max(760, content_height + 140)

    img = Image.new("RGB", (width, height), (246, 247, 251))
    draw = ImageDraw.Draw(img)

    draw.rounded_rectangle((36, 36, width - 36, height - 36), radius=36, fill=(255, 255, 255), outline=(228, 231, 236), width=2)

    y = padding
    draw.text((padding, y), theme, font=title_font, fill=(20, 24, 35))
    y += 78

    subtitle = "自定义完整排序" if top_k is None else f"豆瓣电影 Top {min(top_k, len(ranked))}"
    draw.text((padding, y), subtitle, font=subtitle_font, fill=(98, 106, 120))
    y += 54

    draw.line((padding, y, width - padding, y), fill=(230, 233, 238), width=2)
    y += 28

    for idx, (_, wrapped, row_height) in enumerate(ranked_layout, 1):
        rank_text = f"{idx:02d}"
        draw.text((padding, y), rank_text, font=item_font, fill=(73, 93, 241))
        for j, line in enumerate(wrapped):
            draw.text((padding + 90, y + j * 40), line, font=item_font, fill=(20, 24, 35))
        y += row_height

    if skipped_items:
        y += 12
        draw.line((padding, y, width - padding, y), fill=(230, 233, 238), width=2)
        y += 24
        skipped_text = f"已剔除未看过/不熟悉项：{len(skipped_items)} 个"
        draw.text((padding, y), skipped_text, font=small_font, fill=(98, 106, 120))
        y += 36

        for line in skipped_lines:
            draw.text((padding, y), line, font=small_font, fill=(98, 106, 120))
            y += 28

    footer = f"Generated at {datetime.now().strftime('%Y-%m-%d %H:%M')}"
    draw.text((padding, height - 70), footer, font=small_font, fill=(140, 146, 156))

    out = io.BytesIO()
    img.save(out, format="PNG")
    return out.getvalue()


def ensure_share_poster_generated() -> None:
    ranked = st.session_state.get(k("ranked"), [])
    if not ranked:
        return

    theme = st.session_state.get(k("theme"), "我的排序")
    skipped_items = st.session_state.get(k("skipped_items"), [])
    top_k = st.session_state.get(k("top_k"))
    mode = st.session_state.get(k("mode"), MODE_CUSTOM)
    signature = build_share_poster_signature(theme, ranked, skipped_items, top_k, mode)

    if st.session_state.get(k("share_poster_signature")) == signature and st.session_state.get(k("share_poster_bytes")):
        return

    poster_bytes = generate_share_poster_bytes(theme, ranked, skipped_items, top_k, mode)
    st.session_state[k("share_poster_bytes")] = poster_bytes
    st.session_state[k("share_poster_signature")] = signature


def get_current_opponent_index(ranked: List[str], low: int, high: int) -> int:
    if st.session_state.get(k("top_k_boundary_check"), False):
        return max(0, len(ranked) - 1)
    return max(0, min(len(ranked) - 1, (low + high) // 2))


def render_poster_placeholder() -> None:
    st.markdown(
        '<div class="poster-placeholder">海报暂时不可用<br>排序仍可继续</div>',
        unsafe_allow_html=True,
    )


def render_option_card(
    label: str,
    title: str,
    button_text: str,
    button_key: str,
    prefer_left: bool,
    show_poster: bool,
) -> None:
    with bordered_container():
        st.markdown(
            f"""
            <div class="battle-head">
              <span class="battle-label">{html.escape(label)}</span>
              <span class="battle-label">1v1</span>
            </div>
            """,
            unsafe_allow_html=True,
        )
        if show_poster:
            poster = get_poster_for_option(title)
            if poster and not show_image_compat(poster):
                render_poster_placeholder()
            elif not poster:
                render_poster_placeholder()

        st.markdown(f'<div class="battle-title">{html.escape(title)}</div>', unsafe_allow_html=True)
        if render_button_compat(button_text, key=button_key, use_container_width=True, button_type="primary"):
            handle_choice(prefer_left=prefer_left)


# =========================
# 排序页面渲染
# =========================
def render_result_section(total: int, comparisons: int, top_k: Optional[int]) -> None:
    ranked = st.session_state.get(k("ranked"), [])
    skipped_items = st.session_state.get(k("skipped_items"), [])

    ensure_share_poster_generated()

    if top_k is None:
        st.success("🎉 排序完成！下面是你的完整排名：")
    else:
        st.success(f"🎉 排序完成！下面是你的 Top {len(ranked)}：")

    render_ranked_list(ranked)

    summary = f"共处理 {total} 个候选项，完成比较 {comparisons} 次。"
    if skipped_items:
        summary += f" 已剔除 {len(skipped_items)} 项。"
    st.caption(summary)

    poster_bytes = st.session_state.get(k("share_poster_bytes"), b"")
    if poster_bytes:
        with st.expander("🖼️ 可分享海报", expanded=True):
            show_image_compat(poster_bytes)
            file_name = f"{slugify_filename(st.session_state.get(k('theme'), 'ranking'))}_share.png"
            render_download_button_compat(
                "⬇️ 下载分享海报",
                data=poster_bytes,
                file_name=file_name,
                mime="image/png",
                key="btn_download_share_poster",
            )

    theme = st.session_state.get(k("theme"), "ranking")
    mode = st.session_state.get(k("mode"), MODE_CUSTOM)
    txt_bytes, csv_bytes, json_bytes = build_export_payloads(
        theme=theme,
        mode=mode,
        ranked=ranked,
        skipped_items=skipped_items,
        top_k=top_k,
        comparisons=comparisons,
    )
    base_name = slugify_filename(theme)
    with st.expander("导出结果", expanded=False):
        d1, d2, d3 = st.columns(3)
        with d1:
            render_download_button_compat("下载 TXT", txt_bytes, f"{base_name}.txt", "text/plain", "btn_export_txt")
        with d2:
            render_download_button_compat("下载 CSV", csv_bytes, f"{base_name}.csv", "text/csv", "btn_export_csv")
        with d3:
            render_download_button_compat("下载 JSON", json_bytes, f"{base_name}.json", "application/json", "btn_export_json")

    col1, col2, col3 = st.columns(3)
    with col1:
        if render_button_compat("↩️ 撤销上一步", key="btn_undo_result", use_container_width=True):
            undo_last_step()
    with col2:
        if render_button_compat("🔁 用同一配置重新排一次", key="btn_reset_same", use_container_width=True):
            reset_same_config()
    with col3:
        if render_button_compat("🗑️ 清除本次排序结果", key="btn_clear_result", use_container_width=True):
            clear_ranking_state()
            rerun()


def render_right_panel() -> None:
    if not st.session_state.get(k("started"), False):
        st.info("参数填写完成后，点击开始按钮即可。")
        return

    theme = st.session_state.get(k("theme"), "我的排序")
    total = st.session_state.get(k("total"), 0)
    processed = st.session_state.get(k("processed"), 0)
    comparisons = st.session_state.get(k("comparisons"), 0)
    top_k = st.session_state.get(k("top_k"))
    show_poster = st.session_state.get(k("show_poster"), False)
    mode = st.session_state.get(k("mode"), MODE_CUSTOM)
    skipped_items = st.session_state.get(k("skipped_items"), [])

    if st.session_state.get(k("finished"), False):
        st.subheader(f"当前主题：{theme}")
        render_result_section(total=total, comparisons=comparisons, top_k=top_k)
        return

    prepare_next_item()
    if st.session_state.get(k("finished"), False):
        rerun()
        return

    current = st.session_state[k("current_item")]
    low = st.session_state[k("low")]
    high = st.session_state[k("high")]
    opponent_index = get_current_opponent_index(st.session_state[k("ranked")], low, high)
    opponent = st.session_state[k("ranked")][opponent_index]

    progress = processed / total if total else 0
    st.progress(progress)
    remaining_estimate = estimated_remaining_comparisons(total, processed, top_k)
    mode_label = "自定义完整排序" if top_k is None else f"豆瓣 Top {top_k}"
    if top_k is not None:
        poster_map = st.session_state.get(k("source_poster_map"), {})
        poster_hint = f"{sum(1 for v in poster_map.values() if v)} 张海报"
    else:
        poster_hint = "无海报"

    st.markdown(
        f"""
        <div class="compact-status">
          <div class="status-chip"><div class="status-label">主题</div><div class="status-value">{html.escape(theme)}</div></div>
          <div class="status-chip"><div class="status-label">模式</div><div class="status-value">{html.escape(mode_label)}</div></div>
          <div class="status-chip"><div class="status-label">进度</div><div class="status-value">{processed}/{total}</div></div>
          <div class="status-chip"><div class="status-label">已比较</div><div class="status-value">{comparisons}</div></div>
          <div class="status-chip"><div class="status-label">预计剩余</div><div class="status-value">约 {remaining_estimate}</div></div>
          <div class="status-chip"><div class="status-label">剔除/海报</div><div class="status-value">{len(skipped_items)} / {poster_hint}</div></div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    if top_k is None:
        st.markdown("### 请选择，你更偏好哪一个？")
    else:
        if st.session_state.get(k("top_k_boundary_check"), False):
            st.caption("这个候选会先挑战当前榜单末位；如果没有更喜欢它，会直接跳过，减少不必要比较。")
        st.markdown("### 请选择，你更喜欢哪一部电影？")

    c1, c2 = st.columns(2)
    with c1:
        render_option_card(
            label="选项 A",
            title=current,
            button_text="更喜欢 A",
            button_key="btn_left",
            prefer_left=True,
            show_poster=show_poster and mode == MODE_DOUBAN,
        )

    with c2:
        render_option_card(
            label="选项 B",
            title=opponent,
            button_text="更喜欢 B",
            button_key="btn_right",
            prefer_left=False,
            show_poster=show_poster and mode == MODE_DOUBAN,
        )

    ctrl1, ctrl2, ctrl3 = st.columns(3)
    with ctrl1:
        if render_button_compat("↩️ 撤销上一步", key="btn_undo_live", use_container_width=True):
            undo_last_step()
    with ctrl2:
        label_a = "👀 没看过 A（剔除 A）" if mode == MODE_DOUBAN else "👀 不熟悉 A（剔除 A）"
        if render_button_compat(label_a, key="btn_skip_current", use_container_width=True):
            handle_skip_current_item()
    with ctrl3:
        label_b = "👀 没看过 B（剔除 B）" if mode == MODE_DOUBAN else "👀 不熟悉 B（剔除 B）"
        if render_button_compat(label_b, key="btn_skip_opponent", use_container_width=True):
            handle_skip_opponent_item()

    ranked = st.session_state.get(k("ranked"), [])
    expander_title = "📊 当前临时完整排序" if top_k is None else f"📊 当前临时 Top {len(ranked)} 榜单"
    with st.expander(expander_title, expanded=False):
        for i, item in enumerate(ranked, 1):
            st.write(f"{i}. {item}")

    if skipped_items:
        with st.expander("⏭️ 已剔除的候选项", expanded=False):
            for i, item in enumerate(skipped_items, 1):
                st.write(f"{i}. {item}")


# =========================
# 三步式流程页面
# =========================
def get_ui_step() -> int:
    step = int(st.session_state.get("ui_step", 1))
    return step if step in (1, 2, 3) else 1


def go_to_step(step: int) -> None:
    st.session_state["ui_step"] = max(1, min(3, int(step)))
    rerun()


def get_selected_mode() -> str:
    return st.session_state.get("ui_selected_mode", MODE_CUSTOM)


def set_selected_mode(mode: str) -> None:
    st.session_state["ui_selected_mode"] = mode


def render_step_header(step: int, title: str, subtitle: str = "") -> None:
    step = max(1, min(3, int(step)))
    st.progress(step / 3)

    cols = st.columns(3)
    labels = [
        ("① 选择模式", 1),
        ("② 填写参数", 2),
        ("③ 开始排序", 3),
    ]
    for col, (label, idx) in zip(cols, labels):
        with col:
            if idx == step:
                st.markdown(f"**{label}**")
            else:
                st.caption(label)

    st.subheader(title)
    if subtitle:
        st.caption(subtitle)
    safe_divider()


def render_mode_selection_page() -> None:
    current_mode = get_selected_mode()
    render_step_header(
        1,
        "先决定你要用哪种排序模式",
        "这一步只选模式，不填参数。",
    )

    mode = st.radio(
        "选择模式",
        [MODE_CUSTOM, MODE_DOUBAN],
        index=0 if current_mode == MODE_CUSTOM else 1,
        help="自定义模式适合任意主题；豆瓣电影模式会自动读取豆瓣 Top250 的电影。",
        key="ui_mode_step1",
    )
    set_selected_mode(mode)

    safe_divider()
    if mode == MODE_CUSTOM:
        st.info("自定义模式：你自己填写主题和候选项，适合歌手、游戏、电影、角色等任意内容。")
    else:
        st.info("豆瓣电影模式：你只需要填写 Top 数量和候选池范围，系统会自动读取豆瓣 Top250。")

    spacer, next_col = st.columns([1, 1])
    with spacer:
        st.empty()
    with next_col:
        if render_button_compat("下一步：填写参数 →", key="btn_to_step2", use_container_width=True, button_type="primary"):
            go_to_step(2)


def render_custom_parameter_page(mode: str) -> None:
    st.text_input("主题名称", value=st.session_state.get("ui_custom_theme", "我的偏好排序"), key="ui_custom_theme")
    st.text_area(
        "候选项（每行一个）",
        value=st.session_state.get("ui_custom_options_text", ""),
        height=320,
        key="ui_custom_options_text",
        placeholder="例：\n周杰伦\n陈奕迅\n王菲\n张学友",
    )

    options = parse_options_text(st.session_state.get("ui_custom_options_text", ""))
    st.caption(f"当前有效候选项：{len(options)} 个（已自动去重、去空行）。")
    st.caption(f"预计比较次数大约：{estimated_comparisons(len(options), None)} 次。")

    with st.expander("查看当前候选项", expanded=False):
        render_searchable_item_preview(options, "ui_custom_preview_search")

    nav1, nav2, nav3 = st.columns(3)
    with nav1:
        if render_button_compat("← 返回上一步", key="btn_custom_back_step1", use_container_width=True):
            go_to_step(1)
    with nav2:
        if render_button_compat("🧹 清空参数", key="btn_clear_custom_step2", use_container_width=True):
            clear_ranking_state()
            st.session_state["ui_custom_theme"] = "我的偏好排序"
            st.session_state["ui_custom_options_text"] = ""
            rerun()
    with nav3:
        if render_button_compat("进入第 3 步：开始排序 →", key="btn_start_custom_step2", use_container_width=True, button_type="primary"):
            if len(options) < 2:
                st.warning("请至少输入 2 个候选项。")
            else:
                init_ranking_state(
                    mode=mode,
                    theme=(st.session_state.get("ui_custom_theme", "") or "").strip() or "我的偏好排序",
                    options=options,
                    top_k=None,
                    show_poster=False,
                    initial_poster_map=None,
                )
                st.session_state["ui_step"] = 3
                rerun()


def render_douban_parameter_page(mode: str) -> None:
    st.text_input("主题名称", value=st.session_state.get("ui_douban_theme", "豆瓣电影偏好排序"), key="ui_douban_theme")

    top_k = int(
        st.number_input(
            "最后要排出 Top 多少",
            min_value=1,
            max_value=250,
            value=int(st.session_state.get("ui_douban_top_k", 10)),
            step=1,
            key="ui_douban_top_k",
        )
    )
    pool_n = int(
        st.number_input(
            "使用豆瓣 Top 前多少作为候选池",
            min_value=1,
            max_value=250,
            value=int(st.session_state.get("ui_douban_pool_n", 100)),
            step=1,
            key="ui_douban_pool_n",
            help="比如填 100，就会用豆瓣 Top250 里的前 100 部电影作为候选项。",
        )
    )
    show_poster = st.checkbox(
        "排序时显示豆瓣海报",
        value=bool(st.session_state.get("ui_douban_show_poster", True)),
        key="ui_douban_show_poster",
    )

    if pool_n < top_k:
        st.error("候选池数量必须不小于 Top 数量。请让“候选池” >= “Top”。")
    else:
        st.caption(f"将从豆瓣 Top250 中读取前 {pool_n} 部电影，最后给出你的 Top {top_k}。")
        st.caption(f"预计比较次数大约：{estimated_comparisons(pool_n, top_k)} 次。")

    if render_button_compat("👀 预览候选电影", key="btn_preview_douban_step2", use_container_width=True):
        if pool_n < top_k:
            st.warning("请先修正参数：候选池数量不能小于 Top 数量。")
        else:
            try:
                movies, _ = prepare_douban_candidates_ui(pool_n, warm_posters=False)
                st.session_state["ui_douban_preview_movies"] = movies
                st.session_state["ui_douban_preview_pool_n"] = pool_n
            except Exception as e:
                st.error(f"读取豆瓣电影列表失败：{e}")

    preview_movies = st.session_state.get("ui_douban_preview_movies", [])
    if st.session_state.get("ui_douban_preview_pool_n") != pool_n:
        preview_movies = []
    if preview_movies:
        with st.expander(f"当前候选电影（前 {len(preview_movies)} 部）", expanded=True):
            render_searchable_item_preview(preview_movies, "ui_douban_preview_search", empty_text="还没有预览结果。")

    nav1, nav2, nav3 = st.columns(3)
    with nav1:
        if render_button_compat("← 返回上一步", key="btn_douban_back_step1", use_container_width=True):
            go_to_step(1)
    with nav2:
        if render_button_compat("🧹 清空参数", key="btn_clear_douban_step2", use_container_width=True):
            clear_ranking_state()
            st.session_state["ui_douban_theme"] = "豆瓣电影偏好排序"
            st.session_state["ui_douban_top_k"] = 10
            st.session_state["ui_douban_pool_n"] = 100
            st.session_state["ui_douban_show_poster"] = True
            st.session_state.pop("ui_douban_preview_movies", None)
            st.session_state.pop("ui_douban_preview_pool_n", None)
            rerun()
    with nav3:
        if render_button_compat("进入第 3 步：开始排序 →", key="btn_start_douban_step2", use_container_width=True, button_type="primary"):
            if pool_n < top_k:
                st.warning("请先修正参数：候选池数量不能小于 Top 数量。")
            else:
                try:
                    movies, poster_map = prepare_douban_candidates_ui(pool_n, warm_posters=show_poster)
                    if len(movies) < 2:
                        st.error("获取到的电影数量不足 2，无法开始排序。")
                    else:
                        init_ranking_state(
                            mode=mode,
                            theme=(st.session_state.get("ui_douban_theme", "") or "").strip() or "豆瓣电影偏好排序",
                            options=movies,
                            top_k=top_k,
                            show_poster=show_poster,
                            initial_poster_map=poster_map,
                        )
                        st.session_state["ui_step"] = 3
                        rerun()
                except Exception as e:
                    st.error(f"读取豆瓣电影列表失败：{e}")


def render_parameter_page() -> None:
    mode = get_selected_mode()
    render_step_header(
        2,
        "填写本次排序参数",
        "根据你刚才选择的模式，补充主题、候选池和展示设置。",
    )

    if mode == MODE_CUSTOM:
        render_custom_parameter_page(mode)
    else:
        render_douban_parameter_page(mode)


def render_sorting_page() -> None:
    render_step_header(
        3,
        "开始排序",
        "在这一页完成 1v1 选择、撤销、剔除和结果分享。",
    )

    theme = st.session_state.get(k("theme"))
    started = st.session_state.get(k("started"), False)
    mode = st.session_state.get(k("mode"), get_selected_mode()) if started else get_selected_mode()

    summary_cols = st.columns(3)
    with summary_cols[0]:
        st.caption(f"当前模式：{mode}")
    with summary_cols[1]:
        st.caption(f"当前主题：{theme or '尚未开始'}")
    with summary_cols[2]:
        st.caption("步骤支持来回切换")

    nav1, nav2 = st.columns(2)
    with nav1:
        if render_button_compat("← 返回第 2 步修改参数", key="btn_back_to_step2", use_container_width=True):
            go_to_step(2)
    with nav2:
        if render_button_compat("重新选择模式", key="btn_back_to_step1", use_container_width=True):
            go_to_step(1)

    safe_divider()

    if not started:
        st.info("你还没有开始排序。请先返回第 2 步填写参数，然后进入第 3 步。")
        return

    render_right_panel()


# =========================
# 主程序
# =========================
def main() -> None:
    st.set_page_config(
        page_title="统一偏好排序工具",
        page_icon="🎯",
        layout="wide",
    )
    render_app_styles()

    if "ui_selected_mode" not in st.session_state:
        st.session_state["ui_selected_mode"] = MODE_CUSTOM
    if "ui_step" not in st.session_state:
        st.session_state["ui_step"] = 1

    st.title("🎯 统一偏好排序工具")
    st.markdown("现在改成了更清晰的三步流程：**先选模式，再填参数，最后专注排序**。")

    step = get_ui_step()
    if step == 1:
        render_mode_selection_page()
    elif step == 2:
        render_parameter_page()
    else:
        render_sorting_page()

    safe_divider()
    st.caption("说明：豆瓣模式准备阶段会显示“准备中...”。如果网络异常或海报抓取失败，单张海报可能不显示，但排序功能仍可继续。")


if __name__ == "__main__":
    main()
