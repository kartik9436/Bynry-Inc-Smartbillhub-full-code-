# ── Trace ──────────────────────────────────────────────
# Story:    US-PAY-001 (POST /accounts/{id}/payments — the S22/S35 Record modal,
#           whose date field collects a CALENDAR DAY) · US-PAY-005 (S32 summary,
#           whose "today" tile buckets money by day) · US-PAY-004 (the S33
#           ledger, whose date filters must select the same rows the tile counts)
#           Screens: S22 · S32 · S33 · S35
# Rules:    BR-TEN-081 (a typed posting DATE becomes midnight in the UTILITY'S
#           OWN timezone — PO 2026-08-12, OQ-153 CLOSED) · BR-TEN-020 (regional
#           settings are display-time transforms; storage stays UTC) ·
#           BR-TEN-043 (event time is an INPUT, never a clock) · BR-PAY-021 (the
#           posting date is what the on-time test reads) · BR-PAY-033 (the
#           posting date is USER-ENTERED) · BR-PAY-027 (S32's counts tie to S33's
#           lists EXACTLY) · BR-TEN-013 (a module never touches another's ORM —
#           the zone is read through the seam)
# Defect:   DEF-094 — "Closing the timezone defect does NOT make the midnight
#           rule live — the WRITE half still anchors at midnight UTC"
# Tests:    this file
# Impacts:  apps/payments/api._moment (the named fix) ·
#           apps/payments/settings_seam.tenant_timezone (the seam) ·
#           apps/tenancy/selectors.tenant_timezone (the ONE derivation) ·
#           apps/payments/summary._day_bounds · apps/payments/selectors._day_bounds
#           (the sweep)
# ───────────────────────────────────────────────────────
"""DEF-094 — a CLOSED DEFECT that claimed a guarantee it had not delivered.

**THE SHAPE, which is the transferable part.** Hard-won law 1 says a comment
claiming a guarantee is not the guarantee. This is that law one level up: a
CLOSED DEFECT claiming one. DEF-082 closed *"the timezone dropdown"* and built
the READ half — `tenant_today()` reads the tenant's zone, proved by moving the
answer across a date boundary. Anyone reading "DEF-082 fixed" would reasonably
conclude BR-TEN-081 was honoured. **It was not.** `apps/payments/api._moment`
went on anchoring a bare `YYYY-MM-DD` at midnight **UTC** — and said so in its
own docstring — so the two halves of one rule were each internally consistent
and disagreed with each other by a day.

**THE WORKED CASE, and it is the PO's own.** A Houston clerk (`America/Chicago`,
UTC−5 in August) types **22 August** on the S22 Record form:

    stored, before this fix   2026-08-22T00:00:00Z   = 21 Aug 19:00 Central
    read back by every screen 21 August              (through `tenant_today`'s zone)
    stored, after this fix    2026-08-22T05:00:00Z   = 22 Aug 00:00 Central
    read back by every screen 22 August              ✔

**WHAT A ONE-DAY SHIFT COSTS, in this product's own rules.** BR-PAY-021's
on-time test is `posted_at <= due_date`, so a day backwards clears a late fee
that was owed and a day forwards charges one that was not (BR-BIL-001, over a
**$25.00** floor). BR-PAY-025 allows exactly ONE deposit batch per day per
method, so the money lands on the wrong drawer day and BR-REP-013 reports it
there. At a month edge it is the wrong month's books.

**THE SWEEP IS PART OF THE FIX AND IS ASSERTED HERE.** DEF-094 asks for *"every
other bare-date anchor on a money path"*. The three in payments — the write
anchor, the S32 day/month bounds and the S33 date filters — are covered by the
cases below. The two OUTSIDE payments are REPORTED and not touched, in the
lane report and in `12-governance/02-decision-log.md`, because they are in
other lanes' live files: `apps/billing/selectors._day_bounds` (which already
reports its own caveat) and `apps/ledger/finance_api._moment`, which is a NEW
file this session carrying the identical `replace(tzinfo=utc)` shape.
"""

import uuid
from datetime import date, datetime, time, timezone as dt_timezone
from decimal import Decimal
from zoneinfo import ZoneInfo

import pytest

from apps.payments import models, selectors, settings_seam, summary
from apps.payments.exceptions import PaymentRuleError
from apps.tenancy import services as tenancy_services

