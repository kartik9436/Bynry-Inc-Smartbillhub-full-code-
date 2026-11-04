// ── Trace ──────────────────────────────────────────────
// Change:   CR-179-BRC10 — the reporting framework's SERVER-DECLARED INPUTS.
//           Drawn from `05-prototype/rate-impact-2026-10-12/04-inputs.png` and
//           `05-result.png`, read as IMAGES (B14 rule 42). The first report to
//           declare inputs is Rate Impact; nothing here names it.
// Rules:    PO 2026-10-12 — *"we ahve to use reporting framework ot create this
//           report - dont create custom report"* · *"i mena cusotm code"* ·
//           B14 rule 21 (Tailwind utilities; this file is on
//           `src/styles/route-b-migrated.txt`) · rule 31 (no id is ever a
//           visible value — every option shows its `label`) · rule 33 (labels
//           ≤ 3 words; rationale zero words) · rule 36/43 (the kit's
//           `TableArray`, `CheckDropdown`, `SelectField`, `Button`) · rule 44 ·
//           CLAUDE.md hard rule 2 (money stored to 4, shown to 2; a unit price
//           shown up to 4; never a float — `scaleByPercent`)
// Tests:    src/features/reports/reportDeclaredInputs.dom.test.tsx
// ───────────────────────────────────────────────────────
//
// WHAT THIS IS
// ────────────
// A report may declare, in its run response, the inputs it needs —
// `controls.inputs`. The standard viewer draws each one by its KIND, never by
// its name:
//   · `select` — one dropdown;
//   · `multi`  — the kit's tick-box dropdown; its value is comma-joined;
//   · `table`  — an editable table array whose value is ONE JSON string, an
//     array of objects keyed by the table's non-display columns.
//
// Every value is a STRING, so the URL (`in.<param>`), the export and the run
// history carry it unchanged. A `select` or `multi` change re-runs the report at
// once (the table's choices depend on it); the table is edited LOCALLY and
// reaches the server only when **Run report** is pressed — never per keystroke.
//
// ⚠ **IT COMPUTES NO REVENUE.** The only arithmetic is the percent shortcut,
// which fills a proposed BOX from its "now" figure in integer arithmetic at
// money's stored four places. Every figure of the result is the server's.
import { useCallback, useRef, useState } from "react";
import type { ReactNode } from "react";

import type {
  ReportGap,
  ReportInput,
  ReportInputChoice,
  ReportInputColumn,
  ReportInputOption,
  ReportInputValues,
} from "@/api/reportsEndpoints";
import { Button } from "@/components/Button";
import { CheckDropdown } from "@/components/CheckDropdown";
import { formatDate } from "@/components/DateCell";
import type { RegionalDateFormat } from "@/components/DateCell";
import { SelectField } from "@/components/FormModal";
import { formatMoney, formatMoneyInput, formatRate, formatRateNumber } from "@/components/MoneyCell";
import { scaleByPercent, startingAmount } from "@/components/moneyMath";
import { Panel } from "@/components/Panel";
import { CellSelect, TableArray } from "@/components/TableArray";
import type { CellOption, TableArrayColumn } from "@/components/TableArray";
import { Dash } from "@/features/metering/meteringShared";
import i18n from "@/i18n";
import type { Translator } from "@/features/tenancy/settingsShared";

type TableInput = Extract<ReportInput, { kind: "table" }>;

/** One row of a table input being edited. A select cell holds `""` (nothing
 *  chosen) or `v:<value>` — the prefix is what lets a choice whose value IS
 *  the empty string (*All sizes*) be told from the placeholder. */
export interface DraftRow {
  id: string;
  cells: Record<string, string>;
}

const CHOSEN = "v:";
const DATE_ONLY = /^\d{4}-\d{2}-\d{2}$/;
const PLURAL_SUFFIX = /_(zero|one|two|few|many|other)$/;

