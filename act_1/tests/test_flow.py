"""End to end in simulator mode: onboarding by taps, advisory approval, fan-out, status tracking."""
import json
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.main import app
from scripts.seed import main as seed_main  # noqa: F401  (import check only)

FIX = Path(__file__).resolve().parent.parent / "fixtures"
H = {"X-API-Key": "test-key"}
FARMER = "+919812345678"


@pytest.fixture(scope="module")
def c():
    with TestClient(app) as client:
        for s in json.loads((FIX / "subscribers.json").read_text(encoding="utf-8")):
            s["phone"] = s["phone"].split(":")[-1].rstrip("}") if s["phone"].startswith("${") else s["phone"]
            assert client.post("/subscribers", json=s, headers=H).status_code == 201
        yield client


def say(c, **kw):
    before = c.get("/dev/outbox", params={"phone": FARMER}).json()
    last = before[-1]["id"] if before else 0
    assert c.post("/dev/inbound", json={"phone": FARMER, **kw}).status_code == 200
    return [m for m in c.get("/dev/outbox", params={"phone": FARMER, "after": last}).json() if m["direction"] == "out"]


def wait_for(fn, timeout=20):
    end = time.time() + timeout
    while time.time() < end:
        if fn():
            return True
        time.sleep(0.3)
    return False


def test_auth_required(c):
    assert c.get("/dispatch/log").status_code == 401
    assert c.get("/dispatch/log", headers=H).status_code == 200


def test_dev_refuses_tunnel(c):
    r = c.post("/dev/inbound", json={"phone": FARMER, "text": "hi"}, headers={"CF-Connecting-IP": "1.2.3.4"})
    assert r.status_code == 403


def test_onboarding_by_taps(c):
    out = say(c, kind="text", text="hi")
    assert out[-1]["kind"] == "list" and any(r["id"] == "lang:kn" for r in out[-1]["payload"]["rows"])
    assert len(out[-1]["payload"]["rows"]) <= 10

    out = say(c, kind="list", payload="lang:kn")
    assert out[-1]["kind"] == "location_request"

    out = say(c, kind="location", lat=15.2566, lon=75.2486)          # Kundgol
    assert out[-1]["kind"] == "buttons" and "Kundgol" in out[-1]["payload"]["body"]
    assert len(out[-1]["payload"]["buttons"]) <= 3

    out = say(c, kind="button", payload="blk:yes")
    assert out[-1]["kind"] == "list" and out[-1]["payload"]["rows"][-1]["id"] == "crop:other"
    assert len(out[-1]["payload"]["rows"]) == 10
    out = say(c, kind="list", payload="crop:ragi")
    assert [b["id"] for b in out[-1]["payload"]["buttons"]] == ["crop:more", "crop:done"]
    out = say(c, kind="button", payload="crop:more")
    assert "✓" in [r["description"] for r in out[-1]["payload"]["rows"] if r["id"] == "crop:ragi"]
    say(c, kind="list", payload="crop:greengram")

    out = say(c, kind="button", payload="crop:done")
    ask = out[-1]                                     # when did it go in the ground?
    assert ask["kind"] == "list" and [r["id"] for r in ask["payload"]["rows"]][0] == "sow:recent"

    out = say(c, kind="list", payload="sow:mid")
    menu = out[-1]
    assert menu["kind"] == "buttons"
    assert [b["id"] for b in menu["payload"]["buttons"]] == ["outlook", "change_crop", "officer"]

    sub = next(s for s in c.get("/subscribers", headers=H).json() if s["phone"] == FARMER)
    assert sub["language"] == "kn" and sub["block_id"] == "7132399B30508081289508"
    assert sorted(sub["crops"]) == ["greengram", "ragi"] and sub["consent_ts"]


def test_outlook_from_forecast(c):
    out = say(c, kind="button", payload="outlook")
    assert len(out) == 1 and out[0]["kind"] == "buttons"      # outlook and menu arrive as one message
    text = out[0]["payload"]["body"]
    assert "Kundgol" in text and "10" in text and text.count("\n") < 20


def test_typed_menu_word_any_language(c):
    out = say(c, kind="text", text="नमस्ते")
    assert out[-1]["kind"] == "buttons"


