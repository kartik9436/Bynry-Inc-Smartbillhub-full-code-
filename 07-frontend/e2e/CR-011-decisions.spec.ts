// ── Trace ──────────────────────────────────────────────
// Change:  CR-011 (12-governance/11-change-requests.md) — the Phase-4 decision
//          batch: TEN PO answers delivered in one message on 2026-08-18. It is
//          not a screen build, so this file is not a screen walkthrough: it is
//          the DECISION-BY-DECISION proof that the four decisions with a user-
//          visible half actually reach a user.
// Screens: S8 Settings → Configure → Reference data (decision 3) · S8 Settings
//          → Users (decision 7) · S8 Settings → Configure → Templates
//          (decision 9) · S8 Settings → Security (decision 8) · S13 Plans &
//          Rates → Taxes & fees (decision 1)
// Rules:   BR-IDN-017 (a System Admin changes a user's email through PATCH
//          /users/{id}) · BR-IDN-025/026 (the ratified security-policy
//          defaults) · BR-NOT-002 (a contract version is effective-dated, so a
//          default is OFFERED and never auto-published) · BR-TEN-012 (a
//          fixture never overwrites a tenant-touched row).
// ───────────────────────────────────────────────────────
//
// **WHY A SPEC FOR A CR THAT SHIPPED NO SCREEN.** CR-011's requirement IS the
// ten decisions being recorded and implemented, and four of them landed
// somewhere a person has to be able to see or do something:
//
//   3 · the twelve account sub-type names the PO confirmed
//   7 · the two sample staff users — AND the new requirement that came with the
//       delegation, verbatim: *"later allow user to cahnge email as well as
//       Name"*
//   8 · the security-policy row question the PO delegated
//   9 · *"provide default and allow user to change"* for the four legal-wording
//       contract classes
//
// Hard-won law 2 is the whole reason this exists: decision 7's email change was
// COMPLETE in `apps/identity/services.update_user` (it validates per-tenant
// uniqueness and writes a `user.email_changed` audit row), the API client's
// `updateTenantUser` accepted `email` — and the Edit-user modal drew one text
// field and sent `{full_name, role}`. Every backend test passed. Nobody could
// change an email. That is what this file goes red on.
import { expect, test } from "@playwright/test";
import type { Page } from "@playwright/test";

import { signIn, skipUnlessAppServer, tenant } from "./support/app";

const APP_SERVER_TAG = "[app-server]";

skipUnlessAppServer(test);

const referenceDataPath = (list: string): string =>
  `/${tenant()}/settings/reference-data/reference-data?list=${list}`;
const usersPath = (): string => `/${tenant()}/settings/users`;
const templatesPath = (): string => `/${tenant()}/settings/reference-data/templates`;
const securityPath = (): string => `/${tenant()}/settings/security`;
const taxesPath = (): string => `/${tenant()}/plans-rates/taxes-fees`;

// ═══════════════════════════════════════════════════════════════════════════
// DECISION 3 · ACCOUNT SUB-TYPE NAMES — *"Confirmed"*
// ═══════════════════════════════════════════════════════════════════════════
//
// This is the ONE item of the ten the CR could bank on the day it arrived,
// and the reason is recorded there: the twelve-row tree had been SHOWN to the
// PO on screen (seed audit Part 10.0) before they answered. So the standing
// sign-off rule was satisfied — a signature covers what was shown. This test
// re-establishes that the thing shown is still the thing shipped.
test(`CR-011 decision 3 · the twelve confirmed account sub-types are on screen ${APP_SERVER_TAG}`, async ({
  page,
}) => {
  test.setTimeout(180_000);
  await signIn(page);
  await page.goto(referenceDataPath("account_subtypes"));
  await expect(page.getByRole("button", { name: "← Reference data" })).toBeVisible();

  // The names as the PO saw them, in the seed's own order. Asserted on the
  // RENDERED CELL rather than on the fixture, because the fixture is one of
  // four places these strings pass through and the only one that matters is
  // the one a person reads.
  for (const name of [
    "Single-family",
    "Multi-family",
    "Senior/Low-income",
    "Small commercial",
    "Large commercial",
    "Institutional & non-profit",
    "Healthcare",
    "Light industrial",
    "Heavy industrial",
    "Municipal buildings",
    "Schools",
    "Parks & facilities",
  ]) {
    await expect(
      page.getByRole("cell", { name, exact: true }),
      `account sub-type "${name}" is on the screen the PO confirmed`,
    ).toHaveCount(1);
  }
  await expect(page.locator(".table-pager-range")).toHaveText("1–12 of 12");
});

