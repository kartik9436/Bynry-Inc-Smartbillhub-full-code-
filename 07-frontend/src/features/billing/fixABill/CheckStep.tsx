// ── Trace ──────────────────────────────────────────────
// Change:  CR-180-BRC10 — F7, step 3 *Check*
// Drawing: 05-prototype/fix-a-bill-2026-10-12/16 (clerk, finance closed),
//          17 (approver, finance open), 18 (bulk)
// Rulings: decision log 2026-10-12 *FIX A BILL REVAMP*, the first entry's item 5
//          (finance closed for the clerk, open for the approver)
// Rules:   BR-BIL-044 (the approver is shown the whole of it) · BR-BIL-004
//          (an existing bill is never edited) · hard rule 2
// ───────────────────────────────────────────────────────
/**
 * STEP 3 — WHAT IT DOES, in the customer's terms first: what they owe now,
 * whether there is a refund, what they receive and when it is due. Then the
 * existing bills (never edited), then *For finance* — closed for a clerk, OPEN
 * for an approver, because the approver is who `BR-BIL-044` protects.
 */
import type { ReactNode } from "react";

import type { CorrectionPreview } from "@/api/billingOpsEndpoints";
import { StatusPill } from "@/components/StatusPill";
import { PlainTable } from "@/components/Surfaces";
import { Note } from "@/components/TextBits";

import {
  CollapsiblePanel,
  OTB_TABLE,
  OtbPanel,
  PanelAside,
  TableScroll,
} from "../oneTimeBill/oneTimeBillShared";

import { periodLabel, signOf } from "./fixABillModel";
import type { Translate } from "./fixABillModel";
import { Band, changeBandTone, changeTone, money, signedMoney } from "./fixABillShared";
import type { FixFmt } from "./fixABillShared";

function Row(props: { label: string; children: ReactNode }) {
  return (
    <div className="flex items-baseline justify-between gap-4 border-b border-divider py-3 last:border-b-0">
      <span className="text-base text-neutral-700">{props.label}</span>
      <span className="text-right font-heading text-md font-semibold">{props.children}</span>
    </div>
  );
}

/** `1 credit note + 1 new bill · by post`. */
function receives(
  counts: { credit_notes: number; new_bills: number; reprints: number; channels: string[] },
  t: Translate,
): string {
  const parts: string[] = [];
  if (counts.credit_notes > 0)
    parts.push(t("billing.fixBill.check.creditNotes", { count: counts.credit_notes }));
  if (counts.new_bills > 0)
    parts.push(t("billing.fixBill.check.newBills", { count: counts.new_bills }));
  if (counts.reprints > 0)
    parts.push(t("billing.fixBill.check.reprints", { count: counts.reprints }));
  const what = parts.length === 0 ? t("billing.fixBill.check.nothing") : parts.join(" + ");
  if (counts.channels.length === 0) return what;
  const how = counts.channels
    .map((channel) => t(`billing.fixBill.channel.${channel}`, { defaultValue: channel }))
    .join(", ");
  return `${what} · ${how}`;
}

/** Image 16/17 — For <customer>. */
export function CustomerCheck(props: {
  preview: CorrectionPreview;
  t: Translate;
  fmt: FixFmt;
  dateWords: (iso: string | null) => string;
}) {
  const { preview, t, fmt } = props;
  const customer = preview.customer;
  if (customer === null) return null;
  const net = preview.totals.net;
  const way = signOf(net);
  return (
    <OtbPanel
      id="check-customer"
      title={t("billing.fixBill.check.for", { name: customer.name ?? customer.account_no ?? "" })}
    >
      <div data-fix-check="customer">
        <Row label={t("billing.fixBill.check.owes")}>
          {money(customer.owes_before, fmt)} → {money(customer.owes_after, fmt)}
        </Row>
        <Row label={t("billing.fixBill.check.refund")}>
          {customer.refund === null || signOf(customer.refund) === "flat"
            ? t("billing.fixBill.check.no")
            : money(customer.refund, fmt)}
        </Row>
        <Row label={t("billing.fixBill.check.receive")}>{receives(customer, t)}</Row>
        <Row label={t("billing.fixBill.check.due")}>{props.dateWords(customer.new_due_date)}</Row>
      </div>
      <Band tone={changeBandTone(net)}>
        <strong>{t(`billing.fixBill.check.asks.${way}`)}</strong>
      </Band>
    </OtbPanel>
  );
}

