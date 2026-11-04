// ── Trace ──────────────────────────────────────────────
// Change:   CR-166-BRC10 round 3 task 7 — the discount edit form's saved state,
//           built from image 30 of `05-prototype/discounts-2026-10-03/images/`
//           (B14 rule 42): a tick, *<name> saved*, one sentence, *Back to
//           discount*.
// ───────────────────────────────────────────────────────
import { Button } from "@/components/Button";
import { Panel } from "@/components/Panel";

import type { Translator } from "./discountFormShared";

export function EditDiscountSavedPanel(props: {
  name: string;
  /** One FACT sentence (B14 rule 33) — what was saved, and where it is logged. */
  sentence: string;
  onBack: () => void;
  t: Translator;
}) {
  const { t } = props;
  return (
    <Panel as="section" aria-labelledby="discount-edit-saved-title" data-discount-edit-saved="">
      <span
        aria-hidden="true"
        className="flex h-11 w-11 items-center justify-center bg-success-700 font-heading text-h4 text-bg"
      >
        ✓
      </span>
      <h2 id="discount-edit-saved-title" className="m-0 mt-4 font-heading text-h4" role="status">
        {t("rating.discountEdit.saved.title", { name: props.name })}
      </h2>
      <p className="m-0 mt-3 text-md">{props.sentence}</p>
      <div className="mt-4 flex justify-end border-t border-divider pt-4">
        <Button variant="primary" onClick={props.onBack}>
          {t("rating.discountEdit.backToDiscount")}
        </Button>
      </div>
    </Panel>
  );
}
