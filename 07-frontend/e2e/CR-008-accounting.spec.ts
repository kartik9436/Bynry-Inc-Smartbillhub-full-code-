// ── Trace ──────────────────────────────────────────────
// Change:  CR-008 (12-governance/11-change-requests.md) — SET-11 Settings →
//          Accounting: the chart of accounts, the five-section GL map and the
//          finance controls. Marked **BUILT-NOT-PROVEN 2026-08-18**, and the
//          register says in its own words why: *"no browser walkthrough exists
//          and no spec is even written … CR-008 is the largest unmet item in
//          the CR-011 audit for this reason."* This file is that spec.
// Story:   CR-008@set11 · Screens: SET-11.coa · SET-11.map · SET-11.controls
//          Routes: /{tenant}/settings/accounting/{chart|mapping|controls}
//          plus /{tenant}/finance/gl?view=chart (S56, the same panel) and
//          /{tenant}/payments/record (S33, where B-10's posting is provable).
// Rules:   BR-BIL-067 (a seeded service→revenue account is a DEFAULT the tenant
//          may override) · BR-BIL-069 (each tax AUTHORITY has its own liability
//          account) · BR-BIL-010 (a bill fails ATOMICALLY at issue when a line
//          cannot resolve an account — which is why the GAP banners are rules
//          and not decoration) · BR-LED-037/038 (the 5xxx cost rows are a
//          PROPOSAL awaiting a finance signature and no surface may call them
//          approved) · BR-TEN-026 · BR-TEN-034 (deactivate, never delete) ·
//          BR-SHL-025 (a control that cannot work stays VISIBLE and DISABLED
//          WITH ITS REASON) · BR-SHL-020 (a plain-language refusal) ·
//          CR-008 PO rulings 1·3·4·5·8·9 (2026-08-17) and the B-section
//          rulings B-8 · B-9 · B-10 (built 2026-08-18 at 2.16.0/2.17.0).
// ───────────────────────────────────────────────────────
//
// **THE BAR THIS FILE IS WRITTEN AGAINST**, verbatim from the PO on 2026-08-18
// (`12-governance/13-change-process.md` §8, THE CLOSURE BAR):
//
//   *"in this session CR is not closed until we have confirm user is able to
//    perform tasks using screen/broswer/UI"*
//
// and the three properties that bar spells out:
//
//   1. assertions on **rendered text a person reads** — never on an API
//      response or a component prop. There are exactly TWO API calls in this
//      file and both are in `ensureRoleUser`, fenced and labelled, for the one
//      thing no screen can do (create a signed-in Executive — `/change-password`
//      is not built, DEF-200);
//   2. **every task the CR promises, performed end to end, INCLUDING ITS
//      REFUSALS** — so a mapping to a retired account is picked and refused, a
//      card payment against a retired clearing account is refused by name, and
//      an import file with a bad row is refused whole;
//   3. **re-runnable over its own leftovers.** Every row this file creates
//      carries a per-run stamp; nothing asserts a counter starting at 1; the
//      one shared row it must touch (the `card` tender's clearing account) is
//      RESET to unmapped at the start of its own test as well as at the end,
//      so a crashed run cannot leave the tenant unable to take a card payment.
//
// ── THE INVERSION CONTRACT — READ BEFORE TRUSTING A GREEN RUN ──────────────
//
// This lane reports; it does not fix product code. A finding is therefore
// pinned as a `test.fail()` that states the RULE it believes is right, so the
// day somebody fixes it the run goes RED at that exact line with the finding
// quoted ("expected to fail, but passed"). Nobody can close one of these
// quietly. **A green run of this file means: the screens work as described AND
// the findings below are still open.** It does NOT mean SET-11 is right.
//
// ── THE RUN RECORD ─────────────────────────────────────────────────────────
//
// | run | database | result |
// |---|---|---|
// | 1 | live `sbh_e2e`, NOT reset — it already carried other lanes' data | **12 passed · 3 failed**, 10.6 min |
// | 2 | the same database, **over run 1's own leftovers** | **17 passed · 0 failed**, 11.7 min |
// | 3 | 2026-08-19, the CLOSING walk, same stack, over runs 1 and 2's leftovers | **16 passed · 1 failed**, 11.8 min |
// | 4 | 2026-08-19, the same file after the inversion below | **17 passed · 0 failed**, 11.5 min |
// | 5 | 2026-08-19, `-g "SET-11.controls"` only, after rulings 2 and 7 were added to it | **1 passed**, 28.4 s |
// | 6 | 2026-08-19, **the committed bytes**, whole file, after CR-008 was closed | **17 passed · 0 failed**, 11.4 min |
//
// Run 6 exists so the closure record's claim is about the artefact that is IN the
// repo rather than about a working copy that has since been edited three times.
//
// **Run 5 exists because run 4 exposed a COVERAGE hole rather than a failure.**
// Rulings 2 and 7 — the write-off approval threshold and the bank-match amount
// tolerance, both money, both shipped by CR-008 — are rendered on THIS tab and
// no run had ever read either. Added to §12, proved RED first by asserting
// `$5,000.00` (the run answered *"Received string: \"$0.00\""*, so the locator
// resolves and the assertion discriminates), then restored and green.
//
// **Run 3's single failure was the TRIPWIRE FIRING, not a regression**, and it
// is the reason the tripwire was written into a visible test instead of a
// `test.fail`. Verbatim from the run:
//
//   *"Error: the cost-section proposal sentence is missing — if the 2026-08-18
//    finance re-sign has landed this is EXPECTED and the fix is to invert this
//    block and revisit FINDINGS 1 and 2 … waiting for getByText('are a proposal
//    awaiting a finance signature')"*
//
// It had. The Product Owner re-signed 4180 and all eight 5xxx cost rows on
// 2026-08-18, both pending registers are `()`, and the note the assertion was
// waiting for is correctly gone from the screen. **The PRODUCT was right and
// this FILE was stale**, so the fix is here and not there: §3's block is
// inverted, FINDING 1 becomes a live regression test of the ratified state
// (its cause, DEF-260, was fixed the same day in `5a85bec`), and FINDING 2 is
// annotated as a now-latent pin. Nothing else moved.
//
// **Two of run 1's three failures were the SPEC's and are fixed here**, and
// both are worth naming because both were the spec asserting something truer
// than the product:
//
//   · the §4 GAP banner was asserted to name `LATE`. It names the FIRST FIVE
//     unmapped codes and this tenant has twenty-three, so `LATE` is not among
//     them. The count is live data another lane edits — it read 30 unmapped
//     when this file was written and 23 when it first ran — so the assertion
//     is now a SHAPE and never a figure. The truncation itself became
//     FINDING 3;
//   · the pick-time refusal was asserted with a bare `getByText`, and the
//     shared FormModal renders the sentence TWICE (field error + form-level
//     alert). Playwright's strict mode turned a correct product refusal into
//     *"a retired account was accepted"* — a failure message that said the
//     exact opposite of what happened. Both copies are asserted now.
//
// **The third failure was the PRODUCT and is FINDING 1.**
//
// **RUN 2 DROVE THE IDENTICAL FILE STRAIGHT OVER RUN 1's LEFTOVERS** — its two
// retired QA accounts, its imported account, its two Executive users and its two
// recorded payments — and every claim still held. So nothing in this walkthrough
// passes only on a pristine seed, which is the property that decides whether
// anybody runs it a second time.
//
// ── ⚠ WHAT THIS FILE WRITES, because it writes MONEY ───────────────────────
//
// It creates two ledger accounts per run (`19xx-QA-<stamp>` and
// `49xx-QA-<stamp>`), imports one more from a CSV, retires one of them, points
// the `card` tender at one and back to nothing, re-points ONE adjustment reason
// (`GOODWILL`) and back, and **records two customer payments of $4.18 and
// $4.19 against account AC-2026-00001** — one that posts and one that is
// refused. Payments and journal entries are IMMUTABLE by hard rule 4, so those
// two rows are permanent. That is the price of proving B-10 on screen; there is
// no read-only route to the same claim, because the only surface that shows
// where a receipt landed is the trial balance, and nothing reaches the trial
// balance without money moving. **Point this at a disposable tenant only** —
// the same posture, and the same warning, as CR-004-reference-crud.spec.ts.
import { expect, test } from "@playwright/test";
import type { Locator, Page } from "@playwright/test";

import { APP_SERVER_TAG } from "./support/census";
import { signIn, skipUnlessAppServer, tenant } from "./support/app";

skipUnlessAppServer(test);

// MEASURED on this stack, not guessed: `vite build` emits one 3.5 MB chunk and
// a cold load runs ~13 s. These are WALKTHROUGHS — sign in, cross three
// sub-tabs, open modals, reload to prove persistence — so the 90 s default is
// not the budget for one.
const WALK_BUDGET_MS = 300_000;

/** Per-run, so every row this file creates is unique and a second run over the
 *  first run's leftovers collides with nothing. Base 36 keeps it short enough
 *  to read in a table cell. */
const STAMP = Date.now().toString(36).slice(-6);

const ACCOUNTING = `/${tenant()}/settings/accounting`;
const MAPPING = `${ACCOUNTING}/mapping`;
const CONTROLS = `${ACCOUNTING}/controls`;
const GL_CHART_VIEW = `/${tenant()}/finance/gl?view=chart`;

// ── Selectors, and why they are what they are ──────────────────────────────
//
// SET-11 carries NO per-screen test ids — unlike SET-09, which grew them when
// it moved onto the shared `DataTable`. That is a fact about the product rather
// than a preference of this file. Every locator here is therefore anchored on a
// HEADING a person reads, which is the same thing the person is anchored on, and
// it means a copy change breaks this spec loudly rather than silently matching
// the wrong table.

