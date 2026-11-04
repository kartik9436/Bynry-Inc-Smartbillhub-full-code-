// ── Trace ──────────────────────────────────────────────
// Ruling:   PO 2026-10-17, decision log *"WHERE A USER ENTERS A METER
//           READING"* — and, the same day, verbatim: *"use same code
//           components"* … *"for meter reading, date and fetch"*. ONE
//           component for the reading box, its read date and the Fetch
//           control, mounted by every screen that takes a reading.
// Rules:    B14 rule 43 (a piece of UI is a COMPONENT) · rule 21 (Tailwind;
//           on route-b-migrated.txt) · rule 33 (labels ≤ 3 words, a refusal
//           ≤ 6) · hard rule 3 (a reading carries its unit) · BR-MET-129 (a
//           reading is stored; only an error refuses)
// Hosts:    customers/moveInWizard/StepUnit.tsx (Move-in step 1) ·
//           customers/disconnect/record/MarkAsCutDialog.tsx (Mark as cut) ·
//           customers/moveDetail/MoveActionsModals.tsx (Enter opening read)
// Tests:    MeterReadingEntry.dom.test.tsx
// ───────────────────────────────────────────────────────
//
// ⚠ **THE HOST HOLDS THE STATE.** Every host keeps its readings in its own
// shape (a wizard draft keyed by meter number, a dialog's local state), so this
// component is controlled: it renders `value` / `readDate` / `estimate` and
// hands back the whole next entry through `onChange`. It never reaches into a
// host's draft.
//
// ⚠ **A FETCHED READING KEEPS THE METER'S OWN DATE.** When Fetch fills the box,
// the read date becomes the head-end's `read_on` and the date field is locked
// (with its reason under it, BR-SHL-025) while the box still holds that value.
// Typing over the value makes it the clerk's reading again: the date unlocks
// and returns to `defaultReadDate`.
//
// ⚠ **THE DATE BOUNDS ARE REAL BOUNDS, NOT COPY.** `maxDate` (today, in the
// tenant's zone) and `minDate` (the meter's last reading — derived from
// `lastReading.readAt` when not given) are passed to the date input AND decide
// the refusal `readDateProblem` returns, so a host's Continue/Save can hold on
// exactly what the field shows. The server re-checks both
// (`customers.services._refuse_bad_read_dates`).
import type { ApiClient } from "@/api/client";
import { AffixField } from "@/components/AffixField";
import { formatDate } from "@/components/DateCell";
import type { RegionalDateFormat } from "@/components/DateCell";
import { CheckboxField, DatePickerField, TextField } from "@/components/FormModal";
import { formatQuantity } from "@/components/UnitCell";
import type { Translator } from "@/features/tenancy/settingsShared";

import { FetchMeterReading } from "./FetchMeterReading";

/** What the clerk has in front of them for one meter. */
export interface MeterReadingEntryValue {
  value: string;
  /** `YYYY-MM-DD`, or `""` when nothing is chosen. */
  readDate: string;
  estimate: boolean;
  /** The box holds the head-end's reading (and its date). */
  fetched: boolean;
}

export type ReadDateProblem = "required" | "future" | "before_last";

/** The catalogue sentence for each refusal (B14 rule 33: ≤ 6 words). */
export const READ_DATE_PROBLEM_KEY: Record<ReadDateProblem, string> = {
  required: "metering.readingEntry.error.dateRequired",
  future: "metering.readingEntry.error.dateFuture",
  before_last: "metering.readingEntry.error.dateBeforeLast",
};

/**
 * **THE READ-DATE RULE, PURE.** `null` = the date is lawful.
 * Dates are `YYYY-MM-DD`, so a string comparison is a calendar comparison.
 * Equal to the last reading's day is lawful (two reads in a day happen).
 */
export function readDateProblem(
  readDate: string,
  bounds: { minDate?: string | null; maxDate?: string | null },
): ReadDateProblem | null {
  const day = readDate.trim().slice(0, 10);
  if (day === "") return "required";
  if (bounds.maxDate && day > bounds.maxDate.slice(0, 10)) return "future";
  if (bounds.minDate && day < bounds.minDate.slice(0, 10)) return "before_last";
  return null;
}

export interface MeterReadingEntryProps {
  /** The meter NUMBER (`W-5023`) — what the head-end and the read door know. */
  meterNo: string;
  /** Seeds DOM ids; the asset id where the host has one. */
  assetId?: string;
  /** Overrides the DOM id seed (`<idPrefix>-value`, `<idPrefix>-date`). */
  idPrefix?: string;
  /** Overrides the reading box's accessible name (default *Reading for W-1*). */
  readingLabel?: string;
  /** The register's unit (the box's affix). Never invented when absent. */
  unit: string | null;
  /** The meter's last committed reading, if any. Its date is the lower bound. */
  lastReading?: { value: string | null; readAt: string | null } | null;
  value: string;
  readDate: string;
  estimate?: boolean;
  fetched?: boolean;
  onChange: (next: MeterReadingEntryValue) => void;
  /** The date a typed reading takes (the event's date). */
  defaultReadDate?: string;
  /** Fetch: the reading on or last before this day. Absent = the latest. */
  asOf?: string;
  showFetch?: boolean;
  showEstimate?: boolean;
  /** Overrides `lastReading.readAt` as the earliest lawful read date. */
  minDate?: string;
  /** The latest lawful read date — today in the tenant's zone. */
  maxDate?: string;
  /** The reading box's own refusal (e.g. required). */
  error?: string;
  /** Show the date refusal now (hosts turn this on once Save was pressed). */
  showDateError?: boolean;
  /** Labels announced but not drawn — a table cell whose header names them. */
  labelsHidden?: boolean;
  /** Draws the last reading under the box. */
  showLastReading?: boolean;
  required?: boolean;
  /** Warning tone on the box (e.g. below the last read). */
  warning?: string;
  client: ApiClient;
  t: Translator;
  timeZone: string;
  dateFormat: RegionalDateFormat;

