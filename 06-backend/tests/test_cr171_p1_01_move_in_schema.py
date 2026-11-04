# ── Trace ──────────────────────────────────────────────
# Change:   CR-171-BRC10 `P1.01` (lane MVI-SCHEMA) — the ONE customers migration
#           for every new fact the move-in redesign needs.
# Rules:    CLAUDE.md hard rule 1 (tenant scoping) · hard rule 2 (money 4 places,
#           percentages 6) · hard rule 8 (no address column) · BR-CUS-092 (SSN
#           and licence encrypted at the application layer, blind index beside,
#           last four on read) · BR-CUS-1077 (`cancelled` now has a writer —
#           CR-171 S2) · CR-171 §8.3 (the down path REFUSES while new rows exist)
# Migration under test: apps/customers/migrations/0080_cr171_p1_01_move_in_redesign.py
# PostgreSQL half: tests/test_cr171_p1_01_rls_pg.py
# ───────────────────────────────────────────────────────
"""The move-in redesign's schema, proved on the suite's own database.

What runs here runs on SQLite AND on PostgreSQL (`--ds=config.settings.pgtest`);
the row-level-security half lives in `test_cr171_p1_01_rls_pg.py` because SQLite
has no RLS and a probe there would pass by vacuum (hard-won law 7).
"""

from __future__ import annotations

import importlib
from types import SimpleNamespace
from datetime import date
from decimal import Decimal

import pytest
from django.apps import apps as django_apps
from django.db import IntegrityError, connection, transaction
from django.core.exceptions import FieldError

from core import crypto

from tests.test_us_met_helpers import *  # noqa: F401,F403 — brazos · lonestar · dana · erin
from tests.test_us_met_helpers import make_premises, make_unit, tenant_ctx

pytestmark = [pytest.mark.django_db]

MIGRATION = "apps.customers.migrations.0080_cr171_p1_01_move_in_redesign"


# ── fixtures ────────────────────────────────────────────────────────────────
def _account(tenant, actor, service, tag="A"):
    from apps.customers import models as cm

    premises = make_premises(actor, address_line=f"{tag} Schema Way", services_available=[service])
    unit = make_unit(actor, premises["id"], label=f"Unit {tag}", services=[service])
    return cm.Account.objects.create(
        tenant=tenant,
        unit_id=unit["id"],
        status=cm.AccountStatus.objects.filter(tenant=tenant).first(),
        account_type=cm.AccountType.objects.filter(tenant=tenant).first(),
        account_no=f"A-{tag}-{tenant.pk.hex[:6]}",
    )


def _move(tenant, account):
    from apps.customers import moves

    return moves.MoveRecord.objects.create(
        tenant=tenant, kind=moves.KIND_MOVE_IN, account=account, effective_on=date(2026, 10, 10)
    )


@pytest.fixture
def estate(brazos, dana):
    with tenant_ctx(brazos):
        account = _account(brazos, dana, "electric")
        move = _move(brazos, account)
    return brazos, account, move


def _db_id(pk):
    """A uuid as this vendor stores it: SQLite holds 32 hex digits, PostgreSQL a uuid."""
    return pk.hex if connection.vendor == "sqlite" else str(pk)


def _refused(make):
    """An insert the database must refuse, inside a savepoint (law 14)."""
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            make()


# ── (1) the co-owner / owner-or-officer table ───────────────────────────────
def test_co_owner_table_holds_both_kinds_with_full_fields(estate):
    from apps.customers.co_owner_models import AccountCoOwner, KINDS

    tenant, account, _ = estate
    assert KINDS == ("co_owner", "officer")
    with tenant_ctx(tenant):
        riya = AccountCoOwner.objects.create(
            tenant=tenant,
            account=account,
            kind="co_owner",
            full_name="Riya G",
            relationship="spouse",
            date_of_birth=date(1999, 3, 2),
            phone="(732) 555-0144",
            email="riya@example.com",
            contact_by="text",
            responsible_for_bills=True,
        )
        arun = AccountCoOwner.objects.create(
            tenant=tenant,
            account=account,
            kind="officer",
            full_name="Arun Mehta",
            title="Managing member",
            ownership_pct=Decimal("50.000000"),
            signs_for_company=True,
            personal_guarantee=False,
        )
        riya.refresh_from_db()
        arun.refresh_from_db()
    assert riya.responsible_for_bills is True and riya.relationship == "spouse"
    assert arun.ownership_pct == Decimal("50.000000") and arun.signs_for_company is True
    assert riya.photo_id_document_id is None  # nullable: *"No ID"* is a real state


