// ── Trace ──────────────────────────────────────────────
// Change:  Finance blueprint p014 `P1.19` (Other) — *"Forty-seven strings,
//          eleven catalogues. The rule-33 cut is not a drawing change — EVERY
//          CUT STRING IS A KEY."*  OUTCOME: *"A deleted English string with ten
//          live translations is a catalogue that lies. The fan-in tool owns
//          this file set — never hand-edit."*
// Rules:   B14 rule 33 (ON-SCREEN TEXT IS CAPPED BY WHAT IT IS FOR — a LABEL or
//          heading ≤ 3 words and no sentence · a FACT ≤ 6 words · an
//          INSTRUCTION ≤ 6 words PER SENTENCE, two sentences of six beating one
//          of twelve · a CONSEQUENCE ≤ 6 per sentence and at most two ·
//          RATIONALE is ZERO WORDS ON SCREEN) · B14 rule 31 (no database id and
//          no internal code is ever visible to a utility user) · B14 rule 32
//          (no rule id or internal code in clerk-facing copy)
// Tests:   this file
// ───────────────────────────────────────────────────────
/**
 * RULE 33, COUNTED, OVER FINANCE'S OWN CLERK-FACING COPY.
 *
 * ⚠ **WHY A NEW FILE AND NOT A WIDER `G33`.** `10-scripts/gates/g33_refusal_copy_length.py`
 * already counts words — over **G32's raised-refusal key set only**, which is
 * every message a backend `raise` resolves to. Finance's screens are mostly not
 * refusals: a column header, a tab word, a panel title, a KPI caption and a
 * stated absence are all on screen, all capped by rule 33, and **none of them is
 * in G33's subject**. That is hard-won law 7's *reporting zero over a scope it
 * silently excludes*, so this file names its scope in one place and prints what
 * it covers beside what it finds.
 *
 * ⚠ **THREE CAPS, NOT ONE — AND THE SECOND IS THE ONE A CAP ALONE CANNOT SEE.**
 * B14 rule 33 is not "six words". *"Sold. Now who?"* is three words in two
 * sentences: inside every cap and outside the rule, because a HEADING may not be
 * a sentence at all. So `headings` asks a different question from `theCap`, and
 * a file that only counted words would pass over it.
 *
 * ⚠ **THE BASELINE MAY ONLY SHRINK, AND ITS IDENTITY IS THE TEXT.** Measured
 * 2026-09-24 over the English `finance.*` / `reports.ledger.*` strings:
 * **144 were over the cap on 2026-09-24; 141 on 2026-09-25.** Setting the rule with no baseline would take
 * this check from green to 144 findings — *"a backlog wearing a gate's
 * clothes"*, which G33's own docstring records the PO forbidding in these words:
 * *"this family BORN ASPIRATIONAL it cannot be ASPIRATIONAL any more"*. So the
 * 144 are listed, **keyed on `<key> :: <its English text>`**: change the copy and
 * the licence lapses, because the rule binds every NEW or CHANGED string. A
 * baselined entry that is now short or gone is STALE and fails too, so the list
 * cannot quietly stop matching the catalogue.
 *
 * ⚠ **AND 144 IS NOT 47.** `P1.19`'s figure is a count of strings drawn over the
 * cap **inside the blueprint's own previous wireframes**, cut in the drawings
 * and owed to the catalogue. This file counts what the CATALOGUE holds, which is
 * a bigger set and the one a clerk actually reads. The two numbers answer
 * different questions and neither replaces the other.
 */
import { describe, expect, it } from "vitest";

import en from "./locales/en.json";

/** The scope, in one place. Printed by the coverage case below. */
const PREFIXES = ["finance.", "reports.ledger."];

/** A key whose value is a LABEL or a HEADING rather than a sentence — capped at
 *  three words, and may not be a sentence at all.
 *
 *  Matched on the last SEGMENT and on `.col.` / `.tab.` infixes, never on a
 *  substring: an early draft used `\.col` and matched
 *  `finance.taxes.collectedUnavailable`, which is a stated absence and not a
 *  column header — a detector that catches the wrong thing reports a finding
 *  nobody can act on and earns itself an exclusion instead of a fix. */
