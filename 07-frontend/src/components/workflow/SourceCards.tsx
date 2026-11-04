// ── Trace ──────────────────────────────────────────────
// Change:   CR-023 — Stage 1 EXTRACT, the four source choices (design B15 §4.1)
// Rules:    B14 rule 21 (Tailwind) · B14 rule 9 (a choice is a control, never a
//           wall of undecorated boxes) · CR-016 (no internal reference reaches
//           a utility user's screen — the reason a card refuses is PLAIN
//           ENGLISH here and an open-question id in this comment)
// Impacts:  components/workflow/WorkflowRunner.tsx composes this.
// ───────────────────────────────────────────────────────
import { useTranslation } from "react-i18next";

import type { SourceChoice } from "./contract";
import * as WF from "./workflowKit";

/**
 * `File · SFTP · API · Manual` — one selectable, and **the three we do not
 * support yet stated honestly rather than drawn live**.
 *
 * ⚠ THIS IS THE STATED-ABSENCE DISCIPLINE APPLIED TO A CHOICE. B15 §4.1 marks
 * three of r10's four cards out of scope and §8 Q2 asks whether they are in
 * scope at all — an open question routed to the PO on this lane. Three
 * behaviours were available and two of them are wrong: DELETING the cards makes
 * the screen quietly disagree with the design a utility was shown, and WIRING
 * them answers an open question by building it. Drawing them with a sentence is
 * the third, and it is the one this repo has ruled for elsewhere.
 *
 * ⚠ AN UNAVAILABLE CARD IS A DISABLED RADIO, NOT A `<div>` THAT IGNORES CLICKS.
 * The keyboard has to skip it and a screen reader has to say it is unavailable;
 * a styled box that silently swallows a press says neither.
 */
export interface SourceCardsProps {
  /** Accessible name for the group — the stage's own question. */
  legend: string;
  choices: readonly SourceChoice[];
  selectedId: string;
  /** Radio-group name; unique per runner instance. */
  groupName: string;
  onSelect: (id: string) => void;
}

export function SourceCards({
  legend,
  choices,
  selectedId,
  groupName,
  onSelect,
}: SourceCardsProps) {
  const { t } = useTranslation();
  return (
    <div
      className={WF.SOURCE_GRID}
      data-workflow="source-cards"
      role="radiogroup"
      aria-label={legend}
    >
      {choices.map((choice) => {
        const selected = choice.available && choice.id === selectedId;
        const classes = [
          WF.SOURCE_CARD,
          selected ? WF.SOURCE_CARD_SELECTED : "",
          choice.available ? "" : WF.SOURCE_CARD_OFF,
        ]
          .filter((c) => c !== "")
          .join(" ");
        return (
          <label
            key={choice.id}
            className={classes}
            data-workflow-source={choice.id}
            data-available={choice.available ? "true" : "false"}
            data-state={selected ? "selected" : "unselected"}
          >
            <input
              className={WF.SOURCE_INPUT}
              type="radio"
              name={groupName}
              value={choice.id}
              checked={selected}
              disabled={!choice.available}
              onChange={() => onSelect(choice.id)}
            />
            <span className={WF.SOURCE_TITLE}>{t(choice.title_key)}</span>
            <span className={WF.SOURCE_SUB}>{t(choice.sub_key)}</span>
            {!choice.available && (
              <span className={WF.SOURCE_OFF_REASON}>{t(choice.unavailable_reason_key)}</span>
            )}
          </label>
        );
      })}
    </div>
  );
}
