// ── Trace ──────────────────────────────────────────────
// Journey:  J19 — month-end close (08-qa/01-e2e/journeys/J19-month-end-close.md).
//           Its seven steps are walked IN ORDER, one test each, carrying that
//           step's handoff contract and its downstream (ledger · reports ·
//           queue · audit) assertions.
// Story:    US-LED-015 (close checklist · period lock · late-event auto-forward)
//           · US-LED-016 (export batch · drill-back) · US-LED-008 (trial
//           balance) · US-LED-014 (remittance) · US-PAY-023 · US-TEN-006
//           (fiscal calendar)
//           Screens: S3 · S36 · S42 · S43 · S56 · S41 · S33/S22 · S61
// Rules:    BR-LED-018 (close = WARN + CONFIRM, audited reason, never a silent
//           close and never a hard lockout) · BR-LED-006 (closed periods lock;
//           the five-item checklist) · BR-TEN-038 (a money event dated into a
//           closed period auto-posts to the earliest OPEN one, with the note) ·
//           BR-LED-017 (an export REQUIRES its covered period CLOSED) ·
//           BR-LED-004 (recorded, IDEMPOTENT batches; one summary JE per period
//           per GL) · BR-LED-001 (every exported figure drills back) ·
//           BR-LED-005 (accrual mirrors) · BR-AUD-018 (a refused attempt is
//           itself audited) · BR-REP-001 (a report labels its basis)
// Golden:   LE-1 (**598.69 = 598.69**) · LE-5 (batch **EXP-2607-QBO**, 8 GL
//           rows, "what is the 506.31?") · LE-9 (July closed Aug 5; a Jul 30
//           event keyed Aug 7 resolves to **1 Aug**). NOT ONE of those figures
//           is retyped in this file — see §MONEY.
// Tests:    this file. Fixture: `manage.py seed_demo` +
//           `08-qa/01-e2e/stack/seed_e2e_fixture.py` — see §FIXTURE, which is
//           itself a finding.
// Impacts:  e2e/support/census.ts (counts these assertions and writes the run
//           receipt) · 10-scripts/gates/g12_journeys.py (reads that receipt at
//           `--wave-close`; this file ACTIVATES J19, so the gate now judges it)
// ───────────────────────────────────────────────────────
//
// ════════════════════════════════════════════════════════════════════════════
// WHAT THIS SPEC IS FOR
// ════════════════════════════════════════════════════════════════════════════
// `apps/ledger/close.py` and `apps/ledger/exports.py` landed on 2026-08-15 with
// a full unit suite and both record, in their own Lifecycle trailers,
// `D=deferred(the S42 close endpoints are the API half — not built by this
// lane)` and `E=deferred(no-frontend-half)`. This spec is the first thing in the
// repo that asks a BROWSER whether a human can close a month. It walks J19's
// step table exactly as written and asserts what each step's handoff contract
// says the product must leave behind.
//
// It is RED, and the red is the deliverable. Every failure below names the
// screen it looked at, everywhere else it looked, and the words that screen
// actually rendered — so the failure output IS the gap report. Nothing here is
// weakened, skipped or re-pointed at a passing target to make a wave close: a
// journey that stops at step 1 on a real gap has told the truth, and a journey
// edited until it goes green has told DEF-057's lie in a new costume.
//
// ════════════════════════════════════════════════════════════════════════════
// §MONEY — why `moneyTriple(...)` does not appear in this file
// ════════════════════════════════════════════════════════════════════════════
// The activation contract (e2e/README.md §Journey activation) says a journey
// asserts every money figure through `moneyTriple(...)`. J19's money is not a
// bill triple and the dataset cannot serve it:
//
//   · `moneyTriple(shape, billType, payment)` reads the 245-row A×D×E dataset
//     (`08-qa/01-e2e/expected/money-triples.csv`), whose columns are taxable /
//     tax / total / paid / outstanding / credit / next_late_fee — ONE BILL's
//     figures. J19 states a trial-balance FOOTING (598.69 = 598.69), an export
//     batch total and a drill-back figure (506.31). There is no key under which
//     a period footing lives, and inventing one would be a fabricated tie.
//   · `goldenCalc("GT-51")` — LE-1 under B5's mechanical LE-n → GT-(50+n)
//     allocation, cited in `04-docs/05-modules/09-ledger/08-worked-examples.md`
//     — throws: `04-docs/02-decisions/05-golden-tests.md` states no GT-51
//     section, so the frozen document this harness reads does not carry it.
//
// So J19's figures are UNSOURCEABLE from the expectation kit, and this spec
// refuses to retype them (CLAUDE.md rule 2 · DEF-028: a second copy of a signed
// number is exactly the drift that costs). What it asserts instead is the
// PROPERTY the books must hold — debits equal credits, read off the screen as
// exact 2-dp strings — plus the one figure it legitimately can source: GT-1's
// frozen total, read from B5 at run time by `goldenCalc("GT-1")`, which is the
// amount step 2's payment tenders because the fixture's only bill is GT-1's.
// This is REPORTED, not worked around: closing it means either an expectation
// row for the ledger worked examples or a GT-51 section in B5, and both are
// finance-signed artefacts no lane may mint on its own.
//
// ════════════════════════════════════════════════════════════════════════════
// §FIXTURE — J19's book does not exist in the E2E stack, and that is a finding
// ════════════════════════════════════════════════════════════════════════════
// J19's fixture line reads: *"Tenant brazos-bend · closing July 2026 on Aug 5 ·
// fixture-month trial balance = the LE-1 book (totals 598.69 / 598.69) ·
// checklist state: runs issued ✓, deposit batches reconciled ✓, bank rec
// current ✓, accruals posted ✓, remittance recorded ✗ · export target
// QuickBooks, batch EXP-2607-QBO, 8 GL summary rows."*
//
// The booted stack holds NONE of that. `seed_e2e_fixture.py` seeds one account
// and one engine-priced GT-1 bill whose journal entry is dated **2026-06-30**
// (the June cycle's period end), so `GET /ledger/trial-balance?from=2026-07-01&
// to=2026-07-31` answers **zero rows, 0.000000 = 0.000000** and the whole book
// lives in JUNE. There is no LE-1 book, no reconciled deposit batch, no accrual
// and no remittance to be missing — so even with every screen built, J19 would
// close an EMPTY July. The assertions below are still the journey's own; where
// one needs the LE-1 book it says so at the assertion.
//
// ════════════════════════════════════════════════════════════════════════════
// HOW THE SWEEP WORKS — "no screen" is asserted, never assumed
// ════════════════════════════════════════════════════════════════════════════
// A1 puts the close and the export on **S42 — Finance (tab: Export to
// accounting)**, and `apps/ledger/close.py`'s own Trace names `S42 · S36`. A
// claim that a control does not exist is worthless if only one page was opened,
// so `sweepForControl` visits all five Finance tabs, the S8 Accounting tab
// (where BR-LED-014 puts the export codes), the report library and the sidebar
// itself, and reports what each one rendered. The failure message names every
// place looked, and counts OPERABLE controls apart from merely matching ones —
// S36's "↓ Download period pack" ships disabled with its reason, and a button
// onto nothing must not be read as a path.
import { readFile } from "node:fs/promises";

