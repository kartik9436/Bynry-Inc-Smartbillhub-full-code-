# ── Trace ──────────────────────────────────────────────
# Story:    US-MET-002 (S15 unit detail — the Account tab) · CR-089 wave I
#           Screens: S15 (PRM-03, Account tab)
# Rules:    BR-CUS-039 (a protection forbids disconnection) · BR-PAY-013 (the
#           cash-only / no-autopay privilege sanction at the tenant's Nth
#           bounce) · BR-CUS-059 (autopay is the customer's ELECTION) ·
#           BR-CUS-035 (account notes, pinned first) · BR-CUS-094 (the seven
#           customer classes) · BR-CUS-050 (the deposit and its receipt date) ·
#           CLAUDE.md hard rule 2 (money stored 4 decimals, displayed 2 — this
#           file serves DECIMAL STRINGS at the stored scale and rounds nothing)
# Tests:    06-backend/tests/test_cr089_i_unit_account_facts.py
# Impacts:  apps/metering/seams.py (`account_facts_for`) · apps/metering/
#           unit_account.py · 07-frontend/src/features/metering/UnitDetailPage
#           .tsx (`UnitAccountTab`)
# ───────────────────────────────────────────────────────
"""**EVERYTHING THE UNIT'S ACCOUNT TAB NEEDS, GATHERED WHERE THE ROWS LIVE.**

`DEF-CUS-4691` and `DEF-CUS-4692`, and the Product Owner's sentence that raised
both — *"Unit → Account - can you please check - what all other infrmation we
can display about accounts here - and expand the details"*.

WHY THIS FILE IS IN `customers` AND NOT IN `metering`
------------------------------------------------------
The tab is metering's screen and every fact on it is customers' row. B1/B8:
metering never touches another module's ORM, so metering resolves ONE callable —
this one — through `apps/metering/seams.py`, and customers does the reading.
Nothing here writes; it is a pure read, and `apps/metering` could not make it a
write if it tried (there is no write to call).

WHAT IT REFUSES TO DO, WHICH IS THE HALF WORTH READING
-------------------------------------------------------
**An absence is a first-class answer with a REASON, never a zero.** Three of the
five money states below live in modules this one reads through a seam
(`payment_plans` and `account_collection_state` are payments'; `account_budget_
status` is billing's), and every one of those seams answers `None` when the
owning module cannot be reached. `None` is carried to the screen as *"could not
be read"* and is NEVER collapsed into *"none running"* — that is `DEF-127` word
for word, and `seams.payment_plans_for`'s own docstring says it: *"a screen that
renders 'no payment plan' over a plan it simply could not fetch tells a clerk
the customer never agreed one."*

**`credit_tier` IS SERVED WITH ITS PROVENANCE AND THE SCREEN DOES NOT DRAW IT.**
`Account.credit_tier` is a COMPUTED CACHE (`BR-CUS-058`) whose rules live in the
unbuilt `credit_tier_rules`, so nothing in this product computes it. A demo row
carrying `B` would render as a grade the utility awarded, which nobody did. It
travels with `computed: False` so a future reader meets the reason rather than
the value.

**AUTOPAY IS NEVER READ OFF ONE COLUMN.** `apps.payments.autopay.is_enrolled` is
the ONE place that reads the election and the sanction together, and this file
calls it rather than re-implementing `autopay and not cash_only`. `DEF-070` is
what the second implementation cost, and the customer portal shipped the same
fault again months later.
"""

from __future__ import annotations

from datetime import date
from typing import Any

from . import models, seams, selectors
from .disconnects import (
    PROTECTION_MEDICAL,
    PROTECTION_MORATORIUM,
    PROTECTION_PLAN,
    protections_for,
)

# ════════════════════════════════════════════════════════════════════════════
# THE CODES THIS READ PUBLISHES — greppable from the screen that renders them
# ════════════════════════════════════════════════════════════════════════════
#
# ⚠ **STRINGS, NOT SENTENCES.** `G32` requires every refusal a clerk reads to
# resolve to a catalogue key, and this module may not write catalogue copy; so
# the screen owns the words and this owns the STATE. A sentence typed here
# would also be a sentence in one language on an eleven-language product.

#: Autopay, read as one answer rather than as two columns (`I3`).
AUTOPAY_TAKEN = "taken"  # elected, not cash-only → money will be drafted
AUTOPAY_HELD_CASH_ONLY = "held_cash_only"  # elected AND cash-only → nothing is drafted
AUTOPAY_NOT_ELECTED = "not_elected"  # never asked for
AUTOPAY_NOT_ELECTED_CASH_ONLY = "not_elected_and_cash_only"  # both facts, both true
AUTOPAY_UNREADABLE = "unreadable"  # payments could not answer — NOT "off"

