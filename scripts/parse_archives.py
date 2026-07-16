"""Extract each monthly archive and parse Magic (1) / Pokemon (3) prices.

Writes one parquet per month with columns:
  categoryId, productId, subTypeName, marketPrice
Rows with null marketPrice are dropped. highPrice is ignored entirely
(seller price-parking makes it unusable); low/mid are not needed for the
fixed-basket index.
"""
import json
import shutil
import subprocess
import sys
from pathlib import Path

import pandas as pd

from tcg_config import CATEGORIES

ARCHIVES = Path(sys.argv[1])
WORK = Path(sys.argv[2])
OUT = Path(sys.argv[3])
OUT.mkdir(parents=True, exist_ok=True)
CATS = tuple(str(c) for c in CATEGORIES)

manifest = pd.read_csv(ARCHIVES / "manifest.csv", dtype=str)

for _, row in manifest.iterrows():
    month, date = row["month"], row["date"]
    out_path = OUT / f"prices_{month}.parquet"
    if out_path.exists():
        print(f"{month}: cached")
        continue
    archive = ARCHIVES / f"prices-{date}.ppmd.7z"
    extract_dir = WORK / date
    if extract_dir.exists():
        shutil.rmtree(extract_dir)
    extract_dir.mkdir(parents=True)

    # Selective extraction of just the two categories we need.
    patterns = [f"{date}/{c}/*" for c in CATS]
    proc = subprocess.run(
        ["7z", "x", str(archive), f"-o{extract_dir}", "-y", *patterns],
        capture_output=True, text=True)
    if proc.returncode != 0:
        print(f"{month}: 7z failed\n{proc.stdout[-2000:]}\n{proc.stderr[-2000:]}",
              file=sys.stderr)
        sys.exit(1)

    rows = []
    for cat in CATS:
        cat_dir = extract_dir / date / cat
        if not cat_dir.is_dir():
            # normal for games that launched after this snapshot
            continue
        for prices_file in cat_dir.glob("*/prices"):
            with open(prices_file) as f:
                results = json.load(f).get("results", [])
            for r in results:
                mp = r.get("marketPrice")
                if mp is None:
                    continue
                rows.append((int(cat), r["productId"], r.get("subTypeName"), mp))

    df = pd.DataFrame(rows, columns=["categoryId", "productId", "subTypeName",
                                     "marketPrice"])
    df.to_parquet(out_path)
    shutil.rmtree(extract_dir)
    per_cat = df.groupby("categoryId").size()
    print(f"{month}: {len(df)} priced rows across {len(per_cat)} categories")

print("parse done")