def test_co_owner_kind_and_vocabularies_are_checked_by_the_database(estate):
    from apps.customers.co_owner_models import AccountCoOwner

    tenant, account, _ = estate
    base = dict(tenant=tenant, account=account, full_name="X")
    with tenant_ctx(tenant):
        _refused(lambda: AccountCoOwner.objects.create(kind="friend", **base))
        _refused(
            lambda: AccountCoOwner.objects.create(kind="co_owner", contact_by="pigeon", **base)
        )
        _refused(
            lambda: AccountCoOwner.objects.create(
                kind="officer", ownership_pct=Decimal("100.000001"), **base
            )
        )
        _refused(
            lambda: AccountCoOwner.objects.create(
                kind="officer", ownership_pct=Decimal("-1"), **base
            )
        )
        # A co-owner is not an officer: a title or a stake on one is refused.
        _refused(lambda: AccountCoOwner.objects.create(kind="co_owner", title="CEO", **base))
        _refused(
            lambda: AccountCoOwner.objects.create(
                kind="co_owner", ownership_pct=Decimal("10"), **base
            )
        )


def test_ownership_is_a_percentage_held_to_six_places(estate):
    """Hard rule 2: a percentage is stored to 6."""
    from apps.customers.co_owner_models import AccountCoOwner

    field = AccountCoOwner._meta.get_field("ownership_pct")
    assert (field.max_digits, field.decimal_places) == (18, 6)


def test_ssn_and_licence_are_ciphertext_on_disk_with_a_blind_index(estate):
    """BR-CUS-092, the same way `customers.Customer` holds them."""
    from apps.customers import co_owner_models
    from apps.customers.co_owner_models import AccountCoOwner

    tenant, account, _ = estate
    with tenant_ctx(tenant):
        row = AccountCoOwner(tenant=tenant, account=account, kind="co_owner", full_name="Riya G")
        co_owner_models.set_identifier(row, "ssn", "210-80-9662")
        co_owner_models.set_identifier(row, "driving_licence", "DL986735")
        row.save()
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT ssn, ssn_bidx, driving_licence, driving_licence_bidx "
                "FROM account_co_owners WHERE id = %s",
                [_db_id(row.pk)],
            )
            ssn_raw, ssn_bidx, dl_raw, dl_bidx = cursor.fetchone()
        again = AccountCoOwner.objects.get(pk=row.pk)

    assert crypto.is_ciphertext(ssn_raw) and "9662" not in ssn_raw
    assert crypto.is_ciphertext(dl_raw) and "986735" not in dl_raw
    assert again.ssn == "210-80-9662" and again.driving_licence == "DL986735"
    assert ssn_bidx in crypto.blind_index_candidates("210809662", context="account_co_owners.ssn")
    assert dl_bidx in crypto.blind_index_candidates(
        "DL986735", context="account_co_owners.driving_licence"
    )
    # Clearing an identifier clears its token too — a stale token would go on
    # matching a value the row no longer holds.
    co_owner_models.set_identifier(again, "ssn", "")
    assert again.ssn is None and again.ssn_bidx is None


def test_the_crypto_contexts_match_the_field_declarations():
    """Hard-won law 1: a test, not the comment, holds the two in step."""
    from apps.customers import co_owner_models
    from apps.customers.co_owner_models import AccountCoOwner

    for field, context in co_owner_models.CRYPTO_CONTEXT.items():
        assert AccountCoOwner._meta.get_field(field).crypto_context == context
        assert AccountCoOwner._meta.get_field(co_owner_models.BIDX_COLUMN[field])
    assert set(co_owner_models.CRYPTO_CONTEXT) == {"ssn", "driving_licence"}
    with pytest.raises(ValueError):
        co_owner_models.set_identifier(AccountCoOwner(), "phone", "1")


