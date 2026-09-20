"""Reads forecast/latest.json (brief §2b) and turns one block's entry into the 4-week outlook message.

Shape: { block_id: { "onset"|"dry_spell"|"heavy_rain": [ {week, p, p_clim, confidence} x4 ] } }
Keys starting with "_" are metadata, not blocks. If "_meta.valid_from" is present, weeks get dates.
The file is re-read whenever its modification time changes, so the pipeline can overwrite it in place.
"""
from __future__ import annotations

import datetime as dt
import json
import threading

from .config import get_settings
from .locales import Locale
from .render.text import WEEK_EVENTS, chance, fmt_date

NOTABLE = 0.10   # a week is worth mentioning when an event is 1 in 10 or more above its usual chance
_cache: dict = {"mtime": None, "data": {}}
_lock = threading.Lock()


def latest() -> dict:
    path = get_settings().forecast_path
    try:
        mtime = path.stat().st_mtime
    except FileNotFoundError:
        return {}
    with _lock:
        if _cache["mtime"] != mtime:
            _cache["data"] = json.loads(path.read_text(encoding="utf-8"))
            _cache["mtime"] = mtime
        return _cache["data"]


def for_block(block_id: str) -> dict | None:
    rec = latest().get(block_id)
    if not isinstance(rec, dict) or not any(rec.get(e) for e in WEEK_EVENTS):
        return None
    return rec


def outlook_text(block_id: str, block_name: str, loc: Locale) -> str:
    rec = for_block(block_id)
    if rec is None:
        return loc.t("strings.outlook_unavailable", block=block_name)
    meta = latest().get("_meta") or {}
    start = None
    if meta.get("valid_from"):
        try:
            start = dt.date.fromisoformat(str(meta["valid_from"])[:10])
        except ValueError:
            start = None

    # One line per week, farmer-simple: only the event that differs most from normal, else "close to normal".
    lines = [f"*{loc.t('strings.outlook_title', block=block_name)}*", ""]
    for wk in range(1, 5):
        head = f"*{loc.t('strings.week_label', n=wk)}*"
        if start:
            s = start + dt.timedelta(days=7 * (wk - 1))
            head += f" · {fmt_date(s, loc)} – {fmt_date(s + dt.timedelta(days=6), loc)}"
        weeks = {ev: next((x for x in rec.get(ev) or [] if int(x.get("week", 0)) == wk), None) for ev in WEEK_EVENTS}
        weeks = {ev: w for ev, w in weeks.items() if w}
        if not weeks:
            continue
        ev, w = max(weeks.items(), key=lambda kv: kv[1]["p"] - kv[1]["p_clim"])
        if w["p"] - w["p_clim"] >= NOTABLE:
            line = loc.t("strings.outlook_line", event=loc.t(f"strings.ev_{ev}"),
                         chance=chance(w["p"], loc), usual=chance(w["p_clim"], loc))
        else:
            line = loc.t("strings.outlook_normal")
        lines.append(f"{head}\n{line}")
    lines += ["", f"_{loc.t('strings.outlook_footer')}_"]
    return "\n".join(lines)
