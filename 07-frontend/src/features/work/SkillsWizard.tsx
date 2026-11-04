// ── Trace ──────────────────────────────────────────────
// Story:    US-WRK-021 (the three-step skills wizard, reached from *Assign
//           skills*).  Screen: an UNDRAWN SUB-SCREEN of Work-024 — it takes no
//           screen id (`01-overview.md` §6: *"Seven undrawn r10 surfaces take
//           no id and are sub-screens … the skills wizard under Work-024"*)
// Rules:    BR-WRK-028 (Work assigns what a person can do; the account itself
//           is Settings → Team's) · B14 rule 3 (the wizard's numbered rail) ·
//           rule 21 (Tailwind; on route-b-migrated.txt) · rule 31 (no database
//           id is a visible value) · rule 32 (one sentence per section) ·
//           rule 36 (compose the kit — this is `WizardFrame`, not a new one) ·
//           BR-SHL-019 (ONE transactional call at the commit)
// Tests:    src/features/work/SkillsWizard.test.tsx
// Impacts:  src/features/work/TechnicianDetailPage.tsx (opens it)
// ───────────────────────────────────────────────────────
//
// THREE STEPS, AND THE FIRST ONE IS ALREADY ANSWERED.
//
// `WS-24`'s card names them *Select technician · Skills & certifications ·
// Confirm & update*. This wizard is reached from ONE technician's own screen,
// so step 1 is a confirmation of who rather than a picker — the person is
// named and the step says so. Building a picker here would let a supervisor
// open R. Patel and edit M. Chen, which is the kind of quiet wrong-row edit
// that is very hard to notice afterwards.
//
// ⚠ **THE COMMIT IS ONE CALL AND IT REPLACES THE WHOLE SET** (`BR-SHL-019`).
// Step 2 shows every skill the utility has, ticked or not, so a supervisor who
// unticks Water II MEANS it — and a merge would silently keep it. The server's
// `PUT …/skills` is a replace for the same reason, so the two halves agree.
//
// ⚠ **AND *Not held* IS NEVER SENT.** It is the ABSENCE of a row, not a third
// proficiency; the server refuses it BY NAME rather than storing it, so a
// future caller cannot invent a third state from either end.
import { useMemo, useState } from "react";
import { useTranslation } from "react-i18next";

import type { ApiClient } from "@/api/client";
import { Button } from "@/components/Button";
import { WizardFrame, initialWizardNav } from "@/components/WizardFrame";
import type { WizardCommitOutcome, WizardNavState, WizardStep } from "@/components/WizardFrame";
import { Note } from "@/components/TextBits";

import { setTechnicianSkills } from "./workEndpoints";
import { PROFICIENCY_FALLBACK } from "./workforceLabels";
import type { TechnicianDetail } from "./workEndpoints";

type Proficiency = "trained" | "certified";

/** What step 2 holds: skill id → the proficiency ticked, or absent for none. */
export type SkillChoice = Record<string, Proficiency>;

/** The wizard's opening state — exactly what the person holds today.
 *
 * Exported and pure so a test can assert the round trip without a DOM: open
 * the wizard on R. Patel, change nothing, confirm, and the set that goes to
 * the server must be the set that came from it. */
export function initialChoice(detail: TechnicianDetail): SkillChoice {
  const out: SkillChoice = {};
  for (const skill of detail.skills) {
    if (skill.proficiency === "trained" || skill.proficiency === "certified") {
      out[skill.skill_id] = skill.proficiency;
    }
  }
  return out;
}

/** The body of `PUT …/skills` — the ticked rows only, in the screen's order. */
export function skillsPayload(
  detail: TechnicianDetail,
  choice: SkillChoice,
): { skill_id: string; proficiency: Proficiency }[] {
  return detail.skills
    .filter((skill) => choice[skill.skill_id] !== undefined)
    .map((skill) => ({ skill_id: skill.skill_id, proficiency: choice[skill.skill_id] }));
}

export interface SkillsWizardProps {
  detail: TechnicianDetail;
  client: ApiClient;
  onClose: () => void;
  onSaved: () => void;
}

