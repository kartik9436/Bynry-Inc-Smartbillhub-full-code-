# ── Trace ──────────────────────────────────────────────
# Defects: DEF-2585 · DEF-2398 · DEF-2392 · DEF-3343 · DEF-2343 · DEF-3157 ·
#          DEF-3220 — SEVEN register rows, all of them the SAME defect: a
#          fixture that opens an account with a name and no identifier, which
#          BR-CUS-1024 has refused since 2026-09-01.
# Rules:   BR-CUS-1024 (a door about to mint a customer number matches first;
#          no identifier, no account) · BR-CUS-1023 (the creation minimum) ·
#          BR-CUS-1022 (identity is per kind) · BR-CUS-089 (the MONEY test,
#          untouched by anything here)
# ───────────────────────────────────────────────────────
"""THE ONE WAY A TEST FIXTURE OPENS AN ACCOUNT WITH A VALID IDENTIFIER.

NOT a test module and deliberately not named like one: pytest collects
`tests/test_*.py`, and a helper that defines pytest fixtures AND is imported by
several test modules registers those fixtures twice. So this file holds PLAIN
FUNCTIONS only, in the shape of `tests/sub_metering_fixtures.py`,
`tests/cost_of_service_fixtures.py` and `tests/ledger_le_fixtures.py`.

════════════════════════════════════════════════════════════════════════════
WHY IT EXISTS — ONE DEFECT THAT WAS FILED SEVEN TIMES
════════════════════════════════════════════════════════════════════════════
`BR-CUS-1024` landed on 2026-09-01 (PO verbatim: *"Without identifier we cannot
create Customer ID or master account ot regular account"*). It is CORRECT and it
is signed law. What it reversed is what a FIXTURE is allowed to build: a payload
carrying `contact.full_name` and no `customer` block opened an account until
that morning and has raised `BIZ-COMPLETENESS` ever since — in SETUP, before a
single assertion of the file it takes down runs.

Nothing in this repository enumerates the suites that construct an account, so
the casualties were found one lane at a time, each lane filing the file in front
of it, each honestly, and **the aggregate never existed anywhere**:

    DEF-2585  3 tests   the rule's own landing commit, two suites
    DEF-2398  2 tests   the accounts import suite (0 of 3 accounts created)
    DEF-2392  16 tests  a move-out file, one case `isolation`-marked
    DEF-3343  12 tests  two billing suites, hidden under DEF-3086's first cause
    DEF-2343  17 tests  the deposit carry-forward suite
    DEF-3157  2 tests   two collection-ladder master-account cases
    DEF-3220  17 tests  every close-out case, through a shared W7 fixture

Seven rows, five different lanes, and every one of them says the same sentence
in its `escape_reason`: *nothing on the branch runs the files that share a
fixture together*. **The durable fix is not a seventh single-file repair — it is
ONE shape, defined here, that every one of those fixtures calls**, so the next
rule that changes what a WRITE requires moves one file instead of twenty-four.

════════════════════════════════════════════════════════════════════════════
THE SHAPE, AND IT IS COPIED RATHER THAN INVENTED
════════════════════════════════════════════════════════════════════════════
`apps/customers/sample_data._customer_block` already goes THROUGH the rule
instead of around it — its own comment says why — and this is the same answer in
the same words:

    a person   ->  name + a `555-` phone, the reserved-for-fiction range
    a company  ->  name + `99-0001234`, the IRS's own reserved Tax ID range

⚠ **A PHONE, AND NOT AN SSN OR A DRIVING LICENCE, AND THE CHOICE IS THE WHOLE
POINT.** `BR-CUS-1023` accepts a phone as enough to MINT a number. `BR-CUS-1024`
does **not** accept one as enough to REUSE somebody else's — its matching test is
the name plus a GOVERNMENT-grade identifier — and `BR-CUS-089` does not accept
one as enough to move MONEY. So a fixture identified by phone:

  * opens its account, which is all these files ever wanted;
  * mints its OWN customer number and can never silently reuse another
    fixture's, however many suites share the constant below;
  * records **no tier and no confirmer**, so `discounts.carry_forward_offer`
    still refuses and **$0.00** of anybody's deposit moves.

⚠ **A COMPANY IS THE OTHER CASE AND IT IS STATED RATHER THAN LEFT TO BE
FOUND.** `BR-CUS-1024`'s reuse test for a company IS the name plus the Tax ID,
and `tier_for` calls that pair **strong** — so two company fixtures presenting
the SAME display name in the SAME tenant share one customer row, by the rule and
not by accident. No file repaired here does that (each company name appears
once), and a lane that adds a second must either give it its own name or pass an
explicit `tax_id=`. It is why the person default is a phone and not an SSN: for a
person there is no such coupling at all.

**No assertion in any repaired file moves, and none may.** These suites are about
move-outs, close-outs, ladders, deposits and billing; not one of them is about
identity. If a repair here would change what a money test asserts, the file is
NOT repaired here — that is a signed-figure question and it goes back to the PO.

⚠ **NOTHING HERE IS INVENTED TO GET PAST THE RULE.** The `555-01xx` block is
reserved for fiction and `99-0001234` is in the IRS's reserved range; both are
values the repo already writes. `BR-CUS-1024` forbids a placeholder phone or a
zeroed Tax ID **on a real party** — a fixture's fictional tenant is not a real
party, and the demo seed made exactly this call on 2026-09-01 (decision log,
*THE DEMO FIXTURE'S PEOPLE KEEP THEIR CUSTOMER NUMBERS, AND NOTHING WAS INVENTED
TO DO IT*). One rule applied twice, not two lanes each deciding for themselves.

════════════════════════════════════════════════════════════════════════════
HOW TO USE IT
════════════════════════════════════════════════════════════════════════════
    from tests import identity_fixtures

    customers_services.create_account(actor, identity_fixtures.with_identity({
        "unit_id": str(unit["id"]),
        "account_type": "residential",
        "status": "active",
        "opened_at": "2026-07-01",
        "contact": {"full_name": "Sarah Miller"},
    }))

`with_identity` reads the name off `contact.full_name` and the kind off
`account_type`, so a caller adds four words and no literal. A payload that
ALREADY carries a `customer` block is returned untouched — a fixture that made a
deliberate identity choice keeps it.

⚠ **THE SWEEP OF 2026-09-03 USED THE OTHER FORM AND THAT IS NOT AN OVERSIGHT.**
Thirty files took `"customer": customer_block(name, account_type="residential")`
as one line INSIDE the payload they already had, because a wrapper around a
literal reindents it and a reindented dict is a diff nobody can read for the
thing that matters. `with_identity` is for a payload built somewhere else — a
variable, a helper's `**overrides`, a master door — where there is no literal to
put a key into. Both produce the identical block; pick whichever leaves the
smaller diff.

It serves all three gated doors, because all three take the same block:
`POST /accounts` (`CREATE_FIELDS`), `POST /accounts/{id}/move-in`
(`MOVE_IN_FIELDS`) and `POST /accounts/master` (`MASTER_CREATE_FIELDS`).
"""

