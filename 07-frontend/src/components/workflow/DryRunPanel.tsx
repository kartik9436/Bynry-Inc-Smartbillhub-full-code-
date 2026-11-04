// ── Trace ──────────────────────────────────────────────
// Change:   CR-023 — Stage 4 LOAD, the dry run (design B15 §4.4)
// Rules:    BR-MET-085 (a premises load creates premises and NOTHING else — the
//           dry run's second clause is withdrawn with the behaviour behind it) ·
//           B14 rule 11 (a form that writes shows a "what this will do" box
//           before its commit button) · B14 rule 21 (Tailwind)
// Impacts:  components/workflow/WorkflowRunner.tsx composes this.
// ───────────────────────────────────────────────────────
import { useTranslation } from "react-i18next";

import { CheckboxField } from "@/components/FormModal";
import { Kicker } from "@/components/TextBits";

import type { ApprovalNote, DryRunFigure, LoadOptions } from "./contract";
import type { WriteModeOption } from "./WriteModeChoice";
import { WriteModeStated } from "./WriteModeChoice";
import * as WF from "./workflowKit";

/**
 * `DRY RUN · WHAT WILL BE WRITTEN` — the figure list, the write mode STATED
 * (chosen at step 1 — DEF-770), the approval note and the two checkboxes.
 *
 * ⚠ THIS IS B14 RULE 11's CONSEQUENCE PREVIEW, ON THE ONE STAGE THAT WRITES.
 * Everything before stage 4 was rehearsal; this box is the last thing a person
 * reads before the only endpoint in the runner that changes the database.
 *
 * ⚠ THE FIGURES ARE THE SERVER'S, PRE-WORDED, AND `dry-run` AND `load` MUST
 * AGREE (B15 §16 TC-16: *"a dry run that lies is worse than none"*). This panel
 * prints `POST /imports/{id}/dry-run`'s answer and computes nothing — a screen
 * that re-derived "will create" from the row count would report a number the
 * loader never uses.
 *
 * ⚠ AND THE `Will create` LINE HAS ONE CLAUSE, NOT TWO. r10 prints *"426
 * premises · 181 single-unit premises auto-create their unit"* here and again
 * on the receipt; BR-MET-085 withdraws the auto-create with the sentence. Do
 * not restore it from the screenshot — B15 §4A exists to stop exactly that, and
 * an auto-created unit is a row the operator never supplied and never reviewed.
 *
 * ⚠ THE APPROVAL THRESHOLD IS DATA. B15 §4.4 records the 5% as r10 copy rather
 * than a signed rule, and DEF-435 is what a screen constant no server enforces
 * costs. The percentage, the reject count and the batch size all arrive in
 * `ApprovalNote`.
 */
export interface DryRunPanelProps {
  figures: readonly DryRunFigure[];
  modes: readonly WriteModeOption[];
  selectedModeId: string;
  /** ⚠ DEF-770 — the mode is CHOSEN at step 1 and only STATED here, so this
   *  takes the operator back to the step that owns it rather than offering a
   *  second control that would compete with it. */
  onChangeModeRequested: () => void;
  approval: ApprovalNote;
  options: LoadOptions;
  onOptionsChange: (next: LoadOptions) => void;
  /** Unique per runner instance. */
  idPrefix: string;
  /** `DEF-PAY-10758` (L3-03) — false for a target that can never roll back
   *  (payments): the tick would promise a point the server never makes, and the
   *  receipt then read *"Rollback point: Not recorded"* over a ticked box. */
  offerRollbackPoint?: boolean;
}

export function DryRunPanel({
  figures,
  modes,
  selectedModeId,
  onChangeModeRequested,
  approval,
  options,
  onOptionsChange,
  idPrefix,
  offerRollbackPoint = true,
}: DryRunPanelProps) {
  const { t } = useTranslation();
  return (
    <div data-workflow="dry-run">
      <div className={WF.FIG_ROWS} data-workflow="dry-run-figures">
        <Kicker as="div" className={WF.FIG_CAPTION}>
          {t("workflow.dry.caption")}
        </Kicker>
        {figures.map((figure) => (
          <div key={figure.id} className={WF.FIG_ROW} data-workflow-figure={figure.id}>
            <span>{figure.label}</span>
            <b className={figure.numeric ? WF.FIG_ROW_VALUE : WF.FIG_ROW_VALUE_TEXT}>
              {figure.value}
            </b>
          </div>
        ))}
      </div>

      {/* ⚠ **STATED HERE, CHOSEN AT STEP 1 — DEF-770.** This was a second
          `SegmentedField`, identical to step 1's, and the PO said so looking at
          the deployed screen: *"Write mode from this screen may not required .
          it is already added on step 1"*. They are right, and the reason is
          sharper than the duplication: **two controls for one setting invite the
          question of which one wins**, and there is no good answer to give.

          It is not simply deleted, because the dry run REHEARSES against this
          mode — an operator reading "will create 0 · will update 9,881" has to
          know which premise produced it, or the figures are unreadable. So the
          mode stays VISIBLE as a fact, and `Change it` walks back to the step
          that owns it (`back()` already steps a stage at a time, so nobody is
          stranded — that was the only reason a control was kept here).

          ⚠ **CR-042 — THE SENTENCE IS NOW THE SHARED ONE, AND THAT FIXED A REAL
          GAP.** It used to be `t("workflow.dry.writeModeStated", { defaultValue:
          … })` and that key was in NO catalogue, so a Hindi or Japanese operator
          read this line in English on the last screen before a commit. The
          shared `WriteModeStated` uses `workflow.writeMode.stated`, which is in
          all eleven. */}
      <WriteModeStated
        value={selectedModeId}
        options={modes}
        onChangeRequested={onChangeModeRequested}
        t={t}
      />

      <div data-workflow="approval">
        <Kicker as="div" className={WF.FIG_CAPTION}>
          {t("workflow.dry.approval")}
        </Kicker>
        {approval.always_requires !== null && (
          <p className={WF.NOTE_BLOCK_WARN} data-workflow="approval-always">
            {approval.always_requires}
          </p>
        )}
        <p className={WF.NOTE_BLOCK} data-workflow="approval-threshold">
          {t("workflow.dry.thresholdSentence", { pct: approval.threshold_pct })}{" "}
          {t("workflow.dry.thisRunSentence", {
            rejected: approval.rejected,
            rows: approval.of_rows,
          })}
        </p>
      </div>

      <div className={WF.CHECK_STACK}>
        {offerRollbackPoint && (
          <CheckboxField
            id={`${idPrefix}-rollback-point`}
            label={t("workflow.dry.rollbackPoint")}
            checked={options.create_rollback_point}
            onChange={(checked) => onOptionsChange({ ...options, create_rollback_point: checked })}
          />
        )}
        <CheckboxField
          id={`${idPrefix}-notify`}
          label={t("workflow.dry.notify")}
          checked={options.notify_on_finish}
          onChange={(checked) => onOptionsChange({ ...options, notify_on_finish: checked })}
        />
      </div>
    </div>
  );
}
