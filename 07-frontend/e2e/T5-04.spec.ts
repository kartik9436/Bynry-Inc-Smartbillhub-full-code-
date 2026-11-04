// ── Trace ──────────────────────────────────────────────
// Journey:  T5-04 — 08-qa/01-e2e/journeys/T5-04-cross-tenant-sweep.md
//           (tier 5 — RLS zero-tolerance; NFR-10 makes ONE leak a release
//           blocker)
// Story:    US-SHL-003 (global search) · US-SHL-006 · US-SHL-008 (list export) ·
//           US-AUD-004 (audit viewer) · US-IDN-001 (sign-in)
//           Screens: S30 · S33 · S25 · S61 · S3
// Guards:   hard rule 1 (no tenant table touched without `app.tenant_id`; RLS
//           FORCE; no cross-tenant queryset) · BR-AUD-007 (RLS FORCE on
//           audit_log — no cross-tenant view even for support) · BR-IDN-029
//           (the same email is a DIFFERENT user per tenant) · BR-SHL-016 ·
//           NFR-10/11/30
// Impacts:  nothing — this spec reads the product. Its ONE write is the tenant B
//           it provisions through the public signup API, because an isolation
//           sweep with only one tenant proves nothing.
// ───────────────────────────────────────────────────────
//
// A fully authenticated staff user of tenant A must get NOTHING of tenant B's —
// not a row, not an export line, not a search hit, not an audit entry, not even
// CONFIRMATION THAT B'S RECORDS EXIST.
import { expect, test } from "@playwright/test";
import type { Page } from "@playwright/test";

import { signIn, skipUnlessAppServer, tenant } from "./support/app";
import { journey } from "./support/journey";

const RUN_STAMP = Date.now().toString(36);
const TENANT_B = `mapleridge${RUN_STAMP}`;
// BR-IDN-029's fixture: the SAME address Dana uses in tenant A, as a separate
// user row in tenant B. That is legal, and step 6 is about proving it.
const SHARED_EMAIL = "dana@brazosbendutilities.com";
const B_PASSWORD = "S3cure!passw0rdB";

async function apiJson(page: Page, tenantSlug: string, path: string) {
  const response = await page.request.get(`/api/${tenantSlug}${path}`);
  return { status: response.status(), body: await response.json().catch(() => null) };
}

async function provisionTenantB(page: Page): Promise<boolean> {
  const created = await page.request.post("/api/tenants", {
    // Exactly `SignupPayload` (07-frontend/src/api/endpoints.ts) — the same body
    // the S114 wizard commits, so tenant B arrives the way a tenant arrives.
    data: {
      name: `Maple Ridge Utilities ${RUN_STAMP}`,
      subdomain: TENANT_B,
      currency: "CAD",
      plan: "starter",
      services: ["water"],
      load_defaults: true,
      owner: { full_name: "Dana Ridge", email: SHARED_EMAIL, password: B_PASSWORD },
    },
  });
  return created.status() < 400;
}

