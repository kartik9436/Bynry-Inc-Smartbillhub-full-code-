// ── Trace ──────────────────────────────────────────────
// Story:    US-SHL-013 (EP-SHL-05 §Stories — display kit)  Screens: every status chip (S17, S25, S30, S33, S49, …)
// Rules:    BR-SHL-023 (labels from the catalog) · A12 §Semantic tokens (status meaning only, never decoration)
// ───────────────────────────────────────────────────────
// FE-10 StatusPill (B13 §1): THE status chip. SIX semantic tones map to the
// A12 design-system pill classes (2026-08-07 addendum; `info` and `muted`
// added 2026-08-26, DEF-722 — see the StatusTone union): success → .pill.ok,
// warning → .pill.warn, danger → .pill.past, neutral → .pill.draft. The
// consuming screen maps ITS A5 enum value to a tone + a pre-translated label
// from its own catalog keys — this component never knows domain statuses, so
// a new status never needs a new pill. The .pill base class is StateFrame.css's
// one definition (BR-SHL-020 composition); this file adds only the tone
// classes StateFrame does not already carry.
import type { ReactNode } from "react";


/**
 * ⚠ **SIX SINCE 2026-08-26, AND THE TWO NEW ONES ARE A PO RULING (DEF-722).**
 * Verbatim: *"have differnt color for diff pill - you can define colors -
 * recommendation: A"*. BR-CUS-055 seeds SIX account statuses; four tones meant
 * two statuses shared a colour, and the pair that shared it — `Pending
 * activation` (never started) and `Disconnected` (cut off, owes money, can come
 * back) — are opposite facts a clerk has to tell apart on S17.
 *
 * `info` is a NEW hue (`--color-info-*`). `muted` is NOT: it is the existing
 * neutral ramp one step solid, so the grey family holds both of the "no money
 * at stake" states and separates them by weight — pale = nothing has happened
 * yet, solid = the file is shut.
 *
 * ⚠ **THESE ARE STILL STATUS MEANING, NEVER DECORATION (A12 §Semantic
 * tokens).** `info` is not "a blue pill"; it is *paused, and nothing is wrong*.
 * `muted` is not "a grey pill"; it is *finished, and nothing is owed*. A screen
 * reaching for one of them because it likes the colour is the rule A12 exists
 * to stop.
 */
export type StatusTone = "success" | "warning" | "danger" | "info" | "neutral" | "muted";

// A12 §Semantic tokens: the design-system styling per tone — status meaning
// ONLY, never decoration. CR-018 Route B: StatusPill.css (deleted) ported
// value for value — each tone was one background + one text colour, and the
// utilities name the exact tokens the rules read (--color-success-100 etc.).
// `past` stays a CLASS: `.pill.past` is StateFrame.css's rule and that file
// is not migrated yet, so the danger tone keeps composing it unchanged.
const TONE_CLASS: Record<StatusTone, string> = {
  success: "bg-success-100 text-success-700",
  warning: "bg-warning-100 text-warning-700",
  danger: "past",
  // DEF-722. Contrast measured against each fill, not assumed — WCAG AA wants
  // 4.5:1 for this size and the four originals sit at 4.45–6.24:
  //   info   #1d4ea8 on #e6eefb = 6.64:1
  //   muted  #2d2b2b on #bab6b6 = 7.01:1
  info: "bg-info-100 text-info-700",
  neutral: "bg-neutral-200 text-neutral-700",
  // ⚠ `muted` DELIBERATELY ADDS NO TOKEN. neutral-400 is a step this ramp
  // already declares, and the whole design of the grey family here is that the
  // two quiet statuses differ by WEIGHT rather than by hue: neutral-200 is
  // "nothing has happened yet", neutral-400 is "this is over".
  muted: "bg-neutral-400 text-neutral-900",
};

export interface StatusPillProps {
  tone: StatusTone;
  children: ReactNode; // pre-translated label from the consuming screen's catalog keys
  /** A qualifier the label cannot carry without becoming a sentence.
   *
   * ⚠ ADDED 2026-08-24 (DEF-644) FOR ONE REASON, and it should stay rare. The
   * `Autopay on` pill is TRUE and INCOMPLETE: autopay in this version is "a
   * promise recorded, never a charge" (`apps/payments/models.py:623`), so a
   * clerk can switch it on and reasonably expect the next bill to be taken. It
   * will not be. That warning used to live in a page-level panel, which the PO
   * deleted on 2026-08-24 — correctly, a build backlog does not belong in a
   * grey box — and it had no second home.
   *
   * This is the BR-SHL-025 pattern pointed at a pill instead of a button: the
   * reason travels ON the thing it is about, so it is read where the mistake
   * would be made rather than at the foot of the page.
   *
   * NOT a general slot for commentary. A pill whose LABEL is wrong is fixed by
   * fixing the label; this is for a label that is right and would mislead
   * alone. */
  title?: string;
}

export function StatusPill(props: StatusPillProps) {
  return (
    <span className={`pill ${TONE_CLASS[props.tone]}`} title={props.title}>
      {props.children}
    </span>
  );
}

// ── Lifecycle ─────────────────────────────────────────────
// packet: US-SHL-013@1e89ecb (story+rules snapshot hash)
// generated: 2026-08-09 by story-coder v1
// checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-08)
// gates: trace_lint✔ run_gates✔ (10 PASS · 0 FAIL · 2 SKIP) tsc✔ eslint✔ vitest 94/94✔ (12 todo this packet — browser/server/consumer scope)
// exceptions: none
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
