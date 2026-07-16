# TCG price-trend analysis (TCGCSV archives)

One-off analysis producing a client-ready exhibit of TCGplayer price trends
for Magic: The Gathering and Pokemon, Feb 2024 – Jul 2026.

## Status

**Complete.** Run on live TCGCSV data on 2026-07-16 (30 monthly snapshots,
2024-02-08 through 2026-07-01); generated outputs are committed under
`./output`. Requires network access to `tcgcsv.com` to re-run (in Claude
Code cloud environments: set the environment's network access to Custom
and allow `tcgcsv.com`).

## Run

```bash
./run_analysis.sh          # requires p7zip-full, python3 + pandas/pyarrow/matplotlib/openpyxl/requests
```

Downloads ~30 monthly archive snapshots (custom User-Agent, throttled,
404 fallback to the 2nd/3rd of the month), pulls the catalog once, parses
categories 1 (Magic) and 3 (Pokemon), and writes to `./output`:

- `tcg_price_trends.png` / `.svg` — two-panel exhibit (Pokemon | Magic),
  median fixed-basket index per segment with IQR band, sampled product
  scatter behind on log y
- `tcg_price_trends.xlsx` — monthly median/IQR series per segment + basket sizes
- a printed 5-line findings summary

## Method

- Snapshots: 2024-02-08 (earliest archive), then the 1st of each month
  through 2026-07-01.
- Key is the composite `(productId, subTypeName)`. Rows with null
  `marketPrice` are dropped; `highPrice` is ignored (seller price-parking).
- Singles = products whose catalog `extendedData` includes `Rarity` or
  `Number`; everything else is sealed.
- Fixed basket per segment = pairs priced in **every** sampled month, which
  avoids mix-shift artifacts. Each product is indexed to 100 at its own
  Feb 2024 price; the series is the cross-product median, with the
  25th–75th percentile band for dispersion.
- Exhibit footnote: "TCGplayer market prices via TCGCSV; fixed basket;
  price trend, not sales volume."

## Layout

- `run_analysis.sh` — end-to-end driver (work dir override: `TCG_WORKDIR`)
- `scripts/fetch_archives.py` — monthly archive downloads + manifest
- `scripts/fetch_catalog.py` — one-time groups/products pull, singles flag
- `scripts/parse_archives.py` — selective 7z (PPMd) extraction → monthly parquet
- `scripts/analyze.py` — basket, index, exhibit, workbook, summary
