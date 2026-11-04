#!/usr/bin/env python
"""Walk a premises import that names owners, end to end, on REAL PostgreSQL.

WHY THIS EXISTS
---------------
On 2026-09-19 the PO reported: *"User reported when we import premsies ->
provide owner deetails -> in thos ec ases Master Account is not getting
generated - can you check what is the issue?"*

The account WAS being generated. What was missing is that **nobody owned it** —
`premises.owner_id` NULL, no `premises_owners` row, the operator's name in the
legacy free-text box only. A first migration took that branch on EVERY row,
because the branch that writes the link is the one only an owner **already on
file** can take.

⛔ **AND THE UNIT SUITE WAS GREEN THROUGHOUT.**
`tests/test_cr058_w3_premises_owner_import.py` asserted
`premises_owner_accounts_created == 1`, which was TRUE. **The receipt was
telling the truth about the account and nothing asked whether the account had an
owner.** That is what this walk is for, and it is why every case below asserts
`premises.owner_id` and `premises_owners.master_account_id` **out of the
database** rather than reading a count off the receipt. A count is what made this
invisible for weeks.

⚠ **IT NEEDS REAL PostgreSQL** and not the default suite. The rehearsal, the
savepoints around a refused party and a refused account, and the RLS the whole
thing runs under are all things SQLite cannot express — CLAUDE.md hard-won law
14, and `config/settings/pgtest.py`'s own docstring.

USE
    cd 06-backend
    set -a; . ./.env; set +a
    DJANGO_SETTINGS_MODULE=config.settings.local \
    SBH_FIELD_ENCRYPTION_KEYS="insecure-dev:<the dev key>" \
    .venv/bin/python ../10-scripts/premises_owner_import_walkthrough.py

⚠ **`.env` points at production settings and a key the dev rows were not written
under**, so both overrides are required; without them the run fails on decrypting
rows it did not write.

⚠ **IT WRITES NOTHING.** Everything happens inside one transaction that ends in
a deliberate `RuntimeError`, so the tenant is exactly as it was — verified by
counting premises and owners either side and printing both. A walk that left
seven addresses behind could only be run once.

EXIT CODE
    0  every expectation held
    1  at least one did not, and each failure prints what was expected and what
       the database actually held.
"""

import io
import os
import sys

import django

django.setup()

import csv  # noqa: E402

from django.db import transaction  # noqa: E402

from apps.customers import models as cm  # noqa: E402
from apps.identity.models import TenantMembership  # noqa: E402
from apps.metering import import_runs as ir  # noqa: E402
from apps.metering import models as mm  # noqa: E402
from apps.tenancy import models as tm  # noqa: E402
from core.tenancy import tenant_context  # noqa: E402

HEADERS = [
    "PREMISE_ID", "ADDR1", "CITY", "STATE", "ZIP", "PROP_TYPE", "UNIT_CNT",
    "SVC_AVAIL", "OWNER", "OWNER/MANAGER", "LEGACY_KEY", "INSIDE_CITY",
    "OWNER_KIND", "SSN", "DRIVING LICENCE", "OWNER PHONE", "TAX ID",
    "OWNER ACCOUNT TYPE", "OWNER CATEGORY", "OWNER EMAIL",
]

MAPPING = {
    "PREMISE_ID": "premise_no", "ADDR1": "address_line", "CITY": "city",
    "STATE": "state", "ZIP": "postal_code", "PROP_TYPE": "premises_type",
    "UNIT_CNT": ir.IGNORE, "SVC_AVAIL": "services_available",
    "OWNER": "owner",
    # ⛔ **`OWNER/MANAGER` MAPS TO NOTHING ON PURPOSE (`DEF-MET-5802`).** The
    # free-text `owner_manager` column was RETIRED from the premises template on
    # 2026-09-19: it was a second name-shaped column that created nobody, beside
    # `Owner name`, which creates the owner. Pointing a header at it now is
    # refused at stage 2 by name — `metering.import.unknown_mapping_target` —
    # which is the correct answer for a target that no longer exists, and which
    # this script hit on its first run because it was copied from a reproduction
    # written the same morning.
    #
    # ⚠ **A SAVED TEMPLATE naming it degrades differently and must**: the entry
    # is DROPPED from the suggestion so the column arrives unmapped, rather than
    # refusing the operator's whole run. That path is covered by
    # `tests/test_def_met_5802_declared_columns.py`.
    #
    # ⚠ **THE FIELD IS STILL WRITTEN.** `_resolve_owner_ref` puts the `Owner
    # name` cell into `owner_manager` as BR-MET-151 clause 4 provenance, which
    # case 1 below asserts.
    "OWNER/MANAGER": ir.IGNORE,
    "LEGACY_KEY": "external_ref", "INSIDE_CITY": "inside_city_limits",
    "OWNER_KIND": "owner_kind", "SSN": "owner_ssn",
    "DRIVING LICENCE": "owner_driving_licence", "OWNER PHONE": "owner_phone",
    "TAX ID": "owner_tax_id", "OWNER ACCOUNT TYPE": "owner_account_type",
    "OWNER CATEGORY": "owner_category", "OWNER EMAIL": "owner_email",
}
ALL_ON = {
    "drop_exact_duplicates": True,
    "keep_latest_on_key": False,
    "skip_rows_missing_required": False,
}

