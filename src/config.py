"""Central paths and constants. Data lives on D:\\Morphy; code lives in the repo."""
from pathlib import Path
import os

DATA_ROOT = Path(os.environ.get("MORPHY_DATA", r"D:\Morphy"))

RAW = DATA_ROOT / "raw"
RAW_IMD = RAW / "imd"
RAW_INDICES = RAW / "indices"
INTERIM = DATA_ROOT / "interim"
PROCESSED = DATA_ROOT / "processed"
EXPORTS = DATA_ROOT / "exports"          # what the web app consumes

for _p in (RAW_IMD, RAW_INDICES, INTERIM, PROCESSED, EXPORTS):
    _p.mkdir(parents=True, exist_ok=True)

# --- Training period -------------------------------------------------------
# IMD gridded rainfall starts 1901, but the planetary predictors constrain us:
# MJO RMM starts 1974-06, ERA5 from 1940, CHIRPS from 1981.
YEAR_START = 1980
YEAR_END = 2025

# --- Monsoon season --------------------------------------------------------
# Kharif window. Onset search starts well before the climatological all-India
# onset (1 June over Kerala) because interior peninsular onset varies widely.
SEASON_START_DOY = 121   # 1 May
SEASON_END_DOY = 304     # 31 Oct

# --- Event definitions (see docs/LABELS.md for justification) --------------
WET_DAY_MM = 2.5             # IMD's standard "rainy day" threshold
ONSET_WINDOW_DAYS = 5        # accumulate over this many days...
ONSET_ACCUM_MM = 25.0        # ...and require this much rain to call a wet spell
ONSET_CHECK_DAYS = 30        # look this far ahead to test whether onset held
FALSE_ONSET_DRY_RUN = 10     # a dry run this long inside the check window
                             # invalidates the onset  -> "false onset"
DRY_SPELL_DAYS = 7           # >= this many consecutive dry days = dry spell
LONG_DRY_SPELL_DAYS = 10     # crop-damaging break
HEAVY_RAIN_MM = 64.5         # IMD "heavy rainfall" class, mm/day

# --- Grid ------------------------------------------------------------------
IMD_RES = 0.25
INDIA_BOX = dict(lat_min=6.5, lat_max=38.5, lon_min=66.5, lon_max=100.0)