/** Image 18 — For the customers. */
export function BulkCheck(props: { preview: CorrectionPreview; t: Translate; fmt: FixFmt }) {
  const { preview, t, fmt } = props;
  const bulk = preview.bulk;
  if (bulk === null) return null;
  const { up, down } = preview.totals;
  return (
    <OtbPanel id="check-customers" title={t("billing.fixBill.check.forAll")}>
      <div data-fix-check="customer">
        <Row label={t("billing.fixBill.check.oweMore")}>
          <span className={changeTone(up.amount)}>
            {t("billing.fixBill.check.customers", {
              count: up.count,
              amount: signedMoney(up.amount, fmt),
            })}
          </span>
        </Row>
        <Row label={t("billing.fixBill.check.oweLess")}>
          <span className={changeTone(down.amount)}>
            {t("billing.fixBill.check.customers", {
              count: down.count,
              amount: signedMoney(down.amount, fmt),
            })}
          </span>
        </Row>
        <Row label={t("billing.fixBill.check.refunds")}>
          {bulk.refunds === null || signOf(bulk.refunds) === "flat"
            ? t("billing.fixBill.check.noRefunds")
            : money(bulk.refunds, fmt)}
        </Row>
        <Row label={t("billing.fixBill.check.receive")}>{receives(bulk, t)}</Row>
      </div>
    </OtbPanel>
  );
}

/** Existing bills — never edited. One customer: a row per bill. Bulk: counts. */
export function ExistingBills(props: {
  preview: CorrectionPreview;
  cls: string | null;
  t: Translate;
  fmt: FixFmt;
}) {
  const { preview, t, fmt } = props;
  const aside = <PanelAside>{t("billing.fixBill.check.neverEdited")}</PanelAside>;
  if (preview.bulk !== null) {
    return (
      <OtbPanel id="check-existing" title={t("billing.fixBill.check.existing")} aside={aside}>
        <div data-fix-check="existing">
          <Row label={t("billing.fixBill.check.replaced")}>
            {preview.totals.up.count + preview.totals.down.count}
          </Row>
          <Row label={t("billing.fixBill.check.leftAsIs")}>{preview.totals.unchanged}</Row>
          <Row label={t("billing.fixBill.check.paymentsMoved")}>
            {money(preview.bulk.payments_moved, fmt)}
          </Row>
        </div>
      </OtbPanel>
    );
  }
  const becomes =
    props.cls === "credit_only" ? "credited" : props.cls === "document" ? "reprinted" : "corrected";
  return (
    <OtbPanel id="check-existing" title={t("billing.fixBill.check.existing")} aside={aside}>
      <TableScroll>
        <PlainTable className={OTB_TABLE} data-fix-check="existing">
          <thead>
            <tr>
              <th scope="col">{t("billing.fixBill.col.bill")}</th>
              <th scope="col">{t("billing.fixBill.col.becomes")}</th>
              <th scope="col" data-num="">
                {t("billing.fixBill.col.paid")}
              </th>
              <th scope="col" data-num="">
                {t("billing.fixBill.col.moves")}
              </th>
              <th scope="col" data-num="">
                {t("billing.fixBill.col.stillOwed")}
              </th>
            </tr>
          </thead>
          <tbody>
            {preview.bills.map((bill) => (
              <tr key={bill.invoice_id}>
                <td>{bill.invoice_no ?? "—"}</td>
                <td>
                  <span className="inline-flex items-center gap-2">
                    <StatusPill tone="muted">
                      {t(`billing.fixBill.check.becomes.${becomes}`)}
                    </StatusPill>
                    {becomes === "corrected" && <span>→ {t("billing.fixBill.check.newBill")}</span>}
                  </span>
                </td>
                <td data-num="">{money(bill.paid, fmt)}</td>
                <td data-num="">{money(bill.moves_to_new_bill, fmt)}</td>
                <td data-num="">{money(bill.still_owed, fmt)}</td>
              </tr>
            ))}
          </tbody>
        </PlainTable>
      </TableScroll>
    </OtbPanel>
  );
}

/** For finance — entries, net per account, posting month per bill. CLOSED for
 *  a clerk, OPEN for an approver. */
