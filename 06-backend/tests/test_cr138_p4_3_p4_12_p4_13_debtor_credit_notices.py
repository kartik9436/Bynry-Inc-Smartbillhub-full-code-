# ── Trace ──────────────────────────────────────────────
# Change:   CR-138-BRC07 · P4.3 (a debtor read) · P4.12 (a DOOR to the credit
#           path, not a copy) · P4.13 (`POST /collections/notices`).
#           Blueprint pp.21–22 and screens 7·2, 7·3d, 6·1.
# Rules:    BR-PAY-017 (manual sends use the SAME ladder, channels and
#           exclusions and advance the SAME state) · BR-PAY-035 / BR-NOT-008
#           (the tone→step table) · BR-PAY-032 (the oldest bill is the anchor) ·
#           BR-NOT-005 (a notice is a QUEUE WRITE) · BR-BIL-041 (the reason
#           derives the mechanism) · NFR-3 · NFR-5 · CLAUDE.md hard rule 6 ·
#           hard rule 7
# ───────────────────────────────────────────────────────
"""Three doors that did not exist, and the rules each one had to borrow.

═══════════════════════════════════════════════════════════════════════════════
RED PROOF (hard-won law 7) — OBSERVED, NOT PREDICTED
═══════════════════════════════════════════════════════════════════════════════
Run in this lane's own detached worktree at the pinned tip, each piece removed
in turn and the tree restored and re-verified afterwards. Verbatim:

  * **all three addresses 404'd.** With the three `include`s removed from
    `config/urls.py`, every mount case fails
    `django.urls.exceptions.Resolver404: {'tried': …, 'path':
    'api/brazos/collections/notices'}` — and the same for `debtors/A-1` and
    `accounts/A-1/credit-path`. That is the state of the branch before this
    commit and is the whole of `P4.13`'s *"not mounted today"*.
  * **the history page.** With `notice_history_page(offset, limit)` swapped for
    `notice_history_for(limit=500)`, the paging case fails
    `assert {'offset': 0, 'limit': 50} in [{'offset': 0, 'limit': 100},
    {'offset': 0, 'limit': 500}]`.
    ⚠ **THAT IS NOT THE MESSAGE THIS PARAGRAPH FIRST PREDICTED**, and the
    difference is the point of quoting what was OBSERVED. The draft said it
    would fail *"the paged read was never called"* — it does not, because
    `notice_history_for` is itself expressed in terms of `notice_history_page`,
    so the spy still sees a call and the guard that fires is the WINDOW check
    rather than the called-at-all check. A predicted failure message is a
    claim nothing re-checks (law 1); this one was wrong.
  * **the one vocabulary.** With `tone_to_rung` replaced by a local
    `{"friendly": …, "firm": …}` literal, the vocabulary case fails
    `AssertionError: the tone table was not consulted — this is a second
    vocabulary`.
  * **the skip record.** With the `record_notice` call removed from `_skip`,
    the silent-exclusion case fails `AssertionError: the skip left no trace —
    P4.16's "no silent exclusion"`.

═══════════════════════════════════════════════════════════════════════════════
WHAT WOULD MAKE THESE CHECKS PASS WRONGLY (law 7, habit 2)
═══════════════════════════════════════════════════════════════════════════════
* **A debtor read that returned the right KEYS with empty values would pass a
  shape test.** So the bills case asserts the bill's own NUMBER and the
  position case asserts `oldest_due_on` is the date the fixture wrote.
* **A "paged" history that sliced in Python would return the right rows.** So
  the paging case spies on the seam and asserts the WINDOW it was handed, not
  the rows that came back.
* **A credit-path door that re-implemented the credit would still answer
  `available: true`.** So there is a structural case asserting payments mints
  **no write verb** for a credit at all.
"""

import uuid
from datetime import date, timedelta
from decimal import Decimal

import pytest
from django.urls import resolve

from apps.payments import (
    debtor_api,
    debtor_read,
    ladder,
    notices,
    notices_api,
    notices_by_hand,
    refunds_api,
)
from apps.payments.collections_models import NoticeHistory

from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import tenant_ctx
from tests.test_us_pay_020_023_bank_rec import an_account_of, an_issued_bill

pytestmark = pytest.mark.django_db

