// ── Trace ──────────────────────────────────────────────
// Story:    US-REP-001 (S44 library) · US-REP-002 (S46 viewer) · US-REP-005
//           (AR ageing) · US-REP-006 (billing register · revenue by service &
//           rate) · US-REP-007 (payments by method)   Screens: S44 · S46
// Rules:    BR-REP-001 (every money render names its date basis) · BR-REP-024
//           (a figure that cannot be computed prints its REASON — never 0,
//           never "null") · BR-SHL-025 (an unavailable control is STATED)
// ───────────────────────────────────────────────────────
// PROOF BY CLICKING (PO ruling 2026-08-11: *"we ahve to prove against human
// clicking"*). Everything else in this lane is a unit test over a mock; this
// file opens a real browser against a real Django and a real Postgres and reads
// what a clerk would read.
//
// It exists because of hard-won law 6 — *diff the running app against the
// prototype; no gate looks at rendered output* — and because three lanes on
// 2026-08-16 shipped a browser check that PASSED against a broken screen. So
// every assertion below names the thing that was actually at risk:
//
//   · the library RENDERS CARDS rather than the developer string that stood at
//     `/{tenant}/reports` until this morning;
//   · an unavailable card has NO LINK — the "confident empty report" this whole
//     lane was told to avoid;
//   · the viewer's page head carries a BASIS, and the two reports disagree
//     about which one, which is the entire content of BR-REP-001;
//   · a KPI the server could not compute shows a SENTENCE, and the literal
//     strings "null" and "NaN" appear nowhere in the rendered page.
import { expect, test } from "@playwright/test";

import { signIn } from "./support/app";

const TENANT = "brazosbend";

