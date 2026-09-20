"""Load fixture subscribers (and optionally post fixture advisories) into the local database.

    .venv\\Scripts\\python scripts\\seed.py                 # subscribers only
    .venv\\Scripts\\python scripts\\seed.py --advisories    # also POST fixtures/advisories/*.json to a running service

Phone numbers in fixtures/subscribers.json may be ${ENV_NAME:default}; real numbers (your Meta test
recipients) belong in .env as DEMO_PHONE_1 etc., never in the committed fixture.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from dotenv import dotenv_values  # noqa: E402

from app import db, subscribers  # noqa: E402
from app.models import SubscriberIn  # noqa: E402

VAR = re.compile(r"\$\{(\w+)(?::([^}]*))?\}")


def expand(text: str) -> str:
    env = {**dotenv_values(ROOT / ".env"), **os.environ}
    return VAR.sub(lambda m: env.get(m.group(1)) or (m.group(2) or ""), text)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--advisories", action="store_true", help="POST fixture advisories to the running service")
    ap.add_argument("--url", default="http://127.0.0.1:8000")
    args = ap.parse_args()

    db.init_db()
    subs = json.loads(expand((ROOT / "fixtures" / "subscribers.json").read_text(encoding="utf-8")))
    for s in subs:
        saved = subscribers.upsert(SubscriberIn(**s))
        print(f"subscriber {saved.subscriber_id:26} {saved.phone:15} {saved.language} {saved.channel_pref:8} "
              f"{saved.role:7} {saved.block_id}")

    if args.advisories:
        import httpx
        key = dotenv_values(ROOT / ".env").get("ADMIN_API_KEY") or ""
        for f in sorted((ROOT / "fixtures" / "advisories").glob("*.json")):
            r = httpx.post(f"{args.url}/advisories", content=f.read_bytes(), timeout=60,
                           headers={"Content-Type": "application/json", "X-API-Key": key})
            print(f"{f.name}: {r.status_code} {r.text[:300]}")


if __name__ == "__main__":
    main()
