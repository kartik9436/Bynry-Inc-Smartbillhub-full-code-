// ── Trace ──────────────────────────────────────────────
// Change:  CR-007 (12-governance/11-change-requests.md) — SET-09 the template
//          catalog · SET-10 the template detail. Marked **BUILT 2026-08-17 ·
//          version 2.7.0 · awaiting human review** and NOT CLOSED: no browser
//          walkthrough had happened.
// Story:   CR-007@set0910 · Screens: SET-09 · SET-10
//          Route: /{tenant}/settings/reference-data/templates
// Rules:   BR-NOT-001 (variants + a mandatory default fallback) · BR-NOT-006
//          (type × category × language; the palette IS the catalog) ·
//          BR-NOT-014 (THREE disconnect slots, one per dunning stage) ·
//          BR-NOT-015 (the rights footer is a PLATFORM DEFAULT a System Admin
//          overrides — the PO ruled on 2026-08-17 that the platform writes the
//          five sentences, closing the rights-footer OQ-253; the id in this
//          header read OQ-250, which is CR-005's counter-pad question) ·
//          BR-BIL-026 (an edit is a NEW append-only version) · BR-BIL-027
//          (System Admin publishes) · BR-SHL-025 (a control that cannot work
//          stays VISIBLE and DISABLED WITH ITS REASON) · BR-SHL-032 (a confirm
//          names the action) · BR-TEN-017 (the utility's identity is stamped at
//          render) · B14 rules 5 · 6 · 13 · 14 · 15 · 16 · 17 · 18 · 20
// Defect:  DEF-195 ({utility_logo} is in every printable palette and the
//          renderer supplies no value) — CONFIRMED here, on screen, by clicking
//          it. Plus eight further findings this file pins; see THE INVERSION
//          CONTRACT below.
// ───────────────────────────────────────────────────────
//
// **THE PO'S BAR, VERBATIM, IS THE ONLY REASON THIS FILE EXISTS:**
// *"confirmation based on web click"*.
//
// CR-007 shipped eight routes and two screens over an engine that was already
// finished and already tested — its own build record calls it *"hard-won law 2
// at the largest scale it has appeared so far"*. So the backend being green
// says nothing about this CR. On this project a walkthrough of six shipped,
// fully-tested reference lists found **five of them answering HTTP 500**
// (DEF-187) with the entire suite passing. A green test is not this. Every
// assertion below is on RENDERED TEXT a person reads, never on a payload.
//
// ── THE INVERSION CONTRACT — READ THIS BEFORE TRUSTING A GREEN RUN ─────────
//
// This spec was written against a build with **nine open findings**, none of
// them fixed by this lane (QA reports; it does not fix product code). A spec
// that asserted the CORRECT behaviour would be nine tests red on the current
// build and would be deleted or skipped by the next person who saw it — which
// is how a finding evaporates.
//
// So every assertion that pins a DEFECT is wrapped in a `FINDING (…)` block
// that states, in words, what the product does today and what it must do
// instead. Those assertions are deliberately written so that **fixing the
// defect turns this file RED**, at the exact line, with the finding quoted in
// the failure message. Nobody can fix one of these quietly; the fix arrives
// with a spec change that names it.
//
// A green run of this file therefore means: *the screens work as described, and
// the findings still marked open are still open.* It does NOT mean the screens
// are right.
//
// ⚠ **AMENDED 2026-08-18 — TEN OF THE NINETEEN FINDINGS ARE NOW FIXED, AND THE
// MECHANISM ABOVE IS WHAT MADE THEM VISIBLE.** DEF-211 (eight B14 rule breaks),
// DEF-212 (four faults plus a copy fix) and DEF-209's remainder landed in one
// pass, and every assertion they touch was INVERTED here in the same commit —
// which is the contract working exactly as written: nobody could fix one
// quietly, because this file went red at the exact line with the finding
// quoted. Findings 1, 2, 4 (the DataTable half), 5 (the cycle), 6, 7, 11, 12,
// 13, 14, 15, 17 and rule 19 now assert the CORRECT behaviour and are labelled
// `(fixed)`. What is still pinned as open is labelled `(remainder)` or `STILL
// OPEN` and names WHOSE it is: three of them are the shared `DataTable`'s
// (rule 16's `Showing`/first-last, rule 13's third click, rule 5's
// `.table-columns-up`), one is DEF-223's product-wide table size, and one is
// DEF-212 (4) — the bill-layout panel, which lives in `SettingsPage.tsx`.
//
// ⚠ **SELECTORS MOVED.** SET-09's table is `table.data-table` with no
// per-screen test id, its rows are found by the name cell's
// `template-name-<code>`, and the pager/column-chooser are the shared
// `.table-pager` / `.table-columns`. See the helpers below.
//
// ⚠ **THIS SPEC WRITES, AND ONLY TO ONE TEMPLATE CLASS.** It creates a
// run-unique variant on `receipt` — keyed `commercial / qa-<stamp>`, because a
// variant's identity is `(code, category, language)` and NOT its name (finding
// 19) — saves drafts on it, publishes one, restores one and deactivates it.
// `dunning` is left pristine for the read-only assertions, because a variant
// can never be deleted (deactivate only, by design) so anything a write test
// adds is permanent. It NEVER deactivates a SEEDED default variant: one
// unconfirmed click there leaves the only past-due reminder the product can
// actually produce with nothing to resolve (finding 14). A crashed run leaves
// one inactive `QA …` variant behind; the next run's stamp differs, so it never
// collides. Point this at a disposable tenant only — the same posture, and the
// same warning, as CR-004-reference-crud.spec.ts.
import { expect, test } from "@playwright/test";
import type { Locator, Page } from "@playwright/test";

import { APP_SERVER_TAG } from "./support/census";
import { signIn, skipUnlessAppServer, tenant } from "./support/app";

skipUnlessAppServer(test);

function templatesPath(): string {
  return `/${tenant()}/settings/reference-data/templates`;
}

// ⚠ THE SELECTORS MOVED ON 2026-08-18 (DEF-211), AND THAT IS THE FIX ITSELF.
// SET-09 was a hand-rolled `.settings-table` with its own sort, its own column
// chooser and its own pager, which is why B14 rules 13, 14 and 16 were absent
// at once (finding 4/9 below). It rides the shared `DataTable` now, so the
// table is `table.data-table` and it carries no per-screen test id.
//
// A ROW is still addressed BY TEMPLATE CODE — through the name cell's own test
// id, which survived the move — because addressing it by displayed name would
// make every assertion here depend on copy.
const catalogTable = (page: Page): Locator => page.locator("table.data-table");
const catalogRows = (page: Page): Locator => catalogTable(page).locator("tbody tr");
const catalogRow = (page: Page, code: string): Locator =>
  catalogRows(page).filter({ has: page.locator(`[data-testid=template-name-${code}]`) });
const rowNames = (page: Page): Locator => catalogTable(page).locator("tbody td:first-child button");

/** Open one template's SET-10 detail from the catalog, and wait for it. */
async function openTemplate(page: Page, code: string): Promise<void> {
  await catalogTable(page).waitFor({ timeout: 30_000 });
  await page.locator(`[data-testid=template-open-${code}]`).click();
  await page.locator("[data-testid=template-back]").waitFor({ timeout: 30_000 });
}

/** The merge-field rows a template OFFERS, as the bare token names. */
async function offeredTokens(page: Page): Promise<string[]> {
  const cells = await page.locator("[data-testid=merge-fields] tbody td:first-child code").allInnerTexts();
  return cells.map((raw) => raw.trim().replace(/^\{|\}$/g, ""));
}

// ═══════════════════════════════════════════════════════════════════════════
// SET-09 · THE CATALOG
// ═══════════════════════════════════════════════════════════════════════════

