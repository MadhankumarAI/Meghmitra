"""WhatsApp conversation: taps, not typing (Namma Metro style). Each message does one thing.

Onboarding: language list -> share location (or type PIN) -> confirm block -> crops (multi-select) -> subscribed.
Main menu, always one tap away: 4-week outlook · Change crop · Talk to officer.
Typed "menu"/"hi"/"help" in any supported language -> main menu. "STOP" -> opt out, confirmed. "START" -> back in.
"""
from __future__ import annotations

import json
import logging
import re
import threading
from collections import defaultdict
from dataclasses import dataclass

from . import db, dispatch, forecast, geo, subscribers
from .config import get_settings
from .locales import Locale, get_locale, load_locales, match_keyword, template_spec
from .models import SubscriberIn
from .render import banner
from .render.text import crop_name
from .channels.whatsapp import Row
from .runtime import rt

log = logging.getLogger(__name__)
def _picture(make, *args):
    """A banner for the message, or None if it could not be drawn (the message then goes without a picture)."""
    try:
        return make(*args)
    except Exception:
        log.exception("banner %s failed", getattr(make, "__name__", make))
        return None


PIN = re.compile(r"^\s*(\d{3})\s?(\d{3})\s*$")
_locks: dict[str, threading.Lock] = defaultdict(threading.Lock)


@dataclass
class Inbound:
    phone: str                       # E.164 with '+'
    kind: str                        # text | button | list | location | other
    text: str | None = None
    payload: str | None = None       # callback id of a tapped button or list row
    lat: float | None = None
    lon: float | None = None
    message_id: str | None = None


def _is_done(text: str) -> bool:
    from .locales import normalise_word
    words = {normalise_word(loc.t("strings.crop_done")) for loc in load_locales().values()}
    return normalise_word(text) in words | {"done", "ok", "okay", "finish"}


def _resolve_crop(text: str) -> str:
    """Typed crop name -> crop id if any locale knows it (e.g. 'ಹುರುಳಿ' or 'horse gram' -> horsegram), else the text."""
    from .locales import normalise_word
    word = normalise_word(text)
    forms = {word, word[:-3] + "i" if word.endswith("ies") else word, word[:-1] if word.endswith("s") else word,
             word[:-2] if word.endswith("es") else word}
    for loc in load_locales().values():
        for key, e in loc.entries.items():
            if key.startswith("crops.") and key != "crops.all":
                cid = key[6:]
                names = {normalise_word(e.text), normalise_word(cid), normalise_word(e.text.split("(")[0])}
                if forms & names:
                    return cid
    return text.strip()[:40]


# --------------------------------------------------------------------------- session store

def _load(phone: str) -> tuple[str, dict]:
    rows = db.query("SELECT state, data FROM sessions WHERE phone=?", (phone,))
    return (rows[0]["state"], json.loads(rows[0]["data"])) if rows else ("NEW", {})


def _save(phone: str, state: str, data: dict, inbound: bool = False) -> None:
    with db.tx() as c:
        c.execute("""INSERT INTO sessions(phone, state, data, last_inbound_ts, updated_ts) VALUES (?,?,?,?,?)
                     ON CONFLICT(phone) DO UPDATE SET state=excluded.state, data=excluded.data,
                       last_inbound_ts=COALESCE(excluded.last_inbound_ts, sessions.last_inbound_ts),
                       updated_ts=excluded.updated_ts""",
                  (phone, state, db.dumps(data), db.iso() if inbound else None, db.iso()))


# --------------------------------------------------------------------------- entry point

def handle(ev: Inbound) -> None:
    with _locks[ev.phone]:
        state, data = _load(ev.phone)
        _save(ev.phone, state, data, inbound=True)   # opens the 24-hour customer-service window
        if ev.message_id:   # blue ticks in the background: the reply should not wait for them
            threading.Thread(target=rt.wa.mark_read, args=(ev.message_id,), daemon=True).start()
        try:
            Conversation(ev, state, data).run()
        except Exception:
            log.exception("bot failed for %s in %s", ev.phone, state)


