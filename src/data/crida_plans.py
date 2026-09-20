"""ICAR-CRIDA District Agriculture Contingency Plans: fetch and turn into structured advice.

These are the plans the Ministry itself uses: per district, what a farmer should do when the
monsoon is late by 2/4/6/8 weeks, during mid-season dry spells, and in unusual rain. We read
them so the advisory engine quotes a published plan for that district instead of a table we
wrote (docs/ADVICE_SOURCES.md).

  python crida_plans.py index            list every plan PDF (state, district, url)
  python crida_plans.py fetch [STATE]    download the PDFs (resumable)
  python crida_plans.py parse [STATE]    extract crops, sowing windows and contingency rows

Writes RAW/crida/index.json, RAW/crida/<state>/<district>.pdf and PROCESSED/crida_plans.json.
Every extracted row keeps its district, page and source URL, so the console can cite it.
"""
from __future__ import annotations
import sys, re, json, html, unicodedata, urllib.parse, subprocess
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from config import RAW, PROCESSED

BASE = "https://www.icar-crida.res.in/CP-2012/"
CRIDA = RAW / "crida"
# the delay tables are keyed by this phrasing, e.g. "Delay by 2 weeks June 3rd week"
DELAY = re.compile(r"delay(?:ed)?\s*(?:by|of)?\s*(\d+)\s*weeks?", re.I)
NO_CHANGE = re.compile(r"^\s*(no\s*change|same as|as usual|-|–)?\s*$", re.I)
SOWING_HEAD = re.compile(r"sowing window", re.I)
COND_HEAD = re.compile(r"condition|suggested contingency", re.I)
# a condition row that names a real situation (the stage rows underneath inherit it)
SECTION = re.compile(r"drought|delay|dry spell|flood|unusual rain|heavy rain|rainless|onset", re.I)


def clean(s: str | None) -> str:
    s = unicodedata.normalize("NFKC", s or "")
    return re.sub(r"\s+", " ", s).strip()


def state_of(link: str) -> str:
    """'statewiseplans/Karnataka (Pdf)/UAS, Dharward/KA7-Dharwad 3.2.2011.pdf' -> 'Karnataka'."""
    raw = html.unescape(urllib.parse.unquote(link.split("/")[1]))
    return re.sub(r"\s*\(pdf\)\s*$", "", raw, flags=re.I).strip()


def district_of(link: str) -> str:
    """'KA7-Dharwad 3.2.2011.pdf' -> 'Dharwad' (drop the state code and the date)."""
    name = html.unescape(urllib.parse.unquote(link.split("/")[-1]))[:-4]
    name = re.sub(r"^[A-Za-z&.\s]{2,14}?\s*-?\s*\d+\s*[-–]?\s*", "", name)  # KA7-, AP12-, WestBengal 1-
    name = re.sub(r"\d{1,2}[.\-/]\d{1,2}[.\-/]\d{2,4}.*$", "", name)        # trailing date
    name = re.sub(r"\b(final|revised|new|updated)\b.*$", "", name, flags=re.I)
    return re.sub(r"[_\s]+", " ", name).strip(" -–_")


def index() -> list[dict]:
    CRIDA.mkdir(parents=True, exist_ok=True)
    page = CRIDA / "district.html"
    if not page.exists():
        subprocess.run(["curl", "-sSf", "--max-time", "120", "-o", str(page), BASE + "district.html"], check=True)
    links = re.findall(r'href="(statewiseplans/[^"]+\.pdf)"', page.read_text(errors="ignore"), re.I)
    rows, seen = [], set()
    for l in links:
        st, di = state_of(l), district_of(l)
        if not di or (st, di) in seen:
            continue
        seen.add((st, di))
        href = urllib.parse.unquote(html.unescape(l))          # decode first: some hrefs are encoded
        rows.append({"state": st, "district": di, "url": BASE + urllib.parse.quote(href),
                     "file": f"{st}/{di}.pdf".replace(" ", "_")})
    (CRIDA / "index.json").write_text(json.dumps(rows, indent=1))
    print(f"{len(rows)} district plans in {len({r['state'] for r in rows})} states -> {CRIDA / 'index.json'}")
    return rows


