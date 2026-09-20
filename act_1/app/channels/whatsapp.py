"""WhatsApp channel. One interface, two implementations:

- CloudWhatsApp: the official Meta WhatsApp Cloud API through pywa (MIT). The production path.
- SimulatedWhatsApp: records messages in SQLite for the /dev/phone simulator and emits the same
  sent/delivered/read status events, so everything downstream is exercised without Meta credentials.

Every method returns the provider message id, which status updates are later matched on.
WhatsApp limits enforced here: 3 reply buttons, 10 list rows, titles 20/24 characters.
"""
from __future__ import annotations

import logging
import threading
import time
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from .. import db

log = logging.getLogger(__name__)

StatusCallback = Callable[[str, str, str | None], None]   # (provider_id, status, error)
MAX_BUTTONS, MAX_ROWS = 3, 10
BUTTON_TITLE, ROW_TITLE, ROW_DESC, LIST_BUTTON, HEADER, FOOTER = 20, 24, 72, 20, 60, 60


class ChannelError(RuntimeError):
    pass


@dataclass
class Row:
    id: str
    title: str
    description: str | None = None


# Small icons in front of button titles make each option recognisable before it is read (Namma Metro style).
BUTTON_ICONS = {"outlook": "🌦", "change_crop": "🌾", "officer": "📞", "menu": "🏠", "blk:yes": "✅",
                "blk:no": "✏️", "crop:more": "➕", "crop:done": "✅", "kw:start": "▶️"}


def titled(button_id: str, title: str) -> str:
    """Button title with its icon, if the icon still fits WhatsApp's 20 characters."""
    icon = BUTTON_ICONS.get(button_id)
    with_icon = f"{icon} {title}" if icon else title
    return with_icon if len(with_icon) <= BUTTON_TITLE else fit(title, BUTTON_TITLE)


