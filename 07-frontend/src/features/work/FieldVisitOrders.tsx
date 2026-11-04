// ── Trace ──────────────────────────────────────────────
// Defect:   DEF-CUS-6363 — the move-in's *Field visit* panel spoke of a
//           move-out, offered only published templates (so a utility with none
//           could raise nothing), and listed nothing it would raise.
// Rulings:  PO 2026-09-23, move-in: *"please provide the button to raise field
//           work order … if work order is raised you should shown in table
//           format and also on review step"*, then *"this is good - show the
//           status - … and who is working on it"*. PO 2026-09-23, transfer:
//           *"it should be dropdown please use table array component with add
//           option; also have no visit required option"* — decision log
//           2026-09-23, *"ONE FIELD-VISIT COMPONENT, INLINE ADD, FOR EVERY FLOW"*
//           and *"THE TRANSFER'S FIELD VISIT IS THE MOVE-IN'S TABLE"*.
// Rules:    BR-WRK-055 (the flow does not wait for the visit; orders are RAISED
//           and numbered when the flow is saved, so an abandoned wizard leaves
//           no orphan order) · BR-WRK-018 (an empty due date lets the
//           priority's target stand) · BR-WRK-029 (the dispatcher's own skill
//           test applies to the assignee) · B14 rules 21 (Tailwind; this file
//           is on route-b-migrated.txt), 31 (no id is a visible value), 33
//           (labels ≤ 3 words, no rationale), 38 (inline rows, no modal — the
//           construction is ours), 43 (ONE component, every flow mounts it)
// Tests:    src/features/work/FieldVisitOrders.dom.test.tsx
// Hosts:    features/customers/MoveInWizard.tsx (step 3, review, done) · the
//           transfer wizard (lane TRANSFER mounts it; it builds no second one)
// ───────────────────────────────────────────────────────
//
// ⚠ **THREE MODES, ONE COLUMN SET.** `edit` is the step: rows are added inline
// with *+ Add work order*, and *No visit needed* clears and hides them. `review`
// is the same rows read-only with an *Order #* column reading *On save*. `live`
// is after the save: each order's real number links to it, and STATUS and
// ASSIGNED TO are read from Work at that moment — never copied into the flow.
//
// ⚠ **IT OWNS ITS OWN READS** (job types, priorities, crews and technicians,
// and in live mode each order), each through a `client` prop, so a host mounts
// one element and passes nothing it would have to fetch for it.
import { useQueries, useQuery } from "@tanstack/react-query";
import { useEffect, useMemo } from "react";
import { Link } from "react-router-dom";

import { api } from "@/api/client";
import type { ApiClient } from "@/api/client";
import { Button } from "@/components/Button";
import { DateCell } from "@/components/DateCell";
import type { RegionalDateFormat } from "@/components/DateCell";
import { EditableTable } from "@/components/EditableTable";
import type { EditableColumn } from "@/components/EditableTable";
import {
  CheckboxField,
  DatePickerField,
  SearchSelectField,
  SelectField,
  TextField,
} from "@/components/FormModal";
import { formatDate } from "@/components/DateCell";
import { TableArray } from "@/components/TableArray";
import { PlainTable, RefusalStrip } from "@/components/Surfaces";
import { Note } from "@/components/TextBits";
import type { Translator } from "@/features/tenancy/settingsShared";
import { useTenantPath } from "@/routing/tenantPath";

import { adviceText } from "./candidateAdvice";
import { workOrderDetailPath } from "./OrderDetailPage";
import { listRaiseCandidates } from "./raise/raiseEndpoints";
import { isDay, windowMoments } from "./visitWindow";
import { getProposedWorkOrders, getRaiseOptions, getWorkOrder, listCrews } from "./workEndpoints";
import type { CrewRow, ProposedWorkOrder, RaiseOptions } from "./workEndpoints";

// ── The value a host holds ─────────────────────────────────────────────────

/** One row a clerk added. `holder` is `technician:<id>`, `crew:<id>` or `""`
 *  (unassigned) — one select, two kinds of holder, the dispatcher's own split. */
export interface FieldVisitRow {
  key: string;
  type_id: string;
  priority_id: string;
  /** `YYYY-MM-DD`, or `""` for the priority's own target (`BR-WRK-018`). */
  due_on: string;
  holder: string;
  note: string;
  /** `CR-168-BRC10` P3.42 — the Work rule that put this row here, or absent
   *  for a row the clerk added. Its `id` travels as `rule_id` so the job
   *  names its rule (`BR-WRK-024`); its name is what the row says. */
  rule?: { id: string; name: string } | null;
  /** `CR-171-BRC10` P1.19 (image 30) — the TEMPLATE the *Work order* field
   *  named; its job type is `type_id`. Absent on a row typed by job type. */
  template_id?: string;
  /** `DEF-WRK-9784` — the named template's SERVICE code, kept beside it so
   *  the step can refuse a template of another service than the *For* meter's. */
  template_service?: string;
  /** Image 30's *For* — the meter the visit is for, by NUMBER (B14 rule 31). */
  asset_no?: string;
  /** Image 30's *Window* — the product's own three (`visitWindow.ts`). */
  window?: "any" | "morning" | "afternoon";
}

export interface FieldVisitValue {
  /** *No visit needed* — an ANSWER, kept, and exclusive with rows. */
  none: boolean;
  rows: FieldVisitRow[];
  /** P3.42 — the rules' rows have been put in once. A clerk who removes them
   *  is answered, not refilled. */
  ruled?: boolean;
}

