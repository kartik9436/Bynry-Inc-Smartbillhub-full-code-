// ── Trace ──────────────────────────────────────────────
// Change:   CR-053 task 13 — *"Print bills"* (W4). PO ruling 2026-08-30:
//           *"Im okay with this"* on the PDF-set-plus-manifest recommendation.
//           ⚠ REDRAWN 2026-09-15 for `DEF-BIL-5354` — blueprint **screen 28**,
//           `05-prototype/04 Billing, As Built.pdf` p147–p150, READ AS IMAGES
//           at scale 2 and scale 4 (B14 rule 42).
//           Screens: Print bills, the seventh Billing tab
// Rules:    BR-NOT-029 (the pair, the fourteen columns, and clause (c) — never
//           claim a mail standard we do not perform) · BR-CUS-674 (an address
//           changes when the ACCOUNT HOLDER says so; this screen only reads) ·
//           BR-BIL-026 (a reprint renders the PINNED layout, for ever) ·
//           BR-SHL-025 (a forbidden control renders disabled WITH its reason) ·
//           BR-SHL-020 (a refusal in plain language) · BR-SHL-044 (one page
//           header) · BR-TEN-043 (the instant is the CLIENT's) · NFR-3 / NFR-5
//           (every list paged in the database; no cap anywhere) · B14 rule 21
//           (Tailwind utilities, no stylesheet class) · rule 31 (no database id
//           is the visible value of a field) · rule 32 (one sentence a section;
//           a stated absence CLOSED) · rule 33 (label ≤3 · fact ≤6 · rationale
//           ZERO words) · rule 37 (a drawn figure is an illustration) ·
//           rule 41 (the product matches the blueprint) · B12 r1 (202 + job_id)
// Defects:  DEF-BIL-5354 (the drawn second group and the four tiles, missing)
// ───────────────────────────────────────────────────────
/**
 * Hand one period's bills to a printer — and answer *"is this customer's bill
 * in it?"* before anybody presses anything.
 *
 * ══════════════════════════════════════════════════════════════════════════
 * WHAT CHANGED ON 2026-09-15, AND WHY IT IS THE WHOLE POINT (DEF-BIL-5354)
 * ══════════════════════════════════════════════════════════════════════════
 * This screen had the form, the counts and the button and **no list**. The
 * blueprint's own note says what that costs: *"A clerk's commonest question
 * here is not HOW MANY — it is IS THIS CUSTOMER'S BILL IN THE SET, usually
 * because that customer has rung. Without a searchable table the answer is
 * generate it and look in the zip."*
 *
 * So the period's bills are listed, paged in the database, each row saying
 * whether it will print and, when it will not, why. **One table for the whole
 * population, not two** — *"two tables would make a clerk searching for one
 * bill look twice, and the counts would stop reconciling the moment a filter
 * was applied."*
 *
 * ══════════════════════════════════════════════════════════════════════════
 * THE FOUR TILES ADD UP, AND THAT IS A RULE RATHER THAN A FLOURISH
 * ══════════════════════════════════════════════════════════════════════════
 * `will print + held back = in this period`, always: *"A set that printed 404
 * of 412 without saying so sends a print shop a short run and tells nobody."*
 * All four come off ONE server forecast, so nothing here can disagree with
 * anything else here.
 *
 * ⚠ **THE PAGES TILE IS MEASURED, AND IT IS 2 A BILL AND NOT THE 6 DRAWN.**
 * Every one of the demo utility's 79 printable bills was counted through the
 * archive's own renderer on 2026-09-15 and every one came back 2 pages. B14
 * rule 37: a figure drawn in a wireframe is an illustration, never a fact to
 * build to.
 *
 * ══════════════════════════════════════════════════════════════════════════
 * WHAT IT PROMISES ABOUT ADDRESSES, WHICH IS NOTHING IT CANNOT KEEP
 * ══════════════════════════════════════════════════════════════════════════
 * The server's `unavailable` notes are DRAWN, not swallowed. They say in words
 * that no address was CASS-certified, NCOA-processed or barcoded, because a
 * mail house's default assumption is otherwise and a silence here is a claim.
 * The screen adds nothing of its own to that list and edits none of it.
 *
 * And the screen changes no address: no form, no field, no save. An address
 * moves when the account holder says so, on the account, and this is a reader.
 */
import { useState } from "react";

import { useMutation, useQuery } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import { useNavigate } from "react-router-dom";

