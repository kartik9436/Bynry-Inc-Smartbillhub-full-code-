// ── Trace ──────────────────────────────────────────────
// Story:    US-LED-009 (S59 Account ledger report — Account · From · To →
//           dated rows with the FULL source vocabulary, a running balance and a
//           period-totals footer)
//           Screens: S59 (Reports → Account ledger; also the "Download ledger"
//           intent from S21 Account detail, A1 r2)
// Rules:    BR-LED-010 (account + date range → dated charges/payments +
//           running balance → PDF/CSV) · BR-REP-001 (posting-basis label on the
//           header) · BR-REP-002 (the rows are the account's journal-dimension
//           read model, never a parallel query) · BR-REP-008 (Type carries the
//           FULL source vocabulary so the report foots to the AR tie-out) ·
//           BR-REP-018 (downloads per IS-11) · BR-SHL-011 (the URL grammar) ·
//           BR-SHL-012 (the A18 shared states) · BR-SHL-020 (plain-language
//           failure) · BR-SHL-023 (one money formatting path) · BR-SHL-025 (a
//           control this deployment cannot honour renders disabled WITH its
//           reason) · BR-SHL-044 (one page header)
// ───────────────────────────────────────────────────────
// S59 — the account ledger. `apps/ledger/reporting.account_ledger` opens
// ACC-1042 at 45.00, bills it to 292.87 and pays it to 0.00; the four closings
// of the fixture sum to the 152.32 AR control to the cent. None of it was
// visible to anybody.
//
// **THE RUNNING BALANCE IS THE SERVER'S, EVERY ROW.** US-LED-009 §7 states the
// formula (`r_n = r_{n−1} + charge_n − payment_n`) and the read model executes
// it; this screen renders `row.running_balance` and never accumulates one in the
// browser. That is not fussiness — a client-side running balance is a second
// derivation of the same money, and the first time the two disagree a clerk has
// to decide which screen is lying (BR-REP-002).
//
// WHAT THE PROTOTYPE DRAWS HERE AND THIS SCREEN DOES NOT, each said on screen:
//
//   · **No Premises parameter.** The prototype's parameter bar has one and
//     US-LED-009 §8 rules it out by name: `premises_id` is NULL on every journal
//     line (US-LED-002 unbuilt), so a premises picker would accept a choice and
//     change nothing — a report that LOOKS filtered, which is worse than one
//     that is not.
//   · **The Reference column shows a UUID, not `BL-2607-018204`.** A journal
//     line carries the invoice's id; turning it into a document number is a
//     per-source-type read neither billing nor payments publishes. Shown with
//     the reason rather than blanked — a blank Reference is the column failing
//     silently.
//   · **Downloads are disabled with their reason** (`POST /reports/{key}/export`
//     is contracted and served by nothing).
//   · **No Favorite / Schedule / Print.** US-REP-012 owns favourites, US-REP-004
//     schedules, and printing is the PDF that does not exist yet.
//
// AND ONE THING THE PROTOTYPE GETS RIGHT THAT THIS SCREEN CANNOT YET: its
// Account field reads `A-10432 · Miller, Sarah`. This one takes an account id,
// because the report endpoint keys on `account_id` and no picker endpoint is
// wired into this screen; the S17 account list is where a clerk copies one from.
// Reported, not mimed.
import { useQuery } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import { useNavigate, useSearchParams } from "react-router-dom";

import { api, isApiError } from "@/api/client";
import type { ApiClient } from "@/api/client";
import { getAccountLedgerReport } from "@/api/endpoints";
import type { AccountLedgerResponse, AccountLedgerRow } from "@/api/endpoints";
import { DateCell } from "@/components/DateCell";
import type { RegionalDateFormat } from "@/components/DateCell";
import { MoneyCell } from "@/components/MoneyCell";
import { PageHeader } from "@/components/PageHeader";
import { Panel } from "@/components/Panel";
import { InlineLinkTo, PlainTable } from "@/components/Surfaces";
import { journalSourcePath } from "@/features/ledger/JournalEntryDetail";
import { LoadingSkeleton, PermissionDenied } from "@/components/StateFrame";
import {
  Dash,
  isDenied,
  useRegional,
  useAccessCell,
} from "@/features/metering/meteringShared";
import type { RegionalProps } from "@/features/metering/meteringShared";
import { ArrivesWith, apiErrorText, isPermissionDenied } from "@/features/tenancy/settingsShared";
import type { Translator } from "@/features/tenancy/settingsShared";
import { REPORTS_PERMISSION, gapSentence, isZeroAmount } from "@/features/ledger/financeShared";
import { useTenantPath } from "@/routing/tenantPath";

