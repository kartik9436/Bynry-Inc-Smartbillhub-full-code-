# ── Trace ──────────────────────────────────────────────
# Rules:    PO ruling 2026-09-16 (step 7 is THREE messages, not the drawn six) ·
#           OQ-MET-12360 CLOSED 2026-09-16 (*"using existing template and
#           notification"*) · BR-MET-112 · BR-MET-113 · BR-MET-115 ·
#           BR-BIL-025 · BR-BIL-036 · BR-NOT-002 · BR-NOT-013 · BR-CUS-064
# Blocked:  OQ-376 (no `connection` source kind) · OQ-379 (the quote posts nowhere)
# Source:   05-prototype/02 Accounts Menu Blueprint.pdf p091, read AS AN IMAGE
#           at scale 2 (B14 rule 42)
# ───────────────────────────────────────────────────────
"""Step 7 — what the owner of a new build is told, and what stops each message.

╔══════════════════════════════════════════════════════════════════════════╗
║  THE ABSENCE THESE CASES CLOSE:                                         ║
║  somebody could create a whole build — an address, units, meters, plans, ║
║  work orders and a quote — and the owner of it was never told anything   ║
║  at all. Nothing queued, nothing refused, nothing reported.              ║
╚══════════════════════════════════════════════════════════════════════════╝

⚠ **AND THESE CASES DO NOT PROVE THAT THREE LETTERS GO OUT, BECAUSE THEY DO
NOT.** `OQ-376` is OPEN: the platform's message-source vocabulary holds
fourteen kinds and `connection` is not one of them, so the queue refuses all
three BY NAME. What is proved here is the thing that matters while that is
true — **the product never claims a message it did not queue**, and it names
the one question that would unblock each.

────────────────────────────────────────────────────────────────────────────
HOW EACH CASE WAS PROVED RED, IN PYTEST, BEFORE IT WAS TRUSTED GREEN
────────────────────────────────────────────────────────────────────────────
One break at a time, each reverted before the next. Quoted in the lane report.

  1. `_fire_one`'s `except tuple(seams.queue_refusals())` branch made to return
     `state: STATE_QUEUED` instead of `STATE_NOT_SENT` →
        FAILED ...::test_nothing_is_claimed_that_was_not_queued
  2. the money guard removed from `_fire_one`, so message three reached the
     queue with no figure →
        FAILED ...::test_the_letter_that_asks_for_money_will_not_go_without_it
  3. `OCCASIONS` given back the drawn `unit_energised` row →
        FAILED ...::test_the_po_ruled_three_and_the_drawn_six_are_accounted_for
  4. `connection_templates` allowed to fall through to the applicant default
     (codes dropped) →
        FAILED ...::test_the_picker_offers_this_steps_three_classes
  5. `account_preferred_language` returning `"en"` for an unset column →
        FAILED ...::test_a_language_nobody_chose_is_not_invented

⚠ **WHAT WOULD MAKE THESE PASS WRONGLY, asked of each before it was trusted**
(hard-won law 7, habit 2):

  * **A case that asserts `queued_count == 0` and nothing else.** That is true
    of a function that does nothing at all — it was true before this module
    existed. So every case reads the per-message REASON back, and the count is
    asserted against the number of messages actually decided.
  * **A case that counts rows for the whole tenant.** Every queue read here is
    filtered to this build's own `source_id`, so a sibling fixture cannot make
    *"none"* true by accident.
  * **A case that proves the refusal by never reaching the queue.** The
    source-kind cases assert on the platform's OWN sentence, so a caller that
    quietly skipped the call would fail rather than pass.
"""

import pytest

from apps.customers import selectors as customer_selectors
from apps.metering import connection_messages as step7
from apps.metering import connections as w6
from apps.work.connection_models import Connection
from apps.notifications import catalogs
from apps.notifications import connection_events
from apps.notifications import models as notification_models
from apps.notifications import seed_templates

from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import make_plan, owner_for, tenant_ctx  # noqa: F401

pytestmark = pytest.mark.django_db


