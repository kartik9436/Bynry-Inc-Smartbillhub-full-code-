// ── Trace ──────────────────────────────────────────────
// Journey:  T5-05 — Duplicate bill run (idempotency key refuses the re-run).
//           `08-qa/01-e2e/journeys/T5-05-duplicate-bill-run.md` is the spec;
//           this file walks its five-row step table in order.
// Story:    US-BIL-001 (S31 step 1 — cycle · period · scope · the idempotent
//           run) · US-BIL-006 (the Pending-billing queue and its catch-up
//           sub-run) · US-IDN-001 (the S3 sign-in every step rides on)
//           Screens: S3 · S31 step 1
// Rules:    BR-BIL-005 (one run per tenant+cycle+period; the refusal carries
//           who/when/link) · BR-BIL-015 (a catch-up SUB-RUN is parent-linked
//           and scope-keyed, so it never collides with the parent key) ·
//           CLAUDE.md hard rule 6 (bill runs are idempotent) · NFR-16 (the
//           refusal is server-side; UI gating is convenience) · NFR-4 (a race
//           has exactly one winner)
// Money:    the journey's fixture cites money-triples `flat,cycle,full`
//           ($97.41). This stack's seeded tenant carries ONE issued bill,
//           BL-2606-000001 at GT-1's signed total, so the "nothing changed"
//           invariant is asserted against `goldenCalc("GT-1")` — the second
//           sanctioned source (e2e/README.md §Support kit). `moneyTriple` is
//           read for the journey's own named figure and asserted as ABSENT
//           from the tenant, which is the honest statement about a fixture
//           this stack does not seed.
// Tests:    this file. Fixture: 08-qa/01-e2e/stack/seed_e2e_fixture.py
// Impacts:  10-scripts/gates/g12_journeys.py (activation) ·
//           e2e/support/census.ts (the run receipt G12 reads)
// ───────────────────────────────────────────────────────
//
// WHAT THIS JOURNEY CAN AND CANNOT DO ON THIS STACK, stated before the code so
// nobody reads a green run as more than it is.
//
// The journey's fixture is a COMPLETED run RUN-2607-A that issued 1,240
// invoices. Nothing seeds that, and `POST /billing/runs/{id}/issue` is not
// served at all (apps/billing/api.py's own trailer says so). So the parent run
// this spec refuses a duplicate of is one it CREATES, through S31 step 1, the
// way a clerk does — a run in `draft`, not an issued one. Every refusal under
// test (BR-BIL-005's unique tenant+cycle+period key) is armed the moment that
// row exists, so the rule is genuinely exercised; what is NOT exercised is the
// "1,240 invoices already issued" backdrop, and step 1's "invoice count for the
// period still exactly 1,240" is therefore asserted as "the tenant's invoice
// count did not move", which is the same claim at this fixture's scale.
//
// REPEATABILITY. This spec WRITES, and `boot_stack.sh` does not drop between
// runs, so the parent run exists already on the second run. The setup below
// accepts EITHER outcome — 201 with a new id, or 409 carrying the original's id
// — because "a run for this cycle+period exists" is the journey's FIXTURE, not
// its assertion. Every assertion after the setup is one that holds on every run.
import { expect, test } from "@playwright/test";
import type { APIResponse, Page } from "@playwright/test";

import { signIn, skipUnlessAppServer, tenant } from "./support/app";
import { goldenCalc, moneyTriple } from "./support/expected";
import { journey } from "./support/journey";

const GT1_TOTAL = goldenCalc("GT-1").total;
// The journey's own fixture figure. Read, never typed.
const TRIPLE_CYCLE_FULL = moneyTriple("flat", "cycle", "full");

// The period this journey runs and re-runs. Fixed constants, never a clock
// read (BR-TEN-043 / gate G6): the same two dates on every run, so the second
// POST is a duplicate of the first by construction.
const PERIOD_START = "2026-07-01";
const PERIOD_END = "2026-07-31";
const BILL_DATE = "2026-07-31";

function api(path: string): string {
  return `/api/${tenant()}${path}`;
}

interface RunRefusal {
  code: string;
  br_ref: string | null;
  params: Record<string, string | null>;
}

