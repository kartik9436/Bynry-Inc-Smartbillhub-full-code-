# ── Trace ──────────────────────────────────────────────
# Story:    US-LED-011 (the S57 manual journal entry over HTTP — TC-1 the
#           draft, TC-2 the post, TC-4 the unbalanced entry and the empty memo,
#           TC-6 the deleted draft, TC-7 another tenant's entry) ·
#           US-LED-012 (the accrual auto-reversal — TC-1 the mirror, TC-3 the
#           links, TC-5 no suppress path) · US-LED-013 (reverse + repost)
#           Screens: S57 · S56
# Rules:    BR-LED-003 · BR-LED-005 · BR-LED-021 · BR-LED-001 · BR-LED-015 ·
#           BR-TEN-043 (event time is an input) · CLAUDE.md rule 1 · rule 2 ·
#           rule 4 · rule 5 · rule 7
# Golden:   LE-4 — a Sep 30 accrual DR 1210 500.00 / CR 4100 500.00 takes an
#           Oct 1 mirror DR 4100 500.00 / CR 1210 500.00, linked both ways
# ───────────────────────────────────────────────────────
"""S57 is REACHABLE — and an unbalanced entry cannot be posted through it.

WHY THIS FILE EXISTS. `apps/ledger/manual_je.py` shipped on 2026-08-15 with the
whole BR-LED-003 lifecycle built, LE-4 reproduced and a G7 guard on it, carrying
`D=deferred(the S57 endpoints are the API half — not built by this lane)`. The
one way a finance officer puts a correction into the books by hand existed and
no human could reach it.

**THE CASE THIS FILE IS FOR IS `test_us_led_011_tc4__…unbalanced…`.** The S57
modal disables *Post entry ✓* while the entry does not foot, and that is a
courtesy, not the rule: this proves the SERVER refuses the same request when the
screen is bypassed entirely, which is the only version of the rule that holds.
"""

import uuid
from datetime import date, datetime, timezone as dt_timezone
from decimal import Decimal
from types import SimpleNamespace

import pytest

from apps.ledger import chart, journal_api, manual_je, models, posting, selectors
from core import errors

from tests.cost_of_service_fixtures import with_monthly_fiscal_year
from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared tenant fixtures
from tests.test_us_ten_helpers import api_call, tenant_ctx

pytestmark = pytest.mark.django_db

ENTRY_DAY = date(2026, 8, 6)
POSTED_AT = datetime(2026, 8, 6, 14, 30, tzinfo=dt_timezone.utc)

#: LE-4's own figure — a 500.00 accrual, quoted from the workbook rather than
#: invented, so a change to the golden example goes red here too.
LE4_ACCRUAL = Decimal("500.00")


def signed_in(role="system_admin"):
    """Both halves of a role, deliberately — see the chart-API suite's twin."""
    return SimpleNamespace(id=uuid.uuid4(), pk=uuid.uuid4(), role=role, is_authenticated=True)


def call(view, tenant, method="post", *, role="system_admin", data=None, query=None, **kwargs):
    return api_call(
        view,
        method,
        user=signed_in(role),
        role=role,
        tenant=tenant,
        data=data,
        query=query,
        **kwargs,
    )


def refused(response, code: str) -> None:
    assert response.status_code == errors.HTTP_STATUS_BY_CODE[code], (
        f"expected {code} ({errors.HTTP_STATUS_BY_CODE[code]}), got "
        f"{response.status_code} {getattr(response, 'data', None)!r}"
    )
    assert response.data["code"] == code


def two_accounts(tenant):
    """Two live chart rows to move money between, resolved BY DESIGNATION.

    Never by code: `chart.py`'s whole subject is that code reads the designation
    and never the number, and a test that hardcoded "1200" would be the first
    place that property rotted.
    """
    with tenant_ctx(tenant):
        debit = selectors.gl_account_for_designation(chart.UNBILLED_AR)
        credit = models.LedgerAccount.objects.filter(
            tenant_id=tenant.id, type="revenue", deleted_at__isnull=True
        ).order_by("code").first()
    assert debit is not None and credit is not None
    return str(debit.pk), str(credit.pk)


