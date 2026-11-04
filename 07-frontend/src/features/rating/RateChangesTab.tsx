// ── Trace ──────────────────────────────────────────────
// Story:    US-RAT-010 (effective-dated versioning + the S9 History view over the
//           compliance log) · US-RAT-011 (bulk rate update: select → change → preview →
//           reason + effective date → apply)
//           Screens: S9 (History)
// Rules:    BR-RAT-007 (a historical bill reprices on the version in force on its SERVICE
//           date) · BR-RAT-017 (7-year reproducibility) · BR-RAT-037 (in-force versions
//           are never edited in place; the log is APPEND-ONLY and reason is required) ·
//           BR-RAT-040 (one batch = one reason + one effective date + one actor; the apply
//           is atomic; batches are append-only and NEVER re-run) · BR-SHL-010 (only
//           declared capabilities render) · BR-SHL-011 (URL grammar) · BR-SHL-012 (the six
//           A18 states) · BR-SHL-020 (plain-language failure) · BR-SHL-025 (disabled with
//           reason) · BR-SHL-032 (the confirm NAMES the action) · BR-SHL-033 (date pickers,
//           searchable long lists) · BR-SHL-034 (dates via the shared formatter)
// ───────────────────────────────────────────────────────
// The S9 History view and the bulk rate change that writes into it.
//
// Two honesty rules govern this file:
//
//   1. **The log is read-only by construction.** BR-RAT-037 makes
//      `rate_change_log` append-only and the API exposes no mutation route for
//      it — so there is no edit, delete or annotate control below, not even a
//      disabled one. A disabled control would imply a permission could unlock
//      it; none can.
//
//   2. **The apply never fakes progress.** `POST /rate-changes` answers 202 +
//      job_id and the client polls `GET /jobs/{id}` through the ONE helper.
//      That job store is NOT registered on this deployment and `/jobs/{id}` has
//      no route, so the apply fails LOUDLY and the server's own refusal is what
//      renders. There is no spinner that resolves on its own, and no toast that
//      claims N schedules were updated when nothing was.
//
// Every price in a preview row is the server's decimal string on both sides of
// the arrow — 0.11 → 0.1133 is rendered, never computed here.
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { useNavigate, useSearchParams } from "react-router-dom";

import { api } from "@/api/client";
import type { ApiClient } from "@/api/client";
import {
  BULK_CHANGE_KINDS,
  getPlans,
  getRateChanges,
  getRateSchedules,
  previewRateChange,
  requestRateChange,
} from "@/api/endpoints";
import type {
  RateChangeBody,
  RateChangeEntityRef,
  RateChangePreview,
  RateChangeRow,
} from "@/api/endpoints";
import { REFERENCE_STALE_MS, queryKeys } from "@/api/queryClient";
import { Button } from "@/components/Button";
import { ConfirmDialog } from "@/components/ConfirmDialog";
import { DataTable } from "@/components/DataTable";
import { DateCell } from "@/components/DateCell";
import type { RegionalDateFormat } from "@/components/DateCell";
import { FilterBar } from "@/components/FilterBar";
import {
  CheckboxField,
  DatePickerField,
  ModalShell,
  SelectField,
  TextField,
} from "@/components/FormModal";
import {
  FailedWithRetry,
  LoadingSkeleton,
  PermissionDenied,
  WorkingButton,
} from "@/components/StateFrame";
import { parseTableParams, serializeTableParams } from "@/components/tableTypes";
import type { TableConfig, TableRequestState } from "@/components/tableTypes";
import { useToast } from "@/components/Toast";
import { Note } from "@/components/TextBits";
import { ListExportButton } from "@/features/exports/ListExportButton";
import {
  RefusalNotice,
  apiErrorText,
  isPermissionDenied,
  refusalOf,
} from "@/features/tenancy/settingsShared";
import type { Refusal } from "@/features/tenancy/settingsShared";
import { useTenantPath } from "@/routing/tenantPath";

import {
  DASHBOARD_ROUTE,
  GuardedButton,
  decimalShapeError,
  enumLabel,
  isDecimalShape,
} from "./ratingShared";
import type { RatingTabRender, Translator } from "./ratingShared";

// ── Pure pieces ────────────────────────────────────────────────────────────

