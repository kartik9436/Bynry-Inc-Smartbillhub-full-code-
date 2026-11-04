# ── Trace ──────────────────────────────────────────────
# Story:    US-CUS-001 (EP-CUS-01 — the BR-CUS-055 status vocabulary the S17
#           pill renders) · US-CUS-020 (EP-CUS-07 reference data)
#           Screens: S17 · S21 · S8 · S90
# Rules:    BR-CUS-107 (a cut account is `Disconnected`, class `non_billable`;
#           PO 2026-08-25, closing DEF-701) · BR-CUS-055 (the five this
#           amends) · BR-CUS-103 (base stops at the cut — why the class is not
#           `billable_base_only`) · BR-CUS-104 (paying is how a cut customer
#           gets reconnected — why payment must still be accepted) ·
#           BR-PAY-036 (a payment is ALWAYS accepted, in every account status)
#           · BR-CUS-017 / BR-MET-036 (which statuses occupy a unit) ·
#           BR-TEN-012 (per-list idempotent) · BR-TEN-030 (codes unique per
#           tenant, case-insensitive)
# Defects:  DEF-701 (a cut account still reads `Marked disconnect / billable`)
# ───────────────────────────────────────────────────────
"""BR-CUS-107 — the sixth account status, and the two things it must not break.

**What the PO ruled, 2026-08-25, closing DEF-701:** a cut account gets a sixth
status, **`Disconnected`**, in behaviour class **`non_billable`**. BR-CUS-055
seeded five — Pending activation · Active · Marked disconnect · Vacation
hold/Suspended · Closed — and none of them means *"the service is off"*: a cut
account read `Marked disconnect / billable`, which is the rung BEFORE the cut
and whose own seed comment says *"consuming until cut"* about a customer who
has stopped consuming.

The other three classes were each ruled out with a stated reason and this file
pins all three so a later lane cannot quietly re-open one: `billable` bills a
service that no longer runs; `billable_base_only` was eliminated by the PO's
own answer the same day (BR-CUS-103 — base stops at the cut, so there is no
base to bill); `terminal` is what `Closed` means, and a cut account is not
closed — it holds a debt, it can pay, and it comes back.

**Worked, on a real seeded account:** `A-11488`, cut **2026-08-18** owing
**$612.75**, reads `Disconnected / non-billable`; nothing accrues, the $612.75
stays owed, and `mark_reconnecting` can still take it back.

════════════════════════════════════════════════════════════════════════════
THE CLAUSE THE RULING ITSELF FLAGS — AND WHAT MEASURING IT FOUND
════════════════════════════════════════════════════════════════════════════
BR-CUS-107 says in as many words: *"a `non_billable` account MUST still accept
a PAYMENT"*, because paying is how a cut customer gets reconnected
(BR-CUS-104). **It does.** `§2` below asserts the absence that guarantees it:
`apps/payments/services.py` reads `accounts.status` nowhere at all, so no
behaviour class can suppress a payment. That is BR-PAY-036 held structurally
rather than by a status list somebody must remember to extend.

**Two OTHER things do break, and neither is a reason to pick a different class
— they are defects to close before an account is moved onto this row.** Both
are MEASURED here rather than described, so the day somebody wires the status
these tests say exactly what they broke:

  · **§3 — OCCUPANCY.** `OCCUPYING_BEHAVIOR_CLASSES` is (billable,
    billable_base_only), so an account on this row stops occupying its unit:
    the unit reads vacant and pickable for another move-in, and the cut
    customer's own move-out is refused `not_an_occupant`. `DSC-02.4` cuts
    *"leaving the account open"* and BR-MET-036 flips a unit to Vacant when the
    account is CLOSED — which a cut account is not.
  · **§4 — BILLING DROPS THE WHOLE ACCOUNT.** `resolve_subscription` refuses
    `non_billable` outright, so a cut account becomes a non-retryable break on
    every run and the usage it consumed BEFORE the cut is never billed.
    BR-CUS-103 does not need this row to stop base — `service_off_windows`
    subtracts the dark days from `service_days`, which only runs on an account
    billing has NOT dropped.

**§5 asserts the status is still ASSIGNED BY NOBODY**, which is the honest
state of this landing: the row is seeded reference data, `commit_cut` writes no
`accounts` column, and `DSC-02.4`'s three prohibitions are untouched.
"""

