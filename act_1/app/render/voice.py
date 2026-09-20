"""Voice notes: content-addressed TTS cache shared with the TTS worker process (scripts/tts_worker.py).

The service only queues text; the worker (ML venv, AI4Bharat Indic Parler-TTS) renders OGG/Opus files.
Same language + speaker + text -> same key -> rendered once, reused for every subscriber and resend.
"""
from __future__ import annotations

import hashlib
import time
from pathlib import Path

from .. import db
from ..config import get_settings
from ..locales import get_locale

ENGINE = "indic-parler-tts"


def voice_key(language: str, text: str) -> tuple[str, str]:
    speaker = get_locale(language).meta.get("tts_speaker", "")
    engine = f"{ENGINE}:{speaker}"
    return hashlib.sha256(f"{engine}|{language}|{text}".encode()).hexdigest()[:24], engine


def voice_file(key: str) -> Path:
    return get_settings().media_dir / "voice" / f"{key}.ogg"


def request(language: str, text: str) -> str:
    """Queue a voice note (no-op if already queued or rendered). Returns its key."""
    key, engine = voice_key(language, text)
    # The .ogg on disk is the cache: a note rendered before (even under an older database) is reused as is.
    on_disk = voice_file(key).exists()
    with db.tx() as c:
        c.execute(
            "INSERT OR IGNORE INTO tts_jobs(key, language, text, state, path, engine, created_ts, updated_ts) "
            "VALUES (?,?,?,?,?,?,?,?)", (key, language, text, "done" if on_disk else "pending",
                                         str(voice_file(key)) if on_disk else None, engine, db.iso(), db.iso()))
        # A failed job is retried when someone asks for it again.
        c.execute("UPDATE tts_jobs SET state='pending', error=NULL, updated_ts=? WHERE key=? AND state='failed'",
                  (db.iso(), key))
    return key


def prioritise(keys: list[str]) -> None:
    """Move these notes to the front of the worker's queue (an approved advisory is waiting)."""
    if keys:
        with db.tx() as c:
            c.executemany("UPDATE tts_jobs SET priority=1 WHERE key=?", [(k,) for k in keys])


def wait_all(keys: list[str], timeout: float) -> None:
    """Block until every note is done or failed, or the one shared deadline passes."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        states = [(status(k) or {}).get("state") for k in keys]
        if all(s in ("done", "failed") for s in states):
            return
        time.sleep(2)


def status(key: str) -> dict | None:
    rows = db.query("SELECT key, language, state, path, error, updated_ts FROM tts_jobs WHERE key=?", (key,))
    return dict(rows[0]) if rows else None


def ready(key: str) -> Path | None:
    st = status(key)
    if st and st["state"] == "done":
        p = voice_file(key)
        return p if p.exists() else None
    return None


def queue_depth() -> dict:
    return {r["state"]: r["n"] for r in db.query("SELECT state, COUNT(*) n FROM tts_jobs GROUP BY state")}
