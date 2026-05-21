# Go-live checklist — RentRiga

A practical, tick-as-you-go checklist for taking RentRiga from "static demo
on a public URL" all the way to "production rental aggregator with real
listings, real users, and revenue." Items are grouped by phase; do them
roughly in order.

The numbers in brackets are realistic costs (EUR/month) for the first 12
months, assuming modest traffic. They get cheaper per visitor as you grow.

---

## Phase 1 — Get the demo on the public internet (Week 1)

Goal: `rentriga.com` resolves to the polished demo, looks alive, and is
indexed by Google.

- [ ] **Domain.** Confirm you own `rentriga.com`. Renew for at least 5 years
      (longer registrations rank better and signal seriousness). Consider
      buying `.lv` and `.eu` as defensive registrations. (~€15/year per TLD)
- [ ] **Hosting.** Pick Netlify / Vercel / Cloudflare Pages — see
      `DEPLOY.md`. (Free at this scale)
- [ ] **SSL.** Auto-issued by any of the three hosts. Verify
      `https://rentriga.com` shows a green padlock.
- [ ] **DNS.** Set A/AAAA/CNAME records as instructed by the host.
      Add `www → rentriga.com` redirect.
- [ ] **Email forwarding.** Set up `hello@`, `legal@`, `privacy@`, `dpo@`,
      `takedown@` via Cloudflare Email Routing (free) → forwards to one
      monitored mailbox.
- [ ] **Search Console + analytics.**
      - Google Search Console (verify, submit `sitemap.xml`)
      - Bing Webmaster Tools (same)
      - Yandex Webmaster (same — important for Russian audience)
      - Plausible Analytics (€9/mo) or Cloudflare Web Analytics (free)
- [ ] **Brand basics.** Logo final, social card image (1200×630) committed,
      LinkedIn page, Instagram and Facebook handles secured even if unused.

---

## Phase 2 — Legal and corporate setup (Weeks 1–3)

Goal: RentRiga is a real legal entity that can sign contracts, take
payments, employ people, and process personal data lawfully.

- [ ] **Incorporate** RentRiga SIA in Latvia (or use an existing entity).
      Use a local accountant for the filings; ~€500 one-off + ~€100/month
      for ongoing bookkeeping.
- [ ] **Business bank account** (Swedbank, SEB, or Revolut Business — the
      last is the fastest to open).
- [ ] **Latvian IT/IP lawyer review** of:
      - `terms.html`
      - `privacy.html`
      - `cookies.html`
      - `takedown.html`
      The templates ship with placeholders ("Template notice" callout at the
      top) — your lawyer fills in the company details, retention periods,
      and refines clauses for Latvian law. Budget €800–€1,500.
- [ ] **DPO appointment.** Once you process listing data at scale, Latvian
      law (DVI guidance) requires a designated DPO. The DPO can be
      external (~€150/month service).
- [ ] **GDPR record of processing activities** (ROPA). One page covering
      what data, why, where it's stored, who accesses it. Required by Art. 30.
