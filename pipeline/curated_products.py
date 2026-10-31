#!/usr/bin/env python3
"""Curated products: a hand-maintained list for products the open databases don't cover well,
mainly household goods (glass bottles, stainless steel containers, wooden brushes...).

Every row is checked by the same checker as every other product, so nothing with plastic gets
in by hand. Only rows with status "approved" are published; research goes in as "pending" for
the owner to review.

List: data/curated_products.csv
  id           barcode (UPC/EAN) when known, else "cs-0001", "cs-0002"...
  status       pending | approved | rejected
  type         household | beauty
  category     what the product is, for browsing: Straws, Utensils, Towels, Jars...
  name, brand
  materials    what the product is made of, every part with its material, e.g.
               "glass jar, glass lid, natural rubber ring, stainless steel clamps"
               (a bare "lid" or "cap" counts as possible hidden plastic)
  ingredients  for beauty products (leave empty for household)
  packaging    e.g. "cardboard box, paper" (empty = not verified yet)
  asin         exact Amazon product ID, when verified; "none" = not sold on Amazon (no Amazon button)
  product_url  the manufacturer's page the details came from
  countries    where it's sold (the site lists "United States" only)
  added_on, notes

Usage:
  python3 pipeline/curated_products.py check     # run the checker over every row
  python3 pipeline/curated_products.py approve <id> [<id>...]
  python3 pipeline/curated_products.py reject <id> [<id>...]
"""
import csv
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import banlist  # noqa: E402

PATH = ROOT / "data" / "curated_products.csv"
FIELDS = ["id", "status", "type", "category", "name", "brand", "materials", "ingredients", "packaging", "asin",
          "product_url", "countries", "added_on", "notes"]
SOURCE = {"household": "products", "beauty": "beauty"}  # the pipeline's source names
VERDICT_NAMES = {banlist.OK: "ok", banlist.EXCLUDED: "excluded", banlist.UNKNOWN: "unknown"}


def read():
    if not PATH.exists():
        return []
    with open(PATH, newline="", encoding="utf-8") as f:
        return [{k: (v or "").strip() for k, v in row.items()} for row in csv.DictReader(f)]


def write(rows):
    with open(PATH, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        w.writeheader()
        w.writerows(rows)


def check_row(matcher, row):
    """-> (verdict name, banned slugs, unknown reasons) using the shared checker."""
    verdict, results, unknown = matcher.check(row["ingredients"] or None, row["packaging"] or None,
                                              row["materials"] or None, row["name"], None)
    banned = sorted({matcher.ban(b)["slug"] for rows in results.values() for r in rows for b in r[2]})
    return VERDICT_NAMES[verdict], banned, unknown


def main():
    if len(sys.argv) < 2 or sys.argv[1] not in ("check", "approve", "reject"):
        sys.exit(__doc__)
    rows = read()
    if sys.argv[1] in ("approve", "reject"):
        ids = set(sys.argv[2:])
        status = "approved" if sys.argv[1] == "approve" else "rejected"
        for row in rows:
            if row["id"] in ids:
                row["status"] = status
                ids.discard(row["id"])
        if ids:
            sys.exit(f"not found: {', '.join(sorted(ids))}")
        write(rows)
        print(f"{status}: {', '.join(sys.argv[2:])}")
        return
    matcher = banlist.MemoryMatcher(banlist.connect())
    for row in rows:
        verdict, banned, unknown = check_row(matcher, row)
        packaging_only = all(not r.startswith(("no ingredients", "material")) for r in unknown)
        shown = verdict == "ok" or (verdict == "unknown" and not banned and packaging_only)
        print(f"{row['id']:14} {row['status']:9} {'LISTABLE' if shown else 'BLOCKED':9} {verdict:9} "
              f"{row['brand']} {row['name']}")
        for why in banned + unknown:
            print(f"{'':25}- {why}")
    print(f"{len(rows)} row(s)")


if __name__ == "__main__":
    main()
