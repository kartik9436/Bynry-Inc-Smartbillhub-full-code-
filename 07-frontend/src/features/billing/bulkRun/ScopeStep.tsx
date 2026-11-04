// ── Trace ──────────────────────────────────────────────
// Screen:   S31 · BIL-02 — the bill run, step 1 Scope (`/:tenant/billing/run`)
// Drawing:  05-prototype/bulk-bill-run-2026-09-30/01…08-scope-*.png ·
//           inventory.md §2
// Story:    US-BIL-036 (TC-2 … TC-14)
// Plan:     15-bulk-bill-run-build-plan.md F3 · F4 · F5 · F19 (the two panels)
// Rules:    changes rows 10–19, 30–35, 43 · BR-BIL-1050 (the Scope list) ·
//           B14 rules 10 (asterisk), 21, 31, 33, 38/44 (a form is built our way),
//           42 (from the images)
// Defects:  DEF-BIL-8221 (the two panels have no list read) · DEF-BIL-8222
//           (one template listable)
// ───────────────────────────────────────────────────────
/**
 * SCOPE — WHAT TO BILL, AND EVERY PROBLEM WITH IT AT ONCE.
 *
 * Everything below the form is the server's answer to ONE read,
 * `GET /billing/runs/scope-preview`, asked again whenever a field changes: the
 * refusals and warnings (each on its field, with its own key), the cycle's
 * details, what the run covers with last run's three account counts, the
 * continuity verdict, and the cycle's previous runs (paged). This file decides
 * no problem itself — the SAME check answers the POST, so what the screen
 * shows is what Start will be told.
 *
 * **Absent on purpose** (inventory §11): no services filter, no standing
 * answers, no "billed to owner", no "continue anyway" tick on a gap, and no
 * last-run figure beside anything but the three account counts.
 */
import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import type { ReactNode } from "react";

import { getScopeList, scopeListKey } from "@/api/bulkRunEndpoints";
import type {
  ScopeFields,
  ScopeListName,
  ScopeMissingMeterRow,
  ScopeNobodyRow,
  ScopePreview,
  ScopeProblem,
} from "@/api/bulkRunEndpoints";
import type { ApiClient } from "@/api/client";
import type { BillRunHistoryRow, CycleRow } from "@/api/endpoints";
import { DatePickerField, SelectField, TextField } from "@/components/FormModal";
import type { Translator } from "@/components/FormModal";
import { ListPager } from "@/components/ListPager";
import type { PageSize } from "@/components/tableTypes";
import { Panel } from "@/components/Panel";
import { StatusPill } from "@/components/StatusPill";
import type { StatusTone } from "@/components/StatusPill";
import { PlainTable } from "@/components/Surfaces";

import { dueDateFrom } from "../billRunShared";

import {
  CollapsiblePanel,
  FactCards,
  ordinalDay,
  PanelAside,
  ProblemBox,
  RUN_TABLE,
  ServiceLabel,
  SidePanel,
  TableScroll,
  count,
  day,
  money,
  span,
} from "./bulkRunShared";
import type { FactCardItem, ProblemLine, RunFormat } from "./bulkRunShared";

export interface TemplateOption {
  value: string;
  label: string;
}

export interface ScopeLinks {
  cycle: (cycleId: string) => string;
  run: (runId: string) => string;
  allRuns: string;
}

/** The dates a problem's params carry, shown in the tenant's format. */
const DATE_PARAMS = ["from", "to", "today", "ranAt", "periodEnd"] as const;

/** The cycle frequencies Meter Reads stores (`metering.schedule.FREQUENCIES`),
 *  each with a whole sentence in the catalogue so no language has to bend an
 *  adjective into another sentence's grammar. */
const CYCLE_FREQUENCIES = new Set(["daily", "weekly", "fortnightly", "monthly", "bimonthly", "quarterly", "semiannual", "annual"]);

