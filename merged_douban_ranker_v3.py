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
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import qrcode
import requests
import streamlit as st
import streamlit.components.v1 as components
from bs4 import BeautifulSoup
from PIL import Image, ImageDraw, ImageFont, ImageOps, UnidentifiedImageError

from analytics import (
    EVENT_CHALLENGE_OPENED,
    EVENT_PAGE_VIEW,
    EVENT_POSTER_DOWNLOADED,
    EVENT_RANKING_COMPLETED,
    EVENT_RANKING_STARTED,
    EVENT_SHARE_LINK_COPIED,
    analytics_enabled,
    fetch_admin_metrics,
    fetch_public_metrics,
    get_admin_token,
    get_public_app_url,
    get_session_id,
    track_event,
    track_once,
)
from challenge_store import (
    Challenge,
    build_challenge_url,
    build_template_url,
    challenge_from_template,
    decode_fallback_payload,
    fetch_challenge,
    save_challenge,
)
from launch_copy import (
    FILM_CHALLENGE_TEMPLATES,
    HERO_SUBTITLE,
    HERO_TAGLINE,
    HERO_TITLE,
    LAUNCH_CHECKLIST,
    RESUME_BULLETS,
    challenge_share_caption,
    get_template,
    result_share_caption,
)

# =========================
# 基础配置
# =========================
DOUBAN_TOP250_URL = "https://movie.douban.com/top250"
DOUBAN_SUGGEST_URL = "https://movie.douban.com/j/subject_suggest"
IMDB_SUGGEST_URL = "https://v3.sg.media-imdb.com/suggestion"
APP_TITLE = "电影审美名单"
APP_SUBTITLE = HERO_SUBTITLE
COVER_IMAGE_PATH = Path(__file__).parent / "assets" / "cover_banner.png"
POSTER_CACHE_DIR = Path(__file__).parent / "cache" / "verified_posters"
BATTLE_PICKER_COMPONENT = components.declare_component(
    "battle_picker",
    path=str(Path(__file__).parent / "components" / "battle_picker"),
)
COPY_BUTTON_COMPONENT = components.declare_component(
    "copy_button",
    path=str(Path(__file__).parent / "components" / "copy_button"),
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

# 精确到 IMDb ID 的备用海报源，只覆盖内置片单里豆瓣 Top250 不稳定命中的影片。
CURATED_IMDB_POSTERS: Dict[str, Dict[str, str]] = {
    "追随": {"query": "following", "imdb_id": "tt0154506"},
    "记忆碎片": {"query": "memento", "imdb_id": "tt0209144"},
    "失眠症": {"query": "insomnia", "imdb_id": "tt0278504"},
    "蝙蝠侠：侠影之谜": {"query": "batman_begins", "imdb_id": "tt0372784"},
    "致命魔术": {"query": "the_prestige", "imdb_id": "tt0482571"},
    "蝙蝠侠：黑暗骑士": {"query": "the_dark_knight", "imdb_id": "tt0468569"},
    "盗梦空间": {"query": "inception", "imdb_id": "tt1375666"},
    "蝙蝠侠：黑暗骑士崛起": {"query": "the_dark_knight_rises", "imdb_id": "tt1345836"},
    "星际穿越": {"query": "interstellar", "imdb_id": "tt0816692"},
    "敦刻尔克": {"query": "dunkirk", "imdb_id": "tt5013056"},
    "信条": {"query": "tenet", "imdb_id": "tt6723592"},
    "奥本海默": {"query": "oppenheimer", "imdb_id": "tt15398776"},
    "风之谷": {"query": "nausicaa_of_the_valley_of_the_wind", "imdb_id": "tt0087544"},
    "天空之城": {"query": "castle_in_the_sky", "imdb_id": "tt0092067"},
    "龙猫": {"query": "my_neighbor_totoro", "imdb_id": "tt0096283"},
    "魔女宅急便": {"query": "kikis_delivery_service", "imdb_id": "tt0097814"},
    "红猪": {"query": "porco_rosso", "imdb_id": "tt0104652"},
    "幽灵公主": {"query": "princess_mononoke", "imdb_id": "tt0119698"},
    "千与千寻": {"query": "spirited_away", "imdb_id": "tt0245429"},
    "哈尔的移动城堡": {"query": "howls_moving_castle", "imdb_id": "tt0347149"},
    "悬崖上的金鱼姬": {"query": "ponyo", "imdb_id": "tt0876563"},
    "起风了": {"query": "the_wind_rises", "imdb_id": "tt2013293"},
    "你想活出怎样的人生": {"query": "the_boy_and_the_heron", "imdb_id": "tt6587046"},
    "霸王别姬": {"query": "farewell_my_concubine", "imdb_id": "tt0106332"},
    "活着": {"query": "to_live", "imdb_id": "tt0110081"},
    "无间道": {"query": "infernal_affairs", "imdb_id": "tt0338564"},
    "大话西游之大圣娶亲": {"query": "a_chinese_odyssey_part_two_cinderella", "imdb_id": "tt0114996"},
    "让子弹飞": {"query": "let_the_bullets_fly", "imdb_id": "tt1533117"},
    "鬼子来了": {"query": "devils_on_the_doorstep", "imdb_id": "tt0245929"},
    "饮食男女": {"query": "eat_drink_man_woman", "imdb_id": "tt0111797"},
    "牯岭街少年杀人事件": {"query": "a_brighter_summer_day", "imdb_id": "tt0101985"},
    "阳光灿烂的日子": {"query": "in_the_heat_of_the_sun", "imdb_id": "tt0111786"},
    "花样年华": {"query": "in_the_mood_for_love", "imdb_id": "tt0118694"},
    "一一": {"query": "yi_yi", "imdb_id": "tt0244316"},
    "悲情城市": {"query": "a_city_of_sadness", "imdb_id": "tt0096908"},
    "喜宴": {"query": "the_wedding_banquet", "imdb_id": "tt0107156"},
    "甜蜜蜜": {"query": "comrades_almost_a_love_story", "imdb_id": "tt0117905"},
    "卧虎藏龙": {"query": "crouching_tiger_hidden_dragon", "imdb_id": "tt0190332"},
    "重庆森林": {"query": "chungking_express", "imdb_id": "tt0109424"},
    "春光乍泄": {"query": "happy_together", "imdb_id": "tt0118845"},
    "芙蓉镇": {"query": "hibiscus_town", "imdb_id": "tt0093206"},
    "我不是药神": {"query": "dying_to_survive", "imdb_id": "tt7362036"},
    "哪吒之魔童降世": {"query": "ne_zha", "imdb_id": "tt10627720"},
    "爱在黎明破晓前": {"query": "before_sunrise", "imdb_id": "tt0112471"},
    "爱在日落黄昏时": {"query": "before_sunset", "imdb_id": "tt0381681"},
    "怦然心动": {"query": "flipped", "imdb_id": "tt0817177"},
    "花束般的恋爱": {"query": "we_made_a_beautiful_bouquet", "imdb_id": "tt11219254"},
    "消失的爱人": {"query": "gone_girl", "imdb_id": "tt2267998"},
    "婚姻故事": {"query": "marriage_story", "imdb_id": "tt7653254"},
    "泰坦尼克号": {"query": "titanic", "imdb_id": "tt0120338"},
    "时空恋旅人": {"query": "about_time", "imdb_id": "tt2194499"},
    "恋恋笔记本": {"query": "the_notebook", "imdb_id": "tt0332280"},
    "一天": {"query": "one_day", "imdb_id": "tt1563738"},
    "她": {"query": "her", "imdb_id": "tt1798709"},
    "蓝色情人节": {"query": "blue_valentine", "imdb_id": "tt1120985"},
}

MODE_CUSTOM = "自备片单"
MODE_DOUBAN = "豆瓣高分"

CUSTOM_TEMPLATES = [
    {
        "name": "周末电影",
        "theme": "我的周末电影名单",
        "items": ["千与千寻", "星际穿越", "盗梦空间", "怦然心动", "机器人总动员", "海上钢琴师", "疯狂动物城", "泰坦尼克号", "阿甘正传", "肖申克的救赎"],
    },
    {
        "name": "导演私藏",
        "theme": "我的导演作品名单",
        "items": ["花样年华", "重庆森林", "一一", "牯岭街少年杀人事件", "饮食男女", "阳光灿烂的日子", "让子弹飞", "无间道", "霸王别姬", "活着"],
    },
    {
        "name": "爱情电影",
        "theme": "我的爱情电影名单",
        "items": ["爱在黎明破晓前", "爱在日落黄昏时", "怦然心动", "花束般的恋爱", "时空恋旅人", "泰坦尼克号", "甜蜜蜜", "重庆森林", "恋恋笔记本", "一天"],
    },
    {
        "name": "动画电影",
        "theme": "我的动画电影名单",
        "items": ["千与千寻", "龙猫", "天空之城", "哈尔的移动城堡", "疯狂动物城", "机器人总动员", "寻梦环游记", "飞屋环游记", "你想活出怎样的人生", "哪吒之魔童降世"],
    },
]

DOUBAN_PRESETS = [
    ("轻量", 10, 40),
    ("标准", 10, 100),
    ("细排", 20, 180),
]

SHARE_POSTER_STYLES = ["留白卡片", "银幕红", "夜场蓝"]
SHARE_POSTER_FORMATS = ["自适应长图", "长图 9:16", "方图 1:1"]

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
    "challenge_id",
    "template_id",
    "source_channel",
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
    "poster_prefetch_scheduled",
    "history",
    "skipped_items",
    "user_name",
    "seed_text",
    "blind_mode",
    "side_shuffle",
    "defers",
    "challenge_id",
    "template_id",
    "source_channel",
    "completion_event_signature",
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


def render_download_button_compat(label: str, data: bytes, file_name: str, mime: str, key: str, on_click=None) -> None:
    try:
        st.download_button(label, data=data, file_name=file_name, mime=mime, key=key, use_container_width=True, on_click=on_click)
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


def image_mime_type(image_data: bytes) -> str:
    if image_data.startswith(b"\xff\xd8"):
        return "image/jpeg"
    if image_data.startswith(b"\x89PNG"):
        return "image/png"
    if image_data.startswith(b"RIFF") and b"WEBP" in image_data[:16]:
        return "image/webp"
    return "image/png"


def poster_data_uri(image_data: Optional[bytes]) -> Optional[str]:
    if not image_data:
        return None
    encoded = base64.b64encode(image_data).decode("ascii")
    return f"data:{image_mime_type(image_data)};base64,{encoded}"


@st.cache_data(show_spinner=False, max_entries=512)
def poster_preview_data_uri(image_data: bytes, max_width: int = 360, max_height: int = 520) -> Optional[str]:
    try:
        with Image.open(io.BytesIO(image_data)) as img:
            img = ImageOps.exif_transpose(img)
            img = img.convert("RGB")
            img.thumbnail((max_width, max_height), Image.Resampling.LANCZOS)
            output = io.BytesIO()
            img.save(output, format="JPEG", quality=82, optimize=True)
            encoded = base64.b64encode(output.getvalue()).decode("ascii")
            return f"data:image/jpeg;base64,{encoded}"
    except Exception:
        return poster_data_uri(image_data)


def image_from_bytes(image_data: Optional[bytes]) -> Optional[Image.Image]:
    if not image_data:
        return None
    try:
        img = Image.open(io.BytesIO(image_data))
        return img.convert("RGB")
    except Exception:
        return None


def make_rounded_rect_mask(size: Tuple[int, int], radius: int) -> Image.Image:
    mask = Image.new("L", size, 0)
    draw = ImageDraw.Draw(mask)
    draw.rounded_rectangle((0, 0, size[0], size[1]), radius=radius, fill=255)
    return mask


def render_poster_thumb(image_data: Optional[bytes], size: Tuple[int, int], bg: Tuple[int, int, int]) -> Image.Image:
    thumb = Image.new("RGB", size, bg)
    poster = image_from_bytes(image_data)
    if poster:
        poster.thumbnail((size[0], size[1]), Image.Resampling.LANCZOS)
        x = (size[0] - poster.width) // 2
        y = (size[1] - poster.height) // 2
        thumb.paste(poster, (x, y))
    return thumb


def make_qr_image(url: str, size: int = 164) -> Image.Image:
    qr = qrcode.QRCode(
        version=None,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=8,
        border=2,
    )
    qr.add_data(url or get_public_app_url())
    qr.make(fit=True)
    img = qr.make_image(fill_color="#1f2328", back_color="white").convert("RGB")
    return img.resize((size, size), Image.Resampling.NEAREST)


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


def get_query_param(name: str) -> str:
    try:
        value = st.query_params.get(name, "")
    except Exception:
        try:
            value = st.experimental_get_query_params().get(name, [""])
        except Exception:
            value = ""
    if isinstance(value, list):
        return str(value[0]) if value else ""
    return str(value or "")


def render_copy_button(label: str, text: str, key: str, placeholder: str = "") -> bool:
    result = COPY_BUTTON_COMPONENT(label=label, text=text, placeholder=placeholder, key=key, default=None)
    if isinstance(result, dict):
        return bool(result.get("copied"))
    return False


def get_source_channel() -> str:
    channel = get_query_param("src") or get_query_param("utm_source") or "direct"
    return channel[:60]


def bordered_container():
    try:
        return st.container(border=True)
    except TypeError:
        return st.container()


def render_app_styles() -> None:
    st.markdown(
        """
        <style>
        html,
        body,
        [data-testid="stAppViewContainer"],
        .stApp {
            background: #fbfaf7 !important;
            color: #1f2328 !important;
        }
        [data-testid="stHeader"] {
            background: rgba(251, 250, 247, 0.92) !important;
        }
        [data-testid="stToolbar"] {
            color: #1f2328 !important;
        }
        section.main > div {
            padding-top: 1rem;
        }
        .stApp h1,
        .stApp h2,
        .stApp h3,
        .stApp h4,
        .stApp h5,
        .stApp h6,
        .stApp [data-testid="stMarkdownContainer"],
        .stApp [data-testid="stCaptionContainer"] {
            color: #1f2328;
        }
        .stApp [data-testid="stCaptionContainer"],
        .stApp [data-testid="stCaptionContainer"] p {
            color: #7a746c !important;
        }
        div[data-testid="stRadio"] label,
        div[data-testid="stRadio"] label p,
        div[data-testid="stRadio"] label span {
            color: #1f2328 !important;
        }
        div[data-testid="stRadio"] [role="radiogroup"] {
            gap: 0.25rem;
        }
        div[data-testid="stRadio"] label > div:first-child {
            border-color: #2b2f36 !important;
        }
        div[data-testid="stExpander"] {
            background: #fffdf9;
            border-color: #e7e1d8;
            color: #1f2328;
        }
        div[data-testid="stSelectbox"] label,
        div[data-testid="stTextInput"] label,
        div[data-testid="stNumberInput"] label,
        div[data-testid="stCheckbox"] label,
        div[data-testid="stTextArea"] label,
        div[data-testid="stFileUploader"] label {
            color: #1f2328 !important;
        }
        div[data-testid="stTextInput"] input,
        div[data-testid="stNumberInput"] input,
        div[data-testid="stTextArea"] textarea {
            background: #fffdf9 !important;
            color: #1f2328 !important;
            border-color: #d8d1c6 !important;
        }
        div[data-testid="stButton"] > button {
            min-height: 34px;
            border-radius: 6px;
            border-color: #d8d1c6;
            background: #fffdf9;
            color: #2b2f36;
            font-size: 13px;
            font-weight: 650;
            padding: 0.34rem 0.72rem;
            box-shadow: none;
        }
        div[data-testid="stButton"] > button:hover {
            border-color: #9b6a58;
            color: #6f3f31;
            background: #fffaf4;
        }
        div[data-testid="stButton"] > button[kind="primary"],
        div[data-testid="stButton"] > button[data-testid="baseButton-primary"] {
            border-color: #2b2f36;
            background: #2b2f36;
            color: #fffaf4;
        }
        div[data-testid="stMetric"] {
            background: #fffdf9;
            border: 1px solid #e7e1d8;
            border-radius: 8px;
            padding: 10px 12px;
        }
        .compact-status {
            display: grid;
            grid-template-columns: repeat(6, minmax(0, 1fr));
            gap: 7px;
            margin: 4px 0 8px;
        }
        .status-chip {
            border: 1px solid #e7e1d8;
            border-radius: 8px;
            padding: 7px 9px;
            background: #fffdf9;
        }
        .status-label {
            color: #7a746c;
            font-size: 12px;
            line-height: 1.2;
        }
        .status-value {
            color: #1f2328;
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
            color: #6f665d;
            font-size: 13px;
            font-weight: 700;
        }
        .battle-title {
            color: #1f2328;
            font-size: clamp(18px, 2.3vw, 24px);
            font-weight: 800;
            line-height: 1.25;
            overflow-wrap: anywhere;
            margin: 0 0 8px;
            min-height: 32px;
        }
        .poster-placeholder {
            height: min(46vh, 440px);
            border: 1px dashed #d8d1c6;
            border-radius: 8px;
            background: #fffaf4;
            color: #7a746c;
            display: flex;
            align-items: center;
            justify-content: center;
            text-align: center;
            padding: 16px;
            margin-bottom: 0;
        }
        .poster-choice-frame {
            height: min(46vh, 440px);
            border: 1px solid #e7e1d8;
            border-radius: 8px;
            background: #fffaf4;
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
            color: #6f665d;
            font-weight: 700;
            text-align: center;
            padding: 16px;
        }
        .choice-help {
            color: #7a746c;
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
            color: #1f2328;
            margin: 8px 0 8px;
        }
        .cover-subtitle {
            color: #5f574f;
            font-size: 16px;
            line-height: 1.55;
            margin-bottom: 8px;
        }
        .cover-tag {
            display: inline-block;
            border: 1px solid #d8d1c6;
            border-radius: 999px;
            padding: 6px 12px;
            color: #6f665d;
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
        .launch-hero {
            display: grid;
            grid-template-columns: minmax(0, 1.15fr) minmax(260px, 0.85fr);
            gap: 18px;
            align-items: center;
            margin-bottom: 8px;
            padding: 4px 0 2px;
        }
        .hero-copy {
            min-width: 0;
        }
        .hero-kicker {
            color: #8a4f3d;
            font-size: 12px;
            font-weight: 850;
            letter-spacing: 0;
            margin-bottom: 6px;
        }
        .hero-title {
            color: #1f2328;
            font-size: clamp(32px, 4vw, 50px);
            font-weight: 880;
            letter-spacing: 0;
            line-height: 1.02;
            margin: 0 0 8px;
        }
        .hero-subtitle {
            color: #5f574f;
            font-size: 15px;
            line-height: 1.5;
            margin: 0;
            max-width: 620px;
        }
        .hero-proof {
            display: grid;
            grid-template-columns: repeat(3, minmax(0, 1fr));
            gap: 7px;
            margin: 8px 0 2px;
        }
        .hero-proof-item {
            border: 1px solid #e7e1d8;
            border-radius: 8px;
            padding: 8px 10px;
            background: #fffdf9;
        }
        .hero-proof-value {
            color: #1f2328;
            font-weight: 900;
            font-size: 17px;
            line-height: 1.25;
        }
        .hero-proof-label {
            color: #7a746c;
            font-size: 11px;
            line-height: 1.3;
            margin-top: 2px;
        }
        .example-card {
            border: 1px solid #e7e1d8;
            border-radius: 8px;
            background: #fffdf9;
            padding: 12px;
        }
        .example-title {
            color: #1f2328;
            font-size: 15px;
            font-weight: 900;
            margin-bottom: 6px;
        }
        .example-rank {
            display: flex;
            align-items: center;
            gap: 8px;
            border-top: 1px solid #eee7dd;
            padding: 6px 0;
            color: #2b2f36;
            font-weight: 750;
            font-size: 13px;
        }
        .example-rank span:first-child {
            width: 34px;
            color: #8a4f3d;
            font-weight: 900;
        }
        .challenge-grid {
            display: grid;
            grid-template-columns: repeat(5, minmax(0, 1fr));
            gap: 8px;
            margin: 6px 0 8px;
        }
        .challenge-card {
            border: 1px solid #e7e1d8;
            border-radius: 8px;
            background: #fffdf9;
            padding: 11px;
            min-height: 112px;
            display: flex;
            flex-direction: column;
            justify-content: space-between;
        }
        .challenge-badge {
            display: inline-block;
            width: fit-content;
            border: 1px solid #ead9cc;
            border-radius: 999px;
            color: #8a4f3d;
            background: #fff6ef;
            padding: 3px 7px;
            font-size: 11px;
            font-weight: 800;
            margin-bottom: 6px;
        }
        .challenge-title {
            color: #1f2328;
            font-size: 15px;
            font-weight: 820;
            line-height: 1.3;
            margin-bottom: 4px;
        }
        .challenge-copy {
            color: #6f665d;
            font-size: 12px;
            line-height: 1.38;
        }
        .dashboard-table {
            border: 1px solid #e7e1d8;
            border-radius: 8px;
            background: #fffdf9;
            padding: 12px;
            margin: 8px 0;
        }
        .rank-card {
            border: 1px solid #e7e1d8;
            border-radius: 8px;
            padding: 10px 12px;
            margin: 8px 0;
            background: #fffdf9;
        }
        .rank-card.top-rank {
            border-color: #ead9cc;
            background: #fff6ef;
        }
        .rank-num {
            display: inline-block;
            width: 44px;
            color: #8a4f3d;
            font-weight: 800;
        }
        .rank-name {
            color: #1f2328;
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
            border: 1px solid #e7e1d8;
            border-radius: 8px;
            background: #fffdf9;
            padding: 12px;
            min-width: 0;
        }
        .insight-label {
            color: #7a746c;
            font-size: 12px;
            line-height: 1.25;
            margin-bottom: 4px;
        }
        .insight-value {
            color: #1f2328;
            font-size: 17px;
            font-weight: 800;
            line-height: 1.3;
            overflow-wrap: anywhere;
        }
        .share-callout {
            border: 1px solid #ead9cc;
            border-radius: 8px;
            background: #fff6ef;
            padding: 12px 14px;
            color: #4b352d;
            margin: 8px 0 12px;
        }
        .mini-note {
            color: #7a746c;
            font-size: 13px;
            line-height: 1.5;
        }
        @media (max-width: 820px) {
            section.main > div {
                padding-top: 0.35rem;
            }
            h3 {
                font-size: 1.25rem;
                margin: 0.45rem 0 0.35rem;
            }
            div[data-testid="stHorizontalBlock"] {
                flex-direction: row !important;
                gap: 0.35rem !important;
            }
            div[data-testid="stHorizontalBlock"] > div[data-testid="column"] {
                min-width: 0 !important;
            }
            div[data-testid="stButton"] > button {
                min-height: 30px;
                font-size: 12px;
                padding: 0.24rem 0.38rem;
            }
            .compact-status {
                grid-template-columns: repeat(3, minmax(0, 1fr));
                gap: 5px;
                margin: 3px 0 5px;
            }
            .status-chip {
                padding: 5px 6px;
            }
            .status-label {
                font-size: 10px;
            }
            .status-value {
                font-size: 13px;
                line-height: 1.22;
            }
            .insight-grid {
                grid-template-columns: repeat(2, minmax(0, 1fr));
            }
            .launch-hero,
            .challenge-grid {
                grid-template-columns: 1fr;
            }
            .challenge-grid {
                grid-template-columns: repeat(2, minmax(0, 1fr));
            }
            .hero-proof {
                grid-template-columns: repeat(3, minmax(0, 1fr));
            }
            .battle-title {
                font-size: 22px;
            }
            .poster-choice-frame,
            .poster-placeholder {
                height: min(34vh, 230px);
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


@st.cache_data(show_spinner=False)
def fetch_douban_top250_poster_index() -> Dict[str, str]:
    index: Dict[str, str] = {}
    try:
        entries = fetch_douban_top_movie_entries(250)
    except Exception:
        return index
    for entry in entries:
        title = entry.get("title")
        poster_url = entry.get("poster_url")
        if title and poster_url:
            index[title] = poster_url
    return index


def normalize_image_bytes(image_bytes: bytes) -> Optional[bytes]:
    if not image_bytes:
        return None

    try:
        with Image.open(io.BytesIO(image_bytes)) as img:
            img = ImageOps.exif_transpose(img)
            img = img.convert("RGB")
            img.thumbnail((720, 1080), Image.Resampling.LANCZOS)
            output = io.BytesIO()
            img.save(output, format="JPEG", quality=88, optimize=True, progressive=True)
            return output.getvalue()
    except (UnidentifiedImageError, OSError, ValueError):
        return None


def poster_cache_path(title: str) -> Path:
    digest = hashlib.sha1(title.encode("utf-8")).hexdigest()[:16]
    return POSTER_CACHE_DIR / f"{digest}.jpg"


def legacy_poster_cache_path(title: str) -> Path:
    digest = hashlib.sha1(title.encode("utf-8")).hexdigest()[:16]
    return POSTER_CACHE_DIR / f"{digest}.png"


def read_cached_poster(title: str) -> Optional[bytes]:
    current_path = poster_cache_path(title)
    try:
        if current_path.exists():
            return current_path.read_bytes()
    except OSError:
        return None

    legacy_path = legacy_poster_cache_path(title)
    try:
        if legacy_path.exists():
            legacy_bytes = legacy_path.read_bytes()
            migrated = normalize_image_bytes(legacy_bytes)
            if migrated:
                write_cached_poster(title, migrated)
                return migrated
            return legacy_bytes
    except OSError:
        return None
    return None


def write_cached_poster(title: str, image_data: Optional[bytes]) -> None:
    if not image_data:
        return
    try:
        POSTER_CACHE_DIR.mkdir(parents=True, exist_ok=True)
        poster_cache_path(title).write_bytes(image_data)
    except OSError:
        return


@st.cache_resource(show_spinner=False)
def get_poster_prefetch_executor() -> ThreadPoolExecutor:
    return ThreadPoolExecutor(max_workers=3, thread_name_prefix="poster-prefetch")


def douban_image_url_candidates(img_url: str) -> List[str]:
    if not img_url:
        return []

    candidates = [img_url]
    match = re.search(r"https://img\d+\.doubanio\.com/(.+)", img_url)
    if match:
        path = match.group(1)
        for host in ("img1", "img2", "img3", "img9"):
            candidates.append(f"https://{host}.doubanio.com/{path}")

    normalized: List[str] = []
    seen = set()
    for url in candidates:
        if url and url not in seen:
            normalized.append(url)
            seen.add(url)
    return normalized


@st.cache_data(show_spinner=False)
def fetch_poster_bytes_from_url(img_url: str) -> Optional[bytes]:
    if not img_url or "movie_default_small" in img_url:
        return None

    for url in douban_image_url_candidates(img_url):
        for _ in range(2):
            try:
                img_resp = requests.get(url, headers=HEADERS, timeout=10)
                img_resp.raise_for_status()

                content_type = (img_resp.headers.get("Content-Type") or "").lower()
                if content_type and not content_type.startswith("image/"):
                    continue

                poster_bytes = normalize_image_bytes(img_resp.content)
                if poster_bytes:
                    return poster_bytes
            except Exception:
                continue
    return None


def normalize_imdb_query(query: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", query.lower()).strip("_")


@st.cache_data(show_spinner=False)
def fetch_imdb_poster_bytes(title: str) -> Optional[bytes]:
    poster_meta = CURATED_IMDB_POSTERS.get(title)
    if not poster_meta:
        return None

    query = normalize_imdb_query(poster_meta.get("query", ""))
    imdb_id = poster_meta.get("imdb_id", "")
    if not query or not imdb_id:
        return None

    try:
        resp = requests.get(
            f"{IMDB_SUGGEST_URL}/{query[0]}/{query}.json",
            headers={"User-Agent": HEADERS["User-Agent"], "Accept": "application/json"},
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()
    except Exception:
        return None

    items = data.get("d", []) if isinstance(data, dict) else []
    if not isinstance(items, list):
        return None

    exact_item = None
    for item in items:
        if isinstance(item, dict) and item.get("id") == imdb_id:
            exact_item = item
            break
    if not exact_item:
        return None

    image_url = (exact_item.get("i") or {}).get("imageUrl") if isinstance(exact_item.get("i"), dict) else ""
    return fetch_poster_bytes_from_url(image_url)


@st.cache_data(show_spinner=False)
def fetch_douban_poster_bytes(title: str) -> Optional[bytes]:
    poster_url = fetch_douban_top250_poster_index().get(title)
    if poster_url:
        poster_bytes = fetch_poster_bytes_from_url(poster_url)
        if poster_bytes:
            return poster_bytes

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


def get_best_poster_bytes(title: str, primary_url: str = "") -> Optional[bytes]:
    cached = read_cached_poster(title)
    if cached:
        return cached

    poster_bytes = fetch_poster_bytes_from_url(primary_url) if primary_url else None

    if poster_bytes is None and title in CURATED_IMDB_POSTERS:
        poster_bytes = fetch_imdb_poster_bytes(title)
    if poster_bytes is None:
        poster_bytes = fetch_douban_poster_bytes(title)
    if poster_bytes is None and title not in CURATED_IMDB_POSTERS:
        poster_bytes = fetch_imdb_poster_bytes(title)

    if poster_bytes:
        write_cached_poster(title, poster_bytes)
        return poster_bytes

    return None


def prefetch_poster_to_cache(title: str) -> None:
    try:
        get_best_poster_bytes(title)
    except Exception:
        return


def schedule_poster_prefetch(titles: List[str]) -> None:
    if not titles:
        return

    poster_map = st.session_state.setdefault(k("poster_map"), {})
    failed = set(st.session_state.setdefault(k("poster_fetch_failed"), []))
    scheduled = set(st.session_state.setdefault(k("poster_prefetch_scheduled"), []))
    executor = get_poster_prefetch_executor()
    newly_scheduled: List[str] = []
    seen: set[str] = set()

    for title in titles:
        clean_title = (title or "").strip()
        if not clean_title or clean_title in seen:
            continue
        seen.add(clean_title)
        if poster_map.get(clean_title) or clean_title in failed or clean_title in scheduled:
            continue
        if read_cached_poster(clean_title):
            continue
        executor.submit(prefetch_poster_to_cache, clean_title)
        scheduled.add(clean_title)
        newly_scheduled.append(clean_title)

    if newly_scheduled:
        st.session_state[k("poster_prefetch_scheduled")] = list(scheduled)[-240:]


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
            poster_bytes = get_best_poster_bytes(title, entry.get("poster_url") or "")
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
    challenge_id: str = "",
    template_id: str = "",
    source_channel: str = "",
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
    st.session_state[k("poster_prefetch_scheduled")] = []
    st.session_state[k("history")] = []
    st.session_state[k("skipped_items")] = []
    st.session_state[k("user_name")] = user_name.strip()
    st.session_state[k("seed_text")] = clean_seed
    st.session_state[k("blind_mode")] = blind_mode
    st.session_state[k("side_shuffle")] = side_shuffle
    st.session_state[k("defers")] = 0
    st.session_state[k("challenge_id")] = challenge_id
    st.session_state[k("template_id")] = template_id
    st.session_state[k("source_channel")] = source_channel or get_source_channel()
    st.session_state[k("completion_event_signature")] = ""
    st.session_state[k("share_poster_bytes")] = b""
    st.session_state[k("share_poster_signature")] = ""

    safe_source = "custom" if not template_id and not challenge_id else "shared"
    track_event(
        EVENT_RANKING_STARTED,
        challenge_id=challenge_id,
        mode=mode,
        template_id=template_id,
        source_channel=source_channel or get_source_channel(),
        payload={
            "total": len(opts),
            "top_k": top_k,
            "has_seed": bool(clean_seed),
            "blind_mode": blind_mode,
            "side_shuffle": side_shuffle,
            "source": safe_source,
            "session_hint": get_session_id()[-8:],
        },
    )


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
    challenge_id = st.session_state.get(k("challenge_id"), "")
    template_id = st.session_state.get(k("template_id"), "")
    source_channel = st.session_state.get(k("source_channel"), "")
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
        challenge_id=challenge_id,
        template_id=template_id,
        source_channel=source_channel,
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
        f"署名：{user_name or '未署名'}",
        f"模式：{mode}",
        "类型：完整排序" if top_k is None else f"类型：Top {min(top_k, len(ranked))}",
        f"取舍次数：{comparisons}",
        f"暂放次数：{defers}",
        f"顺序口令：{seed_text or '未设置'}",
        f"生成时间：{generated_at}",
        "",
        "整理结果：",
    ]
    txt_lines.extend(f"{idx}. {item}" for idx, item in enumerate(ranked, 1))
    if skipped_items:
        txt_lines.extend(["", "已略过："])
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
        f"- 署名：{user_name or '未署名'}",
        f"- 模式：{mode}",
        f"- 取舍次数：{comparisons}",
        f"- 暂放次数：{defers}",
    ]
    if seed_text:
        md_lines.append(f"- 顺序口令：`{seed_text}`")
    md_lines.extend(["", "## 整理结果"])
    md_lines.extend(f"{idx}. {item}" for idx, item in enumerate(ranked, 1))
    if skipped_items:
        md_lines.extend(["", "## 已略过"])
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
    challenge_url: str = "",
) -> str:
    caption = result_share_caption(
        app_title=APP_TITLE,
        theme=theme,
        ranked=ranked,
        comparisons=comparisons,
        challenge_url=challenge_url,
        seed_text=seed_text,
    )
    extras = []
    if user_name:
        extras.append(f"署名：{user_name}")
    if skipped_items:
        extras.append(f"略过了 {len(skipped_items)} 部暂时不想判断的电影。")
    if extras:
        return caption + "\n" + "\n".join(extras)
    return caption


def result_archetype(comparisons: int, expected: int, skipped_count: int, ranked_count: int) -> str:
    if ranked_count <= 1:
        return "刚开始整理"
    ratio = comparisons / max(1, expected)
    if skipped_count >= max(3, ranked_count // 4):
        return "取舍清晰"
    if ratio <= 0.65:
        return "直觉很稳"
    if ratio >= 1.1:
        return "认真斟酌"
    return "节奏稳定"


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
          <div class="insight-card"><div class="insight-label">最前面</div><div class="insight-value">{html.escape(champion)}</div></div>
          <div class="insight-card"><div class="insight-label">前三名</div><div class="insight-value">{html.escape(podium)}</div></div>
          <div class="insight-card"><div class="insight-label">整理节奏</div><div class="insight-value">{html.escape(archetype)}</div></div>
          <div class="insight-card"><div class="insight-label">少做判断</div><div class="insight-value">{html.escape(efficiency)}</div></div>
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
    with st.expander("两份名单的差异", expanded=False):
        st.caption("导入另一份 JSON 名单，看看你们把同一批电影放在了哪里。")
        uploaded = st.file_uploader("导入另一份 JSON 名单", type=["json"], key="friend_ranking_json")
        if not uploaded:
            return
        try:
            payload = json.load(uploaded)
            friend_ranked = extract_ranked_items_from_payload(payload)
        except Exception as e:
            st.error(f"读取失败：{e}")
            return
        if not friend_ranked:
            st.warning("这个 JSON 里没有可识别的整理结果。")
            return
        comparison = compare_rankings(my_ranked, friend_ranked)
        shared = comparison["shared"]
        if not shared:
            st.info("两份名单里没有重合电影。")
            return
        friend_name = payload.get("user_name") or "对方"
        st.markdown(
            f"""
            <div class="share-callout">
              你和 {html.escape(str(friend_name))} 共有 {len(shared)} 部重合电影；前 5 名重合 {comparison["top_overlap"]} 部；平均相差 {comparison["avg_gap"]:.1f} 位。
            </div>
            """,
            unsafe_allow_html=True,
        )
        biggest = comparison["biggest_gap"]
        if biggest:
            item, gap, mine, friend = biggest
            st.caption(f"相差最大：{item}，你放在第 {mine} 位，对方放在第 {friend} 位，相差 {gap} 位。")


def current_challenge_for_share() -> Challenge:
    return Challenge(
        id=st.session_state.get(k("challenge_id"), ""),
        theme=st.session_state.get(k("theme"), "电影审美名单"),
        mode=st.session_state.get(k("mode"), MODE_CUSTOM),
        items=st.session_state.get(k("source_options"), []),
        top_k=st.session_state.get(k("top_k")),
        seed_text=st.session_state.get(k("seed_text"), ""),
        source="result_share",
        template_id=st.session_state.get(k("template_id"), ""),
    )


def current_challenge_url() -> str:
    challenge = current_challenge_for_share()
    if challenge.id:
        return build_challenge_url(challenge)
    return build_challenge_url(challenge, use_payload_fallback=True)


def start_challenge(challenge: Challenge, *, show_poster: bool = True) -> None:
    init_ranking_state(
        mode=challenge.mode,
        theme=challenge.theme,
        options=challenge.items,
        top_k=challenge.top_k,
        show_poster=show_poster,
        user_name="",
        seed_text=challenge.seed_text or challenge.id,
        blind_mode=True,
        side_shuffle=True,
        challenge_id=challenge.id,
        template_id=challenge.template_id,
        source_channel=get_source_channel(),
        initial_poster_map=None,
    )
    st.session_state["ui_selected_mode"] = MODE_CUSTOM
    st.session_state["ui_step"] = 3
    rerun()


def resolve_challenge_from_url() -> Optional[Challenge]:
    challenge_id = get_query_param("list") or get_query_param("challenge")
    if challenge_id:
        template = get_template(challenge_id)
        if template:
            return challenge_from_template(template)
        return fetch_challenge(challenge_id)

    payload = get_query_param("payload")
    if payload:
        return decode_fallback_payload(payload)

    return None


def maybe_open_url_challenge() -> None:
    challenge_id = get_query_param("list") or get_query_param("challenge") or get_query_param("payload")
    if not challenge_id or st.session_state.get("loaded_url_challenge") == challenge_id:
        return

    challenge = resolve_challenge_from_url()
    st.session_state["loaded_url_challenge"] = challenge_id
    if not challenge:
        st.warning("这个片单入口暂时不可用，可以先从下方内置片单开始。")
        return

    if st.session_state.get(k("started"), False):
        clear_ranking_state()

    track_once(
        f"challenge_opened_{challenge.id}",
        EVENT_CHALLENGE_OPENED,
        challenge_id=challenge.id,
        mode=challenge.mode,
        template_id=challenge.template_id,
        source_channel=get_source_channel(),
        payload={"item_count": len(challenge.items), "top_k": challenge.top_k},
    )
    start_challenge(challenge)


def render_public_metrics() -> None:
    metrics = fetch_public_metrics()
    completed = metrics.get("completed", 0)
    today_users = metrics.get("today_users", 0)
    avg = metrics.get("avg_comparisons", 0.0)
    if not metrics.get("enabled"):
        completed, today_users, avg = 0, 0, 0.0
    st.markdown(
        f"""
        <div class="hero-proof">
          <div class="hero-proof-item"><div class="hero-proof-value">{completed}</div><div class="hero-proof-label">已整理名单</div></div>
          <div class="hero-proof-item"><div class="hero-proof-value">{today_users}</div><div class="hero-proof-label">今日整理</div></div>
          <div class="hero-proof-item"><div class="hero-proof-value">{avg:.1f}</div><div class="hero-proof-label">平均取舍次数</div></div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_admin_dashboard() -> None:
    token = get_query_param("admin")
    expected = get_admin_token()
    if not expected or token != expected:
        st.error("后台口令无效或未配置。")
        return

    st.title("电影审美名单 · 匿名数据看板")
    metrics = fetch_admin_metrics()
    if not metrics.get("enabled"):
        st.warning("Supabase 还没有配置，暂时没有可展示的数据。")
        return

    counts = metrics.get("counts", {})
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.metric("访问", counts.get(EVENT_PAGE_VIEW, 0))
    with c2:
        st.metric("开始整理", counts.get(EVENT_RANKING_STARTED, 0))
    with c3:
        st.metric("完成", counts.get(EVENT_RANKING_COMPLETED, 0), f"{metrics.get('completion_rate', 0):.1%}")
    with c4:
        st.metric("复制链接", counts.get(EVENT_SHARE_LINK_COPIED, 0), f"{metrics.get('share_rate', 0):.1%}")

    left, right = st.columns(2)
    with left:
        st.subheader("热门模板")
        for template_id, count in metrics.get("top_templates", []):
            st.write(f"{template_id}: {count}")
    with right:
        st.subheader("热门片单")
        for challenge_id, count in metrics.get("top_challenges", []):
            st.write(f"{challenge_id}: {count}")

    with st.expander("最近事件", expanded=False):
        st.json(metrics.get("recent_events", [])[:50])


def render_cover_header() -> None:
    cover_src = image_file_data_uri(COVER_IMAGE_PATH)
    image_html = f'<img class="cover-image" src="{cover_src}" alt="{APP_TITLE} 封面">' if cover_src else ""
    st.markdown(
        f"""
        <div class="launch-hero">
          <div class="hero-copy">
            <div class="hero-kicker">电影片单整理器</div>
            <h1 class="hero-title">{html.escape(HERO_TITLE)}</h1>
            <p class="hero-subtitle">{html.escape(HERO_SUBTITLE)} {html.escape(HERO_TAGLINE)}</p>
          </div>
          <div class="example-card">
            {image_html}
            <div class="example-title">示例：一份电影审美名单</div>
            <div class="example-rank"><span>#01</span><div>千与千寻</div></div>
            <div class="example-rank"><span>#02</span><div>星际穿越</div></div>
            <div class="example-rank"><span>#03</span><div>霸王别姬</div></div>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    safe_divider()


def get_poster_for_option(name: str, *, fetch: bool = True) -> Optional[bytes]:
    poster_map = st.session_state.setdefault(k("poster_map"), {})
    if poster_map.get(name):
        return poster_map[name]

    cached = read_cached_poster(name)
    if cached:
        poster_map[name] = cached
        st.session_state[k("poster_map")] = poster_map
        return cached

    if not fetch:
        return None

    failed = st.session_state.setdefault(k("poster_fetch_failed"), [])
    if name in failed:
        return None

    poster_bytes = get_best_poster_bytes(name)
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
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc" if bold else "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/opentype/noto/NotoSerifCJK-Bold.ttc" if bold else "/usr/share/fonts/opentype/noto/NotoSerifCJK-Regular.ttc",
        "/usr/share/fonts/truetype/noto/NotoSansCJK-Bold.ttc" if bold else "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/truetype/wqy/wqy-microhei.ttc",
        "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc",
        "/usr/share/fonts/truetype/arphic/uming.ttc",
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
    share_url: str = "",
) -> str:
    return "|".join(
        [
            theme,
            mode,
            user_name,
            poster_style,
            poster_format,
            share_url,
            "full" if top_k is None else f"top{top_k}",
            "ranked:" + "||".join(ranked),
            "skipped:" + "||".join(skipped_items),
        ]
    )


def get_share_palette(poster_style: str) -> dict:
    palettes = {
        "银幕红": {
            "bg": (54, 20, 23),
            "card": (255, 248, 238),
            "row": (255, 252, 246),
            "outline": (242, 199, 122),
            "title": (70, 28, 28),
            "text": (30, 28, 26),
            "muted": (113, 89, 75),
            "accent": (192, 49, 49),
        },
        "夜场蓝": {
            "bg": (14, 18, 32),
            "card": (25, 31, 48),
            "row": (33, 40, 61),
            "outline": (81, 102, 151),
            "title": (236, 242, 255),
            "text": (236, 242, 255),
            "muted": (171, 185, 214),
            "accent": (111, 231, 214),
        },
        "留白卡片": {
            "bg": (246, 247, 251),
            "card": (255, 255, 255),
            "row": (250, 251, 254),
            "outline": (228, 231, 236),
            "title": (20, 24, 35),
            "text": (20, 24, 35),
            "muted": (98, 106, 120),
            "accent": (73, 93, 241),
        },
    }
    aliases = {
        "热映红毯": "银幕红",
        "午夜霓虹": "夜场蓝",
        "清爽白卡": "留白卡片",
    }
    return palettes.get(aliases.get(poster_style, poster_style), palettes["留白卡片"])


def get_result_poster_bytes(title: str) -> Optional[bytes]:
    poster_map = st.session_state.get(k("poster_map"), {})
    if poster_map.get(title):
        return poster_map[title]

    cached = read_cached_poster(title)
    if cached:
        return cached

    poster_bytes = get_best_poster_bytes(title)
    if poster_bytes:
        poster_map[title] = poster_bytes
        st.session_state[k("poster_map")] = poster_map
    return poster_bytes


def generate_share_poster_bytes(
    theme: str,
    ranked: List[str],
    skipped_items: List[str],
    top_k: Optional[int],
    mode: str,
    user_name: str,
    poster_style: str,
    poster_format: str,
    share_url: str = "",
    poster_bytes_map: Optional[Dict[str, Optional[bytes]]] = None,
) -> bytes:
    width = 1080
    fixed_height = None
    if poster_format == "长图 9:16":
        fixed_height = 1920
    elif poster_format == "方图 1:1":
        fixed_height = 1080

    padding = 64
    row_height = 144
    row_gap = 12
    thumb_size = (86, 124)
    palette = get_share_palette(poster_style)
    poster_bytes_map = poster_bytes_map or {}
    share_url = get_public_app_url()

    measure_img = Image.new("RGB", (1, 1))
    measure_draw = ImageDraw.Draw(measure_img)

    title_font = load_font(50, bold=True)
    subtitle_font = load_font(26)
    item_font = load_font(32)
    small_font = load_font(22)
    tiny_font = load_font(18)

    title_lines = wrap_text(measure_draw, theme, title_font, width - padding * 2)
    title_height = len(title_lines) * 60
    header_height = title_height + 54 + (34 if user_name else 0) + 34
    qr_block_height = 184
    bottom_margin = 48

    display_ranked = ranked
    if fixed_height is not None:
        available = fixed_height - padding - header_height - qr_block_height - bottom_margin
        max_rows = max(3, available // (row_height + row_gap))
        display_ranked = ranked[: min(len(ranked), max_rows)]

    text_x = padding + 56 + thumb_size[0] + 28
    max_text_width = width - text_x - padding
    ranked_layout = []
    for item in display_ranked:
        wrapped = wrap_text(measure_draw, item, item_font, max_text_width)
        ranked_layout.append((item, wrapped))

    skipped_lines: List[str] = []
    if skipped_items:
        joined = "、".join(skipped_items[:12])
        if len(skipped_items) > 12:
            joined += "……"
        skipped_lines = wrap_text(measure_draw, joined, small_font, width - padding * 2)

    content_height = padding + header_height + len(ranked_layout) * (row_height + row_gap)
    if len(display_ranked) < len(ranked):
        content_height += 38
    if skipped_items:
        content_height += 12 + 2 + 24 + 36 + len(skipped_lines) * 28
    content_height += qr_block_height + bottom_margin
    height = fixed_height or max(900, content_height)

    img = Image.new("RGB", (width, height), palette["bg"])
    draw = ImageDraw.Draw(img)

    draw.rounded_rectangle((36, 36, width - 36, height - 36), radius=36, fill=palette["card"], outline=palette["outline"], width=2)

    y = padding
    for line in title_lines:
        draw.text((padding, y), line, font=title_font, fill=palette["title"])
        y += 60

    if top_k is None:
        subtitle = "完整偏爱顺序"
    elif mode == MODE_DOUBAN:
        subtitle = f"豆瓣电影前 {min(top_k, len(ranked))} 名"
    else:
        subtitle = f"保留前 {min(top_k, len(ranked))} 名"
    draw.text((padding, y), subtitle, font=subtitle_font, fill=palette["muted"])
    y += 54
    if user_name:
        draw.text((padding, y), f"by {user_name}", font=small_font, fill=palette["muted"])
        y += 34

    draw.line((padding, y, width - padding, y), fill=palette["outline"], width=2)
    y += 28

    thumb_mask = make_rounded_rect_mask(thumb_size, 12)
    for idx, (item, wrapped) in enumerate(ranked_layout, 1):
        row_bottom = y + row_height
        draw.rounded_rectangle((padding, y, width - padding, row_bottom), radius=20, fill=palette.get("row", palette["card"]))
        rank_text = f"{idx:02d}"
        draw.text((padding + 2, y + 44), rank_text, font=item_font, fill=palette["accent"])

        thumb_x = padding + 58
        thumb_y = y + 10
        poster_thumb = render_poster_thumb(poster_bytes_map.get(item), thumb_size, (238, 239, 243))
        if poster_bytes_map.get(item):
            img.paste(poster_thumb, (thumb_x, thumb_y), thumb_mask)
        else:
            draw.rounded_rectangle(
                (thumb_x, thumb_y, thumb_x + thumb_size[0], thumb_y + thumb_size[1]),
                radius=12,
                fill=(238, 239, 243),
                outline=palette["outline"],
                width=1,
            )
            draw.text((thumb_x + 15, thumb_y + 42), "暂无\n海报", font=tiny_font, fill=(112, 118, 130), spacing=4)

        text_y = y + max(24, (row_height - len(wrapped) * 38) // 2)
        for j, line in enumerate(wrapped):
            draw.text((text_x, text_y + j * 38), line, font=item_font, fill=palette["text"])
        y = row_bottom + row_gap

    if len(display_ranked) < len(ranked):
        draw.text((text_x, y), f"还有 {len(ranked) - len(display_ranked)} 项完整名单", font=small_font, fill=palette["muted"])
        y += 38

    if skipped_items:
        y += 12
        draw.line((padding, y, width - padding, y), fill=palette["outline"], width=2)
        y += 24
        skipped_text = f"已略过暂不判断的电影：{len(skipped_items)} 部"
        draw.text((padding, y), skipped_text, font=small_font, fill=palette["muted"])
        y += 36

        for line in skipped_lines:
            draw.text((padding, y), line, font=small_font, fill=palette["muted"])
            y += 28

    qr_y = min(max(y + 12, height - padding - qr_block_height), height - padding - qr_block_height)
    draw.rounded_rectangle((padding, qr_y, width - padding, qr_y + qr_block_height), radius=24, fill=(255, 255, 255), outline=palette["outline"], width=2)
    qr_img = make_qr_image(share_url, 144)
    img.paste(qr_img, (padding + 20, qr_y + 20))
    qr_text_x = padding + 188
    draw.text((qr_text_x, qr_y + 30), "扫码打开电影审美名单", font=subtitle_font, fill=(31, 35, 40))
    draw.text((qr_text_x, qr_y + 72), "从首页进入，排出你自己的顺序。", font=small_font, fill=(98, 106, 120))
    for idx, line in enumerate(wrap_text(draw, share_url, tiny_font, width - qr_text_x - padding - 20)[:2]):
        draw.text((qr_text_x, qr_y + 112 + idx * 24), line, font=tiny_font, fill=(112, 118, 130))

    footer = f"{APP_TITLE} · {datetime.now().strftime('%Y-%m-%d %H:%M')}"
    draw.text((padding, height - 70), footer, font=small_font, fill=palette["muted"])

    out = io.BytesIO()
    img.save(out, format="PNG")
    return out.getvalue()


def generate_challenge_poster_bytes(theme: str, challenge_url: str, item_count: int) -> bytes:
    width, height = 1080, 1350
    palette = get_share_palette("银幕红")
    home_url = get_public_app_url()
    title_font = load_font(58, bold=True)
    subtitle_font = load_font(32)
    body_font = load_font(28)
    small_font = load_font(22)

    img = Image.new("RGB", (width, height), palette["bg"])
    draw = ImageDraw.Draw(img)
    draw.rounded_rectangle((48, 48, width - 48, height - 48), radius=34, fill=palette["card"], outline=palette["outline"], width=2)

    y = 110
    draw.text((80, y), "电影审美名单", font=subtitle_font, fill=palette["accent"])
    y += 72
    for line in wrap_text(draw, theme, title_font, width - 160):
        draw.text((80, y), line, font=title_font, fill=palette["title"])
        y += 68

    y += 24
    draw.line((80, y, width - 80, y), fill=palette["outline"], width=2)
    y += 48
    body_lines = [
        f"{item_count} 部电影",
        "每次只选更喜欢的一部",
        "发给朋友，看看彼此的喜欢如何不同",
    ]
    for line in body_lines:
        draw.text((80, y), line, font=body_font, fill=palette["text"])
        y += 52

    y += 40
    draw.rounded_rectangle((80, y, width - 80, y + 260), radius=24, fill=(255, 255, 255), outline=palette["outline"], width=2)
    qr_img = make_qr_image(home_url, 150)
    img.paste(qr_img, (110, y + 54))
    draw.text((290, y + 44), "打开首页", font=subtitle_font, fill=palette["title"])
    url_lines = wrap_text(draw, home_url, small_font, width - 220)
    yy = y + 104
    for line in url_lines[:4]:
        draw.text((290, yy), line, font=small_font, fill=palette["muted"])
        yy += 32

    footer = f"{APP_TITLE} · {datetime.now().strftime('%Y-%m-%d')}"
    draw.text((80, height - 110), footer, font=small_font, fill=palette["muted"])

    out = io.BytesIO()
    img.save(out, format="PNG")
    return out.getvalue()


def ensure_share_poster_generated(share_url: str = "") -> None:
    ranked = st.session_state.get(k("ranked"), [])
    if not ranked:
        return
    share_url = get_public_app_url()

    theme = st.session_state.get(k("theme"), "我的排序")
    skipped_items = st.session_state.get(k("skipped_items"), [])
    top_k = st.session_state.get(k("top_k"))
    mode = st.session_state.get(k("mode"), MODE_CUSTOM)
    user_name = st.session_state.get(k("user_name"), "")
    poster_style = st.session_state.get(k("share_poster_style"), SHARE_POSTER_STYLES[0])
    poster_format = st.session_state.get(k("share_poster_format"), SHARE_POSTER_FORMATS[0])
    signature = build_share_poster_signature(theme, ranked, skipped_items, top_k, mode, user_name, poster_style, poster_format, share_url)

    if st.session_state.get(k("share_poster_signature")) == signature and st.session_state.get(k("share_poster_bytes")):
        return

    display_count = len(ranked)
    if poster_format == "方图 1:1":
        display_count = min(display_count, 5)
    elif poster_format == "长图 9:16":
        display_count = min(display_count, 10)
    poster_bytes_map = {title: get_result_poster_bytes(title) for title in ranked[:display_count]}
    poster_bytes = generate_share_poster_bytes(
        theme,
        ranked,
        skipped_items,
        top_k,
        mode,
        user_name,
        poster_style,
        poster_format,
        share_url=share_url,
        poster_bytes_map=poster_bytes_map,
    )
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
    left_poster_bytes = get_poster_for_option(left_title, fetch=True) if show_poster else None
    right_poster_bytes = get_poster_for_option(right_title, fetch=True) if show_poster else None
    left_poster = poster_preview_data_uri(left_poster_bytes) if left_poster_bytes else None
    right_poster = poster_preview_data_uri(right_poster_bytes) if right_poster_bytes else None
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


def upcoming_poster_candidates(current: str, opponent: str) -> List[str]:
    candidates: List[str] = []
    ranked = st.session_state.get(k("ranked"), [])
    remaining = st.session_state.get(k("remaining"), [])
    low = st.session_state.get(k("low"), 0)
    high = st.session_state.get(k("high"), 0)

    for title in (current, opponent):
        if title:
            candidates.append(title)

    if ranked:
        probe_indices = {
            get_current_opponent_index(ranked, low, high),
            max(0, min(len(ranked) - 1, low)),
            max(0, min(len(ranked) - 1, high - 1)),
        }
        for idx in sorted(probe_indices):
            if 0 <= idx < len(ranked):
                candidates.append(ranked[idx])

    candidates.extend(remaining[:5])
    return candidates


# =========================
# 排序页面渲染
# =========================
def render_result_section(total: int, comparisons: int, top_k: Optional[int]) -> None:
    ranked = st.session_state.get(k("ranked"), [])
    skipped_items = st.session_state.get(k("skipped_items"), [])
    user_name = st.session_state.get(k("user_name"), "")
    seed_text = st.session_state.get(k("seed_text"), "")
    defers = st.session_state.get(k("defers"), 0)
    challenge_id = st.session_state.get(k("challenge_id"), "")
    template_id = st.session_state.get(k("template_id"), "")
    source_channel = st.session_state.get(k("source_channel"), "")
    challenge_url = current_challenge_url()

    completion_signature = build_share_poster_signature(
        st.session_state.get(k("theme"), "我的排序"),
        ranked,
        skipped_items,
        top_k,
        st.session_state.get(k("mode"), MODE_CUSTOM),
        user_name,
        "completion",
        "event",
    )
    if st.session_state.get(k("completion_event_signature")) != completion_signature:
        payload = {
            "total": total,
            "ranked_count": len(ranked),
            "skipped_count": len(skipped_items),
            "comparisons": comparisons,
            "top_k": top_k,
            "defers": defers,
            "session_hint": get_session_id()[-8:],
        }
        if template_id and ranked:
            payload["winner"] = ranked[0]
        track_event(
            EVENT_RANKING_COMPLETED,
            challenge_id=challenge_id,
            mode=st.session_state.get(k("mode"), MODE_CUSTOM),
            template_id=template_id,
            source_channel=source_channel,
            payload=payload,
        )
        st.session_state[k("completion_event_signature")] = completion_signature

    if top_k is None:
        st.success("已经整理完成。下面是你的完整名单。")
    else:
        st.success(f"已经整理完成。下面是你的前 {len(ranked)} 名。")

    render_result_insights(total=total, comparisons=comparisons, top_k=top_k)
    render_ranked_list(ranked)

    summary = f"共整理 {total} 部电影，作出 {comparisons} 次取舍。"
    if skipped_items:
        summary += f" 已略过 {len(skipped_items)} 项。"
    if defers:
        summary += f" 暂放 {defers} 次。"
    st.caption(summary)

    st.subheader("保存与分享")
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
    ensure_share_poster_generated(challenge_url)

    poster_bytes = st.session_state.get(k("share_poster_bytes"), b"")
    if poster_bytes:
        with st.expander("结果海报", expanded=True):
            show_image_compat(poster_bytes)
            file_name = f"{slugify_filename(st.session_state.get(k('theme'), 'ranking'))}_share.png"
            render_download_button_compat(
                "下载结果海报",
                data=poster_bytes,
                file_name=file_name,
                mime="image/png",
                key="btn_download_share_poster",
                on_click=lambda: track_event(
                    EVENT_POSTER_DOWNLOADED,
                    challenge_id=challenge_id,
                    mode=st.session_state.get(k("mode"), MODE_CUSTOM),
                    template_id=template_id,
                    source_channel=source_channel,
                    payload={"poster_type": "result"},
                ),
            )

    challenge_poster = generate_challenge_poster_bytes(
        st.session_state.get(k("theme"), "电影审美名单"),
        challenge_url,
        len(st.session_state.get(k("source_options"), [])),
    )
    with st.expander("同一份片单海报", expanded=False):
        show_image_compat(challenge_poster)
        render_download_button_compat(
            "下载片单海报",
            data=challenge_poster,
            file_name=f"{slugify_filename(st.session_state.get(k('theme'), 'challenge'))}_challenge.png",
            mime="image/png",
            key="btn_download_challenge_poster",
            on_click=lambda: track_event(
                EVENT_POSTER_DOWNLOADED,
                challenge_id=challenge_id,
                mode=st.session_state.get(k("mode"), MODE_CUSTOM),
                template_id=template_id,
                source_channel=source_channel,
                payload={"poster_type": "challenge"},
            ),
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
        challenge_url=challenge_url,
    )
    with st.expander("发布文案", expanded=True):
        st.text_area("文案", value=share_caption, height=220)
        st.caption("发朋友圈、群聊或评论区时可以直接使用；JSON 可用于查看两份名单的差异。")
        if render_copy_button("复制片单链接", challenge_url, "copy_result_challenge_link", "片单链接"):
            track_event(
                EVENT_SHARE_LINK_COPIED,
                challenge_id=challenge_id,
                mode=mode,
                template_id=template_id,
                source_channel=source_channel,
                payload={"surface": "result"},
            )
        if render_copy_button("复制文案", share_caption, "copy_result_share_caption", "发布文案"):
            track_event(
                EVENT_SHARE_LINK_COPIED,
                challenge_id=challenge_id,
                mode=mode,
                template_id=template_id,
                source_channel=source_channel,
                payload={"surface": "caption"},
            )

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
            render_download_button_compat("下载片单 JSON", json_bytes, f"{base_name}.json", "application/json", "btn_export_json")
        with d4:
            render_download_button_compat("下载 Markdown", md_bytes, f"{base_name}.md", "text/markdown", "btn_export_md")

    render_friend_compare(ranked)

    col1, col2, col3 = st.columns(3)
    with col1:
        if render_button_compat("撤销上一步", key="btn_undo_result", use_container_width=True):
            undo_last_step()
    with col2:
        if render_button_compat("再排一次", key="btn_reset_same", use_container_width=True):
            reset_same_config()
    with col3:
        if render_button_compat("清空", key="btn_clear_result", use_container_width=True):
            clear_ranking_state()
            rerun()


def render_right_panel() -> None:
    if not st.session_state.get(k("started"), False):
        st.info("片单准备好后，就可以开始逐组选择。")
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
        st.subheader(f"这份片单：{theme}")
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
        mode_label = "完整顺序"
    elif mode == MODE_DOUBAN:
        mode_label = f"豆瓣前 {top_k} 名"
    else:
        mode_label = f"保留前 {top_k} 名"
    player_label = user_name or "未署名"

    st.markdown(
        f"""
        <div class="compact-status">
          <div class="status-chip"><div class="status-label">主题</div><div class="status-value">{html.escape(theme)}</div></div>
          <div class="status-chip"><div class="status-label">署名</div><div class="status-value">{html.escape(player_label)}</div></div>
          <div class="status-chip"><div class="status-label">进度</div><div class="status-value">{processed}/{total}</div></div>
          <div class="status-chip"><div class="status-label">已取舍</div><div class="status-value">{comparisons}</div></div>
          <div class="status-chip"><div class="status-label">预计剩余</div><div class="status-value">约 {remaining_estimate}</div></div>
          <div class="status-chip"><div class="status-label">略过 / 暂放</div><div class="status-value">{len(skipped_items)} / {defers}</div></div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.caption(f"{mode_label}。快捷键：A/← 选择左侧，D/→ 选择右侧。{'已隐藏过程名单，结束后再揭晓。' if blind_mode else ''}")

    if top_k is None:
        st.markdown("### 你更喜欢哪一个？")
    else:
        if st.session_state.get(k("top_k_boundary_check"), False):
            st.caption("这部电影会先和当前名单末位相遇；如果没有进入前列，会自然略过。")
        st.markdown("### 你更喜欢哪一部？")

    if side_shuffle:
        current_on_left = stable_int(f"{current}|{opponent}|{comparisons}|{st.session_state.get(k('seed_text'), '')}") % 2 == 0
    else:
        current_on_left = True

    left_title = current if current_on_left else opponent
    right_title = opponent if current_on_left else current
    left_label = "新进入" if current_on_left else "名单中"
    right_label = "名单中" if current_on_left else "新进入"

    ctrl1, ctrl2, ctrl3, ctrl4 = st.columns(4)
    with ctrl1:
        label_left = "未看过 A" if mode == MODE_DOUBAN else "略过 A"
        if render_button_compat(label_left, key="btn_skip_left", use_container_width=True):
            if current_on_left:
                handle_skip_current_item()
            else:
                handle_skip_opponent_item()
    with ctrl2:
        label_right = "未看过 B" if mode == MODE_DOUBAN else "略过 B"
        if render_button_compat(label_right, key="btn_skip_right", use_container_width=True):
            if current_on_left:
                handle_skip_opponent_item()
            else:
                handle_skip_current_item()
    with ctrl3:
        if render_button_compat("暂放", key="btn_defer_pair", use_container_width=True):
            handle_defer_current_pair()
    with ctrl4:
        if render_button_compat("上一步", key="btn_undo_live", use_container_width=True):
            undo_last_step()

    component_key = f"battle_{processed}_{comparisons}_{stable_int(current + opponent)}"
    choice = render_battle_picker(
        left_title=left_title,
        right_title=right_title,
        left_label=left_label,
        right_label=right_label,
        show_poster=show_poster,
        key=component_key,
    )
    if choice:
        prefer_current = (choice == "left" and current_on_left) or (choice == "right" and not current_on_left)
        handle_choice(prefer_left=prefer_current)
        return

    if show_poster:
        schedule_poster_prefetch(upcoming_poster_candidates(current, opponent))

    ranked = st.session_state.get(k("ranked"), [])
    expander_title = "过程名单" if top_k is None else f"当前前 {len(ranked)} 名"
    if blind_mode:
        st.caption("过程名单已隐藏，结束后再揭晓。")
    else:
        with st.expander(expander_title, expanded=False):
            for i, item in enumerate(ranked, 1):
                st.write(f"{i}. {item}")

    if skipped_items:
        with st.expander("已略过的电影", expanded=False):
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
        ("① 选片单", 1),
        ("② 定范围", 2),
        ("③ 作取舍", 3),
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
        "今日可排的片单",
        "不用先想完整顺序，只在两部电影之间作一次取舍。",
    )

    card_html = []
    for template in FILM_CHALLENGE_TEMPLATES:
        card_html.append(
            f'<div class="challenge-card">'
            f'<div>'
            f'<span class="challenge-badge">{html.escape(str(template.get("badge", "电影片单")))}</span>'
            f'<div class="challenge-title">{html.escape(str(template["name"]))}</div>'
            f'<div class="challenge-copy">{html.escape(str(template.get("tagline", "")))}</div>'
            f'</div>'
            f'<div class="mini-note">{len(template.get("items", []))} 部电影 · 前 {template.get("top_k", 10)} 名</div>'
            f'</div>'
        )
    st.markdown(f'<div class="challenge-grid">{"".join(card_html)}</div>', unsafe_allow_html=True)

    cols = st.columns(len(FILM_CHALLENGE_TEMPLATES))
    for idx, template in enumerate(FILM_CHALLENGE_TEMPLATES):
        with cols[idx]:
            template_id = str(template["id"])
            if render_button_compat("整理", key=f"btn_start_template_{template_id}", use_container_width=True, button_type="primary"):
                start_challenge(challenge_from_template(template))

    with st.expander("把这份片单发给朋友", expanded=False):
        selected_template_name = st.selectbox(
            "选择片单",
            [str(template["name"]) for template in FILM_CHALLENGE_TEMPLATES],
            key="home_share_template_name",
        )
        selected_template = next(
            template for template in FILM_CHALLENGE_TEMPLATES if str(template["name"]) == selected_template_name
        )
        template_id = str(selected_template["id"])
        template_url = build_template_url(template_id)
        if render_copy_button("复制片单链接", template_url, f"copy_template_{template_id}", "片单链接"):
            track_event(
                EVENT_SHARE_LINK_COPIED,
                challenge_id=template_id,
                mode=MODE_CUSTOM,
                template_id=template_id,
                source_channel=get_source_channel(),
                payload={"surface": "home_template"},
            )

    safe_divider()
    st.subheader("写下自己的片单")
    mode = st.radio(
        "片单来源",
        [MODE_CUSTOM, MODE_DOUBAN],
        index=0 if current_mode == MODE_CUSTOM else 1,
        help="自备片单适合私人主题；豆瓣高分会读取豆瓣 Top250。",
        key="ui_mode_step1",
    )
    set_selected_mode(mode)

    safe_divider()
    if mode == MODE_CUSTOM:
        st.caption("把想整理的电影粘进来，也可以生成一条片单链接发给朋友。")
    else:
        st.caption("设置保留名次和候选范围，从豆瓣高分片里整理自己的顺序。")

    spacer, next_col = st.columns([1, 1])
    with spacer:
        st.empty()
    with next_col:
        if render_button_compat("继续整理", key="btn_to_step2", use_container_width=True, button_type="primary"):
            go_to_step(2)

    safe_divider()
    render_public_metrics()


def render_custom_template_gallery() -> None:
    with st.expander("片单灵感", expanded=not bool(st.session_state.get("ui_custom_options_text", ""))):
        st.caption("先放入一组电影，再慢慢替换成自己的名单。")
        cols = st.columns(4)
        for idx, template in enumerate(CUSTOM_TEMPLATES):
            with cols[idx % 4]:
                if render_button_compat(template["name"], key=f"btn_custom_template_{idx}", use_container_width=True):
                    st.session_state["ui_custom_theme"] = template["theme"]
                    st.session_state["ui_custom_options_text"] = "\n".join(template["items"])
                    rerun()


def render_douban_preset_buttons() -> None:
    with st.expander("整理深度", expanded=True):
        st.caption("轻量适合几分钟完成，标准适合认真整理，细排适合想多看几轮的时候。")
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

    with st.expander("署名与顺序", expanded=True):
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
                "顺序口令",
                key=f"{prefix}_seed_text",
                placeholder="例：weekend-001",
                help="同样候选 + 同样口令会得到同样出场顺序，方便朋友整理同一份片单。",
            )
        c3, c4 = st.columns(2)
        with c3:
            blind_mode = st.checkbox(
                "隐藏过程名单，结束后再揭晓",
                key=f"{prefix}_blind_mode",
            )
        with c4:
            side_shuffle = st.checkbox(
                "左右随机，降低固定位置偏差",
                key=f"{prefix}_side_shuffle",
            )
    return {
        "user_name": user_name,
        "seed_text": seed_text,
        "blind_mode": blind_mode,
        "side_shuffle": side_shuffle,
    }


def reset_custom_parameter_defaults() -> None:
    st.session_state["ui_custom_theme"] = "我的电影审美名单"
    st.session_state["ui_custom_options_text"] = ""
    st.session_state["ui_custom_top_k_enabled"] = False
    st.session_state["ui_custom_top_k"] = 10
    st.session_state["ui_custom_user_name"] = ""
    st.session_state["ui_custom_seed_text"] = ""
    st.session_state["ui_custom_blind_mode"] = False
    st.session_state["ui_custom_side_shuffle"] = True
    st.session_state.pop("ui_custom_challenge_url", None)
    st.session_state.pop("ui_custom_challenge_caption", None)
    st.session_state.pop("ui_custom_challenge_id", None)


def reset_douban_parameter_defaults() -> None:
    st.session_state["ui_douban_theme"] = "我的豆瓣电影名单"
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

    st.text_input("片单标题", value=st.session_state.get("ui_custom_theme", "我的电影审美名单"), key="ui_custom_theme")
    st.text_area(
        "电影名单（每行一部，也可以直接粘贴逗号分隔）",
        value=st.session_state.get("ui_custom_options_text", ""),
        height=320,
        key="ui_custom_options_text",
        placeholder="例：\n千与千寻\n星际穿越\n霸王别姬\n盗梦空间",
    )

    options = parse_options_text(st.session_state.get("ui_custom_options_text", ""))
    st.caption(f"当前有效电影：{len(options)} 部（已自动去重、去空行）。")
    st.caption("支持每行一个，也支持用逗号、顿号、分号或竖线一次性粘贴。")

    top_k_enabled = st.checkbox(
        "只保留前 N 名",
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
                "最终保留前 N 名",
                min_value=1,
                max_value=max_top_k,
                value=int(st.session_state.get("ui_custom_top_k", min(10, max_top_k))),
                step=1,
                key="ui_custom_top_k",
            )
        )
    estimate_top_k = custom_top_k if custom_top_k and len(options) >= 2 else None
    st.caption(f"预计需要取舍约 {estimated_comparisons(len(options), estimate_top_k)} 次。")

    personalization = render_personalization_controls("ui_custom")

    with st.expander("生成片单链接", expanded=False):
        st.caption("生成后会保存片单标题和电影列表；未配置 Supabase 时，会退回较长的本地链接。")
        if render_button_compat("生成片单链接", key="btn_create_custom_challenge", use_container_width=True, button_type="primary"):
            if len(options) < 2:
                st.warning("至少需要 2 部电影才能生成片单链接。")
            else:
                challenge = save_challenge(
                    theme=(st.session_state.get("ui_custom_theme", "") or "").strip() or "我的电影审美名单",
                    mode=mode,
                    items=options,
                    top_k=estimate_top_k,
                    seed_text=personalization["seed_text"] or f"custom-{stable_int('||'.join(options)) % 100000}",
                    source="custom_challenge",
                )
                if challenge:
                    st.session_state["ui_custom_challenge_url"] = build_challenge_url(
                        challenge,
                        use_payload_fallback=not analytics_enabled(),
                    )
                    st.session_state["ui_custom_challenge_caption"] = challenge_share_caption(challenge.theme, st.session_state["ui_custom_challenge_url"])
                    st.session_state["ui_custom_challenge_id"] = challenge.id
                    st.success("片单链接已生成。")
        custom_url = st.session_state.get("ui_custom_challenge_url", "")
        if custom_url:
            if render_copy_button("复制片单链接", custom_url, "copy_custom_challenge_url", "片单链接"):
                track_event(
                    EVENT_SHARE_LINK_COPIED,
                    challenge_id=st.session_state.get("ui_custom_challenge_id", ""),
                    mode=mode,
                    source_channel=get_source_channel(),
                    payload={"surface": "custom_setup"},
                )
            st.text_area("分享文案", value=st.session_state.get("ui_custom_challenge_caption", ""), height=120)

    with st.expander("查看当前候选项", expanded=False):
        render_searchable_item_preview(options, "ui_custom_preview_search")

    nav1, nav2, nav3 = st.columns(3)
    with nav1:
        if render_button_compat("返回", key="btn_custom_back_step1", use_container_width=True):
            go_to_step(1)
    with nav2:
        if render_button_compat("清空", key="btn_clear_custom_step2", use_container_width=True):
            clear_ranking_state()
            st.session_state["ui_reset_custom_requested"] = True
            rerun()
    with nav3:
        if render_button_compat("开始整理", key="btn_start_custom_step2", use_container_width=True, button_type="primary"):
            if len(options) < 2:
                st.warning("请至少输入 2 个候选项。")
            else:
                init_ranking_state(
                    mode=mode,
                    theme=(st.session_state.get("ui_custom_theme", "") or "").strip() or "我的名单",
                    options=options,
                    top_k=estimate_top_k,
                    show_poster=True,
                    user_name=personalization["user_name"],
                    seed_text=personalization["seed_text"],
                    blind_mode=personalization["blind_mode"],
                    side_shuffle=personalization["side_shuffle"],
                    challenge_id=st.session_state.get("ui_custom_challenge_id", ""),
                    template_id="",
                    source_channel=get_source_channel(),
                    initial_poster_map=None,
                )
                st.session_state["ui_step"] = 3
                rerun()


