// ── Trace ──────────────────────────────────────────────
// Change:  CR-058 W2 task 9 — BOTH counter screens, clicked in a real browser
//          against a real server (PO ruling 2026-08-30, verbatim: *"All UI
//          screen should be confirm using real broswer testing and not just
//          based on test cases"*).
// Rules:   BR-CUS-1024 (match first; an exact name + government identifier
//          reuses the number on file; and no identifier means NO ACCOUNT) ·
//          BR-CUS-1023 (the creation minimum) · BR-CUS-1022 (identity is per
//          kind) · B14 rule 31 (no database id is ever a visible value) ·
//          B14 rule 32 (no rule id or internal code in clerk copy)
// Defect:  DEF-2817 — one landlord, one SSN, three customer numbers.
// ───────────────────────────────────────────────────────
/**
 * **What a clerk actually sees at the counter.**
 *
 * The unit suites prove the payload and the server proves the rule. Neither can
 * answer the question this file asks, which is the one the PO asked: **does the
 * screen say it?** A refusal that renders as nothing, or an outcome sentence
 * whose class no stylesheet declares (B14 rule 21 · DEF-974), passes every
 * assertion in both other layers.
 */
import { expect, test } from "@playwright/test";
import { signIn, skipUnlessAppServer, tenant } from "./support/app";

skipUnlessAppServer(test);

test.describe("CR-058 — the customer, at both counter doors", () => {
  test.beforeEach(async ({ page }) => {
    await signIn(page);
  });

  test("S18: the account will not open on a name alone, and the reason is a sentence", async ({
    page,
  }) => {
    await page.goto(`/${tenant()}/accounts/new`);
    await page.locator("#full_name").fill("Okonkwo, Adaeze");

    // ⛔ `BR-CUS-1024` — a name and nothing else. The clerk must be told, HERE,
    // that this will not open an account, and told what to add.
    const strip = page.locator("[data-refusal]").first();
    await expect(strip).toBeVisible();
    const said = (await strip.textContent()) ?? "";
    expect(said.length).toBeGreaterThan(10);
    // B14 rule 32 clause 4 — no rule id and no internal code reaches a clerk.
    expect(said).not.toMatch(/BR-[A-Z]{3}-\d+/);
    expect(said).not.toContain("customer_");
    expect(said).not.toContain("identity_required");

    // ...and Continue does not move: the server refuses this payload, so a
    // wizard that advanced would collect five steps and throw them away.
    const advanced = page.getByRole("button", { name: /Continue/i }).first();
    await advanced.click();
    await expect(page.locator("#full_name")).toBeVisible();

    // Saying it is a PERSON is not enough on its own — the identifier is the
    // other half of the minimum, and the sentence changes to name it.
    await page.locator('label.seg-opt:has(input[name="customer_kind"][value="person"])').click();
    await expect(page.locator("#ssn")).toBeVisible();
    const afterKind = (await strip.textContent()) ?? "";
    expect(afterKind).not.toBe(said);

    // A PHONE clears it, which is what keeps the counter workable.
    await page.locator("#phone").fill("+1 (512) 555-0198");
    await expect(page.locator("[data-refusal]")).toHaveCount(0);
    await advanced.click();
    await expect(page.locator("#full_name")).toHaveCount(0);
  });

  test("S18: a business is asked for its Tax ID and never for a driving licence", async ({
    page,
  }) => {
    await page.goto(`/${tenant()}/accounts/new`);
    await page.locator("#full_name").fill("Rio Verde Property Holdings LLC");
    await page.locator('label.seg-opt:has(input[name="customer_kind"][value="company"])').click();

    // `BR-CUS-1022` — neither kind is shown the other's evidence.
    await expect(page.locator("#tax_id")).toBeVisible();
    await expect(page.locator("#ssn")).toHaveCount(0);
    await expect(page.locator("#driving_licence")).toHaveCount(0);

    const said = (await page.locator("[data-refusal]").first().textContent()) ?? "";
    expect(said).toMatch(/Tax ID/i);
    expect(said).not.toMatch(/driver's license/i);

    await page.locator("#tax_id").fill("12-3456789");
    await expect(page.locator("[data-refusal]")).toHaveCount(0);
  });

  test("S19: the move-in screen asks who is moving in, which it never did", async ({ page }) => {
    // The move-in wizard is reached from an account that is leaving. Any
    // account will do for the question this asks — does the STEP collect an
    // identity — so the first row of the accounts list is used.
    await page.goto(`/${tenant()}/accounts`);
    const firstAccount = page.locator("table tbody tr a").first();
    await expect(firstAccount).toBeVisible();
    const href = await firstAccount.getAttribute("href");
    expect(href).toBeTruthy();
    // `?step=` is the wizard's own deep link and it CLAMPS rather than erroring
    // (BR-SHL-011's spirit), so the customer step is addressable directly.
    await page.goto(`${href}/move-in?step=2`);
    await expect(page.locator("#full_name")).toBeVisible();
    // ⛔ **THE CONTROLS THIS SCREEN HAS NEVER HAD (`CR-058` task 8).** It
    // collected a contact and nothing else, so a returning tenant got a second
    // customer number and an account opened with a blank customer column.
    await expect(page.locator('input[name="customer_kind"][value="person"]')).toHaveCount(1);
    await expect(page.locator('input[name="customer_kind"][value="company"]')).toHaveCount(1);

    await page.locator("#full_name").fill("Okonkwo, Adaeze");
    await expect(page.locator("[data-refusal]").first()).toBeVisible();
    await page.locator('label.seg-opt:has(input[name="customer_kind"][value="person"])').click();
    await expect(page.locator("#ssn")).toBeVisible();
    await page.locator("#ssn").fill("555-44-3333");
    await expect(page.locator("[data-refusal]")).toHaveCount(0);
  });

  test("B14 rule 31: no database id is ever the visible value of a field", async ({ page }) => {
    await page.goto(`/${tenant()}/accounts/new`);
    const body = (await page.locator("body").textContent()) ?? "";
    // A UUID rendered as a value is the rule this catches, and it is the one
    // thing no unit test in either layer looks at.
    expect(body).not.toMatch(/[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}/i);
  });
});
