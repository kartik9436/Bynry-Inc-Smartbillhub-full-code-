// ── Trace ────────────────────────────────────────────────────────────────
// Story:    US-INT-037 (EP-INT-10) — S143, *Their words for our things*: a
//           foreign name is a row, never a column. Frames 45.1 (the mapping
//           editor) · 81.2 (how they say a customer paid). US-INT-039 — the
//           format picker is the manifest's `file_format` field on S141, drawn
//           by the field slot wave B builds; nothing here.
// Rules:    BR-INT-032 (one row per foreign word; two of theirs may share one
//           of ours; the ledger's two columns are read, never widened —
//           OQ-INT-1480) · BR-INT-031 (an unmapped word shows RED and records
//           as Other; R02 waits on OQ-INT-1487) · B14 rule 15 (the row action
//           is an ICON with a tooltip) · rule 21 (Tailwind only; this file is
//           on route-b-migrated.txt) · rule 31 (their word and our word are
//           the visible values, never an id) · rule 32 (one sentence per
//           section; a stated absence is closed by default) · rule 33 (a fact
//           in six words or fewer) · rule 5 (two button sizes) · rule 6 (no
//           danger tier — mapping a word is reversible; the pack's red *Map it*
//           is stamped as a deviation in 08-screen-layouts.md)
// Tests:    src/features/integrations/ValueMappingPage.test.tsx
// Impacts:  src/api/integrationsEndpoints.ts (the contract) · src/App.tsx (the
//           route) · src/routing/screenIds.ts (S143 · INT-03) ·
//           src/features/integrations/IntegrationsTab.tsx (the card's link) ·
//           the eleven locale catalogues (`integrations.mappings.*`)
// ─────────────────────────────────────────────────────────────────────────
//
// ⚠ THE SECOND TAB — *Waiting for a decision*, the GIS difference queue — IS
// NOT RENDERED, AND THAT IS A STATED ABSENCE CLOSED BY DEFAULT (rule 32). It
// is US-INT-043's, arrives with wave Q, and stays stubbed on OQ-INT-1470. A
// tab strip with one live tab and one that opens on nothing is the failure
// hard-won law 2 names, so the strip here is the manifest's KINDS OF WORDS
// (tender · bounced payments · account codes), and nothing else.

import { useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useParams } from "react-router-dom";

import { api } from "@/api/client";
import type { ApiClient } from "@/api/client";

import { getMappings, putMappings } from "@/api/integrationsEndpoints";
import type {
  MappingRow,
  MappingType,
  MappingsPayload,
  MappingWrite,
} from "@/api/integrationsEndpoints";
import { queryKeys } from "@/api/queryClient";
import { refusalText } from "@/api/refusalText";
import { Button } from "@/components/Button";
import { DateCell } from "@/components/DateCell";
import type { RegionalDateFormat } from "@/components/DateCell";
import { PageHeader } from "@/components/PageHeader";
import { RowAction, RowActions } from "@/components/RowActions";
import { FailedWithRetry, LoadingSkeleton } from "@/components/StateFrame";
import { RefusalStrip } from "@/components/Surfaces";
import { Note } from "@/components/TextBits";
import { PencilIcon } from "@/components/icons";
import { useTenantPath } from "@/routing/tenantPath";
import { useRegional } from "@/features/metering/meteringShared";

const INTEGRATIONS_ROUTE = "/settings/integrations";

/**
 * Our side of a row, in words. A tenant's payment methods and accounts carry
 * the tenant's own spelling and are shown as served; a reversal reason is one
 * of four signed codes, so its word comes from the catalogue with the server's
 * English as the fallback.
 */
function ourWord(t: (key: string, options?: Record<string, unknown>) => string, row: MappingRow) {
  if (row.local_value === null) return null;
  if (row.entity_type === "reversal_reason") {
    return t(`integrations.mappings.reason.${row.local_value}`, {
      defaultValue: row.local_label ?? row.local_value,
    });
  }
  return row.local_label ?? row.local_value;
}

function choiceWord(
  t: (key: string, options?: Record<string, unknown>) => string,
  kind: string,
  choice: { value: string; label: string },
) {
  if (kind === "reversal_reason") {
    return t(`integrations.mappings.reason.${choice.value}`, { defaultValue: choice.label });
  }
  return choice.label;
}

