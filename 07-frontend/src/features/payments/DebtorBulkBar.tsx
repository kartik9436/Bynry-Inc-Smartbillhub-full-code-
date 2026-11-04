// ── Trace ──────────────────────────────────────────────
// Change:   CR-138-BRC07 · P4.11 — *"Six buttons to two plus overflow — four
//           of the six have never worked. The bar stops teaching clerks to
//           ignore it."* Blueprint `05-prototype/06 Payments Page
//           Blueprint.pdf` **p081** (the drawing), **p082** (annotations ⑤ and
//           ⑥, and the GAP box *"Six bulk buttons, and four of them have never
//           worked"*) and **p083** (*"So the bar drops to two plus an
//           overflow, and the four return when their endpoints land"*), read
//           as IMAGES at 2.0 and 6.0 (B14 rule 42).
//           Screens: 7·1 Debtors (S34 · PAY-J)
// Defect:   DEF-PAY-6252 (the notices refusal outlived its endpoint by hours)
//           · DEF-PAY-6253 (the plan refusal outlived S24 by 38 days)
// Rules:    B14 rule 15 (**max 2 visible + `…` overflow**) · B14 rule 43 (a
//           piece of UI is a COMPONENT) · B14 rule 6 (danger tier on a
//           destructive commit) · B14 rule 32 (a row of controls holds only
//           things a person can PRESS — the eligibility sentence is a FACT and
//           goes in its own slot) · B14 rule 33 (a FACT ≤ 6 words) ·
//           BR-SHL-025 (a control this deployment cannot honour renders
//           DISABLED WITH ITS REASON, never hidden) · BR-PAY-017 · BR-PAY-020
// Tests:    src/features/payments/debtorBulkBar.dom.test.tsx
// ───────────────────────────────────────────────────────
/**
 * **THE DEBTOR LIST'S SELECTION BAR — TWO CONTROLS AND AN OVERFLOW.**
 *
 * The drawing, measured off p081 at 6.0:
 *
 *     3 selected · $1,284.60 │ 2 can be sent · 1 is on a medical hold
 *                                    [Send notice 2] [Move on 2] [ … ] Clear
 *
 * Six buttons became two because **four of the six have never worked**, and
 * the blueprint says so in the product's own words: *"FOUR of the prototype's
 * six bulk actions render DISABLED WITH THEIR REASON."*
 *
 * ══════════════════════════════════════════════════════════════════════════
 * ⚠ TWO OF THOSE FOUR REASONS HAD EXPIRED, AND NOTHING NOTICED
 * ══════════════════════════════════════════════════════════════════════════
 * The task says *"establish which four are dead before you remove anything."*
 * Measured on 2026-09-23, against the running route table and the catalogue:
 *
 * | control | its reason | still true? |
 * |---|---|---|
 * | Send a reminder | *"no route accepts one yet"* | **NO** — `P4.13` mounted `POST /collections/notices` the same day |
 * | Send a disconnection notice | the same sentence | **NO** — the same route |
 * | Offer a payment plan | *"the wizard … is not built yet"* | **NO** — `PaymentPlanWizard` was generated 2026-08-16 and is routed |
 * | Book a site visit | *"no agreed rule behind it"* | **YES**, re-checked by `P4.17` today, and its guard holds the sentence WORD FOR WORD |
 *
 * **So only one of the four was dead for the reason it gave.** That is
 * hard-won law 2's mirror — a live capability behind a dead control — and it
 * is what `DEF-PAY-6252` and `DEF-PAY-6253` record. The blueprint's own line
 * is *"the four return when their endpoints land"*, and two of them have.
 *
 * ══════════════════════════════════════════════════════════════════════════
 * WHAT ACTUALLY CHANGES, AND WHAT DELIBERATELY DOES NOT
 * ══════════════════════════════════════════════════════════════════════════
 * **`Send notice` is PROMOTED to a visible control in the danger tier**, which
 * is annotation ⑥'s own reasoning: *"real postage, a legal instrument, and it
 * cannot be recalled."* It opens **7·3d Send a notice**, the three-step wizard
 * the drawing puts behind it (p087, *"Carried in from your selection"*) — and
 * **7·3d is `P4.14`, which is not built.** So it is still disabled, and its
 * sentence now names the SCREEN rather than the route, because the route is
 * there. A reason that is false is worse than a reason that is unflattering.
 *
 * **`Offer a payment plan` keeps its refusal and loses its false sentence.**
 * S24 takes ONE account; this bar holds a selection of N. The capability that
 * is missing is a BULK plan, which is a different thing from the wizard, and
 * the new sentence says so. The door to the wizard for one account is on
 * **7·2 Debtor**, where the drawing puts it — so the capability a clerk was
 * told did not exist is now one click away, from the row.
 *
 * **`Book a site visit` is not touched — not its label, not its sentence, not
 * its position.** `P4.17` re-checked it hours ago and
 * `tests/test_cr138_p4_17_site_visit_refusal.py` asserts the exact string and
 * a PAIRING INVARIANT: the sentence and the door move together, four states
 * and two lawful. Moving it into the overflow changes neither.
 *
 * ⚠ **NOTHING IS REMOVED.** *"Six to two plus overflow"* is about what is
 * VISIBLE, not about what exists — BR-SHL-025 puts a control that cannot act
 * on screen WITH its reason, because a clerk who expects to send a reminder
 * must see that the product knows about it. All six are still reachable; four
 * of them are one click further away, which is the point of an overflow.
 */