#: The three states every money row below can be in. `UNREADABLE` is the one
#: that exists because `DEF-127` happened.
STATE_NONE = "none"
STATE_SOME = "some"
STATE_UNREADABLE = "unreadable"

#: Why `credit_tier` is served and not drawn. See the module docstring.
CREDIT_TIER_NOT_COMPUTED = "credit_tier_rules_unbuilt"


def _account_type_block(account: models.Account) -> dict[str, Any] | None:
    """`I2` — the customer CLASS, which since `CR-087` selects a base charge.

    Residential and commercial can be `$8.00` and `$34.00` for the same meter
    size, so this is not a label: it is the fact that decides which figure the
    plan applies. The tab says so in one clause beside the value.

    The tenant's own sub-type rides with it when there is one (`BR-CUS-067`'s
    two-level tree), because a clerk who has both wants both.
    """
    account_type = account.account_type
    if account_type is None:  # pragma: no cover — the column is NOT NULL
        return None
    subtype = account.account_subtype
    return {
        "code": account_type.code,
        "name": account_type.name,
        # `BR-CUS-094`: a legacy code still prices and still filters; it is only
        # unselectable on new records. The screen says nothing about it, but a
        # reader of this payload should not have to go and look it up.
        "legacy": bool(account_type.legacy),
        "subtype_code": subtype.code if subtype is not None else None,
        "subtype_name": subtype.name if subtype is not None else None,
    }


def _protection_block(account_id: Any, *, as_of: date) -> dict[str, Any]:
    """`I1` — every protection standing on this account, in force first.

    ⚠ **`set_by` IS A ROLE AND NOT A PERSON, AND THE SCREEN MUST NOT PRINT IT
    AS A NAME.** The column defaults to `tenant` and the moratorium's own
    default is `regulator` (`B18` §5.8.3: *"a date window set by the regulator,
    not by the tenant"*). `CR-089`'s worked example reads *"set by D. Whitfield"*
    — that is a PERSON, and no column in `account_protections` holds one. Who
    typed it lives in `audit_log`, which is pruned. So the payload carries the
    role verbatim and the screen renders the role; inventing a name would be a
    fabricated attribution on the record that stops a disconnection.

    `disconnection_held` is the whole point of the banner: it is TRUE when any
    protection is in force, and it is what any disconnection control on this
    screen must be held by.
    """
    rows = protections_for(account_id, as_of=as_of)
    in_force = [row for row in rows if row["in_force"]]
    return {
        "in_force": [_protection_row(row) for row in in_force],
        "lapsed": [_protection_row(row) for row in rows if not row["in_force"]],
        # A protection FORBIDS disconnection (`BR-CUS-039`). One in force is
        # enough; the banner names them all.
        "disconnection_held": bool(in_force),
        "kinds_in_force": tuple(sorted({row["kind"] for row in in_force})),
    }


#: The three kinds, exported so the screen's catalogue keys and this module
#: cannot drift on spelling. `disconnects.PROTECTIONS` is the source.
PROTECTION_KINDS = (PROTECTION_MEDICAL, PROTECTION_PLAN, PROTECTION_MORATORIUM)


def _protection_row(row: dict[str, Any]) -> dict[str, Any]:
    """One protection, dated, with the ROLE that set it and nothing invented."""
    return {
        "id": row["id"],
        "kind": row["kind"],
        "lifetime": row["lifetime"],
        "in_force": row["in_force"],
        "effective_from": row["effective_from"],
        "expires_on": row["expires_on"],
        "lifted_on": row["lifted_on"],
        # `tenant` | `regulator` — a ROLE. See `_protection_block`.
        "set_by": row["set_by"],
    }