from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import FakeUser, tenant_ctx  # noqa: F401
from tests.test_us_pay_001_record_payment import PE1_CHECK, an_issued_bill, pe1_bills  # noqa: F401
from tests.test_us_pay_004_payments_api import record
from tests.test_w3_billing_models import an_account

pytestmark = pytest.mark.django_db

#: The utility in DEF-094's own example. UTC−5 in August (CDT).
HOUSTON = "America/Chicago"
#: The calendar day the clerk types into the S22 date field.
TYPED_DAY = "2026-08-22"
TYPED_DATE = date(2026, 8, 22)
#: What the clerk MEANS: 22 Aug 00:00 Central.
MEANT = datetime(2026, 8, 22, 0, 0, tzinfo=ZoneInfo(HOUSTON))
#: What the code STORED before this fix, and it is a different instant.
STORED_BEFORE = datetime(2026, 8, 22, 0, 0, tzinfo=dt_timezone.utc)


def houston(actor):
    """Put the tenant on Central through tenancy's OWN service — never a column
    write. The point of DEF-082's fix is that a human's choice is what is read,
    so a test that set the column directly would prove the wrong thing."""
    tenancy_services.save_regional_settings(actor, {"timezone": HOUSTON})


# ═══════════════════════════════════════════════════════════════════════════
# THE WRITE HALF — the fix DEF-094 names
# ═══════════════════════════════════════════════════════════════════════════
def test_def_094__a_typed_date_is_midnight_in_the_utilitys_zone_not_utc(brazos, marcus, dana):
    """**THE CASE THE DEFECT WAS WRITTEN FOR.** 22 August means 22 August.

    The clerk types `2026-08-22`. It is stored as **22 Aug 00:00 Central** —
    `2026-08-22T05:00:00Z` — and NOT as `2026-08-22T00:00:00Z`, which is 21 Aug
    19:00 Central and is what every screen would have called *21 August*.

    The instant is asserted, not just the date: `.date()` on the stored value is
    05:00 UTC's date either way, which is precisely why the old behaviour passed
    `test_us_pay_001_tc2` for months. **A test that only reads `.date()` on a
    UTC-stored timestamp cannot see this defect at all.**
    """
    with tenant_ctx(brazos):
        houston(dana)
        account = an_account(marcus, brazos)
        pe1_bills(brazos, account)

        response = record(brazos, marcus.user, account, posted_at=TYPED_DAY, cleared_at=TYPED_DAY)
        payment = models.Payment.objects.get(pk=response.data["id"])

        assert payment.posted_at == MEANT, "the clerk's midnight, in the clerk's zone"
        assert payment.posted_at != STORED_BEFORE, "which is NOT midnight UTC — DEF-094"
        assert payment.posted_at.astimezone(dt_timezone.utc).hour == 5, "CDT is UTC−5"
        # The day the utility reads it back as — the half DEF-082 already fixed.
        assert payment.posted_at.astimezone(ZoneInfo(HOUSTON)).date() == TYPED_DATE


def test_def_094__the_two_halves_of_the_rule_now_agree(brazos, marcus, dana):
    """The stored instant and the displayed day are the same day. That is the rule.

    DEF-094's finding is not "UTC is wrong" — it is that the WRITE half and the
    READ half each behaved reasonably and disagreed. So the assertion is the
    agreement itself, made through the two real functions: the payment is
    recorded through the endpoint, and the day is read back through the same
    zone `apps.tenancy.selectors.tenant_today()` uses.
    """
    with tenant_ctx(brazos):
        houston(dana)
        account = an_account(marcus, brazos)
        pe1_bills(brazos, account)

        # Read BEFORE the endpoint call: `api_call` establishes and then clears
        # its own tenant context, so a seam read after it has none — the same
        # reason every other endpoint case in this suite reads its facts first.
        zone = settings_seam.tenant_timezone()
        assert zone == ZoneInfo(HOUSTON)

        response = record(brazos, marcus.user, account, posted_at=TYPED_DAY)
        payment = models.Payment.objects.get(pk=response.data["id"])
        assert payment.posted_at.astimezone(zone).date() == TYPED_DATE

        # And under the OLD anchor the same payment reads as the day before —
        # the defect, computed rather than remembered.
        assert STORED_BEFORE.astimezone(zone).date() == date(2026, 8, 21)