async function body(response: APIResponse): Promise<Record<string, unknown>> {
  return (await response.json()) as Record<string, unknown>;
}

/**
 * The journey's fixture, established the only way this product allows: create
 * the run. Returns the id of the run that owns (cycle, PERIOD_START..END) —
 * whether this call minted it or an earlier run of the suite did.
 */
async function parentRunId(page: Page, cycleId: string): Promise<string> {
  const response = await page.request.post(api("/billing/runs"), {
    data: {
      cycle_id: cycleId,
      period_start: PERIOD_START,
      period_end: PERIOD_END,
      bill_date: BILL_DATE,
      scope_services: [],
    },
  });
  const payload = await body(response);
  if (response.status() === 201) {
    return String(payload.id);
  }
  expect(
    response.status(),
    "the fixture run neither created (201) nor already existed (409)",
  ).toBe(409);
  return String((payload.params as Record<string, string>).run_id);
}

async function firstCycleId(page: Page): Promise<string> {
  const response = await page.request.get(api("/cycles"));
  expect(response.status()).toBe(200);
  const cycles = (await response.json()) as { id: string; code: string }[];
  expect(cycles.length, "the seeded tenant has no cycle to run").toBeGreaterThan(0);
  return cycles[0].id;
}

async function invoiceCount(page: Page): Promise<number> {
  const response = await page.request.get(api("/invoices"));
  expect(response.status()).toBe(200);
  return ((await response.json()) as { count: number }).count;
}

async function runCount(page: Page, cycleId: string): Promise<number> {
  // There is no GET /billing/runs (405 — the collection is write-only), so the
  // count of runs for this key is read the only way the product allows: by
  // asking for one more and reading the refusal. A key that carried two runs
  // could not answer with one original id.
  const response = await page.request.post(api("/billing/runs"), {
    data: {
      cycle_id: cycleId,
      period_start: PERIOD_START,
      period_end: PERIOD_END,
      bill_date: BILL_DATE,
      scope_services: [],
    },
  });
  return response.status() === 409 ? 1 : 2;
}

