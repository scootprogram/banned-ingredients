#!/usr/bin/env python3
"""Manage the banned-ingredients database and check products against it.

Run `python3 banlist.py -h` for the list of commands.
"""
import argparse
import csv
import json
import re
import sqlite3
import sys
import unicodedata
from pathlib import Path

HERE = Path(__file__).resolve().parent
DB_PATH = HERE / "banlist.db"
SCHEMA_PATH = HERE / "schema.sql"
TAXONOMY_DIR = HERE / "data" / "taxonomy"
TAXONOMY_FILES = {"ingredient": ["ingredients.txt", "additives.txt"],
                  "packaging": ["packaging_materials.txt"]}
FIELDS = ("ingredients", "packaging", "material")
FIELD_KIND = {"ingredients": "ingredient", "packaging": "packaging", "material": "packaging"}
MAX_PHRASE_WORDS = 6  # longest alias/synonym we try to match, in words

TRACE_RE = re.compile(r"\b(may contain|may also contain|traces? of|made in a facility|"
                      r"processed in a facility|produced in a facility|manufactured on)\b"
                      r"(?: that also processes| that processes)?", re.I)
NEGATIONS = {"no", "non", "without", "zero"}
# Packaging/material words that say nothing about what the thing is made of.
FILLER_WORDS = {"recyclable", "recycled", "fsc", "certified", "eco", "sustainable", "sustainably", "sourced",
                "100", "percent", "pure", "natural", "organic", "new", "the", "a", "of", "with", "en",
                "recyclable", "recyclables", "recycle", "recyclage", "recyclabel", "recycelbar", "recyclebar",
                "reciclable", "riciclabile", "de", "en", "et", "und", "y", "e", "di", "da", "van", "het"}
NO_PACKAGING = {"none", "no packaging", "unpackaged", "loose", "bulk", "package free", "packaging free"}

# Packaging completeness rules: a part list can name only safe materials and still not
# prove the product is plastic-free.
# 1. A container listed without its closure: the closure (cap, lid, pump) is usually plastic
#    or plastic-lined, so it must be listed and pass on its own.
CONTAINER_WORDS = {"bottle", "bottles", "jar", "jars", "flacon", "flask", "jug", "carafe", "decanter",
                   "bouteille", "bocal", "pot", "flasche", "botella", "frasco", "tarro", "bottiglia",
                   "barattolo", "vasetto", "fles", "pot", "бутылка", "банка", "флакон"}
CLOSURE_WORDS = {"lid", "lids", "cap", "caps", "cork", "stopper", "closure", "top", "couvercle", "bouchon",
                 "capsule", "opercule", "deckel", "verschluss", "korken", "tapa", "tapon", "tappo", "coperchio",
                 "capsula", "dop", "deksel", "kurk", "крышка", "пробка", "pump", "sprayer", "dropper"}
# Glass packaging with no shape ('glass', 'clear glass') is nearly always a jar or bottle, so it
# counts as a container too. A 'glass lid' names its own closure and passes.
GLASS_WORDS = {"glass", "vial", "vials", "verre", "glas", "vidrio", "vetro", "vidro", "vidre", "szklo", "szkło", "cristal",
               "sticla", "sklo", "staklo", "steklo", "uveg", "lasi", "glasflasche", "glasflaschen", "стекло",
               "стъкло", "скло"}
# 3. A protective gas fills a sealed, gas-tight pack (usually a plastic tray or film). Unless a
#    glass or metal container is listed to hold it, that pack is missing from the list.
GAS_WORDS = {"protective", "gas", "gases", "atmosphere", "modified", "nitrogen", "azote", "n2", "co2", "carbon",
             "dioxide", "inert", "argon", "gaz", "protecteur", "schutzgas", "schutzatmosphare", "atmosfera",
             "protettiva", "protectora"}
# 2. Metal packaging other than plain foil: cans, tins, trays and lids are nearly always
#    plastic-lined or lacquered, whatever the record calls them.
METAL_WORDS = {"metal", "metals", "metallic", "steel", "aluminium", "aluminum", "alu", "tin", "tinplate",
               "tin plated", "plated", "metall", "acier", "fer", "stahl", "acero", "acciaio", "alluminio",
               "aluminio", "ferro", "blech", "metaal", "staal", "металл", "сталь", "алюминий", "жесть"}
FOIL_WORDS = {"foil", "foils", "folie", "feuille", "papier", "paper"}

# Product context rules (need the product's name and categories, see Matcher.check).
# 4. Liquids and wet or fresh foods can't sit in plain paper or cardboard: there is a lined
#    carton, tray, pot, pouch or blister inside that the record doesn't list.
LIQUID_CATEGORIES = ["fruit based beverages", "juice drinks", "sweetened beverages", "unsweetened beverages",
                     "artificially sweetened beverages", "non alcoholic beverages", "alcoholic beverages",
                     "carbonated", "fruit juices",
                     "meats", "fishes", "seafood", "meals", "prepared meals", "terrines", "pates", "rillettes",
                     "compotes", "fruit purees", "apple sauces", "baby foods", "cheeses", "yogurts",
                     "dairy desserts", "sausages", "hams", "poultries", "dietary supplements",
                     "food supplements", "vitamins", "tomato purees", "tomato sauces", "crushed tomatoes",
                     "tomatoes and their products",
                     "juices", "nectars", "milks", "waters", "soups", "broths", "sodas", "smoothies",
                     "soft drinks", "carbonated drinks", "plant based milks", "milk substitutes", "wines", "beers",
                     "ciders", "kombucha", "iced teas", "lemonades", "cooking creams", "creams", "drinkable",
                     "sauces", "passata", "coconut milks", "liquid", "syrups", "vinegars", "oils"]
DRY_CATEGORIES = ["dried", "dehydrated", "powder", "powders", "instant", "mixes", "cubes", "granulated", "flakes"]
# 5. Frozen-food boxes are plastic-coated or hold an inner bag; canned food means a lined can.
FROZEN_CATEGORIES = ["frozen", "surgeles", "tiefkuhl", "congelados", "surgelati", "ice creams", "ice cream",
                     "sorbets", "glace", "glaces", "glace aux fruits", "smoothie bowl", "smoothie bowls"]
