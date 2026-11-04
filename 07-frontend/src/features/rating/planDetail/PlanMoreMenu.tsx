// ── Trace ──────────────────────────────────────────────
// Change:   CR-167-BRC10 round 3 task 7 — the header's More ▾ (image 25):
//           Duplicate · Retire, and *Delete draft* on a draft (the field-map
//           judgment, CR-167 §5.5 L13 — it moved here off the header button the
//           list lane left as a stopgap).
// Defects:  DEF-RAT-9352 (Duplicate held until the copy act; released by lane
//           PLAN-FIXES) · DEF-RAT-9334
// Rules:    BR-SHL-025 (a control that cannot act is disabled WITH its reason) ·
//           B14 rule 6 (danger tier on a destructive act) · BR-RAT-030 (a plan
//           ever billed is never deleted — the server refuses) · hard-won law 2
// ───────────────────────────────────────────────────────
import { useRef } from "react";

import { ButtonSummary } from "@/components/Button";
import { RowMenuAction } from "@/components/RowActions";

import type { Translator } from "./planDetailModel";

/**
 * *Duplicate* opens the copy dialog (`DEF-RAT-9352` — the hold is released:
 * `POST /plans/{id}/duplicate` copies the version in force into a new draft).
 * *Retire* is offered on a published plan; *Delete draft* only on a draft.
 */
export function PlanMoreMenu(props: {
  status: string;
  readOnly: boolean;
  onDeleteDraft: () => void;
  onDuplicate: () => void;
  onRetire: () => void;
  t: Translator;
}) {
  const { t } = props;
  const menu = useRef<HTMLDetailsElement | null>(null);
  const close = () => {
    if (menu.current !== null) menu.current.open = false;
  };
  const readOnlyReason = props.readOnly ? t("rating.readOnlyReason") : null;
  const draft = props.status === "draft";
  const retireReason = readOnlyReason ?? (props.status === "published" ? null : t("rating.taxDetail.more.retireNotLive"));
  return (
    <details ref={menu} className="relative inline-flex" data-plan-more="">
      <ButtonSummary variant="secondary" className="list-none [&::-webkit-details-marker]:hidden">
        {t("rating.taxDetail.more.label")} <span aria-hidden="true">▾</span>
      </ButtonSummary>
      <div className="absolute right-0 top-[calc(100%+var(--space-1))] z-40 flex min-w-48 flex-col border border-divider bg-surface py-1 shadow-md">
        <RowMenuAction
          label={t("rating.planDetail.action.duplicate")}
          icon={null}
          reason={readOnlyReason}
          testId="plan-more-duplicate"
          onClick={() => {
            close();
            props.onDuplicate();
          }}
        />
        {draft && (
          <RowMenuAction
            label={t("rating.planDetail.action.deleteDraft")}
            icon={null}
            reason={readOnlyReason}
            danger
            testId="plan-more-delete-draft"
            onClick={() => {
              close();
              props.onDeleteDraft();
            }}
          />
        )}
        {!draft && (
          <RowMenuAction
            label={t("rating.planDetail.action.retire")}
            icon={null}
            reason={retireReason}
            danger
            testId="plan-more-retire"
            onClick={() => {
              close();
              props.onRetire();
            }}
          />
        )}
      </div>
    </details>
  );
}
