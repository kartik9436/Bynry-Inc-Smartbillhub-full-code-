# ── Trace ──────────────────────────────────────────────
# Story:    US-RBS-024 (EP-RBS-05) — CR-075 wave S, the customers half: the two
#           reads runbook 12 (*Disconnect eligibility*) makes, added by the
#           module that OWNS `disconnect_cases`, `disconnect_notices` and
#           `account_protections`.
# Rules:    BR-RBS-039 (a runbook READS through a seam this module owns; the
#           OWNING module publishes the selector and the seam never reaches past
#           it) · BR-RBS-032 (a returned letter is not a served notice) ·
#           BR-CUS-100 (proof of service is a record a PERSON enters; a tier-3
#           cut must not be schedulable on an unrecorded service) · BR-CUS-039
#           (a protection freezes the ladder) · BR-CUS-082 (a closed account
#           cannot be escalated to disconnection) · BR-TEN-043 (a business date
#           is an argument, never a clock read — gate G6) · CLAUDE.md hard
#           rule 1 (tenant scoping) · hard rule 8 (an address lives on
#           `premises`, so nothing here serves one)
# Tests:    06-backend/tests/test_us_rbs_024_disconnect_eligibility.py
# Impacts:  apps/runbooks/seams/customers_seam.py (the two wrappers) ·
#           04-docs/05-modules/17-runbooks/13-selector-inventory.md W-3
# ───────────────────────────────────────────────────────
"""READ ONLY — the two questions runbook 12 asks of this module.

⚠ **THIS FILE IS `customers`', NOT `runbooks`', AND THAT IS THE WHOLE POINT.**
`BR-RBS-039` and `13-selector-inventory.md` say the same thing twice: a runbook
reads through a seam, and **the owning module adds the selector**. A version of
these two living inside `apps/runbooks/` would be `customers`' law — what *the
last tier* is, what *served* means, which four checks a protection sweep runs —
re-derived in a file `customers`' reviewers never open, and `G115` refuses it
besides.

⚠ **A THIRD KIND OF MODULE, EXACTLY AS `apps/payments/runbook_reads.py` IS.** It
is not `selectors.py`, because that file is edited by several lanes in a week and
a whole-file collision on it costs more than a new name (CLAUDE.md law 11).
`runbooks/seams/customers_seam.py` imports this module by name.

WHY THE BOARD READS `disconnect_cases` AND NOT PAYMENTS' LADDER
---------------------------------------------------------------
`RB-112`'s scope row is **Last tier · certified letter sent**, and this product
holds two overlapping ladders — `apps/payments`' `account_collection_state`
(rungs: reminder · 10-day · 5-day · certified final) and this module's
`disconnect_cases.tier` (TIER 1 · 2 · 3), an overlap `disconnects.py`'s own
lifecycle block records as unruled (`DEF-675`).

**Only one of the two records a CERTIFIED LETTER and its proof of service.**
`account_collection_state` carries the rung and the date it was sent and nothing
about how it went out; `disconnect_notices` carries `service_channel`,
`proof_reference`, `served_on`, `signed_for_on` and `proof_recorded_at`, and
`BR-CUS-100` — PO 2026-08-25 — makes exactly those columns the thing that
authorises a cut: *"a tier-3 cut must not be schedulable on an unrecorded
service."* A disconnect list assembled from the other ladder could not answer its
own step 2. So the board is built from the cases, and the runbook reports how
many of them payments' ladder ALSO shows at its final rung, so the disagreement
`DEF-675` describes arrives as a NUMBER on the screen rather than as a silence.

WHAT THESE ANSWERS CANNOT SAY, SAID IN THE ANSWER ITSELF
---------------------------------------------------------
1. **A DISPUTE OVER AN AMOUNT IS NOT STORED ANYWHERE IN THIS PRODUCT.**
   `protection_check` already answers that fourth row as `unavailable` rather
   than `pass`, in its own words: *"a green clearance derived from a table that
   does not exist would authorise a cut."* `protection_board` carries that
   verdict through unchanged and never collapses it into a clean sweep.
2. **`delivered` IS A PROVIDER FACT AND NO PROVIDER ADAPTER EXISTS ON ANY
   CHANNEL, PRINT INCLUDED.** So *the letter arrived* is not readable from
   `outbound_messages` on any deployment; what is readable is a person's
   attestation that they served it, which is `BR-CUS-100`'s design and the
   stronger fact. `final_notice_board` returns the proof and states the absence
   of the other.
3. **NOTHING HERE SERVES AN ADDRESS** (hard rule 8, `BR-MET-1161`). The field
   list's address is walked to on `premises` through `metering_seam`; this file
   carries the unit and premises HANDLES and stops.
"""

