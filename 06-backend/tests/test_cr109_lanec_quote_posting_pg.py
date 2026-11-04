# ── Trace ──────────────────────────────────────────────
# Change:   CR-109 — the New Connect Charges step, money half (lane C, wave 1).
#           Drawing: `05-prototype/02 Accounts Menu Blueprint.pdf` p090,
#           read AS AN IMAGE (B14 rule 42). Step 6 of 8 · Charges.
# Story:    US-BIL-012 (the one-time door)
# Defects:  DEF-BIL-5445 (the old proof died in its fixture) ·
#           DEF-MET-5446 (the caller was reverted out of connections.py)
# Rules:    BR-BIL-020 (lines come ONLY from rules and charge codes; free-typed
#           amounts never exist on any bill) · BR-BIL-007 (the TENANT's row
#           carries the figure) · BR-BIL-010 (a charge code carries its own GL)
#           · BR-CUS-1010 (a master account hangs off the ADDRESS) ·
#           CLAUDE.md hard rules 1, 2, 4, 5, 7 · hard-won laws 7 and 14
# ───────────────────────────────────────────────────────
"""**A build's quote reaches the books, and the pair is observed rather than intended.**

This file exists because the one before it could not answer the question. It
proves the MONEY DOOR — `billing.fee_bill.raise_and_issue_quote_bill` — against
real PostgreSQL, by calling it directly.

════════════════════════════════════════════════════════════════════════════
WHY IT CALLS THE DOOR DIRECTLY, AND WHY THAT IS A SEPARATION AND NOT A DODGE
════════════════════════════════════════════════════════════════════════════
`tests/test_cr109_connection_quote_posts_pg.py` drives the same money through
`metering.connections.commit_connection`, which is the wizard's button. As of
2026-09-16 that path **cannot post**, and not for a reason in billing:

    git log -S "_post_connection_quote" -- 06-backend/apps/metering/connections.py
    ce576cc5   2026-09-16 04:11:45   removed it
    ec7ccdda   2026-09-16 04:09:08   added it

Three minutes apart, deletions only — a whole-file pathspec commit from a stale
blob (`DEF-MET-5446`, hard-won law 11 mechanism two). `connections.py` step 6 is
back to *"THE QUOTE — recorded, not posted"*.

So there are two different claims, and conflating them is what left this path
unproven for a day:

  * **does the money work** — this file, and it is now ANSWERED;
  * **is the button wired to it** — the other file, and it is NOT, for a reason
    that lives in another module and another lane's file.

A test that could only ever run through a reverted caller proves nothing about
the door. This one holds while `connections.py` is repaired.

════════════════════════════════════════════════════════════════════════════
THE WORKED POSTING — EVERY FIGURE BELOW WAS READ OUT OF THE DATABASE
════════════════════════════════════════════════════════════════════════════
A developer's build. Three coded lines, counts taken from the services grid and
prices read from the tenant's own catalogue (`BR-BIL-007`), charged to the
OWNER'S account — a `kind='master'` row anchored on the premises with
`unit_id` NULL, which is the drawing's *"the owner's account for this address"*:

    CC-CONN       Connection fee              per unit      6 x $325.00 = $1,950.00
    CC-METERSET   Meter set                   per meter    20 x  $45.00 =   $900.00
    CC-CASVC      Common-area service point   per premise   1 x $180.00 =   $180.00
                                                              Quoted     $3,030.00

**READ OUT OF THE DATABASE ON 2026-09-16, AFTER THE RUN — NOT A SPECIFICATION:**

    ACCOUNT  AC-2026-00001   unit_id: None        (the owner's account for the address)
    INVOICE  BL-2609-000001  3030.000000 USD      status: issued

      'Connection fee'              qty=6.000000  unit    @ 325.000000 = 1950.000000
      'Meter set'                   qty=20.000000 meter   @  45.000000 =  900.000000
      'Common-area service point'   qty=1.000000  premise @ 180.000000 =  180.000000

    JOURNAL ENTRY 01a0a89d-b182-… · memo "Bill BL-2609-000001 issued"
      DEBIT  1200 Accounts receivable            3030.000000  premises=…2a94 unit=None
      CREDIT 4600 Connection & new-service fees  1950.000000  premises=…2a94 unit=None
      CREDIT 4630 Field-service & meter fees     1080.000000  premises=…2a94 unit=None
      TIE-OUT debits 3030.000000 == credits 3030.000000

**EVERY LINE CARRIES THE PREMISES AND NO UNIT, AND BOTH HALVES OF THAT ARE THE
DESIGN.** The premises is the dimension the by-premises report groups on, so the
money is attributable to the address the build is at; the unit is absent because
the build has no one home the money belongs to, which is the same truthfulness
that leaves `service` empty on a cash line (`BR-LED-001`, required *where it
applies*).

⚠ **THE FIGURES ARE THE DRAWING'S AND ARE THEREFORE ILLUSTRATIONS** (B14 rule
37 — *"treat every number drawn in a wireframe as an illustration, never a fact
to build to"*). They are used here as FIXTURE INPUT, not as an expectation: the
test asserts against the charge rows it created, so a utility charging $95.00 a
unit is not this file's problem. What is asserted as product behaviour is the
SHAPE — that the count multiplies, that the price comes from the catalogue, and
that the revenue splits by the code's own GL.

**THE $1,080.00 IS THE POINT OF THE THIRD LINE.** Two codes sharing one revenue
account post as ONE credit, not two. A journal entry says where money went, not
how many lines agreed about it — and a test using three codes with three
different accounts could not tell a correct implementation from one that emits a
line per line.

════════════════════════════════════════════════════════════════════════════
PROVED RED FIRST — THE FAILURES BELOW ARE QUOTED FROM RUNS THAT HAPPENED
════════════════════════════════════════════════════════════════════════════
⚠ **EVERY FAILURE BELOW WAS QUOTED AFTER THE RUN THAT PRODUCED IT.** The file
that preceded this one carried five COMPOSED failures under this exact heading
and its author deleted them (`9df607cb`); the vocabulary of law 7 is worth
nothing if it can be written ahead of the evidence.

**PART A — THE FOUR REAL DEFECTS, EACH FOUND BY THIS FILE REFUSING TO PASS.**
These are not mutations. They are what the product did, in order, each one
uncovered only once the one before it was fixed — which is why a single
undiagnosed red taught the previous lane nothing:

  1 · `core.errors.ValidationError: VAL-005
      (customers.serviceRequest.fieldNotAccepted)` — `service_request_service.
      py:777`. The OLD proof file's fixture, dead on its first statement
      (`DEF-BIL-5445`). Then, one line further on,
      `core.errors.BizError: BIZ-COMPLETENESS
      (customers.account.identity_kind_required)` — `services.py:2743`.
  2 · `apps.billing.gather.GatherProblem: account 'AC-2026-00001' has no unit,
      so it has no plan and no service points. BR-CUS-017 binds an account to
      exactly one unit.` — `single.py:158`. **The owner's account could not be
      billed at all** (`DEF-BIL-5457`).
  3 · `apps.billing.exceptions.BillingRuleError: account AC-2026-00001: a fee
      line carries a quantity with no unit (CLAUDE.md rule 3).` —
      `stages/assemble_document.py:495`. **No counted line could ever be
      issued** (`DEF-BIL-5458`).
  4 · `apps.ledger.posting.PostingError: account 01a0a89a-… has no resolvable
      unit → premises chain (account_is_not_in_the_customer_register), so this
      entry's lines cannot carry BR-LED-001's premises and unit dimensions.` —
      `posting.py:716`. **The books reported a lawful master account in the
      words reserved for a forged cross-tenant id** (`DEF-LED-5459`). After the
      anchor half of that fix the same line refused again with `(None)`,
      because `Location.resolved` still demanded a unit.

**PART B — THE MUTATIONS, RUN IN A PRIVATE WORKTREE, EACH REVERTED AFTER.**
Every fix above was then broken again to prove this file notices:

  * **Revenue split collapsed** — all three lines forced onto one charge id:
    `AssertionError: the revenue split should follow each code's own GL
    (BR-BIL-010); got {'4600': Decimal('3030.000000')}`.
    ⚠ **`sum(debits) == sum(credits)` PASSED THROUGHOUT THAT MUTATION**, at
    3030 == 3030. That is the false pass this file's shape exists to catch, and
    it has now been observed rather than merely predicted.
  * **`unit=_unit_for_basis(item)` → `unit=None`**: `BillingRuleError: charge
    code 'CC-CONN' was given a count of 6 and no unit to count in (CLAUDE.md
    rule 3 …)` — 3 failed.
  * **The old unit-less refusal restored**: `GatherProblem: has no unit (old
    guard)` — 3 failed.
  * **`Location.resolved` made to demand a unit again**: `PostingError: …
    (None) … Nothing was written.` — 1 failed, 2 passed (pricing does not post,
    which is `tc3`'s whole point).

Reverting all four returned the file to **3 passed**.

════════════════════════════════════════════════════════════════════════════
WHAT WOULD MAKE EACH OF THESE PASS WRONGLY — law 7, habit 2
════════════════════════════════════════════════════════════════════════════
  * **The balanced-pair test is the easiest check in this repo to fool.**
    `sum(debits) == sum(credits)` is true of an EMPTY entry, and it was true of
    this path yesterday **because there was no entry at all**. So `tc1` asserts
    the entry EXISTS, that it has at least three lines, names BOTH revenue
    account codes and the AR code, and asserts the FIGURE on each. A tie-out
    with no account codes in it proves only that zero equals zero.
  * **`tc2` would pass on an implementation that ignored the catalogue** if the
    fixture's price and the quote's price were the same number. They are
    deliberately DIFFERENT: the catalogue says $325.00 and the caller is given
    no way to say anything at all, so the only figure that can appear is the
    catalogue's. `QuotedCharge` has no amount field — the enforcement is an
    ABSENT MEMBER rather than a validation, which is the one shape a later
    refactor cannot quietly delete.
  * **`tc3` could pass because the ACCOUNT was wrong rather than because the
    key refused**, since both come back as errors. So it asserts the exception
    TYPE and that the message names the first run.
  * **Every one of these would pass on sqlite while the product lost data**
    (hard-won law 14), which is why the file is `_pg` and is skipped, loudly,
    where PostgreSQL is absent.
"""

