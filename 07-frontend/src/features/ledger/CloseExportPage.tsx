// ── Trace ──────────────────────────────────────────────
// Story:    US-LED-015 (month close — the live checklist, WARN + CONFIRM with a
//           reason, the period lock, SysAdmin reopen, the closed-through
//           banner) · US-LED-016 (S42 export to accounting + the S43 send modal
//           — the GL summary, the balanced preview, the recorded idempotent
//           batch, export history and drill-back)
//           Screens: S42 · S43 (AppShell sidebar → Finance → Export to
//           accounting)
// Rules:    BR-LED-006 (Finance closes the month per fiscal settings; closed
//           periods lock; SysAdmin reopens; the five-item checklist) ·
//           BR-LED-018 (WARN + CONFIRM — never a silent close, never a hard
//           lockout) · BR-LED-017 (an export requires the covered period
//           CLOSED) · BR-LED-004 (one summary JE per period per GL account;
//           batches recorded + IDEMPOTENT; every figure drills back) ·
//           BR-LED-007 (drift refuses the handover) · BR-LED-014 (export codes
//           live on the GL mapping page, Settings → Configure) · BR-LED-020
//           (v1 is a FILE/batch export; direct connect is v2) · BR-REP-001
//           (every money group labels its basis) · IS-6 (a money action is
//           modal → explicit confirm → toast → audit) · BR-SHL-020
//           (plain-language failure) · BR-SHL-023 (one money formatting path) ·
//           BR-SHL-025 (a control this deployment cannot honour renders
//           disabled WITH its reason) · BR-SHL-044 (one page header)
// ───────────────────────────────────────────────────────
// S42/S43 — Close the month, then hand it to the accountant.
//
// ══════════════════════════════════════════════════════════════════════════
// THIS IS THE SCREEN DEF-112 MEASURED AS EMPTY
// ══════════════════════════════════════════════════════════════════════════
// The defect row is exact: the Finance → Export-to-accounting tab rendered the
// sentence *"Handing the period to an accounting package arrives with the
// export-batch story. No file is written yet."* and **zero of the five checklist
// items appeared**. The month-close journey booted a real stack, signed in
// through a browser, and went red at STEP 1 — not on a wrong figure, on the
// absence of anything to click, while `close_checklist`, `close_period`,
// `reopen_period` and the export batch with its four gates were all built,
// unit-tested and correct.
//
// ══════════════════════════════════════════════════════════════════════════
// FOUR THINGS THIS SCREEN REFUSES TO DECIDE FOR ITSELF
// ══════════════════════════════════════════════════════════════════════════
//   1. **Whether the export may be sent.** `sendable` is the SERVER's answer
//      from four gates (closed · not already handed over · foots · every account
//      mapped). This file renders it. It does not re-derive it from the four
//      booleans beside it, because a client-side fifth opinion drifts the first
//      time a gate changes and would enable a button the server then refuses.
//   2. **Whether the books balance.** `balanced` and the totals are served. No
//      money value is added, compared or rounded anywhere in this file.
//   3. **Whether a checklist item is done.** Three of the five answer `unknown`
//      — billing and payments publish no count of unissued runs, unreconciled
//      batches or unmatched bank lines. `unknown` is rendered as ITSELF, with
//      the read it wants named. A grey "?" is honest; a green tick nobody
//      derived is hard-won law 1 in a checklist.
//   4. **Whether an empty month is a closed month.** A period with no entries
//      renders as visibly EMPTY (DEF-110): the seed fixture holds one bill dated
//      30 June, so a July close today would close nothing and a screen that
//      showed a tidy zero would make that look like success.
//
// ══════════════════════════════════════════════════════════════════════════
// WHERE THIS SCREEN DIVERGES FROM `05-prototype/UtilityBilling.html`
// ══════════════════════════════════════════════════════════════════════════
// Law 6 — diff against the prototype and report BOTH directions.
//
//   · **"Before you send" has FIVE items, not the prototype's four.** BR-LED-006
//     names five (runs issued · batches reconciled · bank rec current · accruals
//     posted · remittance recorded) and the prototype draws four with "8
//     adjustments reviewed" among them. The RULE wins; the count is computed.
//   · **A CLOSE action the prototype does not draw at all.** The prototype's
//     export tab has no close button — BR-LED-006 makes closing the month an
//     explicit act and BR-LED-017 makes it the export's precondition, so the
//     checklist ends in the button that acts on it.
//   · **No "Connections" panel** (QuickBooks Connected · Stripe · Xero Set up).
//     Live ERP connections are v2 (BR-LED-020 / BR-INT-010): three green
//     "Connected" chips over nothing is DEF-007.
//     ⚠ **AMENDED 2026-09-06 (`CR-069` wave J) — THE SECOND HALF OF THIS
//     SENTENCE WAS TRUE WHEN WRITTEN AND IS NOT NOW.** It read *"and no route
//     serves a connection state"*. `GET /integrations` serves exactly that, and
//     the accounting export target is a real connection on it. So ONE line is
//     drawn — the saved destination, from the adapter's own `describe()` — and
//     the PANEL still is not, because the panel's three chips are about LIVE
//     ERP SYNC and that is still v2. The reason narrowed; it did not vanish.
//     Left as a correction rather than a rewrite, because the difference
//     between *"we cannot"* and *"we choose not to"* is the whole of what a
//     later reader needs from this line (hard-won law 2's mirror: a refusal
//     that has stopped being true is worse than one that never was).
//   · **The four send buttons are ONE target picker.** The prototype offers
//     "↗ Send to QuickBooks Online", "↓ CSV", "↓ IIF" and "↓ Xero journal CSV"
//     as four controls; all four are the SAME recorded batch with a different
//     `target`, and **no file is written by any of them** (BR-LED-020 makes v1
//     the batch and its stored payload). Four download-shaped buttons that
//     download nothing would be four broken promises instead of one honest one.
//   · **Export history is REAL and its "Status" column is not.** The prototype
//     prints "Accepted"/"Downloaded" — a state an ERP would report back and
//     nothing does. What is served is the recorded batch: sent, period,
//     destination, entries and its content hash.
//   · **Drill-back is added**, which the prototype does not draw: BR-LED-004
//     requires every exported figure to open to its dimensioned lines, and
//     US-LED-016 TC-3 is the auditor asking *"what is the 506.31?"*.
import { useEffect, useState } from "react";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import { useNavigate, useParams, useSearchParams } from "react-router-dom";
import { z } from "zod";

