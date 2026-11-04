/**
 * CR-035 · r11 step 2d — **PROVE IT BY CLICKING** (hard-won law 6: no gate in
 * this repo looks at rendered output, and nine defects were found this way and
 * by nothing else).
 *
 * WHY THIS IS NOT A VITEST FILE. `wizardPark.dom.test.tsx` and
 * `WaitingOnTab.dom.test.tsx` cover the same feature in jsdom and cover it
 * well — and jsdom cannot tell you that a button is VISIBLE, that a panel
 * OPENED where a person can see it, or that the row you just parked is on the
 * screen you landed on. It also has no bundler: these run the real `vite build`
 * output, the real router and the real Tailwind CSS.
 *
 * ⚠ **IT EARNED ITS KEEP ON THE FIRST RUN.** Answering `/units/{id}/assets`
 * with a generic empty page took the whole move-in screen down with
 * `Cannot read properties of undefined (reading 'total')` —
 * `UnitAssetsPanel` reads `assets.counts.total` with no guard on `counts`
 * itself. That is another lane's file and is REPORTED, not fixed here; the
 * point is that no suite in this repo could have told anyone.
 *
 * RUN (from 07-frontend):
 *   npx vite build
 *   PORT=4319 API_PROXY_TARGET= node server.mjs &
 *   node ../10-scripts/render-checks/cr035-park-clickthrough.mjs
 *   node ../10-scripts/render-checks/cr035-resume-clickthrough.mjs
 *
 * The API is answered by Playwright route interception, reproducing the
 * SERVICE's own behaviour — `subject_ref: null` is stored as `{}` and a bare
 * string is refused `VAL-002` — so the contract bug the coordinator caught
 * would fail here rather than be papered over.
 *
 * Exits non-zero on any failed check.
 */
import fs from "node:fs";
import path from "node:path";
import { createRequire } from "node:module";

// Borrow playwright-core from 07-frontend/node_modules, the way
// `column-chooser-geometry.mjs` and `12-smoke-walkthrough.mjs` do — this script
// has no dependencies of its own and must not add a second install. Run it from
// the REPO ROOT.
const requireFrontend = createRequire(path.resolve("07-frontend/package.json"));
const { chromium } = requireFrontend("playwright-core");

/** Any installed chromium, not only the revision playwright pinned — the same
 *  resolution `column-chooser-geometry.mjs` uses, and for the same reason: the
 *  pinned revision is often not the one on the box. */
function findChromium() {
  if (process.env.SBH_CHROMIUM) return process.env.SBH_CHROMIUM;
  const wanted = chromium.executablePath();
  if (fs.existsSync(wanted)) return wanted;
  const root = process.env.PLAYWRIGHT_BROWSERS_PATH ?? "/opt/pw-browsers";
  for (const dir of fs.existsSync(root) ? fs.readdirSync(root) : []) {
    if (!dir.startsWith("chromium")) continue;
    for (const rel of ["chrome-linux/chrome", "chrome"]) {
      const candidate = path.join(root, dir, rel);
      if (fs.existsSync(candidate)) return candidate;
    }
  }
  return wanted; // let playwright report the miss in its own words
}


const BASE = process.env.SBH_BASE ?? "http://127.0.0.1:4319";
const T = "brazosbend";
const SHOT = process.env.SBH_SHOTS ?? path.resolve("07-frontend/dist");

const DRAFT = {
  id: "park-9",
  flow: "move_in",
  subject_label: "500 Main St · Unit 12",
  subject_ref: { unit_id: "u-12", account_id: "acc-1" },
  step: 3,
  values: {
    unit_id: "u-12",
    opened_at: "2026-09-02",
    customer: {
      account_type: "residential",
      full_name: "Okafor, Joy",
      email: "joy@example.test",
      phone: "555-0142",
      dob: "",
      gov_id_last4: "",
      mailing_line1: "",
      mailing_city: "",
      mailing_state: "",
      mailing_postal_code: "",
    },
    preferences: {
      autopay: true,
      preferred_language: "",
      tax_exempt: false,
      tax_exempt_ref: "",
      tax_exempt_expires: "",
      custom_data: {},
    },
  },
  waiting_on: "deposit",
  park_note: "Waiting on the $150 deposit.",
  remind_on: "2026-09-02",
  parked_at: "2026-08-19T09:00:00Z",
  parked_by: "user-1",
  parked_by_name: "A. Clerk",
  age_days: 7,
};

