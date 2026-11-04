# ── Trace ──────────────────────────────────────────────
# Change:   CR-029 (PO 2026-08-23) — Routes & Cycles. Wave RC-W5 task W5-T5:
#           the five backend refusals that borrowed another surface's message
#           key are re-pointed at the sentences RC-W3c wrote.
# Design:   04-docs/02-decisions/17-cr029-routes-cycles-design.md (B17) §7 W5-T5
# Rules:    CLAUDE.md hard-won law 1 (a comment claiming a guarantee is not the
#           guarantee — a REPORTED stopgap is a promise until a test holds it) ·
#           G15 (eleven catalogues) · G18 (a catalogue key with no call site is
#           dead) · G32 (every refusal carries a key)
# ───────────────────────────────────────────────────────
"""W5-T5 — the borrowed keys go back, and the right sentences get their callers.

**WHY THESE WERE BORROWED, AND WHY THAT ENDED.** Three lanes needed a refusal
sentence before the locale catalogues were theirs to edit: a zero-baseline gate
(G32) blocks an unkeyed refusal, and minting a key obliges eleven translations
under G15. Each lane reused a neighbouring key, said so in its own docstring,
and REPORTED the proper key for minting. RC-W3c minted all six, in all eleven
catalogues — so until this file existed, **G18 counted exactly five dead keys
that were not dead by intent**, they were dead because nobody had moved the
call site.

**WHAT EACH REFUSAL NOW SAYS, IN ENGLISH** — this is the whole test, and the
strings below are the eleven-catalogue `en` values, quoted so a reader can see
what a clerk reads:

| Site | Key | The sentence |
|---|---|---|
| `POST /billing/runs` bad `due_days` | `billing.run.due_days_invalid` | *"Enter a whole number of days, zero or more."* |
| closing a read window with an unknown result | `metering.readWindow.result_unknown` | *"Pick one of: {{allowed}}."* |
| a premises twice in the walking order | `metering.route.walk_order_duplicate_premises` | *"A premises appears twice in the walking order. Each stop appears once."* |
| two stops on one number | `…_duplicate_position` | *"Two stops claim the same position. Give each stop its own number."* |
| a stop that is not on the route | `…_not_a_member` | *"Some of those stops are not on this route. Only its own premises can be ordered."* |
| an order that leaves a stop out | `…_incomplete` | *"The walking order leaves out some of this route's premises. Every stop has to be in it."* |

**THE THREE SHAPE REFUSALS KEEP `metering.payload_not_object` AND THAT IS
DELIBERATE** (B17 §7 W5-T5, verbatim: *"the three shape refusals … keep
`metering.payload_not_object`, because 'We couldn't read that change' is the
right sentence for a malformed body"*). A list that is not a list, an entry that
is not an object and a stop with no premises id are all one thing to a user —
the request was unreadable — and they are asserted here so a later lane cannot
quietly promote them into four more keys.
"""

from datetime import date

import pytest

from apps.metering import models, read_windows, walk_order
from core import errors

from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import make_premises, make_unit, tenant_ctx

pytestmark = pytest.mark.django_db

AUG = (date(2026, 8, 1), date(2026, 8, 5))


def _world(actor) -> dict:
    """Two stops on one walk route — the same world W3b's own suite builds."""
    from apps.metering import services

    elm = make_premises(actor, address_line="1408 Elm St")
    cedar = make_premises(actor, address_line="12 Cedar Ct")
    make_unit(actor, elm["id"], label="Unit 1")
    make_unit(actor, cedar["id"], label="Unit A")
    route = services.create_route(
        actor,
        {
            "code": "RT-W5T5",
            "name": "Elm and Cedar walk",
            "route_type": "walk",
            "service_codes": ["water"],
            "premises_ids": [elm["id"], cedar["id"]],
        },
    )
    return {"route": route, "elm": elm["id"], "cedar": cedar["id"]}


def _keys(caught) -> set[str]:
    """Every key the envelope carries — the top-level one AND each field error.

    Both are asserted because the wizard renders the field error under the
    control and the toast renders the top-level one; a re-point that moved only
    one of them would leave a clerk reading two different sentences about one
    refusal.
    """
    error = caught.value
    return {error.message_key} | {fe["message_key"] for fe in (error.field_errors or ())}


# ═══════════════════════════════════════════════════════════════════════════
# (a) BILLING — the run's due-days override
# ═══════════════════════════════════════════════════════════════════════════
@pytest.mark.parametrize("bad", ["not-a-number", -1])
def test_w5_t5_a__a_bad_due_days_override_speaks_in_billings_own_key(brazos, dana, bad):
    """`metering.cycle.due_days_range` was the borrowed sentence; the refusal is
    billing's and now carries `billing.run.due_days_invalid`."""
    from apps.billing import api as billing_api
    from apps.metering import models as metering_models

    from tests.test_us_met_helpers import FakeUser
    from tests.test_us_ten_helpers import api_call

    with tenant_ctx(brazos):
        cycle = metering_models.Cycle.objects.create(
            tenant_id=brazos.id, code=f"W5T5-{str(bad)[:4]}", name="W5-T5", status="active"
        )
    response = api_call(
        billing_api.bill_runs,
        "post",
        user=FakeUser(dana.id),
        role="billing_clerk",
        tenant=brazos,
        data={
            "cycle_id": str(cycle.id),
            "period_start": "2026-06-01",
            "period_end": "2026-06-30",
            "due_days": bad,
        },
    )
    assert response.status_code == 422
    # ⚠ AMENDED 2026-09-30 (bulk bill run plan A1/B1): the door now answers every
    # Scope refusal at once, each with its own key; the due-days one is
    # `billing.runScope.refusal.dueDaysInvalid` (≤6 words, B14 rule 33) and is
    # still billing's own sentence, never metering's.
    assert response.data["message_key"] == "billing.runScope.refused"
    due = [error for error in response.data["field_errors"] if error["field"] == "due_days"]
    assert [error["message_key"] for error in due] == ["billing.runScope.refusal.dueDaysInvalid"]


