"""The farmer's record end to end: panchayat registration, confirming it on WhatsApp, and who an
alert actually reaches once we know the sowing date, the irrigation and what we told them last week."""
import datetime as dt
import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.main import app

FIX = Path(__file__).resolve().parent.parent / "fixtures"
H = {"X-API-Key": "test-key"}
BLOCK = "7132399B30508081289508"          # Kundgol, Dharwad
TODAY = dt.date.today()


@pytest.fixture(scope="module")
def c():
    with TestClient(app) as client:
        yield client


def register(c, phone, **kw):
    body = {"phone": phone, "block_id": BLOCK, "language": "en", "village": "Yettinhatti",
            "panchayat": "Yettinhatti gram panchayat", "district": "Dharwad", **kw}
    r = c.post("/farmers", json=body, params={"registered_by": "panchayat clerk"}, headers=H)
    assert r.status_code == 201, r.text
    return r.json()


def advisory(aid, **kw):
    adv = json.loads((FIX / "advisories" / "01_kundgol_delay_sowing.json").read_text(encoding="utf-8"))
    adv["advisory_id"] = aid
    adv.update(kw)
    return adv


def test_registration_keeps_the_land_record(c):
    ctx = register(c, "+919820000001", name="Ramesh", land_ha=1.2, soil="red", irrigation="rainfed",
                   plots=[{"survey_no": "114/2", "area_ha": 1.2, "soil": "red"}],
                   crops=[{"crop": "ragi", "sown_on": str(TODAY - dt.timedelta(days=60))}])
    assert ctx["profile"]["village"] == "Yettinhatti"
    assert ctx["profile"]["plots"][0]["survey_no"] == "114/2"
    # 60 days into a 110-day ragi crop: flowering, which is when a dry spell costs the most
    assert ctx["crops"][0] == dict(ctx["crops"][0], crop="ragi", stage="flowering")
    assert [e["kind"] for e in ctx["history"]][-1] == "registered"


def test_registering_twice_is_the_same_farmer(c):
    first = register(c, "+919820000001", name="Ramesh", land_ha=1.5)
    again = register(c, "+919820000001", name="Ramesh Gowda", land_ha=1.5)
    assert first["subscriber"]["subscriber_id"] == again["subscriber"]["subscriber_id"]
    assert again["profile"]["name"] == "Ramesh Gowda"


def test_farmer_confirms_what_the_panchayat_wrote(c):
    phone = "+919820000002"
    register(c, phone, name="Lakshmi", land_ha=0.8, irrigation="rainfed",
             crops=[{"crop": "maize", "sown_on": str(TODAY - dt.timedelta(days=10))}])

    def say(**kw):
        c.post("/dev/inbound", json={"phone": phone, **kw})
        return c.get("/dev/outbox", params={"phone": phone}).json()[-1]

    m = say(kind="text", text="hi")                      # not the language list: we already know her
    assert m["kind"] == "buttons"
    assert "Lakshmi" in m["payload"]["body"] and "Yettinhatti" in m["payload"]["body"]
    assert [b["id"] for b in m["payload"]["buttons"]] == ["id:yes", "id:fix", "id:notme"]

    m = say(kind="button", payload="id:yes")
    assert m["kind"] == "buttons" and [b["id"] for b in m["payload"]["buttons"]][0] == "outlook"
    sid = c.get(f"/farmers?block_id={BLOCK}", headers=H).json()
    me = next(f for f in sid if f["name"] == "Lakshmi")
    assert me["confirmed_ts"]

    m = say(kind="text", text="farm")                    # and she can read it back any time
    assert "Yettinhatti" in m["payload"]["body"] and "Maize" in m["payload"]["body"]


def test_wrong_number_stops_the_messages(c):
    phone = "+919820000003"
    register(c, phone, name="Someone Else")
    c.post("/dev/inbound", json={"phone": phone, "kind": "text", "text": "hi"})
    c.post("/dev/inbound", json={"phone": phone, "kind": "button", "payload": "id:notme"})
    sub = next(s for s in c.get("/subscribers", headers=H).json() if s["phone"] == phone)
    assert sub["opted_out"] is True
    hist = [e["kind"] for e in c.get(f"/farmers/{sub['subscriber_id']}", headers=H).json()["history"]]
    assert "disputed" in hist


