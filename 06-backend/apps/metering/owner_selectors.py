# ── Trace ──────────────────────────────────────────────
# Change:  CR-039 wave C tasks 12-13 — the READ side of the typed premises
#          owner and of BR-MET-151's matching review surface.
# Rules:   BR-MET-150 (the typed record) · BR-MET-151 (unmatched is computed)
# Screens: PRM-01 edit modal (the owner picker) · PRM-02 premises detail (the
#          owner block) · PRM-04 the owner-matching review list
# Tests:   06-backend/tests/test_cr039_c12_premises_owner.py ·
#          06-backend/tests/test_cr039_c13_owner_migration.py
# ───────────────────────────────────────────────────────
"""Read-side for premises owners. No writes live here (B1: selectors read)."""

from typing import Any

from django.db.models import Q, QuerySet

from apps.metering import models, seams


def owner_detail_dict(row: models.PremisesOwner, *, with_account: bool = True) -> dict[str, Any]:
    """One typed owner, as every screen reads it.

    ⚠ **THE CUSTOMER IS REACHED THROUGH THE ACCOUNT, AND STILL NEVER THROUGH
    `customers`' ORM.** `customer_id` and `customer_no` come out of the account
    summary the SEAM already returned (CR-056 task 18, `BR-MET-1020`); B1/B8
    are untouched, because this module still asks its neighbour rather than
    joining. A serializer that quietly joined would be a cross-module read
    hidden inside a dict comprehension, which is the hardest kind to find later.

    ⚠ **THERE IS NO `notes` OR `description` KEY, AND THERE IS NO COLUMN TO
    SERVE ONE FROM.** PO 2026-08-27: *"category is okay, no richer text"*.
    """
    # ONE seam call, TWO consumers — the account block below and the customer
    # the account is linked to (CR-056 task 18). Asking twice would double the
    # cost DEF-324 measured, for a fact the first answer already carries.
    account_summary = (
        seams.owner_master_account_summary(row.master_account_id)
        if (with_account and row.master_account_id)
        else None
    )
    return {
        "id": str(row.id),
        "name": row.name,
        # The category, both halves: the CODE a form posts back unchanged and
        # the NAME a person reads. Same reasoning as `area_code`/`area_name` on
        # the premises row — the client derives neither.
        "category_code": row.category.code if row.category_id else None,
        "category_name": row.category.name if row.category_id else None,
        "contact_name": row.contact_name,
        "email": row.email,
        "phone": row.phone,
        # ── CR-056 W3 task 18 · BR-MET-1020 — REACHED THROUGH THE ACCOUNT ───
        # ⛔ **THIS USED TO BE `str(row.customer_id)` AND THAT COLUMN NO LONGER
        # DECIDES ANYTHING.** Two paths reached the same person and the direct
        # one skipped the account — the only row that holds a balance, receives
        # a bill and can be posted to. Under CR-056's ruling of 2026-08-31 a
        # Master Account IS the owner's account at an address, so the party is
        # whoever that account is linked to, and there is one answer instead of
        # two that can disagree.
        #
        # ⚠ **ANSWERABLE ONLY WHEN THE ACCOUNT IS EXPANDED**, and `None` here
        # therefore means *not asked* as well as *nobody* — which is why
        # `customer_expanded` is served beside it rather than left to be
        # inferred. The list does not expand (DEF-324: one account read per row
        # over 200 rows is the N+1 that cost 47 of 118 profiled seconds), so a
        # picker showing a blank party column is showing *not asked*.
        "customer_id": (
            (account_summary or {}).get("customer", {}).get("id")
            if (account_summary and account_summary.get("customer"))
            else None
        ),
        "customer_expanded": bool(with_account and row.master_account_id),
        # B14 rule 31 — the NUMBER a person quotes, beside the id a machine uses.
        "customer_no": (
            (account_summary or {}).get("customer", {}).get("customer_no")
            if (account_summary and account_summary.get("customer"))
            else None
        ),
        # ⚠ **A STORED VALUE IN THE RETIRED COLUMN IS STATED, NEVER SILENTLY
        # DROPPED.** Rows written before 2026-08-31 may still carry one, and a
        # fact that stops being served without saying so is how a clerk comes to
        # believe a link was lost. `OQ-1240` is open on whether the column is
        # dropped outright; until it is ruled, this key is the only thing that
        # says the value exists and no longer decides anything.
        "customer_link_column_ignored": bool(row.customer_id),
        # BR-MET-151 clause 4 — which free-text string became this party. NULL
        # on an owner created from scratch, which is a different fact from an
        # empty string.
        "source_owner_manager": row.source_owner_manager,
        "active": row.active,
        # How many addresses point at this party. It is the ruling's own reason
        # for the table made visible (*"the same landlord across twelve
        # addresses is one party"*) and it is what a clerk needs before renaming
        # or retiring one.
        "premises_count": row.premises_set.filter(deleted_at__isnull=True).count(),
        # ── BR-MET-400 · DEF-650 — THE ACCOUNT, NOT A NAME BESIDE ONE ───────
        # **PO 2026-08-27, verbatim:** *"you ahve to showall details form
        # account"*. Two keys, and both are needed:
        #   · `master_account_id` is the LINK — what a form posts back, what a
        #     charge posts to, and the one fact this module owns;
        #   · `master_account` is the account's own details, read through the
        #     seam AT THE MOMENT OF ASKING. Nothing is copied onto this row, so
        #     nothing can drift — which is the complaint `OQ-501` files against
        #     `owner_manager` carrying the same name twice.
        #
        # ⚠ **`None` IS A REAL STATE AND IT IS SERVED RATHER THAN OMITTED.** An
        # owner with no account yet is `OQ-790`'s open case, and a screen that
        # cannot tell "no account" from "key missing" renders neither.
        "master_account_id": str(row.master_account_id) if row.master_account_id else None,
        "master_account": account_summary,
        # ⚠ **`master_account: null` MEANS TWO THINGS, SO THE SECOND ONE IS
        # SPELLED OUT RATHER THAN LEFT TO BE INFERRED (DEF-324 · DEF-762).**
        # The expansion costs one account read AND one ledger derivation per
        # row, and the picker asks for 200 owners at a time — which is precisely
        # the N+1 DEF-324 measured at *47 of 118 profiled seconds answering one
        # question 304 times*. So the LIST does not expand, and says so here
        # instead of serving a null that reads as *"this owner has no account"*.
        # `master_account_id` is a column and is always true.
        "master_account_expanded": bool(with_account),
    }