def balanced_body(tenant, *, amount=LE4_ACCRUAL, entry_type=models.JE_STANDARD, memo="Reclass"):
    debit, credit = two_accounts(tenant)
    return {
        "entry_date": ENTRY_DAY.isoformat(),
        "type": entry_type,
        "memo": memo,
        "lines": [
            {"ledger_account_id": debit, "side": models.SIDE_DEBIT, "amount": str(amount)},
            {"ledger_account_id": credit, "side": models.SIDE_CREDIT, "amount": str(amount)},
        ],
    }


# ═══════════════════════════════════════════════════════════════════════════
# THE TWO CASES THAT MATTER MOST — the routes exist, and can be reached
# ═══════════════════════════════════════════════════════════════════════════
def test_us_led_011_tc0__the_s57_routes_are_actually_mounted(brazos):
    from django.urls import resolve

    slug = brazos.subdomain
    entry_id = uuid.uuid4()
    assert (
        resolve(f"/api/{slug}/ledger/journal-entries/drafts").func
        is journal_api.journal_entry_drafts
    )
    assert (
        resolve(f"/api/{slug}/ledger/journal-entries/{entry_id}").func
        is journal_api.journal_entry_item
    )
    assert (
        resolve(f"/api/{slug}/ledger/journal-entries/{entry_id}/post").func
        is journal_api.journal_entry_post
    )
    assert (
        resolve(f"/api/{slug}/ledger/journal-entries/{entry_id}/reverse").func
        is journal_api.journal_entry_reverse
    )
    assert resolve(f"/api/{slug}/ledger/accruals").func is journal_api.accruals
    assert (
        resolve(f"/api/{slug}/ledger/accruals/auto-reverse").func
        is journal_api.accruals_auto_reverse
    )


def test_us_led_011_tc0b__the_S56_JOURNAL_LIST_STILL_ANSWERS_ITS_OWN_GET(brazos):
    """**THE COLLISION CASE, and the reason the draft path is one segment deeper.**

    Django resolves by URL and NOT by method. `apps/ledger/api.py` owns
    `ledger/journal-entries` as a GET-only route and its docstring makes the
    router-level 405 on every write verb a GUARANTEE. If this lane had
    registered `POST /ledger/journal-entries`, the S56 list would have been
    shadowed by a POST-only view and the trial-balance tab would have gone dark.

    So: the list route still resolves to the READ view, and it still refuses
    every write verb at the router.
    """
    from django.test import Client
    from django.urls import resolve

    from apps.ledger import api as ledger_api

    slug = brazos.subdomain
    assert resolve(f"/api/{slug}/ledger/journal-entries").func is ledger_api.journal_entries
    client = Client()
    for verb in ("post", "put", "patch", "delete"):
        response = getattr(client, verb)(f"/api/{slug}/ledger/journal-entries")
        assert response.status_code in (401, 405), (
            f"{verb.upper()} on the S56 list answered {response.status_code} — the read "
            "surface must never accept a write verb (hard rule 4 / BR-LED-003)"
        )


def test_us_led_011_tc0c__the_write_routes_are_reachable_through_the_whole_stack(brazos):
    """401 = the route exists and asked for a sign-in. 404 = S57 does not exist."""
    from django.test import Client

    slug = brazos.subdomain
    response = Client().post(
        f"/api/{slug}/ledger/journal-entries/drafts", data={}, content_type="application/json"
    )
    assert response.status_code == 401, (
        f"the draft route answered {response.status_code}: a 404 here means S57 is still "
        "unreachable, whatever the URLconf says"
    )
    assert Client().get(f"/api/{slug}/ledger/accruals").status_code == 401