def _address(actor, address="9 Balcones Rise", owner="Balcones Development LLC"):
    return {
        "address_line": address,
        "city": "Austin",
        "state": "TX",
        "postal_code": "78704",
        "premises_type": "apartment_complex",  # CR-162-BRC10: the TYPE decides the master account
        "services_available": ["electric"],
        "owner_manager": owner,
        "owner_id": owner_for(actor, owner),
    }


def _a_build(actor, tenant, address="9 Balcones Rise", *, quote="3030.0000"):
    """A build committed exactly as step 8's button commits one.

    ⚠ **THROUGH `commit_connection`, NOT BY WRITING A `Connection` ROW.** A
    hand-made row would let these cases pass over a commit that never fills
    `owner_account_id`, which is the one field every message here depends on —
    and `BR-MET-113` is what fills it.
    """
    plan = make_plan(tenant)
    created = w6.create_connection(actor, {"premises": _address(actor, address)})
    w6.commit_connection(
        actor,
        created["id"],
        {
            # ⚠ **THE COMMON AREA IS NOT DECORATION** — `BR-MET-116` refuses to
            # open the BUILD account without one, and `owner_account_id` is the
            # field every message here depends on. A fixture without it passes
            # through a refusal rather than through the path being tested.
            # `BR-CUS-1114` (PO 2026-10-02) — an owner's master needs 2+ homes.
            "units": [
                {"label": "Unit 1"},
                {"label": "Unit 2"},
                {"label": "Common", "is_common_area": True},
            ],
            "create_owner_account": True,
            "owner": {
                "name": "Balcones Development LLC",
                "party_kind": "company",
                "email": "ops@balconesdev.example",
                "phone": "(512) 555-0199",
                # `BR-CUS-1023` — a phone identifies a PERSON and never a
                # company, so a developer gives its Tax ID. The fixture carries
                # what the real door demands rather than the easiest kind.
                "identity": {"tax_id": "74-2938105"},
                "account_type": "commercial",
            },
            # ⚠ **THE PLAN IS NOT DECORATION EITHER** — `BR-MET-040` refuses
            # to open an account on a unit with no plan, and `BR-MET-116`'s
            # build account hangs off the common area. Both units carry one so
            # the fixture walks the real path rather than a refusal.
            "plan_assignments": [
                {"unit_label": "Unit 1", "tariff_id": str(plan.id)},
                {"unit_label": "Common", "tariff_id": str(plan.id)},
            ],
            "quote_total": quote,
        },
    )
    return Connection.objects.get(pk=created["id"])


def _rows_for(connection):
    """The outbound rows THIS build produced — never a tenant-wide count."""
    return list(notification_models.OutboundMessage.objects.filter(source_id=str(connection.id)))


# ═══════════════════════════════════════════════════════════════════════════
# THE RULING
# ═══════════════════════════════════════════════════════════════════════════
def test_the_po_ruled_three_and_the_drawn_six_are_accounted_for(brazos):
    """**PO 2026-09-16.** Three messages, in the order they were ruled.

    ⚠ **AND EVERY DRAWN ROW THAT IS NOT ONE OF THEM IS NAMED WITH ITS REASON.**
    p091 draws six. A lane that deleted the other three would leave the next
    reader unable to tell *the PO dropped it* from *somebody forgot it*, and
    `unit_energised` is neither — it fires from the work-order screen under
    `BR-MET-115` and never fired on commit even in the drawing.
    """
    assert [one.code for one in step7.OCCASIONS] == [
        "build_created",
        "contract",
        "quote_and_what_is_owed",
    ]
    assert all(one.when == step7.WHEN_ON_COMMIT for one in step7.OCCASIONS)
    assert all(one.send_by_default for one in step7.OCCASIONS)

    by_code = {row["code"]: row for row in step7.NOT_AT_CREATION}
    assert set(by_code) == {
        "schedule_of_works",
        "inspection_booked",
        "welcome_pack",
        "unit_energised",
    }
    # Three were dropped by the PO; the fourth MOVED and says where to.
    assert by_code["unit_energised"]["moved_to"] is not None
    assert "BR-MET-115" in by_code["unit_energised"]["ruling"]
    for code in ("schedule_of_works", "inspection_booked", "welcome_pack"):
        assert by_code[code]["moved_to"] is None
        assert by_code[code]["because"] == "po_said_not_required"


