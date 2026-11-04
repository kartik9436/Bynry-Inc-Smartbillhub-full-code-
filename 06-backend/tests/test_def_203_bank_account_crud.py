# ── Trace ──────────────────────────────────────────────
# Defect:   DEF-203 — "The utility's own bank accounts cannot be created, so
#           bank reconciliation cannot run for any real tenant". The register's
#           own prevention line asks for exactly the guard below: *"a test that
#           provisions a tenant the way seed_demo does and then drives S38 — the
#           class of defect is 'reachable only from a test fixture', and only a
#           test that refuses to mint fixtures can see it."*
# Story:    US-TEN-009 · US-TEN-010 · US-TEN-011 (the S8 card and its CRUD) ·
#           US-PAY-021 (the statement import that SELECTS one)
#           Screens: S8 · S38
# Rules:    BR-PAY-850 (this list's law) · BR-TEN-031 (the OWNING module
#           validates and writes) · BR-TEN-029 (used-by live) · BR-TEN-030
#           (identity unique per tenant, case-insensitive) · BR-TEN-034
#           (deactivate, never delete) · BR-PAY-019 · BR-PAY-028
# ───────────────────────────────────────────────────────
"""DEF-203 — a utility can create its own bank accounts, and reconciliation runs.

⛔ **THIS FILE MINTS NO `BankAccount`, ANYWHERE, ON PURPOSE.** That is the whole
guard. `bankrec_models.BankAccount` had a model, a unique key, an RLS policy, a
PROTECTed FK and two readers from 2026-08-11, and the ONLY thing in the repo that
ever created one was `tests/test_us_pay_020_023_bank_rec.py::a_bank_account`.
Every bank-rec test passed because each minted its own — which is precisely what
hid the defect for eleven days. So every account below arrives the way a utility's
does: through `tenancy.services.create_lookup_entry`, the door the S8 card posts
to, with a System Admin actor and a provisioned tenant.

RED BEFORE GREEN (hard-won law 7). Against the tree at the start of this lane —
no `apps/payments/lookups.py`, no `bank_accounts` in `LOOKUP_LISTS` — every test
in this file fails: `create_lookup_entry` raises `NotFoundError` for an
unregistered list, so a utility has no door and `bank_accounts()` stays empty
forever. The transcript is in the lane report.
"""

from datetime import UTC, date, datetime

import pytest

from apps.payments import api as payments_api
from apps.payments import bankrec_models as bankrec
from apps.payments import bankrec_read, lookups, reconciliation
from apps.payments.exceptions import PaymentRuleError
from apps.tenancy import api as tenancy_api
from apps.tenancy import selectors as tenancy_selectors
from apps.tenancy import services as tenancy_services
from core import errors

from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import api_call, tenant_ctx

pytestmark = pytest.mark.django_db

LIST = "bank_accounts"

#: r10 SET-11's own example, and the string S38 step 1 renders.
CHASE = {"code": "Chase Operating", "name": "Chase Operating", "mask": "4021"}

STATEMENT_AT = datetime(2026, 8, 11, 6, 40, tzinfo=UTC)


def a_statement(rows, *, header="Posting date,Description,Amount"):
    """A bank CSV in the shape S38 step 1 accepts."""
    body = "\n".join(f"{when},{reference},{amount}" for when, reference, amount in rows)
    return f"{header}\n{body}\n".encode()


def add_bank_account(actor, payload=None):
    """The ONLY way an account is created in this file — the S8 card's door."""
    return tenancy_services.create_lookup_entry(actor, LIST, dict(payload or CHASE))


# ═══════════════════════════════════════════════════════════════════════════
# THE DEFECT ITSELF — a fresh tenant has no bank account and CAN make one
# ═══════════════════════════════════════════════════════════════════════════
def test_def203__a_freshly_provisioned_tenant_has_no_bank_account(brazos):
    """The honest starting state, and it is not the defect.

    Nothing seeds this list and nothing should: nobody but the utility knows
    what their accounts are called (BR-PAY-850). What WAS the defect is that
    this state could never be left."""
    with tenant_ctx(brazos):
        assert bankrec_read.bank_accounts() == []


