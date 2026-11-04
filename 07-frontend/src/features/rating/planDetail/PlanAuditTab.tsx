// ── Trace ──────────────────────────────────────────────
// Change:   CR-167-BRC10 round 3 task 7 — the Audit tab (images 34–36): *All ·
//           Plan changes · Changes underneath*, From / To, ⤓ CSV, and every row
//           opens to *Before → After · Version* (ruling 13).
// Defects:  DEF-RAT-9288 (raw ids and JSON as the change — now the server's
//           words, `before_display` / `after_display`) · DEF-RAT-9334
// Rules:    NFR-3 (one paged read, SQL UNION of the plan's own changes and what
//           moved underneath it — J10) · BR-SHL-011 (the filters are URL state)
//           · B14 rules 31 (names, never ids), 33 · hard rule 4 (`audit_log` is
//           pruned on retention, so a short trail is a true answer)
// ───────────────────────────────────────────────────────
import { useQuery } from "@tanstack/react-query";
import { useSearchParams } from "react-router-dom";

import type { ApiClient } from "@/api/client";
import { PLAN_AUDIT_KINDS, getPlanAuditCsv, getPlanAuditPage } from "@/api/planDetailEndpoints";
import type { PlanAuditRow } from "@/api/planDetailEndpoints";
import { ChipRow, ChipToggle } from "@/components/Chip";
import { DataTable } from "@/components/DataTable";
import { formatDate } from "@/components/DateCell";
import { DownloadButton } from "@/components/DownloadButton";
import { FactBlock } from "@/components/FactBlock";
import { setFilter } from "@/components/FilterBar";
import { DatePickerField } from "@/components/FormModal";
import { Panel } from "@/components/Panel";
import { useToast } from "@/components/Toast";
import { dateRangeFilter, parseTableParams, serializeTableParams } from "@/components/tableTypes";
import type { TableConfig, TableRequestState } from "@/components/tableTypes";

import { SECTION_HEADING } from "../planForm/planFormShared";
import { DASH, changedText, dayShown } from "./planDetailModel";
import type { PlanRegional, Translator } from "./planDetailModel";
import { saveCsv } from "./saveCsv";

export const AUDIT_PARAM_PREFIX = "a.";

/** Literal keys, so G18 sees each one used. */
const CHANGE_KEYS: Readonly<Record<string, string>> = {
  created: "rating.planDetail.audit.change.created",
  edited: "rating.planDetail.audit.change.edited",
  new_version: "rating.planDetail.audit.change.new_version",
  correction: "rating.planDetail.audit.change.correction",
  added: "rating.planDetail.audit.change.added",
  removed: "rating.planDetail.audit.change.removed",
  published: "rating.planDetail.audit.change.published",
};

const KIND_KEYS: Readonly<Record<string, string>> = {
  plan: "rating.planDetail.audit.kind.plan",
  schedule: "rating.planDetail.audit.kind.schedule",
  charge_code: "rating.planDetail.audit.kind.charge_code",
  tax: "rating.planDetail.audit.kind.tax",
  discount: "rating.planDetail.audit.kind.discount",
};

const FILTER_KEYS: Readonly<Record<string, string>> = {
  plan: "rating.planDetail.audit.filter.plan",
  underneath: "rating.planDetail.audit.filter.underneath",
};

export function auditChangeWord(change: string, t: Translator): string {
  const key = CHANGE_KEYS[change];
  return key === undefined ? change : t(key);
}

export function auditKindWord(kind: string, t: Translator): string {
  const key = KIND_KEYS[kind];
  return key === undefined ? kind : t(key);
}

/** WHAT (image 34): *Fixed a mistake · v1* for the plan's own change; *Rate
 *  schedule · Residential water* for what moved underneath it. */
export function auditWhat(row: PlanAuditRow, t: Translator): string {
  if (row.what_kind === "plan") {
    const word = auditChangeWord(row.change, t);
    return row.version?.version === null || row.version === null
      ? word
      : `${word} · ${t("rating.discountDetail.versions.n", { n: row.version.version })}`;
  }
  return row.what_name === null ? auditKindWord(row.what_kind, t) : `${auditKindWord(row.what_kind, t)} · ${row.what_name}`;
}

/** CHANGE (image 34): the plan's own change in words, before → after; the word
 *  for anything underneath (*New version*). */