function chosen(cell: string | undefined): string | null {
  return cell !== undefined && cell.startsWith(CHOSEN) ? cell.slice(CHOSEN.length) : null;
}

/**
 * A catalogue key with its parameters. ⚠ **A PLURAL FORM SENT BY NAME IS READ
 * AS ITS BASE KEY** — a server naming `…months_one` with `count: 12` means the
 * plural family, and i18next only picks the right form (in eleven languages)
 * when it is handed the base.
 */
export function inputText(
  key: string,
  t: Translator,
  params?: Record<string, string | number>,
): string {
  const base = params?.count !== undefined ? key.replace(PLURAL_SUFFIX, "") : key;
  return t(base, params);
}

function optionLabel(option: ReportInputOption, t: Translator): string {
  if (option.label !== undefined) return option.label;
  if (option.label_key !== undefined) return inputText(option.label_key, t, option.params);
  return option.value;
}

function columnLabel(input: TableInput, column: ReportInputColumn, t: Translator): string {
  return t(column.label_key ?? `${input.label_key}.column.${column.name}`);
}

/** Columns a person types or picks — every column but a `display`. */
function valueColumns(input: TableInput): ReportInputColumn[] {
  return input.columns.filter((column) => column.kind !== "display");
}

function isMoneyColumn(column: ReportInputColumn): boolean {
  return column.kind === "money" || column.kind === "unit_price";
}

/** The record a `select` cell has chosen from its `choices` list. */
function choiceOf(
  input: TableInput,
  column: ReportInputColumn,
  row: DraftRow,
): ReportInputChoice | undefined {
  if (column.choices === undefined) return undefined;
  const value = chosen(row.cells[column.name]);
  if (value === null) return undefined;
  // ⚠ **BY VALUE AND BY PARENT.** Two versions of one schedule may both carry
  // a `5/8"` size; matched on value alone, v2's row read v3's "now" figures.
  const parent = column.depends_on === undefined ? null : chosen(row.cells[column.depends_on]);
  return (input.choices[column.choices] ?? []).find(
    (choice) =>
      choice.value === value && (column.depends_on === undefined || choice[column.depends_on] === parent),
  );
}

/**
 * What a choice READS. A choice the server marks `in_force` reads
 * *v3 · in force*, the way every version picker in the product does; every
 * other reads its own label (B14 rule 31 — never its value).
 */
export function choiceLabel(choice: ReportInputChoice, t: Translator): string {
  return choice.in_force === true ? t("reports.input.inForce", { label: choice.label }) : choice.label;
}

/**
 * The option a dependent select starts on when its parent changes: the only
 * one, else the one IN FORCE (*"every version, the one in force first"* —
 * CR-179 §1 row 7), else none. The walk of 2026-10-12 found the version box
 * left on *Choose* with the version in force sitting in the list.
 */
function startingOption(
  input: TableInput,
  column: ReportInputColumn,
  row: DraftRow,
  t: Translator,
): string {
  const options = selectOptions(input, column, row, t);
  if (options.length === 1) return options[0].value;
  if (column.choices === undefined) return "";
  const parent = column.depends_on === undefined ? null : chosen(row.cells[column.depends_on]);
  const live = (input.choices[column.choices] ?? []).find(
    (choice) =>
      choice.in_force === true &&
      (column.depends_on === undefined || choice[column.depends_on] === parent),
  );
  return live === undefined ? "" : `${CHOSEN}${live.value}`;
}

/** The chosen record of the select drawing from `list`. */
function chosenFrom(input: TableInput, list: string, row: DraftRow): ReportInputChoice | undefined {
  const column = input.columns.find((one) => one.kind === "select" && one.choices === list);
  return column === undefined ? undefined : choiceOf(input, column, row);
}

/** A field of any chosen record on the row — `item_kind`, `item_noun`. */
function rowFact(input: TableInput, row: DraftRow, field: string): string | undefined {
  for (const column of input.columns) {
    const value = choiceOf(input, column, row)?.[field];
    if (typeof value === "string" && value !== "") return value;
  }
  return undefined;
}