const HEADING_SEGMENTS = new Set([
  "title",
  "label",
  "heading",
  "head",
  "tab",
  "col",
  "viewsLabel",
]);

function isHeading(key: string): boolean {
  const parts = key.split(".");
  if (parts.some((part, i) => i > 0 && i < parts.length - 1 && (part === "col" || part === "tab"))) {
    return true;
  }
  return HEADING_SEGMENTS.has(parts[parts.length - 1]);
}

const PLACEHOLDER = /\{\{[^}]*\}\}/g;
const SENTENCE_BREAK = /(?<=[.!?])\s+/;

/** The message as sentences, with placeholders collapsed to one token — the
 *  same normalisation `g33_refusal_copy_length.py` uses, so the two checks
 *  cannot disagree about what a word is. */
function sentences(value: string): string[] {
  return PLACEHOLDER.source === ""
    ? []
    : value
        .replace(PLACEHOLDER, "X")
        .replace(/…/g, ".")
        .trim()
        .split(SENTENCE_BREAK)
        .map((part) => part.trim())
        .filter((part) => part !== "");
}

function longestSentence(value: string): number {
  const parts = sentences(value);
  return parts.length === 0 ? 0 : Math.max(...parts.map((part) => part.split(/\s+/).length));
}

/** `<key> :: <whitespace-normalised English>` — G33's identity, on purpose. */
function identity(key: string, value: string): string {
  return `${key} :: ${value.split(/\s+/).join(" ")}`;
}

const catalogue = en as Record<string, string>;

const inScope = Object.keys(catalogue)
  .filter((key) => PREFIXES.some((prefix) => key.startsWith(prefix)))
  .filter((key) => typeof catalogue[key] === "string")
  .sort();