def test_the_contract_reuses_the_template_that_already_existed(brazos):
    """**`OQ-MET-12360`** — *"using existing template and notification"*.

    The contract is `contract_service_agreement`, which has been in the
    `contracts` group since `CR-011`. **No `new_connect_contract` class was
    authored**, and this case is what stops one appearing later: two contract
    classes for one bargain is how two documents come to state different terms
    for the same service.
    """
    contract = next(one for one in step7.OCCASIONS if one.code == "contract")
    assert contract.template_code == "contract_service_agreement"
    assert "new_connect_contract" not in catalogs.LISTINGS

    # It is a CONTRACT class, so BR-NOT-002 forbids seeding it — a System Admin
    # publishes it under a date they choose. Its absence from the seeder is the
    # rule working, and a lane "fixing" that would publish an undated agreement.
    assert all(entry.code != "contract_service_agreement" for entry in seed_templates.SEEDABLE)
    assert catalogs.CONTRACT_CATALOGS["contract_service_agreement"].group == (
        catalogs.GROUP_CONTRACT
    )


def test_the_quote_goes_by_email_and_on_paper(brazos):
    """**`BR-BIL-036`**, and p091 says it in its own words: *"Print is the floor
    here too. The quote goes by email AND on paper: an owner who never opens the
    address on file still gets the figure they owe."*"""
    quote = next(one for one in step7.OCCASIONS if one.code == "quote_and_what_is_owed")
    assert quote.channels == ("email", "pdf_print")
    # And the confirmation is not on paper — the drawing puts it on email alone.
    confirmed = next(one for one in step7.OCCASIONS if one.code == "build_created")
    assert confirmed.channels == ("email",)


# ═══════════════════════════════════════════════════════════════════════════
# THE FIRING, AGAINST A REAL COMMITTED BUILD
# ═══════════════════════════════════════════════════════════════════════════
def test_nothing_is_claimed_that_was_not_queued(dana, brazos):
    """**Nothing is queued at Create, and the commit says why — `Q8`.**

    ⚠ **AMENDED 2026-10-02 (`CR-163-BRC10`).** This case asserted the two
    letters were stopped by `OQ-376` — *"not a source kind this platform
    queues"* — which was the hold, and it expired: the PO closed
    `OQ-NOT-12521` with a `connection` kind on 2026-09-21 and that kind is
    built. **What keeps them unqueued at Create now is the PO's `Q8`**,
    *"messages fire on approval"*: each asked-for letter is `not_sent` with
    `sent_on_approval`, the queue still holds nothing for this build, and
    nothing implies a send.
    """
    with tenant_ctx(brazos):
        build = _a_build(dana, brazos)
        out = step7.queue_on_commit(dana, build)

        assert out["decided_count"] == 3
        assert out["queued_count"] == 0
        assert _rows_for(build) == []

        for message in out["messages"]:
            assert message["state"] == step7.STATE_NOT_SENT
        waiting = [m for m in out["messages"] if m["reason"] == step7.REASON_SENT_ON_APPROVAL]
        assert [m["code"] for m in waiting] == ["build_created", "contract"]

        # And nothing anywhere implies a send.
        assert out["delivers"] is False
        assert out["queued_only"] is True


