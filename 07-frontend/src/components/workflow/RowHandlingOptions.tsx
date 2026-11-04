// ── Trace ──────────────────────────────────────────────
// Change:   CR-023 — Stage 2 TRANSFORM, row handling (design B15 §4.2)
// Rules:    B14 rule 21 (Tailwind) · B14 rule 9/10 (one control vocabulary —
//           the shared `CheckboxField`, never a hand-drawn box)
// Impacts:  components/workflow/WorkflowRunner.tsx composes this.
// ───────────────────────────────────────────────────────
import { useTranslation } from "react-i18next";

import { CheckboxField } from "@/components/FormModal";

import type { RowHandling } from "./contract";
import * as WF from "./workflowKit";

/**
 * The three checkboxes: *Drop exact duplicate rows* · *Keep the latest row when
 * a key appears twice* · *Skip rows with empty required fields rather than
 * rejecting them*.
 *
 * ⚠ THEY ARE `CheckboxField`, NOT A THIRD CHECKBOX. The product already draws
 * this control — `.radio` + `.dot`, the A12 form kit — and a workflow that
 * invented its own box would be the `met-panel-hint`-on-a-customers-screen
 * mistake in a different suit. A kit reuses the vocabulary it finds; it only
 * adds one where none exists.
 *
 * ⚠ AND THE SECOND CHECKBOX OPERATES ON A KEY THE PREMISES MAP MAY NOT HAVE
 * MAPPED. B15 §4.2A: *"keep the latest row when a key appears twice"* keys on
 * `premise_no`, which is OPTIONAL in the map — so with that column ignored, the
 * option is a promise about a key nobody supplied. That is a VALIDATION
 * sentence at stage 3 (`premise_no` unique in the tenant is tier 1), not a
 * silent no-op here, and it is the caller's to raise: this component reports
 * the operator's choice and nothing more.
 */
export interface RowHandlingOptionsProps {
  value: RowHandling;
  /** Unique per runner instance — three ids per mounted runner. */
  idPrefix: string;
  onChange: (next: RowHandling) => void;
}

export function RowHandlingOptions({ value, idPrefix, onChange }: RowHandlingOptionsProps) {
  const { t } = useTranslation();
  return (
    <div className={WF.CHECK_STACK} data-workflow="row-handling">
      <CheckboxField
        id={`${idPrefix}-drop-duplicates`}
        label={t("workflow.rows.dropDuplicates")}
        checked={value.drop_exact_duplicates}
        onChange={(checked) => onChange({ ...value, drop_exact_duplicates: checked })}
      />
      <CheckboxField
        id={`${idPrefix}-keep-latest`}
        label={t("workflow.rows.keepLatest")}
        checked={value.keep_latest_on_key}
        onChange={(checked) => onChange({ ...value, keep_latest_on_key: checked })}
      />
      <CheckboxField
        id={`${idPrefix}-skip-empty`}
        label={t("workflow.rows.skipEmpty")}
        checked={value.skip_rows_missing_required}
        onChange={(checked) => onChange({ ...value, skip_rows_missing_required: checked })}
      />
    </div>
  );
}