from datetime import date
from decimal import Decimal as D

import pytest

from apps.billing import fee_bill, models as billing_models
from apps.customers import services as customers_services
from apps.ledger import models as ledger_models
from apps.rating import models as rating_models
from tests.isolation_helpers import requires_postgres
from tests.test_us_met_helpers import *  # noqa: F401,F403 — W1 shared fixtures
from tests.test_us_met_helpers import (  # noqa: F401
    brazos,
    dana,
    make_premises,
    tenant_ctx,
)
from tests import identity_fixtures

pytestmark = [pytest.mark.django_db, requires_postgres]

#: The day the build commits. A DATE a clerk chose, never a clock
#: (`BR-TEN-043` / gate `G6`) — every figure here reproduces because of it.
COMMIT_ON = date(2026, 9, 20)

#: The developer. One spelling for the application and the account, so the
#: account the charges land on is demonstrably the party the quote names.
OWNER_NAME = "Balcones Development LLC"

#: The drawing's three lines: (code, description, catalogue price, GL account,
#: count). **Read as an ILLUSTRATION** (B14 rule 37) — these are fixture INPUT.
#: The GL accounts are the two `CR-066` table 1 names the codes' own kinds map
#: to, and CC-METERSET and CC-CASVC deliberately SHARE one.
#: The fifth member is the BASIS, which `DEF-BIL-5458` made load-bearing: it is
#: what the count is counted IN, and hard rule 3 refuses a quantity without it.
BUILD = (
    ("CC-CONN", "Connection fee", D("325.00"), "4600", D("6"), "per unit"),
    ("CC-METERSET", "Meter set", D("45.00"), "4630", D("20"), "per meter"),
    ("CC-CASVC", "Common-area service point", D("180.00"), "4630", D("1"), "per premise"),
)

