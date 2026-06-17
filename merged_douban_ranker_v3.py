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
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import requests
import streamlit as st
import streamlit.components.v1 as components

from analytics import (
    EVENT_LABELS,
    EVENT_CHALLENGE_OPENED,
    EVENT_COMPARISON_MADE,
    EVENT_HOME_CONTENT_RENDERED,
    EVENT_LIST_SELECTED,
    EVENT_PAGE_VIEW,
    EVENT_POSTER_DOWNLOADED,
    EVENT_QR_VIEWED,
    EVENT_RANKING_COMPLETED,
    EVENT_RANKING_STARTED,
    EVENT_RESULT_VIEWED,
    EVENT_SHARE_LINK_COPIED,
    MAIN_FUNNEL_STEPS,
    SHARED_FUNNEL_STEPS,
    available_event_date_range,
    analytics_enabled,
    build_admin_insights,
    build_admin_summary,
    build_channel_metrics,
    build_daily_metrics,
    build_event_table_rows,
    build_experiment_metrics,
    build_current_total_funnel_rows,
    build_funnel_insight,
    build_funnel_instrumentation_summary,
    build_funnel_rows,
    build_group_metrics,
    build_heavy_list_funnel_rows,
    build_home_load_insight,
    build_home_load_metrics,
    build_light_list_funnel_rows,
    build_list_metrics,
    build_numeric_payload_histogram,
    build_payload_value_counts,
    build_setting_rows,
    build_top_k_distribution,
    build_version_metrics,
    fetch_all_events,
    fetch_public_metrics,
    filter_events_by_date,
    get_admin_token,
    get_public_app_url,
    get_session_id,
    supabase_request,
    track_event,
    track_once,
)
from experiments import get_experiment_config, get_experiment_event_context
from challenge_store import (
    Challenge,
    build_challenge_url,
    build_template_url,
    challenge_from_template,
    decode_fallback_payload,
    fetch_challenge,
    save_challenge,
)
from import_store import (
    MEDIA_TYPE_MOVIE,
    MEDIA_TYPE_SERIES,
    MEDIA_TYPE_UNKNOWN,
    clean_media_type,
    build_douban_bookmarklet,
    build_import_url,
    clean_collect_date,
    clean_import_id,
    fetch_imported_movie_list,
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
DOUBAN_COLLECT_URL_TEMPLATE = "https://movie.douban.com/people/{user_id}/collect"
DOUBAN_COLLECT_PAGE_SIZE = 15
DOUBAN_COLLECT_MAX_ITEMS = 1200
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
LOCAL_DRAFT_COMPONENT = components.declare_component(
    "local_draft",
    path=str(Path(__file__).parent / "components" / "local_draft"),
)
BOOKMARKLET_LINK_COMPONENT = components.declare_component(
    "bookmarklet_link",
    path=str(Path(__file__).parent / "components" / "bookmarklet_link"),
)

LOCAL_DRAFT_VERSION = 1
LOCAL_DRAFT_STORAGE_KEY = "film_sort_local_draft_v1"
pd = None
Image = None
ImageDraw = None
ImageFont = None
ImageOps = None
UnidentifiedImageError = None
qrcode = None
BeautifulSoup = None

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/126.0 Safari/537.36"
    ),
    "Referer": "https://movie.douban.com/",
    "Accept": "application/json, text/plain, */*",
}


def ensure_pandas():
    global pd
    if pd is None:
        import pandas as _pd

        pd = _pd
    return pd


def ensure_pillow() -> None:
    global Image, ImageDraw, ImageFont, ImageOps, UnidentifiedImageError
    if Image is not None:
        return
    from PIL import Image as _Image
    from PIL import ImageDraw as _ImageDraw
    from PIL import ImageFont as _ImageFont
    from PIL import ImageOps as _ImageOps
    from PIL import UnidentifiedImageError as _UnidentifiedImageError

    Image = _Image
    ImageDraw = _ImageDraw
    ImageFont = _ImageFont
    ImageOps = _ImageOps
    UnidentifiedImageError = _UnidentifiedImageError


def ensure_qrcode() -> None:
    global qrcode
    if qrcode is None:
        import qrcode as _qrcode

        qrcode = _qrcode


def ensure_beautiful_soup() -> None:
    global BeautifulSoup
    if BeautifulSoup is None:
        from bs4 import BeautifulSoup as _BeautifulSoup

        BeautifulSoup = _BeautifulSoup

# 精确到 IMDb ID 的备用海报源，覆盖内置片单里豆瓣不稳定命中的影片。
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
    "星之声": {"query": "voices_of_a_distant_star", "imdb_id": "tt0370754"},
    "云之彼端，约定的地方": {"query": "the_place_promised_in_our_early_days", "imdb_id": "tt0381348"},
    "秒速5厘米": {"query": "5_centimeters_per_second", "imdb_id": "tt0983213"},
    "追逐繁星的孩子": {"query": "children_who_chase_lost_voices", "imdb_id": "tt1839494"},
    "言叶之庭": {"query": "the_garden_of_words", "imdb_id": "tt2591814"},
    "你的名字。": {"query": "your_name", "imdb_id": "tt5311514"},
    "天气之子": {"query": "weathering_with_you", "imdb_id": "tt9426210"},
    "铃芽之旅": {"query": "suzume", "imdb_id": "tt16428256"},
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
    "旺角卡门": {"query": "as_tears_go_by", "imdb_id": "tt0096461"},
    "阿飞正传": {"query": "days_of_being_wild", "imdb_id": "tt0101258"},
    "重庆森林": {"query": "chungking_express", "imdb_id": "tt0109424"},
    "东邪西毒": {"query": "ashes_of_time", "imdb_id": "tt0109688"},
    "堕落天使": {"query": "fallen_angels", "imdb_id": "tt0112913"},
    "春光乍泄": {"query": "happy_together", "imdb_id": "tt0118845"},
    "2046": {"query": "2046", "imdb_id": "tt0212712"},
    "蓝莓之夜": {"query": "my_blueberry_nights", "imdb_id": "tt0765120"},
    "一代宗师": {"query": "the_grandmaster", "imdb_id": "tt1462900"},
    "芙蓉镇": {"query": "hibiscus_town", "imdb_id": "tt0093206"},
    "我不是药神": {"query": "dying_to_survive", "imdb_id": "tt7362036"},
    "哪吒之魔童降世": {"query": "ne_zha", "imdb_id": "tt10627720"},
    "白雪公主和七个小矮人": {"query": "snow_white_and_the_seven_dwarfs", "imdb_id": "tt0029583"},
    "灰姑娘": {"query": "cinderella", "imdb_id": "tt0042332"},
    "睡美人": {"query": "sleeping_beauty", "imdb_id": "tt0053285"},
    "小美人鱼": {"query": "the_little_mermaid", "imdb_id": "tt0097757"},
    "美女与野兽": {"query": "beauty_and_the_beast", "imdb_id": "tt0101414"},
    "阿拉丁": {"query": "aladdin", "imdb_id": "tt0103639"},
    "狮子王": {"query": "the_lion_king", "imdb_id": "tt0110357"},
    "花木兰": {"query": "mulan", "imdb_id": "tt0120762"},
    "星际宝贝": {"query": "lilo_stitch", "imdb_id": "tt0275847"},
    "公主与青蛙": {"query": "the_princess_and_the_frog", "imdb_id": "tt0780521"},
    "魔发奇缘": {"query": "tangled", "imdb_id": "tt0398286"},
    "无敌破坏王": {"query": "wreck_it_ralph", "imdb_id": "tt1772341"},
    "冰雪奇缘": {"query": "frozen", "imdb_id": "tt2294629"},
    "超能陆战队": {"query": "big_hero_6", "imdb_id": "tt2245084"},
    "疯狂动物城": {"query": "zootopia", "imdb_id": "tt2948356"},
    "海洋奇缘": {"query": "moana", "imdb_id": "tt3521164"},
    "寻龙传说": {"query": "raya_and_the_last_dragon", "imdb_id": "tt5109280"},
    "魔法满屋": {"query": "encanto", "imdb_id": "tt2953050"},
    "海洋奇缘2": {"query": "moana_2", "imdb_id": "tt13622970"},
    "疯狂动物城2": {"query": "zootopia_2", "imdb_id": "tt26443597"},
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
MODE_DOUBAN_COLLECT = "豆瓣已看"

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
SHARE_POSTER_QR_OPTIONS = ["带二维码", "不带二维码"]
DOUBAN_RATING_VALUES = [5, 4, 3, 2, 1]
DOUBAN_COLLECT_MEDIA_FILTERS = [(MEDIA_TYPE_MOVIE, "movie"), (MEDIA_TYPE_SERIES, "tv")]
DOUBAN_COLLECT_MEDIA_TYPES = [MEDIA_TYPE_MOVIE, MEDIA_TYPE_SERIES]
MEDIA_TYPE_LABELS = {
    MEDIA_TYPE_MOVIE: "电影",
    MEDIA_TYPE_SERIES: "剧集",
    MEDIA_TYPE_UNKNOWN: "未识别类型",
}

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
    "decision_log",
    "challenge_id",
    "template_id",
    "source_channel",
]

RANKING_STATE_KEYS = [
    "mode",
    "theme",
    "source_options",
    "source_poster_map",
    "source_poster_url_map",
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
    "decision_log",
    "challenge_id",
    "template_id",
    "source_channel",
    "completion_event_signature",
    "result_view_event_signature",
    "qr_view_event_signature",
    "share_poster_bytes",
    "share_poster_signature",
]

