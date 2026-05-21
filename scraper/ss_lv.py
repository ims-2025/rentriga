#!/usr/bin/env python3
"""
RentRiga — ss.lv adapter.

ss.lv uses a long index table with rows whose ids start with `tr_`. Each row has
cells for image, title (link), district, street, rooms, area, floor, series, and
price. The same parser works for all four rental categories — only the START_URL
differs per type.

Run standalone to fetch+print results for one category:

    # Offline test against the saved fixture:
    python ss_lv.py --from-file test_fixture.html --type apartment --dry-run

    # Polite live fetch (review ss.lv robots.txt + ToS first!):
    python ss_lv.py --live --type apartment --limit 10 --dry-run
"""
from __future__ import annotations

import argparse, json, re, sys, urllib.parse
from dataclasses import asdict
from pathlib import Path

from base import (
    SourceAdapter, PoliteFetcher, Listing,
    parse_price, normalize_district, dedup_hash, soup, txt,
    DEFAULT_DELAY_SECONDS, DEFAULT_TIMEOUT, MAX_LISTINGS_HARD_CAP,
)

BASE = "https://www.ss.lv"


class SsLv(SourceAdapter):
    DOMAIN = "ss.lv"
    # Each path is the "hand_over" (rent) section of ss.lv for a given category.
    # Verify against ss.lv yourself — the site occasionally restructures URLs.
    START_URLS = {
        "apartment":  BASE + "/lv/real-estate/flats/riga/all/hand_over/",
        "house":      BASE + "/lv/real-estate/homes-summer-residences/riga-region/hand_over/",
        "commercial": BASE + "/lv/real-estate/offices/riga/all/hand_over/",
        "short_term": BASE + "/lv/real-estate/flats/riga/short-term-rental/",
    }

    def parse_index(self, html, listing_type):
        s = soup(html)
        for tr in s.select("tr[id^='tr_']"):
            cells = tr.find_all("td", recursive=False)
            if len(cells) < 8:
                continue

            a = tr.select_one("a[id^='dm_'], a[href^='/lv/real-estate/']")
            if not a or not a.get("href"):
                continue
            href = a["href"]
            url = urllib.parse.urljoin(BASE, href)
            sid = re.sub(r"[^a-zA-Z0-9_-]", "_",
                        href.rstrip("/").split("/")[-1].replace(".html", ""))

            img = tr.select_one("img")
            img_url = None
            if img:
                img_url = img.get("src") or img.get("data-src")
                if img_url and img_url.startswith("//"):
                    img_url = "https:" + img_url
                if img_url:
                    img_url = re.sub(r"\.t\.jpg(\?.*)?$", ".jpg", img_url)

            texts = [txt(c) for c in cells]
            # Robust to a leading checkbox column — slice from the end.
            price_text = texts[-1] if len(texts) >= 1 else ""
            series     = texts[-2] if len(texts) >= 2 else ""
            floor      = texts[-3] if len(texts) >= 3 else ""
            area_text  = texts[-4] if len(texts) >= 4 else ""
            rooms_text = texts[-5] if len(texts) >= 5 else ""
            street     = texts[-6] if len(texts) >= 6 else ""
            district   = texts[-7] if len(texts) >= 7 else ""
            title      = txt(a)

            price, price_unit = parse_price(price_text)

            # For commercial spaces, ss.lv often shows €/m² instead of total — keep that signal.
            if listing_type == "commercial" and "/m²" in price_text:
                price_unit = "per_m2"
            # For short-term, normalize to per_night when listing is daily.
            if listing_type == "short_term" and price_unit == "per_month":
                # Heuristic: short-term ss.lv prices are usually quoted per night already.
                price_unit = "per_night"

            try:
                rooms = int(re.search(r"\d+", rooms_text).group()) if re.search(r"\d+", rooms_text) else None
            except (AttributeError, ValueError):
                rooms = None
            try:
                area_m = re.search(r"([\d.,]+)", area_text)
                area = float(area_m.group(1).replace(",", ".")) if area_m else None
            except (AttributeError, ValueError):
                area = None

            yield {
                "source_id": sid,
                "source_url": url,
                "title": title,
                "district_raw": district,
                "street": street,
                "rooms": rooms,
                "area": area,
                "floor": floor or None,
                "price": price,
                "price_unit": price_unit,
                "image": img_url,
            }


# ---------- CLI ---------------------------------------------------------------

def main():
    ap = argparse.ArgumentParser()
    src = ap.add_mutually_exclusive_group(required=True)
    src.add_argument("--live", action="store_true")
    src.add_argument("--from-file", help="Parse a saved index HTML file (offline test)")

    ap.add_argument("--type", choices=list(SsLv.START_URLS.keys()), default="apartment")
    ap.add_argument("--limit", type=int, default=10, help="Max listings to extract (hard cap 500)")
    ap.add_argument("--delay", type=float, default=DEFAULT_DELAY_SECONDS)
    ap.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT)
    ap.add_argument("--out", help="Write JSON to this path")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    adapter = SsLv(PoliteFetcher(delay=args.delay, timeout=args.timeout))

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

    out = {
        "meta": {"source": "ss.lv", "type": args.type, "count": len(listings)},
        "listings": [asdict(l) for l in listings]
    }
    if args.dry_run or not args.out:
        json.dump(out, sys.stdout, ensure_ascii=False, indent=2); print()
    if args.out:
        Path(args.out).write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"[+] wrote {args.out}", file=sys.stderr)

if __name__ == "__main__":
    main()