test(`CR-007 SET-09 · the catalog renders, filters, searches and pages ${APP_SERVER_TAG}`, async ({
  page,
}) => {
  // MEASURED: `vite build` emits one 3.5 MB chunk and a cold load costs ~13 s
  // here. This is a WALKTHROUGH — sign in, filter five times, search, empty,
  // recover — so the 90 s default is not the budget for it.
  test.setTimeout(300_000);
  await signIn(page);
  await page.goto(templatesPath());

  // ── 1 · THE SEPARATION OF CONCERNS CR-007 ASKED TO BE STATED ON SCREEN ──
  // *"Separation of concerns stated on screen: Notifications decide when,
  // Templates define what."* Quoted from the running screen, not the catalogue.
  await expect(
    page.getByText(
      "Notifications decide WHEN a message goes out. Templates define WHAT it says. " +
        "Nothing on this screen schedules, triggers or sends anything.",
    ),
  ).toBeVisible();

  // ── 2 · THE TABLE AND ITS COLUMNS ───────────────────────────────────────
  // CR-007's column list: Template name | Category | Kind | Variants | Used by
  // | Last edited | Actions.
  await expect(catalogTable(page)).toBeVisible();
  // ⚠ AMENDED 2026-08-18, FIRST EVER RUN OF THIS SPEC: "Category" now reads
  // "Category▲". That is B14 rule 13's sort indicator, added by the DEF-211
  // fix and REQUIRED by the rule — the header is right and this assertion was
  // written before the indicator existed. Matched on the leading text so the
  // indicator may move column without re-breaking this.
  await expect(catalogTable(page).locator("thead th")).toHaveText([
    "Template name",
    /^Category/,
    "Kind",
    "Variants",
    "Used by",
    "Last edited",
    "Actions",
  ]);
  // ── FINDING 1 · FIXED 2026-08-18 (DEF-211) · ONE CASE ACROSS THE ROW ────
  // It used to read "Template name  Category  KIND  VARIANTS  USED BY  LAST
  // EDITED  ACTIONS" — two sentence-case headers beside five shouting ones —
  // because `.settings-table th` set `text-transform: uppercase` and the two
  // sortable headers wrapped their label in a <button>, which the UA stylesheet
  // resets to `none`. The shared table's `.table-sort` declares
  // `text-transform: inherit`, so every header now renders the same way.
  // Asserted on RENDERED text (`allInnerTexts` applies the transform,
  // `toHaveText` does not), which is the only way the difference is visible.
  const rendered = await catalogTable(page).locator("thead th").allInnerTexts();
  expect(
    rendered.map((h) => (h === h.toUpperCase() ? "SHOUTING" : "sentence")),
    "FINDING 1 (fixed) — all seven headers share one case. If this goes red, a " +
      "header stopped inheriting the table's text-transform again.",
  ).toEqual([
    "SHOUTING",
    "SHOUTING",
    "SHOUTING",
    "SHOUTING",
    "SHOUTING",
    "SHOUTING",
    "SHOUTING",
  ]);

  // ── 3 · THE FULL INVENTORY IS ON SCREEN ─────────────────────────────────
  // CR-007 names ~19 templates; the build record explains why 36 ship (five
  // pre-existing classes + fourteen new + the three BR-NOT-014 slots + the
  // classes A19 already carried). The count is asserted so a class silently
  // dropping off the catalog goes red.
  // ⚠ AMENDED 2026-08-18, FIRST EVER RUN: 37, not 36. C-14 (PO 2026-08-17)
  // kept the plan-void notice and gave it default language rather than
  // withdrawing the class, taking the catalog 36 → 37. The count assertion is
  // doing its job — it is here so a class silently dropping off goes red, and
  // it went red for a class silently ARRIVING, which is the same guard.
  await expect(catalogRows(page)).toHaveCount(37);
  await expect(page.locator("[data-testid=chip-all]")).toHaveText("All (37)");

  // ── 4 · THE FIVE CATEGORY CHIPS FILTER ──────────────────────────────────
  // CR-007's chips: All · Billing · Collections · Payments · Service & field ·
  // Account lifecycle. Each is clicked and its row count read off the screen;
  // the five parts sum to the whole, which is the assertion a chip that filters
  // nothing would fail.
  // ⚠ AMENDED 2026-08-18, FIRST EVER RUN: Billing 5 → 6, so the parts now sum
  // to 37. The class that arrived is C-14's plan-void notice, kept and given
  // default language instead of being withdrawn (PO 2026-08-17). Counted from
  // the server's own catalog rather than adjusted until it passed.
  const chips: [string, string, number][] = [
    ["billing", "Billing", 6],
    ["collections", "Collections", 12],
    ["payments", "Payments", 8],
    ["service_field", "Service & field", 4],
    ["account_lifecycle", "Account lifecycle", 7],
  ];
  expect(chips.reduce((sum, [, , n]) => sum + n, 0)).toBe(37);
  for (const [key, label, count] of chips) {
    const chip = page.locator(`[data-testid=chip-${key}]`);
    await expect(chip).toHaveText(label);
    await chip.click();
    await expect(chip).toHaveAttribute("aria-pressed", "true");
    await expect(catalogRows(page), `the ${label} chip filters`).toHaveCount(count);
  }
  await page.locator("[data-testid=chip-all]").click();
  await expect(catalogRows(page)).toHaveCount(37);

  // ── 5 · SEARCH ──────────────────────────────────────────────────────────
  await page.locator("[data-testid=template-search]").fill("disconnect");
  await expect(catalogRows(page)).toHaveCount(5);
  await expect(rowNames(page)).toHaveText([
    "Disconnect notice · 10-day warning",
    "Disconnect notice · 48-hour certified",
    "Disconnect notice · 5-day final reminder",
    "Disconnect notice · SMS supplement",
    "Disconnect / reconnect door hanger",
  ]);

  // ── 6 · B14 RULE 17 · THE EMPTY STATE ───────────────────────────────────
  await page.locator("[data-testid=template-search]").fill("zzzz-no-such-template");
  // ── FINDING 2 · FIXED 2026-08-18 (DEF-211) · THE WAY OUT IS THERE ───────
  // B14 rule 17: *"Empty state on every list: what is missing, AND THE ACTION
  // THAT FILLS IT."* This was a bare sentence in a `<td>` with nothing to
  // click. The shared table draws A18 §2's zero-results block instead, which
  // names the query and carries the control that clears it.
  const zero = page.locator(".state-zero");
  await expect(zero).toBeVisible();
  await expect(zero).toContainText("zzzz-no-such-template");
  await expect(
    zero.getByRole("button", { name: "Clear filters" }),
    "FINDING 2 (fixed) — rule 17's second half: the action that fills the list.",
  ).toBeVisible();
  await page.locator("[data-testid=template-search]").fill("");
  await expect(catalogRows(page)).toHaveCount(37);

  // ── 7 · PAGINATION ──────────────────────────────────────────────────────
  // It BEHAVES — and what it does is nothing, always, by construction.
  const pager = page.locator(".table-pager");
  await expect(pager).toContainText("1–37 of 37");
  await expect(pager.locator("button.table-page-btn").first()).toBeDisabled();
  await expect(pager.locator("button.table-page-btn").last()).toBeDisabled();
  // ── FINDING 3 · THE SMALLEST PAGE SIZE (50) EXCEEDS THE WHOLE CATALOG ───
  // Template CLASSES are platform vocabulary, not tenant rows: 36 today, and
  // OQ-253 keeps a tenant from minting more. So with page sizes 50/100/200/
  // 500/1000 there is exactly one page forever, both pager buttons are dead,
  // and the pager is decoration. CR-007 asked for *"pagination 50–1000"* by
  // copying the standard table rules onto a table that cannot use them.
  await expect(pager.locator("select option")).toHaveText(["50", "100", "200", "500", "1000"]);
  const smallest = Number((await pager.locator("select option").first().innerText()).trim());
  expect(
    smallest > (await catalogRows(page).count()),
    "FINDING 3 — the smallest page size is larger than the entire catalog, so " +
      "pagination can never do anything. Either add a smaller size or drop the pager.",
  ).toBe(true);
  // ⚠ STILL TRUE, AND NOW SAID OUT LOUD (DEF-211, 2026-08-18). Dropping the
  // footer would break rule 16 to hide a consequence of rule 16, so the screen
  // states the fact instead of leaving a control a person keeps trying to use.
  await expect(
    page.locator("[data-testid=template-onepage]"),
    "FINDING 3 (answered, not removed) — the screen says why the pager is inert.",
  ).toContainText("fit on one page");

  // ── 8 · B14 RULE 16 · THE PAGINATION FOOTER ─────────────────────────────
  // ── FINDING 4 · FIXED 2026-08-18 (DEF-211), WITH ONE REMAINDER ─────────
  // The footer is the shared one now: the range and the page-size select sit
  // in it rather than in the toolbar, and the table is the component B14's own
  // Enforced column names.
  expect(
    await page.locator("table.data-table").count(),
    "FINDING 4/9 (fixed) — SET-09 rides the shared DataTable, which is why " +
      "rules 13, 14 and 16 arrive together.",
  ).toBe(1);
  await expect(pager).toContainText("Rows per page");
  // ⚠ REMAINDER, AND IT IS THE SHARED COMPONENT'S, NOT THIS SCREEN'S: rule 16
  // reads *"Showing 1–50 of N … ⇤ ← Page x of y → ⇥"* and `DataTable` renders
  // "1–37 of 37" with ‹ › and no first/last. Every list in the product is
  // identical in this respect, so it is one change to DataTable.tsx and not a
  // template fix. When it lands, both assertions below go red.
  await expect(
    page.locator("main.view"),
    "FINDING 4 (remainder) — rule 16's literal footer says `Showing`.",
  ).not.toContainText("Showing 1–37 of 37");
  await expect(
    pager.getByRole("button", { name: /first page|last page/i }),
    "FINDING 4 (remainder) — rule 16 wants ⇤ and ⇥ as well as ‹ and ›.",
  ).toHaveCount(0);

  // ── 9 · B14 RULE 13 · SORTING ───────────────────────────────────────────
  // The rule: *"Headers show ⇅; click cycles asc → desc → clear."*
  // ── FINDING 5 · MOSTLY FIXED 2026-08-18 (DEF-211) ───────────────────────
  // It used to be one-way, on two of seven headers, with no indicator at all.
  // The shared table sorts on every header the SERVER can sort — `CATALOG_SORTS`
  // is name/category/kind/variants/edited, five of the seven — reverses on the
  // second click, and marks the sorted column with ▲/▼ and `aria-sort`.
  const nameHeader = catalogTable(page).locator("thead th").first().locator("button");
  const firstRowName = () => rowNames(page).first();
  await expect(firstRowName()).toHaveText("Bill insert");
  await nameHeader.click();
  await expect(firstRowName()).toHaveText("Account closed confirmation");
  await expect(catalogTable(page).locator("thead th").first()).toHaveAttribute(
    "aria-sort",
    "ascending",
  );
  await nameHeader.click();
  await expect(
    firstRowName(),
    "FINDING 5 (fixed) — the second click REVERSES. This used to be inert.",
  ).not.toHaveText("Account closed confirmation");
  await expect(catalogTable(page).locator("thead th").first()).toHaveAttribute(
    "aria-sort",
    "descending",
  );
  expect(
    catalogTable(page).locator("thead th button"),
    "five of the seven headers sort — `used_by` and the action column are not " +
      "in CATALOG_SORTS, and a header that cycles and changes nothing is worse " +
      "than one that does not move",
  ).toHaveCount(5);
  // ⚠ TWO REMAINDERS, BOTH THE SHARED COMPONENT'S: rule 13's THIRD click
  // ("clear") does not exist — `nextSortState` toggles asc/desc — and the ⇅
  // glyph is drawn only on the SORTED column (as ▲/▼) rather than on every
  // sortable header. One change to DataTable.tsx, product-wide.
  await expect(
    page.locator("main.view"),
    "FINDING 5 (remainder) — rule 13's ⇅ affordance on unsorted headers.",
  ).not.toContainText("⇅");

  // ── 10 · B14 RULE 14 · THE COLUMN SELECTOR ──────────────────────────────
  // ── FINDING 6 · FIXED 2026-08-18 (DEF-211) ──────────────────────────────
  // The hand-rolled `<details>Columns` had show/hide and nothing else. The
  // shared chooser is the one rule 14 describes: show/hide, reorder (↑ per
  // visible column) and Reset to default — and the identity column's checkbox
  // renders DISABLED rather than absent (BR-SHL-013), so "Template name cannot
  // be hidden" is stated instead of silently enforced.
  const columns = page.locator(".table-columns");
  await columns.locator("summary").click();
  await expect(columns.locator("label")).toHaveText([
    "Template name",
    "Category",
    "Kind",
    "Variants",
    "Used by",
    "Last edited",
    "Actions",
  ]);
  await expect(columns.locator("label", { hasText: "Template name" }).locator("input")).toBeDisabled();
  await columns.locator("label", { hasText: "Kind" }).locator("input").uncheck();
  await expect(catalogTable(page).locator("thead th")).toHaveCount(6);
  await expect(
    columns.getByRole("button", { name: "Reset to default" }),
    "FINDING 6 (fixed) — B14 rule 14's Reset.",
  ).toBeVisible();
  await columns.getByRole("button", { name: "Reset to default" }).click();
  await expect(catalogTable(page).locator("thead th")).toHaveCount(7);
  await expect(
    columns.locator("button.table-columns-up").first(),
    "FINDING 6 (fixed) — rule 14's reorder.",
  ).toBeVisible();
});

