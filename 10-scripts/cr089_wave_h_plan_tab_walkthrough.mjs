// ── Trace ──────────────────────────────────────────────
// Change:  CR-089 wave H — H1 (`PUJ-33`, `DEF-MET-4689`) one date format with a
//          named month · H2 (`PUJ-34`, `DEF-MET-4693`) one floor sentence and
//          eligibility written for a clerk · H3 (`PUJ-35`) a zero base says
//          what the service is priced on.
// Rules:   BR-MET-1166 · BR-MET-1167 · B14 rule 32 · CR-063 (fire: the size
//          picks the price, the COUNT multiplies it) · PO definition of done,
//          verbatim: *"everything should be executed based on actual code, and
//          rules that we place, also ensure you do web walkthorugh before you
//          sign off the user story or build"* · hard-won law 6 (no gate in this
//          repo looks at rendered output).
// ───────────────────────────────────────────────────────
//
// **WHY A BROWSER AND NOT A DOM TEST, FOR THESE THREE IN PARTICULAR.**
//
// `DEF-MET-4689` is *"the same screen writes a date four different ways"*. Two
// of those four are NATIVE `<input type="date">` controls, which render in the
// BROWSER's own locale — a thing jsdom does not have and no API reports. So the
// only place the claim *"a person sees one date shape"* can be checked is a
// real browser, and the check below reads what the boxes actually print by
// asking the page, not by formatting the value again.
//
// It also reads the WHOLE tab as one string and counts date shapes across it,
// because every one of these three defects is a property of the page rather
// than of any component on it. That is the comparison nothing else makes.
//
// ── HOW TO RUN IT ───────────────────────────────────────────────────────────
//
//   eval "$(10-scripts/proof-db.sh clone cr89h --export)"   # a private clone
//   (cd 06-backend && DATABASE_URL=$DATABASE_URL DJANGO_SETTINGS_MODULE=config.settings.local \
//      JOBS_EAGER=false python3 manage.py runserver 127.0.0.1:8531 --noreload)
//   (cd 07-frontend && ./node_modules/.bin/vite build && PORT=8541 \
//      API_PROXY_TARGET=http://127.0.0.1:8531 node server.mjs)
//   node 10-scripts/cr089_wave_h_plan_tab_walkthrough.mjs
//
// ⚠ **CHECK THE PORT IS YOURS.** `runserver` prints *"That port is already in
// use"* and exits, and a lane that does not read the log spends two runs
// reading a SIBLING's backend. Grep the log for `Starting development server`
// before believing anything below.
//
// ⚠ **THE FIXTURE.** `SCW-U-001 · Unit 1`, 101 Silver Creek Rd, on the seeded
// `brazosbend` demo. The tenant's Regional date format is `MM/DD/YYYY`, which
// is what made `06/01/2026` ambiguous in the first place — on a tenant set to
// `YYYY-MM-DD` this screen never showed the defect at all.
//
// ⚠ **`H3` NEEDS A SERVICE WITH A ZERO BASE AND NO SEEDED TENANT HAS ONE.**
// `SCW-RES` ships two services and both are priced; the three zero-base rows
// the Product Owner met — Trash, Solar and Fire — exist on no tenant in this
// repository. CR-089 §6's own correction block is about exactly this, so the
// arrangement is stated rather than hidden. Add them to YOUR OWN CLONE first:
//
//   psql "$DATABASE_URL" <<'SQL'
//   set app.tenant_id='<the tenant uuid>';
//   INSERT INTO plan_services (id, base_charge, currency, minimum_amount,
//     gl_account_id, created_at, updated_at, service_id, tenant_id,
//     rate_plan_id, outside_city_exempt)
//   SELECT gen_random_uuid(), 0.000000, 'USD', NULL, NULL, now(), now(), sv.id,
//     '<the tenant uuid>', '<SCW-RES plan uuid>', false
//   FROM services sv WHERE sv.code IN ('trash','solar','fire');
//   SQL
//
// Three rows at `0.0000`, nothing else touched, and the plan's Base charges Σ
// is unmoved because three zeros add nothing — which is why the sum check at
// the bottom of this file still holds afterwards. The `H3` checks say so by
// name when the rows are absent rather than passing over an empty table.
const { existsSync, readdirSync, mkdirSync, writeFileSync } = await import("node:fs");
const { createRequire } = await import("node:module");
const { join } = await import("node:path");

