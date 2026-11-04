# ── Trace ──────────────────────────────────────────────
# Story:    US-PAY-020 (deposit batches — day × method, DEP- numbering, the S37
#           list · TC-1 the PE-10 pair, TC-3 the drawer day, TC-5 no hand-edit,
#           TC-6 isolation) · US-PAY-021 (S38 import → auto-match on amount +
#           date ± tolerance → confirm · TC-2 the tolerance, TC-5 the re-import
#           block) · US-PAY-022 (S40: every difference explained with reason +
#           GL · TC-1 PE-11's −5.00, TC-3 the card day, TC-5/TC-6 the refusals)
#           · US-PAY-023 (S39 trail + the reconciled LOCK · TC-3/TC-4/TC-5)
#           Screens: S37 · S38 · S39 · S40
# Rules:    BR-PAY-004 (reconciled batches LOCK; Unreconcile is the only
#           reversal) · BR-PAY-019 (bank rec in FINANCE: statement import,
#           auto-match on amount + date ± a finance setting, every exception
#           explained with reason + GL) · BR-PAY-021 (posting ≠ clearing) ·
#           BR-PAY-025 (SUPERSEDED-IN-PART 2026-09-22 — batches group a TILL ×
#           a tender; the day is still the POSTING day,
#           PO ruling RQ-5 / BR-REP-013) · BR-PAY-028 (file+tags import
#           idempotency 🔒) · BR-PAY-035 ("Force match anyway" permanently
#           SUPERSEDED) · BR-LED-001 (every journal line carries its source) ·
#           BR-TEN-043 (event time is named by the caller, never a clock) ·
#           CLAUDE.md rule 1 (tenant scoping) · rule 2 (money NUMERIC(18,6),
#           never float) · rule 4 (immutability) · rule 5 (ONLY the ledger
#           posting service writes journal lines) · rule 6 (idempotency) ·
#           rule 7 (every money action writes audit_log)
# Golden:   PE-10 ❄️ (GT-44 by the B5 PE-n → GT-(34+n) allocation): checks
#           292.87 + 142.30 + 36.22 = 471.39 (DEP-260808-CHK) · cash 105.36 +
#           16.42 = 121.78 (DEP-260808-CSH) — the MONEY is frozen and unmoved;
#           the CODES gained their year by PO ruling 2026-08-12 (OQ-162, and
#           EP-PAY-06 §4's format superseded) · PE-11 ❄️ (GT-45): bank 588.17 vs
#           batch 593.17 → −5.00 explained as a bank fee with reason + GL
# Tests:    06-backend/tests/test_us_pay_020_023_bank_rec.py
# Impacts:  apps/payments/bankrec_models.py (the six tables this is the only
#           write path for) · apps/payments/lockbox.py (the file kernel) ·
#           apps/payments/settings_seam.py (the ±N-day tolerance) ·
#           apps/payments/ledger_seam.post_batch_reconciled (the balanced
#           handoff — payments posts nothing itself) · apps/payments/models.py
#           (Payment.deposit_batch_id, opened write-once by migration 0005) ·
#           apps/payments/run_alert_seam.py (the notifications seam
#           `import_bank_statement` now calls; `StatementImportResult
#           .staff_alert` carries what it did)
# Change:   CR-048 wave B follow-up (2026-08-30) — `import_bank_statement` now
#           sends the ONE staff message a finished reconciliation run owes its
#           operator. Nothing else in this file moved; no money path changed.
#           Test: 06-backend/tests/test_cr048_staff_alerts_wired.py
# ───────────────────────────────────────────────────────
"""Deposit batches and bank reconciliation — and the event that REALISES CASH.

HUMAN-OWNED · HUMAN-REVIEW-PENDING — this file decides when a customer's money
becomes CASH in the books (CLAUDE.md 🔒 "ledger posting" + rule 4). AI-authored
2026-08-11 under the PO ruling of 2026-08-09 (*"AI will do it; we will review it
later as human"*); row in 12-governance/09-human-review-ledger.md.

⚠ CORRECTED 2026-09-01 (DEF-2791) — THE PARAGRAPH BELOW IS HISTORY, NOT THE
CURRENT STATE. A glob DOES match this file: `human_owned.txt` carries
`06-backend/apps/payments/reconciliation.py` ("Bank reconciliation — the event
that REALISES cash … and the net-match + fee split"), granted by the PO ruling
of 2026-08-11 — verbatim *"Pls start 2 and 1 and then 3"*, answering a ranked
list whose item 2 was *"five money paths are unguarded"*, this file among the
five. **So G7 DOES read the two markers above.** The ask below was answered
nearly three weeks ago; it is kept because why a money path went unguarded is
worth knowing, and nothing below it describes today.

⚠ **THIS FILE MATCHES NO GLOB IN `10-scripts/gates/human_owned.txt`**, so G7 does
not read the HUMAN-OWNED / HUMAN-REVIEW-PENDING markers above — it reports
"conform" over a money path it is not looking at. Editing that guard list is a
process event (its own header says so), so the line is **REPORTED for the daily
PO batch rather than self-granted**, which is the posture `posting_seam.py` and
`delivery_seam.py` each took from this same position. Saying it here is the
point: a marker no gate reads is hard-won law 1, and the file that carries it is
the honest place to say so.

╔══════════════════════════════════════════════════════════════════════════╗
║  CASH IS NOT CASH UNTIL THE BANK CONFIRMS IT — AND THIS FILE IS WHERE    ║
║  THE BANK CONFIRMS IT.                                                   ║
╚══════════════════════════════════════════════════════════════════════════╝

**PO ruling, 2026-08-11 (OQ-143 CLOSED), verbatim:** *"Cash is received but
undeposted in such case payment will say csah but ledger will say undeposited -
until bank record and reconcilaition confirm it it is not realised"*.

Two records that deliberately say different things: the PAYMENT says cash was
received (that is what the clerk saw), and the LEDGER says a HOLDING account
(that is what the bank has confirmed, which is nothing yet). So the posting is
TWO steps and this module owns the second (amended 2026-08-18, CR-008 B-10:
the holding account is the TENDER's own clearing account when one is mapped —
`payment_methods.clearing_gl_account_id` — and 1010 Undeposited funds
otherwise, which is every tender's pre-B-10 behaviour unchanged):

    on receipt          DR the tender's holding account / CR accounts receivable
    on RECONCILIATION   DR cash / CR what each receipt DEBITED   ← here,
                        read from the member entries themselves
                        (`_member_credit_split` over the ledger's
                        `entry_debit_totals`), never from today's mapping

Both accounts are in the ❄️ finance-signed chart (1000 Cash · 1010 Undeposited
funds), so nothing here needs a finance re-sign. `apps/payments/ledger_seam.py`
carries both halves; this module never writes a journal line itself (hard rule
5) and never picks an account by number (OQ-110's closure — by DESIGNATION).

**A batch that is never reconciled therefore never becomes cash**, which is the
whole point of the ruling: the trial balance shows money sitting in undeposited
funds until a bank statement says otherwise.

╔══════════════════════════════════════════════════════════════════════════╗
║  A CARD DAY RECONCILES **NET**, WITH THE PROCESSOR'S FEE AS ITS OWN LINE ║
╚══════════════════════════════════════════════════════════════════════════╝

**PO ruling, 2026-08-11 (OQ-144 CLOSED), verbatim:** *"Match net with a fee
line"*. **Worked, on the prototype's own figures:** a card day takes **$5,120.40**
from customers, the bank credits **$4,972.90**, and **$147.50** is the
processor's fee. Matching is exact-amount and one-to-one, so before this ruling
that day could NEVER tie — roughly **250 hand-worked exceptions a year** for a
utility with one or two staff. Under the ruling the batch reconciles against the
bank's NET credit and the fee posts as its own line to **6800 Bank fees** (in
the ❄️ chart — no re-sign).

That is one balanced entry:

    DR 1000 Cash               4,972.90   ← what the bank actually gave us
    DR 6800 Bank fees            147.50   ← its own line, never netted away
    CR 1010 Undeposited funds  5,120.40   ← what the customers handed over

**The fee is NOT absorbed into the cash line and it is NOT netted against
revenue.** A netted deposit is a fee nobody can report, and BR-PAY-019's whole
control is that every difference carries a reason AND a GL account.

────────────────────────────────────────────────────────────────────────────
THE PROCESSOR FEE — RULED 2026-08-12 (OQ-160), AND THE HAZARD IT CARRIES
────────────────────────────────────────────────────────────────────────────
This section described a refusal until the ruling landed. The hazard the
refusal existed for is REAL and is kept on the record rather than deleted,
because deriving the fee means the gap is fully explained by construction: *"whether the net match requires the fee to be known in advance from the
processor's settlement file, or is derived from the difference (which would
silently absorb a genuine shortfall into 'fees'). That distinction decides
whether a $10 customer chargeback hides inside a fee line."*

**RULED 2026-08-12: the fee MAY be derived from the shortfall** (PO verbatim,
*"derived from shortfall"*). Most acquirers net silently, so a stated-fee-only
rule makes card reconciliation impossible in practice. `derive_processor_fee()`
builds the resolution and — deliberately — does NOT reconcile: the derived
figure enters `reconcile_batch` through the same door as a human's, meets the
same tie-out, and is written with a reason code and a GL account like any other.
It also refuses a difference in the wrong direction, because a bank crediting
MORE than we recorded has not charged us a fee, and naming it one would post a
negative expense over a real question.

────────────────────────────────────────────────────────────────────────────
THE DAY A BATCH BELONGS TO IS THE **POSTING** DAY (BR-PAY-025 · PO RQ-5)
────────────────────────────────────────────────────────────────────────────
The drawer day, not the bank day. BR-PAY-025 (*"day = POSTING date per
RQ-5/BR-REP-013"*), BR-REP-013 and journey J14 step 4 all say so; **EP-PAY-06's
US-PAY-020 said `cleared_at` and shipped a test case asserting it**, which was
stale text written before the ruling — corrected in this commit with defect row
DEF-065. The ±3-day match tolerance is what lets a drawer day tie to a bank day:
J14 takes the money on 8 Aug and the statement lands on 11 Aug.

The day is read off `posted_at` in **UTC**, which is what the column stores
(B2 §5: storage is UTC, display per tenant). A tenant west of UTC banking at
6pm local therefore lands on the next UTC day — that is **OQ-153**, already
open, raised by the payments API lane for exactly this column. Named here rather
than solved with an invented timezone conversion.

────────────────────────────────────────────────────────────────────────────
MATCHING IS EXACT AND ONE-TO-ONE. A DIFFERENCE IS A HUMAN'S TO EXPLAIN
────────────────────────────────────────────────────────────────────────────
`auto_match` links a bank line to a batch only when the amounts are EQUAL and
the dates are within the tenant's tolerance (BR-PAY-019, signed). It refuses to
guess in three ways, each of which would otherwise reconcile the wrong money:

  * two candidate batches for one line (or two lines for one batch) → neither is
    matched; ambiguity is left for a human;
  * a NON-EQUAL amount is never auto-linked — that is the S40 exception, and
    linking it here would be the auto-fee derivation OQ-160 forbids;
  * a bank line whose method is "obvious" from its reference text
    (`CARD SETTLEMENT STRIPE`) is not paired on that basis. Parsing a method out
    of a bank's prose is a heuristic, and BR-PAY-023's rule for staged imports is
    *"never auto-guess silently"*.

A human then names the pairing (`match_bank_line`) and explains the difference
(`reconcile_batch`). **"Force match anyway" does not exist** — BR-PAY-035 made
the prototype's button permanently SUPERSEDED, and there is no code path here
that reconciles an unexplained residual.

**Many-to-one matching IS BUILT, as of 2026-09-01 (CR-059 task 45 / CS-17).**
This paragraph used to read *"Many-to-one matching is NOT built"* and it stopped
being true today. The PO closed **OQ-161** on **2026-08-12** — verbatim, *"Build
many-to-one matching"* — on the worked case of **$2,840.00 + $14,280.00 posted
by the bank as ONE credit of $17,120.00**, and the code was owed for twenty
days. `match_set()` is the door; `bank_rec_match_sets` and its members are the
record. Three things about it are worth reading before touching it:

  * **it is never automatic.** `auto_match` is untouched and still exact and
    one-to-one. A set exists only because a HUMAN said *"that credit is these
    two deposits"* — CS-17 widens what can TIE and never what can be GUESSED.
  * **a set's two sides must be EXACTLY equal**, not within the tenant's amount
    tolerance. On one pair a difference has an owner and is explained with a
    reason and a GL; across a set nothing rules how to apportion it.
  * **there is no dissolve path**, in the service or the database. CS-17 rules
    the set IN and rules nothing about undoing one, and inventing that verb here
    would be this lane ratifying a rule nobody ruled.

────────────────────────────────────────────────────────────────────────────
THE LOCK HOLDS, AND A BOUNCE INSIDE IT IS NEW ROWS — OQ-134, RULED 2026-08-12
────────────────────────────────────────────────────────────────────────────
BR-PAY-004: a reconciled batch LOCKS and Unreconcile is the only way back. The
guarantee is the trigger in `migrations/0005`; this module refuses the same
things one layer up so the SQLite developer database behaves like production.

**What this section used to say, and why it was right at the time.** A member
cheque that bounced after its batch was reconciled was refused by name as
**OQ-134**, from both sides: `assert_bounce_allowed()` refused a payment sitting
in a reconciled batch, and `recompute_batch_total()` refused the same case from
the other side so the invariant held even if the NSF path forgot to ask. The
claim was that US-PAY-022 TC-2 resolves the UNLOCKED case by recomputing
`recorded_total`, that doing so after the lock is an in-place edit of a
signed-off money record, and that choosing between the lock and the tie-out was
a finance call rather than an implementing lane's. **That refusal was correct
while the question stood** — kept here rather than deleted, because the shape of
it is still visible in EP-PAY-06 and in this module's tests.

**PO ruling, 2026-08-12 (OQ-134 CLOSED), verbatim:** *"if this happen Utility
will charge Cheque bounce charges and add new entry - this will be mnaul process
by utility user in payments or in finance we have to decide the place - you
decide for me"*. **THE LOCK HOLDS.** Worked on the prototype fixture:
DEP-260805-CHK is 8 cheques recorded at **$2,840.00**, reconciled and locked;
three weeks later cheque #4021 (**$100.00**) is returned. The batch total stays
**$2,840.00** — the bank statement it was agreed against did not change, and
rewriting it to $2,740.00 would edit a signed-off money record in place, which
hard rule 4 forbids. The bounce is the ordinary reversing row plus the utility's
bounce fee, both NEW rows. The placement half was delegated and decided:
**PAYMENTS, on the payment** (`apps/payments/reversal.py` carries the reasoning
and the code).

The two halves therefore now say different things, deliberately:

  * `assert_bounce_allowed()` LETS A LOCKED BATCH THROUGH. What it still refuses
    is the case the ruling did not touch — a payment naming a batch this process
    cannot READ has an unknown lock state, and a batch id resolving to no row is
    a broken reference rather than a lock, so it fails closed.
  * `recompute_batch_total()` STILL REFUSES a reconciled batch, and that IS the
    ruling rather than a leftover: the total does not move, so recomputing it is
    the in-place edit hard rule 4 forbids. It refuses as a RULE now
    (`PaymentRuleError`, BR-PAY-004), not as a parked question.

────────────────────────────────────────────────────────────────────────────
UNRECONCILE TAKES THE CASH BACK OUT OF THE BOOKS — AND THAT IS OQ-163
────────────────────────────────────────────────────────────────────────────
Unreconciling posts the linked MIRROR of the reconciliation entry (through the
ledger's own `reverse_entry`, US-LED-003 — a correction is a NEW entry, never an
edit). It has to: the PO's ruling says money is not cash until the bank confirms
it, and unreconciling is precisely the statement that the confirmation did not
hold. Leaving the entry would leave CASH in the trial balance for a batch the
product itself says is unreconciled, and a later re-reconcile would post the
cash a second time.

Nobody has ruled that, so it is **OQ-163**, raised. It is implemented rather
than stubbed for the reason `apps/ledger/posting.py` gives about OQ-126: the
alternative is not a different answer, it is books that contradict a ruling
already made, and a `NotImplementedError` here would break BR-PAY-004's
CONFIRMED Unreconcile path outright.

────────────────────────────────────────────────────────────────────────────
WHAT THIS MODULE DOES NOT BUILD, NAMED SO SILENCE IS NOT READ AS "DONE"
────────────────────────────────────────────────────────────────────────────
  * ⚠ **THIS BULLET USED TO SAY "NO HTTP SURFACE AND NO SCREEN" AND IT HAD BEEN
    FALSE SINCE 2026-08-16.** The payments surface lane mounted eight routes in
    `apps/payments/api.py` and built S37, S38, S39 and S40 that day; the claim
    stood here — and, worse, was SERVED to those very screens inside
    `RECONCILE_UNAVAILABLE` — for sixteen days. Corrected 2026-09-01 with a
    defect row rather than quietly deleted: a stated absence that outlives its
    absence is hard-won law 1 wearing a helpful face, and the honest record of
    how long one survived is worth more than a clean paragraph.
    **What is genuinely not wired TODAY:** the four W8 additions below —
    `match_set`, `resolve_bank_line`, the statement balances and the
    difference-reason list — have routes and reads (this commit) and **no screen
    control**. S38's line-selection, S39's set panel, S40's reason picker and
    S37's reconciliation statement are all **CR-059 task 48**, and until that
    lands a clerk cannot reach any of them. Said out loud rather than left for a
    reviewer to discover.
  * ⚠ **THIS BULLET SAID THE BATCH CODE COULD NOT COME FROM SETTINGS, AND IT
    IS OBSOLETE AS OF 2026-09-22.** It read: *"BR-TEN-035's format grammar has
    no method token and REQUIRES a sequence token, so the composed code cannot
    be stored in a `number_series` row at all."* **Every clause of that was
    true OF A CODE CONTAINING THE TENDER — and the tender has left the code.**
    PO ruling 2026-09-22, verbatim: *"(b) Put it in Settings today —
    DEP-260922-0001 — Settings → Numbering, like every other number"*. So **the
    DEP- code is ALLOCATED from the tenant's `deposit_batch` series**, which
    was already seeded, already carried a counter and was already ignored by
    this module. `_get_or_create_batch` calls `core.numbering.next_number`
    inside the issuing transaction like every other number in the product.
    It is struck here rather than deleted because CLAUDE.md records eight
    occasions of a ruling landing while the pointer to it did not move, and a
    reader who remembers the old sentence needs to find its retraction.
  * **The year and the date are still in the code, and the 2026-08-12 ruling
    is untouched.** *"Add the year + Date is important"* (OQ-162, DEF-066) —
    the seeded format is `DEP-{YY}{MM}{DD}-{0000}`, so 8 Aug 2026 and 8 Aug
    2027 still render differently. **Only the method token left.** The batches
    banked before this change keep their composed codes (`DEP-260808-CHK`);
    hard rule 4 freezes a financial record and `BR-PAY-004` locks a reconciled
    batch, so old codes read one way and new ones read another — the same
    two-populations answer the PO gave for the legacy sessions.
  * ⚠ **G3 WAS RULED ON 2026-10-30 (PO: *"Q1. May a bank-statement line that
    isn't a deposit post to the books?-A"*), SO THE BULLET BELOW IS HALF
    HISTORY.** A returned line matched to its payment and a bank-fee line now
    POST (`match_returned_line`, `explain_bank_fee_line`, `DEF-PAY-10694`). An
    ordinary explanation through `resolve_bank_line` still posts nothing — a
    lane judgment recorded in the decision log, *"LBX-05 and LBX-09 built"*.
  * **The "Not in our system" tile is EXPLAINED, and still not POSTED.** Since
    CS-16 (CR-059 task 44) a line that is not a deposit of ours can be given a
    reason and a GL account — *"every bank line ends the period either matched
    or explained; silence is not a state"* — through `resolve_bank_line()`.
    **It posts NOTHING**: creating a payment or a journal entry from a bank line
    is batch decision **G3** and the PO has not ruled on it. So the explanation
    is recorded and reportable, and the line is STILL a difference between the
    bank and the books until G3 is answered — which is why the reconciliation
    statement carries "explained, not posted" as a line of its own rather than
    folding it into the tie-out.
  * **The deposit-slip export (IS-9), the KPI strip and the S37 capability row.**
    Reads over what this writes; they arrive with the screen.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, date, datetime, time, timedelta
from decimal import Decimal
from importlib import import_module
from typing import Any

from django.db import connection, transaction
from django.db.models import Count, Q, Sum

from core import audit as core_audit
from core import errors
from core import money
from core import numbering as core_numbering
from core import permissions
from core import tenancy as core_tenancy

from apps.payments import bankrec_models as bankrec
from apps.payments import ledger_seam, lockbox, models, run_alert_seam, settings_seam
from apps.payments.exceptions import PaymentRuleError

ZERO = Decimal("0")

#: The tenant's `deposit_batch` series is seeded `DEP-{YY}{MM}{DD}-{0000}` and
#: renders `DEP-260922-0001` — the PO's own example, ruled 2026-09-22.
#:
#: ⚠ **THE YEAR IS STILL THERE AND THE 2026-08-12 RULING IS UNTOUCHED**,
#: verbatim: *"Add the year + Date is important"* (OQ-162 CLOSED, DEF-066).
#: Without it, 8 Aug 2026 and 8 Aug 2027 rendered the same string against a
#: code that B2 §2 makes UNIQUE per tenant, so no utility could bank on its
#: go-live anniversary. **Only the METHOD token left the code**, on
#: 2026-09-22, because two tills banking cheques on one day rendered one
#: string and the second was refused. The tender lives in the `method` column
#: it always had.
#:
#: **The MONEY has never moved** — PE-10's 292.87 + 142.30 + 36.22 = 471.39
#: and 105.36 + 16.42 = 121.78 are ❄️ frozen and untouched by any of this;
#: only the label they hang on changed, twice.
#:
#: ⚠ **`CODE_PREFIX` AND `METHOD_TOKENS` WERE DELETED ON 2026-09-22 WITH
#: `batch_code` AND `method_token`.** The prefix and the shape now live in the
#: tenant's `deposit_batch` number series, which is what Settings → Numbering
#: edits — a utility that wants `BATCH-{YY}-{000}` changes it there and this
#: module never learns. Nothing composes a DEP- string any more.
#:
#: The batches banked BEFORE the change still carry composed codes and the
#: tests that pin PE-10's ❄️ frozen `DEP-260808-CHK` and `DEP-260808-CSH`
#: write those strings out literally, which is honest: they are historical
#: labels on frozen rows, not something this code can still produce.
DEPOSIT_BATCH_SERIES = core_numbering.DEPOSIT_BATCH

#: Audit action codes (US-PAY-020 §5 · US-PAY-021 §5 · US-PAY-022 §5 ·
#: US-PAY-023 §5). Codes, never prose — the trail is grouped on them.
AUDIT_BATCH_CREATED = "deposit_batch.created"
AUDIT_BATCH_REGROUPED = "deposit_batch.regrouped"
AUDIT_STATEMENT_IMPORTED = "bank_statement.imported"
AUDIT_REC_CONFIRMED = "bank_rec.confirmed"
AUDIT_REC_RESOLVED = "bank_rec.resolved"
AUDIT_BATCH_RECONCILED = "batch.reconciled"
AUDIT_BATCH_UNRECONCILED = "batch.unreconciled"
#: CR-059 W8. A match SET (CS-17) and a LINE explanation (CS-16) are both acts a
#: reconciliation hangs off, so both write hard rule 7's row.
AUDIT_MATCH_SET = "bank_rec.match_set"
AUDIT_LINE_RESOLVED = "bank_rec.line_resolved"

#: What this module cannot say, carried on results so a caller never has to
#: infer an absence and a reviewer never has to take the docstring's word for it
#: (the `posting_seam.POSTING_UNAVAILABLE` discipline).
#:
#: ⚠ **TWO ENTRIES CAME OUT ON 2026-09-01 AND BOTH HAD BECOME FALSE ON SCREEN.**
#:   * `no_screen_and_no_endpoint` — untrue since **2026-08-16**, when the
#:     payments surface lane mounted eight routes and built S37/S38/S39/S40. It
#:     went on being served to those very screens for sixteen days. Filed as a
#:     defect rather than quietly deleted, because a stated absence that outlives
#:     its absence is hard-won law 1 wearing a helpful face.
#:   * `grouped_bank_credits_not_matchable` — untrue as of CR-059 task 45, which
#:     is what this commit builds. It rendered in ELEVEN languages
#:     (`payments.problem.grouped_bank_credits_not_matchable`) telling a clerk
#:     *"Those deposits will stay unmatched"* — the panel would have contradicted
#:     the new Match-set control sitting beside it. ⚠ **THE ELEVEN LOCALE KEYS
#:     WERE REMOVED ON 2026-09-23, TWENTY-TWO DAYS LATER (`DEF-PAY-6330`).**
#:     This note said they were "the FRONTEND's to remove" and nobody removed
#:     them, so the false sentence went on rendering the whole time — kept alive
#:     by a frontend fixture that invents the code, which makes the test
#:     asserting it renders pass forever after this file stops sending it.
#:     **Handing work to another surface in a comment is not the same as it
#:     being done**, and the only thing that closed it was a Product Owner
#:     reading the panel.
#:
#: ⚠ **`unmatched_bank_lines_are_counted_only` CAME OUT ON 2026-10-30
#: (`DEF-PAY-10694`, LBX-05), AND ITS ELEVEN CATALOGUE KEYS WITH IT, IN THE
#: SAME COMMIT** — the lesson of the two entries above. It said creating a
#: journal entry from a bank line was *"batch decision G3 and is still
#: unruled"*; the PO ruled G3 = A that day, a returned line now matches its
#: reversal and a fee line posts to Bank fees. An ordinary *Explain* still
#: posts nothing, and the reconciliation statement's own
#: `explained_lines_are_not_posted` says so where it is true.
RECONCILE_UNAVAILABLE: tuple[dict[str, Any], ...] = ()


# ── results ─────────────────────────────────────────────────────────────────
@dataclass(frozen=True)
class BatchSummary:
    """One deposit batch as the S37 row reads it."""

    batch_id: str
    code: str
    #: None for a batch made since `CR-186-BRC10` (2026-10-21): all tenders.
    method_code: str | None
    deposited_on: date
    recorded_total: Decimal
    payment_count: int
    status: str
    created: bool


@dataclass(frozen=True)
class CutResult:
    """What cutting one day's batches did — and what it deliberately left."""

    day: date
    batches: tuple[BatchSummary, ...] = ()
    payments_batched: int = 0
    #: Cleared money this day that could NOT be batched, with the reason. Never
    #: silently dropped: a payment nobody banked is a real thing to look at.
    skipped: tuple[dict[str, Any], ...] = ()