  // ── Added by the Assets/Reads/Billing lane (DEF-MET-10183 · DEF-AST-10182,
  // 2026-10-17) — OPTIONAL, so every host above renders what it did. ──────
  /** Overrides the date's accessible name (default *Read date for W-1*). */
  dateLabel?: string;
  /**
   * EXACT DOM ids, where `idPrefix`'s `<p>-value` / `<p>-date` will not do: a
   * `FormModal` keys a field's error by the id, and the server's field errors
   * land under its own field names (`reading`, `read_date`,
   * `final_read_value`) — so a host inside a form passes those names.
   */
  valueId?: string;
  dateId?: string;
  /** `false` where ONE date serves several registers: drawn on the first only. */
  showReadDate?: boolean;
  /** A plain instruction under the box (*"The dial, not the usage."*);
   *  `warning`, when present, takes its place. */
  help?: string;
}

export function MeterReadingEntry(props: MeterReadingEntryProps) {
  const { t } = props;
  const seed = props.idPrefix ?? `reading-${props.assetId ?? props.meterNo}`;
  const estimate = props.estimate === true;
  const fetched = props.fetched === true;
  const minDate = props.minDate ?? props.lastReading?.readAt?.slice(0, 10) ?? undefined;
  const problem = readDateProblem(props.readDate, { minDate, maxDate: props.maxDate });
  const current: MeterReadingEntryValue = {
    value: props.value,
    readDate: props.readDate,
    estimate,
    fetched,
  };
  const emit = (patch: Partial<MeterReadingEntryValue>) => props.onChange({ ...current, ...patch });
  const readingLabel = props.readingLabel ?? t("metering.readingEntry.readingFor", { meter: props.meterNo });
  const dateLabel = props.dateLabel ?? t("metering.readingEntry.dateFor", { meter: props.meterNo });
  const valueId = props.valueId ?? `${seed}-value`;
  const dateId = props.dateId ?? `${seed}-date`;
  const unit = (props.unit ?? "").trim();
  const onValue = (value: string) =>
    emit(
      fetched
        ? { value, fetched: false, readDate: props.defaultReadDate ?? props.readDate }
        : { value },
    );
  const last = props.lastReading;

  return (
    <span className="flex flex-wrap items-start gap-2" data-meter-reading-entry={props.meterNo}>
      {props.showFetch === true ? (
        <FetchMeterReading
          meterNo={props.meterNo}
          asOf={props.asOf}
          client={props.client}
          t={t}
          timeZone={props.timeZone}
          dateFormat={props.dateFormat}
          expectedUnit={unit === "" ? null : unit}
          disabled={estimate}
          currentValue={props.value}
          onFetched={(reading) => emit({ value: reading.value, readDate: reading.read_on, fetched: true })}
        />
      ) : null}
      <span className="flex w-40 flex-col gap-1" data-meter-reading-value={props.meterNo}>
        {unit === "" ? (
          <TextField
            id={valueId}
            label={readingLabel}
            labelHidden={props.labelsHidden}
            required={props.required}
            numeric
            value={props.value}
            readOnly={estimate}
            error={props.error}
            help={props.warning ?? props.help}
            onChange={onValue}
          />
        ) : (
          <AffixField
            id={valueId}
            label={readingLabel}
            labelHidden={props.labelsHidden}
            required={props.required}
            side="end"
            affix={unit}
            value={props.value}
            disabled={estimate}
            tone={props.warning === undefined ? "plain" : "warning"}
            help={props.warning ?? props.help}
            error={props.error}
            onChange={onValue}
          />
        )}
        {props.showLastReading === true && last && last.value !== null ? (
          <span className="text-sm text-neutral-700" data-meter-reading-last={props.meterNo}>
            {t("metering.readingEntry.last", {
              value: unit === "" ? formatQuantity(last.value) : `${formatQuantity(last.value)} ${unit}`,
              date: last.readAt ? formatDate(last.readAt, props.timeZone, props.dateFormat) : "—",
            })}
          </span>
        ) : null}
      </span>
      {props.showReadDate === false ? null : (
      <span className="w-44" data-meter-reading-date={props.meterNo} data-read-date-problem={problem ?? ""}>
        <DatePickerField
          id={dateId}
          label={dateLabel}
          labelHidden={props.labelsHidden}
          required
          regional
          value={props.readDate}
          min={minDate}
          max={props.maxDate}
          dateFormat={props.dateFormat}
          disabled={fetched}
          help={fetched ? t("metering.readingEntry.dateFromMeter") : undefined}
          error={props.showDateError === true && problem !== null ? t(READ_DATE_PROBLEM_KEY[problem]) : undefined}
          onChange={(readDate) => emit({ readDate })}
        />
      </span>
      )}
      {props.showEstimate === true ? (
        <CheckboxField
          id={`${seed}-estimate`}
          label={t("metering.readingEntry.estimate")}
          checked={estimate}
          onChange={(on) => emit(on ? { estimate: true, value: "", fetched: false } : { estimate: false })}
        />
      ) : null}
    </span>
  );
}