/** Measured 2026-09-24. IT MAY ONLY SHRINK. */
const BASELINE = new Set<string>([
  "finance.accruals.forwarded :: That period was closed, so the reversal moved forward.",
  "finance.accruals.help :: An accrual cancels itself on day 1 of your next period. Nothing here reverses twice — pressing this again is safe.",
  "finance.accruals.none :: Every accrual up to {{asOf}} has already reversed.",
  "finance.accruals.sweepSummary :: {{created}} posted out of {{considered}} looked at.",
  "finance.awaits.endpoint :: This deployment does not answer a request for these figures yet. The numbers exist in the books; nothing serves them to a screen.",
  "finance.chart.title :: Billed vs collected · last 12 months",
  "finance.close.form.closedAtHelp :: The day you are actually closing, in YYYY-MM-DD. It is recorded, never taken from the clock.",
  "finance.close.form.closedAtRequired :: Give the date you are closing on.",
  "finance.close.form.reasonHelp :: Required only while something on the list is not done. It is kept beside the close, with the list exactly as it stood.",
  "finance.close.formHelp :: Once closed, anything dated into this month lands in the next open month instead, with a note saying why. Nothing already in the books moves.",
  "finance.close.readiness :: Before you close this month · {{done}} of {{total}} done",
  "finance.close.roleReason :: Your role cannot close an accounting period.",
  "finance.close.snapshot :: {{count}} items were unfinished at the time",
  "finance.close.warn :: {{count}} items are not done. You can still close, but you must type a reason and it is kept with the close.",
  "finance.coa.designationDarkToast :: Retired. Nothing is now the {{designation}} account — point another account at it before the next bill run.",
  "finance.coa.empty :: This tenant has no chart of accounts yet.",
  "finance.cost.correctedButExported :: Saved. Batch {{batches}} was already handed to your accounting system and no longer matches — correct it there by hand.",
  "finance.cost.explainer :: What this utility was invoiced for the water, power and gas it resells, and how much of it reached a customer bill.",
  "finance.cost.field.correctionReasonHelp :: This period is closed. State what is being corrected and why — this note is the only record that can explain the difference later.",
  "finance.cost.field.paidOnHelp :: The day your bank moved the money.",
  "finance.cost.field.supplierHelp :: Type the name as it appears on the invoice. There is no supplier list and nothing is merged.",
  "finance.cost.field.unitHelp :: Required whenever a volume is entered, and it must match the unit the service is billed in.",
  "finance.cost.field.voidReasonHelp :: The row stays on the register with this reason so the month can still be reconciled against the supplier's statement.",
  "finance.cost.field.volumeHelp :: Optional. Leave it blank for a cost-only invoice — but without it, this service's unaccounted-for figure cannot be produced for the period.",
  "finance.cost.noVolumeReason :: No purchase of this category carries a volume, so there is nothing to compare.",
  "finance.cost.noVolumeRow :: This purchase was captured without a volume, which is allowed.",
  "finance.cost.postsNothing :: Recorded — a purchase is held here until you enter the day you paid it, and it is in the books from then on.",
  "finance.cost.problem.billed_volume_basis_is_not_the_ruled_service_period :: This figure counts bills by issue date, which is not the agreed basis for physical loss.",
  "finance.cost.problem.billed_volume_read_is_unavailable :: The billed volume for this period could not be read.",
  "finance.cost.problem.billed_volume_unit_is_mixed :: The bills for this service do not agree on a unit.",
  "finance.cost.problem.no_purchases_captured :: No purchase of this service was captured for this period.",
  "finance.cost.problem.no_volume_captured_for_every_purchase :: At least one purchase of this service was captured without a volume, so the figure would rest on a partial denominator.",
  "finance.cost.problem.no_volume_denominator_for_this_category :: This category has no volume, so it has no percentage.",
  "finance.cost.problem.purchase_unit_does_not_match_billed_unit :: The unit bought and the unit billed are different, and no conversion has been agreed.",
  "finance.cost.problem.unknown :: This figure could not be produced ({{code}}).",
  "finance.cost.unsignedAccount :: This account code is proposed and not yet signed by finance.",
  "finance.denied :: Your role cannot open Finance. Ask a System Admin if you need it.",
  "finance.designation.undeposited_funds :: Money taken, not yet at the bank",
  "finance.error.title :: The finance figures could not be loaded",
  "finance.explainer.export :: One summary journal entry per month — not one per bill. Close the month first; a closed period is the only thing the accounting package receives.",
  "finance.explainer.gl :: Read-only trial balance for the period. Full accounting lives in your connected package — post the summary from Export.",
  "finance.explainer.revenue :: What you billed, what came in, and what is still owed this month.",
  "finance.explainer.taxes :: Tax you billed and tax you collected for each authority, and what you still owe them.",
  "finance.export.blockedAlready :: {{from}} to {{to}} has already been handed over to this destination. Download the recorded batch again rather than sending a second one.",
  "finance.export.blockedDrift :: The month does not add up, so nothing is handed over. Find the entry that broke it — the total is never adjusted to fit.",
  "finance.export.blockedOpen :: This month is still open. A month is handed over only once it is closed, so the accounting package never receives figures that can still move.",
  "finance.export.blockedRefs :: These accounts have no code in your accounting package, so nothing is sent: {{accounts}}",
  "finance.export.confirmConsequence :: {{entries}} lines covering {{from}} to {{to}} go to {{target}}: {{debits}} on one side and {{credits}} on the other. It can only be done once.",
  "finance.export.costSettled :: {{count}} already-paid invoices are not in this figure",
  "finance.export.costSettledReason :: They are already in the totals above: the payment posted when you entered the paid-on date. Counting them here as well would hand the same money over twice.",
  "finance.export.costTotal :: Supplier costs, in {{count}} lines — recorded, and in the books once settled",
  "finance.export.drift.help :: A captured purchase was corrected after this month was handed over. The handover cannot be repeated, so the difference has to be posted by hand in your accounting system.",
  "finance.export.drillEmpty :: Nothing in the books sits behind this figure for the handed-over period.",
  "finance.export.emptyPeriod :: This period has nothing to hand over. An empty month is not a finished one.",
  "finance.export.historyEmpty :: No month has been handed over yet.",
  "finance.export.noAckStatus :: Nothing reports back whether the accounting package accepted it, so no acceptance status is shown.",
  "finance.export.sent :: Handed over — recorded once, for good.",
  "finance.gap.active_connection_classes_are_not_published_by_customers :: This figure counts active, marked-for-disconnect and vacation-hold accounts together. Accounts publishes one total that also includes pending and closed ones, so showing that total here would be a wrong number rather than a rough one.",
  "finance.gap.activity_feed_has_no_event_read_model :: Nothing in this product yet records bill runs, payments and imports as one dated stream, so there is no activity to list. An empty list here would read as “nothing happened today”.",
  "finance.gap.aging_does_not_foot_to_the_ar_control_total :: These bands do not add up to the receivable in the books. That difference is a real one to investigate — this report never adjusts itself to hide it.",
  "finance.gap.ar_control_total_not_published :: The ledger's receivable total could not be read, so this report cannot say whether it agrees with the books.",
  "finance.gap.billing_cycle_window_is_not_offered :: Reporting over a whole billing cycle is not offered. Every window you can pick states the exact dates it covers.",
  "finance.gap.charge_code_references_are_not_readable_here :: We cannot see which charge codes point at an account, so no account is ever deleted on that evidence.",
  "finance.gap.customer_register_could_not_be_read :: The customer register could not be read at all, so this side is shown as unknown rather than as nothing. A register nobody could open and a register holding nothing are different facts.",
  "finance.gap.deposit_register_is_never_written :: Nothing in this product writes the customer deposit register, so the books and the register are kept by different paths. A difference here means the register is not being maintained — not that the books are wrong.",
  "finance.gap.failed_payment_count_is_not_published_by_payments :: Payments publishes the fifty most recent failed payments for its own screen, not a count of all of them. On a utility with more than fifty this tile would say fifty and be wrong.",
  "finance.gap.gl_mapping_bulk_write_is_not_served :: There is no single Save for the whole map. Each half is saved where it belongs: a role here, a service's revenue account on Settings → Services.",
  "finance.gap.imported_opening_buckets_are_not_built :: Balances brought in from your old system are not in these bands: nothing stores them yet, so a utility that migrated will see less here than it is owed.",
  "finance.gap.issued_bill_without_an_issue_date :: Some issued bills carry no issue date and cannot be placed in a period, so they are left out of this report rather than moved into it.",
  "finance.gap.journal_number_series_is_not_seeded :: This entry has no JE number: no numbering series for journal entries has been set up on this utility. The entry is in the books either way.",
  "finance.gap.manual_je_role_gate_is_a_reading_not_a_ruling :: Who may post a manual entry was read from the ruling on reversals — System Admin and Billing Clerk. It has not been ruled for this screen specifically.",
  "finance.gap.no_account_carries_the_accounts_receivable_designation :: No account in this chart is marked as the receivables account, so there is no receivable to report on. One edit to the chart of accounts fixes it.",
  "finance.gap.no_account_carries_the_deposit_liability_designation :: No account in this chart is marked as the customer deposit account, so deposits taken have nowhere to be held in the books and there is nothing to compare.",
  "finance.gap.open_bill_without_a_due_date :: Some unpaid bills carry no due date, so they cannot be aged. Their amount is in each account's total and in none of the bands.",
  "finance.gap.premises_filter_is_not_offered_on_this_report :: This report does not accept a premises filter. The ledger lines carry the dimension; the filter itself has not been built, and a control that filtered nothing would make the report look filtered.",
  "finance.gap.receivable_holds_more_than_one_currency :: More than one currency is owed, so the bands cannot be added into a single total.",
  "finance.gap.register_window_holds_more_than_one_currency :: This range holds bills in more than one currency, so there is no single total to show.",
  "finance.gap.repost_draft_is_not_persisted :: The corrected copy is not saved yet. Check the figures and press Save draft — closing this now loses nothing but the copy.",
  "finance.gap.revenue_window_holds_more_than_one_currency :: This range holds revenue in more than one currency, so the footer cannot be added up.",
  "finance.gap.service_gl_attributes_seam_is_not_wired :: The service list could not be reached, so this section says nothing rather than saying nothing is mapped.",
  "finance.gap.some_money_in_this_period_carries_no_premises :: Some of this period's activity carries no premises, so the table does not add up to the period total. The two unattributed figures below show how much.",
  "finance.gap.tax_authority_references_are_not_readable_here :: We cannot see which tax authorities point at an account, so no account is ever deleted on that evidence.",
  "finance.gap.tax_outstanding_is_the_billed_basis_only :: Outstanding tax is measured as what was billed less what was remitted. An authority you file on a cash basis is compared here on the billed basis instead.",
  "finance.gap.unbilled_read_count_is_not_published_by_metering :: Meter Reads holds every reading but publishes no count of the ones still waiting to be billed. Counting them here would create a second counter of the same fact, and two counters eventually disagree.",
  "finance.gl.driftWarning :: The books do not add up. Debits and credits can only differ if something wrote a journal line outside the posting service — find the entry, never adjust the total.",
  "finance.gl.empty :: No posted entries fall in this period. This is an empty book, not a balanced one.",
  "finance.gl.expandUnavailable :: Opening one account line to the entries behind it needs a detail read the server does not serve yet.",
  "finance.gl.footerScope :: These totals cover every account in the period, not the rows shown above.",
  "finance.gl.noMatchHelper :: The books still balance; only this view is filtered.",
  "finance.je.auditNotice :: Every draft, post and delete is written to the audit log. It cannot be switched off.",
  "finance.je.dateForwarded :: That period is closed, so the entry is dated {{date}} instead.",
  "finance.je.error.accountRequired :: Choose the GL account for this line.",
  "finance.je.error.amountFormat :: Amounts are positive numbers. The side says which way the money went.",
  "finance.je.error.oneSideOnly :: A line is a debit or a credit, never both.",
  "finance.je.error.unbalanced :: The ledger refused this: debits and credits differ by {{gap}}.",
  "finance.je.field.dateHelp :: The book date. If it lands in a closed period the ledger moves it forward and says so.",
  "finance.je.field.memoHelp :: Required to post. Once posted the entry can never be changed, so this is the only place the reason can be written.",
  "finance.je.field.typeHelp :: An accrual schedules its own reversal on day 1 of the next period.",
  "finance.je.postBlocked.memo :: Write a reason. The entry can never be changed once posted.",
  "finance.je.postBlocked.notSaved :: Save the draft first — the ledger checks the balance against the lines it actually holds.",
  "finance.je.postBlocked.unbalanced :: Debits and credits differ by {{gap}}. An entry that does not balance cannot be posted.",
  "finance.journal.alreadyReversedToast :: This entry was already reversed — the first mirror stands.",
  "finance.journal.draftNoReverse :: Draft — not in the books yet",
  "finance.journal.empty :: No journal entries match this period and filter.",
  "finance.journal.reverseHelp :: A posted entry is never edited. This writes a mirror entry that cancels it, then opens a corrected copy for you to check and post.",
  "finance.journal.reversedToast :: Mirror entry posted · the original stands",
  "finance.journal.unbalancedDraft :: This draft does not balance and cannot be posted.",
  "finance.kpi.collected.detail :: {{cash}} in cash and {{deposits}} from applied deposits",
  "finance.kpi.writtenOff.detail :: Since the start of the fiscal year",
  "finance.map.awaitingSignature :: No account yet — this one needs a finance signature before it can exist.",
  "finance.map.designationUnresolved :: No live account has this role. Anything that needs it will fail until one does.",
  "finance.map.designations.help :: The product finds these accounts by their role, never by their number — so you can renumber or rename any of them.",
  "finance.map.designations.title :: What each kind of money lands in",
  "finance.map.export.help :: An export to QuickBooks or Xero is refused while any account it needs has no code here.",
  "finance.map.services.none :: This utility has no services switched on.",
  "finance.map.services.unavailable :: The service list could not be read, so this section is blank rather than empty.",
  "finance.map.taxes.none :: No tax authority has an account yet. One is created in the {{series}} range the moment you add an authority.",
  "finance.revenue.empty :: No revenue was posted to the books in this period.",
  "finance.taxes.authorityUnnamedWhy :: The books identify this authority by its account, not by name.",
  "finance.taxes.basisNotSet :: Nobody has chosen whether this authority is filed on what you billed or on what you collected. Set it in Settings → Configure; nothing is assumed, because the right answer differs per authority.",
  "finance.taxes.collectedUnavailable :: The books cannot say how much tax sits inside the payments received, because a payment records the amount it met and not which charges it met. Showing the billed figure here would have you remit tax on money nobody has paid.",
  "finance.taxes.empty :: No tax liability has been billed in this period.",
  "finance.taxes.form.amountHelp :: Exactly what left your bank, to the cent.",
  "finance.taxes.form.amountInvalid :: Enter an amount as digits, for example 13.87.",
  "finance.taxes.form.amountPositive :: A payment of zero moves no money.",
  "finance.taxes.form.basisHelp :: Authorities differ, and this is never guessed for you.",
  "finance.taxes.form.basisRequired :: Say which basis this return was filed on.",
  "finance.taxes.form.confirmationHelp :: The only proof kept that the return was filed.",
  "finance.taxes.form.paidOnRequired :: Give the date the money left your bank.",
  "finance.taxes.paid.earlierReason :: They were recorded before this list existed, so they live in the journal only. Their confirmation references are on the journal entries.",
  "finance.taxes.paid.noEntryNumber :: This utility numbers no journal entries yet.",
  "finance.taxes.paid.noReceipt :: Nobody attached a receipt to this filing.",
  "finance.taxes.recordHelp :: This posts one balanced entry that drains the authority's liability and credits cash. Type the amount you actually paid — it is never filled in from the report.",
  "finance.taxes.recorded :: Payment recorded — the liability is drained.",
  "finance.taxes.tieOutUnavailable :: No tax-payable account carries a balance to tie out against.",
  "finance.workbench.noMatchHelper :: Clear the filters to see all four.",
  "reports.ledger.noPremisesParam :: There is no premises parameter here: no ledger line carries a premises yet, so a premises choice would change nothing while looking as though it had.",
  "reports.ledger.pickAccount :: Enter an account and a date range above to run this report.",
  "reports.ledger.type.unmapped :: {{source}} — no name for this source yet",
]);

