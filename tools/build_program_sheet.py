#!/usr/bin/env python3
"""Build a priced program sheet from an edX crawl JSON.

Usage:
  python3 tools/build_program_sheet.py <crawl.json> <url_base> <sheet_title> <out.xlsx> <run_note>

Each crawl record: {slug, ld: [prices...], amounts: [...], nCourses, title}.
Bundle price = first JSON-LD price. List price is inferred from page amounts:
an amount whose 90% (standard bundle discount) or 50% (promo) equals the
bundle price; if the JSON-LD carried the list price instead (its 90% appears
on the page), the bundle is derived; otherwise the row is flagged flat.
"""
import json
import re
import sys

from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

PARTNER_HINTS = {
    "harvardx": "Harvard (HarvardX)", "harvard": "Harvard", "mitx": "MIT (MITx)",
    "ibm": "IBM", "google": "Google", "microsoft": "Microsoft", "aws": "Amazon Web Services",
    "tecdemonterrey": "Tec de Monterrey", "uqx": "Univ. of Queensland (UQx)",
    "delftx": "TU Delft (DelftX)", "wharton": "Wharton (UPenn)", "asux": "Arizona State (ASUx)",
    "purduex": "Purdue (PurdueX)", "columbiax": "Columbia (ColumbiaX)",
    "stanfordonline": "Stanford Online", "berkeleyx": "UC Berkeley (BerkeleyX)",
    "michiganx": "Univ. of Michigan (MichiganX)", "utaustinx": "UT Austin (UTAustinX)",
    "nyux": "NYU (NYUx)", "gtx": "Georgia Tech (GTx)", "ritx": "RIT (RITx)",
    "usmx": "Univ. System of Maryland (USMx)", "wasedax": "Waseda (WasedaX)",
    "kironx": "Kiron", "upvalenciax": "UPV Valencia", "uamx": "UAM (UAMx)",
    "urosariox": "Univ. del Rosario", "javerianax": "Univ. Javeriana",
    "anahuacx": "Univ. Anáhuac", "galileox": "Univ. Galileo", "logyca": "LOGYCA",
    "uc3mx": "UC3M (Madrid)", "upmx": "UPM (Madrid)", "banco": "Banco Interamericano",
    "idbx": "Inter-American Development Bank (IDBx)", "edx": "edX",
    "linuxfoundationx": "The Linux Foundation", "w3cx": "W3C (W3Cx)",
    "tumx": "TU Munich (TUMx)", "kulx": "KU Leuven", "hkux": "Univ. of Hong Kong (HKUx)",
    "hkustx": "HKUST", "hkpolyux": "HK PolyU", "nusx": "NUS", "iimbx": "IIM Bangalore",
    "iitbombayx": "IIT Bombay", "iitbombay": "IIT Bombay", "iimax": "IIM Ahmedabad",
    "isaca": "ISACA", "acca": "ACCA", "cfa": "CFA Institute",
    "babson": "Babson College", "babsonx": "Babson College", "dartmouthx": "Dartmouth",
    "rice": "Rice University", "ricex": "Rice University", "curtinx": "Curtin University",
    "adelaidex": "Univ. of Adelaide", "unswx": "UNSW Sydney", "anux": "ANU",
    "fullbridgex": "Fullbridge", "pennx": "UPenn (PennX)", "utokyox": "Univ. of Tokyo",
}


def partner_from_slug(slug):
    head = slug.split("-")[0].lower()
    if head in PARTNER_HINTS:
        return PARTNER_HINTS[head]
    two = "-".join(slug.split("-")[:2]).lower()
    if two in PARTNER_HINTS:
        return PARTNER_HINTS[two]
    return head.capitalize()


def infer_pricing(current, amounts):
    for a in amounts:
        if a > current and abs(a * 0.9 - current) < 0.05:
            return a, current, "standard 10% bundle discount"
    for a in amounts:
        if a > current and abs(a * 0.5 - current) < 0.05:
            return a, current, "50% off — active promo"
    for a in amounts:
        if a < current and abs(current * 0.9 - a) < 0.05:
            return current, round(current * 0.9, 2), "standard 10% bundle discount"
    return current, current, "no separate list price shown"