const UNIT = {
  id: "u-12", unit_no: "Unit 12", premises_id: "p-1", premise_no: "P-1",
  premise_address: "500 Main St", label: "Unit 12", unit_type: "residential",
  floor_label: null, square_feet: null, rate_plan_id: null, plan_effective_from: null,
  plan_locked: false, vacant_standby_auto: false, is_common_area: false, active: true,
  services: ["electric"], meters: [], occupancy: "vacant", occupant: null,
  account_no: null, status: "vacant", sub_metered: false,
};
const CLOSED = {
  id: "acc-1", account_no: "AC-2026-00025", customer_no: "C-1", kind: "regular",
  name: "Prior, Tenant", unit_id: "u-12", unit_label: "Unit 12", premise: "500 Main St",
  services: ["electric"], balance: "0.0000", balance_currency: "USD", balance_basis: "posting",
  balance_source: "ledger", balance_unavailable: [], balance_cached: "0.0000", currency: "USD",
  status: "closed", status_name: "Closed", status_behavior_class: "terminal",
  account_type: "residential", account_subtype: null, autopay: false,
  opened_at: "2024-01-01", closed_at: "2026-08-14", last_bill_at: null, aging: null,
};
const DETAIL = {
  ...CLOSED, deposit_on_file: "0.0000", deposit_received_on: null, credit_tier: null,
  tax_exempt: false, tax_exempt_ref: null, tax_exempt_expires: null, bad_address: false,
  nsf_count: 0, preferred_language: null, custom_data: {}, contacts: [], addresses: [],
  service_agreements: [], meters: [], plan: null, plan_snapshot_unavailable: "BR-CUS-029",
  customer: null, unavailable: [],
};

const calls = [];
const ok = (b, s = 200) => ({ status: s, contentType: "application/json", body: b === null ? "" : JSON.stringify(b) });

function answer(url, method) {
  const u = new URL(url);
  const p = u.pathname;
  calls.push(`${method} ${p}${u.search}`);
  if (p.endsWith("/wizard-parks")) return ok({ count: 1, next: null, previous: null, results: [DRAFT] });
  if (p.includes("/wizard-parks/")) return ok(DRAFT);
  if (p.endsWith("/me/permissions")) return ok({ role: "system_admin", role_name: "System Admin", permissions: [{ code: "premises_accounts", label: "Premises / Accounts", access: "Full" }] });
  if (p.endsWith("/me")) return ok({ id: "user-1", full_name: "A. Clerk", email: "a@b.test", tenant: T });
  // ⚠ THE STUB HAS TO ANSWER THESE PROPERLY, AND FINDING OUT WHY IS ITSELF A
  // FINDING: answering `/units/{id}/assets` with a generic empty page crashed
  // the whole screen with `Cannot read properties of undefined (reading
  // 'total')` — `UnitAssetsPanel` reads `assets.counts.total` with no guard on
  // `counts` itself. Reported; it is another lane's file and not CR-035's.
  if (p.includes("/assets")) return ok({ unit: { id: "u-12", unit_no: "Unit 12", label: "Unit 12", premises_id: "p-1", premise_no: "P-1", premise_address: "500 Main St" }, groups: [], counts: { total: 0 }, reading_expected: { known: false, reason: "stub" } });
  if (p.includes("/pricing")) return ok(null, 404);
  if (p.endsWith("/units")) return ok({ count: 1, next: null, previous: null, results: [UNIT] });
  if (p.endsWith("/accounts")) return ok({ count: 1, next: null, previous: null, results: [CLOSED], rollup: { accounts: 1, outstanding: "0.0000", currency: "USD", outstanding_basis: "posting", outstanding_unavailable: [], past_due_60_plus: null } });
  if (p.includes("/accounts/")) return ok(DETAIL);
  return ok({ count: 0, next: null, previous: null, results: [] });
}

const checks = [];
const check = (n, pass, d = "") => { checks.push(pass); console.log(`${pass ? "PASS" : "FAIL"}  ${n}${d ? ` — ${d}` : ""}`); };

const browser = await chromium.launch({ executablePath: findChromium() });
const page = await browser.newPage({ viewport: { width: 1440, height: 1100 } });
await page.route("**/api/**", (r) => r.fulfill(answer(r.request().url(), r.request().method())));