import importlib
import inspect
import json
from datetime import date
from pathlib import Path

import pytest

from apps.customers import models as customers_models
from apps.customers import selectors as customers_selectors
from apps.customers import services as customers_services
from apps.metering import models as metering_models
from apps.tenancy import reference_sweep as tenancy_reference_sweep
from apps.tenancy import services as tenancy_services

from tests.test_us_ten_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_ten_helpers import provisioned_tenant, tenant_ctx

pytestmark = pytest.mark.django_db

FIXTURE = json.loads(Path(tenancy_services.FIXTURE_PATH).read_text(encoding="utf-8"))

#: BR-CUS-107, verbatim. Written out rather than imported so that a change to
#: the constant this file guards cannot change what this file asserts.
RULED_CODE = "disconnected"
RULED_NAME = "Disconnected"
RULED_CLASS = "non_billable"

#: The three the PO ruled OUT, each with the reason. A later lane that "fixes"
#: the class by picking one of these breaks a named test, not a comment.
REJECTED_CLASSES = {
    "billable": "bills a service that no longer runs",
    "billable_base_only": "BR-CUS-103 — base stops at the cut, so there is no base to bill",
    "terminal": "that is what `Closed` means; a cut account is not closed",
}


def _unit_for(tenant, label="Unit A"):
    premises = metering_models.Premises.objects.create(
        tenant=tenant, address_line="1408 Elm St", city="Katy", state="TX"
    )
    return metering_models.Unit.objects.create(tenant=tenant, premises=premises, label=label)


def _account_for(tenant, *, account_no="A-11488", status_code="active", unit=None):
    status = customers_models.AccountStatus.objects.get(tenant=tenant, code=status_code)
    account_type = customers_models.AccountType.objects.get(code="residential")
    return customers_models.Account.objects.create(
        tenant=tenant,
        unit=unit or _unit_for(tenant),
        account_no=account_no,
        status=status,
        account_type=account_type,
    )


# ══════════════════════════════════════════════════════════════════════════
# 1 · THE RULED ROW LANDS, IN THE RULED CLASS, IN ALL THREE COPIES OF THE LAW
# ══════════════════════════════════════════════════════════════════════════
def test_br_cus_107__provisioning_seeds_disconnected_as_non_billable(growth_plan, identity_seam):
    """A tenant provisioned today receives the sixth status.

    RED before this lane: `SEED_ACCOUNT_STATUSES` carried five and the fixture
    carried five, so this row did not exist for any tenant — which is DEF-701:
    the product could not say a service was off.
    """
    tenant, _ = provisioned_tenant()
    with tenant_ctx(tenant):
        row = customers_models.AccountStatus.objects.get(tenant=tenant, code=RULED_CODE)
    assert row.name == RULED_NAME
    assert row.behavior_class == RULED_CLASS
    # BR-TEN-036 — seeded rows are deactivatable, never deletable.
    assert row.is_system is True
    assert row.active is True


def test_br_cus_107__the_three_rejected_classes_stay_rejected():
    """The ruling names three classes it ruled OUT, each with its reason.

    This is the guard against a later lane reading the occupancy or billing
    consequence below as *"then the class must be wrong"*. It is not: BR-CUS-107
    settled the class, and those consequences are defects in what reads it.
    """
    seeded = dict((code, behavior) for code, _name, behavior in _seed_triples())
    assert seeded[RULED_CODE] == RULED_CLASS
    for rejected, reason in REJECTED_CLASSES.items():
        assert seeded[RULED_CODE] != rejected, f"BR-CUS-107 ruled {rejected!r} out: {reason}"


