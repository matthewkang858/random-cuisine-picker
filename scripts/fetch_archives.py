"""Download monthly TCGCSV price archive snapshots.

One snapshot per month: 2024-02-08 (earliest available), then the 1st of each
month 2024-03-01 .. 2026-07-01. If a date 404s, fall back to the 2nd/3rd.
"""
import sys
import time
from pathlib import Path

import requests

BASE = "https://tcgcsv.com/archive/tcgplayer/prices-{}.ppmd.7z"
HEADERS = {"User-Agent": "ActivateAnalysis/1.0"}
DEST = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("archives")
DEST.mkdir(parents=True, exist_ok=True)


def month_candidates():
    """Yield (label, [candidate date strings]) per sampled month."""
    yield "2024-02", ["2024-02-08"]
    for year in (2024, 2025, 2026):
        for month in range(1, 13):
            if (year, month) <= (2024, 2):
                continue
            if (year, month) > (2026, 7):
                return
            yield f"{year}-{month:02d}", [f"{year}-{month:02d}-{d:02d}" for d in (1, 2, 3)]


def fetch(date_str):
    out = DEST / f"prices-{date_str}.ppmd.7z"
    if out.exists() and out.stat().st_size > 0:
        return out, "cached"
    url = BASE.format(date_str)
    for attempt in range(3):
        try:
            resp = requests.get(url, headers=HEADERS, timeout=120)
        except requests.RequestException as exc:
            print(f"  {date_str}: network error ({exc}), retry {attempt + 1}")
            time.sleep(2 * (attempt + 1))
            continue
        if resp.status_code == 404:
            return None, "404"
        if resp.status_code != 200:
            print(f"  {date_str}: HTTP {resp.status_code}, retry {attempt + 1}")
            time.sleep(2 * (attempt + 1))
            continue
        out.write_bytes(resp.content)
        return out, f"{len(resp.content) / 1e6:.1f} MB"
    return None, "failed"


manifest = []
for label, candidates in month_candidates():
    got = None
    for date_str in candidates:
        path, status = fetch(date_str)
        time.sleep(0.3)
        if path is not None:
            print(f"{label}: {date_str} ({status})")
            manifest.append(f"{label},{date_str}")
            got = date_str
            break
        print(f"{label}: {date_str} -> {status}")
    if got is None:
        print(f"{label}: NO ARCHIVE FOUND", file=sys.stderr)

(DEST / "manifest.csv").write_text("month,date\n" + "\n".join(manifest) + "\n")
print(f"done: {len(manifest)} archives")