# ═══════════════════════════════════════════════════════════════════════════
# US-LED-011 — the lifecycle
# ═══════════════════════════════════════════════════════════════════════════
def test_us_led_011_tc1__a_draft_saves_and_reports_what_it_would_post(brazos, audit_rows):
    response = call(journal_api.journal_entry_drafts, brazos, data=balanced_body(brazos))
    assert response.status_code == 201, response.data
    assert response.data["status"] == models.JE_DRAFT
    assert response.data["balanced"] is True
    assert Decimal(response.data["gap"]) == Decimal("0")
    assert Decimal(response.data["debits"]) == LE4_ACCRUAL
    # CLAUDE.md rule 2 — the CHAR(3) rides with every amount, always.
    assert response.data["currency"]
    assert [row for row in audit_rows if row["entity_type"] == "journal_entry"]


def test_us_led_011_tc4__AN_UNBALANCED_ENTRY_CANNOT_BE_POSTED(brazos):
    """**THE CASE THIS WHOLE FILE IS FOR.**

    The draft SAVES unbalanced — BR-LED-003 says drafts are freely editable, and
    a six-line reclass is unbalanced between every keystroke, so refusing the
    save would make the modal unusable. `gap` comes back and is what S57's
    *Must balance* footer renders.

    The POST is refused, on the SERVER, with the screen bypassed entirely. That
    is the rule; the grey button is the courtesy.
    """
    debit, credit = two_accounts(brazos)
    draft = call(
        journal_api.journal_entry_drafts,
        brazos,
        data={
            "entry_date": ENTRY_DAY.isoformat(),
            "memo": "Off by ten dollars",
            "lines": [
                {"ledger_account_id": debit, "side": models.SIDE_DEBIT, "amount": "500.00"},
                {"ledger_account_id": credit, "side": models.SIDE_CREDIT, "amount": "490.00"},
            ],
        },
    )
    assert draft.status_code == 201, draft.data
    assert draft.data["balanced"] is False
    assert Decimal(draft.data["gap"]) == Decimal("10.00"), "S57's Must-balance footer"

    posted = call(
        journal_api.journal_entry_post,
        brazos,
        data={"posted_at": POSTED_AT.isoformat()},
        entry_id=draft.data["entry_id"],
    )
    refused(posted, errors.BIZ_STATE)
    with tenant_ctx(brazos):
        assert (
            models.JournalEntry.objects.get(pk=draft.data["entry_id"]).status == models.JE_DRAFT
        ), "a refused post leaves the draft a draft — nothing partial enters the books"


def test_us_led_011_tc4b__an_empty_memo_blocks_the_post(brazos):
    """BR-LED-003: *balanced required at post; reason + audit*. The entry is
    immutable the moment it posts, so the memo is the only place the WHY can
    ever be written."""
    body = balanced_body(brazos, memo="")
    draft = call(journal_api.journal_entry_drafts, brazos, data=body)
    assert draft.status_code == 201, draft.data
    posted = call(
        journal_api.journal_entry_post,
        brazos,
        data={"posted_at": POSTED_AT.isoformat()},
        entry_id=draft.data["entry_id"],
    )
    refused(posted, errors.BIZ_STATE)


