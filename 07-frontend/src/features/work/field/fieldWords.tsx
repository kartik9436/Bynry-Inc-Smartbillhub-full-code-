// ── Trace ──────────────────────────────────────────────
// Stories:  US-WRK-055 · US-WRK-059 (EP-WRK-11)
// Rules:    BR-FLD-00004 (four outcomes; Failed is the work failing, Waiting
//           on someone is being BLOCKED — E2E-06: a blocked job does not read
//           as a failure) · B14 rule 43 (one component, every host) ·
//           rule 21 (Tailwind only — this file is on route-b-migrated.txt)
// ───────────────────────────────────────────────────────
//
// The three small pieces the queue AND the order page both draw — the outcome
// pill, the reason (or that it is missing) and the blocker. One home, so the
// queue and the order cannot describe the same job in two ways (rule 43).
import { useTranslation } from "react-i18next";

import { StatusPill } from "@/components/StatusPill";
import type { StatusTone } from "@/components/StatusPill";
import { Dash } from "@/features/customers/customersShared";

import { FIELD_BLOCKERS } from "./fieldDeskEndpoints";
import type { FieldOutcomeRecord, FieldOutcomeWord } from "./fieldDeskEndpoints";

/** ⚠ WAITING ON SOMEONE IS `info`, NEVER `danger` — E2E-06, *"a blocked job is
 *  not a failure and does not read as one"*. */
export function fieldOutcomeTone(word: FieldOutcomeWord): StatusTone {
  switch (word) {
    case "passed":
      return "success";
    case "partly_done":
      return "warning";
    case "failed":
      return "danger";
    default:
      return "info";
  }
}

export function FieldOutcomePill(props: { word: FieldOutcomeWord | null }) {
  const { t } = useTranslation();
  if (props.word === null) return <Dash />;
  return (
    <span data-field-outcome={props.word}>
      <StatusPill tone={fieldOutcomeTone(props.word)}>{t(`work.field.outcome.${props.word}`)}</StatusPill>
    </span>
  );
}

/** The reason as the technician wrote it — or, where an outcome needs one and
 *  none came back, a warning pill saying so (`reason_missing`). */
export function FieldReason(props: { record: Pick<FieldOutcomeRecord, "reason" | "reason_missing"> }) {
  const { t } = useTranslation();
  if (props.record.reason !== null) return <span data-field-reason="">{props.record.reason}</span>;
  if (props.record.reason_missing) {
    return (
      <span data-field-reason-missing="">
        <StatusPill tone="warning">{t("work.field.reasonMissing")}</StatusPill>
      </span>
    );
  }
  return <Dash />;
}

/** R4's three blockers in words; anything else the handset sent, as sent. */
export function FieldBlocker(props: { blocker: string | null }) {
  const { t } = useTranslation();
  if (props.blocker === null) return <Dash />;
  const known = (FIELD_BLOCKERS as readonly string[]).includes(props.blocker);
  return (
    <span data-field-blocker={props.blocker}>
      {known ? t(`work.field.blocker.${props.blocker}`) : props.blocker}
    </span>
  );
}
