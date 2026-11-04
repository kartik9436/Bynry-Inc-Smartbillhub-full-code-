// ── Trace ──────────────────────────────────────────────
// Change:  CR-017 (12-governance/11-change-requests.md) — *"after this step at
//          the time of new tenant creation you need new screen showcaing data
//          migration is going on so that User wil know whats going on in the
//          background"* / *"that you for wating your Utility will be provision
//          soon; … otherwise they are left hi and dry"* (PO, 2026-08-19)
// Story:   US-TEN-001 (EP-TEN-03) · Screens: S114 signup wizard, POST-COMMIT
//          STATE (no new A1 id minted — OQ-268 asks the PO for one)
// Rules:   BR-TEN-010 (one atomic idempotent commit) · BR-TEN-012 (the S111
//          toggle governs the sample set) · BR-TEN-063 (the plant's failure
//          never fails provisioning) · BR-SHL-020 (plain-language failure)
// Defect:  DEF-320 (a plant enqueued with no runner rests `queued` forever) ·
//          DEF-324 (the N+1 that made this wait 78 s)
// ───────────────────────────────────────────────────────
//
// **THE PO'S BAR IS A BROWSER, NOT A SUITE.** CLAUDE.md hard-won law 6: no gate
// in this repo looks at rendered output, and this screen exists entirely to be
// looked at. So every assertion below is on TEXT A PERSON READS while a real
// tenant is really provisioned against a real database.
//
// ⚠ IT SIGNS UP FOR A BRAND-NEW TENANT EVERY RUN, on purpose. Provisioning is
// idempotent on the subdomain (BR-TEN-010), so a repeated subdomain would take
// the REPLAY branch — which mints no session, enqueues no plant and therefore
// never shows the screen this file is about. The stamp in the slug is what
// keeps the run on the first-commit path.
import { expect, test } from "@playwright/test";

const STAMP = `${Date.now()}`.slice(-8);
const TENANT = `cr017w${STAMP}`;
const OWNER_EMAIL = `owner@${TENANT}.example.com`;
const OWNER_PASSWORD = "Sup3rSecret!2026";

test.describe("CR-017 — the signup wait names the work", () => {
  test("signing up shows the named provisioning steps and hands over to the checklist", async ({
    page,
  }) => {
    // The whole point is a LONG wait: the sample-data plant runs inside the
    // commit on this stack (JOBS_EAGER=true) and takes ~41 s measured.
    test.setTimeout(300_000);

    await page.goto("/signup");
    await expect(page.locator("#signup-name")).toBeVisible({ timeout: 60_000 });

    // ── step 1 · the utility ────────────────────────────────────────────
    await page.locator("#signup-name").fill(`CR-017 Walkthrough ${STAMP}`);
    await page.locator("#signup-subdomain").fill(TENANT);
    await page.locator("#signup-state").fill("Texas");
    await page.locator('[data-signup="services"] input[type=checkbox]').first().check();
    await page.getByRole("button", { name: /continue/i }).click();

    // ── step 2 · how you bill ───────────────────────────────────────────
    await expect(page.locator("#signup-currency")).toBeVisible();
    await page.locator("#signup-currency").selectOption("USD");
    // The sample set is what the screen narrates, so it must be ON.
    if (!(await page.locator("#signup-load-defaults").isChecked())) {
      await page.locator('label[for="signup-load-defaults"]').click();
    }
    await page.getByRole("button", { name: /continue/i }).click();

    // ── step 3 · plan ───────────────────────────────────────────────────
    await expect(page.locator("input[name=signup-plan]").first()).toBeVisible();
    await page.locator("input[name=signup-plan]").first().check();
    await page.getByRole("button", { name: /continue/i }).click();

    // ── step 4 · review ─────────────────────────────────────────────────
    await page.getByRole("button", { name: /continue/i }).click();

    // ── step 5 · the login, and the commit ──────────────────────────────
    await expect(page.locator("#signup-owner-name")).toBeVisible();
    await page.locator("#signup-owner-name").fill("Pat Walkthrough");
    await page.locator("#signup-owner-email").fill(OWNER_EMAIL);
    await page.locator("#signup-owner-password").fill(OWNER_PASSWORD);
    await page.locator('label[for="signup-terms"]').click();
    await page.getByRole("button", { name: /create|finish|start/i }).last().click();

    // ── THE SCREEN THIS CR EXISTS FOR ───────────────────────────────────
    // It must be on screen WHILE the request is still in flight — that is the
    // whole requirement. A screen that appeared only afterwards would narrate a
    // wait that was already over. It is asserted within seconds of the click,
    // against a request that takes the better part of a minute.
    const panel = page.locator('[data-signup="provisioning"]');
    await expect(panel).toBeVisible({ timeout: 15_000 });

    // The work, NAMED — not a spinner (the difference is the whole CR).
    await expect(panel).toContainText("Your utility and your owner login");
    await expect(panel).toContainText("Reference lists");
    await expect(panel).toContainText("Chart of accounts");
    await expect(panel).toContainText("Sample data");

    // The reassurance, in the PO's own terms: they are told to wait, told
    // nothing is lost, and told what happens next.
    await expect(panel).toContainText("Thank you for waiting");
    await expect(panel).toContainText("You do not need to do anything");

    // ── and then the work lands, named, with the SERVER's own counts ─────
    // "20 lists, 187 rows" is not a number this screen can invent: it is
    // `reference_seed` off the commit response.
    await expect(panel).toContainText(/\d+ lists, \d+ rows/, { timeout: 240_000 });
    await expect(panel).toContainText(/All \d+ blocks loaded|Block \d+ of \d+/);

    // ── the handover, exactly as before this CR ─────────────────────────
    await expect(page).toHaveURL(new RegExp(`/${TENANT}/`), { timeout: 60_000 });
    await expect(page.getByRole("navigation", { name: "Main navigation" })).toBeVisible();
  });
});

// ── Lifecycle ─────────────────────────────────────────────
// packet: CR-017 (11-change-requests.md) + US-TEN-001@d5f8c32
// generated: 2026-08-19 by story-coder (CR-017 provisioning-screen lane)
// checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-09)
// gates: run against the live stack at http://127.0.0.1:8080 — output quoted in the lane report
// exceptions: the assertions are on ENGLISH source strings rather than on catalogue lookups, because a walkthrough that read the same catalogue the app reads could not tell a wrong key from a right one — the eleven-catalogue parity is G15's and is asserted separately in SignupWizard.test.tsx
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