def test_a_customer_ssn_ciphertext_cannot_be_lifted_into_a_co_owner(estate):
    """The AAD binds a ciphertext to its column."""
    from apps.customers.co_owner_models import AccountCoOwner

    tenant, account, _ = estate
    lifted = crypto.encrypt("210-80-9662", context="customers.ssn")
    with tenant_ctx(tenant):
        row = AccountCoOwner.objects.create(
            tenant=tenant, account=account, kind="co_owner", full_name="Riya G"
        )
        with connection.cursor() as cursor:
            cursor.execute(
                "UPDATE account_co_owners SET ssn = %s WHERE id = %s", [lifted, _db_id(row.pk)]
            )
        with pytest.raises(crypto.FieldDecryptionError):
            AccountCoOwner.objects.get(pk=row.pk).ssn  # noqa: B018


def test_the_encrypted_columns_refuse_a_search():
    from apps.customers.co_owner_models import AccountCoOwner

    with pytest.raises(FieldError):
        AccountCoOwner.objects.filter(ssn="210809662").exists()


def test_the_photo_id_is_a_filing_card_on_the_account():
    """Reuse: the photo ID is an `AccountDocument`, not a new file column."""
    from apps.customers.account_document_models import AccountDocument
    from apps.customers.co_owner_models import AccountCoOwner

    field = AccountCoOwner._meta.get_field("photo_id_document")
    assert field.related_model is AccountDocument and field.null


def test_a_co_owner_has_no_address_column():
    """Hard rule 8 — an address lives on `premises`; a mailing address is
    `customers.addresses kind='mailing'`."""
    from apps.customers.co_owner_models import AccountCoOwner

    names = {f.name for f in AccountCoOwner._meta.get_fields()}
    assert not names & {"address", "line1", "city", "state", "postal_code", "address_line"}


# ── (2) the company columns ─────────────────────────────────────────────────
def test_company_columns_land_on_the_customer_and_the_account(estate):
    from apps.customers import models as cm

    tenant, account, _ = estate
    with tenant_ctx(tenant):
        customer = cm.Customer.objects.create(
            tenant=tenant,
            kind="company",
            display_name="Kestrel Bakery LLC",
            trading_as="Kestrel Bakery",
            business_type="llc",
            registered_in="IA",
        )
        account.po_number = "PO-4471"
        account.bills_go_to = "contact_person"
        account.save(update_fields=["po_number", "bills_go_to"])
        customer.refresh_from_db()
        account.refresh_from_db()
    assert (customer.trading_as, customer.business_type, customer.registered_in) == (
        "Kestrel Bakery",
        "llc",
        "IA",
    )
    assert (account.po_number, account.bills_go_to) == ("PO-4471", "contact_person")


def test_bills_go_to_is_a_checked_vocabulary(estate):
    from apps.customers import models as cm

    tenant, account, _ = estate
    assert cm.BILLS_GO_TO == ("account_holder", "contact_person")
    with tenant_ctx(tenant):
        _refused(lambda: cm.Account.objects.filter(pk=account.pk).update(bills_go_to="the moon"))


def test_autopay_from_is_a_per_account_pointer_with_no_foreign_key():
    """CR-171 §6: *"the Autopay source points at a StoredPaymentInstrument"* —
    a UUID, because payments already points into customers."""
    from django.db import models as dj

    from apps.customers import models as cm

    field = cm.Account._meta.get_field("autopay_instrument_id")
    assert isinstance(field, dj.UUIDField) and field.null


@pytest.mark.parametrize("what", ["autopay", "contact"])
def test_the_down_path_refuses_while_an_autopay_source_or_contact_detail_is_set(estate, what):
    import uuid

    from apps.customers import models as cm

    tenant, account, _ = estate
    with tenant_ctx(tenant):
        if what == "autopay":
            cm.Account.objects.filter(pk=account.pk).update(autopay_instrument_id=uuid.uuid4())
            words = ("autopay", "accounts")
        else:
            cm.Contact.objects.create(
                tenant=tenant, account=account, full_name="Nilesh G", job_title="Owner"
            )
            words = ("job title", "contacts")
    with pytest.raises(RuntimeError) as refused:
        _run_guard()
    assert all(word in str(refused.value) for word in words)


