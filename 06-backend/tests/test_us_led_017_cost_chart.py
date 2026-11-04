# ── Trace ──────────────────────────────────────────────
# Story:    US-LED-017 (cost-of-service chart section: proposed for finance
#           signature, seeded only for the services a tenant sells — TC-1
#           Brazos Bend's seven rows and NOT 5145, TC-2 Silver Creek's two,
#           TC-3 gas enabled later mints 5140 at that moment, TC-4 the tenant's
#           own pointer survives a re-seed, TC-5 nothing presents an unsigned
#           code as signed, TC-6 delete blocked / code frozen once referenced,
#           TC-7 isolation)   Screens: S56 · S73
# Rules:    BR-LED-037 (the section is an addition to B5 line 74 ❄️ and needed a
#           finance re-sign via HUMAN-GUIDE §6 — TAKEN 2026-08-18; until signed
#           a row seeds marked-unsigned, which now governs FUTURE rows and is
#           held under test on a synthetic one) · BR-LED-038 (seeded only for services sold; a
#           tenant's own pointer is never overwritten by a re-seed) ·
#           BR-LED-015 (every chart change writes audit_log) · BR-LED-028 (the
#           chart is the ONLY place a captured cost is classified)
# ───────────────────────────────────────────────────────
"""The eight accounts a captured supplier invoice can point at — all signed
since 2026-08-18 (this line read "none signed" until then).

**The state this corrects, factually** (decision log 2026-08-12 and 2026-08-15):
the seeded chart held exactly TWO expense accounts — 6800 Bank fees and 6900 Bad
debt — plus 6950 Deposit interest expense, every one of them arising from
meter-to-cash itself. Purchased power, purchased water, purchased gas, O&M and
infrastructure had **no accounts at all**, so a captured supplier invoice had
nowhere to point.

**THE TEST THIS FILE EXISTS FOR** is
`test_us_led_017_tc5__no_surface_presents_an_unsigned_cost_code_as_signed`.
Everything else here is mechanism; that one is the rule. B5 line 74 is ❄️ FROZEN
and finance-signed 2026-08-08 and it carries no cost accounts, so all eight were
this lane's PROPOSAL and a finance re-sign through HUMAN-GUIDE §6 was the only
thing that could change that. **B5 was not edited by this lane, and was not
edited by the re-sign either.**

⚠ **THE RE-SIGN LANDED ON 2026-08-18** — the Product Owner, the sign-off
authority per their own ruling of 2026-08-11, ratified the eight codes and names
(with 4180 Budget billing variance) in the working chat session, shown in plain
English, with no dollar figure attached to any of them. So **the rule's test has
zero real subjects left**, and a guard with no subject passes vacuously, which
reads as protection and is none. It is therefore kept alive on a SYNTHETIC
unsigned row: the day a lane proposes another account finance has not signed,
the surfaces still have to refuse to present it as signed. The precedent is
`test_us_not_005_an_uncatalogued_class_is_refused_with_its_reason` (CR-011 item
9), which did the same when its last uncatalogued class was ruled away.
"""

from decimal import Decimal

import pytest
from django.utils import timezone

from apps.ledger import chart, models as ledger_models, selectors as ledger_selectors
from apps.ledger import services as ledger_services
from apps.tenancy import services as tenancy_services

from tests.cost_of_service_fixtures import enable_le11_services, with_monthly_fiscal_year
from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared tenant fixtures
from tests.test_us_met_helpers import (
    lonestarridge_payload,
    provisioned_tenant,
    staff_actor,
    tenant_ctx,
)

pytestmark = pytest.mark.django_db

#: BR-LED-037's proposed section, transcribed from the rule rather than read
#: back out of `chart.py` — a test that imported the list it is checking would
#: agree with any list.
PROPOSED = {
    "5100": "Purchased power",
    "5110": "Purchased water",
    "5120": "Sewer treatment & disposal",
    "5130": "Trash hauling & disposal",
    "5140": "Purchased gas",
    "5145": "Broadband transport",
    "5200": "Operations & maintenance",
    "5300": "Infrastructure",
}


def codes_for(tenant):
    with tenant_ctx(tenant):
        return set(
            ledger_models.LedgerAccount.objects.filter(tenant=tenant).values_list("code", flat=True)
        )


