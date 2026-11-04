// ── Trace ──────────────────────────────────────────────
// Change:   CR-167-BRC10 round 2 task 5 — the published and saved-as-draft
//           states, built from images 22 and 23 (B14 rule 42).
// ───────────────────────────────────────────────────────
//
// One instruction after the fact says where to go next: a published plan is
// assigned to units from its own page; a draft is published from there.
import { Button } from "@/components/Button";
import { formatDate } from "@/components/DateCell";
import { Panel } from "@/components/Panel";

import type { PlanFormLists, Translator } from "./planFormShared";

export function PlanSavedPanel(props: {
  name: string;
  published: boolean;
  /** The start date the plan was saved with, ISO. */
  startsOn: string | null;
  lists: PlanFormLists;
  onOpen: () => void;
  t: Translator;
}) {
  const { t } = props;
  const line = props.published
    ? props.startsOn === null
      ? t("rating.planForm.saved.liveNoDate")
      : t("rating.planForm.saved.live", { date: formatDate(props.startsOn, props.lists.timeZone, props.lists.dateFormat) })
    : t("rating.planForm.saved.draft");
  return (
    <Panel as="section" aria-labelledby="plan-saved-title" data-plan-saved={props.published ? "published" : "draft"}>
      <span
        aria-hidden="true"
        className="flex h-11 w-11 items-center justify-center bg-success-700 font-heading text-h4 text-bg"
      >
        ✓
      </span>
      <h2 id="plan-saved-title" className="m-0 mt-4 font-heading text-h4" role="status">
        {props.published
          ? t("rating.planForm.saved.publishedTitle", { name: props.name })
          : t("rating.planForm.saved.draftTitle", { name: props.name })}
      </h2>
      <p className="m-0 mt-3 text-md">{line}</p>
      <div className="mt-4 flex justify-end gap-2 border-t border-divider pt-4">
        <Button variant="primary" onClick={props.onOpen}>
          {t("rating.planForm.saved.open")}
        </Button>
      </div>
    </Panel>
  );
}