export function emptyFieldVisit(): FieldVisitValue {
  return { none: false, rows: [] };
}

/** The order a flow raised, as the save answered it. */
export interface RaisedWorkOrderRef {
  id: string;
  order_no: string | null;
}

let rowCounter = 0;
function newRowKey(): string {
  rowCounter += 1;
  return `fv-${Date.now().toString(36)}-${rowCounter}`;
}

/**
 * The row a *+ Add work order* press appends. The priority opens on the
 * utility's *Normal* where it has one — the PO's approved default — and the
 * job type's own default replaces it the moment a type is picked, unless the
 * clerk has chosen one themselves.
 */
export function newFieldVisitRow(
  options: RaiseOptions | undefined,
  flowKind?: string,
  /** `CR-171-BRC10` image 30 — a move-in row's Due opens on the move-in date. */
  defaultDue?: string,
): FieldVisitRow {
  // `DEF-WRK-9626` — the row opens on the job type that fits this flow (the
  // server's `flow_types`), and on that type's own priority where it has one.
  const typeId = (flowKind ? options?.flow_types?.[flowKind] : undefined) ?? "";
  const kind = options?.types.find((row) => row.id === typeId);
  return {
    key: newRowKey(),
    type_id: typeId,
    priority_id: kind?.default_priority_id ?? normalPriorityId(options) ?? "",
    due_on: defaultDue ?? "",
    holder: "",
    note: "",
  };
}

/** The utility's own *Normal*, by code or name, or null where it has none. */
export function normalPriorityId(options: RaiseOptions | undefined): string | null {
  const row = (options?.priorities ?? []).find(
    (priority) =>
      priority.code.toLowerCase() === "normal" || priority.name.toLowerCase() === "normal",
  );
  return row?.id ?? null;
}

/**
 * What the step's Continue checks: every row names its job type. Returns the
 * catalogue key of the refusal, or null. The server refuses the same row by
 * name (`work.fromFlows.jobTypeRequired`) — this is only where a clerk meets
 * it first.
 */
export function fieldVisitProblem(
  value: FieldVisitValue,
  /** `DEF-WRK-9784` — the service code of a *For* meter, by its number. A
   *  host that draws no *For* column passes nothing and nothing is checked. */
  meterService?: (assetNo: string) => string | undefined,
): string | null {
  if (value.none) return null;
  if (value.rows.some((row) => row.type_id === "")) return "work.fieldVisitOrders.jobTypeRequired";
  if (meterService !== undefined && value.rows.some((row) => templateOfAnotherService(row, meterService))) {
    return "work.order.template_wrong_service";
  }
  return null;
}

/** `DEF-WRK-9784` — a row naming a template of another service than its
 *  *For* meter's. The server refuses the same row by name before the flow
 *  commits (`from_flows.check_order_rows_on_unit`); this is where a clerk
 *  meets it first. */
export function templateOfAnotherService(
  row: FieldVisitRow,
  meterService: (assetNo: string) => string | undefined,
): boolean {
  if (!row.template_id || !row.template_service || !row.asset_no) return false;
  const service = meterService(row.asset_no);
  return service !== undefined && service !== row.template_service;
}

/**
 * The `field_visit` a flow's body carries, or `undefined` when there is nothing
 * to say. `{none: true}` when *No visit needed* is ticked; `{orders: [...]}`
 * with each row's ids split into `technician_id` / `crew_id`.
 */
export function fieldVisitPayload(value: FieldVisitValue): Record<string, unknown> | undefined {
  if (value.none) return { none: true };
  if (value.rows.length === 0) return undefined;
  return {
    orders: value.rows.map((row) => {
      const [kind, id] = row.holder.split(":");
      const order: Record<string, unknown> = { type_id: row.type_id };
      if (row.priority_id !== "") order.priority_id = row.priority_id;
      if (row.due_on !== "") order.due_on = row.due_on;
      if (kind === "technician" && id) order.technician_id = id;
      if (kind === "crew" && id) order.crew_id = id;
      if (row.note.trim() !== "") order.note = row.note.trim();
      if (row.rule?.id) order.rule_id = row.rule.id;
      // `CR-171-BRC10` P1.19 — each only when the clerk gave it, so a flow
      // whose table draws none of these columns posts exactly what it did.
      if (row.template_id) order.template_id = row.template_id;
      if (row.asset_no) order.asset_no = row.asset_no;
      if (row.window !== undefined && row.window !== "any" && isDay(row.due_on)) {
        const moments = windowMoments(row.due_on, row.window);
        if (moments.window_start !== null) order.window_start = moments.window_start;
        if (moments.window_end !== null) order.window_end = moments.window_end;
      }
      return order;
    }),
  };
}

