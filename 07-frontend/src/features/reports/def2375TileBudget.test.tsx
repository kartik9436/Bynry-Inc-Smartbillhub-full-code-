// ── Trace ──────────────────────────────────────────────
// Defect:  DEF-2375 — three dashboard tiles printed a three-line paragraph each,
//          always on screen.  Screens: S7 (Dashboard)
// Rules:   B14 rule 32 — "a screen has a DESCRIPTION BUDGET — one sentence per
//          section; a stated absence is a `<details>` CLOSED by default"
//          (RATIFIED 2026-08-31, PO, four times: "too much content -
//          desctiption is too much for clark to read") · BR-REP-024
// ───────────────────────────────────────────────────────
/**
 * **THE SECOND TIME THE PRODUCT OWNER RAISED THIS, ON A SCREEN WHOSE OWN
 * COMMENT SAID IT HAD BEEN HANDLED.**
 *
 * `DashboardPage.tsx` already argued the right thing — the reason *"moves to
 * the tile's SUPPORT text, where somebody diagnosing a problem can reach it and
 * a clerk reading the screen is not made to"* — and then rendered it as a bare
 * `<span>` that is always visible. A comment claiming a guarantee is not the
 * guarantee (hard-won law 1). Three tiles side by side, each with a paragraph
 * about which module publishes which counter, is what the PO saw.
 *
 * ⚠ **RULE 32's OWN STATUS NOTE SAYS ITS CLAUSES ARE UNENFORCED, BECAUSE NO
 * GATE READS RENDERED OUTPUT.** So this asserts the RENDERED MARKUP: the
 * disclosure must exist, must be closed, and the paragraph must be inside it.
 * That is the only kind of check that can catch this shape.
 *
 * RED FIRST, quoted from the run against the shipped `<span>`:
 *   `expected '<span class="fin-absent-reason" role="note">Payments publishes
 *    the fifty…' to contain '<details'`
 *
 * The reason is NOT deleted and NOT shortened. It is the honest explanation of
 * a figure this product refuses to guess at, support needs it, and every
 * assertion below keeps it reachable — it is simply not in a clerk's way.
 */
import "@/i18n";

import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import i18n from "i18next";

import { dashboardKpis } from "./DashboardPage";

const t = i18n.getFixedT(null, null) as (k: string, o?: Record<string, unknown>) => string;

const GAP = "failed_payment_count_is_not_published_by_payments";
const GAPS = [
  {
    code: GAP,
    detail:
      "Payments publishes the fifty most recent failed payments for its own screen, " +
      "not a count of all of them.",
  },
];

function absentTileMarkup(): string {
  const tiles = dashboardKpis(
    [
      {
        id: "failed_payments",
        kind: "count",
        label: "Failed payments",
        value: null,
        display: null,
        basis: "posting",
        sub: null,
        unavailable_code: GAP,
      } as never,
    ],
    GAPS as never,
    t,
  );
  return renderToStaticMarkup(
    <>{tiles.map((k) => ("value" in k ? [k.value, k.detail] : null))}</>,
  );
}

describe("DEF-2375 — a tile's stated absence is a closed disclosure", () => {
  it("wraps the reason in a <details>", () => {
    expect(absentTileMarkup()).toContain("<details");
  });

  it("is CLOSED by default — the paragraph is not on screen until asked for", () => {
    const html = absentTileMarkup();
    // `open` on the element is the whole failure mode: a <details open> is a
    // paragraph wearing a disclosure's clothes.
    expect(html).not.toMatch(/<details[^>]*\sopen/);
  });

  it("keeps the reason reachable, not deleted", () => {
    const html = absentTileMarkup();
    expect(html).toContain("fifty");
    expect(html).toMatch(/role="note"/);
  });

  it("still says what is true in the tile itself", () => {
    const html = absentTileMarkup();
    expect(html).toContain("Not counted yet");
    // The two wordings ruled against previously must not return by the back door.
    expect(html).not.toContain("Not available");
    expect(html.toLowerCase()).not.toContain("not received");
  });

  it("the summary is a short prompt, not a second copy of the sentence", () => {
    const summary = t("dashboard.kpi.whyNotCounted");
    expect(summary.length).toBeLessThanOrEqual(24);
    expect(summary).not.toContain("Payments");
  });
});
