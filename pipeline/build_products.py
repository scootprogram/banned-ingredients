#!/usr/bin/env python3
"""Check every Open Beauty Facts and Open Products Facts product against banlist.db.

Reads the CSV exports (and the packaging TSVs made by extract_packaging.py) from data/raw/,
and writes:
  data/products.db   every product with its verdict (large; not committed)
  products_clean.db  only the products that passed (OK), with full-text search
  products_clean.csv the same, for spreadsheets

Usage: python3 pipeline/build_products.py [--workers 4] [--limit N]
Re-run it whenever the ban list changes.
"""
import argparse
import csv
import gzip
import json
import multiprocessing as mp
import sqlite3
import sys
import time
import urllib.parse
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import banlist  # noqa: E402

RAW = ROOT / "data" / "raw"
# Food and pet food (Open Food Facts, Open Pet Food Facts) are deliberately left out: the list
# covers beauty and household products only.
SOURCES = [  # (source name, CSV export, packaging TSV)
    ("beauty", "en.openbeautyfacts.org.products.csv.gz", "openbeautyfacts.packaging.tsv"),
    ("products", "en.openproductsfacts.org.products.csv.gz", "openproductsfacts.packaging.tsv"),
]
COLUMNS = ["code", "url", "product_name", "brands", "categories_en", "countries_en", "ingredients_text",
           "ingredients_tags", "allergens_en", "traces_en", "packaging_en", "image_small_url"]
VERDICT_NAMES = {banlist.OK: "ok", banlist.EXCLUDED: "excluded", banlist.UNKNOWN: "unknown"}

csv.field_size_limit(10 ** 9)


def tag_names(tags):
    """'en:wheat-flour,fr:farine' -> ['wheat flour'] (English tags only)."""
    return [t[3:].replace("-", " ") for t in tags.split(",") if t.startswith("en:")]


DAIRY_CATEGORIES = ["dairies", "dairy", "cheeses", "cheese", "butters", "butter", "yogurts", "yoghurts", "milks",
                    "creams", "fermented milk products", "milk desserts"]
NOT_DAIRY = ["plant based", "substitute", "substitutes", "non dairy", "dairy free", "vegan", "vegetable", "nut butters",
             "peanut butters", "cocoa butter", "shea butter", "coconut milks", "almond milks", "oat milks",
             "soy milks", "rice milks"]


def dairy_from_categories(p):
    """True when the category says dairy (cheese, butter, yogurt...) even if the ingredient text
    is missing or garbled, e.g. a cheese whose 'ingredients' field holds the nutrition table."""
    cats = f" {banlist.norm(p['categories_en'])} "
    has = lambda terms: any(f" {banlist.norm(t)} " in cats for t in terms)
    return has(DAIRY_CATEGORIES) and not has(NOT_DAIRY)


def ingredients_text(p):
    """Original label text plus Open Food Facts' English tags, so non-English labels still match.

    English tags and allergens go first and traces last, because everything after a
    'may contain' marker only counts for traces-strict bans."""
    parts = tag_names(p["ingredients_tags"]) + [a for a in p["allergens_en"].split(",") if a.strip()]
    if dairy_from_categories(p):
        parts.append("dairy")
    text = ", ".join(parts + ([p["ingredients_text"]] if p["ingredients_text"].strip() else []))
    if p["traces_en"].strip():
        text += ". May contain: " + p["traces_en"]
    return text


def packaging_text(p, extra):
    """Structured packaging parts (material + shape) when known, else free text, else the CSV field."""
    parts, free, materials = extra or ("", "", "")
    pieces = [x for x in (parts, materials) if x]
    if not pieces:
        pieces = [x for x in (free, p["packaging_en"]) if x]
    return "; ".join(pieces)


def amazon_url(p):
    query = " ".join(x for x in (p["brands"].split(",")[0].strip(), p["product_name"].strip()) if x) or p["code"]
    return "https://www.amazon.com/s?k=" + urllib.parse.quote_plus(query)


def read_packaging(path):
    out = {}
    if path.exists():
        with open(path, encoding="utf-8", errors="replace") as f:
            for line in f:
                cols = line.rstrip("\n").split("\t")
                if len(cols) == 4:
                    out[cols[0]] = tuple(cols[1:])
    return out


def read_products(limit):
    """Yield (source, product dict, packaging extra) for every product in every export."""
    for source, csv_name, pack_name in SOURCES:
        path = RAW / csv_name
        if not path.exists():
            print(f"  skipping missing {path}", file=sys.stderr)
            continue
        packaging = read_packaging(RAW / pack_name)
        print(f"  {source}: {len(packaging):,} products with structured packaging", file=sys.stderr)
        with gzip.open(path, "rt", encoding="utf-8", errors="replace") as f:
            reader = csv.reader(f, delimiter="\t", quoting=csv.QUOTE_NONE)
            header = next(reader)
            ix = {c: header.index(c) for c in COLUMNS if c in header}
            for n, row in enumerate(reader):
                if limit and n >= limit:
                    break
                if len(row) != len(header):
                    continue
                p = {c: (row[ix[c]] if c in ix else "") for c in COLUMNS}
                if p["code"] and (p["product_name"] or p["ingredients_text"]):
                    yield source, p, packaging.get(p["code"])


