"""Advisory lifecycle: ingest -> (hold for approval) -> fan out -> track status.

Nothing is sent to a farmer while an advisory with requires_approval=true is unapproved.
One log row per (advisory, subscriber, channel); a WhatsApp row is several messages (card, voice note,
text with buttons) tracked in dispatch_parts, and the row's status is derived from them.
"""
from __future__ import annotations

import datetime as dt
import json
import logging
import threading
from concurrent.futures import ThreadPoolExecutor
from zoneinfo import ZoneInfo

from . import db, subscribers
from .channels.whatsapp import ChannelError
from .config import get_settings
from .locales import get_locale
from .models import Advisory, Subscriber
from .render import voice
from .render.card import render_card
from .render.text import Rendered, TemplateError, render
from .runtime import rt

log = logging.getLogger(__name__)
RANK = {"queued": 0, "sent": 1, "delivered": 2, "read": 3}
_pool = ThreadPoolExecutor(max_workers=2, thread_name_prefix="dispatch")
_status_lock = threading.Lock()


class AdvisoryError(Exception):
    def __init__(self, status: int, detail: str) -> None:
        super().__init__(detail)
        self.status, self.detail = status, detail


# --------------------------------------------------------------------------- storage

def get(advisory_id: str) -> dict | None:
    rows = db.query("SELECT * FROM advisories WHERE advisory_id=?", (advisory_id,))
    if not rows:
        return None
    r = dict(rows[0])
    r["payload"] = json.loads(r["payload"])
    return r


def list_(state: str | None = None, block_id: str | None = None) -> list[dict]:
    sql, args = "SELECT advisory_id, block_id, state, received_ts, approved_ts, approved_by FROM advisories WHERE 1=1", []
    if state:
        sql, args = sql + " AND state=?", args + [state]
    if block_id:
        sql, args = sql + " AND block_id=?", args + [block_id]
    return [dict(r) for r in db.query(sql + " ORDER BY received_ts DESC", tuple(args))]


def advisory(advisory_id: str) -> Advisory:
    rec = get(advisory_id)
    if rec is None:
        raise AdvisoryError(404, f"advisory {advisory_id} not found")
    return Advisory.model_validate(rec["payload"])


def officer_for_block(block_id: str) -> dict | None:
    """Officer contact from the block's most recent advisory."""
    for r in db.query("SELECT payload FROM advisories WHERE block_id=? ORDER BY received_ts DESC", (block_id,)):
        off = json.loads(r["payload"]).get("officer")
        if off and off.get("phone"):
            return off
    return None


# --------------------------------------------------------------------------- ingest / approve

def ingest(adv: Advisory) -> dict:
    try:
        render(adv, "en")  # validates template id, required params, event names
    except TemplateError as e:
        raise AdvisoryError(422, str(e)) from e
    warnings = []
    today = dt.datetime.now(ZoneInfo(get_settings().timezone)).date()
    if adv.valid_to < today:
        if not get_settings().allow_expired_advisories:
            raise AdvisoryError(422, f"advisory expired on {adv.valid_to}; set ALLOW_EXPIRED_ADVISORIES=true for demos")
        warnings.append(f"advisory expired on {adv.valid_to} (accepted because ALLOW_EXPIRED_ADVISORIES=true)")

    payload = adv.model_dump_json()
    existing = get(adv.advisory_id)
    if existing:
        if json.dumps(existing["payload"], sort_keys=True) == json.dumps(json.loads(payload), sort_keys=True):
            return summary(adv.advisory_id, warnings=warnings + ["identical advisory already received"])
        if existing["state"] != "pending_approval":
            raise AdvisoryError(409, f"advisory {adv.advisory_id} is already {existing['state']}; send a new advisory_id")
        warnings.append("replaced an unapproved advisory with the same id")

    with db.tx() as c:
        c.execute("""INSERT INTO advisories(advisory_id, block_id, payload, state, received_ts)
                     VALUES (?,?,?,?,?)
                     ON CONFLICT(advisory_id) DO UPDATE SET payload=excluded.payload, state=excluded.state,
                       received_ts=excluded.received_ts, approved_ts=NULL, approved_by=NULL""",
                  (adv.advisory_id, adv.block.block_id, payload, "pending_approval", db.iso()))
    _pool.submit(_prerender, adv)
    if not adv.requires_approval:
        return approve(adv.advisory_id, "auto: requires_approval=false", warnings=warnings)
    return summary(adv.advisory_id, warnings=warnings)


