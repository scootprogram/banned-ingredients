#!/usr/bin/env python3
"""Read an Open Food Facts JSONL export on stdin; write code<TAB>packaging-materials text per product.

The JSONL has structured packaging ("packagings": [{"material": "en:glass", "shape": "en:jar"}, ...])
that the CSV export lacks, so it gives far better packaging information.
Usage: curl .../openfoodfacts-products.jsonl.gz | gzip -dc | python3 extract_packaging.py > packaging.tsv
"""
import json
import sys

def clean(tag):
    return tag.split(":", 1)[-1].replace("-", " ") if tag else ""

out = sys.stdout
for line in sys.stdin:
    try:
        p = json.loads(line)
    except ValueError:
        continue
    parts = []
    for pk in p.get("packagings") or []:
        if not isinstance(pk, dict):
            continue
        material, shape = clean(pk.get("material")), clean(pk.get("shape"))
        if material or shape:
            parts.append(f"{material} {shape}".strip())
    text = p.get("packaging_text_en") or p.get("packaging_text") or ""
    materials = [clean(t) for t in p.get("packaging_materials_tags") or [] if t != "en:unknown"]
    if parts or text or materials:
        row = [str(p.get("code", "")), "; ".join(parts), " ".join(text.split()), "; ".join(materials)]
        out.write("\t".join(c.replace("\t", " ") for c in row) + "\n")
