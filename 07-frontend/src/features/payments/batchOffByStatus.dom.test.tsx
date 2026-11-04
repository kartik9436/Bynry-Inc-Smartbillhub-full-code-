// @vitest-environment jsdom
// ── Trace ──────────────────────────────────────────────
// Defect:  DEF-PAY-10748 (Payments audit by level L3-04 — a batch off by
//          $566.50 read plain "Matched")
// Ruling:  decision log 2026-10-30 "Payments audit by level (L1/L2/L3, 31
//          issues)" — "Rest we will fix", L3-04 ("Matched · off by $X")
// ───────────────────────────────────────────────────────
// The worked figure is the tester's own batch: DEP-261029-0043, recorded
// $266.80, the bank posted $833.30 — off by $566.50. "Matched" means the batch
// is PAIRED with a bank line, not that the two agree, so the status says how
// far apart they are. At $0.00 it stays plain "Matched".
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen } from "@testing-library/react";
import { renderToStaticMarkup } from "react-dom/server";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it } from "vitest";

import "@/i18n";
import i18n from "@/i18n";

import type { DepositBatchDetail, DepositBatchRow } from "@/api/bankRecEndpoints";
import { ToastProvider } from "@/components/Toast";

import { DepositBatchPage, depositBatchQueryKey } from "./DepositBatchPage";
import { depositsConfig } from "./DepositsList";
import { batchStatusLabel } from "./depositsShared";

const TENANT = "westdesmoines";
const BATCH_ID = "01a0d3f3-8b66-7ff6-bf08-0000000000b3";
const t = (key: string, params?: Record<string, unknown>): string => i18n.t(key, params);

afterEach(cleanup);

function batch(over: Partial<DepositBatchDetail["batch"]> = {}): DepositBatchDetail["batch"] {
  return {
    id: BATCH_ID,
    code: "DEP-261029-0043",
    method_code: null,
    method_name: null,
    deposited_on: "2026-10-29",
    recorded_total: "266.800000",
    bank_total: "833.300000",
    difference: "566.500000",
    currency: "USD",
    payment_count: 3,
    status: "matched",
    locked: false,
    ...over,
  };
}

function detail(over: Partial<DepositBatchDetail["batch"]> = {}): DepositBatchDetail {
  return {
    batch: batch(over),
    live_total: "266.800000",
    members: [],
    bank_line: {
      bank_line_id: "bl-43",
      posted_on: "2026-10-30",
      reference: "CFP-STL-1029",
      amount: "833.300000",
      currency: "USD",
      line_no: 1,
      bank_account_name: "Bank of America",
      bank_account_mask: "8956",
      statement_import_id: "si-43",
      period_start: "2026-10-29",
      period_end: "2026-10-31",
    },
    trail: [],
    resolutions: [],
    unavailable: [],
  };
}

function mount(seed: DepositBatchDetail) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  queryClient.setQueryData(depositBatchQueryKey(seed.batch.id), seed);
  render(
    <QueryClientProvider client={queryClient}>
      <ToastProvider>
        <MemoryRouter initialEntries={[`/${TENANT}/finance/deposits/${seed.batch.id}`]}>
          <Routes>
            <Route path="/:tenant/finance/deposits/:batchId" element={<DepositBatchPage />} />
          </Routes>
        </MemoryRouter>
      </ToastProvider>
    </QueryClientProvider>,
  );
}

function listStatus(over: Partial<DepositBatchRow>): string {
  const config = depositsConfig(t, "en-US", { statuses: [], methods: [] });
  const column = config.columns.find((c) => c.key === "status");
  if (column?.cell === undefined) {
    throw new Error("the Deposits list has no Status cell");
  }
  const row = { ...batch(), ...over } as DepositBatchRow;
  return renderToStaticMarkup(<>{column.cell(row)}</>).replace(/<[^>]+>/g, "");
}

describe("L3-04 — a matched batch says how far it is off", () => {
  it("DEP-261029-0043: $266.80 vs bank $833.30 reads 'Matched · off by $566.50'", () => {
    expect(batchStatusLabel("matched", t, { difference: "566.500000", currency: "USD" })).toBe(
      "Matched · off by $566.50",
    );
  });

  it("a bank line SHORT of what we recorded reads the size of the gap, unsigned", () => {
    expect(batchStatusLabel("matched", t, { difference: "-147.500000", currency: "USD" })).toBe(
      "Matched · off by $147.50",
    );
  });

  it("at $0.00 — and with no difference known — it stays plain 'Matched'", () => {
    expect(batchStatusLabel("matched", t, { difference: "0.000000", currency: "USD" })).toBe(
      "Matched",
    );
    expect(batchStatusLabel("matched", t, { difference: null, currency: "USD" })).toBe("Matched");
    expect(batchStatusLabel("matched", t)).toBe("Matched");
  });

  it("only MATCHED carries it — reconciled and unmatched keep their own word", () => {
    expect(batchStatusLabel("reconciled", t, { difference: "566.500000", currency: "USD" })).toBe(
      "Reconciled",
    );
  });

  it("the Deposits list's Status column says it", () => {
    expect(listStatus({})).toBe("Matched · off by $566.50");
    expect(listStatus({ difference: "0.000000", bank_total: "266.800000" })).toBe("Matched");
  });

  it("the batch page's status pill says it", () => {
    mount(detail());
    expect(screen.getByText("Matched · off by $566.50")).toBeTruthy();
  });

  it("every catalogue carries the sentence with its {{amount}}", async () => {
    const languages = ["de", "en", "es", "es-MX", "fr-FR", "hi", "id-ID", "it-IT", "ja-JP", "ko-KR", "pt-BR"];
    for (const language of languages) {
      const catalogue = (await import(`../../i18n/locales/${language}.json`)).default as Record<
        string,
        string
      >;
      expect(catalogue["payments.deposits.status.matchedOffBy"], language).toContain("{{amount}}");
    }
  });
});