CANNED_CATEGORIES = ["canned", "tinned", "conserves", "preserves in cans"]
# A volume in the name ('10 x 20 cl', '1 L', '330 ml') or water as the first ingredient also
# marks a liquid.
VOLUME_RE = re.compile(r"\b\d+(?:[.,]\d+)?\s?(?:ml|cl|dl|l|lt|ltr|litre|litres|liter|liters|fl oz)\b", re.I)
WATER_WORDS = {"water", "eau", "wasser", "agua", "acqua", "woda", "вода", "aqua", "vann", "vatten", "vesi"}
# ...as does meat or fish as the first ingredient (a pâté or fish with no category is usually canned).
MEAT_FISH_WORDS = {"meat", "viande", "fleisch", "carne", "pork", "porc", "schwein", "beef", "boeuf", "rind",
                   "chicken", "poulet", "huhn", "pollo", "turkey", "dinde", "duck", "canard", "lamb", "agneau",
                   "fish", "poisson", "fisch", "pescado", "pesce", "tuna", "thon", "thunfisch", "atun", "tonno",
                   "salmon", "saumon", "lachs", "sardine", "sardines", "mackerel", "maquereau", "makrele"}
# 5b. Products that nearly always come in an inner bag or wrapper inside the box.
INNER_BAG_CATEGORIES = ["breakfast cereals", "biscuits", "cookies", "crackers", "puffed cereal cakes", "rice cakes",
                        "cereal cakes", "crisps", "chips", "cereal bars", "snacks", "confectioneries", "candies",
                        "cake mixes", "dessert mixes", "pastry helpers"]
# 6. Names (or categories) that announce packaging parts the record leaves out (tea bags,
#    capsules, pouches).
NAME_HINTS = ["sachet", "sachets", "capsule", "capsules", "capsulas", "kapseln", "pods", "pod", "k cup", "k cups",
              "gourde", "gourdes", "pouch", "pouches", "doypack", "kochbeutel", "boil in bag", "teebeutel",
              "aufgussbeutel", "bolsitas", "bustine", "filtri", "infusettes", "tea bags", "teabags", "tea bag",
              "teabag", "spray", "tube", "tubes", "stick pack", "portions", "squeeze", "coffee capsules",
              "coffee pods"]

# Exit codes for `check`.
OK, EXCLUDED, UNKNOWN = 0, 1, 2


# ---------------------------------------------------------------- text helpers

def norm(text):
    """Lowercase, strip accents and punctuation, collapse whitespace. Keeps letters of every
    script (Cyrillic, Greek, CJK, ...), so non-Latin labels are matched rather than dropped."""
    text = unicodedata.normalize("NFKD", text)
    text = "".join(c for c in text if not unicodedata.combining(c))
    text = text.lower().replace("&", " and ")
    text = re.sub(r"[\W_]+", " ", text)
    return " ".join(text.split())


def taxonomy_id(lang, name):
    """Open Food Facts style node id: 'en: Palm Oil' -> 'en:palm-oil'."""
    return f"{lang.strip()}:{norm(name).replace(' ', '-')}"


def split_list(text):
    """Split label text into individual phrases.

    'Flour (wheat, malt), sugar, Red No. 40' -> ['flour', 'wheat', 'malt', 'sugar', 'red no. 40'].
    """
    text = re.sub(r"\b[a-z]{2}:(?=[a-z])", "", text.lower())  # Open Food Facts tags like 'en:glass'
    parts = re.split(r"[,;:()\[\]{}/+]|\.(?!\s*\d)|\band\b|\bor\b", text)
    return [p.strip() for p in parts if norm(p)]


def csv_fields(value):
    """'ingredients|packaging' or 'ingredients,packaging' -> 'ingredients,packaging' (validated)."""
    fields = [f.strip() for f in re.split(r"[|,]", value or "") if f.strip()]
    bad = [f for f in fields if f not in FIELDS]
    if bad:
        sys.exit(f"Unknown field(s) {bad}; use {', '.join(FIELDS)}")
    return ",".join(f for f in FIELDS if f in fields)


def negated(words, start):
    return ((start > 0 and words[start - 1] in NEGATIONS)
            or (start > 1 and words[start - 2:start] in (["free", "of"], ["free", "from"])))


# ---------------------------------------------------------------- database

def connect():
    db = sqlite3.connect(DB_PATH)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA foreign_keys = ON")
    cols = {r[1] for r in db.execute("PRAGMA table_info(banned_ingredients)")}
    if "taxonomy_id" in cols:
        sys.exit("banlist.db uses the old format. Export it first with the old tool, or rebuild with\n"
                 "  rm banlist.db && python3 banlist.py init --seed seed.csv")
    db.executescript(SCHEMA_PATH.read_text())
    return db


def log(db, ingredient_id, action, details=None, note=None):
    db.execute("INSERT INTO change_log (ingredient_id, action, details, note) VALUES (?, ?, ?, ?)",
               (ingredient_id, action, json.dumps(details) if details else None, note))


def get_ban(db, slug):
    row = db.execute("SELECT * FROM banned_ingredients WHERE slug = ?", (slug,)).fetchone()
    if row is None:
        sys.exit(f"No entry with slug '{slug}'. Try `list --all`.")
    return row


def add_aliases(db, ingredient_id, aliases, fields=None):
    added = []
    for alias in aliases:
        if norm(alias):
            cur = db.execute("INSERT OR IGNORE INTO aliases (ingredient_id, alias, alias_norm, fields) "
                             "VALUES (?, ?, ?, ?)", (ingredient_id, alias.strip(), norm(alias), fields or None))
            if cur.rowcount:
                added.append(alias.strip())
    return added


def add_exceptions(db, ingredient_id, phrases):
    added = []
    for phrase in phrases:
        if norm(phrase):
            cur = db.execute("INSERT OR IGNORE INTO exceptions (ingredient_id, phrase, phrase_norm) VALUES (?, ?, ?)",
                             (ingredient_id, phrase.strip(), norm(phrase)))
            if cur.rowcount:
                added.append(phrase.strip())
    return added