import type { ReactNode } from "react";

import { SelectionToolbar } from "@/components/SelectionToolbar";
import { RowActionsMore, RowMenuAction } from "@/components/RowActions";
import { BellIcon, BoltIcon, CalendarIcon, EnvelopeIcon, RetireIcon } from "@/components/icons";
import { GuardedButton } from "@/features/metering/meteringShared";

export interface DebtorBulkBarProps {
  /** The group's accessible name — a bar of unnamed controls is unusable
   *  without a mouse (B14's own note on rule 15). */
  label: string;
  /** *"3 selected"*, already translated with its count. */
  count: ReactNode;
  /** The selection's money **already rendered** through the one money path, or
   *  the caller's stated absence. This component formats nothing. */
  totalText: ReactNode;
  /**
   * *"2 can be sent · 1 is on a medical hold"* — what will ACTUALLY happen.
   *
   * ⚠ **THE BLUEPRINT FILES ITS ABSENCE AS A GAP.** A bar that goes live when
   * the act will mostly fail is worse than one that is greyed out: the confirm
   * behind it takes only a COUNT, so it asks *"Send 5 notices?"* when it is
   * about to send two and silently skip three. Absent when the screen cannot
   * compute it — a missing fact is not a fact of zero.
   */
  eligibility?: ReactNode;
  /** How many of the selection `Send notice` would actually reach. Drawn ON the
   *  button — *Send notice 2*, never *Send notice* — because the selection and
   *  the eligible set are different numbers and only one is going to happen. */
  sendableCount: number | null;
  /** How many the ladder would step. Same rule, same reason. */
  steppableCount: number | null;

  // ── The two visible controls ────────────────────────────────────────────
  /** `null` = this role may send. A sentence = disabled WITH that sentence. */
  sendNoticeReason: string | null;
  onSendNotice: () => void;
  /** `null` = this role may act. */
  moveOnReason: string | null;
  moveOnWorking?: boolean;
  onMoveOn: () => void;

  // ── The overflow, in the drawing's order ────────────────────────────────
  writeOffReason: string | null;
  onWriteOff: () => void;
  reminderReason: string | null;
  onReminder: () => void;
  planReason: string | null;
  onPlan: () => void;
  /** ⚠ `P4.17` owns this string. Pass it through; do not re-word it. */
  siteVisitReason: string | null;
  onSiteVisit: () => void;

  /** Labels, all eleven catalogues' business. */
  labels: {
    sendNotice: string;
    moveOn: string;
    writeOff: string;
    reminder: string;
    plan: string;
    siteVisit: string;
    more: string;
    clear: string;
  };
  onClear: () => void;
}

/**
 * A count drawn ON its control — *Send notice 2*.
 *
 * ⚠ **A NULL COUNT DRAWS NO NUMBER AT ALL**, and that is not a nicety. The
 * eligible count comes from the same rows the server sent; when the screen
 * cannot work it out, *"Send notice 0"* would say the act will reach nobody,
 * which is a claim. The bare verb says only what it has always said.
 */
export function countedLabel(label: string, count: number | null): string {
  return count === null ? label : `${label} ${count}`;
}

