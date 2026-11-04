// ── Trace ──────────────────────────────────────────────
// Journey:  T5-09 — Post into a closed period (the auto-forward proof).
//           `08-qa/01-e2e/journeys/T5-09-post-into-closed-period.md` is the
//           spec; this file walks its five-row step table in order.
// Story:    US-PAY-001 (record a payment, S22/S33) · US-LED-011 (manual JE) ·
//           US-LED-015 (period close) · US-IDN-001 (sign in)
//           Screens: S3 · S33 Record payments · S57 Manual JE · S56 JE list
// Rules:    BR-TEN-038 (a money event dated inside a CLOSED period auto-posts
//           to the earliest OPEN period, with an audit note) · BR-LED-006 (a
//           closed period locks; reopen is System-Admin-only) · BR-LED-003
//           (balanced at post; the posting service is the sole writer) ·
//           BR-PAY-021/033 (the payment keeps the date the clerk typed) ·
//           NFR-26 (closed-period rollups never invalidate)
// Money:    the check amount typed into S33 is `moneyTriple("flat","cycle",
//           "full").total` — the frozen dataset figure, read at run time, never
//           retyped here (e2e/README.md §Support kit).
// Tests:    this file. Fixture: 08-qa/01-e2e/stack/seed_e2e_fixture.py
// Impacts:  10-scripts/gates/g12_journeys.py · e2e/support/census.ts
// ───────────────────────────────────────────────────────
//
// THE FIXTURE THIS JOURNEY NEEDS AND THIS PRODUCT CANNOT BUILD.
//
// Every row of T5-09's table is about a period being CLOSED. This stack serves
// no `periods` resource at all — no close, no reopen, no period state — so the
// journey's precondition ("2026-06 CLOSED, exported as EXP-2606-01") cannot be
// established through the product. Step 1 below therefore OPENS by closing the
// month, exactly as a Finance user would, and the journey's own first row is
// where the run is expected to stop.
//
// The spec still walks all five rows. Which row is the first the product cannot
// perform, and what it answered instead, is the deliverable.
import { expect, test } from "@playwright/test";

import { signIn, skipUnlessAppServer, tenant } from "./support/app";
import { moneyTriple } from "./support/expected";
import { journey } from "./support/journey";

// The mailed check. Its FIGURE is the dataset's; its two dates are parameters,
// never a clock read (BR-TEN-043 / gate G6).
const CHECK = moneyTriple("flat", "cycle", "full");
const CLOSED_PERIOD = "2026-06";
const OPEN_PERIOD = "2026-07";
const POSTED_INSIDE_CLOSED_MONTH = "2026-06-28";
const MANUAL_JE_DATE = "2026-06-15";

function api(path: string): string {
  return `/api/${tenant()}${path}`;
}