/** The first `<table>` that follows a given heading, by its rendered text. */
function tableAfter(page: Page, heading: string, level: "h3" | "h4" = "h3"): Locator {
  return page.locator(
    `xpath=//${level}[normalize-space(.)='${heading}']/following-sibling::table[1]`,
  );
}

/**
 * The `met-table` inside the finance panel whose heading reads `heading`.
 *
 * ⚠ NOT `tableAfter`. A finance panel wraps its heading in its own
 * `.fin-panel-head` div, so the table is a sibling of that DIV and never of the
 * `<h3>` — an XPath `following-sibling::table` finds nothing there. The two
 * helpers exist because the two features genuinely lay out differently, and one
 * helper that silently matched neither would be the worst of the three options.
 */
function finTable(page: Page, heading: string): Locator {
  return page
    .locator(".met-panel")
    .filter({ has: page.getByRole("heading", { name: heading, exact: true }) })
    .locator("table.met-table");
}

/** The chart panel's own table (the `met-table` the ledger feature renders). */
const chartTable = (page: Page): Locator => page.locator("table.met-table").first();

/** One chart row, addressed BY ACCOUNT CODE — never by name, so the assertions
 *  do not depend on copy that a rename would move. */
const chartRow = (page: Page, code: string): Locator =>
  chartTable(page).locator("tbody tr").filter({ has: page.getByText(code, { exact: true }) });

/** One row of a settings table, addressed by the text in its first cell. */
function settingsRow(table: Locator, firstCell: string): Locator {
  return table.locator("tbody tr").filter({ hasText: firstCell });
}

async function openSubTab(page: Page, name: string): Promise<void> {
  await page.getByRole("tab", { name, exact: true }).click();
}

async function signInAsAdmin(page: Page): Promise<void> {
  await signIn(page);
}

/**
 * PRE-FLIGHT, EXPLICITLY NOT PART OF THE PROOF — the only API calls in this
 * file, in one function so that is impossible to miss.
 *
 * An Executive is needed to prove BR-SHL-025 on this surface and the seed's own
 * Executive (`avery.cole@sample.test`) is invited and UNCREDENTIALED — the
 * sample-staff seam creates users with no password on purpose. Creating one
 * from the Users screen would be the purer route and does not exist: BR-IDN-022
 * hands back a temporary password and flags `must_change_password`, and the
 * forced-change screen at `/change-password` IS NOT BUILT (DEF-200). This walks
 * the three calls a human would otherwise walk through a screen. Copied
 * deliberately from CR-006-routes-cycles.spec.ts rather than shared: that file
 * is another lane's territory.
 */
