"""One-chart overview: the TCG market overall.

Composite = equal-weight geometric mean of the 10 games' median fixed-basket
indices, chain-linked month over month so games that launched after Feb 2024
join the composite without distorting the base. Equal weighting keeps Magic's
huge catalog from swamping the read; the light lines behind show each game.
"""
import sys
from datetime import date
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from tcg_config import CATEGORIES, CATEGORY_ORDER

MONTHLY = Path(sys.argv[1])
CATALOG = Path(sys.argv[2])
OUTPUT = Path(sys.argv[3]) if len(sys.argv) > 3 else Path("output")
OUTPUT.mkdir(parents=True, exist_ok=True)
MIN_BASE_ROWS = 50

INK = "#0b0b0b"
INK2 = "#52514e"
MUTED = "#898781"
GRID = "#e1e0d9"
BASELINE = "#c3c2b7"
SURFACE = "#fcfcfb"
C_SINGLES = "#2a78d6"
C_SEALED = "#008300"
C_CONTEXT = "#b9b8b0"

# ------------------------------------------------- per-game median indices
months = sorted(p.stem.replace("prices_", "") for p in MONTHLY.glob("prices_*.parquet"))
frames = []
for m in months:
    df = pd.read_parquet(MONTHLY / f"prices_{m}.parquet")
    df["month"] = m
    frames.append(df)
prices = pd.concat(frames, ignore_index=True)
prices["subTypeName"] = prices["subTypeName"].fillna("")
catalog = pd.concat(
    [pd.read_parquet(CATALOG / f"products_{c}.parquet") for c in CATEGORY_ORDER],
    ignore_index=True,
)[["productId", "isSingle"]]
prices = prices.merge(catalog, on="productId", how="inner")
prices["segment"] = np.where(prices["isSingle"], "singles", "sealed")

wide = prices.pivot_table(
    index=["categoryId", "segment", "productId", "subTypeName"],
    columns="month", values="marketPrice", aggfunc="first")

game_total, game_seg = {}, {"singles": {}, "sealed": {}}
for cat in CATEGORY_ORDER:
    cat_wide = wide.loc[wide.index.get_level_values("categoryId") == cat]
    counts = cat_wide.notna().sum()
    live = [m for m in months if counts.get(m, 0) >= MIN_BASE_ROWS]
    if not live:
        continue
    sub = cat_wide[live].dropna()
    sub = sub[sub[live[0]] > 0]
    rel = sub.div(sub[live[0]], axis=0) * 100.0
    game_total[cat] = rel.median().reindex(months)
    for seg in ("singles", "sealed"):
        grp = rel.loc[rel.index.get_level_values("segment") == seg]
        if len(grp):
            game_seg[seg][cat] = grp.median().reindex(months)


def chain_composite(indices):
    """Equal-weight, chain-linked geometric-mean composite (base 100)."""
    vals = [100.0]
    for prev, cur in zip(months, months[1:]):
        growths = [s[cur] / s[prev] for s in indices.values()
                   if pd.notna(s.get(prev)) and pd.notna(s.get(cur))]
        vals.append(vals[-1] * float(np.exp(np.mean(np.log(growths)))))
    return pd.Series(vals, index=months)


comp_all = chain_composite(game_total)
comp_seg = {seg: chain_composite(game_seg[seg]) for seg in ("singles", "sealed")}

span_years = (date(2026, 7, 1) - date(2024, 2, 8)).days / 365.25
for name, s in [("Market", comp_all), ("Singles", comp_seg["singles"]),
                ("Sealed", comp_seg["sealed"])]:
    print(f"{name} composite: final {s.iloc[-1]:.1f}, "
          f"CAGR {((s.iloc[-1] / 100) ** (1 / span_years) - 1) * 100:+.1f}%/yr")

# ------------------------------------------------------------------ chart
dates = pd.to_datetime([m + "-01" for m in months])
fig, ax = plt.subplots(figsize=(11.5, 6.6), dpi=200, facecolor=SURFACE)
fig.subplots_adjust(left=0.075, right=0.90, top=0.80, bottom=0.11)
ax.set_facecolor(SURFACE)

