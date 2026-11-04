// ── Trace ──────────────────────────────────────────────
// Story:    CR-085 step 2 lane 1 — the portal FRAME. Screens: all 50.
// Rules:    R-22 (PO 2026-09-11, verbatim: *"differntiate it using text
//           message"* — loading, empty and failed are told apart by their
//           SENTENCE, not by three pictures) · R-10 (PO 2026-09-11, verbatim:
//           *"when a screen tells a customer something bad, the thing they can
//           do about it must be on that same screen, next to the message. Not a
//           page away. Not in a menu. Right there."*) · B14 rule 2 (ONE page
//           header, every screen) · rule 21 (Tailwind utilities, no stylesheet
//           class) · rule 32 (one sentence) · rule 36 (compose the kit)
// Defects:  DEF-CWP-4926 — ten signed-in screens declare `if (failed) return …`
//           BEFORE their `PageHeader`, so a failed or loading read throws the
//           heading, the screen id and the only door out away with the data.
// Tests:    src/portal/components/states.dom.test.tsx
// ───────────────────────────────────────────────────────
import type { ReactNode } from "react";

import { Button, ButtonLink } from "@/components/Button";

/**
 * ══ THE TWO PIECES EVERY PORTAL SCREEN'S FRAME NEEDS ══════════════════════
 *
 * `PortalScreen` — the screen's OUTER shell: its id and its head, on **every**
 * branch including the ones that failed.
 * `PortalState`  — the ONE card that says loading, empty or failed, told apart
 * by its SENTENCE and able to carry the way out beside it.
 *
 * ⚠ **WHY THEY ARE ONE FILE AND NOT TWO.** They are the same defect seen from
 * two sides. On 2026-09-11 all fifty portal addresses were walked at 390 and at
 * 1280, and **13 of the 34 signed-in screens rendered no `<h1>` at all**. Three
 * of those thirteen are correct by design. The other **ten share one cause**:
 *
 *     if (failed) return <Card><p>{t("…couldNotRead")}</p></Card>;
 *     if (!rows)  return <Card><p>{t("…reading")}</p></Card>;
 *     return <div data-screen="CWP-0nn"><PageHeader … />…</div>;

 * ⚠ **`CWP-0nn` RATHER THAN A REAL ID IN THAT SKETCH IS NOT PEDANTRY.**
 * `pageHeadCensus.test.ts` finds portal screens by grepping raw source for
 * `data-screen="CWP-<digits>"`, comments included — so a real id in this
 * docstring makes THIS FILE look like a screen, and the census went red naming
 * it within a minute of the sketch being written. That is the census working,
 * and it is cheaper to keep the example unmatchable than to teach the grep
 * about comments.
 *
 * The head — and the `data-screen` mark, and whatever action row the drawing
 * puts beside the title — exists **only in the success branch**. So the moment
 * a read is slow or fails, the customer loses the page title, the product loses
 * the screen id every rendered check selects on, and the screen loses the one
 * row of controls that could have got the customer anywhere else. That is R-10
 * and R-22 failing together, from a single misplaced `return`.
 *
 * **Three signed-in screens already do it right and they are the model** —
 * `arrears/Overdue.tsx`, `Protections.tsx`, `MoneyBack.tsx` each build the head
 * ONCE into a `const` and render it on every branch. These two components make
 * that shape the cheap one to write.
 */

/* ═══════════════════════════════════════════════════════════════════════════
 * 1 · THE SCREEN SHELL
 * ═══════════════════════════════════════════════════════════════════════════ */

export function PortalScreen(props: {
  /** `CWP-037`. The mark every rendered check in this repo selects on. */
  screen: string;
  /**
   * The screen's `PageHeader`, built ONCE above the branches.
   *
   * ⚠ **IT IS A `ReactNode` AND NOT A SET OF `PageHeader` PROPS, DELIBERATELY.**
   * Re-declaring `kicker`/`title`/`backTo`/`secondaryActions` here would be a
   * second page-header interface one import away from the first, which is
   * exactly the two-of-everything failure B14 rule 36 exists to stop — the
   * portal has already had two `TwoCol`s and three `Panel`s. The screen keeps
   * composing `@/components/PageHeader`; this only decides WHERE it renders,
   * which is *on every branch*.
   */
  head: ReactNode;
  /** Extra classes for the screen's own outer stack, where it has any. */
  className?: string;
  children: ReactNode;
}) {
  return (
    <div data-screen={props.screen} className={props.className}>
      {props.head}
      {props.children}
    </div>
  );
}

