// @vitest-environment jsdom
// ── Trace ──────────────────────────────────────────────
// Story:   US-MET-002 (S15 unit detail — the Account tab) · CR-089 wave I
//          Screens: S15 (PRM-03) · the destination S20 (ACC-06)
// Rules:   BR-SHL-025 (a control this path cannot offer renders DISABLED WITH
//          ITS REASON) · BR-CUS-030 (closing an account is the move-out flow)
//          · CLAUDE.md hard-won law 2's MIRROR (a live screen behind a dead
//          control — DEF-CWP-3925, 2026-09-05)
// ───────────────────────────────────────────────────────
// **THIS IS THE TEST THAT FIRES THE DAY THE DOOR LANDS.**
//
// `CR-089` wave I says `Move-out…` stays held on the unit's Account tab and is
// not built there. Hard-won law 2's mirror says a hold with no test that fires
// when it expires is a promise nobody is keeping:
//
//     "WHEN YOU WRITE A HOLD, WRITE THE TEST THAT FIRES WHEN THE HOLD EXPIRES,
//      in the same commit — assert the destination by ADDRESS and by the screen
//      id it opens, so the day the screen lands the suite goes red and names
//      it."
//
// ⚠ **AND ON THIS PARTICULAR HOLD THE SCREEN HAS ALREADY LANDED** — which is
// exactly the state that law describes and is `DEF-CUS-4702`. `MoveOutWizard`
// has been routed at `/:tenant/accounts/:accountId/move-out` since 2026-08-25;
// the refusal on this tab went on saying *"This unit has no door to it yet"*,
// which a clerk reads as *the flow is not built*. The hold is CORRECT (this
// unit owns no door to that flow and building one is another wave's) and the
// SENTENCE was not. So this file pins three things at once:
//
//   1. the destination EXISTS, by address and by screen id, in the registry —
//      so the address in the refusal's story cannot rot silently;
//   2. the refusal's words point AT that flow rather than denying it exists;
//   3. **the moment the control stops being disabled, it must carry that exact
//      address** — which is the assertion that fires the day somebody builds
//      the door and forgets to lift the hold.
import "@/i18n";
import "@testing-library/jest-dom/vitest";

import { describe, expect, it } from "vitest";

import { SCREEN_ROUTES } from "@/routing/screenIds";

import { quietAnswer, renderAccountTab, TEST_TENANT } from "./unitAccountFixture";

/** The address the move-out flow lives at, written once and asserted twice. */
const MOVE_OUT_ROUTE = "/:tenant/accounts/:accountId/move-out";

describe("CR-089 I · the Move-out hold on the unit's Account tab", () => {
  it("the destination exists in the registry, by address AND by screen id", () => {
    // ⚠ **BY ID, NOT ONLY BY ADDRESS.** An address can be re-pathed by a lane
    // tidying routes; the SCREEN is what the refusal is about. `S20`/`ACC-06`
    // is the pair `12-governance` tickets name, so pinning both means a rename
    // in either direction lands here rather than in a bug report.
    const row = SCREEN_ROUTES.find((screen) => screen.path === MOVE_OUT_ROUTE);
    expect(
      row,
      `the move-out flow is not registered at ${MOVE_OUT_ROUTE} — the refusal on the ` +
        "unit's Account tab points at a screen that no longer exists there",
    ).toBeDefined();
    expect(row?.ids.a1).toBe("S20");
    expect(row?.ids.r10).toBe("ACC-06");
  });

  it("the refusal says where the flow lives — it does not claim the flow is unbuilt", () => {
    const html = renderAccountTab(quietAnswer());
    // The hold stands.
    expect(html).toContain("Move-out…");
    expect(html).toContain("disabled");
    // And it names the destination in words a clerk can act on.
    expect(html).toContain("Move-out runs from the account");
    expect(html).toContain("Open it to start.");
    // ⚠ The sentence this replaced. It is asserted ABSENT rather than merely
    // not asserted present: a lane restoring the old copy would otherwise
    // re-ship a refusal that denies a screen which is live.
    expect(html).not.toContain("no door to it yet");
    // The way through is the button beside it, and it must be a real address.
    expect(html).toContain(`href="/${TEST_TENANT}/accounts/acc-1"`);
  });

  it("FIRES THE DAY THE DOOR LANDS: an enabled Move-out must carry the move-out address", () => {
    // ⚠ **THIS IS THE WHOLE POINT OF THE FILE AND IT IS DELIBERATELY
    // CONDITIONAL.** Today the control is disabled and the second branch does
    // not run. The day a lane wires a door from the unit — and every reason to
    // do so is a good one — this assertion starts running and requires the
    // control to lead to `S20` at the account's own address. A hold that is
    // lifted onto nothing, or onto the plan modal next door (which is
    // `DEF-594`'s original shape), fails HERE and names the screen.
    const html = renderAccountTab(quietAnswer());
    const control = /<button[^>]*>Move-out…<\/button>|<a[^>]*>Move-out…<\/a>/.exec(html);
    expect(control, "the Move-out control is not on the tab at all").not.toBeNull();
    const markup = control?.[0] ?? "";
    if (markup.includes("disabled")) {
      // Still held. `BR-SHL-025` requires the reason to be ON the control, so
      // a held button with no reason fails even while the hold is correct.
      expect(markup).toContain("title=");
      return;
    }
    expect(
      markup,
      "Move-out is no longer held on the unit's Account tab, so it must open the " +
        "move-out flow (S20 / ACC-06) at /{tenant}/accounts/{accountId}/move-out",
    ).toContain("/accounts/acc-1/move-out");
  });

  it("a common area is not offered a move-out at all", () => {
    // A common area never had a tenant, so *held* would be the wrong word for
    // it: there is nothing to move out of. The control is absent rather than
    // drawn and refused — `BR-SHL-025` is about a control this ROLE cannot use,
    // not one this THING does not have.
    const answer = quietAnswer();
    answer.unit.is_common_area = true;
    const html = renderAccountTab(answer);
    expect(html).not.toContain("Move-out…");
  });
});

// ── Lifecycle ─────────────────────────────────────────────
// packet: CR-089 wave I · DEF-CUS-4702 · hard-won law 2's mirror
// generated: 2026-09-08 by the CR-089 wave I build lane
// checklist: A=n/a B=n/a C✔ D=n/a E✔ F✔ G✔ H=n/a
// gates: vitest src/features/metering/UnitAccountMoveOutHold.dom.test.tsx
// exceptions: E3 the third case is CONDITIONAL by design — it is inert while the hold stands and becomes the assertion the day it is lifted
// ──────────────────────────────────────────────────────────
