// ── Trace ──────────────────────────────────────────────
// Change:   CR-138-BRC07 · P4.26 — "A Kind column and filter on 6·1".
//           Blueprint `05-prototype/06 Payments Page Blueprint.pdf` p023 (the
//           task row) and p072–p074 (screen 6·1, read AS IMAGES at scale 2 per
//           B14 rule 42). The task line, verbatim: *"Refund or Credit, and a
//           chip that shows one or both. **The columns must not flatten the two
//           lifecycles:** a refund is raised, approved, issued, cleared; a
//           credit note has **no state column at all**."*
//           Screens: 6·1 Refunds (S58 · PAY-P)
// Rules:    B14 rule 31 (no database id is ever the visible value of a field) ·
//           rule 32 (a screen's description budget; a stated absence is a
//           disclosure CLOSED by default) · rule 33 (a LABEL ≤ 3 words, a FACT
//           ≤ 6; RATIONALE is ZERO words on screen) · rule 21 (Tailwind
//           utilities, no stylesheet class — this file is on
//           `styles/route-b-migrated.txt` from its first commit) · rule 43 (a
//           piece of UI is a COMPONENT; standalone code inside a page is not
//           reuse) · BR-BIL-074 (a credit note's amount is stored NEGATIVE) ·
//           BR-SHL-020 (plain language when something is absent) ·
//           BR-SHL-023 (ONE money formatting path)
// Tests:    07-frontend/src/features/payments/refundsAndCredits.dom.test.tsx
// Impacts:  features/payments/RefundsPage.tsx (6·1's only consumer) ·
//           api/endpoints.getRefundsAndCredits (`P4.25`, the read this draws)
// ───────────────────────────────────────────────────────
//
// THE CELLS THAT KEEP TWO LIFECYCLES APART.
//
// ╔══════════════════════════════════════════════════════════════════════════╗
// ║  A REFUND HAS FIVE STATES. A CREDIT NOTE HAS NONE. THE COLUMN SAYS SO.   ║
// ╚══════════════════════════════════════════════════════════════════════════╝
// The blueprint's own GAP panel (p074) states it and the server enforces it:
//
//   *"A refund has five states and a two-person control — requested, approved,
//   issued, cleared, voided — because money leaves the utility and a bank has
//   to confirm it. **A credit note has one field that matters and no lifecycle
//   at all**: it is issued, and it auto-applies at the next bill. There is no
//   `state` column on `CreditNote` to read. … **A single "status" that meant
//   something different depending on the row would be the drift this document
//   keeps finding.**"*
//
// So `refunds_and_credits._row_for_credit_note` sends **no `status` key at
// all** — not `null`, ABSENT — and `RefundStateCell` below branches on
// `row.status === undefined` rather than on a falsy check. `null` would read on
// screen as *we do not know*; the truth is *there is nothing to know*, and they
// are different sentences to say to a clerk.
//
// ⚠ **THE DRAWN SAMPLE ROWS CONTRADICT ALL OF THAT, AND THEY LOSE (B14 rule
// 37).** p073's five illustrative rows put `Issued` and `Applied` chips in the
// State column of both CRN rows. Three other frames of the SAME document say
// the opposite — its GAP panel above, its own annotation ⑥ (*"State · the two
// lifecycles are different and the column does not pretend otherwise"*) and its
// task row P4.26 (*"a credit note has no state column at all"*) — and so does
// the built read, whose test drives RED on *"a credit note was given a
// synthesised status"*. Rule 37: **a figure drawn in a wireframe is an
// ILLUSTRATION, never a fact to build to**; where two frames of one blueprint
// draw the same fact differently, build the shape they agree on. Filed as
// `DEF-PAY-6278` rather than silently resolved.
//
// ══════════════════════════════════════════════════════════════════════════
// WHAT THIS FILE WILL NOT DRAW, AND WHY THAT IS THE POINT
// ══════════════════════════════════════════════════════════════════════════
// **NEVER INVENT A VALUE THE SERVER REFUSED TO ANSWER.** A sibling lane shipped
// *"$0.00 taken today"* where the server had said *"I cannot answer that"*, past
// `tsc`, 26 tests and every gate. Every cell below has an explicit branch for
// the absent case and none of them falls back to a plausible word:
//
//   · a credit note's STATE      → a stated absence, never `Issued`
//   · a row with no NUMBER       → the reason it has none, never a bare dash
//                                  (`DEF-127` — a dash reads as *this record
//                                  has no reference*, and the truth is either
//                                  *this refund is not a cheque* or *nobody has
//                                  set up numbering*)
//   · an unrecognised absence    → an em-dash and nothing else. Printing the
//     CODE                         code would put an internal string on a
//                                  clerk's screen (rule 31)
import type { ReactNode } from "react";

