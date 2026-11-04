# ── Trace ──────────────────────────────────────────────
# Defect:  DEF-LED-6723 — the `View entry` eye on Finance → General ledger →
#          Journal could not be clicked, because `GET /ledger/journal-entries/
#          {id}` was never served: the path was registered DELETE-only and
#          Django resolves by URL, not by method. Reported by the Product Owner
#          on v2.351.84. Filed BEFORE the fix (CLAUDE.md step W).
# Story:   US-LED-013 · A1 S56 (*"Journal list + detail"*, 11b §2.10 line 436,
#          *"lines expand to dimensions"*)
# Rules:   BR-LED-001 (the five dimensions on every line) · BR-LED-003 + hard
#          rule 4 (a posted entry is immutable — NOTHING here writes and no
#          write verb is offered) · BR-LED-021 (a draft and an opening balance
#          have NO number, ever) · NFR-3 (the lines page) · NFR-5 (no cap) ·
#          hard rule 1 (tenant scoping; a foreign id denies as NOT FOUND) ·
#          B14 rule 31 (no database id is the visible value of a field)
# Tests:   this file
# Impacts: apps/ledger/reporting.py (`journal_entry_detail`) · apps/ledger/
#          wire.py (`journal_entry_detail_dict`) · apps/ledger/journal_api.py
#          (the GET half of `journal_entry_item`) · core/permissions.py
#          (`JournalEntryReadAnyDeleteAdminOrClerk`)
# ───────────────────────────────────────────────────────
"""DEF-LED-6723 — one journal entry opens, with both sides and that they agree.

RED-FIRST PROOF (hard-won law 7, in the harness that runs it — `pytest`, never a
`__main__`). Every case below was run against this worktree BEFORE the fix. The
route case failed with the router's own refusal —

    rest_framework.exceptions.MethodNotAllowed: Method "GET" not allowed.

— which is the defect exactly: the path existed and the verb did not.

⚠ **WHAT WOULD MAKE THESE PASS WRONGLY, ASKED BEFORE THEY WERE TRUSTED.**

  * A case that only checked the response was `200` would pass over an entry
    served with no lines at all, which is the one shape a detail screen must
    never show silently. So `test_both_sides_are_served_and_they_agree` asserts
    the LINE COUNT, both sides' sums, and that they are equal — arithmetic, not
    a status code.
  * A case that read `balanced` off a page would pass on a two-line fixture and
    fail nobody. `test_balanced_is_the_whole_entry_and_not_the_page` plants an
    entry with **120** lines, asks for page 1 (fifty), and asserts the header's
    debit and credit are the whole entry's while `results` holds fifty. On the
    naive implementation — summing the page — the header would report a
    balanced entry as balanced anyway, so the case asserts the FIGURE and not
    the flag.
  * A case asserting `je_number is None` on a draft would pass on code that
    never looked at the column. `test_an_entry_with_no_number_shows_no_number`
    asserts it on a POSTED entry sitting beside one that HAS a number, so the
    read is provably reading.

Run with `JOBS_EAGER=false` (DEF-567). The tenancy case wants PostgreSQL
(`--ds=config.settings.pgtest`) to be about RLS rather than about a filter;
it is meaningful on either tier because the read filters explicitly too.
"""

from decimal import Decimal

import pytest
from rest_framework.test import APIRequestFactory, force_authenticate

from apps.ledger import journal_api
from apps.ledger import models as ledger_models
from apps.ledger import reporting
from core import errors
from core.permissions import AdminOrClerk, JournalEntryReadAnyDeleteAdminOrClerk

from tests.test_def_led_6493_journal_pages_in_sql import _open_write_window, plant_entries
from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared tenant fixtures
from tests.test_us_met_helpers import (  # noqa: F401
    brazos,
    dana,
    lonestar,
    tenant_ctx,
)

pytestmark = pytest.mark.django_db


def _get(tenant, actor, entry_id, role="system_admin", **params):
    request = APIRequestFactory().get(
        f"/api/{tenant.subdomain}/ledger/journal-entries/{entry_id}", params
    )
    force_authenticate(request, user=actor.user)
    request.tenant_role = role
    request.tenant_id = tenant.id
    return journal_api.journal_entry_item(request, entry_id=str(entry_id))


def _one_entry(tenant, *, lines_each=2, tag="det"):
    plant_entries(tenant, entries=1, tag=tag, lines_each=lines_each)
    return ledger_models.JournalEntry.objects.filter(
        tenant=tenant, posting_key=f"{tag}-00000"
    ).get()


