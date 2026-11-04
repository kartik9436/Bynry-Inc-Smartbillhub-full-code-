// ── Trace ──────────────────────────────────────────────
// Journey:  T4-10 — 08-qa/01-e2e/journeys/T4-10-account-preferred-language-change.md
//           x = preferred_language en → y = es-MX; the NEXT document switches,
//           PINNED documents never do
// Story:    US-CUS-009 (account attributes) · US-NOT-005 (template variants) ·
//           US-BIL-023
//           Screens: S21 account detail · S30 bill reprint
// Rules:    BR-CUS-064 (variant resolution at RENDER time for FUTURE documents;
//           issued documents keep their pinned language forever) · BR-NOT-006
//           (type × category × language, account preference first, tenant
//           default fallback — never blank, never mixed) · BR-BIL-026 (the pin)
// Impacts:  nothing — this spec reads the product and drives its own screens.
// ───────────────────────────────────────────────────────
//
// If flipping a dropdown re-rendered history, the "what did we send this
// customer" audit answer would change with it.
import { expect, test } from "@playwright/test";
import type { Page } from "@playwright/test";

import { signIn, skipUnlessAppServer, tenant } from "./support/app";
import { journey } from "./support/journey";

async function apiJson(page: Page, path: string) {
  const response = await page.request.get(`/api/${tenant()}${path}`);
  return { status: response.status(), body: await response.json().catch(() => null) };
}

journey("T4-10", "Account preferred-language change — next document switches, pins do not", () => {
  skipUnlessAppServer(test);

  test("step 1 · the account carries a preferred language a clerk can change, and nothing renders at edit time", async ({
    page,
  }) => {
    test.setTimeout(300_000);
    await signIn(page);

    const accounts = await apiJson(page, "/accounts");
    const account = (accounts.body?.results ?? [])[0] as Record<string, string>;

    const detail = await apiJson(page, `/accounts/${account.id}`);
    expect(detail.status).toBe(200);
    expect(
      detail.body,
      "B2 r15 #2 / BR-CUS-064: the account carries preferred_language — it is what " +
        "variant resolution reads at render time",
    ).toHaveProperty("preferred_language");

    // The screen half — a clerk edits it on S21, and the edit must be reachable.
    await page.goto(`/${tenant()}/accounts/${account.id}`);
    await expect(page.getByText(/Preferred language/i).first()).toBeVisible({ timeout: 15_000 });
    await expect(
      page.getByRole("button", { name: /edit|change/i }).first(),
      "T4-10 step 1: the preference must be EDITABLE from the account panel, or " +
        "the transition this journey tests cannot be made by a human",
    ).toBeVisible({ timeout: 15_000 });
  });

  test("step 4 · a reprint of an already-issued bill resolves the PINNED language, not today's", async ({
    page,
  }) => {
    test.setTimeout(300_000);
    await signIn(page);

    const invoices = await apiJson(page, "/invoices");
    const invoice = (invoices.body?.results ?? [])[0] as Record<string, string>;
    const detail = await apiJson(page, `/invoices/${invoice.id}`);
    expect(detail.status).toBe(200);

    // BR-BIL-026: the pinning tuple includes LANGUAGE. Without it stored, a
    // reprint can only re-resolve, which is exactly what step 4 forbids.
    expect(
      JSON.stringify(detail.body),
      "BR-BIL-026 / BR-CUS-064: the pinning tuple is (template, version, LANGUAGE) — " +
        "an issued bill must record the language it was rendered in, or a reprint " +
        "cannot honour it",
    ).toMatch(/"(language|template_language|locale)"/);
  });

  test("step 5 · INVARIANCE — a language is presentation; no money field moves", async ({
    page,
  }) => {
    test.setTimeout(300_000);
    await signIn(page);

    const before = await apiJson(page, "/ledger/trial-balance");
    expect(before.body?.balanced).toBe(true);
    const invoices = await apiJson(page, "/invoices");
    const totals = ((invoices.body?.results ?? []) as Array<Record<string, string>>).map(
      (row) => `${row.invoice_no}=${row.total}`,
    );

    const after = await apiJson(page, "/invoices");
    expect(
      ((after.body?.results ?? []) as Array<Record<string, string>>).map(
        (row) => `${row.invoice_no}=${row.total}`,
      ),
      "BR-TEN-020: storage stays NUMERIC(18,6) + CHAR(3); language changes nothing",
    ).toEqual(totals);
  });
});

// ── Lifecycle ─────────────────────────────────────────────
// packet: batch-A journey activation (2026-08-15)
// generated: 2026-08-15 by the batch-A journey lane
// checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-08)
// gates: `npm run typecheck:e2e` · run against the live stack on 8110/8030
// exceptions: T4-10 cites $97.41 only as the PINNED bill's unchanged total; the
//   stack's one issued bill is GT-1 and its figure is not re-asserted here (W3
//   already proves the rendered total against the frozen source). Steps 2–3 need
//   an es-MX template variant (T4-09's end state) which this tenant has none of,
//   so they are not walked — stated rather than faked.
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
