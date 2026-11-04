// @vitest-environment jsdom
// ── Trace ──────────────────────────────────────────────
// Change:   CR-059 · CS-26 · task 65 — the bad-debt report's screen. The read
//           landed 2026-09-01 and NOTHING CALLED IT: the last of seven finished
//           backends shipping with no door under this CR (§11b, 2026-09-02).
// Story:    US-PAY-012 (write-offs)   Screens: S36 (Finance · Revenue & AR)
// Rules:    BR-PAY-020 (payments records, ledger posts, FINANCE REPORTS) ·
//           BR-REP-001 (a money report labels its basis) · BR-TEN-043 (the
//           caller names the window; nothing reads a clock) · CLAUDE.md rule 2
//           (money 4dp, percentages 6dp, both DISPLAY 2) · B14 rule 31 (no
//           database id is the visible value of a field) · rule 32 (a stated
//           absence is a `<details>` CLOSED by default) · rule 34 (*In the
//           books* is the phrase)
// ───────────────────────────────────────────────────────
// THE FIGURES ARE CS-26's OWN, and none of them is invented here:
//
//     uncollectible after 120 days   2,840.00   72.081218 %
//     deceased, no estate              712.40   18.081218 %
//     customer bankruptcy              387.60    9.837563 %
//     ─────────────────────────────────────────────────────
//     net bad debt                   3,940.00
//
// and US-PAY-012 TC-2's reversal: **948.20** approved in August, put back in
// December, netting bad debt to **0.00** over the year while appearing in BOTH
// months. No gate in this repo reads rendered output, so every assertion below
// reads the MARKUP a person would see.
import { cleanup } from "@testing-library/react";
import { renderToStaticMarkup } from "react-dom/server";
import { afterEach, describe, expect, it } from "vitest";

import "@/i18n";
import i18n from "@/i18n";

import type { BadDebtAccountRow, BadDebtReport } from "@/api/bankRecEndpoints";
import type { Translator } from "@/features/tenancy/settingsShared";

import {
  BadDebtCaveats,
  BadDebtTables,
  badDebtWindow,
  fiscalYearStartOnOrBefore,
  reasonRowsWithZeros,
  sharePercentDisplay,
} from "./BadDebtPanel";

const t: Translator = (key, params) => i18n.t(key, params);

/** The uuid a screen may never print (B14 rule 31, DEF-2580's exact shape). */
const ACCOUNT_UUID = "6d2f9a10-0000-4000-8000-0000000004a1";

function report(over: Partial<BadDebtReport> = {}): BadDebtReport {
  return {
    start: "2026-01-01",
    end: "2026-12-31",
    basis: "approved_on",
    currency: "USD",
    written_off: "3940.0000",
    reversed: "0.0000",
    net: "3940.0000",
    count: 3,
    by_reason: [
      {
        reason: "uncollectible_120_days",
        written_off: "2840.0000",
        reversed: "0.0000",
        net: "2840.0000",
        share_percent: "72.081218",
        count: 1,
        currency: "USD",
      },
      {
        reason: "deceased_no_estate",
        written_off: "712.4000",
        reversed: "0.0000",
        net: "712.4000",
        share_percent: "18.081218",
        count: 1,
        currency: "USD",
      },
      {
        reason: "customer_bankruptcy",
        written_off: "387.6000",
        reversed: "0.0000",
        net: "387.6000",
        share_percent: "9.837563",
        count: 1,
        currency: "USD",
      },
    ],
    by_month: [
      {
        period: "2026-08",
        written_off: "3940.0000",
        reversed: "0.0000",
        net: "3940.0000",
        count: 3,
        currency: "USD",
      },
    ],
    reasons: [
      "uncollectible_120_days",
      "customer_bankruptcy",
      "deceased_no_estate",
      "below_write_off_threshold",
    ],
    ledger: {
      available: true,
      account_code: "5900",
      net: "3940.0000",
      agrees: true,
    },
    problems: [
      { code: "bad_debt_not_split_by_service" },
      { code: "excludes_billing_small_balance_write_offs" },
    ],
    ...over,
  };
}

/** One write-off behind a bar, EXACTLY as the server serves it — `account_id`
 *  and all. The uuid is in the props on purpose: an assertion that a uuid is
 *  absent from markup that never held one cannot fail, which is the shape of a
 *  check that is trusted and cannot bite (DEF-182's lesson). */