import { MoneyCell } from "@/components/MoneyCell";
import { StatusPill } from "@/components/StatusPill";
import type { StatusTone } from "@/components/StatusPill";
import type { RefundLifecycle, RefundsAndCreditsRow } from "@/api/endpoints";
import type { Translator } from "@/features/tenancy/settingsShared";

// ── The vocabulary, borrowed and not minted ────────────────────────────────
// `refunds_and_credits.KIND_REFUND` / `KIND_CREDIT_NOTE`. The filter, the
// discriminator and the `lifecycles` descriptor all use these two strings
// server-side, so a screen cannot offer a word it cannot filter by.
export const KIND_REFUND = "refund";
export const KIND_CREDIT_NOTE = "credit_note";

/** The `number_absence` codes, verbatim from `refunds_and_credits`. Two of the
 *  three are DIFFERENT FACTS kept apart for `DEF-127`'s reason: one is a
 *  property of this refund and the other is a gap in the tenant's settings, and
 *  a clerk sent to fix the second when it is the first has been sent to fix
 *  nothing. */
export const NUMBER_ABSENT_NO_SERIES = "refunds_have_no_number_series";
export const NUMBER_ABSENT_NOT_A_CHEQUE = "refund_is_not_a_cheque";
export const NUMBER_ABSENT_HISTORIC_NOTE = "credit_note_predates_numbering";

const ABSENCE_KEY: Readonly<Record<string, string>> = {
  [NUMBER_ABSENT_NO_SERIES]: "payments.refundsAndCredits.number.noCheque",
  [NUMBER_ABSENT_NOT_A_CHEQUE]: "payments.refundsAndCredits.number.notACheque",
  [NUMBER_ABSENT_HISTORIC_NOTE]: "payments.refundsAndCredits.number.historic",
};

/** The em-dash every *"there is genuinely nothing here"* cell draws. It is one
 *  constant because three cells need it and three spellings of a dash is how a
 *  list stops looking like one list. */
const DASH = "—";

// ── Pure pieces (provable without a browser or a network) ──────────────────

/**
 * A2/A12's tone for a KIND — and a kind is not a status, so neither value is
 * `success` or `danger`.
 *
 * A refund and a credit note are two ways of giving money back and **neither is
 * the good one**: the blueprint's outcome line for the whole task is *"the
 * cheaper option becomes visible where the choice is made"*, which is an
 * economics fact about the utility and not a judgment about the row. Colouring
 * `Credit` green would tell a clerk that a customer who got a credit was
 * treated better than one who got a cheque.
 */
export function refundKindTone(kind: string): StatusTone {
  return kind === KIND_CREDIT_NOTE ? "info" : "neutral";
}

/**
 * The i18n key for a kind's LABEL — ≤ 3 words (B14 rule 33), and `Refund` and
 * `Credit` are both one.
 *
 * ⚠ An UNKNOWN kind returns `null` rather than the raw string. The two kinds
 * are a closed set the server publishes on every response; a third would be a
 * deployment this build does not know, and echoing its internal code into a
 * cell is exactly what rule 31 forbids.
 */
export function refundKindLabelKey(kind: string): string | null {
  if (kind === KIND_REFUND) {
    return "payments.refundsAndCredits.kind.refund";
  }
  if (kind === KIND_CREDIT_NOTE) {
    return "payments.refundsAndCredits.kind.creditNote";
  }
  return null;
}

/**
 * The `+ Filter` panel's options for Kind — **DERIVED FROM THE RESPONSE, NEVER
 * TYPED OUT HERE.**
 *
 * `CLAUDE.md` hard-won law: the service list is hand-typed in two places, so an
 * eleventh service does not appear on screen on its own *and it fails
 * silently*. The same trap one table over: a kind the server starts serving
 * would be filterable by nobody, `tsc` and every test would pass, and the chip
 * would simply never offer it. `kinds` is on every envelope for this reason.
 *
 * A kind with no label key is DROPPED rather than rendered as its code — the
 * filter then offers one option fewer, which is visible, instead of an internal
 * string, which is a rule-31 breach.
 */
export function kindFilterOptions(
  kinds: readonly string[],
  t: Translator,
): { value: string; label: string }[] {
  const options: { value: string; label: string }[] = [];
  for (const kind of kinds) {
    const key = refundKindLabelKey(kind);
    if (key !== null) {
      options.push({ value: kind, label: t(key) });
    }
  }
  return options;
}

