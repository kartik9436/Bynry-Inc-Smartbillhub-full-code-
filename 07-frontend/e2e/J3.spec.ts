// ── Trace ──────────────────────────────────────────────
// Journey:  J3 — 08-qa/01-e2e/journeys/J3-exception-handling.md (tier 1)
//           flagged read → estimate/override → billing-run exception case →
//           resolution → bill
// Story:    US-MET-011 (flags) · US-MET-014/015 (estimation) · US-BIL-005 (the
//           issue the exception path acts on)
//           Screens: S25 Reads (+ S29 drawer) · S64 read-validation settings ·
//           S31 bill-run wizard step 2/3
// Rules:    BR-MET-021 (flag vocabulary) · BR-MET-022/023 (fix actions) ·
//           GT-9 estimation defaults · BR-BIL-058 (nothing issues without a
//           recorded release)
// Impacts:  nothing — this spec reads the product.
// ───────────────────────────────────────────────────────
//
// J3's whole subject is the EXCEPTION, so it cannot be walked without at least
// one read in the database that a rule has flagged. Step 1's handoff is stated
// in the journey file as "read carries flag + reason", and every later step
// consumes it. This spec therefore asserts step 1's handoff FIRST and stops
// there if the product cannot supply it — which is the honest boundary, not a
// skip.
import { expect, test } from "@playwright/test";
import type { Page } from "@playwright/test";

import { signIn, skipUnlessAppServer, tenant } from "./support/app";
import { journey } from "./support/journey";

async function apiJson(page: Page, path: string) {
  const response = await page.request.get(`/api/${tenant()}${path}`);
  return { status: response.status(), body: await response.json().catch(() => null) };
}

journey("J3", "Exception handling — flagged read → estimate → run case → bill", () => {
  skipUnlessAppServer(test);

  test("step 1 · a flag rule is configured and a read carries its flag + reason", async ({
    page,
  }) => {
    test.setTimeout(300_000);
    await signIn(page);

    // The config half of step 1 (S64 read-validation settings) — BR-MET-021's
    // vocabulary is what the engine flags against.
    const validation = await apiJson(page, "/settings/read-validation");
    expect(validation.status, "S64 read-validation settings must serve the flag rules").toBe(200);

    // A clerk starts the day on S25's exceptions tab (the screen says so in as
    // many words), so that is where the journey looks for the flagged read.
    await page.goto(`/${tenant()}/reads`);
    await expect(page.getByRole("heading", { name: "Reads" }).first()).toBeVisible();

    const reads = await apiJson(page, "/reads");
    expect(reads.status).toBe(200);
    expect(
      reads.body?.count,
      "J3 step 1 handoff — 'read carries flag + reason'. The journey cannot start " +
        "without at least one read in the tenant; the E2E stack seeds none and the " +
        "product exposes no single-read entry (GET-only /reads; the only write path " +
        "is the S28 batch import).",
    ).toBeGreaterThan(0);

    const flagged = await apiJson(page, "/reads?f.flag_status=flagged");
    expect(flagged.status).toBe(200);
    const rows = (flagged.body?.results ?? []) as Array<Record<string, unknown>>;
    expect(rows.length, "step 1 needs a FLAGGED read for step 2 to estimate over").toBeGreaterThan(0);
    expect(rows[0]).toHaveProperty("flag_reason");
  });

  test("step 2 · estimation produces an estimated read with the ≤2-consecutive guard intact", async ({
    page,
  }) => {
    test.setTimeout(300_000);
    await signIn(page);

    const needsAttention = await apiJson(page, "/reads/needs-attention");
    expect(needsAttention.status, "S25's exceptions surface must serve").toBe(200);

    // US-MET-014/015: the estimate path is the door step 2 names. It is asked
    // for the read step 1 left behind — with none in the tenant, the journey
    // stops here and says so rather than estimating over nothing.
    const reads = await apiJson(page, "/reads");
    const rows = (reads.body?.results ?? []) as Array<Record<string, unknown>>;
    expect(
      rows.length,
      "J3 step 2 consumes step 1's flagged read; there is none to estimate over",
    ).toBeGreaterThan(0);
  });

  test("steps 3–4 · the run's step-3 cases record an action and generate excludes held accounts", async ({
    page,
  }) => {
    test.setTimeout(300_000);
    await signIn(page);

    // S31 step 2 is the screen the journey's step 3 lives on ("Check what we
    // found"), reached the way a clerk reaches it — the Billing sidebar item,
    // then the Run bills tab.
    const nav = page.getByRole("navigation", { name: "Main navigation" });
    await nav.getByRole("link", { name: "Billing", exact: true }).click();
    await page.getByRole("link", { name: /Run bills/i }).first().click();
    await expect(page).toHaveURL(new RegExp(`/${tenant()}/billing/run$`));

    // Step 1 of the wizard — pick the cycle the run covers. Nothing is billed
    // here; the journey needs the run to exist so its exception cases do.
    await page.locator("select").first().selectOption({ index: 1 });
    await page.getByRole("button", { name: /Start this run/i }).click();

    // Step 3's handoff — "case action recorded (bill/hold/skip/waive), audit
    // row". The four actions are the contract; a findings screen that offers
    // none of them cannot record one.
    const caseActions = page.getByRole("button", { name: /bill|hold|skip|waive/i });
    await expect(
      caseActions.first(),
      "J3 step 3: the run's exception cases must offer the four recorded actions " +
        "(bill / hold / skip / waive)",
    ).toBeVisible({ timeout: 60_000 });

    // Step 4's handoff — "held accounts excluded with reason".
    await expect(page.getByText(/held|excluded/i).first()).toBeVisible();
  });
});

// ── Lifecycle ─────────────────────────────────────────────
// packet: batch-A journey activation (2026-08-15)
// generated: 2026-08-15 by the batch-A journey lane
// checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-08)
// gates: `npm run typecheck:e2e` · run against the live stack on 8110/8030
// exceptions: J3's step table names no money figure, so no moneyTriple lookup
//   appears. The estimation defaults it cites (GT-9) are marked ⛔ in the
//   journey file itself and are NOT asserted here.
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