const requireFrontend = createRequire(new URL("../07-frontend/package.json", import.meta.url));
const { chromium } = requireFrontend("playwright-core");

const BASE = process.env.BASE ?? "http://127.0.0.1:8541";
const TENANT = process.env.TENANT ?? "brazosbend";
const EMAIL = process.env.EMAIL ?? "dana@brazosbendutilities.com";
const PASSWORD = process.env.PASSWORD ?? "S3cure!passw0rd";
const UNIT = process.env.UNIT ?? "01a08246-3eaf-7b8a-a671-ee5928dd3fa4"; // SCW-U-001
const OUT = process.env.OUT ?? "/tmp/cr89h";
mkdirSync(OUT, { recursive: true });

function resolveChromium() {
  const wanted = chromium.executablePath();
  if (wanted && existsSync(wanted)) return wanted;
  for (const root of [process.env.PLAYWRIGHT_BROWSERS_PATH, "/opt/pw-browsers"].filter(Boolean)) {
    if (!existsSync(root)) continue;
    for (const dir of readdirSync(root)) {
      const candidate = join(root, dir, "chrome-linux", "chrome");
      if (existsSync(candidate)) return candidate;
    }
  }
  throw new Error("no chromium found — set PLAYWRIGHT_BROWSERS_PATH");
}

const results = [];
// ⚠ A CHECK'S OUTPUT MUST DISTINGUISH PASS FROM FAIL TO A READER (law 7). Every
// check prints the sentence it looked for AND what it found instead.
function check(name, ok, detail = "") {
  results.push({ name, ok });
  console.log(`${ok ? "  PASS" : "  FAIL"}  ${name}${ok || !detail ? "" : `\n          ${detail}`}`);
}

/** Every date-shaped run in the page text. No `\b`: a label and its value are
 *  concatenated with no separator, so a word boundary never fires. */
function dateShapes(text) {
  const found = new Set();
  for (const m of text.matchAll(/(?<!\d)\d{4}-\d{2}-\d{2}(?!\d)/g)) found.add(m[0]);
  for (const m of text.matchAll(/(?<!\d)\d{1,2}\/\d{1,2}\/\d{4}(?!\d)/g)) found.add(m[0]);
  for (const m of text.matchAll(/(?<!\d)\d{1,2} [A-Z][a-z]{2} \d{4}(?!\d)/g)) found.add(m[0]);
  return [...found].sort();
}

const browser = await chromium.launch({ executablePath: resolveChromium(), args: ["--no-sandbox"] });
const page = await browser.newPage({ viewport: { width: 1440, height: 1600 } });

await page.goto(`${BASE}/${TENANT}/signin`, { waitUntil: "networkidle" });
await page.fill("#signin-email", EMAIL);
await page.fill("#signin-password", PASSWORD);
await page.click('button[type="submit"]');
await page.waitForTimeout(3000);
console.log(`signed in as ${EMAIL}\n`);

await page.goto(`${BASE}/${TENANT}/premises/units/${UNIT}?tab=plan`, { waitUntil: "networkidle" });
await page.waitForTimeout(4000);
await page.screenshot({ path: join(OUT, "cr089-wave-h-plan-tab.png"), fullPage: true });

const main = page.locator("main");
const text = await main.innerText();
writeFileSync(join(OUT, "cr089-wave-h-plan-tab.txt"), text);

