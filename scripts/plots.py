"""The four performance figures, drawn from the exported artifacts.

  .venv/Scripts/python scripts/plots.py [OUT_DIR]

Writes into docs/img by default:
  perf_roc.png          ROC curves, week 1
  perf_pr.png           precision-recall curves, week 1
  perf_reliability.png  reliability (calibration), week 1
  perf_matrix.png       performance matrix: AUC by event and lead week

Inputs (all produced by the pipeline, never typed in):
  exports/curves.json      src/verify/curves.py    ROC, PR and reliability points
  exports/confusion.json   src/verify/confusion.py precision and recall at the real thresholds
  exports/model_card.json  src/export/model_card.py the performance matrix

The chart is the subject: one panel per figure, the name of the chart as its title, and numbers
only where the number is the point.
"""
from __future__ import annotations
import json, sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.ticker import PercentFormatter
from matplotlib.colors import LinearSegmentedColormap

EXPORTS = Path("D:/Morphy/exports")
OUT = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).resolve().parents[1] / "docs" / "img"

INK = "#101820"
MUTED = "#6b7785"
GRID = "#e6eaef"
BLUE = "#1f5fa8"
GREEN = "#2f8f68"
AMBER = "#c6891c"
GREY = "#aeb7c2"
EVENT_COLOR = {"dry10": BLUE, "onset": GREEN, "heavy": AMBER}
FOOT = "Held-out years only: 1991-2025 in five blocks of seven years, each block scored by a model that never saw it."

plt.rcParams.update({
    "figure.dpi": 200, "savefig.dpi": 200,
    "font.family": "DejaVu Sans", "font.size": 11,
    "axes.edgecolor": GRID, "axes.labelcolor": INK, "axes.labelsize": 11,
    "axes.grid": True, "grid.color": GRID, "grid.linewidth": 0.8,
    "xtick.color": MUTED, "ytick.color": MUTED, "xtick.labelsize": 10, "ytick.labelsize": 10,
    "legend.frameon": False, "figure.facecolor": "white", "axes.facecolor": "white",
})


def canvas(title: str, sub: str = ""):
    """One chart, centred, titled with the name of the chart."""
    fig, ax = plt.subplots(figsize=(8.6, 6.2))
    fig.subplots_adjust(left=0.115, right=0.97, top=0.845, bottom=0.115)
    fig.text(0.012, 0.975, title, ha="left", va="top", fontsize=17, fontweight="bold", color=INK)
    if sub:
        fig.text(0.012, 0.917, sub, ha="left", va="top", fontsize=10.5, color=MUTED)
    fig.text(0.012, 0.018, FOOT, ha="left", va="bottom", fontsize=8.5, color=MUTED)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    ax.set_axisbelow(True)
    return fig, ax


def save(fig, name: str):
    fig.savefig(OUT / name, bbox_inches="tight", pad_inches=0.25)
    plt.close(fig)
    print(f"{OUT / name}")


def load():
    curves = json.loads((EXPORTS / "curves.json").read_text())
    conf = json.loads((EXPORTS / "confusion.json").read_text())["operating_points"]
    card = json.loads((EXPORTS / "model_card.json").read_text(encoding="utf-8"))
    return curves, conf, card


# ---------------------------------------------------------------- 1. ROC
def roc(curves):
    fig, ax = canvas("ROC curves", "Week 1, all three events, against the random-guess diagonal")
    ax.plot([0, 1], [0, 1], color=GREY, lw=1.2, ls=(0, (4, 3)), zorder=1)
    for key, ev in curves["events"].items():
        w = ev["weeks"]["W1"]
        ax.plot(w["roc"]["fpr"], w["roc"]["tpr"], color=EVENT_COLOR[key], lw=3, zorder=3,
                label=f"{ev['label']}      AUC {w['auc']:.3f}")
    ax.set_xlim(0, 1); ax.set_ylim(0, 1)
    ax.xaxis.set_major_formatter(PercentFormatter(1.0, decimals=0))
    ax.yaxis.set_major_formatter(PercentFormatter(1.0, decimals=0))
    ax.set_xlabel("False positive rate")
    ax.set_ylabel("True positive rate")
    ax.legend(loc="lower right", fontsize=11.5, labelcolor=INK, handlelength=1.8,
              borderaxespad=1.0, labelspacing=0.7)
    save(fig, "perf_roc.png")


