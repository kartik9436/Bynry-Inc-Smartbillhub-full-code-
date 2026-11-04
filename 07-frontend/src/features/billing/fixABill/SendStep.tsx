// ── Trace ──────────────────────────────────────────────
// Change:  CR-180-BRC10 — F8, step 4 *Send*
// Drawing: 05-prototype/fix-a-bill-2026-10-12/19 (clerk), 20 (waiting),
//          21 (approver), 22 (done, one customer), 23 (done, bulk)
// Rulings: decision log 2026-10-12 *FIX A BILL REVAMP* (step 4: tick, Send for
//          approval; the approver opens the same step and presses Approve and issue)
// Rules:   BR-BIL-014 (the case is OPENED here — nothing earlier writes) ·
//          BR-BIL-044 (approval binds the previewed figures) · B14 rule 6
//          (a reversal is a danger-tier commit) · B14 rules 31, 33
// ───────────────────────────────────────────────────────
/**
 * STEP 4 — the summary card and the one act this step is for, which depends on
 * where the case is:
 *
 *   no case yet       → *I checked the amounts* and **Send for approval**
 *                        (`POST /corrections` — the case is born here)
 *   waiting, clerk    → *Waiting for approval* and who it went to
 *   waiting, approver → **Approve and issue** (`/approve-and-issue`), or Send back
 *   done              → the numbers, and per-bill done / failed / already done
 *
 * Whether the viewer may approve is the SERVER's answer (`viewer_can_approve`,
 * contract A4); this screen never compares roles.
 *
 * The buttons sit inside the card, as drawn, and the frame's own action row is
 * hidden on this step — the act differs by viewer and a single frame commit
 * cannot carry two different acts.
 */
import type { ReactNode } from "react";

import { useState } from "react";

import type {
  CorrectionCaseV2,
  CorrectionDelivery,
  CorrectionPreview,
} from "@/api/billingOpsEndpoints";
import { CORRECTION_DELIVERIES } from "@/api/billingOpsEndpoints";
import { Button, ButtonLink } from "@/components/Button";
import { CheckboxField } from "@/components/FormModal";
import { Panel } from "@/components/Panel";
import { SegmentedControl } from "@/components/SegmentedControl";
import { PlainTable } from "@/components/Surfaces";

import { OTB_TABLE } from "../oneTimeBill/oneTimeBillShared";

import { Band, changeTone, signedMoney } from "./fixABillShared";
import type { FixFmt } from "./fixABillShared";
import type { Translate } from "./fixABillModel";

export interface SendHead {
  /** `One customer · Wrong reading`. */
  kicker: string;
  /** `Ben Bennett · AC-2026-00002`, or the run / price scope in words. */
  title: string;
  net: string;
  bills: number;
}

function Head(props: { head: SendHead; t: Translate; fmt: FixFmt }) {
  const { head, t, fmt } = props;
  return (
    <div className="flex flex-wrap items-start justify-between gap-4">
      <div className="flex min-w-0 flex-col gap-1">
        <span className="font-heading text-xs font-semibold uppercase tracking-kicker text-neutral-700">
          {head.kicker}
        </span>
        <span className="font-heading text-h4 font-semibold">{head.title}</span>
      </div>
      <div className="flex flex-col items-end gap-1">
        <span className="font-heading text-xs font-semibold uppercase tracking-kicker text-neutral-700">
          {t("billing.fixBill.send.net")}
        </span>
        <span
          className={`font-heading text-metric font-semibold tabular-nums ${changeTone(head.net)}`}
        >
          {signedMoney(head.net, fmt)}
        </span>
        <span className="text-sm text-neutral-700">
          {t("billing.fixBill.send.bills", { count: head.bills })}
        </span>
      </div>
    </div>
  );
}

function Facts(props: { rows: readonly [string, ReactNode][] }) {
  return (
    <PlainTable className={`${OTB_TABLE} mt-4`}>
      <tbody>
        {props.rows.map(([label, value]) => (
          <tr key={label}>
            <th scope="row">{label}</th>
            <td data-num="">{value}</td>
          </tr>
        ))}
      </tbody>
    </PlainTable>
  );
}

const ACTIONS = "mt-4 flex flex-wrap items-center gap-2 border-t border-divider pt-4";