interface EditorProps {
  row: MappingRow;
  kind: MappingType;
  saving: boolean;
  refusal: string | null;
  onSave: (localValue: string | null) => void;
  onCancel: () => void;
}

/** The inline editor: one select of OUR words, Save, Cancel — no id anywhere. */
function RowEditor(props: EditorProps) {
  const { t } = useTranslation();
  const [choice, setChoice] = useState<string>(props.row.local_value ?? "");
  const selectId = `mapping-${props.row.entity_type}-${props.row.external_value}`;
  return (
    <form
      className="flex flex-wrap items-center gap-2"
      data-mapping-editor={props.row.external_value}
      onSubmit={(event) => {
        event.preventDefault();
        props.onSave(choice === "" ? null : choice);
      }}
    >
      <label className="sr-only" htmlFor={selectId}>
        {t("integrations.mappings.choose")}
      </label>
      <select
        id={selectId}
        className="border border-field-border bg-neutral-100 px-2 py-1 text-sm text-neutral-900"
        value={choice}
        onChange={(event) => setChoice(event.target.value)}
        disabled={props.saving}
      >
        <option value="">{t("integrations.mappings.leaveUnmapped")}</option>
        {props.kind.choices.map((one) => (
          <option key={one.value} value={one.value}>
            {choiceWord(t, props.kind.entity_type, one)}
          </option>
        ))}
      </select>
      <Button type="submit" variant="primary" size="sm" disabled={props.saving}>
        {t("integrations.mappings.save")}
      </Button>
      <Button type="button" variant="secondary" size="sm" onClick={props.onCancel} disabled={props.saving}>
        {t("integrations.mappings.cancel")}
      </Button>
      {props.refusal !== null && (
        <RefusalStrip as="span" className="basis-full">
          {props.refusal}
        </RefusalStrip>
      )}
    </form>
  );
}

interface MappingRowProps {
  row: MappingRow;
  kind: MappingType;
  editing: boolean;
  saving: boolean;
  refusal: string | null;
  timeZone: string;
  dateFormat: RegionalDateFormat;
  onEdit: () => void;
  onSave: (localValue: string | null) => void;
  onCancel: () => void;
}

/**
 * One of their words → one of ours. RED when unmapped (frame 45.1), because an
 * unmapped word is money landing in the wrong bucket on a report. The action
 * is an icon (rule 15) whose accessible name is *Map it* or *Change*; for the
 * one word the writer refuses to decide (R02) it is disabled with the reason.
 */
function MappingRowView(props: MappingRowProps) {
  const { t } = useTranslation();
  const { row } = props;
  const unmapped = row.state === "unmapped";
  const word = ourWord(t, row);
  const action = unmapped ? t("integrations.mappings.mapIt") : t("integrations.mappings.change");
  return (
    <li
      className={
        unmapped
          ? "flex flex-col gap-2 border border-danger-500 bg-neutral-100 p-3"
          : "flex flex-col gap-2 border border-neutral-200 bg-neutral-100 p-3"
      }
      data-mapping-row={row.external_value}
      data-state={row.state}
    >
      <div className="flex items-center justify-between gap-3">
        <div className="flex min-w-0 flex-1 items-center gap-3">
          <code className="shrink-0 font-mono text-sm text-neutral-900">{row.external_value}</code>
          <span aria-hidden="true" className="text-neutral-400">
            →
          </span>
          {unmapped ? (
            <span className="text-sm font-medium text-danger-700" data-our-word="">
              {t("integrations.mappings.notSet")}
            </span>
          ) : (
            <span className="text-sm font-medium text-success-700" data-our-word="">
              {word}
            </span>
          )}
        </div>
        <RowActions>
          <RowAction
            label={action}
            icon={<PencilIcon />}
            reason={row.stays_other ? t("integrations.mappings.staysOther") : null}
            onClick={props.onEdit}
          />
        </RowActions>
      </div>
      {row.last_seen_at !== null && (
        <Note>
          {t("integrations.mappings.lastSeen")}{" "}
          <DateCell
            value={row.last_seen_at}
            timeZone={props.timeZone}
            dateFormat={props.dateFormat}
            withTime
          />
        </Note>
      )}
      {props.editing && (
        <RowEditor
          row={row}
          kind={props.kind}
          saving={props.saving}
          refusal={props.refusal}
          onSave={props.onSave}
          onCancel={props.onCancel}
        />
      )}
    </li>
  );
}