export function problemMessage(problem: ScopeProblem, fmt: RunFormat): string {
  const params: Record<string, unknown> = { ...problem.params };
  // DEF-BIL-8691 — *45 days. Cycle is monthly.* (D1 04): the server sends the
  // cycle's frequency word; a word the catalogue has no sentence for keeps the
  // day count rather than printing a raw code.
  const frequency = typeof params.frequency === "string" ? params.frequency.toLowerCase() : null;
  if (problem.code === "period_length" && frequency !== null && CYCLE_FREQUENCIES.has(frequency)) {
    return fmt.t(`billing.runScope.warning.periodCycleIs.${frequency}`, { days: params.days });
  }
  // DEF-BIL-8691 — *Not the cycle's bill day (1st).* (D1 04).
  if (typeof params.billDay === "number") params.billDay = ordinalDay(params.billDay, fmt.t);
  for (const name of DATE_PARAMS) {
    const value = params[name];
    if (typeof value === "string" && value !== "") params[name] = day(value.slice(0, 10), fmt);
  }
  return fmt.t(problem.message_key, { ...params, defaultValue: fmt.t("billing.bulkRun.scope.problemGeneric") });
}

/** The label a problem line leads with: its field's label, or — for a
 *  problem about the run as a whole — the thing it is about. */
export function problemFieldLabel(problem: ScopeProblem, t: Translator): string {
  if (problem.field !== null) return t(`billing.bulkRun.scope.field.${problem.field}`);
  return t(`billing.bulkRun.scope.about.${problem.code}`, { defaultValue: t("billing.bulkRun.scope.about.run") });
}

export function problemsOn(problems: readonly ScopeProblem[], field: string): ScopeProblem[] {
  return problems.filter((problem) => problem.field === field);
}

/** The run a problem names, for its `Open BR-0231` link. */
function namedRun(problem: ScopeProblem): { id: string; no: string | null } | null {
  const id = problem.params.run_id;
  if (typeof id !== "string" || id === "") return null;
  const no = problem.params.runNo;
  return { id, no: typeof no === "string" ? no : null };
}

export function periodDays(start: string, end: string): number | null {
  if (start === "" || end === "") return null;
  const a = Date.parse(`${start}T00:00:00Z`);
  const b = Date.parse(`${end}T00:00:00Z`);
  if (Number.isNaN(a) || Number.isNaN(b) || b < a) return null;
  return Math.round((b - a) / 86_400_000) + 1;
}

export function scopeDueDate(fields: ScopeFields, preview: ScopePreview | null): string | null {
  const days = fields.due_days.trim() === "" ? (preview?.cycle?.due_days ?? null) : Number(fields.due_days);
  if (days === null || !Number.isInteger(days) || days < 0) return null;
  return dueDateFrom(fields.bill_date, days);
}

const CONTINUITY_TONE: Record<string, StatusTone> = {
  continuous: "success",
  gap: "warning",
  overlap: "danger",
  first: "neutral",
};

export function ContinuityLine(props: { fields: ScopeFields; preview: ScopePreview | null; fmt: RunFormat }) {
  const { preview, fmt } = props;
  const { t } = fmt;
  const continuity = preview?.continuity;
  if (continuity === undefined || continuity.state === "unknown") return null;
  const run = continuity.run;
  const overlap = preview?.refusals.find((p) => p.code === "period_overlap");
  let fact: string;
  if (continuity.state === "continuous" && run !== undefined) {
    fact = t("billing.bulkRun.scope.continuity.continuousFact", {
      run: run.run_no ?? run.label ?? "",
      period: span(run.period_start, run.period_end, fmt),
      days: periodDays(props.fields.period_start, props.fields.period_end) ?? "—",
    });
  } else if (continuity.state === "gap") {
    fact = t("billing.bulkRun.scope.continuity.gapFact", {
      period: span(continuity.from ?? null, continuity.to ?? null, fmt),
    });
  } else if (continuity.state === "overlap") {
    const from = typeof overlap?.params.from === "string" ? overlap.params.from : run?.period_start ?? null;
    const to = typeof overlap?.params.to === "string" ? overlap.params.to : run?.period_end ?? null;
    fact = t("billing.bulkRun.scope.continuity.overlapFact", {
      period: span(from, to, fmt),
      run: run?.run_no ?? run?.label ?? "",
    });
  } else {
    fact = t("billing.bulkRun.scope.continuity.firstFact");
  }
  return (
    <p className="m-0 mt-4 flex flex-wrap items-center gap-3 text-base" data-continuity={continuity.state}>
      <StatusPill tone={CONTINUITY_TONE[continuity.state] ?? "neutral"}>
        {t(`billing.bulkRun.continuity.${continuity.state}`)}
      </StatusPill>
      <span className="text-neutral-700">{fact}</span>
    </p>
  );
}

