// ── Trace ──────────────────────────────────────────────
// Screen:   S31 · BIL-02 — the bill run, step 4 Send
// Drawing:  05-prototype/bulk-bill-run-2026-09-30/32…36-send-*.png · inventory.md §6
// Story:    US-BIL-040 (TC-1 … TC-4) · US-BIL-041 TC-3 (catch-up)
// Plan:     15-bulk-bill-run-build-plan.md F15
// Rules:    B14 rules 6 (danger tier on the send), 21, 33 (a CONSEQUENCE before
//           an irreversible act: at most two sentences of six words), 43, 44
// Defects:  DEF-BIL-8224 (no count while sending) · DEF-BIL-8220 (delivery and
//           autopay figures)
// ───────────────────────────────────────────────────────
/**
 * SEND — ONE ACKNOWLEDGED SEND, THEN WHAT WENT AND WHAT DID NOT.
 *
 * The Send card states the run, its total and bills, and the one consequence;
 * the frame's danger-tier commit (`Send N bills`) stays disabled until *I
 * checked the totals* is ticked. Pressing it issues the run through the served
 * `POST …/issue`. Sent reads the run back (`GET /billing/runs/{id}`) for how
 * many bills went out and whether any broke, and Not in this run moves to
 * Pending billing with its catch-up action.
 */
import type { ReactNode } from "react";

import type { Translator } from "@/components/FormModal";
import { Panel } from "@/components/Panel";
import { Button, ButtonLink } from "@/components/Button";
import { StatusPill } from "@/components/StatusPill";
import { PlainTable } from "@/components/Surfaces";
import type { BillRunBreakRow } from "@/features/billing/billRunEndpoints";

import { Kicker, NotAvailable, RUN_TABLE, SidePanel, TableScroll, count, day, money, span } from "./bulkRunShared";
import type { RunFormat } from "./bulkRunShared";

/** The reasons a Send break is labelled with; any other reads as the generic one. */
const SEND_REASONS = new Set([
  "line_has_no_gl_account",
  "tax_authority_has_no_live_account",
  "charge_code_has_no_live_account",
  "document_render_refused_the_issue",
  "delivery_row_could_not_be_queued",
  "issue_failed_unexpectedly",
]);

/**
 * CR-197-BRC10 Phase 3 — a break that is a MISSING ACCOUNT opens the one GL
 * mapping list filtered to the type that is missing, rather than leaving the
 * clerk to find it. Only the three account reasons map; the rest have no row
 * on that list to fix.
 */
export const SEND_REASON_GL_TYPE: Record<string, string> = {
  line_has_no_gl_account: "service_revenue",
  tax_authority_has_no_live_account: "tax",
  charge_code_has_no_live_account: "charge_code",
};

export function glMappingFixPath(reason: string): string | null {
  const type = SEND_REASON_GL_TYPE[reason];
  return type === undefined ? null : `/settings/accounting/mapping?type=${type}&status=not_mapped`;
}

export function sendReasonLabel(reason: string, t: Translator): string {
  return SEND_REASONS.has(reason) ? t(`billing.bulkRun.sendReason.${reason}`) : t("billing.bulkRun.sendReason.other");
}

/**
 * NOT SENT — the bills Send could not issue, each with its reason, apart from
 * what went (clerk check F3, DEF-BIL-8421). *Retry failed* sends only these:
 * a bill already sent is not a draft any more and cannot be sent twice.
 */