/** Image 19 — the clerk, before anything is saved. */
export function SendForApproval(props: {
  head: SendHead;
  preview: CorrectionPreview;
  reasons: string;
  t: Translate;
  fmt: FixFmt;
  checked: boolean;
  onChecked: (checked: boolean) => void;
  onBack: () => void;
  onSend: () => void;
  sending: boolean;
  refusal: string | null;
  blockedReason: string | null;
}) {
  const { t, preview } = props;
  const documents =
    (preview.customer?.credit_notes ?? preview.bulk?.credit_notes ?? 0) +
    (preview.customer?.new_bills ?? preview.bulk?.new_bills ?? 0) +
    (preview.customer?.reprints ?? preview.bulk?.reprints ?? 0);
  const channels = preview.customer?.channels ?? preview.bulk?.channels ?? [];
  const cls = preview.correction_class;
  return (
    <Panel as="section" data-fix-send="clerk" aria-label={t("billing.fixBill.step.send")}>
      <Head head={props.head} t={t} fmt={props.fmt} />
      <Facts
        rows={[
          [t("billing.fixBill.send.whatWrong"), props.reasons],
          [
            t("billing.fixBill.send.whatHappens"),
            cls === null ? "—" : t(`billing.fixBill.class.${cls}`),
          ],
          [t("billing.fixBill.send.approver"), preview.approver.role_name],
          ...channels.map((channel): [string, ReactNode] => [
            t("billing.fixBill.send.sentBy", {
              channel: t(`billing.fixBill.channel.${channel}`, { defaultValue: channel }),
            }),
            t("billing.fixBill.send.documents", { count: documents }),
          ]),
        ]}
      />
      <Band tone="danger" role="note">
        <strong>{t("billing.fixBill.send.nothingSaved")}</strong>
      </Band>
      <div className="mt-4">
        <CheckboxField
          id="fix-checked"
          label={t("billing.fixBill.send.checked")}
          checked={props.checked}
          onChange={props.onChecked}
        />
      </div>
      <div className={ACTIONS}>
        <Button variant="secondary" onClick={props.onBack} className="mr-auto">
          {t("wizard.back")}
        </Button>
        <Button
          variant="primary"
          disabled={!props.checked || props.sending || props.blockedReason !== null}
          title={props.blockedReason ?? undefined}
          onClick={props.onSend}
        >
          {t("billing.fixBill.send.send")}
        </Button>
      </div>
      {props.refusal !== null && (
        <p className="m-0 mt-2 text-right text-base text-danger-500" role="alert">
          {props.refusal}
        </p>
      )}
    </Panel>
  );
}

/** Image 20 — waiting, seen by the clerk who sent it. */
export function WaitingForApproval(props: {
  head: SendHead;
  caseRow: CorrectionCaseV2;
  t: Translate;
  fmt: FixFmt;
  onClose: () => void;
  closing: boolean;
  blockedReason: string | null;
}) {
  const { t, caseRow } = props;
  const to = [caseRow.approval?.role_name, caseRow.approval?.approver_name]
    .filter((p): p is string => p != null && p !== "")
    .join(" · ");
  return (
    <Panel as="section" data-fix-send="waiting" aria-label={t("billing.fixBill.step.send")}>
      <Head head={props.head} t={t} fmt={props.fmt} />
      <Band tone="info">
        <strong>{t("billing.fixBill.send.waiting")}</strong>
        {to !== "" && <span>{t("billing.fixBill.send.sentTo", { to })}</span>}
      </Band>
      <div className={`${ACTIONS} justify-end`}>
        <Button
          variant="secondary"
          disabled={props.closing || props.blockedReason !== null}
          title={props.blockedReason ?? undefined}
          onClick={props.onClose}
        >
          {t("billing.fixBill.send.close")}
        </Button>
      </div>
    </Panel>
  );
}

