"""Normal monsoon onset date per location, and where the onset search may start.

Approximates IMD's normal onset isolines (2020 revision) from latitude and longitude:
the Arabian Sea branch advances north-northwest from Kerala (~1 Jun) to Mumbai
(~11 Jun), Delhi (~27 Jun) and west Rajasthan (~8 Jul); the Bay of Bengal branch
reaches the northeast and east earlier (Guwahati ~5 Jun, Kolkata ~10 Jun).
Checked against those cities to within about +-5 days, well inside the 20-day
allowance below.

Rain that meets the sowing criterion more than PRE_ONSET_DAYS before the normal
onset is pre-monsoon convection (e.g. May thunderstorms over Rajasthan), not the
monsoon. Counting it inflated false onsets by ~44% before this correction.
"""
import numpy as np

PRE_ONSET_DAYS = 20
EARLIEST_DOY = 121          # 1 May: never search earlier than this


def normal_onset_doy(lat, lon):
    lat, lon = np.asarray(lat, float), np.asarray(lon, float)
    d = (152
         + 1.4 * np.clip(lat - 10, 0, None)                       # northward advance
         + 1.8 * np.clip(77 - lon, 0, None) * (lat > 20)          # slower into the northwest
         - 2.5 * np.clip(lon - 84, 0, None))                      # Bay branch arrives earlier in the east
    return np.clip(d, 150, 192)


def search_start_doy(lat, lon):
    return np.maximum(EARLIEST_DOY, normal_onset_doy(lat, lon) - PRE_ONSET_DAYS).astype(int)


if __name__ == "__main__":
    for name, la, lo, imd in [("Thiruvananthapuram", 8.5, 76.9, 152), ("Bengaluru", 13.0, 77.6, 156),
                              ("Mumbai", 19.1, 72.9, 162), ("Bhubaneswar", 20.3, 85.8, 162),
                              ("Kolkata", 22.6, 88.4, 161), ("Guwahati", 26.1, 91.7, 156),
                              ("Bhopal", 23.3, 77.4, 170), ("Patna", 25.6, 85.1, 166),
                              ("Delhi", 28.6, 77.2, 178), ("Jaisalmer", 26.9, 70.9, 189)]:
        n = float(normal_onset_doy(la, lo))
        print(f"{name:18s} approx DOY {n:5.0f}  IMD normal {imd}  diff {n - imd:+4.0f}")