for cat, s in game_total.items():
    ax.plot(dates, s.values, color=C_CONTEXT, lw=1, alpha=0.85, zorder=1)
# name only the outlier context lines
extremes = sorted(game_total, key=lambda c: game_total[c].iloc[-1])
for cat in (extremes[0], extremes[-1]):
    s = game_total[cat]
    ax.annotate(CATEGORIES[cat][0], (dates[-1], s.iloc[-1]),
                xytext=(5, 0), textcoords="offset points", va="center",
                fontsize=8, color=MUTED)

lines = [(comp_seg["singles"], C_SINGLES, 1.8, "Singles"),
         (comp_seg["sealed"], C_SEALED, 1.8, "Sealed"),
         (comp_all, INK, 2.6, "All products")]
# dodge end labels apart in log space (the composites end close together)
order = sorted(range(len(lines)), key=lambda i: lines[i][0].iloc[-1])
label_y = [lines[i][0].iloc[-1] for i in order]
for j in range(1, len(label_y)):
    label_y[j] = max(label_y[j], label_y[j - 1] * 1.09)
label_pos = dict(zip(order, label_y))
for i, (s, color, lw, label) in enumerate(lines):
    ax.plot(dates, s.values, color=color, lw=lw, zorder=3,
            solid_capstyle="round")
    ax.annotate(f"{label}  {s.iloc[-1]:.0f}", (dates[-1], label_pos[i]),
                xytext=(8, 0), textcoords="offset points", va="center",
                fontsize=10, fontweight="bold", color=color)

ax.set_yscale("log")
ax.set_ylim(28, 230)
ax.yaxis.set_major_locator(matplotlib.ticker.FixedLocator([50, 100, 200]))
ax.yaxis.set_major_formatter(matplotlib.ticker.FixedFormatter(["50", "100", "200"]))
ax.yaxis.set_minor_locator(matplotlib.ticker.NullLocator())
ax.axhline(100, color=BASELINE, lw=1, zorder=2)
ax.grid(axis="y", color=GRID, lw=0.7)
for spine in ("top", "right", "left"):
    ax.spines[spine].set_visible(False)
ax.spines["bottom"].set_color(BASELINE)
ax.tick_params(colors=MUTED, labelsize=9.5)
ax.xaxis.set_major_locator(mdates.MonthLocator(interval=4))
ax.xaxis.set_major_formatter(mdates.DateFormatter("%b %y"))
ax.set_xlim(dates[0], dates[-1] + pd.Timedelta(days=40))
ax.set_ylabel("Price index (Feb 2024 = 100, log scale)", fontsize=10, color=INK2)

fig.suptitle("The TCG market overall: composite fixed-basket price index",
             x=0.075, y=0.955, ha="left", fontsize=16, fontweight="bold",
             color=INK)
fig.text(0.075, 0.885,
         "Equal-weight composite of the top-10 games' median fixed-basket "
         "indices, chain-linked monthly; gray lines show individual games",
         fontsize=10.5, color=INK2)
fig.text(0.075, 0.025,
         "TCGplayer market prices via TCGCSV; fixed basket; price trend, not "
         "sales volume. Monthly snapshots Feb 2024 – Jul 2026.\nGames launched "
         "after Feb 2024 join the composite from their second sampled month.",
         fontsize=8, color=MUTED, linespacing=1.5)
fig.savefig(OUTPUT / "tcg_market_overview.png", facecolor=SURFACE)
fig.savefig(OUTPUT / "tcg_market_overview.svg", facecolor=SURFACE)
print(f"chart -> {OUTPUT}/tcg_market_overview.png|.svg")

# append composite series to the workbook
out = pd.DataFrame({
    "month": months,
    "market_composite": comp_all.values,
    "singles_composite": comp_seg["singles"].values,
    "sealed_composite": comp_seg["sealed"].values,
})
xlsx = OUTPUT / "tcg_price_trends.xlsx"
if xlsx.exists():
    with pd.ExcelWriter(xlsx, mode="a", engine="openpyxl",
                        if_sheet_exists="replace") as writer:
        out.to_excel(writer, sheet_name="Market composite", index=False)
    print("composite sheet appended to workbook")
