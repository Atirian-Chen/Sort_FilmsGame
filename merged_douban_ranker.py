from __future__ import annotations

import io
import json
import math
import random
import time
from pathlib import Path
from typing import Dict, List, Optional
from urllib.parse import urljoin

import requests
import streamlit as st
from bs4 import BeautifulSoup
from PIL import Image, UnidentifiedImageError

# =========================
# 基础配置
# =========================
DOUBAN_TOP250_URL = "https://movie.douban.com/top250"
MODE_CUSTOM = "自定义模式"
MODE_DOUBAN = "豆瓣电影模式"
CACHE_VERSION = 2
CACHE_DIR = Path(__file__).resolve().parent / "cache"
POSTER_DIR = CACHE_DIR / "posters"
META_JSON = CACHE_DIR / "douban_top250_cache.json"
REQUEST_GAP_SECONDS = 0.25

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/126.0 Safari/537.36"
    ),
    "Referer": "https://movie.douban.com/",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
}

CACHE_DIR.mkdir(parents=True, exist_ok=True)
POSTER_DIR.mkdir(parents=True, exist_ok=True)


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
# 图片与缓存相关
# =========================
def normalize_image_bytes(image_bytes: bytes) -> Optional[bytes]:
    """把有效图片统一转成 PNG 字节，失效内容直接返回 None。"""
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


def request_get(url: str, *, params: Optional[dict] = None, timeout: int = 20) -> requests.Response:
    response = requests.get(url, params=params, headers=HEADERS, timeout=timeout)
    response.raise_for_status()
    return response


@st.cache_data(show_spinner=False)
def fetch_subject_page_poster_url(subject_url: str) -> str:
    """当榜单页拿不到图片时，去电影详情页补抓海报 URL。"""
    try:
        response = request_get(subject_url, timeout=20)
        soup = BeautifulSoup(response.text, "html.parser")

        og = soup.select_one('meta[property="og:image"]')
        if og and og.get("content"):
            return og["content"].strip()

        img = soup.select_one("#mainpic img")
        if img:
            return (img.get("src") or "").strip()
    except Exception:
        return ""

    return ""


@st.cache_data(show_spinner=False)
def parse_top250_items(limit: int) -> List[dict]:
    """解析豆瓣 Top250 页面，拿到标题、条目链接和尽量准确的海报链接。"""
    limit = max(1, min(250, int(limit)))
    items: List[dict] = []

    for start in range(0, 250, 25):
        if len(items) >= limit:
            break

        response = request_get(DOUBAN_TOP250_URL, params={"start": start, "filter": ""}, timeout=20)
        soup = BeautifulSoup(response.text, "html.parser")

        for card in soup.select("div.item"):
            if len(items) >= limit:
                break

            title_tag = card.select_one("div.info span.title:first-child")
            link_tag = card.select_one("div.pic a")
            img_tag = card.select_one("div.pic img")
            rank_tag = card.select_one("div.pic em")

            if not title_tag or not link_tag:
                continue

            title = title_tag.get_text(strip=True)
            subject_url = (link_tag.get("href") or "").strip()
            poster_url = ""
            if img_tag:
                poster_url = (
                    img_tag.get("src")
                    or img_tag.get("data-src")
                    or img_tag.get("data-original")
                    or ""
                ).strip()
                if poster_url.startswith("//"):
                    poster_url = "https:" + poster_url
                elif poster_url.startswith("/"):
                    poster_url = urljoin(subject_url or DOUBAN_TOP250_URL, poster_url)

            if not poster_url and subject_url:
                poster_url = fetch_subject_page_poster_url(subject_url)

            rank_text = rank_tag.get_text(strip=True) if rank_tag else str(len(items) + 1)
            try:
                rank_value = int(rank_text)
            except ValueError:
                rank_value = len(items) + 1

            items.append(
                {
                    "rank": rank_value,
                    "title": title,
                    "subject_url": subject_url,
                    "poster_url": poster_url,
                }
            )

        time.sleep(REQUEST_GAP_SECONDS)

    return items[:limit]


