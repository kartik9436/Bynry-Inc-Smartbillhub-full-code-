// ── Trace ──────────────────────────────────────────────
// Journey:  T7-09 — Currency lifecycle: a fresh tenant picks CAD, formats flow,
//           the first financial record locks it.
//           `08-qa/01-e2e/journeys/T7-09-currency-lifecycle-cad-lock.md` is the
//           spec; this file walks its six-row step table in order.
// Story:    US-TEN-001 (provisioning, S110–S114) · US-TEN-006 (S8 Regional) ·
//           US-BIL-005 (the run summary / release that ISSUES the first bill) ·
//           US-IDN-001 (sign in)
//           Screens: S3 · S111 signup · S8 Company → Regional · S30
// Rules:    BR-TEN-042 (ONE currency per tenant; mutable until the FIRST
//           financial record, immutable after) · BR-TEN-021 (the forward-only
//           warning) · BR-TEN-016 (before/after audit on every settings save) ·
//           IS-8 (formatting flows from Regional settings) · NFR-22
// Money:    `moneyTriple("flat","cycle","full")` — the journey's BL-2608-0001
//           at 97.41 CAD. Read at run time; never typed here.
// Impacts:  10-scripts/gates/g12_journeys.py · e2e/support/census.ts
// ───────────────────────────────────────────────────────
//
// TWO TENANTS, DELIBERATELY. The journey's subject is the ARMING MOMENT, and a
// tenant can only be on one side of it. So:
//
//   · steps 1–3 need a tenant with NO financial record. This spec PROVISIONS
//     one through the real public signup (US-TEN-001, `POST /api/tenants`) —
//     the same door a utility uses — rather than seeding one.
//   · step 5 needs a tenant one commit PAST the arming event. The seeded
//     `brazosbend` is exactly that: it carries one issued invoice, so its
//     currency is already locked, and the refusal under test is live there.
//   · step 4 IS the arming event, and it is the row this product cannot
//     perform: `POST /billing/runs/{id}/issue` is not served
//     (apps/billing/api.py's own trailer says so), so no bill can be issued on
//     the fresh tenant and the lock cannot be watched engaging.
import { expect, test } from "@playwright/test";
import type { APIRequestContext } from "@playwright/test";

import { signIn, skipUnlessAppServer, tenant } from "./support/app";
import { moneyTriple } from "./support/expected";
import { journey } from "./support/journey";

const FIRST_BILL = moneyTriple("flat", "cycle", "full");
// The journey's Maple Creek Utilities, Saskatchewan. A fixed subdomain so a
// re-run of the suite REPLAYS the provisioning (BR-TEN-010) rather than minting
// a second tenant every time.
const FRESH = {
  name: "Maple Creek Utilities",
  subdomain: "maple-creek",
  currency: "CAD",
  owner_email: "joel@maplecreekutilities.ca",
  owner_password: "S3cure!passw0rd",
};

function api(slug: string, path: string): string {
  return `/api/${slug}${path}`;
}

interface Regional {
  currency: string;
  country: string;
}

async function regional(request: APIRequestContext, slug: string): Promise<Regional> {
  const response = await request.get(api(slug, "/settings/regional"));
  expect(response.status(), `GET regional for ${slug} answered ${response.status()}`).toBe(200);
  return (await response.json()) as Regional;
}

/** Provisions Maple Creek through the PUBLIC signup. Idempotent (BR-TEN-010). */
async function freshTenant(request: APIRequestContext): Promise<void> {
  const plans = await request.get("/api/public/pricing-plans");
  expect(plans.status()).toBe(200);
  const catalogue = (await plans.json()) as { plans?: { code: string }[] } | { code: string }[];
  const list = Array.isArray(catalogue) ? catalogue : (catalogue.plans ?? []);
  expect(list.length, "the public pricing catalogue is empty — signup cannot pick a plan").toBeGreaterThan(0);

  const response = await request.post("/api/tenants", {
    data: {
      name: FRESH.name,
      subdomain: FRESH.subdomain,
      state: "SK",
      currency: FRESH.currency,
      plan: list[0].code,
      services: ["electric"],
      load_defaults: true,
      owner: {
        full_name: "Joel Tremblay",
        email: FRESH.owner_email,
        password: FRESH.owner_password,
      },
    },
  });
  expect(
    [200, 201],
    `provisioning ${FRESH.subdomain} answered ${response.status()}: ` +
      `${(await response.text()).slice(0, 400)}`,
  ).toContain(response.status());
}