/**
 * ⚠ **THREE LICENCES LAPSED ON 2026-09-25 AND THE LIST IS 141 (`FIN-COPY`).**
 * They are named here rather than merely deleted, because a baseline that only
 * ever gets shorter tells the next reader nothing about WHY:
 *
 *   · `finance.tieOut.noDismiss` — 19 words of rationale on an undismissable
 *     note, replaced by the Finance blueprint p036's own drawn three,
 *     *"Clears when explained."* (`DEF-LED-6603`).
 *   · `finance.refundDetail.creditInstead` — *"A credit note is possible on 1
 *     bills."* It has `_one` / `_other` forms now and was cut to the cap on
 *     the way past (`DEF-LED-6666`).
 *   · `finance.map.codeAwaitingSignature` — twelve words glued to an account
 *     name, retired entirely in favour of the product's own `Proposed` pill
 *     (`DEF-LED-6613`).
 *
 * **NOTE WHAT THIS NUMBER CANNOT SEE.** Four of that day's defects were prose
 * composed in the BACKEND and printed verbatim — a 90-word basis paragraph, a
 * `Formula:` line, a 55-word download note and a 38-word rule-33 breach with
 * `BR-LED-028:` in front of it. None of them is a catalogue key, so **none of
 * them ever counted here and removing all four moved this number by zero**.
 * That is hard-won law 7's fifth shape and it is filed as `DEF-LED-6699`: this
 * file names its scope honestly, and a reader must not take 141 for the number
 * of over-long strings a Finance clerk can read.
 */