def test_def203__the_card_is_the_door_and_it_opens(brazos, dana):
    """RED before the fix: `create_lookup_entry` raises NotFoundError because
    no module had registered a handler for `bank_accounts` — the list was not
    even declared."""
    with tenant_ctx(brazos):
        row = add_bank_account(dana)
    assert row["name"] == "Chase Operating"
    assert row["mask"] == "4021"
    assert row["active"] is True
    assert row["used_by"] == 0
    # No `code` column exists — the framework's code slot is the NAME.
    assert row["code"] == "Chase Operating"


def test_def203__s38_step_1_can_now_offer_the_account(brazos, dana):
    """The surface the defect was reported on: S38 step 1's picker, rendered
    as *"Chase Operating ••4021"*."""
    with tenant_ctx(brazos):
        created = add_bank_account(dana)
        offered = bankrec_read.bank_accounts()
    assert [(row["name"], row["mask"]) for row in offered] == [("Chase Operating", "4021")]
    assert offered[0]["id"] == created["id"]


def test_def203__a_statement_imports_against_an_account_made_on_the_card(brazos, dana):
    """END TO END, and it is the assertion the defect's headline asks for: the
    bank half of reconciliation runs on a tenant whose bank account was created
    the way a real utility creates one."""
    with tenant_ctx(brazos):
        created = add_bank_account(dana)
        result = reconciliation.import_bank_statement(
            actor=dana,
            bank_account_id=created["id"],
            period_start=date(2026, 8, 1),
            period_end=date(2026, 8, 14),
            payload=a_statement([("2026-08-11", "DEPOSIT", "588.17")]),
            imported_at=STATEMENT_AT,
            file_name="august.csv",
        )
        assert result.line_count == 1
        review = bankrec_read.statement_review(result.statement_import_id)
    assert review["statement"]["bank_account_name"] == "Chase Operating"
    assert review["statement"]["bank_account_mask"] == "4021"


def test_def203__the_import_is_still_idempotent_on_file_plus_this_account(brazos, dana):
    """BR-PAY-028: the account is the TAG half of the key, so a second import
    of the same bytes for the same account and period is refused by name. The
    card must not have weakened that."""
    payload = a_statement([("2026-08-11", "DEPOSIT", "588.17")])
    with tenant_ctx(brazos):
        created = add_bank_account(dana)
        kwargs = dict(
            actor=dana,
            bank_account_id=created["id"],
            period_start=date(2026, 8, 1),
            period_end=date(2026, 8, 14),
            payload=payload,
            imported_at=STATEMENT_AT,
        )
        reconciliation.import_bank_statement(**kwargs)
        with pytest.raises(PaymentRuleError) as refusal:
            reconciliation.import_bank_statement(**kwargs)
    assert "already imported" in str(refusal.value)


# ═══════════════════════════════════════════════════════════════════════════
# THE ROW IS THREE FIELDS — and the two that are absent stay absent
# ═══════════════════════════════════════════════════════════════════════════
def test_br_pay_850__the_mask_is_four_digits_and_a_fifth_is_refused(brazos, dana):
    """⛔ The PII posture is only real if something REFUSES.

    B2 §6: a column you do not store cannot leak. Without this cap the field is
    a free-text box a well-meaning clerk fills with the full account number."""
    with tenant_ctx(brazos):
        with pytest.raises(errors.ValidationError) as refusal:
            add_bank_account(dana, {"name": "Chase Operating", "mask": "123456789012"})
    assert refusal.value.message_key == "payments.lookups.mask_shape"


@pytest.mark.parametrize("mask", ["40x1", "•4021", "٤٠٢١", " 4021 5", "4-21"])
def test_br_pay_850__a_non_numeric_mask_is_refused(brazos, dana, mask):
    """ASCII digits only. `٤٠٢١` is there on purpose: `str.isdigit()` answers
    True for Arabic-Indic digits, so a mask checked that way would store
    characters no bank statement can be compared against."""
    with tenant_ctx(brazos):
        with pytest.raises(errors.ValidationError) as refusal:
            add_bank_account(dana, {"name": "Chase Operating", "mask": mask})
    assert refusal.value.message_key == "payments.lookups.mask_shape"


