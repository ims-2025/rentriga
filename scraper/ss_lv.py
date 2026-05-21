#!/usr/bin/env python3
"""
RentRiga — ss.lv adapter (with pagination).

Differences from v1:
  - parse_index splits 'Imanta Dammes 4' style address cells into (district, street)
    using the canonical Riga district list. Required because ss.lv combines both
    into a single cell on most listing rows.
  - Thumbnail upgrade regex broadened to catch .t.jpg, .th.jpg, .th2.jpg, .th3.jpg → .jpg
  - Adapter supports multi-page fetches via a `pages` parameter — page 1 then
    pageN.html for N=2..pages. Default 1 (one page) for safety in standalone runs.

Run standalone:
    # Offline test against the fixture:
    python ss_lv.py --from-file test_fixture.html --type apartment --dry-run

    # Polite live fetch (review ss.lv robots.txt + ToS first!):
    python ss_lv.py --live --type apartment --limit 30 --pages 2 --dry-run
"""
from __future__ import annotations

import argparse, json, re, sys, urllib.parse
from dataclasses import asdict
from pathlib import Path

from base import (
    SourceAdapter, PoliteFetcher,
    parse_price, normalize_district, dedup_hash, soup, txt,
    RR_DISTRICTS, DISTRICT_ALIASES,
    DEFAULT_DELAY_SECONDS, DEFAULT_TIMEOUT, MAX_LISTINGS_HARD_CAP,
)

BASE = "https://www.ss.lv"

# Pre-build a lookup for the FIRST word of an address being a district name.
# Includes both the canonical names and the lowercase aliases.
_DISTRICT_TOKENS = {d.lower(): d for d in RR_DISTRICTS}
for alias, canonical in DISTRICT_ALIASES.items():
    _DISTRICT_TOKENS[alias.lower().split(",")[0].strip()] = canonical


def _split_address(s):
    """ss.lv often packs district + street into one cell like 'Imanta Dammes 4'.
    Try to split off the leading district name. Returns (district, street)."""
    if not s:
        return "", ""
    s = s.strip()
    # Try matching the longest leading district name first (e.g. 'Vecmīlgrāvis' before 'Vec')
    tokens = s.split()
    for n in (3, 2, 1):  # support multi-word district names ('Old Riga')
        if len(tokens) < n:
            continue
        candidate = " ".join(tokens[:n]).lower().rstrip(",")
        if candidate in _DISTRICT_TOKENS:
            district = _DISTRICT_TOKENS[candidate]
            street = " ".join(tokens[n:]).strip(", ")
            return district, street
    return "", s   # no recognizable district — pass through whole string as street


def _upgrade_thumb(url):
    """ss.lv image URLs come in as thumbnails. Upgrade to full size by removing
    the thumbnail suffix:  ".../foo.t.jpg" or ".../foo.th2.jpg" → ".../foo.jpg" """
    if not url:
        return url
    # Patterns observed: .t.jpg, .th.jpg, .th2.jpg, .th3.jpg, .th4.jpg
    return re.sub(r"\.t(?:h\d*)?\.jpg(\?.*)?$", r".jpg\1", url)


class SsLv(SourceAdapter):
    DOMAIN = "ss.lv"
    START_URLS = {
        "apartment":  BASE + "/lv/real-estate/flats/riga/all/hand_over/",
        "house":      BASE + "/lv/real-estate/homes-summer-residences/riga-region/hand_over/",
        "commercial": BASE + "/lv/real-estate/offices/riga/all/hand_over/",
        "short_term": BASE + "/lv/real-estate/flats/riga/short-term-rental/",
    }

    def __init__(self, fetcher=None, pages=1):
        super().__init__(fetcher)
        self.pages = max(1, pages)

    # ------ pagination ------
    def page_urls(self, start_url):
        """Yield start_url then start_url+page2.html, page3.html, ..."""
        yield start_url
        # ss.lv pagination URL pattern: append "pageN.html" to the category path.
        base = start_url.rstrip("/")
        for n in range(2, self.pages + 1):
            yield f"{base}/page{n}.html"

    def run(self, types=None, limit_per_type=20):
        types = types or list(self.START_URLS.keys())
        for t in types:
            start = self.START_URLS.get(t)
            if not start:
                continue
            collected = 0
            for url in self.page_urls(start):
                if collected >= limit_per_type:
                    break
                print(f"[{self.DOMAIN}] {t} -> {url}", file=sys.stderr)
                try:
                    html = self.fetch_index(url)
                except PermissionError as e:
                    print(f"[{self.DOMAIN}] {e}", file=sys.stderr); break
                except Exception as e:
                    print(f"[{self.DOMAIN}] ERROR {e}", file=sys.stderr); break
                page_count = 0
                for raw in self.parse_index(html, t):
                    listing = self.normalize(raw, t)
                    if listing is None:
                        continue
                    yield listing
                    collected += 1
                    page_count += 1
                    if collected >= limit_per_type:
                        break
                # If a page returned 0 rows, no point asking for the next page
                if page_count == 0:
                    print(f"[{self.DOMAIN}] {t} page returned 0 rows, stopping pagination", file=sys.stderr)
                    break

    # ------ parsing ------
    def parse_index(self, html, listing_type):
        s = soup(html)
        for tr in s.select("tr[id^='tr_']"):
            cells = tr.find_all("td", recursive=False)
            if len(cells) < 6:
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
                img_url = _upgrade_thumb(img_url)

            texts = [txt(c) for c in cells]

            # ss.lv layout (from end): price, series, floor, area, rooms, address
            # The address may be "District Street Number" packed into one cell.
            price_text = texts[-1] if len(texts) >= 1 else ""
            series     = texts[-2] if len(texts) >= 2 else ""
            floor      = texts[-3] if len(texts) >= 3 else ""
            area_text  = texts[-4] if len(texts) >= 4 else ""
            rooms_text = texts[-5] if len(texts) >= 5 else ""
            address    = texts[-6] if len(texts) >= 6 else ""
            title      = txt(a)

            # Some layouts also have a separate district column at texts[-7] —
            # try it first; fall back to splitting the address.
            district, street = "", address
            if len(texts) >= 7:
                explicit_district = texts[-7]
                # Sanity-check: a real district has to match our canonical list (case-insensitive)
                # or one of its aliases. Otherwise it's almost certainly the title cell.
                if explicit_district and explicit_district.lower().rstrip(",") in _DISTRICT_TOKENS:
                    district = _DISTRICT_TOKENS[explicit_district.lower().rstrip(",")]
            if not district:
                district, street = _split_address(address)

            price, price_unit = parse_price(price_text)

            if listing_type == "commercial" and "/m²" in price_text:
                price_unit = "per_m2"
            if listing_type == "short_term" and price_unit == "per_month":
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
    ap.add_argument("--limit", type=int, default=30, help="Max listings per type")
    ap.add_argument("--pages", type=int, default=1, help="Number of index pages to crawl")
    ap.add_argument("--delay", type=float, default=DEFAULT_DELAY_SECONDS)
    ap.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT)
    ap.add_argument("--out", help="Write JSON to this path")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    adapter = SsLv(PoliteFetcher(delay=args.delay, timeout=args.timeout), pages=args.pages)

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
        "meta": {"source": "ss.lv", "type": args.type, "pages": args.pages, "count": len(listings)},
        "listings": [asdict(l) for l in listings]
    }
    if args.dry_run or not args.out:
        json.dump(out, sys.stdout, ensure_ascii=False, indent=2); print()
    if args.out:
        Path(args.out).write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"[+] wrote {args.out}", file=sys.stderr)

if __name__ == "__main__":
    main()