test(`CR-007 SET-09 · BR-NOT-014's THREE disconnect slots are three rows ${APP_SERVER_TAG}`, async ({
  page,
}) => {
  test.setTimeout(300_000);
  // **THE CHECK THAT WOULD HAVE BEEN A SERIOUS FINDING.** BR-NOT-014 signed
  // three disconnect notices, one per dunning stage, on 2026-08-16; the ruling
  // reached three documents and NO CODE, and CR-007's step 0 caught it
  // (DEF-193 — the id in this comment read DEF-190 until 2026-08-17, which is a
  // different, i18n, defect: DEF-230). A catalog showing ONE is that ruling lost
  // a second time. It shows three, and each names its own stage in the Used-by
  // column.
  //
  // ⚠ AMENDED 2026-08-17 (CR-007's disconnect-notice lane). The Used-by cells
  // said *"not yet selected"* because `generate_disconnect_notice` resolved the
  // superseded single class at every tier. It selects by tier now, so the copy
  // would have been asserting a defect that had been fixed.
  await signIn(page);
  await page.goto(templatesPath());
  await catalogTable(page).waitFor({ timeout: 30_000 });

  for (const [code, name, kind, stage] of [
    ["disconnect_notice_10_day", "Disconnect notice · 10-day warning", "Print + email", "Dunning stage 1 of the regulated ladder (BR-NOT-014)"],
    ["disconnect_notice_5_day", "Disconnect notice · 5-day final reminder", "Print + email", "Dunning stage 2 of the regulated ladder (BR-NOT-014)"],
    ["disconnect_notice_48_hour", "Disconnect notice · 48-hour certified", "Certified print + email", "Dunning stage 3 of the regulated ladder, certified mail (BR-NOT-014)"],
  ]) {
    const row = catalogRow(page, code);
    await expect(row, `${name} is its own row`).toHaveCount(1);
    await expect(row.locator("td:first-child button")).toHaveText(name);
    await expect(row).toContainText(kind);
    await expect(row, "the Used-by cell names WHICH stage consumes it").toContainText(stage);
  }
});

test(`CR-007 SET-10 · each disconnect tier offers ONLY its own tier tokens ${APP_SERVER_TAG}`, async ({
  page,
}) => {
  test.setTimeout(300_000);
  // The second half of the BR-NOT-014 check, and the one that actually matters
  // to a customer: three rows carrying ONE union palette would let a System
  // Admin put `{48h}` or `{certified_no}` on a 10-day warning — a letter
  // threatening certified 48-hour disconnection at stage one. The build record
  // claims *"each carrying A19 §2's own tier tokens and not the union"*.
  // Verified from the merge-fields panel, on screen.
  await signIn(page);

  const tiers: [string, string[], string[]][] = [
    [
      "disconnect_notice_10_day",
      // `rights_footer` added 2026-08-17: it is on EVERY tier and is mandatory
      // class content beside `state_puc_ref` (CR-007 / BR-NOT-015).
      ["pay_by_date", "balance", "state_puc_ref", "rights_footer"],
      ["48h", "certified_no", "cut_date", "reconnect_fee"],
    ],
    [
      "disconnect_notice_5_day",
      ["cut_date", "reconnect_fee", "service_address", "rights_footer"],
      ["48h", "certified_no", "pay_by_date"],
    ],
    [
      "disconnect_notice_48_hour",
      ["48h", "certified_no", "cut_date", "rights_footer"],
      ["pay_by_date", "reconnect_fee"],
    ],
  ];

  for (const [code, mustOffer, mustNotOffer] of tiers) {
    await page.goto(templatesPath());
    await openTemplate(page, code);
    await page.locator("[data-testid=merge-fields]").waitFor({ timeout: 30_000 });
    const tokens = await offeredTokens(page);
    for (const token of mustOffer) {
      expect(tokens, `${code} offers {${token}}`).toContain(token);
    }
    for (const token of mustNotOffer) {
      expect(
        tokens,
        `${code} must NOT offer {${token}} — a tier's palette is A19 §2's own, ` +
          "never the union of the three (BR-NOT-014)",
      ).not.toContain(token);
    }
    // BR-NOT-015 / US-NOT-007 TC-6: the commission reference can never be
    // dropped from a regulated notice, and the screen says so in words.
    // ⚠ AMENDED 2026-08-18, FIRST EVER RUN: the screen now names TWO mandatory
    // tokens, `{state_puc_ref}` AND `{rights_footer}`. The second arrived with
    // the disconnect-defaults pass (2.7.4) that authored the three tier bodies
    // and the five rights clauses — BR-NOT-015 makes the rights footer
    // unremovable from a regulated notice exactly as it does the commission
    // reference. The product is right; this assertion predates it.
    await expect(page.locator("[data-testid=mandatory-content]")).toHaveText(
      "This template may never be saved without: {state_puc_ref}, {rights_footer}",
    );
  }
});

// ═══════════════════════════════════════════════════════════════════════════
// SET-10 · THE DETAIL, ONE TEMPLATE OF EACH KIND
// ═══════════════════════════════════════════════════════════════════════════

