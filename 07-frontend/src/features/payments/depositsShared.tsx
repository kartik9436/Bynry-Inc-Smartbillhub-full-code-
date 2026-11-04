// ── Trace ──────────────────────────────────────────────
// Story:    US-PAY-020 (S37 — the batch row, the KPI strip, the day-cut) ·
//           US-PAY-021 (S38 — the four match states) · US-PAY-022 (S40 — a
//           difference explained with reason + GL) · US-PAY-023 (S39 — the
//           trail's event vocabulary and BR-PAY-004's lock)
//           Screens: S37 · S38 · S39 · S40
// Rules:    BR-PAY-004 (a reconciled batch LOCKS; Unreconcile is the only
//           reversal) · BR-PAY-019 (bank rec in FINANCE; reason AND GL on every
//           difference) · BR-PAY-025 (a TILL × a tender since 2026-09-22) ·
//           BR-PAY-035 ("Force match
//           anyway" permanently SUPERSEDED — this module offers no such
//           control and no code path could express one) · BR-PAY-040 (a card
//           day reconciles NET with its fee as its own line) · BR-SHL-020
//           (plain language when something is absent) · BR-SHL-023 (ONE money
//           formatting path) · BR-SHL-025 (a control this deployment cannot
//           honour renders disabled WITH its reason) · CLAUDE.md rule 2
// ───────────────────────────────────────────────────────
// The pieces S37, S38, S39 and S40 are built from.
//
// ══════════════════════════════════════════════════════════════════════════
// THE ONE THING THIS MODULE EXISTS FOR: "PENDING" IS NOT "$0.00"
// ══════════════════════════════════════════════════════════════════════════
// `deposit_batches.bank_total` is NULL until a statement line is tied, and NULL
// means *the bank has not shown us this money yet*. The prototype draws that
// cell as the literal word **pending** and the Difference cell as an em dash —
// two different absences, deliberately distinguished on the design's own S37.
//
// A screen can undo that in one character. `{row.bank_total ?? "0.00"}` prints a
// deposit that reconciles perfectly to zero over money nobody has confirmed, and
// that is DEF-127 — an account screen that showed **$0.00** while the ledger
// held an issued, unpaid **$108.88** — aimed at a bank reconciliation. So this
// module owns the rendering of an absent bank figure, `BankFigure` takes a
// REASON as a required prop, and no screen here formats money any other way.
//
// ══════════════════════════════════════════════════════════════════════════
// FOUR CONTROLS THIS FAMILY REFUSES TO DRAW
// ══════════════════════════════════════════════════════════════════════════
//   1. **"Force match anyway."** The prototype's S40 has the button
//      (UtilityBilling.html:5597). BR-PAY-035 made it **permanently
//      SUPERSEDED** and `reconcile_batch` has no path that reconciles a
//      residual — there is no request body a client could send that would do
//      it. It is not disabled here; it does not exist.
//   2. **A GL-account NUMBER picker.** The prototype offers *"6200 · Merchant
//      Fees"* and *"1020 · Undeposited Funds"*, and **neither code is in any
//      signed chart** (DEF-067). B5 line 74 ❄️ has **1000 Cash · 1010
//      Undeposited funds · 6800 Bank fees**. The fee account is resolved by
//      DESIGNATION through the server (`bank_fees`), never typed here, and when
//      the tenant has designated none the form ASKS instead of substituting.
//   3. **The deposit-slip CSV.** IS-9's "Deposit slip for bookkeeper" rides the
//      platform export pipeline and `deposit_batches` is not a registered
//      exportable resource — the control renders disabled with that reason
//      (BR-SHL-025) rather than as a second download path.
//   4. **An "NSF this cheque" control inside S40.** The prototype's modal marks
//      a member bounced from the reconcile dialog. The bounce is
//      `apps/payments/reversal.py`'s and the PO placed it on the PAYMENT (OQ-134
//      closure, 2026-08-12) — and the same ruling holds the batch total still
//      at **$2,840.00** when cheque #4021's **$100.00** is returned, because
//      rewriting a signed-off batch is the in-place edit hard rule 4 forbids.
//      A control here would suggest the total moves. It does not.
import { isApiError } from "@/api/client";
import type {
  BankRecGap,
  DepositBatchMember,
  DepositBatchRow,
  StillOpenCounters,
} from "@/api/bankRecEndpoints";
import { EyeIcon, PencilIcon, RollBackIcon } from "@/components/icons";
import { formatMoney, MoneyCell } from "@/components/MoneyCell";
import {
  RowAction,
  RowActionLink,
  RowActions,
  RowActionsMore,
  RowMenuAction,
} from "@/components/RowActions";
import type { StatusTone } from "@/components/StatusPill";
import { ROLE_SYSTEM_ADMIN } from "@/features/metering/meteringShared";
import type { Translator } from "@/features/tenancy/settingsShared";

