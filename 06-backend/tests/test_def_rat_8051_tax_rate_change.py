# ── Trace ──────────────────────────────────────────────
# Defect:  DEF-RAT-8051 (2026-09-29) — a tax rate change, filed exactly the way
#          the model's own comment instructs ("r6.5; new row per change"),
#          caused NO TAX LINE AT ALL to be written. Not the old rate and not
#          the new one. `selectors._authority_tax` took no date: it picked the
#          OLDEST non-superseded row by `created_at` and only afterwards did
#          the caller ask `tax_in_force(tax, service_date)`, which the old row
#          then failed.
# Rules:   BR-BIL-069 (the identity and the rate must name the same row) ·
#          DEF-483 (the effective window is a GATE, not a queryset filter) ·
#          DEF-384 (superseded rows are preferred against, not excluded) ·
#          B14 rule 31 (no database id on screen) · B14 rule 33 (six words) ·
#          CLAUDE.md hard rule 2 (money 4dp stored, 2dp displayed) · hard
#          rule 4 (an issued bill's price never moves)
# Golden:  ❄️ B4/B5 UNMOVED. Every frozen figure is priced from UNDATED tax
#          rows, and an undated row is in force on every date, so the pick this
#          file changes returns the same row for all of them — asserted below
#          in `test_tc4`, not assumed.
# ───────────────────────────────────────────────────────
"""A filed rate change must charge the NEW rate, and two live rates must refuse.

WHY NO EXISTING TEST CAUGHT THIS, AND WHAT IT MEANS FOR THE ONES BELOW
----------------------------------------------------------------------
**Every tax row in this product is UNDATED.** Measured on the branch the fix
landed on: the `taxes` table holds 2 rows and BOTH carry `effective_from` NULL
and `effective_to` NULL, and the provisioning seed writes no dated row either.
A NULL bound is *no bound stated* (`tax_in_force`'s own words), so every
existing row is in force on every date, the window gate never bites, and **the
old query and the fixed one return the same row on all existing data.**

That is what made the defect safe to fix and it is also what makes a test
worthless unless it **creates dated rows itself**. A fixture that reuses the
seeded taxes exercises the identity case and reports green over the whole bug.
Every case here writes its own `effective_from` / `effective_to`.

THE RED, QUOTED VERBATIM
------------------------
`test_tc1` below was run with the PRE-FIX `_authority_tax` — the two-line
query, no date — monkeypatched over the live one, through this same pytest
harness. It fails like this, and **the shape of the failure is the defect**:
not a wrong number, but no tax rule produced at all.

    >           assert len(rules) == 1, "January 2027 must be taxed at 7.00%"
    E           AssertionError: January 2027 must be taxed at 7.00%
    E           assert 0 == 1
    E            +  where 0 = len([])

    1 failed, 12 warnings in 314.13s

With the fix in place the same file is **13 passed**.

`test_tc0_the_old_pick_is_reproduced_here` keeps that failure permanently
available: it runs the pre-fix query beside the fixed one on the same two rows
and asserts they disagree, so a lane that "simplifies" the date back out of the
choice sees the old behaviour named rather than a green suite.
"""

from datetime import date
from decimal import Decimal

import pytest
from django.db import transaction

from apps.billing import rating_seam
from apps.rating import models as rating_models
from apps.rating import resolution, selectors, services

from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import make_plan, tenant_ctx

pytestmark = pytest.mark.django_db

USD = "USD"
TAXED = rating_seam.AccountContext(currency=USD, tax_exempt=False)
FULL_MONTH = rating_seam.BillingPeriod(cycle_days=30, service_days=30)

#: The PO's worked example is a **$196.00** taxable bill, so 7.00% reads
#: $13.72 and 6.25% reads $12.25 without a reader having to do the arithmetic.
BILL = rating_seam.TariffConfig(
    service="electric",
    model="flat",
    billed_unit="kWh",
    base_charge=Decimal("196.00"),
    unit_price=Decimal("0"),
)
NO_USAGE = rating_seam.Quantity(amount=Decimal("0"), unit="kWh")

#: The two dates either side of the statutory change.
DECEMBER = date(2026, 12, 15)
JANUARY = date(2027, 1, 15)


