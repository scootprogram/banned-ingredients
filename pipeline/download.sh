#!/usr/bin/env bash
# Download the Open Beauty Facts and Open Products Facts exports into data/raw/ and extract
# structured packaging from the JSONL exports. Safe to re-run: finished files are skipped,
# and a broken connection fails loudly instead of leaving a silently truncated file.
set -euo pipefail
cd "$(dirname "$0")/.."
mkdir -p data/raw
B=https://openfoodfacts-ds.s3.eu-west-3.amazonaws.com

# Beauty and household products only; food and pet food are deliberately left out.
for f in en.openbeautyfacts.org.products.csv.gz en.openproductsfacts.org.products.csv.gz; do
  [ -s "data/raw/$f" ] && gzip -t "data/raw/$f" 2>/dev/null && { echo "have $f"; continue; }
  echo "downloading $f"
  curl -fsS --retry 5 -C - -o "data/raw/$f.part" "$B/$f" && gzip -t "data/raw/$f.part" && mv "data/raw/$f.part" "data/raw/$f"
done

for s in openbeautyfacts openproductsfacts; do
  out="data/raw/$s.packaging.tsv"
  [ -s "$out" ] && { echo "have $out"; continue; }
  echo "extracting packaging from $s"
  curl -fsS --retry 5 "$B/$s-products.jsonl.gz" | gzip -dc | python3 pipeline/extract_packaging.py > "$out.part"
  mv "$out.part" "$out"
  echo "  $(wc -l < "$out") products with packaging"
done
