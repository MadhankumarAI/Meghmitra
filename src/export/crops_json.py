"""Write the engine's indicative crop lists to EXPORTS/crops.json for the web app.

Single source of truth stays in src/advisory/engine.py.
"""
import os, sys, json
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from advisory.engine import STATE_CROPS, DEFAULT_CROPS, CROPS            # noqa: E402

out = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(os.environ.get("MORPHY_DATA", Path.home() / "morphy" / "data")) / "exports"
(out / "crops.json").write_text(json.dumps({
    "by_state": STATE_CROPS, "default": DEFAULT_CROPS,
    "tolerance": {k: v["tolerance"] for k, v in CROPS.items()},
}, indent=1))
print("crops.json ->", out)
