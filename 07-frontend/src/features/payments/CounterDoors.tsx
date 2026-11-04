// ── Trace ──────────────────────────────────────────────
// Change:   `CR-136-BRC07` `P2.7` and `P2.9` — the two doors onto the counter
//           that live on OTHER screens. From `05-prototype/06 Payments Page
//           Blueprint.pdf` §03 frames **2·1** (p030, note ①) and **2·3a**
//           (p037–p038, note ①), read as IMAGES at scale 2.0 (B14 rule 42).
// Screens:  2·1 Payments · 2·3a Record a payment
// Rules:    B14 rule 4 (`Verb →` navigates) · rule 33 (a FACT ≤ 6 words, an
//           INSTRUCTION ≤ 6 words per sentence) · rule 43 (a piece of UI is a
//           COMPONENT — these are two hosts and one answer) · rule 21 ·
//           BR-SHL-025 (the refusal is the SERVER's; these state it) ·
//           `CR-136-BRC07` §3.4
// Tests:    src/features/payments/counterDoors.dom.test.tsx
// ───────────────────────────────────────────────────────
// Two controls, one question: **is my counter open?**
//
// ══════════════════════════════════════════════════════════════════════════
// `P2.7` — THE PAGE-HEAD SLOT, AND IT HAS TWO STATES
// ══════════════════════════════════════════════════════════════════════════
// 2·1 note ①, verbatim: *"`Start counter →` · opens your till **and its batch
// in one act** · B14 4's `Verb →`, because it opens the screen in flow 2 ·
// **NEW — AND IT WAS MISSING ENTIRELY** · when your counter is already open
// this same slot reads **`Your counter · CTR-260921-DW · open`** and is the
// door back to it"*.
//
// **The second state is the half that is easy to lose.** A slot that always
// says `Start counter →` is a control that lies to the one clerk who already
// has a till open — and `uq_counter_sessions_open_owner` means pressing it
// would be refused, so the product would offer an act it knows it will refuse.
//
// ══════════════════════════════════════════════════════════════════════════
// `P2.9` — THE RECORD BANNER, AND WHY IT IS NOT A BLANKET REFUSAL
// ══════════════════════════════════════════════════════════════════════════
// 2·3a note ①: *"Which batch this goes into · a clerk must never wonder ·
// NEW · refuses the form when no batch is open"*, over the drawn sentence
// **"Goes into your counter batch CTR-260921-DW, open since 08:55."**
//
// ⚠ **`CR-136-BRC07` §3.4 NARROWS THAT, AND THE NARROWING IS THE PO's.**
// Ruling of 2026-09-23: *"(a) Refuse it. \"Start your counter first.\" One
// press, then take the money. It is the only option where every cash dollar
// belongs to somebody"* — and it names **three of the seven tenders**:
// `cash`, `check`, `money_order`, the ones that pass through hands. The other
// four — `ach`, `card`, `wire`, `lockbox` — keep phase 0's system till and
// need no counter at all. A banner that refused a back-office ACH keying would
// be a control refusing work the product permits.
//
// ⚠ **AND IT REFUSES NOTHING ITSELF.** `BR-SHL-025`: the check is at the
// endpoint (`P2.23`), never on a screen. This banner STATES the position and
// offers the way out, which is `P2.9`'s own task line — *"offers `Start
// counter →` rather than only refusing"*. A refusal with no door is hard-won
// law 2's mirror.
import { useTranslation } from "react-i18next";

import type { ApiClient } from "@/api/client";
import { ButtonLink } from "@/components/Button";
import { formatDate } from "@/components/DateCell";
import { useRegional } from "@/features/metering/meteringShared";
import type { RegionalProps } from "@/features/metering/meteringShared";
import { useTenantPath } from "@/routing/tenantPath";

import { COUNTER_START_ROUTE, CounterNote, counterRoute } from "./counterShared";

// ⚠ **`data-counter-door` AND `data-counter-banner` ARE A SIBLING LANE'S TEST
// HOOKS, AND HONOURING THEM IS THE POINT.** `10-scripts/p2head_counter_door_
// walkthrough.mjs` walks every payments tab asking *does the door point at
// `?start=1`* and finds it by `[data-counter-door]`. This component predates
// that walk and emitted neither attribute, so the walk reported **"no Start
// counter control"** on five tabs that visibly have one — a check looking at
// the wrong thing (law 7), over doors that were fine. Two lanes agreeing on a
// selector costs two attributes; not agreeing costs a false red that reads
// exactly like a real one.
import { useMyOpenCounter } from "./useCounter";

/**
 * **THE THREE TENDERS THAT PASS THROUGH HANDS** — `CR-136-BRC07` §3.4, and
 * they are the tenants' own `payment_methods.code` values.
 *
 * ⚠ **NOT A LIST THIS SCREEN INVENTED AND NOT ONE IT MAY WIDEN.** The ruling
 * names exactly these three and leaves the other four alone on purpose: a card
 * swiped at a window is among the four, because the Close screen counts only
 * cash and cheques and a card total typed back at the system's own figure
 * makes the reconciliation worthless.
 *
 * ⚠ **A CHEQUE THAT ARRIVES IN THE MAIL IS NOT DECIDED.** The case put to the
 * PO was cash at a counter; a back-office clerk keying a mailed cheque never
 * sits at a till and this list would catch them. `CR-136-BRC07` §3.4 says in
 * as many words: **do not build a silent exception and do not widen the
 * ruling** — raise it as a question when the take-payment path is built.
 */
