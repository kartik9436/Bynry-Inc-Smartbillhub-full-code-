// ── Trace ──────────────────────────────────────────────
// Defects:  DEF-CUS-10250 (Portal apply asks Move-in's fields, in Move-in's
//           order, in the portal look — PO 2026-10-18, image 04-portal.png)
// Rules:    B14 rule 43 (a piece of UI is a COMPONENT — four sections of the
//           About-you step share this box) · rule 44 (the drawing says what
//           and where; the kit's tokens and spacing say how) · rule 21
//           (Tailwind utilities only) · 22-product-maintenance-process.md §6
//           (the portal's accessibility questions: a real label on every
//           control, a 44px target, reachable by keyboard)
// Tests:    src/portal/guest/AboutYouMoveInFields.dom.test.tsx
// ───────────────────────────────────────────────────────
import type { ReactNode } from "react";
import { useId } from "react";

import { SectionHeadingTag, SectionScope, useSectionHeading } from "@/components/HeadingLevel";

/**
 * One boxed section of a portal form — the drawing's *"I'm applying as"*,
 * *"Someone else on the account"*, *"Mailing address"* and *"Preferences"*.
 *
 * ⚠ **THE TICK IN THE HEADER OPENS AND CLOSES THE SECTION** — Move-in's rule
 * for every optional section (image `00-overview.png`: *"Optional sections …
 * open and close with the tick box in their header"*). The tick is a native
 * checkbox inside its own `<label>`, so it is one Tab stop, Space toggles it,
 * and the whole label — at least 44px tall — is the target.
 */
export function FormSection(props: {
  title?: string;
  /** The header tick: its words, whether it is ticked, and what a tick does. */
  tick?: { label: string; checked: boolean; onChange: (checked: boolean) => void; id: string };
  children?: ReactNode;
  testId?: string;
}) {
  const headingId = `section-${useId()}`;
  const hasHeader = props.title !== undefined || props.tick !== undefined;
  // `DEF-CWP-10563`: the level is the outline's (an h2 straight under a page
  // h1, an h3 inside a panel), never the look's — the size is `text-md` either
  // way. Outside an outline it stays the `<h3>` it always was.
  const heading = useSectionHeading(3);
  return (
    <section
      className="flex flex-col gap-3 border border-neutral-200 bg-[white] p-4"
      aria-labelledby={props.title !== undefined ? headingId : undefined}
      data-form-section={props.testId ?? ""}
    >
      {hasHeader ? (
        <div className="flex flex-wrap items-center justify-between gap-2">
          {props.title !== undefined ? (
            <SectionHeadingTag tag={heading.tag} id={headingId} className="m-0 text-md font-semibold text-neutral-900">
              {props.title}
            </SectionHeadingTag>
          ) : null}
          {props.tick !== undefined ? (
            <label
              htmlFor={props.tick.id}
              className="ml-auto flex min-h-11 cursor-pointer items-center gap-2 text-base font-semibold text-neutral-900"
            >
              <input
                id={props.tick.id}
                type="checkbox"
                className="size-4"
                checked={props.tick.checked}
                data-section-tick={props.tick.id}
                onChange={(event) => props.tick?.onChange(event.target.checked)}
              />
              {props.tick.label}
            </label>
          ) : null}
        </div>
      ) : null}
      <SectionScope inner={props.title !== undefined ? heading.inner : null}>{props.children}</SectionScope>
    </section>
  );
}

/** Three equal columns that fold to one on a phone — the drawing's
 *  Phone · Email · Date of birth row and the Preferences row. */
export function ThreeUp(props: { children: ReactNode }) {
  return <div className="grid grid-cols-3 gap-5 max-md:grid-cols-1">{props.children}</div>;
}
