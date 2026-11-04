// ── Trace ──────────────────────────────────────────────
// Story:    US-LED-014 (S41 Taxes & Remittance — BOTH bases per authority,
//           billed · collected · remitted · outstanding, the basis indicator,
//           and recording the remittance payment)
//           Screens: S41 (AppShell sidebar → Finance → Taxes & Remittance)
// Rules:    BR-LED-002 (BOTH bases always computed; the per-authority setting
//           picks the remitting basis; the remittance payment is a JE draining
//           the authority's liability) · BR-LED-013 (four columns per
//           authority) · BR-LED-019 (a remittance carries its filing
//           confirmation ref) · BR-LED-007 (the tax-payable GL ties out to
//           remittance outstanding) · BR-REP-001 (every money group labels its
//           date basis) · BR-REP-003 (dual-basis columns + basis indicator) ·
//           BR-BIL-069 (each authority has its OWN 2200-nn account — the
//           account IS the authority's identity in the books) · BR-SHL-020
//           (plain-language failure) · BR-SHL-023 (one money formatting path) ·
//           BR-SHL-025 (a control this deployment cannot honour renders
//           disabled WITH its reason) · BR-SHL-044 (one page header)
// ───────────────────────────────────────────────────────
// S41 — Taxes & Remittance.
//
// `GET /finance/taxes` has been SERVED since 2026-08-11. Until this file the
// only caller was a Settings table borrowing the authority list, and the
// dual-basis report the A1 addendum ratified — *"S41 = dual-basis remittance"*,
// which SUPERSEDED the prototype's collected-only table — had no screen at all.
//
// ══════════════════════════════════════════════════════════════════════════
// ⚠ THE COLLECTED COLUMN FILLS IN SINCE 2026-09-02 (CR-060 C19 / task T7d)
// ══════════════════════════════════════════════════════════════════════════
// This block read *"THE COLLECTED COLUMN IS EMPTY ON PURPOSE, AND IT IS THE
// POINT OF THE SCREEN … an `allocations` row names a payment, an invoice and an
// AMOUNT — it carries NO line class (OQ-129) … So the column renders ABSENT
// WITH ITS REASON"*. **NO FRONTEND CODE CHANGED, and that is the good outcome:**
// the cell has always been `row.collected === null ? absent : money(...)`, so
// the day the backend started answering, the screen started drawing the figure.
//
// WHAT CHANGED UNDERNEATH: `allocation_classes` (payments/0015) records what
// every payment actually met inside every bill, in the same transaction as the
// allocation, so the collected basis is READ rather than refused. BR-LED-794
// splits one bill's collected tax across the authorities THAT BILL charged, in
// proportion to what each was billed on it — exact whenever the bill's tax was
// met in full, which is LE-3's signed 20.97.
//
// ⚠ TWO THINGS THE SCREEN STILL SAYS, AND BOTH ARE STILL TRUE.
//   * **The cell renders ABSENT WITH ITS REASON when the figure is null**, which
//     now means the payments read is unpublished on this deployment rather than
//     that the rule is unsigned. Never the billed figure — that would remit tax
//     on money nobody has paid.
//   * **The figure is a FLOOR.** Allocations written before 2026-09-02 carry no
//     breakdown and cannot be backfilled, and a credit application or release
//     never runs the class walk; the response carries how much money that is
//     (`totals.allocated_without_breakdown`) and the absence code names it.
//
// ⚠ AND THE 20.97 SPREAD IS NOT RESOLVED BY ANY OF THIS — it is RECORDED. On a
// PARTIAL payment the same bill's collected tax is 0.00 under the shipped class
// order and 20.97 under tax-first, both correct for different tenant settings
// (BR-PAY-010 · OQ-174), and the product now reports whichever happened.
//
// ══════════════════════════════════════════════════════════════════════════
// WHERE THIS SCREEN DIVERGES FROM `05-prototype/UtilityBilling.html`
// ══════════════════════════════════════════════════════════════════════════
// Law 6 — diff against the prototype and report BOTH directions.
//
//   · **The prototype's four KPI tiles are not drawn.** "Collected this month",
//     "Remitted YTD · 7 filings", "Due next · TX Comptroller Aug 20" and
//     "Overdue · all current" each need a figure the books cannot produce: the
//     first is the collected basis (above), and the other three need FILING
//     DUE DATES, which live on `tax_remittances` — a table that is not in the
//     schema (B2 r13 #3). Four confident tiles over four missing facts.
//   · **No "Coming up" banner**, for the same reason: it names a due date.
//   · **No Tax type / Rate / Taxable base / Filing period / Due / Status
//     columns.** Every one of them is rating's (`tax_jurisdictions`) and the
//     ledger read model publishes none of them — what it has is the AUTHORITY'S
//     OWN 2200-nn ACCOUNT and the money on it.
//   · **No filing-history table and no "Receipt ↓".** `tax_remittances` does not
//     exist, so there is no register to list and no attachment column; the
//     confirmation ref survives on the immutable entry memo and in `audit_log`,
//     and `apps/ledger/journal.record_tax_remittance` REFUSES a receipt file BY
//     NAME rather than accepting one and dropping it.
//   · **"Mark as filed" is the RECORD REMITTANCE form**, which is what the
//     prototype's button means once there is a ledger behind it: recording the
//     payment posts DR 2200-nn / CR cash through the posting service.
//   · **"↓ Remittance report" renders DISABLED with its reason** (BR-SHL-025):
//     the IS-11 download needs `POST /reports/{key}/export`, served by nothing.
import { useState } from "react";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import { useNavigate, useParams } from "react-router-dom";
import { z } from "zod";

