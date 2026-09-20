import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

_tmp = Path(tempfile.mkdtemp(prefix="delivery-test-"))
os.environ.update({
    "DB_PATH": str(_tmp / "test.sqlite3"),
    "MEDIA_DIR": str(_tmp / "media"),
    "WHATSAPP_MODE": "simulator",
    "ADMIN_API_KEY": "test-key",
    "DEV_MODE": "true",
    "ALLOW_EXPIRED_ADVISORIES": "true",
    "VOICE_WAIT_SECONDS": "0",
})
