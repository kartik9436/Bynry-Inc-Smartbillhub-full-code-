// ── Trace ──────────────────────────────────────────────
// Story:    US-LED-010 (S60 By-premises summary — billed / collected / owed +
//           collection % per premises, KPI strip and all-premises footer)
//           Screens: S60 (Reports → By-premises summary)
// Rules:    BR-LED-011 (by-premises billed/collected/owed via the unit chain) ·
//           BR-MET-046 (units NEVER move between premises — the chain
//           guarantee is about the STAMP, not about a join) · BR-REP-001
//           (posting-basis label) · BR-REP-002 (read-model over journal-line
//           dimensions) · BR-REP-009 (collection %) · BR-REP-018 (downloads per
//           IS-11) · BR-SHL-012 (the A18 shared states) · BR-SHL-020
//           (plain-language failure) · BR-SHL-023 (one money formatting path) ·
//           BR-SHL-025 (a control this deployment cannot honour renders
//           disabled WITH its reason) · BR-SHL-044 (one page header)
// ───────────────────────────────────────────────────────
// S60 — the by-premises summary, and **today it renders a measured refusal**.
//
// `apps/ledger/reporting.by_premises_summary` answers `available: false`.
// Not because it is unfinished: because `premises_id` and `unit_id` are NULL on
// every journal line in this product. Nothing stamps either — billing's posting
// seam reports the gap on every bill, payments passes only source/account, and
// US-LED-002, the story that would resolve account → unit → premises AT POSTING
// TIME, is unbuilt.
//
// **THE SCREEN'S JOB IS TO RENDER THAT HONESTLY, AND IT IS A REAL JOB.** The read
// model considered three answers and called two of them defects — an empty table
// ("no activity this period" to the one person who most needs to know
// otherwise), and one row labelled *Unassigned* holding the whole book (it
// sorts, exports and reads like a premises, and is a finding disguised as data).
// It chose the third: `available=false` with the money it cannot attribute. A
// screen that took that response and drew an empty table would put the first
// defect back, in the last place anyone would look for it.
//
// So this screen shows **the amount at stake** — LE-6's own 553.69 billed and
// 446.37 collected — beside a sentence naming what is missing and the story that
// closes it. The refusal is quantified rather than adjectival.
//
// THE TABLE AND THE KPI STRIP ARE BUILT AND WIRED, and render the day
// `available` turns true. That is not speculative UI: the response's row shape
// is served today (as an empty array), the fixture figures are transcribed in
// the backend's own test file as `LE6_ROWS`, and the alternative — shipping the
// refusal alone — would leave the next lane to build a table over a read model
// that already returns its rows.
//
// WHAT THE PROTOTYPE DRAWS HERE AND THIS SCREEN DOES NOT:
//
//   · **No Service filter and no Group-by picker.** A14 r3 gives the report
//     both. Service needs the tenant's LIVE enabled set (BR-REP-006) and no
//     report endpoint serves one; Group-by "Premises → Unit" needs the unit
//     dimension that is the very thing missing. Two pickers that changed nothing
//     is the defect this screen exists to avoid, twice over.
//   · **No Period picker.** The period is the tenant's own, computed from fiscal
//     settings (BR-TEN-022) and served on `GET /shell/display` — the same one
//     S36 heads its page with, composed from the same selector, so the two
//     screens can never disagree about which month a figure belongs to. It read
//     `GET /settings/regional` until 2026-09-06 and that endpoint answers a
//     Billing Clerk 403, so this report never ran for the role A4 gives it
//     (`DEF-SHL-4283`).
//   · **Downloads render disabled with their reason.**
import { useQuery } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import { useNavigate } from "react-router-dom";

import { api } from "@/api/client";
import type { ApiClient } from "@/api/client";
import { getByPremisesReport, getShellDisplay } from "@/api/endpoints";
import type { ByPremisesResponse, ByPremisesRow, ShellDisplayPeriod } from "@/api/endpoints";
import { AbsentFigure } from "@/components/AbsentFigure";
import { KPIStrip } from "@/components/KPIStrip";
import type { KpiTile } from "@/components/KPIStrip";
import { MoneyCell } from "@/components/MoneyCell";
import { PageHeader } from "@/components/PageHeader";
import { Panel } from "@/components/Panel";
import { InlineLinkTo, PlainTable } from "@/components/Surfaces";
import { premisesDetailPath } from "@/features/metering/meteringShared";
import { LoadingSkeleton, PermissionDenied } from "@/components/StateFrame";
import { queryKeys } from "@/api/queryClient";
import { Dash, isDenied, useAccessCell } from "@/features/metering/meteringShared";
import { ArrivesWith, apiErrorText, isPermissionDenied } from "@/features/tenancy/settingsShared";
import type { Translator } from "@/features/tenancy/settingsShared";
import {
  FactRow,
  REPORTS_PERMISSION,
  gapSentence,
} from "@/features/ledger/financeShared";
import { reportRouteAbsent } from "./AccountLedgerReportPage";
import { ReportDownloads, ReportGapList, ReportParamBar } from "./reportsShared";
import { useTenantPath } from "@/routing/tenantPath";

