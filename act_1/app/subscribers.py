"""Subscriber store (brief §2d)."""
from __future__ import annotations

import datetime as dt
import json
import uuid

from . import db
from .models import Subscriber, SubscriberIn


def _row(r) -> Subscriber:
    return Subscriber(
        subscriber_id=r["subscriber_id"], phone=r["phone"], channel_pref=r["channel_pref"], language=r["language"],
        block_id=r["block_id"], crops=json.loads(r["crops"]), role=r["role"],
        consent_ts=dt.datetime.fromisoformat(r["consent_ts"]) if r["consent_ts"] else None,
        opted_out=bool(r["opted_out"]),
    )


def get(subscriber_id: str) -> Subscriber | None:
    rows = db.query("SELECT * FROM subscribers WHERE subscriber_id=?", (subscriber_id,))
    return _row(rows[0]) if rows else None


def by_phone(phone: str) -> Subscriber | None:
    rows = db.query("SELECT * FROM subscribers WHERE phone=?", (phone,))
    return _row(rows[0]) if rows else None


def all_(block_id: str | None = None, include_opted_out: bool = True) -> list[Subscriber]:
    sql, args = "SELECT * FROM subscribers WHERE 1=1", []
    if block_id:
        sql += " AND block_id=?"
        args.append(block_id)
    if not include_opted_out:
        sql += " AND opted_out=0"
    return [_row(r) for r in db.query(sql + " ORDER BY subscriber_id", tuple(args))]


def upsert(s: SubscriberIn) -> Subscriber:
    """Insert or update by subscriber_id, else by phone. Keeps the id stable for a phone number."""
    existing = (get(s.subscriber_id) if s.subscriber_id else None) or by_phone(s.phone)
    sid = s.subscriber_id or (existing.subscriber_id if existing else f"sub-{uuid.uuid4().hex[:10]}")
    consent = s.consent_ts or (existing.consent_ts if existing else None) or db.now()
    with db.tx() as c:
        c.execute(
            """INSERT INTO subscribers(subscriber_id, phone, channel_pref, language, block_id, crops, role,
                                       consent_ts, opted_out, updated_ts)
               VALUES (?,?,?,?,?,?,?,?,?,?)
               ON CONFLICT(subscriber_id) DO UPDATE SET phone=excluded.phone, channel_pref=excluded.channel_pref,
                 language=excluded.language, block_id=excluded.block_id, crops=excluded.crops, role=excluded.role,
                 consent_ts=excluded.consent_ts, opted_out=excluded.opted_out, updated_ts=excluded.updated_ts""",
            (sid, s.phone, s.channel_pref, s.language, s.block_id, json.dumps(s.crops), s.role,
             consent.isoformat(), int(s.opted_out), db.iso()),
        )
    return get(sid)  # type: ignore[return-value]


def set_opted_out(phone: str, opted_out: bool) -> Subscriber | None:
    with db.tx() as c:
        c.execute("UPDATE subscribers SET opted_out=?, updated_ts=?"
                  + (", consent_ts=?" if not opted_out else "") + " WHERE phone=?",
                  (int(opted_out), db.iso(), *([db.iso()] if not opted_out else []), phone))
    return by_phone(phone)


def targets(block_id: str, crop: str | None) -> list[Subscriber]:
    """Who receives an advisory: everyone subscribed in the block who grows the crop, plus the block's officers."""
    crop = (crop or "all").lower()
    out = []
    for s in all_(block_id, include_opted_out=False):
        crops = {c.lower() for c in s.crops}
        if s.role == "officer" or crop == "all" or crop in crops or "all" in crops:
            out.append(s)
    return out