def _autopay_block(account: models.Account) -> dict[str, Any]:
    """`I3` — autopay and cash-only read TOGETHER, which is the whole task.

    ⚠ **`autopay: true` ALONE IS THE WRONG ANSWER AND THIS PRODUCT HAS SHIPPED
    IT TWICE.** `DEF-070`: the sanction column existed with nothing reading it,
    so a second bounce did nothing and the customer's card kept being scheduled.
    The customer portal then drew *"Autopay on"* over an account under the
    sanction, and it cost a wave to find.

    `apps.payments.autopay.is_enrolled` is the ONE reader of the pair. It is
    resolved BY NAME (never imported), and when payments cannot answer the state
    is `unreadable` — never `off`, because *"we could not tell"* and *"they are
    not enrolled"* are different statements and only the second one silently
    stops an intent from ever being recorded (that sentence is `is_enrolled`'s
    own).
    """
    elected = bool(account.autopay)
    cash_only = bool(account.cash_only_no_autopay)
    will_be_taken: bool | None = None
    enrolled = seams.resolve("payments", "is_enrolled", kind="autopay")
    if enrolled is not None:
        try:
            will_be_taken = bool(enrolled(account.pk))
        except Exception:  # pragma: no cover — a read must never break the tab
            will_be_taken = None

    if will_be_taken is None:
        reading = AUTOPAY_UNREADABLE
    elif will_be_taken:
        reading = AUTOPAY_TAKEN
    elif elected and cash_only:
        reading = AUTOPAY_HELD_CASH_ONLY
    elif cash_only:
        reading = AUTOPAY_NOT_ELECTED_CASH_ONLY
    else:
        reading = AUTOPAY_NOT_ELECTED

    return {
        # The customer's own election (`BR-CUS-059`) — nothing here un-asks it.
        "elected": elected,
        # `BR-PAY-013`'s privilege sanction. J12 step 6: no rule auto-clears it.
        "cash_only": cash_only,
        "nsf_count": int(account.nsf_count or 0),
        # The tenant's N. `None` means the setting could not be read and is
        # never read as 2 — `seams.nsf_privilege_threshold`'s own rule.
        "nsf_threshold": seams.nsf_privilege_threshold(),
        "will_be_taken": will_be_taken,
        "reading": reading,
    }


def _payment_plan_block(account_id: Any, *, as_of: date) -> dict[str, Any]:
    """`I4` row 1 — *Payment plan · None running*, stated rather than omitted.

    `seams.payment_plans_for` answers `None` when payments cannot be read, and
    that `None` travels here as `unreadable`. See the module docstring.
    """
    plans = seams.payment_plans_for(account_id, as_of=as_of)
    if plans is None:
        return {"state": STATE_UNREADABLE, "count": None, "running": None}
    # A plan is RUNNING when payments says its status is active. The vocabulary
    # is payments' and is read off the row rather than re-declared here.
    running = [plan for plan in plans if str(plan.get("status") or "").lower() == "active"]
    return {
        "state": STATE_SOME if running else STATE_NONE,
        "count": len(plans),
        "running": len(running),
        "reference": str(running[0].get("id")) if running else None,
    }


def _budget_block(account_id: Any) -> dict[str, Any]:
    """`I4` row 2 — *Budget billing · Not enrolled*.

    `account_budget_status` is BILLING's table. The read is resolved by name
    through `seams.budget_enrolment_for`, which answers `None` when billing
    cannot be reached; `None` is `unreadable` and never *"not enrolled"*.
    """
    enrolment = seams.budget_enrolment_for(account_id)
    if enrolment is None:
        return {"state": STATE_UNREADABLE, "level": None, "currency": None, "enrolled_on": None}
    if not enrolment.get("enrolled"):
        return {"state": STATE_NONE, "level": None, "currency": None, "enrolled_on": None}
    return {
        "state": STATE_SOME,
        # A DECIMAL STRING at the stored scale — hard rule 2. Rounding happens
        # at display and `MoneyCell` is the one place that does it.
        "level": enrolment.get("level"),
        "currency": enrolment.get("currency"),
        "enrolled_on": enrolment.get("enrolled_on"),
        "status": enrolment.get("status"),
    }


def _collections_block(account_id: Any, *, as_of: date) -> dict[str, Any]:
    """`I4` row 3 — *Collections · Not in collections*.

    `account_collection_state` is PAYMENTS' table, one row per account, and an
    account that has never been chased simply has no row. **No row is a real
    answer** (`not in collections`); a read that could not be made is not.
    """
    state = seams.collection_state_for(account_id, as_of=as_of)
    if state is None:
        return {"state": STATE_UNREADABLE, "tier": None, "paused_reason": None}
    if not state.get("on_the_ladder"):
        # ⚠ **`paused_reason` IS NOT CARRIED ON THIS BRANCH.** Payments answers
        # `no_live_plan` for an account nobody has ever chased — true in its own
        # vocabulary, and read on this tab it would say *"collections is paused
        # because there is no payment plan"* about an account that is not in
        # collections at all. A reason for a state the row is not in is worse
        # than no reason.
        return {"state": STATE_NONE, "tier": None, "paused_reason": None}
    return {
        "state": STATE_SOME,
        "tier": state.get("tier"),
        "tier_sent_on": state.get("tier_sent_on"),
        "next_step_due": state.get("next_step_due"),
        "paused_reason": state.get("paused_reason"),
    }