import { apiHref } from "@/api/apiHref";
import { api, formErrorEnvelope, isApiError } from "@/api/client";
import type { ApiClient } from "@/api/client";
import {
  EXPORT_TARGETS,
  closePeriod,
  createExportBatch,
  getCloseChecklist,
  getExportBatches,
  getExportDrift,
  getExportDrillBack,
} from "@/api/endpoints";
import type {
  ClosedPeriodRow,
  ExportBatchRow,
  ExportDrillBackResponse,
  ExportHistoryResponse,
  ExportPreviewResponse,
  ExportTarget,
} from "@/api/endpoints";
import { getIntegrationsGrid } from "@/api/integrationsEndpoints";
import type { ProviderCard } from "@/api/integrationsEndpoints";
import { ConfirmDialog } from "@/components/ConfirmDialog";
import { FormModal, TextField } from "@/components/FormModal";
import type { FormSubmitOutcome } from "@/components/FormModal";
import { DateCell } from "@/components/DateCell";
import type { RegionalDateFormat } from "@/components/DateCell";
import { MoneyCell } from "@/components/MoneyCell";
import { LoadingSkeleton, PermissionDenied } from "@/components/StateFrame";
import { useToast } from "@/components/Toast";
import { RowAction, RowActions } from "@/components/RowActions";
import { RollBackIcon } from "@/components/icons";
import { InlineLink, PlainTable } from "@/components/Surfaces";
import { Panel } from "@/components/Panel";
import {
  Dash,
  ROLE_BILLING_CLERK,
  ROLE_SYSTEM_ADMIN,
  isDenied,
  useRegional,
  useAccessCell,
  useTenantRole,
} from "@/features/metering/meteringShared";
import type { RegionalProps } from "@/features/metering/meteringShared";
import { ArrivesWith, apiErrorText, isPermissionDenied } from "@/features/tenancy/settingsShared";
import type { Translator } from "@/features/tenancy/settingsShared";
import { useTenantPath } from "@/routing/tenantPath";

import { CloseView } from "./CloseView";
import { ExportView } from "./ExportView";
import type { ExportGranularity } from "./ExportView";
import { FinanceBody, FinanceHeader, useFinancePeriod } from "./financeChrome";
import { ReopenPeriodDialog } from "./ReopenPeriodDialog";
import { FINANCE_PERMISSION, FINANCE_TAB_EXPORT, financeTabFrom } from "./financeShared";
import { ViewStrip, withView } from "./financeViewStrip";

import "./finance.css";

/* ⚠ **TAB 6 IS TWO VIEWS SINCE 2026-09-24 (`P4.12`), AND `close` IS THE LANDING
   ONE.** Finance blueprint p069 draws the pair as a strip above the params band
   — 6·1 **Close** and 6·2 **Export** — and p071's DOORS line gives the second
   one an address of its own: *"the Export view on 6·1 · a
   `/finance/export?view=export` bookmark"*.

   The strip is `financeViewStrip`'s, which is the SAME control tabs 1 and 2
   already carry (p071's component table names it) — B14 rule 43, and the
   reason `P2.18` extracted it in the first place. */
export const CLOSE_EXPORT_VIEWS = ["close", "export"] as const;
export type CloseExportViewName = (typeof CLOSE_EXPORT_VIEWS)[number];

/** WHICH HEAD BELONGS TO WHICH VIEW — a function so that it can be TESTED.
 *
 * ⚠ **THIS WAS AN INLINE TERNARY IN THE JSX AND THE SCREEN SHIPPED WITH THE
 * WRONG HEAD.** Tab 6 is two screens; the strip switched and the head went on
 * reading *"Close <month>"* over the export filter, the preview and the
 * hand-over history. `tsc`, 278 front-end cases and every gate passed over it,
 * because the title was a real translated string correctly interpolated — just
 * for the other view. Found only by opening the screen in a browser, which is
 * hard-won law 6.
 *
 * It is a function rather than a ternary so a case can assert it: a guard
 * cannot be written against an expression buried in a render tree, which is
 * why the defect had no test to fail.
 */
export function headTitleKeyFor(view: CloseExportViewName): string {
  return view === "export" ? "finance.export.headTitle" : "finance.close.headTitle";
}
export type CloseExportView = (typeof CLOSE_EXPORT_VIEWS)[number];

/** An unknown `?view=` lands on the CLOSE view and never 404s (BR-SHL-011).
 *  `/finance/export` with no query is how every existing door reaches this tab,
 *  and closing the month is what those doors were promising. */
export function closeExportViewFrom(raw: string | null): CloseExportView {
  return (CLOSE_EXPORT_VIEWS as readonly string[]).includes(raw ?? "")
    ? (raw as CloseExportView)
    : "close";
}

export const checklistQueryKey = (period: string) => ["finance", "close-checklist", period] as const;
export const previewQueryKey = (period: string, target: string) =>
  ["finance", "export-preview", period, target] as const;
export const batchesQueryKey = () => ["finance", "export-batches"] as const;
export const savedTargetQueryKey = () => ["finance", "export-saved-target"] as const;

/** The manifest key of the accounting export connection (`BR-INT-010`). */
export const ACCOUNTING_PROVIDER = "accounting_file";

/** What S43 shows and sets from the saved export connection, or `null`.
 *
 * ⚠ **EVERY BRANCH THAT RETURNS `null` IS A DELIBERATE ONE**, and the list is
 * the point of this function: no grid served · no accounting card · the card
 * has no production connection · it was never set up · it is turned off · it
 * has no sentence to show. In every one of those S43 renders exactly as it did
 * before wave J.
 *
 * ⚠ **`not_working` IS NOT ONE OF THEM, AND THAT IS THE JUDGMENT WORTH
 * NAMING.** A connection whose last test failed is still a REMEMBERED
 * DESTINATION — the utility told us where the month's journal goes, and a
 * folder that was unreachable on Tuesday does not un-tell us. Hiding the line
 * on a failed test would make S43 say *nowhere* about a destination that is
 * saved and that S8 is at that moment showing as *Not working*, which is two
 * screens disagreeing about one fact.
 *
 * ⚠ **THE FORMAT IS VALIDATED AGAINST `EXPORT_TARGETS` RATHER THAN TRUSTED.**
 * `settings` is a `Record<string, unknown>` — the connection's own config, and
 * a manifest can grow a fifth format before the ledger's four move. Feeding an
 * unvalidated string into `setTarget` would put a value in the picker that no
 * `<option>` carries, which renders as an EMPTY select and reads as a bug in
 * the screen rather than as the mismatch it is.
 *
 * ⚠ **AND `describe` IS THE SERVER'S SENTENCE, NOT ONE COMPOSED HERE.** The
 * adapter already answers *Month-end journal · QuickBooks · downloaded here*
 * and the conformance kit asserts no secret reaches it; rebuilding that line
 * from `settings` would be a second copy to keep in step and a second place a
 * secret could be joined in by mistake. */
