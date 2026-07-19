"""One-time catalog pull: groups and products for the configured categories.

Classifies products as singles (extendedData has "Rarity" or "Number") vs
sealed, and writes one catalog parquet per category. Categories whose
parquet already exists are skipped (IDs are stable).
"""
import sys
import time
from pathlib import Path

import pandas as pd
import requests

from tcg_config import CATEGORIES as CATEGORY_NAMES

HEADERS = {"User-Agent": "ActivateAnalysis/1.0"}
DEST = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("catalog")
DEST.mkdir(parents=True, exist_ok=True)
CATEGORIES = {cat: names[0] for cat, names in CATEGORY_NAMES.items()}


def get_json(url):
    for attempt in range(4):
        try:
            resp = requests.get(url, headers=HEADERS, timeout=60)
            if resp.status_code == 200:
                return resp.json()
            print(f"  HTTP {resp.status_code} for {url}")
        except (requests.RequestException, ValueError) as exc:
            print(f"  error {exc} for {url}")
        time.sleep(2 * (attempt + 1))
    raise RuntimeError(f"failed to fetch {url}")


for cat, cat_name in CATEGORIES.items():
    if (DEST / f"products_{cat}.parquet").exists():
        print(f"{cat_name}: cached")
        continue
    groups = get_json(f"https://tcgcsv.com/tcgplayer/{cat}/groups")["results"]
    pd.DataFrame(
        [{"groupId": g["groupId"], "groupName": g["name"],
          "abbreviation": g.get("abbreviation")} for g in groups]
    ).to_parquet(DEST / f"groups_{cat}.parquet")
    print(f"{cat_name}: {len(groups)} groups")

    rows = []
    for i, g in enumerate(groups):
        time.sleep(0.26)
        data = get_json(f"https://tcgcsv.com/tcgplayer/{cat}/{g['groupId']}/products")
        for p in data["results"]:
            ext = {e.get("name"): e.get("value")
                   for e in (p.get("extendedData") or [])}
            rows.append({
                "productId": p["productId"],
                "productName": p["name"],
                "groupId": g["groupId"],
                "isSingle": bool(ext.keys() & {"Rarity", "Number"}),
                "rarity": ext.get("Rarity"),
            })
        if (i + 1) % 50 == 0:
            print(f"  {cat_name}: {i + 1}/{len(groups)} groups, {len(rows)} products")

    df = pd.DataFrame(rows)
    df.to_parquet(DEST / f"products_{cat}.parquet")
    print(f"{cat_name}: {len(df)} products, {int(df.isSingle.sum())} singles")

print("catalog done")
