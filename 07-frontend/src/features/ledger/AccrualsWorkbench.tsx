// ── Trace ──────────────────────────────────────────────
// Task:     Finance blueprint `P3.1` — the accruals workbench. Eight live
//           routes over four engines (`unbilled_accrual`, `unpaid_cost_accrual`,
//           `depreciation`, `allowance`), ~145 KB of tested Python, and **zero
//           front-end callers** until this file.
// Drawing:  05-prototype/07 Finance Blueprint.pdf — **p026** is the wireframe
//           of 1·4 and its correction box; **p027** carries the six numbered
//           notes, the filter-criteria table and "Components to use"; **p028**
//           carries WRITE SURFACES / TODAY / TASK / WALKED / RULES.
//           Built from the RENDERED IMAGES (B14 rule 42) — the text layer of
//           this document is scrambled and is an index, never a specification.
// Rules:    BR-LED-005 (an accrual auto-reverses on day 1 of the NEXT period) ·
//           BR-LED-006 (the close checklist asks the same question) ·
//           BR-TEN-022 (the period comes from fiscal settings, never stored) ·
//           BR-TEN-043 (the posting instant is an INPUT) · BR-SHL-020 ·
//           BR-SHL-023 · BR-SHL-025 (a control that cannot act is DISABLED WITH
//           ITS REASON) · CLAUDE.md hard rule 2 (money 4dp, display 2, beside a
//           CHAR(3)) · hard rule 4 · hard rule 7 ·
//           B14 rule 2 · 4 (button grammar) · 12 · 13 · 14 · 15 (two visible row
//           actions then `…`) · 16 · 20 (ONE table type) · 21 (Tailwind only —
//           this file is on `styles/route-b-migrated.txt`) · 31 (no database id
//           is ever a visible value) · 32 · 33 (the text caps; RATIONALE is zero
//           words on screen) · 37 (a drawn figure is an illustration) · 43 (a
//           piece of UI is a COMPONENT) · 44 (our scale and kit decide HOW)
// Tests:    07-frontend/src/features/ledger/financeP3Doors.dom.test.tsx ·
//           10-scripts/fin_p3_screens_walkthrough.mjs (the browser walk — the
//           only check in this repo that reads rendered output)
//           10-scripts/fin_p3_6_accrual_reversal_pg_proof.py (the engine, on
//           real PostgreSQL)
// ───────────────────────────────────────────────────────
//
// 1·4 ACCRUALS — the four period-end entries a finance officer posts before the
// month closes.
//
// ══════════════════════════════════════════════════════════════════════════
// ⚠ TWO OF THE FOUR REVERSE AND TWO MUST NEVER. THAT IS THE WHOLE SCREEN.
// ══════════════════════════════════════════════════════════════════════════
// p026's correction box, verbatim: *"Two of the four are accruals; two are not,
// on purpose."* Unbilled revenue and unpaid costs post `type='accrual'` and take
// a day-1 mirror (BR-LED-005). Depreciation posts `type='standard'` and STANDS —
// `depreciation.py`: *"IT IS NOT AN ACCRUAL AND IT MUST NEVER BE ONE … a
// depreciation entry that reversed itself on day 1 would leave the plant at its
// purchase cost forever"*, which `CR-060` §5 measures at **$40,000 on one
// truck**. The allowance stands too — `allowance.py`: *"IT IS A BALANCE, NOT AN
// ACCRUAL … carried from month to month."*
//
// **So the drawing carries a `Type` and a `Reverses` column and the difference
// is on screen rather than in a docstring.** Neither is decided here: both
// arrive on every preview from `accruals_api._posting_shape`, because a browser
// holding its own table of *which engine reverses* is the literal-outlives-its-
// list failure this blueprint names on p019 — and this one would be a literal
// about money.
//
// ══════════════════════════════════════════════════════════════════════════
// WHY A ROW IS A LINE AND AN ACT IS AN ENGINE — the one place this differs
// from the drawing, recorded rather than left to be noticed
// ══════════════════════════════════════════════════════════════════════════
// p027 note 5's box: *"Four engines, with unbilled revenue split by service."*
// So five lines, and the drawing puts `👁 ✓ …` on every one of them.
//
// **A POST IS PER ENGINE AND NOT PER LINE.** `accrue_unbilled_revenue` writes
// ONE entry covering every service in the window — p028's WRITE SURFACES row
// says so: *"Post per engine — preview and post, four times."* A `✓` on the
// *Electric* line that also posted *Water* would be a control lying about what
// it does, on a money path.
//
// So the actions render **once per engine, on its first line**, and a
// continuation service line carries none. The confirm dialog names the engine
// and its WHOLE total, so nobody can read a per-service post into it. The
// difference from the drawing is deliberate and is in the decision log with its
// figure.
//
// ══════════════════════════════════════════════════════════════════════════
// PRESSING IT TWICE IS SAFE, AND THAT IS THE ENGINE'S PROPERTY, NOT THIS
// SCREEN'S
// ══════════════════════════════════════════════════════════════════════════
// Every engine keys its post once per period, for ever, so a re-run posts only
// what is missing and a replay answers `created: false` with the same entry id.
// p027 note 6 states it as the reason `Post all ✓` is safe on a resumed close.
// **Nothing here disables a button to achieve that** — a screen that guarded it
// would be a second, weaker copy of a guarantee the database already holds.
//
// ══════════════════════════════════════════════════════════════════════════
// THE TOOLBAR IS FOR CONSISTENCY, NOT VOLUME (p027)
// ══════════════════════════════════════════════════════════════════════════
// *"Four engines, with unbilled revenue split by service. It will not grow with
// the tenant … server paging is not proposed and NFR-3 does not bite."* The six
// controls are here because B14 rule 12 puts them on every list; the search, the
// filters, the sort and the page are taken in the browser through the shared
// `clientPage` seam, which says in its own docstring that it is a seam.
import { useMemo, useState } from "react";

