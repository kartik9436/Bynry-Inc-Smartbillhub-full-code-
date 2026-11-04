# ── Trace ──────────────────────────────────────────────
# Change:  CR-142-BRC07 — the Reports Build Brief, Phase 0 task `P0.18`, and
#          §7.2.4 *"As-was or as-is"*, RULED — OPTION (b).
#          Outcome, verbatim: *"Moving account 100244 to Small Commercial
#          leaves July readable as Residential."*
# Rules:   CLAUDE.md hard rule 1 (tenant scoping) · hard-won law 14 (a failed
#          statement poisons a PostgreSQL transaction; the suite is SQLite) ·
#          BR-REP-024 (name the gap, never substitute a value)
# ───────────────────────────────────────────────────────
"""THE BRIEF'S OWN WORKED CASE, RUN.

⚠ **WHAT THIS FILE CANNOT PROVE, STATED BESIDE WHAT IT CAN** (hard-won law 7's
fifth shape). The RLS policy on this table is `customers/0073` and **is not
exercised here at all** — `config/settings/test.py` hardcodes in-memory SQLite,
which has no row-level security, so every isolation assertion would pass by
vacuum. That half is
`06-backend/tests/test_cr142_p0_10_reports_rls_pg.py`, which refuses to run
anywhere but PostgreSQL. What IS proved here is the arithmetic of the window
and the behaviour of the recorder.
"""

from __future__ import annotations

from datetime import date

import pytest

from apps.customers import attribute_history
from apps.customers import models as customer_models
from apps.customers.attribute_history_models import AccountAttributeHistory

from tests.test_us_met_helpers import *  # noqa: F401,F403 — brazos · dana
from tests.test_us_met_helpers import make_premises, make_unit, tenant_ctx

pytestmark = [pytest.mark.django_db]

JULY = date(2026, 7, 1)
SEPTEMBER = date(2026, 9, 1)


def _account(actor, tenant):
    premises = make_premises(actor, address_line="100244 Bluestem Ln", services_available=["electric"])
    unit = make_unit(actor, premises["id"], label="Unit A", services=["electric"])
    return customer_models.Account.objects.create(
        tenant=tenant,
        unit_id=unit["id"],
        status=customer_models.AccountStatus.objects.filter(tenant=tenant).first(),
        account_type=customer_models.AccountType.objects.filter(tenant=tenant).first(),
        account_no="A-100244",
    )


def _subtype(tenant):
    return customer_models.AccountSubtype.objects.filter(tenant=tenant).first()


def test_p0_18_july_stays_readable_after_a_september_move(brazos, dana):
    """The brief's sentence, as arithmetic.

    July's row keeps July's values; September's row carries the new sub-type;
    and a question dated in July reads the first one.
    """
    with tenant_ctx(brazos):
        account = _account(dana, brazos)
        was = account.account_type
        first = attribute_history.record(account, on=JULY)
        assert first is not None

        account.account_subtype = _subtype(brazos)
        account.save(update_fields=["account_subtype"])
        second = attribute_history.record(account, on=SEPTEMBER)
        assert second is not None and second.pk != first.pk

        in_july = attribute_history.as_was(account.pk, on=date(2026, 7, 14))
        assert in_july is not None
        assert in_july.account_type_id == was.pk
        assert in_july.account_subtype_id is None, (
            "July must still read as the account was IN JULY. A sub-type here "
            "means the read followed the account's current column."
        )

        now = attribute_history.as_was(account.pk, on=date(2026, 9, 14))
        assert now is not None and now.account_subtype_id == _subtype(brazos).pk


def test_p0_18_the_window_is_half_open_and_the_boundary_day_belongs_to_the_new_row():
    """`[from, to)` — the off-by-one that would count one account twice."""
    assert True  # asserted in the case below, against real rows


def test_p0_18_the_boundary_day_is_the_new_periods(brazos, dana):
    with tenant_ctx(brazos):
        account = _account(dana, brazos)
        attribute_history.record(account, on=JULY)
        account.account_subtype = _subtype(brazos)
        account.save(update_fields=["account_subtype"])
        attribute_history.record(account, on=SEPTEMBER)

        on_the_day = attribute_history.as_was(account.pk, on=SEPTEMBER)
        assert on_the_day is not None
        assert on_the_day.effective_from == SEPTEMBER, (
            "1 September belongs to the period that BEGAN on it. A closed "
            "window ending on the 1st must not also contain the 1st, or a "
            "month-end report counts this account in both months."
        )
        day_before = attribute_history.as_was(account.pk, on=date(2026, 8, 31))
        assert day_before is not None and day_before.effective_from == JULY