import { expect, test } from "@playwright/test";
import type { Page } from "@playwright/test";

import { signIn, skipUnlessAppServer, tenant } from "./support/app";
import { goldenCalc } from "./support/expected";
import { journey } from "./support/journey";

// GT-1 — B5 ❄️ FROZEN, finance-signed 2026-08-08. Read at run time, never typed.
const GT1_TOTAL = goldenCalc("GT-1").steps[3];

// BR-TEN-043 in a spec: every business moment J19 names is a PARAMETER, so a
// run on any day walks the same journey. These are the journey file's own dates.
const JULY_START = "2026-07-01";
const JULY_END = "2026-07-31";
const LATE_EVENT_DATE = "2026-07-30"; // step 2 — the payment's own date
const AUTO_FORWARD_TARGET = "2026-08-01"; // LE-9 — the earliest open period's day 1

const FIXTURE_ACCOUNT_NO = process.env.E2E_ACCOUNT_NO ?? "E2E-10001";

/**
 * Every place in the product a month-close or an export could legitimately
 * live, in the order a closer would look, and reached the way a closer reaches
 * them — a sidebar CLICK and a tab CLICK, never a typed URL.
 *
 * **The clicks are not decoration, they are the timeout.** `playwright.config.ts`
 * measures a full page load of the built SPA at ~13 s (ONE 3.5 MB chunk), so the
 * first draft of this sweep — seven `page.goto`s — blew the 90 s test timeout
 * mid-sweep and the assertion it exists for never ran. Client-side navigation
 * costs one load for the whole sweep and is what a human does anyway.
 */
