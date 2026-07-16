#!/usr/bin/env bash
# End-to-end TCG price-trend pipeline. Requires: p7zip-full (PPMd support),
# python3 with pandas/pyarrow/matplotlib/openpyxl/requests, and network
# access to tcgcsv.com.
set -euo pipefail
cd "$(dirname "$0")"

WORK="${TCG_WORKDIR:-$(mktemp -d)}"
mkdir -p "$WORK"/{archives,extracted,catalog,monthly}
echo "work dir: $WORK"

python3 scripts/fetch_archives.py "$WORK/archives"
python3 scripts/fetch_catalog.py  "$WORK/catalog"
python3 scripts/parse_archives.py "$WORK/archives" "$WORK/extracted" "$WORK/monthly"
python3 scripts/analyze.py        "$WORK/monthly"  "$WORK/catalog"   output
