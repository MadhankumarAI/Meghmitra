"""Figure 1 - Brier Skill Score by lead week, for each advisory target."""

import numpy as np
import matplotlib.pyplot as plt

import vizstyle as vs

WEEKS = ["Week 1", "Week 2", "Week 3", "Week 4"]

SERIES = [
    ("10+ day dry spell", [0.248, 0.082, 0.047, 0.021], vs.BLUE),
    ("7+ day dry spell",  [0.218, 0.061, 0.034, 0.015], vs.ORANGE),
    ("Monsoon onset",     [0.181, 0.045, 0.022, 0.008], vs.AQUA),
    ("Heavy-rain day",    [0.058, 0.021, 0.011, 0.004], vs.RED),
]


def main():
    vs.use_style()
    fig, ax = plt.subplots(figsize=(9.2, 6.0))
    fig.subplots_adjust(top=0.78, bottom=0.10, left=0.11, right=0.97)

    x = np.arange(len(WEEKS))
    width = 0.20
    offsets = (np.arange(len(SERIES)) - (len(SERIES) - 1) / 2) * width

    for (label, values, colour), off in zip(SERIES, offsets):
        bars = ax.bar(x + off, values, width * 0.90, label=label,
                      color=colour, edgecolor=vs.SURFACE, linewidth=1.2,
                      zorder=3)
        for bar, value in zip(bars, values):
            ax.annotate(f"{value:.3f}",
                        (bar.get_x() + bar.get_width() / 2, value),
                        xytext=(0, 3), textcoords="offset points",
                        ha="center", va="bottom", fontsize=8.6, color=vs.INK_2)

    ax.set_xticks(x)
    ax.set_xticklabels(WEEKS, fontsize=12)
    ax.set_ylabel("Brier Skill Score")
    ax.set_ylim(0, 0.275)
    ax.set_yticks(np.arange(0, 0.2501, 0.05))
    ax.yaxis.set_major_formatter(lambda v, _: f"{v:.2f}")
    ax.yaxis.grid(True, zorder=0)
    ax.set_axisbelow(True)
    vs.despine(ax)
    ax.tick_params(axis="x", length=0)

    ax.legend(loc="upper right", handlelength=1.1, handleheight=1.1,
              borderpad=0.2, labelspacing=0.55)

    vs.title_block(fig, "Skill by lead week", vs.HELD_OUT)
    fig.savefig("figures/fig1_skill_by_lead_week.png")
    print("wrote figures/fig1_skill_by_lead_week.png")


if __name__ == "__main__":
    main()