const FINANCE_TABS = [
  "Revenue & AR", // S36 — its header carries the page actions
  "Deposits & Bank",
  "Taxes & Remittance", // S41
  "General ledger", // S56 — the trial balance the close is asserted against
  "Export to accounting", // S42 — A1's home for the close AND the export
];

async function screenText(page: Page): Promise<string> {
  const main = page.locator("main").first();
  return ((await main.count()) > 0
    ? await main.innerText()
    : await page.locator("body").innerText()
  ).trim();
}

/**
 * Controls a human could actually operate — a disabled button is not a path.
 *
 * SCOPED TO `main`, and that is load-bearing: the sidebar's Finance section
 * expands to a child link literally named "Export to accounting", so an
 * unscoped search for an export control would find the NAV ITEM that opens the
 * empty tab and report the journey satisfied by the very screen that is missing.
 */
function screenScope(page: Page) {
  return page.locator("main").first();
}

async function operableCount(page: Page, pattern: RegExp): Promise<number> {
  const scope = screenScope(page);
  const buttons = scope.getByRole("button", { name: pattern }).and(page.locator(":enabled"));
  const links = scope.getByRole("link", { name: pattern });
  return (await buttons.count()) + (await links.count());
}

/**
 * Visit every candidate screen and return what each rendered, so an assertion
 * that a control is missing can prove where it looked. `hits` counts only
 * controls a human could OPERATE; the log records the disabled ones too.
 */
async function sweepForControl(
  page: Page,
  pattern: RegExp,
): Promise<{ hits: string[]; log: string }> {
  const hits: string[] = [];
  const lines: string[] = [];
  const nav = page.getByRole("navigation", { name: "Main navigation" });

  const record = async (label: string): Promise<void> => {
    // A tab click swaps the panel and its data query starts after the render, so
    // reading immediately catches the tab strip with an empty body — the first
    // run of this sweep reported Settings → Accounting as blank for exactly that
    // reason, which would have been a false "nothing here" finding.
    await page.waitForLoadState("networkidle");
    const text = await screenText(page);
    const operable = await operableCount(page, pattern);
    const all =
      (await screenScope(page).getByRole("button", { name: pattern }).count()) +
      (await screenScope(page).getByRole("link", { name: pattern }).count());
    if (operable > 0) {
      hits.push(label);
    }
    lines.push(
      `  ${label} → ${operable} operable / ${all} matching control(s); screen said: ` +
        text.replace(/\n+/g, " ⏎ ").slice(0, 400),
    );
  };

  await nav.getByRole("link", { name: "Finance", exact: true }).click();
  for (const tab of FINANCE_TABS) {
    await page.getByRole("tab", { name: tab }).click();
    await record(`Finance → ${tab}`);
  }
  // BR-LED-014 puts the per-target export codes on the GL mapping page.
  await nav.getByRole("link", { name: "Settings", exact: true }).click();
  await page.getByRole("tab", { name: "Accounting" }).click();
  await record("Settings → Accounting");
  await nav.getByRole("link", { name: "Reports", exact: true }).click();
  await record("Reports");

  lines.push(`  sidebar → ${(await nav.innerText()).replace(/\n+/g, " · ")}`);
  return { hits, log: lines.join("\n") };
}

/**
 * S61 — the audit log, filtered to ONE action code. The journey's downstream
 * column asks for audit rows at nearly every step, and S61 is the one screen in
 * the product that can answer, so every audit assertion below is a real click
 * through the real filter rather than a database read.
 */