def _deposit_block(account: models.Account) -> dict[str, Any]:
    """`I4` row 6 — *Deposit held · 150.00 · taken 1 Jun 2026* (`BR-CUS-050`).

    A DECIMAL STRING at the stored scale, with its currency partner, and a zero
    is a real held-nothing rather than an absence. `deposit_received_on` is NULL
    on an account that has never held one, and NULL is drawn as an absence — the
    date a deposit was taken is what `BR-CUS-057`'s interest clock runs from, so
    a made-up one would be money.
    """
    # ⚠ **NOT `account.deposit_on_file or 0`.** `Decimal("0.000000")` is FALSY,
    # so the `or` substituted the INT zero and this row served `"0"` where every
    # other money string in the product serves `"0.000000"`. Found in the first
    # probe against live data, not by a test — nothing in this repo compares the
    # SCALE of a money string, only its value.
    held = account.deposit_on_file if account.deposit_on_file is not None else 0
    return {
        "held": str(held),
        "currency": account.currency,
        "received_on": account.deposit_received_on,
        "any": bool(held),
    }


def _tax_exemption_block(account: models.Account) -> dict[str, Any]:
    """`I4` row 5 — *Tax exemption · None claimed*.

    ⚠ **A LIVE PER-TAX CERTIFICATE IS A CLAIM TOO (`DEF-CUS-9774`).** PO ruling
    (A), 2026-10-05: a move-in's certificate removes only the tax it names and
    leaves `accounts.tax_exempt` false, so reading the blanket flag alone said
    *None claimed* for a church the bill run was exempting. The blanket
    exemption still wins where it is set; otherwise the first live certificate
    (rating's row, through the seam) answers."""
    if account.tax_exempt:
        return {
            "claimed": True,
            "reference": account.tax_exempt_ref,
            "expires_on": account.tax_exempt_expires,
        }
    live = [
        row for row in seams.account_tax_exemptions(account.pk) if row.get("state") == "live"
    ]
    if live:
        return {
            "claimed": True,
            "reference": live[0].get("certificate_ref"),
            "expires_on": live[0].get("expires_on"),
        }
    return {"claimed": False, "reference": account.tax_exempt_ref, "expires_on": None}


def _reach_block(account: models.Account) -> dict[str, Any]:
    """How the utility reaches this customer — `DEF-CUS-4692`'s other columns.

    ⚠ **`paperless` AND `sms_reminders` ONLY EVER ADD A CHANNEL.** `BR-BIL-036`
    (PO 2026-08-10): print is the FLOOR, applied inside `apps/notifications`
    where no writer can forget it, so a paperless account still gets its printed
    bill. The screen says *"and by post"* for that reason; it is not decoration.

    ⚠ **`bad_address` IS A FACT ABOUT POST ON AN ACCOUNT WHOSE ADDRESS IS
    WALKED FROM THE BUILDING** (`BR-MET-1161`). It is the one flag here a clerk
    standing on a unit can act on, so it travels first.
    """
    return {
        "bad_address": bool(account.bad_address),
        "paperless": bool(account.paperless),
        "sms_reminders": bool(account.sms_reminders),
        # `BR-CUS-064` — a tag like `es-MX`, or NULL for *"nobody has asked"*.
        "preferred_language": account.preferred_language,
    }


def account_facts(account_id: Any, *, as_of: date) -> dict[str, Any]:
    """The whole Account tab, in one read, for ONE account.

    `as_of` is REQUIRED and has no default — `BR-TEN-043` and gate `G6`: a
    protection that expires today must resolve against the tenant's business
    date and never against this process's wall clock.

    404s through `selectors.account_or_404` before anything else is read, so a
    foreign or unknown id is a refusal rather than an empty tab that would read
    as *"this account has nothing on it"*.
    """
    account = selectors.account_or_404(account_id)
    return {
        "account_id": str(account.pk),
        "account_no": account.account_no,
        "as_of": as_of,
        "protections": _protection_block(account.pk, as_of=as_of),
        "customer_class": _account_type_block(account),
        "autopay": _autopay_block(account),
        "payment_plan": _payment_plan_block(account.pk, as_of=as_of),
        "budget_billing": _budget_block(account.pk),
        "collections": _collections_block(account.pk, as_of=as_of),
        "bounced_payments": {"count": int(account.nsf_count or 0)},
        "tax_exemption": _tax_exemption_block(account),
        "deposit": _deposit_block(account),
        "notes": selectors.account_notes(account.pk),
        "reach": _reach_block(account),
        # The utility's OWN reference from the system they migrated off
        # (`BR-CUS-172`). NOT a database id, so `B14` rule 31 does not reach it
        # — it is the number a clerk reads out of the old ledger.
        "external_ref": account.external_ref,
        # Served WITH its provenance and deliberately not drawn. See the module
        # docstring: nothing in this product computes it.
        "credit_tier": {
            "value": account.credit_tier,
            "computed": False,
            "why": CREDIT_TIER_NOT_COMPUTED,
        },
    }