def test_def_094__an_instant_that_states_its_own_offset_is_left_alone(brazos, marcus, dana):
    """A full ISO instant is not anchored — it already has an answer.

    Only a value carrying NO offset is missing one. An integration posting
    `2026-08-22T10:30:00-05:00` means that instant, and a layer that re-anchored
    it would be overriding a caller who was explicit. Asserted because the fix
    could so easily have been applied one line too widely.
    """
    with tenant_ctx(brazos):
        houston(dana)
        account = an_account(marcus, brazos)
        pe1_bills(brazos, account)

        response = record(brazos, marcus.user, account, posted_at="2026-08-22T10:30:00-05:00")
        payment = models.Payment.objects.get(pk=response.data["id"])
        assert payment.posted_at == datetime(
            2026, 8, 22, 15, 30, tzinfo=dt_timezone.utc
        ), "the caller's own offset, untouched"


def test_def_094__a_tenant_with_no_zone_still_records_and_lands_on_utc(brazos, marcus, dana):
    """UTC for an unset zone is a real answer, not a silent default.

    Provisioning prefills the zone from the signup state and leaves it NULL only
    when the state is unknown. That tenant's screens render every date in UTC
    (`tenant_today()` falls back the same way, through the SAME function), so
    anchoring their typed dates in UTC is what keeps the day they see equal to
    the day that was stored — which is the whole property BR-TEN-081 protects.
    Refusing here instead would stop a real utility recording a real payment
    over a setting they were never required to pick.
    """
    with tenant_ctx(brazos):
        tenancy_services.save_regional_settings(dana, {"timezone": None})
        account = an_account(marcus, brazos)
        pe1_bills(brazos, account)

        assert settings_seam.tenant_timezone() == ZoneInfo("UTC")

        response = record(brazos, marcus.user, account, posted_at=TYPED_DAY)
        payment = models.Payment.objects.get(pk=response.data["id"])
        assert payment.posted_at == STORED_BEFORE


def test_def_094__an_unwired_seam_refuses_and_never_quietly_anchors_utc(
    brazos, marcus, dana, monkeypatch
):
    """The seam REPORTS that it cannot answer. It never answers midnight UTC.

    Two different situations that a lazy implementation collapses into one:
    a tenant with **no zone** (tenancy answers UTC — a real answer, asserted
    above) and a **seam that cannot answer at all** (tenancy publishes no
    `tenant_timezone`). Defaulting to UTC in the second case would re-create
    DEF-094 exactly, in the one place nobody would ever look — a wiring failure
    wearing the shape of a working feature (hard-won law 2).
    """
    from apps.tenancy import selectors as tenancy_selectors

    monkeypatch.delattr(tenancy_selectors, "tenant_timezone", raising=True)
    with tenant_ctx(brazos):
        with pytest.raises(PaymentRuleError) as refusal:
            settings_seam.tenant_timezone()
    assert "tenant_timezone" in str(refusal.value)
    assert "DEF-094" in str(refusal.value) or "midnight UTC" in str(refusal.value)


# ═══════════════════════════════════════════════════════════════════════════
# THE SWEEP — every other bare-date anchor on a money path, in payments
# ═══════════════════════════════════════════════════════════════════════════
def test_def_094__the_summary_day_buckets_money_in_the_utilitys_own_day(brazos, marcus, dana):
    """S32's *today* tile counts an evening payment on the day the clerk means.

    **The case UTC bounds got wrong, worked:** a payment posted at **22 Aug
    20:00 Central** is `2026-08-23T01:00Z`. A UTC day window put it in the 23rd
    — every Houston utility's evening takings on the wrong day, every day. At a
    month edge that is the wrong month's books, which is exactly what DEF-094
    says a shifted date costs.
    """
    evening = datetime(2026, 8, 22, 20, 0, tzinfo=ZoneInfo(HOUSTON))
    with tenant_ctx(brazos):
        houston(dana)
        account = an_account(marcus, brazos)
        pe1_bills(brazos, account)

        from apps.payments import services

        services.record_payment(
            marcus,
            account_id=account.pk,
            amount=PE1_CHECK,
            posted_at=evening,
            cleared_at=evening,
            confirmation="8842",
            idempotency_reference=uuid.uuid4(),
        )

        start, end = summary._day_bounds(TYPED_DATE)
        assert start == MEANT, "the day starts at the utility's midnight"
        assert start <= evening <= end, "and the evening payment is inside it"

        view = summary.summary(as_of=TYPED_DATE)
        assert view.today["count"] == 1
        assert Decimal(view.today["amount"]) == PE1_CHECK

        # Under the OLD bounds the same payment fell out of the day entirely —
        # computed here rather than asserted from memory.
        utc_end = datetime.combine(TYPED_DATE, time.max, tzinfo=dt_timezone.utc)
        assert evening > utc_end, "which is why the tile used to miss it"


