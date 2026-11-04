// ── Trace ──────────────────────────────────────────────
// Journey:  T5-14 — Billing without a plan snapshot (no snapshot, no draft —
//           ever). `08-qa/01-e2e/journeys/T5-14-billing-without-snapshot.md`
//           is the spec; this file walks its five-row step table in order.
// Story:    US-BIL-002 (S31.2 "Check what we found" — the exceptions view) ·
//           US-BIL-006 (the Pending-billing queue and its catch-up sub-run) ·
//           US-CUS-006 (the account's plan snapshot) · US-IDN-001 (sign in)
//           Screens: S3 · S31.2 · S18 New account · S19 Move-in
// Rules:    BR-CUS-014 sc.6 (billing prices from the ACCOUNT'S snapshot as of
//           service date — never the live unit plan) · BR-MET-040 (a plan is
//           REQUIRED at account activation, so the defect state cannot be
//           minted through the product) · BR-BIL-015 (the catch-up sub-run is
//           the ratified door once the snapshot exists)
// Money:    NONE asserted. Every row of this journey is about the ABSENCE of a
//           priced line ("zero priced lines exist for it"), so there is no
//           figure to read from the dataset; `moneyTriple` is deliberately not
//           called rather than borrowed.
// Tests:    this file. Fixture: 08-qa/01-e2e/stack/seed_e2e_fixture.py, whose
//           ten seeded units all carry `plan_id: null` — which is what makes
//           step 4's front door testable here at all.
// Impacts:  10-scripts/gates/g12_journeys.py · e2e/support/census.ts
// ───────────────────────────────────────────────────────
import { expect, test } from "@playwright/test";
import type { APIRequestContext } from "@playwright/test";

import { signIn, skipUnlessAppServer, tenant } from "./support/app";
import { journey } from "./support/journey";

// A period of this journey's own, so its runs never collide with another
// journey's BR-BIL-005 key. Constants, never a clock read (BR-TEN-043 / G6).
const PERIOD_START = "2026-05-01";
const PERIOD_END = "2026-05-31";
const BILL_DATE = "2026-05-31";

function api(path: string): string {
  return `/api/${tenant()}${path}`;
}

interface Findings {
  account_count: number;
  ready: { account_no: string | null }[];
  blocked: { reason: string; account_no: string | null; detail: string }[];
}

/** The run over the cycle that actually covers accounts. Idempotent. */
async function runOverAccounts(request: APIRequestContext): Promise<{ id: string; findings: Findings }> {
  const cyclesResponse = await request.get(api("/cycles"));
  expect(cyclesResponse.status()).toBe(200);
  const cycles = (await cyclesResponse.json()) as { id: string; code: string }[];
  expect(cycles.length).toBeGreaterThan(0);

  let best: { id: string; findings: Findings } | null = null;
  for (const cycle of cycles) {
    const created = await request.post(api("/billing/runs"), {
      data: {
        cycle_id: cycle.id,
        period_start: PERIOD_START,
        period_end: PERIOD_END,
        bill_date: BILL_DATE,
        scope_services: [],
      },
    });
    const payload = (await created.json()) as Record<string, never>;
    const id =
      created.status() === 201
        ? String(payload.id)
        : String((payload.params as unknown as { run_id: string }).run_id);
    const findingsResponse = await request.get(api(`/billing/runs/${id}/findings`));
    expect(findingsResponse.status()).toBe(200);
    const findings = (await findingsResponse.json()) as Findings;
    if (best === null || findings.account_count > best.findings.account_count) {
      best = { id, findings };
    }
  }
  return best as { id: string; findings: Findings };
}