// ── H1 · ONE DATE SHAPE, AND IT NAMES ITS MONTH ─────────────────────────────
console.log("H1 · one date format, with a named month (DEF-MET-4689)");
check("the plan's Effective from reads a named month", text.includes("1 Jun 2026"),
  `not found. date shapes on the tab: ${JSON.stringify(dateShapes(text))}`);
check("the pricing panel no longer prints the stored string 2026-06-01",
  !text.includes("2026-06-01"), "2026-06-01 is still on the page");
check("the period sentence names its months",
  text.includes("1 Sep 2026") && text.includes("30 Sep 2026"),
  `sentence found: ${(text.match(/Showing what applies[^\n]*/) ?? ["<none>"])[0]}`);
check("the period's stored strings are gone from the sentence",
  !text.includes("2026-09-01") && !text.includes("2026-09-30"),
  "an ISO period bound is still rendered as text");

// The two native controls. Their VALUE stays ISO — that is what the control is
// — and the named-month line beneath each is what a person compares.
const boxes = await page.locator('input[type="date"]').all();
const values = [];
for (const box of boxes) values.push(await box.inputValue());
check("both period boxes still hold an ISO value the picker can use",
  values.length === 2 && values.every((v) => /^\d{4}-\d{2}-\d{2}$/.test(v)),
  `values: ${JSON.stringify(values)}`);
// What a PERSON reads under each box, taken from the rendered label group.
const echoes = await page.locator('[data-pricing-period-control] label span[aria-hidden="true"]').allInnerTexts();
check("each period box carries a named-month line a person can read",
  echoes.length === 2 && echoes.every((one) => /^\d{1,2} [A-Z][a-z]{2} \d{4}$/.test(one)),
  `lines under the boxes: ${JSON.stringify(echoes)}`);

// ⚠ **THE WHOLE-PAGE CLAIM, AND IT IS UNCONDITIONAL NOW.**
// Everything on this screen that looks like a date must be the one shape. That
// is `BR-MET-1167` and it is what a person actually experiences; no unit test
// in this repository can assert it.
//
// ⚠ **THE NAMED EXCEPTION IS GONE, AND IT WENT THE WAY IT WAS SUPPOSED TO
// (`DEF-MET-4725`, closed 2026-09-09 by CR-089 wave F).** Wave H could not
// touch the `ON PLAN SINCE` KPI tile — it sat in the strip wave F was
// rewriting — so instead of an allowance nobody ever removes it wrote **a
// second check that went RED the day the hold expired**, naming what to
// delete. Wave F then replaced that strip's four tiles with **Assets · Owed ·
// Plan · Open work** under `F3`, the tile went with them, and the expiry check
// fired exactly as designed. This is hard-won law 2's mirror working end to
// end, which is rare enough to be worth the paragraph: the hold was written
// with its own alarm, the alarm went off on its own, and the lane that
// expired the hold is the one that deleted the exception.
const strays = dateShapes(text).filter((one) => !/^\d{1,2} [A-Z][a-z]{2} \d{4}$/.test(one));
check("no numeric date shape survives anywhere on this screen",
  strays.length === 0,
  `still numeric: ${JSON.stringify(strays)} — every date on a screen uses one format (BR-MET-1167)`);

// ── H2 · ONE FLOOR SENTENCE, AND ELIGIBILITY FOR A CLERK ────────────────────
console.log("\nH2 · one floor sentence, eligibility written for a clerk (DEF-MET-4693)");
const FLOOR = "No floor is set — a bill can be any amount, including nothing";
const copies = text.split(FLOOR).length - 1;
check("the floor sentence is printed exactly ONCE", copies === 1, `printed ${copies} time(s)`);
check("the sentence printed seven times is gone", !text.includes("No floor is set on this plan."),
  "the old sentence is still on the page");
check("eligibility no longer explains our implementation to a clerk",
  !text.includes("no code reads them"),
  "the B14 rule 32 sentence is still rendered");
check("eligibility says what the JOB is",
  text.includes("Not checked — no plan here asks for proof before it applies"),
  `eligibility row reads: ${(text.match(/Eligibility check\n[^\n]*/) ?? ["<none>"])[0]}`);

