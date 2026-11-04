// ── Trace ──────────────────────────────────────────────
// Change:  DEF-RAT-5793 / -5794 / -5795 — the four changes the PO approved walking TAX-02 in the
//          beta on 2026-09-19: cut the over-cap copy, the nineteen checkboxes
//          become two chip multi-selects, the "we cannot do this yet"
//          paragraphs come off, and step 3 reads back what the wizard collects.
// Rules:   PO definition of done, verbatim: *"everything should be executed based
//          on actual code, and rules that we place, also ensure you do web
//          walkthorugh before you sign off the user story or build"* ·
//          hard-won law 6 (no gate looks at rendered output) · B14 rules 9,
//          32 and 33.
// ───────────────────────────────────────────────────────
//
// WHY THIS ONE STUBS THE API INSTEAD OF PROXYING TO DJANGO.
//
// Every other tax walkthrough drives a seeded database. This change is
// FRONT-END ONLY — not one line of `06-backend` moved — and the shared
// development database is in use by other lanes tonight, so seeding it to look
// at a screen would be spending somebody else's resource on a question that does
// not need it. The bundle under test is the REAL `vite build` output rendered by
// a REAL browser; only the four reads behind it are fixtures.
//
// ⚠ WHAT THAT MEANS THIS CANNOT ANSWER, said here rather than left to be assumed
// (hard-won law 7 — a check that cannot cover its whole subject must print what
// it skipped beside what it checked): it does NOT prove the matched-premises
// COUNT is right, because that number is the engine's and a fixture cannot test
// it. `cr087b_tax_screens_walkthrough.mjs` owns that against a live server.
// What this proves is everything a person SEES: the controls, the words, and
// the read-back.
import { createRequire } from "node:module";
import { existsSync, mkdirSync, readdirSync, writeFileSync } from "node:fs";
import { join } from "node:path";

const requireFrontend = createRequire(new URL("../07-frontend/package.json", import.meta.url));
const { chromium } = requireFrontend("playwright-core");

const BASE = process.env.BASE ?? "http://127.0.0.1:8731";
const TENANT = process.env.TENANT ?? "brazosbend";
const OUT = process.env.OUT ?? "/tmp/def-rat-5793";
mkdirSync(OUT, { recursive: true });

// The eleven the platform ships, in SEED ORDER, `fire` at position 11 and
// nothing renumbered (CR-063). Served the way `GET /settings/services` serves
// them, because this screen reads the tenant's rows and never a list typed into
// the front end.
const SERVICES = [
  ["electric", "Electric"], ["water", "Water"], ["gas", "Gas"], ["sewer", "Sewer"],
  ["trash", "Trash"], ["storm_water", "Storm water"], ["solar", "Solar"],
  ["broadband", "Broadband"], ["thermal", "Thermal/Heat"], ["battery", "Battery"],
  ["fire", "Fire"],
].map(([service, name]) => ({
  service, name, enabled: true, primary_uom: "kgal", alt_uom: null,
  billing_basis: "metered", billed_uom: null, conversion_factor: null,
  revenue_account: null, base_revenue_account: null,
  rate_schedules: 1, active_accounts: 10,
}));

// ⚠ **EVERY PATH IS TENANT-SCOPED — `/api/{tenant}/…` — AND THE FIRST DRAFT OF
// THIS FILE GOT THAT WRONG**, so the shell fell over on `regional.language`
// being undefined and the wizard never mounted. Worth recording because of what
// it did to the checks: *"not one service or class checkbox is left"* PASSED
// over a React error page, which is hard-won law 7's *looking at the wrong
// thing* exactly. The mount assertion below now runs FIRST and stops the walk.
const STUBS = [
  [/\/api\/[^/]+\/me$/, {
    id: "3f2a0000-0000-4000-8000-000000000009", full_name: "Dana Whitfield",
    email: "dana@brazosbendutilities.com", phone: null,
    role: "owner", role_name: "Owner", must_change_password: false,
  }],
  [/\/api\/[^/]+\/shell\/display$/, {
    regional: {
      country: "US", timezone: "America/Chicago", language: "en",
      first_day_of_week: "sunday", currency: "USD", number_format: "1,234.56",
      date_format: "MM/DD/YYYY", time_format: "12h",
    },
    company: {
      legal_name: "Brazos Bend Utilities", dba_name: null, has_logo: false,
      mark: { kind: "initials", value: "BB" }, brand_primary_hex: null,
    },
    period: null,
  }],
  [/\/api\/[^/]+\/in-app-messages$/, { unread: 0, messages: [] }],
  [/\/api\/[^/]+\/me\/permissions$/, {
    role: "owner", role_name: "Owner",
    // `ratingAccess` reads exactly this cell, by code, and "Full" is the only
    // value that is neither denied nor read-only.
    permissions: [{ code: "plans_rates", label: "Plans & Rates", access: "Full" }],
  }],
  [/\/api\/[^/]+\/settings\/services/, SERVICES],
  // ⚠ **A PAGINATED ROUTE, NOT A BARE ARRAY** (`NFR-3` — every list is a
  // `{count,next,previous,results}` envelope). A bare array here parsed to an
  // EMPTY authority list, so the only option left was *Add an authority*, the
  // inline fields appeared, the step was incomplete and Continue silently
  // refused. The walk then failed on step 2 and said nothing about why.
  [/\/api\/[^/]+\/tax-jurisdictions/, {
    count: 1, next: null, previous: null,
    results: [
      { id: "8f1c0a52-0000-4000-8000-000000000001", name: "City of Brazos Bend", level: "city", authority: "City Finance", reference: "Ord. 14-22" },
    ],
  }],
  [/\/api\/[^/]+\/taxes\/matched-premises/, { count: 41, total: 85, resolvable: true, narrowed: true, sample: [] }],
];


