# RentRiga

> Riga's premium rental aggregator. Every listing, one place.

RentRiga aggregates rental listings from 30+ Latvian property portals
(`ss.lv`, `city24.lv`, `mm.lv`, `varianti.lv`, `inch.lv`, `latio.lv`,
`ober-haus.lv` and more) into a single fast, modern, multilingual search
experience covering apartments, houses, commercial space and short-term
stays in Riga.

This repository contains the **launch-ready static demo** plus the
**architecture, scraper prototype, and go-live tooling** needed to take
the project from concept to live product.

---

## What's in this repo

```
RentRiga/
├── index.html              ← Homepage (hero, search, featured listings)
├── listings.html           ← Browse / search with filters, sort, map view
├── listing.html            ← Listing detail page with gallery + contact form
├── 404.html
├── terms.html              ← Terms of Service (template — needs lawyer review)
├── privacy.html            ← Privacy Policy (GDPR-aware)
├── cookies.html            ← Cookie Policy
├── takedown.html           ← Takedown / removal request form
├── manifest.json           ← PWA manifest
├── robots.txt
├── sitemap.xml             ← Auto-generated, multi-language
│
├── assets/
│   ├── css/styles.css      ← Single stylesheet, mobile-first
│   ├── js/data.js          ← Sample listings (replaced by API in production)
│   ├── js/i18n.js          ← EN / LV / RU translations (~125 keys × 3)
│   ├── js/app.js           ← All page logic: search, filters, render
│   └── icons/              ← SVG icons used by the manifest
│
├── scraper/
│   ├── ss_lv.py            ← Polite, robots.txt-aware ss.lv scraper prototype
│   ├── merge_into_demo.py  ← Feeds scraper output into the demo's data.js
│   ├── test_fixture.html   ← Offline test fixture for parser verification
│   ├── requirements.txt
│   └── README.md
│
├── tools/
│   └── build_sitemap.py    ← Regenerates sitemap.xml from listings
│
├── netlify.toml            ← Netlify deployment config
├── vercel.json             ← Vercel deployment config
├── _headers / _redirects   ← Cloudflare Pages / Netlify shared configs
│
├── DEPLOY.md               ← Step-by-step: get the demo live in ~15 min
├── GO_LIVE_CHECKLIST.md    ← Every external piece needed for production
└── RentRiga_Architecture_and_Strategy.docx  ← Full strategy document
```

---

## Quick start

### View locally

```bash
python3 -m http.server 8000
# then open http://localhost:8000
```

### Deploy

See `DEPLOY.md` for one-click instructions for **Netlify**, **Vercel**, or
**Cloudflare Pages**. All three configs are already in this repo — no
build step needed.

### Run the scraper prototype

```bash
cd scraper
pip install -r requirements.txt
python ss_lv.py --from-file test_fixture.html --dry-run     # offline test
python ss_lv.py --live --pages 1 --limit 10 --dry-run       # tiny live run (review ss.lv ToS first)
```

---

## Features

- **One search across 30+ portals.** Aggregation, dedup, fresh hourly.
- **Modern UI.** Hero search, category cards, filter sidebar, grid / list /
  map views, smart pagination, listing detail with gallery, sticky
  contact card, similar-listings rail.
- **Multilingual.** Full UI in **English, Latvian, Russian** — switch
  persists across pages.
- **SEO-ready.** JSON-LD on every listing, hreflang pairs, multi-language
  sitemap, semantic HTML, mobile-first responsive layout.
- **GDPR-aware.** Privacy policy, cookie consent strategy, takedown form,
  90-day data retention plan documented.
- **Polite scraping.** robots.txt-respecting fetcher, rate-limited,
  identified User-Agent, hard caps, dry-run defaults.

---

## Roadmap

The full phased roadmap lives in `GO_LIVE_CHECKLIST.md` and the strategy
document. In summary:

1. **Week 1** — Deploy static demo to `rentriga.com`.
2. **Weeks 1–3** — Incorporate SIA, lawyer review of legal pages,
   business bank.
3. **Weeks 2–6** — Production infrastructure: PostgreSQL + PostGIS,
   Meilisearch, R2/S3, Postmark, monitoring.
4. **Weeks 4–10** — Scraper fleet: ss.lv + 4 more P0 portals, dedup,
   geocoding, translation.
5. **Weeks 8–12** — Next.js production frontend, API, public launch.
6. **Months 4–6** — Monetization: featured listings, agency Pro, lead
   routing.

---

## License

All rights reserved © 2026 RentRiga.com.

This codebase is private to RentRiga.com. The static demo and strategy
documents may be shared with prospective developers, investors, and
partners under NDA.

---

## Contact

- General: hello@rentriga.com
- Legal: legal@rentriga.com
- Privacy / GDPR: privacy@rentriga.com
- Takedown requests: takedown@rentriga.com