import "./payments.css";

// ── Permission (A4 "Finance / reconcile / export") ─────────────────────────
// BR-PAY-019 puts bank rec in the FINANCE area, *"Owner/Finance roles"*, and
// A4's own row reads System Admin Full · Billing Clerk — · Executive Full. A
// clerk who records payments all day does not reconcile the bank, and
// US-PAY-021 TC-6 makes that a NEGATIVE test. Declared once so the four screens
// cannot gate on two copies of the code.
export const BANKREC_PERMISSION = "finance_reconcile_export";

// ── Routes ────────────────────────────────────────────────────────────────
// TENANT-RELATIVE (PO 2026-08-10 path tenancy). `/finance/deposits` is the
// RATIFIED sidebar child (BR-SHL-001) and the Finance page's own second tab, so
// S37 lands exactly where the nav already points — the tab has been sending
// people to a "arrives with…" panel since the Finance screens shipped.
export const DEPOSITS_ROUTE = "/finance/deposits";
export const DEPOSITS_IMPORT_ROUTE = "/finance/deposits/import";
// CR-059 W8 · P8 — the period statement. All-static, and it MUST be declared
// above `deposits/:batchId` in the router for the same reason `import` is, or
// the word "statement" resolves as a batch id and the screen 404s on a batch
// that never existed.
export const DEPOSITS_STATEMENT_ROUTE = "/finance/deposits/statement";
export const depositBatchRoute = (batchId: string) => `${DEPOSITS_ROUTE}/${batchId}`;
// ⛔ `WRITE_OFFS_ROUTE = "/finance/write-offs"` IS GONE — `CR-135` P1.10,
// 2026-09-22. The write-off approval queue is `WriteOffQueuePanel` inside
// Revenue & AR (`CR-060` §8b), and the standalone page at this address was a
// second implementation of the same queue that nothing ever linked to. The
// CONSTANT goes with the route on purpose: an address constant outliving its
// route is what a later lane re-mounts from, and an absence is invisible to
// every check this repository has.

// ── `CR-186-BRC10` · WHOSE DEPOSIT AN ALL-TENDERS BATCH IS ─────────────────

/** PO 2026-10-21: one batch per till, or per provider or channel, per day —
 *  every tender in it. A person's till has no channel and reads *All tenders*;
 *  a channel reads its own name. `office` and `lockbox` are ours and are
 *  translated; a PROVIDER (`invoice_cloud`, `paymentus`) is a proper noun and
 *  is shown as its own name, never translated. */
export function depositOwnerLabel(channel: string | null, t: Translator): string {
  if (channel === null || channel === "") {
    return t("payments.deposits.allTenders");
  }
  if (channel === "office" || channel === "lockbox") {
    return t(`payments.deposits.channel.${channel}`);
  }
  // PO 2026-10-30 Q6 — a store network's own batch (`store:hy-vee`, from the
  // file's Network column) reads *Store · Hy-Vee*, as its payments do. The
  // channel is stored lowercased, so each word is capitalised back.
  if (channel.startsWith("store:")) {
    const network = channel
      .slice("store:".length)
      .split(/([\s-]+)/)
      .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
      .join("");
    return t("payments.source.store", { network });
  }
  return channel
    .split(/[_\s]+/)
    .filter((word) => word !== "")
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
    .join(" ");
}

