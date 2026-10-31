"""Turn products_clean.db into products.json for the Clean Shelf page (read-only on the project).

Usage: python3 site/export_json.py <project root> <output products.json>

Only products recorded as sold in the United States are exported (the site sells through
amazon.com). Products with no recorded name get one built from brand, type and size, marked with `nn`.
Each product carries `k`: "v" when its packaging is verified plastic-free, "u" when the
packaging is still unknown. When data/packaging_votes.json exists (from
pipeline/packaging_votes.py), each product with votes also carries `q`: the majority answer
per packaging question.
"""
import json, re, sqlite3, sys
from pathlib import Path

# Category names too general to describe a product.
GENERIC_CATEGORIES = {"non food products", "open beauty facts", "cosmetic products", "cosmetics", "hygiene",
                      "not tested on animal", "not tested on", "open products facts", "non open products facts",
                      "incorrect product type", "groceries", "health beauty", "personal care", "accessories",
                      "cosmetiques", "cosmetique"}


def product_type(categories):
    """The most specific category that says what the product is: 'Hygiene,Deodorants,Deodorants sticks'
    -> 'Deodorants sticks'."""
    names = [re.sub(r"^[a-z]{2}:", "", c.strip()).replace("-", " ").replace("_", " ").strip()
             for c in (categories or "").split(",")]
    names = [n for n in names if n and re.sub(r"[^a-z ]", "", n.lower()).strip() not in GENERIC_CATEGORIES]
    if not names:
        return ""
    # "Deodorants sticks" -> "Deodorant stick": one product, so singular words.
    words = [w[:-1] if len(w) > 4 and w.endswith("s") and not w.endswith(("ss", "us", "is")) else w
             for w in names[-1].split()]
    kind = " ".join(words)
    return kind[:1].upper() + kind[1:]


def generated_name(brand, categories, quantity):
    """A title for a product with no recorded name: brand + product type + size."""
    brand = (brand or "").split(",")[0].strip()
    kind = product_type(categories)
    title = " ".join(x for x in (brand, kind or ("product" if brand else "")) if x) or "Unnamed product"
    return title + (f" · {quantity.strip()}" if (quantity or "").strip() else "")

root = Path(sys.argv[1])
db = sqlite3.connect(f"file:{root}/products_clean.db?mode=ro", uri=True)
info = dict(db.execute("SELECT key, value FROM build_info"))
labels = {"gluten": "gluten", "soy": "soy", "peanut": "peanuts", "milk": "dairy", "palm-oil": "palm oil",
          "hfcs": "high-fructose corn syrup", "aspartame": "aspartame", "red-40": "Red 40", "msg": "MSG",
          "carrageenan": "carrageenan", "plastic": "plastic of any kind", "hidden-plastic": "plastic linings, lids or pouches",
          "plastic-like": "silicone, synthetic rubber, rayon or cellophane"}
order = list(labels)
bans = sorted(info["active_bans"].split(","), key=lambda s: order.index(s) if s in order else 99)
votes_path = root / "data" / "packaging_votes.json"
votes = json.loads(votes_path.read_text(encoding="utf-8")) if votes_path.exists() else {}

cut = lambda s, n: (s or "")[:n] + ("…" if s and len(s) > n else "")
products = []
for c, s, n, b, g, w, i, p, u, verdict, qty in db.execute(
        "SELECT code, source, name, brands, categories, countries, ingredients, packaging, off_url, verdict, quantity "
        "FROM products WHERE ',' || countries || ',' LIKE '%,United States,%' "
        "ORDER BY verdict != 'ok', source, name"):
    r = dict(c=c, s=s, n=(n or "").replace("&quot;", '"').strip(), b=b, g=cut(g, 200), w=w, i=cut(i, 600), p=p, u=u,
             k="v" if verdict == "ok" else "u")
    if not r["n"]:  # no recorded name: build one, and mark it as built
        r["n"], r["nn"] = generated_name(b, g, qty), 1
    if c in votes:
        r["q"] = votes[c]
    products.append({k: (v.replace("�", "") if isinstance(v, str) else v) for k, v in r.items()})

meta = {"bans": [labels.get(b, b) for b in bans], "checked": info["products_checked"], "built": info["built_at"][:10]}
json.dump({"meta": meta, "products": products}, open(sys.argv[2], "w", encoding="utf-8"),
          ensure_ascii=False, separators=(",", ":"))
print(len(products), "products,", sum(r["k"] == "v" for r in products), "with verified packaging,",
      sum("q" in r for r in products), "with votes")
