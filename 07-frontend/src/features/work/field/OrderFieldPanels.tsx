// ── Trace ──────────────────────────────────────────────
// Stories:  US-WRK-059 (EP-WRK-11) — on the order's own page: what the field
//           SAID (the outcome, its reason or that the reason is missing, the
//           blocker, the steps a partial left undone, the photographs, the
//           cost) and every time the job CAME BACK (reopened, or followed on)
//           · US-WRK-057 — *Send alert…* to the holder's handset
// Server:   GET /work-orders/{id}/outcome · GET /work-orders/{id}/come-backs
// Rules:    BR-FLD-00004 (four outcomes; Waiting on someone is not a failure,
//           E2E-06) · E2E-04 (*"Office sees which steps remain"*) · E2E-17/18
//           (reopen and follow-on are DISTINGUISHABLE) · hard rule 2 (cost
//           displayed to 2, a string from the server) · B14 rules 31 (an
//           order NUMBER is shown, never its id) · 33 · 41 · 43 · 21
// Impacts:  src/features/work/OrderDetailPage.tsx (the Overview tab mounts it)
// ───────────────────────────────────────────────────────
//
// ⚠ **ONE GROUP, *From the field*, AT THE FOOT OF THE OVERVIEW — AND THE
// DRAWN HEAD IS NOT TOUCHED.** The order page is built to images 03–11 and
// its head's buttons are asserted in the drawn order (*Print · Reassign… ·
// Put on hold… · Cancel order*; rule 41). *Send alert…* is therefore this
// group's ACTION, beside its toggle, rather than a fifth button squeezed into
// a drawn row.
//
// ⚠ **CLOSED BY DEFAULT, AND THE READS HAPPEN ON OPEN.** `Disclosure` unmounts
// its body when closed, so the two reads below run only when a dispatcher
// opens the group. That keeps the order page's first paint to the reads its
// drawing needs — and it keeps `recordedServerShapes.dom.test.tsx`, which
// refuses any read with no recording of the REAL server's reply, honest: the
// two new routes have no recording yet (they need `cr168_capture_work_shapes.py`
// run against a seeded PostgreSQL, which this lane could not do), and a read
// at mount would have been a typed-up reply or a red suite. When the
// recordings land, `defaultOpen` on a completed job is a one-word change.
import { useTranslation } from "react-i18next";
import { useQuery } from "@tanstack/react-query";

import type { ApiClient } from "@/api/client";
import { Button } from "@/components/Button";
import { Disclosure } from "@/components/Disclosure";
import { FactBlock } from "@/components/FactBlock";
import { MoneyCell } from "@/components/MoneyCell";
import { StatusPill } from "@/components/StatusPill";
import { InlineLinkTo } from "@/components/Surfaces";
import { Note } from "@/components/TextBits";
import { formatDate } from "@/components/DateCell";
import { useTenantPath } from "@/routing/tenantPath";

import { getComeBacks, getOrderOutcome, orderAddress } from "./fieldDeskEndpoints";
import type { ComeBackEvent, ComeBackHistory, OrderOutcome } from "./fieldDeskEndpoints";
import { FieldBlocker, FieldOutcomePill, FieldReason } from "./fieldWords";

const COST_CURRENCY = "USD";

/** FF-36's three reasons — the technician's whole vocabulary. An office
 *  reason is free text and is shown as written. */
const TECHNICIAN_REASONS = ["wrong_outcome", "missed_step", "missing_evidence"] as const;

const SECTION_HEADING = "m-0 mb-2 font-heading text-md font-semibold";

export interface OrderFieldPanelsProps {
  orderId: string;
  completed: boolean;
  client: ApiClient;
  timeZone: string;
  dateFormat: Parameters<typeof formatDate>[2];
  /** Present on an OPEN job somebody holds — the alert rings their handset. */
  onAlert?: () => void;
}

export function OrderFieldPanels(props: OrderFieldPanelsProps) {
  const { t } = useTranslation();
  return (
    <section data-order-field="">
      <Disclosure
        variant="panel"
        title={t("work.field.title")}
        action={
          props.onAlert === undefined ? undefined : (
            <Button variant="secondary" size="sm" onClick={props.onAlert} data-action="send-alert">
              {t("work.field.alertAction")}
            </Button>
          )
        }
      >
        <OrderFieldBody {...props} />
      </Disclosure>
    </section>
  );
}