def add_roots(db, ingredient_id, kind, node_ids, warn=True):
    added = []
    for node_id in node_ids:
        node_id = node_id.strip()
        if not node_id:
            continue
        if warn and not db.execute("SELECT 1 FROM taxonomy_nodes WHERE kind = ? AND id = ?", (kind, node_id)).fetchone():
            print(f"  warning: {kind} taxonomy id '{node_id}' not found (see `search`); saved anyway")
        cur = db.execute("INSERT OR IGNORE INTO ban_roots (ingredient_id, kind, node_id) VALUES (?, ?, ?)",
                         (ingredient_id, kind, node_id))
        if cur.rowcount:
            added.append(f"{kind}:{node_id}" if kind == "packaging" else node_id)
    return added


def upsert_ban(db, slug, name, applies_to="ingredients", category=None, reason=None, strictness="exact",
               include_children=True, ingredient_roots=(), packaging_roots=(), aliases=(),
               material_aliases=(), exceptions=(), note=None):
    """Create a ban, or update the existing one with the same slug. Lists are only ever added to."""
    existing = db.execute("SELECT * FROM banned_ingredients WHERE slug = ?", (slug,)).fetchone()
    fields = dict(name=name, applies_to=csv_fields(applies_to) or "ingredients", category=category or None,
                  reason=reason or None, strictness=strictness or "exact", include_children=int(include_children))
    if existing is None:
        cur = db.execute("""INSERT INTO banned_ingredients
                            (slug, name, applies_to, category, reason, strictness, include_children)
                            VALUES (:slug, :name, :applies_to, :category, :reason, :strictness, :include_children)""",
                         dict(fields, slug=slug))
        ban_id, action, changes = cur.lastrowid, "add", dict(fields)
        aliases = [slug, name, *aliases]
    else:
        ban_id, action = existing["id"], "edit"
        changes = {k: v for k, v in fields.items() if existing[k] != v}
        if changes:
            sets = ", ".join(f"{k} = :{k}" for k in changes)
            db.execute(f"UPDATE banned_ingredients SET {sets}, updated_at = datetime('now') WHERE id = :id",
                       dict(changes, id=ban_id))
    for key, added in (("roots_added", add_roots(db, ban_id, "ingredient", ingredient_roots)
                                       + add_roots(db, ban_id, "packaging", packaging_roots)),
                       ("aliases_added", add_aliases(db, ban_id, aliases)),
                       ("material_aliases_added", add_aliases(db, ban_id, material_aliases, "packaging,material")),
                       ("exceptions_added", add_exceptions(db, ban_id, exceptions))):
        if added:
            changes[key] = added
    if changes:
        log(db, ban_id, action, changes, note)
    return ban_id, action if changes else "unchanged"


# ---------------------------------------------------------------- taxonomy

def parse_taxonomy(path):
    """Yield (node_id, display_name, [(lang, synonym), ...], [(lang, parent_name), ...]) per entry."""
    block = []
    for line in path.read_text(encoding="utf-8").splitlines() + [""]:
        line = line.strip()
        if line:
            if not line.startswith("#"):
                block.append(line)
            continue
        if not block:
            continue
        lines, block = block, []
        if re.match(r"^(synonyms|stopwords):", lines[0]):
            continue
        parents, synonyms, node_id, name = [], [], None, None
        for entry in lines:
            if entry.startswith("<"):
                lang, _, value = entry[1:].strip().partition(":")
                parents.append((lang.strip(), value.strip()))
                continue
            if re.match(r"^[a-z0-9_]+:[a-z]{2,3}:", entry):  # property line, e.g. wikidata:en: Q123
                continue
            m = re.match(r"^([a-z]{2,3}(?:[-_][a-z]+)?):\s*(.+)$", entry)
            if not m:
                continue
            lang, values = m.groups()
            words = [v.replace("\\,", ",").strip() for v in re.split(r"(?<!\\),", values)]
            words = [w for w in words if norm(w)]
            if not words:
                continue
            if node_id is None:
                node_id, name = taxonomy_id(lang, words[0]), words[0]
            synonyms += [(lang, w) for w in words]
        if node_id:
            yield node_id, name, synonyms, parents


def resolve(db, kind, lang, text):
    """A parent reference like '< xx: PE' names a node by any of its synonyms, not only by its id."""
    node_id = taxonomy_id(lang, text)
    if db.execute("SELECT 1 FROM taxonomy_nodes WHERE kind = ? AND id = ?", (kind, node_id)).fetchone():
        return node_id
    row = db.execute("SELECT node_id FROM taxonomy_synonyms WHERE kind = ? AND text_norm = ? "
                     "ORDER BY lang NOT IN (?, 'xx'), lang != 'en' LIMIT 1", (kind, norm(text), lang)).fetchone()
    return row["node_id"] if row else node_id


def load_taxonomy(db):
    for table in ("taxonomy_nodes", "taxonomy_synonyms", "taxonomy_parents"):
        db.execute(f"DELETE FROM {table}")
    counts = {}
    for kind, files in TAXONOMY_FILES.items():
        pending = []
        for fname in files:
            path = TAXONOMY_DIR / fname
            if not path.exists():
                print(f"  skipping missing {path}")
                continue
            for node_id, name, synonyms, parents in parse_taxonomy(path):
                db.execute("INSERT OR IGNORE INTO taxonomy_nodes (kind, id, name) VALUES (?, ?, ?)", (kind, node_id, name))
                db.executemany("INSERT INTO taxonomy_synonyms (kind, node_id, lang, text_norm) VALUES (?, ?, ?, ?)",
                               {(kind, node_id, lang, norm(s)) for lang, s in synonyms})
                pending += [(node_id, lang, text) for lang, text in parents]
                counts[kind] = counts.get(kind, 0) + 1
        for child, lang, text in pending:  # after every node exists, so references resolve
            parent = resolve(db, kind, lang, text)
            if parent != child:
                db.execute("INSERT OR IGNORE INTO taxonomy_parents (kind, child_id, parent_id) VALUES (?, ?, ?)",
                           (kind, child, parent))
    return counts


def descendants(db, kind, node_id):
    rows = db.execute("""WITH RECURSIVE d(id) AS (
                             SELECT ? UNION
                             SELECT p.child_id FROM taxonomy_parents p JOIN d ON p.kind = ? AND p.parent_id = d.id)
                         SELECT d.id, n.name FROM d LEFT JOIN taxonomy_nodes n ON n.kind = ? AND n.id = d.id""",
                      (node_id, kind, kind)).fetchall()
    return [(r["id"], r["name"]) for r in rows]


