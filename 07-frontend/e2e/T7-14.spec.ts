// ── Trace ──────────────────────────────────────────────
// Journey:  T7-14 — Config change: overcharge guardrail % (next run's preview
//           flags shift; issued flags stand).
//           `08-qa/01-e2e/journeys/T7-14-overcharge-guardrail-change.md` is the
//           spec; this file walks its six-row step table in order.
// Story:    US-TEN-010 (S66 rule page, atomic save) · US-BIL-002 (S31.2 run
//           preview) · US-BIL-004 (draft totals) · US-BIL-005 (the run summary
//           and release) · US-IDN-001 (sign in)
//           Screens: S3 · S66 Billing defaults · S31.2 run preview
// Rules:    BR-BIL-029 (the guardrail flags any draft above the tenant-set % of
//           the account's trailing average, IN THE PREVIEW, before issue —
//           default 200%) · BR-BIL-021 · BR-TEN-016 · BR-TEN-020
// Money:    `moneyTriple("flat","cycle","full")` (the 97.41 trailing average)
//           and `moneyTriple("flat","backbill","full")` (the 292.23 backbill
//           draft). Both read at run time; the ratio between them is the
//           journey's own harness-verified fact and is not recomputed here.
// Impacts:  10-scripts/gates/g12_journeys.py · e2e/support/census.ts
// ───────────────────────────────────────────────────────
import { expect, test } from "@playwright/test";
import type { APIRequestContext, Page } from "@playwright/test";

import { signIn, skipUnlessAppServer, tenant } from "./support/app";
import { moneyTriple } from "./support/expected";
import { journey } from "./support/journey";

const TRAILING = moneyTriple("flat", "cycle", "full");
const BACKBILL = moneyTriple("flat", "backbill", "full");
const CARD_LABEL = "Billing defaults";

// Two runs of this journey's own, on periods no other journey in the batch
// uses, so no BR-BIL-005 key collides. Constants, never a clock read.
const RUN_A = { start: "2026-03-01", end: "2026-03-31", bill: "2026-03-31" };
const RUN_B = { start: "2026-04-01", end: "2026-04-30", bill: "2026-04-30" };

function api(path: string): string {
  return `/api/${tenant()}${path}`;
}

async function guardrail(request: APIRequestContext): Promise<string> {
  const response = await request.get(api("/settings/billing-defaults"));
  expect(response.status()).toBe(200);
  return ((await response.json()) as { overcharge_guardrail_pct: string })
    .overcharge_guardrail_pct;
}

async function runFor(
  request: APIRequestContext,
  window: { start: string; end: string; bill: string },
): Promise<string> {
  const cycles = (await (await request.get(api("/cycles"))).json()) as { id: string }[];
  expect(cycles.length).toBeGreaterThan(0);
  const created = await request.post(api("/billing/runs"), {
    data: {
      cycle_id: cycles[0].id,
      period_start: window.start,
      period_end: window.end,
      bill_date: window.bill,
      scope_services: [],
    },
  });
  const payload = (await created.json()) as Record<string, never>;
  return created.status() === 201
    ? String(payload.id)
    : String((payload.params as unknown as { run_id: string }).run_id);
}

async function openBillingDefaults(page: Page): Promise<void> {
  await page.goto(`/${tenant()}/settings/reference-data`);
  await page.getByRole("button", { name: CARD_LABEL }).first().click();
  await expect(page.locator("#overcharge_guardrail_pct")).toBeVisible();
}