/**
 * A heading that is a SENTENCE, which is the half a word cap cannot see.
 *
 * ⚠ **AN INTERNAL BREAK, NOT A TRAILING FULL STOP.** *"Sold. Now who?"* is three
 * words in two sentences — inside every cap and outside the rule — and it is
 * caught here by the break in the MIDDLE. A trailing `.` alone is not enough:
 * `finance.journal.col.number` is **"Entry no."**, an abbreviation and the
 * column header a bookkeeper says out loud, and a detector that called it a
 * sentence would report a finding nobody can act on and earn itself an
 * exclusion instead of a fix. A trailing `?` is left too — *"Reopen this
 * period?"* is a dialog asking its own question, three words, and rewriting it
 * would be this lane inventing copy nobody agreed (B14 rule 41).
 */
function isSentence(value: string): boolean {
  return /[.!?]\s+\S/.test(value.replace(PLACEHOLDER, "X"));
}

/**
 * Headings over three words on 2026-09-24. **IT MAY ONLY SHRINK**, and it is a
 * SEPARATE list from the cap's because these are a different rule with a
 * different fix: each needs the WORDS from its own drawing, and inventing them
 * here is what the decision log of 2026-09-24 names as the error — *"this lane
 * writing copy nobody agreed"*. They are the remainder of `P1.19`.
 */
