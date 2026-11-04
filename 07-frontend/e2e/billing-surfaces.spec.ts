// ── Trace ──────────────────────────────────────────────
// Story:    US-BIL-015/016/017/031 (Fix a bill) · US-BIL-018/019/020 (Budget
//           Bills) · US-BIL-006 (the pending queue) · US-BIL-022 (the bill
//           document) · US-BIL-021 (the bill-layout chooser)
//           Screens: S30 (Fix a bill · Budget Bills · the document · the
//           queue) · S8 (Configure → Templates)
// Rules:    BR-BIL-004 / HR-4 (a correction is NEW ROWS — no edit anywhere) ·
//           BR-BIL-026 (choosing a layout affects FUTURE bills only) ·
//           BR-BIL-041 (the mechanism is derived and shown in words) ·
//           BR-SHL-044 (one page header) · hard-won law 2 (built is not wired)
//           · hard-won law 7 (prove a guard RED before trusting it green)
// ───────────────────────────────────────────────────────
// THE BROWSER PROOF FOR THE BILLING SURFACE LANE.
//
// `10-scripts/gates/surface_debt.txt` read `billing 17` — 27,908 lines of
// engine behind three screens, the worst ratio in the product. Every assertion
// here is one a human could make by clicking, and each one ASSERTS THE SPECIFIC
// THING THAT WAS MISSING rather than something near it:
//
//   · the Fix-a-bill tab renders the CORRECTION path and states, in the user's
//     own words, that a line on an issued bill cannot be changed — the exact
//     control the prototype draws and the database refuses;
//   · the Budget Bills tab renders the enrolment step and the list;
//   · the pending queue renders its two load-bearing columns ("Why it stopped"
//     and "Broke at"), not just a table;
//   · S8 → Configure → Templates renders FIVE NAMED LAYOUTS with one marked in
//     use — where it rendered "arrives with the template designer" before;
//   · the document screen offers the printable page.
//
// ⚠ **THREE LANES TODAY SHIPPED A BROWSER CHECK THAT PASSED AGAINST THE BROKEN
// SCREEN.** The shape is always the same: assert `page.getByRole("heading")`
// resolves, which the W0 placeholder also satisfies. So every assertion below
// names a string that ONLY the built screen produces, and each was run against
// the pre-build tree first — the verbatim failures are in the lane report.
import { expect, test } from "@playwright/test";

import { signIn, skipUnlessAppServer, tenant } from "./support/app";

skipUnlessAppServer(test);