def main():
    crawl_json, url_base, sheet_title, out_path, run_note = sys.argv[1:6]
    recs = json.load(open(crawl_json))

    rows = []
    for r in recs:
        if not r.get("ld"):
            continue
        current = float(r["ld"][0])
        amounts = [float(a) for a in r.get("amounts", [])]
        listp, bundle, note = infer_pricing(current, amounts)
        title = re.sub(r"\s*\|\s*edX\s*$", "", (r.get("title") or r["slug"])).strip()
        rows.append((title, partner_from_slug(r["slug"]), r["slug"],
                     r.get("nCourses"), round(listp, 2), round(bundle, 2), note))
    rows.sort(key=lambda x: -x[5])

    wb = Workbook()
    ws = wb.active
    ws.title = "Prices"
    ARIAL = "Arial"
    border = Border(bottom=Side(style="thin", color="B0B0B0"))

    ws["A1"] = sheet_title
    ws["A1"].font = Font(name=ARIAL, size=13, bold=True)
    ws["A2"] = run_note
    ws["A2"].font = Font(name=ARIAL, size=9, italic=True, color="666666")

    HDR = ["Program", "Partner", "Courses", "List price ($)", "Bundle price ($)",
           "Discount", "Pricing note", "URL"]
    for c, h in enumerate(HDR, 1):
        cell = ws.cell(row=4, column=c, value=h)
        cell.font = Font(name=ARIAL, size=10, bold=True, color="FFFFFF")
        cell.fill = PatternFill("solid", fgColor="333F50")
        cell.alignment = Alignment(vertical="center")

    r0 = 5
    for i, (title, partner, slug, n, listp, cur, note) in enumerate(rows):
        r = r0 + i
        url = url_base + slug
        vals = [title, partner, n, listp, cur,
                f'=IF(D{r}=0,"",1-E{r}/D{r})', note, url]
        for c, v in enumerate(vals, 1):
            cell = ws.cell(row=r, column=c, value=v)
            cell.font = Font(name=ARIAL, size=10)
            cell.border = border
        ws.cell(row=r, column=4).number_format = "$#,##0.00"
        ws.cell(row=r, column=5).number_format = "$#,##0.00"
        ws.cell(row=r, column=6).number_format = "0.0%"
        u = ws.cell(row=r, column=8)
        u.hyperlink = url
        u.font = Font(name=ARIAL, size=9, color="0563C1", underline="single")

    last = r0 + len(rows) - 1
    s = last + 2
    stats = [
        ("Programs", f"=COUNTA(A{r0}:A{last})", "0"),
        ("Min bundle price", f"=MIN(E{r0}:E{last})", "$#,##0.00"),
        ("25th percentile", f"=QUARTILE(E{r0}:E{last},1)", "$#,##0.00"),
        ("Median bundle price", f"=MEDIAN(E{r0}:E{last})", "$#,##0.00"),
        ("75th percentile", f"=QUARTILE(E{r0}:E{last},3)", "$#,##0.00"),
        ("Max bundle price", f"=MAX(E{r0}:E{last})", "$#,##0.00"),
        ("Average discount", f"=AVERAGE(F{r0}:F{last})", "0.0%"),
    ]
    ws.cell(row=s, column=1, value="Summary").font = Font(name=ARIAL, size=11, bold=True)
    for i, (label, formula, fmt) in enumerate(stats, 1):
        ws.cell(row=s + i, column=1, value=label).font = Font(name=ARIAL, size=10)
        c = ws.cell(row=s + i, column=2, value=formula)
        c.font = Font(name=ARIAL, size=10, bold=True)
        c.number_format = fmt

    note_r = s + len(stats) + 2
    ws.cell(row=note_r, column=1, value=(
        "Notes: bundle price = the program page's JSON-LD offer (USD). List price is inferred "
        "from amounts shown on the same page (90% standard-discount or 50% promo relation); "
        "rows marked 'no separate list price shown' displayed only one price — treat their "
        "discount as 0% observed, not necessarily 0% offered. Some non-US pages show localized "
        "currency, which this inference conservatively ignores. edX sitewide promo codes "
        "(15-30%) can apply at checkout; financial assistance (80% off) applies to individual "
        "verified certificates, generally not program bundles.")).font = \
        Font(name=ARIAL, size=9, italic=True, color="666666")

    for c, w in enumerate([56, 30, 9, 13, 14, 10, 30, 64], 1):
        ws.column_dimensions[get_column_letter(c)].width = w
    ws.freeze_panes = "A5"
    wb.save(out_path)
    print(f"wrote {out_path}: {len(rows)} programs")


if __name__ == "__main__":
    main()
