"""Figure 2 - Reliability diagram plus the forecast-probability histogram."""

import numpy as np
import matplotlib.pyplot as plt

import vizstyle as vs

BIN_CENTRE = np.array([0.05, 0.15, 0.25, 0.35, 0.45, 0.55, 0.65, 0.75, 0.85, 0.95])
OBSERVED = np.array([0.040, 0.155, 0.260, 0.350, 0.450, 0.535,
                     0.635, 0.730, 0.830, 0.920])
COUNTS_M = np.array([38.2, 20.7, 15.6, 13.4, 11.9, 10.2, 9.1, 8.7, 10.1, 12.3])


def main():
    vs.use_style()
    fig, (ax, axh) = plt.subplots(
        2, 1, figsize=(8.0, 7.6), sharex=True,
        gridspec_kw={"height_ratios": [3.1, 1.0], "hspace": 0.10})
    fig.subplots_adjust(top=0.845, bottom=0.09, left=0.15, right=0.96)

    # --- reliability -----------------------------------------------------
    ax.plot([0, 1], [0, 1], ls=(0, (5, 4)), lw=1.4, color=vs.INK_3, zorder=2)
    ax.annotate("perfect", (0.955, 0.955), xytext=(-4, 8),
                textcoords="offset points", ha="right", va="bottom",
                rotation=45, rotation_mode="anchor", fontsize=10.5,
                color=vs.INK_3)

    ax.plot(BIN_CENTRE, OBSERVED, lw=2.0, color=vs.BLUE, marker="o",
            markersize=7, markerfacecolor=vs.BLUE,
            markeredgecolor=vs.SURFACE, markeredgewidth=1.6, zorder=4)

    ax.set_xlim(-0.02, 1.02)
    ax.set_ylim(-0.02, 1.02)
    ax.set_xticks(np.arange(0, 1.01, 0.2))
    ax.set_yticks(np.arange(0, 1.01, 0.2))
    ax.set_ylabel("Observed frequency")
    ax.grid(True, zorder=0)
    ax.set_axisbelow(True)
    vs.despine(ax)

    ax.text(0.03, 0.965, "Weighted reliability error 0.28%.\nNo calibration layer.",
            transform=ax.transAxes, ha="left", va="top", fontsize=11,
            color=vs.INK, linespacing=1.5)

    # --- sharpness histogram --------------------------------------------
    bars = axh.bar(BIN_CENTRE, COUNTS_M, width=0.088, color="#c6d9f2",
                   edgecolor=vs.BLUE, linewidth=1.0, zorder=3)
    for bar, value in zip(bars, COUNTS_M):
        axh.annotate(f"{value:.1f}",
                     (bar.get_x() + bar.get_width() / 2, value),
                     xytext=(0, 3), textcoords="offset points",
                     ha="center", va="bottom", fontsize=9, color=vs.INK_2)

    axh.set_ylim(0, 60)
    axh.set_yticks([0, 20, 40, 60])
    axh.set_ylabel("Forecasts\n(millions)", fontsize=10.5, linespacing=1.4)
    axh.set_xlabel("Forecast probability")
    axh.yaxis.grid(True, zorder=0)
    axh.set_axisbelow(True)
    vs.despine(axh)

    vs.title_block(fig, "Does 70% mean 70%?",
                   vs.HELD_OUT + "\n10+ day dry spell",
                   y_title=0.985, y_sub=0.944)
    fig.savefig("figures/fig2_reliability.png")
    print("wrote figures/fig2_reliability.png")


if __name__ == "__main__":
    main()