# ═══════════════════════════════════════════════════════════════════════════
# TC-1 — the whole cost section seeds for every tenant (CR-010 B-9, 2026-08-17)
# ═══════════════════════════════════════════════════════════════════════════
def test_us_led_017_tc1__the_full_cost_section_seeds_at_provisioning(brazos, dana):
    """⚠ REWRITTEN 2026-08-18 — this pinned *"cost section seeded per service
    sold; 5145 Broadband transport is NOT seeded"* under BR-LED-038's
    narrowing. CR-010 B-9 reverses it (PO 2026-08-17, verbatim: *"9 - A full
    ~40 accounts for every tenant, as you said"*): ALL EIGHT proposed rows seed
    at provisioning, 5145 included, whatever the tenant sells. Every row still
    carries no designation — the reversal changed WHICH rows land, not their
    signature state.

    ⚠ AMENDED 2026-08-18: this said every row is "still UNSIGNED (BR-LED-037's
    re-sign is still owed)". The re-sign arrived later that day (PO, working
    chat session, the eight codes and names with no figure attached), so the
    owed signature is paid. The seeding assertions below are untouched by it —
    which is the point of asserting the two questions separately.
    """
    with tenant_ctx(brazos):
        enable_le11_services(dana)

    codes = codes_for(brazos)
    assert set(PROPOSED) <= codes  # all eight, 5145 included

    with tenant_ctx(brazos):
        rows = {
            row.code: row
            for row in ledger_models.LedgerAccount.objects.filter(
                tenant=brazos, code__startswith="5"
            )
        }
    for code, name in PROPOSED.items():
        assert rows[code].name == name, f"{code} seeded as {rows[code].name!r}, want {name!r}"
        assert rows[code].type == "expense"
        # No designation, and the 2026-08-18 re-sign did NOT change that: what
        # was ratified is the eight codes and names, not a slot for one of them
        # in the twelve-designation enumeration. Giving one a designation is a
        # separate ruling AND a migration (see `chart.GL_DESIGNATIONS`).
        assert rows[code].designation is None


def test_us_led_017_tc1__every_seeded_cost_row_is_signed_after_the_2026_08_18_addendum(
    brazos, dana
):
    """⚠ **AMENDED 2026-08-18 — THE ADDENDUM IS SIGNED, so this test's subject
    changed and its assertion is INVERTED with the ruling named.**

    It read *"each row renders the `unsigned` marker until the B5 addendum is
    signed"* — the clause "until … signed" is the amendment condition, and it
    was met: the Product Owner re-signed all eight cost rows and 4180 on
    2026-08-18 in the working chat session, having been shown the nine codes and
    names in plain English with the statement that no dollar figure attaches to
    any of them and that B5 itself stays frozen.

    So the eight are now offered as SIGNED, and the marker must be gone —
    leaving a signed account marked `unsigned` would tell a finance reviewer
    that ratified rows still need their attention.
    """
    with tenant_ctx(brazos):
        enable_le11_services(dana)
        offered = {row["code"]: row for row in ledger_selectors.cost_accounts()}

    # All eight since CR-010 B-9's full seed (5145 included).
    for code in PROPOSED:
        assert offered[code]["unsigned"] is False, f"{code} still offered as unsigned"
        assert not offered[code]["unsigned_reason"], f"{code} carries a stale re-sign reason"

    # The tenant's own expense accounts are NOT marked: nobody proposed them on
    # finance's behalf. 6800/6900/6950 are transcribed from B5 line 74 ❄️.
    for code in ("6800", "6900", "6950"):
        assert offered[code]["unsigned"] is False


def test_us_led_017_tc1__the_top_up_mint_audits_with_its_signature_state(
    brazos, dana, audit_rows, monkeypatch
):
    """BR-LED-015 — every chart change audits, and the trail records
    `finance_signed` at the moment the account is minted, because that is the
    row a finance reviewer will be reading.

    ⚠ AMENDED 2026-08-18 (CR-010 B-9): on a full-seed tenant enabling Gas mints
    nothing (5140 already exists), so the narrowing-era state is reconstructed
    first — the account hard-removed while nothing references it — and the
    enablement's TOP-UP mint is what audits `source: service_enabled`.

    ⚠ **AMENDED AGAIN 2026-08-18 — THE RE-SIGN, AND THE SUBJECT WENT WITH IT.**
    This pinned `finance_signed: False` on the minted 5140. The Product Owner
    finance re-signed all eight cost rows and 4180 that day in the working chat
    session, having been shown the nine codes and names in plain English with
    the statement that no dollar figure attaches to any of them and that B4/B5
    stay ❄️ FROZEN and were not edited. So the real mint now audits **True**,
    which is what the first half asserts.

    **The second half keeps the MECHANISM under test on a synthetic unsigned
    row**, because a trail that only ever records True would pass just as
    happily if the flag had been replaced by the constant `True` — and the
    whole point of the field is the day it has to say False. `signed=False` is
    put back on 5140 for the length of the test only, and the mint must report
    it. Same move as `test_us_not_005`'s uncatalogued-class case when its last
    real subject was ruled away (CR-011 item 9).
    """

    def _reconstruct_narrowing_era_gas():
        with tenant_ctx(brazos):
            from apps.tenancy import models as tenancy_models

            # A narrowing-era tenant has neither the gas SERVICE ROW (mandate 4
            # postdates it) nor the 5140 account. The row must go first: its
            # PROTECT FK references the revenue account, and a present-but-off
            # row would make the toggle a plain flag flip that mints nothing —
            # which is correct for a tenant whose own chart edit removed the
            # account.
            tenancy_models.TenantService.objects.filter(tenant=brazos, service__code="gas").delete()
            ledger_models.LedgerAccount.objects.get(tenant=brazos, code="5140").delete()

    def _mint_5140_and_read_the_trail():
        audit_rows.clear()
        with tenant_ctx(brazos):
            tenancy_services.update_tenant_service(dana, "gas", {"enabled": True})
        minted = [
            row
            for row in audit_rows
            if row["action"] == "ledger_account.created" and row["after"]["code"] == "5140"
        ]
        assert len(minted) == 1
        return minted[0]

    # ── the LAW as of 2026-08-18: the seeded 5140 is signed and audits so ────
    _reconstruct_narrowing_era_gas()
    row = _mint_5140_and_read_the_trail()
    assert row["after"]["finance_signed"] is True, (
        "5140 was finance re-signed on 2026-08-18 and the trail says a reviewer still has "
        "to look at it"
    )
    assert row["after"]["source"] == "service_enabled"

    # ── the MECHANISM, on a row that is unsigned only inside this test ───────
    unsigned_5140 = tuple(
        chart.SeedAccount(r.code, r.name, r.type, r.designation, r.code != "5140")
        for r in chart.COST_OF_SERVICE_CHART
    )
    monkeypatch.setattr(chart, "COST_OF_SERVICE_CHART", unsigned_5140)
    _reconstruct_narrowing_era_gas()
    resigned = _mint_5140_and_read_the_trail()
    assert resigned["after"]["finance_signed"] is False, (
        "the trail records the row's OWN signature flag; an account minted without one must "
        "say so at the moment it is minted"
    )
    assert resigned["after"]["source"] == "service_enabled"