/** A parked draft's field visit, distrusting every field (BR-SHL-048 (b)). */
export function hydrateFieldVisit(raw: unknown): FieldVisitValue {
  if (raw === null || typeof raw !== "object") return emptyFieldVisit();
  const source = raw as Record<string, unknown>;
  const text = (value: unknown) => (typeof value === "string" ? value : "");
  const rows = Array.isArray(source.rows) ? source.rows : [];
  const ruleOf = (raw: unknown): { id: string; name: string } | null => {
    if (raw === null || typeof raw !== "object") return null;
    const rule = raw as Record<string, unknown>;
    return text(rule.id) !== "" ? { id: text(rule.id), name: text(rule.name) } : null;
  };
  return {
    none: source.none === true,
    ruled: source.ruled === true,
    rows: rows
      .filter((row): row is Record<string, unknown> => row !== null && typeof row === "object")
      .map((row) => ({
        key: text(row.key) || newRowKey(),
        type_id: text(row.type_id),
        priority_id: text(row.priority_id),
        due_on: text(row.due_on),
        holder: text(row.holder),
        note: text(row.note),
        rule: ruleOf(row.rule),
        ...(text(row.template_id) !== "" ? { template_id: text(row.template_id) } : {}),
        ...(text(row.template_service) !== "" ? { template_service: text(row.template_service) } : {}),
        ...(text(row.asset_no) !== "" ? { asset_no: text(row.asset_no) } : {}),
        ...(row.window === "morning" || row.window === "afternoon" || row.window === "any"
          ? { window: row.window as "any" | "morning" | "afternoon" }
          : {}),
      })),
  };
}

/** `technician:<id>` for a person, `crew:<id>` for a crew or a contractor. */
export function holderValue(row: CrewRow): string {
  return row.kind === "person" ? `technician:${row.id}` : `crew:${row.id}`;
}

// ── The component ──────────────────────────────────────────────────────────

export const FIELD_VISIT_OPTIONS_KEY = ["work", "raise-options"] as const;
export const FIELD_VISIT_HOLDERS_KEY = ["work", "crews", "field-visit-holders"] as const;

export interface FieldVisitOrdersProps {
  /** The flow this is on — `move_in`, `transfer`, … — for ids and the DOM hook. */
  flowKind: string;
  value: FieldVisitValue;
  /** Absent in `review` and `live`, which change nothing. */
  onChange?: (next: FieldVisitValue) => void;
  mode?: "edit" | "review" | "live";
  /** `live` only — what the save raised, in the order the rows were sent. */
  raised?: readonly RaisedWorkOrderRef[];
  /** Show the row refusal. A host passes true once Continue has been pressed,
   *  so nothing is red before the clerk has done anything. */
  showErrors?: boolean;
  dateFormat: RegionalDateFormat;
  timeZone: string;
  t: Translator;
  client?: ApiClient;
  /**
   * **`"panel"` — THE DRAWN *FIELD VISIT* OF THE MOVE-IN'S STEP 1**
   * (`CR-171-BRC10` P2.21, image 30): a framed table with `#`, *Work order*
   * (one searchable field naming a template and its type), *For*, *Priority*,
   * *Due*, *Window*, *Assign to* with best-fit advice, *Note*; *Visit needed*
   * at the panel's right; *Raised when you complete* under it. Opt-in under
   * B14 rule 36: absent, every other flow renders exactly what it rendered.
   */
  layout?: "panel";
  /** `panel` — the services this flow starts: what the *Work order* list is
   *  offered for (`?flow=`'s read). */
  services?: readonly string[];
  /** `panel` — the *For* choices: the unit's meters, `{value: asset_no, label}`,
   *  each with its SERVICE code so a row's *Work order* list offers only that
   *  service's templates (`DEF-WRK-9784`). */
  meters?: readonly { value: string; label: string; service?: string | null }[];
  /** `panel` — the day a new row's Due opens on (the move-in date). */
  defaultDue?: string;
  /** `panel` — the unit the visit is at, for the best-fit advice's area. */
  unitId?: string;
}

