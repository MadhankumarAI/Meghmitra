# Locked decisions

Each entry here is chosen so it does not need to be redone. Changing one means re-running everything downstream of it, so a change needs a stated reason.

## Compute: user02 @ 14.143.127.114

| Resource | Machine | **Our budget** | Why the gap |
|---|---|---|---|
| CPU | 42 Xeon Cascade Lake | **20 workers** (was 36) | user02 also runs `bci_a100` EEG experiments using ~18 cores; oversubscribing slowed both. Threads come from `MORPHY_CPUS`, never hard-coded |
| RAM | 62 GB | **34 GB** | that job uses 7.6 GB; running out of RAM OOM-kills every process on the box, so this stays conservative |
| GPU | A100 80 GB (MIG 7g, whole card) | **72 GB** | that job uses ~1 GB; owner authorised killing it if training is ever starved |
| Disk | `/home/user02` 585 GB free | **all data here** | — |
| Disk | `/` **99% full, 19 GB free** | **never written to** | filling it takes the server down for every user |

Environment: `source ~/morphy/env.sh` before every job. It pins `TMPDIR`, caches, thread counts and the budget, raises the open-file limit, and activates the `morphy` conda env.

**The GPU is a MIG slice, not the whole card.** Device `A100 80GB PCIe MIG 1c.7g.80gb`: all 80 GB of memory but **14 of 108 SMs**. Measured with warm-up: **24.4 TFLOP/s bf16, 12.4 TFLOP/s TF32**. Train in bf16 mixed precision. Estimated ~35 min per validation fold for the spatial model, so the full hindcast runs overnight. A root user could reassign all 7 compute slices for ~7× speed; that needs the pending reboot and may affect other accounts, so it is not planned.

PyTorch is pinned to **2.5.1+cu121**, the exact build already proven to reach CUDA on this box's driver (the NVIDIA userspace was auto-upgraded 2026-09-17 without a reboot; `nvidia-smi` is broken, CUDA via torch works).

## Where each job runs

| Job | Runs on | Reason |
|---|---|---|
| IMD rainfall download | Laptop | `imdpune.gov.in` is unreachable from the server |
| ERA5 atmosphere | Server | largest dataset, server has the disk |
| Labels, features, all training, hindcast | Server | 32 cores + A100 |
| UI exports | Server → `D:\Morphy\exports` | web app reads from there |

## Data

**Period: 1981–2025, all 12 months** (training 1991–2025, see indices below). The full year is kept, not only the monsoon season, because pre-monsoon state (April–May sea surface and soil moisture) is predictive and climatology needs the full annual cycle.

**ERA5 domain: 20°S–40°N, 40°E–160°E at native 0.25°.** Deliberately much larger than India. A spatial model must see the upstream moisture source over the Arabian Sea and southern Indian Ocean, the whole IOD dipole, and the MJO arriving from the west. Resolution can always be coarsened later but never refined, so native resolution is kept.

**ERA5 access: Copernicus CDS daily-statistics datasets**, not Google's public ARCO-ERA5 copy. ARCO stores pressure-level variables in `(1 hour, 37 levels, 721, 1440)` chunks, so any regional single-level read pulls the whole globe at every level: ~21 TB for our needs, measured at ~25 s per variable-day. CDS computes daily means and crops to our domain server-side (~90 GB total) and serves ERA5T about 5 days behind real time, which the live system needs. Datasets: `derived-era5-pressure-levels-daily-statistics`, `derived-era5-single-levels-daily-statistics`.

**ERA5 variables, daily means:**

| Variable | Level | Physical role |
|---|---|---|
| u, v wind | 850 hPa | Monsoon low-level jet: strength and position drives active vs break |
| Specific humidity | 850 hPa | Moisture being transported |
| u wind | 200 hPa | Tropical easterly jet, upper-level monsoon strength |
| Geopotential | 500 hPa | Mid-tropospheric troughs and the monsoon trough |
| Mean sea-level pressure | surface | Monsoon trough and pressure gradient |
| Total column water vapour | column | Precipitable water |
| Outgoing longwave radiation | top | Convection proxy; the MJO/BSISO signal itself |
| Soil moisture layer 1 | 0–7 cm | Land memory: what the soil will do with the next rain |
| Sea surface temperature | surface | Regional ocean boundary condition |

**Planetary indices.** Each one was checked for whether it is *still published*, because an index that stops updating means the live system cannot issue a forecast. Checked 2026-09-19:

