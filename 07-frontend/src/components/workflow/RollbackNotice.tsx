// ── Trace ──────────────────────────────────────────────
// Change:   CR-023 — Stage 5 RESULT / PRM-04, the rollback callout
//           (design B15 §6.1, §11 PRM-04)
// Rules:    B14 rule 6 (a destructive commit takes the danger tier — B15 §9
//           note 4: "`Commit load ✓` writes; `Roll back this run` reverses.
//           Both qualify") · B14 rule 11 (say what it will do BEFORE the
//           button) · B14 rule 21 (Tailwind)
// Impacts:  components/workflow/WorkflowRunner.tsx composes this; PRM-04's run
//           list draws the same callout above its rollback action.
// ───────────────────────────────────────────────────────
import type { ReactNode } from "react";
import { useTranslation } from "react-i18next";

import { Kicker } from "@/components/TextBits";

import type { WorkflowRollbackBody } from "./kinds";
import * as WF from "./workflowKit";

/**
 * What rolling back THIS run will actually do, said before the button that does
 * it.
 *
 * ⚠ THE "AND THIS IS WHAT IT WILL NOT REVERSE" CLAUSE IS THE WHOLE REASON THIS
 * IS A COMPONENT AND NOT A LINE OF COPY. A rollback that quietly keeps rows is
 * a rollback the operator believes was complete, and the rows it keeps are
 * precisely the ones something else is already attached to — a customer, a
 * meter read, an issued bill. Saying it BEFORE the button is B14 rule 11
 * applied to a reversal; saying it afterwards is an apology.
 *
 * ⛔ **AND THE SENTENCE IS THE TARGET'S OWN (DEF-623, major).** This component
 * used to render one unconditional `t("workflow.rollback.body")` — *"Rolling
 * back reverses every premise and unit the run created…"* — for all six kinds.
 * An ACCOUNTS receipt therefore told the operator that rolling back reverses
 * premises and units, and the three assets receipts said the same, directly
 * above a `danger`-tier control. `body` is now REQUIRED and comes from
 * `kind.rollbackBody`, so the kind that is rendering supplies the sentence and
 * a kind cannot exist without one.
 *
 * ⚠ AND IT IS TINTED DANGER, NOT NEUTRAL. r10 draws this as its ordinary
 * `exception` callout in the same grey as a DETECT hint. B14 rule 6 puts the
 * danger tier on a destructive commit, and B15 §9 note 4 names this action
 * specifically: the sentence takes the same tier as the button it describes so
 * the two read as one control.
 */
export interface RollbackNoticeProps {
  /** The rendering kind's own rollback sentence — `kind.rollbackBody`.
   *  REQUIRED: there is no target-neutral sentence, and the one that used to
   *  stand in for all six was a claim about premises (DEF-623). */
  body: WorkflowRollbackBody;
  /** The action itself — `<Button variant="danger">` — supplied by the screen
   *  that owns the endpoint. Passing it in keeps this component free of any
   *  call: the kit states the consequence, the screen performs it. */
  action: ReactNode;
}

export function RollbackNotice({ body, action }: RollbackNoticeProps) {
  const { t } = useTranslation();
  return (
    <div className={WF.CALLOUT} data-workflow="rollback-notice" role="note">
      <Kicker as="div">{t("workflow.rollback.kicker")}</Kicker>
      <div className={WF.CALLOUT_BODY}>
        {/* `defaultValue` is the English the key was written from. A key that
            has not yet reached the catalogues renders that sentence rather than
            the literal `workflow.accounts.rollback` — the one string in this kit
            where G27/DEF-662's raw-key failure would land above a destructive
            control. */}
        <p>{t(body.key, { defaultValue: body.en })}</p>
        {action}
      </div>
    </div>
  );
}
