# ── Trace ──────────────────────────────────────────────
# Change:  CR-139-BRC07 — the payments blueprint's phase 5, tasks `P5.1` (the
#          settlement ingest), `P5.2` (the fee posting), `P5.3` (idempotency on
#          a repeat payout), `P5.4`/`P5.5` (the two tables) and `P5.6`
#          (`payments.settlement_id` and the state its NULL means).
# Amended: 2026-09-24 — `OQ-PAY-12608` CLOSED, option (b): the PO DROPPED
#          `payments.settlement_id` (`payments/0044`) rather than widening hard
#          rule 4's allow list. Two `P5.6` cases and one `P5.2` case are
#          rewritten; `settlement_members` is the one record.
# Rules:   CLAUDE.md hard rule 1 · rule 2 (four decimals on a NEW money column)
#          · rule 4 (`OQ-PAY-12608` — the pointer could not be stamped, so it
#          is gone; the payment-row lock is untouched) · rule 5
#          (nothing in `settlements.py` writes a journal line) · rule 6 (two
#          independent guards, asserted separately — DEF-058) · rule 7 ·
#          hard-won law 7 (every case below was proved RED first, and the
#          *what would make this pass wrongly* question is answered in each
#          docstring) · hard-won law 14 (the SAVEPOINT, proved on PostgreSQL)
# Tests:   this file. The RLS half is `test_cr139_p5_rls_pg.py`; the
#          immutability-trigger proof is
#          `10-scripts/cr139_p5_6_pointer_freeze_proof.py`.
# ───────────────────────────────────────────────────────
"""Phase 5's money half, checked where each check can actually run.

WHAT IS NOT HERE, AND WHY — READ THIS BEFORE ADDING TO IT
-----------------------------------------------------------
`config/settings/test.py` hardcodes in-memory SQLite and ignores
`DATABASE_URL`, so **two of this phase's guarantees cannot be asserted here at
all** and saying so is the point (hard-won law 7's *reporting zero over a scope
it silently excludes*):

  * **The SAVEPOINT.** SQLite has no aborted-transaction state, so the version
    with a bare `try/except` passes every case below. The one case that can
    tell the difference is marked `requires_postgres` and **skips loudly**.
  * **The immutability trigger.** `payments/0005`'s trigger is installed by a
    `RunPython` that returns early on any non-PostgreSQL vendor. So a version
    of `ingest_payout` that stamped `payments.settlement_id` would have gone
    GREEN on every machine and failed the first real payout. That was measured
    on PostgreSQL 16.13 in 2026-09-23 and is what produced `OQ-PAY-12608`;
    **the PO dropped the column on 2026-09-24**, so the trap is now closed by
    the schema rather than watched for, and the standing guard
    (`…_the_pointer_column_is_gone_and_stays_gone`) runs on SQLite like
    everything else — a column's ABSENCE needs no trigger to observe, which is
    exactly why the original finding needed one and this does not.

Run the PostgreSQL half like this (the whole line — a header that omits
`JOBS_EAGER=false` costs an hour, `DEF-567`):

    export DJANGO_SETTINGS_MODULE=config.settings.local JOBS_EAGER=false \\
      DATABASE_URL="postgres://smartbillhub:smartbillhub@127.0.0.1:5432/sbh_p5proof?sslmode=disable"
    pytest tests/test_cr139_p5_settlements.py
"""

from __future__ import annotations

import ast
import uuid
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pytest
from django.db import IntegrityError, transaction

from apps.payments import models as payment_models
from apps.payments import settlement_models, settlements
from apps.payments.exceptions import PaymentRuleError

from tests.isolation_helpers import requires_postgres
from tests.test_us_met_helpers import *  # noqa: F401,F403 — brazos · dana · marcus
from tests.test_us_met_helpers import tenant_ctx

#: ⚠ **NOT A MODULE-LEVEL `django_db` MARK, AND THE REASON IS THE TWO
#: STRUCTURAL CASES AT THE FOOT OF THIS FILE.** They read the source tree and
#: touch no row, and a mark up here would make them pay eighteen minutes of
#: test-database build to answer a question about a file on disk. Every case
#: that needs the database carries its own mark.
pytestmark: list = []

BACKEND = Path(__file__).resolve().parents[1]


# ═══════════════════════════════════════════════════════════════════════════
#  READING THE SOURCE PROPERLY — why these two helpers exist
# ═══════════════════════════════════════════════════════════════════════════
# ⚠ **THE FIRST DRAFT OF THE TWO STRUCTURAL CASES BELOW GREPPED THE FILE AND
# BOTH WENT RED ON THEIR OWN SUBJECT'S PROSE.** `settlements.py` EXPLAINS that
# it must not import `ledger_seam` and EXPLAINS that `G77` fails a
# `provider_key ==` comparison, so a substring search finds both phrases in the
# docstrings that forbid them. The naive fix — strip the module docstring — is
# what the draft did, and it is still wrong: FUNCTION docstrings and refusal
# strings come after it.
#
# **So these read the file as PYTHON.** An import is an import node; a
# comparison is a comparison node; a vendor name is checked only in string
# LITERALS, never in comments or docstrings. That is the difference between a
# check that asks the question and a check that asks about the wording.
#
# ⚠ **AND IT MAKES THE CHECK STRICTER, NOT LOOSER:** `from apps.payments import
# ledger_seam` inside a function body — the obvious way a later lane would slip
# a posting in — is invisible to a grep for `import ledger_seam` at the top of
# the file and is caught here.
def _parsed(filename: str) -> ast.Module:
    """One file of `apps/payments/`, as a syntax tree."""
    return ast.parse((BACKEND / "apps" / "payments" / filename).read_text())


