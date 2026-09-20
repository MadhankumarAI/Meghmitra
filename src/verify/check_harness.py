"""Build fold climatology, self-test the scoring harness, and prove no fold leaks."""
import sys, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import numpy as np, xarray as xr
from config import PROCESSED
from models.climatology import fold_climatology, EVENTS, FOLDS, fold_of
from verify.score import summary

tg = xr.open_dataset(PROCESSED / "targets.nc"); years = tg.year.values
t0 = time.time(); clim = {}
for e in EVENTS:
    clim[e] = fold_climatology(tg[e].values.astype(np.int8), years)
    print(f"clim {e}: {time.time()-t0:.0f}s", flush=True)
xr.Dataset({e: (tg[e].dims, clim[e]) for e in EVENTS}, coords=tg.coords).to_netcdf(
    PROCESSED / "clim_folds.nc", encoding={e: {"zlib": True} for e in EVENTS})

# --- LEAK PROOF: scramble one fold's targets; its climatology must not change -------
t = tg["dry10"].values.astype(np.int8).copy()
fi = 4; sel = np.array([fold_of(int(y)) == fi for y in years])
t2 = t.copy(); t2[sel] = 1 - t2[sel]                       # invert every 2019-2025 label
c1, c2 = fold_climatology(t, years), fold_climatology(t2, years)
assert np.array_equal(c1[sel], c2[sel]), "LEAK: fold climatology depends on its own years"
assert not np.array_equal(c1[~sel], c2[~sel]), "other folds should see the change"
print(f"leak proof: inverting all {FOLDS[fi]} labels leaves that fold's climatology bit-identical ✓")

# --- harness self-tests ----------------------------------------------------------
c = clim["dry10"]
assert abs(summary(c, c, t, years)["W1"]["bss"]) < 1e-9
assert abs(summary(t.astype(np.float32), c, t, years)["W1"]["bss"] - 1) < 1e-9
nat = np.broadcast_to(c.mean(-1, keepdims=True), c.shape)
bn = summary(nat, c, t, years)["W1"]["bss"]; assert bn < 0
print(f"self-tests pass (clim=0, perfect=1, all-India constant={bn:+.3f})")

for e in EVENTS:
    s = summary(clim[e], clim[e], tg[e].values.astype(np.int8), years)
    print(f"{e:6s} base W1 {s['W1']['base_rate']:.3f}  clim AUC W1 {s['W1']['auc']:.3f} W4 {s['W4']['auc']:.3f}"
          f"  reliability error {s['reliability_error']:.4f}")
