# ── Trace ──────────────────────────────────────────────
# Epics:    EP-BIL-01 (bill run — the holiday input to the late-fee grace clock)
#           Screens: S63 (Settings → Holiday calendar, where the rows are kept)
#           NOTE: no US-ID is cited here ON PURPOSE — same reason
#           apps/billing/tenancy_seam.py and late_fee.py state.
# Rules:    BR-TEN-013 (cross-module reads resolve the owner's published
#           callable; billing never touches tenancy's ORM) · BR-TEN-039 (the
#           holiday calendar is tenant Reference data, S63) · BR-BIL-002
#           (business-day grace) · BR-BIL-008 (grace length is tenant config)
# Tests:    this file
# Impacts:  apps/billing/tenancy_seam.py · apps/billing/late_fee.py
# ───────────────────────────────────────────────────────
"""The billing→tenancy holiday seam: does the READ produce what the CLOCK needs.

`test_gt08_late_fee_grace.py` pins the clock with hand-built date sets. This
file pins the other half — that the dates actually reaching that clock from the
tenant's own S63 calendar are `datetime.date` objects and not the ISO strings
tenancy's screen payload carries.

That distinction is the entire failure mode this file exists to catch:

    date(2026, 12, 25) in {"2026-12-25"}   ->  False

A seam that forwarded tenancy's payload unparsed would skip no holidays at all,
silently, while every clock test stayed green — because the clock tests build
their own `date` sets and never touch the seam. The last test here closes that
loop end to end: rows in the database, read through the seam, into
`assess_late_fee`, landing on the PO's ruled Tue 5 Jan 2027.
"""

from datetime import date
from decimal import Decimal

import pytest
from django.db import connection as db_connection

from apps.billing import tenancy_seam
from apps.billing.exceptions import BillingConfigError
from apps.billing.services import assess_late_fee
from apps.tenancy.models import HolidayCalendar, Tenant
from core import tenancy as core_tenancy

pytestmark = pytest.mark.django_db

# GT-8's inputs (the frozen FIGURE itself is asserted in tests/golden/).
OVERDUE = Decimal("542.10")
PERCENT = Decimal("0.015")
MINIMUM = Decimal("5")

CHRISTMAS = date(2026, 12, 25)
NEW_YEAR = date(2027, 1, 1)


class _FakeCursor:
    """Records the `set_config` BE-01 would issue; sqlite cannot run it."""

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def execute(self, sql, params=None):
        return None


class _FakeConnection:
    def cursor(self):
        return _FakeCursor()


@pytest.fixture(autouse=True)
def _tenant_guc(monkeypatch):
    """`app.tenant_id` is a Postgres GUC and the test DB is sqlite.

    The same shim `tests/test_us_idn_helpers.py` uses: on a non-Postgres DB the
    kernel's `set_config` call is recorded instead of run, so the Python-side
    tenant mirror still works and tenancy's read still filters on it. What only
    a real Postgres can prove — RLS actually DENYING a cross-tenant row — is the
    G5 isolation suite's job, not this file's, and is deliberately not claimed
    here.
    """
    if db_connection.vendor != "postgresql":
        monkeypatch.setattr(core_tenancy, "connection", _FakeConnection())
    yield
    core_tenancy._current_tenant.set(None)


@pytest.fixture()
def brazosbend():
    return Tenant.objects.create(name="Brazos Bend Utilities", subdomain="brazosbend")


@pytest.fixture()
def lonestarridge():
    return Tenant.objects.create(name="Lone Star Ridge Water Co-op", subdomain="lonestarridge")


def _holiday(tenant, day, label):
    return HolidayCalendar.objects.create(tenant=tenant, holiday_date=day, label=label)


def test_holiday_dates_are_real_dates_not_iso_strings(brazosbend):
    """The seam's whole reason to exist: tenancy's payload is ISO strings.

    `apps.tenancy.selectors.holidays()` is shaped for the S63 screen and carries
    `"date": "2026-12-25"`. The grace clock walks a `datetime.date` cursor, so a
    forwarded string matches nothing and skips nothing — the fee then lands ON
    the holiday, which is the behaviour the PO ruled against on 2026-08-11.
    """
    _holiday(brazosbend, CHRISTMAS, "Christmas Day")
    _holiday(brazosbend, NEW_YEAR, "New Year's Day")

    with core_tenancy.tenant_context(brazosbend.id):
        holidays = tenancy_seam.holiday_dates()

    assert all(isinstance(day, date) for day in holidays)
    # The membership test the clock actually performs. This assertion is the
    # guard: it is False for every element of the raw ISO-string payload.
    assert CHRISTMAS in holidays
    assert NEW_YEAR in holidays
    assert holidays == frozenset({CHRISTMAS, NEW_YEAR})


def test_holiday_dates_are_scoped_to_the_current_tenant(brazosbend, lonestarridge):
    """CLAUDE.md hard rule 1 — one tenant's calendar never bills another's.

    The seam adds no query of its own; it inherits tenancy's tenant-filtered
    read (and RLS FORCE behind it). Asserted rather than assumed, because a
    holiday leaking across tenants would move real money by days.
    """
    _holiday(brazosbend, CHRISTMAS, "Christmas Day")
    _holiday(lonestarridge, date(2026, 7, 4), "Independence Day")

    with core_tenancy.tenant_context(brazosbend.id):
        assert tenancy_seam.holiday_dates() == frozenset({CHRISTMAS})
    with core_tenancy.tenant_context(lonestarridge.id):
        assert tenancy_seam.holiday_dates() == frozenset({date(2026, 7, 4)})