@dataclass(frozen=True)
class MatchOutcome:
    """One bank line's fate at auto-match (S38 step 2's four tiles)."""

    bank_line_id: str
    amount: Decimal
    posted_on: date
    batch_id: str | None
    batch_code: str | None
    state: str  # auto | needs_a_look | not_in_our_system
    difference: Decimal | None = None
    detail: str | None = None


@dataclass(frozen=True)
class StatementImportResult:
    """S38 steps 1–2: the file landed, and here is how it lines up."""

    statement_import_id: str
    line_count: int
    matched: tuple[MatchOutcome, ...] = ()
    exceptions: tuple[MatchOutcome, ...] = ()
    not_in_our_system: tuple[MatchOutcome, ...] = ()
    unavailable: tuple[dict[str, Any], ...] = field(default=RECONCILE_UNAVAILABLE)
    #: CR-048 wave B — what the ONE staff message this run sends did: queued,
    #: already queued, suppressed by the utility's own switch, or broken. Carried
    #: for the same reason `unavailable` is: a run that told nobody it finished
    #: must be able to say why, rather than leaving a clerk to notice an empty
    #: bell.
    staff_alert: tuple[dict[str, Any], ...] = ()


@dataclass(frozen=True)
class ResolutionInput:
    """One explanation of one difference — BR-PAY-019's *reason + GL*, stated.

    `amount` is SIGNED and is the part of `bank_total − recorded_total` this
    explanation accounts for: the card day's processor fee is **−147.50**.
    Never derived from the difference by this module (OQ-160) — a human or a
    settlement file states it, and the sum is CHECKED against the difference.
    """

    reason_code: str
    gl_account_id: Any
    amount: Decimal
    note: str | None = None


@dataclass(frozen=True)
class MatchSetResult:
    """CS-17 — what one match SET tied, and to what.

    `created=False` is the idempotent replay: the SAME lines against the SAME
    batches, submitted twice, answers with the set that already exists rather
    than a red error for a button that worked (`record_payment`'s posture, and
    hard rule 6 applied to a match).
    """

    match_set_id: str
    matched_total: Decimal
    currency: str
    bank_line_ids: tuple[str, ...]
    batch_ids: tuple[str, ...]
    batch_codes: tuple[str, ...]
    created: bool
    unavailable: tuple[dict[str, Any], ...] = field(default=RECONCILE_UNAVAILABLE)


@dataclass(frozen=True)
class LineResolutionResult:
    """CS-16 — one bank line, explained with a reason and a GL account.

    `journal_entry_id` is deliberately absent from this class: an ordinary
    explanation posts NOTHING. G3 was ruled on 2026-10-30 for a returned line
    and a bank-fee line only — those go through `match_returned_line` /
    `explain_bank_fee_line` and answer with `LinePostingResult` instead.
    """

    resolution_id: str
    bank_line_id: str
    reason_code: str
    gl_account_id: str
    amount: Decimal
    currency: str
    created: bool
    unavailable: tuple[dict[str, Any], ...] = field(default=RECONCILE_UNAVAILABLE)


@dataclass(frozen=True)
class ReconcileResult:
    """What one reconcile left in the books, and what it tied out to."""

    batch_id: str
    code: str
    recorded_total: Decimal
    bank_total: Decimal
    difference: Decimal
    explained: Decimal
    journal_entry_id: str
    posting_key: str
    created: bool
    resolutions: tuple[dict[str, Any], ...] = ()
    unavailable: tuple[dict[str, Any], ...] = field(default=RECONCILE_UNAVAILABLE)


# ── tenant + small helpers ──────────────────────────────────────────────────
def _tenant_id() -> Any:
    """CLAUDE.md rule 1 — nothing touches a tenant table without `app.tenant_id`.

    Refuses rather than defaulting: a batch cut with no tenant context would be
    blocked by RLS on Postgres and would bank another tenant's money on SQLite.
    """
    tenant_id = core_tenancy.current_tenant_id()
    if tenant_id is None:
        raise errors.AuthError(errors.AUTH_TENANT_UNRESOLVABLE, br_ref="BR-TEN-003")
    return tenant_id


def _resolve(module: str, attribute: str, kind: str = "selectors") -> Any:
    """A neighbour's published callable, or None while it has not published one."""
    try:
        target = import_module(f"apps.{module}.{kind}")
    except ImportError:  # pragma: no cover - defensive
        return None
    found = getattr(target, attribute, None)
    return found if callable(found) else None


def _allocate_batch_code(day: date) -> str:
    """The batch's number, from Settings → Numbering (PO ruling 2026-09-22).

    Verbatim: *"(b) Put it in Settings today — DEP-260922-0001 — Settings →
    Numbering, like every other number"*. The `deposit_batch` series already
    existed on every seeded tenant, already carried a counter and was simply
    ignored by this module; **that divergence between the shipped Settings
    screen and the shipped banking code is what this closes.**

    ⚠ **THIS REPLACED A PURE FUNCTION, `batch_code(day, method_code)`, WHICH
    COMPOSED `DEP-{YY}{MM}{DD}-{METHOD}` BY HAND.** It could not survive the
    re-key: two tills banking cheques on one day both rendered
    `DEP-260922-CHK` and the second was refused by `uq_deposit_batches_code`,
    measured on PostgreSQL. **The tender leaves the code and lives in the
    `method` column it already has** — the PO's own *"a code is a label, never
    a data store"*.

    **The 2026-08-12 ruling SURVIVES INTACT.** *"Add the year + Date is
    important"* (OQ-162, DEF-066): the seeded format is
    `DEP-{YY}{MM}{DD}-{0000}`, so 8 Aug 2026 and 8 Aug 2027 still render
    differently and the anniversary defect stays fixed. Only the method token
    left.

    ⚠ **THERE IS NO COUNTER HERE AND NO RETRY LOOP, DELIBERATELY.** The series
    allocator takes a row lock, serves thirty other numbers and is already safe
    when two callers allocate at once (`BR-TEN-035`). A per-day-per-tender
    counter computed by counting rows would have been a race that two clerks
    closing tills in the same second could lose. **The uniqueness problem
    dissolves rather than being solved.**

    `issue_date` is the DRAWER DAY the caller named, never a clock — BR-TEN-043
    and gate G6. A cut re-run for last Tuesday numbers under last Tuesday.
    """
    try:
        return core_numbering.next_number(DEPOSIT_BATCH_SERIES, day)
    except core_numbering.NumberingError as exc:
        raise PaymentRuleError(
            f"this tenant has no usable {DEPOSIT_BATCH_SERIES!r} number series, so a deposit "
            f"batch for {day.isoformat()} cannot be numbered ({exc}). Settings → Numbering "
            "seeds one for every tenant at provisioning; a host provisioned before the series "
            "existed repairs it with `manage.py seed_demo --tenant <subdomain>`, which creates "
            "only the missing rows and never overwrites a format a utility has configured. "
            "Refused rather than composing a code by hand, because a code this module invented "
            "would not be the one the Settings screen promises.",
            br_ref="BR-PAY-025",
        ) from exc


def _money(value: Any, *, what: str) -> Decimal:
    """Money is a `Decimal` (hard rule 2). A float is REFUSED, never converted."""
    if isinstance(value, float):
        raise PaymentRuleError(
            f"{what} arrived as a float ({value!r}). Money is NUMERIC(18,6) and never a float "
            "(CLAUDE.md rule 2); it is refused rather than converted, because a conversion hides "
            "the place where money became binary and the reconciliation would report a "
            "difference nobody can reproduce.",
            br_ref="BR-PAY-019",
        )
    if not isinstance(value, Decimal):
        raise PaymentRuleError(
            f"{what} is a {type(value).__name__} ({value!r}); money is a Decimal (rule 2).",
            br_ref="BR-PAY-019",
        )
    return value


def _batch(batch_id: Any) -> bankrec.DepositBatch:
    batch = bankrec.DepositBatch.objects.filter(tenant_id=_tenant_id(), pk=batch_id).first()
    if batch is None:
        raise PaymentRuleError(
            f"deposit batch {batch_id!r} is not one of this tenant's batches (hard rule 1). "
            "Nothing is read and nothing is reconciled.",
            br_ref="BR-PAY-019",
        )
    return batch


def _refuse_if_the_till_is_open(batch: bankrec.DepositBatch) -> None:
    """`P2.10` — a drawer still taking money may not be matched or reconciled.

    ⚠ **AT THE ENDPOINT, NOT BY HIDING A BUTTON** (`BR-SHL-025`, and
    `CR-136-BRC07` §3.4 applies the same reasoning to the three hand-held
    tenders). `P2.10` also keeps an open till's batch off the Deposits list, so
    in the product there is no control to press — but a list filter is a
    rendering decision and this is a money rule, and the two must not be the
    same sentence. `auto_match` is guarded separately at its candidate scan,
    because nothing presses a button there at all.

    **What it prevents, concretely:** reconciling LOCKS the batch
    (`BR-PAY-004`) and `_recompute_total` then refuses the edit, so a till
    reconciled at 14:00 can never account for the money taken after it. The
    clerk's own close would fail on a batch nobody could add to.

    `bankrec.is_bankable` is the SAME expression the list uses, asked of one
    row in the database — see `bankrec_models`.

    ⚠ **THE SENTENCE IS TWO SHORT ONES AND THE REASONING IS UP HERE, ON
    PURPOSE.** This prose reaches a finance lead's screen verbatim as
    `params.detail` (`api._as_catalog_refusal`), so B14 rule 33 binds it: a
    fact ≤ 6 words, an instruction ≤ 6 words per sentence, and **rationale is
    ZERO words on screen**. *"Close the counter first"* is the half they act
    on; why closing settles the total is this docstring's job, and the BR-ID
    travels in `br_ref` rather than in the words (rule 32 — no internal code
    in clerk-facing copy).

    ⚠ **IT TAKES NO `act` ARGUMENT, AND THAT IS A DELETION RATHER THAN AN
    OMISSION.** A first draft named the refused act ("matched to a bank line",
    "reconciled") and interpolated it — which makes the sentence longer than
    rule 33 allows, and a parameter that survives only in a docstring is a
    prop nothing passes (hard-won law 2). The three call sites are already
    distinguishable by the traceback.

    **`batch.code` is a BATCH number, not a database id**, so rule 31 is not
    in play: `DEP-260923-0001` is the series number Settings → Numbering
    allocates and the one a finance lead reads off the screen.
    """
    if bankrec.is_bankable(batch):
        return
    raise PaymentRuleError(
        f"Batch {batch.code} is still at the counter. Close the counter first.",
        br_ref="BR-PAY-025",
    )


def _trail(
    batch: bankrec.DepositBatch,
    event: str,
    *,
    actor: Any,
    occurred_at: datetime,
    **detail: Any,
) -> None:
    """Append one row to the S39 reconciliation trail. Never truncated (0005)."""
    bankrec.DepositBatchEvent.objects.create(
        tenant_id=batch.tenant_id,
        batch=batch,
        event=event,
        actor_id=core_audit.actor_user_id(actor),  # DEF-CUS-9081
        occurred_at=occurred_at,
        detail=detail,
    )


def _require_moment(value: Any, what: str) -> datetime:
    """BR-TEN-043 — the caller names the moment; nothing here reads a clock."""
    if not isinstance(value, datetime):
        raise PaymentRuleError(
            f"{what} must be a datetime supplied by the caller (BR-TEN-043, gate G6): a resumed "
            "batch run, a replay and a re-run must stamp the SAME moment rather than three, "
            "which is impossible if this module reads the clock itself.",
            br_ref="BR-TEN-043",
        )
    return value


# ── CS-18 · the difference reasons are a LIST now, not free text ────────────
def live_difference_reasons() -> dict[str, str]:
    """The tenant's ACTIVE difference reasons, as `lower(code) → the stored code`.

    CS-18's new rule: *"Reconciliation difference reasons are a seeded,
    tenant-extensible list, deactivated and never deleted, like every other
    reference list."* This is the read the write paths check against, and it is
    published so the S40 picker and the S8 card can offer the same set.

    Keyed case-insensitively because `uq_bank_rec_diff_reasons_code_ci` is, and
    the VALUE is the list's own spelling: a resolution stores what the list
    calls it, so `difference_report` groups `Bank_Fee` and `bank_fee` as one
    cause instead of two.
    """
    return {
        str(code).lower(): str(code)
        for code in bankrec.BankRecDifferenceReason.objects.filter(
            tenant_id=_tenant_id(), active=True
        ).values_list("code", flat=True)
    }


def _canonical_reason(raw: Any, *, where: str, reasons: dict[str, str] | None) -> str:
    """BR-PAY-019's *reason*, checked against the tenant's list when there is one.

    ⚠ **AN EMPTY LIST ACCEPTS ANY NON-BLANK REASON, AND THAT IS REQUIRED RATHER
    THAN LENIENT.** `bank_rec_difference_reasons` is a DISCRETIONARY reference
    list, so a tenant whose S111 "load standard reference data" toggle was OFF
    has none (BR-TEN-067 — only the STRUCTURAL lists always seed), and every
    tenant provisioned before today has none either. Refusing on an empty list
    would make bank reconciliation impossible for all of them the day this
    change lands — a control that breaks the workflow it governs. So the rule
    bites the moment a tenant HAS a vocabulary, which is the moment it means
    anything, and `RECONCILE_UNAVAILABLE`'s sibling in the read layer says which
    state a tenant is in.
    """
    code = str(raw or "").strip()
    if not code:
        raise PaymentRuleError(
            f"{where} carries no reason. BR-PAY-019 requires a reason AND a GL account on "
            "every difference — the prototype's 'Force match anyway' is permanently "
            "SUPERSEDED (BR-PAY-035), so an unexplained residual has no path to reconcile.",
            br_ref="BR-PAY-019",
        )
    if not reasons:
        return code
    canonical = reasons.get(code.lower())
    if canonical is None:
        offered = ", ".join(sorted(reasons.values())) or "(none)"
        raise PaymentRuleError(
            f"{where} names the reason {code!r}, which is not one of this utility's "
            f"reconciliation difference reasons. The list is Settings → Configure → Reference "
            f"data → Bank reconciliation reasons, and it offers: {offered}. Free text was "
            "replaced by a list so a finance user can ask how much of this quarter's difference "
            "was processor fees and how much was error (CS-18); a code nobody can group by "
            "answers neither question. Add the reason to the list, or pick one.",
            br_ref="BR-PAY-019",
        )
    return canonical


# ── US-PAY-020 · cutting the day's batches ──────────────────────────────────
# ═══════════════════════════════════════════════════════════════════════════
# CR-186-BRC10 · WHO OWNS A DEPOSIT: A TILL, OR A CHANNEL FOR ONE DAY
# ═══════════════════════════════════════════════════════════════════════════
# PO 2026-10-21, *"this is correct"*, to the table: Dana's till · 14 Oct (cash
# $300 + cheques $500 = ONE batch, $800.00), Sam's till · 14 Oct, Invoice
# Cloud · 14 Oct, Paymentus · 14 Oct, Lockbox · 14 Oct — five batch IDs.
#
# **THE OWNER DESIGN, AND WHY IT IS THE SYSTEM TILL RATHER THAN A KEY ON THE
# BATCH** (decision log 2026-10-21, lane PAY-CORE): a channel's day is a
# SYSTEM TILL with `channel` set (`counter_sessions.channel`, `payments/0051`),
# one per (tenant, day, channel). Every existing reader of *whose deposit is
# this* already walks `deposit_batches.session` — the Deposits list, the
# bankable rule, the counter screens, `trg_deposit_batch_needs_session` — so a
# channel lands on all of them without a second owner column to keep in step.
# A key on the batch would have been a second answer to the same question.
#
# **THE CHANNEL VOCABULARY.** A webhook, an agent or a partner names its
# provider in the idempotency reference (`webhook|invoice_cloud:TID161007`,
# `agent|pay_uspayments:…`), so the provider IS the channel — Invoice Cloud and
# Paymentus never share a batch. A remittance file is `lockbox`. Money a clerk
# keys in with no till (card or ACH taken over the phone, a move-in fee) is
# `office`. A caller may name the channel outright (`record_payment(
# deposit_channel=…)`), which beats the derivation.

#: What a payment may be in to be banked. `cleared` is for the rows written
#: before 2026-10-21; every new payment is `posted` (PO: *"first they will pot
#: the payment"*).
STAMPABLE_STATUSES = (models.PAYMENT_POSTED, models.PAYMENT_CLEARED)

#: A batch still taking members. `matched` has a bank line tied to its total
#: and `reconciled` is LOCKED (BR-PAY-004), so neither takes another payment —
#: a payment posted for such a day joins the next cut day's batch instead.
OPEN_BATCH_STATUSES = (bankrec.BATCH_IN_TRANSIT, bankrec.BATCH_UNMATCHED)

