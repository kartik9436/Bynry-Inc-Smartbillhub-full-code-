# ── Trace ──────────────────────────────────────────────
# Story:    US-RBS-034 (EP-RBS-05) — CR-075 wave Q′, runbook 22.
# Rules:    BR-RBS-002 · BR-RBS-004 · BR-RBS-011 · BR-RBS-012 · BR-RBS-020 ·
#           BR-RBS-021 · BR-RBS-023 · BR-RBS-027 · BR-RBS-035 · BR-NOT-005 ·
#           CLAUDE.md hard rule 2 · B14 rules 31 and 32
# Tests:    this file. The PostgreSQL half — the real seams and the savepoint —
#           is tests/test_rbs_sync_runbooks_pg.py.
# Impacts:  apps/runbooks/definitions/undeliverable_contacts.py
# ───────────────────────────────────────────────────────
"""Runbook 22, against the rules rather than against itself.

⚠ **THE SEAMS ARE REPLACED, AND ONE BRANCH CAN BE PROVED NOWHERE ELSE.** No
adapter on this deployment writes `bounced` or `failed` on any channel — the
owning module says so in as many words (`delivery_ops.queue_health`: *"delivery
is out of this release by PO ruling (2026-08-15)"*) — and every account with
print traffic on the seeded tenant has an email and a phone on file. So **a hard
bounce, a failed text, and the *nothing left* outcome cannot be reached with real
data at all**, and this file is the only place they are exercised. That is a
statement about what the fixture proves as much as about what this file does, and
both numbers are quoted in the lane report; neither is quoted alone.
"""

import datetime as dt

import pytest

from apps.runbooks.contract import BLOCK_TYPES
from apps.runbooks.definitions import undeliverable_contacts as uc
from apps.runbooks.engine import executor

pytestmark = pytest.mark.django_db

TODAY = dt.date(2026, 9, 6)


def _item(
    message_id="m1",
    account_id="a1",
    channel="email",
    status="bounced",
    told_by="provider",
    attempts=3,
    at="2026-09-06",
    is_sample=False,
):
    return {
        "message_id": message_id,
        "account_id": account_id,
        "channel": channel,
        "status": status,
        "told_by": told_by,
        "recipient_address": "someone@example.test",
        "attempts": attempts,
        "provider_text": None,
        "source_type": "invoice",
        "template_code": "notice",
        "at": at,
        "is_sample": is_sample,
    }


@pytest.fixture
def seams(monkeypatch):
    """Fixed answers for the five reads runbook 22 makes.

    Everything defaults to *nothing is connected and nothing came back*, which
    is the STOP — so a case that forgets to give the runbook work cannot
    accidentally assert on a happy path.
    """
    state = {
        "connections": [],
        "items": [],
        "channels": {},
        "positions": {},
        "currency": "USD",
        "not_reported": ["delivered", "bounced"],
    }
    monkeypatch.setattr(
        uc.integrations_seam, "live_connections", lambda keys: list(state["connections"])
    )
    monkeypatch.setattr(
        uc.notifications_seam,
        "undeliverable_feedback",
        lambda limit=2000: {
            "items": list(state["items"]),
            "messages_on_file": 353,
            "not_reported": list(state["not_reported"]),
            "channels_with_traffic": ["email", "sms", "pdf_print"],
        },
    )
    # ⚠ **THE LABEL MUST NOT CONTAIN THE ID, AND THE FIRST DRAFT'S DID.** It
    # answered `f"Customer {account_id}"`, so the *no database id on a screen*
    # case failed over the FIXTURE rather than over the runbook — the runbook
    # draws `account_facts`' own label and never the handle. A fixture that
    # cannot tell a compliant renderer from a leaking one is worse than none:
    # here it cried wolf, and the same shape one step over passes wrongly.
    monkeypatch.setattr(
        uc.customers_seam,
        "account_facts",
        lambda account_id: {"account_no": "A-10432", "label": "Nunes, R."},
    )
    monkeypatch.setattr(
        uc.customers_seam,
        "contact_channels_for",
        lambda ids: {
            str(one): state["channels"].get(
                str(one), {"email": "e@x.test", "text": "555", "post": "1 Road", "channels": ["email", "text", "post"]}
            )
            for one in ids
        },
    )
    monkeypatch.setattr(uc.payments_seam, "tenant_currency", lambda: state["currency"])
    monkeypatch.setattr(
        uc.payments_seam,
        "open_bill_position",
        lambda account_id: state["positions"].get(str(account_id), {"total_open": "218.9000"}),
    )
    monkeypatch.setattr(uc.tenancy_seam, "today", lambda: TODAY)
    return state