// ── The batch status vocabulary (`bankrec_models.BATCH_STATUSES`) ──────────

/** The four, and only the four. A tenant cannot invent a fifth: the lock
 *  trigger, the matcher and the ledger handoff are all written against these.
 *
 *  ⚠ `matched` means PAIRED with a bank line, not EQUAL to it (`DEF-PAY-10748`,
 *  Payments audit L3-04, PO 2026-10-30). So a matched batch whose difference
 *  is not $0.00 reads *"Matched · off by $566.50"* — DEP-261029-0043, recorded
 *  $266.80, bank $833.30. The gap is shown UNSIGNED: the Difference figure
 *  beside it carries the direction. An unknown difference (`null`) and an
 *  exact $0.00 keep the plain word. A label only — the status is unchanged. */
export function batchStatusLabel(
  status: string,
  t: Translator,
  gap?: { difference: string | null; currency: string; locale?: string },
): string {
  if (
    status === "matched" &&
    gap !== undefined &&
    gap.difference !== null &&
    !isZeroAmount(gap.difference)
  ) {
    const unsigned = gap.difference.replace(/^-/, "");
    return t("payments.deposits.status.matchedOffBy", {
      amount: formatMoney(unsigned, gap.currency, gap.locale),
    });
  }
  return t(`payments.deposits.status.${status}`, { defaultValue: status });
}

export function batchStatusTone(status: string): StatusTone {
  if (status === "reconciled") {
    return "success";
  }
  if (status === "matched") {
    // `neutral`, not a colour of its own: A12 gives StatusPill four tones and
    // "matched" is a resting state — tied to a bank line and waiting for a
    // person, which is neither good news nor a warning.
    return "neutral";
  }
  // `unmatched` is the one that needs a person; `in_transit` is merely waiting.
  return status === "unmatched" ? "danger" : "warning";
}

/** The trail's event names (`bankrec_models.BATCH_EVENTS`) — created ·
 *  regrouped · matched · flagged · resolved · reconciled · unreconciled. */
export function trailEventLabel(event: string, t: Translator): string {
  return t(`payments.deposits.event.${event}`, { defaultValue: event });
}

/** S38 step 2's four states. `matched_off_by` is the prototype's "Off by $100"
 *  and "Fees?" — tied to a batch and still owed an explanation. */
export function matchStateLabel(state: string, t: Translator): string {
  return t(`payments.deposits.match.${state}`, { defaultValue: state });
}

export function matchStateTone(state: string): StatusTone {
  if (state === "auto") {
    return "success";
  }
  // "not in our system" is a fact to note, not a problem to fix — the four
  // A12 tones have no informational blue, so it takes the resting one.
  return state === "not_in_our_system" ? "neutral" : "warning";
}

// ── Money, and the absence of it ──────────────────────────────────────────

/**
 * A served money figure, or a STATED absence with its reason.
 *
 * `reason` is REQUIRED and is a string, not an optional: the type is what makes
 * "render an absence silently" unexpressible, which is the same discipline
 * `financeShared.AbsentFigure` keeps for the ledger's four null figures. A
 * caller cannot get a blank cell out of this component without saying why it is
 * blank.
 *
 * Nothing here formats. `MoneyCell` is the ONE money path in this app
 * (BR-SHL-023) and the display rounding is its own; this component decides only
 * whether there is a figure to hand it.
 */
export function BankFigure(props: {
  amount: string | null;
  currency: string;
  reason: string;
  locale?: string;
}) {
  if (props.amount === null) {
    return (
      <span className="pay-absent" role="note">
        {props.reason}
      </span>
    );
  }
  return <MoneyCell amount={props.amount} currency={props.currency} locale={props.locale} />;
}

/**
 * The sentence for a batch whose bank side is unknown — chosen by STATUS, not
 * by the null, because the two absences the prototype draws are different
 * facts and a clerk acts on them differently.
 *
 *   `in_transit`   the money is on its way; nothing is wrong and nothing is due
 *   anything else  no statement line is tied yet; a person has work to do
 */
