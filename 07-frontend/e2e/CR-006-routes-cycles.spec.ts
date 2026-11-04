// ── Trace ──────────────────────────────────────────────
// Change:  CR-006 (12-governance/11-change-requests.md) — SET-05 Routes &
//          Cycles landing · SET-06 the four-step route wizard · SET-07 the
//          four-step cycle wizard. Recorded there as **BUILT, NOT CLOSED**:
//          *"Status: BUILT-NOT-PROVEN. Every part of r11 step 2 is done except
//          (d): there has been no browser walkthrough."*
// Story:   US-MET-006 (EP-MET-02) · Screens: S8 → Settings → Configure →
//          Routes & Cycles (r10 SET-05/06/07)
//          Route: /{tenant}/settings/reference-data/routes-cycles
// Rules:   BR-MET-008 (deactivate-first; delete locked while referenced) ·
//          BR-MET-009 (cycle delete lock) · BR-MET-010 (one cycle per route —
//          assigning MOVES it) · BR-MET-071/072 (premises carry an area; the
//          filter is one-to-many) · BR-MET-073 (route code from the series,
//          editable; service · area · notes) · BR-MET-074 (a premises on
//          another route MOVES, with confirm) · BR-MET-075 (a meter may be
//          excluded and stays on the premises) · BR-MET-076 (the Draft pill;
//          a draft affects nothing) · BR-MET-077 (day-of-month DEFAULTS, not
//          dates) · BR-MET-078 (NO money on this surface) · BR-MET-079 (reads
//          history refuses delete) · BR-MET-080 (the coverage query) ·
//          BR-MET-081 (an edit lands next read window) · BR-MET-035b (System
//          Admin only; everyone else read-only WITH the reason) · BR-SHL-020
//          (plain-language failure) · BR-SHL-025 (a control that cannot work
//          stays VISIBLE and DISABLED WITH ITS REASON) · BR-SHL-032 (the
//          confirm names the action)
// B14:     rules 4 · 5 · 6 · 8 · 9 · 12 · 13 · 14 · 15 · 16 · 17 · 18 · 20
// Defect:  DEF-217 · DEF-218 · DEF-219 · DEF-220 · DEF-221 · DEF-222 ·
//          DEF-223 · DEF-224 (all filed by this lane; see below) ·
//          **DEF-233 · DEF-234** (filed by the CLOSING walkthrough of the same
//          day, which re-ran this file after the fixes landed)
// ───────────────────────────────────────────────────────
//
// **THE PO'S BAR, VERBATIM, IS THE ONLY REASON THIS FILE EXISTS:**
// *"full CRUD working - from Ui scren not just backend"* and
// *"we need final confirmation it working on screen"*.
//
// CR-006's build record reports 26 new backend tests, a 650-passing metering +
// tenancy selection, `tsc` clean and 79 frontend tests green — and then says in
// its own words that none of that is the bar. On this project a walkthrough of
// six shipped, fully-tested reference lists found **five of them answering HTTP
// 500** with the whole suite passing (DEF-187), and CR-005's walkthrough found
// a PO ruling contradicted by the running product that 235 green tests could
// not see. So every assertion below is on RENDERED TEXT a person reads, never
// on a payload. The only API calls in this file are fenced into
// `ensureRoleUser` and labelled there.
//
// ── WHAT THIS WALKTHROUGH FOUND ────────────────────────────────────────────
//
// **The screens are real and most of the CR works.** Both landing tables draw
// with r10's columns and counts; the route wizard walks four steps and PUTS
// REAL PREMISES ON A ROUTE that survive a full page reload — which is the thing
// the shipped screen previously could not do at all; a meter can be excluded
// and the exclusion re-opens unticked; the cycle wizard walks four steps and
// its frequency and day-of-month defaults survive a reload; both delete guards
// refuse in readable English rather than 500ing; there is NO money anywhere on
// either wizard or the landing; and an Executive sees the whole surface
// READ-ONLY with every control visible, disabled and carrying its reason — so
// DEF-196's shape does NOT occur here.
//
// **But three findings stop the CR closing, and the first is a 500.**
//
//   · **DEF-217 — creating or editing a route whose premises carry reading
//     history answers HTTP 500 and saves nothing.** Measured: signing in as the
//     seeded System Admin, opening `+ Add route`, ticking `1408 Bluestem Ln`
//     (2 meters, 135 collected reads) and pressing `Create route ✓` produced
//     `POST /api/brazosbend/routes → 500` and the A18 §4 card *"Something went
//     wrong on our side. Nothing was saved."* `PATCH` on the seeded `Route 1`
//     did the same. The server log names it: `route_dict()["last_completion"]`
//     is a raw `datetime` from `meter_reads.read_at`, it goes into the audit
//     row's JSON payload, and psycopg raises
//     `TypeError: Object of type datetime is not JSON serializable`. The
//     selector predates CR-006 — but before CR-006 no screen could put a
//     premises on a route, so a new route never had reads and the payload was
//     always `None`. CR-006's headline feature is what makes it reachable, and
//     every real utility has reading history.
//   · **DEF-218 — the wizard pre-fills a route/cycle code it knows is taken.**
//     `create_route` draws from the numbering series only when the payload
//     carries NO code, and the wizard always sends the code it pre-filled. So
//     the counter never advances: the second route ever created from this
//     screen is offered `RT-001` again and refused *"A route with that code
//     already exists."* Same for `CY-001`. A utility can create exactly one
//     route and one cycle from these screens unless the admin knows to overtype
//     the field.
//   · **DEF-219 — a route saved as a DRAFT strips membership from an ACTIVE
//     route.** Measured: `Route 2 · Mason Rd`, active and on cycle 08-A, went
//     from `1 · 2 members / 3 meters` to `0 · 0 / 0` on the SET-05 landing
//     because a route saved as a Draft took its premises. The CR's own shared
//     rule is *"drafts don't affect Reads/Billing"* and the wizard's own copy
//     says *"Draft — not used by Reads or Billing yet"*.
//
// **And the PO's areas ruling is not delivered on any screen (DEF-220/221).**
// *"user can define their own areas and we wil tag them to premises ; in CR06
// you can use area and sub area for filtering"*. The filter is built and is
// multi-select with removable chips — and it can only ever return ZERO rows,
// because **no screen anywhere can tag a premises to an area** (`premises.
// area_id` shipped with no write path: the backend's own `_validate_premises`
// refuses `area_code`, and neither the S16 add-premises wizard nor the premises
// detail page draws the field), and **no screen can create a sub-area** (the
// backend accepts `parent_code` on `/lookups/areas`; the reference-data editor
// sends `{code, name, detail}` only). The wizard's `parent_name` rendering is
// dead UI in the hard-won-law-2 sense: nothing in the product can produce it.
//
// Three smaller findings (DEF-222/223/224) cover the commit button reading
// "Create route ✓" while EDITING, the B14 divergences measured on screen, and
// the copy — an ordinal-less preview (*"bills out the 5"* where r10 says
// *"bills out 5th"*) and no plural forms (*"1 routes selected"*).
//
// ── THE INVERSION CONTRACT — READ THIS BEFORE TRUSTING A GREEN RUN ─────────
//
// This spec was written against a build with those findings open, and this lane
// fixed none of them (QA reports; it does not fix product code). A spec that
// asserted the CORRECT behaviour would be red on the current build and would be
// skipped or deleted by the next person who saw it — which is how a finding
// evaporates. So every assertion that pins a defect is a `test.fail()` test
// whose body states the RULE, with a `FINDING` block quoting what the product
// does today. **The moment the product is fixed the run goes RED with "expected
// to fail but passed"**, which forces the annotation off and the defect row
// closed. `expect(broken).toBe(broken)` would have gone green forever.
//
// A green run of this file therefore means: *the screens work as described, and
// the findings still pinned below are still open.* It does NOT mean the surface
// is right.
//
// ── THE CLOSING WALKTHROUGH, 2026-08-17 — WHAT THE RE-RUN FOUND ────────────
//
// The eight findings above were re-driven after four of them were fixed.
// **Six inverted** and their annotations are gone, each with the fixing commit
// named at the test: DEF-217 (the 500), DEF-219 (fixed by REFUSAL), DEF-220 and
// DEF-221 (areas and sub-areas), DEF-222 (the edit verb) and the ordinal half of
// DEF-224. **Three findings stay pinned**: the rest of DEF-223 (three button
// sizes, two wizard tables with no pagination footer, the SET-07 picker with no
// toolbar) and the plural half of DEF-224.
//
// ⚠ **AND THE RE-RUN FOUND TWO NEW ONES, both of which a green test suite
// could not have found and one of which stops the CR closing:**
//
//   · **DEF-234 — DEF-218's fix routed the wizard onto a path that answers
//     HTTP 500.** The screen now correctly sends no code when the pre-fill is
//     untouched, and the server's own "an absent code means use the series"
//     branch calls `select_for_update` OUTSIDE a transaction. So a route or
//     cycle created the ordinary way — leave the suggested code alone, press
//     the button — is refused with *"Something went wrong on our side."*
//     **Django's `TestCase` wraps every test in a transaction, so no unit test
//     in this repo can see this class of bug.** 28 backend tests passed on the
//     fix that shipped it.
//   · **DEF-233 — the reads-history delete guard is bypassed by moving the
//     premises away first**, found because this file is run TWICE over the same
//     database: the second run deleted the seeded `Route 1`, which the first run
//     had watched the product refuse to delete.
//
// **Both of those needed a SECOND RUN and a REAL SERVER to exist at all**,
// which is the argument for this whole file in two sentences.
//
// ⚠ **THIS SPEC WRITES, AND ONLY TO A DISPOSABLE TENANT.** It creates
// run-unique routes (`QA-RT-…`) and cycles (`QA-CY-…`), moves premises between
// them, and moves `Route 5 · Gulf Fwy` onto the cycle it creates — that last
// one is deliberate and permanent, because the conflict badge cannot be proved
// without a route that is already on a cycle. It CANCELS every deactivation
// dialog rather than confirming it, and it confirms two deletes that are
// EXPECTED TO BE REFUSED (a route with reading history, a cycle with bills) so
// the refusal sentence can be read on screen — neither destroys anything. It
// creates ONE Executive user per run under a run-unique address. Point this at
// a disposable tenant and nothing else — the same posture, and the same
// warning, as CR-004-reference-crud.spec.ts.
import { expect, test } from "@playwright/test";
import type { Locator, Page } from "@playwright/test";

import { APP_SERVER_TAG } from "./support/census";
import {
  expectScreenInContentPane,
  signInEmail,
  signInPassword,
  signInPath,
  skipUnlessAppServer,
  tenant,
} from "./support/app";

skipUnlessAppServer(test);

// MEASURED, not guessed: `vite build` emits one 3.5 MB chunk and a cold load
// costs ~13 s in this sandbox. Every test here signs in and then walks a
// four-step wizard, so the 90 s file default is not the budget for one.
const WALK_BUDGET_MS = 300_000;

/** One stamp per worker process, so two runs never collide on a code. */
const STAMP = `${Date.now()}`.slice(-7);

// ── FIXTURE PREMISES · AMENDED 2026-08-18 ──────────────────────────────────
// ⚠ **THIS SPEC USED TO NAME PREMISES THAT NO SEEDER PLANTS, AND IT COST THREE
// FIVE-MINUTE TIMEOUTS BEFORE ANYONE KNEW WHY.**
//
// It reached for `500 Main St`, `Marina Bay` and `Oak Grove`. Those are JOURNEY
// fixture addresses — `08-qa/01-e2e/journeys/J07-first-bill-life.md` and its
// siblings — and `boot_stack.sh` reports **"50 journey(s) could not be seeded"**
// because no seeder is registered for them; it continues under
// `--tolerate-missing`. The original CR-006 walkthrough passed against the
// lane's OWN database (`sbh_e2e_cr006`), where they existed. Against the
// standard `sbh_e2e` they do not, and `locator.check` simply waited 300s for a
// checkbox that was never going to render.
//
// So the addresses are now the ones the SAMPLE PLANT actually seeds, and they
// are named ONCE here rather than sprinkled through the file. What each test
// needs is a premises WITH UNITS AND METERS — not a particular street — which
// is what the old `Oak Grove` comment already said it was standing in for.
//
// This is the same lesson the delete-guard test learned as DEF-233 and wrote
// down one screen below: *"a walkthrough that destroys its own preconditions is
// not re-runnable"*. Depending on preconditions nobody creates is the same
// fault arriving earlier.
const PREMISES_A = "101 Silver Creek Rd";
// ⚠ PREMISES_B IS DELIBERATELY A **TWO-UNIT** PREMISES, and that is load-bearing.
// Two assertions in this file read the summary's `premises · units` pair — "2 · 3"
// on the four-step wizard (A's one unit plus B's two) and "1 · 2" on the draft
// test (B alone). Those figures are the FIXTURE's, not the product's, so a
// one-unit substitute silently turned both into "2 · 2" and "1 · 1" and reported
// a counting bug that did not exist. Measured on the live database: of 47
// premises, 41 have a single unit and only four have two — `500 Mason Rd Plaza`
// is one of them and carries 4 service points and 2 meters, so it exercises the
// multi-unit path the summary line is there to show.
const PREMISES_B = "500 Mason Rd Plaza";
const PREMISES_C = "105 Cedar Ridge Way";

