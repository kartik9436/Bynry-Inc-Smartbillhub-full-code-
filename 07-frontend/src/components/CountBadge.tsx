// ── Trace ──────────────────────────────────────────────
// Change:   CR-139-BRC08 · Finance blueprint `P2.15` — *"BandHeading and
//           CountBadge … both are new"*. Only ONE of the two is built, and the
//           measurement that decided it is in this header.
// Task:     `P2.15` (the component) · `P2.18` (its first host, the Revenue & AR
//           view strip) · blueprint p014 (the task row), p030 (1·5a's
//           `Entries · 3`), p039 and p041 (the two queue views' own
//           *Components to use* tables, each naming this by name)
// Rules:    B14 rule 43 (a piece of UI used TWICE is a COMPONENT — standalone
//           code inside a page is not reuse) · rule 21 (Tailwind utilities, no
//           class added to any stylesheet; this file is on
//           `route-b-migrated.txt` from its first commit) · rule 31 (no
//           database id is ever a visible value) · rule 33 (a LABEL is ≤ 3
//           words — this renders a NUMBER and no words at all)
// Tests:    src/components/CountBadge.test.tsx
// ───────────────────────────────────────────────────────
//
// ══════════════════════════════════════════════════════════════════════════
// WHY THIS ONE IS BUILT AND `BandHeading` IS NOT — THE RE-MEASUREMENT
// ══════════════════════════════════════════════════════════════════════════
// `P2.15` proposes both. The lane before this one judged NEITHER to be worth
// building and gave a measured reason: rule 43 makes a component out of UI used
// **twice**, and each of the two had one host or none. That judgment was
// correct when it was made and **it flips for exactly one of them the moment
// `P2.18` lands**, which is why it was re-taken rather than inherited:
//
//   · **`CountBadge` — TWO HOSTS, so it is a component.** `P2.18`'s view strip
//     puts a pending count in TWO of its five labels (*Write-offs · 2* and
//     *Refunds · 1*, drawn on p033, p034, p036 and p038), and p030's own
//     *Components to use* table puts the same badge on 1·5a's `Entries · 3`
//     with the words *"The same badge the Revenue & AR view labels use"*. Two
//     FILES, which is what rule 43 measures — not two call sites in one page.
//
//   · **`BandHeading` — ONE HOST, so it is NOT built.** Its two named hosts
//     were the old Revenue & AR board's four bands and 6·1's three steps, and
//     **`P2.18` retires the board**, which takes the first of the two away. A
//     component with one caller is hard-won law 2's dead UI wearing rule 43's
//     clothes: it renders, every test passes, and nothing is reused. It is
//     recorded as not-built rather than silently skipped.
//     (`features/billing/BudgetEnrolPage.tsx` has a private `BandHeading` used
//     three times inside ONE page — that is already a component, it is a
//     different thing, and it is deliberately left alone.)
//
// ══════════════════════════════════════════════════════════════════════════
// WHAT IT IS NOT
// ══════════════════════════════════════════════════════════════════════════
// ⚠ **IT IS NOT A STATUS PILL AND MUST NOT GROW INTO ONE.** `StatusPill` says
// WHAT something is; this says HOW MANY are waiting. A pill here would put two
// different meanings in one shape, which is the `Chip` header's own warning one
// component over.
//
// ⚠ **IT RENDERS A COUNT AND NEVER A TOTAL.** The blueprint is explicit about
// what this number is for (p038): *"The answer to 'a page lies about what is
// pending' is the count in the view label: `Write-offs · 2` states the true
// total on every page, so paging can no longer hide anything."* So the caller
// passes the WHOLE-POPULATION pending count — never `rows.length` of the page
// on screen, which is the exact lie the badge exists to end.
//
// ⚠ **ZERO RENDERS NOTHING.** A badge reading `0` beside *Write-offs* is noise
// on four of the five views for the whole of a quiet month, and B14 rule 32's
// description budget is spent on facts that change. `null` and `undefined`
// render nothing for the DIFFERENT reason that the count is not known yet —
// and the two are deliberately indistinguishable on screen, because a clerk
// acts identically on both and rule 33 puts the rationale at zero words.
//
// ⚠ **THE TOKENS ARE THE THEME'S.** `src/styles/tailwind.css` sets
// `--color-*: initial`, which DELETES Tailwind's stock palette — so
// `text-gray-500` would compile to NOTHING while `tsc`, eslint and every
// `toContain("text-gray-500")` assertion passed, because the class IS in the
// DOM (DEF-974 · DEF-SHL-5088). `neutral-700`, `text` and `text-btn-sm` are
// declared; `src/styles/routeBUtilities.test.ts` compiles every class in this
// file through the real Tailwind and is the only check that knows.
import type { ReactNode } from "react";

/**
 * r10's numeric counts are tabular and quiet: the LABEL carries the emphasis
 * and the number sits beside it at the same small size as a button's own type.
 *
 * `tabular-nums` is not decoration — a strip whose counts change under a poll
 * would jitter its labels sideways without it.
 */
const BADGE = "ml-1.5 inline-block font-heading text-btn-sm font-semibold tabular-nums";

export interface CountBadgeProps {
  /** The whole-population count. `0`, `null` and `undefined` all render nothing
   *  — see the header for why the last two are not distinguished. */
  count: number | null | undefined;
  /** What this count is OF, for a screen reader — the badge itself is a bare
   *  number and *"2"* alone tells a non-sighted user nothing. Supplied by the
   *  caller because only the caller knows the label it is riding in.
   *
   *  ⚠ **A KEY'S TEXT, NOT A KEY.** This component does not translate: the
   *  eleven catalogues are the caller's business, and a `t()` inside the kit
   *  would put one sentence's wording in a file no translator reads. */
  srLabel: string;
  /** Muted by default. `accent` is for a count that is itself the reason to
   *  look — nothing passes it today and it exists so the next caller does not
   *  invent a second badge to get one (rule 43's own failure mode). */
  tone?: "muted" | "accent";
}

export function CountBadge(props: CountBadgeProps): ReactNode {
  const { count } = props;
  if (count === null || count === undefined || count === 0) {
    return null;
  }
  const tone = props.tone === "accent" ? "text-accent-text" : "text-neutral-700";
  return (
    <span className={`${BADGE} ${tone}`} data-count={count}>
      {/* The number is the visible value and the sentence is the accessible
          one. Both describe the same fact, so the number is hidden from the
          accessibility tree rather than read twice. */}
      <span aria-hidden="true">{count}</span>
      <span className="sr-only">{props.srLabel}</span>
    </span>
  );
}

export default CountBadge;

// ── Lifecycle ─────────────────────────────────────────────
// packet: 05-prototype/07 Finance Blueprint.pdf p014 (`P2.15`), p030 (1·5a),
//         p033/p034/p036/p038 (the strip, drawn on all five views) and
//         p039/p041 (the two *Components to use* tables) — rendered at scale 3
//         and read as IMAGES (B14 rule 42) ·
//         04-docs/02-decisions/14-ui-conventions.md rules 21/31/32/33/43/44
// generated: 2026-09-24 by LANE FIN-P2B
// checklist: A✔ B=n/a(no endpoint) C✔ D=n/a E✔(two host files) F✔ G✔ H=n/a
// exceptions:
//   E1 **`0` RENDERS NOTHING**, which the drawing cannot show either way — it
//      draws a month with two write-offs and one refund waiting. Stated rather
//      than assumed, because the opposite reading (a `0` badge on every quiet
//      view) is equally consistent with the picture.
//   E2 **NO `t()` INSIDE THE KIT.** `srLabel` is text the caller has already
//      translated; see the prop's own note.
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