CHANNEL_OFFICE = "office"
CHANNEL_LOCKBOX = "lockbox"
CHANNEL_IMPORT = "import"
CHANNEL_AGENT = "agent"
CHANNEL_WEBHOOK = "online"


CHANNEL_STORE_PREFIX = "store:"


def channel_for(
    *,
    origin: str | None,
    reference: Any = None,
    explicit: str | None = None,
    network: str | None = None,
) -> str:
    """The provider or channel a till-less payment banks under. Pure.

    `reference` is the idempotency REFERENCE (`invoice_cloud:TID161007`), never
    the composed key. A reference without a `provider:` prefix falls back to
    the origin's own channel.

    `network` is the store payment network a payments file's **Network** column
    named (`payments.store_network`, PO 2026-10-30 Q6: *"can you add network
    name as part of csv file / excel file do not add it on screen"*). A named
    network banks in its OWN channel, `store:<name lowercased>` — so a day's
    lockbox file and its Hy-Vee file are two batches, and *Hy-Vee* and *hy-vee*
    are one. A blank or absent name keeps today's channel (the lockbox).
    """
    if explicit is not None and str(explicit).strip():
        return str(explicit).strip().lower()
    store = " ".join(str(network or "").split()).lower()
    if store:
        return f"{CHANNEL_STORE_PREFIX}{store}"
    text = "" if reference is None else str(reference)
    head, sep, _tail = text.partition(":")
    provider = head.strip().lower() if sep else ""
    if origin in ("webhook", "agent") and provider:
        return provider
    if origin == "import":
        # A remittance or lockbox file. Its reference is the file's own
        # `batch:row` handle, never a provider, so it is never parsed for one.
        return CHANNEL_LOCKBOX
    if origin == "webhook":
        return CHANNEL_WEBHOOK
    if origin == "agent":
        return CHANNEL_AGENT
    return CHANNEL_OFFICE


def channel_of_payment(payment: Any) -> str:
    """`channel_for`, read back off a stored row — its origin and its key."""
    key = getattr(payment, "webhook_key", None) or ""
    _source, _sep, reference = str(key).partition("|")
    return channel_for(
        origin=getattr(payment, "origin", None),
        reference=reference or None,
        network=getattr(payment, "store_network", None),
    )


def _channel_batch(*, tenant_id: Any, day: date, channel: str) -> Any:
    """The channel's all-tenders batch for one day, or None. A read."""
    return (
        bankrec.DepositBatch.objects.filter(
            tenant_id=tenant_id,
            session__system_day=day,
            session__channel=channel,
            method__isnull=True,
        )
        .select_related("session")
        .first()
    )


def banked_members(batch: Any) -> Any:
    """The members whose money goes to the bank — every member but a CANCELLED one.

    ONE definition with three readers: the batch total, the reconciliation's
    credit split and the per-tender totals. A payment cancelled while its batch
    was open (`cancel.cancel_payment`, `CR-186-BRC10`) keeps its membership —
    the stamp is write-once — and its receipt and its cancel net to nothing in
    the holding account, so it is not money the bank will show.
    """
    return models.Payment.objects.filter(
        tenant_id=batch.tenant_id, deposit_batch_id=batch.pk
    ).exclude(status=models.PAYMENT_CANCELLED)


def tender_totals(batch: Any) -> list[dict[str, Any]]:
    """A batch's total PER TENDER — PO 2026-10-21 ruling 3, worked: Dana · 14 Oct
    = cash **$300.00** + cheques **$500.00** = **$800.00**. Grouped in SQL."""
    rows = (
        banked_members(batch)
        .values("method__code", "method__name")
        .annotate(amount=Sum("amount"), count=Count("id"))
        .order_by("method__code")
    )
    return [
        {
            "method_code": row["method__code"],
            "method_name": row["method__name"],
            "amount": row["amount"] if row["amount"] is not None else ZERO,
            "count": row["count"],
        }
        for row in rows
    ]


@dataclass(frozen=True)
class StampedBatch:
    """Which batch a payment joined at posting — or why it joined none yet."""

    batch: Any = None
    deferred_reason: str | None = None


def batch_for_new_payment(
    *,
    tenant_id: Any,
    posted_on: date,
    payment_type: str,
    amount: Decimal,
    bankable_from: date | None,
    counter_session: Any = None,
    channel: str | None = None,
    actor: Any = None,
    occurred_at: datetime | None = None,
) -> StampedBatch:
    """The batch a payment is stamped into AT POSTING (`CR-186-BRC10` ruling 2).

    PO, verbatim: the batch ID *"is stamped the moment the payment is posted,
    for every method"*. Called INSIDE `record_payment`'s transaction, so a
    rolled-back payment opens no batch and burns no `DEP-` number.

    Three cases join NO batch, each named rather than silent:
      * a credit, an adjustment or a negative row — not money for the bank;
      * a post-dated cheque taken without a till — the cut banks it on its day;
      * a channel whose batch for that day is already matched or reconciled —
        the next cut day's batch takes it (`cut_deposit_batches`), keeping the
        payment's own posting date. A cut is what knows which day *today* is;
        this function reads no clock (BR-TEN-043).
    """
    if payment_type != models.PAYMENT_TYPE_PAYMENT or amount <= ZERO:
        return StampedBatch(deferred_reason="not_bankable_money")
    if counter_session is not None:
        batch, _created = _get_or_create_batch(
            tenant_id=tenant_id,
            # The TILL's drawer day, never the payment's posting date: a shift
            # is one drawer day even when a backdated entry is keyed into it.
            day=counter_session.opened_at.date(),
            session=counter_session,
        )
        return StampedBatch(batch=batch)
    if bankable_from is not None and bankable_from > posted_on:
        return StampedBatch(deferred_reason="held_until_bankable")
    owner = channel or CHANNEL_OFFICE
    existing = _channel_batch(tenant_id=tenant_id, day=posted_on, channel=owner)
    if existing is not None and existing.status not in OPEN_BATCH_STATUSES:
        return StampedBatch(deferred_reason="day_batch_already_sealed")
    if existing is not None:
        return StampedBatch(batch=existing)
    session = _system_session(tenant_id=tenant_id, day=posted_on, channel=owner)
    batch, created = _get_or_create_batch(tenant_id=tenant_id, day=posted_on, session=session)
    if created and occurred_at is not None:
        # The S39 trail and hard rule 7 start where the batch does — at the
        # first payment that opens a channel's day, as the cut's batches did.
        # The trail row names no actor: a posting door may be a partner, a
        # webhook or a kiosk with no user row behind it; the audit row below
        # carries whoever posted the payment (hard rule 7).
        _trail(batch, bankrec.EVENT_CREATED, actor=None, occurred_at=occurred_at,
               channel=owner, opened_by="posting")
        core_audit.money_action(
            actor,
            AUDIT_BATCH_CREATED,
            "deposit_batch",
            str(batch.pk),
            after={
                "code": batch.code,
                "method": None,
                "channel": owner,
                "deposited_on": posted_on.isoformat(),
                "session_id": str(session.pk),
                "session_is_system": True,
                "job": None if actor is not None else "payments.record",
            },
        )
    return StampedBatch(batch=batch)


def refresh_batch_total(batch: Any) -> Decimal:
    """Re-foot an OPEN batch after a member joined or was cancelled. A batch
    that is matched or reconciled is left exactly as it is (BR-PAY-004)."""
    if batch.status not in OPEN_BATCH_STATUSES:
        return batch.recorded_total
    return _recompute_total(batch)



def cut_deposit_batches(*, actor: Any, day: date, occurred_at: datetime) -> CutResult:
    """Sweep posted money that joined no batch at posting into its owner's batch.

    ⚠ **AMENDED 2026-10-21 (`CR-186-BRC10`, PO: one batch per till or provider
    per day, all tenders, stamped AT POSTING).** Since that change
    `record_payment` stamps every payment's batch when it is posted, so this
    sweep banks only what joined none: a payment for a day whose batch was
    already matched or reconciled (it joins THIS cut day's batch, keeping its
    own posting date), a post-dated cheque that has become bankable, and the
    rows written before the change. It groups by OWNER (a till, or a channel's
    system till) and day — never by tender — and selects `posted` and
    `cleared`. The paragraphs below describe the per-tender cut it replaced;
    the type, amount, hold and method exclusions and hard rule 6 are unchanged.

    **The day is the POSTING day** — the physical drawer day (PO ruling RQ-5 /
    BR-REP-013 / BR-PAY-025), never the day the bank credits it.

    Which payments join, and why each filter is there rather than implied:

      * `status = cleared` — money that actually arrived (BR-PAY-021's own
        definition of clearing). A `processing` payment is not in the drawer,
        and migration 0005 refuses to stamp one anyway.
      * `type = payment` and `amount > 0` — a credit, an adjustment or an NSF
        reversing row is not money that went to the bank. The reversing row's
        exact shape belongs to the NSF lane (BR-PAY-013); excluding negative and
        non-payment rows means this batching cannot be wrong about it.
        ⚠ **THE TYPE TEST MOVED OUT OF THE QUERY AND INTO THE LOOP ON
        2026-09-02 (CR-059 CS-35), AND THE REASON IS NOT STYLE.** It was
        `type=PAYMENT_TYPE_PAYMENT` in the `filter()`, so a credit or an
        adjustment on that drawer day was **dropped before this function could
        see it** — invisible, unmentioned, indistinguishable from a day that had
        none. CS-35 requires that such a row is *"named in the result rather
        than dropped"*, and it matters on the one day it matters: a clerk
        reconciling a drawer that does not tie needs to be told that 25.00 of
        what they are looking at was a concession and was never going to the
        bank. **The SET THAT GETS BATCHED IS UNCHANGED** — the same rows are
        excluded, by the same test, one layer later — which is what makes this
        safe to do on a money path. The type check runs FIRST inside the loop,
        before the amount and method checks, so a tenderless credit is reported
        as a credit rather than as "no method".
      * `deposit_batch_id IS NULL` — membership is write-once (0005), so a
        payment already banked is never re-banked. This is also what makes a
        second call on the same day a no-op (hard rule 6).
      * **`bankable_from` is in the past, or absent** — CR-059 CS-30's fourth
        rule, ruled by the PO on 2026-09-01: *"a cheque dated in the future is
        held out of the batch cut until its date, and named on the day it
        becomes bankable."* A post-dated cheque is REAL money the utility is
        holding and a real payment row; what it is not is money the bank will
        honour today, and depositing it is how a utility gets a returned item
        and a fee for an instrument the customer told them to hold. **Held rows
        are NAMED in the result, never dropped** — the same rule CS-35 imposed
        on a credit one clause up, and for the same reason: a drawer that does
        not tie has to be explainable. The hold is read from `bankable_from`
        alone and is never derived from `cheque_date`, because a utility may
        agree to hold a cheque past its own date and a cheque dated last week is
        bankable today.
      * a payment with NO method is SKIPPED and reported: `deposit_batches.method`
        is NOT NULL and B2 leaves `payments.method` nullable for exactly the
        rows this filter already excludes.

    ⚠ **RE-KEYED 2026-09-22 (`P0.6`): THE BATCH IS KEYED ON (tenant, SESSION,
    method), NOT ON THE DAY.** A batch is one till and one tender — PO,
    `OQ-PAY-12577` (a) — because a bank credits cash and cheques separately
    and they clear on different days. Dana's shift taking **$600 cash and $640
    cheques** is ONE till, TWO tenders and **two batches**, totalling $1,240.

    ⚠ **AMENDED 2026-09-23 BY `P2.13` / `DEF-PAY-6226`. THIS PARAGRAPH READ
    *"TODAY EVERY PAYMENT BANKS UNDER THE DAY'S SYSTEM TILL, BECAUSE NO
    PAYMENT CARRIES A SESSION YET"* AND IT NO LONGER DOES.** A counter payment
    now names its till and its till's batch in its own INSERT, so it is
    **never a candidate here at all**: the `deposit_batch_id IS NULL` filter
    above excludes it before the loop sees it — not skipped-and-reported,
    filtered. Hard rule 6 is unchanged and so is the arithmetic: a till's
    money is footed by `counters._seal_batches` at close, and this cut goes on
    grouping exactly what it always grouped, which is everything nobody's
    hands touched. Phase 0 predicted *"only `_session_for` changes"*; the
    group key had to change with it, and that comment says why.

    Idempotent, still: calling this twice cuts nothing the second time, because
    the session is found rather than re-made (`uq_counter_sessions_system_day`)
    and the batch is found rather than re-cut
    (`uq_deposit_batches_session_method`). Hard rule 6, applied to a grouping.
    """
    tenant_id = _tenant_id()
    occurred_at = _require_moment(occurred_at, "the moment the batches were cut")
    if not isinstance(day, date) or isinstance(day, datetime):
        raise PaymentRuleError(
            "the drawer day must be a date (BR-PAY-025 as amended 2026-09-22 groups a TILL × a "
            "tender, and the day is the "
            "POSTING day per the PO's RQ-5 ruling).",
            br_ref="BR-PAY-025",
        )

    # ⚠ **CR-186-BRC10 (PO 2026-10-21): `posted` AND `cleared`, and a payment
    # from an EARLIER day is swept too.** Every new payment is `posted` and is
    # stamped into its batch the moment it is posted (`record_payment`), so
    # what reaches this sweep is the stragglers: a payment whose own day's
    # batch was already matched or reconciled when it was posted (it joins
    # THIS cut day's batch, keeping its own posting date — *"A payment posted
    # for a day whose batch is already reconciled … joins today's batch"*), a
    # post-dated cheque that has become bankable, and the rows written before
    # the change. `cleared` stays in the filter for those legacy rows.
    candidates = (
        models.Payment.objects.filter(
            tenant_id=tenant_id,
            status__in=STAMPABLE_STATUSES,
            deposit_batch_id__isnull=True,
            posted_at__date__lte=day,
        )
        # An earlier day's credit, adjustment or reversing row is never
        # bankable and was already named on its own day's cut — filtered in
        # SQL so the sweep does not re-read every one of them every night.
        .filter(Q(posted_at__date=day) | Q(type=models.PAYMENT_TYPE_PAYMENT, amount__gt=ZERO))
        .select_related("method")
        .order_by("posted_at", "id")
    )

    # The group key is the OWNER and the DAY: a till, or a channel's system
    # till for one day (`CR-186-BRC10`). All tenders share the batch; the
    # tender is no longer part of the key.
    by_group: dict[tuple[Any, Any, date], list[models.Payment]] = {}
    skipped: list[dict[str, Any]] = []
    for payment in candidates:
        # CR-059 CS-35, and it is FIRST on purpose: a credit carries no tender,
        # so testing the method before the type would report the right exclusion
        # under the wrong name and send a clerk to the payment-methods screen.
        if payment.type != models.PAYMENT_TYPE_PAYMENT:
            if payment.posted_at.date() != day:
                continue  # named on its own day's cut, not on every later one
            skipped.append(
                {
                    "payment_id": str(payment.pk),
                    "payment_no": payment.payment_no,
                    "reason": "not_cash",
                    # CR-059 CS-35, in this comment rather than in the sentence
                    # (gate G28): a clerk reading a drawer that does not tie
                    # wants the reason, not a register to go and look up.
                    "detail": f"a {payment.type} is not money that went to the bank — no "
                    "cash arrived, no bank line will ever mention it, and batching one "
                    "would put the day's takings permanently out against the drawer. It is "
                    "named here rather than dropped so a drawer that does not tie can be "
                    "explained.",
                }
            )
            continue
        if payment.amount <= ZERO:
            if payment.posted_at.date() != day:
                continue
            skipped.append(
                {
                    "payment_id": str(payment.pk),
                    "payment_no": payment.payment_no,
                    "reason": "not_positive_money",
                    "detail": "a reversing or negative row is not money that went to the bank "
                    "(BR-PAY-013's reversal is a NEW row); it joins no drawer batch.",
                }
            )
            continue
        # ── CR-059 CS-30 · the post-dated hold (BR-PAY-883) ────────────────
        # Compared against the DRAWER DAY the caller named and never against a
        # clock (BR-TEN-043, gate G6).
        if payment.bankable_from is not None and payment.bankable_from > day:
            skipped.append(
                {
                    "payment_id": str(payment.pk),
                    "payment_no": payment.payment_no,
                    "reason": "held_until_bankable",
                    "bankable_from": payment.bankable_from.isoformat(),
                    "detail": f"this cheque may not be banked until "
                    f"{payment.bankable_from.isoformat()}, so it is held out of the cut and "
                    "stays in the drawer. The money is real and the payment row stands; "
                    "depositing it today is how a utility gets a returned item and a fee for "
                    "an instrument the customer asked them to hold.",
                }
            )
            continue
        if payment.method_id is None:
            skipped.append(
                {
                    "payment_id": str(payment.pk),
                    "payment_no": payment.payment_no,
                    "reason": "no_method",
                    "detail": "a batch carries a total per tender (BR-PAY-025 as amended "
                    "2026-10-21), and a payment recorded without an instrument cannot be "
                    "totalled under one; it is reported rather than dropped into a guessed "
                    "tender.",
                }
            )
            continue
        session_id = getattr(payment, "counter_session_id", None)
        channel = None if session_id is not None else channel_of_payment(payment)
        # Its own posting day's batch when that one still takes money; THIS
        # cut day's batch when its own is already matched or reconciled.
        own_day = payment.posted_at.date()
        target_day = own_day
        if session_id is None and own_day != day:
            own = _channel_batch(tenant_id=tenant_id, day=own_day, channel=channel)
            if own is not None and own.status not in OPEN_BATCH_STATUSES:
                target_day = day
        by_group.setdefault((session_id, channel, target_day), []).append(payment)

    summaries: list[BatchSummary] = []
    batched = 0
    with transaction.atomic():
        for (session_id, channel, target_day), payments in by_group.items():
            if session_id is not None:
                session = _session_for(payments[0], tenant_id=tenant_id, day=target_day)
            else:
                session = _system_session(tenant_id=tenant_id, day=target_day, channel=channel)
            batch, created = _get_or_create_batch(
                tenant_id=tenant_id, day=target_day, session=session
            )
            if batch.status not in OPEN_BATCH_STATUSES:
                # A cut re-run for a day whose batch is already matched or
                # reconciled cannot add to it (BR-PAY-004) — named, never forced.
                skipped.extend(
                    {
                        "payment_id": str(p.pk),
                        "payment_no": p.payment_no,
                        "reason": "batch_already_sealed",
                        "detail": f"deposit batch {batch.code} is {batch.status}, so it takes "
                        "no more money. The next day's cut banks this payment.",
                    }
                    for p in payments
                )
                continue
            # The membership stamp. `.update()` rather than `.save()` because a
            # posted payment is frozen except for this one column, and the
            # database trigger (0005, body from 0051) permits it — once.
            stamped = models.Payment.objects.filter(
                tenant_id=tenant_id, pk__in=[p.pk for p in payments], deposit_batch_id__isnull=True
            ).update(deposit_batch_id=batch.pk)
            batched += stamped
            total = _recompute_total(batch)
            _trail(
                batch,
                bankrec.EVENT_CREATED if created else bankrec.EVENT_REGROUPED,
                actor=actor,
                occurred_at=occurred_at,
                payments_added=stamped,
                recorded_total=str(total),
            )
            core_audit.money_action(
                actor,
                AUDIT_BATCH_CREATED if created else AUDIT_BATCH_REGROUPED,
                "deposit_batch",
                str(batch.pk),
                after={
                    "code": batch.code,
                    "method": None,
                    "channel": session.channel,
                    "deposited_on": batch.deposited_on.isoformat(),
                    # `P0.6` — hard rule 7: which drawer this deposit came out
                    # of is part of what a money action recorded.
                    "session_id": str(batch.session_id),
                    "session_is_system": session.system_day is not None,
                    "payments_added": stamped,
                    "recorded_total": str(total),
                    "job": None if actor is not None else "payments.cut_deposit_batches",
                },
            )
            summaries.append(
                BatchSummary(
                    batch_id=str(batch.pk),
                    code=batch.code,
                    method_code=None,
                    deposited_on=batch.deposited_on,
                    recorded_total=total,
                    payment_count=len(payments),
                    status=batch.status,
                    created=created,
                )
            )
    return CutResult(
        day=day,
        batches=tuple(sorted(summaries, key=lambda row: row.code)),
        payments_batched=batched,
        skipped=tuple(skipped),
    )


def _session_for(payment: models.Payment, *, tenant_id: Any, day: date) -> Any:
    """Which till this payment's deposit banks under — its own, or the system's.

    **PHASE 2 CHANGED THIS FUNCTION AND ONLY THIS FUNCTION, AS PHASE 0 SAID IT
    WOULD** (`CR-136-BRC07` `P2.13`, `DEF-PAY-6226`). A payment that names a
    till banks under THAT till; every payment that does not banks under the
    day's system till, which is openly nobody's.

    **PO ruling 2026-09-22, verbatim:** *"we have to make process uniform for
    all hence we should geneate system generated till"*. The case that forced
    it: four of the seven seeded tenders — **ACH, card, wire and lockbox** —
    never touch a counter, and a utility taking **$14,280 of ACH** on a Tuesday
    has no clerk, no drawer and no till. Built with a counter-only guard it
    could not have banked that money at all. The fallback is therefore the
    rule's own second half, not a stand-in.

    ⚠ **IN PRACTICE A COUNTER PAYMENT NEVER REACHES THIS FUNCTION, AND THE
    BRANCH IS HERE ANYWAY.** `record_payment` stamps `deposit_batch_id` in the
    same INSERT as the till (*"The id attaches when taken. Not at close."*),
    and `cut_deposit_batches` selects on `deposit_batch_id IS NULL` — so a
    till's money is filtered out before the loop sees it. What this branch
    covers is every row that took some other road: the rows `payments/0035`
    left NULL, a counter payment whose batch was somehow never stamped, and
    the two hand-recording doors `api.py` names as NOT calling the till guard
    (`POST /customers/{id}/payments` and the transfer path, `OQ-PAY-12601`).
    Answering the system till for those would put a clerk's money in a drawer
    nobody owns, silently — which is the whole defect this repaired.

    ⚠ **THE TENANT CHECK IS NOT BELT AND BRACES.** `counter_session_id` has no
    referential integrity (`payments/0035` states that rather than leaving it
    to be found), so a stale or foreign id must resolve to nothing and fall
    back rather than raise in the middle of a nightly cut.
    """
    session_id = getattr(payment, "counter_session_id", None)
    if session_id is not None:
        from apps.payments import counter_session_models as tills

        own = tills.CounterSession.objects.filter(
            tenant_id=tenant_id, pk=session_id
        ).first()
        if own is not None:
            return own
    return _system_session(tenant_id=tenant_id, day=day)