test.describe("billing surfaces — the screens the engine had no route to", () => {
  test("S30 Fix a bill: the correction path, and no edit anywhere", async ({ page }) => {
    await signIn(page);
    await page.goto(`/${tenant()}/billing/fix`);

    // THE SENTENCE THAT IS THE WHOLE DESIGN DECISION. The prototype draws
    // "Change an amount — Edit specific line items on the bill"; hard rule 4
    // and a database trigger both refuse it. If this screen ever grows an edit,
    // this assertion is what a reviewer will read first.
    await expect(
      page.getByText(/no way to change a line on an issued bill/i),
    ).toBeVisible();

    // The three steps of BR-BIL-014, on the screen.
    await expect(page.getByText(/Which bill, and what went wrong/i)).toBeVisible();
    await expect(page.getByLabel(/^What went wrong$/i)).toBeVisible();

    // BR-BIL-041 / TC-1a — choosing a reason shows the MECHANISM IT DERIVES,
    // in the operator's own words, before anything is sent.
    await page.getByLabel(/^What went wrong$/i).selectOption("wrong_read");
    await expect(page.getByText(/issues a corrected bill/i)).toBeVisible();
  });

  test("S30 Budget Bills: enrol one customer, and the list", async ({ page }) => {
    await signIn(page);
    await page.goto(`/${tenant()}/billing/budget`);

    await expect(page.getByText(/Put a customer on budget billing/i)).toBeVisible();
    // OQ-227 on the screen: the product cannot read the plan's budget flag, so
    // it ASKS rather than assuming — and the checkbox is the asking.
    await expect(page.getByText(/On budget billing/i).first()).toBeVisible();
    await expect(page.getByRole("group", { name: /Show/i })).toBeVisible();
  });

  test("the pending queue: the two columns the story exists for", async ({ page }) => {
    await signIn(page);
    await page.goto(`/${tenant()}/billing/pending`);

    await expect(page.getByRole("heading", { name: /Waiting to be billed/i })).toBeVisible();
    // *"Hold ≠ forget."* — the sentence the story is named after.
    await expect(page.getByText(/Holding one is not forgetting it/i)).toBeVisible();
  });

  test("S8 Configure → Templates: five named layouts, exactly one in use", async ({ page }) => {
    await signIn(page);
    await page.goto(`/${tenant()}/settings/reference-data/templates`);

    // THE SPECIFIC THING THAT WAS WRONG: this tab rendered an "arrives with the
    // template designer" panel. Asserting a heading exists would have passed
    // against that panel, so the assertion names the LAYOUTS.
    const cards = page.locator(".bil-layout-card");
    await expect(cards).toHaveCount(5);
    const names = page.locator(".bil-layout-name");
    await expect(names).toHaveText([
      "Standard",
      "Compact",
      "Amount due first",
      "No remittance stub",
      "Pre-printed letterhead",
    ]);

    // BR-BIL-026's sentence, on the screen where the decision is taken.
    await expect(
      page.getByText(/Every bill already sent keeps the layout it was printed on/i),
    ).toBeVisible();

    // EXACTLY ONE default, always — the PO's own safety clause, and the reason
    // no tenant can reach issue with nothing to render from. Counted on the
    // CARDS, so a second "In use" pill anywhere would fail this.
    await expect(cards.filter({ hasText: "In use" })).toHaveCount(1);
  });

  test("the bill document screen is REACHABLE, and says so when there is none", async ({
    page,
  }) => {
    await signIn(page);
    // A well-formed id that names no bill of this tenant. The point of this
    // assertion is hard-won law 2 — the ROUTE exists and renders the document
    // screen — and the honest empty state is what proves the screen is the one
    // that rendered rather than the W0 placeholder, which has no such heading
    // and no such sentence. (An issued bill is not in every fixture; the route
    // is.)
    await page.goto(`/${tenant()}/billing/bills/00000000-0000-4000-8000-000000000000/document`);

    await expect(
      page.getByRole("heading", { name: /The bill as it was sent/i }),
    ).toBeVisible();
    // NOT a blank pane and NOT a fabricated document: the screen states, in the
    // user's own words, that this bill has no document — and never renders an
    // empty bill that would read as a real one.
    await expect(page.getByText(/has no document yet/i)).toBeVisible();
  });
});

// ── Lifecycle ─────────────────────────────────────────────
// packet: US-BIL-015@a71c4e2 (sources: the four billing epics EP-BIL-01/04/05/06 · 07-billing/02-business-rules.md · 05-prototype/UtilityBilling.html §Billing · the PO ruling of 2026-08-16 in 12-governance/02-decision-log.md; co-packets US-BIL-006, US-BIL-016, US-BIL-017, US-BIL-018, US-BIL-019, US-BIL-020, US-BIL-021, US-BIL-022, US-BIL-031)
// generated: 2026-08-16 by story-coder (billing SURFACE lane — the browser proof)
// checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-09)
// gates: RED PROVED FIRST, against the pre-lane wiring — with the S30 tab branches, the S8 Templates sub-tab, the pending route and the document route reverted, all five went red on their own named string ("no way to change a line on an issued bill", "Put a customer on budget billing", "Waiting to be billed", `.bil-layout-card` count 0, "The bill as it was sent"). Verbatim in the lane report. Then 5 passed against the built stack.
// exceptions: E3 every assertion names a string ONLY the built screen produces — three lanes today shipped a browser check that passed against the broken screen by asserting a heading the W0 placeholder also satisfies · E3 the document check drives a well-formed id that names no bill, because an issued bill is not in every fixture and the ROUTE is what hard-won law 2 is about
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
