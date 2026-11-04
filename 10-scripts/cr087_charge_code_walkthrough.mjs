// ── Trace ──────────────────────────────────────────────
// Change:   CR-087 — the Charge codes tab against its drawn blueprint.
//           Specs: 04-docs/05-modules/06-rating/conformance/CR-087-p003,
//           -p006, -p011, -p016, -p018.
// Defects:  DEF-RAT-4830 (a live column denied on screen for twenty days) ·
//           DEF-RAT-4831 (five types in a four-column grid; B14 rule 10
//           unmeetable) · DEF-RAT-4832 (?tab=audit opened the Overview; the
//           Plans tab could not name a plan)
// Rules:    CLAUDE.md hard-won law 6 (NO GATE READS RENDERED OUTPUT — diff the
//           running app) and law 2 in BOTH directions · B14 rules 9, 10, 16 ·
//           13-change-process.md's CLOSURE BAR, PO 2026-08-18: *"CR is not
//           closed until we have confirm user is able to perform tasks using
//           screen/broswer/UI"*
// ───────────────────────────────────────────────────────
/**
 * Walk the charge-code wizard and the charge-code page IN A REAL BROWSER.
 *
 *     BASE=http://127.0.0.1:5199 node 10-scripts/cr087_charge_code_walkthrough.mjs
 *
 * ⚠ **WHY THIS FILE EXISTS AND THE 654 VITEST CASES DO NOT REPLACE IT.** Every
 * defect this lane fixed passed `tsc`, eslint, every gate and every assertion
 * in `ChargeCodeWizard.test.tsx`, for twenty days in one case. A five-item row
 * wrapping inside a four-column grid, a catalogue key that renders blank, and a
 * refusal sentence that has stopped being true are all invisible to a test that
 * asserts on text content — and the first two are invisible to jsdom as well,
 * because it loads no stylesheet.
 *
 * ⚠ **IT ASSERTS THE SHAPE, NEVER A DRAWN FIGURE (B14 rule 37).** The frame
 * inks `$45.0000`, `74`, `12` and `132`; those say what a cell looks like and
 * nothing about what any real row holds. Nothing here compares a number to the
 * drawing.
 */
import { createRequire } from "node:module";
const require = createRequire("/home/user/SMARTBillHub/07-frontend/package.json");
const { chromium } = require("playwright");

const BASE = process.env.BASE ?? "http://127.0.0.1:5199";
const TENANT = process.env.TENANT ?? "brazosbend";
const EMAIL = process.env.EMAIL ?? "dana@brazosbendutilities.com";
const PASSWORD = process.env.PASSWORD ?? "S3cure!passw0rd";

const problems = [];
const note = (m) => console.log(m);
const fail = (m) => { problems.push(m); console.log("  ✗ " + m); };
const ok = (m) => console.log("  ✓ " + m);

const browser = await chromium.launch({
  ...(process.env.CHROME_PATH ? { executablePath: process.env.CHROME_PATH } : {}),
});
const ctx = await browser.newContext({ viewport: { width: 1440, height: 1100 } });
const page = await ctx.newPage();

// ⚠ **THE DEV SERVER PROXIES NOTHING, SO THE API IS FORWARDED HERE.**
// `DEFAULT_BASE_URL` is `""` (client.ts), so the app calls `/api/...` on
// whatever origin is serving it. `vite` has no proxy block and `server.mjs`
// — which does — is only used for a built bundle. Rather than start a second
// server, the request is forwarded at the browser: this drives the REAL
// screen against the REAL API, which is the whole point of the file.
const API = process.env.API ?? "http://127.0.0.1:8000";
// ⚠ **A REGEX ANCHORED AT THE PATH ROOT, NOT THE GLOB `**\/api/**`.** That glob
// also matches vite's own module URLs — `/src/api/client.ts`, `/src/api/endpoints.ts`
// — so the first version of this file forwarded the APPLICATION'S OWN SOURCE to
// Django, got five 404s, and rendered a page with no sign-in form on it. The
// walkthrough then reported "the field is missing" over a screen that was fine.
// A check broken this way does not fail loudly; it reports the wrong finding.
await page.route(/^https?:\/\/[^/]+\/api\//, async (route) => {
  const req = route.request();
  const target = API + new URL(req.url()).pathname + new URL(req.url()).search;
  const res = await ctx.request.fetch(target, {
    method: req.method(),
    headers: { ...req.headers(), host: new URL(API).host },
    data: req.postData() ?? undefined,
    maxRedirects: 0,
  });
  await route.fulfill({
    status: res.status(),
    headers: { ...res.headers(), "access-control-allow-origin": "*" },
    body: await res.body(),
  });
});

