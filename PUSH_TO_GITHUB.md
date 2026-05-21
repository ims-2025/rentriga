# Push RentRiga to GitHub

Open **Terminal** on your Mac, paste the block below, and press enter.
It'll take about 10 seconds.

```bash
cd ~/Documents/Claude/Projects/RentRiga
git init -b main
git config user.email "hello@rentriga.com"
git config user.name "RentRiga"
git add -A
git commit -m "Initial commit — RentRiga static demo, scraper prototype, and strategy docs"
git remote add origin https://github.com/ims-2025/rentriga.git
git push -u origin main
```

### What happens on the last line

`git push` will prompt you to authenticate to GitHub. Two ways:

1. **macOS Keychain (easiest)** — if you've ever pushed to a GitHub repo
   from this Mac, it'll just work. If you haven't, install GitHub CLI
   (`brew install gh`) then run `gh auth login` once and re-run the push.
2. **Personal access token** — generate one at
   https://github.com/settings/tokens (classic, scope: `repo`) and paste
   it as the password when git prompts.

### After it lands

Refresh your repo page at https://github.com/ims-2025/rentriga — you should
see all the files appear. From there:

- Go to **Settings → Pages** if you want a one-click public preview at
  `https://ims-2025.github.io/rentriga/` (free).
- Or follow `DEPLOY.md` to deploy to Netlify / Vercel / Cloudflare with a
  proper `rentriga.com` domain.

### If you'd rather use GitHub Desktop

1. Open GitHub Desktop → **File → Add Local Repository**.
2. Choose `~/Documents/Claude/Projects/RentRiga`.
3. Desktop will detect it isn't a git repo and offer to init one — say yes.
4. Write a commit message ("Initial commit") and click **Commit to main**.
5. Click **Publish repository** at the top, untick "Keep this code private"
   only if you want it public, and pick `ims-2025/rentriga` as the
   destination.
