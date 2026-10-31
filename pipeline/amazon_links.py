#!/usr/bin/env python3
"""Verified Amazon links: a registry mapping product barcodes to exact amazon.com product IDs (ASINs).

A product in the registry gets a direct "View on Amazon" link to its exact product page instead
of a search. Entries are only ever added by someone who checked the product page (or, later, by
Amazon's product API), so every link in the registry is one we trust.

Registry: data/amazon_links.csv (code, asin, source, verified_on, note)

Usage:
  python3 pipeline/amazon_links.py add <barcode> <amazon product URL or ASIN> [--note "..."]
  python3 pipeline/amazon_links.py remove <barcode>
  python3 pipeline/amazon_links.py list
"""
import argparse
import csv
import datetime
import re
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REGISTRY = ROOT / "data" / "amazon_links.csv"
FIELDS = ["code", "asin", "source", "verified_on", "note"]
# An ASIN is 10 characters: B followed by 9 letters/digits, or an ISBN-10 for books.
ASIN_RE = re.compile(r"^(B[0-9A-Z]{9}|\d{9}[\dX])$")
URL_PATTERNS = [r"/dp/([0-9A-Z]{10})", r"/gp/product/([0-9A-Z]{10})", r"/gp/aw/d/([0-9A-Z]{10})",
                r"/product/([0-9A-Z]{10})", r"[?&]asin=([0-9A-Z]{10})"]


def read():
    if not REGISTRY.exists():
        return {}
    with open(REGISTRY, newline="", encoding="utf-8") as f:
        return {row["code"]: row for row in csv.DictReader(f)}


def write(rows):
    REGISTRY.parent.mkdir(parents=True, exist_ok=True)
    with open(REGISTRY, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        w.writeheader()
        w.writerows(sorted(rows.values(), key=lambda r: r["code"]))


def parse_asin(text):
    """'https://www.amazon.com/Some-Name/dp/B00ABC1234/ref=...' or 'B00ABC1234' -> 'B00ABC1234'."""
    text = text.strip()
    if ASIN_RE.match(text.upper()):
        return text.upper()
    for pattern in URL_PATTERNS:
        m = re.search(pattern, text, re.I)
        if m and ASIN_RE.match(m.group(1).upper()):
            return m.group(1).upper()
    return None


def product_name(code):
    try:
        db = sqlite3.connect(f"file:{ROOT / 'products_clean.db'}?mode=ro", uri=True)
        row = db.execute("SELECT name, brands FROM products WHERE code = ?", (code,)).fetchone()
        return " · ".join(x for x in row if x) if row else None
    except sqlite3.Error:
        return None


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    a = sub.add_parser("add", help="record a product's exact Amazon page")
    a.add_argument("code", help="the product's barcode, as shown on the site")
    a.add_argument("link", help="Amazon product URL or ASIN")
    a.add_argument("--note", default="")
    a.add_argument("--source", default="manual", help="manual (checked by a person) or api")
    r = sub.add_parser("remove", help="remove a product's link (e.g. it pointed to the wrong item)")
    r.add_argument("code")
    sub.add_parser("list", help="show every verified link")
    args = ap.parse_args()

    rows = read()
    if args.cmd == "add":
        code = re.sub(r"\D", "", args.code)
        asin = parse_asin(args.link)
        if not code:
            sys.exit("That barcode has no digits.")
        if not asin:
            sys.exit("Couldn't find an Amazon product ID in that link. Paste the product page's URL "
                     "(it contains /dp/ followed by 10 characters) or the 10-character ID itself.")
        name = product_name(code)
        if name is None:
            print(f"note: {code} isn't in products_clean.db; saved anyway")
        rows[code] = dict(code=code, asin=asin, source=args.source,
                          verified_on=datetime.date.today().isoformat(), note=args.note)
        write(rows)
        print(f"saved: {code}{f' ({name})' if name else ''} -> https://www.amazon.com/dp/{asin}")
    elif args.cmd == "remove":
        if rows.pop(re.sub(r"\D", "", args.code), None) is None:
            sys.exit(f"{args.code} isn't in the registry.")
        write(rows)
        print(f"removed {args.code}")
    else:
        for row in rows.values():
            print(f"{row['code']:15} {row['asin']}  {row['source']:7} {row['verified_on']}  {row['note']}")
        print(f"{len(rows)} verified link(s)")


if __name__ == "__main__":
    main()