# ═══════════════════════════════════════════════════════════════════════════
# TC-2 / TC-3 — the PO's own worked case, on the cost ladder
# ═══════════════════════════════════════════════════════════════════════════
def test_us_led_017_tc2__silver_creek_water_gets_the_whole_cost_section_too():
    """⚠ REWRITTEN 2026-08-18 — this pinned Silver Creek Water at *"5110 and
    5120 only"*. CR-010 B-9 (PO 2026-08-17: *"9 - A full ~40 accounts for
    every tenant, as you said"* · New mandate 4: *"more is better ; less is
    contraint"*) reverses the narrowing: every tenant gets all eight cost rows
    at provisioning, and a utility that wants fewer lines deactivates them on
    S56 — its own act, protected by US-LED-005 rule 1."""
    silver, _ = provisioned_tenant(
        lonestarridge_payload(
            name="Silver Creek Water", subdomain="silvercreekcost", services=["water", "sewer"]
        )
    )
    codes = codes_for(silver)
    assert set(PROPOSED) <= codes  # all eight — 5100/5130/5140/5145 included now


def test_us_led_017_tc3__the_top_up_still_mints_5140_for_a_narrowing_era_tenant():
    """⚠ REWRITTEN 2026-08-18 — B-9's own boundary sentence:
    *"`ensure_service_revenue_accounts` keeps working as the lookup+top-up
    path."* A tenant provisioned under the narrowing (2026-08-11 → 2026-08-17)
    has no 5140; the full seed never reached it (hard-won law 4). That state is
    reconstructed and enabling Gas through `update_tenant_service` — the S8
    write path — must mint 5140 at that moment, exactly as under BR-LED-038.
    """
    silver, _ = provisioned_tenant(
        lonestarridge_payload(
            name="Silver Creek Water", subdomain="silvercreekgascost", services=["water", "sewer"]
        )
    )
    actor = staff_actor(silver, "system_admin", "ops@silvercreekcost.test")
    with tenant_ctx(silver):
        # Reconstruct the narrowing-era shape: no gas cost account, no revenue
        # account, no gas service row (delete order respects the PROTECT FKs).
        from apps.tenancy import models as tenancy_models

        tenancy_models.TenantService.objects.filter(tenant=silver, service__code="gas").delete()
        ledger_models.LedgerAccount.objects.get(tenant=silver, code="5140").delete()
        ledger_models.LedgerAccount.objects.get(tenant=silver, code="4140").delete()
        assert not ledger_models.LedgerAccount.objects.filter(tenant=silver, code="5140").exists()

        tenancy_services.update_tenant_service(actor, "gas", {"enabled": True})

        gas = ledger_models.LedgerAccount.objects.get(tenant=silver, code="5140")
        assert (gas.code, gas.name, gas.type) == ("5140", "Purchased gas", "expense")
        assert ledger_selectors.cost_account_for_service("gas").pk == gas.pk


