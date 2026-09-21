"""Runtime settings. Everything secret or machine-specific comes from `.env`."""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=ROOT / ".env", env_file_encoding="utf-8", extra="ignore")

    # --- service ---
    public_base_url: str = ""          # e.g. https://xyz.trycloudflare.com (only needed for media-by-link)
    admin_api_key: str = ""            # required on every non-webhook route when set
    dev_mode: bool = True              # enables /dev (simulator); refuses requests arriving through the tunnel
    cors_origins: str = "*"
    allow_expired_advisories: bool = False
    timezone: str = "Asia/Kolkata"

    # --- paths ---
    db_path: Path = ROOT / "var" / "delivery.sqlite3"
    media_dir: Path = ROOT / "var" / "media"
    content_dir: Path = ROOT / "content"
    forecast_path: Path = ROOT / "forecast" / "latest.json"
    geo_dir: Path = ROOT / "data"
    blocks_parquet: Path = Path(r"D:\Morphy\processed\blocks.parquet")
    boundaries_geojson: Path = Path(r"D:\Morphy\raw\boundaries\IND_ADM3.geojson")

    # --- WhatsApp (Meta Cloud API) ---
    whatsapp_mode: str = "simulator"   # "cloud" | "simulator"
    wa_phone_id: str = ""
    wa_token: str = Field("", validation_alias=AliasChoices("wa_token", "meta_access_token"))  # either name works
    wa_verify_token: str = ""
    wa_app_id: str = ""
    wa_app_secret: str = ""
    wa_webhook_path: str = "/whatsapp/webhook"
    wa_session_hours: int = 24         # customer-service window for free-form messages


    # --- who gets an advisory ---
    quiet_days: int = 5                # do not repeat the same kind of warning inside this many days
    always_send_alert: bool = True     # a red (alert) advisory ignores quiet_days and crop stage

    # --- voice notes ---
    voice_wait_seconds: int = 900      # how long dispatch waits for a pending voice note
    kisan_call_centre: str = "18001801551"

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    s = Settings()
    s.media_dir.mkdir(parents=True, exist_ok=True)
    s.db_path.parent.mkdir(parents=True, exist_ok=True)
    return s