import {
  ReportDownloads,
  ReportGapList,
  ReportParamBar,
  sourceTypeLabel,
} from "./reportsShared";

import "@/features/ledger/finance.css";

export const accountLedgerQueryKey = (params: string) =>
  ["reports", "account-ledger", params] as const;

/** A read that answers 404 is not served here. DERIVED, never declared. */
export function reportRouteAbsent(error: unknown): boolean {
  return isApiError(error) && error.status === 404;
}

/** BR-SHL-011's `f.<name>` grammar, read off the screen's own URL so a report
 *  a user ran is a link they can send to their bookkeeper. */
export interface AccountLedgerParams {
  accountId: string;
  from: string;
  to: string;
}

export function accountLedgerParamsFrom(search: URLSearchParams): AccountLedgerParams {
  return {
    accountId: search.get("f.account_id") ?? "",
    from: search.get("f.from") ?? "",
    to: search.get("f.to") ?? "",
  };
}

export function accountLedgerSearchFrom(params: AccountLedgerParams): URLSearchParams {
  const search = new URLSearchParams();
  if (params.accountId !== "") {
    search.set("f.account_id", params.accountId);
  }
  if (params.from !== "") {
    search.set("f.from", params.from);
  }
  if (params.to !== "") {
    search.set("f.to", params.to);
  }
  return search;
}

/** Every parameter the report needs before it can be run at all. */
export function accountLedgerReady(params: AccountLedgerParams): boolean {
  return params.accountId !== "" && params.from !== "" && params.to !== "";
}

// ── The result table ──────────────────────────────────────────────────────

export function AccountLedgerTable(props: {
  report: AccountLedgerResponse;
  t: Translator;
  timeZone: string;
  dateFormat: RegionalDateFormat;
  locale?: string;
  /** Record links (PO 2026-10-19): a reference to a bill, payment or refund
   *  opens it. Absent, references stay text. */
  tenantPath?: (path: string) => string;
}) {
  const { report, t } = props;
  const money = (amount: string) => (
    <MoneyCell amount={amount} currency={report.currency} locale={props.locale} />
  );
  return (
    <PlainTable>
      <thead>
        <tr>
          <th scope="col">{t("reports.ledger.col.date")}</th>
          <th scope="col">{t("reports.ledger.col.type")}</th>
          <th scope="col">{t("reports.ledger.col.reference")}</th>
          <th scope="col">{t("reports.ledger.col.description")}</th>
          <th scope="col" className="fin-num">
            {t("reports.ledger.col.charge")}
          </th>
          <th scope="col" className="fin-num">
            {t("reports.ledger.col.payment")}
          </th>
          <th scope="col" className="fin-num">
            {t("reports.ledger.col.balance")}
          </th>
        </tr>
      </thead>
      <tbody>
        {/* The opening row is a REAL row, not a caption: it is the account's AR
            position at `start`, so a report that begins mid-history opens where
            the books left off rather than at zero (US-LED-009 TC-1's 45.00). */}
        <tr className="fin-opening-row">
          <td colSpan={4}>{t("reports.ledger.opening")}</td>
          <td className="fin-num" />
          <td className="fin-num" />
          <td className="fin-num">{money(report.opening_balance)}</td>
        </tr>
        {report.rows.map((row: AccountLedgerRow) => (
          <tr key={`${row.entry_id}|${row.source_id ?? ""}|${row.running_balance}`}>
            <td>
              <DateCell
                value={row.entry_date}
                timeZone={props.timeZone}
                dateFormat={props.dateFormat}
              />
            </td>
            <td className={row.type_mapped ? undefined : "fin-unmapped"}>
              {sourceTypeLabel(row.type, row.type_mapped, t)}
            </td>
            <td>
              {(() => {
                if (row.reference === null) {
                  return <Dash />;
                }
                const path =
                  props.tenantPath === undefined
                    ? null
                    : journalSourcePath(row.source_type, row.source_id);
                return path === null || props.tenantPath === undefined ? (
                  row.reference
                ) : (
                  <InlineLinkTo to={props.tenantPath(path)}>{row.reference}</InlineLinkTo>
                );
              })()}
            </td>
            <td>{row.description === null ? <Dash /> : row.description}</td>
            {/* charge/payment are the AR leg's two DIRECTIONS, never one signed
                amount — the same discipline `journal_lines.side` enforces, so a
                reader never has to work out what a minus sign meant. */}
            <td className="fin-num">{isZeroAmount(row.charge) ? <Dash /> : money(row.charge)}</td>
            <td className="fin-num">
              {isZeroAmount(row.payment) ? <Dash /> : money(row.payment)}
            </td>
            <td className="fin-num">{money(row.running_balance)}</td>
          </tr>
        ))}
      </tbody>
      <tfoot>
        <tr className="fin-total-row">
          <td colSpan={4}>{t("reports.ledger.totals")}</td>
          <td className="fin-num">{money(report.totals.charges)}</td>
          <td className="fin-num">{money(report.totals.payments)}</td>
          <td className="fin-num">
            <MoneyCell
              amount={report.totals.closing_balance}
              currency={report.currency}
              // BR-REP-001: the closing balance is the figure that must foot to
              // the AR tie-out, and it names its basis where it is read.
              basis={report.basis}
              locale={props.locale}
            />
          </td>
        </tr>
      </tfoot>
    </PlainTable>
  );
}