# ═══════════════════════════════════════════════════════════════════════════
# TC-4 — the tenant's own pointer survives a re-seed (BR-LED-038)
# ═══════════════════════════════════════════════════════════════════════════
def test_us_led_017_tc4__a_tenants_own_account_survives_a_reseed(brazos, dana):
    """*"A tenant points purchased water at its own existing `5115 · Raw water
    purchases` and a re-seed runs → the tenant's pointer SURVIVES."*

    The BR-BIL-067 protection, extended to the cost ladder: the seed inserts
    what is MISSING and never rewrites what is there.
    """
    with tenant_ctx(brazos):
        own = ledger_models.LedgerAccount.objects.create(
            tenant=brazos, code="5115", name="Raw water purchases", type="expense"
        )
        # The tenant retires the seeded 5110 in favour of their own (IS-1
        # deactivate-first — a chart account in use is never hard-deleted).
        seeded = ledger_models.LedgerAccount.objects.get(tenant=brazos, code="5110")
        seeded.name = "Purchased water (legacy)"
        seeded.save()

        ledger_services.seed_chart_of_accounts(dana)

        assert (
            ledger_models.LedgerAccount.objects.get(tenant=brazos, code="5110").name
            == "Purchased water (legacy)"
        ), "the re-seed renamed a row the tenant had edited"
        assert ledger_models.LedgerAccount.objects.filter(tenant=brazos, code="5115").count() == 1
        assert own.pk in {
            row.pk for row in ledger_models.LedgerAccount.objects.filter(tenant=brazos)
        }
        # And their own account is offerable, unmarked — nobody proposed it on
        # finance's behalf.
        offered = {row["code"]: row for row in ledger_selectors.cost_accounts()}
        assert offered["5115"]["unsigned"] is False