def test_the_contact_person_carries_a_job_title_and_a_contact_by(estate):
    """Lane MVI-IDN's ask (CR-171 §9.IDN): image 40's *Job title* and the
    *Contact by* of images 33 and 40 live on the `contacts` row (E59)."""
    from apps.customers import models as cm

    tenant, account, _ = estate
    assert cm.CONTACT_BY == ("email", "text", "phone", "letter")
    with tenant_ctx(tenant):
        contact = cm.Contact.objects.create(
            tenant=tenant,
            account=account,
            full_name="Nilesh G",
            job_title="Owner",
            contact_by="email",
        )
        contact.refresh_from_db()
        assert (contact.job_title, contact.contact_by) == ("Owner", "email")
        _refused(lambda: cm.Contact.objects.filter(pk=contact.pk).update(contact_by="pigeon"))


# ── (3) tax exemption — REUSED, nothing new ─────────────────────────────────
def test_tax_exemption_type_and_issued_are_reused_from_rating():
    """`rating.TaxExemptionCertificate` already holds the exemption's TYPE
    (`category`) and its ISSUED date (`issued_on`); the move-in adds no column
    for either, and none on `accounts`."""
    from apps.customers import models as cm
    from apps.rating.models import TaxExemptionCertificate

    cert = {f.name for f in TaxExemptionCertificate._meta.get_fields()}
    assert {"category", "issued_on", "expires_on", "certificate_ref", "account_id"} <= cert
    account = {f.name for f in cm.Account._meta.get_fields()}
    assert not account & {"tax_exempt_type", "tax_exempt_issued", "tax_exempt_category"}


# ── (4) `cancelled` on a move-in job ────────────────────────────────────────
def test_a_move_in_job_may_now_be_cancelled_and_nothing_else_new(brazos, dana):
    from apps.customers import move_in_jobs

    assert move_in_jobs.STATES == ("pending", "done", "cancelled")
    assert move_in_jobs.STATE_CANCELLED == "cancelled"
    constraint = next(
        c for c in move_in_jobs.MoveInJob._meta.constraints if c.name == "ck_move_in_job_state"
    )
    assert "cancelled" in str(constraint.condition)
    assert "bogus" not in str(constraint.condition)


# ── (5) fee lines on the move record ────────────────────────────────────────
def test_fee_lines_hang_off_the_move_record_at_four_places(estate):
    from apps.customers.move_in_extras import MoveFeeLine

    tenant, _, move = estate
    with tenant_ctx(tenant):
        deposit = MoveFeeLine.objects.create(
            tenant=tenant,
            move_record=move,
            seq=1,
            kind="deposit",
            source="plan",
            code="DEPOSIT",
            description="Residential deposit",
            amount=Decimal("150.0000"),
            currency="USD",
        )
        MoveFeeLine.objects.create(
            tenant=tenant,
            move_record=move,
            seq=2,
            kind="fee",
            source="charge_code",
            code="RUSH",
            amount=Decimal("40.0000"),
            currency="USD",
        )
        total = sum(line.amount for line in MoveFeeLine.objects.filter(move_record=move))
    assert total == Decimal("190.0000")
    field = MoveFeeLine._meta.get_field("amount")
    assert (field.max_digits, field.decimal_places) == (18, 4)
    assert deposit.charge_code_id is None  # nullable — an open-amount line names none


def test_fee_line_vocabularies_and_sign_are_checked(estate):
    from apps.customers.move_in_extras import MoveFeeLine

    tenant, _, move = estate
    base = dict(tenant=tenant, move_record=move, code="X", currency="USD")
    with tenant_ctx(tenant):
        _refused(
            lambda: MoveFeeLine.objects.create(
                seq=1, kind="tip", source="plan", amount=Decimal("1"), **base
            )
        )
        _refused(
            lambda: MoveFeeLine.objects.create(
                seq=1, kind="fee", source="clerk", amount=Decimal("1"), **base
            )
        )
        _refused(
            lambda: MoveFeeLine.objects.create(
                seq=1, kind="fee", source="plan", amount=Decimal("-1"), **base
            )
        )
        MoveFeeLine.objects.create(seq=1, kind="fee", source="plan", amount=Decimal("1"), **base)
        _refused(
            lambda: MoveFeeLine.objects.create(
                seq=1, kind="fee", source="plan", amount=Decimal("2"), **base
            )
        )


