"""The farmer's long-term record: who they are, what is in the ground, and what we have told them.

Three things live here.

  profile      the panchayat register: name, village, land, soil, irrigation, survey numbers.
               Entered once by panchayat staff, corrected by the farmer or an officer, never by us.
  crop cycles  one row per crop in the ground, with its sowing date. A sowing date is what turns a
               block forecast into advice for one farm: it says which growth stage the crop will be
               in when the weather arrives.
  memory       every registration, tap, advisory and alert, in order. It is read back before we send
               (so nobody is told the same thing twice in a week) and shown to the officer before
               they approve.

Nothing here is inferred from the weather. Stages come from the sowing date the farmer gave us.
"""
from __future__ import annotations

import datetime as dt
import json

from . import db
from .models import CropCycle, FarmerProfile

# Days from sowing to harvest, and the fraction of that run each stage occupies. Durations are the
# common short-duration varieties in the ICAR contingency plans; a crop we do not know falls back to
# DEFAULT_DURATION, which is close enough to place a 10-day dry spell in the right half of the season.
DURATION = {
    "ragi": 110, "maize": 105, "paddy": 130, "rice": 130, "jowar": 110, "sorghum": 110,
    "bajra": 85, "pearlmillet": 85, "groundnut": 105, "tur": 160, "pigeonpea": 160,
    "cotton": 165, "soybean": 100, "sunflower": 95, "horsegram": 95, "greengram": 70,
    "blackgram": 75, "redgram": 160, "sugarcane": 330, "onion": 120, "tomato": 120,
}
DEFAULT_DURATION = 110
# (stage id, the fraction of the season it ends at)
STAGES = [("sowing", 0.12), ("vegetative", 0.42), ("flowering", 0.62), ("filling", 0.85), ("maturity", 1.0)]
# Which stages an event actually hurts. A dry spell in flowering costs yield; the same dry spell a
# fortnight after sowing is survivable. Heavy rain matters most when the crop is ready to come off.
HARMFUL = {
    "dry_spell": {"flowering": 3, "filling": 2, "sowing": 2, "vegetative": 1, "maturity": 0},
    "heavy_rain": {"maturity": 3, "filling": 2, "flowering": 1, "sowing": 2, "vegetative": 0},
    "onset": {"sowing": 3, "vegetative": 0, "flowering": 0, "filling": 0, "maturity": 0},
}


def season_of(on: dt.date | None = None) -> str:
    """Indian crop season, the way a panchayat register writes it: kharif June to October, else rabi."""
    d = on or dt.date.today()
    return f"kharif-{d.year}" if 6 <= d.month <= 10 else f"rabi-{d.year if d.month > 10 else d.year - 1}"


def stage_on(sown_on: dt.date | None, crop: str, when: dt.date) -> str | None:
    """Growth stage of this crop on a given day, or None when we were never told the sowing date."""
    if not sown_on:
        return None
    days = (when - sown_on).days
    if days < 0:
        return "before_sowing"
    run = DURATION.get(crop.lower(), DEFAULT_DURATION)
    if days > run:
        return "harvested"
    share = days / run
    for name, end in STAGES:
        if share <= end:
            return name
    return "maturity"


def harm(event: str, stage: str | None) -> int:
    """0 no harm at this stage, 3 the worst. Unknown stage scores 1: we send, but we do not shout."""
    if stage in ("before_sowing", "harvested"):
        return 0
    if stage is None:
        return 1
    return HARMFUL.get(event, {}).get(stage, 1)


# --------------------------------------------------------------------------- profile

def _profile(r) -> FarmerProfile:
    return FarmerProfile(
        subscriber_id=r["subscriber_id"], name=r["name"], village=r["village"], panchayat=r["panchayat"],
        district=r["district"], land_ha=r["land_ha"], soil=r["soil"], irrigation=r["irrigation"],
        plots=json.loads(r["plots"] or "[]"), registered_by=r["registered_by"],
        registered_ts=dt.datetime.fromisoformat(r["registered_ts"]) if r["registered_ts"] else None,
        confirmed_ts=dt.datetime.fromisoformat(r["confirmed_ts"]) if r["confirmed_ts"] else None,
    )


def profile(subscriber_id: str) -> FarmerProfile | None:
    rows = db.query("SELECT * FROM farmers WHERE subscriber_id=?", (subscriber_id,))
    return _profile(rows[0]) if rows else None


