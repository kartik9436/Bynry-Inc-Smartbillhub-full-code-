// ── Trace ──────────────────────────────────────────────
// Journey:  T7-07 — Per-user UI language override vs tenant default (chrome is
//           personal; documents don't care).
//           `08-qa/01-e2e/journeys/T7-07-user-ui-language-override.md` is the
//           spec; this file walks its six-row step table in order.
// Story:    US-SHL-005 (the shell's user menu — where the override lives) ·
//           US-SHL-013 (the formatting/locale service) · US-TEN-006 (S8
//           Regional — the tenant default) · US-IDN-001 (sign in)
//           Screens: S3 · S48 profile (user menu) · S8 Regional · S30
// Rules:    BR-SHL-030 (per-user UI override, stored SERVER-side) · BR-TEN-042
//           (the tenant default) · BR-CUS-064 (account preferred language —
//           DOCUMENTS only) · TD-16 (#3: the server emits error CODES +
//           parameters and each client translates them, so no translated
//           string is ever stored; #5: tenant-entered reference data is never
//           machine-translated) · BR-NOT-006 (the document language pin)
// Money:    NONE. Every row is about language precedence; `moneyTriple` is not
//           called rather than borrowed.
// Impacts:  10-scripts/gates/g12_journeys.py · e2e/support/census.ts
// ───────────────────────────────────────────────────────
//
// WHAT THE HARNESS ALREADY SAYS ABOUT THIS ONE. `07-frontend/e2e/README.md`:
// *"Until the real language-switcher UI lands (FI-03 switcher, S48 packet),
// specs flip languages through the `window.__SMARTBILLHUB_I18N__` handle."* So
// the surface step 1 needs is known-absent, and this journey's subject is not
// "does i18n work" — it is the PRECEDENCE of three settings that must not bleed
// into each other, which needs the override to be storable at all.
//
// `PATCH /me` takes `full_name` and `phone` (identity's ProfileSerializer) and
// nothing else; `role` and `email` are explicitly refused. There is no
// per-user language field anywhere in the identity surface.
import { expect, test } from "@playwright/test";

import { signIn, skipUnlessAppServer, tenant } from "./support/app";
import { journey } from "./support/journey";

function api(path: string): string {
  return `/api/${tenant()}${path}`;
}

journey("T7-07", "Per-user UI language override vs tenant default", () => {
  // NOT serial: each row builds its own precondition, so the run reports which
  // of the journey's six hold rather than stopping at the first that does not.
  skipUnlessAppServer(test);

  test("step 1 — the user menu stores a per-user UI language SERVER-side", async ({ page }) => {
    await signIn(page);
    const response = await page.request.patch(api("/me"), { data: { ui_language: "hi" } });
    expect(
      [200, 201],
      `PATCH /me {ui_language} answered ${response.status()} — BR-SHL-030's override has ` +
        "no server field (identity's ProfileSerializer takes full_name and phone only)",
    ).toContain(response.status());
    const me = await page.request.get(api("/me"));
    expect(me.status()).toBe(200);
    expect(
      JSON.stringify(await me.json()),
      "the stored override must come back on the profile read",
    ).toMatch(/hi/);
  });

  test("step 2 — two users see different chrome over identical data rows", async ({ page }) => {
    await signIn(page);
    // The precedence this step proves needs the override from step 1 to exist.
    const me = await page.request.get(api("/me"));
    expect(me.status()).toBe(200);
    expect(
      JSON.stringify(await me.json()),
      "BR-SHL-030: the profile must carry a UI-language field for chrome to follow",
    ).toMatch(/language/i);
  });

  test("step 3 — a tenant-default change moves only the users WITHOUT an override", async ({
    page,
  }) => {
    await signIn(page);
    const before = await page.request.get(api("/settings/regional"));
    expect(before.status()).toBe(200);
    const original = ((await before.json()) as { language: string }).language;

    const save = await page.request.put(api("/settings/regional"), { data: { language: "es-MX" } });
    expect(
      [200, 201],
      `changing the tenant default answered ${save.status()}: ${(await save.text()).slice(0, 300)}`,
    ).toContain(save.status());

    // Precedence: a tenant-level save must NOT rewrite any user profile row.
    const me = await page.request.get(api("/me"));
    expect(
      JSON.stringify(await me.json()),
      "BR-SHL-030 > BR-TEN-042: a tenant save must not overwrite a user's own override",
    ).not.toMatch(/es-MX/);

    await page.request.put(api("/settings/regional"), { data: { language: original } });
  });

  test("step 4 — a server refusal travels as a CODE + parameters, never a translated string", async ({
    page,
  }) => {
    await signIn(page);
    // TD-16 #3, proved on a real refusal: the envelope carries `message_key`
    // and `params`, and no rendered sentence.
    const response = await page.request.put(api("/settings/regional"), { data: { currency: "XXX" } });
    expect(response.status()).toBeGreaterThanOrEqual(400);
    const envelope = (await response.json()) as Record<string, unknown>;
    expect(envelope.message_key, "the refusal must name a CODE").toBeTruthy();
    expect(
      JSON.stringify(envelope),
      "no translated prose may travel in a refusal payload (TD-16 #3)",
    ).not.toMatch(/[a-z]{4,}\s+[a-z]{4,}\s+[a-z]{4,}/);
  });

  test("step 5 — a document renders its PINNED language, whatever the viewer's chrome is", async ({
    page,
  }) => {
    await signIn(page);
    const invoices = await page.request.get(api("/invoices?per=1"));
    expect(invoices.status()).toBe(200);
    const first = ((await invoices.json()) as { results: { id: string }[] }).results[0];
    expect(first, "the fixture has no bill to reprint").toBeDefined();

    const doc = await page.request.get(api(`/invoices/${first.id}/document`));
    expect(
      doc.status(),
      `the rendered document answered ${doc.status()} — BR-NOT-006's language pin has no ` +
        "document surface to be honoured on (PO 2026-08-15: a journey step expecting " +
        "delivery ends at a RENDERED DOCUMENT, and there is none)",
    ).toBe(200);
  });

  test("step 6 — INVARIANCE: every language edit touched settings only", async ({ page }) => {
    await signIn(page);
    const invoices = await (await page.request.get(api("/invoices?per=100"))).text();
    const ledger = await (await page.request.get(api("/ledger/trial-balance"))).text();
    await page.request.put(api("/settings/regional"), { data: { language: "en-US" } });
    expect(await (await page.request.get(api("/invoices?per=100"))).text()).toBe(invoices);
    expect(await (await page.request.get(api("/ledger/trial-balance"))).text()).toBe(ledger);
  });
});

// ── Lifecycle ─────────────────────────────────────────────
// packet: T7-07 journey activation (batch B lane, 2026-08-15)
// generated: 2026-08-15 by the E2E journey-activation lane
// checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-08)
// gates: run against the live stack on E2E_BACKEND_PORT=8040 / E2E_WEB_PORT=8120
// exceptions: (1) the journey's two concurrent users (Priya with an override,
//   Dana without) cannot be staged: the seeded tenant has one user and the
//   add-user flow hands back no usable credential (NFR-14) — so steps 1–3
//   assert the OVERRIDE FIELD itself, which is what the two-user comparison
//   rests on · (2) the spec does NOT use the `window.__SMARTBILLHUB_I18N__`
//   handle the W0 smoke uses: that handle proves the catalogues load, and this
//   journey is about a SERVER-STORED preference, which the handle cannot stand
//   in for · (3) no money figure is asserted
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