def test_br_pay_850__the_mask_is_optional_and_blank_stores_nothing(brazos, dana):
    """A utility with one account need not type a mask at all. Blank is NULL,
    not an empty string, so the picker renders the bare name."""
    with tenant_ctx(brazos):
        row = add_bank_account(dana, {"name": "Community Bank", "mask": ""})
        assert row["mask"] is None
        assert bankrec_read.bank_accounts() == [
            {"id": row["id"], "name": "Community Bank", "mask": None}
        ]


@pytest.mark.parametrize(
    "field", ["account_number", "routing_number", "gl_account", "bank_address"]
)
def test_br_pay_850__the_row_cannot_be_widened(brazos, dana, field):
    """An account number, a routing number, a GL account: REFUSED BY NAME.

    A silent drop would look exactly like storage to the person who typed it,
    and 'no GL account hangs off this row' is a ruling (OQ-110's closure —
    reconciliation resolves `cash` by designation), not an oversight."""
    with tenant_ctx(brazos):
        with pytest.raises(errors.ValidationError) as refusal:
            add_bank_account(dana, {"name": "Chase Operating", field: "1234567890"})
    assert refusal.value.message_key == "payments.lookups.unknown_field"
    with tenant_ctx(brazos):
        assert bankrec_read.bank_accounts() == []


def test_br_ten_030__two_accounts_cannot_share_a_name(brazos, dana):
    """The identity is the NAME (`uq_bank_accounts_name`), so this refusal is a
    readable message in front of a constraint that would otherwise 500."""
    with tenant_ctx(brazos):
        add_bank_account(dana)
        with pytest.raises(errors.ValidationError) as refusal:
            add_bank_account(dana, {"name": "chase operating", "mask": "9999"})
    assert refusal.value.message_key == "payments.lookups.duplicate_name"


def test_br_pay_850__a_nameless_account_is_refused(brazos, dana):
    with tenant_ctx(brazos):
        with pytest.raises(errors.ValidationError) as refusal:
            add_bank_account(dana, {"name": "   ", "mask": "4021"})
    assert refusal.value.message_key == "payments.lookups.name_required"


# ═══════════════════════════════════════════════════════════════════════════
# DEACTIVATE, NEVER DELETE — and a used account stays resolvable
# ═══════════════════════════════════════════════════════════════════════════
def test_br_ten_034__a_deactivated_account_leaves_the_picker_and_refuses_an_import(brazos, dana):
    with tenant_ctx(brazos):
        created = add_bank_account(dana)
        tenancy_services.set_lookup_entry_active(dana, LIST, created["id"], False)
        assert bankrec_read.bank_accounts() == []
        with pytest.raises(PaymentRuleError) as refusal:
            reconciliation.import_bank_statement(
                actor=dana,
                bank_account_id=created["id"],
                period_start=date(2026, 8, 1),
                period_end=date(2026, 8, 14),
                payload=a_statement([("2026-08-11", "DEPOSIT", "10.00")]),
                imported_at=STATEMENT_AT,
            )
    assert "not a live bank account" in str(refusal.value)


def test_br_ten_034__what_was_already_imported_still_resolves_after_deactivation(brazos, dana):
    """THE REASON THE CONTROL IS DEACTIVATE AND NOT DELETE. A bank account named
    on an imported statement must stay resolvable, forever."""
    with tenant_ctx(brazos):
        created = add_bank_account(dana)
        result = reconciliation.import_bank_statement(
            actor=dana,
            bank_account_id=created["id"],
            period_start=date(2026, 8, 1),
            period_end=date(2026, 8, 14),
            payload=a_statement([("2026-08-11", "DEPOSIT", "588.17")]),
            imported_at=STATEMENT_AT,
        )
        tenancy_services.set_lookup_entry_active(dana, LIST, created["id"], False)
        review = bankrec_read.statement_review(result.statement_import_id)
    assert review["statement"]["bank_account_name"] == "Chase Operating"
    assert review["statement"]["bank_account_mask"] == "4021"


