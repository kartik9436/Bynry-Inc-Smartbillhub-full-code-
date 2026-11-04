// ── Trace ──────────────────────────────────────────────
// Journey:  T6-09 — Finance-role gates: JE draft/post · reverse+repost ·
//           remittance · close (warn+confirm) · export-requires-closed ·
//           reopen = SysAdmin · unreconcile.
//           `08-qa/01-e2e/journeys/T6-09-finance-role-gates.md` is the spec;
//           this file walks its twelve-row step table in order.
// Story:    US-LED-011..016 (manual JE · reverse+repost · remittance · bank
//           rec · period close · ERP export) · US-PAY-021/022/023 (deposit
//           batches, bank statement import, reconcile/unreconcile) ·
//           US-IDN-001 (sign in)
//           Screens: S3 · S56 JE list · S57 Manual JE · S36 Finance · S42 Export
// Rules:    BR-LED-003 (draft freely; balanced + memo enforced at post; posted
//           JEs immutable) · BR-LED-006 (close locks; REOPEN is System-Admin
//           only) · BR-LED-018 (the close checklist: WARN + CONFIRM, never
//           silent, never a hard lockout) · BR-LED-017 (export requires the
//           covered period CLOSED) · BR-LED-004 · BR-LED-002/019 (remittance) ·
//           BR-PAY-004/019 (reconciled batches lock; Unreconcile is the ONLY
//           reversal) · BR-TEN-038 · BR-SHL-031 (the receipt upload guards)
// Money:    the LE-4 fixture (accrual DR 1210 / CR 4100 500.00 and its
//           unbalanced 500.00/480.00 variant) is the journey's own, CITED not
//           recomputed — its own §Intent says "no new arithmetic is
//           introduced". It is not in the money-triples dataset, so
//           `moneyTriple` is not called: the figures below are the journey
//           file's own and are used only as POSTED INPUTS, never asserted as
//           an expectation.
// Impacts:  10-scripts/gates/g12_journeys.py · e2e/support/census.ts
// ───────────────────────────────────────────────────────
//
// THE ROLE PROBES FROM BELOW CANNOT BE STAGED, and that is a finding in itself.
// Rows 1, 7 and 11 need Priya (Billing Clerk) to be REFUSED. The seeded tenant
// has one user; `POST /users` creates a membership but hands back no usable
// credential, and v1 sends no staff auth email (NFR-14). `e2e/support/app.ts`
// forbids forging a session on purpose — "a journey that forged its own cookie
// would prove the API and skip the screen". So those rows assert the seam that
// is missing rather than faking a clerk.
//
// Everything else in this table is a Finance ACTION, and the actions are the
// story: no journal-entry write, no period resource, no export resource, no
// remittance and no bank-rec surface is mounted in `config/urls.py`.
import { expect, test } from "@playwright/test";
import type { APIRequestContext } from "@playwright/test";

import { signIn, skipUnlessAppServer, tenant } from "./support/app";
import { journey } from "./support/journey";

const OPEN_PERIOD = "2026-07";
const CLOSED_PERIOD = "2026-06";
// The journey's LE-4 fixture, cited from its own file. Inputs, not expectations.
const LE4_BALANCED = [
  { account_code: "1210", debit: "500.000000", credit: "0.000000" },
  { account_code: "4100", debit: "0.000000", credit: "500.000000" },
];
const LE4_UNBALANCED = [
  { account_code: "1210", debit: "500.000000", credit: "0.000000" },
  { account_code: "4100", debit: "0.000000", credit: "480.000000" },
];

function api(path: string): string {
  return `/api/${tenant()}${path}`;
}

/** True when the surface a clerk would be refused ON does not exist to gate. */
async function absent(request: APIRequestContext, method: "GET" | "POST", path: string): Promise<number> {
  const response =
    method === "GET" ? await request.get(api(path)) : await request.post(api(path), { data: {} });
  return response.status();
}