import { api, formErrorEnvelope, isApiError } from "@/api/client";
import type { ApiClient } from "@/api/client";
import {
  getRemittanceByAuthority,
  getRemittancesPaid,
  recordRemittance,
  requestListExport,
} from "@/api/endpoints";
import type { AuthorityRemittanceRow, RemittanceResponse } from "@/api/endpoints";
import { AbsentFigure } from "@/components/AbsentFigure";
import { DownloadButton } from "@/components/DownloadButton";
import { FileField } from "@/components/FileField";
import { FormModal, SelectField, TextField } from "@/components/FormModal";
import type { FormSubmitOutcome } from "@/components/FormModal";
import { MoneyCell, formatMoney } from "@/components/MoneyCell";
import { LoadingSkeleton, PermissionDenied } from "@/components/StateFrame";
import { useToast } from "@/components/Toast";
import { InlineLink, PlainTable } from "@/components/Surfaces";
import { Panel } from "@/components/Panel";
import { isDenied, useRegional, useAccessCell } from "@/features/metering/meteringShared";
import type { RegionalProps } from "@/features/metering/meteringShared";
import { ArrivesWith, apiErrorText, isPermissionDenied } from "@/features/tenancy/settingsShared";
import type { Translator } from "@/features/tenancy/settingsShared";
import { useTenantPath } from "@/routing/tenantPath";

import { FinanceBody, FinanceHeader, useFinancePeriod } from "./financeChrome";
import { PaymentsMadePanel } from "./PaymentsMadePanel";
import {
  FINANCE_PERMISSION,
  FINANCE_TAB_TAXES,
  FactRow,
  financeTabFrom,
  gapSentence,
} from "./financeShared";

import "./finance.css";

export const remittanceQueryKey = (period: string) => ["finance", "taxes", period] as const;

export function remittanceRouteAbsent(error: unknown): boolean {
  return isApiError(error) && error.status === 404;
}

/** The form a clerk fills to record what they actually paid an authority.
 *
 *  **`amount` is typed by the human and is never pre-filled from the report.**
 *  Defaulting it to the outstanding figure would make the payment agree with the
 *  report by construction — the exact property that hides a wrong report, and
 *  the reason `record_tax_remittance` refuses to derive it either. */
export interface RemittanceDraft {
  amount: string;
  basis: string;
  confirmationRef: string;
  paidOn: string;
  /** `P4.3` — the filing receipt `BR-LED-019` asks for, or `null`.
   *
   *  ⚠ **IT IS NOT IN `remittanceSchema` AND THAT IS DELIBERATE.** The rule
   *  requires the receipt as the auditor artefact and the FORM does not make it
   *  mandatory: a filing whose paper arrives a week later is an ordinary one,
   *  and blocking a clerk from recording a payment they have genuinely made
   *  would be this lane inventing a gate nobody ruled. The confirmation
   *  reference — the other half of BR-LED-019 — IS required, here and at the
   *  server. */
  receipt: File | null;
}

