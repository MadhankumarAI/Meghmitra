"""Contract endpoints: advisories (§2a), dispatch log and summary (§2c), subscribers (§2d)."""
from __future__ import annotations

import datetime as dt
import hmac

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request
from fastapi.responses import FileResponse
from pydantic import BaseModel

from .. import db, dispatch, geo, subscribers
from ..config import get_settings
from ..locales import load_locales
from ..models import Advisory, LogRow, SubscriberIn
from ..render import voice
from ..render.card import render_card
from ..render.text import TemplateError
from ..runtime import rt


def require_key(x_api_key: str | None = Header(default=None), key: str | None = Query(default=None)) -> None:
    expected = get_settings().admin_api_key
    if expected and not hmac.compare_digest((x_api_key or key or "").encode(), expected.encode()):
        raise HTTPException(401, "missing or wrong X-API-Key")


api = APIRouter(dependencies=[Depends(require_key)])
public = APIRouter()


def _err(e: dispatch.AdvisoryError):
    return HTTPException(e.status, e.detail)


# --------------------------------------------------------------------------- advisories

class Decision(BaseModel):
    approved_by: str
    note: str | None = None


@api.post("/advisories", status_code=201, tags=["advisories"])
def post_advisory(adv: Advisory) -> dict:
    """Receive an advisory. Held for approval when requires_approval=true, else dispatched at once."""
    try:
        return dispatch.ingest(adv)
    except dispatch.AdvisoryError as e:
        raise _err(e)


@api.get("/advisories", tags=["advisories"])
def list_advisories(state: str | None = None, block_id: str | None = None) -> list[dict]:
    return dispatch.list_(state, block_id)


@api.get("/advisories/{advisory_id}", tags=["advisories"])
def get_advisory(advisory_id: str) -> dict:
    rec = dispatch.get(advisory_id)
    if not rec:
        raise HTTPException(404, "not found")
    return {**dispatch.summary(advisory_id), "received_ts": rec["received_ts"], "note": rec["decided_note"],
            "advisory": rec["payload"]}


@api.post("/advisories/{advisory_id}/approve", tags=["advisories"])
def approve(advisory_id: str, d: Decision) -> dict:
    """Officer sign-off. Only now does anything reach a farmer."""
    try:
        return dispatch.approve(advisory_id, d.approved_by, d.note)
    except dispatch.AdvisoryError as e:
        raise _err(e)


@api.post("/advisories/{advisory_id}/reject", tags=["advisories"])
def reject(advisory_id: str, d: Decision) -> dict:
    try:
        return dispatch.reject(advisory_id, d.approved_by, d.note)
    except dispatch.AdvisoryError as e:
        raise _err(e)


@api.get("/advisories/{advisory_id}/preview", tags=["advisories"])
def preview(advisory_id: str, request: Request, lang: str = "en") -> dict:
    """Exactly what a subscriber in `lang` would receive: card, text and voice note, with review status."""
    if lang not in load_locales():
        raise HTTPException(422, f"unknown language {lang!r}; have {list(load_locales())}")
    try:
        adv = dispatch.advisory(advisory_id)
        r, vkey = dispatch.preview(adv, lang)
    except dispatch.AdvisoryError as e:
        raise _err(e)
    except TemplateError as e:
        raise HTTPException(422, str(e))
    card = render_card(r, adv.product)
    media = get_settings().media_dir
    vst = voice.status(vkey) or {}
    base = str(request.base_url).rstrip("/")
    return {
        "advisory_id": advisory_id, "language": r.language, "review_status": r.review_status,
        "cmri_class": r.cmri_class, "imd_colour": r.imd_colour, "verdict": r.verdict,
        "whatsapp_text": r.whatsapp_text, "speech_text": r.speech_text,
        "card_url": f"{base}/media/{card.relative_to(media).as_posix()}",
        "voice_state": vst.get("state"),
        "voice_url": f"{base}/media/voice/{vkey}.ogg" if vst.get("state") == "done" else None,
        "string_status": r.string_status, "warnings": r.warnings,
    }


@api.get("/advisories/{advisory_id}/card/{lang}.png", tags=["advisories"], response_class=FileResponse)
def card_png(advisory_id: str, lang: str):
    try:
        adv = dispatch.advisory(advisory_id)
        r, _ = dispatch.preview(adv, lang)
    except dispatch.AdvisoryError as e:
        raise _err(e)
    return FileResponse(render_card(r, adv.product), media_type="image/png")


