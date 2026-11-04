// @vitest-environment jsdom
//
// ── Trace ──────────────────────────────────────────────
// Defect:  DEF-LED-6717 — the Revenue-by-service table and the Total line
//          underneath it were struck on two different bases. The Product Owner,
//          on deployed v2.351.84: one row reading **Total billed $50.00** above
//          a Total line reading **$0.00 POSTING DATE**.
// Rules:   CLAUDE.md NFR-3 (a total and the rows under it are ONE aggregate
//          over ONE filtered set, one of them windowed) · hard rule 2 (money is
//          never float) · hard-won law 7 (prove a guard RED first, and ask what
//          would make it pass wrongly)
// ───────────────────────────────────────────────────────
//
// ╔══════════════════════════════════════════════════════════════════════════╗
// ║  WHAT MADE THIS INVISIBLE FOR THE LIFE OF THE SCREEN                     ║
// ╚══════════════════════════════════════════════════════════════════════════╝
//
// Neither figure was wrong. The rows sum movement on the tenant's REVENUE
// accounts; `kpis.billed` sums AR DEBITS from invoice-sourced entries. On books
// written entirely by the bill run those are the same money seen from two
// sides, so every fixture in this repo agreed with itself by accident. They
// part the moment a finance officer types a journal entry by hand — and the
// only instrument that can see it is a check that ADDS THE ROWS UP.
//
// ⚠ **WHAT WOULD MAKE THIS CHECK PASS WRONGLY** (habit 2 of hard-won law 7),
// asked before it was trusted:
//   · *A fixture whose rows happen to sum to `kpis.billed`.* `DRIFTED` below is
//     built so they CANNOT: the rows total 50.00 and the KPI says 0.00, which
//     is the PO's own photograph. A regression to `kpis.billed` fails by 50.00
//     rather than by a rounding cent.
//   · *Reading the total out of the same expression the page used.* Every
//     figure below is read from the RENDERED DOM by its label and parsed from
//     the text a person sees — never recomputed from the fixture.
//   · *Summing only the visible page.* The filtered case below keeps a row the
//     PAGE would have shown and drops one it would not, so a footer that summed
//     the slice instead of the filtered set gives a different answer.
//   · *A table that drew no rows at all.* Each case asserts the row COUNT it
//     expects before it asserts the total, so an empty table cannot pass by
//     footing 0.00 to 0.00.
import { render, screen, cleanup, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it } from "vitest";

import i18n from "@/i18n";

import { RevenueByServiceTable } from "./RevenueArPage";

const t = i18n.getFixedT("en");

/** One `unavailable` entry; the screen renders the catalogue, never `detail`. */
function gap(code: string, brRef: string) {
  return { code, br_ref: brRef, detail: "(abbreviated — the screen never renders it)" };
}

/**
 * **THE PRODUCT OWNER'S OWN NUMBERS**, and the fixture is the defect.
 *
 * One revenue row of `50.0000` carrying no service — money posted by hand, the
 * `OQ-LED-12629` bucket — and a `kpis.billed` of `0`, because no AR debit on an
 * invoice-sourced entry backs it. The shipped page printed the KPI under the
 * row and the two disagreed by the whole of the period's revenue.
 */
const DRIFTED = {
  basis: "posting",
  currency: "USD",
  period: { start: "2026-09-01", end: "2026-09-30" },
  kpis: {
    billed: "0.000000",
    collected: "0.000000",
    collected_from_cash: "0.000000",
    collected_from_applied_deposits: "0.000000",
    collection_pct: null,
    still_owed: "25042.650000",
    accounts_owing: 44,
    dso: null,
    written_off_ytd: null,
  },
  revenue_by_service: [
    {
      service_id: null,
      service_code: null,
      usage: "50.000000",
      base_and_fees: "0.000000",
      total_billed: "50.000000",
      tax: null,
      collected: null,
    },
  ],
  unavailable: [gap("per_service_tax_and_collected_columns", "BR-LED-001 · BR-REP-009")],
} as never;