def fetch(only: str | None = None) -> None:
    rows = json.loads((CRIDA / "index.json").read_text())
    todo = [r for r in rows if not only or only.lower() in r["state"].lower()]
    got = 0
    for r in todo:
        dest = CRIDA / r["file"]
        if dest.exists() and dest.stat().st_size > 50_000:
            continue
        dest.parent.mkdir(parents=True, exist_ok=True)
        p = subprocess.run(["curl", "-sS", "--max-time", "180", "-o", str(dest), r["url"]])
        ok = p.returncode == 0 and dest.exists() and dest.stat().st_size > 50_000
        if not ok:
            dest.unlink(missing_ok=True)
            print(f"  missed {r['state']}/{r['district']}", flush=True)
        else:
            got += 1
            if got % 10 == 0:
                print(f"  {got} downloaded", flush=True)
    have = sum(1 for r in todo if (CRIDA / r["file"]).exists())
    print(f"{have} of {len(todo)} plans on disk in {CRIDA}")


def sowing_windows(text: str) -> dict[str, str]:
    """Section 1.12 'Sowing window for 5 major field crops' -> {crop: normal sowing period}."""
    m = SOWING_HEAD.search(text)
    if not m:
        return {}
    block = text[m.start(): m.start() + 1200]
    lines = [clean(l) for l in block.splitlines()[1:] if clean(l)]
    crops: list[str] = []
    for l in lines[:4]:
        # the crop names sit on the header line(s), before the first "Kharif"/"Rabi" row
        if re.match(r"^(kharif|rabi|summer|\(start)", l, re.I):
            break
        crops += [c for c in re.split(r"\s{2,}|\s·\s", l) if re.match(r"^[A-Za-z][A-Za-z \-()]{2,}$", c)]
    out: dict[str, str] = {}
    for c in crops:
        c = clean(c)
        if len(c) > 2 and not SOWING_HEAD.search(c) and "field crops" not in c.lower():
            out[c] = ""
    for l in lines:
        if re.match(r"^kharif\s*-?\s*rainfed", l, re.I):
            periods = re.split(r"\s{2,}", l.split(":", 1)[-1])
            for crop, per in zip(out, periods[1:]):
                out[crop] = clean(per)
            break
    return out


# column headers used across the plans, mapped to the fields we keep
HEADERS = {"crop_system": r"crop\s*/?\s*cropping system|normal crop", "change": r"change in crop",
           "agronomy": r"agronomic measure", "situation": r"farming situation", "remarks": r"remarks"}


def columns(cells: list[str]) -> dict[str, int] | None:
    """Read the column order off a header row; the plans are not consistent about it."""
    found = {}
    for field, pat in HEADERS.items():
        for i, c in enumerate(cells):
            if re.search(pat, c, re.I):
                found[field] = i
                break
    return found if {"crop_system", "change"} <= set(found) else None


def candidate_pages(path: Path) -> list[int]:
    """Page numbers that hold a contingency table, found with the fast text layer.

    pdfplumber's table extraction is accurate but slow, and a plan is ~40 pages of which ~8
    carry the tables. pypdfium2 reads the text layer about ten times faster, so it does the
    finding and pdfplumber only does the pages that matter.
    """
    import pypdfium2 as pdfium
    doc = pdfium.PdfDocument(str(path))
    out = []
    try:
        for i in range(len(doc)):
            page = doc[i]
            text = page.get_textpage().get_text_range()
            if COND_HEAD.search(text or ""):
                out.append(i)
            page.close()
    finally:
        doc.close()
    return out