export const EMPTY_DRAFT: RemittanceDraft = {
  amount: "",
  // NOTHING DEFAULTS THE BASIS. LE-3 files State on COLLECTED and County on
  // BILLED in the SAME month, so a seeded value would be wrong for one of them
  // in its first month — the clerk states which return they filed.
  basis: "",
  confirmationRef: "",
  paidOn: "",
  receipt: null,
};

/** Money is a STRING all the way to the wire (CLAUDE.md rule 2) — up to six
 *  decimals, matching `NUMERIC(18,6)`, and never zero: a zero remittance moves
 *  no money and would put an empty balanced pair in the books. */
const AMOUNT_PATTERN = /^\d+(\.\d{1,6})?$/;
const ALL_ZEROS_PATTERN = /^0*(\.0*)?$/;

export function remittanceSchema(t: Translator) {
  return z.object({
    amount: z
      .string()
      .regex(AMOUNT_PATTERN, t("finance.taxes.form.amountInvalid"))
      .refine((value) => !ALL_ZEROS_PATTERN.test(value), {
        message: t("finance.taxes.form.amountPositive"),
      }),
    basis: z.string().min(1, t("finance.taxes.form.basisRequired")),
    confirmation_ref: z.string().min(1, t("finance.taxes.form.confirmationRequired")),
    entry_date: z.string().min(1, t("finance.taxes.form.paidOnRequired")),
  });
}

// ── The dual-basis table (BR-LED-013's four columns) ──────────────────────