/** Mounted only while the group is open — the reads live here. */
function OrderFieldBody(props: OrderFieldPanelsProps) {
  const { t } = useTranslation();
  const outcome = useQuery({
    queryKey: ["work", "order", props.orderId, "outcome"],
    queryFn: () => getOrderOutcome(props.orderId, props.client),
    enabled: props.completed,
  });
  const comeBacks = useQuery({
    queryKey: ["work", "order", props.orderId, "come-backs"],
    queryFn: () => getComeBacks(props.orderId, props.client),
  });
  const history: ComeBackHistory | undefined = comeBacks.data;
  const events = Array.isArray(history?.events) ? history.events : [];
  const followedFrom = history?.followed_on_from ?? null;
  const cameBack = events.length > 0 || followedFrom !== null;
  return (
    <div className="flex flex-col gap-6">
      {props.completed && outcome.data !== undefined && (
        <OutcomePanel outcome={outcome.data} timeZone={props.timeZone} dateFormat={props.dateFormat} />
      )}
      {history !== undefined && cameBack && (
        <ComeBacksPanel
          events={events}
          followedFrom={followedFrom}
          timeZone={props.timeZone}
          dateFormat={props.dateFormat}
        />
      )}
      {history !== undefined && !cameBack && !props.completed && (
        <Note data-field-nothing="">{t("work.field.nothingBack")}</Note>
      )}
    </div>
  );
}

/** What the field said about the job. */
export function OutcomePanel(props: {
  outcome: OrderOutcome;
  // DEF-WRK-10646 — REQUIRED: the tenant's own pair, never a seed fallback
  // (DEF-SHL-3964). The one caller already passes both.
  timeZone: string;
  dateFormat: Parameters<typeof formatDate>[2];
}) {
  const { t } = useTranslation();
  const o = props.outcome;
  const remaining = Array.isArray(o.remaining_steps) ? o.remaining_steps : [];
  const when = (at: string | null | undefined) =>
    at ? formatDate(at, props.timeZone, props.dateFormat, true) : null;
  const paid = o.payment_received ?? null;
  const facts = [
    { id: "outcome", label: t("work.field.col.outcome"), value: <FieldOutcomePill word={o.word ?? null} /> },
    { id: "reason", label: t("work.field.col.reason"), value: <FieldReason record={o} /> },
    // FB-013 — the technician's own times, and on a paid close the money the
    // phone SAW beside what the server READ at the close (PO ruling (b)).
    ...(o.times
      ? [
          {
            id: "times",
            label: t("work.field.col.times"),
            value: (
              <span className="tabular-nums">
                {[when(o.times.arrived_at), when(o.times.finished_at)].filter(Boolean).join(" – ")}
              </span>
            ),
          },
        ]
      : []),
    ...(paid
      ? [
          {
            id: "balance-seen",
            label: t("work.field.paid.balanceSeen"),
            value: (
              <span className="inline-flex flex-wrap items-center gap-2" data-paid-balance-seen="">
                <MoneyCell amount={paid.phone.balance} currency={paid.phone.currency ?? COST_CURRENCY} />
                <Note as="span">{t("work.field.paid.asAt", { at: when(paid.phone.as_at) })}</Note>
              </span>
            ),
          },
          ...(paid.phone.latest_payment?.amount
            ? [
                {
                  id: "payment-seen",
                  label: t("work.field.paid.paymentSeen"),
                  value: (
                    <span className="inline-flex flex-wrap items-center gap-2" data-paid-payment-seen="">
                      <MoneyCell
                        amount={paid.phone.latest_payment.amount}
                        currency={paid.phone.currency ?? COST_CURRENCY}
                      />
                      {paid.phone.latest_payment.at ? (
                        <Note as="span">{when(paid.phone.latest_payment.at)}</Note>
                      ) : null}
                    </span>
                  ),
                },
              ]
            : []),
          {
            id: "balance-at-close",
            label: t("work.field.paid.balanceAtClose"),
            value:
              paid.server.owing === null ? (
                <StatusPill tone="warning">{t("work.field.paid.unread")}</StatusPill>
              ) : (
                <span className="inline-flex flex-wrap items-center gap-2" data-paid-balance-at-close="">
                  <MoneyCell
                    amount={paid.server.owing.amount}
                    currency={paid.server.owing.currency ?? paid.server.currency ?? COST_CURRENCY}
                  />
                  <Note as="span">{t("work.field.paid.asAt", { at: when(paid.server.as_at) })}</Note>
                </span>
              ),
          },
        ]
      : []),
    ...(o.kind === "blocked"
      ? [{ id: "blocker", label: t("work.field.col.blocker"), value: <FieldBlocker blocker={o.blocker} /> }]
      : []),
    {
      id: "steps",
      label: t("work.field.stepsDone"),
      value: <span className="tabular-nums">{t("work.field.stepsOf", { left: o.steps_done, total: o.steps_total })}</span>,
    },
    {
      id: "photos",
      label: t("work.field.col.photos"),
      value: <span className="tabular-nums">{o.photographs}</span>,
    },
    {
      id: "cost",
      label: t("work.field.col.cost"),
      value:
        o.cost === undefined ? null : (
          <span className="inline-flex items-center gap-2">
            <MoneyCell amount={o.cost.total} currency={COST_CURRENCY} />
            {o.cost.frozen ? (
              <StatusPill tone="success">
                {t("work.field.costReport", { version: o.cost.report_version ?? "" })}
              </StatusPill>
            ) : (
              <StatusPill tone="info">{t("work.field.costPreview")}</StatusPill>
            )}
          </span>
        ),
    },
  ];
  return (
    <div data-order-field-outcome="">
      <h3 className={SECTION_HEADING}>{t("work.field.outcomeTitle")}</h3>
      <FactBlock name="order-field-outcome" facts={facts} variant="rows" />
      {remaining.length > 0 && (
        <div className="mt-4" data-remaining-steps={remaining.length}>
          <h4 className={SECTION_HEADING}>{t("work.field.col.steps")}</h4>
          <ol className="m-0 flex list-decimal flex-col gap-1 pl-6">
            {remaining.map((step) => (
              <li key={step.seq}>
                {step.title}
                {step.is_mandatory && (
                  <>
                    {" "}
                    <StatusPill tone="warning">{t("work.field.required")}</StatusPill>
                  </>
                )}
              </li>
            ))}
          </ol>
        </div>
      )}
    </div>
  );
}