export function savedExportTarget(
  providers: ProviderCard[] | undefined,
): { describe: string; format: ExportTarget | undefined; retentionMonths: number | null } | null {
  const card = providers?.find((one) => one.key === ACCOUNTING_PROVIDER);
  const connection = card?.connection ?? null;
  if (connection === null || connection.status === "not_set_up" || !connection.enabled) {
    return null;
  }
  const describe = connection.describe ?? connection.label;
  if (describe === null || describe === "") return null;
  const saved = connection.settings?.["file_format"];
  const format = EXPORT_TARGETS.find((one) => one === saved);
  // `P4.9` — *Keep files for*, in months. ⚠ **PARSED DEFENSIVELY AND `null` ON
  // ANYTHING ELSE**, for the same reason `format` is validated against
  // `EXPORT_TARGETS` rather than trusted: `settings` is the connection's own
  // `Record<string, unknown>` and a manifest can grow a value the screen has
  // never seen. A `null` here means *no policy*, which is what every tenant has
  // had until now — never *forever* dressed up as a number.
  const months = Number(connection.settings?.["retention_months"]);
  const retentionMonths = Number.isFinite(months) && months > 0 ? months : null;
  return { describe, format, retentionMonths };
}

/**
 * The month a period STARTS in, named in the reader's own language.
 *
 * ⚠ **`Intl` RATHER THAN TWELVE CATALOGUE KEYS**, which is what the same
 * question already does on `AssetRegistryPage`. Eleven catalogues times twelve
 * months is 132 strings that every one of them would have to keep in step, for
 * a fact the platform already knows; and B14 rule 35 asks for a catalogue in
 * its own language, which is exactly what `Intl.DateTimeFormat` gives.
 *
 * ⚠ **`timeZone: "UTC"` IS LOAD-BEARING.** A period starting `2026-09-01` read
 * in a negative offset is 31 August locally, and the head would name the wrong
 * month on the one screen whose whole subject is which month it is.
 *
 * `null` — never a guess — when the date is not a date this can read.
 */
export function monthName(day: string, locale: string): string | null {
  const match = /^(\d{4})-(\d{2})/.exec(day);
  if (match === null) {
    return null;
  }
  try {
    return new Intl.DateTimeFormat(locale, { month: "long", timeZone: "UTC" }).format(
      new Date(Date.UTC(Number(match[1]), Number(match[2]) - 1, 15)),
    );
  } catch {
    return null;
  }
}

export function financeRouteAbsent(error: unknown): boolean {
  return isApiError(error) && error.status === 404;
}

/* ⚠ **`CloseChecklistPanel`, `CHECKLIST_LABEL_FALLBACK` AND `checklistTone`
   MOVED TO `CloseView.tsx` ON 2026-09-24 (`P5.9`), AND NOTHING IS RE-EXPORTED
   FROM HERE.**

   The panel was *Before you close* — a BOARD of seven facts with no act
   attached to any of them, which is what the Product Owner was reading when
   they said *"as user i dont understand this screen at all"*. What replaced it
   is two numbered steps with a door on every unfinished row, and it lives in
   its own file because B14 rule 43 makes a piece of UI a COMPONENT and because
   120 lines of steps inline in this 1,096-line page would be importable by
   nothing.

   **No compatibility re-export**, exactly as `AbsentFigure`'s move recorded
   the same day: two import paths for one component is the drift a move exists
   to remove, and a re-export is how a move never finishes. `financeSurface.
   test.tsx` imports `checklistTone` from `./CloseView` now, and the three
   panel cases moved to `CloseView.dom.test.tsx` where they can assert the
   thing that actually changed. */

/* ⚠ **`ExportSummaryTable` STOOD HERE UNTIL 2026-09-24 (`P4.12`) AND IS
   DELETED, NOT MOVED.** It was the GL summary as a `PlainTable` — the same five
   columns 6·2's preview now draws — with the cost block underneath it. The
   Export view draws that table as a `DataTable`, because p070 items 4, 5 and 6
   put the toolbar, the ▦ chooser and the ↓ on it and a `PlainTable` has none of
   the three.

   **Keeping the old component beside the new one would have been dead UI**
   (hard-won law 2), and this file has deleted an uncalled component for exactly
   that reason once before — `ExportTargetPicker`, recorded in the trailer.

   **The cost block is NOT part of that table and was NOT deleted with it**: it
   is the one thing on the old component the drawing does not replace — p070
   draws no cost row — so it moved to `financeShared.ExportCostSection`, where
   the view can reach it without importing this page. */

// ── Export history (the epic's capability matrix) ─────────────────────────