def profiles(block_id: str | None = None, village: str | None = None) -> list[FarmerProfile]:
    sql = "SELECT f.* FROM farmers f JOIN subscribers s USING(subscriber_id) WHERE 1=1"
    args: list = []
    if block_id:
        sql, args = sql + " AND s.block_id=?", args + [block_id]
    if village:
        sql, args = sql + " AND f.village=? COLLATE NOCASE", args + [village]
    return [_profile(r) for r in db.query(sql + " ORDER BY f.village, f.name", tuple(args))]


def save_profile(p: FarmerProfile, by: str | None = None) -> FarmerProfile:
    """Write the panchayat's record. The first write is the registration and is remembered as one."""
    first = profile(p.subscriber_id) is None
    with db.tx() as c:
        c.execute(
            """INSERT INTO farmers(subscriber_id, name, village, panchayat, district, land_ha, soil,
                                   irrigation, plots, registered_by, registered_ts, updated_ts)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
               ON CONFLICT(subscriber_id) DO UPDATE SET name=excluded.name, village=excluded.village,
                 panchayat=excluded.panchayat, district=excluded.district, land_ha=excluded.land_ha,
                 soil=excluded.soil, irrigation=excluded.irrigation, plots=excluded.plots,
                 registered_by=COALESCE(excluded.registered_by, farmers.registered_by),
                 updated_ts=excluded.updated_ts""",
            (p.subscriber_id, p.name, p.village, p.panchayat, p.district, p.land_ha, p.soil, p.irrigation,
             db.dumps([x.model_dump() for x in p.plots]), by or p.registered_by,
             db.iso(p.registered_ts) if p.registered_ts else db.iso(), db.iso()))
    remember(p.subscriber_id, "registered" if first else "profile_updated",
             detail={"by": by or p.registered_by, "village": p.village})
    return profile(p.subscriber_id)  # type: ignore[return-value]


def needs_confirmation(subscriber_id: str) -> bool:
    """True when the panchayat registered this farmer and they have not yet confirmed it themselves.

    A record entered at the panchayat office is somebody else's account of this farmer. Before we
    treat it as theirs, the first thing we do on WhatsApp is read it back and ask.
    """
    p = profile(subscriber_id)
    return bool(p and p.registered_ts and not p.confirmed_ts)


def mark_confirmed(subscriber_id: str, corrections: dict | None = None) -> None:
    with db.tx() as c:
        c.execute("UPDATE farmers SET confirmed_ts=?, updated_ts=? WHERE subscriber_id=?",
                  (db.iso(), db.iso(), subscriber_id))
    remember(subscriber_id, "confirmed", detail=corrections or {})


def flag_wrong(subscriber_id: str, what: str) -> None:
    """The farmer says the register is wrong about them. We do not guess a fix: we record it for the
    panchayat and the officer, because the land record is theirs to change, not ours."""
    remember(subscriber_id, "disputed", detail={"what": what})


# --------------------------------------------------------------------------- crops in the ground

def _cycle(r) -> CropCycle:
    return CropCycle(
        subscriber_id=r["subscriber_id"], crop=r["crop"], season=r["season"],
        sown_on=dt.date.fromisoformat(r["sown_on"]) if r["sown_on"] else None,
        area_ha=r["area_ha"], irrigation=r["irrigation"],
        harvested_on=dt.date.fromisoformat(r["harvested_on"]) if r["harvested_on"] else None,
        source=r["source"])


def cycles(subscriber_id: str, season: str | None = None) -> list[CropCycle]:
    sql, args = "SELECT * FROM crop_cycles WHERE subscriber_id=?", [subscriber_id]
    if season:
        sql, args = sql + " AND season=?", args + [season]
    return [_cycle(r) for r in db.query(sql + " ORDER BY crop", tuple(args))]


def save_cycle(cy: CropCycle) -> CropCycle:
    with db.tx() as c:
        c.execute(
            """INSERT INTO crop_cycles(subscriber_id, crop, season, sown_on, area_ha, irrigation,
                                       harvested_on, source, updated_ts)
               VALUES (?,?,?,?,?,?,?,?,?)
               ON CONFLICT(subscriber_id, crop, season) DO UPDATE SET sown_on=excluded.sown_on,
                 area_ha=excluded.area_ha, irrigation=excluded.irrigation,
                 harvested_on=excluded.harvested_on, source=excluded.source, updated_ts=excluded.updated_ts""",
            (cy.subscriber_id, cy.crop.lower(), cy.season, cy.sown_on.isoformat() if cy.sown_on else None,
             cy.area_ha, cy.irrigation, cy.harvested_on.isoformat() if cy.harvested_on else None,
             cy.source, db.iso()))
    remember(cy.subscriber_id, "sowing_recorded",
             detail={"crop": cy.crop, "sown_on": cy.sown_on and cy.sown_on.isoformat(), "by": cy.source})
    return cy