// ── The two boxes at the top (F4) ───────────────────────────────────────────

/** The form's own field order (D1 02, 04): a box reads top to bottom the way
 *  the clerk fills the form in, whatever order the server listed the problems
 *  in; lines with no field (counts) come last. DEF-BIL-8673. */
const FIELD_ORDER = ["label", "cycle_id", "period_start", "period_end", "bill_date", "due_days", "template_id"];

/** DEF-BIL-8691 — two problems on one field read as ONE line (D1 04: *Period —
 *  45 days. … Ends after today.*); a line carrying a link keeps its own. */
export function oneLinePerField(lines: readonly ProblemLine[]): ProblemLine[] {
  const out: ProblemLine[] = [];
  for (const line of lines) {
    const last = out.at(-1);
    if (last !== undefined && line.field !== null && last.field === line.field && last.link === undefined && line.link === undefined) {
      out[out.length - 1] = { ...last, message: `${last.message} ${line.message}` };
    } else {
      out.push(line);
    }
  }
  return out;
}

export function inFormOrder(problems: readonly ScopeProblem[]): ScopeProblem[] {
  const rank = (problem: ScopeProblem) => {
    const at = problem.field === null ? -1 : FIELD_ORDER.indexOf(problem.field);
    return at === -1 ? FIELD_ORDER.length : at;
  };
  return problems
    .map((problem, index) => ({ problem, index }))
    .sort((a, b) => rank(a.problem) - rank(b.problem) || a.index - b.index)
    .map(({ problem }) => problem);
}

export function ScopeProblems(props: {
  preview: ScopePreview | null;
  fmt: RunFormat;
  links: ScopeLinks;
  onOpenPanel: (panel: "nobody" | "missingMeter") => void;
}) {
  const { preview, fmt } = props;
  const { t } = fmt;
  if (preview === null) return null;
  const line = (problem: ScopeProblem, index: number): ProblemLine => {
    const run = namedRun(problem);
    let link: ProblemLine["link"];
    if (problem.code === "units_nobody_to_bill") {
      link = { label: t("billing.bulkRun.scope.seeUnits"), onPress: () => props.onOpenPanel("nobody") };
    } else if (problem.code === "services_no_meter") {
      link = { label: t("billing.bulkRun.scope.seeServices"), onPress: () => props.onOpenPanel("missingMeter") };
    } else if (run !== null) {
      link = { label: t("billing.bulkRun.scope.openRun", { run: run.no ?? "" }), href: props.links.run(run.id) };
    }
    return {
      key: `${problem.code}-${index}`,
      field: problem.field,
      fieldLabel: problemFieldLabel(problem, t),
      message: problemMessage(problem, fmt),
      link,
    };
  };
  return (
    <div className="flex flex-col gap-2" data-scope-problems="">
      <ProblemBox
        tone="refusal"
        title={t("billing.bulkRun.scope.refusals", { count: preview.refusals.length })}
        lines={oneLinePerField(inFormOrder(preview.refusals).map(line))}
      />
      <ProblemBox
        tone="warning"
        title={t("billing.bulkRun.scope.warnings", { count: preview.warnings.length })}
        lines={oneLinePerField(inFormOrder(preview.warnings).map(line))}
      />
    </div>
  );
}

// ── What to bill (F3) ───────────────────────────────────────────────────────

function fieldMessage(problems: readonly ScopeProblem[], field: string, fmt: RunFormat): { error?: string; warning?: string } {
  const on = problemsOn(problems, field);
  const refusal = on.find((p) => p.severity === "refusal");
  // DEF-BIL-8691 — every warning on the field, as one note: D1 04 writes
  // "45 days. Cycle is monthly. Ends after today." under Period end.
  const warnings = on.filter((p) => p.severity === "warning");
  return {
    error: refusal === undefined ? undefined : problemMessage(refusal, fmt),
    warning: warnings.length === 0 ? undefined : warnings.map((one) => problemMessage(one, fmt)).join(" "),
  };
}

