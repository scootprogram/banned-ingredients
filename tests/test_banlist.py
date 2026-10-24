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
    total = 2 * len(CASES)
    print(f"{total - failures}/{total} passed")
    sys.exit(1 if failures else 0)


if __name__ == "__main__":
    main()
