# Banned ingredients

A SQLite database of things to avoid (ingredients, and materials like plastic), plus a command-line tool (`banlist.py`, Python 3, no installs needed) to edit it and check products against it.

## Files
| File | What it is |
|---|---|
| `banlist.db` | The database (source of truth) |
| `banlist.py` | The tool |
| `schema.sql` | Table definitions |
| `seed.csv` | Starting entries (10 ingredients + plastic, hidden plastic, plastic-like materials) |
| `banned_ingredients.csv` | Latest export, readable in any spreadsheet app |
| `data/taxonomy/` | Open Food Facts ingredient, additive and packaging-material taxonomies |

## Three fields per product
Each entry says which product fields it applies to (`applies_to`):

| Field | Meaning | Example |
|---|---|---|
| `ingredients` | what's in it | "Sugar, soy lecithin, gum base" |
| `packaging` | what it comes in | "glass jar, metal lid, paper label" |
| `material` | what the product is made of | "95% cotton, 5% elastane" |

Allergens and additives only apply to `ingredients`. `plastic` applies to all three. `hidden-plastic` covers can linings, lid liners, pouches, tea bags, labels, tape and similar, and applies to packaging and material. `plastic-like` covers silicone, synthetic rubber, rayon/viscose/modal/lyocell and cellophane. Natural rubber is allowed.

## Three verdicts
`check` gives one of three verdicts, shown both as text and as an exit code:

| Verdict | Exit code | Meaning |
|---|---|---|
| **OK** | 0 | Nothing banned was found, and there was enough information to be sure. |
| **EXCLUDED** | 1 | Something banned was found. |
| **UNKNOWN** | 2 | Nothing banned was found, but some information is missing. |

UNKNOWN happens when no packaging is given (while a packaging ban is active), when neither ingredients nor materials are given, or when a packaging or material part isn't a recognized material. For example, "wrapper" alone could be anything.

For packaging, "none", "loose" or "unpackaged" count as known.

## Everyday commands
```sh
python3 banlist.py list
python3 banlist.py show plastic
python3 banlist.py expand plastic              # every packaging material plastic covers

python3 banlist.py check "Sugar, gum base" --packaging "paper wrapper"
python3 banlist.py check --material "100% linen" --packaging "kraft paper, paper tape"

python3 banlist.py search sesame               # find taxonomy ids
python3 banlist.py add sesame --name Sesame --taxonomy en:sesame-seeds \
    --category allergen --strictness traces --alias tahini
python3 banlist.py alias plastic "polyvinyl butyral" pvb
python3 banlist.py alias plastic pvb --fields packaging,material   # short code: packaging/material only
python3 banlist.py exception hidden-plastic "glass stopper"        # don't flag this phrase
python3 banlist.py root plastic en:silicone --kind packaging       # cover a whole taxonomy family

python3 banlist.py remove hidden-plastic --note "trying without it"   # reversible
python3 banlist.py restore hidden-plastic
python3 banlist.py log

python3 banlist.py import more.csv             # bulk add (run `import -h` for the columns)
python3 banlist.py export banned_ingredients.csv
```

## How matching works
A part of a product is flagged when either of these holds:
1. **Taxonomy.** It names an entry's taxonomy node, or any descendant of it. Ingredient text is matched against the ingredient taxonomy. Packaging and material text is matched against the packaging-material taxonomy, where `en:plastic` covers PET, HDPE, PLA, bioplastics, plastic-lined cartons, and more.
2. **Alias.** An entry's alias appears as whole words. Aliases marked `[packaging,material]` (short codes like PET or SAN) are ignored in ingredient text, so "San Marzano tomatoes" is safe.

A part is not flagged when:
- It is negated: "plastic-free", "no plastic", "free from soy".
- An exception phrase for that entry is present ("coconut milk" for milk, "cork stopper" for hidden plastic).

"BPA-free" is still flagged, because BPA-free plastic is still plastic.

Anything after "may contain", "made in a facility…", and so on only counts for entries with `strictness = traces`.

## Scale
Nothing is loaded into memory. Every lookup goes through an index, so speed doesn't depend on list size. In a test with 1,000,000 extra entries, a check across all three fields took about 0.25 seconds.
