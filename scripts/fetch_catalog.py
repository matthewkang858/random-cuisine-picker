"""One-time catalog pull: groups and products for Magic (1) and Pokemon (3).

Classifies products as singles (extendedData has "Rarity" or "Number") vs
sealed, and writes one catalog parquet per category.
"""
import sys
import time
from pathlib import Path

import pandas as pd
import requests

HEADERS = {"User-Agent": "ActivateAnalysis/1.0"}
DEST = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("catalog")
DEST.mkdir(parents=True, exist_ok=True)
CATEGORIES = {1: "Magic", 3: "Pokemon"}


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
            ext_names = {e.get("name") for e in (p.get("extendedData") or [])}
            rows.append({
                "productId": p["productId"],
                "productName": p["name"],
                "groupId": g["groupId"],
                "isSingle": bool(ext_names & {"Rarity", "Number"}),
            })
        if (i + 1) % 50 == 0:
            print(f"  {cat_name}: {i + 1}/{len(groups)} groups, {len(rows)} products")

    df = pd.DataFrame(rows)
    df.to_parquet(DEST / f"products_{cat}.parquet")
    print(f"{cat_name}: {len(df)} products, {int(df.isSingle.sum())} singles")

print("catalog done")