/** Image 21 — the approver's view of the same step. */
export function ApproveAndIssue(props: {
  head: SendHead;
  caseRow: CorrectionCaseV2;
  t: Translate;
  fmt: FixFmt;
  dateWords: (iso: string | null) => string;
  onBack: () => void;
  onSendBack: () => void;
  /** The clerk's channels — null on a case that offers no choice (bulk). */
  onApprove: (delivery: CorrectionDelivery | null) => void;
  working: boolean;
  refusal: string | null;
  blockedReason: string | null;
}) {
  const { t, caseRow } = props;
  const by = caseRow.approval?.initiated_by_name ?? null;
  const disabled = props.working || props.blockedReason !== null;
  const offer = caseRow.delivery ?? null;
  // DEF-BIL-10535 (PO 2026-10-22, Q1) — starts on the ORIGINAL bill's channels.
  const [delivery, setDelivery] = useState<CorrectionDelivery | null>(
    offer?.preselected ?? null,
  );
  return (
    <Panel as="section" data-fix-send="approver" aria-label={t("billing.fixBill.step.send")}>
      <Head head={props.head} t={t} fmt={props.fmt} />
      {by !== null && (
        <Band tone="info">
          <span>
            {t("billing.fixBill.send.sentBy2", {
              name: by,
              date: props.dateWords(caseRow.approval?.sent_on ?? null),
            })}
          </span>
        </Band>
      )}
      <Band tone="warning" role="note">
        <span>{t("billing.fixBill.send.changedRefused")}</span>
      </Band>
      {offer !== null && (
        <div className="mt-4 flex flex-col gap-1" data-fix-delivery="">
          <span id="fix-delivery-label" className="text-sm font-semibold text-neutral-700">
            {t("billing.fixBill.send.sendBy")}
          </span>
          <SegmentedControl
            purpose="choice"
            name="fix-delivery"
            label={t("billing.fixBill.send.sendBy")}
            labelledBy="fix-delivery-label"
            active={delivery ?? ""}
            onSelect={(id) => setDelivery(id as CorrectionDelivery)}
            readOnly={disabled}
            segments={CORRECTION_DELIVERIES.map((choice) => ({
              id: choice,
              label: t(`billing.fixBill.send.delivery.${choice}`),
              ...(choice !== "paper" && !offer.email_on_file
                ? { disabledReason: t("billing.fixBill.send.noEmail") }
                : {}),
            }))}
          />
        </div>
      )}
      <div className={ACTIONS}>
        <Button variant="secondary" onClick={props.onBack} className="mr-auto">
          {t("wizard.back")}
        </Button>
        <Button
          variant="secondary"
          disabled={disabled}
          title={props.blockedReason ?? undefined}
          onClick={props.onSendBack}
        >
          {t("billing.fixBill.send.sendBack")}
        </Button>
        {/* B14 rule 6 — approving issues credit notes that REVERSE issued
            bills, so the commit is danger tier (DEF-712's reasoning). */}
        <Button
          variant="danger"
          disabled={disabled}
          title={props.blockedReason ?? undefined}
          onClick={() => props.onApprove(offer !== null ? delivery : null)}
        >
          {t("billing.fixBill.send.approve")}
        </Button>
      </div>
      {props.refusal !== null && (
        <p className="m-0 mt-2 text-right text-base text-danger-500" role="alert">
          {props.refusal}
        </p>
      )}
    </Panel>
  );
}

/**
 * DEF-BIL-10082 — a case that RAN and left a bill unresolved (BR-BIL-047: the
 * case stays open while any bill is). Each bill with its result and, for a
 * failure, the reason; **Try again** resumes through `/execute`, which skips
 * every bill already done (rule 6), and **Close without correcting** abandons
 * the rest with a reason. Without this the screen read *Waiting for approval*
 * over a case already approved.
 */
/** DEF-BIL-10097 — the engine's sentence, with any database id taken out
 *  (B14 rule 31: an id is never shown). */
const ID_PATTERN = /\s*[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}/gi;
export function withoutIds(text: string): string {
  return text.replace(ID_PATTERN, "").replace(/\s{2,}/g, " ").trim();
}

export function CorrectionUnfinished(props: {
  head: SendHead;
  caseRow: CorrectionCaseV2;
  t: Translate;
  fmt: FixFmt;
  onRetry: () => void;
  onClose: () => void;
  working: boolean;
  refusal: string | null;
  blockedReason: string | null;
}) {
  const { t, caseRow } = props;
  const disabled = props.working || props.blockedReason !== null;
  return (
    <Panel as="section" data-fix-send="unfinished" aria-label={t("billing.fixBill.step.send")}>
      <Head head={props.head} t={t} fmt={props.fmt} />
      <Band tone="warning" role="note">
        <strong>{t("billing.fixBill.done.unfinished")}</strong>
      </Band>
      <dl className="m-0 mt-3 flex flex-col">
        {caseRow.bills_detail.map((bill) => {
          const failed = bill.status === "failed";
          return (
            <div
              key={bill.invoice_id}
              className="flex flex-wrap justify-between gap-x-4 border-b border-divider py-2"
              data-fix-unfinished-bill={bill.status}
            >
              <dt className="m-0 font-semibold">{bill.invoice_no ?? "—"}</dt>
              <dd className="m-0 text-right">
                {failed
                  ? t("billing.fixBill.done.failed")
                  : bill.status === "done"
                    ? [bill.credit_note_no, bill.rebill_invoice_no]
                        .filter((p): p is string => p != null && p !== "")
                        .join(" · ") || t("billing.fixBill.done.succeeded")
                    : "—"}
              </dd>
              {failed && bill.failure_reason != null && (
                <dd className="m-0 w-full text-sm text-danger-700">
                  {withoutIds(bill.failure_reason)}
                </dd>
              )}
            </div>
          );
        })}
      </dl>
      <div className={`${ACTIONS} justify-end`}>
        <Button
          variant="secondary"
          disabled={disabled}
          title={props.blockedReason ?? undefined}
          onClick={props.onClose}
        >
          {t("billing.fixBill.send.close")}
        </Button>
        <Button
          variant="primary"
          disabled={disabled}
          title={props.blockedReason ?? undefined}
          onClick={props.onRetry}
        >
          {t("billing.fixBill.done.retry")}
        </Button>
      </div>
      {props.refusal !== null && (
        <p className="m-0 mt-2 text-right text-base text-danger-500" role="alert">
          {props.refusal}
        </p>
      )}
    </Panel>
  );
}

