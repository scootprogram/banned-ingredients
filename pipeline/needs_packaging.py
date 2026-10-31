#!/usr/bin/env python3
"""List products that pass every ingredient check and are held back only by missing or
incomplete packaging details: the products where adding packaging info to Open Food Facts
can grow the clean list.

Ranks them US first, then by how likely their category is to be plastic-free and how often
people scan them. Reads data/products.db (from build_products.py) and the CSV exports.

Writes:
  needs_packaging.csv        every candidate with at least a 10% chance of passing, best first
  data/needs_packaging.json  the top candidates, for the Clean Shelf page

Usage: python3 pipeline/needs_packaging.py [--page-limit 2000]
"""
import argparse
import collections
import csv
import gzip
import json
import math
import sqlite3
import sys
import urllib.parse
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw"
CSV_EXPORTS = {"food": "en.openfoodfacts.org.products.csv.gz", "beauty": "en.openbeautyfacts.org.products.csv.gz",
               "products": "en.openproductsfacts.org.products.csv.gz", "petfood": "en.openpetfoodfacts.org.products.csv.gz"}
PLASTIC_BANS = {"plastic", "hidden-plastic", "plastic-like"}
MIN_SUPPORT = 30  # products with known packaging a category needs before its pass rate is trusted
MIN_CHANCE = 0.10  # below this a category almost never passes (sodas, snacks): not worth a contributor's time

# Reasons that adding packaging details can resolve, and how to describe the gap to a contributor.
FIXABLE = {
    "no packaging information": "No packaging recorded",
    "container listed without its cap/lid": "Cap or lid not recorded",
    "packaging part not identified": "A packaging part isn't a recognized material",
}

csv.field_size_limit(10 ** 9)


def fixable_gaps(reasons):
    """-> list of contributor-facing gaps, or None if any reason isn't fixable by adding packaging."""
    gaps = []
    for r in filter(None, reasons.split("; ")):
        key = next((k for k in FIXABLE if r.startswith(k)), None)
        if key is None:
            return None
        detail = r[len(key):].strip(": ")
        gaps.append(FIXABLE[key] + (f" ({detail})" if detail else ""))
    return gaps


def category_pass_rates(db):
    """Among products whose ingredients pass and whose packaging is recorded, the share that pass
    outright, per category. Estimates how likely a product in that category is to be plastic-free."""
    known, ok = collections.Counter(), collections.Counter()
    q = """SELECT categories, verdict, banned, unknown_reasons FROM products
           WHERE unknown_reasons NOT LIKE '%no packaging information%'
             AND unknown_reasons NOT LIKE '%no ingredients%' AND packaging != ''"""
    for categories, verdict, banned, reasons in db.execute(q):
        if banned and not set(banned.split(",")) <= PLASTIC_BANS:
            continue  # excluded for an ingredient: says nothing about packaging
        for cat in {c.strip() for c in (categories or "").split(",") if c.strip()}:
            known[cat] += 1
            ok[cat] += verdict == "ok"
    base = sum(ok.values()) / max(1, sum(known.values()))
    rates = {c: ok[c] / n for c, n in known.items() if n >= MIN_SUPPORT}
    return rates, base


def read_scans(codes):
    """code -> unique_scans_n, from the CSV exports."""
    scans = {}
    for name in CSV_EXPORTS.values():
        path = RAW / name
        if not path.exists():
            continue
        with gzip.open(path, "rt", encoding="utf-8", errors="replace") as f:
            reader = csv.reader(f, delimiter="\t", quoting=csv.QUOTE_NONE)
            header = next(reader)
            if "unique_scans_n" not in header:
                continue
            ic, isc = header.index("code"), header.index("unique_scans_n")
            for row in reader:
                if len(row) == len(header) and row[ic] in codes and row[isc]:
                    scans[row[ic]] = int(float(row[isc]))
    return scans


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--page-limit", type=int, default=2000, help="how many candidates the page shows")
    args = ap.parse_args()
    db = sqlite3.connect(f"file:{ROOT / 'data' / 'products.db'}?mode=ro", uri=True)

    rates, base = category_pass_rates(db)
    print(f"pass rate with packaging recorded: {base:.1%} overall; {len(rates):,} categories rated", file=sys.stderr)

    candidates = []
    for row in db.execute("""SELECT code, source, name, brands, categories, countries, ingredients, packaging,
                                    unknown_reasons, off_url, amazon_url FROM products
                             WHERE verdict = 'unknown' AND banned = ''"""):
        code, source, name, brands, categories, countries, ingredients, packaging, reasons, off_url, amazon = row
        gaps = fixable_gaps(reasons)
        if not gaps:
            continue
        cats = [c.strip() for c in (categories or "").split(",") if c.strip()]
        rated = [rates[c] for c in cats if c in rates]
        chance = max(rated) if rated else base
        candidates.append(dict(code=code, source=source, name=name, brands=brands, categories=categories,
                               countries=countries, ingredients=ingredients, packaging=packaging,
                               gaps="; ".join(gaps), chance=round(chance, 3),
                               us=int("United States" in (countries or "")), off_url=off_url, amazon_url=amazon))
    print(f"{len(candidates):,} candidates; reading scan counts...", file=sys.stderr)

    scans = read_scans({c["code"] for c in candidates})
    for c in candidates:
        c["scans"] = scans.get(c["code"], 0)
        # Likelihood counts more than popularity: a likely pass with a few scans beats a popular long shot.
        c["score"] = round(c["chance"] ** 2 * (1 + math.log1p(c["scans"])), 4)
    total, total_us = len(candidates), sum(c["us"] for c in candidates)
    candidates = [c for c in candidates if c["chance"] >= MIN_CHANCE]
    candidates.sort(key=lambda c: (-c["us"], -c["score"], c["name"] or ""))

    cols = ["code", "source", "name", "brands", "countries", "categories", "gaps", "chance", "scans", "us",
            "packaging", "off_url", "amazon_url"]
    with open(ROOT / "needs_packaging.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        w.writerows(candidates)

    cut = lambda s, n: (s or "")[:n] + ("…" if s and len(s) > n else "")
    top = [dict(c=c["code"], s=c["source"], n=(c["name"] or "").replace("�", ""), b=c["brands"],
                w=c["countries"], g=cut(c["categories"], 160), i=cut(c["ingredients"], 300),
                p=c["packaging"], m=c["gaps"], k=c["chance"], v=c["scans"], u=c["off_url"])
           for c in candidates[:args.page_limit]]
    with open(ROOT / "data" / "needs_packaging.json", "w", encoding="utf-8") as f:
        json.dump(top, f, ensure_ascii=False, separators=(",", ":"))

    print(json.dumps({"blocked_only_by_packaging": total, "of_which_us": total_us,
                      f"listed_chance_{MIN_CHANCE:.0%}_or_more": len(candidates),
                      "listed_us": sum(c["us"] for c in candidates),
                      "chance_25pct_or_more": sum(c["chance"] >= 0.25 for c in candidates),
                      "page_rows": len(top)}, indent=2))


if __name__ == "__main__":
    main()