export function AuthorityTable(props: {
  report: RemittanceResponse;
  t: Translator;
  locale?: string;
  onRecord: (row: AuthorityRemittanceRow) => void;
}) {
  const { report, t } = props;
  const money = (amount: string) => (
    <MoneyCell amount={amount} currency={report.currency} locale={props.locale} />
  );
  const absentCollected = (
    <AbsentFigure label={t("finance.absent")} reason={t("finance.taxes.collectedUnavailable")} />
  );
  return (
    <Panel>
      <div className="fin-panel-head">
        <h3>{t("finance.taxes.byAuthority")}</h3>
      </div>
      {report.rows.length === 0 ? (
        <p className="fin-absent-reason" role="note">
          {t("finance.taxes.empty")}
        </p>
      ) : (
        <PlainTable>
          <thead>
            <tr>
              <th scope="col">{t("finance.taxes.col.authority")}</th>
              <th scope="col" className="fin-num">
                {t("finance.taxes.col.billed")}
              </th>
              {/* OQ-1190, PO 2026-08-31 — *"(a) Add a per-authority subtotal to
                  the bill and the finance screens"*. The SAME authority's debt
                  as the BILLS charged it, beside the books' own figure. */}
              <th scope="col" className="fin-num">
                {t("finance.taxes.col.billedFromBills")}
              </th>
              <th scope="col" className="fin-num">
                {t("finance.taxes.col.collected")}
              </th>
              <th scope="col" className="fin-num">
                {t("finance.taxes.col.remitted")}
              </th>
              <th scope="col" className="fin-num">
                {t("finance.taxes.col.outstanding")}
              </th>
              <th scope="col">{t("finance.taxes.col.basis")}</th>
              <th scope="col">{t("finance.taxes.col.action")}</th>
            </tr>
          </thead>
          <tbody>
            {report.rows.map((row) => (
              <tr key={row.account_id}>
                <td>
                  {/* BR-BIL-069 — the 2200-nn ACCOUNT is the authority's
                      identity in the books, and its name is the one the tenant
                      typed when they minted it. The name rating knows is a
                      dimension no journal line carries.

                      ⚠ OQ-1190 — IT CAN NOW BE NAMED, and it is named FROM THE
                      BILLS rather than from the books: the bill's tax lines
                      carry `tax_id`, and billing resolves *"Bexar County Tax
                      Office"* where the account says *"Tax payable — Local ·
                      Bexar County"*. `GAP_TAX_AUTHORITY_NAME` is still open —
                      no journal line carries the dimension — so the account
                      stays on the row as the identity it has always been, and
                      the authority's own name sits above it. */}
                  {/* ⚠ DEF-LED-6706 — THIS CELL USED TO PRINT *Authority not
                      named* WITH THE AUTHORITY'S NAME ON THE LINE UNDERNEATH
                      IT. The absent state was written for the RATING-side name
                      and was reached whenever no bill in the window charged
                      this authority, which is most windows. It was never an
                      absence: BR-BIL-069 (PO 2026-08-11) rules that the 2200-nn
                      account IS the authority's identity in the books, and
                      `row.name` is the name the tenant typed when they minted
                      it. So the books' own name is the fallback, and the note
                      under it says which of the two names is on the row. */}
                  <span data-fin="authority-name">
                    {row.authority_name ?? row.name}
                  </span>
                  <span className="fin-absent-reason">
                    {row.authority_name === null ? row.code : `${row.code} · ${row.name}`}
                  </span>
                </td>
                <td className="fin-num">{money(row.billed)}</td>
                {/* OQ-1190 — the bills' own per-authority subtotal. Σ of the
                    ROUNDED tax lines (B4.4), computed by billing over exactly
                    the bills the books counted for this account, so the figure
                    here and the figure on the bill's Charges tab are one
                    derivation and cannot disagree.

                    ⚠ ABSENT IS ABSENT, NEVER ZERO. On a screen a return is
                    filed from, `0.00` reads as *"this authority is owed
                    nothing"*; the reason is shown instead. */}
                <td className="fin-num" data-fin="billed-from-bills">
                  {row.billed_from_bills === null ? (
                    <AbsentFigure
                      label={t("finance.absent")}
                      reason={t("finance.taxes.billedFromBillsUnavailable")}
                    />
                  ) : (
                    <>
                      {money(row.billed_from_bills)}
                      {/* STATED, never reconciled — `_charges_by_service`'s
                          posture on the bill, for its reason: a screen that
                          balanced the books would destroy the evidence. */}
                      <span
                        className="fin-absent-reason"
                        role="note"
                        data-fin="bills-vs-books"
                        data-agrees={String(row.bills_agree)}
                      >
                        {row.bills_agree === true
                          ? t("finance.taxes.billsAgree")
                          : t("finance.taxes.billsDiffer", {
                              bills: formatMoney(row.billed_from_bills, report.currency),
                              books: formatMoney(row.billed, report.currency),
                            })}
                      </span>
                    </>
                  )}
                </td>
                <td className="fin-num">
                  {row.collected === null ? absentCollected : money(row.collected)}
                </td>
                <td className="fin-num">{money(row.remitted)}</td>
                {/* OUTSTANDING IS GIVEN PER BASIS AND NEVER AS ONE NUMBER.
                    LE-3 has State on COLLECTED while County is on BILLED, so a
                    single "outstanding" would be wrong for one of them in the
                    first month it ran. */}
                <td className="fin-num">
                  {row.outstanding_billed === null
                    ? absentCollected
                    : money(row.outstanding_billed)}
                </td>
                <td>
                  {row.remitting_basis === null ? (
                    <AbsentFigure
                      label={t("finance.absent")}
                      reason={t("finance.taxes.basisNotSet")}
                    />
                  ) : (
                    t(`finance.taxes.basis.${row.remitting_basis}`, {
                      defaultValue: row.remitting_basis,
                    })
                  )}
                </td>
                <td>
                  <InlineLink
 type="button"
 onClick={() => props.onRecord(row)}
                  >
                    {t("finance.taxes.record")}
                  </InlineLink>
                </td>
              </tr>
            ))}
          </tbody>
          <tfoot>
            <tr className="fin-total-row">
              <td>{t("finance.taxes.total")}</td>
              <td className="fin-num">
                {/* BR-REP-001 — the BILLED total is on the POSTING basis and
                    the response names it per column, not once for the table:
                    billed is posting and collected is clearing, so one basis
                    label over both would be wrong about one of them. */}
                <MoneyCell
                  amount={report.totals.billed}
                  currency={report.currency}
                  basis={report.basis.billed}
                  locale={props.locale}
                />
              </td>
              {/* OQ-1190 — served ONLY when every row carried a figure. A
                  partial sum under a column heading reads as the whole and is
                  not, and a return would be filed from it. */}
              <td className="fin-num">
                {report.totals.billed_from_bills === null ? (
                  <AbsentFigure
                    label={t("finance.absent")}
                    reason={t("finance.taxes.billedFromBillsUnavailable")}
                  />
                ) : (
                  money(report.totals.billed_from_bills)
                )}
              </td>
              {/* ⚠ DEF-LED-6722 — THIS CELL WAS LITERALLY `{absentCollected}`,
                  unconditional, while every row above it drew a figure. It is
                  hard-won law 2's mirror: a REFUSAL that outlived the reason
                  for it. `CR-060` C19 / task T7d made the collected basis a
                  number on 2026-09-02 and changed the ROWS; the footer kept its
                  refusal, so *All authorities* said *Not available* under a
                  column of real money. `totals.collected` is null only when the
                  read genuinely cannot say (some row's figure is absent), and
                  that is the only case the refusal now covers. */}
              <td className="fin-num">
                {report.totals.collected === null
                  ? absentCollected
                  : money(report.totals.collected)}
              </td>
              <td className="fin-num">{money(report.totals.remitted)}</td>
              <td className="fin-num">
                {report.totals.outstanding_billed === null
                  ? absentCollected
                  : money(report.totals.outstanding_billed)}
              </td>
              <td colSpan={2} />
            </tr>
          </tfoot>
        </PlainTable>
      )}
    </Panel>
  );
}

