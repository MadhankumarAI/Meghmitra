"""Figure 4 - Stated chance vs. what actually happened, per advice type.

The y-axis values are the same "where we sent the advice" hit rates as figure 3.
The x-axis values (the mean probability the system stated for each advice type)
are not printed on the source chart, so they are read off its point positions.
"""

import numpy as np
import matplotlib.pyplot as plt

import vizstyle as vs

# label, stated chance (%), what actually happened (%), n, label offset (pts)
POINTS = [
    ("Protect against heavy rain", 25.0, 32.7,   906, (14, -14), "left"),
    ("Sow now",                    51.5, 68.1, 10874, (12, -20), "left"),
    ("Prepare irrigation",         63.5, 74.8, 14617, (10, -30), "left"),
    ("Conserve soil moisture",     71.0, 79.3, 91252, (14,  -4), "left"),
    ("Wait to sow",                77.5, 86.4, 28482, (10,  12), "left"),
]


def main():
    vs.use_style()
    fig, ax = plt.subplots(figsize=(8.4, 6.6))
    fig.subplots_adjust(top=0.865, bottom=0.11, left=0.12, right=0.97)

    x = np.array([p[1] for p in POINTS])
    y = np.array([p[2] for p in POINTS])

    # smooth guide through the origin: y = a*x + b*x^2
    design = np.vstack([x, x ** 2]).T
    a, b = np.linalg.lstsq(design, y, rcond=None)[0]
    xs = np.linspace(0, 100, 300)
    ax.plot(xs, a * xs + b * xs ** 2, ls=(0, (5, 4)), lw=1.4,
            color=vs.INK_3, zorder=2)

    ax.scatter(x, y, s=120, color=vs.BLUE, edgecolor=vs.SURFACE,
               linewidth=1.8, zorder=4)

    for label, px, py, n, offset, ha in POINTS:
        ax.annotate(f"{label}\n({n:,})", (px, py), xytext=offset,
                    textcoords="offset points", ha=ha, va="center",
                    fontsize=11, color=vs.INK, linespacing=1.35)

    ax.set_xlim(0, 100)
    ax.set_ylim(0, 100)
    ax.set_xticks(np.arange(0, 101, 20))
    ax.set_yticks(np.arange(0, 101, 20))
    ax.set_xlabel("Chance the system stated (%)")
    ax.set_ylabel("What actually happened (%)")
    ax.grid(True, zorder=0)
    ax.set_axisbelow(True)
    vs.despine(ax)

    vs.title_block(fig, "Are the advice's own numbers honest?",
                   "Scored only on years the model never saw "
                   "(1991-2025, five held-out blocks of seven years).",
                   y_title=0.985, y_sub=0.930, sub_size=10.8)
    fig.savefig("figures/fig4_advice_honesty.png")
    print("wrote figures/fig4_advice_honesty.png")


if __name__ == "__main__":
    main()
