// ── Trace ──────────────────────────────────────────────
// Change:   DEF-CUS-4631 — **the account icon rail's four refusals were typed
//           sentences and all four had rotted.** PO 2026-09-07, verbatim:
//           *"in account - view we have all those icons - can you activate them
//           now"*, then *"activate all of them"*. The same evening's ruling —
//           *"A TEMPLATE'S 'IS THIS IN USE' SENTENCE BECOMES DERIVED FROM
//           ACTUAL NOTIFICATION USAGE"* / *"A MESSAGE THAT WILL NOT BE SENT
//           MUST SAY SO ON SCREEN"* — is the shape this file implements for a
//           REFUSAL: derive it, never type it.
// Story:    US-CUS-013 (Issue credit) · US-CUS-014 (Send statement, Print bill)
//           US-CUS-015 (Disconnect notice)
//           Screens: S21
// Rules:    BR-SHL-025 (a control with no endpoint is DISABLED WITH ITS REASON,
//           never hidden) · BR-SHL-045 (the rail's seven) · BR-CUS-040
//           (statement ≠ bill; a reprint never recomputes) · BR-BIL-004 (a
//           credit note is a new row beside the original bill, never a touch of
//           it) · BR-CUS-039 (disconnect tiers) · B14 rule 33 (a refusal is SIX
//           WORDS per sentence and RATIONALE IS ZERO WORDS ON SCREEN — so the
//           reasoning below is in this comment, which is where the rule puts
//           it) · B14 rule 6 · B14 rule 15
// Tests:    accountRailReadiness.test.ts (the derivation)
//           accountRailHoldExpiry.test.ts (the holds, and the day they lapse)
// ───────────────────────────────────────────────────────
//
// ══════════════════════════════════════════════════════════════════════════
// WHY THIS FILE EXISTS: A TYPED REFUSAL CANNOT NOTICE THAT IT CAME TRUE
// ══════════════════════════════════════════════════════════════════════════
// On 2026-09-07 the rail drew four disabled glyphs. Each carried an honest
// sentence, written by somebody doing the right thing, and **every one of the
// four was false** — three of them for weeks:
//
//   🖨 Print bill      *"…is not available yet. Which copy a reprint should
//                       show … has not been decided either."*
//                      → `OQ-103` and `OQ-169` both read **CLOSED** (PO
//                        2026-08-12): a later reprint renders the CORRECTED
//                        instance. And `GET /invoices/{id}/document` is mounted
//                        — the server-side twin of this sentence still said it
//                        was not, which is how both halves stayed wrong.
//   $ Issue credit     *"Which account a goodwill credit should be charged to
//                       has not been decided."*
//                      → `OQ-105`/`OQ-168` read **CLOSED** (PO 2026-08-12, *"a
//                        separate write-off account"*); `corrections.
//                        credit_only_gl_accounts` resolves DR write-off / CR
//                        customer credit balance BY DESIGNATION and
//                        `execute_credit_only` has posted the pair ever since.
//   ⚡ Disconnect notice *"The notice history has no table, the medical-hold flag
//                       has no column, and where the collection sequence stands
//                       … is still open with the Product Owner."*
//                      → **all three clauses false.** `payments.
//                        collections_models.NoticeHistory` IS the table
//                        (`db_table = "notice_history"`); `customers.
//                        disconnects.medical_hold_for` IS the flag; and
//                        `OQ-133`, `OQ-136` and `OQ-137` all read **CLOSED**
//                        (PO 2026-08-12).
//   ✉ Send statement    *"…a different document from a bill. Nothing renders one
//                       yet."*
//                      → **TRUE**, and the only one of the four that is. It
//                        keeps its refusal; see `sendStatement` below.
//
// **The mechanism is a rule with a clock in it** (CLAUDE.md hard-won law 2):
// landing the thing a control waits for and releasing the control are two acts,
// and only the first feels like the work. Three of these four were released by
// nobody because the sentence that held them was a STRING, and a string cannot
// read a register.
//
// So the three that can be derived are derived — each one asks a question about
// THIS account that the answer changes by itself:
//
//   Print bill      · has this account an ISSUED bill?      → the bills read
//   Issue credit    · has this account an issued bill to    → the same read
//                     raise the credit against?
//   Disconnect      · is this account occupying its unit?   → the account row
//
// None of those three can go stale, because none of them is an opinion about
// what the product can do — each is a fact about the row in front of you.
//
// ⚠ **AND `sendStatement` IS THE HONEST EXCEPTION, STATED RATHER THAN HIDDEN.**
// It is a CAPABILITY absence, not a data absence: no per-account read can tell
// you that this product has no statement renderer. A derived refusal is
// impossible for it, so it keeps a typed one — and gets, in the same commit,
// the test that CLAUDE.md law 2 asks for and that nobody wrote for the other
// three: `accountRailHoldExpiry.test.ts` fails the day a statement route
// appears. A hold with no such test is a promise nobody is keeping.
//
// ══════════════════════════════════════════════════════════════════════════
// THE BILLS READ IS THE ONE THE OVERVIEW TAB ALREADY MAKES
// ══════════════════════════════════════════════════════════════════════════
// `accountRecentBillsKey` and `RecentBillsPanel`'s exact arguments, so React
// Query serves both from one cache entry. Deriving two refusals therefore costs
// **no extra request** on the tab where the panel is mounted, and one cheap
// request on the tabs where it is not. Copying the key but not the arguments
// would have been the worst of both: two entries, two fetches, one of them
// silently different.

