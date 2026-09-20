"""FastAPI app: wires channels, the WhatsApp webhook, API routes and background workers.

    .venv\\Scripts\\uvicorn app.main:app --port 8000
"""
from __future__ import annotations

import contextlib
import logging
import threading

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

from . import bot, db, dispatch, geo
from .api.dev import dev
from .api.routes import api, public
from .channels.whatsapp import CloudWhatsApp, SimulatedWhatsApp
from .config import ROOT, get_settings
from .models import normalise_phone
from .runtime import rt

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("delivery")
if __import__("os").environ.get("PYWA_DEBUG"):  # log every raw webhook payload (troubleshooting)
    logging.getLogger("pywa").setLevel(logging.DEBUG)


def _setup_whatsapp(app: FastAPI) -> None:
    s = get_settings()
    if s.whatsapp_mode != "cloud":
        rt.wa = SimulatedWhatsApp(dispatch.on_status)
        rt.notes.append("WhatsApp: simulator (set WHATSAPP_MODE=cloud for the Meta Cloud API)")
        return
    missing = [k for k in ("wa_phone_id", "wa_token", "wa_verify_token") if not getattr(s, k)]
    if missing:
        raise RuntimeError(f"WHATSAPP_MODE=cloud needs {', '.join(m.upper() for m in missing)} in .env")
    from pywa import WhatsApp, types

    wa = WhatsApp(
        phone_id=s.wa_phone_id, token=s.wa_token, server=app, webhook_endpoint=s.wa_webhook_path,
        verify_token=s.wa_verify_token, app_secret=s.wa_app_secret or None,
        validate_updates=bool(s.wa_app_secret),
    )
    if not s.wa_app_secret:
        rt.notes.append("WA_APP_SECRET not set: webhook signatures are NOT verified")

    def phone_of(update) -> str:
        # Users who hide their number behind a WhatsApp username have no wa_id; we key everything by phone.
        if not update.from_user.wa_id:
            raise ValueError(f"update from username-only user {update.from_user.bsuid}; phone number required")
        return normalise_phone(update.from_user.wa_id)

    @wa.on_message()
    def on_message(_: WhatsApp, msg: types.Message) -> None:
        loc = msg.location
        if loc is not None:
            ev = bot.Inbound(phone_of(msg), "location", lat=loc.latitude, lon=loc.longitude, message_id=msg.id)
        elif msg.text:
            ev = bot.Inbound(phone_of(msg), "text", text=msg.text, message_id=msg.id)
        else:
            ev = bot.Inbound(phone_of(msg), "other", message_id=msg.id)
        bot.handle(ev)

    @wa.on_callback_button()
    def on_button(_: WhatsApp, cb: types.CallbackButton) -> None:
        bot.handle(bot.Inbound(phone_of(cb), "button", payload=cb.data, message_id=cb.id))

    @wa.on_callback_selection()
    def on_selection(_: WhatsApp, sel: types.CallbackSelection) -> None:
        bot.handle(bot.Inbound(phone_of(sel), "list", payload=sel.data, message_id=sel.id))

    @wa.on_message_status()
    def on_status(_: WhatsApp, st: types.MessageStatus) -> None:
        err = None
        if st.error is not None:
            err = f"{getattr(st.error, 'code', '')} {getattr(st.error, 'message', st.error)}".strip()
        dispatch.on_status(st.id, str(st.status.value if hasattr(st.status, "value") else st.status), err)

    rt.wa = CloudWhatsApp(wa)
    rt.notes.append(f"WhatsApp: Meta Cloud API, webhook at {s.wa_webhook_path}")


@contextlib.asynccontextmanager
async def lifespan(app: FastAPI):
    s = get_settings()
    stop = threading.Event()
    threading.Thread(target=geo.warm, daemon=True, name="geo-warm").start()
    if not s.admin_api_key:
        rt.notes.append("ADMIN_API_KEY not set: admin API is open. Set it before starting a public tunnel.")
    for n in rt.notes:
        log.info(n)
    for aid in dispatch.resume_interrupted():
        log.info("resuming interrupted dispatch of %s", aid)
    yield
    stop.set()
    dispatch.shutdown()


def create_app() -> FastAPI:
    s = get_settings()
    db.init_db()
    rt.notes.clear()
    app = FastAPI(title="Advisory delivery service", version="1.0",
                  description="Delivers approved CMRI monsoon advisories over WhatsApp in Indian languages.",
                  lifespan=lifespan)
    app.add_middleware(CORSMiddleware, allow_origins=s.cors_origin_list, allow_methods=["*"], allow_headers=["*"])
    _setup_whatsapp(app)
    app.include_router(api)
    app.include_router(public)
    app.include_router(dev)
    app.mount("/media", StaticFiles(directory=s.media_dir), name="media")
    app.mount("/assets", StaticFiles(directory=ROOT / "assets"), name="assets")

    @app.get("/", include_in_schema=False)
    def root():
        return RedirectResponse("/docs")

    @app.exception_handler(ValueError)
    async def value_error(_: Request, e: ValueError):
        return JSONResponse({"detail": str(e)}, status_code=422)

    return app


app = create_app()
