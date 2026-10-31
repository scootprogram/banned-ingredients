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
- **Tests**: `python3 tests/test_banlist.py` (130 checks across both matchers, all passing).
- **Trial run** on the first 20,000 rows of each export: 130 of 60,874 products passed. The pipeline works.

## Scope: beauty and household only (since 2026-10-31)
Food and pet food were removed at the owner's request:
- from the page (both tabs and all text)
- from `products_clean.*`, `needs_packaging.csv` and `data/needs_packaging.json`
- from the pipeline: `download.sh`, `build_products.py` and `needs_packaging.py` only handle Open Beauty Facts and Open Products Facts.

Earlier versions with food remain in git history. To bring food back, restore the food and pet food entries in those three scripts (commit c7cd3d1 has them), then rebuild.

The food-specific checker rules stay in `banlist.py`. They don't affect beauty products and keep the tests passing.

## Latest build (2026-10-31, beauty and household only)
- Checked 66,683 products:
  - 110 passed (97 beauty, 13 household)
  - 18,926 excluded
  - 47,647 unknown
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

## Needs-packaging list
- `python3 pipeline/needs_packaging.py` (after `build_products.py`) finds products that pass every ingredient check and are held back only by missing or incomplete packaging details.
  - 3,760 products are held back this way (433 in the US).
  - Each one gets a chance of passing: among products in the same category whose packaging is recorded, the share that pass.
  - Beauty products rarely pass. Bar soap is the best category at about 8.5%, so the cutoff is 5%.
- `needs_packaging.csv`: the 84 candidates at or above 5% (11 in the US), ranked US first, then by chance² × (1 + log(scans)).
- The page's **Help fill the gaps** tab shows them with what's missing and how to add it on Open Beauty Facts or Open Products Facts. Link straight to it with `#gaps`.
- Page data: `data/needs_packaging.json`, published as `needs.json` next to `products.json`.

## Rebuild steps (repeat to refresh)
1. `bash pipeline/download.sh`
   - Downloads about 25 MB of CSV exports.
   - Then streams the beauty and household JSONL exports to extract packaging (a few minutes).
   - Re-running skips files that are already complete. A broken connection fails loudly instead of leaving a truncated file.
2. `python3 pipeline/build_products.py`
   - Takes under a minute for about 67,000 products.
   - Writes `products_clean.db` and `products_clean.csv`.
3. `python3 pipeline/needs_packaging.py` refreshes the to-do list (seconds).
4. Spot-check a random sample of OK products for anything that slipped through.
5. Run `python3 tests/test_banlist.py`.
6. Update the page:
   - Export `products.json` with `site/export_json.py`.
   - Copy `data/needs_packaging.json` as `needs.json`.
   - Publish `site/clean-shelf.html` with both files to the same link.

## Amazon links (2026-10-31)
- Products with a real retail barcode (UPC/EAN, not a store code starting with 2) now link to an **Amazon search by barcode**, which often lands on the exact item. An "Amazon by name" link sits next to it as a fallback.
- Products without a usable barcode keep the name search.
- This is done on the page itself, in `amazonLinks` in `site/clean-shelf.html`.

## Ideas not started yet
- A personal verification list (products you've checked yourself) that overrides the database.
- A monthly automatic rebuild that updates the page.
- A "report a problem" button on the page.
- Exact Amazon product links. This needs the owner to:
  1. Open an Amazon Associates account. Approval requires 3 qualifying sales within 180 days.
  2. Request product API access inside that account.

  Then the pipeline would look up each barcode on the build side and store Amazon's product ID, so the page links straight to the product page. API keys go in environment variables, never in the repo or the page.

## Known limits
- **OK means every packaging part that is listed is plastic-free.** If the data leaves out a part, such as the plastic bag inside a cereal box, the product can still pass.
- **"Carton" is ambiguous.** It can mean a cardboard box or a plastic-lined drink carton.
- **Most products have no packaging data**, so most products come out UNKNOWN.
