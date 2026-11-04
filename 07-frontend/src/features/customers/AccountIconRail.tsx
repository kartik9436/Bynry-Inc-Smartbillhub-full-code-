// ── Trace ──────────────────────────────────────────────
// Change:   CR-030 W3 · task 3.2 — the account-detail ICON RAIL. Was ⛔ D2 in
//           B18 §5.2.1 ("a picture cannot say what a glyph does") and is RULED
//           as of 2026-08-24.
// Story:    US-CUS-008 (S21 detail header, status pills & action rails)
//           Screens: S21
// Rules:    BR-SHL-045 (the seven, in r10's order, each naming itself — and the
//           name is the button's ACCESSIBLE NAME, not only a hover tooltip) ·
//           BR-SHL-025 (a control with no endpoint is DISABLED WITH ITS REASON,
//           never hidden) · B14 rule 6 (the destructive control takes the danger
//           tier — colour, not only shape) · B14 rule 15 (icons with tooltips,
//           one glyph vocabulary) · B14 rule 21 (new UI is Tailwind utilities
//           and adds NO class to a stylesheet)
// Impacts:  `AccountDetailPage.tsx` — seven worded secondary buttons leave the
//           page header and become these seven glyphs. Nothing is deleted.
// ───────────────────────────────────────────────────────
//
// THE SEVEN, AND WHAT EACH ONE DOES.
//
// BR-SHL-045, PO 2026-08-24, on being shown three presentations and choosing
// *"Seven icons, label appears on hover"* over a two-icon-plus-menu reduction
// and over icons with words beneath:
//
//     ✉ Send statement · 🖨 Print bill · $ Issue credit · ⇄ Change plan ·
//     ⚡ Disconnect notice · 🗓 Payment plan · ✎ Add note
//
// That is r10's own seven-item secondary rail in r10's own order, transcribed
// from `05-prototype/r10-2026-08-16/SMARTBillHub.dc.html` (~offset 167k) rather
// than proposed here. B18's §5.2.1 proposal — *"✉ contact · 🖨 print statement ·
// $ record payment · ⇄ transfer · ⚡ actions overflow · 🗓 schedule · ✎ edit"* —
// is NOT what was ruled and is not what is built: two of its seven (record
// payment, an overflow menu) are not even the same kind of control.
//
// ⚠ **THE "SEVEN VERSUS TEN" WAS NEVER A MISSING THREE.** `AccountDetailPage`'s
// own docstring says *"a header card, a ten-action rail and nine tabs"*. The ten
// are these seven PLUS Record payment, Adjust and Move-out — and those three are
// r10's ACTION STACK, the worded buttons beside the metric columns (task 3.3,
// already built). So no feature leaves the screen here; three move out of the
// rail into words, which is what r10 draws.
//
// ⚠ **HOVER IS A MOUSE, AND THAT IS WHY THIS IS A COMPONENT AND NOT SEVEN
// TOOLTIPS.** BR-SHL-045 rules the label as the button's ACCESSIBLE NAME, which
// hover happens to reveal: a real `aria-label` AND a `title`, on a real
// `<button>` that tab reaches and Enter/Space activates. A tooltip alone leaves
// a touch user guessing between two glyphs — and one of the two SENDS A
// DISCONNECT NOTICE. `components/RowActions.tsx` is the one place in this
// product where the accessible name is a REQUIRED prop rather than an
// attribute somebody remembers, so the rail is built out of `RowAction` rather
// than reimplementing the same control a second time. Its own header states
// why: *"Making the label a REQUIRED PROP is the only form where forgetting it
// does not compile."*
//
// ⚠ **AND `reason` AND `disabled` ARE ONE PROP THERE**, which is exactly
// BR-SHL-025's shape: an icon whose module has not shipped cannot be drawn
// disabled without saying why, because there is no boolean to pass. Four of the
// seven are in that state today (Send statement · Print bill · Issue credit ·
// Disconnect notice) and each carries its owning module's own sentence from
// `UNAVAILABLE_ACTIONS`, the same sentence the worded button carried an hour
// ago. Three are LIVE (Change plan · Payment plan · Add note) and were live
// before this rail existed — the reason this task replaces the buttons rather
// than deleting them.
//
// WHY A `<div>` OF `RowAction`s AND NOT `<RowActions>` ITSELF
// ───────────────────────────────────────────────────────────
// `RowActions` is the ACTIONS CELL of a table row and is `flex-nowrap` on
// purpose — DEF-352, where four 32px icons folded 2×2 inside a column sized for
// text. This is not a table cell: r10 draws the rail as
// `display:flex;gap:6px;flex-wrap:wrap` under a rule, and at seven glyphs it is
// meant to wrap on a narrow viewport rather than push the card wide. So the
// CONTROL is shared and the CONTAINER is this screen's own.
import type { ReactNode } from "react";

import {
  BoltIcon,
  CalendarIcon,
  DollarIcon,
  EnvelopeIcon,
  MessageIcon,
  PencilIcon,
  PrinterIcon,
  SwapIcon,
} from "@/components/icons";
import { RowAction } from "@/components/RowActions";
import type { Translator } from "@/features/tenancy/settingsShared";