def covered_nodes(db, ban):
    """Every (kind, node_id, name) a ban covers through its taxonomy roots."""
    out = set()
    for r in db.execute("SELECT kind, node_id FROM ban_roots WHERE ingredient_id = ?", (ban["id"],)):
        nodes = descendants(db, r["kind"], r["node_id"]) if ban["include_children"] else [(r["node_id"], None)]
        out |= {(r["kind"], n, name) for n, name in nodes}
    return sorted(out)


# ---------------------------------------------------------------- matching

class Matcher:
    """Checks product text against the active ban list using indexed lookups.

    Nothing is preloaded: each phrase costs a few index lookups (its word n-grams against
    `aliases` and the taxonomy, each taxonomy hit's ancestors against `ban_roots`), so
    speed doesn't depend on how many bans exist.
    """

    def __init__(self, db):
        self.db = db
        self.bans = {}  # id -> row, filled as bans are hit

    def ban(self, ban_id):
        if ban_id not in self.bans:
            self.bans[ban_id] = self.db.execute("SELECT * FROM banned_ingredients WHERE id = ?", (ban_id,)).fetchone()
        return self.bans[ban_id]

    def required_fields(self):
        """Which product fields the active bans need in order to give a confident verdict."""
        fields = set()
        for (applies_to,) in self.db.execute("SELECT DISTINCT applies_to FROM banned_ingredients WHERE active = 1"):
            fields |= set(applies_to.split(","))
        return fields

    def alias_hits(self, gram, field):
        return [r[0] for r in self.db.execute(
            """SELECT a.ingredient_id FROM aliases a JOIN banned_ingredients b ON b.id = a.ingredient_id
               WHERE a.alias_norm = :g AND b.active = 1
                 AND instr(',' || b.applies_to || ',', ',' || :f || ',')
                 AND (a.fields IS NULL OR instr(',' || a.fields || ',', ',' || :f || ','))""",
            {"g": gram, "f": field})]

    def lookup_node(self, kind, gram):
        row = self.db.execute("SELECT node_id FROM taxonomy_synonyms WHERE kind = ? AND text_norm = ? "
                              "ORDER BY lang != 'en' LIMIT 1", (kind, gram)).fetchone()
        return row["node_id"] if row else None

    def node_hits(self, kind, node_id, field):
        """Active bans on this node, or on an ancestor of it when the ban includes children."""
        rows = self.db.execute("""WITH RECURSIVE up(id, depth) AS (
                                      SELECT :n, 0 UNION
                                      SELECT p.parent_id, up.depth + 1 FROM taxonomy_parents p
                                      JOIN up ON p.kind = :k AND p.child_id = up.id)
                                  SELECT DISTINCT b.id FROM up
                                  JOIN ban_roots r ON r.kind = :k AND r.node_id = up.id
                                  JOIN banned_ingredients b ON b.id = r.ingredient_id
                                  WHERE b.active = 1 AND (up.depth = 0 OR b.include_children = 1)
                                    AND instr(',' || b.applies_to || ',', ',' || :f || ',')""",
                               {"n": node_id, "k": kind, "f": field})
        return [r[0] for r in rows]

    def find_nodes(self, kind, words):
        """Greedy longest-match of the phrase's words against the taxonomy -> [(start, end, node_id)]."""
        found, i = [], 0
        while i < len(words):
            for size in range(min(MAX_PHRASE_WORDS, len(words) - i), 0, -1):
                gram = " ".join(words[i:i + size])
                if gram.replace(" ", "").isdigit():  # recycling codes like '5' would match '5% cotton'
                    continue
                node = self.lookup_node(kind, gram)
                if node:
                    found.append((i, i + size, node))
                    i += size
                    break
            else:
                i += 1
        return found

    def excepted(self, ban_id, phrase_norm):
        padded = f" {phrase_norm} "
        exceptions = self.db.execute("SELECT phrase_norm FROM exceptions WHERE ingredient_id = ?", (ban_id,))
        return any(f" {e[0]} " in padded for e in exceptions)

    def check_phrase(self, phrase, field):
        """Return ({ban_id: 'why it matched'}, [taxonomy nodes found]) for one phrase."""
        kind = FIELD_KIND[field]
        p = norm(phrase)
        words = p.split()
        hits = {}
        nodes = [(s, e, n) for s, e, n in self.find_nodes(kind, words) if not negated(words, s)]
        for _, _, node in nodes:
            for ban_id in self.node_hits(kind, node, field):
                hits.setdefault(ban_id, f"taxonomy {node}")
        for start, end in ((s, e) for size in range(min(MAX_PHRASE_WORDS, len(words)), 0, -1)
                           for s in range(len(words) - size + 1) for e in [s + size]):
            if end < len(words) and words[end] == "free":  # 'gluten free', 'plastic-free'
                continue
            if negated(words, start):                      # 'no plastic', 'free from soy'
                continue
            for ban_id in self.alias_hits(" ".join(words[start:end]), field):
                hits.setdefault(ban_id, f"alias '{' '.join(words[start:end])}'")
        return {b: why for b, why in hits.items() if not self.excepted(b, p)}, [n for _, _, n in nodes]

    def check_field(self, text, field):
        """-> list of (phrase, nodes, hits, is_trace, identified)."""
        if field == "ingredients":
            m = TRACE_RE.search(text)
            sections = [(text[:m.start()], False), (TRACE_RE.sub(" ", text[m.start():]), True)] if m else [(text, False)]
        else:
            sections = [(text, False)]
        results = []
        for section, is_trace in sections:
            for phrase in split_list(section):
                hits, nodes = self.check_phrase(phrase, field)
                if is_trace:
                    hits = {b: w for b, w in hits.items() if self.ban(b)["strictness"] == "traces"}
                p = norm(phrase)
                identified = bool(hits or [n for n in nodes if n != "en:unknown"] or p in NO_PACKAGING
                                  or all(w in FILLER_WORDS for w in p.split()))
                results.append((phrase, nodes, hits, is_trace, identified))
        return results

    @staticmethod
    def context_reasons(packaging_words, name, categories, ingredients=None):
        """Packaging gaps revealed by the product's name, categories and ingredients (rules 4-6 above)."""
        has = lambda text, terms: [t for t in terms if f" {norm(t)} " in text]
        cats = f" {norm(categories or '')} "
        reasons = []
        holds_it = any(w & (CONTAINER_WORDS | GLASS_WORDS | METAL_WORDS) for w in packaging_words)
        first = norm(split_list(ingredients)[0]).split() if ingredients and split_list(ingredients) else []
        needs_inner = ((has(cats, LIQUID_CATEGORIES) and not has(cats, DRY_CATEGORIES))
                       or VOLUME_RE.search(name or "") or (first and first[0] in WATER_WORDS | MEAT_FISH_WORDS))
        if needs_inner and not holds_it:
            reasons.append("liquid, wet or fresh product in paper or cardboard (the inner carton, tray, "
                           "pot or blister isn't listed)")
        if has(cats, INNER_BAG_CATEGORIES) and not holds_it:
            reasons.append("this kind of product nearly always has an inner bag or wrapper, which isn't listed")
        if has(cats, FROZEN_CATEGORIES):
            reasons.append("frozen food (frozen-food boxes are plastic-coated or hold an inner bag)")
        if has(cats, CANNED_CATEGORIES):
            reasons.append("canned food (the can is plastic-lined)")
        hints = has(f" {norm(name or '')} ", NAME_HINTS) or has(cats, NAME_HINTS)
        if hints:
            reasons.append(f"name mentions '{hints[0]}', which the packaging list leaves out")
        return reasons

    def check(self, ingredients=None, packaging=None, material=None, name=None, categories=None):
        """-> (verdict, {field: results}, [reasons the verdict is unknown]).

        `name` and `categories` are optional product context. They are never matched against
        the ban list; they only let the packaging rules see what the packaging data leaves out
        (a juice in 'cardboard' is a lined carton, '25 sachets' means tea bags)."""
        given = {f: t for f, t in (("ingredients", ingredients), ("packaging", packaging), ("material", material))
                 if t and t.strip()}
        results = {f: self.check_field(t, f) for f, t in given.items()}
        excluded = any(r[2] for rows in results.values() for r in rows)
        needed = self.required_fields()
        unknown = []
        if "packaging" in needed:
            if "packaging" not in given:
                unknown.append("no packaging information")
            else:
                parts = results["packaging"]
                if not parts:
                    unknown.append("packaging text has no recognizable words")
                unknown += [f"packaging part not identified: '{r[0]}'" for r in parts if not r[4]]
                words = [set(norm(r[0]).split()) for r in parts]
                if (any(w & (CONTAINER_WORDS | GLASS_WORDS) for w in words)
                        and not any(w & CLOSURE_WORDS for w in words)):
                    unknown.append("container listed without its cap/lid")
                gas_tight = CONTAINER_WORDS | GLASS_WORDS | METAL_WORDS
                if any(w - FILLER_WORDS and w - FILLER_WORDS <= GAS_WORDS for w in words) and \
                        not any(w & gas_tight for w in words):
                    unknown.append("protective gas listed without the sealed container that holds it")
                unknown += [f"metal packaging '{r[0]}' (cans, tins, trays and lids are plastic-lined)"
                            for r, w in zip(parts, words) if not r[2] and w & METAL_WORDS and not w & FOIL_WORDS]
                if parts and all(w <= FILLER_WORDS for w in words) and \
                        not any(norm(r[0]) in NO_PACKAGING for r in parts):
                    unknown.append("packaging names no material")
                unknown += self.context_reasons(words, name, categories, ingredients)
        if needed & {"ingredients", "material"} and not given.keys() & {"ingredients", "material"}:
            unknown.append("no ingredients or materials information")
        if "material" in given and "material" in needed:
            if not results["material"]:
                unknown.append("material text has no recognizable words")
            unknown += [f"material not identified: '{r[0]}'" for r in results["material"] if not r[4]]
        verdict = EXCLUDED if excluded else UNKNOWN if unknown else OK
        return verdict, results, unknown


