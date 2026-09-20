"""Process-wide channel instances, set once at startup by app.main."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .channels.whatsapp import WhatsAppChannel


@dataclass
class Runtime:
    wa: "WhatsAppChannel | None" = None
    notes: list[str] = field(default_factory=list)


rt = Runtime()
