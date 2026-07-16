"""Fixed-basket price-trend analysis and client exhibit.

Method (documented in the exhibit footnote):
- Basket per segment = (productId, subTypeName) pairs with a non-null
  marketPrice in EVERY sampled month (avoids mix-shift artifacts).
- Each basket product is indexed to 100 at its own Feb 2024 price; the
  segment series is the cross-product median of those relatives per month,
  with the IQR (25th-75th pct) as a dispersion band.
- Four segments: Pokemon singles, Pokemon sealed, MTG singles, MTG sealed.

Outputs (./output): exhibit PNG + SVG, tcg_price_trends.xlsx, and a printed
5-line findings summary.
"""
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

MONTHLY = Path(sys.argv[1])   # per-month price parquets
CATALOG = Path(sys.argv[2])   # catalog parquets
OUTPUT = Path(sys.argv[3]) if len(sys.argv) > 3 else Path("output")
OUTPUT.mkdir(parents=True, exist_ok=True)

GAMES = {1: "Magic: The Gathering", 3: "Pokemon"}
BASE_MONTH = "2024-02"
SCATTER_PER_GAME = 500
RNG = np.random.default_rng(20260716)

# Deck style (validated palette; see scripts/ dataviz notes)
INK = "#0b0b0b"
INK2 = "#52514e"
MUTED = "#898781"
GRID = "#e1e0d9"
BASELINE = "#c3c2b7"
SURFACE = "#fcfcfb"
C_SINGLES = "#2a78d6"
C_SEALED = "#008300"

# ---------------------------------------------------------------- load data
months = sorted(p.stem.replace("prices_", "") for p in MONTHLY.glob("prices_*.parquet"))
if BASE_MONTH not in months:
    sys.exit(f"base month {BASE_MONTH} missing from {MONTHLY}")
print(f"{len(months)} months: {months[0]} .. {months[-1]}")

frames = []
for m in months:
    df = pd.read_parquet(MONTHLY / f"prices_{m}.parquet")
    df["month"] = m
    frames.append(df)
prices = pd.concat(frames, ignore_index=True)
prices["subTypeName"] = prices["subTypeName"].fillna("")

catalog = pd.concat(
    [pd.read_parquet(CATALOG / f"products_{c}.parquet") for c in (1, 3)],
    ignore_index=True,
)[["productId", "isSingle"]]
prices = prices.merge(catalog, on="productId", how="inner")
prices["segment"] = np.where(prices["isSingle"], "singles", "sealed")

# ------------------------------------------------- fixed basket + relatives
# Wide matrix: one row per (category, segment, productId, subTypeName),
# one column per month. Basket = rows priced in every month.
wide = prices.pivot_table(
    index=["categoryId", "segment", "productId", "subTypeName"],
    columns="month", values="marketPrice", aggfunc="first")
basket = wide.dropna()
basket = basket[basket[BASE_MONTH] > 0]
relatives = basket.div(basket[BASE_MONTH], axis=0) * 100.0

summary_rows, series = [], {}
for (cat, seg), grp in relatives.groupby(level=["categoryId", "segment"]):
    med = grp.median()
    q25 = grp.quantile(0.25)
    q75 = grp.quantile(0.75)
    series[(cat, seg)] = {"median": med, "q25": q25, "q75": q75, "n": len(grp)}
    print(f"{GAMES[cat]} {seg}: basket n={len(grp)}, "
          f"final index {med.iloc[-1]:.1f}")

# ---------------------------------------------------------------- exhibit
dates = pd.to_datetime([m + "-01" for m in months])
fig, axes = plt.subplots(1, 2, figsize=(13.5, 6.2), dpi=200, sharey=True,
                         facecolor=SURFACE)
fig.subplots_adjust(left=0.065, right=0.985, top=0.80, bottom=0.16, wspace=0.06)