class MemoryMatcher(Matcher):
    """Same matching as Matcher, but loads the whole active ban list and taxonomy into memory
    once and caches phrase results. For batch jobs (checking millions of products); the
    one-off load takes seconds per million bans."""

    def __init__(self, db):
        super().__init__(db)
        self.bans = {r["id"]: r for r in db.execute("SELECT * FROM banned_ingredients WHERE active = 1")}
        self.applies = {i: set(b["applies_to"].split(",")) for i, b in self.bans.items()}
        self.aliases = {}
        for r in db.execute("SELECT ingredient_id, alias_norm, fields FROM aliases"):
            if r[0] in self.bans:
                self.aliases.setdefault(r[1], []).append((r[0], set(r[2].split(",")) if r[2] else None))
        self.exceptions = {}
        for r in db.execute("SELECT ingredient_id, phrase_norm FROM exceptions"):
            self.exceptions.setdefault(r[0], []).append(r[1])
        self.synonyms = {}
        for kind, node_id, text in db.execute(
                "SELECT kind, node_id, text_norm FROM taxonomy_synonyms ORDER BY lang = 'en'"):
            self.synonyms[(kind, text)] = node_id  # English rows come last, so they win
        self.parents = {}
        for kind, child, parent in db.execute("SELECT kind, child_id, parent_id FROM taxonomy_parents"):
            self.parents.setdefault((kind, child), []).append(parent)
        self.roots = {}
        for ban_id, kind, node_id in db.execute("SELECT ingredient_id, kind, node_id FROM ban_roots"):
            if ban_id in self.bans:
                self.roots.setdefault((kind, node_id), []).append(ban_id)
        self.needed = {f for a in self.applies.values() for f in a}
        self.ancestor_cache, self.phrase_cache = {}, {}

    def required_fields(self):
        return self.needed

    def alias_hits(self, gram, field):
        return [b for b, fields in self.aliases.get(gram, ())
                if field in self.applies[b] and (fields is None or field in fields)]

    def lookup_node(self, kind, gram):
        return self.synonyms.get((kind, gram))

    def ancestors(self, kind, node_id):
        """-> {ancestor: min depth}, the node itself at depth 0."""
        key = (kind, node_id)
        if key not in self.ancestor_cache:
            seen, frontier, depth = {node_id: 0}, [node_id], 0
            while frontier:
                depth += 1
                frontier = [p for n in frontier for p in self.parents.get((kind, n), ()) if p not in seen]
                seen.update((p, depth) for p in frontier)
            self.ancestor_cache[key] = seen
        return self.ancestor_cache[key]

    def node_hits(self, kind, node_id, field):
        return list({b for anc, depth in self.ancestors(kind, node_id).items()
                     for b in self.roots.get((kind, anc), ())
                     if field in self.applies[b] and (depth == 0 or self.bans[b]["include_children"])})

    def excepted(self, ban_id, phrase_norm):
        padded = f" {phrase_norm} "
        return any(f" {e} " in padded for e in self.exceptions.get(ban_id, ()))

    def check_phrase(self, phrase, field):
        key = (norm(phrase), field)
        if key not in self.phrase_cache:
            if len(self.phrase_cache) > 2_000_000:
                self.phrase_cache.clear()
            self.phrase_cache[key] = super().check_phrase(phrase, field)
        return self.phrase_cache[key]