def test_us_led_011_tc2__a_balanced_entry_posts_and_becomes_immutable(brazos):
    """TC-2, and hard rule 4 immediately after it.

    The second half is the one that matters: the posted entry is offered NO
    edit anywhere in this surface, and the draft-delete path refuses it. A
    posted entry is immutable forever and the only "edit" is reverse + repost.
    """
    draft = call(journal_api.journal_entry_drafts, brazos, data=balanced_body(brazos))
    posted = call(
        journal_api.journal_entry_post,
        brazos,
        data={"posted_at": POSTED_AT.isoformat()},
        entry_id=draft.data["entry_id"],
    )
    assert posted.status_code == 200, posted.data
    assert posted.data["status"] == models.JE_POSTED
    assert Decimal(posted.data["debits"]) == Decimal(posted.data["credits"]) == LE4_ACCRUAL
    # ⚠ THIS ASSERTION DID ITS JOB AND WAS INVERTED, 2026-08-17. It read *"the
    # number is NULL on every host today … asserting the gap by name is how a
    # seeded series goes red here"* — and CR-005 seeded the series, so it went
    # red, exactly as its author intended. BR-LED-021's `JE-{000000}` is now
    # provisioned for every tenant, so a posted entry carries a number a finance
    # officer can read aloud, and nothing is unavailable.
    assert posted.data["je_number"] == "JE-000001"
    # The numbering gap specifically is gone; the OQ-175 role-gate note that
    # shares this list is another matter entirely and stays.
    assert "journal_number_series_is_not_seeded" not in {
        gap["code"] for gap in posted.data["unavailable"]
    }

    deleted = call(
        journal_api.journal_entry_item,
        brazos,
        "delete",
        entry_id=draft.data["entry_id"],
    )
    refused(deleted, errors.BIZ_STATE)
    with tenant_ctx(brazos):
        assert models.JournalEntry.objects.filter(pk=draft.data["entry_id"]).exists()


def test_us_led_011_tc6__a_draft_deletes_without_trace_in_the_books(brazos):
    draft = call(journal_api.journal_entry_drafts, brazos, data=balanced_body(brazos))
    entry_id = draft.data["entry_id"]
    response = call(journal_api.journal_entry_item, brazos, "delete", entry_id=entry_id)
    assert response.status_code == 200, response.data
    assert response.data["deleted"] is True
    with tenant_ctx(brazos):
        assert not models.JournalEntry.objects.filter(pk=entry_id).exists()
        assert not models.JournalLine.objects.filter(journal_entry_id=entry_id).exists()


def test_us_led_011_tc7__another_tenants_entry_is_refused(brazos, lonestar):
    """HR-1 — nothing is posted, and nothing is reported about whose it is."""
    theirs = call(journal_api.journal_entry_drafts, lonestar, data=balanced_body(lonestar))
    assert theirs.status_code == 201, theirs.data
    response = call(
        journal_api.journal_entry_post,
        brazos,
        data={"posted_at": POSTED_AT.isoformat()},
        entry_id=theirs.data["entry_id"],
    )
    assert response.status_code in (404, 409), response.data
    with tenant_ctx(lonestar):
        assert (
            models.JournalEntry.objects.get(pk=theirs.data["entry_id"]).status == models.JE_DRAFT
        )


def test_us_led_011_tc8__a_float_amount_is_refused_rather_than_coerced(brazos):
    """CLAUDE.md rule 2 — money is never a float, and the one place a float
    looks harmless is exactly where it gets in. A JSON number reaching the view
    has already lost the value, so the wire contract is a decimal STRING."""
    debit, credit = two_accounts(brazos)
    response = call(
        journal_api.journal_entry_drafts,
        brazos,
        data={
            "entry_date": ENTRY_DAY.isoformat(),
            "memo": "float",
            "lines": [
                {"ledger_account_id": debit, "side": models.SIDE_DEBIT, "amount": 500.10},
                {"ledger_account_id": credit, "side": models.SIDE_CREDIT, "amount": "500.10"},
            ],
        },
    )
    refused(response, errors.VAL_FORMAT)


def test_us_led_011_tc9__an_executive_may_not_post_a_journal_entry(brazos):
    """The PO's closure of OQ-175, 2026-08-12: System Admin and Billing Clerk
    may; Executive may not."""
    response = call(
        journal_api.journal_entry_drafts, brazos, role="executive", data=balanced_body(brazos)
    )
    refused(response, errors.AUTH_PERMISSION_DENIED)