/**
 * Does this row's KIND have a state column to read at all?
 *
 * ⚠ **THE ANSWER COMES OFF THE ENVELOPE, NOT OFF A CONSTANT IN THIS FILE.**
 * `lifecycles[kind].has_state` is carried on every response precisely so the
 * screen does not hold a second copy of a fact the server owns — the shape
 * hard-won law 1 exists for. When the descriptor is missing the answer is
 * `null`: **not `false`**, because *this kind has no lifecycle* and *this build
 * cannot tell you whether it does* are different, and collapsing them is how a
 * screen starts asserting things it was never told.
 */
export function kindHasState(
  kind: string,
  lifecycles: Record<string, RefundLifecycle> | undefined,
): boolean | null {
  const lifecycle = lifecycles?.[kind];
  return lifecycle === undefined ? null : lifecycle.has_state;
}

// ── The cells ──────────────────────────────────────────────────────────────

export interface RefundCellProps {
  row: RefundsAndCreditsRow;
  t: Translator;
}

/** ④ **Kind** — *"Refund or Credit, as a column and a filter"* (p073). */
export function RefundKindCell(props: RefundCellProps) {
  const key = refundKindLabelKey(props.row.kind);
  if (key === null) {
    return <span className="text-neutral-700">{DASH}</span>;
  }
  return <StatusPill tone={refundKindTone(props.row.kind)}>{props.t(key)}</StatusPill>;
}

export interface RefundStateCellProps extends RefundCellProps {
  lifecycles: Record<string, RefundLifecycle> | undefined;
  /** The screen's own status→tone map, passed in rather than re-derived, so
   *  6·1 and the refund detail cannot tone one status two ways. */
  tone: (status: string) => StatusTone;
}

/**
 * ⑥ **State** — *"the two lifecycles are different and the column does not
 * pretend otherwise"* (p073, annotation ⑥).
 *
 * Three branches, and the middle one is the whole task:
 *
 *   `status` present            → the refund's pill, as it always was
 *   `status` absent, no state   → a STATED ABSENCE (rule 32). There is nothing
 *                                 to know, and the cell says that rather than
 *                                 inventing `Issued`
 *   `status` absent, unknown    → an em-dash alone. This build was not told
 *                                 whether this kind has a lifecycle, so it
 *                                 asserts nothing either way
 */
export function RefundStateCell(props: RefundStateCellProps) {
  const status = props.row.status;
  if (status !== undefined && status !== "") {
    return (
      <StatusPill tone={props.tone(String(status))}>
        {props.t(`payments.refunds.status.${String(status)}`)}
      </StatusPill>
    );
  }
  const hasState = kindHasState(props.row.kind, props.lifecycles);
  if (hasState === false) {
    return (
      <span
        className="text-neutral-700"
        title={props.t("payments.refundsAndCredits.state.noneTitle")}
      >
        {props.t("payments.refundsAndCredits.state.none")}
      </span>
    );
  }
  return <span className="text-neutral-700">{DASH}</span>;
}

/**
 * ⑤ **How** — *"cheque or card for a refund; **a credit is not paid out at all**
 * and says so"* (p073, annotation ⑤).
 *
 * The blueprint draws the credit row's cell as *"— stays on account"* and its
 * GAP panel says why in terms: *"the shared columns tell the truth instead of
 * inventing a state for a credit: **How** reads — stays on account rather than
 * a blank."* A blank here would read as *we failed to load the method*.
 */
export function RefundHowCell(props: RefundCellProps) {
  if (props.row.kind === KIND_CREDIT_NOTE) {
    return (
      <span className="text-neutral-700">{props.t("payments.refundsAndCredits.how.onAccount")}</span>
    );
  }
  const method = props.row.source.method;
  if (typeof method !== "string" || method === "") {
    return <span className="text-neutral-700">{DASH}</span>;
  }
  return <>{props.t(`payments.refunds.method.${method}`)}</>;
}

/**
 * ③ **Reference** — *"RFD- or CRN- — two series, one column"* (p073).
 *
 * ⚠ **ONLY ONE OF THE TWO SERIES EXISTS TODAY, AND THE CELL SAYS WHICH IS
 * MISSING RATHER THAN DRAWING A DASH.** `Credit memo #` is real
 * (`core.numbering.CREDIT_MEMO`). Refunds have **no number column at all**:
 * `_refund_number` serves the CHEQUE number — the bank's, not ours — and it is
 * null on every ACH refund and on every refund before it is issued.
 * `OQ-PAY-12605` closed 2026-09-23 with the PO's *"(a) Its own series,
 * RFD-26-0001"*, so `refunds.refund_no` is OWED and `number` starts carrying it
 * the day it lands — **this cell does not change when it does.**
 *
 * ⚠ **AND NOTHING IS BACKFILLED**, which is why the absence sentences matter: a
 * refund issued before the series exists carries no number, and inventing one
 * would be a reference no document ever carried. B14 rule 31 keeps ids off
 * screens, so an unnumbered old refund shows an honest absence.
 */
