# Where we left off

_Last updated 2026-10-24._

## Browsing by material, and curated round 2 (2026-10-31)
- **Two-layer browsing.**
  - Layer 1: Beauty, or what a household product is made of (Stainless steel & metal, Wood & bamboo, Cotton & linen, Glass, Wool, Natural fibers, Ceramic & stone, Other household).
  - Layer 2: what it is. Beauty: Toothpaste, Soap, Shampoo… (`BEAUTY_TYPES`). Household: the curated row's `category`.
  - Groups come from `MATERIAL_GROUPS` in `site/export_json.py`.
- **Exact Amazon links for 5 of 6 curated products:** Weck 743 (B08LG6S4MZ), Redecker 2" (B003XCVR86), ECOlunchbox Three-in-One 31 oz (B0040MH642), Friendsheep 6-pack XL (B0186RP2YM), Bee's Wrap 3-pack (B07MCVM6SQ). These were found through web search of amazon.com listings. The ECOlunchbox Solo Rectangle listing (B008UY4Z9U) was unavailable.
- Curated `asin` = `none` means not sold on Amazon. The product shows only the maker's link.
- **Amazon links in general:** the 475 database products use barcode search. Nothing is needed from the owner until Amazon's product API is available (after 3 sales), when a script can fill exact links for everything.
- **New candidates, pending approval:**
  - `cs-0008` Package Free stainless steel straw: 100% steel, package-free, not on Amazon. Amazon straw sets found include nylon brushes or silicone tips.
  - `cs-0009` Bambu bamboo utensils: one piece, no glue or lacquer. The oil isn't named and could be soy; confirm.
  - `cs-0010` Rawganique Bremington towels: 100% organic cotton with cotton thread.

## Curated products (2026-10-31)
- `data/curated_products.csv` is a hand-maintained list for products the open databases don't cover, mainly household goods. `pipeline/curated_products.py check | approve <id> | reject <id>` manages it.
  - Every row goes through the same checker. Only **approved** rows are built into the list and published.
  - Name every part with its material ("glass jar, glass lid…"). A bare "lid" or "cap" counts as possible hidden plastic.
- First 7 candidates were researched from retailer and brand pages. **Published 2026-10-31 (approved by the owner):** Weck jar, Redecker dish brush, ECOlunchbox Three-in-One and Solo Rectangle, Friendsheep dryer balls, Bee's Wrap. The US page has 481 products, 7 of them household. **Lodge skillet stays pending.**
  - **Lodge:** an informal Target answer says its seasoning oil is soy-based. Soy is banned, so confirm before approving.
  - Barcodes and Amazon IDs are unknown for now (ids `cs-0001`…). Amazon links use the specific name search until IDs are added with `pipeline/amazon_links.py`.
- **Material labels:** products with listed materials show labels like GLASS / STAINLESS STEEL / WOOL at the **same size as the title** (design principle). `MATERIAL_LABELS` is in `site/export_json.py`.
- `KNOWN_MATERIALS` in `banlist.py` lists natural materials (wool, tampico, beechwood, jojoba oil, tree resin…) so they count as identified. Bans still apply.
- "Stainless steel lid" is an exception to hidden-plastic (an all-steel lid, no liner). Tinplate jar lids stay flagged.
- Tested end to end in a test copy: household goes from 1 to 8 products, labels match the title size, no errors.

## False matches fixed (2026-10-31)
- About 3,200 products were wrongly excluded. On the US page this is 56 products, mostly toothpastes and lotions (419 to 475).
  - "…glutamate" surfactants and chelators (sodium cocoyl glutamate, tetrasodium glutamate diacetate) were read as MSG. Fixed with exceptions on `msg`; real MSG and "sodium glutamate" are still caught.
  - Plant butters were read as dairy. "Shea (Butyrospermum Parkii) Butter" was split at the brackets into a lone "butter". `split_list` now keeps "shea butter" together, and `milk` has exceptions for plant butters, "crème" (cosmetic cream) and "fil".
  - Real dairy (milk protein, goat/donkey milk, lactose, whey, yogurt powder, "sine adipe lac") is still banned.
- US searches now: toothpaste 36, soap 46, shampoo 32, deodorant 23, mouthwash 17, conditioner 11, lotion 14, sunscreen 8.
- **Household is still 1 product (a hat), and this is missing data, not a bug.**
  - 926 of 1,318 US Open Products Facts records list no materials at all.
  - Many aren't household goods (cigarettes, gift cards, drinks).
  - Growing household needs another source: see "Curated products" under ideas.