function accountRow(over: Partial<BadDebtAccountRow> = {}): BadDebtAccountRow {
  return {
    id: "wo-1",
    account_id: ACCOUNT_UUID,
    account_no: "A-10802",
    amount: "948.2000",
    currency: "USD",
    reason: "uncollectible_120_days",
    note: "Chased for four months.",
    status: "approved",
    approved_on: "2026-08-15",
    reverses_write_off_id: null,
    reversal_reason: null,
    ...over,
  };
}

function tables(data: BadDebtReport, accountRows: BadDebtAccountRow[] | null = null): string {
  return renderToStaticMarkup(
    <BadDebtTables
      report={data}
      t={t}
      openReason={accountRows === null ? null : "uncollectible_120_days"}
      onOpenReason={() => undefined}
      accountRows={accountRows}
      accountsPending={false}
    />,
  );
}

afterEach(cleanup);

describe("CS-26 · the bad-debt report, on a screen a person can open", () => {
  it("prints CS-26's own three figures and their total", () => {
    const html = tables(report());
    expect(html).toContain("$2,840.00");
    expect(html).toContain("$712.40");
    expect(html).toContain("$387.60");
    expect(html).toContain("$3,940.00");
  });

  it("displays a six-decimal share at TWO decimals and never sums the shares", () => {
    // Hard rule 2: percentages are stored and served at six decimals and are
    // DISPLAYED at two. 72.081218 is the served figure; 72.08% is the screen's.
    expect(sharePercentDisplay("72.081218")).toBe("72.08%");
    const html = tables(report());
    expect(html).toContain("72.08%");
    expect(html).not.toContain("72.081218");
    // The three shares sum to 99.999999, not 100 — so nothing anywhere adds the
    // displayed percentages up. The total row is MONEY, summed by the server.
    expect(html).not.toContain("99.999999");
    expect(html).not.toContain("100.00%");
  });

  it("a share of nothing is a stated absence, never 0.00%", () => {
    // `summary.py`'s zero-state posture, and the server sends null for it.
    expect(sharePercentDisplay(null)).toBeNull();
    const html = tables(report());
    expect(html).toContain(t("payments.badDebt.noShare"));
    expect(html).not.toContain("0.00%");
  });

  it("draws a ZERO row for a reason nobody used, rather than dropping it", () => {
    // The server serves `reasons` for exactly this. A category missing from a
    // board's table reads as a category that does not exist, and *we wrote off
    // nothing for this reason* is an answer.
    const rows = reasonRowsWithZeros(report());
    expect(rows).toHaveLength(4);
    expect(rows.map((row) => row.reason)).toContain("below_write_off_threshold");
    expect(tables(report())).toContain(
      t("payments.writeOff.reason.below_write_off_threshold"),
    );
  });

  it("B14 rule 31 — the account NUMBER reaches the screen and the id never does", () => {
    const html = tables(report(), [accountRow()]);
    expect(html).toContain("A-10802");
    expect(html).not.toContain(ACCOUNT_UUID);
    expect(html).not.toContain("6d2f9a10");
  });

  it("an account with no number says so instead of printing an id", () => {
    const html = tables(report(), [
      accountRow({ id: "wo-2", account_no: null, amount: "100.0000" }),
    ]);
    expect(html).toContain(t("payments.writeOffQueue.noAccountNo"));
    expect(html).not.toContain(ACCOUNT_UUID);
  });

  it("a put-back row is MARKED, so a reader cannot count it as a second write-off", () => {
    const html = tables(report(), [
      accountRow({
        id: "wo-3",
        status: "reversed",
        approved_on: "2026-12-04",
        reverses_write_off_id: "wo-1",
      }),
    ]);
    expect(html).toContain(t("payments.badDebt.putBackRow"));
  });

  it("US-PAY-012 TC-2 — 948.20 written off in August and put back in December nets to 0.00, and shows in BOTH months", () => {
    const netted = report({
      written_off: "948.2000",
      reversed: "948.2000",
      net: "0.0000",
      count: 2,
      by_reason: [
        {
          reason: "uncollectible_120_days",
          written_off: "948.2000",
          reversed: "948.2000",
          net: "0.0000",
          share_percent: null,
          count: 2,
          currency: "USD",
        },
      ],
      by_month: [
        {
          period: "2026-08",
          written_off: "948.2000",
          reversed: "0.0000",
          net: "948.2000",
          count: 1,
          currency: "USD",
        },
        {
          period: "2026-12",
          written_off: "0.0000",
          reversed: "948.2000",
          net: "-948.2000",
          count: 1,
          currency: "USD",
        },
      ],
      ledger: { available: true, account_code: "5900", net: "0.0000", agrees: true },
    });
    const html = tables(netted);
    // August's own answer does not change retroactively: both months are there.
    expect(html).toContain("2026-08");
    expect(html).toContain("2026-12");
    expect(html).toContain("$948.20");
    expect(html).toContain("-$948.20");
    // …and the year nets to zero.
    expect(html).toContain("$0.00");
  });

  it("B14 rule 34 — the books' figure sits beside this one under *In the books*", () => {
    const html = tables(report());
    expect(html).toContain(t("payments.badDebt.inTheBooks"));
    expect(html).toContain(t("payments.badDebt.booksAgree"));
  });

  it("a DISAGREEMENT is reported rather than reconciled into one number", () => {
    // Two readings that agree are evidence; one number hiding a disagreement is
    // how a control stops working. Both figures are on the screen.
    const html = tables(
      report({
        ledger: { available: true, account_code: "5900", net: "3900.0000", agrees: false },
      }),
    );
    expect(html).toContain(t("payments.badDebt.booksDiffer"));
    expect(html).toContain("$3,900.00");
    expect(html).toContain("$3,940.00");
    expect(html).not.toContain(t("payments.badDebt.booksAgree"));
  });

  it("books that could NOT be read are an absence, never a zero", () => {
    const html = tables(
      report({ ledger: { available: false, account_code: null, net: null, agrees: false } }),
    );
    expect(html).toContain(t("payments.badDebt.booksUnavailable"));
    // A zero here would say the books hold nothing, which is a different fact.
    expect(html).not.toContain(t("payments.badDebt.booksAgree"));
  });
});