function FieldWarning(props: { text: string | undefined; field: string }) {
  if (props.text === undefined) return null;
  return (
    <p className="m-0 mt-1 text-base font-semibold text-warning-700" data-field-warning={props.field}>
      {props.text}
    </p>
  );
}

export function WhatToBill(props: {
  fields: ScopeFields;
  onChange: (patch: Partial<ScopeFields>) => void;
  cycles: readonly CycleRow[];
  templates: readonly TemplateOption[];
  preview: ScopePreview | null;
  fmt: RunFormat;
  readOnly: boolean;
}) {
  const { fields, fmt, preview } = props;
  const { t } = fmt;
  const problems = [...(preview?.refusals ?? []), ...(preview?.warnings ?? [])];
  const msg = (field: string) => fieldMessage(problems, field, fmt);
  const cycle = preview?.cycle ?? null;
  const due = scopeDueDate(fields, preview);
  const billHelp =
    cycle?.bill_day === null || cycle?.bill_day === undefined
      ? undefined
      : t("billing.bulkRun.scope.billDayHelp", { day: ordinalDay(cycle.bill_day, t) });
  const dueHelp =
    due === null
      ? undefined
      : fields.due_days.trim() === "" || Number(fields.due_days) === cycle?.due_days
        ? t("billing.bulkRun.scope.dueFromCycle", { due: day(due, fmt) })
        : t("billing.bulkRun.scope.dueOn", { due: day(due, fmt) });
  const f = {
    label: msg("label"),
    cycle: msg("cycle_id"),
    start: msg("period_start"),
    end: msg("period_end"),
    bill: msg("bill_date"),
    days: msg("due_days"),
    template: msg("template_id"),
  };
  return (
    <Panel as="section" title={t("billing.bulkRun.scope.whatToBill")} aria-label={t("billing.bulkRun.scope.whatToBill")} data-run-panel-section="what-to-bill">
      <div className="grid grid-cols-3 gap-x-4 gap-y-2">
        <div className="col-span-2">
          <TextField
            id="label"
            label={t("billing.bulkRun.scope.field.label")}
            required
            value={fields.label}
            onChange={(value) => props.onChange({ label: value })}
            readOnly={props.readOnly}
            error={f.label.error}
          />
          <FieldWarning text={f.label.warning} field="label" />
        </div>
        <div>
          <SelectField
            id="cycle_id"
            label={t("billing.bulkRun.scope.field.cycle_id")}
            required
            value={fields.cycle_id}
            onChange={(value) => props.onChange({ cycle_id: value })}
            options={props.cycles.map((c) => ({ value: c.id, label: c.name === null ? c.code : `${c.code} · ${c.name}` }))}
            placeholder={t("billing.bulkRun.scope.chooseCycle")}
            error={f.cycle.error}
          />
        </div>
        <div>
          <DatePickerField
            id="period_start"
            label={t("billing.bulkRun.scope.field.period_start")}
            required
            value={fields.period_start}
            onChange={(value) => props.onChange({ period_start: value })}
            dateFormat={fmt.dateFormat}
            error={f.start.error}
          />
          <FieldWarning text={f.start.warning} field="period_start" />
        </div>
        <div>
          <DatePickerField
            id="period_end"
            label={t("billing.bulkRun.scope.field.period_end")}
            required
            value={fields.period_end}
            onChange={(value) => props.onChange({ period_end: value })}
            dateFormat={fmt.dateFormat}
            error={f.end.error}
          />
          <FieldWarning text={f.end.warning} field="period_end" />
        </div>
        <div>
          <DatePickerField
            id="bill_date"
            label={t("billing.bulkRun.scope.field.bill_date")}
            required
            value={fields.bill_date}
            onChange={(value) => props.onChange({ bill_date: value })}
            dateFormat={fmt.dateFormat}
            help={f.bill.error === undefined && f.bill.warning === undefined ? billHelp : undefined}
            error={f.bill.error}
          />
          <FieldWarning text={f.bill.warning} field="bill_date" />
        </div>
        <div>
          <TextField
            id="due_days"
            label={t("billing.bulkRun.scope.field.due_days")}
            required
            value={fields.due_days}
            onChange={(value) => props.onChange({ due_days: value })}
            numeric
            help={f.days.error === undefined && f.days.warning === undefined ? dueHelp : undefined}
            error={f.days.error}
          />
          <FieldWarning text={f.days.warning} field="due_days" />
        </div>
        <div className="col-span-2">
          <SelectField
            id="template_id"
            label={t("billing.bulkRun.scope.field.template_id")}
            required
            value={fields.template_id}
            onChange={(value) => props.onChange({ template_id: value })}
            options={[...props.templates]}
            placeholder={t("billing.bulkRun.scope.chooseTemplate")}
            error={f.template.error}
          />
          <FieldWarning text={f.template.warning} field="template_id" />
        </div>
      </div>
      <ContinuityLine fields={fields} preview={preview} fmt={fmt} />
    </Panel>
  );
}

