#!/usr/bin/env python3
"""Search the clean products (no banned ingredients, no plastic) built by pipeline/build_products.py.

Examples:
  python3 search.py "olive oil"
  python3 search.py soap --source beauty
  python3 search.py chocolate --country "United States" --limit 50
  python3 search.py --stats
"""
import argparse
import sqlite3
import sys
from pathlib import Path

DB = Path(__file__).resolve().parent / "products_clean.db"


def fts_query(text):
    """Every word must match, as a prefix: 'olive oi' -> "olive"* AND "oi"*."""
    words = [w.replace('"', "") for w in text.split() if w.strip('"')]
    return " AND ".join(f'"{w}"*' for w in words)


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0],
                                 epilog="\n".join(__doc__.splitlines()[2:]),
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("query", nargs="?", default="", help="words to find in name, brand, category or ingredients")
    ap.add_argument("--source", choices=["food", "beauty", "products", "petfood"])
    ap.add_argument("--country", help="e.g. 'United States' (matches the countries the product is sold in)")
    ap.add_argument("--limit", type=int, default=20)
    ap.add_argument("--stats", action="store_true", help="show how the last build went")
    args = ap.parse_args()
    if not DB.exists():
        sys.exit(f"{DB.name} not found; run pipeline/build_products.py first")
    db = sqlite3.connect(DB)

    if args.stats:
        for k, v in db.execute("SELECT key, value FROM build_info"):
            print(f"{k:>20}: {v}")
        for src, n in db.execute("SELECT source, count(*) FROM products GROUP BY 1 ORDER BY 2 DESC"):
            print(f"{'clean ' + src:>20}: {n:,}")
        return

    sql, params = "SELECT p.* FROM products p", []
    where = []
    if args.query.strip():
        sql += " JOIN products_fts f ON f.rowid = p.rowid"
        where.append("products_fts MATCH ?")
        params.append(fts_query(args.query))
    if args.source:
        where.append("p.source = ?")
        params.append(args.source)
    if args.country:
        where.append("p.countries LIKE ?")
        params.append(f"%{args.country}%")
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += (" ORDER BY f.rank" if args.query.strip() else " ORDER BY p.name") + " LIMIT ?"
    params.append(args.limit)

    cur = db.execute(sql, params)
    cols = [d[0] for d in cur.description]
    rows = [dict(zip(cols, r)) for r in cur]
    for r in rows:
        print(f"{r['name'] or '(no name)'} — {r['brands'] or 'unknown brand'}  [{r['source']}]")
        print(f"   packaging:   {r['packaging']}")
        if r["ingredients"]:
            print(f"   ingredients: {r['ingredients'][:160]}{'…' if len(r['ingredients']) > 160 else ''}")
        print(f"   sold in:     {r['countries'] or '?'}")
        print(f"   amazon:      {r['amazon_url']}")
        print(f"   details:     {r['off_url']}\n")
    print(f"{len(rows)} result(s)" + (" (use --limit for more)" if len(rows) == args.limit else ""))


if __name__ == "__main__":
    main()