def owner_list(*, q: str | None = None, active: bool | None = None) -> QuerySet:
    """The picker and the S8-style list. Search = name · contact · the free-text
    string this party was matched from — that last one is what makes the picker
    usable while the matching backlog exists: a clerk typing the name off the
    old box finds the party it already became."""
    from apps.metering.premises_owners import _tenant_id

    qs = models.PremisesOwner.objects.filter(tenant_id=_tenant_id()).select_related("category")
    if active is not None:
        qs = qs.filter(active=active)
    term = (q or "").strip()
    if term:
        qs = qs.filter(
            Q(name__icontains=term)
            | Q(contact_name__icontains=term)
            | Q(source_owner_manager__icontains=term)
        )
    return qs.order_by("name")


def unmatched_owner_rows(limit: int = 200) -> list[dict[str, Any]]:
    """PRM-04 — the free-text names still waiting for a person (BR-MET-151).

    **This is what "a flagged migration that offers each name for matching"
    looks like when the migration itself writes nothing.** Each row is one
    address, its free-text string, and the typed owners whose name or
    provenance already matches that string — the *offer*. It offers CANDIDATES
    and never a category: `suggested_owner_ids` is only ever populated by an
    EXACT case-insensitive name match, because a fuzzy match is a guess wearing
    a suggestion's clothes and a clerk clicking through a list will accept it.

    Grouped BY NAME rather than by address, deliberately: twelve addresses
    sharing one landlord are ONE decision, and a list of twelve identical rows
    invites twelve separate parties — the exact outcome
    `uq_premises_owners_tenant_name_ci` exists to make impossible.
    """
    from apps.metering.premises_owners import unmatched_premises_qs

    grouped: dict[str, dict[str, Any]] = {}
    for row in unmatched_premises_qs().order_by("owner_manager", "address_line")[:limit]:
        name = (row.owner_manager or "").strip()
        entry = grouped.setdefault(
            name,
            {
                "owner_manager": name,
                "premises": [],
                "premises_count": 0,
                "suggested_owner_ids": [],
            },
        )
        if len(entry["premises"]) < 25:
            entry["premises"].append(
                {
                    "id": str(row.id),
                    "premise_no": row.premise_no,
                    "address_line": row.address_line,
                }
            )
        entry["premises_count"] += 1

    if grouped:
        from apps.metering.premises_owners import _tenant_id

        # ⚠ **MATCHED IN PYTHON, ON LOWERCASE, AND THAT IS NOT LAZINESS.** A
        # `name__in=[...]` lookup is CASE-SENSITIVE on both vendors, so
        # *Whitfield Rentals LLC* would not be offered for the premises whose box
        # reads *whitfield rentals llc* -- and the whole reason this surface
        # exists is that the strings are inconsistent. It is still an EXACT
        # match, never a fuzzy one (BR-MET-151 clause 3).
        # `uq_premises_owners_tenant_name_ci` is case-INSENSITIVE too, so two
        # parties can never collide on the lowered key. A tenant of this product
        # has at most a few hundred owners (<3,000 connections), so the set is
        # small and the comparison is exact rather than a LIKE.
        lowered = {name.lower(): name for name in grouped}
        for owner in models.PremisesOwner.objects.filter(tenant_id=_tenant_id(), active=True):
            for candidate in (owner.name, owner.source_owner_manager):
                key = lowered.get((candidate or "").strip().lower())
                if key is not None and str(owner.id) not in grouped[key]["suggested_owner_ids"]:
                    grouped[key]["suggested_owner_ids"].append(str(owner.id))
    return sorted(grouped.values(), key=lambda entry: entry["owner_manager"].lower())


# ── Lifecycle ─────────────────────────────────────────────
# packet: CR-039 wave C tasks 12-14 (12-governance/11-change-requests.md) + PO ruling 2026-08-27 ("category is okay, no richer text") + BR-MET-150/151/152 + BR-TEN-150
# generated: 2026-08-27 by the CR-039 wave C tasks 12-14 lane
# checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=n/a
# gates: ruff✔ black✔ · manage.py check 0 issues✔ · makemigrations --check clean✔ · pytest tests/test_cr039_c12_premises_owner.py 13 passed · tests/test_cr039_c13_owner_migration.py 12 passed · RED-proved (see the lane report)
# exceptions:
#   E3 `owner_detail_dict` serves `customer_id` and NOT the customer's name:
#      resolving it here would be a cross-module read hidden inside a dict
#      comprehension (B1/B8). The caller that needs the name fetches it through
#      `apps.metering.seams`.
#   E3 `unmatched_owner_rows` matches suggestions in PYTHON on lowercase rather
#      than with a `__in` lookup — `__in` is case-SENSITIVE on both vendors and the
#      whole reason this surface exists is that the strings are inconsistent. Still
#      an EXACT match, never fuzzy (BR-MET-151 clause 3).
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