def _seed_triples():
    return [
        (code, name, behavior) for code, name, behavior in customers_services.SEED_ACCOUNT_STATUSES
    ]


def test_br_cus_107__the_three_copies_of_the_law_are_one_law():
    """The ratified constant, the platform fixture and the migration agree.

    Three copies exist on purpose — a migration must survive a later constant
    edit — and this is what stops them drifting, the same posture
    `test_us_cus_schema_and_seed` takes for the original five.
    """
    ratified = [
        {"code": code, "name": name, "behavior_class": behavior}
        for code, name, behavior in customers_services.SEED_ACCOUNT_STATUSES
    ]
    assert FIXTURE["account_statuses"] == ratified
    assert {"code": RULED_CODE, "name": RULED_NAME, "behavior_class": RULED_CLASS} in ratified

    migration = importlib.import_module(
        "apps.customers.migrations.0025_br_cus_107_disconnected_status"
    )
    assert migration.STATUS_CODE == RULED_CODE
    assert migration.STATUS_NAME == RULED_NAME
    assert migration.STATUS_BEHAVIOR_CLASS == RULED_CLASS


def test_br_cus_107__the_fixture_bump_is_pinned_and_reaches_existing_tenants():
    """BR-TEN-077's content guard, and the reason the bump exists at all.

    A content change with no version bump is a change that reaches nobody:
    `_seed_reference_data` skips a list whose seed-run row already sits at the
    current version, so an existing tenant would keep five statuses for ever.
    That is 2026.08.2's undelivered fix (DEF-213) in a different list.

    ⚠ **AMENDED 2026-08-27 (CR-039 wave E task 22) — THIS ASSERTED
    `V2.48.0.0` AND THAT WAS THE WRONG QUESTION.** BR-CUS-107's bump was
    V2.48.0.0; the fixture has since moved to **V2.48.0.1** for the sub-area
    rows, and BR-CUS-107's own delivery is unaffected — a LATER version still
    carries the sixth status and still re-visits every tenant. Pinning the
    literal made this test assert *"no other lane may ever bump the fixture"*,
    which is not a rule anybody wrote and would go red on every future bump
    for the rest of the product's life.

    **So it asks what BR-CUS-107 actually needs instead**, and each of the three
    is stronger than the literal was: the version and its content AGREE
    (BR-TEN-077's real guard, unchanged), the version at which this rule landed
    is still a RATIFIED digest and was therefore never rewritten, and the
    current version is at or after it — so the row still reaches an existing
    tenant. A bump BACKWARDS, or a rewritten history, still goes red.
    """
    version = tenancy_reference_sweep.assert_fixture_version_matches_content()
    assert version in tenancy_reference_sweep.RATIFIED_FIXTURE_DIGESTS
    # The version BR-CUS-107 landed at is still pinned — its digest was never
    # rewritten, which is what would make the ledger a forgery (see the
    # `V1.0.0.0` entry's own note on rewriting history).
    assert "V2.48.0.0" in tenancy_reference_sweep.RATIFIED_FIXTURE_DIGESTS
    # …and the fixture has not been bumped BACKWARDS past it.
    assert tenancy_reference_sweep.version_key(version) >= tenancy_reference_sweep.version_key(
        "V2.48.0.0"
    )


def test_br_cus_107__the_seam_seeds_it_idempotently(growth_plan, identity_seam):
    """BR-TEN-012 — a replay creates nothing and overwrites no rename."""
    tenant, _ = provisioned_tenant()
    with tenant_ctx(tenant):
        row = customers_models.AccountStatus.objects.get(tenant=tenant, code=RULED_CODE)
        row.name = "Cut off"  # the tenant renames it — Reference data is theirs
        row.save(update_fields=["name"])

        assert customers_services.ensure_account_statuses() == 0

        row.refresh_from_db()
        assert row.name == "Cut off", "a tenant's own label is never overwritten"
        assert row.behavior_class == RULED_CLASS, "the CLASS is the rule, not the label"