journey("T5-04", "Cross-tenant sweep — RLS zero tolerance", () => {
  skipUnlessAppServer(test);

  test("steps 1–2 · tenant A's session reads and writes NOTHING of tenant B", async ({ page }) => {
    test.setTimeout(420_000);
    await signIn(page);

    const provisioned = await provisionTenantB(page);
    expect(
      provisioned,
      "T5-04 needs a SECOND tenant to sweep against — an isolation suite with one " +
        "tenant proves nothing (NFR-10)",
    ).toBe(true);

    // Sign back in as Dana of tenant A: provisioning signs the caller into the
    // new tenant under the one-origin ruling, and the sweep is about A's session.
    await signIn(page);

    // Step 1 — direct-id reads across every entity of the tier under sweep.
    for (const path of [
      "/accounts",
      "/invoices",
      "/payments",
      "/premises",
      "/units",
      "/reads",
      "/assets",
      "/plans",
      "/audit-log",
      "/ledger/journal-entries",
    ]) {
      const probe = await apiJson(page, TENANT_B, path);
      expect(
        probe.status,
        `hard rule 1: Dana of ${tenant()} must not read ${TENANT_B}${path} — RLS FORCE ` +
          "yields zero rows, and the posture is not-found/empty, never a confirmation",
      ).toBeGreaterThanOrEqual(400);
    }

    // Step 2 — a WRITE against B's surface must not resolve either.
    const write = await page.request.post(`/api/${TENANT_B}/collections/run`, {
      data: { account_ids: ["00000000-0000-4000-8000-000000000000"] },
    });
    expect(
      write.status(),
      "hard rule 1: the write target does not resolve under app.tenant_id = A",
    ).toBeGreaterThanOrEqual(400);
  });

  test("step 5 · the audit viewer shows tenant A's events and no others", async ({ page }) => {
    test.setTimeout(300_000);
    await signIn(page);

    // A's own audit reads normally (step 8's recovery half).
    const mine = await apiJson(page, tenant(), "/audit-log");
    expect(mine.status, "BR-AUD-007: a tenant sees its OWN audit log").toBe(200);
    expect((mine.body?.results ?? []).length, "and it is not empty").toBeGreaterThan(0);

    // B's is invisible even to a System Admin — there is no cross-tenant view.
    const theirs = await apiJson(page, TENANT_B, "/audit-log");
    expect(
      theirs.status,
      "BR-AUD-007: RLS FORCE on audit_log holds — no cross-tenant view exists in v1, " +
        "not even for support",
    ).toBeGreaterThanOrEqual(400);

    await page.goto(`/${tenant()}/audit-log`);
    await expect(page.getByRole("heading", { name: /Audit/i }).first()).toBeVisible({
      timeout: 15_000,
    });
    await expect(
      page.getByText(new RegExp(TENANT_B, "i")),
      "zero tenant-B bytes render anywhere on A's audit screen",
    ).toHaveCount(0);
  });

  test("step 6 · the same email in two tenants is two users; A's password fails on B", async ({
    page,
  }) => {
    test.setTimeout(300_000);

    // BR-IDN-029: sign-in resolves the tenant FIRST, so tenant-A credentials
    // presented on tenant B are simply wrong credentials.
    const attempt = await page.request.post(`/api/${TENANT_B}/auth/session`, {
      data: { email: SHARED_EMAIL, password: "S3cure!passw0rd" },
    });
    expect(
      attempt.status(),
      "BR-IDN-029 / NFR-11: her tenant-A password is worthless on tenant B — the two " +
        "user rows are unrelated, and the posture is invalid-credentials",
    ).toBeGreaterThanOrEqual(400);

    // And her A session is still hers on A (step 8's recovery).
    await signIn(page);
    const me = await apiJson(page, tenant(), "/me");
    expect(me.status).toBe(200);
  });

  test("step 4 · a list export streams tenant-A rows only", async ({ page }) => {
    test.setTimeout(300_000);
    await signIn(page);

    // `resource` is the key BR-SHL-011's export grammar names (the list's own
    // request state), and "invoices" is the S30 list this step exports.
    const exported = await page.request.post("/api/exports", {
      data: { resource: "invoices" },
    });
    expect(
      exported.status(),
      "US-SHL-008: the table-level export must accept a request for a money list — " +
        "IS-9 streams it server-side under RLS",
    ).toBeLessThan(400);
    const body = await exported.text();
    expect(
      body,
      "BR-SHL-016 / hard rule 1: an export carries ONLY tenant-A rows",
    ).not.toContain(TENANT_B);
  });
});

// ── Lifecycle ─────────────────────────────────────────────
// packet: batch-A journey activation (2026-08-15)
// generated: 2026-08-15 by the batch-A journey lane
// checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-08)
// gates: `npm run typecheck:e2e` · run against the live stack on 8110/8030
// exceptions: T5-04 states no money figure, so no moneyTriple lookup appears.
//   Tenant B is PROVISIONED here rather than assumed — the catalog fixture names
//   a maple-ridge tenant that no seeder creates, and a sweep against a tenant
//   that does not exist would pass on 404s that mean "no such tenant" rather
//   than "no such row". Step 3 (global search) is not walked: US-SHL-003's
//   search surface has no endpoint in config/urls.py to probe. Step 7's
//   parameterised re-run over every other tier is out of one lane's scope and is
//   REPORTED rather than claimed.
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