import { serverLinkHref } from "@/api/apiHref";
import { api } from "@/api/client";
import type { ApiClient, JobRecord } from "@/api/client";
import { getBillRuns, getCycles } from "@/api/endpoints";
import type { BillRunHistoryRow, CycleRow } from "@/api/endpoints";
import {
  getPrintSetBills,
  getPrintSetPreview,
  requestPrintSet,
} from "@/api/billingPrintEndpoints";
import type {
  PrintBillRow,
  PrintSetPreview,
  PrintSetUnavailable,
} from "@/api/billingPrintEndpoints";
import { Button } from "@/components/Button";
import { DataTable } from "@/components/DataTable";
import { DateCell } from "@/components/DateCell";
import type { RegionalDateFormat } from "@/components/DateCell";
import { KPIStrip } from "@/components/KPIStrip";
import type { KpiTile } from "@/components/KPIStrip";
import { MoneyCell } from "@/components/MoneyCell";
import { PageHeader } from "@/components/PageHeader";
import { Panel } from "@/components/Panel";
import { StatusPill } from "@/components/StatusPill";
import { InlineLinkTo } from "@/components/Surfaces";
import { accountDetailPath } from "@/features/customers/customersShared";
import { LoadingSkeleton, PermissionDenied } from "@/components/StateFrame";
import { DEFAULT_PAGE_SIZE } from "@/components/tableTypes";
import type { TableConfig, TableRequestState } from "@/components/tableTypes";
import {
  CELL_FULL,
  GuardedButton,
  isDenied,
  useAccessCell,
  useRegional,
} from "@/features/metering/meteringShared";
import type { RegionalProps } from "@/features/metering/meteringShared";
import { exportFailureReason } from "@/features/exports/ListExportButton";
import { frequencyKey } from "@/features/tenancy/routesCyclesShared";
import { apiErrorText, isPermissionDenied } from "@/features/tenancy/settingsShared";
import type { Translator } from "@/features/tenancy/settingsShared";
import { useTenantPath } from "@/routing/tenantPath";

import {
  BILLING_PERMISSION,
  BILLING_ROUTE,
  BILLING_TABS,
  BILLING_TAB_ALL,
  DASHBOARD_ROUTE,
  billDetailPath,
} from "./billingShared";

/** The SPA route. Registered in `App.tsx` and in `routing/screenIds.ts`. */
export const BILLING_PRINT_ROUTE = "/billing/print";

/** `ALL` is not a filter value — it is the ABSENCE of one, spelled so a
 *  `<select>` can carry it. Sending it as `f.bill_run_id=ALL` would filter for
 *  a run whose id is the word ALL and answer an empty set. */
export const ALL_RUNS = "";

/**
 * How the set is scoped, in the blueprint's own three words.
 *
 * The drawing gives Scope a picker AND a shortcut row beneath the form (*"Or
 * scope it by: a bill run · every issued bill"*). Both write THIS one value, so
 * the screen has a single source of truth for what is being printed and the two
 * controls cannot end up disagreeing about it.
 */
export type PrintScope = "cycle" | "run" | "all";

export const printSetPreviewKey = (filters: Record<string, string>) =>
  ["billing", "print-set", "preview", filters] as const;

export const printSetBillsKey = (
  filters: Record<string, string>,
  state: { q: string; page: number; per: number },
  hold: string,
) => ["billing", "print-set", "bills", filters, state, hold] as const;

export interface PrintBillsPageProps extends RegionalProps {
  client?: ApiClient; // test seam — screens never build their own transport
  /** IS-8 — the tenant's number format for `MoneyCell`. */
  locale?: string;
}

/**
 * The `f.<name>` filters this scope means, in the bills list's OWN grammar.
 *
 * Exported and pure because it is the one place the screen's three controls
 * become a server selection: the preview, the table and the POST all call it,
 * so **the tiles, the list and the archive cannot cover different bills.** That
 * was the whole argument for one table over two, one level down.
 */
export function printFilters(form: {
  scope: PrintScope;
  cycleId: string;
  runId: string;
  issuedFrom: string;
  issuedTo: string;
}): Record<string, string> {
  const filters: Record<string, string> = {};
  if (form.scope === "cycle" && form.cycleId !== "") {
    filters.cycle_id = form.cycleId;
  }
  if (form.scope === "run" && form.runId !== ALL_RUNS) {
    filters.bill_run_id = form.runId;
  }
  if (form.issuedFrom !== "") {
    filters.issued_from = form.issuedFrom;
  }
  if (form.issuedTo !== "") {
    filters.issued_to = form.issuedTo;
  }
  return filters;
}

/**
 * One run, as the picker names it. NEVER by id (B14 rule 31): a clerk choosing
 * *"which cycle am I posting?"* recognises a period and a run number, and a
 * uuid in a dropdown is the defect that rule was written for.
 */
export function runOptionLabel(run: BillRunHistoryRow, t: Translator): string {
  const period =
    run.period_start !== null && run.period_end !== null
      ? `${run.period_start} – ${run.period_end}`
      : t("billing.print.run.noPeriod");
  const name = run.run_no ?? t("billing.print.run.unnumbered");
  return t("billing.print.run.option", { name, period, bills: run.bills_issued });
}

/**
 * One cycle, as the drawing names it — `09-A · monthly`.
 *
 * The CODE and the frequency WORD, never the id (B14 rule 31), and the
 * frequency runs through `frequencyKey` so the two generations of that value
 * fold onto one catalogue entry instead of rendering a raw key.
 */
export function cycleScopeLabel(cycle: CycleRow, t: Translator): string {
  const key = frequencyKey(cycle.frequency);
  return key === null ? cycle.code : `${cycle.code} · ${t(key)}`;
}

/**
 * The seconds tile detail, in the unit a person plans around.
 *
 * Under a minute a clerk waits at the screen; over one they go and do something
 * else, so the sentence changes shape rather than printing 214 seconds.
 */