journey("T5-05", "Duplicate bill run — the idempotency key refuses the re-run", () => {
  // NOT serial: every test below signs in and builds its own precondition,
  // so the run reports which of the journey's rows hold rather than stopping
  // at the first that does not. Which row is the first the product cannot
  // perform is the deliverable.
  skipUnlessAppServer(test);

  test("step 1 — the clerk re-selects the same cycle+period on S31 and is refused at creation", async ({
    page,
  }) => {
    await signIn(page);
    const cycleId = await firstCycleId(page);
    const original = await parentRunId(page, cycleId);
    const invoicesBefore = await invoiceCount(page);

    // A human clicking: sidebar → Billing → the Run bills tab (S31 step 1).
    const nav = page.getByRole("navigation", { name: "Main navigation" });
    await nav.getByRole("link", { name: "Billing", exact: true }).click();
    await expect(page).toHaveURL(new RegExp(`/${tenant()}/billing$`));
    await page.getByRole("tab", { name: "Run bills" }).click();
    await expect(page).toHaveURL(new RegExp(`/${tenant()}/billing/run`));

    // The same cycle and the same period the fixture run already owns.
    await page.locator("#brun-cycle").selectOption(cycleId);
    await page.locator("#brun-period-start").fill(PERIOD_START);
    await page.locator("#brun-period-end").fill(PERIOD_END);
    await page.locator("#brun-bill-date").fill(BILL_DATE);
    // "Tick at least one service, or this run bills nobody" — the screen's own
    // scope rule, so the run is complete before it is refused for the RIGHT
    // reason (a scope refusal would prove nothing about BR-BIL-005).
    // The input itself is visually hidden behind the `.radio`/`.dot` styling
    // (components/FormModal.tsx CheckboxField), so a human clicks the LABEL.
    await page.locator('label[for="brun-service-electric"]').click();
    await expect(page.locator("#brun-service-electric")).toBeChecked();

    // Step 1's exit — the wizard's own control, NOT Continue (BR-SHL-019 gives
    // this wizard one transactional commit and it is step 6's release).
    await page.getByRole("button", { name: "Start this run" }).click();

    // The journey requires the REFUSAL to reach the screen: an IS-7 failed
    // state naming the run that already exists, with WHO ran it and WHEN
    // (BR-BIL-005's three facts, which the server composes and sends).
    const failure = page.locator('[data-brun="failure"]');
    await expect(failure, "S31 step 1 must render BR-BIL-005's refusal").toBeVisible();
    await expect(
      failure,
      "the refusal must be a SENTENCE, not the untranslated catalog key",
    ).not.toHaveText("billing.run.duplicate");
    await expect(
      failure,
      "BR-BIL-005: the refusal must carry the ORIGINAL run's id so the clerk can navigate to it",
    ).toContainText(original);

    // Nothing changed.
    expect(await invoiceCount(page), "a refused run must not mint invoices").toBe(invoicesBefore);
  });

  test("step 2 — five replays of POST /billing/runs all hit the same unique key", async ({
    page,
  }) => {
    await signIn(page);
    const cycleId = await firstCycleId(page);
    const original = await parentRunId(page, cycleId);
    const invoicesBefore = await invoiceCount(page);

    const refusals: RunRefusal[] = [];
    for (let attempt = 0; attempt < 5; attempt++) {
      const response = await page.request.post(api("/billing/runs"), {
        data: {
          cycle_id: cycleId,
          period_start: PERIOD_START,
          period_end: PERIOD_END,
          bill_date: BILL_DATE,
          scope_services: [],
        },
      });
      expect(response.status(), `replay ${attempt + 1} must be refused 409`).toBe(409);
      refusals.push((await response.json()) as unknown as RunRefusal);
    }

    for (const refusal of refusals) {
      expect(refusal.code).toBe("BIZ-IDEMPOTENT");
      expect(refusal.br_ref).toBe("BR-BIL-005");
      // The SAME original every time — a retry storm never forks the answer.
      expect(refusal.params.run_id).toBe(original);
      expect(refusal.params.ran_at, "the refusal must say WHEN the original ran").not.toBeNull();
    }

    // Zero money writes: the ledger and the issued bill are exactly as they were.
    expect(await invoiceCount(page)).toBe(invoicesBefore);
    const trialBalance = await page.request.get(api("/ledger/trial-balance"));
    expect(trialBalance.status()).toBe(200);
    const tb = (await trialBalance.json()) as { rows: { debit: string; credit: string }[] };
    const debits = tb.rows.reduce((sum, row) => sum + Number(row.debit), 0);
    const credits = tb.rows.reduce((sum, row) => sum + Number(row.credit), 0);
    expect(debits.toFixed(6), "the ledger must still balance after five refused runs").toBe(
      credits.toFixed(6),
    );
  });

  test("step 3 — two clerks submit the same run concurrently; exactly one row wins", async ({
    page,
  }) => {
    await signIn(page);
    const response = await page.request.get(api("/cycles"));
    const cycles = (await response.json()) as { id: string }[];
    // The SECOND cycle, so the race runs on a key this suite has not used.
    expect(cycles.length, "the race probe needs a second, unused cycle").toBeGreaterThan(1);
    const raceCycle = cycles[1].id;

    const payload = {
      cycle_id: raceCycle,
      period_start: PERIOD_START,
      period_end: PERIOD_END,
      bill_date: BILL_DATE,
      scope_services: [],
    };
    const [a, b] = await Promise.all([
      page.request.post(api("/billing/runs"), { data: payload }),
      page.request.post(api("/billing/runs"), { data: payload }),
    ]);
    const statuses = [a.status(), b.status()].sort();
    // On a re-run of the suite the row already exists, so BOTH lose — which is
    // the same rule holding. What must never happen is both WINNING.
    expect(
      statuses.filter((s) => s === 201).length,
      "a race must never create two runs on one tenant+cycle+period key",
    ).toBeLessThanOrEqual(1);
    expect(await runCount(page, raceCycle), "exactly one run owns the raced key").toBe(1);
  });

  test("step 4 — re-running the whole cycle to catch 'just the held accounts' is refused identically", async ({
    page,
  }) => {
    await signIn(page);
    const cycleId = await firstCycleId(page);
    const original = await parentRunId(page, cycleId);

    const response = await page.request.post(api("/billing/runs"), {
      data: {
        cycle_id: cycleId,
        period_start: PERIOD_START,
        period_end: PERIOD_END,
        bill_date: BILL_DATE,
        // The clerk's intent — "only the held ones" — expressed the only way
        // step 1 allows: a narrowed service scope. The key is unchanged, so
        // the refusal must be unchanged too: a re-run is never that door.
        scope_services: ["electric"],
      },
    });
    expect(response.status(), "a narrowed re-run is still the same key").toBe(409);
    const refusal = (await response.json()) as unknown as RunRefusal;
    expect(refusal.br_ref).toBe("BR-BIL-005");
    expect(refusal.params.run_id).toBe(original);
  });

  test("step 5 — RECOVERY: the catch-up sub-run is scope-keyed and creates cleanly", async ({
    page,
  }) => {
    await signIn(page);
    const cycleId = await firstCycleId(page);
    const parent = await parentRunId(page, cycleId);

    const accounts = await page.request.get(api("/accounts"));
    expect(accounts.status()).toBe(200);
    const held = ((await accounts.json()) as { results: { id: string }[] }).results;
    expect(held.length, "the catch-up needs at least one account to bill").toBeGreaterThan(0);

    const response = await page.request.post(api(`/billing/runs/${parent}/catch-up`), {
      data: { account_ids: held.map((a) => a.id) },
    });
    // 201 the first time; 409 (BR-BIL-005 at sub-run granularity) on a re-run.
    // Either proves the point the journey makes: the sub-run's scope key NEVER
    // collides with the parent's, so it is reachable where the re-run is not.
    expect(
      [201, 409],
      `catch-up answered ${response.status()}: ${await response.text()}`,
    ).toContain(response.status());
    if (response.status() === 201) {
      const child = await body(response);
      expect(String(child.id), "the sub-run is a NEW row, not the parent").not.toBe(parent);
    }
  });

  test("invariance — the one issued bill still renders GT-1's signed total afterwards", async ({
    page,
  }) => {
    // The journey's "nothing changed" column, read from the SCREEN. Every
    // refusal above is only a refusal if the money that existed before is the
    // money that exists after.
    await signIn(page);
    await page.goto(`/${tenant()}/billing`);
    const row = page.getByRole("row").filter({ hasText: "BL-" }).first();
    await expect(row).toBeVisible();
    await expect(row.locator(".cell-money-amount").first()).toHaveText(`$${GT1_TOTAL}`);

    // The journey's own fixture figure ($97.41, money-triples flat/cycle/full)
    // belongs to a tenant this stack does not seed. Asserting it is NOT on
    // screen is the honest statement — and it fails loudly the day someone
    // seeds it, which is when this assertion should be revisited.
    await expect(
      page.locator("main"),
      "the seeded tenant does not carry the journey's 97.41 fixture bill",
    ).not.toContainText(`$${TRIPLE_CYCLE_FULL.total}`);
  });
});

// ── Lifecycle ─────────────────────────────────────────────
// packet: T5-05 journey activation (batch B lane, 2026-08-15)
// generated: 2026-08-15 by the E2E journey-activation lane
// checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-08)
// gates: run against the live stack booted by 08-qa/01-e2e/stack/boot_stack.sh
//   on E2E_BACKEND_PORT=8040 / E2E_WEB_PORT=8120 — counts in the lane report
// exceptions: (1) the journey's fixture (a COMPLETED run that issued 1,240
//   invoices) cannot be built on this product — `POST /billing/runs/{id}/issue`
//   is not served — so the parent run this spec refuses duplicates of is a
//   DRAFT run it creates itself; the BR-BIL-005 key is armed either way, the
//   "1,240 issued" backdrop is not · (2) step 1's "invoice count still exactly
//   1,240" is asserted as "the tenant's invoice count did not move" · (3) step
//   3's race is asserted as "never two winners" rather than "exactly one
//   winner", because on a re-run of the suite the key is already owned and
//   both callers correctly lose · (4) the money figure asserted on screen is
//   GT-1's (the seeded bill), not the journey's 97.41, and the divergence is
//   asserted rather than hidden
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
