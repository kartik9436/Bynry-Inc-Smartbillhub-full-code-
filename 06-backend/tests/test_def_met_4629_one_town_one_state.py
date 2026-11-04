# ── Trace ──────────────────────────────────────────────
# Defect:  DEF-MET-4629 — one seeded estate answered the same address question
#          three ways: the premises panel said `Silver Creek, Texas 68901`, the
#          mailing box on the same screen said `Silver Creek, NE, 68901`, and
#          `select distinct state from premises` returned BOTH `Texas` and `TX`.
#          `68901` is a Nebraska postcode.
# Ruling:  PO 2026-09-08, verbatim: *"(a) Texas, fix the postcode"* — decision
#          log of that date, answer (8).
# Rules:   CLAUDE.md hard rule 8 (an address is stored on `premises` and every
#          other entity derives it by walking there; `customers.addresses`
#          `kind='mailing'` is one of the three named exceptions, because it is
#          where the BILL goes and for a landlord that is another building) ·
#          BR-NOT-029 clause (b) (a bill with no state is held out of the print
#          set — DEF-2848, which is why the state exists at all) ·
#          BR-MET-139 (the premises importer offers `state`) ·
#          hard-won law 7 (what would make this check PASS WRONGLY)
# Tests:   this file
# ───────────────────────────────────────────────────────
"""The seeded estate names ONE town, ONE state and ONE postcode.

WHY THIS FILE EXISTS, AND IT IS THE DEFECT'S OWN ESCAPE REASON
---------------------------------------------------------------
`DEF-MET-4629`'s `escape_reason` column says it in one line: **nothing compares
the two address sources against each other.** `DEF-2848` correctly gave the
MAILING address a state, chose `NE` so that town, state and postcode named one
real place, and never looked at `premises` — which nothing was refusing over.
The estate then answered the same question two ways, and the only way to see it
was to read two panels of one screen side by side, which no test does.

So these cases do exactly that comparison, on rows the product's own seeders
wrote.

╔══════════════════════════════════════════════════════════════════════════╗
║  WHAT WOULD MAKE THESE CHECKS PASS WRONGLY — asked before trusting them   ║
╚══════════════════════════════════════════════════════════════════════════╝
  1. **A tenant that declares nothing.** `tenants.state` is not required at
     sign-up (`DEF-444`), and a tenant with no state seeds premises with no
     state — on which "one spelling" is trivially true of the empty set. So
     `test_the_estate_states_one_state` asserts the set is `{fixture.STATE}`
     rather than `len(...) == 1`, and a second case asserts the fold itself on
     both spellings without touching the database.
  2. **An estate with no mailing addresses.** The agreement case would pass
     over zero rows. It asserts a non-zero count first, and names it.
  3. **Reading both facts from the same constant — and this one was not
     hypothetical.** The agreement case was written as *"every mailing row is
     `(fixture.CITY, fixture.STATE, fixture.POSTAL)`"* and it came back GREEN
     against the code that produced the defect: both `customers.sample_data`
     rows read that constant, so the assertion compared the constant with
     itself while `premises` sat one table away still saying `Texas`. It
     compares the two ROW SETS now, and asserts the constant separately.

WHERE `78611` CAME FROM, BECAUSE IT IS A LOOKED-UP FACT AND NOT A COMPUTED ONE
------------------------------------------------------------------------------
It is the Burnet, Texas postcode, and Burnet is the post office that serves
**Silver Creek Village** — the unincorporated community in Burnet County on the
eastern shore of Lake Buchanan, about twelve miles north-west of Burnet. That is
the one Texas place carrying the fixture's town name, and it sits an hour up the
road from the Austin ballpark the estate's coordinates are anchored in
(`STREET_GEO`, CR-028). No test can prove a postcode belongs to a town — what
these cases CAN do, and do, is prove that every seeded address takes its three
parts from the one place that states them, so a future correction moves them
together instead of leaving a second copy behind.
"""

import pytest

from apps.customers import models as customers_models
from apps.customers import sample_data as customers_sample
from apps.metering import models as metering_models
from apps.metering import sample_data as metering_sample
from apps.metering import seams as metering_seams
from apps.rating import sample_data as rating_sample
from apps.tenancy import selectors as tenancy_selectors
from core import sample_fixture as fixture

from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import (
    brazosbend_payload,
    provisioned_tenant,
    seed_physical_series,
    staff_actor,
    tenant_ctx,
)

pytestmark = pytest.mark.django_db