// ═══════════════════════════════════════════════════════════════════════════
// DECISION 7 · SAMPLE STAFF USERS, AND THE REQUIREMENT THAT CAME WITH THEM
// ═══════════════════════════════════════════════════════════════════════════
//
// PO verbatim: *"you decide and later allow user to cahnge email as well as
// Name"*. TWO things, and the second is a new requirement rather than a
// delegation. The delegation half was honoured — `apps/identity/sample_data.py`
// picks Sam Reyes (Billing Clerk) and Avery Cole (Executive) on the RFC 2606
// `.test` domain, both invited and UNCREDENTIALED so the owner stays the only
// login. The requirement half is what this test is for.
test(`CR-011 decision 7 · a staff user's NAME and EMAIL can both be changed ${APP_SERVER_TAG}`, async ({
  page,
}) => {
  test.setTimeout(240_000);
  await signIn(page);
  await page.goto(usersPath());

  const table = page.locator("table.data-table");
  await table.waitFor({ timeout: 30_000 });

  // ── 1 · THE DELEGATION HALF — the two sample staff users exist ──────────
  await expect(page.getByRole("cell", { name: "Sam Reyes", exact: true })).toHaveCount(1);
  await expect(page.getByRole("cell", { name: "Avery Cole", exact: true })).toHaveCount(1);
  await expect(
    page.getByRole("cell", { name: "avery.cole@sample.test", exact: true }),
    "the sample staff address is on the clearly-sample .test domain (BR-IDN-029)",
  ).toHaveCount(1);

  // ── 2 · THE REQUIREMENT HALF — open Edit on one of them ────────────────
  const row = table
    .locator("tbody tr")
    .filter({ has: page.getByRole("cell", { name: "Avery Cole", exact: true }) });
  await row.getByRole("button", { name: "Edit" }).click();

  // BOTH fields must be there. The name field has always been.
  await expect(page.locator("#full_name")).toBeVisible();
  await expect(
    page.locator("#email"),
    'CR-011 decision 7: the PO ruled "later allow user to cahnge email as well as ' +
      'Name". `update_user` has accepted an email since the day it was written and ' +
      "the Edit modal offered no field for it, so no System Admin could change one.",
  ).toBeVisible();

  // ── 3 · AND IT MUST ACTUALLY ROUND-TRIP ────────────────────────────────
  // Built is not wired has a second half: a field that renders and does not
  // reach the server is the same defect wearing a control.
  const original = "avery.cole@sample.test";
  const changed = "avery.cole.cr011@sample.test";
  await page.locator("#email").fill(changed);
  await page.locator("#full_name").fill("Avery Cole");
  await page.getByRole("button", { name: "Save user" }).click();
  await expect(page.getByRole("cell", { name: changed, exact: true })).toHaveCount(1);

  // Put it back — this walkthrough runs against the demo tenant and must leave
  // the seed as it found it (CR-006 run 4's lesson: a spec that only passes on
  // a pristine seed is a spec that passes once).
  await row.getByRole("button", { name: "Edit" }).click();
  await page.locator("#email").fill(original);
  await page.getByRole("button", { name: "Save user" }).click();
  await expect(page.getByRole("cell", { name: original, exact: true })).toHaveCount(1);
});

// ═══════════════════════════════════════════════════════════════════════════
// DECISION 8 · THE SECURITY-POLICY ROW — *"you decide"*
// ═══════════════════════════════════════════════════════════════════════════
//
// The delegation was to decide whether provisioning WRITES the row or lets
// every read fall back to the ratified column defaults. Whatever is decided,
// the figures a utility sees on day zero are BR-IDN-025/026's and must not
// move: minimum length 8, upper+lower+number required, symbol optional,
// expiry never, idle timeout 60 minutes, no IP restriction. This test pins
// the FIGURES, so the decision can be implemented underneath it without any
// tenant's effective policy changing.
test(`CR-011 decision 8 · the security screen opens on the ratified defaults ${APP_SERVER_TAG}`, async ({
  page,
}) => {
  test.setTimeout(180_000);
  await signIn(page);
  await page.goto(securityPath());

  await expect(page.locator("#pw_min_length")).toBeVisible();
  await expect(page.locator("#pw_min_length")).toHaveValue("8");
  await expect(page.locator("#session_timeout_minutes")).toHaveValue("60");
  await expect(page.locator("#pw_require_mixed")).toBeChecked();
  await expect(page.locator("#pw_require_symbol")).not.toBeChecked();
});

// ═══════════════════════════════════════════════════════════════════════════
// DECISION 9 · THE FOUR LEGAL-WORDING CONTRACT CLASSES
// ═══════════════════════════════════════════════════════════════════════════
//
// PO verbatim, reversing a standing refusal: *"already answer - provide default
// and allow user to change"*, and the reasoning the PO gave for the one this
// session had recommended holding: *"create this dont leave it open ; once
// sample and defaults are available we can make changes later; but without
// default sample functionalities ill not work"*.
//
// The bodies are deliberately NOT seeded as versions — BR-NOT-002 makes a
// contract effective-dated and provisioning day is not a date a human chose —
// so they arrive on the detail payload as an OFFER. Which means the only place
// this ruling can be seen at all is this screen.
const CONTRACT_CLASSES = [
  "contract_service_agreement",
  "contract_deposit",
  "contract_payment_plan",
  "contract_autopay_authorization",
] as const;