def approve(advisory_id: str, by: str, note: str | None = None, warnings: list[str] | None = None) -> dict:
    with db.tx() as c:
        row = c.execute("SELECT state FROM advisories WHERE advisory_id=?", (advisory_id,)).fetchone()
        if row is None:
            raise AdvisoryError(404, f"advisory {advisory_id} not found")
        if row["state"] != "pending_approval":
            raise AdvisoryError(409, f"advisory is {row['state']}, not pending_approval")
        c.execute("UPDATE advisories SET state='approved', approved_ts=?, approved_by=?, decided_note=? "
                  "WHERE advisory_id=?", (db.iso(), by, note, advisory_id))
    adv = advisory(advisory_id)
    _create_rows(adv)
    _pool.submit(_run_dispatch, advisory_id)
    return summary(advisory_id, warnings=warnings)


def reject(advisory_id: str, by: str, note: str | None = None) -> dict:
    with db.tx() as c:
        row = c.execute("SELECT state FROM advisories WHERE advisory_id=?", (advisory_id,)).fetchone()
        if row is None:
            raise AdvisoryError(404, f"advisory {advisory_id} not found")
        if row["state"] != "pending_approval":
            raise AdvisoryError(409, f"advisory is {row['state']}, not pending_approval")
        c.execute("UPDATE advisories SET state='rejected', approved_ts=?, approved_by=?, decided_note=? "
                  "WHERE advisory_id=?", (db.iso(), by, note, advisory_id))
    return summary(advisory_id)


def summary(advisory_id: str, warnings: list[str] | None = None) -> dict:
    rec = get(advisory_id)
    adv = Advisory.model_validate(rec["payload"])
    tg = subscribers.targets(adv.block.block_id, adv.crop)
    return {
        "advisory_id": advisory_id, "state": rec["state"], "block_id": adv.block.block_id,
        "requires_approval": adv.requires_approval, "approved_by": rec["approved_by"],
        "approved_ts": rec["approved_ts"], "recipients": len(tg),
        "languages": sorted({s.language for s in tg}),
        "channels": _channel_counts(tg), "warnings": warnings or [],
    }


def _channel_counts(tg: list[Subscriber]) -> dict:
    return {"whatsapp": len(tg)}


def _channels(s: Subscriber) -> list[str]:
    return ["whatsapp"]


# --------------------------------------------------------------------------- rendering

def _prerender(adv: Advisory) -> None:
    """While the advisory waits for approval: queue voice notes and draw cards for every target language."""
    langs = {s.language for s in subscribers.targets(adv.block.block_id, adv.crop)} | {"en"}
    for lang in sorted(langs):
        try:
            r = render(adv, lang)
            voice.request(lang, r.speech_text)
            render_card(r, adv.product)
        except Exception:
            log.exception("prerender %s %s failed", adv.advisory_id, lang)


def preview(adv: Advisory, lang: str) -> tuple[Rendered, str]:
    r = render(adv, lang)
    return r, voice.request(lang, r.speech_text)


# --------------------------------------------------------------------------- fan-out

def _create_rows(adv: Advisory) -> None:
    with db.tx() as c:
        for s in subscribers.targets(adv.block.block_id, adv.crop):
            lang = get_locale(s.language).code
            for ch in _channels(s):
                provider = rt.wa.provider if rt.wa else "?"
                c.execute("""INSERT OR IGNORE INTO dispatch(advisory_id, subscriber_id, channel, language, status, ts,
                                                           block_id, provider)
                             VALUES (?,?,?,?,'queued',?,?,?)""",
                          (adv.advisory_id, s.subscriber_id, ch, lang, db.iso(), adv.block.block_id, provider))


def _run_dispatch(advisory_id: str) -> None:
    adv = advisory(advisory_id)
    # One shared wait for this advisory's voice notes, then send to everyone.
    rows = db.query("SELECT * FROM dispatch WHERE advisory_id=? AND status='queued' ORDER BY id", (advisory_id,))
    wa_langs = sorted({r["language"] for r in rows if r["channel"] == "whatsapp"})
    keys = [voice.request(lang, render(adv, lang).speech_text) for lang in wa_langs]
    voice_waited = False
    for row in rows:
        if row["channel"] == "whatsapp" and not voice_waited:
            voice.prioritise(keys)
            voice.wait_all(keys, get_settings().voice_wait_seconds)
            voice_waited = True
        sub = subscribers.get(row["subscriber_id"])
        if sub is None or sub.opted_out:
            _set_row(row["id"], "failed", "subscriber opted out before sending")
            continue
        try:
            r = render(adv, row["language"])
            _send_whatsapp(row["id"], adv, sub, r)
        except ChannelError as e:
            _set_row(row["id"], "failed", str(e)[:500])
        except Exception as e:
            log.exception("dispatch row %s failed", row["id"])
            _set_row(row["id"], "failed", f"internal error: {e}"[:500])
    with db.tx() as c:
        c.execute("UPDATE advisories SET state='dispatched' WHERE advisory_id=? AND state='approved'", (advisory_id,))


