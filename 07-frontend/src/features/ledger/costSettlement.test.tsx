// @vitest-environment jsdom
// ── Trace ──────────────────────────────────────────────
// Change:   CR-060 C1 · task T6(e) — the "Paid on" field and R8's two state
//           sentences. T6 landed the column, the posting and the route on
//           2026-09-02 and recorded "(e) THE SCREEN — NOT LANDED" in writing.
//           Screens: S73 (Finance → Costs, the captured-purchase register)
// Rules:    B14 rule 31 (no database id is the visible value of a field) ·
//           B14 rule 32 (a stated absence is a disclosure CLOSED by default) ·
//           B14 rule 34 (ONE pair of words: **Recorded** · **In the books**) ·
//           B14 rule 15 (a row action is an icon with an accessible name) ·
//           BR-LED-028 as AMENDED 2026-09-02 · CLAUDE.md hard rule 4 (no
//           UPDATE reaches a posted journal entry)
// ───────────────────────────────────────────────────────
// **NOTHING IN THIS REPO READS RENDERED OUTPUT, so this file does.**
//
// Every assertion below is against the HTML the register actually produces. The
// three things that would each pass `tsc`, pass every existing suite, and be
// wrong on a finance officer's screen:
//
//   · the state read off `paid_on !== null` instead of the SERVER's
//     `in_the_books` — indistinguishable today, wrong the first time the two
//     come apart, and red nowhere;
//   · `settlement.journal_entry_id` reaching a cell, which is B14 rule 31 and
//     the exact thing the PO photographed on 2026-08-19;
//   · a Record-payment control offered on a purchase already in the books,
//     where hard rule 4 leaves the server no answer but a refusal.
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen } from "@testing-library/react";
import { renderToStaticMarkup } from "react-dom/server";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it } from "vitest";

import "@/i18n";
import i18n from "@/i18n";

import { queryKeys } from "@/api/queryClient";
import { ToastProvider } from "@/components/Toast";
import { shellBootSeed } from "@/components/shellBootSeed";
import type { CostRegisterResponse, CostRegisterRow } from "@/api/endpoints";

import {
  CostOfServicePage,
  SettlementCell,
  costRegisterDefaultParams,
  costRegisterKey,
} from "./CostOfServicePage";

const t = (key: string) => i18n.t(key) as string;

/** LE-11's CI-1: RS-2607-0141, City of Rosenberg, $1,240.00 of bulk water. */
function row(overrides: Partial<CostRegisterRow> = {}): CostRegisterRow {
  return {
    id: "8f2b6c14-0f6a-4d2a-9c1e-3a7b5d9e0011",
    invoice_date: "2026-07-05",
    supplier_name: "City of Rosenberg",
    service: "water",
    amount: "1240.0000",
    currency: "USD",
    volume: "400000",
    volume_unit: "gal",
    gl_account_id: "1a2b3c4d-5e6f-4708-9a0b-1c2d3e4f5061",
    gl_account_code: "5110",
    gl_account_name: "Purchased water",
    gl_account_unsigned: false,
    period: ["2026-07-01", "2026-07-31"],
    status: "captured",
    reference: "RS-2607-0141",
    memo: null,
    captured_by_user_id: null,
    captured_at: "2026-07-06T14:02:00Z",
    void_reason: null,
    voided_at: null,
    voided_by_user_id: null,
    paid_on: null,
    settlement: {
      paid_on: null,
      in_the_books: false,
      journal_entry_id: null,
      replayed: false,
      ruling: "Recording the payment charges the cost account and takes the same amount out of cash.",
    },
    ...overrides,
  };
}

/** The same purchase, settled on 2026-07-28 and posted. */
const SETTLED = row({
  paid_on: "2026-07-28",
  settlement: {
    paid_on: "2026-07-28",
    in_the_books: true,
    // Served for the tie-out and the drill-back. NO CELL MAY PRINT IT.
    journal_entry_id: "c9d8e7f6-a5b4-4321-8765-0f1e2d3c4b5a",
    replayed: false,
    ruling: "Recording the payment charges the cost account and takes the same amount out of cash.",
  },
});

function register(rows: CostRegisterRow[]): CostRegisterResponse {
  return {
    rows,
    total_amount: "1240.0000",
    currency: "USD",
    count: rows.length,
    sort: "-date",
    bulk_actions: [],
    categories: ["water"],
    refused_categories: [],
    forbidden_actions: [],
    pending_finance_re_sign_cost: [],
    cost_section_source: "",
    posting: { posted: false, reason: "capture_posts_nothing_in_r2" },
  } as unknown as CostRegisterResponse;
}

afterEach(cleanup);

/**
 * ⚠ `DEF-LED-9029` — RENDERED IN A DOM AND WAITED ON, NOT TO A STRING. Since
 * the register moved onto the shared table (26376795e) its rows are drawn
 * after the table measures itself, which a static server render never reaches:
 * the string held the frame, the filters and the headers and NO ROW. Three
 * cases below then failed as if the row controls were missing, and the rule-31
 * case passed on a register with nothing in it. This waits for the supplier's
 * name, so an empty register can no longer pass anything.
 */
