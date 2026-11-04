# ── Trace ──────────────────────────────────────────────
# Defect:  DEF-738 — a tax (and, through the same validator, a base charge
#          code) could be restricted only to the PRE-BR-CUS-094 four customer
#          classes, so no tax could reach an Agricultural, Institutional,
#          Municipal or Builder-developer customer. Second site of DEF-684.
# Rules:   BR-CUS-094 (PO 2026-08-24, "Expand the signed list to seven";
#          `government` LEGACY — unselectable on new records, "still a valid
#          FK, still filterable, still priceable") · BR-RAT-108 (a charge code
#          prices one customer class; NULL/[] = every class; an unknown class
#          is REFUSED, never dropped) · BR-RAT-103 (a tax's four statuses and
#          its effective window — READ FIRST and it says nothing about who a
#          tax may be restricted TO) · DEF-273 (the INCLUSION-list direction)
# Golden:  NONE MOVES. This widens the set of class codes a tax may NAME; it
#          changes no rate, no base and no rounding, and every tax that exists
#          today keeps the exact class list it was stored with. GT-1..61
#          unchanged, verified with 10-scripts/03-golden-verify.py.
# Files:   apps/rating/seams.py :: account_type_codes ·
#          apps/rating/services.py :: TAX_CUSTOMER_CLASSES ·
#          07-frontend/src/api/endpoints.ts :: TAX_CUSTOMER_CLASSES
# ───────────────────────────────────────────────────────
"""DEF-738 — rating's copy of the consumer-category vocabulary, DERIVED.

**The defect, in one sentence a person would say:** the platform gives a utility
eight kinds of customer and a tax rule could only be restricted to four of them,
so nobody could write a tax that applies to an Agricultural, Institutional,
Municipal or Builder-developer customer.

**Why it survived two days with a guard pointed straight at it.**
`tests/test_def_273_tax_conditions.py::
test_def273_the_class_vocabulary_mirrors_the_platform_account_types` compares
`rating.TAX_CUSTOMER_CLASSES` against the live `account_types` rows and has been
RED since BR-CUS-094's migration seeded the four new codes on 2026-08-24. Nobody
read it. So this file does not add a second copy of that comparison — it removes
the thing being compared. There is no longer a hand-typed tuple in rating to
drift: the vocabulary is READ from `customers.AccountType`, which is the module
that owns it, through the seam rating already uses for that table.

**THE RED PROOF, verbatim, on the unpatched tree (HEAD 32c708d).** Every case
below was run before the fix. The service-layer case:

    E  core.errors.ValidationError: VAL_UNKNOWN_LOOKUP
    E  field_errors: [{'field': 'applies_to_customer_classes[0]',
    E                  'code': 'VAL_UNKNOWN_LOOKUP',
    E                  'message_key': 'rating.taxes.unknown_customer_class'}]

and the money case, which is the one that matters — a 6.25 % state tax written
for farms, priced on a $100.00 taxable bill:

    HEAD cannot even store it: the tax is refused at creation, so an
    agricultural customer is charged $0.00 by a tax the utility believes it
    configured, and a residential customer is charged $0.00 too. After the fix
    the farm pays $6.25 and the house still pays $0.00.

**WHAT IS *NOT* CHANGED, stated because a money surface deserves it.** Widening
the set of codes a restriction MAY NAME re-points no existing row. Every tax
stored today keeps the class list it was stored with; `[]` still means every
class; an unknown code is still REFUSED rather than dropped (DEF-273's
direction, BR-RAT-108's warning). `government` stays in the vocabulary because
BR-CUS-094 keeps a legacy code *"still a valid FK, still filterable, still
priceable"* — dropping it would invalidate live restrictions and is the one
substitution the ruling forbids.
"""

from __future__ import annotations

import re
from decimal import Decimal
from pathlib import Path

import pytest

from apps.billing import rating_seam
from apps.customers import models as customer_models
from apps.rating import models as rating_models
from apps.rating import seams, selectors, services
from core import errors

from tests.test_us_rat_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_rat_helpers import tenant_ctx

pytestmark = pytest.mark.django_db

REPO_ROOT = Path(__file__).resolve().parents[2]
ENDPOINTS_TS = REPO_ROOT / "07-frontend" / "src" / "api" / "endpoints.ts"