def test_br_ten_034__a_used_account_cannot_be_deleted(brazos, dana):
    """`used_by` counts the statements imported against it (BR-TEN-029, live),
    and `bank_statement_imports.bank_account_id` is PROTECT underneath."""
    with tenant_ctx(brazos):
        created = add_bank_account(dana)
        reconciliation.import_bank_statement(
            actor=dana,
            bank_account_id=created["id"],
            period_start=date(2026, 8, 1),
            period_end=date(2026, 8, 14),
            payload=a_statement([("2026-08-11", "DEPOSIT", "588.17")]),
            imported_at=STATEMENT_AT,
        )
        page = tenancy_selectors.lookup_page(LIST, None)
        assert [row["used_by"] for row in page] == [1]
        with pytest.raises(errors.BizError):
            tenancy_services.delete_lookup_entry(dana, LIST, created["id"])
        assert bankrec.BankAccount.objects.filter(tenant=brazos).count() == 1


def test_br_ten_034__an_unused_account_can_be_deleted(brazos, dana):
    with tenant_ctx(brazos):
        created = add_bank_account(dana)
        tenancy_services.delete_lookup_entry(dana, LIST, created["id"])
        assert bankrec_read.bank_accounts() == []


# ═══════════════════════════════════════════════════════════════════════════
# THE CARD, THE REGISTRY AND THE ONE-WRITER RULE
# ═══════════════════════════════════════════════════════════════════════════
def test_def203__the_s8_card_grid_shows_the_list_with_its_live_count(brazos, dana):
    """BR-TEN-029: the count is computed at render. A card with no number is
    what a System Admin reads as 'nothing here', so the card must be in the
    grid from the moment the list is declared — at 0, honestly."""
    with tenant_ctx(brazos):
        before = {card["list"]: card for card in tenancy_selectors.lookup_cards()}
        assert before[LIST]["count"] == 0
        assert before[LIST]["owner"] == "payments"
        add_bank_account(dana)
        after = {card["list"]: card for card in tenancy_selectors.lookup_cards()}
    assert after[LIST]["count"] == 1


def test_def203__the_list_is_declared_and_owned_by_payments():
    """BR-TEN-031 — tenancy renders, the OWNING module validates and writes."""
    definition = tenancy_services.LOOKUP_LISTS[LIST]
    assert definition.owner == "payments"
    assert isinstance(definition.handler, lookups.BankAccountLookupHandler)


def test_def016__the_list_is_registered_as_never_seeded_with_a_written_reason():
    """It is EMPTY on every fresh tenant by design, so DEF-016's rule applies:
    an empty declared list carries a written reason or the report calls it
    UNEXPLAINED. This is the one entry expected to be permanent."""
    reason = tenancy_services.UNSEEDABLE_REFERENCE_LISTS[LIST]
    assert len(reason) > 120
    assert LIST not in dict(tenancy_services.SEED_LIST_OWNERS)


def test_def203__the_reference_data_report_calls_it_empty_not_unexplained(brazos):
    with tenant_ctx(brazos):
        report = tenancy_services.reference_data_report()
    row = next(entry for entry in report["lists"] if entry["list"] == LIST)
    assert row["state"] == "empty"
    assert report["unexplained"] == []


def test_br_pay_850__the_card_is_the_only_writer_in_the_product():
    """ONE WRITER FOR ONE FACT (PO ruling 2026-08-28). S38 SELECTS; it must
    never gain a create path.

    A source scan rather than a behaviour test, deliberately: the failure this
    guards against is a SECOND writer being added, and a second writer breaks
    nothing until two screens disagree about which accounts a utility has. It
    would pass every behavioural test on the day it landed."""
    import pathlib
    import re

    root = pathlib.Path(__file__).resolve().parents[1] / "apps"
    creators = sorted(
        str(path.relative_to(root.parent))
        for path in root.rglob("*.py")
        if re.search(r"BankAccount\.objects\.create\(", path.read_text("utf-8"))
    )
    assert creators == ["apps/payments/lookups.py"], (
        "a SECOND writer of bank_accounts exists — the card is the only one "
        f"(BR-PAY-850, PO ruling 2026-08-28): {creators}"
    )