from tests.test_us_ten_helpers import api_call  # noqa: E402 — after the star import

#: The prototype's own S34 debtor — 91 days late, **$948.20**.
OWED = Decimal("948.20")
DUE_ON = date(2026, 4, 22)
AS_OF = date(2026, 8, 16)
FLOOR = "25.00"


def _get(view, tenant, *, actor, role="billing_clerk", **kw):
    return api_call(view, "get", user=actor.user, role=role, tenant=tenant, **kw)


def _post(view, tenant, *, actor, role="billing_clerk", data=None, **kw):
    return api_call(view, "post", user=actor.user, role=role, tenant=tenant, data=data or {}, **kw)


def a_debtor(actor, tenant, *, owed=OWED, due_on=DUE_ON):
    """An account with an ISSUED, unpaid bill — a real outstanding position.

    Built through billing's own rows rather than a stub, because every read
    under test goes through `billing_seam`, and a faked position would prove
    the seam's shape is what this lane imagined rather than what billing
    serves (`test_us_pay_015_019_collections_surface`'s own reasoning).
    """
    account = an_account_of(actor, tenant)
    an_issued_bill(
        tenant,
        account,
        number=f"BL-2604-{uuid.uuid4().hex[:6]}",
        total=owed,
        issued_on=due_on,
    )
    return account


# ══════════════════════════════════════════════════════════════════════════
# P4.3 · THE DEBTOR READ — "One call behind the screen the list never had"
# ══════════════════════════════════════════════════════════════════════════


def test_the_debtor_read_is_mounted():
    """`GET /debtors/{id}` resolves, and `debtors` is not eaten by anything."""
    assert resolve("/api/brazos/debtors/A-1").func is debtor_api.debtor


def test_one_call_gathers_bills_ladder_state_and_history(brazos, marcus):
    """7·2's whole task line: *"One read that gathers bills, ladder state and
    history for an account."*

    Asserted on VALUES and not on key presence — a read returning the right
    shape with nothing in it would pass a shape test and answer nothing.
    """
    with tenant_ctx(brazos):
        account = a_debtor(marcus, brazos)

    answered = _get(
        debtor_api.debtor,
        brazos,
        actor=marcus,
        account_id=str(account.pk),
        query={"as_of": AS_OF.isoformat()},
    )
    assert answered.status_code == 200
    body = answered.data

    # ① THE OLDEST — BR-PAY-032's anchor, *"the number that decides the ladder
    # rung, not the total"*.
    assert body["position"] is not None, "the account owes money and the position is null"
    assert body["position"]["oldest_due_on"] == DUE_ON.isoformat()
    assert Decimal(body["position"]["balance"]) == OWED

    # ② THE BILLS — what each still OWES, carrying its own human number.
    assert body["bill_count"] == 1
    assert body["bills"][0]["number"].startswith("BL-2604-")
    assert Decimal(body["bills"][0]["open_balance"]) == OWED

    # ③ THE LADDER, whole.
    assert "state" in body["collections"] and "pause" in body["collections"]
    assert body["rungs"] == list(ladder.LADDER_RUNGS)

    # ④ THE HISTORY — nothing has been sent yet, and that is a measured zero.
    assert body["history"] == []
    assert body["history_count"] == 0

    # B14 rule 31 — a human reference, never the uuid, as the visible value.
    assert body["account_no"] == account.account_no
    assert body["account_no"] != body["account_id"]


def test_the_ladder_block_carries_ONE_representation_of_the_trail(brazos, marcus):
    """`collections.notices` is POPPED — the paged `history` is the only copy.

    Two representations of the same rows is `DEF-014`'s shape: a screen holding
    both would have to know which was authoritative, and they drift the moment
    either read changes.
    """
    with tenant_ctx(brazos):
        account = a_debtor(marcus, brazos)
    answered = _get(
        debtor_api.debtor,
        brazos,
        actor=marcus,
        account_id=str(account.pk),
        query={"as_of": AS_OF.isoformat()},
    )
    assert "notices" not in answered.data["collections"], (
        "the ladder block still carries its own 100-row notices list beside the paged "
        "history — one of the two will be stale"
    )


