"""Deck-style single chart: sealed product price trends by TCG.

Reads output/tcg_monthly_sealed.tsv (decimal fractions, 0 = base month) and
renders the six-game line chart with direct end labels. Riftbound's
pre-launch zeros are masked so its line starts at launch.
"""
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import numpy as np
import pandas as pd

OUTPUT = Path("output")
INK = "#0b0b0b"
INK2 = "#52514e"
MUTED = "#898781"
GRID = "#e1e0d9"
BASELINE = "#c3c2b7"
SURFACE = "#fcfcfb"
# validated categorical slots, assigned in fixed order
COLORS = {
    "Pokemon": "#2a78d6", "One Piece": "#008300", "Magic": "#e87ba4",
    "Riftbound": "#eda100", "Yu-Gi-Oh": "#1baf7a", "Lorcana": "#eb6834",
}
LAUNCH = {"Riftbound": "2025-11"}

df = pd.read_csv(OUTPUT / "tcg_monthly_sealed.tsv", sep="\t", index_col=0)
dates = pd.to_datetime(df.index, format="%b %Y")
month_keys = dates.strftime("%Y-%m")

fig, ax = plt.subplots(figsize=(11.5, 6.4), dpi=200, facecolor=SURFACE)
fig.subplots_adjust(left=0.075, right=0.80, top=0.80, bottom=0.10)
ax.set_facecolor(SURFACE)

order = df.iloc[-1].sort_values(ascending=False).index
ends = {}
for game in order:
    s = df[game].copy()
    if game in LAUNCH:  # mask pre-launch zeros so the line starts at launch
        s[month_keys < LAUNCH[game]] = np.nan
    ax.plot(dates, s.values, color=COLORS[game], lw=2.2, zorder=3,
            solid_capstyle="round")
    ends[game] = s.iloc[-1]

# dodge end labels (linear space)
lab = sorted(ends.items(), key=lambda kv: kv[1])
ys = [v for _, v in lab]
for i in range(1, len(ys)):
    ys[i] = max(ys[i], ys[i - 1] + 0.135)
for (game, val), y in zip(lab, ys):
    pct = f"{val * 100:+.1f}%" if abs(val) < 0.995 else f"{val * 100:+.0f}%"
    label = f"{pct}  {game}"
    if game in LAUNCH:
        label += "*"
    ax.annotate(label, (dates[-1], y), xytext=(10, 0),
                textcoords="offset points", va="center", fontsize=11,
                fontweight="bold", color=COLORS[game],
                annotation_clip=False)

ax.axhline(0, color=INK, lw=1.2, zorder=2)
ax.set_ylim(-0.35, 2.35)
ax.yaxis.set_major_formatter(mticker.PercentFormatter(xmax=1, decimals=0))
ax.yaxis.set_major_locator(mticker.MultipleLocator(0.5))
ax.grid(axis="y", color=GRID, lw=0.7)
for spine in ("top", "right", "left"):
    ax.spines[spine].set_visible(False)
ax.spines["bottom"].set_color(BASELINE)
ax.tick_params(colors=MUTED, labelsize=10)
ax.xaxis.set_major_locator(matplotlib.dates.MonthLocator(bymonth=(2, 8)))
ax.xaxis.set_major_formatter(matplotlib.dates.DateFormatter("%b %Y"))
ax.set_xlim(dates[0], dates[-1])

fig.suptitle("Sealed product price trends by TCG, TCGplayer marketplace, "
             "Feb 2024 – Jul 2026,",
             x=0.075, y=0.955, ha="left", fontsize=14.5, fontweight="bold",
             color=INK)
fig.text(0.075, 0.895, "% change in median market price of fixed product basket",
         fontsize=14.5, fontweight="bold", color=INK)
fig.text(0.075, 0.845,
         "*Riftbound measured from its Nov 2025 launch",
         fontsize=9.5, color=INK2)
fig.text(0.075, 0.022,
         "TCGplayer market prices via TCGCSV; fixed basket; price trend, not "
         "sales volume. Monthly snapshots, latest Jul 27, 2026.",
         fontsize=8, color=MUTED)
fig.savefig(OUTPUT / "tcg_sealed_trends.png", facecolor=SURFACE)
fig.savefig(OUTPUT / "tcg_sealed_trends.svg", facecolor=SURFACE)
print("chart -> output/tcg_sealed_trends.png|.svg")
for g in order:
    print(f"  {g}: {ends[g] * 100:+.1f}%")