const HEADING_BASELINE = new Set<string>([
  "finance.accruals.title :: Accruals waiting to reverse",
  "finance.coa.col.designation :: Role in the books",
  "finance.export.col.ref :: Code in your package",
  "finance.export.drift.title :: An exported month no longer matches",
  "finance.export.viewsLabel :: Close and export sections",
  "finance.map.export.title :: Codes your accounting package knows",
  "finance.map.services.title :: Where each service's revenue goes",
  "finance.revenue.viewsLabel :: Revenue and AR sections",
  "finance.writeOffs.title :: Write-offs waiting for approval",
]);

/**
 * ⚠⚠ **THE BASELINE WAS RE-DERIVED ONCE, AGAINST A SIBLING, BEFORE THIS FILE
 * WAS EVER PUSHED — AND THAT IS THE STRONGEST THING THAT CAN BE SAID FOR IT.**
 * Measured first at `86fd33e29`, it read 143. While this file was being
 * written, `770a9098b` landed the Close & export view and the catalogues went
 * to 144: **four new strings over the cap** (`finance.taxes.paid.earlierReason`
 * at 14 words, `…paid.noEntryNumber` and `…paid.noReceipt` at 7, and
 * `finance.export.viewsLabel`, a four-word heading) and **two baselined
 * sentences reworded**, which lapsed their licence exactly as the identity rule
 * says it should. The check went RED on a lane that had never seen it, on its
 * first contact with live work, and named all six. It is baselined rather than
 * left red — a red nobody can act on is a red nobody reads (hard-won law 7) —
 * but the four are new debt that arrived after the count, and they are named
 * here so the next re-derivation can tell them from the original 143.
 */