from __future__ import annotations

from typing import Any

#: The reserved-for-fiction number every repaired fixture presents. ONE constant
#: and not one per file: a phone is not a reuse identifier under `BR-CUS-1024`,
#: so sharing it cannot make two fixtures collide on a customer number, and a
#: per-file literal would be twenty-four chances to type a real one.
SAMPLE_PERSON_PHONE = "+1 (512) 555-0161"

#: The IRS's own reserved range, and the SAME literal
#: `apps/customers/sample_data.SAMPLE_COMPANY_TAX_ID` writes. Kept as a separate
#: constant rather than imported because a test helper importing app constants
#: makes a fixture's identity move when the demo seed's does, and those are two
#: decisions. `test_identity_fixtures_shape.py` asserts they agree.
SAMPLE_COMPANY_TAX_ID = "99-0001234"

#: `!= "residential"` and not `== "commercial"`, which is `sample_data`'s own
#: reading and for its own reason: a `government` or `industrial` account is an
#: ORGANISATION, and calling it a person asks a public works department for a
#: driving licence.
_PERSON_ACCOUNT_TYPE = "residential"


def customer_kind_for(account_type: Any) -> str:
    """Which identity kind an account type implies — `BR-CUS-1022`."""
    return "person" if account_type == _PERSON_ACCOUNT_TYPE else "company"


