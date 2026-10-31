# Where we left off

_Last updated 2026-10-24._

## Done
- **Ban list** (`banlist.db`) has 13 active entries:
  - 10 ingredients: gluten, soy, peanuts, milk, palm oil, HFCS, aspartame, Red 40, MSG, carrageenan
  - `plastic`, `hidden-plastic`, `plastic-like`

  Every change is recorded in the change log (`python3 banlist.py log`).
- **Checker** handles ingredients, packaging and material. It returns OK, EXCLUDED or UNKNOWN, and it works on non-English labels.
- **Product pipeline**:
  - `pipeline/download.sh` downloads the data.
  - `pipeline/build_products.py` checks every product against the ban list.
  - `search.py` searches the clean products.
- **Tests**: `python3 tests/test_banlist.py` (28 cases × 2 matchers, all passing).
- **Trial run** on the first 20,000 rows of each export: 130 of 60,874 products passed. The pipeline works.

## Latest build (2026-10-31, after accuracy fixes)
- Checked 4,621,274 products:
  - 5,224 passed (was 16,739 before the fixes)
  - 1,033,560 excluded
  - 3,582,490 unknown
- **Shareable search page**: https://claude.ai/artifact/K9XSaVNM81cksFh63a4wQx (private until shared)
  - Source: `site/clean-shelf.html`
  - Data: `python3 site/export_json.py . <out>/products.json`, then publish with `files`
- Accuracy fixes found by three rounds of spot-checks. Each fix is covered in `tests/test_banlist.py` (130 checks, all passing).
  - A jar, bottle or bare "glass" (in 20+ languages) needs its lid or cap listed.
  - Metal packaging other than plain foil (cans, tins, trays, lids) is unknown.
  - A protective gas needs the glass or metal container that holds it.
  - Packaging that names no material (only "FSC" or "recyclable") is unknown.
  - Product context (name and categories), used only to spot unlisted packaging:
    - Liquids, wet and fresh foods, and supplements in paper or cardboard. Detected by category, by a volume in the name ("20 cl") or by water, meat or fish as the first ingredient.
    - Cereals, biscuits, snacks and sweets: they nearly always have an inner bag.
    - Frozen and canned foods.
    - Names or categories mentioning tea bags, capsules, sachets, pouches or "Kochbeutel".
  - Dairy categories (cheese, butter, yogurt) count as milk even when the ingredient text is missing.
  - Drink cartons named as such ("beverage karton") count as plastic.
- Known remaining gaps:
  - Records that leave out a part with no clue in the name or category.
  - A few products with wrong categories.
  - Canned fish with neither a category nor a meat/fish first ingredient.

## Needs-packaging list (2026-10-31)
- `python3 pipeline/needs_packaging.py` (about 3 minutes, after `build_products.py`) finds products that pass every ingredient check and are held back only by missing or incomplete packaging details.
  - 430,882 products are held back this way (197,044 sold in the US).
  - Each one gets a chance of passing: among products in the same category whose packaging is recorded, the share that pass. Eggs are about 70%, sugar about 35%, sodas near 0.
  - Ranked US first, then by chance² × (1 + log(scans)), so a likely pass beats a popular long shot.
- `needs_packaging.csv`: the 30,680 candidates with at least a 10% chance (10,147 in the US).
- The page's **Help fill the gaps** tab shows the top 2,000 (all US) with what's missing and how to add it in the Open Food Facts app. Link straight to it with `#gaps`.
- Page data: `data/needs_packaging.json`, published as `needs.json` next to `products.json`.

## Rebuild steps (repeat to refresh)
1. `bash pipeline/download.sh`
   - Downloads about 1.5 GB of CSV exports.
   - Then streams the 13 GB food JSONL to extract packaging, which takes about 20 minutes.
   - Re-running skips files that are already complete. A broken connection fails loudly instead of leaving a truncated file.
2. `python3 pipeline/build_products.py`
   - Takes about 7 minutes for roughly 4.6 million products.
   - Writes `products_clean.db` and `products_clean.csv`.
3. `python3 pipeline/needs_packaging.py` refreshes the to-do list (about 3 minutes).
4. Spot-check a random sample of OK products for anything that slipped through.
5. Run `python3 tests/test_banlist.py`.
6. Update the page:
   - Export `products.json` with `site/export_json.py`.
   - Copy `data/needs_packaging.json` as `needs.json`.
   - Publish `site/clean-shelf.html` with both files to the same link.

## Ideas not started yet
- A personal verification list (products you've checked yourself) that overrides Open Food Facts.
- A monthly automatic rebuild that updates the page.
- A "report a problem" button on the page.
- Exact Amazon product links (needs an Amazon Associates account).

## Known limits
- **OK means every packaging part that is listed is plastic-free.** If the data leaves out a part, such as the plastic bag inside a cereal box, the product can still pass.
- **"Carton" is ambiguous.** It can mean a cardboard box or a plastic-lined drink carton.
- **Most products have no packaging data**, so most products come out UNKNOWN.