def _run(params=None):
    definition = uc.RUNBOOK
    ctx = executor.build_context(
        definition, tenant_id="t", run_id=None, params=params or {"window": 7}
    )
    return executor.execute(definition, ctx=ctx)


def _blocks(result):
    return {block["block"]: block["payload"] for block in result.report}


def _checked(result, step):
    return (result.set_results.get(step) or {}).get("checked") or {}


def _plan(result):
    return (result.set_results.get(uc.STEP_FLAG) or {})["plan"]


# ── step 1 · the two doors ────────────────────────────────────────────────


def test_both_doors_shut_stops_the_run_and_names_both_absences(seams):
    stop = (_run().set_results[uc.STEP_GATHER])["stop"]
    assert stop["headline"] == "Nothing has come back."
    assert "No delivery provider is set up" in stop["detail"]
    assert "No returned letters have been marked either" in stop["detail"]


def test_a_stopped_run_draws_no_kpi_strip(seams):
    blocks = _blocks(_run())
    assert "kpis" not in blocks
    assert set(blocks) == {"verdict", "sentence", "chain", "records"}


def test_a_stopped_run_says_stopped_and_never_says_failed(seams):
    result = _run()
    assert _blocks(result)["verdict"]["word"] == "Stopped"
    assert "failed" not in str(result.report).lower()


def test_every_later_step_reads_never_reached(seams):
    cells = _blocks(_run())["chain"]["cells"]
    assert len(cells) == len(uc.STEP_LABELS)
    assert [one["note"] for one in cells[1:]] == ["Never reached"] * (len(cells) - 1)


def test_a_connection_that_reported_nothing_is_a_different_sentence(seams):
    seams["connections"] = [
        {"key": "sendgrid", "display_name": "SendGrid", "enabled": True, "status": "working"}
    ]
    stop = (_run().set_results[uc.STEP_GATHER])["stop"]
    assert stop["headline"] == "Nothing has come back yet."
    assert "SendGrid is connected" in stop["detail"]


def test_not_reported_travels_on_a_run_that_carries_on(seams):
    """Hard-won law 7 — a declared blind spot with no number is an empty one."""
    seams["items"] = [_item()]
    checked = _checked(_run(), uc.STEP_GATHER)
    assert checked["not_reported"] == ["delivered", "bounced"]
    assert checked["told_by_a_provider"] == 1


# ── the window ────────────────────────────────────────────────────────────


def test_feedback_older_than_the_window_is_excluded_and_counted(seams):
    """Without a window this runbook re-suppresses the same channels for ever."""
    seams["items"] = [_item("m1", at="2026-09-06"), _item("m2", at="2026-08-01")]
    checked = _checked(_run({"window": 2}), uc.STEP_GATHER)
    assert checked["feedback_items"] == 1
    assert checked["items_outside_the_window"] == 1
    assert checked["window_starts"] == "2026-09-04"


def test_an_item_with_no_date_is_included_and_counted(seams):
    """A filter with nothing to filter on is a filter that guesses."""
    seams["items"] = [_item("m1", at=None)]
    checked = _checked(_run({"window": 1}), uc.STEP_GATHER)
    assert checked["feedback_items"] == 1
    assert checked["items_with_no_date"] == 1


# ── step 2 · the four kinds ───────────────────────────────────────────────


def test_a_bounced_email_is_a_hard_bounce(seams):
    seams["items"] = [_item(status="bounced")]
    assert _checked(_run(), uc.STEP_CLASSIFY)["by_kind"] == {uc.KIND_HARD_BOUNCE: 1}