def test_an_empty_calendar_is_an_empty_set_and_not_a_refusal(brazosbend):
    """A tenant that keeps no holidays is a legitimate, ordinary answer.

    Nothing is seeded into this table by this product (no signed document names
    a default holiday set), so an empty calendar is in fact the state every new
    tenant starts in. It must read as "none", not as an error.
    """
    with core_tenancy.tenant_context(brazosbend.id):
        assert tenancy_seam.holiday_dates() == frozenset()


def test_an_unpublished_tenancy_read_refuses_rather_than_billing_on_no_holidays(monkeypatch):
    """Hard-won law 3 — "unreachable" must not quietly become "none".

    Returning an empty set here would reinstate exactly the Mon–Fri behaviour
    the PO ruled against, for every caller, with no signal at all.
    """
    monkeypatch.setattr(tenancy_seam, "_resolve", lambda *a, **k: None)
    with pytest.raises(BillingConfigError, match="not.*published"):
        tenancy_seam.holiday_dates()


def test_an_unreadable_holiday_row_refuses_rather_than_being_dropped(monkeypatch):
    """A date shape the seam does not understand is never coerced to "no holiday".

    Silently dropping the row would charge the fee early on exactly the day the
    tenant configured to be protected.
    """
    monkeypatch.setattr(tenancy_seam, "_resolve", lambda *a, **k: lambda: [{"date": "25/12/2026"}])
    with pytest.raises(BillingConfigError, match="not an\nISO date|not an ISO date"):
        tenancy_seam.holiday_dates()

    monkeypatch.setattr(tenancy_seam, "_resolve", lambda *a, **k: lambda: [{"date": 20261225}])
    with pytest.raises(BillingConfigError, match="int where a"):
        tenancy_seam.holiday_dates()


def test_the_po_worked_case_end_to_end_through_the_seam(brazosbend):
    """PO ruling 2026-08-11, from stored rows rather than a hand-built set.

    Bill due Thu 24 Dec 2026, 5 business days' grace, with Christmas Day and
    New Year's Day in THIS TENANT's S63 calendar:

      Mon-Fri only : Fri 25 (Christmas) · Mon 28 · Tue 29 · Wed 30 · Thu 31
                     -> fee charged Fri 1 Jan, NEW YEAR'S DAY
      holiday-aware: Mon 28 · Tue 29 · Wed 30 · Thu 31 · Mon 4 Jan
                     -> fee charged Tue 5 Jan

    `test_gt08_late_fee_grace.py` proves the clock does this with a set someone
    typed. This proves the tenant's real rows get there intact — the half a
    parsing bug would break while that file stayed green.
    """
    _holiday(brazosbend, CHRISTMAS, "Christmas Day")
    _holiday(brazosbend, NEW_YEAR, "New Year's Day")

    with core_tenancy.tenant_context(brazosbend.id):
        holidays = tenancy_seam.holiday_dates()

    def charged_on(as_of):
        return assess_late_fee(
            overdue_amount=OVERDUE,
            percent=PERCENT,
            minimum=MINIMUM,
            due_date=date(2026, 12, 24),
            as_of=as_of,
            grace_days=5,
            grace_mode="business",
            holidays=holidays,
        )

    assert charged_on(NEW_YEAR) == Decimal("0.00")  # NOT on New Year's Day
    assert charged_on(date(2027, 1, 4)) == Decimal("0.00")  # last grace day
    assert charged_on(date(2027, 1, 5)) == Decimal("8.13")  # Tue 5 Jan, as ruled


def test_the_seam_never_imports_tenancys_orm():
    """B1/BR-TEN-013 asserted as an absence, not as a comment.

    The boundary rule is that billing resolves tenancy's published callable at
    call time. A future edit that reached for `apps.tenancy.models` directly
    would be a boundary violation no other gate in this repo would catch, so it
    is caught here.
    """
    import inspect

    source = inspect.getsource(tenancy_seam)
    assert "apps.tenancy.models" not in source
    assert "from apps.tenancy" not in source
    assert "import_module" in source  # resolved, not imported

    # And the module really does hold no Django model reference at runtime.
    assert not [name for name in vars(tenancy_seam) if name.endswith("Calendar")]


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-BIL-002@70a0044 (carried from apps/billing/late_fee.py, the module
#         this seam feeds; no new frozen source is involved)
# generated: 2026-08-11 by story-coder (late-fee holiday lane — PO ruling 2026-08-11 option A)
# checklist: A✔ B✔ C✔ D=deferred(not an API surface) E=deferred(no-frontend-half) F✔ G✔ H=deferred(PO 2026-08-09)
# gates: ruff✔ black✔ · pytest tests/test_bil_holiday_seam.py 7 passed✔ · RED PROOF EXECUTED 2026-08-11, measured `4 failed, 3 passed in 12.51s` when the seam forwards tenancy's raw ISO payload — full output quoted in apps/billing/tenancy_seam.py's trailer
# exceptions: sqlite test DB, so tenant scoping is asserted through tenancy's tenant-filtered read rather than through live RLS denial; the RLS half is the G5 isolation suite's (holiday_calendars carries FORCE policies in db/rls_tenancy_w0.sql) — REPORTED, the same split every W0 model test carries
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