@pytest.fixture()
def seeded(growth_plan, identity_seam):  # noqa: F405 — W0 helper fixtures
    """The estate and its accounts, through each module's REAL seeder.

    A water/sewer/trash tenant for `test_cr039_c11_seeded_surcharge`'s reason —
    it is the shape the fixture's own money exists for — and it declares its
    state as the WORD *"Texas"*, exactly as `brazosbend_payload` and
    `seed_demo` do, so the fold is exercised rather than assumed.
    """
    tenant, _ = provisioned_tenant(
        brazosbend_payload(
            name="Silver Creek Water",
            subdomain="silvercreekstate",
            services=["water", "sewer", "trash"],
        )
    )
    seed_physical_series(tenant)
    actor = staff_actor(tenant)
    with tenant_ctx(tenant):
        rating_sample.seed_sample_records(actor)
        metering_sample.seed_sample_records(actor)
        customers_sample.seed_sample_records(actor)
    return tenant, actor


def test_the_fixture_states_a_postal_code_and_not_a_word():
    """`fixture.STATE` is the two-letter form, and the repo's own map agrees.

    This is the half of the ruling that settles the SPELLING. `us_state_code`
    is the normaliser `DEF-444`'s tax-jurisdiction seeding already goes
    through, so asking it is asking the one map rather than a second copy.
    """
    assert fixture.STATE == "TX"
    assert tenancy_selectors.us_state_code(fixture.STATE) == fixture.STATE
    assert fixture.POSTAL == "78611"


def test_the_seam_folds_both_spellings_to_one(seeded):
    """`Texas` and `TX` are one answer by the time they reach an address.

    ⚠ The tenant on this run declares the WORD. If the seam ever stops folding,
    this case fails without needing a seeded estate at all — which is why it is
    asserted here as well as through the rows below: a fold that works only on
    the path the seeder happens to take is not a fold.
    """
    tenant, _ = seeded
    with tenant_ctx(tenant):
        assert metering_seams.tenant_state() == "TX"


def test_an_unrecognised_state_survives_verbatim(seeded):
    """A word the map cannot read is NOT dropped.

    `DEF-2848` is what a missing state costs: `BR-NOT-029` clause (b) held
    every seeded bill out of the print set. So the fold returns the raw text
    when it cannot normalise, and never `None` — the value is somebody's to
    look at, not something to be silently emptied.
    """
    tenant, _ = seeded
    from apps.tenancy import models as tenancy_models

    with tenant_ctx(tenant):
        tenancy_models.Tenant.objects.filter(id=tenant.id).update(state="Ostrobothnia")
        assert metering_seams.tenant_state() == "Ostrobothnia"


def test_the_estate_states_one_state_and_one_postcode(seeded):
    """`select distinct state from premises` answers exactly one thing.

    This is the query in the defect report, run as a test. It answered
    `['TX', 'Texas']` on 2026-09-07.
    """
    tenant, _ = seeded
    with tenant_ctx(tenant):
        rows = list(
            metering_models.Premises.objects.values_list("city", "state", "postal_code")
        )
    assert rows, "no premises were seeded — this case would pass over an empty estate"
    assert {row[1] for row in rows} == {fixture.STATE}
    assert {row[2] for row in rows} == {fixture.POSTAL}
    assert {row[0] for row in rows} == {fixture.CITY}


def test_the_mailing_box_and_the_premises_panel_agree(seeded):
    """The two panels of one account screen name the same place.

    ⚠ **THE LINE MAY LEGITIMATELY DIFFER AND THE TOWN MAY NOT.**
    `customers.addresses` `kind='mailing'` is a genuine second fact — CLAUDE.md
    hard rule 8 names it as one of the three exceptions, because it is where
    the BILL goes and for a landlord that is another building. The fixture uses
    it that way on purpose: the two `CASE_LANDLORD` accounts bill to
    `12 Quarry Hill Ct` rather than to their own units. So this case says
    nothing about `line1`. What it refuses is the estate answering *which town,
    which state, which postcode* two ways, which is not a second fact — it is a
    contradiction.
    """
    tenant, _ = seeded
    with tenant_ctx(tenant):
        mailing = list(
            customers_models.Address.objects.filter(kind="mailing").values_list(
                "city", "state", "postal_code"
            )
        )
        premises = list(
            metering_models.Premises.objects.values_list("city", "state", "postal_code")
        )
    assert mailing, "no mailing addresses were seeded — this case needs rows to compare"
    assert premises, "no premises were seeded — this case needs rows to compare"
    # ⚠ **ROWS AGAINST ROWS, NEVER EITHER SIDE AGAINST `fixture.STATE`.** Both
    # seeders read that one constant, so comparing each of them WITH it is
    # comparing the constant with itself — the check passes on the estate that
    # produced the defect, because on 2026-09-07 the constant said `NE` and
    # both mailing rows agreed with it perfectly while `premises` said `Texas`.
    # It was written that way first and came back green on the old code, which
    # is hard-won law 7's second question answered the hard way.
    assert set(mailing) == set(premises)
    # …and the constant is right as well, which is a SECOND claim and is made
    # separately rather than folded into the one above.
    assert set(premises) == {(fixture.CITY, fixture.STATE, fixture.POSTAL)}