/** A premises that genuinely HAS collected reads, for BR-MET-079's delete guard.
 *
 *  ⚠ AMENDED 2026-08-18 for the same reason as the three above, and this one
 *  was the subtler failure: the spec used `1408 Bluestem Ln` and its comment
 *  said *"the one premises on this fixture that has 135 collected reads"*. On
 *  THIS stack that premises has **zero** — so the delete guard correctly did
 *  not fire, and the test reported *"the reads-history refusal never reached
 *  the screen"*, which reads like a product fault and was a fixture fact.
 *  Measured on the live database: `301 Mill Pond Ln` carries **348** reads,
 *  the most of any premises here. What the test needs is a premises WITH READ
 *  HISTORY, not a particular address. */
const PREMISES_WITH_READS = "301 Mill Pond Ln";

/** Fail in SECONDS with a sentence, instead of in five minutes with a timeout.
 *  A missing fixture is an environment fact, and an environment fact that
 *  presents as `locator.check: Test timeout` sends the reader to the product. */
async function requireFixturePremises(page: Page, ...names: string[]): Promise<void> {
  for (const name of names) {
    await expect(
      page.getByRole("checkbox", { name: `Put ${name} on this route` }),
      `FIXTURE: the premises "${name}" is not in the picker. This stack's sample ` +
        `plant did not seed it — check boot_stack.sh's seed step rather than the ` +
        `Routes & Cycles screen.`,
    ).toHaveCount(1, { timeout: 15_000 });
  }
}

function routesCyclesPath(): string {
  return `/${tenant()}/settings/reference-data/routes-cycles`;
}

// ── Locators, named for what a person sees ────────────────────────────────
const routesTable = (page: Page): Locator => page.locator("table.settings-table").first();
const cyclesTable = (page: Page): Locator => page.locator("table.settings-table").nth(1);
const routeRow = (page: Page, text: string): Locator =>
  routesTable(page).locator("tbody tr").filter({ hasText: text });
const cycleRow = (page: Page, text: string): Locator =>
  cyclesTable(page).locator("tbody tr").filter({ hasText: text });
const dialog = (page: Page): Locator => page.locator(".modal-card");
const wizardStep = (page: Page): Locator => page.locator(".wizard-step-content");

/** The `<input>` under a wizard field whose LABEL a person reads as `label`. */
function field(page: Page, label: string): Locator {
  return page.locator('[data-rcw="field"]').filter({ hasText: label }).locator("input").first();
}

function select(page: Page, label: string): Locator {
  return page.locator('[data-rcw="field"]').filter({ hasText: label }).locator("select").first();
}

/** The route-code box: the only `data-rcw="code"` input on step 1 of either wizard. */
const codeBox = (page: Page): Locator => page.locator('input[data-rcw="code"]').first();

/** Sign in through S3's own form — never by forging a cookie (PO 2026-08-11). */
async function signInAs(page: Page, email: string, password: string): Promise<void> {
  await page.context().clearCookies();
  await page.goto(signInPath());
  await page.locator("#signin-email").fill(email);
  await page.locator("#signin-password").fill(password);
  await page.locator("form button[type=submit]").first().click();
  await page.getByRole("navigation", { name: "Main navigation" }).waitFor({ timeout: 60_000 });
  await expectScreenInContentPane(page, `/${tenant()}/dashboard`);
}

const signInAsAdmin = (page: Page): Promise<void> =>
  signInAs(page, signInEmail(), signInPassword());

/**
 * Open SET-05 and prove it is the SCREEN, not a failure card and not the
 * permission refusal.
 *
 * ⚠ THE ORDER HERE IS THE ASSERTION. A bare `toHaveCount(0)` on the failure
 * card straight after a navigation passes INSTANTLY, because the two queries
 * are still in flight and nothing has rendered yet. So wait for the body to
 * SETTLE into one of its three possible states first, then say which two it
 * must not be.
 */
async function openRoutesCycles(page: Page): Promise<void> {
  await page.goto(routesCyclesPath());
  const failure = page.getByText("We couldn't load routes and cycles.");
  const denied = page.getByText("Your role can't open this Settings tab.");
  const table = routesTable(page);
  await expect(failure.or(denied).or(table).first()).toBeVisible({ timeout: 60_000 });
  await expect(
    failure,
    "the routes/cycles read answered an error and the frame rendered the failure card",
  ).toHaveCount(0);
  await expect(denied, "the routes/cycles read answered 403 and the tab refused").toHaveCount(0);
}

/**
 * Narrow the landing's ROUTES table with the same search box a person uses.
 *
 * ⚠ Added by the CLOSING walkthrough (2026-08-17) and it is not cosmetic: the
 * footer's default page size is 50, this spec creates roughly ten routes per
 * run and it is deliberately run WITHOUT resetting the database. A row lookup
 * that never searched would start passing and then quietly stop finding its own
 * route somewhere around the fifth consecutive run — a spec that rots on a
 * schedule nobody is watching.
 */
async function searchRoutes(page: Page, text: string): Promise<void> {
  await page.locator("input.settings-search").first().fill(text);
}

/** The same, for the CYCLES table's own search box. */
async function searchCycles(page: Page, text: string): Promise<void> {
  await page.locator("input.settings-search").nth(1).fill(text);
}

/** Press Continue and wait for the step rail to move on. */
async function continueStep(page: Page, expectStep: number): Promise<void> {
  await page.getByRole("button", { name: "Continue" }).click();
  await expect(
    page.locator(`.br-step[aria-current=step]`),
    `the wizard did not advance to step ${expectStep}`,
  ).toHaveText(new RegExp(`^${expectStep}`), { timeout: 30_000 });
}

/**
 * Walk the route wizard from the landing to a saved route, and return the code
 * it was saved under. Every step is DRIVEN, not posted.
 */
async function createRoute(
  page: Page,
  options: { code: string; name: string; premises: string[]; draft?: boolean },
): Promise<void> {
  await page.getByRole("button", { name: "+ Add route" }).first().click();
  await expect(page.getByText("Step 1 of 4 · Details")).toBeVisible({ timeout: 30_000 });
  await codeBox(page).fill(options.code);
  await field(page, "Name").fill(options.name);
  await continueStep(page, 2);

  await expect(page.getByText("Step 2 of 4 · Select premises")).toBeVisible({ timeout: 30_000 });
  for (const address of options.premises) {
    await page.getByRole("checkbox", { name: `Put ${address} on this route` }).check();
  }
  await continueStep(page, 3);
  await continueStep(page, 4);

  if (options.draft === true) {
    await page.getByRole("radio", { name: "Draft — not used by Reads or Billing yet" }).check();
  }
  const commit = page.getByRole("button", {
    name: options.draft === true ? "Save draft ✓" : "Create route ✓",
  });
  await commit.click();
  // A18 §4 replaces the action row on failure — so the honest wait is "either
  // the wizard closed or the failure card appeared", and then a claim about
  // which. A bare wait for the table would time out on the 500 and report a
  // timeout instead of naming the failure (DEF-129's lesson).
  const failed = page.getByText("The route could not be saved");
  await expect(failed.or(routesTable(page)).first()).toBeVisible({ timeout: 60_000 });
  await expect(
    failed,
    `saving route ${options.code} failed on screen — the wizard rendered "The route could not be saved"`,
  ).toHaveCount(0);
}

/**
 * PRE-FLIGHT, AND EXPLICITLY NOT PART OF THE PROOF — the only API calls in this
 * file, kept in one function so that is impossible to miss.
 *
 * The Executive walkthrough needs an Executive and the seed ships exactly one
 * user. Creating one from the Users & roles SCREEN would be the purer route and
 * it is not available: BR-IDN-022 hands back a temporary password and flags
 * `must_change_password`, and **the forced-change screen at `/change-password`
 * IS NOT BUILT** (DEF-200). So a browser-only path from "create user" to
 * "signed in as that user" does not exist today, and this walks the three API
 * calls a human would otherwise walk through a screen.
 */
async function ensureRoleUser(
  page: Page,
  role: string,
  email: string,
  password: string,
): Promise<void> {
  const base = `/api/${tenant()}`;
  const created = await page.request.post(`${base}/users`, {
    data: { full_name: `QA ${role} walkthrough`, email, role },
  });
  expect(
    created.ok(),
    `could not create the ${role} fixture user: HTTP ${created.status()} ${await created.text()}`,
  ).toBe(true);
  const { temp_password: temp } = (await created.json()) as { temp_password: string };
  const session = await page.request.post(`${base}/auth/session`, {
    data: { email, password: temp },
  });
  expect(session.ok(), "the fixture user could not sign in with its temporary password").toBe(true);
  const changed = await page.request.post(`${base}/me/password`, {
    data: {
      current_password: temp,
      new_password: password,
      confirm_password: password,
      sign_out_other_sessions: false,
    },
  });
  expect(changed.status(), "the forced password change did not take").toBe(204);
  await page.request.delete(`${base}/auth/session`).catch(() => undefined);
  await page.context().clearCookies();
}

// ═══════════════════════════════════════════════════════════════════════════
// 1 · SET-05 — THE LANDING DRAWS BOTH TABLES
// ═══════════════════════════════════════════════════════════════════════════
test(`CR-006 SET-05 · both tables render with r10's columns, counts and footers ${APP_SERVER_TAG}`, async ({
  page,
}) => {
  test.setTimeout(WALK_BUDGET_MS);
  await signInAsAdmin(page);
  await openRoutesCycles(page);

  // The two section kickers a person reads, and their ledes.
  await expect(page.getByText("Meter-reading groups. Members are the premises and units on the route.")).toBeVisible();
  await expect(page.getByText("When each group is read and billed.")).toBeVisible();

  // CR-006 verbatim for the routes table: *"Route ID | Name | Type | Members
  // (premises+units count) | Meters | Cycle assigned | Status | Actions"*.
  // SERVICE is the one column CR-006 did not name and BR-MET-073 added.
  await expect(routesTable(page).locator("thead th")).toHaveText([
    "Route",
    "Name",
    "Type",
    "Service",
    "Members",
    "Meters",
    "Cycle",
    "Status",
    "Actions",
  ]);

  // And for the cycles table. BILL DATE / DUE DATE are BILL DAY / DUE DAY here
  // because PO ruling three made them day-of-month DEFAULTS, not dates.
  await expect(cyclesTable(page).locator("thead th")).toHaveText([
    "Cycle",
    "Name",
    "Frequency",
    "Routes",
    "Read window",
    "Bill day",
    "Due day",
    "Accounts",
    "Status",
    "Actions",
  ]);

  // A real seeded row, read as a person reads it: `Route 1 · Katy Central` is
  // an AMI route with members, meters and a cycle.
  const row = routeRow(page, "Katy Central");
  await expect(row).toHaveCount(1);
  await expect(row).toContainText("AMI");
  await expect(row.locator(".pill").first()).toHaveText("Active");

  // B14 rule 16 — a pagination footer under EVERY list table. Two tables, two
  // footers, each naming its own total.
  const pagers = page.locator("main.view .table-pager");
  await expect(pagers).toHaveCount(2);
  await expect(pagers.first()).toContainText("Rows per page");
  await expect(pagers.first()).toContainText(/of \d+/);

  // B14 rule 4 — `+ Noun` opens a creator, one per table.
  await expect(page.getByRole("button", { name: "+ Add route" })).toHaveCount(1);
  await expect(page.getByRole("button", { name: "+ Add cycle" })).toHaveCount(1);

  // B14 rule 12 — [Search…] first in each toolbar, and it actually narrows.
  await page.locator("input.settings-search").first().fill("Mason");
  await expect(routesTable(page).locator("tbody tr")).toHaveCount(1);
  await expect(routesTable(page).locator("tbody tr")).toContainText("Mason Rd");
});