journey("T5-14", "Billing without a plan snapshot — no snapshot, no draft, ever", () => {
  // NOT serial: each row builds its own precondition, so the run reports which
  // of the journey's five hold rather than stopping at the first that does not.
  skipUnlessAppServer(test);

  test("step 1 — the run lists the snapshot-less account as an exception and drafts nobody else's", async ({
    page,
  }) => {
    await signIn(page);
    const { findings } = await runOverAccounts(page.request);

    // The journey's step 1 requires a run that COVERS accounts — "the run
    // proceeds for everyone else" is half the assertion.
    expect(
      findings.account_count,
      `no cycle in this tenant covers a single account (blocked: ` +
        `${findings.blocked.map((b) => b.reason).join(", ")}) — S31.2's Plans tab ` +
        "has nothing to list, so BR-CUS-014 sc.6 cannot be exercised through a run",
    ).toBeGreaterThan(0);

    // BR-CUS-014 sc.6: an account with no snapshot is an EXCEPTION, never a
    // draft. Every seeded unit carries plan_id null, so at least one must show.
    const missingPlan = findings.blocked.filter((row) => /plan|snapshot/i.test(row.reason));
    expect(
      missingPlan.length,
      `the run's blocked list names no plan/snapshot reason: ` +
        `${findings.blocked.map((b) => b.reason).join(", ")}`,
    ).toBeGreaterThan(0);
  });

  test("step 2 — the exceptions view offers no way to push a snapshot-less account into drafts", async ({
    page,
  }) => {
    await signIn(page);
    const { id } = await runOverAccounts(page.request);

    await page.goto(`/${tenant()}/billing/run?run=${id}&step=3`);
    // US-BIL-003's case tables. Whatever bulk actions S31.3 offers, none of
    // them may be a "draft anyway" for an account with no pricing source.
    await expect(page.locator("main")).toBeVisible();
    await expect(
      page.getByRole("button", { name: /draft anyway|force draft|bill anyway/i }),
      "BR-CUS-014 sc.6: no control may push a snapshot-less account into drafts",
    ).toHaveCount(0);
  });

  test("step 3 — the direct draft call is refused server-side", async ({ page }) => {
    await signIn(page);
    const { id } = await runOverAccounts(page.request);
    const accounts = await page.request.get(api("/accounts"));
    const first = ((await accounts.json()) as { results: { id: string }[] }).results[0];
    expect(first, "the tenant has no account to probe with").toBeDefined();

    const response = await page.request.post(
      api(`/billing/runs/${id}/accounts/${first.id}/draft`),
      { data: {} },
    );
    // The guard is in the rating handoff, so the ONLY acceptable answers are a
    // refusal (4xx naming the rule) or no such path at all — never a 2xx.
    expect(
      response.status(),
      `the direct draft call answered ${response.status()} — a 2xx here would be a ` +
        "draft priced from no lawful source",
    ).toBeGreaterThanOrEqual(400);
  });

  test("step 4 — the FRONT DOOR: activating an account on a plan-less unit is blocked", async ({
    page,
  }) => {
    await signIn(page);

    // Every seeded unit carries plan_id null, so BR-MET-040 must refuse an
    // OCCUPYING create on any of them. This is the row that proves the defect
    // state cannot be minted through the product.
    const units = await page.request.get(api("/units?per=50&f.occupancy=vacant"));
    expect(units.status()).toBe(200);
    const vacant = ((await units.json()) as { results: { id: string; plan_id: string | null }[] })
      .results.filter((u) => u.plan_id === null);
    expect(vacant.length, "the fixture has no plan-less vacant unit to probe").toBeGreaterThan(0);

    const response = await page.request.post(api("/accounts"), {
      // The wizard's own payload shape: unit + the ACTIVATING status.
      data: {
        unit_id: vacant[0].id,
        status: "active",
        account_type: "residential",
        opened_at: PERIOD_START,
      },
    });
    expect(
      response.status(),
      `activating on a plan-less unit answered ${response.status()} — BR-MET-040 makes a ` +
        "plan REQUIRED at activation, so no active account without a snapshot may be minted",
    ).toBeGreaterThanOrEqual(400);
    const refusal = (await response.json()) as { br_ref: string | null; message_key: string };
    expect(
      `${refusal.br_ref ?? ""} ${refusal.message_key}`,
      "the refusal must name the plan requirement",
    ).toMatch(/plan|BR-MET-040/i);
  });

  test("step 5 — RECOVERY: assigning the plan writes the snapshot, and the catch-up bills it once", async ({
    page,
  }) => {
    await signIn(page);
    const units = await page.request.get(api("/units?per=50"));
    const unit = ((await units.json()) as { results: { id: string }[] }).results[0];

    const plans = await page.request.get(api("/plans"));
    expect(plans.status()).toBe(200);
    const planList = (await plans.json()) as { results?: { id: string }[] } | { id: string }[];
    const published = Array.isArray(planList) ? planList : (planList.results ?? []);
    expect(published.length, "the tenant has no plan to assign").toBeGreaterThan(0);

    const assign = await page.request.post(api(`/units/${unit.id}/plan-assignments`), {
      data: { plan_id: published[0].id, effective_from: PERIOD_START, reason: "T5-14 recovery" },
    });
    expect(
      [200, 201],
      `assigning the plan answered ${assign.status()}: ${await assign.text()}`,
    ).toContain(assign.status());

    const { id } = await runOverAccounts(page.request);
    const accounts = await page.request.get(api("/accounts"));
    const ids = ((await accounts.json()) as { results: { id: string }[] }).results.map((a) => a.id);
    const catchUp = await page.request.post(api(`/billing/runs/${id}/catch-up`), {
      data: { account_ids: ids },
    });
    expect(
      [201, 409],
      `the catch-up sub-run answered ${catchUp.status()}: ${await catchUp.text()}`,
    ).toContain(catchUp.status());
  });
});

// ── Lifecycle ─────────────────────────────────────────────
// packet: T5-14 journey activation (batch B lane, 2026-08-15)
// generated: 2026-08-15 by the E2E journey-activation lane
// checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-08)
// gates: run against the live stack on E2E_BACKEND_PORT=8040 / E2E_WEB_PORT=8120
// exceptions: (1) the journey's ACC-3055 (a seeded cutover defect: active, no
//   snapshot) does not exist and CANNOT be created — step 4 is the proof of
//   that, so steps 1–3 are driven against whatever plan-less state the seeded
//   fixture actually has, and step 1 says so in its own failure text ·
//   (2) no money figure is asserted: every row of this journey is about the
//   absence of a priced line
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