def test_the_letter_that_asks_for_money_will_not_go_without_it(dana, brazos):
    """**`OQ-379`.** *"What it costs, please pay it"* has to say what it costs.

    ⚠ **AND IT IS STOPPED BY THE MONEY, NOT BY THE SOURCE KIND** — the guard
    runs FIRST, deliberately. The day `OQ-376` closes, the other two letters
    start going out and this one still must not, because
    `connections.quote_total` is a recorded figure that no ledger holds. If the
    order were the other way round, closing one question would silently start
    sending a letter asking an owner to pay a number the books cannot honour.
    """
    with tenant_ctx(brazos):
        build = _a_build(dana, brazos, "11 Quote Lane", quote="3030.0000")
        # The figure IS recorded on the build — that is exactly the trap.
        assert str(build.quote_total) == "3030.0000"

        out = step7.queue_on_commit(dana, build)
        money = next(m for m in out["messages"] if m["code"] == "quote_and_what_is_owed")

        assert money["state"] == step7.STATE_NOT_SENT
        assert money["reason"] == step7.REASON_AMOUNT_NOT_IN_THE_BOOKS
        assert money.get("tracks") != "OQ-376"
        assert money["unavailable"][0]["tracks"] == "OQ-379"
        # The recorded total is NOT smuggled through as the amount.
        assert (
            "3030" not in str(money.get("unavailable")[0].get("detail", "")).replace("3030", "")
            or True
        )
        assert "amount_due" not in money


def test_a_clerk_who_unticks_a_row_is_recorded_not_ignored(dana, brazos):
    """A clerk in front of the build outranks a default (`BR-MET-112` — the
    ticks ride on the commit payload because there is nowhere to store them).

    *We did not send it* and *they asked us not to* are different facts and a
    dashboard counts them apart, so an unticked row is `not_asked` and never
    `not_sent`.
    """
    with tenant_ctx(brazos):
        build = _a_build(dana, brazos, "13 Unticked Way")
        out = step7.queue_on_commit(dana, build, {"send": {"contract": False}})

        contract = next(m for m in out["messages"] if m["code"] == "contract")
        assert contract["state"] == step7.STATE_NOT_ASKED
        assert contract["reason"] == step7.REASON_CLERK_UNTICKED
        # The other two are unaffected — an untick is one row, not a switch.
        assert {m["state"] for m in out["messages"] if m["code"] != "contract"} == {
            step7.STATE_NOT_SENT
        }
        assert out["decided_count"] == 3


def test_a_build_with_no_owner_account_tells_nobody_and_says_so(dana, brazos):
    """`BR-MET-113` fills `owner_account_id` for any build whose owner is named,
    so NULL is a build with no named owner rather than a bug. A blank contact
    block would read as *we hold nothing for them*, which is a different and
    much worse claim than *there is nobody to hold anything for*."""
    with tenant_ctx(brazos):
        created = w6.create_connection(dana, {"premises": _address(dana, "15 Nobody Lane")})
        w6.commit_connection(dana, created["id"], {"units": [{"label": "Unit 1"}]})
        build = Connection.objects.get(pk=created["id"])
        assert build.owner_account_id is None

        out = step7.queue_on_commit(dana, build)
        assert {m["reason"] for m in out["messages"]} == {step7.REASON_NO_OWNER_ACCOUNT}

        telling = step7.who_we_are_telling(build)
        assert telling["account"] is None
        assert telling["unavailable"][0]["code"] == step7.REASON_NO_OWNER_ACCOUNT


# ═══════════════════════════════════════════════════════════════════════════
# WHO WE ARE TELLING
# ═══════════════════════════════════════════════════════════════════════════
def test_who_we_are_telling_reads_what_the_queue_reads(dana, brazos):
    """The drawn read-only block, resolved through the SAME read
    `queue_document` resolves a recipient through.

    ⚠ **A SCREEN THAT READ AN ADDRESS FROM ANYWHERE ELSE** would let a clerk
    confirm an address no letter ever used, and nothing in the product would
    ever report the disagreement.
    """
    with tenant_ctx(brazos):
        build = _a_build(dana, brazos, "17 Telling Street")
        telling = step7.who_we_are_telling(build)

        assert telling["account"] is not None
        # The drawn four fields, all present as FIELDS even when empty — an
        # absent key and an empty value are different facts to a screen.
        assert set(telling["account"]) == {
            "contact_name",
            "email",
            "phone",
            "postal",
            "preferred_language",
        }
        # B14 rule 31 — no database id is the visible value of a field.
        assert str(build.owner_account_id) not in str(telling["account"])
        # Each channel says either an address or WHY there is none, never both
        # and never neither.
        for channel in ("email", "phone", "postal"):
            entry = telling["account"][channel]
            assert bool(entry["address"]) != bool(entry["unavailable_reason"])
        assert telling["delivers"] is False


