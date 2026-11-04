// ── Trace ──────────────────────────────────────────────
// Ruling:   PO 2026-10-30, decision log *"Payments audit by level: answers to
//           Q1, Q3, Q5, Q6, Q7"* — Q3 = A: a **Print receipt** button on a
//           recorded payment opens a ONE-PAGE receipt in the browser to print
//           now (Rosa pays $68.00 cash → prints). Plain HTML, not a PDF; no
//           attachments on a payment.
// Defect:   DEF-PAY-10743 · DEF-PAY-10770 (W4 = A: Credit on account)
// Rules:    CLAUDE.md hard rule 2 (money displays 2 places — `formatMoney`) ·
//           B14 rules 21 (Tailwind only; this file is on the Route B ledger),
//           31 (the PY- number, never an id), 33 (labels, no rationale),
//           43 (a component, imported by both doors)
// Tests:    07-frontend/src/features/payments/printReceipt.dom.test.tsx ·
//           06-backend/tests/test_pay_g_print_receipt.py
// ───────────────────────────────────────────────────────
/**
 * `PrintReceiptButton` — one button, used by the recorded-payment panel and by
 * the payment page, that opens the receipt in a NEW browser window and prints it.
 *
 * WHY A NEW WINDOW AND NOT A ROUTE. A route would print inside the app frame
 * (sidebar, header, toasts) unless every screen learned a print rule; a window
 * of its own holds the receipt and nothing else, so *one page* is true by
 * construction. The receipt is rendered INTO that window through a React portal,
 * so it keeps this app's translations, query cache and regional formats — and
 * the app's own stylesheets are copied into the window's head so the Tailwind
 * utilities below resolve there too.
 *
 * The window is opened SYNCHRONOUSLY in the click (a pop-up blocker allows a
 * window only there); the facts arrive afterwards and the print dialog opens
 * once they have. A blocked window says so in a toast.
 *
 * The facts are `GET /payments/{id}/receipt/print` (a READ — nothing is queued
 * or sent); the utility's name and mark are the shell's own (`GET
 * /shell/display`), the same response the sidebar draws from.
 */
import { useEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { useQuery } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";

import { api } from "@/api/client";
import type { ApiClient } from "@/api/client";
import { getShellDisplay } from "@/api/endpoints";
import { queryKeys } from "@/api/queryClient";
import { Button } from "@/components/Button";
import { formatDate } from "@/components/DateCell";
import { formatMoney } from "@/components/MoneyCell";
import { useToastIfMounted } from "@/components/Toast";
import { useRegional } from "@/features/metering/meteringShared";
import { BrandMark } from "@/features/tenancy/BrandMark";

/** One payment's receipt facts — `apps/payments/receipt_print.print_receipt`. */
export interface PrintReceiptFacts {
  payment_id: string;
  payment_no: string | null;
  posted_at: string | null;
  account_no: string | null;
  customer_name: string | null;
  amount: string;
  currency: string;
  method_name: string | null;
  confirmation: string | null;
  status: string | null;
  bills: { number: string | null; amount: string }[];
  /** The account's net position from the books now, SIGNED (negative = in
   *  credit, DEF-PAY-10770); `null` when they cannot answer — never "0.00". */
  balance: string | null;
  taken_by: string | null;
  counter: string | null;
}

export function getPrintReceipt(client: ApiClient, paymentId: string): Promise<PrintReceiptFacts> {
  return client
    .get<PrintReceiptFacts>(`/payments/${encodeURIComponent(paymentId)}/receipt/print`)
    .then((response) => {
      if (response.data === undefined || response.data === null) {
        throw new Error("receipt/print answered no body");
      }
      return response.data;
    });
}

export const printReceiptQueryKey = (paymentId: string) =>
  ["payments", "receipt-print", paymentId] as const;

const RECEIPT_MARK_SIZE = 40;

/** The receipt page itself — exported so a test can draw it without a window. */
export function ReceiptSheet(props: {
  paymentId: string;
  client?: ApiClient;
  locale?: string;
  onReady?: () => void;
}) {
  const { t } = useTranslation();
  const client = props.client ?? api;
  const { timeZone, dateFormat } = useRegional({});
  const locale = props.locale ?? "en-US";
  const facts = useQuery({
    queryKey: printReceiptQueryKey(props.paymentId),
    queryFn: () => getPrintReceipt(client, props.paymentId),
    retry: false,
  });
  const display = useQuery({
    queryKey: queryKeys.shellDisplay,
    queryFn: () => getShellDisplay(client),
    retry: false,
  });
  const ready = facts.isSuccess && !display.isLoading;
  // Once per receipt: the print dialog must not reopen on every re-render.
  const announced = useRef(false);
  const { onReady } = props;
  useEffect(() => {
    if (ready && onReady && !announced.current) {
      announced.current = true;
      onReady();
    }
  }, [ready, onReady]);

  if (facts.isError) return <p className="p-6 text-base">{t("payments.printReceipt.failed")}</p>;
  if (!facts.isSuccess) return <p className="p-6 text-base">{t("payments.printReceipt.loading")}</p>;

  const receipt = facts.data;
  const company = display.data?.company;
  const utilityName = company?.dba_name || company?.legal_name || "";
  const money = (amount: string) => formatMoney(amount, receipt.currency, locale);
  const absent = t("payments.printReceipt.notRecorded");
  // DEF-PAY-10770 (PO W4 = A): the server serves the account's NET position,
  // signed — negative is money the utility holds. Hugo's −68.00 prints
  // "Credit on account $68.00", never "Balance remaining −$68.00".
  const inCredit = receipt.balance !== null && Number(receipt.balance) < 0;
  const rows: [string, string][] = [
    [t("payments.printReceipt.number"), receipt.payment_no ?? absent],
    [
      t("payments.printReceipt.date"),
      receipt.posted_at ? formatDate(receipt.posted_at, timeZone, dateFormat) : absent,
    ],
    [t("payments.printReceipt.account"), receipt.account_no ?? absent],
    [t("payments.printReceipt.customer"), receipt.customer_name ?? absent],
    [t("payments.printReceipt.method"), receipt.method_name ?? absent],
  ];
  if (receipt.confirmation) rows.push([t("payments.printReceipt.reference"), receipt.confirmation]);

  return (
    <article className="mx-auto max-w-[560px] p-6 text-base text-body" data-testid="receipt-sheet">
      <header className="mb-4 flex items-center gap-3 border-b border-neutral-300 pb-4">
        {company ? (
          <BrandMark
            mark={company.mark}
            hasLogo={company.has_logo}
            logoRef={company.logo_ref}
            size={RECEIPT_MARK_SIZE}
            name={utilityName}
          />
        ) : null}
        <div>
          <p className="font-semibold">{utilityName}</p>
          <h1 className="text-base font-semibold">{t("payments.printReceipt.title")}</h1>
        </div>
      </header>
      <dl className="mb-4 grid grid-cols-2 gap-x-4 gap-y-1">
        {rows.map(([label, value]) => (
          <div key={label} className="contents">
            <dt className="text-neutral-700">{label}</dt>
            <dd>{value}</dd>
          </div>
        ))}
      </dl>
      <p className="mb-4 flex justify-between border-y border-neutral-300 py-2 font-semibold">
        <span>{t("payments.printReceipt.amount")}</span>
        <span className="tabular-nums">{money(receipt.amount)}</span>
      </p>
      <h2 className="mb-1 text-base font-semibold">{t("payments.printReceipt.bills")}</h2>
      {receipt.bills.length > 0 ? (
        <table className="mb-4 w-full border-collapse">
          <tbody>
            {receipt.bills.map((bill, index) => (
              <tr key={`${bill.number ?? "bill"}-${index}`}>
                <td>{bill.number ?? absent}</td>
                <td className="text-right tabular-nums">{money(bill.amount)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      ) : (
        <p className="mb-4">{t("payments.printReceipt.noBill")}</p>
      )}
      <p className="mb-4 flex justify-between">
        <span>{t(inCredit ? "payments.printReceipt.credit" : "payments.printReceipt.balance")}</span>
        <span className="tabular-nums">
          {receipt.balance === null
            ? absent
            : money(inCredit ? receipt.balance.replace(/^-/, "") : receipt.balance)}
        </span>
      </p>
      <dl className="mb-4 grid grid-cols-2 gap-x-4 gap-y-1 text-neutral-700">
        <dt>{t("payments.printReceipt.takenBy")}</dt>
        <dd>{receipt.taken_by ?? absent}</dd>
        {receipt.counter ? (
          <>
            <dt>{t("payments.printReceipt.counter")}</dt>
            <dd>{receipt.counter}</dd>
          </>
        ) : null}
      </dl>
      <p className="text-center">{t("payments.printReceipt.thanks")}</p>
    </article>
  );
}

/** Copy the app's stylesheets into the receipt window, so its classes resolve. */
function copyStyles(target: Document) {
  document.querySelectorAll('link[rel="stylesheet"], style').forEach((node) => {
    target.head.appendChild(node.cloneNode(true));
  });
}

export function PrintReceiptButton(props: {
  paymentId: string;
  client?: ApiClient;
  locale?: string;
}) {
  const { t } = useTranslation();
  // The recorded-payment panel is a shared component some tests mount bare.
  const toast = useToastIfMounted();
  const [target, setTarget] = useState<{ win: Window; root: HTMLElement } | null>(null);

  function open() {
    // No `openWindow` prop: a test stubs `window.open` instead (DEF-PAY-10762,
    // gate G13 — an optional prop nothing in the product passes is dead UI).
    const win = window.open("", "_blank", "width=640,height=820");
    if (!win) {
      toast(t("payments.printReceipt.blocked"));
      return;
    }
    win.document.title = t("payments.printReceipt.title");
    copyStyles(win.document);
    const root = win.document.createElement("div");
    win.document.body.appendChild(root);
    setTarget({ win, root });
  }

  return (
    <>
      <Button variant="secondary" onClick={open}>
        {t("payments.printReceipt.action")}
      </Button>
      {target
        ? createPortal(
            <ReceiptSheet
              paymentId={props.paymentId}
              client={props.client}
              locale={props.locale}
              onReady={() => {
                target.win.focus();
                target.win.print();
              }}
            />,
            target.root,
          )
        : null}
    </>
  );
}