export function bankAbsenceReason(status: string, t: Translator): string {
  return status === "in_transit"
    ? t("payments.deposits.bankPending")
    : t("payments.deposits.bankNotMatched");
}

// ── Gap sentences (BR-SHL-020 · TD-16/B8) ─────────────────────────────────

/**
 * The catalogue sentence for one served gap, keyed on the server's stable
 * `code` and NEVER on its English `detail`.
 *
 * The server sends codes and the UI renders language — a screen that printed
 * `detail` would be English-only on a product with eleven catalogues. A code
 * this app has no copy for falls back to a sentence NAMING the code and the BR
 * the server cited, so a new refusal from a backend lane surfaces as itself
 * rather than as a blank.
 */
export function bankRecGapSentence(gap: BankRecGap, t: Translator): string {
  // The EXISTING `payments.problem.*` family, not a parallel one:
  // `paymentsShared.ProblemList` already renders server codes from it, and two
  // catalogues for one vocabulary is how the second one goes stale.
  const copy = t(`payments.problem.${gap.code}`, { defaultValue: "" });
  return copy !== "" ? copy : t("payments.problem.unknown", { code: gap.code, brRef: gap.br_ref });
}

/** Every named gap, rendered. A screen that dropped them would be the comment
 *  that claims a guarantee (hard-won law 1). */
export function GapNotes(props: { gaps: readonly BankRecGap[]; t: Translator }) {
  if (props.gaps.length === 0) {
    return null;
  }
  return (
    <>
      {props.gaps.map((gap) => (
        <p key={gap.code} className="pay-absent" role="note">
          {bankRecGapSentence(gap, props.t)}
        </p>
      ))}
    </>
  );
}

/** `P2.10` — what S37 is holding back, as a NUMBER.
 *
 *  Since phase 0's re-key a deposit batch exists from the moment its till
 *  opens, so the list now serves only BANKABLE batches — the blueprint's own
 *  word, from p059: the batch *"becomes bankable"* at Close and only then
 *  *"appears on Finance → Deposits ready to be matched"*. That gives this
 *  screen a deliberate blind spot, and **hard-won law 7 is explicit that a
 *  declared blind spot with no number attached is indistinguishable from an
 *  empty one**. This is the number.
 *
 *  It is NOT a fifth KPI tile: the four tiles tie to the rows beneath them
 *  (US-PAY-020 TC-2) and this figure by definition does not — it is the money
 *  those rows do not contain.
 *
 *  Rendered NOTHING when the count is zero, because a line reading "$0.00 at 0
 *  open counters" on a utility with no counters is noise every day of the year
 *  (B14 rule 32 — a stated absence is CLOSED by default).
 *
 *  ⚠ A COMPONENT rather than six lines inside `DepositsPage` — B14 rule 43,
 *  ratified after "use it" turned out to mean 120 lines inline in a 4,186-line
 *  page, importable by nothing. `DepositsPage` and its test both mount THIS. */
export function StillOpenCounterNote(props: {
  stillOpen: StillOpenCounters | undefined;
  t: Translator;
  locale?: string;
}) {
  const held = props.stillOpen;
  if (!held || held.batch_count <= 0) {
    return null;
  }
  // BR-SHL-023 — ONE money formatting path. Never a template string of the
  // raw six-decimal wire value, which is how a screen prints `612.500000`.
  const money = formatMoney(held.recorded_total, held.currency, props.locale);
  return (
    <p className="pay-absent" role="note" data-testid="deposits-still-open">
      {props.t("payments.deposits.stillOpen", { count: held.batch_count, money })}
    </p>
  );
}