function hiddenOnRow(input: TableInput, column: ReportInputColumn, row: DraftRow): boolean {
  const kinds = column.hidden_for_item_kinds;
  if (kinds === undefined || kinds.length === 0) return false;
  const kind = rowFact(input, row, "item_kind");
  return kind !== undefined && kinds.includes(kind);
}

/** The "now" figure a money box starts from: a string, `null` (*Billed* — not
 *  a flat figure), or `undefined` when nothing it depends on is chosen. */
export function nowFigure(
  input: TableInput,
  column: ReportInputColumn,
  row: DraftRow,
): string | null | undefined {
  if (column.now_from === undefined) return undefined;
  const record = chosenFrom(input, column.now_from, row);
  if (record === undefined) return undefined;
  const now = record.now as Record<string, string | null> | undefined;
  if (now === undefined || !(column.name in now)) return undefined;
  const figure = now[column.name];
  return figure === null || figure === undefined ? null : String(figure);
}

/** What a box shows for a figure: 2 places for money, up to 4 for a price. */
function boxFigure(column: ReportInputColumn, figure: string): string {
  return column.kind === "unit_price" ? startingAmount(figure) : formatMoneyInput(figure);
}

function selectOptions(
  input: TableInput,
  column: ReportInputColumn,
  row: DraftRow,
  t: Translator,
): CellOption[] {
  if (column.options !== undefined) {
    return column.options.map((option) => ({
      value: `${CHOSEN}${option.value}`,
      label: optionLabel(option, t),
    }));
  }
  if (column.choices === undefined) return [];
  const parent = column.depends_on === undefined ? null : chosen(row.cells[column.depends_on]);
  if (column.depends_on !== undefined && parent === null) return [];
  return (input.choices[column.choices] ?? [])
    .filter((choice) => column.depends_on === undefined || choice[column.depends_on] === parent)
    .map((choice) => ({ value: `${CHOSEN}${choice.value}`, label: choiceLabel(choice, t) }));
}

/** Every column that hangs, directly or not, off `name`. */
function dependentsOf(input: TableInput, name: string): Set<string> {
  const found = new Set<string>();
  let grew = true;
  while (grew) {
    grew = false;
    for (const column of input.columns) {
      const parent = column.depends_on;
      if (parent !== undefined && (parent === name || found.has(parent)) && !found.has(column.name)) {
        found.add(column.name);
        grew = true;
      }
    }
  }
  return found;
}

/**
 * A select cell changed: clear what depends on it, start a dependent on its
 * only choice or on the one in force, and start every money box from its new
 * "now" figure
 * (*"Picking an older version changes only the 'now' figures and the starting
 * point of the proposed boxes"* — CR-179 confirmed rule 3).
 */
export function changeSelect(
  input: TableInput,
  row: DraftRow,
  name: string,
  value: string,
  t: Translator,
): DraftRow {
  const next: DraftRow = { id: row.id, cells: { ...row.cells, [name]: value } };
  const cleared = dependentsOf(input, name);
  // In column order, so a version started on the one in force then offers
  // its own capacities to the column after it.
  for (const column of input.columns) {
    if (!cleared.has(column.name) || column.kind !== "select") continue;
    next.cells[column.name] = startingOption(input, column, next, t);
  }
  for (const column of input.columns) {
    if (!isMoneyColumn(column)) continue;
    const figure = nowFigure(input, column, next);
    next.cells[column.name] = figure === undefined || figure === null ? "" : boxFigure(column, figure);
  }
  return next;
}

/** The URL's JSON back into rows. A value that does not parse is no rows —
 *  a hand-edited link must not break the screen. */