def test_br_cus_107__the_migration_body_backfills_an_existing_tenant(growth_plan, identity_seam):
    """The migration's `forwards` is CODE, and code nobody runs is untrusted.

    A tenant provisioned before this landed has five statuses and no seed-run
    row will revisit it until somebody runs the sweep. This drives the migration
    body itself against exactly that state — the row deleted, the tenant
    otherwise intact — and then drives it a second time to prove the replay
    writes nothing (BR-TEN-012).
    """
    migration = importlib.import_module(
        "apps.customers.migrations.0025_br_cus_107_disconnected_status"
    )

    class _Apps:
        """The migration takes a historical `apps`; the live models answer the
        same three calls and keep this test honest about the real table."""

        @staticmethod
        def get_model(app_label, model_name):
            return getattr(customers_models, {"AccountStatus": "AccountStatus"}[model_name])

    tenant, _ = provisioned_tenant()
    with tenant_ctx(tenant):
        # Wind the tenant back to the pre-ruling five.
        customers_models.AccountStatus.objects.filter(tenant=tenant, code=RULED_CODE).delete()
        assert not customers_models.AccountStatus.objects.filter(
            tenant=tenant, code=RULED_CODE
        ).exists()

        migration.forwards(_Apps, None)
        row = customers_models.AccountStatus.objects.get(tenant=tenant, code=RULED_CODE)
        assert (row.name, row.behavior_class, row.is_system) == (RULED_NAME, RULED_CLASS, True)

        # Replay — BR-TEN-012, and the reason the probe is `code__iexact`.
        before = customers_models.AccountStatus.objects.filter(tenant=tenant).count()
        migration.forwards(_Apps, None)
        assert customers_models.AccountStatus.objects.filter(tenant=tenant).count() == before


# ══════════════════════════════════════════════════════════════════════════
# 2 · THE CLAUSE BR-CUS-107 FLAGS — A NON-BILLABLE ACCOUNT STILL PAYS
# ══════════════════════════════════════════════════════════════════════════
def test_br_cus_107__non_billable_does_not_suppress_payment():
    """*"A `non_billable` account MUST still accept a PAYMENT"* — BR-CUS-107.

    Paying is how a cut customer gets reconnected (BR-CUS-104), so if the class
    suppressed payment anywhere the ruling would be wrong in practice. It does
    not, and the reason is structural rather than a list: **payments never reads
    the account's status at all** (BR-PAY-036, PO 2026-08-11 verbatim —
    *"payment is always accepted - even it is disconnected and tagged to
    account"*).

    Asserted as an ABSENCE in the source, which is the only shape that survives
    a new status being added: a test that drove one status would say nothing
    about a sixth.
    """
    from apps.payments import services as payments_services

    source = inspect.getsource(payments_services)
    assert "account.status" not in source
    assert "status__" not in source
    for behavior_class in ("non_billable", "billable", "billable_base_only", "terminal"):
        assert behavior_class not in source, (
            f"{behavior_class!r} appears in apps/payments/services.py — a behaviour class "
            "reaching the money-taking path is how BR-PAY-036 gets broken"
        )


