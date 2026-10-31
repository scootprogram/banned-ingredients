#!/usr/bin/env python3
"""Regression tests: python3 tests/test_banlist.py (exits 1 on any failure).

Runs every case through both the normal and the batch (in-memory) matcher.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import banlist  # noqa: E402

# (ingredients, packaging, material, expected verdict)
CASES = [
    ("Extra virgin olive oil", "glass bottle, cork stopper, paper label", None, "OK"),
    ("Extra virgin olive oil", "glass bottle, metal cap", None, "EXCLUDED"),        # cap liner
    ("Durum wheat semolina", "cardboard box, plastic window", None, "EXCLUDED"),
    ("Apple juice", "en:tetra-pak, en:plastic-cap", None, "EXCLUDED"),
    ("Apples", "none", None, "OK"),
    ("Apples", None, None, "UNKNOWN"),                                           # no packaging info
    ("Rice", "paper bag, wrapper", None, "UNKNOWN"),                             # 'wrapper' of what?
    ("Brown rice", "kraft paper bag", None, "OK"),
    ("Sugar, gum base, sorbitol", "paper wrapper", None, "EXCLUDED"),
    ("Aqua, glycerin, polyethylene, PEG-100 stearate", "glass jar, glass lid", None, "EXCLUDED"),
    (None, "cardboard sleeve", "100% food-grade silicone, nylon core", "EXCLUDED"),
    (None, "recycled paper", "95% organic cotton, 5% elastane", "EXCLUDED"),
    (None, "unpackaged", "beech wood", "OK"),
    ("Oats", "plastic-free paper bag", None, "OK"),
    ("Chickpeas, water, salt", "BPA-free steel can", None, "EXCLUDED"),
    ("San Marzano tomatoes, basil, salt", "glass jar, glass lid", None, "OK"),     # 'SAN' plastic code
    ("Sugar, FD&C Red No. 40", "glass jar", None, "EXCLUDED"),
    ("Coconut milk, cocoa butter, buckwheat flour, gluten-free oats", "glass jar, glass lid", None, "OK"),
    ("Enriched flour (wheat flour), soybean oil. May contain milk.", "paper", None, "EXCLUDED"),
    ("Potatoes, sunflower oil, dimethylpolysiloxane", "paper bag", None, "EXCLUDED"),
    (None, "none", "100% natural rubber", "OK"),
    ("Aqua, tocopheryl acetate, silica", "glass jar, cork", None, "OK"),
    ("farine de blé, sucre", "carton", None, "EXCLUDED"),                        # French wheat
    ("Mehl (Weizen), Zucker", "Karton", None, "EXCLUDED"),                       # German wheat
    ("Рис", "Пауч", None, "EXCLUDED"),                                           # Russian pouch
    ("Рис", "картон", None, "OK"),
    ("Rice", "glass jar", None, "UNKNOWN"),                                      # jar without its lid
    ("Beans", "metal", None, "UNKNOWN"),                                         # bare metal = can?
    ("Jam", "glass", None, "UNKNOWN"),                                           # glass jar, lid not listed
    ("Jam", "glass; glass", None, "UNKNOWN"),
    ("Cumin", "glass vial; glass", None, "UNKNOWN"),
    ("Jam", "glass jar, glass lid", None, "OK"),
    ("Wine", "verre, bouchon en liège", None, "OK"),                             # French: glass, cork
    ("Salmon", "protective gas", None, "UNKNOWN"),                               # sealed tray, not listed
    ("Salmon", "en:protective-gas, en:cardboard", None, "UNKNOWN"),               # cardboard holds no gas
    ("Mayonesa", "en:cristal", None, "UNKNOWN"),                                 # Spanish glass, no lid
    ("Mushrooms", "pl:szkło", None, "UNKNOWN"),                                  # Polish glass, no lid
    ("Pâtée", "Jetez les emballages metal dans le bac de tri", None, "UNKNOWN"),  # metal in free text
    ("Drink", "de:fsc", None, "UNKNOWN"),                                        # a label, not a material
    ("Chocolate", "aluminium foil, paper", None, "OK"),                          # plain foil is fine
    ("Fruit juice", "Recycled as food- & beverage-karton", None, "EXCLUDED"),    # liquid carton by name
    (None, "none", "Ручка полипропилен, термопластичный эластомер; щетина полибутилентерефталат.", "EXCLUDED"),
    (None, "none", "Manche en polypropylène", "EXCLUDED"),                       # French polypropylene
    ("Savon, huile d'olive", "papier, sans plastique", None, "OK"),             # French "without plastic"
    ("Seife", "Papier, ohne Kunststoff", None, "OK"),                          # German "without plastic"
    ("Soap", "paper wrapper, plastic-free", None, "OK"),                        # a claim, not a part
    ("Aqua, Acrylatescala, Glycerin", "glass jar, glass lid", None, "EXCLUDED"),  # glued words: stem 'acrylat'
    ("Aqua, 4polyquaternium-10", "glass jar, glass lid", None, "EXCLUDED"),       # stem 'polyquatern'
    ("Silica, Sodium Bicarbonate", "glass jar, glass lid", None, "OK"),           # silica is not silicone
    ("Aqua, Polysorbate 20, Polyglyceryl-3 Caprate", "glass jar, glass lid", None, "OK"),  # not plastics
    ("Aqua, sans silicone", "glass jar, glass lid", None, "OK"),                  # negated stem
    ("Ethyl acetate, trimellitic anhydride copolyrmer", "glass jar, glass lid", None, "EXCLUDED"),  # misspelled
    ("Alcool, Hansaplast", "glass jar, glass lid", None, "OK"),                   # a brand, not a material
    ("Shampoo, ohne Plastik", "glass jar, glass lid", None, "OK"),                # German "without plastic"
    ("Shea (Butyrospermum Parkii) Butter, Cocoa (Theobroma Cacao) Seed Butter", "glass jar, glass lid", None, "OK"),  # plant butters
    ("Aqua, Sodium Cocoyl Glutamate, Tetrasodium Glutamate Diacetate", "glass jar, glass lid", None, "OK"),  # not MSG
    ("Aqua, Monosodium Glutamate", "glass jar, glass lid", None, "EXCLUDED"),     # real MSG still caught
    ("Aqua, Hydrolyzed Milk Protein", "glass jar, glass lid", None, "EXCLUDED"),  # real dairy still caught
    ("Crème colorante, aqua", "glass jar, glass lid", None, "OK"),               # cosmetic cream, not dairy
    (None, "lokta paper bag", "100% New Zealand wool", "OK"),                    # known natural material
    (None, "none", "beechwood handle, tampico fiber bristles", "OK"),
    (None, "none", "glass jar, glass lid, natural rubber ring, stainless steel clamps", "OK"),
    (None, "none", "glass jar and lid", "EXCLUDED"),                             # a lid of unnamed material
    (None, "none", "stainless steel container, stainless steel lid", "OK"),      # all-steel lid, no liner
    ("Jam", "glass jar, metal lid", None, "EXCLUDED"),                           # jar lids are still lined
    (None, "none", "glass jar, glass lid, natural rubber seal, stainless steel wire clamp", "OK"),
    ("Snack", "paper tray, heat seal", None, "EXCLUDED"),                       # a plain seal is still plastic
    (None, "none", "beechwood handle, nylon bristles", "EXCLUDED"),              # a known material doesn't hide plastic
    (None, "none", "stainless steel, silicone lid", "EXCLUDED"),
    ("Мыло", "бумага", "пластик", "EXCLUDED"),                                   # Russian "plastic"
]

# With product context: (ingredients, packaging, name, categories, expected verdict)
CONTEXT_CASES = [
    ("Orange juice", "paperboard packet", "Orangensaft", "Beverages, Juices, Orange juices", "UNKNOWN"),
    ("Water, oats, sunflower oil", "cardboard", "Oat Milk", "Plant-based milks", "UNKNOWN"),
    ("Pea purée, salt", "paper", "Pea cream soup", "Soups, Dried soups", "OK"),       # dry soup mix
    ("Potatoes, sunflower oil", "cardboard box", "Long Frites", "Frozen foods, Fries", "UNKNOWN"),
    ("Tuna, olive oil", "cardboard", "Thon entier", "Seafood, Canned fish", "UNKNOWN"),
    ("Green tea", "cardboard sleeve", "Thé vert 25 sachets", "Teas", "UNKNOWN"),
    ("Rice", "cardboard, paperboard", "Kochbeutel Reis", "Rice", "UNKNOWN"),          # boil-in-bag
    ("Green tea", "paper bag", "Thé vert en vrac", "Teas, Green teas", "OK"),
    ("Red wine, sulfites", "glass bottle, cork", "Haut Médoc", "Beverages, Wines", "OK"),
    ("Pomme 99,9%", "cardboard sleeve", "Compote", "Plant-based foods, Desserts, Compotes", "UNKNOWN"),
    ("Viande bovine", "cardboard sleeve", "4 Steaks hachés", "Meats and their products, Beef", "UNKNOWN"),
    ("Eau, jus de fruits", "cardboard", "Boisson orange - 10 x 20 cl", "Beverages and beverages preparations",
     "UNKNOWN"),                                                                 # volume in the name
    ("Water, tomatoes, salt", "paper", "Tomato soup", "", "UNKNOWN"),          # water first
    ("Glucose, probiotic cultures", "cardboard", "Tribiolac", "Dietary supplements", "UNKNOWN"),
    ("Eggs", "cardboard egg carton", "12 Large Eggs", "Farming products, Eggs, Chicken eggs", "OK"),
    ("Black tea", "paper bag", "Ceylon", "Beverages and beverages preparations, Teas", "OK"),
    ("Kiwi", "cardboard tray", "Kiwi Hayward", "Plant-based foods, Fruits, Fresh fruits", "OK"),
    ("Whole oats, sugar", "cardboard", "Multi Grain Cheerios", "Cereals, Breakfast cereals", "UNKNOWN"),
    ("Viande de porc (91%)", "cardboard", "Le pâté Hénaff", "", "UNKNOWN"),     # meat first, no category
    ("Tomater, salt", "paper", "Passerade tomater", "Tomatoes and their products", "UNKNOWN"),
    ("Sun-dried tomatoes", "paper bag", "Tomates séchées", "Tomatoes and their products, Dried tomatoes", "OK"),
    ("Chickpea flour", "cardboard", "Chickpea fusilli", "Pastas, Chickpea pasta", "OK"),
    ("Nuez moscada", "fr:vidre", "Nuez moscada molida", "Spices", "UNKNOWN"),     # Catalan glass, no lid
    ("Fruits, sucre", "cardboard", "Fruit ice", "fr:Glace aux fruits", "UNKNOWN"),
]
NAMES = {banlist.OK: "OK", banlist.EXCLUDED: "EXCLUDED", banlist.UNKNOWN: "UNKNOWN"}


def main():
    db = banlist.connect()
    failures = 0
    for matcher in (banlist.Matcher(db), banlist.MemoryMatcher(db)):
        for ingredients, packaging, material, want in CASES:
            verdict, _, reasons = matcher.check(ingredients, packaging, material)
            if NAMES[verdict] != want:
                failures += 1
                print(f"FAIL [{type(matcher).__name__}] {(ingredients, packaging, material)}: "
                      f"got {NAMES[verdict]}, want {want} {reasons}")
        for ingredients, packaging, name, categories, want in CONTEXT_CASES:
            verdict, _, reasons = matcher.check(ingredients, packaging, None, name, categories)
            if NAMES[verdict] != want:
                failures += 1
                print(f"FAIL [{type(matcher).__name__}] {(name, packaging, categories)}: "
                      f"got {NAMES[verdict]}, want {want} {reasons}")
    total = 2 * (len(CASES) + len(CONTEXT_CASES))
    print(f"{total - failures}/{total} passed")
    sys.exit(1 if failures else 0)


if __name__ == "__main__":
    main()