# ═══════════════════════════════════════════════════════════════════════════
# US-LED-012 — the accrual and its day-1 mirror (LE-4)
# ═══════════════════════════════════════════════════════════════════════════
def test_us_led_012_tc1__an_accrual_takes_its_day_one_mirror_linked_both_ways(brazos):
    """LE-4 end to end, through the surface a human can actually reach.

    The accrual posts; the sweep is asked for the day the mirror is due; the
    mirror exists, is linked BOTH ways (r13 #2 gives the pair two links, and one
    column cannot answer *"was this reversed?"* and *"is this the reversal?"*),
    and a second sweep writes nothing.
    """
    # BR-TEN-022: the accrual's mirror is due on day 1 of the tenant's NEXT
    # PERIOD, which is computed from its fiscal calendar. Without one
    # `close.period_window` refuses by design, so the calendar is stated first —
    # exactly as a real tenant states it on Settings → Regional.
    with tenant_ctx(brazos):
        with_monthly_fiscal_year(signed_in())
    draft = call(
        journal_api.journal_entry_drafts,
        brazos,
        data=balanced_body(brazos, entry_type=models.JE_ACCRUAL, memo="August accrual"),
    )
    posted = call(
        journal_api.journal_entry_post,
        brazos,
        data={"posted_at": POSTED_AT.isoformat()},
        entry_id=draft.data["entry_id"],
    )
    assert posted.status_code == 200, posted.data

    with tenant_ctx(brazos):
        due_on = manual_je.accrual_reversal_due_on(ENTRY_DAY)
    assert due_on > ENTRY_DAY, "BR-LED-005 — day 1 of the NEXT period"

    listed = call(journal_api.accruals, brazos, "get", query={"as_of": due_on.isoformat()})
    assert listed.status_code == 200, listed.data
    assert draft.data["entry_id"] in {row["entry_id"] for row in listed.data["rows"]}

    swept = call(
        journal_api.accruals_auto_reverse,
        brazos,
        data={
            "as_of": due_on.isoformat(),
            "posted_at": datetime.combine(due_on, datetime.min.time())
            .replace(tzinfo=dt_timezone.utc)
            .isoformat(),
        },
    )
    assert swept.status_code == 200, swept.data
    assert swept.data["created"] == 1, swept.data
    row = swept.data["rows"][0]
    assert row["mirror_entry_id"] is not None
    assert Decimal(row["amount"]) == LE4_ACCRUAL

    with tenant_ctx(brazos):
        accrual = models.JournalEntry.objects.get(pk=draft.data["entry_id"])
        mirror = models.JournalEntry.objects.get(pk=row["mirror_entry_id"])
        assert str(accrual.auto_reverse_entry_id) == str(mirror.pk)
        assert str(mirror.reversal_of_id) == str(accrual.pk)

    # US-LED-012 TC-5 — the sweep is idempotent. A replay writes NOTHING; the
    # posting key is one string per accrual, forever.
    again = call(
        journal_api.accruals_auto_reverse,
        brazos,
        data={
            "as_of": due_on.isoformat(),
            "posted_at": datetime.combine(due_on, datetime.min.time())
            .replace(tzinfo=dt_timezone.utc)
            .isoformat(),
        },
    )
    assert again.status_code == 200, again.data
    assert again.data["created"] == 0, "a second sweep must write nothing"
    empty = call(journal_api.accruals, brazos, "get", query={"as_of": due_on.isoformat()})
    assert empty.data["count"] == 0, "the accrual no longer owes a mirror"


def test_us_led_012_tc2__the_accrual_read_refuses_to_invent_a_clock(brazos):
    """BR-TEN-043 / gate G6 — `as_of` is the CALLER's. A read that took 'today'
    from the server could never be asked about a day the host was down, and a
    catch-up run is the normal case after one was."""
    refused(call(journal_api.accruals, brazos, "get"), errors.VAL_REQUIRED)