// ── Cycle details · This run covers · Previous runs (F5) ───────────────────

function frequencyWord(frequency: string | null, t: Translator): string {
  return frequency === null ? "—" : t(`settings.cycles.frequency.${frequency.toLowerCase()}`, { defaultValue: frequency });
}

export function CycleDetails(props: { preview: ScopePreview | null; label: string; fmt: RunFormat; links: ScopeLinks }) {
  const { fmt } = props;
  const { t } = fmt;
  const cycle = props.preview?.cycle ?? null;
  if (cycle === null) return null;
  const items: FactCardItem[] = [
    { id: "cycle", label: t("billing.bulkRun.scope.field.cycle_id"), value: cycle.name === null ? cycle.code : `${cycle.code} · ${cycle.name}`, wide: true },
    { id: "run-name", label: t("billing.bulkRun.scope.field.label"), value: props.label === "" ? "—" : props.label, wide: true },
    { id: "frequency", label: t("billing.bulkRun.cycle.frequency"), value: frequencyWord(cycle.frequency, t) },
    {
      id: "reads-start",
      label: t("billing.bulkRun.cycle.readsStart"),
      value: cycle.reads_start_day === null ? "—" : t("billing.bulkRun.cycle.day", { day: cycle.reads_start_day }),
      note:
        cycle.days_to_complete === null
          ? undefined
          : t("billing.bulkRun.cycle.daysToComplete", { count: cycle.days_to_complete }),
    },
    { id: "bill-day", label: t("billing.bulkRun.cycle.billDay"), value: cycle.bill_day === null ? "—" : ordinalDay(cycle.bill_day, t) },
    { id: "days-to-pay", label: t("billing.bulkRun.scope.field.due_days"), value: count(cycle.due_days) },
    { id: "routes", label: t("billing.bulkRun.cycle.routes"), value: count(cycle.routes) },
    { id: "first-run", label: t("billing.bulkRun.cycle.firstRun"), value: day(cycle.first_run_date, fmt) },
    { id: "runs-so-far", label: t("billing.bulkRun.cycle.runsSoFar"), value: count(cycle.runs_so_far) },
    {
      id: "status",
      label: t("billing.bulkRun.cycle.status"),
      value:
        cycle.status === null ? (
          "—"
        ) : (
          <StatusPill tone={cycle.status === "active" ? "success" : "neutral"}>
            {t(`billing.bulkRun.cycle.statusWord.${cycle.status}`, { defaultValue: cycle.status })}
          </StatusPill>
        ),
    },
  ];
  return (
    <CollapsiblePanel
      id="cycle-details"
      title={t("billing.bulkRun.scope.cycleDetails")}
      toggleLabel={t("billing.bulkRun.scope.cycleDetails")}
      aside={
        <span className="flex items-center gap-3">
          <PanelAside>
            {t("billing.bulkRun.scope.cycleAside", {
              frequency: frequencyWord(cycle.frequency, t),
              day: cycle.bill_day === null ? "—" : ordinalDay(cycle.bill_day, t),
            })}
          </PanelAside>
          <a
            href={props.links.cycle(cycle.id)}
            target="_blank"
            rel="noreferrer"
            className="font-heading text-base font-semibold text-accent-700 underline"
            data-link="open-cycle"
          >
            {t("billing.bulkRun.scope.openCycle")}
          </a>
        </span>
      }
    >
      <FactCards name="cycle" items={items} />
    </CollapsiblePanel>
  );
}

