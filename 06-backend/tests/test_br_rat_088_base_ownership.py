# ── Trace ──────────────────────────────────────────────
# Rules:    BR-RAT-088 (PO ruling 2026-08-20, closing B1/OQ-238 — the CHARGE
#           CODE owns the base) · §A3 (the activation gate) · BR-RAT-080
# ───────────────────────────────────────────────────────
"""P1b's data side: the seed AUTHORS a base charge code, and the gate reads it.

WHY THIS FILE EXISTS SEPARATELY FROM THE CHAIN TESTS
----------------------------------------------------
`test_cr013_resolution_chain.py` proves `resolve_base_charge` picks the right
row. This proves the two things around it that a pure-function test cannot see:
that a base charge code EXISTS to be picked, and that §A3's activation gate
turns itself on only for a tenant that has one.

THE SEED MAY AUTHOR THIS; A MIGRATION MAY NOT
---------------------------------------------
Until P1b the demo tenant had **no base charge code for any service** — the base
lived only on `tariff_versions.base_charge`, so there was nothing to cut over to.
A data migration cannot fill that gap, because it inherits a tenant's own codes
and would have to GUESS which one is the base by matching `BASE-<service>` —
the hard-coded vocabulary B12 forbids, and one that fails silently for a tenant
who names theirs anything else. The seed does not guess; it declares.
"""

from apps.tenancy.management.commands.seed_demo import CHARGE_CODES, RATE_SCHEDULES
from core import sample_fixture as fixture


def _by_code():
    return {entry["code"]: entry for entry in CHARGE_CODES}


def _base_key(entry):
    """The tuple BR-RAT-108 narrows a base by, minus meter size.

    Service first (`charges.service_id`), then customer class
    (`charges.applies_to_customer_classes`). Meter size is the THIRD dimension
    and it lives in `charge_code_amounts`, not on the code, so it is not part of
    a seeded code's identity. NULL or `[]` means every class (BR-RAT-108), and
    every seeded code means exactly that today — so it normalises to `None`
    rather than to an empty tuple, because "all classes" is a value and not an
    absence of one.
    """
    classes = entry.get("applies_to_customer_classes") or None
    return (entry.get("service"), tuple(sorted(classes)) if classes else None)


def test_exactly_one_declared_base_per_service_and_customer_class():
    """⚠ AMENDED 2026-08-24 (DEF-630). THIS TEST USED TO ASSERT A GLOBAL COUNT
    OF ONE AND WAS RED ON THE BRANCH, AND THE SEED WAS NOT WHAT WAS WRONG.

    It was written when the seed declared `BASE-W` and nothing else, and it read
    §A3's *"two base codes is a duplication"* as a statement about the WHOLE
    seed. It is not. BR-RAT-108 (PO 2026-08-21) states the narrowing in three
    dimensions — **service** → **account type** → **meter size** — and says in
    as many words that two base codes for one service *"does not make two
    matching base codes legal — it makes them SEPARABLE"*. Two codes on
    DIFFERENT services were never the thing forbidden; this file's own next
    test has always said so: *"a plan covering water and electric carries two
    base codes and each service must get its own"*.

    `BASE-E` then arrived because it had to. DEF-528 (critical) records why:
    BR-RAT-088's guard is self-activating per tenant, so declaring `BASE-W`
    ALONE armed a refusal that killed `seed_demo` at the first electric
    schedule — a fresh deployment could not be seeded at all. The seed's own
    rule is *"a base charge code is seeded for EVERY service this seed prices,
    or for none"*, and `RATE_SCHEDULES` prices two.

    So the invariant is per-key, and it is STRONGER than the count it replaces:
    a global count of one passes for a seed with a single WRONG base, while this
    fails the moment any (service, class) pair carries two — which is the
    ambiguity `DEF-468` makes `resolve_base_charge` refuse at run time. What the
    old assertion actually caught — a penalty flagged `is_base` — is caught by
    `test_no_other_seeded_code_claims_to_be_a_base` below, which now names the
    bases by their flag instead of hard-coding one code string.
    """
    declared = [e for e in CHARGE_CODES if e.get("is_base")]
    assert declared, "the seed declares no base charge at all — DEF-528"

    seen: dict[tuple, list[str]] = {}
    for entry in declared:
        seen.setdefault(_base_key(entry), []).append(entry["code"])
    duplicated = {key: codes for key, codes in seen.items() if len(codes) > 1}
    assert not duplicated, (
        "two base charge codes share one (service, customer class) — "
        f"R4 cannot choose between them and DEF-468 refuses the bill: {duplicated}"
    )