def render_douban_parameter_page(mode: str) -> None:
    if st.session_state.pop("ui_reset_douban_requested", False):
        reset_douban_parameter_defaults()

    render_douban_preset_buttons()

    st.text_input("片单标题", value=st.session_state.get("ui_douban_theme", "我的豆瓣电影名单"), key="ui_douban_theme")

    top_k = int(
        st.number_input(
            "最后保留前多少名",
            min_value=1,
            max_value=250,
            value=int(st.session_state.get("ui_douban_top_k", 10)),
            step=1,
            key="ui_douban_top_k",
        )
    )
    pool_n = int(
        st.number_input(
            "从豆瓣前多少部里整理",
            min_value=1,
            max_value=250,
            value=int(st.session_state.get("ui_douban_pool_n", 100)),
            step=1,
            key="ui_douban_pool_n",
            help="比如填 100，就会用豆瓣 Top250 里的前 100 部电影作为候选项。",
        )
    )
    show_poster = st.checkbox(
        "整理时显示电影海报",
        value=bool(st.session_state.get("ui_douban_show_poster", True)),
        key="ui_douban_show_poster",
    )
    personalization = render_personalization_controls("ui_douban")

    if pool_n < top_k:
        st.error("候选范围不能小于 Top 数量。请让候选范围 >= Top。")
    else:
        st.caption(f"将从豆瓣 Top250 中读取前 {pool_n} 部电影，最后生成你的前 {top_k} 名。")
        st.caption(f"预计需要取舍约 {estimated_comparisons(pool_n, top_k)} 次。")

    if render_button_compat("预览候选电影", key="btn_preview_douban_step2", use_container_width=True):
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
        if render_button_compat("返回", key="btn_douban_back_step1", use_container_width=True):
            go_to_step(1)
    with nav2:
        if render_button_compat("清空", key="btn_clear_douban_step2", use_container_width=True):
            clear_ranking_state()
            st.session_state["ui_reset_douban_requested"] = True
            rerun()
    with nav3:
        if render_button_compat("开始整理", key="btn_start_douban_step2", use_container_width=True, button_type="primary"):
            if pool_n < top_k:
                st.warning("请先修正设置：候选范围不能小于 Top 数量。")
            else:
                st.session_state["ui_pending_douban"] = {
                    "mode": mode,
                    "theme": (st.session_state.get("ui_douban_theme", "") or "").strip() or "我的豆瓣电影名单",
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
        "整理这份电影名单",
        "补充标题、电影范围和分享方式。",
    )

    if mode == MODE_CUSTOM:
        render_custom_parameter_page(mode)
    else:
        render_douban_parameter_page(mode)