/** Images 22–23 — done. */
export function CorrectionDone(props: {
  caseRow: CorrectionCaseV2;
  bulk: boolean;
  t: Translate;
  fmt: FixFmt;
  accountHref: string | null;
  onViewCase: () => void;
  onAnother: () => void;
}) {
  const { caseRow, t, fmt } = props;
  const doneNet = caseRow.preview?.totals.net ?? caseRow.net_delta;
  const result = caseRow.result;
  // DEF-BIL-10097 — a case read back after Try again carries no `result`;
  // its rows still say which bills are done.
  const succeeded =
    result?.succeeded.length ??
    caseRow.bills_detail.filter((bill) => bill.status === "done").length;
  const rows: [string, ReactNode, string?][] = props.bulk
    ? [
        [t("billing.fixBill.done.succeeded"), String(succeeded), "succeeded"],
        [t("billing.fixBill.done.failed"), String(result?.failed.length ?? 0), "failed"],
        [
          t("billing.fixBill.done.skipped"),
          String(result?.skipped_already_done.length ?? 0),
          "skipped",
        ],
      ]
    : caseRow.bills_detail.map((bill): [string, ReactNode] => [
        bill.invoice_no ?? "—",
        [bill.credit_note_no, bill.rebill_invoice_no]
          .filter((p): p is string => p != null && p !== "")
          .join(" · ") || "—",
      ]);
  return (
    <Panel as="section" data-fix-send="done" aria-label={t("billing.fixBill.step.send")}>
      <span
        aria-hidden="true"
        className="flex h-11 w-11 items-center justify-center bg-success-500 text-metric text-bg"
      >
        ✓
      </span>
      <h3 className="m-0 mt-3 font-heading text-h4 font-semibold">
        {t("billing.fixBill.done.title", { count: succeeded })}
      </h3>
      <dl className="m-0 mt-2 grid max-w-md grid-cols-[1fr_auto] gap-x-6 gap-y-1 text-base">
        {rows.map(([label, value, hook]) => (
          <div key={label} className="contents">
            <dt className="text-neutral-700">{label}</dt>
            <dd className="m-0 text-right font-semibold" data-fix-result={hook}>
              {value}
            </dd>
          </div>
        ))}
        <dt className="text-neutral-700">{t("billing.fixBill.send.net")}</dt>
        {/* DEF-BIL-10085 — the net the clerk and approver were SHOWN (the
            stored preview's), so a goodwill-only case reads −$40.00 here as it
            did on Check and Send, not the bill's own delta of $0.00. */}
        <dd className={`m-0 text-right font-semibold ${changeTone(doneNet)}`}>
          {doneNet === null
            ? "—"
            : signedMoney(doneNet, {
                ...fmt,
                currency: caseRow.currency ?? fmt.currency,
              })}
        </dd>
        <dt className="text-neutral-700">{t("billing.fixBill.done.case")}</dt>
        <dd className="m-0 text-right font-semibold">
          {caseRow.case_no ?? t("billing.fixBill.done.noCaseNo")}
        </dd>
      </dl>
      <div className="mt-4 flex flex-wrap gap-2">
        {!props.bulk && props.accountHref !== null ? (
          <ButtonLink to={props.accountHref} variant="primary">
            {t("billing.fixBill.done.viewAccount")}
          </ButtonLink>
        ) : (
          <Button variant="primary" onClick={props.onViewCase}>
            {t("billing.fixBill.done.viewCase")}
          </Button>
        )}
        <Button variant="secondary" onClick={props.onAnother}>
          {t("billing.fixBill.done.another")}
        </Button>
      </div>
    </Panel>
  );
}

/** A case closed without correcting. */
export function CorrectionClosed(props: { t: Translate; onAnother: () => void }) {
  return (
    <Panel as="section" data-fix-send="closed" aria-label={props.t("billing.fixBill.step.send")}>
      <p className="m-0 font-heading text-md font-semibold">
        {props.t("billing.fixBill.done.closed")}
      </p>
      <div className="mt-4">
        <Button variant="secondary" onClick={props.onAnother}>
          {props.t("billing.fixBill.done.another")}
        </Button>
      </div>
    </Panel>
  );
}
