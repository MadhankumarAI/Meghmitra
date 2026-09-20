"""Native-speaker review of translations, through a spreadsheet instead of YAML.

    .venv\\Scripts\\python scripts\\review_sheet.py export kn        # -> review/kn_review.csv (opens in Excel/Sheets)
    .venv\\Scripts\\python scripts\\review_sheet.py import kn        # <- review/kn_review.csv

The reviewer fills two columns per row:
  approved      Y if the current translation is right as it stands
  corrected     a better translation (implies approved); keep every {placeholder} exactly as in English
Imported rows become `status: reviewed`, which translate_content.py never overwrites. Rows whose placeholders
don't match the English, or that break a WhatsApp length limit, are refused and listed.
"""
from __future__ import annotations

import argparse
import csv
import re
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from scripts.translate_content import LIMITS, flatten  # noqa: E402

LOCALES = ROOT / "content" / "locales"
OUT = ROOT / "review"
PH = re.compile(r"\{(\w+)\}")
COLUMNS = ["key", "where_it_appears", "max_chars", "english", "current_translation", "status", "approved",
           "corrected", "reviewer_notes"]


def where(key: str) -> str:
    if key.startswith("crops."):
        return "crop name (lists, card, messages)"
    if ".actions." in key:
        return "numbered action on card and in message"
    if key.endswith((".verdict", ".verdict_sub")):
        return "big headline on the advisory card"
    if key.endswith(".headline"):
        return "first bold line of the advisory message"
    if key.startswith("strings.btn_") or key in ("strings.crop_done", "strings.share_again"):
        return "WhatsApp button / list row"
    if key.startswith(("strings.cmri_", "strings.imd_")):
        return "alert band on card"
    return "WhatsApp message text"


def limit(key: str) -> int | None:
    return LIMITS.get(key)


def english() -> dict[str, str]:
    en = yaml.safe_load((LOCALES / "en.yaml").read_text(encoding="utf-8"))
    src: dict[str, str] = {}
    for section in ("strings", "templates", "crops"):
        src.update(flatten(en[section], section + "."))
    return src


def export(code: str) -> Path:
    doc = yaml.safe_load((LOCALES / f"{code}.yaml").read_text(encoding="utf-8"))
    entries, gloss = doc.get("entries") or {}, flatten(doc.get("glossary") or {})
    OUT.mkdir(exist_ok=True)
    path = OUT / f"{code}_review.csv"
    with open(path, "w", newline="", encoding="utf-8-sig") as f:   # BOM: Excel then shows Indic scripts correctly
        w = csv.DictWriter(f, fieldnames=COLUMNS)
        w.writeheader()
        for key, src in english().items():
            e = entries.get(key) or {}
            text, status = (gloss[key], "glossary") if key in gloss and e.get("status") != "reviewed" \
                else (e.get("text") or e.get("mt") or "", e.get("status", "missing"))
            w.writerow({"key": key, "where_it_appears": where(key), "max_chars": limit(key) or "",
                        "english": src, "current_translation": text, "status": status,
                        "approved": "Y" if status == "reviewed" else "", "corrected": "", "reviewer_notes": ""})
    return path


def import_(code: str, reviewer: str | None) -> None:
    path = LOCALES / f"{code}.yaml"
    text = path.read_text(encoding="utf-8")
    head = text.split("\n", 1)[0] if text.startswith("#") else ""
    doc = yaml.safe_load(text)
    entries = doc.setdefault("entries", {})
    src = english()
    done, refused = 0, []
    with open(OUT / f"{code}_review.csv", newline="", encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            key = row["key"]
            new = (row.get("corrected") or "").strip()
            ok = (row.get("approved") or "").strip().upper() in ("Y", "YES")
            if key not in src or not (new or ok):
                continue
            final = new or row["current_translation"].strip()
            if set(PH.findall(final)) != set(PH.findall(src[key])):
                refused.append(f"{key}: placeholders must be exactly {sorted(set(PH.findall(src[key])))}")
                continue
            lim = limit(key)
            if lim and len(final) > lim:
                refused.append(f"{key}: {len(final)} characters, limit {lim}")
                continue
            entry = {"source": src[key], "text": final, "status": "reviewed"}
            if reviewer:
                entry["reviewed_by"] = reviewer
            if (row.get("reviewer_notes") or "").strip():
                entry["note"] = row["reviewer_notes"].strip()
            entries[key] = entry
            done += 1
    path.write_text((head + "\n" if head else "") + yaml.safe_dump(doc, allow_unicode=True, sort_keys=False,
                                                                   width=1000), encoding="utf-8")
    print(f"{code}: {done} strings marked reviewed")
    for r in refused:
        print("  refused", r)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("action", choices=["export", "import"])
    ap.add_argument("langs", nargs="+")
    ap.add_argument("--reviewer", help="name recorded on imported rows, e.g. 'Dr. X, KVK Dharwad'")
    a = ap.parse_args()
    for code in a.langs:
        if a.action == "export":
            print(export(code))
        else:
            import_(code, a.reviewer)


if __name__ == "__main__":
    main()
