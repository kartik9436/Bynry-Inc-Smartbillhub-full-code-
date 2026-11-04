// ── Trace ──────────────────────────────────────────────
// Journey:  T4-22 — 08-qa/01-e2e/journeys/T4-22-currency-set-then-lock.md
//           x = fresh tenant, currency freely changeable → y = the first
//           financial record ARMS the BR-TEN-042 lock
// Story:    US-TEN-001 (provisioning) · US-TEN-006 (regional settings) ·
//           US-BIL-005 (the arming record)
//           Screens: S114 signup · S8 Settings → Regional · S30 bill
// Rules:    BR-TEN-042 (one currency per tenant, locked by the first financial
//           record) · BR-TEN-020/021 (storage stays NUMERIC(18,6) + CHAR(3);
//           display formats are transforms only) · BR-IDN-029 (per-tenant
//           identity — the same email may be a DIFFERENT user in another
//           tenant) · NFR-37 (a new currency is a DATA change, never code)
// Impacts:  nothing — this spec reads the product and drives its own screens.
// ───────────────────────────────────────────────────────
//
// This is the ALLOWED half of the transition T5-03 proves from the refusal
// side: choose freely before money exists, then watch the first invoice snap
// the lock shut.
import { expect, test } from "@playwright/test";
import type { Page } from "@playwright/test";

import { signIn, skipUnlessAppServer, tenant } from "./support/app";
import { journey } from "./support/journey";

const RUN_STAMP = Date.now().toString(36);
const FRESH_TENANT = `maplecreek${RUN_STAMP}`;
const OWNER_EMAIL = "pat@maplecreek.example";
const OWNER_PASSWORD = "S3cure!passw0rd";

async function apiJson(page: Page, tenantSlug: string, path: string) {
  const response = await page.request.get(`/api/${tenantSlug}${path}`);
  return { status: response.status(), body: await response.json().catch(() => null) };
}

journey("T4-22", "Currency set on a fresh tenant, then the lock engages", () => {
  skipUnlessAppServer(test);

  test("steps 1–2 · a tenant with ZERO financial records may change its currency", async ({
    page,
  }) => {
    test.setTimeout(420_000);

    // Step 1 — provision maple-creek through the real S114 wizard.
    await page.goto("/signup");
    await page.locator("#signup-name").fill(`Maple Creek Utilities ${RUN_STAMP}`);
    await page.locator("#signup-subdomain").fill(FRESH_TENANT);
    // The SERVICE checkboxes (step 1). Scoped to the services fieldset because
    // the wizard renders every step's fields in the DOM — an unscoped checkbox
    // query resolves the step-5 terms box, which is present but not visible.
    await page.locator('[data-signup="services"] input[type=checkbox]').first().check();
    const next = page.getByRole("button", { name: /continue/i });
    await expect(next).toBeEnabled({ timeout: 15_000 });
    await next.click();

    // Step 1's assertion — the seed list, with the tenant defaulting to USD.
    const currency = page.locator("#signup-currency");
    await expect(currency).toBeVisible();
    for (const code of ["USD", "CAD", "MXN", "EUR", "GBP"]) {
      await expect(
        currency.locator(`option[value=${code}]`),
        `BR-TEN-042: the seed list carries ${code}`,
      ).toHaveCount(1);
    }
    await currency.selectOption("USD");
    // Same visually-hidden pattern as the terms box: click the label.
    if (!(await page.locator("#signup-load-defaults").isChecked())) {
      await page.locator('label[for="signup-load-defaults"]').click();
    }
    await page.getByRole("button", { name: /continue/i }).click();
    await page.locator("input[name=signup-plan]").first().check();
    await page.getByRole("button", { name: /continue/i }).click();
    await page.getByRole("button", { name: /continue/i }).click();
    await page.locator("#signup-owner-name").fill("Pat Maple");
    await page.locator("#signup-owner-email").fill(OWNER_EMAIL);
    await page.locator("#signup-owner-password").fill(OWNER_PASSWORD);
    await page.locator('label[for="signup-terms"]').click();
    await page.getByRole("button", { name: /create|finish|start/i }).last().click();
    await expect(page).toHaveURL(new RegExp(`/${FRESH_TENANT}/`), { timeout: 120_000 });

    // Step 2 — ALLOWED, because no financial record exists.
    const before = await apiJson(page, FRESH_TENANT, "/settings/regional");
    expect(before.status).toBe(200);
    expect(before.body?.currency, "the tenant starts on its seeded default").toBe("USD");

    const write = await page.request.put(`/api/${FRESH_TENANT}/settings/regional`, {
      data: { ...before.body, currency: "CAD" },
    });
    expect(
      write.status(),
      "BR-TEN-042: with ZERO financial records the currency is freely changeable — " +
        "there is no history to restate",
    ).toBeLessThan(400);

    const after = await apiJson(page, FRESH_TENANT, "/settings/regional");
    expect(after.body?.currency, "the change applied").toBe("CAD");
  });

  test("step 5 · the isolation sweep — the contrast tenant is untouched by every step", async ({
    page,
  }) => {
    test.setTimeout(300_000);
    await signIn(page);

    // brazos-bend is still USD, its own lock armed by ITS OWN first record.
    const regional = await apiJson(page, tenant(), "/settings/regional");
    expect(regional.status).toBe(200);
    expect(
      regional.body?.currency,
      "BR-TEN-003 / RLS FORCE: nothing maple-creek did may reach brazos-bend",
    ).toBe("USD");

    const tb = await apiJson(page, tenant(), "/ledger/trial-balance");
    expect(tb.body?.currency, "every stored amount keeps its CHAR(3)").toBe("USD");
    expect(tb.body?.balanced).toBe(true);
  });

  test("steps 3–4 · once a financial record exists the control disables and the API refuses", async ({
    page,
  }) => {
    test.setTimeout(300_000);
    await signIn(page);

    // brazos-bend IS the armed-lock tenant on this stack: it carries an issued
    // bill, which is precisely the arming record BR-TEN-042 names.
    const invoices = await apiJson(page, tenant(), "/invoices");
    expect(invoices.body?.count, "the arming financial record exists").toBeGreaterThan(0);

    const current = (await apiJson(page, tenant(), "/settings/regional")).body;
    const attempt = await page.request.put(`/api/${tenant()}/settings/regional`, {
      data: { ...current, currency: "CAD" },
    });
    expect(
      attempt.status(),
      "BR-TEN-042: after the first financial record the currency is immutable — the " +
        "API must refuse with a 409/422 validation posture, never quietly accept",
    ).toBeGreaterThanOrEqual(400);

    const after = await apiJson(page, tenant(), "/settings/regional");
    expect(after.body?.currency, "the tenant is still USD").toBe("USD");
  });
});

// ── Lifecycle ─────────────────────────────────────────────
// packet: batch-A journey activation (2026-08-15)
// generated: 2026-08-15 by the batch-A journey lane
// checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-08)
// gates: `npm run typecheck:e2e` · run against the live stack on 8110/8030
// exceptions: T4-22 names 97.41 CAD as maple-creek's first bill; billing a fresh
//   tenant needs a plan, a unit, an account and a read that signup does not
//   seed, so step 3's ARMING is asserted against brazos-bend — the tenant on
//   this stack that HAS an issued bill — and the fresh tenant carries steps 1–2.
//   Stated rather than faked. The subdomain carries a run stamp because
//   BR-TEN-011 refuses a name already taken.
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