def test_an_email_still_inside_its_retries_is_a_soft_bounce(seams):
    """`BR-NOT-005` retry ×3 — the product's own definition of *still trying*."""
    seams["items"] = [_item(status="failed", attempts=1)]
    assert _checked(_run(), uc.STEP_CLASSIFY)["by_kind"] == {uc.KIND_SOFT_BOUNCE: 1}


def test_an_email_that_used_all_its_retries_is_hard(seams):
    seams["items"] = [_item(status="failed", attempts=3)]
    assert _checked(_run(), uc.STEP_CLASSIFY)["by_kind"] == {uc.KIND_HARD_BOUNCE: 1}


def test_a_failed_text_and_a_returned_letter_are_their_own_kinds(seams):
    seams["items"] = [
        _item("m1", channel="sms", status="failed"),
        _item("m2", channel="pdf_print", status="sent", told_by="a person"),
    ]
    assert _checked(_run(), uc.STEP_CLASSIFY)["by_kind"] == {
        uc.KIND_FAILED_TEXT: 1,
        uc.KIND_RETURNED_POST: 1,
    }


def test_a_message_addressed_to_no_account_is_named_never_dropped(seams):
    """A staff report bouncing is real feedback that suppresses no customer channel."""
    seams["items"] = [_item(account_id=None)]
    checked = _checked(_run(), uc.STEP_CLASSIFY)
    assert checked["items_with_no_customer_account"] == 1
    assert checked["feedback_classified"] == 1


def test_an_in_app_message_is_not_a_contact_channel(seams):
    seams["items"] = [_item(channel="in_app")]
    assert _checked(_run(), uc.STEP_CLASSIFY)["by_kind"] == {uc.KIND_NOT_A_CHANNEL: 1}


# ── step 3 · the suppression rule ─────────────────────────────────────────


def test_soft_bounces_suppress_nothing_however_many_there_are(seams):
    """`RB-122`'s own guard, and the one that protects a customer.

    ⚠ **THE FIRST DRAFT OF THIS CASE USED ONE ITEM AND PASSED ON THE WRONG
    BUILD.** With a threshold of two, one soft bounce suppresses nothing whether
    the rule counts it or not — so the case was green over a runbook that had
    stopped honouring the guard entirely. It uses THREE now, which is over the
    threshold, so the only thing keeping it green is the rule itself. That is
    hard-won law 7's second habit: ask what would make this check pass wrongly.
    """
    seams["items"] = [
        _item("m1", status="failed", attempts=1),
        _item("m2", status="failed", attempts=1),
        _item("m3", status="failed", attempts=2),
    ]
    result = _run()
    assert _checked(result, uc.STEP_SUPPRESSION)["channels_to_suppress"] == 0
    assert _checked(result, uc.STEP_SUPPRESSION)["still_retrying"] == 3
    assert _plan(result)[0]["outcome"] == uc.OUTCOME_RETRYING
    assert "One soft bounce suppresses nothing" in _plan(result)[0]["reason"]


def test_a_soft_bounce_does_not_help_a_hard_one_over_the_threshold(seams):
    """One hard and one soft is ONE failure, not two."""
    seams["items"] = [_item("m1", status="bounced"), _item("m2", status="failed", attempts=1)]
    result = _run()
    assert _checked(result, uc.STEP_SUPPRESSION)["channels_to_suppress"] == 0
    hard = next(one for one in _plan(result) if one["kind"] == uc.KIND_HARD_BOUNCE)
    assert "1 of 2 failures needed to suppress email" in hard["reason"]


def test_one_hard_bounce_is_below_the_threshold_and_says_so(seams):
    seams["items"] = [_item()]
    row = _plan(_run())[0]
    assert row["outcome"] == uc.OUTCOME_NEEDS_A_PERSON
    assert "1 of 2 failures needed to suppress email" in row["reason"]


def test_two_hard_bounces_suppress_the_email(seams):
    seams["items"] = [_item("m1"), _item("m2")]
    result = _run()
    assert _checked(result, uc.STEP_SUPPRESSION)["channels_to_suppress"] == 1
    assert all(one["outcome"] == uc.OUTCOME_PLANNED for one in _plan(result))


