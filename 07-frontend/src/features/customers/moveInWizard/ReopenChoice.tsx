// ── Trace ──────────────────────────────────────────────
// Change:   CR-181-BRC10 F2 (lane REOPEN, 2026-10-13) — on the move-in's
//           Customer step, once a returning customer is linked: *Reopen AC-… /
//           New account*, what the old account still owes, and the clerk's
//           *Must pay first / Carry it* choice.
// Rules:    PO rulings 2026-10-13, verbatim: *"Q2 - Reopen, for the same unit
//           only ; Q3 - give opton to use whether pay it now or carry itr -
//           Must pay first · Carry it onto the reopened account · Clerk
//           chooses"* and *"Q4 - keep 5 years right now"* · DEF-127 (the
//           figure is the ledger's, shown, never moved here) · B14 rules 21,
//           31 (the account NUMBER is shown, its id is a handle), 33, 43, 44
// Server:   `owner_lookup.search` → row.reopen (`move_in_reopen.offer_for`);
//           the commit's `reopen_account_id` + `reopen_balance`
// Tests:    moveInWizard/StepCustomer.dom.test.tsx
// ───────────────────────────────────────────────────────
//
// ⚠ **THE PAYMENT IS PAYMENTS', NOT OURS.** *Must pay first* opens the account
// page's own `RecordPaymentModal` on the OLD account — the same form, the same
// door (`POST /accounts/{id}/payments`) — and then asks the search again so
// the figure drawn here is the ledger's after the payment, never one this
// screen subtracted.
import { useState } from "react";
import { useTranslation } from "react-i18next";

import { Button } from "@/components/Button";
import { formatDate, nowInZone } from "@/components/DateCell";
import type { RegionalDateFormat } from "@/components/DateCell";
import { SegmentedField } from "@/components/FormModal";
import { formatMoney } from "@/components/MoneyCell";
import { Panel } from "@/components/Panel";
import { StatusPill } from "@/components/StatusPill";
import { RefusalStrip } from "@/components/Surfaces";
import type { ApiClient } from "@/api/client";
import type { Translator } from "@/features/tenancy/settingsShared";

import { RecordPaymentModal } from "../AccountActions";
import type { CustomerReopenOffer, ReopenBalanceChoice } from "../customerEndpoints";

export type ReopenMode = "reopen" | "new";

/** True when the books say the old account owes something — or cannot say,
 *  which is asked about exactly as a debt is (fail closed, DEF-127). */
export function reopenOwes(offer: CustomerReopenOffer | null | undefined): boolean {
  if (offer === null || offer === undefined) return false;
  if (offer.outstanding === null) return true;
  return Number(offer.outstanding) > 0;
}

export function ReopenChoice(props: {
  offer: CustomerReopenOffer;
  mode: ReopenMode;
  balance: ReopenBalanceChoice | "";
  onMode: (mode: ReopenMode) => void;
  onBalance: (choice: ReopenBalanceChoice) => void;
  /** Called after Payments recorded the money — re-read the figure. */
  onPaid: () => void;
  t: Translator;
  timeZone: string;
  dateFormat: RegionalDateFormat;
  client: ApiClient;
  showErrors: boolean;
  /** Complete's refusal, routed here by the wizard (*Pay the old balance first.*). */
  refusal?: string | null;
}) {
  const { offer, t } = props;
  const [paying, setPaying] = useState(false);
  const locale = useTranslation().i18n.language;
  const currency = offer.currency ?? "USD";
  const owed = offer.outstanding === null ? null : formatMoney(offer.outstanding, currency, locale);
  const owes = reopenOwes(offer);
  const closed =
    offer.closed_at === null ? null : formatDate(offer.closed_at, props.timeZone, props.dateFormat);

  if (!offer.eligible) {
    return (
      <Panel as="section" title={t("customers.moveIn.reopen.title")} data-reopen="refused">
        <div className="flex flex-wrap items-center gap-3">
          <StatusPill tone="info">{t("customers.moveIn.reopen.new")}</StatusPill>
          <span data-reopen-why={offer.reason ?? ""}>
            {offer.reason === "too_old"
              ? t("customers.moveIn.reopen.why.too_old", { years: offer.within_years })
              : offer.reason === "unit_occupied"
                ? t("customers.moveIn.reopen.why.unit_occupied")
                : t("customers.moveIn.reopen.why.other")}
          </span>
        </div>
      </Panel>
    );
  }

  return (
    <Panel as="section" title={t("customers.moveIn.reopen.title")} data-reopen="offered">
      <div className="flex flex-col gap-5">
        <SegmentedField
          id="reopen_mode"
          label={t("customers.moveIn.reopen.accountLabel")}
          value={props.mode}
          options={[
            {
              value: "reopen",
              label: t("customers.moveIn.reopen.reopen", { account: offer.account_no }),
            },
            { value: "new", label: t("customers.moveIn.reopen.new") },
          ]}
          onChange={(value) => props.onMode(value === "new" ? "new" : "reopen")}
        />
        {props.mode === "reopen" ? (
          <div className="flex flex-wrap items-center gap-3" data-reopen-account={offer.account_no}>
            <span className="font-heading font-semibold">{offer.account_no}</span>
            {closed === null ? null : (
              <span>{t("customers.moveIn.customer.match.closedOn", { date: closed })}</span>
            )}
            {owes ? (
              <span data-reopen-owes={offer.outstanding ?? ""}>
                <StatusPill tone="danger">
                  {owed === null
                    ? t("customers.moveIn.reopen.balanceUnreadable")
                    : t("customers.moveIn.reopen.owes", { amount: owed })}
                </StatusPill>
              </span>
            ) : (
              <span data-reopen-owes="0">
                <StatusPill tone="success">{t("customers.moveIn.reopen.nothingOwed")}</StatusPill>
              </span>
            )}
          </div>
        ) : null}
        {props.mode === "reopen" && (owes || props.balance !== "") ? (
          <div className="flex flex-wrap items-end gap-4">
            <SegmentedField
              id="reopen_balance"
              label={t("customers.moveIn.reopen.balanceLabel")}
              required
              value={props.balance}
              error={
                props.showErrors && props.balance === "" && owes
                  ? t("customers.moveIn.reopen.choiceRequired")
                  : undefined
              }
              options={[
                { value: "pay_first", label: t("customers.moveIn.reopen.payFirstOption") },
                { value: "carry", label: t("customers.moveIn.reopen.carryOption") },
              ]}
              onChange={(value) => props.onBalance(value === "carry" ? "carry" : "pay_first")}
            />
            {props.balance === "pay_first" && owes && offer.outstanding !== null ? (
              <Button
                variant="primary"
                data-reopen-record-payment=""
                onClick={() => setPaying(true)}
              >
                {t("customers.moveIn.reopen.recordPayment")}
              </Button>
            ) : null}
          </div>
        ) : null}
        {props.refusal ? (
          <RefusalStrip role="alert" data-reopen-refusal="">
            {props.refusal}
          </RefusalStrip>
        ) : null}
      </div>
      {paying ? (
        <RecordPaymentModal
          accountId={offer.account_id}
          accountLabel={offer.account_no}
          currency={currency}
          balance={offer.outstanding}
          today={nowInZone(props.timeZone).slice(0, 10)}
          dateFormat={props.dateFormat}
          client={props.client}
          onClose={() => setPaying(false)}
          onRecorded={() => {
            setPaying(false);
            props.onPaid();
          }}
        />
      ) : null}
    </Panel>
  );
}