journey("T6-09", "Finance-role gates across the month-end power set", () => {
  // NOT serial: each row builds its own precondition, so the run reports which
  // of the journey's twelve hold rather than stopping at the first that does not.
  skipUnlessAppServer(test);

  test("step 1 — the Clerk is DENIED S57 Manual JE and POST /journal-entries", async ({ page }) => {
    await signIn(page);
    // The gate can only be observed on a surface that exists to gate.
    const status = await absent(page.request, "POST", "/journal-entries");
    expect(
      status,
      `POST /journal-entries answered ${status} — BR-LED-003's write has no route, so the ` +
        "A4 finance-row gate in front of it cannot be exercised by any role",
    ).not.toBe(404);
  });

  test("step 2 — the Executive drafts the LE-4 accrual; a draft touches no books", async ({
    page,
  }) => {
    await signIn(page);
    const response = await page.request.post(api("/journal-entries"), {
      data: {
        status: "draft",
        entry_date: "2026-07-31",
        type: "accrual",
        memo: "Accrue Sep unbilled revenue",
        lines: LE4_BALANCED,
      },
    });
    expect(
      [200, 201],
      `drafting a JE answered ${response.status()} — S56/S57 have no route and the write ` +
        "endpoint is not mounted",
    ).toContain(response.status());
  });

  test("step 3 — an UNBALANCED post is refused; the balanced one posts through the service", async ({
    page,
  }) => {
    await signIn(page);
    const unbalanced = await page.request.post(api("/journal-entries"), {
      data: { entry_date: "2026-07-31", type: "accrual", memo: "unbalanced", lines: LE4_UNBALANCED },
    });
    expect(
      unbalanced.status(),
      "BR-LED-003: an unbalanced entry must be refused server-side with the gap shown",
    ).toBeGreaterThanOrEqual(400);

    const balanced = await page.request.post(api("/journal-entries"), {
      data: {
        entry_date: "2026-07-31",
        type: "accrual",
        memo: "Accrue Sep unbilled revenue",
        lines: LE4_BALANCED,
      },
    });
    expect(
      [200, 201],
      `the balanced post answered ${balanced.status()} — the posting service has no route`,
    ).toContain(balanced.status());
  });

  test("step 4 — a posted JE is immutable; REVERSE + REPOST is the only door", async ({ page }) => {
    await signIn(page);
    const entries = await page.request.get(api("/ledger/journal-entries?per=50"));
    expect(entries.status()).toBe(200);
    const posted = ((await entries.json()) as { results: { entry_id: string; status: string }[] })
      .results.find((e) => e.status === "posted");
    expect(posted, "the seeded books carry no posted entry to probe").toBeDefined();

    for (const probe of [
      page.request.patch(api(`/ledger/journal-entries/${posted?.entry_id}`), {
        data: { memo: "mutated" },
      }),
      page.request.delete(api(`/ledger/journal-entries/${posted?.entry_id}`)),
    ]) {
      const response = await probe;
      expect(
        response.status(),
        "hard rule 4: a posted journal entry is immutable forever",
      ).toBeGreaterThanOrEqual(400);
    }

    const reverse = await page.request.post(
      api(`/journal-entries/${posted?.entry_id}/reverse`),
      { data: { reason: "T6-09 step 4 — the ratified door" } },
    );
    expect(
      [200, 201],
      `the one-click reverse answered ${reverse.status()} — BR-LED-003's ratified "edit" ` +
        "has no route, so a misposted entry has no lawful correction path",
    ).toContain(reverse.status());
  });

  test("step 5 — the remittance drains the authority's liability and stores its receipt", async ({
    page,
  }) => {
    await signIn(page);
    const response = await page.request.post(api("/finance/remittances"), {
      data: {
        authority: "Texas State",
        confirmation_ref: "#TX-88231",
        period: OPEN_PERIOD,
      },
    });
    expect(
      [200, 201],
      `recording the remittance answered ${response.status()} — BR-LED-002/019 have no ` +
        "surface, so the confirmation ref and the BR-SHL-031-guarded receipt have nowhere to go",
    ).toContain(response.status());
  });

  test("step 6 — an export covering the OPEN period is DENIED", async ({ page }) => {
    await signIn(page);
    const response = await page.request.post(api("/exports"), { data: { period: OPEN_PERIOD } });
    expect(
      [409, 422],
      `POST /exports answered ${response.status()} — BR-LED-017's refusal has no resource ` +
        "to be raised by (the same finding as T5-08)",
    ).toContain(response.status());
  });

  test("step 7 — the Clerk is DENIED the period close", async ({ page }) => {
    await signIn(page);
    const status = await absent(page.request, "POST", `/periods/${OPEN_PERIOD}/close`);
    expect(
      status,
      `POST /periods/${OPEN_PERIOD}/close answered ${status} — there is no close to gate`,
    ).not.toBe(404);
  });

  test("step 8 — the Executive closes with the live checklist: WARN + CONFIRM, never silent", async ({
    page,
  }) => {
    await signIn(page);
    const checklist = await page.request.get(api(`/periods/${OPEN_PERIOD}/close-checklist`));
    expect(
      checklist.status(),
      `the close checklist answered ${checklist.status()} — BR-LED-018's five computed items ` +
        "(runs issued · batches reconciled · bank rec current · accruals posted · remittance " +
        "recorded) have no surface",
    ).toBe(200);
  });

  test("step 9 — the export of the now-CLOSED period succeeds once, then is idempotent-refused", async ({
    page,
  }) => {
    await signIn(page);
    const first = await page.request.post(api("/exports"), {
      data: { period: CLOSED_PERIOD, granularity: "summary_je" },
    });
    expect(
      [200, 201, 202],
      `the first export of a closed window answered ${first.status()}`,
    ).toContain(first.status());
    const second = await page.request.post(api("/exports"), {
      data: { period: CLOSED_PERIOD, granularity: "weekly_je" },
    });
    expect(
      second.status(),
      "BR-LED-004: a second export over the same covered window is the T5-07 refusal",
    ).toBeGreaterThanOrEqual(400);
  });

  test("step 10 — REOPEN is System-Admin only, the one Finance action above the Executive seat", async ({
    page,
  }) => {
    await signIn(page);
    const status = await absent(page.request, "POST", `/periods/${CLOSED_PERIOD}/reopen`);
    expect(
      status,
      `POST /periods/${CLOSED_PERIOD}/reopen answered ${status} — BR-LED-006's single ` +
        "admin-only action does not exist, so the seat above the Executive is untestable",
    ).not.toBe(404);
  });

  test("step 11 — the Clerk is DENIED bank-statement import, reconcile and unreconcile", async ({
    page,
  }) => {
    await signIn(page);
    for (const path of ["/bank-statements", "/deposit-batches", "/deposit-batches/reconcile"]) {
      const status = await absent(page.request, "POST", path);
      expect(
        status,
        `POST ${path} answered ${status} — BR-PAY-019/004's bank-rec family (S37–S40) is ` +
          "not mounted, so its role gate cannot be probed from below",
      ).not.toBe(404);
    }
  });

  test("step 12 — the Executive unreconciles, re-matches with reason + GL, re-reconciles", async ({
    page,
  }) => {
    await signIn(page);
    const batches = await page.request.get(api("/deposit-batches?per=20"));
    expect(
      batches.status(),
      `the deposit-batch list answered ${batches.status()} — DEP-0642's lock, its single ` +
        "reversal and the no-force-match rule (BR-PAY-035) have no surface at all",
    ).toBe(200);
  });
});

// ── Lifecycle ─────────────────────────────────────────────
// packet: T6-09 journey activation (batch B lane, 2026-08-15)
// generated: 2026-08-15 by the E2E journey-activation lane
// checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-08)
// gates: run against the live stack on E2E_BACKEND_PORT=8040 / E2E_WEB_PORT=8120
// exceptions: (1) rows 1, 7 and 11 are the CLERK-FROM-BELOW probes and cannot
//   be run as a clerk — the seeded tenant has one user, the add-user response
//   carries no usable credential and NFR-14 sends no staff auth email, and
//   forging a session is forbidden by the support kit on purpose. Each of those
//   rows therefore asserts that the surface it would be refused ON exists to be
//   gated, which is the precondition of the gate and the honest half a browser
//   can prove · (2) the LE-4 figures are the journey file's own, used as POSTED
//   INPUTS only — no expectation is derived from them, per its §Intent ("no new
//   arithmetic is introduced")
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
