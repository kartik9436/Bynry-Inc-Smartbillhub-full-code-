// ── Trace ──────────────────────────────────────────────
// Story:    US-PAY-020 (S37 — the day × method batch list, the KPI strip, the
//           day-cut and the status filter) · US-PAY-022 (the S40 "Why doesn't
//           this match?" modal, opened from an unmatched row)
//           Screens: S37 · S40
// Rules:    BR-PAY-004 (a reconciled batch LOCKS — Resolve and Unreconcile are
//           mutually exclusive on a row) · BR-PAY-019 (bank rec in FINANCE,
//           Owner/Finance roles; every difference carries a reason AND a GL) ·
//           BR-PAY-025 (SUPERSEDED-IN-PART 2026-09-22: a TILL × a tender; the
//           day is still the POSTING day) ·
//           BR-PAY-035 ("Force match anyway" permanently SUPERSEDED) ·
//           BR-PAY-040 (a card day reconciles NET, fee as its own line) ·
//           BR-SHL-020 · BR-SHL-023 · BR-SHL-025 · BR-SHL-044 (one page header)
// ───────────────────────────────────────────────────────
// S37 "Deposits & Bank" — the Finance tab that has been telling people to come
// back later ever since the Finance screens shipped.
//
// ══════════════════════════════════════════════════════════════════════════
// WHAT WAS ACTUALLY BROKEN
// ══════════════════════════════════════════════════════════════════════════
// `/finance/deposits` is a RATIFIED sidebar child (BR-SHL-001) and the second
// tab of the Finance page. It resolved to `RevenueArPage`, which rendered an
// "arrives with …" panel — while `apps/payments/reconciliation.py` could cut a
// day's deposit batches, import a bank statement, auto-match it, explain a
// difference with a reason and a GL, reconcile, lock and unreconcile, under a
// full test suite. **A nav item that lands on a placeholder over a finished
// engine is hard-won law 2 at feature scale**, and the engine's own docstring
// said so in as many words.
//
// ══════════════════════════════════════════════════════════════════════════
// THE PROTOTYPE, AND THE FOUR PLACES THIS SCREEN LEAVES IT
// ══════════════════════════════════════════════════════════════════════════
// Layout, copy and column order are UtilityBilling.html:3802-3830 — the nine
// columns, the four KPI tiles, the "Needs your attention" card and the status
// segments. What differs, each reported rather than taken quietly:
//
//   · **The KPI tiles carry no hardcoded figures.** The prototype prints
//     "$298,410 · 31 batches"; those are a demo tenant's. Every tile here is
//     folded server-side over the SAME rows the table shows (US-PAY-020 TC-2).
//   · **"In transit" money is its own tile and its Bank-shows cell says
//     `pending`,** exactly as the design draws it — never $0.00. That is the
//     one thing this screen must not get wrong.
//   · **"↓ Deposit slip for bookkeeper" renders DISABLED with its reason**
//     (BR-SHL-025): IS-9's CSV rides the platform export pipeline and
//     `deposit_batches` is not a registered exportable resource.
//   · **"Cut today's deposits" is not "today".** BR-TEN-043 forbids the server
//     reading a clock, so the control offers the DAYS THAT ACTUALLY HAVE
//     unbatched cleared money and the clerk picks one. An empty list is the
//     honest "everything is banked", which a "today" button could never say.
//
// ══════════════════════════════════════════════════════════════════════════
// THE LIST IS THE SHARED `DataTable` SINCE 2026-09-24 — `P1.2` · `P1.4` · `P1.7`
// ══════════════════════════════════════════════════════════════════════════
// Finance blueprint p048–p049, read as IMAGES (B14 rule 42). The table, its
// toolbar, its chooser and its footer are `DepositsList` — a COMPONENT, per
// B14 rule 43 — and this file keeps what belongs to the PAGE: the header, the
// tiles, the day-cut and the request state.
//
// **The request state lives in the URL** (`P1.9`'s shape, `CR-060` C14), so a
// clerk who has narrowed to unmatched cheques can send a colleague the link and
// they see the same rows. It was `useState` before, which p048 note 2 records
// in one word: *"unlinkable, lost on refresh"*.
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { useNavigate, useSearchParams } from "react-router-dom";
import { z } from "zod";