# ---------------------------------------------------------------- commands

def cmd_init(db, args):
    counts = load_taxonomy(db)
    print("Loaded taxonomy: " + ", ".join(f"{n:,} {k} entries" for k, n in counts.items()))
    if args.seed:
        cmd_import(db, argparse.Namespace(file=args.seed, note="initial seed"))


def cmd_load_taxonomy(db, args):
    counts = load_taxonomy(db)
    print("Loaded taxonomy: " + ", ".join(f"{n:,} {k} entries" for k, n in counts.items()))


def cmd_reindex(db, args):
    """Reload the taxonomies and re-normalize every alias and exception (after `norm` changes)."""
    cmd_load_taxonomy(db, args)
    changed = 0
    for table, text_col, norm_col in (("aliases", "alias", "alias_norm"), ("exceptions", "phrase", "phrase_norm")):
        for row_id, text, old in db.execute(f"SELECT id, {text_col}, {norm_col} FROM {table}").fetchall():
            if norm(text) != old:
                changed += db.execute(f"UPDATE OR IGNORE {table} SET {norm_col} = ? WHERE id = ?",
                                      (norm(text), row_id)).rowcount
    print(f"Re-normalized {changed} alias/exception row(s).")


def cmd_add(db, args):
    ban_id, action = upsert_ban(db, args.slug, args.name or args.slug, args.applies_to, args.category, args.reason,
                                args.strictness, not args.no_children, args.taxonomy or [],
                                args.packaging_taxonomy or [], args.alias or [], args.material_alias or [],
                                args.exception or [], args.note)
    print(f"{action}: {args.slug} (id {ban_id})")


def cmd_remove(db, args):
    for slug in args.slugs:
        ban = get_ban(db, slug)
        if not ban["active"]:
            print(f"{slug} is already removed")
            continue
        db.execute("UPDATE banned_ingredients SET active = 0, updated_at = datetime('now') WHERE id = ?", (ban["id"],))
        log(db, ban["id"], "remove", note=args.note)
        print(f"removed: {slug} (restore with `restore {slug}`)")


def cmd_restore(db, args):
    for slug in args.slugs:
        ban = get_ban(db, slug)
        db.execute("UPDATE banned_ingredients SET active = 1, updated_at = datetime('now') WHERE id = ?", (ban["id"],))
        log(db, ban["id"], "restore", note=args.note)
        print(f"restored: {slug}")


def cmd_alias(db, args):
    ban = get_ban(db, args.slug)
    if args.remove:
        removed = [a for a in args.aliases
                   if db.execute("DELETE FROM aliases WHERE ingredient_id = ? AND alias_norm = ?",
                                 (ban["id"], norm(a))).rowcount]
        if removed:
            log(db, ban["id"], "alias_remove", {"aliases": removed}, args.note)
        print(f"removed {len(removed)} alias(es) from {args.slug}")
    else:
        added = add_aliases(db, ban["id"], args.aliases, csv_fields(args.fields) if args.fields else None)
        if added:
            log(db, ban["id"], "alias_add", {"aliases": added, "fields": args.fields}, args.note)
        print(f"added {len(added)} alias(es) to {args.slug}")


def cmd_exception(db, args):
    ban = get_ban(db, args.slug)
    if args.remove:
        removed = [p for p in args.phrases
                   if db.execute("DELETE FROM exceptions WHERE ingredient_id = ? AND phrase_norm = ?",
                                 (ban["id"], norm(p))).rowcount]
        if removed:
            log(db, ban["id"], "exception_remove", {"exceptions": removed}, args.note)
        print(f"removed {len(removed)} exception(s) from {args.slug}")
    else:
        added = add_exceptions(db, ban["id"], args.phrases)
        if added:
            log(db, ban["id"], "exception_add", {"exceptions": added}, args.note)
        print(f"added {len(added)} exception(s) to {args.slug}")


def cmd_root(db, args):
    ban = get_ban(db, args.slug)
    if args.remove:
        removed = [n for n in args.node_ids
                   if db.execute("DELETE FROM ban_roots WHERE ingredient_id = ? AND kind = ? AND node_id = ?",
                                 (ban["id"], args.kind, n)).rowcount]
        if removed:
            log(db, ban["id"], "root_remove", {"kind": args.kind, "roots": removed}, args.note)
        print(f"removed {len(removed)} taxonomy root(s) from {args.slug}")
    else:
        added = add_roots(db, ban["id"], args.kind, args.node_ids)
        if added:
            log(db, ban["id"], "root_add", {"roots": added}, args.note)
        print(f"added {len(added)} taxonomy root(s) to {args.slug}")


def cmd_list(db, args):
    where = "" if args.all else "WHERE b.active = 1"
    rows = db.execute(f"""SELECT b.*, (SELECT COUNT(*) FROM aliases a WHERE a.ingredient_id = b.id) AS n_alias
                          FROM banned_ingredients b {where} ORDER BY b.category, b.slug""").fetchall()
    print(f"{'slug':<15}{'name':<30}{'category':<21}{'applies to':<31}{'strict':<8}{'aliases':>7}")
    for r in rows:
        flag = "  [removed]" if not r["active"] else ""
        print(f"{r['slug']:<15}{r['name'][:29]:<30}{(r['category'] or '')[:20]:<21}{r['applies_to']:<31}"
              f"{r['strictness']:<8}{r['n_alias']:>7}{flag}")
    print(f"\n{len(rows)} entr{'y' if len(rows) == 1 else 'ies'}")