def render_douban_prepare_page() -> None:
    pending = st.session_state.get("ui_pending_douban")
    st.progress(0.72)
    st.subheader("正在准备片单")
    st.caption("正在读取豆瓣电影和海报。准备完成后会自动进入选择页。")

    if not pending:
        st.warning("没有待准备的豆瓣片单。")
        if render_button_compat("返回设置", key="btn_prepare_back", use_container_width=True):
            go_to_step(2)
        return

    try:
        movies, poster_map = prepare_douban_candidates_ui(
            int(pending["pool_n"]),
            warm_posters=bool(pending["show_poster"]),
        )
        if len(movies) < 2:
            st.error("获取到的电影数量不足 2，无法开始整理。")
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
            challenge_id="",
            template_id="douban-live",
            source_channel=get_source_channel(),
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
        st.caption("① 选片单")
    with labels[1]:
        st.caption("② 定范围")
    with labels[2]:
        st.markdown("**③ 作取舍**")

    if not started:
        st.info("还没有开始。请先回到第 2 步完成设置。")
    else:
        render_right_panel()

    safe_divider()
    nav1, nav2 = st.columns(2)
    with nav1:
        if render_button_compat("返回修改片单", key="btn_back_to_step2", use_container_width=True):
            go_to_step(2)
    with nav2:
        if render_button_compat("重新选择来源", key="btn_back_to_step1", use_container_width=True):
            go_to_step(1)