/* ═══════════════════════════════════════════════════════════════════════════
 * 2 · THE ONE STATE CARD
 * ═══════════════════════════════════════════════════════════════════════════ */

/** Which of the three this is. Rendered as `data-portal-state`. */
export type PortalStateKind = "loading" | "empty" | "failed";

/**
 * One way out of a state — R-10's *"the thing they can do about it"*.
 *
 * Exactly one of `to` and `onClick` is used and `to` wins if both are given, so
 * a way out is either a real address (⌘-click opens it in a second tab, and the
 * address bar tells a person where they are) or an action on this screen.
 */
export interface PortalWayOut {
  label: string;
  /** An ALREADY-RESOLVED portal address — run it through `usePortalPath` in the
   *  screen. A bare `/help` from here comes out `//portal/help`, a
   *  protocol-relative URL to another host that reads as a perfectly good
   *  string to every assertion we own (`BR-CWP-007`, hard-won law 2). */
  to?: string;
  onClick?: () => void;
  /** The loud one. At most one per card — r10's *exactly one primary*. */
  tone?: "primary" | "plain";
  testKey?: string;
}

interface PortalStateBase {
  /**
   * **THE SENTENCE, AND IT IS REQUIRED — THIS IS R-22 IN ONE PROP.**
   *
   * The PO's ruling narrows the blueprint's *"three states can never render as
   * the same picture"* to *"differntiate it using text message"*: the same
   * card, the same shape, the same position, **three different sentences**.
   * So there is no default here and there never will be one — a default would
   * put the same words on fifty screens, which is the rule's own failure case
   * with extra steps. An empty state says WHAT IS ABSENT; a failed state says
   * THE READ DID NOT WORK; a loading state says IT IS STILL COMING.
   *
   * ⚠ **AND IT IS CLERK-FACING COPY, so it is a catalogue key in all eleven
   * languages** — passed in by the screen, because only the screen knows what
   * is absent.
   */
  sentence: string;
  /** Preserves the `data-testid` the screen's existing card carried. */
  testId?: string;
  /** Anything the screen draws under the sentence — rarely needed. */
  children?: ReactNode;
}

/**
 * ⚠ **`waysOut` IS OPTIONAL AND THAT IS A DELIBERATE, STATED LIMIT (hard-won
 * law 1 — say what a thing does not guarantee).**
 *
 * R-10 says bad news never appears without the way out beside it, so the
 * honest type would make `waysOut` REQUIRED on `failed`. It is not, for one
 * reason: on the day this component was written, ten portal screens had a
 * failed branch and not one of them had a way out to give it — the read they
 * would retry is held in each screen's own effect, and per-screen actions
 * belong to the lane that owns that screen (`CR-085` step 2 splits exactly
 * there). A required prop would have been satisfied ten times by `waysOut={[]}`
 * or by a `Try again` wired to nothing, which is `EmptyList`'s own
 * `onCta: () => undefined` defect (`DEF-MET-4764`) — a control that looks
 * pressable, is pressable, and does nothing.
 *
 * **What this component guarantees instead is that it CAN carry one**, in the
 * right place, next to the message rather than a page away. What it cannot do
 * is know whether one exists. `states.dom.test.tsx` asserts the card renders
 * them; the census in `pageHeadCensus.test.ts` is where *which screens still
 * have none* belongs.
 */
export type PortalStateProps = PortalStateBase & {
  kind: PortalStateKind;
  waysOut?: readonly PortalWayOut[];
};