import { useQueries, useQueryClient } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";

import { api, isApiError } from "@/api/client";
import type { ApiClient } from "@/api/client";
import {
  getAllowancePreview,
  getDepreciationPreview,
  getUnbilledAccrualPreview,
  getUnpaidCostAccrualPreview,
  postAllowance,
  postDepreciation,
  postUnbilledAccrual,
  postUnpaidCostAccrual,
} from "@/api/endpoints";
import type {
  AllowancePreview,
  DepreciationPreview,
  UnbilledAccrualPreview,
  UnpaidCostAccrualPreview,
} from "@/api/endpoints";
import { Button } from "@/components/Button";
import { ConfirmDialog } from "@/components/ConfirmDialog";
import { DataTable } from "@/components/DataTable";
import { FilterBar } from "@/components/FilterBar";
import { MoneyCell } from "@/components/MoneyCell";
import { Panel } from "@/components/Panel";
import { PlainTable } from "@/components/Surfaces";
import { RowAction, RowActions } from "@/components/RowActions";
import { StatusPill } from "@/components/StatusPill";
import { useToast } from "@/components/Toast";
import { clientPage } from "@/components/clientTable";
import type { ClientTableSpec } from "@/components/clientTable";
import { CommitIcon, EyeIcon } from "@/components/icons";
import { DEFAULT_PAGE_SIZE } from "@/components/tableTypes";
import type { TableConfig, TableRequestState } from "@/components/tableTypes";
import { serviceLabel } from "@/features/assets/assetsShared";
import { Dash } from "@/features/metering/meteringShared";
import { bucketLabel } from "@/features/payments/paymentsShared";
import { apiErrorText } from "@/features/tenancy/settingsShared";
import type { Translator } from "@/features/tenancy/settingsShared";

/** The four routes, named once.
 *
 *  ⚠ **THIS IS NOT A LIST THAT CAN GO STALE BEHIND THE SERVER.** `entry_type`
 *  and `reverses_on` — the two facts that decide money — are NOT in it; they
 *  arrive on every response. What is here is which WRAPPER to call and which
 *  catalogue key names the engine, and both of those are this file's own. */
export const ACCRUAL_ENGINES = [
  "unbilled",
  "unpaid_costs",
  "depreciation",
  "allowance",
] as const;
export type AccrualEngine = (typeof ACCRUAL_ENGINES)[number];

/** The screen id the shared `ColumnChooser` keys its per-user preference on. */
export const ACCRUALS_SCREEN_ID = "S56.accruals";

