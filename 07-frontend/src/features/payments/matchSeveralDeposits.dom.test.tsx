// @vitest-environment jsdom
// ── Trace ──────────────────────────────────────────────
// Defect:   DEF-PAY-10780 — one bank line to several deposits, from the line
// Ruling:   decision log 2026-10-30 "Match to several deposits mock-up
//           approved (PO)" — approved as drawn
// ───────────────────────────────────────────────────────
// The PO's own figures: CFP-STL-1029 $833.30 = DEP-261029-0043 $266.80 +
// DEP-261029-0044 $313.00 + DEP-261021-0031 $253.50; DEP-261030-0046 $412.15
// (Counter) is the one that does not belong.
import "@testing-library/jest-dom/vitest";

import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { DepositBatchRow, StatementLineRow } from "@/api/bankRecEndpoints";
import type { ApiClient } from "@/api/client";
import i18n from "@/i18n";

import {
  MatchSeveralDepositsModal,
  SetMatchedLines,
  UnexplainedLineActions,
  canMatchSeveral,
  severalVerdict,
} from "./MatchSeveralDeposits";

const t = (key: string, params?: Record<string, unknown>): string => i18n.t(key, params);

afterEach(cleanup);

function batch(id: string, code: string, total: string, day: string, method: string | null): DepositBatchRow {
  return {
    id,
    code,
    method_code: null,
    method_name: method,
    all_tenders: true,
    channel: null,
    deposited_on: day,
    recorded_total: total,
    bank_total: null,
    difference: null,
    currency: "USD",
    payment_count: 3,
    status: "in_transit",
    locked: false,
  };
}

const OPEN = [
  batch("b-43", "DEP-261029-0043", "266.800000", "2026-10-29", "Store · Hy-Vee"),
  batch("b-44", "DEP-261029-0044", "313.000000", "2026-10-29", "Store · Hy-Vee"),
  batch("b-31", "DEP-261021-0031", "253.500000", "2026-10-21", "Store · Hy-Vee"),
  batch("b-46", "DEP-261030-0046", "412.150000", "2026-10-30", "Counter"),
];

const LINE = {
  bank_line_id: "line-1029",
  reference: "CFP-STL-1029",
  posted_on: "2026-10-29",
  amount: "833.300000",
};

function client(post = vi.fn()): ApiClient {
  return { post, get: vi.fn() } as unknown as ApiClient;
}

function open(post = vi.fn(), onDone = vi.fn()) {
  render(
    <MatchSeveralDepositsModal
      line={LINE}
      openBatches={OPEN}
      currency="USD"
      timeZone="America/Chicago"
      dateFormat="MM/DD/YYYY"
      client={client(post)}
      onClose={vi.fn()}
      onDone={onDone}
    />,
  );
}

function tick(code: string) {
  fireEvent.click(screen.getByRole("checkbox", { name: t("payments.deposits.several.tickOne", { deposit: code }) }));
}

describe("DEF-PAY-10780 — the running total against the bank line", () => {
  it("is exact scaled arithmetic: short, equal, over", () => {
    expect(severalVerdict("833.300000", ["266.800000", "313.000000"])).toMatchObject({
      kind: "short",
      left: "253.500000",
    });
    expect(severalVerdict("833.300000", ["266.800000", "313.000000", "253.500000"]).kind).toBe(
      "equal",
    );
    expect(
      severalVerdict("833.300000", ["266.800000", "313.000000", "253.500000", "412.150000"]),
    ).toMatchObject({ kind: "over", over: "412.150000" });
    expect(severalVerdict("833.300000", []).kind).toBe("none");
  });

  it("offers the button on a credit only", () => {
    expect(canMatchSeveral("833.300000")).toBe(true);
    expect(canMatchSeveral("-76.400000")).toBe(false);
    expect(canMatchSeveral(null)).toBe(false);
  });
});