def test_one_returned_letter_suppresses_the_post(seams):
    """An envelope came back — a fact somebody held in their hand."""
    seams["items"] = [_item(channel="pdf_print", status="sent", told_by="a person")]
    result = _run()
    assert _checked(result, uc.STEP_SUPPRESSION)["channels_to_suppress"] == 1
    assert _plan(result)[0]["outcome"] == uc.OUTCOME_PLANNED


# ── step 4 · the fall-back ────────────────────────────────────────────────


def test_a_suppressed_channel_names_where_it_falls_back_to(seams):
    """`US-RBS-034`'s acceptance sentence, asserted as a sentence."""
    seams["items"] = [_item(channel="pdf_print", status="sent", told_by="a person")]
    row = _plan(_run())[0]
    assert row["falls_back_to"] == uc.CHANNEL_EMAIL
    assert "Falls back to email." in row["reason"]


def test_a_channel_suppressed_in_this_same_run_is_not_a_fall_back(seams):
    """Otherwise the plan hands an account back to the address that just failed."""
    seams["channels"] = {"a1": {"email": "e@x.test", "text": None, "post": "1 Road", "channels": ["email", "post"]}}
    seams["items"] = [
        _item("m1", channel="email"),
        _item("m2", channel="email"),
        _item("m3", channel="pdf_print", status="sent", told_by="a person"),
    ]
    rows = {one["item_id"]: one for one in _plan(_run())}
    assert rows["m3"]["falls_back_to"] is None
    assert rows["m3"]["outcome"] == uc.OUTCOME_NOTHING_LEFT


def test_nothing_left_when_no_channel_remains(seams):
    """⚠ UNREACHABLE ON REAL DATA — see this module's docstring."""
    seams["channels"] = {"a1": {"email": "e@x.test", "text": None, "post": None, "channels": ["email"]}}
    seams["items"] = [_item("m1"), _item("m2")]
    result = _run()
    assert _checked(result, uc.STEP_FALLBACK)["nothing_left"] == 2
    assert _checked(result, uc.STEP_FLAG)["accounts_with_nothing_left"] == 1
    row = _plan(result)[0]
    assert row["fix_label"] == "Add a contact →"
    assert "Nothing is left on file" in row["reason"]


def test_an_account_with_no_channel_at_all_is_counted(seams):
    """Also answers `13-selector-inventory.md` S-10 for `RB-119` step 5."""
    seams["channels"] = {"a1": {"email": None, "text": None, "post": None, "channels": []}}
    seams["items"] = [_item("m1"), _item("m2")]
    assert _checked(_run(), uc.STEP_FALLBACK)["accounts_with_no_channel_at_all"] == 1


# ── steps 5 and 6 · the two ports ─────────────────────────────────────────


def test_suppress_channel_is_called_and_its_own_refusal_is_the_outcome(seams):
    """`BR-RBS-003` — dry and live are ONE path; there is no `if is_bound` branch."""
    seams["items"] = [_item("m1"), _item("m2")]
    record = _run().records[0]
    assert record.outcome == uc.OUTCOME_PLANNED
    assert "has no writer bound" in record.decided_by_rule


def test_flag_account_is_called_and_its_refusal_is_recorded(seams):
    seams["channels"] = {"a1": {"email": "e@x.test", "text": None, "post": None, "channels": ["email"]}}
    seams["items"] = [_item("m1"), _item("m2")]
    checked = _checked(_run(), uc.STEP_FLAG)
    assert checked["accounts_flagged"] == 0
    assert "has no writer bound" in checked["flag_state"]


def test_flag_state_does_not_read_flagged_over_an_empty_list(seams):
    """A loop that never ran must not leave an optimistic word behind."""
    seams["items"] = [_item("m1"), _item("m2")]
    assert _checked(_run(), uc.STEP_FLAG)["flag_state"] == "nothing to flag"