// ── H3 · A ZERO BASE SAYS WHAT PRICES IT ────────────────────────────────────
console.log("\nH3 · a zero base says what the service is priced on (PUJ-35, BR-MET-1166)");
const cells = await page.locator("[data-priced-on]").count();
check("every service row carries a Priced on cell", cells > 0, `found ${cells}`);
for (const [service, shape] of [["fire", "size_bands"], ["trash", "size_bands"], ["solar", "capacity"]]) {
  const row = page.locator(`[data-plan-service="${service}"]`);
  const present = (await row.count()) > 0;
  if (!present) {
    check(`${service} is on this plan`, false,
      "not on SCW-RES — run with --seed-zero-base, see this file's header");
    continue;
  }
  const rowText = await row.innerText();
  const got = await row.locator("[data-priced-on]").getAttribute("data-priced-on");
  check(`${service} shows $0.00 AND says what prices it (${shape})`,
    rowText.includes("$0.00") && got === shape,
    `row reads: ${JSON.stringify(rowText)} · data-priced-on=${got}`);
}
// Fire's zero is CORRECT and that is the whole point — CR-063: the size class
// picks the price and the COUNT multiplies it.
const fireText = (await page.locator('[data-plan-service="fire"]').count())
  ? await page.locator('[data-plan-service="fire"]').innerText()
  : "";
check("fire's row names the size-times-count arithmetic",
  fireText.includes("By the size of each one, times how many"),
  `fire row: ${JSON.stringify(fireText)}`);
check("solar names the unit it sums in", (await page.locator('[data-priced-on="capacity"]').count()) > 0
  && (await page.locator('[data-priced-on="capacity"]').first().innerText()).includes("kW"),
  "solar's cell does not name kW");

// ── THE SUM THE PRODUCT OWNER CHECKED, RE-CHECKED ───────────────────────────
// Decision log 2026-09-08 §5: the service bases add to the plan's own figure,
// and *"that is the one sum on the screen a person can verify"*. This READS
// both sides off the rendered page and compares them; it computes no price and
// writes nothing — BR-RAT-027's Σ is rating's, forwarded.
console.log("\nThe one sum on this screen a person can check");
const bases = (await page.locator("[data-plan-service] td:nth-child(2)").allInnerTexts())
  .map((one) => Number(one.replace(/[^0-9.]/g, "")))
  .filter((n) => Number.isFinite(n));
const shown = Number(((text.match(/BASE CHARGES\n\$([\d,.]+)/) ?? [])[1] ?? "").replace(/,/g, ""));
const summed = bases.reduce((a, b) => a + b, 0);
check("the service bases add to the plan's Base charges",
  bases.length > 0 && Math.abs(summed - shown) < 0.005,
  `rows ${JSON.stringify(bases)} sum to ${summed.toFixed(2)}; the plan reports ${shown.toFixed(2)}`);

// ── WHAT IS STILL WRONG AND IS NOT THIS WAVE'S ──────────────────────────────
// ⚠ **THIS NOTE USED TO SAY THE `ON PLAN SINCE` TILE WAS SOMEBODY ELSE'S AND
// PRINTED A SECOND DATE SHAPE. THE TILE NO LONGER EXISTS.** CR-089 wave F's
// `F3` replaced the strip's four tiles with **Assets · Owed · Plan · Open
// work**, so there is nothing left to hand over — `DEF-MET-4725` is closed by
// removal rather than by reformatting. Left as a note rather than deleted
// silently, because a reader of this file will otherwise wonder where the
// hand-over went.

const failed = results.filter((r) => !r.ok);
console.log(`\n${results.length - failed.length}/${results.length} checks passed`);
console.log(`screenshot: ${join(OUT, "cr089-wave-h-plan-tab.png")}`);
await browser.close();
process.exit(failed.length === 0 ? 0 : 1);
