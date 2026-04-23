from __future__ import annotations

import io
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


def render_button_compat(label: str, key: str, use_container_width: bool = True) -> bool:
    try:
        return st.button(label, key=key, use_container_width=use_container_width)
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
            st.session_state[k("high")] = len(st.session_state[k("ranked")])
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

    low = st.session_state[k("low")]
    high = st.session_state[k("high")]
    mid = (low + high) // 2

    st.session_state[k("comparisons")] += 1

    if prefer_left:
        st.session_state[k("high")] = mid
    else:
        st.session_state[k("low")] = mid + 1

    if st.session_state[k("low")] >= st.session_state[k("high")]:
        insert_pos = st.session_state[k("low")]
        ranked = st.session_state[k("ranked")]
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
    if high <= 0:
        return

    mid = (low + high) // 2
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
        st.session_state[k("processed")] = st.session_state.get(k("processed"), 0) + 1
    else:
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
    extra = max(0, total - top_k) * max(1, math.ceil(math.log2(top_k)))
    return int(base + extra)


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
    extra_rows = max(8, len(ranked))
    height = 300 + extra_rows * line_height + max(0, len(skipped_items)) * 24 + 180

    img = Image.new("RGB", (width, height), (246, 247, 251))
    draw = ImageDraw.Draw(img)

    title_font = load_font(52, bold=True)
    subtitle_font = load_font(26)
    item_font = load_font(34)
    small_font = load_font(22)

    draw.rounded_rectangle((36, 36, width - 36, height - 36), radius=36, fill=(255, 255, 255), outline=(228, 231, 236), width=2)

    y = padding
    draw.text((padding, y), theme, font=title_font, fill=(20, 24, 35))
    y += 78

    subtitle = "自定义完整排序" if top_k is None else f"豆瓣电影 Top {min(top_k, len(ranked))}"
    draw.text((padding, y), subtitle, font=subtitle_font, fill=(98, 106, 120))
    y += 54

    draw.line((padding, y, width - padding, y), fill=(230, 233, 238), width=2)
    y += 28

    max_text_width = width - padding * 2 - 120
    for idx, item in enumerate(ranked, 1):
        rank_text = f"{idx:02d}"
        draw.text((padding, y), rank_text, font=item_font, fill=(73, 93, 241))
        wrapped = wrap_text(draw, item, item_font, max_text_width)
        for j, line in enumerate(wrapped):
            draw.text((padding + 90, y + j * 40), line, font=item_font, fill=(20, 24, 35))
        y += max(line_height, len(wrapped) * 40 + 12)

    if skipped_items:
        y += 12
        draw.line((padding, y, width - padding, y), fill=(230, 233, 238), width=2)
        y += 24
        skipped_text = f"已剔除未看过/不熟悉项：{len(skipped_items)} 个"
        draw.text((padding, y), skipped_text, font=small_font, fill=(98, 106, 120))
        y += 36

        joined = "、".join(skipped_items[:12])
        if len(skipped_items) > 12:
            joined += "……"
        for line in wrap_text(draw, joined, small_font, width - padding * 2):
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


def render_option_card(title: str, button_text: str, button_key: str, prefer_left: bool, show_poster: bool) -> None:
    if show_poster:
        poster = get_poster_for_option(title)
        if poster:
            shown = show_image_compat(poster)
            if not shown:
                st.caption("海报加载失败")
        else:
            st.caption("该电影海报暂时获取失败")

    st.markdown(f"### 🎯 {title}")
    if render_button_compat(button_text, key=button_key, use_container_width=True):
        handle_choice(prefer_left=prefer_left)


# =========================
# 页面渲染
# =========================
def render_left_panel() -> None:
    st.markdown("**先选择模式，再配置参数，然后开始排序。**")

    mode = st.radio(
        "选择模式",
        [MODE_CUSTOM, MODE_DOUBAN],
        index=0,
        help="自定义模式适合任意主题；豆瓣电影模式会自动读取豆瓣 Top250 里的电影标题。",
    )

    safe_divider()

    if mode == MODE_CUSTOM:
        render_custom_mode_controls(mode)
    else:
        render_douban_mode_controls(mode)


