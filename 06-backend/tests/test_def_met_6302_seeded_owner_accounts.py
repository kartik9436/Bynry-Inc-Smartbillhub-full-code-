# ── Trace ──────────────────────────────────────────────
# Story:    US-TEN-019 (EP-TEN-03 — tenant sample data)   Screens: S14 (the
#           Premises list's Owner column — the screen the PO was looking at) ·
#           S17 / S21 (the Accounts list and the master account's Accounts tab)
# Change:   DEF-MET-6302 — PO 2026-09-23, verbatim: *"attach master accounts to
#           the sample data"*.
#           ⚠ AND BR-CUS-1094 (PO 2026-09-23, CLOSING OQ-CUS-12609), ruled the
#           same day — a VACANT unit is billed to its premises' master account.
#           NOT BUILT; case 5 asserts what is true TODAY and names the day it
#           stops being true.
# Rules:    BR-CUS-1010 · BR-CUS-068 as amended · BR-MET-400 · BR-MET-1181 ·
#           BR-MET-1030 · BR-CUS-1011 · BR-CUS-1024 · BR-MET-151 clause 3 ·
#           BR-TEN-057 · BR-TEN-060 · BR-TEN-063
# Tests:    this file
# Impacts:  apps/customers/sample_owner_accounts.py · apps/tenancy/sample_data.py
# ───────────────────────────────────────────────────────
"""**DEF-MET-6302 — the SEEDED estate must name its owners' accounts.**

WHY THIS FILE EXISTS WHEN `test_def709_seeded_master_account.py` ALREADY PASSES
-------------------------------------------------------------------------------
`DEF-709`'s suite proves the estate holds a master ACCOUNT. It never asks
whether an ADDRESS names one — and that is the whole of this defect: the
account existed, `premises.master_account_id` was NULL on all 79 rows, and the
Premises list's Owner column was therefore empty on every row of every tenant
this product has ever planted. Two different questions, one screen, and only
one of them was being asked.

⚠ **EVERY ASSERTION RUNS AGAINST THE ESTATE THE REAL SEEDERS PLANT**, through
those seeders' own entry points — `DEF-709`'s own discipline, for its own
reason: a test that builds its own premises and its own link reproduces the
defect rather than catching it.

⚠ **AND THE SECOND HALF IS AS IMPORTANT AS THE FIRST.** *Some address names an
account* would pass on a seed that filled every row, which is exactly what the
PO ruled out — *"a demo where all 80 properties have an identical master
account teaches a clerk nothing and hides the cases that matter"*. So the
count of addresses WITHOUT one is asserted too, and the three excluded
owner-occupier premises are named.
"""

import pytest

from apps.customers import models as customers_models
from apps.customers import sample_data as customers_sample
from apps.customers import sample_owner_accounts as owner_accounts
from apps.customers import selectors as customers_selectors
from apps.customers import services as customers_services
from apps.metering import models as metering_models
from apps.metering import sample_data as metering_sample
from apps.rating import sample_data as rating_sample
from core import sample_fixture as fixture

from tests.test_us_ten_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_ten_helpers import tenant_ctx
from tests.test_us_met_helpers import (  # noqa: F401 — brazos/dana are fixtures
    brazos,
    dana,
)

pytestmark = pytest.mark.django_db

#: The three addresses the rule deliberately passes over, and the reason each
#: one is passed over. Named rather than counted, because *"three were skipped"*
#: is true of the wrong three as well as the right three.
OWNER_OCCUPIED = ("77 Industrial Way", "403 Silver Creek Rd", "401 Quarry Hill Ct")


@pytest.fixture()
def seeded(brazos, dana):
    """The sample plant in the orchestrator's own order, plus the new block.

    `SAMPLE_MODULES` puts `customers:seed_sample_owner_accounts` immediately
    after the accounts block, and that ORDER is the fixture: the owner accounts
    must come after the estate's fifty or four of them would take numbers ahead
    of it and renumber all fifty (`BR-TEN-035`).
    """
    with tenant_ctx(brazos):
        rating_sample.seed_sample_records(dana)
        metering_sample.seed_sample_records(dana)
        customers_sample.seed_sample_records(dana)
        owner_accounts.seed_sample_owner_accounts(dana)
    return brazos, dana