describe("DEF-PAY-10780 — the dialog, as the mock-up draws it", () => {
  it("lists the open deposits by label, says Still to find, then Equals, and only then lets Match go", async () => {
    const post = vi.fn().mockResolvedValue({
      data: {
        match_set_id: "set-1",
        matched_total: "833.300000",
        currency: "USD",
        bank_line_ids: ["line-1029"],
        batch_ids: ["b-43", "b-44", "b-31"],
        batch_codes: ["DEP-261029-0043", "DEP-261029-0044", "DEP-261021-0031"],
        created: true,
        unavailable: [],
      },
      status: 201,
    });
    const onDone = vi.fn();
    open(post, onDone);

    expect(screen.getByRole("dialog")).toHaveTextContent(t("payments.deposits.several.title"));
    expect(screen.getByText("DEP-261030-0046")).toBeInTheDocument();
    const match = () => screen.getByRole("button", { name: /^(Match|Match \d deposits)$/ });
    expect(match()).toBeDisabled();

    tick("DEP-261029-0043");
    tick("DEP-261029-0044");
    const verdict = () => document.querySelector("[data-several-verdict]") as HTMLElement;
    expect(verdict()).toHaveTextContent("Selected 2 · $579.80");
    expect(verdict()).toHaveTextContent("Still to find $253.50");
    expect(match()).toBeDisabled();
    expect(match()).toHaveTextContent("Match 2 deposits");

    tick("DEP-261030-0046");
    expect(verdict()).toHaveTextContent("Over by $158.65");
    expect(match()).toBeDisabled();
    tick("DEP-261030-0046");

    tick("DEP-261021-0031");
    expect(verdict()).toHaveTextContent("Selected 3 · $833.30");
    expect(verdict()).toHaveTextContent("Equals the bank line");
    expect(verdict()).toHaveAttribute("data-several-verdict", "equal");
    expect(match()).toBeEnabled();
    expect(match()).toHaveTextContent("Match 3 deposits");

    fireEvent.click(match());
    await waitFor(() => expect(onDone).toHaveBeenCalled());
    const [path, body] = post.mock.calls[0];
    expect(path).toBe("/bank-rec/match-set");
    expect(body.bank_line_ids).toEqual(["line-1029"]);
    expect(body.batch_ids).toEqual(["b-43", "b-44", "b-31"]);
    expect(typeof body.occurred_at).toBe("string");
    expect(onDone.mock.calls[0][1]).toBe(3);
  });

  it("shows the server's refusal inside the dialog and keeps the ticks", async () => {
    const { ApiError } = await import("@/api/client");
    const post = vi.fn().mockRejectedValue(
      new ApiError(422, {
        code: "VAL-001",
        message_key: "api.error.unexpected",
        params: {},
        field_errors: [],
      } as never),
    );
    open(post);
    tick("DEP-261029-0043");
    tick("DEP-261029-0044");
    tick("DEP-261021-0031");
    fireEvent.click(screen.getByRole("button", { name: "Match 3 deposits" }));
    await waitFor(() =>
      expect(document.querySelector("[data-several-refusal]")).toBeInTheDocument(),
    );
    expect(screen.getAllByRole("checkbox", { checked: true })).toHaveLength(3);
  });
});

describe("DEF-PAY-10780 — the row and the result", () => {
  it("puts the button beside Explain on a credit, not on a line the bank took out", () => {
    const { rerender } = render(
      <UnexplainedLineActions amount="833.300000" onExplain={vi.fn()} onMatchSeveral={vi.fn()} />,
    );
    expect(screen.getByRole("button", { name: t("payments.deposits.several.open") })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: t("payments.deposits.statement.explain") })).toBeInTheDocument();
    rerender(<UnexplainedLineActions amount="-76.400000" onExplain={vi.fn()} onMatchSeveral={vi.fn()} />);
    expect(screen.queryByRole("button", { name: t("payments.deposits.several.open") })).toBeNull();
  });

  it("reads Matched · 3 deposits with the three labels", () => {
    const row = {
      bank_line_id: "line-1029",
      posted_on: "2026-10-29",
      reference: "CFP-STL-1029",
      amount: "833.300000",
      currency: "USD",
      line_no: 2,
      batch_id: null,
      batch_code: null,
      match_set_id: "set-1",
      match_set_batch_codes: ["DEP-261021-0031", "DEP-261029-0043", "DEP-261029-0044"],
      match_set_total: "833.300000",
      recorded_total: null,
      difference: "0.000000",
      state: "set_matched",
    } as unknown as StatementLineRow;
    render(
      <SetMatchedLines rows={[row]} currency="USD" timeZone="America/Chicago" dateFormat="MM/DD/YYYY" />,
    );
    expect(screen.getByText("Matched · 3 deposits")).toBeInTheDocument();
    expect(screen.getByText("DEP-261021-0031, DEP-261029-0043, DEP-261029-0044")).toBeInTheDocument();
    expect(screen.getByText("CFP-STL-1029")).toBeInTheDocument();
  });
});