export interface ValueMappingPageProps {
  /** Test seam, and the same shape every Settings screen takes. */
  client?: ApiClient;
}

export function ValueMappingPage(props: ValueMappingPageProps) {
  const { t } = useTranslation();
  const params = useParams<{ key: string }>();
  const providerKey = params.key ?? "";
  const tenantPath = useTenantPath();
  const client = props.client ?? api;
  const queryClient = useQueryClient();

  const [kindChosen, setKindChosen] = useState<string | null>(null);
  const [search, setSearch] = useState("");
  const [unmappedOnly, setUnmappedOnly] = useState(false);
  const [editing, setEditing] = useState<string | null>(null);

  const mappingsQuery = useQuery({
    queryKey: queryKeys.integrationMappings(providerKey),
    queryFn: () => getMappings(client, providerKey),
  });
  // The tenant's own zone and date format for *last seen* (IS-8).
  //
  // DEF-SHL-3964 — this screen used to run its OWN copy of the shell's regional
  // query and spell its own `?? "MM/DD/YYYY"` / `?? "UTC"` fallback beside it.
  // The shell publishes the same read (same query key, so this was never a
  // second request — only a second fallback), and it renders no screen until it
  // has answered, so there is nothing left to fall back to.
  const { timeZone, dateFormat } = useRegional({});

  const save = useMutation({
    mutationFn: (write: MappingWrite) => putMappings(client, providerKey, [write]),
    // The answer IS the refreshed document — rows, counts and choices — so the
    // cache takes the server's truth, never a guess made here.
    onSuccess: (next: MappingsPayload) => {
      queryClient.setQueryData(queryKeys.integrationMappings(providerKey), next);
      setEditing(null);
    },
  });

  const payload = mappingsQuery.data;
  // ⚠ MEMOISED, NOT PLAIN — `payload?.types ?? []` builds a NEW empty array on
  // every render while the read is in flight, and `kinds` is a dependency of the
  // memo below, so the plain form re-ran it on every render (`DEF-CUS-3935`).
  const kinds = useMemo(() => payload?.types ?? [], [payload]);
  const kind = useMemo(
    () => kinds.find((one) => one.entity_type === kindChosen) ?? kinds[0] ?? null,
    [kinds, kindChosen],
  );

  const rows = useMemo(() => {
    if (payload === undefined || kind === null) return [];
    const needle = search.trim().toLowerCase();
    return payload.rows.filter((row) => {
      if (row.entity_type !== kind.entity_type) return false;
      if (unmappedOnly && row.state !== "unmapped") return false;
      if (needle === "") return true;
      const ours = ourWord(t, row) ?? "";
      return (
        row.external_value.toLowerCase().includes(needle) || ours.toLowerCase().includes(needle)
      );
    });
  }, [payload, kind, search, unmappedOnly, t]);

  if (mappingsQuery.isPending) {
    return <LoadingSkeleton variant="table" />;
  }

  if (payload === undefined) {
    return (
      <FailedWithRetry
        title={t("integrations.mappings.failedTitle")}
        reason={refusalText(t, mappingsQuery.error)}
        onRetry={() => void mappingsQuery.refetch()}
        onDownloadReport={() => undefined}
      />
    );
  }

  const providerName = t(`integrations.provider.${payload.provider.key}.name`, {
    defaultValue: payload.provider.display_name,
  });

  return (
    <section className="flex flex-col gap-4" data-screen="S143" data-provider={payload.provider.key}>
      <PageHeader
        title={providerName}
        kicker={t("integrations.mappings.title")}
        backTo={{ to: tenantPath(INTEGRATIONS_ROUTE), label: t("integrations.mappings.backTo") }}
      />
      {/* rule 32: one sentence under the head, and it is the whole introduction. */}
      <p className="text-sm text-neutral-600">{t("integrations.mappings.intro")}</p>

      {kinds.length > 1 && (
        <div className="flex flex-wrap gap-2" role="group" aria-label={t("integrations.mappings.title")}>
          {kinds.map((one) => (
            <button
              key={one.entity_type}
              type="button"
              onClick={() => {
                setKindChosen(one.entity_type);
                setEditing(null);
              }}
              aria-pressed={kind?.entity_type === one.entity_type}
              data-kind={one.entity_type}
              className={
                kind?.entity_type === one.entity_type
                  ? "rounded-full border border-neutral-900 bg-neutral-900 px-3 py-1 text-xs font-medium uppercase tracking-wide text-neutral-100"
                  : "rounded-full border border-neutral-300 px-3 py-1 text-xs font-medium uppercase tracking-wide text-neutral-600"
              }
            >
              {t(`integrations.mappings.type.${one.entity_type}`, { defaultValue: one.label })}
            </button>
          ))}
        </div>
      )}

      {kind === null ? (
        <Note>{t("integrations.mappings.noWords")}</Note>
      ) : (
        <>
          {kind.counts.unmapped > 0 ? (
            <div
              className="border border-l-4 border-danger-500 bg-neutral-100 p-3 text-sm text-neutral-900"
              role="status"
              data-unmapped={kind.counts.unmapped}
            >
              <strong>
                {t("integrations.mappings.alert", {
                  unmapped: kind.counts.unmapped,
                  count: kind.counts.rows,
                })}
              </strong>{" "}
              {t("integrations.mappings.alertConsequence")}
            </div>
          ) : (
            <p className="text-sm text-success-700" role="status" data-unmapped={0}>
              {t("integrations.mappings.allMapped")}
            </p>
          )}

          {kind.beside_the_chart && <Note>{t("integrations.mappings.ledgerNote")}</Note>}

          <div className="flex flex-wrap items-center gap-3">
            <label className="sr-only" htmlFor="mapping-search">
              {t("integrations.mappings.search")}
            </label>
            <input
              id="mapping-search"
              type="search"
              className="w-72 max-w-full border border-field-border bg-neutral-100 px-2 py-1 text-sm"
              placeholder={t("integrations.mappings.search")}
              value={search}
              onChange={(event) => setSearch(event.target.value)}
            />
            <label className="flex items-center gap-2 text-sm text-neutral-700">
              <input
                type="checkbox"
                checked={unmappedOnly}
                onChange={(event) => setUnmappedOnly(event.target.checked)}
              />
              {t("integrations.mappings.unmappedOnly")}
            </label>
          </div>

          {rows.length === 0 ? (
            <Note>{t("integrations.mappings.empty")}</Note>
          ) : (
            <ul className="flex flex-col gap-2" data-mapping-rows={rows.length}>
              {rows.map((row) => (
                <MappingRowView
                  key={row.external_value}
                  row={row}
                  kind={kind}
                  editing={editing === row.external_value}
                  saving={save.isPending && editing === row.external_value}
                  refusal={
                    save.isError && editing === row.external_value
                      ? refusalText(t, save.error)
                      : null
                  }
                  timeZone={timeZone}
                  dateFormat={dateFormat}
                  onEdit={() => {
                    save.reset();
                    setEditing(row.external_value);
                  }}
                  onSave={(localValue) =>
                    save.mutate({
                      entity_type: row.entity_type,
                      external_value: row.external_value,
                      local_value: localValue,
                    })
                  }
                  onCancel={() => {
                    save.reset();
                    setEditing(null);
                  }}
                />
              ))}
            </ul>
          )}

          <Note>{t("integrations.mappings.foot")}</Note>
        </>
      )}
    </section>
  );
}

// ── Lifecycle ────────────────────────────────────────────────────────────
// packet: US-INT-037 (EP-INT-10) · US-INT-039 · frames 45.1 · 81.2 · 08-screen-layouts.md S143
// generated: 2026-09-03 by the CR-069 wave D build lane
// checklist: A✔ B✔ C✔ D✔(GET / PUT /integrations/{key}/mappings) E✔(routed at settings/integrations/:key/mappings; linked from the card) F✔ G✔ H=n/a
// gates: tsc · vitest · G13 (the one optional prop is the client seam every Settings screen takes) · G31 (Tailwind only; on route-b-migrated.txt) · G37 (the row action is a <RowAction>) · G40 (mounted from App.tsx) · G69 (no id is a visible value)
// exceptions: the GIS queue tab is not rendered (wave Q, OQ-INT-1470) — a stated absence closed by default · the S141 format picker is the manifest's `file_format` select, drawn by wave B's field slot, and nothing here
// status: VERIFIED-UNRATIFIED
// ─────────────────────────────────────────────────────────────────────────
