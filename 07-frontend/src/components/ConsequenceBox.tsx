// ── Trace ──────────────────────────────────────────────
// Story:    US-WRK-016 (EP-WRK-03) — the eight-step template builder draws
//           this box on steps 3, 5 and 8 (`wireframes/Work-015.png`,
//           `Work-016.png`, `Work-017.png`); it is drawn on THIRTEEN Work
//           screens (`09-component-inventory.md` row `ConsequenceBox`).
// Rules:    B14 rule 11 (a consequence preview before a commit that writes
//           money, service state or a legal notice) · B14 rule 36 (the
//           captured packs give layout, r10 gives the visual style, and the
//           SHARED COMPONENT KIT is how you comply — PO 2026-09-04) ·
//           B14 rule 32 (one sentence per section; no rule id in the copy)
// Tests:    src/components/ConsequenceBox.test.tsx
// Impacts:  src/features/tenancy/RoutesCyclesWizards.tsx (the original two
//           tones, which now re-export from here) ·
//           src/features/work/TemplateBuilder.tsx
// ───────────────────────────────────────────────────────
//
// ⚠ **THIS COMPONENT EXISTED AND IT WAS NOT IN THE KIT.** It was declared in
// `features/tenancy/RoutesCyclesWizards.tsx` — a screen file — and read by that
// screen's four call sites and nothing else, while `09-component-inventory.md`
// lists it against thirteen Work screens and the portal carries a THIRD shape
// of the same idea in `portal/components/primitives.tsx`. Two answers to one
// question is how a figure drifts (decision log, 2026-09-05); a third is how a
// product stops looking like one product.
//
// So it moves here, unchanged in every pixel, and `RoutesCyclesWizards.tsx`
// re-exports it so its own call sites and tests keep working. **Nothing about
// the routes-and-cycles wizards renders differently** — that is the same
// promise CR-018 §6 made for every migration, and it is why this is a move and
// not a redesign.
//
// ⚠ **THE PORTAL'S `ConsequenceBox` IS FOLDED IN HERE TOO, AND THE FIRST DRAFT
// OF THIS FILE SAID IT WOULD NOT BE.** That draft argued that a heading with
// bullets and a tone with one sentence are two shapes, and that folding two
// shapes under one name is what `DEF-CWP-3655` cost. **`G86` clause (c)
// corrected it, and correctly:** the moment this name existed in the kit, the
// portal's own export became the collision that clause is about — *"two
// components called X in two directories are two visual decisions wearing one
// name, and the second author cannot see the first because an import names a
// PATH."* Its baseline may only SHRINK, so recording the collision was never
// available and folding was the only honest road.
//
// **What is settled is the NAME and the FILE; the two LOOKS are both kept.**
//
// ⚠ **THE TONE CLASS IS A WHOLE STRING PER TONE, NOT AN INTERPOLATION.**
// Tailwind's scanner cannot see `border-${tone}`; `routeBUtilities.test.ts`
// refuses an interpolated class in a migrated file by name, and a class the
// compiler never emitted renders as NOTHING while every `toContain` assertion
// still passes (CLAUDE.md, B14 rule 21's per-file clause).
import type { ReactNode } from "react";

/** What kind of consequence this is.
 *
 *  `move` — something will be RELOCATED or re-pointed (a premises changes
 *  route, a cycle changes an account's bill date).
 *  `check` — something wants a person's eye before it is committed.
 *  `publish` — this act reaches work that is already out in the world, or
 *  deliberately does not. `Work-017`'s box is the second kind: *"Publishing
 *  affects new work orders only."*
 */
export type ConsequenceTone = "move" | "check" | "publish";

const BASE =
  "flex max-w-[640px] items-start gap-2.5 border border-divider px-3 py-2.5 text-base";

const CONSEQUENCE_TONE: Record<ConsequenceTone, string> = {
  move: `${BASE} bg-[color-mix(in_srgb,var(--color-accent)_6%,transparent)]`,
  check: `${BASE} bg-[color-mix(in_srgb,var(--color-warning-700)_8%,transparent)]`,
  publish: `${BASE} bg-[color-mix(in_srgb,var(--color-warning-700)_8%,transparent)]`,
};

