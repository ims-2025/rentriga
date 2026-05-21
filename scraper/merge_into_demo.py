#!/usr/bin/env python3
"""
Merge scraper output (JSON) into the demo's assets/js/data.js so the static
demo page renders real, freshly-scraped listings alongside the sample dataset.

This is for the demo phase only. In production, listings are persisted in
PostgreSQL and served via API — the static data.js no longer plays a role.

Usage:
    python merge_into_demo.py scraped.json
    python merge_into_demo.py scraped.json --replace   # wipe sample listings first
"""
import argparse, json, re, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA_JS = ROOT / "assets" / "js" / "data.js"

PLACEHOLDER_IMG = "https://images.unsplash.com/photo-1554995207-c18c203602cb?w=1200&q=70&auto=format&fit=crop"

def to_demo_shape(l: dict) -> dict:
    """Map scraper output to the field names the demo's data.js uses."""
    return {
        "id": l["id"],
        "type": l["type"],
        "title": l["title"],
        "district": l.get("district") or "Unknown",
        "street": l.get("street", ""),
        "price": l.get("price") or 0,
        "currency": l.get("currency", "EUR"),
        "priceUnit": l.get("price_unit") if l.get("price_unit") != "per_month" else None,
        "rooms": l.get("rooms"),
        "area": l.get("area"),
        "floor": l.get("floor"),
        "year": l.get("year"),
        "img": l.get("image") or PLACEHOLDER_IMG,
        "gallery": [l.get("image") or PLACEHOLDER_IMG],
        "source": l.get("source_domain", "ss.lv"),
        "sourceUrl": l.get("source_url", ""),
        "verified": False,
        "isNew": True,
        "amenities": l.get("amenities", []),
        "desc": l.get("description") or l.get("title","")
    }

def render_js_object(o: dict) -> str:
    """Pretty-print a dict as a JS object literal in the data.js style."""
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
            inner = ",".join(json.dumps(x, ensure_ascii=False) for x in v)
            parts.append(f"{k}:[{inner}]")
    return "{" + ", ".join(parts) + "}"

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("input", help="JSON file produced by ss_lv.py")
    ap.add_argument("--replace", action="store_true",
                    help="Wipe the existing sample listings before merging")
    args = ap.parse_args()

    if not DATA_JS.exists():
        print(f"[!] {DATA_JS} not found", file=sys.stderr); sys.exit(1)

    payload = json.loads(Path(args.input).read_text(encoding="utf-8"))
    new_listings = [to_demo_shape(l) for l in payload.get("listings", [])]
    print(f"[+] {len(new_listings)} listings to merge", file=sys.stderr)

    js_objs = ",\n  ".join(render_js_object(o) for o in new_listings)

    text = DATA_JS.read_text(encoding="utf-8")

    if args.replace:
        # Replace the RR_LISTINGS array entirely
        new_block = f"window.RR_LISTINGS = [\n  {js_objs}\n];"
        text = re.sub(
            r"window\.RR_LISTINGS\s*=\s*\[[\s\S]*?\];\s*",
            new_block + "\n\n",
            text, count=1
        )
    else:
        # Insert just before the closing ']' of RR_LISTINGS
        m = re.search(r"window\.RR_LISTINGS\s*=\s*\[[\s\S]*?\];", text)
        if not m:
            print("[!] couldn't locate RR_LISTINGS array", file=sys.stderr); sys.exit(2)
        block = m.group(0)
        # last ']' before the ';'
        idx = block.rfind("]")
        merged = block[:idx].rstrip().rstrip(",") + ",\n  " + js_objs + "\n" + block[idx:]
        text = text[:m.start()] + merged + text[m.end():]

    DATA_JS.write_text(text, encoding="utf-8")
    print(f"[+] wrote {DATA_JS.relative_to(ROOT)}", file=sys.stderr)

if __name__ == "__main__":
    main()
