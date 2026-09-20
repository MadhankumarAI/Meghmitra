"""Development simulator: a web 'phone' that talks to the bot through the same code path as WhatsApp.

Enabled only when DEV_MODE=true, and only for requests that did not come through the public tunnel.
"""
from __future__ import annotations

import json
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

from .. import bot, db, dispatch
from ..config import get_settings
from ..models import normalise_phone

STATIC = Path(__file__).resolve().parent.parent / "static"


def local_only(request: Request) -> None:
    if not get_settings().dev_mode:
        raise HTTPException(404)
    if request.headers.get("cf-connecting-ip") or request.headers.get("x-forwarded-for"):
        raise HTTPException(403, "dev routes are not served through the tunnel")


dev = APIRouter(prefix="/dev", dependencies=[Depends(local_only)], tags=["dev"])


class InboundIn(BaseModel):
    phone: str
    kind: str = "text"
    text: str | None = None
    payload: str | None = None
    title: str | None = None       # what the tapped button said, for the transcript
    lat: float | None = None
    lon: float | None = None


@dev.post("/inbound")
def inbound(m: InboundIn) -> dict:
    phone = normalise_phone(m.phone)
    shown = m.text or m.title or (f"Location {m.lat:.4f}, {m.lon:.4f}" if m.lat is not None else m.payload)
    with db.tx() as c:
        c.execute("INSERT INTO sim_outbox(channel, direction, phone, kind, payload, ts) VALUES ('whatsapp','in',?,?,?,?)",
                  (phone, m.kind, db.dumps({"body": shown}), db.iso()))
    bot.handle(bot.Inbound(phone=phone, kind=m.kind, text=m.text, payload=m.payload, lat=m.lat, lon=m.lon))
    return {"ok": True}


@dev.get("/outbox")
def outbox(phone: str, after: int = 0) -> list[dict]:
    rows = db.query("SELECT id, channel, direction, kind, payload, provider_id, ts FROM sim_outbox "
                    "WHERE phone=? AND id>? ORDER BY id", (normalise_phone(phone), after))
    media = get_settings().media_dir
    out = []
    for r in rows:
        p = json.loads(r["payload"])
        for src, dst in (("path", "url"), ("image", "image_url")):
            if p.get(src):
                try:
                    p[dst] = "/media/" + Path(p[src]).resolve().relative_to(media.resolve()).as_posix()
                except ValueError:
                    p[dst] = None
        out.append({**dict(r), "payload": p})
    return out


@dev.post("/read")
def mark_read(phone: str) -> dict:
    """The simulated phone opened the chat: every delivered message to it becomes 'read' (blue ticks)."""
    rows = db.query("SELECT provider_id FROM sim_outbox WHERE phone=? AND direction='out' AND provider_id IS NOT NULL",
                    (normalise_phone(phone),))
    for r in rows:
        dispatch.on_status(r["provider_id"], "read")
    return {"marked": len(rows)}


@dev.post("/reset")
def reset(phone: str) -> dict:
    """Forget the conversation for a phone (not the subscriber)."""
    p = normalise_phone(phone)
    with db.tx() as c:
        c.execute("DELETE FROM sessions WHERE phone=?", (p,))
        c.execute("DELETE FROM sim_outbox WHERE phone=?", (p,))
    return {"ok": True}


@dev.get("/phone", response_class=HTMLResponse)
def phone_page() -> str:
    return (STATIC / "phone.html").read_text(encoding="utf-8")