await page.goto(`${BASE}/${TENANT}/signin`, { waitUntil: "domcontentloaded" });
await page.fill("#signin-email", EMAIL);
await page.fill("#signin-password", PASSWORD);
await Promise.all([
  page.waitForURL((u) => !u.pathname.endsWith("/signin"), { timeout: 30000 }),
  page.click('button[type="submit"]'),
]);
note(`signed in as ${EMAIL} → ${page.url()}`);

async function continueOn() {
  const cont = page.getByRole("button", { name: /^Continue$/ }).first();
  if (!(await cont.count())) return false;
  await cont.click().catch(() => {});
  await page.waitForTimeout(900);
  return true;
}

/** Every visible line, as a person reads it — never innerHTML (B14 rule 31's
 *  own warning: the internal value rides on `title`, so a markup read goes red
 *  on a correct fix and green on the breach). */
const screenText = () => page.locator("body").innerText();

// ══════════════════════════════════════════════════════════════════════════
// STEP 1 · the type is a SELECT, and the table is shown BEFORE the choice
// ══════════════════════════════════════════════════════════════════════════
note("\n1 · Basics — the type control (DEF-RAT-4831)");
await page.goto(`${BASE}/${TENANT}/plans-rates/charge-codes/new`, { waitUntil: "domcontentloaded" });
await page.locator("#charge-code").waitFor({ timeout: 30000 });

const typeTag = await page.locator("#charge-type").evaluate((el) => el.tagName).catch(() => "MISSING");
typeTag === "SELECT" ? ok("the charge type is a select") : fail(`the charge type is a ${typeTag}, not a select`);

const typeOptions = await page.locator("#charge-type option").allInnerTexts();
typeOptions.length === 5
  ? ok(`five types, in the drawn order: ${typeOptions.join(" · ")}`)
  : fail(`${typeOptions.length} types offered, not five: ${typeOptions.join(" · ")}`);

// The five radio CARDS are gone rather than hidden — a second control beside
// the select would pass every assertion above this one.
(await page.locator('[role="radiogroup"][aria-label="Type"]').count()) === 0
  ? ok("the five radio cards are gone, not hidden behind the select")
  : fail("a radiogroup for the type is still on the screen");

// B14 rule 10 — the asterisk, READ OFF THE RENDERED LABEL.
const typeLabel = await page.locator('label[for="charge-type"]').innerText().catch(() => "");
typeLabel.includes("*")
  ? ok(`the type label carries the required marker: "${typeLabel.replace(/\s+/g, " ").trim()}"`)
  : fail(`the type label carries no asterisk: "${typeLabel}"`);
(await page.locator("#charge-type").getAttribute("aria-required")) === "true"
  ? ok("…and it is announced, not merely drawn")
  : fail("aria-required is missing from the type control");

// `What the type decides`, shown BEFORE the choice — the blueprint's complaint
// was that a clerk met the mapping for the first time after pressing Continue.
const rows = await page.locator("[data-type-effect]").count();
rows === 5
  ? ok("`What the type decides` draws all five rows, on step 1")
  : fail(`the type table draws ${rows} rows, not five`);

// ⚠ THE WRAP IS THE DEFECT, AND ONLY A BROWSER CAN SEE IT. Five cells in a
// four-column grid put the fifth on a row of its own. This measures the TOP of
// each row box: if they are not all equal, the strip has wrapped.
const tops = await page.locator("[data-type-effect]").evaluateAll((els) =>
  els.map((el) => Math.round(el.getBoundingClientRect().top)),
);
new Set(tops).size === 5
  ? ok(`the five rows stack as a table (tops ${tops.join(", ")}) — nothing wraps alone`)
  : fail(`the type rows do not lay out as five rows: tops ${tops.join(", ")}`);