# ═══════════════════════════════════════════════════════════════════════════
# TC-5 — THE RULE. Nothing presents an unsigned code as finance-signed.
# ═══════════════════════════════════════════════════════════════════════════
def test_us_led_017_tc5__no_surface_presents_an_unsigned_cost_code_as_signed(monkeypatch):
    """BR-LED-037, and the assertion the whole story is for.

    B5 line 74 is ❄️ FROZEN, finance-signed 2026-08-08, and it carries **no cost
    accounts at all**. All eight of BR-LED-037's codes were therefore a PROPOSAL,
    and a finance re-sign via HUMAN-GUIDE §6 was the only thing that could change
    that — never an inline edit of B5 and never a lane's decision.

    It read: *"This test goes RED the day somebody drops `signed=False` from a
    row without a signature. When finance DOES re-sign, the change is one word
    per row plus this figure — the same shape the 4160/4170 addendum took on
    2026-08-11."*

    ⚠ **FINANCE RE-SIGNED ON 2026-08-18 AND IT WAS EXACTLY THAT CHANGE.** The
    Product Owner — the sign-off authority per their own ruling of 2026-08-11 —
    ratified the eight codes and names in the working chat session, shown in
    plain English (**5100 Purchased power · 5110 Purchased water · 5120 Sewer
    treatment & disposal · 5130 Trash hauling & disposal · 5140 Purchased gas ·
    5145 Broadband transport · 5200 Operations & maintenance · 5300
    Infrastructure**), with the explicit statement that **no dollar figure is
    attached to any of them** and that B4/B5 stay ❄️ FROZEN and were not edited.
    A signature covers only what was shown: an amount, a rate or a default
    posted to one of these accounts is NOT covered and needs its own ruling.

    ⚠ **AND THE SUBJECT OF THE OLD ASSERTION IS NOW GONE, WHICH IS THE DANGEROUS
    PART.** There are zero unsigned cost codes, so *"no surface presents an
    unsigned cost code as signed"* would pass over an empty set no matter how
    badly the surfaces behaved — a vacuous guard that reads as protection and is
    none. **So the mechanism is driven from a SYNTHETIC unsigned code** (5110,
    for the length of this test only), and the surfaces must still refuse to
    present it as signed. Precedent: CR-011 item 9 kept
    `test_us_not_005`'s uncatalogued-class case alive the same way.

    The synthetic half is not decoration. `apps/ledger/services._chart_row`
    derived `finance_signed` from *"is this code in the cost section"* rather
    than from the signature, so from the moment of the re-sign S56 served eight
    RATIFIED accounts as unsigned — TC-5's failure pointed the other way. This
    half is what holds that fixed.
    """
    # ── the LAW as of 2026-08-18 ─────────────────────────────────────────────
    #
    # ⚠ **REWRITTEN 2026-09-01 (CR-060 C15 · task T5) — NOT DELETED, AND THE
    # DISTINCTION IS THE WHOLE POINT.** This asserted
    # `PENDING_FINANCE_RE_SIGN_COST == ()`, which was TRUE while the eight
    # cost-of-service rows were the only cost rows in the chart. C15 adds
    # FOURTEEN more, every one of them `signed=False` and awaiting a finance
    # re-sign through HUMAN-GUIDE §6 — the same route 4160/4170, 4180 and 4300
    # each took — so that tuple is no longer empty and never will be until
    # somebody signs them.
    #
    # **The LAW this test holds has not changed:** the eight the Product Owner
    # ratified on 2026-08-18 are signed, and no code edit may un-sign them. That
    # is what the two assertions below say, stated about the eight specifically
    # rather than about whatever happens to be in the tuple. Deleting this test
    # instead would have lost the record of WHY those eight are signed at all,
    # which is the mistake CR-060's own T6a row warns against on the other side
    # of this module.
    assert [row.code for row in chart.COST_OF_SERVICE_CHART if not row.signed] == [], (
        "a cost-of-service account lost its signature and no re-sign is recorded — a "
        "signature is a HUMAN-GUIDE §6 re-sign, never a code edit"
    )
    assert set(chart.PENDING_FINANCE_RE_SIGN_COST).isdisjoint(
        {row.code for row in chart.COST_OF_SERVICE_CHART}
    ), (
        "one of the eight cost-of-service codes the PO finance re-signed on 2026-08-18 is "
        "being served as PENDING a signature. The signature is recorded; this is a drift in "
        "the derivation, not a missing re-sign"
    )
    # And the fourteen C15 rows ARE pending, every one of them. A widened
    # category whose account quietly seeded `signed=True` would be a lane
    # claiming a finance signature nobody gave (US-LED-017 TC-5's own failure,
    # pointed the other way).
    assert [row.code for row in chart.WIDENED_COST_CHART if row.signed] == [], (
        "a CR-060 C15 widened cost account seeded as finance-signed. B5 line 74 is ❄️ FROZEN "
        "and carries no cost accounts at all — a new one seeds `signed=False` and waits for a "
        "HUMAN-GUIDE §6 re-sign"
    )
    assert set(chart.PENDING_FINANCE_RE_SIGN_COST) == {
        row.code for row in chart.WIDENED_COST_CHART
    }, (
        "the pending tuple and the widened chart disagree — it is DERIVED from the rows so "
        "that it cannot, and a disagreement means somebody listed it by hand"
    )
    # The eight ratified rows, by code AND name, because the names are half of
    # what was put to the PO and a rename is not covered by that signature.
    assert {row.code: row.name for row in chart.COST_OF_SERVICE_CHART} == PROPOSED
    # The route is still named IN THE CODE, so the next unsigned row cannot be
    # waved through on a comment.
    assert "HUMAN-GUIDE §6" in chart.COST_SECTION_RE_SIGN_SOURCE
    assert "❄️ FROZEN" in chart.COST_SECTION_RE_SIGN_SOURCE

    # ── the MECHANISM, on a code that is unsigned only inside this test ──────
    class _Account:
        """The two attributes both surfaces read, and nothing else."""

        def __init__(self, code):
            self.pk = f"synthetic-{code}"
            self.code = code
            self.name = f"{code} under test"
            self.type = "expense"
            self.designation = None
            # ⚠ ADDED 2026-09-02 (CR-061 statement (1)). `_chart_row` now reads
            # `category`, so a stand-in missing it raises `AttributeError` and
            # this guard fails for a reason that has nothing to do with the rule
            # it holds. The class comment above says "the two attributes both
            # surfaces read"; it has always been more than two, and a stand-in
            # for a model row has to carry every field its readers touch.
            self.category = None
            self.deleted_at = None
            self.qbo_ref = None
            self.xero_ref = None
            self.created_at = None

    monkeypatch.setattr(chart, "PENDING_FINANCE_RE_SIGN_COST", ("5110",))

    # S73's GL picker.
    offered = ledger_selectors.cost_account_row(_Account("5110"))
    assert offered["unsigned"] is True
    assert "HUMAN-GUIDE §6" in offered["unsigned_reason"]

    # S56's chart panel — the row that got this wrong in the other direction.
    assert ledger_services._chart_row(_Account("5110"))["finance_signed"] is False

    # And a code nobody proposed on finance's behalf is untouched by either.
    assert ledger_selectors.cost_account_row(_Account("5100"))["unsigned"] is False
    assert ledger_services._chart_row(_Account("5100"))["finance_signed"] is True