# ════════════════════════════════════════════════════════════════════════════
# THE WHOLE TAB, KEYED BY THE UNIT — what `apps/metering` resolves by name
# ════════════════════════════════════════════════════════════════════════════
#: Why there is no account to show. Two DIFFERENT sentences on screen, and the
#: difference is the point of `CR-089`'s vacant-unit rule.
NO_ACCOUNT_VACANT = "vacant"
NO_ACCOUNT_UNREADABLE = "owner_account_unreadable"


def owner_account_for_unit(unit_id: Any) -> dict[str, Any] | None:
    """The OWNER's account covering this unit — `BR-CUS-068`'s master account.

    `CR-089`: *"a vacant unit shows no account: the tab says base charges bill
    to the owner, NAMES the owner's account and links to it, rather than an
    empty table. A common area is always the owner's account."*

    ⚠ **COVERAGE IS READ THROUGH THE SERVICE AGREEMENTS, NOT THROUGH
    `accounts.unit_id`.** `selectors.master_account_covering_unit` says why in
    full: a master row ANCHORS on one common-area unit and covers the rest
    through open agreements on their service points, so the anchor test would
    miss every covered unit but one. Re-implementing it here would be a second
    answer to *whose account pays for this unit*, on a bill.
    """
    row = selectors.master_account_covering_unit(unit_id)
    if row is None:
        return None
    return {
        "id": str(row.pk),
        "account_no": row.account_no,
        "name": selectors.primary_contact_name(row),
        "kind": row.kind,
        "status_name": row.status.name,
    }


def unit_account(unit_id: Any, *, as_of: date) -> dict[str, Any]:
    """THE READ `apps/metering/seams.py` RESOLVES — the tab, in one call.

    Three shapes, and they are three different sentences on the screen:

      * **occupied** — `account` is the row S17 already serves for it (the SAME
        `selectors.account_row`, so the balance on this tab and the balance on
        the accounts list cannot be two different numbers), and `facts` is
        everything hanging off it.
      * **vacant** — no account. `owner_account` names the party the base
        charges go to, with its number, so the tab can link there instead of
        drawing an empty table.
      * **the owner cannot be named either** — `owner_account` is null and the
        screen says the owner is not recorded rather than implying there is
        nobody to bill.

    ⚠ **"OCCUPIES" IS `selectors.occupying_accounts_for_unit`'S DEFINITION AND
    NOT `closed_at IS NULL`.** It keys off the status's BEHAVIOUR CLASS
    (`BR-CUS-055`), so a draft account does not occupy and a closed one does
    not either, whatever a tenant has renamed them to. The front end's own
    `currentAccount` helper picks the newest row with no end date, which is the
    same account in every ordinary case and is NOT the same rule; the server's
    answer is the one this tab now renders, because it is the one billing uses.
    """
    account = (
        selectors.occupying_accounts_for_unit(unit_id).order_by("created_at", "id").first()
    )
    if account is None:
        owner = owner_account_for_unit(unit_id)
        return {
            "unit_id": str(unit_id),
            "account": None,
            "facts": None,
            "no_account_reason": NO_ACCOUNT_VACANT,
            "owner_account": owner,
        }
    return {
        "unit_id": str(unit_id),
        "account": selectors.account_row(account),
        "facts": account_facts(account.pk, as_of=as_of),
        "no_account_reason": None,
        "owner_account": None,
    }


# ── Lifecycle ─────────────────────────────────────────────
# packet: CR-089 wave I (I1–I5) · DEF-CUS-4691 · DEF-CUS-4692 · PUJ-36..PUJ-40
# generated: 2026-09-08 by the CR-089 wave I build lane
# checklist: A✔ B=n/a C✔ D=n/a E✔(apps/metering/unit_account.py reads it through the seam) F✔ G✔ H=n/a
# gates: pytest 06-backend/tests/test_cr089_i_unit_account_facts.py · G6 (as_of is required) · G78 n/a (customers, not work)
# exceptions: E3 `credit_tier` is served and NOT rendered — BR-CUS-058's rules are unbuilt, so a value on screen would be a grade nobody awarded · E3 `set_by` is a ROLE (`tenant`/`regulator`) and the screen renders the role; CR-089's worked example names a PERSON and no column holds one · E3 the three seam reads answer `None` for *unreadable* and it is never collapsed into *none* (DEF-127)
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
