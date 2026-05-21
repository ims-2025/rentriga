# RentRiga scrapers

A small Python codebase that pulls rental listings from source portals and
normalizes them into RentRiga's listing schema. This folder contains a
**prototype** scraper for `ss.lv` to prove the end-to-end flow.

> **Read this before running anything against a live source.**

## What this prototype does

`ss_lv.py` fetches one or more index pages of Riga apartment rentals from
ss.lv, parses each row, normalizes prices/districts/area, and emits JSON
matching RentRiga's `Listing` schema.

It deliberately ships with very conservative defaults:

- Respects `robots.txt` — fails closed if the path isn't allowed.
- Identifies as `RentRigaBot/0.1 (+contact)` so the source can contact you.
- 3-second delay between requests.
- Default `--limit 10` and `--pages 1` (≈ 11 requests total).
- Hard cap of 200 listings per run no matter what CLI args say.
- Defaults to printing JSON to stdout; nothing is written unless you pass `--out`.

## Before going live

1. Open https://www.ss.lv/robots.txt and confirm the path
   `/lv/real-estate/flats/riga/` is allowed for general user-agents. If it
   isn't, stop — switch to a partnership request instead.
2. Read ss.lv's Terms of Service. The cleanest path is a written data-feed
   agreement; scraping should be a fallback.
3. Decide which fields you may persist. Phone numbers must be masked
   (see [Privacy Policy](../privacy.html)).
4. Set up a real cron schedule (every 15–30 minutes), error monitoring (Sentry),
   and a healthcheck that pages you when new-listing volume drops > 40%
   versus the 7-day moving average.

## Install

```bash
cd scraper
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Use

**Offline test (recommended first run).** Save one ss.lv listings page as
`sample.html` from your browser and run:

```bash
python ss_lv.py --from-file sample.html --dry-run
```

**Live, polite, tiny.** One page, ten listings, three-second delay, dry-run:

```bash
python ss_lv.py --live --pages 1 --limit 10 --dry-run
```

**Write to disk.**

```bash
python ss_lv.py --live --pages 1 --limit 10 --out scraped.json
```

## Output shape

```json
{
  "meta": {
    "source": "ss.lv",
    "scraped_at": "2026-05-21T08:42:31Z",
    "count": 10
  },
  "listings": [
    {
      "id": "ss-aaabbb",
      "source_id": "aaabbb",
      "source_domain": "ss.lv",
      "source_url": "https://www.ss.lv/lv/real-estate/flats/riga/.../aaabbb.html",
      "type": "apartment",
      "title": "Quiet 2-room in centre",
      "district": "Centrs",
      "street": "Brīvības iela 102",
      "price": 650,
      "price_unit": "per_month",
      "currency": "EUR",
      "rooms": 2,
      "area": 58.0,
      "floor": "3/5",
      "image": "https://i.ss.lv/.../aaabbb.jpg",
      "amenities": [],
      "dedup_hash": "a1b2c3d4e5f6"
    }
  ]
}
```

## Next steps to make this production-grade

The prototype is intentionally minimal. To turn it into the production scraper
fleet described in the architecture document, layer the following on top:

1. **Detail-page enrichment.** After parsing the index, fetch each listing's
   detail page (politely, max 1 per 3 seconds) to collect: full description,
   image gallery, floor max, year built, amenities, lat/lng from the on-page
   map.
2. **Persistence.** Upsert into PostgreSQL via SQLAlchemy. Match on `(source,
   source_id)` for the same row; cross-source dedup uses `dedup_hash` +
   perceptual image hash.
3. **Image mirroring.** Download each image once, upload to S3 / Cloudflare R2
   with attribution metadata, then store our CDN URL on the listing.
4. **Geocoding.** Run the address through Nominatim (self-hosted) or Google
   Geocoding API and snap to a district polygon (PostGIS).
5. **Translation.** Run titles and descriptions through DeepL or a self-hosted
   NLLB model to produce `_lv`, `_ru`, `_en` variants.
6. **Scheduling.** Wrap in a BullMQ or RQ job; run every 15 minutes for P0
   sources, with per-source backoff if errors spike.
7. **Healthcheck.** Compare today's new-listing count to a 7-day moving
   average. Page on >40% drop or >2x spike (likely parsing failure).
8. **Per-source adapters.** Add `city24.py`, `mm_lv.py`, `varianti.py`,
   `inch.py`, `latio.py`, `ober_haus.py` following the same pattern.

## Disclaimer

This prototype is provided as a starting point. The legality of scraping
specific sites depends on the site's Terms of Service, robots.txt, and the
content involved. Always seek legal counsel before deploying scrapers to
production.
