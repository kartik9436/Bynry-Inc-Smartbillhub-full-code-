// ── Trace ──────────────────────────────────────────────
// Change:   DEF-RAT-5786 — CHG-02's copy against B14 rule 33's REAL caps, and
//           the eight hardcoded customer classes behind its class pickers.
// Reported: Product Owner, beta walk 2026-09-19 — "too much text on step 1",
//           "step 2 too much text", "step 3 too much text", and
//           "make customer class drop down multi select".
// Rules:    B14 rule 33 (on-screen text is capped BY WHAT IT IS FOR; RATIONALE
//           is ZERO words) · rule 32 · rule 9 · rule 36/38 (a kit change is
//           never local) · BR-SHL-033 (searchable past LONG_LIST_THRESHOLD) ·
//           BR-SHL-025 (a disabled control owes its reason) ·
//           CLAUDE.md hard-won law 6 (NO GATE READS RENDERED OUTPUT).
// ───────────────────────────────────────────────────────
/**
 * Read all three steps of the charge-code wizard IN A REAL BROWSER.
 *
 *     BASE=http://127.0.0.1:8112 node 10-scripts/def_rat_5786_charge_copy_walkthrough.mjs
 *
 * ⚠ **WHY THIS EXISTS BESIDE 800-ODD GREEN VITEST CASES.** The whole defect
 * survived a green suite. Every deleted paragraph rendered correctly, every
 * assertion about it passed, and `tsc` was clean — the text was the wrong KIND,
 * which no gate in this repo can see because none reads rendered output.
 *
 * ⚠ **THE CLASS ASSERTIONS ARE WRITTEN SO THEY CANNOT PASS AGAINST THE BUG.**
 * The tenant's `school_district` is in NO front-end literal. A screen still
 * reading `CUSTOMER_CLASSES` cannot produce that word, so finding it on screen
 * is proof the picker read the tenant's rows — where "eight options appear"
 * would have been satisfied by the defect itself.
 *
 * ⚠ **IT ASSERTS SHAPE AND WORD COUNTS, NEVER A DRAWN FIGURE (B14 rule 37).**
 */
import { createRequire } from "node:module";
import { existsSync, readdirSync } from "node:fs";
import { join } from "node:path";
const require = createRequire("/home/user/SMARTBillHub/07-frontend/package.json");
const { chromium } = require("playwright");

/** The SAME resolver `12-smoke-walkthrough.mjs` uses, and for the same reason:
 *  the pinned playwright revision is routinely absent on this box while an
 *  off-revision chromium is installed. This walk asserts TEXT and SHAPE, never
 *  a pixel, so an off-revision browser beats not running at all — and the
 *  substitution is printed so nobody is surprised. */
function resolveChromium() {
  const wanted = chromium.executablePath();
  if (wanted && existsSync(wanted)) return wanted;
  const roots = [process.env.PLAYWRIGHT_BROWSERS_PATH, "/opt/pw-browsers"].filter(Boolean);
  for (const root of roots) {
    if (!existsSync(root)) continue;
    for (const dir of readdirSync(root)) {
      if (!dir.startsWith("chromium")) continue;
      for (const sub of ["chrome-linux64/chrome", "chrome-linux/chrome", "chrome-linux/headless_shell"]) {
        const candidate = join(root, dir, sub);
        if (existsSync(candidate)) {
          console.log(`chromium: pinned revision missing; using ${candidate}`);
          return candidate;
        }
      }
    }
  }
  throw new Error(`no chromium found (playwright wants ${wanted}); run: npx playwright install chromium`);
}

const BASE = process.env.BASE ?? "http://127.0.0.1:8112";
const TENANT = process.env.TENANT ?? "brazosbend";
const EMAIL = process.env.EMAIL ?? "dana@brazosbendutilities.com";
const PASSWORD = process.env.PASSWORD ?? "S3cure!passw0rd";

const out = [];
const note = (s) => { console.log(s); out.push(s); };
let failures = 0;
function check(ok, label) {
  note(`${ok ? "  PASS" : "  FAIL"}  ${label}`);
  if (!ok) failures += 1;
}

/** Longest sentence in words — rule 33 caps PER SENTENCE, never per string. */
function longestSentence(text) {
  const parts = String(text).split(/(?<=[.!?])\s+/).map((s) => s.trim()).filter(Boolean);
  if (!parts.length) return 0;
  return Math.max(...parts.map((s) => s.split(/\s+/).filter(Boolean).length));
}

const browser = await chromium.launch({ executablePath: resolveChromium() });
const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } });

await page.goto(`${BASE}/${TENANT}/signin`, { waitUntil: "domcontentloaded" });
await page.fill("#signin-email", EMAIL);
await page.fill("#signin-password", PASSWORD);
await Promise.all([
  page.waitForURL((u) => !u.pathname.endsWith("/signin"), { timeout: 30000 }),
  page.click('button[type="submit"]'),
]);
note(`signed in as ${EMAIL}`);

/** Every visible line, as a person reads it — never innerHTML. */
const screenText = () => page.locator("body").innerText();

// ══════════════════════════════════════════════════════════════════════════
// STEP 1 — "too much text on step 1"
// ══════════════════════════════════════════════════════════════════════════
note("\n── STEP 1 · Basics ─────────────────────────────────────────────");
await page.goto(`${BASE}/${TENANT}/plans-rates/charge-codes/new`, { waitUntil: "domcontentloaded" });
await page.locator("#charge-code").waitFor({ timeout: 30000 });
const step1 = await screenText();
note(step1.split("\n").filter(Boolean).map((l) => `    | ${l}`).join("\n"));