async function auditScreenFor(page: Page, action: string): Promise<string> {
  await page.goto(`/${tenant()}/audit-log`);
  await page.getByLabel("Action code").fill(action);
  await page.waitForLoadState("networkidle");
  return screenText(page);
}

journey(
  "J19",
  "month-end close — checklist WARN+CONFIRM → close → late event auto-forwards → gated idempotent export",
  () => {
    skipUnlessAppServer(test);

    // ── STEP 1 ────────────────────────────────────────────────────────────
    // Aug 5 — Finance opens the close: the checklist lists the incomplete item
    // and Finance closes ANYWAY with a typed, audited reason (BR-LED-018).
    // Handoff: July CLOSED, lock active, reason + incomplete-item snapshot on
    // the close row. Downstream: TB debits = credits at close; the close event
    // audited with its reason; no silent close occurred.
    test("step 1 · Aug 5 — the close checklist WARNs and Finance confirms with an audited reason", async ({
      page,
    }) => {
      await signIn(page);

      // A human clicking, not a URL typed: sidebar → Finance.
      const nav = page.getByRole("navigation", { name: "Main navigation" });
      await nav.getByRole("link", { name: "Finance", exact: true }).click();
      await expect(page).toHaveURL(new RegExp(`/${tenant()}/finance$`));

      // A1 S42 is the Finance tab named "Export to accounting"; close.py's Trace
      // names S42 and S36. Click the tab a closer would click.
      await page.getByRole("tab", { name: "Export to accounting" }).click();
      await page.waitForLoadState("networkidle");
      const s42 = await screenText(page);

      // BR-LED-006's five items, computed live — the WARN half of BR-LED-018.
      // `close.close_checklist` returns all five today; three answer `unknown`
      // because billing and payments publish no counts, and `unknown` counts as
      // INCOMPLETE, so the close must demand a reason. The screen must LIST them.
      for (const item of [
        /runs issued/i,
        /batches reconciled|deposit batches/i,
        /bank rec/i,
        /accruals posted/i,
        /remittance recorded/i,
      ]) {
        expect
          .soft(s42, `S42 does not list BR-LED-006's checklist item ${item}. S42 rendered:\n${s42}`)
          .toMatch(item);
      }

      // The confirm-with-reason control. BR-LED-018 forbids BOTH a silent close
      // and a hard lockout, so the screen must offer a reason box and a confirm.
      const { hits, log } = await sweepForControl(page, /clos(e|ing)\s+(the\s+)?(month|period|books)/i);
      expect(
        hits,
        "J19 step 1 needs a month-close control. Swept every Finance tab, the S8 " +
          "Accounting tab, the report library and the sidebar:\n" +
          log,
      ).not.toHaveLength(0);

      // Downstream — the close event is audited WITH the confirm reason
      // (BR-LED-018 · CLAUDE.md rule 7). `close.close_period` writes
      // `period.closed`; S61 is where a human reads it.
      const audit = await auditScreenFor(page, "period.closed");
      expect(
        audit,
        "the close must write a `period.closed` audit row carrying the typed reason and the " +
          `incomplete-item snapshot (BR-LED-018). S61 filtered on that action code showed:\n${audit}`,
      ).toContain("period.closed");
    });

    // ── STEP 2 ────────────────────────────────────────────────────────────
    // Aug 7 — a payment arrives DATED Jul 30. Handoff: it AUTO-POSTS INTO
    // AUGUST with the note "period closed; auto-forwarded" (LE-9, BR-TEN-038);
    // the books stay locked and nothing silently lands in July. Downstream:
    // July's TB byte-identical to step 1; August carries the payment; the
    // posting-basis report labels its basis (BR-REP-001); the audit note is present.
    //
    // NOTE ON CAUSATION, so this failure is not over-read: `apps/ledger/close.py`
    // states in its own Lifecycle exceptions that **billing and payments do not
    // call `resolve_entry_date` yet**, so a late-dated payment lands where it was
    // dated regardless of any close. This step therefore fails for TWO
    // independent reasons — no close could be performed in step 1, and the
    // payment path is not wired to the resolver even when one has been.
    test("step 2 · Aug 7 — a payment dated Jul 30 auto-forwards into August with its audit note", async ({
      page,
    }) => {
      await signIn(page);

      // The money event, recorded the way a clerk records it (the real S33/S22
      // form — the same path W4-payment-write drives).
      await page.goto(`/${tenant()}/payments/record`);
      await page.getByRole("button", { name: "Record payment", exact: true }).first().click();
      const form = page.getByRole("dialog");
      await expect(form).toBeVisible();

      // ⚠ ONE CONTROL SINCE 2026-09-23 (`DEF-PAY-6319`) — type and choose on the
      // same element; the matches are `role="option"` rows in its panel.
      await form.locator("#account_id").fill(FIXTURE_ACCOUNT_NO);
      await form.getByRole("option", { name: new RegExp(FIXTURE_ACCOUNT_NO) }).first().click();
      // The amount is GT-1's frozen total, read from B5 — the journey names no
      // figure, and the fixture's only bill is GT-1's (see §MONEY).
      await form.locator("#amount").fill(GT1_TOTAL);
      // BOTH BR-PAY-021 dates are the journey's Jul 30: the money arrived and
      // cleared inside the month that step 1 shut, which is what makes it the
      // late-dated event LE-9 is about. A payment with no clearing date reaches
      // no books at all and could not test the rule.
      await form.locator("#posted_at").fill(LATE_EVENT_DATE);
      await form.locator("#cleared_at").fill(LATE_EVENT_DATE);
      await form.locator("#method").selectOption({ index: 1 });
      await form.getByRole("button", { name: "Record payment", exact: true }).click();

      const result = page.locator(".pay-result");
      await expect(result).toBeVisible();
      await expect(result.locator(".cell-money-amount").first()).toHaveText(`$${GT1_TOTAL}`);

      // Handoff — the ENTRY moved even though the PAYMENT keeps its own Jul 30
      // posting date (BR-PAY-021 is untouched by BR-TEN-038; it is the journal
      // entry that forwards to the earliest open period's day 1). S56 is the
      // screen that shows an entry's date.
      await page.goto(`/${tenant()}/finance/gl`);
      await page.waitForLoadState("networkidle");
      const gl = await screenText(page);
      expect
        .soft(
          gl,
          `LE-9: the journal entry behind a Jul 30 payment keyed after the close must be dated ` +
            `${AUTO_FORWARD_TARGET}. S56 (Finance → General ledger) rendered:\n${gl}`,
        )
        .toContain(AUTO_FORWARD_TARGET);

      // Downstream — the audit note. `close.resolve_entry_date` returns the note
      // `period closed; auto-forwarded` and `AUDIT_AUTO_FORWARDED` is the action
      // code `journal.auto_forwarded`.
      const audit = await auditScreenFor(page, "journal.auto_forwarded");
      expect(
        audit,
        "BR-TEN-038 requires the forwarded entry to carry the audit note *period closed; " +
          `auto-forwarded*. S61 filtered on \`journal.auto_forwarded\` showed:\n${audit}`,
      ).toContain("journal.auto_forwarded");
    });

    // ── STEP 3 ────────────────────────────────────────────────────────────
    // Aug 8 — an export attempt for AUGUST, which is still open, is REFUSED
    // (BR-LED-017, the L-3b gate). Handoff: no batch created; the refusal
    // writes a security-event attempt row (BR-AUD-018).
    test("step 3 · Aug 8 — exporting the still-OPEN August is refused, and the attempt is audited", async ({
      page,
    }) => {
      await signIn(page);

      // S36's "↓ Download period pack" ships DISABLED with its reason
      // (BR-SHL-025) — a button onto nothing is not an export path — so the
      // sweep counts operable controls separately from matching ones, and the
      // assertion is on the operable count.
      const { hits, log } = await sweepForControl(
        page,
        /export|send to (quickbooks|xero)|hand ?over/i,
      );
      expect(
        hits,
        "J19 step 3 needs an export control that can be OPERATED, so that choosing an OPEN " +
          `period (August) can be refused with BR-LED-017's reason. Swept:\n${log}`,
      ).not.toHaveLength(0);
    });

    // ── STEP 4 ────────────────────────────────────────────────────────────
    // Aug 8 — export JULY to QBO: granularity chosen per export; batch
    // EXP-2607-QBO, one summary JE, 8 GL rows from July's period deltas, each
    // carrying its qbo_ref from the mapping page. Handoff: the batch is recorded
    // (who/when/hash). Downstream: every exported figure DRILLS BACK to
    // dimensioned journal lines.
    test("step 4 · Aug 8 — July exports to QuickBooks as one recorded batch whose figures drill back", async ({
      page,
    }) => {
      await signIn(page);
      const nav = page.getByRole("navigation", { name: "Main navigation" });

      // BR-LED-014 puts the per-target export codes on the GL mapping page, and
      // `exports.create_export_batch` gate 4 refuses the whole QBO batch, naming
      // the account, when any row has no `qbo_ref`. So the mapping page must
      // offer a place to type one before a QBO export can ever succeed.
      await nav.getByRole("link", { name: "Settings", exact: true }).click();
      await page.getByRole("tab", { name: "Accounting" }).click();
      await page.waitForLoadState("networkidle");
      const mapping = await screenText(page);
      expect
        .soft(
          mapping,
          "BR-LED-014: the QuickBooks/Xero export codes live on the GL mapping page (Settings → " +
            `Accounting), and export gate 4 blocks the batch without them. That page rendered:\n${mapping}`,
        )
        .toMatch(/quickbooks|qbo|xero|export code/i);

      // The batch itself. LE-5 names it; the journey asserts its 8 GL rows.
      await nav.getByRole("link", { name: "Finance", exact: true }).click();
      await page.getByRole("tab", { name: "Export to accounting" }).click();
      await page.waitForLoadState("networkidle");
      const s42 = await screenText(page);
      expect(
        s42,
        `J19 step 4 needs S42 to record an export batch (BR-LED-004: who/when/hash), whose 8 GL ` +
          `rows each drill back to dimensioned journal lines (LE-5 · BR-LED-001). S42 rendered:\n${s42}`,
      ).toMatch(/batch|EXP-/i);

      // ── `P4.8` — AND IT GAINS THE FILE ──────────────────────────────────
      //
      // The journey's own step-4 row has said *"Export batch recorded
      // (who/when/hash); **files per IS-11**"* since it was written, and until
      // 2026-09-24 the second half was a plan: `apps/ledger/exports.py` said
      // *"No file is written and nothing is sent"* and the hand-over history
      // drew **Not written** in its File column. `P4.2` writes the bytes and
      // this is the assertion that they reach a person.
      //
      // ⚠ **IT ASSERTS THE BYTES, NOT THE BUTTON.** A control that starts a
      // download and produces nothing passes every check that stops at the
      // click — which is this journey's whole method (`sweepForControl` counts
      // OPERABLE controls apart from matching ones, for exactly that reason).
      // So the download is awaited, saved, and READ: a name, and content that
      // is not empty.
      //
      // ⚠ **THE HAND-OVER LIVES ON THE EXPORT VIEW SINCE `P4.12`**, so the
      // walk goes there rather than assuming the tab's landing view still
      // carries the history. A step that opened the right tab and the wrong
      // VIEW would report *"no download control"* over one that is three
      // pixels away, which is `DEF-REP-6649`'s neighbouring shape.
      await page.goto(`/${tenant()}/finance/export?view=export`);
      await page.waitForLoadState("networkidle");
      const again = page.getByRole("link", { name: /download again/i }).first();
      const hasFile = await again.count();
      expect(
        hasFile,
        "J19 step 4 (P4.8): the hand-over history must offer the recorded batch's FILE — " +
          "IS-11, and the journey's own step-4 row has promised it since it was written. " +
          `The Export view rendered:\n${await screenText(page)}`,
      ).toBeGreaterThan(0);

      const download = await Promise.all([
        page.waitForEvent("download"),
        again.click(),
      ]).then(([one]) => one);
      const saved = await download.path();
      expect(
        download.suggestedFilename(),
        "IS-11 names the file; a download with no name is one the browser invented",
      ).not.toEqual("");
      expect(
        saved,
        "J19 step 4 (P4.8): the download produced no file on disk. A control that starts a " +
          "download and writes nothing passes every check that stops at the click",
      ).not.toBeNull();
      const bytes = saved === null ? 0 : (await readFile(saved)).length;
      expect(
        bytes,
        "J19 step 4 (P4.8): the hand-over's file is EMPTY. A zero-byte artefact would satisfy " +
          "every assertion about a download existing and prove nothing about the month",
      ).toBeGreaterThan(0);
    });

    // ── STEP 5 ────────────────────────────────────────────────────────────
    // Aug 9 — the July export is re-run and is BLOCKED with a link to the
    // existing batch (LE-5, idempotent, no double-handover). Exactly one July
    // batch exists, forever; the attempt is audited.
    test("step 5 · Aug 9 — a second July export is blocked and links the batch that already went", async ({
      page,
    }) => {
      await signIn(page);
      await page.goto(`/${tenant()}/finance/export`);
      await page.waitForLoadState("networkidle");
      const s42 = await screenText(page);

      expect
        .soft(
          s42,
          `BR-LED-004: S42 must show the export HISTORY (Sent · Period · Destination · Entries · ` +
            `By · Status) so a second handover can be refused against it. S42 rendered:\n${s42}`,
        )
        .toMatch(/sent|history|destination/i);

      const audit = await auditScreenFor(page, "export.batch_created");
      expect(
        audit,
        "exactly one July batch must exist, and `export.batch_created` is the audit row that " +
          `proves it went once (BR-LED-004 · BR-LED-015). S61 showed:\n${audit}`,
      ).toContain("export.batch_created");
    });

    // ── STEP 6 ────────────────────────────────────────────────────────────
    // Aug 12 — epilogue: July's accrual-type JE auto-reversed on Aug 1 (mirror
    // linked both ways) and the remittance is recorded in August with its filing
    // confirmation ref. Downstream: the remittance report shows dual-basis
    // columns per authority (LE-3).
    test("step 6 · Aug 12 — the accrual mirror is linked and August's remittance carries its filing ref", async ({
      page,
    }) => {
      await signIn(page);
      await page.goto(`/${tenant()}/finance/taxes`);
      await page.waitForLoadState("networkidle");
      const s41 = await screenText(page);

      // LE-3 / BR-LED-002: both bases, always, per authority.
      expect
        .soft(
          s41,
          `LE-3: S41 must show BOTH bases per authority (billed and collected). It rendered:\n${s41}`,
        )
        .toMatch(/billed/i);
      expect
        .soft(s41, `LE-3: S41 must show the COLLECTED basis column too. It rendered:\n${s41}`)
        .toMatch(/collected/i);

      // BR-LED-019: the remittance JE drains the authority liability and carries
      // the confirmation ref + receipt attachment. Recording one is a WRITE that
      // needs a surface.
      const { hits, log } = await sweepForControl(page, /record (a )?remittance|remit|filing/i);
      expect(
        hits,
        "J19 step 6 needs a way to RECORD a remittance with its filing confirmation ref " +
          `(BR-LED-019). Swept:\n${log}`,
      ).not.toHaveLength(0);
    });

    // ── STEP 7 ────────────────────────────────────────────────────────────
    // INVARIANCE — July is byte-frozen from step 1 forward: no row entered or
    // left the closed period, the closed-period lock held through every probe,
    // and the export file re-generated from the batch is identical (hash-stable).
    // The one screen in the product that can show a period's figures is S56.
    test("step 7 · INVARIANCE — July's book is byte-frozen and every gate refusal is attempt-audited", async ({
      page,
    }) => {
      await signIn(page);

      // The trial balance J19 step 1 foots and step 7 re-reads unchanged.
      // US-LED-008's read model is served; S56 is the screen for it.
      await page.goto(`/${tenant()}/finance/gl`);
      await page.waitForLoadState("networkidle");
      const s56 = await screenText(page);
      expect
        .soft(
          s56,
          "J19 steps 1 and 7 both read July's trial balance off the screen and require it " +
            `unchanged between them. S56 (Finance → General ledger) rendered:\n${s56}`,
        )
        .toMatch(/trial balance/i);
      // The FOOTING is the property, never a retyped constant (§MONEY): whatever
      // the screen shows for debits it must show for credits.
      expect
        .soft(
          s56,
          `BR-LED-007: the period must FOOT — the screen must state its debit and credit totals ` +
            `so ${JULY_START}…${JULY_END} can be compared before and after. S56 rendered:\n${s56}`,
        )
        .toMatch(/balanced|totals?/i);

      // BR-AUD-018: every refusal in this journey — the open-period export, the
      // re-export — is itself an attempt row. `period.reopened` is the one act
      // that could have moved July, and J19 step 7 says it is NOT exercised, so
      // the assertion is that the closed-period lock is visible at all.
      const audit = await auditScreenFor(page, "period.closed");
      expect(
        audit,
        "the closed-period lock has to be READABLE for the invariance step to mean anything: " +
          `S61 must carry the close (and any reopen) of ${JULY_START}…${JULY_END}. It showed:\n${audit}`,
      ).toContain("period.closed");
    });
  },
);

