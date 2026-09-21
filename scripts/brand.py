"""Every brand image, cut from one source: act_1/dp.png.

  .venv/Scripts/python scripts/brand.py            rebuild them all
  .venv/Scripts/python scripts/brand.py --check    print what would change, write nothing

The logo is drawn once, as a round badge on white. Everything the product shows is a crop of it,
so replacing dp.png and running this is the whole brand update:

  the badge     the circle with the cream inside it, transparent outside, for the intro and the
                favicons and the social card
  the mark      just the cloud, leaf and raindrops, with the cream keyed out, for the header and
                anywhere the name is already written next to it
  the profile   the badge flattened onto white as a JPEG, which is what WhatsApp accepts

Cream is keyed out rather than cropped around, which is why the white swoosh inside the cloud is
transparent too: on a dark header that reads as the gap it is meant to be.
"""
from __future__ import annotations
import argparse
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "act_1" / "dp.png"

# Where the mark sits inside the badge, as a fraction of the badge. The side lines ("FORECAST
# ADVISE FARM BETTER") and the wordmark are outside this window, so the crop finds the mark alone.
MARK_WINDOW = (0.26, 0.04, 0.80, 0.465)     # left, top, right, bottom: drops end, wordmark begins
# The cream behind the mark is pale and almost grey (saturation about 28); the mark is saturated
# blue and green (about 63) and, where it is dark, dark. Keying on both keeps the mark's own dark
# edges and drops the cream gradient, which a brightness-only key leaves as a beige halo.
SAT_LO, SAT_SPAN = 32, 16                    # channel spread: transparent below, opaque above
DARK_AT, DARK_SPAN = 215, 25                 # min channel: opaque below
SS = 4                                       # supersampling for the circular edge


def badge(im: Image.Image) -> Image.Image:
    """The round logo on its own, square, with everything outside the circle transparent."""
    a = np.array(im.convert("RGB")).astype(int)
    ink = a.min(-1) < 246                                  # anything that is not the page white
    ys, xs = np.where(ink)
    if not len(ys):
        sys.exit(f"{SRC} looks blank")
    y0, y1, x0, x1 = ys.min(), ys.max() + 1, xs.min(), xs.max() + 1
    side = max(y1 - y0, x1 - x0)
    cy, cx = (y0 + y1) // 2, (x0 + x1) // 2
    box = (cx - side // 2, cy - side // 2, cx - side // 2 + side, cy - side // 2 + side)
    out = im.convert("RGB").crop(box)
    mask = Image.new("L", (side * SS, side * SS), 0)       # drawn large, then shrunk: clean edge
    ImageDraw.Draw(mask).ellipse((0, 0, side * SS - 1, side * SS - 1), fill=255)
    out.putalpha(mask.resize((side, side), Image.LANCZOS))
    return out


def mark(badge_im: Image.Image) -> Image.Image:
    """The cloud, leaf and raindrops, with the cream background keyed out."""
    w, h = badge_im.size
    l, t, r, b = MARK_WINDOW
    win = badge_im.convert("RGB").crop((int(w * l), int(h * t), int(w * r), int(h * b)))
    a = np.array(win).astype(np.float32)
    sat = a.max(-1) - a.min(-1)
    alpha = np.clip(np.maximum((sat - SAT_LO) / SAT_SPAN,
                               (DARK_AT - a.min(-1)) / DARK_SPAN), 0, 1) * 255
    out = win.convert("RGBA")
    out.putalpha(Image.fromarray(alpha.astype(np.uint8)))
    # trim to what is actually drawn, with a hair of margin so nothing touches the edge
    box = out.getchannel("A").point(lambda v: 255 if v > 16 else 0).getbbox()
    if box is None:
        sys.exit("no mark found inside MARK_WINDOW: check the window against the new logo")
    pad = max(2, (box[2] - box[0]) // 100)
    return out.crop((max(0, box[0] - pad), max(0, box[1] - pad),
                     min(out.width, box[2] + pad), min(out.height, box[3] + pad)))


def fit(im: Image.Image, w: int, h: int) -> Image.Image:
    """Scale to fit w x h, keeping the aspect, centred on transparency."""
    s = min(w / im.width, h / im.height)
    r = im.resize((max(1, round(im.width * s)), max(1, round(im.height * s))), Image.LANCZOS)
    out = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    out.paste(r, ((w - r.width) // 2, (h - r.height) // 2), r)
    return out


def square(im: Image.Image, n: int) -> Image.Image:
    return fit(im, n, n)


def on_white(im: Image.Image, n: int) -> Image.Image:
    bg = Image.new("RGB", (n, n), "white")
    r = im.resize((n, n), Image.LANCZOS)
    bg.paste(r, (0, 0), r)
    return bg


def write(path: Path, im: Image.Image, check: bool, **kw) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    before = path.stat().st_size if path.exists() else 0
    if check:
        print(f"   would write {path.relative_to(ROOT)}  {im.size} (was {before:,} bytes)")
        return
    im.save(path, **kw)
    print(f"   {path.relative_to(ROOT)}  {im.size}  {before:,} -> {path.stat().st_size:,} bytes")


def main(check: bool) -> None:
    if not SRC.exists():
        sys.exit(f"{SRC} not found")
    src = Image.open(SRC)
    b = badge(src)
    m = mark(b)
    print(f"{SRC.relative_to(ROOT)} {src.size} -> badge {b.size}, mark {m.size}")

    web, app, brand = ROOT / "web" / "public" / "brand", ROOT / "web" / "src" / "app", ROOT / "act_1" / "assets" / "brand"
    write(web / "badge-640.png", b.resize((640, 640), Image.LANCZOS), check)
    write(web / "badge-192.png", b.resize((192, 192), Image.LANCZOS), check)
    write(web / "mark.png", square(m, 256), check)
    write(web / "mark-wide.png", fit(m, 277, 207), check)
    write(app / "icon.png", b.resize((192, 192), Image.LANCZOS), check)
    write(app / "apple-icon.png", b.resize((180, 180), Image.LANCZOS), check)
    # the delivery service draws the card and the banner with these
    write(brand / "logo_256.png", on_white(b, 256), check)
    write(brand / "profile_640.jpg", on_white(b, 640), check, quality=92)
    write(brand / "meghmitra_logo.png", src.convert("RGB"), check)
    old = brand / "mungaru_logo.png"
    if old.exists() and not check:
        old.unlink()
        print(f"   removed {old.relative_to(ROOT)} (renamed with the product)")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--check", action="store_true", help="print what would change, write nothing")
    main(ap.parse_args().check)