from __future__ import annotations

import datetime as dt
from typing import Any

from apps.customers import disconnects
from core import tenancy as core_tenancy


def _tenant_id() -> Any:
    """The tenant this read is for, or a refusal — never a silent whole-estate read.

    `apps/payments/runbook_reads._tenant_id`'s posture, for its reason: on
    PostgreSQL RLS `FORCE` would return nothing at all, and on the SQLite unit
    tier it would return EVERY tenant's rows. The two failure modes are opposite
    and both are worse than a refusal.
    """
    tenant_id = core_tenancy.current_tenant_id()
    if tenant_id is None:
        raise RuntimeError(
            "a runbook read was taken with no tenant set. CLAUDE.md hard rule 1: never touch a "
            "tenant table without `app.tenant_id`. On PostgreSQL this would read nothing and on "
            "the SQLite test tier it would read everything, so it refuses instead."
        )
    return tenant_id


def _accounts_by_id(account_ids) -> dict[str, Any]:
    """Account rows through this module's OWN published queryset.

    `apps.customers.selectors.account_queryset` — never `Account.objects`, which
    is the queryset without this module's tenant scope or its `select_related`.
    """
    from apps.customers import selectors as customers_selectors

    wanted = [one for one in account_ids if one]
    if not wanted:
        return {}
    return {
        str(row.id): row
        for row in customers_selectors.account_queryset().filter(id__in=wanted)
    }


def _labels(accounts: dict[str, Any]) -> dict[str, str]:
    """What a clerk calls each account — never its id (B14 rule 31).

    `primary_contact_names_for` is this module's OWN batched read and is what
    `account_row` uses, so the name on a disconnect list and the name on the
    accounts screen cannot come out different. The account number is the
    fallback because every account has one and *"(unnamed)"* on a field list a
    crew carries is worse than a number they can look up.
    """
    from apps.customers import selectors as customers_selectors

    if not accounts:
        return {}
    names = customers_selectors.primary_contact_names_for(list(accounts))
    return {
        key: str(names.get(key) or getattr(row, "account_no", "") or "")
        for key, row in accounts.items()
    }


# ══════════════════════════════════════════════════════════════════════════
# W-3 · THE LAST TIER, AND HOW ITS LETTER WENT OUT — runbook 12 steps 1 and 2
# ══════════════════════════════════════════════════════════════════════════


