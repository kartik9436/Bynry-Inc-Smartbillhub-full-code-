// @vitest-environment jsdom
// ── Trace ──────────────────────────────────────────────
// Defects:  DEF-PAY-10785 (P1 a1-3) · DEF-PAY-10786 (P1 a2-2) · DEF-PAY-10787
//           (P1 a2-3) · DEF-PAY-10788 (P2 = A)
// Ruling:   decision log 2026-10-31 "Twelve open payment questions answered
//           (PO)" — *"P1-a1-3 a2-2 a2-3, P2-A"*
// ───────────────────────────────────────────────────────
// The tester's statement line RET1029-02 CHK 4103, −$154.00:
//   * a2-3 — Match to payment opens with "4103" in the search, and its FIRST
//     request already carries ?q=4103;
//   * a2-2 — the Bank memo is shown pre-filled with the line's words and the
//     clerk's edit is what reaches the server;
//   * a1-3 — a matched line reads "RET1029-01 → Clara Castillo · AC-2026-00003";
//   * P2 — Reconciliation's unexplained money-out row offers Match to payment
//     and Bank fee, and opens the SAME form, pre-filled the same way.
import "@testing-library/jest-dom/vitest";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { ReconcilingItem, StatementLineRow, StatementReview } from "@/api/bankRecEndpoints";
import type { ApiClient } from "@/api/client";
import i18n from "@/i18n";

import { StatementReviewTable } from "./BankImportWizard";
import { UnexplainedTable, moneyOutLine } from "./ReconciliationStatementPage";
import { MatchReturnForm, matchedToText } from "./StatementLineActions";
import type { MoneyOutLine } from "./StatementLineActions";

const t = (key: string, params?: Record<string, unknown>): string => i18n.t(key, params);

afterEach(cleanup);

const CANDIDATE = {
  payment_id: "pay-4103",
  payment_no: "PY-2026-0103",
  cheque: "4103",
  account_id: "acc-2",
  account_no: "AC-2026-00002",
  amount: "154.000000",
  posted_on: "2026-10-26",
  already_reversed: false,
  reversal_id: null,
  reversed_on: null,
  reference_match: true,
};

const LINE: MoneyOutLine = {
  bank_line_id: "l-ret2",
  reference: "RET1029-02 CHK 4103",
  posted_on: "2026-10-29",
  amount: "-154.000000",
  search_hint: "4103",
};

function mountForm(line: MoneyOutLine = LINE) {
  const get = vi.fn().mockImplementation((path: string) =>
    Promise.resolve({
      data: path.includes("/nsf-fee")
        ? { status: "nsf_fee_not_set_on_plan", code: null, amount: null, currency: "USD" }
        : { rows: [CANDIDATE] },
    }),
  );
  const post = vi.fn().mockResolvedValue({
    data: { resolution_id: "r", created: true, posted: true, reversed_now: true },
  });
  const client = { get, post } as unknown as ApiClient;
  const onDone = vi.fn();
  const queries = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={queries}>
      <MatchReturnForm
        line={line}
        currency="USD"
        client={client}
        onClose={() => undefined}
        onDone={onDone}
      />
    </QueryClientProvider>,
  );
  return { get, post, onDone };
}

async function pickTheCheque() {
  await screen.findByRole("option", { name: /4103/ });
  fireEvent.change(document.getElementById("payment_id") as HTMLSelectElement, {
    target: { value: "pay-4103" },
  });
}

function submit() {
  fireEvent.click(screen.getByRole("button", { name: new RegExp(t("payments.deposits.lines.matchSubmit")) }));
}

describe("P1 a2-3 — the search opens on the line's cheque number", () => {
  it("shows 4103 in the search and the first request carries it", async () => {
    const { get } = mountForm();
    expect(document.getElementById("return_search")).toHaveValue("4103");
    await waitFor(() =>
      expect(get).toHaveBeenCalledWith("/bank-lines/l-ret2/return-candidates?q=4103"),
    );
    expect(get).not.toHaveBeenCalledWith("/bank-lines/l-ret2/return-candidates");
  });

  it("opens empty when the line carries no cheque number", async () => {
    const { get } = mountForm({ ...LINE, reference: "RET1029-02", search_hint: null });
    expect(document.getElementById("return_search")).toHaveValue("");
    await waitFor(() => expect(get).toHaveBeenCalledWith("/bank-lines/l-ret2/return-candidates"));
  });
});

