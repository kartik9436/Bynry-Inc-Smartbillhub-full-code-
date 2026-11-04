// ── Trace ──────────────────────────────────────────────
// Change:   CR-166-BRC10 round 3 task 7 — the steps only the EDIT form has,
//           built from images 27, 31, 32, 34 and 35 of
//           `05-prototype/discounts-2026-10-03/images/` (B14 rule 42). Every box
//           in them is the New form's own section component (rule 43); this
//           file adds only what the New form never draws.
// Defects:  DEF-RAT-9292 D36 (value editable on a live discount — now a locked
//           fact strip on *Name and details*, with the door that moves it)
// ───────────────────────────────────────────────────────
//
//   EditInfoDetailsStep  image 27 — Basics (code and type as facts) + *Value and
//                        limits* read, locked, *🔒 Change with a new value.*
//   EditValueStep        images 31/32 — *New value*: Value · Limits · Dates
//                        (a new start, and the day today's value ends);
//                        images 34/35 — *Fix the value*: Value · Limits · the
//                        dates as facts (*🔒 Same dates as today.*) · Reason
import { DatePickerField, TextField } from "@/components/FormModal";
import { formatDate } from "@/components/DateCell";
import { FactBlock } from "@/components/FactBlock";
import { Panel } from "@/components/Panel";

import { BasicsSection, LimitsSection, ReadOnlyFact, ValueSection } from "./DetailsStep";
import { bigFigure, scopeWords } from "./DiscountSummaryPanel";
import { dayBefore } from "./discountEditModel";
import { limitsSetCount, valueFigure } from "./discountFormModel";
import { LockNote, PAIR, SECTION_HEADING, labelOf } from "./discountFormShared";
import type { DiscountStepProps } from "./discountFormShared";

/** The section head with a lock line on the right (images 27, 34). */
function LockedHead(props: { id: string; title: string; note: string }) {
  return (
    <div className="mb-4 flex items-baseline justify-between gap-3">
      <h2 id={props.id} className="m-0 font-heading text-h4">
        {props.title}
      </h2>
      <LockNote>{props.note}</LockNote>
    </div>
  );
}

/** *Value and limits*, READ — three facts and the door that changes them. */
export function ValueLimitsFacts(props: DiscountStepProps) {
  const { draft, lists, t } = props;
  const applies = labelOf(lists.appliesTo, draft.applies_to) || "—";
  const scope = scopeWords(draft, lists);
  const limits = limitsSetCount(draft);
  const facts = [
    { id: "value", label: t("rating.discountForm.review.value"), value: valueFigure(draft) ?? bigFigure(draft, t) },
    {
      id: "applies",
      label: t("rating.discountForm.field.appliesTo"),
      value: scope === applies || scope === "—" ? applies : `${applies} · ${scope}`,
    },
    {
      id: "limits",
      label: t("rating.discountForm.section.limits"),
      value: limits === 0 ? t("rating.discountForm.limits.none") : t("rating.discountForm.limits.set", { count: limits }),
    },
  ];
  return (
    <Panel as="section" aria-labelledby="discount-sec-value-locked">
      <LockedHead
        id="discount-sec-value-locked"
        title={t("rating.discountEdit.section.valueLimits")}
        note={t("rating.discountEdit.lock.value")}
      />
      <FactBlock name="discount-value-limits" variant="strip" columns={3} facts={facts} />
    </Panel>
  );
}

/** Step 1 of *Name and details* on a live discount (image 27). */
export function EditInfoDetailsStep(props: DiscountStepProps) {
  return (
    <div className="flex flex-col gap-5" data-discount-step="edit-details">
      <BasicsSection {...props} />
      <ValueLimitsFacts {...props} />
    </div>
  );
}

/** *New value* (images 31, 32): a new start after today's, and the end. */
function NewValueDates(props: DiscountStepProps & { liveFrom: string }) {
  const { draft, lists, t } = props;
  const day = (value: string) => formatDate(value, lists.timeZone, lists.dateFormat);
  // A start on or before today's start is refused, so "today's value ends
  // 07/31/2026" would describe a save that cannot happen (the tax form's rule).
  const startsHelp =
    draft.effective_from === "" || draft.effective_from <= props.liveFrom
      ? t("rating.discountEdit.help.newFrom")
      : t("rating.discountEdit.help.todayEnds", { date: day(dayBefore(draft.effective_from)) });
  return (
    <Panel as="section" aria-labelledby="discount-sec-new-dates">
      <h2 id="discount-sec-new-dates" className={SECTION_HEADING}>
        {t("rating.discountEdit.section.dates")}
      </h2>
      <div className={PAIR}>
        <DatePickerField
          id="discount-starts"
          label={t("rating.discountEdit.field.newFrom")}
          required
          value={draft.effective_from}
          dateFormat={lists.dateFormat}
          help={startsHelp}
          onChange={(effective_from) => props.onChange({ effective_from })}
        />
        <DatePickerField
          id="discount-ends"
          label={t("rating.discountForm.field.ends")}
          value={draft.effective_to}
          dateFormat={lists.dateFormat}
          help={t("rating.discountForm.help.ends")}
          onChange={(effective_to) => props.onChange({ effective_to })}
        />
      </div>
    </Panel>
  );
}

/** *Fix the value* (image 34): a correction keeps the window it corrects. */
function SameDates(props: DiscountStepProps) {
  const { draft, lists, t } = props;
  const day = (value: string) => (value === "" ? "—" : formatDate(value, lists.timeZone, lists.dateFormat));
  return (
    <Panel as="section" aria-labelledby="discount-sec-same-dates">
      <LockedHead
        id="discount-sec-same-dates"
        title={t("rating.discountEdit.section.dates")}
        note={t("rating.discountEdit.lock.dates")}
      />
      <div className={PAIR}>
        <ReadOnlyFact id="discount-starts" label={t("rating.discountForm.field.starts")} value={day(draft.effective_from)} />
        <ReadOnlyFact
          id="discount-ends"
          label={t("rating.discountForm.field.ends")}
          value={draft.effective_to === "" ? t("rating.discountForm.noEnd") : day(draft.effective_to)}
        />
      </div>
    </Panel>
  );
}

/** *Reason* (images 34, 35) — why the recorded figure was wrong. */
function ReasonSection(props: { reason: string; onReason: (reason: string) => void; t: DiscountStepProps["t"] }) {
  const { t } = props;
  return (
    <Panel as="section" aria-labelledby="discount-sec-reason">
      <h2 id="discount-sec-reason" className={SECTION_HEADING}>
        {t("rating.discountEdit.section.reason")}
      </h2>
      <TextField
        id="discount-reason"
        label={t("rating.discountEdit.field.reason")}
        required
        value={props.reason}
        placeholder={t("rating.discountEdit.placeholder.reason")}
        help={t("rating.discountEdit.help.reason")}
        onChange={props.onReason}
      />
    </Panel>
  );
}

/** Step 1 of *New value from a date* and of *Fix a mistake*. */
export function EditValueStep(
  props: DiscountStepProps & {
    mode: "change" | "correct";
    liveFrom: string;
    reason: string;
    onReason: (reason: string) => void;
  },
) {
  return (
    <div className="flex flex-col gap-5" data-discount-step={props.mode === "change" ? "new-value" : "fix-value"}>
      <ValueSection {...props} />
      <LimitsSection {...props} />
      {props.mode === "change" ? <NewValueDates {...props} /> : <SameDates {...props} />}
      {props.mode === "correct" && <ReasonSection reason={props.reason} onReason={props.onReason} t={props.t} />}
    </div>
  );
}
