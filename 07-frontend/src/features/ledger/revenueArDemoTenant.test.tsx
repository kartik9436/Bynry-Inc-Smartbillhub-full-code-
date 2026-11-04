// ── Trace ──────────────────────────────────────────────
// Story:    US-LED-007 (S36 Revenue & AR)  Screens: S36
// Rules:    BR-LED-016 · BR-REP-001 · BR-REP-002 · BR-SHL-023 (one money path) ·
//           CLAUDE.md rule 2 · CLAUDE.md hard-won law 6 (look at the RENDERED app)
// ───────────────────────────────────────────────────────
// DEF-176 — THE FIXTURE IS THE DEFECT, SO THIS FILE HOLDS NO FIXTURE.
//
// `revenueAr.test.tsx` mounts this screen with `revenue_by_service: []`. Every
// assertion in it is correct and the screen it proves is dead: on the seeded
// demo tenant the table has ONE row, and rendering that row threw
// `MoneyAmountAbsent`, which React Router caught at the ROUTE, so a finance
// officer clicking Finance got no page at all — no sidebar, no tabs, nothing but
//
//     Unexpected Application Error!
//     MoneyCell was handed an absent amount for USD. …
//
// 27 gates, golden 33/33, 2,938 backend and 1,250 frontend tests were green
// while that screen was dead, because no test in the product had ever mounted it
// with a row in that table.
//
// ══════════════════════════════════════════════════════════════════════════
// WHERE THIS PAYLOAD CAME FROM — RECORDED, NOT WRITTEN
// ══════════════════════════════════════════════════════════════════════════
// It is the response body of
//
//     GET /api/brazosbend/finance/revenue-ar?from=2026-08-01&to=2026-08-31
//
// read off a PostgreSQL database provisioned by `manage.py load_sample_data`
// (`sbh_verify_demo`) on 2026-08-16, signed in as dana@brazosbendutilities.com.
// Copied field for field. Nothing here was chosen to make a point: `tax` and
// `collected` are absent from the row below because the server did not send
// them, `written_off_ytd` is null because the caller stated no fiscal year, and
// six figures are absent in total.
//
// **Two fields are abbreviated and it is safe: `detail` and `wanted_reads`.**
// `financeShared.gapSentence` renders THIS APP's catalogue keyed on the server's
// `code` and never the server's prose (TD-16/B8), so no assertion below can see
// them. Everything a screen reads is verbatim.
//
// To re-record after a wire change:
//     curl -s -b <cookiejar> \
//       "$SPA/api/brazosbend/finance/revenue-ar?from=2026-08-01&to=2026-08-31"
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import "@/i18n";
import i18n from "@/i18n";

import type { RevenueArResponse } from "@/api/endpoints";

import {
  AdjustmentsPanelView,
  GAP_AGING,
  GAP_COLLECTION_PCT,
  GAP_DSO,
  GAP_LATE_FEES,
  GAP_SERVICE_COLUMNS,
  GAP_WRITTEN_OFF_YTD,
  RevenueByServiceTable,
  S36_CLAIMED_GAPS,
  UnclaimedGaps,
  revenueArKpis,
} from "./RevenueArPage";
import { KPIStrip } from "@/components/KPIStrip";

const t = i18n.getFixedT("en");

/** One `unavailable` entry, with its `detail` abbreviated (see the header). */
function gap(code: string, brRef: string) {
  return { code, br_ref: brRef, detail: "(abbreviated — the screen never renders it)" };
}

/**
 * The recorded wire. **`tax` and `collected` are missing on purpose** — the
 * server omits them, `endpoints.ts` declares them as required members, and the
 * gap between those two facts is the whole defect. The cast is what a real
 * response does to a type that turned out to be a claim rather than a fact.
 */
