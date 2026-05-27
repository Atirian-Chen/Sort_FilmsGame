from __future__ import annotations

import csv
import base64
import hashlib
import html
import io
import json
import math
import random
import re
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

import requests
import streamlit as st
import streamlit.components.v1 as components
from bs4 import BeautifulSoup
from PIL import Image, ImageDraw, ImageFont, UnidentifiedImageError

# =========================
# 基础配置
# =========================
DOUBAN_TOP250_URL = "https://movie.douban.com/top250"
DOUBAN_SUGGEST_URL = "https://movie.douban.com/j/subject_suggest"
APP_TITLE = "偏爱对决"
APP_SUBTITLE = "用一次次二选一，排出真正属于你的榜单。"
COVER_IMAGE_PATH = Path(__file__).parent / "assets" / "cover_banner.png"
BATTLE_PICKER_COMPONENT = components.declare_component(
    "battle_picker",
    path=str(Path(__file__).parent / "components" / "battle_picker"),
)

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

CUSTOM_TEMPLATES = [
    {
        "name": "华语歌手",
        "theme": "我的华语歌手偏爱榜",
        "items": ["周杰伦", "陈奕迅", "王菲", "张学友", "孙燕姿", "林俊杰", "蔡依林", "李宗盛", "张惠妹", "陶喆", "梁静茹", "五月天"],
    },
    {
        "name": "周末电影",
        "theme": "我的周末电影 Top",
        "items": ["肖申克的救赎", "霸王别姬", "千与千寻", "泰坦尼克号", "盗梦空间", "星际穿越", "疯狂动物城", "机器人总动员", "怦然心动", "海上钢琴师"],
    },
    {
        "name": "游戏神作",
        "theme": "我的游戏神作榜",
        "items": ["塞尔达传说：旷野之息", "艾尔登法环", "荒野大镖客：救赎2", "巫师3", "黑神话：悟空", "赛博朋克2077", "只狼", "星露谷物语", "空洞骑士", "传送门2"],
    },
    {
        "name": "旅行城市",
        "theme": "最想再去一次的城市",
        "items": ["上海", "北京", "成都", "杭州", "重庆", "广州", "南京", "厦门", "西安", "青岛", "苏州", "香港"],
    },
]

DOUBAN_PRESETS = [
    ("快排局", 10, 40),
    ("标准局", 10, 100),
    ("深挖局", 20, 180),
]

SHARE_POSTER_STYLES = ["清爽白卡", "热映红毯", "午夜霓虹"]
SHARE_POSTER_FORMATS = ["方图 1:1", "长图 9:16", "自适应长图"]

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
    "defers",
]