def test_every_service_the_seed_PRICES_has_a_base_and_no_service_it_does_not():
    """DEF-528's rule, asserted rather than described.

    *"A base charge code is seeded for EVERY service this seed prices, or for
    none."* The guard is self-activating, so a seed that prices three services
    and declares two bases does not ship a partial feature — it refuses the
    third service's schedule and the whole seed dies. This is the test that goes
    red the day a third service is priced and nobody adds its base.
    """
    priced = {s["service"] for s in RATE_SCHEDULES if s.get("service")}
    based = {e["service"] for e in CHARGE_CODES if e.get("is_base")}
    assert based == priced, (
        "the set of services with a base charge code must equal the set the "
        f"seed prices — priced-without-a-base {priced - based}, "
        f"based-without-a-price {based - priced}"
    )


def test_the_base_is_flagged_and_bound_to_its_service():
    """`is_base` alone is not enough — `resolve_base_charge` matches on BOTH the
    flag and the service, because a plan covering water and electric carries two
    base codes and each service must get its own."""
    base = _by_code()["BASE-W"]
    assert base["is_base"] is True
    assert base["service"] == "water"
    assert base["charge_type"] == "recurring"


def test_the_figure_is_the_SCHEDULES_OWN_and_was_not_re_typed():
    """B12 §No hard-coded values. The base did not change value when it changed
    owner — it is `fixture.WATER_BASE`, the same [W] §1 figure the water schedule
    has always priced with. A second literal here would be a second source of
    truth for the exact fact this ruling exists to make singular."""
    assert _by_code()["BASE-W"]["amount"] == fixture.WATER_BASE


def test_no_other_seeded_code_claims_to_be_a_base():
    """LATE, CONN, DISC, NSF and TAMPER are penalties and one-times. A penalty
    flagged `is_base` would make R4 resolve a late fee as a customer's base
    charge — a wrong bill in which every row is individually correct."""
    # ⚠ AMENDED 2026-08-24 (DEF-630): this used to exempt the single literal
    # `"BASE-W"`, which made it fail on `BASE-E` — a base code doing exactly
    # what BR-RAT-088 requires. Hard-coding ONE code string is the same
    # name-matching that BR-RAT-088's own docstring forbids a migration from
    # doing ("fails silently for a tenant that names theirs anything else"),
    # and it is why this test could not survive a second service. It now
    # exempts codes by their `charge_type`, which is the fact that actually
    # distinguishes a base from a penalty.
    for entry in CHARGE_CODES:
        if entry.get("is_base"):
            assert entry["charge_type"] == "recurring", (
                f"{entry['code']} is flagged is_base but is a "
                f"{entry['charge_type']} — a base is charged because a "
                "connection EXISTS (BR-RAT-080), so it recurs"
            )
            assert entry.get("service"), (
                f"{entry['code']} is flagged is_base with no service — R4 "
                "narrows by service FIRST (BR-RAT-108) and cannot place it"
            )
        else:
            assert entry["charge_type"] != "recurring" or "service" in entry, entry["code"]

    # The failure mode the original test was written for, kept verbatim in
    # intent: a PENALTY or ONE-TIME code must never claim to be a base.
    for entry in CHARGE_CODES:
        if entry["charge_type"] in {"penalty", "one_time"}:
            assert not entry.get("is_base"), entry["code"]
