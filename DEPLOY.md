# Deploy RentRiga — step-by-step

The current `RentRiga/` folder is a complete static site. You can put it on the
public internet at `https://rentriga.com` in roughly 15 minutes, using one of
three free hosting services. Pick whichever you're most comfortable with.

| Host | Free tier | Setup time | Custom domain |
|---|---|---|---|
| **Netlify** (recommended for first launch) | 100 GB bandwidth/month | ~10 min | Yes |
| **Vercel** | 100 GB bandwidth/month | ~10 min | Yes |
| **Cloudflare Pages** | Unlimited bandwidth | ~15 min | Yes |

All three already have config files in this folder (`netlify.toml`,
`vercel.json`, `_headers`/`_redirects`) — no edits needed.

---

## Option A — Netlify (easiest)

1. Go to **https://app.netlify.com/drop**.
2. Drag the entire `RentRiga/` folder into the drop zone.
3. Netlify gives you a temporary URL like `frosty-elf-12345.netlify.app`.
   Open it — the site is live.
4. To connect `rentriga.com`:
   - In Netlify: **Site settings → Domain management → Add custom domain → `rentriga.com`**.
   - At your domain registrar, change the DNS records:
     - **A** `@` → `75.2.60.5`
     - **CNAME** `www` → `<your-site>.netlify.app`
     - (Or use Netlify DNS for a one-click setup.)
   - SSL is automatic and free, issued within ~5 minutes.

That's it.

---

## Option B — Vercel

1. Install the Vercel CLI: `npm i -g vercel`.
2. From inside the `RentRiga/` folder run `vercel`. It will auto-detect a
   static site, ask you a couple of questions, and give you a URL.
3. In the Vercel dashboard: **Settings → Domains → Add `rentriga.com`**.
4. Add the DNS records Vercel shows you (an A record to `76.76.21.21` and a
   CNAME for `www`).
5. SSL auto-provisions.

---

## Option C — Cloudflare Pages

1. Push the `RentRiga/` folder to a GitHub repository.
2. In Cloudflare dashboard: **Workers & Pages → Create application →
   Pages → Connect to Git** → pick the repo.
3. Build settings: **Framework: None, Build command: (empty),
   Build output: `/`**.
4. Deploy.
5. To add the custom domain: **Custom domains → Set up a custom domain →
   `rentriga.com`**. If your domain is already on Cloudflare, this is a
   single click; if not, follow the DNS steps shown.

---

## After deployment — same on all three

1. **Update absolute URLs in `index.html`.** The Open Graph and JSON-LD
   blocks reference `https://rentriga.com/`. They're already correct — but
   if you launch under a different domain first, replace those URLs
   accordingly.
2. **Regenerate `sitemap.xml`.** Anytime the listings dataset changes,
   re-run:
   ```bash
   python3 tools/build_sitemap.py --base https://rentriga.com
   ```
3. **Submit the sitemap to search engines.**
   - Google: https://search.google.com/search-console (add
     `https://rentriga.com`, verify via DNS TXT record, then Sitemaps →
     `https://rentriga.com/sitemap.xml`).
   - Bing: https://www.bing.com/webmasters.
   - Yandex: https://webmaster.yandex.com (important for the Russian-speaking
     audience).
4. **Verify the legal pages** open: `/terms`, `/privacy`, `/cookies`,
   `/takedown` (clean URLs work via the redirects config).
5. **Set up an inbox** for `hello@rentriga.com`, `legal@rentriga.com`,
   `privacy@rentriga.com`, `dpo@rentriga.com`, `takedown@rentriga.com`.
   Cheapest is Cloudflare Email Routing (free) forwarding to a Gmail.
6. **Run a Lighthouse audit** in Chrome DevTools. Target: 95+ on every
   category. The site is built to hit those numbers already.

---

## What you should NOT deploy yet

- **The scraper.** `scraper/ss_lv.py` is a prototype. Deploying it to
  production needs everything in `GO_LIVE_CHECKLIST.md`: a database, a
  cron, healthchecks, partnerships or legal sign-off with the sources, and
  GDPR registration.
- **The contact form.** Right now the enquiry form on listing pages just
  shows a thank-you message — no email goes anywhere. To wire it up:
  - On Netlify: rename the form to `<form name="enquiry" netlify>` and add
    `<input type="hidden" name="form-name" value="enquiry">`. Netlify will
    capture submissions for free.
  - Or sign up for [Formspree](https://formspree.io/) or
    [Resend](https://resend.com/) — both have free tiers — and POST to
    their endpoint.

---

## Quick sanity test before going live

From the `RentRiga/` folder, serve locally:

```bash
python3 -m http.server 8000
```

Then open `http://localhost:8000` and click through:
- Homepage renders, language switcher works (EN / LV / RU)
- Search box on homepage navigates to listings page with filters applied
- Listings page: filters, sort, grid/list/map toggle all work
- Click any listing → detail page loads with gallery
- Footer links to Terms / Privacy / Cookies / Takedown all work
- Visit an invalid URL → 404 page shows

If all of that works locally, deployment will work.
