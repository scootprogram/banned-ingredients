"""Turn products_clean.db into products.json for the Clean Shelf page (read-only on the project)."""
import json, sqlite3, sys
root = sys.argv[1]
sys.path.insert(0, root)
from banlist import norm, CLOSURE_WORDS, CONTAINER_WORDS
GLASS = CONTAINER_WORDS | {"glass", "vial", "vials", "verre", "glas", "vidrio", "vetro", "vidro", "стекло"}
GAS = {"protective", "gas", "atmosphere", "modified", "nitrogen", "azote", "n2", "co2", "carbon", "dioxide", "inert"}

def closure_missing(packaging):
    """Glass container with no cap/lid listed, or only a protective gas listed (sealed tray)."""
    words = set(norm(packaging).split())
    return bool((words & GLASS and not words & CLOSURE_WORDS) or (words and words <= GAS))

db = sqlite3.connect(f"file:{root}/products_clean.db?mode=ro", uri=True)
info = dict(db.execute("SELECT key, value FROM build_info"))
labels = {"gluten": "gluten", "soy": "soy", "peanut": "peanuts", "milk": "dairy", "palm-oil": "palm oil",
          "hfcs": "high-fructose corn syrup", "aspartame": "aspartame", "red-40": "Red 40", "msg": "MSG",
          "carrageenan": "carrageenan", "plastic": "plastic of any kind", "hidden-plastic": "plastic linings, lids or pouches",
          "plastic-like": "silicone, synthetic rubber, rayon or cellophane"}
order = list(labels)
bans = sorted(info["active_bans"].split(","), key=lambda s: order.index(s) if s in order else 99)
cut = lambda s, n: (s or "")[:n] + ("…" if s and len(s) > n else "")
products = [dict(c=c, s=s, n=n.replace("&quot;", '"').strip(), b=b, g=cut(g, 200), w=w, i=cut(i, 600), p=p, u=u, x=int(closure_missing(p)))
            for c, s, n, b, g, w, i, p, u in db.execute(
                "SELECT code, source, name, brands, categories, countries, ingredients, packaging, off_url FROM products")]
meta = {"bans": [labels.get(b, b) for b in bans], "checked": info["products_checked"], "built": info["built_at"][:10]}
products = [{k: (v.replace("\ufffd", "") if isinstance(v, str) else v) for k, v in r.items()} for r in products]
json.dump({"meta": meta, "products": products}, open(sys.argv[2], "w"), ensure_ascii=False, separators=(",", ":"))
print(len(products), "products")
