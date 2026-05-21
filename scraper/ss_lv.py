#!/usr/bin/env python3
"""
RentRiga — ss.lv rental scraper (prototype)

Polite, conservative scraper that fetches Riga rental flat listings from ss.lv
and normalizes them into RentRiga's listing schema.

DESIGN NOTES
- Honors robots.txt before any fetch.
- Identifies with a friendly User-Agent and a contact email.
- Rate-limited (default 3.0s between requests).
- Default LIMITS the run to 1 results page and 10 listings (max ~11 requests).
- Defaults to --dry-run; you must opt in to write output.
- Network calls go through Python's stdlib `urllib` so it has zero non-stdlib
  required deps; install BeautifulSoup for nicer parsing (recommended).

USAGE
    # Verify config + parsing in offline mode using a saved sample HTML file:
    python ss_lv.py --from-file sample_listing_index.html --dry-run

    # Politely fetch one page from ss.lv (LIVE — review robots.txt and ToS first):
    python ss_lv.py --live --pages 1 --limit 10 --dry-run

    # When happy, write JSON output:
    python ss_lv.py --live --pages 1 --limit 10 --out scraped.json

REQUIRED REVIEW BEFORE LIVE USE
    1) https://www.ss.lv/robots.txt   — confirm the path you're targeting is allowed.
    2) ss.lv Terms of Service        — confirm aggregation is acceptable, or seek a feed agreement.
    3) GDPR posture                  — do not store contact phone numbers; mask before persistence.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import re
import sys
import time
import urllib.parse
import urllib.request
import urllib.robotparser
from dataclasses import dataclass, asdict, field
from pathlib import Path
from typing import Iterable, Iterator, Optional

try:
    from bs4 import BeautifulSoup  # type: ignore
    HAS_BS4 = True
except ImportError:
    HAS_BS4 = False

# ---------- Configuration ----------------------------------------------------

BASE = "https://www.ss.lv"
# Riga apartments for rent (lv locale). Verify this is the URL you want;
# ss.lv splits by room count under /1, /2, /3, /4 etc. — we use /all.
START_PATH = "/lv/real-estate/flats/riga/all/hand_over/"

USER_AGENT = "RentRigaBot/0.1 (+https://rentriga.com/about; contact: hello@rentriga.com)"

# Be polite. ss.lv is a small Latvian site — don't hammer it.
DEFAULT_DELAY_SECONDS = 3.0
DEFAULT_TIMEOUT       = 20
MAX_LISTINGS_HARD_CAP = 200  # never exceed in a single run regardless of CLI args

# Canonical district list — must mirror RR_DISTRICTS in assets/js/data.js
RR_DISTRICTS = {
    "Centrs","Vecrīga","Āgenskalns","Mežaparks","Teika","Purvciems","Imanta",
    "Ziepniekkalns","Jugla","Daugavgrīva","Sarkandaugava","Bolderāja","Pļavnieki",
    "Ķengarags","Iļģuciems","Zolitūde","Skanste","Andrejsala","Brasa",
    "Čiekurkalns","Berģi","Vecmīlgrāvis"
}

# District name normalization (ss.lv uses some short or alt names)
DISTRICT_ALIASES = {
    "centre": "Centrs", "centrs": "Centrs", "centre, kluss centrs": "Centrs",
    "vecriga": "Vecrīga", "vecrīga": "Vecrīga", "old riga": "Vecrīga",
    "agenskalns": "Āgenskalns", "āgenskalns": "Āgenskalns",
    "mezaparks": "Mežaparks", "mežaparks": "Mežaparks",
    "purvciems": "Purvciems", "imanta": "Imanta", "teika": "Teika",
    "jugla": "Jugla", "daugavgriva": "Daugavgrīva", "daugavgrīva": "Daugavgrīva",
    "sarkandaugava": "Sarkandaugava", "bolderaja": "Bolderāja", "bolderāja": "Bolderāja",
    "plavnieki": "Pļavnieki", "pļavnieki": "Pļavnieki",
    "kengarags": "Ķengarags", "ķengarags": "Ķengarags",
    "ilguciems": "Iļģuciems", "iļģuciems": "Iļģuciems",
    "zolitude": "Zolitūde", "zolitūde": "Zolitūde",
    "skanste": "Skanste", "andrejsala": "Andrejsala", "brasa": "Brasa",
    "ciekurkalns": "Čiekurkalns", "čiekurkalns": "Čiekurkalns",
    "bergi": "Berģi", "berģi": "Berģi",
    "vecmilgravis": "Vecmīlgrāvis", "vecmīlgrāvis": "Vecmīlgrāvis",
    "ziepniekkalns": "Ziepniekkalns",
}

# ---------- Data structures --------------------------------------------------

@dataclass
class Listing:
    """RentRiga canonical schema (subset)."""
    id: str
    source_id: str
    source_domain: str
    source_url: str
    type: str                          # 'apartment' | 'house' | 'commercial' | 'short_term'
    title: str
    district: str
    street: str = ""
    price: Optional[float] = None
    price_unit: str = "per_month"
    currency: str = "EUR"
    rooms: Optional[int] = None
    area: Optional[float] = None
    floor: Optional[str] = None
    year: Optional[int] = None
    image: Optional[str] = None
    description: str = ""
    amenities: list = field(default_factory=list)
    first_seen: str = field(default_factory=lambda: dt.datetime.utcnow().isoformat(timespec="seconds") + "Z")
    last_seen:  str = field(default_factory=lambda: dt.datetime.utcnow().isoformat(timespec="seconds") + "Z")
    dedup_hash: str = ""

# ---------- HTTP fetching ----------------------------------------------------

class PoliteFetcher:
    """A tiny HTTP fetcher that obeys robots.txt and rate-limits all calls."""

    def __init__(self, user_agent: str, delay: float, timeout: int):
        self.user_agent = user_agent
        self.delay = delay
        self.timeout = timeout
        self._last_call = 0.0
        self._rp = urllib.robotparser.RobotFileParser()
        self._robots_loaded = False

    def _load_robots(self):
        url = urllib.parse.urljoin(BASE, "/robots.txt")
        self._rp.set_url(url)
        try:
            self._rp.read()
            self._robots_loaded = True
            print(f"[robots] loaded {url}", file=sys.stderr)
        except Exception as e:
            print(f"[robots] WARNING: could not read {url}: {e}", file=sys.stderr)
            self._robots_loaded = False

    def allowed(self, url: str) -> bool:
        if not self._robots_loaded:
            self._load_robots()
        if not self._robots_loaded:
            return False  # fail closed
        return self._rp.can_fetch(self.user_agent, url)

    def get(self, url: str) -> str:
        if not self.allowed(url):
            raise PermissionError(f"robots.txt disallows {url}")
        # rate-limit
        wait = (self._last_call + self.delay) - time.monotonic()
        if wait > 0:
            time.sleep(wait)
        req = urllib.request.Request(url, headers={
            "User-Agent": self.user_agent,
            "Accept-Language": "lv,en;q=0.8,ru;q=0.6",
            "Accept": "text/html,application/xhtml+xml",
        })
        with urllib.request.urlopen(req, timeout=self.timeout) as resp:
            charset = resp.headers.get_content_charset() or "utf-8"
            data = resp.read().decode(charset, errors="replace")
        self._last_call = time.monotonic()
        return data

# ---------- Parsing ----------------------------------------------------------

def _txt(node) -> str:
    if node is None:
        return ""
    if HAS_BS4:
        return re.sub(r"\s+", " ", node.get_text(" ", strip=True)).strip()
    return re.sub(r"\s+", " ", str(node)).strip()

def parse_price(s):
    """ss.lv prices typically look like '€ 450 / mēn.' or '€ 450 (€ 7.50/m²)'"""
    if not s:
        return None, "per_month"
    s = s.strip()
    # ss.lv prices can read "€ 650" or "650 €" or "650 EUR" — match either order.
    m = re.search(r"(?:€|EUR)\s*([\d\s.,]+)|([\d\s.,]+)\s*(?:€|EUR)", s)
    val = None
    if m:
        raw = (m.group(1) or m.group(2) or "").strip()
        raw = re.sub(r"\s+", "", raw).replace(",", ".")
        # Heuristic: "1.100" → 1100 (European thousands), "1100.50" → 1100.5
        if re.fullmatch(r"\d{1,3}\.\d{3}", raw):
            raw = raw.replace(".", "")
        try:
            val = float(raw)
        except ValueError:
            val = None
    unit = "per_month"
    low = s.lower()
    if "/nakt" in low or "/night" in low:
        unit = "per_night"
    elif "/m²" in s or "/m2" in low:
        unit = "per_m2"
    return val, unit

def normalize_district(s: str) -> str:
    if not s:
        return ""
    key = s.strip().lower()
    if key in DISTRICT_ALIASES:
        return DISTRICT_ALIASES[key]
    # title-case heuristics
    title = s.strip()
    return title if title in RR_DISTRICTS else (DISTRICT_ALIASES.get(title.lower(), title))

def dedup_hash(street: str, area: Optional[float], rooms: Optional[int]) -> str:
    key = f"{street.strip().lower()}|{round(area or 0)}|{rooms or 0}"
    return hashlib.sha1(key.encode()).hexdigest()[:16]

def parse_listing_index(html: str) -> Iterator[dict]:
    """
    Yield raw listing dicts from an ss.lv listings index page.

    ss.lv uses a long table with rows whose ids start with 'tr_'. Each row has cells:
      [checkbox/img] [photo+title link] [district] [street] [rooms] [area] [floor] [series] [price]

    Selectors are isolated here so they're easy to update if ss.lv changes its HTML.
    """
    if not HAS_BS4:
        raise RuntimeError(
            "BeautifulSoup4 is required for parsing. Install with:\n"
            "  pip install beautifulsoup4"
        )
    soup = BeautifulSoup(html, "html.parser")

    rows = soup.select("tr[id^='tr_']")
    for tr in rows:
        # Skip header / promo rows
        if not tr.select("td"):
            continue
        cells = tr.find_all("td", recursive=False)
        if len(cells) < 8:
            continue

        # The listing detail link is the title anchor (col 2 normally)
        a = tr.select_one("a[id^='dm_'], a[href^='/lv/real-estate/']")
        if not a or not a.get("href"):
            continue
        href = a["href"]
        url = urllib.parse.urljoin(BASE, href)
        listing_id = re.sub(r"[^a-zA-Z0-9_-]", "_", href.rstrip("/").split("/")[-1].replace(".html",""))

        # Photo
        img = tr.select_one("img")
        img_url = None
        if img:
            img_url = img.get("src") or img.get("data-src")
            if img_url and img_url.startswith("//"):
                img_url = "https:" + img_url
            # ss.lv thumbnails are tiny — try to upgrade to .800.jpg if a pattern matches
            if img_url:
                img_url = re.sub(r"\.t\.jpg(\?.*)?$", ".jpg", img_url)

        # Heuristic column extraction
        texts = [_txt(c) for c in cells]
        # Most rentals: texts ≈ [chk?, title, district, street, rooms, area, floor, series, price]
        # Slice from the end to be robust to leading checkbox column:
        price_text = texts[-1] if len(texts) >= 1 else ""
        series     = texts[-2] if len(texts) >= 2 else ""
        floor      = texts[-3] if len(texts) >= 3 else ""
        area_text  = texts[-4] if len(texts) >= 4 else ""
        rooms_text = texts[-5] if len(texts) >= 5 else ""
        street     = texts[-6] if len(texts) >= 6 else ""
        district   = texts[-7] if len(texts) >= 7 else ""
        title      = _txt(a)

        price, price_unit = parse_price(price_text)
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
            "source_id": listing_id,
            "source_url": url,
            "title": title,
            "district_raw": district,
            "street": street,
            "rooms": rooms,
            "area": area,
            "floor": floor,
            "series": series,
            "price": price,
            "price_unit": price_unit,
            "image": img_url,
            "raw_price_text": price_text,
        }

def normalize(raw: dict) -> Optional[Listing]:
    if not raw.get("title") or raw.get("price") is None:
        return None
    district = normalize_district(raw.get("district_raw", ""))
    if not district:
        district = "Unknown"

    return Listing(
        id="ss-" + raw["source_id"],
        source_id=raw["source_id"],
        source_domain="ss.lv",
        source_url=raw["source_url"],
        type="apartment",  # this index URL targets apartments
        title=raw["title"][:200],
        district=district,
        street=raw["street"],
        price=raw["price"],
        price_unit=raw["price_unit"],
        currency="EUR",
        rooms=raw["rooms"],
        area=raw["area"],
        floor=raw["floor"] or None,
        image=raw.get("image"),
        dedup_hash=dedup_hash(raw["street"], raw["area"], raw["rooms"]),
    )

# ---------- Runner -----------------------------------------------------------

def run(args) -> int:
    fetcher = PoliteFetcher(USER_AGENT, args.delay, args.timeout) if args.live else None
    pages = []

    if args.from_file:
        html = Path(args.from_file).read_text(encoding="utf-8")
        pages.append(("file://" + args.from_file, html))
    elif args.live:
        page_n = 1
        while page_n <= args.pages:
            path = START_PATH if page_n == 1 else START_PATH + f"page{page_n}.html"
            url = urllib.parse.urljoin(BASE, path)
            print(f"[fetch] {url}", file=sys.stderr)
            try:
                html = fetcher.get(url)
            except PermissionError as e:
                print(f"[robots] {e}", file=sys.stderr)
                return 2
            except Exception as e:
                print(f"[error] {e}", file=sys.stderr)
                return 3
            pages.append((url, html))
            page_n += 1
    else:
        print("ERROR: must pass --from-file or --live (see --help).", file=sys.stderr)
        return 1

    found_raw = []
    for src_url, html in pages:
        for raw in parse_listing_index(html):
            found_raw.append(raw)
            if len(found_raw) >= min(args.limit, MAX_LISTINGS_HARD_CAP):
                break
        if len(found_raw) >= min(args.limit, MAX_LISTINGS_HARD_CAP):
            break

    listings = [l for l in (normalize(r) for r in found_raw) if l]
    print(f"[+] parsed {len(found_raw)} rows, normalized {len(listings)} listings", file=sys.stderr)

    out = {
        "meta": {
            "source": "ss.lv",
            "scraped_at": dt.datetime.utcnow().isoformat(timespec="seconds") + "Z",
            "count": len(listings)
        },
        "listings": [asdict(l) for l in listings]
    }

    if args.dry_run or not args.out:
        json.dump(out, sys.stdout, ensure_ascii=False, indent=2)
        print()
    if args.out:
        Path(args.out).write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"[+] wrote {args.out}", file=sys.stderr)

    return 0

def main():
    ap = argparse.ArgumentParser(description="RentRiga scraper for ss.lv (prototype)")
    src = ap.add_mutually_exclusive_group(required=True)
    src.add_argument("--live", action="store_true",
                     help="Fetch live from ss.lv (review robots.txt and ToS first)")
    src.add_argument("--from-file", help="Parse a saved index HTML file (offline test)")

    ap.add_argument("--pages", type=int, default=1, help="Number of index pages to fetch (default 1)")
    ap.add_argument("--limit", type=int, default=10, help="Max listings to extract (default 10, hard cap 200)")
    ap.add_argument("--delay", type=float, default=DEFAULT_DELAY_SECONDS,
                    help=f"Seconds between requests (default {DEFAULT_DELAY_SECONDS})")
    ap.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT, help=f"HTTP timeout seconds (default {DEFAULT_TIMEOUT})")
    ap.add_argument("--out", help="Write JSON to this path")
    ap.add_argument("--dry-run", action="store_true",
                    help="Print result to stdout but don't promise any persistence")
    args = ap.parse_args()
    sys.exit(run(args))

if __name__ == "__main__":
    main()
