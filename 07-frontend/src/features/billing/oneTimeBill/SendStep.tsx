// ── Trace ──────────────────────────────────────────────
// Drawing: 05-prototype/one-time-bill-2026-09-30/*-4-send.png, *-07-*-send-ticked.png,
//          *-08-Interim-4-sent.png (inventory.md §5)
// Design:  11-one-time-bill-redesign.md §1 step 4 — *"Final once sent. Changes
//          need a credit note."*, a tick box *"I checked the amounts"* that
//          unlocks Send; then the sent state
// Plan:    12-one-time-bill-build-plan.md F12
// Rules:   B14 rules 6 (danger tier on an irreversible commit), 33
//          (a CONSEQUENCE ≤ 6 words per sentence, at most two), 31, 43, 44
// ───────────────────────────────────────────────────────
/**
 * STEP 4 — the send card, and the sent card that replaces it.
 *
 * ⚠ **THE SEND BUTTON IS THE FRAME'S COMMIT, NOT A BUTTON IN THIS CARD.** The
 * drawing puts `Back · Save draft · Send $168.49 bill` inside the card; the
 * product puts every wizard's footer in `WizardFrame`'s action row, which is
 * where its single-flight guard, its working state and its failure-with-
 * entered-state-preserved live (BR-SHL-019). B14 rule 38 settles a footer's
 * button order as construction, so the kit wins and the difference is
 * recorded rather than hidden. The five confirmations here (PO 2026-09-30,
 * option B — was one *"I checked the amounts"* tick) are what the page reads
 * to enable that commit.
 */
import type {
  OneTimeBillDelivery,
  OneTimeBillKind,
  OneTimeBillSent,
  OneTimeBillWarning,
} from "@/api/billingOpsEndpoints";
import { ButtonLink, Button } from "@/components/Button";
import type { Translator } from "@/components/FormModal";
import { StatusPill } from "@/components/StatusPill";
import { PlainTable } from "@/components/Surfaces";

import type { GateState } from "../billRunShared";
import { SendConfirmations } from "./SendConfirmations";
import { OTB_TABLE, day, kindName, money } from "./oneTimeBillShared";
import type { OtbFormat } from "./oneTimeBillShared";

export function SendCard(props: {
  kind: OneTimeBillKind;
  accountNo: string | null;
  customer: string;
  address: string | null;
  total: string | null;
  dueDate: string | null;
  billDate: string | null;
  dueDays: string;
  lines: number | null;
  delivery: OneTimeBillDelivery;
  warnings: readonly OneTimeBillWarning[];
  /** PO 2026-09-30, option B — the five release confirmations, each ticked. */
  confirmations: GateState;
  onConfirmationChange: (id: string, checked: boolean) => void;
  t: Translator;
  fmt: OtbFormat;
}) {
  const { t, fmt } = props;
  const firstWarning = props.warnings[0];
  return (
    <section
      className="border border-divider border-t-4 border-t-text bg-surface p-4"
      aria-label={t("billing.oneTimeBill.send.title")}
      data-otb-send=""
    >
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <p className="m-0 font-heading text-xs font-semibold uppercase tracking-kicker text-neutral-700">
            {props.accountNo === null
              ? kindName(props.kind, t)
              : t("billing.oneTimeBill.send.kicker", { kind: kindName(props.kind, t), account: props.accountNo })}
          </p>
          <p className="m-0 mt-1 font-heading text-h4 font-semibold">{props.customer}</p>
          {props.address !== null && <p className="m-0 text-base text-neutral-700">{props.address}</p>}
        </div>
        <div className="text-right">
          <p className="m-0 font-heading text-xs font-semibold uppercase tracking-kicker text-neutral-700">
            {t("billing.oneTimeBill.send.totalDue")}
          </p>
          <p className="m-0 font-heading text-metric-lg font-semibold" data-otb-send-total="">
            {money(props.total, fmt)}
          </p>
          <p className="m-0 text-base text-neutral-700">
            {t("billing.oneTimeBill.send.dueOn", { date: day(props.dueDate, fmt) })}
          </p>
        </div>
      </div>
      <div className="mt-4">
        <PlainTable className={`${OTB_TABLE} bg-bg`}>
          <tbody>
            <tr>
              <th scope="row">{t("billing.oneTimeBill.send.billDate")}</th>
              <td data-num="">{day(props.billDate, fmt)}</td>
            </tr>
            <tr>
              <th scope="row">{t("billing.oneTimeBill.send.dueDays")}</th>
              <td data-num="">{props.dueDays}</td>
            </tr>
            <tr>
              <th scope="row">{t("billing.oneTimeBill.send.lines")}</th>
              <td data-num="">{props.lines ?? "—"}</td>
            </tr>
            <tr>
              <th scope="row">{t("billing.oneTimeBill.send.sendBy")}</th>
              <td data-num="">{t(`billing.oneTimeBill.delivery.${props.delivery}`)}</td>
            </tr>
            <tr>
              <th scope="row">{t("billing.oneTimeBill.send.warnings")}</th>
              <td data-num="">
                {firstWarning === undefined ? (
                  <StatusPill tone="success">{t("billing.oneTimeBill.send.noWarnings")}</StatusPill>
                ) : (
                  <StatusPill tone="warning">
                    {/* `1 · Electric base $0.00` — a count and the first
                        warning's own words; the separator is punctuation, not
                        a word to translate. */}
                    {`${props.warnings.length} · ${t(firstWarning.key, firstWarning.params)}`}
                  </StatusPill>
                )}
              </td>
            </tr>
          </tbody>
        </PlainTable>
      </div>
      {/* B14 rule 33 — a CONSEQUENCE before an irreversible act: two
          sentences, each under six words, never cut below clarity. */}
      <p className="m-0 mt-4 bg-danger-100 px-3 py-2 text-base text-danger-700" data-otb-final="">
        <strong>{t("billing.oneTimeBill.send.final")}</strong> {t("billing.oneTimeBill.send.creditNote")}
      </p>
      <div className="mt-3">
        <SendConfirmations state={props.confirmations} onChange={props.onConfirmationChange} t={t} />
      </div>
    </section>
  );
}

