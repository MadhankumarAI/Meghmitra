"""Who an advisory is actually for, and why.

The block is where the forecast is made. It is not who the warning is for. A ten-day dry spell over
Koppal block matters to a rainfed ragi farmer whose crop is about to flower, and hardly at all to
the farmer next to him who finished harvesting last week or who irrigates from a canal. This module
turns one advisory into a list of farmers with a reason against each name, and a second list of the
people it deliberately left out, so the officer approving it can see both.

The decision uses only what the farmer or the panchayat told us (app/farmers.py):

    in the block       the forecast applies here at all
    in the village     when the advisory names villages, and we know where the farmer is
    grows the crop     the advisory's crop, or every crop when it has none
    growth stage       from the sowing date: a dry spell at flowering scores 3, at maturity 0
    irrigation         a dry spell is one step less serious on irrigated land
    not repeating      nobody hears about the same kind of weather twice inside quiet_days

A red (alert) advisory skips the last three: when it is that serious, everyone in the area hears it.
"""
from __future__ import annotations

import datetime as dt
import json
from dataclasses import dataclass, field

from . import db, farmers, subscribers
from .config import get_settings
from .models import Advisory, Subscriber

# Which weather an advisory is about, when its params do not say outright.
BY_TEMPLATE = {
    "DELAY_SOWING": "onset", "SOW_NOW": "onset", "SWITCH_CROP": "onset",
    "PREPARE_IRRIGATION": "dry_spell", "DRY_SPELL_CONSERVE_MOISTURE": "dry_spell",
    "HEAVY_RAIN_PROTECT": "heavy_rain",
}
SEVERITY = {"normal": 0, "watch": 1, "warning": 2, "alert": 3}


@dataclass
class Match:
    subscriber: Subscriber
    reasons: list[str] = field(default_factory=list)
    score: int = 1                     # 0 barely affected, 3 this is the worst time for it
    crops: list[str] = field(default_factory=list)
    stage: str | None = None

    def as_dict(self) -> dict:
        return {"subscriber_id": self.subscriber.subscriber_id, "phone": self.subscriber.phone,
                "role": self.subscriber.role, "language": self.subscriber.language,
                "score": self.score, "crops": self.crops, "stage": self.stage, "reasons": self.reasons}


@dataclass
class Skip:
    subscriber: Subscriber
    reason: str

    def as_dict(self) -> dict:
        return {"subscriber_id": self.subscriber.subscriber_id, "reason": self.reason}


def event_of(adv: Advisory) -> str:
    """dry_spell | heavy_rain | onset. From params.event where the engine sent one, else the template.

    The engine spells the event more precisely than we need here ("dry_spell_10d", "heavy_rain_64mm"),
    so match on the front of the name."""
    ev = str(adv.params.get("event") or "").strip().lower()
    for name in ("dry_spell", "heavy_rain", "onset"):
        if ev.startswith(name):
            return name
    return BY_TEMPLATE.get(adv.template_id, "dry_spell")


def villages_of(adv: Advisory) -> set[str]:
    """Villages the advisory names, lowercased. Empty means the whole block."""
    raw = (adv.model_extra or {}).get("villages") or adv.params.get("villages") or []
    return {str(v).strip().lower() for v in raw if str(v).strip()}


def _grown(sub: Subscriber, standing: list) -> set[str]:
    """Every crop we believe this farmer has: what they told the bot, plus the panchayat's sowing rows."""
    return {c.lower() for c in sub.crops} | {c.crop.lower() for c in standing}