// ═══════════════════════════════════════════════════════════════════════════
// 2 · SET-06 — THE WHOLE POINT: PREMISES ONTO A ROUTE, THROUGH A RELOAD
// ═══════════════════════════════════════════════════════════════════════════
test(`CR-006 SET-06 · four steps put real premises on a route, and a reload still shows them ${APP_SERVER_TAG}`, async ({
  page,
}) => {
  test.setTimeout(WALK_BUDGET_MS);
  await signInAsAdmin(page);
  await openRoutesCycles(page);

  const code = `QA-RT-A-${STAMP}`;
  await page.getByRole("button", { name: "+ Add route" }).first().click();

  // ── Step 1 · Details ────────────────────────────────────────────────────
  await expect(page.getByText("Step 1 of 4 · Details")).toBeVisible({ timeout: 30_000 });
  await expect(page.getByText("Name the route.")).toBeVisible();
  // BR-MET-073: the code arrives PRE-FILLED from the numbering series and is
  // editable. Both halves are asserted — a blank box would be the CR-005 `JE-`
  // failure (a series with no row, shipping unnumbered records silently).
  await expect(codeBox(page), "the route code was not pre-filled from the series").toHaveValue(/\S/);
  await expect(page.getByText("Filled in from your numbering format.")).toBeVisible();
  await codeBox(page).fill(code);
  // B14 rule 10 — the asterisk is on the LABEL, and Continue is refused until
  // the required name is filled. Prove the refusal before filling it.
  await page.getByRole("button", { name: "Continue" }).click();
  await expect(
    page.getByText("Give the route a name so the reader knows which one it is."),
  ).toBeVisible({ timeout: 15_000 });
  await field(page, "Name").fill(`QA route A ${STAMP}`);
  // r10 SET-06.1's three read types, in its words.
  await expect(select(page, "Read type").locator("option")).toHaveText([
    "AMR — drive-by",
    "Network — AMI, no visit",
    "Walk — manual entry",
  ]);
  await continueStep(page, 2);

  // ── Step 2 · Select premises ────────────────────────────────────────────
  // ⚠ `getByRole("heading")` and not `getByText`: the picker table repeats the
  // step title in a visually-hidden `<caption>` for screen readers, so a text
  // match is a strict-mode violation on two legitimate elements.
  await expect(page.getByRole("heading", { name: "Who's on this route?" })).toBeVisible();
  // The picker lists premises with their unit and meter counts — SET-06 step 2
  // verbatim: *"Show per-premise unit and meter counts"*.
  await expect(page.locator('table[data-rcw="table"] thead th')).toHaveText([
    "",
    "Premise",
    "Address",
    "Type",
    "Units",
    "Meters",
    "Area · sub",
    "Current route",
  ]);
  await page.getByRole("checkbox", { name: `Put ${PREMISES_A} on this route` }).check();
  await page.getByRole("checkbox", { name: `Put ${PREMISES_B} on this route` }).check();
  // The live counter is what a person reads to know the selection took.
  await expect(page.locator('[data-rcw="count"]').first()).toContainText("2 selected");
  await continueStep(page, 3);

  // ── Step 3 · Meters ─────────────────────────────────────────────────────
  // `getByRole("heading")` again — the meter table repeats this title in its
  // visually-hidden `<caption>`, so `getByText` matches two elements.
  await expect(
    page.getByRole("heading", { name: "These meters come with your premises." }),
  ).toBeVisible();
  await expect(page.locator('[data-rcw="stats"]')).toContainText("Premises");
  await continueStep(page, 4);

  // ── Step 4 · Review & confirm ───────────────────────────────────────────
  await expect(page.getByText(`Ready to create ${code}.`)).toBeVisible();
  await expect(page.locator('[data-rcw="summary"]')).toContainText(code);
  // Members, read as the screen prints it: 2 premises · 3 units.
  await expect(page.locator('[data-rcw="summary"]')).toContainText("2 · 3");
  await expect(
    page.getByText("Every save here is recorded in the audit log"),
  ).toBeVisible();
  await page.getByRole("button", { name: "Create route ✓" }).click();

  const failed = page.getByText("The route could not be saved");
  await expect(failed.or(routesTable(page)).first()).toBeVisible({ timeout: 60_000 });
  await expect(failed, "the route wizard refused to save a route of unmetered premises").toHaveCount(0);

  // ── THE ASSERTION THIS WHOLE CR EXISTS FOR: a FULL PAGE RELOAD ──────────
  // Not a re-render, not a cache read — `page.goto` throws the SPA away and
  // asks the server again.
  await openRoutesCycles(page);
  const row = routeRow(page, code);
  await expect(row, `${code} is not on the landing after a full page reload`).toHaveCount(1);
  // "2 · 3" is the Members cell — 2 premises, 3 units — read off the screen.
  await expect(row, `${code} came back with no premises on it`).toContainText("2 · 3");
  await expect(row.locator(".pill").first()).toHaveText("Active");

  // …and re-opening the wizard shows the same two premises still ticked.
  await page.getByRole("button", { name: `Edit ${code}` }).click();
  await expect(page.getByText("Step 1 of 4 · Details")).toBeVisible({ timeout: 30_000 });
  await continueStep(page, 2);
  await expect(page.locator('[data-rcw="count"]').first()).toContainText("2 selected");
  await expect(page.getByRole("checkbox", { name: `Put ${PREMISES_A} on this route` })).toBeChecked();
});

// ═══════════════════════════════════════════════════════════════════════════
// 3 · SET-06 STEP 3 — A METER CAN BE LEFT OFF, AND THE EXCLUSION PERSISTS
// ═══════════════════════════════════════════════════════════════════════════
test(`CR-006 SET-06.3 · a meter is excluded, the count says "2 of 3", and the edit re-opens it unticked ${APP_SERVER_TAG}`, async ({
  page,
}) => {
  test.setTimeout(WALK_BUDGET_MS);
  await signInAsAdmin(page);
  await openRoutesCycles(page);

  const code = `QA-RT-M-${STAMP}`;
  await page.getByRole("button", { name: "+ Add route" }).first().click();
  await expect(page.getByText("Step 1 of 4 · Details")).toBeVisible({ timeout: 30_000 });
  await codeBox(page).fill(code);
  await field(page, "Name").fill(`QA route meters ${STAMP}`);
  await continueStep(page, 2);
  // `500 Mason Rd Plaza` carries three meters and no collected reads on this
  // fixture, so it is the one premises that exercises step 3 without tripping
  // DEF-217 below.
  await page.getByRole("checkbox", { name: "Put 500 Mason Rd Plaza on this route" }).check();
  await continueStep(page, 3);

  // BR-MET-075: BOTH halves of the count, so an exclusion is never invisible.
  await expect(page.locator('[data-rcw="stats"]')).toContainText("3");
  const meterTicks = page.locator('table[data-rcw="table"] tbody input[type=checkbox]');
  await expect(meterTicks).toHaveCount(3);
  const excludedLabel = await meterTicks.first().getAttribute("aria-label");
  await meterTicks.first().uncheck();
  await expect(page.locator('[data-rcw="stats"]'), "the meter count did not drop after unticking").toContainText("2");
  await expect(page.locator('[data-rcw="stats"]')).toContainText("of 3");
  await continueStep(page, 4);
  // Step 4 states the exclusion in words a person reads.
  await expect(page.locator('[data-rcw="summary"]')).toContainText("2 (1 left off)");
  await page.getByRole("button", { name: "Create route ✓" }).click();
  await expect(page.getByText("The route could not be saved").or(routesTable(page)).first()).toBeVisible({ timeout: 60_000 });
  await expect(page.getByText("The route could not be saved")).toHaveCount(0);

  // Reload, and the landing shows the route carrying 2 meters, not 3.
  await openRoutesCycles(page);
  const row = routeRow(page, code);
  await expect(row).toHaveCount(1);
  await expect(row, "the excluded meter is still being counted on the landing").toContainText("1 · 2");

  // Re-open and confirm the SAME meter comes back unticked.
  await page.getByRole("button", { name: `Edit ${code}` }).click();
  await expect(page.getByText("Step 1 of 4 · Details")).toBeVisible({ timeout: 30_000 });
  await continueStep(page, 2);
  await continueStep(page, 3);
  await expect(page.locator('[data-rcw="stats"]')).toContainText("of 3");
  await expect(
    page.getByRole("checkbox", { name: excludedLabel ?? "" }),
    "the excluded meter came back ticked — the exclusion did not persist",
  ).not.toBeChecked();
});

// ═══════════════════════════════════════════════════════════════════════════
// 4 · BR-MET-074 — A PREMISES MOVES, AND CANNOT SIT ON TWO ROUTES AT ONCE
// ═══════════════════════════════════════════════════════════════════════════
test(`CR-006 SET-06.2 · a premises already on a route is badged, moves with a stated consequence, and leaves the old route ${APP_SERVER_TAG}`, async ({
  page,
}) => {
  test.setTimeout(WALK_BUDGET_MS);
  await signInAsAdmin(page);
  await openRoutesCycles(page);

  // Build the route it will move OFF, so this test owns both ends of the move
  // and does not depend on another test having run first.
  const from = `QA-RT-F-${STAMP}`;
  const to = `QA-RT-T-${STAMP}`;
  await createRoute(page, { code: from, name: `QA from ${STAMP}`, premises: [PREMISES_C] });
  await openRoutesCycles(page);
  await expect(routeRow(page, from)).toContainText("1 · 1");

  await page.getByRole("button", { name: "+ Add route" }).first().click();
  await expect(page.getByText("Step 1 of 4 · Details")).toBeVisible({ timeout: 30_000 });
  await codeBox(page).fill(to);
  await field(page, "Name").fill(`QA to ${STAMP}`);
  await continueStep(page, 2);

  // BR-MET-074: the badge r10 draws — *"on SCW-R1"*.
  const oakRow = page.locator('table[data-rcw="table"] tbody tr').filter({ hasText: PREMISES_C });
  await expect(oakRow, `${PREMISES_C} is not badged as being on ${from}`).toContainText(`on ${from}`);
  await page.getByRole("checkbox", { name: `Put ${PREMISES_C} on this route` }).check();
  await continueStep(page, 3);
  await continueStep(page, 4);

  // B14 rule 11 — the consequence, in words, BEFORE the commit. r10 SET-06.4:
  // *"…move to this route — … No bills change; only who reads them."*
  await expect(page.locator('[data-rcw="consequence-move"]')).toContainText(`1 premises currently on ${from} move here`);
  await expect(page.locator('[data-rcw="consequence-move"]')).toContainText("No bills change; only who reads them.");
  await page.getByRole("button", { name: "Create route ✓" }).click();
  await expect(page.getByText("The route could not be saved").or(routesTable(page)).first()).toBeVisible({ timeout: 60_000 });
  await expect(page.getByText("The route could not be saved")).toHaveCount(0);

  // The invariant, read off the landing after a full reload: the premises is on
  // the new route and NOT on the old one.
  await openRoutesCycles(page);
  await expect(routeRow(page, to), "the moved premises did not land on the new route").toContainText("1 · 1");
  await expect(
    routeRow(page, from),
    "the old route still counts the premises — it is on two routes for one service",
  ).toContainText("0 · 0");
});

