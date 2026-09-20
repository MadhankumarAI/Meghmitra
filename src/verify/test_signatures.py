"""Synthetic check: a block whose event happens only in MJO phase 3 must show a
strong positive phase-3 signature; a block with no MJO link must show ~0."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import numpy as np
from scipy import sparse
from models.signatures import per_year_counts, estimate, lookup, issue_bin, N_BINS

rng = np.random.default_rng(0)
Y, I, L, B = 30, 153, 4, 2
mjo = rng.integers(0, 9, size=(Y, I)).astype(np.int8)
T = np.zeros((Y, I, L, B), np.int8)
T[..., 0] = (mjo == 3)[:, :, None]                      # block 0: event iff phase 3
T[..., 1] = (rng.random((Y, I, L)) < 0.2)               # block 1: 20% at random, no link
H, V = per_year_counts(T, mjo, 9)
assert H.max() > 1, "counts must be sums, not a logical OR"
sig = estimate(H, V, np.ones(Y, bool), sparse.identity(B, format="csr"))
print("block 0 signature by phase (bin 3, W1):", np.round(sig[:, 3, 0, 0], 2))
print("block 1 signature by phase (bin 3, W1):", np.round(sig[:, 3, 0, 1], 2))
assert sig[3, 3, 0, 0] > 0.5 and (np.delete(sig[:, 3, 0, 0], 3) < 0).all()
# no-link block: sampling noise only. ~50 samples/cell at p=0.2 -> worst of 360 cells
# reaches ~0.11 by chance; neighbour pooling (absent in this 2-block test) shrinks it.
noise = np.abs(sig[:, :, :, 1])
print(f"no-link block: mean |sig| {noise.mean():.3f}, max {noise.max():.3f}")
assert noise.mean() < 0.03 and noise.max() < 0.15
row = lookup(sig, np.array([3, 5, -1]), issue_bin(I)[[40, 40, 40]], 0, np.array([0]))
assert row[0, 0] > 0.5 and row[1, 0] < 0 and row[2, 0] == 0
print("signature tests pass")