def test_pin_and_pick_other_block(c):
    c.post("/dev/reset", params={"phone": FARMER})
    say(c, kind="text", text="language")
    say(c, kind="list", payload="lang:en")          # subscribed: just changes language
    sub = next(s for s in c.get("/subscribers", headers=H).json() if s["phone"] == FARMER)
    assert sub["language"] == "en"


def test_stop_and_start(c):
    out = say(c, kind="text", text="STOP")
    assert "unsubscribed" in out[-1]["payload"]["body"]
    sub = next(s for s in c.get("/subscribers", headers=H).json() if s["phone"] == FARMER)
    assert sub["opted_out"] is True
    out = say(c, kind="text", text="menu")
    assert "START" in out[-1]["payload"]["body"]
    out = say(c, kind="text", text="start")
    assert out[-1]["kind"] == "buttons"


def test_advisory_needs_approval_then_delivers(c):
    adv = json.loads((FIX / "advisories" / "01_kundgol_delay_sowing.json").read_text(encoding="utf-8"))
    r = c.post("/advisories", json=adv, headers=H)
    assert r.status_code == 201, r.text
    assert r.json()["state"] == "pending_approval"
    time.sleep(1)
    assert c.get("/dispatch/log", params={"advisory_id": adv["advisory_id"]}, headers=H).json() == []

    prev = c.get(f"/advisories/{adv['advisory_id']}/preview", params={"lang": "kn"}, headers=H).json()
    assert prev["card_url"].endswith(".png") and prev["whatsapp_text"]

    r = c.post(f"/advisories/{adv['advisory_id']}/approve", json={"approved_by": "ADA Kundgol"}, headers=H)
    assert r.status_code == 200 and r.json()["state"] == "approved"
    assert c.post(f"/advisories/{adv['advisory_id']}/approve", json={"approved_by": "x"}, headers=H).status_code == 409

    def delivered():
        rows = c.get("/dispatch/log", params={"advisory_id": adv["advisory_id"]}, headers=H).json()
        return rows and all(row["status"] == "delivered" for row in rows)
    assert wait_for(delivered, 60)

    rows = c.get("/dispatch/log", params={"advisory_id": adv["advisory_id"]}, headers=H).json()
    got = {(r["subscriber_id"], r["channel"], r["language"]) for r in rows}
    # Kannada farmer, the newly onboarded farmer (ragi), the Kundgol officer: WhatsApp only.
    assert ("sub-kn-kundgol-01", "whatsapp", "kn") in got and all(ch == "whatsapp" for _, ch, _ in got)
    assert ("off-en-kundgol-01", "whatsapp", "en") in got
    assert all(r["error"] is None or "voice" in r["error"] for r in rows)

    # WhatsApp message = card + text with buttons (voice note too once the TTS worker has rendered it).
    msgs = c.get("/dev/outbox", params={"phone": "+919000000001"}).json()
    kinds = [m["kind"] for m in msgs if m["channel"] == "whatsapp"]
    assert "image" in kinds and "buttons" in kinds

    c.post("/dev/read", params={"phone": "+919000000001"})
    assert wait_for(lambda: any(r["status"] == "read" for r in c.get(
        "/dispatch/log", params={"advisory_id": adv["advisory_id"]}, headers=H).json()), 10)

    s = c.get("/dispatch/summary", params={"block_id": "7132399B30508081289508"}, headers=H).json()
    assert s["total"] == len(rows) and s["by_channel"] == {"whatsapp": len(rows)} and "kn" in s["by_language"]

    since = rows[0]["ts"]
    assert all(r["ts"] >= since for r in c.get("/dispatch/log", params={"since": since}, headers=H).json())


def test_no_approval_needed_dispatches_at_once(c):
    adv = json.loads((FIX / "advisories" / "03_sehore_all_clear.json").read_text(encoding="utf-8"))
    r = c.post("/advisories", json=adv, headers=H)
    assert r.json()["state"] == "approved" and r.json()["approved_by"].startswith("auto")
    assert wait_for(lambda: c.get("/dispatch/log", params={"advisory_id": adv["advisory_id"]}, headers=H).json(), 30)