export function auditChange(row: PlanAuditRow, t: Translator, regional?: PlanRegional): string {
  if (row.what_kind === "plan" && row.after_display !== null) {
    const before = auditSide(row, "before", t, regional);
    const after = auditSide(row, "after", t, regional) ?? row.after_display;
    return before === null ? after : `${before} → ${after}`;
  }
  // `DEF-RAT-10033` — a tax or discount the plan uses, in History's words:
  // *Rate: 2.00% → 6.00%*. The bare word stays for a row the server cannot word.
  if (row.changes !== undefined && row.changes.length > 0) return changedText(row.changes, t);
  return auditChangeWord(row.change, t);
}

/** `DEF-RAT-9502` — one side of a change in the catalogue's words:
 *  *Beginnt: 01/01/2027 · Stand: Veröffentlicht*. A field the catalogue does
 *  not name keeps the server's English label; its value is the utility's own
 *  words unless it is a yes/no, a status or a date, which are worded here.
 *  Falls back to the server's English `*_display` when it sent no facts. */
export function auditSide(
  row: PlanAuditRow,
  side: "before" | "after",
  t: Translator,
  regional?: PlanRegional,
): string | null {
  if (row.what_kind !== "plan" && row.changes !== undefined && row.changes.length > 0) {
    // `DEF-RAT-10033` — the same worded facts the CHANGE column reads.
    return row.changes.map((one) => `${one.field}: ${side === "before" ? one.before : one.after}`).join(" · ");
  }
  const facts = side === "before" ? row.before_facts : row.after_facts;
  const display = side === "before" ? row.before_display : row.after_display;
  if (facts === null || facts === undefined) return display;
  const parts = facts.map((fact) => {
    const label = t(`rating.planDetail.audit.field.${fact.key}`, { defaultValue: fact.label });
    let value = fact.value;
    if (fact.kind === "none") value = t("rating.planSections.none");
    else if (fact.kind === "bool" && typeof fact.raw === "boolean") value = t(fact.raw ? "rating.yes" : "rating.no");
    else if (fact.kind === "status" && typeof fact.raw === "string") {
      value = t(`rating.plan.status.${fact.raw}`, { defaultValue: fact.raw });
    } else if (fact.kind === "date" && typeof fact.raw === "string" && regional !== undefined) {
      value = dayShown(fact.raw, regional);
    }
    return `${label}: ${value}`;
  });
  if ((row.facts_more ?? 0) > 0) parts.push(t("rating.planDetail.audit.more", { count: row.facts_more }));
  return parts.length === 0 ? display : parts.join(" · ");
}

/** VERSION (image 36): *Rate schedule v4 from 09/30/2026*. */
export function auditVersion(row: PlanAuditRow, regional: PlanRegional, t: Translator): string {
  const version = row.version;
  if (version === null) return DASH;
  const kind = auditKindWord(version.kind, t);
  const n = version.version === null ? "" : ` ${t("rating.discountDetail.versions.n", { n: version.version })}`;
  const from =
    version.effective_from === null ? "" : ` ${t("rating.planSections.from", { date: dayShown(version.effective_from, regional) })}`;
  return `${kind}${n}${from}`;
}