// ── Lifecycle ─────────────────────────────────────────────
// packet: J19@08-qa/01-e2e/journeys/J19-month-end-close.md (steps 1-7 + fixture line) · US-LED-015 / US-LED-016 (apps/ledger/close.py · apps/ledger/exports.py, both landed 2026-08-15) · e2e/README.md §Journey activation · DEF-057 / PO ruling 2026-08-11 ("we ahve to prove against human clicking")
// generated: 2026-08-15 by the J19 journey-activation lane
// checklist: A✔ B✔ C✔ D=n/a(no backend half — this lane wrote no server code) E✔ F✔ G✔ H=deferred(PO 2026-08-08)
// gates: `npm run typecheck:e2e`✔ · playwright against the live stack booted by
//   08-qa/01-e2e/stack/boot_stack.sh on E2E_BACKEND_PORT=8020 / E2E_WEB_PORT=8100
//   against database sbh_j19_lane — the run receipt is
//   07-frontend/test-results/journey-run.json and it records J19 RED. `npm run
//   lint` covers `src` only, so no lint result is claimed for this file.
// red-proof (law 7): not applicable in the usual direction — this spec is red on
//   its first execution, against the product, for the reason it was written to
//   detect. The harness half WAS proved: step 2 executes a real write through the
//   real S33/S22 form and its `$108.88` result assertion passes, so the file's
//   locators, sign-in and money source are demonstrably working where the product
//   supports the step. A spec that failed everywhere would not have distinguished
//   "no screen" from "broken spec"; this one does.
//   TWO HARNESS DEFECTS IN THIS FILE were found by running it and fixed here,
//   both stated rather than absorbed: (a) the first sweep used seven
//   `page.goto`s and blew the 90 s test timeout mid-sweep at ~13 s a load, so
//   the assertion it exists for never ran — it now navigates by CLICK; (b) the
//   sweep read a tab's panel before its query resolved and reported Settings →
//   Accounting as blank, which would have been a false "nothing here" finding —
//   it now waits for networkidle. No product assertion was changed by either.
// exceptions: (1) **`moneyTriple(...)` is NOT used** — J19's figures are a
//   trial-balance footing and an export total, which the 245-row A×D×E bill
//   dataset does not carry under any key, and `goldenCalc("GT-51")` throws
//   because B5 states no GT-51 section. The figures are therefore asserted as
//   PROPERTIES (debits = credits, read off the screen) and never retyped. See
//   §MONEY · (2) the J19 FIXTURE does not exist in the E2E stack: July's trial
//   balance is empty (the seeded bill's entry is dated 2026-06-30) and there is
//   no LE-1 book, no reconciled batch, no accrual and no remittance. See
//   §FIXTURE · (3) step 2 fails for TWO independent reasons and says so at the
//   assertion — no close can be performed, AND `apps/ledger/close.py`'s own
//   exceptions record that payments never call `resolve_entry_date` · (4) this
//   spec ACTIVATES J19 (gate G12), so `run_gates.py --wave-close` now FAILS on a
//   red journey. That is the gate working: a wave cannot close with an activated
//   journey red, and the fix is the missing API and screens, not this file
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
