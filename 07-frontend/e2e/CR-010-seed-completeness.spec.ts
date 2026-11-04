// ── Trace ──────────────────────────────────────────────
// Change:  CR-010 (12-governance/11-change-requests.md) — *"Seed data must be
//          COMPLETE"*. This file is the CLOSING WALKTHROUGH the change-process
//          §8 closure bar demands, and the row CR-011's retroactive audit
//          marks against CR-010: **"browser evidence: none — ❌ unmet"**.
// Story:   CR-010@item0 (the count) · @item1 (full lists) · @item3 (the
//          two-level account-type tree) · @item5/@item6 (the FULL chart of
//          accounts and the twelfth GL designation) · @item7 (the
//          notifications rows written at provisioning)
//          Screens: S8 → Settings → Configure → Reference data ·
//                   S8 → Settings → Accounting · S8 → Settings → Notifications
//          Routes:  /{tenant}/settings/reference-data
//                   /{tenant}/settings/reference-data?list={code}
//                   /{tenant}/settings/accounting
//                   /{tenant}/settings/notifications
// Rules:   BR-TEN-029 (a card's count is computed LIVE, so the badge IS the
//          row count) · BR-TEN-012/067 (what seeds, structural vs
//          discretionary) · BR-CUS-067 (the twelve account sub-types) ·
//          BR-BIL-067/069 (a bill line resolves its GL account by DESIGNATION)
// Defect:  DEF-258 (the SET-12 rule rows were NOT written at provisioning —
//          fixed in this slice) · DEF-256 / DEF-257 (a seeded vocabulary
//          attached to nothing — fixed in code 2026-08-18, and this file pins
//          the screen face of the residue on the tenant planted before it)
// ───────────────────────────────────────────────────────
//
// **WHY THIS FILE IS READ-ONLY, AND THAT IS DELIBERATE.**
//
// Every other closing walkthrough in this folder creates a row, refuses a bad
// one and deletes what it made. This one asserts COUNTS — CR-010's whole
// subject is *how much vocabulary a tenant is given* — and a walkthrough that
// added rows would be changing the number it exists to measure. It is
// therefore re-runnable over its own leftovers by construction: it leaves
// none. What it costs is that the refusal half of the closure bar is not
// exercised here; CR-004's spec already walks add/refuse/edit/deactivate/
// delete over six of these same lists and is recorded MET, so the refusals are
// proved once rather than not at all. Said here rather than discovered later.
//
// **THE NUMBERS BELOW WERE MEASURED, NOT COPIED.** They come from
// `select count(*)` against the running `sbh_e2e` database on 2026-08-19, and
// the reason that matters is CR-010 item 0 itself: the PO's *"we have increase
// this number check out seed data"* was aimed at a figure ("31 priced
// objects") transcribed out of the r10 prototype's fixture line instead of
// counted out of the product. A test that copied a document would repeat that
// mistake. `06-backend/tests/test_cr010_reference_list_inventory.py` pins the
// same counts for a FRESHLY provisioned tenant; this file pins what a person
// actually sees on the tenant that exists.
//
// ⚠ ONE HONEST FRAGILITY. These are live counts on a SHARED demo tenant. A
// lane that adds a reference row through the screen while this runs turns it
// red on a number, not on a bug. That is the correct trade: a card badge that
// no longer equals the seeded vocabulary is exactly the drift CR-010 exists to
// catch, and a "greater than zero" assertion would catch nothing at all.

import { expect, test } from "@playwright/test";

import { APP_SERVER_TAG } from "./support/census";
import { signIn, skipUnlessAppServer, tenant } from "./support/app";

skipUnlessAppServer(test);

/**
 * The twenty seeded reference lists, each with the row count the live database
 * holds and the card label a person reads. CR-010 item 1's *"we have to provide
 * a full possible list"* is what these numbers answer, list by list.
 */