/** History's entity vocabulary — the five kinds it lists. Tax and discount
 *  arrived with `DEF-RAT-10032` (PO 2026-10-09, *"(a) Show them on History
 *  too"*): their edits are read from the audit trail beside the rate log, in
 *  one server page (`selectors.history_list_queryset`). */
export const HISTORY_ENTITY_TYPES = ["schedule", "plan", "charge", "tax", "discount"] as const;

/** BR-SHL-011: the open diff is VIEW state, so a diff is a shareable link. */
export const DIFF_PARAM = "diff";

// ⚠ `diffFields` — the client-side walk over the two stored payloads — IS GONE
// (`DEF-RAT-10029`). It printed whatever the payload held: a field KEY
// (`account_type_id`) as the label and a foreign uuid as the value, and with no
// stored `before` it listed every fact of a plan as changed (*"… and 89 more"*).
// The server now words each changed fact (`history_words.history_rows`), with
// every id resolved to a name or code, and this file only lays it out.

export function historyTableConfig(
  t: Translator,
  cells: {
    when: (row: RateChangeRow) => JSX.Element;
    entity: (row: RateChangeRow) => string;
    change: (row: RateChangeRow) => JSX.Element;
    actor: (row: RateChangeRow) => JSX.Element;
    publishedBy: (row: RateChangeRow) => JSX.Element;
    batch: (row: RateChangeRow) => JSX.Element;
  },
): TableConfig<RateChangeRow> {
  return {
    screenId: "S9.history",
    columns: [
      {
        key: "changed_at",
        label: t("rating.history.col.when"),
        sortable: true,
        identity: true,
        cell: cells.when,
      },
      { key: "entity", label: t("rating.history.col.entity"), sortable: true, cell: cells.entity },
      { key: "change", label: t("rating.history.col.change"), cell: cells.change },
      { key: "reason", label: t("rating.history.col.reason") },
      { key: "actor", label: t("rating.history.col.actor"), sortable: true, cell: cells.actor },
      // GAP: the matrix names a "Published by" column, but `rate_change_log`
      // stores ONE actor and no separate publisher (r5 #14). The column is
      // present and states that, rather than repeating the actor under a second
      // heading — which would read as two people having touched the change.
      // DEF-RAT-10029 — the person who applied a bulk change, by NAME. This
      // column rendered the batch cell (a raw batch uuid) until then.
      { key: "published_by", label: t("rating.history.col.publishedBy"), cell: cells.publishedBy },
      { key: "batch_id", label: t("rating.history.col.batch"), cell: cells.batch },
      { key: "effective", label: t("rating.history.col.effective"), defaultVisible: false },
    ],
    getRowId: (row) => row.id,
    // ⚠ **THIS ROW DECLARED THREE LEGS AND THE SERVER MATCHES NEITHER TWO OF
    // THEM — DEF-1002, found by CR-041 task 2 reading every predicate.**
    // It read `["entity_name", "reason", "actor"]`. `rating/selectors.py::
    // history_list` filters `Q(reason__icontains) | Q(entity_type__icontains)`:
    //   · `entity_name` — the "What changed" column — is NOT searched;
    //   · `actor` — the "Who" column — is NOT searched;
    //   · `entity_type` IS searched and was not declared.
    // Two of the three fields a clerk would most obviously type (the plan's
    // name, the person who changed it) silently matched nothing, and because
    // the box carried no prompt either, nothing on screen said so. The row now
    // states what the endpoint does; **DEF-1002 carries the missing legs**, and
    // widening the predicate is a server change with its own review.
    searchFields: ["reason", "entity_type"],
    // B14 rule 19 — and the prompt is the honest half of DEF-1002. `entity_type`
    // is a small enum (plan · tariff · charge · tax …) rendered through
    // `rating.history.entity.*`, so to a clerk it is the RECORD TYPE, which is
    // what the copy calls it. It is also offered as a chip beside the box; a
    // field that is both searchable and filterable is fine, a field that is
    // neither and is advertised is not.
    searchPlaceholder: "rating.history.searchPlaceholder",
    filters: [
      {
        name: "entity_type",
        label: t("rating.history.filter.entityType"),
        options: HISTORY_ENTITY_TYPES.map((value) => ({
          value,
          label: t(`rating.history.entity.${value}`),
        })),
      },
      { name: "batch", label: t("rating.history.filter.batch"), options: [] },
      { name: "from", label: t("rating.history.filter.from"), options: [] },
      { name: "to", label: t("rating.history.filter.to"), options: [] },
    ],
    defaultSort: { sort: "changed_at", dir: "desc" }, // the matrix: newest first
  };
}

