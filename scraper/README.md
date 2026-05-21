# RentRiga scrapers

A modular Python framework that pulls rental listings from source portals
and normalizes them into RentRiga's listing schema. Runs free on GitHub
Actions every 6 hours and commits updated `data.js` back to the repo;
Vercel auto-redeploys.

## Architecture

```
scraper/
├── base.py             ← Framework: SourceAdapter base class, PoliteFetcher,
│                          shared parsers (parse_price, normalize_district,
│                          dedup_hash, fingerprint), canonical district list
├── ss_lv.py            ← ss.lv adapter (apartments, houses, commercial, short-term)
├── varianti_lv.py      ← varianti.lv adapter
├── run_all.py          ← Orchestrator: runs every adapter, dedupes across
│                          sources, writes assets/js/data.js + data/listings.json
├── merge_into_demo.py  ← Standalone tool to merge a single JSON file into data.js
├── test_fixture.html         ← ss.lv offline test fixture
├── test_fixture_varianti.html ← varianti.lv offline test fixture
├── requirements.txt    ← beautifulsoup4
└── README.md           ← (this file)
```

## How to add a new source

Each adapter is ~80 lines. Copy `varianti_lv.py` as a template, change three
things:

```python
class NewSourceLv(SourceAdapter):
    DOMAIN = "newsource.lv"                              # 1) the domain
    START_URLS = {                                       # 2) start URLs per type
        "apartment": "https://newsource.lv/rent/flats",
        "house":     "https://newsource.lv/rent/houses",
    }

    def parse_index(self, html, listing_type):           # 3) HTML -> raw dicts
        s = soup(html)
        for card in s.select(".listing"):
            ...
            yield {
                "source_id": "...", "source_url": "...",
                "title": "...", "district_raw": "...", "street": "...",
                "price": 720, "rooms": 2, "area": 58, "image": "...",
            }
```

Then register it in `run_all.py`:

```python
from new_source_lv import NewSourceLv
ADAPTERS = [VariantiLv, SsLv, NewSourceLv]
```

The orchestrator handles normalization, deduplication, persistence, and the
data.js update for free.

## Use

### Offline smoke test

```bash
cd scraper
pip install -r requirements.txt

# Single adapter against its fixture:
python ss_lv.py --from-file test_fixture.html --type apartment --dry-run

# Full pipeline against all fixtures:
python run_all.py --fixtures
```

### Polite live test

```bash
python run_all.py --live --limit 10
```

Defaults are conservative: 3-second delay between requests, robots.txt
respected, 500-listing hard cap, 20 listings per (source × type).

### Outputs

- `data/listings.json` — full audit trail of every listing scraped this run
- `assets/js/data.js` — the live demo's data, with scraped listings prepended
  to the curated sample listings (which stay as a fallback)
- `scraper/last_run.json` — per-source success/count/error summary for healthcheck

## Production safeguards

| Safeguard | How |
|---|---|
| robots.txt respect | `PoliteFetcher.allowed()` calls `RobotFileParser.can_fetch()` — fails closed if robots.txt can't load |
| Rate limiting | 3 seconds between requests by default (`--delay`) |
| Friendly identity | `User-Agent: RentRigaBot/0.2 (+https://rentriga.com/about; contact: hello@rentriga.com)` |
| Hard cap | 500 listings per run, regardless of CLI args |
| Per-source isolation | A failing source logs the error and continues with the next — other sources still update |
| Audit trail | `data/listings.json` keeps a record of every successful scrape |

## GitHub Actions

The workflow at `.github/workflows/scrape.yml` runs the orchestrator every
6 hours and commits `assets/js/data.js` if it changed. Vercel auto-deploys
on the resulting push. You can also trigger it manually:

1. Go to **Actions** tab in your GitHub repo
2. Pick **"Scrape sources and update listings"**
3. Click **Run workflow**, optionally tweak the `live` and `limit` inputs

## Before pointing this at any real portal

For each source:

1. Open `https://www.<source>/robots.txt` and confirm the path you're
   targeting is allowed.
2. Read the source's Terms of Service. Aggregation usually needs a feed
   agreement long-term; scraping is a stopgap.
3. Verify your selectors against the live HTML — sites do change, and our
   placeholder selectors in `varianti_lv.py` may need tweaking.
4. Start with `--limit 5 --dry-run` and check the JSON output before
   committing to a real run.

## Disclaimer

The legality of scraping a specific site depends on its Terms of Service,
robots.txt, and the content involved. Always seek legal counsel before
deploying scrapers to production. The architecture document
`RentRiga_Architecture_and_Strategy.docx` (Section 3) covers the EU/Latvian
posture in detail.
