#!/usr/bin/env python3
"""Count visitors' answers about products' packaging and keep the most common answer.

Input: the responses of the Clean Shelf "Help" form as CSV, one row per submission, with a
barcode column and one column per question (recyclable, non-toxic, sustainable) answered
Yes / No / Not sure. Columns are found by keyword, so the form's exact wording doesn't matter.

For each product and question, the most common of Yes and No wins and the rest is ignored.
"Not sure" and blank answers don't count; a tie leaves the question undecided.

Writes data/packaging_votes.json, which site/export_json.py merges into the page data:
  {"<barcode>": {"recyclable": "yes"|"no"|"undecided", "nontoxic": ..., "sustainable": ...,
                 "responses": <number of submissions>}}

Usage: python3 pipeline/packaging_votes.py <responses.csv | published CSV URL>
"""
import collections
import csv
import io
import json
import re
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
QUESTIONS = {  # key -> keywords that identify its column in the form's CSV
    "recyclable": ["recyclable", "recycle"],
    "nontoxic": ["non-toxic", "nontoxic", "non toxic", "toxic"],
    "sustainable": ["sustainable", "sustainab"],
}
CODE_KEYWORDS = ["barcode", "code", "product id"]


def read_rows(source):
    if re.match(r"https?://", source):
        with urllib.request.urlopen(source, timeout=60) as r:
            text = r.read().decode("utf-8-sig")
    else:
        text = Path(source).read_text(encoding="utf-8-sig")
    return list(csv.DictReader(io.StringIO(text)))


def find_column(header, keywords):
    for col in header:
        if any(k in col.lower() for k in keywords):
            return col
    return None


def answer(value):
    v = (value or "").strip().lower()
    return "yes" if v.startswith("y") else "no" if v.startswith("n") and not v.startswith("not") else None


def majority(answers):
    counts = collections.Counter(a for a in answers if a)
    if not counts:
        return "undecided"
    (top, n), *rest = counts.most_common()
    return "undecided" if rest and rest[0][1] == n else top


def main():
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    rows = read_rows(sys.argv[1])
    if not rows:
        sys.exit("no responses found")
    header = list(rows[0].keys())
    code_col = find_column(header, CODE_KEYWORDS)
    cols = {q: find_column(header, kw) for q, kw in QUESTIONS.items()}
    missing = [q for q, c in [("barcode", code_col), *cols.items()] if c is None]
    if missing:
        sys.exit(f"couldn't find column(s) for {missing} in {header}")

    by_code = collections.defaultdict(list)
    for row in rows:
        code = re.sub(r"\D", "", row.get(code_col) or "")
        if code:
            by_code[code].append(row)
    votes = {code: {**{q: majority(answer(r[col]) for r in rs) for q, col in cols.items()}, "responses": len(rs)}
             for code, rs in by_code.items()}
    out = ROOT / "data" / "packaging_votes.json"
    out.write_text(json.dumps(votes, indent=1, sort_keys=True), encoding="utf-8")
    print(f"{len(rows)} responses for {len(votes)} products -> {out}")


if __name__ == "__main__":
    main()