def resume_interrupted() -> list[str]:
    """Approved advisories with rows still queued (service stopped mid-send): send the rest."""
    ids = [r["advisory_id"] for r in db.query(
        "SELECT DISTINCT a.advisory_id FROM advisories a JOIN dispatch d USING(advisory_id) "
        "WHERE a.state='approved' AND d.status='queued'")]
    for aid in ids:
        _pool.submit(_run_dispatch, aid)
    return ids


def shutdown() -> None:
    """Let in-flight sends finish; drop queued pre-renders (they are redone on demand)."""
    _pool.shutdown(wait=True, cancel_futures=True)


def in_session_window(phone: str) -> bool:
    rows = db.query("SELECT last_inbound_ts FROM sessions WHERE phone=?", (phone,))
    if not rows or not rows[0]["last_inbound_ts"]:
        return False
    last = dt.datetime.fromisoformat(rows[0]["last_inbound_ts"])
    return db.now() - last < dt.timedelta(hours=get_settings().wa_session_hours)


def _send_whatsapp(row_id: int, adv: Advisory, sub: Subscriber, r: Rendered) -> None:
    wa = rt.wa
    if wa.provider == "meta-cloud" and not in_session_window(sub.phone):
        raise ChannelError("outside WhatsApp's 24-hour customer-service window: a business-initiated message "
                           "needs a Meta-approved utility template (see README, 'Production path')")
    loc = get_locale(r.language)
    card = render_card(r, adv.product)
    vkey = voice.request(r.language, r.speech_text)
    vpath = voice.ready(vkey)
    tracker = f"d{row_id}"

    _add_part(row_id, "card", wa.image(sub.phone, card, caption=f"{r.verdict} · {r.verdict_sub}", tracker=tracker))
    note = None
    if vpath:
        _add_part(row_id, "voice", wa.voice(sub.phone, vpath, tracker=tracker))
    else:
        st = voice.status(vkey) or {}
        note = f"sent without voice note (TTS {st.get('state', 'not queued')})"
    buttons = [("outlook", loc.t("strings.btn_outlook")), ("officer", loc.t("strings.btn_officer")),
               ("menu", loc.t("strings.btn_menu"))]
    _add_part(row_id, "text", wa.buttons(sub.phone, r.whatsapp_text, buttons, tracker=tracker))
    if note:
        with db.tx() as c:
            c.execute("UPDATE dispatch SET error=? WHERE id=?", (note, row_id))


def _add_part(row_id: int, part: str, provider_id: str) -> None:
    with db.tx() as c:
        c.execute("INSERT INTO dispatch_parts(dispatch_id, part, provider_id, status, ts) VALUES (?,?,?,?,?)",
                  (row_id, part, provider_id, "queued", db.iso()))
        if part == "text":
            c.execute("UPDATE dispatch SET message_ref=? WHERE id=?", (provider_id, row_id))
    # A status webhook can beat the INSERT above; replay anything that arrived early.
    early = _early.pop(provider_id, None)
    if early:
        on_status(provider_id, *early)


def _set_row(row_id: int, status: str, error: str | None) -> None:
    with db.tx() as c:
        c.execute("UPDATE dispatch SET status=?, error=?, ts=? WHERE id=?", (status, error, db.iso(), row_id))


# --------------------------------------------------------------------------- status updates

_early: dict[str, tuple[str, str | None]] = {}


def on_status(provider_id: str, status: str, error: str | None = None) -> None:
    """Apply a provider status (sent/delivered/read/played/failed) to its part, then recompute the row."""
    status = {"played": "read"}.get(status, status)
    if status not in RANK and status != "failed":
        return
    with _status_lock, db.tx() as c:
        part = c.execute("SELECT * FROM dispatch_parts WHERE provider_id=?", (provider_id,)).fetchone()
        if part is None:
            if len(_early) < 10_000:
                _early[provider_id] = (status, error)
            return
        cur = part["status"]
        if cur == "failed" or (status != "failed" and RANK.get(status, -1) <= RANK.get(cur, -1)):
            return  # statuses only move forward; late 'sent' after 'delivered' is ignored
        c.execute("UPDATE dispatch_parts SET status=?, error=?, ts=? WHERE id=?",
                  (status, error, db.iso(), part["id"]))
        parts = c.execute("SELECT part, status, error FROM dispatch_parts WHERE dispatch_id=?",
                          (part["dispatch_id"],)).fetchall()
        row = c.execute("SELECT status, error FROM dispatch WHERE id=?", (part["dispatch_id"],)).fetchone()
        failed = [p for p in parts if p["status"] == "failed"]
        if failed:
            new, err = "failed", f"{failed[0]['part']}: {failed[0]['error'] or 'failed'}"
        else:
            new, err = min((p["status"] for p in parts), key=RANK.__getitem__), row["error"]
        if new != row["status"] or err != row["error"]:
            c.execute("UPDATE dispatch SET status=?, error=?, ts=? WHERE id=?", (new, err, db.iso(), part["dispatch_id"]))