# =========================
# 主程序
# =========================
def main() -> None:
    st.set_page_config(
        page_title=APP_TITLE,
        page_icon="🎬",
        layout="wide",
    )
    render_app_styles()

    if get_query_param("admin"):
        render_admin_dashboard()
        return

    if "ui_selected_mode" not in st.session_state:
        st.session_state["ui_selected_mode"] = MODE_CUSTOM
    if "ui_step" not in st.session_state:
        st.session_state["ui_step"] = 1

    track_once(
        f"page_view_{get_source_channel()}",
        EVENT_PAGE_VIEW,
        source_channel=get_source_channel(),
        payload={
            "has_list": bool(get_query_param("list") or get_query_param("challenge")),
            "has_payload": bool(get_query_param("payload")),
            "session_hint": get_session_id()[-8:],
        },
    )
    maybe_open_url_challenge()

    step = get_ui_step()
    if step == 3:
        st.caption(APP_TITLE)
    elif step == 1:
        render_cover_header()
    else:
        st.title(APP_TITLE)
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
    if analytics_enabled():
        st.caption("说明：本应用只记录匿名访问、开始、完成和分享事件，不记录姓名、IP 或自定义完整名单内容。")
    else:
        st.caption("说明：未配置 Supabase 时，应用仍可完整使用；公开统计和短链接会自动降级。")


if __name__ == "__main__":
    main()
