// ── Trace ──────────────────────────────────────────────
// Change:   Payments audit Q4 (PO 2026-10-30, decision log *"Q4 settled: bulk
//           Send receipts AND bulk Reapply are built"*) · DEF-PAY-10747 ·
//           lane PAY-J
// Rules:    BR-SHL-025 (a control that cannot be honoured is disabled WITH
//           its reason) · B14 rule 15 · B14 rule 33 · CLAUDE.md law 2
// ───────────────────────────────────────────────────────
// The worked case: 20 payments ticked after the 29 Oct email outage. The
// server answers each one — 5 receipts SENT (theirs had failed), 15 WAITING in
// the outbound table for the email service — and the result panel reads
// "5 sent · 15 waiting for the email service". A 21st row whose customer has
// no email is NAMED "No contact on file", beside its payment number.
//
// RED FIRST: before this lane `receiptOne`, `reapplyOne`, `outcomeSummary`
// and the two bar props did not exist, so every case failed on import; the
// summary case, with the panel still printing `resultSummary`, failed with
// "20 of 20 went through" where "5 sent · 15 waiting…" was asked for.
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import "@/i18n";
import i18n from "@/i18n";

import type { ApiClient } from "@/api/client";
import type { PaymentRow } from "@/api/endpoints";
import type { Translator } from "@/features/tenancy/settingsShared";

import {
  BulkRunPanel,
  EMPTY_SELECTION,
  PaymentsBulkBar,
  bulkReapplyRefusal,
  bulkReceiptRefusal,
  reapplyOne,
  receiptOne,
  runPerRow,
  toggleSelected,
} from "./paymentsBulk";
import type { BulkRun, PaymentSelection, PerRowOutcome } from "./paymentsBulk";

const t: Translator = (key, params) => i18n.t(key, params);

function escaped(text: string): string {
  return text
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#x27;");
}

function payment(n: number, over: Partial<PaymentRow> = {}): PaymentRow {
  return {
    id: `pay-${n}`,
    payment_no: `PY-2610-${String(n).padStart(6, "0")}`,
    account_id: `acc-${n}`,
    account_no: `AC-2026-${String(n).padStart(5, "0")}`,
    customer_name: `Customer ${n}`,
    type: "payment",
    method: "check",
    method_name: "Cheque",
    confirmation: String(4000 + n),
    memo: null,
    amount: "68.000000",
    currency: "USD",
    status: "cleared",
    purpose: "bill",
    posted_at: "2026-10-29",
    cleared_at: "2026-10-29",
    applied_to: [],
    applied_total: "0.000000",
    deposit_batch_id: null,
    receipt_no: null,
    cheque_date: null,
    drawer_bank: null,
    bankable_from: null,
    moved_from_payment_no: null,
    moved_from_account_no: null,
    moved_to_payment_no: null,
    moved_to_account_no: null,
    origin: "entry",
    batch_ref: null,
    batch_kind: null,
    ...over,
  };
}

/** A fake client answering each POST from a table keyed by payment id. */
function clientAnswering(
  outcomeFor: (paymentId: string) => string,
  seen: { path: string; body: unknown }[],
): ApiClient {
  const post = async (path: string, body?: unknown) => {
    seen.push({ path, body });
    const id = decodeURIComponent(path.split("/")[2] ?? "");
    return {
      status: 200,
      data: { payment_id: id, payment_no: null, outcome: outcomeFor(id) },
      etag: null,
      notModified: false,
    };
  };
  return { post } as unknown as ApiClient;
}

async function run(
  action: BulkRun["action"],
  rows: readonly PaymentRow[],
  refusalFor: (row: PaymentRow) => string | null,
  call: (row: PaymentRow) => Promise<string>,
): Promise<BulkRun> {
  const outcomes: PerRowOutcome[] = [];
  await runPerRow(
    rows,
    refusalFor,
    (row) => row.payment_no ?? "",
    call,
    () => "failed",
    (outcome) => outcomes.push(outcome),
  );
  return { action, total: rows.length, outcomes, running: false };
}

function panel(result: BulkRun): string {
  return renderToStaticMarkup(
    <BulkRunPanel run={result} refundsHref={null} onRetry={null} onDismiss={() => undefined} />,
  );
}

function selectionOf(rows: readonly PaymentRow[]): PaymentSelection {
  let selection = EMPTY_SELECTION;
  for (const row of rows) {
    selection = toggleSelected(selection, row);
  }
  return selection;
}

function bar(rows: readonly PaymentRow[]): string {
  return renderToStaticMarkup(
    <PaymentsBulkBar
      selection={selectionOf(rows)}
      role="billing_clerk"
      currency="USD"
      total={undefined}
      running={null}
      progress={null}
      onClear={() => undefined}
      onReverse={() => undefined}
      onRefund={() => undefined}
      onSendReceipts={() => undefined}
      onReapply={() => undefined}
    />,
  );
}

const TWENTY = Array.from({ length: 20 }, (_, i) => payment(i + 1));
const FAILED_FIVE = new Set(TWENTY.slice(0, 5).map((row) => row.id));

