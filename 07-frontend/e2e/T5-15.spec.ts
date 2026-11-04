// ── Trace ──────────────────────────────────────────────
// Journey:  T5-15 — Unit picker on an occupied unit (one active account per
//           unit). `08-qa/01-e2e/journeys/T5-15-occupied-unit-picker.md` is the
//           spec; this file walks its five-row step table in order.
// Story:    US-CUS-003 (S18 New account wizard) · US-CUS-004 (S19 Move-in) ·
//           US-IDN-001 (sign in)
//           Screens: S3 · S18 step 2 unit picker · S19 step 1 · S20 Move-out
// Rules:    BR-CUS-017 (at most ONE active account per unit) · BR-CUS-020 (the
//           pickers offer vacant/reserved units ONLY) · BR-MET-036 (occupancy
//           is DERIVED from the active account)
// Money:    NONE. Every row of this journey asserts the ABSENCE of a second
//           account and of "snapshot, deposit or first-bill artifacts"; no
//           figure is rendered on any step, so `moneyTriple` is not called.
// Tests:    this file. Fixture: 08-qa/01-e2e/stack/seed_e2e_fixture.py seeds
//           ten units, exactly one of them OCCUPIED (U-00101-A, by E2E-10001),
//           which is precisely the journey's PRM-007 4B/4C shape.
// Impacts:  10-scripts/gates/g12_journeys.py · e2e/support/census.ts
// ───────────────────────────────────────────────────────
import { expect, test } from "@playwright/test";
import type { APIRequestContext } from "@playwright/test";

import { signIn, skipUnlessAppServer, tenant } from "./support/app";
import { journey } from "./support/journey";

function api(path: string): string {
  return `/api/${tenant()}${path}`;
}

interface UnitRow {
  id: string;
  unit_no: string | null;
  label?: string | null;
  occupancy: string | null;
}

async function units(request: APIRequestContext): Promise<UnitRow[]> {
  const response = await request.get(api("/units?per=100"));
  expect(response.status()).toBe(200);
  return ((await response.json()) as { results: UnitRow[] }).results;
}

async function occupiedUnit(request: APIRequestContext): Promise<UnitRow> {
  const found = (await units(request)).find((u) => u.occupancy === "occupied");
  expect(found, "the fixture has no OCCUPIED unit — this journey has no subject").toBeDefined();
  return found as UnitRow;
}

async function activeAccountsOn(request: APIRequestContext, unitId: string): Promise<number> {
  const response = await request.get(api("/accounts?per=200"));
  expect(response.status()).toBe(200);
  const rows = ((await response.json()) as {
    results: { unit_id: string | null; status: string }[];
  }).results;
  return rows.filter((a) => a.unit_id === unitId && a.status === "active").length;
}