def render_custom_mode_controls(mode: str) -> None:
    default_theme = st.session_state.get("ui_custom_theme", "我的偏好排序")
    theme = st.text_input("主题名称", value=default_theme, key="ui_custom_theme")

    default_text = st.session_state.get("ui_custom_options_text", "")
    options_text = st.text_area(
        "候选项（每行一个）",
        value=default_text,
        height=280,
        key="ui_custom_options_text",
        placeholder="例：\n周杰伦\n陈奕迅\n王菲\n张学友",
    )

    options = parse_options_text(options_text)
    st.caption(f"当前有效候选项：{len(options)} 个（已自动去重、去空行）。")
    st.caption(f"预计比较次数大约：{estimated_comparisons(len(options), None)} 次。")

    with st.expander("查看当前候选项", expanded=False):
        if options:
            for i, item in enumerate(options, 1):
                st.write(f"{i}. {item}")
        else:
            st.write("还没有输入候选项。")

    col1, col2 = st.columns(2)
    with col1:
        if render_button_compat("✅ 开始完整排序", key="btn_start_custom", use_container_width=True):
            if len(options) < 2:
                st.warning("请至少输入 2 个候选项。")
            else:
                init_ranking_state(
                    mode=mode,
                    theme=theme.strip() or "我的偏好排序",
                    options=options,
                    top_k=None,
                    show_poster=False,
                    initial_poster_map=None,
                )
                rerun()
    with col2:
        if render_button_compat("🧹 清空当前配置", key="btn_clear_custom", use_container_width=True):
            clear_ranking_state()
            st.session_state["ui_custom_theme"] = "我的偏好排序"
            st.session_state["ui_custom_options_text"] = ""
            rerun()


def render_douban_mode_controls(mode: str) -> None:
    default_theme = st.session_state.get("ui_douban_theme", "豆瓣电影偏好排序")
    theme = st.text_input("主题名称", value=default_theme, key="ui_douban_theme")

    top_k = int(
        st.number_input(
            "最后要排出 Top 多少",
            min_value=1,
            max_value=250,
            value=10,
            step=1,
            key="ui_douban_top_k",
        )
    )

    pool_n = int(
        st.number_input(
            "使用豆瓣 Top 前多少作为候选池",
            min_value=1,
            max_value=250,
            value=100,
            step=1,
            key="ui_douban_pool_n",
            help="比如填 100，就会用豆瓣 Top250 里的前 100 部电影作为候选项。",
        )
    )

    show_poster = st.checkbox(
        "排序时显示豆瓣海报",
        value=True,
        key="ui_douban_show_poster",
    )

    if pool_n < top_k:
        st.error("候选池数量必须不小于 Top 数量。请让“候选池” >= “Top”。")
    else:
        st.caption(f"将从豆瓣 Top250 中读取前 {pool_n} 部电影，最后给出你的 Top {top_k}。")
        st.caption(f"预计比较次数大约：{estimated_comparisons(pool_n, top_k)} 次。")

    preview_btn = render_button_compat("👀 预览候选电影", key="btn_preview_douban", use_container_width=True)
    if preview_btn:
        if pool_n < top_k:
            st.warning("请先修正参数：候选池数量不能小于 Top 数量。")
        else:
            try:
                movies, _ = prepare_douban_candidates_ui(pool_n, warm_posters=False)
                with st.expander(f"当前候选电影（前 {len(movies)} 部）", expanded=True):
                    for i, item in enumerate(movies, 1):
                        st.write(f"{i}. {item}")
            except Exception as e:
                st.error(f"读取豆瓣电影列表失败：{e}")

    col1, col2 = st.columns(2)
    with col1:
        if render_button_compat("✅ 开始电影 Top 排序", key="btn_start_douban", use_container_width=True):
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
                            theme=theme.strip() or "豆瓣电影偏好排序",
                            options=movies,
                            top_k=top_k,
                            show_poster=show_poster,
                            initial_poster_map=poster_map,
                        )
                        rerun()
                except Exception as e:
                    st.error(f"读取豆瓣电影列表失败：{e}")
    with col2:
        if render_button_compat("🧹 清空当前配置", key="btn_clear_douban", use_container_width=True):
            clear_ranking_state()
            st.session_state["ui_douban_theme"] = "豆瓣电影偏好排序"
            st.session_state["ui_douban_top_k"] = 10
            st.session_state["ui_douban_pool_n"] = 100
            st.session_state["ui_douban_show_poster"] = True
            rerun()


