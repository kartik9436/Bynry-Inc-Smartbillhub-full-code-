// ── Trace ──────────────────────────────────────────────
// Change:   CR-023 — the ETL runner's numbered stage strip
// Rules:    BR-SHL-018 (rail semantics: numbered; completed steps back-clickable;
//           forward only via a validated advance) · B14 rule 3 (any flow with
//           2+ stages uses the numbered step rail) · B14 rule 21 (Tailwind)
// Impacts:  components/workflow/WorkflowRunner.tsx renders this.
// ───────────────────────────────────────────────────────
import { useTranslation } from "react-i18next";

import type { WorkflowCopy, WorkflowStage } from "./kinds";
import * as WF from "./workflowKit";

/**
 * `1 Extract · 2 Transform · 3 Validate · 4 Load · 5 Result`, with the current
 * stage highlighted and **the writing stage marked as the writing stage**.
 *
 * ⚠ THE `WRITES` MARK IS THE ONE THING r10 DOES NOT DRAW, AND IT IS THE ONE THE
 * RUNNER PROMISES. r10 prints *"Five stages · nothing is written until you
 * commit at stage four"* under the title and then draws five identical steps,
 * so the promise points at a stage the strip never identifies. B15 §4's own
 * state diagram marks stage 4 *"⚠ THE ONLY STAGE THAT WRITES"*; this puts that
 * on the strip, beside the number the sentence names.
 *
 * ⚠ AND THE FORWARD FENCE IS BR-SHL-018, NOT r10. r10 wires every step to a
 * `goWf<n>` handler, so a click on stage 4 jumps straight to the writing stage
 * from stage 1. BR-SHL-018 is CONFIRMED law — *"completed steps back-clickable;
 * forward only via validated Continue"* — and where a ratified rule and r10
 * disagree the rule wins (B14's own precedent, rule 18's 66% → 80%). An
 * upcoming stage keeps full opacity and loses only the pointer: it is not
 * broken, it is simply not navigation yet.
 */
export interface StageBarProps {
  stages: readonly WorkflowStage[];
  /** 1-based. */
  current: number;
  /** The furthest stage ever advanced into — the forward fence. */
  reached: number;
  onSelect: (stage: number) => void;
  /**
   * `undefined` draws the shared promise sentence; `null` draws none; an object
   * draws that target's own. See `WorkflowOwnCopy.railPromise` — the Meter
   * Reads blueprint lists the equivalent stage-4 sentence as REMOVED, *"11
   * words of rationale. The `WRITES` chip on the rail says it without a
   * sentence."*
   */
  promise?: WorkflowCopy | null;
}

export function StageBar({ stages, current, reached, onSelect, promise }: StageBarProps) {
  const { t } = useTranslation();
  return (
    <div data-workflow="stagebar">
      {/* The promise, under the title and above the strip it describes —
          unless the target has declared it away (B14 rule 33: rationale is
          zero words on screen). */}
      {promise !== null && (
        <p className={WF.PROMISE} data-workflow="promise">
          {promise === undefined
            ? t("workflow.promise")
            : t(promise.key, { defaultValue: promise.en })}
        </p>
      )}
      <nav className={WF.RAIL} data-workflow="rail" aria-label={t("workflow.rail")}>
        {stages.map((stage, index) => {
          const number = index + 1;
          const done = number < current;
          const active = number === current;
          const reachable = done && number <= reached;
          return (
            <button
              key={stage.id}
              type="button"
              className={active ? `${WF.RAIL_STEP} ${WF.RAIL_STEP_ACTIVE}` : WF.RAIL_STEP}
              data-workflow-stage={number}
              data-state={active ? "active" : done ? "done" : "upcoming"}
              data-writes={stage.writes ? "true" : "false"}
              disabled={!reachable}
              aria-current={active ? "step" : undefined}
              onClick={() => onSelect(number)}
            >
              <span
                className={
                  active
                    ? `${WF.RAIL_BADGE} ${WF.RAIL_BADGE_ACTIVE}`
                    : done
                      ? `${WF.RAIL_BADGE} ${WF.RAIL_BADGE_DONE}`
                      : WF.RAIL_BADGE
                }
                aria-hidden="true"
              >
                {/* ⚖️ **Q8, PO 2026-09-14, verbatim: *"numbers"*.** Asked
                    whether a COMPLETED step shows a tick or its number, over
                    blueprint drawings that draw `✓` on every stage behind the
                    current one. **B14 rule 3's NUMBERED rail wins over the
                    drawn tick** — its words are *"any flow with 2+ stages uses
                    the numbered step rail (clickable when complete)"* — and the
                    PO ruled it product-wide, *"seven wizards move either way"*,
                    so this badge renders the NUMBER in every state. A completed
                    stage is told apart by its TONE (`RAIL_BADGE_DONE`), never
                    by swapping the glyph. `stageBarNumbers.test.tsx` is what
                    holds it here, because a comment is not the guarantee
                    (hard-won law 1). */}
                {number}
              </span>
              {t(stage.labelKey)}
              {stage.writes && <span className={WF.RAIL_WRITES}>{t("workflow.writes")}</span>}
            </button>
          );
        })}
      </nav>
    </div>
  );
}