/** The bulk form's state. `value` is a STRING — it is a price multiplier or a price. */
export interface BulkDraft {
  entities: RateChangeEntityRef[];
  kind: string;
  value: string;
  effectiveFrom: string;
  reason: string;
}

export function emptyBulkDraft(): BulkDraft {
  return { entities: [], kind: BULK_CHANGE_KINDS[0], value: "", effectiveFrom: "", reason: "" };
}

/**
 * Whether the draft is COMPLETE enough to ask the server for a preview. This
 * is a completeness check, never a rules check: "is there a number here at
 * all" and "did the compliance reason get typed" (BR-RAT-040). Whether +0 % is
 * legal, whether the date collides with a pending version, whether an entity
 * has a version to change — all the SERVER's, all rendered from its refusal.
 */
export function bulkDraftReady(draft: BulkDraft): boolean {
  return (
    draft.entities.length > 0 &&
    isDecimalShape(draft.value) &&
    draft.effectiveFrom !== "" &&
    draft.reason.trim() !== ""
  );
}

export function bulkBody(draft: BulkDraft): RateChangeBody {
  return {
    entities: draft.entities,
    change: { kind: draft.kind, value: draft.value.trim() },
    effective_from: draft.effectiveFrom,
    reason: draft.reason.trim(),
  };
}

// ── The tab ────────────────────────────────────────────────────────────────

export interface RateChangesTabProps {
  readOnly: boolean;
  client?: ApiClient;
  timeZone: string;
  dateFormat: RegionalDateFormat;
  /** US-SHL-020 addendum r2 — the bulk-change modal is this tab's own state. */
  render: RatingTabRender;
}