def _declaring(tenant):
    return metering_models.Premises.objects.filter(
        tenant_id=tenant.id, deleted_at__isnull=True, master_account_id__isnull=False
    )


def _sample_premises(tenant):
    return metering_models.Premises.objects.filter(
        tenant_id=tenant.id, deleted_at__isnull=True, is_sample=True
    )


# ══════════════════════════════════════════════════════════════════════════
# 1 · THE DEFECT ITSELF — an ADDRESS names an account
# ══════════════════════════════════════════════════════════════════════════


def test_the_seeded_estate_has_addresses_that_name_their_owners_account(seeded):
    """**DEF-MET-6302, stated as the one assertion that would have caught it.**

    RED before this lane: `assert 0 >= 1`. Measured on a seeded `brazosbend`
    clone on 2026-09-23, **79 premises declared 0 master accounts** — the column
    `BR-MET-1181` added was written by no seeder in the product.
    """
    tenant, _ = seeded
    with tenant_ctx(tenant):
        assert _declaring(tenant).count() >= 1, (
            "DEF-MET-6302: at least one seeded address must name its owner's master "
            "account, or the Premises list's Owner column renders empty on every row"
        )


def test_it_is_not_every_address_and_the_absence_is_the_other_half(seeded):
    """PO, in the same instruction: *"a demo where all 80 properties have an
    identical master account teaches a clerk nothing and hides the cases that
    matter"*.

    ⚠ **A CHECK THAT ONLY ASSERTS PRESENCE PASSES ON A BLANKET FILL**, which is
    the thing that was ruled out — law 7 habit 2, *ask what would make this pass
    wrongly*. So both sides are counted and both must be non-zero.
    """
    tenant, _ = seeded
    with tenant_ctx(tenant):
        total = _sample_premises(tenant).count()
        declaring = _sample_premises(tenant).filter(master_account_id__isnull=False).count()
        assert declaring >= 1
        assert declaring < total, (
            f"{declaring} of {total} sample premises name an owner account — a blanket "
            "fill is the demo the PO ruled out"
        )


def test_the_owner_occupied_premises_are_left_alone_by_name(seeded):
    """`OWNER_ACCOUNT_MIN_UNITS` — the clause that excludes an owner-occupier.

    These three carry a NAMED owner and a single suite, and that name is their
    occupying customer: `Northwind Mfg.`, `Quarry Hill Diner`, `Creekside
    Laundromat`. A second account naming the same party would be the blanket
    fill wearing a rule.

    ⚠ **NAMED, NOT COUNTED**, because *"three were skipped"* is just as true of
    the wrong three.
    """
    tenant, _ = seeded
    with tenant_ctx(tenant):
        for address in OWNER_OCCUPIED:
            row = metering_models.Premises.objects.filter(
                tenant_id=tenant.id, address_line=address, deleted_at__isnull=True
            ).first()
            if row is None:  # pragma: no cover — the estate plants all three
                continue
            assert row.owner_manager, f"{address} should carry a named owner"
            assert row.master_account_id is None, (
                f"{address} is owner-occupied — its occupying customer IS its owner, so "
                "an owner account there names the same party twice"
            )


def test_no_address_without_a_named_owner_gets_one(seeded):
    """`BR-MET-151` clause 3 — a party is never read off a name, and an address
    that names NO party is not given one either.

    This is the clause that keeps the 62 single-family houses, the two
    uncategorised commercial units and the municipal depot out of it.
    """
    tenant, _ = seeded
    with tenant_ctx(tenant):
        offenders = [
            row.address_line
            for row in _sample_premises(tenant).filter(master_account_id__isnull=False)
            if not (row.owner_manager or "").strip()
        ]
        assert offenders == [], (
            f"{offenders} name an owner account and no owner — a party was invented"
        )