async function renderRegister(rows: CostRegisterRow[]): Promise<string> {
  // `staleTime: Infinity` — the seeded page is the answer; a refetch on mount
  // would draw the table in its loading state and reach for a live server.
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false, staleTime: Infinity } },
  });
  // `DEF-LED-9029` — the key the page actually asks with on a first load (its
  // default sort and page), never `{}`, which no screen requests.
  queryClient.setQueryData(costRegisterKey(costRegisterDefaultParams(t)), register(rows));
  // DEF-SHL-4283 — the Finance frame reads its period from `GET /shell/display`
  // now, not from the Admin/Executive `GET /settings/regional`, because seven
  // screens share `useFinancePeriod` and one of them is a Billing Clerk's. A
  // seed on the old key leaves the frame at "Loading the period…" and every
  // assertion below measures a header instead of the screen.
  queryClient.setQueryData(
    queryKeys.shellDisplay,
    shellBootSeed(
      { timezone: "America/Chicago", date_format: "MM/DD/YYYY" },
      {
        fy_label: "FY2026",
        period: 7,
        start: "2026-07-01",
        end: "2026-07-31",
        status: "open",
      },
    ),
  );
  const { container } = render(
    <QueryClientProvider client={queryClient}>
      <ToastProvider>
        <MemoryRouter initialEntries={["/finance/cost-of-service"]}>
          <CostOfServicePage timeZone="America/Chicago" dateFormat="MM/DD/YYYY" />
        </MemoryRouter>
      </ToastProvider>
    </QueryClientProvider>,
  );
  await screen.findAllByText("City of Rosenberg");
  return container.innerHTML;
}

describe("S73 · the settlement state on the register (CR-060 T6(e))", () => {
  it("draws a settled purchase as IN THE BOOKS, with the day the bank moved", () => {
    const html = renderToStaticMarkup(<SettlementCell row={SETTLED} t={t} />);

    // B14 rule 34's pair, not a sixth phrasing of it.
    expect(html).toContain("In the books");
    expect(html).toContain("2026-07-28");
    // A settled purchase is NOT a stated absence, so it is not behind a
    // disclosure — a clerk should see the state without opening anything.
    expect(html).not.toContain("<details");
  });

  it("draws an unsettled purchase as RECORDED, behind a CLOSED disclosure", () => {
    const html = renderToStaticMarkup(<SettlementCell row={row()} t={t} />);

    expect(html).toContain("Recorded");
    expect(html).toContain("Held here, not in the books.");
    // B14 rule 32 — the reason is a disclosure and it is SHUT. An unpaid
    // purchase is the ordinary case (nine of LE-11's nine on capture day), so
    // an open explanation would shout on every row of the register.
    expect(html).toContain("<details");
    expect(html).not.toContain("<details open");
  });

  it("never prints the journal entry behind the settlement (B14 rule 31)", async () => {
    const cell = renderToStaticMarkup(<SettlementCell row={SETTLED} t={t} />);
    const page = await renderRegister([SETTLED]);

    for (const html of [cell, page]) {
      expect(html).not.toContain("c9d8e7f6");
      expect(html).not.toContain(SETTLED.settlement.journal_entry_id);
    }
  });

  it("reads the SERVER's state, never whether paid_on happens to be set", () => {
    // The shape that would pass every other assertion in this file and be
    // wrong: a date recorded with nothing posted behind it. Today the two
    // cannot disagree — `record_settlement` writes the column and posts the
    // entry in one transaction — and a screen that quietly leans on that is a
    // screen that breaks silently the day they come apart.
    const dateWithoutAPosting = row({
      paid_on: "2026-07-28",
      settlement: { ...row().settlement, paid_on: "2026-07-28", in_the_books: false },
    });
    const html = renderToStaticMarkup(<SettlementCell row={dateWithoutAPosting} t={t} />);

    expect(html).toContain("Recorded");
    expect(html).not.toContain("In the books");
  });
});

describe("S73 · the Record-payment control (CR-060 T6(e))", () => {
  it("offers Record payment on a purchase that is not in the books", async () => {
    const html = await renderRegister([row()]);

    // The whole point of the row: before this landed, the books moved only for
    // a caller with an HTTP client (hard-won law 2, open in writing on T6).
    expect(html).toContain("Record payment");
    // The column is drawn, and it is drawn beside Status rather than inside it.
    expect(html).toContain("Paid on");
  });

  it("withholds it once the purchase IS in the books", async () => {
    const html = await renderRegister([SETTLED]);

    // Hard rule 4 leaves no path to change a posted entry, so the server
    // refuses a clear or a move by name. A control that can only be refused is
    // worse than no control.
    expect(html).not.toContain("Record payment");
    expect(html).toContain("In the books");
  });

  it("keeps Correct and Void, which are different acts from recording a payment", async () => {
    const html = await renderRegister([row()]);

    // The server refuses a body carrying `paid_on` beside anything else, so the
    // screen must offer two saves. If Record payment ever replaced Correct, a
    // clerk would have no way to fix a mistyped amount.
    expect(html).toContain("Correct");
    expect(html).toContain("Void");
  });
});