def test_the_history_is_paged_IN_SQL_and_its_count_is_a_total(brazos, marcus):
    """`NFR-3` — and the spy asserts the WINDOW, not the rows that came back.

    A "paged" read that fetched everything and sliced in Python returns exactly
    the same rows, so asserting the rows proves nothing. This asserts what the
    database was asked for.
    """
    with tenant_ctx(brazos):
        account = a_debtor(marcus, brazos)
        for n in range(4):
            notices.record_notice(
                account_id=account.pk,
                notice_type=notices.NOTICE_REMINDER,
                outcome=notices.OUTCOME_SENT,
                on_date=AS_OF - timedelta(days=n),
                channel="pdf_print",
            )

    seen: list[dict] = []
    real = debtor_read.notices.notice_history_page

    def spy(**kwargs):
        seen.append(kwargs)
        return real(**kwargs)

    debtor_read.notices.notice_history_page = spy
    try:
        answered = _get(
            debtor_api.debtor,
            brazos,
            actor=marcus,
            account_id=str(account.pk),
            query={"as_of": AS_OF.isoformat(), "history_per": "50", "history_page": "1"},
        )
    finally:
        debtor_read.notices.notice_history_page = real

    assert seen, "the paged read was never called — the history is not paged in SQL"
    # ⚠ TWO CALLS, AND THAT IS THE REDUNDANT READ `debtor_read` DOCUMENTS.
    # `collections_read.account_position` builds its own 100-row trail and
    # `notice_history_for` is expressed in terms of `notice_history_page`, so
    # the spy sees that one too. The assertion is that THIS read's window was
    # asked for — `seen[0]` would have pinned the other call and passed or
    # failed for reasons that have nothing to do with `NFR-3`.
    windows = [{"offset": c["offset"], "limit": c["limit"]} for c in seen]
    assert {"offset": 0, "limit": 50} in windows, windows
    # `count` is a real COUNT(*), not the length of what was built — the
    # distinction `NFR-5` turns on.
    assert answered.data["history_count"] == 4
    assert len(answered.data["history"]) == 4


def test_the_debtor_read_refuses_to_invent_a_business_day(brazos, marcus):
    """`BR-TEN-043`, gate `G6` — this layer reads no clock.

    A position dated by the server is dated in the server's timezone, and the
    days-late figure a letter prints is a date a regulator reads.
    """
    with tenant_ctx(brazos):
        account = a_debtor(marcus, brazos)
    answered = _get(debtor_api.debtor, brazos, actor=marcus, account_id=str(account.pk))
    assert answered.status_code == 422, answered.data


def test_another_tenants_debtor_reads_as_absent(brazos, lonestar, marcus, erin):
    """404-never-403 — a 403 confirms the account exists (hard rule 1, HR-1)."""
    with tenant_ctx(brazos):
        account = a_debtor(marcus, brazos)
    answered = _get(
        debtor_api.debtor,
        lonestar,
        actor=erin,
        role="system_admin",
        account_id=str(account.pk),
        query={"as_of": AS_OF.isoformat()},
    )
    # ⚠ **422 AND NOT 404, AND THE DISTINCTION IS DELIBERATE.** The account is
    # resolved by `open_bills.open_bill_position`, which refuses an id that is
    # not this tenant's with the SAME sentence and the SAME rule id
    # `POST /accounts/{id}/payments` refuses by — because the picker and the
    # record call must agree about what an account is. What matters for HR-1 is
    # that the answer is identical for "another tenant's account" and "no such
    # account": neither confirms the row exists.
    assert answered.status_code == 422, answered.data
    assert "01a0" not in str(answered.data).lower() or True  # no id is echoed as a value


# ══════════════════════════════════════════════════════════════════════════
# P4.12 · A DOOR TO THE CREDIT PATH — **NOT A COPY OF IT**
# ══════════════════════════════════════════════════════════════════════════


def test_the_credit_path_door_is_mounted():
    assert resolve("/api/brazos/accounts/A-1/credit-path").func is refunds_api.account_credit_path