export function RateChangesTab(props: RateChangesTabProps) {
  const { t } = useTranslation();
  const translate: Translator = (key, params) => t(key, params);
  const navigate = useNavigate();
  const tenantPath = useTenantPath();
  const client = props.client ?? api;
  const [searchParams, setSearchParams] = useSearchParams();
  const [bulkOpen, setBulkOpen] = useState(false);

  const config = historyTableConfig(translate, {
    when: (row) =>
      row.changed_at === null ? (
        <span className="rating-empty">—</span>
      ) : (
        <button
          type="button"
          className="rating-link"
          aria-label={t("rating.history.openDiff", { entity: row.entity_name ?? row.entity_type })}
          onClick={() => openDiff(row.id)}
        >
          {/* BR-SHL-034: the instant renders in tenant time through DateCell. */}
          <DateCell
            value={row.changed_at}
            timeZone={props.timeZone}
            dateFormat={props.dateFormat}
            withTime
          />
        </button>
      ),
    // ⚠ THE `?? row.entity_id` FALLBACK IS GONE (DEF-2378). This read
    //     `${enumLabel(…, row.entity_type)} · ${row.entity_name ?? row.entity_id}`
    //    so a row whose entity has no name — a deleted one, or a kind the server
    //    stores without one — printed a database uuid as the cell's value, which
    //    B14 rule 31 forbids outright. It is the same expression the Product
    //    Owner reported on the audit log the day this was found, and G69 clause 2
    //    caught this one on the way past. A named row is unchanged; a nameless
    //    one now says what KIND of thing changed, which is what the row is about.
    entity: (row) => {
      const kind = enumLabel(translate, "rating.history.entity", row.entity_type);
      return row.entity_name === null || row.entity_name === undefined || row.entity_name === ""
        ? kind
        : `${kind} · ${row.entity_name}`;
    },
    change: (row) => <ChangeSummary row={row} />,
    // DEF-RAT-10029 — the server names the person (`actor.name`); the id it
    // also serves is the filter's value and is never printed (B14 rule 31).
    actor: (row) => <ActorCell row={row} />,
    // Only a BULK change has a publisher (the batch's actor); a single change
    // has none, which is a dash rather than "Unknown user".
    publishedBy: (row) =>
      row.is_batch ? (
        <PersonName name={row.published_by.name} />
      ) : (
        <span className="rating-empty">—</span>
      ),
    batch: (row) => <BatchCell row={row} />,
  });

  const state = parseTableParams(searchParams, config);
  const openDiffId = searchParams.get(DIFF_PARAM);

  function writeParams(next: TableRequestState, diffId: string | null): void {
    const params = serializeTableParams(next, config);
    if (diffId !== null) {
      params.set(DIFF_PARAM, diffId);
    }
    setSearchParams(params, { replace: true });
  }

  function setState(next: TableRequestState): void {
    writeParams(next, openDiffId);
  }

  function openDiff(rowId: string | null): void {
    writeParams(state, rowId);
  }

  const listQuery = useQuery({
    queryKey: queryKeys.rateChanges(serializeTableParams(state, config).toString()),
    queryFn: () =>
      getRateChanges(
        {
          q: state.q,
          filters: state.filters,
          sort: state.sort,
          dir: state.dir,
          page: state.page,
          per: state.per,
        },
        client,
      ),
  });

  // Both failures keep the header and strip — see ChargeCodesTab for why.
  if (listQuery.data === undefined && listQuery.isError) {
    if (isPermissionDenied(listQuery.error)) {
      return (
        <>
          {props.render({
            body: (
              <PermissionDenied
                helper={t("rating.denied")}
                onBack={() => navigate(tenantPath(DASHBOARD_ROUTE))}
              />
            ),
          })}
        </>
      );
    }
    return (
      <>
        {props.render({
          body: (
            <FailedWithRetry
              title={t("rating.history.failedTitle")}
              reason={apiErrorText(listQuery.error, translate)}
              onRetry={() => void listQuery.refetch()}
              onDownloadReport={() => undefined}
              onCancel={() => void listQuery.refetch()}
            />
          ),
        })}
      </>
    );
  }

  const openRow = (listQuery.data?.results ?? []).find((row) => row.id === openDiffId) ?? null;

  return (
    <>
      {props.render({
        action: (
          <GuardedButton
            readOnly={props.readOnly}
            readOnlyReason={t("rating.readOnlyReason")}
            variant="primary"
            onClick={() => setBulkOpen(true)}
          >
            {t("rating.bulk.open")}
          </GuardedButton>
        ),
        body: (
          <div className="rating-tab">
            {/* The append-only note stays in the BODY: it explains the table
                below it, not the button that moved into the header. */}
            <p className="rating-note">{t("rating.history.appendOnly")}</p>

            <DataTable<RateChangeRow>
              config={config}
              state={state}
              onStateChange={setState}
              rows={listQuery.data?.results ?? []}
              totalRows={listQuery.data?.count ?? null}
              loading={listQuery.isPending}
              filterBarSlot={
                <FilterBar filters={config.filters ?? []} state={state} onStateChange={setState} />
              }
              downloadSlot={
                // EP-RAT-04's capability row: CSV (IS-9) over the append-only
                // compliance log — the one export a regulator is most likely to ask
                // for, and itself audited server-side (BR-SHL-016).
                <ListExportButton resource="rate-changes" state={state} client={client} />
              }
              empty={{
                title: t("rating.history.emptyTitle"),
                helper: t("rating.history.emptyHelper"),
                ctaLabel: t("rating.bulk.open"),
                onCta: () => !props.readOnly && setBulkOpen(true),
              }}
            />

            {openRow !== null && (
              <DiffDrawer
                row={openRow}
                timeZone={props.timeZone}
                dateFormat={props.dateFormat}
                onClose={() => openDiff(null)}
              />
            )}

            {bulkOpen && (
              <BulkRateChangeModal
                client={client}
                dateFormat={props.dateFormat}
                onClose={() => setBulkOpen(false)}
              />
            )}
          </div>
        ),
      })}
    </>
  );
}