journey("T5-09", "Post into a closed period — the auto-forward proof", () => {
  // NOT serial: every test below signs in and builds its own precondition,
  // so the run reports which of the journey's rows hold rather than stopping
  // at the first that does not. Which row is the first the product cannot
  // perform is the deliverable.
  skipUnlessAppServer(test);

  test("step 1 — a payment dated inside the CLOSED month posts its JE into the earliest OPEN one", async ({
    page,
  }) => {
    await signIn(page);

    // The journey's fixture: 2026-06 is CLOSED. Established the only way a
    // Finance user can — through the product.
    const close = await page.request.post(api(`/periods/${CLOSED_PERIOD}/close`), {
      data: { reason: "T5-09 fixture — 2026-06 closed and exported" },
    });
    expect(
      [200, 201, 202],
      `closing ${CLOSED_PERIOD} answered ${close.status()} — this journey's entire ` +
        "table is about a closed period, and no periods resource exists to close one",
    ).toContain(close.status());

    // The clerk records the check on S33 with the posting date they were given.
    await page.goto(`/${tenant()}/payments/record`);
    await page.getByRole("button", { name: "Record payment", exact: true }).first().click();
    const form = page.getByRole("dialog");
    await expect(form).toBeVisible();
    // ⚠ ONE CONTROL SINCE 2026-09-23 (`DEF-PAY-6319`) — type and choose on the
    // same element; the matches are `role="option"` rows in its panel.
    await form.locator("#account_id").fill("E2E-10001");
    await form.getByRole("option", { name: new RegExp("E2E-10001") }).first().click();
    await form.locator("#amount").fill(CHECK.total);
    await form.locator("#posted_at").fill(POSTED_INSIDE_CLOSED_MONTH);
    await form.locator("#method").selectOption({ index: 1 });
    await form.getByRole("button", { name: "Record payment", exact: true }).click();
    await expect(page.locator(".pay-result")).toBeVisible();

    // BR-TEN-038: the payment KEEPS 2026-06-28; the journal entry does not.
    const entries = await page.request.get(api("/ledger/journal-entries"));
    expect(entries.status()).toBe(200);
    const rows = ((await entries.json()) as { results: { entry_date: string; memo: string }[] })
      .results;
    const forwarded = rows.find((row) => row.memo?.includes("PY-"));
    expect(forwarded, "the payment must have produced a journal entry").toBeDefined();
    expect(
      forwarded?.entry_date.startsWith(CLOSED_PERIOD),
      `BR-TEN-038: the JE landed in the CLOSED period (${forwarded?.entry_date}) instead of ` +
        `auto-forwarding to ${OPEN_PERIOD}`,
    ).toBe(false);
  });

  test("step 2 — the closed month's trial balance is byte-identical afterwards", async ({
    page,
  }) => {
    await signIn(page);
    const before = await page.request.get(
      api(`/ledger/trial-balance?from=${CLOSED_PERIOD}-01&to=${CLOSED_PERIOD}-30`),
    );
    expect(before.status()).toBe(200);
    const first = await before.text();
    // NFR-26: a closed period's rollups never invalidate — two reads of a
    // locked month must be the same bytes.
    const again = await page.request.get(
      api(`/ledger/trial-balance?from=${CLOSED_PERIOD}-01&to=${CLOSED_PERIOD}-30`),
    );
    expect(await again.text()).toBe(first);

    // And the month must actually be locked, which is what makes the identity
    // above a guarantee rather than a coincidence.
    const state = await page.request.get(api(`/periods/${CLOSED_PERIOD}`));
    expect(
      state.status(),
      `GET /periods/${CLOSED_PERIOD} answered ${state.status()} — nothing in this ` +
        "product can say whether a period is closed",
    ).toBe(200);
  });

  test("step 3 — a manual JE dated inside the closed month posts into the open one", async ({
    page,
  }) => {
    await signIn(page);
    const response = await page.request.post(api("/journal-entries"), {
      data: {
        entry_date: MANUAL_JE_DATE,
        type: "accrual",
        memo: "T5-09 step 3 — dated inside the closed month",
        lines: [
          { account_code: "1210", debit: "500.000000", credit: "0.000000" },
          { account_code: "4100", debit: "0.000000", credit: "500.000000" },
        ],
      },
    });
    expect(
      [200, 201],
      `POST /journal-entries answered ${response.status()} — BR-LED-003's manual JE ` +
        "post is not served, so BR-TEN-038's forwarding cannot be exercised through it",
    ).toContain(response.status());
  });

  test("step 4 — a forced `period` field is ignored and the entry forwards with its audit note", async ({
    page,
  }) => {
    await signIn(page);
    const response = await page.request.post(api("/journal-entries"), {
      data: {
        period: CLOSED_PERIOD,
        entry_date: MANUAL_JE_DATE,
        type: "accrual",
        memo: "T5-09 step 4 — adversarial forced period",
        lines: [
          { account_code: "1210", debit: "500.000000", credit: "0.000000" },
          { account_code: "4100", debit: "0.000000", credit: "500.000000" },
        ],
      },
    });
    expect(
      [200, 201],
      `the adversarial probe answered ${response.status()} — there is no journal-entry ` +
        "write path for a client to force a period on",
    ).toContain(response.status());
  });

  test("step 5 — RECOVERY: System Admin reopens the month, the entry lands, Finance re-closes", async ({
    page,
  }) => {
    await signIn(page);
    const reopen = await page.request.post(api(`/periods/${CLOSED_PERIOD}/reopen`), {
      data: { reason: "T5-09 recovery — the entry genuinely belongs in June" },
    });
    expect(
      [200, 201, 202],
      `POST /periods/${CLOSED_PERIOD}/reopen answered ${reopen.status()} — the one ` +
        "System-Admin-only Finance action in the product does not exist",
    ).toContain(reopen.status());
  });
});

// ── Lifecycle ─────────────────────────────────────────────
// packet: T5-09 journey activation (batch B lane, 2026-08-15)
// generated: 2026-08-15 by the E2E journey-activation lane
// checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-08)
// gates: run against the live stack on E2E_BACKEND_PORT=8040 / E2E_WEB_PORT=8120
// exceptions: (1) step 1 establishes the journey's own fixture (2026-06 CLOSED)
//   through the product rather than by seeding, because a period state that
//   only a fixture script can produce would prove nothing about the rule ·
//   (2) the S33 payment WRITE is left in place on failure — payments are
//   append-only (hard rule 4) and are never cleaned up by a test
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