export function parseTableValue(input: TableInput, raw: string | undefined): DraftRow[] {
  if (raw === undefined || raw === "") return [];
  let parsed: unknown;
  try {
    parsed = JSON.parse(raw);
  } catch {
    return [];
  }
  if (!Array.isArray(parsed)) return [];
  return parsed
    .filter((entry): entry is Record<string, unknown> => typeof entry === "object" && entry !== null)
    .map((entry, index) => {
      const cells: Record<string, string> = {};
      for (const column of valueColumns(input)) {
        const value = entry[column.name];
        if (column.kind === "select") {
          cells[column.name] = typeof value === "string" ? `${CHOSEN}${value}` : "";
        } else {
          cells[column.name] = value === null || value === undefined ? "" : String(value);
        }
      }
      return { id: `u${index}`, cells };
    });
}

/** Rows into the ONE JSON string the server reads. A box that is hidden on its
 *  row, or empty, is `null`; decimals stay strings. */
export function serializeTable(input: TableInput, rows: readonly DraftRow[]): string {
  return JSON.stringify(
    rows.map((row) => {
      const out: Record<string, string | null> = {};
      for (const column of valueColumns(input)) {
        const cell = row.cells[column.name] ?? "";
        if (column.kind === "select") {
          out[column.name] = chosen(cell) ?? "";
        } else {
          const typed = cell.trim();
          out[column.name] = hiddenOnRow(input, column, row) || typed === "" ? null : typed;
        }
      }
      return out;
    }),
  );
}

function rowComplete(input: TableInput, row: DraftRow): boolean {
  return input.columns.every((column) => column.kind !== "select" || chosen(row.cells[column.name]) !== null);
}

/** *Change all prices by* — every visible box with a "now" figure, moved. */
export function fillByPercent(input: TableInput, rows: readonly DraftRow[], percent: string): DraftRow[] {
  return rows.map((row) => {
    const cells = { ...row.cells };
    for (const column of input.columns) {
      if (!isMoneyColumn(column) || hiddenOnRow(input, column, row)) continue;
      const figure = nowFigure(input, column, row);
      if (figure === undefined || figure === null) continue;
      cells[column.name] = boxFigure(column, scaleByPercent(figure, percent));
    }
    return { id: row.id, cells };
  });
}

/** `+5 %`, `−10 %` — the language's own percent form, sign always shown. A
 *  label only: the figure that MOVES money is the string, in `scaleByPercent`. */
export function percentLabel(value: string): string {
  const share = Number(value) / 100;
  if (!Number.isFinite(share)) return value;
  return new Intl.NumberFormat(i18n.language || "en", {
    style: "percent",
    signDisplay: "exceptZero",
    maximumFractionDigits: 2,
  }).format(share);
}

function shownFigure(column: ReportInputColumn, figure: string, currency: string | null): string {
  if (currency === null) {
    return column.kind === "unit_price" ? formatRateNumber(figure) : formatMoneyInput(figure);
  }
  return column.kind === "unit_price" ? formatRate(figure, currency) : formatMoney(figure, currency);
}

function displayValue(
  input: TableInput,
  column: ReportInputColumn,
  row: DraftRow,
  regional: { timeZone: string; dateFormat: RegionalDateFormat },
): string | null {
  if (column.from === undefined) return null;
  const record = chosenFrom(input, column.from, row);
  if (record === undefined) return null;
  const labelled = record[`${column.name}_label`];
  const raw = typeof labelled === "string" && labelled !== "" ? labelled : record[column.name];
  if (typeof raw !== "string" || raw === "") return null;
  return DATE_ONLY.test(raw) ? formatDate(raw, regional.timeZone, regional.dateFormat) : raw;
}

export interface DeclaredInputsArgs {
  inputs: readonly ReportInput[];
  /** The committed values, from the URL. */
  values: ReportInputValues;
  /** Commit new values — the viewer writes them to the URL, which runs. */
  onCommit: (next: ReportInputValues) => void;
  currency: string | null;
  timeZone: string;
  dateFormat: RegionalDateFormat;
  t: Translator;
}