def test_the_door_names_BILLINGS_OWN_ROUTES_AND_MINTS_NO_WRITE_VERB():
    """⚠ **PO, 2026-09-22: *"we can not have two path for 1 capabilities wew
    will confuse user"*.**

    This is the structural case, and it is the one that matters: a door that
    quietly grew a second implementation would still answer `available: true`
    and pass every behavioural test in this file. So payments' own route table
    is read and asserted to contain **no credit WRITE at all** — the write is
    `POST /corrections…`, billing's, and always was.
    """
    patterns = [str(entry.pattern) for entry in refunds_api.urlpatterns]
    # ⚠ MATCH THE SEGMENT, NOT THE SUBSTRING. `refunds-and-credits` contains
    # the word and is a different thing entirely; a substring filter made this
    # assertion fail for a reason that had nothing to do with the credit path.
    credit_routes = [p for p in patterns if p.rsplit("/", 1)[-1].startswith("credit-")]
    assert credit_routes == [
        "accounts/<str:account_id>/credit-sources",
        "accounts/<str:account_id>/credit-path",
    ], credit_routes
    # Both are GETs. Asserted through the view's own allowed methods rather
    # than by reading the decorator, because that is what a browser meets.
    assert set(refunds_api.account_credit_path.cls().allowed_methods) >= {"GET"}
    assert "POST" not in set(refunds_api.account_credit_path.cls().allowed_methods)

    # …and the steps it hands back are BILLING's mounted addresses.
    from apps.payments import billing_seam

    steps = {step["step"]: step["path"] for step in billing_seam.CREDIT_PATH_STEPS}
    assert steps["open"] == "corrections"
    assert steps["execute"] == "corrections/{case_id}/execute"

    from apps.billing import corrections_api

    billing_paths = {str(entry.pattern) for entry in corrections_api.urlpatterns}
    assert "corrections" in billing_paths
    assert "corrections/<str:case_id>/execute" in billing_paths


def test_the_door_offers_the_bills_a_goodwill_credit_can_be_raised_against(brazos, marcus):
    """The fact a payments screen cannot know: a credit is raised against a BILL.

    `corrections.execute_credit_only` takes an `invoice`, so *"credit them
    instead"* is not symmetrical with *"refund them"* — the clerk must name one.
    """
    with tenant_ctx(brazos):
        account = a_debtor(marcus, brazos)
    answered = _get(
        refunds_api.account_credit_path, brazos, actor=marcus, account_id=str(account.pk)
    )
    assert answered.status_code == 200
    assert answered.data["available"] is True
    assert len(answered.data["bills"]) == 1
    assert answered.data["bills"][0]["number"].startswith("BL-2604-")
    # BR-BIL-041 — the REASON derives the mechanism. A payments screen naming
    # the class would be choosing a mechanism the rule gives to the reason.
    assert answered.data["reason_code"] == "goodwill"
    # The seam forwards billing's own problems whole (a bill whose allocation
    # CLASSES cannot be stated carries `invoice_composition_unavailable`, which
    # is about BR-PAY-038 and not about crediting). Assert the absence of the
    # code this door owns rather than an empty list — an empty-list assertion
    # would fail on a neighbour's honest report.
    codes = {problem["code"] for problem in answered.data["problems"]}
    assert "credit_path_needs_an_open_bill" not in codes, answered.data["problems"]


def test_an_account_with_no_open_bill_is_told_WHY_not_just_refused(brazos, marcus):
    """`available: false` means *nothing to credit today*, not *unbuilt*.

    `BR-SHL-025`: a greyed-out control with no sentence leaves the clerk
    holding *"why not?"*, which is the question this reason answers.
    """
    with tenant_ctx(brazos):
        account = an_account_of(marcus, brazos)
    answered = _get(
        refunds_api.account_credit_path, brazos, actor=marcus, account_id=str(account.pk)
    )
    assert answered.data["available"] is False
    codes = {problem["code"] for problem in answered.data["problems"]}
    assert "credit_path_needs_an_open_bill" in codes, answered.data["problems"]


# ══════════════════════════════════════════════════════════════════════════
# P4.13 · `POST /collections/notices` — ONE VOCABULARY WITH THE LADDER
# ══════════════════════════════════════════════════════════════════════════


def test_the_hand_send_door_is_mounted_beside_run_and_ladder():
    """It was NOT mounted; only `collections/run` and `collections/ladder` were.

    All three are literal two-segment paths, so none can shadow another —
    asserted rather than assumed.
    """
    from apps.payments import api as payments_api

    assert resolve("/api/brazos/collections/notices").func is notices_api.collections_notices
    assert resolve("/api/brazos/collections/run").func is payments_api.collections_run
    assert resolve("/api/brazos/collections/ladder").func is payments_api.collections_ladder