// ═══════════════════════════════════════════════════════════════════════════
// 5 · SET-07 — THE CYCLE WIZARD, ITS DEFAULTS, AND A RELOAD
// ═══════════════════════════════════════════════════════════════════════════
test(`CR-006 SET-07 · four steps create a cycle whose frequency and day-of-month defaults survive a reload ${APP_SERVER_TAG}`, async ({
  page,
}) => {
  test.setTimeout(WALK_BUDGET_MS);
  await signInAsAdmin(page);
  await openRoutesCycles(page);

  const code = `QA-CY-${STAMP}`;
  await page.getByRole("button", { name: "+ Add cycle" }).first().click();

  // ── Step 1 · Details, and PO RULING TWO in the lede a person reads ──────
  await expect(page.getByText("Step 1 of 4 · Details")).toBeVisible({ timeout: 30_000 });
  await expect(page.getByText("Name the cycle.")).toBeVisible();
  await expect(
    page.getByText(
      "A cycle is a group of routes — and through them, the premises, units and accounts billed together. You define the group here; the timing is confirmed when you actually run it.",
    ),
    "PO ruling 2026-08-16 (second) — 'a cycle is a DEFINITION, not a schedule' — is not stated to the user",
  ).toBeVisible();
  await expect(codeBox(page)).toHaveValue(/\S/);
  await codeBox(page).fill(code);
  await field(page, "Name").fill(`QA cycle ${STAMP}`);
  // r10 SET-07.1 draws exactly three frequencies.
  await expect(select(page, "Frequency").locator("option")).toHaveText([
    "Monthly",
    "Bi-monthly",
    "Quarterly",
  ]);
  await select(page, "Frequency").selectOption("quarterly");
  await continueStep(page, 2);

  // ── Step 2 · Select routes, and BR-MET-010's conflict badge ─────────────
  // `getByRole("heading")` for the same reason as SET-06 step 2 above: the
  // picker table repeats the title in a visually-hidden `<caption>`.
  await expect(page.getByRole("heading", { name: "Which routes bill on this cycle?" })).toBeVisible();
  await expect(
    page.getByText("A route belongs to one cycle — picking a route already on a cycle moves it here."),
  ).toBeVisible();
  // `Route 5 · Gulf Fwy` is already on a cycle, which is exactly what makes it
  // the row that proves the badge. It moves, permanently — see the file header.
  const gulf = page.locator('table[data-rcw="table"] tbody tr').filter({ hasText: "Gulf Fwy" });
  await expect(gulf.locator(".pill").first(), "Route 5 is on no cycle, so the conflict badge cannot be proved").toHaveText(/\S/);
  await page.getByRole("checkbox", { name: "Put route Route 5 on this cycle" }).check();
  await expect(page.locator('[data-rcw="consequence-move"]')).toContainText("already on another cycle");
  await expect(page.locator('[data-rcw="consequence-move"]')).toContainText("Nothing already billed changes.");
  await continueStep(page, 3);

  // ── Step 3 · Schedule — PO RULING THREE: DEFAULTS, not a commitment ─────
  await expect(page.getByText("When is it normally read, billed, and due?")).toBeVisible();
  await expect(
    page.getByText(
      "These are the days of the month this cycle usually runs on. They are defaults: every run starts from them and you can change them for that run without changing what is saved here.",
    ),
    "PO ruling 2026-08-16 (third) — the cycle CARRIES defaults the run may override — is not stated to the user",
  ).toBeVisible();

  // The day-order guards, each proved by breaking it and reading the refusal.
  await field(page, "Read window from").fill("5");
  await field(page, "Read window to").fill("3");
  await page.getByRole("button", { name: "Continue" }).click();
  await expect(page.getByText("The read window has to start on or before it ends.")).toBeVisible({ timeout: 15_000 });
  await field(page, "Read window from").fill("1");
  await field(page, "Read window to").fill("3");
  await field(page, "Bill day").fill("2");
  await page.getByRole("button", { name: "Continue" }).click();
  await expect(
    page.getByText("Bills go out after the read window closes, so the bill day cannot come first."),
  ).toBeVisible({ timeout: 15_000 });
  await field(page, "Bill day").fill("5");
  await field(page, "Due day").fill("26");

  // The preview strip — and BR-MET-078's absence, asserted STRUCTURALLY so
  // adding a fee clause back goes red.
  const preview = page.locator('[data-rcw="preview"]');
  await expect(preview).toContainText("Preview — a normal month");
  await expect(preview).toContainText("Read 1–3");
  // ✅ DEF-224 (ordinal half) FIXED in 506234b — the preview read *"bills out
  // the 5 · due the 26"* when this spec was written, and now reads r10's own
  // *"bills out 5th · due 26th"*. So the assertion is the CORRECT copy, and
  // the redundant "the" coming back goes red on both halves.
  await expect(preview).toContainText("due 26th");
  await expect(preview).toContainText("bills out 5th");
  await expect(preview, "the day of the month lost its ordinal again — r10 says 5th, not 'the 5'").not.toContainText(
    /the 5 |the 26/,
  );
  await expect(preview, "the late-fee clause is back on the preview — PO ruling one removed it").not.toContainText(/late|penalt|fee/i);
  await continueStep(page, 4);

  // ── Step 4 · Review & confirm ───────────────────────────────────────────
  await expect(page.getByText(`Ready to create ${code}.`)).toBeVisible();
  await expect(page.locator('[data-rcw="summary"]')).toContainText("Quarterly");
  await expect(page.locator('[data-rcw="summary"]')).toContainText("Read 1–3 · bill 5 · due 26");
  // r10 SET-07.4's footer, which is hard rule 4's promise in the CR's own words.
  await expect(
    page.getByText(
      "Accounts on these routes bill on this cycle from the first run — nothing already issued changes.",
    ),
  ).toBeVisible();
  await page.locator("input[type=date]").fill("2026-10-01");
  await page.getByRole("button", { name: "Create cycle ✓" }).click();
  const failed = page.getByText("The cycle could not be saved");
  await expect(failed.or(cyclesTable(page)).first()).toBeVisible({ timeout: 60_000 });
  await expect(failed).toHaveCount(0);

  // ── FULL PAGE RELOAD ────────────────────────────────────────────────────
  await openRoutesCycles(page);
  const row = cycleRow(page, code);
  await expect(row, `${code} is not on the landing after a full page reload`).toHaveCount(1);
  await expect(row, "the cycle's frequency did not persist").toContainText("Quarterly");
  await expect(row, "the day-of-month defaults did not persist").toContainText("1–3");
  await expect(row).toContainText("Route 5");
  // And the route moved onto it — read off the ROUTES table, not the cycle row.
  await expect(routeRow(page, "Gulf Fwy"), "Route 5 did not move onto the new cycle").toContainText(code);

  // An EDIT re-opens the stored defaults, and changing one persists.
  await page.getByRole("button", { name: `Edit ${code}` }).click();
  await expect(page.getByText("Step 1 of 4 · Details")).toBeVisible({ timeout: 30_000 });
  await field(page, "Name").fill(`QA cycle edited ${STAMP}`);
  await continueStep(page, 2);
  await continueStep(page, 3);
  await expect(field(page, "Read window from"), "the stored read-window default did not re-open").toHaveValue("1");
  await expect(field(page, "Bill day")).toHaveValue("5");
  await field(page, "Due day").fill("20");
  await continueStep(page, 4);
  // BR-MET-081 — an edit to an ACTIVE cycle says when it takes effect.
  await expect(
    page.getByText("This cycle is active, so your changes take effect at the next read window."),
  ).toBeVisible();
  await page.getByRole("button", { name: /^(Create cycle ✓|Save cycle ✓)$/ }).click();
  await expect(page.getByText("The cycle could not be saved").or(cyclesTable(page)).first()).toBeVisible({ timeout: 60_000 });
  await openRoutesCycles(page);
  await expect(cycleRow(page, code), "the edited due day did not persist").toContainText(`QA cycle edited ${STAMP}`);
});

// ═══════════════════════════════════════════════════════════════════════════
// 6 · PO RULING ONE — NO MONEY ANYWHERE ON THIS SURFACE
// ═══════════════════════════════════════════════════════════════════════════
test(`CR-006 · no money, no fee and no currency on the landing or either wizard ${APP_SERVER_TAG}`, async ({
  page,
}) => {
  test.setTimeout(WALK_BUDGET_MS);
  await signInAsAdmin(page);
  await openRoutesCycles(page);

  // PO verbatim, 2026-08-16: *"you dont need late fees in this. so dont have
  // anything related to money when you create route and cycles."* Swept over
  // RENDERED TEXT, so a fee that arrives through any catalogue, any locale or
  // any server string is caught — not just one that arrives through a field.
  const MONEY =
    /[$€£¥]|\bUSD\b|\bEUR\b|\bGBP\b|late\s*fee|penalt|currency|tariff|\bfee\b|\bprice\b|\brate\b|\bcharge[sd]?\b|\bamount\b/i;

  async function sweep(where: string): Promise<void> {
    const text = await page.locator("main.view").innerText();
    const hits = text.split("\n").filter((line) => MONEY.test(line));
    expect(hits, `money-shaped copy reached ${where}: ${JSON.stringify(hits)}`).toEqual([]);
  }

  await sweep("the SET-05 landing");

  await page.getByRole("button", { name: "+ Add route" }).first().click();
  await expect(page.getByText("Step 1 of 4 · Details")).toBeVisible({ timeout: 30_000 });
  await sweep("SET-06 step 1");
  await field(page, "Name").fill(`QA sweep ${STAMP}`);
  await continueStep(page, 2);
  await sweep("SET-06 step 2");
  await page.getByRole("checkbox", { name: `Put ${PREMISES_A} on this route` }).check();
  await continueStep(page, 3);
  await sweep("SET-06 step 3");
  await continueStep(page, 4);
  await sweep("SET-06 step 4");

  await openRoutesCycles(page);
  await page.getByRole("button", { name: "+ Add cycle" }).first().click();
  await expect(page.getByText("Step 1 of 4 · Details")).toBeVisible({ timeout: 30_000 });
  await sweep("SET-07 step 1");
  await field(page, "Name").fill(`QA sweep cycle ${STAMP}`);
  await continueStep(page, 2);
  await sweep("SET-07 step 2");
  await continueStep(page, 3);
  await sweep("SET-07 step 3");
  await field(page, "Read window from").fill("1");
  await field(page, "Read window to").fill("3");
  await field(page, "Bill day").fill("5");
  await field(page, "Due day").fill("26");
  await expect(page.locator('[data-rcw="preview"]')).toBeVisible();
  await sweep("SET-07 step 3 with the preview showing");
  await continueStep(page, 4);
  await sweep("SET-07 step 4");
});

// ═══════════════════════════════════════════════════════════════════════════
// 7 · PO RULING TWO — A CYCLE IS A DEFINITION, NOT A SCHEDULE
// ═══════════════════════════════════════════════════════════════════════════
test(`CR-006 · the cycle surface defines a grouping and schedules or runs nothing ${APP_SERVER_TAG}`, async ({
  page,
}) => {
  test.setTimeout(WALK_BUDGET_MS);
  await signInAsAdmin(page);
  await openRoutesCycles(page);

  // Nothing on the landing offers to run, schedule or start anything.
  const labels = await page.locator("main.view button").allInnerTexts();
  const runners = labels.filter((label) => /\brun\b|schedule now|start (the )?run|generate bills|bill run/i.test(label));
  expect(runners, `SET-05 offers a control that RUNS something: ${JSON.stringify(runners)}`).toEqual([]);

  await page.getByRole("button", { name: "+ Add cycle" }).first().click();
  await expect(page.getByText("Step 1 of 4 · Details")).toBeVisible({ timeout: 30_000 });
  // The four step names, read off the rail: Details · Select routes ·
  // Schedule · Review & confirm. "Schedule" survives as DEFAULTS (ruling
  // three), which is why the step exists at all.
  await expect(page.locator("nav.br-steps .br-step")).toHaveText([
    /Details$/,
    /Select routes$/,
    /Schedule$/,
    /Review & confirm$/,
  ]);
  await field(page, "Name").fill(`QA definition ${STAMP}`);
  await continueStep(page, 2);
  await continueStep(page, 3);
  // The three timing controls are DAY-OF-MONTH boxes hinted 1–31, never dates.
  for (const label of ["Read window from", "Read window to", "Bill day", "Due day"]) {
    await expect(field(page, label), `${label} is a date input, not a day-of-month box`).not.toHaveAttribute("type", "date");
  }
  await expect(page.locator('[data-rcw="hint"]').first()).toContainText("Day of the month, 1–31");
  const stepText = await wizardStep(page).innerText();
  expect(
    /\brun (it|now|this)\b|schedule now|start the run/i.test(stepText),
    "the Schedule step offers to RUN the cycle — it may only define defaults",
  ).toBe(false);
});

// ═══════════════════════════════════════════════════════════════════════════
// 8 · THE TWO DELETE GUARDS REFUSE IN ENGLISH, NOT WITH A 500
// ═══════════════════════════════════════════════════════════════════════════
test(`CR-006 · a route with reading history and a cycle with bills both refuse deletion readably ${APP_SERVER_TAG}`, async ({
  page,
}) => {
  test.setTimeout(WALK_BUDGET_MS);
  await signInAsAdmin(page);
  await openRoutesCycles(page);

  // BR-MET-079. `1408 Bluestem Ln` is the one premises on this fixture that has
  // been read — 135 collected reads — so a route carrying it is a route with
  // reading history.
  //
  // ⚠ THIS BUILDS ITS OWN ROUTE AND NO LONGER POINTS AT THE SEEDED `Route 1`,
  // and the reason is a defect this walkthrough found the hard way: on the
  // second consecutive run the seeded `Route 1` WAS GONE, because the DEF-217
  // test further down had moved `1408 Bluestem Ln` onto a route of its own and
  // that left `Route 1` deletable — so this test deleted the fixture's own
  // route and then two later tests failed looking for it. Filed as DEF-233.
  // A walkthrough that destroys its own preconditions is not re-runnable, which
  // is the property the "run it again without resetting" instruction exists to
  // protect, so this test now owns both ends.
  const guarded = `QA-RT-DEL-${STAMP}`;
  await createRoute(page, {
    code: guarded,
    name: `QA delete guard ${STAMP}`,
    premises: [PREMISES_WITH_READS],
  });
  await openRoutesCycles(page);
  await searchRoutes(page, guarded);
  await routeRow(page, guarded).getByRole("button", { name: "Delete" }).click();
  // BR-SHL-032 — the confirm NAMES the action, never "OK".
  await expect(dialog(page)).toContainText(`Delete route ${guarded}?`);
  await expect(dialog(page).getByRole("button", { name: `Delete ${guarded}` })).toBeVisible();
  await dialog(page).getByRole("button", { name: `Delete ${guarded}` }).click();

  await expect(page.getByText(/reads were collected on this route/i), "the reads-history refusal never reached the screen").toBeVisible({ timeout: 30_000 });
  const routeRefusal = await page.locator("main.view").innerText();
  expect(routeRefusal, "the refusal does not tell the user what to do instead").toContain("Deactivate it instead");
  expect(routeRefusal, "the refusal does not name how many reads are at stake").toMatch(/\d[\d,]* reads were collected/);
  // Not a 500, and the row is still there.
  expect(routeRefusal).not.toContain("Something went wrong on our side");
  await searchRoutes(page, guarded);
  await expect(routeRow(page, guarded)).toHaveCount(1);

  // BR-MET-009 — the cycle half of the same rule.
  await openRoutesCycles(page);
  await cycleRow(page, "08-A").getByRole("button", { name: "Delete" }).click();
  await expect(dialog(page)).toContainText("Delete cycle 08-A?");
  await dialog(page).getByRole("button", { name: "Delete 08-A" }).click();
  await expect(
    page.getByText(/Reads or bills already reference this cycle/i),
    "the cycle delete guard never reached the screen",
  ).toBeVisible({ timeout: 30_000 });
  await expect(cycleRow(page, "08-A")).toHaveCount(1);
});

