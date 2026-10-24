#!/usr/bin/env bash
# Download the Open Food/Beauty/Products/Pet Facts exports into data/raw/ and extract
# structured packaging from the JSONL exports. Safe to re-run: finished files are skipped,
# and a broken connection fails loudly instead of leaving a silently truncated file.
set -euo pipefail
cd "$(dirname "$0")/.."
mkdir -p data/raw
B=https://openfoodfacts-ds.s3.eu-west-3.amazonaws.com

for f in en.openfoodfacts.org.products.csv.gz en.openbeautyfacts.org.products.csv.gz \
         en.openproductsfacts.org.products.csv.gz en.openpetfoodfacts.org.products.csv.gz; do
  [ -s "data/raw/$f" ] && gzip -t "data/raw/$f" 2>/dev/null && { echo "have $f"; continue; }
  echo "downloading $f"
  curl -fsS --retry 5 -C - -o "data/raw/$f.part" "$B/$f" && gzip -t "data/raw/$f.part" && mv "data/raw/$f.part" "data/raw/$f"
done

for s in openfoodfacts openbeautyfacts openproductsfacts openpetfoodfacts; do
  out="data/raw/$s.packaging.tsv"
  [ -s "$out" ] && { echo "have $out"; continue; }
  echo "extracting packaging from $s (the food export is 13 GB; ~20 min)"
  curl -fsS --retry 5 "$B/$s-products.jsonl.gz" | gzip -dc | python3 pipeline/extract_packaging.py > "$out.part"
  mv "$out.part" "$out"
  echo "  $(wc -l < "$out") products with packaging"
done
