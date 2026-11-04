// ── Trace ──────────────────────────────────────────────
// Change:   CR-167-BRC10 follow-up (lane PLAN-FIXES) — a new version saved with
//           *Save new version* (Edit → Change from a date, images 41–42) is
//           published HERE, the details page being the plan's home.
// Defect:   DEF-RAT-9364 (nothing on screen published a draft version)
// Rules:    BR-RAT-1066 (publishing ends the version in force the day before)
//           · B14 rule 33 (facts ≤ 6 words) · BR-SHL-025 (a control that
//           cannot act is disabled with its reason)
// ───────────────────────────────────────────────────────
import type { PlanVersionWindow } from "@/api/planDetailEndpoints";

import { GuardedButton } from "../ratingShared";
import { dayShown } from "./planDetailModel";
import type { PlanRegional, Translator } from "./planDetailModel";

/**
 * Not drawn in images 24–44: the drawings stop at *v2 saved. Not published
 * yet.* (Edit's own saved panel). Our judgment (decision log *"CR-167
 * FOLLOW-UP · PUBLISHING A SAVED NEW VERSION …"*): the same info strip as
 * ruling 13's upcoming banner, above it, with the one act it needs.
 */
export function PlanDraftVersionBanner(props: {
  draft: PlanVersionWindow;
  readOnly: boolean;
  onPublish: () => void;
  regional: PlanRegional;
  t: Translator;
}) {
  const { draft, t } = props;
  return (
    <div
      role="status"
      className="flex flex-wrap items-center gap-x-3 gap-y-2 bg-info-100 px-3 py-2 text-sm text-info-700"
      data-testid="plan-draft-version"
    >
      <strong className="font-semibold">{t("rating.planDetail.draftVersion.head", { n: draft.version })}</strong>
      {draft.effective_from !== null && (
        <span>{t("rating.planDetail.draftVersion.starts", { date: dayShown(draft.effective_from, props.regional) })}</span>
      )}
      <GuardedButton
        readOnly={props.readOnly}
        readOnlyReason={t("rating.readOnlyReason")}
        variant="primary"
        size="sm"
        onClick={props.onPublish}
      >
        {t("rating.planDetail.draftVersion.publish", { n: draft.version })}
      </GuardedButton>
    </div>
  );
}