# ── plumbing (the shape test_br_rat_113_attach_taxes.py uses) ───────────────
def an_authority(tenant, name="Testland State DEF-RAT-8051"):
    jurisdiction, _ = rating_models.TaxJurisdiction.objects.get_or_create(
        tenant=tenant, name=name
    )
    return jurisdiction


def a_tax(tenant, jurisdiction, **fields):
    fields.setdefault("kind", "percent")
    fields.setdefault("name", "State Utility Tax")
    return rating_models.Tax.objects.create(
        tenant=tenant, jurisdiction=jurisdiction, **fields
    )


def bind(tenant, plan, jurisdiction):
    rating_models.PlanTaxRule.objects.get_or_create(
        tenant=tenant, rate_plan=plan, jurisdiction=jurisdiction
    )


def percent_rules(plan, on):
    """`plan_tax_rules` narrowed to the percent rows, which is what this is about."""
    return [
        row
        for row in selectors.plan_tax_rules(str(plan.id), on, services=("electric",))
        if row.get("rate") is not None
    ]


def tax_charged(rules):
    """What a $196.00 bill actually carries under these resolved rules."""
    bill = rating_seam.price_period(
        tariff=BILL,
        consumption=NO_USAGE,
        period=FULL_MONTH,
        account=TAXED,
        taxes=tuple(
            rating_seam.TaxRule(
                code=rule["code"],
                rate=Decimal(str(rule["rate"])),
                tax_id=rule.get("tax_id"),
            )
            for rule in rules
        ),
    )
    return sum(
        (line.amount for line in bill.lines if line.kind == "tax"), Decimal("0.00")
    )


def the_old_pick(jurisdiction_id, kind="percent"):
    """`_authority_tax` EXACTLY as it stood before this defect was fixed.

    Copied rather than imported on purpose: this is the behaviour under test,
    and a copy is the only way to keep the comparison after the original is
    gone. Two lines, and they are the whole bug.
    """
    rows = rating_models.Tax.objects.filter(
        tenant_id=selectors._tenant_id(), jurisdiction_id=jurisdiction_id, kind=kind
    )
    return (
        rows.filter(superseded_by__isnull=True).order_by("created_at").first()
        or rows.order_by("created_at").first()
    )


def a_changed_rate(tenant, plan):
    """The PO's worked example, filed the way the model's comment instructs.

    Row A: written Jan 2024 at 6.25%, window ends 2026-12-31.
    Row B: written Dec 2026 at 7.00%, window opens 2027-01-01.

    B is created SECOND so its `created_at` is strictly later, which is what
    made A win the old pick.
    """
    authority = an_authority(tenant)
    old = a_tax(
        tenant,
        authority,
        name="State Utility Tax (to 2026)",
        rate=Decimal("0.062500"),
        effective_to=date(2026, 12, 31),
    )
    new = a_tax(
        tenant,
        authority,
        name="State Utility Tax (from 2027)",
        rate=Decimal("0.070000"),
        effective_from=date(2027, 1, 1),
    )
    bind(tenant, plan, authority)
    return authority, old, new


# ── TC-0 · THE RED, KEPT ────────────────────────────────────────────────────
def test_tc0_the_old_pick_is_reproduced_here(brazos):
    """The pre-fix query, run on the two dated rows, still answers ROW A — and
    row A is not in force in January 2027. That pair of facts IS the defect:
    the pick and the gate disagreed, and nothing reconciled them."""
    with tenant_ctx(brazos):
        plan = make_plan(brazos, name="DEF-RAT-8051 TC0")
        authority, old, new = a_changed_rate(brazos, plan)

        assert the_old_pick(authority.id).id == old.id
        assert selectors.tax_in_force(old, JANUARY) is False
        # …so the old code resolved a row it then refused, and wrote no line.

        assert selectors._authority_tax(authority.id, "percent", JANUARY).id == new.id


# ── TC-1 · THE WORKED EXAMPLE ───────────────────────────────────────────────
def test_tc1_january_2027_is_taxed_at_the_new_rate(brazos):
    """$196.00 taxed at 7.00% is **$13.72**. Before the fix it was $0.00."""
    with tenant_ctx(brazos):
        plan = make_plan(brazos, name="DEF-RAT-8051 TC1")
        _authority, _old, new = a_changed_rate(brazos, plan)

        rules = percent_rules(plan, JANUARY)
        assert len(rules) == 1, "January 2027 must be taxed at 7.00%"
        assert Decimal(str(rules[0]["rate"])) == Decimal("0.070000")
        # BR-BIL-069 — the rate and the identity name the SAME row.
        assert rules[0]["tax_id"] == str(new.id)
        assert tax_charged(rules) == Decimal("13.72")


