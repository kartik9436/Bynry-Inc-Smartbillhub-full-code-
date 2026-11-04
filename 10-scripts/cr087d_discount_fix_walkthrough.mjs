// ── Trace ──────────────────────────────────────────────
// Change:  CR-087's Discounts fix wave + `CR-091-BRC01`, against the drawn
//          blueprint pages 65-84 and the two PO rulings of 2026-09-10.
// Rules:   hard-won law 6 (*"diff the running app against the prototype — nine
//          defects were found this way and by nothing else"*) · the UI skill
//          §15 close-out · B14 rule 8 (5+ options are searchable) · rule 9
//          (chips, never a wall of tick-boxes) · rule 31/32 (nothing internal
//          on a clerk's screen) · `BR-RAT-963` · `BR-RAT-964` · `DEF-364`
// ───────────────────────────────────────────────────────
//
// WHAT THIS OPENS, AND WHY EACH IS HERE RATHER THAN IN A UNIT TEST.
//
//   1 · The not-priceable note, driven by CHOOSING each type in a real
//       dropdown. A unit test can call the predicate; only the browser can say
//       that picking `Usage allowance` puts THAT type's name on the screen and
//       that `Charge waiver` — which prices perfectly well — gets no note at
//       all. ⚠ THIS WALK ASSERTED THE OPPOSITE ON ITS FIRST RUN AND THE SCREEN
//       WAS RIGHT: `DEF-2802`'s trap is that the pair a reader expects is not
//       the pair the predicate fires on, and it caught the author of the fix.
//   2 · The value read-back, TYPED. `0.15` must read back `0.15 is a 0.15%
//       reduction`, wrong on its face — the whole argument for replacing a
//       rule-to-remember with an echo. A rendering assertion cannot type.
//   3 · The service pair and its chip control, opened and used: seven scopes,
//       nothing chosen to begin with, a `<select>` add control, one chip with
//       its own remove.
//   4 · **Step 4 read with the budget cap CLEARED.** This is the check that
//       earned the walk: every unit assertion about the deleted second-approval
//       panel passed while a HELP LINE on the same step went on saying a blank
//       cap always needs one. Nothing but a browser and a cleared box finds a
//       true sentence that has become false.
//   5 · The review step, reached by clicking through, reading back the value
//       retyped four steps earlier.
//   6 · 1280 and 1440, the two staff widths the skill requires, checking that
//       the page body never scrolls sideways.
//
// USAGE: build and serve the branch, then
//   BASE=http://127.0.0.1:8577 node 10-scripts/cr087d_discount_fix_walkthrough.mjs
import { existsSync, readdirSync, mkdirSync } from "node:fs";
import { createRequire } from "node:module";
import { join } from "node:path";
const requireFrontend = createRequire(new URL("/home/user/SMARTBillHub/07-frontend/package.json", import.meta.url));
const { chromium } = requireFrontend("playwright-core");
const BASE = process.env.BASE ?? "http://127.0.0.1:8577";
const TENANT = process.env.TENANT ?? "brazosbend";
const EMAIL = process.env.EMAIL ?? "dana@brazosbendutilities.com";
const PASSWORD = process.env.PASSWORD ?? "S3cure!passw0rd";
const OUT = "/tmp/discount-walk"; mkdirSync(OUT, { recursive: true });
function resolveChromium() {
  const wanted = chromium.executablePath();
  if (wanted && existsSync(wanted)) return wanted;
  for (const root of [process.env.PLAYWRIGHT_BROWSERS_PATH, "/opt/pw-browsers"].filter(Boolean)) {
    if (!existsSync(root)) continue;
    for (const dir of readdirSync(root)) {
      if (!dir.startsWith("chromium")) continue;
      for (const sub of ["chrome-linux64/chrome","chrome-linux/chrome","chrome-linux/headless_shell"]) {
        const c = join(root, dir, sub); if (existsSync(c)) return c;
      }
    }
  }
  throw new Error("no chromium found");
}
const browser = await chromium.launch({ executablePath: resolveChromium() });
const page = await browser.newPage({ viewport: { width: 1440, height: 1100 } });
const say = (...p) => console.log(...p);
let bad = 0;
const check = (ok, label, detail = "") => { say(ok ? "  PASS " : "  FAIL ", label, detail); if (!ok) bad += 1; };

await page.goto(`${BASE}/${TENANT}/signin`, { waitUntil: "networkidle" });
await page.fill("#signin-email", EMAIL);
await page.fill("#signin-password", PASSWORD);
await page.click('button[type="submit"]');
await page.waitForURL((u) => !u.pathname.endsWith("/signin"), { timeout: 30000 });
say("signed in as", EMAIL);

await page.goto(`${BASE}/${TENANT}/plans-rates/discounts/new`, { waitUntil: "networkidle" });
await page.waitForSelector("#discount-type", { timeout: 30000 });

// ── 1 · step 1: the not-priceable note names the type CHOSEN ──────────────
say("\n1 · step 1 — the not-priceable sentence");
await page.selectOption("#discount-type", "usage_allowance");
let note = await page.locator("[data-note]").allInnerTexts();
let joined = note.join(" | ");
check(joined.includes("Usage allowance"), "picking Usage allowance names Usage allowance");
check(!joined.includes("Charge waiver"), "and does NOT name Charge waiver");
// ⚠ CHARGE WAIVER IS PRICEABLE AND GETS NO NOTE AT ALL — this walk asserted
// the opposite on its first run and the SCREEN was right. That is DEF-2802's
// own trap one turn later: the pair a reader expects here is not the pair the
// predicate fires on.
await page.selectOption("#discount-type", "charge_waiver");
joined = (await page.locator("[data-note]").allInnerTexts()).join(" | ");
check(!joined.includes("cannot be priced"), "Charge waiver PRICES, so it gets no note");
await page.selectOption("#discount-type", "rate_override");
joined = (await page.locator("[data-note]").allInnerTexts()).join(" | ");
check(joined.includes("Rate override"), "picking Rate override names Rate override");
check(!joined.includes("Charge waiver"), "and does NOT name Charge waiver");
await page.selectOption("#discount-type", "percentage");
joined = (await page.locator("[data-note]").allInnerTexts()).join(" | ");
check(!joined.includes("cannot be priced"), "a priceable type gets no note at all");