// The step is IDENTITY ONLY — the drawing's own words.
const step1 = await screenText();
/carries no customer-class column/i.test(step1)
  ? fail("the FALSE customer-class refusal is still on step 1")
  : ok("the false customer-class refusal is gone from step 1");

await page.fill("#charge-code", `CR087W${Date.now().toString().slice(-5)}`);
await page.fill("#charge-name", "CR-087 walkthrough fee");
await page.selectOption("#charge-service", { index: 1 }).catch(() => {});
await continueOn();

// ══════════════════════════════════════════════════════════════════════════
// STEP 2 · the reach control, and the two required markers
// ══════════════════════════════════════════════════════════════════════════
note("\n2 · Amount & behaviour — who it reaches (DEF-RAT-4830) and rule 10");
await page.locator("#charge-amount-rule").waitFor({ timeout: 30000 });

const reach = page.locator('[data-chip-select="charge-customer-classes"]');
(await reach.count())
  ? ok("the customer-type control is on step 2, beside the amount it narrows")
  : fail("there is no customer-type control on step 2");

// B14 rule 9 — chips plus ONE add control, never a wall of checkboxes.
const ticks = await reach.locator('input[type="checkbox"]').count();
ticks === 0 ? ok("it is chips + an add control, not a wall of checkboxes")
            : fail(`${ticks} checkboxes drawn where rule 9 asks for chips`);

// An EMPTY list is a real answer and the field says so, in words.
const emptyLine = await reach.locator("[data-chip-empty]").innerText().catch(() => "");
emptyLine.trim().length > 0
  ? ok(`empty reads as words rather than a blank box: "${emptyLine.trim()}"`)
  : fail("the empty state renders as nothing — a clerk would hunt for boxes to tick");

// BUILT IS NOT WIRED — pick one and watch the chip appear.
const add = reach.locator("[data-chip-add]");
const offered = await add.locator("option").count();
await add.selectOption({ index: 1 }).catch(() => {});
await page.waitForTimeout(400);
const chips = await reach.locator("[data-chip]").count();
chips === 1
  ? ok(`choosing one of ${offered - 1} types puts a removable chip on the screen`)
  : fail(`a type was chosen and ${chips} chips are drawn`);

// …and it comes off again.
await reach.locator("[data-chip-remove]").first().click().catch(() => {});
await page.waitForTimeout(300);
(await reach.locator("[data-chip]").count()) === 0
  ? ok("and the chip carries its own remove, which works")
  : fail("the chip's remove control does not remove it");

// B14 rule 10 — the two drawn markers, read off the rendered labels.
for (const [id, what] of [["charge-amount-rule", "How the amount is worked out"], ["charge-amount", "Amount"]]) {
  const label = await page.locator(`label[for="${id}"]`).innerText().catch(() => "");
  const announced = await page.locator(`#${id}`).getAttribute("aria-required").catch(() => null);
  label.includes("*") && announced === "true"
    ? ok(`${what} carries the asterisk and is announced required`)
    : fail(`${what}: label "${label.replace(/\s+/g, " ").trim()}", aria-required=${announced}`);
}

// The four behaviour ticks STAY STACKED — PO 2026-09-10, "Stacks them down the
// page". The drawing asks DEF-2356 back, and this is what stops a later lane
// "fixing" the column into the row the PO rejected.
const tickTops = await page
  .locator("#charge-taxable, #charge-auto-apply, #charge-waivable, #charge-separate-line")
  .evaluateAll((els) => els.map((el) => Math.round(el.getBoundingClientRect().top)));
new Set(tickTops).size === tickTops.length && tickTops.length === 4
  ? ok(`the four behaviour ticks are still one per line (tops ${tickTops.join(", ")})`)
  : fail(`the behaviour ticks share a line again: tops ${tickTops.join(", ")}`);

