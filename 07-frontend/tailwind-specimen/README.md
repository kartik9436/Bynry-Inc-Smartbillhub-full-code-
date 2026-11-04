# `tailwind-specimen/` — CR-018 Phase 0 proof page

**Throwaway. Not routed, not in `src/`, not shipped.** It is the only thing that
imports `src/styles/tailwind.css` in Phase 0, and it exists to answer one
question by RENDERING rather than by reading a config (hard-won law 1):

> did all **76** tokens in `src/styles/tokens.css` cross into the Tailwind theme
> with their value intact?

## Run it

```sh
cd 07-frontend
npx vite build --config tailwind-specimen/vite.config.ts
(cd tailwind-specimen/dist-specimen && python3 -m http.server 8931 &)
node tailwind-specimen/verify.mjs http://127.0.0.1:8931/index.html /tmp/specimen.png
```

`file://` does not work — Chrome blocks the module script as cross-origin and
the page comes back empty. If Playwright's own browser is not downloaded, point
at any Chromium: `CR018_CHROME=/opt/pw-browsers/chromium-1194/chrome-linux/chrome`.

## What it asserts, and why it is three checks and not one

| | claim | who depends on it |
|---|---|---|
| **utilities** 76/76 | `bg-accent-700`, `text-h2`, `p-4` … each paints exactly what `tokens.css` says | Phase 3 markup |
| **variables** 76/76 | the custom property `@theme` re-emits into `:root` still equals `tokens.css` | the **1,788** existing `var(--token)` sites, which must survive `tokens.css` being deleted |
| **neutralised** 17/17 | `bg-red-500`, `text-lg`, `text-base`, `text-xs`, `font-sans`, `shadow-2xl` are inert; all nine `rounded-*` keys are 0px; `rounded-full` is **not** | B14 rules 5 and 20, by construction |

Both sides of every comparison come out of `getComputedStyle` in a real browser.
The `tokens.css` side is parsed from that file's **source text** — the sheet is
deliberately never imported here, because if both sheets declared `:root` the
comparison would be a variable against itself.

## Proved RED before trusted green (hard-won law 7)

Four values were sabotaged in `tailwind.css` and the page rebuilt:

| sabotage | caught by |
|---|---|
| `--color-accent-700` `#ae1800` → `#ae1801` | utilities **and** variables |
| `--radius-md` `0px` → `4px` | utilities, variables **and** neutralised |
| `--shadow-md` blur `3px` → `4px` | utilities **and** variables |
| `--space-4` `16px` → `17px` | **variables only** |

That last row is why there are two token checks. `p-4` comes from Tailwind's
`--spacing` multiplier, not from our key, so the utility check walked straight
past a token that had drifted by a pixel. **The variables section was written
because breaking the guard exposed the hole — it was not designed in.**

Two more findings came out of building it, both recorded in the source because
each will bite a Phase 3 lane:

* **55 of 76 first reported `rgba(0, 0, 0, 0)`** — the classes had been built as
  `` `bg-${name}` `` and Tailwind generates only what its scanner can SEE in
  source. The theme was correct the whole time. Every class name here is now
  written out in full; any interpolated class name in Phase 3 is this bug.
* **Lightning CSS resolves a static `color-mix()` at build time**, so the theme
  side spells `--color-divider` as `rgba(32, 30, 29, .4)` and the browser spells
  the literal side `color(srgb 0.12549 … / 0.4)`. Same colour, two spellings,
  four false FAILs — so colours are canonicalised to 8-bit RGBA before comparing
  rather than being accepted as different.

## What it costs

| | |
|---|---|
| app bundle with Tailwind wired and nothing importing the theme | **0 bytes** — built twice at one commit in an isolated worktree with nothing changed but the plugin line, the production CSS is byte-identical: `index-DSjCOfdd.css`, 125.25 kB, `sha256 6ab0e6ad…85f123ed` |
| the theme's own floor, compiled with zero utilities used | **4.22 kB raw / 1.50 kB gzip** (Preflight + the `:root` block) |
| this proof page, ~110 utilities exercised | 16.32 kB raw / 3.70 kB gzip |

The 4.22 kB is the baseline Phase 3 is judged against. The 0 bytes is what says
the build the PO is verifying in a browser has not moved.

⚠ **Re-verify it by toggling the plugin at ONE commit, never by comparing against a
hash recorded on another day.** The first attempt did that, cited 125.21 kB /
`06c80632…`, and the number moved — because another lane edited `SignupWizard.css`,
which has nothing to do with Tailwind. In a shared tree a bundle hash is a fact
about the whole tree, not about one change.

## Deleting it

Phase 3's last commit. Its job ends when `tokens.css` does.
