#!/usr/bin/env python3
"""
RentRiga — scraper orchestrator.

Runs every registered SourceAdapter, dedupes results across sources, and writes
`assets/js/data.js` with the merged listings (preserving the curated sample
listings as a fallback so the site never goes empty if all scrapers fail).

Usage:
    # Offline test using the bundled HTML fixtures:
    python run_all.py --fixtures

    # Live run, defaults: 20 listings per (source × type), 6h schedule
    python run_all.py --live

    # Live with custom limits
    python run_all.py --live --limit 30

Outputs:
    - data/listings.json                 (raw scrape output, audit trail)
    - assets/js/data.js                  (updated RR_LISTINGS array)
    - scraper/last_run.json              (run summary + counts per source)
"""
from __future__ import annotations

import argparse, datetime as dt, json, re, sys
from dataclasses import asdict
from pathlib import Path

from base import PoliteFetcher, fingerprint, MAX_LISTINGS_HARD_CAP
from ss_lv import SsLv
from varianti_lv import VariantiLv

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
LISTINGS_JSON = DATA_DIR / "listings.json"
DATA_JS = ROOT / "assets" / "js" / "data.js"
LAST_RUN = Path(__file__).resolve().parent / "last_run.json"

# Register adapters here. Order matters for the "canonical" pick during dedup:
# the FIRST source that has a listing wins, so list the most trustworthy ones first.
ADAPTERS = [VariantiLv, SsLv]

# What categories to scrape per source. Some sources don't have all four.
TYPES_PER_SOURCE = {
    "ss.lv":       ["apartment", "house", "commercial", "short_term"],
    "varianti.lv": ["apartment", "house", "commercial"],
}

# Local fixture paths for --fixtures mode (offline smoke test)
FIXTURES = {
    "ss.lv":       Path(__file__).resolve().parent / "test_fixture.html",
    "varianti.lv": Path(__file__).resolve().parent / "test_fixture_varianti.html",
}


def run_live(limit_per_type=20):
    fetcher = PoliteFetcher()
    all_listings = []
    summary = {"sources": {}, "started_at": _now(), "mode": "live"}

    for AdapterCls in ADAPTERS:
        adapter = AdapterCls(fetcher)
        types = TYPES_PER_SOURCE.get(adapter.DOMAIN, ["apartment"])
        before = len(all_listings)
        try:
            for l in adapter.run(types=types, limit_per_type=limit_per_type):
                all_listings.append(l)
                if len(all_listings) >= MAX_LISTINGS_HARD_CAP:
                    print(f"[orchestrator] hit hard cap of {MAX_LISTINGS_HARD_CAP}", file=sys.stderr)
                    break
        except Exception as e:
            print(f"[orchestrator] {adapter.DOMAIN} ERROR: {e}", file=sys.stderr)
        summary["sources"][adapter.DOMAIN] = {
            "status": "ok",
            "count": len(all_listings) - before,
        }
        if len(all_listings) >= MAX_LISTINGS_HARD_CAP:
            break

    summary["finished_at"] = _now()
    return all_listings, summary


def run_fixtures():
    """Offline: run each adapter against its bundled HTML fixture."""
    all_listings = []
    summary = {"sources": {}, "started_at": _now(), "mode": "fixtures"}
    for AdapterCls in ADAPTERS:
        adapter = AdapterCls()
        fixture = FIXTURES.get(adapter.DOMAIN)
        if not fixture or not fixture.exists():
            print(f"[orchestrator] no fixture for {adapter.DOMAIN}, skipping", file=sys.stderr)
            continue
        html = fixture.read_text(encoding="utf-8")
        types = TYPES_PER_SOURCE.get(adapter.DOMAIN, ["apartment"])
        before = len(all_listings)
        for t in types:
            for raw in adapter.parse_index(html, t):
                l = adapter.normalize(raw, t)
                if l: all_listings.append(l)
            # Fixtures only cover apartments; don't repeat for every type
            break
        summary["sources"][adapter.DOMAIN] = {
            "status": "ok",
            "count": len(all_listings) - before,
        }
    summary["finished_at"] = _now()
    return all_listings, summary


def dedupe(listings):
    """Drop cross-source duplicates. Keeps the first occurrence (which, given the
    ADAPTERS order, is the most trusted source)."""
    seen = {}
    out = []
    for l in listings:
        fp = fingerprint(l)
        if fp in seen:
            # Already have a canonical copy. Could merge images here later.
            continue
        seen[fp] = l
        out.append(l)
    print(f"[orchestrator] {len(listings)} listings -> {len(out)} after dedup", file=sys.stderr)
    return out


def _now():
    return dt.datetime.utcnow().isoformat(timespec="seconds") + "Z"


# ---------- writers ----------------------------------------------------------

