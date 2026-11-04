# ── Trace ──────────────────────────────────────────────
# Defect:  DEF-2803 (2026-08-31) — TWO hand-written `discount_row` functions
#          serve the same DIS-01 landing row and they have already diverged.
#          `apps/rating/discount_services.discount_row` is what a WRITE hands
#          back (and therefore what the DIS-02 wizard reads after a save);
#          `apps/rating/selectors.discount_row` is what the READ path serves
#          the landing. Before BR-RAT-960's lane the services copy served a raw
#          value string and NO `value_display` at all, so the same discount
#          showed a formatted figure on the landing and an unformatted one in
#          the wizard's response.
# Rules:   BR-RAT-087 (a client may not format a money value — the server
#          serves the display string) · BR-RAT-960 (a usage allowance carries
#          the unit it resolved to) · CLAUDE.md hard-won law 5, read for what it
#          MEANS rather than for the word "generated"
# Tests:   this file
# ───────────────────────────────────────────────────────
"""DEF-2803 — the two DIS-01 row shapes, compared.

WHY THIS GUARD EXISTS AND WHY IT IS A *SUBSET* CHECK
-----------------------------------------------------
Hard-won law 5 is *"one generated file, committed once"* and is written about
GENERATED files, so **two hand-written copies of one row shape do not read as an
instance of it** — which is exactly why this drifted with nothing objecting.
Each suite exercises its own path and both are green; a reader of one file has
no reason to suspect a second function of the same name in a sibling module.

DEF-2803's prevention column proposes the cheap interim guard as

    set(services.discount_row(d)) == set(selectors.discount_row(d))

and **that assertion cannot pass today**, which is worth stating rather than
quietly weakening. The read row legitimately carries three fields the write row
has no business inventing — `version_id`, `version_no`, `version_status` — which
describe WHICH VERSION was read, a question a freshly-created discount's
response does not answer the same way.

So the shape asserted here is a RATCHET rather than an equality: the write row's
keys must be a subset of the read row's, and the difference must be EXACTLY
those three. Add a field to one side only and this goes red naming it, which is
the whole ask. Reconciling the two into one function is a contract change across
`rating/api.py` and the wizard's response type; DEF-2803 says so and says it
needs its own change rather than being taken inside a ruling lane.

⚠ THE VALUE COMPARISON IS THE SHARPER HALF. Matching KEYS with different
CONTENT is the failure the defect actually reported: `value_display` present on
one row and absent from the other showed one clerk `−15%` and the next `15`. So
the shared keys are compared by VALUE too, on a real seeded discount, and
`value_display` and `allowance_unit` are named in their own assertion because
those are the two fields the divergence has already been found in.
"""

from datetime import date

import pytest

from apps.rating import discount_services, selectors
from apps.rating import discounts as discount_models

from tests.test_us_rat_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_rat_helpers import tenant_ctx

pytestmark = pytest.mark.django_db

#: The three fields the READ row carries and the WRITE row deliberately does
#: not: they answer "which version did you read", which is not a question the
#: create response is answering. Pinned so a FOURTH divergence goes red.
READ_ONLY_KEYS = {"version_id", "version_no", "version_status"}

#: `CR-166-BRC10` §9 (the discounts redesign's API contract, 2026-10-03), verbatim:
#: *"Discount read (list rows and `GET /discounts/{id}`) adds: `version` (int),
#: `status` …, `program_owner`, `exclusivity_group`, `eligibility` …, `value_display`
#: …, `effective_from`, `effective_to`, `offered_to` (units on its plans),
#: `receiving` (accounts), `granted_this_month` …, `scheduled_next`"*, plus
#: `stored_status` from its *Fields added* table. The contract gives them to the
#: READ, and the write row's one consumer (the New discount form) reads only `id`
#: and `name` from it, then re-reads the list. Pinned as a second NAMED set so a
#: field added to one copy outside that contract still goes red (`DEF-RAT-9345`;
#: before it, this guard named these nine as drift).
CR166_READ_ONLY_KEYS = {
    "version",
    "program_owner",
    "exclusivity_group",
    "effective_to",
    "offered_to",
    "receiving",
    "granted_this_month",
    "scheduled_next",
    "stored_status",
}


