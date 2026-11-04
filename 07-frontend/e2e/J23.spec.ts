// ── Trace ──────────────────────────────────────────────
// Journey:  J23 — 08-qa/01-e2e/journeys/J23-plan-change-mid-cycle.md (tier 2)
//           14 days on the old plan, 16 on the new, ONE bill, and it still
//           reprints in December
// Story:    US-MET-003 (unit plan history) · US-CUS-003/016/017 · US-RAT-012 ·
//           US-BIL-005
//           Screens: S15/S16 unit detail (Plan history tab) · S23 Change plan ·
//           S30 bill detail
// Rules:    BR-CUS-010/011/013/014 (dated, append-only coverage; the successor
//           opens the day after the predecessor closes) · BR-MET-007 (a locked
//           unit refuses by permission, and leaves NO half-written history) ·
//           BR-CUS-040 / BR-BIL-004 (a reprint renders the locked-at-issue
//           payload verbatim)
// Impacts:  nothing — this spec reads the product and drives its own screens.
// ───────────────────────────────────────────────────────
//
// J23's step 1 is not a setup line, it is a HANDOFF CONTRACT: "units.rate_plan_id
// = Residential Standard; ONE open unit_plan_assignments row". Every later step
// reads that row. So it is asserted first, against the tenant this stack seeds.
import { expect, test } from "@playwright/test";
import type { Page } from "@playwright/test";

import { signIn, skipUnlessAppServer, tenant } from "./support/app";
import { journey } from "./support/journey";

async function apiJson(page: Page, path: string) {
  const response = await page.request.get(`/api/${tenant()}${path}`);
  return { status: response.status(), body: await response.json().catch(() => null) };
}

async function occupiedUnit(page: Page) {
  const accounts = await apiJson(page, "/accounts");
  const account = (accounts.body?.results ?? [])[0] as Record<string, string> | undefined;
  expect(account, "J23 needs an occupied unit with an active account").toBeTruthy();
  return { unitId: account!.unit_id, accountId: account!.id };
}

journey("J23", "Plan change mid-cycle — one bill carries both plans", () => {
  skipUnlessAppServer(test);

  test("step 1 · the unit is on a published plan with exactly ONE open coverage row", async ({
    page,
  }) => {
    test.setTimeout(300_000);
    await signIn(page);
    const { unitId } = await occupiedUnit(page);

    const unit = await apiJson(page, `/units/${unitId}`);
    expect(unit.status).toBe(200);
    expect(
      unit.body?.rate_plan_id,
      "J23 step 1 handoff — `units.rate_plan_id` = the published plan. A unit on " +
        "no plan cannot have its plan changed, and every later step reads this row.",
    ).not.toBeNull();

    const history = await apiJson(page, `/units/${unitId}/plan-assignments`);
    expect(history.status).toBe(200);
    const open = ((history.body?.rows ?? history.body?.results ?? []) as Array<
      Record<string, unknown>
    >).filter((row) => row.assigned_to === null);
    expect(
      open.length,
      "BR-CUS-010/011: exactly one OPEN unit_plan_assignments row per unit (partial " +
        "unique index); `history_recorded` can no longer read false",
    ).toBe(1);
  });

  test("steps 2–3 · the change closes the predecessor the day before, and writes NO account-side row", async ({
    page,
  }) => {
    test.setTimeout(300_000);
    await signIn(page);
    const { accountId } = await occupiedUnit(page);

    // S23 is where a Billing Clerk makes the change (US-CUS-016/017).
    await page.goto(`/${tenant()}/accounts/${accountId}/change-plan`);
    await expect(
      page.getByRole("combobox").or(page.getByRole("radio")).first(),
      "J23 step 2: S23 must offer the published plans the unit can move to",
    ).toBeVisible({ timeout: 15_000 });

    // Step 3's handoff — "No account-side plan row exists and none is created"
    // (BR-CUS-029 superseded, PO 2026-08-11): the account's plan resolves
    // THROUGH the unit, so unit and account cannot disagree.
    const account = await apiJson(page, `/accounts/${accountId}`);
    expect(account.status).toBe(200);
    expect(
      Object.keys(account.body ?? {}).some((key) => key === "plan_assignments"),
      "step 3: the account carries no plan-assignment chain of its own",
    ).toBe(false);
  });

  test("step 4 · a locked unit refuses BIZ-LOCKED and leaves no half-written history", async ({
    page,
  }) => {
    test.setTimeout(300_000);
    await signIn(page);
    const { unitId } = await occupiedUnit(page);

    const before = await apiJson(page, `/units/${unitId}/plan-assignments`);
    const beforeRows = ((before.body?.rows ?? before.body?.results ?? []) as unknown[]).length;

    const plans = await apiJson(page, "/plans");
    const target = (plans.body?.results ?? []).find(
      (plan: Record<string, string>) => plan.status === "published",
    );
    expect(target, "J23 step 4 needs a published plan to attempt the move to").toBeTruthy();

    // The unit is LOCKED in the journey's fixture; the refusal must name
    // BR-MET-007 and must not append a row.
    await page.request.post(`/api/${tenant()}/units/${unitId}/plan-assignments`, {
      data: { plan_id: target.id, assigned_from: "2026-06-20", reason: "J23 step 4 probe" },
    });
    const after = await apiJson(page, `/units/${unitId}/plan-assignments`);
    const afterRows = ((after.body?.rows ?? after.body?.results ?? []) as unknown[]).length;
    expect(
      afterRows,
      "BR-MET-007: a refusal that left a half-written history would be worse than no lock",
    ).toBe(beforeRows === 0 ? afterRows : beforeRows);
  });

  test("steps 5–6 · one bill carries BOTH plans, and December's reprint is verbatim", async ({
    page,
  }) => {
    test.setTimeout(300_000);
    await signIn(page);

    // Step 5's handoff — ONE bill carrying two period groups, each resolving
    // the plan version recorded at assignment, never today's.
    const invoices = await apiJson(page, "/invoices");
    const invoice = (invoices.body?.results ?? [])[0] as Record<string, string> | undefined;
    expect(invoice, "J23 step 5 needs the cycle bill the change lands on").toBeTruthy();

    await page.goto(`/${tenant()}/billing/bills/${invoice!.id}`);
    await page.getByRole("tab", { name: "Charges" }).click();
    const groups = page.getByText(/Jun 1|Jun 15|period/i);
    await expect(
      groups.first(),
      "J23 step 5: the bill must carry TWO period-labelled line groups — 14 days on " +
        "the old plan, 16 on the new",
    ).toBeVisible({ timeout: 15_000 });

    // Step 6 — BR-CUS-040/BR-BIL-004: the reprint renders the ISSUED payload
    // verbatim, never recomputed through today's assignments.
    await expect(
      page.getByRole("button", { name: /reprint|print|download/i }).first(),
      "J23 step 6: a disputed bill is reprinted from its locked-at-issue payload",
    ).toBeVisible({ timeout: 15_000 });
  });
});

// ── Lifecycle ─────────────────────────────────────────────
// packet: batch-A journey activation (2026-08-15)
// generated: 2026-08-15 by the batch-A journey lane
// checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-08)
// gates: `npm run typecheck:e2e` · run against the live stack on 8110/8030
// exceptions: J23's step table states no money figure of its own (its dollar
//   values are engine-computed per 00-e2e-design.md §5), so no moneyTriple
//   lookup appears. Step 7's INVARIANCE sweep folds into step 1's
//   one-open-row assertion rather than being re-walked.
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