export function RunCovers(props: { preview: ScopePreview | null; t: Translator }) {
  const { t } = props;
  const counts = props.preview?.counts ?? null;
  const last = props.preview?.last_run_counts ?? null;
  if (counts === null) return null;
  const lastRun = (value: number | undefined) =>
    value === undefined ? undefined : t("billing.bulkRun.scope.lastRunCount", { value: count(value) });
  const items: FactCardItem[] = [
    { id: "units", label: t("billing.bulkRun.covers.units"), value: count(counts.units_in_cycle) },
    { id: "accounts", label: t("billing.bulkRun.covers.accounts"), value: count(counts.accounts_to_bill), note: lastRun(last?.accounts_to_bill) },
    { id: "regular", label: t("billing.bulkRun.covers.regular"), value: count(counts.regular_accounts), note: lastRun(last?.regular_accounts) },
    { id: "master", label: t("billing.bulkRun.covers.master"), value: count(counts.master_accounts), note: lastRun(last?.master_accounts) },
    { id: "meters", label: t("billing.bulkRun.covers.meters"), value: count(counts.meters) },
    { id: "sub-meters", label: t("billing.bulkRun.covers.subMeters"), value: count(counts.sub_meters) },
    { id: "behind", label: t("billing.bulkRun.covers.behind"), value: count(counts.behind_the_meter) },
    { id: "missing", label: t("billing.bulkRun.covers.missing"), value: count(counts.missing_meter) },
  ];
  return (
    <CollapsiblePanel
      id="run-covers"
      title={t("billing.bulkRun.scope.runCovers")}
      toggleLabel={t("billing.bulkRun.scope.runCovers")}
      aside={
        <PanelAside>
          {t("billing.bulkRun.scope.coversAside", { accounts: count(counts.accounts_to_bill), meters: count(counts.meters) })}
        </PanelAside>
      }
    >
      <FactCards name="covers" items={items} />
    </CollapsiblePanel>
  );
}

function runStatusTone(status: string): StatusTone {
  if (status === "issued" || status === "sent") return "success";
  if (status === "abandoned" || status === "cancelled") return "neutral";
  return "info";
}

export function PreviousRuns(props: {
  preview: ScopePreview | null;
  fmt: RunFormat;
  links: ScopeLinks;
  page: number;
  per: PageSize;
  onPage: (page: number) => void;
  onPer: (per: PageSize) => void;
}) {
  const { fmt } = props;
  const { t } = fmt;
  const page = props.preview?.previous_runs ?? null;
  if (props.preview?.cycle === null || props.preview === null) return null;
  const last = props.preview.previous_run;
  const rows: BillRunHistoryRow[] = page?.results ?? [];
  return (
    <CollapsiblePanel
      id="previous-runs"
      title={t("billing.bulkRun.scope.previousRuns")}
      toggleLabel={t("billing.bulkRun.scope.previousRuns")}
      defaultOpen={false}
      aside={
        <PanelAside>
          {last === null
            ? t("billing.bulkRun.scope.noPreviousRun")
            : t("billing.bulkRun.scope.lastRunAside", { run: last.run_no ?? "", period: span(last.period_start, last.period_end, fmt) })}
        </PanelAside>
      }
    >
      {rows.length === 0 ? (
        <p className="m-0 text-base text-neutral-700" role="status">
          {t("billing.bulkRun.scope.noPreviousRun")}
        </p>
      ) : (
        <TableScroll>
          <PlainTable className={RUN_TABLE} data-run-table="previous-runs">
            <thead>
              <tr>
                <th scope="col">{t("billing.bulkRun.col.run")}</th>
                <th scope="col">{t("billing.bulkRun.col.period")}</th>
                <th scope="col" data-num="">{t("billing.bulkRun.col.bills")}</th>
                <th scope="col" data-num="">{t("billing.bulkRun.col.value")}</th>
                <th scope="col">{t("billing.bulkRun.col.runBy")}</th>
                <th scope="col">{t("billing.bulkRun.col.status")}</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((row) => (
                <tr key={row.id}>
                  <td>
                    <a href={props.links.run(row.id)} target="_blank" rel="noreferrer" className="font-semibold text-accent-700 underline">
                      {row.run_no ?? t("billing.bulkRun.runUnnumbered")}
                    </a>
                    {row.label !== null && row.label !== undefined && (
                      <span className="block text-neutral-700">{row.label}</span>
                    )}
                  </td>
                  <td>{span(row.period_start, row.period_end, fmt)}</td>
                  <td data-num="">{count(row.bills_issued)}</td>
                  <td data-num="">{money(row.value ?? null, { ...fmt, currency: row.value_currency ?? fmt.currency })}</td>
                  <td>{row.ran_by_name ?? "—"}</td>
                  <td>
                    <StatusPill tone={runStatusTone(row.status)}>
                      {t(`billing.runs.status.${row.status}`, { defaultValue: row.status })}
                    </StatusPill>
                  </td>
                </tr>
              ))}
            </tbody>
          </PlainTable>
        </TableScroll>
      )}
      {page !== null && page.count > 0 && (
        <ListPager total={page.count} page={props.page} per={props.per} onPage={props.onPage} onPer={props.onPer} />
      )}
      <p className="m-0 mt-3">
        <a href={props.links.allRuns} target="_blank" rel="noreferrer" className="font-semibold text-accent-700 underline" data-link="all-runs">
          {t("billing.bulkRun.scope.allRuns")}
        </a>
      </p>
    </CollapsiblePanel>
  );
}