describe("P1 a2-2 — the Bank memo is the clerk's to edit", () => {
  it("is pre-filled from the line, and the edit is what is sent", async () => {
    const { post, onDone } = mountForm();
    await pickTheCheque();
    const memo = await screen.findByLabelText(t("payments.reverse.bankMemo"));
    expect(memo).toHaveValue("RET1029-02 CHK 4103");
    fireEvent.change(memo, { target: { value: "NSF - account closed" } });
    submit();
    await waitFor(() => expect(onDone).toHaveBeenCalled());
    expect(post).toHaveBeenCalledWith(
      "/bank-lines/l-ret2/match-return",
      expect.objectContaining({ payment_id: "pay-4103", bank_memo: "NSF - account closed" }),
    );
  });

  it("refuses 61 characters before anything is sent", async () => {
    const { post } = mountForm();
    await pickTheCheque();
    const memo = await screen.findByLabelText(t("payments.reverse.bankMemo"));
    fireEvent.change(memo, { target: { value: "x".repeat(61) } });
    submit();
    expect(await screen.findByText(t("payments.reverse.bankMemoTooLong"))).toBeInTheDocument();
    expect(post).not.toHaveBeenCalled();
  });

  it("a link to a hand reversal shows no memo and sends none", async () => {
    const get = vi.fn().mockResolvedValue({
      data: { rows: [{ ...CANDIDATE, already_reversed: true, reversal_id: "rev", reversed_on: "2026-11-03" }] },
    });
    const post = vi.fn().mockResolvedValue({ data: { created: true, posted: true } });
    const queries = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    const onDone = vi.fn();
    render(
      <QueryClientProvider client={queries}>
        <MatchReturnForm
          line={LINE}
          currency="USD"
          client={{ get, post } as unknown as ApiClient}
          onClose={() => undefined}
          onDone={onDone}
        />
      </QueryClientProvider>,
    );
    await pickTheCheque();
    expect(screen.queryByLabelText(t("payments.reverse.bankMemo"))).toBeNull();
    submit();
    await waitFor(() => expect(onDone).toHaveBeenCalled());
    expect(post.mock.calls[0][1]).not.toHaveProperty("bank_memo");
  });
});

describe("P1 a1-3 — a matched line says whose cheque it was", () => {
  it("formats reference → name · account number, leaving out what is unknown", () => {
    expect(matchedToText("RET1029-01", "Clara Castillo", "AC-2026-00003")).toBe(
      "RET1029-01 → Clara Castillo · AC-2026-00003",
    );
    expect(matchedToText("RET1029-01", null, "AC-2026-00003")).toBe(
      "RET1029-01 → AC-2026-00003",
    );
    expect(matchedToText("FEE1031", null, null)).toBeNull();
  });

  it("the import review's In the books row names the customer and account", () => {
    const row: StatementLineRow = {
      bank_line_id: "l1",
      posted_on: "2026-10-29",
      reference: "RET1029-01",
      amount: "-76.400000",
      currency: "USD",
      line_no: 2,
      batch_id: null,
      batch_code: null,
      recorded_total: null,
      difference: null,
      state: "explained",
      posted: true,
      actions: [],
      returned_customer_name: "Clara Castillo",
      returned_account_no: "AC-2026-00003",
    };
    render(
      <MemoryRouter>
        <StatementReviewTable
          review={{ rows: [row], tiles: {}, open_batches: [], currency: "USD", unavailable: [] } as unknown as StatementReview}
          t={t}
          batchPath={(id) => `/x/${id}`}
          onPair={() => undefined}
          onLineAction={() => undefined}
        />
      </MemoryRouter>,
    );
    expect(screen.getByText(t("payments.deposits.lines.inTheBooks"))).toBeInTheDocument();
    expect(screen.getByText("RET1029-01 → Clara Castillo · AC-2026-00003")).toBeInTheDocument();
  });
});

describe("P2 — Match to payment and Bank fee on Reconciliation", () => {
  const ITEM: ReconcilingItem = {
    code: "unexplained_lines",
    amount: "-178.000000",
    count: 2,
    rows: [
      { ...LINE, line_no: 3, age_days: 2, actions: ["match_return", "bank_fee"] },
      { bank_line_id: "l-wire", reference: "WIRE 99812", posted_on: "2026-10-28", amount: "12.400000", line_no: 5, age_days: 3, actions: [] },
    ],
  } as unknown as ReconcilingItem;

  function table(onLineAction?: (kind: string, row: unknown) => void) {
    render(
      <UnexplainedTable
        item={ITEM}
        currency="USD"
        t={t}
        timeZone="America/Chicago"
        dateFormat={"MM/DD/YYYY" as never}
        selected={[]}
        onToggle={() => undefined}
        onExplain={() => undefined}
        onMatchSeveral={() => undefined}
        onLineAction={onLineAction}
      />,
    );
  }

  it("offers both on the money-out line only, and says which line", () => {
    const onLineAction = vi.fn();
    table(onLineAction);
    const match = screen.getAllByRole("button", { name: t("payments.deposits.lines.matchReturn") });
    const fee = screen.getAllByRole("button", { name: t("payments.deposits.lines.bankFee") });
    expect(match).toHaveLength(1);
    expect(fee).toHaveLength(1);
    fireEvent.click(match[0]);
    expect(onLineAction).toHaveBeenCalledWith("match_return", ITEM.rows[0]);
    fireEvent.click(fee[0]);
    expect(onLineAction).toHaveBeenCalledWith("bank_fee", ITEM.rows[0]);
  });

  it("offers neither when no handler is wired", () => {
    table(undefined);
    expect(screen.queryByRole("button", { name: t("payments.deposits.lines.matchReturn") })).toBeNull();
  });

  it("the row opens the SAME form, pre-filled the same way", async () => {
    const { get } = mountForm(moneyOutLine(ITEM.rows[0]));
    expect(document.getElementById("return_search")).toHaveValue("4103");
    await waitFor(() =>
      expect(get).toHaveBeenCalledWith("/bank-lines/l-ret2/return-candidates?q=4103"),
    );
  });
});