# ── (6) the extra-messages plan ─────────────────────────────────────────────
def test_extra_messages_are_planned_on_the_move_record(estate):
    from apps.customers.co_owner_models import AccountCoOwner
    from apps.customers.move_in_extras import MoveExtraMessage

    tenant, account, move = estate
    with tenant_ctx(tenant):
        riya = AccountCoOwner.objects.create(
            tenant=tenant, account=account, kind="co_owner", full_name="Riya G"
        )
        row = MoveExtraMessage.objects.create(
            tenant=tenant,
            move_record=move,
            seq=1,
            template_key="move_in_reminder",
            recipient="co_owner",
            co_owner=riya,
            channel="text",
            send_when="day_before_move_in",
        )
        row.refresh_from_db()
    assert row.notification_id is None  # written when P1.20 queues it


def test_extra_message_vocabularies_are_checked(estate):
    from apps.customers.move_in_extras import MoveExtraMessage

    tenant, _, move = estate
    base = dict(tenant=tenant, move_record=move, seq=1, template_key="t")
    ok = dict(recipient="customer", channel="email", send_when="on_complete")
    with tenant_ctx(tenant):
        _refused(lambda: MoveExtraMessage.objects.create(**{**base, **ok, "recipient": "dog"}))
        _refused(lambda: MoveExtraMessage.objects.create(**{**base, **ok, "channel": "fax"}))
        _refused(lambda: MoveExtraMessage.objects.create(**{**base, **ok, "send_when": "never"}))
        # A co-owner recipient names which co-owner; nobody else names one.
        _refused(lambda: MoveExtraMessage.objects.create(**{**base, **ok, "recipient": "co_owner"}))


# ── (7) the down path refuses while new rows exist (CR-171 §8.3) ────────────
def _run_guard():
    module = importlib.import_module(MIGRATION)
    # The guard reads only `schema_editor.connection`; SQLite refuses a real
    # schema editor inside the test's transaction, so it is handed the connection.
    module.refuse_while_rows_exist(django_apps, SimpleNamespace(connection=connection))


def test_the_down_path_passes_on_an_empty_estate(estate):
    _run_guard()


@pytest.mark.parametrize("what", ["co_owner", "fee", "message", "cancelled", "company", "po"])
def test_the_down_path_refuses_while_new_rows_exist_and_names_the_count(estate, what):
    from apps.customers import models as cm
    from apps.customers import move_in_jobs
    from apps.customers.co_owner_models import AccountCoOwner
    from apps.customers.move_in_extras import MoveExtraMessage, MoveFeeLine

    tenant, account, move = estate
    with tenant_ctx(tenant):
        if what == "co_owner":
            AccountCoOwner.objects.create(
                tenant=tenant, account=account, kind="co_owner", full_name="Riya G"
            )
            name = "account_co_owners"
        elif what == "fee":
            MoveFeeLine.objects.create(
                tenant=tenant,
                move_record=move,
                seq=1,
                kind="fee",
                source="plan",
                code="X",
                amount=Decimal("1"),
                currency="USD",
            )
            name = "move_fee_lines"
        elif what == "message":
            MoveExtraMessage.objects.create(
                tenant=tenant,
                move_record=move,
                seq=1,
                template_key="t",
                recipient="customer",
                channel="email",
                send_when="on_complete",
            )
            name = "move_extra_messages"
        elif what == "cancelled":
            from apps.customers import models as cmod

            request = cmod.ServiceRequest.objects.create(tenant=tenant, applicant_name="A")
            move_in_jobs.MoveInJob.objects.create(tenant=tenant, request=request, state="cancelled")
            name = "move_in_jobs"
        elif what == "company":
            cm.Customer.objects.create(
                tenant=tenant, kind="company", display_name="K", trading_as="K Bakery"
            )
            name = "customers"
        else:
            cm.Account.objects.filter(pk=account.pk).update(po_number="PO-1")
            name = "accounts"
    with pytest.raises(RuntimeError) as refused:
        _run_guard()
    assert name in str(refused.value) and "1" in str(refused.value)


