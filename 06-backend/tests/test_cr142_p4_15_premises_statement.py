# ── Trace ──────────────────────────────────────────────
# Story:    CR-142-BRC07 Phase 4 · `P4.15` — *"a landlord sees their own
#           account only"*.  Screen: CWP-078 Property statement.
# Rules:    **R24c LAW (ruled)** — brief p070/p071, verbatim: *"This report
#           crosses customers — and that is now ruled. Staff see it as drawn.
#           In the customer portal a landlord sees **their own master account
#           only**: the $69.60, never Unit 3's $100.00 (`P4.15`)."* ·
#           BR-CWP-016 (PO 2026-09-04, *"(a) no"*) · BR-CWP-010 (the tenant AND
#           the account set, IN THE QUERY) · BR-CWP-093 (nothing empty ever
#           appears) · CLAUDE.md hard rule 1 · hard rule 2 (4 dp stored) ·
#           hard rule 8 (the address is WALKED) · hard-won law 14 (this suite
#           runs on SQLite, which has NO row-level security)
# Tests:    this file · 10-scripts/rep_p4_15_landlord_rls_proof.py (the OTHER
#           strand, on real PostgreSQL 16 as a role that is neither SUPERUSER
#           nor BYPASSRLS — the one this file structurally cannot make)
# ───────────────────────────────────────────────────────
"""THE PO'S OWN WORKED EXAMPLE, BUILT AND THEN ASSERTED FROM BOTH SIDES.

The ruling names four figures and this file writes all four into the ledger
and reads them back:

    Unit 3 (a TENANT's account)   charges 196.00  credits −96.00  closing 100.00
    Common (the LANDLORD's master) charges  69.60  credits   0.00  closing  69.60

The landlord must see the `69.60` and **must not see the `100.00`**; the tenant
must see the `100.00` and **must not see the `69.60`**. Both directions are
asserted, because a scoping bug that leaks upward and one that leaks downward
are different bugs and a test for one is not a test for the other.

⚠ **THE ABSENCE IS ASSERTED OVER THE SERIALISED PAYLOAD, NOT OVER A FIELD.**
`assert row["closing"] != "100.00"` passes on a body that carries the tenant's
figure in a key the assertion never named — which is exactly how a scoped read
leaks: not in the column somebody thought about, but in a roll-up, a total or a
debugging key beside it. So the checks below render the WHOLE body to a string
and refuse the forbidden figure anywhere in it. That is hard-won law 7's *ask
what would make this check pass wrongly* applied to the check itself.

⚠ **WHAT THIS FILE CANNOT PROVE, STATED RATHER THAN IMPLIED.** `BR-CWP-010`
has two strands — the account set in the query, and the tenant. This suite runs
on in-memory SQLite (`config/settings/test.py`, hard-won law 14), which has no
row-level security at all, so the DATABASE's half of hard rule 1 is invisible
here and every case below would pass on a build with RLS switched off. The
companion script named in the Trace block is the strand this one cannot reach.
"""

from __future__ import annotations

import json
from datetime import date
from decimal import Decimal

import pytest

from apps.customers import models as customer_models
from apps.ledger import models as ledger_models, posting
from apps.portal import premises_statement
from apps.portal.seams import customers_seam
from apps.portal.session import AccountEntry, PortalPrincipal
from core import errors

from tests.ledger_le_fixtures import a_request, gl, line, make_accounts
from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared tenant fixtures
from tests.test_us_met_helpers import tenant_ctx

pytestmark = pytest.mark.django_db

#: The window the statement is asked for. Stated, never derived from a clock
#: (`BR-TEN-043`), so a reader can do the arithmetic without running anything.
START = date(2026, 9, 1)
END = date(2026, 9, 30)
A_DAY_IN_IT = date(2026, 9, 12)

#: R24c's own four figures, from the brief's p070. Nothing here is rounded or
#: recomputed: these are posted and then read back.
UNIT3_CHARGE = Decimal("196.00")
UNIT3_CREDIT = Decimal("96.00")
UNIT3_CLOSING = Decimal("100.00")
COMMON_CHARGE = Decimal("69.60")


def _principal(tenant, *account_ids, source="holder"):
    """A signed-in portal person holding exactly the ids named and no others.

    Built directly rather than through `credentials.create_credential` on
    purpose: what is under test is the SCOPING of a read given an account set,
    and constructing the set by hand is the only way to state *this person
    holds the master and nothing else* as a premise the test controls.
    `test_us_cwp_023_shell_scope.py` owns the question of whether the real
    sign-in derives the same set.
    """
    return PortalPrincipal(
        session_id="test-session",
        credential_id="test-credential",
        customer_id="test-customer",
        tenant_id=tenant.id,
        accounts=tuple(
            AccountEntry(account_id=str(one), permissions=("see",), source=source)
            for one in account_ids
        ),
    )


