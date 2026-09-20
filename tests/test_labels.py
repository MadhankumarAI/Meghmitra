"""Label logic on synthetic rain with known answers.  Run: python tests/test_labels.py"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
import numpy as np
from features.labels import onset_labels, forward_dry_run

T = 120


def test_basic_cases():
    r = np.zeros((T, 1, 4))
    r[10:16, 0, 0] = [10, 10, 10, 0, 10, 10]; r[16:, 0, 0] = np.tile([8, 0, 0], 40)[:T - 16]      # clean onset
    r[10:15, 0, 1] = [10, 10, 10, 0, 5]                                                         # false, then true
    r[40:45, 0, 1] = [10, 10, 10, 0, 10]; r[45:, 0, 1] = np.tile([9, 0, 0], 30)[:T - 45]
    r[::4, 0, 2] = 1.0                                                                          # never enough rain
    to, nf, ff = onset_labels(r)                                                                # cell 3: all dry
    assert to[0, 0] == 10
    assert (nf[0, 1], ff[0, 1], to[0, 1]) == (1, 10, 40)
    assert to[0, 2] == -1 and to[0, 3] == -1
    rr = np.zeros((10, 1, 1)); rr[0, 0, 0] = 50
    assert forward_dry_run(rr)[0, 0, 0] == 0 and forward_dry_run(rr)[1, 0, 0] == 9


def test_pre_season_storm_is_ignored():
    """A storm before the search start must be neither an onset nor a false onset."""
    r = np.zeros((T, 1, 2))
    for c in range(2):
        r[10:15, 0, c] = [10, 10, 10, 0, 10]                      # storm, then 35 dry days
        r[50:, 0, c] = np.tile([10, 10, 0], 24)[:T - 50]          # the monsoon
    to, nf, _ = onset_labels(r, np.array([[0, 30]]))              # cell 1 counts rain from day 30
    assert (to[0, 0], nf[0, 0]) == (50, 1)
    assert (to[0, 1], nf[0, 1]) == (50, 0)


if __name__ == "__main__":
    test_basic_cases(); test_pre_season_storm_is_ignored()
    print("all label tests pass")