def person_customer(
    display_name: str,
    *,
    phone: str = SAMPLE_PERSON_PHONE,
    external_ref: str | None = None,
) -> dict[str, Any]:
    """A `customer` block for a person: name + a `555-` phone (`BR-CUS-1023`)."""
    block: dict[str, Any] = {
        "display_name": display_name,
        "kind": "person",
        "identity": {"phone": phone},
    }
    if external_ref is not None:
        block["external_ref"] = external_ref
    return block


def company_customer(
    display_name: str,
    *,
    tax_id: str = SAMPLE_COMPANY_TAX_ID,
    external_ref: str | None = None,
) -> dict[str, Any]:
    """A `customer` block for a company: name + Tax ID (`BR-CUS-1023`)."""
    block: dict[str, Any] = {
        "display_name": display_name,
        "kind": "company",
        "identity": {"tax_id": tax_id},
    }
    if external_ref is not None:
        block["external_ref"] = external_ref
    return block


def customer_block(
    display_name: str,
    *,
    kind: str | None = None,
    account_type: Any = None,
    external_ref: str | None = None,
    phone: str = SAMPLE_PERSON_PHONE,
    tax_id: str = SAMPLE_COMPANY_TAX_ID,
) -> dict[str, Any]:
    """The block for either kind. `kind` wins; otherwise it follows the type."""
    resolved = kind or customer_kind_for(account_type)
    if resolved == "company":
        return company_customer(display_name, tax_id=tax_id, external_ref=external_ref)
    return person_customer(display_name, phone=phone, external_ref=external_ref)


def with_identity(
    payload: dict[str, Any],
    *,
    display_name: str | None = None,
    kind: str | None = None,
    external_ref: str | None = None,
    phone: str = SAMPLE_PERSON_PHONE,
    tax_id: str = SAMPLE_COMPANY_TAX_ID,
) -> dict[str, Any]:
    """Return `payload` with the `customer` block `BR-CUS-1024` requires.

    ⚠ **A PAYLOAD THAT ALREADY CARRIES ONE IS RETURNED UNCHANGED**, even when
    that block is short of the minimum. A fixture asserting the REFUSAL is a
    real and necessary test — `test_cr058_w1_one_customer_every_door.py` is full
    of them — and a helper that quietly completed every block would turn those
    green by making the product untestable, which is the failure this whole
    repair exists to avoid.

    ⚠ **IT COPIES.** The caller's dict is not mutated; several of the repaired
    fixtures build one payload and post it twice.
    """
    if "customer" in payload:
        return payload
    name = display_name
    if name is None:
        contact = payload.get("contact")
        name = (contact or {}).get("full_name") if isinstance(contact, dict) else None
    if not name:
        # `BR-CUS-1024`'s third row — a payload presenting NO party at all is
        # not a payload that failed to identify one, and the door lets it
        # through untouched. Inventing a name here would put this helper in the
        # business of deciding who an account belongs to.
        return dict(payload)
    return {
        **payload,
        "customer": customer_block(
            name,
            kind=kind,
            account_type=payload.get("account_type"),
            external_ref=external_ref,
            phone=phone,
            tax_id=tax_id,
        ),
    }
