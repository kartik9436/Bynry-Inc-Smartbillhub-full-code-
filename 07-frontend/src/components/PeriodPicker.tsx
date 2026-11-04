// ── Trace ──────────────────────────────────────────────
// Defects:  DEF-LED-10071 (J3 — the Journal's Period filter) · DEF-LED-10072
//           (P1/P2/P4/P8/P9 — the Trial balance period becomes a control) ·
//           DEF-LED-10075 (dates in the utility's format, not ISO)
// Ruling:   12-governance/02-decision-log.md 2026-10-12 "FINANCE: JOURNAL
//           SEARCH AND THE PERIOD CONTROLS", CONFIRMED (PO: *"this good please
//           start and fix it"*). The Trial balance report: *"user want filter
//           to and from date you have given but it is plan text"*.
// Rules:    B14 rule 43 (a piece of UI is a COMPONENT — P8 asks for ONE picker
//           serving both tabs) · rule 38/44 (built from the kit's own fields)
//           · rule 21 (Tailwind utilities only — this file is on
//           `styles/route-b-migrated.txt`) · rule 33 (labels ≤3 words, a
//           refusal ≤6) · BR-TEN-043 (the business date is the caller's)
// ───────────────────────────────────────────────────────
//
// ONE PERIOD PICKER: a quick choice, then From and To.
//
// * Choosing a quick choice FILLS From and To and applies them.
// * Typing a date switches the choice to **Custom** (P2).
// * A window that ends before it starts, or after today, is REFUSED in words
//   beside To and is never applied (P4) — the screen goes on showing the last
//   window it was given, so a half-typed date never empties a report.
//
// ⚠ **THE PICKER HOLDS A DRAFT AND THE CALLER HOLDS THE TRUTH.** What a clerk is
// typing lives here; what the screen is SHOWING is the `value` prop, which the
// caller keeps in its URL (J5 · P7). `onChange` fires only with a window that
// may be applied, so a URL can never carry a refused period.
//
// The dates are drawn by `DatePickerField` with `regional` on, so the box shows
// the utility's own format — `10/01/2026`, never `2026-10-01` (P9).

import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";

import type { RegionalDateFormat } from "./DateCell";
import { DatePickerField, SelectField } from "./FormModal";
import {
  periodRefusal,
  periodWindow,
  type PeriodChoice,
  type PeriodMonth,
  type PeriodRefusal,
  type PeriodValue,
} from "./periodWindow";

type Translator = (key: string, params?: Record<string, unknown>) => string;

/**
 * A quick choice's WORD. Spelled as six literal `t()` calls rather than one
 * computed key, so the catalogue gates can see every key this file uses.
 */
export function periodChoiceLabel(choice: PeriodChoice, t: Translator): string {
  switch (choice) {
    case "this_month":
      return t("forms.period.thisMonth");
    case "last_month":
      return t("forms.period.lastMonth");
    case "last_30":
      return t("forms.period.last30");
    case "last_60":
      return t("forms.period.last60");
    case "last_90":
      return t("forms.period.last90");
    case "custom":
      return t("forms.period.custom");
  }
}

/** The refusal sentence beside To, or `undefined` when there is none. */
export function periodRefusalText(refusal: PeriodRefusal | null, t: Translator): string | undefined {
  if (refusal === "toBeforeFrom") return t("forms.period.toBeforeFrom");
  if (refusal === "endsAfterToday") return t("forms.period.endsAfterToday");
  return undefined; // an unfinished date is not an error yet
}

interface Draft {
  choice: PeriodChoice | "";
  from: string;
  to: string;
}

function draftOf(value: PeriodValue | null): Draft {
  return value === null ? { choice: "", from: "", to: "" } : { ...value };
}

export function PeriodPicker(props: {
  /** The id prefix — the three fields are `<id>.choice`, `<id>.from`, `<id>.to`. */
  id: string;
  /** The quick choice's label, e.g. *Period*. */
  label: string;
  /** What the screen is showing. `null` is NO period — every date (J4). */
  value: PeriodValue | null;
  choices: readonly PeriodChoice[];
  /** The utility's business date, `YYYY-MM-DD` — never the browser's clock. */
  today: string;
  /** The finance month a *This month* means. */
  month?: PeriodMonth | null;
  dateFormat: RegionalDateFormat;
  onChange: (next: PeriodValue) => void;
  /** `row` for a params band, `stack` inside a filter panel. */
  layout: "row" | "stack";
}) {
  const { t } = useTranslation();
  const translate: Translator = (key, params) => t(key, params);
  const { value, today, month } = props;
  const [draft, setDraft] = useState<Draft>(() => draftOf(value));
  const keyOf = (one: PeriodValue | null) =>
    one === null ? "" : `${one.choice}|${one.from}|${one.to}`;
  const valueKey = keyOf(value);
  // What this picker last handed the caller. Its own window coming back as the
  // `value` prop is an ECHO, not news: resyncing on it would rewrite a date box
  // mid-typing (`10/05/20` is already a valid day — 2020 — so the caller hears
  // about it before the clerk has finished the year).
  const [emitted, setEmitted] = useState<string | null>(null);
  // A new value from ELSEWHERE (a link opened, a chip cleared, a quick choice
  // applied by another control) replaces whatever was being typed.
  useEffect(() => {
    if (valueKey !== emitted) setDraft(draftOf(value));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [valueKey]);
  function emit(next: PeriodValue): void {
    setEmitted(keyOf(next));
    props.onChange(next);
  }

  const refusal = draft.choice === "custom" ? periodRefusal(draft.from, draft.to, today) : null;

  function choose(next: string): void {
    const choice = props.choices.find((one) => one === next);
    if (choice === undefined) return;
    const window = periodWindow(choice, today, month);
    if (window !== null) {
      setDraft({ choice, ...window });
      emit({ choice, ...window });
      return;
    }
    // Custom keeps the dates already showing and asks for nothing else.
    const typed = { choice, from: draft.from, to: draft.to };
    setDraft(typed);
    if (periodRefusal(typed.from, typed.to, today) === null) emit(typed);
  }

  function type(end: "from" | "to", day: string): void {
    const typed: Draft = { ...draft, choice: "custom", [end]: day };
    setDraft(typed);
    if (periodRefusal(typed.from, typed.to, today) === null) {
      emit({ choice: "custom", from: typed.from, to: typed.to });
    }
  }

  return (
    <div
      className={
        props.layout === "row" ? "flex flex-wrap items-start gap-4" : "flex flex-col gap-2"
      }
      data-period-picker={props.id}
    >
      <SelectField
        id={`${props.id}.choice`}
        label={props.label}
        value={draft.choice}
        onChange={choose}
        placeholder={value === null && draft.choice === "" ? t("forms.period.anyDate") : undefined}
        options={props.choices.map((choice) => ({
          value: choice,
          label: periodChoiceLabel(choice, translate),
        }))}
      />
      <DatePickerField
        id={`${props.id}.from`}
        label={t("table.filters.dateFrom")}
        value={draft.from}
        onChange={(day) => type("from", day)}
        dateFormat={props.dateFormat}
        max={draft.to === "" ? today : draft.to}
        regional
      />
      <DatePickerField
        id={`${props.id}.to`}
        label={t("table.filters.dateTo")}
        value={draft.to}
        onChange={(day) => type("to", day)}
        dateFormat={props.dateFormat}
        min={draft.from === "" ? undefined : draft.from}
        max={today}
        error={periodRefusalText(refusal, translate)}
        regional
      />
    </div>
  );
}