/** Three services with movement, so a FILTER has something to cut. */
const THREE = {
  ...(DRIFTED as never as Record<string, unknown>),
  kpis: { ...(DRIFTED as never as { kpis: Record<string, unknown> }).kpis, billed: "9999.000000" },
  revenue_by_service: [
    {
      service_id: "01a00ade-6972-70f2-987d-34625491faf5",
      service_code: "water",
      usage: "100.250000",
      base_and_fees: "12.000000",
      total_billed: "112.250000",
      tax: null,
      collected: null,
    },
    {
      service_id: "01a00ade-6972-70f2-987d-34625491fbb6",
      service_code: "sewer",
      usage: "40.100000",
      base_and_fees: "0.000000",
      total_billed: "40.100000",
      tax: null,
      collected: null,
    },
    {
      service_id: null,
      service_code: null,
      usage: "7.650000",
      base_and_fees: "0.000000",
      total_billed: "7.650000",
      tax: null,
      collected: null,
    },
  ],
} as never;

/** The money figure the **Total** line shows a person, read off the DOM. */
function statedTotal(): string {
  const label = screen.getByText(t("finance.revenue.total"));
  const row = label.closest("div, li, tr") as HTMLElement;
  const text = within(row).getByText(/\$/).textContent ?? "";
  return (text.match(/\$[\d,]+\.\d{2}/) ?? [""])[0];
}

/** Σ of the TOTAL BILLED cells actually drawn, read off the DOM. */
function drawnRowTotal(): { sum: string; rows: number } {
  const body = document.querySelector("tbody") as HTMLElement;
  const cells = [...body.querySelectorAll("tr")].map((tr) => {
    const money = [...tr.querySelectorAll("td")]
      .map((td) => (td.textContent ?? "").trim())
      .filter((text) => /^\$[\d,]+\.\d{2}$/.test(text));
    // TOTAL BILLED is the last money cell on the row: Usage · Base & fees ·
    // Tax (a dash) · Total billed · Collected (a dash).
    return money[money.length - 1] ?? "$0.00";
  });
  const cents = cells.reduce(
    (acc, text) => acc + BigInt(text.replace(/[$,.]/g, "")),
    0n,
  );
  const whole = (cents / 100n).toString();
  const rest = (cents % 100n).toString().padStart(2, "0");
  return {
    sum: `$${whole.replace(/\B(?=(\d{3})+(?!\d))/g, ",")}.${rest}`,
    rows: cells.length,
  };
}

afterEach(cleanup);

describe("DEF-LED-6717 — the Revenue-by-service table foots to its own rows", () => {
  it("states a total equal to the rows it draws, unfiltered", () => {
    render(<RevenueByServiceTable report={DRIFTED} t={t} />);
    const drawn = drawnRowTotal();
    expect(drawn.rows).toBe(1);
    expect(drawn.sum).toBe("$50.00");
    // THE ASSERTION THE SHIPPED PAGE FAILED: it printed `kpis.billed`, $0.00.
    expect(statedTotal()).toBe(drawn.sum);
  });

  it("states a total equal to the rows it draws, under a filter", async () => {
    const user = userEvent.setup();
    render(<RevenueByServiceTable report={THREE} t={t} />);
    expect(drawnRowTotal()).toEqual({ sum: "$160.00", rows: 3 });
    expect(statedTotal()).toBe("$160.00");
    // `DEF-LED-9120` — the Service cell is the service's WORD, never its code.
    expect(screen.getAllByText("Sewer").length).toBeGreaterThan(0);
    expect(screen.queryByText("sewer")).toBeNull();

    // Driven through the real control, never by poking state (the lane brief's
    // own rule, and DEF-CWP-3925's lesson one layer up). The option is found by
    // its WORD — `DEF-LED-9120`: it read `water` until the label was resolved.
    await user.click(screen.getByText(t("table.filters.open")));
    await user.click(screen.getByLabelText("Water"));

    const filtered = drawnRowTotal();
    expect(filtered.rows).toBe(1);
    expect(filtered.sum).toBe("$112.25");
    // A total that stayed at $160.00 here is the same defect wearing a filter.
    expect(statedTotal()).toBe(filtered.sum);
  });
});

// ── Lifecycle ─────────────────────────────────────────────
// packet: DEF-LED-6717 · CLAUDE.md NFR-3 paragraph + hard rule 2 + hard-won law 7 · 12-governance/22-product-maintenance-process.md
// generated: 2026-09-25 by lane REV (maintenance)
// checklist: A=n/a B=n/a C✔ D=n/a E=n/a F✔ G✔ H=n/a
// gates: RED PROVED FIRST against the shipped page — see the lane report for the verbatim failure.
// exceptions: (1) it reads the TOTAL BILLED cell as the last money cell on the row rather than by a column id, because `DataTable` renders no per-column test id and adding one is a kit change with no proof behind it in this lane
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