test.describe("US-REP-001 · S44 — the report library is a screen @app-server", () => {
  test("US-REP-001 TC-1: the library renders its three groups of cards", async ({ page }) => {
    await signIn(page);
    await page.goto(`/${TENANT}/reports`);

    // DEF-152's own assertion, kept: the address that used to render
    // "SMARTBillHub — W0 scaffold" now renders the product.
    await expect(page.getByRole("heading", { name: "Reports", level: 1 })).toBeVisible();
    await expect(page.locator("body")).not.toContainText("W0 scaffold");

    // ⚠ **SIX GROUPS, NOT THREE — `P1.1`, 2026-09-26.** The catalogue used to
    // be a frozen Python tuple of 23 cards in A14's three groups. It is now 45
    // cards out of `report_definitions` in the six `report_categories` holds,
    // and each heading carries its own sub-groups.
    for (const group of [
      "Billing",
      "Receivables",
      "Finance",
      "Customers",
      "Operations",
      "Compliance",
    ]) {
      await expect(page.locator("[data-report-group]").filter({ hasText: group }).first()).toBeVisible();
    }
    await expect(page.locator("[data-report-group]")).toHaveCount(6);
    await expect(page.locator("[data-report-key]")).toHaveCount(45);
    await expect(page.locator("[data-report-key='ar_aging']")).toBeVisible();
    await expect(page.locator("[data-report-key='billing_register']")).toBeVisible();
    await expect(page.locator("[data-report-key='payments_by_method']")).toBeVisible();
    // p20 callout ①: the sub-line states the SHAPE of the catalogue, never an
    // availability count. The old one read "10 of 23 can be produced here".
    await expect(page.locator(".fin-rollup")).toContainText("45 reports · 6 groups · 19 sub-groups");
    await expect(page.locator(".fin-rollup")).not.toContainText("can be produced here");
  });

  // ── P1.7 · the two halves the audit-card case did not cover ───────────────
  test("P1.7: a search finds one report by name, SERVER-SIDE", async ({ page }) => {
    await signIn(page);
    await page.goto(`/${TENANT}/reports`);
    await expect(page.locator("[data-report-key]")).toHaveCount(45);

    await page.locator("[data-catalogue-search]").fill("ageing");
    // `P1.2`'s outcome verbatim: *"a search for ageing returns one card."*
    await expect(page.locator("[data-report-key]")).toHaveCount(1);
    await expect(page.locator("[data-report-key='ar_aging']")).toBeVisible();
    // The roll-up describes the CATALOGUE and not the page, so a search does
    // not rewrite what the sub-line says the catalogue holds.
    await expect(page.locator(".fin-rollup")).toContainText("45 reports");
  });

  test("P1.7: the group filter keeps one group and can be undone", async ({ page }) => {
    await signIn(page);
    await page.goto(`/${TENANT}/reports`);

    await page.locator("#catalogue-group").selectOption("finance");
    // Only groups with something in them are drawn (1·2B callout ④).
    await expect(page.locator("[data-report-group]")).toHaveCount(1);
    await expect(page.locator("[data-report-group='finance']")).toBeVisible();
    // The applied filter is a removable chip, and removing it restores the six.
    await expect(page.locator("[data-catalogue-chips]")).toContainText("Finance");
    await page.locator("[data-catalogue-chips] button").first().click();
    await expect(page.locator("[data-report-group]")).toHaveCount(6);
  });

  test("P1.7: Custom reads zero on day one and says so", async ({ page }) => {
    await signIn(page);
    await page.goto(`/${TENANT}/reports`);

    const strip = page.locator('[data-sub-tabs="catalogue-origin"]');
    await expect(strip.getByRole("tab", { name: /Custom/ })).toBeVisible();
    await strip.getByRole("tab", { name: /Custom/ }).click();
    // p20 callout ④: *"Custom reads 0 on day one and that is the point."*
    await expect(page.locator("[data-report-key]")).toHaveCount(0);
    await expect(page.locator("body")).toContainText("Nothing here yet.");
    // And the two holds, from the browser: neither control is on the screen.
    await expect(page.locator("body")).not.toContainText("Build your own");
    await expect(page.getByRole("tab", { name: "History" })).toHaveCount(0);
  });

  test("US-REP-001 TC-4: an unavailable card carries a reason and NO link", async ({ page }) => {
    await signIn(page);
    await page.goto(`/${TENANT}/reports`);

    const unavailable = page.locator("[data-report-key='read_completeness']");
    await expect(unavailable).toBeVisible();
    // THE ASSERTION THIS LANE WAS GIVEN AS A HARD CONSTRAINT: no page is drawn
    // over an absent read. The card is not an anchor and holds none.
    await expect(unavailable).not.toHaveAttribute("href", /./);
    await expect(unavailable.locator("a")).toHaveCount(0);
    // B14 rule 33: the reason is a FACT, six words. The paragraph of rationale
    // this card used to carry is REMOVED rather than shortened (`P1.3`).
    await expect(unavailable).toContainText("This report cannot be produced yet.");
    await expect(unavailable).not.toContainText("does not publish them as a report yet");

    // …while an AVAILABLE one is a link, so the two are visibly different
    // states rather than one state with a different colour.
    await expect(page.locator("a[data-report-key='ar_aging']")).toHaveAttribute(
      "href",
      `/${TENANT}/reports/ar-aging`,
    );
  });

  // ── P1.7 (part) · DEF-REP-6812 ────────────────────────────────────────────
  // **PROOF BY CLICKING FOR THE ONE DOOR THAT WAS OPENING THE WRONG SCREEN.**
  // The card linked to `/settings/audit-log`, which matches `settings/:tab`,
  // which SettingsPage resolves with `tabs.find(...) ?? tabs[0]` — so it opened
  // **Settings → Company** and looked, to every check this product had, like a
  // card that worked.
  //
  // The assertion is the DESTINATION AND THE SCREEN IT OPENS, both, because
  // either alone passes on the defect: the address matched a route, and a
  // heading assertion with no URL assertion would have read "Settings" happily
  // if someone renamed a tab. Hard-won law 2's mirror.
  //
  // ⚠ The other two halves of P1.7 — search and the group filter — landed with
  // P1.2/P1.3 on 2026-09-26 and are the three cases above.
  test("P1.7: the audit card opens the AUDIT LOG, not a Settings tab", async ({ page }) => {
    await signIn(page);
    await page.goto(`/${TENANT}/reports`);

    // The key moved with `reports/0003` — `user_activity_audit` → `audit_trail`
    // — and the door did not. Same report, same screen, different row.
    const card = page.locator("a[data-report-key='audit_trail']");
    await expect(card).toHaveAttribute("href", `/${TENANT}/audit-log`);
    await card.click();

    await expect(page).toHaveURL(new RegExp(`/${TENANT}/audit-log$`));
    await expect(page.getByRole("heading", { name: "Audit log", level: 1 })).toBeVisible();
    // The screen tag is the machine-readable half of the same fact, and it is
    // what tells the two Settings screens apart from this one.
    await expect(page.locator("body")).toHaveAttribute("data-screen-a1", "S61");
  });
});