export function DebtorBulkBar(props: DebtorBulkBarProps) {
  return (
    <SelectionToolbar
      label={props.label}
      count={props.count}
      totalText={props.totalText}
      eligibility={props.eligibility}
      role="status"
      data-testid="debtor-bulk-bar"
    >
      {/* ① SEND NOTICE — danger tier. Annotation ⑥: *"real postage, a legal
          instrument, and it cannot be recalled."* B14 rule 6 puts a commit
          nobody can take back in the danger tier, and this one leaves the
          building. */}
      <GuardedButton
        label={countedLabel(props.labels.sendNotice, props.sendableCount)}
        reason={props.sendNoticeReason}
        danger
        onClick={props.onSendNotice}
      />
      {/* ② MOVE ON — the screen's primary action, *"advance the ladder"*. */}
      <GuardedButton
        label={countedLabel(props.labels.moveOn, props.steppableCount)}
        reason={props.moveOnReason}
        variant="primary"
        working={props.moveOnWorking}
        onClick={props.onMoveOn}
      />
      {/* ③ THE OVERFLOW. Annotation ⑥ again: *"Write off moves under ⋯, B14
          15's two-plus-overflow."* `RowActionsMore` is the kit's `…` and it
          renders open-able markup under `renderToStaticMarkup`, so a static
          suite can read what is inside it — a `useState` menu would render as
          nothing at all and four assertions would pass over an empty cell. */}
      <RowActionsMore label={props.labels.more}>
        <RowMenuAction
          icon={<RetireIcon />}
          label={props.labels.writeOff}
          reason={props.writeOffReason}
          danger
          onClick={props.onWriteOff}
        />
        <RowMenuAction
          icon={<BellIcon />}
          label={props.labels.reminder}
          reason={props.reminderReason}
          onClick={props.onReminder}
        />
        <RowMenuAction
          icon={<CalendarIcon />}
          label={props.labels.plan}
          reason={props.planReason}
          onClick={props.onPlan}
        />
        {/* ⚠ `P4.17`'s control. Its sentence is asserted word for word by
            `tests/test_cr138_p4_17_site_visit_refusal.py`, whose pairing
            invariant fails if the sentence and the door ever move apart. */}
        <RowMenuAction
          icon={<BoltIcon />}
          label={props.labels.siteVisit}
          reason={props.siteVisitReason}
          onClick={props.onSiteVisit}
        />
      </RowActionsMore>
      {/* ④ CLEAR — drawn last and at the far right of the controls, a plain
          text tier because it undoes a selection rather than writing anything.
          It is a CONTROL, so it belongs in the run and not in `note`. */}
      <GuardedButton
        label={props.labels.clear}
        reason={null}
        variant="ghost"
        onClick={props.onClear}
      />
    </SelectionToolbar>
  );
}

/** The envelope glyph the notice controls share, exported so 7·2's own
 *  *Send a notice* row action cannot pick a different one. */
export const NOTICE_ICON = <EnvelopeIcon />;

// ── Lifecycle ─────────────────────────────────────────────
// packet: 05-prototype/06 Payments Page Blueprint.pdf p081 (drawing, crops at 5.0 and 6.0), p082 (annotations ⑤⑥ + the GAP box), p083 (*"two plus an overflow"*), read as IMAGES · CR-138-BRC07 §3 P4.11 · 04-docs/02-decisions/14-ui-conventions.md rules 6/15/32/33/43
// generated: 2026-09-23 by LANE P4-SCREENS-A
// checklist: A✔ B=n/a(no endpoint of its own) C✔ D=n/a E✔(OutstandingsTab renders it) F✔ G✔ H=n/a
// exceptions: (1) NOTHING IS REMOVED — "six to two plus overflow" is about what is VISIBLE; BR-SHL-025 keeps every refused control on screen WITH its reason, and four move one click away · (2) `Send notice` is promoted and STAYS DISABLED because its screen 7·3d is `P4.14` and unbuilt — its route landed today, so the sentence now names the screen; a reason that is false is worse than one that is unflattering (DEF-PAY-6252) · (3) `Book a site visit` is passed through untouched in label, sentence and behaviour, because `P4.17`'s pairing invariant asserts the exact string · (4) `Clear` is a `ghost` GuardedButton rather than the kit's `Button` so the whole run of five controls comes from one tier vocabulary
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