/* ── THE BATCH LINE'S ACTIONS — `P3.10` ─────────────────────────────────────
 *
 * ⚠ **THIS IS THE SCREEN WHERE A WRONG CHEQUE NUMBER IS FOUND, AND UNTIL NOW
 * THERE WAS NOTHING A CLERK COULD DO ON A LINE.** Finance blueprint p049: the
 * batch detail drew *"three `PlainTable`s … with no toolbar, no pager, no row
 * actions and no empty state"*, and its finding names the three lawful acts
 * that were missing — open the payment, correct the reference, reverse.
 *
 * **WHAT IS RIGHTLY ABSENT STAYS ABSENT.** There is no *edit this line* and no
 * *remove from batch*: a payment inside a cut batch cannot be removed (the
 * day's total would change after the fact) and hard rule 4 forbids editing one.
 * p049 says so in terms — *"Some of that is correct and must stay."*
 *
 * **THE SHAPE IS B14 RULE 15'S — two visible, then `…`** — which is what the
 * drawing draws (`👁 ✎ …`) and what puts the destructive act behind a
 * disclosure. `RowActionsMore` holding one item has precedent in the product
 * (`features/ledger/JournalView.tsx`, the journal's *Delete draft*).
 *
 * **A COMPONENT AND NOT INLINE MARKUP — B14 rule 43**, ratified after *"use
 * it"* turned out to mean 120 lines inside a page, importable by nothing. The
 * page passes three callbacks and this owns the grammar.
 *
 * ⚠ **EVERY REFUSAL HERE MIRRORS ONE THE SERVICE ALREADY MAKES** and none is
 * invented (BR-SHL-025 — a control that cannot act is DISABLED WITH ITS REASON,
 * never hidden):
 *
 *   · **Open** is blocked only when the row has no number AND no id to address,
 *     which is not a state the server serves.
 *   · **Correct the reference** is NEVER blocked by the batch. This is the one
 *     in-place write hard rule 4 allows (PO 2026-09-02) and it permits the
 *     cheque number and the memo *in any status, banked included*. Only the
 *     TENDER is refused once banked — deposit batches group by till × tender —
 *     and that is the form's business, not this cell's.
 *   · **Reverse** is blocked when nothing of the payment still stands, which is
 *     `BR-PAY-884`'s own refusal (*"a customer who pays again after a bounce
 *     makes a NEW payment"*), and when the row is itself a reversing row. **It
 *     is NOT blocked by the lock**: `_refuse_if_batch_locked` deliberately
 *     permits a reversal inside a locked batch, and greying it there would be
 *     this screen contradicting the service.
 */
export function BatchMemberActions(props: {
  member: DepositBatchMember;
  t: Translator;
  /** The signed-in role, or `null` while the read has not answered. */
  role: string | null;
  /** The payment's own address, already tenant-scoped by the caller. */
  openTo: string;
  onCorrect: () => void;
  onReverse: () => void;
}) {
  const { member, t } = props;
  return (
    <RowActions>
      {/* The SAME three labels and the SAME three glyphs the payments list
          draws (`PaymentsPage`'s actions cell). Not a new vocabulary for the
          same three acts: a clerk who learns `✎` on S33 recognises it here,
          which is rule 15's own note and rule 34's reasoning. */}
      <RowActionLink
        label={t("payments.detail.view")}
        icon={<EyeIcon />}
        to={props.openTo}
      />
      <RowAction
        label={t("payments.correct.action")}
        icon={<PencilIcon />}
        onClick={props.onCorrect}
      />
      <RowActionsMore label={t("table.rowActions.more")}>
        <RowMenuAction
          label={t("payments.reverse.action")}
          icon={<RollBackIcon />}
          danger
          reason={memberReverseBlockedReason(member, props.role, t)}
          onClick={props.onReverse}
        />
      </RowActionsMore>
    </RowActions>
  );
}