import { api, formErrorEnvelope, isApiError } from "@/api/client";
import type { ApiClient } from "@/api/client";
import { cutDepositBatches, getDepositBatches } from "@/api/bankRecEndpoints";
import { requestListExport } from "@/api/endpoints";
import type { CuttableDay } from "@/api/bankRecEndpoints";
import { Button, ButtonLink } from "@/components/Button";
import { DownloadButton } from "@/components/DownloadButton";
import { FormModal, SelectField } from "@/components/FormModal";
import type { FormSubmitOutcome } from "@/components/FormModal";
import { KPIStrip } from "@/components/KPIStrip";
import { formatMoney } from "@/components/MoneyCell";
import { LoadingSkeleton, PermissionDenied } from "@/components/StateFrame";
import { parseTableParams, serializeTableParams } from "@/components/tableTypes";
import type { TableRequestState } from "@/components/tableTypes";
import { useToast } from "@/components/Toast";
import { InlineLinkTo } from "@/components/Surfaces";
import { Kicker } from "@/components/TextBits";
import { Panel } from "@/components/Panel";
import { FinanceHeader, useFinancePeriod } from "@/features/ledger/financeChrome";
import { FINANCE_TAB_DEPOSITS } from "@/features/ledger/financeShared";
import { isDenied, useRegional, useAccessCell } from "@/features/metering/meteringShared";
import type { RegionalProps } from "@/features/metering/meteringShared";
import { ArrivesWith, apiErrorText, isPermissionDenied } from "@/features/tenancy/settingsShared";
import type { Translator } from "@/features/tenancy/settingsShared";
import { useTenantPath } from "@/routing/tenantPath";

import { DepositsList, depositsConfig } from "./DepositsList";
import {
  BANKREC_PERMISSION,
  DEPOSITS_IMPORT_ROUTE,
  DEPOSITS_STATEMENT_ROUTE,
  GapNotes,
  StillOpenCounterNote,
  bankRecRouteAbsent,
  depositBatchRoute,
} from "./depositsShared";

import "./payments.css";

/**
 * The list's cache key.
 *
 * ⚠ **EVERY PART OF THE REQUEST IS IN IT, AND LEAVING ONE OUT IS THE DEFECT
 * `GeneralLedgerPage` RECORDS ONE MODULE OVER.** react-query caches by key: a
 * term the key does not mention changes the request and not the cached answer,
 * so the control would move, the network would carry `q`, and the table would
 * go on showing the unsearched page — a filter that looks applied and is not,
 * which is worse than no filter at all.
 */
export const depositBatchesQueryKey = (state: {
  q: string;
  sort: string;
  dir: string;
  page: number;
  per: number;
  status: string;
  method: string;
}) =>
  [
    "payments",
    "deposit-batches",
    state.q,
    state.sort,
    state.dir,
    state.page,
    state.per,
    state.status,
    state.method,
  ] as const;

// ⚠ **`DEPOSIT_FILTERS` STOOD HERE UNTIL 2026-09-24 AND IS DELETED, NOT MOVED
// (`P1.4` · `DEF-PAY-6556`).** It listed the four batch statuses as literals
// with an "all" in front, so a fifth status added server-side was served,
// filterable and invisible: the row exists, the API answers `f.status` for it,
// `tsc` and every test pass, and no chip appears. That is hard-won law 2's
// silent shape, the one `SignupWizard.tsx`'s tick-list taught this repo.
// `GET /deposit-batches` now serves `statuses` and `methods`, and
// `DepositsList` renders what it is handed.

// ── The screen ────────────────────────────────────────────────────────────

export interface DepositsPageProps extends RegionalProps {
  client?: ApiClient; // test seam
  locale?: string;
}

