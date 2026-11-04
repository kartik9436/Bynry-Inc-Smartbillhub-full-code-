# ── Trace ──────────────────────────────────────────────
# Change:   CR-138-BRC07 · P4.13 — `POST /collections/notices`, which is NOT
#           mounted today; only `collections/run` and `collections/ladder` are.
#           Blueprint `05-prototype/06 Payments Page Blueprint.pdf` p22 and
#           screen 7·3d. Its outcome line: *"A clerk can send a notice by hand,
#           and it shares ONE vocabulary with the automatic ladder — which is
#           what makes no-double-send possible."*
#           Screens: S34 (the two bulk buttons that have never worked) · 7·3d
# Rules:    BR-PAY-017 (manual sends use the SAME tier ladder, channels and
#           exclusions as the sequence engine, and advance the SAME state) ·
#           BR-PAY-035 / BR-NOT-008 (the tone→step table, and that a regulated
#           step always renders the disconnect class) · BR-NOT-005 (every
#           notice is a QUEUE WRITE; nothing sends inline) · BR-CUS-039
#           (medical-hold accounts excluded) · BR-TEN-043 (the business date is
#           an argument, never a clock) · CLAUDE.md hard rule 6 (idempotency) ·
#           hard rule 7 (every money action writes `audit_log`) · hard rule 1
# Tests:    06-backend/tests/test_cr138_p4_13_collections_notices.py
# Impacts:  apps/payments/notices_api.py (the route) · config/urls.py ·
#           apps/payments/ladder.step_one (the ONE send path) ·
#           apps/payments/collections_read.ladder_board (the ONE stop-condition
#           evaluation) · apps/notifications/notices.TONE_TO_STEP (the ONE tone
#           table, resolved BY NAME)
# ───────────────────────────────────────────────────────
"""**A CLERK SENDS A NOTICE BY HAND — THROUGH THE LADDER, NOT BESIDE IT.**

╔══════════════════════════════════════════════════════════════════════════╗
║  ONE VOCABULARY. THIS FILE DEFINES NO RUNG, NO TONE AND NO SKIP REASON.  ║
╚══════════════════════════════════════════════════════════════════════════╝
`BR-PAY-017`: *"manual sends use the same tier ladder, channels and exclusions
as the sequence engine, and advance the same state."* That sentence is the
whole design, and it is what makes *"no double-send"* possible at all
(`US-PAY-015` TC-4): two vocabularies would be two states, and a customer who
complained about the 5-day notice would get it again from the other one.

So every name here is borrowed and none is minted:

  the RUNGS          `ladder.LADDER_RUNGS` — four, in `BR-PAY-017`'s order
  the TONE→STEP map  `apps.notifications.notices.TONE_TO_STEP`, resolved BY
                     NAME at call time. `GET /notice-tones` publishes that same
                     table, so the picker a clerk uses and the resolution this
                     performs cannot disagree
  the STOP CONDITIONS `collections_read.ladder_board`, which is `ladder.decide`
                     — **the five, plus the same-day guard**
  the SEND           `ladder.step_one`, which is `notices.send_reminders` /
                     `send_disconnect_notices` — the same two functions the S35
                     modals and `run_ladder` call
  the SKIP ROWS      `notices.record_notice`, the only writer of
                     `notice_history`

⚠ **THE CLERK CHOOSES THE RUNG; THE LADDER CHOOSES WHETHER.** That split is the
point. A hand send exists because a clerk knows something the engine does not —
*these three have ignored a reminder, send them the notice* — so the RUNG is
theirs. What is NOT theirs is the stop conditions: an account below the floor,
on a medical hold, on a paused plan, partly paid, not overdue, or already
written to today is skipped **exactly as the nightly engine would skip it**, and
the skip is RECORDED. A hand send that could step past a medical hold would put
this product in front of a regulator.

═══════════════════════════════════════════════════════════════════════════════
EVERY SKIP IS RECORDED — P4.16's ASSERTION, BUILT NOW SO IT CAN PASS LATER
═══════════════════════════════════════════════════════════════════════════════
`P4.16`: *"Every skip is recorded and shown — five reasons. **No silent
exclusion: the one thing a collections trail may not contain.**"* Every path out
of `send()` below writes a `notice_history` row: the sends through
`ladder.step_one`, and the skips here. **There is no `continue` in this file
that does not write first.**

An account excluded for a medical hold and one nobody ever chased must never
read the same on S34's *Notice history* column — which is J4 step 2's contract
and `notices.py`'s own opening statement.

═══════════════════════════════════════════════════════════════════════════════
HARD RULE 6 — PRESSING SEND TWICE DOES NOT WRITE TWICE, IN THREE LAYERS
═══════════════════════════════════════════════════════════════════════════════
It is not one guard, and saying which is which matters, because two of the
three were already here and the third is the one this route needed:

  1. **THE SAME-DAY GUARD**, `ladder.SKIP_ALREADY_NOTICED_TODAY`. The board
     evaluates it and this refuses on it. Its own docstring is the reason it
     exists: *"PER PASS IS NOT PER DAY, and the difference is four letters in
     one afternoon"* — on an account 62 days overdue all four rungs are past due
     at once, so four presses post four letters, the last a certified one at
     real postage. **`POST /collections/run` pressed twice is two passes**, and
     so is this. `DEF-3150`.
  2. **THE TIER GUARD**, `notices._tier_already_sent`, inside the sender. A tier
     already sent is skipped whoever asks — the engine, the S35 modal or this.
  3. **THE DETERMINISTIC QUEUE KEY**, `notices.ladder_notice_source_id`, which
     hashes account + kind + tier. A re-send finds its own outbound row and
     writes nothing, so even a send that got past 1 and 2 cannot produce a
     second letter.

⚠ **AND THE CALLER'S OWN TOKEN IS REQUIRED ON TOP OF ALL THREE.** A double-click
inside the same second reaches the server as two requests that both see a board
computed before either wrote — the classic read-modify-write race that the three
guards above, all of which read state the other request has not yet committed,
do not close. `idempotency_key` is the form's submit token and `send()` refuses
without one, which is the posture `POST /accounts/{id}/refunds` already takes
for exactly this reason.

⚠ **WHAT THIS FILE DOES NOT DO, AND IT IS STATED RATHER THAN HIDDEN (law 1):**
the token is REQUIRED and REPORTED but it is not yet a unique key in the
database. `payments.webhook_key`'s `UNIQUE (tenant_id, webhook_key)` is the
shape a second press should hit, and `notice_history` has no such column. Filed
as `OQ-PAY-12606` rather than a column invented on a money path — the three
guards above already stop the letter, and what the missing key would stop is a
duplicate HISTORY row, which is a reporting defect rather than a second letter
in a customer's hand.

This module reads no clock (`BR-TEN-043`) and writes no journal line (rule 5).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from importlib import import_module
from typing import Any

from apps.payments import collections_read, ladder, notices
from apps.payments.exceptions import PaymentRuleError
from core import audit as core_audit

#: The tone table's owner. Resolved BY NAME at call time — the idiom every seam
#: in this module uses — so payments imports nothing of notifications' and the
#: edge is greppable from both sides.
TONE_MODULE = "notifications"
TONE_TABLE = "TONE_TO_STEP"

#: hard rule 7. A notice reaches a real customer with a real cut-off date on it;
#: `run_ladder` writes `collection.step` for the automatic sweep and this is the
#: same act taken by a person, so it carries the same verb with its own entity.
AUDIT_HAND_SEND = ladder.AUDIT_LADDER_STEP

#: What `send()` reports when the tone table cannot be resolved. A PROBLEM and
#: not an exception only where it is harmless; an unresolvable tone REFUSES,
#: because guessing which letter a tone sends is how a clerk posts a certified
#: 48-hour disconnection notice believing they sent a reminder (`BR-NOT-008` is
#: the rule that makes this dangerous rather than untidy).
TONE_TABLE_UNAVAILABLE = "tone_table_unavailable"


@dataclass(frozen=True)
class HandSend:
    """What ONE hand-sent notice did for ONE account."""

    account_id: str
    account_no: str | None
    rung: str
    sent: bool
    skip_reason: str | None = None
    tier_from: str | None = None
    tier_to: str | None = None
    queued_message_ids: tuple[str, ...] = ()
    detail: str | None = None


def tone_to_rung(tone: str) -> str:
    """Which RUNG a tone sends — through the ONE table, never a copy of it.

    `TONE_TO_STEP` maps `firm` and `final` to their disconnect tiers and
    `friendly` to **`None`**, meaning *not a regulated step*. `None` is not an
    absence here: the friendly tone IS the ladder's first rung, `TIER_FRIENDLY`,
    and that is the single line of translation this file performs.

    ⚠ **`TIER_SECOND_5_DAY` HAS NO TONE, AND THAT ASYMMETRY IS REAL AND
    REPORTED.** `LADDER_RUNGS` has four members and `TONE_TO_STEP` has three
    keys, so the 5-day notice is reachable by the automatic engine and by a
    caller naming the rung directly, and **not** by a clerk picking a tone.
    That is why `send()` accepts a `rung` as well as a `tone`: closing the gap
    by inventing a fourth tone would add a word to a table `BR-PAY-035` ratified
    and `GET /notice-tones` publishes. Filed as `OQ-PAY-12607`.

    An unknown tone is REFUSED with the closed set. `notifications.notices`
    refuses it too — *"free-text tones do not exist"* — and this refuses at the
    door so a caller is told before anything is evaluated.
    """
    table = _tone_table()
    if tone not in table:
        raise PaymentRuleError(
            f"unknown tone {tone!r}; BR-PAY-035 names {', '.join(table)} and states that "
            "free-text tones do not exist. Picking a tone decides which LETTER goes out — "
            "'Firm' sends the regulated 10-day disconnect notice, not a firmer reminder "
            "(BR-NOT-008) — so an unrecognised one is refused rather than defaulted.",
            br_ref="BR-PAY-035",
        )
    step = table[tone]
    return ladder.TIER_FRIENDLY if step is None else step


def _tone_table() -> dict[str, str | None]:
    """`apps.notifications.notices.TONE_TO_STEP`, resolved by name.

    REFUSES when it cannot be resolved rather than falling back to a local copy.
    A fallback table is a second answer to *"which letter does Firm send?"*, and
    the day the two disagree a clerk posts a certified letter believing they
    sent a reminder.
    """
    try:
        module = import_module(f"apps.{TONE_MODULE}.notices")
    except ImportError as missing:  # pragma: no cover - defensive
        raise PaymentRuleError(
            "the tone→step table cannot be read, so which LETTER a tone sends cannot be "
            "answered. Nothing was queued. BR-NOT-008 makes this a refusal rather than a "
            "default: a guessed tone can post a regulated disconnection notice.",
            br_ref="BR-NOT-008",
        ) from missing
    table = getattr(module, TONE_TABLE, None)
    if not isinstance(table, dict) or not table:
        raise PaymentRuleError(
            "the tone→step table is empty or is not a mapping. Nothing was queued.",
            br_ref="BR-NOT-008",
        )
    return dict(table)


def send(
    *,
    account_ids: tuple[Any, ...],
    as_of: date,
    tone: str | None = None,
    rung: str | None = None,
    cut_date: date | None = None,
    channels: tuple[str, ...] = ("pdf_print",),
    balance_floor: Decimal | None = None,
    partial_pause_percent: Decimal | None = None,
    medical_hold_account_ids: tuple[Any, ...] = (),
    idempotency_key: str,
    actor: Any = None,
) -> dict[str, Any]:
    """Send ONE rung by hand, over a selection — the two S34 buttons, served.

    `Send a reminder` and `Send a disconnection notice` have rendered DISABLED
    on S34 since the screen shipped, with `OutstandingsTab.tsx`'s own words:
    *"both need `POST /collections/notices` — which is not mounted."* This is
    that endpoint's service.

    **Exactly one of `tone` and `rung`.** A clerk's picker sends a tone; a
    caller that already knows the rung (the board's `next_rung`, a replayed
    request) names it. Both resolve into the SAME four-member vocabulary and
    neither widens it. Both absent, or both given, is a refusal rather than a
    precedence rule nobody would remember.

    **THE BOARD IS ASKED FIRST, AND IT IS THE LADDER'S OWN ANSWER.** Every
    account in the selection is evaluated by `collections_read.ladder_board` —
    which is `ladder.decide`, the five stop conditions plus the same-day guard —
    and an account it stops is SKIPPED with that reason recorded. The clerk's
    rung is then handed to `ladder.step_one`, which re-asks payments' own two
    conditions and keeps its veto.

    ⚠ **AN ACCOUNT ABSENT FROM THE BOARD IS SKIPPED AS `nothing_overdue`, NOT
    SENT.** The board's rows are the accounts with an outstanding position, so
    an id that does not come back owes nothing — and a notice to a customer who
    owes nothing is the worst letter this product can post. It is recorded like
    any other skip.

    Returns the sends, the skips and the problems. **It does not raise on a
    per-account refusal**: a selection of twelve where one is on a medical hold
    must send the eleven and say why the twelfth did not, which is what a bulk
    act means.
    """
    if not account_ids:
        raise PaymentRuleError(
            "choose at least one account. A send over an empty selection would report "
            "success having queued nothing at all — the shape a silently dropped message "
            "has (US-PAY-015 TC-5).",
            br_ref="BR-PAY-017",
        )
    if not channels:
        raise PaymentRuleError(
            "choose at least one channel. A notice with no channel would report 'Sent 3 ✓' "
            "having queued nothing (US-PAY-015 TC-5).",
            br_ref="BR-NOT-005",
        )
    if not str(idempotency_key or "").strip():
        raise PaymentRuleError(
            "this send needs the form's submit token. Without one a double-clicked Send is "
            "two requests that both read the board before either writes, and the three "
            "guards that stop a second letter all read state the other request has not "
            "committed yet (CLAUDE.md hard rule 6).",
            br_ref="BR-PAY-028",
        )
    if (tone is None) == (rung is None):
        raise PaymentRuleError(
            "name exactly one of `tone` and `rung`. A tone decides which letter goes out "
            "(BR-NOT-008) and a rung names it directly; accepting both would need a "
            "precedence rule, and a precedence rule on which disconnection notice to post "
            "is a rule nobody would remember on the day it mattered.",
            br_ref="BR-PAY-035",
        )

    chosen = tone_to_rung(tone) if tone is not None else str(rung)
    if chosen not in ladder.LADDER_RUNGS:
        raise PaymentRuleError(
            f"unknown ladder rung {chosen!r}; BR-PAY-017 names "
            f"{', '.join(ladder.LADDER_RUNGS)}. A rung this module does not recognise would "
            "advance the account to a state `decide` can never step out of.",
            br_ref="BR-PAY-017",
        )

    board = collections_read.ladder_board(
        as_of=as_of,
        account_ids=tuple(account_ids),
        balance_floor=balance_floor,
        partial_pause_percent=partial_pause_percent,
        medical_hold_account_ids=tuple(medical_hold_account_ids),
    )
    rows = {str(row["account_id"]): row for row in board.get("rows", ())}

    notice_type = (
        notices.NOTICE_REMINDER if chosen == ladder.TIER_FRIENDLY else notices.NOTICE_DISCONNECT
    )
    results: list[HandSend] = []
    problems: list[dict[str, Any]] = [dict(entry) for entry in board.get("problems", ())]

    for account_id in account_ids:
        key = str(account_id)
        row = rows.get(key)

        if row is None:
            # Not on the board = no outstanding position. RECORDED, never
            # silently dropped: P4.16's "no silent exclusion".
            results.append(
                _skip(
                    account_id=account_id,
                    account_no=None,
                    rung=chosen,
                    reason=ladder.SKIP_NOTHING_OVERDUE,
                    notice_type=notice_type,
                    as_of=as_of,
                    detail="this account has no outstanding position, so there is nothing to "
                    "chase. A notice to a customer who owes nothing is the worst letter this "
                    "product can post.",
                    actor=actor,
                )
            )
            continue

        if not row.get("runs"):
            results.append(
                _skip(
                    account_id=account_id,
                    account_no=row.get("account_no"),
                    rung=chosen,
                    reason=row.get("skip_reason") or ladder.SKIP_NOTHING_OVERDUE,
                    notice_type=notice_type,
                    as_of=as_of,
                    detail=row.get("detail"),
                    actor=actor,
                    balance=row.get("balance"),
                )
            )
            continue

        # ⚠ THE SEND IS `ladder.step_one` AND NOTHING ELSE. Three writes in one
        # transaction — the queue row, the `notice_history` row and the tier —
        # and payments keeps its veto inside it.
        step = ladder.step_one(
            account_id=account_id,
            rung=chosen,
            as_of=as_of,
            actor=actor,
            channels=tuple(channels),
            cut_date=cut_date,
        )
        problems.extend(dict(problem) for problem in step.problems)
        results.append(
            HandSend(
                account_id=key,
                account_no=row.get("account_no"),
                rung=chosen,
                sent=step.stepped,
                skip_reason=step.skip_reason,
                tier_from=step.tier_from,
                tier_to=step.tier_to,
                queued_message_ids=step.queued_message_ids,
            )
        )

    # ── hard rule 7 ────────────────────────────────────────────────────────
    # A person chose these accounts and this letter. `run_ladder` writes one row
    # for its sweep; this writes one for the press, with WHO and WHICH rung.
    # `entity_id` is left NULL for `run_ladder`'s own reason: a bulk send is not
    # a persisted entity and a date or a token reaching a UUIDField raises
    # `ValueError: badly formed hexadecimal UUID string` — the 500 that crashed
    # a request AFTER the ladder had already stepped it.
    core_audit.money_action(
        actor,
        AUDIT_HAND_SEND,
        "collection_notice_by_hand",
        None,
        after={
            "as_of": as_of.isoformat(),
            "rung": chosen,
            "tone": tone,
            "channels": list(channels),
            "idempotency_key": str(idempotency_key),
            "accounts": len(account_ids),
            "sent": [{"account_id": r.account_id, "rung": r.rung} for r in results if r.sent],
            "skipped": [
                {"account_id": r.account_id, "reason": r.skip_reason} for r in results if not r.sent
            ],
        },
    )

    return {
        "as_of": as_of.isoformat(),
        "rung": chosen,
        "tone": tone,
        "rungs": list(ladder.LADDER_RUNGS),
        "sent": [
            {
                "account_id": r.account_id,
                "account_no": r.account_no,
                "rung": r.rung,
                "tier_from": r.tier_from,
                "tier_to": r.tier_to,
                "queued_message_ids": list(r.queued_message_ids),
            }
            for r in results
            if r.sent
        ],
        "skipped": [
            {
                "account_id": r.account_id,
                "account_no": r.account_no,
                "rung": r.rung,
                "reason": r.skip_reason,
                "detail": r.detail,
            }
            for r in results
            if not r.sent
        ],
        "problems": problems,
    }


def _skip(
    *,
    account_id: Any,
    account_no: str | None,
    rung: str,
    reason: str,
    notice_type: str,
    as_of: date,
    detail: str | None,
    actor: Any,
    balance: str | None = None,
) -> HandSend:
    """Record the skip, THEN return it — never the other way round.

    P4.16: *"No silent exclusion — the one thing a collections trail may not
    contain."* `record_notice` is the only writer of `notice_history` and it
    REFUSES a skip with no reason, so a caller cannot record a half-skip.
    """
    notices.record_notice(
        account_id=account_id,
        notice_type=notice_type,
        outcome=notices.OUTCOME_SKIPPED,
        skip_reason=reason,
        on_date=as_of,
        tier=rung,
        detail={"by_hand": True, "why": detail, "balance": balance},
        actor=actor,
    )
    return HandSend(
        account_id=str(account_id),
        account_no=account_no,
        rung=rung,
        sent=False,
        skip_reason=reason,
        detail=detail,
    )


# ── Lifecycle ─────────────────────────────────────────────
# packet: CR-138-BRC07 §3 P4.13 · 05-prototype/06 Payments Page Blueprint.pdf
#         p22 + screen 7·3d · apps/payments/ladder.py · collections_read.py ·
#         notices.py · apps/notifications/notices.TONE_TO_STEP · BR-PAY-017 ·
#         BR-PAY-035 · BR-NOT-005 · BR-NOT-008 · BR-CUS-039
# generated: 2026-09-23 by the CR-138 lane P4-READS
# checklist: A✔ B=deferred(P4.14 and P4.27 own screen 7·3d and are HELD to
#            wave 2) C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-09)
# gates: RED PROVED FIRST — see the test file's own header.
# exceptions:
#   (1) THIS FILE MINTS NO VOCABULARY. Rungs, tones, skip reasons, the sender
#       and the history writer are all borrowed. The ONE translation it performs
#       is `TONE_TO_STEP`'s `None` → `TIER_FRIENDLY`, and it is a named function
#       with its reasoning attached.
#   (2) ⚠ `TIER_SECOND_5_DAY` HAS NO TONE — four rungs, three tones. A clerk
#       picking a tone cannot reach the 5-day notice; a caller naming the rung
#       can. Inventing a fourth tone would widen a table BR-PAY-035 ratified and
#       `GET /notice-tones` publishes. Filed as `OQ-PAY-12607`.
#   (3) ⚠ THE IDEMPOTENCY TOKEN IS REQUIRED AND AUDITED BUT IS NOT YET A UNIQUE
#       KEY. Three guards already stop a second LETTER (same-day, tier-already-
#       sent, deterministic queue id); what the missing key would stop is a
#       duplicate HISTORY row under a same-second double click. Filed as
#       `OQ-PAY-12606` rather than a column invented on a money path.
#   (4) AN ACCOUNT ABSENT FROM THE BOARD IS SKIPPED AS `nothing_overdue` AND
#       RECORDED. It is not an error and it is not a silent drop.
#   (5) A PER-ACCOUNT REFUSAL DOES NOT RAISE. A bulk act sends the eleven and
#       reports the twelfth; raising would make one medical hold cancel a whole
#       morning's chase.
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