/**
 * Why this BATCH LINE cannot be reversed, or `null`. Pure, so every branch is
 * provable without a browser.
 *
 * It is `PaymentsPage.reverseBlockedReason`'s three clauses — the role, money
 * that never arrived, a row that is itself a reversal — **plus one that list
 * cannot make**, and the difference is the point. That function's own note
 * says so: *"IT DOES NOT ASK WHETHER THIS PAYMENT WAS ALREADY REVERSED, AND IT
 * CANNOT … `PaymentRow` carries no link to one."* A batch member DOES carry
 * `reversed_amount`, so here the answer is known and `BR-PAY-884`'s refusal —
 * *"nothing of it still stands"* — is stated before the press instead of after
 * it.
 *
 * ⚠ **THE LOCK IS NOT A CLAUSE, DELIBERATELY.** `_refuse_if_batch_locked`
 * permits a reversal inside a locked batch (PO 2026-08-12, OQ-134), so a
 * screen that greyed it there would contradict the service — and it is exactly
 * the case `P3.11` exists to surface.
 *
 * ⚠ **A NULL ROLE OFFERS THE CONTROL**, as on the list: the permissions read
 * may not have answered, and the server is the boundary either way.
 */
export function memberReverseBlockedReason(
  member: DepositBatchMember,
  role: string | null,
  t: Translator,
): string | null {
  if (role !== null && role !== ROLE_SYSTEM_ADMIN) {
    return t("payments.reverse.adminOnly");
  }
  if (member.status === "processing") {
    return t("payments.reverse.notCleared");
  }
  // The decimal string is READ, never parsed — `Number()` on money is the float
  // hard rule 2 keeps out, in one of the places it is most tempting.
  if (member.status === "reversed" || (member.amount ?? "").trim().startsWith("-")) {
    return t("payments.reverse.isReversal");
  }
  if (isZeroAmount(stillStandsOf(member.amount, member.reversed_amount))) {
    return t("payments.reverse.nothingStands");
  }
  return null;
}

/**
 * What a member payment STILL STANDS FOR — its amount less what has come back.
 * `null` when either figure is missing or unreadable, which is *we do not
 * know* and is never collapsed to zero by a caller.
 *
 * `BR-PAY-884`: *"the sum of all reversals against one payment may never
 * exceed it"*, so this reaches zero and stops.
 */
export function stillStandsOf(
  amount: string | null,
  reversedAmount: string | null,
): string | null {
  return residualOf(amount, reversedAmount === null ? [] : [reversedAmount]);
}

// ── Failure shapes ────────────────────────────────────────────────────────

/** A COLLECTION route that answers 404 does not exist — the batch list answers
 *  200-with-zero-rows when a tenant has banked nothing. DERIVED from the
 *  response rather than declared, so nothing here has to be edited if a route
 *  moves, and a constant reading `BANKREC_API = true` would be a comment
 *  claiming a fact about another file. */
export function bankRecRouteAbsent(error: unknown): boolean {
  return isApiError(error) && error.status === 404;
}

// ── Exact decimal comparison (CLAUDE.md rule 2 — never a float) ────────────

const DECIMAL_RE = /^-?\d+(\.\d+)?$/;
const SCALE = 6; // NUMERIC(18,6) — the storage grid, and the wire's own

/**
 * A decimal STRING as an exact scaled BigInt, or null when it is not one.
 *
 * S40 needs to know whether the explanations sum to the difference BEFORE it
 * lets a clerk press Reconcile — the server refuses a residual either way, but
 * a form that only discovers this on submit wastes the round trip and reads as
 * a bug. `Number("9758.11") - Number("8154.50")` is `1603.6100000000005821`,
 * which is the shape of every money defect this repo has logged; scaling to six
 * decimal places of integer is exact for anything the database can hold.
 *
 * ⚠ **THIS CITED THE CARD DAY'S PAIR UNTIL 2026-09-24 AND THAT PAIR IS EXACT**
 * (`DEF-PAY-6650`) — `5120.40 - 4972.90` really is `147.5` here. The hazard is
 * real; it simply does not land on those two numbers, and a comment nothing
 * re-runs is how a figure like that survives three files.
 *
 * Nothing here rounds and nothing here FORMATS — the result never reaches a
 * screen as text, only as a comparison (BR-SHL-023 keeps `MoneyCell` the one
 * formatter).
 */
export function scaledDecimal(value: string): bigint | null {
  const text = value.trim();
  if (!DECIMAL_RE.test(text)) {
    return null;
  }
  const negative = text.startsWith("-");
  const [whole, fraction = ""] = (negative ? text.slice(1) : text).split(".");
  const scaled = BigInt(whole + fraction.padEnd(SCALE, "0").slice(0, SCALE));
  return negative ? -scaled : scaled;
}