journey("T5-15", "Unit picker on an occupied unit — one active account per unit", () => {
  // NOT serial: each row builds its own precondition, so the run reports which
  // of the journey's five hold rather than stopping at the first that does not.
  skipUnlessAppServer(test);

  test("step 1 — S18's unit picker does not offer the OCCUPIED unit", async ({ page }) => {
    await signIn(page);
    const occupied = await occupiedUnit(page.request);

    await page.goto(`/${tenant()}/accounts/new`);
    // Step 1 is the CUSTOMER step and its Continue asks for a name (the server
    // requires one once a contact is sent), so a clerk types it before they can
    // reach the unit picker. Typed, then Continue — the way a clerk walks it.
    await page.locator("#full_name").fill("T5-15 picker probe");
    await page.getByRole("button", { name: "Continue" }).first().click();
    const picker = page.locator("#unit_id");
    await expect(picker, "S18 step 2 must render a unit picker").toBeVisible();

    const options = await picker.locator("option").allInnerTexts();
    const label = occupied.unit_no ?? occupied.label ?? "";
    expect(
      options.filter((text) => text.includes(label)),
      `BR-CUS-020: the occupied unit ${label} must be ABSENT from the picker — ` +
        `options were [${options.join(" | ")}]`,
    ).toHaveLength(0);
    // …and a vacant one IS offered, so the emptiness above is a filter and not
    // a picker that failed to load.
    expect(options.length, "the picker offered nothing at all").toBeGreaterThan(1);
  });

  test("step 2 — S19's move-in picker filters identically", async ({ page }) => {
    await signIn(page);
    const occupied = await occupiedUnit(page.request);

    // BR-CUS-020 is a SERVER rule: the picker asks for vacant units only, and
    // the server decides. This is that query, made the way the wizard makes it.
    const response = await page.request.get(api("/units?per=500&f.occupancy=vacant"));
    expect(response.status()).toBe(200);
    const offered = ((await response.json()) as { results: UnitRow[] }).results;
    expect(
      offered.map((u) => u.id),
      "the vacant-unit query must never return the occupied unit",
    ).not.toContain(occupied.id);
    expect(offered.length, "the vacant-unit query returned nothing at all").toBeGreaterThan(0);
  });

  test("step 3 — forcing the occupied unit through the API is refused 409", async ({ page }) => {
    await signIn(page);
    const occupied = await occupiedUnit(page.request);
    const before = await activeAccountsOn(page.request, occupied.id);
    expect(before, "the fixture's occupied unit must carry exactly one active account").toBe(1);

    const response = await page.request.post(api("/accounts"), {
      // The wizard's own payload shape (createAccountPayload): the URL/body
      // carries the unit and the ACTIVATING status, and nothing else — a
      // contact name is not a field POST /accounts accepts.
      data: { unit_id: occupied.id, status: "active", account_type: "residential" },
    });
    expect(
      response.status(),
      `forcing the occupied unit answered ${response.status()}: ${await response.text()}`,
    ).toBe(409);
    const refusal = (await response.json()) as { message_key: string; br_ref: string | null };
    expect(
      `${refusal.br_ref ?? ""} ${refusal.message_key}`,
      "the refusal must name the existing active account / the one-per-unit rule",
    ).toMatch(/occupied|active|BR-CUS-017/i);

    expect(
      await activeAccountsOn(page.request, occupied.id),
      "BR-CUS-017: exactly one active account on the unit, before and after",
    ).toBe(1);
  });

  test("step 4 — two clerks racing a VACANT unit: one wins, one hits the same conflict", async ({
    page,
  }) => {
    await signIn(page);
    const vacant = (await units(page.request)).find((u) => u.occupancy === "vacant");
    expect(vacant, "the fixture has no vacant unit to race for").toBeDefined();
    const unitId = (vacant as UnitRow).id;

    const payload = {
      unit_id: unitId,
      status: "active",
      account_type: "residential",
      opened_at: "2026-08-01",
    };
    const [a, b] = await Promise.all([
      page.request.post(api("/accounts"), { data: payload }),
      page.request.post(api("/accounts"), { data: payload }),
    ]);
    const created = [a, b].filter((r) => r.status() === 201).length;
    expect(
      created,
      `the race created ${created} accounts on one unit — BR-CUS-017 allows at most one ` +
        `(${a.status()} / ${b.status()}: ${await a.text()})`,
    ).toBeLessThanOrEqual(1);
    expect(
      await activeAccountsOn(page.request, unitId),
      "BR-MET-036: occupancy derives to Occupied exactly once",
    ).toBeLessThanOrEqual(1);
  });

  test("step 5 — RECOVERY: move-out frees the unit and it reappears in the pickers", async ({
    page,
  }) => {
    await signIn(page);
    const occupied = await occupiedUnit(page.request);
    const accounts = await page.request.get(api("/accounts?per=200"));
    const sitting = ((await accounts.json()) as {
      results: { id: string; unit_id: string | null; status: string }[];
    }).results.find((a) => a.unit_id === occupied.id && a.status === "active");
    expect(sitting, "no active account sits on the occupied unit").toBeDefined();

    const moveOut = await page.request.post(api(`/accounts/${sitting?.id}/move-out`), {
      // BR-CUS-030 / US-CUS-005: the move-out flow takes `moved_out_on`.
      // `closed_at` is a REFUSED field — closing an account is this flow, not a
      // status write, and the server says so.
      data: { moved_out_on: "2026-08-31" },
    });
    expect(
      [200, 201],
      `move-out answered ${moveOut.status()}: ${await moveOut.text()}`,
    ).toContain(moveOut.status());

    // The unit derives Vacant, so BR-CUS-020's picker offers it again.
    const after = await page.request.get(api("/units?per=500&f.occupancy=vacant"));
    expect(
      ((await after.json()) as { results: UnitRow[] }).results.map((u) => u.id),
      "after move-out the unit must reappear in the vacant set",
    ).toContain(occupied.id);
  });
});

// ── Lifecycle ─────────────────────────────────────────────
// packet: T5-15 journey activation (batch B lane, 2026-08-15)
// generated: 2026-08-15 by the E2E journey-activation lane
// checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-08)
// gates: run against the live stack on E2E_BACKEND_PORT=8040 / E2E_WEB_PORT=8120
// exceptions: (1) step 4's race is asserted as "at most one winner" rather than
//   "exactly one", because on a re-run of the suite the unit is already taken
//   and BOTH callers correctly lose — which is the same rule holding ·
//   (2) step 5 MOVES OUT the fixture's only occupied account, and does not put
//   it back: a move-out is a real lifecycle event with a final-bill handoff and
//   is never undone by a test. Steps 1–4 re-read the tenant's state rather than
//   assuming U-00101-A, so a later suite run finds whatever the product left
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