def test_us_led_017_tc5__the_signed_chart_is_untouched_by_this_section():
    """The other half of the same rule: adding a PROPOSAL must not disturb what
    finance already signed.

    `SEED_CHART` is the machine copy of B5 line 74 plus the dated 4160/4170
    addendum. The cost section lives in its own tuple, so a reader of the signed
    chart cannot pick up a proposal by iterating it — which is how a proposal
    would come to be presented as law.
    """
    signed_codes = {row.code for row in chart.SEED_CHART}
    assert signed_codes.isdisjoint(set(PROPOSED)), "a proposed cost code entered SEED_CHART"
    # AMENDED 2026-08-18: this pinned `== ()`, then `== ("4180",)` when the PO
    # ruled 4180 into the chart with `signed=False` (CR-010 B-8, 2026-08-17,
    # "8 - A"), and is back to `== ()` now that finance re-signed 4180 the same
    # day it re-signed the eight cost rows. The question this assertion asks is
    # unchanged through all three states — no COST code may ride the signed
    # chart's pending list, and it stays a DIFFERENT list from the cost
    # section's however empty both happen to be.
    # ⚠ **AMENDED AGAIN 2026-09-01 (`DEF-2411`) — `()` HAD BEEN WRONG SINCE
    # 2026-08-28 AND THIS TEST HAD BEEN RED THAT WHOLE TIME.** The tuple gained
    # **4300 Customer discounts (contra-revenue)**, seeded `signed=False` by the
    # `DEF-536` discount lane. Its human-review row is still
    # `HUMAN-REVIEW-PENDING` and says so in its own words: *"A SIGNATURE ON
    # THOSE IS NOT A FINANCE RE-SIGN OF THE CHART … Until that lands the row
    # carries signed=False."* **So 4300 genuinely awaits its re-sign** and the
    # pin names it, exactly as `()` → `("4180",)` was done above.
    #
    # ⚠ **THE SIBLING TEST WAS RE-PINNED THAT DAY AND THIS ONE WAS MISSED.**
    # `tests/test_us_led_005_gl_designations.py` moved to `("4300",)` on
    # 2026-08-28; two files pin one tuple and only one was updated. **The cost
    # of leaving it: a standing red attributes itself to whoever runs the suite
    # next** — it cost the CR-060 T5 lane real time proving the failure was not
    # its own.
    #
    # ⚠ **NAMING IT IS STRONGER THAN `()` AND THAT IS WHY THIS SHAPE WAS
    # CHOSEN**, per the decision log's own judgment on amending tests to
    # rulings: `== ()` *"could only ever say nothing is pending … it would have
    # gone GREEN the day somebody marked 4300 signed with no ruling behind
    # it"*. Named, it fails in BOTH directions.
    #
    # **The question this assertion asks is unchanged through all four states:**
    # no COST code may ride the SIGNED chart's pending list, and it stays a
    # DIFFERENT list from the cost section's. 4300 is a REVENUE code, so that
    # question was satisfied throughout — `()` was a proxy that happened to be
    # true on 2026-08-18. The `isdisjoint` line below asks it directly.
    # 4155 Fire joined on 2026-09-02 (`CR-063`, the eleventh utility service).
    # Both are REVENUE codes, so the question this assertion actually asks — no
    # COST code rides the SIGNED chart's pending list — is satisfied by both,
    # exactly as it was by 4760 alone and by 4300 before it.
    # ⚠ **NINE MORE JOINED ON 2026-09-02 (`CR-066`), AND THE PIN MOVES WITH THEM
    # RATHER THAN BEING WIDENED INTO A COUNT.** `4600` Connection & new-service
    # fees · `4610` Disconnection & reconnection fees · `4630` Field-service &
    # meter fees · `4640` Equipment recovery & penalties · `4650` Billing &
    # payment fees · `4700` Billing adjustment · `4710` Leak adjustment · `4720`
    # Rate / meter correction · `4730` Customer credit. They arrived on exactly
    # the posture 4160, 4170, 4180, 4760 and 4155 each arrived on: **the Product
    # Owner approved the MAPPING — which charge code and which adjustment
    # reason posts where — having been shown every name and number in plain
    # English, and an approval of a mapping is not a finance signature on the
    # chart.** Only a dated HUMAN-GUIDE §6 addendum makes any of them
    # `signed=True`.
    # ⚠ **AMENDED 2026-09-23 (`DEF-LED-6224`) — THIS PIN HAD BEEN RED SINCE
    # 2026-09-03**, when the PO split solar and battery (*"We need seperate code
    # for Solar 4150 and Battery 4150"*): `4150` re-entered the unsigned list
    # because what finance signed was an account covering the PAIR, and `4165`
    # arrived beside it. Three weeks of lanes ran past the failure. `6850 Cash
    # over and short` joins on 2026-09-23 (`CR-136-BRC07` §3.3) — the PO ruled
    # that a counted drawer difference must POST and named no code, no name and
    # no type.
    # **The tuple stays EXACT and is kept current in the commit that grows it.**
    # The question this case asks is whether the SIGNED chart's unsigned list
    # and the PROPOSED cost codes stay disjoint, and a loose pin cannot ask it.
    assert chart.PENDING_FINANCE_RE_SIGN == (
        "4150",
        "4155",
        "4165",
        "4600",
        "4610",
        "4630",
        "4640",
        "4650",
        "4700",
        "4710",
        "4720",
        "4730",
        "4760",
        "6850",
    ), (
        "the SIGNED chart's unsigned list holds 4150 Solar, 4155 Fire, 4165 Battery, 4760 "
        "and 6850 Cash over and short, each awaiting the "
        "HUMAN-GUIDE §6 re-sign its review row is still pending — it is a different "
        "question from the cost section's, and conflating them is how a signature gets "
        "assumed"
    )
    assert set(chart.PENDING_FINANCE_RE_SIGN).isdisjoint(set(PROPOSED))
    # `SHARED_CHART` drives the per-tenant seed of the SIGNED ladder and must
    # not have grown either.
    assert {row.code for row in chart.SHARED_CHART}.isdisjoint(set(PROPOSED))