# ── ⚖️ THE HUMAN SIGN-OFF OF 2026-10-06 ─────────────────────────────────────
def test_the_statement_the_po_signed_on_2026_10_06(estate):
    """⚖️ THE HUMAN SIGN-OFF, ASSERTED SO DRIFT GOES RED (PO 2026-10-06,
    decision log *"SIX MOVE-IN MONEY FILES SIGNED"*, verbatim: *"Money-file
    review: approve these six? - all good - go ahead"*). Statement 1 of six,
    exactly as shown:

    *"A move-in can hold Riya G as a co-owner, with her SSN stored scrambled so
    staff see only the last four digits, 9662. It can also hold fees of $150.00
    deposit + $25.00 connection, a text reminder the day before move-in, and
    "Kestrel Bakery LLC trading as Kestrel Bakery" with PO-4471 printed on its
    bills. Undoing this database change is refused while any such record
    exists, and says how many."*

    The signature covers only this sentence — NOT whether `co_owner_models.py`
    joins the guard list (never asked) and NOT the RLS policy text itself
    (machine-proved by `test_cr171_p1_01_rls_pg.py`).
    """
    from apps.customers import co_owner_models
    from apps.customers import models as cm
    from apps.customers.co_owner_models import AccountCoOwner
    from apps.customers.move_in_extras import MoveExtraMessage, MoveFeeLine

    tenant, account, move = estate
    with tenant_ctx(tenant):
        riya = AccountCoOwner(tenant=tenant, account=account, kind="co_owner", full_name="Riya G")
        co_owner_models.set_identifier(riya, "ssn", "210-80-9662")
        riya.save()
        with connection.cursor() as cursor:
            cursor.execute("SELECT ssn FROM account_co_owners WHERE id = %s", [_db_id(riya.pk)])
            on_disk = cursor.fetchone()[0]
        shown = crypto.last_four(AccountCoOwner.objects.get(pk=riya.pk).ssn)

        for seq, (kind, code, amount) in enumerate(
            (("deposit", "DEPOSIT", "150.0000"), ("fee", "CONN", "25.0000")), start=1
        ):
            MoveFeeLine.objects.create(
                tenant=tenant,
                move_record=move,
                seq=seq,
                kind=kind,
                source="plan",
                code=code,
                amount=Decimal(amount),
                currency="USD",
            )
        fees = {line.kind: line.amount for line in MoveFeeLine.objects.filter(move_record=move)}
        reminder = MoveExtraMessage.objects.create(
            tenant=tenant,
            move_record=move,
            seq=1,
            template_key="move_in_reminder",
            recipient="customer",
            channel="text",
            send_when="day_before_move_in",
        )
        kestrel = cm.Customer.objects.create(
            tenant=tenant,
            kind="company",
            display_name="Kestrel Bakery LLC",
            trading_as="Kestrel Bakery",
        )
        cm.Account.objects.filter(pk=account.pk).update(po_number="PO-4471")
        account.refresh_from_db()

    # Riya's SSN: scrambled on disk, staff see 9662 and nothing more.
    assert crypto.is_ciphertext(on_disk) and "9662" not in on_disk
    assert shown == "9662"
    # $150.00 deposit + $25.00 connection, held at four places.
    assert fees == {"deposit": Decimal("150.0000"), "fee": Decimal("25.0000")}
    # A text the day before move-in.
    assert (reminder.channel, reminder.send_when) == ("text", "day_before_move_in")
    # Kestrel Bakery LLC trading as Kestrel Bakery, PO-4471 on its bills.
    assert (kestrel.display_name, kestrel.trading_as) == ("Kestrel Bakery LLC", "Kestrel Bakery")
    assert account.po_number == "PO-4471"
    # Undoing the change is refused, and says how many.
    with pytest.raises(RuntimeError) as refused:
        _run_guard()
    said = str(refused.value)
    assert "1 co-owners / owners and officers (account_co_owners)" in said
    assert "2 fee lines (move_fee_lines)" in said
    assert "1 extra messages (move_extra_messages)" in said
    assert "(customers)" in said and "(accounts)" in said