export function ForFinance(props: {
  preview: CorrectionPreview;
  approver: boolean;
  t: Translate;
  fmt: FixFmt;
}) {
  const { preview, t, fmt } = props;
  const finance = preview.finance;
  const entryWords = {
    credit_notes: { debit: "revenueTax", credit: "receivable" },
    new_bills: { debit: "receivable", credit: "revenueTax" },
    // DEF-BIL-10085 — the concession's own entry (server lane judgment 2).
    goodwill: { debit: "writeOff", credit: "customerCredit" },
  } as const;
  return (
    <CollapsiblePanel
      key={props.approver ? "approver" : "clerk"}
      id="finance"
      title={t("billing.fixBill.finance.title")}
      aside={
        <PanelAside>
          {t("billing.fixBill.finance.net", { amount: signedMoney(finance.net, fmt) })}
        </PanelAside>
      }
      toggleLabel={t("billing.fixBill.finance.toggle")}
      defaultOpen={props.approver}
    >
      <TableScroll>
        <PlainTable className={OTB_TABLE}>
          <thead>
            <tr>
              <th scope="col">{t("billing.fixBill.finance.entry")}</th>
              <th scope="col">{t("billing.fixBill.finance.debit")}</th>
              <th scope="col">{t("billing.fixBill.finance.credit")}</th>
              <th scope="col" data-num="">
                {t("billing.fixBill.col.amount")}
              </th>
            </tr>
          </thead>
          <tbody>
            {finance.entries.map((entry) => (
              <tr key={entry.entry}>
                <td>{t(`billing.fixBill.finance.${entry.entry}`)}</td>
                <td>{t(`billing.fixBill.finance.${entryWords[entry.entry].debit}`)}</td>
                <td>{t(`billing.fixBill.finance.${entryWords[entry.entry].credit}`)}</td>
                <td data-num="">{money(entry.amount, fmt)}</td>
              </tr>
            ))}
            <tr data-total="">
              <td colSpan={3}>{t("billing.fixBill.finance.netBooks")}</td>
              <td data-num="" className={changeTone(finance.net)}>
                {signedMoney(finance.net, fmt)}
              </td>
            </tr>
          </tbody>
        </PlainTable>
        <PlainTable className={`${OTB_TABLE} mt-3`}>
          <thead>
            <tr>
              <th scope="col">{t("billing.fixBill.finance.account")}</th>
              <th scope="col" data-num="">
                {t("billing.fixBill.col.change")}
              </th>
            </tr>
          </thead>
          <tbody>
            {finance.accounts.map((account) => {
              const flat = signOf(account.change) === "flat";
              return (
                <tr key={account.code} className={flat ? "text-neutral-600" : undefined}>
                  <td>{account.name}</td>
                  <td data-num="" className={flat ? undefined : changeTone(account.change)}>
                    {signedMoney(account.change, fmt)}
                  </td>
                </tr>
              );
            })}
            <tr data-total="">
              <td>{t("billing.fixBill.finance.receivableTotal")}</td>
              <td data-num="">{signedMoney(finance.net, fmt)}</td>
            </tr>
          </tbody>
        </PlainTable>
        <PlainTable className={`${OTB_TABLE} mt-3`}>
          <thead>
            <tr>
              <th scope="col">{t("billing.fixBill.col.bill")}</th>
              <th scope="col">{t("billing.fixBill.finance.postsIn")}</th>
              <th scope="col" data-num="">
                {t("billing.fixBill.col.change")}
              </th>
            </tr>
          </thead>
          <tbody>
            {preview.bills.map((bill) => (
              <tr key={bill.invoice_id}>
                <td>{bill.invoice_no ?? "—"}</td>
                <td>
                  {bill.posting_period === null
                    ? "—"
                    : periodLabel(bill.posting_period, fmt.language)}
                </td>
                <td data-num="" className={changeTone(bill.delta)}>
                  {signedMoney(bill.delta, fmt)}
                </td>
              </tr>
            ))}
          </tbody>
        </PlainTable>
      </TableScroll>
      {finance.closed_through !== null && finance.earliest_open !== null && (
        <Note as="p" className="mt-2 text-sm">
          {t("billing.fixBill.finance.closed", {
            closed: periodLabel(finance.closed_through, fmt.language),
            open: periodLabel(finance.earliest_open, fmt.language),
          })}
        </Note>
      )}
    </CollapsiblePanel>
  );
}