import { useQuery } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";

import { api } from "@/api/client";
import type { ApiClient } from "@/api/client";
import { getInvoices } from "@/api/endpoints";
import type { InvoiceRow } from "@/api/endpoints";
import { DEFAULT_PAGE_SIZE } from "@/components/tableTypes";
import { FIX_A_BILL_PARAM } from "@/features/billing/billingOpsShared";
import type { Translator } from "@/features/tenancy/settingsShared";
import { useTenantPath } from "@/routing/tenantPath";

import { accountRecentBillsKey } from "./accountDetailTabs";
import { accountOverlayPath } from "./accountActionOverlays";
import { DISCONNECT_WIZARD_ROUTE } from "./transferDisconnectShared";
import type { AccountRailAction } from "./AccountIconRail";

/** The four the rail could not honour on 2026-09-07. Three are derived below. */
export type DerivedRailActionId =
  | "sendStatement"
  | "printBill"
  | "issueCredit"
  | "disconnectNotice";

/**
 * A bill this account has actually ISSUED, newest first — or `null`.
 *
 * ⚠ **THE TEST IS `issued_at`, NOT `status`.** `InvoiceRow.issued_at` is
 * documented as *"null on a draft"* and is stamped once, at issue; `status`
 * moves on afterwards (`paid`, `corrected`, `void`) and reading it would make a
 * reprint of a PAID bill impossible — which is the single most common reprint a
 * clerk is asked for. A voided bill was still issued and still went to a
 * customer, so it is still reprintable; that is `BR-CUS-040`'s *"a reprint
 * serves the issued document"* and not a judgement made here.
 *
 * The list arrives `sort=issue_date&dir=desc` from the server, so the first row
 * carrying an `issued_at` is the newest issued bill. Nothing re-sorts: a second
 * ordering in the client is a second definition of "latest".
 */
export function latestIssuedBill(rows: readonly InvoiceRow[]): InvoiceRow | null {
  return rows.find((row) => row.issued_at !== null) ?? null;
}

/** What the account row must say for a disconnect to be lawful. */
export interface RailAccountFacts {
  /** `isOccupyingAccount(detail)` — the page already computes it for two other
   *  glyphs, so it is passed in rather than re-derived from a second copy of
   *  the status vocabulary. */
  occupying: boolean;
  /** The role/permission refusal that outranks every reason here, or `null`. */
  writeBlockedReason: string | null;
}

/**
 * The four actions, wired or refused — and every refusal DERIVED except one.
 *
 * Returns exactly the shape `AccountIconRail` wants, so the page spreads it in
 * and holds no second copy of any sentence.
 */