// ── The screen ────────────────────────────────────────────────────────────

export interface RemittancePageProps extends RegionalProps {
  client?: ApiClient; // test seam
  locale?: string;
}

export function RemittancePage(props: RemittancePageProps) {
  const { t } = useTranslation();
  const translate: Translator = (key, params) => t(key, params);
  const client = props.client ?? api;
  const navigate = useNavigate();
  const tenantPath = useTenantPath();
  const routeParams = useParams();
  const queryClient = useQueryClient();
  const toast = useToast();
  const { timeZone, dateFormat } = useRegional(props);
  const cell = useAccessCell(FINANCE_PERMISSION, client);
  const { period, loading } = useFinancePeriod(client);

  const [target, setTarget] = useState<AuthorityRemittanceRow | null>(null);
  const [draft, setDraft] = useState<RemittanceDraft>(EMPTY_DRAFT);

  const windowKey = period === null ? "" : `${period.start}|${period.end}`;
  const reportQuery = useQuery({
    queryKey: remittanceQueryKey(windowKey),
    queryFn: () =>
      getRemittanceByAuthority({ from: period?.start ?? "", to: period?.end ?? "" }, client),
    retry: false,
    enabled: period !== null,
  });

  // `P4.11` — what you have already PAID, which no screen could show before
  // today. It is a SEPARATE read from the owed table above and it is NOT
  // windowed by the open period: a filing history that showed only this month
  // would answer *"did we pay Bexar County in August?"* with silence in
  // September, which is the question the panel exists for.
  const paidQuery = useQuery({
    queryKey: ["finance", "taxes", "paid"],
    queryFn: () => getRemittancesPaid({}, client),
    retry: false,
  });

  // P4.5 — `apps/ledger/finance_exports.py` registers `remittance`. The
  // filters are the screen's OWN window, so the file and the table on screen
  // cannot show different months.
  const exportRequest = useMutation({
    mutationFn: () =>
      requestListExport(
        {
          resource: "remittance",
          filters: period === null ? {} : { from: period.start, to: period.end },
        },
        // ⚠ THE PAGE'S CLIENT. `requestListExport` defaults to the module-level
        // `api`, so omitting this reaches the real network from inside a test
        // and from any screen mounted against a seam.
        client,
      ),
    onSuccess: () => toast(t("reports.export.queued")),
  });

  if (isDenied(cell)) {
    return (
      <PermissionDenied
        helper={t("finance.denied")}
        onBack={() => navigate(tenantPath("/dashboard"))}
      />
    );
  }
  if (reportQuery.isError && isPermissionDenied(reportQuery.error)) {
    return (
      <PermissionDenied
        helper={t("finance.denied")}
        onBack={() => navigate(tenantPath("/dashboard"))}
      />
    );
  }

  const report = reportQuery.data;
  const failed = reportQuery.isError && report === undefined;
  const routeAbsent = failed && remittanceRouteAbsent(reportQuery.error);

  async function handleSubmit(): Promise<FormSubmitOutcome> {
    if (target === null || period === null) {
      return { ok: false, error: { code: "", message_key: "api.error.unexpected" } };
    }
    try {
      await recordRemittance(
        {
          tax_account_id: target.account_id,
          from: period.start,
          to: period.end,
          amount: draft.amount,
          basis: draft.basis === "collected" ? "collected" : "billed",
          confirmation_ref: draft.confirmationRef,
          entry_date: draft.paidOn,
          // BR-TEN-043 — the caller states the moment. The date the clerk typed
          // is the business fact; the server anchors a bare date to UTC, and
          // OQ-153 (raised by the payments lane, unanswered) owns which instant
          // a user-entered calendar date should become in whose timezone.
          posted_at: draft.paidOn,
        },
        client,
        // `P4.3` — a file makes the request multipart and nothing else
        // changes. `null` sends byte-for-byte what this screen sent before.
        draft.receipt,
      );
      setTarget(null);
      setDraft(EMPTY_DRAFT);
      toast(t("finance.taxes.recorded"));
      await queryClient.invalidateQueries({ queryKey: remittanceQueryKey(windowKey) });
      // ⚠ **AND THE FILING HISTORY.** The payment a clerk just recorded is the
      // row the panel below exists to show; leaving it stale would mean the
      // screen that took the payment is the one screen that does not show it.
      await queryClient.invalidateQueries({ queryKey: ["finance", "taxes", "paid"] });
      return { ok: true };
    } catch (error) {
      // BR-SHL-020: the server's refusal is SHOWN, never swallowed. A remittance
      // that silently failed would leave a clerk believing a return was filed.
      if (isApiError(error)) {
        return { ok: false, error: formErrorEnvelope(error) };
      }
      return { ok: false, error: { code: "", message_key: "api.error.unexpected" } };
    }
  }

  return (
    <div className="fin-page">
      <FinanceHeader
        activeTab={financeTabFrom(routeParams.tab ?? FINANCE_TAB_TAXES)}
        explainer={t("finance.explainer.taxes")}
        period={period}
        t={translate}
        timeZone={timeZone}
        dateFormat={dateFormat}
        actions={
          /* THE S41 "↓ Remittance report", WORKING (`P4.5`).

             ⚠ **THIS CONTROL WAS DISABLED WITH A REASON, AND THE REASON MOVED
             TWICE BEFORE THE CONTROL DID.** It first said the download *"needs
             the report export service, which is not running on this
             deployment"* — false; the kernel had been writing report files
             since August. `P2.5` corrected it on the MORNING of 2026-09-24 to
             name the real gap, a missing REGISTRATION. `P4.1` registered it
             that afternoon (`apps/ledger/finance_exports.py`), so the
             corrected sentence became false in turn and is now DELETED rather
             than shortened — B14 rule 33 puts rationale at zero words on
             screen, and a working download needs nothing beside it.

             ⚠ **THE FILE NAMES NO BASIS, AND THAT IS `BR-REP-001` HONOURED
             RATHER THAN SKIPPED.** `BR-LED-013` lets each authority remit on
             its own basis — LE-3 has State on collected and County on billed
             in the same month — so a file stamped with either label would be
             false about half its own rows. The `{basis}` filename segment
             reads `per-authority` and every row carries its own
             `remitting_basis` column. */
          <DownloadButton
            disabled={period === null || report === undefined}
            onDownload={() => exportRequest.mutate()}
          />
        }
      />
      <FinanceBody period={period} loading={loading} t={translate}>
        {routeAbsent ? (
          <ArrivesWith
            title={t("finance.awaits.endpointTitle")}
            message={t("finance.awaits.endpoint")}
          />
        ) : failed ? (
          <Panel role="alert">
            <h3>{t("finance.error.title")}</h3>
            <p className="fin-absent-reason">{apiErrorText(reportQuery.error, translate)}</p>
          </Panel>
        ) : report === undefined ? (
          <LoadingSkeleton variant="table" />
        ) : (
          <>
            <AuthorityTable
              report={report}
              t={translate}
              locale={props.locale}
              onRecord={(row) => {
                setTarget(row);
                setDraft(EMPTY_DRAFT);
              }}
            />
            <Panel>
              <div className="fin-panel-head">
                <h3>{t("finance.taxes.tieOutTitle")}</h3>
              </div>
              <FactRow
                label={t("finance.taxes.tieOut")}
                value={
                  report.tie_out.tax_payable_gl === null ? (
                    <AbsentFigure
                      label={t("finance.absent")}
                      reason={t("finance.taxes.tieOutUnavailable")}
                    />
                  ) : (
                    <MoneyCell
                      amount={report.tie_out.tax_payable_gl}
                      currency={report.currency}
                      basis={report.basis.billed}
                      locale={props.locale}
                    />
                  )
                }
                strong
              />
            </Panel>
            {/* Every gap the read model named, listed rather than dropped — a
                new refusal from the server appears here on its own instead of
                being silently ignored by a screen that does not know it. */}
            {report.unavailable.map((gap) => (
              <p key={gap.code} className="fin-absent-reason" role="note">
                {gapSentence(gap, translate)}
              </p>
            ))}
            {/* ⚠ **AN `ArrivesWith` PANEL STOOD HERE UNTIL 2026-09-24 AND IS
                DELETED, NOT REWORDED (`P4.11`/`P4.4`).** It read *"Filing
                history arrives with the remittance register"* — a promise about
                a table that did not exist. It exists, so the promise is
                replaced by the thing it promised (hard-won law 2's mirror: a
                refusal that has stopped being true is worse than one that never
                was), and both its keys are retired from all eleven catalogues
                in the same commit. */}
            {paidQuery.data !== undefined && (
              <PaymentsMadePanel
                history={paidQuery.data}
                t={translate}
                locale={props.locale}
                tenantPath={tenantPath}
                loading={paidQuery.isLoading}
              />
            )}
          </>
        )}
      </FinanceBody>
      {target !== null && (
        <FormModal
          title={t("finance.taxes.recordTitle", { authority: target.name })}
          kicker={t("finance.taxes.recordKicker", { code: target.code })}
          schema={remittanceSchema(translate)}
          values={{
            amount: draft.amount,
            basis: draft.basis,
            confirmation_ref: draft.confirmationRef,
            entry_date: draft.paidOn,
          }}
          submitLabel={t("finance.taxes.recordSubmit")}
          onSubmit={handleSubmit}
          onClose={() => setTarget(null)}
        >
          <p className="fin-absent-reason">{t("finance.taxes.recordHelp")}</p>
          <TextField
            id="amount"
            label={t("finance.taxes.form.amount")}
            value={draft.amount}
            onChange={(value) => setDraft({ ...draft, amount: value })}
            numeric
            required
            help={t("finance.taxes.form.amountHelp")}
          />
          <SelectField
            id="basis"
            label={t("finance.taxes.form.basis")}
            value={draft.basis}
            onChange={(value) => setDraft({ ...draft, basis: value })}
            required
            placeholder={t("finance.taxes.form.basisPlaceholder")}
            help={t("finance.taxes.form.basisHelp")}
            options={[
              { value: "billed", label: t("finance.taxes.basis.billed") },
              { value: "collected", label: t("finance.taxes.basis.collected") },
            ]}
          />
          <TextField
            id="confirmation_ref"
            label={t("finance.taxes.form.confirmation")}
            value={draft.confirmationRef}
            onChange={(value) => setDraft({ ...draft, confirmationRef: value })}
            required
            help={t("finance.taxes.form.confirmationHelp")}
          />
          <TextField
            id="entry_date"
            label={t("finance.taxes.form.paidOn")}
            value={draft.paidOn}
            onChange={(value) => setDraft({ ...draft, paidOn: value })}
            required
            placeholder={t("finance.taxes.form.paidOnPlaceholder")}
          />
          {/* ⚠ **`finance.taxes.form.receiptUnavailable` STOOD HERE UNTIL
              2026-09-24 AND IS DELETED, NOT REWORDED (`P4.3`).** It read *"a
              receipt file cannot be kept yet, so it is refused rather than
              accepted and lost"* — true while `tax_remittances` was not in the
              schema, and the drawn field on p060 is what replaces it.
              `ledger/0020` builds the register and `tenancy/0052` makes
              `tax_remittance` a document source, so the file is KEPT: seven
              years, write-once, against the filing it proves. B14 rule 33
              removes a refusal rather than shortening it, and its key is
              retired from all eleven catalogues in the same commit. */}
          <FileField
            id="receipt"
            label={t("finance.taxes.form.receipt")}
            accept=".pdf,.png,.jpg,.jpeg,.csv"
            fileName={draft.receipt?.name ?? null}
            onChange={(file) => setDraft({ ...draft, receipt: file })}
            help={t("finance.taxes.form.receiptHelp")}
          />
        </FormModal>
      )}
    </div>
  );
}