// ── The screen ────────────────────────────────────────────────────────────

export interface AccountLedgerReportPageProps extends RegionalProps {
  client?: ApiClient; // test seam
  locale?: string;
}

export function AccountLedgerReportPage(props: AccountLedgerReportPageProps) {
  const { t } = useTranslation();
  const translate: Translator = (key, params) => t(key, params);
  const client = props.client ?? api;
  const navigate = useNavigate();
  const tenantPath = useTenantPath();
  const [searchParams, setSearchParams] = useSearchParams();
  const { timeZone, dateFormat } = useRegional(props);

  const params = accountLedgerParamsFrom(searchParams);
  const ready = accountLedgerReady(params);
  const cell = useAccessCell(REPORTS_PERMISSION, client);

  const reportQuery = useQuery({
    queryKey: accountLedgerQueryKey(accountLedgerSearchFrom(params).toString()),
    queryFn: () =>
      getAccountLedgerReport(
        { account_id: params.accountId, from: params.from, to: params.to },
        client,
      ),
    retry: false,
    // A report with no parameters is not run. The prototype's viewer says the
    // same thing in its own generic state ("Set your parameters above and click
    // Run report") and this is that state with real parameters behind it.
    enabled: ready,
  });

  if (isDenied(cell)) {
    return (
      <PermissionDenied
        helper={t("reports.denied")}
        onBack={() => navigate(tenantPath("/dashboard"))}
      />
    );
  }
  if (reportQuery.isError && isPermissionDenied(reportQuery.error)) {
    return (
      <PermissionDenied
        helper={t("reports.denied")}
        onBack={() => navigate(tenantPath("/dashboard"))}
      />
    );
  }

  const report = reportQuery.data;
  const failed = reportQuery.isError && report === undefined;
  const routeAbsent = failed && reportRouteAbsent(reportQuery.error);

  function update(next: Partial<AccountLedgerParams>): void {
    setSearchParams(accountLedgerSearchFrom({ ...params, ...next }), { replace: true });
  }

  return (
    <div className="fin-page">
      <PageHeader
        kicker={t("reports.kicker")}
        title={t("reports.ledger.title")}
        backTo={{ to: tenantPath("/finance"), label: t("shell.nav.finance") }}
        rollup={
          report === undefined ? undefined : (
            <span className="fin-rollup">
              <span className="fin-rollup-item">
                {t("reports.rollup", {
                  from: report.period.start,
                  to: report.period.end,
                })}
              </span>
              <span className="fin-rollup-item">{t(`cells.basis.${report.basis}`)}</span>
            </span>
          )
        }
      />

      <ReportParamBar
        actions={
          // P4.5. The account AND the window travel, so the file is exactly
          // the run on screen — `ready` is the same guard the report itself
          // runs under.
          <ReportDownloads
            resource="account_ledger"
            client={client}
            filters={{
              account_id: params.accountId,
              from: params.from,
              to: params.to,
            }}
            disabled={!ready || report === undefined}
          />
        }
      >
        {/* A14 r2's parameter set MINUS the premises picker US-LED-009 §8 rules
            out by name. Every field is a URL parameter, so a run is a link. */}
        <div className="field">
          <label htmlFor="rep-account">{t("reports.param.account")}</label>
          <input
            id="rep-account"
            className="input"
            value={params.accountId}
            onChange={(event) => update({ accountId: event.target.value })}
          />
          <p className="field-help">{t("reports.param.accountHelp")}</p>
        </div>
        <div className="field">
          <label htmlFor="rep-from">{t("reports.param.from")}</label>
          <input
            id="rep-from"
            className="input"
            type="date"
            value={params.from}
            onChange={(event) => update({ from: event.target.value })}
          />
        </div>
        <div className="field">
          <label htmlFor="rep-to">{t("reports.param.to")}</label>
          <input
            id="rep-to"
            className="input"
            type="date"
            value={params.to}
            onChange={(event) => update({ to: event.target.value })}
          />
        </div>
        <p className="fin-params-note" role="note">
          {t("reports.ledger.noPremisesParam")}
        </p>
      </ReportParamBar>

      {!ready ? (
        <ArrivesWith
          title={t("reports.ledger.title")}
          message={t("reports.ledger.pickAccount")}
        />
      ) : routeAbsent ? (
        <ArrivesWith
          title={t("finance.awaits.endpointTitle")}
          message={t("finance.awaits.endpoint")}
        />
      ) : failed ? (
        <Panel role="alert">
          <h3>{t("finance.error.title")}</h3>
          {/* The server's own refusal, rendered from its message_key — a From
              later than a To answers `ledger.report.range_inverted` and this is
              where that sentence lands (BR-SHL-020). */}
          <p className="fin-absent-reason">{apiErrorText(reportQuery.error, translate)}</p>
        </Panel>
      ) : report === undefined ? (
        <LoadingSkeleton variant="table" />
      ) : (
        <>
          <AccountLedgerTable
            report={report}
            t={translate}
            timeZone={timeZone}
            dateFormat={dateFormat}
            locale={props.locale}
            tenantPath={tenantPath}
          />
          <ReportGapList
            gaps={report.unavailable}
            title={t("finance.gap.title")}
            render={(gap) => gapSentence(gap, translate)}
          />
        </>
      )}
    </div>
  );
}