/** One drawn LINE of the workbench. */
export interface AccrualLine {
  /** React's key and the preference store's. **Never rendered** (B14 rule 31). */
  key: string;
  engine: AccrualEngine;
  /** TRUE on the engine's first line — the only line that carries the acts. */
  leads: boolean;
  /** `"accrual"` or `"standard"`, from the server. */
  entryType: string | null;
  /** Day 1 of the next FISCAL period, or `null` for *Never*. */
  reversesOn: string | null;
  service: string | null;
  amount: string | null;
  currency: string | null;
  posted: boolean;
  /** TRUE while the engine's preview has not arrived or could not be read. */
  unanswered: boolean;
}

/** What each engine's preview answers, narrowed to what a LINE needs. */
type EnginePreview =
  | { engine: "unbilled"; data: UnbilledAccrualPreview }
  | { engine: "unpaid_costs"; data: UnpaidCostAccrualPreview }
  | { engine: "depreciation"; data: DepreciationPreview }
  | { engine: "allowance"; data: AllowancePreview };

/**
 * The engine's lines, in the drawing's order.
 *
 * ⚠ **UNBILLED REVENUE SPLITS BY SERVICE AND THE OTHER THREE DO NOT** — p027's
 * own box. A window in which no service accrued produces ONE line carrying the
 * engine's total, because a list that drops an engine when it has nothing to
 * post is a list a clerk reads as *"depreciation is not set up"*.
 *
 * ⚠ **THE ALLOWANCE'S FIGURE IS `movement`, NOT `target`.** It is a balance
 * carried forward and the entry tops it up; showing the target would show the
 * whole provision as though it were about to be posted this month.
 */
export function accrualLines(previews: readonly EnginePreview[]): AccrualLine[] {
  const out: AccrualLine[] = [];
  for (const preview of previews) {
    if (preview.engine === "unbilled") {
      const services = preview.data.services;
      if (services.length === 0) {
        out.push({
          key: "unbilled",
          engine: "unbilled",
          leads: true,
          entryType: preview.data.entry_type,
          reversesOn: preview.data.reverses_on,
          service: null,
          amount: preview.data.total,
          currency: preview.data.currency,
          posted: preview.data.already_posted_entry_id !== null,
          unanswered: false,
        });
      } else {
        services.forEach((row, index) => {
          out.push({
            key: `unbilled|${row.service}`,
            engine: "unbilled",
            leads: index === 0,
            entryType: preview.data.entry_type,
            reversesOn: preview.data.reverses_on,
            service: row.service,
            amount: row.amount,
            currency: preview.data.currency,
            posted: preview.data.already_posted_entry_id !== null,
            unanswered: false,
          });
        });
      }
    } else if (preview.engine === "unpaid_costs") {
      out.push({
        key: "unpaid_costs",
        engine: "unpaid_costs",
        leads: true,
        entryType: preview.data.entry_type,
        reversesOn: preview.data.reverses_on,
        service: null,
        amount: preview.data.total,
        currency: preview.data.currency,
        posted: preview.data.already_posted_entry_id !== null,
        unanswered: false,
      });
    } else if (preview.engine === "depreciation") {
      out.push({
        key: "depreciation",
        engine: "depreciation",
        leads: true,
        entryType: preview.data.entry_type,
        reversesOn: preview.data.reverses_on,
        service: null,
        amount: preview.data.total,
        currency: preview.data.currency,
        posted: preview.data.already_posted_entry_id !== null,
        unanswered: false,
      });
    } else {
      out.push({
        key: "allowance",
        engine: "allowance",
        leads: true,
        entryType: preview.data.entry_type,
        reversesOn: preview.data.reverses_on,
        service: null,
        // A balance, topped up — see this function's docstring.
        amount: preview.data.movement,
        currency: preview.data.currency ?? null,
        posted: preview.data.already_posted_entry_id !== null,
        unanswered: false,
      });
    }
  }
  return out;
}

/** A line for an engine whose preview has not arrived or was refused.
 *
 *  ⚠ **AN ENGINE THAT COULD NOT BE ASKED IS SHOWN, NOT DROPPED.** A workbench
 *  silently four rows short is one a clerk closes the month from. */
export function unansweredLine(engine: AccrualEngine): AccrualLine {
  return {
    key: engine,
    engine,
    leads: true,
    entryType: null,
    reversesOn: null,
    service: null,
    amount: null,
    currency: null,
    posted: false,
    unanswered: true,
  };
}