export function ExportHistoryTable(props: {
  history: ExportHistoryResponse;
  t: Translator;
  locale?: string;
  //: ⚠ **THE TENANT'S CLOCK AND CALENDAR, AND THEY ARE REQUIRED (IS-8,
  //: `DEF-LED-6667`).** The SENT column rendered `row.created_at` verbatim, so
  //: a clerk read `2026-09-24T16:51:33.306729+00:00` — microseconds and a UTC
  //: offset — five rows down a finance screen where every other date goes
  //: through `DateCell`. They are not optional here on purpose: a default
  //: would let the next caller reintroduce the raw string silently, which is
  //: how this one survived (`exportView.dom.test.tsx` asserts the row's period
  //: and total; a raw ISO string is a valid non-empty string to every
  //: assertion in the suite).
  timeZone: string;
  dateFormat: RegionalDateFormat;
}) {
  const { history, t } = props;
  const tenantPath = useTenantPath();
  if (history.rows.length === 0) {
    return (
      <Panel>
        <div className="fin-panel-head">
          <h3>{t("finance.export.historyTitle")}</h3>
        </div>
        <p className="fin-absent-reason" role="note">
          {t("finance.export.historyEmpty")}
        </p>
      </Panel>
    );
  }
  return (
    <Panel>
      <div className="fin-panel-head">
        <h3>{t("finance.export.historyTitle")}</h3>
      </div>
      <PlainTable>
        <thead>
          <tr>
            <th scope="col">{t("finance.export.col.sent")}</th>
            <th scope="col">{t("finance.export.col.period")}</th>
            <th scope="col">{t("finance.export.col.destination")}</th>
            <th scope="col" className="fin-num">
              {t("finance.export.col.entries")}
            </th>
            <th scope="col" className="fin-num">
              {t("finance.export.col.total")}
            </th>
            <th scope="col">{t("finance.export.col.hash")}</th>
            {/* P4.2 — the FILE column. `p070` row 8 records this as *"a stated
                absence until P4.2"*, and P4.2 has landed: a batch's bytes are
                re-derived from its FROZEN payload by
                `GET /finance/export/batches/{id}/file`. Leaving the column out
                now would be a live endpoint behind no door — hard-won law 2's
                mirror, which no gate in this repo can see. */}
            <th scope="col">{t("finance.export.col.file")}</th>
          </tr>
        </thead>
        <tbody>
          {history.rows.map((row: ExportBatchRow) => (
            <tr key={row.batch_id}>
              <td>
                {row.created_at === null || row.created_at === undefined ? (
                  ""
                ) : (
                  // `withTime` — a hand-over is an INSTANT, and two batches on
                  // one day are told apart by the hour. The tenant's zone, not
                  // the browser's (IS-8).
                  <DateCell
                    value={row.created_at}
                    timeZone={props.timeZone}
                    dateFormat={props.dateFormat}
                    withTime
                  />
                )}
              </td>
              <td>
                {t("reports.rollup", { from: row.period.start, to: row.period.end })}
                {/* No `EXP-` number is faked. A tenant with no `export_batch`
                    series records the batch UNNUMBERED and this says so — the
                    batch's identity is (period, target), not its printed name. */}
                {row.batch_no === null ? null : <span className="met-muted"> {row.batch_no}</span>}
              </td>
              <td>{t(`finance.export.target.${row.target}`, { defaultValue: row.target })}</td>
              <td className="fin-num">{row.entries}</td>
              <td className="fin-num">
                <MoneyCell
                  amount={row.total_debits}
                  currency={row.currency}
                  locale={props.locale}
                />
              </td>
              <td>
                <code className="fin-hash">{row.content_hash.slice(0, 12)}</code>
              </td>
              <td>
                {/* An ordinary link, NOT a fetch: the BROWSER must be the thing
                    that saves the file, and `Content-Disposition: attachment`
                    is what tells it to. `<a download>` also gets the keyboard
                    and the context menu for free.

                    ⚠ The href is the API path, not a SPA route, and it is
                    tenant-scoped (`/api/{tenant}/…`) because the batch is —
                    built from the tenant the page is already on. */}
                <a
                  className="fin-hash"
                  href={apiHref(tenantPath(`/finance/export/batches/${row.batch_id}/file`))}
                  download
                >
                  {t("finance.export.downloadAgain")}
                </a>
              </td>
            </tr>
          ))}
        </tbody>
      </PlainTable>
      {/* The prototype's "Status: Accepted" column is not drawn: an ERP
          acknowledgement is a state nothing in this deployment reports back. */}
      <p className="fin-absent-reason" role="note">
        {t("finance.export.noAckStatus")}
      </p>
    </Panel>
  );
}

// ── Drill-back (US-LED-016 TC-3) ──────────────────────────────────────────

export function DrillBackPanel(props: {
  drill: ExportDrillBackResponse;
  t: Translator;
  locale?: string;
}) {
  const { drill, t } = props;
  return (
    <Panel>
      <div className="fin-panel-head">
        <h3>{t("finance.export.drillTitle", { code: drill.code })}</h3>
      </div>
      {drill.lines.length === 0 ? (
        <p className="fin-absent-reason" role="note">
          {t("finance.export.drillEmpty")}
        </p>
      ) : (
        <PlainTable>
          <thead>
            <tr>
              <th scope="col">{t("finance.journal.col.number")}</th>
              <th scope="col">{t("finance.journal.col.date")}</th>
              <th scope="col">{t("finance.export.col.side")}</th>
              <th scope="col" className="fin-num">
                {t("finance.export.col.amount")}
              </th>
              <th scope="col">{t("finance.journal.col.source")}</th>
            </tr>
          </thead>
          <tbody>
            {drill.lines.map((line, index) => (
              <tr key={`${line.entry_id}|${index}`}>
                <td>{line.je_number === null ? <Dash /> : line.je_number}</td>
                <td>{line.entry_date ?? ""}</td>
                <td>{t(`finance.export.side.${line.side}`, { defaultValue: line.side })}</td>
                <td className="fin-num">
                  <MoneyCell
                    amount={line.amount}
                    currency={line.currency ?? drill.currency}
                    locale={props.locale}
                  />
                </td>
                <td>{line.source_type ?? ""}</td>
              </tr>
            ))}
          </tbody>
        </PlainTable>
      )}
    </Panel>
  );
}

// ── The screen ────────────────────────────────────────────────────────────

export function closeSchema(t: Translator) {
  return z.object({
    // BR-TEN-043 — the moment the period shut is a business fact the caller
    // states. The server refuses a missing one rather than reading its clock.
    closed_at: z.string().min(1, t("finance.close.form.closedAtRequired")),
    reason: z.string(),
  });
}

/**
 * The day this period was handed over to an accounting package, or `null`.
 *
 * BR-LED-017 — **reopening does not recall a handover**, so 6·1b states the
 * date when there is one. A batch whose window overlaps the period at all
 * counts: a monthly close handed over as part of a quarter is still a handover
 * of this month, and saying nothing would be the more dangerous silence.
 *
 * Dates are ISO `YYYY-MM-DD` strings from the server and compare correctly as
 * strings; nothing here parses one into a `Date`.
 */
export function handedOverOn(
  batches: readonly ExportBatchRow[],
  period: { start: string; end: string },
): string | null {
  const overlapping = batches.filter(
    (batch) =>
      (batch.period.start ?? "") <= period.end && (batch.period.end ?? "") >= period.start,
  );
  if (overlapping.length === 0) {
    return null;
  }
  // The LATEST one — a month handed over twice was last sent on the later day,
  // and that is the date a clerk would be asked about.
  const days = overlapping
    .map((batch) => (batch.created_at ?? "").slice(0, 10))
    .filter((day) => day !== "")
    .sort();
  return days.length === 0 ? null : days[days.length - 1];
}

export interface CloseExportPageProps extends RegionalProps {
  client?: ApiClient; // test seam
  locale?: string;
}