/**
 * Σ of the explanations, exactly, or null when any of them is unreadable.
 *
 * Null rather than "skip the bad one": a total that silently dropped one
 * explanation would be a smaller number wearing the right label, and the clerk
 * would be told a difference was fully explained when it was not.
 */
export function sumScaled(values: readonly string[]): bigint | null {
  let total = 0n;
  for (const value of values) {
    const scaled = scaledDecimal(value);
    if (scaled === null) {
      return null;
    }
    total += scaled;
  }
  return total;
}

/**
 * Does this set of explanations account for the whole difference?
 *
 * US-PAY-022 §7, verbatim: *"Σ reason-coded explanations + Σ member
 * corrections = difference, then difference = 0 at reconcile."* Computed here
 * only so the form can say so before the round trip — **the SERVER's tie-out is
 * the enforcement** (`reconcile_batch` refuses anything else, and BR-PAY-035
 * left no bypass), and this is never treated as permission.
 */
export function explainsTheDifference(
  difference: string | null,
  amounts: readonly string[],
): boolean {
  if (difference === null) {
    return false;
  }
  const target = scaledDecimal(difference);
  const explained = sumScaled(amounts);
  return target !== null && explained !== null && target === explained;
}

/** A batch row's own difference, for a screen that wants it as text. Returns
 *  null when the bank has not spoken — the caller then renders `BankFigure`'s
 *  absence rather than a computed zero. */
export function differenceOf(row: DepositBatchRow): string | null {
  return row.difference;
}

/**
 * A scaled integer back to the decimal string the wire and `MoneyCell` speak.
 *
 * The inverse of `scaledDecimal`, and it is written here rather than borrowed
 * so the pair cannot drift: a residual that round-trips through a different
 * scale is a figure that disagrees with the comparison it came from.
 */
function unscaled(value: bigint): string {
  const negative = value < 0n;
  const digits = (negative ? -value : value).toString().padStart(SCALE + 1, "0");
  const body = `${digits.slice(0, digits.length - SCALE)}.${digits.slice(digits.length - SCALE)}`;
  return negative ? `-${body}` : body;
}

/**
 * **THE RESIDUAL — `P3.12`.** The difference, less what has been explained so
 * far. `null` when the bank has not spoken or any amount is unreadable.
 *
 * p055 draws it as the third line of the trio and enables `Record ✓` only at
 * `$0.00`. The arithmetic is exact `BigInt` on the `NUMERIC(18,6)` grid —
 * `Number("-172.50") - Number("-147.50")` is `-25.000000000000004`, and a
 * residual that never quite reaches zero is a button that never enables.
 *
 * ⚠ **`null` IS NOT ZERO AND A CALLER MUST NOT COLLAPSE IT.** An unreadable
 * amount means *we do not know what is left*, and rendering that as `$0.00`
 * would be the one state where a plausible zero opens the commit.
 */
export function residualOf(
  difference: string | null,
  amounts: readonly string[],
): string | null {
  if (difference === null) {
    return null;
  }
  const target = scaledDecimal(difference);
  const explained = sumScaled(amounts);
  if (target === null || explained === null) {
    return null;
  }
  return unscaled(target - explained);
}

/**
 * **THE DRIFT — `P3.11`.** What the members still stand for, less the total
 * frozen at the cut. `null` when either figure is missing or unreadable, and
 * `"0.000000"` when they agree.
 *
 * A reversal inside a LOCKED batch is lawful (`_refuse_if_batch_locked` permits
 * it — *"the bank statement the batch was agreed against did not change"*), so
 * these two legitimately part company and the blueprint's answer is to SAY SO
 * rather than to move either one. **Nothing here changes a rule**; `live_total`
 * is served and `recorded_total` is frozen, and this only subtracts them.
 *
 * ⚠ **IT TAKES THE SERVED `live_total` AND NEVER RE-DERIVES IT FROM `members`
 * (`DEF-PAY-6651`).** A reversing row carries no `deposit_batch_id` and the
 * original's amount and status may not move, so Σ`members[].amount` is
 * identically `recorded_total` and a drift computed that way is always zero —
 * on a batch that is short.
 */
