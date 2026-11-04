// ── Trace ──────────────────────────────────────────────
// Journey:  T7-11 — Config change: late-fee grace mode calendar → business
//           (next evaluation shifts; assessed fees stand).
//           `08-qa/01-e2e/journeys/T7-11-grace-mode-calendar-to-business.md` is
//           the spec; this file walks its six-row step table in order.
// Story:    US-TEN-010 (the S66 rule page and its atomic tab save) ·
//           US-PAY-014 (collections / late-fee assessment) · US-IDN-001
//           Screens: S3 · S66 Billing defaults (Settings → Configure →
//           Reference data → Billing defaults)
// Rules:    BR-BIL-002 (grace is calendar OR business days, a tenant setting) ·
//           BR-BIL-008 (the 5-day default) · BR-BIL-021 (late-fee params are
//           tenant config) · BR-TEN-016 (one before/after audit row per atomic
//           save) · BR-TEN-020 (a settings save never restates history) ·
//           BR-AUD-011 (one row per atomic save)
// Money:    `moneyTriple("flat","cycle","none")` — the journey's ACC-1101 /
//           ACC-1102 row (97.41 outstanding, next_late_fee 5.00). Read at run
//           time; no figure is typed in this file.
// Impacts:  10-scripts/gates/g12_journeys.py · e2e/support/census.ts
// ───────────────────────────────────────────────────────
//
// WHAT THIS JOURNEY SPLITS INTO, on this product. The CONFIG half — the rule
// page, the atomic save, the single before/after audit row, and the invariance
// of every issued row across it — is fully reachable. The EVALUATION half —
// "grace now counts 5 BUSINESS days, so expiry moves 08-19 → 08-21, and the fee
// assesses at the later date" — needs a collections engine with an assessable
// account behind it. Both halves are walked; which one the product can perform
// is the finding.
import { expect, test } from "@playwright/test";
import type { APIRequestContext } from "@playwright/test";

import { signIn, skipUnlessAppServer, tenant } from "./support/app";
import { moneyTriple } from "./support/expected";
import { journey } from "./support/journey";

const OUTSTANDING = moneyTriple("flat", "cycle", "none");
const CARD_LABEL = "Billing defaults";

function api(path: string): string {
  return `/api/${tenant()}${path}`;
}

interface BillingDefaults {
  late_pct: string;
  late_min_amount: string;
  late_grace_days: number;
  late_grace_mode: string;
  overcharge_guardrail_pct: string;
}

async function defaults(request: APIRequestContext): Promise<BillingDefaults> {
  const response = await request.get(api("/settings/billing-defaults"));
  expect(response.status()).toBe(200);
  return (await response.json()) as BillingDefaults;
}

interface AuditRow {
  action: string;
  entity_type: string;
  summary: string;
}

async function auditRows(request: APIRequestContext, per = 25): Promise<AuditRow[]> {
  const response = await request.get(api(`/audit-log?per=${per}`));
  expect(response.status()).toBe(200);
  return ((await response.json()) as { results: AuditRow[] }).results;
}

/** Opens S66 by clicking, the way an admin reaches it (BR-SHL-035 card grid). */
async function openBillingDefaults(page: import("@playwright/test").Page): Promise<void> {
  await page.goto(`/${tenant()}/settings/reference-data`);
  await page.getByRole("button", { name: CARD_LABEL }).first().click();
  await expect(page.locator("#late_grace_mode")).toBeVisible();
}