| Driver | Source used | Available | Rejected alternative and why |
|---|---|---|---|
| **ENSO** | CPC weekly OISST Niño 3.4 anomaly | 1981-09 → 2026-09-09, weekly | PSL monthly Niño 3.4: fine but monthly and ~10-day lag; kept only as a cross-check |
| **MJO** | NOAA PSL **ROMI** (CPC OLR), daily | 1991-01 → 2026-09-14 | BoM RMM: **discontinued 2024-02-24**, and switches method in 2013 (inhomogeneous). OMI: needs future data, lags 3 months |
| **IOD** | **Computed in-house** from ERA5 SST: west box 50–70°E 10°S–10°N minus east box 90–110°E 10°S–0° | ERA5 lag ~5 days | PSL DMI: last value May 2026, **~4 months behind**, unusable operationally |
| **BSISO** | **Computed in-house** from ERA5 OLR and u850, Lee et al. (2013) method, domain 10°S–40°N 40–160°E | ERA5 lag ~5 days | No reliable operational feed found |

BSISO is added deliberately: it is the monsoon-season intraseasonal mode and is more relevant to Indian active/break cycles than the MJO index the problem statement names. The in-house indices use EOFs and climatologies **fitted inside each validation fold**, so they cannot leak the test year.

Context worth stating in the pitch: Niño 3.4 reached **+1.89 °C in August 2026**. The current year is an El Niño year.

**Consequence for the period.** ROMI starts in 1991, so **model training and the hindcast archive cover 1991–2025 (35 leave-one-year-out folds).** The longer 1981–2025 record is still used for the climatology baseline (excluding the test year), where more years reduce noise. The ERA5 domain extends east to **160°E** (not 120°E) so the BSISO calculation sees the whole west Pacific.

**CHIRPS is used for spatial texture, not as daily truth (measured, 2026-09-19).** Per block, June–September 1981–2025, CHIRPS vs IMD: seasonal totals agree (ratio median **1.06**, IQR 0.98–1.15), dry-week agreement **86%**, weekly correlation **0.63**, but **daily correlation only 0.31**. CHIRPS's daily estimates come from satellite cloud-top temperature and misplace rain by about a day, and our events are defined daily. So event labels stay on IMD, and CHIRPS enters as static 5 km covariates: block climatology and wet-day frequency relative to the parent IMD cell. Those let the model tell neighbouring blocks apart without inheriting CHIRPS's timing errors. Candidate upgrades for a daily high-resolution target, if time allows: IMERG (0.1°, 2000–) or MSWEP (0.1°, gauge-corrected).

**Blocks:** geoBoundaries India ADM3, 6,824 subdistricts, open licence. **84% of blocks (5,703) are smaller than one IMD 0.25° cell**, so IMD alone cannot tell neighbouring blocks apart. Therefore: **IMD 0.25°** is the authoritative gauge record (event climatology, validation); **CHIRPS v2.0 0.05°** (~5 km, 1981–present) is the high-resolution target the spatial model learns to predict. Block values are area-weighted means over the cells each block intersects.

## Validation protocol: fixed before any model is trained

This section exists because a leaking validation protocol is the one mistake that would invalidate every number in the PPT and the demo.

1. **Five blocks of seven consecutive years, each held out whole:** 1991–97, 1998–2004, 2005–11, 2012–18, 2019–25. *(Revised from leave-one-year-out before any model was trained.)* Two reasons. (a) Adjacent years aren't independent: 2023 and 2024 share one El Niño, so a model tested on 2023 but trained on 2024 has partly seen the answer. Contiguous blocks close that leak. (b) It's 7× cheaper, so all three models run under the identical protocol. The demo consequence is a stronger claim: the 2023 replay comes from a model that has **never seen any data after 2018**. 1981–1990 (no MJO index) is used only for climatology.
2. **Everything derived from data is fitted inside the fold, excluding every year of the held-out block**: climatology, anomalies, standardisation statistics, EOF/PCA patterns, in-house IOD and BSISO. This includes the climatology used as a model *input*. If it were computed leaving out only the one year being forecast, the training rows for 2019 would carry 2023's rainfall.
3. **Initialisation uses only information available at issue time.** A forecast issued on day d uses observations up to d−1 (index publication lag respected). No future rainfall in any feature.
4. **Every model is scored against climatology** with Brier Skill Score, reliability diagrams and ROC, per event and per lead week.
5. **Three models are compared under the identical protocol:** climatology, gradient boosting per block (CPU), spatial neural downscaler (A100). The published model per event and lead is whichever scores best, including if that is the simpler one.
6. **Calibration is reported as count-weighted reliability error**, not the worst bin. The worst bin is dominated by rare cases: onset climatology is overconfident in the top 0.3% of forecasts, where a block's onset is unusually late, and that alone would make one headline number misleading.
7. **The demo year (2023) is not chosen by looking at results.** It is chosen now, for being the most recent El Niño year with a documented record-dry August, before any hindcast exists.