export function CloseExportPage(props: CloseExportPageProps) {
  const { t, i18n } = useTranslation();
  const translate: Translator = (key, params) => t(key, params);
  const locale = i18n.language || "en";
  const client = props.client ?? api;
  const navigate = useNavigate();
  const tenantPath = useTenantPath();
  const routeParams = useParams();
  const queryClient = useQueryClient();
  const toast = useToast();
  const { timeZone, dateFormat } = useRegional(props);
  const cell = useAccessCell(FINANCE_PERMISSION, client);
  const { period, loading } = useFinancePeriod(client);

  const [target, setTarget] = useState<ExportTarget>("csv");
  const [targetTouched, setTargetTouched] = useState(false);
  const [closing, setClosing] = useState(false);
  const [closedAt, setClosedAt] = useState("");
  const [reason, setReason] = useState("");
  const [confirmSend, setConfirmSend] = useState(false);
  const [drillCode, setDrillCode] = useState<string | null>(null);
  const [sendRefusal, setSendRefusal] = useState<string | null>(null);
  const [searchParams, setSearchParams] = useSearchParams();
  const view = closeExportViewFrom(searchParams.get("view"));
  /** `P4.12` — the window 6·2's ↗ Send is about. `null` means *the open
   *  period*, which is the only window this screen could send before the
   *  Export view existed and is what the confirm dialog falls back to.
   *
   *  ⚠ **THE SEND READS THIS AND NOT THE PARAMS BAND.** 6·2 lets a clerk pick
   *  any two dates; the batch that gets written must be the range they were
   *  looking at when they pressed Send, so the view hands it over at that
   *  moment rather than the page reading a control it does not own. */
  const [sendWindow, setSendWindow] = useState<{
    from: string;
    to: string;
    granularity: ExportGranularity;
  } | null>(null);
  /** The preview 6·2 was showing when Send was pressed. **IS-6's consequence
   *  names FIGURES**, and the figures have to be the ones the clerk just read —
   *  re-reading them here would name a different window's money in the dialog
   *  that asks about this one. */
  const [sendPreview, setSendPreview] = useState<ExportPreviewResponse | null>(null);
  // `P3.2` — 6·1b's door. `null` is *no dialog open*; a row means *this period*.
  const [reopening, setReopening] = useState<ClosedPeriodRow | null>(null);
  // BR-LED-006 as AMENDED by the PO on 2026-09-24 — closing a month is
  // `system_admin` + `billing_clerk`; REOPENING is `system_admin` ONLY.
  // A `null` role means `/me/permissions` has not answered and the control is
  // OFFERED (BR-SHL-025); `close.reopen_period` is the boundary either way.
  const role = useTenantRole(client);
  const mayReopen = role === null || role === ROLE_SYSTEM_ADMIN;
  // ⚠ **THE CLOSE'S OWN GATE, WHICH IS NOT THE REOPEN'S** (`DEF-LED-6668`).
  // `apps/ledger/close.close_period` is `SYSTEM_ADMIN` + `BILLING_CLERK`
  // (ruled 2026-09-24, verbatim *"system admin and clark"*); `reopen_period`
  // is System Admin alone and is separately ruled. A `null` role means
  // `/me/permissions` has not answered and the control is OFFERED — BR-SHL-025
  // makes the server's `@require_role` the boundary either way, and this
  // decides only which sentence a disabled button carries.
  const mayClose =
    role === null || role === ROLE_SYSTEM_ADMIN || role === ROLE_BILLING_CLERK;

  const windowKey = period === null ? "" : `${period.start}|${period.end}`;
  const checklistQuery = useQuery({
    queryKey: checklistQueryKey(windowKey),
    queryFn: () => getCloseChecklist({ from: period?.start ?? "", to: period?.end ?? "" }, client),
    retry: false,
    enabled: period !== null,
  });
  /* ⚠ **THE PAGE'S OWN `GET /finance/export/preview` IS GONE (`P4.12`).** It
     read the OPEN period only, which is what this screen could do before 6·2
     existed. The Export view reads the window the clerk actually chose, and a
     second read of a different window living up here is how two panels come to
     disagree about one month — so the query went with the panels it fed.

     `previewQueryKey` is KEPT and exported: the close and the send still
     invalidate it, and `financeSurface.test.tsx` asserts its shape. */
  const historyQuery = useQuery({
    queryKey: batchesQueryKey(),
    queryFn: () => getExportBatches({}, client),
    retry: false,
  });
  // ── CR-069 wave J — WHERE THE MONTH'S JOURNAL GOES, REMEMBERED ───────────
  //
  // `BR-INT-010` makes the accounting target a CONNECTION, so the saved
  // destination is a row on the integrations grid rather than a fifth thing
  // this screen stores. Any tenant role may READ that grid
  // (`SettingsReadAnyWriteSystemAdmin`), so a Billing Clerk standing on S43
  // sees the same remembered destination a System Admin does.
  //
  // ⚠ `retry: false` AND EVERY FAILURE IS A `null`. This is a decoration on a
  // finance screen, not a precondition of it: a settings read that 403s, 404s
  // or has simply not shipped must leave S43 exactly as it was. That is why
  // `savedTarget` below is derived defensively rather than asserted.
  const targetQuery = useQuery({
    queryKey: savedTargetQueryKey(),
    queryFn: () => getIntegrationsGrid(client),
    retry: false,
  });
  const savedTarget = savedExportTarget(targetQuery.data?.providers);
  // The saved format is the DEFAULT, never an override: once a clerk has
  // chosen from the picker this month, their choice stands.
  useEffect(() => {
    if (!targetTouched && savedTarget?.format !== undefined) {
      setTarget(savedTarget.format);
    }
  }, [targetTouched, savedTarget?.format]);
  const latestBatch = historyQuery.data?.rows[0] ?? null;
  // ⚠ OQ-203's CONDITION, and it is why this query exists at all.
  //
  // The PO permitted a captured supplier invoice to be corrected AFTER its
  // period closes — *"Yes it can be corrected"* (2026-08-16) — on the stated
  // basis that the utility is told **which exported batch no longer matches**,
  // because the export is idempotent and a re-run is blocked (BR-LED-004), so
  // the difference can only be fixed by a person at the accounting system's
  // end. The registry row is blunt about the alternative: *"Building the edit
  // without that warning would be worse than freezing it."*
  //
  // This is the export screen's half of that warning — the other half fires in
  // the toast at the moment of correction, on S73. Two halves because two people
  // are involved: the clerk who corrects, and the finance officer who hands the
  // month over.
  const driftQuery = useQuery({
    queryKey: ["finance", "export", "drift"],
    queryFn: () => getExportDrift(client),
    retry: false,
  });
  const drift = driftQuery.data?.rows ?? [];
  const drillQuery = useQuery({
    queryKey: ["finance", "drill", latestBatch?.batch_id ?? "", drillCode ?? ""],
    queryFn: () =>
      getExportDrillBack({ batchId: latestBatch?.batch_id ?? "", code: drillCode ?? "" }, client),
    retry: false,
    enabled: drillCode !== null && latestBatch !== null,
  });

  const sendMutation = useMutation({
    mutationFn: (createdAt: string) =>
      createExportBatch(
        {
          // `P4.12` — the window 6·2 handed over, or the open period when the
          // send came from 6·1's own panel. Never both, and never a third
          // opinion derived here.
          from: sendWindow?.from ?? period?.start ?? "",
          to: sendWindow?.to ?? period?.end ?? "",
          target,
          granularity: sendWindow?.granularity,
          created_at: createdAt,
        },
        client,
      ),
  });

  if (isDenied(cell)) {
    return (
      <PermissionDenied
        helper={t("finance.denied")}
        onBack={() => navigate(tenantPath("/dashboard"))}
      />
    );
  }
  if (checklistQuery.isError && isPermissionDenied(checklistQuery.error)) {
    return (
      <PermissionDenied
        helper={t("finance.denied")}
        onBack={() => navigate(tenantPath("/dashboard"))}
      />
    );
  }

  const checklist = checklistQuery.data;
  const failed = checklistQuery.isError && checklist === undefined;
  const routeAbsent = failed && financeRouteAbsent(checklistQuery.error);

  async function submitClose(): Promise<FormSubmitOutcome> {
    if (period === null) {
      return { ok: false, error: { code: "", message_key: "api.error.unexpected" } };
    }
    try {
      await closePeriod(
        {
          from: period.start,
          to: period.end,
          closed_at: closedAt,
          reason: reason === "" ? undefined : reason,
        },
        client,
      );
      setClosing(false);
      setReason("");
      toast(t("finance.close.done"));
      await queryClient.invalidateQueries({ queryKey: checklistQueryKey(windowKey) });
      await queryClient.invalidateQueries({ queryKey: previewQueryKey(windowKey, target) });
      // ⚠ **AND THE VIEW'S OWN READS.** 6·2 holds its preview and its extract
      // under `["finance","export",…]` keyed by the window the CLERK chose, not
      // by this page's `windowKey` — so invalidating the two keys above leaves
      // a just-closed month still reading *"This month is still open"* on the
      // very screen that closed it. Hard-won law 2's mirror, one query key
      // down.
      await queryClient.invalidateQueries({ queryKey: ["finance", "export"] });
      return { ok: true };
    } catch (error) {
      // The 422 that names every incomplete item lands HERE, under the reason
      // field, which is BR-LED-018's WARN reaching the human who can satisfy it.
      if (isApiError(error)) {
        return { ok: false, error: formErrorEnvelope(error) };
      }
      return { ok: false, error: { code: "", message_key: "api.error.unexpected" } };
    }
  }

  async function send() {
    setSendRefusal(null);
    try {
      // BR-TEN-043 — the browser states the moment the handover happened. The
      // server reads no clock, so a retried send would otherwise stamp two.
      await sendMutation.mutateAsync(new Date().toISOString());
      setConfirmSend(false);
      toast(t("finance.export.sent"));
      await queryClient.invalidateQueries({ queryKey: batchesQueryKey() });
      await queryClient.invalidateQueries({ queryKey: previewQueryKey(windowKey, target) });
      await queryClient.invalidateQueries({ queryKey: ["finance", "export"] });
    } catch (error) {
      setSendRefusal(apiErrorText(error, translate));
    }
  }

  return (
    <div className="fin-page">
      {/* ⚠ **THE HEAD NAMES THE MONTH AND WHAT IS LEFT OF IT — `P5.9`,
          Finance blueprint p067 items ① and ②.** Every Finance tab drew the
          word *Finance* over a period rollup, and the Product Owner's report
          of this screen was *"as user i dont understand this screen at all"*.
          The drawing's answer is **Close September** over *September is open.
          3 things left.* — two sentences of three words, inside B14 rule 33's
          six-word cap for a fact.

          ⚠ **`explainer=""` IS A DELIBERATE BLANK, NOT A MISSING VALUE.** The
          tab's paragraph read *"One summary journal entry per month — not one
          per bill. Close the month first; a closed period is the only thing
          the accounting package receives."* — 28 words of RATIONALE, which
          B14 rule 33 puts at ZERO words on screen, over a head that now says
          the month and what is left. The drawing has no paragraph there.

          ⚠ **THE MONTH'S NAME IS THE CATALOGUE'S, NOT ENGLISH BUILT HERE.**
          `finance.close.headTitle` takes the month as an interpolation and the
          eleven catalogues each name it in their own language (B14 rule 35) —
          composing `"Close " + month` would have shipped an English verb in
          front of a translated noun in ten of them. */}
      <FinanceHeader
        activeTab={financeTabFrom(routeParams.tab ?? FINANCE_TAB_EXPORT)}
        explainer=""
        period={period}
        t={translate}
        timeZone={timeZone}
        dateFormat={dateFormat}
        /* ⚠ **THE HEAD FOLLOWS THE VIEW, AND IT DID NOT UNTIL THIS WAS
           OPENED IN A BROWSER.** The strip switched to Export and the page
           went on reading *"Close September"* over the export filter, the
           preview and the hand-over history — a head naming the OTHER view.
           p069 draws this screen's head as **Export** over *"Closed through
           <month>"*, and B14 rule 44 makes the drawing what is ON the screen.
           Nothing caught it: `tsc`, 278 front-end cases and every gate pass
           over a title that is a real translated string, correctly
           interpolated, for the wrong screen. */
        title={
          period === null
            ? undefined
            : view === "export"
              ? t(headTitleKeyFor(view))
              : t(headTitleKeyFor(view), { month: monthName(period.start, locale) })
        }
        rollup={
          period === null || checklist === undefined ? undefined : (
            /* ⚠ **BOTH VIEWS READ THE SAME `checklist.closed`, AND THE EXPORT
               ONE DID NOT UNTIL `DEF-LED-6663`.** p069's subtitle for Export is
               *"Closed through <month>"* — a STATEMENT ABOUT THE BOOKS — and it
               was rendered unconditionally over the current period, so on an
               open September the head said *"Closed through September."* ten
               lines above the hand-over panel's *"This month is still open."*
               on the same screen, with the send button disabled for exactly
               that reason. A sentence stating a fact about the books is derived
               from the books or it is not said at all; the Close branch beside
               it had always done this and the Export branch never checked.
               Introduced by `e03e85e47`, the fix for `DEF-LED-6657`, which was
               proved on a database already closed through August — where the
               sentence happens to be true. */
            <span className="fin-absent-reason">
              {checklist.closed
                ? view === "export"
                  ? t("finance.export.headClosedThrough", {
                      month: monthName(period.start, locale),
                    })
                  : t("finance.close.headClosed", { month: monthName(period.start, locale) })
                : `${t("finance.close.headOpen", {
                    month: monthName(period.start, locale),
                  })} ${t("finance.close.headLeft", { count: checklist.incomplete.length })}`}
            </span>
          )
        }
      />
      <FinanceBody period={period} loading={loading} t={translate}>
        {/* Rendered ABOVE everything, including the checklist: a finance officer
            who scrolls past this and sends the next month has lost the only
            notice they will ever get. Every figure carries its currency and both
            sides are quoted, because the fix is a manual posting in QuickBooks
            or Xero and "this batch is stale" is not an instruction. */}
        {drift.length > 0 && (
          <Panel className="fin-absent-panel" role="alert">
            <h3>{t("finance.export.drift.title")}</h3>
            <p>{t("finance.export.drift.help")}</p>
            <ul>
              {drift.map((row) => (
                <li key={row.batch_id}>
                  {t("finance.export.drift.row", {
                    batch: row.batch_no ?? row.target,
                    from: row.period[0],
                    to: row.period[1],
                  })}{" "}
                  <MoneyCell amount={row.carried} currency={row.currency} />
                  {" → "}
                  <MoneyCell amount={row.register_now} currency={row.currency} />
                  <span className="fin-absent-reason" role="note">
                    {row.detail}
                  </span>
                </li>
              ))}
            </ul>
          </Panel>
        )}
        {routeAbsent ? (
          <ArrivesWith
            title={t("finance.awaits.endpointTitle")}
            message={t("finance.awaits.endpoint")}
          />
        ) : failed ? (
          <Panel role="alert">
            <h3>{t("finance.error.title")}</h3>
            <p className="fin-absent-reason">{apiErrorText(checklistQuery.error, translate)}</p>
          </Panel>
        ) : checklist === undefined ? (
          <LoadingSkeleton variant="card" />
        ) : (
          <>
            {/* ── THE VIEW STRIP — `P4.12`, blueprint p069 ─────────────────
                Tab 6 is two screens: 6·1 **Close** and 6·2 **Export**. The
                strip is the SAME control tabs 1 and 2 carry (p071's component
                table names it `SegmentedControl`; ours is `ViewStrip`, which is
                that control in this product's kit — B14 rule 44), and `?view=`
                is URL state so a section is linkable into a ticket and a
                browser Back leaves it (BR-SHL-011).

                ⚠ **`close` IS THE LANDING VIEW AND THAT IS NOT A DEFAULT, IT
                IS A DOOR DECISION.** Every existing door to this tab addresses
                `/finance/export` with no query — the dashboard's month-end
                to-do among them — and what those doors promise is closing the
                month. Landing them on the Export view would move eight doors
                without touching one of them (hard-won law 2's mirror). */}
            <ViewStrip
              label={t("finance.export.viewsLabel")}
              active={view}
              items={CLOSE_EXPORT_VIEWS.map((candidate) => ({
                id: candidate,
                label: t(`finance.export.view.${candidate}`),
              }))}
              onSelect={(candidate) => setSearchParams(withView(searchParams, candidate))}
            />
            {view === "close" ? (
            <>
            {/* `P5.9` — 6·1 is a CLOSE, not a board. The two numbered steps,
                the amounts (`P5.10`) and a door on every unfinished row live in
                `CloseView`, which is a COMPONENT because B14 rule 43 says a
                piece of UI is one and because 120 lines of steps inline in this
                1,096-line page would be importable by nothing.

                ⚠ **THE CLOSED-MONTH HISTORY MOVED IN WITH THEM, AND `P3.2`'s
                `↺ reopen` MOVED WITH IT.** It was a second `Panel` of
                `FactRow`s here; p067 draws all three bands under ONE head, and
                leaving the history behind would have split one drawn screen
                across two files. The reopen action is a SIBLING LANE'S work
                (`P3.2`, landed while this was being written) and it is not
                taken over: `CloseView` draws the ACTIONS column p068 item 6
                shows, and what goes in a cell is still composed here, beside
                the state and the dialog that own it. */}
            <CloseView
              checklist={checklist}
              currency={checklist.currency ?? ""}
              month={period === null ? null : monthName(period.start, locale)}
              /* ⚠ **THE PERMISSION, NOT THE PERIOD** (`DEF-LED-6668`). This
                 passed `!checklist.closed` — the BOOKS' state into a prop
                 declared as a ROLE — so the disabled button titled itself
                 *"Your role cannot close an accounting period."* at the System
                 Admin who had just closed it. `CloseView` reads
                 `checklist.closed` itself for the other half. */
              canClose={mayClose}
              onClose={() => setClosing(true)}
              rowActions={(row) =>
                row.status === "closed" ? (
                  // B14 rule 15 — a row action is an ICON with a tooltip, which
                  // is what p068 draws (`↺ …`). BR-SHL-025 — a role that may not
                  // reopen sees the control DISABLED WITH ITS REASON, never
                  // hidden.
                  <RowActions>
                    <RowAction
                      label={t("finance.reopen.open")}
                      icon={<RollBackIcon />}
                      danger
                      reason={mayReopen ? null : t("finance.reopen.needsAdmin")}
                      onClick={() => setReopening(row)}
                    />
                  </RowActions>
                ) : null
              }
            />
            </>
            ) : (
            <>
            <ExportView
              client={client}
              t={translate}
              dateFormat={dateFormat}
              locale={props.locale}
              period={period}
              target={target}
              onTargetChange={(next) => {
                setTargetTouched(true);
                setTarget(next);
              }}
              // `P1.6` — the SERVED vocabulary, not a list typed out in the
              // front end. A fifth target added on the server reaches the
              // picker with no front-end change (CLAUDE.md law 12).
              servedTargets={historyQuery.data?.targets}
              savedDestination={savedTarget?.describe ?? null}
              retentionMonths={savedTarget?.retentionMonths ?? null}
              onOpenDestinationSettings={() => navigate(tenantPath("/settings/integrations"))}
              sendRefusal={sendRefusal}
              onDrill={(code) => setDrillCode(code)}
              onSend={(handover) => {
                setSendWindow({
                  from: handover.from,
                  to: handover.to,
                  granularity: handover.granularity,
                });
                setSendPreview(handover.preview);
                setConfirmSend(true);
              }}
            />
            {historyQuery.data !== undefined && (
              <ExportHistoryTable
                history={historyQuery.data}
                t={translate}
                locale={props.locale}
                timeZone={timeZone}
                dateFormat={dateFormat}
              />
            )}
            {drillQuery.data !== undefined && (
              <DrillBackPanel drill={drillQuery.data} t={translate} locale={props.locale} />
            )}
            <Panel>
              <div className="fin-panel-head">
                <h3>{t("finance.export.mappingTitle")}</h3>
              </div>
              <InlineLink
 type="button"
 onClick={() => navigate(tenantPath("/settings/configure"))}
              >
                {t("finance.gl.mappingLink")}
              </InlineLink>
            </Panel>
            </>
            )}
          </>
        )}
      </FinanceBody>
      {/* `P3.2` — 6·1b. The handover date is read from the batches this screen
          ALREADY holds for its drift panel; a second read of one fact is how
          two screens come to disagree about whether a month was sent. */}
      {reopening !== null && (
        <ReopenPeriodDialog
          period={reopening.period}
          periodLabel={t("reports.rollup", {
            from: reopening.period.start,
            to: reopening.period.end,
          })}
          handedOverOn={handedOverOn(historyQuery.data?.rows ?? [], reopening.period)}
          now={() => new Date().toISOString()}
          t={translate}
          client={client}
          onClose={() => setReopening(null)}
          onReopened={async () => {
            await queryClient.invalidateQueries({ queryKey: checklistQueryKey(windowKey) });
            await queryClient.invalidateQueries({ queryKey: batchesQueryKey() });
          }}
        />
      )}
      {closing && (
        <FormModal
          title={t("finance.close.formTitle")}
          kicker={t("reports.rollup", { from: period?.start ?? "", to: period?.end ?? "" })}
          schema={closeSchema(translate)}
          values={{ closed_at: closedAt, reason }}
          submitLabel={t("finance.close.formSubmit")}
          onSubmit={submitClose}
          onClose={() => setClosing(false)}
        >
          <p className="fin-absent-reason">{t("finance.close.formHelp")}</p>
          <TextField
            id="closed_at"
            label={t("finance.close.form.closedAt")}
            value={closedAt}
            onChange={setClosedAt}
            required
            help={t("finance.close.form.closedAtHelp")}
          />
          <TextField
            id="reason"
            label={t("finance.close.form.reason")}
            value={reason}
            onChange={setReason}
            multiline
            help={t("finance.close.form.reasonHelp")}
          />
        </FormModal>
      )}
      {confirmSend && sendPreview !== null && (
        // IS-6 — a money action is modal → explicit confirm → toast → audit.
        // The consequence names the FIGURES, because "Send?" over a number
        // nobody re-read is how the wrong month reaches an accountant.
        <ConfirmDialog
          title={t("finance.export.confirmTitle")}
          consequence={t("finance.export.confirmConsequence", {
            entries: sendPreview.entries,
            debits: sendPreview.total_debits,
            credits: sendPreview.total_credits,
            target: t(`finance.export.target.${sendPreview.target}`),
            from: sendPreview.period.start,
            to: sendPreview.period.end,
          })}
          confirmLabel={t("finance.export.confirmSubmit")}
          working={sendMutation.isPending}
          onConfirm={() => void send()}
          onCancel={() => setConfirmSend(false)}
        />
      )}
    </div>
  );
}