# ══════════════════════════════════════════════════════════════════════════
# 1 · THE DOOR OPENS AT ALL — the case that goes red on the old code
# ══════════════════════════════════════════════════════════════════════════
def test_the_route_serves_a_get_at_all(brazos, dana):
    """RED BEFORE: `MethodNotAllowed: Method "GET" not allowed.`"""
    with tenant_ctx(brazos):
        entry = _one_entry(brazos)
        response = _get(brazos, dana, entry.pk)
    assert response.status_code == 200, response.data
    assert response.data["entry"]["entry_id"] == str(entry.pk)


def test_both_sides_are_served_and_they_agree(brazos, dana):
    """Every line, both sides, and the arithmetic — not a status code."""
    with tenant_ctx(brazos):
        entry = _one_entry(brazos, lines_each=6, tag="agree")
        response = _get(brazos, dana, entry.pk)
    body = response.data
    assert len(body["results"]) == 6
    assert body["count"] == 6
    debits = sum(Decimal(r["debit"]) for r in body["results"] if r["debit"] is not None)
    credits = sum(
        Decimal(r["credit"]) for r in body["results"] if r["credit"] is not None
    )
    assert debits == credits, (debits, credits)
    assert Decimal(body["entry"]["debit"]) == debits
    assert Decimal(body["entry"]["credit"]) == credits
    assert body["entry"]["balanced"] is True


def test_balanced_is_the_whole_entry_and_not_the_page(brazos, dana):
    """NFR-3 — the lines page, and the header still describes the ENTRY.

    A 120-line entry over a 50-row page. The header's figures must be the
    entry's; summed from the page they would be 50/120ths of it.
    """
    with tenant_ctx(brazos):
        entry = _one_entry(brazos, lines_each=120, tag="big")
        response = _get(brazos, dana, entry.pk)
    body = response.data
    assert len(body["results"]) == 50, "the lines did not page"
    assert body["count"] == 120, "count must be the whole entry's lines"
    page_debits = sum(
        Decimal(r["debit"]) for r in body["results"] if r["debit"] is not None
    )
    whole = Decimal("15066.0000") * 60
    assert Decimal(body["entry"]["debit"]) == whole
    assert Decimal(body["entry"]["debit"]) != page_debits, (
        "the header repeated the page's figure — the whole-entry sum was not taken"
    )
    assert body["entry"]["balanced"] is True


def test_no_cap_is_introduced(brazos, dana):
    """NFR-5 — a bigger page is SERVED, never refused."""
    with tenant_ctx(brazos):
        entry = _one_entry(brazos, lines_each=120, tag="nocap")
        response = _get(brazos, dana, entry.pk, per="200")
    assert response.status_code == 200
    assert len(response.data["results"]) == 120


# ══════════════════════════════════════════════════════════════════════════
# 2 · THE ENTRY WITH NO NUMBER — the case most likely to break
# ══════════════════════════════════════════════════════════════════════════
def test_an_entry_with_no_number_shows_no_number(brazos, dana):
    """An opening balance is not a document. Nothing invents one.

    Asserted BESIDE an entry that HAS a number, so a read that never looks at
    the column cannot pass this by returning null for everything.
    """
    with tenant_ctx(brazos):
        unnumbered = _one_entry(brazos, tag="nonum")
        numbered = _one_entry(brazos, tag="hasnum")
        _open_write_window()
        ledger_models.JournalEntry.objects.filter(pk=numbered.pk).update(
            number="JE-080226-0043"
        )
        ledger_models.JournalEntry.objects.filter(pk=unnumbered.pk).update(
            source_type="opening_balance"
        )
        blank = _get(brazos, dana, unnumbered.pk).data
        filled = _get(brazos, dana, numbered.pk).data
    assert blank["entry"]["je_number"] is None
    assert blank["entry"]["source_label"] == "opening"
    assert filled["entry"]["je_number"] == "JE-080226-0043"


# ══════════════════════════════════════════════════════════════════════════
# 3 · THE DIMENSIONS ARE NAMES, NOT IDS (B14 rule 31)
# ══════════════════════════════════════════════════════════════════════════
def test_a_dimension_carries_a_label_and_the_id_is_never_the_label(
    brazos, dana
):
    with tenant_ctx(brazos):
        entry = _one_entry(brazos, tag="dims")
        body = _get(brazos, dana, entry.pk).data
    for line in body["results"]:
        for name in ("service", "account", "premises", "unit", "tax_authority"):
            slot = line[name]
            if slot is None:
                continue
            assert set(slot) == {"id", "label"}
            assert slot["label"] != slot["id"], (
                f"{name} rendered its id as its label — B14 rule 31"
            )
        # The chart account is a CODE and a NAME, never the row's uuid.
        assert "-" not in (line["account_code"] or ""), line["account_code"]