export default RemittancePage;

// ── Lifecycle ─────────────────────────────────────────────
// packet: US-LED-014@7e1e359 (sources: 04-docs/05-modules/09-ledger/06-epics/EP-LED-05-remittance-close-export.md US-LED-014 §1-§8 · 09-ledger/02-business-rules.md BR-LED-002/007/013/019 · 09-ledger/08-worked-examples.md LE-3 · 04-docs/01-spec/11b-api-audit.md §1 · 05-prototype/UtilityBilling.html lines 3832-3878 · 12-governance/10-defect-log.csv DEF-112)
// generated: 2026-08-15 by story-coder (DEF-112 lane — `GET /finance/taxes` was SERVED on 2026-08-11 with no screen)
// checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-09)
// gates: RED PROVED FIRST — `src/features/ledger/remittance.test.tsx` failed to resolve `./RemittancePage` before this file existed; verbatim in the lane report. tsc✔ · eslint --max-warnings 0✔ · vitest✔ · vite build✔ · run_gates✔
// exceptions: (1) ⚠ **AMENDED 2026-09-02 (CR-060 C19 / task T7d) — THE COLLECTED COLUMN DRAWS A FIGURE NOW AND NO CODE IN THIS FILE CHANGED.** This read *the COLLECTED column and the collected-basis OUTSTANDING render ABSENT WITH THEIR REASON on every row and in the footer — an `allocations` row carries no line class (OQ-129)*; `allocation_classes` records what a payment met, so the backend answers and the cell's existing `collected === null ? absent : money(...)` draws it. **The absent state remains** and now means the payments read is unpublished, never that the billed figure may be substituted — which would still remit tax on money nobody paid. **The figure is a FLOOR** while any allocated money carries no breakdown, and the response says how much · (2) the prototype's four KPI tiles, its "Coming up" banner and its Tax type / Rate / Taxable base / Filing period / Due / Status columns are NOT drawn: each needs a filing due date or a rating dimension the ledger read model does not publish, and `tax_remittances` (B2 r13 #3) is not in the schema · (3) NO filing-history table and NO "Receipt ↓" — same missing table; the confirmation ref survives on the immutable entry memo and in audit_log, and the service REFUSES a receipt file by name rather than dropping it · (4) `remitting_basis` renders ABSENT per authority until the tenant sets it on Settings → Configure (BR-LED-014); nothing defaults it, because LE-3 files State on COLLECTED and County on BILLED in the same month · (5) "↓ Remittance report" renders DISABLED with its reason (BR-SHL-025) — the IS-11 download needs `POST /reports/{key}/export`, served by nothing · (6) the amount is TYPED, never pre-filled from the outstanding figure: a pre-filled amount makes the payment agree with the report by construction, which is the property that hides a wrong report
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
