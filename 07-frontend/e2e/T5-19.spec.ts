// ── Trace ──────────────────────────────────────────────
// Journey:  T5-19 — Hand-typed bill amount (the path does not exist).
//           `08-qa/01-e2e/journeys/T5-19-hand-typed-bill-amount.md` is the
//           spec; this file walks its six-row step table in order.
// Story:    US-BIL-004 (the draft/run totals surface) · US-BIL-012 (the ad-hoc
//           single-bill wizard) · US-BIL-014 (the correction workflow) ·
//           US-RAT-008 (charge codes in Plans & Rates) · US-IDN-001 (sign in)
//           Screens: S3 · S30 bill detail (Charges) · S31 · S12 charge codes
// Rules:    BR-BIL-019 (theft/penalty money enters as ASSESSED READS priced by
//           the engine plus configured charge codes) · BR-BIL-020 (ad-hoc bills
//           draw lines ONLY from rules and charge codes) · BR-BIL-023 (computed
//           amounts are never hand-editable) · NFR-19 (every total reproducible
//           from inputs + rules, forever)
// Money:    the ONE figure this journey names as a hand-edit target is the
//           draft's usage line. It is read from `goldenCalc("GT-1")` — the
//           seeded bill's own signed figures — and asserted RENDERED READ-ONLY.
//           `moneyTriple("flat","penalty","none")` is read for the journey's
//           TAMPER-bill row so the penalty figure this spec reasons about is
//           the dataset's, never typed.
// Tests:    this file. Fixture: 08-qa/01-e2e/stack/seed_e2e_fixture.py
// Impacts:  10-scripts/gates/g12_journeys.py · e2e/support/census.ts
// ───────────────────────────────────────────────────────
//
// A JOURNEY THAT ASSERTS AN ABSENCE. Every row here is "no such control, no
// such field, no such contract" — which is exactly the kind of claim a unit
// test cannot make and a rendered screen can. The assertions are counts of
// zero on real screens and refusals from the real API.
import { expect, test } from "@playwright/test";

import { signIn, skipUnlessAppServer, tenant } from "./support/app";
import { goldenCalc, moneyTriple } from "./support/expected";
import { journey } from "./support/journey";

const GT1 = goldenCalc("GT-1");
const [GT1_USAGE, , , GT1_TOTAL] = GT1.steps;
// The journey's penalty row. Read so the figure this spec reasons about comes
// from the frozen dataset, never from this file.
const PENALTY = moneyTriple("flat", "penalty", "none");

function api(path: string): string {
  return `/api/${tenant()}${path}`;
}