describe("CS-26 · B14 rule 32 — the caveats are CLOSED by default", () => {
  it("renders a <details> with no `open`, and states OQ-1300's gap in words", () => {
    const html = renderToStaticMarkup(
      <BadDebtCaveats problems={report().problems} t={t} />,
    );
    expect(html).toContain("<details");
    // CLOSED. `open` on the element is what would put four paragraphs of
    // explanation on a finance screen the moment it loads.
    expect(html).not.toContain("<details open");
    expect(html).toContain(t("payments.badDebt.notCovered"));
    expect(html).toContain(t("payments.problem.bad_debt_not_split_by_service"));
    expect(html).toContain(t("payments.problem.excludes_billing_small_balance_write_offs"));
  });

  it("no rule id, question id or route reaches the reader (B14 rules 31 and 32)", () => {
    const html = renderToStaticMarkup(
      <BadDebtCaveats
        problems={[
          { code: "bad_debt_not_split_by_service" },
          { code: "ledger_disagrees_with_payments" },
          { code: "ledger_tie_out_unavailable_no_write_off_designation" },
        ]}
        t={t}
      />,
    );
    expect(html).not.toMatch(/OQ-\d{3,5}(?!\d)/);
    expect(html).not.toMatch(/BR-[A-Z]{3}-\d{3,5}(?!\d)/);
    expect(html).not.toContain("/bad-debt");
  });

  it("nothing at all is drawn when the server named no gap", () => {
    expect(renderToStaticMarkup(<BadDebtCaveats problems={[]} t={t} />)).toBe("");
  });
});

describe("CS-26 · the window is chosen from SERVED facts and never from a clock", () => {
  const period = {
    fy_label: "FY2026",
    period: 3,
    start: "2026-03-01",
    end: "2026-03-31",
    status: "open",
    close_by: null,
  };

  it("*this period* is the accounting period the header is already showing", () => {
    expect(badDebtWindow("period", period, 7, 1)).toEqual({
      start: "2026-03-01",
      end: "2026-03-31",
    });
  });

  it("a 1 July financial year opens the year-to-date window on the PREVIOUS 1 July", () => {
    // The period ends 31 March 2026, so the financial year running from 1 July
    // opened on 1 July 2025 — not on 1 July 2026, which has not happened.
    expect(fiscalYearStartOnOrBefore("2026-03-31", 7, 1)).toBe("2025-07-01");
    expect(badDebtWindow("year", period, 7, 1)).toEqual({
      start: "2025-07-01",
      end: "2026-03-31",
    });
  });

  it("a calendar financial year opens on 1 January of the period's own year", () => {
    expect(fiscalYearStartOnOrBefore("2026-03-31", 1, 1)).toBe("2026-01-01");
  });

  it("a tenant with NO financial year gets no year option — never a guessed one", () => {
    // A calendar-year fallback would be this screen inventing the tenant's
    // financial year, and the heading is the half a board reads.
    expect(badDebtWindow("year", period, null, null)).toBeNull();
    expect(badDebtWindow("year", period, 7, null)).toBeNull();
  });
});