/** One line per return: *Reopened by office · 10/21/2026 14:05 · A. Reed —
 *  Customer called back*, and a follow-on's NEW order as a link. */
export function ComeBacksPanel(props: {
  events: ComeBackEvent[];
  followedFrom: { id: string; order_no: string | null } | null;
  timeZone: string;
  dateFormat: Parameters<typeof formatDate>[2];
}) {
  const { t } = useTranslation();
  const tenantPath = useTenantPath();
  const link = (ref: { id: string; order_no: string | null }) => (
    <InlineLinkTo to={tenantPath(orderAddress(ref.id))}>{ref.order_no ?? ""}</InlineLinkTo>
  );
  return (
    <div data-order-come-backs="">
      <h3 className={SECTION_HEADING}>{t("work.field.comeBacksTitle")}</h3>
      {props.followedFrom !== null && (
        <p className="m-0 mb-2" data-followed-from="">
          {t("work.field.follows")} {link(props.followedFrom)}
        </p>
      )}
      {props.events.length > 0 && (
        <ul className="m-0 flex list-none flex-col gap-2 p-0">
          {props.events.map((event) => {
            const reason = (TECHNICIAN_REASONS as readonly string[]).includes(event.reason)
              ? t(`work.field.reopenReason.${event.reason}`)
              : event.reason;
            const head = [
              t(`work.field.comeBack.${event.kind}`),
              formatDate(event.at, props.timeZone, props.dateFormat, true),
              event.by,
            ]
              .filter((part): part is string => part !== null && part !== "")
              .join(" · ");
            return (
              <li key={event.id} data-come-back={event.kind} className="flex flex-col">
                <span className="font-semibold">{head}</span>
                <span>{reason}</span>
                {event.note !== null && event.note !== "" && (
                  <span className="text-sm text-neutral-600">{event.note}</span>
                )}
                {event.follow_on !== null && (
                  <span>
                    {t("work.field.newOrder")} {link(event.follow_on)}
                  </span>
                )}
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}
