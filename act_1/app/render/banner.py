"""Picture headers for the WhatsApp conversation (1200x630, WhatsApp's header shape).

welcome     Meghmitra banner with "welcome" in every language (first message)
block       mini-map: the farmer's block highlighted among its neighbours, drawn from the real boundaries
subscribed  tick, block and crop chips (sign-up done)
outlook     four week tiles with icons (the 4-week outlook)

Same pipeline as the advisory card (HTML -> Chromium PNG), cached by content so each banner is drawn once.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import os
import uuid
from pathlib import Path

import shapely

from .. import forecast, geo
from ..config import get_settings
from ..locales import Locale, load_locales
from .card import ASSETS, FONT_FILES, TEMPLATE_DIR, _env, _icons, _render_lock
from .text import WEEK_EVENTS, chance, crop_name, fmt_date

W, H = 1200, 630
LOGO = ASSETS / "brand" / "logo_256.png"
EVENT_ICON = {"onset": "cloud-rain", "dry_spell": "sun", "heavy_rain": "cloud-rain-wind"}
EVENT_MOOD = {"onset": "wet", "dry_spell": "hot", "heavy_rain": "hot"}


def _png(kind: str, lang: str, ctx: dict) -> Path:
    tpl = (TEMPLATE_DIR / "banner.html.j2").read_bytes() + LOGO.read_bytes()[:4096]
    key = hashlib.sha256(json.dumps([kind, lang, ctx], sort_keys=True, ensure_ascii=False).encode() + tpl).hexdigest()[:16]
    out = get_settings().media_dir / "banners" / f"{kind}-{lang}-{key}.png"
    if out.exists():
        return out
    out.parent.mkdir(parents=True, exist_ok=True)
    loc_font = load_locales()[lang].meta.get("font", "Anek Latin") if lang in load_locales() else "Anek Latin"
    fonts = [{"family": fam, "url": (ASSETS / "fonts" / fn).as_uri()} for fam, fn in FONT_FILES.items()]
    html = _env().get_template("banner.html.j2").render(kind=kind, lang=lang, font=loc_font, fonts=fonts,
                                                        icons=_icons(), logo=LOGO.as_uri(), **ctx)
    tmp = out.with_name(f"{out.stem}-tmp{uuid.uuid4().hex[:8]}.x")   # own files: renders of one card may overlap
    page_file = tmp.with_suffix(".html")
    page_file.write_text(html, encoding="utf-8")
    from playwright.sync_api import sync_playwright
    with _render_lock, sync_playwright() as pw:
        browser = pw.chromium.launch()
        try:
            page = browser.new_page(viewport={"width": W, "height": H})
            page.goto(page_file.as_uri())
            page.evaluate("document.fonts.ready")
            page.screenshot(path=str(tmp.with_suffix(".png")), clip={"x": 0, "y": 0, "width": W, "height": H})
        finally:
            browser.close()
    page_file.unlink(missing_ok=True)
    os.replace(tmp.with_suffix(".png"), out)   # atomic: readers never see half a file
    return out


def welcome() -> Path:
    locs = list(load_locales().values())
    words = list(dict.fromkeys(l.t("strings.welcome_word") for l in locs))
    return _png("welcome", "en", {"words": words, "tagline": load_locales()["en"].t("strings.tagline")})


def block_map(block_id: str, loc: Locale) -> Path:
    b = geo.block(block_id)
    ids, geoms, tree = geo._index()
    mine = geoms[ids.index(block_id)]
    minx, miny, maxx, maxy = mine.bounds
    pad = max(maxx - minx, maxy - miny) * 0.9
    box = shapely.box(minx - pad, miny - pad, maxx + pad, maxy + pad)
    others = [geoms[i] for i in tree.query(box, predicate="intersects") if ids[int(i)] != block_id]
    bx0, by0, bx1, by1 = box.bounds
    kx = __import__("math").cos(__import__("math").radians((by0 + by1) / 2))   # keep shapes true at this latitude
    span = max((bx1 - bx0) * kx, by1 - by0)

    def xy(x: float, y: float) -> tuple[float, float]:
        return round(15 + (x - bx0) * kx / span * 600, 1), round(615 - (y - by0) / span * 600, 1)

    def paths(g) -> list[str]:
        polys = getattr(g, "geoms", [g])
        out = []
        for p in polys:
            if p.geom_type != "Polygon":
                continue
            ring = p.simplify(span / 900).exterior.coords
            out.append("M" + " L".join(f"{a},{c}" for a, c in (xy(x, y) for x, y in ring)) + " Z")
        return out

    c = mine.representative_point()
    ctx = {"mine": paths(mine), "others": [p for g in others for p in paths(g.intersection(box))],
           "pin": xy(c.x, c.y), "block": b["name"], "district": b["district"], "state": b["state"],
           "your_block": loc.t("strings.your_block")}
    return _png("block", loc.code, ctx)


def subscribed(block_id: str, crops: list[str], loc: Locale) -> Path:
    b = geo.block(block_id) or {"name": block_id}
    return _png("subscribed", loc.code, {"title": loc.t("strings.subscribed_title"), "block": b["name"],
                                         "crops": [crop_name(c, loc) for c in crops],
                                         "tagline": loc.t("strings.tagline")})


def outlook(block_id: str, loc: Locale) -> Path | None:
    rec = forecast.for_block(block_id)
    if rec is None:
        return None
    meta = forecast.latest().get("_meta") or {}
    start = dt.date.fromisoformat(str(meta["valid_from"])[:10]) if meta.get("valid_from") else None
    tiles = []
    for wk in range(1, 5):
        weeks = {ev: next((x for x in rec.get(ev) or [] if int(x.get("week", 0)) == wk), None) for ev in WEEK_EVENTS}
        weeks = {ev: w for ev, w in weeks.items() if w}
        if not weeks:
            continue
        ev, w = max(weeks.items(), key=lambda kv: kv[1]["p"] - kv[1]["p_clim"])
        notable = w["p"] - w["p_clim"] >= forecast.NOTABLE
        dates = ""
        if start:
            s = start + dt.timedelta(days=7 * (wk - 1))
            dates = f"{fmt_date(s, loc)} – {fmt_date(s + dt.timedelta(days=6), loc)}"
        tiles.append({
            "week": wk, "label": loc.t("strings.week_label", n=wk), "dates": dates,
            "icon": EVENT_ICON[ev] if notable else "circle-check",
            "mood": EVENT_MOOD[ev] if notable else "calm",
            "event": loc.t(f"strings.ev_{ev}") if notable else loc.t("strings.outlook_normal"),
            "chance": chance(w["p"], loc) if notable else "",
            "usual": loc.t("strings.outlook_usual", usual=chance(w["p_clim"], loc)) if notable else "",
        })
    b = geo.block(block_id) or {"name": block_id}
    return _png("outlook", loc.code, {"title": loc.t("strings.outlook_title", block=b["name"]), "tiles": tiles,
                                      "block": b["name"]})