def test_def_094__the_list_filter_selects_the_same_day_the_tile_counts(brazos, marcus, dana):
    """BR-PAY-027: *"counts tie to lists EXACTLY"* — including at midnight.

    The S32 tile links to the S33 list. A tile bucketed in the tenant's day
    beside a list filtered in UTC's day is two screens disagreeing about the
    same money, and the clerk is sent looking for a payment the tile insists
    exists. The filter bound is the same midnight the tile uses.
    """
    with tenant_ctx(brazos):
        houston(dana)
        assert selectors._day_bounds(TYPED_DAY) == MEANT
        assert selectors._day_bounds(TYPED_DAY) == summary._day_bounds(TYPED_DATE)[0]
        # BR-SHL-011 is untouched: a malformed bound is still ignored, never a 4xx.
        assert selectors._day_bounds("not-a-date") is None
        assert selectors._day_bounds("") is None


def test_def_094__the_tenant_zone_has_exactly_one_derivation(brazos, marcus, dana):
    """`tenant_today()` and the payments seam read the SAME function.

    A second copy of the zone-resolution rule is how DEF-094 happened: two
    halves, each reasonable, drifting apart. So the read half and the write half
    are wired to one callable, and this asserts the wiring rather than the
    behaviour — behaviour tests pass on two copies that happen to agree today.
    """
    from apps.tenancy import selectors as tenancy_selectors

    with tenant_ctx(brazos):
        houston(dana)
        assert settings_seam.tenant_timezone() is not None
        assert settings_seam.tenant_timezone() == tenancy_selectors.tenant_timezone()

        import inspect

        source = inspect.getsource(tenancy_selectors.tenant_today)
        assert "tenant_timezone()" in source, "tenant_today reads the one derivation"
        assert "ZoneInfo(" not in source, "and does not resolve a zone of its own"


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-PAY-001@e9d5a48 (sources, in order: 12-governance/10-defect-log.csv DEF-094 + DEF-082 · 12-governance/01-open-questions.md OQ-153 CLOSED · 04-docs/05-modules/01-tenancy/06-epics/EP-TEN-05-company-settings.md BR-TEN-081 · 04-docs/05-modules/08-payments/02-business-rules.md BR-PAY-021/025/027/033)
# generated: 2026-08-15 by the money-correctness lane (DEF-094)
# checklist: A✔ B✔ C✔ D✔ E=deferred(no-frontend-half — the named it.todo in the frontend test is the other lane's to retire) F✔ G✔ H=deferred(PO 2026-08-09)
# gates: PROVED RED BEFORE GREEN on live PostgreSQL — with `_moment` anchoring
#         at midnight UTC again, this file's first case fails
#         `assert datetime.datetime(2026, 8, 22, 0, 0, tzinfo=datetime.timezone.utc) ==
#         datetime.datetime(2026, 8, 22, 0, 0, tzinfo=zoneinfo.ZoneInfo(key='America/Chicago'))`
#         — the two instants five hours apart, which IS the defect
# exceptions: the stored INSTANT is asserted and not only its `.date()`, because
#         `.date()` on a UTC-stored value is the same either way — which is
#         exactly why `test_us_pay_001_tc2` passed throughout the defect's life ·
#         the UTC fallback for a tenant with NO zone is asserted as CORRECT
#         rather than treated as a gap: tenancy answers UTC, every screen renders
#         UTC, and the day seen equals the day stored, which is the property the
#         rule protects · two bare-date anchors OUTSIDE payments are REPORTED and
#         not touched (apps/billing/selectors._day_bounds and the new
#         apps/ledger/finance_api._moment), both in other lanes' live files
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