// ── 2 · step 2: the read-back, and the service pair ───────────────────────
await page.fill("#discount-code", "WALKTEST");
await page.fill("#discount-name", "Walkthrough discount");
await page.click('button:has-text("Continue")');
await page.waitForSelector("#discount-value", { timeout: 15000 });
say("\n2 · step 2 — the value read-back");
check((await page.locator("[data-value-readback]").count()) === 0, "nothing typed: no read-back line");
await page.fill("#discount-value", "10");
await page.waitForTimeout(150);
let rb = (await page.locator("[data-value-readback]").innerText()).trim();
check(rb === "10 is a 10% reduction — points, not a fraction.", "10 reads back", `→ ${rb}`);
await page.fill("#discount-value", "0.15");
await page.waitForTimeout(150);
rb = (await page.locator("[data-value-readback]").innerText()).trim();
check(rb === "0.15 is a 0.15% reduction — points, not a fraction.", "0.15 reads back wrong ON ITS FACE", `→ ${rb}`);
const help = await page.locator("#discount-value").evaluate((el) => el.closest("label,div")?.innerText ?? "");
check(!help.includes("POINTS, not a fraction"), "the two-sentence capitals rule is GONE");

say("\n3 · step 2 — the service pair (CR-091)");
const scopes = await page.$$eval("#discount-scope option", (os) => os.map((o) => `${o.value}::${o.textContent.trim()}`));
say("   scope options:", scopes.join(" | "));
check(scopes.length === 7, "seven scopes are offered");
check(scopes.some((s) => s.startsWith("all_services::All services")), "All services is offered");
check(scopes.some((s) => s.startsWith("specific_services::Specific services")), "Specific services is offered");
check((await page.locator('[data-chip-select="discount-services"]').count()) === 0, "no chip control until Specific services");
await page.selectOption("#discount-scope", "specific_services");
await page.waitForSelector('[data-chip-select="discount-services"]', { timeout: 10000 });
check(true, "choosing Specific services opens the chip control");
const emptyLabel = (await page.locator("[data-chip-empty]").innerText()).trim();
check(emptyLabel === "No services chosen yet", "it starts with NOTHING chosen", `→ ${emptyLabel}`);
const addOpts = await page.$$eval('[data-chip-add="discount-services"] option', (os) => os.map((o) => o.textContent.trim()));
say("   add control offers:", addOpts.join(" | "));
check((await page.locator('[data-chip-add="discount-services"]').evaluate((e) => e.tagName)) === "SELECT",
      "the add control is a <select>, which every browser type-filters (B14 rule 8)");
const firstService = await page.$eval('[data-chip-add="discount-services"] option:nth-child(2)', (o) => o.value);
await page.selectOption('[data-chip-add="discount-services"]', firstService);
await page.waitForTimeout(150);
check((await page.locator("[data-chip]").count()) === 1, "picking one adds ONE removable chip");
check((await page.locator("[data-chip-remove]").count()) === 1, "and the chip carries its own remove (B14 rule 9)");
await page.screenshot({ path: `${OUT}/step2-services.png` });

// ── 4 · step 4: the second-approval panel is GONE ─────────────────────────
await page.click('button:has-text("Continue")');
await page.waitForTimeout(400);
await page.click('button:has-text("Continue")');
await page.waitForSelector("#discount-effective-from", { timeout: 15000 });
say("\n4 · step 4 — the second-approval panel");
const step4 = await page.locator("main").innerText();
check(!step4.includes("Second approval"), "no Second approval panel");
check(!step4.includes("$500") && !step4.includes("$10,000"), "neither policy figure is on screen");
check(!step4.includes("Product Owner"), "and no internal role word (B14 rule 31/32)");
await page.fill("#discount-budget-cap", "");
await page.waitForTimeout(150);
check(!(await page.locator("main").innerText()).includes("second approval"),
      "a BLANK budget cap no longer claims a second approval is required");
await page.screenshot({ path: `${OUT}/step4.png` });

// ── 5 · step 5: the review reads back the DRAFT ───────────────────────────
await page.click('button:has-text("Continue")');
await page.waitForTimeout(600);
say("\n5 · step 5 — the review reads back what is about to be saved");
const review = await page.locator("main").innerText();
say("   review grid contains:", review.split("\n").filter((l) => l.trim()).slice(0, 30).join(" / "));
check(review.includes("0.15"), "the retyped value 0.15 is read back");
check(review.includes("as typed"), "and is marked as typed, not formatted");
await page.screenshot({ path: `${OUT}/step5.png`, fullPage: true });

// ── 6 · 1280 and the narrow guard ────────────────────────────────────────
say("\n6 · the staff width the skill requires");
for (const w of [1280, 1440]) {
  await page.setViewportSize({ width: w, height: 1000 });
  await page.waitForTimeout(200);
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth > document.documentElement.clientWidth + 1);
  check(!overflow, `no horizontal scroll at ${w}`);
}

say(`\n${bad === 0 ? "ALL CHECKS PASSED" : bad + " CHECK(S) FAILED"}`);
await browser.close();
process.exit(bad === 0 ? 0 : 1);