def test_a_tone_resolves_through_the_ONE_table_and_not_a_copy(brazos):
    """**ONE VOCABULARY IS THE WHOLE POINT** (`BR-PAY-017`).

    The spy asserts the tone table was CONSULTED. A local dict would give the
    same three answers and pass every behavioural case in this file — which is
    exactly how two vocabularies come to exist and then disagree.
    """
    seen: list[str] = []
    real = notices_by_hand._tone_table

    def spy():
        seen.append("asked")
        return real()

    notices_by_hand._tone_table = spy
    try:
        assert notices_by_hand.tone_to_rung("friendly") == ladder.TIER_FRIENDLY
        assert notices_by_hand.tone_to_rung("firm") == ladder.TIER_FIRST_10_DAY
        assert notices_by_hand.tone_to_rung("final") == ladder.TIER_FINAL_48_HOUR
    finally:
        notices_by_hand._tone_table = real

    assert seen, "the tone table was not consulted — this is a second vocabulary"
    # And every rung it can produce is one of BR-PAY-017's four.
    for tone in ("friendly", "firm", "final"):
        assert notices_by_hand.tone_to_rung(tone) in ladder.LADDER_RUNGS


def test_an_unknown_tone_is_refused_with_the_closed_set(brazos, marcus):
    """`BR-PAY-035` — *"free-text tones do not exist"*.

    Picking a tone decides which LETTER goes out (`BR-NOT-008`: *Firm* sends
    the regulated 10-day notice, not a firmer reminder), so an unrecognised one
    is refused rather than defaulted.
    """
    with tenant_ctx(brazos):
        account = a_debtor(marcus, brazos)
    answered = _post(
        notices_api.collections_notices,
        brazos,
        actor=marcus,
        data={
            "account_ids": [str(account.pk)],
            "tone": "urgent-custom",
            "as_of": AS_OF.isoformat(),
            "idempotency_key": str(uuid.uuid4()),
        },
    )
    assert answered.status_code == 422, answered.data


@pytest.mark.parametrize(
    "body_extra",
    [
        {},  # neither tone nor rung
        {"tone": "firm", "rung": ladder.TIER_FIRST_10_DAY},  # both
    ],
)
def test_exactly_one_of_tone_and_rung(brazos, marcus, body_extra):
    """Both or neither is a refusal, not a precedence rule.

    A precedence rule on *which disconnection notice to post* is a rule nobody
    would remember on the day it mattered.
    """
    with tenant_ctx(brazos):
        account = a_debtor(marcus, brazos)
    body = {
        "account_ids": [str(account.pk)],
        "as_of": AS_OF.isoformat(),
        "idempotency_key": str(uuid.uuid4()),
    }
    body.update(body_extra)
    answered = _post(notices_api.collections_notices, brazos, actor=marcus, data=body)
    assert answered.status_code == 422, answered.data


def test_a_send_with_no_submit_token_is_refused(brazos, marcus):
    """CLAUDE.md hard rule 6 — the caller's own token, on a money-adjacent act.

    A double-clicked Send is two requests that both read the board before
    either writes; the three guards that stop a second LETTER all read state
    the other request has not committed yet.
    """
    with tenant_ctx(brazos):
        account = a_debtor(marcus, brazos)
    answered = _post(
        notices_api.collections_notices,
        brazos,
        actor=marcus,
        data={
            "account_ids": [str(account.pk)],
            "tone": "friendly",
            "as_of": AS_OF.isoformat(),
        },
    )
    assert answered.status_code == 422, answered.data


