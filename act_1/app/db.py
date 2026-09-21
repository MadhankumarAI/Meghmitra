"""SQLite storage. One short-lived connection per unit of work; WAL lets the TTS worker process share the file."""
from __future__ import annotations

import contextlib
import datetime as dt
import json
import sqlite3
from collections.abc import Iterator

from .config import get_settings

SCHEMA = """
CREATE TABLE IF NOT EXISTS advisories (
    advisory_id   TEXT PRIMARY KEY,
    block_id      TEXT NOT NULL,
    payload       TEXT NOT NULL,
    state         TEXT NOT NULL,     -- pending_approval | approved | dispatched | rejected
    received_ts   TEXT NOT NULL,
    approved_ts   TEXT,
    approved_by   TEXT,
    decided_note  TEXT
);
CREATE TABLE IF NOT EXISTS subscribers (
    subscriber_id TEXT PRIMARY KEY,
    phone         TEXT NOT NULL UNIQUE,
    channel_pref  TEXT NOT NULL,
    language      TEXT NOT NULL,
    block_id      TEXT NOT NULL,
    crops         TEXT NOT NULL,     -- JSON list
    role          TEXT NOT NULL,
    consent_ts    TEXT,
    opted_out     INTEGER NOT NULL DEFAULT 0,
    updated_ts    TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_sub_block ON subscribers(block_id);
-- What the panchayat knows about a farmer, kept between conversations. The phone number lives in
-- subscribers; everything here is the farm itself, and it is the same record an officer reads.
CREATE TABLE IF NOT EXISTS farmers (
    subscriber_id TEXT PRIMARY KEY REFERENCES subscribers(subscriber_id),
    name          TEXT,
    village       TEXT,              -- ADM5 name, as the map spells it
    panchayat     TEXT,
    district      TEXT,
    land_ha       REAL,
    soil          TEXT,              -- red | black | alluvial | laterite | sandy | clay | loam
    irrigation    TEXT,              -- rainfed | borewell | canal | tank | mixed
    plots         TEXT NOT NULL DEFAULT '[]',   -- JSON, survey numbers from the panchayat register
    registered_by TEXT,              -- the panchayat official who entered it
    registered_ts TEXT,
    confirmed_ts  TEXT,              -- when the farmer themselves confirmed it on WhatsApp
    updated_ts    TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_farmers_village ON farmers(village);
-- One row per crop a farmer has in the ground. The sowing date is what turns a block forecast into
-- advice for this farm: it says which growth stage the crop is in when the weather arrives.
CREATE TABLE IF NOT EXISTS crop_cycles (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    subscriber_id TEXT NOT NULL REFERENCES subscribers(subscriber_id),
    crop          TEXT NOT NULL,
    season        TEXT NOT NULL,     -- kharif-2026, rabi-2026
    sown_on       TEXT,
    area_ha       REAL,
    irrigation    TEXT,              -- overrides the farm default for this crop
    harvested_on  TEXT,
    source        TEXT NOT NULL,     -- panchayat | farmer | officer
    updated_ts    TEXT NOT NULL,
    UNIQUE (subscriber_id, crop, season)
);
CREATE INDEX IF NOT EXISTS ix_cycles_sub ON crop_cycles(subscriber_id);
-- The farmer's own history: every registration, every tap, every advisory, every alert. Read back
-- when we decide whether to send again, and shown to the officer before they approve.
CREATE TABLE IF NOT EXISTS farmer_events (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    subscriber_id TEXT NOT NULL,
    ts            TEXT NOT NULL,
    kind          TEXT NOT NULL,     -- registered | subscribed | crops_changed | language_changed |
                                     -- asked_outlook | asked_officer | asked_farm | advisory_sent |
                                     -- suppressed | opted_out | opted_in | note
    event         TEXT,              -- dry_spell | heavy_rain | onset, where the row is about one
    advisory_id   TEXT,
    detail        TEXT NOT NULL DEFAULT '{}'
);
CREATE INDEX IF NOT EXISTS ix_events_sub ON farmer_events(subscriber_id, id DESC);
CREATE INDEX IF NOT EXISTS ix_events_recent ON farmer_events(subscriber_id, kind, ts);
CREATE TABLE IF NOT EXISTS dispatch (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    advisory_id   TEXT NOT NULL,
    subscriber_id TEXT NOT NULL,
    channel       TEXT NOT NULL,
    language      TEXT NOT NULL,
    status        TEXT NOT NULL,
    ts            TEXT NOT NULL,     -- last status change
    error         TEXT,
    block_id      TEXT NOT NULL,
    provider      TEXT NOT NULL,
    message_ref   TEXT,
    UNIQUE (advisory_id, subscriber_id, channel)
);
CREATE INDEX IF NOT EXISTS ix_dispatch_ts ON dispatch(ts);
-- One advisory to one WhatsApp user is several messages (card, voice, text); each is tracked here.
CREATE TABLE IF NOT EXISTS dispatch_parts (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    dispatch_id   INTEGER NOT NULL REFERENCES dispatch(id),
    part          TEXT NOT NULL,
    provider_id   TEXT,
    status        TEXT NOT NULL,
    ts            TEXT NOT NULL,
    error         TEXT
);
CREATE INDEX IF NOT EXISTS ix_parts_provider ON dispatch_parts(provider_id);
CREATE TABLE IF NOT EXISTS sessions (
    phone           TEXT PRIMARY KEY,
    state           TEXT NOT NULL,
    data            TEXT NOT NULL,
    last_inbound_ts TEXT,
    updated_ts      TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS tts_jobs (
    key           TEXT PRIMARY KEY,  -- sha256 of engine+language+voice+text
    language      TEXT NOT NULL,
    text          TEXT NOT NULL,
    state         TEXT NOT NULL,     -- pending | running | done | failed
    path          TEXT,
    error         TEXT,
    engine        TEXT,
    priority      INTEGER NOT NULL DEFAULT 0,  -- 1 = an approved advisory is waiting for it
    created_ts    TEXT NOT NULL,
    updated_ts    TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS sim_outbox (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    channel       TEXT NOT NULL,     -- whatsapp
    direction     TEXT NOT NULL,     -- out | in
    phone         TEXT NOT NULL,
    kind          TEXT NOT NULL,
    payload       TEXT NOT NULL,
    provider_id   TEXT,
    ts            TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_sim_phone ON sim_outbox(phone, id);
"""


