# ── Trace ──────────────────────────────────────────────
# Change:   CR-056 W6 — A CUSTOMER NUMBER NEEDS A NAME **AND ONE IDENTIFIER**.
#           A name alone no longer creates one.
# Rules:    BR-CUS-1023 (the creation minimum — PO 2026-09-01, verbatim:
#           *"Customer ID - minimum name and one ID - minimum - please make
#           this rule and apply"*, elaborated as *"Customer can be person or
#           company - in case of person, if we have SSN, or DL or Phone number,
#           we create the Customer ID and attached these to customer ID; if it
#           is Company then we ask for Tax ID"*) ·
#           BR-CUS-1022 (identity is per kind) · BR-CUS-089 (the MATCH
#           criteria, and NOT the creation ones) · BR-CUS-054 (the entity and
#           its N:M link) · BR-CUS-019 (advisory) ·
#           CLAUDE.md hard rule 1 (tenant scoping) · hard rule 7 (audit_log) ·
#           law 7 (prove a guard RED first) · B14 rule 32 (no rule id in copy)
# Impacts:  apps/customers/identity_match.creation_minimum ·
#           apps/customers/services.link_customer (the ONE writer) ·
#           the five doors: create_account · create_master_account · move_in ·
#           the bulk import (_commit_import_row / create_from_import) ·
#           service_request_service.link_customer
# ───────────────────────────────────────────────────────
"""**A name in a box used to mint a Customer number. It no longer does.**

THE RULE, IN THE PO'S OWN WORDS (2026-09-01)
============================================
    "Customer ID - minimum name and one ID - minimum - please make this rule
     and apply"

| kind | enough to CREATE a Customer # |
|---|---|
| **person** | a name **AND** (Social Security number **or** driving licence **or** phone) |
| **company** | a name **AND** its Tax ID |

THE ONE DISTINCTION THIS FILE EXISTS TO HOLD DOWN
=================================================
**WHAT IS ENOUGH TO CREATE IS NOT WHAT IS ENOUGH TO MATCH**, and the decision
log of 2026-09-01 predicts in as many words that somebody will collapse the two
within a week. So both halves are asserted here, in one test, on one phone
number:

    A **phone alone CREATES** a customer number — the PO's own list names it.
    A **phone alone is a WEAK match** and moves **$0.00** of anybody's deposit
    (`BR-CUS-089` says *one government ID* and a telephone is not one).

Collapse them in either direction and one of those two assertions goes red.

THE OTHER HALF OF THE RULING, WHICH IS THE HALF THAT COSTS SOMETHING
====================================================================
**The refusal is scoped to the NUMBER and never to the ACCOUNT.** The PO:
*"a person standing at the counter who will not give an identifier still gets
their water."* Every door case below therefore asserts BOTH outcomes on the same
call — the account is there, and the customer number is not — because the one
way to get this wrong that no single assertion catches is to fuse them.

**And the refusal must never be an exception.** Each door runs its customer link
inside its own `transaction.atomic()`, so a `BizError` here would roll the
ACCOUNT back. `TC-8` is the case that would go red on that "tidy-up", and it
asserts the account row exists after the call rather than asserting that no
exception was raised — an assertion about an exception passes on a silent
rollback.

⛔ SUPERSEDED THE SAME DAY, AT ONE CLAUSE — READ THIS BEFORE "FIXING" A CASE
============================================================================
**PO 2026-09-01, verbatim:** *"Without identifier we cannot create Customer ID
or master account ot regular account"*. The identifier now gates **the account**
as well, so `name alone` must eventually create NOTHING — no customer and no
account of either kind.

**Every case here still asserts the right MINIMUM and the right REFUSAL
WORDING.** What is dated is the OTHER half of TC-6, TC-8 and TC-9: each asserts
that the account exists afterwards. **Those assertions encode a clause the PO
has since reversed, not a guarantee** — when the account-level refusal is built
they FLIP to "nothing was created", and that is the rule arriving rather than a
test breaking. They are left standing because the behaviour they describe is
what the code does today, and a test that asserts what the code does not do is
worse than one that is dated.

WHAT IS **NOT** TESTED HERE, DELIBERATELY
=========================================
That existing customers with a name and no identifier still work. `TC-10` makes
one the only way it can now be made — before the rule can see it — and asserts
every read path still serves it. The ruling is explicit that it *"governs what is
WRITTEN from now on"* and invalidates nothing on file.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from apps.customers import identity_match
from apps.customers import models as customers_models
from apps.customers import services as customers_services
from apps.metering import services as metering_services
from apps.rating import models as rating_models
from apps.tenancy import models as tenancy_models

from tests.test_us_met_helpers import *  # noqa: F401,F403 — W1 shared fixtures
from tests.test_us_met_helpers import (  # noqa: F401
    audit_rows,
    brazos,
    dana,
    make_premises,
    make_unit,
    tenant_ctx,
)

pytestmark = pytest.mark.django_db

D = Decimal

PERSON = "Okonkwo, Adaeze"
PERSON_PHONE = "+1 (512) 555-0198"
PERSON_SSN = "555-44-3333"
PERSON_LICENCE = "TX-88213904"
COMPANY = "Rio Verde Property Holdings LLC"
COMPANY_TAX_ID = "12-3456789"


# ═══════════════════════════════════════════════════════════════════════════
# FIXTURE PLUMBING — real rows through real services (DEF-658: never the ORM)
# ═══════════════════════════════════════════════════════════════════════════
def _plan(tenant, name="Residential Standard", service_code="electric"):
    service = tenancy_models.Service.objects.get(code=service_code)
    plan, _ = rating_models.RatePlan.objects.get_or_create(
        tenant=tenant,
        name=name,
        defaults={"code": name.lower().replace(" ", "-"), "status": "published"},
    )
    tariff, _ = rating_models.Tariff.objects.get_or_create(
        tenant=tenant, name=f"{name} — {service_code}", service=service
    )
    rating_models.PlanRateSchedule.objects.get_or_create(
        tenant=tenant, rate_plan=plan, service=service, defaults={"tariff": tariff}
    )
    return plan


def _unit(actor, tenant, *, label, service_code="electric"):
    premises = make_premises(actor, services_available=[service_code])
    unit = make_unit(actor, premises["id"], label=label)
    metering_services.assign_unit_plan(
        actor, unit["id"], {"tariff_id": str(_plan(tenant, service_code=service_code).id)}
    )
    metering_services.ensure_service_point(unit["id"], service_code)
    return unit


def _open(actor, tenant, *, label, name, kind=None, identity=None, external_ref=None):
    """S18 — an account opened through the REAL door with a `customer` block."""
    unit = _unit(actor, tenant, label=label)
    block: dict[str, object] = {"display_name": name}
    if kind is not None:
        block["kind"] = kind
    if identity is not None:
        block["identity"] = identity
    if external_ref is not None:
        block["external_ref"] = external_ref
    return customers_services.create_account(
        actor,
        {
            "unit_id": str(unit["id"]),
            "account_type": "residential",
            "status": "active",
            "opened_at": "2026-07-01",
            "contact": {"full_name": name},
            "customer": block,
        },
    )


def _customers(name):
    return customers_models.Customer.objects.filter(display_name=name)


# ═══════════════════════════════════════════════════════════════════════════
# TC-1..4 · THE RULE ITSELF, on the function that owns it
# ═══════════════════════════════════════════════════════════════════════════
def test_tc1_a_person_is_created_by_any_one_of_the_three_the_po_named():
    """SSN, driving licence **or** phone. Each one alone is enough."""
    for field, value in (
        ("ssn", PERSON_SSN),
        ("driving_licence", PERSON_LICENCE),
        ("phone", PERSON_PHONE),
    ):
        evidence = identity_match.IdentityEvidence(
            name=PERSON, kind=identity_match.KIND_PERSON, **{field: value}
        )
        assert identity_match.creation_minimum(evidence) is None, field


def test_tc2_a_company_is_created_by_its_tax_id_and_by_nothing_else():
    """⚠ **A PHONE DOES NOT CREATE A COMPANY.**

    The PO's list for a business names the Tax ID and nothing else. A phone IS
    capturable for a company (`BR-CUS-1022` allows it and the matcher indexes
    it) — capture and creation are two questions, and this is the cell where
    the two tables differ. A business's phone is answered by whoever is at the
    desk; a Customer number minted on it names nobody.
    """
    with_tax = identity_match.IdentityEvidence(
        name=COMPANY, kind=identity_match.KIND_COMPANY, tax_id=COMPANY_TAX_ID
    )
    assert identity_match.creation_minimum(with_tax) is None

    phone_only = identity_match.IdentityEvidence(
        name=COMPANY, kind=identity_match.KIND_COMPANY, phone=PERSON_PHONE
    )
    shortfall = identity_match.creation_minimum(phone_only)
    assert shortfall is not None
    assert shortfall["missing"] == identity_match.MISSING_IDENTIFIER
    assert shortfall["accepts"] == ["tax_id"]


def test_tc3_neither_kind_borrows_the_other_s_identifier():
    """A Social Security number does not satisfy a company; a Tax ID does not
    satisfy a person. Both directions, because a union would pass one of them."""
    person_with_tax_id = identity_match.IdentityEvidence(
        name=PERSON, kind=identity_match.KIND_PERSON, tax_id=COMPANY_TAX_ID
    )
    assert identity_match.creation_minimum(person_with_tax_id) is not None

    company_with_ssn = identity_match.IdentityEvidence(
        name=COMPANY, kind=identity_match.KIND_COMPANY, ssn=PERSON_SSN
    )
    assert identity_match.creation_minimum(company_with_ssn) is not None


def test_tc4_the_three_shortfalls_are_named_and_each_has_a_sentence():
    """A missing NAME, a missing KIND and a missing IDENTIFIER are three
    different things to fix, and a clerk is told which — never a rule id and
    never an internal code (B14 rule 32 clause 4)."""
    cases = {
        identity_match.MISSING_NAME: identity_match.IdentityEvidence(
            name=None, kind=identity_match.KIND_PERSON, phone=PERSON_PHONE
        ),
        identity_match.MISSING_KIND: identity_match.IdentityEvidence(
            name=PERSON, kind=None, phone=PERSON_PHONE
        ),
        identity_match.MISSING_IDENTIFIER: identity_match.IdentityEvidence(
            name=PERSON, kind=identity_match.KIND_PERSON
        ),
    }
    for expected, evidence in cases.items():
        shortfall = identity_match.creation_minimum(evidence)
        assert shortfall is not None and shortfall["missing"] == expected
        payload = identity_match.not_created_payload(shortfall)
        assert payload["code"] == identity_match.NOT_CREATED
        assert payload["message_key"].startswith("customers.customer.")
        # No rule id anywhere in what reaches the clerk.
        assert "BR-" not in payload["message_key"]

    # A date of birth is one of BR-CUS-089's MATCHING facts and is NOT an
    # identifier: a row minted on a name and a birthday holds nothing the
    # matcher can ever make strong.
    dob_only = identity_match.IdentityEvidence(
        name=PERSON, kind=identity_match.KIND_PERSON, date_of_birth="1974-03-02"
    )
    assert identity_match.creation_minimum(dob_only) is not None


# ═══════════════════════════════════════════════════════════════════════════
# TC-5 · THE DISTINCTION THAT WILL BE COLLAPSED — create vs match, one phone
# ═══════════════════════════════════════════════════════════════════════════
def test_tc5_a_phone_creates_and_the_same_phone_is_only_a_weak_match(dana, brazos):
    """**Both halves, on one number, in one test.**

    A phone alone CREATES (the PO's list). The same phone alone is a WEAK match
    and moves nothing (`BR-CUS-089`: *one government ID*, and a telephone is
    not one). Reconcile them and exactly one of these assertions goes red.
    """
    with tenant_ctx(brazos):
        first = _open(
            dana, brazos, label="Phone A", name=PERSON, kind="person",
            identity={"phone": PERSON_PHONE},
        )
        # HALF ONE — it created.
        assert first["customer"]["customer_no"], first.get("customer_not_created")

        second = _open(
            dana, brazos, label="Phone B", name=PERSON, kind="person",
            identity={"phone": PERSON_PHONE},
        )
        # HALF TWO — the same evidence against the same person on file is
        # WEAK, so nothing was recognised and nothing could carry a deposit.
        match = second["customer_match"]
        assert match["tier"] is None
        assert match["recognised"] is False
        # And a second, separate customer number exists rather than a merge.
        assert _customers(PERSON).count() == 2


# ═══════════════════════════════════════════════════════════════════════════
# TC-6..9 · THE DOORS. Each asserts BOTH outcomes: account yes, number no.
# ═══════════════════════════════════════════════════════════════════════════
def test_tc6_s18_a_name_with_no_identifier_now_opens_NO_ACCOUNT(dana, brazos):
    """⛔ **THIS ASSERTION WAS REVERSED ON 2026-09-01 AND THE REVERSAL IS THE
    POINT OF THE TEST (`BR-CUS-1024`).**

    It was `test_tc6_s18_a_name_with_no_identifier_opens_the_account_and_mints_
    nothing`, and it asserted — correctly, that morning — that *the account is
    there* and only the number was withheld. **PO verbatim, later the same
    day:** *"Without identifier we cannot create Customer ID or master account
    ot regular account"*, which supersedes this rule's own clause *"An account
    may still be opened… a person standing at the counter who will not give an
    identifier still gets their water."*

    The two outcomes are now deliberately FUSED at this door, and the assertion
    is that **no account row exists**, not that an exception was raised — an
    exception assertion passes on a silent half-write.
    """
    with tenant_ctx(brazos):
        before = customers_models.Account.objects.count()
        with pytest.raises(Exception) as caught:
            _open(dana, brazos, label="Counter", name=PERSON, kind="person")

        assert getattr(caught.value, "br_ref", None) == "BR-CUS-1024"
        assert (
            getattr(caught.value, "message_key", "")
            == "customers.account.identity_required_person"
        )
        # NOTHING was written — not the account, not the customer.
        assert customers_models.Account.objects.count() == before
        assert _customers(PERSON).count() == 0

    # And the skip itself is unchanged where it still applies: `creation_minimum`
    # is still a pure predicate and still never raises. What changed is that the
    # counter doors ask it BEFORE they open a transaction.
    shortfall = identity_match.creation_minimum(
        identity_match.IdentityEvidence(name=PERSON, kind=identity_match.KIND_PERSON)
    )
    assert shortfall["missing"] == identity_match.MISSING_IDENTIFIER


def test_tc7_s18_an_identifier_with_no_kind_cannot_be_resolved(dana, brazos):
    """`BR-CUS-1022` — which identifier counts depends on the kind, so an
    identity with no kind is refused BY NAME at the door, before the account."""
    with tenant_ctx(brazos):
        with pytest.raises(Exception) as caught:
            _open(
                dana, brazos, label="No kind", name=PERSON, kind=None,
                identity={"ssn": PERSON_SSN},
            )
        assert "kind_required_for_identity" in str(
            getattr(caught.value, "message_key", "")
        ) or "kind_required_for_identity" in str(caught.value)


def test_tc8_the_master_account_door_now_refuses_an_owner_name_alone(dana, brazos):
    """⛔ **REVERSED 2026-09-01, AND THIS IS THE EXACT QUESTION THE PO WAS
    ASKED.** It was `test_tc8_the_master_account_door_opens_on_an_owner_name_
    alone` and asserted that the master account was *created anyway*.

    `CR-058` raised it as one of three things it would not assume: *what a
    master account does when the owner has a name and no identifier*. **PO
    verbatim:** *"Without identifier we cannot create Customer ID or master
    account ot regular account"*.

    The address's owner is still FREE TEXT and still may name a person or a
    limited company — that half is unchanged, and it is why the shortfall is a
    missing KIND. What changed is that the door now refuses instead of opening
    an account with nobody identifiable behind it.
    """
    with tenant_ctx(brazos):
        before = customers_models.Account.objects.count()
        premises = make_premises(dana, services_available=["electric"])
        with pytest.raises(Exception) as caught:
            customers_services.create_master_account(
                dana,
                {
                    "premises_id": str(premises["id"]),
                    "account_type": "residential",
                    "opened_at": "2026-07-01",
                    "contact": {"full_name": "Ruiz, Marisol"},
                },
            )
        assert getattr(caught.value, "br_ref", None) == "BR-CUS-1024"
        assert (
            getattr(caught.value, "message_key", "")
            == "customers.account.identity_kind_required"
        )
        assert customers_models.Account.objects.count() == before
        assert _customers("Ruiz, Marisol").count() == 0


def test_tc9_the_bulk_import_loads_the_account_creates_nobody_and_flags_the_row(dana, brazos):
    """**The door this ruling costs.** A staged row carries a name and a legacy
    reference and no identity at all, so no number is minted — and the row is
    FLAGGED durably rather than only counted, because a count in a response is
    gone the moment the wizard closes."""
    with tenant_ctx(brazos):
        unit = _unit(dana, brazos, label="Imported")
        account = customers_services.create_from_import(
            actor=dana,
            payload={
                # The row a real cutover file produces: a NAME and a LEGACY
                # REFERENCE, and no identity at all. `customer_ref` is a
                # reconciliation key and its own comment in `services.py` says
                # so — it was never evidence about a person.
                "mapped": {"customer_ref": "LEGACY-4471", "customer_name": PERSON},
                "unit_id": str(unit["id"]),
                "account_no": "A-40001",
                "currency": "USD",
                "cutover_on": "2026-07-01",
                "import_run_id": None,
                "account": {"account_type": "residential", "opened_at": "2026-07-01"},
            },
        )
        assert account["account_no"]
        assert account["customer_no"] is None
        assert account["customer_not_created"]["missing"] == identity_match.MISSING_KIND
        assert _customers(PERSON).count() == 0


# ═══════════════════════════════════════════════════════════════════════════
# TC-10 · WHAT THE RULE DOES **NOT** DO
# ═══════════════════════════════════════════════════════════════════════════
def test_tc10_a_customer_already_on_file_with_no_identifier_stays_lawful(dana, brazos):
    """The ruling *"governs what is WRITTEN from now on"* and invalidates
    nothing. A row that predates it is displayable, findable and LINKABLE —
    the minimum gates CREATION and never a link."""
    with tenant_ctx(brazos):
        legacy = customers_models.Customer.objects.create(
            tenant_id=brazos.id,
            customer_no="C-000001",
            kind="person",
            display_name="Pre-Rule, Patricia",
            external_ref="LEGACY-0001",
        )
        # It reads back through the ordinary selector — no screen refuses it.
        assert customers_models.Customer.objects.filter(pk=legacy.pk).exists()

        # And a NEW account naming that same legacy ref LINKS to it rather than
        # being refused for having no identifier: the row already exists.
        unit = _unit(dana, brazos, label="Returning")
        linked = customers_services.link_customer(
            account_id=str(
                customers_services.create_account(
                    dana,
                    {
                        "unit_id": str(unit["id"]),
                        "account_type": "residential",
                        "status": "active",
                        "opened_at": "2026-07-01",
                        "contact": {"full_name": "Pre-Rule, Patricia"},
                        # ⛔ `BR-CUS-1024` (2026-09-01) — the account itself now
                        # needs an identifier, **and naming a customer already
                        # on file IS one**: the door's guard lets an
                        # `external_ref` through precisely because it points at
                        # a row that EXISTS, which is what this rule protects
                        # rather than blocks.
                        #
                        # **THE POINT OF THIS CASE IS UNCHANGED and is now made
                        # twice over:** a legacy row holding a name and no
                        # identifier still opens an account and still takes the
                        # link, and no second customer is minted for it.
                        "customer": {
                            "display_name": "Pre-Rule, Patricia",
                            "external_ref": "LEGACY-0001",
                        },
                    },
                )["id"]
            ),
            external_ref="LEGACY-0001",
            display_name="Pre-Rule, Patricia",
        )
        assert linked["id"] == str(legacy.id)
        assert linked.get("not_created") is None
        assert _customers("Pre-Rule, Patricia").count() == 1


def test_tc14_the_rule_reaches_all_five_doors_through_ONE_writer():
    """**The claim is FIVE doors, so five doors are checked — structurally.**

    Four of them create, and they create through exactly one function. If a lane
    ever adds a SECOND `Customer.objects.create`, the minimum stops applying at
    that door and every case above still passes — which is why this reads the
    module rather than exercising a fixture.

    The fifth is not a creating door at all. `service_request_service` points an
    application at a customer row a **human already chose**; it holds no
    `Customer.objects.create` anywhere. That was CHECKED rather than assumed,
    and it is written down here so the next lane does not have to re-derive it.
    """
    import ast
    from pathlib import Path

    backend = Path(__file__).resolve().parents[1]

    def creates_customer(relative: str) -> int:
        tree = ast.parse((backend / relative).read_text(encoding="utf-8"))
        count = 0
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            source = ast.unparse(node.func)
            if source.endswith("Customer.objects.create"):
                count += 1
        return count

    # ONE creator, in the module that owns the rule.
    assert creates_customer("apps/customers/services.py") == 1
    # And none in the module that only LINKS.
    assert creates_customer("apps/customers/service_request_service.py") == 0

    # The three payload doors all admit the same block, so they all reach that
    # one creator with the same evidence. `move_in` in particular: US-CUS-004
    # takes `CREATE_FIELDS` minus the unit, so the customer block rides it.
    for field_set in (
        customers_services.CREATE_FIELDS,
        customers_services.MOVE_IN_FIELDS,
        customers_services.MASTER_CREATE_FIELDS,
        customers_services.IMPORT_ACCOUNT_FIELDS,
    ):
        assert "customer" in field_set


def test_tc12_every_refusal_sentence_exists_in_the_catalogue():
    """A `message_key` that resolves to nothing renders as SILENCE.

    ⚠ **`G32` CANNOT SEE THESE KEYS AND THAT IS WHY THIS CASE EXISTS.** That
    gate reads `message_key=` keyword arguments with `ast`; these live as the
    VALUES of a dict literal, which is the same blind spot its own docstring
    records for the three `field_errors` keys that were absent from every
    catalogue on the day it was written. The PO ruling of 2026-08-19 suppresses
    `params.detail`, so an unresolved key here means the clerk clicks, no
    customer number appears, and **nothing at all is said about why**.
    """
    import json
    from pathlib import Path

    catalogue = json.loads(
        (
            Path(__file__).resolve().parents[2] / "07-frontend/src/i18n/locales/en.json"
        ).read_text(encoding="utf-8")
    )
    keys = set(identity_match.NOT_CREATED_MESSAGE_KEY.values())
    missing = sorted(key for key in keys if key not in catalogue)
    assert not missing, missing

    # And every sentence a clerk reads is free of rule ids and internal codes
    # (B14 rule 32 clause 4).
    for key in keys:
        sentence = catalogue[key]
        assert "BR-" not in sentence and "DEF-" not in sentence and "OQ-" not in sentence, sentence
        assert "customer_" not in sentence, sentence


def test_tc13_every_kind_and_shortfall_pair_has_a_sentence():
    """The lookup is total. A pair with no entry is a `KeyError` on a live door,
    which is a 500 where the ruling asked for a sentence."""
    kinds = (None, identity_match.KIND_PERSON, identity_match.KIND_COMPANY)
    for missing in (
        identity_match.MISSING_NAME,
        identity_match.MISSING_KIND,
        identity_match.MISSING_IDENTIFIER,
    ):
        for kind in kinds:
            shortfall = {"missing": missing, "kind": kind, "accepts": []}
            if (missing, kind) not in identity_match.NOT_CREATED_MESSAGE_KEY:
                # Only the pairs `creation_minimum` can actually produce must
                # exist: a missing KIND is never reported WITH a kind, and a
                # missing IDENTIFIER is never reported without one.
                assert (missing, kind) in {
                    (identity_match.MISSING_KIND, identity_match.KIND_PERSON),
                    (identity_match.MISSING_KIND, identity_match.KIND_COMPANY),
                    (identity_match.MISSING_IDENTIFIER, None),
                }, (missing, kind)
                continue
            assert identity_match.not_created_payload(shortfall)["message_key"]


def test_tc11_the_skip_writes_an_audit_row(dana, brazos, audit_rows):
    """CLAUDE.md hard rule 7 — the decision NOT to mint a number gates a deposit
    carry-forward exactly as a weak match does, and a refusal that leaves no
    trace is a customer nobody can account for."""
    # ⛔ **THE DOOR MOVED ON 2026-09-01 AND THE RULE DID NOT (`BR-CUS-1024`).**
    # This used to run through S18, which now REFUSES a name with no identifier
    # rather than skipping the number. The skip — and therefore this audit row —
    # still happens at every door that is NOT gated, and the bulk import is the
    # one that matters: it carries a name and a legacy reference and no identity
    # at all, so it is where a real utility meets this. The rule under test is
    # unchanged: **a decision NOT to mint a number writes `audit_log`.**
    with tenant_ctx(brazos):
        unit = _unit(dana, brazos, label="Audited")
        created = customers_services.create_from_import(
            actor=dana,
            payload={
                "mapped": {"customer_ref": "LEGACY-9001", "customer_name": PERSON},
                "unit_id": str(unit["id"]),
                "account_no": "A-49001",
                "currency": "USD",
                "cutover_on": "2026-07-01",
                "import_run_id": None,
                "account": {"account_type": "residential", "opened_at": "2026-07-01"},
            },
        )
        rows = [row for row in audit_rows if row.get("action") == "customer.not_created"]
        assert rows, sorted({row.get("action") for row in audit_rows})
        blob = rows[-1]["after"]
        # ⚠ **THE SHORTFALL THE IMPORT RECORDS IS THE *KIND*, NOT THE
        # IDENTIFIER**, and that is `creation_minimum`'s own order: which
        # identifier counts depends on the kind, so an unstated kind is
        # reported first, because it is the first thing a human must supply.
        # A mapping that DID carry a kind would report the identifier. The
        # rule under test is unchanged — a decision not to mint a number
        # writes `audit_log` — and it is the DOOR that moved on 2026-09-01.
        assert blob["missing"] == identity_match.MISSING_KIND
        assert blob["display_name"] == PERSON
        # The ACCOUNT is the entity: there is no customer row to key on, which
        # is the whole point of the row.
        assert str(created["id"]).replace("-", "") == str(rows[-1]["entity_id"]).replace("-", "")
