"""Preflight check before a live demo. Prints one line per check, with the fix when something is wrong.

    .venv\\Scripts\\python scripts\\doctor.py

Checks the local build (geo data, forecast, fonts, Chromium, ffmpeg, locales, subscribers, voice notes), and,
when configured: the Meta token and phone number id (Graph API), the tunnel (by doing Meta's own webhook
verification handshake through it) and the running service.
Makes only read-only calls. Exit code 1 if any check fails.
"""
from __future__ import annotations

import json
import shutil
import sqlite3
import sys
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.config import get_settings  # noqa: E402

OK, WARN, FAIL = "  ok  ", " warn ", " FAIL "
results: list[str] = []


def report(level: str, what: str, detail: str = "", fix: str = "") -> None:
    results.append(level)
    print(f"[{level}] {what}" + (f": {detail}" if detail else ""))
    if fix and level != OK:
        print(f"         -> {fix}")


def local(s) -> None:
    for f in ("blocks.json", "blocks_geom.pkl.gz", "pincodes.json"):
        p = s.geo_dir / f
        report(OK if p.exists() else FAIL, f"geo data {f}", "" if p.exists() else "missing",
               "run .venv\\Scripts\\python scripts\\build_geo.py")
    try:
        data = json.loads(s.forecast_path.read_text(encoding="utf-8"))
        n = sum(1 for k in data if not k.startswith("_"))
        report(OK, "forecast", f"{n} blocks in {s.forecast_path}")
    except Exception as e:
        report(FAIL, "forecast", str(e), "copy fixtures\\forecast\\latest.json to forecast\\latest.json")
    report(OK if shutil.which("ffmpeg") else FAIL, "ffmpeg on PATH", "", "winget install Gyan.FFmpeg")
    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as pw:
            exe = Path(pw.chromium.executable_path)
        report(OK if exe.exists() else FAIL, "Chromium for cards", "", ".venv\\Scripts\\python -m playwright install chromium")
    except Exception as e:
        report(FAIL, "Chromium for cards", str(e), ".venv\\Scripts\\python -m playwright install chromium")

    from app.locales import load_locales
    for code, loc in load_locales().items():
        counts: dict[str, int] = {}
        for e in loc.entries.values():
            counts[e.status] = counts.get(e.status, 0) + 1
        unreviewed = sum(v for k, v in counts.items() if k != "reviewed")
        level = OK if code == "en" or not unreviewed else WARN
        report(level, f"language {code} ({loc.meta.get('english_name', code)})", str(counts),
               f"native review needed: scripts\\review_sheet.py export {code}")

    if not s.db_path.exists():
        report(FAIL, "database", "not created yet", "run .venv\\Scripts\\python scripts\\seed.py")
        return
    c = sqlite3.connect(s.db_path)
    subs = c.execute("SELECT phone, language, channel_pref, role FROM subscribers WHERE opted_out=0").fetchall()
    fake = [p for p, *_ in subs if p.startswith("+9190000000")]
    report(OK if subs else FAIL, "subscribers", f"{len(subs)} active, {len(fake)} with placeholder numbers",
           "run scripts\\seed.py")
    if len(fake) == len(subs) and subs:
        report(WARN, "demo phones", "every subscriber has a placeholder number",
               "set DEMO_PHONE_1 (your WhatsApp test recipient) in .env and rerun scripts\\seed.py")
    try:
        q = dict(c.execute("SELECT state, COUNT(*) FROM tts_jobs GROUP BY state").fetchall())
    except sqlite3.OperationalError:
        q = {}
    level = FAIL if q.get("failed") else WARN if q.get("pending") or q.get("running") else OK
    report(level, "voice-note queue", str(q or "empty"), "start the TTS worker (scripts\\run.ps1) and let it finish")
    ml = ROOT / ".venv-ml" / "Scripts" / "python.exe"
    report(OK if ml.exists() else WARN, "ML venv for voice notes", "" if ml.exists() else "missing",
           "README section 6")


def whatsapp(s) -> None:
    if s.whatsapp_mode != "cloud":
        report(WARN, "WhatsApp mode", "simulator", "set WHATSAPP_MODE=cloud and the WA_* values (README section 3)")
        return
    for k in ("wa_phone_id", "wa_token", "wa_verify_token", "wa_app_secret", "admin_api_key"):
        report(OK if getattr(s, k) else FAIL, f".env {k.upper()}", "set" if getattr(s, k) else "missing",
               "README section 3")
    if not (s.wa_phone_id and s.wa_token):
        return
    from pywa.utils import Version
    url = f"https://graph.facebook.com/v{Version.GRAPH_API.value}/{s.wa_phone_id}"
    try:
        r = httpx.get(url, params={"fields": "display_phone_number,verified_name,quality_rating"},
                      headers={"Authorization": f"Bearer {s.wa_token}"}, timeout=20)
        if r.status_code == 200:
            d = r.json()
            report(OK, "Meta token + phone number id", f"{d.get('verified_name')} {d.get('display_phone_number')}")
        else:
            err = r.json().get("error", {})
            hint = "the temporary token lasts 24 h: generate a new one in API Setup" if err.get("code") == 190 \
                else "check WA_PHONE_ID is the 'Phone number ID', not the phone number"
            report(FAIL, "Meta token + phone number id", f"{r.status_code} {err.get('message', r.text[:200])}", hint)
    except httpx.HTTPError as e:
        report(FAIL, "Meta Graph API reachable", str(e), "check the internet connection")


def tunnel(s) -> None:
    if not s.public_base_url:
        if s.whatsapp_mode == "cloud":
            report(WARN, "tunnel", "PUBLIC_BASE_URL not set, so the webhook cannot be checked",
                   "run scripts\\tunnel.ps1 and put the https://...trycloudflare.com URL in PUBLIC_BASE_URL")
        return
    url = s.public_base_url.rstrip("/") + s.wa_webhook_path
    try:
        r = httpx.get(url, params={"hub.mode": "subscribe", "hub.verify_token": s.wa_verify_token,
                                   "hub.challenge": "doctor-42"}, timeout=20)
        good = r.status_code == 200 and r.text == "doctor-42"
        report(OK if good else FAIL, "webhook verification through the tunnel", f"{r.status_code} {r.text[:80]}",
               "service not running, tunnel URL changed, or WA_VERIFY_TOKEN differs from Meta's webhook config")
    except httpx.HTTPError as e:
        report(FAIL, "tunnel reachable", str(e), "restart scripts\\tunnel.ps1; the URL changes on every restart")


def service(s) -> None:
    try:
        r = httpx.get("http://127.0.0.1:8000/health", headers={"X-API-Key": s.admin_api_key}, timeout=10)
        if r.status_code == 200:
            h = r.json()
            report(OK, "service on :8000", f"whatsapp={h['whatsapp']}")
            for n in h.get("notes", []):
                if "NOT" in n or "not set" in n:
                    report(WARN, "service note", n)
        else:
            report(FAIL, "service on :8000", f"{r.status_code}", "check ADMIN_API_KEY matches the running service")
    except httpx.HTTPError:
        report(WARN, "service on :8000", "not running", "scripts\\run.ps1")


def main() -> None:
    s = get_settings()
    print(f"Preflight for {ROOT}\n")
    local(s)
    service(s)
    whatsapp(s)
    tunnel(s)
    fails = results.count(FAIL)
    print(f"\n{results.count(OK)} ok, {results.count(WARN)} warnings, {fails} failures")
    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    main()