def test_us_led_017_tc5__the_capture_result_and_the_register_carry_the_marker(
    brazos, dana, monkeypatch
):
    """Every surface, not only the picker. A capture against an unsigned account
    comes back saying so, and so does its register row.

    ⚠ **AMENDED 2026-08-18 — 5110 IS SIGNED NOW, so this case lost its real
    subject and is driven from a synthetic one.** It captured against 5110
    Purchased water and asserted the marker; the Product Owner finance re-signed
    all eight cost codes that day (the codes and names, in plain English, no
    dollar figure attached to any of them), so a capture against 5110 must now
    come back CLEAN — which the first half asserts, because a capture flagging a
    ratified account would send a clerk to a finance reviewer for nothing.

    **The second half keeps the marker mechanism alive on a code that is
    unsigned only inside this test.** The rule US-LED-017 TC-5 states is about
    ANY unsigned code, not about the eight that happened to be unsigned in
    August, and a capture path that had quietly stopped carrying the marker
    would now pass in silence. Same move, and the same reason, as
    `test_us_not_005_an_uncatalogued_class_is_refused_with_its_reason`
    (CR-011 item 9).
    """
    from apps.ledger import cost_capture

    def _capture(reference):
        return cost_capture.capture_supplier_invoice(
            dana,
            invoice_date=__import__("datetime").date(2026, 7, 6),
            service="water",
            supplier_name="City of Rosenberg — Bulk Water Supply",
            amount=Decimal("1240.00"),
            currency="USD",
            volume=Decimal("400000"),
            volume_unit="gal",
            reference=reference,
        )

    with tenant_ctx(brazos):
        with_monthly_fiscal_year(dana)

        # ── the LAW as of 2026-08-18: 5110 is signed and nothing flags it ────
        captured = _capture("RS-2607-0141")
        assert cost_capture.UNSIGNED_ACCOUNT_NOTE not in captured["problems"]
        assert captured["gl_account_unsigned"] is False
        assert cost_capture.register()["rows"][0]["gl_account_unsigned"] is False

        # ── the MECHANISM, on a synthetic unsigned code ──────────────────────
        monkeypatch.setattr(chart, "PENDING_FINANCE_RE_SIGN_COST", ("5110",))
        flagged = _capture("RS-2607-0142")
        assert cost_capture.UNSIGNED_ACCOUNT_NOTE in flagged["problems"]
        assert flagged["gl_account_unsigned"] is True

        # The register carries it too — every surface, not only the one that
        # wrote the row.
        listed = cost_capture.register()
        assert all(row["gl_account_unsigned"] is True for row in listed["rows"]), (
            "the register derives the marker per row from the live register of unsigned "
            "codes; a row that lost it would present an unsigned account as signed"
        )


# ═══════════════════════════════════════════════════════════════════════════
# TC-6 — referenced accounts are audit-locked (IS-1)
# ═══════════════════════════════════════════════════════════════════════════
def test_us_led_017_tc6__an_account_a_capture_points_at_cannot_be_deleted(brazos, dana):
    """*"Delete attempted on 5110 after a supplier invoice references it →
    blocked."*

    Enforced by the FK's `PROTECT` rather than by a count somebody has to
    remember to run — IS-1's audit lock in the database. Deactivation (the
    ratified door) still works, which is what makes this a lock and not a
    lockout.
    """
    from datetime import date as _date

    from django.db.models import ProtectedError

    from apps.ledger import cost_capture

    with tenant_ctx(brazos):
        with_monthly_fiscal_year(dana)
        cost_capture.capture_supplier_invoice(
            dana,
            invoice_date=_date(2026, 7, 6),
            service="water",
            supplier_name="City of Rosenberg — Bulk Water Supply",
            amount=Decimal("1240.00"),
            currency="USD",
            volume=Decimal("400000"),
            volume_unit="gal",
            reference="RS-2607-0141",
        )
        account = ledger_models.LedgerAccount.objects.get(tenant=brazos, code="5110")
        with pytest.raises(ProtectedError):
            account.delete()

        # IS-1's ratified door is open: deactivate, never delete.
        account.deleted_at = timezone.now()
        account.save()
        assert ledger_models.LedgerAccount.objects.filter(tenant=brazos, code="5110").exists()


