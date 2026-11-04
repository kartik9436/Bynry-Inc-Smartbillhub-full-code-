// ── Trace ──────────────────────────────────────────────
// Change:   CR-166-BRC10 round 3 task 7 — *What to change*, the card row on top
//           of the discount edit form (images 27–36 of
//           `05-prototype/discounts-2026-10-03/images/`, B14 rule 42).
// Defects:  DEF-RAT-9292 D35 (*"Fix this version"* and *"Edit"* as two buttons
//           — now three named choices on ONE form, each its own flow)
// ───────────────────────────────────────────────────────
//
// THREE CARDS, ONE CHOSEN, AS A RADIO GROUP — the tax edit's device
// (`taxForm/EditChoiceCards.tsx`). Each card is a native radio inside its
// label, so the arrow keys move between them and a screen reader hears
// *"Name and details, radio, 1 of 3, checked"*. The chosen card carries the
// accent rule along its top edge and an accent border, as drawn.
//
// ⚠ **A DRAFT HAS ONLY ONE CHOICE.** *New value from a date* and *Fix a
// mistake* act on the version IN FORCE, and a draft has none — the server
// refuses both (`new_value_needs_live`, `correct_draft`). Those two cards are
// drawn disabled rather than offered and refused (hard-won law 2's mirror: a
// live control over a road that ends).
import { Panel } from "@/components/Panel";

import { DISCOUNT_EDIT_MODES } from "./discountEditModel";
import type { DiscountEditMode } from "./discountEditModel";
import { SECTION_HEADING } from "./discountFormShared";
import type { Translator } from "./discountFormShared";

/** Literal keys, so G18 sees each one used. */
const CARD_KEYS: Record<DiscountEditMode, { title: string; sub: string }> = {
  info: { title: "rating.discountEdit.card.info", sub: "rating.discountEdit.card.infoSub" },
  change: { title: "rating.discountEdit.card.change", sub: "rating.discountEdit.card.changeSub" },
  correct: { title: "rating.discountEdit.card.correct", sub: "rating.discountEdit.card.correctSub" },
};

export function EditDiscountChoiceCards(props: {
  mode: DiscountEditMode;
  onChoose: (mode: DiscountEditMode) => void;
  /** After a save the choice is history: the cards read, they do not switch. */
  disabled?: boolean;
  /** The choices a draft cannot take (it has no version in force). */
  unavailable?: ReadonlySet<DiscountEditMode>;
  t: Translator;
}) {
  const { t } = props;
  return (
    <Panel as="section" aria-labelledby="discount-edit-choose">
      <h2 id="discount-edit-choose" className={SECTION_HEADING}>
        {t("rating.discountEdit.choose")}
      </h2>
      <div role="radiogroup" aria-labelledby="discount-edit-choose" className="grid grid-cols-3 gap-2">
        {DISCOUNT_EDIT_MODES.map((mode) => {
          const chosen = mode === props.mode;
          const off = props.disabled === true || props.unavailable?.has(mode) === true;
          return (
            <label
              key={mode}
              data-discount-edit-card={mode}
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
                name="discount-edit-change"
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