_matcher = None


def init_worker():
    global _matcher
    db = sqlite3.connect(f"file:{banlist.DB_PATH}?mode=ro", uri=True)
    db.row_factory = sqlite3.Row
    _matcher = banlist.MemoryMatcher(db)


def check(item):
    source, p, extra = item
    packaging = packaging_text(p, extra)
    if source == "products":
        # Open Products Facts (durable goods) uses the ingredients field for what the item is
        # made of, e.g. 'Edelstahl'. Checking it as material means each part must be a known material.
        verdict, results, unknown = _matcher.check(None, packaging, p["ingredients_text"],
                                                   p["product_name"], p["categories_en"])
    else:
        verdict, results, unknown = _matcher.check(ingredients_text(p), packaging, None,
                                                   p["product_name"], p["categories_en"])
    banned = sorted({_matcher.ban(b)["slug"] for rows in results.values() for r in rows for b in r[2]})
    return (p["code"], source, p["product_name"], p["brands"], p["categories_en"], p["countries_en"],
            p["ingredients_text"], packaging, VERDICT_NAMES[verdict], ",".join(banned), "; ".join(unknown),
            p["url"], amazon_url(p), p["image_small_url"])


SCHEMA = """
CREATE TABLE products (
    code TEXT, source TEXT, name TEXT, brands TEXT, categories TEXT, countries TEXT,
    ingredients TEXT, packaging TEXT, verdict TEXT, banned TEXT, unknown_reasons TEXT,
    off_url TEXT, amazon_url TEXT, image_url TEXT,
    PRIMARY KEY (source, code)
);
"""


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--workers", type=int, default=mp.cpu_count())
    ap.add_argument("--limit", type=int, help="only read the first N rows of each export (for testing)")
    args = ap.parse_args()

    all_path, clean_path = ROOT / "data" / "products.db", ROOT / "products_clean.db"
    for path in (all_path, clean_path):
        path.unlink(missing_ok=True)
    out = sqlite3.connect(all_path)
    out.executescript("PRAGMA journal_mode = OFF; PRAGMA synchronous = OFF;" + SCHEMA)

    start, counts, batch = time.time(), {}, []
    with mp.Pool(args.workers, initializer=init_worker) as pool:
        for n, row in enumerate(pool.imap(check, read_products(args.limit), chunksize=500), 1):
            counts[row[8]] = counts.get(row[8], 0) + 1
            batch.append(row)
            if len(batch) >= 20000:
                out.executemany("INSERT OR REPLACE INTO products VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)", batch)
                batch.clear()
                rate = n / (time.time() - start)
                print(f"\r  {n:,} products checked ({rate:,.0f}/s)  " +
                      "  ".join(f"{k}={v:,}" for k, v in sorted(counts.items())), end="", file=sys.stderr)
    out.executemany("INSERT OR REPLACE INTO products VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)", batch)
    out.execute("CREATE INDEX idx_verdict ON products (verdict)")
    out.commit()
    print(file=sys.stderr)

    # The clean subset: its own small database with full-text search, plus a CSV.
    clean = sqlite3.connect(clean_path)
    clean.executescript(SCHEMA + """
        CREATE VIRTUAL TABLE products_fts USING fts5(name, brands, categories, ingredients,
                                                     content='products', content_rowid='rowid');
        CREATE TABLE build_info (key TEXT PRIMARY KEY, value TEXT);""")
    clean.execute(f"ATTACH '{all_path}' AS src")
    clean.execute("INSERT INTO products SELECT * FROM src.products WHERE verdict = 'ok' ORDER BY source, name")
    clean.execute("INSERT INTO products_fts (rowid, name, brands, categories, ingredients) "
                  "SELECT rowid, name, brands, categories, ingredients FROM products")
    bans = [r[0] for r in sqlite3.connect(banlist.DB_PATH).execute(
        "SELECT slug FROM banned_ingredients WHERE active = 1 ORDER BY slug")]
    info = {"built_at": time.strftime("%Y-%m-%d %H:%M:%S"), "products_checked": sum(counts.values()),
            **{f"verdict_{k}": v for k, v in counts.items()}, "active_bans": ",".join(bans)}
    clean.executemany("INSERT INTO build_info VALUES (?, ?)", [(k, str(v)) for k, v in info.items()])
    clean.commit()
    clean.execute("DETACH src")
    with open(ROOT / "products_clean.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        cur = clean.execute("SELECT code, source, name, brands, categories, countries, ingredients, packaging, "
                            "off_url, amazon_url FROM products")
        w.writerow([d[0] for d in cur.description])
        w.writerows(cur)
    clean.execute("VACUUM")
    clean.close()
    print(json.dumps(info, indent=2))
    print(f"done in {time.time() - start:,.0f}s", file=sys.stderr)


if __name__ == "__main__":
    main()