class Conversation:
    def __init__(self, ev: Inbound, state: str, data: dict) -> None:
        self.ev, self.state, self.data = ev, state, data
        self.phone = ev.phone
        self.sub = subscribers.by_phone(ev.phone)
        self.loc: Locale = get_locale(data.get("lang") or (self.sub.language if self.sub else None))

    # ---- helpers
    def goto(self, state: str) -> None:
        self.state = state
        _save(self.phone, state, self.data)

    def t(self, key: str, **kw) -> str:
        return self.loc.t(f"strings.{key}", **kw)

    def say(self, text: str) -> None:
        rt.wa.text(self.phone, text)

    def crops_text(self, crops: list[str]) -> str:
        return ", ".join(crop_name(c, self.loc) for c in crops)

    # ---- dispatcher
    def run(self) -> None:
        ev, p = self.ev, self.ev.payload or ""
        if ev.kind == "text" and ev.text:
            kw = match_keyword(ev.text)
            if kw == "stop":
                return self.stop()
            if kw == "start":
                return self.start()
            if self.sub and self.sub.opted_out:
                return rt.wa.buttons(self.phone, self.t("opted_out_hint"), [("kw:start", "START")])
            if kw == "language":
                self.data["mode"] = "change_lang" if self.sub else "onboarding"
                return self.ask_language()
            if kw == "menu":
                return self.menu() if self.sub else self.ask_language()
        if p == "kw:start":
            return self.start()
        if self.sub and self.sub.opted_out:
            return rt.wa.buttons(self.phone, self.t("opted_out_hint"), [("kw:start", "START")])

        # Buttons that work from anywhere once subscribed (they also sit under every advisory).
        if self.sub and p in ("outlook", "officer", "menu", "change_crop"):
            return {"outlook": self.outlook, "officer": self.officer, "menu": self.menu,
                    "change_crop": self.change_crop}[p]()

        handler = {
            "LANG": self.on_language, "LOCATION": self.on_location, "CONFIRM": self.on_confirm,
            "PICK": self.on_pick, "CROPS": self.on_crops, "CROP_TYPE": self.on_crop_type,
        }.get(self.state)
        if handler:
            return handler()
        if self.sub:
            if ev.kind == "text":
                self.say(self.t("tap_hint"))
            return self.menu()
        self.data = {"mode": "onboarding"}
        return self.ask_language()

    # ---- onboarding: language
    def ask_language(self) -> None:
        locs = list(load_locales().values())
        body = " · ".join(dict.fromkeys(l.t("strings.lang_word") for l in locs))
        rows = [Row(f"lang:{l.code}", l.name, l.meta.get("english_name")) for l in locs][:10]
        if self.data.get("mode") == "onboarding":   # first contact: the Mungaru welcome picture
            pic = _picture(banner.welcome)
            if pic:
                rt.wa.image(self.phone, pic)
        rt.wa.list(self.phone, body, get_locale("en").t("strings.lang_list_button"), rows, section="Language")
        self.goto("LANG")

    def on_language(self) -> None:
        p = self.ev.payload or ""
        if not p.startswith("lang:") or p[5:] not in load_locales():
            return self.ask_language()
        self.data["lang"] = p[5:]
        self.loc = get_locale(p[5:])
        if self.data.get("mode") == "change_lang" and self.sub:
            self.sub = subscribers.upsert(SubscriberIn(**{**self.sub.model_dump(), "language": self.loc.code}))
            self.say(self.t("language_changed"))
            return self.menu()
        self.ask_location(lead=self.t("welcome"))

    # ---- onboarding: location / PIN
    def ask_location(self, lead: str | None = None) -> None:
        body = "📍 " + self.t("location_prompt")
        rt.wa.location_request(self.phone, f"{lead}\n\n{body}" if lead else body)
        self.goto("LOCATION")

    def on_location(self) -> None:
        ev = self.ev
        if ev.kind == "location" and ev.lat is not None:
            bid = geo.block_at(ev.lat, ev.lon)
            if not bid:
                self.say(self.t("block_not_found"))
                return self.ask_location()
            self.data.update(candidate=bid, lat=ev.lat, lon=ev.lon, pin_blocks=[])
            return self.confirm_block()
        m = PIN.match(ev.text or "") if ev.kind == "text" else None
        if m:
            pin = m.group(1) + m.group(2)
            rec = geo.pin_lookup(pin)
            if not rec or not rec["blocks"]:
                self.say(self.t("pin_not_found", pin=pin))
                return self.ask_location()
            self.data.update(candidate=rec["blocks"][0][0], lat=rec["lat"], lon=rec["lon"],
                             pin_blocks=[b for b, _ in rec["blocks"][1:]])
            return self.confirm_block()
        self.ask_location()

    def confirm_block(self) -> None:
        b = geo.block(self.data["candidate"])
        rt.wa.buttons(self.phone, self.t("block_found", block=b["name"], district=b["district"]),
                      [("blk:yes", self.t("btn_yes")), ("blk:no", self.t("btn_no"))],
                      image=_picture(banner.block_map, self.data["candidate"], self.loc))
        self.goto("CONFIRM")

    def on_confirm(self) -> None:
        p = self.ev.payload
        if p == "blk:yes":
            return self.set_block(self.data["candidate"])
        if p == "blk:no":
            return self.pick_block()
        self.confirm_block()

    def pick_block(self) -> None:
        seen = {self.data["candidate"]}
        options = [b for b in self.data.get("pin_blocks", []) if b not in seen]
        options += [b for b in geo.nearest_blocks(self.data["lat"], self.data["lon"], k=12, exclude=seen)
                    if b not in options]
        rows = [Row(f"blk:{bid}", geo.block(bid)["name"], geo.block(bid)["district"]) for bid in options[:9]]
        rows.append(Row("blk:again", self.t("share_again")))
        rt.wa.list(self.phone, self.t("pick_block"), self.t("pick_block_button"), rows)
        self.goto("PICK")

    def on_pick(self) -> None:
        p = self.ev.payload or ""
        if p == "blk:again":
            return self.ask_location()
        if p.startswith("blk:") and geo.block(p[4:]):
            return self.set_block(p[4:])
        self.pick_block()

    def set_block(self, block_id: str) -> None:
        self.data["block_id"] = block_id
        self.data["crops"] = []
        self.data["mode"] = "onboarding"
        self.ask_crops()

    # ---- crops (multi-select across messages)
    def ask_crops(self, body: str | None = None) -> None:
        chosen = self.data.get("crops", [])
        ids = template_spec()["onboarding_crops"][:9]
        rows = [Row(f"crop:{c}", crop_name(c, self.loc), "✓" if c in chosen else None) for c in ids]
        # 10 rows max: 9 crops + "Other crop". "Done" is a button sent after every pick.
        rows.append(Row("crop:other", "✏️ " + self.t("other_crop")))
        rt.wa.list(self.phone, body or self.t("crop_prompt"), self.t("crop_list_button"), rows)
        self.goto("CROPS")

    def on_crops(self) -> None:
        p = self.ev.payload or ""
        if self.ev.kind == "text" and _is_done(self.ev.text or ""):
            p = "crop:done"  # a typed "Done" (any language) counts like the Done row
        chosen: list[str] = self.data.setdefault("crops", [])
        if p == "crop:done":
            if not chosen:
                return self.ask_crops(self.t("crop_need_one"))
            return self.finish_crops()
        if p == "crop:more":
            return self.ask_crops()
        if p == "crop:other":
            self.say(self.t("crop_type_prompt"))
            return self.goto("CROP_TYPE")
        if p.startswith("crop:"):
            c = p[5:]
            if c in chosen:
                chosen.remove(c)
            else:
                chosen.append(c)
            if not chosen:
                return self.ask_crops()
            # Two plain buttons instead of re-sending the long list: "Done" is never hidden at the bottom.
            rt.wa.buttons(self.phone, self.t("crop_added", crops=self.crops_text(chosen)),
                          [("crop:more", self.t("btn_add_crop")), ("crop:done", self.t("crop_done"))])
            return self.goto("CROPS")
        self.ask_crops()

    def on_crop_type(self) -> None:
        """A crop typed by the farmer. Known names in any language map to our crop id; others are kept as typed."""
        text = (self.ev.text or "").strip() if self.ev.kind == "text" else ""
        if not text:
            self.say(self.t("crop_type_prompt"))
            return
        if _is_done(text):
            self.ev.payload = "crop:done"
            return self.on_crops()
        chosen: list[str] = self.data.setdefault("crops", [])
        crop = _resolve_crop(text)
        if crop not in chosen:
            chosen.append(crop)
        rt.wa.buttons(self.phone, self.t("crop_added", crops=self.crops_text(chosen)),
                      [("crop:more", self.t("btn_add_crop")), ("crop:done", self.t("crop_done"))])
        self.goto("CROPS")

    def finish_crops(self) -> None:
        crops = self.data["crops"]
        if self.data.get("mode") == "change_crop" and self.sub:
            self.sub = subscribers.upsert(SubscriberIn(**{**self.sub.model_dump(), "crops": crops}))
            lead = self.t("crops_updated", crops=self.crops_text(crops))
            pic = _picture(banner.subscribed, self.sub.block_id, crops, self.loc)
        else:
            existing = self.sub
            self.sub = subscribers.upsert(SubscriberIn(
                subscriber_id=existing.subscriber_id if existing else None, phone=self.phone,
                channel_pref=existing.channel_pref if existing else "whatsapp", language=self.loc.code,
                block_id=self.data["block_id"], crops=crops, role=existing.role if existing else "farmer",
                consent_ts=db.now(), opted_out=False,
            ))
            b = geo.block(self.data["block_id"])
            lead = self.t("subscribed", crops=self.crops_text(crops), block=b["name"])
            pic = _picture(banner.subscribed, self.data["block_id"], crops, self.loc)
        self.data = {"lang": self.loc.code}
        self.menu(lead, image=pic)

    def change_crop(self) -> None:
        self.data.update(mode="change_crop", crops=list(self.sub.crops))
        self.ask_crops()

    # ---- main menu and its actions
    def menu(self, lead: str | None = None, image=None) -> None:
        """Main menu. `lead` puts a short answer above the buttons, so the farmer gets one message, not two."""
        body = self.t("menu_prompt")
        if lead and len(lead) + len(body) < 1000:   # WhatsApp interactive body limit is 1024
            body = f"{lead}\n\n{body}"
        elif lead:
            self.say(lead)
        rt.wa.buttons(self.phone, body,
                      [("outlook", self.t("btn_outlook")), ("change_crop", self.t("btn_change_crop")),
                       ("officer", self.t("btn_officer"))],
                      footer=self.t("menu_footer"), image=image)
        self.data = {"lang": self.loc.code}
        self.goto("READY")

    def outlook(self) -> None:
        b = geo.block(self.sub.block_id) or {"name": self.sub.block_id}
        self.menu(forecast.outlook_text(self.sub.block_id, b["name"], self.loc),
                  image=_picture(banner.outlook, self.sub.block_id, self.loc))

    def officer(self) -> None:
        off = dispatch.officer_for_block(self.sub.block_id)
        if off:
            self.say(self.t("officer_intro"))
            rt.wa.contact(self.phone, off["name"], off["phone"])
        else:
            self.say(self.t("no_officer"))
        kcc = get_settings().kisan_call_centre
        self.say(self.t("officer_kcc", kcc=f"{kcc[:4]}-{kcc[4:7]}-{kcc[7:]}" if len(kcc) == 11 else kcc))
        officers = [s for s in subscribers.targets(self.sub.block_id, "all")
                    if s.role == "officer" and s.phone != self.phone]
        b = geo.block(self.sub.block_id) or {"name": self.sub.block_id}
        for o in officers:
            ol = get_locale(o.language)
            try:
                rt.wa.text(o.phone, ol.t("strings.officer_alert", block=b["name"], phone=self.phone,
                                         crops=", ".join(crop_name(c, ol) for c in self.sub.crops)))
            except Exception as e:
                log.warning("could not alert officer %s: %s", o.subscriber_id, e)
        if officers:
            self.say(self.t("officer_notified"))
        self.menu()

    # ---- STOP / START
    def stop(self) -> None:
        if self.sub:
            subscribers.set_opted_out(self.phone, True)
        self.say(self.t("stop_confirm"))
        self.data = {"lang": self.loc.code}
        self.goto("STOPPED")

    def start(self) -> None:
        if self.sub:
            self.sub = subscribers.set_opted_out(self.phone, False)
            self.say(self.t("start_confirm"))
            return self.menu()
        self.data = {"mode": "onboarding"}
        self.ask_language()