def test_alert_goes_to_the_farms_it_can_hurt(c):
    """One dry-spell advisory, three farms: the reasons decide, not the block."""
    flowering = register(c, "+919820000011", name="At flowering", irrigation="rainfed",
                         crops=[{"crop": "ragi", "sown_on": str(TODAY - dt.timedelta(days=60))}])
    harvested = register(c, "+919820000012", name="Already off", irrigation="rainfed",
                         crops=[{"crop": "ragi", "sown_on": str(TODAY - dt.timedelta(days=140))}])
    canal = register(c, "+919820000013", name="On the canal", irrigation="canal",
                     crops=[{"crop": "ragi", "sown_on": str(TODAY - dt.timedelta(days=60))}])

    plan = c.post("/audience", json=advisory("aud-1"), headers=H).json()
    assert plan["event"] == "dry_spell"
    got = {m["subscriber_id"]: m for m in plan["matched"]}
    left = {s["subscriber_id"]: s["reason"] for s in plan["left_out"]}

    sid = lambda ctx: ctx["subscriber"]["subscriber_id"]          # noqa: E731
    assert got[sid(flowering)]["score"] == 3                       # the worst possible timing
    assert "flowering" in " ".join(got[sid(flowering)]["reasons"])
    assert sid(harvested) in left and "does not hurt" in left[sid(harvested)]
    assert got[sid(canal)]["score"] == 2                           # water to fall back on
    assert "canal" in " ".join(got[sid(canal)]["reasons"])


def test_only_the_villages_the_alert_names(c):
    other = register(c, "+919820000014", name="Next village over", village="Lebgera",
                     crops=[{"crop": "ragi", "sown_on": str(TODAY - dt.timedelta(days=60))}])
    adv = advisory("aud-2", villages=["Yettinhatti"])
    plan = c.post("/audience", json=adv, headers=H).json()
    left = {s["subscriber_id"]: s["reason"] for s in plan["left_out"]}
    assert other["subscriber"]["subscriber_id"] in left
    assert "not in the 1 villages" in left[other["subscriber"]["subscriber_id"]]


def test_nobody_hears_the_same_warning_twice(c):
    phone = "+919820000015"
    ctx = register(c, phone, name="Told yesterday", irrigation="rainfed",
                   crops=[{"crop": "ragi", "sown_on": str(TODAY - dt.timedelta(days=60))}])
    sid = ctx["subscriber"]["subscriber_id"]
    plan = c.post("/audience", json=advisory("aud-3"), headers=H).json()
    assert sid in {m["subscriber_id"] for m in plan["matched"]}

    from app import farmers
    farmers.remember(sid, "advisory_sent", event="dry_spell", advisory_id="aud-3",
                     detail={"cmri_class": "warning"})

    plan = c.post("/audience", json=advisory("aud-4"), headers=H).json()
    left = {s["subscriber_id"]: s["reason"] for s in plan["left_out"]}
    assert "already told about dry spell" in left[sid]

    # a red advisory goes out anyway: at that point everyone in the area hears it
    plan = c.post("/audience", json=advisory("aud-5", cmri_class="alert"), headers=H).json()
    assert sid in {m["subscriber_id"] for m in plan["matched"]}


def test_sowing_recorded_later_changes_who_is_warned(c):
    phone = "+919820000016"
    ctx = register(c, phone, name="No date yet", irrigation="rainfed", crops=[{"crop": "ragi"}])
    sid = ctx["subscriber"]["subscriber_id"]
    plan = c.post("/audience", json=advisory("aud-6"), headers=H).json()
    assert next(m for m in plan["matched"] if m["subscriber_id"] == sid)["score"] == 1

    r = c.post(f"/farmers/{sid}/crops", headers=H, params={"source": "farmer"},
               json={"crop": "ragi", "sown_on": str(TODAY - dt.timedelta(days=60))})
    assert r.status_code == 201
    plan = c.post("/audience", json=advisory("aud-7"), headers=H).json()
    assert next(m for m in plan["matched"] if m["subscriber_id"] == sid)["score"] == 3