import "@/features/ledger/finance.css";

export const byPremisesQueryKey = (period: string) => ["reports", "by-premises", period] as const;

/** `apps/ledger/reporting.py`'s own identifier for the missing dimension. */
export const GAP_PREMISES_DIMENSION = "premises_and_unit_dimensions_never_stamped";

// ── The KPI strip (A14 r3: premises count · billed · collected · owed) ────

export function byPremisesKpis(
  report: ByPremisesResponse,
  t: Translator,
  locale: string | undefined,
): KpiTile[] {
  const money = (amount: string) => ({
    amount,
    currency: report.currency,
    basis: report.basis,
    locale,
  });
  return [
    { id: "premises", label: t("reports.premises.col.premises"), value: report.kpis.premises },
    { id: "billed", label: t("reports.premises.col.billed"), money: money(report.kpis.billed) },
    {
      id: "collected",
      label: t("reports.premises.col.collected"),
      money: money(report.kpis.collected),
    },
    { id: "owed", label: t("reports.premises.col.owed"), money: money(report.kpis.owed) },
  ];
}

// ── The result table (renders when the dimension lands) ───────────────────

export function ByPremisesTable(props: {
  report: ByPremisesResponse;
  t: Translator;
  locale?: string;
  /** Record links (PO 2026-10-19): where a premises name opens. */
  premisesHref?: (premisesId: string) => string;
}) {
  const { report, t } = props;
  const money = (amount: string) => (
    <MoneyCell amount={amount} currency={report.currency} locale={props.locale} />
  );
  return (
    <PlainTable>
      <thead>
        <tr>
          <th scope="col">{t("reports.premises.col.premises")}</th>
          <th scope="col" className="fin-num">
            {t("reports.premises.col.units")}
          </th>
          <th scope="col">{t("reports.premises.col.services")}</th>
          <th scope="col" className="fin-num">
            {t("reports.premises.col.billed")}
          </th>
          <th scope="col" className="fin-num">
            {t("reports.premises.col.collected")}
          </th>
          <th scope="col" className="fin-num">
            {t("reports.premises.col.owed")}
          </th>
          <th scope="col" className="fin-num">
            {t("reports.premises.col.collectionPct")}
          </th>
        </tr>
      </thead>
      <tbody>
        {report.rows.map((row: ByPremisesRow) => (
          <tr key={row.premises_id}>
            <td>
              {props.premisesHref !== undefined ? (
                <InlineLinkTo to={props.premisesHref(row.premises_id)}>
                  {row.premises_name}
                </InlineLinkTo>
              ) : (
                row.premises_name
              )}
            </td>
            <td className="fin-num">{row.units === null ? <Dash /> : row.units}</td>
            <td>{row.services.length === 0 ? <Dash /> : row.services.join(" · ")}</td>
            <td className="fin-num">{money(row.billed)}</td>
            <td className="fin-num">{money(row.collected)}</td>
            <td className="fin-num">{money(row.owed)}</td>
            {/* BR-REP-009's percentage per premises has the same numerator
                problem as the S36 KPI: it needs which bill the cash met. A row
                whose percentage the server would not state shows the absence,
                never `collected ÷ billed` computed here. */}
            <td className="fin-num">
              {row.collection_pct === null ? (
                <Dash />
              ) : (
                t("finance.kpi.pctValue", { value: row.collection_pct })
              )}
            </td>
          </tr>
        ))}
      </tbody>
      <tfoot>
        <tr className="fin-total-row">
          <td>{t("reports.premises.total")}</td>
          <td className="fin-num" />
          <td />
          <td className="fin-num">
            <MoneyCell
              amount={report.kpis.billed}
              currency={report.currency}
              basis={report.basis}
              locale={props.locale}
            />
          </td>
          <td className="fin-num">{money(report.kpis.collected)}</td>
          <td className="fin-num">{money(report.kpis.owed)}</td>
          <td className="fin-num" />
        </tr>
      </tfoot>
    </PlainTable>
  );
}

