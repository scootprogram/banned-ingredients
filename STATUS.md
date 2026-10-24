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

## Next steps
1. `bash pipeline/download.sh`
   - Downloads about 1.5 GB of CSV exports.
   - Then streams the 13 GB food JSONL to extract packaging, which takes about 20 minutes.
   - The first attempt was cut off by a network reset. The script now fails loudly on that, and re-running it skips files that are already complete.
2. `python3 pipeline/build_products.py`
   - Takes about 11 minutes for roughly 4 million products.
   - Writes `products_clean.db` and `products_clean.csv`.
3. Spot-check a random sample of OK products for anything that slipped through, as was done in the trial run.
4. Commit `products_clean.db` and `products_clean.csv` if they're small enough. GitHub rejects files over 100 MB.
5. Optional:
   - Build a web page for searching or browsing the clean list.
   - Show "unknown" products that only lack packaging details, as possible candidates.

## Known limits
- **OK means every packaging part that is listed is plastic-free.** If the data leaves out a part, such as the plastic bag inside a cereal box, the product can still pass.
- **"Carton" is ambiguous.** It can mean a cardboard box or a plastic-lined drink carton.
- **Most products have no packaging data**, so most products come out UNKNOWN.