export function estimateText(seconds: number, t: Translator): string {
  if (seconds < 60) {
    const whole = Math.max(1, Math.round(seconds));
    // ⚠ **A SEPARATE SENTENCE FOR ONE, RATHER THAN A PLURAL RULE.** The browser
    // walk on 2026-09-15 read *"about 1 seconds"* off the tile. `{{seconds}}`
    // is not i18next's `count`, so nothing was ever going to pluralise it —
    // and turning it into `count` would owe every one of the eleven languages
    // its own plural forms for a sentence that only ever breaks at one.
    return whole === 1
      ? t("billing.print.tile.oneSecond")
      : t("billing.print.tile.seconds", { seconds: whole });
  }
  const whole = Math.max(1, Math.round(seconds / 60));
  return whole === 1
    ? t("billing.print.tile.oneMinute")
    : t("billing.print.tile.minutes", { minutes: whole });
}

/**
 * What the WILL IT PRINT column says on one row.
 *
 * ⚠ **THE REASON CODE IS NEVER RENDERED** (B14 rule 32). The server sends a
 * stable code and the words come from the catalogues; a code with no key of its
 * own falls back to the generic *Held back* rather than printing
 * `address_incomplete` at a clerk.
 */
export function holdText(reason: string | null, t: Translator): string {
  if (reason === null) {
    return t("billing.print.verdict.willPrint");
  }
  const words = t(`billing.print.hold.${reason}`, {
    defaultValue: t("billing.print.hold.other"),
  });
  return `${t("billing.print.verdict.held")} · ${words}`;
}

/**
 * What the finished job leaves the clerk with. Exported as a pure function so
 * the completed state is provable as data — a mutation's result never survives
 * a static render.
 */
export function printSetOutcome(
  job: JobRecord,
  t: Translator,
): { message: string; ok: boolean; href: string | null } {
  if (job.status !== "succeeded") {
    // DEF-TEN-9190 follow-up (PO 2026-10-02 item 7): the server's plain reason
    // when it wrote one — the print set is published through the same export
    // store as a list export, so the same reader decides.
    const reason = exportFailureReason(job);
    return {
      message:
        reason === null ? t("billing.print.failed") : t("billing.print.failedBecause", { reason }),
      ok: false,
      href: null,
    };
  }
  const link = job.result_link;
  if (link === null || link === "") {
    // A job that succeeded and reported no file still says so. The sentence
    // never promises a download the anchor cannot deliver.
    return { message: t("billing.print.readyNoFile"), ok: true, href: null };
  }
  return { message: t("billing.print.ready"), ok: true, href: serverLinkHref(link) };
}

/**
 * The server's own statements about what this hand-over is NOT.
 *
 * Exported as its own pure component for the reason `ExportNotice` is: a panel
 * that only appears once a query has resolved is unreachable by a static
 * render, so a test asserting it through the page would be asserting a
 * skeleton. This is the check that can actually fail.
 *
 * ⚠ **IT WRITES NONE OF ITS OWN COPY AND EDITS NONE OF THE SERVER'S.** These
 * sentences are the rule reaching a person — no address here was CASS-certified,
 * NCOA-processed or barcoded — and a screen that summarised them would be
 * deciding which parts of that a mail house needs to know.
 *
 * ⚠ **CLOSED BY DEFAULT SINCE 2026-09-15** (B14 rule 32 — a stated absence is a
 * `<details>` closed by default). The drawn group 3 is two short rows; these
 * four paragraphs are the same statements at the vendor's own length, and they
 * stay one click away rather than filling the foot of the screen.
 */
export function PrintSetNotes(props: { notes: PrintSetUnavailable[]; title: string }) {
  return (
    <details className="mt-3" data-print-notes="">
      <summary className="cursor-pointer text-sm font-medium">{props.title}</summary>
      <ul className="m-0 mt-2 flex list-disc flex-col gap-2 pl-5">
        {props.notes.map((note) => (
          <li key={note.code} className="max-w-measure text-sm">
            {note.detail}
          </li>
        ))}
      </ul>
    </details>
  );
}

/** One drawn label/value row of group 3, and of the two read-only fields in
 *  group 1. A FACT, never a control — which is why it is not an input. */
function FactRow(props: { label: string; value: string; testId: string }) {
  return (
    <div className="flex flex-col gap-0.5" data-print-fact={props.testId}>
      <span className="text-sm font-medium">{props.label}</span>
      <span className="text-sm text-[color-mix(in_srgb,var(--color-text)_70%,transparent)]">
        {props.value}
      </span>
    </div>
  );
}

/** A numbered group heading, the way the blueprint draws all three. */
function GroupHead(props: { index: number; title: string }) {
  return (
    <h3 className="m-0 flex items-baseline gap-2">
      <span className="text-sm text-[color-mix(in_srgb,var(--color-text)_55%,transparent)]">
        {props.index}
      </span>
      <span>{props.title}</span>
    </h3>
  );
}

/**
 * §08 screen 28's six drawn columns — BILL · ACCOUNT · PERIOD · AMOUNT · PAGES
 * · WILL IT PRINT.
 *
 * ⚠ **NO COLUMN IS SORTABLE AND NONE IS DRAWN THAT WAY.** The archive, the
 * manifest and the vendor's stack are all in bill-number order so a re-run is
 * diffable; a clerk sorting this list by amount would be looking at an order
 * the hand-over will never be in.
 *
 * ⚠ **THE BILL NUMBER, NEVER THE ROW ID** (B14 rule 31). `id` keys the row and
 * is rendered by nothing; a bill that has no number at all is held for exactly
 * that reason and its cell says so with a dash.
 */