def _modules_imported_by(filename: str) -> set[str]:
    """Every module name this file imports — **including inside functions.**"""
    found: set[str] = set()
    for node in ast.walk(_parsed(filename)):
        if isinstance(node, ast.Import):
            found.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            base = node.module or ""
            found.add(base)
            found.update(f"{base}.{alias.name}" for alias in node.names)
    return found


def _string_constants(tree: ast.Module, *, literals_only: bool) -> list[str]:
    """Every string constant, with docstrings left out when asked.

    `literals_only` drops the docstring of the module and of every function and
    class, which is the only reason a vendor name could lawfully appear here —
    a docstring naming Worldpay as an example is prose, and a literal naming it
    is a coupling.
    """
    docstrings = set()
    if literals_only:
        for node in ast.walk(tree):
            if isinstance(node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                first = node.body[0] if node.body else None
                if (
                    isinstance(first, ast.Expr)
                    and isinstance(first.value, ast.Constant)
                    and isinstance(first.value.value, str)
                ):
                    docstrings.add(id(first.value))
    return [
        node.value
        for node in ast.walk(tree)
        if isinstance(node, ast.Constant)
        and isinstance(node.value, str)
        and id(node) not in docstrings
    ]


PAID_OUT_AT = datetime(2026, 8, 6, 3, 0, tzinfo=UTC)
POSTED_AT = datetime(2026, 8, 5, 14, 30, tzinfo=UTC)

#: A `provider_key`, never a vendor. `G77` fails the merge on a comparison of
#: one outside `adapters/` and `manifests/`; this is test DATA, which is the
#: distinction that keeps `BR-INT-037` meaningful.
PROVIDER = "payments_sandbox"


def _account(actor, tenant):
    """One account for a payment to hang off. Deliberately minimal.

    These cases are about the SETTLEMENT service. Routing them through
    `services.record_payment` would re-assert US-PAY-006's allocation on every
    one of them and make a failure here ambiguous between two modules.
    """
    from apps.customers import models as customer_models

    from tests.test_us_met_helpers import make_premises, make_unit

    premises = make_premises(
        actor, address_line="1901 Bluestem Ln", services_available=["electric"]
    )
    unit = make_unit(actor, premises["id"], label="Unit A", services=["electric"])
    return customer_models.Account.objects.create(
        tenant=tenant,
        unit_id=unit["id"],
        status=customer_models.AccountStatus.objects.filter(tenant=tenant).first(),
        account_type=customer_models.AccountType.objects.first(),
        account_no=f"A-{uuid.uuid4().hex[:8]}",
    )


def _card_payment(tenant, account, *, amount, reference):
    """A cleared card payment carrying the webhook key a payout will name.

    `webhook|<provider>:<event_id>` is composed by
    `idempotency.inbound_payment_key` on the ONE inbound path, and the payout's
    member references are those same `event_id`s. Matching on this rather than
    on `confirmation` is what `settlements._payment_for` documents: a clerk may
    correct `confirmation` through `POST /payments/{id}/correct-reference`, and
    a join a correction can break is a join that stops matching one day.
    """
    return payment_models.Payment.objects.create(
        tenant=tenant,
        account=account,
        amount=amount,
        currency="USD",
        status=payment_models.PAYMENT_CLEARED,
        posted_at=POSTED_AT,
        cleared_at=POSTED_AT,
        webhook_key=f"webhook|{PROVIDER}:{reference}",
    )


def _payout(**overrides):
    """The blueprint's worked payout, shrunk to three members for readability.

    `$100.00 + $60.00 + $40.00 = $200.00` gross, `$2.90 + $1.74 + $1.16 =
    $5.80` in fees, `$194.20` net. Every figure here is exact in four decimals,
    which is the point of hard rule 2 being a `Decimal`.
    """
    kwargs = dict(
        provider=PROVIDER,
        code="po_20260806_0001",
        paid_out_at=PAID_OUT_AT,
        gross=Decimal("200.0000"),
        fees=Decimal("5.8000"),
        net=Decimal("194.2000"),
        currency="USD",
        members=(
            settlements.PayoutMember("ch_A", Decimal("100.0000"), Decimal("2.9000")),
            settlements.PayoutMember("ch_B", Decimal("60.0000"), Decimal("1.7400")),
            settlements.PayoutMember("ch_C", Decimal("40.0000"), Decimal("1.1600")),
        ),
    )
    kwargs.update(overrides)
    return kwargs


@pytest.fixture()
def three_card_payments(brazos, dana):
    """`ch_A` $100.00 · `ch_B` $60.00 · `ch_C` $40.00, all cleared."""
    with tenant_ctx(brazos):
        rows = {}
        for ref, amount in (("ch_A", "100.0000"), ("ch_B", "60.0000"), ("ch_C", "40.0000")):
            rows[ref] = _card_payment(
                brazos, _account(dana, brazos), amount=Decimal(amount), reference=ref
            )
        return rows


# ═══════════════════════════════════════════════════════════════════════════
#  P5.1 — a payout arrives, its members are written
# ═══════════════════════════════════════════════════════════════════════════
@pytest.mark.django_db
def test_cr139_p5_1_a_payout_writes_its_members(brazos, dana, three_card_payments):
    """*"Being paid out is a second message, and it is handled."*

    The phase's own acceptance sentence, at three members instead of
    forty-six: **a supervisor opens last night's payout and sees the payments
    inside it.**

    ⚠ **WHAT WOULD MAKE THIS PASS WRONGLY** (law 7 habit 2): a version that
    wrote the settlement row and no members would still answer `created=True`
    with the right totals. So the member COUNT and the member's own gross are
    both asserted, and the gross is asserted against the PAYMENT's amount
    rather than against the payout's — which is the one figure a netting bug
    would move.
    """
    with tenant_ctx(brazos):
        result = settlements.ingest_payout(actor=dana, **_payout())

        assert result.created is True
        assert result.member_count == 3
        assert result.unresolved == ()
        assert result.status == settlement_models.SETTLEMENT_RECEIVED

        row = settlement_models.Settlement.objects.get(pk=result.settlement_id)
        assert row.members.count() == 3
        member = row.members.get(payment=three_card_payments["ch_A"])
        assert member.gross == three_card_payments["ch_A"].amount == Decimal("100.0000"), (
            "a member's gross is what the CUSTOMER paid. A $100.00 card payment with a "
            "$2.90 fee is a $100.00 payment and a $2.90 expense — never a $97.10 payment."
        )
        assert member.fee == Decimal("2.9000")


@pytest.mark.django_db
def test_cr139_p5_1_a_member_we_hold_no_payment_for_is_recorded_not_raised(
    brazos, dana, three_card_payments
):
    """A payout can carry a charge this product never saw. It still lands.

    A charge taken before the utility went live, or one whose settlement
    callback never arrived, must not cost the supervisor the record of a bank
    credit that is really in their account.

    ⚠ **WHAT WOULD MAKE THIS PASS WRONGLY:** a version that silently dropped
    the unknown member would also produce a settlement with three members. So
    the `unresolved` row and its CODE are asserted, not merely the survivors —
    *no silent exclusion* is the one thing a money trail may not contain.
    """
    payout = _payout(
        gross=Decimal("225.0000"),
        fees=Decimal("6.5250"),
        net=Decimal("218.4750"),
        members=(
            settlements.PayoutMember("ch_A", Decimal("100.0000"), Decimal("2.9000")),
            settlements.PayoutMember("ch_B", Decimal("60.0000"), Decimal("1.7400")),
            settlements.PayoutMember("ch_C", Decimal("40.0000"), Decimal("1.1600")),
            settlements.PayoutMember("ch_GHOST", Decimal("25.0000"), Decimal("0.7250")),
        ),
    )
    with tenant_ctx(brazos):
        result = settlements.ingest_payout(actor=dana, **payout)

        assert result.created is True
        assert result.member_count == 3
        assert len(result.unresolved) == 1
        assert result.unresolved[0]["reference"] == "ch_GHOST"
        assert result.unresolved[0]["code"] == settlements.MEMBER_PAYMENT_NOT_FOUND


@pytest.mark.django_db
def test_cr139_p5_1_a_member_whose_gross_disagrees_is_refused_by_name(brazos, dana):
    """The payout says $97.10 and the payment says $100.00 — **no member.**

    ⚠ **THIS IS THE CASE THE WHOLE PHASE EXISTS FOR.** The natural wrong build
    reads the provider's NET per charge and records it as the member's gross,
    and it looks completely reasonable: the numbers foot, the payout ties, and
    the customer is quietly $2.90 short of what they actually paid.

    ⚠ **WHAT WOULD MAKE THIS PASS WRONGLY:** a version that wrote the member
    with the payout's figure and reported no problem. So the assertion is that
    **no member row exists**, not merely that a problem was reported.
    """
    with tenant_ctx(brazos):
        _card_payment(brazos, _account(dana, brazos), amount=Decimal("100.0000"), reference="ch_A")
        payout = _payout(
            gross=Decimal("97.1000"),
            fees=Decimal("0.0000"),
            net=Decimal("97.1000"),
            members=(settlements.PayoutMember("ch_A", Decimal("97.1000"), Decimal("0.0000")),),
        )
        result = settlements.ingest_payout(actor=dana, **payout)

        assert result.member_count == 0
        assert result.unresolved[0]["code"] == settlements.MEMBER_GROSS_DISAGREES
        assert settlement_models.SettlementMember.objects.count() == 0, (
            "a member's gross is the CUSTOMER'S payment. Writing the provider's netted "
            "figure is the one error phase 5 exists to prevent."
        )


@requires_postgres
@pytest.mark.django_db
def test_cr139_p5_1_one_bad_member_keeps_the_rest(brazos, dana, three_card_payments):
    """**Hard-won law 14, and the blueprint names it as this phase's risk.**

    A payment already inside another payout raises `IntegrityError` from
    `uq_settlement_members_payment`. **On PostgreSQL that aborts the enclosing
    transaction unless the write is inside a SAVEPOINT** — so a bare
    `try/except IntegrityError: continue` loses the settlement row and every
    member already written, at COMMIT, with no exception a caller can see.

    ⚠ **THIS CASE IS `requires_postgres` AND THE SKIP IS THE POINT.** SQLite
    has no aborted-transaction state: the broken version passes there, on every
    machine, green. That is law 14 word for word, and it is why this is the one
    case in the file that cannot run in the default suite.
    """
    with tenant_ctx(brazos):
        first = settlements.ingest_payout(actor=dana, **_payout())
        assert first.member_count == 3

        # `ch_B` is already paid out; the other two are new.
        newer = _account(dana, brazos)
        _card_payment(brazos, newer, amount=Decimal("15.0000"), reference="ch_D")
        payout = _payout(
            code="po_20260807_0002",
            gross=Decimal("75.0000"),
            fees=Decimal("2.1750"),
            net=Decimal("72.8250"),
            members=(
                settlements.PayoutMember("ch_B", Decimal("60.0000"), Decimal("1.7400")),
                settlements.PayoutMember("ch_D", Decimal("15.0000"), Decimal("0.4350")),
            ),
        )
        result = settlements.ingest_payout(actor=dana, **payout)

        assert result.created is True, (
            "the SECOND payout must still exist. Without the SAVEPOINT, PostgreSQL has "
            "aborted this transaction by now and nothing at all was written."
        )
        assert result.member_count == 1
        assert result.unresolved[0]["code"] == settlements.MEMBER_ALREADY_PAID_OUT
        assert (
            settlement_models.Settlement.objects.get(pk=result.settlement_id).members.count() == 1
        )


# ═══════════════════════════════════════════════════════════════════════════
#  P5.3 — a redelivery writes nothing twice (hard rule 6)
# ═══════════════════════════════════════════════════════════════════════════
@pytest.mark.django_db
def test_cr139_p5_3_guard_one_recognises_a_redelivery(brazos, dana, three_card_payments):
    """The same payout, twice. ONE settlement, THREE members, `created=False`.

    Guard 1 is the pre-write SELECT on `(tenant, provider, code)`.

    ⚠ **A REDELIVERY IS NOT AN ERROR.** A provider re-sending is a provider
    behaving correctly, and answering with a red failure teaches an operator to
    retry until something breaks. `created=False` is the whole signal.
    """
    with tenant_ctx(brazos):
        first = settlements.ingest_payout(actor=dana, **_payout())
        second = settlements.ingest_payout(actor=dana, **_payout())

        assert first.created is True and second.created is False
        assert second.settlement_id == first.settlement_id
        assert settlement_models.Settlement.objects.count() == 1
        assert settlement_models.SettlementMember.objects.count() == 3


@pytest.mark.django_db
def test_cr139_p5_3_guard_two_holds_the_line_on_its_own(brazos, dana, three_card_payments):
    """`uq_settlements_provider_code` — asserted **independently of guard 1.**

    `DEF-058`'s lesson, which `webhooks.py` already keeps: *neither guard is
    trusted because the other exists.* This case bypasses the service entirely
    and writes the duplicate straight at the table, which is the only way to
    find out whether the index would catch the race guard 1's SELECT cannot
    close.

    ⚠ **WHAT WOULD MAKE THIS PASS WRONGLY:** nothing — a missing unique index
    lets the second row in and the `pytest.raises` fails. That is the property
    that makes this case worth its lines.
    """
    with tenant_ctx(brazos):
        settlements.ingest_payout(actor=dana, **_payout())
        with pytest.raises(IntegrityError), transaction.atomic():
            settlement_models.Settlement.objects.create(
                tenant=brazos,
                provider=PROVIDER,
                code="po_20260806_0001",
                paid_out_at=PAID_OUT_AT,
                gross=Decimal("200.0000"),
                fees=Decimal("5.8000"),
                net=Decimal("194.2000"),
            )


# ═══════════════════════════════════════════════════════════════════════════
#  P5.4 / P5.5 — the schema, and the figures it refuses
# ═══════════════════════════════════════════════════════════════════════════
@pytest.mark.parametrize(
    "model, fields",
    [
        (settlement_models.Settlement, ("gross", "fees", "net")),
        (settlement_models.SettlementMember, ("gross", "fee")),
    ],
)
def test_cr139_p5_4_every_new_money_column_declares_four_decimals(model, fields):
    """**Hard rule 2 over the drawing.** `P5.4` says `NUMERIC(18,6)`; four wins.

    PO re-sign 2026-08-22, verbatim: *"We already confirmed this - MOney 4
    decimal, percentage 6 decimal , display both 2 decimal"* — and that
    supersedes hard rule 2's own original `NUMERIC(18,6)`. Existing 18,6
    columns stay lawful containers; a NEW column declares four.

    B14 rule 37 one level down: **a figure drawn in a wireframe is an
    illustration, never a fact to build to** — and a signed rule is not an
    illustration. `payments/0031` took the same reading on 2026-09-22, so this
    is the second time.
    """
    for name in fields:
        field = model._meta.get_field(name)
        assert field.decimal_places == 4, (
            f"{model.__name__}.{name} declares {field.decimal_places} decimals. The "
            "blueprint draws NUMERIC(18,6) and CLAUDE.md hard rule 2 (PO re-sign "
            "2026-08-22) says a NEW money column declares FOUR. The signed rule wins."
        )
        assert field.max_digits == 18


def test_cr139_p5_4_currency_is_char_three():
    """`CHAR(3)`, per hard rule 2 and per the drawing — they agree here."""
    assert settlement_models.Settlement._meta.get_field("currency").max_length == 3


@pytest.mark.django_db
def test_cr139_p5_4_a_payout_that_does_not_tie_is_refused_not_recomputed(brazos, dana):
    """gross − fees ≠ net ⇒ **refused**, and `net` is never worked out for them.

    ⚠ **WHAT WOULD MAKE THIS CHECK USELESS**, which is the reason its docstring
    is longer than its body: computing `net = gross - fees` ourselves. The
    check then cannot fail — `OQ-160`'s recorded hazard exactly, one level up.
    *A figure derived to close a gap can never disagree with anything.*
    """
    with tenant_ctx(brazos):
        with pytest.raises(PaymentRuleError, match="does not tie"):
            settlements.ingest_payout(actor=dana, **_payout(net=Decimal("190.0000")))


@pytest.mark.django_db
def test_cr139_p5_4_members_must_foot_to_the_payout(brazos, dana, three_card_payments):
    """Σ member fees ≠ stated fees ⇒ refused. **This is what makes `P5.2` work.**

    If the two halves may disagree, the stated total is just another guess and
    `stated_processor_fee` is no better than deriving the fee from the gap.
    """
    with tenant_ctx(brazos):
        broken = _payout(
            members=(
                settlements.PayoutMember("ch_A", Decimal("100.0000"), Decimal("2.9000")),
                settlements.PayoutMember("ch_B", Decimal("60.0000"), Decimal("1.7400")),
                settlements.PayoutMember("ch_C", Decimal("40.0000"), Decimal("0.5000")),
            )
        )
        with pytest.raises(PaymentRuleError, match="per-payment fees sum"):
            settlements.ingest_payout(actor=dana, **broken)


@pytest.mark.django_db
def test_cr139_p5_4_a_float_is_refused_and_not_converted(brazos, dana):
    """Hard rule 2: money is a `Decimal` or it is refused.

    A `float` from a provider's JSON is already wrong before it arrives —
    `0.1 + 0.2` is not `0.3` in binary — and a payout is a sum of hundreds of
    amounts. Converting it would launder the error into something that looks
    like money.
    """
    with tenant_ctx(brazos):
        with pytest.raises(PaymentRuleError, match="not a Decimal"):
            settlements.ingest_payout(actor=dana, **_payout(gross=200.0))


def test_cr139_p5_5_a_payment_belongs_to_at_most_one_payout():
    """`uq_settlement_members_payment` — the rule as a constraint, not a habit.

    Asserted on the DECLARATION rather than on a stored row: a test that
    happens to write two payouts proves the service is careful, and this needs
    to prove the DATABASE is.
    """
    names = {c.name for c in settlement_models.SettlementMember._meta.constraints}
    assert "uq_settlement_members_payment" in names
    constraint = next(
        c
        for c in settlement_models.SettlementMember._meta.constraints
        if c.name == "uq_settlement_members_payment"
    )
    assert tuple(constraint.fields) == ("tenant", "payment")


@pytest.mark.django_db
def test_cr139_p5_5_status_and_the_bank_line_cannot_disagree(brazos):
    """`matched` with no bank line is not writable. Two values, ONE fact.

    A status column and a nullable pointer answering the same question is the
    *two places that can disagree* shape this module keeps filing, so it is a
    CHECK rather than a service rule.

    ⚠ SQLite enforces CHECK constraints, so this one case genuinely runs in the
    default suite — unlike the trigger, which does not.
    """
    with tenant_ctx(brazos):
        with pytest.raises(IntegrityError), transaction.atomic():
            settlement_models.Settlement.objects.create(
                tenant=brazos,
                provider=PROVIDER,
                code="po_bad_state",
                paid_out_at=PAID_OUT_AT,
                gross=Decimal("10.0000"),
                fees=Decimal("0.0000"),
                net=Decimal("10.0000"),
                status=settlement_models.SETTLEMENT_MATCHED,
            )


# ═══════════════════════════════════════════════════════════════════════════
#  P5.2 — the fee stops being a guess
# ═══════════════════════════════════════════════════════════════════════════
def test_cr139_p5_2_nothing_in_this_module_writes_a_journal_line():
    """**Hard rule 5, asserted as an ABSENCE over the source.**

    *"Only the ledger posting service writes journal lines."* This file keeps
    it by having nothing to keep it about: the balanced pair for a card day is
    already written by `reconciliation.reconcile_batch`, and a second posting
    path would post the same money twice.

    ⚠ **THIS IS A STRUCTURAL ASSERTION BECAUSE A BEHAVIOURAL ONE CANNOT SEE
    IT.** A future lane adding `ledger_seam.post_*` here would break no case in
    this file — the payout would still ingest, the members would still be
    written, the totals would still tie. It would simply post the money a
    second time, and the trial balance is where that shows up.
    """
    reached = _modules_imported_by("settlements.py")
    offenders = sorted(one for one in reached if "ledger" in one)
    assert not offenders, (
        f"apps/payments/settlements.py imports {offenders}. It must not reach the ledger: "
        "the balanced pair for a card day already exists in reconciliation.reconcile_batch "
        "under the PO's rulings of 2026-08-11 (OQ-144) and 2026-08-12 (OQ-160), and a "
        "second posting path posts the same money twice — the blueprint's own 'two answers "
        "to one question' risk, on the money path."
    )


@pytest.mark.django_db
def test_cr139_p5_2_a_stated_fee_that_explains_the_gap_becomes_a_resolution(brazos, dana):
    """The happy half: provider kept $5.80, bank is $5.80 short. **Ties.**

    The result is a `reconciliation.ResolutionInput` — the identical type a
    human's explanation and `derive_processor_fee`'s guess both produce — so it
    reaches the books through `reconcile_batch` and `post_batch_reconciled`
    exactly as they do. **Nothing is posted here.**
    """
    from apps.payments import reconciliation

    with tenant_ctx(brazos):
        settlement = settlement_models.Settlement.objects.create(
            tenant=brazos,
            provider=PROVIDER,
            code="po_tie",
            paid_out_at=PAID_OUT_AT,
            gross=Decimal("200.0000"),
            fees=Decimal("5.8000"),
            net=Decimal("194.2000"),
        )
        resolution = settlements.stated_processor_fee(
            settlement,
            recorded_total=Decimal("200.0000"),
            bank_total=Decimal("194.2000"),
            gl_account_id=uuid.uuid4(),
        )
        assert isinstance(resolution, reconciliation.ResolutionInput)
        assert resolution.amount == Decimal("-5.80")
        assert resolution.reason_code == settlements.REASON_PROCESSOR_FEE
        assert "OQ-160" in (resolution.note or "")


@pytest.mark.django_db
def test_cr139_p5_2_a_chargeback_hiding_inside_the_gap_is_refused(brazos, dana):
    """**The case the phase's money half exists for, on the PO's own figures.**

        recorded 5,120.40 · bank 4,972.90 · difference −147.50
        provider states it kept                        137.50
        unexplained                                     10.00   ← A CUSTOMER

    `derive_processor_fee` answers *fee 147.50*, the batch reconciles clean,
    and the **$10.00 chargeback is invisible forever** — the customer's bill
    stays paid and nothing ever re-opens it. That is `OQ-160`'s recorded
    hazard, accepted by the PO **because the product had no settlement file**.
    Phase 5 is that file, so this refuses and names the remainder.

    ⚠ **WHAT WOULD MAKE THIS PASS WRONGLY:** returning two lines — *fee
    137.50* + *unexplained 10.00* — which would make the batch tie out and
    would be a plug with a nicer name. `BR-PAY-019` and `BR-PAY-035` both
    forbid it; the remainder is a question for a person.
    """
    with tenant_ctx(brazos):
        settlement = settlement_models.Settlement.objects.create(
            tenant=brazos,
            provider=PROVIDER,
            code="po_chargeback",
            paid_out_at=PAID_OUT_AT,
            gross=Decimal("5120.4000"),
            fees=Decimal("137.5000"),
            net=Decimal("4982.9000"),
        )
        with pytest.raises(PaymentRuleError, match=r"10\.00 is unexplained"):
            settlements.stated_processor_fee(
                settlement,
                recorded_total=Decimal("5120.4000"),
                bank_total=Decimal("4972.9000"),
                gl_account_id=uuid.uuid4(),
            )


@pytest.mark.django_db
def test_cr139_p5_2_an_overage_is_never_called_a_fee(brazos):
    """The bank credited MORE than we recorded. That is not a fee, in any build.

    The same refusal `derive_processor_fee` makes, kept here deliberately
    rather than inherited: calling an overage a fee would post a NEGATIVE
    expense over the top of a real question about where extra money came from.
    """
    with tenant_ctx(brazos):
        settlement = settlement_models.Settlement.objects.create(
            tenant=brazos,
            provider=PROVIDER,
            code="po_over",
            paid_out_at=PAID_OUT_AT,
            gross=Decimal("200.0000"),
            fees=Decimal("0.0000"),
            net=Decimal("200.0000"),
        )
        with pytest.raises(PaymentRuleError, match="cannot be one"):
            settlements.stated_processor_fee(
                settlement,
                recorded_total=Decimal("200.0000"),
                bank_total=Decimal("205.0000"),
                gl_account_id=uuid.uuid4(),
            )


# ═══════════════════════════════════════════════════════════════════════════
#  P5.6 — the third state, and the pointer the PO ruled away
# ═══════════════════════════════════════════════════════════════════════════
def test_cr139_p5_6_the_pointer_column_is_gone_and_stays_gone():
    """**`payments.settlement_id` IS DROPPED — `OQ-PAY-12608`, PO ruling
    2026-09-24 option (b), verbatim: *"p7 (b) — nothing is lost, and the
    payment-row lock stays exactly as it is"*.**

    ⛔ **THIS CASE WAS `…_the_pointer_is_nullable_and_a_plain_uuid` AND
    ASSERTED THE COLUMN'S SHAPE.** `P5.6` of the payments blueprint (p024)
    drew *"`payments.settlement_id` — nullable. Null is Awaiting
    settlement."*, and the column was built. **Nothing could ever write it:**
    `payments/0005`'s trigger compares a frozen payment's whole row minus a
    short allow list and its own comment says *"a column added later is frozen
    the day it is created"*, so the pointer was frozen from the moment the row
    existed, in every status — measured on PostgreSQL 16.13 before anything
    was written. Hard rule 4 narrows itself in terms (*"widening it anywhere
    else is a new ruling"*), so it went to the PO, who chose to drop the
    column rather than widen the lock.

    **So this is now the standing guard that it stays dropped**, and it runs
    on SQLite like every other case — the drop is a schema fact, not a trigger
    fact, so unlike the freeze it does not need PostgreSQL to be seen. What
    DOES need PostgreSQL is the migration itself, and `payments/0044` was run
    forward and back on a real server before this landed.

    `settlement_members` is the one record of which payments a payout holds,
    and `settlements.awaiting_settlement_filter()` answers *Awaiting
    settlement* from it — which it already did, because the pointer was never
    readable either.
    """
    names = {field.name for field in payment_models.Payment._meta.get_fields()}
    assert "settlement_id" not in names, (
        "payments.settlement_id is back. OQ-PAY-12608 ruled it away on 2026-09-24 because "
        "hard rule 4's immutability trigger freezes it in every status; re-adding it "
        "re-creates a column nothing can write. settlement_members is the record."
    )
    assert "settlement" not in names


@pytest.mark.django_db
def test_cr139_p5_6_nothing_stamps_the_pointer_and_the_absence_is_declared(
    brazos, dana, three_card_payments
):
    """**Hard rule 4 won over the drawing, and the PO then removed the
    column — `OQ-PAY-12608`, ruled (b) on 2026-09-24.**

    `payments/0005`'s trigger compares a frozen payment's WHOLE ROW minus
    `(deposit_batch_id, updated_at)` and its own comment says *"a column added
    later is frozen the day it is created"*, so `settlement_id` was frozen
    from the moment the row existed — in every status, not merely after
    clearing. Hard rule 4 says widening that allow list is a new PO ruling;
    the PO was shown the choice and dropped the column instead. **The
    payment-row lock did not move, which is half of what they ruled.**

    ⛔ **SUPERSEDED — what this case used to assert.** It read back
    `payments.settlement_id is None` after a payout. There is no such
    attribute now, so that line would raise rather than fail, which is why it
    is REPLACED rather than deleted: the case that guards the column's absence
    is `test_cr139_p5_6_the_pointer_column_is_gone_and_stays_gone` above, and
    this one keeps the half that still means something — **the absence is
    DECLARED on every result** (the `WEBHOOK_UNAVAILABLE` posture), so a
    caller never has to infer that no payment row names its payout.

    The code is UNCHANGED (`no_payment_row_is_stamped_with_its_payout`): it is
    still exactly true and is what a caller groups on. Only its reason moved,
    from *a column exists that nothing can write* to *the PO ruled it away and
    `settlement_members` is the one record*.
    """
    with tenant_ctx(brazos):
        result = settlements.ingest_payout(actor=dana, **_payout())
        codes = {one["code"] for one in result.problems}
        assert "no_payment_row_is_stamped_with_its_payout" in codes, (
            "the absence is DECLARED on every result (the WEBHOOK_UNAVAILABLE posture). A "
            "caller must not have to infer it and a reviewer must not have to take a "
            "docstring's word for it."
        )
        detail = next(
            one["detail"] for one in result.problems
            if one["code"] == "no_payment_row_is_stamped_with_its_payout"
        )
        assert "exists and NOTHING writes it" not in detail, (
            "the declared absence still describes a column that was dropped on 2026-09-24. "
            "A stated absence whose stated reason has stopped being true is DEF-PAY-6330's "
            "shape, and it passes every parity check."
        )


@pytest.mark.django_db
def test_cr139_p5_6_the_third_state_is_answered_from_the_membership(
    brazos, dana, three_card_payments
):
    """*Awaiting settlement* is read from `settlement_members`, not the pointer.

    ⚠ **WHY THIS MATTERS RATHER THAN BEING A DETAIL:** a filter on
    `settlement_id__isnull=True` would answer *"all of them"* truthfully and
    uselessly for as long as `OQ-PAY-12608` is open — hard-won law 7's
    *incapable of failing* shape wearing a list filter.
    """
    with tenant_ctx(brazos):
        before = payment_models.Payment.objects.filter(
            settlements.awaiting_settlement_filter()
        ).count()
        assert before == 3

        settlements.ingest_payout(actor=dana, **_payout())

        after = payment_models.Payment.objects.filter(
            settlements.awaiting_settlement_filter()
        ).count()
        assert after == 0, (
            "every payment in the payout has stopped reading 'Awaiting settlement' — which "
            "is P5.12's outcome, answered from the record rather than from a column nothing "
            "can write."
        )


@pytest.mark.django_db
def test_cr139_p5_2_the_membership_is_the_only_place_the_payout_is_held(
    brazos, dana, three_card_payments
):
    """**ONE place holds this fact now, so there is nothing to disagree with.**

    ⛔ **THIS CASE WAS `…_pointer_and_member_agree` AND COMPARED TWO PLACES.**
    It said the check *"will matter on the day `OQ-PAY-12608` closes"*. The
    question closed on 2026-09-24 the other way — the PO dropped
    `payments.settlement_id` rather than making it writable — so the check
    that was being kept warm can never be needed, and a case comparing a
    column that does not exist would raise rather than fail.

    What replaces it is the guarantee that survived the ruling and is the
    whole reason the drop costs nothing: **every member names its payout, and
    a payment reaches its payout only through the membership.** That is what
    `awaiting_settlement_filter()` reads, and it is why *"nothing is lost"* is
    a fact rather than a reassurance.
    """
    with tenant_ctx(brazos):
        result = settlements.ingest_payout(actor=dana, **_payout())
        members = list(settlement_models.SettlementMember.objects.all())
        assert members, "a payout with no membership rows holds no record of anything"
        for member in members:
            assert str(member.settlement_id) == result.settlement_id, (
                "settlement_members is the ONE record of which payout a payment is in "
                "(OQ-PAY-12608, 2026-09-24). A member that names a different payout means "
                "the one remaining source of that fact is wrong."
            )
        assert len({str(member.payment_id) for member in members}) == len(members), (
            "uq_settlement_members_payment says a payment is in at most one payout; two "
            "member rows for one payment would put the third state back in doubt."
        )


# ═══════════════════════════════════════════════════════════════════════════
#  BR-INT-037 / G77 — no vendor is named in this module
# ═══════════════════════════════════════════════════════════════════════════
def test_cr139_p5_9_no_provider_is_named_in_apps_payments():
    """*"Adding a provider stays one manifest and one adapter."*

    PO ruling 2026-09-05, verbatim: *"we will have multiple payment providers
    integrated using integration module. For given utility we will activate 1
    or 2."* So `provider` is a `provider_key` string that travels through this
    module and is never compared to a literal in it.

    ⚠ **WHAT WOULD MAKE THIS PASS WRONGLY:** checking only for vendor NAMES.
    A comparison against a key constant is the same coupling wearing a variable,
    which is why `G77` looks for `provider_key ==` rather than for brands — and
    why this asserts the absence of BOTH.
    """
    tree = _parsed("settlements.py")
    for node in ast.walk(tree):
        if isinstance(node, ast.Compare):
            for side in [node.left, *node.comparators]:
                name = getattr(side, "attr", None) or getattr(side, "id", None)
                assert name != "provider_key", (
                    "apps/payments/settlements.py compares `provider_key` at line "
                    f"{node.lineno}. `G77` fails the merge on exactly that, and BR-INT-037 "
                    "is the reason: 'every time such integration comes we dont want to "
                    "change our integration framework'."
                )
    for text in _string_constants(tree, literals_only=True):
        low = text.lower()
        for vendor in ("stripe", "worldpay", "paymentus", "braintree"):
            assert vendor not in low, (
                f"{vendor!r} appears in a string LITERAL in apps/payments/settlements.py. "
                "A provider is one manifest and one adapter (BR-INT-037)."
            )