# ══════════════════════════════════════════════════════════════════════════
# 2 · WHAT THE ACCOUNTS ARE, AND WHAT THEY MUST NOT BE
# ══════════════════════════════════════════════════════════════════════════


def test_every_declared_account_is_a_master_account_of_this_tenant(seeded):
    """`BR-CUS-068` — an ordinary `accounts` row with `kind='master'`, and no
    new table. An ORDINARY account named here would bill a TENANT for their
    landlord's charges, which is the failure `BR-MET-400` was ruled to close."""
    tenant, _ = seeded
    with tenant_ctx(tenant):
        for premises in _declaring(tenant):
            account = customers_models.Account.objects.get(
                tenant_id=tenant.id, pk=premises.master_account_id
            )
            assert account.kind == customers_services.ACCOUNT_KIND_MASTER
            assert account.is_sample is True, "BR-TEN-057 — the tag is on the owning row"


def test_the_seeded_owner_accounts_cover_nothing_and_so_bill_nothing(seeded):
    """⛔ **THIS ASSERTS WHAT IS TRUE TODAY, AND IT NAMES THE DAY IT STOPS.**

    Every address this block opens an account for has ZERO common-area units, so
    each account covers nothing and produces no document — *no lines, no
    document*, the 2026-08-31 ruling's own general rule.

    ⚠ **`BR-CUS-1094` WAS RULED THE SAME DAY THIS LANE RAN (`OQ-CUS-12609`,
    CLOSED 2026-09-23): a VACANT unit is billed to its premises' master
    account.** Billing cannot do that yet, so this case is green and honest. It
    is **not** a claim that these accounts can never bill — when that ruling is
    built, `Kestrel Park ph. 2`'s twelve vacant units acquire this master as
    their payer, and the mechanism will be OCCUPANCY AT RUN TIME rather than
    `covered_unit_ids`. **A lane building `BR-CUS-1094` should expect to
    rewrite this case rather than to satisfy it** — that is a hold with a test
    behind it rather than a promise nobody is keeping (hard-won law 2).

    ⚠ **`500 Main St` IS EXCLUDED, AND THAT IS THE POINT OF THE EXCLUSION.**
    Its account is `DEF-709`'s, it already covered that building's one common
    area before this lane existed, and this block only wrote its DECLARATION. A
    test that demanded zero coverage everywhere would be asserting that this
    lane had changed something it deliberately did not touch.
    """
    tenant, _ = seeded
    with tenant_ctx(tenant):
        for premises in _declaring(tenant).exclude(
            address_line=fixture.CR030_COMMON_AREA_ADDRESS
        ):
            account = customers_models.Account.objects.get(
                tenant_id=tenant.id, pk=premises.master_account_id
            )
            covered = customers_selectors.covered_unit_ids(account)
            assert covered == [], (
                f"{premises.address_line}'s owner account covers {covered} — this fixture "
                "must not make a charge flow anywhere new while OQ-CUS-12609 is open"
            )


def test_a_landlord_with_two_addresses_holds_one_account_for_both(seeded):
    """`BR-CUS-1011` reads *at most one owner account per address*, never
    *exactly one per address* — and `premises.master_account`'s own `PROTECT`
    comment states the intended shape: *"an account twelve addresses are billed
    through"*.

    Measured on a live clone: `181 Willow Bend Dr` and `183 Cedar Ridge Way`
    both declare `AC-2026-00054`. They share one typed owner record, so the door
    takes its typed-owner branch and `ensure_owner_master_account` is *ensure*
    for the OWNER. The estate now demonstrates the case a clerk meets first —
    one landlord, several buildings — instead of only describing it.
    """
    tenant, _ = seeded
    with tenant_ctx(tenant):
        by_owner: dict[str, set[str]] = {}
        for premises in _declaring(tenant):
            if premises.owner_manager:
                by_owner.setdefault(premises.owner_manager, set()).add(
                    str(premises.master_account_id)
                )
        shared = {name: ids for name, ids in by_owner.items() if len(ids) == 1}
        assert any(
            len([p for p in _declaring(tenant) if p.owner_manager == name]) > 1
            for name in shared
        ), "no seeded landlord holds one account across two addresses"