export const TENDERS_THAT_NEED_A_TILL = ["cash", "check", "money_order"] as const;

export function tenderNeedsATill(methodCode: string | null | undefined): boolean {
  return (
    methodCode !== null &&
    methodCode !== undefined &&
    (TENDERS_THAT_NEED_A_TILL as readonly string[]).includes(methodCode)
  );
}

/**
 * ⚠ **THESE TWO RESOLVE THEIR OWN REGIONAL PAIR RATHER THAN TAKING ONE.**
 * `RecordPaymentModal` has NINE call sites across payments, customers and
 * seven test files, and `AccountDetailPage` mounts it too. Threading a new
 * REQUIRED prop through all of them to reach one banner would have been nine
 * edits in files this lane does not own — and every one of them a chance to
 * revert a sibling (hard-won law 11). `useRegional` is a hook and reads the
 * same provider those screens already sit inside; an explicit override stays
 * available for a test that wants to state which tenant it is testing.
 */
export interface CounterDoorProps extends RegionalProps {
  client?: ApiClient;
  /** BR-SHL-025: a string here disables the way in and says why. */
  writeBlockedReason?: string | null;
}

/**
 * `P2.7` — the page-head slot, in both of 2·1 ①'s states.
 *
 * ⚠ **BOTH STATES ARE ADDRESSES, NOT HANDLERS**, for `DEF-CWP-3925`'s reason:
 * a control whose destination is a closure carries nothing a test can assert,
 * which is how the customer portal shipped six dead doors over live screens.
 */
export function CounterHeadSlot(props: CounterDoorProps & { variant?: "primary" | "secondary" }) {
  const { t } = useTranslation();
  const tenantPath = useTenantPath();
  const mine = useMyOpenCounter(props.client);
  const variant = props.variant ?? "secondary";

  // ⚠ **A READ THAT HAS NOT LANDED DRAWS THE WAY IN, AND THIS PARAGRAPH USED
  // TO SAY THE OPPOSITE.** It returned `null` while loading, reasoning that a
  // `Start counter →` swapped under a clerk's cursor is worse than a beat of
  // nothing. **That was wrong in the direction this repository fails in.**
  //
  // A page head with an EMPTY action slot is a MISSING DOOR — hard-won law 2's
  // mirror, the defect that cost the customer portal six of its eight front
  // doors — and on a slow connection it is the state a clerk actually sees.
  // The flicker costs a glance; the absence costs the only way to open a till.
  //
  // ⚠ **AND THE TEST IS WHAT FOUND IT.** `sevenTabs.dom.test.tsx` asserts this
  // door BY ADDRESS through a SERVER render, where a query is `isLoading` for
  // ever — so the old branch made the page head's action slot permanently
  // empty to the one check written to protect it. A door a test cannot see is
  // a door nobody is keeping.
  //
  // The way IN is the right default for the unknown state: its worst case is a
  // clerk who already has a till open pressing it and being told so, which is
  // recoverable and informative. The other default's worst case is a clerk who
  // cannot take money and cannot see why.
  //
  // ⚠ **THE BANNER BELOW KEEPS ITS `isLoading` → `null`, AND THAT IS NOT AN
  // INCONSISTENCY.** A head slot that appears is a door; a BANNER that appears
  // is a refusal, and a refusal that flashes and withdraws is worse than one
  // that waits a beat.

  if (props.writeBlockedReason != null) {
    // The reason rides on `title` here rather than as body text: a page head is
    // a row of CONTROLS (B14 rule 15's reasoning), and a sentence in it is the
    // fact-in-a-control-row shape the PO objected to ten times in one sitting.
    return (
      <ButtonLink
        variant={variant}
        to={tenantPath(COUNTER_START_ROUTE)}
        aria-disabled="true"
        title={props.writeBlockedReason}
        data-counter-door="blocked"
      >
        {t("payments.counter.action.start")}
      </ButtonLink>
    );
  }

  const open = mine.data ?? null;
  if (open === null) {
    return (
      <ButtonLink variant={variant} to={tenantPath(COUNTER_START_ROUTE)} data-counter-door="start">
        {t("payments.counter.action.start")}
      </ButtonLink>
    );
  }

  // *"…this same slot reads `Your counter · CTR-260921-DW · open` and is the
  // door back to it"*. The code is a HUMAN-FACING number, which is the one
  // thing B14 rule 31 lets a screen show (the id never leaves the client).
  return (
    <ButtonLink
      variant={variant}
      to={tenantPath(counterRoute(open.code))}
      data-counter-door="yours"
    >
      {t("payments.counter.door.yours", { counter: open.code })}
    </ButtonLink>
  );
}

