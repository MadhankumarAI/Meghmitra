"""Emit advisories in the delivery-service contract (docs/DELIVERY_BRIEF.md §2a).

  python advisory_contract.py 2023-06-22                      all blocks with advice that day
  python advisory_contract.py 2023-06-22 --block Navalgund    one block (name or block_id)
  python advisory_contract.py 2023-06-22 --latest [PATH]      also write latest.json (brief §2b);
                                                              default EXPORTS/forecast/latest.json

Reads EXPORTS/forecast/{date}.json and EXPORTS/advisory/{date}.json and writes one
JSON object per advisory to EXPORTS/contract/{date}.jsonl, ready to POST to
/advisories. Runs anywhere the exports are (laptop or server).
"""
from __future__ import annotations
import os, sys, json, argparse
from datetime import date as _date, timedelta
from pathlib import Path

EXPORTS = Path(os.environ.get("MORPHY_EXPORTS", r"D:\Morphy\exports"))
CMRI = {0: "normal", 1: "watch", 2: "warning", 3: "alert"}
WEEK_KEYS = ("onset", "dry_spell", "heavy_rain")
CONF = {1: "high", 2: "medium", 3: "low", 4: "low"}

# The delivery service localises crops by its own ids (act/content/locales/*.yaml `crops`).
CROP_ID = {"rice": "paddy", "pigeonpea": "tur"}
# SWITCH_CROP carries the crop id named by that district's CRIDA contingency plan
# (advisory/sources.py). Where no plan was read, the engine sends its indicative ladder as text
# and we do not switch crops: the farmer is told to wait, which is the safe side.
SOW_WINDOW = 13                     # days: SOW_NOW / SWITCH_CROP "sow before" = the two-week outlook


def date_add(d: str, days: int) -> _date:
    return _date.fromisoformat(d) + timedelta(days=days)


def delivery_params(date: str, crop: str, tid: str, params: dict) -> tuple[str, dict]:
    """Engine advice -> the delivery service's template parameters (act/content/templates.yaml)."""
    params = dict(params)
    sow_by = str(date_add(date, SOW_WINDOW))
    if tid == "SOW_NOW":
        params["sow_by"] = sow_by
    elif tid == "SWITCH_CROP":
        if params.get("alternative"):
            params["sow_by"] = sow_by                 # plan-backed: alternative is a crop id already
        else:
            tid = "DELAY_SOWING"                      # indicative ladder only: wait, do not switch
            params.setdefault("wait_until", sow_by)
    if tid == "DELAY_SOWING":
        params.setdefault("wait_until", sow_by)
    return tid, params


def contract(date: str, i: int, block: dict, fc: dict, adv: list) -> dict:
    crop, tid, tier, params = adv
    tid, params = delivery_params(date, crop, tid, params)
    if params.get("alternative"):
        params["alternative"] = CROP_ID.get(params["alternative"], params["alternative"])
    weeks = []
    for w in range(4):
        row = {"week": w + 1, "confidence": CONF[w + 1]}
        for key, ev in zip(WEEK_KEYS, ("onset", "dry10", "heavy")):
            v = fc["events"][ev]["p"][w][i]
            row[key] = 0.0 if v < 0 else round(v / 100, 2)     # -1 = not applicable (onset already came)
        weeks.append(row)
    return {
        "advisory_id": f"{block['id']}_{date}_{crop}_{adv[1].lower()}",
        "issued_at": f"{date}T06:00:00+05:30",
        "valid_from": date,
        # advice covers the next two weeks unless it names its own end date
        "valid_to": params.get("wait_until") or str(date_add(date, 13)),
        "product": fc["product"],
        "block": {"block_id": block["id"], "name": block["name"],
                  "district": block["district"], "state": block["state"]},
        "cmri_class": CMRI.get(fc["cmri"][0][i], "normal"),
        "crop": CROP_ID.get(crop, crop),
        "template_id": tid,
        "params": params,
        "weeks": weeks,
        # officer contact comes from the state's KVK/ADA directory in deployment; omitted until known
        "requires_approval": True,          # human sign-off before anything reaches a farmer
    }


def latest_json(fc: dict, blocks: list) -> dict:
    """Delivery brief §2b: {block_id: {onset|dry_spell|heavy_rain: [{week, p, p_clim, confidence}]}},
    plus "_meta". Weeks where an event doesn't apply (onset already came) are left out."""
    out = {"_meta": {"issued_at": f"{fc['issued']}T06:00:00+05:30", "valid_from": fc["issued"],
                     "product": fc["product"], "source": fc.get("source", "hindcast")}}
    for b in blocks:
        i, row = b["i"], {}
        for key, ev in zip(WEEK_KEYS, ("onset", "dry10", "heavy")):
            e = fc["events"][ev]
            row[key] = [{"week": w + 1, "p": round(e["p"][w][i] / 100, 2),
                         "p_clim": round(e["clim"][w][i] / 100, 2), "confidence": CONF[w + 1]}
                        for w in range(4) if e["p"][w][i] >= 0 and e["clim"][w][i] >= 0]
        out[b["id"]] = row
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("date")
    ap.add_argument("--block", help="block name or block_id")
    ap.add_argument("--latest", nargs="?", const=str(EXPORTS / "forecast" / "latest.json"),
                    help="also write latest.json (default EXPORTS/forecast/latest.json)")
    a = ap.parse_args()
    blocks = json.loads((EXPORTS / "blocks_index.json").read_text(encoding="utf-8"))
    fc = json.loads((EXPORTS / "forecast" / f"{a.date}.json").read_text())
    adv = json.loads((EXPORTS / "advisory" / f"{a.date}.json").read_text())["advisories"]
    want = None
    if a.block:
        want = {b["i"] for b in blocks if a.block in (b["name"], b["id"])}
        if not want:
            sys.exit(f"no block named {a.block!r}")
    out_dir = EXPORTS / "contract"; out_dir.mkdir(exist_ok=True)
    out = out_dir / f"{a.date}.jsonl"
    n = 0
    with out.open("w", encoding="utf-8") as f:
        for key, rows in adv.items():
            i = int(key)
            if want is not None and i not in want:
                continue
            for r in rows:
                f.write(json.dumps(contract(a.date, i, blocks[i], fc, r), ensure_ascii=False) + "\n")
                n += 1
    print(f"{n} advisories -> {out}")
    if a.latest:
        f = Path(a.latest)
        tmp = f.with_suffix(".part")                # the bot re-reads on change: never show half a file
        tmp.write_text(json.dumps(latest_json(fc, blocks), separators=(",", ":")))
        tmp.replace(f)
        print(f"latest -> {f} ({f.stat().st_size / 1e6:.1f} MB)")


if __name__ == "__main__":
    main()