// ── The measured refusal (what this screen actually renders today) ────────

export function UnattributedPanel(props: {
  report: ByPremisesResponse;
  t: Translator;
  locale?: string;
}) {
  const { report, t } = props;
  const gap = report.unavailable.find((row) => row.code === GAP_PREMISES_DIMENSION) ?? null;
  // BR-LED-011 is the rule this report implements (billed/collected/owed per
  // premises via the unit chain), and the server's own identifier for the gap is
  // `GAP_PREMISES_DIMENSION` above. NEITHER is interpolated into the sentence any
  // more: B14 rule 31 keeps a rule number off a utility user's screen, and this
  // comment is where the provenance lives now. The ids are still on the wire, in
  // the response fixture and here.
  const reason =
    gap === null
      ? t("finance.gap.unknown")
      : gapSentence(gap, t);
  return (
    <Panel className="fin-absent-panel">
      <div className="fin-panel-head">
        <h3>{t("reports.premises.unavailableTitle")}</h3>
      </div>
      <p className="fin-absent-reason" role="note">
        {reason}
      </p>
      {/* The refusal, QUANTIFIED. These two are the period's whole billed and
          collected totals — the same figures S36 shows in its KPI strip — and
          they are here so a finance officer reads "553.69 has no premises",
          not "the report is broken". */}
      <FactRow
        label={t("reports.premises.unattributedBilled")}
        value={
          <MoneyCell
            amount={report.unattributed_billed}
            currency={report.currency}
            basis={report.basis}
            locale={props.locale}
          />
        }
      />
      <FactRow
        label={t("reports.premises.unattributedCollected")}
        value={
          <MoneyCell
            amount={report.unattributed_collected}
            currency={report.currency}
            basis={report.basis}
            locale={props.locale}
          />
        }
      />
      <FactRow
        label={t("reports.premises.col.premises")}
        value={
          <AbsentFigure label={t("finance.absent")} reason={t("reports.premises.noRows")} />
        }
        strong
      />
    </Panel>
  );
}

// ── The screen ────────────────────────────────────────────────────────────

export interface ByPremisesReportPageProps {
  client?: ApiClient; // test seam
  locale?: string;
}