# ══════════════════════════════════════════════════════════════════════════
# 3 · MEASURED CONSEQUENCE ONE — THE UNIT STOPS BEING HELD
# ══════════════════════════════════════════════════════════════════════════
def test_br_cus_107__an_account_on_this_row_stops_occupying_its_unit(growth_plan, identity_seam):
    """⚠ **REPORTED, NOT RESOLVED — this test records a defect, not a design.**

    `OCCUPYING_BEHAVIOR_CLASSES` is (billable, billable_base_only), so the
    moment an account is moved onto `Disconnected` its unit reads VACANT: it
    becomes pickable for another move-in at an address the cut customer still
    holds, and the cut customer's own move-out is refused because only an
    OCCUPANT can move out.

    Two CONFIRMED rules say a cut account still occupies — `DSC-02.4` cuts
    *"leaving the account open"*, and BR-MET-036 flips a unit to Vacant when the
    account is **CLOSED**, which a cut account is not — so this reading is wrong
    for this row. It is measured rather than fixed because the fix moves a
    boundary ten call sites and the frontend key off, and that is a ruling plus
    a decision-log row, not a side effect of seeding a status.

    **This is why nothing assigns the status yet** (§5).
    """
    tenant, _ = provisioned_tenant()
    with tenant_ctx(tenant):
        unit = _unit_for(tenant)
        account = _account_for(tenant, unit=unit, status_code="active")

        occupant = customers_selectors.active_account_for_unit(unit.id)
        assert occupant is not None, "an active account holds its unit"

        cut_status = customers_models.AccountStatus.objects.get(tenant=tenant, code=RULED_CODE)
        account.status = cut_status
        account.save(update_fields=["status"])

        # THE MEASUREMENT. Not an assertion that this is right.
        assert customers_selectors.active_account_for_unit(unit.id) is None, (
            "BR-CUS-107 + OCCUPYING_BEHAVIOR_CLASSES: a cut account's unit reads VACANT. "
            "If this ever flips to a held unit, the occupancy boundary was ruled and this "
            "test should be rewritten to assert the ruling — not deleted."
        )
        assert customers_services.is_occupying(cut_status) is False


# ══════════════════════════════════════════════════════════════════════════
# 4 · MEASURED CONSEQUENCE TWO — BILLING DROPS THE ACCOUNT, NOT ITS BASE
# ══════════════════════════════════════════════════════════════════════════
def test_br_cus_107__billing_refuses_the_whole_account_not_only_its_base():
    """⚠ **REPORTED, NOT RESOLVED — the second thing to close before assigning.**

    BR-CUS-103 stops base at the cut, and it does so WITHOUT this status:
    `disconnects.service_off_windows` hands billing the dark days and
    `gather` subtracts them from `service_days`, which B4.3's frozen
    `service_days / cycle_days` factor already prorates by.

    Moving the account to `non_billable` does something else entirely — stage 1
    refuses the account outright, so `runs.calculate_account` records a
    NON-RETRYABLE break and the usage consumed BEFORE the cut is never billed.
    Worked: `A-11488` cut on 2026-08-18 inside a 1–31 August cycle has 18 billable
    days of service, and a run over a `non_billable` account bills none of them.
    """
    from apps.billing.contracts import AccountBillingData
    from apps.billing.exceptions import BillingRuleError
    from apps.billing.stages import resolve_subscription as stage

    assert RULED_CLASS in stage.BILLING_CLASSES, "the class is known to billing"
    assert RULED_CLASS not in stage.CLASSES_THAT_BILL, "and it produces no bill at all"

    data = AccountBillingData(
        account_id="00000000-0000-0000-0000-000000000001",
        account_no="A-11488",
        behavior_class=RULED_CLASS,
        currency="USD",
        tax_exempt=False,
        period_start=date(2026, 8, 1),
        period_end=date(2026, 8, 31),
        cycle_days=31,
        service_days=18,  # 1–18 August: the days it DID have service
        rate_plan_id="plan-1",
    )
    with pytest.raises(BillingRuleError) as excinfo:
        stage.resolve_subscription(data)
    assert "is not billed" in str(excinfo.value)