def test_a_balance_that_will_not_read_is_named_not_skipped(seams):
    seams["channels"] = {"a1": {"email": "e@x.test", "text": None, "post": None, "channels": ["email"]}}
    seams["positions"] = {"a1": None}
    seams["items"] = [_item("m1"), _item("m2")]
    checked = _checked(_run(), uc.STEP_FLAG)
    assert checked["balances_that_would_not_read"] == 1
    assert checked["balances_read"] == 0


# ── the guard ─────────────────────────────────────────────────────────────


def test_a_sample_item_is_guarded_counted_and_seen_by_no_step(seams):
    seams["items"] = [_item("m1"), _item("m2", is_sample=True)]
    result = _run()
    assert len(result.subjects) == 2
    assert [one.subject_id for one in result.guarded] == ["m2"]
    assert result.counts[executor.OUTCOME_SKIPPED] == 1
    assert _checked(result, uc.STEP_CLASSIFY)["feedback_classified"] == 1


# ── the report ────────────────────────────────────────────────────────────


def test_every_block_name_is_one_of_the_twelve(seams):
    seams["items"] = [_item("m1"), _item("m2")]
    for report in (_run().report, _run({"window": 0}).report):
        assert {block["block"] for block in report} <= set(BLOCK_TYPES)


def test_owed_is_stored_to_four_and_carries_its_currency(seams):
    """CLAUDE.md hard rule 2 — the cell carries four; the renderer shows two.

    ⚠ Wave `P` shipped `182.400000` into a clerk's sentence. A money CELL is the
    fix: the amount and its `CHAR(3)` code travel, and the rounding and the
    symbol are the renderer's one job.
    """
    seams["channels"] = {"a1": {"email": "e@x.test", "text": None, "post": None, "channels": ["email"]}}
    seams["items"] = [_item("m1"), _item("m2")]
    rows = _blocks(_run())["records"]["rows"]
    assert rows[0]["cells"]["owed"] == {"kind": "money", "amount": "218.9000", "currency": "USD"}


def test_now_reads_an_em_dash_on_every_nothing_left_row(seams):
    """`RB-122`'s own note. A blank cell reads as *not looked at*."""
    seams["channels"] = {"a1": {"email": "e@x.test", "text": None, "post": None, "channels": ["email"]}}
    seams["items"] = [_item("m1"), _item("m2")]
    for row in _blocks(_run())["records"]["rows"]:
        assert row["cells"]["now"]["text"] == "—"


def test_the_by_channel_table_says_where_each_one_went(seams):
    seams["items"] = [_item("m1", channel="pdf_print", status="sent", told_by="a person")]
    rows = _blocks(_run())["breakdown"]["rows"]
    post = next(one for one in rows if one["cells"]["channel"]["text"] == "Post")
    assert post["cells"]["to"]["text"] == "Email 1"


def test_the_soft_tile_is_its_own_number(seams):
    """*Nine soft* must never hide inside *thirty-one suppressed*."""
    seams["items"] = [_item("m1", status="failed", attempts=1), _item("m2"), _item("m3")]
    tiles = {one["id"]: one["value"]["text"] for one in _blocks(_run())["kpis"]["tiles"]}
    assert tiles["retrying"] == "1"
    assert tiles["suppressed"] == "2"


def test_no_rule_id_reaches_a_drawn_cell(seams):
    seams["channels"] = {"a1": {"email": "e@x.test", "text": None, "post": None, "channels": ["email"]}}
    seams["items"] = [_item("m1"), _item("m2")]
    for block in _run().report:
        for row in block["payload"].get("rows", []):
            drawn = " ".join(
                str(cell.get("text") or cell.get("label") or "") for cell in row["cells"].values()
            )
            assert "BR-RBS" not in drawn
            assert "BR-NOT" not in drawn


def test_no_database_id_is_the_visible_value_of_a_field(seams):
    seams["channels"] = {"01a0-uuid": {"email": "e@x.test", "text": None, "post": None, "channels": ["email"]}}
    seams["items"] = [_item("m1", account_id="01a0-uuid"), _item("m2", account_id="01a0-uuid")]
    for block in _run().report:
        for row in block["payload"].get("rows", []):
            for cell in row["cells"].values():
                assert "01a0-uuid" not in str(cell)