#: BR-CUS-094's eight, read from the model that owns them. Re-typing them here
#: would be the defect wearing a lab coat.
EXPECTED = tuple(code for code, _name in customer_models.AccountType.SEVEN_CATEGORIES) + tuple(
    customer_models.AccountType.LEGACY_CODES
)
#: The four BR-CUS-094 added — the ones no tax could name.
THE_FOUR_THAT_COULD_NOT_BE_NAMED = (
    "agricultural",
    "institutional",
    "municipal",
    "builder_developer",
)

USD = "USD"
TAXED = rating_seam.AccountContext(currency=USD, tax_exempt=False)
FULL_MONTH = rating_seam.BillingPeriod(cycle_days=30, service_days=30)
#: A bill whose taxable base is EXACTLY $100.00, so every figure below reads as
#: its own percentage without arithmetic in the reader's head — the same shape
#: `test_def_273_tax_conditions.py` prices its five ruled Texas rows on.
HUNDRED = rating_seam.TariffConfig(
    service="electric",
    model="flat",
    billed_unit="kWh",
    base_charge=Decimal("100.00"),
    unit_price=Decimal("0"),
)
NO_USAGE = rating_seam.Quantity(amount=Decimal("0"), unit="kWh")


def _bill(rules):
    """Price a $100.00 taxable bill under exactly these resolved rules, through
    the SAME adaptation `apps/billing/gather.py` performs — the real engine, not
    a hand-built spec that could agree with the code and be wrong."""
    return rating_seam.price_period(
        tariff=HUNDRED,
        consumption=NO_USAGE,
        period=FULL_MONTH,
        account=TAXED,
        taxes=tuple(
            rating_seam.TaxRule(
                code=rule["code"],
                rate=None if rule.get("rate") is None else Decimal(str(rule["rate"])),
                tax_id=rule.get("tax_id"),
                flat_amount=(
                    None if rule.get("flat_amount") is None else Decimal(str(rule["flat_amount"]))
                ),
            )
            for rule in rules
        ),
    )


def _tax_amounts(priced):
    return {line.description: line.amount for line in priced.lines_of("tax")}


# ══════════════════════════════════════════════════════════════════════════
# 1 · THE VOCABULARY IS READ, NOT RE-TYPED — the durable half
# ══════════════════════════════════════════════════════════════════════════
def test_def738_the_class_vocabulary_is_derived_from_the_platform_model():
    """`rating.TAX_CUSTOMER_CLASSES` IS `customers.AccountType`'s vocabulary.

    Not *equal to* it by inspection — DERIVED from it, so the two cannot part.
    The order is BR-CUS-094's own ruling order and never alphabetical: the
    screen renders in this order, and sorting would put Agricultural first in a
    list the PO drew.
    """
    assert tuple(services.TAX_CUSTOMER_CLASSES) == EXPECTED
    assert tuple(seams.account_type_codes()) == EXPECTED
    # The four the defect was about are IN it, named so a reader of the failure
    # does not have to diff two sorted lists to see what is missing.
    for code in THE_FOUR_THAT_COULD_NOT_BE_NAMED:
        assert code in services.TAX_CUSTOMER_CLASSES
    # And the legacy code stays: BR-CUS-094 keeps it "still a valid FK, still
    # filterable, still priceable", so a tax already restricted to it still is.
    assert "government" in services.TAX_CUSTOMER_CLASSES


def test_def738_rating_holds_no_hand_typed_copy_of_the_vocabulary():
    """⚠ **THE CHECK THAT MAKES THIS FIX DURABLE RATHER THAN CURRENT.**

    A widened literal is still a literal, and BR-CUS-094 will not be the last
    ruling to move this list. So the assertion is not *"the tuple has eight
    entries"* — it is *"rating writes none of them down"*. Scanned by CONTENT
    over rating's production modules, so renaming the constant does not evade
    it, exactly as `test_def_684_category_vocabulary.py` scans the frontend.

    A single code in prose is fine and deliberate — DEF-738's own comments quote
    `government` and `agricultural` by name. THREE distinct codes inside one
    string literal or one adjacent pair of lines is an enumeration.
    """
    rating_src = REPO_ROOT / "06-backend" / "apps" / "rating"
    vocabulary = set(EXPECTED)
    offenders: dict[str, list[tuple[int, list[str]]]] = {}
    for path in sorted(rating_src.rglob("*.py")):
        if "/migrations/" in path.as_posix():
            continue  # a migration is a historical record, never a live list
        lines = path.read_text(encoding="utf-8").splitlines()
        hits = []
        for number, line in enumerate(lines, start=1):
            # Quoted codes only. A bare word in a sentence is prose.
            found = {m for m in re.findall(r'["\']([a-z_]+)["\']', line) if m in vocabulary}
            if found:
                hits.append((number, found))
        for index, (start, _codes) in enumerate(hits):
            window: set[str] = set()
            for number, codes in hits[index:]:
                if number - start > 2:
                    break
                window |= codes
            if len(window) >= 3:
                offenders.setdefault(path.relative_to(rating_src).as_posix(), []).append(
                    (start, sorted(window))
                )
                break
    assert offenders == {}, (
        "a rating module writes the platform consumer-category vocabulary down. "
        "It is owned by `customers.AccountType` and read through "
        "`seams.account_type_codes()` — a typed copy cannot notice a ruling, "
        f"which is DEF-738 exactly. Found: {offenders}"
    )


