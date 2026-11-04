# ── Trace ──────────────────────────────────────────────
# Story:    US-RBS-031 (EP-RBS-05) — CR-075 wave S: runbook 19, *Data hygiene* —
#           seven read steps over the whole utility, grouped by what each
#           finding will break.
# Rules:    BR-RBS-002 (a Check is CONSTRUCTED with no writer) · BR-RBS-010
#           (every record states the rule that decided it, in words a clerk can
#           read) · BR-RBS-011 (a failure names its fix route) · BR-RBS-019 (the
#           declared unit of work) · BR-RBS-020 (the report is composed at close
#           and frozen) · BR-RBS-021 (twelve blocks) · BR-RBS-022 (a work item
#           is the ENGINE's act, never a port) · BR-RBS-023 (a step declares its
#           mode) · BR-RBS-024 (one category from the fixed sixteen) ·
#           BR-RBS-035 (a count per outcome for what has no row) · BR-RBS-039
#           (every foreign read through a seam this module owns) · BR-TEN-056 /
#           BR-TEN-057 (sample records are tagged on the owning row) ·
#           BR-CUS-089 (a phone is encrypted with a blind index) ·
#           CLAUDE.md hard rule 8 (an address lives on `premises`) ·
#           hard-won law 7 (a declared blind spot carries a NUMBER) ·
#           B14 rules 31, 32
# Tests:    06-backend/tests/test_us_rbs_031_data_hygiene.py ·
#           06-backend/tests/test_rbs_check_runbooks_pg.py (PostgreSQL only)
# Impacts:  apps/runbooks/definitions/__init__.py (the one line that registers
#           it) · apps/runbooks/seams/customers_seam.py ·
#           apps/runbooks/seams/metering_seam.py · apps/customers/selectors.py
#           · apps/metering/selectors.py · apps/assets/selectors.py
#           · 04-docs/05-modules/17-runbooks/11-catalogue/RB-119-data-hygiene.md
# ───────────────────────────────────────────────────────
"""Runbook 19 — **Data hygiene**.

*What in our records will trip the other runbooks?* Duplicate customers,
premises with no meter, accounts nobody can reach. `RB-119`'s own sentence:
**the runbook that makes the others honest.**

⚠ **IT IS GROUPED BY CONSEQUENCE AND NEVER BY TABLE**, which is the card's
design note and the whole of why it is useful: a clerk fixes *"dunning will miss
108 people"* and never *"null contact rows"*. Every group therefore names the
runbook or the job it breaks, and carries the screen that fixes it
(`BR-RBS-011`).

THE ONE NUMBER THAT MATTERS MOST IS NOT A FINDING
--------------------------------------------------
*Reachable by text* is a TILE rather than a group, because it is the number that
decides whether the storm runbook works at all, and a utility should see it
every month rather than discover it in a storm. It is a ratio — *1,350 of
2,907* — and is drawn as one, because a bare *1,350* answers nothing.

WHY THE SAMPLE EXCLUSION IS NOT A `Guard` HERE, STATED RATHER THAN INFERRED
----------------------------------------------------------------------------
`RB-119`'s scope row reads **Never include: Sample**, and every other runbook
that carries that row walks a set of ROWS — 23 accounts, 2,862 premises — where
`BR-RBS-012`'s guard is exactly right: the subject stays pinned, the guard is
absolute, the count is visible and `RBS-004.4` draws the control disabled WITH
its reason.

**This runbook's subject is the TENANT and there is exactly one of it.** A
`Guard` over that subject could only ever return `False`, which is hard-won law
7's *structurally incapable of failing* — a check that cannot fire, drawn on a
screen as though it protected something. So the exclusion is applied inside each
step's read and **every step reports how many rows it left out beside how many
it looked at**, which is the same law's other half: *a declared blind spot with
no NUMBER attached is indistinguishable from an empty one.*

⚠ **ON A DEMO UTILITY THAT IS ALMOST EVERYTHING, AND THE SCREEN HAS TO SAY SO.**
`BR-TEN-056` fills a new tenant with realistic, deletable sample records so an
operator does not meet eleven empty states. On the seeded utility that is 48 of
49 customers, 73 of 79 premises and 126 of 137 meters — so a run that reported
*"0 items"* with no second number would tell a new operator their records are
clean when the truth is that this check has almost nothing of their own to look
at yet.

WHAT THIS RUNBOOK CANNOT SEE, EACH WITH ITS FIGURE
---------------------------------------------------
1. **A duplicate is an EQUALITY match on a blind index, never a similarity
   one.** `RB-119`'s own stated absence: *"phone numbers are encrypted with a
   blind index, so 'same phone' here means a blind-index match. Fuzzy phone
   matching is not possible on an encrypted column."* Two spellings of one
   number are two customers here and always will be. The count of customers
   carrying each token travels, so *"0 duplicates"* over a tenant holding no
   tokens at all cannot read as a clean result.
2. **Nothing standardises an address in this product.** `RB-119` step 6 asks for
   *addresses that failed standardisation*; there is no such flag and no address
   service is connected (`13-selector-inventory.md` **S-8**, ABSENT). What this
   step CAN see is an address `premises` holds incompletely — no city, no state
   or no postal code — and it says that in those words rather than claiming a
   standardiser refused them. Recorded as a judgment in the decision log.
3. **Consent to text is not recorded as consent.** The card's largest group is
   *"No mobile, or no consent"*; `customers` holds `sms_reminders` on the
   account and a phone on the contact, and neither is a consent record with a
   date. So this counts **no mobile on file** and **not opted in to texts**
   separately and names them both, rather than adding them into one number whose
   two halves have different fixes.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from apps.runbooks import models
from apps.runbooks.contract import (
    MODE_SET,
    PARAM_ENUM,
    PARAM_REF_SETTING,
    PARAM_TOGGLE,
    Block,
    Parameter,
    RunbookDefinition,
    Step,
    SubjectRef,
)
from apps.runbooks.seams import customers_seam, metering_seam, tenancy_seam

KEY = "data_hygiene"

# ── the seven steps, in the card's own order ──────────────────────────────

STEP_DUPLICATES = "duplicate_customers"
STEP_PREMISES_NO_METER = "premises_with_no_meter"
STEP_METERS_NO_PREMISE = "meters_with_no_premise"
STEP_ACCOUNTS_NO_UNIT = "accounts_with_no_unit"
STEP_NO_CHANNEL = "accounts_with_no_contact_channel"
STEP_ADDRESSES = "addresses_that_failed_standardisation"
STEP_GROUP = "group_by_what_it_breaks"

STEP_LABELS = {
    STEP_DUPLICATES: "Duplicate customers",
    STEP_PREMISES_NO_METER: "Premises with no meter",
    STEP_METERS_NO_PREMISE: "Meters with no premise",
    STEP_ACCOUNTS_NO_UNIT: "Accounts with no unit",
    STEP_NO_CHANNEL: "Accounts with no contact channel",
    STEP_ADDRESSES: "Addresses that failed standardisation",
    STEP_GROUP: "Group by what each will break",
}

# ── fix routes ────────────────────────────────────────────────────────────
#
# ⚠ **EVERY ONE IS A PATH THIS PRODUCT ACTUALLY MOUNTS**, verified against
# `07-frontend/src/routing/` on 2026-09-07. Tenant-relative: the shell prefixes
# `/:tenant/` through `toHref` (`DEF-RBS-4329` — a route written absolute here
# resolved against the RUN's own URL and every Fix link landed on *"this screen
# is not built yet"*).
FIX_CUSTOMERS = "customers"
FIX_ACCOUNTS = "accounts"
FIX_PREMISES = "premises"
FIX_ASSETS = "assets"

# ── the groups, named by CONSEQUENCE (`RB-119` step 7) ────────────────────
#
# ⚠ **THE ORDER IS THE CARD'S AND IT IS NOT A SORT.** *"The groups are named by
# consequence — the storm text, dunning, runbook 3 — so the fix order is obvious
# without anyone ranking it."* A runbook that re-sorted these by count would put
# whatever is largest this month at the top and lose that.
GROUP_NO_MOBILE = "no_mobile_or_not_opted_in"
GROUP_NO_CHANNEL = "no_contact_channel_at_all"
GROUP_DUPLICATES = "duplicate_customers"
GROUP_PREMISES_NO_METER = "premises_with_no_meter"
GROUP_ADDRESSES = "addresses_not_standardised"
GROUP_METERS_NO_PREMISE = "meters_with_no_premise"
GROUP_ACCOUNTS_NO_UNIT = "accounts_with_no_unit"

GROUP_ORDER = (
    GROUP_NO_MOBILE,
    GROUP_NO_CHANNEL,
    GROUP_DUPLICATES,
    GROUP_PREMISES_NO_METER,
    GROUP_ADDRESSES,
    GROUP_METERS_NO_PREMISE,
    GROUP_ACCOUNTS_NO_UNIT,
)

#: What each group BREAKS, and where a clerk goes. Both halves are the card's.
#: ⚠ No rule id and no runbook KEY appears in either — B14 rule 32 keeps an
#: internal code out of clerk-facing copy, so *"runbook 3"* is written as the
#: job it is: *Billing readiness*.
GROUP_FACTS: dict[str, dict[str, str]] = {
    GROUP_NO_MOBILE: {
        "label": "No mobile, or not opted in",
        "breaks": "The storm text · leak alerts",
        "fix_label": "Ask on the bill and portal →",
        "fix_route": FIX_ACCOUNTS,
    },
    GROUP_NO_CHANNEL: {
        "label": "No contact channel at all",
        "breaks": "Dunning · every notice",
        "fix_label": "Add a contact →",
        "fix_route": FIX_ACCOUNTS,
    },
    GROUP_DUPLICATES: {
        "label": "Duplicate customers",
        "breaks": "Deposits carried twice · two logins",
        "fix_label": "Merge →",
        "fix_route": FIX_CUSTOMERS,
    },
    GROUP_PREMISES_NO_METER: {
        "label": "Premises with no meter",
        "breaks": "Billing readiness",
        "fix_label": "Assign a meter →",
        "fix_route": FIX_PREMISES,
    },
    GROUP_ADDRESSES: {
        "label": "Addresses not standardised",
        "breaks": "Post · certified letters",
        "fix_label": "Fix address →",
        "fix_route": FIX_PREMISES,
    },
    GROUP_METERS_NO_PREMISE: {
        "label": "Meters with no premise",
        "breaks": "Reads land nowhere",
        "fix_label": "Attach to premise →",
        "fix_route": FIX_ASSETS,
    },
    GROUP_ACCOUNTS_NO_UNIT: {
        "label": "Accounts with no unit",
        "breaks": "Billing readiness · every bill",
        "fix_label": "Attach to a unit →",
        "fix_route": FIX_ACCOUNTS,
    },
}

#: Which groups are ORPHANS — the tile the card counts. ⚠ **THE CARD'S OWN
#: EXAMPLE TILE COUNTS TWO OF THE THREE** (20 premises + 3 meters = 23) while
#: its *Orphan means* row names three — *Premise · no meter / Meter · no premise
#: / Account · no unit*. The row is the definition and the tile is one month's
#: illustration, so this counts THREE and the breakdown lists all three, which
#: is what keeps the tile and the table adding up (`RB-119`: *"the tables on the
#: screens add up to them, so moving one is still an error"*).
ORPHAN_GROUPS = (GROUP_PREMISES_NO_METER, GROUP_METERS_NO_PREMISE, GROUP_ACCOUNTS_NO_UNIT)


@dataclass
class _StepResult:
    """What every step returns — what it found, and what it LOOKED AT.

    `checked` is not decoration. A step reporting nothing because the utility's
    records are clean and a step reporting nothing because every row it can see
    is sample data are the same sentence with very different meanings, and a
    check whose output cannot tell a reader which is which is worse than no
    check at all (hard-won law 7).
    """

    items: list[dict[str, Any]] = field(default_factory=list)
    checked: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return {"reached": True, "items": list(self.items), "checked": dict(self.checked)}


def _items(ctx, step: str) -> list[dict[str, Any]]:
    return list((ctx.set_results.get(step) or {}).get("items") or [])


def _checked(view, step: str) -> dict[str, Any]:
    return dict((view.set_results.get(step) or {}).get("checked") or {})


def _finding(
    *,
    group: str,
    label: str,
    detail: str,
    decided_by_rule: str,
) -> dict[str, Any]:
    """One thing to fix, in the shape every group row is built from.

    ⚠ **NO DATABASE ID IS A VISIBLE VALUE** (B14 rule 31): `label` is the
    premises number, the account number or the customer's name — what a clerk
    reads — and the handle a screen would need to open the row is deliberately
    NOT carried, because nothing in this report draws one and a field that
    exists gets rendered eventually.
    """
    facts = GROUP_FACTS[group]
    return {
        "group": group,
        "label": label,
        "detail": detail,
        "breaks": facts["breaks"],
        "fix_route": facts["fix_route"],
        "fix_label": facts["fix_label"],
        "decided_by_rule": decided_by_rule,
    }


# ── step 1 · duplicate customers ──────────────────────────────────────────


def step_duplicate_customers(ctx, subjects) -> dict[str, Any]:
    """1 · Same phone, same tax id or same email under two names.

    ⚠ **EQUALITY ON A BLIND INDEX, NEVER SIMILARITY** (`BR-CUS-089`, and the
    card's own stated absence). `555-0100` and `(555) 0100` are two tokens and
    therefore two customers, for ever, and no amount of care in this runbook
    changes that — it is a property of an encrypted column.

    ⚠ **THE NUMBER BESIDE THE BLIND SPOT.** How many customers carry a phone
    token and how many carry a tax-id token both travel, so a tenant that has
    imported neither cannot read *"no duplicates"* as a clean bill of health.
    """
    answer = customers_seam.duplicate_customer_groups()
    groups = list(answer.get("groups") or [])
    live = [
        one
        for one in groups
        # A sample customer duplicated by another sample customer is the seed's
        # own doing and not the utility's data — see the module docstring for
        # why this is a filter here rather than a `Guard`.
        if not all(bool(member.get("is_sample")) for member in one.get("customers") or [])
    ]
    excluded = len(groups) - len(live)
    items = [
        _finding(
            group=GROUP_DUPLICATES,
            label=" · ".join(str(member.get("name") or "") for member in one["customers"]),
            detail=f"Same {one['matched_on'].replace('_', ' ')} under {one['count']} names.",
            decided_by_rule="Two customers sharing a phone, a tax id or an email are one person",
        )
        for one in live
    ]
    return _StepResult(
        items=items,
        checked={
            "customers_checked": answer.get("customers_checked", 0),
            "groups_found": len(groups),
            "groups_that_are_all_sample_records": excluded,
            # Hard-won law 7 — what this check could not see, with its number.
            "customers_with_a_phone_token": answer.get("customers_with_a_phone_token", 0),
            "customers_with_a_tax_id_token": answer.get("customers_with_a_tax_id_token", 0),
            "emails_checked": answer.get("emails_checked", 0),
            "matching_is": "equality on a blind index, never similarity",
        },
    ).as_dict()


# ── steps 2, 3 and 6 · one walk of the estate ─────────────────────────────


def _census(ctx) -> dict[str, Any]:
    """The chain, read ONCE per run and cached on the context.

    Steps 2, 3 and 6 are three questions about one walk — *premises with no
    meter*, *meters with no premise*, *addresses `premises` holds incompletely*
    — and asking metering three times would be three walks that can disagree
    about which premises are in scope inside a single run.
    """
    cached = ctx.set_results.get("_census")
    if cached is None:
        cached = metering_seam.premises_meter_census(include_sample=True)
        ctx.set_results["_census"] = cached
    return cached


def step_premises_with_no_meter(ctx, subjects) -> dict[str, Any]:
    """2 · A service point that cannot be read.

    ⚠ **A PREMISES WITH NO METER IS NOT THE SAME FAULT AS ONE WITH NO SERVICE
    POINT, AND BOTH COUNTS TRAVEL.** A premises nobody has connected yet is an
    ordinary state at a utility that is still building its estate; a premises
    with a service point and no meter is a connection that cannot be billed.
    Reporting one number for both would put a subdivision under construction on
    the same line as a live connection nobody can read.
    """
    census = _census(ctx)
    rows = list(census.get("premises") or [])
    live = [one for one in rows if not one.get("is_sample")]
    without = [one for one in live if not one.get("meters")]
    connected_but_unread = [one for one in without if one.get("service_points")]
    items = [
        _finding(
            group=GROUP_PREMISES_NO_METER,
            label=str(one.get("label") or ""),
            detail=(
                f"{len(one.get('service_points') or [])} service point(s) and no meter."
                if one.get("service_points")
                else "No service point and no meter."
            ),
            decided_by_rule="A premises with no meter cannot be read and cannot be billed",
        )
        for one in without
    ]
    return _StepResult(
        items=items,
        checked={
            "premises_checked": len(live),
            "premises_that_are_sample_records": len(rows) - len(live),
            "premises_with_no_meter": len(without),
            "of_those_with_a_service_point": len(connected_but_unread),
            # ⚠ `False` MEANS NOBODY COULD ANSWER, WHICH IS NOT `no meters`.
            "meters_answered": bool(census.get("meters_answered")),
        },
    ).as_dict()


def step_meters_with_no_premise(ctx, subjects) -> dict[str, Any]:
    """3 · A meter that cannot be billed — reads would land nowhere.

    ⚠ **A METER IN THE STORE ROOM IS NOT A FINDING AND ITS STATUS SAYS SO.**
    `BR-AST-005`'s `uninstalled` is the product's own word for a meter that
    legitimately stands on nothing, so those are counted separately and are not
    put on a clerk's list — a hygiene report that told a utility to attach its
    spare meters to premises would be ignored by the second month.
    """
    census = _census(ctx)
    orphans = list(census.get("meters_without_a_service_point") or [])
    live = [one for one in orphans if not one.get("is_sample")]
    in_stock = [one for one in live if str(one.get("status") or "") == "uninstalled"]
    stranded = [one for one in live if one not in in_stock]
    items = [
        _finding(
            group=GROUP_METERS_NO_PREMISE,
            label=str(one.get("asset_no") or ""),
            detail=f"Stands on no service point · {one.get('status') or 'no status'}.",
            decided_by_rule="A meter on no service point has nowhere to send its reads",
        )
        for one in stranded
    ]
    return _StepResult(
        items=items,
        checked={
            "meters_with_no_service_point": len(live),
            "meters_that_are_sample_records": len(orphans) - len(live),
            "in_stock_and_not_a_finding": len(in_stock),
            "meters_answered": bool(census.get("meters_answered")),
        },
    ).as_dict()


# ── step 4 · accounts with no unit ────────────────────────────────────────


def step_accounts_with_no_unit(ctx, subjects) -> dict[str, Any]:
    """4 · The chain break from runbook 1, re-checked.

    ⚠ **A MASTER ACCOUNT NAMES A PREMISES AND NO UNIT, LAWFULLY** (`BR-CUS-1010`
    — a Master Account is the OWNER'S account at an ADDRESS). A check that
    counted every account without a unit would report every master account in
    the utility as broken, every month, which is how a hygiene report teaches a
    clerk to ignore it. Only a `regular` account anchored to nothing is a
    finding, and the master count travels beside it.
    """
    anchors = customers_seam.account_anchors()
    live = [one for one in anchors if not one.get("is_sample")]
    masters = [one for one in live if str(one.get("kind")) != "regular"]
    broken = [
        one
        for one in live
        if str(one.get("kind")) == "regular" and not one.get("unit_id")
    ]
    items = [
        _finding(
            group=GROUP_ACCOUNTS_NO_UNIT,
            label=str(one.get("account_no") or ""),
            detail="Anchored to no unit, so nothing can be measured for it.",
            decided_by_rule="An account that bills for service names the unit it serves",
        )
        for one in broken
    ]
    return _StepResult(
        items=items,
        checked={
            "accounts_checked": len(live),
            "accounts_that_are_sample_records": len(anchors) - len(live),
            "master_accounts_anchored_to_a_premises": len(masters),
            "accounts_with_no_unit": len(broken),
        },
    ).as_dict()


# ── step 5 · accounts nobody can reach ────────────────────────────────────


def step_accounts_with_no_contact_channel(ctx, subjects) -> dict[str, Any]:
    """5 · Nobody can be told anything — and the text number the card asks for.

    `13-selector-inventory.md` **S-10**, answered by
    `customers.contact_channels_for`: an account whose entry has all three false
    is one.

    ⚠ **THREE DIFFERENT ABSENCES AND THEY ARE NOT ADDED TOGETHER.** *No channel
    at all* is dunning's problem; *no mobile* is the storm text's; *a mobile
    with no opt-in* is a consent question with a different fix. The card's own
    table keeps the first two apart, and the third is named here rather than
    folded into the second — see the module docstring's third blind spot.

    ⚠ **PRESENT MEANS ON FILE, NEVER WORKING.** Nothing in `customers` records
    that a channel stopped working (`DEF-RBS-4331`), so an account with a dead
    email address counts as reachable here and the wording says *on file*.
    """
    anchors = customers_seam.account_anchors()
    live = [one for one in anchors if not one.get("is_sample")]
    ids = [one["id"] for one in live]
    channels = customers_seam.contact_channels_for(ids)
    labels = {one["id"]: (one.get("account_no") or "") for one in live}
    opted_in = customers_seam.accounts_opted_in_to_text(ids)

    nothing: list[dict[str, Any]] = []
    no_mobile: list[dict[str, Any]] = []
    reachable_by_text = 0
    for account_id in ids:
        entry = channels.get(str(account_id)) or {}
        has_text = bool(entry.get("text"))
        if has_text and opted_in.get(str(account_id)):
            reachable_by_text += 1
        if not (entry.get("channels") or []):
            nothing.append(
                _finding(
                    group=GROUP_NO_CHANNEL,
                    label=str(labels.get(account_id) or ""),
                    detail="No email, no phone and no mailing address on file.",
                    decided_by_rule="An account with no channel on file cannot be sent anything",
                )
            )
            continue
        if not has_text:
            no_mobile.append(
                _finding(
                    group=GROUP_NO_MOBILE,
                    label=str(labels.get(account_id) or ""),
                    detail="No mobile number on file.",
                    decided_by_rule="A text needs a mobile number on file and an opt-in",
                )
            )
        elif not opted_in.get(str(account_id)):
            no_mobile.append(
                _finding(
                    group=GROUP_NO_MOBILE,
                    label=str(labels.get(account_id) or ""),
                    detail="Mobile on file · not opted in to texts.",
                    decided_by_rule="A text needs a mobile number on file and an opt-in",
                )
            )
    return _StepResult(
        items=nothing + no_mobile,
        checked={
            "accounts_checked": len(live),
            "accounts_that_are_sample_records": len(anchors) - len(live),
            "no_channel_at_all": len(nothing),
            "cannot_be_texted": len(no_mobile),
            "reachable_by_text": reachable_by_text,
            "channel_means": "on file, never known to be working",
        },
    ).as_dict()


# ── step 6 · addresses post will not arrive at ────────────────────────────


def step_addresses_that_failed_standardisation(ctx, subjects) -> dict[str, Any]:
    """6 · Post will not arrive — and **nothing here standardises an address**.

    ⚠ **THE CARD ASKS FOR A FLAG THIS PRODUCT DOES NOT HOLD**
    (`13-selector-inventory.md` **S-8**, ABSENT): no address service is
    connected and `premises` carries no `standardised` column, so there is no
    row anywhere saying a standardiser refused an address. Inventing that
    verdict would be a check reporting a judgment nobody made.

    **What is checked instead, and it is said in those words on the screen:** an
    address `premises` holds INCOMPLETELY — no city, no state or no postal code.
    A certified letter cannot be posted to one, which is the consequence the
    card's group is named for.

    ⚠ **`premises` IS THE ONE ADDRESS HOME** (hard rule 8, `BR-MET-1161`), so
    this walks premises and nothing else. An account, a route and a cycle have
    no address column to check.
    """
    census = _census(ctx)
    rows = [one for one in (census.get("premises") or []) if not one.get("is_sample")]
    items: list[dict[str, Any]] = []
    for one in rows:
        missing = [
            name
            for name, value in (
                ("city", one.get("city")),
                ("state", one.get("state")),
                ("postal code", one.get("postal_code")),
            )
            if not str(value or "").strip()
        ]
        if not missing:
            continue
        items.append(
            _finding(
                group=GROUP_ADDRESSES,
                label=str(one.get("label") or ""),
                detail="No " + ", no ".join(missing) + " on the premises.",
                decided_by_rule="A letter needs a city, a state and a postal code",
            )
        )
    return _StepResult(
        items=items,
        checked={
            "premises_checked": len(rows),
            "addresses_incomplete": len(items),
            # Hard-won law 7 — the blind spot with a number, and here the number
            # is zero BY CONSTRUCTION rather than by measurement.
            "addresses_a_standardiser_refused": 0,
            "no_address_service_is_connected": True,
        },
    ).as_dict()


# ── step 7 · group by what each will break ────────────────────────────────


def step_group_by_what_it_breaks(ctx, subjects) -> dict[str, Any]:
    """7 · The whole answer, in the order the card fixes.

    ⚠ **THE GROUPS ARE NOT SORTED BY COUNT.** `RB-119`'s design note: *"the
    groups are named by consequence — the storm text, dunning, runbook 3 — so
    the fix order is obvious without anyone ranking it."* Sorting by size would
    put whatever happens to be largest this month first and lose that ordering.

    A group with nothing in it is KEPT and reads `0`, because a group that
    disappears when it is clean is a group a clerk cannot see they are winning.
    """
    every = (
        _items(ctx, STEP_DUPLICATES)
        + _items(ctx, STEP_PREMISES_NO_METER)
        + _items(ctx, STEP_METERS_NO_PREMISE)
        + _items(ctx, STEP_ACCOUNTS_NO_UNIT)
        + _items(ctx, STEP_NO_CHANNEL)
        + _items(ctx, STEP_ADDRESSES)
    )
    counts = {name: 0 for name in GROUP_ORDER}
    for one in every:
        counts[one["group"]] = counts.get(one["group"], 0) + 1
    return _StepResult(
        items=every,
        checked={
            "items": len(every),
            "by_group": counts,
            "orphans": sum(counts[name] for name in ORPHAN_GROUPS),
            "work_items_raised": 0,
            "work_list_state": (
                "The work list is built in a later wave; these are on this run's own screen."
            ),
        },
    ).as_dict()


# ── the report ────────────────────────────────────────────────────────────


def _tile(tile_id: str, label: str, text: str, detail: str | None = None) -> dict[str, Any]:
    tile: dict[str, Any] = {
        "id": tile_id,
        "label": label,
        "value": {"kind": "text", "text": text},
    }
    if detail:
        tile["detail"] = detail
    return tile


def report(view) -> list[Block]:
    """Composed at CLOSE from what the steps counted, then frozen (`BR-RBS-020`).

    `RB-119`'s own block list — **KPIs · Breakdown · Action · Downloads** — plus
    the **Verdict** the result header consumes, which is the same composition
    `RB-122` ships and for the same reason.

    ⚠ **NO `Records` BLOCK, DELIBERATELY.** The card composes four blocks and
    the design note says why: this runbook is read as *groups*, not as 212 rows.
    The rows exist — they are in `set_results` and in the two download files —
    and drawing a 212-row table above the groups would bury the sentence the
    whole runbook exists to deliver.
    """
    grouped = _checked(view, STEP_GROUP)
    duplicates = _checked(view, STEP_DUPLICATES)
    premises = _checked(view, STEP_PREMISES_NO_METER)
    meters = _checked(view, STEP_METERS_NO_PREMISE)
    accounts = _checked(view, STEP_ACCOUNTS_NO_UNIT)
    channels = _checked(view, STEP_NO_CHANNEL)
    addresses = _checked(view, STEP_ADDRESSES)

    by_group = dict(grouped.get("by_group") or {})
    total = int(grouped.get("items") or 0)
    orphans = int(grouped.get("orphans") or 0)
    checked_accounts = int(channels.get("accounts_checked") or 0)
    texted = int(channels.get("reachable_by_text") or 0)

    # ⚠ **THE SAMPLE SENTENCE IS PART OF THE ANSWER, NOT A FOOTNOTE.** On a
    # utility whose records are still the seeded set, *"0 items"* alone would
    # read as *your records are clean*.
    sample_rows = (
        int(duplicates.get("customers_checked") or 0),
        int(premises.get("premises_that_are_sample_records") or 0),
        int(accounts.get("accounts_that_are_sample_records") or 0),
    )
    excluded = sample_rows[1] + sample_rows[2] + int(
        meters.get("meters_that_are_sample_records") or 0
    )
    sample_sentence = (
        f"{excluded} sample records were left out — they are the seeded set, not this "
        "utility's own records."
        if excluded
        else ""
    )
    # ⚠ **`0 of 0` IS NOT AN ANSWER AND IT NEARLY SHIPPED.** The first run of this
    # runbook on the seeded utility produced *"0 of 0 accounts cannot be reached
    # by text"* — arithmetically true, and it reads as a fault where the fact is
    # that every account here is a sample record. A ratio needs a denominator; a
    # count with no denominator gets a sentence instead.
    text_sentence = (
        f"{checked_accounts - texted} of {checked_accounts} accounts cannot be reached by text."
        if checked_accounts
        else "No accounts of this utility's own to check yet."
    )

    return [
        Block(
            block="verdict",
            payload={
                "word": "Clean" if not total else "To fix",
                "tone": "success" if not total else "warning",
                "count": (
                    f"{total} item{'s' if total != 1 else ''} in "
                    f"{len([one for one in GROUP_ORDER if by_group.get(one)])} groups."
                ),
                "detail": f"{text_sentence} {sample_sentence}".strip(),
            },
        ),
        Block(
            block="kpis",
            payload={
                "tiles": [
                    _tile(
                        "duplicates",
                        "Duplicate customers",
                        str(by_group.get(GROUP_DUPLICATES, 0)),
                        "Same phone, tax id or email",
                    ),
                    _tile("orphans", "Orphans", str(orphans), "Premises · meters · accounts"),
                    _tile(
                        "no_channel",
                        "No contact channel",
                        str(by_group.get(GROUP_NO_CHANNEL, 0)),
                        "Nobody can be told anything",
                    ),
                    _tile(
                        "addresses",
                        "Incomplete addresses",
                        str(by_group.get(GROUP_ADDRESSES, 0)),
                        "No address service is connected",
                    ),
                    # ⚠ A RATIO, BECAUSE A BARE COUNT ANSWERS NOTHING. *1,350*
                    # is meaningless; *1,350 of 2,907* is the number that decides
                    # whether the storm runbook works.
                    _tile(
                        "reachable_by_text",
                        "Reachable by text",
                        f"{texted} of {checked_accounts}" if checked_accounts else "—",
                        (
                            "A mobile on file and an opt-in"
                            if checked_accounts
                            else "No accounts of this utility's own yet"
                        ),
                    ),
                ]
            },
        ),
        Block(
            block="breakdown",
            payload={
                "heading": "By what it will break",
                "columns": [
                    {"key": "group", "label": "Group"},
                    {"key": "items", "label": "Items", "numeric": True},
                    {"key": "breaks", "label": "Will break"},
                    {"key": "fix", "label": "Fix"},
                ],
                "rows": [
                    {
                        "id": f"group-{name}",
                        "cells": {
                            "group": {"kind": "text", "text": GROUP_FACTS[name]["label"]},
                            "items": {"kind": "text", "text": str(by_group.get(name, 0))},
                            "breaks": {"kind": "text", "text": GROUP_FACTS[name]["breaks"]},
                            "fix": {
                                "kind": "link",
                                "label": GROUP_FACTS[name]["fix_label"],
                                "to": GROUP_FACTS[name]["fix_route"],
                            },
                        },
                    }
                    for name in GROUP_ORDER
                ],
            },
        ),
        Block(
            block="action",
            payload=(
                {
                    "label": "Raise work items",
                    "tier": "secondary",
                    "enabled": False,
                    # ⚠ B14 rule 33 — a refusal caps at five or six words.
                    "reason": "The work list is not built yet",
                }
            ),
        ),
        Block(
            block="downloads",
            payload={
                "files": [
                    {"id": "all_items", "label": "All items", "format": "csv"},
                    {"id": "by_group", "label": "By group", "format": "csv"},
                ]
            },
        ),
    ]


# ── the pinned scope ──────────────────────────────────────────────────────


def resolve(ctx):
    """The pinned set: **the tenant, once** (`BR-RBS-019`).

    `RB-119`'s *subject and unit of work* row reads **Tenant**, and every step
    is a `set` step over that one subject — which is what a runbook whose scope
    is *"the whole utility"* means. The record count on the run is therefore 1
    and the ITEM count is the number a clerk reads; those are different figures
    and the report never presents the first as the second.
    """
    return [
        SubjectRef(
            subject_type="tenant",
            subject_id=str(ctx.tenant_id) if ctx.tenant_id else "tenant",
            # B14 rule 31 — never the tenant's id. `tenancy_seam.today()` is
            # already this run's business date, so the label is a date a clerk
            # recognises rather than a handle.
            label=f"The whole utility · {tenancy_seam.today().isoformat()}",
        )
    ]


RUNBOOK = RunbookDefinition(
    key=KEY,
    name="Data hygiene",
    kind=models.KIND_CHECK,
    category="data_hygiene",
    subject_type="tenant",
    unit_of_work="the whole utility",
    # ⚠ **SCHEDULE ONLY, WHICH IS THE CARD'S OWN TRIGGER ROW.** `RB-119` reads
    # *Trigger: Schedule* and its *Runs* parameter reads *Monthly*. A Check that
    # a person could also start on demand would be a wider declaration than the
    # card makes, and widening one is a change request rather than a lane's
    # decision (`12-governance/13-change-process.md`).
    triggers=(models.TRIGGER_SCHEDULE,),
    tags=("Accounts", "Service points"),
    parameters=(
        Parameter(
            name="duplicate_means",
            type=PARAM_ENUM,
            label="Duplicate means",
            default="phone_tax_id_or_email",
            # ⚠ ONE CHOICE, AND IT IS THE ONE THE CARD NAMES. The source draws a
            # dropdown and gives it a single value; narrower matchers (phone
            # only, tax id only) are plausible and are NOT invented here —
            # `gis_reconciliation`'s `match_on` sets the same precedent.
            choices=("phone_tax_id_or_email",),
        ),
        Parameter(
            name="orphan_means",
            type=PARAM_REF_SETTING,
            label="Orphan means",
            # ⚠ **DECLARED, AND THE SETTING DOES NOT EXIST YET.** The card marks
            # this read-only and Settings-owned; no `customers` setting holds
            # the three orphan shapes today, so the definition is the step's own
            # (`Premise · no meter / Meter · no premise / Account · no unit`) and
            # the absence is stated rather than papered over. `RB-122`'s
            # `re_enable_when` is declared the same way and for the same reason:
            # a parameter that appears the day the setting does is a smaller
            # change than one nobody remembered.
            setting_key="customers.orphan_definition",
        ),
        Parameter(
            name="reachable_means",
            type=PARAM_ENUM,
            label="Reachable means",
            default="email_mobile_or_postal",
            choices=("email_mobile_or_postal",),
        ),
        Parameter(
            name="raise_work_items",
            type=PARAM_TOGGLE,
            label="Raise work items",
            # ⚠ **ON, AND IT RAISES NOTHING TODAY.** A work item is an ENGINE
            # act (`BR-RBS-022`) and the upsert is `CR-075` task `H1`, phase 4.
            # The Action block says so in its own reason rather than offering a
            # button that would do nothing.
            default=True,
        ),
        Parameter(
            name="runs",
            type=PARAM_ENUM,
            label="Runs",
            default="monthly",
            choices=("monthly",),
        ),
    ),
    resolve=resolve,
    report=report,
    steps=(
        Step(
            key=STEP_DUPLICATES,
            label=STEP_LABELS[STEP_DUPLICATES],
            mode=MODE_SET,
            run=step_duplicate_customers,
        ),
        Step(
            key=STEP_PREMISES_NO_METER,
            label=STEP_LABELS[STEP_PREMISES_NO_METER],
            mode=MODE_SET,
            run=step_premises_with_no_meter,
        ),
        Step(
            key=STEP_METERS_NO_PREMISE,
            label=STEP_LABELS[STEP_METERS_NO_PREMISE],
            mode=MODE_SET,
            run=step_meters_with_no_premise,
        ),
        Step(
            key=STEP_ACCOUNTS_NO_UNIT,
            label=STEP_LABELS[STEP_ACCOUNTS_NO_UNIT],
            mode=MODE_SET,
            run=step_accounts_with_no_unit,
        ),
        Step(
            key=STEP_NO_CHANNEL,
            label=STEP_LABELS[STEP_NO_CHANNEL],
            mode=MODE_SET,
            run=step_accounts_with_no_contact_channel,
        ),
        Step(
            key=STEP_ADDRESSES,
            label=STEP_LABELS[STEP_ADDRESSES],
            mode=MODE_SET,
            run=step_addresses_that_failed_standardisation,
        ),
        Step(
            key=STEP_GROUP,
            label=STEP_LABELS[STEP_GROUP],
            mode=MODE_SET,
            run=step_group_by_what_it_breaks,
        ),
    ),
    # ⚠ **NO PORTS AT ALL** (`BR-RBS-002`). Not an empty allow-list this runbook
    # is trusted not to use — the capability is absent, and `RunbookDefinition`
    # refuses a Check that declares one at CONSTRUCTION.
)


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-RBS-031 (EP-RBS-05; CR-075 wave S)
# generated: 2026-09-07 by the CR-075 wave S build lane
# checklist: A✔ B✔ C✔ D=n/a(no endpoint — every runbooks route is a GET and POST /runbooks/{key}/runs is wave L) E=n/a(no screen — RBS-004 and RBS-006 render any runbook; RB-020) F✔ G✔ H=n/a(no 🔒 path: this composes no idempotency key, touches no rating math and posts no ledger line)
# gates: pytest tests/test_us_rbs_031_data_hygiene.py · pytest tests/test_us_rbs_015_conformance.py · G115 (the import census) · G20 (the seam implementers)
# exceptions: nothing standardises an address in this product (`13-selector-inventory.md` S-8), so step 6 counts a premises address missing a city, a state or a postal code and says so in those words · a duplicate is an EQUALITY match on a blind index and never a similarity one (`BR-CUS-089`, the card's own stated absence) · consent to text is not recorded as consent, so *no mobile* and *not opted in* are counted separately · the sample exclusion is applied in the reads rather than as a `Guard`, because a guard over a single tenant subject could never fire · `orphan_means` is declared and no Settings row holds it
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