test(`CR-007 SET-10 · a PRINT template renders all six panels ${APP_SERVER_TAG}`, async ({ page }) => {
  test.setTimeout(300_000);
  // `dunning` is one of exactly THREE classes in the product with a publishable
  // body (the build record's own count: *"Of 36 catalogued classes, THREE have
  // a body"*), so it is the only place most of SET-10 can be seen working at
  // all. Read-only here; the write walkthrough uses a disposable variant.
  await signIn(page);
  await page.goto(templatesPath());
  await openTemplate(page, "dunning");

  await expect(page.locator("h3").filter({ hasText: "Past-due reminder" }).first()).toBeVisible();
  await expect(page.getByText("Print · collections")).toBeVisible();

  // ── 1 · THE PREVIEW PANE RENDERS THE ARTEFACT WITH SAMPLE DATA ──────────
  await expect(page.locator("[data-testid=preview-pane]")).toBeVisible();
  await expect(page.locator("[data-testid=preview-body]")).toHaveText(
    "Hi Sample, this is a friendly reminder that your account SAMPLE-ACCOUNT has a " +
      "balance of 123.45 USD. You can pay online at any time. Thanks for being a customer.",
  );
  // The PO's header strip: previewing as · kind · whose sample data · default pill.
  await expect(page.locator("[data-testid=preview-kind]")).toHaveText("Print");
  await expect(page.locator("[data-testid=preview-sample-identity]")).toHaveText(
    "sample data: Sample Customer · SAMPLE-ACCOUNT",
  );
  await expect(page.locator("[data-testid=preview-default-pill]")).toHaveText("Default variant");
  // The pane always says it is a preview — a preview that stops saying so is a
  // preview somebody reads as a real customer's letter.
  await expect(page.locator("[data-testid=preview-notice]")).toContainText(
    "Preview only, rendered from SAMPLE data",
  );

  // ── 2 · MERGE FIELDS WITH THEIR RESOLVED SAMPLE VALUES ──────────────────
  // The PO confirmed this SHAPE from SET-10.corrected: token on the left, the
  // value it will actually resolve to on the right ({{bill.original_total}} →
  // $32.22). It is two columns and the values resolve.
  await expect(page.locator("[data-testid=merge-fields] thead th")).toHaveText([
    "Field",
    "Sample value",
  ]);
  for (const [token, value] of [
    ["balance", "123.45 USD"],
    ["customer_name", "Sample Customer"],
    ["days_late", "14"],
    ["first_name", "Sample"],
    ["service_address", "1 Sample Street, Sample City"],
    ["unpaid_bills", "2"],
  ]) {
    await expect(
      page.locator(`[data-testid=merge-field-${token}] td`).last(),
      `{${token}} shows the value it will resolve to`,
    ).toHaveText(value);
  }

  // ── 3 · "WHERE IT'S USED" RENDERS A SENTENCE ────────────────────────────
  await expect(page.locator("[data-testid=where-used]")).toBeVisible();
  // ── FINDING 7 · FIXED 2026-08-18 (DEF-212, last item) ───────────────────
  // The PO's addendum A is explicit: *"**Where it's used** — ONE plain
  // sentence, not a list of ids (*'Sent automatically when a rebill posts.'*)"*.
  // A System Admin used to read `notices.generate_reminder — dunning stages 1-2
  // (BR-NOT-008)`: a module path in front of an English sentence. The path is
  // dropped and the rule id stays, because every other row cites one.
  await expect(
    page.locator("[data-testid=where-used]"),
    "FINDING 7 (fixed) — one plain sentence, still citing its rule.",
  ).toHaveText("Dunning stages 1-2 (BR-NOT-008)");
  await expect(page.locator("main.view")).not.toContainText("notices.generate_reminder");

  // ── 4 · HISTORY RENDERS DATED ENTRIES ───────────────────────────────────
  await expect(page.locator("[data-testid=version-history] thead th")).toHaveText([
    "Version",
    "Status",
    "Updated",
    "Messages using it",
    "Actions",
  ]);
  const v1 = page.locator("[data-testid=version-1]");
  await expect(v1.locator("td").first()).toHaveText("v1");
  await expect(v1).toContainText("Published");
  await expect(
    page.locator("[data-testid=version-trail-1]"),
    "the entry is DATED and says who — the PO's line is 'Jul 30 · Priya Menon'",
  ).toContainText(/^\d{4}-\d{2}-\d{2} · platform seed/);
  // The third part of the PO's history line — WHAT changed — is honestly
  // absent, and the screen says so rather than leaving a blank (OQ-255).
  await expect(page.locator("[data-testid=version-trail-1]")).toContainText(
    "No column records what an edit changed",
  );

  // ── 5 · THE VARIANT SWITCHER RENDERS EVEN AT ONE VARIANT ────────────────
  // The PO's shape from SET-10.corrected: tabs render at a single variant
  // ("Standard", one tab), and CR-007's *"each category must have at least one
  // alternative variant"* is a CATALOG-level statement — no variant is invented
  // to satisfy it.
  const tabs = page.locator("[data-testid=variant-switcher] [role=tab]");
  await expect(tabs, "the switcher draws at ONE variant").toHaveCount(1);
  await expect(tabs.first()).toContainText("Dunning");
  // ⚠ WAS `.locator(".settings-badge")` UNTIL CR-048 WAVE C. `.badge` was an
  // unprefixed name no stylesheet declared, renamed to `.settings-badge` and
  // declared once (DEF-211); wave C migrated this screen to Tailwind and
  // retired that rule, so the badge now carries utilities and a stable
  // `data-badge` hook. The hook is what a locator should have named all along
  // — a class name is a STYLING decision and this assertion is about content.
  await expect(tabs.first().locator("[data-badge]")).toHaveText("Default");
  await expect(tabs.first()).toHaveAttribute("aria-selected", "true");

  // ── 6 · BR-SHL-025 · THE THREE DISABLED CONTROLS, EACH WITH ITS REASON ──
  // ⚠ CHECK B, and it is the answer the PO's *"no email yet"* requires. The
  // control is neither hidden nor live: it renders, it is disabled, and the
  // reason is VISIBLE on the page as well as in the tooltip.
  const testSend = page.locator("[data-testid=test-send]");
  await expect(testSend).toBeVisible();
  await expect(testSend).toHaveText("Send test to me");
  await expect(testSend, "a live test-send would be a defect — PO: 'no email yet'").toBeDisabled();
  await expect(page.locator("[data-testid=test-send-reason]")).toContainText(
    "No test send in this release, on any channel.",
  );
  await expect(page.locator("[data-testid=test-send-reason]")).toContainText('"no email yet"');
  const downloadPdf = page.locator("[data-testid=download-pdf]");
  await expect(downloadPdf).toBeVisible();
  await expect(downloadPdf).toBeDisabled();
  await expect(page.locator("[data-testid=download-pdf-reason]")).toContainText(
    "No sample PDF for this class.",
  );
  const setDefault = page.locator("[data-testid=set-default]");
  await expect(setDefault).toBeVisible();
  await expect(setDefault).toBeDisabled();
  // ⚠ DEF-335 — THIS LINE USED TO ASSERT `toContainText("OQ-252")`, on the
  // screen a water utility reads. A test written beside a string pins it, so
  // the internal sentence was not merely unchecked here: it was a REQUIREMENT
  // this walkthrough enforced. Inverted, both halves: the words a person reads
  // name no id, and the provenance rides `data-br-ref` for support.
  const setDefaultReason = page.locator("[data-testid=set-default-reason]");
  await expect(setDefaultReason).not.toContainText("OQ-252");
  await expect(setDefaultReason).not.toContainText("BR-NOT-");
  await expect(setDefaultReason).toHaveAttribute("data-br-ref", /OQ-252/);
  const languageNote = page.locator("[data-testid=language-note]");
  await expect(languageNote).not.toContainText("apps/customers");
  await expect(languageNote).toHaveAttribute("data-br-ref", /OQ-254/);
  // Three DIFFERENT sentences, because the three have three different fixes.
  const reasons = await Promise.all(
    ["test-send-reason", "download-pdf-reason", "set-default-reason"].map((id) =>
      page.locator(`[data-testid=${id}]`).innerText(),
    ),
  );
  expect(new Set(reasons).size).toBe(3);
  // And no raw key anywhere on the screen (DEF-188's whole cost).
  await expect(page.locator("main.view")).not.toContainText("templates.detail.");
  await expect(page.locator("main.view")).not.toContainText("notifications.templates.");

  // ── FINDING 8 · THE BILL-LAYOUT PANEL IS STILL ON THE SET-10 SCREEN ─────
  // `SettingsPage` renders `<TemplateCatalogTab/>` AND `<BillLayoutTab/>` as
  // siblings, and the detail replaces only the first. So a System Admin reading
  // the wording of the past-due reminder finds *"Choose the page your customers
  // receive"*, five bill layouts and a SECOND version-history table underneath
  // it — two unrelated documents and two histories on one screen. The catalog
  // deliberately does not list bills (B2 r10 #4, *"one document, one home"*),
  // which is exactly why the panel should not follow the detail.
  // ⚠ INVERTED 2026-08-18 — DEF-212 (4) IS FIXED, on this finding's own
  // instruction ("When it lands, invert to .toHaveCount(0)"). `ConfigureSubTabs`
  // now reads the SAME `?template=` param the catalog reads and renders
  // <BillLayoutTab/> only when it is absent, so the two components stay in step
  // without either knowing the other exists. The bill layout keeps its home on
  // this tab; it just stops sharing the screen with another document's history.
  await expect(
    page.getByText("Choose the page your customers receive"),
    "FINDING 8 (fixed) — the bill-layout panel no longer follows the SET-10 detail.",
  ).toHaveCount(0);
});

