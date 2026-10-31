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
# Verified Amazon product IDs (pipeline/amazon_links.py): products here link straight to their page.
links_path = root / "data" / "amazon_links.csv"
asins = {}
if links_path.exists():
    import csv
    with open(links_path, newline="", encoding="utf-8") as f:
        asins = {row["code"]: row["asin"] for row in csv.DictReader(f) if row.get("asin")}
# Curated products (pipeline/curated_products.py): their Amazon IDs and materials.
curated = {}
curated_path = root / "data" / "curated_products.csv"
if curated_path.exists():
    import csv
    with open(curated_path, newline="", encoding="utf-8") as f:
        curated = {row["id"]: row for row in csv.DictReader(f) if row.get("status") == "approved"}
        asins.update({k: r["asin"] for k, r in curated.items() if r.get("asin") and r["asin"] != "none"})

# Material names -> the big label shown on the product (design principle: as large as the title).
MATERIAL_LABELS = [("stainless steel", "STAINLESS STEEL"), ("cast iron", "CAST IRON"), ("natural rubber", "NATURAL RUBBER"),
                   ("glass", "GLASS"), ("steel", "STEEL"), ("aluminum", "ALUMINUM"), ("aluminium", "ALUMINUM"),
                   ("copper", "COPPER"), ("brass", "BRASS"), ("tin", "TIN"), ("ceramic", "CERAMIC"),
                   ("porcelain", "PORCELAIN"), ("stoneware", "STONEWARE"), ("bamboo", "BAMBOO"), ("wood", "WOOD"),
                   ("beech", "WOOD"), ("cotton", "COTTON"), ("linen", "LINEN"), ("hemp", "HEMP"), ("wool", "WOOL"),
                   ("sisal", "SISAL"), ("jute", "JUTE"), ("coconut fiber", "COCONUT FIBER"), ("coir", "COCONUT FIBER"),
                   ("tampico", "PLANT FIBER"), ("horsehair", "HORSEHAIR"), ("loofah", "LOOFAH"), ("cork", "CORK"),
                   ("paper", "PAPER"), ("beeswax", "BEESWAX"), ("stone", "STONE"), ("silk", "SILK")]


def material_labels(materials):
    text, labels = f" {(materials or '').lower()} ", []
    for word, label in MATERIAL_LABELS:
        if re.search(rf"\b{re.escape(word)}", text) and label not in labels:
            if label == "STEEL" and "STAINLESS STEEL" in labels:
                continue
            labels.append(label)
            text = text.replace(word, " ")
    return labels


# Browsing, layer 1: material groups (household), from the material labels.
MATERIAL_GROUPS = {"STAINLESS STEEL": "Stainless steel & metal", "STEEL": "Stainless steel & metal",
                   "CAST IRON": "Stainless steel & metal", "ALUMINUM": "Stainless steel & metal",
                   "COPPER": "Stainless steel & metal", "BRASS": "Stainless steel & metal", "TIN": "Stainless steel & metal",
                   "WOOD": "Wood & bamboo", "BAMBOO": "Wood & bamboo", "CORK": "Wood & bamboo",
                   "COTTON": "Cotton & linen", "LINEN": "Cotton & linen", "HEMP": "Cotton & linen", "SILK": "Cotton & linen",
                   "GLASS": "Glass", "WOOL": "Wool", "PAPER": "Paper",
                   "PLANT FIBER": "Natural fibers", "SISAL": "Natural fibers", "JUTE": "Natural fibers",
                   "COCONUT FIBER": "Natural fibers", "LOOFAH": "Natural fibers", "HORSEHAIR": "Natural fibers",
                   "CERAMIC": "Ceramic & stone", "PORCELAIN": "Ceramic & stone", "STONEWARE": "Ceramic & stone",
                   "STONE": "Ceramic & stone"}

# Browsing, layer 2 for beauty: product type from categories and name (first match wins).
BEAUTY_TYPES = [("Toothpaste", ["toothpaste", "dentifrice", "tooth paste", "zahnpasta"]),
                ("Mouthwash", ["mouthwash", "mouth wash", "mouth rinse", "rinse"]),
                ("Deodorant", ["deodorant", "antiperspirant", "deodorante"]),
                ("Shampoo", ["shampoo", "shampoing"]), ("Conditioner", ["conditioner", "apres shampooing"]),
                ("Body wash", ["body wash", "shower gel", "bath", "gel douche"]),
                ("Soap", ["soap", "savon", "seife"]),
                ("Sunscreen", ["sunscreen", "suncreen", "sun protection", "spf", "solaire"]),
                ("Makeup", ["makeup", "mascara", "foundation", "lipstick", "eyeshadow", "nail polish", "nail", "concealer"]),
                ("Lip care", ["lip balm", "lip", "lips", "chapstick"]),
                ("Supplements & medicine", ["supplement", "supplements", "vitamin", "vitamins", "tablets", "capsules",
                                            "gummies", "antacid", "medicine", "melatonin", "omega", "probiotic", "collagen"]),
                ("Lotion & cream", ["lotion", "cream", "creme", "moisturizer", "moisturiser", "butter", "balm"]),
                ("Hair care", ["hair", "styling", "curl"]), ("Oils", ["oil", "oils"])]


def beauty_type(categories, name):
    text = " " + re.sub(r"[^a-z0-9]+", " ", f"{categories} {name}".lower()) + " "
    for kind, words in BEAUTY_TYPES:
        if any(f" {w} " in text for w in words):
            return kind
    return "Other beauty"


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
    if c in curated:
        r["cu"] = 1
        if curated[c].get("materials"):
            r["m"] = material_labels(curated[c]["materials"])
            r["mg"] = list(dict.fromkeys(MATERIAL_GROUPS[m] for m in r["m"] if m in MATERIAL_GROUPS))
        if curated[c].get("asin") == "none":  # not sold on Amazon: no Amazon button
            r["na"] = 1
        r["t"] = curated[c].get("category") or "Other"
        if curated[c].get("type") == "cleaning":  # judged by ingredients: browsed under "Cleaning"
            r["mg"] = ["Cleaning"]
    elif s == "beauty":
        r["t"] = beauty_type(g, n)
    else:
        r["t"] = "Other household"
    if c in asins:
        r["a"] = asins[c]
    if c in votes:
        r["q"] = votes[c]
    products.append({k: (v.replace("�", "") if isinstance(v, str) else v) for k, v in r.items()})

meta = {"bans": [labels.get(b, b) for b in bans], "checked": info["products_checked"], "built": info["built_at"][:10]}
json.dump({"meta": meta, "products": products}, open(sys.argv[2], "w", encoding="utf-8"),
          ensure_ascii=False, separators=(",", ":"))
print(len(products), "products,", sum(r["k"] == "v" for r in products), "with verified packaging,",
      sum("q" in r for r in products), "with votes,", sum("a" in r for r in products), "with verified Amazon links")