# --------------------------------------------------------------------------- dispatch log (§2c)

def _since(since: str | None) -> str | None:
    if not since:
        return None
    try:
        t = dt.datetime.fromisoformat(since.replace("Z", "+00:00"))
    except ValueError:
        raise HTTPException(422, "since must be ISO 8601, e.g. 2026-06-21T06:00:00+05:30")
    if t.tzinfo is None:
        t = t.replace(tzinfo=dt.timezone.utc)
    return t.astimezone(dt.timezone.utc).isoformat()


def _where(block_id, since, advisory_id) -> tuple[str, list]:
    sql, args = " WHERE 1=1", []
    if block_id:
        sql, args = sql + " AND block_id=?", args + [block_id]
    if advisory_id:
        sql, args = sql + " AND advisory_id=?", args + [advisory_id]
    if s := _since(since):
        sql, args = sql + " AND ts>=?", args + [s]
    return sql, args


@api.get("/dispatch/log", response_model=list[LogRow], tags=["dispatch"])
def dispatch_log(block_id: str | None = None, since: str | None = None, advisory_id: str | None = None,
                 limit: int = Query(1000, le=10000)) -> list[dict]:
    """One row per (advisory, subscriber, channel). `ts` is the time of the last status change, so polling
    with since=<last ts seen> returns only rows that changed."""
    where, args = _where(block_id, since, advisory_id)
    rows = db.query("SELECT advisory_id, subscriber_id, channel, language, status, ts, error, block_id, provider, "
                    f"message_ref FROM dispatch{where} ORDER BY ts DESC, id DESC LIMIT ?", tuple(args + [limit]))
    return [dict(r) for r in rows]


@api.get("/dispatch/summary", tags=["dispatch"])
def dispatch_summary(block_id: str | None = None, since: str | None = None, advisory_id: str | None = None) -> dict:
    where, args = _where(block_id, since, advisory_id)
    out: dict = {"total": db.query(f"SELECT COUNT(*) n FROM dispatch{where}", tuple(args))[0]["n"]}
    for dim, col in (("by_status", "status"), ("by_channel", "channel"), ("by_language", "language"),
                     ("by_block", "block_id"), ("by_provider", "provider")):
        out[dim] = {r["k"]: r["n"] for r in db.query(
            f"SELECT {col} k, COUNT(*) n FROM dispatch{where} GROUP BY {col} ORDER BY n DESC", tuple(args))}
    return out


# --------------------------------------------------------------------------- subscribers (§2d)

@api.get("/subscribers", tags=["subscribers"])
def list_subscribers(block_id: str | None = None) -> list[dict]:
    return [s.model_dump() for s in subscribers.all_(block_id)]


@api.post("/subscribers", status_code=201, tags=["subscribers"])
def create_subscriber(s: SubscriberIn) -> dict:
    if not geo.block(s.block_id):
        raise HTTPException(422, f"unknown block_id {s.block_id}")
    if s.language not in load_locales():
        raise HTTPException(422, f"unknown language {s.language!r}")
    return subscribers.upsert(s).model_dump()


@api.get("/subscribers/{subscriber_id}", tags=["subscribers"])
def get_subscriber(subscriber_id: str) -> dict:
    s = subscribers.get(subscriber_id)
    if not s:
        raise HTTPException(404, "not found")
    return s.model_dump()


@api.patch("/subscribers/{subscriber_id}", tags=["subscribers"])
def patch_subscriber(subscriber_id: str, changes: dict) -> dict:
    s = subscribers.get(subscriber_id)
    if not s:
        raise HTTPException(404, "not found")
    return subscribers.upsert(SubscriberIn(**{**s.model_dump(), **changes, "subscriber_id": subscriber_id})).model_dump()


# --------------------------------------------------------------------------- status

@api.get("/health", tags=["ops"])
def health() -> dict:
    s = get_settings()
    langs = {}
    for code, loc in load_locales().items():
        counts: dict[str, int] = {}
        for e in loc.entries.values():
            counts[e.status] = counts.get(e.status, 0) + 1
        langs[code] = {"name": loc.name, "strings": counts}
    return {
        "whatsapp": rt.wa.provider if rt.wa else None,
        "notes": rt.notes, "tts_queue": voice.queue_depth(), "pin_source": geo.pin_source(),
        "forecast_path": str(s.forecast_path), "forecast_present": s.forecast_path.exists(),
        "subscribers": len(subscribers.all_()), "languages": langs,
    }