export function driftOf(recordedTotal: string | null, liveTotal: string | null): string | null {
  if (recordedTotal === null || liveTotal === null) {
    return null;
  }
  const recorded = scaledDecimal(recordedTotal);
  const live = scaledDecimal(liveTotal);
  if (recorded === null || live === null) {
    return null;
  }
  return unscaled(live - recorded);
}

/**
 * Σ of a set of decimal amounts, exactly, or `null` when any of them is
 * unreadable — never a partial total wearing the whole label.
 *
 * `sumScaled` already does the arithmetic; this returns it as the string the
 * wire and `MoneyCell` speak, so the *Explained* line and the residual beneath
 * it are two views of ONE calculation rather than two calculations.
 */
export function sumOf(amounts: readonly string[]): string | null {
  const total = sumScaled(amounts);
  return total === null ? null : unscaled(total);
}

/** Is this decimal string exactly zero? `null` (unknown) is NOT zero. */
export function isZeroAmount(amount: string | null): boolean {
  if (amount === null) {
    return false;
  }
  const scaled = scaledDecimal(amount);
  return scaled !== null && scaled === 0n;
}

/**
 * A wire amount as a form INPUT's initial value — exact, and without the
 * padding zeros the NUMERIC(18,6) grid carries.
 *
 * `-147.500000` becomes `-147.50`. This is NOT rounding and it is not the
 * display formatter: `MoneyCell` owns display (BR-SHL-023) and this value goes
 * back to the SERVER, where it meets a tie-out that compares it to the
 * difference exactly. So only genuine TRAILING ZEROS are removed — `-147.505000`
 * becomes `-147.505` and keeps every digit that means something, and at least
 * two decimal places are always left so a money field never reads as a whole
 * number a clerk has to check.
 *
 * It exists because S40 pre-fills the difference, and a form that opened
 * showing `-147.500000` made a clerk wonder whether the extra digits mattered.
 * Seen on the running app; a unit test would never have asked.
 */
export function amountForInput(amount: string): string {
  if (!DECIMAL_RE.test(amount) || !amount.includes(".")) {
    return amount;
  }
  const trimmed = amount.replace(/0+$/, "");
  const [whole, fraction = ""] = trimmed.split(".");
  return `${whole}.${fraction.padEnd(2, "0")}`;
}

// ── Lifecycle ─────────────────────────────────────────────
// packet: US-PAY-020@5b2e814 (story+rules snapshot — EP-PAY-06 US-PAY-020 lead; co-packets US-PAY-021, US-PAY-022, US-PAY-023, same epic; 08-payments/02-business-rules.md BR-PAY-004/019/025/035/040; 05-prototype/UtilityBilling.html lines 3802-3830, 4021-4090, 5568-5600)
// generated: 2026-08-16 by story-coder (payments SURFACE lane — the screens a complete bank-rec engine had never had)
// checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-09)
// gates: tsc✔ · eslint --max-warnings 0✔ · vitest✔ · vite build✔ · run_gates✔ (G13 unwired-props, G15 i18n-parity, G18 i18n call sites)
// exceptions: (1) `BankFigure.reason` is REQUIRED rather than optional on purpose — an optional reason is exactly how a plausible zero gets rendered, and this family's whole job is that a batch the bank has not shown never reads as one it matched to the penny · (2) "Force match anyway" is NOT drawn and NOT disabled — BR-PAY-035 made it permanently superseded and the server has no path that would honour it, so a disabled control would imply the feature exists · (3) no GL-account NUMBER is written anywhere in this module; the prototype's 6200/1020 are in no signed chart (DEF-067) and the fee account is resolved by DESIGNATION server-side · (4) `explainsTheDifference` computes on BigInt over the NUMERIC(18,6) grid and is used ONLY to tell a clerk early — the server's tie-out is the enforcement and this is never treated as permission
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
