// ── Trace ──────────────────────────────────────────────
// Story:    US-BIL-002 (S31.2 "Check what we found")   Screens: S31.2
// Rules:    BR-BIL-039 (the preview and the real run are the SAME code) ·
//           BR-SHL-020 (a refusal reads as a sentence, not a code) ·
//           BR-RAT-087 (the server formats money; the client never does)
// ───────────────────────────────────────────────────────
// STEP 3 OF THE R1–R7 CUTOVER, ON SCREEN.
//
// ⚠ EVERY ASSERTION HERE IS A WAY THE PANEL COULD QUIETLY LIE, and each one is
// a sentence out of the decision log rather than a preference:
//
//   1. "READ THE THIRD AND FOURTH NUMBERS TOGETHER OR THEY LIE. '0 disagreed'
//      is also what perfect agreement looks like." So the attempted count must
//      be on screen beside the disagreement count, ALWAYS.
//   2. "A count that is always zero means the chain is not running, and nothing
//      else would say so." So a run that compared nothing says so in words.
//   3. "A lane that makes the disagreements go away has destroyed the evidence
//      this job exists to produce." So both figures render and no difference
//      between them is computed anywhere.
//   4. Rendering the exception class name instead of the refusal sentence is
//      "the lazy way to make the first test pass" — asserted against.
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import "@/i18n";
import i18n from "@/i18n";

import type {
  BillRunPricingShadow,
  PricingShadowAccount,
  PricingShadowClass,
} from "@/api/endpoints";

import {
  PricingShadowPanel,
  isPricingShadow,
  shadowAccountsToList,
  shadowFigure,
  shadowMeasuredNothing,
} from "./billRunShared";

const t = i18n.getFixedT("en");

function shadow(over: Partial<BillRunPricingShadow> = {}): BillRunPricingShadow {
  return {
    accounts: 1,
    attempted: 1,
    agreed: 0,
    disagreed: 1,
    chain_refused: 1,
    not_attempted: 0,
    by_step: { R1: 1 },
    blocked_by_reason: {},
    steps: [{ step: "R1", accounts: ["ACC-1042"], count: 1, refusals: 1, divergences: 0 }],
    classes: [refusalClass()],
    blocked_classes: [],
    accounts_detail: [refusedAccount()],
    ...over,
  };
}

function refusalClass(over: Partial<PricingShadowClass> = {}): PricingShadowClass {
  return {
    class_id: "R1 · NoPlanInForce",
    kind: "refusal",
    step: "R1",
    what: "NoPlanInForce",
    refusal_type: "NoPlanInForce",
    services: [],
    accounts: 412,
    occurrences: 412,
    example_account_no: "ACC-1042",
    example_sentence:
      "R1: account ACC-1042 has no plan version in force on 2026-07-01.",
    example_service: null,
    example_live: null,
    example_chain: null,
    example_live_display: null,
    example_chain_display: null,
    example_live_summary: "Residential Standard (v1) — electric base 18.50 on version 7",
    is_money: false,
    ...over,
  };
}

function refusedAccount(over: Partial<PricingShadowAccount> = {}): PricingShadowAccount {
  return {
    account_id: "acc-1",
    account_no: "ACC-1042",
    status: "chain_refused",
    refusal_step: "R1",
    refusal_type: "NoPlanInForce",
    refusal_sentence:
      "R1: account ACC-1042 has no plan version in force on 2026-07-01.",
    blocked_reason: null,
    blocked_detail: null,
    live_summary: "Residential Standard (v1) — electric base 18.50 on version 7",
    divergences: [],
    ...over,
  };
}

function render(body: BillRunPricingShadow): string {
  return renderToStaticMarkup(<PricingShadowPanel t={t} shadow={body} />);
}

