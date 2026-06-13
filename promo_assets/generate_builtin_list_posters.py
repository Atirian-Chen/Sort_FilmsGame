from __future__ import annotations

import sys
from io import BytesIO
from pathlib import Path
from typing import Dict, Tuple

import qrcode
from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageOps

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from merged_douban_ranker_v3 import get_best_poster_bytes


OUT = ROOT / "promo_assets" / "builtin_list_posters"
BG = ROOT / "promo_assets" / "douban_collect_bg.png"
PUBLIC_URL = "https://sortfilmsgamegit.streamlit.app"

FONT_REGULAR = r"C:\Windows\Fonts\msyh.ttc"
FONT_BOLD = r"C:\Windows\Fonts\msyhbd.ttc"

INK = "#20242b"
MUTED = "#716b64"
TERRA = "#9a5f4d"
BLUE = "#2f7ee2"
PAPER = "#fffdf8"
LINE = "#e8ddd0"
DARK = "#292d34"


def font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(FONT_BOLD if bold else FONT_REGULAR, size)


F = {
    "tiny": font(24),
    "small": font(30),
    "small_b": font(30, True),
    "body": font(36),
    "body_b": font(36, True),
    "mid": font(46, True),
    "title": font(62, True),
    "big": font(78, True),
}


def fit_bg(w: int, h: int) -> Image.Image:
    if BG.exists():
        img = Image.open(BG).convert("RGB")
        img = ImageOps.fit(img, (w, h), method=Image.Resampling.LANCZOS)
        img = img.filter(ImageFilter.GaussianBlur(13))
        veil = Image.new("RGB", (w, h), "#fffaf3")
        return Image.blend(img, veil, 0.74)
    return Image.new("RGB", (w, h), "#fff8ef")


def shadowed_card(base: Image.Image, box: Tuple[int, int, int, int], radius: int = 34, fill: str = PAPER) -> None:
    x1, y1, x2, y2 = box
    layer = Image.new("RGBA", base.size, (0, 0, 0, 0))
    layer_draw = ImageDraw.Draw(layer)
    layer_draw.rounded_rectangle((x1 + 10, y1 + 16, x2 + 10, y2 + 16), radius=radius, fill=(70, 52, 39, 34))
    layer = layer.filter(ImageFilter.GaussianBlur(18))
    base.alpha_composite(layer)
    draw = ImageDraw.Draw(base)
    draw.rounded_rectangle(box, radius=radius, fill=fill, outline=LINE, width=2)


def draw_wrapped(
    draw: ImageDraw.ImageDraw,
    text: str,
    xy: Tuple[int, int],
    fnt: ImageFont.FreeTypeFont,
    fill: str,
    max_width: int,
    line_gap: int = 8,
) -> int:
    x, y = xy
    lines = []
    current = ""
    for ch in text:
        trial = current + ch
        if draw.textlength(trial, font=fnt) <= max_width or not current:
            current = trial
        else:
            lines.append(current)
            current = ch
    if current:
        lines.append(current)
    for line in lines:
        draw.text((x, y), line, font=fnt, fill=fill)
        y += fnt.size + line_gap
    return y


def shrink_font_to_fit(text: str, max_width: int, start: int, min_size: int = 28) -> ImageFont.FreeTypeFont:
    size = start
    while size > min_size:
        fnt = font(size, True)
        if ImageDraw.Draw(Image.new("RGB", (1, 1))).textlength(text, font=fnt) <= max_width:
            return fnt
        size -= 2
    return font(min_size, True)


def qr_img(url: str, size: int = 152) -> Image.Image:
    qr = qrcode.QRCode(border=1, box_size=10)
    qr.add_data(url)
    qr.make(fit=True)
    img = qr.make_image(fill_color=INK, back_color=PAPER).convert("RGB")
    return img.resize((size, size), Image.Resampling.NEAREST)