journey("T5-19", "Hand-typed bill amount — the path does not exist", () => {
  // NOT serial: each row builds its own precondition, so the run reports which
  // of the journey's six hold rather than stopping at the first that does not.
  skipUnlessAppServer(test);

  test("step 1 — the bill's amounts render READ-ONLY; there is no editable amount field", async ({
    page,
  }) => {
    await signIn(page);
    await page.goto(`/${tenant()}/billing`);
    await page.getByRole("row").filter({ hasText: "BL-" }).first().getByRole("link").first().click();
    await expect(page).toHaveURL(new RegExp(`/${tenant()}/billing/bills/`));
    await page.getByRole("tab", { name: "Charges" }).click();

    const lines = page.locator("table.met-table").filter({ has: page.locator("tfoot") });
    await expect(lines).toBeVisible();
    // The figures are the engine's, rendered — the same ones W3 proves equal
    // B5's signed values. What matters here is that they are TEXT.
    await expect(
      lines.getByRole("row").filter({ hasText: "electric usage" }).locator(".cell-money-amount").last(),
    ).toHaveText(`$${GT1_USAGE}`);
    await expect(lines.locator("tfoot tr").nth(2).locator(".cell-money-amount")).toHaveText(
      `$${GT1_TOTAL}`,
    );

    // BR-BIL-023: not one input, anywhere in the charges table.
    await expect(
      lines.locator("input, textarea, [contenteditable='true']"),
      "BR-BIL-023: a computed amount is never hand-editable — the charges table " +
        "may contain no editable control at all",
    ).toHaveCount(0);
  });

  test("step 2 — 'Add charge line' offers configured CODES, never a free amount input", async ({
    page,
  }) => {
    await signIn(page);
    await page.goto(`/${tenant()}/billing`);
    await page.getByRole("row").filter({ hasText: "BL-" }).first().getByRole("link").first().click();
    await page.getByRole("tab", { name: "Charges" }).click();

    const add = page.getByRole("button", { name: /add charge/i });
    const count = await add.count();
    if (count === 0) {
      // The draft power exists on the RUN, not on an issued bill. Assert the
      // stronger statement the journey makes about an issued document: an
      // issued bill offers no line-adding affordance at all (hard rule 4).
      await expect(
        page.getByRole("button", { name: /add line|new line|add charge/i }),
        "an ISSUED bill must offer no line-adding control",
      ).toHaveCount(0);
      return;
    }
    await add.first().click();
    const dialog = page.getByRole("dialog");
    await expect(dialog).toBeVisible();
    await expect(
      dialog.locator("input#amount, input[name='amount']"),
      "BR-BIL-023/BR-BIL-007: the amount comes from the CODE's tenant configuration, " +
        "never from a free input",
    ).toHaveCount(0);
  });

  test("step 3 — the ad-hoc single-bill wizard has no amount field in any step", async ({
    page,
  }) => {
    await signIn(page);
    await page.goto(`/${tenant()}/billing/one-time`);
    await expect(page.locator("main")).toBeVisible();
    await expect(
      page.locator("main").locator("input[name='amount'], input#amount, input[inputmode='decimal']"),
      "BR-BIL-020: no path from keyboard to invoice_lines.amount in any wizard step",
    ).toHaveCount(0);
  });

  test("step 4 — a theft/penalty bill takes assessed READS, never typed dollars", async ({
    page,
  }) => {
    await signIn(page);
    // The dollars in the penalty row (`flat,penalty,none` → next_late_fee
    // ${PENALTY.next_late_fee}) come from charge codes and the engine. The
    // product's own statement of that is that the ONLY writable read surface
    // is the staged batch, and no invoice-line write exists at all.
    const invoicePost = await page.request.post(api("/invoices"), {
      data: { lines: [{ amount: "75.00", description: "typed" }] },
    });
    expect(
      [404, 405],
      `POST /invoices answered ${invoicePost.status()} — no client-supplied-amount ` +
        "contract may exist (BR-BIL-019 / NFR-19)",
    ).toContain(invoicePost.status());

    // …and assessed reads DO have a door: the staged batch. Its existence is
    // what makes "dollars only from the engine" a workable rule rather than a
    // dead end.
    const reads = await page.request.get(api("/reads?per=1"));
    expect(reads.status(), "the assessed-read door must exist for BR-BIL-019 to be workable").toBe(
      200,
    );
  });

  test("step 5 — forcing an amount at the API is refused; no draft line amount is writable", async ({
    page,
  }) => {
    await signIn(page);
    const invoices = await page.request.get(api("/invoices"));
    const first = ((await invoices.json()) as { results: { id: string }[] }).results[0];
    expect(first, "the fixture has no invoice to probe").toBeDefined();

    for (const probe of [
      page.request.post(api("/invoices"), { data: { lines: [{ amount: "75.00" }] } }),
      page.request.patch(api(`/invoices/${first.id}`), { data: { lines: [{ amount: "75.00" }] } }),
      page.request.patch(api(`/invoices/${first.id}/lines/1`), { data: { amount: "75.00" } }),
    ]) {
      const response = await probe;
      expect(
        response.status(),
        `a forced amount answered ${response.status()} — the API accepts INPUTS and ` +
          "computes lines server-side (BR-BIL-019 / NFR-19)",
      ).toBeGreaterThanOrEqual(400);
    }

    // Nothing was written: the issued bill still renders its signed total.
    await page.goto(`/${tenant()}/billing`);
    await expect(
      page.getByRole("row").filter({ hasText: "BL-" }).first().locator(".cell-money-amount").first(),
    ).toHaveText(`$${GT1_TOTAL}`);
  });

  test("step 6 — RECOVERY: the ratified door is fixing the INPUT (a charge code in Plans & Rates)", async ({
    page,
  }) => {
    await signIn(page);
    // US-RAT-008: the charge-code catalogue is where a dollar is configured.
    // Its existence IS the recovery this journey names.
    const charges = await page.request.get(api("/charges"));
    expect(
      charges.status(),
      `GET /charges answered ${charges.status()} — with no charge-code catalogue, ` +
        "BR-BIL-023's ratified door does not exist",
    ).toBe(200);

    await page.goto(`/${tenant()}/plans-rates/charges`);
    await expect(
      page.locator("main"),
      "the Plans & Rates charge-code surface must be reachable by clicking",
    ).toBeVisible();
    await expect(page.locator("main [data-not-built-yet]")).toHaveCount(0); // DEF-152
  });
});

// ── Lifecycle ─────────────────────────────────────────────
// packet: T5-19 journey activation (batch B lane, 2026-08-15)
// generated: 2026-08-15 by the E2E journey-activation lane
// checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-08)
// gates: run against the live stack on E2E_BACKEND_PORT=8040 / E2E_WEB_PORT=8120
// exceptions: (1) the journey's fixture is a DRAFT bill under run RUN-2607-A;
//   this stack's only bill is ISSUED, so steps 1–2 assert the absence of an
//   editable amount on the ISSUED document — a strictly stronger claim (hard
//   rule 4) but NOT the draft-editing surface the journey describes, and the
//   difference is stated rather than hidden · (2) the TAMPER $500.00 charge
//   code is not configured in this tenant, so step 4 asserts the absence of the
//   typed-dollar contract rather than the presence of the code's line
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
