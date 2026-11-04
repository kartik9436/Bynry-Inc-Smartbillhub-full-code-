// @vitest-environment jsdom
// ── Trace ──────────────────────────────────────────────
// Defects:  DEF-PAY-10700 (LBX-01 — a batch matching the bank to the penny
//           could never be reconciled) · DEF-PAY-10704 (LBX-02 — a stale field
//           error stayed under a corrected amount; amounts took 6 decimals)
// Ruling:   decision log 2026-10-30 "LBX-01, LBX-02 and LBX-04 are fixed (PO)"
// Rules:    CLAUDE.md hard rule 2 (money stored to 4 decimals) · BR-PAY-019
//           (a reason AND a GL on every NON-ZERO difference) · BR-PAY-004 (a
//           reconciled batch locks) · Finance blueprint p051 (`Reconcile ✓` is
//           the batch's primary action) and p055 (`Record ✓` at a residual of
//           $0.00 only)
// ───────────────────────────────────────────────────────
// The worked figure is the tester's own batch: DEP-261026-0007, recorded
// $870.50 against a bank line of $870.50 — a difference of exactly $0.00.
// Before the fix the only door was *Resolve difference*, which opened a form
// that pre-filled a 0.00 row, refused it ("Zero explains nothing.") and
// demanded at least one row, so the batch stayed Matched for ever.
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { renderToStaticMarkup } from "react-dom/server";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it } from "vitest";

import "@/i18n";
import i18n from "@/i18n";

import type { DepositBatchDetail, DepositBatchRow } from "@/api/bankRecEndpoints";
import { createApiClient } from "@/api/client";
import { ToastProvider } from "@/components/Toast";

import { DepositBatchPage, depositBatchQueryKey } from "./DepositBatchPage";
import { depositsConfig } from "./DepositsList";

const TENANT = "westdesmoines";
const BATCH_ID = "01a0d3f3-8b66-7ff6-bf08-0000000000a7";
const t = (key: string, params?: Record<string, unknown>): string => i18n.t(key, params);

afterEach(cleanup);

const BANK_LINE = {
  bank_line_id: "bl-7",
  posted_on: "2026-10-26",
  reference: "LBX4521-1026",
  amount: "870.500000",
  currency: "USD",
  line_no: 1,
  bank_account_name: "Bank of America",
  bank_account_mask: "7895",
  statement_import_id: "si-7",
  period_start: "2026-10-26",
  period_end: "2026-10-31",
};

function batch(over: Partial<DepositBatchDetail["batch"]> = {}): DepositBatchDetail["batch"] {
  return {
    id: BATCH_ID,
    code: "DEP-261026-0007",
    method_code: null,
    method_name: null,
    deposited_on: "2026-10-26",
    recorded_total: "870.500000",
    bank_total: "870.500000",
    difference: "0.000000",
    currency: "USD",
    payment_count: 6,
    status: "matched",
    locked: false,
    ...over,
  };
}

function detail(over: Partial<DepositBatchDetail> = {}): DepositBatchDetail {
  return {
    batch: batch(),
    live_total: "870.500000",
    members: [],
    bank_line: BANK_LINE,
    trail: [],
    resolutions: [],
    unavailable: [],
    ...over,
  };
}

interface Call {
  method: string;
  url: string;
  body: Record<string, unknown> | null;
}

/** A server that answers the batch GET and the reconcile POST, and after a
 *  reconcile serves the batch as RECONCILED and LOCKED — exactly what
 *  `reconcile_batch` leaves behind. */
function stub(calls: Call[], first: DepositBatchDetail) {
  let reconciled = false;
  return createApiClient({
    tenant: TENANT,
    fetchImpl: async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      const method = init?.method ?? "GET";
      const body = typeof init?.body === "string" ? JSON.parse(init.body) : null;
      calls.push({ method, url, body });
      const json = (b: unknown, status = 200) =>
        new Response(JSON.stringify(b), {
          status,
          headers: { "Content-Type": "application/json" },
        });
      if (method === "POST" && url.includes(`/deposit-batches/${BATCH_ID}/reconcile`)) {
        reconciled = true;
        return json({ code: first.batch.code, status: "reconciled" });
      }
      if (url.includes(`/deposit-batches/${BATCH_ID}`)) {
        return json(
          reconciled
            ? { ...first, batch: { ...first.batch, status: "reconciled", locked: true } }
            : first,
        );
      }
      return json({ detail: "not here" }, 404);
    },
  });
}