LOCAL_DRAFT_STATE_KEYS = [
    "mode",
    "theme",
    "source_options",
    "source_poster_url_map",
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
    "skipped_items",
    "user_name",
    "seed_text",
    "blind_mode",
    "side_shuffle",
    "defers",
    "decision_log",
    "challenge_id",
    "template_id",
    "source_channel",
    "completion_event_signature",
    "result_view_event_signature",
    "qr_view_event_signature",
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


def render_boot_loading_notice() -> None:
    st.markdown(
        """
        <div style="margin: 0 0 12px; padding: 10px 14px; border: 1px solid #d8dee8; border-radius: 8px; background: #f6f8fb; color: #3f4957; font-size: 14px; font-weight: 700;">
          第一次打开可能需要几秒
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_home_collab_badge() -> None:
    st.markdown(
        '<div class="home-collab-badge">合作：13823698639@163.com</div>',
        unsafe_allow_html=True,
    )


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
    ensure_pillow()
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
    ensure_pillow()
    if not image_data:
        return None
    try:
        img = Image.open(io.BytesIO(image_data))
        return img.convert("RGB")
    except Exception:
        return None


def make_rounded_rect_mask(size: Tuple[int, int], radius: int) -> Image.Image:
    ensure_pillow()
    mask = Image.new("L", size, 0)
    draw = ImageDraw.Draw(mask)
    draw.rounded_rectangle((0, 0, size[0], size[1]), radius=radius, fill=255)
    return mask


def render_poster_thumb(image_data: Optional[bytes], size: Tuple[int, int], bg: Tuple[int, int, int]) -> Image.Image:
    ensure_pillow()
    thumb = Image.new("RGB", size, bg)
    poster = image_from_bytes(image_data)
    if poster:
        poster.thumbnail((size[0], size[1]), Image.Resampling.LANCZOS)
        x = (size[0] - poster.width) // 2
        y = (size[1] - poster.height) // 2
        thumb.paste(poster, (x, y))
    return thumb


def make_qr_image(url: str, size: int = 164) -> Image.Image:
    ensure_pillow()
    ensure_qrcode()
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


def draw_medal_icon(draw: ImageDraw.ImageDraw, x: int, y: int, rank: int, font: ImageFont.ImageFont) -> None:
    colors = {
        1: ((236, 183, 73), (174, 116, 24)),
        2: ((190, 198, 210), (118, 130, 148)),
        3: ((203, 132, 76), (141, 78, 40)),
    }
    fill, outline = colors.get(rank, ((73, 93, 241), (46, 58, 180)))
    cx, cy, radius = x + 22, y + 22, 21
    draw.polygon([(cx - 14, cy + 14), (cx - 3, cy + 42), (cx + 3, cy + 14)], fill=outline)
    draw.polygon([(cx + 14, cy + 14), (cx + 3, cy + 42), (cx - 3, cy + 14)], fill=outline)
    draw.ellipse((cx - radius, cy - radius, cx + radius, cy + radius), fill=fill, outline=outline, width=3)
    label = str(rank)
    bbox = draw.textbbox((0, 0), label, font=font)
    draw.text((cx - (bbox[2] - bbox[0]) / 2, cy - (bbox[3] - bbox[1]) / 2 - 1), label, font=font, fill=(255, 255, 255))


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


def clear_query_param(name: str) -> None:
    try:
        if name in st.query_params:
            del st.query_params[name]
        return
    except Exception:
        pass
    try:
        params = st.experimental_get_query_params()
        params.pop(name, None)
        st.experimental_set_query_params(**params)
    except Exception:
        return


def render_copy_button(label: str, text: str, key: str, placeholder: str = "") -> bool:
    result = COPY_BUTTON_COMPONENT(label=label, text=text, placeholder=placeholder, key=key, default=None)
    if isinstance(result, dict):
        return bool(result.get("copied"))
    return False


def render_bookmarklet_link(label: str, href: str, key: str) -> None:
    BOOKMARKLET_LINK_COMPONENT(label=label, href=href, key=key, default=None)


def get_source_channel() -> str:
    channel = get_query_param("source") or get_query_param("utm_source") or get_query_param("src") or "direct / unknown"
    return channel[:80]


def get_attribution_params() -> Dict[str, str]:
    source = get_source_channel()
    return {
        "source": source,
        "utm_source": (get_query_param("utm_source") or source)[:80],
        "utm_medium": (get_query_param("utm_medium") or "unknown")[:80],
        "utm_campaign": (get_query_param("utm_campaign") or "unknown")[:120],
    }


def current_experiment_assignment() -> Dict[str, Any]:
    return get_experiment_event_context(get_session_id())


def build_event_payload(**payload: Any) -> Dict[str, Any]:
    merged: Dict[str, Any] = {
        "page": payload.pop("page", "app"),
        "route": payload.pop("route", f"step_{st.session_state.get('ui_step', 1)}"),
    }
    merged.update(get_attribution_params())
    experiment_context = current_experiment_assignment()
    if experiment_context:
        merged.update(experiment_context)
    merged.update({key: value for key, value in payload.items() if value is not None})
    return merged


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
            border-color: #2b2f36 !important;
            background: #2b2f36 !important;
            color: #fffaf4 !important;
        }
        div[data-testid="stButton"] > button[kind="primary"] *,
        div[data-testid="stButton"] > button[data-testid="baseButton-primary"] * {
            color: #fffaf4 !important;
        }
        div[data-testid="stButton"] > button[kind="primary"]:hover,
        div[data-testid="stButton"] > button[data-testid="baseButton-primary"]:hover {
            border-color: #171a1f !important;
            background: #171a1f !important;
            color: #fffaf4 !important;
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
            grid-template-columns: minmax(0, 1fr) minmax(310px, 0.72fr);
            gap: 22px;
            align-items: stretch;
            margin-bottom: 10px;
            padding: 28px;
            min-height: 330px;
            border: 1px solid #2f3540;
            border-radius: 8px;
            background-color: #232832;
            background-position: center;
            background-size: cover;
            overflow: hidden;
        }
        .hero-copy {
            min-width: 0;
            display: flex;
            flex-direction: column;
            justify-content: center;
        }
        .launch-hero .hero-kicker {
            color: #ffd19a;
            font-size: 12px;
            font-weight: 850;
            letter-spacing: 0;
            margin-bottom: 6px;
        }
        .launch-hero .hero-title {
            color: #fffaf4;
            font-size: clamp(32px, 4vw, 50px);
            font-weight: 880;
            letter-spacing: 0;
            line-height: 1.02;
            margin: 0 0 8px;
            text-shadow: 0 1px 18px rgba(0, 0, 0, 0.28);
        }
        .launch-hero .hero-subtitle {
            color: #f5e9dd;
            font-size: 16px;
            line-height: 1.5;
            margin: 0;
            max-width: 620px;
        }
        .hero-outcomes {
            display: flex;
            flex-wrap: wrap;
            gap: 8px;
            margin-top: 18px;
            max-width: 660px;
        }
        .hero-outcome {
            border: 1px solid rgba(255, 250, 244, 0.28);
            border-radius: 999px;
            background: rgba(255, 250, 244, 0.13);
            color: #fffaf4;
            padding: 7px 10px;
            font-size: 12px;
            font-weight: 780;
            line-height: 1.2;
            backdrop-filter: blur(5px);
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
            border: 1px solid rgba(255, 250, 244, 0.45);
            border-radius: 8px;
            background: rgba(255, 253, 249, 0.88);
            padding: 14px;
            box-shadow: 0 18px 50px rgba(20, 24, 30, 0.18);
            backdrop-filter: blur(8px);
            align-self: center;
        }
        .example-title {
            color: #1f2328;
            font-size: 18px;
            font-weight: 900;
            line-height: 1.25;
            margin-bottom: 8px;
        }
        .example-eyebrow {
            color: #1f6f6a;
            font-size: 12px;
            font-weight: 850;
            line-height: 1.2;
            margin-bottom: 5px;
        }
        .example-champion {
            border: 1px solid #dcebe6;
            border-radius: 8px;
            background: #f6fffb;
            padding: 9px 10px;
            margin-bottom: 8px;
        }
        .example-champion-label {
            color: #52706c;
            font-size: 11px;
            font-weight: 780;
            line-height: 1.2;
        }
        .example-champion-name {
            color: #163f3c;
            font-size: 20px;
            font-weight: 900;
            line-height: 1.25;
            margin-top: 2px;
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
        .example-footer {
            display: grid;
            grid-template-columns: repeat(2, minmax(0, 1fr));
            gap: 7px;
            margin-top: 10px;
        }
        .example-result-chip {
            border: 1px solid #e7e1d8;
            border-radius: 8px;
            color: #4b4640;
            background: #fffaf4;
            padding: 7px 8px;
            font-size: 12px;
            font-weight: 760;
            line-height: 1.25;
            text-align: center;
        }
        .challenge-grid {
            display: grid;
            grid-template-columns: repeat(3, minmax(0, 1fr));
            gap: 10px;
            margin: 10px 0 8px;
        }
        .challenge-card {
            border: 1px solid #e7e1d8;
            border-radius: 8px;
            background: #fffdf9;
            padding: 13px;
            min-height: 188px;
            display: flex;
            flex-direction: column;
            justify-content: space-between;
            color: inherit;
            text-decoration: none !important;
            transition: border-color 120ms ease, box-shadow 120ms ease, transform 120ms ease;
        }
        .challenge-card:hover {
            border-color: #9b6a58;
            box-shadow: 0 0 0 3px rgba(155, 106, 88, 0.10);
            transform: translateY(-1px);
            text-decoration: none !important;
        }
        .collect-spotlight {
            border: 1px solid #dccfc2;
            border-radius: 8px;
            background: linear-gradient(135deg, #fffdf9 0%, #fff5ec 100%);
            padding: 16px 18px;
            margin: 6px 0 10px;
            display: grid;
            grid-template-columns: minmax(0, 1fr) auto;
            gap: 14px;
            align-items: center;
        }
        .collect-spotlight-kicker {
            color: #8a4f3d;
            font-size: 12px;
            font-weight: 850;
            line-height: 1.25;
            margin-bottom: 5px;
        }
        .collect-spotlight-title {
            color: #1f2328;
            font-size: 24px;
            font-weight: 900;
            line-height: 1.18;
            margin-bottom: 6px;
        }
        .collect-spotlight-copy {
            color: #5f574f;
            font-size: 14px;
            line-height: 1.45;
            max-width: 760px;
        }
        .collect-spotlight-note {
            border: 1px solid #ead9cc;
            border-radius: 8px;
            background: rgba(255, 255, 255, 0.72);
            color: #6f665d;
            padding: 9px 10px;
            font-size: 12px;
            font-weight: 720;
            line-height: 1.35;
            min-width: 132px;
            text-align: center;
        }
        .bookmarklet-link {
            display: inline-flex;
            align-items: center;
            justify-content: center;
            min-height: 38px;
            padding: 0 14px;
            border: 1px solid #9b6a58;
            border-radius: 8px;
            background: #fffaf4;
            color: #8a4f3d !important;
            font-weight: 850;
            text-decoration: none !important;
        }
        .bookmarklet-link:hover {
            background: #fff1e4;
            text-decoration: none !important;
        }
        .import-helper {
            border: 1px solid #e7e1d8;
            border-radius: 8px;
            background: #fffdf9;
            padding: 12px;
            margin: 6px 0 10px;
        }
        .import-helper-title {
            color: #1f2328;
            font-size: 15px;
            font-weight: 850;
            margin-bottom: 4px;
        }
        .import-helper-copy {
            color: #6f665d;
            font-size: 13px;
            line-height: 1.45;
        }
        .import-step-list {
            margin: 8px 0;
            padding-left: 18px;
            color: #3c3935;
            font-size: 13px;
            line-height: 1.55;
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
        .challenge-reason {
            border-left: 3px solid #1f6f6a;
            color: #334340;
            background: #f6fffb;
            padding: 8px 9px;
            margin-top: 10px;
            font-size: 12px;
            font-weight: 700;
            line-height: 1.42;
        }
        .challenge-reason-label {
            color: #1f6f6a;
            font-size: 11px;
            font-weight: 850;
            line-height: 1.2;
            margin-bottom: 2px;
        }
        .challenge-foot {
            display: flex;
            flex-direction: column;
            gap: 8px;
            margin-top: 10px;
        }
        .challenge-action {
            display: block;
            width: 100%;
            border-radius: 6px;
            background: #2b2f36;
            color: #fffaf4 !important;
            font-size: 13px;
            font-weight: 760;
            line-height: 1;
            text-align: center;
            padding: 11px 10px;
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
        .home-collab-badge {
            position: fixed;
            top: 58px;
            right: 18px;
            z-index: 60;
            padding: 4px 8px;
            border: 1px solid rgba(31, 35, 40, 0.10);
            border-radius: 6px;
            background: rgba(255, 255, 255, 0.62);
            color: rgba(31, 35, 40, 0.62);
            font-size: 12px;
            line-height: 1.2;
            font-weight: 650;
            pointer-events: none;
            backdrop-filter: blur(6px);
        }
        .peer-match-panel {
            border: 1px solid #dbe7e3;
            border-radius: 8px;
            background: #f7fbf9;
            padding: 14px;
            margin: 12px 0;
        }
        .peer-match-title {
            color: #1f3f3b;
            font-size: 16px;
            font-weight: 850;
            margin-bottom: 5px;
        }
        .peer-match-copy {
            color: #586760;
            font-size: 13px;
            line-height: 1.5;
            margin-bottom: 10px;
        }
        .peer-side-section {
            margin-top: 18px;
        }
        .peer-section-heading {
            color: #1f2328;
            font-size: 17px;
            font-weight: 900;
            line-height: 1.25;
            margin-bottom: 5px;
        }
        .peer-section-copy {
            color: #6f665d;
            font-size: 12px;
            line-height: 1.45;
            margin-bottom: 8px;
        }
        .peer-card-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
            gap: 10px;
            margin-top: 10px;
        }
        .peer-card-list {
            display: grid;
            grid-template-columns: 1fr;
            gap: 8px;
            margin: 8px 0 12px;
        }
        .peer-card {
            border: 1px solid #dbe7e3;
            border-radius: 8px;
            background: #fff;
            padding: 12px;
            min-width: 0;
        }
        .peer-card-label {
            color: #6b7a73;
            font-size: 12px;
            font-weight: 750;
            margin-bottom: 5px;
        }
        .peer-contact {
            color: #1f2328;
            font-size: 15px;
            font-weight: 850;
            overflow-wrap: anywhere;
            margin-bottom: 7px;
        }
        .peer-shared {
            color: #56625d;
            font-size: 13px;
            line-height: 1.45;
            overflow-wrap: anywhere;
        }
        .peer-empty-note {
            color: #7a6f66;
            font-size: 12px;
            line-height: 1.45;
            border: 1px dashed #d8d1c6;
            border-radius: 8px;
            padding: 10px 12px;
            margin: 8px 0 12px;
        }
        .result-peak {
            border: 1px solid #d8d1c6;
            border-radius: 8px;
            background:
                linear-gradient(135deg, rgba(31, 35, 40, 0.94) 0%, rgba(72, 54, 45, 0.90) 54%, rgba(31, 111, 106, 0.84) 100%);
            padding: 20px;
            color: #fffaf4;
            margin: 4px 0 14px;
        }
        .result-peak-kicker {
            color: #ffd19a;
            font-size: 12px;
            font-weight: 850;
            line-height: 1.2;
            margin-bottom: 8px;
        }
        .result-peak-title {
            color: #fffaf4;
            font-size: clamp(28px, 3.6vw, 48px);
            font-weight: 900;
            line-height: 1.04;
            letter-spacing: 0;
            margin-bottom: 16px;
            overflow-wrap: anywhere;
        }
        .result-peak-grid {
            display: grid;
            grid-template-columns: minmax(0, 1.05fr) minmax(260px, 0.95fr);
            gap: 12px;
        }
        .result-peak-panel {
            border: 1px solid rgba(255, 250, 244, 0.22);
            border-radius: 8px;
            background: rgba(255, 250, 244, 0.10);
            padding: 13px;
            min-width: 0;
        }
        .result-peak-label {
            color: rgba(255, 250, 244, 0.76);
            font-size: 12px;
            font-weight: 780;
            line-height: 1.25;
            margin-bottom: 5px;
        }
        .result-peak-value {
            color: #fffaf4;
            font-size: 24px;
            font-weight: 900;
            line-height: 1.2;
            overflow-wrap: anywhere;
        }
        .contest-pair {
            display: grid;
            grid-template-columns: minmax(0, 1fr) auto minmax(0, 1fr);
            gap: 8px;
            align-items: center;
            margin-top: 6px;
        }
        .contest-item {
            border: 1px solid rgba(255, 250, 244, 0.24);
            border-radius: 8px;
            background: rgba(255, 250, 244, 0.12);
            padding: 9px;
            color: #fffaf4;
            font-weight: 820;
            line-height: 1.25;
            text-align: center;
            overflow-wrap: anywhere;
        }
        .contest-versus {
            color: #ffd19a;
            font-size: 12px;
            font-weight: 900;
        }
        .result-peak-note {
            color: rgba(255, 250, 244, 0.78);
            font-size: 12px;
            line-height: 1.42;
            margin-top: 8px;
        }
        .poster-stage {
            display: grid;
            grid-template-columns: minmax(280px, 0.9fr) minmax(0, 1.1fr);
            gap: 16px;
            align-items: start;
            margin: 12px 0 14px;
        }
        .poster-preview-shell {
            border: 1px solid #e7e1d8;
            border-radius: 8px;
            background: #fffdf9;
            padding: 10px;
        }
        .poster-side-panel {
            border: 1px solid #e7e1d8;
            border-radius: 8px;
            background: #fffdf9;
            padding: 14px;
        }
        .poster-panel-title {
            color: #1f2328;
            font-size: 18px;
            font-weight: 900;
            line-height: 1.25;
            margin-bottom: 6px;
        }
        .poster-panel-copy {
            color: #6f665d;
            font-size: 13px;
            line-height: 1.45;
            margin-bottom: 12px;
        }
        .share-action-grid {
            display: grid;
            grid-template-columns: repeat(2, minmax(0, 1fr));
            gap: 8px;
            margin: 10px 0 12px;
        }
        .challenge-invite {
            border-left: 3px solid #1f6f6a;
            background: transparent;
            color: #163f3c;
            padding: 4px 0 4px 12px;
            margin-top: 10px;
        }
        .challenge-invite-title {
            font-size: 15px;
            font-weight: 900;
            line-height: 1.25;
            margin-bottom: 4px;
        }
        .challenge-invite-copy {
            color: #52706c;
            font-size: 12px;
            line-height: 1.45;
        }
        .next-template-grid {
            display: grid;
            grid-template-columns: repeat(3, minmax(0, 1fr));
            gap: 10px;
            margin: 10px 0 12px;
        }
        .next-template-card {
            border: 1px solid #e7e1d8;
            border-radius: 8px;
            background: #fffdf9;
            color: inherit;
            display: block;
            min-height: 132px;
            padding: 12px;
            text-decoration: none !important;
            transition: border-color 120ms ease, box-shadow 120ms ease, transform 120ms ease;
        }
        .next-template-card:hover {
            border-color: #1f6f6a;
            box-shadow: 0 0 0 3px rgba(31, 111, 106, 0.10);
            transform: translateY(-1px);
            text-decoration: none !important;
        }
        .next-template-label {
            color: #1f6f6a;
            font-size: 11px;
            font-weight: 850;
            line-height: 1.2;
            margin-bottom: 6px;
        }
        .next-template-title {
            color: #1f2328;
            font-size: 15px;
            font-weight: 860;
            line-height: 1.25;
            margin-bottom: 5px;
        }
        .next-template-copy {
            color: #6f665d;
            font-size: 12px;
            line-height: 1.4;
        }
        .mini-note {
            color: #7a746c;
            font-size: 13px;
            line-height: 1.35;
        }
        .home-step-copy {
            color: #7a746c;
            font-size: 15px;
            line-height: 1.45;
            margin: 6px 0 6px;
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
            .result-peak-grid,
            .poster-stage,
            .next-template-grid {
                grid-template-columns: 1fr;
            }
            .share-action-grid {
                grid-template-columns: 1fr;
            }
            .launch-hero {
                grid-template-columns: 1fr;
                min-height: 0;
                padding: 18px;
            }
            .collect-spotlight {
                grid-template-columns: 1fr;
                padding: 12px;
                gap: 8px;
            }
            .collect-spotlight-title {
                font-size: 20px;
            }
            .collect-spotlight-note {
                text-align: left;
                min-width: 0;
            }
            .challenge-grid {
                grid-template-columns: 1fr;
            }
            .home-collab-badge {
                top: 50px;
                right: 10px;
                font-size: 11px;
                max-width: calc(100vw - 20px);
            }
            .peer-card-grid {
                grid-template-columns: 1fr;
            }
            .hero-proof {
                grid-template-columns: repeat(3, minmax(0, 1fr));
            }
            .hero-outcomes {
                display: grid;
                grid-template-columns: 1fr;
            }
            .example-footer {
                grid-template-columns: 1fr;
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
    ensure_beautiful_soup()
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


def normalize_douban_user_id(raw_value: str) -> str:
    value = (raw_value or "").strip()
    if not value:
        return ""

    match = re.search(r"douban\.com/people/([^/?#]+)/?", value)
    if match:
        value = match.group(1)

    value = value.strip().strip("/")
    if not re.fullmatch(r"[A-Za-z0-9_-]{2,64}", value):
        return ""
    return value


def collect_entry_title(item, seen: Dict[str, int]) -> str:
    title_el = item.select_one("li.title a")
    em_el = title_el.select_one("em") if title_el else None
    img_el = item.select_one("div.pic img")

    raw_title = ""
    if em_el:
        raw_title = em_el.get_text(" ", strip=True)
    elif title_el:
        raw_title = title_el.get_text(" ", strip=True)
    elif img_el:
        raw_title = img_el.get("alt", "").strip()

    primary_title = re.split(r"\s*/\s*", raw_title)[0].strip()
    title = primary_title or raw_title.strip()
    if not title:
        return ""

    intro_text = item.select_one("li.intro")
    intro = intro_text.get_text(" ", strip=True) if intro_text else ""
    year_match = re.search(r"(?:19|20)\d{2}", intro)
    year = year_match.group(0) if year_match else ""

    count = seen.get(title, 0)
    seen[title] = count + 1
    if count == 0:
        return title
    if year:
        candidate = f"{title}（{year}）"
        if candidate not in seen:
            seen[candidate] = 1
            return candidate
    return f"{title} #{count + 1}"


def collect_entry_subject_id(item) -> str:
    link_el = item.select_one("li.title a") or item.select_one("a.nbgnbg")
    href = link_el.get("href", "") if link_el else ""
    match = re.search(r"/subject/(\d+)", href)
    return match.group(1) if match else ""


def collect_entry_rating(item) -> Optional[int]:
    rating_el = item.select_one('span[class*="rating"]')
    if not rating_el:
        return None
    class_text = " ".join(rating_el.get("class", []))
    match = re.search(r"rating([1-5])-t", class_text)
    if not match:
        return None
    return int(match.group(1))


def collect_entry_rated_at(item) -> Optional[str]:
    date_el = item.select_one(".date")
    if date_el:
        rated_at = clean_collect_date(date_el.get_text(" ", strip=True))
        if rated_at:
            return rated_at
    return clean_collect_date(item.get_text(" ", strip=True))


def sort_collect_entries_by_recency(entries: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    indexed = list(enumerate(entries))
    indexed.sort(key=lambda pair: (str(pair[1].get("rated_at") or ""), -pair[0]), reverse=True)
    return [entry for _, entry in indexed]


@st.cache_data(show_spinner=False)
def fetch_douban_collect_entries(user_id: str, max_items: int = DOUBAN_COLLECT_MAX_ITEMS) -> List[Dict[str, Any]]:
    ensure_beautiful_soup()
    clean_user_id = normalize_douban_user_id(user_id)
    if not clean_user_id:
        raise ValueError("豆瓣 ID 格式不正确。")

    max_items = max(DOUBAN_COLLECT_PAGE_SIZE, min(DOUBAN_COLLECT_MAX_ITEMS, int(max_items)))
    entries: List[Dict[str, Any]] = []
    seen_titles: Dict[str, int] = {}
    seen_keys = set()

    for media_type, douban_type in DOUBAN_COLLECT_MEDIA_FILTERS:
        for start in range(0, max_items, DOUBAN_COLLECT_PAGE_SIZE):
            resp = requests.get(
                DOUBAN_COLLECT_URL_TEMPLATE.format(user_id=clean_user_id),
                params={
                    "start": start,
                    "sort": "time",
                    "type": douban_type,
                    "filter": "all",
                    "mode": "grid",
                },
                headers=HEADERS,
                timeout=15,
            )
            resp.raise_for_status()

            soup = BeautifulSoup(resp.text, "html.parser")
            items = soup.select("div.item.comment-item, div.item")
            if not items:
                break

            before_count = len(entries)
            for item in items:
                title = collect_entry_title(item, seen_titles)
                if not title:
                    continue

                subject_id = collect_entry_subject_id(item)
                dedupe_key = f"id:{subject_id}" if subject_id else f"title:{media_type}:{title}"
                if dedupe_key in seen_keys:
                    continue
                seen_keys.add(dedupe_key)

                img_el = item.select_one("div.pic img")
                poster_url = img_el.get("src") or img_el.get("data-src") if img_el else None
                entry: Dict[str, Any] = {
                    "title": title,
                    "poster_url": poster_url,
                    "rating": collect_entry_rating(item),
                    "rated_at": collect_entry_rated_at(item),
                    "media_type": media_type,
                }
                if subject_id:
                    entry["subject_id"] = subject_id
                entries.append(entry)

            if len(entries) == before_count:
                break
            next_link = soup.select_one("span.next a, .paginator .next a")
            if not next_link:
                break

    if not entries:
        raise ValueError("没有读取到公开的“看过”条目。请确认豆瓣主页公开，且链接是 /people/你的ID/collect。")
    return sort_collect_entries_by_recency(entries)[:max_items]


def normalize_collect_entries(entries: List[Any]) -> List[Dict[str, Any]]:
    normalized: List[Dict[str, Any]] = []
    seen = set()
    for entry in entries:
        if not isinstance(entry, dict):
            title = str(entry or "").strip()
            poster_url = ""
            subject_id = ""
            rating = None
            rated_at = None
            media_type = MEDIA_TYPE_UNKNOWN
            has_rating_key = False
            has_rated_at_key = False
            has_media_type_key = False
        else:
            title = str(entry.get("title") or "").strip()
            poster_url = str(entry.get("poster_url") or entry.get("poster") or "").strip()
            subject_id = str(entry.get("subject_id") or entry.get("subject") or "").strip()
            has_rating_key = "rating" in entry
            has_rated_at_key = "rated_at" in entry or "collect_date" in entry or "date" in entry
            has_media_type_key = "media_type" in entry or "type" in entry or "category" in entry
            try:
                rating = int(entry.get("rating")) if entry.get("rating") is not None else None
            except (TypeError, ValueError):
                rating = None
            if rating not in DOUBAN_RATING_VALUES:
                rating = None
            rated_at = clean_collect_date(entry.get("rated_at") or entry.get("collect_date") or entry.get("date"))
            media_type = clean_media_type(entry.get("media_type") or entry.get("type") or entry.get("category"))
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
    return normalized


def collect_entries_have_rating_data(entries: List[Dict[str, Any]]) -> bool:
    return any(isinstance(entry, dict) and "rating" in entry for entry in entries)


def collect_entries_have_year_data(entries: List[Dict[str, Any]]) -> bool:
    return any(isinstance(entry, dict) and "rated_at" in entry for entry in entries)


def collect_entries_have_media_type_data(entries: List[Dict[str, Any]]) -> bool:
    return any(isinstance(entry, dict) and "media_type" in entry for entry in entries)


def collect_media_type_counts(entries: List[Dict[str, Any]]) -> Dict[str, int]:
    counts: Dict[str, int] = {MEDIA_TYPE_MOVIE: 0, MEDIA_TYPE_SERIES: 0, MEDIA_TYPE_UNKNOWN: 0}
    for entry in entries:
        media_type = clean_media_type(entry.get("media_type") if isinstance(entry, dict) else None)
        counts[media_type] = counts.get(media_type, 0) + 1
    return counts


def collect_rating_counts(entries: List[Dict[str, Any]]) -> Dict[Optional[int], int]:
    counts: Dict[Optional[int], int] = {rating: 0 for rating in DOUBAN_RATING_VALUES}
    counts[None] = 0
    for entry in entries:
        rating = entry.get("rating") if isinstance(entry, dict) else None
        if rating in DOUBAN_RATING_VALUES:
            counts[int(rating)] = counts.get(int(rating), 0) + 1
        else:
            counts[None] = counts.get(None, 0) + 1
    return counts


def collect_year_counts(entries: List[Dict[str, Any]]) -> Dict[Optional[int], int]:
    counts: Dict[Optional[int], int] = {None: 0}
    for entry in entries:
        rated_at = clean_collect_date(entry.get("rated_at") if isinstance(entry, dict) else None)
        if rated_at:
            year = int(rated_at[:4])
            counts[year] = counts.get(year, 0) + 1
        else:
            counts[None] = counts.get(None, 0) + 1
    return dict(sorted(counts.items(), key=lambda item: -1 if item[0] is None else -int(item[0])))


def filter_collect_entries_by_media_type(
    entries: List[Dict[str, Any]],
    selected_media_types: List[str],
    include_unknown_media_type: bool,
) -> List[Dict[str, Any]]:
    clean_types = {clean_media_type(media_type) for media_type in selected_media_types}
    clean_types.discard(MEDIA_TYPE_UNKNOWN)
    if not clean_types and not include_unknown_media_type:
        return []
    filtered: List[Dict[str, Any]] = []
    for entry in entries:
        media_type = clean_media_type(entry.get("media_type") if isinstance(entry, dict) else None)
        if media_type in clean_types or (media_type == MEDIA_TYPE_UNKNOWN and include_unknown_media_type):
            filtered.append(entry)
    return filtered


def filter_collect_entries_by_rating(
    entries: List[Dict[str, Any]],
    selected_ratings: List[int],
    include_unrated: bool,
) -> List[Dict[str, Any]]:
    clean_ratings = set()
    for rating in selected_ratings:
        try:
            rating_int = int(rating)
        except (TypeError, ValueError):
            continue
        if rating_int in DOUBAN_RATING_VALUES:
            clean_ratings.add(rating_int)
    if not clean_ratings and not include_unrated:
        return []
    filtered: List[Dict[str, Any]] = []
    for entry in entries:
        rating = entry.get("rating") if isinstance(entry, dict) else None
        if rating in clean_ratings or (rating not in DOUBAN_RATING_VALUES and include_unrated):
            filtered.append(entry)
    return filtered


def filter_collect_entries_by_year(
    entries: List[Dict[str, Any]],
    selected_years: List[int],
    include_unknown_year: bool,
) -> List[Dict[str, Any]]:
    clean_years = set()
    for year in selected_years:
        try:
            year_int = int(year)
        except (TypeError, ValueError):
            continue
        if 1900 <= year_int <= 2100:
            clean_years.add(year_int)
    if not clean_years and not include_unknown_year:
        return []
    filtered: List[Dict[str, Any]] = []
    for entry in entries:
        rated_at = clean_collect_date(entry.get("rated_at") if isinstance(entry, dict) else None)
        year = int(rated_at[:4]) if rated_at else None
        if year in clean_years or (year is None and include_unknown_year):
            filtered.append(entry)
    return filtered


def filter_collect_entries(
    entries: List[Dict[str, Any]],
    selected_media_types: List[str],
    include_unknown_media_type: bool,
    selected_ratings: List[int],
    include_unrated: bool,
    selected_years: Optional[List[int]] = None,
    include_unknown_year: bool = True,
) -> List[Dict[str, Any]]:
    filtered = filter_collect_entries_by_media_type(entries, selected_media_types, include_unknown_media_type)
    filtered = filter_collect_entries_by_rating(filtered, selected_ratings, include_unrated)
    if selected_years is None:
        return filtered
    return filter_collect_entries_by_year(filtered, selected_years, include_unknown_year)


def normalize_image_bytes(image_bytes: bytes) -> Optional[bytes]:
    ensure_pillow()
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


def get_source_poster_url(title: str) -> str:
    poster_url_map = st.session_state.get(k("source_poster_url_map"), {})
    if isinstance(poster_url_map, dict):
        return str(poster_url_map.get(title) or "")
    return ""


def prefetch_poster_to_cache(title: str, primary_url: str = "") -> None:
    try:
        get_best_poster_bytes(title, primary_url)
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
        executor.submit(prefetch_poster_to_cache, clean_title, get_source_poster_url(clean_title))
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


def prepare_douban_collect_candidates_ui(
    user_id: str,
    warm_posters: bool,
    max_items: int = DOUBAN_COLLECT_MAX_ITEMS,
    selected_media_types: Optional[List[str]] = None,
    include_unknown_media_type: bool = True,
    selected_ratings: Optional[List[int]] = None,
    include_unrated: bool = True,
    selected_years: Optional[List[int]] = None,
    include_unknown_year: bool = True,
    imported_entries: Optional[List[Dict[str, Any]]] = None,
) -> tuple[List[str], Dict[str, Optional[bytes]], Dict[str, str]]:
    text_holder = st.empty()
    progress_holder = st.empty()
    text_holder.caption("正在读取豆瓣看过列表...")
    bar = progress_holder.progress(8)

    if imported_entries is not None:
        entries = normalize_collect_entries(imported_entries)
        text_holder.caption("正在读取已导入片单...")
    else:
        entries = fetch_douban_collect_entries(user_id, max_items)
    active_media_types = DOUBAN_COLLECT_MEDIA_TYPES if selected_media_types is None else selected_media_types
    active_ratings = DOUBAN_RATING_VALUES if selected_ratings is None else selected_ratings
    entries = filter_collect_entries(
        entries,
        active_media_types,
        include_unknown_media_type,
        active_ratings,
        include_unrated,
        selected_years,
        include_unknown_year,
    )
    movies = [entry["title"] for entry in entries if entry.get("title")]
    poster_url_map = {
        str(entry["title"]): str(entry.get("poster_url") or "")
        for entry in entries
        if entry.get("title") and entry.get("poster_url")
    }

    if not movies:
        bar.progress(100)
        return [], {}, {}

    poster_map: Dict[str, Optional[bytes]] = {}
    if warm_posters:
        warm_entries = entries[: min(12, len(entries))]
        total_steps = max(1, len(warm_entries))
        text_holder.caption("正在预热前几张海报...")
        for idx, entry in enumerate(warm_entries, 1):
            title = entry.get("title")
            if not title:
                continue
            poster_bytes = get_best_poster_bytes(title, entry.get("poster_url") or "")
            poster_map[title] = poster_bytes
            bar.progress(35 + int(idx / total_steps * 60))
    else:
        bar.progress(95)

    bar.progress(100)
    text_holder.caption(f"已读取 {len(movies)} 个看过的条目。")
    return movies, poster_map, poster_url_map


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
    initial_poster_url_map: Optional[Dict[str, str]] = None,
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
    poster_url_map = dict(initial_poster_url_map or {})

    st.session_state[k("mode")] = mode
    st.session_state[k("theme")] = theme
    st.session_state[k("source_options")] = options[:]
    st.session_state[k("source_poster_map")] = poster_map.copy()
    st.session_state[k("source_poster_url_map")] = poster_url_map.copy()
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
    st.session_state[k("decision_log")] = []
    st.session_state[k("challenge_id")] = challenge_id
    st.session_state[k("template_id")] = template_id
    st.session_state[k("source_channel")] = source_channel or get_source_channel()
    st.session_state[k("completion_event_signature")] = ""
    st.session_state[k("result_view_event_signature")] = ""
    st.session_state[k("qr_view_event_signature")] = ""
    st.session_state[k("share_poster_bytes")] = b""
    st.session_state[k("share_poster_signature")] = ""

    safe_source = "custom" if not template_id and not challenge_id else "shared"
    track_event(
        EVENT_RANKING_STARTED,
        challenge_id=challenge_id,
        mode=mode,
        template_id=template_id,
        source_channel=source_channel or get_source_channel(),
        payload=build_event_payload(
            route="sorting",
            list_id=challenge_id or template_id or mode,
            list_size=len(opts),
            total=len(opts),
            top_k=top_k,
            has_seed=bool(clean_seed),
            blind_mode=blind_mode,
            side_shuffle=side_shuffle,
            list_source=safe_source,
            session_hint=get_session_id()[-8:],
        ),
    )


def clear_ranking_state() -> None:
    for name in RANKING_STATE_KEYS:
        st.session_state.pop(k(name), None)
    st.session_state["local_draft_clear_requested"] = True
    st.session_state["local_draft_last_signature"] = ""


def has_incoming_ranking_url() -> bool:
    return bool(
        get_query_param("challenge")
        or get_query_param("payload")
        or get_query_param("list")
        or get_query_param("template")
        or get_query_param("import")
    )


def json_safe_copy(value):
    if isinstance(value, dict):
        safe = {}
        for key, item in value.items():
            if isinstance(key, str):
                safe[key] = json_safe_copy(item)
        return safe
    if isinstance(value, list):
        return [json_safe_copy(item) for item in value]
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return None


def build_local_draft_payload() -> Optional[dict]:
    if not st.session_state.get(k("started"), False):
        return None

    state: dict = {}
    for name in LOCAL_DRAFT_STATE_KEYS:
        state[name] = json_safe_copy(st.session_state.get(k(name)))

    if not state.get("source_options") or not state.get("ranked"):
        return None

    state["source_poster_map"] = {}
    state["poster_map"] = {}
    state["poster_fetch_failed"] = []
    state["poster_prefetch_scheduled"] = []
    state["history"] = []
    state["share_poster_bytes"] = ""
    state["share_poster_signature"] = ""

    return {
        "version": LOCAL_DRAFT_VERSION,
        "updated_at": datetime.utcnow().isoformat(timespec="seconds") + "Z",
        "state": state,
        "ui": {"step": 3},
    }


def restore_local_draft_payload(draft: dict) -> bool:
    if not isinstance(draft, dict) or draft.get("version") != LOCAL_DRAFT_VERSION:
        return False
    state = draft.get("state")
    if not isinstance(state, dict) or not state.get("started"):
        return False
    if not isinstance(state.get("source_options"), list) or not isinstance(state.get("ranked"), list):
        return False

    clear_ranking_state()
    st.session_state.pop("local_draft_clear_requested", None)

    for name in LOCAL_DRAFT_STATE_KEYS:
        st.session_state[k(name)] = json_safe_copy(state.get(name))

    st.session_state[k("source_poster_map")] = {}
    st.session_state[k("poster_map")] = {}
    st.session_state[k("poster_fetch_failed")] = []
    st.session_state[k("poster_prefetch_scheduled")] = []
    st.session_state[k("history")] = []
    st.session_state[k("share_poster_bytes")] = b""
    st.session_state[k("share_poster_signature")] = ""
    st.session_state["ui_step"] = 3
    st.session_state["local_draft_restored"] = True
    return True


def sync_local_draft() -> None:
    if st.session_state.pop("local_draft_clear_requested", False):
        LOCAL_DRAFT_COMPONENT(
            action="clear",
            storage_key=LOCAL_DRAFT_STORAGE_KEY,
            key="local_draft_clear",
            default=None,
        )
        return

    if not st.session_state.get("local_draft_checked", False):
        result = LOCAL_DRAFT_COMPONENT(
            action="load",
            storage_key=LOCAL_DRAFT_STORAGE_KEY,
            key="local_draft_load",
            default=None,
        )
        if isinstance(result, dict) and result.get("status") == "loaded":
            st.session_state["local_draft_checked"] = True
            draft = result.get("draft")
            if (
                draft
                and not st.session_state.get(k("started"), False)
                and not has_incoming_ranking_url()
                and restore_local_draft_payload(draft)
            ):
                rerun()
        return

    draft = build_local_draft_payload()
    if not draft:
        return

    signature_payload = {"state": draft.get("state"), "ui": draft.get("ui")}
    signature = hashlib.sha256(
        json.dumps(signature_payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
    ).hexdigest()
    if st.session_state.get("local_draft_last_signature") == signature:
        return

    st.session_state["local_draft_last_signature"] = signature
    LOCAL_DRAFT_COMPONENT(
        action="save",
        storage_key=LOCAL_DRAFT_STORAGE_KEY,
        draft=draft,
        key=f"local_draft_save_{signature[:16]}",
        default=None,
    )


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
    source_poster_url_map = st.session_state.get(k("source_poster_url_map"), {})

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
        initial_poster_url_map=source_poster_url_map,
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


def current_pair_for_log() -> tuple[str, str]:
    current_item = st.session_state.get(k("current_item")) or ""
    ranked = st.session_state.get(k("ranked"), [])
    if not current_item or not ranked:
        return current_item, ""
    low = st.session_state.get(k("low"), 0)
    high = st.session_state.get(k("high"), 0)
    idx = get_current_opponent_index(ranked, low, high)
    opponent = ranked[idx] if 0 <= idx < len(ranked) else ""
    return current_item, opponent


def append_decision_log(event_type: str, left_item: str, right_item: str, winner: str = "") -> None:
    if not left_item and not right_item:
        return
    log = st.session_state.get(k("decision_log"), [])
    if not isinstance(log, list):
        log = []
    log.append(
        {
            "type": event_type,
            "left": left_item,
            "right": right_item,
            "winner": winner,
            "comparison": int(st.session_state.get(k("comparisons"), 0)),
        }
    )
    st.session_state[k("decision_log")] = log[-200:]


def get_most_contested_pair() -> dict:
    log = st.session_state.get(k("decision_log"), [])
    if not isinstance(log, list):
        log = []
    ranked = st.session_state.get(k("ranked"), [])

    deferred = [
        row
        for row in log
        if isinstance(row, dict) and row.get("type") == "defer" and (row.get("left") or row.get("right"))
    ]
    if deferred:
        row = deferred[-1]
        return {
            "left": str(row.get("left") or ""),
            "right": str(row.get("right") or ""),
            "label": "你曾经暂放的选择",
            "note": "这组被你先放了一会儿，说明它确实需要多想一秒。",
        }

    choices = [
        row
        for row in log
        if isinstance(row, dict) and row.get("type") == "choice" and (row.get("left") or row.get("right"))
    ]
    if choices:
        top_set = set(ranked[:5])
        top_choices = [
            row
            for row in choices
            if str(row.get("left") or "") in top_set and str(row.get("right") or "") in top_set
        ]
        row = (top_choices or choices)[-1]
        winner = str(row.get("winner") or "")
        loser = str(row.get("right") if winner == row.get("left") else row.get("left") or "")
        return {
            "left": str(row.get("left") or ""),
            "right": str(row.get("right") or ""),
            "label": "关键取舍",
            "note": f"最后你选择了「{winner}」。" if winner and loser else "这组选择参与决定了最终榜单的前列气质。",
        }

    if len(ranked) >= 2:
        return {
            "left": ranked[0],
            "right": ranked[1],
            "label": "冠军边上的分岔",
            "note": "冠军和第二名之间，就是这份名单最有性格的一道分界线。",
        }

    return {"left": ranked[0] if ranked else "", "right": "", "label": "最纠结的一组选择", "note": "完成一次整理后，这里会记录你的关键取舍。"}


def handle_choice(prefer_left: bool) -> None:
    if st.session_state.get(k("finished"), False):
        return

    push_history_snapshot()

    current_item, opponent_item = current_pair_for_log()
    winner = current_item if prefer_left else opponent_item
    append_decision_log("choice", current_item, opponent_item, winner)

    st.session_state[k("comparisons")] += 1
    track_event(
        EVENT_COMPARISON_MADE,
        challenge_id=st.session_state.get(k("challenge_id"), ""),
        mode=st.session_state.get(k("mode"), MODE_CUSTOM),
        template_id=st.session_state.get(k("template_id"), ""),
        source_channel=st.session_state.get(k("source_channel"), get_source_channel()),
        payload=build_event_payload(
            route="sorting",
            list_id=st.session_state.get(k("challenge_id"), "") or st.session_state.get(k("template_id"), "") or st.session_state.get(k("mode"), MODE_CUSTOM),
            list_size=st.session_state.get(k("total"), 0),
            comparison_count=st.session_state.get(k("comparisons"), 0),
            top_k=st.session_state.get(k("top_k")),
        ),
    )
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
    current_item, opponent_item = current_pair_for_log()
    append_decision_log("defer", current_item, opponent_item)
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


def filter_collect_preview_entries(entries: List[Dict[str, Any]], query: str) -> List[Dict[str, Any]]:
    query = query.strip().lower()
    if not query:
        return entries
    return [entry for entry in entries if query in str(entry.get("title") or "").lower()]


def collect_entry_meta(entry: Dict[str, Any]) -> str:
    parts = []
    media_type = clean_media_type(entry.get("media_type"))
    parts.append(MEDIA_TYPE_LABELS.get(media_type, "未识别类型"))
    rating = entry.get("rating")
    if rating in DOUBAN_RATING_VALUES:
        parts.append(f"{rating} 星")
    rated_at = clean_collect_date(entry.get("rated_at"))
    if rated_at:
        parts.append(rated_at)
    return " · ".join(parts)


def valid_excluded_titles(excluded_titles: Any, entries: List[Dict[str, Any]]) -> List[str]:
    valid_titles = {str(entry.get("title") or "") for entry in entries if entry.get("title")}
    return [str(title) for title in excluded_titles if str(title) in valid_titles] if isinstance(excluded_titles, list) else []


def apply_excluded_titles(entries: List[Dict[str, Any]], excluded_titles: List[str]) -> List[Dict[str, Any]]:
    excluded = set(excluded_titles)
    return [entry for entry in entries if str(entry.get("title") or "") not in excluded]


def render_editable_collect_preview(
    entries: List[Dict[str, Any]],
    search_key: str,
    excluded_key: str,
    empty_text: str = "还没有预览结果。",
) -> None:
    excluded_titles = list(st.session_state.get(excluded_key, []))
    if excluded_titles:
        cols = st.columns([2.2, 1])
        with cols[0]:
            st.caption(f"已手动移除 {len(excluded_titles)} 部。")
        with cols[1]:
            if render_button_compat("恢复全部", key=f"{excluded_key}_restore", use_container_width=True):
                st.session_state[excluded_key] = []
                rerun()

    if not entries:
        st.write(empty_text)
        return

    query = st.text_input("搜索候选项", key=search_key, placeholder="输入关键词筛选")
    filtered = filter_collect_preview_entries(entries, query)
    display_entries = filtered[:30]
    st.caption(f"显示 {len(display_entries)} / {len(filtered)} 项；当前候选共 {len(entries)} 项。")
    for index, entry in enumerate(display_entries, 1):
        title = str(entry.get("title") or "")
        row_cols = st.columns([0.10, 0.78, 0.12])
        with row_cols[0]:
            st.write(f"{index}.")
        with row_cols[1]:
            st.write(title)
            st.caption(collect_entry_meta(entry))
        with row_cols[2]:
            if render_button_compat("×", key=f"{excluded_key}_remove_{stable_int(title)}", use_container_width=True):
                next_excluded = list(dict.fromkeys([*excluded_titles, title]))
                st.session_state[excluded_key] = next_excluded
                rerun()
    if len(filtered) > len(display_entries):
        st.caption("还有更多结果未显示，请继续输入关键词缩小范围。")


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


def render_result_peak(total: int, comparisons: int, top_k: Optional[int]) -> None:
    ranked = st.session_state.get(k("ranked"), [])
    theme = st.session_state.get(k("theme"), "我的电影审美名单")
    champion = ranked[0] if ranked else "暂无"
    contested = get_most_contested_pair()
    left = contested.get("left") or "暂无"
    right = contested.get("right") or "暂无"
    result_scope = "完整名单" if top_k is None else f"Top {min(top_k, len(ranked))}"

    st.markdown(
        f"""
        <div class="result-peak">
          <div class="result-peak-kicker">整理完成 · {html.escape(result_scope)}</div>
          <div class="result-peak-title">{html.escape(theme)}</div>
          <div class="result-peak-grid">
            <div class="result-peak-panel">
              <div class="result-peak-label">我的冠军电影</div>
              <div class="result-peak-value">{html.escape(champion)}</div>
              <div class="result-peak-note">这部电影站在了你这次 {total} 部电影取舍的最前面。</div>
            </div>
            <div class="result-peak-panel">
              <div class="result-peak-label">{html.escape(str(contested.get("label") or "最纠结的一组选择"))}</div>
              <div class="contest-pair">
                <div class="contest-item">{html.escape(left)}</div>
                <div class="contest-versus">VS</div>
                <div class="contest-item">{html.escape(right)}</div>
              </div>
              <div class="result-peak-note">{html.escape(str(contested.get("note") or ""))}</div>
            </div>
          </div>
          <div class="result-peak-note">共作出 {comparisons} 次取舍。现在可以把这份名单变成海报，发给朋友猜你的冠军。</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_poster_preview_html(poster_bytes: bytes) -> None:
    src = poster_data_uri(poster_bytes)
    if not src:
        st.info("海报正在生成。")
        return
    st.markdown(
        f"""
        <div class="poster-preview-shell">
          <img src="{src}" alt="结果海报预览" style="display:block;width:100%;border-radius:6px;" />
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_next_template_recommendations(current_template_id: str) -> None:
    templates_by_id = {str(template["id"]): template for template in FILM_CHALLENGE_TEMPLATES}
    routes = {
        "douban-top50": ["nolan", "chinese-highscore", "miyazaki"],
        "nolan": ["miyazaki", "chinese-highscore", "douban-top50"],
        "miyazaki": ["nolan", "chinese-highscore", "douban-top50"],
        "chinese-highscore": ["douban-top50", "nolan", "miyazaki"],
        "couple-debate": ["douban-top50", "nolan", "chinese-highscore"],
    }
    preferred = routes.get(current_template_id, ["nolan", "chinese-highscore", "miyazaki"])
    selected = [templates_by_id[item] for item in preferred if item in templates_by_id and item != current_template_id]
    for template in FILM_CHALLENGE_TEMPLATES:
        if len(selected) >= 3:
            break
        if str(template["id"]) != current_template_id and template not in selected:
            selected.append(template)

    if not selected:
        return

    cards = []
    for template in selected[:3]:
        template_id = html.escape(str(template["id"]), quote=True)
        cards.append(
            f'<a class="next-template-card" href="?list={template_id}" target="_self" aria-label="继续整理 {html.escape(str(template["name"]), quote=True)}">'
            f'<div class="next-template-label">下一份片单</div>'
            f'<div class="next-template-title">{html.escape(str(template["name"]))}</div>'
            f'<div class="next-template-copy">{html.escape(str(template.get("recommendation") or template.get("tagline") or ""))}</div>'
            f'</a>'
        )
    st.subheader("再生成一份不同气质的名单")
    st.markdown(f'<div class="next-template-grid">{"".join(cards)}</div>', unsafe_allow_html=True)


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


def clean_contact_value(raw_value: str) -> str:
    text = re.sub(r"\s+", " ", str(raw_value or "")).strip()
    for prefix in ("微信号：", "微信：", "微信号:", "微信:", "wechat:", "WeChat:", "WECHAT:"):
        if text.startswith(prefix):
            text = text[len(prefix):].strip()
    if len(text) > 80:
        text = text[:80]
    return text


def peer_list_key(mode: str, challenge_id: str, template_id: str) -> str:
    return template_id or challenge_id or mode or "unknown"


def peer_match_kind(mode: str, ranked: List[str], challenge_id: str, template_id: str, total: int) -> str:
    has_shared_list = bool(challenge_id or template_id)
    if mode == MODE_CUSTOM and has_shared_list and total <= 80:
        return "light"
    if len(ranked) < 10 and has_shared_list:
        return "light"
    return "heavy"


def peer_top_items(ranked: List[str], limit: int = 20) -> List[str]:
    return [str(item).strip() for item in ranked[:limit] if str(item).strip()]


def save_peer_contact(
    *,
    contact: str,
    ranked: List[str],
    mode: str,
    challenge_id: str,
    template_id: str,
    total: int,
) -> bool:
    if not analytics_enabled() or not ranked:
        return False
    clean_contact = clean_contact_value(contact)
    if len(clean_contact) < 2:
        return False
    top_items = peer_top_items(ranked, 20)
    body = {
        "session_id": get_session_id(),
        "contact": clean_contact,
        "list_kind": peer_match_kind(mode, ranked, challenge_id, template_id, total),
        "list_key": peer_list_key(mode, challenge_id, template_id),
        "challenge_id": challenge_id or None,
        "template_id": template_id or None,
        "mode": mode,
        "champion": top_items[0],
        "top_items": top_items,
        "ranked_count": len(ranked),
        "allow_display": True,
    }
    result = supabase_request(
        "POST",
        "peer_match_contacts",
        json_body=body,
        prefer="return=representation",
    )
    return isinstance(result, list) and bool(result)


def fetch_peer_contact_candidates(kind: str, champion: str, list_key: str) -> List[Dict[str, Any]]:
    if not analytics_enabled():
        return []
    params = {
        "select": "id,created_at,session_id,contact,list_kind,list_key,champion,top_items,ranked_count",
        "allow_display": "eq.true",
        "order": "created_at.desc",
        "limit": "200",
    }
    if kind == "light":
        params["list_kind"] = "eq.light"
        params["champion"] = f"eq.{champion}"
        if list_key:
            params["list_key"] = f"eq.{list_key}"
        params["limit"] = "30"
    else:
        params["list_kind"] = "eq.heavy"
    result = supabase_request("GET", "peer_match_contacts", params=params)
    return result if isinstance(result, list) else []


def peer_contact_matches(
    *,
    ranked: List[str],
    mode: str,
    challenge_id: str,
    template_id: str,
    total: int,
) -> Tuple[str, List[Dict[str, Any]]]:
    if not ranked:
        return "light", []
    kind = peer_match_kind(mode, ranked, challenge_id, template_id, total)
    list_key = peer_list_key(mode, challenge_id, template_id)
    candidates = fetch_peer_contact_candidates(kind, ranked[0], list_key)
    current_session = get_session_id()
    seen_contacts = set()
    matches: List[Dict[str, Any]] = []

    for row in candidates:
        contact = clean_contact_value(str(row.get("contact") or ""))
        if not contact or contact in seen_contacts:
            continue
        if str(row.get("session_id") or "") == current_session:
            continue
        candidate_items = row.get("top_items") if isinstance(row.get("top_items"), list) else []
        clean_items = [str(item).strip() for item in candidate_items if str(item).strip()]
        if kind == "light":
            if str(row.get("champion") or "") != ranked[0]:
                continue
            shared = [ranked[0]]
            score = 1.0
        else:
            my_top10 = peer_top_items(ranked, 10)
            other_top10 = clean_items[:10]
            shared = [item for item in my_top10 if item in set(other_top10)]
            if len(shared) < 3:
                continue
            score = len(shared) / max(1, len(my_top10))
        seen_contacts.add(contact)
        item = dict(row)
        item["contact"] = contact
        item["shared_items"] = shared
        item["match_score"] = score
        matches.append(item)

    matches.sort(key=lambda item: (float(item.get("match_score", 0.0)), len(item.get("shared_items", [])), str(item.get("created_at", ""))), reverse=True)
    return kind, matches[:5]


def render_peer_cards(kind: str, ranked: List[str], matches: List[Dict[str, Any]], *, compact: bool = False) -> None:
    if not ranked:
        return
    if not matches:
        note = (
            "暂时还没有找到第一名相同且愿意公开联系方式的同好。"
            if kind == "light"
            else "暂时还没有找到前十重合度达到 30% 且愿意公开联系方式的同好。"
        )
        st.markdown(f'<div class="peer-empty-note">{html.escape(note)}</div>', unsafe_allow_html=True)
        return

    cards = []
    champion = html.escape(ranked[0])
    for index, match in enumerate(matches, 1):
        contact = html.escape(str(match.get("contact") or ""))
        shared_items = [html.escape(str(item)) for item in match.get("shared_items", [])[:5]]
        if kind == "light":
            label = "第一名相同"
            copy = f"TA与你的第一名相同，你们都很喜欢 {champion}"
        else:
            overlap = len(match.get("shared_items", []))
            score = float(match.get("match_score", 0.0))
            label = f"前十重合 {overlap}/10"
            copy = "你们都很喜欢 " + "、".join(shared_items)
            if score:
                copy += f" · 重合度 {score:.0%}"
        cards.append(
            f"""
            <div class="peer-card">
              <div class="peer-card-label">{index}. {html.escape(label)}</div>
              <div class="peer-contact">{contact}</div>
              <div class="peer-shared">{copy}</div>
            </div>
            """
        )
    container_class = "peer-card-list" if compact else "peer-card-grid"
    st.markdown(f'<div class="{container_class}">{"".join(cards)}</div>', unsafe_allow_html=True)


def render_peer_contact_section(
    *,
    ranked: List[str],
    mode: str,
    challenge_id: str,
    template_id: str,
    total: int,
    compact: bool = False,
) -> None:
    if not ranked:
        return

    kind, matches = peer_contact_matches(
        ranked=ranked,
        mode=mode,
        challenge_id=challenge_id,
        template_id=template_id,
        total=total,
    )
    match_copy = "第一名相同会优先推荐；重榜单会看前十重合度。"
    st.markdown(
        f"""
        <div class="peer-side-section">
          <div class="peer-section-heading">推荐好友</div>
          <div class="peer-section-copy">{html.escape(match_copy)}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    render_peer_cards(kind, ranked, matches, compact=compact)

    st.markdown(
        """
        <div class="peer-side-section">
          <div class="peer-section-heading">留下联系方式</div>
          <div class="peer-section-copy">提交后会展示给与你结果相似的用户。请只填写愿意公开的信息。</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    contact = st.text_input(
        "微信号 / 联系方式",
        key=k("peer_contact_input"),
        max_chars=80,
        placeholder="例如微信号",
    )
    if render_button_compat("提交联系方式", key="btn_submit_peer_contact", use_container_width=True):
        clean_contact = clean_contact_value(contact)
        signature = f"{clean_contact}|{peer_list_key(mode, challenge_id, template_id)}|{ranked[0]}"
        if len(clean_contact) < 2:
            st.warning("请填写有效的联系方式。")
        elif st.session_state.get(k("peer_contact_saved_signature")) == signature:
            st.success("这个联系方式已经提交过了。")
        elif save_peer_contact(
            contact=clean_contact,
            ranked=ranked,
            mode=mode,
            challenge_id=challenge_id,
            template_id=template_id,
            total=total,
        ):
            st.session_state[k("peer_contact_saved_signature")] = signature
            st.success("已提交。之后相似榜单的用户可能会看到你的联系方式。")
        else:
            st.error("暂时没有保存成功。请确认 Supabase 已更新表结构，或稍后再试。")


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


def store_imported_movie_list_state(imported, *, update_collect_input: bool = True) -> None:
    if update_collect_input:
        st.session_state["ui_douban_collect_import_id"] = imported.id
    st.session_state["ui_douban_collect_preview_entries"] = imported.entries
    st.session_state["ui_douban_collect_preview_movies"] = imported.items
    st.session_state["ui_douban_collect_preview_source"] = f"import:{imported.id}"
    st.session_state["ui_douban_collect_preview_user_id"] = ""
    st.session_state["ui_douban_collect_excluded_titles"] = []
    st.session_state["ui_import_id"] = imported.id
    st.session_state["ui_import_item_count"] = len(imported.items)
    st.session_state["ui_import_poster_url_map"] = imported.poster_url_map
    st.session_state["ui_import_rating_map"] = imported.rating_map
    st.session_state["ui_import_rated_at_map"] = imported.rated_at_map
    st.session_state["ui_import_media_type_map"] = imported.media_type_map
    st.session_state["ui_import_has_rating_data"] = imported.has_rating_data
    st.session_state["ui_import_has_year_data"] = imported.has_rated_at_data
    st.session_state["ui_import_has_media_type_data"] = imported.has_media_type_data
    st.session_state["ui_import_entries"] = imported.entries
    st.session_state["ui_import_source"] = imported.source


def open_imported_movie_list(import_id: str, *, update_collect_input: bool = True) -> bool:
    clean_id = clean_import_id(import_id)
    if not clean_id:
        st.session_state["ui_selected_mode"] = MODE_DOUBAN_COLLECT
        st.session_state["ui_step"] = 2
        st.session_state["ui_import_fetch_failed_id"] = str(import_id or "").strip()
        st.session_state["ui_import_fetch_failed_message"] = "这个片单 ID 看起来不正确。"
        return False

    imported = fetch_imported_movie_list(clean_id)
    st.session_state["local_draft_checked"] = True
    if not imported:
        st.session_state["ui_selected_mode"] = MODE_DOUBAN_COLLECT
        st.session_state["ui_step"] = 2
        st.session_state["ui_import_lookup_id"] = clean_id
        st.session_state["ui_import_fetch_failed_id"] = clean_id
        st.session_state["ui_import_fetch_failed_message"] = "收到片单 ID，但还没有从云端读到片单。可能是 Supabase 表/权限没有更新，或刚保存完还需要几秒。"
        return False

    st.session_state["loaded_import_id"] = clean_id
    st.session_state.pop("ui_import_fetch_failed_id", None)
    st.session_state.pop("ui_import_fetch_failed_message", None)
    if st.session_state.get(k("started"), False):
        clear_ranking_state()

    st.session_state["ui_selected_mode"] = MODE_DOUBAN_COLLECT
    st.session_state["ui_step"] = 2
    store_imported_movie_list_state(imported, update_collect_input=update_collect_input)
    st.session_state["ui_import_loaded_notice"] = True
    return True


def maybe_open_imported_movie_list() -> None:
    import_id = get_query_param("import")
    if not import_id or st.session_state.get("loaded_import_id") == import_id:
        return

    opened = open_imported_movie_list(import_id)
    if opened:
        track_once(
            f"import_list_opened_{clean_import_id(import_id)}",
            EVENT_CHALLENGE_OPENED,
            challenge_id=clean_import_id(import_id),
            mode=MODE_DOUBAN_COLLECT,
            source_channel=get_source_channel(),
            payload=build_event_payload(
                route="import_open",
                list_id=clean_import_id(import_id),
                mode=MODE_DOUBAN_COLLECT,
            ),
        )
        clear_query_param("import")
        rerun()
    else:
        clear_query_param("import")


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
        payload=build_event_payload(
            route="list_open",
            list_id=challenge.id,
            list_size=len(challenge.items),
            item_count=len(challenge.items),
            top_k=challenge.top_k,
        ),
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


def admin_int(value: Any) -> str:
    try:
        return f"{int(value):,}"
    except (TypeError, ValueError):
        return "0"


def admin_float(value: Any) -> str:
    try:
        return f"{float(value):.1f}"
    except (TypeError, ValueError):
        return "0.0"


def admin_percent(value: Any) -> str:
    try:
        return f"{float(value):.1%}"
    except (TypeError, ValueError):
        return "0.0%"


def admin_short_time(value: Any) -> str:
    text = str(value or "")
    return text.replace("T", " ")[:19]


def render_admin_dataframe(frame: pd.DataFrame) -> None:
    try:
        st.dataframe(frame, use_container_width=True, hide_index=True)
    except TypeError:
        st.dataframe(frame)


def render_admin_metric_grid(summary: Dict[str, Any]) -> None:
    first_row = [
        ("访问", admin_int(summary.get("page_views"))),
        ("独立 session", admin_int(summary.get("unique_sessions"))),
        ("开始整理", admin_int(summary.get("started"))),
        ("完成名单", admin_int(summary.get("completed"))),
        ("复制分享", admin_int(summary.get("copied"))),
        ("下载海报", admin_int(summary.get("posters"))),
    ]
    second_row = [
        ("开始率", admin_percent(summary.get("start_rate"))),
        ("完成率", admin_percent(summary.get("completion_rate"))),
        ("复制/完成", admin_percent(summary.get("share_rate"))),
        ("海报/完成", admin_percent(summary.get("poster_rate"))),
        ("平均取舍", admin_float(summary.get("avg_comparisons"))),
        ("平均规模", admin_float(summary.get("avg_total"))),
    ]
    for row in (first_row, second_row):
        columns = st.columns(len(row))
        for column, (label, value) in zip(columns, row):
            with column:
                st.metric(label, value)
    st.caption("复制/完成、海报/完成按动作次数除以完成名单数计算；同一用户多次复制或下载时可能超过 100%。")


def render_admin_insights(insights: List[str]) -> None:
    st.subheader("自动洞察")
    if not insights:
        st.info("当前筛选范围内还没有足够数据生成洞察。")
        return
    st.markdown("\n".join(f"- {html.escape(insight)}" for insight in insights))


def admin_funnel_df(rows: List[Dict[str, Any]]) -> pd.DataFrame:
    if not rows:
        return pd.DataFrame()
    frame = pd.DataFrame(rows)
    return pd.DataFrame(
        {
            "步骤": frame["step"],
            "事件": frame["event_name"].map(lambda name: EVENT_LABELS.get(str(name), str(name))),
            "数量": frame["count"],
            "上一步转化": frame["step_rate"].map(admin_percent),
            "总转化": frame["overall_rate"].map(admin_percent),
        }
    )


def render_admin_funnel(title: str, rows: List[Dict[str, Any]], caption: str) -> None:
    st.markdown(f"**{title}**")
    if not rows:
        st.info("当前筛选范围内没有漏斗数据。")
        return
    frame = pd.DataFrame(rows)
    chart = frame[["step", "count"]].rename(columns={"step": "步骤", "count": "数量"}).set_index("步骤")
    chart_col, table_col = st.columns([1, 1])
    with chart_col:
        st.bar_chart(chart)
    with table_col:
        render_admin_dataframe(admin_funnel_df(rows))
    st.caption(caption)


def admin_group_df(rows: List[Dict[str, Any]], label_key: str, label_name: str, include_winners: bool = False) -> pd.DataFrame:
    if not rows:
        return pd.DataFrame()
    display_rows: List[Dict[str, Any]] = []
    for row in rows:
        item = {
            label_name: row.get(label_key, ""),
            "事件": int(row.get("total_events", 0)),
            "访问": int(row.get("page_views", 0)),
            "打开": int(row.get("challenge_opened", 0)),
            "开始": int(row.get("started", 0)),
            "完成": int(row.get("completed", 0)),
            "复制": int(row.get("copied", 0)),
            "海报": int(row.get("posters", 0)),
            "完成率": admin_percent(row.get("completion_rate")),
            "复制/完成": admin_percent(row.get("share_rate")),
            "海报/完成": admin_percent(row.get("poster_rate")),
            "平均取舍": round(float(row.get("avg_comparisons", 0.0)), 1),
            "平均规模": round(float(row.get("avg_total", 0.0)), 1),
            "最近活跃": admin_short_time(row.get("last_seen")),
        }
        if include_winners:
            item["冠军 Top3"] = row.get("top_winners", "")
        display_rows.append(item)
    return pd.DataFrame(display_rows)


def render_admin_group_section(
    title: str,
    rows: List[Dict[str, Any]],
    label_key: str,
    label_name: str,
    *,
    include_winners: bool = False,
) -> None:
    st.markdown(f"**{title}**")
    if not rows:
        st.info("当前筛选范围内没有数据。")
        return
    display = admin_group_df(rows, label_key, label_name, include_winners=include_winners)
    chart_source = display[[label_name, "完成", "开始"]].head(12).set_index(label_name)
    chart_col, table_col = st.columns([1, 1.6])
    with chart_col:
        st.bar_chart(chart_source)
    with table_col:
        render_admin_dataframe(display)


def render_admin_count_chart(rows: List[Dict[str, Any]], label_key: str, title: str) -> None:
    st.markdown(f"**{title}**")
    if not rows:
        st.info("当前筛选范围内没有数据。")
        return
    frame = pd.DataFrame(rows)
    st.bar_chart(frame[[label_key, "count"]].set_index(label_key))
    render_admin_dataframe(frame)


def render_admin_trends(events: List[Dict[str, Any]]) -> None:
    daily_rows = build_daily_metrics(events)
    if not daily_rows:
        st.info("当前筛选范围内没有趋势数据。")
        return
    daily = pd.DataFrame(daily_rows).set_index("date")
    event_cols = [
        EVENT_PAGE_VIEW,
        EVENT_RANKING_STARTED,
        EVENT_RANKING_COMPLETED,
        EVENT_SHARE_LINK_COPIED,
        EVENT_POSTER_DOWNLOADED,
    ]
    rate_cols = ["start_rate", "completion_rate", "share_rate", "poster_rate"]
    event_chart = daily[event_cols].rename(columns=EVENT_LABELS)
    rate_chart = (daily[rate_cols] * 100).rename(
        columns={
            "start_rate": "开始率",
            "completion_rate": "完成率",
            "share_rate": "复制/完成",
            "poster_rate": "海报/完成",
        }
    )
    event_tab, rate_tab, data_tab = st.tabs(["事件趋势", "转化趋势", "趋势数据"])
    with event_tab:
        st.line_chart(event_chart)
    with rate_tab:
        st.line_chart(rate_chart)
        st.caption("转化趋势以百分比数值展示。")
    with data_tab:
        display = daily.reset_index().rename(columns={"date": "日期", **EVENT_LABELS})
        render_admin_dataframe(display)
        render_download_button_compat(
            "下载每日趋势 CSV",
            display.to_csv(index=False).encode("utf-8-sig"),
            "admin_daily_metrics.csv",
            "text/csv",
            "admin_download_daily_metrics",
        )


def render_admin_recent_events(events: List[Dict[str, Any]]) -> None:
    label_to_name = {label: name for name, label in EVENT_LABELS.items()}
    event_labels = list(label_to_name.keys())
    selected_labels = st.multiselect("事件类型", event_labels, default=event_labels, key="admin_recent_event_labels")
    selected_names = {label_to_name[label] for label in selected_labels}
    search_col1, search_col2, search_col3, search_col4 = st.columns([1, 1, 1, 1])
    with search_col1:
        session_query = st.text_input("Session 后 8 位", key="admin_recent_session_query").strip().lower()
    with search_col2:
        template_query = st.text_input("模板 ID", key="admin_recent_template_query").strip().lower()
    with search_col3:
        challenge_query = st.text_input("片单 ID", key="admin_recent_challenge_query").strip().lower()
    with search_col4:
        limit = st.number_input("展示条数", min_value=20, max_value=1000, value=200, step=20, key="admin_recent_limit")

    filtered: List[Dict[str, Any]] = []
    for event in events:
        if event.get("event_name") not in selected_names:
            continue
        session_id = str(event.get("session_id") or "").lower()
        template_id = str(event.get("template_id") or "").lower()
        challenge_id = str(event.get("challenge_id") or "").lower()
        if session_query and session_query not in session_id[-8:]:
            continue
        if template_query and template_query not in template_id:
            continue
        if challenge_query and challenge_query not in challenge_id:
            continue
        filtered.append(event)

    rows = build_event_table_rows(filtered, int(limit))
    if not rows:
        st.info("当前筛选条件下没有事件。")
        return
    frame = pd.DataFrame(rows)
    render_admin_dataframe(frame)
    render_download_button_compat(
        "下载当前事件 CSV",
        frame.to_csv(index=False).encode("utf-8-sig"),
        "admin_events.csv",
        "text/csv",
        "admin_download_events",
    )


def render_admin_dashboard() -> None:
    ensure_pandas()
    token = get_query_param("admin")
    expected = get_admin_token()
    if not expected or token != expected:
        st.error("后台口令无效或未配置。")
        return

    st.title("电影审美名单 · Admin Analytics v1")
    if not analytics_enabled():
        st.warning("Supabase 还没有配置，暂时没有可展示的数据。")
        return

    if render_button_compat("刷新数据缓存", key="admin_refresh_cache", use_container_width=False):
        try:
            fetch_all_events.clear()
        except Exception:
            pass
        rerun()

    all_events = fetch_all_events()
    min_event_date, max_event_date = available_event_date_range(all_events)
    if not all_events or min_event_date is None or max_event_date is None:
        st.info("Supabase 已配置，但 analytics_events 里还没有可展示的事件。")
        return

    st.caption(f"已读取历史事件 {len(all_events):,} 条。统计基于匿名事件，不包含姓名、IP 或联系方式。")
    filter_col1, filter_col2, filter_col3 = st.columns([1, 1, 1])
    with filter_col1:
        range_option = st.selectbox(
            "时间范围",
            ["近 7 天", "近 30 天", "近 90 天", "全部历史", "自定义"],
            index=1,
            key="admin_range_option",
        )

    if range_option == "近 7 天":
        start_date = max(min_event_date, max_event_date - timedelta(days=6))
        end_date = max_event_date
    elif range_option == "近 30 天":
        start_date = max(min_event_date, max_event_date - timedelta(days=29))
        end_date = max_event_date
    elif range_option == "近 90 天":
        start_date = max(min_event_date, max_event_date - timedelta(days=89))
        end_date = max_event_date
    elif range_option == "全部历史":
        start_date = min_event_date
        end_date = max_event_date
    else:
        default_start = max(min_event_date, max_event_date - timedelta(days=29))
        with filter_col2:
            start_date = st.date_input(
                "开始日期",
                value=default_start,
                min_value=min_event_date,
                max_value=max_event_date,
                key="admin_custom_start_date",
            )
        with filter_col3:
            end_date = st.date_input(
                "结束日期",
                value=max_event_date,
                min_value=min_event_date,
                max_value=max_event_date,
                key="admin_custom_end_date",
            )
    if range_option != "自定义":
        with filter_col2:
            st.metric("开始日期", start_date.isoformat())
        with filter_col3:
            st.metric("结束日期", end_date.isoformat())

    if isinstance(start_date, tuple):
        start_date = start_date[0]
    if isinstance(end_date, tuple):
        end_date = end_date[-1]
    if start_date > end_date:
        st.warning("开始日期晚于结束日期，已自动交换。")
        start_date, end_date = end_date, start_date

    events = filter_events_by_date(all_events, start_date, end_date)
    st.caption(f"当前筛选：{start_date.isoformat()} 至 {end_date.isoformat()}，共 {len(events):,} 条事件。")
    if not events:
        st.info("当前时间范围内没有事件。")
        return

    summary = build_admin_summary(events)
    render_admin_metric_grid(summary)
    safe_divider()
    render_admin_insights(build_admin_insights(events))
    safe_divider()

    funnel_tab, trend_tab, source_tab, content_tab, behavior_tab, share_tab, event_tab = st.tabs(
        ["转化漏斗", "每日趋势", "渠道与模式", "内容表现", "行为质量", "分享与素材", "最近事件"]
    )

    with funnel_tab:
        render_admin_funnel(
            "主漏斗",
            build_funnel_rows(events, MAIN_FUNNEL_STEPS),
            "主漏斗按事件总量计算，不做同一 session 的严格路径归因。",
        )
        safe_divider()
        render_admin_funnel(
            "共享片单漏斗",
            build_funnel_rows(events, SHARED_FUNNEL_STEPS),
            "共享片单漏斗用于观察片单传播链路；开始、完成和分享仍是筛选范围内的总事件数。",
        )

    with trend_tab:
        render_admin_trends(events)

    with source_tab:
        source_rows = build_group_metrics(events, "source_channel", label_key="source_channel", include_unknown=True, top_n=30)
        mode_rows = build_group_metrics(events, "mode", label_key="mode", include_unknown=True, top_n=30)
        render_admin_group_section("来源渠道表现", source_rows, "source_channel", "来源")
        safe_divider()
        render_admin_group_section("模式表现", mode_rows, "mode", "模式")

    with content_tab:
        template_rows = build_group_metrics(events, "template_id", label_key="template_id", include_winners=True, top_n=30)
        challenge_rows = build_group_metrics(events, "challenge_id", label_key="challenge_id", top_n=30)
        render_admin_group_section("模板表现排行榜", template_rows, "template_id", "模板", include_winners=True)
        safe_divider()
        render_admin_group_section("热门片单传播榜", challenge_rows, "challenge_id", "片单 ID")
        safe_divider()
        render_admin_count_chart(
            build_payload_value_counts(events, EVENT_RANKING_COMPLETED, "winner", label_key="冠军", top_n=20),
            "冠军",
            "冠军电影分布",
        )

    with behavior_tab:
        q1, q2, q3, q4 = st.columns(4)
        with q1:
            st.metric("取舍中位数", admin_float(summary.get("median_comparisons")))
        with q2:
            st.metric("取舍 P75", admin_float(summary.get("p75_comparisons")))
        with q3:
            st.metric("取舍 P90", admin_float(summary.get("p90_comparisons")))
        with q4:
            st.metric("平均暂放", admin_float(summary.get("avg_defers")))
        h1, h2 = st.columns(2)
        with h1:
            render_admin_count_chart(
                build_numeric_payload_histogram(
                    events,
                    EVENT_RANKING_COMPLETED,
                    "comparisons",
                    [10, 20, 40, 80, 120, 200],
                    label_key="取舍次数",
                ),
                "取舍次数",
                "取舍次数分布",
            )
        with h2:
            render_admin_count_chart(
                build_numeric_payload_histogram(
                    events,
                    EVENT_RANKING_COMPLETED,
                    "total",
                    [10, 20, 50, 100, 250, 500, 1000],
                    label_key="片单规模",
                ),
                "片单规模",
                "片单规模分布",
            )
        safe_divider()
        k1, k2 = st.columns(2)
        with k1:
            render_admin_count_chart(build_top_k_distribution(events), "top_k", "Top K 设置分布")
        with k2:
            setting_rows = build_setting_rows(events)
            if setting_rows:
                settings_display = pd.DataFrame(
                    {
                        "设置": [row["setting"] for row in setting_rows],
                        "次数": [row["count"] for row in setting_rows],
                        "占开始比例": [admin_percent(row["rate"]) for row in setting_rows],
                    }
                )
                st.markdown("**交互设置使用率**")
                st.bar_chart(pd.DataFrame(setting_rows).set_index("setting")[["count"]])
                render_admin_dataframe(settings_display)
            else:
                st.info("当前筛选范围内没有设置数据。")

    with share_tab:
        c1, c2 = st.columns(2)
        with c1:
            render_admin_count_chart(
                build_payload_value_counts(events, EVENT_SHARE_LINK_COPIED, "surface", label_key="分享入口", include_empty=True),
                "分享入口",
                "分享动作拆分",
            )
        with c2:
            render_admin_count_chart(
                build_payload_value_counts(events, EVENT_POSTER_DOWNLOADED, "poster_type", label_key="海报类型", include_empty=True),
                "海报类型",
                "海报下载拆分",
            )

    with event_tab:
        render_admin_recent_events(events)


# Admin Analytics v2 overrides the legacy v1 dashboard helpers above.
def render_admin_metric_grid(summary: Dict[str, Any]) -> None:
    first_row = [
        ("访问数", admin_int(summary.get("visits"))),
        ("独立 session", admin_int(summary.get("unique_sessions"))),
        ("打开/选择片单", admin_int(summary.get("open_or_select_list"))),
        ("开始整理", admin_int(summary.get("started"))),
        ("完成名单", admin_int(summary.get("completed"))),
        ("复制分享", admin_int(summary.get("copied"))),
        ("下载海报", admin_int(summary.get("posters"))),
    ]
    second_row = [
        ("开始率", admin_percent(summary.get("start_rate"))),
        ("完成率", admin_percent(summary.get("completion_rate"))),
        ("复制/完成", admin_percent(summary.get("share_rate"))),
        ("海报/完成", admin_percent(summary.get("poster_rate"))),
        ("平均取舍次数", admin_float(summary.get("avg_comparisons"))),
        ("平均整理规模", admin_float(summary.get("avg_list_size"))),
    ]
    for row in (first_row, second_row):
        columns = st.columns(len(row))
        for column, (label, value) in zip(columns, row):
            with column:
                st.metric(label, value)
    st.caption("复制/完成、海报/完成按动作次数除以完成名单数计算；同一匿名 session 多次复制或下载时可能超过 100%。")


def admin_funnel_df(rows: List[Dict[str, Any]]) -> pd.DataFrame:
    if not rows:
        return pd.DataFrame()
    frame = pd.DataFrame(rows)
    return pd.DataFrame(
        {
            "步骤": frame["step"],
            "事件": frame["event_name"],
            "事件数": frame["count"],
            "单步转化率": frame["step_rate"].map(admin_percent),
            "总体转化率": frame["overall_rate"].map(admin_percent),
            "相邻流失数": frame["dropoff"],
        }
    )


def admin_session_funnel_df(rows: List[Dict[str, Any]]) -> pd.DataFrame:
    if not rows:
        return pd.DataFrame()
    frame = pd.DataFrame(rows)
    return pd.DataFrame(
        {
            "步骤": frame["step"],
            "埋点": frame["event_name"],
            "session 数": frame["count"],
            "单步转化率": frame["step_rate"].map(admin_percent),
            "总体转化率": frame["overall_rate"].map(admin_percent),
            "相邻流失 session": frame["dropoff"],
        }
    )


def render_admin_funnel(title: str, rows: List[Dict[str, Any]], caption: str) -> None:
    st.markdown(f"**{title}**")
    if not rows:
        st.info("当前筛选范围内没有漏斗数据。")
        return
    frame = pd.DataFrame(rows)
    chart = frame[["step", "count"]].rename(columns={"step": "步骤", "count": "事件数"}).set_index("步骤")
    chart_col, table_col = st.columns([1, 1.25])
    with chart_col:
        st.bar_chart(chart)
    with table_col:
        render_admin_dataframe(admin_funnel_df(rows))
    st.info(build_funnel_insight(rows))
    st.caption(caption)


def render_admin_session_funnel(title: str, rows: List[Dict[str, Any]], caption: str) -> None:
    st.markdown(f"**{title}**")
    if not rows or int(rows[0].get("count", 0)) == 0:
        st.info("当前筛选范围内没有符合当前埋点口径的 session。")
        st.caption(caption)
        return
    frame = pd.DataFrame(rows)
    chart = frame[["step", "count"]].rename(columns={"step": "步骤", "count": "session 数"}).set_index("步骤")
    chart_col, table_col = st.columns([1, 1.35])
    with chart_col:
        st.bar_chart(chart)
    with table_col:
        render_admin_dataframe(admin_session_funnel_df(rows))
    st.info(build_funnel_insight(rows))
    st.caption(caption)


def render_admin_instrumentation_note(events: List[Dict[str, Any]]) -> None:
    summary = build_funnel_instrumentation_summary(events)
    cols = st.columns(4)
    cards = [
        ("当前埋点事件", admin_int(summary.get("current_events"))),
        ("历史兼容事件", admin_int(summary.get("legacy_events"))),
        ("首页已渲染 session", admin_int(summary.get("home_rendered_sessions"))),
        ("重链路入口 session", admin_int(summary.get("heavy_entry_sessions"))),
    ]
    for col, (label, value) in zip(cols, cards):
        with col:
            st.metric(label, value)
    st.caption(
        "新版 session 漏斗只统计当前 canonical 埋点，并按上一步 session 逐步收敛；"
        "历史兼容事件会继续用于趋势、最近事件和旧口径参考，但不会进入新版漏斗的上一级分母。"
    )


def render_admin_home_load_diagnostics(events: List[Dict[str, Any]]) -> None:
    metrics = build_home_load_metrics(events)
    visits = int(metrics.get("home_visit_sessions", 0))
    home_load_available = int(metrics.get("home_render_event_count", 0) or 0) > 0
    render_time_available = int(metrics.get("home_render_time_count", 0) or 0) > 0
    st.markdown("**首页加载诊断**")
    if not visits:
        st.info("当前筛选范围内没有普通首页访问。带 list/challenge/payload 的深链访问不计入这个诊断。")
        return

    cards = [
        ("首页访问 session", admin_int(visits)),
        ("内容已渲染 session", admin_int(metrics.get("home_rendered_sessions")) if home_load_available else VERSION_NO_DATA),
        ("加载中流失 session", admin_int(metrics.get("pre_render_lost_sessions")) if home_load_available else VERSION_NO_DATA),
        ("渲染后未行动 session", admin_int(metrics.get("post_render_no_action_sessions")) if home_load_available else VERSION_NO_DATA),
        ("渲染完成率", admin_percent(metrics.get("render_completion_rate")) if home_load_available else VERSION_NO_DATA),
        ("渲染后行动率", admin_percent(metrics.get("post_render_action_rate")) if home_load_available and int(metrics.get("home_rendered_sessions", 0) or 0) > 0 else VERSION_NO_DATA),
        ("平均渲染耗时", f"{float(metrics.get('avg_render_elapsed_ms', 0.0)):.0f} ms" if render_time_available else VERSION_NO_DATA),
        ("P75 渲染耗时", f"{float(metrics.get('p75_render_elapsed_ms', 0.0)):.0f} ms" if render_time_available else VERSION_NO_DATA),
        ("P90 渲染耗时", f"{float(metrics.get('p90_render_elapsed_ms', 0.0)):.0f} ms" if render_time_available else VERSION_NO_DATA),
    ]
    columns = st.columns(4)
    for index, (label, value) in enumerate(cards):
        with columns[index % 4]:
            st.metric(label, value)

    st.info(build_home_load_insight(metrics))
    render_admin_dataframe(
        pd.DataFrame(
            [
                {
                    "阶段": "visit：开始加载首页",
                    "session 数": visits,
                    "相对首页访问": admin_percent(1.0),
                },
                {
                    "阶段": "home_content_rendered：首页核心内容已渲染",
                    "session 数": int(metrics.get("home_rendered_sessions", 0)) if home_load_available else VERSION_NO_DATA,
                    "相对首页访问": admin_percent(metrics.get("render_completion_rate")) if home_load_available else VERSION_NO_DATA,
                },
                {
                    "阶段": "list_opened/list_selected/sorting_started：渲染后发生片单动作",
                    "session 数": int(metrics.get("home_engaged_sessions", 0)) if home_load_available else VERSION_NO_DATA,
                    "相对首页访问": (
                        admin_percent(int(metrics.get("home_engaged_sessions", 0)) / visits)
                        if home_load_available and visits
                        else VERSION_NO_DATA
                    ),
                },
            ]
        )
    )
    st.caption(
        "说明：这是匿名 session 级诊断。home_content_rendered 表示 Streamlit 服务端完成首页核心内容渲染；"
        "它能帮助定位服务端渲染前流失，但不等同于浏览器真实 FCP/LCP。"
    )


def version_sort_value(row: Dict[str, Any]) -> str:
    return str(row.get("released_at") or row.get("first_event_at") or "")


VERSION_NO_DATA = "---"


def version_has_home_load_data(row: Dict[str, Any]) -> bool:
    return bool(row.get("home_load_diagnostic_available"))


def version_percent_or_dash(row: Dict[str, Any], key: str, denominator_key: str, *, require_home_load: bool = False) -> str:
    if require_home_load and not version_has_home_load_data(row):
        return VERSION_NO_DATA
    try:
        if int(row.get(denominator_key, 0)) <= 0:
            return VERSION_NO_DATA
        if row.get(key) is None:
            return VERSION_NO_DATA
        return admin_percent(row.get(key))
    except (TypeError, ValueError):
        return VERSION_NO_DATA


def version_count_or_dash(row: Dict[str, Any], key: str, *, require_home_load: bool = False) -> str:
    if require_home_load and not version_has_home_load_data(row):
        return VERSION_NO_DATA
    try:
        return admin_int(row.get(key))
    except (TypeError, ValueError):
        return VERSION_NO_DATA


def version_ms_or_dash(row: Dict[str, Any], key: str, *, require_render_time: bool = False) -> str:
    if require_render_time and int(row.get("home_render_time_count", 0) or 0) <= 0:
        return VERSION_NO_DATA
    try:
        if row.get(key) is None:
            return VERSION_NO_DATA
        return f"{float(row.get(key, 0.0)):.0f} ms"
    except (TypeError, ValueError):
        return VERSION_NO_DATA


def version_rate_value_or_none(row: Dict[str, Any], key: str, denominator_key: str, *, require_home_load: bool = False) -> Optional[float]:
    if require_home_load and not version_has_home_load_data(row):
        return None
    try:
        if int(row.get(denominator_key, 0)) <= 0:
            return None
        return float(row.get(key, 0.0))
    except (TypeError, ValueError):
        return None


def admin_delta_pp(current: Any, previous: Any) -> str:
    if current is None or previous is None:
        return VERSION_NO_DATA
    try:
        return f"{(float(current) - float(previous)) * 100:+.1f} pp"
    except (TypeError, ValueError):
        return VERSION_NO_DATA


def admin_delta_ms(current: Any, previous: Any) -> str:
    if current is None or previous is None:
        return VERSION_NO_DATA
    try:
        return f"{float(current) - float(previous):+.0f} ms"
    except (TypeError, ValueError):
        return VERSION_NO_DATA


def build_version_overview_display(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    display_rows = []
    for row in rows:
        display_rows.append(
            {
                "版本": row.get("release_label", row.get("app_version", "")),
                "上线时间": admin_short_time(row.get("released_at")),
                "事件窗口": f"{admin_short_time(row.get('first_event_at'))} ~ {admin_short_time(row.get('last_event_at'))}",
                "事件数": int(row.get("events", 0)),
                "session": int(row.get("sessions", 0)),
                "首页访问": int(row.get("visit_sessions", 0)),
                "加载中流失": version_count_or_dash(row, "pre_render_lost_sessions", require_home_load=True),
                "首页渲染完成率": version_percent_or_dash(row, "home_render_rate", "visit_sessions", require_home_load=True),
                "加载中流失率": version_percent_or_dash(row, "pre_render_loss_rate", "visit_sessions", require_home_load=True),
                "渲染后行动率": version_percent_or_dash(row, "post_render_action_rate", "home_rendered_sessions", require_home_load=True),
                "打开/选择率": version_percent_or_dash(row, "open_or_select_rate", "visit_sessions"),
                "开始率": version_percent_or_dash(row, "start_rate", "visit_sessions"),
                "完成率": version_percent_or_dash(row, "completion_rate", "started_sessions"),
                "分享率": version_percent_or_dash(row, "share_rate", "completed_sessions"),
                "P90 渲染耗时": version_ms_or_dash(row, "p90_render_elapsed_ms", require_render_time=True),
                "commit": row.get("commit", ""),
            }
        )
    return display_rows


def build_version_comparison_display(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    chronological = sorted(rows, key=version_sort_value)
    display_rows = []
    for previous, current in zip(chronological, chronological[1:]):
        display_rows.append(
            {
                "版本对比": f"{previous.get('app_version', '')} -> {current.get('app_version', '')}",
                "当前版本": current.get("release_label", current.get("app_version", "")),
                "上一版本": previous.get("release_label", previous.get("app_version", "")),
                "首页渲染完成率变化": admin_delta_pp(
                    version_rate_value_or_none(current, "home_render_rate", "visit_sessions", require_home_load=True),
                    version_rate_value_or_none(previous, "home_render_rate", "visit_sessions", require_home_load=True),
                ),
                "加载中流失率变化": admin_delta_pp(
                    version_rate_value_or_none(current, "pre_render_loss_rate", "visit_sessions", require_home_load=True),
                    version_rate_value_or_none(previous, "pre_render_loss_rate", "visit_sessions", require_home_load=True),
                ),
                "渲染后行动率变化": admin_delta_pp(
                    version_rate_value_or_none(current, "post_render_action_rate", "home_rendered_sessions", require_home_load=True),
                    version_rate_value_or_none(previous, "post_render_action_rate", "home_rendered_sessions", require_home_load=True),
                ),
                "开始率变化": admin_delta_pp(
                    version_rate_value_or_none(current, "start_rate", "visit_sessions"),
                    version_rate_value_or_none(previous, "start_rate", "visit_sessions"),
                ),
                "完成率变化": admin_delta_pp(
                    version_rate_value_or_none(current, "completion_rate", "started_sessions"),
                    version_rate_value_or_none(previous, "completion_rate", "started_sessions"),
                ),
                "分享率变化": admin_delta_pp(
                    version_rate_value_or_none(current, "share_rate", "completed_sessions"),
                    version_rate_value_or_none(previous, "share_rate", "completed_sessions"),
                ),
                "P90 渲染耗时变化": admin_delta_ms(
                    current.get("p90_render_elapsed_ms") if int(current.get("home_render_time_count", 0) or 0) > 0 else None,
                    previous.get("p90_render_elapsed_ms") if int(previous.get("home_render_time_count", 0) or 0) > 0 else None,
                ),
                "当前首页访问": int(current.get("visit_sessions", 0)),
                "当前开始": int(current.get("started_sessions", 0)),
                "当前完成": int(current.get("completed_sessions", 0)),
            }
        )
    return list(reversed(display_rows))


def render_version_metric_definitions() -> None:
    with st.expander("每列怎么计算", expanded=False):
        st.markdown(
            """
| 列 | 计算方式 |
| --- | --- |
| 事件窗口 | 当前筛选范围内，归因到该版本的第一条事件时间 ~ 最后一条事件时间 |
| 事件数 | 归因到该版本的匿名事件条数 |
| session | 归因到该版本的去重匿名 session 数 |
| 首页访问 | `visit` 且 `payload.route = home`，并且不是 `?list / ?challenge / ?payload / ?import` 深链入口的去重 session 数 |
| 加载中流失 | 仅在该版本有 `home_content_rendered` 埋点时计算：`首页访问 session - 首页已渲染 session - 已发生片单动作 session` |
| 首页渲染完成率 | 仅在该版本有 `home_content_rendered` 埋点时计算：`首页已渲染 session / 首页访问 session` |
| 加载中流失率 | 仅在该版本有 `home_content_rendered` 埋点时计算：`加载中流失 session / 首页访问 session` |
| 渲染后行动率 | 仅在该版本有 `home_content_rendered` 埋点时计算：`渲染后发生片单动作 session / 首页已渲染 session` |
| 打开/选择率 | `打开或选择片单 session / 首页访问 session` |
| 开始率 | `开始整理 session / 首页访问 session` |
| 完成率 | `完成名单 session / 开始整理 session` |
| 分享率 | `复制链接或下载海报 session / 完成名单 session` |
| P90 渲染耗时 | `home_content_rendered.payload.render_elapsed_ms` 的 P90 |
| commit | `release_history.py` 里记录的版本起始 commit |
            """.strip()
        )
        st.caption(
            "显示 --- 表示当前筛选范围内没有对应埋点或没有分母，不能解释为 0。"
            "例如老版本没有 home_content_rendered 埋点时，首页渲染完成率、加载中流失率和 P90 渲染耗时都会显示 ---。"
        )


def render_admin_version_metrics(events: List[Dict[str, Any]]) -> None:
    rows = build_version_metrics(events)
    st.markdown("**版本表现**")
    if not rows:
        st.info("当前筛选范围内没有可归因到版本的事件。")
        return

    latest = max(rows, key=version_sort_value)
    cards = [
        ("版本数", admin_int(len(rows))),
        ("最新版本", str(latest.get("release_label") or latest.get("app_version") or "")),
        ("最新版本首页访问", admin_int(latest.get("visit_sessions"))),
        ("最新版本开始率", version_percent_or_dash(latest, "start_rate", "visit_sessions")),
    ]
    columns = st.columns(len(cards))
    for column, (label, value) in zip(columns, cards):
        with column:
            st.metric(label, value)

    st.markdown("**版本总览**")
    render_version_metric_definitions()
    render_admin_dataframe(pd.DataFrame(build_version_overview_display(rows)))

    chronological = sorted(rows, key=version_sort_value)
    chart_rows = [
        {
            "版本": row.get("app_version", ""),
            "首页渲染完成率": version_rate_value_or_none(row, "home_render_rate", "visit_sessions", require_home_load=True),
            "加载中流失率": version_rate_value_or_none(row, "pre_render_loss_rate", "visit_sessions", require_home_load=True),
            "开始率": version_rate_value_or_none(row, "start_rate", "visit_sessions"),
            "完成率": version_rate_value_or_none(row, "completion_rate", "started_sessions"),
            "分享率": version_rate_value_or_none(row, "share_rate", "completed_sessions"),
        }
        for row in chronological
    ]
    if len(chart_rows) >= 2:
        st.markdown("**版本趋势**")
        st.line_chart(pd.DataFrame(chart_rows).set_index("版本"))

    st.markdown("**相邻版本对比**")
    comparison_rows = build_version_comparison_display(rows)
    if comparison_rows:
        render_admin_dataframe(pd.DataFrame(comparison_rows))
    else:
        st.info("当前筛选范围内只有一个版本，暂时无法做相邻版本对比。")

    st.markdown("**单版本详情**")
    label_to_row = {str(row.get("release_label") or row.get("app_version") or ""): row for row in rows}
    labels = list(label_to_row.keys())
    selected_label = st.selectbox("选择版本", labels, key="admin_version_detail_select")
    selected = label_to_row[selected_label]
    previous_rows = [row for row in chronological if version_sort_value(row) < version_sort_value(selected)]
    previous = previous_rows[-1] if previous_rows else None

    metric_cards = [
        ("首页访问", admin_int(selected.get("visit_sessions"))),
        ("加载中流失", version_count_or_dash(selected, "pre_render_lost_sessions", require_home_load=True)),
        ("内容已渲染", version_count_or_dash(selected, "home_rendered_sessions", require_home_load=True)),
        ("渲染后行动", version_count_or_dash(selected, "home_engaged_sessions", require_home_load=True)),
        ("开始整理", admin_int(selected.get("started_sessions"))),
        ("完成名单", admin_int(selected.get("completed_sessions"))),
        ("分享/海报", admin_int(selected.get("shared_sessions"))),
        ("P90 渲染耗时", version_ms_or_dash(selected, "p90_render_elapsed_ms", require_render_time=True)),
    ]
    columns = st.columns(4)
    for index, (label, value) in enumerate(metric_cards):
        with columns[index % 4]:
            st.metric(label, value)

    detail_rows = [
        (
            "首页访问",
            admin_int(selected.get("visit_sessions")),
            "100.0%" if int(selected.get("visit_sessions", 0) or 0) > 0 else VERSION_NO_DATA,
        ),
        (
            "首页核心内容已渲染",
            version_count_or_dash(selected, "home_rendered_sessions", require_home_load=True),
            version_percent_or_dash(selected, "home_render_rate", "visit_sessions", require_home_load=True),
        ),
        (
            "打开/选择片单",
            admin_int(selected.get("opened_or_selected_sessions")),
            version_percent_or_dash(selected, "open_or_select_rate", "visit_sessions"),
        ),
        (
            "开始整理",
            admin_int(selected.get("started_sessions")),
            version_percent_or_dash(selected, "start_rate", "visit_sessions"),
        ),
        (
            "完成名单",
            admin_int(selected.get("completed_sessions")),
            version_percent_or_dash(selected, "completion_rate", "started_sessions"),
        ),
        (
            "分享/下载海报",
            admin_int(selected.get("shared_sessions")),
            version_percent_or_dash(selected, "share_rate", "completed_sessions"),
        ),
    ]
    render_admin_dataframe(
        pd.DataFrame(
            {
                "阶段": [row[0] for row in detail_rows],
                "session 数": [row[1] for row in detail_rows],
                "核心转化率": [row[2] for row in detail_rows],
            }
        )
    )
    if previous:
        st.info(
            "相对上一版本："
            f"首页渲染完成率 {admin_delta_pp(version_rate_value_or_none(selected, 'home_render_rate', 'visit_sessions', require_home_load=True), version_rate_value_or_none(previous, 'home_render_rate', 'visit_sessions', require_home_load=True))}，"
            f"加载中流失率 {admin_delta_pp(version_rate_value_or_none(selected, 'pre_render_loss_rate', 'visit_sessions', require_home_load=True), version_rate_value_or_none(previous, 'pre_render_loss_rate', 'visit_sessions', require_home_load=True))}，"
            f"开始率 {admin_delta_pp(version_rate_value_or_none(selected, 'start_rate', 'visit_sessions'), version_rate_value_or_none(previous, 'start_rate', 'visit_sessions'))}，"
            f"完成率 {admin_delta_pp(version_rate_value_or_none(selected, 'completion_rate', 'started_sessions'), version_rate_value_or_none(previous, 'completion_rate', 'started_sessions'))}。"
        )
    st.caption(
        "说明：新版事件优先使用 payload.app_version；历史事件没有版本字段时，按 created_at 落到 release_history.py 的上线时间区间。"
    )


def admin_group_df(rows: List[Dict[str, Any]], label_key: str, label_name: str, include_winners: bool = False) -> pd.DataFrame:
    if not rows:
        return pd.DataFrame()
    display_rows: List[Dict[str, Any]] = []
    for row in rows:
        item = {
            label_name: row.get(label_key, ""),
            "访问": int(row.get("visits", row.get("page_views", 0))),
            "打开": int(row.get("list_opened", row.get("challenge_opened", 0))),
            "选择": int(row.get("list_selected", 0)),
            "开始": int(row.get("started", 0)),
            "完成": int(row.get("completed", 0)),
            "复制分享": int(row.get("copied", 0)),
            "下载海报": int(row.get("posters", 0)),
            "开始率": admin_percent(row.get("start_rate")),
            "完成率": admin_percent(row.get("completion_rate")),
            "分享率": admin_percent(row.get("share_rate")),
            "海报下载率": admin_percent(row.get("poster_rate")),
            "平均取舍": round(float(row.get("avg_comparisons", 0.0)), 1),
            "平均规模": round(float(row.get("avg_list_size", row.get("avg_total", 0.0))), 1),
            "最近活跃": admin_short_time(row.get("last_seen")),
        }
        for optional_key, display_name in [
            ("template_id", "template_id"),
            ("mode", "mode"),
            ("utm_source", "utm_source"),
            ("utm_medium", "utm_medium"),
            ("utm_campaign", "utm_campaign"),
            ("experiment_id", "experiment_id"),
            ("variant_id", "variant_id"),
        ]:
            if optional_key in row:
                item[display_name] = row.get(optional_key, "")
        if include_winners:
            item["冠军 Top3"] = row.get("top_winners", "")
        display_rows.append(item)
    return pd.DataFrame(display_rows)


def render_admin_group_section(
    title: str,
    rows: List[Dict[str, Any]],
    label_key: str,
    label_name: str,
    *,
    include_winners: bool = False,
) -> None:
    st.markdown(f"**{title}**")
    if not rows:
        st.info("当前筛选范围内没有数据。")
        return
    display = admin_group_df(rows, label_key, label_name, include_winners=include_winners)
    chart_columns = [label_name, "完成", "开始"]
    chart_source = display[chart_columns].head(12).set_index(label_name)
    chart_col, table_col = st.columns([1, 1.8])
    with chart_col:
        st.bar_chart(chart_source)
    with table_col:
        render_admin_dataframe(display)


def render_admin_trends(events: List[Dict[str, Any]]) -> None:
    daily_rows = build_daily_metrics(events)
    if not daily_rows:
        st.info("当前筛选范围内没有趋势数据。")
        return
    daily = pd.DataFrame(daily_rows).set_index("date")
    event_cols = [
        EVENT_PAGE_VIEW,
        EVENT_CHALLENGE_OPENED,
        EVENT_LIST_SELECTED,
        EVENT_RANKING_STARTED,
        EVENT_RANKING_COMPLETED,
        EVENT_SHARE_LINK_COPIED,
        EVENT_POSTER_DOWNLOADED,
        EVENT_HOME_CONTENT_RENDERED,
    ]
    event_chart = daily[[column for column in event_cols if column in daily.columns]].rename(columns=EVENT_LABELS)
    rate_chart = (daily[["start_rate", "completion_rate", "share_rate", "poster_rate"]] * 100).rename(
        columns={
            "start_rate": "开始率",
            "completion_rate": "完成率",
            "share_rate": "复制/完成",
            "poster_rate": "海报/完成",
        }
    )
    event_tab, rate_tab, data_tab = st.tabs(["事件趋势", "转化趋势", "趋势数据"])
    with event_tab:
        st.line_chart(event_chart)
    with rate_tab:
        st.line_chart(rate_chart)
        st.caption("转化趋势以百分比数值展示。")
    with data_tab:
        display = daily.reset_index().rename(columns={"date": "日期", **EVENT_LABELS})
        render_admin_dataframe(display)
        render_download_button_compat(
            "下载每日趋势 CSV",
            display.to_csv(index=False).encode("utf-8-sig"),
            "admin_daily_metrics_v2.csv",
            "text/csv",
            "admin_download_daily_metrics_v2",
        )


def render_admin_recent_events(events: List[Dict[str, Any]]) -> None:
    canonical_names = [
        EVENT_PAGE_VIEW,
        EVENT_CHALLENGE_OPENED,
        EVENT_LIST_SELECTED,
        EVENT_RANKING_STARTED,
        EVENT_COMPARISON_MADE,
        EVENT_RANKING_COMPLETED,
        EVENT_RESULT_VIEWED,
        EVENT_QR_VIEWED,
        EVENT_SHARE_LINK_COPIED,
        EVENT_POSTER_DOWNLOADED,
    ]
    label_to_name = {EVENT_LABELS.get(name, name): name for name in canonical_names}
    selected_labels = st.multiselect("事件类型", list(label_to_name.keys()), default=list(label_to_name.keys()), key="admin_recent_event_labels_v2")
    selected_names = {label_to_name[label] for label in selected_labels}
    search_col1, search_col2, search_col3, search_col4 = st.columns([1, 1, 1, 1])
    with search_col1:
        session_query = st.text_input("Session 后 8 位", key="admin_recent_session_query_v2").strip().lower()
    with search_col2:
        template_query = st.text_input("Template ID", key="admin_recent_template_query_v2").strip().lower()
    with search_col3:
        list_query = st.text_input("List ID", key="admin_recent_list_query_v2").strip().lower()
    with search_col4:
        limit = st.number_input("展示条数", min_value=20, max_value=1000, value=200, step=20, key="admin_recent_limit_v2")

    filtered: List[Dict[str, Any]] = []
    for event in events:
        if event.get("event_name") not in selected_names:
            continue
        session_id = str(event.get("session_id") or "").lower()
        template_id = str(event.get("template_id") or event.get("payload", {}).get("template_id") or "").lower()
        list_id = str(event.get("payload", {}).get("list_id") or event.get("challenge_id") or "").lower()
        if session_query and session_query not in session_id[-8:]:
            continue
        if template_query and template_query not in template_id:
            continue
        if list_query and list_query not in list_id:
            continue
        filtered.append(event)

    rows = build_event_table_rows(filtered, int(limit))
    if not rows:
        st.info("当前筛选条件下没有事件。")
        return
    frame = pd.DataFrame(rows)
    render_admin_dataframe(frame)
    render_download_button_compat(
        "下载当前事件 CSV",
        frame.to_csv(index=False).encode("utf-8-sig"),
        "admin_events_v2.csv",
        "text/csv",
        "admin_download_events_v2",
    )


def render_admin_dashboard() -> None:
    ensure_pandas()
    token = get_query_param("admin")
    expected = get_admin_token()
    if not expected or token != expected:
        st.error("后台口令无效或未配置。")
        return

    st.title("电影审美名单 · Admin Analytics v2")
    if not analytics_enabled():
        st.warning("Supabase 还没有配置，暂时没有可展示的数据。")
        return

    if render_button_compat("刷新数据缓存", key="admin_refresh_cache_v2", use_container_width=False):
        try:
            fetch_all_events.clear()
        except Exception:
            pass
        rerun()

    all_events = fetch_all_events()
    min_event_date, max_event_date = available_event_date_range(all_events)
    if not all_events or min_event_date is None or max_event_date is None:
        st.info("Supabase 已配置，但 analytics_events 里还没有可展示的事件。")
        return

    st.caption(f"已读取历史事件 {len(all_events):,} 条。统计基于匿名事件，不包含姓名、IP、联系方式或原始 user_agent。")
    filter_col1, filter_col2, filter_col3 = st.columns([1, 1, 1])
    with filter_col1:
        range_option = st.selectbox(
            "时间范围",
            ["最近 7 天", "最近 30 天", "全部历史", "自定义"],
            index=1,
            key="admin_range_option_v2",
        )

    if range_option == "最近 7 天":
        start_date = max(min_event_date, max_event_date - timedelta(days=6))
        end_date = max_event_date
    elif range_option == "最近 30 天":
        start_date = max(min_event_date, max_event_date - timedelta(days=29))
        end_date = max_event_date
    elif range_option == "全部历史":
        start_date = min_event_date
        end_date = max_event_date
    else:
        default_start = max(min_event_date, max_event_date - timedelta(days=29))
        with filter_col2:
            start_date = st.date_input("开始日期", value=default_start, min_value=min_event_date, max_value=max_event_date, key="admin_custom_start_date_v2")
        with filter_col3:
            end_date = st.date_input("结束日期", value=max_event_date, min_value=min_event_date, max_value=max_event_date, key="admin_custom_end_date_v2")

    if range_option != "自定义":
        with filter_col2:
            st.metric("开始日期", start_date.isoformat())
        with filter_col3:
            st.metric("结束日期", end_date.isoformat())

    if isinstance(start_date, tuple):
        start_date = start_date[0]
    if isinstance(end_date, tuple):
        end_date = end_date[-1]
    if start_date > end_date:
        st.warning("开始日期晚于结束日期，已自动交换。")
        start_date, end_date = end_date, start_date

    events = filter_events_by_date(all_events, start_date, end_date)
    st.caption(f"当前筛选：{start_date.isoformat()} 至 {end_date.isoformat()}，共 {len(events):,} 条事件。")
    if not events:
        st.info("当前时间范围内没有事件。")
        return

    summary = build_admin_summary(events)
    render_admin_metric_grid(summary)
    safe_divider()
    render_admin_insights(build_admin_insights(events))
    safe_divider()

    funnel_tab, load_tab, version_tab, trend_tab, list_tab, channel_tab, experiment_tab, behavior_tab, share_tab, event_tab = st.tabs(
        ["漏斗分析", "首页加载诊断", "版本分析", "每日趋势", "片单分析", "渠道归因", "实验分析", "行为质量", "分享素材", "最近事件"]
    )

    with funnel_tab:
        render_admin_instrumentation_note(events)
        safe_divider()
        render_admin_session_funnel(
            "总漏斗（当前埋点，按 session）",
            build_current_total_funnel_rows(events),
            "从 home_content_rendered 起算，只统计能确认首页核心内容已渲染的当前埋点 session；旧埋点数据不进入这个漏斗分母。",
        )
        safe_divider()
        two_col_a, two_col_b = st.columns(2)
        with two_col_a:
            render_admin_session_funnel(
                "轻量片单漏斗",
                build_light_list_funnel_rows(events),
                "轻量片单指从 ?list / ?challenge / ?payload 直接打开并开始整理的片单，当前口径从 list_opened 起算。",
            )
        with two_col_b:
            render_admin_session_funnel(
                "重链路漏斗（豆瓣已看 / 自填 / 参数页）",
                build_heavy_list_funnel_rows(events),
                "重链路从 list_selected 起算；这里把它作为“进入填参数/配置页”的代理事件，再观察实际开始、完成和传播。",
            )
        safe_divider()
        render_admin_funnel(
            "历史兼容事件数漏斗（旧口径参考）",
            build_funnel_rows(events, MAIN_FUNNEL_STEPS),
            "这是事件总量口径，用于兼容改埋点前的数据；不建议用它判断新版分步漏斗的精确流失。",
        )

    with load_tab:
        render_admin_home_load_diagnostics(events)

    with version_tab:
        render_admin_version_metrics(events)

    with trend_tab:
        render_admin_trends(events)

    with list_tab:
        sort_label = st.selectbox("片单排序", ["完成数", "完成率", "开始数", "访问数"], key="admin_list_sort_v2")
        sort_map = {"完成数": "completed", "完成率": "completion_rate", "开始数": "started", "访问数": "visits"}
        render_admin_group_section("片单维度表现", build_list_metrics(events, sort_by=sort_map[sort_label], top_n=100), "list_id", "list_id")
        safe_divider()
        render_admin_group_section("模式维度表现", build_group_metrics(events, "mode", label_key="mode", include_unknown=True, top_n=30), "mode", "mode")

    with channel_tab:
        render_admin_group_section("渠道归因表现", build_channel_metrics(events, top_n=100), "source", "source")

    with experiment_tab:
        render_admin_group_section("A/B 实验表现", build_experiment_metrics(events, top_n=100), "experiment_variant", "experiment_variant")

    with behavior_tab:
        q1, q2, q3, q4 = st.columns(4)
        with q1:
            st.metric("取舍中位数", admin_float(summary.get("median_comparisons")))
        with q2:
            st.metric("取舍 P75", admin_float(summary.get("p75_comparisons")))
        with q3:
            st.metric("取舍 P90", admin_float(summary.get("p90_comparisons")))
        with q4:
            st.metric("平均暂放", admin_float(summary.get("avg_defers")))
        h1, h2 = st.columns(2)
        with h1:
            render_admin_count_chart(
                build_numeric_payload_histogram(events, EVENT_RANKING_COMPLETED, "comparisons", [10, 20, 40, 80, 120, 200], label_key="取舍次数"),
                "取舍次数",
                "取舍次数分布",
            )
        with h2:
            render_admin_count_chart(
                build_numeric_payload_histogram(events, EVENT_RANKING_COMPLETED, "total", [10, 20, 50, 100, 250, 500, 1000], label_key="片单规模"),
                "片单规模",
                "片单规模分布",
            )
        safe_divider()
        k1, k2 = st.columns(2)
        with k1:
            render_admin_count_chart(build_top_k_distribution(events), "top_k", "Top K 设置分布")
        with k2:
            setting_rows = build_setting_rows(events)
            if setting_rows:
                settings_display = pd.DataFrame(
                    {
                        "设置": [row["setting"] for row in setting_rows],
                        "次数": [row["count"] for row in setting_rows],
                        "占开始比例": [admin_percent(row["rate"]) for row in setting_rows],
                    }
                )
                st.markdown("**交互设置使用率**")
                st.bar_chart(pd.DataFrame(setting_rows).set_index("setting")[["count"]])
                render_admin_dataframe(settings_display)
            else:
                st.info("当前筛选范围内没有设置数据。")

    with share_tab:
        c1, c2 = st.columns(2)
        with c1:
            render_admin_count_chart(
                build_payload_value_counts(events, EVENT_SHARE_LINK_COPIED, "surface", label_key="分享入口", include_empty=True),
                "分享入口",
                "分享动作拆分",
            )
        with c2:
            render_admin_count_chart(
                build_payload_value_counts(events, EVENT_POSTER_DOWNLOADED, "poster_type", label_key="海报类型", include_empty=True),
                "海报类型",
                "海报下载拆分",
            )

    with event_tab:
        render_admin_recent_events(events)


def render_cover_header() -> None:
    experiment_config = get_experiment_config(get_session_id(), "homepage_cta_v1", {"hero_title": HERO_TITLE})
    hero_title = str(experiment_config.get("hero_title") or HERO_TITLE)
    hero_title_html = html.escape(hero_title).replace("你的电影审美名单", "你的<br>电影审美名单").replace("你的电影审美榜单", "你的<br>电影审美榜单")
    st.markdown(
        f"""
        <div class="launch-hero">
          <div class="hero-copy">
            <div class="hero-kicker">电影片单整理器</div>
            <h1 class="hero-title">{hero_title_html}</h1>
            <p class="hero-subtitle">{html.escape(HERO_SUBTITLE)} {html.escape(HERO_TAGLINE)}</p>
            <div class="hero-outcomes">
              <div class="hero-outcome">得到一份 Top 榜单</div>
              <div class="hero-outcome">看见你的冠军电影</div>
              <div class="hero-outcome">生成结果海报</div>
              <div class="hero-outcome">复制链接给朋友同题挑战</div>
            </div>
          </div>
          <div class="example-card">
            <div class="example-eyebrow">完成后会得到</div>
            <div class="example-title">我的电影审美 Top 10</div>
            <div class="example-champion">
              <div class="example-champion-label">冠军电影</div>
              <div class="example-champion-name">千与千寻</div>
            </div>
            <div class="example-rank"><span>#02</span><div>星际穿越</div></div>
            <div class="example-rank"><span>#03</span><div>霸王别姬</div></div>
            <div class="example-rank"><span>#04</span><div>盗梦空间</div></div>
            <div class="example-footer">
              <div class="example-result-chip">结果海报</div>
              <div class="example-result-chip">片单链接</div>
            </div>
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

    poster_bytes = get_best_poster_bytes(name, get_source_poster_url(name))
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
    ensure_pillow()
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
    qr_option: str = SHARE_POSTER_QR_OPTIONS[0],
) -> str:
    return "|".join(
        [
            theme,
            mode,
            user_name,
            poster_style,
            poster_format,
            qr_option,
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

    poster_bytes = get_best_poster_bytes(title, get_source_poster_url(title))
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
    include_qr: bool = True,
    poster_bytes_map: Optional[Dict[str, Optional[bytes]]] = None,
) -> bytes:
    ensure_pillow()
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
    share_url = share_url or get_public_app_url()

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
    qr_block_height = 184 if include_qr else 0
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

    content_height = padding + header_height + len(ranked_layout) * (row_height + row_gap)
    if len(display_ranked) < len(ranked):
        content_height += 38
    content_height += (qr_block_height + 20 if include_qr else 0) + bottom_margin
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
        if idx <= 3:
            draw_medal_icon(draw, padding + 4, y + 42, idx, small_font)
        else:
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

    if include_qr:
        qr_y = min(max(y + 12, height - padding - qr_block_height), height - padding - qr_block_height)
        draw.rounded_rectangle((padding, qr_y, width - padding, qr_y + qr_block_height), radius=24, fill=(255, 255, 255), outline=palette["outline"], width=2)
        qr_img = make_qr_image(share_url, 144)
        img.paste(qr_img, (padding + 20, qr_y + 20))
        qr_text_x = padding + 188
        draw.text((qr_text_x, qr_y + 30), "扫码打开电影审美名单", font=subtitle_font, fill=(31, 35, 40))
        draw.text((qr_text_x, qr_y + 72), "发给朋友，让 TA 也排同一份片单。", font=small_font, fill=(98, 106, 120))
        for idx, line in enumerate(wrap_text(draw, share_url, tiny_font, width - qr_text_x - padding - 20)[:2]):
            draw.text((qr_text_x, qr_y + 112 + idx * 24), line, font=tiny_font, fill=(112, 118, 130))

    footer = f"{APP_TITLE} · {datetime.now().strftime('%Y-%m-%d %H:%M')}"
    draw.text((padding, height - 70), footer, font=small_font, fill=palette["muted"])

    out = io.BytesIO()
    img.save(out, format="PNG")
    return out.getvalue()


def generate_challenge_poster_bytes(theme: str, challenge_url: str, item_count: int) -> bytes:
    ensure_pillow()
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


def normalize_contested_pair(contested: dict, ranked: List[str]) -> dict:
    left = str(contested.get("left") or "").strip()
    right = str(contested.get("right") or "").strip()
    for item in ranked:
        if not left:
            left = item
        elif not right and item != left:
            right = item
            break
    if not right:
        right = "另一部电影"
    return {
        "left": left,
        "right": right,
        "label": str(contested.get("label") or "最纠结的一组选择"),
        "note": str(contested.get("note") or "这组选择参与决定了你的榜单气质。"),
    }


def build_contested_poster_signature(theme: str, contested: dict, share_url: str) -> str:
    return "|".join(
        [
            theme,
            str(contested.get("left") or ""),
            str(contested.get("right") or ""),
            str(contested.get("label") or ""),
            str(contested.get("note") or ""),
            share_url,
        ]
    )


def draw_choice_movie_card(
    img: Image.Image,
    draw: ImageDraw.ImageDraw,
    *,
    box: Tuple[int, int, int, int],
    title: str,
    poster_bytes: Optional[bytes],
    hotkey: str,
    title_font: ImageFont.ImageFont,
    body_font: ImageFont.ImageFont,
    tiny_font: ImageFont.ImageFont,
) -> None:
    x1, y1, x2, y2 = box
    draw.rounded_rectangle(box, radius=22, fill=(255, 253, 249), outline=(224, 206, 188), width=2)
    poster_size = (112, 164)
    poster_x = x1 + 34
    poster_y = y1 + 54
    poster_thumb = render_poster_thumb(poster_bytes, poster_size, (239, 236, 230))
    poster_mask = make_rounded_rect_mask(poster_size, 14)
    if poster_bytes:
        img.paste(poster_thumb, (poster_x, poster_y), poster_mask)
    else:
        draw.rounded_rectangle(
            (poster_x, poster_y, poster_x + poster_size[0], poster_y + poster_size[1]),
            radius=14,
            fill=(239, 236, 230),
            outline=(224, 206, 188),
            width=1,
        )
        draw.text((poster_x + 34, poster_y + 82), "暂无\n海报", font=tiny_font, fill=(126, 118, 108), spacing=6)

    text_x = poster_x + poster_size[0] + 28
    text_width = x2 - text_x - 28
    title_lines = wrap_text(draw, title, title_font, text_width)[:2]
    text_y = y1 + 58
    for line in title_lines:
        draw.text((text_x, text_y), line, font=title_font, fill=(31, 35, 40))
        text_y += 42
    note_lines = wrap_text(draw, "更喜欢它", body_font, text_width)[:1]
    text_y += 10
    for line in note_lines:
        draw.text((text_x, text_y), line, font=body_font, fill=(112, 105, 96))
        text_y += 34

    chip_w, chip_h = 126, 48
    chip_x = x2 - chip_w - 28
    chip_y = y2 - chip_h - 26
    draw.rounded_rectangle((chip_x, chip_y, chip_x + chip_w, chip_y + chip_h), radius=16, fill=(248, 243, 236), outline=(224, 206, 188), width=1)
    bbox = draw.textbbox((0, 0), hotkey, font=body_font)
    draw.text(
        (chip_x + (chip_w - (bbox[2] - bbox[0])) / 2, chip_y + (chip_h - (bbox[3] - bbox[1])) / 2 - 2),
        hotkey,
        font=body_font,
        fill=(157, 91, 73),
    )


def generate_contested_poster_bytes(
    theme: str,
    contested: dict,
    share_url: str,
    poster_bytes_map: Optional[Dict[str, Optional[bytes]]] = None,
) -> bytes:
    ensure_pillow()
    width, height = 1080, 1350
    poster_bytes_map = poster_bytes_map or {}
    left = str(contested.get("left") or "")
    right = str(contested.get("right") or "")
    label = str(contested.get("label") or "最纠结的一组选择")
    note = str(contested.get("note") or "这组选择参与决定了你的榜单气质。")
    share_url = share_url or get_public_app_url()
    scan_url = get_public_app_url()

    img = Image.new("RGB", (width, height), (218, 212, 203))
    draw = ImageDraw.Draw(img)
    draw.polygon([(0, 0), (width, 0), (width, 270), (0, 430)], fill=(233, 224, 214))
    draw.polygon([(0, height), (width, height), (width, 1040), (0, 1160)], fill=(202, 198, 191))
    draw.rounded_rectangle((52, 52, width - 52, height - 52), radius=36, fill=(255, 252, 246), outline=(224, 206, 188), width=2)

    kicker_font = load_font(28, bold=True)
    title_font = load_font(58, bold=True)
    subtitle_font = load_font(34, bold=True)
    body_font = load_font(28)
    small_font = load_font(23)
    tiny_font = load_font(20)

    y = 104
    draw.text((86, y), "电影审美名单 · 最纠结取舍", font=kicker_font, fill=(157, 91, 73))
    y += 68
    for line in wrap_text(draw, "这两部里，你更偏爱哪一部？", title_font, width - 172)[:2]:
        draw.text((86, y), line, font=title_font, fill=(31, 35, 40))
        y += 68

    intro_lines = wrap_text(draw, f"在「{theme}」里，{note}", body_font, width - 172)[:3]
    for line in intro_lines:
        draw.text((86, y), line, font=body_font, fill=(112, 105, 96))
        y += 38

    y += 34
    draw.rounded_rectangle((86, y, width - 86, y + 164), radius=24, fill=(255, 253, 249), outline=(224, 206, 188), width=2)
    draw.text((122, y + 34), f"这组选择 · {label}", font=small_font, fill=(157, 91, 73))
    pair_title = f"{left}  VS  {right}"
    for idx, line in enumerate(wrap_text(draw, pair_title, subtitle_font, width - 300)[:2]):
        draw.text((122, y + 76 + idx * 42), line, font=subtitle_font, fill=(31, 35, 40))
    y += 224

    battle_box = (86, y, width - 86, y + 438)
    draw.rounded_rectangle(battle_box, radius=26, fill=(255, 253, 249), outline=(224, 206, 188), width=2)
    draw.text((122, y + 44), "如果重新遇到这一题，你会怎么选？", font=subtitle_font, fill=(31, 35, 40))
    draw.line((122, y + 104, width - 122, y + 104), fill=(226, 214, 201), width=4)

    card_y = y + 150
    card_h = 248
    gap = 24
    card_w = (width - 244 - gap) // 2
    draw_choice_movie_card(
        img,
        draw,
        box=(122, card_y, 122 + card_w, card_y + card_h),
        title=left,
        poster_bytes=poster_bytes_map.get(left),
        hotkey="A / ←",
        title_font=subtitle_font,
        body_font=body_font,
        tiny_font=tiny_font,
    )
    draw_choice_movie_card(
        img,
        draw,
        box=(122 + card_w + gap, card_y, 122 + card_w * 2 + gap, card_y + card_h),
        title=right,
        poster_bytes=poster_bytes_map.get(right),
        hotkey="D / →",
        title_font=subtitle_font,
        body_font=body_font,
        tiny_font=tiny_font,
    )

    qr_y = height - 234
    qr_img = make_qr_image(scan_url, 150)
    img.paste(qr_img, (110, qr_y))
    qr_text_x = 300
    draw.text((qr_text_x, qr_y + 18), "扫码试试：把自己的已看电影排出来", font=subtitle_font, fill=(31, 35, 40))
    for idx, line in enumerate(wrap_text(draw, scan_url, body_font, width - qr_text_x - 100)[:2]):
        draw.text((qr_text_x, qr_y + 74 + idx * 36), line, font=body_font, fill=(112, 105, 96))

    footer = f"{APP_TITLE} · {datetime.now().strftime('%Y-%m-%d')}"
    draw.text((86, height - 88), footer, font=small_font, fill=(112, 105, 96))

    out = io.BytesIO()
    img.save(out, format="PNG")
    return out.getvalue()


def ensure_share_poster_generated(share_url: str = "") -> None:
    ranked = st.session_state.get(k("ranked"), [])
    if not ranked:
        return
    share_url = share_url or get_public_app_url()

    theme = st.session_state.get(k("theme"), "我的排序")
    skipped_items = st.session_state.get(k("skipped_items"), [])
    top_k = st.session_state.get(k("top_k"))
    mode = st.session_state.get(k("mode"), MODE_CUSTOM)
    user_name = st.session_state.get(k("user_name"), "")
    poster_style = st.session_state.get(k("share_poster_style"), SHARE_POSTER_STYLES[0])
    poster_format = st.session_state.get(k("share_poster_format"), SHARE_POSTER_FORMATS[0])
    qr_option = st.session_state.get(k("share_poster_qr_option"), SHARE_POSTER_QR_OPTIONS[0])
    include_qr = qr_option == SHARE_POSTER_QR_OPTIONS[0]
    signature = build_share_poster_signature(theme, ranked, skipped_items, top_k, mode, user_name, poster_style, poster_format, share_url, qr_option)

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
        include_qr=include_qr,
        poster_bytes_map=poster_bytes_map,
    )
    st.session_state[k("share_poster_bytes")] = poster_bytes
    st.session_state[k("share_poster_signature")] = signature


def ensure_contested_poster_generated(share_url: str = "") -> None:
    ranked = st.session_state.get(k("ranked"), [])
    if not ranked:
        return
    share_url = share_url or get_public_app_url()
    theme = st.session_state.get(k("theme"), "我的电影审美名单")
    contested = normalize_contested_pair(get_most_contested_pair(), ranked)
    signature = build_contested_poster_signature(theme, contested, share_url)
    if st.session_state.get(k("contested_poster_signature")) == signature and st.session_state.get(k("contested_poster_bytes")):
        return

    titles = [title for title in [contested.get("left"), contested.get("right")] if title and title != "另一部电影"]
    poster_bytes_map = {title: get_result_poster_bytes(str(title)) for title in titles}
    poster_bytes = generate_contested_poster_bytes(
        theme,
        contested,
        share_url,
        poster_bytes_map=poster_bytes_map,
    )
    st.session_state[k("contested_poster_bytes")] = poster_bytes
    st.session_state[k("contested_poster_signature")] = signature


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
        payload = build_event_payload(
            route="result",
            list_id=challenge_id or template_id or st.session_state.get(k("mode"), MODE_CUSTOM),
            list_size=total,
            total=total,
            ranked_count=len(ranked),
            skipped_count=len(skipped_items),
            comparison_count=comparisons,
            comparisons=comparisons,
            top_k=top_k,
            defers=defers,
            session_hint=get_session_id()[-8:],
        )
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

    if st.session_state.get(k("result_view_event_signature")) != completion_signature:
        track_event(
            EVENT_RESULT_VIEWED,
            challenge_id=challenge_id,
            mode=st.session_state.get(k("mode"), MODE_CUSTOM),
            template_id=template_id,
            source_channel=source_channel,
            payload=build_event_payload(
                route="result",
                list_id=challenge_id or template_id or st.session_state.get(k("mode"), MODE_CUSTOM),
                list_size=total,
                comparison_count=comparisons,
                top_k=top_k,
            ),
        )
        st.session_state[k("result_view_event_signature")] = completion_signature

    render_result_peak(total=total, comparisons=comparisons, top_k=top_k)
    render_result_insights(total=total, comparisons=comparisons, top_k=top_k)

    summary = f"共整理 {total} 部电影，作出 {comparisons} 次取舍。"
    if skipped_items:
        summary += f" 已略过 {len(skipped_items)} 项。"
    if defers:
        summary += f" 暂放 {defers} 次。"
    st.caption(summary)

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
    challenge_invite_text = "\n".join(
        [
            f"猜猜我这份「{theme}」的冠军电影是哪一部？",
            "我刚排完，发你同一份片单，看看你的冠军会不会一样。",
            challenge_url,
        ]
    )

    st.subheader("把结果变成海报")
    if st.session_state.get(k("share_poster_style")) not in SHARE_POSTER_STYLES:
        st.session_state[k("share_poster_style")] = SHARE_POSTER_STYLES[0]
    if st.session_state.get(k("share_poster_format")) not in SHARE_POSTER_FORMATS:
        st.session_state[k("share_poster_format")] = SHARE_POSTER_FORMATS[0]
    if st.session_state.get(k("share_poster_qr_option")) not in SHARE_POSTER_QR_OPTIONS:
        st.session_state[k("share_poster_qr_option")] = SHARE_POSTER_QR_OPTIONS[0]

    control_col1, control_col2, control_col3 = st.columns(3)
    with control_col1:
        st.selectbox(
            "海报风格",
            SHARE_POSTER_STYLES,
            key=k("share_poster_style"),
        )
    with control_col2:
        st.selectbox(
            "海报尺寸",
            SHARE_POSTER_FORMATS,
            key=k("share_poster_format"),
        )
    with control_col3:
        st.radio(
            "二维码版本",
            SHARE_POSTER_QR_OPTIONS,
            key=k("share_poster_qr_option"),
        )
    ensure_share_poster_generated(challenge_url)
    ensure_contested_poster_generated(challenge_url)

    poster_bytes = st.session_state.get(k("share_poster_bytes"), b"")
    contested_poster_bytes = st.session_state.get(k("contested_poster_bytes"), b"")
    if poster_bytes:
        file_name = f"{slugify_filename(st.session_state.get(k('theme'), 'ranking'))}_ranking.png"
        contested_file_name = f"{slugify_filename(st.session_state.get(k('theme'), 'ranking'))}_choice.png"
        preview_col, action_col = st.columns([0.95, 1.05])
        with preview_col:
            if contested_poster_bytes:
                ranking_tab, choice_tab = st.tabs(["名单海报", "最纠结取舍海报"])
                with ranking_tab:
                    render_poster_preview_html(poster_bytes)
                with choice_tab:
                    render_poster_preview_html(contested_poster_bytes)
            else:
                render_poster_preview_html(poster_bytes)
        with action_col:
            has_qr = st.session_state.get(k("share_poster_qr_option")) == SHARE_POSTER_QR_OPTIONS[0]
            if has_qr and st.session_state.get(k("qr_view_event_signature")) != completion_signature:
                track_event(
                    EVENT_QR_VIEWED,
                    challenge_id=challenge_id,
                    mode=mode,
                    template_id=template_id,
                    source_channel=source_channel,
                    payload=build_event_payload(
                        route="result",
                        list_id=challenge_id or template_id or mode,
                        list_size=total,
                        comparison_count=comparisons,
                        poster_type="result",
                    ),
                )
                st.session_state[k("qr_view_event_signature")] = completion_signature
            qr_copy = "、项目名称和二维码" if has_qr else "和项目名称"
            st.markdown(
                f"""
                <div class="poster-side-panel">
                  <div class="poster-panel-title">两张图晒出你的电影审美</div>
                  <div class="poster-panel-copy">名单海报展示前三名奖牌和前列名单{qr_copy}；取舍海报展示你最纠结的一组选择，更适合发出去让朋友参与讨论。</div>
                  <div class="challenge-invite">
                    <div class="challenge-invite-title">发给朋友，让 TA 猜你的冠军</div>
                    <div class="challenge-invite-copy">复制同题挑战链接，朋友排完后可以拿 JSON 和你对比差异。</div>
                  </div>
                </div>
                """,
                unsafe_allow_html=True,
            )
            a1, a2 = st.columns(2)
            with a1:
                render_download_button_compat(
                    "下载名单海报",
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
                        payload=build_event_payload(
                            route="result",
                            list_id=challenge_id or template_id or mode,
                            list_size=total,
                            comparison_count=comparisons,
                            poster_type="result",
                        ),
                    ),
                )
            with a2:
                if contested_poster_bytes:
                    render_download_button_compat(
                        "下载取舍海报",
                        data=contested_poster_bytes,
                        file_name=contested_file_name,
                        mime="image/png",
                        key="btn_download_contested_poster",
                        on_click=lambda: track_event(
                            EVENT_POSTER_DOWNLOADED,
                            challenge_id=challenge_id,
                            mode=st.session_state.get(k("mode"), MODE_CUSTOM),
                            template_id=template_id,
                            source_channel=source_channel,
                            payload=build_event_payload(
                                route="result",
                                list_id=challenge_id or template_id or mode,
                                list_size=total,
                                comparison_count=comparisons,
                                poster_type="contested_choice",
                            ),
                        ),
                    )
            if render_copy_button("复制链接", challenge_url, "copy_result_challenge_link", "片单链接"):
                track_event(
                    EVENT_SHARE_LINK_COPIED,
                    challenge_id=challenge_id,
                    mode=mode,
                    template_id=template_id,
                    source_channel=source_channel,
                    payload=build_event_payload(
                        route="result",
                        list_id=challenge_id or template_id or mode,
                        list_size=total,
                        comparison_count=comparisons,
                        surface="result_link",
                    ),
                )
            if render_copy_button("复制猜冠军文案", challenge_invite_text, "copy_guess_champion_caption", "猜冠军文案"):
                track_event(
                    EVENT_SHARE_LINK_COPIED,
                    challenge_id=challenge_id,
                    mode=mode,
                    template_id=template_id,
                    source_channel=source_channel,
                    payload=build_event_payload(
                        route="result",
                        list_id=challenge_id or template_id or mode,
                        list_size=total,
                        comparison_count=comparisons,
                        surface="guess_champion",
                    ),
                )
            render_peer_contact_section(
                ranked=ranked,
                mode=mode,
                challenge_id=challenge_id,
                template_id=template_id,
                total=total,
                compact=True,
            )

    with st.expander("发布文案", expanded=False):
        st.text_area("文案", value=share_caption, height=220)
        st.caption("发朋友圈、群聊或评论区时可以直接使用；JSON 可用于查看两份名单的差异。")
        if render_copy_button("复制文案", share_caption, "copy_result_share_caption", "发布文案"):
            track_event(
                EVENT_SHARE_LINK_COPIED,
                challenge_id=challenge_id,
                mode=mode,
                template_id=template_id,
                source_channel=source_channel,
                payload=build_event_payload(
                    route="result",
                    list_id=challenge_id or template_id or mode,
                    list_size=total,
                    comparison_count=comparisons,
                    surface="caption",
                ),
            )

    safe_divider()
    st.subheader("完整名单")
    render_ranked_list(ranked)

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
    render_next_template_recommendations(template_id)

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
        label_left = "跳过 / 不想排 A"
        if render_button_compat(label_left, key="btn_skip_left", use_container_width=True):
            if current_on_left:
                handle_skip_current_item()
            else:
                handle_skip_opponent_item()
    with ctrl2:
        label_right = "跳过 / 不想排 B"
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
    return st.session_state.get("ui_selected_mode", MODE_DOUBAN_COLLECT)


def set_selected_mode(mode: str) -> None:
    st.session_state["ui_selected_mode"] = mode


def render_step_header(step: int, title: str, subtitle: str = "", compact: bool = False) -> None:
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

    if title.strip():
        st.subheader(title)
    if subtitle:
        if compact:
            st.markdown(f'<div class="home-step-copy">{html.escape(subtitle)}</div>', unsafe_allow_html=True)
        else:
            st.caption(subtitle)
    if not compact:
        safe_divider()


def render_douban_collect_spotlight(homepage_cta_text: str = "开始整理") -> None:
    st.markdown(
        """
        <div class="collect-spotlight">
          <div>
            <div class="collect-spotlight-kicker">主推功能 · 豆瓣已看总榜</div>
            <div class="collect-spotlight-title">把你看过的电影排成私人总榜</div>
            <div class="collect-spotlight-copy">适合想排出自己总榜单、年度榜单或某个阶段观影坐标的用户。输入豆瓣 ID，读取公开的“看过”电影，再用一轮轮二选一整理出总榜或 Top N。</div>
          </div>
          <div class="collect-spotlight-note">可只排 Top N<br>也可整理完整总榜</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    action_col, hint_col = st.columns([1, 2.4])
    with action_col:
        if render_button_compat(homepage_cta_text, key="btn_feature_douban_collect", use_container_width=True, button_type="primary"):
            set_selected_mode(MODE_DOUBAN_COLLECT)
            track_event(
                EVENT_LIST_SELECTED,
                mode=MODE_DOUBAN_COLLECT,
                source_channel=get_source_channel(),
                payload=build_event_payload(route="home", mode=MODE_DOUBAN_COLLECT, list_id=MODE_DOUBAN_COLLECT),
            )
            go_to_step(2)
    with hint_col:
        st.caption("只读取公开可访问的“看过”页面；可以只排 Top N，也可以整理完整总榜。")


def render_builtin_quick_start_lists() -> None:
    card_html = []
    for template in FILM_CHALLENGE_TEMPLATES:
        template_id = html.escape(str(template["id"]), quote=True)
        recommendation = html.escape(str(template.get("recommendation", "")))
        card_html.append(
            f'<a class="challenge-card" href="?list={template_id}" target="_self" aria-label="整理 {html.escape(str(template["name"]), quote=True)}">'
            f'<div>'
            f'<span class="challenge-badge">{html.escape(str(template.get("badge", "电影片单")))}</span>'
            f'<div class="challenge-title">{html.escape(str(template["name"]))}</div>'
            f'<div class="challenge-copy">{html.escape(str(template.get("tagline", "")))}</div>'
            f'<div class="challenge-reason"><div class="challenge-reason-label">推荐理由</div>{recommendation}</div>'
            f'</div>'
            f'<div class="challenge-foot">'
            f'<div class="mini-note">{len(template.get("items", []))} 部电影 · 前 {template.get("top_k", 10)} 名</div>'
            f'<span class="challenge-action">开始整理</span>'
            f'</div>'
            f'</a>'
        )
    st.markdown(f'<div class="challenge-grid">{"".join(card_html)}</div>', unsafe_allow_html=True)

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
                payload=build_event_payload(
                    route="home",
                    list_id=template_id,
                    list_size=len(selected_template.get("items", [])),
                    top_k=selected_template.get("top_k"),
                    surface="home_template",
                ),
            )


def render_mode_selection_page() -> None:
    current_mode = get_selected_mode()
    mode_options = [MODE_DOUBAN_COLLECT, MODE_CUSTOM, MODE_DOUBAN]
    cta_config = get_experiment_config(get_session_id(), "homepage_cta_v1", {"cta_text": "开始整理"})
    homepage_cta_text = str(cta_config.get("cta_text") or "开始整理")
    layout_config = get_experiment_config(
        get_session_id(),
        "home_layout_order_v1",
        {"home_layout_order": "current"},
    )
    home_layout_order = str(layout_config.get("home_layout_order") or "current")
    st.session_state["home_layout_order"] = home_layout_order
    render_step_header(
        1,
        "",
        "不用先想完整顺序，只在两部电影之间作一次取舍。",
        compact=True,
    )

    if home_layout_order == "builtin_first":
        render_builtin_quick_start_lists()
        safe_divider()
        render_douban_collect_spotlight(homepage_cta_text)
    else:
        render_douban_collect_spotlight(homepage_cta_text)
        safe_divider()
        render_builtin_quick_start_lists()

    safe_divider()
    st.subheader("也可以从其他来源开始")
    mode = st.radio(
        "片单来源",
        mode_options,
        index=mode_options.index(current_mode) if current_mode in mode_options else 0,
        help="自备片单适合私人主题；豆瓣高分会读取豆瓣 Top250；豆瓣已看会读取公开的看过列表。",
        key="ui_mode_step1",
    )
    set_selected_mode(mode)

    safe_divider()
    if mode == MODE_DOUBAN_COLLECT:
        st.caption("输入豆瓣 ID，读取公开的“看过”电影列表，再排出自己的总榜或 Top N。")
    elif mode == MODE_CUSTOM:
        st.caption("把想整理的电影粘进来，也可以生成一条片单链接发给朋友。")
    else:
        st.caption("设置保留名次和候选范围，从豆瓣高分片里整理自己的顺序。")

    spacer, next_col = st.columns([1, 1])
    with spacer:
        st.empty()
    with next_col:
        if render_button_compat("继续整理", key="btn_to_step2", use_container_width=True, button_type="primary"):
            track_event(
                EVENT_LIST_SELECTED,
                mode=mode,
                source_channel=get_source_channel(),
                payload=build_event_payload(route="home", mode=mode, list_id=mode),
            )
            go_to_step(2)


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
                placeholder="例：某位影迷",
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
    st.session_state.pop("ui_import_id", None)
    st.session_state.pop("ui_import_item_count", None)
    st.session_state.pop("ui_import_poster_url_map", None)
    st.session_state.pop("ui_import_source", None)
    st.session_state.pop("ui_import_loaded_notice", None)


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


def reset_douban_collect_parameter_defaults() -> None:
    st.session_state["ui_douban_collect_user_id"] = ""
    st.session_state["ui_douban_collect_import_id"] = ""
    st.session_state["ui_douban_collect_theme"] = "我的豆瓣已看电影总榜"
    st.session_state["ui_douban_collect_scope"] = "只保留前 N 名"
    st.session_state["ui_douban_collect_top_k"] = 20
    st.session_state["ui_douban_collect_show_poster"] = True
    st.session_state["ui_douban_collect_user_name"] = ""
    st.session_state["ui_douban_collect_seed_text"] = ""
    st.session_state["ui_douban_collect_blind_mode"] = False
    st.session_state["ui_douban_collect_side_shuffle"] = True
    st.session_state["ui_douban_collect_selected_media_types"] = DOUBAN_COLLECT_MEDIA_TYPES[:]
    st.session_state["ui_douban_collect_include_unknown_media_type"] = True
    st.session_state["ui_douban_collect_selected_ratings"] = DOUBAN_RATING_VALUES[:]
    st.session_state["ui_douban_collect_include_unrated"] = True
    st.session_state.pop("ui_douban_collect_selected_years", None)
    st.session_state["ui_douban_collect_include_unknown_year"] = True
    st.session_state["ui_douban_collect_excluded_titles"] = []
    st.session_state.pop("ui_douban_collect_preview_movies", None)
    st.session_state.pop("ui_douban_collect_preview_entries", None)
    st.session_state.pop("ui_douban_collect_preview_source", None)
    st.session_state.pop("ui_douban_collect_preview_user_id", None)
    st.session_state.pop("ui_import_id", None)
    st.session_state.pop("ui_import_item_count", None)
    st.session_state.pop("ui_import_poster_url_map", None)
    st.session_state.pop("ui_import_entries", None)
    st.session_state.pop("ui_import_rating_map", None)
    st.session_state.pop("ui_import_rated_at_map", None)
    st.session_state.pop("ui_import_media_type_map", None)
    st.session_state.pop("ui_import_has_rating_data", None)
    st.session_state.pop("ui_import_has_year_data", None)
    st.session_state.pop("ui_import_has_media_type_data", None)
    st.session_state.pop("ui_import_source", None)
    st.session_state.pop("ui_import_loaded_notice", None)
    st.session_state.pop("ui_import_lookup_id", None)
    st.session_state.pop("ui_import_fetch_failed_id", None)
    st.session_state.pop("ui_import_fetch_failed_message", None)


def render_imported_list_notice() -> None:
    import_id = clean_import_id(st.session_state.get("ui_import_id", ""))
    if not import_id:
        return

    item_count = int(st.session_state.get("ui_import_item_count", 0) or 0)
    import_url = build_import_url(import_id)
    st.info(f"已导入豆瓣已看片单：{item_count} 个条目。片单 ID：{import_id}")
    c1, c2 = st.columns(2)
    with c1:
        render_copy_button("复制手机继续链接", import_url, "copy_import_url", "导入链接")
    with c2:
        render_copy_button("复制片单 ID", import_id, "copy_import_id", "片单 ID")


def render_collect_filters(
    entries: List[Dict[str, Any]],
    has_media_type_data: bool,
    has_rating_data: bool,
    has_year_data: bool,
) -> tuple[List[str], bool, List[int], bool, Optional[List[int]], bool, List[Dict[str, Any]]]:
    if "ui_douban_collect_selected_media_types" not in st.session_state:
        st.session_state["ui_douban_collect_selected_media_types"] = DOUBAN_COLLECT_MEDIA_TYPES[:]
    if "ui_douban_collect_include_unknown_media_type" not in st.session_state:
        st.session_state["ui_douban_collect_include_unknown_media_type"] = True
    if "ui_douban_collect_selected_ratings" not in st.session_state:
        st.session_state["ui_douban_collect_selected_ratings"] = DOUBAN_RATING_VALUES[:]
    if "ui_douban_collect_include_unrated" not in st.session_state:
        st.session_state["ui_douban_collect_include_unrated"] = True
    if "ui_douban_collect_include_unknown_year" not in st.session_state:
        st.session_state["ui_douban_collect_include_unknown_year"] = True

    if not entries:
        st.caption("读取片单后会显示各星级数量。")
        return DOUBAN_COLLECT_MEDIA_TYPES[:], True, DOUBAN_RATING_VALUES[:], True, None, True, []

    st.markdown("**按条目类型筛选**")
    st.caption("提示：新版读取会区分电影和剧集；旧导入片单没有类型信息时会归为未识别类型。")

    media_counts = collect_media_type_counts(entries)
    if not has_media_type_data:
        st.warning("这份片单没有类型信息。可以继续整理全部条目；如果想按电影/剧集筛选，请重新读取或重新用书签导入一次。")
        selected_media_types, include_unknown_media_type = DOUBAN_COLLECT_MEDIA_TYPES[:], True
        media_filtered_entries = entries
    else:
        stored_media_types = st.session_state.get("ui_douban_collect_selected_media_types", [])
        valid_media_types = [
            clean_media_type(media_type)
            for media_type in stored_media_types
            if clean_media_type(media_type) in DOUBAN_COLLECT_MEDIA_TYPES
        ]
        if valid_media_types != stored_media_types:
            st.session_state["ui_douban_collect_selected_media_types"] = valid_media_types

        media_cols = st.columns(4)
        with media_cols[0]:
            if render_button_compat("全部类型", key="btn_media_type_all", use_container_width=True):
                st.session_state["ui_douban_collect_selected_media_types"] = DOUBAN_COLLECT_MEDIA_TYPES[:]
                st.session_state["ui_douban_collect_include_unknown_media_type"] = True
        with media_cols[1]:
            if render_button_compat("只看电影", key="btn_media_type_movie", use_container_width=True):
                st.session_state["ui_douban_collect_selected_media_types"] = [MEDIA_TYPE_MOVIE]
                st.session_state["ui_douban_collect_include_unknown_media_type"] = False
        with media_cols[2]:
            if render_button_compat("只看剧集", key="btn_media_type_series", use_container_width=True):
                st.session_state["ui_douban_collect_selected_media_types"] = [MEDIA_TYPE_SERIES]
                st.session_state["ui_douban_collect_include_unknown_media_type"] = False
        with media_cols[3]:
            if render_button_compat("清空类型", key="btn_media_type_clear", use_container_width=True):
                st.session_state["ui_douban_collect_selected_media_types"] = []
                st.session_state["ui_douban_collect_include_unknown_media_type"] = False

        selected_media_types = st.multiselect(
            "选择要整理的类型",
            options=DOUBAN_COLLECT_MEDIA_TYPES,
            format_func=lambda media_type: f"{MEDIA_TYPE_LABELS.get(media_type, media_type)}（{media_counts.get(media_type, 0)} 部）",
            key="ui_douban_collect_selected_media_types",
        )
        include_unknown_media_type = st.checkbox(
            f"包含未识别类型（{media_counts.get(MEDIA_TYPE_UNKNOWN, 0)} 部）",
            key="ui_douban_collect_include_unknown_media_type",
        )
        media_filtered_entries = filter_collect_entries_by_media_type(entries, selected_media_types, include_unknown_media_type)

    st.markdown("**按我的豆瓣评分筛选**")
    st.caption("提示：老版本获取的片单不支持按评分筛选，使用该功能需重新获取片单。")

    counts = collect_rating_counts(media_filtered_entries)
    if not has_rating_data:
        st.warning("这份片单没有评分信息。可以继续整理全部条目；如果想按星级筛选，请重新用书签导入一次。")
        selected_ratings, include_unrated = DOUBAN_RATING_VALUES[:], True
        rating_filtered_entries = media_filtered_entries
    else:
        preset_cols = st.columns(4)
        with preset_cols[0]:
            if render_button_compat("全部", key="btn_rating_all", use_container_width=True):
                st.session_state["ui_douban_collect_selected_ratings"] = DOUBAN_RATING_VALUES[:]
                st.session_state["ui_douban_collect_include_unrated"] = True
        with preset_cols[1]:
            if render_button_compat("4 星及以上", key="btn_rating_4_up", use_container_width=True):
                st.session_state["ui_douban_collect_selected_ratings"] = [5, 4]
                st.session_state["ui_douban_collect_include_unrated"] = False
        with preset_cols[2]:
            if render_button_compat("只看 5 星", key="btn_rating_5_only", use_container_width=True):
                st.session_state["ui_douban_collect_selected_ratings"] = [5]
                st.session_state["ui_douban_collect_include_unrated"] = False
        with preset_cols[3]:
            if render_button_compat("清空星级", key="btn_rating_clear", use_container_width=True):
                st.session_state["ui_douban_collect_selected_ratings"] = []
                st.session_state["ui_douban_collect_include_unrated"] = False

        selected_ratings = st.multiselect(
            "选择要整理的评分",
            options=DOUBAN_RATING_VALUES,
            format_func=lambda rating: f"{rating} 星（{counts.get(rating, 0)} 部）",
            key="ui_douban_collect_selected_ratings",
        )
        include_unrated = st.checkbox(
            f"包含未评分 / 未识别评分（{counts.get(None, 0)} 部）",
            key="ui_douban_collect_include_unrated",
        )
        rating_filtered_entries = filter_collect_entries_by_rating(media_filtered_entries, selected_ratings, include_unrated)

    st.markdown("**按我的豆瓣标记年份筛选**")
    st.caption("提示：按“看过”页面显示的标记日期筛选，可以用来整理某一年的观影名单。")

    year_counts = collect_year_counts(rating_filtered_entries)
    available_years = sorted([year for year in year_counts if year is not None], reverse=True)
    if not has_year_data:
        st.warning("这份片单没有标记年份信息。可以继续整理当前评分筛选后的条目；如果想按年份筛选，请重新读取或重新用书签导入一次。")
        filtered_entries = rating_filtered_entries
        st.caption(f"当前筛选后：{len(filtered_entries)} 部。")
        return selected_media_types, include_unknown_media_type, selected_ratings, include_unrated, None, True, filtered_entries

    stored_years = st.session_state.get("ui_douban_collect_selected_years")
    if stored_years is None:
        st.session_state["ui_douban_collect_selected_years"] = available_years[:]
    else:
        valid_years = []
        for year in stored_years:
            try:
                year_int = int(year)
            except (TypeError, ValueError):
                continue
            if year_int in available_years:
                valid_years.append(year_int)
        if stored_years and not valid_years and available_years:
            st.session_state["ui_douban_collect_selected_years"] = available_years[:]
        elif valid_years != stored_years:
            st.session_state["ui_douban_collect_selected_years"] = valid_years

    current_year = datetime.now().year
    year_cols = st.columns(4)
    with year_cols[0]:
        if render_button_compat("全部年份", key="btn_year_all", use_container_width=True):
            st.session_state["ui_douban_collect_selected_years"] = available_years[:]
            st.session_state["ui_douban_collect_include_unknown_year"] = True
    with year_cols[1]:
        if render_button_compat("今年", key="btn_year_current", use_container_width=True):
            st.session_state["ui_douban_collect_selected_years"] = [current_year] if current_year in available_years else []
            st.session_state["ui_douban_collect_include_unknown_year"] = False
    with year_cols[2]:
        if render_button_compat("去年", key="btn_year_previous", use_container_width=True):
            previous_year = current_year - 1
            st.session_state["ui_douban_collect_selected_years"] = [previous_year] if previous_year in available_years else []
            st.session_state["ui_douban_collect_include_unknown_year"] = False
    with year_cols[3]:
        if render_button_compat("清空年份", key="btn_year_clear", use_container_width=True):
            st.session_state["ui_douban_collect_selected_years"] = []
            st.session_state["ui_douban_collect_include_unknown_year"] = False

    selected_years = st.multiselect(
        "选择要整理的标记年份",
        options=available_years,
        format_func=lambda year: f"{year} 年（{year_counts.get(year, 0)} 部）",
        key="ui_douban_collect_selected_years",
    )
    include_unknown_year = st.checkbox(
        f"包含未识别年份（{year_counts.get(None, 0)} 部）",
        key="ui_douban_collect_include_unknown_year",
    )

    filtered_entries = filter_collect_entries_by_year(rating_filtered_entries, selected_years, include_unknown_year)
    st.caption(f"当前筛选后：{len(filtered_entries)} 部。")
    return selected_media_types, include_unknown_media_type, selected_ratings, include_unrated, selected_years, include_unknown_year, filtered_entries


def render_import_id_loader() -> None:
    failed_id = clean_import_id(st.session_state.get("ui_import_fetch_failed_id", ""))
    failed_message = st.session_state.get("ui_import_fetch_failed_message", "")
    if failed_id:
        st.warning(f"{failed_message} 当前片单 ID：{failed_id}")

    st.text_input(
        "已有片单 ID",
        key="ui_import_lookup_id",
        placeholder="例：db-0123456789abcdef",
        help="电脑导入后会生成片单 ID。手机或另一台电脑输入这个 ID，就能打开同一份片单。",
    )
    import_id = clean_import_id(st.session_state.get("ui_import_lookup_id", ""))
    c1, c2 = st.columns(2)
    with c1:
        if render_button_compat("打开这份片单", key="btn_open_import_id", use_container_width=True):
            if not import_id:
                st.warning("请先输入完整的片单 ID，格式类似 db-0123456789abcdef。")
            elif open_imported_movie_list(import_id, update_collect_input=False):
                rerun()
    with c2:
        if import_id:
            render_copy_button("复制片单链接", build_import_url(import_id), "copy_lookup_import_url", "片单链接")


def render_douban_bookmarklet_import(clean_user_id: str = "") -> None:
    with st.expander("电脑导入助手：自动读取失败时用这个", expanded=True):
        failed_id = clean_import_id(st.session_state.get("ui_import_fetch_failed_id", ""))
        failed_message = st.session_state.get("ui_import_fetch_failed_message", "")
        if failed_id:
            st.warning(f"{failed_message} 当前片单 ID：{failed_id}")
            retry_col, copy_col = st.columns(2)
            with retry_col:
                if render_button_compat("重新读取这份片单", key="btn_retry_failed_import", use_container_width=True):
                    if open_imported_movie_list(failed_id, update_collect_input=False):
                        rerun()
            with copy_col:
                render_copy_button("复制片单 ID", failed_id, "copy_failed_import_id", "片单 ID")

        if not analytics_enabled():
            st.warning("这个导入方式需要先配置 Supabase。配置后才能生成跨设备片单 ID。")
            return

        bookmarklet = build_douban_bookmarklet()
        if not bookmarklet:
            st.warning("还没有读到 Supabase 配置，暂时不能生成导入工具。")
            return

        try:
            first_tab, resume_tab = st.tabs(["第一次导入", "已有片单 ID"])
        except Exception:
            first_tab, resume_tab = st.container(), st.container()

        with first_tab:
            st.markdown(
                """
                <div class="import-helper">
                  <div class="import-helper-title">只需要在电脑上做一次</div>
                  <div class="import-helper-copy">把导入按钮放进书签栏，然后在豆瓣“看过”页面点它。导入成功后，会生成一个片单 ID，可以发到手机继续。</div>
                </div>
                """,
                unsafe_allow_html=True,
            )
            st.markdown(
                """
                <ol class="import-step-list">
                  <li>按 <strong>Ctrl + Shift + B</strong> 显示浏览器书签栏。</li>
                  <li>把下面的按钮拖到书签栏。</li>
                  <li>打开豆瓣“看过”页面，在豆瓣页面点击书签栏里的导入按钮。</li>
                </ol>
                """,
                unsafe_allow_html=True,
            )
            if clean_user_id:
                st.markdown(f"[打开我的豆瓣已看页](https://movie.douban.com/people/{clean_user_id}/collect)")
            bookmarklet_name = "导入我的豆瓣已看"
            render_bookmarklet_link(bookmarklet_name, bookmarklet, "douban_bookmarklet_link")
            st.caption("保存后可以在 Chrome 书签管理器里确认：名称是「导入我的豆瓣已看」，网址以 javascript: 开头。")
            with st.expander("拖不动？手动复制导入按钮代码", expanded=False):
                st.caption("新建一个浏览器书签，名称填「导入我的豆瓣已看」，网址/URL 粘贴导入按钮代码。")
                name_col, code_col = st.columns(2)
                with name_col:
                    render_copy_button("复制书签名称", bookmarklet_name, "copy_douban_bookmarklet_name", "书签名称")
                with code_col:
                    render_copy_button("复制导入按钮代码", bookmarklet, "copy_douban_bookmarklet", "导入按钮代码")

        with resume_tab:
            st.caption("电脑导入完成后，页面会显示一个 db- 开头的片单 ID。手机上输入它，就能打开同一份片单。")
            render_import_id_loader()


def render_custom_parameter_page(mode: str) -> None:
    if st.session_state.pop("ui_reset_custom_requested", False):
        reset_custom_parameter_defaults()

    if st.session_state.pop("ui_import_loaded_notice", False):
        st.success("导入成功。你可以在这里调整标题和 Top N，然后把链接发到手机继续。")
    render_imported_list_notice()

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
    imported_poster_url_map = st.session_state.get("ui_import_poster_url_map", {})
    if isinstance(imported_poster_url_map, dict):
        imported_poster_url_map = {
            str(title): str(url)
            for title, url in imported_poster_url_map.items()
            if str(title) in options and str(url).strip()
        }
    else:
        imported_poster_url_map = {}
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
                    payload=build_event_payload(
                        route="custom_setup",
                        list_id=st.session_state.get("ui_custom_challenge_id", ""),
                        list_size=len(options),
                        surface="custom_setup",
                    ),
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
                    initial_poster_url_map=imported_poster_url_map,
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


def render_douban_collect_parameter_page(mode: str) -> None:
    if st.session_state.pop("ui_reset_douban_collect_requested", False):
        reset_douban_collect_parameter_defaults()

    if st.session_state.pop("ui_import_loaded_notice", False):
        st.success("导入成功。你可以先按类型、评分和标记年份筛选，再开始整理。")

    st.text_input(
        "豆瓣 ID 或看过页面链接",
        value=st.session_state.get("ui_douban_collect_user_id", ""),
        key="ui_douban_collect_user_id",
        placeholder="例：123456 或 https://movie.douban.com/people/123456/collect",
        help="打开豆瓣电影“看过”页面，链接里 /people/ 和 /collect 之间的部分就是 ID；需要这个页面公开可访问。",
    )
    st.text_input(
        "片单 ID（可选）",
        value=st.session_state.get("ui_douban_collect_import_id", ""),
        key="ui_douban_collect_import_id",
        placeholder="例：db-0123456789abcdef",
        help="电脑书签导入后会生成片单 ID。豆瓣 ID 和片单 ID 只用填写一个；如果都填写，会优先使用片单 ID。",
    )
    st.caption(
        f"示例：如果链接是 movie.douban.com/people/123456/collect，豆瓣 ID 就是 123456。"
        f" 只读取公开可访问的“看过”页面，最多读取前 {DOUBAN_COLLECT_MAX_ITEMS} 部。"
    )

    raw_user_id = st.session_state.get("ui_douban_collect_user_id", "")
    clean_user_id = normalize_douban_user_id(raw_user_id)
    raw_import_id = st.session_state.get("ui_douban_collect_import_id", "")
    clean_import_id_value = clean_import_id(raw_import_id)
    if raw_user_id.strip() and not clean_user_id:
        st.warning("这个豆瓣 ID/链接看起来不对。可以直接填数字 ID，比如 123456。")
    if raw_import_id.strip() and not clean_import_id_value:
        st.warning("这个片单 ID 看起来不对。格式类似 db-0123456789abcdef。")
    if clean_import_id_value and clean_user_id:
        st.info("正在使用片单 ID。清空片单 ID 后，可以改用豆瓣 ID 重新读取。")
    render_douban_bookmarklet_import(clean_user_id)
    render_imported_list_notice()

    st.text_input(
        "片单标题",
        value=st.session_state.get("ui_douban_collect_theme", "我的豆瓣已看电影总榜"),
        key="ui_douban_collect_theme",
    )

    scope = st.radio(
        "输出范围",
        ["只保留前 N 名", "完整排序"],
        index=0 if st.session_state.get("ui_douban_collect_scope", "只保留前 N 名") == "只保留前 N 名" else 1,
        key="ui_douban_collect_scope",
        horizontal=True,
    )
    top_k: Optional[int] = None
    if scope == "只保留前 N 名":
        top_k = int(
            st.number_input(
                "最终保留前 N 名",
                min_value=1,
                max_value=500,
                value=int(st.session_state.get("ui_douban_collect_top_k", 20)),
                step=1,
                key="ui_douban_collect_top_k",
            )
        )
    else:
        st.info("完整排序会把所有看过的条目排出顺序；如果片单很长，可能需要比较很多次。第一次建议先试 Top 20。")

    show_poster = st.checkbox(
        "整理时显示电影海报",
        value=bool(st.session_state.get("ui_douban_collect_show_poster", True)),
        key="ui_douban_collect_show_poster",
    )
    personalization = render_personalization_controls("ui_douban_collect")

    active_source = f"import:{clean_import_id_value}" if clean_import_id_value else (f"user:{clean_user_id}" if clean_user_id else "")
    preview_entries = normalize_collect_entries(st.session_state.get("ui_douban_collect_preview_entries", []))
    if st.session_state.get("ui_douban_collect_preview_source") != active_source:
        preview_entries = []
        st.session_state["ui_douban_collect_excluded_titles"] = []
    else:
        valid_excluded = valid_excluded_titles(st.session_state.get("ui_douban_collect_excluded_titles", []), preview_entries)
        if valid_excluded != st.session_state.get("ui_douban_collect_excluded_titles", []):
            st.session_state["ui_douban_collect_excluded_titles"] = valid_excluded
    preview_has_media_type_data = collect_entries_have_media_type_data(preview_entries)
    preview_has_rating_data = collect_entries_have_rating_data(preview_entries)
    preview_has_year_data = collect_entries_have_year_data(preview_entries)
    (
        selected_media_types,
        include_unknown_media_type,
        selected_ratings,
        include_unrated,
        selected_years,
        include_unknown_year,
        filtered_entries,
    ) = render_collect_filters(
        preview_entries,
        preview_has_media_type_data,
        preview_has_rating_data,
        preview_has_year_data,
    )
    excluded_titles = list(st.session_state.get("ui_douban_collect_excluded_titles", []))
    final_entries = apply_excluded_titles(filtered_entries, excluded_titles)
    preview_movies = [str(entry["title"]) for entry in final_entries if entry.get("title")]

    if preview_movies:
        effective_top_k = min(top_k, len(preview_movies)) if top_k is not None else None
        st.caption(f"当前将整理 {len(preview_movies)} 个条目。预计需要取舍约 {estimated_comparisons(len(preview_movies), effective_top_k)} 次。")
    else:
        st.caption("先预览一次，确认能读取片单，再开始整理。")

    c1, c2 = st.columns(2)
    with c1:
        if render_button_compat("读取 / 预览片单", key="btn_preview_douban_collect", use_container_width=True):
            if clean_import_id_value:
                imported = fetch_imported_movie_list(clean_import_id_value)
                if not imported:
                    st.error("没有读到这份片单。请确认片单 ID 正确，或刚导入后等待几秒再试。")
                else:
                    store_imported_movie_list_state(imported, update_collect_input=False)
                    st.success(f"读取到 {len(imported.items)} 个已导入条目。")
                    rerun()
            elif clean_user_id:
                try:
                    entries = normalize_collect_entries(fetch_douban_collect_entries(clean_user_id))
                    movies = [str(entry["title"]) for entry in entries if entry.get("title")]
                    st.session_state["ui_douban_collect_preview_entries"] = entries
                    st.session_state["ui_douban_collect_preview_movies"] = movies
                    st.session_state["ui_douban_collect_preview_source"] = f"user:{clean_user_id}"
                    st.session_state["ui_douban_collect_preview_user_id"] = clean_user_id
                    st.session_state["ui_douban_collect_excluded_titles"] = []
                    st.success(f"读取到 {len(movies)} 个看过的条目。")
                    rerun()
                except Exception as e:
                    st.error(f"读取豆瓣看过列表失败：{e}")
            else:
                st.warning("请先输入豆瓣 ID、看过页面链接，或片单 ID。")
    with c2:
        if clean_import_id_value:
            st.caption(f"将读取片单 ID：{clean_import_id_value}")
        elif clean_user_id:
            st.caption(f"将读取：movie.douban.com/people/{clean_user_id}/collect")

    if filtered_entries or excluded_titles:
        with st.expander(f"当前筛选后的片单（{len(preview_movies)} 个条目）", expanded=True):
            render_editable_collect_preview(
                final_entries,
                "ui_douban_collect_preview_search",
                "ui_douban_collect_excluded_titles",
                empty_text="当前候选已被筛选或手动移除为空。",
            )

    nav1, nav2, nav3 = st.columns(3)
    with nav1:
        if render_button_compat("返回", key="btn_douban_collect_back_step1", use_container_width=True):
            go_to_step(1)
    with nav2:
        if render_button_compat("清空", key="btn_clear_douban_collect_step2", use_container_width=True):
            clear_ranking_state()
            st.session_state["ui_reset_douban_collect_requested"] = True
            rerun()
    with nav3:
        if render_button_compat("开始整理", key="btn_start_douban_collect_step2", use_container_width=True, button_type="primary"):
            if clean_import_id_value:
                if not preview_entries:
                    imported = fetch_imported_movie_list(clean_import_id_value)
                    if imported:
                        store_imported_movie_list_state(imported, update_collect_input=False)
                        preview_entries = normalize_collect_entries(imported.entries)
                    else:
                        st.error("没有读到这份片单。请先点击“读取 / 预览片单”。")
                        return
                filtered_entries = filter_collect_entries(
                    preview_entries,
                    selected_media_types,
                    include_unknown_media_type,
                    selected_ratings,
                    include_unrated,
                    selected_years,
                    include_unknown_year,
                )
                final_entries = apply_excluded_titles(filtered_entries, list(st.session_state.get("ui_douban_collect_excluded_titles", [])))
                if len(final_entries) < 2:
                    st.warning("当前筛选和手动移除后不足 2 个条目，无法开始整理。")
                    return
                st.session_state["ui_pending_douban"] = {
                    "source_type": "collect_import",
                    "mode": mode,
                    "theme": (st.session_state.get("ui_douban_collect_theme", "") or "").strip() or "我的豆瓣已看电影总榜",
                    "top_k": top_k,
                    "user_id": "",
                    "import_id": clean_import_id_value,
                    "entries": final_entries,
                    "selected_media_types": selected_media_types,
                    "include_unknown_media_type": include_unknown_media_type,
                    "selected_ratings": selected_ratings,
                    "include_unrated": include_unrated,
                    "selected_years": selected_years,
                    "include_unknown_year": include_unknown_year,
                    "show_poster": show_poster,
                    "user_name": personalization["user_name"],
                    "seed_text": personalization["seed_text"] or f"douban-import-{clean_import_id_value}",
                    "blind_mode": personalization["blind_mode"],
                    "side_shuffle": personalization["side_shuffle"],
                }
                st.session_state["ui_step"] = 4
                rerun()
            elif clean_user_id:
                if preview_entries and len(final_entries) < 2:
                    st.warning("当前筛选和手动移除后不足 2 个条目，无法开始整理。")
                    return
                st.session_state["ui_pending_douban"] = {
                    "source_type": "collect",
                    "mode": mode,
                    "theme": (st.session_state.get("ui_douban_collect_theme", "") or "").strip() or "我的豆瓣已看电影总榜",
                    "top_k": top_k,
                    "user_id": clean_user_id,
                    "entries": final_entries if preview_entries else None,
                    "selected_media_types": selected_media_types,
                    "include_unknown_media_type": include_unknown_media_type,
                    "selected_ratings": selected_ratings,
                    "include_unrated": include_unrated,
                    "selected_years": selected_years,
                    "include_unknown_year": include_unknown_year,
                    "show_poster": show_poster,
                    "user_name": personalization["user_name"],
                    "seed_text": personalization["seed_text"] or f"douban-collect-{clean_user_id}",
                    "blind_mode": personalization["blind_mode"],
                    "side_shuffle": personalization["side_shuffle"],
                }
                st.session_state["ui_step"] = 4
                rerun()
            else:
                st.warning("请先输入有效的豆瓣 ID、看过页面链接，或片单 ID。")


def render_parameter_page() -> None:
    mode = get_selected_mode()
    render_step_header(
        2,
        "整理这份电影名单",
        "补充标题、电影范围和分享方式。",
    )

    if mode == MODE_CUSTOM:
        render_custom_parameter_page(mode)
    elif mode == MODE_DOUBAN:
        render_douban_parameter_page(mode)
    else:
        render_douban_collect_parameter_page(mode)


def render_douban_prepare_page() -> None:
    pending = st.session_state.get("ui_pending_douban")
    st.progress(0.72)
    st.subheader("正在准备片单")
    source_type = (pending or {}).get("source_type", "top250") if isinstance(pending, dict) else "top250"
    if source_type in {"collect", "collect_import"}:
        st.caption("正在读取豆瓣已看列表和海报。准备完成后会自动进入选择页。")
    else:
        st.caption("正在读取豆瓣电影和海报。准备完成后会自动进入选择页。")

    if not pending:
        st.warning("没有待准备的豆瓣片单。")
        if render_button_compat("返回设置", key="btn_prepare_back", use_container_width=True):
            go_to_step(2)
        return

    try:
        poster_url_map: Dict[str, str] = {}
        if source_type in {"collect", "collect_import"}:
            pending_ratings = pending.get("selected_ratings")
            pending_media_types = pending.get("selected_media_types")
            movies, poster_map, poster_url_map = prepare_douban_collect_candidates_ui(
                str(pending.get("user_id", "")),
                warm_posters=bool(pending["show_poster"]),
                selected_media_types=list(DOUBAN_COLLECT_MEDIA_TYPES if pending_media_types is None else pending_media_types),
                include_unknown_media_type=bool(pending.get("include_unknown_media_type", True)),
                selected_ratings=list(DOUBAN_RATING_VALUES if pending_ratings is None else pending_ratings),
                include_unrated=bool(pending.get("include_unrated", True)),
                selected_years=pending.get("selected_years"),
                include_unknown_year=bool(pending.get("include_unknown_year", True)),
                imported_entries=pending.get("entries") if pending.get("entries") else None,
            )
        else:
            movies, poster_map = prepare_douban_candidates_ui(
                int(pending["pool_n"]),
                warm_posters=bool(pending["show_poster"]),
            )
        if len(movies) < 2:
            st.error("获取到的候选项不足 2，无法开始整理。")
            if render_button_compat("返回设置", key="btn_prepare_failed_back", use_container_width=True):
                st.session_state.pop("ui_pending_douban", None)
                go_to_step(2)
            return

        top_k = pending.get("top_k")
        if top_k is not None:
            top_k = min(int(top_k), len(movies))

        init_ranking_state(
            mode=pending["mode"],
            theme=pending["theme"],
            options=movies,
            top_k=top_k,
            show_poster=bool(pending["show_poster"]),
            user_name=str(pending.get("user_name", "")),
            seed_text=str(pending.get("seed_text", "")),
            blind_mode=bool(pending.get("blind_mode", False)),
            side_shuffle=bool(pending.get("side_shuffle", True)),
            challenge_id="",
            template_id="douban-collect" if source_type in {"collect", "collect_import"} else "douban-live",
            source_channel=get_source_channel(),
            initial_poster_map=poster_map,
            initial_poster_url_map=poster_url_map,
        )
        st.session_state.pop("ui_pending_douban", None)
        st.session_state["ui_step"] = 3
        rerun()
    except Exception as e:
        st.error(f"准备豆瓣片单失败：{e}")
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
    home_render_started_at = datetime.now()
    render_boot_loading_notice()
    render_app_styles()

    if get_query_param("admin"):
        render_admin_dashboard()
        return

    if "ui_selected_mode" not in st.session_state:
        st.session_state["ui_selected_mode"] = MODE_DOUBAN_COLLECT
    if "ui_step" not in st.session_state:
        st.session_state["ui_step"] = 1

    track_once(
        f"page_view_{get_source_channel()}",
        EVENT_PAGE_VIEW,
        source_channel=get_source_channel(),
        payload=build_event_payload(
            route="home",
            has_list=bool(get_query_param("list") or get_query_param("challenge")),
            has_payload=bool(get_query_param("payload")),
            has_import=bool(get_query_param("import")),
            session_hint=get_session_id()[-8:],
        ),
    )
    maybe_open_imported_movie_list()
    maybe_open_url_challenge()
    sync_local_draft()

    step = get_ui_step()
    if step == 3:
        st.caption(APP_TITLE)
    elif step == 1:
        render_home_collab_badge()
        render_cover_header()
    else:
        st.title(APP_TITLE)
        st.markdown(APP_SUBTITLE)

    if st.session_state.pop("local_draft_restored", False):
        st.success("已接回本机上次未完成的整理进度。")

    if step == 1:
        render_mode_selection_page()
        track_once(
            f"home_content_rendered_{get_source_channel()}",
            EVENT_HOME_CONTENT_RENDERED,
            mode=get_selected_mode(),
            source_channel=get_source_channel(),
            payload=build_event_payload(
                route="home",
                mode=get_selected_mode(),
                render_elapsed_ms=int(max(0, (datetime.now() - home_render_started_at).total_seconds() * 1000)),
                home_layout_order=st.session_state.get("home_layout_order", "current"),
            ),
        )
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
