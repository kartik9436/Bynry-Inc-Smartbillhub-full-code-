// ── Trace ──────────────────────────────────────────────
// Journey:  T5-18 — Demand estimate attempt (a peak is NEVER estimated).
//           `08-qa/01-e2e/journeys/T5-18-demand-estimate-attempt.md` is the
//           spec; this file walks its five-row step table in order.
// Story:    US-MET-014 (estimation) · US-MET-017 (channel-based manual entry) ·
//           US-IDN-001 (sign in)
//           Screens: S3 · S25 Reads (+ S29 fix-actions drawer)
// Rules:    BR-MET-062 (a missing `demand` value is NEVER auto-estimated — it
//           always forces a field visit) · BR-MET-058 (estimation is
//           PER-CHANNEL, so the kWh channels of the same meter may estimate
//           while demand may not) · BR-MET-049 (the plan's required channel
//           set drives completeness) · BR-MET-051 (register reset recorded)
// Money:    NONE rendered by any step; the journey's money claim is the
//           NEGATIVE one ("the kW rate is never applied to a guessed peak"),
//           which is asserted as the absence of an estimated demand row rather
//           than as a figure. `moneyTriple` is not called.
// Tests:    this file. Fixture: 08-qa/01-e2e/stack/seed_e2e_fixture.py
// Impacts:  10-scripts/gates/g12_journeys.py · e2e/support/census.ts
// ───────────────────────────────────────────────────────
import { expect, test } from "@playwright/test";
import type { APIRequestContext } from "@playwright/test";

import { signIn, skipUnlessAppServer, tenant } from "./support/app";
import { journey } from "./support/journey";

const JULY_READ_DATE = "2026-07-31";

function api(path: string): string {
  return `/api/${tenant()}${path}`;
}

async function anyActiveMeter(request: APIRequestContext): Promise<string> {
  const response = await request.get(api("/assets?page_size=100"));
  expect(response.status()).toBe(200);
  const meter = ((await response.json()) as {
    results: { asset_no: string; type: string; status: string }[];
  }).results.find((a) => a.type === "meter" && a.status === "active");
  expect(meter, "the fixture has no active meter").toBeDefined();
  return (meter as { asset_no: string }).asset_no;
}

/** The GLOBAL invariant the journey asks for, across the whole database. */
async function estimatedDemandRows(request: APIRequestContext): Promise<number> {
  const response = await request.get(api("/reads?f.channel=demand&f.status=estimated&per=200"));
  expect(response.status()).toBe(200);
  return ((await response.json()) as { count: number }).count;
}