# ══════════════════════════════════════════════════════════════════════════
# 4 · HARD RULE 4 — the detail offers no edit, and the path offers no write
# ══════════════════════════════════════════════════════════════════════════
def test_the_detail_offers_nothing_that_could_be_saved(brazos, dana):
    with tenant_ctx(brazos):
        entry = _one_entry(brazos, tag="ro")
        body = _get(brazos, dana, entry.pk).data
    forbidden = {"updated_at", "version", "etag", "editable", "lock_version"}
    assert not (forbidden & set(body["entry"])), body["entry"].keys()
    for line in body["results"]:
        assert not (forbidden & set(line))


@pytest.mark.parametrize("verb", ["put", "patch", "post"])
def test_no_write_verb_is_offered_on_this_path(brazos, dana, verb):
    """Hard rule 4 / BR-LED-003. DRF refuses the verb before the view body runs.

    ⚠ **ASSERTED AS A 405 RESPONSE AND NOT AS A RAISE, WHICH IS WHAT THIS CASE
    WAS FIRST WRITTEN AS AND WAS WRONG ABOUT.** `@api_view` catches
    `MethodNotAllowed` and renders it, so `pytest.raises` never fires — a case
    that would have gone red on correct code, which is the mirror of a check
    that cannot fail. The status is the thing a caller actually meets.
    """
    with tenant_ctx(brazos):
        entry = _one_entry(brazos, tag="verbs")
        request = getattr(APIRequestFactory(), verb)(
            f"/api/brazosbend/ledger/journal-entries/{entry.pk}", {}, format="json"
        )
        force_authenticate(request, user=dana.user)
        request.tenant_role = "system_admin"
        request.tenant_id = brazos.id
        response = journal_api.journal_entry_item(request, entry_id=str(entry.pk))
    assert response.status_code == 405, response.data


# ══════════════════════════════════════════════════════════════════════════
# 5 · HARD RULE 1 — a foreign entry is NOT FOUND, never FORBIDDEN
# ══════════════════════════════════════════════════════════════════════════
def test_another_tenants_entry_denies_as_not_found(brazos, lonestar, dana):
    with tenant_ctx(lonestar):
        foreign = _one_entry(lonestar, tag="foreign")
    with tenant_ctx(brazos):
        # ⚠ **A 404 RESPONSE, NOT A RAISE.** `@api_view` renders
        # `NotFoundError` through BE-02's handler, so the thing a stranger
        # actually meets is a status — and it must be byte-identical to the one
        # a genuinely absent id gets, or the refusal itself tells them which of
        # our tenants holds which entry (HR-1 / G4).
        foreign_response = _get(brazos, dana, foreign.pk)
        absent_response = _get(brazos, dana, "01a0d239-0000-7000-8000-000000000000")
        assert foreign_response.status_code == 404
        assert absent_response.status_code == 404
        # ⚠ `trace_id` IS PER REQUEST AND IS EXCLUDED ON PURPOSE. It differs
        # between any two calls, including two identical ones, so comparing it
        # would make this case fail on correct code — a check incapable of
        # passing, which is the shape law 7 names. Everything else must match.
        def _body(response):
            return {k: v for k, v in response.data.items() if k != "trace_id"}

        assert _body(foreign_response) == _body(absent_response), (
            "a foreign entry and an absent one answer differently — existence leaks"
        )
        # And the read model itself refuses, so a future caller that does not go
        # through the view inherits the same guarantee.
        with pytest.raises(errors.NotFoundError):
            reporting.journal_entry_detail("01a0d239-0000-7000-8000-000000000000")


# ══════════════════════════════════════════════════════════════════════════
# 6 · THE DELETE'S ROLE SET DID NOT MOVE WHEN THE READ ARRIVED
# ══════════════════════════════════════════════════════════════════════════
def test_adding_the_read_did_not_widen_the_delete():
    """The PO's closure of OQ-175 is pinned, so a later lane widening the READ
    cannot widen the DELETE with it."""
    assert (
        JournalEntryReadAnyDeleteAdminOrClerk.WRITE_ROLES
        == AdminOrClerk.allowed_roles
    )
    assert "executive" not in JournalEntryReadAnyDeleteAdminOrClerk.WRITE_ROLES


def test_a_role_that_may_not_delete_may_still_open(brazos, dana):
    """A4: Finance is readable by every tenant role, as the LIST already is.

    Driven as an EXECUTIVE — the one role `AdminOrClerk` excludes — so this case
    is about the widening and not about a role that could already read.
    """
    with tenant_ctx(brazos):
        entry = _one_entry(brazos, tag="exec")
        response = _get(brazos, dana, entry.pk, role="executive")
    assert response.status_code == 200