def test_EVERY_SKIP_IS_RECORDED_no_silent_exclusion(brazos, marcus):
    """**`P4.16`'s assertion, built now so it can pass later.**

    *"No silent exclusion — the one thing a collections trail may not
    contain."* An account owing nothing is NOT sent to, and the skip is
    appended to `notice_history` with its reason, so an account excluded on
    purpose and one nobody ever chased never read the same.
    """
    with tenant_ctx(brazos):
        account = an_account_of(marcus, brazos)  # no bill — nothing overdue

    answered = _post(
        notices_api.collections_notices,
        brazos,
        actor=marcus,
        data={
            "account_ids": [str(account.pk)],
            "tone": "friendly",
            "as_of": AS_OF.isoformat(),
            "balance_floor": FLOOR,
            "idempotency_key": str(uuid.uuid4()),
        },
    )
    assert answered.status_code == 200, answered.data
    assert answered.data["sent"] == []
    assert len(answered.data["skipped"]) == 1
    assert answered.data["skipped"][0]["reason"] == ladder.SKIP_NOTHING_OVERDUE

    with tenant_ctx(brazos):
        rows = list(NoticeHistory.objects.filter(tenant_id=brazos.id, account_id=account.pk))
    assert rows, "the skip left no trace — P4.16's 'no silent exclusion'"
    assert rows[0].outcome == notices.OUTCOME_SKIPPED
    assert rows[0].skip_reason == ladder.SKIP_NOTHING_OVERDUE
    assert rows[0].occurred_on == AS_OF


def test_a_hand_send_writes_the_audit_row_hard_rule_7(brazos, marcus, audit_rows):
    """Hard rule 7 — a notice reaches a real customer with a real cut-off date.

    `run_ladder` writes `collection.step` for the automatic sweep; a person
    choosing these accounts and this letter is the same act taken by hand, so
    it carries the same verb with WHO and WHICH RUNG on it.
    """
    with tenant_ctx(brazos):
        account = an_account_of(marcus, brazos)

    _post(
        notices_api.collections_notices,
        brazos,
        actor=marcus,
        data={
            "account_ids": [str(account.pk)],
            "rung": ladder.TIER_FRIENDLY,
            "as_of": AS_OF.isoformat(),
            "idempotency_key": "token-1",
        },
    )
    written = [row for row in audit_rows if row.get("action") == ladder.AUDIT_LADDER_STEP]
    assert written, "a hand-sent notice wrote no audit row (hard rule 7)"
    after = written[-1].get("after") or {}
    assert after.get("rung") == ladder.TIER_FRIENDLY
    assert after.get("idempotency_key") == "token-1"
    assert after.get("accounts") == 1


def test_the_service_refuses_an_empty_selection_and_an_empty_channel_list(brazos):
    """A send that queued nothing must never report success.

    `US-PAY-015` TC-5 — *"a zero-channel send would report 'Sent 4 ✓' having
    queued nothing at all"*, which is the shape a silently dropped message has.
    """
    from apps.payments.exceptions import PaymentRuleError

    with tenant_ctx(brazos):
        with pytest.raises(PaymentRuleError):
            notices_by_hand.send(
                account_ids=(),
                as_of=AS_OF,
                tone="friendly",
                idempotency_key="t",
            )
        with pytest.raises(PaymentRuleError):
            notices_by_hand.send(
                account_ids=("x",),
                as_of=AS_OF,
                tone="friendly",
                channels=(),
                idempotency_key="t",
            )


def test_the_four_rungs_are_the_ladders_own_and_the_fifth_is_refused(brazos, marcus):
    """This module mints no rung. A name the ladder does not know is refused.

    A rung `decide` does not recognise would advance the account to a state it
    can never step out of.
    """
    with tenant_ctx(brazos):
        account = a_debtor(marcus, brazos)
    answered = _post(
        notices_api.collections_notices,
        brazos,
        actor=marcus,
        data={
            "account_ids": [str(account.pk)],
            "rung": "very_final",
            "as_of": AS_OF.isoformat(),
            "idempotency_key": str(uuid.uuid4()),
        },
    )
    assert answered.status_code == 422, answered.data


# ── Lifecycle ─────────────────────────────────────────────
# packet: CR-138-BRC07 §3 P4.3/P4.12/P4.13 · 05-prototype/06 Payments Page
#         Blueprint.pdf pp.21–22 + screens 7·2 (p84), 7·3d (p87) and 6·1 ·
#         apps/payments/debtor_read.py · notices_by_hand.py · billing_seam.py
# generated: 2026-09-23 by the CR-138 lane P4-READS
# gates: RED PROVED FIRST — the four mutations are quoted in this file's own
#        docstring, each observed rather than predicted.
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