def test_p0_18_an_unchanged_save_writes_no_row(brazos, dana):
    """A table with one row per PATCH is a list of edits, not a history."""
    with tenant_ctx(brazos):
        account = _account(dana, brazos)
        attribute_history.record(account, on=JULY)
        assert attribute_history.record(account, on=SEPTEMBER) is None
        assert AccountAttributeHistory.objects.filter(account=account).count() == 1


def test_p0_18_two_changes_on_one_day_collapse(brazos, dana):
    """Same-day changes update the open row — a zero-day window contains no date."""
    with tenant_ctx(brazos):
        account = _account(dana, brazos)
        attribute_history.record(account, on=JULY)
        account.account_subtype = _subtype(brazos)
        account.save(update_fields=["account_subtype"])
        attribute_history.record(account, on=SEPTEMBER)
        other = customer_models.AccountStatus.objects.filter(tenant=brazos).last()
        account.status = other
        account.save(update_fields=["status"])
        attribute_history.record(account, on=SEPTEMBER)
        assert AccountAttributeHistory.objects.filter(account=account).count() == 2
        assert attribute_history.as_was(account.pk, on=SEPTEMBER).status_id == other.pk


def test_p0_18_a_date_before_recording_began_answers_none_not_the_current_row(brazos, dana):
    """BR-REP-024 in one assertion: a stated absence, never a substituted value.

    ⚠ This is the case that keeps the honest half of the ruling honest. The
    brief: *"Where it does not — anything before the table ships — it falls
    back to as-is and SAYS SO ON THE FACE OF THE REPORT."* A helper that
    returned the current row here would make that sentence unwritable, because
    the report would have no way to tell the two apart.
    """
    with tenant_ctx(brazos):
        account = _account(dana, brazos)
        attribute_history.record(account, on=JULY)
        assert attribute_history.as_was(account.pk, on=date(2026, 6, 30)) is None


def test_p0_18_backdating_is_refused_by_name(brazos, dana):
    """Not built, and it says so rather than failing at the database."""
    with tenant_ctx(brazos):
        account = _account(dana, brazos)
        attribute_history.record(account, on=SEPTEMBER)
        account.account_subtype = _subtype(brazos)
        account.save(update_fields=["account_subtype"])
        with pytest.raises(ValueError, match="backdate"):
            attribute_history.record(account, on=JULY)


def test_p0_18_no_document_or_docstring_claims_the_audit_log_is_permanent():
    """CLAUDE.md hard rule 4's closing clause, asserted rather than trusted.

    `audit_log` has ONE retention rule and no row type is exempt (PO ruling
    2026-09-23, verbatim: *"keep the same rule s; when audit log is delete - it
    is deleted thats okay"*), so **no document, screen or docstring may
    describe that path as a permanent record of an old value**. The two files
    this task adds are the ones most tempted to, because the whole argument for
    them is what `audit_log` cannot do.
    """
    import pathlib

    from apps.customers import attribute_history as service
    from apps.customers import attribute_history_models as model

    for module in (service, model):
        text = pathlib.Path(module.__file__).read_text().lower()
        assert "pruned" in text, f"{module.__name__} must state that audit_log is pruned"
        for forbidden in ("permanent record", "permanently record", "kept forever", "never deleted"):
            assert forbidden not in text, (
                f"{module.__name__} claims `{forbidden}`. CLAUDE.md hard rule 4: "
                "audit_log has one retention rule and no row type is exempt."
            )


# ── Lifecycle ─────────────────────────────────────────────
# packet: CR-142-BRC07 P0.18 (05-prototype/09 Reports Build Brief.pdf p9 + §7.2.4 p85-86)
# screens: none
# generated: 2026-09-26 by lane REP-P0B
# checklist: A✔ B=n/a C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-09)
# gates: RED PROVED FIRST — every case failed on `ModuleNotFoundError: apps.customers.attribute_history` before the module existed.
# exceptions: (1) the RLS half of this table is NOT tested here and the docstring says so with the file that does test it — SQLite has no row-level security and a probe here would pass by vacuum (law 7)
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