/**
 * `P2.9` — 2·3a's banner. Which batch this money goes into, said plainly,
 * because a clerk must never wonder.
 */
export function RecordCounterBanner(
  props: CounterDoorProps & {
    /** The tender the form currently has chosen — `payment_methods.code`. */
    methodCode: string | null;
    /**
     * **Whether an OPEN till's sentence is said at all.** Absent means yes,
     * which is 2·3a and every caller that existed before this line.
     *
     * ⚠ **`false` IS FOR MONEY THAT JOINS NO BATCH (`DEF-CUS-6376`).** A
     * service request's application fee is a `counter_receipts` row under the
     * 2026-09-19 *OPTION A2* ruling — no payment row, so no deposit batch —
     * and *"Goes into your counter batch …"* would be false there. The
     * refusal half (no till, a hand tender) is unchanged and still drawn.
     */
    announceBatch?: boolean;
  },
) {
  const { t } = useTranslation();
  const tenantPath = useTenantPath();
  const { timeZone, dateFormat } = useRegional(props);
  const mine = useMyOpenCounter(props.client);

  if (mine.isLoading) {
    return null;
  }

  // ⚠ **A FAILED READ IS NOT *NO TILL*** — the `DEF-127` shape. Saying *start
  // your counter first* to a clerk who HAS one open, because the server did
  // not answer, sends them to open a second till the database will refuse.
  if (mine.isError) {
    return (
      <CounterNote tone="plain" data-counter-banner="unknown">
        {t("payments.counter.door.unknown")}
      </CounterNote>
    );
  }

  const open = mine.data ?? null;
  if (open !== null && props.announceBatch === false) {
    return null;
  }
  if (open !== null) {
    // ⚠ **TWO SENTENCES WHERE THE DRAWING WRITES ONE, AND B14 RULE 33 IS WHY.**
    // p037 draws *"Goes into your counter batch CTR-260921-DW, open since
    // 08:55."* — NINE words, and rule 33 caps a FACT at six. Nothing is lost:
    // it is the same two facts, and *"two sentences of six beat one sentence
    // of twelve"* is the rule's own preference. Reported rather than taken
    // quietly, because rule 41 makes a drawing that contradicts a signed rule
    // the one thing that reaches the PO.
    //
    // ⚠ **THE INSTANT IS FORMATTED INTO THE SENTENCE RATHER THAN RENDERED
    // BESIDE IT.** A `<DateCell>` after a translated fragment is the
    // concatenated sentence B8 forbids — it breaks in German and Japanese
    // word order, where the time does not come last. `formatDate` is the same
    // function `DateCell` itself calls, so there is still ONE date-formatting
    // path (BR-SHL-023).
    return (
      <CounterNote tone="plain" data-counter-banner="open">
        {t("payments.counter.door.goesInto", { counter: open.code })}{" "}
        {t("payments.counter.door.openSince", {
          when: formatDate(open.opened_at, timeZone, dateFormat, true),
        })}
      </CounterNote>
    );
  }

  // No till, and the tender does not need one — the four that keep phase 0's
  // system till. Nothing is said, because there is nothing a clerk must do.
  if (!tenderNeedsATill(props.methodCode)) {
    return null;
  }

  // §3.4's refusal, WITH ITS DOOR. Two sentences of five and four words.
  return (
    <CounterNote tone="warning" data-counter-banner="none">
      {t("payments.counter.door.needATill")}{" "}
      {/* ⛔ `size="small"` DID NOT COMPILE — `ButtonSize` is
          `"default" | "sm" | "row"` (`buttonKit.ts`), so `tsc` answered TS2322
          and this file was part of a RED type check on the branch. B14 rule 5's
          "two button sizes only" is the reason the union is closed; the small
          one is spelt `sm`. */}
      <ButtonLink
        variant="secondary"
        size="sm"
        to={tenantPath(COUNTER_START_ROUTE)}
        data-counter-door="banner"
      >
        {t("payments.counter.action.start")}
      </ButtonLink>
    </CounterNote>
  );
}

// ── Lifecycle ─────────────────────────────────────────────
// packet: CR-136-BRC07 §3.4 · §4 rows `P2.7` and `P2.9` · blueprint p030 and p037–p038 as images at 2.0
// generated: 2026-09-23 by LANE P2-SCREENS
// checklist: A✔ B=n/a(`GET /counters` is `P2.3`, LANE P2-API's) C✔ D=n/a E✔ F✔ G✔ H=n/a
// gates: tsc --noEmit · vitest src/features/payments/counterDoors.dom.test.tsx · G31 · routeBUtilities.test.ts
// exceptions: E3 `GET /counters?f.mine=1` is NOT SERVED at this commit — the slot draws the way IN when the read fails rather than hiding the only door · E3 the banner refuses nothing: `BR-SHL-025` puts the check at the endpoint (`P2.23`) · E3 2·3a's agreed move from a modal to `/payments/record/new` was a separate change and is DONE (`DEF-PAY-6317`, 2026-09-23) — `RecordCounterBanner` now mounts in `RecordPaymentForm`, the component inside the page, and this exception is CLOSED rather than left standing over work that has landed
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