def test_def738_the_frontend_mirror_is_the_same_list_in_the_same_order():
    """⚠ **THE HALF NOTHING HAD.** `endpoints.ts` cannot import Python, so its
    `TAX_CUSTOMER_CLASSES` is a MIRROR and stays one — deliberately, and the
    reason is a money one. `[]` means *every class*, so a wizard that fetched
    this catalogue and failed to would offer nothing, and a clerk editing a
    restricted tax would save it applying to EVERYBODY. A static list cannot do
    that. What it CAN do is drift, and this is the check that drift goes red:
    the same codes, in the same order, both directions.
    """
    source = ENDPOINTS_TS.read_text(encoding="utf-8")
    start = source.index("export const TAX_CUSTOMER_CLASSES")
    end = source.index("]", start)
    offered = tuple(re.findall(r'"([a-z_]+)"', source[start:end]))
    assert offered == tuple(services.TAX_CUSTOMER_CLASSES), (
        "the tax wizard's restrict-to control offers "
        f"{list(offered)} and rating accepts {list(services.TAX_CUSTOMER_CLASSES)}"
    )


# ══════════════════════════════════════════════════════════════════════════
# 2 · THE REAL SERVICE ACCEPTS THEM — the RED case
# ══════════════════════════════════════════════════════════════════════════
def test_def738_a_tax_can_be_restricted_to_each_of_the_four_new_classes(env):
    """RED ON HEAD, through the real write path, once per code:

        core.errors.ValidationError: VAL_UNKNOWN_LOOKUP on
        applies_to_customer_classes[0] / rating.taxes.unknown_customer_class

    BR-CUS-094 makes these *"REAL categories a plan can be priced for"*. A
    category that can be priced and cannot be taxed is half a vocabulary.
    """
    for index, code in enumerate(THE_FOUR_THAT_COULD_NOT_BE_NAMED):
        stored = env.tax(
            f"Levy for {code}",
            jurisdiction={"name": f"Authority {index}", "level": "state"},
            applies_to_customer_classes=[code],
        )
        assert stored["applies_to_customer_classes"] == [code], code


def test_def738_a_base_charge_code_can_be_priced_for_the_four_too(env):
    """BR-RAT-108 gave `charges` the SAME dimension through the SAME validator
    (`_customer_class_list`, extracted 2026-08-21 precisely so the two objects
    could not answer one question two ways). Widening the vocabulary therefore
    widens both, and that is the rule's own intent: the base is narrowed by
    service → ACCOUNT TYPE → meter size, and an account type nobody may name is
    a dimension with a hole in it.
    """
    code = env.charge(
        "BASE-AG",
        "Agricultural water base",
        charge_type="recurring",
        amount="12.00",
        is_base=True,
        applies_to_customer_classes=["agricultural", "municipal"],
    )
    assert code["applies_to_customer_classes"] == ["agricultural", "municipal"]


def test_def738_a_typo_is_still_refused_and_never_dropped(env):
    """Widening the set does not soften the refusal, and that is DEF-273's and
    BR-RAT-108's shared reason: a silently-vanished `"agricultral"` leaves a tax
    the utility believes is restricted applying to EVERYBODY, on every bill.
    """
    with pytest.raises(errors.ValidationError) as excinfo:
        env.tax(
            "Typo levy",
            jurisdiction={"name": "Typo authority", "level": "state"},
            applies_to_customer_classes=["agricultral"],
        )
    assert excinfo.value.field_errors[0]["field"] == "applies_to_customer_classes[0]"
    assert excinfo.value.field_errors[0]["message_key"] == "rating.taxes.unknown_customer_class"


