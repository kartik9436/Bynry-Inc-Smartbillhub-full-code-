// ── Trace ──────────────────────────────────────────────
// Change:   CR-167-BRC10 round 3 task 8 — the plan edit form's saved state
//           (image 42 names it *new version published*): a tick, *<name>
//           saved*, one sentence, *Back to plan*. The discount and tax edit
//           forms' saved panel, copied (B14 rule 43: their shape, this form's
//           words).
// ───────────────────────────────────────────────────────
import { Button } from "@/components/Button";
import { Panel } from "@/components/Panel";

import type { Translator } from "./planFormShared";

export function EditPlanSavedPanel(props: {
  name: string;
  /** One FACT sentence (B14 rule 33) — what was saved, and where it is logged. */
  sentence: string;
  onBack: () => void;
  t: Translator;
}) {
  const { t } = props;
  return (
    <Panel as="section" aria-labelledby="plan-edit-saved-title" data-plan-edit-saved="">
      <span
        aria-hidden="true"
        className="flex h-11 w-11 items-center justify-center bg-success-700 font-heading text-h4 text-bg"
      >
        ✓
      </span>
      <h2 id="plan-edit-saved-title" className="m-0 mt-4 font-heading text-h4" role="status">
        {t("rating.planEdit.saved.title", { name: props.name })}
      </h2>
      <p className="m-0 mt-3 text-md">{props.sentence}</p>
      <div className="mt-4 flex justify-end border-t border-divider pt-4">
        <Button variant="primary" onClick={props.onBack}>
          {t("rating.planEdit.backToPlan")}
        </Button>
      </div>
    </Panel>
  );
}