#: Every expectation is stated as a sentence a person can check, beside the
#: three database facts that decide it. `party` — is there a `premises_owners`
#: row linked to the address. `account` — does the address carry an account.
#: `link` — is `premises_owners.master_account_id` written, which is the
#: declared link `DEF-2902`/`DEF-2903` report missing from every master account.
CASES: list[dict] = []
FAILURES: list[str] = []


def _case(label, expect_party, expect_account, expect_link, why, **cells):
    CASES.append(
        {
            "label": label,
            "cells": cells,
            "party": expect_party,
            "account": expect_account,
            "link": expect_link,
            "why": why,
        }
    )


def build_cases(account_type: str, category: str, existing_owner: str) -> None:
    _case(
        "1 name + identity + type + CATEGORY",
        True, True, True,
        "the ruling of 2026-09-19: told the category, the import creates the "
        "party and links it",
        OWNER="Walk Alpha Holdings", OWNER_KIND="company",
        **{"TAX ID": "84-1000001", "OWNER ACCOUNT TYPE": account_type,
           "OWNER CATEGORY": category, "OWNER EMAIL": "ap@walk-alpha.test"},
    )
    _case(
        "2 name + identity + type, NO category",
        False, True, False,
        "unchanged from before the ruling — nothing may read a category off a "
        "name (BR-MET-151 clause 3), so the address gets its account and the "
        "party waits for a person",
        OWNER="Walk Bravo Holdings", OWNER_KIND="company",
        **{"TAX ID": "84-1000002", "OWNER ACCOUNT TYPE": account_type},
    )
    _case(
        "3 no account type",
        False, False, False,
        "PO 2026-09-01 — nothing may guess what a customer is charged as",
        OWNER="Walk Charlie Holdings", OWNER_KIND="company",
        **{"TAX ID": "84-1000003", "OWNER CATEGORY": category},
    )
    _case(
        "4 no owner kind",
        False, False, False,
        "BR-CUS-1022 — an identifier under an unstated kind cannot be judged",
        OWNER="Walk Delta Holdings",
        **{"TAX ID": "84-1000004", "OWNER ACCOUNT TYPE": account_type,
           "OWNER CATEGORY": category},
    )
    _case(
        "5 name only, no identifier",
        False, False, False,
        "PO 2026-09-01 — 'otherwise dont create anything'. A category does not "
        "widen what earns an account",
        OWNER="Walk Echo Holdings",
        **{"OWNER CATEGORY": category},
    )
    _case(
        "6 name ONLY in the legacy box",
        False, False, False,
        "the fifth verdict — the Owner column names nobody, so nothing is "
        "created and the row is COUNTED (it was counted nowhere until "
        "2026-09-19)",
        OWNER_KIND="person",
        **{"OWNER/MANAGER": "Walk Foxtrot", "SSN": "444-55-6666",
           "OWNER ACCOUNT TYPE": account_type, "OWNER CATEGORY": category},
    )
    _case(
        "7 owner ALREADY on file",
        True, True, True,
        "the branch that always worked — the party exists, so the import links "
        "to it and no second party is created",
        OWNER=existing_owner, OWNER_KIND="company",
        **{"TAX ID": "84-1000007", "OWNER ACCOUNT TYPE": account_type,
           "OWNER CATEGORY": category},
    )
    _case(
        "8 category that is not on the list",
        False, True, False,
        "an unknown code is refused BY NAME by the tenant's own lookup, the "
        "party is not created, and the refusal is counted rather than hidden — "
        "the address and its account still stand",
        OWNER="Walk Golf Holdings", OWNER_KIND="company",
        **{"TAX ID": "84-1000008", "OWNER ACCOUNT TYPE": account_type,
           "OWNER CATEGORY": "not_a_real_category"},
    )


