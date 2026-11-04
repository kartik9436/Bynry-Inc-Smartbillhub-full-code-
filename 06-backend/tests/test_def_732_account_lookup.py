# ── Trace ──────────────────────────────────────────────
# Defect:   DEF-732 — the transfer wizard (and the disconnect wizard beside it)
#           asked a clerk to type an internal id. They now find the account the
#           way the product SHOWS it: by the number on every list, KPI tile and
#           detail header, through the published `GET /accounts?q=`.
# Screens:  S89 `TRF-02.1` · `DSC-02.1` (the frontend half is
#           `07-frontend/src/features/customers/accountLookup.dom.test.tsx`)
# Rules:    CLAUDE.md hard rule 1 (tenant scoping, RLS FORCE) ·
#           BR-CUS-053 (one box, five terms) · BR-TEN-003 (a cross-tenant id is
#           indistinguishable from an absent one) · BR-SHL-011
# ───────────────────────────────────────────────────────
"""DEF-732 — the account-number lookup a clerk now depends on, and the boundary
it must never cross.

**WHY THIS FILE EXISTS AT ALL.** The fix moved the wizards from an internal id
onto a HUMAN-TYPED number, and a human-typed number is exactly where a
cross-tenant leak would hide: `AC-2026-00025` is allocated from each tenant's
OWN series, so the same string is a real account in several tenants at once. An
id is a uuid nobody guesses; a number is a string every one of our customers
prints on their bills.

**The screens' half is proved in the browser and cannot prove this half.** A
frontend test stubs the server, so it can show the box searches — it can never
show WHOSE accounts come back. That is a fact about rows, RLS and the session
GUC, and it lives here.

⚠ **NOTHING IN THE BACKEND CHANGED FOR DEF-732.** These are guards over the
behaviour the screens now RELY on: the published search was already the right
door (BR-CUS-053), and this file is what makes it a door that cannot be widened
without a red test.
"""

import pytest

from apps.customers import selectors
from core import errors
from core.pagination import ListParams

from tests.isolation_helpers import (  # noqa: F401
    live_tenant_context,
    requires_postgres,
    rls,
    rls_probe_role,
)
from tests.test_us_met_helpers import *  # noqa: F401,F403
from tests.test_us_met_helpers import (  # noqa: F401
    brazos,
    erin,
    lonestar,
    marcus,
    make_premises,
    make_unit,
    tenant_ctx,
)

from tests.test_cr030_w0_customer_no import _account_for  # noqa: E402

pytestmark = pytest.mark.django_db


def _search(term: str) -> list[str]:
    """`GET /accounts?q=<term>` as the wizards' box asks it — account numbers
    back, because those are what a reader of a failure message recognises."""
    return [row["account_no"] for row in selectors.account_list(ListParams(q=term))]


# ══════════════════════════════════════════════════════════════════════════
# The leg the screen now stands on
# ══════════════════════════════════════════════════════════════════════════


def test_def_732__the_number_a_list_displays_finds_the_account(brazos, marcus):
    """The PO typed `AC-2026-00025`. Whatever this tenant's series produces, the
    number the register PRINTS is the number the box FINDS — asserted through
    the same selector the screen calls, not a hand-built query."""
    with tenant_ctx(brazos):
        account = _account_for(marcus, brazos, label="DEF-732 A")
        number = account["account_no"]
        assert number, "the fixture account has no number — the premise of the case is gone"

        assert _search(number) == [number]


def test_def_732__a_number_that_matches_nothing_is_an_empty_list_not_an_error(brazos, marcus):
    """BR-SHL-011, and the screen's second sentence.

    "No account matches" and "that account could not be read" are DIFFERENT
    FACTS (DEF-732's own finding), and the first one is only available to the
    screen because this call returns an empty list instead of raising."""
    with tenant_ctx(brazos):
        _account_for(marcus, brazos, label="DEF-732 B")

        assert _search("AC-2026-99999") == []


def test_def_732__what_the_old_field_did_is_still_refused_as_not_found(brazos, marcus):
    """The DEFECT, pinned as behaviour: `GET /accounts/{id}` is right to refuse a
    number, and it was the SCREEN that was wrong to send one.

    Kept as a test because the tempting "fix" is to teach this door to resolve
    numbers too — which would give one URL two identifier spaces and a second
    place for the tenant check to be written. The published search is the door
    for a number; this one stays an id door."""
    with tenant_ctx(brazos):
        account = _account_for(marcus, brazos, label="DEF-732 C")
        with pytest.raises(errors.NotFoundError):
            selectors.account_detail(account["account_no"])
        # …and the id it resolves to still reads, so nothing was traded away.
        assert selectors.account_detail(account["id"])["account_no"] == account["account_no"]


# ══════════════════════════════════════════════════════════════════════════
# THE BOUNDARY — CLAUDE.md hard rule 1
# ══════════════════════════════════════════════════════════════════════════


def test_def_732__one_tenant_never_resolves_another_tenants_account_number(
    brazos, lonestar, marcus, erin
):
    """**The case the fix is not allowed to ship without.**

    Both tenants allocate from their OWN series, so their first accounts carry
    the SAME number — which is the condition a leak hides behind, and the reason
    a human-typed number is a sharper edge than a uuid ever was. Each tenant's
    search must answer with its own row and nothing else.
    """
    with tenant_ctx(brazos):
        mine = _account_for(marcus, brazos, label="DEF-732 X")
    with tenant_ctx(lonestar):
        theirs = _account_for(erin, lonestar, label="DEF-732 Y", service="water")

    assert mine["account_no"] == theirs["account_no"], (
        "the two tenants' first accounts no longer collide, so this case is no "
        "longer testing the leak it was written for — pin the numbers instead"
    )
    number = mine["account_no"]

    with tenant_ctx(brazos):
        rows = selectors.account_list(ListParams(q=number))
        assert [row["id"] for row in rows] == [str(mine["id"])] or [row["id"] for row in rows] == [
            mine["id"]
        ], rows
    with tenant_ctx(lonestar):
        rows = selectors.account_list(ListParams(q=number))
        assert [str(row["id"]) for row in rows] == [str(theirs["id"])], rows


def test_def_732__the_id_the_choice_resolves_to_is_refused_across_the_boundary(
    brazos, lonestar, marcus, erin
):
    """The other half: what the clerk's CHOICE posts is an id, and an id from
    another tenant reads as ABSENT — never as forbidden (BR-TEN-003 / HR-1,
    existence must not leak)."""
    with tenant_ctx(lonestar):
        theirs = _account_for(erin, lonestar, label="DEF-732 Z", service="water")
    with tenant_ctx(brazos):
        _account_for(marcus, brazos, label="DEF-732 W")
        with pytest.raises(errors.NotFoundError):
            selectors.account_detail(theirs["id"])


# ── Lifecycle ─────────────────────────────────────────────
# packet: DEF-732 (12-governance/10-defect-log.csv) · BR-CUS-053 · BR-TEN-003 ·
#         CLAUDE.md hard rules 1 and 2
# generated: 2026-08-26 by the ACCTLOOKUP lane
# checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-09)
# gates: pytest (this file) · the frontend half is
#        `accountLookup.dom.test.tsx`, proved RED against the shipped wizards
#        before the fix
# exceptions: E4 this file lives in `06-backend/tests/` and not in
#   `apps/customers/tests/` — the latter does not exist; every customers suite
#   in this repo is in `tests/`
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