/** The word in the little outlined box at the left. It is a LABEL for the kind
 *  of consequence, so it is the caller's catalogue string — never a token this
 *  file spells in English (`G15`). The two original tones defaulted to their
 *  own words and keep them. */
const DEFAULT_TAG: Record<ConsequenceTone, string> = {
  move: "MOVE",
  check: "CHECK",
  publish: "EFFECT",
};

export interface StaffConsequenceProps {
  tone: ConsequenceTone;
  title: string;
  /** One sentence. B14 rule 32 gives a section ONE, and the drawings obey it:
   *  *"45 minutes total is what the dispatcher sees when scheduling."* A
   *  `ReactNode` so a consequence can bold the word that carries it, which is
   *  what `Work-017` draws — *"Publishing affects **new** work orders only."* */
  body: ReactNode;
  /** Overrides the tag word. Pass a catalogue string; omit for the default. */
  tag?: string;
  /** The hook a test or a walkthrough finds this box by. */
  "data-consequence"?: string;
}

/**
 * The CUSTOMER-FACING shape: a heading and the bullets that say what will
 * happen, behind a left brand rule.
 *
 * ⚠ **THE TWO LOOKS ARE KEPT AND NOT MERGED, ON PURPOSE.** Folding them into
 * one appearance would move pixels on seventeen customer-portal screens the
 * Product Owner has been looking at today, and that is a design decision rather
 * than a refactor. What is settled here is the NAME and the FILE; which look a
 * page gets is decided by which props it passes.
 */
export interface CustomerConsequenceProps {
  heading: string;
  bullets: ReactNode[];
}

export type ConsequenceBoxProps = StaffConsequenceProps | CustomerConsequenceProps;

function isCustomerShape(props: ConsequenceBoxProps): props is CustomerConsequenceProps {
  return "bullets" in props;
}

export function ConsequenceBox(props: ConsequenceBoxProps) {
  if (isCustomerShape(props)) {
    // Byte-for-byte what `portal/components/primitives.tsx` rendered before the
    // fold, `data-consequence` hook included, so no portal screen moves.
    return (
      <div
        className="border border-neutral-200 border-l-4 border-l-accent bg-[white] p-4"
        data-consequence=""
      >
        <p className="mb-2 text-xs font-bold uppercase tracking-wide text-neutral-900">
          {props.heading}
        </p>
        <ul className="list-disc pl-5 text-body leading-relaxed text-neutral-800">
          {props.bullets.map((bullet, index) => (
            <li key={index} data-bullet={index}>
              {bullet}
            </li>
          ))}
        </ul>
      </div>
    );
  }
  return (
    <div
      className={CONSEQUENCE_TONE[props.tone]}
      role="note"
      data-consequence={props["data-consequence"] ?? props.tone}
      data-rcw={`consequence-${props.tone}`}
    >
      <span className="border border-current px-1.5 py-0.5 text-xs font-bold tracking-tag">
        {props.tag ?? DEFAULT_TAG[props.tone]}
      </span>
      <div>
        <b>{props.title}</b>
        <p className="m-0 max-w-measure text-sm text-[color-mix(in_srgb,var(--color-text)_65%,transparent)]">
          {props.body}
        </p>
      </div>
    </div>
  );
}

// ── Lifecycle ─────────────────────────────────────────────
// packet: US-WRK-016@2b08ba9f (EP-WRK-03) · 10-execution-plan.md wave E task E1 · 09-component-inventory.md `ConsequenceBox` · 14-ui-conventions.md rules 11, 21, 36
// generated: 2026-09-05 by the CR-070 wave E build lane
// checklist: A✔ B✔ C✔ D=n/a(no endpoint) E✔(TemplateBuilder and RoutesCyclesWizards both render it) F✔ G✔ H=n/a
// gates: tsc · vitest src/components/ConsequenceBox.test.tsx · G31 (this file is on src/styles/route-b-migrated.txt) · G86 (house-style controls)
// exceptions: E3 the portal's own `ConsequenceBox` (heading + bullets) is NOT folded in — a different shape under one name is what DEF-CWP-3655 cost; reported rather than merged
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
