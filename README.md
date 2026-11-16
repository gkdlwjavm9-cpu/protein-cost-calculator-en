# Protein Cost Per Gram Calculator

A single-file web tool (`index.html`) that answers one question: **which groceries are actually cheap protein?**

Enter a price, a package weight, the protein per 100 g and the calories, and it ranks everything you entered by:

- price per 100 g
- **cost per gram of protein** (the headline number — lower means cheaper protein)
- protein share of the food's calories
- the cost, weight and calories needed to hit your daily protein target with that food

It ships with a set of starter rows (chicken breast, eggs, milk, tofu, Greek yogurt, whey, etc.) so you never start from an empty screen.

## Notes

- No libraries, no CDN, no API keys — works offline and can be hosted anywhere as a static file.
- Values are stored in your browser's `localStorage` only; nothing is sent to a server.
- One-click copy of the results table (paste straight into a spreadsheet).
- Dark mode and a mobile layout.

## Run it locally

Open `index.html` in a browser, or serve the folder:

```bash
python3 -m http.server 8000
```

## Deploy

GitHub Pages: Settings → Pages → Deploy from a branch → `main` / `(root)`.
The site is published at `https://<user>.github.io/protein-cost-calculator-en/`.

Korean edition: [protein-cost-calculator](https://github.com/gkdlwjavm9-cpu/protein-cost-calculator)

## Checks and maintenance

```bash
pip install quickjs                       # once
python3 tests/test_tool.py                # 79 math checks: units, per-serving labels, ranking, summary, formatting
python3 tests/test_ui.py                  # 61 UI checks: presets, sorting, add/remove, target, unit toggle, storage, CTA
bash deploy.sh                            # (re)deploy to GitHub Pages and wait for HTTP 200
```

- `GUMROAD_URL` at the top of the inline script: set it to the live product URL to make the CTA a checkout link, or to `""` to show a "coming soon" toast instead.
- Two `.adslot` placeholders hold the ad space — paste the AdSense unit inside them after approval.
- `PRESETS` is the starter list: `{name, price, size, unit, protein, kcal}`, USD with protein and kcal per 100 g.