function mount(seed: DepositBatchDetail, client?: ReturnType<typeof createApiClient>) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  queryClient.setQueryData(depositBatchQueryKey(seed.batch.id), seed);
  render(
    <QueryClientProvider client={queryClient}>
      <ToastProvider>
        {/* Mounted under the REAL path pattern (hard-won law 2's fixture note). */}
        <MemoryRouter initialEntries={[`/${TENANT}/finance/deposits/${seed.batch.id}`]}>
          <Routes>
            <Route
              path="/:tenant/finance/deposits/:batchId"
              element={<DepositBatchPage client={client} />}
            />
          </Routes>
        </MemoryRouter>
      </ToastProvider>
    </QueryClientProvider>,
  );
}

const amountAt = (index: number) =>
  document.getElementById(`resolutions.${index}.amount`) as HTMLInputElement;
const residual = () => screen.getByTestId("resolve-residual").textContent ?? "";

describe("LBX-01 — a batch that matches the bank to the penny reconciles", () => {
  it("DEP-261026-0007: $870.50 = $870.50 → Reconcile ✓ posts no explanation rows → Reconciled", async () => {
    const calls: Call[] = [];
    const seed = detail();
    mount(seed, stub(calls, seed));

    // The head offers the plain commit, not the explain-a-difference form.
    expect(
      screen.queryByRole("button", { name: t("payments.deposits.resolveDifference") }),
    ).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: t("payments.deposits.reconcileCommit") }));

    await waitFor(() =>
      expect(calls.some((call) => call.method === "POST")).toBe(true),
    );
    const post = calls.find((call) => call.method === "POST");
    expect(post?.url).toContain(`/deposit-batches/${BATCH_ID}/reconcile`);
    // NO explanation rows — the server accepts that at a zero difference
    // (`test_cr008_tender_gl_posting.py`, `test_p3_11_locked_batch_drift.py`).
    expect(post?.body?.resolutions).toEqual([]);

    // The batch comes back reconciled and locked: Unreconcile is the only act.
    await waitFor(() =>
      expect(
        screen.getByRole("button", { name: t("payments.deposits.unreconcile") }),
      ).toBeTruthy(),
    );
    expect(
      screen.queryByRole("button", { name: t("payments.deposits.reconcileCommit") }),
    ).toBeNull();
  });

  it("a NON-zero difference still opens the explain form, never the plain commit", () => {
    mount(
      detail({
        batch: batch({ bank_total: "846.500000", difference: "-24.000000" }),
      }),
    );
    expect(
      screen.queryByRole("button", { name: t("payments.deposits.reconcileCommit") }),
    ).toBeNull();
    expect(
      screen.getByRole("button", { name: t("payments.deposits.resolveDifference") }),
    ).toBeTruthy();
  });

  it("the list row reads Reconcile for a matched $0.00 batch, Resolve when it differs", () => {
    const config = depositsConfig(
      t,
      "en-US",
      { statuses: [], methods: [] },
      (id) => `/${TENANT}/finance/deposits/${id}`,
    );
    const action = config.columns.find((column) => column.key === "actions");
    const row = (over: Partial<DepositBatchRow>): DepositBatchRow => ({
      id: BATCH_ID,
      code: "DEP-261026-0007",
      method_code: null,
      method_name: null,
      deposited_on: "2026-10-26",
      recorded_total: "870.500000",
      bank_total: "870.500000",
      difference: "0.000000",
      currency: "USD",
      payment_count: 6,
      status: "matched",
      locked: false,
      ...over,
    });
    const cell = (r: DepositBatchRow) =>
      renderToStaticMarkup(<MemoryRouter>{action?.cell?.(r)}</MemoryRouter>);
    expect(cell(row({}))).toContain(`>${t("payments.deposits.reconcile")}<`);
    expect(cell(row({ bank_total: "846.500000", difference: "-24.000000" }))).toContain(
      `>${t("payments.deposits.resolve")}<`,
    );
    expect(cell(row({ status: "reconciled", locked: true }))).toContain(
      `>${t("payments.deposits.view")}<`,
    );
  });
});