def cmd_show(db, args):
    ban = get_ban(db, args.slug)
    for k in ban.keys():
        print(f"{k:>17}: {ban[k]}")
    roots = [f"{r['kind']}:{r['node_id']}" for r in
             db.execute("SELECT kind, node_id FROM ban_roots WHERE ingredient_id = ? ORDER BY kind, node_id", (ban["id"],))]
    aliases = [f"{r['alias']}" + (f" [{r['fields']}]" if r["fields"] else "") for r in
               db.execute("SELECT alias, fields FROM aliases WHERE ingredient_id = ? ORDER BY alias", (ban["id"],))]
    excs = [r["phrase"] for r in db.execute("SELECT phrase FROM exceptions WHERE ingredient_id = ? ORDER BY phrase", (ban["id"],))]
    print(f"{'taxonomy roots':>17}: {', '.join(roots) or '-'}")
    print(f"{'taxonomy covers':>17}: {len(covered_nodes(db, ban)):,} node(s) (see `expand {args.slug}`)")
    print(f"{'aliases':>17}: {len(aliases):,}  {', '.join(aliases[:args.limit])}"
          + (f" ... (+{len(aliases) - args.limit}, use --limit)" if len(aliases) > args.limit else ""))
    print(f"{'exceptions':>17}: {', '.join(excs) or '-'}")


def cmd_expand(db, args):
    ban = get_ban(db, args.slug)
    nodes = covered_nodes(db, ban)
    for kind, node_id, name in nodes[:args.limit]:
        print(f"  {kind:<11}{node_id:<60} {name or '(not in taxonomy)'}")
    if len(nodes) > args.limit:
        print(f"  ... and {len(nodes) - args.limit:,} more (use --limit)")
    print(f"{len(nodes):,} taxonomy node(s) covered by '{args.slug}'")


def cmd_search(db, args):
    q = norm(args.text)
    rows = db.execute("""SELECT DISTINCT s.kind, s.node_id, n.name FROM taxonomy_synonyms s
                         JOIN taxonomy_nodes n ON n.kind = s.kind AND n.id = s.node_id
                         WHERE s.text_norm LIKE ? AND (? IS NULL OR s.kind = ?)
                         ORDER BY length(s.text_norm) LIMIT ?""",
                      (f"%{q}%", args.kind, args.kind, args.limit)).fetchall()
    for r in rows:
        print(f"  {r['kind']:<11}{r['node_id']:<60} {r['name']}")
    print(f"{len(rows)} match(es)")


def cmd_check(db, args):
    read = lambda t: sys.stdin.read() if t == "-" else t
    matcher = Matcher(db)
    verdict, results, unknown = matcher.check(read(args.ingredients or args.text or ""),
                                              read(args.packaging or ""), read(args.material or ""),
                                              args.name, args.categories)
    banned = {}
    for field, rows in results.items():
        print(f"{field}:")
        for phrase, nodes, hits, is_trace, identified in rows:
            tag = " (trace warning)" if is_trace else ""
            if hits:
                names = "; ".join(f"{matcher.ban(b)['slug']} via {why}" for b, why in hits.items())
                print(f"  BANNED   {phrase}{tag}  ->  {names}")
                banned.update(dict.fromkeys(hits))
            elif not identified and field != "ingredients":
                print(f"  UNKNOWN  {phrase}  (not a recognized material)")
            elif args.verbose:
                print(f"  ok       {phrase}{tag}  [{', '.join(nodes) or 'not in taxonomy'}]")
    if verdict == EXCLUDED:
        print("\nRESULT: EXCLUDED - contains " + ", ".join(matcher.ban(b)["name"] for b in banned))
    elif verdict == UNKNOWN:
        print("\nRESULT: UNKNOWN - can't confirm it's clean:\n  - " + "\n  - ".join(unknown))
    else:
        print("\nRESULT: OK - nothing banned found")
    return verdict


def cmd_log(db, args):
    rows = db.execute("""SELECT l.*, b.slug FROM change_log l LEFT JOIN banned_ingredients b ON b.id = l.ingredient_id
                         WHERE (? IS NULL OR b.slug = ?) ORDER BY l.id DESC LIMIT ?""",
                      (args.slug, args.slug, args.limit)).fetchall()
    for r in reversed(rows):
        details = f"  {r['details']}" if r["details"] and args.verbose else ""
        note = f"  — {r['note']}" if r["note"] else ""
        print(f"{r['at']}  {r['action']:<16} {r['slug'] or '-':<15}{note}{details}")


IMPORT_HELP = """CSV columns (lists separated by |):
  slug, name, applies_to (ingredients|packaging|material), category, reason, strictness (exact|traces),
  include_children (1|0), ingredient_taxonomy, packaging_taxonomy, aliases,
  material_aliases (only matched in packaging/material text), exceptions"""