def to_demo_shape(l):
    """Map scraper Listing dataclass to the field names assets/js/data.js uses."""
    d = asdict(l) if hasattr(l, "__dict__") else l
    return {
        "id": d["id"],
        "type": d["type"],
        "title": d["title"],
        "district": d.get("district") or "Unknown",
        "street": d.get("street", ""),
        "price": d.get("price") or 0,
        "currency": d.get("currency", "EUR"),
        "priceUnit": d.get("price_unit") if d.get("price_unit") != "per_month" else None,
        "rooms": d.get("rooms"),
        "area": d.get("area"),
        "floor": d.get("floor"),
        "year": d.get("year"),
        "img": d.get("image") or "https://images.unsplash.com/photo-1554995207-c18c203602cb?w=1200&q=70&auto=format&fit=crop",
        "gallery": [d.get("image")] if d.get("image") else [],
        "source": d.get("source_domain", ""),
        "sourceUrl": d.get("source_url", ""),
        "verified": True,
        "isNew": True,
        "amenities": d.get("amenities", []),
        "desc": d.get("description") or d.get("title", "")
    }


def render_js_object(o):
    parts = []
    for k, v in o.items():
        if v is None:
            continue
        if isinstance(v, str):
            esc = v.replace("\\", "\\\\").replace('"', '\\"')
            parts.append(f'{k}:"{esc}"')
        elif isinstance(v, bool):
            parts.append(f'{k}:{"true" if v else "false"}')
        elif isinstance(v, (int, float)):
            parts.append(f"{k}:{v}")
        elif isinstance(v, list):
            parts.append(f"{k}:[" + ",".join(json.dumps(x, ensure_ascii=False) for x in v) + "]")
    return "{" + ", ".join(parts) + "}"


SAMPLE_MARKER_START = "/* === SAMPLE LISTINGS (kept as fallback) === */"
SAMPLE_MARKER_END   = "/* === END SAMPLE LISTINGS === */"
SCRAPED_MARKER      = "/* === SCRAPED LISTINGS — auto-generated, do not edit by hand === */"


def update_data_js(scraped_listings, generated_at):
    """Rewrite RR_LISTINGS in data.js: scraped listings first, then sample fallback."""
    text = DATA_JS.read_text(encoding="utf-8")

    scraped_objs = ",\n  ".join(render_js_object(to_demo_shape(l)) for l in scraped_listings)
    scraped_block = (
        f"  {SCRAPED_MARKER}\n"
        f"  // Generated: {generated_at}\n"
        f"  // Source count: {len(scraped_listings)}\n"
        + ("  " + scraped_objs + ("," if scraped_listings else "") + "\n" if scraped_listings else "")
        + f"  {SAMPLE_MARKER_START}"
    )

    # If markers don't exist yet, wrap the existing sample listings in markers.
    if SAMPLE_MARKER_START not in text:
        text = re.sub(
            r"(window\.RR_LISTINGS\s*=\s*\[\s*)(/\*[\s\S]*?\*/\s*)?",
            lambda m: m.group(1) + scraped_block + "\n  ",
            text, count=1
        )
        # Also append the end marker just before the closing ']'.
        text = re.sub(
            r"(\];\s*/\* Quick stats)",
            f"\n  {SAMPLE_MARKER_END}\n" + r"\1",
            text, count=1
        )
    else:
        # Replace just the scraped section between SCRAPED_MARKER and SAMPLE_MARKER_START.
        pattern = (
            r"  " + re.escape(SCRAPED_MARKER) + r"[\s\S]*?  " + re.escape(SAMPLE_MARKER_START)
        )
        text = re.sub(pattern, scraped_block, text, count=1)

    # Inject/refresh the freshness timestamp.
    timestamp_line = f'window.RR_LAST_UPDATED = "{generated_at}"; // auto-generated\n'
    if "window.RR_LAST_UPDATED" in text:
        text = re.sub(r'window\.RR_LAST_UPDATED\s*=\s*"[^"]*";\s*//[^\n]*\n', timestamp_line, text)
    else:
        text = timestamp_line + text

    DATA_JS.write_text(text, encoding="utf-8")
    print(f"[orchestrator] wrote {DATA_JS.relative_to(ROOT)}", file=sys.stderr)


# ---------- main -------------------------------------------------------------

def main():
    ap = argparse.ArgumentParser()
    grp = ap.add_mutually_exclusive_group(required=True)
    grp.add_argument("--live", action="store_true", help="Run real network scrapes")
    grp.add_argument("--fixtures", action="store_true", help="Use bundled HTML fixtures (offline)")
    ap.add_argument("--limit", type=int, default=20, help="Listings per (source × type)")
    ap.add_argument("--no-write", action="store_true", help="Don't update data.js")
    args = ap.parse_args()

    DATA_DIR.mkdir(parents=True, exist_ok=True)

    if args.live:
        listings, summary = run_live(limit_per_type=args.limit)
    else:
        listings, summary = run_fixtures()

    deduped = dedupe(listings)
    summary["total_listings"] = len(deduped)

    # 1) raw audit trail
    LISTINGS_JSON.write_text(
        json.dumps({"meta": summary, "listings": [asdict(l) for l in deduped]},
                   ensure_ascii=False, indent=2),
        encoding="utf-8")
    print(f"[orchestrator] wrote {LISTINGS_JSON.relative_to(ROOT)}", file=sys.stderr)

    # 2) per-run summary (for healthchecks, dashboards)
    LAST_RUN.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    # 3) update data.js
    if not args.no_write:
        update_data_js(deduped, summary["finished_at"])

    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