journey("T7-11", "Config change: late-fee grace mode calendar → business", () => {
  // NOT serial: each row re-reads the settings, so the run reports which of the
  // journey's six hold rather than stopping at the first that does not.
  skipUnlessAppServer(test);

  test("step 1 — baseline: the tenant is on calendar grace with the BR-BIL-008 default", async ({
    page,
  }) => {
    await signIn(page);
    // Restore the journey's own starting state, so a re-run of the suite starts
    // where the fixture says it does.
    await page.request.put(api("/settings/billing-defaults"), {
      data: { late_grace_mode: "calendar" },
    });
    const config = await defaults(page.request);
    expect(config.late_grace_mode).toBe("calendar");
    expect(config.late_grace_days, "BR-BIL-008's default grace").toBe(5);
    // The journey's fixture figure, read from the frozen dataset.
    expect(OUTSTANDING.next_late_fee, "the dataset must carry the fee this journey cites")
      .not.toBe("");
  });

  test("step 2 — the flip saves on S66 and writes ONE before/after audit row", async ({ page }) => {
    await signIn(page);
    await page.request.put(api("/settings/billing-defaults"), {
      data: { late_grace_mode: "calendar" },
    });
    const auditBefore = (await auditRows(page.request, 50)).filter((r) =>
      r.action.includes("billing_defaults"),
    ).length;

    await signIn(page);
    await openBillingDefaults(page);
    await page.locator("#late_grace_mode").selectOption("business");
    await page.getByRole("button", { name: /^Save/ }).first().click();

    await expect
      .poll(async () => (await defaults(page.request)).late_grace_mode, {
        message: "the atomic tab save must land the new mode",
      })
      .toBe("business");

    // BR-TEN-016 / BR-AUD-011: ONE row, naming only the changed field.
    const rows = (await auditRows(page.request, 50)).filter((r) =>
      r.action.includes("billing_defaults"),
    );
    expect(rows.length, "one atomic save = exactly one audit row").toBe(auditBefore + 1);
    expect(rows[0].action).toBe("settings.billing_defaults.updated");
    expect(rows[0].entity_type).toBe("tenant_settings");
    expect(
      rows[0].summary,
      "the row must carry the CHANGED FIELD with its before → after",
    ).toMatch(/late_grace_mode:\s*calendar\s*→\s*business/);
  });

  test("step 3 — the next fee evaluation counts BUSINESS days from the due date", async ({
    page,
  }) => {
    await signIn(page);
    await page.request.put(api("/settings/billing-defaults"), {
      data: { late_grace_mode: "business" },
    });

    // The evaluation is the collections engine's, run server-side under the
    // mode in force at evaluation time (BR-BIL-002).
    // `POST /collections/run` is the S34 BULK ACTION, not a nightly job — the
    // endpoint's own docstring says so and every response carries
    // `no_scheduled_caller`. So the evaluation is driven the only way the
    // product allows: over a clerk's selection.
    const accounts = await page.request.get(api("/accounts?per=50"));
    const ids = ((await accounts.json()) as { results: { id: string }[] }).results.map((a) => a.id);
    const response = await page.request.post(api("/collections/run"), {
      data: { as_of: "2026-08-20", account_ids: ids },
    });
    expect(
      response.status(),
      `the collections evaluation answered ${response.status()}: ` +
        `${(await response.text()).slice(0, 300)}`,
    ).toBeLessThan(400);
    const body = await response.text();
    expect(
      body,
      "the evaluation must report the grace basis it used, or the mode flip is unobservable",
    ).toMatch(/grace|business|eligib/i);
  });

  test("step 4 — a fee assessed after the flip carries the minimum from the dataset", async ({
    page,
  }) => {
    await signIn(page);
    const accounts = await page.request.get(api("/accounts?per=50"));
    const ids = ((await accounts.json()) as { results: { id: string }[] }).results.map((a) => a.id);
    const response = await page.request.post(api("/collections/run"), {
      data: { as_of: "2026-08-22", account_ids: ids },
    });
    expect(response.status()).toBeLessThan(400);
    const assessed = await page.request.get(api("/invoices?per=100"));
    expect(assessed.status()).toBe(200);
    const rows = ((await assessed.json()) as {
      results: { bill_type: string; total: string | null }[];
    }).results;
    const feeRows = rows.filter((r) => r.bill_type === "late_fee" || r.bill_type === "penalty");
    expect(
      feeRows.length,
      "no fee row was assessed, so BR-BIL-002's business-day expiry cannot be observed",
    ).toBeGreaterThan(0);
    expect(
      feeRows.map((r) => r.total),
      `the assessed fee must be the dataset's ${OUTSTANDING.next_late_fee}`,
    ).toContain(OUTSTANDING.next_late_fee);
  });

  test("step 5 — a fee assessed BEFORE the flip is untouched by the save", async ({ page }) => {
    await signIn(page);
    // Every issued row is immutable (hard rule 4); the settings save may not
    // re-date, re-compute or reverse one. Read the issued set, flip, read again.
    const before = await page.request.get(api("/invoices?per=100"));
    const beforeText = await before.text();

    await page.request.put(api("/settings/billing-defaults"), {
      data: { late_grace_mode: "calendar" },
    });
    await page.request.put(api("/settings/billing-defaults"), {
      data: { late_grace_mode: "business" },
    });

    const after = await page.request.get(api("/invoices?per=100"));
    expect(
      await after.text(),
      "BR-TEN-020: a settings write never touches a money row",
    ).toBe(beforeText);
  });

  test("step 6 — INVARIANCE: the ledger is unchanged across both saves", async ({ page }) => {
    await signIn(page);
    const before = await (await page.request.get(api("/ledger/trial-balance"))).text();
    await page.request.put(api("/settings/billing-defaults"), {
      data: { late_grace_mode: "calendar" },
    });
    const after = await (await page.request.get(api("/ledger/trial-balance"))).text();
    expect(after, "NFR-22: changing settings does not restate history").toBe(before);
    expect((await defaults(page.request)).late_grace_mode, "the fixture is left as found").toBe(
      "calendar",
    );
  });
});

// ── Lifecycle ─────────────────────────────────────────────
// packet: T7-11 journey activation (batch B lane, 2026-08-15)
// generated: 2026-08-15 by the E2E journey-activation lane
// checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-08)
// gates: run against the live stack on E2E_BACKEND_PORT=8040 / E2E_WEB_PORT=8120
// exceptions: (1) the journey's ACC-1101 (fee already assessed under calendar)
//   and ACC-1102 (due Fri 2026-08-14, not yet eligible) are not seeded, so
//   steps 3–4 exercise the collections evaluation against whatever the tenant
//   holds and say so in their own failure text · (2) the spec RESTORES
//   `late_grace_mode: calendar` at the end so the shared fixture is left as it
//   was found — a config knob is not a money row and restoring it is not
//   rewriting history
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