@pytest.fixture
def elm_street(brazos, dana):
    """Marina Bay with a TENANT's unit and the owner's MASTER, both posted.

    `make_accounts` already puts `ACC-1055` (unit `3B`) and `ACC-0009`
    (`MASTER`) on ONE premises — which is the shape `R24c` is about — so the
    cast is the ledger fixture's and only the postings and the `kind` flip are
    this file's.
    """
    with tenant_ctx(brazos):
        accounts = make_accounts(dana, brazos, {})
        master = accounts["ACC-0009"]
        master.kind = customers_seam.ACCOUNT_KIND_MASTER
        master.save(update_fields=["kind"])

        ar = gl(brazos, "1200", "asset")
        revenue = gl(brazos, "4100", "revenue")
        cash = gl(brazos, "1000", "asset")

        def post(key, debit, credit, amount, account):
            posting.post(
                a_request(
                    [
                        line(
                            debit,
                            ledger_models.SIDE_DEBIT,
                            amount,
                            account_id=account.id,
                        ),
                        line(
                            credit,
                            ledger_models.SIDE_CREDIT,
                            amount,
                            account_id=account.id,
                        ),
                    ],
                    key=key,
                    entry_date=A_DAY_IN_IT,
                )
            )

        # Unit 3's bill and its part payment — 196.00 − 96.00 = 100.00.
        post("p415|unit3|bill", ar, revenue, UNIT3_CHARGE, accounts["ACC-1055"])
        post("p415|unit3|payment", cash, ar, UNIT3_CREDIT, accounts["ACC-1055"])
        # The building's common-area charge on the owner's master — 69.60.
        post("p415|common|bill", ar, revenue, COMMON_CHARGE, master)

        premises_id = master.unit.premises_id
    return {
        "accounts": accounts,
        "master": master,
        "premises_id": premises_id,
        "elsewhere": accounts["ACC-1042"],
    }


def _read(principal, account_id):
    """The read, addressed by an ACCOUNT the caller holds — see the module
    docstring of `apps/portal/premises_statement.py` for why the subject is an
    account rather than a premises (it keeps a uuid out of the browser's
    address bar AND removes the id a stranger could supply)."""
    body, count = premises_statement.premises_statement(
        principal, account_id, start=START, end=END
    )
    return body, count


# ═══════════════════════════════════════════════════════════════════════════
# TC-1 — the landlord sees the $69.60 and NOTHING of Unit 3
# ═══════════════════════════════════════════════════════════════════════════
def test_p4_15_tc1__the_landlord_sees_their_master_and_only_their_master(
    brazos, elm_street
):
    """The ruling's own sentence, asserted: *"the $69.60, never Unit 3's
    $100.00"*."""
    who = _principal(brazos, elm_street["master"].pk)
    with tenant_ctx(brazos):
        body, count = _read(who, elm_street["master"].pk)

    assert count == 1, "one account held here, so one row"
    row = body["rows"][0]
    assert row["is_master"] is True
    assert Decimal(row["charges"]) == COMMON_CHARGE
    assert Decimal(row["closing"]) == COMMON_CHARGE
    assert Decimal(body["totals"]["closing"]) == COMMON_CHARGE
    assert Decimal(body["common_areas"]) == COMMON_CHARGE

    # ⚠ THE WHOLE BODY, not a field. See the module docstring.
    rendered = json.dumps(body)
    for forbidden in (str(UNIT3_CHARGE), str(UNIT3_CREDIT), str(UNIT3_CLOSING)):
        assert forbidden not in rendered, (
            f"{forbidden} belongs to Unit 3's customer and reached the landlord's "
            f"payload: {rendered}"
        )


# ═══════════════════════════════════════════════════════════════════════════
# TC-2 — and the leak does not run the other way either
# ═══════════════════════════════════════════════════════════════════════════
def test_p4_15_tc2__the_tenant_sees_their_own_hundred_and_not_the_common_areas(
    brazos, elm_street
):
    """A scoping bug that leaks UP and one that leaks DOWN are different bugs.

    ⚠ **`common_areas` IS ABSENT HERE AND IS NOT `0.00`** (`BR-CWP-093`). A
    zero would be a claim about what the building's common areas cost this
    month, which is not this reader's business and is not a figure this read
    ever computed.
    """
    unit3 = elm_street["accounts"]["ACC-1055"]
    who = _principal(brazos, unit3.pk)
    with tenant_ctx(brazos):
        body, count = _read(who, unit3.pk)

    assert count == 1
    row = body["rows"][0]
    assert row["is_master"] is False
    assert Decimal(row["closing"]) == UNIT3_CLOSING
    assert body["common_areas"] is None, "absent, never a zero"

    rendered = json.dumps(body)
    assert str(COMMON_CHARGE) not in rendered, (
        f"the owner's common-area charge reached a tenant: {rendered}"
    )


