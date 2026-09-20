"""Meta Cloud API path, offline: real-shaped webhook payloads go through pywa into the bot and status pipeline.

Runs the app in a subprocess with WHATSAPP_MODE=cloud and dummy credentials (no network calls are made).
"""
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

SCRIPT = r'''
import json, time, hmac, hashlib
from fastapi.testclient import TestClient
from app import bot, dispatch
got, st = [], []
bot.handle = lambda ev: got.append([ev.phone, ev.kind, ev.text, ev.payload, ev.lat, ev.lon])
dispatch.on_status = lambda *a: st.append(list(a))
from app.main import app
CONTACT = {"profile": {"name": "Farmer"}, "wa_id": "919812345678", "user_id": "IN.1234567890"}
def wh(value):
    return {"object": "whatsapp_business_account", "entry": [{"id": "WABA", "changes": [{"field": "messages", "value": {
        "messaging_product": "whatsapp", "metadata": {"display_phone_number": "15550000000", "phone_number_id": "123456789"},
        "contacts": [CONTACT], **value}}]}]}
def post(c, body, secret="s3cret"):
    raw = json.dumps(body).encode()
    sig = "sha256=" + hmac.new(secret.encode(), raw, hashlib.sha256).hexdigest()
    return c.post("/whatsapp/webhook", content=raw, headers={"Content-Type": "application/json", "X-Hub-Signature-256": sig}).status_code
out = {}
with TestClient(app) as c:
    out["verify"] = c.get("/whatsapp/webhook", params={"hub.mode": "subscribe", "hub.verify_token": "vt123", "hub.challenge": "42"}).text
    out["verify_bad"] = c.get("/whatsapp/webhook", params={"hub.mode": "subscribe", "hub.verify_token": "no", "hub.challenge": "42"}).status_code
    m = lambda i, **kw: {"from": "919812345678", "id": f"wamid.{i}", "timestamp": "1760000000", **kw}
    out["posts"] = [post(c, wh({"messages": [x]})) for x in [
        m(1, type="text", text={"body": "hi"}),
        m(2, context={"from": "15550000000", "id": "wamid.OUTB"}, type="interactive", interactive={"type": "button_reply", "button_reply": {"id": "blk:yes", "title": "Yes"}}),
        m(3, context={"from": "15550000000", "id": "wamid.OUTL"}, type="interactive", interactive={"type": "list_reply", "list_reply": {"id": "lang:kn", "title": "x"}}),
        m(4, type="location", location={"latitude": 15.2566, "longitude": 75.2486}),
    ]]
    out["forged"] = post(c, wh({"messages": [m(5, type="text", text={"body": "hi"})]}), secret="wrong")
    post(c, wh({"statuses": [{"id": "wamid.OUT1", "status": "delivered", "timestamp": "1760000009", "recipient_id": "919812345678"}]}))
    post(c, wh({"statuses": [{"id": "wamid.OUT2", "status": "failed", "timestamp": "1760000009", "recipient_id": "919812345678",
                              "errors": [{"code": 131047, "title": "Re-engagement message", "message": "Re-engagement message"}]}]}))
    time.sleep(2)
out["got"], out["st"] = got, st
print("RESULT" + json.dumps(out))
'''


def test_meta_webhook_through_pywa(tmp_path):
    env = {**os.environ, "DB_PATH": str(tmp_path / "t.db"), "MEDIA_DIR": str(tmp_path / "m"), "WHATSAPP_MODE": "cloud",
           "WA_PHONE_ID": "123456789", "WA_TOKEN": "dummy", "WA_VERIFY_TOKEN": "vt123", "WA_APP_SECRET": "s3cret"}
    p = subprocess.run([sys.executable, "-c", SCRIPT], cwd=ROOT, env=env, capture_output=True, text=True, timeout=120)
    line = next((l for l in p.stdout.splitlines() if l.startswith("RESULT")), None)
    assert line, p.stdout[-2000:] + p.stderr[-3000:]
    out = json.loads(line[6:])
    assert out["verify"] == "42" and out["verify_bad"] == 403
    assert out["posts"] == [200, 200, 200, 200] and out["forged"] in (401, 403)
    assert ["+919812345678", "text", "hi", None, None, None] in out["got"]
    assert ["+919812345678", "button", None, "blk:yes", None, None] in out["got"]
    assert ["+919812345678", "list", None, "lang:kn", None, None] in out["got"]
    assert ["+919812345678", "location", None, None, 15.2566, 75.2486] in out["got"]
    assert len(out["got"]) == 4                     # the forged one never reached the bot
    assert ["wamid.OUT1", "delivered", None] in out["st"]
    failed = next(s for s in out["st"] if s[0] == "wamid.OUT2")
    assert failed[1] == "failed" and "131047" in failed[2]