async function ensureRoleUser(
  page: Page,
  role: string,
  email: string,
  password: string,
): Promise<void> {
  const base = `/api/${tenant()}`;
  const created = await page.request.post(`${base}/users`, {
    data: { full_name: `QA ${role} CR-008`, email, role },
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

/** Adds an account from the CHART SCREEN's own add form. Returns nothing —
 *  every later assertion re-reads the table, which is the point. */
async function addAccountOnScreen(
  page: Page,
  code: string,
  name: string,
  type: string,
): Promise<void> {
  const addPanel = page.locator(".met-panel").filter({ hasText: "Add an account" });
  await addPanel.locator("input.input").first().fill(code);
  await addPanel.locator("input.input").nth(1).fill(name);
  await addPanel.locator("select.input").selectOption({ label: type });
  await addPanel.getByRole("button", { name: "Add account ✓" }).click();
  await expect(
    chartRow(page, code),
    `${code} was not added from the chart screen — the add form reported nothing`,
  ).toBeVisible({ timeout: 30_000 });
}

// ═══════════════════════════════════════════════════════════════════════════
// 1 · SET-11 OPENS, AND IT IS THE THREE SUB-TABS r10 DRAWS
// ═══════════════════════════════════════════════════════════════════════════

test(`CR-008 SET-11 · the tab opens on three sub-tabs and lands on the chart ${APP_SERVER_TAG}`, async ({
  page,
}) => {
  test.setTimeout(WALK_BUDGET_MS);
  await signInAsAdmin(page);
  await page.goto(ACCOUNTING);

  // The kicker and the lede a person reads first.
  await expect(page.getByText("GL code mapping").first()).toBeVisible({ timeout: 60_000 });
  await expect(
    page.getByText(
      "liability land in your books",
      { exact: false },
    ),
  ).toBeVisible();

  // r10's three, in r10's order.
  for (const name of ["Chart of accounts", "GL mapping", "Finance controls"]) {
    await expect(
      page.getByRole("tab", { name, exact: true }),
      `SET-11 does not draw the "${name}" sub-tab`,
    ).toBeVisible();
  }
  await expect(
    page.getByRole("tab", { name: "Chart of accounts", exact: true }),
    "the default sub-tab is not the chart",
  ).toHaveAttribute("aria-selected", "true");

  // The chart panel itself, and the sentence that states the CR's core
  // principle — *your books own the chart; we never invent one*.
  await expect(page.getByText("Your chart of accounts")).toBeVisible();
  await expect(
    page.getByText("Your books own this list.", { exact: false }),
    "the chart tab does not say the books own the list",
  ).toBeVisible();

  // ⚠ RULING 3 (2026-08-17, *"we only need file no live integration"*) — the
  // QuickBooks sync, its last-sync timestamp and the Synced/Local pill are OUT.
  // Asserted as an ABSENCE so re-adding one goes red.
  await expect(
    page.getByText(/QuickBooks/i),
    'ruling 3 removed "⇅ Sync from QuickBooks" from SET-11 and something drew it again',
  ).toHaveCount(0);
  await expect(
    page.getByText(/Read-only/),
    "every account is LOCAL since ruling 3, so no row may say Read-only",
  ).toHaveCount(0);

  // A sub-tab is a URL SEGMENT, so a link to one is sendable.
  await openSubTab(page, "GL mapping");
  await expect(page).toHaveURL(new RegExp(`${tenant()}/settings/accounting/mapping$`));
  await openSubTab(page, "Finance controls");
  await expect(page).toHaveURL(new RegExp(`${tenant()}/settings/accounting/controls$`));
});

// ═══════════════════════════════════════════════════════════════════════════
// 2 · THE FULL 33-ACCOUNT CHART EVERY TENANT NOW SEEDS (B-9, 2026-08-18)
// ═══════════════════════════════════════════════════════════════════════════

// B-9, PO 2026-08-17: *"9 - A full ~40 accounts for every tenant, as you said"*.
// The build record settles the exact figure: **33** — 25 signed-chart rows plus
// 8 cost rows. Listed here by CODE, in the seed's own order, because a count
// alone would pass on 33 of the wrong rows.
const SEEDED_CHART_CODES = [
  "1000", "1010", "1200", "1210", "2300", "2400", "3000",
  "4100", "4105", "4110", "4115", "4120", "4130", "4140", "4145", "4150",
  "4160", "4170", "4180", "4190", "4200", "4210",
  "5100", "5110", "5120", "5130", "5140", "5145", "5200", "5300",
  "6800", "6900", "6950",
];

const COST_CODES = ["5100", "5110", "5120", "5130", "5140", "5145", "5200", "5300"];

test(`CR-008 SET-11.coa · all 33 seeded accounts render, with the ten services' revenue rows ${APP_SERVER_TAG}`, async ({
  page,
}) => {
  test.setTimeout(WALK_BUDGET_MS);
  await signInAsAdmin(page);
  await page.goto(ACCOUNTING);
  await expect(chartTable(page)).toBeVisible({ timeout: 60_000 });

  expect(SEEDED_CHART_CODES, "the seed list in this spec is not 33 codes").toHaveLength(33);
  for (const code of SEEDED_CHART_CODES) {
    await expect(
      chartRow(page, code),
      `account ${code} is missing from the chart — B-9 seeds all 33 for every tenant`,
    ).toHaveCount(1);
  }

  // The rows that only exist because New mandate 4 seeds ALL TEN services, not
  // the two this tenant switched on. Named, because "33 rows" would pass with
  // the wrong eight.
  await expect(chartRow(page, "4160"), "storm water revenue (4160) is not seeded").toContainText(
    "Storm water",
  );
  await expect(chartRow(page, "4170"), "thermal/heat revenue (4170) is not seeded").toContainText(
    "Thermal/Heat",
  );
  await expect(chartRow(page, "4150"), "the solar/battery capacity row is not seeded").toContainText(
    "Capacity (solar/battery)",
  );

  // The tenant's OWN authority accounts sit beside the seed, in the 2200 series
  // B5 line 74 seeds to nobody (BR-BIL-069 — a tenant mints its own).
  await expect(chartRow(page, "2200-01")).toContainText("City utility tax");
  await expect(chartRow(page, "2200-02")).toContainText("State water tax");

  // Every row carries a status pill, and every seeded row is Active.
  await expect(chartRow(page, "1000")).toContainText("Active");
});

// ═══════════════════════════════════════════════════════════════════════════
// 3 · 4180 RENDERS AS AWAITING A FINANCE SIGNATURE, NOT AS A CONFIGURED ROW
// ═══════════════════════════════════════════════════════════════════════════

test(`CR-008 B-8 · 4180 Budget billing variance shows its awaiting-finance state on the chart ${APP_SERVER_TAG}`, async ({
  page,
}) => {
  test.setTimeout(WALK_BUDGET_MS);
  await signInAsAdmin(page);
  await page.goto(ACCOUNTING);
  await expect(chartTable(page)).toBeVisible({ timeout: 60_000 });

  const row = chartRow(page, "4180");
  await expect(row, "4180 Budget billing variance is not seeded (B-8)").toHaveCount(1);
  await expect(row).toContainText("Budget billing variance");
  await expect(row, "4180 must carry the twelfth designation").toContainText(
    "Budget-plan difference",
  );
  // 4180 renders as an ORDINARY CONFIGURED ROW, and since 2026-08-18 that is
  // CORRECT — see the inversion below. Until that date it was the FINDING 1
  // defect; the row is unchanged and its meaning is not.

  // ⚠ **INVERTED 2026-08-19 BY THE CLOSING WALKTHROUGH — THE TRIPWIRE FIRED,
  // EXACTLY AS THE BLOCK IT REPLACES SAID IT WOULD.**
  //
  // What stood here asserted BR-LED-037's *"the eight 5xxx cost rows are a
  // proposal awaiting a finance signature"* note, and said in its own words:
  // *"A red on this line is not a regression. It is the re-sign arriving … it
  // means: replace this block with `await expect(costNote).toHaveCount(0)`,
  // then go and re-read FINDINGS 1 and 2."* On run 3 (2026-08-19) it went red
  // with precisely that message. **The re-sign has landed**: `chart.py` records
  // the Product Owner re-signing all nine rows — 4180 plus every row of
  // `COST_OF_SERVICE_CHART` — in the working chat session on 2026-08-18, so
  // `PENDING_FINANCE_RE_SIGN` and `PENDING_FINANCE_RE_SIGN_COST` are BOTH `()`
  // and every seeded row carries `signed=True`. B4/B5 were NOT edited and stay
  // ❄️ FROZEN; the re-sign is an addendum, which is HUMAN-GUIDE §6's own shape.
  //
  // **So the assertion flips and keeps its job.** The rule it now pins is the
  // MIRROR of US-LED-017 TC-5 — the direction this product actually shipped
  // wrong, and the direction nothing was watching: *no surface presents a
  // SIGNED code as unsigned.* `services._chart_row` used to derive the flag
  // from cost-section MEMBERSHIP (`is_cost_of_service_code`), so on the morning
  // of the re-sign S56 told a finance reviewer that eight RATIFIED accounts
  // still needed their attention. Fixed in `5a85bec` — the flag now comes from
  // the two pending registers, which are derived from each row's own `signed`
  // field and cannot disagree with it (DEF-260).
  //
  // This is also the screen-level half of the sign-off rule of 2026-08-11: a
  // ratification is only recorded when *"a test asserts the ratified figure so
  // drift goes RED"*. Re-introduce an unsigned row without wiring its sentence,
  // or resurrect the membership derivation, and this line is where it shows.
  const costNote = page.getByText("are a proposal awaiting a finance signature", { exact: false });
  await expect(
    costNote,
    "a chart row still calls itself a proposal awaiting a finance signature — the PO re-signed " +
      "all nine rows on 2026-08-18 and both pending registers are empty, so NO row may say this",
  ).toHaveCount(0);
  // And the contrast that stops the count above being vacuous: the eight cost
  // rows are still ON the chart. They were re-signed, not withdrawn — a green
  // that came from the section having vanished would prove the opposite thing.
  for (const code of COST_CODES) {
    await expect(
      chartRow(page, code),
      `${code} is missing from the chart — the cost section was re-signed, not removed`,
    ).toHaveCount(1);
  }
});


// ── FINDING 1 — ✅ CLOSED 2026-08-19 (DEF-260 fixed in 5a85bec) ────────────
// The finding as it was written on 2026-08-18 is kept verbatim below, because
// the measurement in it is the only run in which the bug was observable and a
// deleted finding teaches nobody. Read to the RESOLVED note for what is true
// today.
//
// **NOTHING IN THE PRODUCT MARKS 4180 AS UNSIGNED, and the server contradicts
// itself in one response.** MEASURED on the live stack, from
// `GET /ledger/accounts?f.status=active`:
//
//     4180 Budget billing variance   finance_signed = true
//     pending_finance_re_sign        = ["4180"]
//
// Both fields are in the SAME payload. The register says 4180 awaits a finance
// re-sign; the row says it is signed. `apps/ledger/services._chart_row:778`
// computes the flag as
//
//     "finance_signed": not chart.is_cost_of_service_code(account.code)
//
// — i.e. it knows only about the EIGHT 5xxx cost rows and has never read
// `chart.PENDING_FINANCE_RE_SIGN`. That was harmless from 2026-08-11, when
// `PENDING_FINANCE_RE_SIGN` was empty, until B-8 put 4180 into it on
// 2026-08-18. The row-level flag was simply never widened with the register.
//
// **The consequence, in the CR's own words.** CR-008's third-set record claims:
// *"The S56 GL-mapping flag `awaiting_finance_re_sign` now reports an unsigned
// CODE as well as an unseeded designation, so 4180 renders with its pending
// state instead of as a plain configured row."* The first half is true. The
// second half is false on BOTH surfaces that could show it — the chart tab
// (this finding) and the GL map (FINDING 2) — so a finance reviewer opening
// Settings → Accounting today sees 4180 presented exactly like 1000 Cash.
// US-LED-017 TC-5 says in as many words: *no surface presents an UNSIGNED code
// as signed.*
//
// ✅ **RESOLVED 2026-08-19 BY THE CLOSING WALKTHROUGH — `test.fail` REMOVED,
// AND THIS IS NOW A LIVE REGRESSION TEST.** Two things landed on 2026-08-18,
// after everything above this line was written, and they have to be read
// together:
//
//   1. **The CAUSE was fixed** in `5a85bec`. `services._chart_row` no longer
//      derives the flag from cost-section membership; it reads both pending
//      registers, which are themselves derived from each row's own `signed`
//      field and so cannot disagree with it. The measurement quoted above —
//      `finance_signed: true` beside `pending_finance_re_sign: ["4180"]` in one
//      payload — is no longer reproducible on any input. **DEF-260 is FIXED.**
//   2. **The SYMPTOM vanished** the same day: the Product Owner re-signed 4180
//      and all eight cost rows, so `PENDING_FINANCE_RE_SIGN` is `()` and there
//      is no unsigned code left for any surface to mis-report.
//
// **Fixing the cause is what closes this finding; the re-sign only hid it.**
// Had the re-sign landed alone, this would still be an open latent defect, and
// that is exactly what FINDING 2 below still is.
//
// **What this test asserts NOW, and why it is the assertion worth keeping.**
// Run 3 could not re-check the original claim — with the register empty there
// is no unsigned row to look at — so re-stating it would have left a test
// pinned on a condition that can never occur again, which reports nothing
// forever. It asserts instead the state the PO actually ratified, on the screen
// a finance reviewer reads: **every seeded row, 4180 included, presents as
// settled, and none of them carries the proposal sentence.** That is the mirror
// of US-LED-017 TC-5 and it is the direction this product shipped wrong. It
// goes RED the day a membership-derived flag comes back, the day an unsigned
// row is seeded without its sentence being wired, or the day someone edits ❄️
// B4/B5 to undo the re-sign rather than filing an addendum.
test(
  `CR-008 DEF-260 · every re-signed chart row presents as settled, 4180 included ${APP_SERVER_TAG}`,
  async ({ page }) => {
    test.setTimeout(WALK_BUDGET_MS);
    await signInAsAdmin(page);
    await page.goto(ACCOUNTING);
    await expect(chartTable(page)).toBeVisible({ timeout: 60_000 });

    // 4180 is the row the PO was shown by name. It is on the chart, it is
    // Active, and it says nothing about awaiting anybody.
    await expect(
      chartRow(page, "4180"),
      "4180 Budget billing variance is not on the chart — B-8 seeds it",
    ).toHaveCount(1);
    await expect(
      chartRow(page, "4180"),
      "4180 was finance re-signed on 2026-08-18 and must not present as awaiting a signature",
    ).not.toContainText(/proposed|not approved|awaiting a finance signature/i);

    // 4190 sits beside it in the same seed and was signed from the start. It
    // was the CONTRAST row while this was a finding, and it stays here: if a
    // future change makes the whole chart silent about signatures for the wrong
    // reason, both halves go quiet together and only the row-level count above
    // would have noticed.
    await expect(
      chartRow(page, "4190"),
      "4190 is finance-signed and must not carry an unsigned sentence",
    ).not.toContainText(/proposed|not approved/i);
  },
);

// ═══════════════════════════════════════════════════════════════════════════
// 4 · THE CHART'S OWN TOOLBAR — search and the type filter
// ═══════════════════════════════════════════════════════════════════════════

test(`CR-008 SET-11.coa · search and the type filter narrow the chart on screen ${APP_SERVER_TAG}`, async ({
  page,
}) => {
  test.setTimeout(WALK_BUDGET_MS);
  await signInAsAdmin(page);
  await page.goto(ACCOUNTING);
  await expect(chartTable(page)).toBeVisible({ timeout: 60_000 });

  const before = await chartTable(page).locator("tbody tr").count();
  expect(before, "the chart came back with fewer rows than the seed plants").toBeGreaterThanOrEqual(
    33,
  );

  const search = page.getByPlaceholder("Code or name");
  await search.fill("4180");
  await expect(chartTable(page).locator("tbody tr")).toHaveCount(1, { timeout: 30_000 });
  await expect(chartTable(page).locator("tbody tr").first()).toContainText(
    "Budget billing variance",
  );

  await search.fill("");
  await expect(chartTable(page).locator("tbody tr").nth(32)).toBeVisible({ timeout: 30_000 });

  // The type filter enumerates the LIVE vocabulary (BR-REP-006), so Expense
  // must return the eight cost rows plus the three 6xxx rows and nothing else.
  const typeFilter = page.locator("label", { hasText: "Type" }).locator("select.input").first();
  await typeFilter.selectOption({ label: "Expense" });
  await expect(chartRow(page, "5100")).toHaveCount(1, { timeout: 30_000 });
  await expect(chartRow(page, "6900")).toHaveCount(1);
  await expect(
    chartRow(page, "4100"),
    "the Expense filter still shows a revenue account",
  ).toHaveCount(0);
});

// ═══════════════════════════════════════════════════════════════════════════
// 5 · THE FIVE-SECTION GL MAP (ruling 9 made it five, not r10's four)
// ═══════════════════════════════════════════════════════════════════════════

test(`CR-008 SET-11.map · all five sections render with this tenant's real rows ${APP_SERVER_TAG}`, async ({
  page,
}) => {
  test.setTimeout(WALK_BUDGET_MS);
  await signInAsAdmin(page);
  await page.goto(MAPPING);

  // The five headings, in the order the CR lists them. §5 is the PO's ruling 9
  // (*"9 make it separate"*) and is the one r10 does not draw.
  for (const heading of [
    "Service revenue accounts",
    "Tax authority liability accounts",
    "Payments and deposits",
    "Charges and fees",
    "Adjustment reasons",
  ]) {
    await expect(
      page.getByRole("heading", { name: heading, exact: true }),
      `GL mapping section "${heading}" is missing`,
    ).toBeVisible({ timeout: 60_000 });
  }

  // §1 — the two services this tenant sells, each with BOTH pointers resolved
  // to a code and a name (never a raw uuid, DEF-206's own lesson).
  const services = tableAfter(page, "Service revenue accounts");
  await expect(settingsRow(services, "Electric")).toContainText("4100");
  await expect(settingsRow(services, "Electric")).toContainText("Electric usage");
  await expect(settingsRow(services, "Electric")).toContainText("4105");
  await expect(settingsRow(services, "Water")).toContainText("4110");
  await expect(settingsRow(services, "Water")).toContainText("4115");
  // BR-TEN-026 — a service that is OFF holds no `tenant_services` GL row, so it
  // is COUNTED rather than listed. Eight of the ten are off on this tenant.
  await expect(
    page.getByText("services are switched off and hold no accounts", { exact: false }),
    "the off-services sentence is missing — a reader cannot tell why eight services are absent",
  ).toBeVisible();

  // §2 — BR-BIL-069: one liability account PER AUTHORITY, not one per tax.
  const taxes = tableAfter(page, "Tax authority liability accounts");
  await expect(settingsRow(taxes, "City utility tax")).toContainText("2200-01");
  await expect(settingsRow(taxes, "State water tax")).toContainText("2200-02");
  await expect(
    page.getByText("is the only place a tax authority", { exact: false }),
    "§2 does not say it is the one editor",
  ).toBeVisible();

  // §3a — the four designations a payment resolves through, READ-ONLY here
  // because a designation moves by telling a CHART ROW it holds the role.
  const designations = tableAfter(page, "Payments and deposits");
  for (const [label, code] of [
    ["Money in the bank", "1000"],
    ["Taken but not yet banked", "1010"],
    ["Unapplied cash and credit balances", "2400"],
    ["Customer deposits held", "2300"],
  ] as const) {
    await expect(
      settingsRow(designations, label),
      `the "${label}" designation does not resolve to ${code}`,
    ).toContainText(code);
  }

  // §3b — CR-008 second-set ruling 1's genuine gap: the tender→cash column.
  const tenders = tableAfter(page, "Where each way of paying lands", "h4");
  await expect(settingsRow(tenders, "Card")).toBeVisible();
  await expect(settingsRow(tenders, "Check")).toBeVisible();
  await expect(settingsRow(tenders, "Cash")).toBeVisible();
  // B-10 changed this sentence in the same slice that wired the posting. It
  // must no longer say the setting moves no money.
  await expect(
    page.getByText("a mapped tender", { exact: false }),
    "§3's sentence still describes the pre-B-10 behaviour (nothing posts yet)",
  ).toBeVisible();

  // §4 — the GAP banner is a RULE (BR-BIL-010 refuses the WHOLE bill), so it
  // must name a count and the codes, not gesture at a problem.
  const gap = page.getByText("have no account to post to", { exact: false });
  await expect(gap, "§4's GAP banner is missing on a tenant with unmapped charges").toBeVisible();
  // The COUNT and at least one CODE, as a shape rather than as figures. The
  // tenant's charge list is live data that other lanes edit — it read 30
  // unmapped when this spec was written and 23 when it first ran — so a
  // hardcoded count would be a spec that goes red on somebody else's work.
  await expect(
    gap,
    "the GAP banner names no count and no charge code, so nobody can act on it",
  ).toContainText(/\d+ charges have no account to post to \([A-Z0-9-]+/);
  await expect(
    page.getByText(
      "A bill carrying one of them cannot be issued until it does.",
      { exact: false },
    ),
    "the GAP banner does not state the consequence a bill run will hit",
  ).toBeVisible();

  // §5 — ruling 9's own section.
  const reasons = tableAfter(page, "Adjustment reasons");
  await expect(settingsRow(reasons, "Goodwill credit")).toBeVisible();
  await expect(settingsRow(reasons, "Billing error correction")).toBeVisible();
  await expect(
    page.getByText(
      "A credit given for a billing error and one given as goodwill are different things to an auditor.",
      { exact: false },
    ),
    "§5 does not explain why the reasons are mapped separately",
  ).toBeVisible();
});

// ── FINDING 3 ──────────────────────────────────────────────────────────────
// **The §4 GAP banner names five charge codes out of twenty-three and does not
// say it stopped at five.** Read on screen, verbatim:
//
//   *"23 charges have no account to post to (AFTER-HRS, BULK-WATER, CC-CONV,
//    CONN, DAMAGE). A bill carrying one of them cannot be issued until it
//    does."*
//
// `SettingsAccountingTab.tsx:840` slices the list to five deliberately, which
// is right — twenty-three codes in a banner is a wall. What is missing is the
// SENTENCE saying so. A reader sees a count of 23 and a parenthesis of 5 and
// has no way to know whether the parenthesis is the whole list, a sample, or
// the five that matter most; and BR-BIL-010 makes this banner the only warning
// before a bill run fails ATOMICALLY on one of the eighteen it did not name.
//
// The import modal one tab away already solves the identical problem in the
// identical situation — *"{{count}} more rows are not shown here."* — so this
// is a missing sentence rather than a design question.
//
// TO INVERT: when the banner says how many codes it did not list, delete
// `test.fail`; the assertion below states the rule.
test.fail(
  `CR-008 FINDING 3 · the GAP banner truncates its code list without saying so ${APP_SERVER_TAG}`,
  async ({ page }) => {
    test.setTimeout(WALK_BUDGET_MS);
    await signInAsAdmin(page);
    await page.goto(MAPPING);

    const gap = page.getByText("have no account to post to", { exact: false });
    await expect(gap).toBeVisible({ timeout: 60_000 });
    const text = (await gap.innerText()).trim();
    const count = Number(/^(\d+) charges/.exec(text)?.[1] ?? "0");
    const listed = (/\(([^)]*)\)/.exec(text)?.[1] ?? "").split(", ").filter(Boolean).length;
    expect(count, "this tenant has no unmapped charges, so the banner proves nothing").toBeGreaterThan(
      listed,
    );
    // THE RULE: a list that stops short says how much it left out.
    expect(
      /more|not shown|and \d+ others/i.test(text),
      `the banner names ${listed} of ${count} codes and never says the list is cut short: ${JSON.stringify(text)}`,
    ).toBe(true);
  },
);

// ═══════════════════════════════════════════════════════════════════════════
// 6 · ALL 12 DESIGNATIONS PLACED — and where the unsigned-code flag surfaces
// ═══════════════════════════════════════════════════════════════════════════

const ALL_TWELVE_DESIGNATIONS: readonly (readonly [string, string])[] = [
  ["Cash in the bank", "1000"],
  ["Money taken, not yet at the bank", "1010"],
  ["Money customers owe you", "1200"],
  ["Earned but not yet billed", "1210"],
  ["Customer deposits you hold", "2300"],
  ["Credit sitting on an account", "2400"],
  ["Opening balances brought in", "3000"],
  ["Budget-plan difference", "4180"],
  ["Top-up to a minimum bill", "4190"],
  ["Fees the bank charged you", "6800"],
  ["Debt written off as uncollectable", "6900"],
  ["Interest owed on deposits held", "6950"],
];

test(`CR-008 B-8/B-9 · all twelve GL designations resolve to a seeded account on S56 ${APP_SERVER_TAG}`, async ({
  page,
}) => {
  test.setTimeout(WALK_BUDGET_MS);
  await signInAsAdmin(page);
  // The five-section SET-11 map shows only the FOUR payment designations; the
  // full twelve live on the same shared panel, reached from Finance → General
  // Ledger → "Chart of accounts & mapping". Same component, same server flag.
  await page.goto(GL_CHART_VIEW);

  const map = finTable(page, "What each kind of money lands in");
  await expect(map, "the designation map does not render on S56").toBeVisible({ timeout: 60_000 });
  expect(ALL_TWELVE_DESIGNATIONS, "this spec's designation list is not twelve").toHaveLength(12);

  for (const [label, code] of ALL_TWELVE_DESIGNATIONS) {
    await expect(
      settingsRow(map, label),
      `the "${label}" designation has no account — SEEDED_DESIGNATIONS is meant to be all 12 since B-8`,
    ).toContainText(code);
  }
  // PENDING_FINANCE_RESIGN (unseeded designations) is EMPTY since B-8, so no
  // row may render the "needs a finance signature before it can exist" state.
  await expect(
    page.getByText("this one needs a finance signature before it can exist", { exact: false }),
    "a designation still has NO seeded account — PENDING_FINANCE_RESIGN should be empty since B-8",
  ).toHaveCount(0);
  // And nothing may be unresolved, which is a different and worse state.
  await expect(
    page.getByText("No live account has this role.", { exact: false }),
    "a designation is unresolved on a freshly seeded tenant",
  ).toHaveCount(0);
});

// ── FINDING 2 — the SECOND surface, and a DIFFERENT mechanism ──────────────
// **The `awaiting_finance_re_sign` flag is SERVED for an unsigned code and the
// screen cannot render it.** This is not a duplicate of FINDING 1: there the
// SERVER answers the wrong thing; here the server answers correctly and the
// SCREEN throws it away. Both have to be fixed, and fixing either one alone
// leaves 4180 unmarked on the other surface. CR-008's third-set record says,
// of B-8:
//
//   *"The S56 GL-mapping flag `awaiting_finance_re_sign` now reports an
//    unsigned CODE as well as an unseeded designation, so 4180 renders with its
//    pending state instead of as a plain configured row."*
//
// The first half is true — `apps/ledger/chart_api.py:455` sets the flag when
// `account["code"] in chart.PENDING_FINANCE_RE_SIGN`, which is exactly 4180.
// **The second half is false on screen.** `GlMappingPanels` in
// `features/ledger/ChartOfAccountsPanel.tsx` reads the flag only in the branch
// where `account_id === null`:
//
//     {row.account_id !== null ? (<button …>{code} · {name}</button>)
//       : row.awaiting_finance_re_sign ? (…) : (…)}
//
// 4180 HAS an account id, so it takes the first branch and renders exactly like
// 1000 Cash. The widened server flag is unreachable for the case it was widened
// for — hard-won law 2, *built is not wired*, on the one row a finance reviewer
// is being asked to sign.
//
// ⚠ The comment that stood here until the first run said *"the chart tab DOES
// say it, so nothing is hidden from a person who goes looking"*. **THE RUN
// FALSIFIED THAT** — see FINDING 1. Neither surface says it. Left in the record
// rather than quietly corrected, because it is exactly the assumption a code
// reading produces and only a browser disproves (hard-won law 6).
//
// ⚠ **THE SAME IN-FLIGHT RE-SIGN APPLIES** (see FINDING 1). Once 4180 is
// signed, no seeded code is pending and this branch is unreachable for a real
// row — latent, not fixed. The branch is wrong whichever register is empty.
//
// ⚠ **MEASURED AGAIN 2026-08-19, AND THE PIN IS NOW LATENT — SAY SO OUT LOUD.**
// The re-sign of 2026-08-18 landed, so `PENDING_FINANCE_RE_SIGN` is `()` and no
// seeded row is served the flag any more. FINDING 1's CAUSE was fixed with it
// (`5a85bec`, server side); **this one's was not** — `GlMappingPanels` still
// reads `awaiting_finance_re_sign` only in the `account_id === null` branch, and
// DEF-261/DEF-274 stay open on exactly that line. The consequence for THIS TEST
// is worth stating rather than leaving for someone to discover: with no pending
// code in existence it can no longer go green even after the branch is fixed,
// so it reports "still failing" for two different reasons and cannot tell them
// apart. **It is kept as the marker of where the defect lives, and the alarm
// that actually fires lives in the backend suite instead** — the day a code
// re-enters either register, `PENDING_FINANCE_RE_SIGN` is non-empty again and
// this file's run 3 note is the thing to re-read.
//
// TO INVERT: when the map renders a pending code's state — which needs a pending
// code to exist — delete `test.fail` and the assertion below flips to
// `toBeVisible()`.
test.fail(
  `CR-008 FINDING 2 · the GL map ignores the awaiting-signature flag it is served ${APP_SERVER_TAG}`,
  async ({ page }) => {
    test.setTimeout(WALK_BUDGET_MS);
    await signInAsAdmin(page);
    await page.goto(GL_CHART_VIEW);

    const map = finTable(page, "What each kind of money lands in");
    const row = settingsRow(map, "Budget-plan difference");
    await expect(row).toContainText("4180", { timeout: 60_000 });
    // THE RULE: an unsigned code must not be presented as settled anywhere it
    // is presented at all (US-LED-017 TC-5). This is the assertion that fails
    // today and must pass once the map honours the flag it is served.
    await expect(
      row,
      "the GL map presents unsigned 4180 exactly like a signed account — the served " +
        "`awaiting_finance_re_sign: true` is never read on this branch",
    ).toContainText(/finance/i);
  },
);

// ═══════════════════════════════════════════════════════════════════════════
// 7 · THE CSV IMPORT — upload → map columns → validate → load, and its REFUSAL
// ═══════════════════════════════════════════════════════════════════════════

test(`CR-008 SET-11.coa · the CSV import validates, refuses a bad file, then loads a good one ${APP_SERVER_TAG}`, async ({
  page,
}) => {
  test.setTimeout(WALK_BUDGET_MS);
  await signInAsAdmin(page);
  await page.goto(ACCOUNTING);
  await expect(chartTable(page)).toBeVisible({ timeout: 60_000 });

  const goodCode = `4901-${STAMP}`;
  const openImport = () => page.getByRole("button", { name: "Import from a file" }).click();

  // ── ACT 1: a file with one NEW row, one row already in the chart, and one
  // row whose type is nonsense. The whole load must be refused. ──────────────
  await openImport();
  const dialog = page.getByRole("dialog", { name: "Import a chart of accounts" });
  await expect(dialog).toBeVisible({ timeout: 30_000 });
  await expect(
    dialog.getByText("Choose your file, say which column is which", { exact: false }),
    "the import modal does not state its four acts",
  ).toBeVisible();

  const mixed =
    "code,name,type\n" +
    `${goodCode},QA imported revenue ${STAMP},revenue\n` +
    "1000,Cash,asset\n" +
    `4902-${STAMP},QA broken row ${STAMP},widget\n`;
  await dialog.locator("#chart-import-file").setInputFiles({
    name: `qa-chart-${STAMP}.csv`,
    mimeType: "text/csv",
    buffer: Buffer.from(mixed, "utf8"),
  });
  await expect(dialog.getByText("3 rows found.", { exact: false })).toBeVisible();

  // Step 2 — the mapping. The headers are named `code`/`name`/`type` so the
  // guess should already be right; asserted rather than assumed, because a
  // guess that silently missed would make act 3 meaningless.
  await expect(dialog.locator("#chart-import-code")).toHaveValue("code");
  await expect(dialog.locator("#chart-import-name")).toHaveValue("name");
  await expect(dialog.locator("#chart-import-type")).toHaveValue("type");

  await dialog.getByRole("button", { name: "Check the file" }).click();
  await expect(
    dialog.getByText("1 to add · 1 already here · 1 we cannot read · 0 listed twice"),
    "the validate step does not report the four outcomes a person needs",
  ).toBeVisible({ timeout: 60_000 });
  await expect(dialog.getByText("Will be added")).toBeVisible();
  await expect(dialog.getByText("Already here — left alone")).toBeVisible();
  await expect(dialog.getByText("Cannot be read")).toBeVisible();
  await expect(
    dialog.getByText("the type must be asset, liability, equity, revenue or expense", {
      exact: false,
    }),
    "the bad row does not say WHY it cannot be read",
  ).toBeVisible();
  await expect(
    dialog.getByText("1 rows need fixing before anything can be loaded. Nothing has been changed."),
    "a file with a bad row was not refused whole",
  ).toBeVisible();
  // BR-SHL-025 — Load stays VISIBLE and disabled with its reason.
  const load = dialog.getByRole("button", { name: /^Add \d+ accounts$/ });
  await expect(load, "Load is hidden rather than disabled on a blocked file").toBeVisible();
  await expect(load).toBeDisabled();
  await expect(load).toHaveAttribute("title", "Fix the rows below first.");

  // NOTHING was written. Proved by closing and reading the chart.
  await dialog.getByRole("button", { name: "Close" }).click();
  await expect(
    chartRow(page, goodCode),
    "a refused import still created a row — the load is meant to be all-or-nothing",
  ).toHaveCount(0);

  // ── ACT 2: the same file with the bad row removed. It loads. ──────────────
  await openImport();
  await expect(dialog).toBeVisible({ timeout: 30_000 });
  const clean = "code,name,type\n" + `${goodCode},QA imported revenue ${STAMP},revenue\n1000,Cash,asset\n`;
  await dialog.locator("#chart-import-file").setInputFiles({
    name: `qa-chart-clean-${STAMP}.csv`,
    mimeType: "text/csv",
    buffer: Buffer.from(clean, "utf8"),
  });
  await dialog.getByRole("button", { name: "Check the file" }).click();
  await expect(
    dialog.getByText("1 to add · 1 already here · 0 we cannot read · 0 listed twice"),
  ).toBeVisible({ timeout: 60_000 });
  await dialog.getByRole("button", { name: "Add 1 accounts" }).click();
  await expect(dialog.getByText("1 accounts were added.")).toBeVisible({ timeout: 60_000 });
  await dialog.getByRole("button", { name: "Close" }).click();

  // Hard-won law 2 — the table below must not still show the pre-import chart.
  await expect(
    chartRow(page, goodCode),
    "the imported account is not in the table the import modal sits on top of",
  ).toHaveCount(1, { timeout: 30_000 });
  await expect(chartRow(page, goodCode)).toContainText(`QA imported revenue ${STAMP}`);

  // ── ACT 3: RE-RUNNABILITY, proved rather than claimed. The identical file,
  // imported again, dedupes on code and adds nothing. ───────────────────────
  await openImport();
  await expect(dialog).toBeVisible({ timeout: 30_000 });
  await dialog.locator("#chart-import-file").setInputFiles({
    name: `qa-chart-again-${STAMP}.csv`,
    mimeType: "text/csv",
    buffer: Buffer.from(clean, "utf8"),
  });
  await dialog.getByRole("button", { name: "Check the file" }).click();
  await expect(
    dialog.getByText("0 to add · 2 already here · 0 we cannot read · 0 listed twice"),
    "a re-import of the same file did not dedupe on code",
  ).toBeVisible({ timeout: 60_000 });
  await dialog.getByRole("button", { name: "Close" }).click();
});

// ═══════════════════════════════════════════════════════════════════════════
// 8 · ACCOUNTING IS THE ONE EDITOR — proved by the REFUSAL somewhere else
// ═══════════════════════════════════════════════════════════════════════════

test(`CR-008 ruling 2 · Plans & Rates shows a charge's GL account and refuses to edit it ${APP_SERVER_TAG}`, async ({
  page,
}) => {
  test.setTimeout(WALK_BUDGET_MS);
  await signInAsAdmin(page);
  await page.goto(`/${tenant()}/plans-rates/charge-codes`);

  // Open the charge a late fee posts through — the one BR-BIL-010 will refuse a
  // whole bill on if it has no income account.
  const lateRow = page.locator("tbody tr").filter({ hasText: "Late payment fee" }).first();
  await expect(lateRow, "the charge-codes tab does not list the late fee").toBeVisible({
    timeout: 60_000,
  });
  await lateRow.getByRole("button", { name: "Edit", exact: true }).click();

  // THE RULE, on screen, in the form that used to own the picker.
  await expect(
    page.getByText("This account is set in Settings, under Accounting."),
    "S12 does not say where a charge's GL account is edited — ruling 2's whole point",
  ).toBeVisible({ timeout: 30_000 });
  // ⚠ It must NOT be the older "arrives with the Finance module" sentence
  // (DEF-206/DEF-231) — an absence claim that outlived the absence.
  await expect(
    page.getByText(/arrives with the Finance module/i),
    "a screen still claims the chart of accounts is not built (DEF-206/DEF-231 shape)",
  ).toHaveCount(0);

  // No editable control for the account exists on this form any more.
  await expect(
    page.locator("#gl_account_id"),
    "S12 still offers a GL picker — that is a SECOND editor, which ruling 2 removed",
  ).toHaveCount(0);

  // And the link goes to the one editor.
  await page.getByRole("button", { name: "Open Accounting settings" }).click();
  await expect(page).toHaveURL(new RegExp(`${tenant()}/settings/accounting/mapping$`), {
    timeout: 30_000,
  });
  await expect(page.getByRole("heading", { name: "Charges and fees", exact: true })).toBeVisible({
    timeout: 60_000,
  });
});

test(`CR-008 ruling 2 · Taxes & fees shows the authority's account and refuses to edit it ${APP_SERVER_TAG}`, async ({
  page,
}) => {
  test.setTimeout(WALK_BUDGET_MS);
  await signInAsAdmin(page);
  await page.goto(`/${tenant()}/plans-rates/taxes-fees`);

  const taxRow = page.locator("tbody tr").filter({ hasText: "City utility tax" }).first();
  await expect(taxRow, "the taxes tab does not list the city tax").toBeVisible({ timeout: 60_000 });
  await taxRow.getByRole("button", { name: "Edit", exact: true }).click();

  // ⚠ EDIT IS NO LONGER A MODAL (CR-013 P4, PO 2026-08-20: *"Wizards for each
  // type - no modal;"*). The pencil now opens TAX-02, a full-page four-step
  // route, and the liability account lives on step 3 — so this walk reaches it
  // through the rail instead of finding it in a dialog. The ASSERTIONS are
  // unchanged, which is the point: CR-008 ruling 2 survived the reshape.
  await expect(
    page.getByRole("heading", { level: 1 }),
    "the pencil did not open the tax wizard",
  ).toBeVisible({ timeout: 60_000 });
  await page.getByRole("button", { name: "Remittance", exact: true }).click();

  await expect(
    page.getByText("This account is set in Settings, under Accounting."),
    "TAX-02 step 3 does not point at the one editor",
  ).toBeVisible({ timeout: 30_000 });
  await expect(
    page.locator("#liability_gl_account_id"),
    "TAX-02 still offers a liability-account picker — a second editor",
  ).toHaveCount(0);
});

// ═══════════════════════════════════════════════════════════════════════════
// 9 · PICK-TIME VALIDATION — the account is checked WHEN IT IS PICKED
// ═══════════════════════════════════════════════════════════════════════════

// CR-008 second-set ruling 3: *"Validate the account WHEN IT IS PICKED, not
// only when a bill runs"* — because *"a mapping can look correct on screen for
// weeks and fail on the day a bill runs, which is when a utility can least
// afford it."*
//
// Proving that in a browser needs a picker holding an account that has stopped
// being live SINCE it was drawn, which is exactly the real-world case: a clerk
// opens the mapping page, somebody retires the account, the clerk saves. Two
// pages in one session reproduce it honestly — no API call, no forged state.
test(`CR-008 ruling 3 · picking a retired account is refused at the pick, on screen ${APP_SERVER_TAG}`, async ({
  page,
  context,
}) => {
  test.setTimeout(WALK_BUDGET_MS);
  await signInAsAdmin(page);

  const code = `4903-${STAMP}`;
  await page.goto(ACCOUNTING);
  await expect(chartTable(page)).toBeVisible({ timeout: 60_000 });
  await addAccountOnScreen(page, code, `QA pick-time ${STAMP}`, "Revenue");

  // The clerk's page: the GL map, with the picker open and the account chosen.
  const clerk = await context.newPage();
  await clerk.goto(MAPPING);
  const reasons = tableAfter(clerk, "Adjustment reasons");
  await expect(reasons).toBeVisible({ timeout: 60_000 });
  await settingsRow(reasons, "Goodwill credit").getByRole("button", { name: "Change" }).click();
  const picker = clerk.locator("#default_gl_account_id");
  await expect(picker, "§5's account picker did not open").toBeVisible({ timeout: 30_000 });
  await picker.selectOption({ label: `${code} — QA pick-time ${STAMP}` });

  // Meanwhile, on the chart, somebody retires it (BR-TEN-034 / IS-1 —
  // deactivate, never delete).
  await page.getByPlaceholder("Code or name").fill(code);
  await expect(chartRow(page, code)).toHaveCount(1, { timeout: 30_000 });
  await chartRow(page, code).getByRole("button", { name: "Retire", exact: true }).click();
  await expect(chartRow(page, code), "the account was not retired").toContainText("Retired", {
    timeout: 30_000,
  });

  // The clerk saves the pick that was legal when it was made.
  await clerk.getByRole("button", { name: "Save account" }).click();
  // ⚠ `.first()` IS LOAD-BEARING AND IS NOT A WORKAROUND. The refusal renders
  // TWICE by the shared FormModal's design — once as the field error on
  // `#default_gl_account_id`, once as the form-level `role=alert` summary — and
  // a bare `getByText` is a strict-mode violation, which reports as *"a retired
  // account was accepted"* when the opposite happened. Both copies are asserted
  // below so the pair is the claim, not an accident that a `.first()` hides.
  await expect(
    clerk.locator("#default_gl_account_id-error"),
    "a retired account was accepted at the pick — CR-008 ruling 3 is not enforced on screen",
  ).toHaveText("That account is not one of yours, or it has been deactivated.", {
    timeout: 60_000,
  });
  await expect(
    clerk.getByRole("alert").filter({ hasText: "not one of yours" }),
    "the refusal never reached the form-level summary a person reads first",
  ).toBeVisible();

  // AND NOTHING WAS STORED. The refusal is whole, not partial.
  await clerk.goto(MAPPING);
  await expect(
    settingsRow(tableAfter(clerk, "Adjustment reasons"), "Goodwill credit"),
    "the refused pick was stored anyway",
  ).toContainText("Not mapped", { timeout: 60_000 });
  await clerk.close();
});

// ═══════════════════════════════════════════════════════════════════════════
// 10 · THE TENDER → CASH ACCOUNT COLUMN, AND B-10's POSTING
// ═══════════════════════════════════════════════════════════════════════════

// The whole of CR-008's B-10 slice, on screen, in one walk:
//   (a) the tender→cash column is EDITED here and persists across a reload;
//   (b) a card payment DEBITS the mapped clearing account at receipt — read off
//       the trial balance, which is the only surface in the product that shows
//       where a receipt landed (`GET /ledger/journal-entries/{id}` is unserved,
//       so a journal row expands to nothing);
//   (c) a mapping to a DEACTIVATED account REFUSES the payment BY NAME;
//   (d) clearing the mapping returns the tender to undeposited funds.
//
// ⚠ (d) is not tidiness. `card` is a shared row on a shared tenant: leaving it
// pointed at a retired account would refuse every card payment anybody takes
// afterwards. It is reset at the START of this test as well as at the end, so a
// crashed run self-heals on the next one.
test(`CR-008 B-10 · a card payment lands in its mapped clearing account, and a retired mapping refuses it ${APP_SERVER_TAG}`, async ({
  page,
}) => {
  test.setTimeout(WALK_BUDGET_MS);
  await signInAsAdmin(page);

  const clearingCode = `1015-${STAMP}`;
  const clearingName = `QA card clearing ${STAMP}`;

  async function setCardAccount(label: string | null): Promise<void> {
    await page.goto(MAPPING);
    const tenders = tableAfter(page, "Where each way of paying lands", "h4");
    await expect(tenders).toBeVisible({ timeout: 60_000 });
    await settingsRow(tenders, "Card").getByRole("button", { name: "Change" }).click();
    const field = page.locator("#clearing_gl_account_id");
    await expect(field, "the tender's clearing-account picker did not open").toBeVisible({
      timeout: 30_000,
    });
    await field.selectOption(label === null ? { index: 0 } : { label });
    await page.getByRole("button", { name: "Save account" }).click();
    await expect(page.locator(".modal-card")).toHaveCount(0, { timeout: 60_000 });
  }

  // SELF-HEAL: whatever a previous run left, Card starts unmapped.
  await setCardAccount(null);
  await expect(
    settingsRow(tableAfter(page, "Where each way of paying lands", "h4"), "Card"),
  ).toContainText("Not mapped", { timeout: 30_000 });

  // (a) — create the clearing account on the chart, then point Card at it.
  await page.goto(ACCOUNTING);
  await expect(chartTable(page)).toBeVisible({ timeout: 60_000 });
  await addAccountOnScreen(page, clearingCode, clearingName, "Asset");
  await setCardAccount(`${clearingCode} — ${clearingName}`);
  await expect(
    page.getByText(`Card now points at the account you chose.`),
    "no confirmation was shown after mapping the Card tender",
  ).toBeVisible({ timeout: 30_000 });

  // Persistence across a full page throw-away, not just a re-render.
  await page.goto(MAPPING);
  await expect(
    settingsRow(tableAfter(page, "Where each way of paying lands", "h4"), "Card"),
    "the tender mapping did not survive a reload",
  ).toContainText(clearingCode, { timeout: 60_000 });

  // (b) — take a card payment that CLEARS today, so the receipt leg posts.
  const amountPosted = "4.18";
  await page.goto(`/${tenant()}/payments/record`);
  await page.getByRole("button", { name: "Record payment" }).click();
  await expect(page.getByRole("heading", { name: "Record a payment" })).toBeVisible({
    timeout: 60_000,
  });
  const today = new Date().toISOString().slice(0, 10);
  // ⚠ ONE CONTROL SINCE 2026-09-23 (`DEF-PAY-6319`) — type and choose on the
  // same element; the matches are `role="option"` rows in its panel, and there
  // is no placeholder row to count past any more.
  await page.locator("#account_id").fill("AC-2026-00001");
  await expect(page.getByRole("option").first()).toBeVisible({ timeout: 30_000 });
  await page.getByRole("option").first().click();
  await page.locator("#amount").fill(amountPosted);
  await page.locator("#posted_at").fill(today);
  await page.locator("#cleared_at").fill(today);
  await page.locator("#method").selectOption({ label: "Card" });
  await page.locator(".modal-card").getByRole("button", { name: "Record payment" }).click();

  await expect(
    page.getByText("The books were updated in the same step: cash up, receivables down."),
    "the payment did not post to the books, so B-10's receipt leg cannot be read anywhere",
  ).toBeVisible({ timeout: 60_000 });

  // The trial balance is the ONLY screen that says WHERE it landed.
  await page.goto(`/${tenant()}/finance/gl`);
  const balance = finTable(page, "Trial balance");
  await expect(balance).toBeVisible({ timeout: 60_000 });
  await expect(
    settingsRow(balance, clearingCode),
    `the card receipt did not debit ${clearingCode} — B-10's first leg is not wired to the screen`,
  ).toBeVisible({ timeout: 30_000 });

  // (c) — retire the clearing account under the live mapping, then try again.
  await page.goto(ACCOUNTING);
  await page.getByPlaceholder("Code or name").fill(clearingCode);
  await expect(chartRow(page, clearingCode)).toHaveCount(1, { timeout: 60_000 });
  await chartRow(page, clearingCode).getByRole("button", { name: "Retire", exact: true }).click();
  await expect(chartRow(page, clearingCode)).toContainText("Retired", { timeout: 30_000 });

  await page.goto(`/${tenant()}/payments/record`);
  await page.getByRole("button", { name: "Record payment" }).click();
  await expect(page.getByRole("heading", { name: "Record a payment" })).toBeVisible({
    timeout: 60_000,
  });
  // ⚠ ONE CONTROL SINCE 2026-09-23 (`DEF-PAY-6319`) — type and choose on the
  // same element; the matches are `role="option"` rows in its panel, and there
  // is no placeholder row to count past any more.
  await page.locator("#account_id").fill("AC-2026-00001");
  await expect(page.getByRole("option").first()).toBeVisible({ timeout: 30_000 });
  await page.getByRole("option").first().click();
  await page.locator("#amount").fill("4.19");
  await page.locator("#posted_at").fill(today);
  await page.locator("#cleared_at").fill(today);
  await page.locator("#method").selectOption({ label: "Card" });
  await page.locator(".modal-card").getByRole("button", { name: "Record payment" }).click();

  // BY NAME, and naming the fix. Not a 500, not a silent re-route to
  // undeposited funds — the two things B-10's own docstring refuses.
  const refusal = page.getByText("recorded as asked", { exact: false });
  await expect(
    refusal,
    "a payment on a tender pointed at a RETIRED account was not refused",
  ).toBeVisible({ timeout: 60_000 });
  await expect(refusal, "the refusal does not name the tender").toContainText("card");
  await expect(refusal, "the refusal does not name where to fix it").toContainText(
    "Settings → Accounting → GL mapping",
  );

  // (d) — and clearing the mapping returns Card to today's behaviour.
  await page.keyboard.press("Escape");
  await setCardAccount(null);
  await expect(
    settingsRow(tableAfter(page, "Where each way of paying lands", "h4"), "Card"),
    "the Card tender could not be returned to unmapped — the next run inherits a broken tender",
  ).toContainText("Not mapped", { timeout: 30_000 });
});

// ═══════════════════════════════════════════════════════════════════════════
// 11 · FINANCE CONTROLS — the third sub-tab, and the two rulings it must OBEY
// ═══════════════════════════════════════════════════════════════════════════

test(`CR-008 SET-11.controls · the fiscal calendar, the reopen sentence, the scope card and the two money thresholds ${APP_SERVER_TAG}`, async ({
  page,
}) => {
  test.setTimeout(WALK_BUDGET_MS);
  await signInAsAdmin(page);
  await page.goto(CONTROLS);

  await expect(page.getByRole("heading", { name: "Fiscal calendar", exact: true })).toBeVisible({
    timeout: 60_000,
  });
  // The calendar is NOT redrawn here — two fiscal calendars in one product is
  // how the second one becomes wrong within a month.
  await expect(
    page.getByText("They are kept in one place so two calendars can never disagree.", {
      exact: false,
    }),
    "the controls tab does not say where the fiscal calendar actually lives",
  ).toBeVisible();
  // RULING 5 (*"5 system admin"*): a picker whose only legal value is the
  // current one is decoration, so it is a SENTENCE.
  await expect(
    page.getByText("A closed period can be reopened by a System Admin, and by nobody else."),
    "ruling 5's reopen sentence is missing",
  ).toBeVisible();
  await expect(
    page.getByText(/Owner \+ Finance admin|Owner only/),
    "r10's three-way reopen chooser was ruled OUT (ruling 5) and something drew it",
  ).toHaveCount(0);

  // The Scope card, verbatim in meaning: revenue only, one expense ever.
  await expect(page.getByRole("heading", { name: "What is in scope", exact: true })).toBeVisible();
  await expect(
    page.getByText("The only cost this product ever posts is bad debt, when you write something off.", {
      exact: false,
    }),
  ).toBeVisible();

  // RULING 1 (*"1. Accrual or cash … take it off"*) and RULING 8 (the
  // rounding-difference account, *"Keep as it is don't post it yet"*). Both are
  // ABSENCES, and an absence is only a rule if something asserts it.
  await expect(
    page.getByText(/accrual|cash basis|revenue recognition/i),
    "ruling 1 removed the accrual/cash control and something redrew it on SET-11",
  ).toHaveCount(0);
  await expect(
    page.getByText(/rounding difference/i),
    "ruling 8 said do not build the rounding-difference control",
  ).toHaveCount(0);

  // ── ADDED 2026-08-19 BY THE CLOSING WALK — RULINGS 2 AND 7, THE TWO MONEY
  // CONTROLS THIS TAB SHIPS, AND THE ONLY CR-008 REQUIREMENTS NO RUN HAD YET
  // READ ON A SCREEN. Both are on THIS tab: `SettingsAccountingTab` renders
  // `FINANCE_CONTROLS_PAGE` through the shared `RulePageView` (the S71 move of
  // 2026-08-16), so the Finance-controls card is a section of SET-11.controls
  // and not a separate page — which is why nobody had walked it: the two runs
  // before this one asserted the three CARDS r10 draws and stopped.
  //
  // **Ruling 2 is a NAME collision and the labels are the whole fix.** Two
  // money fields on one card meant different things and were called almost the
  // same thing; a utility that sets one believing it is the other changes a
  // control it never meant to touch. So both sentences are asserted, together,
  // because either one alone is only half of the distinction.
  const smallBalance = "Automatically write off small balances on a final bill (0–50)";
  const approverAbove = "Write-offs above this amount need an approver";
  await expect(
    page.getByText(smallBalance, { exact: false }),
    "ruling 2: BR-BIL-013's automatic small-balance write-off lost its unambiguous label",
  ).toBeVisible();
  await expect(
    page.getByText(approverAbove, { exact: false }),
    "ruling 2: the MANUAL collections approval threshold is not on the card — it was ruled to ship " +
      "separately labelled, and without it a utility reads the $50-capped field as the approval bound",
  ).toBeVisible();

  // ⚠ **THE DEFAULT IS THE POINT, NOT THE FIELD.** Ruling 2 part 3 and hard-won
  // law 3: today every manual write-off of any size needs an approver, so this
  // threshold ships at **$0.00**, not at r10's $5,000. Shipping $5,000 would
  // have made every write-off under it stop needing approval the moment CR-008
  // landed — a money control LOOSENED by a settings default. The echo is the
  // figure a person reads, so the figure a person reads is what is asserted.
  const approvalField = page
    .locator(".settings-rule-field")
    .filter({ hasText: approverAbove });
  await expect(
    approvalField.locator(".settings-rule-echo"),
    "the manual write-off approval threshold does not read $0.00 — if a lane or a tenant raised it, " +
      "every write-off below that figure now skips its approver, which is the loosening ruling 2 " +
      "part 3 exists to prevent",
  ).toContainText("$0.00");

  // RULING 7 (*"We can take it as threshold from user"*) — the AMOUNT half of
  // the bank match, which did not exist before this CR: the matcher compared
  // `batch.recorded_total == line.amount`, exact to the penny. Same posture as
  // above — the control ships, and its default is today's behaviour, because
  // `abs(batch − line) <= 0` IS penny-exact equality.
  const tolerance = "Bank match amount tolerance";
  await expect(
    page.getByText(tolerance, { exact: false }),
    "ruling 7's user-set bank-match amount tolerance is not on the card",
  ).toBeVisible();
  await expect(
    page.locator(".settings-rule-field").filter({ hasText: tolerance }).locator(".settings-rule-echo"),
    "the bank-match AMOUNT tolerance does not read $0.00 — anything above zero silently matches a " +
      "deposit to a bank line it does not equal",
  ).toContainText("$0.00");
});

// ═══════════════════════════════════════════════════════════════════════════
// 12 · PERMISSIONS — ruling 4: SYSTEM ADMIN, and BR-SHL-025 for everyone else
// ═══════════════════════════════════════════════════════════════════════════

test(`CR-008 ruling 4 · an Executive can read Accounting and cannot change a mapping ${APP_SERVER_TAG}`, async ({
  page,
}) => {
  test.setTimeout(WALK_BUDGET_MS);
  const email = `qa.cr008.exec.${STAMP}@brazosbendutilities.com`;
  const password = "S3cure!passw0rd";
  await signInAsAdmin(page);
  await ensureRoleUser(page, "executive", email, password);

  await page.goto(`/${tenant()}/signin`);
  await page.locator("#signin-email").fill(email);
  await page.locator("#signin-password").fill(password);
  await page.locator("form button[type=submit]").first().click();
  await page.getByRole("navigation", { name: "Main navigation" }).waitFor({ timeout: 60_000 });

  await page.goto(MAPPING);
  // READ: the whole map is legible. A permission that hid it would be a
  // different rule from the one that was ruled.
  const services = tableAfter(page, "Service revenue accounts");
  await expect(services, "an Executive cannot even read the GL map").toBeVisible({
    timeout: 60_000,
  });
  await expect(settingsRow(services, "Electric")).toContainText("4100");

  // WRITE: BR-SHL-025 — visible, disabled, WITH the reason. Every Change button
  // on the mapping tab, not a sample of one.
  const changeButtons = page.getByRole("button", { name: "Change", exact: true });
  const count = await changeButtons.count();
  expect(count, "the mapping tab drew no Change controls at all for an Executive").toBeGreaterThan(
    3,
  );
  for (let index = 0; index < count; index++) {
    const button = changeButtons.nth(index);
    await expect(button, `Change #${index} is HIDDEN from an Executive`).toBeVisible();
    await expect(button, `Change #${index} is still clickable for an Executive`).toBeDisabled();
    await expect(button).toHaveAttribute("title", "Your role can view this, but not change it.");
  }
});

// ── FINDING 4 ──────────────────────────────────────────────────────────────
// **The chart sub-tab ignores `readOnly` entirely.** `AccountingTab` passes
// `readOnly` to `ChartPanel`, and `ChartPanel` spends it on exactly ONE control
// — the "Import from a file" button. `ChartOfAccountsPanel` itself takes no
// such prop, so for an Executive the Add-account form, every row's Edit, every
// row's Retire and every row's Delete render FULLY ENABLED on a Settings tab
// that is System-Admin-only by ruling 4.
//
// The server still refuses the write (`@require_role(SYSTEM_ADMIN)`), so this
// is not a security hole — it is BR-SHL-025 inverted: instead of *"visible,
// disabled, with the reason"*, an Executive gets a live-looking control that
// fails after the click. That is DEF-196's shape, on the surface CR-006's
// walkthrough went out of its way to say was clean next door.
//
// TO INVERT: when the chart panel honours `readOnly`, delete `test.fail` — the
// assertions below already state the correct behaviour.
test.fail(
  `CR-008 FINDING 4 · an Executive sees LIVE add/edit/retire controls on the chart sub-tab ${APP_SERVER_TAG}`,
  async ({ page }) => {
    test.setTimeout(WALK_BUDGET_MS);
    const email = `qa.cr008.exec2.${STAMP}@brazosbendutilities.com`;
    const password = "S3cure!passw0rd";
    await signInAsAdmin(page);
    await ensureRoleUser(page, "executive", email, password);

    await page.goto(`/${tenant()}/signin`);
    await page.locator("#signin-email").fill(email);
    await page.locator("#signin-password").fill(password);
    await page.locator("form button[type=submit]").first().click();
    await page.getByRole("navigation", { name: "Main navigation" }).waitFor({ timeout: 60_000 });

    await page.goto(ACCOUNTING);
    await expect(chartTable(page)).toBeVisible({ timeout: 60_000 });

    // THE RULE: every write control on a read-only surface is disabled with its
    // reason. These three fail today, at this line, all of them enabled.
    await expect(
      page.getByRole("button", { name: "Add account ✓" }),
      "the Add-account button is live for an Executive on a System-Admin-only tab",
    ).toBeDisabled();
    await expect(
      chartRow(page, "1000").getByRole("button", { name: "Edit", exact: true }),
      "a chart row's Edit is live for an Executive",
    ).toBeDisabled();
    await expect(
      chartRow(page, "1000").getByRole("button", { name: "Retire", exact: true }),
      "a chart row's Retire is live for an Executive — one click retires the CASH account",
    ).toBeDisabled();
  },
);

// ── Lifecycle ─────────────────────────────────────────────
// packet:   CR-008 (12-governance/11-change-requests.md) — the PO's verbatim
//           requirement, the nine rulings of 2026-08-17, the second set built at
//           2.8.0 and the third set (B-8 · B-9 · B-10) built 2026-08-18 at
//           2.16.0/2.17.0 · 12-governance/13-change-process.md §8 THE CLOSURE
//           BAR (PO 2026-08-18) · CLAUDE.md hard-won laws 1, 2, 6 and 7.
// generated: 2026-08-18 by the CR-008 walkthrough lane — the CR's own register
//           row named this file's absence as the reason it does not close.
// exceptions:
//   (1) NO assertion anywhere on an API response or a component prop. The two
//       `page.request` calls in `ensureRoleUser` create a signed-in Executive
//       and are fenced in one labelled function, because `/change-password` is
//       not built (DEF-200) and no browser path from "create user" to "signed
//       in as that user" exists today.
//   (2) THE FINANCE RE-SIGN OF 4180 IS NOT TESTED AND CANNOT BE. It is a
//       HUMAN-GUIDE §6 act by finance, not a screen; what this file proves is
//       that until it happens the product SAYS SO where a person can read it.
//       ⚠ AMENDED 2026-08-19: it HAPPENED, on 2026-08-18, for 4180 and all
//       eight cost rows. The act is still not testable — §3 and the former
//       FINDING 1 now assert its CONSEQUENCE on the two screens instead, which
//       is the sign-off rule's own requirement that a test hold the ratified
//       state so drift goes red.
//   (3) The chart's PAGINATION FOOTER is not asserted because the panel draws
//       none — `ChartOfAccountsPanel` renders every row of the chart with a
//       search and two filters and no pager. On 35 rows that is defensible and
//       it is still a divergence from r10's *"rows 50/100/200/500/1000"*
//       footer and from B14 rule 16. Reported, not asserted, because no rule in
//       this repo has yet said which way it goes for a table this size.
//       **FILED 2026-08-19 as DEF-295** by the closing walk, with (4).
//   (4) The COLUMN SELECTOR r10 draws on SET-11.coa is likewise not built, and
//       not asserted, for the same reason. **DEF-295.**
//   (5) `Used by (count of mappings/schedules/authorities referencing it)` —
//       r10's own column — is NOT a column on the shipped chart. The server
//       serves the reference counts (they drive the Delete refusal, which this
//       file does not exercise because every seeded row is referenced), and no
//       column shows them. **FILED 2026-08-19 as DEF-294**, and the filing
//       found the reason it is not a five-minute column: `account_references`
//       answers `answerable: False` UNCONDITIONALLY — two of its kinds
//       (`charges.gl_account`, the tax-authority pointer) publish no reverse
//       lookup, so every count it can produce today is a partial one. Drawing
//       it as "Used by" would be DEF-127's shape, a number that means "I don't
//       know" rendered as a fact.
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
