// ── Trace ──────────────────────────────────────────────
// Change:   Lane E wave 1 — SPLIT OUT OF `NewConnectWizard.tsx`, unchanged.
//           The three rendering helpers that more than one step file needs.
//           They were file-private in the monolith, which is why each is
//           `export`ed here and nowhere else in the move.
//           Lane TEXT — 2026-09-28 — adds `EmptyValue`, the em dash a
//           cell draws when a value is missing: `AbsentValue` with the
//           reason taken out, because B14 rule 33 gives rationale zero
//           words on screen (PO reported bug 1).
// Rules:    B14 rule 21 (Tailwind utilities, no stylesheet class — this file is
//           listed in `src/styles/route-b-migrated.txt`, where `G31` skips it
//           and `routeBUtilities.test.ts` asks the stricter question) · B14
//           rule 32 (a screen's description budget — `StepIntro`'s sentence is
//           OPTIONAL and the docstring below says why) · B14 rule 33
//           (RATIONALE is zero words on screen)
// Tests:    NewConnectWizard.test.tsx, through the step files that render them.
// ───────────────────────────────────────────────────────
//
// ⚠ **THESE ARE NOT A SECOND COMPONENT KIT** (`G104`, `DEF-CWP-3655`). Each one
// composes the shared kit — `StepIntro` is a heading plus `Note`, `ServiceTicks`
// is a row of `CheckboxField`, `ManifestRow` is a `<tr>` — and none of them
// re-declares a name the shared kit already exports. They live here rather than
// in `components/` because all three are shaped by THIS wizard's drawing and
// nothing else in the product renders them.
import { CheckboxField } from "@/components/FormModal";
import { RefusalStrip } from "@/components/Surfaces";
import { Note } from "@/components/TextBits";

import type { Translator } from "./newConnectShared";

// ══════════════════════════════════════════════════════════════════════════
// SMALL SHARED BITS
// ══════════════════════════════════════════════════════════════════════════

/** A ticked/unticked set of service codes. Used twice at step 4 — once for the
 *  street, once for the units — and the second list is CONSTRAINED to the
 *  first, which is the whole rule of that step. */
export function ServiceTicks(props: {
  id: string;
  offer: readonly string[];
  chosen: readonly string[];
  onChange: (next: string[]) => void;
  t: Translator;
}) {
  return (
    <div className="flex flex-wrap gap-3" data-service-ticks={props.id}>
      {props.offer.map((code) => (
        <CheckboxField
          key={code}
          id={`${props.id}_${code}`}
          label={props.t(`rating.service.${code}`, { defaultValue: code })}
          checked={props.chosen.includes(code)}
          onChange={(on) =>
            props.onChange(
              on
                ? [...props.chosen, code]
                : props.chosen.filter((existing) => existing !== code),
            )
          }
        />
      ))}
    </div>
  );
}

/** A step's headline sentence — the drawn copy that explains what the step is
 *  for. Capped at B14 rule 18's measure (80%, the `--desc-measure` token). */
/** A step's heading, and OPTIONALLY the one sentence B14 rule 32 budgets it.
 *
 *  ⚠ **THE SENTENCE IS OPTIONAL BECAUSE MOST OF THEM WERE RATIONALE**, which
 *  rule 33 gives **zero words on screen** — *why* the product works this way
 *  belongs in a docstring, and cutting such a sentence to six words keeps the
 *  breach and merely makes it terser. The blueprint draws no help text inside
 *  the step-1 form at all; the grey prose beside it is the DOCUMENT talking to
 *  a reader, not the screen talking to a clerk. */
export function StepIntro(props: { title: string; children?: React.ReactNode }) {
  return (
    <div className="mb-4">
      <h3 className="font-heading text-h5 m-0 mb-1">{props.title}</h3>
      {props.children !== undefined && <Note className="max-w-measure">{props.children}</Note>}
    </div>
  );
}

/**
 * **THE SERVER'S REFUSAL, ON THE STEP THE CLERK CHOSE THE THING**
 * (`DEF-MET-6110`/`DEF-MET-6111`, PO ruling 2026-09-21: *"you ahve to show the
 * error at step you mentioned"*).
 *
 * ⚠ **IT IS A COMPONENT AND NOT A STRIP INLINED INTO TWO STEPS** — B14 rule 43,
 * ratified after *"use it"* turned out to mean 120 lines inside one page. Two
 * steps render this today and the next rule to be routed will be a third.
 *
 * ⚠ **`null` RENDERS NOTHING**, so a step mounts it unconditionally and there
 * is no second place where a step decides whether a refusal exists.
 */
export function StepRefusal(props: { message: string | null; step: string }) {
  if (props.message === null) {
    return null;
  }
  return (
    <RefusalStrip role="alert" data-step-refusal={props.step}>
      {props.message}
    </RefusalStrip>
  );
}

/**
 * **AN EMPTY VALUE — THE DASH, AND NOTHING ELSE (PO 2026-09-28, reported bug
 * 1: *"To Much text on every step reduce it"*).**
 *
 * ⚠ **IT IS `AbsentValue` WITH THE SENTENCE TAKEN OUT, AND THAT IS THE WHOLE
 * CHANGE.** `AbsentValue` draws the same dash and then a `Note` saying WHY the
 * value is missing — *"Not answered yet."*, *"No parcel given."*, *"No route
 * chosen."*, *"Not captured on this build."* — and B14 rule 33 gives rationale
 * **zero words on screen**. The redesign drawings list all four under *Removed
 * from this step* with the instruction *"(empty shows —)"*, which is exactly
 * this. `AbsentValue` is NOT deleted: the transfer wizard and the work module
 * still render it, and step 8's *"None on this build."* is a FACT about the
 * build rather than a reason, so it keeps its words.
 *
 * ⚠ **IT IS A COMPONENT RATHER THAN A DASH TYPED INTO SIX CELLS** (B14 rule
 * 43), and it keeps `data-absent` so the tests that read those cells still
 * have something to read. `tracks` is kept for the same reason `AbsentValue`
 * has it — the id of the row that would fill the value — and is invisible to
 * the reader (`DEF-332`).
 *
 * ⚠ **`aria-hidden` MATCHES THE HOUSE PATTERN**: the units step's occupancy
 * cell and the manifest's sub-meter row already draw a bare
 * `<span aria-hidden="true">—</span>`, because an em dash announced aloud is
 * noise where an empty cell is the fact.
 */
export function EmptyValue(props: { tracks?: string }) {
  return (
    <span data-absent="" data-tracks={props.tracks} aria-hidden="true">
      —
    </span>
  );
}

export function ManifestRow(props: { label: string; value: number }) {
  return (
    <tr>
      <td>{props.label}</td>
      <td className="tabular-nums">{props.value}</td>
    </tr>
  );
}