export function SentCard(props: {
  sent: OneTimeBillSent;
  deliveryWord: string;
  viewHref: string | null;
  onNew: () => void;
  t: Translator;
  fmt: OtbFormat;
}) {
  const { sent, t, fmt } = props;
  return (
    <section
      className="border border-divider bg-surface p-4"
      aria-label={t("billing.oneTimeBill.sent.title", { number: sent.invoice_no ?? "" })}
      data-otb-sent=""
    >
      <span
        aria-hidden="true"
        className="flex h-10 w-10 items-center justify-center bg-success-700 text-h4 text-bg"
      >
        ✓
      </span>
      <h2 className="m-0 mt-3 font-heading text-h4 font-semibold" role="status">
        {sent.invoice_no === null
          ? t("billing.oneTimeBill.sent.titleNoNumber")
          : t("billing.oneTimeBill.sent.title", { number: sent.invoice_no })}
      </h2>
      <dl className="m-0 mt-3 grid max-w-md grid-cols-[1fr_auto] gap-x-6 gap-y-1 text-base">
        <dt className="text-neutral-700">{t("billing.oneTimeBill.sent.total")}</dt>
        <dd className="m-0 text-right font-semibold">{money(sent.total, { ...fmt, currency: sent.currency })}</dd>
        <dt className="text-neutral-700">{t("billing.oneTimeBill.sent.due")}</dt>
        <dd className="m-0 text-right font-semibold">{day(sent.due_date, fmt)}</dd>
        <dt className="text-neutral-700">{t("billing.oneTimeBill.sent.delivery")}</dt>
        <dd className="m-0 text-right font-semibold">
          {t("billing.oneTimeBill.sent.queued", { channel: props.deliveryWord })}
        </dd>
        <dt className="text-neutral-700">{t("billing.oneTimeBill.sent.reads")}</dt>
        <dd className="m-0 text-right font-semibold">{t("billing.oneTimeBill.sent.locked")}</dd>
      </dl>
      <div className="mt-4 flex flex-wrap gap-2">
        {props.viewHref !== null && (
          <ButtonLink variant="primary" to={props.viewHref}>
            {t("billing.oneTimeBill.sent.view")}
          </ButtonLink>
        )}
        <Button onClick={props.onNew}>{t("billing.oneTimeBill.sent.new")}</Button>
      </div>
    </section>
  );
}