# ═══════════════════════════════════════════════════════════════════════════
# THROUGH THE MOUNTED ROUTES — the walk a person takes, minus the browser
# ═══════════════════════════════════════════════════════════════════════════
def test_def203__the_whole_walk_over_the_real_endpoints(brazos, dana):
    """Settings → Configure → Reference data → Bank accounts → Add, then the
    bank-statement import, over the URLs the SPA actually calls.

    Not a browser (no Playwright browser is installed in this container, and
    that is stated rather than implied), but every layer under it: routing,
    the A4 role gate, the framework's audit write, serialization, and the two
    payments reads S38 depends on."""
    created = api_call(
        tenancy_api.lookups,
        "post",
        user=dana.user,
        role="system_admin",
        tenant=brazos,
        list_code=LIST,
        data={"code": "Chase Operating", "name": "Chase Operating", "mask": "4021"},
    )
    assert created.status_code == 201
    assert created.data["name"] == "Chase Operating"

    # The S8 card grid, in the same request the whole grid uses (BR-TEN-029).
    grid = api_call(
        tenancy_api.lookup_cards, "get", user=dana.user, role="system_admin", tenant=brazos
    )
    card = next(row for row in grid.data if row["list"] == LIST)
    assert (card["owner"], card["count"], card["state"]) == ("payments", 1, "seeded")

    # S38 step 1's picker — the surface DEF-203 was reported on.
    picker = api_call(
        payments_api.bank_accounts, "get", user=dana.user, role="system_admin", tenant=brazos
    )
    assert picker.status_code == 200
    assert [(row["name"], row["mask"]) for row in picker.data["rows"]] == [
        ("Chase Operating", "4021")
    ]

    # …and the statement import accepts it.
    import base64

    imported = api_call(
        payments_api.bank_statements,
        "post",
        user=dana.user,
        role="system_admin",
        tenant=brazos,
        data={
            "file_base64": base64.b64encode(
                a_statement([("2026-08-11", "DEPOSIT", "588.17")])
            ).decode(),
            "bank_account_id": created.data["id"],
            "period_start": "2026-08-01",
            "period_end": "2026-08-14",
            "imported_at": "2026-08-11T06:40:00Z",
            "file_name": "august.csv",
        },
    )
    assert imported.status_code == 201
    assert imported.data["review"]["statement"]["bank_account_name"] == "Chase Operating"


def test_def203__every_write_to_this_list_lands_in_the_audit_log(brazos, dana, audit_rows):
    """CLAUDE.md rule 7. The framework writes it (tenancy's create/update/
    set_active), not this handler — asserted here so a future handler that grows
    its own write path cannot skip it quietly."""
    with tenant_ctx(brazos):
        created = add_bank_account(dana)
        tenancy_services.update_lookup_entry(dana, LIST, created["id"], {"mask": "9999"})
        tenancy_services.set_lookup_entry_active(dana, LIST, created["id"], False)
    actions = [row["action"] for row in audit_rows if row.get("entity_type") == "lookup_entry"]
    assert actions == [
        "settings.lookup.created",
        "settings.lookup.updated",
        "settings.lookup.deactivated",
    ]


