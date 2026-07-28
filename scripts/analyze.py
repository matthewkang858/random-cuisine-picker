"""Fixed-basket price-trend analysis and client exhibit (top-10 TCGs).

Method (documented in the exhibit footnote):
- Basket per (game, segment) = (productId, subTypeName) pairs with a
  non-null marketPrice in EVERY sampled month the game has data for
  (avoids mix-shift artifacts).
- Games launched after Feb 2024 are indexed from their first sampled
  month (annotated on the panel); everything else from Feb 2024.
- Each basket product is indexed to 100 at its base-month price; the
  segment series is the cross-product median, with the IQR band.

Outputs (./output): exhibit PNG + SVG, tcg_price_trends.xlsx, and a
printed 5-line findings summary.
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

from tcg_config import CATEGORIES, CATEGORY_ORDER, RARITY_BALANCE

MONTHLY = Path(sys.argv[1])   # per-month price parquets
CATALOG = Path(sys.argv[2])   # catalog parquets
OUTPUT = Path(sys.argv[3]) if len(sys.argv) > 3 else Path("output")
OUTPUT.mkdir(parents=True, exist_ok=True)

SCATTER_PER_GAME = 150
MIN_BASE_ROWS = 50            # month must have this many priced rows to count
RNG = np.random.default_rng(20260716)

# Deck style (validated palette; see dataviz notes)
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
print(f"{len(months)} months: {months[0]} .. {months[-1]}")

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

rarity_map = pd.concat(
    [pd.read_parquet(CATALOG / f"products_{c}.parquet") for c in RARITY_BALANCE
     ], ignore_index=True).set_index("productId")["rarity"] \
    if RARITY_BALANCE else pd.Series(dtype=object)


def weighted_quantile(frame, weights, q):
    """Per-column weighted quantile of a rows x months frame."""
    out = {}
    for col in frame.columns:
        v = frame[col].to_numpy()
        order = np.argsort(v)
        v, w = v[order], weights[order]
        cw = (np.cumsum(w) - 0.5 * w) / w.sum()
        out[col] = float(np.interp(q, cw, v))
    return pd.Series(out)


def balanced_weights(cat, grp):
    """50:50 collector/playable weights for a balanced game's singles basket.
    Returns (trimmed frame, weights, note) or None if not applicable."""
    spec = RARITY_BALANCE.get(cat)
    if spec is None:
        return None
    rarities = rarity_map.reindex(
        grp.index.get_level_values("productId")).to_numpy()
    is_col = np.isin(rarities, list(spec["collector"]))
    is_play = np.isin(rarities, list(spec["playable"]))
    keep = is_col | is_play
    grp, is_col = grp[keep], is_col[keep]
    n_col, n_play = int(is_col.sum()), int((~is_col).sum())
    if not n_col or not n_play:
        return None
    w = np.where(is_col, 0.5 / n_col, 0.5 / n_play)
    return grp, w, f"{n_col} collector / {n_play} playable, 50:50"


# ------------------------------------------------- fixed basket + relatives
wide = prices.pivot_table(
    index=["categoryId", "segment", "productId", "subTypeName"],
    columns="month", values="marketPrice", aggfunc="first")

series = {}        # (cat, seg) -> dict(median, q25, q75, n, base, months)
relatives_by_cat = {}
for cat in CATEGORY_ORDER:
    cat_wide = wide.loc[wide.index.get_level_values("categoryId") == cat]
    # base month = first sampled month with a real footprint for this game
    counts = cat_wide.notna().sum()
    live = [m for m in months if counts.get(m, 0) >= MIN_BASE_ROWS]
    if not live:
        print(f"{CATEGORIES[cat][0]}: no data, skipped", file=sys.stderr)
        continue
    base, cat_months = live[0], live
    sub = cat_wide[cat_months].dropna()
    sub = sub[sub[base] > 0]
    rel = sub.div(sub[base], axis=0) * 100.0
    relatives_by_cat[cat] = rel
    for seg in ("singles", "sealed"):
        grp = rel.loc[rel.index.get_level_values("segment") == seg]
        if grp.empty:
            continue
        balance = balanced_weights(cat, grp) if seg == "singles" else None
        if balance is not None:
            grp, w, note = balance
            entry = {
                "median": weighted_quantile(grp, w, 0.5),
                "q25": weighted_quantile(grp, w, 0.25),
                "q75": weighted_quantile(grp, w, 0.75),
                "n": len(grp), "note": note,
            }
        else:
            entry = {
                "median": grp.median(), "q25": grp.quantile(0.25),
                "q75": grp.quantile(0.75), "n": len(grp), "note": None,
            }
        entry.update(base=base, months=cat_months)
        series[(cat, seg)] = entry
        print(f"{CATEGORIES[cat][0]} {seg}: basket n={entry['n']}"
              f"{' (' + entry['note'] + ')' if entry['note'] else ''}, "
              f"base {base}, final index {entry['median'].iloc[-1]:.1f}")


def month_dates(ms):
    return pd.to_datetime([m + "-01" for m in ms])


def cagr(key):
    s = series[key]
    y0, m0 = map(int, s["base"].split("-"))
    d0 = date(2024, 2, 8) if s["base"] == "2024-02" else date(y0, m0, 1)
    y1, m1 = map(int, months[-1].split("-"))
    yrs = (date(y1, m1, 1) - d0).days / 365.25
    return (s["median"].iloc[-1] / 100.0) ** (1 / yrs) - 1 if yrs > 0 else np.nan


# ---------------------------------------------------------------- exhibit
all_dates = month_dates(months)
fig, axes = plt.subplots(3, 4, figsize=(15.5, 11.8), dpi=200, sharey=True,
                         sharex=True, facecolor=SURFACE)
fig.subplots_adjust(left=0.055, right=0.985, top=0.885, bottom=0.075,
                    wspace=0.08, hspace=0.34)

for ax, cat in zip(axes.ravel(), CATEGORY_ORDER):
    ax.set_facecolor(SURFACE)
    rel = relatives_by_cat.get(cat)
    if rel is None:
        ax.set_axis_off()
        continue
    dates = month_dates(series[(cat, "singles")]["months"]
                        if (cat, "singles") in series
                        else series[(cat, "sealed")]["months"])

    n_sample = min(SCATTER_PER_GAME, len(rel))
    sample = rel.iloc[RNG.choice(len(rel), n_sample, replace=False)]
    for seg, color in (("singles", C_SINGLES), ("sealed", C_SEALED)):
        seg_rows = sample.loc[sample.index.get_level_values("segment") == seg]
        if len(seg_rows):
            xs = np.tile(mdates.date2num(dates), len(seg_rows))
            ax.plot(xs, seg_rows.to_numpy().ravel(), ".", ms=1.8, color=color,
                    alpha=0.06, rasterized=True, zorder=1)

    present = [seg for seg in ("singles", "sealed") if (cat, seg) in series]
    ends = {seg: series[(cat, seg)]["median"].iloc[-1] for seg in present}
    label_y = dict(ends)
    if len(present) == 2:
        hi, lo = max(ends, key=ends.get), min(ends, key=ends.get)
        if ends[hi] / ends[lo] < 1.35:
            mid = (ends[hi] * ends[lo]) ** 0.5
            label_y[hi], label_y[lo] = mid * 1.16, mid / 1.16

    for seg, color in (("singles", C_SINGLES), ("sealed", C_SEALED)):
        if (cat, seg) not in series:
            continue
        s = series[(cat, seg)]
        ax.fill_between(dates, s["q25"], s["q75"], color=color, alpha=0.12,
                        linewidth=0, zorder=2)
        ax.plot(dates, s["median"], color=color, lw=1.8, zorder=3,
                solid_capstyle="round")
        ax.annotate(f"{ends[seg]:.0f}", (dates[-1], label_y[seg]),
                    xytext=(4, 0), textcoords="offset points",
                    va="center", fontsize=8.5, fontweight="bold", color=color)

    ax.set_yscale("log")
    ax.set_ylim(20, 1000)
    ax.yaxis.set_major_locator(matplotlib.ticker.FixedLocator(
        [25, 50, 100, 200, 400, 800]))
    ax.yaxis.set_major_formatter(matplotlib.ticker.FixedFormatter(
        ["25", "50", "100", "200", "400", "800"]))
    ax.yaxis.set_minor_locator(matplotlib.ticker.NullLocator())
    ax.axhline(100, color=BASELINE, lw=0.9, zorder=2)

    base = series[(cat, present[0])]["base"]
    title = CATEGORIES[cat][0]
    ax.set_title(title, fontsize=11, fontweight="bold", color=INK,
                 loc="left", pad=13)
    n_txt = " / ".join(f"{series[(cat, seg)]['n']:,} {seg}" for seg in present)
    base_txt = "" if base == months[0] else \
        f"  ·  since {pd.to_datetime(base + '-01'):%b %y}"
    if (cat, "singles") in series and series[(cat, "singles")]["note"]:
        base_txt += "  ·  singles 50:50 collector/playable"
    ax.text(0, 1.02, n_txt + base_txt, transform=ax.transAxes,
            fontsize=7, color=MUTED)
    ax.grid(axis="y", color=GRID, lw=0.6)
    for spine in ("top", "right", "left"):
        ax.spines[spine].set_visible(False)
    ax.spines["bottom"].set_color(BASELINE)
    ax.tick_params(colors=MUTED, labelsize=8)
    ax.xaxis.set_major_locator(mdates.YearLocator())
    ax.xaxis.set_major_formatter(mdates.DateFormatter("'%y"))
    ax.set_xlim(all_dates[0], all_dates[-1] + pd.Timedelta(days=150))

for ax in axes[:, 0]:
    ax.set_ylabel("Index (base = 100, log)", fontsize=9, color=INK2)

fig.suptitle("Trading-card prices, top TCGs: fixed-basket market-price index",
             x=0.055, y=0.972, ha="left", fontsize=16, fontweight="bold",
             color=INK)
fig.text(0.055, 0.935,
         "Median of per-product price relatives with interquartile band; dots "
         "show sampled basket products. Base = Feb 2024 or first month on market.",
         fontsize=10.5, color=INK2)
# figure-level legend (color identifies segment in every panel)
fig.legend(handles=[plt.Line2D([], [], color=C_SINGLES, lw=2, label="Singles"),
                    plt.Line2D([], [], color=C_SEALED, lw=2, label="Sealed")],
           loc="upper right", bbox_to_anchor=(0.985, 0.975), ncol=2,
           frameon=False, fontsize=10.5)
fig.text(0.055, 0.02,
         "TCGplayer market prices via TCGCSV; fixed basket; price trend, not "
         "sales volume. Monthly snapshots Feb 2024 – Jul 2026 (latest "
         "Jul 27, 2026); basket = products priced in every sampled month the "
         "game has data for.",
         fontsize=8, color=MUTED)
fig.savefig(OUTPUT / "tcg_price_trends.png", facecolor=SURFACE)
fig.savefig(OUTPUT / "tcg_price_trends.svg", facecolor=SURFACE)
print(f"exhibit -> {OUTPUT}/tcg_price_trends.png|.svg")

# ------------------------------------------------------------------- xlsx
seg_label = {(cat, seg): f"{CATEGORIES[cat][0]} {seg}"
             for cat in CATEGORY_ORDER for seg in ("singles", "sealed")
             if (cat, seg) in series}
with pd.ExcelWriter(OUTPUT / "tcg_price_trends.xlsx") as writer:
    idx_df = pd.DataFrame({"month": months})
    for key, name in seg_label.items():
        med = series[key]["median"].reindex(months)
        idx_df[name] = med.values
    idx_df.to_excel(writer, sheet_name="Index (base=100)", index=False)

    pd.DataFrame({
        "segment": list(seg_label.values()),
        "base_month": [series[k]["base"] for k in seg_label],
        "basket_size": [series[k]["n"] for k in seg_label],
        "final_index": [round(series[k]["median"].iloc[-1], 1) for k in seg_label],
        "CAGR": [round(cagr(k), 4) for k in seg_label],
    }).to_excel(writer, sheet_name="Summary & baskets", index=False)

    for cat in CATEGORY_ORDER:
        present = [s for s in ("singles", "sealed") if (cat, s) in series]
        if not present:
            continue
        cat_months = series[(cat, present[0])]["months"]
        out = pd.DataFrame({"month": cat_months})
        for seg in present:
            s = series[(cat, seg)]
            out[f"{seg}_median"] = s["median"].values
            out[f"{seg}_p25"] = s["q25"].values
            out[f"{seg}_p75"] = s["q75"].values
            out[f"{seg}_basket"] = s["n"]
        sheet = CATEGORIES[cat][0][:31].replace(":", "").replace("/", "-")
        out.to_excel(writer, sheet_name=sheet, index=False)
print(f"workbook -> {OUTPUT}/tcg_price_trends.xlsx")

# ------------------------------------------------------------- 5-line summary
ranked = sorted(seg_label, key=lambda k: cagr(k), reverse=True)
sealed_beats = sum(
    1 for cat in CATEGORY_ORDER
    if (cat, "sealed") in series and (cat, "singles") in series
    and series[(cat, "sealed")]["median"].iloc[-1]
    > series[(cat, "singles")]["median"].iloc[-1])
n_games = len({k[0] for k in series})
decliners = [seg_label[k] for k in seg_label
             if series[k]["median"].iloc[-1] < 100]

print("\nFINDINGS")
top3 = ", ".join(f"{seg_label[k]} {cagr(k) * 100:+.0f}%/yr" for k in ranked[:3])
bot2 = ", ".join(f"{seg_label[k]} {cagr(k) * 100:+.0f}%/yr" for k in ranked[-2:])
print(f"- Fastest appreciation: {top3}.")
print(f"- Slowest: {bot2}.")
print(f"- Sealed outperformed singles in {sealed_beats} of {n_games} games "
      f"with both segments.")
print(f"- Segments below their base level: "
      f"{', '.join(decliners) if decliners else 'none'}.")
print(f"- Fixed baskets track the pre-existing card pool only; newer games "
      f"are indexed from their first sampled month (see Summary sheet).")