def cmd_import(db, args):
    counts = {}
    with open(args.file, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            split = lambda key: [x for x in (row.get(key) or "").split("|") if x.strip()]
            _, action = upsert_ban(db, row["slug"].strip(), row.get("name") or row["slug"],
                                   row.get("applies_to") or "ingredients", row.get("category"), row.get("reason"),
                                   row.get("strictness") or "exact", (row.get("include_children") or "1") != "0",
                                   split("ingredient_taxonomy") + split("taxonomy_id"), split("packaging_taxonomy"),
                                   split("aliases"), split("material_aliases"), split("exceptions"), args.note)
            counts[action] = counts.get(action, 0) + 1
            if (row.get("active") or "1") == "0":
                db.execute("UPDATE banned_ingredients SET active = 0 WHERE slug = ?", (row["slug"].strip(),))
    print("imported: " + ", ".join(f"{n} {a}" for a, n in sorted(counts.items())))


def cmd_export(db, args):
    out = open(args.file, "w", newline="", encoding="utf-8") if args.file != "-" else sys.stdout
    w = csv.writer(out)
    w.writerow(["slug", "name", "applies_to", "category", "reason", "strictness", "include_children", "active",
                "ingredient_taxonomy", "packaging_taxonomy", "aliases", "material_aliases", "exceptions"])
    q = lambda sql, *p: "|".join(r[0] for r in db.execute(sql, p))
    for b in db.execute("SELECT * FROM banned_ingredients ORDER BY id"):
        i = b["id"]
        w.writerow([b["slug"], b["name"], b["applies_to"].replace(",", "|"), b["category"] or "", b["reason"] or "",
                    b["strictness"], b["include_children"], b["active"],
                    q("SELECT node_id FROM ban_roots WHERE ingredient_id = ? AND kind = 'ingredient'", i),
                    q("SELECT node_id FROM ban_roots WHERE ingredient_id = ? AND kind = 'packaging'", i),
                    q("SELECT alias FROM aliases WHERE ingredient_id = ? AND fields IS NULL ORDER BY id", i),
                    q("SELECT alias FROM aliases WHERE ingredient_id = ? AND fields IS NOT NULL ORDER BY id", i),
                    q("SELECT phrase FROM exceptions WHERE ingredient_id = ? ORDER BY id", i)])
    if out is not sys.stdout:
        out.close()
        print(f"exported to {args.file}")


def main():
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("init", help="create the database and load the taxonomies")
    s.add_argument("--seed", help="CSV file of entries to import")
    s.set_defaults(fn=cmd_init)

    s = sub.add_parser("load-taxonomy", help="reload the Open Food Facts taxonomy files")
    s.set_defaults(fn=cmd_load_taxonomy)

    s = sub.add_parser("reindex", help="reload taxonomies and re-normalize aliases (after upgrading the tool)")
    s.set_defaults(fn=cmd_reindex)

    s = sub.add_parser("add", help="add an entry (or add to it if the slug exists)")
    s.add_argument("slug")
    s.add_argument("--name")
    s.add_argument("--applies-to", default="ingredients", help="comma list of ingredients,packaging,material")
    s.add_argument("--taxonomy", action="append", help="ingredient taxonomy id, e.g. en:sesame-seeds (repeatable)")
    s.add_argument("--packaging-taxonomy", action="append", help="packaging taxonomy id, e.g. en:glass (repeatable)")
    s.add_argument("--category")
    s.add_argument("--reason")
    s.add_argument("--strictness", choices=["exact", "traces"], default="exact")
    s.add_argument("--no-children", action="store_true", help="don't cover taxonomy descendants")
    s.add_argument("--alias", action="append", help="repeatable")
    s.add_argument("--material-alias", action="append", help="alias only matched in packaging/material text")
    s.add_argument("--exception", action="append", help="repeatable")
    s.add_argument("--note")
    s.set_defaults(fn=cmd_add)

    for name, fn, help_ in (("remove", cmd_remove, "deactivate entries (reversible)"),
                            ("restore", cmd_restore, "re-activate removed entries")):
        s = sub.add_parser(name, help=help_)
        s.add_argument("slugs", nargs="+")
        s.add_argument("--note")
        s.set_defaults(fn=fn)

    s = sub.add_parser("alias", help="add (or --remove) alternate names for an entry")
    s.add_argument("slug")
    s.add_argument("aliases", nargs="+")
    s.add_argument("--fields", help="only match in these fields, e.g. packaging,material")
    s.add_argument("--remove", action="store_true")
    s.add_argument("--note")
    s.set_defaults(fn=cmd_alias)

    s = sub.add_parser("exception", help="add (or --remove) phrases that should NOT trigger an entry")
    s.add_argument("slug")
    s.add_argument("phrases", nargs="+")
    s.add_argument("--remove", action="store_true")
    s.add_argument("--note")
    s.set_defaults(fn=cmd_exception)

    s = sub.add_parser("root", help="add (or --remove) taxonomy nodes an entry covers")
    s.add_argument("slug")
    s.add_argument("node_ids", nargs="+")
    s.add_argument("--kind", choices=["ingredient", "packaging"], default="ingredient")
    s.add_argument("--remove", action="store_true")
    s.add_argument("--note")
    s.set_defaults(fn=cmd_root)

    s = sub.add_parser("list", help="list entries")
    s.add_argument("--all", action="store_true", help="include removed entries")
    s.set_defaults(fn=cmd_list)

    s = sub.add_parser("show", help="show one entry in detail")
    s.add_argument("slug")
    s.add_argument("--limit", type=int, default=40, help="how many aliases to print")
    s.set_defaults(fn=cmd_show)

    s = sub.add_parser("expand", help="list every taxonomy node an entry covers")
    s.add_argument("slug")
    s.add_argument("--limit", type=int, default=50)
    s.set_defaults(fn=cmd_expand)

    s = sub.add_parser("search", help="search the taxonomies for an id")
    s.add_argument("text")
    s.add_argument("--kind", choices=["ingredient", "packaging"])
    s.add_argument("--limit", type=int, default=20)
    s.set_defaults(fn=cmd_search)

    s = sub.add_parser("check", help="check a product; exit code 0 = OK, 1 = excluded, 2 = unknown",
                       description="Any text argument may be '-' to read it from stdin.")
    s.add_argument("text", nargs="?", help="ingredient list (same as --ingredients)")
    s.add_argument("--ingredients")
    s.add_argument("--packaging", help="e.g. 'glass jar, metal lid, paper label'")
    s.add_argument("--material", help="what the product itself is made of, e.g. '100%% cotton'")
    s.add_argument("--name", help="product name, used only to spot unlisted packaging ('25 sachets')")
    s.add_argument("--categories", help="product categories, e.g. 'Beverages, Juices' (spots lined cartons)")
    s.add_argument("-v", "--verbose", action="store_true", help="also show parts that passed")
    s.set_defaults(fn=cmd_check)

    s = sub.add_parser("log", help="show the change history")
    s.add_argument("slug", nargs="?")
    s.add_argument("--limit", type=int, default=50)
    s.add_argument("-v", "--verbose", action="store_true")
    s.set_defaults(fn=cmd_log)

    s = sub.add_parser("import", help="bulk add/update from CSV", description=IMPORT_HELP,
                       formatter_class=argparse.RawDescriptionHelpFormatter)
    s.add_argument("file")
    s.add_argument("--note")
    s.set_defaults(fn=cmd_import)

    s = sub.add_parser("export", help="write every entry to CSV ('-' for stdout)")
    s.add_argument("file")
    s.set_defaults(fn=cmd_export)

    args = p.parse_args()
    db = connect()
    try:
        status = args.fn(db, args)
        db.commit()
    finally:
        db.close()
    sys.exit(status or 0)


if __name__ == "__main__":
    main()