def select(adv: Advisory, at: dt.date | None = None) -> tuple[list[Match], list[Skip]]:
    """The recipients of this advisory, and the subscribers left out with the reason why."""
    s = get_settings()
    when = at or dt.date.today()
    event = event_of(adv)
    crop = (adv.crop or "all").lower()
    named = villages_of(adv)
    severe = s.always_send_alert and adv.cmri_class == "alert"

    matched: list[Match] = []
    skipped: list[Skip] = []
    for sub in subscribers.all_(adv.block.block_id, include_opted_out=False):
        if sub.role == "officer":
            matched.append(Match(sub, ["officer for this block"], score=3))
            continue

        standing = farmers.standing(sub.subscriber_id)
        prof = farmers.profile(sub.subscriber_id)
        reasons = [f"subscribed in {adv.block.name}"]

        # --- village
        village = (prof.village or "").strip().lower() if prof else ""
        if named:
            if village and village not in named:
                skipped.append(Skip(sub, f"{prof.village} is not in the {len(named)} villages this covers"))
                continue
            reasons.append(f"in {prof.village}" if village else "village not on record, so included")

        # --- crop
        grown = _grown(sub, standing)
        if crop not in ("all", "") and crop not in grown and "all" not in grown:
            skipped.append(Skip(sub, f"does not grow {adv.crop}"))
            continue
        hit = sorted(grown & {crop}) if crop not in ("all", "") else sorted(grown - {"all"})
        if crop not in ("all", ""):
            reasons.append(f"grows {adv.crop}")

        # --- growth stage, from the sowing dates the panchayat or the farmer gave us
        score, stage = 1, None
        staged = [c for c in standing if not hit or c.crop.lower() in hit]
        if staged:
            scored = [(farmers.harm(event, farmers.stage_on(c.sown_on, c.crop, when)), c) for c in staged]
            score, worst = max(scored, key=lambda t: t[0])
            stage = farmers.stage_on(worst.sown_on, worst.crop, when)
            if stage:
                reasons.append(f"{worst.crop} is at {stage.replace('_', ' ')}")

        # --- irrigation: a dry spell is one step less serious where there is water to fall back on
        watered = (prof.irrigation if prof else None) in ("canal", "borewell", "tank")
        if event == "dry_spell" and watered and not severe:
            score = max(0, score - 1)
            reasons.append(f"{prof.irrigation} irrigated, so one step less serious")

        if score == 0 and not severe:
            skipped.append(Skip(sub, f"a {event.replace('_', ' ')} does not hurt this farm now"
                                     f"{f' ({stage})' if stage else ''}"))
            continue

        # --- do not say the same thing twice in a week
        if not severe:
            recent = _recent(sub.subscriber_id, event, s.quiet_days)
            if recent and SEVERITY.get(recent["class"], 0) >= SEVERITY.get(adv.cmri_class, 0):
                days = (db.now() - dt.datetime.fromisoformat(recent["ts"])).days
                skipped.append(Skip(sub, f"already told about {event.replace('_', ' ')} "
                                         f"{'today' if days == 0 else f'{days} days ago'}"))
                continue

        matched.append(Match(sub, reasons, score=score, crops=hit, stage=stage))

    matched.sort(key=lambda m: (-m.score, m.subscriber.subscriber_id))
    return matched, skipped


def _recent(subscriber_id: str, event: str, days: int) -> dict | None:
    """The last advisory about this weather inside the quiet window, with the class it carried."""
    if days <= 0:
        return None
    since = (db.now() - dt.timedelta(days=days)).isoformat()
    rows = db.query("SELECT ts, detail FROM farmer_events WHERE subscriber_id=? AND kind='advisory_sent' "
                    "AND event=? AND ts>=? ORDER BY id DESC LIMIT 1", (subscriber_id, event, since))
    if not rows:
        return None
    return {"ts": rows[0]["ts"], "class": json.loads(rows[0]["detail"]).get("cmri_class", "warning")}


def plan(adv: Advisory, at: dt.date | None = None) -> dict:
    """What would happen if this were approved now. The officer sees this before deciding."""
    matched, skipped = select(adv, at)
    return {
        "advisory_id": adv.advisory_id, "block_id": adv.block.block_id, "event": event_of(adv),
        "cmri_class": adv.cmri_class, "crop": adv.crop, "villages": sorted(villages_of(adv)),
        "recipients": len(matched), "not_sent": len(skipped),
        "by_score": {str(k): sum(1 for m in matched if m.score == k) for k in (3, 2, 1, 0)},
        "languages": sorted({m.subscriber.language for m in matched}),
        "matched": [m.as_dict() for m in matched],
        "left_out": [s.as_dict() for s in skipped],
    }
