from __future__ import annotations

import argparse
import sys
from io import BytesIO
from pathlib import Path
from typing import Dict, Iterable, List

from PIL import Image, ImageDraw, ImageFont, ImageOps, UnidentifiedImageError


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from launch_copy import FILM_CHALLENGE_TEMPLATES
from merged_douban_ranker_v3 import get_best_poster_bytes


OUT_DIR = ROOT / "assets" / "builtin_list_thumbnails"
THUMBNAIL_SIZE = (136, 192)
MAX_FILE_BYTES = 20 * 1024
WEBP_QUALITIES = (84, 80, 76, 72, 68, 64, 60, 56)


def encode_thumbnail(image: Image.Image) -> bytes:
    fitted = ImageOps.fit(
        image.convert("RGB"),
        THUMBNAIL_SIZE,
        method=Image.Resampling.LANCZOS,
        centering=(0.5, 0.5),
    )
    for quality in WEBP_QUALITIES:
        output = BytesIO()
        fitted.save(output, format="WEBP", quality=quality, method=6)
        encoded = output.getvalue()
        if len(encoded) <= MAX_FILE_BYTES:
            return encoded
    raise ValueError("compressed thumbnail is still larger than 20 KB")


def load_font(size: int) -> ImageFont.ImageFont:
    candidates = [
        Path(r"C:\Windows\Fonts\msyh.ttc"),
        Path(r"C:\Windows\Fonts\simhei.ttf"),
        Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
    ]
    for path in candidates:
        if path.exists():
            return ImageFont.truetype(str(path), size)
    return ImageFont.load_default()


def build_contact_sheet(templates: Iterable[Dict[str, object]], output_path: Path) -> None:
    rows = list(templates)
    columns = 6
    cell_width = 220
    cell_height = 258
    sheet = Image.new(
        "RGB",
        (columns * cell_width, ((len(rows) + columns - 1) // columns) * cell_height),
        "#f4f1ec",
    )
    draw = ImageDraw.Draw(sheet)
    id_font = load_font(17)
    title_font = load_font(16)
    for index, template in enumerate(rows):
        template_id = str(template["id"])
        title = str(template.get("card_poster_title") or "")
        path = ROOT / str(template.get("card_poster_asset") or "")
        column = index % columns
        row = index // columns
        x = column * cell_width
        y = row * cell_height
        with Image.open(path) as image:
            poster = image.convert("RGB")
        sheet.paste(poster, (x + 42, y + 8))
        draw.text((x + 8, y + 205), template_id, fill="#20242b", font=id_font)
        draw.text((x + 8, y + 229), title, fill="#625d57", font=title_font)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(output_path, format="PNG", optimize=True)


def selected_templates(ids: List[str]) -> List[Dict[str, object]]:
    by_id = {str(template["id"]): template for template in FILM_CHALLENGE_TEMPLATES}
    unknown = sorted(set(ids) - set(by_id))
    if unknown:
        raise ValueError(f"unknown template ids: {', '.join(unknown)}")
    return [by_id[template_id] for template_id in ids] if ids else list(FILM_CHALLENGE_TEMPLATES)


def generate(templates: Iterable[Dict[str, object]], overwrite: bool) -> List[str]:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    failures: List[str] = []
    for template in templates:
        template_id = str(template["id"])
        title = str(template.get("card_poster_title") or "").strip()
        relative_path = str(template.get("card_poster_asset") or "").strip()
        if not title or not relative_path:
            failures.append(f"{template_id}: missing card_poster_title or card_poster_asset")
            continue
        target = ROOT / relative_path
        if target.exists() and not overwrite:
            print(f"skip {template_id}: {target.relative_to(ROOT)}")
            continue
        poster_bytes = get_best_poster_bytes(title)
        if not poster_bytes:
            failures.append(f"{template_id}: no poster found for {title}")
            continue
        try:
            with Image.open(BytesIO(poster_bytes)) as source:
                encoded = encode_thumbnail(source)
        except (UnidentifiedImageError, OSError, ValueError) as exc:
            failures.append(f"{template_id}: {title}: {exc}")
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(encoded)
        print(f"write {template_id}: {target.relative_to(ROOT)} ({len(encoded)} bytes)")
    return failures


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate static light-list card thumbnails.")
    parser.add_argument("--overwrite", action="store_true", help="Regenerate assets that already exist.")
    parser.add_argument("--ids", nargs="*", default=[], help="Only process the listed template ids.")
    parser.add_argument("--contact-sheet", type=Path, help="Write a labeled PNG contact sheet after generation.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        templates = selected_templates([str(value) for value in args.ids])
    except ValueError as exc:
        print(exc, file=sys.stderr)
        return 2
    failures = generate(templates, bool(args.overwrite))
    if failures:
        print("\nFailed thumbnails:", file=sys.stderr)
        for failure in failures:
            print(f"- {failure}", file=sys.stderr)
        return 1
    if args.contact_sheet:
        build_contact_sheet(templates, args.contact_sheet.resolve())
        print(f"contact sheet: {args.contact_sheet.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