async function openTemplate(page: Page, code: string): Promise<void> {
  await page.locator("table.data-table").waitFor({ timeout: 30_000 });
  await page.locator(`[data-testid=template-open-${code}]`).click();
  await page.locator("[data-testid=template-back]").waitFor({ timeout: 30_000 });
}

test(`CR-011 decision 9 · all four contract classes offer a default on screen ${APP_SERVER_TAG}`, async ({
  page,
}) => {
  test.setTimeout(300_000);
  await signIn(page);

  for (const code of CONTRACT_CLASSES) {
    await page.goto(templatesPath());
    await openTemplate(page, code);

    const offer = page.locator("[data-testid=platform-default-offer]");
    await expect(
      offer,
      `CR-011 decision 9: ${code} must OFFER its default wording. "Without default ` +
        `sample functionalities ill not work" is the ruling this renders.`,
    ).toBeVisible();

    // The body is real wording, not a stub. 200 characters is well under every
    // authored body and well over any placeholder token.
    const body = await page.locator("[data-testid=offer-body]").innerText();
    expect(body.trim().length, `${code}'s offered body is real wording`).toBeGreaterThan(200);

    // The standing notice — the platform wrote it, the utility owns it, the
    // product warrants nothing.
    await expect(page.locator("[data-testid=offer-notice]")).toContainText(
      "not legal advice",
    );
    // BR-NOT-002 stated where the date is chosen.
    await expect(page.locator("[data-testid=offer-date-required]")).toBeVisible();

    if (code === "contract_autopay_authorization") {
      // The one placeholder, and the REFUSAL IS THE FEATURE: a recurring-ACH
      // authorization's wording is NACHA-prescribed and this repo does not
      // hold that scheme, so a default drafted by inference is the one
      // document here where a plausible wrong answer creates real liability.
      await expect(page.locator("[data-testid=offer-placeholder-warning]")).toBeVisible();
      // PO 2026-08-18, second half of the ruling: *"put the details, I will
      // handle it with user"* — so what the utility must supply is enumerated
      // on the screen the PO will be looking at, not left as "paste your own".
      await expect(page.locator("[data-testid=offer-requires] li").first()).toBeVisible();
    } else {
      await expect(page.locator("[data-testid=offer-placeholder-warning]")).toHaveCount(0);
    }
  }
});

// ═══════════════════════════════════════════════════════════════════════════
// DECISION 1 · TAX JURISDICTION RATES — *"already answered"*
// ═══════════════════════════════════════════════════════════════════════════
//
// The PO's answer was that the figures were ALREADY ruled, and they were:
// r10's own five-row Texas table, written out in full in the decision log on
// 2026-08-18 (DEF-254) and seedable only after DEF-273 gave `taxes` the
// customer-class and premises-geography qualifiers three of the five rows
// carry. This asserts the SCREEN a utility prices its taxes on renders the
// authorities the tenant actually holds, with their rates — the surface the
// ruling lands on.
//
// ⚠ IT DOES NOT ASSERT FIVE ROWS, and that is deliberate rather than weak.
// The demo tenant was provisioned 2026-08-18 08:19, BEFORE DEF-273 landed, and
// DEF-247's set-skip means a tenant that already holds any `taxes` row is
// given none by a fixture — so this tenant keeps the two rates it was born
// with, exactly as BR-TEN-012 requires. The five ruled rows are the default a
// tenant provisioned from here receives.
test(`CR-011 decision 1 · the tenant's tax authorities render with their rates ${APP_SERVER_TAG}`, async ({
  page,
}) => {
  test.setTimeout(180_000);
  await signIn(page);
  await page.goto(taxesPath());

  // The identity cell is a BUTTON reading "<tax> · <jurisdiction>", so each
  // authority is addressed with its jurisdiction — which is the right handle
  // anyway: two authorities may share a name across jurisdictions and the
  // remittance report is keyed on the pair.
  await expect(
    page.getByRole("button", { name: "State water tax · Texas State" }),
  ).toHaveCount(1);
  await expect(
    page.getByRole("button", { name: "City utility tax · Local" }),
  ).toHaveCount(1);
  // Each authority has a liability GL account, which is what DEF-166 was: two
  // authorities provisioning had made were never mapped, and every one of 95
  // bills refused at issue because a tax line could not be stamped.
  await expect(page.locator("main.view")).toContainText("Tax payable — State water tax");

  // ⚠ FINDING, filed as DEF-285 and NOT fixed here (it is an adjacent-surface
  // defect, not decision 1's own requirement — 13-change-process.md §"a defect
  // is not a CR blocker"). The Rate column renders the STORED FRACTION:
  // "0.062500 of the taxable amount" where the PO's ruled table says 6.25%.
  // Pinned so the fix cannot land quietly: when this goes red, the screen
  // started speaking percent and the defect row closes with it.
  await expect(
    page.locator("main.view"),
    "DEF-285: the taxes screen states a rate as a fraction (0.062500) where every " +
      "ruled figure, r10's table and the utility's own filing are in percent",
  ).toContainText("0.062500 of the taxable amount");
});