/** The search / filter / sort the browser performs over the bounded list. */
export const ACCRUALS_TABLE_SPEC: ClientTableSpec<AccrualLine> = {
  search: (row) => [row.engine, row.service ?? ""],
  filter: (row, name, value) => {
    if (name === "engine") return row.engine === value;
    if (name === "type") return row.entryType === value;
    if (name === "service") return row.service === value;
    if (name === "state") return value === "posted" ? row.posted : !row.posted;
    return true;
  },
  sortValue: (row, key) => {
    if (key === "entry") return row.engine;
    if (key === "service") return row.service;
    if (key === "amount") return row.amount === null ? null : Number(row.amount);
    if (key === "reverses") return row.reversesOn;
    if (key === "state") return row.posted ? 1 : 0;
    return null;
  },
};

/**
 * The capability-matrix row, as a `TableConfig` — p027's FIELDS line in its
 * drawn order: *Entry · Type · Service · Basis · Amount · Reverses · State ·
 * Actions*.
 *
 * ⚠ **THE SERVICE FILTER'S OPTIONS COME FROM THE ROWS, NOT FROM A LITERAL.**
 * p027's criteria table names `GET /reference/services — never a literal array`
 * and this product serves no such route; deriving the set from the lines the
 * engine actually produced is the same guarantee by a shorter path, and it
 * cannot list a service this tenant does not bill.
 */
export function accrualsConfig(
  lines: readonly AccrualLine[],
  t: Translator,
  locale: string | undefined,
  actions?: {
    onPreview: (engine: AccrualEngine) => void;
    onPost: (engine: AccrualEngine) => void;
    busy: AccrualEngine | null;
  },
): TableConfig<AccrualLine> {
  const services = Array.from(
    new Set(lines.map((row) => row.service).filter((code): code is string => code !== null)),
  );
  return {
    screenId: ACCRUALS_SCREEN_ID,
    getRowId: (row) => row.key,
    searchFields: ["engine", "service"],
    searchPlaceholder: "finance.workbench.searchPrompt",
    defaultSort: { sort: "entry", dir: "asc" },
    filters: [
      {
        name: "engine",
        label: t("finance.workbench.col.entry"),
        options: ACCRUAL_ENGINES.map((value) => ({
          value,
          label: t(`finance.workbench.engine.${value}`),
        })),
      },
      {
        name: "type",
        label: t("finance.workbench.col.type"),
        options: [
          { value: "accrual", label: t("finance.journal.type.accrual") },
          { value: "standard", label: t("finance.journal.type.standard") },
        ],
      },
      {
        name: "service",
        label: t("finance.workbench.col.service"),
        options: services.map((value) => ({
          value,
          label: serviceLabel(value, t),
        })),
      },
      {
        name: "state",
        label: t("finance.workbench.col.state"),
        options: [
          { value: "not_posted", label: t("finance.workbench.state.notPosted") },
          { value: "posted", label: t("finance.workbench.state.posted") },
        ],
      },
    ],
    columns: [
      {
        key: "entry",
        label: t("finance.workbench.col.entry"),
        sortable: true,
        identity: true,
        cell: (row) => t(`finance.workbench.engine.${row.engine}`),
      },
      {
        key: "type",
        label: t("finance.workbench.col.type"),
        // p027 note 4 — *"the two columns that stop the $40,000 error"*. Two
        // TONES, because the difference has to be seen and not read.
        cell: (row) =>
          row.entryType === null ? (
            <Dash />
          ) : (
            <StatusPill tone={row.entryType === "accrual" ? "warning" : "neutral"}>
              {t(`finance.journal.type.${row.entryType}`, { defaultValue: row.entryType })}
            </StatusPill>
          ),
      },
      {
        key: "service",
        label: t("finance.workbench.col.service"),
        sortable: true,
        cell: (row) =>
          row.service === null ? (
            <Dash />
          ) : (
            serviceLabel(row.service, t)
          ),
      },
      {
        key: "basis",
        label: t("finance.workbench.col.basis"),
        cell: (row) => t(`finance.workbench.basis.${row.engine}`),
      },
      {
        key: "amount",
        label: t("finance.workbench.col.amount"),
        numeric: true,
        sortable: true,
        // ⚠ `null` IS NOT 0.00 AND IS NEVER RENDERED AS ONE. Every engine
        // serves a null when the figure is UNANSWERABLE — no currency could be
        // agreed, the asset register published no read, the policy is off — and
        // a 0.00 there is a claim about a balance sheet (DEF-127's shape).
        cell: (row) => (
          <WorkbenchMoney amount={row.amount} currency={row.currency} locale={locale} />
        ),
      },
      {
        key: "reverses",
        label: t("finance.workbench.col.reverses"),
        sortable: true,
        // A STANDARD entry says **Never** — the word, not a dash. p026: *"the
        // difference is on screen rather than in a docstring"*, and a dash
        // reads as *nobody filled this in*.
        cell: (row) =>
          row.reversesOn !== null ? (
            row.reversesOn
          ) : row.entryType === "standard" ? (
            <span className="font-medium">{t("finance.workbench.never")}</span>
          ) : (
            <Dash />
          ),
      },
      {
        key: "state",
        label: t("finance.workbench.col.state"),
        cell: (row) =>
          row.unanswered ? (
            <span className="text-danger-700" role="alert">
              {t("finance.workbench.unanswered")}
            </span>
          ) : (
            <StatusPill tone={row.posted ? "success" : "neutral"}>
              {row.posted
                ? t("finance.workbench.state.posted")
                : t("finance.workbench.state.notPosted")}
            </StatusPill>
          ),
      },
      {
        key: "actions",
        label: t("finance.workbench.col.actions"),
        locked: true,
        // ⚠ **ONE SET PER ENGINE, ON ITS FIRST LINE** — see the header. A `✓`
        // on the *Water* line that posted *Electric* with it would be a control
        // lying about what it does.
        cell: (row) =>
          actions === undefined || !row.leads ? null : (
            <RowActions>
              <RowAction
                label={t("finance.workbench.previewAction")}
                icon={<EyeIcon />}
                reason={row.unanswered ? t("finance.workbench.nothingToPreview") : null}
                onClick={() => actions.onPreview(row.engine)}
              />
              <RowAction
                label={t("finance.workbench.postAction")}
                icon={<CommitIcon />}
                working={actions.busy === row.engine}
                reason={row.unanswered ? t("finance.workbench.nothingToPost") : null}
                onClick={() => actions.onPost(row.engine)}
              />
            </RowActions>
          ),
      },
    ],
  };
}