export function printBillsTableConfig(
  t: Translator,
  regional: { timeZone: string; dateFormat: RegionalDateFormat },
  locale: string | undefined,
  tenantPath?: (path: string) => string,
): TableConfig<PrintBillRow> {
  return {
    screenId: "BIL-S28",
    getRowId: (row) => row.id,
    defaultSort: { sort: "invoice_no", dir: "asc" },
    searchFields: ["invoice_no", "account_no", "customer_name", "address"],
    searchPlaceholder: "billing.print.searchPlaceholder",
    columns: [
      {
        key: "invoice_no",
        label: t("billing.print.col.bill"),
        identity: true,
        // Record links (PO 2026-10-19): the bill number opens the bill.
        cell: (row) =>
          row.invoice_no === null ? (
            "—"
          ) : tenantPath === undefined ? (
            row.invoice_no
          ) : (
            <InlineLinkTo to={tenantPath(billDetailPath(row.id))}>{row.invoice_no}</InlineLinkTo>
          ),
      },
      {
        key: "account",
        label: t("billing.print.col.account"),
        // ⚠ **ONE LINE, AS DRAWN — `100377 · Ridge Coffee Co.`** A stacked pair
        // reads the same and sets the height of every row in a fifty-row table,
        // which is the cell-height trap `tableTypes` warns about in capitals.
        cell: (row) => (
          <span className="whitespace-nowrap">
            {row.account_no === null ? (
              "—"
            ) : tenantPath !== undefined && row.account_id !== undefined ? (
              <InlineLinkTo to={tenantPath(accountDetailPath(row.account_id))}>
                {row.account_no}
              </InlineLinkTo>
            ) : (
              row.account_no
            )}
            {row.customer_name === null || row.customer_name === "" ? null : (
              <span className="text-[color-mix(in_srgb,var(--color-text)_62%,transparent)]">
                {` · ${row.customer_name}`}
              </span>
            )}
          </span>
        ),
      },
      {
        key: "period",
        label: t("billing.print.col.period"),
        cell: (row) =>
          row.period_start === null || row.period_end === null ? (
            "—"
          ) : (
            <span className="whitespace-nowrap">
              <DateCell
                value={row.period_start}
                timeZone={regional.timeZone}
                dateFormat={regional.dateFormat}
              />
              {" – "}
              <DateCell
                value={row.period_end}
                timeZone={regional.timeZone}
                dateFormat={regional.dateFormat}
              />
            </span>
          ),
      },
      {
        key: "total",
        label: t("billing.print.col.amount"),
        numeric: true,
        // ⚠ **A FIGURE WITHOUT ITS CURRENCY IS NOT A FIGURE** (CLAUDE.md hard
        // rule 2 — money keeps its `CHAR(3)` partner, stored to 4 decimals and
        // DISPLAYED at 2, which is what MoneyCell does and this screen must
        // never do for itself).
        cell: (row) =>
          row.total === null ? (
            "—"
          ) : (
            <MoneyCell amount={row.total} currency={row.currency} locale={locale} />
          ),
      },
      {
        key: "pages",
        label: t("billing.print.col.pages"),
        numeric: true,
        // A held bill has no page count because nothing will draw it. A `0`
        // here would be a number a print shop could quote against.
        cell: (row) => (row.pages === null ? "—" : String(row.pages)),
      },
      {
        key: "will_print",
        label: t("billing.print.col.willPrint"),
        cell: (row) => (
          <StatusPill tone={row.will_print ? "success" : "danger"}>
            {holdText(row.hold_reason, t)}
          </StatusPill>
        ),
      },
    ],
  };
}