export function useAccountRailReadiness(props: {
  accountId: string;
  facts: RailAccountFacts;
  t: Translator;
  client?: ApiClient;
}): Record<DerivedRailActionId, AccountRailAction> {
  const { t, facts } = props;
  const navigate = useNavigate();
  const tenantPath = useTenantPath();

  const bills = useQuery({
    queryKey: accountRecentBillsKey(props.accountId),
    queryFn: () =>
      getInvoices(
        {
          filters: { account_id: props.accountId },
          sort: "issue_date",
          dir: "desc",
          per: DEFAULT_PAGE_SIZE,
        },
        props.client ?? api,
      ),
    retry: false,
    enabled: props.accountId !== "",
  });

  // THREE STATES AND NOT TWO. "Still asking" and "asked and there are none" are
  // different facts and a clerk acts differently on each, so they get different
  // sentences — the same distinction `AccountPlanTab` draws between "no plan"
  // and "we could not read the plans" (DEF-127).
  const billsPending = bills.isPending;
  const billsUnreadable = !bills.isPending && bills.data === undefined;
  const issued = latestIssuedBill(bills.data?.results ?? []);

  /** The shared prefix every bill-backed refusal walks before its own reason. */
  const billGate = (noBillKey: string): string | null => {
    if (facts.writeBlockedReason !== null) return facts.writeBlockedReason;
    if (billsPending) return t("customers.account.action.checking");
    if (billsUnreadable) return t("customers.account.action.billsUnreadable");
    if (issued === null) return t(noBillKey);
    return null;
  };

  return {
    // ── ✉ SEND STATEMENT — the SERVER half is live; this glyph is not yet ──
    //
    // A statement is a dated RANGE LEDGER with the "nothing is due" note
    // (BR-CUS-040, A19 rule 1).
    //
    // ⚠ **THE REASON THIS CONTROL USED TO CARRY WAS FALSE, AND CORRECTING THE
    // RECORD IS WHY THIS COMMENT CHANGED WHILE THE CODE DID NOT.** It read
    // *"`apps/billing/documents.py` renders INVOICES and nothing else, and the
    // account-ledger derived view a statement would read does not exist"*. The
    // first half is still true. **The second half has been false since
    // 2026-08-11** — `ledger.reporting.account_ledger` landed that day
    // (`dea0d6f0b`, dated with `git log -S`), FOUR DAYS BEFORE this module was
    // written, and it returns an opening balance, dated rows and period
    // totals: A19 §1's statement, row for row. Nothing re-reads a comment, so
    // a sentence that was wrong on the day it was typed went on holding a
    // control shut for a month. That is hard-won law 1.
    //
    // ⚠ **AND THE SERVER HALF EXISTS NOW** — `POST /accounts/{id}/statement`
    // (`apps/billing/statement.py`) gathers the period and QUEUES the document
    // on print and email, and `ACC-Q07` is declared as a two-date FORM in
    // `accountQuickActions.ts` with `STATEMENT_FORM`. **What is missing is ONE
    // HUNK in `AccountDetailPage.tsx`**: an `openModal` slot named
    // `"statement"` and an `AccountQuickActionForm` branch rendering
    // `quickFormFor("sendStatement")`, exactly as `"activate"` is rendered
    // today. It is not made here because that file is mid-wave under another
    // lane and pushing it would publish their unfinished work (`DEF-GOV-5134`
    // is this lane doing precisely that by accident an hour earlier).
    //
    // **So this stays refused for now, and the refusal string is REWRITTEN
    // rather than left**: *"Statements are not built yet"* is no longer true of
    // anything, and a reason that has stopped being true is how the next lane
    // learns the wrong thing — which is the whole fault above, repeating.
    //
    // ⚠ **THE OTHER HALF OF THE OLD COMMENT WAS RIGHT AND IS KEPT:**
    // `GET /reports/customer-statement` is NOT this document and must never be
    // pointed at this glyph. It is a cross-account BALANCE SUMMARY for one
    // customer (CR-060 C16) — no date range, no ledger lines, no disclaimer —
    // and aiming ✉ at it would ship a button that produces the WRONG document,
    // which is worse than one that refuses. The wave re-read it end to end
    // before building; the measurement is in the decision log, 2026-09-13.
    sendStatement: {
      reason: facts.writeBlockedReason ?? t("customers.account.action.sendStatementBlocked"),
      onClick: () => undefined,
    },

    // ── 🖨 PRINT BILL — LIVE ───────────────────────────────────────────────
    //
    // `GET /invoices/{id}/document` is mounted (`apps.billing.documents_api`)
    // and `frozen_bill.reproduce()` serves the document that was KEPT rather
    // than re-rendering one (CR-049 task 4, BR-NOT-027). `BillDocumentPage`
    // already draws both of its answers — the original, and the honest
    // "re-rendered from data, not the original" — so this glyph opens a screen
    // that cannot lie about which copy it is showing.
    //
    // WHICH copy, once a bill has been corrected, was the sentence that held
    // this control: `OQ-103` + `OQ-169`, both CLOSED on 2026-08-12 — a later
    // reprint renders THE CORRECTED ONE and reissues accumulate.
    printBill: {
      reason: billGate("customers.account.action.printBillNoBill"),
      // ⚠ **`CR-094-BRC01` wave L (`BR-CUS-1051`) — OVER THE ACCOUNT, NOT AWAY
      // TO BILLING.** The document is the same screen at the same component;
      // only the address changed, from `/billing/bills/{id}/document` to the
      // account's own child route, which renders it in a dialog with the
      // balance still behind it. **Billing's address is untouched** — it is
      // still declared, still mounted, and still what a support ticket carries.
      onClick: () =>
        issued === null
          ? undefined
          : navigate(
              tenantPath(accountOverlayPath("printBill", props.accountId, { invoiceId: issued.id })),
            ),
    },

    // ── $ ISSUE CREDIT — LIVE, ONTO THE ONE PATH THAT WRITES ONE ───────────
    //
    // The ACCOUNTING was ruled and is built: a class-C concession debits a
    // SEPARATE WRITE-OFF ACCOUNT and credits the customer's credit balance
    // (`OQ-105`/`OQ-168`, PO 2026-08-12), resolved BY DESIGNATION so a tenant
    // may renumber their chart. GT-6's frozen shape — a $25.00 credit against a
    // $247.30 invoice leaving $222.30 owing — reaches the same balance either
    // way, which is why nothing here needs to know it.
    //
    // ⚠ **THE REMAINING CONSTRAINT IS A SHAPE, NOT A DECISION, AND IT IS WHY
    // THIS GLYPH OPENS THE BILL AND NOT A MODAL.** Every credit note this
    // product can write is raised against ONE BILL, inside the bill-correction
    // workflow: `execute_credit_only` takes an invoice, `credit_notes.
    // original_invoice_id` names it, and the concession's letter and its ledger
    // memo both quote that bill. There is no account-scoped writer, so an
    // account-scoped modal would have nothing to call. The route to a goodwill
    // credit is the bill — open it, correct it as a concession — and that is
    // exactly where this goes.
    //
    // ⚠ `OQ-215` IS OPEN and is NOT decided here: whether a class-C concession
    // moves THIS bill's balance or is an account-level credit the NEXT bill
    // consumes. Nothing on this path chooses — the correction workflow owns
    // that behaviour and `single_correction.py` cites the row at the
    // divergence. This glyph opens a door; it does not post anything.
    issueCredit: {
      reason: billGate("customers.account.action.issueCreditNoBill"),
      // `BR-CUS-1051` — the correction workflow, over the account. The bill it
      // is raised against still rides in `?bill=`, exactly as `fixABillPath`
      // writes it at billing's own address, so `FixABillTab` reads one query
      // key whichever door it was opened from.
      onClick: () =>
        issued === null
          ? undefined
          : navigate(
              tenantPath(
                `${accountOverlayPath("issueCredit", props.accountId)}?${FIX_A_BILL_PARAM}=${encodeURIComponent(issued.id)}`,
              ),
            ),
    },

    // ── ⚡ DISCONNECT NOTICE — LIVE, INTO THE WIZARD THAT ALREADY EXISTS ────
    //
    // ⚠ **NOTHING NEW IS DECIDED HERE AND NOTHING NEW IS BUILT.** `DSC-02`, the
    // five-step disconnect wizard, has been live since 2026-08-25 and is
    // reachable today from the Accounts list and from the Disconnects tab. Its
    // step 2 is *Protections* (the medical hold, read through
    // `disconnects.medical_hold_for`) and its step 3 is *Notice & date*. Every
    // endpoint behind it is mounted: `/accounts/{id}/ladder`,
    // `/accounts/{id}/disconnect-case`, `…/advance`, `…/notices`,
    // `/disconnects/schedule`.
    //
    // So this is a SECOND ENTRANCE to a door the product already had, from the
    // screen a clerk is actually standing on. That is the safest possible way
    // to honour *"activate all of them"*: no new notice path, no new rule, and
    // the wizard's own refusals — a protection in force, a payment that cleared
    // the arrear, a plan pause — keep working exactly as they do from the other
    // two entrances.
    //
    // ⚠ **AND THE WIZARD SCHEDULES; IT NEVER CUTS.** Its footer says so on all
    // five steps — *"nothing is cut until the scheduled date"* — which is the
    // reason it is safe to reach from a glyph.
    //
    // THE GATE IS OCCUPANCY, and it is the same one Change plan and Payment
    // plan already use, because it is the same fact: a draft never took the
    // unit and a closed account has already left it, so neither has service to
    // cut. B14 rule 6 gives this one the danger tier in `AccountIconRail`.
    disconnectNotice: {
      reason:
        facts.writeBlockedReason ??
        (facts.occupying ? null : t("customers.account.action.disconnectNotOccupying")),
      // `BR-CUS-1051` — over the account rather than away to `/disconnects/new`.
      // The wizard is the same five steps; it reads its subject from the PATH
      // here and from `?account=` there, and `/disconnects/new?account=` still
      // works for the two entrances that use it (the Accounts list, the
      // Disconnects tab).
      onClick: () => navigate(tenantPath(accountOverlayPath("disconnectNotice", props.accountId))),
    },
  };
}

/** Re-exported so a test can assert the destination BY ADDRESS (law 2's
 *  "assert the destination by ADDRESS and by the screen id it opens"). */
export { DISCONNECT_WIZARD_ROUTE };