export function DepositsPage(props: DepositsPageProps) {
  const { t } = useTranslation();
  const translate: Translator = (key, params) => t(key, params);
  const client = props.client ?? api;
  const navigate = useNavigate();
  const tenantPath = useTenantPath();
  const queryClient = useQueryClient();
  const toast = useToast();
  const { timeZone, dateFormat } = useRegional(props);
  const cell = useAccessCell(BANKREC_PERMISSION, client);
  // The Finance frame always shows the tenant's accounting period, so this tab
  // reads it for the HEADER only. Deposit batches are not period-scoped — a
  // batch belongs to its drawer day (BR-PAY-025) — so, unlike the other four
  // Finance tabs, the body is NOT gated on a period being configured: a utility
  // with no fiscal calendar must still be able to reconcile its bank.
  const { period } = useFinancePeriod(client);

  const [cutDay, setCutDay] = useState<string>("");
  const [cutOpen, setCutOpen] = useState(false);

  // `P1.9`'s shape — the whole request in the query string, so a narrowed list
  // is a link a clerk can send. The config used for PARSING is built with no
  // served chips, and that is safe for the reason `RefundsPage` records:
  // `parseTableParams`/`serializeTableParams` walk `filters[].name` and never
  // read `options`, so a config built before the first response round-trips
  // `f.status` and `f.method` identically to the one the list renders from.
  // Building it from the response instead would mean the URL could not be
  // serialised until the response landed, which is the wrong way round — the
  // URL is what ASKS for the response.
  const [searchParams, setSearchParams] = useSearchParams();
  const paramsConfig = depositsConfig(translate, props.locale, { statuses: [], methods: [] });
  const tableState = parseTableParams(searchParams, paramsConfig);
  function setTableState(next: TableRequestState): void {
    setSearchParams(serializeTableParams(next, paramsConfig), { replace: true });
  }

  const batchesQuery = useQuery({
    queryKey: depositBatchesQueryKey({
      q: tableState.q,
      sort: tableState.sort,
      dir: tableState.dir,
      page: tableState.page,
      per: tableState.per,
      status: tableState.filters.status ?? "",
      method: tableState.filters.method ?? "",
    }),
    queryFn: () =>
      getDepositBatches(
        {
          status: tableState.filters.status,
          method: tableState.filters.method,
          q: tableState.q,
          sort: tableState.sort,
          dir: tableState.dir,
          page: tableState.page,
          per: tableState.per,
        },
        client,
      ),
    retry: false,
  });

  const cutMutation = useMutation({
    mutationFn: (day: string) =>
      cutDepositBatches(
        {
          day,
          // BR-TEN-043 — the CALLER names the moment. The browser's clock is the
          // caller here, which is the one place a clock is legitimate: it is an
          // input the user is implicitly stating by pressing the button, and it
          // travels to the server rather than being read there (gate G6).
          occurred_at: new Date().toISOString(),
        },
        client,
      ),
  });

  // P4.6 — the deposit slip. `apps/payments/exports.py` registers `deposits`;
  // the list's OWN filter state travels, so the file is the list on screen
  // rather than an approximation of it re-derived under different defaults.
  const slipRequest = useMutation({
    mutationFn: () =>
      requestListExport(
        {
          resource: "deposits",
          filters: {
            ...(tableState.filters.status ? { status: tableState.filters.status } : {}),
            ...(tableState.filters.method ? { method: tableState.filters.method } : {}),
          },
        },
        // ⚠ THE PAGE'S CLIENT. `requestListExport` defaults to the module-level
        // `api`, so omitting it reaches the real network from inside a test.
        client,
      ),
    onSuccess: () => toast(t("reports.export.queued")),
  });

  if (isDenied(cell)) {
    return (
      <PermissionDenied
        helper={t("payments.deposits.denied")}
        onBack={() => navigate(tenantPath("/dashboard"))}
      />
    );
  }
  if (batchesQuery.isError && isPermissionDenied(batchesQuery.error)) {
    return (
      <PermissionDenied
        helper={t("payments.deposits.denied")}
        onBack={() => navigate(tenantPath("/dashboard"))}
      />
    );
  }

  const body = batchesQuery.data;
  const failed = batchesQuery.isError && body === undefined;
  const routeAbsent = failed && bankRecRouteAbsent(batchesQuery.error);
  const days: CuttableDay[] = body?.cuttable_days ?? [];

  async function handleCut(): Promise<FormSubmitOutcome> {
    try {
      const result = await cutMutation.mutateAsync(cutDay);
      setCutOpen(false);
      setCutDay("");
      toast(
        t("payments.deposits.cutDone", {
          batches: result.batches.length,
          payments: result.payments_batched,
        }),
      );
      // `DEF-PAY-10759` (L1-02 c) — what the cut LEFT OUT is said, one line
      // per reason, naming the payments. It used to close with no word while
      // all six of the tester's payments were skipped as `no_method`.
      for (const line of skippedLines(result.skipped ?? [], translate)) {
        toast(line);
      }
      await queryClient.invalidateQueries({ queryKey: ["payments", "deposit-batches"] });
      return { ok: true };
    } catch (error) {
      // BR-SHL-020 — the server's refusal is SHOWN. A cut that silently failed
      // would leave a clerk believing the day's takings were banked.
      if (isApiError(error)) {
        return { ok: false, error: formErrorEnvelope(error) };
      }
      return { ok: false, error: { code: "", message_key: "api.error.unexpected" } };
    }
  }

  return (
    <div className="fin-page">
      <FinanceHeader
        activeTab={FINANCE_TAB_DEPOSITS}
        explainer={t("payments.deposits.explainer")}
        period={period}
        t={translate}
        timeZone={timeZone}
        dateFormat={dateFormat}
        actions={
          <>
            <ButtonLink variant="secondary"  to={tenantPath(DEPOSITS_IMPORT_ROUTE)}>
              {t("payments.deposits.import")}
            </ButtonLink>
            {/* CR-059 W8 · P8 — the period tie-out. WIRED HERE, and that is the
                whole point of the task: the four reconciliation backends have
                been live and unreachable since 2026-09-01, and a screen no nav
                item reaches is the same defect one layer up (hard-won law 2). */}
            <ButtonLink variant="secondary" to={tenantPath(DEPOSITS_STATEMENT_ROUTE)}>
              {t("payments.deposits.statement.link")}
            </ButtonLink>
            {/* THE DEPOSIT SLIP, WORKING (`P4.6`).

                ⚠ **THIS WAS DISABLED WITH ITS REASON UNTIL 2026-09-24, AND THE
                REASON WAS TRUE.** It read *"the affordance exists and says why
                it cannot be used"* over `payments.deposits.slipUnavailable`,
                because no deposits export resource was registered anywhere.
                `apps/payments/exports.py` registers one now, so the sentence is
                DELETED rather than shortened — B14 rule 33 puts rationale at
                zero words on screen and a working download needs none. The
                server-side gap `no_deposit_slip_export` goes with it.

                The file is the deposit LIST under the screen's own filters. It
                is NOT a per-batch paying-in slip with its individual payments;
                that is a different artefact off `DepositBatchPage`, and two
                meanings behind one button is a worse answer than one stated
                meaning. */}
            <DownloadButton
              disabled={body === undefined || slipRequest.isPending}
              onDownload={() => slipRequest.mutate()}
            />
          </>
        }
      />

      {routeAbsent ? (
        <ArrivesWith
          title={t("payments.deposits.awaitsTitle")}
          message={t("payments.deposits.awaits")}
        />
      ) : failed ? (
        <Panel role="alert">
          <h3>{t("payments.deposits.errorTitle")}</h3>
          <p className="pay-absent">{apiErrorText(batchesQuery.error, translate)}</p>
        </Panel>
      ) : body === undefined ? (
        <LoadingSkeleton variant="table" />
      ) : (
        <>
          <KPIStrip
            kpis={[
              {
                id: "deposited",
                label: t("payments.deposits.kpi.deposited"),
                money: {
                  amount: body.kpis.deposited_total ?? "0",
                  currency: body.kpis.currency,
                  // BR-REP-001 — every money KPI labels its date basis, and a
                  // deposit batch's day IS the posting day (BR-PAY-025 / RQ-5).
                  basis: "posting",
                  locale: props.locale,
                },
                detail: t("payments.deposits.kpi.batches", { count: body.kpis.batch_count }),
              },
              {
                id: "reconciled",
                label: t("payments.deposits.kpi.reconciled"),
                money: {
                  amount: body.kpis.reconciled_total,
                  currency: body.kpis.currency,
                  basis: "posting",
                  locale: props.locale,
                },
                detail: t("payments.deposits.kpi.batches", {
                  count: body.kpis.reconciled_count,
                }),
              },
              {
                id: "unmatched",
                label: t("payments.deposits.kpi.unmatched"),
                money: {
                  amount: body.kpis.unmatched_total,
                  currency: body.kpis.currency,
                  basis: "posting",
                  locale: props.locale,
                },
                detail: t("payments.deposits.kpi.needYou", {
                  count: body.kpis.unmatched_count,
                }),
              },
              {
                // ITS OWN TILE. Money we believe we banked and money the bank
                // agrees we banked are different facts; one tile would make a
                // confident wrong number out of two right ones.
                id: "in_transit",
                label: t("payments.deposits.kpi.inTransit"),
                money: {
                  amount: body.kpis.in_transit_total,
                  currency: body.kpis.currency,
                  basis: "posting",
                  locale: props.locale,
                },
                detail: t("payments.deposits.kpi.settling", {
                  count: body.kpis.in_transit_count,
                }),
              },
            ]}
          />

          {/* `P2.10` — the money this list is NOT showing, because its till is
              still open. Directly under the tiles and above the toolbar, so it
              reads as a caveat on the four figures rather than as a row. */}
          <StillOpenCounterNote stillOpen={body.still_open} t={translate} locale={props.locale} />

          {body.kpis.unmatched_count > 0 && (
            <div className="pay-attention" role="note">
              <Kicker>{t("payments.deposits.attentionKicker")}</Kicker>
              <p>
                {t("payments.deposits.attention", { count: body.kpis.unmatched_count })}{" "}
                <InlineLinkTo to={tenantPath(DEPOSITS_IMPORT_ROUTE)}>
                  {t("payments.deposits.attentionLink")}
                </InlineLinkTo>
              </p>
            </div>
          )}

          {/* THE DAY-CUT. The status segments that stood beside it are gone —
              they are chips on the table's own toolbar now (B14 rule 12), which
              is where the search and `+ Filter` live. Disabled WITH its reason
              when there is nothing to cut, which is a real and common state,
              and the reason is a different sentence from "you may not do
              this". */}
          <div className="pay-toolbar">
            {days.length === 0 ? (
              <span className="pay-absent" role="note">
                {t("payments.deposits.nothingToCut")}
              </span>
            ) : (
              <Button
                variant="primary"
                onClick={() => {
                  setCutDay(days[0].day ?? "");
                  setCutOpen(true);
                }}
              >
                {t("payments.deposits.cut", { count: days.length })}
              </Button>
            )}
          </div>

          <DepositsList
            response={body}
            // `isPending`, not `isFetching` — the journal's own choice one
            // module over. A background refetch must not blank a table a clerk
            // is reading; the FIRST load is already the branch above.
            loading={batchesQuery.isPending}
            state={tableState}
            onStateChange={setTableState}
            locale={props.locale}
            batchPath={(batchId) => tenantPath(depositBatchRoute(batchId))}
          />

          <GapNotes gaps={body.unavailable} t={translate} />
        </>
      )}

      {cutOpen && (
        <FormModal
          title={t("payments.deposits.cutTitle")}
          kicker={t("payments.deposits.cutKicker")}
          schema={cutSchema(translate)}
          values={{ day: cutDay }}
          submitLabel={t("payments.deposits.cutSubmit")}
          onSubmit={handleCut}
          onClose={() => setCutOpen(false)}
        >
          <p className="pay-absent">{t("payments.deposits.cutHelp")}</p>
          <SelectField
            id="day"
            label={t("payments.deposits.cutDay")}
            value={cutDay}
            onChange={setCutDay}
            required
            // `DEF-PAY-10731` (L1-11's twin) — the opener pre-selects the first
            // day, but a `""` state with no empty option would DRAW a day the
            // form does not hold. The placeholder makes the two agree always.
            placeholder={t("payments.deposits.cutDayChoose")}
            options={days.map((day) => ({
              value: day.day ?? "",
              // The day AND what is sitting on it, so a clerk banking one of
              // several days can tell them apart by the money rather than by
              // the date alone.
              // `DEF-PAY-10759` (L1-02 d) — through the money formatter: it
              // printed the stored `10.000000 USD`.
              label: `${day.day ?? ""} · ${
                day.unbatched_total === null
                  ? ""
                  : formatMoney(day.unbatched_total, day.currency, props.locale)
              }`,
            }))}
            help={t("payments.deposits.cutDayHelp")}
          />
        </FormModal>
      )}
    </div>
  );
}