@st.cache_data(show_spinner=False)
def download_and_normalize_poster(poster_url: str) -> Optional[bytes]:
    """下载图片，只有在真的是有效图片时才返回 PNG 字节。"""
    if not poster_url:
        return None

    try:
        response = request_get(poster_url, timeout=20)
        content_type = (response.headers.get("Content-Type") or "").lower()
        if content_type and not content_type.startswith("image/"):
            return None
        return normalize_image_bytes(response.content)
    except Exception:
        return None


@st.cache_data(show_spinner=False)
def build_douban_top_cache(limit: int, refresh: bool = False) -> List[dict]:
    """
    抓取前 limit 部电影，并把海报尽量缓存到本地。
    refresh=True 时会重新抓取并覆盖已有缓存状态。
    """
    limit = max(1, min(250, int(limit)))
    existing_map: Dict[str, dict] = {}

    if META_JSON.exists() and not refresh:
        try:
            payload = json.loads(META_JSON.read_text(encoding="utf-8"))
            if payload.get("version") == CACHE_VERSION:
                for item in payload.get("items", []):
                    key = item.get("title")
                    if key:
                        existing_map[key] = item
        except Exception:
            existing_map = {}

    source_items = parse_top250_items(limit)
    results: List[dict] = []

    for item in source_items:
        title = item["title"]
        subject_url = item.get("subject_url", "")
        poster_url = item.get("poster_url", "")
        subject_id = subject_url.rstrip("/").split("/")[-1] if subject_url else f"rank_{item['rank']}"
        poster_local_path = POSTER_DIR / f"{subject_id}.png"
        poster_status = "missing"

        old_item = existing_map.get(title, {})
        old_local = old_item.get("poster_local", "")
        if old_local and not refresh:
            old_path = Path(old_local)
            if not old_path.is_absolute():
                old_path = (Path(__file__).resolve().parent / old_path).resolve()
            if old_path.exists():
                poster_local_path = old_path
                poster_status = "ok"

        if poster_status != "ok" and poster_url:
            poster_bytes = download_and_normalize_poster(poster_url)
            if poster_bytes:
                try:
                    poster_local_path.write_bytes(poster_bytes)
                    poster_status = "ok"
                except Exception:
                    poster_status = "write_failed"
            else:
                poster_status = "invalid_or_blocked"

        poster_local_str = ""
        if poster_status == "ok" and poster_local_path.exists():
            try:
                poster_local_str = str(poster_local_path.relative_to(Path(__file__).resolve().parent))
            except ValueError:
                poster_local_str = str(poster_local_path)

        results.append(
            {
                "rank": item["rank"],
                "title": title,
                "subject_url": subject_url,
                "poster_url": poster_url,
                "poster_local": poster_local_str,
                "poster_status": poster_status,
            }
        )

        time.sleep(REQUEST_GAP_SECONDS)

    META_JSON.write_text(
        json.dumps({"version": CACHE_VERSION, "items": results}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return results


def resolve_local_path(path_str: str) -> Path:
    path = Path(path_str)
    if path.is_absolute():
        return path
    return (Path(__file__).resolve().parent / path).resolve()


def load_cached_poster_bytes(title: str) -> Optional[bytes]:
    meta_map = st.session_state.get(k("douban_meta_map"), {})
    info = meta_map.get(title)
    if not info:
        return None
    poster_local = info.get("poster_local", "")
    if not poster_local:
        return None
    try:
        poster_path = resolve_local_path(poster_local)
        if poster_path.exists():
            return poster_path.read_bytes()
    except Exception:
        return None
    return None


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
    douban_items: Optional[List[dict]] = None,
) -> None:
    opts = options[:]
    random.shuffle(opts)

    st.session_state[k("mode")] = mode
    st.session_state[k("theme")] = theme
    st.session_state[k("source_options")] = options[:]
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
    st.session_state[k("poster_map")] = {}
    st.session_state[k("douban_items")] = douban_items or []
    st.session_state[k("douban_meta_map")] = {
        item.get("title"): item for item in (douban_items or []) if item.get("title")
    }


def clear_ranking_state() -> None:
    for name in [
        "mode",
        "theme",
        "source_options",
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
        "douban_items",
        "douban_meta_map",
    ]:
        st.session_state.pop(k(name), None)


def reset_same_config() -> None:
    mode = st.session_state.get(k("mode"))
    theme = st.session_state.get(k("theme"), "我的排序")
    options = st.session_state.get(k("source_options"), [])
    top_k = st.session_state.get(k("top_k"))
    show_poster = st.session_state.get(k("show_poster"), False)
    douban_items = st.session_state.get(k("douban_items"), [])

    if len(options) < 2:
        st.warning("候选项至少需要 2 个才能排序。")
        return

    init_ranking_state(
        mode=mode,
        theme=theme,
        options=options,
        top_k=top_k,
        show_poster=show_poster,
        douban_items=douban_items,
    )
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


def handle_choice(prefer_left: bool) -> None:
    if st.session_state.get(k("finished"), False):
        return

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

    poster_bytes = load_cached_poster_bytes(name)
    poster_map[name] = poster_bytes
    st.session_state[k("poster_map")] = poster_map
    return poster_bytes


def render_option_card(title: str, button_text: str, button_key: str, prefer_left: bool, show_poster: bool) -> None:
    if show_poster:
        poster = get_poster_for_option(title)
        if poster:
            shown = show_image_compat(poster)
            if not shown:
                st.caption("海报加载失败")
        else:
            meta_map = st.session_state.get(k("douban_meta_map"), {})
            status = meta_map.get(title, {}).get("poster_status", "missing")
            if status == "invalid_or_blocked":
                st.caption("海报下载被拦截或返回的不是有效图片")
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
        help="自定义模式适合任意主题；豆瓣电影模式会先抓候选电影并缓存海报。",
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
                    douban_items=None,
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

    col_a, col_b = st.columns(2)
    with col_a:
        preview_btn = render_button_compat("👀 预览并构建缓存", key="btn_preview_douban", use_container_width=True)
    with col_b:
        refresh_btn = render_button_compat("🔄 强制刷新豆瓣缓存", key="btn_refresh_douban", use_container_width=True)

    requested_refresh = False
    if preview_btn or refresh_btn:
        if pool_n < top_k:
            st.warning("请先修正参数：候选池数量不能小于 Top 数量。")
        else:
            requested_refresh = bool(refresh_btn)
            try:
                with st.spinner("正在抓取候选电影并缓存海报，这一步可能需要几十秒..."):
                    movies = build_douban_top_cache(pool_n, refresh=requested_refresh)
                ok_count = sum(1 for item in movies if item.get("poster_status") == "ok")
                st.success(f"已准备 {len(movies)} 部候选电影，成功缓存海报 {ok_count} 张。")
                with st.expander(f"当前候选电影（前 {len(movies)} 部）", expanded=True):
                    for i, item in enumerate(movies, 1):
                        st.write(f"{i}. {item['title']}")
            except Exception as e:
                st.error(f"读取或缓存豆瓣电影失败：{e}")

    cache_info = None
    if META_JSON.exists():
        try:
            payload = json.loads(META_JSON.read_text(encoding="utf-8"))
            cached_items = payload.get("items", [])
            cache_info = {
                "count": len(cached_items),
                "poster_ok": sum(1 for item in cached_items if item.get("poster_status") == "ok"),
            }
        except Exception:
            cache_info = None

    if cache_info:
        st.caption(f"本地缓存概况：已记录 {cache_info['count']} 部电影，成功缓存海报 {cache_info['poster_ok']} 张。")

    col1, col2 = st.columns(2)
    with col1:
        if render_button_compat("✅ 开始电影 Top 排序", key="btn_start_douban", use_container_width=True):
            if pool_n < top_k:
                st.warning("请先修正参数：候选池数量不能小于 Top 数量。")
            else:
                try:
                    with st.spinner("正在准备豆瓣候选池与本地海报缓存..."):
                        movies = build_douban_top_cache(pool_n, refresh=False)
                    titles = [item["title"] for item in movies]
                    if len(titles) < 2:
                        st.error("获取到的电影数量不足 2，无法开始排序。")
                    else:
                        init_ranking_state(
                            mode=mode,
                            theme=theme.strip() or "豆瓣电影偏好排序",
                            options=titles,
                            top_k=top_k,
                            show_poster=show_poster,
                            douban_items=movies,
                        )
                        rerun()
                except Exception as e:
                    st.error(f"读取或缓存豆瓣电影失败：{e}")
    with col2:
        if render_button_compat("🧹 清空当前配置", key="btn_clear_douban", use_container_width=True):
            clear_ranking_state()
            st.session_state["ui_douban_theme"] = "豆瓣电影偏好排序"
            st.session_state["ui_douban_top_k"] = 10
            st.session_state["ui_douban_pool_n"] = 100
            st.session_state["ui_douban_show_poster"] = True
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

    st.subheader(f"当前主题：{theme}")

    if top_k is None:
        st.caption("当前模式：自定义完整排序")
    else:
        meta_map = st.session_state.get(k("douban_meta_map"), {})
        ok_count = sum(1 for item in meta_map.values() if item.get("poster_status") == "ok")
        st.caption(f"当前模式：豆瓣电影 Top {top_k} 排序（候选总数 {total}，本地海报缓存 {ok_count} 张）")

    if st.session_state.get(k("finished"), False):
        ranked = st.session_state.get(k("ranked"), [])
        if top_k is None:
            st.success("🎉 排序完成！下面是你的完整排名：")
        else:
            st.success(f"🎉 排序完成！下面是你的 Top {len(ranked)}：")

        for i, item in enumerate(ranked, 1):
            st.write(f"{i}. {item}")

        if top_k is None:
            st.caption(f"共 {total} 个候选项，完成比较 {comparisons} 次。")
        else:
            st.caption(f"共处理 {total} 部电影，最终保留 Top {len(ranked)}，完成比较 {comparisons} 次。")

        col1, col2 = st.columns(2)
        with col1:
            if render_button_compat("🔁 用同一配置重新排一次", key="btn_reset_same", use_container_width=True):
                reset_same_config()
        with col2:
            if render_button_compat("🗑️ 清除本次排序结果", key="btn_clear_result", use_container_width=True):
                clear_ranking_state()
                rerun()
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
        st.caption(f"已插入 {processed} / {total} 个候选项，已比较 {comparisons} 次。")
        st.markdown("### 请选择，你更偏好哪一个？")
    else:
        st.caption(f"已处理 {processed} / {total} 部电影，当前最多保留 Top {top_k}，已比较 {comparisons} 次。")
        st.markdown("### 请选择，你更喜欢哪一部电影？")

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

    ranked = st.session_state.get(k("ranked"), [])
    expander_title = "📊 当前临时完整排序" if top_k is None else f"📊 当前临时 Top {len(ranked)} 榜单"
    with st.expander(expander_title, expanded=False):
        for i, item in enumerate(ranked, 1):
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
    st.caption(
        "说明：豆瓣模式会先抓取候选电影，并尽量把海报下载到本地 cache/posters 目录。"
        "如果豆瓣返回的不是有效图片、网络异常或被拦截，单张海报可能失败，但排序功能仍可继续。"
    )


if __name__ == "__main__":
    main()