# ═══════════════════════════════════════════════════════════════════════════
# TC-3 — a premises you hold nothing at is NOT FOUND, never FORBIDDEN
# ═══════════════════════════════════════════════════════════════════════════
def test_p4_15_tc3__a_second_landlord_is_refused_and_learns_nothing(
    brazos, elm_street
):
    """`BR-CWP-010`'s posture. A 403 over a real id and a 404 over an invented
    one are distinguishable, and the difference is an oracle for *does this
    account exist on this utility*. Both answer the same way.

    ⚠ **THE STRANGER HERE IS A LANDLORD AT ANOTHER PROPERTY**, holding a real
    account of their own — not a signed-out caller. That is the case `P4.15`
    is actually about.

    ⚠ **THE REFUSAL IS ASSERTED TO BE THE SAME FOR BOTH**, not merely to be a
    refusal — which is the assertion that actually closes the oracle.
    """
    import uuid

    stranger = _principal(brazos, elm_street["elsewhere"].pk)
    with tenant_ctx(brazos):
        # A REAL account, at the property whose money they must not see.
        with pytest.raises(errors.NotFoundError) as real:
            _read(stranger, elm_street["master"].pk)
        with pytest.raises(errors.NotFoundError) as invented:
            _read(stranger, uuid.uuid4())

    # ⚠ **THE SAME EXCEPTION, AND THE SAME SERIALISED BODY.** `NotFoundError`
    # deliberately carries `audit_br_ref` SERVER-SIDE ONLY (core/errors.py), so
    # both refusals render byte-identically to the caller. Asserting the type
    # alone would pass over two 404s carrying different bodies, which is the
    # leak this case exists to close.
    assert type(real.value) is type(invented.value)
    assert str(real.value) == str(invented.value)


# ═══════════════════════════════════════════════════════════════════════════
# TC-4 — holding BOTH is the landlord who bills the tenants themselves
# ═══════════════════════════════════════════════════════════════════════════
def test_p4_15_tc4__holding_both_shows_both_with_the_master_last(
    brazos, elm_street
):
    """The brief's *"Not an exception"* case, p016: *"where the building bills
    the owner rather than the tenants, the owner **is** the account holder and
    sees it as their own."* Nothing special is built for it — holding the
    account IS the permission — and this case exists so that stays true.

    The master sorts LAST (`_row_order`): a common-area row read first invites
    the reading that it is the building's total.
    """
    both = _principal(
        brazos, elm_street["accounts"]["ACC-1055"].pk, elm_street["master"].pk
    )
    with tenant_ctx(brazos):
        body, count = _read(both, elm_street["master"].pk)

    assert count == 2
    assert [row["is_master"] for row in body["rows"]] == [False, True]
    assert Decimal(body["totals"]["closing"]) == UNIT3_CLOSING + COMMON_CHARGE


# ═══════════════════════════════════════════════════════════════════════════
# TC-5 — the address is WALKED, and no database id is on the page
# ═══════════════════════════════════════════════════════════════════════════
def test_p4_15_tc5__the_address_is_walked_and_carries_no_id(brazos, elm_street):
    """Hard rule 8 and B14 rule 31 in one case.

    The premises id is the ROUTE's value; what a reader sees is the address,
    composed nowhere but `premises`.
    """
    who = _principal(brazos, elm_street["master"].pk)
    with tenant_ctx(brazos):
        body, _ = _read(who, elm_street["master"].pk)

    assert body["address"] == "Marina Bay"
    assert str(elm_street["premises_id"]) not in json.dumps(body["rows"])


# ═══════════════════════════════════════════════════════════════════════════
# TC-6 — an inverted window is refused rather than answered empty
# ═══════════════════════════════════════════════════════════════════════════
def test_p4_15_tc6__an_inverted_window_is_refused_by_name(brazos, elm_street):
    """`account_ledger`'s own posture (`US-LED-009` TC-6): *"never an
    empty-but-plausible report"*. A statement that silently returned no rows
    for `to` before `from` is a document that looks like *you owe nothing*."""
    who = _principal(brazos, elm_street["master"].pk)
    with tenant_ctx(brazos):
        with pytest.raises(errors.ValidationError) as refused:
            premises_statement.premises_statement(
                who, elm_street["master"].pk, start=END, end=START
            )
    assert refused.value.code == errors.VAL_FORMAT


# ═══════════════════════════════════════════════════════════════════════════
# TC-7 — a login holding nothing at all reaches nothing
# ═══════════════════════════════════════════════════════════════════════════
def test_p4_15_tc7__an_empty_account_set_reaches_no_premises(brazos, elm_street):
    """The degenerate case, asserted because `pk__in=[]` is a shape that has
    surprised this repo before: an empty set must refuse, never match all."""
    nobody = _principal(brazos)
    with tenant_ctx(brazos):
        with pytest.raises(errors.NotFoundError):
            _read(nobody, elm_street["master"].pk)