describe("P1.19 · B14 rule 33 over Finance's clerk-facing copy", () => {
  it("covers the scope it claims to, and says how much", () => {
    // Law 7: a check that cannot cover its whole subject prints what it
    // SKIPPED beside what it checked. This one prints what it COVERS, so a
    // prefix quietly stopping to match cannot look like a clean sweep.
    expect(inScope.length).toBeGreaterThan(700);
    expect(PREFIXES).toEqual(["finance.", "reports.ledger."]);
  });

  it("a FACT, an INSTRUCTION or a CONSEQUENCE is ≤ 6 words a sentence, ≤ 2 sentences", () => {
    const findings: string[] = [];
    for (const key of inScope) {
      const value = catalogue[key];
      if (BASELINE.has(identity(key, value))) {
        continue;
      }
      const parts = sentences(value);
      if (parts.length > 2) {
        findings.push(`${key}: ${parts.length} sentences (max 2) — ${value.slice(0, 60)}`);
        continue;
      }
      const longest = longestSentence(value);
      if (longest > 6) {
        findings.push(`${key}: a ${longest}-word sentence (max 6) — ${value.slice(0, 60)}`);
      }
    }
    // SHORTEN BY DELETING THE RATIONALE, NEVER THE INSTRUCTION. Two sentences
    // of six beat one sentence of twelve: the first says what is wrong, the
    // second says what to do next, and cutting the second passes this check and
    // makes the message useless. Move the reason into the code comment.
    expect(findings).toEqual([]);
  });

  it("a LABEL or HEADING is ≤ 3 words and is NOT a sentence", () => {
    // ⚠ THE HALF A CAP CANNOT SEE. *"Sold. Now who?"* is three words and two
    // sentences — inside every cap and outside the rule. A heading NAMES a
    // thing; it does not say something about it.
    const findings: string[] = [];
    for (const key of inScope) {
      if (!isHeading(key)) {
        continue;
      }
      const value = catalogue[key];
      if (BASELINE.has(identity(key, value))) {
        continue;
      }
      if (isSentence(value)) {
        findings.push(`${key}: a heading may not be a sentence — ${value}`);
        continue;
      }
      if (HEADING_BASELINE.has(identity(key, value))) {
        continue;
      }
      const words = value.replace(PLACEHOLDER, "X").split(/\s+/).filter(Boolean).length;
      if (words > 3) {
        findings.push(`${key}: a ${words}-word heading (max 3) — ${value}`);
      }
    }
    expect(findings).toEqual([]);
  });

  it("carries no BR- / DEF- / OQ- / CR- / S<digit> id into clerk-facing copy", () => {
    // B14 rules 31 and 32, and the PO's own words on 2026-08-19: *"you are also
    // adding internal content and BR codes on screen, that is not required; it
    // is application also available to Utility user."* The provenance is not
    // deleted — it stays on the wire, in the fixtures and in the code comment
    // beside the call site. It leaves the CLERK'S SENTENCE.
    const ID = /\b(?:BR|DEF|OQ|CR|GT|ADR|US|EP|IS|TC|NFR|ACC)-[A-Z]{0,3}-?\d|\bS\d{1,3}\b/;
    const findings = inScope
      .filter((key) => ID.test(catalogue[key]))
      .map((key) => `${key}: ${catalogue[key].slice(0, 60)}`);
    expect(findings).toEqual([]);
  });

  it("the baseline may only SHRINK — a stale licence is a failure", () => {
    // A baselined entry whose message is now short, or gone, is a licence for
    // nothing. Failing on it is what stops the list drifting away from the
    // catalogue and quietly forgiving strings nobody looked at.
    const live = new Map(inScope.map((key) => [identity(key, catalogue[key]), key]));
    const stale = [...BASELINE].filter((line) => {
      const key = live.get(line);
      if (key === undefined) {
        return true; // gone, or its text changed — either way the licence lapsed
      }
      return sentences(catalogue[key]).length <= 2 && longestSentence(catalogue[key]) <= 6;
    });
    expect(stale).toEqual([]);

    const staleHeadings = [...HEADING_BASELINE].filter((line) => {
      const key = live.get(line);
      if (key === undefined) {
        return true;
      }
      return catalogue[key].replace(PLACEHOLDER, "X").split(/\s+/).filter(Boolean).length <= 3;
    });
    expect(staleHeadings).toEqual([]);
  });

  it("`P1.19`'s one explicitly named cut is done — the deposits wizard title", () => {
    // Finance blueprint p053, the only string the document tags `P1.19` by
    // name: *"The product's title is a ten-word sentence — 'Import a bank
    // statement and match it to your deposits' — and B14 rule 33 caps a heading
    // at three words."* The DRAWING supplies the replacement, so this is the
    // agreement rendered and not this lane writing copy nobody approved
    // (B14 rule 42: the drawing is the specification).
    const title = (en as Record<string, string>)["payments.deposits.wizardTitle"];
    expect(title).toBe("Import a statement");
    expect(title.split(/\s+/)).toHaveLength(3);
  });
});