export function FieldVisitOrders(props: FieldVisitOrdersProps) {
  const { t, value } = props;
  const mode = props.mode ?? "edit";
  const client = props.client ?? api;
  const tenantPath = useTenantPath();
  const options = useQuery({
    queryKey: FIELD_VISIT_OPTIONS_KEY,
    queryFn: () => getRaiseOptions(client),
    staleTime: 5 * 60 * 1000,
    retry: false,
  });
  const holders = useQuery({
    queryKey: FIELD_VISIT_HOLDERS_KEY,
    queryFn: () => listCrews({ per: 200 }, client),
    staleTime: 5 * 60 * 1000,
    retry: false,
  });
  const live = useQueries({
    queries: (mode === "live" ? (props.raised ?? []) : []).map((order) => ({
      queryKey: ["work", "order", order.id],
      queryFn: () => getWorkOrder(order.id, client),
      retry: false,
    })),
  });

  // ── P3.42 · the rules' rows, put in ONCE, before the clerk touches it ─────
  // `BR-WRK-055`: nothing is raised here — the rows are removable like any
  // other, and *No visit needed* clears them. `ruled` stops a clerk who
  // removed them being handed them back.
  const preselected = options.data?.preselected?.[props.flowKind];
  const untouched = !value.none && value.rows.length === 0 && value.ruled !== true;
  useEffect(() => {
    if (mode !== "edit" || props.onChange === undefined) return;
    if (!untouched || preselected === undefined || preselected.length === 0) return;
    props.onChange({
      none: false,
      ruled: true,
      rows: preselected.map((row) => ({
        key: newRowKey(),
        type_id: row.type_id,
        priority_id: row.priority_id,
        due_on: "",
        holder: row.holder,
        note: "",
        rule: row.rule,
      })),
    });
    // `props.onChange` is the host's setter; the rows are seeded once per
    // offer, so it is deliberately not a dependency.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [mode, untouched, preselected]);

  const typeName = useMemo(() => {
    const byId = new Map((options.data?.types ?? []).map((row) => [row.id, row.name]));
    return (id: string) => byId.get(id) ?? "";
  }, [options.data]);
  const priorityName = useMemo(() => {
    const byId = new Map((options.data?.priorities ?? []).map((row) => [row.id, row.name]));
    return (id: string) => byId.get(id) ?? "";
  }, [options.data]);
  const holderName = useMemo(() => {
    const byValue = new Map(
      (holders.data?.results ?? []).map((row) => [holderValue(row), row.name]),
    );
    return (key: string) =>
      key === "" ? t("work.fieldVisitOrders.unassigned") : (byValue.get(key) ?? "");
  }, [holders.data, t]);

  const set = (next: FieldVisitValue) => props.onChange?.(next);
  const patchRow = (index: number, patch: Partial<FieldVisitRow>) =>
    set({ ...value, rows: value.rows.map((row, i) => (i === index ? { ...row, ...patch } : row)) });
  const idFor = (index: number, field: string) => `${props.flowKind}-fv-${index}-${field}`;
  const dash = <span className="text-neutral-700">—</span>;
  const due = (on: string) =>
    on === "" ? (
      dash
    ) : (
      <DateCell value={on} timeZone={props.timeZone} dateFormat={props.dateFormat} />
    );

  // ── review and live: the same columns, read-only ──────────────────────────
  if (mode !== "edit") {
    if (value.none) {
      return (
        <section data-field-visit={props.flowKind} data-field-visit-mode={mode}>
          <h4 className="m-0 mb-2 font-heading text-base font-semibold">
            {t("work.fieldVisit.panel")}
          </h4>
          <Note data-field-visit-none="">{t("work.fieldVisit.noVisit")}</Note>
        </section>
      );
    }
    if (value.rows.length === 0 && (props.raised ?? []).length === 0) {
      return null;
    }
    const rows =
      mode === "live" && (props.raised ?? []).length > 0 ? (props.raised ?? []) : value.rows;
    return (
      <section data-field-visit={props.flowKind} data-field-visit-mode={mode}>
        <h4 className="m-0 mb-2 font-heading text-base font-semibold">
          {t("work.fieldVisit.panel")}
        </h4>
        <div className="overflow-x-auto">
          <PlainTable>
            <thead>
              <tr>
                {[
                  "work.fieldVisitOrders.col.orderNo",
                  "work.fieldVisitOrders.col.type",
                  "work.fieldVisitOrders.col.priority",
                  "work.fieldVisitOrders.col.due",
                  "work.fieldVisitOrders.col.assignee",
                  "work.fieldVisitOrders.col.status",
                  "work.fieldVisitOrders.col.note",
                ].map((key) => (
                  <th key={key} scope="col" className="px-2 py-1 text-left font-semibold">
                    {t(key)}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {rows.map((_entry, index) => {
                const typed = value.rows[index];
                const order = mode === "live" ? (props.raised ?? [])[index] : undefined;
                const read = mode === "live" ? live[index]?.data : undefined;
                return (
                  <tr
                    key={order?.id ?? typed?.key ?? String(index)}
                    data-field-visit-row={String(index + 1)}
                  >
                    <td className="px-2 py-1 tabular-nums">
                      {order === undefined ? (
                        t("work.fieldVisitOrders.onSave")
                      ) : (
                        <Link to={tenantPath(workOrderDetailPath("", order.id).slice(1))}>
                          {order.order_no ?? t("work.fieldVisitOrders.noNumber")}
                        </Link>
                      )}
                    </td>
                    <td className="px-2 py-1">
                      {read?.type ?? (typed ? typeName(typed.type_id) : "") ?? dash}
                      {typed?.rule ? (
                        <span
                          className="block text-neutral-700"
                          data-field-visit-rule={typed.rule.name}
                        >
                          {t("work.fieldVisitOrders.byRule", { name: typed.rule.name })}
                        </span>
                      ) : null}
                    </td>
                    <td className="px-2 py-1">
                      {read !== undefined
                        ? (read.priority?.name ?? dash)
                        : typed && typed.priority_id !== ""
                          ? priorityName(typed.priority_id)
                          : dash}
                    </td>
                    <td className="px-2 py-1">
                      {read !== undefined ? (
                        read.due_at === null ? (
                          dash
                        ) : (
                          <DateCell
                            value={read.due_at}
                            timeZone={props.timeZone}
                            dateFormat={props.dateFormat}
                          />
                        )
                      ) : (
                        due(typed?.due_on ?? "")
                      )}
                    </td>
                    <td className="px-2 py-1">
                      {read !== undefined
                        ? (read.technician?.name ?? t("work.fieldVisitOrders.unassigned"))
                        : holderName(typed?.holder ?? "")}
                    </td>
                    <td className="px-2 py-1" data-field-visit-status={read?.state ?? "not_raised"}>
                      {read !== undefined
                        ? t(`work.orders.state.${read.state}`)
                        : t("work.fieldVisitOrders.notRaised")}
                    </td>
                    <td className="px-2 py-1">{typed && typed.note !== "" ? typed.note : dash}</td>
                  </tr>
                );
              })}
            </tbody>
          </PlainTable>
        </div>
      </section>
    );
  }

  // ── edit, drawn as image 30's panel (`CR-171-BRC10` P2.21) ─────────────────
  if (props.layout === "panel") {
    return (
      <FieldVisitPanel
        {...props}
        client={client}
        options={options.data}
        optionsFailed={options.isError}
        optionsPending={options.isPending}
        holders={holders.data?.results ?? []}
        set={set}
        patchRow={patchRow}
        idFor={idFor}
      />
    );
  }

  // ── edit: the step ────────────────────────────────────────────────────────
  const typeOptions = (options.data?.types ?? []).map((row) => ({
    value: row.id,
    label: row.parent_name === null ? row.name : `${row.parent_name} · ${row.name}`,
  }));
  const priorityOptions = (options.data?.priorities ?? []).map((row) => ({
    value: row.id,
    label: row.name,
  }));
  const holderOptions = [
    { value: "", label: t("work.fieldVisitOrders.unassigned") },
    ...(holders.data?.results ?? []).map((row) => ({ value: holderValue(row), label: row.name })),
  ];
  const problem = props.showErrors === true ? fieldVisitProblem(value) : null;

  const columns: EditableColumn<FieldVisitRow>[] = [
    {
      key: "type",
      label: t("work.fieldVisitOrders.col.type"),
      cell: (row, index) => (
        <SelectField
          id={idFor(index, "type")}
          label={t("work.fieldVisitOrders.col.type")}
          labelHidden
          required
          value={row.type_id}
          placeholder={t("work.fieldVisitOrders.pickType")}
          options={typeOptions}
          error={
            props.showErrors === true && row.type_id === ""
              ? t("work.fieldVisitOrders.jobTypeRequired")
              : undefined
          }
          help={row.rule ? t("work.fieldVisitOrders.byRule", { name: row.rule.name }) : undefined}
          onChange={(typeId) => {
            // The job type's own default priority replaces the opening Normal,
            // unless the clerk has already chosen one themselves.
            const kind = (options.data?.types ?? []).find((entry) => entry.id === typeId);
            const untouched =
              row.priority_id === "" || row.priority_id === normalPriorityId(options.data);
            patchRow(index, {
              type_id: typeId,
              priority_id:
                untouched && kind?.default_priority_id ? kind.default_priority_id : row.priority_id,
            });
          }}
        />
      ),
    },
    {
      key: "priority",
      label: t("work.fieldVisitOrders.col.priority"),
      cell: (row, index) => (
        <SelectField
          id={idFor(index, "priority")}
          label={t("work.fieldVisitOrders.col.priority")}
          labelHidden
          value={row.priority_id}
          options={priorityOptions}
          placeholder={t("work.fieldVisitOrders.typeDefault")}
          onChange={(priorityId) => patchRow(index, { priority_id: priorityId })}
        />
      ),
    },
    {
      key: "due",
      label: t("work.fieldVisitOrders.col.due"),
      cell: (row, index) => (
        <DatePickerField
          id={idFor(index, "due")}
          label={t("work.fieldVisitOrders.col.due")}
          labelHidden
          regional
          value={row.due_on}
          dateFormat={props.dateFormat}
          onChange={(dueOn) => patchRow(index, { due_on: dueOn })}
        />
      ),
    },
    {
      key: "assignee",
      label: t("work.fieldVisitOrders.col.assignee"),
      cell: (row, index) => (
        <SelectField
          id={idFor(index, "assignee")}
          label={t("work.fieldVisitOrders.col.assignee")}
          labelHidden
          value={row.holder}
          options={holderOptions}
          onChange={(holder) => patchRow(index, { holder })}
        />
      ),
    },
    {
      key: "status",
      label: t("work.fieldVisitOrders.col.status"),
      cell: () => (
        <span data-field-visit-status="not_raised">{t("work.fieldVisitOrders.notRaised")}</span>
      ),
    },
    {
      key: "note",
      label: t("work.fieldVisitOrders.col.note"),
      cell: (row, index) => (
        <TextField
          id={idFor(index, "note")}
          label={t("work.fieldVisitOrders.col.note")}
          labelHidden
          value={row.note}
          onChange={(note) => patchRow(index, { note })}
        />
      ),
    },
  ];

  const addButton = (
    <Button
      variant="secondary"
      size="sm"
      data-field-visit-add=""
      disabled={options.isPending || options.isError}
      onClick={() =>
        set({
          none: false,
          ruled: value.ruled,
          rows: [...value.rows, newFieldVisitRow(options.data, props.flowKind)],
        })
      }
    >
      {t("work.fieldVisitOrders.add")}
    </Button>
  );

  return (
    <section
      className="flex flex-col gap-3"
      data-field-visit={props.flowKind}
      data-field-visit-mode="edit"
    >
      <h4 className="m-0 font-heading text-base font-semibold">{t("work.fieldVisit.panel")}</h4>
      <CheckboxField
        id={`${props.flowKind}-fv-none`}
        label={t("work.fieldVisit.noVisit")}
        checked={value.none}
        onChange={(none) =>
          set(
            none
              ? { none: true, rows: [], ruled: value.ruled }
              : { none: false, rows: value.rows, ruled: value.ruled },
          )
        }
      />
      {options.isError ? (
        <RefusalStrip role="alert" data-field-visit-options="failed">
          {t("work.fieldVisitOrders.optionsFailed")}
        </RefusalStrip>
      ) : null}
      {value.none ? null : value.rows.length === 0 ? (
        <div>{addButton}</div>
      ) : (
        <EditableTable<FieldVisitRow>
          caption={t("work.fieldVisitOrders.caption")}
          columns={columns}
          rows={value.rows}
          rowKey={(row) => row.key}
          onChange={(rows) => set({ ...value, rows, ruled: true })}
          reorderable={false}
          addRow={addButton}
          addRowPosition="above"
          emptyText=""
          labels={{
            remove: t("work.fieldVisitOrders.remove"),
            position: t("work.fieldVisitOrders.position"),
          }}
          data-collection={`${props.flowKind}-field-visit`}
        />
      )}
      {problem !== null ? (
        <RefusalStrip role="alert" data-field-visit-problem="">
          {t(problem)}
        </RefusalStrip>
      ) : null}
    </section>
  );
}

// ══════════════════════════════════════════════════════════════════════════
// `CR-171-BRC10` P2.21 · IMAGE 30's *FIELD VISIT*
// ══════════════════════════════════════════════════════════════════════════
//
// ⚠ **ONE *WORK ORDER* FIELD, NOT A JOB-TYPE SELECT** (P1.19). The list is the
// flow's own offer (`GET /connections/proposed-work-orders?flow=`), each entry
// a TEMPLATE in the drawing's words — *Move-in read · 15 min — Reading* — and
// picking one sets the row's job type from it. The raise accepts only a
// template that same read offers. A job type the offer carries no template
// for is still listed by its own name, so a utility that has written no
// templates can raise a visit (`DEF-CUS-6363`'s complaint, kept fixed).
//
// ⚠ **BEST FIT IS ADVICE, NEVER A CHOICE MADE FOR THE CLERK** (ruling 2,
// *"a guideline, never a block"*; ruling 25, *"user can either assign or can
// leave blank"*). Under *Assign to* the screen says who fits best — and, for
// the person chosen, why — from Work's `GET /work/candidates`; nothing is
// pre-selected.

const TYPE_PREFIX = "type:";

function templateLabel(row: ProposedWorkOrder, t: Translator): string {
  const head =
    row.est_duration_minutes === null
      ? row.name
      : `${row.name} · ${t("work.fieldVisit.minutes", { count: row.est_duration_minutes })}`;
  return row.job_type === null ? head : `${head} — ${row.job_type.name}`;
}

function FieldVisitPanel(
  props: FieldVisitOrdersProps & {
    client: ApiClient;
    options: RaiseOptions | undefined;
    optionsFailed: boolean;
    optionsPending: boolean;
    holders: readonly CrewRow[];
    set: (next: FieldVisitValue) => void;
    patchRow: (index: number, patch: Partial<FieldVisitRow>) => void;
    idFor: (index: number, field: string) => string;
  },
) {
  const { t, value } = props;
  const services = props.services ?? [];
  const offer = useQuery({
    queryKey: ["work", "flow-offer", props.flowKind, [...services].sort().join(",")],
    queryFn: () => getProposedWorkOrders(services, props.client, props.flowKind),
    enabled: services.length > 0,
    staleTime: 5 * 60 * 1000,
    retry: false,
  });
  const templates = offer.data?.proposed ?? [];
  // `DEF-WRK-9784` — a row's *Work order* list is the offer for ITS meter's
  // service. The offer spans every service the move-in starts, and M6 was
  // offered water's *Opening read* for an electric meter; Work refused it and
  // Complete raised nothing. A row with no meter (the whole unit) keeps the
  // whole offer, each entry naming its service once more than one is offered.
  const meterServiceOf = (assetNo: string): string | undefined =>
    (props.meters ?? []).find((meter) => meter.value === assetNo)?.service ?? undefined;
  const servicesOffered = new Set(templates.map((row) => row.service?.code ?? ""));
  function workOrderOptionsFor(row: FieldVisitRow) {
    const service = row.asset_no ? meterServiceOf(row.asset_no) : undefined;
    // The row's own pick stays listed after *For* moves to another service,
    // so the clerk sees what they chose beside the refusal, not a blank.
    const fitting =
      service === undefined
        ? templates
        : templates.filter(
            (entry) =>
              (entry.service?.code ?? service) === service || entry.template_id === row.template_id,
          );
    const typesWithTemplate = new Set(fitting.map((entry) => entry.job_type?.id ?? ""));
    const named = service === undefined && servicesOffered.size > 1;
    return [
      ...fitting.map((entry) => ({
        value: entry.template_id,
        label:
          named && entry.service !== null
            ? `${templateLabel(entry, t)} · ${t(`rating.service.${entry.service.code}`, { defaultValue: entry.service.name })}`
            : templateLabel(entry, t),
      })),
      ...(props.options?.types ?? [])
        .filter((kind) => !typesWithTemplate.has(kind.id))
        .map((kind) => ({
          value: `${TYPE_PREFIX}${kind.id}`,
          label: kind.parent_name === null ? kind.name : `${kind.parent_name} · ${kind.name}`,
        })),
    ];
  }
  const priorityOptions = (props.options?.priorities ?? []).map((row) => ({
    value: row.id,
    label: row.name,
  }));
  const holderOptions = [
    { value: "", label: t("work.fieldVisitOrders.unassigned") },
    ...props.holders.map((row) => ({ value: holderValue(row), label: row.name })),
  ];
  const windowOptions = (["any", "morning", "afternoon"] as const).map((choice) => ({
    value: choice,
    label: t(`work.edit.window.${choice}`),
  }));
  const meterOptions = [...(props.meters ?? [])];

  function pickWorkOrder(index: number, row: FieldVisitRow, picked: string): void {
    if (picked === "") {
      props.patchRow(index, { template_id: undefined, template_service: undefined, type_id: "" });
      return;
    }
    const template = picked.startsWith(TYPE_PREFIX)
      ? undefined
      : templates.find((entry) => entry.template_id === picked);
    const typeId = picked.startsWith(TYPE_PREFIX)
      ? picked.slice(TYPE_PREFIX.length)
      : (template?.job_type?.id ?? "");
    const kind = (props.options?.types ?? []).find((entry) => entry.id === typeId);
    const untouched = row.priority_id === "" || row.priority_id === normalPriorityId(props.options);
    props.patchRow(index, {
      template_service: template?.service?.code ?? undefined,
      template_id: picked.startsWith(TYPE_PREFIX) ? undefined : picked,
      type_id: typeId,
      priority_id:
        untouched && kind?.default_priority_id ? kind.default_priority_id : row.priority_id,
    });
  }

  /**
   * `DEF-WRK-9784` — *For* set after the *Work order*: a template of another
   * service is swapped for the SAME visit (name and job type) of the meter's
   * service when the offer has one — *Reconnect visit* picked first and then
   * pointed at the gas meter is gas's *Reconnect visit*. With no such twin the
   * pick stays and the row says *Template is for another service.*
   */
  function pickMeter(index: number, row: FieldVisitRow, assetNo: string): void {
    const service = assetNo === "" ? undefined : meterServiceOf(assetNo);
    const picked = templates.find((entry) => entry.template_id === row.template_id);
    const twin =
      picked !== undefined && service !== undefined && picked.service?.code !== service
        ? templates.find(
            (entry) =>
              entry.service?.code === service &&
              entry.name === picked.name &&
              (entry.job_type?.id ?? "") === (picked.job_type?.id ?? ""),
          )
        : undefined;
    props.patchRow(index, {
      asset_no: assetNo === "" ? undefined : assetNo,
      ...(twin !== undefined ? { template_id: twin.template_id, template_service: service } : {}),
    });
  }

  const columns = [
    {
      key: "workOrder",
      label: t("work.fieldVisitOrders.col.workOrder"),
      header: (
        <>
          {t("work.fieldVisitOrders.col.workOrder")}
          <span className="field-required" aria-hidden="true">
            *
          </span>
        </>
      ),
      cell: (row: FieldVisitRow, index: number) => (
        // Image 30 gives the Work order the widest cell: its words are what
        // the clerk reads to choose. A width from the scale, never a fixed px.
        <span className="block min-w-64">
          <SearchSelectField
            id={props.idFor(index, "workOrder")}
            label={t("work.fieldVisitOrders.col.workOrder")}
            labelHidden
            required
            dropdown
            value={row.template_id ?? (row.type_id === "" ? "" : `${TYPE_PREFIX}${row.type_id}`)}
            options={workOrderOptionsFor(row)}
            placeholder={t("work.fieldVisitOrders.pickWorkOrder")}
            error={
              props.showErrors === true && row.type_id === ""
                ? t("work.fieldVisitOrders.workOrderRequired")
                : templateOfAnotherService(row, meterServiceOf)
                  ? t("work.order.template_wrong_service")
                  : undefined
            }
            help={row.rule ? t("work.fieldVisitOrders.byRule", { name: row.rule.name }) : undefined}
            onChange={(picked) => pickWorkOrder(index, row, picked)}
          />
        </span>
      ),
    },
    {
      key: "for",
      label: t("work.fieldVisitOrders.col.for"),
      cell: (row: FieldVisitRow, index: number) => (
        <span className="block min-w-32">
          <SelectField
            id={props.idFor(index, "for")}
            label={t("work.fieldVisitOrders.col.for")}
            labelHidden
            value={row.asset_no ?? ""}
            options={meterOptions}
            placeholder={t("work.fieldVisitOrders.wholeUnit")}
            onChange={(assetNo) => pickMeter(index, row, assetNo)}
          />
        </span>
      ),
    },
    {
      key: "priority",
      label: t("work.fieldVisitOrders.col.priority"),
      cell: (row: FieldVisitRow, index: number) => (
        <SelectField
          id={props.idFor(index, "priority")}
          label={t("work.fieldVisitOrders.col.priority")}
          labelHidden
          value={row.priority_id}
          options={priorityOptions}
          placeholder={t("work.fieldVisitOrders.typeDefault")}
          onChange={(priorityId) => props.patchRow(index, { priority_id: priorityId })}
        />
      ),
    },
    {
      key: "due",
      label: t("work.fieldVisitOrders.col.due"),
      cell: (row: FieldVisitRow, index: number) => (
        <span className="block min-w-44">
          <DatePickerField
            id={props.idFor(index, "due")}
            label={t("work.fieldVisitOrders.col.due")}
            labelHidden
            regional
            value={row.due_on}
            dateFormat={props.dateFormat}
            onChange={(dueOn) => props.patchRow(index, { due_on: dueOn })}
          />
        </span>
      ),
    },
    {
      key: "window",
      label: t("work.fieldVisitOrders.col.window"),
      cell: (row: FieldVisitRow, index: number) => (
        <span className="block min-w-36">
          <SelectField
            id={props.idFor(index, "window")}
            label={t("work.fieldVisitOrders.col.window")}
            labelHidden
            value={row.window ?? "any"}
            options={windowOptions}
            // BR-SHL-025: a window is a time ON a day — with no due day it
            // cannot be written, and the box says why rather than vanishing.
            disabled={!isDay(row.due_on)}
            help={isDay(row.due_on) ? undefined : t("work.fieldVisitOrders.windowNeedsDue")}
            onChange={(choice) =>
              props.patchRow(index, { window: choice as "any" | "morning" | "afternoon" })
            }
          />
        </span>
      ),
    },
    {
      key: "assignee",
      label: t("work.fieldVisitOrders.col.assignTo"),
      cell: (row: FieldVisitRow, index: number) => (
        <span className="flex flex-col gap-1">
          <span className="block min-w-40">
            <SelectField
              id={props.idFor(index, "assignee")}
              label={t("work.fieldVisitOrders.col.assignTo")}
              labelHidden
              value={row.holder}
              options={holderOptions}
              onChange={(holder) => props.patchRow(index, { holder })}
            />
          </span>
          <BestFitAdvice
            row={row}
            unitId={props.unitId}
            client={props.client}
            dateFormat={props.dateFormat}
            timeZone={props.timeZone}
            t={t}
          />
        </span>
      ),
    },
    {
      key: "note",
      label: t("work.fieldVisitOrders.col.note"),
      cell: (row: FieldVisitRow, index: number) => (
        <span className="block min-w-40">
          <TextField
            id={props.idFor(index, "note")}
            label={t("work.fieldVisitOrders.col.note")}
            labelHidden
            value={row.note}
            onChange={(note) => props.patchRow(index, { note })}
          />
        </span>
      ),
    },
  ];

  const visitNeeded = (
    <CheckboxField
      id={`${props.flowKind}-fv-needed`}
      label={t("work.fieldVisit.visitNeeded")}
      checked={!value.none}
      onChange={(needed) =>
        props.set(
          needed
            ? { none: false, rows: value.rows, ruled: value.ruled }
            : { none: true, rows: [], ruled: value.ruled },
        )
      }
    />
  );

  return (
    <div
      data-field-visit={props.flowKind}
      data-field-visit-mode="edit"
      data-field-visit-layout="panel"
    >
      <TableArray<FieldVisitRow>
        title={t("work.fieldVisit.panel")}
        fact={visitNeeded}
        collection={`${props.flowKind}-field-visit`}
        numbered
        columns={value.none ? [] : columns}
        rows={value.none ? [] : value.rows}
        rowKey={(row) => row.key}
        emptyText={value.none ? t("work.fieldVisit.noVisit") : t("work.fieldVisitOrders.none")}
        onChange={(rows) => props.set({ ...value, rows, ruled: true })}
        removeLabel={t("work.fieldVisitOrders.remove")}
        actions={
          value.none
            ? []
            : [
                {
                  key: "add-work-order",
                  label: t("work.fieldVisitOrders.add"),
                  onClick: () =>
                    props.set({
                      none: false,
                      ruled: value.ruled,
                      rows: [
                        ...value.rows,
                        newFieldVisitRow(props.options, props.flowKind, props.defaultDue),
                      ],
                    }),
                  blockedReason:
                    props.optionsPending || props.optionsFailed
                      ? t("work.fieldVisitOrders.optionsFailed")
                      : undefined,
                },
              ]
        }
        footerTrailing={
          value.none ? undefined : (
            <span className="text-base text-neutral-700">
              {t("work.fieldVisitOrders.raisedOnComplete")}
            </span>
          )
        }
      >
        {props.optionsFailed ? (
          <RefusalStrip role="alert" data-field-visit-options="failed">
            {t("work.fieldVisitOrders.optionsFailed")}
          </RefusalStrip>
        ) : null}
      </TableArray>
    </div>
  );
}

/**
 * Image 30's green line under *Assign to* — *Best fit · 2 jobs that day*.
 * ADVICE (ruling 2): for the holder chosen, Work's own facts about them that
 * day, led by *Best fit* when they are; with nobody chosen, who the best fit
 * is. Nothing when Work answers nothing — never a guessed name.
 */
function BestFitAdvice(props: {
  row: FieldVisitRow;
  unitId?: string;
  client: ApiClient;
  dateFormat: RegionalDateFormat;
  timeZone: string;
  t: Translator;
}) {
  const { row, t } = props;
  const on = isDay(row.due_on) ? row.due_on : undefined;
  const advice = useQuery({
    queryKey: ["work", "flow-candidates", row.template_id ?? "", props.unitId ?? "", on ?? ""],
    queryFn: () =>
      listRaiseCandidates(
        {
          templateId: row.template_id,
          unitIds: props.unitId ? [props.unitId] : [],
          on,
          per: 50,
        },
        props.client,
      ),
    enabled: row.template_id !== undefined || row.holder !== "",
    staleTime: 60 * 1000,
    retry: false,
  });
  const results = advice.data?.results ?? [];
  const keyOf = (kind: string, id: string) =>
    kind === "person" ? `technician:${id}` : `crew:${id}`;
  const chosen = results.find((row2) => keyOf(row2.kind, row2.id) === row.holder);
  const best = results.find((row2) => row2.best_fit);
  const formatDay = (iso: string) => formatDate(iso, props.timeZone, props.dateFormat);
  let line: string | null = null;
  let good = false;
  if (row.holder !== "" && chosen !== undefined) {
    const facts = adviceText(chosen, t, formatDay);
    line = chosen.best_fit
      ? [t("work.assign.bestFit"), facts].filter((part) => part !== "").join(" · ")
      : facts === ""
        ? null
        : facts;
    good = chosen.best_fit;
  } else if (row.holder === "" && best !== undefined) {
    line = t("work.fieldVisitOrders.bestFitIs", { name: best.name });
    good = true;
  }
  if (line === null) return null;
  return (
    <span
      className={good ? "text-sm font-semibold text-success-700" : "text-sm text-neutral-700"}
      data-field-visit-advice={good ? "best-fit" : "advice"}
    >
      {line}
    </span>
  );
}
