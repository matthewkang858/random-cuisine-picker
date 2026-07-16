"""One-chart overview: the TCG market overall.

Headline series is GMV-WEIGHTED: within each game, the aggregate market
value of its fixed basket; across games, static weights from realized
TCGplayer GMV (client-provided 3-month sales summary — Magic 40%, Pokemon
32%, One Piece 13% of the top-10 total), chain-linked month over month so
games that launched after Feb 2024 join without distorting the base. The
equal-weight composite of game medians (the "typical game") is kept as a
dashed reference; gray lines show each game's own value index.
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

from tcg_config import CATEGORIES, CATEGORY_ORDER, GMV_3MO

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

# ------------------------------------------------------------- fixed baskets
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

# per (game, scope) basket VALUE by month (scope: all/singles/sealed),
# plus per-game median index for the equal-weight reference
value = {"all": {}, "singles": {}, "sealed": {}}
game_median = {}
for cat in CATEGORY_ORDER:
    cat_wide = wide.loc[wide.index.get_level_values("categoryId") == cat]
    counts = cat_wide.notna().sum()
    live = [m for m in months if counts.get(m, 0) >= MIN_BASE_ROWS]
    if not live:
        continue
    basket = cat_wide[live].dropna()
    basket = basket[basket[live[0]] > 0]
    value["all"][cat] = basket.sum().reindex(months)
    game_median[cat] = (basket.div(basket[live[0]], axis=0) * 100.0
                        ).median().reindex(months)
    for seg in ("singles", "sealed"):
        grp = basket.loc[basket.index.get_level_values("segment") == seg]
        if len(grp):
            value[seg][cat] = grp.sum().reindex(months)


def chain_value_index(values):
    """Chained GMV-weighted index (base 100): month-over-month growth is the
    GMV-weighted geometric mean of each game's basket-value growth, over the
    games live in both months (weights renormalized among them)."""
    vals = [100.0]
    for prev, cur in zip(months, months[1:]):
        num = den = 0.0
        for cat, v in values.items():
            if pd.notna(v.get(prev)) and pd.notna(v.get(cur)):
                w = GMV_3MO[cat]
                num += w * np.log(v[cur] / v[prev])
                den += w
        vals.append(vals[-1] * (np.exp(num / den) if den else 1.0))
    return pd.Series(vals, index=months)


def chain_equal_weight(indices):
    vals = [100.0]
    for prev, cur in zip(months, months[1:]):
        growths = [s[cur] / s[prev] for s in indices.values()
                   if pd.notna(s.get(prev)) and pd.notna(s.get(cur))]
        vals.append(vals[-1] * float(np.exp(np.mean(np.log(growths)))))
    return pd.Series(vals, index=months)


comp = {scope: chain_value_index(value[scope])
        for scope in ("all", "singles", "sealed")}
comp_ew = chain_equal_weight(game_median)

span_years = (date(2026, 7, 1) - date(2024, 2, 8)).days / 365.25
for name, s in [("Market (GMV-wt)", comp["all"]),
                ("Singles (GMV-wt)", comp["singles"]),
                ("Sealed (GMV-wt)", comp["sealed"]),
                ("Equal-weight typical game", comp_ew)]:
    print(f"{name}: final {s.iloc[-1]:.1f}, "
          f"CAGR {((s.iloc[-1] / 100) ** (1 / span_years) - 1) * 100:+.1f}%/yr")
gmv_total = sum(GMV_3MO.values())
for cat in sorted(GMV_3MO, key=GMV_3MO.get, reverse=True):
    print(f"  weight {CATEGORIES[cat][0]}: {GMV_3MO[cat] / gmv_total:.1%}")

# ------------------------------------------------------------------ chart
dates = pd.to_datetime([m + "-01" for m in months])
fig, ax = plt.subplots(figsize=(11.5, 6.6), dpi=200, facecolor=SURFACE)
fig.subplots_adjust(left=0.075, right=0.86, top=0.80, bottom=0.13)
ax.set_facecolor(SURFACE)

game_value_idx = {}
for cat, v in value["all"].items():
    lv = v.dropna()
    game_value_idx[cat] = lv / lv.iloc[0] * 100.0
    ax.plot(pd.to_datetime([m + "-01" for m in lv.index]),
            game_value_idx[cat].values, color=C_CONTEXT, lw=1, alpha=0.85,
            zorder=1)
extremes = sorted(game_value_idx, key=lambda c: game_value_idx[c].iloc[-1])
for cat in (extremes[0], extremes[-1]):
    s = game_value_idx[cat]
    ax.annotate(CATEGORIES[cat][0], (dates[-1], s.iloc[-1]),
                xytext=(5, 0), textcoords="offset points", va="center",
                fontsize=8, color=MUTED)

ax.plot(dates, comp_ew.values, color=MUTED, lw=1.4, ls=(0, (4, 3)), zorder=2)

lines = [(comp["singles"], C_SINGLES, 1.8, "Singles"),
         (comp["sealed"], C_SEALED, 1.8, "Sealed"),
         (comp["all"], INK, 2.6, "Market"),
         (comp_ew, MUTED, 0, "Equal-weight")]   # lw 0: line already drawn
order = sorted(range(len(lines)), key=lambda i: lines[i][0].iloc[-1])
label_y = [lines[i][0].iloc[-1] for i in order]
for j in range(1, len(label_y)):
    label_y[j] = max(label_y[j], label_y[j - 1] * 1.09)
label_pos = dict(zip(order, label_y))
for i, (s, color, lw, label) in enumerate(lines):
    if lw:
        ax.plot(dates, s.values, color=color, lw=lw, zorder=3,
                solid_capstyle="round")
    ax.annotate(f"{label}  {s.iloc[-1]:.0f}", (dates[-1], label_pos[i]),
                xytext=(8, 0), textcoords="offset points", va="center",
                fontsize=9.5, fontweight="bold", color=color)

ax.set_yscale("log")
ax.set_ylim(30, 400)
ax.yaxis.set_major_locator(matplotlib.ticker.FixedLocator([50, 100, 200, 400]))
ax.yaxis.set_major_formatter(matplotlib.ticker.FixedFormatter(
    ["50", "100", "200", "400"]))
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

fig.suptitle("The TCG market overall: GMV-weighted fixed-basket price index",
             x=0.075, y=0.97, ha="left", fontsize=16, fontweight="bold",
             color=INK)
fig.text(0.075, 0.915,
         "Games weighted by realized TCGplayer sales (3-mo GMV): Magic 40%, "
         "Pokemon 32%, One Piece 13%, Yu-Gi-Oh 7%.\nDashed: equal-weight "
         "median of the 10 games (the typical game). Gray: individual games' "
         "value indices.",
         fontsize=10, color=INK2, linespacing=1.6, va="top")
fig.text(0.075, 0.025,
         "TCGplayer market prices via TCGCSV; fixed basket; price trend, not "
         "sales volume. Monthly snapshots Feb 2024 – Jul 2026.\nCross-game "
         "weights: realized TCGplayer GMV, ~3-mo window ending Jul 2026 "
         "(static). Games launched after Feb 2024 join from their second "
         "sampled month.",
         fontsize=8, color=MUTED, linespacing=1.5)
fig.savefig(OUTPUT / "tcg_market_overview.png", facecolor=SURFACE)
fig.savefig(OUTPUT / "tcg_market_overview.svg", facecolor=SURFACE)
print(f"chart -> {OUTPUT}/tcg_market_overview.png|.svg")

out = pd.DataFrame({
    "month": months,
    "market_gmv_weighted": comp["all"].values,
    "singles_gmv_weighted": comp["singles"].values,
    "sealed_gmv_weighted": comp["sealed"].values,
    "equal_weight_typical_game": comp_ew.values,
})
xlsx = OUTPUT / "tcg_price_trends.xlsx"
if xlsx.exists():
    with pd.ExcelWriter(xlsx, mode="a", engine="openpyxl",
                        if_sheet_exists="replace") as writer:
        out.to_excel(writer, sheet_name="Market composite", index=False)
    print("composite sheet updated in workbook")
