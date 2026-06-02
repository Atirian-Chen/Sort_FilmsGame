from pathlib import Path
from io import BytesIO

import qrcode
import requests
from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageOps


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "promo_assets"
BG = OUT / "douban_collect_bg.png"
URL = "https://sortfilmsgamegit.streamlit.app/"

FONT_REGULAR = r"C:\Windows\Fonts\msyh.ttc"
FONT_BOLD = r"C:\Windows\Fonts\msyhbd.ttc"

INK = "#1f2328"
MUTED = "#716b64"
TERRA = "#9a5f4d"
BLUE = "#3568dd"
PAPER = "#fffdf8"
LINE = "#e8ddd0"
DARK = "#292d34"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/125 Safari/537.36",
    "Referer": "https://movie.douban.com/",
}
POSTER_URLS = {
    "健听女孩": "https://img1.doubanio.com/view/photo/s_ratio_poster/public/p2870510534.jpg",
    "傲慢与偏见": "https://img1.doubanio.com/view/photo/s_ratio_poster/public/p2016401659.jpg",
    "千与千寻": "https://img1.doubanio.com/view/photo/s_ratio_poster/public/p2557573348.jpg",
    "星际穿越": "https://img3.doubanio.com/view/photo/s_ratio_poster/public/p2614988097.jpg",
    "霸王别姬": "https://img1.doubanio.com/view/photo/s_ratio_poster/public/p2911205318.jpg",
    "情书": "https://img1.doubanio.com/view/photo/s_ratio_poster/public/p2648230660.jpg",
}


def font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(FONT_BOLD if bold else FONT_REGULAR, size)


F = {
    "small": font(30),
    "small_b": font(30, True),
    "body": font(36),
    "body_b": font(36, True),
    "mid": font(46, True),
    "title": font(70, True),
    "big": font(78, True),
}


def fit_bg(w: int, h: int) -> Image.Image:
    if BG.exists():
        img = Image.open(BG).convert("RGB")
        img = ImageOps.fit(img, (w, h), method=Image.Resampling.LANCZOS)
        img = img.filter(ImageFilter.GaussianBlur(10))
        veil = Image.new("RGB", (w, h), "#fffaf3")
        return Image.blend(img, veil, 0.72)
    return Image.new("RGB", (w, h), "#fff8ef")


