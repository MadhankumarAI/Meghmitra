"""Contract models. Field names here are the cross-team contract (brief §2); change them only with a flag."""
from __future__ import annotations

import datetime as dt
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

CmriClass = Literal["normal", "watch", "warning", "alert"]
Confidence = Literal["high", "medium", "low"]
Channel = Literal["whatsapp", "voice"]   # voice: reserved for an IVR call channel
Status = Literal["queued", "sent", "delivered", "read", "failed"]

# IMD colour-code semantics: green no action / yellow be aware / orange be prepared / red take action.
CMRI_TO_IMD = {"normal": "green", "watch": "yellow", "warning": "orange", "alert": "red"}


class Block(BaseModel):
    block_id: str
    name: str
    district: str
    state: str


class Week(BaseModel):
    week: int = Field(ge=1, le=4)
    onset: float = Field(ge=0, le=1)
    dry_spell: float = Field(ge=0, le=1)
    heavy_rain: float = Field(ge=0, le=1)
    confidence: Confidence


class Officer(BaseModel):
    name: str
    phone: str


class Advisory(BaseModel):
    """Inbound advisory, brief §2a. Unknown extra fields are kept, not rejected."""

    model_config = ConfigDict(extra="allow")

    advisory_id: str = Field(min_length=1, max_length=200)
    issued_at: dt.datetime
    valid_from: dt.date
    valid_to: dt.date
    product: str
    block: Block
    cmri_class: CmriClass
    crop: str | None = None          # None or "all" = every farmer in the block
    template_id: str
    params: dict = Field(default_factory=dict)
    weeks: list[Week] = Field(default_factory=list)
    officer: Officer | None = None
    requires_approval: bool = True

    @field_validator("weeks")
    @classmethod
    def _weeks_unique(cls, v: list[Week]) -> list[Week]:
        if len({w.week for w in v}) != len(v):
            raise ValueError("duplicate week numbers")
        return sorted(v, key=lambda w: w.week)

    @property
    def imd_colour(self) -> str:
        return CMRI_TO_IMD[self.cmri_class]


class SubscriberIn(BaseModel):
    """Brief §2d."""

    subscriber_id: str | None = None
    phone: str
    channel_pref: Literal["whatsapp"] = "whatsapp"   # WhatsApp is the only channel
    language: str = "en"
    block_id: str
    crops: list[str] = Field(default_factory=list)
    role: Literal["farmer", "officer"] = "farmer"
    consent_ts: dt.datetime | None = None
    opted_out: bool = False

    @field_validator("phone")
    @classmethod
    def _e164(cls, v: str) -> str:
        return normalise_phone(v)


class Subscriber(SubscriberIn):
    subscriber_id: str


class LogRow(BaseModel):
    """Brief §2c, plus three additive fields (block_id, provider, message_ref) flagged in the README."""

    advisory_id: str
    subscriber_id: str
    channel: Channel
    language: str
    status: Status
    ts: dt.datetime
    error: str | None = None
    block_id: str
    provider: str
    message_ref: str | None = None


def normalise_phone(v: str) -> str:
    """Store phones as E.164 digits with a leading '+'. Bare 10-digit numbers are taken as Indian."""
    digits = "".join(ch for ch in str(v) if ch.isdigit())
    if len(digits) == 10:
        digits = "91" + digits
    if len(digits) < 8 or len(digits) > 15:
        raise ValueError(f"not a phone number: {v!r}")
    return "+" + digits


# --------------------------------------------------------------------------- the farmer's own record
# Additive to the brief: the panchayat register behind a subscriber. A subscriber can exist without
# one (someone who signed up on WhatsApp alone), so nothing in the delivery path requires these.

Soil = Literal["red", "black", "alluvial", "laterite", "sandy", "clay", "loam", "unknown"]
Irrigation = Literal["rainfed", "borewell", "canal", "tank", "mixed", "unknown"]


class Plot(BaseModel):
    """One parcel as the village register records it."""

    survey_no: str | None = None
    area_ha: float | None = Field(default=None, ge=0, le=10000)
    soil: Soil | None = None
    irrigation: Irrigation | None = None
    village: str | None = None


class FarmerProfile(BaseModel):
    subscriber_id: str
    name: str | None = None
    village: str | None = None          # ADM5 name, spelled as the map spells it
    panchayat: str | None = None
    district: str | None = None
    land_ha: float | None = Field(default=None, ge=0, le=10000)
    soil: Soil | None = None
    irrigation: Irrigation | None = None
    plots: list[Plot] = Field(default_factory=list)
    registered_by: str | None = None    # the panchayat official who entered it
    registered_ts: dt.datetime | None = None
    confirmed_ts: dt.datetime | None = None   # when the farmer confirmed it themselves


class CropCycle(BaseModel):
    """One crop in the ground. The sowing date is what makes advice specific to this farm."""

    subscriber_id: str
    crop: str
    season: str
    sown_on: dt.date | None = None
    area_ha: float | None = Field(default=None, ge=0, le=10000)
    irrigation: Irrigation | None = None
    harvested_on: dt.date | None = None
    source: Literal["panchayat", "farmer", "officer"] = "panchayat"


class CropSowing(BaseModel):
    crop: str
    sown_on: dt.date | None = None
    area_ha: float | None = None
    irrigation: Irrigation | None = None


class FarmerRegistration(BaseModel):
    """What panchayat staff submit for one farmer: the person, the land, and what is sown."""

    phone: str
    language: str = "en"
    block_id: str
    name: str | None = None
    village: str | None = None
    panchayat: str | None = None
    district: str | None = None
    land_ha: float | None = None
    soil: Soil | None = None
    irrigation: Irrigation | None = None
    plots: list[Plot] = Field(default_factory=list)
    crops: list[CropSowing] = Field(default_factory=list)
    role: Literal["farmer", "officer"] = "farmer"
    registered_by: str | None = None

    @field_validator("phone")
    @classmethod
    def _e164(cls, v: str) -> str:
        return normalise_phone(v)
