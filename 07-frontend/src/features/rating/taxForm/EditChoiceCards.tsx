// ── Trace ──────────────────────────────────────────────
// Change:   CR-165-BRC10 task 7 — *What to change*, the card row on top of the
//           edit form (images 24–33 of `05-prototype/taxes-fees-2026-10-03/images/`,
//           B14 rule 42).
// Defects:  DEF-RAT-9273 P45 (one form for every kind of edit — now three
//           named choices, each its own flow)
// ───────────────────────────────────────────────────────
//
// THREE CARDS, ONE CHOSEN, AS A RADIO GROUP. Each card is a native radio inside
// its label, so the arrow keys move between them and a screen reader hears
// *"Name and filing, radio, 1 of 3, checked"* — a row of buttons styled as
// cards would announce three unrelated buttons. The chosen card carries the
// accent rule along its top edge and an accent border, as drawn.
import { Panel } from "@/components/Panel";

import { TAX_EDIT_MODES } from "./taxEditModel";
import type { TaxEditMode } from "./taxEditModel";
import { SECTION_HEADING } from "./taxFormShared";
import type { Translator } from "./taxFormShared";

/** Literal keys, so G18 sees each one used. */
const CARD_KEYS: Record<TaxEditMode, { title: string; sub: string }> = {
  info: { title: "rating.taxEdit.card.info", sub: "rating.taxEdit.card.infoSub" },
  change: { title: "rating.taxEdit.card.change", sub: "rating.taxEdit.card.changeSub" },
  correct: { title: "rating.taxEdit.card.correct", sub: "rating.taxEdit.card.correctSub" },
};

export function EditChoiceCards(props: {
  mode: TaxEditMode;
  onChoose: (mode: TaxEditMode) => void;
  /** After a save the choice is history: the cards read, they do not switch. */
  disabled?: boolean;
  t: Translator;
}) {
  const { t } = props;
  return (
    <Panel as="section" aria-labelledby="tax-edit-choose">
      <h2 id="tax-edit-choose" className={SECTION_HEADING}>
        {t("rating.taxEdit.choose")}
      </h2>
      <div role="radiogroup" aria-labelledby="tax-edit-choose" className="grid grid-cols-3 gap-2">
        {TAX_EDIT_MODES.map((mode) => {
          const chosen = mode === props.mode;
          return (
            <label
              key={mode}
              data-tax-edit-card={mode}
              data-chosen={chosen ? "" : undefined}
              className={
                "relative block cursor-pointer border bg-surface px-3 py-3 has-[input:focus-visible]:outline-2 has-[input:focus-visible]:outline-offset-2 has-[input:focus-visible]:outline-accent " +
                (chosen ? "border-accent shadow-[inset_0_3px_0_var(--color-accent)]" : "border-divider") +
                (props.disabled === true ? " cursor-default" : "")
              }
            >
              <input
                type="radio"
                name="tax-edit-change"
                value={mode}
                checked={chosen}
                disabled={props.disabled}
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
