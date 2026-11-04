// ── Trace ──────────────────────────────────────────────
// Change:   CR-168-BRC10 round 4, lane CREWS — the *Shift* row drawn on Add
//           crew member (image 26) and Add a crew (image 29), and the *Set
//           hours* answer on Add a contractor (image 30).
// Rules:    B14 rule 43 (a piece of UI is a COMPONENT — three forms draw this
//           row, so it is written once) · rule 44 (our field kit's label and
//           input, not the drawing's spacing) · rule 39 (label → input) ·
//           rule 21 (Tailwind; on route-b-migrated.txt)
// ───────────────────────────────────────────────────────
//
// Two native time inputs joined by *to*. The browser draws the clock and the
// 12/24-hour form the person's own locale uses; the value is always `HH:MM`,
// which is what `workforce._time_or_none` parses.
import { useTranslation } from "react-i18next";

import { FieldLabel } from "@/components/FormModal";

export interface ShiftValue {
  start: string;
  end: string;
}

export function ShiftField(props: {
  id: string;
  label: string;
  value: ShiftValue;
  onChange: (next: ShiftValue) => void;
}) {
  const { t } = useTranslation();
  return (
    <fieldset className="field m-0 border-0 p-0" data-shift-field={props.id}>
      <FieldLabel id={`${props.id}-label`} label={props.label} required={false} />
      <div className="flex items-center gap-3" role="group" aria-labelledby={`${props.id}-label`}>
        <input
          type="time"
          id={`${props.id}-start`}
          className="input w-40"
          aria-label={t("work.crews.shift.from")}
          value={props.value.start}
          onChange={(event) => props.onChange({ ...props.value, start: event.target.value })}
        />
        <span>{t("work.crews.shift.to")}</span>
        <input
          type="time"
          id={`${props.id}-end`}
          className="input w-40"
          aria-label={t("work.crews.shift.until")}
          value={props.value.end}
          onChange={(event) => props.onChange({ ...props.value, end: event.target.value })}
        />
      </div>
    </fieldset>
  );
}

/** What a write sends: both ends, or neither (`null`) — a half shift is no shift. */
export function shiftPayload(value: ShiftValue): { shift_start: string | null; shift_end: string | null } {
  if (value.start === "" || value.end === "") return { shift_start: null, shift_end: null };
  return { shift_start: value.start, shift_end: value.end };
}

export default ShiftField;