def _system_session(*, tenant_id: Any, day: date, channel: str | None = None) -> Any:
    """The day's system till — one per tenant per banking day, created closed.

    **It is openly nobody's**: no owner, no service centre, no closer, no float
    and `close_kind = 'system'`. `ck_counter_sessions_system_is_nobodys`
    enforces every one of those, in both directions, so a person's till can
    never be written without an owner either.

    ⚠ **IT IS BORN CLOSED, AND THAT IS WHAT KEEPS IT OFF THE SUPERVISOR'S
    SCREEN.** Phase 2's own *done when* is *"a supervisor can see the three
    tills nobody counted"*, and that list asks `closed_at IS NULL`. A till that
    is closed from its first moment never answers it, so the screen needs no
    knowledge of system tills and cannot drift out of step with this rule.
    There is nothing to force-close either: a System Admin's forced close is
    for a person who went home without counting.

    ⚠ **ONE PER DAY, NOT ONE PER TENANT AND NOT ONE PER TENDER.** Per tenant
    would put every day's ACH into one batch for ever; per tender would make
    a till mean a tender, which it does not. A day is the unit the cut is
    called for, and `uq_counter_sessions_system_day` is what makes two cuts
    racing on one day share one till rather than each opening its own — a
    partial index rather than a service check, for `P0.4`'s stated reason.

    `opened_at`/`closed_at` bracket the drawer day itself. They are not a
    shift: nobody worked it. `system_day` is the column anything should key
    on, and it is separate from `opened_at` precisely so a later lane moving
    a timestamp cannot break the idempotency silently.
    """
    from apps.payments import counter_session_models as tills

    # ⚠ **CR-186-BRC10 (PO 2026-10-21): ONE PER DAY PER CHANNEL.** Invoice
    # Cloud, Paymentus and a lockbox file each bank under their own system
    # till, so each has its own batch ID for the day. `channel=None` answers
    # the channel-less till opened before the change and is kept only so a
    # legacy row still resolves to where it always did.
    existing = tills.CounterSession.objects.filter(
        tenant_id=tenant_id, system_day=day, channel=channel
    ).first()
    if existing is not None:
        return existing
    # ⚠ **TIMEZONE-AWARE, AND `datetime.combine` ALONE IS NOT.** Django warns
    # `received a naive datetime while time zone support is active` and then
    # stores it interpreted in the default zone, which puts the till a few
    # hours either side of the day it is named for. `system_day` is the column
    # anything should key on — that is why it exists — but a stored moment that
    # disagrees with it would still be read by a human one day.
    #
    # Midnight UTC of the drawer day, bracketing it at both ends: a system till
    # is not a shift and nobody worked it, so there is no real opening moment
    # to record and inventing one from a clock would breach BR-TEN-043.
    moment = datetime.combine(day, time.min, tzinfo=UTC)
    return tills.CounterSession.objects.create(
        tenant_id=tenant_id,
        owner=None,
        service_centre=None,
        system_day=day,
        opening_float=ZERO,
        opened_at=moment,
        closed_at=moment,
        closed_by=None,
        close_kind=models.COUNTER_CLOSE_SYSTEM,
        counted_totals=None,
        channel=channel,
    )


def _get_or_create_batch(
    *, tenant_id: Any, day: date, session: Any, **_ignored: Any
) -> tuple[bankrec.DepositBatch, bool]:
    """The one batch for (tenant, SESSION), all tenders, created if this is its first money.

    ⚠ **RE-KEYED AGAIN 2026-10-21 BY `CR-186-BRC10`.** PO, verbatim: *"this is
    one batch only - it will ahve 1 batch ID not 2"* (Dana's cash and cheques)
    and *"no it will be sepearte batch iD"* (Paymentus beside Invoice Cloud).
    So the key is the till — a person's, or a channel's system till for one
    day — and the batch holds every tender, with `method` NULL and a total per
    tender read from its members (`tender_totals`). `uq_deposit_batches_
    session_all_tenders` is the database's half. `**_ignored` swallows the
    `method_id`/`method_code` an older caller may still pass; the tender no
    longer chooses the batch.

    ⚠ **RE-KEYED 2026-09-22 BY `P0.6`.** It was `(tenant, day, method)` — the
    grouping half of BR-PAY-025, which the PO superseded that day. A day ×
    method batch is the whole utility's takings, so at a two-counter office
    Dana's **$1,240** of cheques and Sam's **$880** were one row neither clerk
    could be held to. The day still ties to **$2,120**; it is now two deposits,
    which is what the bank sees and what the ledger already posted correctly.

    **The code is ALLOCATED, not composed** — see `_allocate_batch_code`. The
    allocation happens inside the caller's `transaction.atomic()`, which is
    `BR-TEN-035`'s own requirement.

    ⚠ **THE COLLISION GUARD IS KEPT AND ITS MEANING HAS CHANGED.** It used to
    catch a tenant-configured format that could not tell two DAYS apart. The
    series counter is monotonic, so what it catches now is a format edited to
    collide with a code some OTHER row already holds — most plausibly one of
    the composed `DEP-260808-CHK` codes from before this change. The failure
    mode is still money rather than a stack trace: two populations' takings
    crossing into one batch would tie out against a statement that never
    contained them. Refused by name, with the batch that owns the code.
    """
    existing = bankrec.DepositBatch.objects.filter(
        tenant_id=tenant_id, session=session, method__isnull=True
    ).first()
    if existing is not None:
        return existing, False

    code = _allocate_batch_code(day)
    clash = bankrec.DepositBatch.objects.filter(tenant_id=tenant_id, code=code).first()
    if clash is not None:
        raise PaymentRuleError(
            f"deposit batch code {code!r} already belongs to the batch of "
            f"{clash.deposited_on.isoformat()}, so this {day.isoformat()} batch cannot be cut. "
            "B2 §2 makes the code UNIQUE per tenant, and the code is allocated from this "
            "tenant's `deposit_batch` number series (Settings → Numbering, PO ruling "
            "2026-09-22). A collision means that series' format has been edited to a shape "
            "that can repeat — most likely one that now renders a code an older batch already "
            "carries, since batches banked before 2026-09-22 have composed codes such as "
            "`DEP-260808-CHK` and keep them for ever (hard rule 4). Refused rather than "
            "crossing two batches' money into one, which would tie out against a bank "
            "statement that never contained it.",
            br_ref="BR-PAY-025",
        )
    batch = bankrec.DepositBatch.objects.create(
        tenant_id=tenant_id,
        code=code,
        session=session,
        method_id=None,
        deposited_on=day,
        recorded_total=ZERO,
        status=bankrec.BATCH_IN_TRANSIT,
    )
    return batch, True


def _recompute_total(batch: bankrec.DepositBatch) -> Decimal:
    """`recorded_total` = Σ member payments — an assertion, not a rounding event.

    US-PAY-020 §7, verbatim: *"recorded_total = Σ member payments — an
    assertion, not a rounding event (members are finalized 2dp amounts)"*. So
    there is no `quantize` here and no float: PE-10's 292.87 + 142.30 + 36.22 is
    **471.39** by Decimal addition and by nothing else.

    Refuses on a LOCKED batch (BR-PAY-004). That refusal is the same one the
    database makes, one layer up, so the SQLite developer database behaves like
    production.

    **It refused as an OPEN QUESTION until 2026-08-12 and now refuses as a
    RULE.** The old message said the choice between the lock and the tie-out was
    not this lane's to make; the PO made it, and the answer was that the lock
    HOLDS — so a locked batch's total never moves and recomputing it is exactly
    the in-place edit hard rule 4 forbids. Nothing about the behaviour changed;
    what changed is that it is now a settled refusal with a rule behind it
    rather than a parked one (see `assert_bounce_allowed` for the other half).
    """
    if batch.status == bankrec.BATCH_RECONCILED:
        raise PaymentRuleError(
            f"deposit batch {batch.code} is RECONCILED and LOCKED (BR-PAY-004), so its total "
            "cannot be recomputed: that would be an in-place edit of a signed-off money record "
            "(hard rule 4). US-PAY-022 TC-2 recomputes the total for the UNLOCKED case only. "
            "After the lock the total does NOT move — PO ruling 2026-08-12: DEP-260805-CHK stays "
            "$2,840.00 when cheque #4021's $100.00 is returned three weeks later, because the "
            "bank statement it was agreed against did not change. The bounce is new rows (the "
            "reversing payment plus the utility's bounce fee), recorded in payments.",
            br_ref="BR-PAY-004",
        )
    # ⚠ CR-186-BRC10: a member CANCELLED while the batch was open is not
    # money that goes to the bank (its receipt and its cancel net to nothing
    # in the holding account), so it leaves the total. `banked_members` is the
    # one definition, shared with the reconciliation's credit split.
    total = banked_members(batch).aggregate(total=Sum("amount"))["total"]
    total = total if total is not None else ZERO
    batch.recorded_total = total
    batch.save(update_fields=["recorded_total", "updated_at"])
    return total


def recompute_batch_total(batch_id: Any) -> Decimal:
    """Public form of the recompute — for the NSF lane's UNLOCKED case."""
    return _recompute_total(_batch(batch_id))


def assert_bounce_allowed(payment: Any) -> None:
    """The NSF lane's boundary — **a LOCKED batch does not stop a bounce.**

    **WHAT THIS FUNCTION USED TO DO, AND WHY IT WAS RIGHT AT THE TIME.** Until
    2026-08-12 it refused by name, citing OQ-134, for any payment sitting in a
    RECONCILED batch. The claim was: a cheque that bounces three weeks after its
    batch was reconciled leaves the locked batch saying $2,840.00 for a day where
    $100.00 came back, and the three ways out — the locked batch never changes,
    unreconcile → correct → reconcile again, or a visible reducing entry against
    the batch — were a finance call nobody had made. **That refusal was correct
    while the question stood**, and it is written down rather than deleted so the
    next reader meets the reasoning and not just its absence.

    **PO ruling, 2026-08-12 (OQ-134 CLOSED), verbatim:** *"if this happen Utility
    will charge Cheque bounce charges and add new entry - this will be mnaul
    process by utility user in payments or in finance we have to decide the place
    - you decide for me"*. **The lock HOLDS.** Worked on the prototype fixture:
    DEP-260805-CHK is 8 cheques recorded at **$2,840.00**, reconciled and locked;
    three weeks later cheque #4021 (**$100.00**) is returned. The batch total
    stays **$2,840.00** — the bank statement it was agreed against did not
    change, and rewriting it to $2,740.00 would edit a signed-off money record in
    place, which hard rule 4 forbids. The bounce is the ordinary reversing row
    plus the utility's bounce fee, both NEW rows.

    So this function now says YES to a locked batch, and `_recompute_total`
    refuses the recompute from the other side — together that is the ruling: the
    bounce happens, the tie-out does not move.

    **THE PLACEMENT HALF WAS DELEGATED AND DECIDED: PAYMENTS, ON THE PAYMENT.**
    A returned cheque is an event on a payment, `apps/payments/reversal.py`
    already reverses one, and the bounce fee is a charge against the customer's
    account. The deposit batch owns none of those facts — it owns a bank tie-out
    that is still true. Finance's reconciliation screen shows the consequence;
    payments records the cause.

    **WHAT STILL REFUSES IS A DIFFERENT QUESTION.** A payment naming a batch this
    process cannot READ has an unknown lock state. The ruling settles what to do
    when a batch IS locked; it does not make it safe to proceed while blind, so
    that case fails closed — now as a rule refusal with a plain reason rather
    than as an open-question stub.

    ⚠ **THERE ARE STILL TWO IMPLEMENTATIONS OF THIS ONE LAW, and that is
    reported rather than left to be discovered.** `apps/payments/reversal
    ._refuse_if_batch_locked` resolves this module's models BY NAME and is the
    one the bounce path actually calls; **this function has no caller.** Both now
    permit a locked batch and refuse an unreadable one, but two answers to "may
    this payment bounce?" is exactly the shape that lets one of them drift. They
    should collapse onto this function (the owning module's published boundary);
    that is a wiring change beyond this lane and is REPORTED, not made.
    """
    batch_id = getattr(payment, "deposit_batch_id", None)
    if batch_id is None:
        return  # never banked in a batch: nothing is locked, nothing to ask
    batch = bankrec.DepositBatch.objects.filter(tenant_id=_tenant_id(), pk=batch_id).first()
    if batch is None:
        # FAIL CLOSED. A payment naming a batch this process cannot read is a
        # payment whose lock state is UNKNOWN, and a batch id that resolves to no
        # row is a broken reference rather than a lock — which is not the case
        # the PO ruled on. (The same posture `apps/payments/reversal
        # ._refuse_if_batch_locked` takes.)
        raise PaymentRuleError(
            f"payment {getattr(payment, 'payment_no', None) or payment.pk} names deposit "
            f"batch {batch_id}, which cannot be read for this tenant — so this process cannot "
            "tell what it is about to touch. A locked batch is FINE (PO 2026-08-12: the lock "
            "holds and the bounce is new rows); a batch that does not resolve at all is a broken "
            "reference, and reversing the payment would leave the books referring to it too. "
            "Refused rather than assumed safe.",
            br_ref="BR-PAY-004",
        )
    # A RECONCILED batch is deliberately NOT a refusal (PO 2026-08-12). Its
    # `recorded_total` does not move, so there is nothing here to protect: the
    # bounce writes new rows and `_recompute_total` refuses the edit that would
    # have been the actual hard-rule-4 violation.
    return


# ── US-PAY-021 · the statement import and the auto-match ────────────────────
def import_bank_statement(
    *,
    actor: Any,
    bank_account_id: Any,
    period_start: date,
    period_end: date,
    payload: bytes,
    imported_at: datetime,
    file_name: str | None = None,
    file_format: str = lockbox.FORMAT_CSV,
    opening_balance: Any = None,
    closing_balance: Any = None,
) -> StatementImportResult:
    """S38 steps 1–2: persist the statement, then auto-match what is unambiguous.

    Idempotent on **file + tags** (BR-PAY-028 🔒, the OQ-044 closure's model): the
    same bytes against the same bank account and period are REFUSED naming who
    imported them first, when, and the import's id — US-PAY-021 TC-5, *"no
    duplicate bank_lines"*. The unique index is the other half, so two clerks
    racing the same upload cannot both win.

    Parsing refusals are translated into this module's vocabulary at the seam
    (DEF-047's lesson): a caller catching `PaymentRuleError` sees a bad file the
    same way it sees any other refusal.

    ── CS-14 · THE TWO BALANCES (CR-059 task 43) ───────────────────────────
    `opening_balance` and `closing_balance` are the statement's OWN figures,
    captured on S38 step 1 beside the account and period it already asks for.
    **Both are OPTIONAL and neither is defaulted**, because a reconciliation
    statement built on a balance nobody typed is a tie-out that proves nothing:
    `bankrec_read.reconciliation_statement` serves `None` for every figure that
    depends on a missing balance and never `0.00`. They are NOT part of the
    idempotency key — the key is file + (bank account, period), BR-PAY-028 — so
    a clerk who mistypes a balance cannot re-import the file to correct it, and
    the row is append-only besides. That is REPORTED rather than worked around:
    correcting a balance is a schema-level question (a correcting row? a second
    import?) that CS-14 does not rule on, and inventing an UPDATE path here
    would break the append-only trigger 0005 installed on purpose.
    """
    tenant_id = _tenant_id()
    imported_at = _require_moment(imported_at, "the moment the statement was imported")
    account = bankrec.BankAccount.objects.filter(
        tenant_id=tenant_id, pk=bank_account_id, active=True
    ).first()
    if account is None:
        raise PaymentRuleError(
            f"bank account {bank_account_id!r} is not a live bank account of this tenant, so a "
            "statement cannot be imported against it (B2 r14 #1 — the registry S38 step 1 "
            "selects from). Nothing is read from the file.",
            br_ref="BR-PAY-019",
        )
    if period_end < period_start:
        raise PaymentRuleError(
            f"the statement period ends ({period_end}) before it starts ({period_start}).",
            br_ref="BR-PAY-019",
        )
    # CS-14. `_money` refuses a float outright rather than converting it
    # (CLAUDE.md rule 2) — a bank balance that arrived as 48112.4 would already
    # have lost the cents by the time it got here.
    opening = (
        None
        if opening_balance is None
        else _money(opening_balance, what="the statement's opening balance")
    )
    closing = (
        None
        if closing_balance is None
        else _money(closing_balance, what="the statement's closing balance")
    )

    file_hash = lockbox.file_sha256(payload)
    fingerprint = lockbox.statement_tag_fingerprint(
        {
            "bank_account_id": account.pk,
            "period_start": period_start,
            "period_end": period_end,
        }
    )
    duplicate = bankrec.BankStatementImport.objects.filter(
        tenant_id=tenant_id, file_hash=file_hash, tag_fingerprint=fingerprint
    ).first()
    if duplicate is not None:
        who = getattr(duplicate.imported_by, "email", None) or duplicate.imported_by_id
        raise PaymentRuleError(
            f"this statement file was already imported for {account.name} "
            f"{period_start.isoformat()}–{period_end.isoformat()} — import {duplicate.pk}, by "
            f"{who}, at {duplicate.imported_at.isoformat()}. Importing it again would write every "
            "bank line a second time and every one of them would look like money the bank sent "
            "twice (BR-PAY-028 · hard rule 6). Import the corrected file, or open that import.",
            br_ref="BR-PAY-028",
        )

    try:
        parsed = lockbox.parse_bank_statement(payload, file_format=file_format)
    except lockbox.BankFileError as refusal:  # the kernel's vocabulary → this module's
        raise PaymentRuleError(str(refusal), br_ref="BR-PAY-019") from refusal
    # ── LBX-09 (DEF-PAY-10695, PO 2026-10-30) — a line the bank cannot yet have
    # posted, or one outside the statement's own period, is refused BY NAME and
    # nothing is written. "Now" is `imported_at`, the moment the caller named
    # (BR-TEN-043 — no clock is read on this path, gate G6). Tester's case:
    # imported 26 Oct, lines dated 29 and 31 Oct are both refused.
    import_day = imported_at.date()
    for line in parsed:
        label = f"line {line.line_no} ({line.reference or 'no reference'}, {line.posted_on})"
        if line.posted_on > import_day:
            raise PaymentRuleError(
                f"{label} is dated after this import ({import_day}). A bank cannot report "
                "tomorrow's money; nothing was imported.",
                br_ref="BR-PAY-019",
                # DEF-PAY-10764 — the screen names the line, not a payment.
                message_key="payments.bankrec.line_after_import",
                params={"reference": line.reference or "", "date": str(line.posted_on)},
            )
        if not period_start <= line.posted_on <= period_end:
            raise PaymentRuleError(
                f"{label} is outside the statement period {period_start}–{period_end}. "
                "Nothing was imported.",
                br_ref="BR-PAY-019",
                message_key="payments.bankrec.line_outside_period",
                params={"reference": line.reference or "", "date": str(line.posted_on)},
            )

    with transaction.atomic():
        statement = bankrec.BankStatementImport.objects.create(
            tenant_id=tenant_id,
            bank_account=account,
            period_start=period_start,
            period_end=period_end,
            file_name=file_name,
            file_hash=file_hash,
            tag_fingerprint=fingerprint,
            line_count=len(parsed),
            opening_balance=opening,  # CS-14 — NULL when the clerk gave none
            closing_balance=closing,
            imported_by_id=core_audit.actor_user_id(actor),  # DEF-CUS-9081
            imported_at=imported_at,
        )
        bankrec.BankLine.objects.bulk_create(
            [
                bankrec.BankLine(
                    tenant_id=tenant_id,
                    statement_import=statement,
                    posted_on=line.posted_on,
                    reference=line.reference,
                    amount=line.amount,
                    line_no=line.line_no,
                )
                for line in parsed
            ]
        )
        core_audit.money_action(
            actor,
            AUDIT_STATEMENT_IMPORTED,
            "bank_statement_import",
            str(statement.pk),
            after={
                "bank_account": account.name,
                "period_start": period_start.isoformat(),
                "period_end": period_end.isoformat(),
                "file_name": file_name,
                "file_hash": file_hash,
                "lines": len(parsed),
                # CS-14 — money as STRINGS in an audit payload, the discipline
                # every other money action here keeps, and None when absent so
                # the row states "no balance was captured" rather than "0.00".
                "opening_balance": None if opening is None else str(opening),
                "closing_balance": None if closing is None else str(closing),
                "job": None if actor is not None else "payments.import_bank_statement",
            },
        )
        outcomes = auto_match(statement, actor=actor, occurred_at=imported_at)

    exceptions = tuple(row for row in outcomes if row.state == "needs_a_look")
    not_ours = tuple(row for row in outcomes if row.state == "not_in_our_system")

    # ── CR-048 wave B · THE RUN IS FINISHED, SO TELL SOMEBODY ──────────────
    #
    # This is the point a reconciliation run ends — the statement is persisted,
    # every line is sorted, and the transaction that did it has closed — so the
    # message describes work that has actually happened.
    #
    # ONE message for the whole statement, whatever it carried (BR-NOT-020), and
    # zero exceptions is still one message: a clerk who sees nothing cannot tell
    # a clean run from a run that never happened.
    #
    # `failed_count` IS BOTH UNMATCHED TILES — S38's *needs a look* and its
    # *not in our system* — because both are lines this run could not match and
    # both are a clerk's to work. `run_alert_seam`'s docstring carries the
    # reasoning; counting only the first would report a statement of pure
    # unknown credits as a clean run.
    #
    # ⚠ NOTHING THIS CALL DOES CAN REACH THE BANK LINES. The seam holds a
    # savepoint and swallows no reason — on PostgreSQL a `try` alone would lose
    # the whole import at COMMIT.
    staff_alert = run_alert_seam.queue_run_summary(
        run_id=statement.pk,
        total_count=len(parsed),
        failed_count=len(exceptions) + len(not_ours),
        finished_at=imported_at,
        actor=actor,
    )

    return StatementImportResult(
        statement_import_id=str(statement.pk),
        line_count=len(parsed),
        matched=tuple(row for row in outcomes if row.state == "auto"),
        exceptions=exceptions,
        not_in_our_system=not_ours,
        staff_alert=staff_alert,
    )