export function NotSentPanel(props: {
  breaks: readonly BillRunBreakRow[];
  working: boolean;
  onRetry: () => void;
  onClose: () => void;
  t: Translator;
  /** Record links (PO 2026-10-19): where an account number opens (new tab). */
  accountHref?: (accountId: string) => string;
  /** CR-197-BRC10 — turns `glMappingFixPath` into a tenant address. */
  tenantHref?: (path: string) => string;
}) {
  const { t } = props;
  return (
    <SidePanel
      name="not-sent"
      kicker={t("billing.bulkRun.sent.label")}
      title={
        <>
          {t("billing.bulkRun.sent.notSentTitle")} <span className="text-base text-neutral-700">{count(props.breaks.length)}</span>
        </>
      }
      note={t("billing.bulkRun.sent.retryNote")}
      closeLabel={t("billing.bulkRun.close")}
      onClose={props.onClose}
      footer={
        <Button variant="danger" disabled={props.working || props.breaks.length === 0} onClick={props.onRetry} data-retry-failed="">
          {t("billing.bulkRun.sent.retryFailed", { count: props.breaks.length })}
        </Button>
      }
    >
      <TableScroll>
        <PlainTable className={RUN_TABLE} data-run-table="not-sent">
          <thead>
            <tr>
              <th scope="col">{t("billing.bulkRun.col.account")}</th>
              <th scope="col">{t("billing.bulkRun.col.whatFailed")}</th>
            </tr>
          </thead>
          <tbody>
            {props.breaks.map((row) => (
              <tr key={row.id} data-row-account={row.account_no} data-send-reason={row.reason}>
                <td className="font-heading font-semibold">
                  {props.accountHref !== undefined && row.account_id ? (
                    <a href={props.accountHref(row.account_id)} target="_blank" rel="noreferrer" className="text-accent-700 underline">
                      {row.account_no}
                    </a>
                  ) : (
                    row.account_no
                  )}
                </td>
                <td>
                  {sendReasonLabel(row.reason, t)}
                  {props.tenantHref !== undefined && glMappingFixPath(row.reason) !== null && (
                    <>
                      {" "}
                      <a
                        href={props.tenantHref(glMappingFixPath(row.reason) as string)}
                        target="_blank"
                        rel="noreferrer"
                        className="text-accent-700 underline"
                        data-gl-mapping-fix=""
                      >
                        {t("billing.bulkRun.sendReason.fixOnGlMapping")}
                      </a>
                    </>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </PlainTable>
      </TableScroll>
    </SidePanel>
  );
}

function KeyValue(props: { rows: readonly { label: string; value: ReactNode; name: string }[] }) {
  return (
    <dl className="m-0 mt-4 border border-divider">
      {props.rows.map((row, index) => (
        <div
          key={row.name}
          className={`flex items-center justify-between gap-3 px-3 py-2 text-base ${index > 0 ? "border-t border-divider" : ""}`}
          data-send-row={row.name}
        >
          <dt>{row.label}</dt>
          <dd className="m-0 text-right">{row.value}</dd>
        </div>
      ))}
    </dl>
  );
}

/** DEF-BIL-8685 — *Signed off by J. Ortiz · Oct 1, 09:42* (D1 32): who, the
 *  day in the utility's own format, and the time. Without a name the line
 *  still says when. */
export function signedOffLine(at: string, by: string | null, fmt: RunFormat): string {
  const stamp = new Date(at);
  const time = Number.isNaN(stamp.getTime())
    ? ""
    : stamp.toLocaleTimeString("en-US", { hour: "2-digit", minute: "2-digit" });
  const when = [day(at.slice(0, 10), fmt), time].filter(Boolean).join(", ");
  return by === null
    ? fmt.t("billing.bulkRun.send.signedOff", { when })
    : fmt.t("billing.bulkRun.send.signedOffBy", { who: by, when });
}

export function SendCard(props: {
  runNo: string | null;
  cycleName: string | null;
  periodStart: string;
  periodEnd: string;
  signedOffAt: string | null;
  /** DEF-BIL-8685 — who signed off, as the run detail serves it. */
  signedOffBy?: string | null;
  total: string | null;
  bills: number | null;
  dueDate: string | null;
  templateName: string | null;
  warnings: number;
  acknowledged: boolean;
  onAcknowledged: (value: boolean) => void;
  disabled: boolean;
  fmt: RunFormat;
}) {
  const { fmt } = props;
  const { t } = fmt;
  return (
    <Panel as="section" accent aria-label={t("billing.bulkRun.send.label")} data-send-card="">
      <div className="flex items-start justify-between gap-4">
        <div>
          <Kicker as="div">{[props.runNo === null ? null : t("billing.bulkRun.aside.run", { run: props.runNo }), props.cycleName].filter(Boolean).join(" · ")}</Kicker>
          <h2 className="m-0 mt-1 font-heading text-h4 font-semibold">{span(props.periodStart, props.periodEnd, fmt)}</h2>
          {props.signedOffAt !== null && (
            <p className="m-0 mt-1 text-base text-neutral-700">
              {signedOffLine(props.signedOffAt, props.signedOffBy ?? null, fmt)}
            </p>
          )}
        </div>
        <div className="text-right">
          <Kicker as="div">{t("billing.bulkRun.total")}</Kicker>
          <p className="m-0 mt-1 font-heading text-metric-lg font-semibold" data-send-total="">
            {money(props.total, fmt)}
          </p>
          <p className="m-0 text-base text-neutral-700">
            {t("billing.bulkRun.send.billsDue", { count: props.bills ?? 0, due: day(props.dueDate, fmt) })}
          </p>
        </div>
      </div>
      <KeyValue
        rows={[
          { name: "delivery", label: t("billing.bulkRun.send.delivery"), value: <NotAvailable t={t} id="DEF-BIL-8220" /> },
          { name: "autopay", label: t("billing.bulkRun.send.autopay"), value: <NotAvailable t={t} id="DEF-BIL-8220" /> },
          { name: "template", label: t("billing.bulkRun.aside.template"), value: props.templateName ?? "—" },
          {
            name: "warnings",
            label: t("billing.bulkRun.aside.warnings"),
            value: <StatusPill tone={props.warnings > 0 ? "warning" : "neutral"}>{count(props.warnings)}</StatusPill>,
          },
        ]}
      />
      <p className="m-0 mt-4 bg-danger-100 px-3 py-2 text-base text-danger-700" role="note" data-consequence="">
        <strong>{t("billing.bulkRun.send.final")}</strong> {t("billing.bulkRun.send.creditNote")}
      </p>
      <label className="mt-4 flex items-center gap-3 font-heading text-md font-semibold">
        <input
          type="checkbox"
          checked={props.acknowledged}
          disabled={props.disabled}
          onChange={(event) => props.onAcknowledged(event.target.checked)}
          data-acknowledge=""
        />
        {t("billing.bulkRun.signOff.confirm.final")}
      </label>
    </Panel>
  );
}

export function SentCard(props: {
  sent: number;
  notSent: number;
  total: string | null;
  dueDate: string | null;
  /** DEF-BIL-8685 — Meter Reads' answer for the reads the sent bills priced. */
  meterReads?: { state: string; reads: number; locked: number } | null;
  onSeeBreaks: () => void;
  links: { viewRun: string; print: string };
  fmt: RunFormat;
}) {
  const { fmt } = props;
  const { t } = fmt;
  return (
    <Panel as="section" aria-label={t("billing.bulkRun.sent.label")} data-sent-card="">
      <span className="flex h-11 w-11 items-center justify-center bg-success-700 text-h4 text-bg" aria-hidden="true">
        ✓
      </span>
      <h2 className="m-0 mt-3 font-heading text-h4 font-semibold" data-sent-count={props.sent}>
        {t("billing.bulkRun.sent.title", { count: props.sent })}
      </h2>
      <dl className="m-0 mt-3 flex max-w-md flex-col gap-2">
        <div className="flex justify-between gap-3 text-base">
          <dt>{t("billing.bulkRun.total")}</dt>
          <dd className="m-0 font-heading font-semibold">{money(props.total, fmt)}</dd>
        </div>
        <div className="flex justify-between gap-3 text-base">
          <dt>{t("billing.bulkRun.aside.due")}</dt>
          <dd className="m-0 font-heading font-semibold">{day(props.dueDate, fmt)}</dd>
        </div>
        <div className="flex justify-between gap-3 text-base">
          <dt>{t("billing.bulkRun.send.delivery")}</dt>
          <dd className="m-0">
            <NotAvailable t={t} id="DEF-BIL-8220" />
          </dd>
        </div>
        {props.meterReads !== undefined && props.meterReads !== null && (
          <div className="flex justify-between gap-3 text-base" data-sent-row="meter-reads">
            <dt>{t("billing.bulkRun.sent.meterReads")}</dt>
            <dd className="m-0 font-heading font-semibold" data-meter-reads={props.meterReads.state}>
              {t(`billing.bulkRun.sent.meterReadsState.${props.meterReads.state}`, {
                locked: count(props.meterReads.locked),
                reads: count(props.meterReads.reads),
                defaultValue: "—",
              })}
            </dd>
          </div>
        )}
      </dl>
      {props.notSent > 0 && (
        <p className="m-0 mt-4 bg-danger-100 px-3 py-2 text-base text-danger-700" role="alert" data-not-sent={props.notSent}>
          <strong>{t("billing.bulkRun.sent.notSent", { count: props.notSent })}</strong>{" "}
          <button
            type="button"
            className="cursor-pointer border-0 bg-transparent p-0 font-semibold text-inherit underline"
            onClick={props.onSeeBreaks}
            data-see="breaks"
          >
            {t("billing.bulkRun.seeBreaks")}
          </button>
        </p>
      )}
      <div className="mt-4 flex gap-3">
        <ButtonLink variant="primary" to={props.links.viewRun} data-link="view-run">
          {t("billing.bulkRun.sent.viewRun")}
        </ButtonLink>
        <ButtonLink to={props.links.print} data-link="print">
          {t("billing.bulkRun.sent.print")}
        </ButtonLink>
      </div>
    </Panel>
  );
}

export function CatchUpStarted(props: {
  runLabel: string;
  accounts: number;
  periodStart: string;
  periodEnd: string;
  href: string;
  t: Translator;
  fmt: RunFormat;
}) {
  const { t } = props;
  return (
    <div className="bg-success-100 px-4 py-3 text-base text-success-700" role="status" data-catch-up-started="">
      <p className="m-0 font-heading font-semibold">
        {t("billing.bulkRun.catchUp.started", { run: props.runLabel, count: props.accounts })}
      </p>
      <p className="m-0 mt-1">
        {t("billing.bulkRun.catchUp.samePeriod", { period: span(props.periodStart, props.periodEnd, props.fmt) })}{" "}
        {t("billing.bulkRun.catchUp.goesThrough")}{" "}
        <a href={props.href} className="font-semibold text-success-700 underline" data-link="open-catch-up">
          {t("billing.bulkRun.catchUp.open", { run: props.runLabel })}
        </a>
      </p>
    </div>
  );
}
