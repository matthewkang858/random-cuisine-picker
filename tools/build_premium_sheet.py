#!/usr/bin/env python3
"""Build the FutureLearn Premium courses workbook: join the premium filter
slug list against the full-catalog crawl prices."""
import json
import re

from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

ARIAL = "Arial"
BORDER = Border(bottom=Side(style="thin", color="B0B0B0"))

slugs = json.load(open("research/futurelearn-premium-slugs.json"))
crawl = {r["url"].rsplit("/", 1)[1]: r for r in json.load(open("research/futurelearn-crawl.json"))}
try:
    for r in json.load(open("research/futurelearn-premium-extra.json")):
        crawl[r["url"].rsplit("/", 1)[1]] = r
except FileNotFoundError:
    pass
EXCL = {"349.99", "0", "0.00", "244.99"}

rows, missing = [], []
for slug in slugs:
    r = crawl.get(slug)
    url = f"https://www.futurelearn.com/courses/{slug}"
    if not r:
        missing.append(slug)
        rows.append((slug.replace("-", " ").title(), None, None, "not in catalog crawl", url))
        continue
    src = [s for s in r["srcPrices"] if s not in EXCL and float(s) < 2000]
    dol = [d for d in r["dollars"] if d not in EXCL]
    cands = [s for s in src if any(abs(float(s) - float(d)) < 0.01 for d in dol)] or dol
    uniq = sorted(set(float(c) for c in cands))
    title = re.sub(r"\s*[-–]\s*(?:Online Course.*|Online\b.*|FutureLearn.*)$", "",
                   r["title"]).strip() or slug
    if not uniq:
        rows.append((title, int(r["weeks"]) if r["weeks"] else None, None,
                     "no price shown on page", url))
        continue
    price = uniq[0]
    note = ""
    if len(uniq) > 1:
        note = "ambiguous — page showed " + " and ".join(f"${v:g}" for v in uniq)
    elif price in (54.0, 79.0, 109.0):
        note = "standard-tier price (unusual for Premium)"
    rows.append((title, int(r["weeks"]) if r["weeks"] else None, price, note, url))
rows.sort(key=lambda x: (-(x[2] or -1), x[0]))

wb = Workbook()
ws = wb.active
ws.title = "Premium courses"
ws["A1"] = f"FutureLearn Premium courses — prices ({len(rows)} courses)"
ws["A1"].font = Font(name=ARIAL, size=13, bold=True)
ws["A2"] = ("Source: futurelearn.com course catalog filtered to Premium + started "
            "(filter_category=open&filter_course_type=premium&filter_availability=started), "
            "enumerated Aug 12 2026; prices joined from the same-day crawl of every course page "
            "(US storefront, USD). Premium courses are paid-upfront and NOT included in "
            "FutureLearn Unlimited.")
ws["A2"].font = Font(name=ARIAL, size=9, italic=True, color="666666")
for c, h in enumerate(["Course", "Weeks", "Price ($)", "Note", "URL"], 1):
    cell = ws.cell(row=4, column=c, value=h)
    cell.font = Font(name=ARIAL, size=10, bold=True, color="FFFFFF")
    cell.fill = PatternFill("solid", fgColor="333F50")
    cell.alignment = Alignment(vertical="center")
for c, w in enumerate([62, 8, 14, 34, 64], 1):
    ws.column_dimensions[get_column_letter(c)].width = w
ws.freeze_panes = "A5"

r0 = 5
for i, (title, weeks, price, note, url) in enumerate(rows):
    r = r0 + i
    for c, v in enumerate([title, weeks, price, note, url], 1):
        cell = ws.cell(row=r, column=c, value=v)
        cell.font = Font(name=ARIAL, size=10)
        cell.border = BORDER
    ws.cell(row=r, column=3).number_format = "$#,##0.00"
    u = ws.cell(row=r, column=5)
    u.hyperlink = url
    u.font = Font(name=ARIAL, size=9, color="0563C1", underline="single")

last = r0 + len(rows) - 1
s = last + 2
stats = [
    ("Courses with a shown price", f"=COUNT(C{r0}:C{last})", "0"),
    ("Min price", f"=MIN(C{r0}:C{last})", "$#,##0.00"),
    ("Median price", f"=MEDIAN(C{r0}:C{last})", "$#,##0.00"),
    ("Max price", f"=MAX(C{r0}:C{last})", "$#,##0.00"),
]
ws.cell(row=s, column=1, value="Summary").font = Font(name=ARIAL, size=11, bold=True)
for i, (label, formula, fmt) in enumerate(stats, 1):
    ws.cell(row=s + i, column=1, value=label).font = Font(name=ARIAL, size=10)
    c = ws.cell(row=s + i, column=2, value=formula)
    c.font = Font(name=ARIAL, size=10, bold=True)
    c.number_format = fmt
ws.cell(row=s + len(stats) + 2, column=1, value=(
    f"Notes: {len(missing)} premium-filter slugs were absent from the sitemap crawl "
    "(newly listed courses). Premium courses sit outside Unlimited; their price is the full "
    "cost of taking the course. Prices shown are the US storefront's one-off purchase price.")
).font = Font(name=ARIAL, size=9, italic=True, color="666666")

wb.save("research/futurelearn-premium-prices.xlsx")
print(f"premium sheet: {len(rows)} rows; missing from crawl: {len(missing)}",
      missing[:5] if missing else "")