# ══════════════════════════════════════════════════════════════════════════
# 5 · THE STATUS IS ASSIGNED AT THE CUT (PO 2026-08-30, OQ-1170 CLOSED)
# ══════════════════════════════════════════════════════════════════════════
def test_br_cus_107__the_cut_writes_the_status_and_nothing_else_on_the_account():
    """`DSC-02.4`'s surviving prohibitions, and the status that now IS assigned.

    ⚠ **THIS TEST WAS `..._still_writes_no_account_row` AND IT ASSERTED THE
    OPPOSITE OF THE RULE, WHICH IS WHY IT IS RE-POINTED HERE (DEF-705).** It
    greped `commit_cut`'s body for `account.status`, `account.save`, `closed_at`
    and `deposit_on_file` and demanded all four be absent, and it read
    *"AND THAT IS WHY DEF-701 IS NOT CLOSED BY THIS LANDING"*.

    **PO ruling 2026-08-30 — the disconnect is the WHOLE event:** *"when we
    disconnect - we generate final bill at that time itself - so later bill is
    not required ... entire workflow including all settlement and status update
    is taken care at time of disconnect or move out - so account status changes
    and outstanding is pending on account if any"*. `OQ-1170` is CLOSED, DEF-701
    is closed with it, and BR-CUS-107's row is assigned at the cut.

    **`DSC-02.4` still has two real prohibitions and they are what this now
    guards:** *"Close the account or settle the deposit — that is a move-out,
    not a disconnect."* So `closed_at` and `deposit_on_file` are still absent
    from the cut, and the assertion is written over the SAME body-source read so
    a later lane cannot quietly widen the write.
    """
    from apps.customers import disconnects

    # The BODY, with the docstring removed — the docstring QUOTES `DSC-02.4`'s
    # prohibitions and a naive substring search over the whole source matches
    # the prose that promises the rule rather than the code that keeps it.
    body = _function_body_source(disconnects.commit_cut)
    for forbidden in ("closed_at", "deposit_on_file", "close_reason"):
        assert forbidden not in body, (
            f"`commit_cut` writes {forbidden!r} — `DSC-02.4`'s first prohibition is "
            "*'Close the account or settle the deposit — that is a move-out, not a "
            "disconnect'*, and the PO's ruling of 2026-08-30 is explicit that the cut "
            "*'leaves the account open'*. The STATUS is the only `accounts` column a cut "
            "may move."
        )

    # And the status write itself is delegated to ONE named helper, so there is
    # exactly one place in this module that can touch `accounts.status`.
    assert "_write_disconnected_status(account)" in body
    # ⚠ `_function_body_source` UNPARSES the AST, so it normalises quoting —
    # asserting on a literal source string would compare this file's quote style
    # to `ast.unparse`'s and fail for a reason that has nothing to do with the
    # rule. The columns are what matter, so the columns are what is asserted.
    status_writer = _function_body_source(disconnects._write_disconnected_status)
    assert "update_fields=[" in status_writer
    assert "'status'" in status_writer and "'updated_at'" in status_writer
    for forbidden in ("closed_at", "deposit_on_file"):
        assert forbidden not in status_writer

    ruling = disconnects.DISCONNECTED_STATUS_ASSIGNED
    assert ruling["code"] == "disconnected_status_assigned_at_the_cut"
    assert "BR-CUS-107" in ruling["br_ref"]
    assert "2026-08-30" in ruling["br_ref"]
    # …and the one case where it is deliberately NOT written keeps its name.
    held = disconnects.CUT_BILL_BLOCKED_SO_STATUS_HELD
    assert held["code"] == "cut_bill_blocked_status_not_written"


def _function_body_source(func) -> str:
    """`inspect.getsource` minus the docstring — see the caller for why."""
    import ast
    import textwrap

    tree = ast.parse(textwrap.dedent(inspect.getsource(func)))
    node = tree.body[0]
    statements = node.body
    if (
        statements
        and isinstance(statements[0], ast.Expr)
        and isinstance(statements[0].value, ast.Constant)
        and isinstance(statements[0].value.value, str)
    ):
        statements = statements[1:]
    return "\n".join(ast.unparse(statement) for statement in statements)
