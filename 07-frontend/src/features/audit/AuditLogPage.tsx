// ── Trace ──────────────────────────────────────────────
// Story:    US-AUD-004 (S61 viewer — filter bar, table, roles) · US-AUD-005 (the row detail
//           drawer: who/what/when/entity/before/after) · US-AUD-006 (CSV export under the
//           BR-SHL-016 guards, itself audited)   Screens: S61 (entered from S8 → Security)
// Rules:    BR-AUD-002 (read-only BY CONSTRUCTION — this screen draws no mutating affordance) ·
//           BR-AUD-006 (masked values render exactly as stored; nothing here unmasks) ·
//           BR-AUD-007 (the current tenant's rows exclusively — RLS-enforced server-side) ·
//           BR-AUD-009 (System Admin + Executive; the filter vocabulary; the six columns;
//           row → drawer) · BR-AUD-013 (server pagination · 2-yr hot window · EXPLICIT archive) ·
//           BR-AUD-014 (50,000-row export cap → 422 BIZ-CAP "narrow your filters") ·
//           BR-SHL-010 (the capability row IS the table config) · BR-SHL-011 (q/sort/dir/page/
//           per/f.<name> URL grammar; an invalid value falls back, never errors) ·
//           BR-SHL-012 (the six A18 states composed from StateFrame, never re-implemented) ·
//           BR-SHL-016 (server-side export under the caller's own tenant context) ·
//           BR-SHL-033 (date fields are PICKERS; a long list is SEARCHABLE) ·
//           BR-SHL-034 (every displayed timestamp goes through the shared formatter) ·
//           BR-SHL-025 (the server enforces; hiding is convenience)
// ───────────────────────────────────────────────────────
// S61 — the tenant-scoped audit-log viewer.
//
// Three things this screen refuses to do, each for a stated reason:
//
//   1. **It never writes.** There is no edit, no delete, no annotate control
//      anywhere below — not disabled, ABSENT — because the store is append-only
//      (BR-AUD-002) and the API defines no such verb. A disabled-with-reason
//      control would imply a permission could unlock it; none can.
//
//   2. **It never guesses which window it is showing.** The server answers
//      `X-Audit-Window` / `X-Audit-Window-From`, and the banner states exactly
//      that. Widening to the archive is an EXPLICIT act (BR-AUD-013): a
//      separate control, a separate query, its own URL state.
//
//   3. **It never counts rows for the export.** The 50k cap is measured
//      server-side against the same bounded query (BR-AUD-014); an oversize
//      request comes back as 422 BIZ-CAP carrying the real count and the cap,
//      and the screen renders those numbers verbatim.
//
// Entity cells render as LABELS, not links: this app has no detail route for an
// invoice/account/asset yet, and US-AUD-005 TC-6 already rules that an entity
// without a reachable screen degrades to a labeled non-link. History never 404s.
import { useMutation, useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { useNavigate, useSearchParams } from "react-router-dom";

import { api, isApiError } from "@/api/client";
import type { ApiClient } from "@/api/client";
import {
  AUDIT_OUTCOME_ERROR,
  DIAGNOSTIC_NO_REFERENCE,
  getAuditDiagnostic,
  getAuditEntry,
  getAuditLog,
  getTenantUsers,
  isAutomationActor,
  requestAuditExport,
} from "@/api/endpoints";
import type {
  AuditDiagnostic,
  AuditDiagnosticRecord,
  AuditEntry,
  AuditFilterName,
  AuditRow,
  AuditWindowInfo,
  TenantUser,
} from "@/api/endpoints";
import { REFERENCE_STALE_MS, queryKeys } from "@/api/queryClient";
import { Button } from "@/components/Button";
import { DataTable } from "@/components/DataTable";
import { DateCell } from "@/components/DateCell";
import type { RegionalDateFormat } from "@/components/DateCell";
import { Disclosure } from "@/components/Disclosure";
import { DownloadButton } from "@/components/DownloadButton";
import {
  CheckboxField,
  DatePickerField,
  ModalShell,
  SearchSelectField,
  TextField,
} from "@/components/FormModal";
import { FailedWithRetry, LoadingSkeleton, PermissionDenied } from "@/components/StateFrame";
import { DEFAULT_PAGE_SIZE, parseTableParams, serializeTableParams } from "@/components/tableTypes";
import type { TableConfig, TableRequestState } from "@/components/tableTypes";
import { useToast } from "@/components/Toast";
import { RefusalStrip } from "@/components/Surfaces";
import { Kicker, Note } from "@/components/TextBits";
// LAW 0: "is there a file to fetch, and where?" is decided in ONE place — the
// same helper the nine list exports use. S61 keeps its own control and its own
// copy; what it does not keep is a second reading of `result_link`.
import { exportDownloadHref } from "@/features/exports/ListExportButton";
// DEF-645: the sentence, the field list and the identifier rules are the
// module's, shared with every per-entity Audit tab (BR-AUD-010).
import {
  AuditEventChanges,
  AuditEventSentenceText,
  AuditFieldList,
  auditEntityLabel,
  auditFieldSet,
  auditText,
} from "./auditEvents";
// CR-067 task B2's role gate. `ROLE_SYSTEM_ADMIN` is a CONSTANT and not a
// literal for the reason its own docstring gives: two files each spelling
// `"system_admin"` is how a role rename becomes a silent permission change.
import { ROLE_SYSTEM_ADMIN, useRegional, useTenantRole } from "@/features/metering/meteringShared";
import { apiErrorText, isPermissionDenied } from "@/features/tenancy/settingsShared";
import type { Translator } from "@/features/tenancy/settingsShared";
import { useTenantPath } from "@/routing/tenantPath";

// ── Pure pieces (provable without a browser or a network) ──────────────────

export const AUDIT_ROUTE = "/audit-log"; // the S8 Security button's target (OQ-029 CLOSED)
/**
 * US-MET-020 / US-AUD-007's data-retention view.
 *
 * ⚠ **DECLARED HERE AND NOT IN `RetentionRunsPage.tsx`, AND THE REASON COST A
 * BROWSER RUN.** That file needs `AUDIT_ROUTE` and `DASHBOARD_ROUTE` from this
 * one (its Back control and its permission-denied state), so this file
 * importing a constant back out of it made a CYCLE. Vitest and `tsc` were both
 * perfectly happy; in the bundled SPA one module evaluated first, the other's
 * export was still `undefined`, and **the audit screen rendered an empty main
 * pane** — the whole of S61 gone, not just the new link. Found by booting the
 * stack and clicking (hard-won law 6) and by nothing else.
 *
 * The rule that falls out of it: route CONSTANTS belong with the screen other
 * screens already depend on, so the arrows only ever point one way.
 */
export const RETENTION_ROUTE = "/audit-log/retention";
export const DASHBOARD_ROUTE = "/dashboard";
export const ARCHIVE_PARAM = "archive";
// BR-SHL-011's spirit: the open row is VIEW STATE, so it belongs in the URL.
// An auditor can then send "look at this entry" as a link, and a reload lands
// back on the same drawer instead of an empty list.
export const ENTRY_PARAM = "entry";

/**
 * Who acted, as a person reads it. Three answers, and the third is US-AUD-010's.
 *
 * ⚠ **THE WHOLE STORY IS IN THE MIDDLE BRANCH, SO HERE IS WHAT IT COSTS
 * WITHOUT IT.** The returned-payments runbook applies a $25 fee to 43 accounts
 * overnight — $1,075 charged while nobody is at the office. Six weeks later a
 * customer disputes theirs and a clerk opens this account's history. Before
 * US-AUD-010 this function had two answers and both were wrong for her: *System
 * job*, which she cannot tell from a bill run, an import or a bug; or a
 * colleague's name, because the automation had borrowed a staff login. It now
 * reads **"Returned payments, version 4"**, so she can look up what version 4
 * did and answer the customer properly (`BR-RBS-015`, `TC-RBS-12`).
 *
 * ⚠ **THE SENTENCE IS COMPOSED HERE AND IS NOT STORED.** The server sends the
 * name and the version as two fields precisely so this line can be written in
 * the reader's own language (B14 rule 35 — a catalogue is written in its own
 * language, not translated from English). An automation with no version draws
 * its bare name rather than inventing "version 1".
 *
 * ⚠ **NO ID IS EVER DRAWN** — B14 rule 31, and for a named automation there is
 * no user id on the row at all (BR-RBS-015).
 */
export function actorLabel(row: AuditRow, t: Translator): string {
  if (row.actor === null) {
    // BR-AUD-003: an UNNAMED system job — no user, no name. Still the honest
    // answer for a bill run, and no longer the answer for every automation.
    return t("audit.actor.system");
  }
  if (isAutomationActor(row.actor)) {
    const name = row.actor.name ?? t("audit.actor.system");
    if (row.actor.version === null) {
      return name;
    }
    return t("audit.actor.automation", { name, version: row.actor.version });
  }
  // ⚠ WAS `t("audit.actor.unknownId", { id: row.actor.id })`, whose English read
  //    "User 01a062a7-9f7d-73e6-96e4-700cba033c73" — a database id as the
  //    visible value of a field, which B14 rule 31 forbids outright (DEF-2378).
  //    A removed actor still keeps its history, which is the point; it now says
  //    so in words, and the id travels on `title` for support (see the cell).
  return row.actor.name ?? t("audit.actor.removed");
}

/**
 * The id a support engineer needs, for `title` and a data attribute — NEVER for
 * the cell's text. Null when there is nothing to carry, so the caller can leave
 * the attribute off entirely rather than write an empty one.
 */
export function supportReference(value: string | null): string | undefined {
  const text = (value ?? "").trim();
  return text === "" ? undefined : text;
}

/**
 * US-AUD-005 TC-6: an entity whose detail screen does not exist (or whose row
 * was hard-deleted) renders as a LABEL. Nothing here builds a route it cannot
 * prove exists — a dead link is worse than an honest label.
 *
 * ⚠ **IT USED TO READ `` `${row.entity_type} · ${row.entity_id}` ``, AND THE
 * PRODUCT OWNER READ THE RESULT ON A LIVE DEPLOYMENT (DEF-2378):**
 * `tenant · 01a062a7-9f7d-73e6-96e4-700cba033c73`. B14 rule 31 — *"no Databse
 * ID on screen - that is a rule"* — has no exception for "the server sent it",
 * and the comment that used to sit here ("the server's DATA, not copy, so they
 * render verbatim") is precisely the reasoning the rule overrules.
 *
 * What a person reads now is WHAT THE RECORD IS. The id has not been thrown
 * away and support has not lost it: it rides on `title` and
 * `data-audit-entity-id` on the cell below, it is still the thing the Entity ID
 * filter searches, and the drawer's *Stored record* fold shows it verbatim.
 *
 * **A NAME WOULD BE BETTER AND IS NOT AVAILABLE HERE** — see `auditEntityLabel`
 * for the check that settled it: this list is one read across every module, the
 * API serves no name, and a hard-deleted record could never resolve one.
 */
export function entityLabel(row: AuditRow, t: Translator): string {
  return auditEntityLabel(row.entity_type, t);
}

/**
 * BR-AUD-013 made readable: which window answered, and from when. `from` is an
 * instant, so it renders through the shared formatter like every other date
 * (BR-SHL-034) — this function returns the KEY and its params, never a sentence.
 */
export function windowBannerKey(window: AuditWindowInfo): string {
  return window.window === "archive" ? "audit.window.archive" : "audit.window.hot";
}

/** BR-AUD-013: the archive opens only on an explicit `archive=true`. */
export function archiveFromParams(params: URLSearchParams): boolean {
  const raw = (params.get(ARCHIVE_PARAM) ?? "").trim().toLowerCase();
  return raw === "1" || raw === "true" || raw === "yes" || raw === "on";
}

/**
 * The BR-AUD-014 refusal, rendered from the envelope's own numbers. Returns
 * null for every other failure — only the cap has "narrow your filters" advice
 * the row count actually supports.
 */
export function exportCapRefusal(error: unknown, t: Translator): string | null {
  if (!isApiError(error) || error.code !== "BIZ-CAP") {
    return null;
  }
  const rows = error.params.rows;
  const cap = error.params.cap;
  return t("audit.export.capped", {
    rows: typeof rows === "number" ? rows : "—",
    cap: typeof cap === "number" ? cap : "—",
  });
}

/**
 * BR-AUD-009's filter vocabulary as the shared table framework sees it
 * (BR-SHL-011's `f.<name>` grammar, parsed/serialized in ONE place).
 *
 * `options` is empty for every filter except the actor: the action-type CLASS
 * and MODULE dropdowns BR-AUD-009 names are properties of the US-AUD-002
 * event-code catalog, which does not exist — so those are free text over the
 * action CODE (which is what the server actually filters on) rather than an
 * invented option list. The panel below renders the right control per filter;
 * declaring them here is what puts them in the URL.
 */
export function auditTableConfig(
  t: Translator,
  actorOptions: { value: string; label: string }[],
  cells: {
    when: (row: AuditRow) => JSX.Element;
    entity: (row: AuditRow) => JSX.Element;
    actor: (row: AuditRow) => string;
    source: (row: AuditRow) => JSX.Element;
    // DEF-645: neither the action CODE nor the server's `key: value (+N more)`
    // summary is drawn any more — both cells go through the shared presenter.
    action: (row: AuditRow) => JSX.Element;
    summary: (row: AuditRow) => JSX.Element;
  },
): TableConfig<AuditRow> {
  return {
    screenId: "S61",
    columns: [
      // The six default columns of the A1 S61 addendum, in its order.
      // BR-SHL-013: When is the identity column — it can never be hidden.
      {
        key: "when",
        label: t("audit.col.when"),
        sortable: true,
        identity: true,
        cell: cells.when,
      },
      { key: "actor", label: t("audit.col.actor"), sortable: true, cell: cells.actor },
      // Still SORTED on the server's `action` (the column name is the sort
      // token, not the copy), and still drawn as a sentence.
      { key: "action", label: t("audit.col.action"), sortable: true, cell: cells.action },
      { key: "entity", label: t("audit.col.entity"), sortable: true, cell: cells.entity },
      { key: "summary", label: t("audit.col.summary"), cell: cells.summary },
      // GAP AUD-D2: no storage anchor yet, so the column is PRESENT and empty.
      // Hiding it would hide the gap (US-AUD-004 §5).
      { key: "source", label: t("audit.col.source"), cell: cells.source },
    ],
    getRowId: (row) => row.id,
    // A1 S61: no free-text search — the entity type/id filter IS the lookup
    // path. BR-SHL-010: an undeclared capability is not rendered, so omitting
    // `searchFields` is what removes the search box.
    filters: [
      { name: "actor", label: t("audit.filter.actor"), options: actorOptions },
      { name: "action", label: t("audit.filter.action"), options: [] },
      { name: "entity_type", label: t("audit.filter.entityType"), options: [] },
      { name: "entity_id", label: t("audit.filter.entityId"), options: [] },
      { name: "entity", label: t("audit.filter.entity"), options: [] },
      { name: "from", label: t("audit.filter.from"), options: [] },
      { name: "to", label: t("audit.filter.to"), options: [] },
      // CR-067 B3 / DEF-3322 — "Errors only". ⚠ **DECLARING IT HERE IS HALF THE
      // FEATURE, NOT BOOKKEEPING.** `parseTableParams` and `serializeTableParams`
      // walk THIS array, so a filter missing from it never reaches the URL and
      // never reaches the request — and the server drops an `f.<name>` it does
      // not declare rather than refusing it (BR-SHL-011). Either way the toggle
      // would come back with the whole list and read as a product with no errors
      // in it. It has no `options`, like five of the six above: it is a toggle,
      // and its only value is `error`.
      { name: "outcome", label: t("audit.filter.outcome"), options: [] },
    ],
    defaultSort: { sort: "when", dir: "desc" }, // newest first (the capability row)
  };
}

/** The request state → the wrapper's params. One translation, one place. */
export function auditParamsFrom(state: TableRequestState, archive: boolean) {
  return {
    filters: state.filters as Partial<Record<AuditFilterName, string>>,
    sort: state.sort,
    dir: state.dir,
    page: state.page,
    per: state.per,
    archive,
  };
}

/**
 * The finished export's line (BR-REP-018/IS-11): the sentence plus the file.
 *
 * Its own component so the completed state can be PROVED as markup — the
 * screen's own copy of it is mutation state, which static rendering never
 * reaches. The href is always the server's `result_link`, read through the
 * shared `exportDownloadHref`; nothing here composes a URL.
 */
export function ExportReadyLine(props: { href: string; t: Translator }) {
  return (
    <p
      className="m-0 mb-3 text-base text-[color-mix(in_srgb,var(--color-text)_75%,transparent)]"
      role="status"
    >
      {props.t("audit.export.ready", { id: "" })}{" "}
      {/* Plain same-origin navigation: the session cookie rides along and the
          server's Content-Disposition names the CSV. */}
      <a className="font-semibold text-accent-700" href={props.href} download>
        {props.t("audit.export.download")}
      </a>
    </p>
  );
}

// ── The screen ─────────────────────────────────────────────────────────────

export interface AuditLogPageProps {
  client?: ApiClient; // test seam — screens never build their own transport
  // IS-8: the tenant's TZ and date format arrive with US-SHL-013's formatting
  // service wiring. DateCell REQUIRES both, so the seed values stand in rather
  // than any hand-rolled formatting inside this screen (BR-SHL-034).
  timeZone?: string;
  dateFormat?: RegionalDateFormat;
}

export function AuditLogPage(props: AuditLogPageProps) {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const tenantPath = useTenantPath();
  const client = props.client ?? api;
  const fireToast = useToast();
  const [searchParams, setSearchParams] = useSearchParams();
  // DEF-SHL-3964 — this used to spell its own copy of the seed default, one
  // layer below the resolver. Same defect, same cure: the tenant's own setting.
  // (The first wording of this comment named a prop in backtick-quoted code and
  // G13's scanner read the COMMENT as a prop reference — ten false positives.
  // A comment that contains code-shaped text is code to anything that greps.)
  const { timeZone, dateFormat } = useRegional(props);

  const [exportNotice, setExportNotice] = useState<string | null>(null);
  // The finished export's download route (IS-11), or null while there is none.
  const [exportFile, setExportFile] = useState<string | null>(null);
  const openEntryId = searchParams.get(ENTRY_PARAM);

  // The actor picker's option list. BR-SHL-033: a tenant user list is a LONG
  // list, so it is a searchable select. `GET /users` is System-Admin-only, so
  // for an Executive this read fails and the filter degrades to a text field —
  // stated in the panel, never silently empty.
  const usersQuery = useQuery({
    queryKey: queryKeys.tenantUsers(1, DEFAULT_PAGE_SIZE),
    queryFn: () => getTenantUsers({ page: 1, per: DEFAULT_PAGE_SIZE }, client),
    staleTime: REFERENCE_STALE_MS,
    retry: false,
  });
  const actorOptions = buildActorOptions(usersQuery.data?.results, t);

  const config = auditTableConfig(t, actorOptions, {
    when: (row) => (
      // Row → drawer (the A1 S61 design's own interaction). The whole cell is
      // the affordance; there is no second, mutating one anywhere on the row.
      <button
        type="button"
        className="cursor-pointer border-none border-current bg-transparent bg-none p-0 text-left text-accent-700 [font:inherit] hover:underline focus-visible:underline"
        data-audit="open"
        aria-label={t("audit.openDrawer", { action: row.action })}
        onClick={() => openEntry(row.id)}
      >
        {/* BR-SHL-034: an instant renders in the tenant TZ through DateCell. */}
        <DateCell value={row.created_at} timeZone={timeZone} dateFormat={dateFormat} withTime />
      </button>
    ),
    actor: (row) => actorLabel(row, t),  // words only — see actorLabel (DEF-2378)
    // DEF-645 · the code became a sentence and the payload blob became a
    // readable, complete, expandable list. Both are the shared presenter's.
    action: (row) => <AuditEventSentenceText row={row} t={t} />,
    summary: (row) => <AuditEventChanges row={row} t={t} client={client} />,
    // DEF-2378 — the words are the value; the id is evidence, not copy. `title`
    // gives support the reference on hover and `data-audit-entity-id` gives a
    // support tool one to read, exactly as `data-br-ref` has carried a rule id
    // since DEF-322. Neither is text a person reads by accident.
    entity: (row) => (
      <span
        className="font-body"
        data-audit="entity"
        data-audit-entity-id={supportReference(row.entity_id)}
        title={supportReference(row.entity_id)}
      >
        {entityLabel(row, t)}
      </span>
    ),
    source: (row) => <SourceCell value={row.source} />,
  });

  const state = parseTableParams(searchParams, config);
  const archive = archiveFromParams(searchParams);

  // ONE writer for the whole URL, so the window and the open drawer survive a
  // filter change instead of being dropped by whichever handler ran last.
  function writeParams(
    next: TableRequestState,
    nextArchive: boolean,
    entryId: string | null,
  ): void {
    const params = serializeTableParams(next, config);
    if (nextArchive) {
      params.set(ARCHIVE_PARAM, "true"); // BR-AUD-013: only ever set explicitly
    }
    if (entryId !== null) {
      params.set(ENTRY_PARAM, entryId);
    }
    setSearchParams(params, { replace: true });
  }

  function setState(next: TableRequestState): void {
    writeParams(next, archive, openEntryId);
  }

  function setArchive(next: boolean): void {
    // A different window is a different result set, so the open row may not be
    // in it — close the drawer rather than leave it pointing at nothing.
    writeParams({ ...state, page: 1 }, next, null);
  }

  function openEntry(entryId: string | null): void {
    writeParams(state, archive, entryId);
  }

  const listQuery = useQuery({
    queryKey: queryKeys.auditLog(serializeTableParams(state, config).toString() + `|${archive}`),
    queryFn: () => getAuditLog(auditParamsFrom(state, archive), client),
  });

  const runExport = useMutation({
    mutationFn: async () => {
      const accepted = await requestAuditExport(auditParamsFrom(state, archive), client);
      // B12 r1 / 11b §2.17: a 202 is a JOB — poll it through the ONE helper.
      return client.pollJob(accepted.job_id);
    },
    onSuccess: (job) => {
      setExportNotice(null);
      // IS-11 (the download lane, 2026-08-10): a finished export is a FILE the
      // user can fetch, not an id in a toast. The href is the server's own
      // result_link, read through the ONE shared helper the list exports use.
      setExportFile(exportDownloadHref(job));
      fireToast(
        t(job.status === "succeeded" ? "audit.export.ready" : "audit.export.failed", {
          id: job.id,
        }),
      );
    },
    onError: (error: unknown) => {
      // BR-AUD-014's cap gets its own sentence with the server's own numbers;
      // everything else renders as the plain-language failure (BR-SHL-020).
      setExportFile(null);
      setExportNotice(exportCapRefusal(error, t) ?? apiErrorText(error, t));
    },
  });

  if (listQuery.data === undefined && listQuery.isError) {
    if (isPermissionDenied(listQuery.error)) {
      // US-AUD-004 TC-5: S61 is System Admin + Executive; the server denies the
      // rest, and A18 §6 renders INSTEAD of the screen (no rows behind it).
      return (
        <PermissionDenied
          helper={t("audit.denied")}
          onBack={() => navigate(tenantPath(DASHBOARD_ROUTE))}
        />
      );
    }
    return (
      <FailedWithRetry
        title={t("audit.failedTitle")}
        reason={apiErrorText(listQuery.error, t)}
        onRetry={() => void listQuery.refetch()}
        onDownloadReport={() => undefined}
        onCancel={() => void listQuery.refetch()}
      />
    );
  }

  const window = listQuery.data?.window ?? null;

  return (
    <div className="px-4 pt-6 pb-8">
      <div>
        <Kicker>{t("audit.kicker")}</Kicker>
        <h1 className="m-0 text-h2">{t("audit.title")}</h1>
        {/* BR-AUD-002 stated where the user can read it: this screen shows
            history and cannot change it. */}
        <p className="mt-1 mb-4 text-base text-[color-mix(in_srgb,var(--color-text)_65%,transparent)]">
          {t("audit.sub")}
        </p>
        {/* US-MET-020 / US-AUD-007 (2026-08-16). The retention job's run
            ledger had no reader anywhere, so "has retention ever run?" could
            not be answered from the product. This link is what makes it
            reachable — without a caller the page would be dead UI, which is
            the law-2 defect it was written to close. */}
        <Button
          variant="ghost"
          className="mt-2"
          onClick={() => navigate(tenantPath(RETENTION_ROUTE))}
        >
          {t("audit.retention.link")}
        </Button>
      </div>

      {window !== null && (
        <WindowBanner
          window={window}
          archive={archive}
          timeZone={timeZone}
          dateFormat={dateFormat}
          onToggle={() => setArchive(!archive)}
        />
      )}

      {exportNotice !== null && <RefusalStrip role="alert">{exportNotice}</RefusalStrip>}

      {exportFile !== null && <ExportReadyLine href={exportFile} t={t} />}

      <DataTable<AuditRow>
        config={config}
        state={state}
        onStateChange={setState}
        rows={listQuery.data?.page.results ?? []}
        totalRows={listQuery.data?.page.count ?? null}
        loading={listQuery.isPending}
        filterBarSlot={
          <AuditFilterPanel
            state={state}
            onStateChange={setState}
            actorOptions={actorOptions}
            actorListReadable={usersQuery.isSuccess}
            dateFormat={dateFormat}
          />
        }
        downloadSlot={
          // IS-9/IS-11 through the ONE export control; the guards are the
          // server's (BR-SHL-016/BR-AUD-014) and are never re-implemented here.
          <DownloadButton
            onDownload={() => {
              setExportNotice(null);
              runExport.mutate();
            }}
            disabled={runExport.isPending}
          />
        }
        empty={{
          title: t("audit.emptyTitle"),
          helper: t("audit.emptyHelper"),
          // A18 §1's CTA slot: the only forward move on a read-only screen is
          // to widen the window — there is nothing here for a user to create.
          ctaLabel: t(archive ? "audit.window.backToHot" : "audit.window.viewArchive"),
          onCta: () => setArchive(!archive),
        }}
      />

      {openEntryId !== null && (
        <AuditDrawer
          entryId={openEntryId}
          client={client}
          timeZone={timeZone}
          dateFormat={dateFormat}
          onClose={() => openEntry(null)}
        />
      )}
    </div>
  );
}

/**
 * BR-SHL-033: the tenant user list is long, so the actor filter is searchable.
 *
 * ⚠ **THE `automation` OPTION IS HERE BECAUSE OTHERWISE THE SERVER FILTER IS
 * DEAD (hard-won law 2 — built is not wired).** `f.actor=automation` narrows to
 * every named non-person actor, and a filter nothing in the UI can select is a
 * feature that does not exist. It sits beside `system`, which US-AUD-010
 * narrowed to the UNNAMED half: before this story one value answered both
 * questions badly, and now each answers its own.
 */
export function buildActorOptions(
  users: readonly TenantUser[] | undefined,
  t: Translator,
): { value: string; label: string }[] {
  const options = [
    { value: "system", label: t("audit.actor.system") }, // BR-AUD-003
    { value: "automation", label: t("audit.actor.automations") }, // BR-AUD-019
  ];
  for (const user of users ?? []) {
    options.push({ value: user.id, label: `${user.name} · ${user.email}` });
  }
  return options;
}

function WindowBanner(props: {
  window: AuditWindowInfo;
  archive: boolean;
  timeZone: string;
  dateFormat: RegionalDateFormat;
  onToggle: () => void;
}) {
  const { t } = useTranslation();
  return (
    <div
      className="mb-4 flex flex-wrap items-center gap-3 rounded-sm border border-divider border-l-[3px] border-l-accent-500 bg-surface px-3 py-2 text-base"
      role="status"
    >
      <span>{t(windowBannerKey(props.window))}</span>
      {props.window.from !== null && (
        <span className="text-[color-mix(in_srgb,var(--color-text)_65%,transparent)]">
          {t("audit.window.since")}{" "}
          {/* BR-SHL-034: even this floor goes through the shared formatter. */}
          <DateCell
            value={props.window.from}
            timeZone={props.timeZone}
            dateFormat={props.dateFormat}
          />
        </span>
      )}
      {/* BR-AUD-013: widening is EXPLICIT — its own control, its own query. */}
      <Button variant="ghost" onClick={props.onToggle}>
        {t(props.archive ? "audit.window.backToHot" : "audit.window.viewArchive")}
      </Button>
    </div>
  );
}

/** GAP AUD-D2: present-but-empty, with the reason on hover — never hidden. */
function SourceCell(props: { value: string | null }) {
  const { t } = useTranslation();
  if (props.value === null) {
    return (
      <span
        className="text-[color-mix(in_srgb,var(--color-text)_45%,transparent)] italic"
        data-audit="empty"
        title={t("audit.source.pendingHelp")}
      >
        {t("audit.source.pending")}
      </span>
    );
  }
  return <span>{props.value}</span>;
}

function AuditFilterPanel(props: {
  state: TableRequestState;
  onStateChange: (next: TableRequestState) => void;
  actorOptions: { value: string; label: string }[];
  actorListReadable: boolean;
  dateFormat: RegionalDateFormat;
}) {
  const { t } = useTranslation();
  const { state } = props;

  // Any filter change returns to page 1 — the result set changed (the same
  // derived law DataTable's own transitions follow).
  function set(name: AuditFilterName, value: string): void {
    const filters = { ...state.filters };
    if (value === "") {
      delete filters[name];
    } else {
      filters[name] = value;
    }
    props.onStateChange({ ...state, filters, page: 1 });
  }

  return (
    // ── DEF-2376 · THE SIX CONTROLS SIT ON ONE BASELINE, AND WHAT PUT THEM OFF
    //    IT WAS A PARAGRAPH, NOT THE GRID.
    //
    //    The Product Owner photographed this row on a live deployment: *"took
    //    bar should be aligned properly"*. The grid was right; the field KIT is
    //    what moved the box. `TextField` renders label → **help** → input, so a
    //    three-line helper under "Action code" pushed that ONE input three lines
    //    below the other five while every other box stayed where it was. Nothing
    //    could see it: it is valid Tailwind on a file that IS on
    //    `styles/route-b-migrated.txt` (checked — utilities are lawful here, and
    //    its stylesheet was deleted whole in the CR-018 round-4 migration), it
    //    compiles, it type-checks, and no gate in this repo reads rendered
    //    output.
    //
    //    So the fix is a rule-32 fix and not a layout trick: **no field in this
    //    row carries a paragraph.** Every `.field` is now label + control, one
    //    identical height, and `items-start` says so out loud rather than
    //    leaving it to `stretch`. The one thing a reader genuinely needs — an
    //    example of what an action code looks like — is a PLACEHOLDER, which is
    //    where B14 rule 19 already puts a prompt. `AuditToolbarAlignment.dom.test`
    //    pins this contract, because a helper added back to any one of these
    //    fields would break the row again and pass every existing test.
    //
    //    ⚠ THE PANEL STILL TAKES A WHOLE TOOLBAR LINE (`w-full`), AND THAT IS A
    //    STATED CHOICE RATHER THAN THE DEFAULT NOBODY LOOKED AT. Every other
    //    list puts `components/FilterBar` in this slot — a chip row plus a
    //    `Filter ▾` panel — which sits inline beside the export and column
    //    controls. S61 cannot use it: FilterBar renders a CHECKBOX PER OPTION,
    //    and five of these six filters have no option list at all (free text
    //    over the action code and the entity, two date pickers). Sharing the
    //    line instead would put a `flex-1` block next to `.table-toolbar`'s own
    //    `flex:1` spacer and hand the filters half the room. So the row is
    //    filters, then the two icon controls beneath them at the right — and
    //    with a straight bottom edge above them they read as a row rather than
    //    as two buttons adrift.
    <div className="flex w-full flex-col gap-2">
      <div className="grid w-full grid-cols-[repeat(auto-fit,minmax(180px,1fr))] items-start gap-3">
        {props.actorListReadable ? (
          // BR-SHL-033: a long list is type-ahead searchable, never a scroll list.
          <SearchSelectField
            id="f.actor"
            label={t("audit.filter.actor")}
            value={state.filters.actor ?? ""}
            onChange={(value) => set("actor", value)}
            options={props.actorOptions}
            placeholder={t("audit.filter.actorPlaceholder")}
          />
        ) : (
          // `GET /users` is System-Admin-only; an Executive may read S61 but not
          // the user list. The filter still works — it just takes the id, and
          // the reason is ONE sentence for the whole section below (rule 32)
          // rather than a paragraph inside this field (DEF-2376).
          <TextField
            id="f.actor"
            label={t("audit.filter.actor")}
            value={state.filters.actor ?? ""}
            onChange={(value) => set("actor", value)}
            placeholder={t("audit.filter.actorIdPlaceholder")}
          />
        )}
        <TextField
          id="f.action"
          label={t("audit.filter.action")}
          value={state.filters.action ?? ""}
          onChange={(value) => set("action", value)}
          // BR-AUD-009 also names an action-TYPE class filter and a MODULE
          // filter. Both are properties of the US-AUD-002 event-code catalog,
          // which is not built — so this filters the action CODE, which is what
          // the server actually filters on. That gap is engineering provenance
          // and belongs in this comment: it used to be the second sentence of a
          // helper paragraph on the screen, which is what rule 32 calls a stated
          // absence left OPEN by default, and what knocked this row out of line.
          placeholder={t("audit.filter.actionPlaceholder")}
        />
        <TextField
          id="f.entity_type"
          label={t("audit.filter.entityType")}
          value={state.filters.entity_type ?? ""}
          onChange={(value) => set("entity_type", value)}
        />
        <TextField
          id="f.entity_id"
          label={t("audit.filter.entityId")}
          value={state.filters.entity_id ?? ""}
          onChange={(value) => set("entity_id", value)}
        />
        {/* BR-SHL-033: date fields are always pickers with manual entry. */}
        <DatePickerField
          id="f.from"
          label={t("audit.filter.from")}
          value={state.filters.from ?? ""}
          onChange={(value) => set("from", value)}
          dateFormat={props.dateFormat}
        />
        <DatePickerField
          id="f.to"
          label={t("audit.filter.to")}
          value={state.filters.to ?? ""}
          onChange={(value) => set("to", value)}
          dateFormat={props.dateFormat}
        />
      </div>
      {/* ── CR-067 B3 · "ERRORS ONLY", AND IT IS THE PO'S OWN ASK ─────
          2026-09-02, verbatim: *"What I would add to the toolbar is a "Errors
          only" filter, so you can jump straight to the failures without
          scrolling past 800 rows of successful seeding. - Yes this is
          required"*. Their tenant's log carries 809 rows and the failure they
          were hunting sat behind all of them.

          ⚠ **IT IS OUTSIDE THE SIX-FIELD GRID ON PURPOSE (DEF-2376).** Every
          box in that grid is label-above-control and they share one baseline;
          a checkbox is label-BESIDE-control and would sit at a different
          height in the same row, which is the exact fault DEF-2376 was filed
          for. On its own line it also reads as what it is — a jump, not a
          seventh thing to fill in.

          ⚠ **AND IT WRITES A FILTER THE SERVER DECLARES.** `f.outcome=error`
          narrows to the eight action codes a runtime failure is written under
          (`apps/audit/selectors.FAILURE_ACTIONS`). Ticking it goes through
          `set()` like every other filter, so it lands in the URL, survives a
          refresh, is shared by a link, and is carried by the export. */}
      <div className="flex flex-wrap items-center gap-3">
        <CheckboxField
          id="f.outcome"
          label={t("audit.filter.errorsOnly")}
          checked={state.filters.outcome === AUDIT_OUTCOME_ERROR}
          onChange={(checked) => set("outcome", checked ? AUDIT_OUTCOME_ERROR : "")}
        />
      </div>
      {/* Rule 32's one sentence per section, and it appears only in the state it
          describes — an Executive, whose role cannot read the user list. */}
      {!props.actorListReadable && <Note>{t("audit.filter.actorNoList")}</Note>}
    </div>
  );
}

// ── US-AUD-005 — the detail drawer ─────────────────────────────────────────

function AuditDrawer(props: {
  entryId: string;
  client: ApiClient;
  timeZone: string;
  dateFormat: RegionalDateFormat;
  onClose: () => void;
}) {
  const { t } = useTranslation();
  const entryQuery = useQuery({
    queryKey: queryKeys.auditEntry(props.entryId),
    queryFn: () => getAuditEntry(props.entryId, props.client),
  });

  return (
    // ONE dialog implementation (LAW 0) — the drawer reuses ModalShell's focus
    // trap, Esc and backdrop behaviour rather than growing a second one.
    <ModalShell title={t("audit.drawer.title")} kicker={t("audit.kicker")} onClose={props.onClose}>
      <div className="modal-body flex flex-col gap-4">
        {entryQuery.isPending ? (
          <LoadingSkeleton variant="card" />
        ) : entryQuery.data === undefined ? (
          <RefusalStrip role="alert">{apiErrorText(entryQuery.error, t)}</RefusalStrip>
        ) : (
          <AuditDrawerBody
            entry={entryQuery.data}
            client={props.client}
            timeZone={props.timeZone}
            dateFormat={props.dateFormat}
          />
        )}
      </div>
      <div className="modal-foot">
        <Button variant="secondary" onClick={props.onClose}>
          {t("forms.close")}
        </Button>
      </div>
    </ModalShell>
  );
}

function AuditDrawerBody(props: {
  entry: AuditEntry;
  client: ApiClient;
  timeZone: string;
  dateFormat: RegionalDateFormat;
}) {
  const { t } = useTranslation();
  const translate: Translator = (key, params) => t(key, params);
  const { entry } = props;
  // CR-067 task B2's role gate. `useTenantRole` answers null while
  // `/me/permissions` has not landed or was refused, and null is NOT a System
  // Admin here: the technical half is the one thing on this drawer that is not
  // everyone's, so an unanswered read must not open it (BR-SHL-025's honest
  // default — never guess a role, never grant one).
  const role = useTenantRole(props.client);
  const failure = auditFailureOf(entry.after);
  const isSystemAdmin = role === ROLE_SYSTEM_ADMIN;
  // CR-067 B2 / DEF-3321 — the reproduction record, on its OWN read.
  //
  // ⚠ **THE SEPARATE REQUEST IS WHAT MAKES THE ROLE GATE A BOUNDARY.** Until it
  // existed both halves of this drawer came out of the ONE payload
  // `GET /audit-log/{id}` serves, so `useTenantRole` could only decide what was
  // DRAWN and an Executive held the bytes either way (BR-SHL-025 convenience,
  // said out loud rather than implied). The technical half now arrives from
  // `SystemAdminOnly` on the server, so an Executive is refused whatever this
  // component believes.
  //
  // `enabled` is the same honest default the role check itself uses: an
  // unanswered `/me/permissions` is NOT a System Admin, so nothing is asked for.
  //
  // ⚠ **IT ASKS EVEN WHEN THE ROW CARRIES NO REFERENCE, AND THAT IS DELIBERATE.**
  // The server answers `no_reference` for those, so ONE authority decides which
  // of the three states this panel is in. Deciding it here from
  // `failure.reference === null` would be a second rule that can drift — and the
  // day old rows gain a reference, this screen is already right.
  const diagnosticQuery = useQuery({
    queryKey: queryKeys.auditDiagnostic(entry.id),
    queryFn: () => getAuditDiagnostic(entry.id, props.client),
    enabled: isSystemAdmin && failure !== null,
    retry: false,
  });
  return (
    <>
      <dl className="m-0 grid grid-cols-[minmax(120px,auto)_1fr] gap-x-3 gap-y-2 text-base [&_dd]:m-0 [&_dt]:font-heading [&_dt]:font-semibold [&_dt]:text-[color-mix(in_srgb,var(--color-text)_65%,transparent)]">
        <dt>{t("audit.col.when")}</dt>
        <dd>
          <DateCell
            value={entry.created_at}
            timeZone={props.timeZone}
            dateFormat={props.dateFormat}
            withTime
          />
        </dd>
        <dt>{t("audit.col.actor")}</dt>
        <dd>{actorLabel(entry, translate)}</dd>
        <dt>{t("audit.col.action")}</dt>
        {/* DEF-645: the code identified the event to an engineer and to nobody
            else. The sentence is the shared presenter's; the code still travels
            on `data-audit-action` for support. */}
        <dd>
          <AuditEventSentenceText row={entry} t={translate} />
        </dd>
        <dt>{t("audit.col.entity")}</dt>
        {/* TC-6: a hard-deleted entity still renders — as a label, never a 404.
            DEF-2378: as WORDS, with the id on `title` for support and rendered
            verbatim in the Stored record fold below, which is where an auditor
            reads the exact reference. */}
        <dd title={supportReference(entry.entity_id)}>{entityLabel(entry, translate)}</dd>
        <dt>{t("audit.col.source")}</dt>
        <dd>
          <SourceCell value={entry.source} />
        </dd>
        <dt>{t("audit.drawer.requestMetadata")}</dt>
        {/* GAP AUD-D2 again: the field is in the contract and empty today, so
            it renders empty. Hiding it would hide the gap. */}
        <dd>
          <JsonBlock value={entry.request_metadata} />
        </dd>
      </dl>

      {/* CR-067 · THE SECOND SECTION, AND ONLY WHEN THERE IS A FAILURE TO
          EXPLAIN. A row that records a success carries no `error_code`, so
          `auditFailureOf` answers null and nothing is drawn — B14 rule 32 again:
          a panel nobody asked to see is content on a screen just as a paragraph
          is. */}
      {failure !== null && (
        <AuditDiagnosticSection
          failure={failure}
          action={entry.action}
          isSystemAdmin={isSystemAdmin}
          diagnostic={diagnosticQuery.data ?? null}
          diagnosticPending={diagnosticQuery.isPending}
          timeZone={props.timeZone}
          dateFormat={props.dateFormat}
          t={translate}
        />
      )}

      {/* DEF-645 · WHAT CHANGED, IN WORDS, AND ALL OF IT. The same field list
          the per-entity Audit tab draws, from the same payload: labels in
          English, identifiers dropped, nothing truncated. */}
      <section>
        <h5 className="m-0 mb-1 text-base">
          {auditText(translate, "audit.details.title", "What changed")}
        </h5>
        <AuditFieldList set={auditFieldSet(entry.before, entry.after, translate)} t={translate} />
      </section>

      {/* BR-AUD-006: before/after render EXACTLY as stored. A masked value stays
          masked — there is no unmask path in this app or on the server, and the
          full value never left it.

          ⚠ COLLAPSED SINCE DEF-645, NOT REMOVED. US-AUD-005 §5 ratifies the
          stored diff as part of this drawer and an auditor may need the exact
          record, so it stays reachable — but it is raw storage, keys and all,
          and it is no longer the first thing a reader meets. Disclosure's rule
          is kept: what folds away is the derivation, and the readable result
          above it is always open. */}
      <Disclosure
        variant="section"
        title={auditText(translate, "audit.drawer.stored", "Stored record")}
        summary={auditText(
          translate,
          "audit.drawer.storedHelp",
          "exactly as it was saved, technical",
        )}
      >
        <div className="grid grid-cols-[repeat(auto-fit,minmax(220px,1fr))] gap-3">
          {/* DEF-2378 — THE ONE PLACE THE REFERENCE IS SHOWN, AND IT IS THIS
              PLACE ON PURPOSE. B14 rule 31 is about the value a person READS in
              a field; this fold is closed by default, its own summary says
              "exactly as it was saved, technical", and US-AUD-005 §5 ratifies it
              as the auditor's exact record. It goes through the same JsonBlock
              as before/after because that is what it is: stored data, verbatim. */}
          <section>
            <h5 className="m-0 mb-1 text-base">
              {auditText(translate, "audit.drawer.reference", "Record reference")}
            </h5>
            <JsonBlock value={{ entity_type: entry.entity_type, entity_id: entry.entity_id }} />
          </section>
          <section>
            <h5 className="m-0 mb-1 text-base">{t("audit.drawer.before")}</h5>
            <JsonBlock value={entry.before} />
          </section>
          <section>
            <h5 className="m-0 mb-1 text-base">{t("audit.drawer.after")}</h5>
            <JsonBlock value={entry.after} />
          </section>
        </div>
      </Disclosure>
      <Note>{t("audit.drawer.readOnly")}</Note>
    </>
  );
}

// ══ CR-067 tasks B1 + B2 — THE DIAGNOSTIC, AS A SECOND SECTION IN THIS DRAWER ══
//
// PO ruling 2026-09-02, verbatim, and it settles the surface: *"You click the row
// that failed — the drawer you already have, the one behind "Expand" — and the
// diagnostic is a second section inside it. Everything on my wireframe lives
// there + Same screen. No new tab."*
//
// So: no second dialog (LAW 0 already says one dialog implementation), no second
// route, no second list. One section inside `AuditDrawerBody`, and it renders
// ONLY for a row that actually records a failure — B14 rule 32's description
// budget applies to a panel nobody asked to see exactly as it applies to a
// paragraph.
//
// ⚠ **WHERE EVERY VALUE BELOW COMES FROM, READ OUT OF CODE RATHER THAN OUT OF
// THE WIREFRAME.** `GET /audit-log/{id}` serves the row's stored payload
// verbatim (`apps/audit/selectors.audit_detail` → `after`), and
// `apps/tenancy/sample_data._audit_failed_block` is what writes it: `module`,
// `block`, `label`, `error_code`, `reason_code`, `failure_class`, `root_block`,
// `meaning`, `detail_location` and — since CR-067 task A4 — `reference`.
// Nothing here invents a field, and nothing here calls an endpoint that does not
// exist.
//
// ⚠ **AND THE HALF THAT WAS MISSING IS NOW HERE — `DEF-3321` IS CLOSED.** The
// reproduction record CR-067 §5 is measured against — the exception and its
// module, the code frames, the job step, the release, the settings in force, the
// request's field NAMES — lives in `error_diagnostics`, and for one day **no
// endpoint anywhere in `06-backend` served that table**: `apps/audit/api.py`
// defined three routes, none of them read it, and task A1's own Lifecycle
// trailer said `D=deferred(no endpoint of its own)`. The panel that stood here
// stated that absence rather than binding to a payload key nothing sent, which
// was hard-won law 2 answered correctly and was not the finished product.
//
// `GET /audit-log/{id}/diagnostic` is the read, it is `SystemAdminOnly` on the
// server, and the stated absence it replaced is GONE — a note with no reason
// left outlives its reason, which is what `G38`/DEF-445 are about. What remains
// stated, and must be, are the two absences that are REAL and permanent: a
// record that expired, and a failure recorded before the record existed.

/** A failure as the permanent audit row records it. Null when the row is not one. */
export interface AuditFailure {
  /** The stable code both halves of CR-067 share — `SD-PRECONDITION`. */
  errorCode: string;
  /** The fixed, interpolation-free catalogue sentence (`sample_errors.CATALOGUE`). */
  meaning: string | null;
  /** English platform copy for the step — "Documents", "Meter reads". */
  label: string | null;
  module: string | null;
  block: string | null;
  /** `root` — this is where it started — or `consequence` of an earlier failure. */
  failureClass: string | null;
  /** The block that actually broke, as its KEY. Technical half only (rule 32). */
  rootBlock: string | null;
  /** `5F2B-9C1D` — the short reference CR-067 task A4 puts on the row. */
  reference: string | null;
}

/** `root` / `consequence` as `apps/tenancy/sample_data` spells them. */
export const FAILURE_ROOT = "root";
export const FAILURE_CONSEQUENCE = "consequence";

/** One string out of a stored payload, or null. Never `""`, never a number. */
function payloadText(payload: Record<string, unknown> | null, key: string): string | null {
  const value = payload?.[key];
  if (typeof value !== "string") {
    return null;
  }
  const text = value.trim();
  return text === "" ? null : text;
}

/**
 * The failure this payload describes, or null.
 *
 * ⚠ **`error_code` IS THE TEST, AND IT IS THE ONE THE WRITER ITSELF USES.**
 * `sample.block_retried` carries `error_code: null` when the retry SUCCEEDED and
 * a code when it failed again, so keying on the ACTION would put a "why this
 * failed" panel on a row that says a step recovered. Keying on the code cannot:
 * a successful row has none.
 */
export function auditFailureOf(after: Record<string, unknown> | null): AuditFailure | null {
  const errorCode = payloadText(after, "error_code");
  if (errorCode === null) {
    return null;
  }
  return {
    errorCode,
    meaning: payloadText(after, "meaning"),
    label: payloadText(after, "label"),
    module: payloadText(after, "module"),
    block: payloadText(after, "block"),
    failureClass: payloadText(after, "failure_class"),
    rootBlock: payloadText(after, "root_block"),
    reference: payloadText(after, "reference"),
  };
}

/**
 * WHERE it happened, for the technical half only: `tenancy · seed_sample_records`.
 * Null when the payload named neither, so the row is left out rather than drawn
 * with a separator and nothing on either side of it.
 */
export function failureComponent(failure: AuditFailure): string | null {
  const parts = [failure.module, failure.block].filter((part): part is string => part !== null);
  return parts.length === 0 ? null : parts.join(" · ");
}

/**
 * What to do about it, as ONE short instruction — or null when the record does
 * not say. A knock-on is not the one to fix, and saying so is the whole value of
 * `failure_class` (the five-reds-one-cause problem `sample_data.py` records from
 * DEF-660).
 *
 * ⚠ The ROOT BLOCK IS NOT NAMED HERE even though the payload carries it: it is
 * `metering:seed_sample_records`, an internal code, and B14 rule 32 keeps those
 * out of clerk-facing copy. It renders in the technical half, which is where a
 * reader who can act on it is.
 */
export function failureAdviceKey(failure: AuditFailure): string | null {
  if (failure.failureClass === FAILURE_CONSEQUENCE) {
    return "audit.diagnostic.adviceKnockOn";
  }
  if (failure.failureClass === FAILURE_ROOT) {
    return "audit.diagnostic.adviceRoot";
  }
  return null;
}

/**
 * B1 — **the reference, on screen, with a copy action.** CR-067 §3: *"The
 * reference exists so a person can leave the screen with it — read it down a
 * phone, paste it into a message."*
 *
 * ⚠ **THIS IS NOT B14 RULE 31's DATABASE ID, AND THE DIFFERENCE IS THE POINT.**
 * Rule 31 — *"no Databse ID on screen - that is a rule"* — is about a uuid
 * rendered as the value of a field, which a person can neither read aloud nor
 * use. `5F2B-9C1D` is eight characters, it is minted to be dictated, and
 * `apps/audit/selectors._entity_id_prefix` searches by it. The row's own record
 * id is untouched by this and stays where the lane before us left it: behind the
 * closed *Stored record* fold.
 *
 * The clipboard is best-effort on purpose. It is absent in a non-secure context
 * and in the test renderer, and a reference a person can SEE is already the
 * deliverable — the button is a convenience over it, never the only way to get
 * the value.
 */
export function ReferenceValue(props: { reference: string; t: Translator }) {
  const [copied, setCopied] = useState(false);
  return (
    <span className="inline-flex flex-wrap items-center gap-2">
      <code
        className="rounded-sm border border-divider bg-neutral-100 px-1.5 py-0.5 font-mono text-base tracking-wide"
        data-audit="reference"
      >
        {props.reference}
      </code>
      <Button
        variant="ghost"
        size="sm"
        data-audit="copy-reference"
        onClick={() => {
          const clipboard = globalThis.navigator?.clipboard;
          if (clipboard === undefined) {
            return;
          }
          void clipboard.writeText(props.reference).then(() => setCopied(true));
        }}
      >
        {props.t(copied ? "audit.diagnostic.copied" : "audit.diagnostic.copy")}
      </Button>
    </span>
  );
}

/**
 * B2 — the second section. The PLAIN half is everyone's; the TECHNICAL half is
 * the System Admin's.
 *
 * ⚠ **THE ROLE CHECK IS NOW A BOUNDARY AND NOT ONLY A CHOICE OF WHAT TO DRAW,
 * AND THE DIFFERENCE IS WHICH SERVER READ THE DATA CAME FROM (BR-SHL-025).**
 * The repo's posture — `meteringShared.useTenantRole`'s docstring, verbatim — is
 * that a frontend role check *"decides only whether the control is offered"* and
 * *"the server's own @require_role(SYSTEM_ADMIN) is the boundary either way"*.
 * That was WEAKER here than usual for one day, because both halves were drawn
 * from ONE payload the browser already held: an Executive who can reach S61 had
 * the bytes whether or not this panel drew them. The reproduction record now
 * arrives on its own request — `GET /audit-log/{id}/diagnostic`, behind
 * `SystemAdminOnly` — so an Executive is refused 403 by the server and never
 * receives it. `useTenantRole` here decides whether to ASK.
 *
 * **What is still drawn from the shared payload is the plain half plus the four
 * summary rows** (the code, the module and block, the event, the block it
 * started at), and those are BR-SHL-025 convenience exactly as before. Said out
 * loud rather than left as a claim the markup cannot support (hard-won law 1).
 */
export function AuditDiagnosticSection(props: {
  failure: AuditFailure;
  action: string;
  isSystemAdmin: boolean;
  /** The System-Admin-only read, or null while it is pending, not asked for, or
   *  refused. `diagnosticPending` is what tells those apart. */
  diagnostic: AuditDiagnostic | null;
  diagnosticPending: boolean;
  timeZone: string;
  dateFormat: RegionalDateFormat;
  t: Translator;
}) {
  const { failure, t } = props;
  const adviceKey = failureAdviceKey(failure);
  const component = failureComponent(failure);
  return (
    <section data-audit="diagnostic">
      <h5 className="m-0 mb-1 text-base">{t("audit.diagnostic.title")}</h5>
      {/* Rule 32's ONE sentence for this section, and it is not ours: it is the
          fixed, interpolation-free catalogue sentence the server chose for this
          code (`sample_errors.audit_safe_sentence`), which is exactly why it is
          safe on an append-only record and readable by a clerk. */}
      {failure.meaning !== null && (
        <p
          className="m-0 mb-2 max-w-measure text-base text-[color-mix(in_srgb,var(--color-text)_75%,transparent)]"
          role="note"
        >
          {failure.meaning}
        </p>
      )}
      <dl className="m-0 grid grid-cols-[minmax(120px,auto)_1fr] gap-x-3 gap-y-2 text-base [&_dd]:m-0 [&_dt]:font-heading [&_dt]:font-semibold [&_dt]:text-[color-mix(in_srgb,var(--color-text)_65%,transparent)]">
        {failure.label !== null && (
          <>
            <dt>{t("audit.diagnostic.doing")}</dt>
            <dd data-audit="diagnostic-doing">{failure.label}</dd>
          </>
        )}
        <dt>{t("audit.diagnostic.result")}</dt>
        <dd data-audit="diagnostic-result">{t("audit.diagnostic.resultFailed")}</dd>
        {adviceKey !== null && (
          <>
            <dt>{t("audit.diagnostic.advice")}</dt>
            <dd data-audit="diagnostic-advice">{t(adviceKey)}</dd>
          </>
        )}
        {failure.reference !== null && (
          <>
            <dt>{t("audit.diagnostic.reference")}</dt>
            <dd>
              <ReferenceValue reference={failure.reference} t={t} />
            </dd>
          </>
        )}
      </dl>

      {props.isSystemAdmin && (
        <div className="mt-3" data-audit="diagnostic-technical">
          <h5 className="m-0 mb-1 text-base">{t("audit.diagnostic.techTitle")}</h5>
          <dl className="m-0 grid grid-cols-[minmax(120px,auto)_1fr] gap-x-3 gap-y-2 text-base [&_dd]:m-0 [&_dt]:font-heading [&_dt]:font-semibold [&_dt]:text-[color-mix(in_srgb,var(--color-text)_65%,transparent)]">
            <dt>{t("audit.diagnostic.techCode")}</dt>
            <dd>
              <code className="font-mono text-sm">{failure.errorCode}</code>
            </dd>
            {component !== null && (
              <>
                <dt>{t("audit.diagnostic.techWhere")}</dt>
                <dd>
                  <code className="font-mono text-sm">{component}</code>
                </dd>
              </>
            )}
            <dt>{t("audit.diagnostic.techEvent")}</dt>
            <dd>
              <code className="font-mono text-sm">{props.action}</code>
            </dd>
            {failure.rootBlock !== null && (
              <>
                <dt>{t("audit.diagnostic.techRoot")}</dt>
                <dd>
                  <code className="font-mono text-sm">{failure.rootBlock}</code>
                </dd>
              </>
            )}
          </dl>
          {/* CR-067 §5's six facts, from the System-Admin-only read. While the
              request is in flight nothing is drawn: a skeleton over four rows
              would be more movement than information, and the four summary rows
              above are already on screen. */}
          {props.diagnostic?.record != null && (
            <ReproductionRecord
              record={props.diagnostic.record}
              timeZone={props.timeZone}
              dateFormat={props.dateFormat}
              t={t}
            />
          )}
          {props.diagnostic !== null && !props.diagnostic.held && (
            <DiagnosticAbsence
              reason={props.diagnostic.reason}
              t={t}
            />
          )}
          {props.diagnostic === null && !props.diagnosticPending && (
            <DiagnosticAbsence reason={DIAGNOSTIC_UNREAD} t={t} />
          )}
        </div>
      )}
    </section>
  );
}

/**
 * The reproduction record — **the whole point of CR-067, and the thing that was
 * missing from this screen until `DEF-3321` closed.**
 *
 * CR-067 §5 puts the bar as a question: *"could somebody holding ONLY the
 * diagnostic record write a failing test?"* Every row below is one of the six
 * things that answer takes, in the order a person reads them: what blew up,
 * where in the code, which step of which job, which build, what the deployment
 * was configured to do, and which fields the request carried.
 *
 * ⚠ **THE RAW 32-HEX TRACE ID IS SERVED AND IS DELIBERATELY NOT DRAWN.** It was
 * on this panel for an hour, as the value a server log is grepped for. `G44`'s
 * ratchet caught it and the ratchet is right: B14 rule 31's LETTER is about a
 * database id, and its REASON — a value a person can neither read aloud nor
 * type back — describes a 32-character hex string exactly. **Nothing is lost,
 * and that is checkable rather than asserted:** the reference above IS the first
 * eight hex of the trace, so `grep 5f2b9c1d` finds the same log line the whole
 * string would. It stays in the payload for a support engineer at the API.
 *
 * ⚠ **THERE IS NO MESSAGE ROW AND THERE CANNOT BE.** `core.diagnostics` has no
 * parameter that accepts a value and stores `str(exc)` in no column (task A2),
 * because a runtime message routinely carries an account number or a balance and
 * `audit_log` has no delete (CR-067 §2 / BR-AUD-002). What replaces it is the
 * TYPE, which is code rather than data.
 *
 * ⚠ **"Detail kept until" IS A DATE AND NEVER A NUMBER OF DAYS.** `OQ-1390` — is
 * ninety right, and does a diagnostic fall under `audit_log`'s retention regime
 * or its own — is OPEN, and `DIAGNOSTIC_RETENTION_DAYS` is a per-deployment
 * setting this screen cannot read. The server STAMPS the date on the record at
 * write time, so a utility that set thirty days is told its own date. A printed
 * "90 days" would state an unratified figure as fact and be wrong for that
 * utility besides — which is why the lane before this one took the words back
 * out of eleven catalogues.
 */
function ReproductionRecord(props: {
  record: AuditDiagnosticRecord;
  timeZone: string;
  dateFormat: RegionalDateFormat;
  t: Translator;
}) {
  const { record, t } = props;
  const innermost = record.frames.length === 0 ? null : record.frames[record.frames.length - 1];
  const settings = Object.entries(record.settings_in_force);
  return (
    <div className="mt-3" data-audit="diagnostic-record">
      <dl className="m-0 grid grid-cols-[minmax(120px,auto)_1fr] gap-x-3 gap-y-2 text-base [&_dd]:m-0 [&_dt]:font-heading [&_dt]:font-semibold [&_dt]:text-[color-mix(in_srgb,var(--color-text)_65%,transparent)]">
        <dt>{t("audit.diagnostic.techException")}</dt>
        <dd data-audit="diagnostic-exception">
          <code className="font-mono text-sm">
            {record.exception.type} · {record.exception.module}
          </code>
        </dd>
        {innermost !== null && (
          <>
            <dt>{t("audit.diagnostic.techCodePath")}</dt>
            <dd data-audit="diagnostic-frame">
              <code className="font-mono text-sm">
                {innermost.file}:{innermost.line} · {innermost.function}
              </code>
            </dd>
          </>
        )}
        {record.job.kind !== null && (
          <>
            <dt>{t("audit.diagnostic.techJob")}</dt>
            <dd>
              <code className="font-mono text-sm">{record.job.kind}</code>
            </dd>
          </>
        )}
        {record.job.step !== null && record.job.of !== null && (
          <>
            <dt>{t("audit.diagnostic.techStep")}</dt>
            <dd data-audit="diagnostic-step">
              {t("audit.diagnostic.techStepValue", { step: record.job.step, of: record.job.of })}
            </dd>
          </>
        )}
        <dt>{t("audit.diagnostic.techRelease")}</dt>
        <dd data-audit="diagnostic-release">{record.release}</dd>
        {settings.length > 0 && (
          <>
            <dt>{t("audit.diagnostic.techSettings")}</dt>
            <dd data-audit="diagnostic-settings">
              {/* One line per setting, as `NAME = value`. This is what CR-067
                  §5's worked example prints, and it is the half of the record
                  that most often IS the answer — the 2 September failure was
                  three of these lines and nothing else. */}
              <ul className="m-0 list-none p-0">
                {settings.map(([name, value]) => (
                  <li key={name}>
                    <code className="font-mono text-sm">
                      {name} = {JSON.stringify(value)}
                    </code>
                  </li>
                ))}
              </ul>
            </dd>
          </>
        )}
        {record.request_fields.length > 0 && (
          <>
            <dt>{t("audit.diagnostic.techRequestFields")}</dt>
            {/* NAMES, never values — the writer's signature is what guarantees
                it, and this row is where that guarantee is visible. */}
            <dd data-audit="diagnostic-request-fields">
              <code className="font-mono text-sm">{record.request_fields.join(", ")}</code>
            </dd>
          </>
        )}
        <dt>{t("audit.diagnostic.techKeptUntil")}</dt>
        <dd data-audit="diagnostic-kept-until">
          <DateCell
            value={record.kept_until}
            timeZone={props.timeZone}
            dateFormat={props.dateFormat}
          />
        </dd>
      </dl>
      {record.frames.length > 1 && (
        // CLOSED by default (B14 rule 32). A call path is the least readable and
        // most occasionally decisive thing on this panel; the innermost frame is
        // above, open, because that is the one a reader needs first.
        <details className="mt-2" data-audit="diagnostic-stack">
          <summary className="m-0 cursor-pointer font-heading text-md">
            {t("audit.diagnostic.techStack")}
          </summary>
          <ol className="m-0 mt-1 list-none p-0">
            {record.frames.map((frame, index) => (
              <li key={`${frame.file}:${frame.line}:${index}`}>
                <code className="font-mono text-sm">
                  {frame.file}:{frame.line} · {frame.function}
                </code>
              </li>
            ))}
          </ol>
        </details>
      )}
    </div>
  );
}

/**
 * A stated absence, and **all three of these are honest states rather than
 * things somebody has not got round to.**
 *
 *   `not_held`      the record expired, or was refused for trying to carry a
 *                   value, or the store was down when it was written. CR-067
 *                   struck that bargain on purpose: the detail is what carries
 *                   risk, so the detail is what expires. The permanent row still
 *                   reads correctly on its own.
 *   `no_reference`  the failure was recorded before CR-067 kept a technical
 *                   record at all — **the state a Product Owner meets first**,
 *                   because every row already in their log predates it.
 *   `unread`        the read did not answer. Said rather than drawn as an empty
 *                   panel, which would read as "there is nothing here".
 *
 * ⚠ **CLOSED BY DEFAULT — B14 rule 32**, the shape `billRunShared.RunGap` holds
 * by construction and the one `DEF-2375` re-established on the dashboard tiles.
 * A `<details>` cannot leak its content onto the screen, because being closed is
 * what it IS.
 *
 * ⚠ **NO `data-tracks` HERE, AND ITS ABSENCE IS DELIBERATE.** `G38`/DEF-445 ask
 * a stated absence to cite the row that will KILL it, so that closing the row
 * points a reader at every screen still claiming it. These three name no row,
 * because no row will close them — they are permanent facts about a record with
 * a lifetime. The note that DID carry one, `DEF-3321`, went out with the defect.
 *
 * ⚠ **AND NOT ONE OF THESE SENTENCES MAY CONTAIN A DIGIT.** `OQ-1390` is open on
 * the retention window and the window is a per-deployment setting this screen
 * cannot read — a utility set to thirty days would be told ninety in its own
 * language. A test asserts it across all eleven catalogues.
 */
export const DIAGNOSTIC_UNREAD = "unread";

/**
 * The three absence states, as LITERAL key pairs.
 *
 * ⚠ **THEY ARE WRITTEN OUT RATHER THAN COMPOSED — a template literal here would
 * make all six keys invisible to `G18`**, which reads `t("…")` call sites to
 * answer two questions nothing else can: is a key used in code and defined in no
 * catalogue (it renders raw to a person), and is a key defined and used nowhere
 * (it is dead weight eleven translators keep in step). A key nothing can see is
 * a key nothing can check.
 */
function absenceCopy(reason: string, t: Translator): { title: string; body: string } {
  if (reason === DIAGNOSTIC_NO_REFERENCE) {
    return { title: t("audit.diagnostic.olderTitle"), body: t("audit.diagnostic.olderBody") };
  }
  if (reason === DIAGNOSTIC_UNREAD) {
    return { title: t("audit.diagnostic.unreadTitle"), body: t("audit.diagnostic.unreadBody") };
  }
  return { title: t("audit.diagnostic.goneTitle"), body: t("audit.diagnostic.goneBody") };
}

function DiagnosticAbsence(props: { reason: string; t: Translator }) {
  const copy = absenceCopy(props.reason, props.t);
  return (
    <details
      className="my-3 border border-dashed border-[color-mix(in_srgb,var(--color-text)_30%,transparent)] bg-[color-mix(in_srgb,var(--color-text)_3%,transparent)] p-3"
      data-audit="diagnostic-gap"
      data-diagnostic-absence={props.reason}
    >
      <summary className="m-0 cursor-pointer font-heading text-md">{copy.title}</summary>
      <p
        className="m-0 mt-1 max-w-measure text-base text-[color-mix(in_srgb,var(--color-text)_70%,transparent)]"
        role="note"
      >
        {copy.body}
      </p>
    </details>
  );
}

/** The stored payload, rendered verbatim. Null is a STATE, not a blank. */
function JsonBlock(props: { value: Record<string, unknown> | null }) {
  const { t } = useTranslation();
  if (props.value === null) {
    return (
      <span
        className="text-[color-mix(in_srgb,var(--color-text)_45%,transparent)] italic"
        data-audit="empty"
      >
        {t("audit.drawer.none")}
      </span>
    );
  }
  return (
    <pre className="m-0 overflow-x-auto rounded-sm border border-divider bg-neutral-100 p-2 text-sm leading-body whitespace-pre-wrap [word-break:break-word]">
      {JSON.stringify(props.value, null, 2)}
    </pre>
  );
}

// ── Lifecycle ─────────────────────────────────────────────
// packet: US-AUD-004@009e809 (story+rules snapshot hash — EP-AUD-02 lead story; co-stories US-AUD-005@009e809 · US-AUD-006@009e809)
// generated: 2026-08-09 by story-coder v1 (W0 frontend integration lane — S61, the audit-log viewer) · AMENDED 2026-08-10 by story-coder v1 (path-tenancy lane — PO ruling 2026-08-10: SPA `/{tenant}/…`, API `/api/{tenant}/…`)
// checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-09)
// gates: trace_lint✔ run_gates✔ (11 PASS · 0 FAIL · 1 SKIP) tsc✔ eslint✔ vitest 296 passed / 83 todo across 30 files✔ (239+72 baseline unchanged and green; this packet adds 57 passing + 11 todo — the todos are browser-interaction, server/RLS and unbuilt-neighbour-screen scope) · 2026-08-10 path-tenancy re-run: tsc✔ eslint✔ vitest 529 passed / 134 todo across 44 files✔ (509 passed / 132 todo was the pre-lane baseline — the suite grew, nothing was dropped) · vite build✔ · run_gates 11 PASS · 0 FAIL · 1 SKIP · trace_lint✔
// exceptions: E3 BR-AUD-009's MODULE filter and BR-AUD-004's action-type CLASS filter are NOT rendered — both are properties of the US-AUD-002 event-code catalog, which does not exist; the action filter therefore takes the action CODE (what the server filters on) and the gap is stated on the field rather than faked with an invented option list — same gap the backend reported · E3 the Entity cell is a LABEL, not a link: this app has no invoice/account/asset detail route yet (US-AUD-005 TC-3's S30 target is unbuilt), and US-AUD-005 TC-6 already rules a non-linkable entity degrades to a label — reported · E3 Source + request_metadata are served null (GAP AUD-D2, no B2 column) and render present-but-empty with the reason, per US-AUD-004 §5 · E3 `POST /audit-log/export` enqueues through core.jobs, which has NO registered store on this deployment, and `GET /jobs/{id}` has no registered route in config/urls.py — the export therefore fails loudly today and the failure renders as the plain-language A18 state; the 202→poll path is wired to the ratified 11b §2.17 contract and is untested against a live endpoint (both gaps reported by the backend packets) · E3 the related-approval reference (US-AUD-005 TC-2) is a payload-carried ref with no ratified key name in the drawer contract — it renders inside the before/after payload it lives in, and no separate linked field is invented · E4 tenant TZ + date format arrive as props with seed fallbacks until US-SHL-013's formatting-service wiring lands (same posture as the S63 calendar) — reported · E4 `GET /users` is System-Admin-only, so for an Executive the actor picker degrades from the BR-SHL-033 searchable select to an id field, with the reason on the field
// exceptions: [retention-surface lane 2026-08-16] this screen gained ONE control — "Data retention" — and it is the only thing that makes RetentionRunsPage reachable. US-MET-020's run ledger had a migration, a management command and a kernel and no reader anywhere, so an operator under a 7-year obligation could not answer "has it ever run?". The link is a NAVIGATION and grants nothing: the retention read carries the same BR-AUD-009 gate this screen does, and it can trigger no run (BR-MET-055 "never manual")
// gates: [DEF-2376/2378 lane 2026-09-02] tsc✔ · eslint --max-warnings 0✔ · vitest — the four audit files 58 passed / 8 todo✔, and the whole suite 3,863 passed with ONE failure that is not this lane's (`features/tenancy/provisioningSteps.test.ts`, the CR-064 lane; a second run of the same tree failed instead on `SettingsServicesShareUnits.dom.test.tsx`, also not this lane's — neither file is touched here) · run_gates 56 PASS / 13 FAIL / 3 SKIP against a 55/13/3 baseline taken BEFORE a line moved: **the thirteen failures are the SAME thirteen gates, named one by one, and G71 is the extra pass** · G69✔ G71✔ G44✔ G15✔ G31✔ G43✔ G45✔ · RED-PROVED FIRST (law 7): G69 clause 2 reported `AuditLogPage.tsx:132 `${row.entity_type} · ${row.entity_id}`` and one more on the rate-change history before either was changed, and `AuditToolbarAlignment.dom.test.tsx` failed on the restored helper with *f.action: the control is child 2, not 1*
// exceptions: [DEF-2378 lane 2026-09-02] ⚠ THE E3 ABOUT THE ENTITY CELL IS AMENDED, NOT CLOSED. It still degrades to a LABEL rather than a link — this app has no invoice/account/asset detail route — but the label no longer carries the id. What a person reads is the KIND of record; the id travels on `title` and `data-audit-entity-id`. **A NAME is not available on this screen and that was checked, not assumed** — see `auditEntityLabel`'s docstring for the three reasons · E4 the actor filter's degraded state keeps its explanation, moved OUT of the field to one sentence for the section (B14 rule 32), because inside the field it was the second thing knocking this toolbar out of line · E3 **S61 CANNOT USE `components/FilterBar`** — FilterBar renders a checkbox per option and five of these six filters have no option list at all — so its panel takes a whole toolbar line and the export and column controls sit beneath it. Stated rather than left as the default nobody looked at
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
