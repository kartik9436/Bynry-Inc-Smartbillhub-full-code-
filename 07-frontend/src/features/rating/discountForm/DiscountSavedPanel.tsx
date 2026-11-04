// ── Trace ──────────────────────────────────────────────
// Change:   CR-166-BRC10 round 2 task 4 — the saved state, built from image 18
//           of `05-prototype/discounts-2026-10-03/images/` (B14 rule 42).
// ───────────────────────────────────────────────────────
//
// Saving creates a DRAFT (CR-166 §9: *"`POST /discounts` saves a draft"*), and
// nothing reaches a bill until it is on a plan and approved — so the one
// instruction after the fact says where to go next.
import { Button } from "@/components/Button";
import { formatDate } from "@/components/DateCell";
import { Panel } from "@/components/Panel";

import { valueBoxFor, effectiveType, valueFigure } from "./discountFormModel";
import type { DiscountFormDraft } from "./discountFormModel";
import type { DiscountFormLists, Translator } from "./discountFormShared";

export function DiscountSavedPanel(props: {
  draft: DiscountFormDraft;
  lists: DiscountFormLists;
  savedName: string;
  onOpen: () => void;
  onAnother: () => void;
  t: Translator;
}) {
  const { draft, lists, t } = props;
  const figure = valueFigure(draft);
  const percent = valueBoxFor(effectiveType(draft)) === "percent";
  const parts = [
    figure === null ? null : percent ? t("rating.discountForm.saved.off", { value: figure }) : figure,
    draft.effective_from === ""
      ? null
      : t("rating.discountForm.saved.from", { date: formatDate(draft.effective_from, lists.timeZone, lists.dateFormat) }),
  ].filter((part): part is string => part !== null);
  return (
    <Panel as="section" aria-labelledby="discount-saved-title" data-discount-saved="">
      <span
        aria-hidden="true"
        className="flex h-11 w-11 items-center justify-center bg-success-700 font-heading text-h4 text-bg"
      >
        ✓
      </span>
      <h2 id="discount-saved-title" className="m-0 mt-4 font-heading text-h4" role="status">
        {t("rating.discountForm.saved.title", { name: props.savedName })}
      </h2>
      <p className="m-0 mt-3 text-md">
        {parts.length > 0 && `${parts.join(" · ")}. `}
        {t("rating.discountForm.saved.next")}
      </p>
      <div className="mt-4 flex justify-end gap-2 border-t border-divider pt-4">
        <Button variant="secondary" onClick={props.onOpen}>
          {t("rating.discountForm.saved.open")}
        </Button>
        <Button variant="primary" onClick={props.onAnother}>
          {t("rating.discountForm.saved.another")}
        </Button>
      </div>
    </Panel>
  );
}
