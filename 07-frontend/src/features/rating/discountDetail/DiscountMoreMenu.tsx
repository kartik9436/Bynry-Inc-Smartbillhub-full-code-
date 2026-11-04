// ── Trace ──────────────────────────────────────────────
// Change:   CR-166-BRC10 round 3 task 6 — the header's More ▾ (image 23):
//           Duplicate · Delete draft · Retire (README point 6).
// Defect:   DEF-RAT-9291 D22 · DEF-RAT-9310 (Duplicate — LIVE since the
//           CR-166 follow-up, 2026-10-03)
// Rules:    BR-SHL-025 (a control that cannot act is disabled WITH its
//           reason) · B14 rule 6 (danger tier on a destructive act) ·
//           hard-won law 2 (a hold carries the test that fires when it expires)
// ───────────────────────────────────────────────────────
import { useRef } from "react";

import { ButtonSummary } from "@/components/Button";
import { RowMenuAction } from "@/components/RowActions";

import { retireOffered } from "./discountDetailModel";
import type { Translator } from "./discountDetailModel";

/**
 * *Duplicate* opens `DuplicateDiscountDialog` (`DEF-RAT-9310`): the server
 * copies the version in force into a new draft. Offered in every status — a
 * retired or ended discount is a fine thing to start a new one from.
 *
 * *Delete draft* is drawn only while a draft version exists — the act the old
 * Audit tab's *Discard draft* performed (`DEF-RAT-5817`), moved here because
 * the Audit tab is now the change history.
 */
export function DiscountMoreMenu(props: {
  status: string;
  readOnly: boolean;
  hasDraft: boolean;
  onDuplicate: () => void;
  onDeleteDraft: () => void;
  onRetire: () => void;
  t: Translator;
}) {
  const { t } = props;
  const menu = useRef<HTMLDetailsElement | null>(null);
  const close = () => {
    if (menu.current !== null) menu.current.open = false;
  };
  const readOnlyReason = props.readOnly ? t("rating.readOnlyReason") : null;
  const retireReason = readOnlyReason ?? (retireOffered(props.status) ? null : t("rating.taxDetail.more.retireNotLive"));
  return (
    <details ref={menu} className="relative inline-flex" data-discount-more="">
      <ButtonSummary variant="secondary" className="list-none [&::-webkit-details-marker]:hidden">
        {t("rating.taxDetail.more.label")} <span aria-hidden="true">▾</span>
      </ButtonSummary>
      <div className="absolute right-0 top-[calc(100%+var(--space-1))] z-40 flex min-w-48 flex-col border border-divider bg-surface py-1 shadow-md">
        <RowMenuAction
          label={t("rating.definition.action.duplicate")}
          icon={null}
          reason={readOnlyReason}
          testId="discount-more-duplicate"
          onClick={() => {
            close();
            props.onDuplicate();
          }}
        />
        {props.hasDraft && (
          <RowMenuAction
            label={t("rating.discountDetail.more.deleteDraft")}
            icon={null}
            reason={readOnlyReason}
            danger
            testId="discount-more-delete-draft"
            onClick={() => {
              close();
              props.onDeleteDraft();
            }}
          />
        )}
        <RowMenuAction
          label={t("rating.definition.action.retire")}
          icon={null}
          reason={retireReason}
          danger
          testId="discount-more-retire"
          onClick={() => {
            close();
            props.onRetire();
          }}
        />
      </div>
    </details>
  );
}