// ═══════════════════════════════════════════════════════════════════════════
// 9 · DEACTIVATION WARNS, NAMING THE CYCLE AND THE PREMISES COUNT
// ═══════════════════════════════════════════════════════════════════════════
test(`CR-006 SET-05 · deactivating a route inside a cycle names the cycle and what will be skipped ${APP_SERVER_TAG}`, async ({
  page,
}) => {
  test.setTimeout(WALK_BUDGET_MS);
  await signInAsAdmin(page);
  await openRoutesCycles(page);

  // CR-006 verbatim: *"Deactivating a route in an active cycle → warning:
  // 'Route SCW-R2 is in cycle SCW-M — reads scheduled Sep 1–5 will skip 388
  // premises.'"* `Route 3 · Cane Island` sits on cycle 08-A on this fixture.
  await routeRow(page, "Cane Island").getByRole("button", { name: "Deactivate" }).click();
  await expect(dialog(page)).toContainText("Deactivate route Route 3?");
  const warning = await dialog(page).innerText();
  expect(warning, "the deactivation warning does not name the cycle").toContain("is in cycle 08-A");
  expect(warning, "the deactivation warning does not say what will be skipped").toMatch(/will skip \d+ premises/);
  // CANCEL — this walkthrough never deactivates a seeded route.
  await dialog(page).getByRole("button", { name: "Cancel" }).click();
  await expect(dialog(page)).toHaveCount(0);
  await expect(routeRow(page, "Cane Island").locator(".pill").first()).toHaveText("Active");
});

// ═══════════════════════════════════════════════════════════════════════════
// 10 · PERMISSIONS — BR-MET-035b + BR-SHL-025, MEASURED ON A REAL EXECUTIVE
// ═══════════════════════════════════════════════════════════════════════════
test(`CR-006 · an Executive sees the whole surface READ-ONLY, with the reason on every control ${APP_SERVER_TAG}`, async ({
  page,
}) => {
  test.setTimeout(WALK_BUDGET_MS);
  const email = `qa.cr006.exec.${STAMP}@brazosbendutilities.com`;
  const password = "Exec!passw0rd9";
  await signInAsAdmin(page);
  await ensureRoleUser(page, "executive", email, password);
  await signInAs(page, email, password);
  await openRoutesCycles(page);

  // PO ruling 2026-08-16: *"Billing Clerk and Executive can LOOK at numbering
  // formats, routes, cycles and templates; they cannot change them."* And
  // BR-SHL-025: the control stays VISIBLE and DISABLED WITH ITS REASON.
  await expect(routesTable(page).locator("tbody tr").first(), "an Executive cannot even see the routes").toBeVisible();
  await expect(cyclesTable(page).locator("tbody tr").first()).toBeVisible();

  for (const label of ["+ Add route", "+ Add cycle"]) {
    const button = page.getByRole("button", { name: label }).first();
    await expect(button, `${label} is HIDDEN from an Executive — BR-SHL-025 forbids hiding it`).toBeVisible();
    await expect(button, `${label} is still clickable for an Executive`).toBeDisabled();
    await expect(button, `${label} carries no reason for being disabled`).toHaveAttribute(
      "title",
      "Your role can view this, but not change it.",
    );
  }
  // ⚠ The FIRST row's own ✎, read off the table, rather than the seeded
  // `Route 1` by name — DEF-233 showed that a seeded row can be gone by the
  // second consecutive run, and a permission claim that depends on one
  // particular fixture row is a claim that expires.
  const firstRouteCode = (
    await routesTable(page).locator("tbody tr").first().locator("td").first().innerText()
  ).trim();
  const edit = page.getByRole("button", { name: `Edit ${firstRouteCode}` });
  await expect(edit, `no ✎ for the first route on the landing (${firstRouteCode})`).toBeVisible();
  await expect(edit).toBeDisabled();
  await expect(edit).toHaveAttribute("title", "Your role can view this, but not change it.");
});

// ═══════════════════════════════════════════════════════════════════════════
// 11 · B14 — THE RULES THIS SURFACE MEETS
// ═══════════════════════════════════════════════════════════════════════════
test(`CR-006 B14 · icon row actions, danger tier, 80% descriptions and empty states that name the way out ${APP_SERVER_TAG}`, async ({
  page,
}) => {
  test.setTimeout(WALK_BUDGET_MS);
  await signInAsAdmin(page);
  await openRoutesCycles(page);

  // Rule 15 — row actions are ICONS with tooltips, never text links. Measured:
  // every row-action button holds an <svg> and no text.
  const actions = routesTable(page).locator("tbody tr").first().locator(".settings-row-actions button");
  await expect(actions).toHaveCount(3);
  for (let index = 0; index < 3; index += 1) {
    const button = actions.nth(index);
    await expect(button.locator("svg"), "a row action is not an icon").toHaveCount(1);
    expect((await button.innerText()).trim(), "a row action renders text, not an icon").toBe("");
    await expect(button, "a row-action icon carries no tooltip").toHaveAttribute("title", /\S/);
    await expect(button, "a row-action icon carries no accessible name").toHaveAttribute("aria-label", /\S/);
  }

  // Rule 6 — a destructive commit uses the DANGER tier, never the primary.
  await expect(actions.nth(2)).toHaveClass(/settings-danger/);

  // Rule 18 — descriptions cap at 80% of the content width, through the token.
  const measure = await page.locator(".settings-lede").first().evaluate((node) => getComputedStyle(node).maxWidth);
  expect(measure, "the lede is not capped at the B14 r10-amended 80% measure").toBe("80%");

  // Rule 17 — the empty state names what is missing AND the action that fills
  // it. Driven by searching for something that matches nothing, and asserted
  // INSIDE the empty cell (DEF-214: the page header carries the same label, so
  // a whole-document check could not fail).
  await page.locator("input.settings-search").first().fill("zzz-no-such-route-zzz");
  const empty = routesTable(page).locator("td.settings-empty");
  await expect(empty).toHaveCount(1);
  await expect(empty).toContainText("No routes yet");
  await expect(empty.getByRole("button", { name: "+ Add route" }), "the empty state offers no way out").toHaveCount(1);
});

// ═══════════════════════════════════════════════════════════════════════════
// 12 · DEF-217 — THE 500. THE HEADLINE FEATURE, ON A ROUTE WITH READS.
// ═══════════════════════════════════════════════════════════════════════════
test(`CR-006 · a route whose premises carry reading history saves from the screen ${APP_SERVER_TAG}`, async ({
  page,
}) => {
  test.setTimeout(WALK_BUDGET_MS);
  // FINDING (DEF-217) — WHAT THE PRODUCT DOES TODAY:
  //   Ticking `1408 Bluestem Ln` (2 meters, 135 collected reads on this
  //   fixture) and pressing `Create route ✓` produces
  //   `POST /api/{tenant}/routes → HTTP 500` and the A18 §4 card *"Something
  //   went wrong on our side. Nothing was saved."* `PATCH` on the seeded
  //   `Route 1` behaves identically, so EDIT is broken for the same routes.
  //   The server log names it: `route_dict()["last_completion"]` is a raw
  //   `datetime` taken from `meter_reads.read_at`, it is written into the
  //   audit row's JSON payload by `_audit(... after={**route_dict(row), ...})`,
  //   and psycopg raises `TypeError: Object of type datetime is not JSON
  //   serializable`. The selector predates CR-006; before CR-006 no screen
  //   could put a premises on a route, so `last_completion` was always None
  //   and the bug was unreachable.
  // WHAT IT MUST DO: save the route, exactly as it does for premises with no
  //   reads — every real utility has reading history, and this is the CR's
  //   whole feature.
  //
  // ✅ FIXED in commit 02f1233 (2026-08-17) — `route_dict()["last_completion"]`
  // is serialised before it reaches the audit payload. `test.fail()` was LIFTED
  // by the closing walkthrough on 2026-08-17 after this test reported
  // *"Expected to fail, but passed"*, which is the inversion contract at the top
  // of this file doing exactly what it was built to do. The assertion below is
  // now the RULE: putting a read premises on a route saves from the screen.
  await signInAsAdmin(page);
  await openRoutesCycles(page);
  const withReads = `QA-RT-R-${STAMP}`;
  await createRoute(page, {
    code: withReads,
    name: `QA reads ${STAMP}`,
    premises: [PREMISES_WITH_READS],
  });

  // THE OTHER HALF OF THE SAME DEFECT, and it is the half a utility meets
  // first: DEF-217 also broke the EDIT of a route that has ALREADY collected
  // reads — `PATCH` on the seeded `Route 1` answered 500 on an ordinary rename.
  // Editing and re-saving with nothing changed is enough to reach the audit
  // write that used to fail. The route EDITED is the one just created, which is
  // now the one holding the 135 reads — self-owned, so this claim does not
  // depend on a seeded row still existing (DEF-233).
  await openRoutesCycles(page);
  await searchRoutes(page, withReads);
  await page.getByRole("button", { name: `Edit ${withReads}` }).click();
  await expect(page.getByText("Step 1 of 4 · Details")).toBeVisible({ timeout: 30_000 });
  await continueStep(page, 2);
  await continueStep(page, 3);
  await continueStep(page, 4);
  await page.locator(".wizard-actions button").last().click();
  const editFailed = page.getByText("The route could not be saved");
  await expect(editFailed.or(routesTable(page)).first()).toBeVisible({ timeout: 60_000 });
  await expect(
    editFailed,
    "re-saving the seeded Route 1 — which has 135 collected reads — failed on screen",
  ).toHaveCount(0);
});