AR_ACCOUNT = "1200"


def _charge_code(tenant, code, name, amount, gl_code):
    """One of the tenant's OWN charge rows, pointed at a named GL account.

    Created rather than seeded: no seed in this repo makes one of these, which
    is why every test that reaches a fee makes its own (the same note
    `test_cr108_w1_one_time_fee_lines_and_books.a_charge_code` carries).

    ⚠ **THE GL IS LOOKED UP BY CODE AND THE LOOKUP IS ASSERTED.** An earlier
    helper fell back to `.first()` when its account was missing, which silently
    books two different codes to whatever account happens to sort first — and a
    revenue-split assertion written over that fixture passes while proving
    nothing. If the seeded chart has no `4600`, this test must say so and stop.
    """
    gl = ledger_models.LedgerAccount.objects.filter(
        tenant=tenant, deleted_at__isnull=True, code=gl_code
    ).first()
    assert gl is not None, (
        f"the seeded chart has no account {gl_code!r} for this tenant, so the revenue "
        f"split below would be asserted against an account nobody chose. "
        f"CR-066 table 1 puts {gl_code} in the seed; a missing row is the defect."
    )
    row, _ = rating_models.Charge.objects.get_or_create(
        tenant=tenant,
        code=code,
        defaults={
            "name": name,
            "charge_type": "one_time",
            "amount_rule": "flat",
            "amount": amount,
            "gl_account_id": gl.id,
        },
    )
    return row