def _a_seeded_discount(env):
    """One real discount with one real version, written through the real door."""
    row = discount_services.create_discount(
        env.admin,
        {
            "code": "DEF2803",
            "name": "Row parity discount",
            "discount_type": "percentage",
            "value": "15",
            "applies_to": "whole_bill",
            "effective_from": date(2026, 8, 1),
        },
    )
    return discount_models.Discount.objects.get(tenant=env.tenant, pk=row["id"])


def test_def2803__the_write_rows_keys_are_a_subset_of_the_read_rows(env):
    """The two DIS-01 rows agree on their key set, up to a NAMED difference.

    RED PROOF (law 7): delete `"value_display"` from
    `discount_services.discount_row`'s returned dict — which is the state the
    defect was filed against — and this reports

        the two DIS-01 row shapes have drifted. Only on the READ row:
        value_display, version_id, version_no, version_status

    naming the field, which is what a fixing lane needs and what neither suite
    could give it.
    """
    with tenant_ctx(env.tenant):
        discount = _a_seeded_discount(env)
        written = discount_services.discount_row(discount)
        served = selectors.discount_row(discount)

    only_read = set(served) - set(written)
    only_written = set(written) - set(served)
    assert not only_written, (
        "the WRITE row carries fields the landing never serves, so the wizard shows "
        "something the list cannot: " + ", ".join(sorted(only_written))
    )
    allowed = READ_ONLY_KEYS | CR166_READ_ONLY_KEYS
    assert only_read == allowed, (
        "the two DIS-01 row shapes have drifted. Only on the READ row, unexpectedly: "
        + ", ".join(sorted(only_read - allowed))
        + "; expected on the READ row and missing: "
        + ", ".join(sorted(allowed - only_read))
        + ". Only the three version keys and CR-166-BRC10 section 9's read-only keys may differ; anything else "
        "is DEF-2803 happening again — a field added to one copy and not the other, "
        "invisible from either side because each suite exercises its own path"
    )


def test_def2803__the_shared_fields_carry_the_SAME_VALUES_on_both_rows(env):
    """Matching keys with different content is the failure that was reported.

    Before BR-RAT-960's lane the write row served a raw value string and no
    `value_display`, so one screen showed the formatted figure and the next
    showed the bare number — BR-RAT-087 exists precisely because a client may
    not format a money value, and two servers formatting it differently is the
    same defect with an extra step.
    """
    with tenant_ctx(env.tenant):
        discount = _a_seeded_discount(env)
        written = discount_services.discount_row(discount)
        served = selectors.discount_row(discount)

    differing = {
        key: (written[key], served[key])
        for key in set(written) & set(served)
        if str(written[key]) != str(served[key])
    }
    assert not differing, (
        "the two DIS-01 rows disagree about a field they both serve: "
        + "; ".join(f"{key}: write={one!r} read={two!r}" for key, (one, two) in differing.items())
    )


def test_def2803__both_rows_state_the_display_string_and_the_allowance_unit(env):
    """The two fields the drift has already been found in, named outright.

    A test that only compared key SETS would pass on two rows that both carried
    `value_display: None`. These assert the fields are actually answered, so the
    parity above is parity on something real.
    """
    with tenant_ctx(env.tenant):
        discount = _a_seeded_discount(env)
        written = discount_services.discount_row(discount)
        served = selectors.discount_row(discount)

    # A 15% discount states its own display string on both paths (BR-RAT-087).
    assert written["value_display"] == served["value_display"]
    assert written["value_display"], "no display string was served at all"
    assert "15" in str(written["value_display"])
    # BR-RAT-960 — a percentage discount resolves NO allowance unit, and both
    # rows must say so the same way rather than one omitting the key.
    assert "allowance_unit" in written and "allowance_unit" in served
    assert written["allowance_unit"] == served["allowance_unit"] is None


# ── Lifecycle ─────────────────────────────────────────────
# packet: DEF-2803 (12-governance/10-defect-log.csv) + CLAUDE.md hard-won laws 5 and 7
# generated: 2026-09-01 by the 2026-08-31 defect-sweep lane
# checklist: A✔ B=n/a(no frontend half — this compares two server row shapes) C✔ D=n/a E=n/a F✔ G✔ H=deferred(PO 2026-08-09)
# gates: ruff check .✔ · golden-verify 33 PASS/0 FAIL and G61 PASS before and after — no arithmetic is touched
# exceptions: this is the INTERIM guard DEF-2803 names, not its durable fix. One function serving both paths is a contract change across apps/rating/api.py and the DIS-02 wizard response type, and that needs its own change request.
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