export function PrintBillsPage(props: PrintBillsPageProps) {
  const { t } = useTranslation();
  const translate: Translator = (key, params) => t(key, params);
  const client = props.client ?? api;
  const navigate = useNavigate();
  const tenantPath = useTenantPath();
  const cell = useAccessCell(BILLING_PERMISSION, client);
  const regional = useRegional(props);

  const [scope, setScope] = useState<PrintScope>("all");
  const [cycleId, setCycleId] = useState("");
  const [runId, setRunId] = useState<string>(ALL_RUNS);
  const [issuedFrom, setIssuedFrom] = useState("");
  const [issuedTo, setIssuedTo] = useState("");
  const [heldOnly, setHeldOnly] = useState(false);
  const [table, setTable] = useState<TableRequestState>({
    q: "",
    sort: "invoice_no",
    dir: "asc",
    page: 1,
    per: DEFAULT_PAGE_SIZE,
    filters: {},
  });
  const [outcome, setOutcome] = useState<{
    message: string;
    ok: boolean;
    href: string | null;
  } | null>(null);

  const filters = printFilters({ scope, cycleId, runId, issuedFrom, issuedTo });

  const runsQuery = useQuery({
    queryKey: ["billing", "print-set", "runs"] as const,
    queryFn: () => getBillRuns(null, client),
    retry: false,
  });

  const cyclesQuery = useQuery({
    queryKey: ["cycles", "all"] as const,
    queryFn: () => getCycles(client),
    retry: false,
  });

  const previewQuery = useQuery({
    queryKey: printSetPreviewKey(filters),
    queryFn: () => getPrintSetPreview(filters, client),
    retry: false,
  });

  const billsQuery = useQuery({
    queryKey: printSetBillsKey(filters, table, heldOnly ? "held" : ""),
    queryFn: () =>
      getPrintSetBills(
        {
          state: { q: table.q, page: table.page, per: table.per },
          filters,
          hold: heldOnly ? "held" : undefined,
        },
        client,
      ),
    retry: false,
  });

  const build = useMutation({
    mutationFn: async () => {
      const accepted = await requestPrintSet(
        {
          // ⚠ **THE SEARCH BOX IS NOT IN HERE, AND THAT IS DELIBERATE.** The
          // table's `q` narrows what is LISTED; the archive covers the scope.
          // Handing a print shop the three bills a clerk happened to search for
          // is a short run nobody asked for.
          filters,
          // BR-TEN-043: the server reads no clock on a billing path, so the
          // moment travels with the request — the same thing the release gate
          // sends as `issued_at`. Always offset-bearing.
          generated_at: new Date().toISOString(),
          background: true,
        },
        client,
      );
      // B12 r1: a 202 is a JOB, polled through the ONE helper. A 201 (the
      // server ran it inline because nothing would have run a job) is already
      // finished, so the first poll is terminal and there is one code path.
      return client.pollJob(accepted.job_id);
    },
    onSuccess: (job) => setOutcome(printSetOutcome(job, translate)),
    onError: (error: unknown) =>
      setOutcome({ message: apiErrorText(error, translate), ok: false, href: null }),
  });

  if (isDenied(cell)) {
    return (
      <PermissionDenied
        helper={t("billing.denied")}
        onBack={() => navigate(tenantPath(DASHBOARD_ROUTE))}
      />
    );
  }
  if (previewQuery.isError && isPermissionDenied(previewQuery.error)) {
    return (
      <PermissionDenied
        helper={t("billing.denied")}
        onBack={() => navigate(tenantPath(DASHBOARD_ROUTE))}
      />
    );
  }

  const preview: PrintSetPreview | undefined = previewQuery.data;
  const cycles = cyclesQuery.data ?? [];
  const chosenCycle = cycles.find((one) => one.id === cycleId) ?? null;
  // BR-SHL-025: anything other than Full renders the control disabled WITH the
  // reason. The server refuses regardless — this only saves a round trip.
  const roleReason = cell === CELL_FULL || cell === null ? null : t("billing.rbac.readOnly");
  const buildReason =
    roleReason ??
    (preview === undefined
      ? t("billing.print.blocked.notCounted")
      : preview.bill_count === 0
        ? t("billing.print.blocked.noBills")
        : preview.over_ceiling
          ? t("billing.print.blocked.overCeiling", { max: preview.max_bills })
          : null);

  const scopeLine = [
    scope === "cycle" && chosenCycle !== null
      ? cycleScopeLabel(chosenCycle, translate)
      : t(scope === "run" ? "billing.print.scope.run" : "billing.print.scope.all"),
    outcome !== null && outcome.ok
      ? t("billing.print.head.generated")
      : t("billing.print.head.notGenerated"),
  ].join(" · ");

  /** The four drawn tiles. Every value is the SERVER's forecast — a tile this
   *  screen computed would be a second opinion about what will print. */
  const kpis: KpiTile[] = [
    {
      id: "will-print",
      label: t("billing.print.tile.willPrint"),
      value: preview?.will_print ?? "—",
      detail:
        preview === undefined ? undefined : estimateText(preview.estimated_seconds, translate),
    },
    {
      id: "held-back",
      label: t("billing.print.tile.heldBack"),
      value: preview?.held_back ?? "—",
      detail:
        preview === undefined
          ? undefined
          : // FALSE is *"the address question could not be asked"*, which is not
            // the same statement as *"nothing is held"* (BR-SHL-020).
            !preview.held_reasons_complete
            ? t("billing.print.tile.addressesUnread")
            : preview.held_back === 0
              ? t("billing.print.tile.noneHeld")
              : t("billing.print.tile.eachWithReason"),
    },
    {
      id: "pages",
      label: t("billing.print.tile.pages"),
      value: preview === undefined ? "—" : t("billing.print.tile.about", { pages: preview.pages }),
      detail:
        preview === undefined
          ? undefined
          : t("billing.print.tile.pagesPerBill", { pages: preview.pages_per_bill }),
    },
    {
      id: "in-period",
      label: t("billing.print.tile.inPeriod"),
      value: preview?.bill_count ?? "—",
      detail:
        preview === undefined
          ? undefined
          : t("billing.print.tile.adds", {
              printing: preview.will_print,
              held: preview.held_back,
            }),
    },
  ];

  return (
    <div className="px-4 pt-6 pb-8">
      {/* ⚠ **THIS SCREEN IS THE BILLING PAGE'S SEVENTH TAB FROM 2026-09-14**
          (PO ruling 2026-09-12 #10, verbatim: *"We will need Print bills as tab
          at Billing level"*), so it carries the Billing strip with `print`
          selected — exactly the way `BillRunWizard` carries it for `Run bills`.

          A tab that navigates OUT of its own strip is a one-way door: the clerk
          arrives somewhere with no way back to the other six except the browser
          button. `backTo` STAYS beside it — the drawing keeps both, and the
          back arrow is what names where this screen sits. */}
      <PageHeader
        title={t("billing.print.title")}
        backTo={{ to: tenantPath(BILLING_ROUTE), label: t("billing.title") }}
        tabs={BILLING_TABS.map((tab) => ({ id: tab.id, label: t(tab.labelKey) }))}
        activeTabId="print"
        tabsLabel={t("billing.tabsLabel")}
        onTabSelect={(tab) =>
          navigate(
            tenantPath(tab.id === BILLING_TAB_ALL ? BILLING_ROUTE : `${BILLING_ROUTE}/${tab.id}`),
          )
        }
        rollup={<span data-print-rollup="">{scopeLine}</span>}
        primaryAction={
          // ⚠ **THE DRAWN TOP-RIGHT CONTROL IS `Past print sets`, AND THIS
          // PRODUCT RECORDS NO SET AFTER IT IS HANDED OVER** — the archive is a
          // job artefact and nothing lists them by cycle. A door onto nothing is
          // the defect hard-won law 2 is about, so it is not drawn and the
          // absence is stated in group 3 rather than dressed as a button.
          // `DEF-BIL-5374` carries what recording one would take.
          <GuardedButton
            label={t("billing.print.action.build")}
            reason={buildReason}
            variant="primary"
            working={build.isPending}
            onClick={() => {
              setOutcome(null);
              build.mutate();
            }}
          />
        }
      />

      {/* ⚠ **THE TILES SIT ABOVE THE FORM, WHICH IS WHERE p148 DRAWS THEM.**
          They are the answer to *what would this print set be*, and a clerk
          reads them before deciding what to change — under the form they
          read as a result of scrolling rather than as the state of the
          screen. Found by putting the 1440px capture beside the page. */}
      <KPIStrip kpis={kpis} loading={previewQuery.isPending} />

      <Panel as="section" className="mt-4" data-print-group="what">
        <GroupHead index={1} title={t("billing.print.group.what")} />

        {/* ⚠ **TWO COLUMNS IS THE BASE RULE AND ONE IS THE NARROW OVERRIDE**,
            not the other way round: this theme is DESKTOP-FIRST and `G107`
            fails a new `md:` min-width variant. The drawing pairs the six
            fields two to a row at 1440, which is where a staff screen is
            built. */}
        <div className="mt-3 grid grid-cols-2 gap-4 max-md:grid-cols-1">
          <div className="flex flex-col gap-1">
            <label className="text-sm font-medium" htmlFor="print-scope">
              {t("billing.print.field.scope")}
            </label>
            <select
              id="print-scope"
              data-print-scope=""
              // `rounded-md`, NOT `rounded`. The bare word compiles to NOTHING
              // in this Tailwind configuration, and `routeBUtilities.test.ts`
              // caught it here — tsc, eslint and every `toContain` assertion
              // pass on a class that renders as nothing, because the class IS
              // in the DOM. ⚠ AND A BORDER THAT NAMES AN UNDECLARED CUSTOM
              // PROPERTY COMPILES AND IS THEN DROPPED BY THE BROWSER
              // (DEF-SHL-5088); the house border utility is what this asks for.
              className="rounded-md border border-field-border bg-[var(--color-surface)] px-2 py-1 text-sm"
              value={scope}
              onChange={(event) => {
                setScope(event.target.value as PrintScope);
                setHeldOnly(false);
                setTable((was) => ({ ...was, page: 1 }));
                setOutcome(null);
              }}
            >
              <option value="cycle">{t("billing.print.scope.cycle")}</option>
              <option value="run">{t("billing.print.scope.run")}</option>
              <option value="all">{t("billing.print.scope.all")}</option>
            </select>
          </div>

          <div className="flex flex-col gap-1">
            <label className="text-sm font-medium" htmlFor="print-cycle">
              {t("billing.print.field.cycle")}
            </label>
            <select
              id="print-cycle"
              data-print-cycle=""
              className="rounded-md border border-field-border bg-[var(--color-surface)] px-2 py-1 text-sm"
              value={cycleId}
              disabled={scope !== "cycle"}
              onChange={(event) => {
                setCycleId(event.target.value);
                setHeldOnly(false);
                setTable((was) => ({ ...was, page: 1 }));
                setOutcome(null);
              }}
            >
              <option value="">{t("billing.print.cycle.choose")}</option>
              {cycles.map((cycle) => (
                <option key={cycle.id} value={cycle.id}>
                  {cycleScopeLabel(cycle, translate)}
                </option>
              ))}
            </select>
          </div>

          {/* ⚠ **DRAWN AS `Period from` / `Period to` AND BUILT AS THE ISSUE
              DATE, WITH THE LABELS CHANGED TO MATCH WHAT IS FILTERED.** The
              server's window is `issued_from`/`issued_to` — the day the bill was
              ISSUED — and a bill's service period is a different pair of dates
              it does not filter on. A control labelled *Period* that narrows by
              issue date answers *"is this customer's bill in the set"* wrongly,
              which is the one question this screen exists to answer. Recorded in
              the conformance record as divergence D3. */}
          <div className="flex flex-col gap-1">
            <label className="text-sm font-medium" htmlFor="print-issued-from">
              {t("billing.print.field.issuedFrom")}
            </label>
            <input
              id="print-issued-from"
              data-print-issued-from=""
              type="date"
              className="rounded-md border border-field-border bg-[var(--color-surface)] px-2 py-1 text-sm"
              value={issuedFrom}
              onChange={(event) => {
                setIssuedFrom(event.target.value);
                setHeldOnly(false);
                setTable((was) => ({ ...was, page: 1 }));
                setOutcome(null);
              }}
            />
          </div>

          <div className="flex flex-col gap-1">
            <label className="text-sm font-medium" htmlFor="print-issued-to">
              {t("billing.print.field.issuedTo")}
            </label>
            <input
              id="print-issued-to"
              data-print-issued-to=""
              type="date"
              className="rounded-md border border-field-border bg-[var(--color-surface)] px-2 py-1 text-sm"
              value={issuedTo}
              onChange={(event) => {
                setIssuedTo(event.target.value);
                setHeldOnly(false);
                setTable((was) => ({ ...was, page: 1 }));
                setOutcome(null);
              }}
            />
          </div>

          {/* ⚠ **TWO FACTS WHERE THE DRAWING DRAWS TWO PICKERS, AND BOTH WOULD
              HAVE BEEN DEAD CONTROLS.** One manifest format is registered, so a
              picker is a control with a single option — content a clerk reads
              for no decision (B14 rule 32), which is what the server's own note
              has said since the registry was written. And a bill's LAYOUT is
              pinned at issue for ever (BR-BIL-026): a reprint renders the
              version that was issued, so offering a choice would promise
              something the renderer refuses. Both are still SHOWN, because what
              the vendor receives is worth knowing before it is handed over. */}
          <FactRow
            label={t("billing.print.field.manifest")}
            value={t("billing.print.manifest.value", {
              columns: preview?.manifest_columns.length ?? 0,
            })}
            testId="manifest"
          />
          <FactRow
            label={t("billing.print.field.layout")}
            value={t("billing.print.layout.value")}
            testId="layout"
          />
        </div>

        <p className="m-0 mt-2 text-sm text-[color-mix(in_srgb,var(--color-text)_65%,transparent)]">
          {t("billing.print.manifest.oneFormat")}
        </p>

        {/* The drawing's shortcut row. It writes the SAME scope the picker
            above writes, so the form can never hold two answers at once. */}
        <div className="mt-3 flex flex-wrap items-center gap-2">
          <span className="text-sm">{t("billing.print.scope.orBy")}</span>
          <label className="sr-only" htmlFor="print-run">
            {t("billing.print.scope.run")}
          </label>
          <select
            id="print-run"
            data-print-run=""
            className="rounded-md border border-field-border bg-[var(--color-surface)] px-2 py-1 text-sm"
            value={runId}
            onChange={(event) => {
              setRunId(event.target.value);
              setScope(event.target.value === ALL_RUNS ? "all" : "run");
              setHeldOnly(false);
              setTable((was) => ({ ...was, page: 1 }));
              setOutcome(null);
            }}
          >
            <option value={ALL_RUNS}>{t("billing.print.scope.run")}</option>
            {(runsQuery.data ?? []).map((run) => (
              <option key={run.id} value={run.id}>
                {runOptionLabel(run, translate)}
              </option>
            ))}
          </select>
          <Button
            variant="secondary"
            size="sm"
            onClick={() => {
              setScope("all");
              setRunId(ALL_RUNS);
              setHeldOnly(false);
              setTable((was) => ({ ...was, page: 1 }));
              setOutcome(null);
            }}
          >
            {t("billing.print.scope.all")}
          </Button>
        </div>
      </Panel>

      <Panel as="section" className="mt-4" data-print-group="bills">
        <GroupHead index={2} title={t("billing.print.group.bills")} />
        <p className="m-0 mt-1 text-sm text-[color-mix(in_srgb,var(--color-text)_70%,transparent)]">
          {t("billing.print.searchFirst")}
        </p>

        <div className="mt-3">
          <DataTable<PrintBillRow>
            config={printBillsTableConfig(translate, regional, props.locale, tenantPath)}
            state={table}
            onStateChange={setTable}
            rows={billsQuery.data?.rows ?? []}
            totalRows={billsQuery.data?.total ?? null}
            loading={billsQuery.isPending}
            error={
              billsQuery.isError
                ? {
                    reason: apiErrorText(billsQuery.error, translate),
                    onRetry: () => void billsQuery.refetch(),
                  }
                : null
            }
            // ⚠ **NO CTA.** Nothing a clerk does on this screen CREATES a bill —
            // a bill run does — so an empty state offering a button would be a
            // door onto the wrong screen (`DEF-MET-4764`'s clause).
            empty={{
              title: t("billing.print.empty.title"),
              helper: t("billing.print.empty.helper"),
            }}
          />
        </div>

        {/* The drawn door. It narrows THIS table rather than opening a second
            screen: the held-back list with its eight named reasons is blueprint
            screen 28.1 and is not built (`DEF-BIL-5375`), and a door onto a
            screen that does not exist is the defect hard-won law 2 is about. */}
        <div className="mt-3 flex flex-wrap items-center gap-2">
          <Button
            variant="secondary"
            size="sm"
            data-print-held-door=""
            onClick={() => {
              setHeldOnly((was) => !was);
              setTable((was) => ({ ...was, page: 1 }));
            }}
          >
            {heldOnly
              ? t("billing.print.held.showAll")
              : t("billing.print.held.see", { count: preview?.held_back ?? 0 })}
          </Button>
          <span className="text-sm text-[color-mix(in_srgb,var(--color-text)_65%,transparent)]">
            {t("billing.print.held.alsoInArchive")}
          </span>
        </div>
      </Panel>

      {previewQuery.isError ? (
        <Panel role="alert" className="mt-4">
          <h3>{t("billing.print.errorTitle")}</h3>
          <p className="m-0 max-w-measure text-base">
            {apiErrorText(previewQuery.error, translate)}
          </p>
        </Panel>
      ) : preview === undefined ? (
        <LoadingSkeleton variant="card" rows={3} />
      ) : (
        <Panel as="section" className="mt-4" data-print-group="claims">
          <GroupHead index={3} title={t("billing.print.group.claims")} />
          <div className="mt-3 flex flex-col gap-3">
            <FactRow
              label={t("billing.print.claim.addresses")}
              value={t("billing.print.claim.addressesValue")}
              testId="addresses"
            />
            <FactRow
              label={t("billing.print.claim.screen")}
              value={t("billing.print.claim.screenValue")}
              testId="screen"
            />
            <FactRow
              label={t("billing.print.claim.pastSets")}
              value={t("billing.print.claim.pastSetsValue")}
              testId="past-sets"
            />
          </div>

          {/* BR-NOT-029 clause (c) reaching a person. Rendered from the
              SERVER's own sentences, so a rule change lands here without a
              frontend commit. */}
          <PrintSetNotes notes={preview.unavailable} title={t("billing.print.notesTitle")} />
        </Panel>
      )}

      {/* The drawn footer bar: what pressing the button does, beside the button
          that does it. The primary action is ALSO in the page header, which is
          this product's one-primary-action rule (B14) — the bar restates the
          fact, not the control. */}
      <p className="m-0 mt-4 text-sm text-[color-mix(in_srgb,var(--color-text)_70%,transparent)]">
        {t("billing.print.footer.helper")}
      </p>

      {build.isPending && (
        <p className="m-0 mt-4 max-w-measure text-base" role="status" data-print-working="">
          {t("billing.print.working")}
        </p>
      )}

      {outcome !== null && !build.isPending && (
        <p
          className={
            outcome.ok
              ? "m-0 mt-4 max-w-measure text-base"
              : "m-0 mt-4 max-w-measure border-l-2 border-l-danger-500 bg-danger-100 px-2 py-1 text-base text-danger-700"
          }
          role={outcome.ok ? "status" : "alert"}
          data-print-outcome={outcome.ok ? "ready" : "failed"}
        >
          {outcome.message}
          {outcome.href !== null && (
            <>
              {" "}
              {/* The server's own `result_link`, followed as a plain same-origin
                  navigation so the session cookie rides along and the server's
                  Content-Disposition names the file. The identical posture the
                  list export takes, and for the same reason: a fetch-then-blob
                  would put the whole archive in the tab's memory. */}
              {/* A bare `<a>` and not `InlineLinkAnchor`, for one reason: that
                  component's prop type carries no `download`, and the attribute
                  is the whole point here.
                  `features/exports/ListExportButton.tsx` writes the identical
                  anchor for the identical route. */}
              <a className="font-semibold text-accent-700" href={outcome.href} download>
                {t("billing.print.download")}
              </a>
            </>
          )}
        </p>
      )}
    </div>
  );
}

