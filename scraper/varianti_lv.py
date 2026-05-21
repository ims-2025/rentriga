#!/usr/bin/env python3
"""
RentRiga — varianti.lv adapter.

varianti.lv is a Latvian real-estate listings portal with relatively clean,
mostly static HTML — each search result is a card with a title link, price,
location, rooms, and area. Selectors are isolated at the top of `parse_index`
so they're easy to update if the site restructures.

Selector verification needed: open https://www.varianti.lv/lv/real-estate/flats
in your browser, inspect a single listing card, and confirm CARD_SELECTOR and
the field selectors below still match. If varianti.lv has rotated their CSS
classes, update them here.
"""
from __future__ import annotations

import argparse, json, re, sys, urllib.parse
from dataclasses import asdict
from pathlib import Path

from base import (
    SourceAdapter, PoliteFetcher,
    parse_price, soup, txt,
    DEFAULT_DELAY_SECONDS, DEFAULT_TIMEOUT, MAX_LISTINGS_HARD_CAP,
)

BASE = "https://www.varianti.lv"

# === Update these if varianti.lv changes their HTML ===
CARD_SELECTOR     = "article.real-estate-item, div.listing-card, li.search-result"
TITLE_SELECTOR    = "a.listing-title, h2 a, h3 a, .title a"
PRICE_SELECTOR    = ".price, .listing-price, [data-price]"
LOCATION_SELECTOR = ".location, .address, .listing-location"
ROOMS_SELECTOR    = ".rooms, [data-rooms]"
AREA_SELECTOR     = ".area, [data-area]"
IMAGE_SELECTOR    = "img"


class VariantiLv(SourceAdapter):
    DOMAIN = "varianti.lv"
    START_URLS = {
        "apartment":  BASE + "/lv/real-estate/flats/riga?deal=rent",
        "house":      BASE + "/lv/real-estate/houses/riga?deal=rent",
        "commercial": BASE + "/lv/real-estate/commercial/riga?deal=rent",
    }

    def parse_index(self, html, listing_type):
        s = soup(html)
        cards = s.select(CARD_SELECTOR)

        # Fallback: some Latvian portals use a generic article/list-item structure.
        if not cards:
            cards = s.select("article, .result-item, .property-card")

        for card in cards:
            a = card.select_one(TITLE_SELECTOR) or card.select_one("a[href*='real-estate']")
            if not a or not a.get("href"):
                continue
            url = urllib.parse.urljoin(BASE, a["href"])
            sid = re.sub(r"[^a-zA-Z0-9_-]", "_",
                        a["href"].rstrip("/").split("/")[-1].replace(".html", ""))
            if not sid:
                continue

            title = txt(a)

            price_node = card.select_one(PRICE_SELECTOR)
            price, price_unit = parse_price(txt(price_node))
            if price is None:
                # Some cards embed the price as a data attribute
                dp = card.select_one("[data-price]")
                if dp and dp.get("data-price"):
                    try:
                        price = float(dp["data-price"]); price_unit = "per_month"
                    except ValueError:
                        pass

            loc_text = txt(card.select_one(LOCATION_SELECTOR))
            district, street = _split_location(loc_text)

            rooms = _extract_int(card, ROOMS_SELECTOR, r"(\d+)\s*(?:istab|room)")
            area  = _extract_float(card, AREA_SELECTOR, r"(\d+(?:[.,]\d+)?)\s*m")

            img = card.select_one(IMAGE_SELECTOR)
            img_url = None
            if img:
                img_url = img.get("src") or img.get("data-src") or img.get("data-original")
                if img_url and img_url.startswith("//"):
                    img_url = "https:" + img_url

            yield {
                "source_id": sid,
                "source_url": url,
                "title": title,
                "district_raw": district,
                "street": street,
                "rooms": rooms,
                "area": area,
                "price": price,
                "price_unit": price_unit,
                "image": img_url,
            }


# ---------- helpers ----------------------------------------------------------

def _split_location(s):
    """varianti.lv typically renders 'Rīga, Centrs, Brīvības iela 102'. Drop the
    city prefix; first remaining segment is the district, rest is the street."""
    if not s:
        return "", ""
    parts = [p.strip() for p in s.split(",") if p.strip()]
    parts = [p for p in parts if p.lower() not in ("rīga", "riga")]
    if not parts:
        return "", ""
    if len(parts) == 1:
        return parts[0], ""
    return parts[0], ", ".join(parts[1:])

def _extract_int(card, selector, pattern):
    node = card.select_one(selector)
    text = txt(node) if node else txt(card)
    m = re.search(pattern, text, flags=re.IGNORECASE)
    return int(m.group(1)) if m else None

def _extract_float(card, selector, pattern):
    node = card.select_one(selector)
    text = txt(node) if node else txt(card)
    m = re.search(pattern, text, flags=re.IGNORECASE)
    if not m:
        return None
    try:
        return float(m.group(1).replace(",", "."))
    except ValueError:
        return None


# ---------- CLI ---------------------------------------------------------------

def main():
    ap = argparse.ArgumentParser()
    src = ap.add_mutually_exclusive_group(required=True)
    src.add_argument("--live", action="store_true")
    src.add_argument("--from-file", help="Parse a saved index HTML file (offline test)")

    ap.add_argument("--type", choices=list(VariantiLv.START_URLS.keys()), default="apartment")
    ap.add_argument("--limit", type=int, default=10)
    ap.add_argument("--delay", type=float, default=DEFAULT_DELAY_SECONDS)
    ap.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT)
    ap.add_argument("--out", help="Write JSON to this path")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    adapter = VariantiLv(PoliteFetcher(delay=args.delay, timeout=args.timeout))
    listings = []
    if args.from_file:
        html = Path(args.from_file).read_text(encoding="utf-8")
        for raw in adapter.parse_index(html, args.type):
            l = adapter.normalize(raw, args.type)
            if l: listings.append(l)
            if len(listings) >= min(args.limit, MAX_LISTINGS_HARD_CAP):
                break
    else:
        for l in adapter.run(types=[args.type], limit_per_type=args.limit):
            listings.append(l)

    out = {"meta":{"source":"varianti.lv","type":args.type,"count":len(listings)},
           "listings":[asdict(l) for l in listings]}
    if args.dry_run or not args.out:
        json.dump(out, sys.stdout, ensure_ascii=False, indent=2); print()
    if args.out:
        Path(args.out).write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"[+] wrote {args.out}", file=sys.stderr)

if __name__ == "__main__":
    main()