def _amounts_tie(recorded_total: Decimal, bank_amount: Decimal, tolerance: Decimal) -> bool:
    """Do a deposit batch's total and a bank line's amount count as the same money?

    ONE definition, called from all three comparison sites in `auto_match`, and
    that is the point of extracting it: the candidate test, the rival test and
    the near-miss test each asked the same question in its own words before
    CR-008, and three copies of a money comparison is three places for a
    tolerance to be forgotten.

    `tolerance` is the tenant's own `bank_match_amount_tolerance` (CR-008 #7),
    seeded **0** — and at 0 this function is `recorded_total == bank_amount`,
    character for character what this module did before the setting existed.

    Decimal throughout (CLAUDE.md rule 2). `abs()` on a Decimal is exact; the
    same test written with floats would make 0.05 mean 0.05000000000000000277.
    """
    return abs(recorded_total - bank_amount) <= tolerance


def auto_match(
    statement: bankrec.BankStatementImport, *, actor: Any, occurred_at: datetime
) -> tuple[MatchOutcome, ...]:
    """BR-PAY-019's rule, and nothing beyond it: amount within ±T, date within ±N.

    `auto_match ⇔ |bank_amount − recorded_total| ≤ tolerance_amount ∧
    |bank_date − deposit_date| ≤ tolerance_days` — US-PAY-021 §7 with the AMOUNT
    window added by the PO's CR-008 ruling of 2026-08-17 (*"Okay. We can take it
    as threshold from user"*). Both tolerances are read from the tenant's own
    S71 setting, never from a constant (`settings_seam`).

    ⚠ **THE AMOUNT WINDOW DEFAULTS TO 0, WHICH IS THE `==` THIS FUNCTION USED
    TO WRITE.** Every comparison below went through `recorded_total ==
    line.amount` until CR-008; `_within(a, b, 0)` is that same test, so a tenant
    who never opens the screen sees no change of any kind. A tenant who types
    0.05 has decided, visibly and with an audit row, that five cents of bank
    charge is still the same money — and that decision then LOCKS batches
    (BR-PAY-004), which is why it is theirs and not a seeded convenience.

    One-to-one and unambiguous or nothing: a line with two candidate batches, or
    a batch two lines could claim, is left for a human. An amount OUTSIDE the
    tenant's window is never linked here — that is the S40 exception, and
    linking it automatically is exactly the fee derivation OQ-160 forbids.
    """
    tolerance = timedelta(days=settings_seam.match_tolerance_days())
    amount_tolerance = settings_seam.match_amount_tolerance()
    tenant_id = statement.tenant_id
    lines = list(
        bankrec.BankLine.objects.filter(
            tenant_id=tenant_id, statement_import=statement, deposit_batch__isnull=True
        ).order_by("line_no", "id")
    )
    # `deposit_batch__isnull=False` in the subquery is load-bearing, not
    # tidiness: a subquery that yields NULLs makes `NOT IN (…, NULL)` evaluate
    # to NULL for EVERY row, so the exclude would drop every candidate batch and
    # nothing would ever auto-match. It did exactly that once, before this line.
    already_matched = bankrec.BankLine.objects.filter(
        tenant_id=tenant_id, deposit_batch__isnull=False
    ).values("deposit_batch")
    # ⚠ `P2.10` — `bankrec.bankable` keeps a drawer that is STILL OPEN out of
    # the candidate set. `status` cannot answer this: a counter batch is
    # `in_transit` from the moment its till opens, so without this an
    # unattended statement import could tie a bank line to money a clerk is
    # still taking. `status` says what the BANK has done with a batch; this
    # says whether the batch is finished. Same expression as the Deposits list.
    open_batches = list(
        bankrec.bankable(
            bankrec.DepositBatch.objects.filter(
                tenant_id=tenant_id,
                status__in=(bankrec.BATCH_IN_TRANSIT, bankrec.BATCH_UNMATCHED),
            )
        ).exclude(pk__in=already_matched)
    )

    outcomes: list[MatchOutcome] = []
    claimed: set[Any] = set()
    for line in lines:
        candidates = [
            batch
            for batch in open_batches
            if batch.pk not in claimed
            and _amounts_tie(batch.recorded_total, line.amount, amount_tolerance)
            and abs(line.posted_on - batch.deposited_on) <= tolerance
        ]
        if len(candidates) == 1:
            batch = candidates[0]
            # A second line that ALSO ties this batch exactly makes the pairing
            # ambiguous; neither is matched, because picking one would reconcile
            # money against the wrong day's deposit.
            rivals = [
                other
                for other in lines
                if other.pk != line.pk
                and _amounts_tie(batch.recorded_total, other.amount, amount_tolerance)
                and abs(other.posted_on - batch.deposited_on) <= tolerance
            ]
            if rivals:
                outcomes.append(
                    MatchOutcome(
                        bank_line_id=str(line.pk),
                        amount=line.amount,
                        posted_on=line.posted_on,
                        batch_id=None,
                        batch_code=None,
                        state="needs_a_look",
                        detail=f"{len(rivals) + 1} bank lines tie {batch.code} exactly — a human "
                        "names the pairing; nothing is guessed (BR-PAY-019).",
                    )
                )
                continue
            _link(line, batch, actor=actor, occurred_at=occurred_at, auto=True)
            claimed.add(batch.pk)
            outcomes.append(
                MatchOutcome(
                    bank_line_id=str(line.pk),
                    amount=line.amount,
                    posted_on=line.posted_on,
                    batch_id=str(batch.pk),
                    batch_code=batch.code,
                    state="auto",
                    difference=ZERO,
                )
            )
            continue
        if len(candidates) > 1:
            outcomes.append(
                MatchOutcome(
                    bank_line_id=str(line.pk),
                    amount=line.amount,
                    posted_on=line.posted_on,
                    batch_id=None,
                    batch_code=None,
                    state="needs_a_look",
                    detail=f"{len(candidates)} batches tie this line exactly within the "
                    "tolerance — ambiguous, so a human names the pairing.",
                )
            )
            continue
        # "Needs a look" versus "not in our system" — the difference matters to
        # whoever works the exception, so it is decided on evidence rather than
        # on the date alone: a batch of the SAME AMOUNT four days away is a
        # candidate a human should see, and a tenant who tightened the tolerance
        # to ±1 has not thereby declared their own deposit to be somebody
        # else's money. Neither is a match — nothing here links anything.
        near = [
            batch
            for batch in open_batches
            if batch.pk not in claimed
            and (
                _amounts_tie(batch.recorded_total, line.amount, amount_tolerance)
                or abs(line.posted_on - batch.deposited_on) <= tolerance
            )
        ]
        # LBX-05 (G3 RULED 2026-10-30) — money the bank took OUT (a returned
        # cheque, the bank's fee) is never "not in our system": it is a
        # clerk's to match to its reversal or post as a fee, so it needs a look.
        money_out = line.amount < ZERO
        outcomes.append(
            MatchOutcome(
                bank_line_id=str(line.pk),
                amount=line.amount,
                posted_on=line.posted_on,
                batch_id=None,
                batch_code=None,
                state="needs_a_look" if (near or money_out) else "not_in_our_system",
                detail=(
                    "money left the bank — match it to the payment it returns, or post it as a "
                    "bank fee (batch decision G3, ruled 2026-10-30)."
                    if money_out
                    else "no batch of this day's money equals this line — the difference is a "
                    "human's to explain with a reason and a GL (BR-PAY-019); a card day "
                    "reconciles NET with its fee as its own line (PO ruling 2026-08-11)."
                    if near
                    else "this credit matches no deposit of ours at all — S38's fourth tile."
                ),
            )
        )
    return tuple(outcomes)


def _link(
    line: bankrec.BankLine,
    batch: bankrec.DepositBatch,
    *,
    actor: Any,
    occurred_at: datetime,
    auto: bool,
) -> Decimal:
    """Tie one bank line to one batch and stamp what the bank said. Returns the difference."""
    line.deposit_batch = batch
    line.save(update_fields=["deposit_batch", "updated_at"])
    batch.bank_total = line.amount
    batch.status = bankrec.BATCH_MATCHED
    batch.save(update_fields=["bank_total", "status", "updated_at"])
    difference = line.amount - batch.recorded_total
    _trail(
        batch,
        bankrec.EVENT_MATCHED,
        actor=actor,
        occurred_at=occurred_at,
        bank_line_id=str(line.pk),
        bank_reference=line.reference,
        bank_total=str(line.amount),
        recorded_total=str(batch.recorded_total),
        difference=str(difference),
        auto=auto,
    )
    if difference != ZERO:
        _trail(
            batch,
            bankrec.EVENT_FLAGGED,
            actor=actor,
            occurred_at=occurred_at,
            difference=str(difference),
        )
    return difference


def match_bank_line(
    *, actor: Any, batch_id: Any, bank_line_id: Any, occurred_at: datetime
) -> Decimal:
    """A HUMAN names a pairing the exact rule could not make (S38 step 2 → S40).

    This is how the card day gets tied at all: the amounts differ by the
    processor's fee, so `auto_match` leaves both sides alone and a person says
    *"that credit is this deposit"*. It is not a force-match — nothing
    reconciles here, and BR-PAY-035's superseded button still does not exist.
    The difference remains to be explained in `reconcile_batch`.
    """
    tenant_id = _tenant_id()
    occurred_at = _require_moment(occurred_at, "the moment the match was made")
    batch = _batch(batch_id)
    if batch.status == bankrec.BATCH_RECONCILED:
        raise PaymentRuleError(
            f"deposit batch {batch.code} is reconciled and LOCKED (BR-PAY-004) — Unreconcile is "
            "the only way back, and it is audited.",
            br_ref="BR-PAY-004",
        )
    _refuse_if_the_till_is_open(batch)
    line = bankrec.BankLine.objects.filter(tenant_id=tenant_id, pk=bank_line_id).first()
    if line is None:
        raise PaymentRuleError(
            f"bank line {bank_line_id!r} is not one of this tenant's statement lines.",
            br_ref="BR-PAY-019",
        )
    if line.deposit_batch_id is not None:
        raise PaymentRuleError(
            f"bank line {line.reference or line.pk} is already matched to a deposit batch, and a "
            "match is WRITE-ONCE (migration 0005). Re-pointing it would move a batch onto a "
            "different bank line without touching the batch at all.",
            br_ref="BR-PAY-019",
        )
    # CS-17 — the two doors can never both hold. A line or a batch already tied
    # inside a match SET is refused here, or the same $17,120.00 credit could be
    # spent twice: once through the set and once through this 1:1 link.
    _refuse_if_in_a_set(tenant_id, line=line, batch=batch)
    with transaction.atomic():
        return _link(line, batch, actor=actor, occurred_at=occurred_at, auto=False)


# ── CS-17 · the match SET (CR-059 task 45) ──────────────────────────────────
def _refuse_if_in_a_set(
    tenant_id: Any, *, line: bankrec.BankLine | None = None, batch: Any = None
) -> None:
    """A member of a match set is spoken for; the 1:1 door refuses it by name."""
    if line is not None:
        member = bankrec.BankRecMatchMember.objects.filter(
            tenant_id=tenant_id, bank_line=line
        ).first()
        if member is not None:
            raise PaymentRuleError(
                f"bank line {line.reference or line.pk} is already part of match set "
                f"{member.match_set_id} — a bank credit that pays for several of our deposits is "
                "tied ONCE, as a set (CS-17, PO ruling 2026-08-12). Tying it a second time "
                "one-to-one would reconcile the same money twice.",
                br_ref="BR-PAY-019",
            )
    if batch is not None:
        member = bankrec.BankRecMatchMember.objects.filter(tenant_id=tenant_id, batch=batch).first()
        if member is not None:
            raise PaymentRuleError(
                f"deposit batch {batch.code} is already part of match set {member.match_set_id} "
                "and a match is write-once. Its bank side is the set, not a single line.",
                br_ref="BR-PAY-019",
            )


def match_set(
    *,
    actor: Any,
    bank_line_ids: Any,
    batch_ids: Any,
    occurred_at: datetime,
    note: str | None = None,
) -> MatchSetResult:
    """MANY bank lines to one batch, and one line to many batches — CS-17.

    **RULED, NOT PROPOSED.** PO 2026-08-12 closing `OQ-161`, verbatim: *"Build
    many-to-one matching"*, on the worked case of **$2,840.00 + $14,280.00
    posted by the bank as ONE credit of $17,120.00**. Before this function that
    money could not be reconciled by anybody: `bank_lines` carries
    `UNIQUE (tenant, deposit_batch)` and the auto-matcher compares one line to
    one batch, so both batches stayed unmatched forever and $17,120 sat in
    undeposited funds while the month-end checklist said the bank rec was done.

    ════════════════════════════════════════════════════════════════════════
    THE THREE REFUSALS CS-17 KEEPS, AND THE ONE IT ADDS
    ════════════════════════════════════════════════════════════════════════
    CS-17 in terms: *"the set's totals must be equal and every member's date
    within tolerance. The three existing refusals are unchanged: this widens
    what can tie, never what can be guessed."* So:

      * **nothing here is automatic.** `auto_match` is untouched and still
        exact and one-to-one; a set is only ever built because a HUMAN said
        *"that credit is these two deposits"*. There is no set-shaped guess.
      * **the totals must be EXACTLY equal.** Not within the tenant's amount
        tolerance — see the `BankRecMatchSet` docstring: on one pair the slack
        has one place to go, and across five members nothing rules how to
        apportion it. A set that does not foot is refused with both sums named.
      * **every date is inside the tenant's own ±N-day window**, compared
        pairwise across the two sides, because a set is one event: the money
        left the drawer on those days and the bank posted it on those days.
      * **"Force match anyway" still does not exist** (BR-PAY-035) and no
        argument here carries one.

    ════════════════════════════════════════════════════════════════════════
    WHAT EACH BATCH'S BANK SIDE BECOMES, AND WHY IT NEEDS NO NEW RULING
    ════════════════════════════════════════════════════════════════════════
    Because the set ties exactly, each member batch's share of the bank credit
    is its OWN recorded total — 2,840.00 for the cheque batch and 14,280.00 for
    the ACH one — so `bank_total` is stamped with it and each batch then goes
    through `reconcile_batch` unchanged, at a difference of 0.00. The two
    entries the ledger writes debit cash 2,840.00 and 14,280.00, which sums to
    the 17,120.00 the bank actually credited. **No money figure is apportioned
    and no new posting shape is invented** — which is exactly why the exact-
    equality rule above is worth its refusals.

    Idempotent (hard rule 6): the same lines against the same batches, submitted
    twice, return the existing set with `created=False` rather than a red 409 —
    a matching set is one event however many times the button is pressed.
    """
    tenant_id = _tenant_id()
    occurred_at = _require_moment(occurred_at, "the moment the match set was made")
    line_ids = _distinct(bank_line_ids, what="bank line")
    wanted_batches = _distinct(batch_ids, what="deposit batch")
    if not line_ids or not wanted_batches:
        raise PaymentRuleError(
            "a match set needs at least one bank line AND at least one deposit batch. A set with "
            "nothing on one side is not a match; it is a statement that money appeared or "
            "vanished, which is an explanation (a reason and a GL) rather than a tie.",
            br_ref="BR-PAY-019",
        )
    if len(line_ids) == 1 and len(wanted_batches) == 1:
        raise PaymentRuleError(
            "one bank line against one deposit batch is the ordinary match, and it has its own "
            "door — `match_bank_line`, which is write-once at the database and is how every "
            "batch reconciled since 2026-08-11 was tied. A set exists for the case that door "
            "cannot express: a bank that COMBINES two of our deposits into one credit, or splits "
            "one across two (CS-17). Two doors doing one job is how a guarantee quietly moves to "
            "whichever one a caller happens to use.",
            br_ref="BR-PAY-019",
        )

    lines = list(bankrec.BankLine.objects.filter(tenant_id=tenant_id, pk__in=line_ids))
    if len(lines) != len(line_ids):
        found = {str(row.pk) for row in lines}
        missing = [str(one) for one in line_ids if str(one) not in found]
        raise PaymentRuleError(
            f"{len(missing)} of the bank lines named are not this tenant's statement lines: "
            f"{', '.join(missing)}. Nothing is matched.",
            br_ref="BR-PAY-019",
        )
    batches = list(bankrec.DepositBatch.objects.filter(tenant_id=tenant_id, pk__in=wanted_batches))
    if len(batches) != len(wanted_batches):
        found = {str(row.pk) for row in batches}
        missing = [str(one) for one in wanted_batches if str(one) not in found]
        raise PaymentRuleError(
            f"{len(missing)} of the deposit batches named are not this tenant's: "
            f"{', '.join(missing)}. Nothing is matched.",
            br_ref="BR-PAY-019",
        )

    # ── the idempotent replay, checked BEFORE any refusal that a replay would
    # trip over: the second submit of the same set finds its own members
    # already tied and must answer 200 with the original, not "already matched".
    existing = _existing_match_set(tenant_id, lines=lines, batches=batches)
    if existing is not None:
        return MatchSetResult(
            match_set_id=str(existing.pk),
            matched_total=existing.matched_total,
            currency=settings_seam.tenant_currency(),
            bank_line_ids=tuple(str(row.pk) for row in lines),
            batch_ids=tuple(str(row.pk) for row in batches),
            batch_codes=tuple(row.code for row in batches),
            created=False,
        )

    for line in lines:
        if line.deposit_batch_id is not None:
            raise PaymentRuleError(
                f"bank line {line.reference or line.pk} is already matched one-to-one to a "
                "deposit batch, and a match is WRITE-ONCE (migration 0005). It cannot also be "
                "part of a set.",
                br_ref="BR-PAY-019",
            )
        _refuse_if_in_a_set(tenant_id, line=line)
    for batch in batches:
        if batch.status == bankrec.BATCH_RECONCILED:
            raise PaymentRuleError(
                f"deposit batch {batch.code} is reconciled and LOCKED (BR-PAY-004) — Unreconcile "
                "is the only way back, and it is audited.",
                br_ref="BR-PAY-004",
            )
        _refuse_if_the_till_is_open(batch)
        if bankrec.BankLine.objects.filter(tenant_id=tenant_id, deposit_batch=batch).exists():
            raise PaymentRuleError(
                f"deposit batch {batch.code} is already matched to a bank line one-to-one. Its "
                "bank side is settled; a set cannot claim it as well.",
                br_ref="BR-PAY-019",
            )
        _refuse_if_in_a_set(tenant_id, batch=batch)

    tolerance = timedelta(days=settings_seam.match_tolerance_days())
    for line in lines:
        for batch in batches:
            if abs(line.posted_on - batch.deposited_on) > tolerance:
                raise PaymentRuleError(
                    f"bank line {line.reference or line.pk} posted {line.posted_on} and deposit "
                    f"batch {batch.code} was banked {batch.deposited_on} — "
                    f"{abs((line.posted_on - batch.deposited_on).days)} days apart, outside this "
                    f"utility's ±{tolerance.days}-day matching window (BR-PAY-019, a finance "
                    "setting on S71). A set is ONE event: if these really are the same money, "
                    "widen the window deliberately and be seen doing it.",
                    br_ref="BR-PAY-019",
                )

    bank_side = sum((_money(row.amount, what="a bank line's amount") for row in lines), ZERO)
    book_side = sum(
        (_money(row.recorded_total, what="a batch's recorded total") for row in batches), ZERO
    )
    if bank_side != book_side:
        raise PaymentRuleError(
            f"the set does not foot: {len(lines)} bank line(s) totalling {bank_side} against "
            f"{len(batches)} deposit batch(es) totalling {book_side}, a difference of "
            f"{bank_side - book_side}. CS-17 requires a set's totals to be EQUAL — on a single "
            "pair a difference has one owner and is explained with a reason and a GL, and across "
            "a set there is no ruled way to apportion it between the members. Nothing is "
            "matched. Tie the members that do foot, and explain the rest.",
            br_ref="BR-PAY-019",
        )

    with transaction.atomic():
        record = bankrec.BankRecMatchSet.objects.create(
            tenant_id=tenant_id,
            matched_total=bank_side,
            matched_at=occurred_at,
            actor_id=core_audit.actor_user_id(actor),  # DEF-CUS-9081
            note=note,
        )
        bankrec.BankRecMatchMember.objects.bulk_create(
            [
                bankrec.BankRecMatchMember(
                    tenant_id=tenant_id, match_set=record, bank_line=line, batch=None
                )
                for line in lines
            ]
            + [
                bankrec.BankRecMatchMember(
                    tenant_id=tenant_id, match_set=record, bank_line=None, batch=batch
                )
                for batch in batches
            ]
        )
        for batch in batches:
            # The set ties exactly, so this batch's share of the bank credit IS
            # its own recorded total. Nothing is apportioned; see the docstring.
            batch.bank_total = batch.recorded_total
            batch.status = bankrec.BATCH_MATCHED
            batch.save(update_fields=["bank_total", "status", "updated_at"])
            _trail(
                batch,
                bankrec.EVENT_MATCHED,
                actor=actor,
                occurred_at=occurred_at,
                match_set_id=str(record.pk),
                matched_total=str(bank_side),
                bank_total=str(batch.recorded_total),
                recorded_total=str(batch.recorded_total),
                difference="0",
                bank_line_count=len(lines),
                batch_count=len(batches),
                auto=False,
            )
        core_audit.money_action(
            actor,
            AUDIT_MATCH_SET,
            "bank_rec_match_set",
            str(record.pk),
            after={
                "matched_total": str(bank_side),
                "bank_line_ids": [str(row.pk) for row in lines],
                "batch_codes": [row.code for row in batches],
                "note": note,
                "job": None if actor is not None else "payments.match_set",
            },
        )

    return MatchSetResult(
        match_set_id=str(record.pk),
        matched_total=bank_side,
        currency=settings_seam.tenant_currency(),
        bank_line_ids=tuple(str(row.pk) for row in lines),
        batch_ids=tuple(str(row.pk) for row in batches),
        batch_codes=tuple(row.code for row in batches),
        created=True,
    )


