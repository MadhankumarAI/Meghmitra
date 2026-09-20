"""Render an advisory into one language: WhatsApp text, speech script and card data.

Pure string templating over reviewed/machine-translated locale files. No language model runs here.
"""
from __future__ import annotations

import datetime as dt
import re
from dataclasses import dataclass, field

from babel.dates import format_date

from ..locales import Locale, get_locale, template_spec
from ..models import CMRI_TO_IMD, Advisory

WEEK_EVENTS = ("onset", "dry_spell", "heavy_rain")
EVENT_ICONS = {"onset": "cloud-rain", "dry_spell": "sun", "heavy_rain": "cloud-rain-wind"}
CMRI_ICONS = {"normal": "circle-check", "watch": "eye", "warning": "triangle-alert", "alert": "octagon-alert"}
IMD_HEX = {"green": "#1E8E3E", "yellow": "#F2C200", "orange": "#F07B05", "red": "#D32F2F"}


class TemplateError(ValueError):
    pass


# ---------------------------------------------------------------- small formatters

def fmt_date(d: dt.date | str, loc: Locale) -> str:
    if isinstance(d, str):
        d = dt.date.fromisoformat(d[:10])
    return format_date(d, "d MMMM", locale=loc.meta.get("babel", "en_IN"))


def chance(p: float, loc: Locale) -> str:
    """Natural frequency. Never says 10 in 10: a forecast is not a certainty."""
    n = min(9, round(float(p) * 10))
    return loc.t("strings.chance_lt1") if n <= 0 else loc.t("strings.chance", n=n)


def crop_name(crop_id: str | None, loc: Locale) -> str:
    cid = (crop_id or "all").lower()
    key = f"crops.{cid}"
    try:
        return loc.t(key)
    except KeyError:
        return crop_id or ""


def week_window(adv: Advisory, week: int) -> tuple[dt.date, dt.date]:
    start = adv.valid_from + dt.timedelta(days=7 * (week - 1))
    return start, start + dt.timedelta(days=6)


# ---------------------------------------------------------------- the render

@dataclass
class WeekTile:
    week: int
    start: str
    end: str
    event: str
    label: str
    p: float
    chance: str
    confidence: str
    confidence_label: str
    icon: str


@dataclass
class Rendered:
    advisory_id: str
    language: str
    cmri_class: str
    imd_colour: str
    imd_hex: str
    cmri_icon: str
    template_icon: str
    band_word: str
    band_meaning: str
    verdict: str
    verdict_sub: str
    headline: str
    reason: str | None
    actions: list[str]
    tiles: list[WeekTile]
    block_line: str
    validity: str
    source: str
    labels: dict
    whatsapp_text: str
    speech_text: str
    font: str
    review_status: str                        # reviewed only if every string used is reviewed
    string_status: dict[str, str] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)


def validate(adv: Advisory) -> None:
    spec = template_spec()
    if adv.template_id not in spec or not isinstance(spec[adv.template_id], dict):
        raise TemplateError(f"unknown template_id {adv.template_id!r}")
    missing = [p for p in spec[adv.template_id].get("required", []) if p not in adv.params]
    if missing:
        raise TemplateError(f"{adv.template_id} needs params {missing}")
    ev = adv.params.get("event")
    if ev is not None and ev not in spec["events"]:
        raise TemplateError(f"unknown params.event {ev!r}; known: {sorted(spec['events'])}")
    for key in ("wait_until", "sow_by"):
        if key in adv.params:
            try:
                dt.date.fromisoformat(str(adv.params[key])[:10])
            except ValueError as e:
                raise TemplateError(f"params.{key} is not a date: {adv.params[key]!r}") from e
    lw = adv.params.get("lead_week")
    if lw is not None and not (isinstance(lw, int) and 1 <= lw <= 4):
        raise TemplateError("params.lead_week must be an integer 1-4")


