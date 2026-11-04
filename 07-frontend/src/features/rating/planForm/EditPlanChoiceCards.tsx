// ── Trace ──────────────────────────────────────────────
// Change:   CR-167-BRC10 round 3 task 8 — *What to change*, the card row on top
//           of the plan edit form (images 38, 40, 43 of
//           `05-prototype/plans-2026-10-03/images/`, B14 rule 42).
// Defects:  DEF-RAT-9332 (Edit half — the edit intent was a radio on step 1 of
//           an eight-step wizard; now three named choices, each its own flow)
// ───────────────────────────────────────────────────────
//
// THREE CARDS, ONE CHOSEN, AS A RADIO GROUP — the tax and discount edit forms'
// device, copied. Each card is a native radio inside its label, so the arrow
// keys move between them and a screen reader hears *"Name and details, radio,
// 1 of 3, checked"*. The chosen card carries the accent rule along its top
// edge and an accent border, as drawn.
//
// A DRAFT HAS NO CARDS: it has no version in force, so it edits in place
// (`PATCH`, every field) and the page does not mount this component at all.
import { Panel } from "@/components/Panel";

import { PLAN_EDIT_MODES } from "./planEditModel";
import type { PlanEditMode } from "./planEditModel";
import { SECTION_HEADING } from "./planFormShared";
import type { Translator } from "./planFormShared";

/** Literal keys, so G18 sees each one used. */
const CARD_KEYS: Record<PlanEditMode, { title: string; sub: string }> = {
  info: { title: "rating.planEdit.card.info", sub: "rating.planEdit.card.infoSub" },
  change: { title: "rating.planEdit.card.change", sub: "rating.planEdit.card.changeSub" },
  correct: { title: "rating.planEdit.card.correct", sub: "rating.planEdit.card.correctSub" },
};

export function EditPlanChoiceCards(props: {
  mode: PlanEditMode;
  onChoose: (mode: PlanEditMode) => void;
  /** After a save the choice is history: the cards read, they do not switch. */
  disabled?: boolean;
  t: Translator;
}) {
  const { t } = props;
  return (
    <Panel as="section" aria-labelledby="plan-edit-choose">
      <h2 id="plan-edit-choose" className={SECTION_HEADING}>
        {t("rating.planEdit.choose")}
      </h2>
      <div role="radiogroup" aria-labelledby="plan-edit-choose" className="grid grid-cols-3 gap-2">
        {PLAN_EDIT_MODES.map((mode) => {
          const chosen = mode === props.mode;
          const off = props.disabled === true;
          return (
            <label
              key={mode}
              data-plan-edit-card={mode}
              data-chosen={chosen ? "" : undefined}
              className={
                "relative block border bg-surface px-3 py-3 has-[input:focus-visible]:outline-2 has-[input:focus-visible]:outline-offset-2 has-[input:focus-visible]:outline-accent " +
                (chosen ? "border-accent shadow-[inset_0_3px_0_var(--color-accent)]" : "border-divider") +
                (off ? " cursor-default" : " cursor-pointer") +
                (off && !chosen ? " opacity-60" : "")
              }
            >
              <input
                type="radio"
                name="plan-edit-change"
                value={mode}
                checked={chosen}
                disabled={off}
                onChange={() => props.onChoose(mode)}
                className="sr-only"
              />
              <span className="block font-heading text-md font-semibold text-text">{t(CARD_KEYS[mode].title)}</span>
              <span className="mt-1 block text-sm text-neutral-700">{t(CARD_KEYS[mode].sub)}</span>
            </label>
          );
        })}
      </div>
    </Panel>
  );
}