export const DEMO_TENANT_REVENUE_AR = {
  basis: "posting",
  currency: "USD",
  period: { start: "2026-08-01", end: "2026-08-31" },
  kpis: {
    billed: "4591.170000",
    collected: "7557.440000",
    collected_from_cash: "7557.440000",
    collected_from_applied_deposits: "0.000000",
    collection_pct: null,
    still_owed: "1341.960000",
    accounts_owing: 11,
    dso: null,
    written_off_ytd: null,
  },
  revenue_by_service: [
    {
      service_id: "01a00ade-6972-70f2-987d-34625491faf5",
      service_code: "water",
      usage: "3859.300000",
      base_and_fees: "382.000000",
      total_billed: "4241.300000",
    },
  ],
  aging: null,
  cash: {
    basis: "clearing",
    currency: "USD",
    realised: "0.000000",
    undeposited: "7614.270000",
    note: "PO 2026-08-11 (OQ-143): undeposited money is NOT realised until the bank record and reconciliation confirm it. These two are never added together.",
  },
  adjustments: {
    basis: "posting",
    currency: "USD",
    credits_issued: "0.000000",
    debits_posted: "0.000000",
    late_fees_applied: null,
    net: "0.000000",
    pending_approval: null,
    unavailable: [
      gap(GAP_LATE_FEES, "BR-LED-016 · OQ-110 (PO 2026-08-11) · BR-BIL-008"),
      gap("pending_approval_count_is_not_a_ledger_fact", "BR-REP-002"),
    ],
  },
  tie_out: { ar_control: "1341.960000", computed_by: "US-LED-004 (not built)" },
  unavailable: [
    gap(GAP_COLLECTION_PCT, "BR-REP-009 · BR-LED-016"),
    gap(GAP_AGING, "BR-CUS-048 · BR-LED-016 · BR-REP-008"),
    gap(GAP_DSO, "BR-REP-011"),
    gap(GAP_SERVICE_COLUMNS, "BR-LED-001 · BR-REP-009"),
    gap(GAP_WRITTEN_OFF_YTD, "BR-TEN-022 · BR-REP-001 · BR-LED-016"),
  ],
} as unknown as RevenueArResponse;

/** The six figures `GET /finance/revenue-ar` refuses on this tenant. */
const ABSENT_ON_THIS_TENANT = [
  "kpis.collection_pct",
  "kpis.dso",
  "kpis.written_off_ytd",
  "aging",
  "adjustments.late_fees_applied",
  "adjustments.pending_approval",
] as const;

describe("DEF-176 — S36 renders against the SEEDED DEMO TENANT, not a fixture", () => {
  it("the recorded response really does refuse six figures, and really does omit two keys", () => {
    // If the wire ever stops refusing them, every assertion below passes for
    // the wrong reason — this is the one that notices (DEF-129's shape).
    const report = DEMO_TENANT_REVENUE_AR;
    expect(ABSENT_ON_THIS_TENANT).toHaveLength(6);
    expect(report.kpis.collection_pct).toBeNull();
    expect(report.kpis.dso).toBeNull();
    expect(report.kpis.written_off_ytd).toBeNull();
    expect(report.aging).toBeNull();
    expect(report.adjustments.late_fees_applied).toBeNull();
    expect(report.adjustments.pending_approval).toBeNull();
    // And the row that killed the route: ONE row, with two members the type
    // promises and the server never sent.
    expect(report.revenue_by_service).toHaveLength(1);
    const row = report.revenue_by_service[0] as unknown as Record<string, unknown>;
    expect(Object.keys(row)).not.toContain("tax");
    expect(Object.keys(row)).not.toContain("collected");
  });

  it("DEF-176: the Revenue-by-service table renders — an ABSENT key is an absence, not a crash", () => {
    // THE RED PROOF. Before the fix this line threw
    //   MoneyAmountAbsent: MoneyCell was handed an absent amount for USD.
    // and React Router replaced the entire route with its error boundary.
    const markup = renderToStaticMarkup(
      <RevenueByServiceTable report={DEMO_TENANT_REVENUE_AR} t={t} />,
    );
    // The three figures the books DO state, formatted through the one money path.
    expect(markup).toContain("$3,859.30");
    expect(markup).toContain("$382.00");
    expect(markup).toContain("$4,241.30");
    // The two columns they do not, said rather than zeroed (US-LED-007 exception 8).
    expect(markup).not.toContain("$0.00");
    expect(markup).toContain(escapeHtml(t(`finance.gap.${GAP_SERVICE_COLUMNS}`)));
    // And never the shape DEF-151 was filed on.
    expect(markup).not.toMatch(/null USD|undefined USD|>\s*null\b/);
  });

  it("DEF-176: the whole KPI strip renders, and each absent KPI carries its reason", () => {
    const markup = renderToStaticMarkup(
      <KPIStrip kpis={revenueArKpis(DEMO_TENANT_REVENUE_AR, t, undefined)} />,
    );
    expect(markup).toContain("$4,591.17"); // billed
    expect(markup).toContain("$7,557.44"); // collected
    expect(markup).toContain("$1,341.96"); // still owed
    // Three tiles that are absences, each with the catalogue sentence beside it.
    expect(markup).toContain(escapeHtml(t(`finance.gap.${GAP_COLLECTION_PCT}`)));
    expect(markup).toContain(escapeHtml(t(`finance.gap.${GAP_DSO}`)));
    expect(markup).toContain(escapeHtml(t(`finance.gap.${GAP_WRITTEN_OFF_YTD}`)));
    expect(markup).not.toMatch(/null USD|undefined USD|>\s*null\b/);
  });

  it("DEF-176: the adjustments panel renders its absences with reasons", () => {
    // ⛔ **THE AGEING HALF OF THIS CASE IS GONE WITH `AgingPanel` (`P2.21`,
    // 2026-09-24).** It asserted that the panel showed the derivable TOTAL and
    // stated `GAP_AGING` for the split it could not compute. `?view=aging` now
    // mounts `AgingView` over the `ar_aging` report, which HAS the split and
    // pages it — so there is no absence on that view to state, and asserting
    // one would pin a screen that no longer exists. `GET /finance/revenue-ar`
    // still serves `aging: null` with its reason and the STILL OWED tile still
    // reads that response; what changed is which component renders it.
    const adjustments = renderToStaticMarkup(
      <AdjustmentsPanelView report={DEMO_TENANT_REVENUE_AR} t={t} />,
    );
    expect(adjustments).toContain(escapeHtml(t(`finance.gap.${GAP_LATE_FEES}`)));
    expect(adjustments).not.toMatch(/null USD|undefined USD|>\s*null\b/);
  });
});