export function SkillsWizard(props: SkillsWizardProps) {
  const { t } = useTranslation();
  const { detail } = props;
  const [choice, setChoice] = useState<SkillChoice>(() => initialChoice(detail));
  const [nav, setNav] = useState<WizardNavState>(initialWizardNav);

  const held = useMemo(
    () => detail.skills.filter((skill) => choice[skill.skill_id] !== undefined),
    [detail.skills, choice],
  );

  const steps: WizardStep[] = [
    {
      id: "who",
      label: t("work.skillsWizard.step.who", { defaultValue: "Who" }),
      content: (
        <div data-skills-step="who">
          <p className="m-0">
            {t("work.skillsWizard.who.body", {
              name: detail.name,
              defaultValue: "Assigning skills to {{name}}.",
            })}
          </p>
          {/* B14 rule 32 — ONE sentence per section, and no rule id in it.
              This one earns its place: it is the boundary between what Work
              owns and what Settings owns, and a supervisor looking for how to
              ADD a person needs to be told where that is. */}
          <Note>
            {t("work.skillsWizard.who.note", {
              defaultValue: "Technicians are invited in Settings → Team.",
            })}
          </Note>
        </div>
      ),
    },
    {
      id: "skills",
      label: t("work.skillsWizard.step.skills", { defaultValue: "Skills" }),
      content: (
        <div data-skills-step="skills">
          {detail.skills.map((skill) => {
            const current = choice[skill.skill_id];
            return (
              <p key={skill.skill_id} className="m-0 mb-2" data-skill-choice={skill.skill_id}>
                <label className="inline-flex items-center gap-2">
                  <input
                    type="checkbox"
                    checked={current !== undefined}
                    onChange={(event) =>
                      setChoice((prev) => {
                        const next = { ...prev };
                        if (event.target.checked) next[skill.skill_id] = "trained";
                        else delete next[skill.skill_id];
                        return next;
                      })
                    }
                  />
                  <span>{skill.name}</span>
                </label>
                {current !== undefined && (
                  <select
                    className="ml-2"
                    aria-label={t("work.skillsWizard.proficiencyFor", {
                      skill: skill.name,
                      defaultValue: "Proficiency for {{skill}}",
                    })}
                    value={current}
                    onChange={(event) =>
                      setChoice((prev) => ({
                        ...prev,
                        [skill.skill_id]: event.target.value as Proficiency,
                      }))
                    }
                  >
                    <option value="trained">
                      {t("work.technician.proficiency.trained", { defaultValue: "Trained" })}
                    </option>
                    <option value="certified">
                      {t("work.technician.proficiency.certified", { defaultValue: "Certified" })}
                    </option>
                  </select>
                )}
              </p>
            );
          })}
          {/* ⚠ CERTIFICATIONS ARE NOT EDITED HERE, AND THE CARD'S OWN TITLE FOR
              THIS STEP SAYS *Skills & certifications*. A certification carries
              an EXPIRY DATE and a certification type from Settings, and the
              date is the whole reason the watch exists — a date field tucked
              into a tick list is where a wrong year gets typed. The
              certifications endpoint is built (`PUT …/certifications`) and the
              screen that drives it is owed; it is written down rather than
              half-built here. */}
        </div>
      ),
    },
    {
      id: "confirm",
      label: t("work.skillsWizard.step.confirm", { defaultValue: "Confirm" }),
      content: (
        <div data-skills-step="confirm">
          <p className="m-0">
            {held.length === 0
              ? t("work.skillsWizard.confirm.none", {
                  name: detail.name,
                  defaultValue: "{{name}} will hold no skills.",
                })
              : t("work.skillsWizard.confirm.body", {
                  name: detail.name,
                  count: held.length,
                  defaultValue: "{{name}} will hold {{count}} skills.",
                })}
          </p>
          <ul className="m-0" data-skills-confirm="">
            {held.map((skill) => (
              <li key={skill.skill_id}>
                {skill.name} ·{" "}
                {t(`work.technician.proficiency.${choice[skill.skill_id]}`, {
                  defaultValue: PROFICIENCY_FALLBACK[choice[skill.skill_id]],
                })}
              </li>
            ))}
          </ul>
          {/* What pressing the commit DOES, in the words a person reads. */}
          <Note>
            {t("work.skillsWizard.confirm.effect", {
              defaultValue:
                "Dispatch will offer them jobs that need these skills, and stop offering the ones removed.",
            })}
          </Note>
        </div>
      ),
    },
  ];

  return (
    <div data-skills-wizard="">
      <WizardFrame
        steps={steps}
        nav={nav}
        onNavChange={setNav}
        commitLabel={t("work.skillsWizard.commit", { defaultValue: "Update skills ✓" })}
        commitFailedTitle={t("work.skillsWizard.failed", {
          defaultValue: "The skills were not saved.",
        })}
        onCommit={async (): Promise<WizardCommitOutcome> => {
          try {
            await setTechnicianSkills(detail.slug, skillsPayload(detail, choice), props.client);
            return { ok: true };
          } catch (error) {
            // BR-SHL-020 — PLAIN LANGUAGE reaches the frame, never an envelope.
            return {
              ok: false,
              reason:
                error instanceof Error && error.message !== ""
                  ? error.message
                  : t("work.skillsWizard.failedReason", {
                      defaultValue: "The server refused the change.",
                    }),
            };
          }
        }}
        onCommitted={props.onSaved}
        // ⚠ NO `exit` PROP, DELIBERATELY. `WizardExit` is *Save & exit* plus
        // PARK — a half-filled application left for somebody to come back to,
        // which is B19 §12.2's shape for the sign-up and import flows. There is
        // nothing to park here: the wizard holds three ticks over data the
        // screen behind it already shows, and a *Parked* entry that resumed
        // into a modal would be a promise this flow cannot keep. Leaving is
        // Cancel, below.
      />
      <Button variant="secondary" data-skills-cancel="" onClick={props.onClose}>
        {t("work.skillsWizard.cancel", { defaultValue: "Cancel" })}
      </Button>
    </div>
  );
}

export default SkillsWizard;

// ── Lifecycle ─────────────────────────────────────────────
// packet: US-WRK-021@2b08ba9f (EP-WRK-04) · 09-component-inventory.md WRK-14 (the skills wizard) · 01-overview.md §6 (a sub-screen takes no id)
// generated: 2026-09-05 by the CR-070 wave F build lane
// checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=n/a
// gates: tsc · eslint · vitest · routeBUtilities.test.ts · G31 (rule 21)
// exceptions: step 1 CONFIRMS the technician rather than picking one — the wizard is reached from that person's own screen, and a picker there would let a supervisor open R. Patel and edit M. Chen · certifications are NOT edited here although the card's step title names them: an expiry date belongs on a form of its own, and the endpoint exists for the screen that is owed
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