export default CloseExportPage;

// ── Lifecycle ─────────────────────────────────────────────
// packet: US-LED-016@7e1e359 (sources: 04-docs/05-modules/09-ledger/06-epics/EP-LED-05-remittance-close-export.md US-LED-015 §1-§8 + US-LED-016 §1-§8 · 09-ledger/02-business-rules.md BR-LED-004/006/007/014/017/018/020 · 09-ledger/08-worked-examples.md LE-5 + LE-9 · 08-qa/01-e2e/journeys/J19-month-end-close.md steps 1-7 · 05-prototype/UtilityBilling.html lines 3880-3935 · 12-governance/10-defect-log.csv DEF-112 + DEF-110)
// generated: 2026-08-15 by story-coder (DEF-112 lane — the tab the defect measured at 0 operable / 0 matching)
// checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-09)
// gates: RED PROVED FIRST — `src/features/ledger/closeExport.test.tsx` failed to resolve `./CloseExportPage` before this file existed; verbatim in the lane report. tsc✔ · eslint --max-warnings 0✔ · vitest✔ · vite build✔ · run_gates✔
// exceptions: (1) `sendable` is the SERVER's four-gate answer and the button renders it — this file does not re-derive it from the four flags beside it, because a client-side fifth opinion enables a button the server then refuses · (2) FIVE checklist items where the prototype draws four: BR-LED-006 names five and the rule wins · (3) three of the five render `unknown` with the read they want NAMED — billing and payments publish no counts, and a grey "?" is honest where a green tick nobody derived is not · (4) a CLOSE action the prototype does not draw at all: BR-LED-006 makes closing an explicit act and BR-LED-017 makes it the export's precondition · (5) NO "Connections" panel — live ERP connections are v2 (BR-LED-020 / BR-INT-010) and no route serves a connection state · (6) the prototype's FOUR send buttons are ONE target picker: all four are the same recorded batch with a different `target`, and **no file is written by any of them** (BR-LED-020 makes v1 the batch and its stored payload), so four download-shaped controls would be four broken promises · (7) export history omits the prototype's "Status: Accepted" column — an ERP acknowledgement is a state nothing in this deployment reports back · (8) DRILL-BACK is added, which the prototype does not draw, because BR-LED-004 requires every exported figure to open to its dimensioned lines; it reads the MOST RECENT batch, since no route lists a figure's batches · (9) an empty period renders as visibly EMPTY (DEF-110), never as a tidy balanced zero · (10) `closed_at` and `created_at` are stated by the browser (BR-TEN-043) — the server reads no clock, and the close form collects the date rather than assuming one
// amended:   2026-08-15 by story-coder (DEF-112 lane, same day) — `ExportTargetPicker` DELETED before it shipped. It was an exported `SelectField` wrapper with no caller: the page renders its own labelled `<select>` in the parameter bar and never reached for it. An exported component nothing calls is hard-won law 2 in its purest form — built, typed, styled, and not part of the product — and G13 would not have caught it, because G13 asks whether a PROP has a caller and this had no props anyone passed. Found by grepping this lane's own new exports for callers, which is the check worth repeating.
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
