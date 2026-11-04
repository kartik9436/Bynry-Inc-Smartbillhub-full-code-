// ── Trace ──────────────────────────────────────────────
// Change:   CR-165-BRC10 task 4 — the saved state, built from image 17 of
//           `05-prototype/taxes-fees-2026-10-03/images/` (B14 rule 42).
// ───────────────────────────────────────────────────────
import { Button } from "@/components/Button";
import { formatDate } from "@/components/DateCell";
import { Panel } from "@/components/Panel";

import type { TaxFormDraft } from "./taxFormModel";
import { rateFigure, rateUnitKey } from "./taxFormShared";
import type { TaxFormLists, Translator } from "./taxFormShared";

export function TaxSavedPanel(props: {
  draft: TaxFormDraft;
  lists: TaxFormLists;
  savedName: string;
  onOpen: () => void;
  onAnother: () => void;
  t: Translator;
}) {
  const { draft, lists, t } = props;
  const parts = [
    rateFigure(draft) === null ? null : `${rateFigure(draft)} ${t(rateUnitKey(draft))}`,
    draft.effective_from === ""
      ? null
      : t("rating.taxForm.saved.from", { date: formatDate(draft.effective_from, lists.timeZone, lists.dateFormat) }),
    lists.reach === null ? null : t("rating.taxForm.saved.reaches", { count: lists.reach.count }),
  ].filter((part): part is string => part !== null);
  return (
    <Panel as="section" aria-labelledby="tax-saved-title" data-tax-saved="">
      <span
        aria-hidden="true"
        className="flex h-11 w-11 items-center justify-center bg-success-700 font-heading text-h4 text-bg"
      >
        ✓
      </span>
      <h2 id="tax-saved-title" className="m-0 mt-4 font-heading text-h4" role="status">
        {t("rating.taxForm.saved.title", { name: props.savedName })}
      </h2>
      {parts.length > 0 && <p className="m-0 mt-3 text-md">{`${parts.join(" · ")}.`}</p>}
      <div className="mt-4 flex justify-end gap-2 border-t border-divider pt-4">
        <Button variant="secondary" onClick={props.onOpen}>
          {t("rating.taxForm.saved.open")}
        </Button>
        <Button variant="primary" onClick={props.onAnother}>{t("rating.taxForm.saved.another")}</Button>
      </div>
    </Panel>
  );
}