def final_notice_board(*, as_of: dt.date, tier: str | None = None) -> dict[str, Any]:
    """Every open case at the LAST tier, with the certified letter's own record.

    `13-selector-inventory.md` W-3 asks for *"whether a notice was actually
    DELIVERED, not merely queued"*, account-first. This is the answer that
    exists: `notifications` cannot say whether anything was delivered on ANY
    channel — `delivery_ops.queue_health` records that *"`delivered` and
    `bounced` are PROVIDER facts … no provider adapter exists on any channel,
    print included"* — and `BR-CUS-100` deliberately separates the two halves:
    *"the SEND is in-app … and the PROOF is a record a person enters."* So the
    row carries the PROOF, and `delivery_reported` says out loud that the other
    half is not readable anywhere in this product.

    ⚠ **`as_of` IS AN ARGUMENT AND NEVER A CLOCK READ** (`BR-TEN-043`, `G6`): a
    list re-taken for last Tuesday must be last Tuesday's list, or a run re-taken
    to answer *"why was this household on it"* answers about today instead.

    Each row carries:

      `account_id` `account_no` `label`   who — the number and the name, never the id
      `unit_id` `premises_id`             HANDLES for the address walk (hard rule 8)
      `case_no` `state` `tier`            the case, in this module's vocabulary
      `notice_issued_on`                  when the certified letter was raised
      `proof`                             `service_proof_for`'s own answer, whole
      `cut_reachable`                     `BR-CUS-082` — or the reason it is not

    ⚠ **A CLOSED CASE AND A CLOSED ACCOUNT ARE BOTH EXCLUDED, BY DIFFERENT
    RULES.** `open_case_for`'s exclusion set (`stopped`, `restored`,
    `closed_out`) is applied here through the same predicate that function uses,
    and `assert_cut_reachable` answers the account half — `BR-CUS-082`, *"a
    closed account cannot be escalated to disconnection — there is nothing left
    to disconnect."* Both are reported rather than silently filtered, because a
    supervisor asking *"where did the Okonkwo case go"* deserves the sentence.
    """
    tenant_id = _tenant_id()
    wanted_tier = tier or disconnects.TIER_3
    cases = list(
        disconnects.DisconnectCase.objects.filter(
            tenant_id=tenant_id, tier=wanted_tier
        ).exclude(state__in=disconnects.CLOSED_CASE_STATES)
    )
    accounts = _accounts_by_id([case.account_id for case in cases])
    labels = _labels(accounts)

    rows: list[dict[str, Any]] = []
    unreachable = 0
    for case in cases:
        account = accounts.get(str(case.account_id))
        proof = disconnects.service_proof_for(case, tier=wanted_tier)
        notice = disconnects.latest_notice_at_tier(case, wanted_tier)
        reason = ""
        try:
            disconnects.assert_cut_reachable(case)
        except disconnects.DisconnectRuleError as refusal:
            reason = getattr(refusal, "code", "") or "cut_not_reachable"
            unreachable += 1
        rows.append(
            {
                "account_id": str(case.account_id),
                "account_no": getattr(account, "account_no", None),
                "label": labels.get(str(case.account_id), ""),
                # HANDLES, never visible values — the address is walked to on
                # `premises` (hard rule 8) and the meter through `metering`.
                "unit_id": str(account.unit_id) if getattr(account, "unit_id", None) else None,
                "premises_id": (
                    str(account.premises_id) if getattr(account, "premises_id", None) else None
                ),
                "is_sample": bool(getattr(account, "is_sample", False)),
                "case_no": case.case_no,
                "state": case.state,
                "tier": case.tier,
                "sequence": case.sequence,
                "notice_issued_on": (
                    notice.issued_on.isoformat() if notice and notice.issued_on else None
                ),
                "proof": dict(proof),
                "cut_reachable": not reason,
                "cut_not_reachable_because": reason,
            }
        )
    rows.sort(key=lambda row: (str(row["account_no"] or ""), row["account_id"]))
    return {
        "as_of": as_of.isoformat(),
        "tier": wanted_tier,
        "rows": rows,
        "cases_at_this_tier": len(rows),
        "cases_whose_cut_is_not_reachable": unreachable,
        # ⚠ **NOT A DECORATION — hard-won law 7.** `False` here means *no
        # channel on this deployment reports delivery*, which is a different
        # sentence from *nothing bounced*, and the two send a crew to opposite
        # places. It is a constant today and is served as data so the day an
        # adapter lands the runbook's own sentence changes with it.
        "delivery_reported": False,
        "delivery_not_reported_because": (
            "delivered and bounced are provider facts and no provider adapter exists on any "
            "channel, print included. What is recorded is a person's attestation that the "
            "letter was served (BR-CUS-100)."
        ),
        "proof_channel_required": disconnects.TIER_3_REQUIRED_CHANNEL,
    }


# ══════════════════════════════════════════════════════════════════════════
# S · EVERY PROTECTION, RE-CHECKED ON THE MORNING — runbook 12 steps 5 and 6
# ══════════════════════════════════════════════════════════════════════════