for ax, cat in zip(axes, (3, 1)):  # Pokemon left, Magic right
    ax.set_facecolor(SURFACE)
    # scatter of sampled basket products' relatives, log y
    game_rel = relatives.loc[relatives.index.get_level_values("categoryId") == cat]
    n_sample = min(SCATTER_PER_GAME, len(game_rel))
    sample = game_rel.iloc[RNG.choice(len(game_rel), n_sample, replace=False)]
    for seg, color in (("singles", C_SINGLES), ("sealed", C_SEALED)):
        seg_rows = sample.loc[sample.index.get_level_values("segment") == seg]
        if len(seg_rows):
            xs = np.tile(mdates.date2num(dates), len(seg_rows))
            ax.plot(xs, seg_rows.to_numpy().ravel(), ".", ms=2, color=color,
                    alpha=0.05, rasterized=True, zorder=1)

    # dodge the two end-of-line labels apart if the series end close together
    ends = {seg: series[(cat, seg)]["median"].iloc[-1]
            for seg in ("singles", "sealed")}
    label_y = dict(ends)
    hi, lo = max(ends, key=ends.get), min(ends, key=ends.get)
    if ends[hi] / ends[lo] < 1.22:
        mid = (ends[hi] * ends[lo]) ** 0.5
        label_y[hi], label_y[lo] = mid * 1.10, mid / 1.10

    for seg, color, label in (("singles", C_SINGLES, "Singles"),
                              ("sealed", C_SEALED, "Sealed")):
        s = series[(cat, seg)]
        ax.fill_between(dates, s["q25"], s["q75"], color=color, alpha=0.12,
                        linewidth=0, zorder=2)
        ax.plot(dates, s["median"], color=color, lw=2, zorder=3,
                solid_capstyle="round")
        ax.annotate(f"{label}  {ends[seg]:.0f}", (dates[-1], label_y[seg]),
                    xytext=(6, 0), textcoords="offset points",
                    va="center", fontsize=9.5, fontweight="bold", color=color)

    ax.set_yscale("log")
    ax.axhline(100, color=BASELINE, lw=1, zorder=2)
    ax.set_title(GAMES[cat], fontsize=13, fontweight="bold", color=INK,
                 loc="left", pad=10)
    n_s = series[(cat, "singles")]["n"]
    n_x = series[(cat, "sealed")]["n"]
    ax.text(0, 1.005, f"basket: {n_s:,} singles / {n_x:,} sealed",
            transform=ax.transAxes, fontsize=8.5, color=MUTED)
    ax.grid(axis="y", color=GRID, lw=0.7)
    for spine in ("top", "right", "left"):
        ax.spines[spine].set_visible(False)
    ax.spines["bottom"].set_color(BASELINE)
    ax.tick_params(colors=MUTED, labelsize=9)
    ax.xaxis.set_major_locator(mdates.MonthLocator(interval=6))
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%b %y"))
    # fixed y-range: individual outlier products would otherwise blow out
    # the log scale (the scatter is a context layer, so clipping it is fine)
    ax.set_ylim(20, 1000)
    ax.yaxis.set_major_locator(matplotlib.ticker.FixedLocator(
        [25, 50, 100, 200, 400, 800]))
    ax.yaxis.set_major_formatter(matplotlib.ticker.FixedFormatter(
        ["25", "50", "100", "200", "400", "800"]))
    ax.yaxis.set_minor_locator(matplotlib.ticker.NullLocator())
    ax.set_xlim(dates[0], dates[-1] + pd.Timedelta(days=170))

axes[0].set_ylabel("Price index (Feb 2024 = 100, log scale)", fontsize=10,
                   color=INK2)
fig.suptitle("Trading-card prices since Feb 2024: fixed-basket market-price index",
             x=0.065, y=0.965, ha="left", fontsize=16, fontweight="bold",
             color=INK)
fig.text(0.065, 0.905,
         "Median of per-product price relatives with interquartile band; "
         "dots show a sample of individual basket products",
         fontsize=10.5, color=INK2)
fig.text(0.065, 0.035,
         "TCGplayer market prices via TCGCSV; fixed basket; price trend, "
         "not sales volume. Monthly snapshots Feb 2024 – Jul 2026; basket = "
         "products priced in every sampled month.",
         fontsize=8, color=MUTED)
fig.savefig(OUTPUT / "tcg_price_trends.png", facecolor=SURFACE)
fig.savefig(OUTPUT / "tcg_price_trends.svg", facecolor=SURFACE)
print(f"exhibit -> {OUTPUT}/tcg_price_trends.png|.svg")

# ------------------------------------------------------------------- xlsx
with pd.ExcelWriter(OUTPUT / "tcg_price_trends.xlsx") as writer:
    seg_names = {(3, "singles"): "Pokemon singles", (3, "sealed"): "Pokemon sealed",
                 (1, "singles"): "MTG singles", (1, "sealed"): "MTG sealed"}
    idx_df = pd.DataFrame({"month": months})
    for key, name in seg_names.items():
        idx_df[f"{name} — median index"] = series[key]["median"].values
    idx_df.to_excel(writer, sheet_name="Index (Feb24=100)", index=False)

    for key, name in seg_names.items():
        s = series[key]
        pd.DataFrame({
            "month": months,
            "median_index": s["median"].values,
            "iqr_p25": s["q25"].values,
            "iqr_p75": s["q75"].values,
            "basket_size": s["n"],
        }).to_excel(writer, sheet_name=name.replace(":", ""), index=False)

    pd.DataFrame({
        "segment": [seg_names[k] for k in seg_names],
        "basket_size": [series[k]["n"] for k in seg_names],
    }).to_excel(writer, sheet_name="Basket sizes", index=False)
print(f"workbook -> {OUTPUT}/tcg_price_trends.xlsx")

# ------------------------------------------------------------- 5-line summary
def line(cat, seg):
    s = series[(cat, seg)]["median"]
    peak_m = s.idxmax()
    return (f"{GAMES[cat]} {seg}: index {s.iloc[-1]:.0f} in {months[-1]} "
            f"({s.iloc[-1] - 100:+.0f}% vs Feb 2024; peak {s.max():.0f} in {peak_m})")

gap = (series[(3, "singles")]["median"].iloc[-1]
       - series[(1, "singles")]["median"].iloc[-1])
print("\nFINDINGS")
for cat, seg in ((3, "singles"), (3, "sealed"), (1, "singles"), (1, "sealed")):
    print("- " + line(cat, seg))
print(f"- Pokemon singles ended {gap:+.0f} index points vs MTG singles; "
      f"medians mask wide product-level dispersion (see IQR bands/scatter).")