def shadowed_card(base: Image.Image, box, radius=34, fill=PAPER, outline=LINE) -> None:
    x1, y1, x2, y2 = box
    layer = Image.new("RGBA", base.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    d.rounded_rectangle((x1 + 10, y1 + 16, x2 + 10, y2 + 16), radius=radius, fill=(70, 52, 39, 34))
    layer = layer.filter(ImageFilter.GaussianBlur(18))
    base.alpha_composite(layer)
    d = ImageDraw.Draw(base)
    d.rounded_rectangle(box, radius=radius, fill=fill, outline=outline, width=2)


def draw_wrapped(draw: ImageDraw.ImageDraw, text: str, xy, fnt, fill: str, max_width: int, line_gap=8) -> int:
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


def qr_img(size=180) -> Image.Image:
    qr = qrcode.QRCode(border=1, box_size=10)
    qr.add_data(URL)
    qr.make(fit=True)
    img = qr.make_image(fill_color="#1f2328", back_color="#fffdf8").convert("RGB")
    return img.resize((size, size), Image.Resampling.NEAREST)


def poster_thumb(color1: str, color2: str, title: str, w=148, h=214) -> Image.Image:
    img = Image.new("RGB", (w, h), color1)
    d = ImageDraw.Draw(img)
    for i in range(h):
        ratio = i / h
        c = tuple(
            int(int(color1[j : j + 2], 16) * (1 - ratio) + int(color2[j : j + 2], 16) * ratio)
            for j in (1, 3, 5)
        )
        d.line((0, i, w, i), fill=c)
    d.rounded_rectangle((10, 10, w - 10, h - 10), radius=18, outline=(255, 255, 255), width=3)
    d.text((w // 2, h // 2 - 22), title[:4], font=font(28, True), fill="#fffdf8", anchor="mm")
    d.text((w // 2, h - 32), "MOVIE", font=font(16, True), fill="#fffdf8", anchor="mm")
    mask = Image.new("L", (w, h), 0)
    md = ImageDraw.Draw(mask)
    md.rounded_rectangle((0, 0, w, h), radius=22, fill=255)
    out = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    out.paste(img.convert("RGBA"), (0, 0), mask)
    return out


def real_poster_thumb(title: str, color1: str, color2: str, w=148, h=214) -> Image.Image:
    url = POSTER_URLS.get(title)
    if not url:
        return poster_thumb(color1, color2, title, w, h)
    try:
        resp = requests.get(url, headers=HEADERS, timeout=12)
        resp.raise_for_status()
        img = Image.open(BytesIO(resp.content)).convert("RGB")
        img = ImageOps.fit(img, (w, h), method=Image.Resampling.LANCZOS, centering=(0.5, 0.5))
        mask = Image.new("L", (w, h), 0)
        md = ImageDraw.Draw(mask)
        md.rounded_rectangle((0, 0, w, h), radius=max(12, w // 8), fill=255)
        out = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        out.paste(img.convert("RGBA"), (0, 0), mask)
        return out
    except Exception:
        return poster_thumb(color1, color2, title, w, h)


def image_one() -> Path:
    w, h = 1242, 1656
    base = fit_bg(w, h).convert("RGBA")
    d = ImageDraw.Draw(base)
    d.rounded_rectangle((62, 60, w - 62, h - 64), radius=54, fill=(255, 253, 248, 230), outline="#eaded1", width=2)
    d.text((96, 100), "偶然发现一个很适合影迷的小网站", font=F["small_b"], fill=TERRA)
    d.text((96, 158), "不用硬排第一第二", font=F["big"], fill=INK)
    d.text((96, 250), "它把“已看电影总榜”拆成很多次二选一", font=F["mid"], fill=INK)
    draw_wrapped(
        d,
        "输入豆瓣 ID，读取公开的“看过”电影；个人主页链接中间那串数字就是 ID。接下来只问：这两部里，你更偏爱哪一部？",
        (96, 318),
        F["body"],
        MUTED,
        1010,
        10,
    )

    shadowed_card(base, (96, 470, 1146, 695), radius=34, fill="#fffdf8", outline=LINE)
    d = ImageDraw.Draw(base)
    d.text((136, 516), "主推功能 · 豆瓣已看", font=F["small_b"], fill=TERRA)
    d.text((136, 568), "给你的所有已看排出你的榜单", font=F["mid"], fill=INK)
    d.text((136, 632), "可排 Top N，也可以整理完整总榜", font=F["body"], fill=MUTED)
    d.rounded_rectangle((842, 548, 1088, 628), radius=18, fill=DARK)
    d.text((965, 588), "开始整理", font=F["body_b"], fill="#fffaf4", anchor="mm")

    shadowed_card(base, (96, 760, 1146, 1408), radius=38, fill="#fcfaf6", outline=LINE)
    d = ImageDraw.Draw(base)
    d.text((138, 810), "你更喜欢哪一部？", font=F["mid"], fill=INK)
    d.text((138, 868), "已看 100+ 部 · 正在整理 Top 20", font=F["small"], fill=MUTED)
    d.rounded_rectangle((138, 928, 1094, 944), radius=8, fill="#edf1f6")
    d.rounded_rectangle((138, 928, 512, 944), radius=8, fill="#2e80df")

    card_y = 990
    for x, title, label, c1, c2 in [
        (138, "健听女孩", "A / ←", "#6f91bd", "#283850"),
        (625, "傲慢与偏见", "D / →", "#b8866d", "#35231f"),
    ]:
        d.rounded_rectangle((x, card_y, x + 469, 1320), radius=28, fill="#fffdf8", outline=LINE, width=2)
        thumb = real_poster_thumb(title, c1, c2)
        base.alpha_composite(thumb, (x + 40, card_y + 58))
        d.text((x + 210, card_y + 84), title, font=F["body_b"], fill=INK)
        draw_wrapped(d, "不用一次想清全部顺序，先在这一对里作一次取舍。", (x + 210, card_y + 142), F["small"], MUTED, 225, 8)
        d.rounded_rectangle((x + 300, card_y + 246, x + 430, card_y + 304), radius=16, fill="#f5f0ea", outline=LINE)
        d.text((x + 365, card_y + 275), label, font=F["small_b"], fill=TERRA, anchor="mm")

    qr = qr_img(152).convert("RGBA")
    base.alpha_composite(qr, (138, 1440))
    d.text((316, 1456), "扫码试试：把自己的已看电影排出来", font=F["body_b"], fill=INK)
    d.text((316, 1508), URL, font=F["small"], fill=MUTED)
    out = OUT / "03_douban_collect_two_choice.png"
    base.convert("RGB").save(out, quality=95)
    return out


def image_two() -> Path:
    w, h = 1242, 1656
    base = fit_bg(w, h).convert("RGBA")
    d = ImageDraw.Draw(base)
    d.rounded_rectangle((62, 58, w - 62, h - 58), radius=54, fill=(255, 253, 248, 232), outline="#eaded1", width=2)
    d.text((96, 102), "整理完之后才发现", font=F["small_b"], fill=TERRA)
    d.text((96, 160), "我的已看电影总榜", font=F["big"], fill=INK)
    d.text((96, 248), "终于排出来了", font=F["big"], fill=INK)
    draw_wrapped(d, "不是从一堆电影里硬想“第一第二第三”，而是把复杂排序拆成一次次取舍。", (96, 340), F["body"], MUTED, 1010, 10)

    shadowed_card(base, (112, 500, 1130, 1242), radius=44, fill="#fffdf8", outline=LINE)
    d = ImageDraw.Draw(base)
    d.text((166, 562), "我的豆瓣已看电影总榜", font=F["title"], fill=INK)
    d.text((166, 654), "Top 10 · 来自公开豆瓣已看", font=F["body"], fill=MUTED)
    d.line((166, 724, 1074, 724), fill=LINE, width=3)
    movies = [
        ("01", "千与千寻", "#cc744f", "#2c455a"),
        ("02", "星际穿越", "#314f80", "#101822"),
        ("03", "霸王别姬", "#9a2f39", "#261314"),
        ("04", "情书", "#7aa7b8", "#f0d6c4"),
    ]
    y = 760
    for idx, title, c1, c2 in movies:
        d.text((166, y + 40), idx, font=F["body_b"], fill=BLUE, anchor="lm")
        thumb = real_poster_thumb(title, c1, c2, 70, 100)
        base.alpha_composite(thumb, (260, y))
        d.text((360, y + 28), title, font=F["body_b"], fill=INK)
        d.text((360, y + 72), "来自一次次很小的偏爱选择", font=F["small"], fill=MUTED)
        d.line((166, y + 114, 1074, y + 114), fill="#efe7de", width=2)
        y += 118
    qr = qr_img(172).convert("RGBA")
    shadowed_card(base, (112, 1290, 1130, 1580), radius=34, fill="#fffdf8", outline=LINE)
    d = ImageDraw.Draw(base)
    base.alpha_composite(qr, (166, 1350))
    d.text((382, 1354), "扫码整理自己的已看总榜", font=F["body_b"], fill=INK)
    d.text((382, 1406), "给你的所有已看排出你的榜单", font=F["body"], fill=TERRA)
    d.text((382, 1458), "不用硬想完整顺序，只在两部电影之间作一次取舍。", font=F["small"], fill=MUTED)
    d.text((382, 1508), URL, font=F["small"], fill=MUTED)
    out = OUT / "04_douban_collect_result_poster.png"
    base.convert("RGB").save(out, quality=95)
    return out


if __name__ == "__main__":
    for path in (image_one(), image_two()):
        print(path)