test(`CR-007 SET-10 · an EMAIL and an SMS template — what actually renders ${APP_SERVER_TAG}`, async ({
  page,
}) => {
  test.setTimeout(300_000);
  // **THE FINDING THAT SHAPES THE WHOLE SCREEN.** CR-007's inventory is mostly
  // email and SMS, and NOT ONE email or SMS class in the product has a variant,
  // a body or a merge-field catalogue. So for 34 of 36 templates SET-10 has no
  // preview, no merge fields, no history and no variant switcher — it is a
  // refusal page. That is HONEST (each absence is the server's own named
  // sentence with its OQ, which is DEF-163's posture) and it is not the screen
  // CR-007 describes. This test proves the refusal is well-formed, and records
  // that the demonstrable half of SET-10 is two print classes.
  await signIn(page);

  // ⚠ AMENDED 2026-08-18, FIRST EVER RUN, AND THE AMENDMENT IS GOOD NEWS.
  // The premise above — "NOT ONE email or SMS class has a variant, a body or a
  // merge-field catalogue" — was true when this was written and is FALSE now:
  // the PO's authoring rulings took the product to 33 of 37 classes authored,
  // so `email_corrected_bill` and `sms_past_due` render a real switcher and a
  // real body, and asserting their absence asserts a regression that is
  // actually a fix. The TEST's purpose survives intact — prove the refusal is
  // WELL-FORMED — so it moves onto the classes that are still refusals: two of
  // the four contracts, which stay unauthored by ruling (NACHA-prescribed
  // wording, and an instalment schedule this renderer cannot express, OQ-244).
  // When those two are authored under CR-011, this test needs a new subject or
  // it needs deleting — say so rather than letting it rot again.
  for (const [code, kindLine, absence] of [
    ["contract_service_agreement", "PDF + e-signature", "OQ-206."],
    ["contract_deposit", "PDF + e-signature", "OQ-206."],
  ]) {
    await page.goto(templatesPath());
    await openTemplate(page, code);
    await expect(page.getByText(kindLine)).toBeVisible();

    // No variant → no switcher, and the screen says what to do instead.
    await expect(page.locator("[data-testid=variant-switcher]")).toHaveCount(0);
    await expect(page.locator("[data-testid=variant-none]")).toHaveText(
      "This template has no variant on this utility yet. Create one from the catalog to start writing it.",
    );
    // No catalogue → the merge-fields panel is a NAMED absence, not a blank.
    await expect(page.locator("[data-testid=merge-fields]")).toHaveCount(0);
    await expect(page.locator("[data-testid=merge-fields-unavailable]")).toContainText(absence);
    // No body → no preview, and the two absences are held apart (DEF-163).
    await expect(page.locator("[data-testid=preview-pane]")).toHaveCount(0);
    await expect(page.locator("[data-testid=preview-pending]")).toHaveText(
      "Type a body to see it render.",
    );
    await expect(page.locator("[data-testid=version-empty]")).toHaveText(
      "Nothing has been written for this variant yet.",
    );
  }

  // ── FINDING 9 · INVERTED 2026-08-18 — BOTH CONTROLS NOW DRAW ────────────
  // This finding recorded that CR-007's *"subject line (email)"* and *"plain
  // 160-char counter for SMS"* were unreachable: both are conditioned on
  // `data.channel`, `channel` is derived from a variant's published version,
  // and no email or SMS class had one. Its own note said **"Invert when it
  // draws."** It draws — the PO's authoring rulings gave those classes bodies
  // (33 of 37 authored), so `channel` resolves and both controls render.
  //
  // Asserted on the CLASSES THEMSELVES rather than on whatever the loop above
  // happened to leave open, because that loop now walks contracts and a
  // contract is neither email nor SMS — the previous coupling is exactly how a
  // finding gets "fixed" by drifting onto a subject that cannot show it.
  await page.goto(templatesPath());
  await openTemplate(page, "sms_past_due");
  await expect(
    page.locator("[data-testid=sms-counter]"),
    "FINDING 9 (fixed) — the 160-char SMS counter renders once the class has a body.",
  ).toHaveCount(1);
  await page.goto(templatesPath());
  await openTemplate(page, "email_corrected_bill");
  await expect(
    page.locator("[data-testid=editor-subject]"),
    "FINDING 9 (fixed) — an EMAIL template draws its subject-line box.",
  ).toHaveCount(1);
});

// ═══════════════════════════════════════════════════════════════════════════
// THE TWO RISKS THE LANE WAS POINTED AT
// ═══════════════════════════════════════════════════════════════════════════

test(`CR-007 · DEF-195 CONFIRMED — {utility_logo} prints an absence ${APP_SERVER_TAG}`, async ({
  page,
}) => {
  test.setTimeout(300_000);
  // ⚠ CHECK C, confirmed by clicking, exactly as asked. `catalogs._UTILITY_IDENTITY`
  // puts `{utility_logo}` in EVERY printable class's palette and `rendering.render`
  // supplies no value for it. The merge-field panel therefore OFFERS a token,
  // insert-on-click puts it in the body, and the preview renders a named
  // absence where a customer expects a masthead.
  await signIn(page);
  await page.goto(templatesPath());
  await openTemplate(page, "dunning");
  await page.locator("[data-testid=merge-fields]").waitFor({ timeout: 30_000 });

  // It is OFFERED — the panel row exists and is clickable.
  await expect(page.locator("[data-testid=merge-field-utility_logo]")).toBeVisible();
  await expect(page.locator("[data-testid=insert-utility_logo] code")).toHaveText("{utility_logo}");
  // …and its right-hand column already admits it has no value.
  await expect(page.locator("[data-testid=merge-field-utility_logo] td").last()).toContainText(
    "the utility's own, stamped at render from Settings → Company (BR-TEN-017).",
  );

  // CLICK IT, and look at the preview.
  await page.locator("[data-testid=editor-body]").fill("");
  await page.locator("[data-testid=editor-body]").click();
  await page.locator("[data-testid=insert-utility_logo]").click();
  await page.locator("[data-testid=editor-body]").press("End");
  await page.locator("[data-testid=editor-body]").type(" Dear {first_name}, you owe {balance}.");
  await expect(page.locator("[data-testid=editor-body]")).toHaveValue(
    "{utility_logo} Dear {first_name}, you owe {balance}.",
  );

  // THE QUOTE. `{utility_name}` resolves to the tenant's real name in the same
  // render; `{utility_logo}` does not resolve to anything.
  await expect(page.locator("[data-testid=preview-body]")).toHaveText(
    "—— Dear Sample, you owe 123.45 USD.",
    { timeout: 20_000 },
  );
  // The renderer is honest about it, in the absences drawer.
  await page.locator("[data-testid=preview-absences] summary").click();
  await expect(page.locator("[data-testid=preview-absences]")).toContainText(
    "{utility_logo} is in the 'dunning' palette and the render context carries no value for it",
  );
  // The audit's own recommendation was *"REMOVE {utility_logo} from the
  // palette"*. It is still offered on every printable class; when it is
  // removed, the assertions above go red and DEF-195 closes here.
});

test(`CR-007 · merge-field validation refuses — but names nothing ${APP_SERVER_TAG}`, async ({
  page,
}) => {
  test.setTimeout(300_000);
  // CR-007's rule: *"Merge fields validated on save — unknown token blocks save
  // with inline error."* The BLOCK works, on both the preview and the save, and
  // the server composes a genuinely good sentence naming the token and printing
  // the whole palette. The screen throws that sentence away.
  await signIn(page);
  await page.goto(templatesPath());
  await openTemplate(page, "dunning");
  await page.locator("[data-testid=editor-body]").waitFor({ timeout: 30_000 });

  await page
    .locator("[data-testid=editor-body]")
    .fill("Hi {first_name}, your {frobnicator_total} is due.");

  // The PREVIEW refuses first — editor and save share one validator, so a body
  // the pane renders is a body the save accepts.
  const previewRefusal = page.locator("[data-testid=preview-refused]");
  await expect(previewRefusal).toBeVisible({ timeout: 20_000 });
  await expect(page.locator("[data-testid=preview-pane]")).toHaveCount(0);

  // The SAVE refuses too — not a silent save.
  await page.locator("[data-testid=editor-save]").click();
  const alert = page.locator("[role=alert]").first();
  await expect(alert).toBeVisible({ timeout: 20_000 });

  // ── FINDING 10 · THE REFUSAL NAMES NOTHING ─────────────────────────────
  // The server sent, verbatim:
  //   "{frobnicator_total} is not in the 'dunning' catalog. Its palette is:
  //    account, account_no, balance, customer_name, days_late, first_name,
  //    late_fee, service_address, stage_day, support_email, support_phone,
  //    unpaid_bills, utility_address, utility_logo, utility_name … The palette
  //    IS the catalog — a token outside it has no value to merge, so it would
  //    reach the customer as an empty space or as a literal brace."
  // `en.json` renders `notifications.templates.refused` as a fixed string with
  // NO `{{detail}}` placeholder, so all of it is dropped. The sibling key
  // `billing.templates.refused` reads *"That layout cannot be used: {{detail}}"*
  // and gets it right, which is what makes this an omission rather than a
  // policy. All eleven locales carry the same detail-free string, so it is not
  // a translation gap. This is DEF-188's shape one step on: not a raw key, but
  // a sentence that names nothing — and CR-007's own rule asked for an INLINE
  // error on the field, which also does not exist.
  // ✅ FIXED 2026-08-17 (DEF-208) — and the mechanism this file was built around
  // is what caught it: the assertion below USED to pin the detail-free string
  // and went red the moment `{{detail}}` landed, with the finding quoted. All
  // eleven locales gained it, each taking its own language's separator from its
  // own working `billing.templates.refused` sibling.
  await expect(
    alert,
    "DEF-208 — the refusal NAMES the token now. If this goes red, the " +
      "`{{detail}}` placeholder was dropped from notifications.templates.refused.",
  ).toContainText("frobnicator_total");
  await expect(alert).toContainText("is not in the 'dunning' catalog");
  await expect(previewRefusal).toContainText("frobnicator_total");
  // STILL OPEN (DEF-212): CR-007 asked for an INLINE error under the field and
  // there is none. The banner names the token; the field does not point at it.
  await expect(
    page.locator("#body-error"),
    "FINDING 10 (remainder) — CR-007 asked for an INLINE error under the field.",
  ).toHaveCount(0);

  // Refused means refused: nothing was written. Re-opening from the server
  // shows the seeded body and a single version.
  // ⚠ A RELOAD STAYS ON SET-10 SINCE 2026-08-18 (DEF-212 (2)) — the detail has
  // a URL now, so this no longer bounces back to the catalog and must not
  // re-open the template by hand.
  await page.reload();
  await page.locator("[data-testid=template-back]").waitFor({ timeout: 30_000 });
  expect(page.url()).toContain("template=dunning");
  await expect(page.locator("[data-testid=version-history] tbody tr")).toHaveCount(1);
  await expect(page.locator("[data-testid=editor-body]")).not.toHaveValue(/frobnicator/);
});