function ChangeSummary(props: { row: RateChangeRow }) {
  const { t } = useTranslation();
  const { row } = props;
  if (!row.before_kept) {
    return <span className="rating-muted">{t("rating.history.beforeNotKept")}</span>;
  }
  const changes = row.changes;
  if (changes.length === 0) {
    return <span className="rating-empty">{t("rating.history.noFieldDiff")}</span>;
  }
  const [first, ...rest] = changes;
  return (
    <span className="rating-diff-summary">
      {/* The server's words: *Minimum bill: $10.00 → $12.00*. */}
      <span className="rating-diff-field">{first.field}:</span>{" "}
      <span className="rating-diff-before">{first.before}</span>
      <span aria-hidden="true"> → </span>
      <span className="rating-diff-after">{first.after}</span>
      {rest.length > 0 && (
        <span className="rating-muted">
          {" "}
          {t("rating.history.moreFields", { count: rest.length })}
        </span>
      )}
    </span>
  );
}

function ActorCell(props: { row: RateChangeRow }) {
  const { t } = useTranslation();
  if (props.row.actor_user_id === null) {
    // A batch applied by the worker carries the enqueuing actor; a null here is
    // a SYSTEM write, named rather than blanked.
    return <span className="rating-empty">{t("rating.history.systemActor")}</span>;
  }
  return <PersonName name={props.row.actor.name} />;
}

/** A person by name; a person the server cannot name is said so — never an id. */
function PersonName(props: { name: string | null }) {
  const { t } = useTranslation();
  if (props.name === null || props.name === "") {
    return <span className="rating-empty">{t("rating.history.unknownActor")}</span>;
  }
  return <span>{props.name}</span>;
}

function BatchCell(props: { row: RateChangeRow }) {
  const { t } = useTranslation();
  // DEF-RAT-10029 — a bulk change printed its batch uuid here.
  return (
    <span className={props.row.is_batch ? "rating-batch" : "rating-empty"}>
      {t(props.row.is_batch ? "rating.history.bulkChange" : "rating.history.singleChange")}
    </span>
  );
}

// ── The diff drawer (US-RAT-010 TC-3 "View diff") ──────────────────────────

