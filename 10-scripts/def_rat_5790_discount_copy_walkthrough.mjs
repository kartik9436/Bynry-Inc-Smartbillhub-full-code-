// ── Trace ──────────────────────────────────────────────
// Defect:  DEF-RAT-5790 — the discount wizard's copy, cut to B14 rule 33's real
//          caps after the PO walked DIS-02 in the beta on 2026-09-19 and said
//          *"now discount - too much text on all screens"*.
//          DEF-RAT-5791 — the same screen showing STORED precision on four
//          money figures: `1.500000`, `0.000000`, `2383.000000`, and a review
//          row reading `1.500000 as typed`.
// Rules:   CLAUDE.md hard rule 2 (money 4, percentages 6, both DISPLAY 2) ·
//          hard-won law 6 (*"diff the running app against the prototype — nine
//          defects were found this way and by nothing else"*) · B14 rules 32/33
// ───────────────────────────────────────────────────────
//
// WHY THIS EXISTS AND WHAT ONLY IT CAN ANSWER.
//
// Rule 33's five caps are RATIFIED and UNENFORCED: no gate in this repo reads
// rendered output, so *how much a clerk actually reads* is a number nothing in
// the build can produce. A catalogue grep cannot produce it either — it counts
// dead keys, and it cannot tell which of five steps a string lands on.
//
// This walks the five steps of a REAL discount on the EDIT door and prints the
// visible word count of each, plus the value of every money box. Run it against
// the branch and against the tip and you have a before/after a person can read.
// Measured 2026-09-19 on a 1.5% discount stored as `1.500000`:
//
//        step 1   step 2   step 3   step 4   step 5    total
//   tip     205      312      240      213      126    1,096
//   fix      76      144       75       63       53      411
//
// ⚠ THE COUNT EXCLUDES THE PAGE HEAD ON PURPOSE. It reads
// `[data-wizard="content"]`, so the block that used to sit ABOVE the stepper —
// the sub-line and the `Save draft` paragraph, 40 words a clerk met on EVERY
// one of the five steps — is in neither number. The real reduction is larger
// than the table shows.
//
// ⚠ AND THE MONEY BOXES ARE READ AS `input.value`, NOT AS TEXT. What a box
// SHOWS and what it POSTS are different strings by design (`MoneyTextField`'s
// display-value/draft-value split, DEF-2361), and only one of them is in the
// markup. Reading the rendered text would pass on a screen that shows `1.50`
// and posts `1.50` — which is the backed-out one-line fix that rewrites a
// stored rate on every save.
//
// USAGE: build and serve the branch, then
//   BASE=http://127.0.0.1:8655 DID=<discount uuid> \
//     node 10-scripts/def_rat_5786_discount_copy_walkthrough.mjs
import { createRequire } from "node:module";
import { readdirSync, existsSync } from "node:fs";
import { join } from "node:path";

const FE = join(import.meta.dirname, "..", "07-frontend");
const require = createRequire(join(FE, "package.json"));
const { chromium } = require("playwright-core");

function resolveChromium() {
  for (const base of ["/opt/pw-browsers", "/root/.cache/ms-playwright"]) {
    if (!existsSync(base)) continue;
    for (const d of readdirSync(base)) {
      const p = join(base, d, "chrome-linux", "chrome");
      if (existsSync(p)) return p;
    }
  }
  throw new Error("no chromium found");
}

const BASE = process.env.BASE ?? "http://127.0.0.1:8655";
const TENANT = process.env.TENANT ?? "brazosbend";
const EMAIL = process.env.EMAIL ?? "dana@brazosbendutilities.com";
const PASSWORD = process.env.PASSWORD ?? "S3cure!passw0rd";
const DID = process.env.DID;
if (!DID) throw new Error("set DID to a discount uuid — the EDIT door is where stored precision shows");

const browser = await chromium.launch({ executablePath: resolveChromium() });
const page = await browser.newPage({ viewport: { width: 1440, height: 1100 } });

await page.goto(`${BASE}/${TENANT}/signin`, { waitUntil: "networkidle" });
await page.fill("#signin-email", EMAIL);
await page.fill("#signin-password", PASSWORD);
await page.click('button[type="submit"]');
await page.waitForURL((u) => !u.pathname.endsWith("/signin"), { timeout: 30000 });

await page.goto(`${BASE}/${TENANT}/plans-rates/discounts/${DID}/edit`, { waitUntil: "networkidle" });
await page.waitForSelector("#discount-code", { timeout: 30000 });

let total = 0;
for (let step = 1; step <= 5; step++) {
  const text = await page.evaluate(() => {
    const el = document.querySelector('[data-wizard="content"]') ?? document.body;
    return el.innerText;
  });
  const words = text.split(/\s+/).filter(Boolean).length;
  total += words;
  console.log(`\n${"=".repeat(72)}\nSTEP ${step} — ${words} words of visible text\n${"=".repeat(72)}\n${text}`);
  for (const id of ["discount-value", "discount-floor", "discount-budget-cap", "discount-cap-per-bill"]) {
    const v = await page.evaluate((i) => document.querySelector("#" + i)?.value ?? null, id);
    if (v !== null) console.log(`   [input #${id}] = ${JSON.stringify(v)}`);
  }
  // Step 4 holds the only required field on the edit door; an empty one stops
  // the walk at step 4 and silently prints step 4 twice as "step 5".
  if (step === 4) {
    const reason = await page.$("#discount-change-reason");
    if (reason) {
      await reason.fill("Walkthrough — measuring on-screen words");
      await page.waitForTimeout(200);
    }
  }
  if (step < 5) {
    const next = await page.$('[data-wizard="actions"] button[data-variant="primary"]');
    if (!next) { console.log("  (could not advance — a required field is empty)"); break; }
    await next.click();
    await page.waitForTimeout(700);
  }
}
console.log(`\nTOTAL visible words across the five steps: ${total}`);
console.log("(excludes the page head above the stepper — see this file's header)");
await browser.close();