# ══════════════════════════════════════════════════════════════════════════
# 3 · THE BLOCK'S OWN BEHAVIOUR
# ══════════════════════════════════════════════════════════════════════════


def test_a_replay_writes_nothing(seeded):
    """`BR-TEN-010` / `BR-TEN-063` — a replay writes nothing and changes no
    count. Proved on live PostgreSQL too: a second `load_sample_data` reported
    `0 row(s)` for this block and left the declaration audit rows at five, not
    ten."""
    tenant, dana_user = seeded
    with tenant_ctx(tenant):
        before = _declaring(tenant).count()
        accounts_before = customers_models.Account.objects.filter(tenant_id=tenant.id).count()
        assert owner_accounts.seed_sample_owner_accounts(dana_user) == 0
        assert _declaring(tenant).count() == before
        assert (
            customers_models.Account.objects.filter(tenant_id=tenant.id).count()
            == accounts_before
        )


def test_the_report_names_what_it_passed_over_with_a_number(seeded):
    """Hard-won law 7's fifth shape — *a declared blind spot with no NUMBER
    beside it is indistinguishable from an empty one*.

    `G32` reported `0 unresolved` truthfully over 21 refusals it could not see,
    and `DEF-MET-4288`'s address allow-list excluded every later estate in
    silence. So the report carries both sides, and every skipped row carries the
    clause that skipped it."""
    tenant, _ = seeded
    with tenant_ctx(tenant):
        report = owner_accounts.owner_account_report()
        assert report["sample_premises"] > 0
        assert report["selected"], "nothing selected — the fixture demonstrates nothing"
        assert report["skipped"], "nothing skipped — that would be the blanket fill"
        assert report["sample_premises"] == len(report["selected"]) + len(report["skipped"])
        for row in report["skipped"]:
            assert row["reason"] in {
                owner_accounts.SKIP_NO_OWNER_NAMED,
                owner_accounts.SKIP_SINGLE_UNIT,
                owner_accounts.SKIP_OWNER_OCCUPIER,
                owner_accounts.SKIP_NO_TAX_ID,
            }


def test_the_panel_note_states_both_counts_in_short_sentences(seeded):
    """`BR-TEN-060` + B14 rule 33 — the sentence a clerk reads on the Sample
    data panel is FACTS, each capped at six words, and carries no rule id.

    `DEF-3224` is why it exists at all: metering's own refusal sentence went to
    `logger.info` and nowhere else, and a utility received an estate missing
    `$576.00` a month of electric with nothing on screen saying so.
    """
    tenant, _ = seeded
    with tenant_ctx(tenant):
        note = owner_accounts.owner_account_note()
        assert note
        sentences = [s.strip() for s in note.split(".") if s.strip()]
        assert len(sentences) >= 2, note
        for sentence in sentences:
            assert len(sentence.split()) <= 6, f"B14 rule 33: {sentence!r}"
        assert "BR-" not in note and "DEF-" not in note and "OQ-" not in note


def test_every_owner_that_gets_an_account_is_identified(seeded):
    """`BR-CUS-1024`, PO 2026-09-01: *"Without identifier we cannot create
    Customer ID or master account ot regular account"*.

    A free-text owner name is a NAME and not an identity, so the fixture states
    a reserved Tax ID for each owner that receives an account — and an owner it
    has NOT identified is reported rather than given one the product's own door
    would refuse.
    """
    tenant, _ = seeded
    with tenant_ctx(tenant):
        for premises in _declaring(tenant):
            name = (premises.owner_manager or "").strip()
            declared = (
                fixture.CR030_COMMON_AREA_OWNER_TAX_ID
                if premises.address_line == fixture.CR030_COMMON_AREA_ADDRESS
                else fixture.OWNER_ACCOUNT_TAX_IDS.get(name)
            )
            assert declared, f"{name} holds an owner account and the fixture states no tax id"
            assert declared.startswith("00-"), (
                "a fixture tax id must sit in the reserved, never-issued range — a demo "
                "utility must not model a real business's tax number"
            )