RANKING_STATE_KEYS = [
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
    "poster_fetch_failed",
    "history",
    "skipped_items",
    "user_name",
    "seed_text",
    "blind_mode",
    "side_shuffle",
    "defers",
    "share_poster_bytes",
    "share_poster_signature",
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


def poster_data_uri(image_data: Optional[bytes]) -> Optional[str]:
    if not image_data:
        return None
    encoded = base64.b64encode(image_data).decode("ascii")
    return f"data:image/png;base64,{encoded}"


def image_file_data_uri(path: Path) -> Optional[str]:
    if not path.exists():
        return None
    try:
        encoded = base64.b64encode(path.read_bytes()).decode("ascii")
        return f"data:image/png;base64,{encoded}"
    except OSError:
        return None


def stable_int(value: str) -> int:
    digest = hashlib.sha256(value.encode("utf-8")).hexdigest()
    return int(digest[:16], 16)


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
            margin: 4px 0 8px;
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
            margin-bottom: 6px;
        }
        .battle-label {
            color: #475467;
            font-size: 13px;
            font-weight: 700;
        }
        .battle-title {
            color: #101828;
            font-size: clamp(18px, 2.3vw, 24px);
            font-weight: 800;
            line-height: 1.25;
            overflow-wrap: anywhere;
            margin: 0 0 8px;
            min-height: 32px;
        }
        .poster-placeholder {
            height: min(46vh, 440px);
            border: 1px dashed #cfd4dc;
            border-radius: 8px;
            background: #f7f8fb;
            color: #667085;
            display: flex;
            align-items: center;
            justify-content: center;
            text-align: center;
            padding: 16px;
            margin-bottom: 0;
        }
        .poster-choice-frame {
            height: min(46vh, 440px);
            border: 1px solid #e6e8ef;
            border-radius: 8px;
            background: #f8f9fb;
            padding: 8px;
            margin-bottom: 8px;
        }
        .poster-choice-img {
            display: block;
            width: 100%;
            height: 100%;
            object-fit: contain;
            border-radius: 6px;
        }
        .poster-choice-fallback {
            height: 100%;
            display: flex;
            align-items: center;
            justify-content: center;
            color: #475467;
            font-weight: 700;
            text-align: center;
            padding: 16px;
        }
        .choice-help {
            color: #667085;
            font-size: 13px;
            font-weight: 700;
            margin: 6px 0 0;
            text-align: center;
        }
        .live-controls {
            margin: 4px 0 10px;
        }
        .cover-title {
            font-size: clamp(30px, 4vw, 50px);
            font-weight: 900;
            line-height: 1.05;
            color: #111827;
            margin: 8px 0 8px;
        }
        .cover-subtitle {
            color: #4b5563;
            font-size: 16px;
            line-height: 1.55;
            margin-bottom: 8px;
        }
        .cover-tag {
            display: inline-block;
            border: 1px solid #d0d5dd;
            border-radius: 999px;
            padding: 6px 12px;
            color: #475467;
            font-weight: 700;
            font-size: 13px;
            background: #fff;
        }
        .cover-image {
            width: 100%;
            max-height: 260px;
            object-fit: cover;
            border-radius: 10px;
            display: block;
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
        .insight-grid {
            display: grid;
            grid-template-columns: repeat(4, minmax(0, 1fr));
            gap: 10px;
            margin: 10px 0 12px;
        }
        .insight-card {
            border: 1px solid #e6e8ef;
            border-radius: 8px;
            background: #fff;
            padding: 12px;
            min-width: 0;
        }
        .insight-label {
            color: #667085;
            font-size: 12px;
            line-height: 1.25;
            margin-bottom: 4px;
        }
        .insight-value {
            color: #101828;
            font-size: 17px;
            font-weight: 800;
            line-height: 1.3;
            overflow-wrap: anywhere;
        }
        .share-callout {
            border: 1px solid #d9e2ff;
            border-radius: 8px;
            background: #f7f9ff;
            padding: 12px 14px;
            color: #24324b;
            margin: 8px 0 12px;
        }
        .mini-note {
            color: #667085;
            font-size: 13px;
            line-height: 1.5;
        }
        @media (max-width: 820px) {
            .compact-status {
                grid-template-columns: repeat(2, minmax(0, 1fr));
            }
            .insight-grid {
                grid-template-columns: repeat(2, minmax(0, 1fr));
            }
            .battle-title {
                font-size: 22px;
            }
            .poster-choice-frame,
            .poster-placeholder {
                height: min(38vh, 360px);
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
def fetch_douban_top_movie_entries(limit: int) -> List[Dict[str, Optional[str]]]:
    limit = max(1, min(250, int(limit)))
    entries: List[Dict[str, Optional[str]]] = []
    seen = set()

    for start in range(0, 250, 25):
        if len(entries) >= limit:
            break

        resp = requests.get(
            DOUBAN_TOP250_URL,
            params={"start": start, "filter": ""},
            headers=HEADERS,
            timeout=15,
        )
        resp.raise_for_status()

        soup = BeautifulSoup(resp.text, "html.parser")
        items = soup.select("div.item")
        for item in items:
            title_el = item.select_one("span.title")
            img_el = item.select_one("div.pic img")

            title = title_el.get_text(strip=True) if title_el else ""
            if not title and img_el:
                title = img_el.get("alt", "").strip()

            poster_url = None
            if img_el:
                poster_url = img_el.get("src") or img_el.get("data-src")

            if title and title not in seen:
                entries.append({"title": title, "poster_url": poster_url})
                seen.add(title)
                if len(entries) >= limit:
                    break

    return entries[:limit]


@st.cache_data(show_spinner=False)
def fetch_douban_top_movies(limit: int) -> List[str]:
    return [entry["title"] for entry in fetch_douban_top_movie_entries(limit) if entry.get("title")]


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
def fetch_poster_bytes_from_url(img_url: str) -> Optional[bytes]:
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
    return fetch_poster_bytes_from_url(img_url)


def prepare_douban_candidates_ui(limit: int, warm_posters: bool) -> tuple[List[str], Dict[str, Optional[bytes]]]:
    text_holder = st.empty()
    progress_holder = st.empty()
    text_holder.caption("准备中...")
    bar = progress_holder.progress(0)

    entries = fetch_douban_top_movie_entries(limit)
    movies = [entry["title"] for entry in entries if entry.get("title")]
    if not movies:
        bar.progress(100)
        return [], {}

    poster_map: Dict[str, Optional[bytes]] = {}
    if warm_posters:
        total_steps = max(1, len(movies))
        for idx, entry in enumerate(entries[: len(movies)], 1):
            title = entry.get("title")
            if not title:
                continue
            poster_bytes = fetch_poster_bytes_from_url(entry.get("poster_url") or "")
            if poster_bytes is None:
                poster_bytes = fetch_douban_poster_bytes(title)
            poster_map[title] = poster_bytes
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
    user_name: str = "",
    seed_text: str = "",
    blind_mode: bool = False,
    side_shuffle: bool = True,
    initial_poster_map: Optional[Dict[str, Optional[bytes]]] = None,
) -> None:
    opts = options[:]
    if len(opts) < 2:
        raise ValueError("候选项至少需要 2 个才能开始排序。")

    clean_seed = seed_text.strip()
    if clean_seed:
        rng = random.Random(stable_int(f"{clean_seed}|{theme}|{'||'.join(options)}"))
        rng.shuffle(opts)
    else:
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
    st.session_state[k("poster_fetch_failed")] = []
    st.session_state[k("history")] = []
    st.session_state[k("skipped_items")] = []
    st.session_state[k("user_name")] = user_name.strip()
    st.session_state[k("seed_text")] = clean_seed
    st.session_state[k("blind_mode")] = blind_mode
    st.session_state[k("side_shuffle")] = side_shuffle
    st.session_state[k("defers")] = 0
    st.session_state[k("share_poster_bytes")] = b""
    st.session_state[k("share_poster_signature")] = ""


def clear_ranking_state() -> None:
    for name in RANKING_STATE_KEYS:
        st.session_state.pop(k(name), None)


def reset_same_config() -> None:
    mode = st.session_state.get(k("mode"))
    theme = st.session_state.get(k("theme"), "我的排序")
    options = st.session_state.get(k("source_options"), [])
    top_k = st.session_state.get(k("top_k"))
    show_poster = st.session_state.get(k("show_poster"), False)
    user_name = st.session_state.get(k("user_name"), "")
    seed_text = st.session_state.get(k("seed_text"), "")
    blind_mode = st.session_state.get(k("blind_mode"), False)
    side_shuffle = st.session_state.get(k("side_shuffle"), True)
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
        user_name=user_name,
        seed_text=seed_text,
        blind_mode=blind_mode,
        side_shuffle=side_shuffle,
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


def handle_defer_current_pair() -> None:
    if st.session_state.get(k("finished"), False):
        return

    current_item = st.session_state.get(k("current_item"))
    remaining = st.session_state.get(k("remaining"), [])
    if not current_item:
        return
    if not remaining:
        st.warning("已经是最后一组了，先做一个选择吧。")
        return

    push_history_snapshot()
    remaining.append(current_item)
    st.session_state[k("remaining")] = remaining
    st.session_state[k("current_item")] = None
    st.session_state[k("low")] = 0
    st.session_state[k("high")] = 0
    st.session_state[k("top_k_boundary_check")] = False
    st.session_state[k("defers")] = st.session_state.get(k("defers"), 0) + 1
    rerun()


# =========================
# 工具函数
# =========================
def parse_options_text(text: str) -> List[str]:
    seen = set()
    options: List[str] = []
    pieces: List[str] = []
    for raw in text.splitlines():
        pieces.extend(re.split(r"[,，、;；|]+", raw))

    for raw in pieces:
        item = raw.strip()
        item = re.sub(r"^(?:[-*•]\s*|\d+[\.\)、]\s*)", "", item).strip()
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
    user_name: str = "",
    seed_text: str = "",
    defers: int = 0,
) -> tuple[bytes, bytes, bytes, bytes]:
    generated_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    txt_lines = [
        theme,
        f"署名：{user_name or '匿名'}",
        f"模式：{mode}",
        "类型：完整排序" if top_k is None else f"类型：Top {min(top_k, len(ranked))}",
        f"比较次数：{comparisons}",
        f"稍后再比：{defers}",
        f"对局口令：{seed_text or '未设置'}",
        f"生成时间：{generated_at}",
        "",
        "排名结果：",
    ]
    txt_lines.extend(f"{idx}. {item}" for idx, item in enumerate(ranked, 1))
    if skipped_items:
        txt_lines.extend(["", "已跳过："])
        txt_lines.extend(f"- {item}" for item in skipped_items)
    txt_bytes = "\n".join(txt_lines).encode("utf-8-sig")

    csv_buffer = io.StringIO()
    writer = csv.writer(csv_buffer)
    writer.writerow(["rank", "item", "status", "theme", "user_name", "seed_text"])
    for idx, item in enumerate(ranked, 1):
        writer.writerow([idx, item, "ranked", theme, user_name, seed_text])
    for item in skipped_items:
        writer.writerow(["", item, "skipped", theme, user_name, seed_text])
    csv_bytes = csv_buffer.getvalue().encode("utf-8-sig")

    json_bytes = json.dumps(
        {
            "schema": "film-sort-ranking-v2",
            "app": APP_TITLE,
            "theme": theme,
            "mode": mode,
            "user_name": user_name,
            "seed_text": seed_text,
            "top_k": top_k,
            "comparisons": comparisons,
            "defers": defers,
            "generated_at": generated_at,
            "ranked": [{"rank": idx, "item": item} for idx, item in enumerate(ranked, 1)],
            "skipped_items": skipped_items,
        },
        ensure_ascii=False,
        indent=2,
    ).encode("utf-8")

    md_lines = [
        f"# {theme}",
        "",
        f"- 署名：{user_name or '匿名'}",
        f"- 模式：{mode}",
        f"- 比较次数：{comparisons}",
        f"- 稍后再比：{defers}",
    ]
    if seed_text:
        md_lines.append(f"- 对局口令：`{seed_text}`")
    md_lines.extend(["", "## 排名结果"])
    md_lines.extend(f"{idx}. {item}" for idx, item in enumerate(ranked, 1))
    if skipped_items:
        md_lines.extend(["", "## 已跳过"])
        md_lines.extend(f"- {item}" for item in skipped_items)
    md_bytes = "\n".join(md_lines).encode("utf-8")

    return txt_bytes, csv_bytes, json_bytes, md_bytes


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


def build_share_caption(
    *,
    theme: str,
    ranked: List[str],
    skipped_items: List[str],
    comparisons: int,
    user_name: str,
    seed_text: str,
) -> str:
    top_items = ranked[: min(8, len(ranked))]
    lines = [
        f"我刚用「{APP_TITLE}」排出了「{theme}」。",
    ]
    if user_name:
        lines.append(f"署名：{user_name}")
    if ranked:
        lines.append(f"冠军：{ranked[0]}")
    lines.append("我的榜单：")
    lines.extend(f"{idx}. {item}" for idx, item in enumerate(top_items, 1))
    if len(ranked) > len(top_items):
        lines.append(f"...还有 {len(ranked) - len(top_items)} 个排名")
    lines.append(f"这份榜单经过 {comparisons} 次二选一生成。")
    if skipped_items:
        lines.append(f"跳过了 {len(skipped_items)} 个没看过/不熟悉项。")
    if seed_text:
        lines.append(f"对局口令：{seed_text}。拿同一份候选来挑战我。")
    else:
        lines.append("拿同一份候选来挑战我。")
    return "\n".join(lines)


def result_archetype(comparisons: int, expected: int, skipped_count: int, ranked_count: int) -> str:
    if ranked_count <= 1:
        return "刚开榜"
    ratio = comparisons / max(1, expected)
    if skipped_count >= max(3, ranked_count // 4):
        return "精准筛选派"
    if ratio <= 0.65:
        return "果断派"
    if ratio >= 1.1:
        return "认真纠结派"
    return "稳定输出派"


def render_result_insights(total: int, comparisons: int, top_k: Optional[int]) -> None:
    ranked = st.session_state.get(k("ranked"), [])
    skipped_items = st.session_state.get(k("skipped_items"), [])
    expected = estimated_comparisons(total, top_k)
    champion = ranked[0] if ranked else "暂无"
    podium = " / ".join(ranked[:3]) if ranked else "暂无"
    archetype = result_archetype(comparisons, expected, len(skipped_items), len(ranked))
    efficiency = f"{max(0, expected - comparisons)} 次" if expected >= comparisons else "完整复盘"

    st.markdown(
        f"""
        <div class="insight-grid">
          <div class="insight-card"><div class="insight-label">冠军</div><div class="insight-value">{html.escape(champion)}</div></div>
          <div class="insight-card"><div class="insight-label">前三名</div><div class="insight-value">{html.escape(podium)}</div></div>
          <div class="insight-card"><div class="insight-label">人格标签</div><div class="insight-value">{html.escape(archetype)}</div></div>
          <div class="insight-card"><div class="insight-label">相对预估少做</div><div class="insight-value">{html.escape(efficiency)}</div></div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def extract_ranked_items_from_payload(payload: dict) -> List[str]:
    ranked = payload.get("ranked", [])
    items: List[str] = []
    if not isinstance(ranked, list):
        return items
    for entry in ranked:
        if isinstance(entry, dict):
            item = entry.get("item")
        else:
            item = entry
        if isinstance(item, str) and item.strip():
            items.append(item.strip())
    return items


def compare_rankings(my_ranked: List[str], friend_ranked: List[str]) -> dict:
    my_pos = {item: idx for idx, item in enumerate(my_ranked, 1)}
    friend_pos = {item: idx for idx, item in enumerate(friend_ranked, 1)}
    shared = [item for item in my_ranked if item in friend_pos]
    if not shared:
        return {"shared": [], "top_overlap": 0, "avg_gap": None, "biggest_gap": None}

    top_overlap = len(set(my_ranked[:5]) & set(friend_ranked[:5]))
    gaps = [(item, abs(my_pos[item] - friend_pos[item]), my_pos[item], friend_pos[item]) for item in shared]
    biggest_gap = max(gaps, key=lambda row: row[1])
    avg_gap = sum(row[1] for row in gaps) / len(gaps)
    return {
        "shared": shared,
        "top_overlap": top_overlap,
        "avg_gap": avg_gap,
        "biggest_gap": biggest_gap,
    }


def render_friend_compare(my_ranked: List[str]) -> None:
    with st.expander("好友榜单对比", expanded=False):
        st.caption("让朋友下载 JSON 榜单后发给你，导入这里就能看到你们到底差在哪。")
        uploaded = st.file_uploader("导入朋友的 JSON 榜单", type=["json"], key="friend_ranking_json")
        if not uploaded:
            return
        try:
            payload = json.load(uploaded)
            friend_ranked = extract_ranked_items_from_payload(payload)
        except Exception as e:
            st.error(f"读取失败：{e}")
            return
        if not friend_ranked:
            st.warning("这个 JSON 里没有可识别的排名结果。")
            return
        comparison = compare_rankings(my_ranked, friend_ranked)
        shared = comparison["shared"]
        if not shared:
            st.info("你们的榜单没有重合候选项。")
            return
        friend_name = payload.get("user_name") or "朋友"
        st.markdown(
            f"""
            <div class="share-callout">
              你和 {html.escape(str(friend_name))} 共有 {len(shared)} 个重合项；Top 5 重合 {comparison["top_overlap"]} 个；平均排名差 {comparison["avg_gap"]:.1f} 位。
            </div>
            """,
            unsafe_allow_html=True,
        )
        biggest = comparison["biggest_gap"]
        if biggest:
            item, gap, mine, friend = biggest
            st.caption(f"分歧最大：{item}，你排第 {mine}，对方排第 {friend}，相差 {gap} 位。")


def render_cover_header() -> None:
    text_col, image_col = st.columns([1, 1.05])
    with text_col:
        st.markdown('<span class="cover-tag">电影 / 歌手 / 游戏 / 任意偏好</span>', unsafe_allow_html=True)
        st.markdown(f'<div class="cover-title">{APP_TITLE}</div>', unsafe_allow_html=True)
        st.markdown(f'<div class="cover-subtitle">{APP_SUBTITLE}</div>', unsafe_allow_html=True)
        st.caption("选 A 还是选 B，剩下的交给排序器。")
    with image_col:
        cover_src = image_file_data_uri(COVER_IMAGE_PATH)
        if cover_src:
            st.markdown(f'<img class="cover-image" src="{cover_src}" alt="{APP_TITLE} 封面">', unsafe_allow_html=True)
    safe_divider()


def get_poster_for_option(name: str) -> Optional[bytes]:
    poster_map = st.session_state.setdefault(k("poster_map"), {})
    if poster_map.get(name):
        return poster_map[name]

    failed = st.session_state.setdefault(k("poster_fetch_failed"), [])
    if name in failed:
        return None

    poster_bytes = fetch_douban_poster_bytes(name)
    poster_map[name] = poster_bytes
    st.session_state[k("poster_map")] = poster_map
    if poster_bytes is None and name not in failed:
        failed.append(name)
        st.session_state[k("poster_fetch_failed")] = failed
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


def build_share_poster_signature(
    theme: str,
    ranked: List[str],
    skipped_items: List[str],
    top_k: Optional[int],
    mode: str,
    user_name: str,
    poster_style: str,
    poster_format: str,
) -> str:
    return "|".join(
        [
            theme,
            mode,
            user_name,
            poster_style,
            poster_format,
            "full" if top_k is None else f"top{top_k}",
            "ranked:" + "||".join(ranked),
            "skipped:" + "||".join(skipped_items),
        ]
    )


def get_share_palette(poster_style: str) -> dict:
    palettes = {
        "热映红毯": {
            "bg": (54, 20, 23),
            "card": (255, 248, 238),
            "outline": (242, 199, 122),
            "title": (70, 28, 28),
            "text": (30, 28, 26),
            "muted": (113, 89, 75),
            "accent": (192, 49, 49),
        },
        "午夜霓虹": {
            "bg": (14, 18, 32),
            "card": (25, 31, 48),
            "outline": (81, 102, 151),
            "title": (236, 242, 255),
            "text": (236, 242, 255),
            "muted": (171, 185, 214),
            "accent": (111, 231, 214),
        },
        "清爽白卡": {
            "bg": (246, 247, 251),
            "card": (255, 255, 255),
            "outline": (228, 231, 236),
            "title": (20, 24, 35),
            "text": (20, 24, 35),
            "muted": (98, 106, 120),
            "accent": (73, 93, 241),
        },
    }
    return palettes.get(poster_style, palettes["清爽白卡"])


def generate_share_poster_bytes(
    theme: str,
    ranked: List[str],
    skipped_items: List[str],
    top_k: Optional[int],
    mode: str,
    user_name: str,
    poster_style: str,
    poster_format: str,
) -> bytes:
    width = 1080
    fixed_height = None
    if poster_format == "方图 1:1":
        fixed_height = 1080
    elif poster_format == "长图 9:16":
        fixed_height = 1920

    padding = 64
    line_height = 56
    palette = get_share_palette(poster_style)

    measure_img = Image.new("RGB", (1, 1))
    measure_draw = ImageDraw.Draw(measure_img)

    title_font = load_font(52, bold=True)
    subtitle_font = load_font(26)
    item_font = load_font(34)
    small_font = load_font(22)

    max_text_width = width - padding * 2 - 120
    if fixed_height is None:
        display_ranked = ranked
    else:
        display_ranked = ranked[: 12 if fixed_height == 1080 else 22]

    ranked_layout = []
    for item in display_ranked:
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
    if user_name:
        content_height += 34
    content_height += sum(row_height for _, _, row_height in ranked_layout)
    if len(display_ranked) < len(ranked):
        content_height += 38
    if skipped_items:
        content_height += 12 + 2 + 24 + 36 + len(skipped_lines) * 28
    height = fixed_height or max(760, content_height + 140)

    img = Image.new("RGB", (width, height), palette["bg"])
    draw = ImageDraw.Draw(img)

    draw.rounded_rectangle((36, 36, width - 36, height - 36), radius=36, fill=palette["card"], outline=palette["outline"], width=2)

    y = padding
    draw.text((padding, y), theme, font=title_font, fill=palette["title"])
    y += 78

    if top_k is None:
        subtitle = "完整偏爱排序"
    elif mode == MODE_DOUBAN:
        subtitle = f"豆瓣电影 Top {min(top_k, len(ranked))}"
    else:
        subtitle = f"自定义 Top {min(top_k, len(ranked))}"
    draw.text((padding, y), subtitle, font=subtitle_font, fill=palette["muted"])
    y += 54
    if user_name:
        draw.text((padding, y), f"by {user_name}", font=small_font, fill=palette["muted"])
        y += 34

    draw.line((padding, y, width - padding, y), fill=palette["outline"], width=2)
    y += 28

    for idx, (_, wrapped, row_height) in enumerate(ranked_layout, 1):
        rank_text = f"{idx:02d}"
        draw.text((padding, y), rank_text, font=item_font, fill=palette["accent"])
        for j, line in enumerate(wrapped):
            draw.text((padding + 90, y + j * 40), line, font=item_font, fill=palette["text"])
        y += row_height

    if len(display_ranked) < len(ranked):
        draw.text((padding + 90, y), f"还有 {len(ranked) - len(display_ranked)} 项完整结果", font=small_font, fill=palette["muted"])
        y += 38

    if skipped_items:
        y += 12
        draw.line((padding, y, width - padding, y), fill=palette["outline"], width=2)
        y += 24
        skipped_text = f"已跳过未看过/不熟悉项：{len(skipped_items)} 个"
        draw.text((padding, y), skipped_text, font=small_font, fill=palette["muted"])
        y += 36

        for line in skipped_lines:
            draw.text((padding, y), line, font=small_font, fill=palette["muted"])
            y += 28

    footer = f"{APP_TITLE} · {datetime.now().strftime('%Y-%m-%d %H:%M')}"
    draw.text((padding, height - 70), footer, font=small_font, fill=palette["muted"])

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
    user_name = st.session_state.get(k("user_name"), "")
    poster_style = st.session_state.get(k("share_poster_style"), SHARE_POSTER_STYLES[0])
    poster_format = st.session_state.get(k("share_poster_format"), SHARE_POSTER_FORMATS[0])
    signature = build_share_poster_signature(theme, ranked, skipped_items, top_k, mode, user_name, poster_style, poster_format)

    if st.session_state.get(k("share_poster_signature")) == signature and st.session_state.get(k("share_poster_bytes")):
        return

    poster_bytes = generate_share_poster_bytes(theme, ranked, skipped_items, top_k, mode, user_name, poster_style, poster_format)
    st.session_state[k("share_poster_bytes")] = poster_bytes
    st.session_state[k("share_poster_signature")] = signature


def get_current_opponent_index(ranked: List[str], low: int, high: int) -> int:
    if st.session_state.get(k("top_k_boundary_check"), False):
        return max(0, len(ranked) - 1)
    return max(0, min(len(ranked) - 1, (low + high) // 2))


def render_battle_picker(
    *,
    left_title: str,
    right_title: str,
    left_label: str,
    right_label: str,
    show_poster: bool,
    key: str,
) -> Optional[str]:
    left_poster = poster_data_uri(get_poster_for_option(left_title)) if show_poster else None
    right_poster = poster_data_uri(get_poster_for_option(right_title)) if show_poster else None
    result = BATTLE_PICKER_COMPONENT(
        left={"label": left_label, "title": left_title, "poster": left_poster, "hotkey": "A / ←"},
        right={"label": right_label, "title": right_title, "poster": right_poster, "hotkey": "D / →"},
        key=key,
        default=None,
    )
    if isinstance(result, dict):
        choice = result.get("choice")
        if choice in ("left", "right"):
            return choice
    return None


# =========================
# 排序页面渲染
# =========================
def render_result_section(total: int, comparisons: int, top_k: Optional[int]) -> None:
    ranked = st.session_state.get(k("ranked"), [])
    skipped_items = st.session_state.get(k("skipped_items"), [])
    user_name = st.session_state.get(k("user_name"), "")
    seed_text = st.session_state.get(k("seed_text"), "")
    defers = st.session_state.get(k("defers"), 0)

    if top_k is None:
        st.success("🎉 排序完成！下面是你的完整排名：")
    else:
        st.success(f"🎉 排序完成！下面是你的 Top {len(ranked)}：")

    render_result_insights(total=total, comparisons=comparisons, top_k=top_k)
    render_ranked_list(ranked)

    summary = f"共处理 {total} 个候选项，完成比较 {comparisons} 次。"
    if skipped_items:
        summary += f" 已跳过 {len(skipped_items)} 项。"
    if defers:
        summary += f" 稍后再比 {defers} 次。"
    st.caption(summary)

    st.subheader("分享资产")
    if st.session_state.get(k("share_poster_style")) not in SHARE_POSTER_STYLES:
        st.session_state[k("share_poster_style")] = SHARE_POSTER_STYLES[0]
    if st.session_state.get(k("share_poster_format")) not in SHARE_POSTER_FORMATS:
        st.session_state[k("share_poster_format")] = SHARE_POSTER_FORMATS[0]
    share_col1, share_col2 = st.columns(2)
    with share_col1:
        st.selectbox(
            "海报风格",
            SHARE_POSTER_STYLES,
            key=k("share_poster_style"),
        )
    with share_col2:
        st.selectbox(
            "海报尺寸",
            SHARE_POSTER_FORMATS,
            key=k("share_poster_format"),
        )
    ensure_share_poster_generated()

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
    share_caption = build_share_caption(
        theme=theme,
        ranked=ranked,
        skipped_items=skipped_items,
        comparisons=comparisons,
        user_name=user_name,
        seed_text=seed_text,
    )
    with st.expander("可直接发布的分享文案", expanded=True):
        st.text_area("文案", value=share_caption, height=220)
        st.caption("发朋友圈、群聊或评论区时直接使用；JSON 可以发给朋友做榜单对比。")

    txt_bytes, csv_bytes, json_bytes, md_bytes = build_export_payloads(
        theme=theme,
        mode=mode,
        ranked=ranked,
        skipped_items=skipped_items,
        top_k=top_k,
        comparisons=comparisons,
        user_name=user_name,
        seed_text=seed_text,
        defers=defers,
    )
    base_name = slugify_filename(theme)
    with st.expander("导出结果", expanded=False):
        d1, d2, d3, d4 = st.columns(4)
        with d1:
            render_download_button_compat("下载 TXT", txt_bytes, f"{base_name}.txt", "text/plain", "btn_export_txt")
        with d2:
            render_download_button_compat("下载 CSV", csv_bytes, f"{base_name}.csv", "text/csv", "btn_export_csv")
        with d3:
            render_download_button_compat("下载挑战 JSON", json_bytes, f"{base_name}.json", "application/json", "btn_export_json")
        with d4:
            render_download_button_compat("下载 Markdown", md_bytes, f"{base_name}.md", "text/markdown", "btn_export_md")

    render_friend_compare(ranked)

    col1, col2, col3 = st.columns(3)
    with col1:
        if render_button_compat("↩️ 撤销上一步", key="btn_undo_result", use_container_width=True):
            undo_last_step()
    with col2:
        if render_button_compat("重新排序", key="btn_reset_same", use_container_width=True):
            reset_same_config()
    with col3:
        if render_button_compat("清空结果", key="btn_clear_result", use_container_width=True):
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
    user_name = st.session_state.get(k("user_name"), "")
    blind_mode = st.session_state.get(k("blind_mode"), False)
    side_shuffle = st.session_state.get(k("side_shuffle"), True)
    defers = st.session_state.get(k("defers"), 0)

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
    if top_k is None:
        mode_label = "自定义完整排序"
    elif mode == MODE_DOUBAN:
        mode_label = f"豆瓣 Top {top_k}"
    else:
        mode_label = f"自定义 Top {top_k}"
    player_label = user_name or "匿名玩家"

    st.markdown(
        f"""
        <div class="compact-status">
          <div class="status-chip"><div class="status-label">主题</div><div class="status-value">{html.escape(theme)}</div></div>
          <div class="status-chip"><div class="status-label">玩家</div><div class="status-value">{html.escape(player_label)}</div></div>
          <div class="status-chip"><div class="status-label">进度</div><div class="status-value">{processed}/{total}</div></div>
          <div class="status-chip"><div class="status-label">已比较</div><div class="status-value">{comparisons}</div></div>
          <div class="status-chip"><div class="status-label">预计剩余</div><div class="status-value">约 {remaining_estimate}</div></div>
          <div class="status-chip"><div class="status-label">跳过 / 稍后</div><div class="status-value">{len(skipped_items)} / {defers}</div></div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.caption(f"{mode_label}。快捷键：A/← 选择左侧，D/→ 选择右侧。{'盲排已开启，对局中隐藏当前榜单。' if blind_mode else ''}")

    if top_k is None:
        st.markdown("### 你更喜欢哪一个？")
    else:
        if st.session_state.get(k("top_k_boundary_check"), False):
            st.caption("这个候选会先挑战当前榜单末位；如果没有更喜欢它，会直接跳过，减少不必要比较。")
        st.markdown("### 你更喜欢哪一部？")

    if side_shuffle:
        current_on_left = stable_int(f"{current}|{opponent}|{comparisons}|{st.session_state.get(k('seed_text'), '')}") % 2 == 0
    else:
        current_on_left = True

    left_title = current if current_on_left else opponent
    right_title = opponent if current_on_left else current
    left_label = "新挑战者" if current_on_left else "榜单守擂"
    right_label = "榜单守擂" if current_on_left else "新挑战者"

    ctrl1, ctrl2, ctrl3, ctrl4 = st.columns(4)
    with ctrl1:
        label_left = "没看过 A" if mode == MODE_DOUBAN else "不熟悉 A"
        if render_button_compat(label_left, key="btn_skip_left", use_container_width=True):
            if current_on_left:
                handle_skip_current_item()
            else:
                handle_skip_opponent_item()
    with ctrl2:
        label_right = "没看过 B" if mode == MODE_DOUBAN else "不熟悉 B"
        if render_button_compat(label_right, key="btn_skip_right", use_container_width=True):
            if current_on_left:
                handle_skip_opponent_item()
            else:
                handle_skip_current_item()
    with ctrl3:
        if render_button_compat("稍后再比", key="btn_defer_pair", use_container_width=True):
            handle_defer_current_pair()
    with ctrl4:
        if render_button_compat("撤销上一步", key="btn_undo_live", use_container_width=True):
            undo_last_step()

    component_key = f"battle_{processed}_{comparisons}_{stable_int(current + opponent)}"
    choice = render_battle_picker(
        left_title=left_title,
        right_title=right_title,
        left_label=left_label,
        right_label=right_label,
        show_poster=show_poster and mode == MODE_DOUBAN,
        key=component_key,
    )
    if choice:
        prefer_current = (choice == "left" and current_on_left) or (choice == "right" and not current_on_left)
        handle_choice(prefer_left=prefer_current)
        return

    ranked = st.session_state.get(k("ranked"), [])
    expander_title = "📊 当前榜单" if top_k is None else f"📊 当前 Top {len(ranked)}"
    if blind_mode:
        st.caption("盲排模式：当前榜单会在结束后揭晓。")
    else:
        with st.expander(expander_title, expanded=False):
            for i, item in enumerate(ranked, 1):
                st.write(f"{i}. {item}")

    if skipped_items:
        with st.expander("⏭️ 已跳过的候选项", expanded=False):
            for i, item in enumerate(skipped_items, 1):
                st.write(f"{i}. {item}")


# =========================
# 三步式流程页面
# =========================
def get_ui_step() -> int:
    step = int(st.session_state.get("ui_step", 1))
    return step if step in (1, 2, 3, 4) else 1


def go_to_step(step: int) -> None:
    st.session_state["ui_step"] = max(1, min(4, int(step)))
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
        ("③ 开始对决", 3),
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
        st.info("自定义模式：自己填主题和候选项，歌手、游戏、电影、角色都能排。")
    else:
        st.info("豆瓣电影模式：设置 Top 数量和候选范围，系统会读取豆瓣 Top250。")

    spacer, next_col = st.columns([1, 1])
    with spacer:
        st.empty()
    with next_col:
        if render_button_compat("下一步：填写参数 →", key="btn_to_step2", use_container_width=True, button_type="primary"):
            go_to_step(2)


def render_custom_template_gallery() -> None:
    with st.expander("快速开局模板", expanded=not bool(st.session_state.get("ui_custom_options_text", ""))):
        st.caption("先用模板跑通一局，再替换成自己的候选，能显著降低第一次使用的门槛。")
        cols = st.columns(4)
        for idx, template in enumerate(CUSTOM_TEMPLATES):
            with cols[idx % 4]:
                if render_button_compat(template["name"], key=f"btn_custom_template_{idx}", use_container_width=True):
                    st.session_state["ui_custom_theme"] = template["theme"]
                    st.session_state["ui_custom_options_text"] = "\n".join(template["items"])
                    rerun()


def render_douban_preset_buttons() -> None:
    with st.expander("对局强度预设", expanded=True):
        st.caption("快排适合分享，标准适合认真排，深挖适合电影爱好者。")
        cols = st.columns(len(DOUBAN_PRESETS))
        for idx, (label, top_k, pool_n) in enumerate(DOUBAN_PRESETS):
            with cols[idx]:
                if render_button_compat(f"{label} · Top {top_k}/{pool_n}", key=f"btn_douban_preset_{idx}", use_container_width=True):
                    st.session_state["ui_douban_top_k"] = top_k
                    st.session_state["ui_douban_pool_n"] = pool_n
                    rerun()


def render_personalization_controls(prefix: str) -> dict:
    defaults = {
        f"{prefix}_user_name": "",
        f"{prefix}_seed_text": "",
        f"{prefix}_blind_mode": False,
        f"{prefix}_side_shuffle": True,
    }
    for key_name, default_value in defaults.items():
        if key_name not in st.session_state:
            st.session_state[key_name] = default_value

    with st.expander("传播设置", expanded=True):
        c1, c2 = st.columns(2)
        with c1:
            user_name = st.text_input(
                "署名",
                key=f"{prefix}_user_name",
                placeholder="例：Atirian",
                help="会出现在导出文件、分享文案和海报里。",
            )
        with c2:
            seed_text = st.text_input(
                "对局口令",
                key=f"{prefix}_seed_text",
                placeholder="例：weekend-001",
                help="同样候选 + 同样口令会得到同样出场顺序，方便朋友接力挑战。",
            )
        c3, c4 = st.columns(2)
        with c3:
            blind_mode = st.checkbox(
                "盲排模式：对局中隐藏当前榜单",
                key=f"{prefix}_blind_mode",
            )
        with c4:
            side_shuffle = st.checkbox(
                "左右随机：降低固定位置偏差",
                key=f"{prefix}_side_shuffle",
            )
    return {
        "user_name": user_name,
        "seed_text": seed_text,
        "blind_mode": blind_mode,
        "side_shuffle": side_shuffle,
    }


def reset_custom_parameter_defaults() -> None:
    st.session_state["ui_custom_theme"] = "我的榜单"
    st.session_state["ui_custom_options_text"] = ""
    st.session_state["ui_custom_top_k_enabled"] = False
    st.session_state["ui_custom_top_k"] = 10
    st.session_state["ui_custom_user_name"] = ""
    st.session_state["ui_custom_seed_text"] = ""
    st.session_state["ui_custom_blind_mode"] = False
    st.session_state["ui_custom_side_shuffle"] = True


def reset_douban_parameter_defaults() -> None:
    st.session_state["ui_douban_theme"] = "我的豆瓣电影榜"
    st.session_state["ui_douban_top_k"] = 10
    st.session_state["ui_douban_pool_n"] = 100
    st.session_state["ui_douban_show_poster"] = True
    st.session_state["ui_douban_user_name"] = ""
    st.session_state["ui_douban_seed_text"] = ""
    st.session_state["ui_douban_blind_mode"] = False
    st.session_state["ui_douban_side_shuffle"] = True
    st.session_state.pop("ui_douban_preview_movies", None)
    st.session_state.pop("ui_douban_preview_pool_n", None)


def render_custom_parameter_page(mode: str) -> None:
    if st.session_state.pop("ui_reset_custom_requested", False):
        reset_custom_parameter_defaults()

    render_custom_template_gallery()

    st.text_input("榜单名称", value=st.session_state.get("ui_custom_theme", "我的榜单"), key="ui_custom_theme")
    st.text_area(
        "候选项（每行一个）",
        value=st.session_state.get("ui_custom_options_text", ""),
        height=320,
        key="ui_custom_options_text",
        placeholder="例：\n周杰伦\n陈奕迅\n王菲\n张学友",
    )

    options = parse_options_text(st.session_state.get("ui_custom_options_text", ""))
    st.caption(f"当前有效候选项：{len(options)} 个（已自动去重、去空行）。")
    st.caption("支持每行一个，也支持用逗号、顿号、分号或竖线一次性粘贴。")

    top_k_enabled = st.checkbox(
        "只排前 N 名，缩短分享局",
        value=bool(st.session_state.get("ui_custom_top_k_enabled", False)),
        key="ui_custom_top_k_enabled",
    )
    custom_top_k: Optional[int] = None
    if top_k_enabled:
        max_top_k = max(1, len(options))
        if int(st.session_state.get("ui_custom_top_k", min(10, max_top_k))) > max_top_k:
            st.session_state["ui_custom_top_k"] = max_top_k
        custom_top_k = int(
            st.number_input(
                "最终保留 Top N",
                min_value=1,
                max_value=max_top_k,
                value=int(st.session_state.get("ui_custom_top_k", min(10, max_top_k))),
                step=1,
                key="ui_custom_top_k",
            )
        )
    estimate_top_k = custom_top_k if custom_top_k and len(options) >= 2 else None
    st.caption(f"预计比较次数大约：{estimated_comparisons(len(options), estimate_top_k)} 次。")

    personalization = render_personalization_controls("ui_custom")

    with st.expander("查看当前候选项", expanded=False):
        render_searchable_item_preview(options, "ui_custom_preview_search")

    nav1, nav2, nav3 = st.columns(3)
    with nav1:
        if render_button_compat("← 返回上一步", key="btn_custom_back_step1", use_container_width=True):
            go_to_step(1)
    with nav2:
        if render_button_compat("🧹 清空参数", key="btn_clear_custom_step2", use_container_width=True):
            clear_ranking_state()
            st.session_state["ui_reset_custom_requested"] = True
            rerun()
    with nav3:
        if render_button_compat("开始对决 →", key="btn_start_custom_step2", use_container_width=True, button_type="primary"):
            if len(options) < 2:
                st.warning("请至少输入 2 个候选项。")
            else:
                init_ranking_state(
                    mode=mode,
                    theme=(st.session_state.get("ui_custom_theme", "") or "").strip() or "我的榜单",
                    options=options,
                    top_k=estimate_top_k,
                    show_poster=False,
                    user_name=personalization["user_name"],
                    seed_text=personalization["seed_text"],
                    blind_mode=personalization["blind_mode"],
                    side_shuffle=personalization["side_shuffle"],
                    initial_poster_map=None,
                )
                st.session_state["ui_step"] = 3
                rerun()


def render_douban_parameter_page(mode: str) -> None:
    if st.session_state.pop("ui_reset_douban_requested", False):
        reset_douban_parameter_defaults()

    render_douban_preset_buttons()

    st.text_input("榜单名称", value=st.session_state.get("ui_douban_theme", "我的豆瓣电影榜"), key="ui_douban_theme")

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
            "从豆瓣 Top 多少部里选",
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
    personalization = render_personalization_controls("ui_douban")

    if pool_n < top_k:
        st.error("候选范围不能小于 Top 数量。请让候选范围 >= Top。")
    else:
        st.caption(f"将从豆瓣 Top250 中读取前 {pool_n} 部电影，最后给出你的 Top {top_k}。")
        st.caption(f"预计比较次数大约：{estimated_comparisons(pool_n, top_k)} 次。")

    if render_button_compat("👀 预览候选电影", key="btn_preview_douban_step2", use_container_width=True):
        if pool_n < top_k:
            st.warning("请先修正设置：候选范围不能小于 Top 数量。")
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
            st.session_state["ui_reset_douban_requested"] = True
            rerun()
    with nav3:
        if render_button_compat("准备并开始 →", key="btn_start_douban_step2", use_container_width=True, button_type="primary"):
            if pool_n < top_k:
                st.warning("请先修正设置：候选范围不能小于 Top 数量。")
            else:
                st.session_state["ui_pending_douban"] = {
                    "mode": mode,
                    "theme": (st.session_state.get("ui_douban_theme", "") or "").strip() or "我的豆瓣电影榜",
                    "top_k": top_k,
                    "pool_n": pool_n,
                    "show_poster": show_poster,
                    "user_name": personalization["user_name"],
                    "seed_text": personalization["seed_text"],
                    "blind_mode": personalization["blind_mode"],
                    "side_shuffle": personalization["side_shuffle"],
                }
                st.session_state["ui_step"] = 4
                rerun()


def render_parameter_page() -> None:
    mode = get_selected_mode()
    render_step_header(
        2,
        "填写本次排序参数",
        "补充榜单名称、候选范围和展示设置。",
    )

    if mode == MODE_CUSTOM:
        render_custom_parameter_page(mode)
    else:
        render_douban_parameter_page(mode)


def render_douban_prepare_page() -> None:
    pending = st.session_state.get("ui_pending_douban")
    st.progress(0.72)
    st.subheader("正在准备对局")
    st.caption("正在读取豆瓣榜单和海报。准备完成后会自动进入排序页。")

    if not pending:
        st.warning("没有待准备的豆瓣排序任务。")
        if render_button_compat("返回设置", key="btn_prepare_back", use_container_width=True):
            go_to_step(2)
        return

    try:
        movies, poster_map = prepare_douban_candidates_ui(
            int(pending["pool_n"]),
            warm_posters=bool(pending["show_poster"]),
        )
        if len(movies) < 2:
            st.error("获取到的电影数量不足 2，无法开始排序。")
            if render_button_compat("返回设置", key="btn_prepare_failed_back", use_container_width=True):
                st.session_state.pop("ui_pending_douban", None)
                go_to_step(2)
            return

        init_ranking_state(
            mode=pending["mode"],
            theme=pending["theme"],
            options=movies,
            top_k=int(pending["top_k"]),
            show_poster=bool(pending["show_poster"]),
            user_name=str(pending.get("user_name", "")),
            seed_text=str(pending.get("seed_text", "")),
            blind_mode=bool(pending.get("blind_mode", False)),
            side_shuffle=bool(pending.get("side_shuffle", True)),
            initial_poster_map=poster_map,
        )
        st.session_state.pop("ui_pending_douban", None)
        st.session_state["ui_step"] = 3
        rerun()
    except Exception as e:
        st.error(f"准备豆瓣电影失败：{e}")
        if render_button_compat("返回设置", key="btn_prepare_error_back", use_container_width=True):
            st.session_state.pop("ui_pending_douban", None)
            go_to_step(2)


def render_sorting_page() -> None:
    started = st.session_state.get(k("started"), False)

    st.progress(1.0)
    labels = st.columns(3)
    with labels[0]:
        st.caption("① 选择模式")
    with labels[1]:
        st.caption("② 填写参数")
    with labels[2]:
        st.markdown("**③ 开始对决**")

    if not started:
        st.info("还没有开始。请先回到第 2 步完成设置。")
    else:
        render_right_panel()

    safe_divider()
    nav1, nav2 = st.columns(2)
    with nav1:
        if render_button_compat("← 返回第 2 步修改参数", key="btn_back_to_step2", use_container_width=True):
            go_to_step(2)
    with nav2:
        if render_button_compat("重新选择模式", key="btn_back_to_step1", use_container_width=True):
            go_to_step(1)


# =========================
# 主程序
# =========================
def main() -> None:
    st.set_page_config(
        page_title=APP_TITLE,
        page_icon="🎯",
        layout="wide",
    )
    render_app_styles()

    if "ui_selected_mode" not in st.session_state:
        st.session_state["ui_selected_mode"] = MODE_CUSTOM
    if "ui_step" not in st.session_state:
        st.session_state["ui_step"] = 1

    step = get_ui_step()
    if step == 3:
        st.caption(f"🎯 {APP_TITLE}")
    elif step == 1:
        render_cover_header()
    else:
        st.title(f"🎯 {APP_TITLE}")
        st.markdown(APP_SUBTITLE)

    if step == 1:
        render_mode_selection_page()
    elif step == 2:
        render_parameter_page()
    elif step == 4:
        render_douban_prepare_page()
    else:
        render_sorting_page()

    safe_divider()
    st.caption("说明：豆瓣模式准备阶段会显示“准备中...”。如果网络异常或海报抓取失败，单张海报可能不显示，但排序功能仍可继续。")


if __name__ == "__main__":
    main()
