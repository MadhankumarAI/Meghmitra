"""Planetary indices as an *as-of* daily table: what was actually knowable on each day.

A forecast issued on day d may only use index values that had been published by
d. Each source gets a publication lag; `asof()` joins on availability date, not
observation date. Getting this wrong silently leaks the future into the hindcast.

Sources and why: docs/DECISIONS.md. The IOD arrives as NOAA PSL's Dipole Mode Index
(HadISST1.1, monthly); BSISO is not used.
"""
from __future__ import annotations
import sys
from pathlib import Path
import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from config import RAW_INDICES, PROCESSED

# Days between the observation date and the day the value is publicly available.
LAG_DAYS = {
    "romi": 2,       # NOAA PSL ROMI, updated daily
    "nino34_wk": 7,  # CPC weekly OISST, week centred on Wednesday, posted the next week
    # HadISST is monthly and lands mid-following-month; PSL marks the newest months
    # "preliminary". 30 days after month end is the safe side of that.
    "dmi": 30,
}
DMI_URL = "https://psl.noaa.gov/data/timeseries/month/data/dmi.had.long.data"


def read_romi(path: Path = RAW_INDICES / "romi.cpcolr.1x.txt") -> pd.DataFrame:
    """NOAA PSL ROMI: year month day hour PC1 PC2 amplitude.

    Kiladis et al. (2014): ROMI PC2 ~ RMM1 and -PC1 ~ RMM2, so the familiar
    8-phase Wheeler-Hendon diagram is drawn in the (PC2, -PC1) plane.
    """
    df = pd.read_csv(path, sep=r"\s+", header=None,
                     names=["y", "m", "d", "h", "pc1", "pc2", "amp"])
    df["date"] = pd.to_datetime(dict(year=df.y, month=df.m, day=df.d))
    x, y = df["pc2"], -df["pc1"]
    ang = np.arctan2(y, x)
    # Wheeler-Hendon: phase 1 starts at 180 deg (-x axis), phases advance
    # counter-clockwise in 45-degree sectors.
    df["mjo_phase"] = (((ang + np.pi) // (np.pi / 4)).astype(int) % 8) + 1
    df["mjo_sin"], df["mjo_cos"] = np.sin(ang), np.cos(ang)
    df = df.rename(columns={"pc1": "mjo_pc1", "pc2": "mjo_pc2", "amp": "mjo_amp"})
    return df[["date", "mjo_pc1", "mjo_pc2", "mjo_amp", "mjo_phase", "mjo_sin", "mjo_cos"]]


def read_nino34_weekly(path: Path = RAW_INDICES / "oni_weekly.txt") -> pd.DataFrame:
    """CPC wksst9120.for: fixed-width weekly Nino regions (SST and anomaly).

    Columns are fixed-width, so a negative anomaly fuses onto the SST before it
    ("24.4-0.8"). Whitespace splitting silently drops exactly those lines, i.e.
    La Nina weeks. Parse numbers with a regex instead.
    """
    import re
    num = re.compile(r"-?\d+\.\d+")
    rows = []
    for line in path.read_text().splitlines():
        head = line.strip()[:9]
        try:
            date = pd.to_datetime(head, format="%d%b%Y")
        except ValueError:
            continue
        if pd.isna(date):
            continue
        vals = num.findall(line[10:])
        if len(vals) != 8:
            raise ValueError(f"unparsed CPC line: {line!r}")
        rows.append((date, float(vals[5])))        # order: SST,SSTA x (1+2, 3, 34, 4)
    return pd.DataFrame(rows, columns=["date", "nino34"])


def read_dmi(path: Path = RAW_INDICES / "dmi.had.long.data") -> pd.DataFrame:
    """NOAA PSL Dipole Mode Index: one row per year, twelve monthly values.

    DMI = SST anomaly over 50-70E, 10S-10N minus 90-110E, 10S-0 (Saji et al. 1999) - the
    index the problem statement names as IOD. Dated to the END of its month, because that is
    the earliest the month can be complete; `asof` then adds the publication lag.
    """
    rows = []
    for line in path.read_text().splitlines():
        f = line.split()
        if len(f) != 13 or not f[0].isdigit():
            continue
        year = int(f[0])
        for m, v in enumerate(f[1:], start=1):
            x = float(v)
            if x < -900:                                  # -9999: month not published yet
                continue
            rows.append((pd.Timestamp(year, m, 1) + pd.offsets.MonthEnd(0), x))
    df = pd.DataFrame(rows, columns=["date", "dmi"]).sort_values("date")
    df["dmi_3m"] = df["dmi"].rolling(3, min_periods=1).mean().round(4)   # only past months
    return df.reset_index(drop=True)


def asof(frames: dict[str, pd.DataFrame], days: pd.DatetimeIndex) -> pd.DataFrame:
    """For every issue day, the latest value of each source already published."""
    out = pd.DataFrame({"issue_date": days})
    for name, df in frames.items():
        d = df.copy()
        d["available"] = d["date"] + pd.Timedelta(days=LAG_DAYS[name])
        d = d.drop(columns="date").sort_values("available")
        cols = [c for c in d.columns if c != "available"]
        out = pd.merge_asof(out.sort_values("issue_date"), d,
                            left_on="issue_date", right_on="available", direction="backward")
        out[f"{name}_age_days"] = (out["issue_date"] - out["available"]).dt.days
        out = out.drop(columns="available")
    return out


def main():
    romi = read_romi()
    nino = read_nino34_weekly()
    dmi = read_dmi()
    days = pd.date_range("1991-01-01", pd.Timestamp.today().normalize(), freq="D")
    table = asof({"romi": romi, "nino34_wk": nino, "dmi": dmi}, days)
    table.to_parquet(PROCESSED / "indices_asof.parquet", index=False)

    # --- checks -----------------------------------------------------------
    print(f"ROMI {romi.date.min().date()} .. {romi.date.max().date()}  rows {len(romi)}")
    print(f"Nino34 weekly {nino.date.min().date()} .. {nino.date.max().date()}  rows {len(nino)}")
    print(f"DMI monthly {dmi.date.min().date()} .. {dmi.date.max().date()}  rows {len(dmi)}"
          f"  (2019 positive IOD peak: {dmi.set_index('date').loc['2019-10', 'dmi'].iloc[0]:+.2f})")
    gaps = nino["date"].diff().dt.days.dropna()
    assert (gaps == 7).all(), f"weekly Nino34 has gaps: {gaps.value_counts().to_dict()}"
    print(f"  weeks contiguous; negative-anomaly weeks: {(nino.nino34 < 0).mean():.0%}"
          f"  (strong La Nina 2010-12: {nino.set_index('date').loc['2010-12','nino34'].mean():+.2f})")
    # MJO must propagate eastward = phases advance 1->8 over time on strong days
    strong = romi[romi.mjo_amp > 1.0].copy()
    dphase = strong["mjo_phase"].diff().where(strong["date"].diff().dt.days == 1)
    fwd = ((dphase == 1) | (dphase == -7)).sum()
    back = ((dphase == -1) | (dphase == 7)).sum()
    print(f"phase transitions on strong-MJO days: forward {fwd}, backward {back} "
          f"-> {'OK eastward' if fwd > 3 * back else 'CHECK PHASE CONVENTION'}")
    # no issue date may see a value that wasn't published yet
    assert (table.dropna()["romi_age_days"] >= 0).all()
    assert (table.dropna()["nino34_wk_age_days"] >= 0).all()
    print("as-of table:", table.shape, "| no future values leaked")
    print(table[table.issue_date == "2023-07-01"].T.to_string(header=False))


if __name__ == "__main__":
    main()