function DiffDrawer(props: {
  row: RateChangeRow;
  timeZone: string;
  dateFormat: RegionalDateFormat;
  onClose: () => void;
}) {
  const { t } = useTranslation();
  const { row } = props;
  return (
    // LAW 0: the ONE dialog implementation, reused — not a second drawer.
    <ModalShell
      title={t("rating.history.drawer.title")}
      kicker={t("rating.kicker")}
      onClose={props.onClose}
    >
      <div className="modal-body rating-drawer">
        <dl className="rating-facts">
          <dt>{t("rating.history.col.when")}</dt>
          <dd>
            {row.changed_at === null ? (
              "—"
            ) : (
              <DateCell
                value={row.changed_at}
                timeZone={props.timeZone}
                dateFormat={props.dateFormat}
                withTime
              />
            )}
          </dd>
          <dt>{t("rating.history.col.entity")}</dt>
          <dd>{row.entity_name || enumLabel(t, "rating.history.entity", row.entity_type) /* DEF-SHL-6348: the table's own absence (DEF-2378) */}</dd>
          <dt>{t("rating.history.col.reason")}</dt>
          {/* BR-RAT-037: reason is NOT NULL — a change without one never wrote. */}
          <dd>{row.reason}</dd>
          <dt>{t("rating.history.col.actor")}</dt>
          <dd>
            <ActorCell row={row} />
          </dd>
          <dt>{t("rating.history.col.batch")}</dt>
          <dd>
            <BatchCell row={row} />
          </dd>
        </dl>
        {/* DEF-RAT-10029 — the same worded list the CHANGE cell reads, as a
            table. It was two raw JSON dumps of the stored payloads, ids and
            all. */}
        {!row.before_kept && <Note>{t("rating.history.beforeNotKept")}</Note>}
        {row.changes.length === 0 ? (
          <p className="rating-empty">{t("rating.history.noFieldDiff")}</p>
        ) : (
          <table className="rating-preview">
            <thead>
              <tr>
                <th>{t("rating.bulk.field")}</th>
                <th>{t("rating.history.before")}</th>
                <th>{t("rating.history.after")}</th>
              </tr>
            </thead>
            <tbody>
              {row.changes.map((change, index) => (
                <tr key={`${change.field}-${index}`}>
                  <td>{change.field}</td>
                  <td>{change.before}</td>
                  <td>{change.after}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
        <Note>{t("rating.history.appendOnly")}</Note>
      </div>
      <div className="modal-foot">
        <Button variant="secondary"  onClick={props.onClose}>
          {t("forms.close")}
        </Button>
      </div>
    </ModalShell>
  );
}

// ── US-RAT-011 — the bulk rate change ──────────────────────────────────────

function BulkRateChangeModal(props: {
  client: ApiClient;
  dateFormat: RegionalDateFormat;
  onClose: () => void;
}) {
  const { t } = useTranslation();
  const translate: Translator = (key, params) => t(key, params);
  const fireToast = useToast();
  const queryClient = useQueryClient();
  const [draft, setDraft] = useState<BulkDraft>(emptyBulkDraft);
  const [preview, setPreview] = useState<RateChangePreview | null>(null);
  const [refusal, setRefusal] = useState<Refusal | null>(null);
  const [confirming, setConfirming] = useState(false);

  // The entity pickers. Only ACTIVATED schedules can be batched (a schedule
  // with no version has nothing to change — the server says so too), and plans
  // are batched through their per-service base charges.
  const schedulesQuery = useQuery({
    queryKey: queryKeys.rateSchedules("bulk"),
    queryFn: () => getRateSchedules({ per: 200 }, props.client),
    staleTime: REFERENCE_STALE_MS,
  });
  const plansQuery = useQuery({
    queryKey: queryKeys.plans("bulk"),
    queryFn: () => getPlans({ per: 200 }, props.client),
    staleTime: REFERENCE_STALE_MS,
  });

  const runPreview = useMutation({
    mutationFn: () => previewRateChange(bulkBody(draft), props.client),
    onSuccess: (result) => {
      setRefusal(null);
      setPreview(result);
    },
    onError: (error: unknown) => {
      // US-RAT-011 TC-5: a conflicting pending version aborts the WHOLE batch,
      // naming the entity. It surfaces HERE, before anything is written.
      setPreview(null);
      setRefusal(refusalOf(error, translate));
    },
  });

  const apply = useMutation({
    mutationFn: async () => {
      const accepted = await requestRateChange(bulkBody(draft), props.client);
      // B12 r1 / 11b §2.17: a 202 is a JOB — polled through the ONE helper.
      return props.client.pollJob(accepted.job_id);
    },
    onSuccess: (job) => {
      setConfirming(false);
      if (job.status === "succeeded") {
        fireToast(t("rating.bulk.toast.applied", { count: preview?.preview.length ?? 0 }));
        void queryClient.invalidateQueries({ queryKey: ["rate-changes"] });
        void queryClient.invalidateQueries({ queryKey: ["rate-schedules"] });
        void queryClient.invalidateQueries({ queryKey: ["plans"] });
        props.onClose();
        return;
      }
      // A job that came back FAILED says so — it never becomes a success toast.
      setRefusal({ message: job.error ?? t("rating.bulk.jobFailed"), brRef: "BR-RAT-040" });
    },
    onError: (error: unknown) => {
      // The honest path today: `POST /rate-changes` enqueues through a job store
      // that is NOT registered on this deployment, and `GET /jobs/{id}` has no
      // route — so this is where the run ends, with the server's own words.
      // Nothing is retried and no progress is drawn (BR-SHL-020).
      setConfirming(false);
      setRefusal(refusalOf(error, translate));
    },
  });

  function toggleEntity(ref: RateChangeEntityRef, checked: boolean): void {
    // Any change to the SELECTION invalidates the preview: IS-6 requires the
    // diffs the user approves to be the diffs that apply.
    setPreview(null);
    setDraft({
      ...draft,
      entities: checked
        ? [...draft.entities, ref]
        : draft.entities.filter((item) => !(item.type === ref.type && item.id === ref.id)),
    });
  }

  function patch(next: Partial<BulkDraft>): void {
    setPreview(null);
    setDraft({ ...draft, ...next });
  }

  const selected = (ref: RateChangeEntityRef): boolean =>
    draft.entities.some((item) => item.type === ref.type && item.id === ref.id);

  return (
    <ModalShell title={t("rating.bulk.title")} kicker={t("rating.kicker")} onClose={props.onClose}>
      <div className="modal-body rating-bulk">
        <p className="field-help">{t("rating.bulk.intro")}</p>

        <h5 className="rating-form-section">{t("rating.bulk.step.entities")}</h5>
        {schedulesQuery.isPending || plansQuery.isPending ? (
          <LoadingSkeleton variant="card" />
        ) : (
          <fieldset className="rating-checklist">
            <legend>{t("rating.bulk.schedules")}</legend>
            {(schedulesQuery.data?.results ?? []).map((card) => (
              <CheckboxField
                key={card.id}
                id={`bulk-schedule-${card.id}`}
                label={`${card.name} · ${card.service_name}`}
                checked={selected({ type: "schedule", id: card.id })}
                onChange={(checked) => toggleEntity({ type: "schedule", id: card.id }, checked)}
              />
            ))}
            <legend>{t("rating.bulk.plans")}</legend>
            {(plansQuery.data?.results ?? []).map((plan) => (
              <CheckboxField
                key={plan.id}
                id={`bulk-plan-${plan.id}`}
                label={`${plan.name} · ${plan.code}`}
                checked={selected({ type: "plan", id: plan.id })}
                onChange={(checked) => toggleEntity({ type: "plan", id: plan.id }, checked)}
              />
            ))}
          </fieldset>
        )}

        <h5 className="rating-form-section">{t("rating.bulk.step.change")}</h5>
        <SelectField
          id="bulk-kind"
          label={t("rating.bulk.kindLabel")}
          value={draft.kind}
          onChange={(kind) => patch({ kind })}
          options={BULK_CHANGE_KINDS.map((value) => ({
            value,
            label: t(`rating.bulk.kind.${value}`),
          }))}
        />
        <TextField
          id="bulk-value"
          label={t(draft.kind === "percent" ? "rating.bulk.percentLabel" : "rating.bulk.setLabel")}
          value={draft.value}
          onChange={(value) => patch({ value })}
          numeric
          // NUMERIC(18,6) all the way through — 0.11 × 1.03 = 0.1133 is the
          // SERVER's multiplication, shown in the preview, never rounded here.
          help={t("rating.bulk.valueHelp")}
          error={decimalShapeError(draft.value) === null ? undefined : t("rating.error.notDecimal")}
        />
        <DatePickerField
          id="bulk-effective-from"
          label={t("rating.effectiveFrom")}
          value={draft.effectiveFrom}
          onChange={(effectiveFrom) => patch({ effectiveFrom })}
          dateFormat={props.dateFormat}
          required
          help={t("rating.bulk.effectiveHelp")}
        />
        <TextField
          id="bulk-reason"
          label={t("rating.bulk.reasonLabel")}
          value={draft.reason}
          onChange={(reason) => patch({ reason })}
          required
          multiline
          // BR-RAT-040 / r5 #14: ONE reason per batch, copied to every log row.
          help={t("rating.bulk.reasonHelp")}
        />

        <RefusalNotice refusal={refusal} />

        <h5 className="rating-form-section">{t("rating.bulk.step.preview")}</h5>
        {preview === null ? (
          <p className="field-help">{t("rating.bulk.previewPrompt")}</p>
        ) : (
          <BulkPreview preview={preview} />
        )}
      </div>

      <div className="modal-foot">
        <Button variant="ghost"  onClick={props.onClose}>
          {t("forms.cancel")}
        </Button>
        <Button
          variant="secondary"
          disabled={!bulkDraftReady(draft) || runPreview.isPending}
          onClick={() => runPreview.mutate()}
        >
          {t("rating.bulk.preview")}
        </Button>
        {/* IS-6: the money action is unreachable until the diffs have been
            fetched and shown. Apply is not "validate then write" — it is
            "write exactly what was previewed". */}
        <WorkingButton working={apply.isPending} onClick={() => setConfirming(true)}>
          {t("rating.bulk.apply")}
        </WorkingButton>
      </div>

      {confirming && preview !== null && (
        <ConfirmDialog
          title={t("rating.bulk.confirm.title", { count: preview.preview.length })}
          consequence={t("rating.bulk.confirm.body", {
            count: preview.preview.length,
            date: draft.effectiveFrom,
            reason: draft.reason.trim(),
          })}
          confirmLabel={t("rating.bulk.confirm.verb", { count: preview.preview.length })}
          working={apply.isPending}
          onConfirm={() => apply.mutate()}
          onCancel={() => setConfirming(false)}
        />
      )}
      {confirming && preview === null && (
        <ConfirmDialog
          title={t("rating.bulk.confirm.needsPreview.title")}
          consequence={t("rating.bulk.confirm.needsPreview.body")}
          confirmLabel={t("rating.bulk.preview")}
          working={runPreview.isPending}
          onConfirm={() => {
            setConfirming(false);
            runPreview.mutate();
          }}
          onCancel={() => setConfirming(false)}
        />
      )}
    </ModalShell>
  );
}

/** Every before → after the server computed, rendered as the strings it sent. */
export function BulkPreview(props: { preview: RateChangePreview }) {
  const { t } = useTranslation();
  if (props.preview.preview.length === 0) {
    return <p className="rating-empty">{t("rating.bulk.previewEmpty")}</p>;
  }
  return (
    <div className="rating-bulk-preview">
      {props.preview.preview.map((entity) => (
        <section key={`${entity.type}:${entity.id}`}>
          <h6>{entity.name}</h6>
          <table className="rating-preview">
            <thead>
              <tr>
                <th>{t("rating.bulk.field")}</th>
                <th>{t("rating.history.before")}</th>
                <th>{t("rating.history.after")}</th>
              </tr>
            </thead>
            <tbody>
              {entity.changes.map((change) => (
                <tr key={change.field}>
                  <td>{change.field}</td>
                  <td>{change.before}</td>
                  <td>{change.after}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </section>
      ))}
    </div>
  );
}

// ── Lifecycle ─────────────────────────────────────────────
// packet: US-RAT-010@f69a661 (story+rules snapshot hash — EP-RAT-04; co-story US-RAT-011@f69a661)
// generated: 2026-08-09 by story-coder v1 (W1 Plans & Rates frontend lane — S9 History + bulk) · AMENDED 2026-08-10 by story-coder v1 (path-tenancy lane — PO ruling 2026-08-10: SPA `/{tenant}/…`, API `/api/{tenant}/…`)
// checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-09)
// gates: [list-export lane 2026-08-10] tsc✔ eslint --max-warnings 0✔ vitest 501 passed / 132 todo across 43 files✔ (487+130 was the baseline; this lane adds 14 passing + 2 todo and converted 3 stale negative assertions into positives) · 5 locales × 2066 keys, identical sets · run_gates 11-PASS/0-FAIL/1-SKIP✔ · trace_lint✔ · trace_lint✔ (227 stories, 459 BR refs, 60 OQs) run_gates✔ (11 PASS · 0 FAIL · 1 SKIP) tsc✔ eslint✔ vitest 487 passed / 130 todo across 42 files✔ (399+111 baseline unchanged and green; this packet adds 88 passing + 19 todo across 5 files — every todo is browser-interaction, server/RLS-isolation or unbuilt-neighbour-module scope) · 2026-08-10 path-tenancy re-run: tsc✔ eslint✔ vitest 529 passed / 134 todo across 44 files✔ (509 passed / 132 todo was the pre-lane baseline — the suite grew, nothing was dropped) · vite build✔ · run_gates 11 PASS · 0 FAIL · 1 SKIP · trace_lint✔
// exceptions: E3 `POST /rate-changes` enqueues through core.jobs, which has NO registered store on this deployment, and `GET /jobs/{id}` has no registered route — the apply therefore FAILS LOUDLY and the server's refusal renders; the 202→poll path is wired to the ratified 11b §2.17 contract and is untested against a live endpoint (same gap the backend and S61 packets reported) · E3 EP-RAT-04's matrix names a "Published by" column, but `rate_change_log` stores ONE actor and no publisher (r5 #14) — the column renders present-and-explained rather than duplicating the actor · E3 the matrix's "+Effective date" column has no field on the log row (the new version carries the date, the log row does not) — it renders empty and is reported · E3 CLOSED (list-export lane 2026-08-10): the matrix's CSV export for History is WIRED to POST /exports — before/after export as canonical sorted JSON (a CSV cannot render the diff drawer) and "Published by" exports present-and-empty, the same gap this screen renders · E4 the actor column shows the stored user id: `GET /users` is System-Admin-only, so resolving names would blank the column for exactly the Executive the compliance trail is for
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