def now() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0)


def iso(ts: dt.datetime | None = None) -> str:
    return (ts or now()).isoformat()


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(get_settings().db_path, timeout=30, isolation_level=None)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA busy_timeout=30000")
    return conn


@contextlib.contextmanager
def tx() -> Iterator[sqlite3.Connection]:
    """A connection inside one IMMEDIATE transaction; commits on success, rolls back on error."""
    conn = _connect()
    try:
        conn.execute("BEGIN IMMEDIATE")
        yield conn
        conn.execute("COMMIT")
    except BaseException:
        conn.execute("ROLLBACK")
        raise
    finally:
        conn.close()


def query(sql: str, args: tuple | dict = ()) -> list[sqlite3.Row]:
    conn = _connect()
    try:
        return conn.execute(sql, args).fetchall()
    finally:
        conn.close()


def init_db() -> None:
    conn = _connect()
    try:
        conn.executescript(SCHEMA)
        cols = {r["name"] for r in conn.execute("PRAGMA table_info(farmers)")}
        if cols and "confirmed_ts" not in cols:
            conn.execute("ALTER TABLE farmers ADD COLUMN confirmed_ts TEXT")
        cols = {r["name"] for r in conn.execute("PRAGMA table_info(tts_jobs)")}
        if "priority" not in cols:  # databases created before the column existed
            conn.execute("ALTER TABLE tts_jobs ADD COLUMN priority INTEGER NOT NULL DEFAULT 0")
        # SMS was removed: every subscriber is on WhatsApp; old SMS log rows go.
        conn.execute("UPDATE subscribers SET channel_pref='whatsapp' WHERE channel_pref<>'whatsapp'")
        conn.execute("DELETE FROM dispatch_parts WHERE part='sms'")
        conn.execute("DELETE FROM dispatch WHERE channel='sms'")
        conn.execute("DELETE FROM sim_outbox WHERE channel='sms'")
    finally:
        conn.close()


def dumps(v) -> str:
    return json.dumps(v, ensure_ascii=False, default=str)