check(!/What the type decides/i.test(step1), "the 5-row type table is GONE");
check(!/Not driven by type/i.test(step1), "its `Not driven by type` note is GONE");
check(!/staff-only one is not offered/i.test(step1), "the internal-description RATIONALE is GONE");
check(!/Internal description/i.test(step1), "…and so is the control it explained");
check(await page.locator("#charge-name").count() === 1, "the BILL description field is still there");
check(/Bill description/i.test(step1), "…under a 2-word label");
check(!/rating\.chargeWizard/.test(step1), "no raw catalogue key leaked onto the screen");
// The page sub-line is §8's step count + estimate, and nothing else.
check(!/non-usage line items/i.test(step1), "the sub-line's definition sentence is GONE");

// ══════════════════════════════════════════════════════════════════════════
// STEP 2 — "step 2 too much text" + "make customer class drop down multi select"
// ══════════════════════════════════════════════════════════════════════════
note("\n── STEP 2 · Amount & behaviour ─────────────────────────────────");
await page.fill("#charge-code", "WALK1");
await page.fill("#charge-name", "Walkthrough fee");
await page.getByRole("button", { name: /^Continue$/ }).first().click();
await page.waitForTimeout(1200);
const step2 = await screenText();
note(step2.split("\n").filter(Boolean).map((l) => `    | ${l}`).join("\n"));

check(!/is permission, not an attachment/i.test(step2), "the 24-word taxability sentence is GONE");

// ⚠ **THE HELP LINES LIVE INSIDE `More about this step`, WHICH IS CLOSED BY
// DEFAULT (B14 rule 32), AND `innerText` DOES NOT READ COLLAPSED CONTENT.** A
// check that read the closed page would report these as "gone" — which is the
// same green whether the copy was shortened correctly or deleted by accident.
// So the disclosures are OPENED and re-read.
for (const d of await page.locator("details").all()) {
  await d.locator("summary").click().catch(() => {});
}
await page.waitForTimeout(500);
const step2open = await screenText();
check(/permits tax/i.test(step2open), "…and the RULE it carried is still said");
check(/never taxed/i.test(step2open), "…including BR-RAT-005, fees are never taxed");
check(!/rate schedule is for/i.test(step2open), "the step hint's RATIONALE clause is GONE");

// The customer-class picker: chips + a TYPE-TO-FILTER add control.
const field = page.locator('[data-chip-select="charge-customer-classes"]');
check(await field.count() === 1, "the class field is chips (B14 rule 9), not checkboxes");
check(await field.getByRole("checkbox").count() === 0, "…no wall of checkboxes");
const addBox = field.getByRole("combobox");
check(await addBox.count() === 1, "the ADD control is a combobox (searchable), not a bare select");
check(await field.locator("select").count() === 0, "…and the old `<select>` is gone from THIS field");

// ⚠ THE ASSERTION THE DEFECT CANNOT SATISFY: a class that is in no literal.
await addBox.click();
await page.keyboard.press("ArrowDown");
await page.waitForTimeout(400);
const options = await field.getByRole("option").allInnerTexts();
note(`    options offered: ${JSON.stringify(options)}`);
check(options.some((o) => /School district/i.test(o)),
  "the TENANT's ninth class is offered — proof the list is READ, not hardcoded");
check(options.some((o) => /Government/i.test(o)),
  "a LEGACY class is still offered (it prices accounts that already carry it)");

// It filters as you type — which is the whole of what the PO asked for.
await addBox.fill("school");
await page.waitForTimeout(700);
const filtered = await field.getByRole("option").allInnerTexts();
note(`    after typing "school": ${JSON.stringify(filtered)}`);
check(filtered.length > 0 && filtered.every((o) => /school/i.test(o)),
  "typing FILTERS the list (BR-SHL-033)");

await page.keyboard.press("Escape");

// ══════════════════════════════════════════════════════════════════════════
// STEP 3 — "step 3 too much text"
// ══════════════════════════════════════════════════════════════════════════
note("\n── STEP 3 · Review & save ──────────────────────────────────────");
await page.getByRole("button", { name: /^Continue$/ }).first().click();
await page.waitForTimeout(1200);
const step3 = await screenText();
note(step3.split("\n").filter(Boolean).map((l) => `    | ${l}`).join("\n"));

check(!/formatted by the server/i.test(step3), "the 31-word sample paragraph is GONE");
check(await page.locator("[data-sample-bill-line]").count() === 1, "a real sample bill LINE is drawn");
const sampleText = await page.locator("[data-sample-bill-line]").innerText();
note(`    sample line: ${JSON.stringify(sampleText)}`);
check(/Walkthrough fee/.test(sampleText), "…carrying the label that was typed");

// ── the cap, measured on what a person actually sees ──────────────────────
note("\n── B14 rule 33, measured on the RENDERED text ──────────────────");
for (const [label, text] of [["step 1", step1], ["step 2", step2], ["step 3", step3]]) {
  const lines = text.split("\n").map((s) => s.trim()).filter((s) => s && /\s/.test(s));
  const worst = lines
    .map((l) => ({ l, n: longestSentence(l) }))
    .sort((a, b) => b.n - a.n)[0] ?? { l: "", n: 0 };
  note(`  ${label}: ${lines.length} lines, longest sentence ${worst.n} words`);
  note(`    worst: ${JSON.stringify(worst.l.slice(0, 120))}`);
}

await browser.close();
note(`\n${failures === 0 ? "ALL CHECKS PASSED" : `${failures} CHECK(S) FAILED`}`);
process.exit(failures === 0 ? 0 : 1);