def _distinct(values: Any, *, what: str) -> list[str]:
    """The ids a caller named, de-duplicated, order preserved.

    A repeated id is silently collapsed rather than refused: a screen that sent
    the same line twice meant it once, and the partial UNIQUE index would refuse
    the second member anyway with a message about a database constraint.
    """
    seen: list[str] = []
    for value in values or ():
        text = str(value).strip()
        if not text:
            raise PaymentRuleError(
                f"a blank {what} id was sent in the match set.", br_ref="BR-PAY-019"
            )
        if text not in seen:
            seen.append(text)
    return seen


def _existing_match_set(tenant_id: Any, *, lines: list[Any], batches: list[Any]) -> Any:
    """The set that already holds EXACTLY these members, or None (hard rule 6).

    Matched on the whole membership rather than on a submit token, because a
    match set has no idempotency column and a token would be a second key for
    the same fact. Exact set equality on BOTH sides: a set holding these two
    lines plus a third is a different tie and must not be returned as a replay.
    """
    wanted_lines = {str(row.pk) for row in lines}
    wanted_batches = {str(row.pk) for row in batches}
    candidates = bankrec.BankRecMatchSet.objects.filter(
        tenant_id=tenant_id, members__bank_line__in=[row.pk for row in lines]
    ).distinct()
    for candidate in candidates:
        members = list(candidate.members.all())
        held_lines = {str(row.bank_line_id) for row in members if row.bank_line_id}
        held_batches = {str(row.batch_id) for row in members if row.batch_id}
        if held_lines == wanted_lines and held_batches == wanted_batches:
            return candidate
    return None


# ── CS-16 · an unmatched bank line, EXPLAINED (CR-059 task 44) ──────────────
def resolve_bank_line(
    *,
    actor: Any,
    bank_line_id: Any,
    reason_code: str,
    gl_account_id: Any,
    amount: Decimal,
    occurred_at: datetime,
    note: str | None = None,
) -> LineResolutionResult:
    """*"Every bank line ends the period either matched or explained"* — CS-16.

    **The gap this closes.** A resolution could only hang off a BATCH, so a line
    that is genuinely not a deposit of ours — a customer paying the bank
    directly, an interest credit, a bank error — could only be LEFT ALONE, and
    it sat there forever with nothing said about it. CS-16's new rule: *"Every
    bank line ends the period either matched or explained, with a reason and a
    GL. **Silence is not a state.**"*

    ════════════════════════════════════════════════════════════════════════
    THIS POSTS NOTHING, AND THAT IS BATCH DECISION G3 RATHER THAN AN OVERSIGHT
    ════════════════════════════════════════════════════════════════════════
    Creating a payment or a JOURNAL ENTRY from an unmatched bank line is batch
    decision **G3**, which the PO has not ruled on — this module has said so on
    every result since it was written. So the explanation is RECORDED, with its
    reason and its GL account, and the books are left exactly as they were.
    `journal_entry_id` stays NULL and `RECONCILE_UNAVAILABLE` says why on every
    response, so nobody reads the recorded explanation as a posted one.

    The consequence, stated rather than discovered: an explained line is STILL a
    difference between the bank and the books until G3 is answered, and
    `bankrec_read.reconciliation_statement` carries it as its own line for
    exactly that reason.

    ════════════════════════════════════════════════════════════════════════
    ONE EXPLANATION PER LINE — WHICH IS ALSO THE IDEMPOTENCY GUARD (rule 6)
    ════════════════════════════════════════════════════════════════════════
    A bank line is ONE fact — an interest credit of 44.50 — so it takes ONE
    explanation. That gives hard rule 6 for free and without a new column:

      * the SAME reason, GL and amount submitted twice returns the row that
        exists with `created=False` and **HTTP 200**, because a red error for a
        button that worked is a wrong answer a clerk would act on (the posture
        `record_payment` has had since day one);
      * a DIFFERENT explanation of the same line is REFUSED by name, quoting
        what the line already says. `bank_rec_resolutions` is append-only from
        birth (migration 0005), so there is no path that edits the first one and
        none is invented here.
    """
    tenant_id = _tenant_id()
    occurred_at = _require_moment(occurred_at, "the moment the line was explained")
    amount = _money(amount, what="the explanation's amount")
    if amount == ZERO:
        raise PaymentRuleError(
            "an explanation of 0.00 explains nothing. Every resolution accounts for money the "
            "bank moved and we did not; a zero row would be a reason attached to nothing.",
            br_ref="BR-PAY-019",
        )
    line = bankrec.BankLine.objects.filter(tenant_id=tenant_id, pk=bank_line_id).first()
    if line is None:
        raise PaymentRuleError(
            f"bank line {bank_line_id!r} is not one of this tenant's statement lines.",
            br_ref="BR-PAY-019",
        )
    if line.deposit_batch_id is not None:
        raise PaymentRuleError(
            f"bank line {line.reference or line.pk} is MATCHED to deposit batch "
            f"{line.deposit_batch.code}, so it is not an unexplained line — any difference "
            "between what the bank said and what we recorded is explained on the BATCH, at "
            "reconcile, where it is checked against the difference and posted with the "
            "reconciliation entry (BR-PAY-019). Explaining it here would record the same money "
            "twice under two parents.",
            br_ref="BR-PAY-019",
        )
    if bankrec.BankRecMatchMember.objects.filter(tenant_id=tenant_id, bank_line=line).exists():
        raise PaymentRuleError(
            f"bank line {line.reference or line.pk} is part of a match set, so it is matched "
            "rather than unexplained (CS-17). A set ties exactly by rule, so it leaves no "
            "difference for this door to explain.",
            br_ref="BR-PAY-019",
        )

    canonical = _canonical_reason(
        reason_code, where="this explanation", reasons=live_difference_reasons()
    )
    if not gl_account_id:
        raise PaymentRuleError(
            f"the explanation ({canonical}) names no GL account. BR-PAY-019 requires both; a "
            "difference posted to no account is money that left the tie-out and landed nowhere.",
            br_ref="BR-PAY-019",
        )
    if not _account_is_live(gl_account_id):
        raise PaymentRuleError(
            f"the explanation names GL account {gl_account_id!r}, which is not a LIVE account of "
            "this tenant's own chart. It belongs to another tenant, has been deactivated, or "
            "does not exist — none of which is a reason to pick a different bucket.",
            br_ref="BR-PAY-019",
        )

    prior = bankrec.BankRecResolution.objects.filter(tenant_id=tenant_id, bank_line=line).first()
    if prior is not None:
        same = (
            prior.reason_code == canonical
            and str(prior.gl_account_id) == str(gl_account_id)
            and prior.amount == amount
        )
        if same:  # hard rule 6 — the double click, answered with the original
            return LineResolutionResult(
                resolution_id=str(prior.pk),
                bank_line_id=str(line.pk),
                reason_code=prior.reason_code,
                gl_account_id=str(prior.gl_account_id),
                amount=prior.amount,
                currency=settings_seam.tenant_currency(),
                created=False,
            )
        raise PaymentRuleError(
            f"bank line {line.reference or line.pk} is already explained as {prior.reason_code} "
            f"for {prior.amount} against GL {prior.gl_account_id}, and an explanation of a money "
            "difference is financial history the moment it is written (hard rule 4 — the "
            "append-only trigger in migration 0005 refuses the UPDATE besides). A line has one "
            "explanation; correcting one is not a rewrite and nothing rules its shape yet.",
            br_ref="BR-PAY-019",
        )

    with transaction.atomic():
        row = bankrec.BankRecResolution.objects.create(
            tenant_id=tenant_id,
            batch=None,  # CS-16 — the parent is the LINE
            bank_line=line,
            reason_code=canonical,
            gl_account_id=gl_account_id,
            amount=amount,
            note=note,
            actor_id=core_audit.actor_user_id(actor),  # DEF-CUS-9081
            # G3 — nothing is posted, so there is no entry to stamp. Named on
            # the result rather than left as a silent NULL.
            journal_entry_id=None,
        )
        core_audit.money_action(
            actor,
            AUDIT_LINE_RESOLVED,
            "bank_line",
            str(line.pk),
            after={
                "reference": line.reference,
                "posted_on": line.posted_on.isoformat(),
                "line_amount": str(line.amount),
                "reason_code": canonical,
                "gl_account_id": str(gl_account_id),
                "amount": str(amount),
                "note": note,
                "journal_entry_id": None,
                "posted": False,
                "job": None if actor is not None else "payments.resolve_bank_line",
            },
        )

    return LineResolutionResult(
        resolution_id=str(row.pk),
        bank_line_id=str(line.pk),
        reason_code=canonical,
        gl_account_id=str(gl_account_id),
        amount=amount,
        currency=settings_seam.tenant_currency(),
        created=True,
    )


# ════════════════════════════════════════════════════════════════════════════
# LBX-05 (DEF-PAY-10694) · G3 RULED — A RETURN AND A BANK FEE NOW POST
# ════════════════════════════════════════════════════════════════════════════
# HUMAN-REVIEW-PENDING (🔒 ledger posting) — row "LBX-05" in
# 12-governance/09-human-review-ledger.md.
#
# PO 2026-10-30, verbatim: *"Q1. May a bank-statement line that isn't a deposit
# post to the books?-A"*, and *"Q2. Where should a bounced cheque be reversed
# from?-A or user can do manually from payments and account these three are
# correct"*. Worked on the tester's lockbox day (DEP-261026-0007, six payments
# 870.50): cheques 4102 (76.40) and 4103 (154.00) come back.
#
#   receipts         DR holding 870.50 / CR AR
#   two reversals    DR AR 230.40 / CR holding 230.40       (the ledger mirror)
#   reconcile        DR cash 870.50 / CR holding 870.50     (what the batch held)
#   → before this:   holding −230.40, cash 870.50, bank 616.10
#   RET1029-01/02    DR holding 230.40 / CR cash 230.40     ← match_returned_line
#   FEE1031          DR 6800 24.00 / CR cash 24.00           ← explain_bank_fee_line
#   → after:         holding 0.00, cash 616.10 = bank 616.10, 6800 24.00
#
# The order does not matter: matching the return before the batch reconciles
# leaves holding at +870.50 and cash at −230.40 until the reconcile lands, and
# the same 0.00 / 616.10 after it.
#
# ⚠ **ONLY THESE TWO POST. AN ORDINARY "Explain" STILL POSTS NOTHING** — a lane
# judgment recorded in the decision log (2026-10-30, *"LBX-05 built"*): the PO's
# worked case names a returned cheque and a bank fee, and a free GL pick posting
# against cash would let *"customer paid the bank directly"* land in accounts
# receivable with no payment row behind it.

#: How far back a returned line looks for the payment it returns. BR-PAY-011's
#: longest return window that is not "unlimited" (ACH, 60 days); a cheque
#: returned later than this is still matchable by naming it outright.
RETURN_SEARCH_DAYS = 60

AUDIT_LINE_RETURN_MATCHED = "bank_rec.return_matched"
AUDIT_LINE_FEE_EXPLAINED = "bank_rec.bank_fee_explained"

REASON_RETURNED_ITEM = "returned_item"
REASON_BANK_FEE = "bank_fee"


@dataclass(frozen=True)
class LinePostingResult:
    """A returned line matched, or a fee line explained — and what reached the books.

    `posted=False` with a `journal_entry_id` is a FEE line linked to the fee a
    Reverse already posted: the line is explained and nothing posted twice.
    """

    resolution_id: str
    bank_line_id: str
    reason_code: str
    gl_account_id: str
    amount: Decimal
    currency: str
    created: bool
    journal_entry_id: str | None
    posted: bool
    reversal_payment_id: str | None = None
    original_payment_id: str | None = None
    #: True when THIS call reversed the cheque (it had not been reversed by hand).
    reversed_now: bool = False
    #: The NSF penalty, as the reversal service answered it (lane NSF-FEE):
    #: `charged`, `nsf_fee_waived`, or the named reason none was charged.
    #: None when this call reversed nothing.
    nsf_fee_status: str | None = None
    nsf_fee_amount: Decimal | None = None


def _open_bank_line(tenant_id: Any, bank_line_id: Any, *, what: str) -> bankrec.BankLine:
    """A statement line that is not tied to a deposit — or a named refusal."""
    line = bankrec.BankLine.objects.filter(tenant_id=tenant_id, pk=bank_line_id).first()
    if line is None:
        raise PaymentRuleError(
            f"bank line {bank_line_id!r} is not one of this tenant's statement lines.",
            br_ref="BR-PAY-019",
        )
    if line.deposit_batch_id is not None or bankrec.BankRecMatchMember.objects.filter(
        tenant_id=tenant_id, bank_line=line
    ).exists():
        raise PaymentRuleError(
            f"bank line {line.reference or line.pk} is matched to a deposit, so it cannot be "
            f"{what}.",
            br_ref="BR-PAY-019",
        )
    if line.amount >= ZERO:
        raise PaymentRuleError(
            f"bank line {line.reference or line.pk} is {line.amount}: money came IN. Only a line "
            f"the bank took OUT can be {what}.",
            br_ref="BR-PAY-019",
        )
    return line


def _holding_account_of(original: models.Payment) -> Any:
    """The account the payment's RECEIPT debited — where its money was held.

    Read from the receipt entry itself (`entry_debit_totals`), never from
    today's tender mapping, for the reason `_member_credit_split` gives. A
    pre-seam payment with no entry was held in `undeposited_funds`.
    """
    if original.journal_entry_id is None:
        read = _resolve("ledger", "gl_account_id_for_designation")
        account_id = read("undeposited_funds") if callable(read) else None
    else:
        read = _resolve("ledger", "entry_debit_totals")
        totals = dict(read([original.journal_entry_id])) if callable(read) else {}
        account_id = next(iter(totals)) if len(totals) == 1 else None
    if account_id is None:
        raise PaymentRuleError(
            f"payment {original.payment_no or original.pk}'s receipt does not name ONE holding "
            "account, so the returned money cannot be moved out of it. Refused rather than "
            "posted to a guessed account.",
            br_ref="BR-PAY-019",
        )
    return account_id


#: P1 a2-2 — "the clerk said nothing about the memo", which is not the same
#: as "the clerk cleared it". Absent keeps the line's own words (LBX-04).
LINE_TEXT = object()


def _reverse_for_returned_line(
    *,
    actor: Any,
    original: models.Payment,
    line: bankrec.BankLine,
    nsf_fee: dict[str, Any],
    bank_memo: Any = LINE_TEXT,
) -> Any:
    """⚑ THE HOOK INTO THE REVERSAL SERVICE — the bounce, started from the statement.

    PO 2026-10-30 Q2 (a): *"Match to payment"* finds the cheque and reverses it
    with the NSF fee, in one step. The reversal itself is `reversal.
    reverse_payment`'s — this function composes no reversal of its own. The
    NSF fee and the bank memo are lane NSF-FEE's (`eb36ee5bd`, `DEF-PAY-10698`
    / `DEF-PAY-10699`): the penalty is charged unless the clerk unticked it
    WITH a reason (PO Q1 2026-10-30), and the line's own text is the reversal's
    *Bank memo* (LBX-04, PO 2026-10-30).
    """
    from apps.payments import reversal as reversal_service

    waived = bool(nsf_fee.get("waived"))
    # W1 (`DEF-PAY-10765`, PO 2026-10-30 *"W1-A -Allow Finance Executive"*):
    # the bank-return door, which an Executive may use; the reason is pinned
    # inside it to *Returned by the bank*. `reverse_payment` stays Admin-only.
    return reversal_service.reverse_returned_by_bank(
        actor,
        payment_id=original.pk,
        returned_on=datetime.combine(line.posted_on, time.min, tzinfo=UTC),
        charge_nsf_fee=not waived,
        nsf_fee_waive_reason=nsf_fee.get("waive_reason") if waived else None,
        # P1 a2-2 (PO 2026-10-31): the clerk may EDIT the Bank memo before
        # confirming — pre-filled from the line, ≤ 60, blank means none. The
        # reversal service's `_clean_bank_memo` trims it and refuses 61.
        bank_memo=(line.reference or None) if bank_memo is LINE_TEXT else bank_memo,
    )


def return_candidates(bank_line_id: Any, *, query: str | None = None) -> list[dict[str, Any]]:
    """The payments a RETURNED line could be — by amount, cheque number and date.

    Two kinds, each a payment that was BANKED (in a deposit batch) on or before
    the line's date and within `RETURN_SEARCH_DAYS` of it:
      * already reversed by hand (Payments list or the account's Payments) and
        not yet matched to a line — the match LINKS to that reversal;
      * not reversed yet — the match REVERSES it, once.
    A line whose text carries the cheque number ranks first. `query` narrows by
    cheque number or payment number.
    """
    tenant_id = _tenant_id()
    line = _open_bank_line(tenant_id, bank_line_id, what="matched to a returned payment")
    target = -line.amount
    earliest = line.posted_on - timedelta(days=RETURN_SEARCH_DAYS)
    window = (
        datetime.combine(earliest, time.min, tzinfo=UTC),
        datetime.combine(line.posted_on, time.max, tzinfo=UTC),
    )
    claimed = bankrec.BankRecResolution.objects.filter(
        tenant_id=tenant_id, reversal_payment__isnull=False
    ).values("reversal_payment_id")
    reversals = (
        models.Payment.objects.filter(
            tenant_id=tenant_id,
            status=models.PAYMENT_REVERSED,
            amount=line.amount,
            reverses_payment__deposit_batch_id__isnull=False,
            reverses_payment__posted_at__range=window,
        )
        .exclude(pk__in=claimed)
        .select_related("reverses_payment")
    )
    reversed_ids = models.Payment.objects.filter(
        tenant_id=tenant_id, reverses_payment__isnull=False
    ).values("reverses_payment_id")
    originals = models.Payment.objects.filter(
        tenant_id=tenant_id,
        type=models.PAYMENT_TYPE_PAYMENT,
        status__in=STAMPABLE_STATUSES,
        reverses_payment__isnull=True,
        amount=target,
        deposit_batch_id__isnull=False,
        posted_at__range=window,
    ).exclude(pk__in=reversed_ids)
    needle = (query or "").strip().lower()
    reference = (line.reference or "").lower()
    rows: list[dict[str, Any]] = []
    for original, reversing in [(row.reverses_payment, row) for row in reversals] + [
        (row, None) for row in originals
    ]:
        cheque = original.confirmation or ""
        if needle and needle not in cheque.lower() and needle not in (original.payment_no or "").lower():
            continue
        rows.append(
            {
                "payment_id": str(original.pk),
                "payment_no": original.payment_no,
                "cheque": original.confirmation,
                "account_id": str(original.account_id),
                "amount": f"{target:.6f}",
                "posted_on": original.posted_at.date().isoformat(),
                "already_reversed": reversing is not None,
                "reversal_id": None if reversing is None else str(reversing.pk),
                "reversed_on": None
                if reversing is None
                else reversing.posted_at.date().isoformat(),
                "reference_match": bool(cheque) and cheque.lower() in reference,
            }
        )
    rows.sort(key=lambda row: (not row["reference_match"], row["posted_on"]), reverse=False)
    return rows