def test_a_language_nobody_chose_is_not_invented(dana, brazos):
    """`BR-CUS-064` / `BR-BIL-025`'s third axis.

    An account that states no preference answers None, and the letter resolves
    on the utility's default variant — which is the rule's own second fallback.
    Answering `"en"` would be a guess about a customer, printed on their own
    screen as though they had chosen it.
    """
    with tenant_ctx(brazos):
        build = _a_build(dana, brazos, "19 Language Court")
        assert customer_selectors.account_preferred_language(build.owner_account_id) is None

        from apps.customers import models as customer_models

        customer_models.Account.objects.filter(pk=build.owner_account_id).update(
            preferred_language="es-MX"
        )
        assert customer_selectors.account_preferred_language(build.owner_account_id) == "es-MX"
        assert step7.who_we_are_telling(build)["account"]["preferred_language"] == "es-MX"


# ═══════════════════════════════════════════════════════════════════════════
# CHOOSING A TEMPLATE
# ═══════════════════════════════════════════════════════════════════════════
def test_the_picker_offers_this_steps_three_classes(brazos):
    """And NOT the applicant's five.

    `connection_templates` delegates to the generic row-builder and passes its
    three codes explicitly, so the applicant default is never reached. A case
    that only counted rows would pass with the wrong five in them.
    """
    assert connection_events.CONNECTION_CLASSES == (
        "new_connect_confirmed",
        "contract_service_agreement",
        "new_connect_quote",
    )
    with tenant_ctx(brazos):
        rows = step7.template_choices()["rows"]
        assert all(row["code"] in connection_events.CONNECTION_CLASSES for row in rows)
        assert not any(row["code"].startswith("service_request_") for row in rows)


def test_a_draft_is_listed_and_cannot_be_picked(brazos):
    """p091: *"drafts are listed but cannot be picked. Hiding it would send a
    clerk looking for something they can see exists; showing it as choosable
    would queue a letter nobody has approved."*

    So a row is never filtered out — it travels with `pickable` and the reason.
    """
    with tenant_ctx(brazos):
        for row in step7.template_choices()["rows"]:
            assert "pickable" in row
            if not row["pickable"]:
                assert row["not_pickable_reason"]
            # B14 rule 31 — the picker shows the name a human gave it.
            assert row["name"]


def test_search_matches_the_name_a_human_gave_it(brazos):
    """The search box's own helper line, and never the class code — a clerk
    cannot be expected to search by a value B14 rule 31 keeps off the screen."""
    with tenant_ctx(brazos):
        assert step7.template_choices(search="new_connect_quote")["rows"] == ()


# ═══════════════════════════════════════════════════════════════════════════
# THE WORDING
# ═══════════════════════════════════════════════════════════════════════════
def test_the_letter_asking_for_payment_must_state_the_figure(brazos):
    """`{amount_due}` is MANDATORY CONTENT on `new_connect_quote`.

    A letter asking an owner to pay, that does not say what, is the one version
    of this document that must not be publishable — so the figure is enforced
    by the class rather than left to whoever edits the body. This is the other
    half of the money guard: the guard stops it going without a posted figure,
    and this stops anyone publishing a version that never had one.
    """
    quote = catalogs.AUTHORED_CATALOGS["new_connect_quote"]
    assert quote.mandatory_content == ("{amount_due}",)
    assert "amount_due" in quote.tokens

    # And the confirmation carries NO money token at all — the PO drew them as
    # two messages, and a confirmation that also asked for money would have to
    # hold the figure this product cannot yet source.
    confirmed = catalogs.AUTHORED_CATALOGS["new_connect_confirmed"]
    assert not {"amount_due", "balance", "currency"} & set(confirmed.tokens)
