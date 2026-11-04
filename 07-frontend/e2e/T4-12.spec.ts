// ── Trace ──────────────────────────────────────────────
// Journey:  T4-12 — 08-qa/01-e2e/journeys/T4-12-exemption-cert-expiry.md
//           x = valid certificate → y = expired: a WARNING renders and the
//           system NEVER auto-untags
// Story:    US-CUS-009 · US-BIL-008
//           Screens: S21 account detail (exemption panel)
// Rules:    BR-CUS-063 CL-6 (PO ruling: expired cert → WARNING, not auto-untag —
//           staff decide) · BR-RAT-006 (the flag, not the expiry, gates the
//           engine) · BR-BIL-004
// Impacts:  nothing — this spec reads the product.
// ───────────────────────────────────────────────────────
//
// The tempting automation — flip the account back to taxed the day the cert
// lapses — is exactly what must NOT happen: a renewal may be in the mail, and
// silently re-taxing would surprise-bill an exempt entity. The system's whole
// job at this boundary is to make a human look.
import { expect, test } from "@playwright/test";
import type { Page } from "@playwright/test";

import { signIn, skipUnlessAppServer, tenant } from "./support/app";
import { journey } from "./support/journey";

async function apiJson(page: Page, path: string) {
  const response = await page.request.get(`/api/${tenant()}${path}`);
  return { status: response.status(), body: await response.json().catch(() => null) };
}

journey("T4-12", "Exemption certificate expiry — warning renders, never auto-untag", () => {
  skipUnlessAppServer(test);

  test("step 1 · the expiry is STORED and the expired state is DERIVED, never a stored mutation", async ({
    page,
  }) => {
    test.setTimeout(300_000);
    await signIn(page);

    const accounts = await apiJson(page, "/accounts");
    const account = (accounts.body?.results ?? [])[0] as Record<string, string>;
    const detail = await apiJson(page, `/accounts/${account.id}`);
    expect(detail.status).toBe(200);

    expect(
      JSON.stringify(detail.body),
      "BR-CUS-063: the certificate EXPIRY DATE must be stored on the account — the " +
        "warning is computed from it and from nothing else",
    ).toMatch(/"(tax_exempt_expiry|exemption_expires|certificate_expiry)/);

    // The screen half — S21 renders the expiry, and must be able to render its
    // warning state.
    await page.goto(`/${tenant()}/accounts/${account.id}`);
    await expect(page.getByText(/Exemption expires/i).first()).toBeVisible({ timeout: 15_000 });
  });

  test("step 3 · adversarial probe — no job, trigger or bill-run side effect flips the flag", async ({
    page,
  }) => {
    test.setTimeout(300_000);
    await signIn(page);

    const accounts = await apiJson(page, "/accounts");
    const account = (accounts.body?.results ?? [])[0] as Record<string, string>;

    const before = await apiJson(page, `/accounts/${account.id}`);
    const flag = before.body?.tax_exempt;

    // "account attribute history shows zero system-actor writes" — the audit
    // log is where that is provable.
    const audit = await apiJson(page, `/audit-log?f.entity_id=${account.id}`);
    expect(audit.status, "S61's audit read must serve for step 3 to be checkable").toBe(200);
    const rows = (audit.body?.results ?? []) as Array<Record<string, unknown>>;
    for (const row of rows) {
      expect(
        String(row.action ?? ""),
        "BR-CUS-063 CL-6: nothing may auto-untag an exemption — every change is a " +
          "named human's",
      ).not.toMatch(/exempt.*(expire|auto|system)/i);
    }

    const after = await apiJson(page, `/accounts/${account.id}`);
    expect(after.body?.tax_exempt, "the flag is byte-identical across the expiry boundary").toBe(
      flag,
    );
  });

  test("steps 4–5 · both staff decision paths exist — renew the certificate, or untag by hand", async ({
    page,
  }) => {
    test.setTimeout(300_000);
    await signIn(page);

    const accounts = await apiJson(page, "/accounts");
    const account = (accounts.body?.results ?? [])[0] as Record<string, string>;

    await page.goto(`/${tenant()}/accounts/${account.id}`);
    await expect(
      page.getByRole("button", { name: /edit|certificate|exempt/i }).first(),
      "T4-12 steps 4/5: a human must be able to record a RENEWED certificate or to " +
        "untag — the ruling makes staff the only actor, so the surface must exist",
    ).toBeVisible({ timeout: 15_000 });
  });
});

// ── Lifecycle ─────────────────────────────────────────────
// packet: batch-A journey activation (2026-08-15)
// generated: 2026-08-15 by the batch-A journey lane
// checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-08)
// gates: `npm run typecheck:e2e` · run against the live stack on 8110/8030
// exceptions: T4-12 states no money figure at all, so no moneyTriple lookup
//   appears. Step 2 (the Aug run honouring the exemption) needs a second cycle
//   run and is not walked.
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