# ══════════════════════════════════════════════════════════════════════════
# 3 · AND IT REACHES THE FARM AND NOBODY ELSE — the money case
# ══════════════════════════════════════════════════════════════════════════
def test_def738_an_agricultural_only_tax_charges_the_farm_625_and_the_house_nothing(env):
    """THE $6.25 CASE, one class over from DEF-273's.

    RED ON HEAD: the tax could not be STORED at all, so the farm the utility
    wrote it for was charged **$0.00** by a rate it believed was live — the
    defect register's own words, *"a tax simply never applies, which looks like
    a tax that was not configured"*. After the fix the farm pays **$6.25** on a
    $100.00 taxable bill and the house still pays **$0.00**, which is the whole
    point of a restriction.

    Priced through `selectors.plan_tax_rules` and the real engine, never a stub.
    """
    tax = env.tax(
        "Agricultural Water Levy",
        jurisdiction={"name": "State Water Board", "authority": "State Water Board", "level": "state"},
        kind="percent",
        rate="0.0625",
        applies_to_customer_classes=["agricultural"],
    )
    plan = env.plan(
        "Farm Standard",
        "FARM-STD",
        [{"service": "electric", "base_charge": "100.00"}],
        tax_rules=[{"jurisdiction": tax["jurisdiction"]["id"]}],
    )

    with tenant_ctx(env.tenant):
        farm = selectors.plan_tax_rules(
            plan["id"], customer_class="agricultural", premises={}, services=("electric",)
        )
        house = selectors.plan_tax_rules(
            plan["id"], customer_class="residential", premises={}, services=("electric",)
        )
        unresolved = selectors.plan_tax_rules(
            plan["id"], customer_class=None, premises={}, services=("electric",)
        )

    assert _tax_amounts(_bill(farm)) == {"Tax State Water Board": Decimal("6.25")}
    assert _bill(farm).tax_total == Decimal("6.25")
    # NO LINE AT ALL, not a zero one — DEF-273's ruled direction, unchanged.
    assert house == [] and _bill(house).tax_total == Decimal("0.00")
    # An account whose class could not be resolved gets no restricted tax:
    # under-charging is recoverable, over-charging an exempt customer is a refund.
    assert unresolved == [] and _bill(unresolved).tax_total == Decimal("0.00")


def test_def738_no_stored_tax_is_re_pointed_by_the_widening(env):
    """⚠ **THE STATEMENT A MONEY SURFACE OWES ITS NEXT READER.**

    BR-CUS-094 says of the CATEGORY on a record that *"every existing record
    keeps its code"* and that re-pointing is a human act per record. Widening a
    list of ALLOWED values re-points nothing at all, and this is that sentence
    as an assertion: a tax stored restricted to commercial+industrial before the
    change is restricted to commercial+industrial after it, and one restricted
    to the legacy code still is.
    """
    restricted = env.tax(
        "TX State Utility Tax",
        jurisdiction={"name": "Texas Comptroller", "level": "state"},
        rate="0.0625",
        applies_to_customer_classes=["commercial", "industrial"],
    )
    legacy = env.tax(
        "Municipal Utility Levy",
        jurisdiction={"name": "City Hall", "level": "city"},
        rate="0.0200",
        applies_to_customer_classes=["government"],
    )
    with tenant_ctx(env.tenant):
        rows = {
            row.name: row.applies_to_customer_classes
            for row in rating_models.Tax.objects.filter(tenant=env.tenant)
        }
    assert rows[restricted["name"]] == ["commercial", "industrial"]
    assert rows[legacy["name"]] == ["government"]


# ── Trace footer ───────────────────────────────────────
# packet: DEF-738 (12-governance/10-defect-log.csv) · DEF-684 (the first site) ·
#         DEF-748 (the inventory count, the same drift from the other side) ·
#         BR-CUS-094 (04-docs/05-modules/03-customers/02-business-rules.md) ·
#         BR-RAT-103 + BR-RAT-108 (04-docs/05-modules/06-rating/02-business-rules.md)
# generated: 2026-08-30, DEF-738 lane
# gates: proved RED first (hard-won law 7) against the unpatched tree — the
#        service cases fail with VAL_UNKNOWN_LOOKUP on
#        `applies_to_customer_classes[0]`, the derivation case fails with
#        `AttributeError: module 'apps.rating.seams' has no attribute
#        'account_type_codes'`, and the frontend-mirror case fails on
#        `['residential','commercial','industrial','government']`.
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