def render_result_section(total: int, comparisons: int, top_k: Optional[int]) -> None:
    ranked = st.session_state.get(k("ranked"), [])
    skipped_items = st.session_state.get(k("skipped_items"), [])

    ensure_share_poster_generated()

    if top_k is None:
        st.success("🎉 排序完成！下面是你的完整排名：")
    else:
        st.success(f"🎉 排序完成！下面是你的 Top {len(ranked)}：")

    for i, item in enumerate(ranked, 1):
        st.write(f"{i}. {item}")

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
    st.markdown("**在这里进行 1v1 选择，并查看结果。**")

    if not st.session_state.get(k("started"), False):
        st.info("左侧配置完成后，点击开始按钮即可。")
        return

    theme = st.session_state.get(k("theme"), "我的排序")
    total = st.session_state.get(k("total"), 0)
    processed = st.session_state.get(k("processed"), 0)
    comparisons = st.session_state.get(k("comparisons"), 0)
    top_k = st.session_state.get(k("top_k"))
    show_poster = st.session_state.get(k("show_poster"), False)
    mode = st.session_state.get(k("mode"), MODE_CUSTOM)
    skipped_items = st.session_state.get(k("skipped_items"), [])

    st.subheader(f"当前主题：{theme}")

    if top_k is None:
        st.caption("当前模式：自定义完整排序")
    else:
        poster_map = st.session_state.get(k("source_poster_map"), {})
        ok_count = sum(1 for v in poster_map.values() if v)
        st.caption(f"当前模式：豆瓣电影 Top {top_k} 排序（候选总数 {total}，已准备海报 {ok_count} 张）")

    if st.session_state.get(k("finished"), False):
        render_result_section(total=total, comparisons=comparisons, top_k=top_k)
        return

    prepare_next_item()
    if st.session_state.get(k("finished"), False):
        rerun()
        return

    current = st.session_state[k("current_item")]
    low = st.session_state[k("low")]
    high = st.session_state[k("high")]
    mid = (low + high) // 2
    opponent = st.session_state[k("ranked")][mid]

    progress = processed / total if total else 0
    st.progress(progress)

    if top_k is None:
        st.caption(f"已处理 {processed} / {total} 个候选项，已比较 {comparisons} 次。")
        st.markdown("### 请选择，你更偏好哪一个？")
    else:
        st.caption(f"已处理 {processed} / {total} 部电影，当前最多保留 Top {top_k}，已比较 {comparisons} 次。")
        st.markdown("### 请选择，你更喜欢哪一部电影？")

    if skipped_items:
        st.caption(f"已剔除 {len(skipped_items)} 项。")

    c1, c2 = st.columns(2)
    with c1:
        st.markdown("#### 选项 A")
        render_option_card(
            title=current,
            button_text="更喜欢 A",
            button_key="btn_left",
            prefer_left=True,
            show_poster=show_poster and mode == MODE_DOUBAN,
        )

    with c2:
        st.markdown("#### 选项 B")
        render_option_card(
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
# 主程序
# =========================
def main() -> None:
    st.set_page_config(
        page_title="统一偏好排序工具",
        page_icon="🎯",
        layout="wide",
    )

    st.title("🎯 统一偏好排序工具")
    st.markdown("一个页面支持两种模式：**自定义完整排序** 和 **豆瓣电影 Top 排序**。")

    left, right = st.columns([1.1, 1.9])
    with left:
        render_left_panel()
    with right:
        render_right_panel()

    safe_divider()
    st.caption("说明：豆瓣模式准备阶段会显示“准备中...”。如果网络异常或海报抓取失败，单张海报可能不显示，但排序功能仍可继续。")


if __name__ == "__main__":
    main()