# ═══════════════════════════════════════════════════════════════════════════
# US-LED-013 — the ONE lawful edit
# ═══════════════════════════════════════════════════════════════════════════
def test_us_led_013_tc1__reverse_and_repost_writes_two_entries_and_edits_none(brazos):
    """LE-8's shape: the mirror is POSTED, the correction is RETURNED.

    `repost_draft_is_not_persisted` travels on the response so the screen says
    so rather than a clerk discovering that Cancel lost nothing.
    """
    draft = call(journal_api.journal_entry_drafts, brazos, data=balanced_body(brazos))
    call(
        journal_api.journal_entry_post,
        brazos,
        data={"posted_at": POSTED_AT.isoformat()},
        entry_id=draft.data["entry_id"],
    )
    response = call(
        journal_api.journal_entry_reverse,
        brazos,
        data={
            "reason": "keyed 500.00, the correct amount is 450.00",
            "entry_date": ENTRY_DAY.isoformat(),
            "posted_at": POSTED_AT.isoformat(),
        },
        entry_id=draft.data["entry_id"],
    )
    assert response.status_code == 200, response.data
    assert response.data["mirror_created"] is True
    assert response.data["repost_draft"], "the prefilled correction comes back as DATA"
    assert "repost_draft_is_not_persisted" in {
        gap["code"] for gap in response.data["unavailable"]
    }
    with tenant_ctx(brazos):
        original = models.JournalEntry.objects.get(pk=draft.data["entry_id"])
        assert original.status == models.JE_POSTED, "the original is untouched (hard rule 4)"
        mirror = models.JournalEntry.objects.get(pk=response.data["mirror_entry_id"])
        assert str(mirror.reversal_of_id) == str(original.pk), "r13 #2 links the pair"

    # A second click returns the FIRST mirror — the correct outcome of a
    # double-submitted form, not an error.
    again = call(
        journal_api.journal_entry_reverse,
        brazos,
        data={
            "reason": "keyed 500.00, the correct amount is 450.00",
            "entry_date": ENTRY_DAY.isoformat(),
            "posted_at": POSTED_AT.isoformat(),
        },
        entry_id=draft.data["entry_id"],
    )
    assert again.status_code == 200, again.data
    assert again.data["mirror_created"] is False
    assert again.data["mirror_entry_id"] == response.data["mirror_entry_id"]


def test_us_led_013_tc2__a_reversal_without_a_reason_is_refused(brazos):
    """BR-LED-003 — reason + audit. A correction with no reason is a correction
    nobody can ever explain to an auditor."""
    draft = call(journal_api.journal_entry_drafts, brazos, data=balanced_body(brazos))
    call(
        journal_api.journal_entry_post,
        brazos,
        data={"posted_at": POSTED_AT.isoformat()},
        entry_id=draft.data["entry_id"],
    )
    response = call(
        journal_api.journal_entry_reverse,
        brazos,
        data={"entry_date": ENTRY_DAY.isoformat(), "posted_at": POSTED_AT.isoformat()},
        entry_id=draft.data["entry_id"],
    )
    refused(response, errors.VAL_REQUIRED)


def test_us_led_011_tc10__this_surface_writes_no_journal_row_itself(brazos):
    """CLAUDE.md rule 5, asserted on the SOURCE.

    `apps/ledger/posting.py` is the sole writer and `ledger/0004`'s trigger makes
    that structural. This is the cheap check that keeps the API layer honest
    between now and the next time somebody is in a hurry: no `objects.create(`,
    no `.save(`, no `.delete(` anywhere in the endpoint module.
    """
    from pathlib import Path

    source = Path(journal_api.__file__).read_text(encoding="utf-8")
    for forbidden in ("objects.create(", ".save(", ".delete(", "objects.filter("):
        assert forbidden not in source, (
            f"{forbidden} in apps/ledger/journal_api.py — only the posting service writes "
            "journal rows (CLAUDE.md rule 5) and an api.py touches no ORM at all (G6)"
        )
    assert posting is not None  # the engine this surface calls, named in the imports