describe("the pricing comparison panel", () => {
  it("prints the attempted count in the SAME sentence as the disagreement count", () => {
    const html = render(shadow({ accounts: 1247, attempted: 1247, disagreed: 14 }));
    // The decision log's own example sentence: "the ruled path and the live
    // path disagree on 14 of 1,247 accounts."
    expect(html).toContain("1247");
    expect(html).toContain("14");
    // ⚠ AND THE TWO ARE ONE STRING, so no future edit can drop one and keep the
    // other. Asserted on the element, not on the page: a count that also appears
    // in the chrome would pass a page-wide search over an empty panel.
    const counts = html.match(/data-brun="shadow-counts"[^>]*>([^<]*)</);
    expect(counts).not.toBeNull();
    expect(counts?.[1]).toContain("1247");
    expect(counts?.[1]).toContain("14");
  });

  it("says in words that nothing was compared, rather than printing a clean zero", () => {
    const nothing = shadow({
      accounts: 1247,
      attempted: 0,
      disagreed: 0,
      chain_refused: 0,
      not_attempted: 1247,
      by_step: {},
      steps: [],
      classes: [],
      blocked_classes: [
        {
          reason: "connection_size_unresolved",
          accounts: 1247,
          example_account_no: "ACC-1042",
          example_detail: "service 'electric' has no connection size",
        },
      ],
      accounts_detail: [],
    });
    expect(shadowMeasuredNothing(nothing)).toBe(true);
    const html = render(nothing);
    expect(html).toContain('data-brun="shadow-nothing"');
    expect(html).toContain("not as good news");
    // ⚠ AND THE COULD-NOT-CHECK REASON IS ON SCREEN WITH ITS COUNT, because a
    // person has to be told what to go and do.
    expect(html).toContain("No connection size on the meter");
    expect(html).toContain('data-brun="shadow-blocked"');

    // The OTHER reading of "0 disagreed" — real agreement — must not draw it.
    const agreed = shadow({
      attempted: 1247,
      accounts: 1247,
      agreed: 1247,
      disagreed: 0,
      chain_refused: 0,
      by_step: {},
      steps: [],
      classes: [],
      accounts_detail: [],
    });
    expect(shadowMeasuredNothing(agreed)).toBe(false);
    expect(render(agreed)).not.toContain('data-brun="shadow-nothing"');
  });

  it("renders BOTH figures for a money disagreement and computes no difference", () => {
    const money = shadow({
      chain_refused: 0,
      by_step: { "R3/R4": 1 },
      classes: [
        refusalClass({
          class_id: "R3/R4 · the two paths resolved different figures",
          kind: "divergence",
          step: "R3/R4",
          what: "the two paths resolved different figures",
          refusal_type: null,
          services: ["water"],
          accounts: 3,
          example_live: "18.5000",
          example_chain: "22.0000",
          example_live_display: "18.50",
          example_chain_display: "22.00",
          example_live_summary: null,
          is_money: true,
          example_sentence:
            "R3/R4 water: the live path says '18.5000', the ruled path says '22.0000'",
        }),
      ],
    });
    const html = render(money);
    // ⚠ ASSERTED ON THE TWO CELLS, NOT ON THE PAGE. A page-wide search for
    // "18.50" also matches the example SENTENCE two cells away, so a panel that
    // had dropped the live column entirely would still pass one — proved by
    // mutation before this line was written this way.
    const live = html.match(/data-brun="shadow-live"[^>]*>([\s\S]*?)<\/td>/);
    const ruled = html.match(/data-brun="shadow-ruled"[^>]*>([\s\S]*?)<\/td>/);
    expect(live?.[1]).toContain("18.50");
    expect(ruled?.[1]).toContain("22.00");
    // Both, side by side — the SERVER's own display strings (BR-RAT-087).
    expect(html).toContain("18.50");
    expect(html).toContain("22.00");
    // ⚠ AND NOTHING SUBTRACTS THEM. 22.00 − 18.50 = 3.50, and a difference on
    // screen would be this client deciding which figure is the right one — the
    // ruling that belongs to the Product Owner (step 4).
    expect(html).not.toContain("3.50");
    // The account count is what makes the class rulable at all.
    expect(html).toContain('data-brun="shadow-class-accounts">3<');
  });

  it("shows the refusal's own SENTENCE, and what today's billing would have used", () => {
    const html = render(shadow());
    expect(html).toContain("has no plan version in force");
    // ⚠ NOT THE EXCEPTION CLASS NAME AS THE THING A PERSON READS. The type is
    // allowed to be in the class label a developer greps; the SENTENCE is what
    // carries the finding, and it is present.
    expect(html).toContain("Residential Standard (v1)");
    expect(html).toContain("Billing today would have used");
  });

  it("lists the accounts worth acting on and never buries them in a total", () => {
    const mixed = shadow({
      accounts: 3,
      attempted: 3,
      agreed: 1,
      disagreed: 1,
      chain_refused: 1,
      not_attempted: 1,
      blocked_by_reason: { account_has_no_plan: 1 },
      blocked_classes: [
        {
          reason: "account_has_no_plan",
          accounts: 1,
          example_account_no: "ACC-1099",
          example_detail: "account ACC-1099 carries no rate plan",
        },
      ],
      accounts_detail: [
        refusedAccount(),
        refusedAccount({
          account_id: "acc-2",
          account_no: "ACC-2001",
          status: "agreed",
          refusal_step: null,
          refusal_type: null,
          refusal_sentence: null,
          live_summary: null,
        }),
        refusedAccount({
          account_id: "acc-3",
          account_no: "ACC-1099",
          status: "not_attempted",
          refusal_step: null,
          refusal_type: null,
          refusal_sentence: null,
          blocked_reason: "account_has_no_plan",
          blocked_detail: "account ACC-1099 carries no rate plan",
          live_summary: null,
        }),
      ],
    });
    // An account that agreed has nothing for a person to do; its COUNT is in
    // the sentence above the table, so nothing is hidden — only un-listed.
    expect(shadowAccountsToList(mixed).map((row) => row.account_no)).toEqual([
      "ACC-1042",
      "ACC-1099",
    ]);
    const html = render(mixed);
    expect(html).toContain("ACC-1042");
    expect(html).toContain("ACC-1099");
    expect(html).not.toContain("ACC-2001");
    // ⚠ THREE OUTCOMES, THREE WORDINGS. "Could not work it out" is never shown
    // in the words used for agreement.
    expect(html).toContain("New rules would not price it");
    expect(html).toContain("Could not work it out");
  });

  it("renders NOTHING over a body it cannot read, and never a row of zeros", () => {
    // ⚠ **DEF-2402, AND IT IS THE FAILURE THE SEPARATE ENDPOINT EXISTS TO
    // PREVENT, ARRIVING THROUGH THE RENDERING.** A server that predates this
    // endpoint answers the generic empty-list envelope. The first version of
    // this component read `accounts_detail.filter(...)` straight off it and
    // threw, taking down the WHOLE of "Check what we found" — the stage a
    // clerk cannot bill without. Found by an existing test in another file,
    // before merge.
    const notAShadow = { count: 0, next: null, previous: null, results: [] };
    expect(isPricingShadow(notAShadow)).toBe(false);
    expect(isPricingShadow(shadow())).toBe(true);
    expect(() =>
      render(notAShadow as unknown as BillRunPricingShadow),
    ).not.toThrow();
    expect(render(notAShadow as unknown as BillRunPricingShadow)).toBe("");

    // ⚠ AND IT MUST NOT DEFAULT THE COUNTS. Rendering "0 of 0 customers, 0 came
    // out differently" over a server that never answered is the exact reading
    // the decision log says to distrust, manufactured by the client.
    expect(render(notAShadow as unknown as BillRunPricingShadow)).not.toContain(
      "came out differently",
    );

    // A body that carries the counts but not yet the groupings still renders —
    // absent lists are absent, not a crash.
    const countsOnly = {
      accounts: 3,
      attempted: 3,
      agreed: 3,
      disagreed: 0,
      chain_refused: 0,
      not_attempted: 0,
      by_step: {},
      blocked_by_reason: {},
    };
    const html = render(countsOnly as unknown as BillRunPricingShadow);
    expect(html).toContain("3");
    expect(html).toContain("Nothing came out differently");
  });

  it("prefers the server's display string and never invents one", () => {
    // BR-RAT-087 — the server formats; this only chooses which served string to
    // print, and answers null rather than composing one when neither arrived.
    expect(shadowFigure("18.5000", "18.50")).toBe("18.50");
    expect(shadowFigure("v7", null)).toBe("v7");
    expect(shadowFigure(null, null)).toBeNull();
  });
});
