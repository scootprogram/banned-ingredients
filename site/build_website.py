#!/usr/bin/env python3
"""Build the standalone website (GitHub Pages) from site/clean-shelf.html.

The Claude page is published without a document skeleton (the host adds one); a normal
website needs its own. This wraps the same page in a full HTML document and copies the data.

Usage: python3 site/build_website.py <output folder>   e.g. ../scootprogram.github.io
Writes index.html, products.json and .nojekyll into the folder (and removes the old needs.json).
"""
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def main():
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    out = Path(sys.argv[1]).resolve()
    out.mkdir(parents=True, exist_ok=True)
    page = (ROOT / "site" / "clean-shelf.html").read_text(encoding="utf-8")
    # Head content is everything up to the closing </style>; the rest is the body.
    split = page.index("</style>") + len("</style>")
    head, body = page[:split], page[split:]
    html = ("<!doctype html>\n<html lang=\"en\">\n<head>\n<meta charset=\"utf-8\">\n"
            "<meta name=\"viewport\" content=\"width=device-width, initial-scale=1, viewport-fit=cover\">\n"
            "<meta name=\"description\" content=\"Beauty and household products with no plastic anywhere and "
            "none of a list of common allergens and additives.\">\n"
            "<style>html, body { margin: 0; } img { max-width: 100%; }</style>\n"
            f"{head}\n</head>\n<body>\n{body.strip()}\n</body>\n</html>\n")
    (out / "index.html").write_text(html, encoding="utf-8")
    subprocess.run([sys.executable, str(ROOT / "site" / "export_json.py"), str(ROOT), str(out / "products.json")],
                   check=True)
    (out / "needs.json").unlink(missing_ok=True)  # the old "Help fill the gaps" tab's data, no longer used
    (out / ".nojekyll").write_text("")  # serve files as-is, no Jekyll processing
    print(f"website written to {out}")


if __name__ == "__main__":
    main()