def test_tc1b_december_2026_is_still_taxed_at_the_old_rate(brazos):
    """The same two rows, one month earlier: **$12.25**. A fix that resolved
    the newest row rather than the one whose WINDOW CONTAINS THE DATE would
    charge next year's rate on this year's bill and pass TC-1."""
    with tenant_ctx(brazos):
        plan = make_plan(brazos, name="DEF-RAT-8051 TC1b")
        _authority, old, _new = a_changed_rate(brazos, plan)

        rules = percent_rules(plan, DECEMBER)
        assert len(rules) == 1
        assert rules[0]["tax_id"] == str(old.id)
        assert tax_charged(rules) == Decimal("12.25")


# ── TC-2 · TWO IN FORCE ON ONE DATE REFUSE ──────────────────────────────────
def test_tc2_two_rows_in_force_refuse_and_name_both(brazos):
    """Not a tie-break — a coin toss on a money path. The refusal names both
    rows to an ENGINEER and neither of them to a clerk."""
    with tenant_ctx(brazos):
        plan = make_plan(brazos, name="DEF-RAT-8051 TC2")
        authority = an_authority(brazos)
        first = a_tax(
            brazos,
            authority,
            name="State Utility Tax",
            rate=Decimal("0.062500"),
            effective_from=date(2026, 1, 1),
        )
        # ⚠ CR-165-BRC10 round 2 (`DEF-RAT-9280`): the refusal now holds for
        # two VERSIONS of ONE tax — the same `chain_id` — and no longer for two
        # different taxes of one authority, which both price. This row is
        # therefore stated as a second version of the first (a broken chain
        # PostgreSQL refuses to store, `ex_taxes_chain_no_overlap`).
        mark = transaction.savepoint()  # PostgreSQL refuses this chain at commit
        second = a_tax(
            brazos,
            authority,
            name="State Utility Tax (restated)",
            rate=Decimal("0.070000"),
            effective_from=date(2026, 6, 1),
            chain_id=first.chain_id,
            version_no=2,
        )
        bind(brazos, plan, authority)

        with pytest.raises(selectors.AmbiguousAuthorityTax) as raised:
            selectors._authority_tax(authority.id, "percent", JANUARY)

        engineer = str(raised.value)
        assert str(first.id) in engineer and str(second.id) in engineer

        # B14 rule 31 — what a clerk may be shown carries no database id.
        clerk = resolution.clerk_refusal(raised.value)
        assert clerk is not None
        assert clerk["message_key"] == "rating.refusal.taxesAmbiguous"
        assert clerk["detail"] == "2 Testland State DEF-RAT-8051 taxes apply on 15 Jan 2027. " \
            "Ask an administrator to retire one."
        for field in [clerk["detail"], clerk["message_key"], *map(str, clerk["message_params"].values())]:
            assert str(first.id) not in field and str(second.id) not in field

        # …and the whole read refuses rather than pricing one of them.
        with pytest.raises(selectors.AmbiguousAuthorityTax):
            percent_rules(plan, JANUARY)
        transaction.savepoint_rollback(mark)


def test_tc2b_the_clerk_sentence_is_the_catalogue_sentence(brazos):
    """`CLERK_REFUSALS` is a MIRROR of `en.json`, never a second source.

    ⚠ **`G139` DOES NOT COVER THIS KEY AND THAT IS STATED RATHER THAN LEFT TO
    BE FOUND.** That gate re-raises the nine refusals of `resolution.py` and
    ties each to the catalogue; this refusal is raised from `selectors.py`, so
    the gate's count does not move and its tie never reaches this key. This
    test is the tie for it — one key, held in one place."""
    import json
    import pathlib

    catalogue = json.loads(
        (
            pathlib.Path(__file__).resolve().parents[2]
            / "07-frontend/src/i18n/locales/en.json"
        ).read_text(encoding="utf-8")
    )
    key = "rating.refusal.taxesAmbiguous"
    assert key in catalogue
    assert catalogue[key].replace("{{", "{").replace("}}", "}") == resolution.CLERK_REFUSALS[key]