# ═══════════════════════════════════════════════════════════════════════════
# (b) READ WINDOWS — an unknown result word
# ═══════════════════════════════════════════════════════════════════════════
def test_w5_t5_b__an_unknown_window_result_speaks_in_the_read_windows_key(brazos, dana):
    """Same sentence — *"Pick one of: {{allowed}}."* — under a key that names the
    surface it refuses on, and the `{{allowed}}` parameter is unchanged."""
    from apps.metering import services

    with tenant_ctx(brazos):
        route = services.create_route(
            dana,
            {"code": "RT-W5T5B", "name": "W5-T5", "route_type": "walk", "service_codes": ["water"]},
        )
        with pytest.raises(errors.ValidationError) as caught:
            read_windows.close_read_window(
                dana,
                route_id=route["id"],
                period_start=AUG[0],
                period_end=AUG[1],
                read_on=date(2026, 8, 3),
                collected_count=1,
                expected_count=1,
                result="Partly done",
            )
    assert _keys(caught) == {"metering.readWindow.result_unknown"}
    assert caught.value.params["allowed"] == ", ".join(models.READ_WINDOW_RESULTS)
    assert caught.value.field_errors[0]["params"]["allowed"] == ", ".join(
        models.READ_WINDOW_RESULTS
    )


# ═══════════════════════════════════════════════════════════════════════════
# (c) WALK ORDER — four refusals, four keys
# ═══════════════════════════════════════════════════════════════════════════
def test_w5_t5_c__a_repeated_stop_names_itself(brazos, dana):
    with tenant_ctx(brazos):
        world = _world(dana)
        with pytest.raises(errors.ValidationError) as caught:
            walk_order.save_premises_order(
                dana,
                route_id=world["route"]["id"],
                order=[
                    {"premises_id": world["elm"], "walk_order": 1},
                    {"premises_id": world["elm"], "walk_order": 2},
                    {"premises_id": world["cedar"], "walk_order": 3},
                ],
            )
    assert _keys(caught) == {"metering.route.walk_order_duplicate_premises"}


def test_w5_t5_c__two_stops_on_one_number_name_themselves(brazos, dana):
    with tenant_ctx(brazos):
        world = _world(dana)
        with pytest.raises(errors.ValidationError) as caught:
            walk_order.save_premises_order(
                dana,
                route_id=world["route"]["id"],
                order=[
                    {"premises_id": world["elm"], "walk_order": 1},
                    {"premises_id": world["cedar"], "walk_order": 1},
                ],
            )
    assert _keys(caught) == {"metering.route.walk_order_duplicate_position"}


def test_w5_t5_c__a_stranger_stop_names_itself(brazos, dana):
    with tenant_ctx(brazos):
        world = _world(dana)
        stranger = make_premises(dana, address_line="9 Nowhere Rd")
        with pytest.raises(errors.ValidationError) as caught:
            walk_order.save_premises_order(
                dana,
                route_id=world["route"]["id"],
                order=[
                    {"premises_id": world["elm"], "walk_order": 1},
                    {"premises_id": world["cedar"], "walk_order": 2},
                    {"premises_id": stranger["id"], "walk_order": 3},
                ],
            )
    assert _keys(caught) == {"metering.route.walk_order_not_a_member"}


def test_w5_t5_c__an_order_that_leaves_a_stop_out_names_itself(brazos, dana):
    with tenant_ctx(brazos):
        world = _world(dana)
        with pytest.raises(errors.ValidationError) as caught:
            walk_order.save_premises_order(
                dana,
                route_id=world["route"]["id"],
                order=[{"premises_id": world["elm"], "walk_order": 1}],
            )
    assert _keys(caught) == {"metering.route.walk_order_incomplete"}


# ═══════════════════════════════════════════════════════════════════════════
# THE THREE SHAPE REFUSALS DO **NOT** MOVE
# ═══════════════════════════════════════════════════════════════════════════
@pytest.mark.parametrize(
    "order",
    [
        pytest.param("not-a-list", id="the-body-is-not-a-list"),
        pytest.param([17], id="an-entry-is-neither-an-id-nor-an-object"),
        pytest.param([{"walk_order": 1}], id="a-stop-names-no-premises"),
    ],
)
def test_w5_t5_c__a_malformed_body_keeps_the_shared_shape_key(brazos, dana, order):
    """*"We couldn't read that change"* is the right sentence for a body that
    cannot be parsed, and B17 §7 says so in as many words. Asserted so the four
    new keys do not grow into seven."""
    with tenant_ctx(brazos):
        world = _world(dana)
        with pytest.raises(errors.ValidationError) as caught:
            walk_order.save_premises_order(dana, route_id=world["route"]["id"], order=order)
    assert _keys(caught) == {"metering.payload_not_object"}


# ── Lifecycle ─────────────────────────────────────────────
# packet: B17 §7 RC-W5 T5 + the CR-029 record in 12-governance/11-change-requests.md
# generated: 2026-08-23 by the CR-029 RC-W5 lane
# checklist: A✔ B=n/a(backend refusal keys; the catalogues RC-W3c wrote are the frontend half) C✔ D✔ E✔ F✔ G✔ H=n/a(not a 🔒 path — no money, no RLS policy, no idempotency key)
# gates: G15 parity✔ (all six keys in all 11 catalogues) · G18 dead-key count 39 → 34
# exceptions: none
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