test.describe("US-REP-002 · S46 — the viewer renders real figures @app-server", () => {
  test("US-REP-006: the billing register opens from the library and names the POSTING basis", async ({
    page,
  }) => {
    await signIn(page);
    await page.goto(`/${TENANT}/reports`);
    await page.locator("a[data-report-key='billing_register']").click();

    await expect(page).toHaveURL(new RegExp(`/${TENANT}/reports/billing-register`));
    await expect(page.getByRole("heading", { name: "Billing register", level: 1 })).toBeVisible();
    // BR-REP-001 on the page head, before any figure is read.
    await expect(page.locator(".fin-rollup")).toContainText("Posting date");
    // The table's own head, so a passing test cannot be one that rendered an
    // error panel with the right title above it.
    await expect(page.getByRole("columnheader", { name: "Bill #" })).toBeVisible();
    await expect(page.getByRole("columnheader", { name: "Amount" })).toBeVisible();
  });

  test("US-REP-007: the cash report names the CLEARING basis — the opposite label", async ({
    page,
  }) => {
    await signIn(page);
    await page.goto(`/${TENANT}/reports/payments-by-method`);

    await expect(page.getByRole("heading", { name: "Payments by method", level: 1 })).toBeVisible();
    await expect(page.locator(".fin-rollup")).toContainText("Clearing date");
    await expect(page.locator(".fin-rollup")).not.toContainText("Posting date");
    // BR-REP-014 made visible: purposes render on their own lines, outside any
    // collection figure.
    await expect(page.getByText("Purpose", { exact: true }).first()).toBeVisible();
  });

  test("US-REP-005: the ageing renders its bands and states what it cannot see", async ({
    page,
  }) => {
    await signIn(page);
    await page.goto(`/${TENANT}/reports/ar-aging`);

    await expect(page.getByRole("heading", { name: "AR aging summary", level: 1 })).toBeVisible();
    await expect(page.getByRole("columnheader", { name: "31–60 days" })).toBeVisible();
    await expect(page.getByRole("columnheader", { name: "Over 90 days" })).toBeVisible();
    // BR-REP-008 / BR-CUS-048 — the opening buckets are unbuilt and the report
    // says so on every run rather than footing short in silence.
    await expect(page.locator("body")).toContainText(
      "Balances brought in from your old system are not in these bands",
    );
  });

  test("BR-REP-024: no rendered page prints 'null', 'NaN' or a raw catalogue key", async ({
    page,
  }) => {
    await signIn(page);
    for (const segment of [
      "ar-aging",
      "billing-register",
      "revenue-by-service-rate",
      "payments-by-method",
    ]) {
      await page.goto(`/${TENANT}/reports/${segment}`);
      await expect(page.locator("h1")).toBeVisible();
      const text = (await page.locator("main").innerText()).toLowerCase();
      // The production defect of this morning was a tile reading `null USD`.
      expect(text).not.toContain("null");
      expect(text).not.toContain("nan");
      // A raw i18n key rendering to a user is G18's subject; this is the same
      // check where it can actually be seen.
      expect(text).not.toContain("reports.kpi.");
      expect(text).not.toContain("reports.col.");
    }
  });
});

// ── Lifecycle ─────────────────────────────────────────────
// packet: US-REP-001@c6c35b2 (co-packets US-REP-002/005/006/007; EP-REP-01 · EP-REP-02 · 12-reports/02-business-rules.md BR-REP-001/008/024)
// screens: S44 · S46
// generated: 2026-08-16 by story-coder (reports lane — step 2d)
// checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-09)
// gates: RED PROVED FIRST, PROPERLY, ON THE SECOND ATTEMPT (2026-08-16). The first attempt was worthless and is recorded rather than deleted: the worktree built for it resolved to a commit that ALREADY carried these screens, so the "before" run went green and proved nothing — a browser check that passes against the state it was written to reject is exactly the failure three lanes shipped this morning. Redone against a worktree pinned to 34c264c^ (84daebe, the commit before the screens landed), BUILT and served on the SAME origin and port as the green run so only the bundle differed. 5 of 6 FAILED, verbatim: `expect(locator).toBeVisible() failed · Locator: getByText('Financial', { exact: true }).first() · Error: element(s) not found`; `Locator: locator('[data-report-key=\'read_completeness\']') · Error: element(s) not found`; `Locator: getByRole('heading', { name: 'Payments by method', level: 1 }) · Error: element(s) not found`. The SIXTH — no 'null'/'NaN'/raw key in the rendered text — passed on the old bundle too, and that is honest rather than a hole: it guards the CONTENT of a page whose EXISTENCE the other five assert, and the old bundle rendered the NotBuiltYet placeholder, which contains none of those strings. Same six then run against the current bundle: 6 passed (3.4m), 46 assertions, all @app-server.
// exceptions: (1) the figures are the DEMO tenant's, so the assertions are about SHAPE, LABELS and ABSENCES rather than about specific amounts — the amounts are pinned in the backend suite against the LE/PE fixtures, where a wrong figure is a wrong figure rather than a wrong seed
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