# ── TC-3 · THE THREE DELIBERATE BEHAVIOURS, UNMOVED ─────────────────────────
def test_tc3a_no_row_in_force_still_names_the_authority_and_writes_no_line(brazos):
    """BR-BIL-069's promise. The authority is still resolved — so a bill can
    name whose money it is — and the row then fails `tax_in_force`, so no line
    is produced. Neither half changed."""
    with tenant_ctx(brazos):
        plan = make_plan(brazos, name="DEF-RAT-8051 TC3a")
        authority = an_authority(brazos)
        expired = a_tax(
            brazos,
            authority,
            rate=Decimal("0.062500"),
            effective_to=date(2026, 12, 31),
        )
        bind(brazos, plan, authority)

        assert selectors._authority_tax(authority.id, "percent", JANUARY).id == expired.id
        assert percent_rules(plan, JANUARY) == []


def test_tc3b_every_row_superseded_still_resolves(brazos):
    """DEF-384's pathological case. Superseded rows are PREFERRED AGAINST, not
    excluded, and the final fallback catches an authority all of whose rows are
    superseded — otherwise the bill could not name the authority at all."""
    with tenant_ctx(brazos):
        plan = make_plan(brazos, name="DEF-RAT-8051 TC3b")
        authority = an_authority(brazos)
        head = a_tax(brazos, authority, rate=Decimal("0.070000"))
        tail = a_tax(brazos, authority, rate=Decimal("0.062500"))
        head.superseded_by = tail
        head.save(update_fields=["superseded_by"])
        tail.superseded_by = head
        tail.save(update_fields=["superseded_by"])
        bind(brazos, plan, authority)

        # Nothing is in force (every row is superseded), so the new branch
        # abstains and the old chain answers — the OLDEST row, as it always did.
        resolved = selectors._authority_tax(authority.id, "percent", JANUARY)
        assert resolved is not None and resolved.id == head.id
        assert percent_rules(plan, JANUARY) == []


def test_tc3c_a_deactivated_row_names_the_authority_and_prices_nothing(brazos):
    """⚠ ANSWERED 2026-10-03 (`DEF-RAT-9279`, CR-165-BRC10 round 2). This case
    asserted the DECLINING of *"should a DEACTIVATED tax price a bill"* — a
    deleted row still priced $12.25. The decline was never a register row, and
    the redesign's Retire would have inherited it, so it was filed and fixed:
    the row still RESOLVES (BR-BIL-069 — the identity is unchanged) and now
    fails `tax_in_force`, so it produces no line."""
    with tenant_ctx(brazos):
        from django.utils import timezone

        plan = make_plan(brazos, name="DEF-RAT-8051 TC3c")
        authority = an_authority(brazos)
        gone = a_tax(
            brazos,
            authority,
            rate=Decimal("0.062500"),
            deleted_at=timezone.now(),
        )
        bind(brazos, plan, authority)

        assert selectors._authority_tax(authority.id, "percent", JANUARY).id == gone.id
        assert the_old_pick(authority.id).id == gone.id  # …the same row as before
        assert selectors.tax_in_force(gone, JANUARY) is False
        assert percent_rules(plan, JANUARY) == []


# ── TC-4 · HARD RULE 4 — NO ISSUED BILL RE-PRICES ───────────────────────────
def test_tc4_an_undated_row_resolves_to_the_same_row_as_before(brazos):
    """The identity case, which is ALL EXISTING DATA. Every tax row in this
    product carries NULL bounds, so the fixed pick and the old one must answer
    the same row — otherwise a bill already issued would re-resolve onto a
    different authority row, which hard rule 4 forbids."""
    with tenant_ctx(brazos):
        plan = make_plan(brazos, name="DEF-RAT-8051 TC4")
        authority = an_authority(brazos)
        only = a_tax(brazos, authority, rate=Decimal("0.062500"))
        bind(brazos, plan, authority)

        assert the_old_pick(authority.id).id == only.id
        assert selectors._authority_tax(authority.id, "percent", JANUARY).id == only.id
        assert selectors._authority_tax(authority.id, "percent").id == only.id
        assert tax_charged(percent_rules(plan, JANUARY)) == Decimal("12.25")