// ═══════════════════════════════════════════════════════════════════════════
// 13 · DEF-218 — THE PRE-FILLED CODE IS ONE THAT IS ALREADY TAKEN
// ═══════════════════════════════════════════════════════════════════════════
test(`CR-006 SET-06.1 · a SECOND route and a SECOND cycle can be created from the screen ${APP_SERVER_TAG}`, async ({
  page,
}) => {
  test.setTimeout(WALK_BUDGET_MS);
  // FINDING (DEF-218) — WHAT THE PRODUCT DID:
  //   `create_route` draws a number from the `route` series ONLY when the
  //   payload carries no code, and the wizard always sends the code it
  //   pre-filled. So the counter never advances. Measured: on a freshly seeded
  //   tenant the first route created from the wizard takes `RT-001`; the next
  //   time `+ Add route` is opened the box says `RT-001` again, and pressing
  //   `Create route ✓` is refused *"A route with that code already exists."*
  //   `+ Add cycle` offers `CY-001` the same way. A utility can create exactly
  //   ONE route and ONE cycle from these screens unless the admin knows to
  //   overtype the field.
  // WHAT IT MUST DO: offer a code that is free — either by advancing the series
  //   on allocation, or by having the wizard send no code and let the server
  //   allocate.
  //
  // ✅ FIXED in commit 095f198 (2026-08-17), the SECOND of those two: an
  // UNTOUCHED pre-fill is now omitted from the payload, so the server's series
  // allocates and advances. Only a code the admin actually typed is sent, which
  // keeps the duplicate refusal for a human's own code — a real and useful
  // error. `test.fail()` LIFTED by the closing walkthrough, 2026-08-17.
  //
  // ⚠ AND THE CLAIM IS REWRITTEN, DELIBERATELY, because the old one no longer
  // measures the thing that was broken. The old body asked *"is the pre-filled
  // string free?"* — a question about a PREVIEW, which is now what that string
  // is: `GET next-code` shows what the series WOULD issue and allocates
  // nothing, so on a tenant where somebody has typed `RT-001` by hand the
  // preview can legitimately show a taken code and the save still works.
  // What the PO's bar actually asks is *"can a utility create more than one"*,
  // so that is what this now drives, on BOTH wizards, WITHOUT TOUCHING THE CODE
  // BOX — which is the exact path a real admin walks and the one that failed.
  //
  // ⛔ AND IT DOES NOT PASS, SO IT IS PINNED AGAIN. NEW FINDING (DEF-234):
  //
  //   **DEF-218's fix routed the wizard onto a path that answers HTTP 500.**
  //   The screen now correctly sends NO code when the pre-fill is untouched —
  //   and the server's own "an absent code means use the series" branch
  //   crashes. MEASURED, from this run's own server log:
  //     POST /api/brazosbend/routes -> 500
  //     apps/metering/services.py:1466 create_route
  //       -> _allocate_number(ROUTE_SERIES)
  //       -> apps/tenancy/services.py:3391 allocate_series_number
  //       -> TransactionManagementError: select_for_update cannot be used
  //          outside of a transaction
  //   `_allocate_number` is called BEFORE the `with transaction.atomic():`
  //   that follows it — in `create_route` (line 1466) and in `create_cycle`
  //   (line 2326) alike — and the series lock needs a transaction.
  //   `ATOMIC_REQUESTS` is set nowhere in `config/`, so this fails in every
  //   environment.
  //
  //   The very next POST in the same run, carrying a code the test had TYPED,
  //   answered 201. So the shape is exact: **type a code and it saves; leave
  //   the wizard's own suggestion alone and it 500s.** DEF-218 said a utility
  //   could create exactly ONE route from this screen; today it can create
  //   NONE without overtyping the box.
  //
  //   Why 28 green backend tests did not see it: Django's `TestCase` wraps
  //   every test in a transaction, so `select_for_update` is legal there and
  //   illegal in the running server. No unit test anywhere can catch this
  //   class of bug — only a request against a real server, which is what this
  //   file is.
  //
  // ✅ **`test.fail()` LIFTED 2026-08-18 — THE WALKTHROUGH REPORTED "Expected to
  // fail, but passed", WHICH IS THIS PIN DOING ITS JOB.** DEF-218's fix landed
  // in the CR-006 blocker pass of 2026-08-17 (`RoutesCyclesWizards.tsx` stops
  // sending an untouched pre-fill, at both wizard call sites, with the PO's
  // ruling quoted), and the register row had still read `open` with no fix
  // commit until it was corrected the same day against the code.
  //
  // The pin is REMOVED rather than left inverted, because a `test.fail()` that
  // passes is reported as a FAILURE and would keep this file red forever over a
  // defect that is fixed. The analysis above is kept in full: it is the only
  // written record of WHY 28 green backend tests could not see it — Django's
  // TestCase wraps every test in a transaction, so `select_for_update` is legal
  // there and illegal in the running server.
  await signInAsAdmin(page);
  await openRoutesCycles(page);

  // ── Two routes, back to back, each with the code box left exactly as the
  //    wizard filled it ─────────────────────────────────────────────────────
  const routeNames = [`QA series A ${STAMP}`, `QA series B ${STAMP}`];
  const routeCodes: string[] = [];
  for (const routeName of routeNames) {
    await openRoutesCycles(page);
    await page.getByRole("button", { name: "+ Add route" }).first().click();
    await expect(page.getByText("Step 1 of 4 · Details")).toBeVisible({ timeout: 30_000 });
    // The pre-fill is READ and left alone — never filled, not even with the
    // same value, because "untouched" is the state under test.
    routeCodes.push((await codeBox(page).inputValue()).trim());
    await field(page, "Name").fill(routeName);
    await continueStep(page, 2);
    await continueStep(page, 3);
    await continueStep(page, 4);
    await page.getByRole("button", { name: "Create route ✓" }).click();
    const failed = page.getByText("The route could not be saved");
    await expect(failed.or(routesTable(page)).first()).toBeVisible({ timeout: 60_000 });
    await expect(
      failed,
      `"${routeName}" could not be saved — this is the second route the screen was asked for, and DEF-218 is exactly the wizard refusing it`,
    ).toHaveCount(0);
  }

  // Both are on the landing, and they do NOT share a code.
  await openRoutesCycles(page);
  const savedRouteCodes: string[] = [];
  for (const routeName of routeNames) {
    await searchRoutes(page, routeName);
    await expect(
      routeRow(page, routeName),
      `${routeName} is not on the landing, so the screen created fewer routes than it was asked for`,
    ).toHaveCount(1);
    savedRouteCodes.push(await routeRow(page, routeName).locator("td").first().innerText());
  }
  expect(
    savedRouteCodes[0].trim(),
    `both routes were saved under "${savedRouteCodes[0].trim()}" — the series never advanced (previews offered: ${routeCodes.join(", ")})`,
  ).not.toBe(savedRouteCodes[1].trim());

  // ── And two cycles, the same way — DEF-218 hit `CY-` identically ─────────
  const cycleNames = [`QA series cycle A ${STAMP}`, `QA series cycle B ${STAMP}`];
  for (const cycleName of cycleNames) {
    await openRoutesCycles(page);
    await page.getByRole("button", { name: "+ Add cycle" }).first().click();
    await expect(page.getByText("Step 1 of 4 · Details")).toBeVisible({ timeout: 30_000 });
    await field(page, "Name").fill(cycleName);
    await continueStep(page, 2);
    await continueStep(page, 3);
    await field(page, "Read window from").fill("1");
    await field(page, "Read window to").fill("3");
    await field(page, "Bill day").fill("5");
    await field(page, "Due day").fill("26");
    await continueStep(page, 4);
    await page.getByRole("button", { name: "Create cycle ✓" }).click();
    const failed = page.getByText("The cycle could not be saved");
    await expect(failed.or(cyclesTable(page)).first()).toBeVisible({ timeout: 60_000 });
    await expect(
      failed,
      `"${cycleName}" could not be saved — a utility that can create exactly one cycle cannot bill in two groups`,
    ).toHaveCount(0);
  }

  await openRoutesCycles(page);
  const savedCycleCodes: string[] = [];
  for (const cycleName of cycleNames) {
    await searchCycles(page, cycleName);
    await expect(cycleRow(page, cycleName), `${cycleName} is not on the landing`).toHaveCount(1);
    savedCycleCodes.push(await cycleRow(page, cycleName).locator("td").first().innerText());
  }
  expect(
    savedCycleCodes[0].trim(),
    `both cycles were saved under "${savedCycleCodes[0].trim()}"`,
  ).not.toBe(savedCycleCodes[1].trim());
});

// ═══════════════════════════════════════════════════════════════════════════
// 14 · DEF-219 — A DRAFT EMPTIES AN ACTIVE ROUTE
// ═══════════════════════════════════════════════════════════════════════════
test(`CR-006 · a route saved as a DRAFT leaves an active route's members alone ${APP_SERVER_TAG}`, async ({
  page,
}) => {
  test.setTimeout(WALK_BUDGET_MS);
  // FINDING (DEF-219) — WHAT THE PRODUCT DOES TODAY:
  //   Measured on the seeded fixture: `Route 2 · Mason Rd`, ACTIVE and on cycle
  //   08-A, read `1 · 2 members / 3 meters` on SET-05. A new route was built
  //   over the same premises and saved with `Save draft ✓`. Route 2 then read
  //   `0 · 0 / 0` on the landing while still Active and still listed inside
  //   08-A. The draft's own row read `1 · 2 / 2`.
  //   CR-006's shared rule is *"Draft state visible in tables with 'Draft'
  //   pill; drafts don't affect Reads/Billing"*, the wizard's own radio says
  //   *"Draft — not used by Reads or Billing yet"*, and the tab's docstring
  //   claims *"a draft stamps no service point, so Reads and Billing cannot see
  //   it"* — which is true of SERVICE POINTS and not of MEMBERSHIP, and
  //   membership is what the Members column counts.
  // WHAT IT MUST DO: a draft takes nothing away from an active route until it
  //   is activated. The number a utility reads for an active route must not be
  //   changed by something that has never run.
  //
  // ✅ FIXED in commit 095f198 (2026-08-17), by REFUSAL — PO ruling 2026-08-17,
  // option (i) of the three put to them: *"a draft may not take a premises off
  // an active route — refuse, and name the route"*. So the assertion below is
  // no longer "the numbers are unchanged after the save"; it is "the save is
  // refused in English, it NAMES the route the premises is on, and nothing is
  // written". `test.fail()` LIFTED by the closing walkthrough, 2026-08-17.
  //
  // ⚠ AND THIS ONE COULD NOT HAVE BEEN INVERTED BY WATCHING THE RUN GO RED.
  // The old body drove `createRoute(..., draft: true)`, which ASSERTS THE SAVE
  // SUCCEEDS. Once the fix landed the save was refused, so the body still
  // failed, so `test.fail()` still reported PASS — a fixed defect wearing a
  // green tick. The inversion contract at the top of this file catches a fix
  // that makes a broken path work; it cannot catch a fix that replaces the path
  // with a refusal. Read the fix, not only the colour.
  await signInAsAdmin(page);
  await openRoutesCycles(page);

  // Own both ends: build the ACTIVE route first, then the draft that raids it.
  const active = `QA-RT-ACT-${STAMP}`;
  const activeName = `QA active ${STAMP}`;
  const draft = `QA-RT-DFT-${STAMP}`;
  await createRoute(page, { code: active, name: activeName, premises: [PREMISES_B] });
  await openRoutesCycles(page);
  await searchRoutes(page, active);
  await expect(routeRow(page, active)).toContainText("1 · 2");

  // The draft is walked BY HAND rather than through `createRoute`, because the
  // expected outcome is a refusal and that helper asserts a save.
  await openRoutesCycles(page);
  await page.getByRole("button", { name: "+ Add route" }).first().click();
  await expect(page.getByText("Step 1 of 4 · Details")).toBeVisible({ timeout: 30_000 });
  await codeBox(page).fill(draft);
  await field(page, "Name").fill(`QA draft ${STAMP}`);
  await continueStep(page, 2);
  await page.getByRole("checkbox", { name: `Put ${PREMISES_B} on this route` }).check();
  await continueStep(page, 3);
  await continueStep(page, 4);
  await page.getByRole("radio", { name: "Draft — not used by Reads or Billing yet" }).check();
  await page.getByRole("button", { name: "Save draft ✓" }).click();

  // BR-SHL-020 — the refusal is a sentence, and BR-MET-074's ruling says it
  // must NAME the route, because "that premises is taken" leaves an admin with
  // nowhere to go.
  await expect(
    page.getByText("The route could not be saved"),
    "the draft that used to empty an active route was accepted",
  ).toBeVisible({ timeout: 60_000 });
  const refusal = page.locator('[data-rcw="error"]').last();
  await expect(refusal).toContainText("A draft route cannot take premises");
  await expect(
    refusal,
    `the refusal does not name the route the premises is on — it must say "${active} · ${activeName}"`,
  ).toContainText(`${active} · ${activeName}`);

  // And NOTHING was written: the active route keeps its member, and the refused
  // draft does not exist on the landing.
  await page.getByRole("button", { name: "← Routes & Cycles" }).click();
  await expect(routesTable(page)).toBeVisible({ timeout: 30_000 });
  await searchRoutes(page, active);
  await expect(
    routeRow(page, active),
    `the DRAFT route ${draft} emptied the ACTIVE route ${active} — drafts must affect nothing`,
  ).toContainText("1 · 2");
  await searchRoutes(page, draft);
  await expect(
    routeRow(page, draft),
    "the refused draft was saved anyway, so the refusal was cosmetic",
  ).toHaveCount(0);
});