# ═══════════════════════════════════════════════════════════════════════════
# TC-7 — isolation
# ═══════════════════════════════════════════════════════════════════════════
def test_us_led_017_tc7__charts_never_cross_and_codes_repeat_per_tenant(brazos, lonestar, dana):
    """*"Lone Star Ridge chart → its own cost rows only; Brazos Bend's 5110 is
    invisible there and the codes may repeat per tenant."*

    App-layer half. The DATABASE half — RLS FORCE under a non-superuser probe —
    is `test_us_led_018_capture.py`'s isolation case, which carries
    `requires_postgres` rather than a bare skip.
    """
    with tenant_ctx(brazos):
        enable_le11_services(dana)

    brazos_5110 = ledger_models.LedgerAccount.objects.get(tenant=brazos, code="5110")
    lsr_5110 = ledger_models.LedgerAccount.objects.get(tenant=lonestar, code="5110")
    # The same CODE, two different rows — per-tenant UNIQUE, never global.
    assert brazos_5110.pk != lsr_5110.pk

    with tenant_ctx(lonestar):
        offered = {row["account_id"] for row in ledger_selectors.cost_accounts()}
        assert str(brazos_5110.pk) not in offered
        assert str(lsr_5110.pk) in offered
        # Since CR-010 B-9 (2026-08-18) every tenant carries the whole section
        # — Lone Star Ridge's rows are all its OWN, which is what isolation
        # means; the per-service narrowing this line used to assert is reversed.
        codes = {row["code"] for row in ledger_selectors.cost_accounts()}
        assert set(PROPOSED) <= codes


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-LED-017@d744841 (04-docs/05-modules/09-ledger/06-epics/EP-LED-06-cost-of-service-capture.md US-LED-017 §3 TC-1..TC-7 · 04-docs/05-modules/09-ledger/02-business-rules.md BR-LED-037/038 · 04-docs/05-modules/09-ledger/08-worked-examples.md §"PROPOSED chart addendum" · 08-qa/01-e2e/journeys/J25-cost-of-service-month.md step 1)
# generated: 2026-08-15 by the ledger AP-capture lane · AMENDED 2026-08-18 by the CR-008 ledger lane (CR-010 B-9, PO 2026-08-17 "9 - A full ~40 accounts for every tenant, as you said": the per-service narrowing TC-1/TC-2/TC-3/TC-7 pinned is REVERSED — all eight cost rows seed for every tenant; the top-up mint is asserted against a reconstructed narrowing-era tenant; every signature-state assertion is unchanged) · AMENDED 2026-08-18 by the finance re-sign lane (the PO re-signed the eight cost codes and names + 4180 in the working chat session, shown in plain English with NO dollar figure attached to any of them and with B4/B5 ❄️ FROZEN and un-edited; every signature-state assertion in this file is INVERTED with the ruling named, and the two cases whose SUBJECT the ruling removed — TC-5's cross-surface guard and the capture/register marker — are kept alive on a SYNTHETIC unsigned code rather than deleted, because a guard over an empty set passes vacuously. Precedent: CR-011 item 9 on test_us_not_005)
# checklist: A✔ B✔ C✔ D=deferred(no-API-half) E=deferred(no-frontend-half) F✔ G✔ H=deferred(PO 2026-08-09)
# gates: 2026-08-18 re-sign — PROVED RED BEFORE GREEN in a throwaway module run
#         and deleted in the same lane, three cases: (a) TC-5's synthetic
#         selector half pointed at the REAL (now signed) 5110 with the
#         monkeypatch removed → `assert False is True` on `["unsigned"]`;
#         (b) the OLD `_chart_row` derivation evaluated on the RATIFIED 5100 →
#         `old derivation says finance_signed=False for ratified 5100`, which is
#         the defect this lane fixed, on real data; (c) the capture half pointed
#         at the real 5110 → `assert 'gl_account_is_not_finance_signed' in ()`.
#         All three RED, then GREEN with the monkeypatches and the fix in place ·
#         EARLIER: PROVED RED BEFORE GREEN — TC-5 was driven by removing `False` from one
#         SeedAccount row: `AssertionError: assert {'5100',…} == {'5110',…}` with
#         5100 missing from PENDING_FINANCE_RE_SIGN_COST. TC-1's broadband
#         assertion was driven by seeding COST_OF_SERVICE_CHART unconditionally
#         (`assert '5145' not in codes` failed). TC-4 was driven by making the
#         seed overwrite by code (the tenant's rename was lost)
# exceptions: TC-6's SECOND half (*"code/type edit attempted on the same →
#         frozen once referenced"*) is NOT asserted here: the code/type freeze is
#         US-LED-005's own chart-CRUD service, which is not built (the S56 write
#         half is another lane), so there is no write path to refuse through. The
#         DELETE half IS asserted and is enforced by the FK's PROTECT. REPORTED
#         rather than a test that passes because no path exists (hard-won law 1)
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
