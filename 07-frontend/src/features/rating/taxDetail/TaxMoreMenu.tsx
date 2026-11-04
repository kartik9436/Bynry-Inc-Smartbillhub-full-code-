// ── Trace ──────────────────────────────────────────────
// Change:   CR-165-BRC10 round 3 task 6 — the header's ONE Edit and More ▾
//           (image 21). PO 2026-10-03: *"what the point of so many button cant
//           we simiplify based ona ctions"*; README point 5.
// Defect:   DEF-RAT-9272 P35 (four buttons for one job)
// Rules:    BR-SHL-025 (a control that cannot act is disabled WITH its reason)
//           · B14 rule 6 (danger tier on a destructive act) · hard-won law 2
// ───────────────────────────────────────────────────────
import { useRef } from "react";

import { ButtonSummary } from "@/components/Button";
import { RowMenuAction } from "@/components/RowActions";

import type { Translator } from "./taxDetailModel";

/**
 * Statuses a tax can be retired from: it is pricing now, or it will. An ended
 * or superseded row has nothing left to end, and a draft has never priced.
 */
export const RETIRABLE_STATUSES: readonly string[] = ["active", "scheduled"];

/**
 * Duplicate opens the New form filled from this tax (`?duplicate=<id>`,
 * `DEF-RAT-9299`, released in the web walk, CR-165 §16). It was held — drawn
 * disabled — until the New form learned the parameter; the hold's own expiry
 * test is replaced by tests that follow the door to a filled form.
 */
export { DUPLICATE_PARAM } from "../taxForm/taxEditModel";

export function TaxMoreMenu(props: {
  status: string;
  readOnly: boolean;
  onDuplicate: () => void;
  onRetire: () => void;
  t: Translator;
}) {
  const { t } = props;
  const menu = useRef<HTMLDetailsElement | null>(null);
  const close = () => {
    if (menu.current !== null) menu.current.open = false;
  };
  const retireReason = props.readOnly
    ? t("rating.readOnlyReason")
    : RETIRABLE_STATUSES.includes(props.status)
      ? null
      : t("rating.taxDetail.more.retireNotLive");
  return (
    <details ref={menu} className="relative inline-flex" data-tax-more="">
      <ButtonSummary variant="secondary" className="list-none [&::-webkit-details-marker]:hidden">
        {t("rating.taxDetail.more.label")} <span aria-hidden="true">▾</span>
      </ButtonSummary>
      <div className="absolute right-0 top-[calc(100%+var(--space-1))] z-40 flex min-w-48 flex-col border border-divider bg-surface py-1 shadow-md">
        <RowMenuAction
          label={t("rating.definition.action.duplicate")}
          icon={null}
          reason={props.readOnly ? t("rating.readOnlyReason") : null}
          testId="tax-more-duplicate"
          onClick={() => {
            close();
            props.onDuplicate();
          }}
        />
        <RowMenuAction
          label={t("rating.definition.action.retire")}
          icon={null}
          reason={retireReason}
          danger
          testId="tax-more-retire"
          onClick={() => {
            close();
            props.onRetire();
          }}
        />
      </div>
    </details>
  );
}