// ═══════════════════════════════════════════════════════════════════════════
// 15 · DEF-220 — A PREMISES CANNOT BE TAGGED TO AN AREA ANYWHERE
// ═══════════════════════════════════════════════════════════════════════════
test(`CR-006 · a premises can be given an area, so the SET-06.2 filter can return rows ${APP_SERVER_TAG}`, async ({
  page,
}) => {
  test.setTimeout(WALK_BUDGET_MS);
  // FINDING (DEF-220) — WHAT THE PRODUCT DOES TODAY:
  //   PO ruling 2026-08-16: *"user can define their own areas and we wil tag
  //   them to premises ; in CR06 you can use area and sub area for filtering -
  //   all option 1 to many options will be required"*. The FILTER is built and
  //   is genuinely multi-select with removable chips. Nothing can be tagged.
  //   Measured: every row of the SET-06 step-2 picker shows `—` in the
  //   `Area · sub` column; ticking any area chip takes the picker from
  //   *"9 premises match your filters."* to *"0 premises match your filters."*
  //   and the empty state. `premises.area_id` shipped as a column with no write
  //   path — the backend's `_validate_premises` refuses `area_code`/`area_id`
  //   as unknown fields, and neither the S16 add-premises wizard nor the
  //   premises detail screen draws the control.
  // WHAT IT MUST DO: some screen must set a premises' area, or the ruling is
  //   undelivered and the filter can only ever return zero rows.
  //
  // ✅ FIXED in commits ad60b77 (the write path) · 23f91d0 (the screens) ·
  // 7d89a84 (the strings), 2026-08-17, after the PO ruled *"when we add premises
  // you should allow to select areas and sub areas on premises"*. `test.fail()`
  // LIFTED by the closing walkthrough, 2026-08-17.
  //
  // ⚠ AND THE OLD BODY WAS A WEAK PIN — worth saying, because it stayed RED
  // after the fix landed and so reported PASS. It read the labels on whatever
  // the add-premises wizard shows FIRST, and S16 step 1 is the "How many?" mode
  // chooser: the details form with the Area controls is step 2, so that probe
  // could never have seen the field however well it was built. It was right for
  // the wrong reason. The body now (a) walks to the step that has the form,
  // and then (b) does the thing the ruling is actually FOR: tags a premises and
  // proves THE FILTER RETURNS MORE THAN ZERO ROWS, which is the number the
  // whole finding was about — ticking any area chip used to take the picker
  // from "9 premises match your filters." to "0 premises match your filters."
  await signInAsAdmin(page);

  // ── (a) The form draws the two controls, where a person adds a premises ──
  await page.goto(`/${tenant()}/premises/new`);
  await expect(page.locator(".met-page").first()).toBeVisible({ timeout: 60_000 });
  // Step 1 is the mode chooser and `One premise` is its default; Continue lands
  // on the details form.
  await page.getByRole("button", { name: "Continue" }).first().click();
  await expect(page.getByText("Premise details")).toBeVisible({ timeout: 30_000 });
  // ⚠ SCOPED TO THE FIELD LABELS, not the whole pane: the unit-type option set
  // contains "Common area", so a whole-page /area/i match would pass on a word
  // that has nothing to do with the areas vocabulary.
  const labels = (await page.locator(".met-page label").allInnerTexts()).map((raw) =>
    raw.replace(/\s+/g, " ").trim(),
  );
  expect(
    labels.some((label) => /^area\b/i.test(label)),
    `the add-premises form has no Area field, so a premises can never be tagged — it draws exactly: ${JSON.stringify(labels)}`,
  ).toBe(true);
  expect(
    labels.some((label) => /sub-?area/i.test(label)),
    `the add-premises form has no Sub-area field — it draws exactly: ${JSON.stringify(labels)}`,
  ).toBe(true);

  // ── (b) Tag a real premises, from the S14 edit modal on the premises list ─
  //    `PREMISES_C` is used because it is a seeded premises with units and
  //    meters, so it is a row the SET-06 picker lists.
  await page.goto(`/${tenant()}/premises`);
  const oakRow = page.locator("tr.data-table-row").filter({ hasText: PREMISES_C });
  await expect(oakRow, `the seeded premises ${PREMISES_C} is not on the list`).toHaveCount(1);
  await oakRow.getByRole("button", { name: "Edit", exact: true }).click();
  await expect(page.locator(".modal-card")).toBeVisible({ timeout: 30_000 });
  await expect(
    page.locator("#area_code"),
    "the premises edit modal draws no Area control, so the add wizard and the edit form disagree",
  ).toHaveCount(1);
  await page.locator("#area_code").selectOption("NORTH");
  await page.getByRole("button", { name: "Save premise" }).click();
  await expect(page.locator(".modal-card")).toHaveCount(0, { timeout: 30_000 });

  // It STUCK — re-opened from a fresh read of the server, not from local state.
  await page.goto(`/${tenant()}/premises`);
  await page.locator("tr.data-table-row").filter({ hasText: PREMISES_C })
    .getByRole("button", { name: "Edit", exact: true }).click();
  await expect(page.locator(".modal-card")).toBeVisible({ timeout: 30_000 });
  await expect(
    page.locator("#area_code"),
    "the area was accepted by the form and not stored — the tag did not survive a reload",
  ).toHaveValue("NORTH");
  await page.getByRole("button", { name: "Cancel" }).first().click();

  // ── (c) THE NUMBER THE WHOLE FINDING WAS ABOUT ──────────────────────────
  await openRoutesCycles(page);
  await page.getByRole("button", { name: "+ Add route" }).first().click();
  await expect(page.getByText("Step 1 of 4 · Details")).toBeVisible({ timeout: 30_000 });
  await field(page, "Name").fill(`QA area filter ${STAMP}`);
  await continueStep(page, 2);
  await page.getByLabel("+ Filter").selectOption("NORTH");
  const matching = page.locator('[data-rcw="selectall"]');
  // ⚠ THE ASSERTION IS THE WAIT, and it has to be: while the filtered query is
  // in flight the picker renders `rows = []` and says "0 premises match your
  // filters." — so reading the counter the instant the chip goes on measures
  // the LOADING state and reports a working filter as broken. Measured: this
  // test failed exactly that way at 17:30:28 while the server log for the same
  // second shows `GET /routes/premises-picker?area=NORTH -> 200` returning one
  // row. Requiring a NON-ZERO count polls until the answer arrives and still
  // fails honestly if the answer really is zero.
  await expect(
    matching,
    "the area filter returns nothing with the North district chip on — the PO's ruling is undelivered",
  ).toContainText(/[1-9]\d* premises match your filters/, { timeout: 30_000 });
  const matchText = (await matching.innerText()).replace(/\s+/g, " ");
  const matched = Number(/(\d+) premises match/.exec(matchText)?.[1] ?? "0");
  expect(matched, `the picker says "${matchText.trim()}"`).toBeGreaterThan(0);
  // And the row a person reads carries the area, rather than the em dash every
  // row showed before the write path existed.
  await expect(
    page.locator('table[data-rcw="table"] tbody tr').filter({ hasText: PREMISES_C }),
    "the filtered picker does not list the premises that was just tagged",
  ).toHaveCount(1);
});

// ═══════════════════════════════════════════════════════════════════════════
// 16 · DEF-221 — A SUB-AREA CANNOT BE CREATED ANYWHERE
// ═══════════════════════════════════════════════════════════════════════════
test(`CR-006 · a sub-area can be created from the Areas & sub-areas card ${APP_SERVER_TAG}`, async ({
  page,
}) => {
  test.setTimeout(WALK_BUDGET_MS);
  // FINDING (DEF-221) — WHAT THE PRODUCT DOES TODAY:
  //   The card is called *"Areas & sub-areas"* and the backend accepts
  //   `parent_code` on `/lookups/areas` (a row with a parent IS a sub-area,
  //   depth capped at two). The reference-data editor sends `{code, name,
  //   detail}` only, so no screen can make one. Measured: the `+ Add entry`
  //   modal on that card draws Code, Name and Detail and no parent control, and
  //   all four seeded rows are top-level. The route wizard renders
  //   `parent_name ? "<parent> · <name>" : name` in two dropdowns — a branch
  //   nothing in the product can reach (hard-won law 2).
  // WHAT IT MUST DO: the card that is NAMED "sub-areas" must be able to make
  //   one.
  //
  // ✅ FIXED in commit 23f91d0 (2026-08-17) — the card's add/edit form gained a
  // **Parent area** picker that sends `parent_code`, and the table gained a
  // Parent column so the second level is visible. `test.fail()` LIFTED by the
  // closing walkthrough on 2026-08-17 after this reported *"Expected to fail,
  // but passed"*.
  await signInAsAdmin(page);
  await page.goto(`/${tenant()}/settings/reference-data/reference-data`);
  await expect(page.getByText("Areas & sub-areas")).toBeVisible({ timeout: 60_000 });
  await page.getByText("Areas & sub-areas").click();
  await page.getByRole("button", { name: "+ Add entry" }).first().click();
  await expect(page.locator(".modal-card")).toBeVisible({ timeout: 30_000 });
  // ⚠ SCOPED TO THE FIELD LABELS, NOT THE MODAL. The dialog is TITLED "Add to
  // Areas & sub-areas", so a whole-modal text match for /sub-area/ passes on
  // the heading and proves nothing — measured: this test reported
  // "expected to fail, but passed" on exactly that. DEF-182's shape again: a
  // check whose output cannot distinguish pass from fail is worse than none.
  const labels = (await page.locator(".modal-body label").allInnerTexts()).map((raw) =>
    raw.replace(/\s+/g, " ").trim(),
  );
  expect(
    labels.some((label) => /parent|sub-?area|sits inside|belongs to/i.test(label)),
    `the "Areas & sub-areas" add form has no field for the area a sub-area sits in — it draws exactly: ${JSON.stringify(labels)}`,
  ).toBe(true);
});

// ═══════════════════════════════════════════════════════════════════════════
// 17 · DEF-222 — THE COMMIT BUTTON SAYS "CREATE" WHILE EDITING
// ═══════════════════════════════════════════════════════════════════════════
test(`CR-006 B14/4 · editing an existing route commits with a Save verb, not "Create" ${APP_SERVER_TAG}`, async ({
  page,
}) => {
  test.setTimeout(WALK_BUDGET_MS);
  // FINDING (DEF-222) — WHAT THE PRODUCT DOES TODAY:
  //   Opening ✎ on an existing route walks the same four steps and step 4
  //   correctly reads *"Ready to save Route 1."* — and the commit button next
  //   to it reads **"Create route ✓"**. The cycle wizard does the same:
  //   *"Ready to save CY-001."* over **"Create cycle ✓"**. `commitLabel` is
  //   chosen from `activate` alone and never asks whether this is an edit.
  //   B14 rule 4 is the button-grammar rule; a commit that says Create over a
  //   summary that says save is the surface telling a person two things.
  // WHAT IT MUST DO: an edit commits with a save verb.
  //
  // ✅ FIXED in commit 506234b (2026-08-17) — `commitLabel` now depends on
  // BOTH `editing` and `activate`, four strings per wizard instead of two, in
  // all eleven catalogues. `test.fail()` LIFTED by the closing walkthrough,
  // 2026-08-17.
  await signInAsAdmin(page);
  await openRoutesCycles(page);
  // The first row on the landing, whatever it is — not a fixture row by name
  // (DEF-233).
  const editCode = (
    await routesTable(page).locator("tbody tr").first().locator("td").first().innerText()
  ).trim();
  await page.getByRole("button", { name: `Edit ${editCode}` }).click();
  await expect(page.getByText("Step 1 of 4 · Details")).toBeVisible({ timeout: 30_000 });
  await continueStep(page, 2);
  await continueStep(page, 3);
  await continueStep(page, 4);
  await expect(page.getByText(`Ready to save ${editCode}.`)).toBeVisible();
  const label = (await page.locator(".wizard-actions button").last().innerText()).trim();
  expect(label, `an EDIT commits with "${label}" under a summary that says "Ready to save"`).not.toMatch(/^Create/);
});

// ═══════════════════════════════════════════════════════════════════════════
// 18 · DEF-223 — B14 DIVERGENCES, MEASURED IN THE BROWSER
// ═══════════════════════════════════════════════════════════════════════════
test(`CR-006 B14/20 · every table on this surface renders at one type size ${APP_SERVER_TAG}`, async ({
  page,
}) => {
  test.setTimeout(WALK_BUDGET_MS);
  // FINDING (DEF-223a) — MEASURED IN CHROMIUM:
  //   the SET-05 landing tables render at **14px** (`.settings-table`) and the
  //   wizard tables at **13.5px** (`[data-rcw="table"]`). B14 rule 20 is *"Table type
  //   is one size (13.5px) everywhere; no inline overrides"* — so the surface
  //   carries two sizes and the landing one is the off-spec half.
  //
  // ✅ FIXED in commit 506234b (2026-08-17) — `--table-font-size` was being
  // READ with a fallback and DECLARED BY NOTHING, so the fallback did all the
  // work; it is now a real token at B14's ratified 13.5px and `.settings-table`
  // points at it instead of hardcoding 14px. `test.fail()` LIFTED by the closing
  // walkthrough, 2026-08-17.
  //
  // ⚠ DEF-223 STAYS OPEN, and this test closes only its first part. Rule 20 is
  // still not true PRODUCT-WIDE — the shared `DataTable` renders every list
  // outside this surface at 13px and was deliberately not touched inside a
  // Routes & Cycles fix. The two tests below still pin the other parts.
  await signInAsAdmin(page);
  await openRoutesCycles(page);
  const landing = await routesTable(page).locator("tbody td").first().evaluate((node) => getComputedStyle(node).fontSize);
  await page.getByRole("button", { name: "+ Add route" }).first().click();
  await expect(page.getByText("Step 1 of 4 · Details")).toBeVisible({ timeout: 30_000 });
  await field(page, "Name").fill(`QA b14 ${STAMP}`);
  await continueStep(page, 2);
  const wizard = await page.locator('table[data-rcw="table"] tbody td').first().evaluate((node) => getComputedStyle(node).fontSize);
  expect(landing, `landing tables render at ${landing} and wizard tables at ${wizard}`).toBe(wizard);
});

