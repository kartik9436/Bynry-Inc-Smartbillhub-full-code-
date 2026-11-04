// ── Trace ──────────────────────────────────────────────
// Change:   `DEF-CUS-5482` · `DEF-CUS-5483` · `DEF-CUS-5485` — New Connect
//           steps 5 and 6, walked in a real browser.
// Rules:    CLAUDE.md hard-won law 6 (no gate reads rendered output — diff the
//           running app) · law 7 (a check's output must distinguish pass from
//           fail TO A READER) · 13-change-process.md's CLOSURE BAR (PO
//           2026-08-18: *"CR is not closed until we have confirm user is able
//           to perform tasks using screen/broswer/UI"*)
// ───────────────────────────────────────────────────────
/**
 * Walk the wizard to step 5 and step 6 and READ what renders.
 *
 *     node 10-scripts/def_cus_5483_charges_walkthrough.mjs
 *
 * ⚠ **IT MEASURES THE PAGE HEIGHT AND WHETHER `Continue` IS REACHABLE**, at
 * 1280 and at 1440. `DEF-CUS-5480` is a grid on the step before this one that
 * renders six of fourteen rows and eats the footer while every DOM count
 * passes — a screen can be correct in the DOM and unusable on the glass, and
 * nothing else in this repo looks.
 *
 * ⚠ **AND IT ASSERTS THE ABSENCES AS HARD AS THE PRESENCES.** The whole claim
 * of `DEF-CUS-5482` is that a question asked TWICE is now asked once, so the
 * check that matters is that step 5 no longer offers a plan. A walkthrough that
 * only looks for what it added cannot see a duplicate that stayed.
 */
import { createRequire } from "node:module";
const require = createRequire("/home/user/SMARTBillHub/07-frontend/package.json");
const { chromium } = require("playwright");

const BASE = process.env.BASE ?? "http://127.0.0.1:8098";
const TENANT = process.env.TENANT ?? "brazosbend";
const EMAIL = process.env.EMAIL ?? "dana@brazosbendutilities.com";
const PASSWORD = process.env.PASSWORD ?? "S3cure!passw0rd";

const problems = [];
const ok = (m) => console.log("  ✓ " + m);
const fail = (m) => { problems.push(m); console.log("  ✗ " + m); };

const browser = await chromium.launch({
  ...(process.env.CHROME_PATH ? { executablePath: process.env.CHROME_PATH } : {}),
});