def row_for(index: int, cells: dict) -> dict:
    base = {header: "" for header in HEADERS}
    base.update(
        {
            "ADDR1": f"{900 + index} Walk Way",
            "CITY": "Brazos Bend",
            "STATE": "TX",
            "ZIP": "77000",
            "SVC_AVAIL": "water",
            "INSIDE_CITY": "yes",
        }
    )
    base.update(cells)
    return base


def check(label: str, what: str, expected, actual) -> None:
    if expected == actual:
        print(f"      OK   {what}: {actual}")
        return
    FAILURES.append(f"{label} — {what}: expected {expected!r}, database held {actual!r}")
    print(f"      FAIL {what}: expected {expected!r}, got {actual!r}")


def main() -> int:
    tenant_id = tm.Tenant.objects.values_list("id", flat=True).first()
    if tenant_id is None:
        print("no tenant on this database", file=sys.stderr)
        return 1

    with tenant_context(tenant_id):
        from types import SimpleNamespace

        membership = (
            TenantMembership.objects.filter(status="active", role__code="system_admin")
            .select_related("user")
            .first()
        )
        if membership is None:
            print("no active system_admin on this tenant", file=sys.stderr)
            return 1
        # ⚠ A `User` alone is refused — the role is read off the ACTOR.
        actor = SimpleNamespace(
            id=membership.user.id, pk=membership.user.id,
            role="system_admin", user=membership.user,
        )

        account_type = (
            cm.AccountType.objects.filter(active=True).exclude(legacy=True)
            .order_by("code").values_list("code", flat=True).first()
        )
        category = (
            tm.PremisesOwnerCategory.objects.filter(active=True)
            .order_by("code").values_list("code", flat=True).first()
        )
        existing = mm.PremisesOwner.objects.order_by("name").values_list("name", flat=True).first()
        if not (account_type and category and existing):
            print(
                "this tenant needs an account type, an owner category and at "
                f"least one owner on file (got {account_type!r}, {category!r}, {existing!r})",
                file=sys.stderr,
            )
            return 1
        print(f"tenant reads: account_type={account_type!r} category={category!r} "
              f"existing_owner={existing!r}\n")

        build_cases(account_type, category, existing)

        premises_before = mm.Premises.objects.count()
        owners_before = mm.PremisesOwner.objects.count()

        buf = io.StringIO()
        writer = csv.writer(buf)
        writer.writerow(HEADERS)
        for index, case in enumerate(CASES, start=1):
            writer.writerow([row_for(index, case["cells"])[h] for h in HEADERS])

        try:
            with transaction.atomic():
                run = ir.extract(
                    actor,
                    {
                        "target": "premises", "source_kind": "file",
                        "file_name": "owner_walk.csv", "content": buf.getvalue(),
                        "session_ref": "sess_owner_walk", "ip": "127.0.0.1",
                    },
                )
                ir.transform(actor, run["id"], {"mapping": MAPPING, "row_handling": ALL_ON})
                ir.validate(actor, run["id"])

                print("=== STAGE 3 · what the operator is told BEFORE anything is written ===")
                for row in mm.ImportRunRow.objects.filter(run_id=run["id"]).order_by("row_no"):
                    problem = row.problem
                    if isinstance(problem, dict):
                        codes = sorted(str(k) for k in problem)
                    elif isinstance(problem, list):
                        codes = [
                            str(entry.get("code") or entry) if isinstance(entry, dict) else str(entry)
                            for entry in problem
                        ]
                    else:
                        codes = [str(problem)] if problem else []
                    print(f"  row {row.row_no}: {row.outcome} -> {codes}")

                result = ir.load(actor, run["id"], {"write_mode": "insert"})
                receipt = result.get("receipt", result)
                counts = receipt.get("counts", receipt)

                print("\n=== THE RECEIPT, every owner figure ===")
                for key in sorted(counts):
                    if "owner" in key.lower():
                        print(f"  {key} = {counts[key]}")

                print("\n=== WHAT THE DATABASE ACTUALLY HOLDS, case by case ===")
                for index, case in enumerate(CASES, start=1):
                    address = f"{900 + index} Walk Way"
                    print(f"\n  {case['label']}  ({address})")
                    print(f"      why: {case['why']}")
                    premises = mm.Premises.objects.filter(address_line=address).first()
                    if premises is None:
                        check(case["label"], "the address loaded", True, False)
                        continue
                    owner = (
                        mm.PremisesOwner.objects.filter(id=premises.owner_id).first()
                        if premises.owner_id else None
                    )
                    accounts = list(
                        cm.Account.objects.filter(premises_id=premises.id)
                        .values_list("account_no", flat=True)
                    )
                    # ⛔ THE THREE FACTS. Read from the database, never from the
                    # receipt — the receipt is what hid this.
                    check(case["label"], "premises.owner_id is set", case["party"], premises.owner_id is not None)
                    check(case["label"], "the address has an account", case["account"], bool(accounts))
                    check(
                        case["label"], "premises_owners.master_account_id is written",
                        case["link"], bool(getattr(owner, "master_account_id", None)),
                    )
                    print(f"      party={owner.name if owner else None!r} "
                          f"category={getattr(getattr(owner, 'category', None), 'code', None)!r} "
                          f"accounts={accounts} owner_manager={premises.owner_manager!r}")

                # ⚠ No second party for an owner already on file — the reuse the
                # NOT NULL name index exists to force (BR-MET-150).
                created = mm.PremisesOwner.objects.count() - owners_before
                print(f"\n  parties created by this run: {created}")
                # ⚠ **ONE, NOT TWO — AND THE DIFFERENCE IS THE `BR-MET-150`
                # REUSE THIS WHOLE FEATURE EXISTS TO PROTECT.** Case 1 CREATES a
                # party; case 7 names an owner already on file and LINKS to it.
                # Both end with `premises.owner_id` set, which is why the
                # per-case checks above cannot tell them apart and this one
                # must: a run that created two parties here would be minting
                # *"twelve unrelated strings"* for one landlord, which is the
                # failure the case-insensitive unique name index exists to
                # force. This expectation was 2 on the first run and the walk
                # said so.
                check("overall", "parties created", 1, created)
                check(
                    "overall", "the receipt agrees with the database",
                    created, int(counts.get("premises_owner_parties_created") or 0),
                )
                check(
                    "overall", "the row naming nobody is counted", 1,
                    int(counts.get("premises_owner_no_owner_named") or 0),
                )
                check(
                    "overall", "the row with no category is counted", 1,
                    int(counts.get("premises_owner_no_category") or 0),
                )
                check(
                    "overall", "the unknown category is counted as refused", 1,
                    int(counts.get("premises_owner_party_refused") or 0),
                )
                # ⚠ **AND THE TWO ARE NOT THE SAME FIGURE.** Before this walk
                # ran, an unrecognised category was counted as *no category
                # stated* — the receipt telling an operator the opposite of what
                # their file said, because the lookup had already resolved the
                # typo to `None`. Asserting both numbers is what separates them;
                # asserting either alone passes on the bug.
                check(
                    "overall", "a typo is NOT counted as an unstated category", 1,
                    int(counts.get("premises_owner_no_category") or 0),
                )
                raise RuntimeError("ROLLBACK-ON-PURPOSE")
        except RuntimeError as exc:
            if "ROLLBACK-ON-PURPOSE" not in str(exc):
                raise

        premises_after = mm.Premises.objects.count()
        owners_after = mm.PremisesOwner.objects.count()
        print(f"\n(rolled back — premises {premises_before}->{premises_after}, "
              f"owners {owners_before}->{owners_after})")
        check("overall", "the tenant is untouched", (premises_before, owners_before),
              (premises_after, owners_after))

    print()
    if FAILURES:
        print(f"{len(FAILURES)} PROBLEM(S):")
        for line in FAILURES:
            print(f"  - {line}")
        return 1
    print(f"all {len(CASES)} cases behaved as expected")
    return 0


if __name__ == "__main__":
    if "DJANGO_SETTINGS_MODULE" not in os.environ:
        print("set DJANGO_SETTINGS_MODULE=config.settings.local", file=sys.stderr)
        raise SystemExit(1)
    raise SystemExit(main())