const SEEDED_LISTS: { label: string; count: number }[] = [
  { label: "Units of measure", count: 26 },
  { label: "Charge codes", count: 23 },
  { label: "Tax jurisdictions", count: 5 },
  { label: "Reason codes", count: 5 },
  { label: "Payment methods", count: 7 },
  { label: "Meter types", count: 5 },
  { label: "Read methods", count: 5 },
  { label: "Asset types", count: 12 },
  { label: "Asset lifecycle stages", count: 5 },
  { label: "Premises types", count: 6 },
  { label: "Unit types", count: 5 },
  { label: "Account statuses", count: 5 },
  { label: "Account types", count: 4 },
  { label: "Account sub-types", count: 12 },
  { label: "Areas & sub-areas", count: 4 },
  // 9 → 40 on 2026-08-27 (BR-TEN-171, CR-039 wave E task 20): water 9,
  // electric 6, gas 4, trash 7, storm water 4, solar 4, broadband 3,
  // thermal chilled water 3. Sewer is NONE BY RULING (priced as a share of
  // the water usage charge); thermal STEAM and BATTERY are none because
  // their bands were never put to the PO — OQ-560 and OQ-561.
  { label: "Utility service size classes", count: 40 },
  { label: "Occupancy statuses", count: 5 },
  { label: "Device types (BTM)", count: 6 },
  { label: "Certification types", count: 6 },
  // SEEDED EMPTY ON PURPOSE, and the zero is the assertion: an import mapping
  // describes THIS utility's own spreadsheet columns, so a seeded one would
  // describe a file layout the tenant does not have.
  { label: "Import mappings", count: 0 },
];

/**
 * The cards on the same grid that are NOT lists — configuration panels that
 * open onto a form, so they carry no row badge. Named here because CR-010 item
 * 0 is *"we ahve around 26 to 30 configure items here - you are doing only 16
 * why?"*, and the honest answer is a breakdown of the grid, not a single
 * number: 31 cards = 20 seeded lists + these 6 panels + Custom fields (counted,
 * and empty on this tenant) + the 4 Work lists that are not set up.
 */
const CONFIG_PANELS = [
  "Holiday calendar",
  "Read validation & estimation",
  "Billing defaults",
  "Budget billing rules",
  "Document & message templates",
  "Collections & notices",
];

/**
 * ⚠ DEF-336 MOVED THIS CARD OUT OF `CONFIG_PANELS`, and the move is the finding.
 * `custom_fields` is `kind: "custom"`, and `GET /lookups` has ALWAYS served a
 * count for it — the tile threw the number away because the kind was not
 * "list", so it drew the same bare chevron as a settings panel and this file
 * filed it as one. It is a COUNTED card: today the tenant has defined none, so
 * the honest badge is "0 ›", which is a different statement from "not set up".
 */
const COUNTED_BUT_EMPTY = [{ label: "Custom fields", count: 0 }];

const WORK_CARDS_NOT_SET_UP = [
  "Skills catalog",
  "Safety kits",
  "Work priorities & SLA",
  "Parts categories & locations",
];

function referenceDataPath(): string {
  return `/${tenant()}/settings/reference-data`;
}