const failures = [];
function check(name, ok, detail = "") {
  (ok ? console.log : (m) => { console.log(m); failures.push(name); })(
    `${ok ? "PASS" : "FAIL"}  ${name}${detail ? ` — ${detail}` : ""}`,
  );
}

// ⚠ THE PINNED BUILD AND THE INSTALLED ONE DISAGREE, AND EVERY WALKTHROUGH IN
// `10-scripts/` ALREADY SOLVES THIS. Copied from `cr087b_tax_screens_walkthrough.mjs`
// rather than re-invented: playwright-core asks for the build its version pins
// (1234) and /opt/pw-browsers holds 1194, so `launch()` with no executablePath
// dies with an install banner that reads like a broken machine.
function resolveChromium() {
  const wanted = chromium.executablePath();
  if (wanted && existsSync(wanted)) return wanted;
  for (const root of [process.env.PLAYWRIGHT_BROWSERS_PATH, "/opt/pw-browsers"].filter(Boolean)) {
    if (!existsSync(root)) continue;
    for (const dir of readdirSync(root)) {
      if (!dir.startsWith("chromium")) continue;
      for (const sub of ["chrome-linux64/chrome", "chrome-linux/chrome", "chrome-linux/headless_shell"]) {
        const candidate = join(root, dir, sub);
        if (existsSync(candidate)) return candidate;
      }
    }
  }
  throw new Error("no chromium found");
}

const browser = await chromium.launch({ executablePath: resolveChromium(), args: ["--no-sandbox"] });
const ctx = await browser.newContext({ viewport: { width: 1360, height: 1000 } });
const page = await ctx.newPage();

await page.route(/\/api\//, async (route) => {
  const url = route.request().url();
  for (const [pattern, body] of STUBS) {
    if (pattern.test(url)) {
      return route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(body) });
    }
  }
  return route.fulfill({ status: 200, contentType: "application/json", body: "[]" });
});

const url = `${BASE}/${TENANT}/plans-rates/taxes-fees/new`;
await page.goto(url, { waitUntil: "networkidle" });
await page.waitForTimeout(800);

// ── STEP 1 ───────────────────────────────────────────────────────────────
const step1 = await page.content();
await page.screenshot({ path: `${OUT}/step1.png`, fullPage: true });

// ⚠ DID THE WIZARD MOUNT AT ALL? Everything below reads the DOM, and an
// assertion of the form "X is absent" passes triumphantly on an error page.
if (step1.includes("Unexpected Application Error") || !step1.includes("Step 1 of 3")) {
  console.log("FAIL  the wizard did not mount — every check below would be meaningless");
  console.log((await page.innerText("body")).slice(0, 600));
  await browser.close();
  process.exit(1);
}

check("step 1 · services render as the KIT's chip control, not checkboxes",
  (await page.locator('[data-chip-select="tax-services"]').count()) === 1);
check("step 1 · customer classes render as the chip control too",
  (await page.locator('[data-chip-select="tax-customer-classes"]').count()) === 1);
check("step 1 · not one service or class CHECKBOX is left (B14 rule 9)",
  !/id="service-|id="class-/.test(step1));

// ⚠ THE TRAP: an EMPTY list means EVERY value. A chip row reading "none
// chosen" would silently redefine an untouched field.
const servicesEmpty = (await page.locator('[data-chip-select="tax-services"] [data-chip-empty]').innerText()).trim();
const classesEmpty = (await page.locator('[data-chip-select="tax-customer-classes"] [data-chip-empty]').innerText()).trim();
check("step 1 · the empty services box says EVERY, not none", servicesEmpty === "All services", `read "${servicesEmpty}"`);
check("step 1 · the empty classes box says EVERY, not none", classesEmpty === "Every customer class", `read "${classesEmpty}"`);

