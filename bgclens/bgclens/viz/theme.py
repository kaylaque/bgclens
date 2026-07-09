"""Publication-quality, colorblind-safe theme for BGCLens figures."""
import matplotlib.pyplot as plt
import matplotlib as mpl

# Okabe-Ito palette (colorblind-safe)
OKABE_ITO = [
    "#E69F00",  # orange
    "#56B4E9",  # sky blue
    "#009E73",  # bluish green
    "#F0E442",  # yellow
    "#0072B2",  # blue
    "#D55E00",  # vermilion
    "#CC79A7",  # reddish purple
    "#000000",  # black
]


def apply_theme(fig=None, ax=None):
    """Apply consistent publication theme to a figure/axes."""
    mpl.rcParams.update({
        "font.family": "DejaVu Sans",
        "font.size": 11,
        "axes.titlesize": 13,
        "axes.labelsize": 11,
        "xtick.labelsize": 9,
        "ytick.labelsize": 9,
        "axes.spines.top": False,
        "axes.spines.right": False,
        "axes.grid": True,
        "grid.alpha": 0.3,
        "grid.linewidth": 0.5,
        "figure.dpi": 150,
        "figure.facecolor": "white",
        "axes.facecolor": "white",
    })


def color_cycle(n: int) -> list[str]:
    """Return n colorblind-safe colors (cycling through Okabe-Ito)."""
    return [OKABE_ITO[i % len(OKABE_ITO)] for i in range(n)]