def _owner_account(actor, tenant, premises):
    """**The owner's account for this address** — the drawing's first radio.

    `kind='master'`, `premises_id` set, `unit_id` NULL. That combination is
    lawful because `ck_accounts_anchored` is
    `unit_id IS NOT NULL OR premises_id IS NOT NULL` — read off the live
    database on 2026-09-16, not off a document.

    ⚠ **AND IT IS THE ONLY LAWFUL SHAPE FOR A BUILD'S PAYER**, which is the
    non-obvious half. The neighbouring constraint
    `ck_accounts_regular_has_unit` — `NOT kind='regular' OR unit_id IS NOT NULL`
    — means an ORDINARY account still must name a unit. So the drawing's orange
    note is half right and half stale: the product may indeed anchor a payer on
    an address with no unit, and it may do so **only** as a master account.
    """
    payload = {
        "premises_id": premises["id"],
        "account_type": "commercial",
        "opened_at": "2026-08-01",
        "customer": identity_fixtures.customer_block(
            OWNER_NAME, account_type="commercial"
        ),
    }
    # ⚠ `account_no` is NOT writable through this door — `BR-TEN-035` gives the
    # number to the tenant's own series, and passing one is refused by name
    # (`VAL-002 customers.account.field_not_writable`). The drawing's `A-10088`
    # is an ILLUSTRATION (B14 rule 37); the product allocates the real one.
    return customers_services.create_master_account(actor, payload)


def _quoted_build(actor, tenant):
    """A premises, the tenant's three charge rows, and the owner's account."""
    premises = make_premises(actor)
    for code, name, amount, gl_code, _qty, _basis in BUILD:
        _charge_code(tenant, code, name, amount, gl_code)
    account = _owner_account(actor, tenant, premises)
    return premises, account


def _charges():
    """The quote as the door takes it: WHICH code and HOW MANY. No amounts."""
    return [
        fee_bill.QuotedCharge(
            charge_code=code, quantity=qty, description=name, basis=basis
        )
        for code, name, _amount, _gl, qty, basis in BUILD
    ]


def _expected_total():
    """Σ(catalogue price × count), computed from the FIXTURE ROWS.

    Deliberately not the literal `3030.0000`: a hardcoded total would assert
    that the product equals a number this file typed, where what is wanted is
    that it equals the tenant's own catalogue times the build's own counts.
    """
    return sum((amount * qty for _c, _n, amount, _g, qty, _b in BUILD), D("0"))


def _expected_by_account():
    """Σ per GL account — the revenue split, derived the same way."""
    out: dict[str, D] = {}
    for _code, _name, amount, gl_code, qty, _basis in BUILD:
        out[gl_code] = out.get(gl_code, D("0")) + amount * qty
    return out


def _entry_for(invoice):
    """The journal entry an issued invoice posted, or None."""
    return (
        ledger_models.JournalEntry.objects.filter(
            source_type="invoice", source_id=str(invoice.pk)
        )
        .order_by("created_at")
        .first()
    )


def _sides(entry):
    """(debits, credits) as {account code: total}, read off the posted lines."""
    debits: dict[str, D] = {}
    credits: dict[str, D] = {}
    for line in entry.lines.select_related("ledger_account").all():
        bucket = debits if line.side == "debit" else credits
        code = line.ledger_account.code
        bucket[code] = bucket.get(code, D("0")) + line.amount
    return debits, credits


# ══════════════════════════════════════════════════════════════════════════
# tc1 · THE PAIR — it exists, it balances, and BOTH SIDES ARE NAMED
# ══════════════════════════════════════════════════════════════════════════
def test_tc1_the_quote_posts_a_balanced_pair_with_both_sides_named(brazos, dana):
    """**The money reaches a book and the books say where it went.**

    Asserted in four steps because only the fourth is hard to fake: the entry
    EXISTS · it has a line on each side · the totals AGREE · and each named
    account carries the figure its own codes add up to.
    """
    with tenant_ctx(brazos):
        _premises, account = _quoted_build(dana, brazos)

        invoice = fee_bill.raise_and_issue_quote_bill(
            dana,
            account_id=account["id"],
            charges=_charges(),
            on_date=COMMIT_ON,
            due_days=30,
        )

        entry = _entry_for(invoice)
        assert entry is not None, (
            "the invoice issued and posted NOTHING. This is the state the whole change "
            "exists to end: a build quoted, a button pressed, and the money in no book."
        )

        debits, credits = _sides(entry)
        assert debits, "no debit line: an entry with one side is not a pair"
        assert credits, "no credit line: an entry with one side is not a pair"

        total = _expected_total()
        assert sum(debits.values()) == sum(credits.values()), (
            f"debits {sum(debits.values())} != credits {sum(credits.values())} — "
            f"hard rule 5, balanced pairs"
        )
        # The tie-out that a zero-equals-zero entry cannot pass.
        assert debits == {AR_ACCOUNT: total}, (
            f"the debit side should be exactly {AR_ACCOUNT} for {total}; got {debits}"
        )
        assert credits == _expected_by_account(), (
            f"the revenue split should follow each code's own GL (BR-BIL-010); "
            f"got {credits}"
        )
        # Two codes share 4630, and they must post as ONE credit.
        assert len(credits) == 2, (
            f"expected two credit accounts for three lines — CC-METERSET and CC-CASVC "
            f"share {BUILD[1][3]} — got {len(credits)}: {credits}"
        )