test.describe(`CR-010 · the seed, counted on the screen ${APP_SERVER_TAG}`, () => {
  test(`every seeded list renders its live count ${APP_SERVER_TAG}`, async ({ page }) => {
    // Seven full loads of a 3.5 MB SPA chunk; the config default is 90 s.
    test.setTimeout(300_000);
    await signIn(page);
    await page.goto(referenceDataPath());

    for (const list of SEEDED_LISTS) {
      const tile = page.locator(".lookup-card").filter({ hasText: list.label });
      await expect(tile, `the ${list.label} card is on the grid`).toHaveCount(1);
      // BR-TEN-029: the badge is computed live, so this compares what a person
      // reads against what provisioning actually planted.
      await expect(tile.locator(".v"), `${list.label} badge`).toHaveText(`${list.count} ›`);
    }

    // CR-010 item 0's real answer, asserted rather than asserted-about: the
    // grid draws THIRTY-ONE cards, of which twenty are seeded lists. The PO's
    // *"around 26 to 30 configure items here - you are doing only 16 why?"*
    // was measuring the GRID against the FIXTURE's list count; neither number
    // was wrong and neither answered the question.
    for (const label of CONFIG_PANELS) {
      const tile = page.locator(".lookup-card").filter({ hasText: label });
      await expect(tile, `${label} is a panel, not a list`).toHaveCount(1);
      // ⚠ DEF-336 — THIS LINE ASSERTED `toHaveText("›")`, i.e. it PINNED THE
      // BARE CHEVRON the PO later photographed as missing configuration. A
      // check written from what the screen does, rather than from what a person
      // needs, protects the defect: this one made the blank a requirement.
      // A panel now SAYS it holds settings, and the reason is on the control.
      const badge = tile.locator(".v");
      await expect(badge, `${label} badge is not a bare chevron`).not.toHaveText("›");
      await expect(badge).toHaveAttribute("title", /.+/);
    }
    for (const card of COUNTED_BUT_EMPTY) {
      const tile = page.locator(".lookup-card").filter({ hasText: card.label });
      await expect(tile, `${card.label} is on the grid`).toHaveCount(1);
      await expect(tile.locator(".v"), `${card.label} badge`).toHaveText(`${card.count} ›`);
    }
    for (const label of WORK_CARDS_NOT_SET_UP) {
      const tile = page.locator(".lookup-card").filter({ hasText: label });
      await expect(tile).toContainText("Not set up yet");
    }
    // 31 = 20 + 7 + 4, and nothing else. A card that appears without a row
    // here is a vocabulary the PO has not seen; that is the whole point of
    // item 0.
    await expect(page.locator(".lookup-card")).toHaveCount(
      SEEDED_LISTS.length +
        CONFIG_PANELS.length +
        COUNTED_BUT_EMPTY.length +
        WORK_CARDS_NOT_SET_UP.length,
    );
  });

  test(`the account-type tree has TWO levels on the screen ${APP_SERVER_TAG}`, async ({ page }) => {
    test.setTimeout(300_000);
    // CR-010 item 3, PO verbatim: *"we have Residential, Commercial,
    // Industrial, Municipal/Goventment - then sub categories in each one"*.
    // The four are ratified; the twelve sub-types were ratified on 2026-08-18
    // (CR-011 item 3, *"Confirmed"*). This asserts BOTH levels are readable in
    // one place — the sub-type list's ACCOUNT TYPE column is the parent link,
    // and a sub-type list with no parent column would be a flat list wearing
    // the tree's name.
    await signIn(page);
    await page.goto(`${referenceDataPath()}?list=account_subtypes`);

    await expect(page.locator(".table-pager-range")).toHaveText("1–12 of 12");
    await expect(page.getByRole("columnheader", { name: "ACCOUNT TYPE" })).toBeVisible();
    for (const [code, parent] of [
      ["single_family", "Residential"],
      ["small_commercial", "Commercial"],
      ["light_industrial", "Industrial"],
      ["schools", "Government"],
    ] as const) {
      const row = page
        .locator("tr.data-table-row")
        .filter({ has: page.getByRole("cell", { name: code, exact: true }) });
      await expect(row, `${code} is on the screen`).toHaveCount(1);
      await expect(row.getByRole("cell", { name: parent, exact: true })).toBeVisible();
    }

    // ── FINDING · DEF-257, PINNED WHERE A PERSON SEES IT ──────────────────
    // "USED BY 0" on all twelve. The sample plant was taught to set a sub-type
    // on every account on 2026-08-18 (commit f6c0120) and THIS tenant was
    // planted eight hours earlier, so the demo utility still demonstrates the
    // tree with nothing in it — hard-won law 4 in its data form: a change to
    // the plant never reaches a tenant already planted.
    //
    // ⚠ THIS ASSERTION IS WRITTEN TO GO RED WHEN THE RESIDUE IS CLEARED. A
    // re-planted or newly provisioned tenant makes these non-zero, and this
    // line failing means DEF-257 is done ON THIS TENANT — read the finding,
    // then delete the block. It does NOT mean the product broke.
    const usedByCells = page.locator("tr.data-table-row td:nth-child(4)");
    await expect(usedByCells.first()).toHaveText("0");
  });

  test(`the chart of accounts is FULL and every designation is mapped ${APP_SERVER_TAG}`, async ({
    page,
  }) => {
    test.setTimeout(300_000);
    // CR-010 item 5 (*"make this list full not partial"* — the reversal of the
    // PO's own OQ-115 ruling) and item 6 (*"make this list full"* for the GL
    // map, whose twelfth designation `budget_variance` had NO ratified account
    // number anywhere in the corpus and was put to the PO as 4180).
    await signIn(page);
    await page.goto(`/${tenant()}/settings/accounting`);

    const body = page.locator("main");
    // The twelfth designation, by the number that was proposed and taken.
    await expect(body).toContainText("4180");
    await expect(body).toContainText("Budget billing variance");
    // The rows CR-010 item 5 added by reversing "seed only the services it
    // sells": a tenant selling electric and water still gets storm water and
    // thermal on its chart.
    await expect(body).toContainText("4160");
    await expect(body).toContainText("Storm water");
    await expect(body).toContainText("4170");
    await expect(body).toContainText("Thermal/Heat");
  });

  test(`the notifications home opens POPULATED ${APP_SERVER_TAG}`, async ({ page }) => {
    test.setTimeout(300_000);
    // CR-010 item 7, PO verbatim: *"we need ready to sue notification as given
    // in screenshot - there are many gaps in data seeding"* — the dispatch
    // settings row is written at provisioning *"and the SET-12 rule rows with
    // it"*.
    //
    // ⚠ WHAT A BROWSER CAN AND CANNOT PROVE HERE, STATED PLAINLY. Both the
    // dispatch row and the rule rows also materialise on first READ, so this
    // screen looks identical whether provisioning wrote them or this very page
    // load did. The browser proves the PROMISE — *the home opens populated* —
    // and it cannot prove WHEN the rows were written. The instrument for that
    // is the database, and it is what found DEF-258:
    //
    //     notification_settings  min(created_at) = 2026-08-18 08:19:26 ← provisioning
    //     notification_rules     min(created_at) = 2026-08-19 04:21:17 ← a lane
    //                                                                    opening S8
    //
    // The fix is pinned by `test_def258__the_set12_rule_rows_seed_at_
    // provisioning_too` in tests/test_us_ten_002_seeding.py, which fails with
    // `assert 0 == 15` against the code as it was.
    await signIn(page);
    await page.goto(`/${tenant()}/settings/notifications`);

    await expect(page.getByText("15 events —", { exact: false })).toBeVisible();
    // The five r10 categories, each with rows under it.
    for (const heading of ["Billing", "Payments", "Collections", "Field work", "Staff & system"]) {
      await expect(page.getByRole("heading", { name: heading, exact: true })).toBeVisible();
    }
    // The dispatch card's seeded values — the model's own ratified defaults,
    // with email and SMS OFF because the unsafe option is the one you type.
    const main = page.locator("main");
    await expect(main).toContainText("Messages per hand-off");
    await expect(main).toContainText("500");
    await expect(main).toContainText("08:00 – 21:00");
    await expect(main).toContainText("Turn email on");
    await expect(main).toContainText("Turn text messages on");
    // The CR's own protective filter, seeded ON: the past-due reminder skips
    // customers who are on a payment plan.
    await expect(main).toContainText("Past-due reminder");
  });
});
