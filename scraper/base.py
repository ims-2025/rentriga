"""
RentRiga scraper framework — shared base classes and utilities.

Every per-source adapter inherits from `SourceAdapter` and only implements:
  - DOMAIN, START_URLS  (class-level config)
  - parse_index(html) -> Iterator[dict]   (extract raw listing rows)
  - (optional) parse_detail(html) -> dict (enrich with detail-page facts)
"""
from __future__ import annotations

import datetime as dt
import hashlib
import re
import sys
import time
import urllib.parse
import urllib.request
import urllib.robotparser
from dataclasses import dataclass, asdict, field
from typing import Iterator, Optional

# ---------- Canonical lists --------------------------------------------------

# Must match RR_DISTRICTS in assets/js/data.js
RR_DISTRICTS = {
    "Centrs","Vecrīga","Āgenskalns","Mežaparks","Teika","Purvciems","Imanta",
    "Ziepniekkalns","Jugla","Daugavgrīva","Sarkandaugava","Bolderāja","Pļavnieki",
    "Ķengarags","Iļģuciems","Zolitūde","Skanste","Andrejsala","Brasa",
    "Čiekurkalns","Berģi","Vecmīlgrāvis"
}

# Normalization map — extend as new portals expose new spellings.
DISTRICT_ALIASES = {
    "centre": "Centrs", "centrs": "Centrs", "centre, kluss centrs": "Centrs",
    "city centre": "Centrs", "kluss centrs": "Centrs", "klusais centrs": "Centrs",
    "vecriga": "Vecrīga", "vecrīga": "Vecrīga", "old riga": "Vecrīga", "old town": "Vecrīga",
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

USER_AGENT = "RentRigaBot/0.2 (+https://rentriga.com/about; contact: hello@rentriga.com)"
DEFAULT_DELAY_SECONDS = 3.0
DEFAULT_TIMEOUT       = 20
MAX_LISTINGS_HARD_CAP = 800  # global per-run cap across all adapters

# ---------- Listing schema ----------------------------------------------------

@dataclass
class Listing:
    """Canonical Listing schema — mirrors the shape used by assets/js/data.js."""
    id: str
    source_id: str
    source_domain: str
    source_url: str
    type: str                            # apartment | house | commercial | short_term
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
    sub_type: Optional[str] = None
    first_seen: str = field(default_factory=lambda: dt.datetime.utcnow().isoformat(timespec="seconds") + "Z")
    last_seen:  str = field(default_factory=lambda: dt.datetime.utcnow().isoformat(timespec="seconds") + "Z")
    dedup_hash: str = ""

# ---------- Shared parsing utilities -----------------------------------------

def parse_price(s):
    """Parse a price string into (value, unit). Handles € / EUR, prefix or suffix,
    European thousands separators ("1.100" → 1100), and per-month / per-night / per-m²."""
    if not s:
        return None, "per_month"
    s = s.strip()
    m = re.search(r"(?:€|EUR)\s*([\d\s.,]+)|([\d\s.,]+)\s*(?:€|EUR)", s)
    val = None
    if m:
        raw = (m.group(1) or m.group(2) or "").strip()
        raw = re.sub(r"\s+", "", raw).replace(",", ".")
        if re.fullmatch(r"\d{1,3}\.\d{3}", raw):
            raw = raw.replace(".", "")
        try:
            val = float(raw)
        except ValueError:
            val = None
    unit = "per_month"
    low = s.lower()
    if "/nakt" in low or "/night" in low or "diena" in low:
        unit = "per_night"
    elif "/m²" in s or "/m2" in low:
        unit = "per_m2"
    return val, unit

def normalize_district(s):
    if not s:
        return ""
    key = s.strip().lower()
    if key in DISTRICT_ALIASES:
        return DISTRICT_ALIASES[key]
    title = s.strip()
    if title in RR_DISTRICTS:
        return title
    return DISTRICT_ALIASES.get(title.lower(), title)

def dedup_hash(street, area, rooms):
    """Local (within-source) dedup hash. Cross-source dedup uses fingerprint()."""
    key = f"{(street or '').strip().lower()}|{round(area or 0)}|{rooms or 0}"
    return hashlib.sha1(key.encode()).hexdigest()[:16]

def fingerprint(listing):
    """Cross-source dedup hash. Same property listed on multiple portals should hash
    to the same value as long as address + size + rooms roughly match."""
    street = re.sub(r"[^a-zA-Z0-9āčēģīķļņšūžĀČĒĢĪĶĻŅŠŪŽ\s]", "", (listing.street or "").lower())
    street = re.sub(r"\s+", " ", street).strip()
    area_band = round((listing.area or 0) / 5) * 5  # 5 m² bands
    key = f"{street}|{area_band}|{listing.rooms or 0}|{listing.type}"
    return hashlib.sha1(key.encode()).hexdigest()[:16]

# ---------- Polite HTTP fetcher ----------------------------------------------

class PoliteFetcher:
    """Obeys robots.txt and rate-limits all calls."""

    def __init__(self, user_agent=USER_AGENT, delay=DEFAULT_DELAY_SECONDS, timeout=DEFAULT_TIMEOUT):
        self.user_agent = user_agent
        self.delay = delay
        self.timeout = timeout
        self._last_call = 0.0
        self._robots = {}   # host -> RobotFileParser

    def _robots_for(self, url):
        host = urllib.parse.urlsplit(url).netloc
        if host not in self._robots:
            rp = urllib.robotparser.RobotFileParser()
            rp.set_url(f"https://{host}/robots.txt")
            try:
                rp.read()
                self._robots[host] = rp
                print(f"[robots] loaded https://{host}/robots.txt", file=sys.stderr)
            except Exception as e:
                print(f"[robots] WARNING could not load https://{host}/robots.txt: {e}", file=sys.stderr)
                self._robots[host] = None
        return self._robots[host]

    def allowed(self, url):
        rp = self._robots_for(url)
        if rp is None:
            return False  # fail closed if we can't read robots.txt
        return rp.can_fetch(self.user_agent, url)

    def get(self, url):
        if not self.allowed(url):
            raise PermissionError(f"robots.txt disallows {url}")
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

# ---------- Base adapter -----------------------------------------------------

class SourceAdapter:
    """Per-source scraper. Subclass and set the class-level fields below."""

    DOMAIN: str = ""                 # e.g. "ss.lv"
    START_URLS: dict = {}            # {"apartment": "https://...", "house": "...", ...}

    def __init__(self, fetcher=None):
        self.fetcher = fetcher or PoliteFetcher()

    # ---- subclasses MUST implement ----
    def parse_index(self, html, listing_type):
        """Yield raw listing dicts from a search/index page."""
        raise NotImplementedError

    # ---- shared pipeline ----
    def fetch_index(self, url):
        return self.fetcher.get(url)

    def run(self, types=None, limit_per_type=20):
        """Fetch each START_URLS[type] and yield Listing objects."""
        types = types or list(self.START_URLS.keys())
        for t in types:
            url = self.START_URLS.get(t)
            if not url:
                continue
            print(f"[{self.DOMAIN}] {t} -> {url}", file=sys.stderr)
            try:
                html = self.fetch_index(url)
            except PermissionError as e:
                print(f"[{self.DOMAIN}] {e}", file=sys.stderr); continue
            except Exception as e:
                print(f"[{self.DOMAIN}] ERROR {e}", file=sys.stderr); continue
            count = 0
            for raw in self.parse_index(html, t):
                listing = self.normalize(raw, t)
                if listing is None:
                    continue
                yield listing
                count += 1
                if count >= limit_per_type:
                    break

    # ---- helpers subclasses can override ----
    def normalize(self, raw, listing_type):
        if not raw.get("title") or raw.get("price") is None:
            return None
        district = normalize_district(raw.get("district_raw", ""))
        if not district:
            district = "Unknown"
        sid = raw["source_id"]
        return Listing(
            id=f"{self.DOMAIN.replace('.','-')}-{sid}",
            source_id=sid,
            source_domain=self.DOMAIN,
            source_url=raw["source_url"],
            type=listing_type,
            title=raw["title"][:200],
            district=district,
            street=raw.get("street", ""),
            price=raw["price"],
            price_unit=raw.get("price_unit", "per_month"),
            currency=raw.get("currency", "EUR"),
            rooms=raw.get("rooms"),
            area=raw.get("area"),
            floor=raw.get("floor") or None,
            year=raw.get("year"),
            image=raw.get("image"),
            sub_type=raw.get("sub_type"),
            description=raw.get("description", ""),
            amenities=raw.get("amenities", []),
            dedup_hash=dedup_hash(raw.get("street"), raw.get("area"), raw.get("rooms")),
        )

# ---------- HTML helpers (lazy import bs4) -----------------------------------

def soup(html):
    """Return a BeautifulSoup tree. Lazy-imported so the file can be examined
    without bs4 installed."""
    from bs4 import BeautifulSoup
    return BeautifulSoup(html, "html.parser")

def txt(node):
    if node is None:
        return ""
    return re.sub(r"\s+", " ", node.get_text(" ", strip=True)).strip()