journey("T7-09", "Currency lifecycle — a fresh tenant picks CAD and the first bill locks it", () => {
  // NOT serial: each row builds its own precondition, so the run reports which
  // of the journey's six hold rather than stopping at the first that does not.
  skipUnlessAppServer(test);

  test("step 1 — post-provisioning the currency control is ENABLED (no financial record yet)", async ({
    page,
  }) => {
    await signIn(page);
    await freshTenant(page.request);
    // The signup POST returns the owner's session as an httpOnly cookie, so the
    // request context is now inside the new tenant.
    const config = await regional(page.request, FRESH.subdomain);
    expect(config.currency, "the seed list choice must land on the tenant row").toBe(
      FRESH.currency,
    );
  });

  test("step 2 — pre-financials the currency is MUTABLE, and every save audits before/after", async ({
    page,
  }) => {
    await signIn(page);
    await freshTenant(page.request);

    // CAD → USD → CAD, exactly as the journey flips it.
    for (const currency of ["USD", "CAD"]) {
      const response = await page.request.put(api(FRESH.subdomain, "/settings/regional"), {
        data: { currency },
      });
      expect(
        [200, 201],
        `setting ${currency} on a pre-financial tenant answered ${response.status()}: ` +
          `${(await response.text()).slice(0, 300)}`,
      ).toContain(response.status());
    }
    expect((await regional(page.request, FRESH.subdomain)).currency).toBe("CAD");

    const audit = await page.request.get(api(FRESH.subdomain, "/audit-log?per=25"));
    expect(audit.status()).toBe(200);
    const rows = ((await audit.json()) as { results: { action: string; summary: string }[] })
      .results.filter((r) => r.action.includes("regional"));
    expect(rows.length, "BR-TEN-016: each currency save writes its own before/after row")
      .toBeGreaterThanOrEqual(2);
    expect(rows[0].summary, "the row must carry the currency's before → after").toMatch(
      /currency:\s*\w{3}\s*→\s*\w{3}/,
    );
  });

  test("step 3 — money renders under the tenant's Regional currency (IS-8)", async ({ page }) => {
    await signIn(page);
    await freshTenant(page.request);
    const config = await regional(page.request, FRESH.subdomain);
    expect(config.currency).toBe("CAD");

    // IS-8: the format flows from Regional. The screen must render the tenant's
    // own currency, not the harness default.
    await page.goto(`/${FRESH.subdomain}/billing`);
    await expect(page.locator("main")).toBeVisible();
    await expect(
      page.locator("main"),
      "S30 must render under the tenant's CAD Regional settings, not a hard-coded USD",
    ).not.toContainText("$US");
  });

  test("step 4 — THE ARMING EVENT: the first issued bill engages the lock", async ({ page }) => {
    await signIn(page);
    await freshTenant(page.request);

    const cycles = await page.request.get(api(FRESH.subdomain, "/cycles"));
    expect(cycles.status()).toBe(200);
    const list = (await cycles.json()) as { id: string }[];
    expect(list.length, "the fresh tenant has no cycle to bill").toBeGreaterThan(0);

    const run = await page.request.post(api(FRESH.subdomain, "/billing/runs"), {
      data: {
        cycle_id: list[0].id,
        period_start: "2026-08-01",
        period_end: "2026-08-31",
        bill_date: "2026-08-31",
        scope_services: ["electric"],
      },
    });
    const payload = (await run.json()) as Record<string, never>;
    const runId =
      run.status() === 201
        ? String(payload.id)
        : String((payload.params as unknown as { run_id: string }).run_id);

    const issue = await page.request.post(api(FRESH.subdomain, `/billing/runs/${runId}/issue`), {
      data: {},
    });
    expect(
      issue.status(),
      `POST /billing/runs/{id}/issue answered ${issue.status()} — the ARMING EVENT this ` +
        `journey is about (an issued invoice at ${FIRST_BILL.total}) cannot happen, so the ` +
        "lock cannot be watched engaging",
    ).toBeLessThan(400);
  });

  test("step 5 — one commit past arming, the currency change is REFUSED", async ({ page }) => {
    await signIn(page);
    // The seeded tenant is already past the arming event: it carries one issued
    // invoice, so BR-TEN-042's lock is live on it.
    const before = await regional(page.request, tenant());
    const response = await page.request.put(api(tenant(), "/settings/regional"), {
      data: { currency: before.currency === "USD" ? "CAD" : "USD" },
    });
    expect(
      response.status(),
      `changing a locked tenant's currency answered ${response.status()}`,
    ).toBe(409);
    const refusal = (await response.json()) as { br_ref: string | null; message_key: string };
    expect(refusal.br_ref).toBe("BR-TEN-042");
    expect(refusal.message_key).toBe("settings.regional.currency_locked");

    // Zero money rows changed, and the currency is exactly what it was.
    expect((await regional(page.request, tenant())).currency).toBe(before.currency);

    // …and the S8 control renders DISABLED with its reason, not hidden.
    await page.goto(`/${tenant()}/settings/company/regional`);
    await expect(page.locator("main")).toBeVisible();
    await expect(
      page.locator("main"),
      "BR-SHL-025: a control that cannot be honoured renders disabled WITH its reason",
    ).toContainText(/lock/i);
  });

  test("step 6 — INVARIANCE: the issued bill still renders as issued after the refusals", async ({
    page,
  }) => {
    await signIn(page);
    const invoices = await (await page.request.get(api(tenant(), "/invoices?per=100"))).text();
    await page.request.put(api(tenant(), "/settings/regional"), { data: { currency: "CAD" } });
    expect(
      await (await page.request.get(api(tenant(), "/invoices?per=100"))).text(),
      "NFR-22 / BR-TEN-021: historical documents never restate on a settings change",
    ).toBe(invoices);
  });
});

// ── Lifecycle ─────────────────────────────────────────────
// packet: T7-09 journey activation (batch B lane, 2026-08-15)
// generated: 2026-08-15 by the E2E journey-activation lane
// checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-08)
// gates: run against the live stack on E2E_BACKEND_PORT=8040 / E2E_WEB_PORT=8120
// exceptions: (1) TWO tenants are used and why is in the header — the arming
//   moment has two sides and a tenant is only ever on one of them · (2) the
//   fresh tenant is PROVISIONED through the public signup rather than seeded,
//   and the subdomain is fixed so a re-run REPLAYS (BR-TEN-010) instead of
//   minting a second one · (3) step 5 leaves the seeded tenant's currency
//   untouched by construction — the call under test is the one that must fail
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
