"""Download IMD 0.25 deg gridded daily rainfall for the full training period."""
import sys, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import imdlib
from config import RAW_IMD, YEAR_START, YEAR_END

def main(y0=YEAR_START, y1=YEAR_END):
    out = RAW_IMD
    for yr in range(y0, y1 + 1):
        f = out / "rain" / f"{yr}.grd"
        if f.exists() and f.stat().st_size > 0:
            print(f"{yr} cached", flush=True); continue
        for attempt in range(3):
            try:
                imdlib.get_data('rain', yr, yr, fn_format='yearwise', file_dir=str(out))
                print(f"{yr} ok", flush=True); break
            except Exception as e:
                print(f"{yr} attempt {attempt+1} failed: {e}", flush=True); time.sleep(5)
        else:
            print(f"{yr} GAVE UP", flush=True)

if __name__ == "__main__":
    main(*(int(a) for a in sys.argv[1:]))