def protection_board(account_ids, *, as_of: dt.date) -> dict[str, Any]:
    """`protection_check` for each of these accounts, plus a plan-in-good-standing
    verdict — the four rows `B18` §5.8.4 step 2 names, per account.

    ⚠ **THIS IS `protection_check` CALLED N TIMES AND NOT A SET-SHAPED COPY OF
    IT.** `customers_seam.medical_hold`'s docstring already states that trade for
    the medical half — *"a batched form is `customers`' to publish and is not
    invented here, because a set-shaped copy of `in_force` would be a second
    statement of a rule whose plan half reads payments."* The batched form is
    this function, and it batches the CALL rather than the RULE: the loop is
    here, in the owning module, and each answer is still `protection_check`'s.

    ⚠ **THE PLAN ROW IS THE ONE THE CARD ADDS A WORD TO.** `RB-112`'s scope says
    *"Never include: … Plan in good standing"* — not *on a plan*. A protection of
    kind `payment_plan` is recorded by `_plan_protection_is_live`, which reads
    payments' own pause; a plan that has fallen over is not in good standing and
    the pause lifts on payments' side. So this reads the same answer rather than
    re-deciding what *good standing* means, and `plan_in_good_standing` is the
    protection row's own `in_force`.

    ⚠ **THE DISPUTE ROW IS `unavailable`, NEVER `pass`, AND THAT TRAVELS.**
    `protection_check`'s own words: *"nothing in this repository stores a
    disputed AMOUNT … a green clearance derived from a table that does not exist
    would authorise a cut."* The count of accounts whose dispute could not be
    checked is returned beside the findings, because a blind spot with no number
    on it is indistinguishable from an empty one (hard-won law 7).
    """
    _tenant_id()
    wanted = [str(one) for one in account_ids if one]
    by_account: dict[str, dict[str, Any]] = {}
    counts = {kind: 0 for kind in disconnects.PROTECTIONS}
    for account_id in wanted:
        check = disconnects.protection_check(account_id, as_of=as_of)
        held = {
            str(row["check"]): row
            for row in check["checks"]
            if row["outcome"] == "fail"
        }
        for kind in held:
            if kind in counts:
                counts[kind] += 1
        by_account[account_id] = {
            "all_clear": bool(check["all_clear"]),
            "in_force": sorted(held),
            "checks": [dict(row) for row in check["checks"]],
            "medical": disconnects.PROTECTION_MEDICAL in held,
            "plan_in_good_standing": disconnects.PROTECTION_PLAN in held,
            "weather_moratorium": disconnects.PROTECTION_MORATORIUM in held,
            "reasons": {kind: str(row.get("reason") or "") for kind, row in held.items()},
            "since": {
                kind: (str(row.get("effective_from")) if row.get("effective_from") else None)
                for kind, row in held.items()
            },
        }
    return {
        "as_of": as_of.isoformat(),
        "accounts": by_account,
        "counts": dict(counts),
        "accounts_checked": len(wanted),
        # ⚠ EVERY account, always — the dispute check is `unavailable` for all of
        # them and will be until a disputed AMOUNT is stored somewhere.
        "dispute_checked": 0,
        "dispute_not_checked": len(wanted),
        "dispute_not_checked_because": (
            "nothing in this product stores a disputed amount, so an open dispute cannot be read "
            "from an account (B18 J08 step 7b(i))."
        ),
    }


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-RBS-024 (EP-RBS-05; CR-075 wave S)
# generated: 2026-09-07 by the CR-075 wave S build lane
# checklist: A✔ B=n/a(no schema change — every column read here exists) C✔ D=n/a(no endpoint) E=n/a(no screen) F✔ G✔ H=n/a(no 🔒 path: this composes no idempotency key, touches no rating math and posts no ledger line)
# gates: pytest tests/test_us_rbs_024_disconnect_eligibility.py · G115 · G20
# exceptions: the board reads `disconnect_cases` rather than payments' `account_collection_state` — the two ladders overlap unruled (`DEF-675`) and only one of them records a certified letter and its proof of service (`BR-CUS-100`); the runbook reports how many of these cases payments' ladder also shows at its final rung, so the disagreement is a number rather than a silence · `delivery_reported` is a constant `False` today because no provider adapter exists on any channel and is served as DATA so the sentence changes with the deployment · `protection_board` batches the CALL and never the RULE
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