@permissions.require_role(permissions.SYSTEM_ADMIN, permissions.EXECUTIVE, br_ref="BR-PAY-1070")
def match_returned_line(
    *,
    actor: Any,
    bank_line_id: Any,
    payment_id: Any,
    occurred_at: datetime,
    nsf_fee_waived: bool = False,
    nsf_fee_waive_reason: str | None = None,
    bank_memo: Any = LINE_TEXT,
) -> LinePostingResult:
    """Match a RETURNED statement line to its payment — reversing it if nobody has.

    `payment_id` names the cheque that came back (or its reversing row). If it
    was already reversed by hand the match LINKS to that reversal and reverses
    nothing (PO Q2: *"never reversed twice"*); otherwise it is reversed here,
    reason *Returned by the bank*, through the reversal service. Either way the
    returned amount then moves from the holding account to cash — one balanced
    pair through the ledger posting service (hard rule 5) — and the line is
    explained under `returned_item` with that entry on it.

    Idempotent (hard rule 6): the same line and the same payment again answers
    with the row that exists. One line ↔ one reversal, in the service and in the
    database (`uq_bank_rec_resolutions_line` / `_reversal`).
    """
    tenant_id = _tenant_id()
    occurred_at = _require_moment(occurred_at, "the moment the returned line was matched")
    line = _open_bank_line(tenant_id, bank_line_id, what="matched to a returned payment")
    canonical = _canonical_reason(
        REASON_RETURNED_ITEM, where="a returned line", reasons=live_difference_reasons()
    )
    payment = (
        models.Payment.objects.filter(tenant_id=tenant_id, pk=payment_id)
        .select_related("reverses_payment")
        .first()
    )
    if payment is None:
        raise PaymentRuleError(
            f"payment {payment_id!r} is not one of this tenant's payments.", br_ref="BR-PAY-019"
        )
    if payment.reverses_payment_id is not None:
        original, reversing = payment.reverses_payment, payment
    else:
        original = payment
        reversing = models.Payment.objects.filter(
            tenant_id=tenant_id, reverses_payment=original
        ).first()

    prior = bankrec.BankRecResolution.objects.filter(tenant_id=tenant_id, bank_line=line).first()
    if prior is not None:
        if reversing is not None and prior.reversal_payment_id == reversing.pk:
            return LinePostingResult(
                resolution_id=str(prior.pk),
                bank_line_id=str(line.pk),
                reason_code=prior.reason_code,
                gl_account_id=str(prior.gl_account_id),
                amount=prior.amount,
                currency=settings_seam.tenant_currency(),
                created=False,
                journal_entry_id=None if prior.journal_entry_id is None else str(prior.journal_entry_id),
                posted=True,
                reversal_payment_id=str(reversing.pk),
                original_payment_id=str(original.pk),
            )
        raise PaymentRuleError(
            f"bank line {line.reference or line.pk} is already explained as {prior.reason_code} "
            f"for {prior.amount}. A line has one explanation.",
            br_ref="BR-PAY-019",
        )
    if original.deposit_batch_id is None:
        raise PaymentRuleError(
            f"payment {original.payment_no or original.pk} was never banked, so the bank cannot "
            "have returned it.",
            br_ref="BR-PAY-019",
        )
    if original.amount != -line.amount:
        raise PaymentRuleError(
            f"bank line {line.reference or line.pk} returns {-line.amount}; payment "
            f"{original.payment_no or original.pk} is {original.amount}. A returned line "
            "matches the whole cheque.",
            br_ref="BR-PAY-019",
        )
    if reversing is not None:
        if reversing.amount != line.amount:
            raise PaymentRuleError(
                f"payment {original.payment_no or original.pk} was reversed for "
                f"{-reversing.amount}, not the {-line.amount} the bank returned.",
                br_ref="BR-PAY-019",
            )
        taken = (
            bankrec.BankRecResolution.objects.filter(
                tenant_id=tenant_id, reversal_payment=reversing
            )
            .select_related("bank_line")
            .first()
        )
        if taken is not None:
            raise PaymentRuleError(
                f"the reversal of payment {original.payment_no or original.pk} is already matched "
                f"to bank line {taken.bank_line.reference or taken.bank_line_id}.",
                br_ref="BR-PAY-019",
            )
    holding = _holding_account_of(original)

    with transaction.atomic():
        reversed_now = False
        bounce = None
        if reversing is None:
            bounce = _reverse_for_returned_line(
                actor=actor,
                original=original,
                line=line,
                nsf_fee={"waived": nsf_fee_waived, "waive_reason": nsf_fee_waive_reason},
                bank_memo=bank_memo,
            )
            reversing = models.Payment.objects.get(tenant_id=tenant_id, pk=bounce.reversal_id)
            reversed_now = bool(bounce.created)
        posting = ledger_seam.post_bank_line_settlement(
            bank_line=line,
            counter_account_id=holding,
            event=ledger_seam.EVENT_RETURNED_ITEM,
            entry_date=line.posted_on,
            posted_at=occurred_at,
            currency=original.currency,
            memo=f"Returned item {line.reference or line.pk}: payment "
            f"{original.payment_no or original.pk}",
            actor=actor,
            audit_context={"payment_no": original.payment_no},
        )
        row = bankrec.BankRecResolution.objects.create(
            tenant_id=tenant_id,
            batch=None,
            bank_line=line,
            reason_code=canonical,
            gl_account_id=holding,
            amount=line.amount,
            note=f"payment {original.payment_no or original.pk}",
            actor_id=core_audit.actor_user_id(actor),
            journal_entry_id=posting.entry_id,
            reversal_payment=reversing,
        )
        core_audit.money_action(
            actor,
            AUDIT_LINE_RETURN_MATCHED,
            "bank_line",
            str(line.pk),
            after={
                "reference": line.reference,
                "posted_on": line.posted_on.isoformat(),
                "amount": str(line.amount),
                "payment_id": str(original.pk),
                "payment_no": original.payment_no,
                "reversal_payment_id": str(reversing.pk),
                "reversed_now": reversed_now,
                "nsf_fee_waived": nsf_fee_waived,
                "nsf_fee_waive_reason": nsf_fee_waive_reason,
                "holding_account_id": str(holding),
                "journal_entry_id": posting.entry_id,
                "job": None if actor is not None else "payments.match_returned_line",
            },
        )
    return LinePostingResult(
        resolution_id=str(row.pk),
        bank_line_id=str(line.pk),
        reason_code=canonical,
        gl_account_id=str(holding),
        amount=line.amount,
        currency=settings_seam.tenant_currency(),
        created=True,
        journal_entry_id=posting.entry_id,
        posted=True,
        reversal_payment_id=str(reversing.pk),
        original_payment_id=str(original.pk),
        reversed_now=reversed_now,
        nsf_fee_status=getattr(bounce, "nsf_fee_status", None),
        nsf_fee_amount=getattr(bounce, "nsf_fee_amount", None),
    )


def bank_fee_candidates(bank_line_id: Any) -> list[dict[str, Any]]:
    """Bank fees ALREADY POSTED on a Reverse that this fee line could be.

    The one-fee-posted-once guard (decision log 2026-10-30, *"LBX-05 built"*):
    a fee typed on a Reverse posted `payment|<id>|bank_fee`; the statement's
    line for the same fee LINKS to that entry instead of posting again.
    """
    tenant_id = _tenant_id()
    line = _open_bank_line(tenant_id, bank_line_id, what="explained as a bank fee")
    earliest = line.posted_on - timedelta(days=RETURN_SEARCH_DAYS)
    read = _resolve("ledger", "posted_entry_for_key")
    if not callable(read):  # pragma: no cover - defensive
        return []
    claimed = {
        str(entry_id)
        for entry_id in bankrec.BankRecResolution.objects.filter(
            tenant_id=tenant_id, bank_line__isnull=False, journal_entry_id__isnull=False
        ).values_list("journal_entry_id", flat=True)
    }
    rows: list[dict[str, Any]] = []
    reversals = models.Payment.objects.filter(
        tenant_id=tenant_id,
        status=models.PAYMENT_REVERSED,
        posted_at__range=(
            datetime.combine(earliest, time.min, tzinfo=UTC),
            datetime.combine(line.posted_on, time.max, tzinfo=UTC),
        ),
    ).select_related("reverses_payment")
    for reversing in reversals:
        original = reversing.reverses_payment
        if original is None:
            continue
        entry = read(ledger_seam.bank_fee_posting_key(original.pk))
        if entry is None or entry["entry_id"] in claimed or entry["debits"] != -line.amount:
            continue
        rows.append(
            {
                "payment_id": str(original.pk),
                "payment_no": original.payment_no,
                "cheque": original.confirmation,
                "amount": f"{-line.amount:.6f}",
                "reversed_on": reversing.posted_at.date().isoformat(),
                "journal_entry_id": entry["entry_id"],
            }
        )
    return rows


def explain_bank_fee_line(
    *,
    actor: Any,
    bank_line_id: Any,
    occurred_at: datetime,
    payment_id: Any = None,
) -> LinePostingResult:
    """The bank's own FEE line → Bank fees (6800) against cash, posted once.

    PO 2026-10-30 (Q1 = A, repeated as Q3 = A): *"explaining a bank-fee line
    posts it to Bank fees (6800) against cash"*. Worked: FEE1031 −24.00 →
    DR 6800 24.00 / CR cash 24.00. 6800 is found by DESIGNATION (`bank_fees`).

    **ONE FEE IS POSTED ONCE.** A Reverse (single, today) can already post the
    bank's fee for a returned item (`ledger_seam.post_bank_fee`). When it has,
    `payment_id` names that payment and this LINKS the line to the entry that
    exists — posting nothing — after checking the amounts agree and that no
    other line has claimed it (`uq_bank_rec_resolutions_line_entry`).
    """
    tenant_id = _tenant_id()
    occurred_at = _require_moment(occurred_at, "the moment the fee line was explained")
    line = _open_bank_line(tenant_id, bank_line_id, what="explained as a bank fee")
    canonical = _canonical_reason(
        REASON_BANK_FEE, where="a bank fee line", reasons=live_difference_reasons()
    )
    fees_account = bank_fees_account_id()
    if fees_account is None:
        raise PaymentRuleError(
            "no live account carries the 'bank_fees' designation, so the fee cannot be posted. "
            "The chart is the fix (GL mapping page), never a different bucket.",
            br_ref="BR-BIL-010",
        )
    linked_entry: str | None = None
    if payment_id:
        read = _resolve("ledger", "posted_entry_for_key")
        entry = read(ledger_seam.bank_fee_posting_key(payment_id)) if callable(read) else None
        if entry is None:
            raise PaymentRuleError(
                f"payment {payment_id!r} has no bank fee in the books to link this line to.",
                br_ref="BR-PAY-019",
            )
        if entry["debits"] != -line.amount:
            raise PaymentRuleError(
                f"the bank fee posted on that reversal is {entry['debits']}; this line is "
                f"{-line.amount}. A link needs the same fee.",
                br_ref="BR-PAY-019",
            )
        linked_entry = entry["entry_id"]

    prior = bankrec.BankRecResolution.objects.filter(tenant_id=tenant_id, bank_line=line).first()
    if prior is not None:
        same = prior.reason_code == canonical and (
            linked_entry is None or str(prior.journal_entry_id) == linked_entry
        )
        if same and prior.journal_entry_id is not None:
            return LinePostingResult(
                resolution_id=str(prior.pk),
                bank_line_id=str(line.pk),
                reason_code=prior.reason_code,
                gl_account_id=str(prior.gl_account_id),
                amount=prior.amount,
                currency=settings_seam.tenant_currency(),
                created=False,
                journal_entry_id=str(prior.journal_entry_id),
                posted=linked_entry is None,
            )
        raise PaymentRuleError(
            f"bank line {line.reference or line.pk} is already explained as {prior.reason_code} "
            f"for {prior.amount}. A line has one explanation.",
            br_ref="BR-PAY-019",
        )
    if linked_entry is not None and bankrec.BankRecResolution.objects.filter(
        tenant_id=tenant_id, bank_line__isnull=False, journal_entry_id=linked_entry
    ).exists():
        raise PaymentRuleError(
            "that bank fee is already linked to another statement line.", br_ref="BR-PAY-019"
        )

    with transaction.atomic():
        if linked_entry is None:
            posting = ledger_seam.post_bank_line_settlement(
                bank_line=line,
                counter_account_id=fees_account,
                event=ledger_seam.EVENT_LINE_BANK_FEE,
                entry_date=line.posted_on,
                posted_at=occurred_at,
                currency=settings_seam.tenant_currency(),
                memo=f"Bank fee {line.reference or line.pk}",
                actor=actor,
            )
            entry_id = posting.entry_id
        else:
            entry_id = linked_entry
        row = bankrec.BankRecResolution.objects.create(
            tenant_id=tenant_id,
            batch=None,
            bank_line=line,
            reason_code=canonical,
            gl_account_id=fees_account,
            amount=line.amount,
            note=None,
            actor_id=core_audit.actor_user_id(actor),
            journal_entry_id=entry_id,
        )
        core_audit.money_action(
            actor,
            AUDIT_LINE_FEE_EXPLAINED,
            "bank_line",
            str(line.pk),
            after={
                "reference": line.reference,
                "posted_on": line.posted_on.isoformat(),
                "amount": str(line.amount),
                "gl_account_id": str(fees_account),
                "journal_entry_id": entry_id,
                "posted": linked_entry is None,
                "linked_to_reversal_fee_of": None if payment_id is None else str(payment_id),
                "job": None if actor is not None else "payments.explain_bank_fee_line",
            },
        )
    return LinePostingResult(
        resolution_id=str(row.pk),
        bank_line_id=str(line.pk),
        reason_code=canonical,
        gl_account_id=str(fees_account),
        amount=line.amount,
        currency=settings_seam.tenant_currency(),
        created=True,
        journal_entry_id=entry_id,
        posted=linked_entry is None,
    )


def derive_processor_fee(
    *,
    recorded_total: Decimal,
    bank_total: Decimal,
    gl_account_id: Any,
    reason_code: str = "processor_fee",
    note: str | None = None,
) -> ResolutionInput:
    """**THE FEE MAY BE DERIVED FROM THE SHORTFALL** — PO 2026-08-12, OQ-160.

    Verbatim: *"derived from shortfall"*. Worked, on the PO's own card day:
    we take **5,120.40**, the bank credits **4,972.90**, and the **−147.50**
    difference becomes the fee line to 6800 Bank fees. The batch then reconciles
    NET, which is the PO's earlier ruling (*"Match net with a fee line"*)
    completed rather than changed.

    **WHY THIS WAS ROUTED AND NOT CHOSEN HERE.** Deriving the fee from the gap
    means the gap is, by construction, fully explained — so a genuine shortfall
    disappears into "fees". The decision log put it in one sentence: *"that
    distinction decides whether a $10 customer chargeback hides inside a fee
    line."* The PO ruled for derivation because most acquirers net silently and
    a stated-fee-only rule makes card reconciliation impossible in practice.

    **TWO THINGS THIS FUNCTION DOES SO THE HAZARD STAYS VISIBLE:**

      1. It returns a `ResolutionInput` — it does NOT reconcile. The derived
         figure enters `reconcile_batch` through the same door as a human's, is
         checked against the difference by the same tie-out, and is written to
         the books with a reason code and a GL account like any other. Nothing
         is auto-posted.
      2. It refuses a difference in the WRONG DIRECTION. A bank that credits
         MORE than we recorded has not charged us a fee; that is an overage and
         calling it one would post a negative expense to hide a real question.
    """
    difference = money.finalize(bank_total - recorded_total)
    if difference >= ZERO:
        raise PaymentRuleError(
            f"the bank credited {money.finalize(bank_total)} against a recorded "
            f"{money.finalize(recorded_total)}, a difference of {difference}. A processor fee "
            "makes the bank's credit SMALLER, so this difference cannot be one — an overage is a "
            "real question about where extra money came from, and naming it a fee would post a "
            "negative expense over the top of it.",
            br_ref="BR-PAY-019",
        )
    return ResolutionInput(
        reason_code=reason_code,
        gl_account_id=gl_account_id,
        amount=difference,
        note=note
        or (
            f"processor fee derived from the shortfall: bank {money.finalize(bank_total)} "
            f"less recorded {money.finalize(recorded_total)} (PO ruling 2026-08-12, OQ-160)"
        ),
    )


# ── US-PAY-022 / US-PAY-023 · resolve, reconcile, lock ──────────────────────
def _member_credit_split(batch: bankrec.DepositBatch) -> tuple[tuple[Any, Decimal], ...]:
    """What this batch's member receipts DEBITED, per holding account — the
    credit side of the reconciliation entry (CR-008 B-10, 2026-08-18).

    Read from the members' own journal entries through the ledger's published
    `entry_debit_totals`, NEVER from today's tender mapping: a tender
    re-pointed between receipt and reconciliation must still credit the
    account each payment's money actually sits in, or the difference strands
    in a clearing account forever. Before B-10 every receipt debited 1010
    Undeposited funds and the credit was one line; that is still exactly what
    this answers for such a batch — the split is the mechanism, not a new
    figure.

    **A member with NO journal entry is a pre-seam legacy payment** (recorded
    before 2026-08-11, when nothing posted receipts at all). Its share credits
    the `undeposited_funds` designation — the only lawful answer for that era,
    and byte-for-byte the pre-B-10 behaviour. The seam then refuses the whole
    request unless Σ(split) = recorded_total, so a membership the entries
    cannot account for stops the reconcile instead of plugging a difference.
    """
    entry_ids: list[Any] = []
    residual = ZERO
    for entry_id, amount in banked_members(batch).values_list("journal_entry_id", "amount"):
        if entry_id is None:
            residual += amount
        else:
            entry_ids.append(entry_id)

    read = _resolve("ledger", "entry_debit_totals")
    if not callable(read):  # pragma: no cover - defensive (hard-won law 3)
        raise PaymentRuleError(
            "apps.ledger.selectors publishes no entry_debit_totals, so this batch's "
            "reconciliation cannot know which holding accounts its member receipts debited. "
            "Refused rather than credited to a guessed account (CR-008 B-10).",
            br_ref="BR-PAY-019",
        )
    totals: dict[Any, Decimal] = dict(read(entry_ids)) if entry_ids else {}
    if residual > ZERO:
        undeposited = _resolve("ledger", "gl_account_id_for_designation")
        account_id = undeposited("undeposited_funds") if callable(undeposited) else None
        if account_id is None:
            raise PaymentRuleError(
                "this batch holds pre-seam payments with no journal entry, and no live account "
                "carries the 'undeposited_funds' designation to credit their share to. The chart "
                "is the fix (GL mapping page), never a different bucket.",
                br_ref="BR-BIL-010",
            )
        totals[str(account_id)] = totals.get(str(account_id), ZERO) + residual
    # Sorted for a stable line order — `created_at` is what an audit reader scrolls.
    return tuple(sorted(totals.items(), key=lambda item: str(item[0])))


def bank_fees_account_id() -> Any:
    """The tenant's `bank_fees` account (6800) — for the S40 default, by DESIGNATION.

    Published so a screen can pre-select the account the PO's ruling names
    without hardcoding 6800 anywhere: the chart is tenant-customisable
    (US-LED-005) and OQ-106's closure made a designation the way to find an
    account. Returns None when the tenant has designated none — the caller
    refuses, it does not substitute.
    """
    read = _resolve("ledger", "gl_account_id_for_designation")
    return read("bank_fees") if callable(read) else None