describe("Q4 · bulk Send receipts", () => {
  it("20 ticked → one request per payment → '5 sent · 15 waiting for the email service'", async () => {
    const seen: { path: string; body: unknown }[] = [];
    const client = clientAnswering((id) => (FAILED_FIVE.has(id) ? "sent" : "waiting"), seen);
    const result = await run(
      "receipts",
      TWENTY,
      (row) => bulkReceiptRefusal(row, t),
      (row) => receiptOne(row, client),
    );
    expect(seen).toHaveLength(20);
    expect(seen.every((one) => one.path.endsWith("/bulk-receipt"))).toBe(true);
    const html = panel(result);
    expect(html).toContain("5 sent · 15 waiting for the email service");
    expect(html).toContain(escaped(t("payments.bulk.resultTitle.receipts")));
    // Each row says what happened to IT, by payment number.
    expect(html).toContain("PY-2610-000006");
    expect(html).toContain(escaped(t("payments.bulk.row.waiting")));
  });

  it("a customer with no email on file is NAMED, beside the payment number", async () => {
    const ben = payment(21);
    const client = clientAnswering(
      (id) => (id === ben.id ? "no_contact" : FAILED_FIVE.has(id) ? "sent" : "waiting"),
      [],
    );
    const html = panel(
      await run(
        "receipts",
        [...TWENTY, ben],
        (row) => bulkReceiptRefusal(row, t),
        (row) => receiptOne(row, client),
      ),
    );
    expect(html).toContain("5 sent · 15 waiting for the email service · 1 no contact on file");
    expect(html).toMatch(/PY-2610-000021<\/span><span>No contact on file<\/span>/);
  });

  it("a credit row is refused before anything is sent, and says why", async () => {
    const seen: { path: string; body: unknown }[] = [];
    const credit = payment(30, { type: "credit" });
    const html = panel(
      await run(
        "receipts",
        [credit],
        (row) => bulkReceiptRefusal(row, t),
        (row) => receiptOne(row, clientAnswering(() => "sent", seen)),
      ),
    );
    expect(seen).toHaveLength(0);
    expect(html).toContain(escaped(t("payments.bulk.receiptNotMoney")));
  });
});

describe("Q4 · bulk Reapply", () => {
  it("each ticked payment is one reapply carrying the clerk's day; the panel counts outcomes", async () => {
    const five = TWENTY.slice(0, 5);
    const seen: { path: string; body: unknown }[] = [];
    const client = clientAnswering((id) => (id === "pay-5" ? "nothing_to_reapply" : "reapplied"), seen);
    const html = panel(
      await run(
        "reapply",
        five,
        (row) => bulkReapplyRefusal(row, t),
        (row) => reapplyOne(row, "2026-10-30", client),
      ),
    );
    expect(seen.map((one) => one.path)).toEqual(
      five.map((row) => `/payments/${row.id}/bulk-reapply`),
    );
    expect(seen.every((one) => (one.body as { on_date: string }).on_date === "2026-10-30")).toBe(true);
    expect(html).toContain("4 reapplied · 1 nothing to reapply");
  });

  it("a payment the clerk may not reapply is NAMED, never skipped silently", async () => {
    const seen: { path: string; body: unknown }[] = [];
    const deposit = payment(40, { purpose: "deposit" });
    const reversed = payment(41, { status: "reversed" });
    const html = panel(
      await run(
        "reapply",
        [payment(42), deposit, reversed],
        (row) => bulkReapplyRefusal(row, t),
        (row) => reapplyOne(row, "2026-10-30", clientAnswering(() => "reapplied", seen)),
      ),
    );
    expect(seen).toHaveLength(1);
    expect(html).toContain("PY-2610-000040");
    expect(html).toContain(escaped(t("payments.bulk.reapplyHeldForPurpose")));
    expect(html).toContain("PY-2610-000041");
    expect(html).toContain(escaped(t("payments.bulk.reapplyNotStanding")));
    expect(html).toContain("1 reapplied · 2 not sent");
  });
});

describe("Q4 · the bar", () => {
  it("draws both buttons with the eligible count, singular and plural", () => {
    const one = bar([payment(1), payment(2, { purpose: "deposit", type: "credit" })]);
    expect(one).toContain(escaped(t("payments.bulk.action.receiptsCount", { count: 1 })));
    expect(t("payments.bulk.action.receiptsCount", { count: 1 })).toBe("Send 1 receipt");
    expect(t("payments.bulk.action.receiptsCount", { count: 20 })).toBe("Send 20 receipts");
    expect(one).toContain(escaped(t("payments.bulk.action.reapplyCount", { count: 1 })));
  });

  it("is disabled with its reason when no ticked row can take it", () => {
    const html = bar([payment(1, { type: "adjustment" })]);
    expect(html).toContain(escaped(t("payments.bulk.receiptNotMoney")));
  });

  it("every new key is in all eleven catalogues", () => {
    const keys = [
      "payments.bulk.kind.waiting_other",
      "payments.bulk.row.no_contact",
      "payments.bulk.action.receiptsCount_one",
      "payments.bulk.reapplyHeldForPurpose",
    ];
    for (const lng of ["de", "es", "es-MX", "fr-FR", "hi", "id-ID", "it-IT", "ja-JP", "ko-KR", "pt-BR"]) {
      for (const key of keys) {
        expect(i18n.exists(key, { lng }), `${lng} ${key}`).toBe(true);
      }
    }
  });
});