export interface AccrualsWorkbenchProps {
  /** The tenant's own accounting period. Both ends are the SERVER's answer —
   *  never `new Date()`, which would run a different window for a clerk in
   *  Houston and a laptop still set to UTC (DEF-094's shape). */
  period: { start: string; end: string } | null;
  /** BR-TEN-043 — the instant a post is stamped with, supplied by the caller so
   *  a double-press stamps one moment and a test can state it. */
  now: () => string;
  t: Translator;
  client?: ApiClient;
  locale?: string;
  /** Rendered in the PAGE HEAD by the page (B14 rule 2 — one page header), so
   *  this component reports what it would post and draws no second primary. */
  onSummary?: (summary: { engines: number; unposted: number }) => void;
}

/** The whole of 1·4's first card — the toolbar, the table, the footer and the
 *  preview the `👁` opens. */
export function AccrualsWorkbench(props: AccrualsWorkbenchProps) {
  const { t } = useTranslation();
  const client = props.client ?? api;
  const toast = useToast();
  const queryClient = useQueryClient();
  const [tableState, setTableState] = useState<TableRequestState>({
    q: "",
    sort: "entry",
    dir: "asc",
    page: 1,
    per: DEFAULT_PAGE_SIZE,
    filters: {},
  });
  const [opened, setOpened] = useState<AccrualEngine | null>(null);
  const [confirming, setConfirming] = useState<AccrualEngine | "all" | null>(null);
  const [busy, setBusy] = useState<AccrualEngine | null>(null);
  const [failure, setFailure] = useState<string | null>(null);

  const from = props.period?.start ?? "";
  const to = props.period?.end ?? "";
  const ready = from !== "" && to !== "";

  // FOUR INDEPENDENT READS, not one. Each engine refuses for its own reasons
  // (the asset register is unreadable; the allowance policy is off) and one
  // combined query would make any refusal hide the other three.
  const previews = useQueries({
    queries: [
      {
        queryKey: ["ledger", "accruals", "unbilled", from, to],
        queryFn: () => getUnbilledAccrualPreview({ from, to }, client),
        enabled: ready,
        retry: false,
      },
      {
        queryKey: ["ledger", "accruals", "unpaid_costs", from, to],
        queryFn: () => getUnpaidCostAccrualPreview({ from, to }, client),
        enabled: ready,
        retry: false,
      },
      {
        queryKey: ["ledger", "accruals", "depreciation", from, to],
        queryFn: () => getDepreciationPreview({ from, to }, client),
        enabled: ready,
        retry: false,
      },
      {
        queryKey: ["ledger", "accruals", "allowance", from, to],
        queryFn: () => getAllowancePreview({ from, to }, client),
        enabled: ready,
        retry: false,
      },
    ],
  });

  const loading = previews.some((query) => query.isPending) && ready;

  const lines = useMemo(() => {
    const answered: EnginePreview[] = [];
    const missing: AccrualEngine[] = [];
    const [unbilled, unpaid, depreciation, allowance] = previews;
    if (unbilled.data !== undefined) answered.push({ engine: "unbilled", data: unbilled.data });
    else missing.push("unbilled");
    if (unpaid.data !== undefined) answered.push({ engine: "unpaid_costs", data: unpaid.data });
    else missing.push("unpaid_costs");
    if (depreciation.data !== undefined)
      answered.push({ engine: "depreciation", data: depreciation.data });
    else missing.push("depreciation");
    if (allowance.data !== undefined) answered.push({ engine: "allowance", data: allowance.data });
    else missing.push("allowance");
    const rows = accrualLines(answered);
    // Only AFTER the reads have settled — an engine still in flight is not an
    // engine that could not be asked.
    return loading ? rows : [...rows, ...missing.map(unansweredLine)];
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [previews.map((query) => query.dataUpdatedAt).join("|"), loading]);

  async function post(engine: AccrualEngine) {
    if (!ready) return;
    setBusy(engine);
    setFailure(null);
    const body = { from, to, posted_at: props.now() };
    try {
      const result =
        engine === "unbilled"
          ? await postUnbilledAccrual(body, client)
          : engine === "unpaid_costs"
            ? await postUnpaidCostAccrual(body, client)
            : engine === "depreciation"
              ? await postDepreciation(body, client)
              : await postAllowance(body, client);
      // `created: false` is the REPLAY and not a failure — a resumed close
      // pressing this twice is the correct outcome, and the toast says which
      // happened rather than claiming a posting that did not occur.
      toast(
        result.created
          ? t("finance.workbench.postedToast", {
              entry: t(`finance.workbench.engine.${engine}`),
            })
          : t("finance.workbench.alreadyPostedToast", {
              entry: t(`finance.workbench.engine.${engine}`),
            }),
      );
      await queryClient.invalidateQueries({ queryKey: ["ledger"] });
    } catch (error) {
      setFailure(
        isApiError(error) ? apiErrorText(error, props.t) : t("finance.workbench.postFailed"),
      );
    } finally {
      setBusy(null);
    }
  }

  async function postAll() {
    for (const engine of ACCRUAL_ENGINES) {
      // eslint-disable-next-line no-await-in-loop
      await post(engine);
    }
  }

  const config = useMemo(
    () =>
      accrualsConfig(lines, props.t, props.locale, {
        onPreview: (engine) => setOpened((current) => (current === engine ? null : engine)),
        onPost: (engine) => setConfirming(engine),
        busy,
      }),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [lines, props.locale, busy, t],
  );
  const paged = clientPage(lines, tableState, ACCRUALS_TABLE_SPEC);
  const unposted = lines.filter((row) => row.leads && !row.posted && !row.unanswered).length;

  return (
    <>
      <Panel>
        <div className="mb-4 flex items-center justify-between gap-4">
          <h3 className="m-0 font-heading text-h5 leading-heading">
            {t("finance.workbench.title")}
          </h3>
          {/* B14 rule 4 — `Verb ✓` commits. It is the PANEL's action and not a
              second page-head primary (rule 2); the head already carries the
              view strip and the page title. */}
          <Button
            variant="primary"
            data-testid="accruals-post-all"
            disabled={!ready || loading || unposted === 0 || busy !== null}
            onClick={() => setConfirming("all")}
          >
            {t("finance.workbench.postAll")}
          </Button>
        </div>
        <DataTable<AccrualLine>
          config={config}
          state={tableState}
          onStateChange={setTableState}
          rows={paged.page}
          totalRows={paged.total}
          loading={loading}
          filterBarSlot={
            <FilterBar
              filters={config.filters ?? []}
              state={tableState}
              onStateChange={setTableState}
            />
          }
          empty={{
            title: t("finance.workbench.noMatchTitle"),
            helper: t("finance.workbench.noMatchHelper"),
            ctaLabel: t("finance.journal.clearSearch"),
            ctaVariant: "secondary",
            onCta: () => setTableState({ ...tableState, q: "", filters: {}, page: 1 }),
          }}
        />
        {failure !== null && (
          <p className="mt-4 text-sm text-danger-700" role="alert">
            {failure}
          </p>
        )}
      </Panel>

      {opened !== null && (
        <AccrualPreviewPanel
          engine={opened}
          data={previews[ACCRUAL_ENGINES.indexOf(opened)].data as AnyAccrualPreview | undefined}
          problem={
            previews[ACCRUAL_ENGINES.indexOf(opened)].isError
              ? apiErrorText(previews[ACCRUAL_ENGINES.indexOf(opened)].error, props.t)
              : null
          }
          t={props.t}
          locale={props.locale}
          onClose={() => setOpened(null)}
        />
      )}

      {/* B14 rule 33 — a CONSEQUENCE before an irreversible act: two sentences,
          six words each, and never cut below clarity. */}
      {confirming !== null && (
        <ConfirmDialog
          confirmVariant="danger"
          working={busy !== null}
          title={
            confirming === "all"
              ? t("finance.workbench.confirmAllTitle")
              : t("finance.workbench.confirmOneTitle", {
                  entry: t(`finance.workbench.engine.${confirming}`),
                })
          }
          consequence={
            confirming === "all"
              ? t("finance.workbench.confirmAllBody")
              : t("finance.workbench.confirmOneBody")
          }
          confirmLabel={t("finance.workbench.postAll")}
          onCancel={() => setConfirming(null)}
          onConfirm={() => {
            const target = confirming;
            setConfirming(null);
            void (target === "all" ? postAll() : post(target));
          }}
        />
      )}
    </>
  );
}

/**
 * `👁` — *"the lines it would post"* (p027's Components table).
 *
 * ⚠ **A PANEL AND NOT A MODAL.** B14 §5's test: it holds a TABLE of its own, so
 * it is not the estimate precedent. The blueprint draws no second screen for it
 * and this list is bounded, so it opens in place under the workbench.
 */
function AccrualPreviewPanel(props: {
  engine: AccrualEngine;
  data: AnyAccrualPreview | undefined;
  /** The engine's own refusal, already put into plain language by the caller —
   *  `null` means *still arriving*, not *nothing wrong*. */
  problem: string | null;
  t: Translator;
  locale?: string;
  onClose: () => void;
}) {
  const { t } = useTranslation();
  const data = props.data;

  return (
    <Panel>
      <div className="mb-4 flex items-center justify-between gap-4">
        <h3 className="m-0 font-heading text-h5 leading-heading">
          {t("finance.workbench.previewTitle", {
            entry: t(`finance.workbench.engine.${props.engine}`),
          })}
        </h3>
        <Button variant="ghost" onClick={props.onClose}>
          {t("forms.close")}
        </Button>
      </div>
      {data === undefined ? (
        <p className="text-sm text-neutral-700" role="note">
          {props.problem ?? t("finance.workbench.previewLoading")}
        </p>
      ) : previewRows(props.engine, data, t).length === 0 ? (
        // ⚠ **AN EMPTY TABLE WITH HEADINGS IS HALF A SCREEN.** The first
        // browser walk of this panel opened the allowance and drew two column
        // headings over nothing — which reads as *the preview is broken*, not
        // as *this engine has no lines this period*. Every list in the kit owes
        // an empty state and this one is a list.
        <p className="text-sm text-neutral-700" role="note">
          {t("finance.workbench.previewEmpty")}
        </p>
      ) : (
        <PlainTable>
          <thead>
            <tr>
              <th scope="col">{t("finance.workbench.col.line")}</th>
              <th scope="col">{t("finance.workbench.col.amount")}</th>
            </tr>
          </thead>
          <tbody>
            {previewRows(props.engine, data, t).map((row) => (
              <tr key={row.label}>
                <td>{row.label}</td>
                <td>
                  <WorkbenchMoney
                    amount={row.amount}
                    currency={row.currency}
                    locale={props.locale}
                  />
                </td>
              </tr>
            ))}
          </tbody>
        </PlainTable>
      )}
    </Panel>
  );
}

/** Whichever of the four a preview panel was handed. */
type AnyAccrualPreview =
  | UnbilledAccrualPreview
  | UnpaidCostAccrualPreview
  | DepreciationPreview
  | AllowancePreview;

/**
 * Money on this screen, and the two absences it has to tell apart.
 *
 * ⚠ **A FIGURE WITH NO `CHAR(3)` IS NOT PRINTED** (CLAUDE.md rule 2 — a bare
 * number in a book is half a fact). `null` currency happens for real here:
 * `unpaid_cost_accrual` serves it when the window holds purchases in more than
 * one currency, so no single entry can carry them.
 *
 * ⚠ **AND A NULL AMOUNT IS NEVER 0.00.** `depreciation` serves `null` when the
 * asset register publishes no read — *"the plant did not depreciate"* is a claim
 * about a balance sheet and this screen does not make it (`DEF-127`'s shape).
 *
 * It composes `MoneyCell` and formats nothing itself: BR-SHL-023 gives this
 * product ONE money-formatting path.
 */
function WorkbenchMoney(props: {
  amount: string | null;
  currency: string | null;
  locale?: string;
}) {
  const { t } = useTranslation();
  if (props.amount === null) {
    return <Dash />;
  }
  if (props.currency === null) {
    return (
      <span className="text-neutral-700" role="note">
        {t("finance.workbench.noCurrency")}
      </span>
    );
  }
  return <MoneyCell amount={props.amount} currency={props.currency} locale={props.locale} />;
}

/** The lines an engine would post, as label + money. Each engine publishes a
 *  different evidence shape and none of them is re-derived here. */
function previewRows(
  engine: AccrualEngine,
  data: AnyAccrualPreview,
  t: (key: string, params?: Record<string, unknown>) => string,
): { label: string; amount: string | null; currency: string | null }[] {
  if (engine === "unbilled") {
    const preview = data as UnbilledAccrualPreview;
    return preview.services.map((row) => ({
      label: serviceLabel(row.service, t),
      amount: row.amount,
      currency: preview.currency,
    }));
  }
  if (engine === "unpaid_costs") {
    const preview = data as UnpaidCostAccrualPreview;
    return preview.accounts.map((row) => ({
      // B14 rule 31 — the CODE and the NAME, which is what a finance person
      // reads; `ledger_account_id` travels and is never drawn.
      label: `${row.code ?? ""} · ${row.name ?? ""}`,
      amount: row.amount,
      currency: preview.currency,
    }));
  }
  if (engine === "depreciation") {
    const preview = data as DepreciationPreview;
    return [
      {
        label: t("finance.workbench.assetsCounted", { count: preview.asset_count }),
        amount: preview.total,
        currency: preview.currency,
      },
    ];
  }
  const preview = data as AllowancePreview;
  return preview.bands.map((band) => ({
    label: bucketLabel(band.bucket, t),
    amount: band.provision,
    currency: preview.currency ?? null,
  }));
}

export default AccrualsWorkbench;

// ── Lifecycle ─────────────────────────────────────────────
// packet: 05-prototype/07 Finance Blueprint.pdf p016 (P3.1) + p026–p028 (screen 1·4, rendered at 2.2 and 4 and read as IMAGES, B14 rule 42) · 06-backend/apps/ledger/accruals_api.py · unbilled_accrual.py · unpaid_cost_accrual.py · depreciation.py · allowance.py · 04-docs/02-decisions/14-ui-conventions.md rules 2/4/12/13/14/15/16/20/21/31/32/33/37/43/44
// generated: 2026-09-24 by LANE FIN-P3
// checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-09)
// exceptions:
//   E1 **THE ACTS RENDER ONCE PER ENGINE, ON ITS FIRST LINE** — the drawing puts
//      them on all five. A post is per ENGINE (`accruals_api.py` p028 WRITE
//      SURFACES) and a `✓` on the Water line that also posted Electric would be
//      a control lying about what it does. Decision log 2026-09-24.
//   E2 **THE SERVICE FILTER IS DERIVED FROM THE ROWS**, not from
//      `GET /reference/services` — this product serves no such route. Same
//      guarantee (never a literal array) by a shorter path.
//   E3 **NO DOWNLOAD BUTTON.** p027's TABLE CONTROLS says *"All six"*; the six
//      include `↓`, and no export resource exists for this list (`apps/reports/
//      exports.py` registers four and none is an accrual preview). A live
//      control onto nothing is hard-won law 2's mirror; reported rather than
//      drawn disabled with a rationale rule 33 forbids on screen.
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