## Verified Amazon links (2026-10-31)
- **Registry:** `data/amazon_links.csv` maps barcode to exact Amazon product ID (ASIN), with source (`manual` or `api`), date checked and a note.
  - A product in it gets a single **"View on Amazon ✓"** button to `amazon.com/dp/<ASIN>?tag=cleanshelf01-20`.
  - It starts empty.
- **Adding a link:** open the product on Amazon, confirm it's the same product (same brand, name and size), copy the page URL, then run:
  `python3 pipeline/amazon_links.py add <barcode> "<amazon URL>"`
  - It pulls out the ASIN. Full product URLs only; `a.co` short links can't be read.
  - `remove <barcode>` deletes a wrong link, and `list` shows them all.
  - Then re-export and publish (step 7 of the rebuild).
- **Later:** once the Associates account qualifies for Amazon's product API, a script can fill the registry by looking up each barcode, with `source=api`. The page logic doesn't change.
- **Products not in the registry:**
  - a barcode search, when they have a retail barcode;
  - plus a name search, only when the name is specific: a brand plus at least 2 words beyond generic product types (`GENERIC_WORDS` in the page). Generated names never get one.
  - Products with neither get no Amazon link (4 of 419), rather than a link to unrelated results.

## Design principle (owner, 2026-10-31): ingredients are as important as the name
What makes this business stand out: **a product's ingredients (or materials) matter as much as its name.** Online, especially on Amazon, shoppers see a product's name and design many times before they find its ingredient list, which is often hard to find at all. This site does the opposite.

Future layout work should follow this:
- **Products with ingredients** (cosmetics, soaps, supplements…): the ingredient list is shown **the same size as the product title**, not as small print below it.
- **Products made of a material** (glass water bottles, stainless steel food containers…): a big material label such as **GLASS** or **STAINLESS STEEL**, also the same size as the title.
- So on each product card, the **title, the ingredient list and the material label are all the same size**.
- Not built yet. Today the title is large and the ingredients are small text. Fold this into the planned redesign.

Things to think through when building it:
- Long ingredient lists (30+ items) at title size need a layout that stays readable, for example one line per ingredient or a clear column.
- Material data: household items have materials in their "ingredients" field (`products` source and hygiene articles). Glass and stainless steel can come from the packaging/material taxonomy and the material aliases. Mixed materials get several labels (GLASS + STAINLESS STEEL).
- Since plastic is never allowed, the material label also shows at a glance why the product qualifies.

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
- **Tests**: `python3 tests/test_banlist.py` (158 checks across both matchers, all passing).
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
  - 3,915 have clean ingredients and are listed on the page:
    - 105 with packaging verified plastic-free
    - 3,810 with packaging not verified yet
  - 19,241 excluded
  - the rest unknown for reasons other than packaging (no ingredient or material data)
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
- The page's old **Help fill the gaps** tab was replaced on 2026-10-31 by packaging status on the main list (see below). This CSV is kept as an offline to-do list.

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
6. If there are Help answers, count them: `python3 pipeline/packaging_votes.py <responses CSV or URL>`.
7. Update the page:
   - Export `products.json` with `site/export_json.py`.
   - Publish `site/clean-shelf.html` with it to the same link.
   - Rebuild the website with `site/build_website.py ../scootprogram.github.io`, then push that repo.