- [ ] **Cookie consent banner.** A tiny banner that lets users accept /
      reject analytics + marketing cookies before they fire. Cheapest:
      [CookieYes](https://www.cookieyes.com/) free tier; or roll a 40-line
      vanilla-JS version yourself.
- [ ] **Trademark RentRiga.** Latvian Patent Office or EUIPO (EU-wide).
      ~€850 one-off for EU classes 35/38/42 covering portal services.

---

## Phase 3 — Production infrastructure (Weeks 2–6)

Goal: the back end exists and can store and serve real listings.

- [ ] **Database.** PostgreSQL 16. Either Neon (€0–€20/mo serverless, great
      for early days) or Hetzner Cloud + self-managed (~€8/mo for a 2 GB VM).
      Enable PostGIS.
- [ ] **Search index.** Meilisearch Cloud (€30/mo) or self-host on a
      Hetzner VM (~€8/mo). Configure with these searchable fields:
      title, description, district, street, amenities. Set price, rooms,
      area, type as filterable.
- [ ] **Object storage.** Cloudflare R2 (€0.015/GB/mo, zero egress) or
      AWS S3. For mirrored listing images.
- [ ] **CDN + image transformation.** Cloudflare Images (€5/mo for
      100k stored, fits early scale) — handles resize/format conversion.
- [ ] **Transactional email.** Postmark or Resend (€10–€20/mo). For
      enquiry forwarding, password resets, and saved-search digests.
- [ ] **Error monitoring.** Sentry free tier (5k errors/month).
- [ ] **Uptime monitoring.** Better Stack / Healthchecks.io free tier.
- [ ] **Backups.** Daily PostgreSQL dump → R2/S3, 30-day retention.

---

## Phase 4 — Scraper fleet (Weeks 4–10)

Goal: real listings are flowing into the database every hour.

- [ ] **Decide: scrape or partner.** Best path is partner with the big
      portals first. Reach out to:
      - `city24.lv` — they license data feeds to property startups
      - `mm.lv`
      - `latio.lv` and `ober-haus.lv` — agency-owned but typically open
        to syndication
      Approach: short pitch by email, offer attribution + traffic.
      If two of these say yes, your engineering cost drops by ~50%.
- [ ] **For the rest, scrape politely.** Use the prototype at
      `scraper/ss_lv.py` as the template. Per-source steps:
      - Read robots.txt; confirm the target paths are allowed.
      - Build the per-source parser, isolate selectors at the top of the
        file so they're easy to update.
      - Set rate limit ≤ 0.5 req/sec.
      - Identify with User-Agent + contact email.
      - Test for one week in `--dry-run` before persisting.
- [ ] **Persistence + dedup engine.** Per the architecture document
      §4.3 and §6. Hybrid match on `(address + area + price)` plus
      perceptual image hash.
- [ ] **Healthcheck per source.** Alert if new-listing count drops > 40%
      vs 7-day moving average. Auto-pause the source until investigated.
- [ ] **Manual review queue** for ambiguous dedup clusters in the first
      6 months. Two part-time reviewers can keep up.
- [ ] **Geocoding.** Nominatim self-hosted (free) or Google Geocoding
      (€5/1k after first 28k/mo). Snap each listing into the canonical
      district list.
- [ ] **Auto-translation.** DeepL API (€5.49/mo + €20 per 1M chars) for
      LV ↔ EN ↔ RU. Cache translations — listings don't change often.

---

## Phase 5 — Public launch (Weeks 8–12)

Goal: real users coming to the site, finding listings, and contacting
landlords through it.

- [ ] **Replace the static `data.js`** with API calls. Switch
      `assets/js/app.js` to fetch from `/api/listings?...`.
- [ ] **Move to a Next.js codebase** (recommended) — see architecture doc
      §4.2. The static demo's HTML/CSS can be ported page-for-page, but
      Next.js gives server-side rendering for SEO + faster filter
      navigation.
- [ ] **Wire up enquiry form** to Postmark/Resend so messages actually
      reach landlords.
- [ ] **Saved searches and email alerts.** Top retention feature; users
      come back when a matching listing appears.
- [ ] **Build out programmatic SEO pages.** One landing page per
      (district × type) combination — see architecture doc §7.
- [ ] **Pre-launch press list.** Email/DM Latvian tech blogs (Labs of
      Latvia, Forbes Baltic, Delfi tech). One-paragraph pitch with a
      screenshot.
- [ ] **Soft launch** to a Latvian expat Facebook group and a few Telegram
      channels. Gather feedback for 1–2 weeks before public PR push.
- [ ] **Lighthouse score ≥ 95** on Performance, Accessibility, Best
      Practices, SEO before launch.

---

## Phase 6 — Monetization (Months 4–6)

Goal: revenue covers infrastructure + one engineer.

- [ ] **Featured listings.** €19–€49 for 14 days of priority placement.
      Sell via Stripe Checkout.
- [ ] **Agency Pro accounts.** Tiered subscriptions (€49 / €149 / €299/mo)
      with branded profile and analytics. Sell direct to the top 30 Riga
      agencies — small market, 1–2 founders can close most of them.
- [ ] **Lead routing.** €3–€8 per qualified enquiry sent to a partner
      agency. Track via UTM + agency dashboard.
- [ ] **Native ads.** Moving-company / insurance / internet providers
      on the listing detail page. Sell directly — premium placement.
- [ ] **Stripe + Latvian invoicing.** Your accountant will configure
      Latvia-correct VAT (21%) and reverse-charge rules for EU B2B.

---

## Phase 7 — Growth (Month 6+)

- [ ] **Latvian/Russian SEO content engine.** 1–2 long-form pieces per
      week. Topics: neighborhood guides, cost-of-living analyses, tenant
      rights explainers, market reports.
- [ ] **Telegram + WhatsApp alerts** for saved searches (premium
      consumer feature — €4.99/mo).
- [ ] **Mobile PWA / native app.** The current site is already
      installable as a PWA — the manifest is wired up. Native iOS/Android
      can wait until traffic justifies it.
- [ ] **Partnerships** with relocation services (Workland, Helmes, Jeppesen)
      so they bundle RentRiga in their expat onboarding flow.
- [ ] **Hire your second engineer** so you can run the scraper fleet and
      the product team in parallel.

---

## Things I can do for you next session (no credentials needed)

- Build per-source scrapers for `city24.lv`, `mm.lv`, `varianti.lv`, `inch.lv`
  following the same pattern as `scraper/ss_lv.py`.
- Convert the static HTML site into a Next.js codebase with the same UI,
  ready to wire up to a real API.
- Draft the partnership outreach email to send to `city24.lv`, `latio.lv`,
  `ober-haus.lv`, and `mm.lv`.
- Build a database schema as a SQL migration file ready to run on Neon /
  Supabase / self-hosted Postgres.
- Build a Next.js API route that serves listings out of PostgreSQL +
  Meilisearch, matching the frontend's existing data shape.

Pick any of those when you're ready.

---

## Things only you can do

- Buy / verify the domain.
- Sign hosting and infrastructure accounts.
- Sign the lawyer's engagement letter.
- Open the business bank account.
- Send the partnership emails to the big portals (your founder voice
  matters more than mine).
- Sign Stripe and Postmark contracts.
- Hire the team.
