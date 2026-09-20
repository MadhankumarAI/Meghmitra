"""Fetch IMD real-time gridded rainfall day by day, resumably (run on the laptop:
imdpune.gov.in isn't reachable from the server).

  python download_imd_rt.py 2026-05-01 2026-09-18      -> D:/Morphy/raw/imd_rt/rain_ind0.25_YY_MM_DD.grd

imdpune throttles and drops connections, so: one day per request, skip days already on
disk, back off and retry on errors, and keep cycling until every day is present.
"""
import sys, time
from pathlib import Path
import pandas as pd
import imdlib

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from config import RAW

OUT = RAW / "imd_rt"


def path_for(d: pd.Timestamp) -> Path:
    return OUT / f"rain_ind0.25_{d:%y_%m_%d}.grd"


def main(start: str, end: str, max_rounds: int = 20):
    OUT.mkdir(parents=True, exist_ok=True)
    days = pd.date_range(start, end)
    for rnd in range(max_rounds):
        todo = [d for d in days if not path_for(d).exists() or path_for(d).stat().st_size < 1000]
        if not todo:
            print(f"all {len(days)} days present", flush=True)
            return
        print(f"round {rnd + 1}: {len(todo)} days to fetch", flush=True)
        for d in todo:
            try:
                imdlib.get_real_data("rain", d.strftime("%Y-%m-%d"), d.strftime("%Y-%m-%d"), file_dir=str(OUT))
                print(f"{d:%Y-%m-%d} ok", flush=True)
            except Exception as e:
                print(f"{d:%Y-%m-%d} failed ({type(e).__name__}); backing off", flush=True)
                time.sleep(30)
        time.sleep(10)
    missing = [d.strftime("%Y-%m-%d") for d in days if not path_for(d).exists()]
    print(f"gave up with {len(missing)} missing: {missing[:10]}", flush=True)


if __name__ == "__main__":
    main(*sys.argv[1:3])