def test_validation(c):
    adv = json.loads((FIX / "advisories" / "02_navalgund_heavy_rain.json").read_text(encoding="utf-8"))
    bad = {**adv, "advisory_id": "x1", "template_id": "NOPE"}
    assert c.post("/advisories", json=bad, headers=H).status_code == 422
    bad = {**adv, "advisory_id": "x2", "template_id": "DELAY_SOWING", "params": {}}
    assert "wait_until" in c.post("/advisories", json=bad, headers=H).json()["detail"]
    bad = {**adv, "advisory_id": "x3", "cmri_class": "purple"}
    assert c.post("/advisories", json=bad, headers=H).status_code == 422


def test_reject(c):
    adv = json.loads((FIX / "advisories" / "02_navalgund_heavy_rain.json").read_text(encoding="utf-8"))
    assert c.post("/advisories", json=adv, headers=H).status_code == 201
    r = c.post(f"/advisories/{adv['advisory_id']}/reject", json={"approved_by": "ADA", "note": "wrong crop"}, headers=H)
    assert r.json()["state"] == "rejected"
    assert c.post(f"/advisories/{adv['advisory_id']}/approve", json={"approved_by": "x"}, headers=H).status_code == 409


def test_new_farmer_by_pin_and_no(c):
    p = "+919811112222"
    def s(**kw):
        c.post("/dev/inbound", json={"phone": p, **kw})
        return c.get("/dev/outbox", params={"phone": p}).json()[-1]
    s(kind="text", text="hello")
    s(kind="list", payload="lang:hi")
    m = s(kind="text", text="581 113")
    assert m["kind"] == "buttons"
    m = s(kind="button", payload="blk:no")
    assert m["kind"] == "list" and len(m["payload"]["rows"]) <= 10
    assert any(r["title"] == "Kundgol" for r in m["payload"]["rows"])
    kundgol = next(r["id"] for r in m["payload"]["rows"] if r["title"] == "Kundgol")
    m = s(kind="list", payload=kundgol)
    assert m["kind"] == "list" and m["payload"]["rows"][0]["id"].startswith("crop:")
    m = s(kind="text", text="000000")   # in CROPS state a PIN is just re-prompted, not crashed on
    assert m["kind"] == "list"


def test_typed_done_finishes_crops(c):
    p = "+919811133333"
    def s(**kw):
        c.post("/dev/inbound", json={"phone": p, **kw})
        return c.get("/dev/outbox", params={"phone": p}).json()[-1]
    s(kind="text", text="hi"); s(kind="list", payload="lang:en"); s(kind="location", lat=15.2566, lon=75.2486)
    s(kind="button", payload="blk:yes"); s(kind="list", payload="crop:ragi")
    m = s(kind="text", text="Done")
    assert m["kind"] == "list" and m["payload"]["rows"][0]["id"] == "sow:recent"
    m = s(kind="list", payload="sow:none")            # a farmer who has not sown yet can skip
    assert m["kind"] == "buttons" and [b["id"] for b in m["payload"]["buttons"]][0] == "outlook"


def test_other_crop_typed(c):
    p = "+919811144444"
    def s(**kw):
        c.post("/dev/inbound", json={"phone": p, **kw})
        return c.get("/dev/outbox", params={"phone": p}).json()[-1]
    s(kind="text", text="hi"); s(kind="list", payload="lang:kn"); s(kind="location", lat=15.2566, lon=75.2486)
    s(kind="button", payload="blk:yes")
    s(kind="list", payload="crop:other")
    m = s(kind="text", text="ಹುರುಳಿ")                     # Kannada for horse gram: a known crop, not in the list
    assert [b["id"] for b in m["payload"]["buttons"]] == ["crop:more", "crop:done"]
    s(kind="button", payload="crop:more"); s(kind="list", payload="crop:other")
    s(kind="text", text="Brinjal")                       # unknown crop: kept as typed
    s(kind="button", payload="crop:done")
    s(kind="list", payload="sow:recent")
    sub = next(x for x in c.get("/subscribers", headers=H).json() if x["phone"] == p)
    assert sub["crops"] == ["horsegram", "Brinjal"]