export function PlanAuditTab(props: { planId: string; client: ApiClient; regional: PlanRegional; t: Translator }) {
  const { t, regional } = props;
  const toast = useToast();
  const [searchParams, setSearchParams] = useSearchParams();

  const config: TableConfig<PlanAuditRow> = {
    screenId: "S10.plan.audit",
    columns: [
      {
        key: "at",
        label: t("rating.taxDetail.audit.col.when"),
        identity: true,
        cell: (row) => (
          <span className="tabular-nums">
            {row.at === null ? DASH : formatDate(row.at, regional.timeZone, regional.dateFormat, true)}
          </span>
        ),
      },
      {
        key: "who",
        label: t("rating.taxDetail.audit.col.who"),
        cell: (row) => row.actor_name ?? t("rating.taxDetail.audit.system"),
      },
      { key: "what", label: t("rating.taxDetail.audit.col.what"), cell: (row) => auditWhat(row, t) },
      { key: "change", label: t("rating.taxDetail.audit.col.change"), cell: (row) => auditChange(row, t, regional) },
      {
        key: "reason",
        label: t("rating.taxDetail.audit.col.reason"),
        cell: (row) => (row.reason === null || row.reason.trim() === "" ? DASH : row.reason),
      },
    ],
    getRowId: (row) => row.id,
    filters: [
      {
        name: "kind",
        label: t("rating.planDetail.audit.filter.label"),
        options: PLAN_AUDIT_KINDS.map((value) => ({ value, label: t(FILTER_KEYS[value]) })),
      },
      dateRangeFilter({
        name: "when",
        label: t("rating.taxDetail.audit.col.when"),
        from: "from",
        to: "to",
        dateFormat: regional.dateFormat,
      }),
    ],
    defaultSort: { sort: "at", dir: "desc" },
    renderExpanded: (row) => (
      <div className="py-2" data-plan-audit-open={row.id}>
        <FactBlock
          name={`audit-${row.id}`}
          variant="strip"
          columns={3}
          facts={[
            { id: "before", label: t("rating.planDetail.audit.before"), value: auditSide(row, "before", t, regional) ?? DASH },
            { id: "after", label: t("rating.planDetail.audit.after"), value: auditSide(row, "after", t, regional) ?? DASH },
            { id: "version", label: t("rating.planDetail.versions.col.version"), value: auditVersion(row, regional, t) },
          ]}
        />
      </div>
    ),
  };

  const state = parseTableParams(searchParams, config, AUDIT_PARAM_PREFIX);
  const kind = state.filters.kind ?? "";
  const from = state.filters.from ?? "";
  const to = state.filters.to ?? "";
  const query = useQuery({
    queryKey: ["plans", props.planId, "audit", serializeTableParams(state, config).toString()],
    queryFn: () => getPlanAuditPage(props.planId, { kind, from, to, page: state.page, per: state.per }, props.client),
    enabled: props.planId !== "",
    placeholderData: (previous) => previous,
  });

  function setState(next: TableRequestState): void {
    const merged = new URLSearchParams(searchParams);
    for (const key of [...merged.keys()]) {
      if (key.startsWith(AUDIT_PARAM_PREFIX)) merged.delete(key);
    }
    serializeTableParams(next, config, AUDIT_PARAM_PREFIX).forEach((value, key) => merged.set(key, value));
    setSearchParams(merged, { replace: true });
  }

  async function download(): Promise<void> {
    try {
      saveCsv(await getPlanAuditCsv(props.planId, { kind, from, to }, props.client), "plan-audit.csv");
    } catch {
      toast(t("rating.planDetail.csvFailed"));
    }
  }

  const choices = [{ value: "", label: t("table.filters.all") }, ...PLAN_AUDIT_KINDS.map((value) => ({ value, label: t(FILTER_KEYS[value]) }))];

  return (
    <Panel as="section" aria-labelledby="plan-detail-audit" data-plan-audit="">
      <h2 id="plan-detail-audit" className={SECTION_HEADING}>
        {t("rating.taxDetail.audit.title")}
      </h2>
      <DataTable<PlanAuditRow>
        config={config}
        state={state}
        onStateChange={setState}
        rows={query.data?.rows ?? []}
        totalRows={query.data?.total ?? null}
        loading={query.isPending}
        error={
          query.isError && query.data === undefined
            ? { reason: t("rating.taxDetail.audit.failed"), onRetry: () => void query.refetch() }
            : undefined
        }
        filterBarSlot={
          <div className="flex flex-wrap items-end gap-3" data-plan-audit-filters="">
            <ChipRow>
              {choices.map((choice) => (
                <ChipToggle
                  key={choice.value || "all"}
                  selected={kind === choice.value}
                  onClick={() => setState(setFilter(state, "kind", choice.value))}
                  data-audit-kind={choice.value || "all"}
                >
                  {choice.label}
                </ChipToggle>
              ))}
            </ChipRow>
            <div className="w-48">
              <DatePickerField
                id="plan-audit-from"
                label={t("rating.planDetail.audit.from")}
                value={from}
                onChange={(value) => setState(setFilter(state, "from", value))}
                dateFormat={regional.dateFormat}
                regional
                max={to === "" ? undefined : to}
              />
            </div>
            <div className="w-48">
              <DatePickerField
                id="plan-audit-to"
                label={t("rating.planDetail.audit.to")}
                value={to}
                onChange={(value) => setState(setFilter(state, "to", value))}
                dateFormat={regional.dateFormat}
                regional
                min={from === "" ? undefined : from}
              />
            </div>
          </div>
        }
        downloadSlot={<DownloadButton onDownload={() => void download()} />}
        empty={{ title: t("rating.taxDetail.audit.empty"), helper: "" }}
      />
    </Panel>
  );
}