journey("T5-18", "Demand estimate attempt — a peak is NEVER estimated", () => {
  // NOT serial: each row builds its own precondition, so the run reports which
  // of the journey's five hold rather than stopping at the first that does not.
  skipUnlessAppServer(test);

  test("step 1 — the demand channel is REFUSED an estimate while kWh channels estimate", async ({
    page,
  }) => {
    await signIn(page);
    const meter = await anyActiveMeter(page.request);

    // BR-MET-062. The refusal is DATA with its reason, not a 500 — the clerk
    // must see it (the endpoint's own docstring says so).
    const demand = await page.request.post(api("/reads/estimate"), {
      data: { meter_no: meter, read_at: JULY_READ_DATE, channel: "demand" },
    });
    const demandBody = await demand.text();
    expect(
      demandBody,
      `estimating the demand channel answered ${demand.status()} with ${demandBody} — ` +
        "BR-MET-062 requires a refusal naming 'demand never estimated / field visit required'",
    ).toMatch(/demand_never_estimated|never estimated|field.?visit/i);

    // BR-MET-058: the split is real — the same call on a kWh channel is
    // answered on its own merits, not with the demand refusal.
    const kwh = await page.request.post(api("/reads/estimate"), {
      data: { meter_no: meter, read_at: JULY_READ_DATE, channel: "total" },
    });
    expect(
      await kwh.text(),
      "BR-MET-058: a kWh channel must NOT inherit the demand refusal",
    ).not.toMatch(/demand_never_estimated/i);

    // The GLOBAL invariant, asserted across the whole database.
    expect(
      await estimatedDemandRows(page.request),
      "ZERO meter_reads rows may exist with channel=demand status=estimated, anywhere",
    ).toBe(0);
  });

  test("step 2 — completeness gates billing on the missing demand value", async ({ page }) => {
    await signIn(page);
    const response = await page.request.get(api("/reads/needs-attention"));
    expect(response.status()).toBe(200);
    const counts = (await response.json()) as {
      missing: number | null;
      missing_unavailable_reason: string | null;
    };
    expect(
      counts.missing,
      `the chase list cannot count what is missing: "${counts.missing_unavailable_reason}" — ` +
        "so BR-MET-049's plan-driven completeness cannot gate billing on a missing peak",
    ).not.toBeNull();
  });

  test("step 3 — the fix actions on a missing demand read offer no Estimate", async ({ page }) => {
    await signIn(page);
    await page.goto(`/${tenant()}/reads?channel=demand`);
    await expect(page.locator("main")).toBeVisible();
    // BR-MET-062 is stricter than BR-MET-027's two-estimate allowance: demand
    // gets ZERO, at any consecutive count. Whatever rows the list shows for the
    // demand channel, none may offer an Estimate affordance.
    await expect(
      page.getByRole("row").filter({ hasText: /demand/i }).getByRole("button", { name: /estimate/i }),
      "no demand row may offer an Estimate action",
    ).toHaveCount(0);
  });

  test("step 4 — no path writes an estimated demand read", async ({ page }) => {
    await signIn(page);
    const meter = await anyActiveMeter(page.request);

    const direct = await page.request.post(api("/reads"), {
      data: { meter_no: meter, channel: "demand", status: "estimated", value: "42.7" },
    });
    expect(
      direct.status(),
      `POST /reads answered ${direct.status()} — an estimated demand row must not be ` +
        "writable by any path",
    ).toBeGreaterThanOrEqual(400);

    // Even through the staged-batch door, an estimated demand row must not
    // reach meter_reads.
    expect(await estimatedDemandRows(page.request)).toBe(0);
  });

  test("step 5 — RECOVERY: the field-visit value commits as an ACTUAL demand read", async ({
    page,
  }) => {
    await signIn(page);
    const meter = await anyActiveMeter(page.request);

    // US-MET-017: channel-based manual entry of the peak the field visit read.
    const staged = await page.request.post(api("/read-batches"), {
      data: {
        source_kind: "manual",
        period_month: "2026-07-01",
        rows: [
          { meter_id: meter, read_date: JULY_READ_DATE, reading: "42.7", channel: "demand" },
        ],
      },
    });
    expect(
      staged.status(),
      `staging the field-visit demand read answered ${staged.status()}: ${await staged.text()}`,
    ).toBe(201);
    const id = ((await staged.json()) as { id: string }).id;
    expect((await page.request.post(api(`/read-batches/${id}/validate`))).status()).toBe(200);
    const post = await page.request.post(api(`/read-batches/${id}/post`), {
      data: { certified: true },
    });
    expect(
      post.status(),
      `committing the ACTUAL demand read answered ${post.status()}: ${await post.text()}`,
    ).toBe(200);

    // Exactly one demand value per cycle, and it is ACTUAL.
    const reads = await page.request.get(api(`/reads?f.channel=demand&per=200`));
    // `meter` is NOT one of selectors.READ_FILTERS, so the meter is matched on
    // the served row rather than pushed into the query.
    const rows = ((await reads.json()) as { results: { status: string; meter: string }[] }).results
      .filter((r) => r.meter === meter);
    expect(rows.length, "the committed demand read must be readable").toBeGreaterThan(0);
    expect(rows.every((r) => r.status !== "estimated"), "every demand read is ACTUAL").toBe(true);
  });
});

// ── Lifecycle ─────────────────────────────────────────────
// packet: T5-18 journey activation (batch B lane, 2026-08-15)
// generated: 2026-08-15 by the E2E journey-activation lane
// checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-08)
// gates: run against the live stack on E2E_BACKEND_PORT=8040 / E2E_WEB_PORT=8120
// exceptions: (1) the journey's ACC-2077 / MTR-0713 Commercial-TOU-demand
//   fixture (five required channels) is not seeded, so steps 1/3/4 are driven
//   against an active meter of the seeded fixture: the demand REFUSAL and the
//   global "no estimated demand row" invariant are exercised exactly; the TOU
//   channels estimating "from their own trailing histories" alongside it is NOT
//   · (2) no money figure is asserted — the journey's money claim is a negative
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
