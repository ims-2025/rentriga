#!/usr/bin/env python3
"""
Build sitemap.xml for RentRiga.

Reads listing IDs out of assets/js/data.js and emits a sitemap covering:
- Static pages (home, listings, category pages, legal pages)
- Per-listing detail URLs
- hreflang alternates for EN / LV / RU

Run from the project root:
    python3 tools/build_sitemap.py [--base https://rentriga.com]
"""
import argparse
import datetime as dt
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "assets" / "js" / "data.js"
OUT  = ROOT / "sitemap.xml"

LANGS = ["en", "lv", "ru"]

STATIC_PAGES = [
    ("",                       "weekly",  "1.0"),
    ("listings.html",          "hourly",  "0.95"),
    ("listings.html?type=apartment",  "hourly",  "0.9"),
    ("listings.html?type=house",      "hourly",  "0.9"),
    ("listings.html?type=commercial", "hourly",  "0.9"),
    ("listings.html?type=short_term", "hourly",  "0.9"),
    ("terms.html",             "monthly", "0.3"),
    ("privacy.html",           "monthly", "0.3"),
    ("cookies.html",           "monthly", "0.3"),
    ("takedown.html",          "monthly", "0.3"),
]

def listing_ids():
    if not DATA.exists():
        print(f"[!] {DATA} not found", file=sys.stderr)
        return []
    text = DATA.read_text(encoding="utf-8")
    return re.findall(r'\{id:"([^"]+)"', text)

def xml_escape(s: str) -> str:
    return (s.replace("&", "&amp;")
             .replace("<", "&lt;")
             .replace(">", "&gt;")
             .replace('"', "&quot;")
             .replace("'", "&apos;"))

def url_node(loc, lastmod, changefreq, priority, alternates=None):
    lines = ["  <url>",
             f"    <loc>{xml_escape(loc)}</loc>",
             f"    <lastmod>{lastmod}</lastmod>",
             f"    <changefreq>{changefreq}</changefreq>",
             f"    <priority>{priority}</priority>"]
    for hreflang, href in (alternates or []):
        lines.append(f'    <xhtml:link rel="alternate" hreflang="{hreflang}" href="{xml_escape(href)}"/>')
    lines.append("  </url>")
    return "\n".join(lines)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="https://rentriga.com",
                    help="Public base URL (no trailing slash)")
    args = ap.parse_args()
    base = args.base.rstrip("/")

    today = dt.date.today().isoformat()
    ids = listing_ids()
    print(f"[+] {len(ids)} listings found", file=sys.stderr)

    body = ['<?xml version="1.0" encoding="UTF-8"?>',
            '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"',
            '        xmlns:xhtml="http://www.w3.org/1999/xhtml">']

    for path, freq, prio in STATIC_PAGES:
        loc = f"{base}/{path}" if path else f"{base}/"
        alts = [(lang, f"{base}/{lang}/{path}".rstrip("/") + ("" if path else "")) for lang in LANGS]
        body.append(url_node(loc, today, freq, prio, alts))

    for lid in ids:
        loc = f"{base}/listing.html?id={lid}"
        alts = [(lang, f"{base}/{lang}/listing.html?id={lid}") for lang in LANGS]
        body.append(url_node(loc, today, "daily", "0.8", alts))

    body.append("</urlset>")
    OUT.write_text("\n".join(body) + "\n", encoding="utf-8")
    print(f"[+] wrote {OUT.relative_to(ROOT)} ({sum(1 for _ in OUT.read_text().splitlines())} lines)", file=sys.stderr)

if __name__ == "__main__":
    main()