# ═══════════════════════════════════════════════════════════════════════════
# THE HEADLINE QUESTION — CAN BANK RECONCILIATION ACTUALLY RUN NOW?
# ═══════════════════════════════════════════════════════════════════════════
def test_def203__a_month_reconciles_end_to_end_on_an_account_a_utility_created(
    brazos, marcus, dana, audit_rows
):
    """DEF-203's headline, answered rather than implied: *"bank reconciliation
    cannot run for any real tenant"*.

    The whole chain, on PE-11's frozen figures — money taken over the counter,
    the day's batch cut, the statement imported, the −5.00 explained as a bank
    fee with its GL, the batch reconciled and locked. **The ONLY difference from
    `test_us_pay_020_023_bank_rec.py`'s version is where the bank account comes
    from:** there it is minted by a fixture, here a System Admin creates it on
    the Reference-data card. That one substitution is the entire defect.
    """
    from decimal import Decimal

    from tests import test_us_pay_020_023_bank_rec as bankrec_fixtures

    with tenant_ctx(brazos):
        batch = bankrec_fixtures.a_batch(
            marcus,
            brazos,
            amounts=(Decimal("400.00"), Decimal("193.17")),  # Σ = PE-11's 593.17
            method_code="check",
        )
        assert batch.recorded_total == bankrec_fixtures.PE11_RECORDED

        # ⛔ THE ONE LINE THAT COULD NOT BE WRITTEN BEFORE THIS LANE.
        account = add_bank_account(dana)

        imported = reconciliation.import_bank_statement(
            actor=marcus,
            bank_account_id=account["id"],
            period_start=date(2026, 8, 1),
            period_end=date(2026, 8, 11),
            payload=a_statement([("2026-08-11", "CHECK DEPOSIT 4410", "588.17")]),
            imported_at=bankrec_fixtures.STATEMENT_AT,
        )
        difference = reconciliation.match_bank_line(
            actor=marcus,
            batch_id=batch.batch_id,
            bank_line_id=imported.exceptions[0].bank_line_id,
            occurred_at=bankrec_fixtures.STATEMENT_AT,
        )
        assert difference == bankrec_fixtures.PE11_DIFFERENCE

        result = reconciliation.reconcile_batch(
            actor=marcus,
            batch_id=batch.batch_id,
            posted_at=bankrec_fixtures.STATEMENT_AT,
            resolutions=(
                reconciliation.ResolutionInput(
                    reason_code="bank_fee",
                    gl_account_id=bankrec_fixtures.gl_id(brazos, "bank_fees"),
                    amount=bankrec_fixtures.PE11_DIFFERENCE,
                    note="Bank fee on the Aug 8 deposit, confirmed with the bank",
                ),
            ),
        )
        assert result.explained == bankrec_fixtures.PE11_DIFFERENCE
        assert (
            bankrec.DepositBatch.objects.get(pk=batch.batch_id).status == bankrec.BATCH_RECONCILED
        )
        legs = bankrec_fixtures.journal_legs(brazos)

    # The frozen money, unmoved: the bank gave us 588.17, we took in 593.17, and
    # the 5.00 difference is its own line on 6800 rather than hidden anywhere.
    assert bankrec_fixtures.leg(legs, "1000", "debit") == bankrec_fixtures.PE11_BANK
    assert bankrec_fixtures.leg(legs, "6800", "debit") == Decimal("5.00")
    assert bankrec_fixtures.leg(legs, "1010", "credit") == bankrec_fixtures.PE11_RECORDED


# ── Lifecycle ─────────────────────────────────────────────
# packet: DEF-203 (defect register row, 2026-08-17) + PO ruling 2026-08-28 "BANK ACCOUNTS ARE CAPTURED IN SETTINGS → CONFIGURE" (12-governance/02-decision-log.md) + BR-PAY-850
# generated: 2026-08-28 by story-coder (DEF-203 bank-account capture lane)
# checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-09)
# gates: see the lane report
# exceptions: this file mints NO BankAccount and must never start — every account here arrives through tenancy's create_lookup_entry, the door the S8 card posts to, because "reachable only from a test fixture" is the class of defect DEF-203 belongs to · the one-writer assertion is a SOURCE SCAN rather than a behaviour test, deliberately: a second writer would pass every behavioural test on the day it landed · the deposit-side of reconciliation (batches cut from cleared payments) is NOT re-asserted here — it is US-PAY-020's file and is unchanged by this lane
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