// ── The two list panels (F19) — the rows behind a count (DEF-BIL-8221) ─────

export interface ScopeListLinks {
  /** The unit, on the tab where its account is opened. */
  addAccount: (unitId: string) => string;
  /** The unit, on the tab where a meter is fitted. */
  fitMeter: (unitId: string) => string;
  /** Record links (PO 2026-10-19): an account's page (new tab). */
  account?: (accountId: string) => string;
}

/**
 * Scope's *Nobody to bill* (units) and *Missing meter* (services) panels —
 * the rows behind the count, paged from `GET /billing/runs/scope-list`
 * (DEF-BIL-8221), each with its new-tab fix (changes row 42, EP-BIL-01 TC-12).
 */
export function ScopeListPanel(props: {
  panel: "nobody" | "missingMeter";
  preview: ScopePreview | null;
  cycleId: string;
  client: ApiClient;
  links: ScopeListLinks;
  t: Translator;
  fmt: RunFormat;
  onClose: () => void;
}) {
  const { t, fmt } = props;
  const list: ScopeListName = props.panel === "nobody" ? "nobody" : "missing_meter";
  const [page, setPage] = useState(1);
  const [per, setPer] = useState<PageSize>(50);
  const listQuery = useQuery({
    queryKey: scopeListKey(props.cycleId, list, page, per),
    queryFn: () => getScopeList<ScopeNobodyRow | ScopeMissingMeterRow>(props.cycleId, list, page, per, props.client),
    enabled: props.cycleId !== "",
    retry: false,
    placeholderData: (previous) => previous,
  });
  const counts = props.preview?.counts ?? null;
  const figure = props.panel === "nobody" ? counts?.units_nobody_to_bill : counts?.missing_meter;
  const rows = listQuery.data?.rows ?? [];
  const total = listQuery.data?.total ?? 0;
  const title: ReactNode = (
    <>
      {t(`billing.bulkRun.scope.panel.${props.panel}.title`)}{" "}
      <span className="text-base text-neutral-700">{count(figure ?? null)}</span>
    </>
  );
  // DEF-BIL-8699 — one line, as D1 07/08 draw it: "1400 Elm St · Unit A".
  const place = (row: { address: string | null; unit: string | null }) =>
    [row.address ?? "—", row.unit].filter((part) => part !== null).join(" · ");
  const fixLink = (href: string, name: string, label: string) => (
    <a href={href} target="_blank" rel="noreferrer" className="text-accent-700 underline" data-link={name}>
      {label} ↗
    </a>
  );
  let body: ReactNode;
  if (listQuery.isError) {
    body = (
      <p className="m-0 text-base text-danger-700" role="alert" data-scope-list-error="">
        {t("billing.bulkRun.problemGeneric")}
      </p>
    );
  } else if (listQuery.data === undefined) {
    body = null;
  } else if (rows.length === 0) {
    body = (
      <p className="m-0 text-base text-neutral-700" role="status">
        {t("billing.bulkRun.check.nobodyHere")}
      </p>
    );
  } else if (props.panel === "nobody") {
    body = (
      <TableScroll>
        <PlainTable className={RUN_TABLE} data-run-table="scope-nobody">
          <thead>
            <tr>
              <th scope="col">{t("billing.bulkRun.col.unit")}</th>
              <th scope="col">{t("billing.bulkRun.col.services")}</th>
              <th scope="col">{t("billing.bulkRun.scope.panel.lastAccount")}</th>
              <th scope="col">{t("billing.bulkRun.col.action")}</th>
            </tr>
          </thead>
          <tbody>
            {(rows as ScopeNobodyRow[]).map((row) => (
              <tr key={row.unit_id} data-scope-row="">
                <td>{place(row)}</td>
                <td>
                  {row.services.length === 0
                    ? "—"
                    : row.services.map((code, index) => (
                        <span key={code}>
                          {index > 0 && ", "}
                          <ServiceLabel code={code} t={t} />
                        </span>
                      ))}
                </td>
                <td>
                  {row.last_account === null ? (
                    "—"
                  ) : (
                    <>
                      {props.links.account !== undefined && row.last_account.account_id ? (
                        <a href={props.links.account(row.last_account.account_id)} target="_blank" rel="noreferrer" className="text-accent-700 underline">
                          {row.last_account.account_no}
                        </a>
                      ) : (
                        row.last_account.account_no
                      )}
                      {row.last_account.moved_out !== null && (
                        <span className="block text-neutral-700">
                          {t("billing.bulkRun.scope.panel.movedOut", { date: day(row.last_account.moved_out, fmt) })}
                        </span>
                      )}
                    </>
                  )}
                </td>
                <td>{fixLink(props.links.addAccount(row.unit_id), "add-account", t("billing.bulkRun.scope.panel.addAccount"))}</td>
              </tr>
            ))}
          </tbody>
        </PlainTable>
      </TableScroll>
    );
  } else {
    body = (
      <TableScroll>
        <PlainTable className={RUN_TABLE} data-run-table="scope-missing-meter">
          <thead>
            <tr>
              <th scope="col">{t("billing.bulkRun.col.unit")}</th>
              <th scope="col">{t("billing.bulkRun.col.service")}</th>
              <th scope="col">{t("billing.bulkRun.col.account")}</th>
              <th scope="col">{t("billing.bulkRun.col.action")}</th>
            </tr>
          </thead>
          <tbody>
            {(rows as ScopeMissingMeterRow[]).map((row, index) => (
              <tr key={`${row.unit_id}:${row.service ?? index}`} data-scope-row="">
                <td>{place(row)}</td>
                <td>{row.service === null ? "—" : <ServiceLabel code={row.service} t={t} />}</td>
                <td>
                  {row.account_no === null ? (
                    "—"
                  ) : props.links.account !== undefined && row.account_id ? (
                    <a href={props.links.account(row.account_id)} target="_blank" rel="noreferrer" className="text-accent-700 underline">
                      {row.account_no}
                    </a>
                  ) : (
                    row.account_no
                  )}
                </td>
                <td>{fixLink(props.links.fitMeter(row.unit_id), "fit-meter", t("billing.bulkRun.scope.panel.fitMeter"))}</td>
              </tr>
            ))}
          </tbody>
        </PlainTable>
      </TableScroll>
    );
  }
  return (
    <SidePanel
      name={props.panel}
      kicker={t(`billing.bulkRun.scope.panel.${props.panel}.kicker`)}
      title={title}
      note={t(`billing.bulkRun.scope.panel.${props.panel}.note`)}
      closeLabel={t("billing.bulkRun.close")}
      onClose={props.onClose}
    >
      {body}
      {total > 0 && (
        <ListPager total={total} page={page} per={per} onPage={setPage} onPer={(next) => { setPer(next); setPage(1); }} />
      )}
    </SidePanel>
  );
}