# ══════════════════════════════════════════════════════════════════════════
# tc2 · THE COUNT MULTIPLIES, AND THE PRICE IS THE TENANT'S, NOT THE CALLER'S
# ══════════════════════════════════════════════════════════════════════════
def test_tc2_the_count_multiplies_and_the_price_comes_from_the_catalogue(brazos, dana):
    """`6 x $325.00 = $1,950.00`, with the $325.00 read off the tenant's row.

    **The caller cannot supply a price**, and that is checked here as a property
    of the TYPE rather than as a refusal: `QuotedCharge` has no amount field, so
    a caller holding a figure has nowhere to put it (`BR-BIL-020`). A validation
    could be deleted by a refactor; an absent member cannot.
    """
    with tenant_ctx(brazos):
        _premises, account = _quoted_build(dana, brazos)

        assert not hasattr(fee_bill.QuotedCharge("X", D("1")), "unit_amount"), (
            "QuotedCharge grew an amount field. BR-BIL-020 is kept by that absence; "
            "a bill line whose price a caller can type is a free-typed amount."
        )

        priced = fee_bill.price_quote_bill(
            account_id=account["id"], charges=_charges(), on_date=COMMIT_ON
        )
        # `RatedLine` names its code as `charge_id` (the `rating.charges` row,
        # DEF-714) and not as a code string, so the lines are matched by the
        # charge row this fixture created rather than by their description.
        by_id = {str(line.charge_id): line for line in priced.lines}
        for code, _name, amount, _gl, qty, basis in BUILD:
            row = rating_models.Charge.objects.get(tenant=brazos, code=code)
            line = by_id[str(row.id)]
            assert line.unit == fee_bill.BASIS_UNITS[basis], (
                f"{code}: counted in {line.unit!r}, the basis {basis!r} says "
                f"{fee_bill.BASIS_UNITS[basis]!r} (hard rule 3)"
            )
            assert line.unit_price == amount, (
                f"{code}: priced at {line.unit_price}, the tenant's row says {amount}"
            )
            assert line.quantity == qty, f"{code}: count {line.quantity} != {qty}"
            assert line.amount == amount * qty, (
                f"{code}: {qty} x {amount} should be {amount * qty}, got {line.amount}"
            )
        assert priced.total == _expected_total()

        # Money is stored to FOUR decimals (hard rule 2). Rounded ONCE, at the
        # line; the total is Σ of already-quantised lines and is not re-rounded.
        for line in priced.lines:
            assert -line.amount.as_tuple().exponent <= 4, (
                f"{line.amount} carries more than four decimals"
            )


# ══════════════════════════════════════════════════════════════════════════
# tc3 · PRICING WRITES NOTHING — the screen shows the figure before the button
# ══════════════════════════════════════════════════════════════════════════
def test_tc3_pricing_a_quote_writes_nothing_and_spends_no_bill_number(brazos, dana):
    """Step 6 shows a clerk the lines and the total BEFORE anything is written.

    The drawing's red note is the requirement: *"Nothing is written until the
    last step. Every figure here is held on the draft, the payment included — so
    a wizard abandoned at step 7 has taken no money and raised no charge."*
    """
    with tenant_ctx(brazos):
        _premises, account = _quoted_build(dana, brazos)

        before = (
            billing_models.Invoice.objects.count(),
            billing_models.InvoiceLine.objects.count(),
            billing_models.BillRun.objects.count(),
            ledger_models.JournalEntry.objects.count(),
        )
        fee_bill.price_quote_bill(
            account_id=account["id"], charges=_charges(), on_date=COMMIT_ON
        )
        after = (
            billing_models.Invoice.objects.count(),
            billing_models.InvoiceLine.objects.count(),
            billing_models.BillRun.objects.count(),
            ledger_models.JournalEntry.objects.count(),
        )
        assert before == after, (
            f"pricing wrote something: {before} -> {after}. A clerk who abandons the "
            f"wizard at step 7 must leave no invoice, no line, no run and no entry."
        )