/**
 * THE DECLARED INPUTS, AS FOUR PIECES THE VIEWER PLACES.
 *
 * `fields` sit in the parameter bar beside the fixed filters; `run` is the
 * bar's action (present only when a table input exists — a report with only
 * dropdowns re-runs on each choice, as every report here always has);
 * `tables` sit under the bar; `used` sits under the result and states the
 * proposed figures the result was worked out from.
 */
export function useDeclaredInputs(args: DeclaredInputsArgs): {
  fields: ReactNode;
  run: ReactNode;
  tables: ReactNode;
  used: ReactNode;
} {
  const { inputs, values, t } = args;
  const tableInputs = inputs.filter((input): input is TableInput => input.kind === "table");
  const [drafts, setDrafts] = useState<Record<string, { source: string; rows: DraftRow[] }>>({});
  const [percents, setPercents] = useState<Record<string, string>>({});
  const counter = useRef(0);

  const rowsOf = useCallback(
    (input: TableInput): DraftRow[] => {
      const source = values[input.param] ?? "";
      const held = drafts[input.param];
      return held !== undefined && held.source === source ? held.rows : parseTableValue(input, source);
    },
    [drafts, values],
  );

  function setRows(input: TableInput, rows: DraftRow[]): void {
    setDrafts((was) => ({ ...was, [input.param]: { source: values[input.param] ?? "", rows } }));
  }

  function commitOne(param: string, value: string): void {
    const next = { ...values };
    if (value === "") delete next[param];
    else next[param] = value;
    args.onCommit(next);
  }

  const fields = inputs.map((input) => {
    if (input.kind === "select") {
      return (
        <SelectField
          key={input.param}
          id={`rep-in-${input.param}`}
          label={t(input.label_key)}
          value={values[input.param] ?? input.default ?? ""}
          options={input.options.map((option) => ({ value: option.value, label: optionLabel(option, t) }))}
          onChange={(value) => commitOne(input.param, value)}
        />
      );
    }
    if (input.kind === "multi") {
      const options = input.options.map((option) => ({ value: option.value, label: optionLabel(option, t) }));
      const raw = values[input.param] ?? input.default ?? "";
      const selected = raw === "" ? [] : raw.split(",");
      const all = input.all_label_key;
      return (
        <div key={input.param} className="min-w-56">
          <CheckDropdown
            id={`rep-in-${input.param}`}
            label={t(input.label_key)}
            allLabel={all === undefined ? "" : t(all)}
            mode={all === undefined ? "pick" : "all"}
            placeholder={t("reports.input.choose")}
            options={options}
            selected={selected}
            onChange={(next) => {
              // Every option ticked one by one IS all — the box then reads the
              // all-label rather than a list of every name.
              const everything = all !== undefined && options.every((option) => next.includes(option.value));
              commitOne(input.param, everything ? "" : next.join(","));
            }}
          />
        </div>
      );
    }
    return (input.shortcuts ?? []).map((shortcut) => {
      const id = `rep-in-${input.param}-${shortcut.kind}`;
      const picked = percents[id] ?? "";
      return (
        <div key={id} className="flex items-end gap-2">
          <SelectField
            id={id}
            label={t(shortcut.label_key)}
            value={picked}
            placeholder={t("reports.input.choosePercent")}
            options={shortcut.options.map((value) => ({ value, label: percentLabel(value) }))}
            onChange={(value) => setPercents((was) => ({ ...was, [id]: value }))}
          />
          <Button
            size="default"
            disabled={picked === ""}
            data-input-fill={input.param}
            onClick={() => setRows(input, fillByPercent(input, rowsOf(input), picked))}
          >
            {t("reports.input.fill")}
          </Button>
        </div>
      );
    });
  });

  const incomplete = tableInputs.some((input) => rowsOf(input).some((row) => !rowComplete(input, row)));
  const run =
    tableInputs.length === 0 ? null : (
      <Button
        variant="primary"
        disabled={incomplete}
        title={incomplete ? t("reports.input.incomplete") : undefined}
        data-input-run=""
        onClick={() => {
          const next = { ...values };
          for (const input of tableInputs) {
            const rows = rowsOf(input);
            if (rows.length === 0) delete next[input.param];
            else next[input.param] = serializeTable(input, rows);
          }
          args.onCommit(next);
        }}
      >
        {t("reports.input.run")}
      </Button>
    );

  const regional = { timeZone: args.timeZone, dateFormat: args.dateFormat };

  const tables = tableInputs.map((input) => {
    const rows = rowsOf(input);
    const update = (index: number, row: DraftRow) =>
      setRows(
        input,
        rows.map((one, at) => (at === index ? row : one)),
      );
    const columns: TableArrayColumn<DraftRow>[] = input.columns.map((column) => ({
      key: column.name,
      label: columnLabel(input, column, t),
      numeric: isMoneyColumn(column),
      cell: (row, index) => {
        if (column.kind === "display") {
          const shown = displayValue(input, column, row, regional);
          return shown === null ? <Dash /> : <span className="whitespace-nowrap">{shown}</span>;
        }
        if (column.kind === "select") {
          const options = selectOptions(input, column, row, t);
          const parentOpen = column.depends_on === undefined || chosen(row.cells[column.depends_on]) !== null;
          return (
            <CellSelect
              // The walk of 2026-10-12: at 1280 the Type and Item boxes were a
              // bare chevron, at 1440 they read *Rate* and *Sample — E*. `fit`
              // sizes the box to its longest choice; the table scrolls inside
              // its own box when a row is wider than the screen (DEF-CUS-9093).
              fit
              name={`${input.param}.${column.name}`}
              label={columnLabel(input, column, t)}
              value={row.cells[column.name] ?? ""}
              options={options}
              placeholder={t("reports.input.choose")}
              blockedReason={parentOpen ? undefined : t("reports.input.chooseFirst")}
              onChange={(value) => update(index, changeSelect(input, row, column.name, value, t))}
            />
          );
        }
        if (hiddenOnRow(input, column, row)) {
          return <Dash />;
        }
        const figure = nowFigure(input, column, row);
        const noun = rowFact(input, row, "item_kind") === "capacity" ? rowFact(input, row, "item_noun") : undefined;
        return (
          <div className="flex flex-col items-end gap-1">
            <input
              type="text"
              inputMode="decimal"
              className="input input-num w-28"
              aria-label={columnLabel(input, column, t)}
              data-cell={`${input.param}.${column.name}`}
              value={row.cells[column.name] ?? ""}
              onChange={(event) =>
                update(index, { id: row.id, cells: { ...row.cells, [column.name]: event.target.value } })
              }
            />
            {figure !== undefined && (
              <span className="text-xs text-neutral-600" data-now={`${input.param}.${column.name}`}>
                {figure === null
                  ? t("reports.input.nowBilled")
                  : t("reports.input.now", { amount: shownFigure(column, figure, args.currency) })}
                {noun !== undefined && (
                  <>
                    <br />
                    {t("reports.input.perItem", { noun })}
                  </>
                )}
              </span>
            )}
          </div>
        );
      },
    }));
    return (
      <TableArray<DraftRow>
        key={input.param}
        title={t(input.label_key)}
        collection={`input-${input.param}`}
        columns={columns}
        rows={rows}
        rowKey={(row) => row.id}
        emptyText={t("reports.input.empty")}
        onChange={(next) => setRows(input, next)}
        removeLabel={t("reports.input.remove")}
        note={input.note_key === undefined ? undefined : t(input.note_key)}
        actions={[
          {
            key: "add",
            label: t(input.add_label_key ?? "reports.input.addRow"),
            onClick: () => {
              counter.current += 1;
              const cells: Record<string, string> = {};
              for (const column of valueColumns(input)) cells[column.name] = "";
              setRows(input, [...rows, { id: `n${counter.current}`, cells }]);
            },
          },
        ]}
      />
    );
  });

  // *Proposed figures used* — from the COMMITTED rows (the URL), so it states
  // what the result on screen was worked out from, never an unsaved edit.
  const usedLines = tableInputs.flatMap((input) =>
    parseTableValue(input, values[input.param]).map((row) => {
      const head = input.columns
        .filter((column) => column.kind === "select" && column.choices !== undefined)
        .map((column) => {
          const value = chosen(row.cells[column.name]);
          const choice = choiceOf(input, column, row);
          return value === null || choice === undefined ? null : choiceLabel(choice, t);
        })
        .filter((label): label is string => label !== null && label !== "")
        .join(" · ");
      const facts = input.columns
        .filter((column) => column.kind === "display")
        .map((column) => displayValue(input, column, row, regional))
        .filter((value): value is string => value !== null && !head.includes(value));
      const changes = input.columns
        .filter((column) => isMoneyColumn(column) && !hiddenOnRow(input, column, row))
        .map((column) => {
          const figure = nowFigure(input, column, row);
          const typed = (row.cells[column.name] ?? "").trim();
          const from =
            figure === undefined || figure === null
              ? t("reports.input.billed")
              : shownFigure(column, figure, args.currency);
          const to = typed === "" ? t("reports.input.billed") : shownFigure(column, typed, args.currency);
          return `${columnLabel(input, column, t)} ${from} → ${to}`;
        });
      return {
        key: `${input.param}-${row.id}`,
        head: facts.length === 0 ? head : `${head} (${facts.join(", ")})`,
        changes: changes.join(" · "),
      };
    }),
  );
  const used =
    usedLines.length === 0 ? null : (
      <Panel title={t("reports.input.used")} data-input-used="">
        <ul className="m-0 flex list-disc flex-col gap-1 pl-5 text-base">
          {usedLines.map((line) => (
            <li key={line.key}>
              <span className="font-semibold">{line.head}</span> {line.changes}
            </li>
          ))}
        </ul>
      </Panel>
    );

  return { fields: <>{fields}</>, run, tables: <>{tables}</>, used };
}