def test_tc4b_a_dateless_call_is_the_old_function_byte_for_byte(brazos):
    """`services._detach_tax` asks *which taxes does this authority bring at
    all* — a question with no date in it — and must not start refusing. Two
    rows that WOULD be ambiguous on a date resolve, dateless, to the oldest."""
    with tenant_ctx(brazos):
        authority = an_authority(brazos)
        first = a_tax(brazos, authority, rate=Decimal("0.062500"))
        # CR-165-BRC10 round 2 (`DEF-RAT-9280`): only two VERSIONS of one tax
        # refuse on a date — two separate taxes both price — so the second row
        # is stated as a version of the first. Inside a SAVEPOINT, because
        # PostgreSQL refuses the broken chain at commit and Django checks
        # deferred constraints when a test ends.
        mark = transaction.savepoint()
        try:
            a_tax(
                brazos, authority, rate=Decimal("0.070000"),
                chain_id=first.chain_id, version_no=2,
            )
            assert selectors._authority_tax(authority.id, "percent").id == first.id
            with pytest.raises(selectors.AmbiguousAuthorityTax):
                selectors._authority_tax(authority.id, "percent", JANUARY)
        finally:
            transaction.savepoint_rollback(mark)


# ── TC-5 · THE OTHER TWO FORMS ──────────────────────────────────────────────
def test_tc5_the_flat_and_per_unit_forms_take_the_date_too(brazos):
    """Three call sites, not one. A $0.85 PUC fee re-filed at $0.95 and a
    $0.25/kgal surcharge re-filed at $0.30 lose their line exactly the way the
    percent form did — `DEF-483` made the same argument about its own gate."""
    with tenant_ctx(brazos):
        authority = an_authority(brazos, name="Testland PUC DEF-RAT-8051")
        old_flat = a_tax(
            brazos,
            authority,
            kind="flat_per_bill",
            name="PUC fee (to 2026)",
            flat_amount=Decimal("0.850000"),
            effective_to=date(2026, 12, 31),
        )
        new_flat = a_tax(
            brazos,
            authority,
            kind="flat_per_bill",
            name="PUC fee (from 2027)",
            flat_amount=Decimal("0.950000"),
            effective_from=date(2027, 1, 1),
        )
        assert selectors._authority_tax(authority.id, "flat_per_bill", JANUARY).id == new_flat.id
        assert selectors._authority_tax(authority.id, "flat_per_bill", DECEMBER).id == old_flat.id

        old_unit = a_tax(
            brazos,
            authority,
            kind="per_unit",
            name="Conservation surcharge (to 2026)",
            per_unit_amount=Decimal("0.250000"),
            per_unit_uom="kgal",
            effective_to=date(2026, 12, 31),
        )
        new_unit = a_tax(
            brazos,
            authority,
            kind="per_unit",
            name="Conservation surcharge (from 2027)",
            per_unit_amount=Decimal("0.300000"),
            per_unit_uom="kgal",
            effective_from=date(2027, 1, 1),
        )
        assert selectors._authority_tax(authority.id, "per_unit", JANUARY).id == new_unit.id
        assert selectors._authority_tax(authority.id, "per_unit", DECEMBER).id == old_unit.id


# ── TC-6 · THE MEASUREMENT THIS FIX RESTS ON ────────────────────────────────
def test_tc6_the_seeded_taxes_are_undated(brazos):
    """The reason the fix is a no-op on existing data, asserted rather than
    quoted. If a seed ever starts writing a dated row, this goes red and the
    next lane knows the identity argument above no longer holds for free."""
    with tenant_ctx(brazos):
        seeded = rating_models.Tax.objects.filter(tenant=brazos)
        dated = [
            row
            for row in seeded
            if row.effective_from is not None or row.effective_to is not None
        ]
        assert dated == [], f"{len(dated)} seeded tax row(s) now carry a window"


def test_tc7_services_identity_lookups_still_pass_no_date(brazos):
    """`services._detach_tax` must keep calling this dateless — a refusal there
    would block a plan edit over a configuration problem on a DIFFERENT date.
    Asserted on the source, because the call is two branches deep."""
    import inspect

    source = inspect.getsource(services)
    assert source.count("_authority_tax(rule.jurisdiction_id, kind)") == 1
    assert source.count('_authority_tax(row["jurisdiction"], kind)') == 1