// ── Lifecycle ─────────────────────────────────────────────
// packet: CR-053 task 13 (12-governance/11-change-requests.md) + BR-NOT-029
//         (04-docs/05-modules/10-notifications/02-business-rules.md) + B14
//         (04-docs/02-decisions/14-ui-conventions.md, rules 21/31/32/33/37/41)
//         + blueprint screen 28, p147–p150, read as images
// generated: 2026-08-31 by the CR-053 W4 print-bills lane
// redrawn:   2026-09-15 by the CR-101-BRC03 lane J (DEF-BIL-5354)
// checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-09)
// gates: tsc✔ eslint✔ vitest (PrintBillsPage.test.tsx + PrintBillsPage.dom
//         .test.tsx) · run_gates✔ against the tip's own baseline · WALKED IN A
//         BROWSER at 1440 and 1280 against the page image (B14 rule 42).
// exceptions: (1) THE PERIOD PICKER FILTERS THE ISSUE DATE and its labels say
//         so — the server's window is `issued_from`/`issued_to` and a bill's
//         service period is not filterable anywhere.
//         (2) NO STATUS, ROUTE OR SERVICE FILTER. A print set is issued and
//         paid bills always (`print_set.PRINTABLE_STATUSES`) so a status
//         control would offer a narrowing the server overrides; route and
//         service are in no list's filter vocabulary, and
//         `test_cr101_print_bills.py` goes RED the day either arrives.
//         (3) MANIFEST FORMAT AND BILL LAYOUT ARE FACTS, NOT PICKERS — one
//         format is registered (B14 rule 32) and a bill's layout is pinned at
//         issue (BR-BIL-026).
//         (4) IT WRITES NOTHING ABOUT AN ADDRESS — no form, no field, no save.
//         An address moves when the account holder says so, on the account.
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
