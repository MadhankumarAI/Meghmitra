"""Shared plotting style for the forecast-evaluation figure set.

One place for the palette, fonts and axis furniture so all six figures read as
one system. Colours are the validated categorical slots (blue / orange / aqua /
red / violet), which stay separable under the common colour-vision deficiencies.
"""

import matplotlib as mpl
import matplotlib.pyplot as plt

# --- palette -------------------------------------------------------------
BLUE = "#2a78d6"
ORANGE = "#eb6834"
AQUA = "#1baf7a"
YELLOW = "#eda100"
VIOLET = "#4a3aa7"
RED = "#e34948"
GRAY = "#a3a199"          # neutral comparison series
GRAY_DARK = "#6f6d66"

INK = "#14181f"           # primary text
INK_2 = "#4d545e"         # secondary text
INK_3 = "#7b828c"         # muted text / annotations
GRID = "#e4e6e6"
SURFACE = "#ffffff"
TITLE = "#12263f"

SERIES = [BLUE, ORANGE, AQUA, RED, VIOLET]


def use_style():
    mpl.rcParams.update({
        "figure.facecolor": SURFACE,
        "savefig.facecolor": SURFACE,
        "axes.facecolor": SURFACE,
        "font.family": "DejaVu Sans",
        "font.size": 11,
        "text.color": INK,
        "axes.labelcolor": INK_2,
        "axes.edgecolor": "#c9ccce",
        "axes.linewidth": 0.9,
        "axes.labelsize": 12,
        "axes.titlesize": 13,
        "xtick.color": INK_2,
        "ytick.color": INK_2,
        "xtick.labelsize": 11,
        "ytick.labelsize": 11,
        "xtick.direction": "out",
        "ytick.direction": "out",
        "legend.frameon": False,
        "legend.fontsize": 10.5,
        "grid.color": GRID,
        "grid.linewidth": 0.9,
        "figure.dpi": 110,
        "savefig.dpi": 300,
        "savefig.bbox": "tight",
        "savefig.pad_inches": 0.28,
    })


def title_block(fig, title, subtitle, x=0.5, y_title=0.965, y_sub=0.912,
                ha="center", title_size=19, sub_size=11.5):
    """Bold headline plus a grey provenance line underneath it."""
    fig.text(x, y_title, title, ha=ha, va="top", fontsize=title_size,
             fontweight="bold", color=TITLE)
    fig.text(x, y_sub, subtitle, ha=ha, va="top", fontsize=sub_size,
             color=INK_2, linespacing=1.45)


def despine(ax, keep=("left", "bottom")):
    for side in ("top", "right", "left", "bottom"):
        ax.spines[side].set_visible(side in keep)


HELD_OUT = ("Scored only on years the model never saw (1991-2025,\n"
            "five held-out blocks of seven years).")