test(`CR-006 B14/5 · this surface uses two button sizes, not three ${APP_SERVER_TAG}`, async ({
  page,
}) => {
  test.setTimeout(WALK_BUDGET_MS);
  // FINDING (DEF-223b) — MEASURED IN CHROMIUM on the SET-05 landing: three
  //   distinct button type sizes render — **12px, 13px and 14px**. B14 rule 5
  //   is *"Two button sizes only — default and small (12px). No inline font
  //   sizes"*.
  //
  // ✅ FIXED 2026-08-18, and the mechanical cause was DEF-244's shape for the
  // SIXTH time: **`.btn-sm` was declared by NO stylesheet in the repo.** Three
  // components asked for the small tier and every one of them rendered at the
  // default 14px, so rule 5's "small (12px)" simply did not exist; the third
  // size was `.table-page-btn`'s own hardcoded 14px against a 13px pager row.
  // The tier is now declared once beside `.btn` in StateFrame.css.
  //
  // The assertion names the OFFENDING BUTTONS, not just the count: a bare
  // "expected 2, got 3" sends the next reader back to the browser to find out
  // which three, which is the forty minutes this file exists to save.
  await signInAsAdmin(page);
  await openRoutesCycles(page);
  // ⚠ JUDGMENT CALL, 2026-08-18, recorded here and REPORTED to the PO rather
  // than made silently: `[role="tab"]` is EXCLUDED from this measurement.
  // Rule 5's word is "button sizes", the 13px element the first run caught was
  // the Settings TAB STRIP — `.settings-tabs button`, a tablist ported from the
  // signed prototype that B14 itself was extracted from. Reading rule 5 to
  // outlaw the prototype's own tab strip would make B14 contradict its source.
  // A tab is navigation chrome, not an action button; it carries role="tab"
  // precisely because it is not a button in the ARIA sense either. If the PO
  // rules the other way, delete the `:not([role="tab"])` below and the strip
  // goes red with the offender named.
  const measured = await page.locator('main.view button:not([role="tab"])').evaluateAll((nodes) =>
    nodes.map((node) => ({
      size: getComputedStyle(node).fontSize,
      cls: node.className || "(no class)",
      text: (node.textContent ?? "").trim().slice(0, 24),
    })),
  );
  const sizes = [...new Set(measured.map((entry) => entry.size))].sort();
  const witness = sizes
    .map((size) => {
      const first = measured.find((entry) => entry.size === size);
      return `${size} → "${first?.text}" [${first?.cls}]`;
    })
    .join(" · ");
  expect(sizes, `the landing renders ${sizes.length} button sizes: ${witness}`).toHaveLength(2);
  // Rule 5 names the two tiers, so pin them rather than accepting any two.
  expect(sizes, `B14 rule 5's tiers are default (14px) and small (12px); got ${witness}`).toEqual([
    "12px",
    "14px",
  ]);
});

test(`CR-006 B14/16 · every list table in both wizards carries a pagination footer ${APP_SERVER_TAG}`, async ({
  page,
}) => {
  test.setTimeout(WALK_BUDGET_MS);
  // FINDING (DEF-223c) — MEASURED: the SET-06 premises picker HAS a footer and
  //   both landing tables have one. The SET-06 step-3 METER list has none, and
  //   the SET-07 step-2 ROUTE picker has none — and neither is a wizard SUMMARY
  //   table, which is the only exemption rule 16 grants. The SET-07 route
  //   picker also carries no toolbar at all: no search, no chips, no filter
  //   (rule 12), while the premises picker two screens away has all three.
  test.fail();
  await signInAsAdmin(page);
  await openRoutesCycles(page);
  await page.getByRole("button", { name: "+ Add cycle" }).first().click();
  await expect(page.getByText("Step 1 of 4 · Details")).toBeVisible({ timeout: 30_000 });
  await field(page, "Name").fill(`QA pager ${STAMP}`);
  await continueStep(page, 2);
  await expect(page.locator('table[data-rcw="table"]')).toBeVisible();
  expect(
    await page.locator(".table-pager").count(),
    "the SET-07 route picker is a list table with no pagination footer",
  ).toBeGreaterThan(0);
});

// ═══════════════════════════════════════════════════════════════════════════
// 19 · DEF-224 — THE COPY: NO ORDINALS, NO PLURALS
// ═══════════════════════════════════════════════════════════════════════════
test(`CR-006 · the schedule preview reads in English ordinals, and counts agree with their nouns ${APP_SERVER_TAG}`, async ({
  page,
}) => {
  test.setTimeout(WALK_BUDGET_MS);
  // FINDING (DEF-224) — MEASURED ON SCREEN:
  //   the preview renders *"Read 1–3 · exceptions cleared by the 4 · bills out
  //   the 5 · due the 26"*. r10's own string is *"exceptions cleared by 4th ·
  //   bills out 5th · due 26th"*, and "the 4" is not how a day of the month is
  //   said in English. Counts have no plural forms either: the cycle picker
  //   reads *"1 routes selected"* and *"1 routes · 1 members"*, and the
  //   deactivation warning reads *"will skip 1 premises"*.
  // WHAT IT MUST DO: ordinal-format the day, and use i18next plurals so a count
  //   of one reads as one.
  //
  // ⚠ SPLIT IN TWO by the closing walkthrough (2026-08-17), because DEF-224 was
  // fixed IN HALF and one test cannot report half a defect. The ORDINALS landed
  // in commit 506234b — `ordinalDay()` asks `Intl.PluralRules` for the
  // language's own ordinal category and the suffixes live in the catalogues, so
  // English gets 5th and the other ten get the bare number. The PLURALS did
  // NOT: `settings.cycles.wizard.routesSelected` is still the single string
  // `"{{count}} routes selected"` with no `_one` form, so a single route still
  // reads *"1 routes selected"*. Left as ONE test, the plural half would have
  // gone on failing and `test.fail()` would have gone on reporting PASS over a
  // fix that had already landed — the same trap DEF-219 fell into two tests up.
  //
  // ✅ THIS HALF IS FIXED. `test.fail()` LIFTED.
  await signInAsAdmin(page);
  await openRoutesCycles(page);
  await page.getByRole("button", { name: "+ Add cycle" }).first().click();
  await expect(page.getByText("Step 1 of 4 · Details")).toBeVisible({ timeout: 30_000 });
  await field(page, "Name").fill(`QA copy ${STAMP}`);
  await continueStep(page, 2);
  await continueStep(page, 3);
  await field(page, "Read window from").fill("1");
  await field(page, "Read window to").fill("3");
  await field(page, "Bill day").fill("5");
  await field(page, "Due day").fill("26");
  const preview = (await page.locator('[data-rcw="preview"]').innerText()).replace(/\s+/g, " ");
  expect(preview, `the preview reads "${preview}"`).toContain("5th");
  expect(preview, `the preview reads "${preview}"`).toContain("26th");
  expect(
    preview,
    `the day of the month lost its ordinal again — the preview reads "${preview}"`,
  ).not.toMatch(/the 5 |the 26/);
});

test(`CR-006 · a count of one reads as one, not "1 routes selected" ${APP_SERVER_TAG}`, async ({
  page,
}) => {
  test.setTimeout(WALK_BUDGET_MS);
  // FINDING (DEF-224, the half that is STILL OPEN) — MEASURED ON SCREEN:
  //   no count on this surface has a plural form. The cycle picker reads
  //   *"1 routes selected"* and *"1 routes · 1 members"*, and the deactivation
  //   warning reads *"will skip 1 premises"*. `en.json` carries
  //   `settings.cycles.wizard.routesSelected = "{{count}} routes selected"` as
  //   one string with no `_one` sibling, so i18next has nothing to choose
  //   between.
  // WHAT IT MUST DO: add the `_one` / `_other` keys so a count of one reads as
  //   one. DEF-224's own row says to pair this with DEF-215's translation pass
  //   rather than fix it alone — the same 201 strings are going to a supplier
  //   and a plural-less catalogue is what they should be asked to fill.
  test.fail();
  await signInAsAdmin(page);
  await openRoutesCycles(page);
  await page.getByRole("button", { name: "+ Add cycle" }).first().click();
  await expect(page.getByText("Step 1 of 4 · Details")).toBeVisible({ timeout: 30_000 });
  await field(page, "Name").fill(`QA plural ${STAMP}`);
  await continueStep(page, 2);
  // Whichever route the picker lists first — not a fixture row by name
  // (DEF-233).
  await page.locator('table[data-rcw="table"] tbody input[type=checkbox]').first().check();
  const counter = await page.locator('[data-rcw="count"]').first().innerText();
  expect(counter, `the cycle picker says "${counter.trim()}" for a single route`).not.toContain("1 routes");
});

// ═══════════════════════════════════════════════════════════════════════════
// 20 · DEF-233 — NEW, FOUND BY THE CLOSING WALKTHROUGH: THE READS-HISTORY
//      DELETE GUARD IS BYPASSED BY MOVING THE PREMISES AWAY FIRST
// ═══════════════════════════════════════════════════════════════════════════
test(`CR-006 · a route that collected reads still refuses deletion after its premises move away ${APP_SERVER_TAG}`, async ({
  page,
}) => {
  test.setTimeout(WALK_BUDGET_MS);
  // FINDING (DEF-233) — WHAT THE PRODUCT DOES TODAY, AND HOW IT WAS FOUND:
  //   The seeded `Route 1 · Katy Central` WAS DELETED during the second run of
  //   this walkthrough, and two later tests then failed looking for it. It was
  //   deleted by the test at the top of this file that asks the delete guard to
  //   refuse — and on the first run that guard DID refuse, naming 135 reads.
  //   What changed between the two runs is that DEF-217 was fixed, so the
  //   DEF-217 test could finally put `1408 Bluestem Ln` on a route of its own,
  //   which MOVED the fixture's only read premises off `Route 1`.
  //
  //   `route_read_history_count()` counts reads two ways: through
  //   `meter_reads.import_batch.route_id`, and through the service points
  //   currently stamped with the route. A membership move UNSTAMPS the service
  //   points, and on this fixture **all 135 reads have `import_batch_id` NULL**
  //   — COUNTED in the database, not assumed — so the batch half can never
  //   fire and the guard drops to zero. `Route 1` then had no members and no
  //   history, and the product deleted it.
  //
  //   The services docstring says the guard "hunts through
  //   `read_import_batches.route_id`, which no membership edit clears" — and
  //   `read_import_batches` is EMPTY on this tenant. Hard-won law 1: a comment
  //   claiming a guarantee is not the guarantee.
  //
  // WHAT IT MUST DO: CR-006's own words are *"deleting is not allowed once a
  //   route has reads history — deactivate only"*. Moving the premises to
  //   another route does not un-collect the reads, so the refusal must survive
  //   the move. Two clicks a real admin walks — tidy up the round, then delete
  //   the route that is now empty — and the record of who read those meters
  //   goes with it.
  test.fail();
  await signInAsAdmin(page);
  await openRoutesCycles(page);

  // Own both ends: the route that collects the history, then the route that
  // takes its premises away.
  const keeper = `QA-RT-HIST-${STAMP}`;
  const taker = `QA-RT-TAKE-${STAMP}`;
  await createRoute(page, {
    code: keeper,
    name: `QA history ${STAMP}`,
    premises: [PREMISES_WITH_READS],
  });
  await openRoutesCycles(page);
  await createRoute(page, {
    code: taker,
    name: `QA taker ${STAMP}`,
    premises: [PREMISES_WITH_READS],
  });

  // The keeper is now empty on screen — and it is still the route those 135
  // reads were collected on.
  await openRoutesCycles(page);
  await searchRoutes(page, keeper);
  await expect(routeRow(page, keeper)).toContainText("0 · 0");
  await routeRow(page, keeper).getByRole("button", { name: "Delete" }).click();
  await dialog(page).getByRole("button", { name: `Delete ${keeper}` }).click();

  await expect(
    page.getByText(/reads were collected on this route/i),
    `${keeper} collected 135 reads and was deleted anyway once its premises moved — BR-MET-079 must still refuse`,
  ).toBeVisible({ timeout: 30_000 });
  await searchRoutes(page, keeper);
  await expect(routeRow(page, keeper), "the route with reading history is gone").toHaveCount(1);
});

// ── Lifecycle ─────────────────────────────────────────────
// packet: CR-006 (SET-05/06/07) — the five PO rulings of 2026-08-16, plus the
//   "BUILT, NOT CLOSED" record of 2026-08-17
// generated: 2026-08-17 by the CR-006 browser-walkthrough lane
// checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-08)
// gates: run against the live stack (Postgres + Django + the BUILT SPA on one
//   origin, `08-qa/01-e2e/stack/boot_stack.sh`, database `sbh_e2e_cr006`, ports
//   8041/8141). FOUR runs on a freshly reset database each time except the last:
//   18 passed/3 failed · 20 passed/1 failed · then **21 passed · 0 failed · 343
//   assertions in 13.3 minutes**. Every failure in the first two was a bug in
//   THIS FILE, not in the product — three step titles that a table also carries
//   in a visually-hidden `<caption>` (so `getByText` matched two elements), and
//   one whole-modal regex that passed on the dialog's own heading, which
//   reported "expected to fail, but passed" and is DEF-182's shape. All four
//   fixed.
//   ✅ **AND THE FOURTH RUN IS THE ONE THAT MATTERS: the SAME spec driven
//   straight over the third run's leftovers, WITHOUT resetting the database —
//   21 passed · 0 failed · 332 assertions in 13.1 minutes.** Five QA routes, a
//   QA cycle, `Route 5` already moved off 08-B and `Route 2` already emptied by
//   run 3's draft, and every claim still held. **Nothing here passes only on a
//   pristine seed.** The 11-assertion difference is the design working: DEF-218's
//   test takes the long branch when the pre-filled code is still free and the
//   short one when a route already wears it, reaching the same claim either way.
//   Every code this file creates carries the per-run `STAMP`, and no assertion
//   depends on a counter starting at 1 — keep both properties when editing it.
// exceptions: `ensureRoleUser` makes three API calls because `/change-password`
//   is not built (DEF-200) — fenced, labelled and the only non-browser calls in
//   the file · this spec WRITES (run-unique routes and cycles, and it moves
//   `Route 5` onto the cycle it creates) — disposable tenants only · eight
//   tests are `test.fail()`: they state the RULE and go RED the moment the
//   product is fixed (the inversion contract in the header)
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