/** The seven, in r10's own left-to-right order. */
export const ACCOUNT_RAIL_ACTION_IDS = [
  //: ⚠ **AN EIGHTH, 2026-09-12 — `CR-094-BRC01` wave K, `ACC-S16`.** Step 1's
  //: finding F11, verbatim: *"There is no way to write to the customer from
  //: this screen. Seven icons and six buttons and not one sends a word."* `R6`
  //: draws it FIRST on the rail, which is where it is.
  //:
  //: BR-SHL-045 ruled SEVEN and this is not a quiet eighth: the rule ruled the
  //: seven that existed, against a proposal to reduce them, and `ACC-S16` is a
  //: commitment card in the blueprint's own §12. The rail's `actions` prop is a
  //: `Record` over these ids, so this line does not compile until the page
  //: wires it — which is hard-won law 2 made structural rather than remembered.
  "communication",
  "sendStatement",
  "printBill",
  "issueCredit",
  "changePlan",
  "disconnectNotice",
  "paymentPlan",
  "addNote",
] as const;

export type AccountRailActionId = (typeof ACCOUNT_RAIL_ACTION_IDS)[number];

interface AccountRailGlyph {
  id: AccountRailActionId;
  /** The i18n key for the words. It becomes `aria-label` AND `title`. */
  labelKey: string;
  /** From `components/icons.tsx` — the one owner (B14 rule 15, DEF-348). */
  icon: ReactNode;
  /** B14 rule 6: the destructive one is told apart by COLOUR, not only shape. */
  danger: boolean;
}

/**
 * The rail's contents, declared once so a test can iterate them rather than
 * re-listing seven strings that could drift from the screen.
 *
 * ⚠ `changePlan` reuses `SwapIcon` and `addNote` reuses `PencilIcon`. r10 draws
 * each of those two with a path four units different from the vocabulary's
 * (rounded corners on the swap arrows; a longer pencil), and adding a second
 * near-identical glyph for the difference is DEF-348 exactly — the same shape
 * twice under two names. The divergence is recorded in `icons.tsx` beside the
 * five glyphs this rail DID need adding.
 */
export const ACCOUNT_RAIL_ACTIONS: readonly AccountRailGlyph[] = [
  {
    //: `MessageIcon` is the vocabulary's existing speech bubble and is reused
    //: rather than a ninth near-identical glyph being drawn (DEF-348).
    id: "communication",
    labelKey: "customers.account.action.communication",
    icon: <MessageIcon />,
    danger: false,
  },
  {
    id: "sendStatement",
    labelKey: "customers.account.action.sendStatement",
    icon: <EnvelopeIcon />,
    danger: false,
  },
  {
    id: "printBill",
    labelKey: "customers.account.action.printBill",
    icon: <PrinterIcon />,
    danger: false,
  },
  {
    id: "issueCredit",
    labelKey: "customers.account.action.issueCredit",
    icon: <DollarIcon />,
    danger: false,
  },
  {
    id: "changePlan",
    labelKey: "customers.account.action.changePlan",
    icon: <SwapIcon />,
    danger: false,
  },
  {
    // BR-SHL-045, verbatim: *"The disconnect icon takes B14's danger tier"* —
    // "so the destructive one is distinguishable by colour and not only by
    // shape". It is `ghost-danger` and not rule 6's filled `danger` tier
    // because this control OPENS a notice flow rather than committing one;
    // `buttonKit.ts` draws that distinction and this rail obeys it.
    id: "disconnectNotice",
    labelKey: "customers.account.action.disconnectNotice",
    icon: <BoltIcon />,
    danger: true,
  },
  {
    id: "paymentPlan",
    labelKey: "customers.account.action.paymentPlan",
    icon: <CalendarIcon />,
    danger: false,
  },
  {
    id: "addNote",
    labelKey: "customers.account.action.addNote",
    icon: <PencilIcon />,
    danger: false,
  },
];

/**
 * What the page must supply for ONE glyph.
 *
 * `reason: null` means the action is allowed; any sentence DISABLES the control
 * and becomes its tooltip (BR-SHL-025). It is not optional, so a rail action
 * cannot be added without the page saying whether this deployment can honour it.
 */
export interface AccountRailAction {
  reason: string | null;
  onClick: () => void;
}

/**
 * S21's icon rail.
 *
 * `actions` is a `Record` over the seven ids rather than seven optional props:
 * a missing one does not compile, which is the only form in which "built is not
 * wired" (hard-won law 2, G13) cannot happen here. Every prop on this component
 * is REQUIRED for the same reason.
 */
export function AccountIconRail(props: {
  t: Translator;
  actions: Record<AccountRailActionId, AccountRailAction>;
}) {
  return (
    // r10 draws the rail inside the header card, under `<hr class="hr">`, at
    // `display:flex;gap:6px;flex-wrap:wrap`. This app renders the metric block
    // BELOW the shared PageHeader (a divergence `AccountDetailPage` already
    // records, because `components/PageHeader.tsx` belongs to another lane), so
    // the rail follows the metric block and the negative top margin closes the
    // gap the metric block's own `mb-4` opens — the two read as one card
    // divided by a rule, which is r10's shape.
    //
    // `data-account-icon-rail` is a MARKER, not a style hook: the header slice
    // in the test file learned the hard way (see its own note) that slicing on
    // a style class breaks silently the day the style migrates.
    <div
      className="-mt-4 mb-4 flex flex-wrap items-center gap-1.5 border-t border-t-divider bg-surface px-6 py-3"
      data-account-icon-rail=""
      role="group"
      aria-label={props.t("customers.account.rail.label")}
    >
      {ACCOUNT_RAIL_ACTIONS.map((glyph) => {
        const wired = props.actions[glyph.id];
        return (
          <RowAction
            key={glyph.id}
            label={props.t(glyph.labelKey)}
            icon={glyph.icon}
            reason={wired.reason}
            danger={glyph.danger}
            onClick={wired.onClick}
          />
        );
      })}
    </div>
  );
}