def contingency_rows(pdf, state: str, district: str, url: str, pages: list[int] | None = None) -> list[dict]:
    """The 'Suggested contingency measures' tables: one row per (condition, crop system).

    The plans write the condition, the farming situation and the prescribed change ONCE and
    leave the cells blank for the crop rows underneath, so each value is carried down until a
    new one appears - otherwise every crop but the first reads as "no change".
    """
    rows: list[dict] = []
    todo = pages if pages is not None else range(len(pdf.pages))
    for idx in todo:
        page = pdf.pages[idx]
        pno = idx + 1
        for table in page.extract_tables():
            col = {"situation": 1, "crop_system": 2, "change": 3, "agronomy": 4}
            cond = situation = change = agronomy = ""
            for raw in table:
                cells = [clean(c) for c in raw]
                if len(cells) < 4 or all(not c for c in cells):
                    continue
                head = columns(cells)
                if head:                                        # header row: take the order, skip it
                    col = head
                    cond = situation = change = agronomy = ""
                    continue
                get = lambda f: cells[col[f]] if f in col and col[f] < len(cells) else ""
                if cells[0] and not get("crop_system"):
                    cond = cells[0]
                elif cells[0]:
                    cond = cells[0]
                situation = get("situation") or situation
                change = get("change") or change
                agronomy = get("agronomy") or agronomy
                crop_system = get("crop_system")
                if not crop_system or len(crop_system) < 3 or COND_HEAD.search(crop_system):
                    continue
                weeks = DELAY.search(cond)
                rows.append({
                    "condition": cond, "delay_weeks": int(weeks.group(1)) if weeks else None,
                    "situation": situation, "crop_system": crop_system,
                    "change": "" if NO_CHANGE.match(change) else change,
                    "agronomy": agronomy, "page": pno,
                })
    # "At vegetative stage" and friends are sub-rows of the condition above them: carry the last
    # condition that names a real situation forward, so those rows keep their meaning.
    section = ""
    for r in rows:
        if SECTION.search(r["condition"]):
            section = r["condition"]
        r.update(state=state, district=district, source=url, section=section)
    return rows


def parse(only: str | None = None) -> None:
    import pdfplumber
    rows = json.loads((CRIDA / "index.json").read_text())
    todo = [r for r in rows if (not only or only.lower() in r["state"].lower()) and (CRIDA / r["file"]).exists()]
    out: dict[str, dict] = {}
    if (PROCESSED / "crida_plans.json").exists():
        out = json.loads((PROCESSED / "crida_plans.json").read_text())
    for n, r in enumerate(todo, 1):
        try:
            path = CRIDA / r["file"]
            pages = candidate_pages(path)
            with pdfplumber.open(path) as pdf:
                head = "\n".join((pdf.pages[i].extract_text() or "") for i in range(min(10, len(pdf.pages))))
                cont = contingency_rows(pdf, r["state"], r["district"], r["url"], pages)
        except Exception as e:                                   # a few plans are scans
            print(f"  {r['state']}/{r['district']}: {type(e).__name__}", flush=True)
            continue
        sow = sowing_windows(head)
        out.setdefault(r["state"], {})[r["district"]] = {
            "sowing_windows": sow, "rows": cont, "source": r["url"],
            "crops": sorted({c for c in sow}),
        }
        if n % 5 == 0:
            print(f"  parsed {n}/{len(todo)}", flush=True)
    (PROCESSED / "crida_plans.json").write_text(json.dumps(out, indent=1))
    d = sum(len(v) for v in out.values())
    rows_n = sum(len(x["rows"]) for v in out.values() for x in v.values())
    print(f"{d} districts, {rows_n} contingency rows -> {PROCESSED / 'crida_plans.json'}")


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "index"
    arg = sys.argv[2] if len(sys.argv) > 2 else None
    {"index": lambda: index(), "fetch": lambda: fetch(arg), "parse": lambda: parse(arg)}[cmd]()