// ⚠ **THE ADDRESS MOVED ON 2026-08-26 AND NOTHING ELSE IN THIS FILE DID —
// CR-035 · AMENDMENT 1.** The clerk no longer opens a ninth "Waiting on" tab;
// they open **Move-ins**, the tab for the work they were doing, and the parked
// draft is pinned above that list (PO: *"this will be directly on each request
// … seperate queue not reequired"*). Every assertion below the goto is the one
// it always was, which is the point: **only the presentation moved.** If any of
// them fails now, something that was not presentation was changed.
await page.goto(`${BASE}/${T}/accounts?tab=move-ins`, { waitUntil: "networkidle" });
// ⚠⚠ **THE DRAFT IS A ROW OF THE LIST SINCE 2026-09-20 (`DEF-CUS-5994`).** PO,
// verbatim: *"remove it - it is anyway in the list so we dont need it sepretely
// - if it is not in list add it"*. The paragraph above says *"only the
// presentation moved"* about the 2026-08-26 fold and it is true a second time:
// every assertion below the goto is the one it always was, read off the ROW
// instead of off the panel that used to sit over it.
const draftRow = page.locator("table tr", { has: page.locator("[data-parked-why]") }).first();
await draftRow.waitFor({ state: "visible", timeout: 15000 });
await page.waitForTimeout(1000);
const listText = await draftRow.innerText();
check("the parked MOVE-IN is a ROW of the MOVE-INS list, with its subject", listText.includes("500 Main St · Unit 12"), "");
// Requirement 1 — and it is unmistakably a DRAFT, not a move-in that happened.
check("it wears the DRAFT/PARKED badge (CR-035 amendment 1, requirement 1)",
  listText.includes("Draft") || listText.includes("Parked"));
// ⚠ **REQUIREMENT 2 INVERTED AND DID NOT GO AWAY.** The panel kept drafts out
// of the count; they are rows now, so the count must include them. The
// assertion is that the draft IS in the table and no panel is left above it.
check("the draft IS in the table and no panel is left above it",
  (await page.locator("table [data-parked-why]").count()) === 1 &&
    (await page.locator("[data-parked-drafts]").count()) === 0);
check("counted against the move-in's OWN steps (BR-SHL-046)", listText.includes("3 of "));
check("with the note and the reminder date", listText.includes("Waiting on the $150 deposit.") && listText.includes("09/02/2026"));
check("and the AGE, the server's own figure", listText.includes("days"));
await page.screenshot({ path: `${SHOT}/shot-7-moveIn-list.png` });

await page.getByRole("link", { name: "Resume" }).click();
await page.waitForURL(/parked=park-9/, { timeout: 15000 });
await page.locator('[data-wizard="rail"]').waitFor({ state: "visible", timeout: 15000 });
await page.waitForTimeout(1500);

check("the URL lands on the move-in wizard's own route", page.url().includes("/move-ins/new"), page.url());
check("and `?step=` was moved to the parked step", page.url().includes("step=3"), page.url());
const active = page.locator('[data-wizard-step][data-state="active"]').first();
check("step 3 is the ACTIVE step", (await active.getAttribute("data-wizard-step")) === "3");
check("step 5 is still LOCKED — resume unlocks nothing (BR-SHL-048 (b))", await page.locator('[data-wizard-step="5"]').isDisabled());
await page.screenshot({ path: `${SHOT}/shot-8-resume-step3.png` });

// Walk BACK to step 2 — the typing has to be there, or resume put nothing back.
await page.locator('[data-wizard-step="2"]').click();
await page.waitForTimeout(700);
const content = await page.locator('[data-wizard="content"]').innerText();
check("the customer's name is back in the form", content.includes("Okafor, Joy") || (await page.locator('input[value="Okafor, Joy"]').count()) > 0, content.slice(0, 120));
const nameInput = page.locator('input[value="Okafor, Joy"]');
check("it is in an INPUT, editable, not printed as read-only text", (await nameInput.count()) > 0);
const emailInput = page.locator('input[value="joy@example.test"]');
check("so is the email", (await emailInput.count()) > 0);
await page.screenshot({ path: `${SHOT}/shot-9-resume-step2-values.png` });

// The unit was re-asked, not trusted.
check("BR-SHL-048 (b): the product was RE-READ from the draft's copied unit id",
  calls.some((c) => c.includes("unit_id=u-12")), calls.filter((c) => c.includes("unit_id")).join(" · "));

await browser.close();
const failed = checks.filter((c) => !c).length;
console.log(`\n${checks.length - failed}/${checks.length} checks passed`);
process.exit(failed === 0 ? 0 : 1);
