"""Every fixture renders in every language within channel limits."""
import json
import re
from pathlib import Path

import pytest

from app.channels.whatsapp import BUTTON_TITLE, ROW_TITLE, fit
from app.locales import load_locales, match_keyword, template_ids
from app.models import Advisory
from app.render.text import chance, render

FIX = Path(__file__).resolve().parent.parent / "fixtures" / "advisories"
ADVS = [Advisory.model_validate(json.loads(p.read_text(encoding="utf-8"))) for p in sorted(FIX.glob("*.json"))]
LANGS = list(load_locales())


@pytest.mark.parametrize("lang", LANGS)
@pytest.mark.parametrize("adv", ADVS, ids=lambda a: a.template_id)
def test_fixture_renders(adv, lang):
    r = render(adv, lang)
    for text in (r.whatsapp_text, r.speech_text, r.verdict, *r.actions):
        assert not re.search(r"\{\w+\}", text), f"unfilled placeholder in {text!r}"
    assert len(r.tiles) == 4 and 2 <= len(r.actions) <= 3


@pytest.mark.parametrize("lang", LANGS)
def test_every_template_renders(lang):
    base = ADVS[0].model_dump()
    params = {"wait_until": "2026-07-05", "sow_by": "2026-07-10", "alternative": "horsegram",
              "p_event": 0.6, "p_clim": 0.3, "event": "dry_spell_7d", "lead_week": 1}
    for tid in template_ids():
        r = render(Advisory.model_validate({**base, "template_id": tid, "params": params}), lang)
        assert r.verdict and r.headline and r.actions


def test_natural_frequencies():
    en = load_locales()["en"]
    assert chance(0.68, en) == "7 in 10"
    assert chance(0.31, en) == "3 in 10"
    assert chance(0.04, en) == "less than 1 in 10"
    assert chance(0.99, en) == "9 in 10"      # never "10 in 10"



@pytest.mark.parametrize("lang", LANGS)
def test_button_labels_fit(lang):
    loc = load_locales()[lang]
    for k in ("btn_outlook", "btn_change_crop", "btn_officer", "btn_menu", "btn_yes", "btn_no"):
        assert 0 < len(fit(loc.t(f"strings.{k}"), BUTTON_TITLE)) <= BUTTON_TITLE
    for c in ("ragi", "tur", "greengram"):
        assert len(fit(loc.t(f"crops.{c}"), ROW_TITLE)) <= ROW_TITLE


def test_keywords_any_language():
    assert match_keyword("Hi") == "menu"
    assert match_keyword("  STOP! ") == "stop"
    assert match_keyword("ನಮಸ್ಕಾರ") == "menu"
    assert match_keyword("नमस्ते") == "menu"
    assert match_keyword("रुको") == "stop"
    assert match_keyword("what is the weather") is None


def test_voice_cache_survives_db_reset(tmp_path, monkeypatch):
    from app import db
    from app.render import voice
    key, _ = voice.voice_key("kn", "ಪರೀಕ್ಷೆ")
    f = voice.voice_file(key)
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_bytes(b"OggS")
    db.init_db()
    with db.tx() as c:
        c.execute("DELETE FROM tts_jobs WHERE key=?", (key,))
    assert voice.request("kn", "ಪರೀಕ್ಷೆ") == key
    assert voice.ready(key) == f        # no re-render queued for a file that already exists
    f.unlink()