def render(adv: Advisory, language: str) -> Rendered:
    validate(adv)
    loc = get_locale(language)
    used: dict[str, str] = {}

    def t(key: str, **kw) -> str:
        used[key] = loc.status(key)
        return loc.t(key, **kw)

    p = adv.params
    ctx = {
        "crop": crop_name(adv.crop, loc),
        "block": adv.block.name,
        "district": adv.block.district,
        "state": adv.block.state,
        "valid_from": fmt_date(adv.valid_from, loc),
        "valid_to": fmt_date(adv.valid_to, loc),
        "wait_until": fmt_date(p["wait_until"], loc) if "wait_until" in p else "",
        "sow_by": fmt_date(p["sow_by"], loc) if "sow_by" in p else "",
        "alternative": crop_name(p.get("alternative"), loc) if p.get("alternative") else "",
    }
    for cid in filter(None, [adv.crop or "all", p.get("alternative")]):
        try:
            used[f"crops.{cid.lower()}"] = loc.status(f"crops.{cid.lower()}")
        except KeyError:
            pass  # unknown crop id: shown as sent by the engine

    tk = f"templates.{adv.template_id}"
    verdict = t(f"{tk}.verdict", **ctx)
    verdict_sub = t(f"{tk}.verdict_sub", **ctx)
    headline = t(f"{tk}.headline", **ctx)
    actions = [t(k, **ctx) for k in loc.list_keys(f"{tk}.actions")]

    reason = None
    if all(k in p for k in ("event", "p_event", "p_clim", "lead_week")):
        start, end = week_window(adv, int(p["lead_week"]))
        reason = t(
            "strings.reason",
            event=t(f"strings.event_{p['event']}"),
            start=fmt_date(start, loc),
            end=fmt_date(end, loc),
            chance=chance(p["p_event"], loc),
            usual=chance(p["p_clim"], loc),
        )

    tiles = []
    for w in adv.weeks:
        ev = max(WEEK_EVENTS, key=lambda e: getattr(w, e))
        s, e = week_window(adv, w.week)
        tiles.append(WeekTile(
            week=w.week, start=fmt_date(s, loc), end=fmt_date(e, loc), event=ev,
            label=t(f"strings.ev_{ev}"), p=getattr(w, ev), chance=chance(getattr(w, ev), loc),
            confidence=w.confidence, confidence_label=t(f"strings.confidence_{w.confidence}"),
            icon=EVENT_ICONS[ev],
        ))

    band_word = t(f"strings.cmri_{adv.cmri_class}")
    band_meaning = t(f"strings.imd_{adv.cmri_class}")
    block_line = f"{adv.block.name}, {adv.block.district}"
    validity = t("strings.valid", **ctx)
    source = t("strings.source", product=adv.product)
    labels = {
        "next_weeks": t("strings.next_weeks"),
        "what_to_do": t("strings.what_to_do"),
        "week": [t("strings.week_label", n=i) for i in range(1, 5)],
    }

    wa = [f"*{band_word.upper() if loc.code == 'en' else band_word} · {band_meaning}*", block_line, "",
          f"*{headline}*"]
    if reason:
        wa.append(reason)
    wa += ["", f"*{labels['what_to_do']}*"]
    wa += [f"{i}. {a}" for i, a in enumerate(actions, 1)]
    wa += ["", validity, source]
    whatsapp_text = "\n".join(wa)

    warnings: list[str] = []

    speech_parts = [f"{band_word}. {band_meaning}.", headline]
    if reason:
        speech_parts.append(reason)
    wtd = labels["what_to_do"]
    speech_parts.append(wtd if re.search(r"[.?!।]$", wtd) else wtd + ".")
    speech_parts += actions
    speech_text = speak(" ".join(speech_parts), loc)

    statuses = set(used.values()) - {"n/a"}
    review = "reviewed" if statuses <= {"reviewed"} else ("machine" if "machine" in statuses else sorted(statuses)[0])
    colour = CMRI_TO_IMD[adv.cmri_class]
    return Rendered(
        advisory_id=adv.advisory_id, language=loc.code, cmri_class=adv.cmri_class, imd_colour=colour,
        imd_hex=IMD_HEX[colour], cmri_icon=CMRI_ICONS[adv.cmri_class],
        template_icon=template_spec()[adv.template_id]["icon"], band_word=band_word, band_meaning=band_meaning,
        verdict=verdict, verdict_sub=verdict_sub, headline=headline, reason=reason, actions=actions, tiles=tiles,
        block_line=block_line, validity=validity, source=source, labels=labels, whatsapp_text=whatsapp_text,
        speech_text=speech_text,
        font=loc.meta.get("font", "Anek Latin"), review_status=review, string_status=used, warnings=warnings,
    )


# 1-2 digit numbers, including ones with an Indic case suffix attached ("10ರಲ್ಲಿ"); not parts of longer numbers.
_NUM = re.compile(r"(?<![\d.])(\d{1,2})(?![\d.])")


def speak(text: str, loc: Locale) -> str:
    """Script for the voice note: plain text, and small numbers as words when the locale lists them
    (`meta.number_words`, 0-31), so the TTS never has to guess how to read a digit."""
    words = loc.meta.get("number_words")
    text = text.replace("*", "").replace("·", ",")
    if words:
        text = _NUM.sub(lambda m: words[int(m.group(1))] if int(m.group(1)) < len(words) else m.group(1), text)
    for wrong, right in (loc.meta.get("speech_replace") or {}).items():   # sandhi fixes, per language
        text = text.replace(wrong, right)
    return re.sub(r"\s+", " ", text).strip()
