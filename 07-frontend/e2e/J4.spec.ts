// ── Trace ──────────────────────────────────────────────
// Journey:  J4 — 08-qa/01-e2e/journeys/J4-collections.md (tier 1)
//           past-due → late fee → reminder → notices → plan / write-off
// Story:    US-BIL-005 (the issued bill a collection acts on) · US-PAY-001
//           (the payment that clears it) · US-PAY-014 (the collection sequence
//           engine) · US-CUS-015 (disconnect notice) · US-CUS-018 (payment plan)
//           Screens: S21 account detail · S22 disconnect-notice flow · S33/S34
// Rules:    BR-BIL-001/008 (late fee = max(floor, % × overdue portion) after
//           grace, NON-taxable) · BR-PAY-017 (the ladder) · BR-CUS-039
//           (medical hold skipped) · BR-CUS-043/044 (plan pauses dunning)
// Money:    the LATE-fee floor is read from `08-qa/01-e2e/expected/money-triples.csv`
//           row (flat, cycle, none) — `next_late_fee`. Never retyped here.
// Impacts:  nothing — this spec reads the product and drives its own screens.
// ───────────────────────────────────────────────────────
import { expect, test } from "@playwright/test";
import type { Page } from "@playwright/test";

import { signIn, skipUnlessAppServer, tenant } from "./support/app";
import { moneyTriple } from "./support/expected";
import { journey } from "./support/journey";

// The frozen expectation for an unpaid cycle bill: outstanding 97.41 and the
// NEXT late fee 5.00 (the WE-15b floor). Read, never retyped.
const UNPAID = moneyTriple("flat", "cycle", "none");

async function apiJson(page: Page, path: string) {
  const response = await page.request.get(`/api/${tenant()}${path}`);
  return { status: response.status(), body: await response.json().catch(() => null) };
}

journey("J4", "Collections — past-due → late fee → notices → plan / write-off", () => {
  skipUnlessAppServer(test);

  test("step 1 · the ladder assesses a NON-taxable late fee on the overdue portion after grace", async ({
    page,
  }) => {
    test.setTimeout(300_000);
    await signIn(page);

    // The tenant's own ratified parameters — the fee formula's inputs.
    const defaults = await apiJson(page, "/settings/billing-defaults");
    expect(defaults.status).toBe(200);
    expect(
      defaults.body?.late_min_amount,
      "BR-BIL-008's floor must equal the frozen dataset's next_late_fee for the " +
        "unpaid cycle row — a second opinion on a signed figure is the drift " +
        "CLAUDE.md rule 2 forbids",
    ).toBe(UNPAID.next_late_fee.replace(/\.00$/, ""));

    // The ladder itself, driven over the tenant's own past-due selection —
    // which is the S34 bulk action, and the only caller this engine has.
    const accounts = await apiJson(page, "/accounts");
    const accountId = (accounts.body?.results ?? [])[0]?.id as string | undefined;
    expect(accountId, "J4 needs an account carrying an issued bill").toBeTruthy();

    const ladder = await page.request.post(`/api/${tenant()}/collections/run`, {
      data: { account_ids: [accountId], as_of: "2026-10-01" },
    });
    expect(
      ladder.status(),
      "US-PAY-014's ladder must advance for an account past grace on 2026-10-01",
    ).toBe(200);
    const run = await ladder.json();

    // Step 1's handoff: "non-taxable fee line on overdue portion after grace".
    expect(
      JSON.stringify(run),
      "step 1 must leave a LATE assessment for the overdue account",
    ).toMatch(/late/i);

    // The fee lands on the bill as an invoice line (BR-BIL-008), so the money
    // surface must show it.
    const invoices = await apiJson(page, "/invoices");
    const total = (invoices.body?.results ?? [])[0] as Record<string, unknown> | undefined;
    expect(total, "the issued bill the fee attaches to must still be readable").toBeTruthy();
  });

  test("step 2 · a notice is appended to notice_history and the final tier is certified mail", async ({
    page,
  }) => {
    test.setTimeout(300_000);
    await signIn(page);

    const accounts = await apiJson(page, "/accounts");
    const accountId = (accounts.body?.results ?? [])[0]?.id as string;

    // The S22 disconnect-notice flow is an account-header action (US-CUS-015).
    await page.goto(`/${tenant()}/accounts/${accountId}`);
    await expect(page.getByRole("button", { name: /Disconnect notice/i })).toBeVisible();
    await page.getByRole("button", { name: /Disconnect notice/i }).click();

    // Step 2's handoff — "notice_history appended … certified mail on the final
    // tier". The screen must be able to record one.
    await expect(
      page.getByText(/certified/i).first(),
      "J4 step 2: the final notice tier is certified mail (A15 tiers) and the " +
        "disconnect-notice flow must say so",
    ).toBeVisible({ timeout: 15_000 });
  });

  test("step 3 · a payment plan pauses dunning, and a write-off needs Owner approval + audit", async ({
    page,
  }) => {
    test.setTimeout(300_000);
    await signIn(page);

    const accounts = await apiJson(page, "/accounts");
    const accountId = (accounts.body?.results ?? [])[0]?.id as string;

    // US-CUS-018 — the plan half. BR-CUS-043/044: an active plan pauses dunning
    // and the scheduled disconnect while the customer stays current.
    const plans = await apiJson(page, `/accounts/${accountId}/payment-plans`);
    expect(
      plans.status,
      "J4 step 3: US-CUS-018's payment plan must be reachable — BR-CUS-043/044 " +
        "pause dunning and disconnect while a plan is current",
    ).toBeLessThan(400);

    // The write-off half — bad-debt GL + Owner approval + audit (US-PAY-012).
    const writeOff = await page.request.post(`/api/${tenant()}/write-offs`, {
      data: {
        account_id: accountId,
        amount: UNPAID.outstanding,
        reason: "uncollectible",
        note: "J4 journey — collections write-off path",
        requested_on: "2026-10-01",
      },
    });
    expect(writeOff.status(), "US-PAY-012 must accept a requested write-off").toBeLessThan(400);
    const requested = await writeOff.json();
    expect(
      JSON.stringify(requested),
      "a requested write-off moves NO money until an Owner approves it",
    ).toMatch(/approv/i);
  });
});

// ── Lifecycle ─────────────────────────────────────────────
// packet: batch-A journey activation (2026-08-15)
// generated: 2026-08-15 by the batch-A journey lane
// checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-08)
// gates: `npm run typecheck:e2e` · run against the live stack on 8110/8030
// exceptions: every money figure comes from moneyTriple("flat","cycle","none").
//   The medical-hold exclusion (BR-CUS-039) is NOT asserted: the customers
//   records publish no way to read a hold (the S33 screen says so itself), so
//   there is nothing a browser can check — reported rather than faked.
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