def poster_thumb(title: str, w: int = 148, h: int = 214) -> Image.Image:
    poster_bytes = get_best_poster_bytes(title)
    if poster_bytes:
        img = Image.open(BytesIO(poster_bytes)).convert("RGB")
        img = ImageOps.fit(img, (w, h), method=Image.Resampling.LANCZOS, centering=(0.5, 0.5))
    else:
        img = Image.new("RGB", (w, h), "#d9cab8")
        draw = ImageDraw.Draw(img)
        draw.rounded_rectangle((10, 10, w - 10, h - 10), radius=18, outline="#fffaf3", width=3)
        draw.text((w // 2, h // 2), title[:4], font=font(28, True), fill=INK, anchor="mm")
    mask = Image.new("L", (w, h), 0)
    mask_draw = ImageDraw.Draw(mask)
    mask_draw.rounded_rectangle((0, 0, w, h), radius=18, fill=255)
    out = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    out.paste(img.convert("RGBA"), (0, 0), mask)
    return out


def draw_movie_card(
    base: Image.Image,
    x: int,
    y: int,
    title: str,
    shortcut: str,
    note: str,
) -> None:
    draw = ImageDraw.Draw(base)
    draw.rounded_rectangle((x, y, x + 469, y + 330), radius=28, fill=PAPER, outline=LINE, width=2)
    base.alpha_composite(poster_thumb(title), (x + 40, y + 58))
    title_font = shrink_font_to_fit(title, 225, 38, 30)
    draw_wrapped(draw, title, (x + 210, y + 84), title_font, INK, 225, 2)
    draw_wrapped(draw, note, (x + 210, y + 146), F["small"], MUTED, 225, 8)
    draw.rounded_rectangle((x + 300, y + 246, x + 430, y + 304), radius=16, fill="#f5f0ea", outline=LINE)
    draw.text((x + 365, y + 275), shortcut, font=F["small_b"], fill=TERRA, anchor="mm")


def build_poster(config: Dict[str, object]) -> Path:
    w, h = 1242, 1600
    list_id = str(config["id"])
    list_url = f"{PUBLIC_URL}/?list={list_id}"
    base = fit_bg(w, h).convert("RGBA")
    draw = ImageDraw.Draw(base)

    draw.rounded_rectangle((62, 60, w - 62, h - 60), radius=54, fill=(255, 253, 248, 232), outline="#eaded1", width=2)
    draw.text((96, 104), str(config["kicker"]), font=F["small_b"], fill=TERRA)
    draw.text((96, 174), "不用硬排第一第二", font=F["big"], fill=INK)
    draw.text((96, 266), f"把「{config['list_name']}」拆成很多次二选一", font=F["mid"], fill=INK)
    draw_wrapped(
        draw,
        str(config["intro"]),
        (96, 334),
        F["body"],
        MUTED,
        1010,
        10,
    )

    shadowed_card(base, (96, 470, 1146, 695), radius=34, fill=PAPER)
    draw = ImageDraw.Draw(base)
    draw.text((136, 516), str(config["feature_badge"]), font=F["small_b"], fill=TERRA)
    draw.text((136, 568), str(config["feature_title"]), font=F["mid"], fill=INK)
    draw.text((136, 632), str(config["feature_subtitle"]), font=F["body"], fill=MUTED)
    draw.rounded_rectangle((842, 548, 1088, 628), radius=18, fill=DARK)
    draw.text((965, 588), "开始整理", font=F["body_b"], fill="#fffaf4", anchor="mm")

    shadowed_card(base, (96, 760, 1146, 1408), radius=38, fill="#fcfaf6")
    draw = ImageDraw.Draw(base)
    draw.text((138, 810), "你更喜欢哪一部？", font=F["mid"], fill=INK)
    draw.text((138, 868), str(config["progress_text"]), font=F["small"], fill=MUTED)
    draw.rounded_rectangle((138, 928, 1094, 944), radius=8, fill="#edf1f6")
    draw.rounded_rectangle((138, 928, 512, 944), radius=8, fill=BLUE)

    note = "不用一次想清全部顺序，先在这一对里作一次取舍。"
    left, right = config["pair"]  # type: ignore[index]
    draw_movie_card(base, 138, 990, str(left), "A / ←", note)
    draw_movie_card(base, 625, 990, str(right), "D / →", note)

    base.alpha_composite(qr_img(list_url).convert("RGBA"), (138, 1440))
    draw = ImageDraw.Draw(base)
    draw.text((316, 1456), str(config["qr_title"]), font=F["body_b"], fill=INK)
    draw.text((316, 1508), PUBLIC_URL + "/", font=F["small"], fill=MUTED)

    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / f"{list_id}_promo.png"
    base.convert("RGB").save(path, quality=95)
    return path


POSTERS = [
    {
        "id": "wong-kar-wai",
        "list_name": "王家卫电影榜",
        "kicker": "给王家卫影迷的一道选择题",
        "intro": "从《旺角卡门》到《一代宗师》，只问一个很简单的问题：这两部里，你更偏爱哪一部？",
        "feature_badge": "内置片单 · 导演作品",
        "feature_title": "给你的王家卫电影排出榜单",
        "feature_subtitle": "10 部电影 · 完整排序",
        "progress_text": "10 部 · 正在整理完整榜",
        "pair": ("花样年华", "重庆森林"),
        "qr_title": "扫码试试：排一份王家卫电影榜",
    },
    {
        "id": "shinkai",
        "list_name": "新海诚动画电影榜",
        "kicker": "给新海诚粉丝的一道选择题",
        "intro": "从距离、天空到重逢，把看过的新海诚作品放在同一张桌上，慢慢排出自己的顺序。",
        "feature_badge": "内置片单 · 动画导演",
        "feature_title": "给你的新海诚动画排出榜单",
        "feature_subtitle": "8 部电影 · 完整排序",
        "progress_text": "8 部 · 正在整理完整榜",
        "pair": ("你的名字。", "天气之子"),
        "qr_title": "扫码试试：排一份新海诚动画榜",
    },
    {
        "id": "disney-animation",
        "list_name": "迪士尼动画长片榜",
        "kicker": "给迪士尼动画粉丝的一道选择题",
        "intro": "从经典手绘到近年 3D 动画，不混入皮克斯和真人版，只排你看过的迪士尼动画长片。",
        "feature_badge": "内置片单 · 迪士尼动画",
        "feature_title": "给你的迪士尼动画排出 Top 10",
        "feature_subtitle": "20 部电影 · 最后出 Top 10",
        "progress_text": "20 部 · 正在整理 Top 10",
        "pair": ("狮子王", "冰雪奇缘"),
        "qr_title": "扫码试试：排一份迪士尼动画榜",
    },
]


if __name__ == "__main__":
    for poster in POSTERS:
        print(build_poster(poster))