// ══════════════════════════════════════════════════════════════════════════
// 2026-09-01 — THE THREE CONTENT DEFECTS THE PO PHOTOGRAPHED AT v2.123.0
// ══════════════════════════════════════════════════════════════════════════
// Walking `/silver-creek-water/finance` the PO pointed at the text and the
// layout. All three findings are asserted here against the SAME recorded wire
// above, because a fixture chosen to make a point is how DEF-176 shipped.
describe("B14 rules 31/32/33 — S36 says each absence ONCE, short, and with no id", () => {
  it("the Written-off absence is stated ONCE: in the tile, not again at the foot of the page", () => {
    // ⚠ THE DEFECT, ASSERTED AS ITSELF. `GAP_WRITTEN_OFF_YTD` was missing from
    // the screen's `claimed` list, so the identical 49-word paragraph rendered
    // in the KPI tile AND in the "What these figures cannot show yet" panel at
    // the bottom of the page. The list was an array literal inside the render
    // tree, so nothing could have gone red; it is exported now and this is the
    // case that holds it.
    const strip = renderToStaticMarkup(
      <KPIStrip kpis={revenueArKpis(DEMO_TENANT_REVENUE_AR, t, undefined)} />,
    );
    const sentence = escapeHtml(t(`finance.gap.${GAP_WRITTEN_OFF_YTD}`));
    // THE TILE IS THE HOME — it is where the reader is looking at the moment
    // the figure is missing.
    expect(strip).toContain(sentence);
    expect(strip.split(sentence)).toHaveLength(2); // once, not twice

    // …and the foot-of-page panel has nothing left to say on this response.
    const footer = renderToStaticMarkup(
      <UnclaimedGaps
        gaps={DEMO_TENANT_REVENUE_AR.unavailable}
        claimed={S36_CLAIMED_GAPS}
        t={t}
      />,
    );
    expect(footer).toBe("");
  });

  it("every gap the recorded wire sends is claimed by a panel on this screen", () => {
    // The general form of the same defect: the next figure that earns a tile
    // and is not added to the list duplicates itself exactly as this one did.
    for (const gap of DEMO_TENANT_REVENUE_AR.unavailable) {
      expect(S36_CLAIMED_GAPS, `${gap.code} is stated twice`).toContain(gap.code);
    }
    for (const gap of DEMO_TENANT_REVENUE_AR.adjustments.unavailable) {
      expect(S36_CLAIMED_GAPS, `${gap.code} is stated twice`).toContain(gap.code);
    }
  });

  it("B14 rule 32: an absent tile is a <details> CLOSED by default, and still says so", () => {
    // The PO's words, four times in twenty minutes on 2026-08-31: "too much
    // content - desctiption is too much for clark to read". Three of these six
    // tiles carried a three-sentence paragraph inside a 180px tile.
    const strip = renderToStaticMarkup(
      <KPIStrip kpis={revenueArKpis(DEMO_TENANT_REVENUE_AR, t, undefined)} />,
    );
    // Three absent tiles, three disclosures.
    expect(strip.match(/<details/g) ?? []).toHaveLength(3);
    // NOT ONE OF THEM IS OPEN. `open` is the attribute that would put the
    // paragraphs straight back on the work surface with every test still green.
    expect(strip).not.toMatch(/<details[^>]*\sopen/);
    // ⚠ AND THE SENTENCE IS STILL THERE — hidden is not deleted (G38). A
    // shorter absence is the fix; a silent one is a worse defect.
    expect(strip).toContain(escapeHtml(t(`finance.gap.${GAP_COLLECTION_PCT}`)));
    expect(strip).toContain(escapeHtml(t(`finance.gap.${GAP_DSO}`)));
    expect(strip).toContain(escapeHtml(t(`finance.gap.${GAP_WRITTEN_OFF_YTD}`)));
    // The summary is what a closed tile shows, and it says there IS a gap.
    expect(strip.match(/<summary/g) ?? []).toHaveLength(3);
    expect(strip).toContain(t("finance.absent"));
  });

  it("B14 rule 31: no rule number and no server code reaches anything a user reads", () => {
    // The PO, 2026-08-19: "you are also adding internal content and BR codes on
    // screen, that is not required … those are for internal use." Seven
    // hardcoded `brRef:` arguments used to reach `finance.gap.unknown` from
    // this screen. The provenance moved to the code comments beside them.
    const surfaces = [
      renderToStaticMarkup(<KPIStrip kpis={revenueArKpis(DEMO_TENANT_REVENUE_AR, t, undefined)} />),
      renderToStaticMarkup(<RevenueByServiceTable report={DEMO_TENANT_REVENUE_AR} t={t} />),
      renderToStaticMarkup(<AdjustmentsPanelView report={DEMO_TENANT_REVENUE_AR} t={t} />),
    ];
    for (const html of surfaces) {
      expect(html).not.toMatch(/BR-[A-Z]{3}-\d+/); // a rule number
      expect(html).not.toMatch(/\b(OQ|DEF|US|EP|GT|ADR)-\d+/); // the rest of A1's grammar
      // …and the server's own stable identifiers, which are just as internal.
      for (const code of [
        GAP_COLLECTION_PCT,
        GAP_DSO,
        GAP_WRITTEN_OFF_YTD,
        GAP_AGING,
        GAP_SERVICE_COLUMNS,
        GAP_LATE_FEES,
      ]) {
        expect(html).not.toContain(code);
      }
    }
  });

  it("B14 rule 33: every gap sentence this screen renders is at most two short sentences", () => {
    // Rationale is ZERO words on screen; it lives in the code comment beside
    // the string. The cap is six words per sentence, two sentences.
    const codes = [
      ...DEMO_TENANT_REVENUE_AR.unavailable.map((gap) => gap.code),
      ...DEMO_TENANT_REVENUE_AR.adjustments.unavailable.map((gap) => gap.code),
      "unknown",
    ];
    for (const code of codes) {
      const copy = t(`finance.gap.${code}`);
      const parts = copy.split(/(?<=[.!?])\s+/).filter((part) => part.trim() !== "");
      expect(parts.length, `finance.gap.${code} sentence count`).toBeLessThanOrEqual(2);
      for (const part of parts) {
        expect(part.split(/\s+/).length, `finance.gap.${code}: "${part}"`).toBeLessThanOrEqual(6);
      }
    }
  });
});