export function RefundReferenceCell(props: RefundCellProps) {
  const number = props.row.number;
  if (number !== null && number !== "") {
    return <>{number}</>;
  }
  const key = props.row.number_absence === null ? undefined : ABSENCE_KEY[props.row.number_absence];
  if (key === undefined) {
    return <span className="text-neutral-700">{DASH}</span>;
  }
  return <span className="text-neutral-700">{props.t(key)}</span>;
}

/**
 * **Reason** — a SENTENCE, never a code.
 *
 * ⚠ **THIS CELL RENDERED `wrong_read` ON A LIVE SCREEN, AND IT WAS FOUND BY
 * LOOKING AT ONE.** The first draft was `row.reason ?? ""`, which is right for a
 * REFUND — `refunds.reason` is free text a clerk typed, *"Customer overpaid the
 * June bill and asked for the surplus back"* — and wrong for a CREDIT NOTE,
 * whose `reason` is one of `billing.correction_reasons`' thirteen CODES. B14
 * rule 31 forbids an internal code reaching a utility user by name, and no
 * check in this repo could see it: `tsc` passes, the cell renders a non-empty
 * string, and the drawn column on p073 is full of human sentences
 * (*"Closed in credit"*, *"Goodwill"*, *"Deposit returned"*) so it looks right
 * until a real credit note is in the list. Hard-won law 6, earning its keep.
 *
 * `billing.fix.reason.*` is the EXISTING label family — thirteen keys in all
 * eleven catalogues, written for the Fix-a-bill wizard — so nothing is minted
 * here and the two screens cannot name one reason two ways.
 *
 * ⚠ **A CODE WITH NO SENTENCE DRAWS A STATED ABSENCE, NOT THE CODE.** `t()`
 * answers an unknown key with the key itself, so the fallback has to be
 * explicit; printing the raw value "because it is better than nothing" is the
 * defect this comment is about.
 */
export function RefundReasonCell(props: RefundCellProps) {
  const reason = props.row.reason;
  if (reason === null || reason === "") {
    return null;
  }
  if (props.row.kind !== KIND_CREDIT_NOTE) {
    // A refund's reason is prose, and prose is what the column wants.
    return <>{reason}</>;
  }
  const key = `billing.fix.reason.${reason}`;
  const label = props.t(key);
  if (label === key) {
    return (
      <span className="text-neutral-700">{props.t("payments.refundsAndCredits.reason.unnamed")}</span>
    );
  }
  return <>{label}</>;
}

export interface RefundAmountCellProps {
  row: RefundsAndCreditsRow;
}

/**
 * **Amount** — the MAGNITUDE given back, positive for both kinds.
 *
 * `refunds.amount` is POSITIVE and `credit_notes.amount` is NEGATIVE by CHECK
 * constraint (`BR-BIL-074`), and the server takes the single `abs()` in ONE
 * place with its reason written there. The signed figure travels untouched on
 * `source.amount`. This cell therefore does no arithmetic at all — it formats a
 * decimal string through the one money path (`BR-SHL-023`), which is what keeps
 * `DEF-085`'s *"signed Σ reading $272.30 on a run where the customer owed
 * $222.30"* from arriving one table over.
 */
export function RefundAmountCell(props: RefundAmountCellProps): ReactNode {
  return <MoneyCell amount={props.row.amount_returned} currency={props.row.currency} />;
}

// ── Lifecycle ─────────────────────────────────────────────
// packet: CR-138-BRC07 P4.26 (payments blueprint phase 4, wave 2) — built from
//         p072–p074 read AS IMAGES at scale 2.0 (B14 rule 42), with the task
//         row on p023 and the GAP panel on p074 as the binding text.
// generated: 2026-09-23 by LANE P4-SCREENS-B
// exceptions: (1) **6·1's ACCOUNT and CUSTOMER columns are NOT DRAWN, and that
//         is a reported absence rather than an oversight.** The blueprint draws
//         both; `GET /refunds-and-credits` serves neither on either side of the
//         seam — `selectors.refund_row` and `billing.selectors.credit_note_row`
//         each carry `account_id` (a uuid, which B14 rule 31 forbids on screen)
//         and no `account_no`, and no customer name crosses at all. Filed as
//         `DEF-PAY-6279` rather than faked; the two columns land when the read
//         serves them.
// ──────────────────────────────────────────────────────────