/** A gap that COUNTS the accounts it left out — *3 accounts · No bills in the
 *  period*. Any report may serve one; a gap with no `count` is a plain
 *  sentence and stays in the viewer's existing gap list. */
export function isCountedGap(gap: ReportGap): gap is ReportGap & { count: number } {
  return typeof gap.count === "number";
}

/** *Not worked out*, by reason, from the response's `unavailable`. */
export function CountedGapList(props: { gaps: readonly ReportGap[]; t: Translator }) {
  const counted = props.gaps.filter(isCountedGap);
  if (counted.length === 0) return null;
  return (
    <Panel title={props.t("reports.gap.notWorkedOut")} data-counted-gaps="">
      <ul className="m-0 flex list-disc flex-col gap-1 pl-5 text-base">
        {counted.map((gap) => (
          <li key={gap.code}>
            {props.t("reports.gap.accounts", {
              count: gap.count,
              reason: props.t(gap.message_key ?? `reports.gap.${gap.code}`, {
                defaultValue: props.t(`reports.gap.${gap.code}`),
              }),
            })}
          </li>
        ))}
      </ul>
    </Panel>
  );
}

// ── Lifecycle ─────────────────────────────────────────────
// packet: CR-179-BRC10 (12-governance/change-requests/CR-179-BRC10-rate-impact-report.md) · the server/screen contract of 2026-10-12 · 05-prototype/rate-impact-2026-10-12/04-inputs.png + 05-result.png, read as IMAGES (B14 rule 42)
// screens: S46 (2·1 — the standard report viewer)
// generated: 2026-10-12 by the Rate Impact screen lane
// exceptions: (1) the drawing's per-block column headers are not drawn — the framework's one grouped table has one header row (B14 rule 20) · (2) a dropdown or multi change re-runs at once, because the table's choices depend on it; only the table waits for Run · (3) the result's per-cell red/plus colouring of Change is not drawn — the kit's money cell owns that
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