// All ELEVEN services are offered, fire included, from the tenant's rows.
const offered = await page.locator('[data-chip-select="tax-services"] select option').allTextContents();
check("step 1 · all eleven services are offered, fire among them",
  SERVICES.every((s) => offered.some((o) => o.trim() === s.name)), `${offered.length} options`);

// A chip can actually be ADDED — the control is wired, not decorative.
await page.selectOption('[data-chip-select="tax-services"] select', "fire");
await page.waitForTimeout(250);
check("step 1 · choosing Fire puts a removable chip on the field",
  (await page.locator('[data-chip-select="tax-services"] [data-chip="fire"]').count()) === 1);
await page.screenshot({ path: `${OUT}/step1-chip-added.png`, fullPage: true });

check("step 1 · the deleted rationale paragraphs are gone",
  !step1.includes("no shared registry") && !step1.includes("Overlapping boundaries are expected"));

// ── STEP 2 ───────────────────────────────────────────────────────────────
// ⚠ **THE STEPS ARE CLICKED, NOT JUMPED TO, AND THAT IS NOT A STYLE CHOICE.**
// `BR-SHL-018` fences a NEW record: it earns one step at a time, so
// `?step=2` on an unsaved tax CLAMPS BACK to step 1 and every assertion below
// would then read step 1's DOM and fail for the wrong reason. The first draft
// of this file did exactly that. Clicking is also the only thing that proves
// `Continue` reaches the next step at all.
await page.fill("#name", "City franchise fee");
await page.selectOption("#jurisdiction", "8f1c0a52-0000-4000-8000-000000000001");
await page.click('button:has-text("Continue")');
await page.waitForTimeout(700);
check("step 1 → 2 · Continue reaches step 2", (await page.content()).includes("Step 2 of 3"));
const step2 = await page.content();
await page.screenshot({ path: `${OUT}/step2.png`, fullPage: true });

check("step 2 · the compounding 'we cannot do this yet' panel is gone",
  !step2.includes("Compounding order") && !step2.includes("taxes itself in a circle"));
check("step 2 · the discount CONSEQUENCE keeps its worked figures",
  step2.includes("$3.78") && step2.includes("$3.80"));
check("step 2 · and drops the rationale around them",
  !step2.includes("authority's own rules"));
// ⚠ **THIS NOTE ONLY EXISTS ONCE A RULE IS CHOSEN, AND THE FIRST VERSION OF
// THIS CHECK DID NOT CHOOSE ONE.** It asserted the sentence over a blank
// picker, where the component deliberately renders nothing, and failed for a
// reason that had nothing to do with the copy. A check that cannot describe
// the state it is measuring is hard-won law 7's *looking at the wrong thing*.
check("step 2 · with a blank rule there is no note at all (nothing to warn about)",
  !step2.includes("Recorded only"));
await page.selectOption("#rounding_rule", "half_even");
await page.waitForTimeout(300);
const rounded = await page.content();
check("step 2 · choosing a rule says it is RECORDED and not applied (OQ-309)",
  rounded.includes("Recorded only") && rounded.includes("standard rounding"));
await page.screenshot({ path: `${OUT}/step2-rounding.png`, fullPage: true });

// ── STEP 3 ───────────────────────────────────────────────────────────────
await page.click('button:has-text("Continue")');
await page.waitForTimeout(700);
check("step 2 → 3 · Continue reaches the review", (await page.content()).includes("Step 3 of 3"));
const step3 = await page.content();
await page.screenshot({ path: `${OUT}/step3.png`, fullPage: true });

// The PO's own words: *"it should display here the selction it is preview"*.
for (const label of [
  "Name on bill", "Authority", "Basis", "Rate", "Discounts", "Boundary",
  "Customer classes", "Applies to", "Effective from", "Effective to", "Rounding",
]) {
  check(`step 3 · the read-back states "${label}"`, step3.includes(`>${label}<`));
}
// The rule chosen on step 2 is the one read back here — which is the whole
// point of the row, and it caught this check measuring the wrong state twice.
check("step 3 · the rounding rule chosen on step 2 is the one read back",
  step3.includes("Half to even"));
// ⚠ WHAT THIS WALK CANNOT SHOW, stated rather than left blank: the UNSET case,
// where a blank rule must read as *Standard rounding (half up)* — the rule a
// bill will actually use — and not as a dash. It cannot be reached from here
// because this walk has just set one, and re-walking three steps to look at a
// default is a unit test's job. `TaxWizard.test.tsx` asserts it by name.

const rows = await page.locator("dl dt").count();
check("step 3 · the read-back is more than the four facts the PO found", rows >= 11, `${rows} rows`);

writeFileSync(`${OUT}/step3.html`, step3);
await browser.close();

console.log(`\nscreenshots in ${OUT}`);
if (failures.length > 0) {
  console.log(`\n${failures.length} FAILED:`);
  for (const one of failures) console.log(`  · ${one}`);
  process.exit(1);
}
console.log("\nall checks passed");
