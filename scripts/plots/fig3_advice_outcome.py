"""Figure 3 - Did the advice come true? Advisory cells vs. all monsoon blocks."""

import numpy as np
import matplotlib.pyplot as plt

import vizstyle as vs

LABELS = ["Wait to sow", "Conserve soil\nmoisture", "Prepare\nirrigation",
          "Sow now", "Protect against\nheavy rain"]
ADVISED = [86.4, 79.3, 74.8, 68.1, 32.7]
BASELINE = [47.4, 39.7, 35.8, 23.1, 10.1]
N = [28482, 91252, 14617, 10874, 906]


def main():
    vs.use_style()
    fig, ax = plt.subplots(figsize=(9.4, 6.2))
    fig.subplots_adjust(top=0.745, bottom=0.11, left=0.20, right=0.84)

    y = np.arange(len(LABELS))[::-1]
    height = 0.36

    b1 = ax.barh(y + height / 2, ADVISED, height * 0.92, color=vs.BLUE,
                 edgecolor=vs.SURFACE, linewidth=1.2, zorder=3,
                 label="where we sent the advice")
    b2 = ax.barh(y - height / 2, BASELINE, height * 0.92, color=vs.GRAY,
                 edgecolor=vs.SURFACE, linewidth=1.2, zorder=3,
                 label="all monsoon blocks that day")

    for bars, values, colour in ((b1, ADVISED, vs.BLUE),
                                 (b2, BASELINE, vs.GRAY_DARK)):
        for bar, value in zip(bars, values):
            ax.annotate(f"{value:.1f}%",
                        (value, bar.get_y() + bar.get_height() / 2),
                        xytext=(5, 0), textcoords="offset points",
                        ha="left", va="center", fontsize=10.5, color=colour,
                        fontweight="bold")

    for yi, n in zip(y, N):
        ax.annotate(f"(n = {n:,})", (103.5, yi), xycoords=("data", "data"),
                    ha="left", va="center", fontsize=10.5, color=vs.INK_3,
                    annotation_clip=False)

    ax.set_yticks(y)
    ax.set_yticklabels(LABELS, fontsize=11.5, linespacing=1.3)
    ax.set_xlim(0, 100)
    ax.set_xticks(np.arange(0, 101, 20))
    ax.set_xlabel("Percentage of cases (%)")
    ax.xaxis.grid(True, zorder=0)
    ax.set_axisbelow(True)
    vs.despine(ax)
    ax.tick_params(axis="y", length=0)

    ax.legend(loc="lower left", bbox_to_anchor=(0.0, 1.04), ncol=2,
              handlelength=1.2, handleheight=1.1, columnspacing=1.6)

    vs.title_block(fig, "Did the advice come true?",
                   vs.HELD_OUT + "\n2023 replay, a year the model never saw.",
                   y_title=0.985, y_sub=0.930)
    fig.savefig("figures/fig3_advice_outcome.png")
    print("wrote figures/fig3_advice_outcome.png")


if __name__ == "__main__":
    main()