export default AccountLedgerReportPage;

// ── Lifecycle ─────────────────────────────────────────────
// packet: US-LED-009@a1f04c9 (story+rules snapshot — EP-LED-03 US-LED-009; 09-ledger/02-business-rules.md BR-LED-010; 12-reports/02-business-rules.md BR-REP-001/002/008/018; 11b §1's `GET /reports/{key}` row; 05-prototype/UtilityBilling.html lines 4250-4275)
// generated: 2026-08-11 by story-coder (W5 finance SCREENS lane)
// checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-09)
// gates: RED PROVED FIRST — the test file failed to resolve `./AccountLedgerReportPage` before this file existed. tsc✔ · eslint --max-warnings 0✔ · vitest✔ · vite build✔ · run_gates✔
// exceptions: (1) NO premises parameter, by US-LED-009 §8's own ruling — `premises_id` is NULL on every journal line and a picker that changed nothing would make the report LOOK filtered · (2) the Reference column renders the source UUID the server sends, with the reason listed under the table; a blank cell is the column failing silently · (3) the Account parameter takes an ACCOUNT ID where the prototype shows "A-10432 · Miller, Sarah": the endpoint keys on the id and no picker read is wired into this screen · (4) downloads render DISABLED with their reason — `POST /reports/{key}/export` is contracted and served by nothing · (5) no Favorite / Schedule / Print header actions: US-REP-012 and US-REP-004 own the first two and the third is the PDF that does not exist · (6) the running balance is the SERVER's on every row; this screen accumulates nothing
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