def standing(subscriber_id: str, season: str | None = None) -> list[CropCycle]:
    """The crops still in the ground this season."""
    return [c for c in cycles(subscriber_id, season or season_of()) if not c.harvested_on]


# --------------------------------------------------------------------------- memory

def remember(subscriber_id: str, kind: str, event: str | None = None,
             advisory_id: str | None = None, detail: dict | None = None) -> None:
    with db.tx() as c:
        c.execute("INSERT INTO farmer_events(subscriber_id, ts, kind, event, advisory_id, detail) "
                  "VALUES (?,?,?,?,?,?)",
                  (subscriber_id, db.iso(), kind, event, advisory_id, db.dumps(detail or {})))


def history(subscriber_id: str, limit: int = 50) -> list[dict]:
    rows = db.query("SELECT ts, kind, event, advisory_id, detail FROM farmer_events "
                    "WHERE subscriber_id=? ORDER BY id DESC LIMIT ?", (subscriber_id, limit))
    return [{**dict(r), "detail": json.loads(r["detail"])} for r in rows]


def last_sent(subscriber_id: str, event: str | None = None) -> dt.datetime | None:
    """When this farmer was last told about this kind of weather. Used to not repeat ourselves."""
    sql = "SELECT ts FROM farmer_events WHERE subscriber_id=? AND kind='advisory_sent'"
    args: list = [subscriber_id]
    if event:
        sql, args = sql + " AND event=?", args + [event]
    rows = db.query(sql + " ORDER BY id DESC LIMIT 1", tuple(args))
    return dt.datetime.fromisoformat(rows[0]["ts"]) if rows else None


def context(subscriber_id: str) -> dict:
    """Everything we know about one farmer in one object: the officer's screen, and /farmers/{id}."""
    from . import subscribers
    s = subscribers.get(subscriber_id)
    if s is None:
        return {}
    today = dt.date.today()
    p = profile(subscriber_id)
    last = last_sent(subscriber_id)
    return {
        "subscriber": s.model_dump(),
        "profile": p.model_dump() if p else None,
        "season": season_of(),
        "crops": [{**c.model_dump(), "stage": stage_on(c.sown_on, c.crop, today),
                   "days_since_sowing": (today - c.sown_on).days if c.sown_on else None}
                  for c in standing(subscriber_id)],
        "last_advisory": last.isoformat() if last else None,
        "history": history(subscriber_id, 20),
    }


def register(reg, by: str | None = None) -> dict:
    """Panchayat registration: one form creates the subscriber, the land record and the sowing rows.

    Re-registering the same phone updates the record in place and keeps the subscriber id, so a
    farmer who moves village or sows again does not become a second person in the database.
    """
    from . import subscribers
    from .models import FarmerProfile, SubscriberIn

    existing = subscribers.by_phone(reg.phone)
    sub = subscribers.upsert(SubscriberIn(
        subscriber_id=existing.subscriber_id if existing else None,
        phone=reg.phone, language=reg.language, block_id=reg.block_id,
        crops=[c.crop.lower() for c in reg.crops] or (existing.crops if existing else []),
        role=reg.role, consent_ts=existing.consent_ts if existing else db.now(),
        opted_out=False,
    ))
    save_profile(FarmerProfile(
        subscriber_id=sub.subscriber_id, name=reg.name, village=reg.village, panchayat=reg.panchayat,
        district=reg.district, land_ha=reg.land_ha, soil=reg.soil, irrigation=reg.irrigation,
        plots=reg.plots, registered_by=reg.registered_by or by,
    ), by=reg.registered_by or by)
    season = season_of()
    for c in reg.crops:
        save_cycle(CropCycle(subscriber_id=sub.subscriber_id, crop=c.crop, season=season, sown_on=c.sown_on,
                             area_ha=c.area_ha, irrigation=c.irrigation or reg.irrigation, source="panchayat"))
    return context(sub.subscriber_id)
