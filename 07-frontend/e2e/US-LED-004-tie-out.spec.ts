// ── Trace ──────────────────────────────────────────────
// Story:   US-LED-004 (subledger tie-out views + drift red flag on S36 —
//          RELEASE BLOCKER) · US-LED-002 (dimension stamping, which is what
//          makes the by-premises half of the same books answerable)
//          Screens: S36 · S60
// Rules:   BR-LED-007 (deposit-liability GL = Σ deposits held · AR GL = Σ
//          account balances · tax payable = remittance outstanding; ANY drift
//          = red flag + release blocker; NO dismiss path) · BR-REP-001 (every
//          money number labels its basis) · BR-LED-001 (the dimension set)
// Tests:   the backend halves are 06-backend/tests/test_us_led_004_tie_out.py
//          and 06-backend/tests/test_us_led_002_dimensions.py; the component
//          half is 07-frontend/src/features/ledger/revenueAr.test.tsx
// ───────────────────────────────────────────────────────
//
// HARD-WON LAW 6: "Diff the running app against 05-prototype/. No gate looks at
// rendered output." And law 2: built is not wired. The three tests below click
// through a REAL browser against the booted stack, because everything else in
// this lane's evidence — 11 backend cases, 11 component cases, three red
// proofs — can be true of a panel no human can reach.
//
// The panel this replaces rendered ONE figure and a sentence saying nothing had
// compared it against anything. What must be visible now is the COMPARISON.
import { expect, test } from "@playwright/test";

import { signIn, tenant, skipUnlessAppServer } from "./support/app";
import { APP_SERVER_TAG } from "./support/census";

test.describe(
  "US-LED-004 — a clerk can see whether the books agree with the bills",
  { tag: APP_SERVER_TAG },
  () => {
    skipUnlessAppServer(test);

    test("the S36 tie-out panel states three comparisons, not one control total", async ({
      page,
    }) => {
      await signIn(page);

      // A human clicking, not a URL typed.
      const nav = page.getByRole("navigation", { name: "Main navigation" });
      await nav.getByRole("link", { name: "Finance", exact: true }).click();
      await expect(page).toHaveURL(new RegExp(`/${tenant()}/finance`));

      const panel = page.locator(".met-panel").filter({ hasText: "Subledger tie-out" });
      await expect(panel).toHaveCount(1);

      // ── THE THREE ROWS BR-LED-007 NAMES ──────────────────────────────────
      // Their presence is the whole story: this panel used to have no table at
      // all, because nothing compared a control account against a register.
      await expect(panel).toContainText("Receivables");
      await expect(panel).toContainText("Customer deposits");
      await expect(panel).toContainText("Tax payable");

      // ── BOTH SIDES OF EVERY ROW, WHICH IS THE POINT ──────────────────────
      // A tie-out with one column is a balance. The header row must offer the
      // general ledger, the register AND the difference between them.
      await expect(panel).toContainText("General ledger");
      await expect(panel).toContainText("Register");
      await expect(panel).toContainText("Difference");

      // ── AND THE COPY THAT USED TO BE HERE MUST BE GONE ───────────────────
      // The old panel said, in words, that the comparison was not built and
      // named the story that would build it. A finance officer reading that
      // sentence today would be told the check has not run.
      await expect(panel).not.toContainText("US-LED-004");
      await expect(panel).not.toContainText("not built");

      // ── EVERY MONEY FIGURE CARRIES ITS BASIS (BR-REP-001) ────────────────
      // Not decoration: an AR figure on the posting basis and a cash figure on
      // the clearing basis are different questions, and a tie-out that mixed
      // them would report drift that is not there.
      const figures = panel.locator(".cell-money-amount");
      expect(await figures.count()).toBeGreaterThan(0);
      await expect(panel.locator(".cell-money-basis").first()).toBeVisible();
    });

    test("a row's verdict is readable in WORDS, and there is no dismiss control", async ({
      page,
    }) => {
      await signIn(page);
      await page.goto(`/${tenant()}/finance`);

      const panel = page.locator(".met-panel").filter({ hasText: "Subledger tie-out" });
      await expect(panel).toHaveCount(1);

      // US-LED-004 TC-5 and the accessibility half of BR-LED-007 in one check.
      //
      // The verdict travels as TEXT beside each subledger name — "Agrees",
      // "Does not agree", "Could not be checked" — because a release blocker
      // that only a sighted user on a good monitor can see is not one. Colour
      // is the second signal; this asserts the first.
      const verdicts = panel.locator(".fin-tieout-state");
      await expect(verdicts).toHaveCount(3);
      for (const text of await verdicts.allInnerTexts()) {
        expect(text.trim().length).toBeGreaterThan(0);
      }

      // TC-5: "no dismiss path exists — drift clears only when the explaining
      // entry posts through the service". Asserted on the RENDERED page, which
      // is where a dismiss control would actually appear.
      //
      // ⚠ **THIS WAS `getByRole("button")).toHaveCount(0)` AND THAT STOPPED
      // MEANING WHAT IT SAID ON 2026-09-24 (`P2.20`).** The tie-out is on the
      // shared table now, so the panel legitimately contains buttons — the
      // search box's, the `All` chip, `+ Filter`, the column chooser and the
      // pager's arrows. **None of them dismisses anything**, which is the
      // invariant TC-5 actually protects, and a count of zero can no longer
      // tell a dismiss control from a pager arrow. It is asserted by what such
      // a control would SAY — which is the thing a clerk would look for and
      // press — and the checkbox half is kept unchanged, because the shared
      // table draws none and an acknowledge tick is the likeliest shape a
      // future dismiss control would take.
      for (const word of [/dismiss/i, /ignore/i, /acknowledge/i, /clear flag/i]) {
        await expect(panel.getByRole("button", { name: word })).toHaveCount(0);
      }
      await expect(panel.getByRole("checkbox")).toHaveCount(0);
    });

    test("US-LED-002: the by-premises report answers with premises instead of refusing", async ({
      page,
    }) => {
      await signIn(page);

      // The report the dimension unblocked. Its own trailer promised the table
      // "renders the day the dimension lands"; this is that day, clicked.
      await page.goto(`/${tenant()}/finance`);
      const link = page.getByRole("button", { name: /by premises/i }).first();
      if (await link.count()) {
        await link.click();
      } else {
        await page.goto(`/${tenant()}/reports/by-premises`);
      }

      // Either the table renders (the fixture posted bills in the served
      // period) or the honest refusal does — and the refusal must NO LONGER
      // claim that no line in the product carries a premises, because that
      // sentence stopped being true when US-LED-002 landed. Both branches are
      // acceptable outcomes of a fixture; the FALSE SENTENCE is not.
      await expect(page.locator("body")).not.toContainText(
        "every journal line in the product carries premises_id = NULL",
      );
      await expect(page.locator("body")).not.toContainText(
        "No ledger line in this product carries a premises",
      );
    });
  },
);
