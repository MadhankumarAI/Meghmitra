"""Locale files: loading, lookup with English fallback, review status, and typed-keyword matching.

Adding a language is a data change: drop `content/locales/<code>.yaml` in place (produced by
scripts/translate_content.py) and restart. Nothing in the code lists languages.
"""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

import yaml

from .config import get_settings

SOURCE_LANG = "en"


class MissingString(KeyError):
    pass


def flatten(tree: dict, prefix: str = "") -> dict[str, str]:
    """{'templates': {'X': {'actions': ['a', 'b']}}} -> {'templates.X.actions.0': 'a', ...}"""
    out: dict[str, str] = {}
    for k, v in tree.items():
        key = f"{prefix}{k}"
        if isinstance(v, dict):
            out.update(flatten(v, key + "."))
        elif isinstance(v, list):
            for i, item in enumerate(v):
                out[f"{key}.{i}"] = str(item)
        else:
            out[key] = str(v)
    return out


@dataclass
class Entry:
    text: str
    status: str            # reviewed | machine | stale | fallback
    source: str | None = None


@dataclass
class Locale:
    code: str
    meta: dict
    keywords: dict[str, list[str]]
    entries: dict[str, Entry]
    path: Path
    fallback: "Locale | None" = field(default=None, repr=False)

    @property
    def name(self) -> str:
        return self.meta.get("name", self.code)

    def entry(self, key: str) -> Entry:
        e = self.entries.get(key)
        if e is not None and e.text.strip():
            return e
        if self.fallback is not None:
            fb = self.fallback.entry(key)
            return Entry(fb.text, "fallback", fb.text)
        raise MissingString(f"{self.code}: {key}")

    def t(self, key: str, **kw) -> str:
        text = self.entry(key).text
        return text.format(**kw) if kw else text

    def status(self, key: str) -> str:
        return self.entry(key).status

    def list_keys(self, prefix: str) -> list[str]:
        """Numbered keys under a prefix, as defined by the source language (so counts always match)."""
        src = self.fallback or self
        keys = [k for k in src.entries if k.startswith(prefix + ".") and k[len(prefix) + 1:].isdigit()]
        return sorted(keys, key=lambda k: int(k.rsplit(".", 1)[1]))


def _load_file(path: Path) -> Locale:
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    meta = raw.get("meta") or {}
    code = meta.get("code") or path.stem
    default_status = meta.get("default_status", "machine")
    entries: dict[str, Entry] = {}
    if "entries" in raw:  # translated layout: flat key -> {source, text, status}
        for key, val in (raw.get("entries") or {}).items():
            if isinstance(val, dict):
                entries[key] = Entry(str(val.get("text") or ""), val.get("status", default_status), val.get("source"))
            else:
                entries[key] = Entry(str(val), default_status)
    for section in ("strings", "templates", "crops"):  # authored layout (English), may also be used for overrides
        if section in raw:
            for key, text in flatten(raw[section], section + ".").items():
                entries[key] = Entry(text, default_status, text if code == SOURCE_LANG else None)
    for key, text in flatten(raw.get("glossary") or {}).items():  # hand-entered terms win over machine output
        prev = entries.get(key)
        if not (prev and prev.status == "reviewed"):
            entries[key] = Entry(text, "glossary", prev.source if prev else None)
    keywords = {k: [str(w) for w in v] for k, v in (raw.get("keywords") or {}).items()}
    return Locale(code=code, meta=meta, keywords=keywords, entries=entries, path=path)


@lru_cache
def load_locales() -> dict[str, Locale]:
    folder = get_settings().content_dir / "locales"
    locales = {loc.code: loc for loc in (_load_file(p) for p in sorted(folder.glob("*.yaml")))}
    if SOURCE_LANG not in locales:
        raise RuntimeError(f"source locale {SOURCE_LANG}.yaml missing in {folder}")
    for code, loc in locales.items():
        if code != SOURCE_LANG:
            loc.fallback = locales[SOURCE_LANG]
    return dict(sorted(locales.items(), key=lambda kv: kv[1].meta.get("order", 99)))


def get_locale(code: str | None) -> Locale:
    locs = load_locales()
    return locs.get(code or SOURCE_LANG) or locs[SOURCE_LANG]


@lru_cache
def template_spec() -> dict:
    return yaml.safe_load((get_settings().content_dir / "templates.yaml").read_text(encoding="utf-8"))


def template_ids() -> list[str]:
    return [k for k, v in template_spec().items() if isinstance(v, dict) and "icon" in v]


# ---------------------------------------------------------------- keywords

_PUNCT = re.compile(r"[\s\W_]+", re.UNICODE)


def normalise_word(text: str) -> str:
    text = unicodedata.normalize("NFC", text).casefold().strip()
    return _PUNCT.sub("", text)


@lru_cache
def _keyword_index() -> dict[str, str]:
    index: dict[str, str] = {}
    for loc in load_locales().values():
        for intent, words in loc.keywords.items():
            for w in words:
                index.setdefault(normalise_word(w), intent)
    return index


def match_keyword(text: str) -> str | None:
    """Return 'menu' | 'stop' | 'start' | 'language' when the whole message is one of the known words."""
    return _keyword_index().get(normalise_word(text or ""))


def reload() -> None:
    load_locales.cache_clear()
    template_spec.cache_clear()
    _keyword_index.cache_clear()