// Money shows TWO decimals, however many it is stored to (hard rule 2).
await page.fill("#charge-amount", "45");
// Blur with the KEYBOARD. `#charge-name` is on step 1 and clicking it from
// step 2 waits thirty seconds for a field that is not on the screen — which is
// this file's own version of "looking at the wrong thing".
await page.keyboard.press("Tab");
await page.waitForTimeout(300);
const shown = await page.locator("#charge-amount").inputValue();
/^\d+(\.\d{0,2})?$/.test(shown)
  ? ok(`the amount box holds "${shown}" — never four decimals`)
  : fail(`the amount box holds "${shown}"`);

// ══════════════════════════════════════════════════════════════════════════
// STEP 3 · the review reads back the reach and calls the service by its name
// ══════════════════════════════════════════════════════════════════════════
note("\n3 · Review & save");
await continueOn();
const step3 = await screenText();
/Applies to service/i.test(step3)
  ? ok("the service row is headed `Applies to service`, the same words step 1 uses")
  : fail("the review still heads the service row with the list filter's word");
/Who it reaches/i.test(step3)
  ? ok("the reach is read back before the commit")
  : fail("a field a clerk can set is not read back on the review");

// ══════════════════════════════════════════════════════════════════════════
// THE DETAIL PAGE · the Plans tab, and the address that opened the wrong screen
// ══════════════════════════════════════════════════════════════════════════
note("\n4 · The charge code's page — Plans and Audit (DEF-RAT-4832)");
const listUrl = `${BASE}/${TENANT}/plans-rates/charge-codes`;
await page.goto(listUrl, { waitUntil: "domcontentloaded" });
await page.waitForTimeout(1500);
const firstCode = page.locator("table tbody tr a").first();
if (!(await firstCode.count())) {
  fail("no charge code on the list to open — cannot walk the detail page");
} else {
  await firstCode.click();
  await page.waitForTimeout(1500);
  const detail = page.url().split("?")[0];
  note(`   opened ${detail}`);

  // ⚠ THE BUG THIS CLOSES: `?tab=audit` fell back to the Overview, SILENTLY.
  await page.goto(`${detail}?tab=audit`, { waitUntil: "domcontentloaded" });
  await page.waitForTimeout(1200);
  const auditText = await screenText();
  /Bills always use the version in force/i.test(auditText)
    ? ok("?tab=audit opens the Audit tab (its DATED banner is on screen)")
    : fail("?tab=audit still lands somewhere else");
  // …and the ADDRESS did not move — PO: "Change the label, keep the address".
  await page.getByRole("tab", { name: /Overview/ }).first().click().catch(() => {});
  await page.waitForTimeout(600);
  await page.getByRole("tab", { name: /Audit/ }).first().click().catch(() => {});
  await page.waitForTimeout(600);
  page.url().includes("tab=versions")
    ? ok("clicking the tab still writes ?tab=versions — the address did not move")
    : fail(`the address moved: ${page.url()}`);

  // The Plans tab: the sentence is gone and a table is there.
  await page.goto(`${detail}?tab=plans`, { waitUntil: "domcontentloaded" });
  await page.waitForTimeout(1800);
  const plansText = await screenText();
  /needs a read that does not exist yet/i.test(plansText)
    ? fail("the Plans tab still says it cannot name the plans")
    : ok("the Plans tab no longer says it cannot do its job");
  /Two routes/i.test(plansText)
    ? ok("the TWO ROUTES callout is on the screen, once")
    : fail("the two-routes callout is missing");
  const headers = await page.locator("table thead th").allInnerTexts().catch(() => []);
  headers.length >= 4
    ? ok(`the drawn four columns are there: ${headers.map((h) => h.trim()).join(" · ")}`)
    : note(`   (no table rows for this code — headers seen: ${headers.join(" · ") || "none"})`);
  let reachRows = await page.locator("[data-reach]").count();
  note(`   ${reachRows} plan row(s) drawn`);

  // ⚠ **THE FIRST CODE ON THE LIST MAY REACH NOBODY, AND THAT IS A REAL STATE
  // RATHER THAN A PASS.** The drawn `Nothing carries it` case renders no table,
  // so an assertion that stopped here would report the TABLE as green over a
  // screen that never drew one. So find a code that reaches something — by
  // ASKING THE SERVER, never by typing a seeded code into this file (BR-RAT-035:
  // a charge code is tenant DATA; B14 rule 37: a drawn value is an illustration).
  if (reachRows === 0) {
    const listed = await ctx.request.get(`${API}/api/${TENANT}/charges`, { params: { per: 100 } });
    const codes = (await listed.json().catch(() => ({}))).results ?? [];
    let found = null;
    for (const row of codes) {
      const r = await ctx.request.get(`${API}/api/${TENANT}/charges/${row.id}/plans`, { params: { per: 5 } });
      const body = await r.json().catch(() => ({}));
      if ((body.count ?? 0) > 0) { found = { row, body }; break; }
    }
    if (found === null) {
      // ⚠ **A SCOPE THIS RUN COULD NOT COVER IS PRINTED AS A GAP, NOT SWALLOWED.**
      // Hard-won law 7: "a declared blind spot with no NUMBER attached is
      // indistinguishable from an empty one". Reporting ALL CLEAR over a table
      // that was never drawn is exactly that, so it counts as a problem.
      fail(`the reach TABLE was never drawn: ${codes.length} charge code(s) asked and none reached a plan `
        + `(is the API on ${API} serving GET /charges/{id}/plans? a 401 or 404 reads here as a zero)`);
    } else {
      note(`   walking ${found.row.code}, which the server says reaches ${found.body.count} plan(s)`);
      await page.goto(`${listUrl}/${found.row.id}?tab=plans`, { waitUntil: "domcontentloaded" });
      await page.waitForTimeout(1800);
      reachRows = await page.locator("[data-reach]").count();
      const heads = await page.locator("table thead th").allInnerTexts().catch(() => []);
      heads.length === 4
        ? ok(`the drawn FOUR columns are on the screen: ${heads.map((h) => h.trim()).join(" · ")}`)
        : fail(`${heads.length} columns drawn, not four: ${heads.join(" · ")}`);
      reachRows === found.body.count
        ? ok(`${reachRows} plan row(s) drawn — the screen and the server agree`)
        : fail(`the server says ${found.body.count} and the screen draws ${reachRows}`);
      // B14 rule 16 — the pagination footer the frame does not draw and the
      // rules require. NFR-3: the count is the WHOLE set, not the page.
      //
      // ⚠ **THE FIRST VERSION OF THIS CHECK LOOKED FOR THE WORD `Showing` AND
      // REPORTED THE FOOTER MISSING OVER A FOOTER THAT WAS THERE.** `ListPager`
      // has no early return — it always renders — and its own copy is
      // `{{from}}–{{to}} of {{total}}`, which contains no such word. Law 7's
      // *looking at the wrong thing*, found by running the walk. It asks the
      // shared component's own element now, which is the thing that decides.
      const pager = page.locator(".table-pager");
      if ((await pager.count()) > 0) {
        ok(`the pagination footer is there (B14 rule 16 over the drawing): "${(await pager.first().innerText()).replace(/\s+/g, " ").trim()}"`);
      } else {
        fail("no pagination footer — rule 16 and NFR-3 both ask for one");
      }
    }
  }
  if (reachRows > 0) {
    const routes = await page.locator("[data-reach]").evaluateAll((els) =>
      [...new Set(els.map((el) => el.getAttribute("data-reach")))],
    );
    note(`   routes present: ${routes.join(", ")}`);
    // B14 rule 31 — no database id is a visible value.
    /[0-9a-f]{8}-[0-9a-f]{4}-/i.test(plansText)
      ? fail("a uuid-shaped value is visible on the Plans tab")
      : ok("no database id reaches a cell");
  }
}

// ══════════════════════════════════════════════════════════════════════════
note(`\n${problems.length === 0 ? "ALL CLEAR" : problems.length + " PROBLEM(S)"}`);
for (const p of problems) console.log("  ✗ " + p);
await browser.close();
process.exit(problems.length === 0 ? 0 : 1);