def reconcile_batch(
    *,
    actor: Any,
    batch_id: Any,
    posted_at: datetime,
    resolutions: tuple[ResolutionInput, ...] = (),
    entry_date: date | None = None,
    note: str | None = None,
) -> ReconcileResult:
    """Explain every difference, then RECONCILE — which is what realises the cash.

    The tie-out this refuses to skip (US-PAY-022 §7, verbatim): *"Σ reason-coded
    explanations + Σ member corrections = difference, then difference = 0 at
    reconcile."* Nothing here plugs a residual, and BR-PAY-035 keeps *"Force
    match anyway"* permanently superseded.

    **PE-11, ❄️ frozen:** bank **588.17** vs batch **593.17** → **−5.00**
    explained as a bank fee with a reason and a GL. **The PO's card day:**
    recorded **5,120.40**, bank **4,972.90**, one resolution of **−147.50** to
    6800 Bank fees — the batch reconciles NET and the fee is its own line.

    The books it writes (US-LED-001's payment rows, under the OQ-143 ruling):

        DR cash              bank_total
        DR/CR each resolution's own GL account, one line each, never netted
        CR undeposited funds recorded_total

    `entry_date` defaults to the BANK's posting date, because that is the day
    the bank confirmed the money and the PO's ruling makes confirmation the
    event that realises it. A caller may name a different book date (the PO's
    OQ-107 ruling: *"posting and actual dates can differ; ask actual date to
    user"*).
    """
    occurred_at = _require_moment(posted_at, "the moment the batch was reconciled")
    batch = _batch(batch_id)
    if batch.status == bankrec.BATCH_RECONCILED:
        raise PaymentRuleError(
            f"deposit batch {batch.code} is already reconciled and LOCKED (BR-PAY-004). "
            "Unreconcile is the only way back and it is audited.",
            br_ref="BR-PAY-004",
        )
    _refuse_if_the_till_is_open(batch)
    line = bankrec.BankLine.objects.filter(tenant_id=batch.tenant_id, deposit_batch=batch).first()
    # CS-17 — a batch may instead be tied inside a match SET, where several bank
    # lines and several batches foot to one another. Looked up only when the 1:1
    # link is absent, so the ordinary path is byte-for-byte what it was.
    set_lines: list[bankrec.BankLine] = []
    if line is None:
        member = bankrec.BankRecMatchMember.objects.filter(
            tenant_id=batch.tenant_id, batch=batch
        ).first()
        if member is not None:
            set_lines = list(
                bankrec.BankLine.objects.filter(
                    tenant_id=batch.tenant_id, match_members__match_set_id=member.match_set_id
                ).order_by("posted_on", "id")
            )
    if (line is None and not set_lines) or batch.bank_total is None:
        raise PaymentRuleError(
            f"deposit batch {batch.code} is not matched to a bank line, so there is nothing to "
            "reconcile it against. A batch reconciles against what the BANK said (BR-PAY-019); "
            "match it first — by hand if the amounts differ, or as a match SET if the bank "
            "combined it with another day's deposit (CS-17).",
            br_ref="BR-PAY-019",
        )

    recorded = _money(batch.recorded_total, what="the batch's recorded total")
    bank_total = _money(batch.bank_total, what="the bank's credit")
    difference = bank_total - recorded
    explained = ZERO
    checked: list[ResolutionInput] = []
    # CS-18 — read ONCE for the whole reconcile rather than per resolution: the
    # vocabulary cannot change mid-transaction and one query is one query.
    reasons = live_difference_reasons()
    for index, resolution in enumerate(resolutions, start=1):
        where = f"explanation {index} of {len(resolutions)}"
        amount = _money(resolution.amount, what=f"{where}'s amount")
        if amount == ZERO:
            raise PaymentRuleError(
                f"{where} explains 0.00, which explains nothing. Every row here moves part of a "
                "difference; a zero row would post a journal line for money that did not move.",
                br_ref="BR-PAY-019",
            )
        # CS-18: blank is refused here exactly as before, and a code the tenant's
        # own list does not carry is refused too — with the list quoted.
        canonical = _canonical_reason(resolution.reason_code, where=where, reasons=reasons)
        resolution = ResolutionInput(
            reason_code=canonical,
            gl_account_id=resolution.gl_account_id,
            amount=resolution.amount,
            note=resolution.note,
        )
        if not resolution.gl_account_id:
            raise PaymentRuleError(
                f"{where} ({resolution.reason_code}) names no GL account. BR-PAY-019 requires "
                "both; a difference posted to no account is money that left the tie-out and "
                "landed nowhere.",
                br_ref="BR-PAY-019",
            )
        if not _account_is_live(resolution.gl_account_id):
            raise PaymentRuleError(
                f"{where} names GL account {resolution.gl_account_id!r}, which is not a LIVE "
                "account of this tenant's own chart. It belongs to another tenant, has been "
                "deactivated, or does not exist — none of which is a reason to pick a different "
                "bucket. The processor-fee account the PO named is 6800 Bank fees, resolved by "
                "DESIGNATION (`bank_fees`), never by number.",
                br_ref="BR-PAY-019",
            )
        explained += amount
        checked.append(resolution)

    if explained != difference:
        raise PaymentRuleError(
            f"deposit batch {batch.code} does not tie: we recorded {recorded}, the bank shows "
            f"{bank_total}, a difference of {difference} — and the explanations sum to "
            f"{explained}, leaving {difference - explained} unexplained. Nothing is reconciled "
            "and nothing is posted. BR-PAY-019: every difference carries a reason and a GL, and "
            "BR-PAY-035 made 'Force match anyway' permanently superseded — there is no path that "
            "reconciles a residual.",
            br_ref="BR-PAY-019",
        )

    # CS-17 — for a SET the book date is the LAST bank line in it: the batch is
    # not confirmed until every line of the tie has landed, and confirming it on
    # the first would realise cash before the bank finished saying so (the
    # OQ-143 ruling read forwards). A 1:1 match has one line and is unchanged.
    book_date = entry_date or (line.posted_on if line is not None else set_lines[-1].posted_on)
    with transaction.atomic():
        # CLAUDE.md rule 5 — payments posts NOTHING itself. The seam hands the
        # ledger a fully-specified balanced request and the ledger writes it.
        #
        # THE POSTING COMES FIRST, and the order is load-bearing rather than
        # stylistic: `bank_rec_resolutions` is append-only from birth (migration
        # 0005), so a row written before the entry exists could never be stamped
        # with its `journal_entry_id` afterwards — the trigger refuses the
        # UPDATE, which is exactly what it is for. Writing the rows with the
        # entry id already on them is the only shape that respects both laws.
        posting = ledger_seam.post_batch_reconciled(
            batch=batch,
            bank_total=bank_total,
            recorded_total=recorded,
            resolutions=tuple(
                (item.reason_code.strip(), item.gl_account_id, item.amount) for item in checked
            ),
            entry_date=book_date,
            posted_at=occurred_at,
            attempt=_reconcile_attempt(batch),
            actor=actor,
            # CR-008 B-10: credit EXACTLY what the member receipts debited —
            # per-tender clearing accounts since 2026-08-18, undeposited funds
            # for everything else — read from the entries themselves.
            undeposited_credits=_member_credit_split(batch),
        )

        rows: list[dict[str, Any]] = []
        for resolution in checked:
            row = bankrec.BankRecResolution.objects.create(
                tenant_id=batch.tenant_id,
                batch=batch,
                reason_code=resolution.reason_code.strip(),
                gl_account_id=resolution.gl_account_id,
                amount=resolution.amount,
                note=resolution.note or note,
                actor_id=core_audit.actor_user_id(actor),  # DEF-CUS-9081
                journal_entry_id=posting.entry_id,
            )
            rows.append(
                {
                    "resolution_id": str(row.pk),
                    "reason_code": row.reason_code,
                    "gl_account_id": str(row.gl_account_id),
                    "amount": str(row.amount),
                    "journal_entry_id": posting.entry_id,
                }
            )
            _trail(
                batch,
                bankrec.EVENT_RESOLVED,
                actor=actor,
                occurred_at=occurred_at,
                reason_code=row.reason_code,
                gl_account_id=str(row.gl_account_id),
                amount=str(row.amount),
                note=row.note,
            )
            core_audit.money_action(
                actor,
                AUDIT_REC_RESOLVED,
                "deposit_batch",
                str(batch.pk),
                after={
                    "code": batch.code,
                    "reason_code": row.reason_code,
                    "gl_account_id": str(row.gl_account_id),
                    "amount": str(row.amount),
                    "recorded_total": str(recorded),
                    "bank_total": str(bank_total),
                    "journal_entry_id": posting.entry_id,
                    "job": None if actor is not None else "payments.reconcile_batch",
                },
            )

        batch.status = bankrec.BATCH_RECONCILED
        batch.save(update_fields=["status", "updated_at"])
        # ── CR-186-BRC10 · THE MEMBERS CLEAR, WITH THE BANK'S DATE ──────────
        cleared_count = clear_members(
            batch, cleared_on=book_date, actor=actor, occurred_at=occurred_at
        )
        _trail(
            batch,
            bankrec.EVENT_RECONCILED,
            actor=actor,
            occurred_at=occurred_at,
            recorded_total=str(recorded),
            bank_total=str(bank_total),
            difference=str(difference),
            journal_entry_id=posting.entry_id,
            entry_date=book_date.isoformat(),
            payments_cleared=cleared_count,
        )
        for action in (AUDIT_REC_CONFIRMED, AUDIT_BATCH_RECONCILED):
            core_audit.money_action(
                actor,
                action,
                "deposit_batch",
                str(batch.pk),
                after={
                    "code": batch.code,
                    "recorded_total": str(recorded),
                    "bank_total": str(bank_total),
                    "difference": str(difference),
                    "explanations": len(rows),
                    "journal_entry_id": posting.entry_id,
                    "posting_key": posting.posting_key,
                    "entry_date": book_date.isoformat(),
                    "job": None if actor is not None else "payments.reconcile_batch",
                },
            )

    return ReconcileResult(
        batch_id=str(batch.pk),
        code=batch.code,
        recorded_total=recorded,
        bank_total=bank_total,
        difference=difference,
        explained=explained,
        journal_entry_id=posting.entry_id,
        posting_key=posting.posting_key,
        created=posting.created,
        resolutions=tuple(rows),
    )


#: Hard rule 7's code for the one status move a posted payment makes at the bank.
AUDIT_PAYMENT_CLEARED = "payment.cleared"


def clear_members(
    batch: bankrec.DepositBatch, *, cleared_on: date, actor: Any, occurred_at: datetime
) -> int:
    """Every POSTED member of a just-reconciled batch moves to `cleared`.

    PO 2026-10-21, verbatim: *"uitlity will reconcile it bank statement that
    time it is cleared with clearing date"*, and the batch ruling's point 4:
    *"Reconciling the batch … moves every member payment `posted` →
    `cleared`."* This is the ONE place that move happens, and
    `payments_payment_immutable()` (body from `payments/0051`) is the ONE door
    in hard rule 4 that lets it: `status` and `cleared_at` on a posted row,
    the date written once.

    **The clearing date is the BANK's date** — the reconciliation's book date,
    which defaults to the bank line's posting date — stored as midnight in the
    utility's own zone, the ruled anchor for a business date (OQ-153).

    An Unreconcile puts this batch's cleared members back to `posted` with no
    clearing date (`unclear_members`, PO 2026-10-21), so a re-reconcile clears
    them again with ITS date. A member still `cleared` here is a legacy row and
    keeps its date: the filter below never selects it. A `cancelled` member
    is not touched. Each cleared payment writes its own `payment.cleared`
    audit row (hard rule 7) inside the reconcile's transaction.
    """
    moment = datetime.combine(cleared_on, time.min, tzinfo=settings_seam.tenant_timezone())
    members = list(
        models.Payment.objects.select_for_update()
        .filter(
            tenant_id=batch.tenant_id,
            deposit_batch_id=batch.pk,
            status=models.PAYMENT_POSTED,
        )
        .order_by("posted_at", "id")
    )
    for payment in members:
        payment.status = models.PAYMENT_CLEARED
        payment.cleared_at = moment
        payment.save(update_fields=["status", "cleared_at", "updated_at"])
        core_audit.money_action(
            actor,
            AUDIT_PAYMENT_CLEARED,
            "payment",
            str(payment.pk),
            before={"status": models.PAYMENT_POSTED, "cleared_at": None},
            after={
                "status": models.PAYMENT_CLEARED,
                "cleared_at": moment.isoformat(),
                "deposit_batch_id": str(batch.pk),
                "deposit_batch_code": batch.code,
                "job": None if actor is not None else "payments.reconcile_batch",
            },
        )
    return len(members)


#: Hard rule 7's code for the move back, when a reconciliation is undone.
AUDIT_PAYMENT_UNCLEARED = "payment.uncleared"

#: `payments/0052`'s transaction-local window; its value is the batch id.
UNCLEARING_GUC = "app.payment_unclearing"


def _set_unclearing_window(value: str) -> None:
    """Open (the batch id) or shut (`""`) `payments/0052`'s door.

    `set_config(…, true)` is TRANSACTION-LOCAL, so a crash or a rollback shuts
    it whatever else happens. A no-op on SQLite, which has no trigger.
    """
    if connection.vendor != "postgresql":
        return
    with connection.cursor() as cursor:
        cursor.execute("SELECT set_config(%s, %s, true)", [UNCLEARING_GUC, value])


def unclear_members(batch: bankrec.DepositBatch, *, actor: Any) -> int:
    """Every CLEARED member of a batch being unreconciled goes back to `posted`.

    PO ruling 2026-10-21, *"Allow, back to Posted"*: the $800.00 batch
    reconciled 16 Oct and then undone → its three payments read Posted with no
    clearing date until the batch is reconciled again. `cancelled` and legacy
    rows in other statuses are not touched. Each move writes
    `payment.uncleared` to `audit_log` (hard rule 7). Must run inside the
    Unreconcile transaction.
    """
    members = list(
        models.Payment.objects.select_for_update()
        .filter(
            tenant_id=batch.tenant_id,
            deposit_batch_id=batch.pk,
            status=models.PAYMENT_CLEARED,
        )
        .order_by("posted_at", "id")
    )
    if not members:
        return 0
    _set_unclearing_window(str(batch.pk))
    try:
        for payment in members:
            was = payment.cleared_at
            payment.status = models.PAYMENT_POSTED
            payment.cleared_at = None
            payment.save(update_fields=["status", "cleared_at", "updated_at"])
            core_audit.money_action(
                actor,
                AUDIT_PAYMENT_UNCLEARED,
                "payment",
                str(payment.pk),
                before={
                    "status": models.PAYMENT_CLEARED,
                    "cleared_at": was.isoformat() if was else None,
                },
                after={
                    "status": models.PAYMENT_POSTED,
                    "cleared_at": None,
                    "deposit_batch_id": str(batch.pk),
                    "deposit_batch_code": batch.code,
                    "job": None if actor is not None else "payments.unreconcile_batch",
                },
            )
    finally:
        _set_unclearing_window("")
    return len(members)


def _reconcile_attempt(batch: bankrec.DepositBatch) -> int:
    """How many times this batch has been reconciled before (0 the first time).

    It is the replay key's third part, so that a batch reconciled, unreconciled
    and reconciled again posts a SECOND entry rather than replaying the first —
    the corrected figures are different money and the ledger would no-op them
    onto the original key (hard rule 6 cuts both ways).
    """
    return bankrec.DepositBatchEvent.objects.filter(
        tenant_id=batch.tenant_id, batch=batch, event=bankrec.EVENT_RECONCILED
    ).count()


def _last_reconciliation_entry_id(batch: bankrec.DepositBatch) -> Any:
    """The journal entry the most recent reconcile posted, from the batch's trail.

    The trail is where it was written (`_trail(..., journal_entry_id=…)`) and the
    trail is append-only, so this cannot answer with an entry that was edited
    away. Returns None for a batch reconciled before that stamp existed — the
    seam treats that as "nothing to mirror" rather than refusing an Unreconcile
    BR-PAY-004 makes CONFIRMED.
    """
    event = (
        bankrec.DepositBatchEvent.objects.filter(
            tenant_id=batch.tenant_id, batch=batch, event=bankrec.EVENT_RECONCILED
        )
        .order_by("-occurred_at", "-created_at")
        .first()
    )
    return (event.detail or {}).get("journal_entry_id") if event else None


def _account_is_live(account_id: Any) -> bool:
    """The LEDGER's own answer, resolved by name — payments never reads its ORM."""
    read = _resolve("ledger", "account_is_live")
    if not callable(read):
        raise PaymentRuleError(
            "apps.ledger.selectors.account_is_live is not published, so the GL account on this "
            "explanation cannot be checked. A difference posted to an unchecked account is a "
            "reconciliation that ties on screen and not in the books.",
            br_ref="BR-PAY-019",
        )
    return bool(read(account_id))


def unreconcile_batch(
    *, actor: Any, batch_id: Any, reason: str, posted_at: datetime, entry_date: date | None = None
) -> dict[str, Any]:
    """BR-PAY-004's ONLY way back — audited, and it takes the cash back out.

    *"Reconciled deposit batches lock; Unreconcile is the only reversal."* The
    batch returns to `unmatched` for rework and every trail entry it already has
    stays forever (US-PAY-023 TC-4).

    **It also reverses the reconciliation entry**, through the ledger's own
    `reverse_entry` (US-LED-003: a correction is a NEW linked mirror, never an
    edit). It has to: the PO's ruling of 2026-08-11 says money is not cash until
    the bank confirms it, and unreconciling is the statement that the
    confirmation did not hold — leaving the entry would show CASH for a batch the
    product itself calls unreconciled, and the next reconcile would realise the
    same money twice. Nobody has ruled it in those words, so it is **OQ-163**,
    raised and implemented rather than stubbed (see the module docstring).

    **ITS CLEARED MEMBERS GO BACK TO `posted` (PO ruling 2026-10-21, *"Allow,
    back to Posted"*; decision log *"TWO CR-186 FOLLOW-UP RULINGS"* (1)).** The
    clearing date was the reconciliation's, so undoing the reconciliation
    removes it; a later reconcile clears them again with its own date. Hard
    rule 4's door for that is `payments/0052`, opened only by
    `unclear_members` below for this batch. The balance does not move: posted
    and cleared both count. Supersedes our judgment of earlier the same day
    that the members stay `cleared`.
    """
    occurred_at = _require_moment(posted_at, "the moment the batch was unreconciled")
    if not str(reason or "").strip():
        raise PaymentRuleError(
            "Unreconcile needs a reason: it re-opens a signed-off day (BR-PAY-004, US-PAY-023 "
            "TC-4 — 'confirm + reason, audited'), and the trail is the only record of why.",
            br_ref="BR-PAY-004",
        )
    batch = _batch(batch_id)
    if batch.status != bankrec.BATCH_RECONCILED:
        raise PaymentRuleError(
            f"deposit batch {batch.code} is {batch.status}, not reconciled — there is nothing to "
            "unreconcile.",
            br_ref="BR-PAY-004",
        )

    with transaction.atomic():
        reversal = ledger_seam.reverse_batch_reconciliation(
            batch=batch,
            # The entry to mirror, read off THIS batch's own trail — the ledger
            # publishes no lookup by posting key, and payments may not query the
            # journal itself (B1).
            entry_id=_last_reconciliation_entry_id(batch),
            entry_date=entry_date,
            posted_at=occurred_at,
            attempt=_reconcile_attempt(batch),
            actor=actor,
        )
        uncleared = unclear_members(batch, actor=actor)
        batch.status = bankrec.BATCH_UNMATCHED
        batch.save(update_fields=["status", "updated_at"])
        _trail(
            batch,
            bankrec.EVENT_UNRECONCILED,
            actor=actor,
            occurred_at=occurred_at,
            reason=reason.strip(),
            reversal_entry_id=reversal.entry_id if reversal else None,
        )
        core_audit.money_action(
            actor,
            AUDIT_BATCH_UNRECONCILED,
            "deposit_batch",
            str(batch.pk),
            after={
                "code": batch.code,
                "reason": reason.strip(),
                "recorded_total": str(batch.recorded_total),
                "bank_total": str(batch.bank_total) if batch.bank_total is not None else None,
                "reversal_entry_id": reversal.entry_id if reversal else None,
                "payments_uncleared": uncleared,
                "job": None if actor is not None else "payments.unreconcile_batch",
            },
        )
    return {
        "batch_id": str(batch.pk),
        "code": batch.code,
        "status": batch.status,
        "reversal_entry_id": reversal.entry_id if reversal else None,
        "payments_uncleared": uncleared,
    }


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-PAY-020@b6e4c19 (the five EP-PAY-06 sources, in order: 04-docs/02-decisions/02-database-design-brief.md §2 + Addenda r12 #10/#13/#17 + r14 #1 + DB-12 · 04-docs/05-modules/08-payments/06-epics/EP-PAY-06-deposits-bank-rec.md US-PAY-020..023 · 08-payments/02-business-rules.md BR-PAY-004/019/021/025/028/035 · 08-payments/03-field-map.md §6 · 08-payments/07-pre-session-model.md §7 PE-10/PE-11 + §12; plus the two PO rulings of 2026-08-11 in 12-governance/02-decision-log.md — OQ-143 "Cash is received but undeposted…" and OQ-144 "Match net with a fee line")
# generated: 2026-08-11 by Eng-Lead (W5 deposit-batch + bank-reconciliation lane) · AMENDED 2026-08-18 by the CR-008 ledger lane (B-10 / OQ-264 CLOSED: `_member_credit_split` — the reconciliation credit is what each member receipt DEBITED, read from the entries through the ledger's `entry_debit_totals`; legacy no-entry members credit undeposited; the seam refuses a split that does not foot to recorded_total. Both legs of the tender→GL wiring moved in this one change)
# checklist: A✔ B✔ C✔ D=deferred(no-API-half — NOTHING serves S37–S40; the engine is unreachable from the product and it is REPORTED on every result, not claimed) E=deferred(no-frontend-half — same) F✔ G✔ H=deferred(PO 2026-08-09)
# gates: ruff✔ black✔ · pytest tests/test_us_pay_020_023_bank_rec.py · PROVED RED BEFORE GREEN, each mutation run and its failure quoted verbatim in 12-governance/09-human-review-ledger.md: (1) the card day reconciled against GROSS — the $5,120.40/$4,972.90 day can then never tie; (2) the fee absorbed into the cash line instead of posting to 6800 — the books lose the fee entirely; (3) a reconciled+locked batch edited — both the service refusal and the 0005 trigger; (4) cash posted on RECEIPT instead of on reconciliation — the PO's OQ-143 ruling defeated; (5) the same statement file imported twice
# exceptions: (1) NO SCREEN AND NO ENDPOINT. S37–S40 and every route are unbuilt;
#         the engine is reachable only from a test (hard-won law 2), carried on
#         RECONCILE_UNAVAILABLE so no caller has to infer it
#         (2) OQ-160 — the AUTOMATIC fee rule (derive the fee from the
#         difference) raises `NotImplementedError`. The PO ruled "match net with
#         a fee line" and the decision log records that the EVIDENCE for the fee
#         (settlement file vs derived) is deliberately unsettled
#         (3) OQ-161 — grouped matching (many-to-one / one-to-many) is not built;
#         a bank that combines two deposits leaves both unmatched
#         (4) OQ-162 — the frozen DEP-{MMDD}-{METHOD} default renders the same
#         code in 2026 and 2027 while B2 makes it UNIQUE per tenant; the second
#         year is REFUSED by name rather than renumbering a ❄️ figure (DEF-066)
#         (5) OQ-163 — Unreconcile REVERSES the reconciliation entry. Implemented
#         rather than stubbed because the alternative contradicts the PO's own
#         cash ruling and would realise the same money twice; raised for
#         confirmation
#         (6) OQ-134 — RULED 2026-08-12, and the refusal this file carried while
#         the question stood is GONE. It used to refuse a bounce inside a
#         RECONCILED batch from both sides, claiming the choice between the lock
#         and the tie-out was not this lane's; that was correct until the PO made
#         it. The lock HOLDS (DEP-260805-CHK stays $2,840.00 when cheque #4021's
#         $100.00 comes back) so `assert_bounce_allowed` now PERMITS a locked
#         batch, and `recompute_batch_total` still refuses — as a RULE
#         (PaymentRuleError / BR-PAY-004), because the total does not move.
#         Two things still reported: an UNREADABLE batch fails closed (a broken
#         reference was never the question), and ⚠ `assert_bounce_allowed` STILL
#         HAS NO CALLER — the bounce path calls apps/payments/reversal
#         ._refuse_if_batch_locked, a second implementation of one law
#         (7) the drawer day is read off `posted_at` in UTC; a tenant west of UTC
#         banking in the evening lands on the next UTC day — OQ-153, already
#         open, named rather than solved with an invented conversion
#         (8) CLOSED 2026-09-22 — the DEP- code was composed here and is now
#         ALLOCATED from the tenant's `deposit_batch` series (PO: "(b) Put it in
#         Settings today - DEP-260922-0001 - Settings -> Numbering, like every
#         other number"). The grammar objection was true of a code carrying the
#         TENDER, and the tender has left the code
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