def fit(text: str, limit: int) -> str:
    """Shorten to WhatsApp's character limit without splitting an Indic syllable (drops trailing marks)."""
    text = (text or "").strip()
    if len(text) <= limit:
        return text
    cut = text[:limit]
    if " " in cut[limit // 2:]:
        cut = cut[:cut.rfind(" ")]
    import unicodedata
    while cut and unicodedata.category(cut[-1]) in ("Mn", "Mc"):
        cut = cut[:-1]
    return cut.rstrip(" ,.:;-")


class WhatsAppChannel:
    provider = "base"

    def text(self, to: str, body: str, *, tracker: str | None = None) -> str: ...
    def buttons(self, to: str, body: str, buttons: list[tuple[str, str]], *, header: str | None = None,
                footer: str | None = None, tracker: str | None = None, image: Path | None = None) -> str: ...
    def list(self, to: str, body: str, button: str, rows: list[Row], *, section: str = "",
             header: str | None = None, footer: str | None = None) -> str: ...
    def location_request(self, to: str, body: str) -> str: ...
    def image(self, to: str, path: Path, *, caption: str | None = None, tracker: str | None = None) -> str: ...
    def voice(self, to: str, path: Path, *, tracker: str | None = None) -> str: ...
    def contact(self, to: str, name: str, phone: str) -> str: ...
    def mark_read(self, message_id: str) -> None: ...

    @staticmethod
    def _check(buttons: list | None = None, rows: list | None = None) -> None:
        if buttons is not None and not 1 <= len(buttons) <= MAX_BUTTONS:
            raise ChannelError(f"{len(buttons)} buttons; WhatsApp allows 1-{MAX_BUTTONS}")
        if rows is not None and not 1 <= len(rows) <= MAX_ROWS:
            raise ChannelError(f"{len(rows)} list rows; WhatsApp allows 1-{MAX_ROWS}")


# --------------------------------------------------------------------------- Meta Cloud API

class CloudWhatsApp(WhatsAppChannel):
    provider = "meta-cloud"

    def __init__(self, wa) -> None:   # wa: pywa.WhatsApp, created in app.main with the FastAPI server
        self.wa = wa
        self._media: dict[str, str] = {}   # file -> WhatsApp media id; banners are uploaded once and reused

    def _media_id(self, path: Path, mime: str) -> str:
        key = f"{Path(path).resolve()}:{Path(path).stat().st_mtime_ns}"
        if key not in self._media:
            from pywa.errors import WhatsAppError
            try:
                self._media[key] = self.wa.upload_media(media=Path(path), mime_type=mime).id
            except WhatsAppError as e:
                raise ChannelError(f"media upload failed: {getattr(e, 'message', e)}") from e
        return self._media[key]

    @staticmethod
    def _to(phone: str) -> str:
        return phone.lstrip("+")

    def _call(self, fn, *a, **kw) -> str:
        from pywa.errors import WhatsAppError
        try:
            return fn(*a, **kw).id
        except WhatsAppError as e:
            raise ChannelError(f"{e.__class__.__name__} {getattr(e, 'code', '')}: {getattr(e, 'message', e)}") from e

    def text(self, to, body, *, tracker=None):
        return self._call(self.wa.send_message, self._to(to), body, tracker=tracker)

    def buttons(self, to, body, buttons, *, header=None, footer=None, tracker=None, image=None):
        from pywa.types import Button
        self._check(buttons=buttons)
        btns = [Button(title=titled(i, t), callback_data=i) for i, t in buttons]
        if image:   # picture header above the text and buttons
            return self._call(self.wa.send_image, self._to(to), image=self._media_id(image, "image/png"),
                              caption=body, footer=fit(footer, FOOTER) if footer else None, buttons=btns,
                              tracker=tracker)
        return self._call(
            self.wa.send_message, self._to(to), body,
            header=fit(header, HEADER) if header else None, footer=fit(footer, FOOTER) if footer else None,
            buttons=btns, tracker=tracker,
        )

    def list(self, to, body, button, rows, *, section="", header=None, footer=None):
        from pywa.types import Section, SectionList, SectionRow
        self._check(rows=rows)
        sl = SectionList(button_title=fit(button, LIST_BUTTON), sections=[Section(
            title=fit(section or button, ROW_TITLE),
            rows=[SectionRow(title=fit(r.title, ROW_TITLE), callback_data=r.id,
                             description=fit(r.description, ROW_DESC) if r.description else None) for r in rows],
        )])
        return self._call(self.wa.send_message, self._to(to), body, header=header and fit(header, HEADER),
                          footer=footer and fit(footer, FOOTER), buttons=sl)

    def location_request(self, to, body):
        return self._call(self.wa.request_location, self._to(to), body)

    def image(self, to, path, *, caption=None, tracker=None):
        return self._call(self.wa.send_image, self._to(to), image=Path(path), caption=caption,
                          mime_type="image/png", tracker=tracker)

    def voice(self, to, path, *, tracker=None):
        return self._call(self.wa.send_voice, self._to(to), voice=Path(path), mime_type="audio/ogg", tracker=tracker)

    def contact(self, to, name, phone):
        from pywa.types import Contact
        c = Contact(name=Contact.Name(formatted_name=name, first_name=name),
                    phones=[Contact.Phone(phone=phone, type="WORK")])
        return self._call(self.wa.send_contact, self._to(to), contact=c)

    def mark_read(self, message_id):
        try:
            self.wa.mark_message_as_read(message_id)
        except Exception as e:  # cosmetic only; never fail a conversation over a read receipt
            log.debug("mark_read failed: %s", e)


# --------------------------------------------------------------------------- simulator

class SimulatedWhatsApp(WhatsAppChannel):
    """Stores outbound messages for the /dev/phone page and replays WhatsApp's status lifecycle."""

    provider = "simulator"

    def __init__(self, on_status: StatusCallback, delivery_delay: float = 0.8) -> None:
        self.on_status = on_status
        self.delay = delivery_delay

    def _store(self, to: str, kind: str, payload: dict) -> str:
        pid = f"sim.wa.{uuid.uuid4().hex[:16]}"
        with db.tx() as c:
            c.execute("INSERT INTO sim_outbox(channel, direction, phone, kind, payload, provider_id, ts) "
                      "VALUES ('whatsapp','out',?,?,?,?,?)", (to, kind, db.dumps(payload), pid, db.iso()))
        self._lifecycle(pid)
        return pid

    def _lifecycle(self, pid: str) -> None:
        def run():
            self.on_status(pid, "sent", None)
            time.sleep(self.delay)
            self.on_status(pid, "delivered", None)
        threading.Thread(target=run, daemon=True).start()

    def text(self, to, body, *, tracker=None):
        return self._store(to, "text", {"body": body})

    def buttons(self, to, body, buttons, *, header=None, footer=None, tracker=None, image=None):
        self._check(buttons=buttons)
        return self._store(to, "buttons", {"body": body, "header": header, "footer": footer and fit(footer, FOOTER),
                                           "image": str(image) if image else None,
                                           "buttons": [{"id": i, "title": titled(i, t)} for i, t in buttons]})

    def list(self, to, body, button, rows, *, section="", header=None, footer=None):
        self._check(rows=rows)
        return self._store(to, "list", {"body": body, "header": header, "footer": footer,
                                        "button": fit(button, LIST_BUTTON),
                                        "rows": [{"id": r.id, "title": fit(r.title, ROW_TITLE),
                                                  "description": r.description} for r in rows]})

    def location_request(self, to, body):
        return self._store(to, "location_request", {"body": body})

    def image(self, to, path, *, caption=None, tracker=None):
        return self._store(to, "image", {"path": str(path), "caption": caption})

    def voice(self, to, path, *, tracker=None):
        return self._store(to, "voice", {"path": str(path)})

    def contact(self, to, name, phone):
        return self._store(to, "contact", {"name": name, "phone": phone})

    def mark_read(self, message_id):
        pass
