"""Advisory card: Jinja HTML -> 1080x1350 PNG through headless Chromium (Playwright)."""
from __future__ import annotations

import hashlib
import json
import re
import threading
from dataclasses import asdict
from functools import lru_cache
import os
import uuid
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

from ..config import ROOT, get_settings
from .text import Rendered

ASSETS = ROOT / "assets"
TEMPLATE_DIR = Path(__file__).parent / "templates"
FONT_FILES = {
    "Anek Latin": "AnekLatin.ttf",
    "Anek Kannada": "AnekKannada.ttf",
    "Anek Devanagari": "AnekDevanagari.ttf",
    "Anek Telugu": "AnekTelugu.ttf",
    "Anek Tamil": "AnekTamil.ttf",
}
# Text colour on each IMD band, chosen for contrast >= 4.5:1 in sunlight; tint/edge for the risk tiles.
BAND = {
    "green": ("#17722F", "#FFFFFF", "#17722F", "#E8F5EC"),
    "yellow": ("#F2C200", "#111111", "#B08D00", "#FFF8D6"),
    "orange": ("#F07B05", "#111111", "#C25E00", "#FFEEDD"),
    "red": ("#C62828", "#FFFFFF", "#C62828", "#FDE7E7"),
}
_render_lock = threading.Lock()   # one Chromium at a time: this laptop has 7.5 GB RAM


@lru_cache
def _env() -> Environment:
    return Environment(loader=FileSystemLoader(TEMPLATE_DIR), autoescape=select_autoescape(["html", "j2"]))


@lru_cache
def _icons() -> dict[str, str]:
    out = {}
    for f in (ASSETS / "icons").glob("*.svg"):
        svg = re.sub(r"<!--.*?-->", "", f.read_text(encoding="utf-8"), flags=re.S)
        svg = re.sub(r'\s(width|height|class|stroke-width)="[^"]*"', "", svg)
        out[f.stem] = svg.strip()
    return out


def card_html(r: Rendered, product: str) -> str:
    bg, ink, edge, tint = BAND[r.imd_colour]
    fonts = [{"family": fam, "url": (ASSETS / "fonts" / fn).as_uri()} for fam, fn in FONT_FILES.items()]
    return _env().get_template("card.html.j2").render(
        r=r, product=product, icons=_icons(), fonts=fonts, logo=(ASSETS / "brand" / "logo_256.png").as_uri(),
        band_bg=bg, band_ink=ink, band_edge=edge, band_tint=tint,
    )


def card_key(r: Rendered, product: str) -> str:
    tpl = (TEMPLATE_DIR / "card.html.j2").read_bytes() + (ASSETS / "brand" / "logo_256.png").read_bytes()[:4096]
    blob = json.dumps(asdict(r), sort_keys=True, ensure_ascii=False).encode() + product.encode() + tpl
    return hashlib.sha256(blob).hexdigest()[:16]


def render_card(r: Rendered, product: str) -> Path:
    """Render (or reuse) the card PNG for this exact rendered content. Returns the file path."""
    out_dir = get_settings().media_dir / "cards" / _safe(r.advisory_id)
    out = out_dir / f"{r.language}-{card_key(r, product)}.png"
    if out.exists():
        return out
    out_dir.mkdir(parents=True, exist_ok=True)
    tmp = out.with_name(f"{out.stem}-tmp{uuid.uuid4().hex[:8]}.x")   # own files: renders of one card may overlap
    html_path = tmp.with_suffix(".html")
    html_path.write_text(card_html(r, product), encoding="utf-8")

    from playwright.sync_api import sync_playwright

    with _render_lock, sync_playwright() as pw:
        browser = pw.chromium.launch()
        try:
            page = browser.new_page(viewport={"width": 1080, "height": 1350}, device_scale_factor=1)
            page.goto(html_path.as_uri())
            page.evaluate("document.fonts.ready")
            # Long translations: shrink type in small steps until nothing overflows the page.
            page.evaluate(
                """() => {
                  const root = document.documentElement;
                  let s = 1;
                  const main = document.getElementById('main');
                  const fits = () => main.scrollHeight <= main.clientHeight + 1 &&
                        [...document.querySelectorAll('.tile, .verdict h1')].every(e => e.scrollWidth <= e.clientWidth + 1);
                  while (!fits() && s > 0.6) { s -= 0.04; root.style.setProperty('--scale', s); }
                }"""
            )
            page.screenshot(path=str(tmp.with_suffix(".png")), clip={"x": 0, "y": 0, "width": 1080, "height": 1350})
        finally:
            browser.close()
    html_path.unlink(missing_ok=True)
    os.replace(tmp.with_suffix(".png"), out)   # atomic: readers never see half a file
    return out


def _safe(s: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]", "_", s)[:120]