// ═══════════════════════════════════════════════════════════════════════════
// VARIANT MANAGEMENT AND VERSIONING — THE WRITE WALKTHROUGH
// ═══════════════════════════════════════════════════════════════════════════

test(`CR-007 SET-10 · variant round trip: add → save → reload → publish → deactivate ${APP_SERVER_TAG}`, async ({
  page,
}) => {
  // Seven full page loads plus six writes; the 90 s default cannot hold it.
  test.setTimeout(600_000);
  // ⚠ RUN-UNIQUE ON THE KEY, NOT JUST ON THE NAME, AND FINDING 19 IS WHY THIS
  // FILE LEARNED THAT THE HARD WAY. A variant's identity is
  // `(code, category, language)`; the NAME is not part of it. The first draft
  // of this test used a fixed `commercial/es-MX` and a stamped name, and the
  // SECOND run reported *"Variant “QA 9375799” created."* — the previous run's
  // name — because the server had returned the existing row (see finding 19
  // below). So the LANGUAGE carries the stamp, and every run creates a row that
  // has never existed.
  //
  // AND IT WRITES TO `receipt`, NOT `dunning`. Variants cannot be deleted (by
  // design — deactivate only), so a write test that used `dunning` would leave
  // a second variant behind and break the read-only "the switcher draws at ONE
  // variant" assertion on the next run. One class for reading, one for writing.
  const stamp = Date.now().toString().slice(-7);
  const variantName = `QA ${stamp}`;
  const variantLanguage = `qa-${stamp}`;
  await signIn(page);
  await page.goto(templatesPath());
  await catalogTable(page).waitFor({ timeout: 30_000 });

  // ── 1 · "+ NEW TEMPLATE" SHIPPED AS "+ NEW VARIANT" ─────────────────────
  // CR-007 asked for *"'+ New template' primary top-right"*. OQ-253 is why it
  // is not that: a template CLASS is platform vocabulary and its merge-field
  // whitelist is what makes a body checkable, so a tenant-invented class could
  // never hold one. The button says what it does and the helper says why —
  // which is the right shape for a deferral, and it is a DIVERGENCE from the
  // CR's own words that the PO has not yet ruled on.
  const newButton = page.locator("[data-testid=template-new]");
  await expect(newButton).toBeVisible();
  await expect(newButton).toBeEnabled();
  await expect(
    newButton,
    "CR-007 says '+ New template'; OQ-253 shipped '+ New variant'. Open with the PO.",
  ).toHaveText("+ New variant");
  await newButton.click();
  // `.settings-helper` retired by CR-048 wave C; `data-desc` is the hook every
  // migrated description on these screens carries.
  await expect(page.locator("[data-testid=template-new-form] [data-desc]")).toContainText(
    "OQ-253 asks the Product Owner whether that is what \"+ New template\" means.",
  );

  // ── 2 · ADD A VARIANT (name + language + audience), per CR-007 ──────────
  const variantsBefore = Number(
    (await catalogRow(page, "receipt").locator("td").nth(3).innerText()).trim(),
  );
  await page.locator("[data-testid=template-new-code]").selectOption("receipt");
  await page.locator("[data-testid=template-new-name]").fill(variantName);
  await page.locator("[data-testid=template-new-audience]").selectOption("commercial");
  await page.locator("[data-testid=template-new-language]").fill(variantLanguage);
  await page.locator("[data-testid=template-new-save]").click();
  // The toast dismisses at 2 500 ms — read it immediately or not at all.
  await expect(page.locator(".toast")).toHaveText(`Variant “${variantName}” created.`, {
    timeout: 15_000,
  });

  // It is on the server, not merely on the screen: a full reload re-reads it,
  // and the catalog's Variants count moved with the write.
  await page.reload();
  await catalogTable(page).waitFor({ timeout: 30_000 });
  await expect(catalogRow(page, "receipt").locator("td").nth(3)).toHaveText(
    String(variantsBefore + 1),
  );
  await openTemplate(page, "receipt");
  const tabs = page.locator("[data-testid=variant-switcher] [role=tab]");
  const qaTab = tabs.filter({ hasText: variantName });
  await expect(qaTab).toHaveCount(1);

  // ── FINDING 19 · ADDING A VARIANT THAT ALREADY EXISTS REPORTS SUCCESS ──
  // `template_service.register` is `get_or_create` on `(code, category,
  // language)` and says why: *"A tenant clicking twice must not end up with two
  // 'Residential receipt in es-MX' variants holding different published
  // bodies."* The RULE is right. What reaches the person is not: the route
  // answers **201 Created** for a row it did not create, the screen fires the
  // success toast, and the toast prints the EXISTING variant's name — so a
  // System Admin who types "Large print" over an existing commercial/es-MX
  // variant is told *"Variant “Spanish commercial” created."* and has created
  // nothing. Nothing on the screen says the name was ignored.
  await page.goto(templatesPath());
  await catalogTable(page).waitFor({ timeout: 30_000 });
  await page.locator("[data-testid=template-new]").click();
  await page.locator("[data-testid=template-new-code]").selectOption("receipt");
  await page.locator("[data-testid=template-new-name]").fill(`DIFFERENT NAME ${stamp}`);
  await page.locator("[data-testid=template-new-audience]").selectOption("commercial");
  await page.locator("[data-testid=template-new-language]").fill(variantLanguage);
  await page.locator("[data-testid=template-new-save]").click();
  // ✅ FIXED 2026-08-17 (DEF-207) — and it took BOTH halves. The route now
  // answers 200 for a fetch, `addTemplateVariant` reads the status the client
  // was already carrying, and the toast says which of the two things happened.
  // Fixing only the backend would have left this exact assertion green: the
  // status changed and the sentence did not.
  await expect(
    page.locator(".toast"),
    "DEF-207 — re-adding an existing variant must say it ALREADY EXISTS, not " +
      "report a creation under a name the user did not type.",
  ).toHaveText(`Variant “${variantName}” already exists.`, { timeout: 15_000 });
  await page.reload();
  await catalogTable(page).waitFor({ timeout: 30_000 });
  await expect(
    catalogRow(page, "receipt").locator("td").nth(3),
    "FINDING 19 — nothing was created, and the count proves it",
  ).toHaveText(String(variantsBefore + 1));
  await openTemplate(page, "receipt");

  // ── FINDING 11 · FIXED 2026-08-18 (DEF-212 (3)) ─────────────────────────
  // `active` on the payload means *"has a published version"*, and the tab used
  // to render its negation as **Inactive** — the same word deactivate produces.
  // So a variant created ten seconds ago was called Inactive, and pressing
  // Deactivate on it was REFUSED afterwards by the server. Two states, one
  // word, and the control live when it could not work.
  await qaTab.click();
  await expect(
    qaTab.locator("[data-badge]"),
    "FINDING 11 (fixed) — a variant nobody has published yet says so, and never " +
      "borrows the word a deactivated one uses.",
  ).toHaveText("Not published yet");
  // BR-SHL-025: disabled BEFORE the click, with the reason on the control.
  await expect(page.locator("[data-testid=deactivate-variant]")).toBeDisabled();
  expect(
    await page.locator("[data-testid=deactivate-variant]").getAttribute("title"),
  ).toContain("There is nothing to deactivate");

  // ── 3 · EDIT THE WORDING, SAVE, AND RELOAD ──────────────────────────────
  await qaTab.click();
  const marker = `QA-${stamp}`;
  await page
    .locator("[data-testid=editor-body]")
    .fill(`${marker} Hi {first_name}, we received {amount}. Balance now {balance}.`);
  // BR-BIL-026: the button says what it does — an edit is a NEW version.
  await expect(page.locator("[data-testid=editor-save]")).toHaveText("Save as new version");
  await expect(page.locator("[data-testid=preview-body]")).toHaveText(
    `${marker} Hi Sample, we received 123.45 USD. Balance now 123.45 USD.`,
    { timeout: 20_000 },
  );
  await page.locator("[data-testid=editor-save]").click();
  await expect(page.locator(".toast")).toHaveText(
    "Saved as v1 — a draft. Publish it to make it live.",
    { timeout: 15_000 },
  );

  // PERSISTED, not optimistic: a FULL page reload re-reads the server.
  // ── FINDING 12 · FIXED 2026-08-18 (DEF-212 (2)) · SET-10 HAS A URL ──────
  // Opening a template used to be component state, so a reload landed back on
  // the catalog and the selected VARIANT was lost with it — a reload silently
  // moved you from the variant you were editing to the default one, and no
  // walkthrough could deep-link a template. `?template=<code>&variant=<id>` is
  // the same answer CR-004 gave the reference-data lists with `?list=<code>`.
  const detailUrl = page.url();
  expect(
    detailUrl,
    "FINDING 12 (fixed) — the open template is in the URL.",
  ).toContain("template=receipt");
  expect(detailUrl, "…and so is the variant being edited").toContain("variant=");
  await page.reload();
  await page.locator("[data-testid=template-back]").waitFor({ timeout: 30_000 });
  expect(page.url(), "a reload STAYS on SET-10").toContain("template=receipt");
  await expect(
    tabs.filter({ hasText: variantName }),
    "…on the variant that was selected, not the default one",
  ).toHaveAttribute("aria-selected", "true");
  await expect(
    page.locator("[data-testid=version-history] tbody tr"),
    "the save survived a full reload",
  ).toHaveCount(1);
  await expect(page.locator("[data-testid=version-1]")).toContainText("Draft");
  await expect(page.locator("[data-testid=editor-body]")).toHaveValue(new RegExp(marker));

  // ── 4 · VERSIONING · PUBLISH, THEN SAVE AGAIN ───────────────────────────
  await page.locator("[data-testid=publish-1]").click();
  await expect(page.locator(".toast")).toHaveText("v1 published. It applies to future messages only.", {
    timeout: 15_000,
  });
  await expect(page.locator("[data-testid=version-1]")).toContainText("Published");

  await page
    .locator("[data-testid=editor-body]")
    .fill(`${marker} SECOND Hi {first_name}, we received {amount}.`);
  await page.locator("[data-testid=editor-save]").click();
  await expect(page.locator(".toast")).toHaveText(
    "Saved as v2 — a draft. Publish it to make it live.",
    { timeout: 15_000 },
  );
  await expect(page.locator("[data-testid=version-history] tbody tr")).toHaveCount(2);

  // ── FINDING 13 · FIXED 2026-08-18 (DEF-212 (1)) ─────────────────────────
  // The editor used to seed from `versions.find(published) ?? versions[0]`, so
  // once a published version existed it ALWAYS loaded that one: the v2 draft
  // saved five minutes ago was in no textarea and no preview, and the only
  // route back to your own unfinished wording was Restore, which makes a THIRD
  // version holding it. A drafting workflow you cannot resume is not one.
  await page.reload();
  await page.locator("[data-testid=template-back]").waitFor({ timeout: 30_000 });
  await expect(page.locator("[data-testid=version-2]")).toContainText("Draft");
  await expect(
    page.locator("[data-testid=editor-body]"),
    "FINDING 13 (fixed) — re-opening loads the DRAFT, which is the unfinished " +
      "work somebody left off doing.",
  ).toHaveValue(/SECOND/);
  // …and the screen says WHICH version is in the box, which it never did.
  await expect(page.locator("[data-testid=editor-source]")).toContainText(
    "Editing v2, a draft",
  );
  // Every history row can be opened, so the published one is one click away.
  await page.locator("[data-testid=open-version-1]").click();
  await expect(page.locator("[data-testid=editor-body]")).toHaveValue(new RegExp(`${marker} Hi`));
  await expect(page.locator("[data-testid=editor-source]")).toContainText("Editing v1");
  await page.locator("[data-testid=open-version-2]").click();

  // ── 5 · RESTORE PUTS AN OLD BODY IN A NEW DRAFT ─────────────────────────
  // CLAUDE.md rule 4: a published body is evidence of what a customer was sent,
  // so history is never rewritten. The toast is the server's own sentence and
  // it names WHICH version the wording came from.
  await page.locator("[data-testid=restore-1]").click();
  await expect(page.locator(".toast")).toContainText(
    "v3 is a new DRAFT holding v1's body. v1 is unchanged and every message pinned to it still renders from it",
    { timeout: 15_000 },
  );
  await expect(page.locator("[data-testid=version-history] tbody tr")).toHaveCount(3);
  await expect(page.locator("[data-testid=version-1]")).toContainText("Published");

  // ── 6 · DEACTIVATE, AND THE CONSUMERS ARE NAMED ─────────────────────────
  // CR-007: *"a variant in use by a notification rule can't be deleted —
  // deactivate only, with usage warning listing consumers"*. There is no Delete
  // control anywhere on SET-10, which is the correct end state; and deactivate
  // reports the server's own consumer COUNT rather than the screen's guess.
  await expect(page.getByRole("button", { name: /^delete/i })).toHaveCount(0);
  const deactivate = page.locator("[data-testid=deactivate-variant]");
  await expect(deactivate).toBeEnabled();

  // ── FINDING 14 · FIXED IN TWO PASSES — 2026-08-17 AND 2026-08-18 ────────
  // It used to be ONE CLICK on an unstyled default button with no confirm and
  // no consequence box, and on the SEEDED default variant that single click
  // leaves the one past-due reminder the product can actually produce with
  // nothing to resolve. This spec still refuses to press it on the seeded
  // variant; it is pressed only on the disposable one.
  //
  // 2026-08-17 (DEF-209, PO "Okay"): the DANGER TIER (B14 rule 6) and a confirm
  // carrying a consequence (rule 11) — two different sentences, because
  // deactivating the DEFAULT variant is a materially different act.
  // 2026-08-18 (DEF-209 remainder): the way back is named. There is no
  // unarchive in `template_service` and no route for one, so the honest answer
  // is the two-step path that exists: restore the archived version into a new
  // draft, then publish it.
  expect(
    await deactivate.getAttribute("class"),
    "FINDING 14 (fixed) — B14 rule 6's danger tier.",
  ).toContain("btn-danger");
  await deactivate.click();
  const consequence = page.locator(".confirm-consequence");
  await expect(
    consequence,
    "FINDING 14 (fixed) — BR-SHL-032 / B14 rule 11: the confirm names the act " +
      "and states what it costs.",
  ).toBeVisible();
  await expect(consequence).toContainText("falls back to the default one");
  await expect(
    consequence,
    "FINDING 14 (fixed) — and what it takes to undo it, BEFORE the click.",
  ).toContainText("There is no one-click reactivate");
  await page.locator(".modal-foot button.btn-primary").click();
  await expect(page.locator(".toast")).toHaveText(
    "0 queued message(s) name this exact version and keep it forever — a published body " +
      "is evidence of what a customer was sent (CLAUDE.md rule 4), so it is archived and " +
      "never deleted.",
    { timeout: 15_000 },
  );
  // DEF-212 (3): the word is the one that is TRUE of this variant now — it has
  // an archived version, which "Not published yet" above did not.
  await expect(tabs.filter({ hasText: variantName }).locator("[data-badge]")).toHaveText(
    "Deactivated",
  );
  // BR-SHL-025 — the control a person now goes looking for is present and
  // disabled, carrying the two-step path as its reason, rather than absent.
  const reactivate = page.locator("[data-testid=reactivate-variant]");
  await expect(reactivate, "FINDING 14 (fixed) — it is not hidden").toHaveCount(1);
  await expect(reactivate, "…and it is not a live button onto nothing").toBeDisabled();
  await expect(page.locator("[data-testid=reactivate-helper]")).toContainText(
    "choose Restore on its last version",
  );
  // ⚠ REMAINDER, RECORDED RATHER THAN ASSERTED AS DONE: DEF-209's prevention
  // column asked for the SERVER's own `resolution_after` sentence ("generation
  // HOLDS rather than inventing a body") in the confirm, on the grounds that it
  // is "already on the wire". It is on the DEACTIVATE RESPONSE — i.e. after the
  // click — and the GET detail payload carries no such field, so a pre-click
  // confirm cannot render it without a new read. The screen states the same
  // consequence in its own catalogued words instead.
  await expect(page.locator("main.view")).not.toContainText(
    "generation HOLDS rather than inventing a body",
  );
});