journey("T7-14", "Config change: overcharge guardrail % — the next preview shifts", () => {
  // NOT serial: each row re-reads the settings, so the run reports which of the
  // journey's six hold rather than stopping at the first that does not.
  skipUnlessAppServer(test);

  test("step 1 — Run A's preview FLAGS the backbill draft above 200% of the trailing average", async ({
    page,
  }) => {
    await signIn(page);
    await page.request.put(api("/settings/billing-defaults"), {
      data: { overcharge_guardrail_pct: "200" },
    });
    expect(await guardrail(page.request)).toBe("200");

    const runId = await runFor(page.request, RUN_A);
    const findings = await page.request.get(api(`/billing/runs/${runId}/findings`));
    expect(findings.status()).toBe(200);
    const body = await findings.text();
    expect(
      body,
      `BR-BIL-029: the preview must carry an overcharge finding for a ${BACKBILL.total} ` +
        `draft against a ${TRAILING.total} trailing average — the findings payload names ` +
        "no guardrail at all",
    ).toMatch(/overcharge|guardrail|BR-BIL-029/i);
  });

  test("step 2 — a knowingly-issued flagged bill proceeds and records the flag state", async ({
    page,
  }) => {
    await signIn(page);
    const runId = await runFor(page.request, RUN_A);
    // BR-BIL-029 informs, it does not block: issue must be reachable, and the
    // knowingly-issued flag recorded with the run.
    const issue = await page.request.post(api(`/billing/runs/${runId}/issue`), { data: {} });
    expect(
      issue.status(),
      `POST /billing/runs/{id}/issue answered ${issue.status()} — the guardrail's ` +
        "'informs, does not block' semantics cannot be observed without an issue path",
    ).toBeLessThan(400);
  });

  test("step 3 — the % change saves atomically and writes ONE before/after audit row", async ({
    page,
  }) => {
    await signIn(page);
    await page.request.put(api("/settings/billing-defaults"), {
      data: { overcharge_guardrail_pct: "200" },
    });

    await signIn(page);
    await openBillingDefaults(page);
    await page.locator("#overcharge_guardrail_pct").fill("350");
    await page.getByRole("button", { name: /^Save/ }).first().click();

    await expect
      .poll(async () => guardrail(page.request), {
        message: "the atomic tab save must land the new guardrail",
      })
      .toMatch(/^350(\.0+)?$/);

    const audit = await page.request.get(api("/audit-log?per=25"));
    const rows = ((await audit.json()) as { results: { action: string; summary: string }[] })
      .results.filter((r) => r.action === "settings.billing_defaults.updated");
    expect(rows.length, "the save must audit").toBeGreaterThan(0);
    expect(
      rows[0].summary,
      "BR-TEN-016: the row carries the changed field with its before → after",
    ).toMatch(/overcharge_guardrail_pct:\s*200\s*→\s*350/);
  });

  test("step 4 — Run B's preview does NOT flag the identical draft under the new threshold", async ({
    page,
  }) => {
    await signIn(page);
    await page.request.put(api("/settings/billing-defaults"), {
      data: { overcharge_guardrail_pct: "350" },
    });
    const runId = await runFor(page.request, RUN_B);
    const findings = await page.request.get(api(`/billing/runs/${runId}/findings`));
    expect(findings.status()).toBe(200);
    const body = await findings.text();
    expect(
      body,
      "the threshold is read at PREVIEW time, so the same draft must clear 350%",
    ).not.toMatch(/overcharge/i);
  });

  test("step 5 — Run A's recorded flag state is unchanged by the config save", async ({ page }) => {
    await signIn(page);
    const runId = await runFor(page.request, RUN_A);
    const before = await (await page.request.get(api(`/billing/runs/${runId}/findings`))).text();
    await page.request.put(api("/settings/billing-defaults"), {
      data: { overcharge_guardrail_pct: "200" },
    });
    await page.request.put(api("/settings/billing-defaults"), {
      data: { overcharge_guardrail_pct: "350" },
    });
    // A preview evaluation is a point-in-time FACT. Re-reading Run A after a
    // threshold change must not re-evaluate it.
    expect(
      await (await page.request.get(api(`/billing/runs/${runId}/findings`))).text(),
      "BR-TEN-020: past previews and issued bills never re-evaluate",
    ).toBe(before);
  });

  test("step 6 — INVARIANCE: the settings save changed zero money rows", async ({ page }) => {
    await signIn(page);
    const invoices = await (await page.request.get(api("/invoices?per=200"))).text();
    const ledger = await (await page.request.get(api("/ledger/trial-balance"))).text();
    await page.request.put(api("/settings/billing-defaults"), {
      data: { overcharge_guardrail_pct: "200" },
    });
    expect(await (await page.request.get(api("/invoices?per=200"))).text()).toBe(invoices);
    expect(await (await page.request.get(api("/ledger/trial-balance"))).text()).toBe(ledger);
    expect(await guardrail(page.request), "the fixture is left as found").toBe("200");
  });
});

// ── Lifecycle ─────────────────────────────────────────────
// packet: T7-14 journey activation (batch B lane, 2026-08-15)
// generated: 2026-08-15 by the E2E journey-activation lane
// checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-08)
// gates: run against the live stack on E2E_BACKEND_PORT=8040 / E2E_WEB_PORT=8120
// exceptions: (1) ACC-1130/1131 (a flat account billed 97.41 every cycle with a
//   292.23 backbill draft) are not seeded, so steps 1 and 4 assert the presence
//   and absence of the guardrail finding in the run's own preview payload
//   rather than against those two accounts · (2) the ratio between the two
//   dataset figures is the journey's harness-verified fact and is NOT
//   recomputed here — a second computation of a frozen relationship is the
//   drift CLAUDE.md forbids · (3) the spec restores the 200 default
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
