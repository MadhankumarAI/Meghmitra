"""Figure 5 - Change in Brier Skill Score from adding the Indian Ocean Dipole."""

import numpy as np
import matplotlib.pyplot as plt

import vizstyle as vs

ROWS = [
    ("7+ day dry spell wk 1",   0.0021),
    ("7+ day dry spell wk 2",   0.0018),
    ("7+ day dry spell wk 3",   0.0014),
    ("7+ day dry spell wk 4",   0.0009),
    ("10+ day dry spell wk 1",  0.0034),
    ("10+ day dry spell wk 2",  0.0047),
    ("10+ day dry spell wk 3",  0.0039),
    ("10+ day dry spell wk 4",  0.0026),
    ("Heavy rain wk 1",         0.0012),
    ("Heavy rain wk 2",         0.0016),
    ("Heavy rain wk 3",         0.0011),
    ("Heavy rain wk 4",         0.0008),
    ("Monsoon onset wk 1",      0.0042),
    ("Monsoon onset wk 2",      0.0031),
    ("Monsoon onset wk 3",     -0.0009),
    ("Monsoon onset wk 4",     -0.0004),
]

MINUS = "\u2212"


def fmt(value):
    return f"{value:.4f}" if value >= 0 else f"{MINUS}{abs(value):.4f}"


def main():
    vs.use_style()
    fig, ax = plt.subplots(figsize=(8.8, 7.4))
    fig.subplots_adjust(top=0.845, bottom=0.135, left=0.26, right=0.97)

    labels = [r[0] for r in ROWS]
    values = np.array([r[1] for r in ROWS])
    y = np.arange(len(ROWS))[::-1]

    colours = [vs.AQUA if v >= 0 else vs.RED for v in values]
    ax.barh(y, values, 0.66, color=colours, edgecolor=vs.SURFACE,
            linewidth=1.0, zorder=3)

    for yi, value in zip(y, values):
        ax.annotate(fmt(value), (value, yi),
                    xytext=(6 if value >= 0 else -6, 0),
                    textcoords="offset points",
                    ha="left" if value >= 0 else "right", va="center",
                    fontsize=9.5, color=vs.INK_2)

    ax.axvline(0, color="#9aa0a6", lw=1.1, zorder=4)

    ax.set_yticks(y)
    ax.set_yticklabels(labels, fontsize=11)
    ax.set_ylim(-0.7, len(ROWS) - 0.3)
    ax.set_xlim(-0.005, 0.006)
    ax.set_xticks(np.arange(-0.004, 0.0061, 0.002))
    ax.xaxis.set_major_formatter(lambda v, _: fmt(v).replace("0.0", "0.0")
                                 if v else "0.000")
    ax.set_xlabel("Change in Brier Skill Score")
    ax.xaxis.grid(True, zorder=0)
    ax.set_axisbelow(True)
    vs.despine(ax, keep=("bottom",))
    ax.tick_params(axis="y", length=0)

    fig.text(0.5, 0.045,
             "Mean change +0.0019 BSS over 16 cells. "
             "Built, measured, left out.",
             ha="center", va="center", fontsize=10.5, color=vs.INK_2)

    vs.title_block(fig, "Adding the Indian Ocean Dipole",
                   "Scored only on years the model never saw "
                   "(1991-2025, five held-out blocks of seven years).",
                   y_title=0.985, y_sub=0.936, sub_size=10.8)
    fig.savefig("figures/fig5_iod_ablation.png")
    print("wrote figures/fig5_iod_ablation.png")


if __name__ == "__main__":
    main()