async function walk(width) {
  console.log(`\n══ viewport ${width}×900 ══`);
  const ctx = await browser.newContext({ viewport: { width, height: 900 } });
  const page = await ctx.newPage();
  await page.goto(`${BASE}/${TENANT}/signin`, { waitUntil: "domcontentloaded" });
  await page.locator("#signin-email").fill(EMAIL);
  await page.locator("#signin-password").fill(PASSWORD);
  await page.locator("form button[type=submit]").first().click();
  await page.waitForURL((u) => !u.pathname.endsWith("/signin"), { timeout: 60000 });

  // ⚠ **THE DRAFT DOES NOT SURVIVE A RELOAD**, so the wizard is CLICKED to the
  // step rather than opened at `?step=5`. Landing by URL renders both steps
  // over an EMPTY build — zero units, zero ticks — where every count is 0 and
  // reads exactly like a working screen. That is law 7's *check that cannot
  // fail*, and it is why this walk types.
  await page.goto(`${BASE}/${TENANT}/connections/new`, { waitUntil: "domcontentloaded" });
  await page.waitForSelector('[data-screen="S87"]', { timeout: 30000 });

  const type = async (sel, value) => {
    const el = page.locator(sel).first();
    if ((await el.count()) === 0) return false;
    await el.fill(value);
    return true;
  };
  // ⚠ **THE PAGE DOES NOT SCROLL — `main.view` DOES, AND MEASURING THE DOCUMENT
  // REPORTS A FOOTER AS UNREACHABLE WHEN IT IS FINE.** Measured on the running
  // app: `document.documentElement.scrollHeight` is 900 (the shell is pinned to
  // the viewport, `.app-shell` and `.main` are both `overflow:hidden`) while
  // `main.view` carries `overflow-y:auto` with a 1261px scrollHeight over an
  // 844px client. The first version of this walk read the document and called a
  // reachable Continue button a defect — law 7's *looking at the wrong thing*,
  // inside the very check written to catch `DEF-CUS-5480`.
  //
  // So it SCROLLS THE REAL CONTAINER and then asks whether the button is inside
  // the viewport, which is the question a clerk's hand actually asks.
  const reachInPage = () => {
    const btn = [...document.querySelectorAll('[data-wizard="actions"] button')]
      .find((x) => x.textContent.trim().startsWith("Continue"));
    if (!btn) return { scroller: null, scrollerHeight: null, contentHeight: null, continueVisible: false };
    let el = btn.parentElement;
    while (el && el !== document.documentElement) {
      const cs = getComputedStyle(el);
      if ((cs.overflowY === "auto" || cs.overflowY === "scroll") && el.scrollHeight > el.clientHeight) break;
      el = el.parentElement;
    }
    const scroller = el && el !== document.documentElement ? el : document.scrollingElement;
    scroller.scrollTop = scroller.scrollHeight;
    const r = btn.getBoundingClientRect();
    return {
      scroller: scroller.tagName.toLowerCase() + "." + String(scroller.className).split(" ")[0],
      scrollerHeight: scroller.clientHeight,
      contentHeight: scroller.scrollHeight,
      continueVisible: r.top >= 0 && r.bottom <= window.innerHeight,
    };
  };
  const head = () => page.evaluate(() => document.querySelector("h1")?.textContent?.trim());
  /** Press Continue and REFUSE to carry on unless the page head changed to the
   *  step named. A silent failure to advance is what made the first run of this
   *  walk report twelve false defects. */
  const step = async (expected) => {
    const before = await head();
    await page.locator('[data-wizard="actions"] button', { hasText: "Continue" })
      .first().click();
    await page.waitForTimeout(450);
    const after = await head();
    if (after !== expected) {
      fail(`the wizard would not leave "${before}" — it now reads "${after}", expected "${expected}"`);
      throw new Error(`stuck on "${after}"`);
    }
  };
  const cont = step;

  // ⚠ **THE IDS ARE READ OFF THE STEP FILES, NOT GUESSED.** The first draft of
  // this walk typed into `#nc_owner_party_kind` and `#nc_premise_address`,
  // neither of which exists — `fill` on a missing locator was swallowed, step 1
  // never validated, and the walk then reported step 5 and step 6 defects that
  // were really "the wizard is still on step 1". A walk whose navigation can
  // fail silently is law 7's *check that looks at the wrong thing*, so `step()`
  // below REFUSES to go on unless the page head actually changed.
  //
  // ⚠ **`Person or company`, `Scope` and `Mode` ARE CARD RADIOS, NOT SELECTS.**
  // Read off the running page rather than off the source: `nc_party_kind` is a
  // `<label>`-wrapped radio group, so it is clicked BY ITS VISIBLE WORD, which
  // is also how a clerk reaches it. `nc_tax_id` does not exist until Company is
  // chosen, which is why the order below is not cosmetic.
  const pick = async (word) => {
    await page.locator('[data-wizard="content"] label', { hasText: new RegExp(`^${word}$`) })
      .first().click();
    await page.waitForTimeout(150);
  };
  // step 1 · owner & scope. `nc_prefix` lives HERE, in the scope group.
  await type("#nc_owner_name", "Ridge Property LLC");
  await pick("Company");
  await type("#nc_tax_id", "TX-4471-08");
  await pick("A new premise");
  await pick("Our crew did it");
  await type("#nc_prefix", "Apt");
  await step("The premise");
  // step 2 · premise — the plan now lives here
  await page.locator("#nc_premise_type").selectOption({ index: 1 }).catch(() => {});
  await type("#nc_address", "500 Main Street");
  // ⚠ **THE STREET'S SERVICES ARE TYPED HERE OR EVERY COUNT ON STEP 6 IS ZERO.**
  // The first run of this walk skipped them and reported *"per meter counts 0 —
  // the grid is not reaching this screen"*, which was the FIXTURE and not the
  // screen. A zero that is the honest answer to an empty build is exactly the
  // false red law 7 warns about, in the direction that wastes a lane's day.
  // `#services_available-add` is a `<select>` of the tenant's OWN enabled
  // services, not a text box — read off the running page, never guessed.
  for (const service of ["Electric", "Water", "Sewer"]) {
    await page.locator("#services_available-add").selectOption({ label: service })
      .catch(() => {});
    await page.waitForTimeout(250);
  }
  await step("The units");
  // step 3 · units — `Apt 101–106` plus the common area
  await type("#nc_from", "101");
  await type("#nc_to", "106");
  await step("Which services per unit");
  // step 4 · the services grid, left on its inherited defaults
  await step("Work orders");

  // ── STEP 5 ──────────────────────────────────────────────────────────────
  const five = await page.evaluate((src) => ({
    // eslint-disable-next-line no-new-func
    ...({ reach: new Function("return (" + src + ")()") }).reach(),
    title: document.querySelector("h1")?.textContent?.trim(),
    rail: [...document.querySelectorAll("[data-wizard-step]")]
      .map((b) => b.textContent.replace(/^\d+/, "").trim()),
    hasAddPicker: !!document.querySelector('[data-add-order="picker"]'),
    hasAddButton: !!document.querySelector("[data-add-order-commit]"),
    hasTarget: !!document.querySelector("#nc_target"),
    body: document.body.innerText,
  }), reachInPage.toString());
  console.log(`step 5 · "${five.title}" · scroller ${five.scroller} · content ${five.contentHeight}px in ${five.scrollerHeight}px`);
  five.title === "Work orders"
    ? ok('the page head reads "Work orders"')
    : fail(`the page head reads "${five.title}" — the plan was moved off this step`);
  five.rail[4] === "Work orders"
    ? ok('the rail\'s fifth step reads "Work orders"')
    : fail(`the rail's fifth step reads "${five.rail[4]}"`);
  for (const gone of ["All units on", "Common area on", "WON'T COVER", "Choose a published plan"]) {
    five.body.includes(gone)
      ? fail(`step 5 still shows "${gone}" — the wizard asks for the plan twice`)
      : ok(`"${gone}" is gone from step 5`);
  }
  five.hasAddPicker && five.hasAddButton
    ? ok("a work order can be ADDED — the control the PO asked for exists")
    : fail("no add-a-work-order control on step 5");
  five.hasTarget ? ok("the target activation date is still asked") : fail("the target date is gone");
  five.continueVisible
    ? ok(`Continue is reachable — ${five.contentHeight}px of content scrolls inside ${five.scrollerHeight}px`)
    : fail(`Continue cannot be scrolled into view — ${five.contentHeight}px of content in ${five.scrollerHeight}px`);

  await step("Charges");

  // ── STEP 6 ──────────────────────────────────────────────────────────────
  const six = await page.evaluate((src) => ({
    // eslint-disable-next-line no-new-func
    ...({ reach: new Function("return (" + src + ")()") }).reach(),
    title: document.querySelector("h1")?.textContent?.trim(),
    counts: [...document.querySelectorAll("[data-count-basis]")].map((r) => ({
      basis: r.getAttribute("data-count-basis"),
      qty: r.children[1]?.textContent?.trim(),
    })),
    payers: [...document.querySelectorAll("[data-payer]")].map((l) => ({
      which: l.getAttribute("data-payer"),
      available: l.getAttribute("data-available"),
      state: l.getAttribute("data-state"),
    })),
    dueDays: !!document.querySelector("#nc_quote_due_days"),
    postingDate: !!document.querySelector("#nc_quote_posting_date"),
    takePaymentRefused: !!document.querySelector('[data-take-payment="not-built"]'),
    body: document.body.innerText,
  }), reachInPage.toString());
  console.log(`step 6 · "${six.title}" · scroller ${six.scroller} · content ${six.contentHeight}px in ${six.scrollerHeight}px`);
  console.log("  counted: " + six.counts.map((c) => `${c.basis} = ${c.qty}`).join(" · "));
  six.counts.length === 3
    ? ok("three bases are counted on screen")
    : fail(`${six.counts.length} bases counted, expected 3`);
  // ⚠ **THE POINT OF THE WHOLE CHANGE: A NUMBER THAT IS NOT ZERO AND NOT
  // DRAWN.** `Apt 101–106` is six dwellings, so `per unit` must read 6 — the
  // drawing's own worked build. A zero here is the old screen.
  const perUnit = six.counts.find((c) => c.basis === "per unit")?.qty;
  perUnit === "6"
    ? ok("per unit counts 6 — the six dwellings typed at step 3")
    : fail(`per unit reads "${perUnit}", expected 6`);
  const perMeter = Number(six.counts.find((c) => c.basis === "per meter")?.qty ?? 0);
  perMeter > 0
    ? ok(`per meter counts ${perMeter} — read off step 4's grid`)
    : fail("per meter counts 0 — the grid is not reaching this screen");
  six.body.includes("$")
    ? fail("a currency symbol is on the charges screen — money was multiplied in the browser")
    : ok("no money figure is printed — nothing was multiplied up here (hard rule 2)");
  six.body.includes("3,030") || six.body.includes("1,950")
    ? fail("a DRAWN figure is on screen — B14 rule 37")
    : ok("no drawn illustration figure is printed");
  six.payers.length === 3
    ? ok("all three drawn payers are on screen")
    : fail(`${six.payers.length} payers, expected 3`);
  six.payers.find((p) => p.which === "owner_account")?.state === "selected"
    ? ok("the owner's account is the chosen payer")
    : fail("the owner's account is not selected");
  six.payers.filter((p) => p.available === "false").length === 2
    ? ok("the two refused payers are DISABLED radios, not divs that swallow a click")
    : fail("a refused payer is not disabled");
  six.dueDays && six.postingDate
    ? ok("payment terms and posting date are asked — the two fields the commit wanted and nobody sent")
    : fail("payment terms or posting date is missing");
  six.takePaymentRefused
    ? ok("taking a payment is refused by name rather than drawn dead")
    : fail("the unbuilt payment capture is not stated");
  six.continueVisible
    ? ok(`Continue is reachable — ${six.contentHeight}px of content scrolls inside ${six.scrollerHeight}px`)
    : fail(`Continue cannot be scrolled into view — ${six.contentHeight}px of content in ${six.scrollerHeight}px`);

  await ctx.close();
}

await walk(1280);
await walk(1440);
await browser.close();

console.log(
  problems.length === 0
    ? "\nWALK PASSED — every check above printed a tick."
    : `\nWALK FAILED — ${problems.length} problem(s):\n  - ${problems.join("\n  - ")}`,
);
process.exit(problems.length === 0 ? 0 : 1);