// ═══════════════════════════════════════════════════════════════════════════
// B14 · THE UI-CONVENTIONS AUDIT
// ═══════════════════════════════════════════════════════════════════════════

test(`CR-007 · B14 audit of SET-09 and SET-10 ${APP_SERVER_TAG}`, async ({ page }) => {
  test.setTimeout(300_000);
  // B14's own honest half: *"NOT enforced — no gate reads rendered output at
  // all. Rules 1, 3–15, 17, 19 and 20 are RATIFIED and unchecked."* This is the
  // browser walkthrough that file says is the only mechanism there is. Findings
  // 1–6 are asserted with the catalog test above; these are the rest.
  await signIn(page);
  await page.goto(templatesPath());
  await catalogTable(page).waitFor({ timeout: 30_000 });

  // ── FINDING 15 · FIXED 2026-08-18 (DEF-211) ─────────────────────────────
  // *"Row actions are ICONS with tooltips, never text links. Vocabulary: 👁 view
  // · ✎ edit …"* — and CR-007 itself asked for *"Actions (✎ edit, 👁 preview)"*.
  // What shipped was one button reading "Open" with no title, no aria-label and
  // no icon. Both icons carry their label as BOTH `title` and `aria-label`,
  // because an icon with no accessible name passes a text-absence check and is
  // unusable without a mouse.
  const rowAction = page.locator("[data-testid=template-open-dunning]");
  await expect(rowAction).toHaveText("");
  expect(await rowAction.getAttribute("title")).toBe("View “Past-due reminder”");
  expect(await rowAction.getAttribute("aria-label")).toBe("View “Past-due reminder”");
  expect(await rowAction.locator("svg").count(), "an icon, not a word").toBe(1);
  const rowEdit = page.locator("[data-testid=template-edit-dunning]");
  expect(await rowEdit.getAttribute("aria-label")).toBe("Edit “Past-due reminder”");
  await expect(
    catalogRow(page, "dunning").locator("td:last-child button"),
    "B14 rule 15 — max two visible row actions",
  ).toHaveCount(2);

  // ── FINDING 16 · RULE 5 · THREE BUTTON SIZES, NOT TWO ──────────────────
  // *"Two button sizes only — default and small (12px). No inline font sizes."*
  // 13.3333 px is the UA default for a `<button>` nobody styled, and it appears
  // beside the app's own 13 px and 14 px on the same screen.
  // FIXED FOR EVERY BUTTON THESE TWO SCREENS OWN (2026-08-18, DEF-211): each
  // carries `.btn` (14px, the default tier) or `.settings-icon-btn` (12px, the
  // small tier). Seven of the class names they used — `.settings-helper`,
  // `.settings-chips`, `.settings-actions`, `.settings-inline-form`,
  // `.settings-tokens`, `.badge`, `.preview-strip` — were declared by NO
  // stylesheet in the repo, which is why a third size could appear at all.
  //
  // ⚠ TWO REMAINDERS, BOTH THE SHARED COMPONENT'S, and both now CLOSED by
  // CR-016's design-system slice (DEF-311, 2026-08-19). Kept in full because
  // the reasoning is why they were left open, and the fix landed where the
  // note said it had to — in the shared component, once, for every list screen:
  //   · `.table-columns-up` (the ⋮ menu's reorder ↑) set border, background
  //     and padding and NO font-size, so it rendered at the UA default —
  //     13.3333px — on every list screen. It declares 12px now, rule 5's own
  //     small tier. That value can be produced by no source check: it exists
  //     only in the render.
  //   · **13px was `DataTable.css`'s OWN** (its lines 25/37/93/172). It
  //     appeared on this screen BECAUSE the rule-20 fix moved SET-09 onto the
  //     shared table, and the note said overriding it locally would be an
  //     inline font size — the very thing rule 5 forbids — so it belonged with
  //     DEF-223's remainder in the shared component. That is where it was
  //     fixed: `.table-search-clear` and `.table-columns-item` now sit in the
  //     two tiers, and `.data-table` reads `--table-font-size`.
  // So the expected set is rule 5's two tiers and nothing else.
  const catalogSizes = await page
    .locator("main.view button")
    .evaluateAll((els) => Array.from(new Set(els.map((e) => getComputedStyle(e).fontSize))).sort());
  expect(
    catalogSizes,
    "FINDING 16 — B14 rule 5 holds on this screen: two button sizes, the " +
      "small tier (12px) and the default (14px), and nothing else.",
  ).toEqual(["12px", "14px"]);

  // ── FINDING 17 · RULE 18 · NOT ONE DESCRIPTION IS CAPPED AT 80% ────────
  // Rule 18 shipped as the `--desc-measure` token (80%, PO 2026-08-16 *"make it
  // 80%"*, *"across the app"*). `.panel-hint`, `.settings-helper` and
  // `.settings-refusal` — the three classes carrying EVERY description on these
  // two screens, including the 700-character refusal paragraph under each of
  // the 36 catalog rows — all compute `max-width: none`. Seventeen declarations
  // point at the token elsewhere in the app; none of them is here.
  // FIXED 2026-08-18 (DEF-211). `.settings-helper` was the extreme case: it was
  // not merely uncapped, it was a class name NO stylesheet declared, so the
  // token had nothing to reach it through.
  // ⚠ `.settings-helper` IS RETIRED (CR-048 wave C) and `[data-desc]` replaces
  // it — the SAME elements, reached by a hook instead of a styling class. The
  // migrated descriptions carry `max-w-measure`, which resolves through
  // `--container-measure` to the same `--desc-measure` 80%. `.panel-hint` stays
  // in the list because `Panel` still renders it on every Settings screen.
  const measures = await page
    .locator("main.view .panel-hint, main.view [data-desc], main.view .settings-refusal")
    .evaluateAll((els) => Array.from(new Set(els.map((e) => getComputedStyle(e).maxWidth))));
  expect(measures.length, "there are descriptions on this screen to measure").toBeGreaterThan(0);
  expect(
    measures.filter((value) => value === "none"),
    "FINDING 17 (fixed) — every description carries B14 rule 18's 80% measure.",
  ).toEqual([]);

  // ── FINDING 18 · RULE 20 · HALF FIXED, AND THE HALF LEFT IS DEF-223's ──
  // *"Table type is one size (13.5px) everywhere; no inline overrides."*
  // TWO SEPARATE FIXES LANDED SINCE THIS WAS WRITTEN. `.settings-table` stopped
  // hard-coding 14px and reads `--table-font-size` (DEF-223, 2026-08-17), so
  // SET-10's two panel tables render the ratified 13.5px. And SET-09's LIST
  // moved onto the shared `DataTable` (DEF-211, 2026-08-18), which is what
  // brought rules 13, 14 and 16 with it.
  //
  // ⚠ WHAT WAS LEFT WAS EXACTLY DEF-223's REMAINDER, and it was deliberately
  // not fixed from here: `DataTable` rendered 14px cells and 12px heads, and it
  // draws EVERY list in the product — moving it is its own change with its own
  // walkthrough, which is why the token's own docstring said so in writing.
  // ✅ CLOSED 2026-08-19 by CR-016's design-system slice (DEF-310), which is
  // that change: `.data-table` reads `--table-font-size`, `.data-table td`
  // declares no size of its own, and the walkthrough is the computed-style
  // register in `e2e/ui-conformance-baseline.json`. The 12px head stays and is
  // now the product's ONE header tier — see that register and OQ-267 for why
  // it is 12px where r10 draws 11px.
  await openTemplate(page, "dunning");
  await page.locator("[data-testid=merge-fields]").waitFor({ timeout: 30_000 });
  const panelTables = await page
    .locator("[data-testid=merge-fields] td, [data-testid=version-history] td")
    .evaluateAll((els) => Array.from(new Set(els.map((e) => getComputedStyle(e).fontSize))));
  expect(
    panelTables,
    "FINDING 18 (SET-10 half, fixed) — B14 rule 20's 13.5px, from the token.",
  ).toEqual(["13.5px"]);
  await page.goto(templatesPath());
  await catalogTable(page).waitFor({ timeout: 30_000 });
  const listTable = await catalogTable(page)
    .locator("tbody td")
    .evaluateAll((els) => Array.from(new Set(els.map((e) => getComputedStyle(e).fontSize))));
  expect(
    listTable,
    "FINDING 18 (remainder, DEF-223 — CLOSED) — the shared DataTable renders " +
      "rule 20's 13.5px, on every list in the product.",
  ).toEqual(["13.5px"]);

  // ── RULE 19 · SEARCH PLACEHOLDER · FIXED 2026-08-18 (DEF-211) ──────────
  // *"Search placeholders read 'Search {entities}…' per module."* It was a
  // LABEL with no placeholder and no ellipsis. It is both now — and the input
  // is deliberately still the module's own rather than `DataTable`'s, whose
  // shared box reads "Search this list" and takes no placeholder prop. That is
  // why `searchFields` is left undeclared on the SET-09 config.
  expect(await page.locator("[data-testid=template-search]").getAttribute("placeholder")).toBe(
    "Search templates…",
  );
  await expect(page.locator(".table-toolbar")).toContainText("Search templates");
});