/** How many payment numbers one skipped-line names before it says "+N". */
const SKIPPED_NAMED = 5;

/** `DEF-PAY-10759` (L1-02 c) — the cut's `skipped` list as one sentence per
 *  REASON, naming its payments. Reasons the catalogue does not know read as
 *  the generic one rather than as a code. Exported for its test. */
export function skippedLines(
  skipped: readonly { payment_no: string | null; reason: string }[],
  t: Translator,
): string[] {
  const byReason = new Map<string, string[]>();
  for (const one of skipped) {
    const list = byReason.get(one.reason) ?? [];
    list.push(one.payment_no ?? "—");
    byReason.set(one.reason, list);
  }
  return [...byReason.entries()].map(([reason, numbers]) => {
    const named = numbers.slice(0, SKIPPED_NAMED).join(", ");
    const more = numbers.length - SKIPPED_NAMED;
    return t("payments.deposits.cutSkipped", {
      count: numbers.length,
      reason: t(`payments.deposits.skipReason.${reason}`, {
        defaultValue: t("payments.deposits.skipReason.other"),
      }),
      numbers: more > 0 ? t("payments.deposits.cutSkippedMore", { named, more }) : named,
    });
  });
}

/** The one field the cut needs. `day` is REQUIRED and is chosen from the served
 *  list — the form cannot express a day the server has no money for, which is
 *  what stops a clerk banking a day that turns out to be empty. */
