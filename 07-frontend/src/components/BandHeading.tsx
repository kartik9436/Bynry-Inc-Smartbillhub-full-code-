// ── Trace ──────────────────────────────────────────────
// Change:  Finance blueprint `P5.9` (p068) — *"BandHeading · the two steps · A
//          component, never inline markup — B14 rule 43 · P2.15"*. The 6·1
//          Close rebuild is this component's SECOND host, which is what makes
//          it a component today and did not on 2026-09-24 this morning.
// Rules:   B14 rule 43 (a piece of UI is built as a COMPONENT; standalone code
//          inside a page is not reuse) · B14 rule 36 (where the kit lacks a
//          piece, ADD IT TO THE KIT) · B14 rule 33 (a LABEL or heading is ≤ 3
//          words and never a sentence) · B14 rule 21 (Tailwind utilities; this
//          file is on `route-b-migrated.txt`) · B14 rule 44 (our token scale
//          and spacing say HOW a drawn thing is built, and win)
// Tests:   src/components/BandHeading.test.tsx
// Impacts: src/features/ledger/CloseView.tsx (the two numbered steps) ·
//          src/features/billing/BudgetEnrolPage.tsx (three bands, which
//          declared this function locally until now)
// ───────────────────────────────────────────────────────
//
// ╔══════════════════════════════════════════════════════════════════════════╗
// ║  WHY IT IS A COMPONENT NOW AND WAS CORRECTLY NOT ONE THIS MORNING        ║
// ╚══════════════════════════════════════════════════════════════════════════╝
//
// Lane FINANCE-P2 was asked to extract this under `P2.15` and **deliberately
// did not**, recording the judgment in the decision log of 2026-09-24:
//
//   *"`BandHeading`'s ONLY host is phase 5 … Rule 43 says a piece of UI used
//   TWICE is a component; both are used ONCE or ZERO times. Extracting either
//   now ships a component with no second caller on the promise of a task
//   nobody has scheduled — which is hard-won law 2's dead UI, the exact thing
//   rule 43 exists to prevent in the other direction."*
//
// That was right, and the same rule now points the other way: the 6·1 rebuild
// draws **two** numbered steps and `BudgetEnrolPage` already draws **three**
// bands, so the count is five across two features. P2's row says the extraction
// is *"owed to `P2.18`/`P5.4`, not skipped"* — this is that debt being paid by
// the host it was owed to, rather than by a lane guessing a host would appear.
//
// ⚠ **NOTHING ABOUT THE RENDERING CHANGED IN THE MOVE**, exactly as `P2.14`
// said of `AbsentFigure` the same day: the class list below is byte-for-byte
// the one `BudgetEnrolPage` declared, so the three bands it already draws are
// unmoved by a pixel. A move that also changes behaviour is two changes wearing
// one commit.
//
// ⚠ **AND `BudgetEnrolPage` DOES NOT RE-EXPORT IT.** Two import paths for one
// component is the drift the move exists to remove, and a compatibility
// re-export is how a move never finishes — `AbsentFigure`'s own record says so.
import type { ReactNode } from "react";

/**
 * The small capitalised heading that opens a band inside a section — the two
 * numbered steps on 6·1 Close, the three bands on the budget-enrolment form.
 *
 * ⚠ **IT IS A HEADING AND B14 RULE 33 CAPS IT AT THREE WORDS**, with no
 * sentence. *Step 1 · Finish September* reads as four and is three plus its
 * ordinal, which is the drawn form on p067 and is the reason the ordinal is
 * passed as `children` rather than added here: a component that composed the
 * number would be deciding the wording of every band that uses it.
 *
 * `as` exists because the level depends on what the band sits inside — the
 * budget form's bands are inside a `<section>` under an `<h3>`, and the close
 * view's steps sit directly under the page `<h1>`. A heading level is a
 * document structure fact, not a style, and hard-coding `h4` here would put an
 * `h4` under an `h1` on one of the two screens.
 */
export function BandHeading(props: { children: ReactNode; as?: "h3" | "h4" }) {
  const Tag = props.as ?? "h4";
  return (
    <Tag className="mt-4 mb-1 font-heading text-xs font-extrabold uppercase tracking-tag text-[color-mix(in_srgb,var(--color-text)_55%,transparent)] first:mt-0">
      {props.children}
    </Tag>
  );
}

// ── Lifecycle ─────────────────────────────────────────────
// packet: Finance blueprint p068 `P5.9` · decision log 2026-09-24 (`P2.15`, the recorded debt)
// generated: 2026-09-24 by lane FIN-P5 (the 6·1 Close rebuild — this component's second host)
// checklist: A✔ B✔ C=n/a D=n/a E✔ F✔ G✔ H=n/a (no money math)
// gates: vitest src/components/BandHeading.test.tsx · tsc · G31 (this file is on route-b-migrated.txt, so routeBUtilities.test.ts owns its classes)
// exceptions: (1) `as` is a prop rather than a fixed level — see the docstring; a heading level is document structure and the two hosts sit at different depths
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