# ---------------------------------------------------------------- 2. precision-recall
def pr(curves, conf):
    fig, ax = canvas("Precision-recall curves",
                     "Week 1. The dotted line in each colour is that event's base rate")
    ops = {(r["event"], r["week"], r["operating_point"]): r for r in conf}
    for key, ev in curves["events"].items():
        w = ev["weeks"]["W1"]
        c = EVENT_COLOR[key]
        ax.axhline(w["base_rate"], color=c, lw=1, ls=(0, (2, 3)), alpha=0.55, zorder=1)
        ax.plot(w["pr"]["recall"], w["pr"]["precision"], color=c, lw=3, zorder=3,
                label=f"{ev['label']}      AP {w['ap']:.3f}")
    r = ops.get(("dry10", 1, "advisory: p>=0.50 and departure>=0.12"))
    if r:
        ax.plot([r["recall"]], [r["precision"]], "o", ms=9, color=BLUE, mec="white", mew=2, zorder=5)
        ax.annotate("where an advisory is issued", (r["recall"], r["precision"]),
                    textcoords="offset points", xytext=(26, -34), fontsize=10.5, color=INK,
                    arrowprops=dict(arrowstyle="-", color=BLUE, lw=1, alpha=0.7, shrinkB=8))
    ax.set_xlim(0, 1); ax.set_ylim(0, 1)
    ax.xaxis.set_major_formatter(PercentFormatter(1.0, decimals=0))
    ax.yaxis.set_major_formatter(PercentFormatter(1.0, decimals=0))
    ax.set_xlabel("Recall")
    ax.set_ylabel("Precision")
    ax.legend(loc="lower left", fontsize=11.5, labelcolor=INK, handlelength=1.8,
              bbox_to_anchor=(0.02, 0.16), labelspacing=0.7)
    save(fig, "perf_pr.png")


# ---------------------------------------------------------------- 3. reliability
def reliability(curves):
    fig, ax = canvas("Reliability diagram",
                     "Week 1. A perfectly calibrated forecast sits on the diagonal")
    ax.plot([0, 1], [0, 1], color=GREY, lw=1.2, ls=(0, (4, 3)), zorder=1)
    for key, ev in curves["events"].items():
        w = ev["weeks"]["W1"]
        rel = w["reliability"]
        f = [x for x, n in zip(rel["forecast"], rel["count"]) if n > 0]
        o = [x for x, n in zip(rel["observed"], rel["count"]) if n > 0]
        n = [x for x in rel["count"] if x > 0]
        err = sum(ni * abs(fi - oi) for fi, oi, ni in zip(f, o, n)) / sum(n)
        ax.plot(f, o, color=EVENT_COLOR[key], lw=2.6, marker="o", ms=5.5, mec="white", mew=1.2,
                zorder=3, label=f"{ev['label']}      error {err * 100:.2f} pts")
    ax.set_xlim(0, 1); ax.set_ylim(0, 1)
    ax.xaxis.set_major_formatter(PercentFormatter(1.0, decimals=0))
    ax.yaxis.set_major_formatter(PercentFormatter(1.0, decimals=0))
    ax.set_xlabel("Forecast probability")
    ax.set_ylabel("Observed frequency")
    ax.legend(loc="upper left", fontsize=11.5, labelcolor=INK, handlelength=1.8,
              borderaxespad=1.0, labelspacing=0.7)
    save(fig, "perf_reliability.png")


# ---------------------------------------------------------------- 4. the matrix
def matrix(card):
    order = ["dry10", "dry7", "onset", "heavy"]
    rows = [(k, card["matrix"][k]) for k in order if k in card["matrix"]]
    fig, ax = plt.subplots(figsize=(8.8, 4.9))
    fig.subplots_adjust(left=0.235, right=0.985, top=0.80, bottom=0.14)
    fig.text(0.012, 0.975, "Performance matrix", ha="left", va="top", fontsize=17,
             fontweight="bold", color=INK)
    fig.text(0.012, 0.905, "Area under the ROC curve, every event at every lead week",
             ha="left", va="top", fontsize=10.5, color=MUTED)
    fig.text(0.012, 0.012, FOOT, ha="left", va="bottom", fontsize=8.5, color=MUTED)

    cmap = LinearSegmentedColormap.from_list("auc", ["#eef3f8", "#9dc0e0", "#1f5fa8"])
    grid = [[w["auc"] for w in m["weeks"]] for _, m in rows]
    im = ax.imshow(grid, cmap=cmap, vmin=0.70, vmax=0.95, aspect="auto")
    ax.set_xticks(range(4), [f"Week {i + 1}" for i in range(4)], fontsize=11, color=INK)
    ax.set_yticks(range(len(rows)), [m["label"] for _, m in rows], fontsize=11, color=INK)
    ax.tick_params(length=0)
    for s in ax.spines.values():
        s.set_visible(False)
    ax.grid(False)
    for i, row in enumerate(grid):
        for j, v in enumerate(row):
            ax.text(j, i, f"{v:.3f}", ha="center", va="center", fontsize=13,
                    color="white" if v > 0.87 else INK,
                    fontweight="bold" if v >= 0.90 else "normal")
    cb = fig.colorbar(im, ax=ax, fraction=0.035, pad=0.02)
    cb.outline.set_visible(False)
    cb.ax.tick_params(length=0, labelsize=9, colors=MUTED)
    cb.set_label("AUC", color=MUTED, fontsize=9.5)
    save(fig, "perf_matrix.png")


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    curves, conf, card = load()
    roc(curves)
    pr(curves, conf)
    reliability(curves)
    matrix(card)


if __name__ == "__main__":
    main()