/** React's server renderer escapes text; the expectations compare like for like. */
function escapeHtml(value: string): string {
  return value
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#x27;");
}

// ── Lifecycle ─────────────────────────────────────────────
// packet: US-LED-007@a1f04c9 (story+rules snapshot — EP-LED-03 US-LED-007; the same packet RevenueArPage.tsx carries) + 12-governance/10-defect-log.csv DEF-176
// generated: 2026-08-16 by story-coder (DEF-176 finance-route outage lane)
// checklist: A✔ B✔ C✔ D=deferred(no API call — the payload is RECORDED from the live demo tenant, which is stronger than a mocked one) E✔ F✔ G✔ H=deferred(PO 2026-08-09)
// gates: RED PROVED FIRST against the booted app AND in this file — before the fix, test 2 threw `MoneyAmountAbsent: MoneyCell was handed an absent amount for USD` and the browser showed `Unexpected Application Error!` with the whole page gone (screenshot in the lane report)
// exceptions: (1) `detail`/`wanted_reads` abbreviated — the screen renders its own catalogue keyed on `code` and never the server's prose (TD-16/B8), so no assertion can see them
// amended:   2026-09-01 by the finance-copy lane — five cases added for the three content defects the PO photographed at v2.123.0, all against the SAME recorded wire rather than a fixture written to make the point (which is the DEF-176 lesson this file exists for). They pin: the Written-off absence stated ONCE and the tile as its home; every served gap code claimed by a panel, so the NEXT figure that earns a tile cannot duplicate itself the same way; three closed `<details>` with the sentence still present (hidden is not deleted — G38); no `BR-`/`OQ-`/`DEF-` id and no server gap code in any rendered surface (B14 rule 31); and the two-sentences-of-six cap on every gap sentence the wire can reach (B14 rule 33). PROVED RED FIRST — see the lane report for the four verbatim failures.
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
