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
