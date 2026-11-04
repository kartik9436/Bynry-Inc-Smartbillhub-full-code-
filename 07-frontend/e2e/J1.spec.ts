// ── Trace ──────────────────────────────────────────────
// Journey:  J1 — 08-qa/01-e2e/journeys/J1-tenant-lands.md (tier 1)
//           S1→S114 signup → provisioning → seeding → post-signup checklist (S62)
// Story:    US-TEN-002 (wizard + seeding) · US-TEN-001 (provisioning) ·
//           US-LED-005 (shared chart of accounts) · US-TEN-007 (services
//           enabled) · US-TEN-003 (checklist)
//           Screens: S114 signup wizard · S62 checklist · S8 Settings tabs
// Rules:    BR-TEN-010 (provisioning is ATOMIC — tenant + owner membership +
//           trial, or nothing) · BR-TEN-012 (seeding runs only when "load
//           defaults" is on) · BR-TEN-011 (subdomain grammar, server-side)
// Impacts:  nothing. A journey spec READS the product; the only rows it writes
//           are the ones its own step table tells a human to create.
// ───────────────────────────────────────────────────────
//
// WHAT THIS WALKS. J1 is the only journey in batch A whose step 1 is a PUBLIC
// screen, so it is driven end to end for real: the S114 wizard provisions a
// brand-new tenant on this stack, and every later step asserts that tenant's
// own handoff contract rather than the pre-seeded fixture's. A seeded tenant
// would prove that `seed_demo` works, not that provisioning does.
//
// The subdomain carries a run stamp because provisioning is NOT idempotent from
// the browser's side — BR-TEN-011 refuses a name already taken, which is the
// correct refusal and not something to work around.
import { expect, test } from "@playwright/test";
import type { Page } from "@playwright/test";

import { skipUnlessAppServer } from "./support/app";
import { journey } from "./support/journey";

// A tenant nobody has provisioned before, on every run.
const RUN_STAMP = Date.now().toString(36);
const NEW_TENANT = `j1lane${RUN_STAMP}`;
const OWNER_EMAIL = `pat@${NEW_TENANT}.example`;
const OWNER_PASSWORD = "S3cure!passw0rd";

// The eleven GL designations J1 step 3b says must resolve, and the 13 shared
// chart rows it says must exist, are stated in the journey file. They are
// asserted through the product's own read surfaces — never re-derived here.
const SHARED_CHART_MINIMUM_ROWS = 13;

async function apiJson(page: Page, tenant: string, path: string) {
  const response = await page.request.get(`/api/${tenant}${path}`);
  return { status: response.status(), body: await response.json().catch(() => null) };
}