// ── Lifecycle ─────────────────────────────────────────────
// packet: CR-007 (12-governance/11-change-requests.md, BUILD RECORD + the
//   addendum of 2026-08-16 and the appendix of 2026-08-17) · PO bar
//   "confirmation based on web click" · B14 (04-docs/02-decisions/14-ui-conventions.md)
//   · BR-NOT-014 · BR-SHL-025 · DEF-187 (why a green suite is not a walkthrough)
//   · DEF-195 ({utility_logo})
// generated: 2026-08-17 by the CR-007 browser-walkthrough QA lane
// gates: run against `08-qa/01-e2e/stack/boot_stack.sh` on a freshly seeded
//   `brazosbend` (Postgres + Django + the BUILT SPA on one origin); every
//   quoted string copied from the running screen, never from a catalogue or a
//   payload
// exceptions: (1) THIS SPEC PINS DEFECTS RATHER THAN ASSERTING CORRECTNESS —
//   see THE INVERSION CONTRACT at the top. Fourteen numbered findings were
//   asserted as they behaved on 2026-08-17, each with the sentence that must
//   replace the assertion when it is fixed. ⚠ THIRTEEN OF THOSE ASSERTIONS WERE
//   REPLACED ON 2026-08-18 (DEF-209 · DEF-211 · DEF-212) and now assert the
//   fixed behaviour; the rest still pin open findings and say whose they are.
//   ⚠ THIS FILE HAS NOT BEEN RUN SINCE THAT PASS: Django is not installed in
//   the container the fix was written in, so the changes below are a careful
//   read of the new markup and NOT a booted walkthrough. It needs one before
//   any of the `(fixed)` labels is believed — that is the whole point of this
//   file (hard-won law 6), and saying so is better than implying otherwise.
//   (2) IT WRITES — a run-unique `commercial / qa-<stamp>` variant on
//   `receipt`, never the seeded default variant, never `dunning` (which the
//   read-only tests need pristine), and never on a tenant that is not
//   disposable.
//   (3) IT DELIBERATELY DOES NOT PRESS DEACTIVATE ON THE SEEDED DEFAULT
//   VARIANT (finding 14): one unconfirmed click there leaves the only past-due
//   reminder the product can produce with nothing to resolve.
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
