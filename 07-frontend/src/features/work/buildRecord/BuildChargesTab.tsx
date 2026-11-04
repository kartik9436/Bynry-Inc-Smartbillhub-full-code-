// ── Trace ──────────────────────────────────────────────
// Change:   CR-150-BRC09 task 9 — the Charges tab. MOVED here from
//           `features/customers/BuildDetailTabs.tsx:788` by `DEF-CUS-7618`,
//           unchanged in what it renders.
// Drawing:  `05-prototype/new-connect-detail-2026-09-28/04-charges.png`
// Rules:    `CR-151-BRC09` §2 rule (1) — *"MONEY FACTS LINK; THEY ARE NOT
//           RE-IMPLEMENTED"* · B14 rule 20 · rule 31 · rule 33 (the PNG's grey
//           caption *"Payments are the account's…"* is RATIONALE and is ZERO
//           WORDS ON SCREEN) · rule 43 · CLAUDE.md hard rule 2 (money displays
//           at 2, from the SERVER's one rounding)
// Tests:    src/features/customers/BuildDetailTabs.dom.test.tsx
// ───────────────────────────────────────────────────────
//
// ══════════════════════════════════════════════════════════════════════════
// WHY NO SHARED PANEL SERVES THIS TAB, AND WHY THAT IS THE RULING
// ══════════════════════════════════════════════════════════════════════════
// There is no charges panel in `buildViews.tsx` and there is not supposed to
// be: that file's own `BuildTab` docstring says so in as many words —
// *"THERE IS NO CHARGES PANEL AND NO HISTORY PANEL (execution plan judgment
// 2). Money and its trail are facts about a PAYER … Building a third and a
// fourth copy here is the duplicate destination the ruling is about."* The
// account's own `AccountBillsTab` is the shared panel for money, and
// re-hosting it inside a build tab is wave-O judgment (2) exactly, which
// `G93` check 3 refuses BY SYMBOL.
//
// So this tab is a SUMMARY AND A DOOR: the figures are the server's own
// `display` strings from `GET /connections/{id}/record`, the lines are what
// billing sent, and every bill, payment, adjustment and journal line is
// reached by a LINK to the account. Nothing here multiplies or rounds a
// figure.
//
// ⚠ **`CR-163-BRC10` (2026-10-02, lane NC-B) — FIVE DEFECTS ON THIS TAB.**
// Each and Amount read *"Priced on the bill"* on every line because no
// display pair travelled (`DEF-CUS-9180`; the record now serves `each` and
// `line_total`, rounded once by the server); the quantity printed its stored
// scale `2.000000` (`DEF-CUS-9181`); *Paid so far* was one figure where the
// PO asked for a row per payment (`DEF-CUS-9182`; payments now publishes
// them); the payer link hung off an id DERIVED from another read
// (`DEF-CUS-9183`); and the bill number was not a link (`DEF-CUS-9184`).
// Links use the kit's `InlineLinkTo`, so they look like links.
import { useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import { Button } from "@/components/Button";
import { DateCell } from "@/components/DateCell";
import { useToast } from "@/components/Toast";
import type { KpiTile } from "@/components/KPIStrip";
import { MoneyCell } from "@/components/MoneyCell";
import { StatusPill } from "@/components/StatusPill";
import { InlineLinkTo, PlainTable } from "@/components/Surfaces";
import type { PaymentStatus } from "@/api/endpoints";
import { billDetailPath } from "@/features/billing/billingShared";
import { accountDetailPath } from "@/features/customers/customersShared";
import { AbsentValue, MoneyOrReason } from "@/features/customers/newConnectShared";
import {
  PAYMENTS_ROUTE,
  paymentStatusLabel,
  paymentStatusTone,
} from "@/features/payments/paymentsShared";

import { buildRecordQueryKey } from "../buildViews";
import type { BuildChargeLine, BuildMoney, BuildPaymentRow } from "../workEndpoints";
import { BuildAddFeeDialog } from "./BuildAddFeeDialog";
import { Facts, Section, text } from "./buildTabShell";
import type { BuildTabProps } from "./buildTabShell";

/**
 * A stored quantity as a clerk reads it — `2.000000` → `2`, `2.500000` → `2.5`
 * (`CR-163-BRC10` item 19, `DEF-CUS-9181`).
 *
 * ⚠ **TRAILING ZEROS ARE DROPPED; NOTHING IS ROUNDED.** It is string surgery on
 * the decimal the server stored, so `2.333333` stays `2.333333`: a count is not
 * money and hard rule 2's display-at-2 does not apply to it, and rounding a
 * count would print a number the bill does not hold.
 */
export function quantityText(value: string | number | null | undefined): string | null {
  if (value === null || value === undefined || value === "") {
    return null;
  }
  const raw = String(value);
  if (!/^-?\d+(\.\d+)?$/.test(raw)) {
    return raw;
  }
  return raw.includes(".") ? raw.replace(/0+$/, "").replace(/\.$/, "") : raw;
}

/** A server display pair in the line's own currency, or the stated absence. */
function LineMoney(props: { money: BuildMoney | undefined; currency: string | null | undefined; reason: string }) {
  const display = props.money?.display ?? null;
  if (display === null || display === "") {
    return <AbsentValue reason={props.reason} />;
  }
  if (props.currency === null || props.currency === undefined || props.currency === "") {
    // No currency travelled — the server's figure, unlabelled, rather than a
    // dollar sign stamped on somebody else's money (hard rule 2's CHAR(3)).
    return <span className="tabular-nums">{display}</span>;
  }
  // `display` is already the server's ONE rounding to 2; `MoneyCell` only
  // formats it (symbol and grouping) — it has nothing left to round.
  return <MoneyCell amount={display} currency={props.currency} />;
}

/** `Check #4471` — the tender's own name and the reference written on it. */
function methodText(row: BuildPaymentRow): string | null {
  const name = text(row.method_name) ?? text(row.method_code);
  const reference = text(row.confirmation);
  if (name === null) {
    return reference;
  }
  return reference === null ? name : `${name} #${reference}`;
}

/** The build states a fee may be added in — *"after submission, until
 *  approval"* (`connection_fees.STATES_TAKING_FEES`, the server's rule; the
 *  server refuses the rest regardless). */
export const STATES_TAKING_FEES = ["requested", "in_progress", "on_hold"];

export function BuildChargesTab(props: BuildTabProps) {
  const { t, record, path } = props;
  const money = record?.money ?? null;
  const queryClient = useQueryClient();
  const toast = useToast();
  const [adding, setAdding] = useState(false);
  // BR-SHL-025 — refused WITH its reason, never hidden.
  const feeRefusal =
    props.readOnlyReason ??
    (STATES_TAKING_FEES.includes(props.detail.state)
      ? null
      : t("customers.build.fee.notNow", { defaultValue: "Only before approval" }));
  const notPriced = t("customers.build.absent.notPriced", {
    defaultValue: "Nothing priced yet.",
  });
  // ⚠ **THE PAYER'S ID COMES FROM THE RECORD FIRST** (`DEF-CUS-9183`). The
  // page's own derivation (`GET /premises/{id}/build`) answers the NEWEST build
  // at the address, so on a re-built address it yields nothing and every link
  // here went dead. The record names the bill's own account.
  const payerId = text(money?.billed_to_id) ?? props.accountId;
  const lines: BuildChargeLine[] = money?.lines ?? [];
  const payments = money?.payments;
  const tiles: KpiTile[] = [];
  if (text(money?.quoted.display) !== null) {
    tiles.push({
      id: "charged",
      label: t("customers.build.fact.charged", { defaultValue: "Charged" }),
      value: <span className="tabular-nums">{money?.quoted.display}</span>,
    });
  }
  if (text(money?.taken.display) !== null) {
    tiles.push({
      id: "paid",
      label: t("customers.build.fact.paid", { defaultValue: "Paid" }),
      value: <span className="tabular-nums">{money?.taken.display}</span>,
    });
  }
  if (text(money?.outstanding.display) !== null) {
    tiles.push({
      id: "outstanding",
      label: t("customers.build.fact.outstanding", { defaultValue: "Outstanding" }),
      value: <span className="tabular-nums">{money?.outstanding.display}</span>,
    });
  }
  const invoiceId = text(money?.invoice_id);
  const invoiceNo = text(money?.invoice_no);
  // More than one bill once a fee is added after submission (item 2): each
  // line then says which bill it is on.
  const severalBills = (money?.bills ?? []).length > 1;

  return (
    <>
      <Facts id="charges" tiles={tiles} />
      <Section
        id="invoice"
        title={t("customers.build.charges.title", { defaultValue: "The invoice" })}
      >
        {/* `CR-163-BRC10` item 2 — a fee added after submission is a NEW
            issued bill on the same payer; the server decides and refuses. */}
        <p className="m-0 mb-3">
          <Button
            size="sm"
            data-act="addFee"
            disabled={feeRefusal !== null}
            title={feeRefusal ?? undefined}
            data-blocked-reason={feeRefusal ?? undefined}
            onClick={feeRefusal === null ? () => setAdding(true) : undefined}
          >
            {t("customers.build.fee.title", { defaultValue: "Add fee" })}
          </Button>
        </p>
        <dl className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <div>
            <dt className="font-heading text-xs font-semibold uppercase tracking-label text-neutral-700">
              {t("customers.build.charges.invoice", { defaultValue: "Invoice" })}
            </dt>
            <dd className="m-0" data-invoice-no={invoiceNo ?? undefined}>
              {invoiceNo === null ? (
                <AbsentValue reason={notPriced} />
              ) : invoiceId === null ? (
                <span>{invoiceNo}</span>
              ) : (
                // `DEF-CUS-9184` — the NUMBER is the value; the id is the address.
                <InlineLinkTo to={path(billDetailPath(invoiceId))} data-invoice-link="">
                  {invoiceNo}
                </InlineLinkTo>
              )}
            </dd>
          </div>
          <div>
            <dt className="font-heading text-xs font-semibold uppercase tracking-label text-neutral-700">
              {t("customers.build.charges.billedTo", { defaultValue: "Billed to" })}
            </dt>
            <dd className="m-0">
              {text(money?.billed_to) === null ? (
                <AbsentValue
                  reason={t("customers.build.absent.noAccount", { defaultValue: "No account yet." })}
                />
              ) : payerId === null ? (
                <span>{money?.billed_to}</span>
              ) : (
                <InlineLinkTo to={path(accountDetailPath(payerId))} data-billed-to-link="">
                  {money?.billed_to}
                </InlineLinkTo>
              )}
            </dd>
          </div>
        </dl>

        {lines.length === 0 ? (
          <p className="mt-4 text-sm text-neutral-700" data-build-empty="charges">
            {notPriced}
          </p>
        ) : (
          <PlainTable data-table="build-charges" className="mt-4">
            <thead>
              <tr>
                <th>{t("customers.build.charges.col.charge", { defaultValue: "Charge" })}</th>
                {severalBills && (
                  <th>{t("customers.build.charges.invoice", { defaultValue: "Invoice" })}</th>
                )}
                <th>{t("customers.build.charges.col.qty", { defaultValue: "Qty" })}</th>
                <th>{t("customers.build.charges.col.each", { defaultValue: "Each" })}</th>
                <th>{t("customers.build.charges.col.amount", { defaultValue: "Amount" })}</th>
              </tr>
            </thead>
            <tbody>
              {lines.map((line, index) => (
                <tr key={index} data-charge-line={index}>
                  <td>
                    {[text(line.charge_code), text(line.description)]
                      .filter((part): part is string => part !== null)
                      .join(" · ")}
                  </td>
                  {severalBills && <td className="tabular-nums">{text(line.invoice_no)}</td>}
                  <td className="tabular-nums" data-charge-qty="">
                    {quantityText(line.quantity)}
                  </td>
                  {/* `DEF-CUS-9180` — the SERVER's pairs, never a product taken here. */}
                  <td data-charge-each="">
                    <LineMoney money={line.each} currency={line.currency} reason={notPriced} />
                  </td>
                  <td data-charge-amount="">
                    <LineMoney money={line.line_total} currency={line.currency} reason={notPriced} />
                  </td>
                </tr>
              ))}
            </tbody>
          </PlainTable>
        )}
      </Section>

      <Section
        id="paid"
        title={t("customers.build.charges.paidTitle", { defaultValue: "Paid so far" })}
      >
        <p className="m-0">
          <MoneyOrReason money={money?.taken} reason={notPriced} />
        </p>
        {/* `DEF-CUS-9182` — one row per payment, from PAYMENTS' own rows
            (`selectors.payments_for_bills`). It is a list of facts with a door
            on each, not a second payments screen: nothing here allocates,
            reverses or sums. */}
        {payments === null || payments === undefined ? null : payments.length === 0 ? (
          <p className="mt-2 text-sm text-neutral-700" data-build-empty="payments">
            {t("customers.build.charges.noPayments", { defaultValue: "No payment yet." })}
          </p>
        ) : (
          <PlainTable data-table="build-payments" className="mt-4">
            <thead>
              <tr>
                <th>{t("customers.build.charges.pay.date", { defaultValue: "Date" })}</th>
                <th>{t("customers.build.charges.pay.method", { defaultValue: "Method" })}</th>
                <th>{t("customers.build.charges.pay.type", { defaultValue: "Type" })}</th>
                <th>{t("customers.build.charges.col.amount", { defaultValue: "Amount" })}</th>
                <th>{t("customers.build.charges.pay.receipt", { defaultValue: "Receipt" })}</th>
                <th>{t("customers.build.charges.pay.state", { defaultValue: "State" })}</th>
              </tr>
            </thead>
            <tbody>
              {payments.map((row) => (
                <tr key={row.id} data-payment-row={row.payment_no ?? row.id}>
                  <td>
                    {text(row.posted_at) === null ? null : (
                      <DateCell
                        value={row.posted_at as string}
                        timeZone={props.timeZone}
                        dateFormat={props.dateFormat}
                      />
                    )}
                  </td>
                  <td data-payment-method="">{methodText(row)}</td>
                  <td>{t(`payments.purpose.${row.purpose}`, { defaultValue: row.purpose })}</td>
                  <td>
                    <LineMoney money={row.amount} currency={row.currency} reason={notPriced} />
                  </td>
                  <td>
                    {text(row.payment_no) === null ? null : (
                      // B14 rule 31 — the receipt NUMBER is the value and the
                      // address; `/payments/<number>` opens the record.
                      <InlineLinkTo
                        to={path(`${PAYMENTS_ROUTE}/${encodeURIComponent(row.payment_no as string)}`)}
                        data-payment-link=""
                      >
                        {row.payment_no}
                      </InlineLinkTo>
                    )}
                  </td>
                  <td>
                    <StatusPill tone={paymentStatusTone(row.status as PaymentStatus)}>
                      {paymentStatusLabel(row.status as PaymentStatus, t)}
                    </StatusPill>
                  </td>
                </tr>
              ))}
            </tbody>
          </PlainTable>
        )}
        {payerId !== null && (
          <p className="mt-2">
            <InlineLinkTo
              to={`${path(accountDetailPath(payerId))}?tab=payments`}
              data-open-payments=""
            >
              {t("customers.build.charges.openPayments", { defaultValue: "Open payments" })}
            </InlineLinkTo>
          </p>
        )}
      </Section>
      {adding && (
        <BuildAddFeeDialog
          t={t}
          connectionId={props.detail.id}
          timeZone={props.timeZone}
          dateFormat={props.dateFormat}
          client={props.client}
          onClose={() => setAdding(false)}
          onAdded={(invoiceNo) => {
            setAdding(false);
            toast(
              invoiceNo === null
                ? t("customers.build.fee.addedNoNumber", { defaultValue: "Fee added." })
                : t("customers.build.fee.added", {
                    invoice: invoiceNo,
                    defaultValue: `Fee added on ${invoiceNo}.`,
                  }),
            );
            // Re-read: the new bill, its line and the summed figures all come
            // back from the SERVER (hard rule 2 — nothing is patched here).
            void queryClient.invalidateQueries({
              queryKey: buildRecordQueryKey(props.detail.id),
            });
          }}
        />
      )}
    </>
  );
}

// ── Lifecycle ─────────────────────────────────────────────
// packet: DEF-CUS-7618 · CR-150-BRC09 task 9 · `04-charges.png` (B14 rule 42)
// generated: 2026-09-28 by the DETAIL PAGE lane; MOVED into the kit the same
//   day by the DEF-CUS-7618 lane, with no change to what it renders
// checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO)
// amended: 2026-10-02 by lane NC-B (CR-163-BRC10) — DEF-CUS-9180..9184
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