export function cutSchema(t: Translator) {
  return z.object({ day: z.string().min(1, t("payments.deposits.cutDayRequired")) });
}

// ── Lifecycle ─────────────────────────────────────────────
// packet: US-PAY-020@5b2e814 (sources: 04-docs/05-modules/08-payments/06-epics/EP-PAY-06-deposits-bank-rec.md US-PAY-020 §1/§3/§5 + the S37 capability matrix · 08-payments/02-business-rules.md BR-PAY-004/019/025/035/040 · 08-qa/01-e2e/journeys/J14-lockbox-day.md + J5-month-end.md · 05-prototype/UtilityBilling.html lines 3802-3830; co-packet US-PAY-022)
// generated: 2026-08-16 by story-coder (payments SURFACE lane — the S37 screen the /finance/deposits nav item has pointed at a placeholder for)
// checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-09)
// gates: RED PROVED FIRST — the S37 test file failed to resolve this module before it existed, and the booted-browser walk landed on "arrives with …" at /finance/deposits; verbatim in the lane report. tsc✔ · eslint --max-warnings 0✔ · vitest✔ · vite build✔ · run_gates✔
// exceptions: (1) the prototype's KPI figures ($298,410 / 31 batches) are a demo tenant's and are NOT ported — every tile is folded server-side over the same rows the table shows (US-PAY-020 TC-2) · (2) "↓ Deposit slip for bookkeeper" renders DISABLED with its reason: IS-9's CSV rides the platform export pipeline and `deposit_batches` is not a registered exportable resource · (3) the day-cut offers DAYS THAT HAVE UNBATCHED MONEY rather than "today" — BR-TEN-043 forbids a server clock, and an empty list is the honest "everything is banked" · (4) `occurred_at` is stamped from the BROWSER and sent, which is the legitimate reading of BR-TEN-043: the caller states the moment and the server never reads one · (5) a reconciled row offers View and never Resolve — BR-PAY-004 locks it and the service refuses a second reconcile, so the control would fail on click
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