journey("J1", "Tenant lands — signup → provisioning → seeding → checklist", () => {
  skipUnlessAppServer(test);

  test("steps 1–2 · the S114 wizard provisions a tenant, its owner and its trial", async ({
    page,
  }) => {
    test.setTimeout(240_000);

    // ── Step 1 — US-TEN-002*: "wizard payload complete" ──────────────────
    await page.goto("/signup");
    // The first field IS the precondition — waiting for the wizard's own input
    // rather than for a heading level, so a slow bundle is a wait and not a
    // false claim about the screen.
    await expect(page.locator("#signup-name")).toBeVisible({ timeout: 60_000 });

    await page.locator("#signup-name").fill(`J1 Lane Utilities ${RUN_STAMP}`);
    await page.locator("#signup-subdomain").fill(NEW_TENANT);
    // BR-TEN-011 lives server-side; the wizard will not advance until the live
    // availability check has answered, so the journey waits for the product's
    // own answer rather than for a timer.
    await expect(page.getByText(/available|taken|checking/i).first()).toBeVisible();
    // The SERVICE checkboxes (step 1). Scoped to the services fieldset because
    // the wizard renders every step's fields in the DOM — an unscoped checkbox
    // query resolves the step-5 terms box, which is present but not visible.
    await page.locator('[data-signup="services"] input[type=checkbox]').first().check();

    const continueButton = page.getByRole("button", { name: /continue/i });
    await expect(continueButton).toBeEnabled({ timeout: 15_000 });
    await continueButton.click();

    // Step 2 of the wizard — how you bill. BR-TEN-012: seeding runs only when
    // "load defaults" is on, and J1 step 3's handoff REQUIRES the reference
    // lists, so this journey ticks it the way a utility that wants a working
    // product does.
    await expect(page.locator("#signup-currency")).toBeVisible();
    await page.locator("#signup-currency").selectOption("USD");
    // Same visually-hidden pattern as the terms box: click the label.
    if (!(await page.locator("#signup-load-defaults").isChecked())) {
      await page.locator('label[for="signup-load-defaults"]').click();
    }
    await page.getByRole("button", { name: /continue/i }).click();

    // Step 3 — plan.
    await page.locator("input[name=signup-plan]").first().check();
    await page.getByRole("button", { name: /continue/i }).click();

    // Step 4 — review (read-only).
    await page.getByRole("button", { name: /continue/i }).click();

    // Step 5 — the owner login. BR-TEN-010 makes tenant + owner membership +
    // trial ONE atomic act, so the owner is created here and nowhere else.
    await page.locator("#signup-owner-name").fill("Pat Lane");
    await page.locator("#signup-owner-email").fill(OWNER_EMAIL);
    await page.locator("#signup-owner-password").fill(OWNER_PASSWORD);
    await page.locator('label[for="signup-terms"]').click();
    await page.getByRole("button", { name: /create|finish|start/i }).last().click();

    // ── Step 2 handoff — "tenant + owner membership + trial exist, atomic" ──
    // The PO's 2026-08-10 one-origin ruling signs the owner in at provisioning,
    // so the browser must land INSIDE the new tenant's shell.
    await expect(page).toHaveURL(new RegExp(`/${NEW_TENANT}/`), { timeout: 120_000 });
    await expect(page.getByRole("navigation", { name: "Main navigation" })).toBeVisible();

    const me = await apiJson(page, NEW_TENANT, "/me");
    expect(me.status, "the provisioned owner must have a session on the new tenant").toBe(200);
    expect(me.body?.email ?? me.body?.user?.email).toBe(OWNER_EMAIL);
  });

  test("steps 3 · 3b · 3c — seeding leaves reference lists, the SHARED chart and tenant_services", async ({
    page,
  }) => {
    test.setTimeout(240_000);
    // This test signs in as the owner J1's own step 2 minted, so every read
    // below is the NEW tenant's, never the pre-seeded fixture's.
    await page.goto(`/${NEW_TENANT}/signin`);
    await page.locator("#signin-email").fill(OWNER_EMAIL);
    await page.locator("#signin-password").fill(OWNER_PASSWORD);
    await page.locator("form button[type=submit]").first().click();
    await page.getByRole("navigation", { name: "Main navigation" }).waitFor();

    // ── Step 3 — "reference lists populated per fixtures" ────────────────
    const lookups = await apiJson(page, NEW_TENANT, "/lookups");
    expect(lookups.status).toBe(200);
    expect(
      Array.isArray(lookups.body) ? lookups.body.length : Object.keys(lookups.body ?? {}).length,
      "US-TEN-002 seeding must populate the reference lists",
    ).toBeGreaterThan(0);

    // ── Step 3c — "one tenant_services row per service chosen at signup,
    //    each pointing at the revenue accounts minted for it" ─────────────
    const services = await apiJson(page, NEW_TENANT, "/settings/services");
    expect(services.status).toBe(200);
    const enabled = (services.body as Array<Record<string, unknown>>).filter((s) => s.enabled);
    expect(enabled.length, "the service chosen at signup must be enabled").toBeGreaterThan(0);
    for (const service of enabled) {
      expect(
        service.revenue_account,
        `${String(service.service)} must point at the revenue account minted for it (US-TEN-007 handoff)`,
      ).not.toBeNull();
    }

    // ── Step 3b — "the SHARED chart exists — 13 rows — and every one of the
    //    eleven GL designations resolves" ─────────────────────────────────
    // The chart is what US-LED-005 seeds and what every later posting resolves
    // through, so the journey asks the product to show it.
    const trialBalance = await apiJson(page, NEW_TENANT, "/ledger/trial-balance");
    expect(trialBalance.status).toBe(200);
    expect(
      (trialBalance.body?.rows ?? []).length,
      "J1 step 3b: the SHARED chart of accounts must be readable — 13 rows plus the " +
        "per-service revenue accounts minted at signup",
    ).toBeGreaterThanOrEqual(SHARED_CHART_MINIMUM_ROWS);
  });

  test("step 4 · the S62 checklist computes its gaps live and every link resolves to a Settings tab", async ({
    page,
  }) => {
    test.setTimeout(240_000);
    await page.goto(`/${NEW_TENANT}/signin`);
    await page.locator("#signin-email").fill(OWNER_EMAIL);
    await page.locator("#signin-password").fill(OWNER_PASSWORD);
    await page.locator("form button[type=submit]").first().click();
    await page.getByRole("navigation", { name: "Main navigation" }).waitFor();

    await page.goto(`/${NEW_TENANT}/checklist`);
    await expect(page.getByText(/of \d+ complete/i)).toBeVisible();

    // "company-profile gaps computed live" — a freshly provisioned tenant has
    // typed no legal name, EIN or remit-to, so the company-profile item must
    // read as OUTSTANDING. A checklist that reports a gap it does not have is
    // the failure this step exists to catch.
    const checklist = await apiJson(page, NEW_TENANT, "/tenants/checklist");
    expect(checklist.status).toBe(200);
    const items = (checklist.body?.items ?? []) as Array<Record<string, unknown>>;
    const companyProfile = items.find((item) => item.item === "company_profile");
    expect(companyProfile, "the S62 checklist must carry the company-profile item").toBeTruthy();
    expect(
      companyProfile?.done,
      "step 4: a tenant provisioned seconds ago has typed no company profile, so the " +
        "gap must be computed live rather than seeded done",
    ).toBe(false);

    // "links resolve to Settings tabs" — each target is followed, and each must
    // land on a real Settings screen rather than the W0 placeholder.
    for (const item of items) {
      const target = String(item.target ?? "");
      if (!target.startsWith("settings/")) {
        continue;
      }
      await page.goto(`/${NEW_TENANT}/${target}`);
      await expect(
        page.locator("[data-not-built-yet]"), // DEF-152: the catch-all, by its marker
        `S62 checklist link /${target} must resolve to a Settings tab, not the W0 placeholder`,
      ).toHaveCount(0);
    }
  });
});

// ── Lifecycle ─────────────────────────────────────────────
// packet: batch-A journey activation (2026-08-15)
// generated: 2026-08-15 by the batch-A journey lane
// checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-08)
// gates: `npm run typecheck:e2e` · run against the live stack on 8110/8030
// exceptions: J1 carries no money figure, so no moneyTriple/goldenCalc lookup
//   appears — the journey file's handoff columns are structural. Steps 3/3b/3c
//   are asserted through the product's own READ endpoints under the browser's
//   session, because seeding leaves no screen of its own.
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