export function ByPremisesReportPage(props: ByPremisesReportPageProps) {
  const { t } = useTranslation();
  const translate: Translator = (key, params) => t(key, params);
  const client = props.client ?? api;
  const navigate = useNavigate();
  const tenantPath = useTenantPath();
  const cell = useAccessCell(REPORTS_PERMISSION, client);

  // The same served period S36 heads its page with (BR-TEN-022) — never a
  // calendar month computed here, so the two screens cannot disagree about
  // which month a figure belongs to. Both compose it from the SAME selector
  // (`tenancy.selectors.current_period`), so two endpoints cannot drift.
  //
  // ⚠ **IT READS `GET /shell/display`, AND UNTIL 2026-09-06 IT READ
  // `GET /settings/regional` AND THIS REPORT DID NOT RUN FOR A BILLING CLERK AT
  // ALL (`DEF-SHL-4283`).** A4's `reports` row gives a Billing Clerk **Run**, so
  // this screen is theirs; `GET /settings/regional` is
  // `SettingsReadAnyWriteSystemAdmin` — `{system_admin, executive}` — so it
  // answered them `403 AUTH-002`, `period` stayed null, and `enabled: period
  // !== null` below meant the report was never requested. What the clerk saw
  // instead was *"Set the fiscal year start to see the current period."* at a
  // tenant whose fiscal year start **is** set — a false sentence pointing at a
  // screen only a System Admin can open. That is `DEF-SHL-4272` surviving in a
  // narrower form: the shell's two boot reads were moved and this was not.
  const displayQuery = useQuery({
    queryKey: queryKeys.shellDisplay,
    queryFn: () => getShellDisplay(client),
    retry: false,
  });
  const period: ShellDisplayPeriod | null = displayQuery.data?.period ?? null;

  const reportQuery = useQuery({
    queryKey: byPremisesQueryKey(period === null ? "" : `${period.start}|${period.end}`),
    queryFn: () =>
      getByPremisesReport(period === null ? {} : { from: period.start, to: period.end }, client),
    retry: false,
    enabled: period !== null,
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

  return (
    <div className="fin-page">
      <PageHeader
        kicker={t("reports.kicker")}
        title={t("reports.premises.title")}
        backTo={{ to: tenantPath("/finance"), label: t("shell.nav.finance") }}
        rollup={
          report === undefined ? undefined : (
            <span className="fin-rollup">
              <span className="fin-rollup-item">
                {t("reports.rollup", { from: report.period.start, to: report.period.end })}
              </span>
              <span className="fin-rollup-item">{t(`cells.basis.${report.basis}`)}</span>
            </span>
          )
        }
      />

      <ReportParamBar
        actions={
          // P4.5 — this control was disabled with a reason until 2026-09-24.
          // The filters are the report's OWN window, so the file and the
          // screen cannot show different months.
          <ReportDownloads
            resource="by_premises"
            client={client}
            filters={period === null ? {} : { from: period.start, to: period.end }}
            disabled={period === null || report === undefined}
          />
        }
      >
        <p className="fin-params-note" role="note">
          {t("reports.premises.noParams")}
        </p>
      </ReportParamBar>

      {period === null ? (
        <ArrivesWith
          title={t("settings.regional.currentPeriod")}
          message={t("settings.regional.noPeriod")}
        />
      ) : routeAbsent ? (
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
      ) : report.available ? (
        <>
          <KPIStrip kpis={byPremisesKpis(report, translate, props.locale)} />
          <ByPremisesTable
            report={report}
            t={translate}
            locale={props.locale}
            premisesHref={(premisesId) => tenantPath(premisesDetailPath(premisesId))}
          />
          <ReportGapList
            gaps={report.unavailable}
            title={t("finance.gap.title")}
            render={(gap) => gapSentence(gap, translate)}
          />
        </>
      ) : (
        // NO KPI strip and NO table here, deliberately: `kpis` reads 0 / 0.00 on
        // an unavailable response, and four zeroed tiles over a book holding
        // 553.69 is the plausible-zero defect in its purest form.
        <>
          <UnattributedPanel report={report} t={translate} locale={props.locale} />
          <ReportGapList
            gaps={report.unavailable.filter((gap) => gap.code !== GAP_PREMISES_DIMENSION)}
            title={t("finance.gap.title")}
            render={(gap) => gapSentence(gap, translate)}
          />
        </>
      )}
    </div>
  );
}

export default ByPremisesReportPage;

// ── Lifecycle ─────────────────────────────────────────────
// packet: US-LED-010@a1f04c9 (story+rules snapshot — EP-LED-03 US-LED-010; 09-ledger/02-business-rules.md BR-LED-011; 04-metering/02-business-rules.md BR-MET-046; 12-reports/02-business-rules.md BR-REP-001/002/009/018; 11b §1's `GET /reports/{key}` row; 05-prototype/UtilityBilling.html lines 4220-4249)
// generated: 2026-08-11 by story-coder (W5 finance SCREENS lane)
// checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-09)
// gates: RED PROVED FIRST — the test file failed to resolve `./ByPremisesReportPage` before this file existed. tsc✔ · eslint --max-warnings 0✔ · vitest✔ · vite build✔ · run_gates✔
// exceptions: (1) THIS SCREEN RENDERS A REFUSAL TODAY, for every tenant: `premises_id` is NULL on every journal line in the product (US-LED-002 unbuilt) and `by_premises_summary` answers `available=false`. The KPI strip and the table are built and wired and render the day the dimension lands; on an unavailable response NEITHER is drawn, because `kpis` reads 0/0.00 there and four zeroed tiles over a book holding 553.69 is the plausible-zero defect · (2) NO Service filter and NO Group-by picker although A14 r3 gives the report both — Service needs the tenant's live enabled set, which no report endpoint serves, and "Premises → Unit" needs the unit dimension that is the missing thing · (3) NO period picker: the period is the tenant's served `current_period` (BR-TEN-022), the same one S36 uses, so the two screens cannot disagree · (4) downloads render DISABLED with their reason
// amended:   2026-09-01 by the finance-copy lane — B14 rule 31: the hardcoded `brRef: "BR-LED-011"` and the server `code` no longer reach the sentence this screen prints; both moved into the comment beside the call site. The refusal itself is untouched and still quantified: this panel is the screen's PRIMARY content when `available` is false, so it deliberately does NOT become a closed `<details>` — rule 32's disclosure is for an absence beside the work, and closing the only thing on the page would leave a blank screen (hard-won law 1). Its title and its sentence are inside the rule-33 budget instead.
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