describe("LBX-02 — an error is about the value on screen, and money has 4 decimals", () => {
  const SHORT = detail({ batch: batch({ bank_total: "846.500000", difference: "-24.000000" }) });

  function openForm() {
    mount(SHORT);
    fireEvent.click(screen.getByRole("button", { name: t("payments.deposits.resolveDifference") }));
  }

  it("[+0.01, −0.01] explains 0.00 and shows no error under either amount", () => {
    openForm();
    fireEvent.change(amountAt(0), { target: { value: "abc" } });
    expect(screen.getByText(t("payments.deposits.form.amountInvalid"))).toBeTruthy();
    fireEvent.change(amountAt(0), { target: { value: "0.01" } });
    fireEvent.click(screen.getByRole("button", { name: t("payments.deposits.form.addExplanation") }));
    fireEvent.change(amountAt(1), { target: { value: "-0.01" } });
    // The old error does not survive the corrected value.
    expect(screen.queryByText(t("payments.deposits.form.amountInvalid"))).toBeNull();
    expect(amountAt(0).getAttribute("aria-invalid")).toBeNull();
    expect(amountAt(1).getAttribute("aria-invalid")).toBeNull();
    // Explained $0.00, so the whole −$24.00 is still to explain.
    expect(residual()).toContain("$24.00");
  });

  it("[−24.00] against −24.00 leaves a residual of $0.00", () => {
    openForm();
    // The form opens with the difference itself in the only row.
    expect(amountAt(0).value).toBe("-24.00");
    fireEvent.change(amountAt(0), { target: { value: "-24.00" } });
    expect(residual()).toContain("$0.00");
    expect(screen.queryByText(t("payments.deposits.form.residualBlocks"))).toBeNull();
  });

  it("'1,5' is refused on the spot and is not counted", () => {
    openForm();
    fireEvent.change(amountAt(0), { target: { value: "1,5" } });
    expect(screen.getByText(t("payments.deposits.form.amountInvalid"))).toBeTruthy();
    expect(amountAt(0).getAttribute("aria-invalid")).toBe("true");
    // Not read as 1.5 nor as 15: what is left is UNKNOWN, and the commit stays shut.
    expect(residual()).toContain(t("payments.deposits.form.residualUnknown"));
    expect(screen.getByText(t("payments.deposits.form.residualBlocks"))).toBeTruthy();
  });

  it("a fifth decimal is refused (hard rule 2: money is stored to 4)", () => {
    openForm();
    fireEvent.change(amountAt(0), { target: { value: "-23.99995" } });
    expect(screen.getByText(t("payments.deposits.form.amountPlaces"))).toBeTruthy();
    expect(residual()).toContain(t("payments.deposits.form.residualUnknown"));
    fireEvent.change(amountAt(0), { target: { value: "-24.0000" } });
    expect(screen.queryByText(t("payments.deposits.form.amountPlaces"))).toBeNull();
    expect(residual()).toContain("$0.00");
  });

  it("a schema error raised by a press clears once its own field changes", async () => {
    openForm();
    // The residual ties, so the commit is open; reason and GL are empty.
    fireEvent.click(screen.getByRole("button", { name: t("payments.deposits.resolveSubmit") }));
    await waitFor(() =>
      expect(screen.getByText(t("payments.deposits.form.reasonRequired"))).toBeTruthy(),
    );
    expect(screen.getByText(t("payments.deposits.form.glRequired"))).toBeTruthy();
    fireEvent.change(document.getElementById("resolutions.0.reason_code") as HTMLInputElement, {
      target: { value: "bank_error" },
    });
    expect(screen.queryByText(t("payments.deposits.form.reasonRequired"))).toBeNull();
    // A field nobody touched keeps its error until it is fixed or pressed again.
    expect(screen.getByText(t("payments.deposits.form.glRequired"))).toBeTruthy();
  });
});
