"""Block names in Indian scripts from Wikidata (CC0).

For each block, look up Wikidata items whose English label equals the block name,
keep only those within MAX_KM of the block, and take the nearest one's labels in
Kannada, Hindi, Telugu, Tamil and Marathi. Blocks without a confident match keep
their English name; nothing is transliterated by guesswork.

  python indic_names.py            -> PROCESSED/block_names.parquet
"""
from __future__ import annotations
import os, sys, time, json
from pathlib import Path
import numpy as np
import pandas as pd
import requests

DATA = Path(os.environ.get("MORPHY_DATA", Path.home() / "morphy" / "data"))
PROCESSED = DATA / "processed"
LANGS = ["kn", "hi", "te", "ta", "mr"]
MAX_KM = 40.0
BATCH = 120
URL = "https://query.wikidata.org/sparql"
HEADERS = {"Accept": "application/sparql-results+json",
           "User-Agent": "MungaruSIH/0.1 (monsoon advisory research prototype; Smart India Hackathon)"}


def query(names: list[str]) -> list[dict]:
    values = " ".join(json.dumps(n) + "@en" for n in names)
    opt = "\n".join(f'OPTIONAL {{ ?item rdfs:label ?{l} FILTER(lang(?{l})="{l}") }}' for l in LANGS)
    q = f"""SELECT ?item ?en ?coord {' '.join('?' + l for l in LANGS)} WHERE {{
      VALUES ?en {{ {values} }}
      ?item rdfs:label ?en ; wdt:P625 ?coord ; wdt:P17 wd:Q668 .
      {opt}
    }}"""
    for attempt in range(5):
        r = requests.post(URL, data={"query": q}, headers=HEADERS, timeout=120)
        if r.status_code == 200:
            return [{k: v["value"] for k, v in b.items()} for b in r.json()["results"]["bindings"]]
        time.sleep(10 * (attempt + 1))                      # 429 / 5xx: back off politely
    raise RuntimeError(f"Wikidata failed: {r.status_code} {r.text[:200]}")


def km(lat1, lon1, lat2, lon2):
    p = np.pi / 180
    a = np.sin((lat2 - lat1) * p / 2) ** 2 + np.cos(lat1 * p) * np.cos(lat2 * p) * np.sin((lon2 - lon1) * p / 2) ** 2
    return 12742 * np.arcsin(np.sqrt(a))


def main():
    blocks = pd.read_parquet(PROCESSED / "blocks.parquet")
    names = sorted(set(blocks["name"]))
    rows = []
    for k in range(0, len(names), BATCH):
        rows += query(names[k:k + BATCH])
        print(f"{min(k + BATCH, len(names))}/{len(names)} names, {len(rows)} candidates", flush=True)
        time.sleep(1.0)
    c = pd.DataFrame(rows)
    pt = c["coord"].str.extract(r"Point\(([-\d.]+) ([-\d.]+)\)").astype(float)
    c["lon"], c["lat"] = pt[0], pt[1]

    out = []
    by_name = {n: g for n, g in c.groupby("en")}
    for b in blocks.itertuples():
        g = by_name.get(b.name)
        rec = {"block_id": b.block_id}
        if g is not None:
            d = km(b.lat, b.lon, g["lat"].values, g["lon"].values)
            j = int(np.argmin(d))
            if d[j] <= MAX_KM:
                best = g.iloc[j]
                rec.update({"wikidata": best["item"].rsplit("/", 1)[-1], "match_km": round(float(d[j]), 1)})
                for l in LANGS:
                    v = best.get(l)
                    rec[f"name_{l}"] = v if isinstance(v, str) else None
        out.append(rec)
    df = pd.DataFrame(out)
    df.to_parquet(PROCESSED / "block_names.parquet", index=False)
    m = df["wikidata"].notna()
    print(f"matched {m.sum()}/{len(df)} blocks ({m.mean():.0%}); median distance {df.loc[m, 'match_km'].median():.1f} km")
    for l in LANGS:
        print(f"  {l}: {df[f'name_{l}'].notna().mean():.0%} of blocks have a name")


if __name__ == "__main__":
    main()