## Names and food filter (published 2026-10-31)
- Products with no recorded name get one from brand + type + size, marked "name not recorded" on the page.
- Food and drink filed as beauty is excluded (`is_food` in `pipeline/build_products.py`).
- Vitamins, supplements and over-the-counter medicines are **in scope** (owner's decision). `SUPPLEMENT_MARKERS` and `SUPPLEMENT_NAME_WORDS` keep them from counting as food, even as gummies or tablets.
- The page now has 419 US products: 1 with packaging verified plastic-free and 418 not verified yet.
- Open decisions for the owner:
  1. A redesign with features the owner likes from another site (nontoxiclab.com). Build the site's own version; don't copy that site's text, design or branding.

## US only (2026-10-31)
- The site only shows products recorded as sold in the United States, because it sells through amazon.com. The filter is in `site/export_json.py`. `products_clean.*` still holds the worldwide list (3,915).
- Amazon links: "Find on Amazon" searches amazon.com by barcode, with "Amazon by name" (brand plus up to 10 words of the name) as a fallback. Products without a retail barcode get the name search only. All links carry the tag.
- Why: the owner found barcode searches failing. Most products were sold only in Europe, and amazon.com doesn't list European barcodes.
- The page's search also matches barcodes.

## Plastic in other languages (2026-10-31)
- Found when a Russian toothbrush (7640168930479) was listed. Its materials, "polypropylene, thermoplastic elastomer, polybutylene terephthalate", were only matched in English.
- Plastic and silicone names were added in Russian, French, German, Spanish, Italian, Polish, Dutch and Scandinavian languages.
- "Without" words in those languages (sans, ohne, sin, senza, без…) negate a match. A packaging entry that is only a claim ("sans plastique", "plastic-free") counts as identified.
- **Stems.** `alias --stem` matches anywhere inside a word. This catches glued or misspelled scanner text ("acrylatescala", "copolyrmer", "4polyquaternium"). Stems are chosen not to hit harmless words: there is no bare `silicon` (it would catch silica) and no bare `plast` (it would catch the Hansaplast brand).
- **Hygiene articles.** Toothbrushes, pads, tampons, wipes, swabs, razors, sponges, brushes, bandages and shower caps have their "ingredients" checked as materials too (`ARTICLE_TERMS` in `pipeline/build_products.py`).
- Left as is: "пластификатор" (plasticizer) in 3 Russian soaps. It's ambiguous in soap, often glycerin.

## One list with packaging status (2026-10-31)
- `products_clean.*` holds every product with clean ingredients:
  - verdict `ok` means the packaging is verified plastic-free.
  - verdict `unknown` means only the packaging is in question.
- On the page:
  - Each product shows "Packaging verified plastic-free" or "Packaging not verified yet".
  - A **Packaging** filter offers Any / Verified plastic-free / Not verified yet.
  - Old `#gaps` links open the "Not verified yet" filter.
- **Help! votes.** Each unverified product gets a "Help! Do you know this packaging?" button. It asks three separate Yes / No / Not sure questions: 100% recyclable, non-toxic, sustainable.
  - Answers go to an outside form, because public visitors can't write to the Claude page's database.
  - The button stays hidden until `HELP_FORM` in `site/clean-shelf.html` has the form's address and field ids.
  - Form setup (owner): create a Google Form with 4 short-answer/multiple-choice questions: barcode, then "Is the packaging 100% recyclable?", "…non-toxic?", "…sustainable?", each with choices exactly Yes / No / Not sure, none required. Then use "Get pre-filled link", fill in sample answers, and send the link to Claude. The `entry.…` ids come from it.
- **Counting.** `pipeline/packaging_votes.py` reads the responses CSV (or the sheet's published-CSV URL). It keeps the most common of Yes/No per product and question, ignores "Not sure" and blanks, and treats ties as undecided. It writes `data/packaging_votes.json`, which `site/export_json.py` merges in. The page then shows "Visitors say (N answers): …".

## Amazon links (2026-10-31)
- Products with a real retail barcode (UPC/EAN, not a store code starting with 2) now link to an **Amazon search by barcode**, which often lands on the exact item. An "Amazon by name" link sits next to it as a fallback.
- Products without a usable barcode keep the name search.
- This is done on the page itself, in `amazonLinks` in `site/clean-shelf.html`.

## Website: https://scootprogram.github.io (since 2026-10-31)
- Public GitHub Pages site in the separate repo `scootprogram/scootprogram.github.io`. It holds only the page and its two data files, so no food history is public.
- Built from this repo with `python3 site/build_website.py ../scootprogram.github.io`, then commit and push in that repo.
- This is the site entered for the Amazon Associates application. Amazon rejected the claude.ai link because it isn't a site the owner controls.
- The page shows Amazon's required disclosure: "As an Amazon Associate I earn from qualifying purchases."
- Associates tracking ID: `cleanshelf01-20`, set as `AMAZON_TAG` in `site/clean-shelf.html`. To change it:
  1. Set `AMAZON_TAG` in `site/clean-shelf.html`.
  2. Rebuild the website and republish the Claude page.

## Ideas not started yet
- **Curated products** (proposed 2026-10-31): a hand-maintained list (`data/curated_products.csv`) for items open databases don't cover, mainly household goods like glass water bottles and stainless steel containers. Each row holds name, brand, barcode, materials or ingredients, packaging and the Amazon ASIN, and is checked by the same checker as everything else. It also feeds the GLASS / STAINLESS STEEL material labels.
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
