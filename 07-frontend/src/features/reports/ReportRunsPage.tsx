// ── Trace ──────────────────────────────────────────────
// Change:  CR-142-BRC07 — the Reports Build Brief, Phase 3 `P3.2` (screen
//          `5·1`) and `P3.5`. Drawing p39, read as an IMAGE per B14 rule 42:
//          the column order, the toolbar, the pager and the retention line are
//          all taken from that page and not from a task summary.
// Rules:   B14 rule 44 (the drawing says WHAT and HOW ARRANGED; our UI
//          standard says how it is BUILT and wins) · rule 43 (component, not
//          inline) · rule 40 (page-head title 32px — `PageHeader` owns it) ·
//          rule 33 (LABEL ≤ 3 words · FACT ≤ 6 · RATIONALE zero) · rule 31 (no
//          database id is the visible value of a field) · rule 21 (Tailwind
//          only) · NFR-3 (server pagination) · BR-REP-018 (3-day retention) ·
//          BR-SHL-011 (the URL grammar)
// Tests:   07-frontend/src/features/reports/runHistory.dom.test.tsx
// Impacts: App.tsx (the `/reports/history` route stops being a placeholder) ·
//          ReportsTabs.tsx · RunDialog.tsx · api/runHistoryEndpoints.ts
// ───────────────────────────────────────────────────────
//
// SCREEN `5·1` — *"the cheapest screen in the plan and the one that closes a
// live broken promise"* (p39's own subtitle).
//
// ════════════════════════════════════════════════════════════════════════════
// THE SEVEN COLUMNS ARE THE DRAWING'S, IN THE DRAWING'S ORDER
// ════════════════════════════════════════════════════════════════════════════
// p39: **RAN · REPORT · STARTED BY · PARAMETERS · STATUS · ROWS · FILE**. The
// task summary that sent this lane here said *"status, who, when and the
// file"*, which is four of the seven and in none of these positions — the
// brief's own warning that a task line is an INDEX and the drawing is the
// specification.
//
// ⚠ **`ROWS` IS RIGHT-ALIGNED AND `FILE` IS NOT, AND BOTH ARE THE DRAWING'S.**
// A count is a number and reads down its last digit; the file cell is a
// control. The kit's `align` is how that gets built (rule 44).
//
// ════════════════════════════════════════════════════════════════════════════
// THE FILE CELL — THE WHOLE POINT OF THE SCREEN
// ════════════════════════════════════════════════════════════════════════════
// A download control is drawn **if and only if the server sent an address**.
// On p39 the `Expired` row's FILE cell is an em-dash and the `Failed` row's is
// too. Drawing a button there would be the same defect as the toast this phase
// exists to fix — a live control pointing at nothing — and the ruling this
// lane carries says so in as many words: *"Never draw a download control over
// a file that is not there."*
//
// ⚠ **THE SERVER DECIDES, NOT THE STATUS STRING.** The cell tests
// `run.file !== null` rather than `status === "ready"`. They agree today, and
// the day they stop agreeing it is because the server found no file — which is
// exactly the case where the control must not be drawn. A cell that re-derived
// the answer from the status would be a second opinion about a file this
// screen cannot see.
//
// ════════════════════════════════════════════════════════════════════════════
// THE RETENTION LINE, AND WHY THERE IS ONE
// ════════════════════════════════════════════════════════════════════════════
// p39 note ⑦ draws *"Files are kept for 3 days."* under the table and labels it
// **"Retention · six words, a fact not a rationale · B14 rule 33"**. Six words
// it is. Rule 33 puts RATIONALE at zero words on screen — *why* the product
// keeps them three days, or what happens to the audit row behind a correction
// — and this is not that: it is a FACT about what the screen is showing, in
// the six words rule 33 allows one. It claims no permanence and explains no
// policy.
import { useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import { Link, useNavigate, useParams, useSearchParams } from "react-router-dom";

import { serverLinkHref } from "@/api/apiHref";
import { api } from "@/api/client";
import type { ApiClient } from "@/api/client";
import type { ReportRun } from "@/api/runHistoryEndpoints";
import { getReportRuns } from "@/api/runHistoryEndpoints";
import { DataTable } from "@/components/DataTable";
import { FilterBar } from "@/components/FilterBar";
// ⚠ **THE KIT'S GLYPH, NOT A HAND-DRAWN ONE.** B14 rule 15 keeps the icon
// vocabulary in `components/icons.tsx` and nowhere else — DEF-348 is where the
// same pencil existed four times under two names, and `G37` refused the inline
// `<svg>` this file drew first.
import { DownloadIcon, EyeIcon } from "@/components/icons";
import { PageHeader } from "@/components/PageHeader";
import { RowActionLink, RowActions } from "@/components/RowActions";
import { getReportLibrary } from "@/api/reportsEndpoints";
import { StatusPill } from "@/components/StatusPill";
import type { StatusTone } from "@/components/StatusPill";
import { defaultRequestState } from "@/components/tableTypes";
import type { TableConfig, TableRequestState } from "@/components/tableTypes";

import type { Translator } from "@/features/tenancy/settingsShared";

import { HISTORY_ROUTE, ReportsTabs } from "./ReportsTabs";
import { RetentionNote } from "./RetentionNote";
import { RunDialog } from "./RunDialog";
import { RunParameterSummary } from "./RunParameterSummary";
import { reportLibraryQueryKey, targetFor } from "./ReportLibraryPage";
import { queryFromRunParams, searchFrom } from "./ReportViewerPage";
import { viewerRouteFor } from "./reportsShared";

/** The drawing's five statuses → the kit's six semantic tones (A12).
 *
 * ⚠ **STATUS MEANING, NEVER DECORATION.** `expired` is `muted` because
 * `muted` is the kit's *finished, and nothing is owed*; it is not "the grey
 * one". `queued` is `neutral` — nothing has happened yet — which is the same
 * pale/solid split the account statuses use. */
const TONES: Record<ReportRun["status"], StatusTone> = {
  queued: "neutral",
  running: "info",
  ready: "success",
  failed: "danger",
  expired: "muted",
};

export function ReportRunsPage(props: { client?: ApiClient }) {
  const { t } = useTranslation();
  const client = props.client ?? api;
  const [searchParams, setSearchParams] = useSearchParams();
  const { tenant, runId } = useParams();
  const navigate = useNavigate();
  // ⚠ **TENANT-SCOPED, AND THE MISSING-TENANT CASE IS NOT PAPERED OVER.** A
  // component mounted without `/:tenant` would otherwise build `//reports/…`,
  // a protocol-relative URL to another host that reads as a perfectly good
  // string to `toContain` — the fixture fault CLAUDE.md records under
  // hard-won law 2. The tests mount under the real `/:tenant/reports` pattern.
  const historyBase = `/${tenant ?? ""}${HISTORY_ROUTE}`;

  // BR-SHL-011 — the request state lives in the URL, so a bookmark opens on the
  // same page, search and filters. The same posture as the 2·1 viewer.
  const query = {
    q: searchParams.get("q") ?? "",
    report: searchParams.get("f.report") ?? "",
    status: searchParams.get("f.status") ?? "",
    page: Math.max(1, Number(searchParams.get("page") ?? 1) || 1),
  };

  const runs = useQuery({
    queryKey: ["report-runs", query.q, query.report, query.status, query.page],
    queryFn: () =>
      getReportRuns(
        {
          q: query.q,
          report: query.report || undefined,
          status: query.status || undefined,
          page: query.page,
        },
        client,
      ),
    retry: false,
    // The table stays on screen while a filter changes, rather than blanking to
    // a skeleton and back — the 2·1 viewer's own reason.
    placeholderData: (previous) => previous,
  });
  const page = runs.data;

  // ── `CR-179-BRC10` · OPEN IN REPORT (PO 2026-10-12) ────────────────────
  // ⚠ **ONLY WHERE THE REPORT OPENS IN THE STANDARD VIEWER.** The same read
  // the library and the viewer already make, and the library's own
  // `targetFor` decides it — a run of a report this deployment cannot open
  // gets no door rather than a door onto a refusal. Until the read answers,
  // no row has one.
  const library = useQuery({
    queryKey: reportLibraryQueryKey,
    queryFn: () => getReportLibrary(client),
    retry: false,
  });
  const viewable = useMemo(() => {
    const keys = new Set<string>();
    for (const card of library.data?.cards ?? []) {
      if (targetFor(card) === viewerRouteFor(card.key)) keys.add(card.key);
    }
    return keys;
  }, [library.data]);

  const config = useMemo<TableConfig<ReportRun>>(
    () => ({
      screenId: "5.1",
      getRowId: (row) => row.id,
      searchFields: ["report", "filters"],
      searchPlaceholder: "reports.history.search",
      defaultSort: { sort: "ran_at", dir: "desc" },
      filters: [
        {
          name: "report",
          label: t("reports.history.filter.report"),
          options: (page?.body.reports ?? []).map((key) => ({
            value: key,
            // The report's NAME from the catalogue, in the clerk's language —
            // never the API key, which is a contract and not display copy.
            label: t(`reports.card.${key}.name`, { defaultValue: key }),
          })),
        },
        {
          name: "status",
          label: t("reports.history.filter.status"),
          options: (page?.body.statuses ?? []).map((value) => ({
            value,
            label: t(`reports.history.status.${value}`),
          })),
        },
      ],
      // ⚠ **THE ORDER IS p39's AND IS NOT ALPHABETICAL, NOT ARBITRARY.** It
      // reads as a sentence: when · what · who · with what · how it went · how
      // big · and here it is.
      columns: [
        {
          key: "ran_at",
          label: t("reports.history.column.ran"),
          sortable: true,
          identity: true,
          // ⚠ **THE REAL LINK, AND IT IS WHAT `Tab` REACHES.** `rowHref` below
          // widens the MOUSE target to the rest of the row; the kit's own
          // docstring calls a list that declares `rowHref` with no identity
          // link *"the shape to refuse, not to ship"*.
          cell: (row) => (
            <Link to={`${historyBase}/${row.id}`} data-run-open={row.id}>
              {formatRan(row.ran_at, t)}
            </Link>
          ),
        },
        {
          key: "report",
          label: t("reports.history.column.report"),
          locked: true,
          cell: (row) => (
            <strong>{t(`reports.card.${row.report}.name`, { defaultValue: row.report })}</strong>
          ),
        },
        {
          key: "started_by",
          label: t("reports.history.column.startedBy"),
          // p39 ④: *"a person's name, or the word Schedule"*. The server sends
          // a name or `null`; `null` is a run nobody started by hand, and the
          // word for that is the catalogue's, in eleven languages.
          cell: (row) => <>{row.started_by ?? t("reports.history.schedule")}</>,
        },
        {
          key: "filters",
          label: t("reports.history.column.parameters"),
          // B14 rule 31: a report that stores ids in its run (Rate Impact's
          // `rows`) serves the run IN WORDS, and that is what is drawn.
          cell: (row) =>
            row.summary !== undefined && row.summary !== null && row.summary.length > 0 ? (
              <RunParameterSummary lines={row.summary} t={t} />
            ) : (
              <>{describeFilters(row.filters)}</>
            ),
        },
        {
          key: "status",
          label: t("reports.history.column.status"),
          locked: true,
          cell: (row) => (
            <StatusPill tone={TONES[row.status]}>
              {row.status === "running"
                ? t("reports.history.status.runningAt", { percent: percentOf(row) })
                : t(`reports.history.status.${row.status}`)}
            </StatusPill>
          ),
        },
        {
          key: "rows",
          label: t("reports.history.column.rows"),
          // ⚠ **THE DRAWING RIGHT-ALIGNS THIS COLUMN AND THE KIT HAS NO WAY TO
          // SAY SO.** `TableColumnConfig` is `{key · label · sortable ·
          // identity · locked · cell}` — there is no `align`, and B14 rule 44
          // says our standard decides how a screen is BUILT even where the
          // drawing shows something else. Adding an alignment prop is a change
          // to one component and every table in the product, which is a kit
          // decision and not a lane's. DIVERGENCE FROM p39, REPORTED.
          cell: (row) => <>{row.rows === null ? EM_DASH : row.rows.toLocaleString()}</>,
        },
        {
          key: "open",
          label: t("reports.history.column.open"),
          // The run's parameters back into the viewer's own address: declared
          // inputs as `in.<param>`, fixed filters as `searchFrom` writes them.
          cell: (row) => {
            if (!viewable.has(row.report)) return <>{EM_DASH}</>;
            const search = searchFrom(queryFromRunParams(row.filters)).toString();
            return (
              <span data-run-report={row.id} className="contents">
                <RowActions>
                  <RowActionLink
                    label={t("reports.history.openInReport")}
                    icon={<EyeIcon />}
                    to={`/${tenant ?? ""}${viewerRouteFor(row.report)}${search === "" ? "" : `?${search}`}`}
                  />
                </RowActions>
              </span>
            );
          },
        },
        {
          key: "file",
          label: t("reports.history.column.file"),
          cell: (row) =>
            // ⚠ **NO ADDRESS, NO CONTROL.** See this file's header.
            row.file === null ? (
              <>{EM_DASH}</>
            ) : (
              <a
                href={serverLinkHref(row.file)}
                download
                data-run-file={row.id}
                className="inline-flex h-9 w-9 items-center justify-center text-accent"
                aria-label={t("download.csv")}
                title={t("download.csv")}
              >
                <DownloadIcon />
              </a>
            ),
        },
      ],
      // p39 WRITE SURFACES: *"Detail 5·2 · Add NOTHING · Edit NOTHING — a run
      // is a historical fact and is never editable"*. So the row opens a
      // read-only dialog and nothing on this screen writes.
      //
      // ⚠ **`5·2` IS AN ADDRESS AND NOT A PIECE OF LOCAL STATE.** The drawing
      // shows it as a dialog over `5·1`, and the kit's row target is a URL
      // (`rowHref`) precisely because a `<tr>` is not focusable — a row whose
      // only affordance is a click is unreachable without a mouse. So the run
      // id rides in the path, the dialog opens from it, and the row a clerk
      // sends a colleague opens the same run. p43's DOORS row asks for exactly
      // that: *"A row on 5·1, and a run row inside 4·2"*.
      rowHref: (row) => `${historyBase}/${row.id}`,
    }),
    [t, page?.body.reports, page?.body.statuses, historyBase, viewable, tenant],
  );

  /** The ONE writer of this screen's URL state — the table and the filter bar
   *  both go through it, because two copies drift the moment a param is
   *  renamed and only one of them would be tested. */
  function applyState(next: TableRequestState): void {
    const params = new URLSearchParams();
    if (next.q !== "") params.set("q", next.q);
    if (next.filters.report) params.set("f.report", next.filters.report);
    if (next.filters.status) params.set("f.status", next.filters.status);
    // A filter change moves the clerk back to page one: page 4 of an unfiltered
    // list is rarely page 4 of a filtered one, and the pager would clamp
    // silently.
    if (next.page > 1) params.set("page", String(next.page));
    setSearchParams(params);
  }

  const defaults = defaultRequestState(config);
  const state: TableRequestState = {
    ...defaults,
    q: query.q,
    page: query.page,
    // ⚠ **THE SERVER NO LONGER ECHOES `per`, AND IT SHOULD NOT.** The one list
    // envelope is `{count, next, previous, results}`; page size is the KIT's
    // state, and `DataTable` derives the page count from `totalRows` and this.
    // Reading it back off the wire was part of the second envelope `G114`
    // refused.
    per: defaults.per,
    filters: {
      ...(query.report === "" ? {} : { report: query.report }),
      ...(query.status === "" ? {} : { status: query.status }),
    },
  };

  return (
    <div data-screen="5.1">
      <PageHeader kicker={t("reports.kicker")} title={t("reports.history.title")} />
      <p className="mb-6 mt-0 text-body text-neutral-600">{t("reports.history.grain")}</p>
      <ReportsTabs active="history" />
      <DataTable<ReportRun>
        config={config}
        state={state}
        onStateChange={applyState}
        // ⚠ **DECLARING `config.filters` DRAWS NOTHING ON ITS OWN, AND THAT IS
        // HARD-WON LAW 2 IN THIS FILE'S OWN HISTORY.** `DataTable` renders
        // `filterBarSlot` and never `config.filters` — the config is what a
        // screen DECLARES, the slot is what it COMPOSES. The first draft of
        // this screen declared both filters correctly, `tsc` passed, 24 DOM
        // cases passed, and the walkthrough's screenshot showed a toolbar with
        // a search box and a column chooser and **no filters at all**. Found by
        // looking at the screen, which CLAUDE.md names as the only thing that
        // finds this class (law 6).
        filterBarSlot={
          <FilterBar
            filters={config.filters ?? []}
            state={state}
            onStateChange={(next) => applyState(next)}
          />
        }
        rows={page?.rows ?? []}
        totalRows={page === undefined ? null : page.total}
        loading={runs.isLoading}
        // `DEF-SHL-6915` — A FAILED READ IS NOT AN EMPTY ONE. Without this the
        // table falls through to `ZeroResults` and tells a clerk *"No results
        // match these filters."* over a server that never answered — inviting
        // them to clear a filter that is not the problem.
        error={runs.isError ? { onRetry: () => void runs.refetch() } : null}
        empty={{
          title: t("reports.history.empty.title"),
          helper: t("reports.history.empty.helper"),
        }}
      />
      {/* p39 ⑦ — a FACT in six words (B14 rule 33), never a policy — and, for
          an admin, `P5.12`'s door to the setting that decides the number. */}
      <RetentionNote tenant={tenant ?? ""} days={page?.body.retention_days ?? null} />
      {runId === undefined ? null : (
        <RunDialog
          runId={runId}
          client={client}
          onClose={() => navigate(`${historyBase}${searchParams.size > 0 ? `?${searchParams}` : ""}`)}
          onRerun={() => {
            navigate(historyBase);
            void runs.refetch();
          }}
        />
      )}
    </div>
  );
}

const EM_DASH = "—";

/** *Today 09:02* · *Yest 17:40* · *22 Sep 09:00* — the drawing's three forms.
 *
 * ⚠ **THE THREE FORMS ARE p39's OWN ROWS, NOT AN INVENTION.** A run history is
 * read for *did last night's schedule run*, and a clerk answering that does not
 * want to subtract dates. The words come from the catalogue; only the shape is
 * decided here. */
function formatRan(iso: string | null, t: Translator): string {
  if (iso === null) return EM_DASH;
  const at = new Date(iso);
  if (Number.isNaN(at.getTime())) return EM_DASH;
  const time = at.toLocaleTimeString(undefined, { hour: "2-digit", minute: "2-digit" });
  const days = daysAgo(at);
  if (days === 0) return t("reports.history.today", { time });
  if (days === 1) return t("reports.history.yesterday", { time });
  return `${at.toLocaleDateString(undefined, { day: "numeric", month: "short" })} ${time}`;
}

function daysAgo(at: Date): number {
  const midnight = new Date();
  midnight.setHours(0, 0, 0, 0);
  return Math.floor((midnight.getTime() - at.getTime()) / 86_400_000) + (at < midnight ? 1 : 0);
}

/** The stored parameters as one short line — *09/01–09/30*, *as of 09/30*.
 *
 * ⚠ **A RUN WITH NO STORED PARAMETERS SHOWS AN EM-DASH, NOT AN EMPTY CELL.**
 * p39's `Failed` row draws exactly that. An empty cell reads as a rendering
 * fault; a dash reads as *there were none*, which is the truth. */
function describeFilters(filters: Record<string, string>): string {
  // ⚠ **A STRUCTURED VALUE IS NEVER PRINTED** (B14 rule 31). A declared table
  // input travels as ONE JSON string of ids; a report that stores one serves a
  // `summary` instead, and where it cannot (rows that no longer resolve) the
  // ids are still not a reading for a clerk.
  const entries = Object.entries(filters).filter(
    ([, value]) => value !== "" && value !== null && !/^\s*[[{]/.test(String(value)),
  );
  if (entries.length === 0) return EM_DASH;
  const from = filters.from ?? "";
  const to = filters.to ?? "";
  if (from !== "" && to !== "") return `${from} – ${to}`;
  return entries.map(([, value]) => String(value)).join(" · ");
}

function percentOf(run: ReportRun): number {
  const done = run.progress?.done ?? 0;
  const total = run.progress?.total ?? null;
  // ⚠ **A STREAM HAS NO DENOMINATOR AND THE SCREEN DOES NOT INVENT ONE.**
  // `request_list_export`'s pre-count was DELETED by `P2.4` because it built
  // the whole report twice; `record_progress` takes `total=None` and the bar
  // counts up. 0 here means *we know how many rows so far and not how many
  // there will be* — the honest number, not a guess.
  return total === null || total === 0 ? 0 : Math.round((done / total) * 100);
}

export default ReportRunsPage;

// ── Lifecycle ─────────────────────────────────────────────
// packet: CR-142-BRC07 P3.2 · P3.5 (05-prototype/09 Reports Build Brief.pdf p39 + p42-p43, read as images per B14 rule 42)
// screens: 5·1
// generated: 2026-09-27 by lane REP-P3
// checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-09)
// gates: RED PROVED FIRST — `runHistory.dom.test.tsx` was run before this file existed and reported `Cannot find module './ReportRunsPage'`; the endpoint behind it answered `422 VAL-005 {"key":"history"}` on the tip. G31: this file is listed in styles/route-b-migrated.txt in the same commit.
// exceptions: (1) the tab strip draws TWO of the drawing's four tabs — see ReportsTabs.tsx, held with a test that fires by ADDRESS when the hold expires. DIVERGENCE FROM THE DRAWING, REPORTED · (2) the drawing's `Running 62%` percentage is drawn from `progress`, which has `total: null` for a streamed export (`P2.4` deleted the pre-count), so a running row reads 0% until a total exists — REPORTED rather than faked · (3) the drawing's server-side SEARCH matches the report KEY and the stored parameters, never the translated report NAME, because no column holds the name — stated in the selector's docstring
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