/** ⚠ **`ButtonLink` AND NOT A `<Button>` INSIDE A `<Link>` — the kit already
 *  owns this exact shape** (B14 rule 36). A button nested in a link is two
 *  focusable elements for one control and reaches a keyboard twice; the kit's
 *  own note says why the link form exists at all: *"it is a link because it
 *  NAVIGATES; making it a button would break middle-click and the browser's own
 *  open-in-new-tab."* On a failure card that matters — a customer who cannot
 *  load this page often wants the way out in a second tab. */
function WayOut(props: { wayOut: PortalWayOut }) {
  const { wayOut } = props;
  const variant = wayOut.tone === "primary" ? "primary" : "secondary";
  const handle = wayOut.testKey ?? wayOut.label;
  if (wayOut.to !== undefined) {
    return (
      <ButtonLink to={wayOut.to} variant={variant} data-way-out={handle}>
        {wayOut.label}
      </ButtonLink>
    );
  }
  return (
    <Button variant={variant} onClick={wayOut.onClick} data-way-out={handle}>
      {wayOut.label}
    </Button>
  );
}

/**
 * The portal's loading / empty / failed card — **one picture, three sentences.**
 *
 * ⚠ **IT IS THE SAME CARD FOR ALL THREE ON PURPOSE.** The blueprint's own
 * wording (*"can never render as the same picture"*) reads as a demand for
 * three distinct designs across fifty screens; the PO's ruling replaced that
 * with three distinct SENTENCES, and the decision log records why it is the
 * better answer as well as the cheaper one: three layouts is three new chances
 * to be inconsistent, and the information a customer actually needs is in the
 * words. **So do not fork this into three components.**
 *
 * ⚠ **IT IS NOT `@/components/StateFrame`'s `FailedWithRetry`, AND THE
 * DIFFERENCE IS NOT COSMETIC.** That is the STAFF panel: a red *Failed* pill,
 * *"the address may be wrong"*, and a **Download error report** button. Portal
 * screens import it today, so on 2026-09-11 the service-centre finder offered a
 * member of the public an error report to download because there was no service
 * centre near them — a staff control, on an EMPTY state, drawn as a failure.
 * A customer has nowhere to send an error report and no idea what one is.
 *
 * ⚠ **B14 rule 21** — Tailwind utilities only; this file is covered by the
 * `portal/` directory entry in `styles/route-b-migrated.txt`, so the compiler
 * is asked about it and the classes are actually emitted (`DEF-974`).
 */
export function PortalState(props: PortalStateProps) {
  const waysOut = props.waysOut ?? [];
  return (
    <section
      // ⚠ **THE KIND IS IN THE DOM AND THAT IS THE ONLY WAY R-22 CAN EVER BE
      // CHECKED.** The three states are told apart by their words, and no
      // check in this repo can read whether a sentence MEANS "empty" — so the
      // card says which one it is in an attribute, and a walkthrough can then
      // assert that the empty address and the failed address do not render the
      // same kind. Without it the rule is unobservable by anything but a
      // person reading fifty screens.
      data-portal-state={props.kind}
      data-testid={props.testId}
      // Loading is announced as busy; a failure is an alert. An empty state is
      // neither — it is ordinary content that happens to say nothing is there.
      aria-busy={props.kind === "loading" ? true : undefined}
      role={props.kind === "failed" ? "alert" : undefined}
      className="flex flex-col gap-4 border border-neutral-200 bg-[white] p-4"
    >
      <p className="text-body text-neutral-600" data-state-sentence={props.kind}>
        {props.sentence}
      </p>
      {props.children}
      {waysOut.length > 0 ? (
        // ⚠ **R-10, LITERALLY: *"on that same screen, next to the message"*.**
        // The row is INSIDE this card, directly under the sentence — not in
        // the page head, not in a rail, not behind a menu. `gap-2` is the
        // scale's *inside a control* step; `TwoUp`'s 20px is for fields.
        <div className="flex flex-wrap items-center gap-2" data-ways-out="">
          {waysOut.map((wayOut) => (
            <WayOut key={wayOut.testKey ?? wayOut.label} wayOut={wayOut} />
          ))}
        </div>
      ) : null}
    </section>
  );
}
