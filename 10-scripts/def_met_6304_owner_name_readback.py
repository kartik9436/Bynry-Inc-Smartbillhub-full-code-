"""`DEF-MET-6304` — WHAT THE PREMISES LIST COSTS, AND WHAT IT CAN NAME.

The Owner cell on S14 reads *"No name recorded · AC-2026-00051"* on every row
that has an account. The number is right and the sentence is false: the name IS
recorded — the list simply never asked for it. This script answers the two
questions the fix turns on, on a real PostgreSQL clone:

  1 · **HOW MANY STATEMENTS does one whole page of the list issue?** Before and
      after must be compared on the SAME page of the SAME data, so this counts
      the exact three calls `apps/metering/api.premises` makes — the queryset
      slice, `premises_master_account_numbers` (the `prepare` hook) and
      `premises_detail_dict` once per row — inside one capture.
  2 · **WHAT WOULD THE CELL READ?** The count alone cannot tell a fix from a
      regression; `owner_cell` below reproduces `PremisesListPage.tsx`'s own
      branch (`account.name ?? t("metering.premises.owner.unnamed")`) against
      the payload the server actually serves.

⛔ **THE COUNT IS THE POINT AND IT IS A COUNT PER PAGE, NEVER PER ROW.**
`apps/metering/seams.master_account_numbers` exists so a list can print an
account number without buying `DEF-324` a second time — *47 of 118 profiled
seconds answering one question 304 times* — so the only number worth reading is
whether the page's cost moved with the PAGE SIZE. Section 3 runs the same page
at three sizes for exactly that reason: a fix that adds one statement to a page
of five and one to a page of fifty is O(1); one that adds five and fifty is the
defect coming back.

⚠ **IT WRITES NOTHING.** Every call here is a selector. Nothing is created and
no transaction is opened.

⚠ **EVERY READ NEEDS `app.tenant_id` SET (CLAUDE.md hard rule 1).** Unset, RLS
matches zero rows and a missing name looks exactly like the bug — which is why
`tenancy.tenant_context` wraps the whole run and why section 0 prints the row
count it found before anything is measured.

HOW TO RUN IT
-------------
    10-scripts/proof-db.sh clone ownername
    cd 06-backend && DJANGO_SETTINGS_MODULE=config.settings.local \
      DATABASE_URL=postgres://<user>:<pass>@127.0.0.1:5432/sbh_clone_ownername \
      python3 manage.py shell < ../10-scripts/def_met_6304_owner_name_readback.py

⚠ **RUN IT AGAINST A DATABASE NOBODY ELSE IS SEEDING** — a mid-run reseed looks
exactly like a broken screen. `proof-db.sh clone` gives you a private one.

MEASURED 2026-09-23 ON A CLONE OF `brazosbend`, POSTGRESQL 16
-------------------------------------------------------------
BEFORE the fix (tip `a162557c0`):

    FOUND  premises 79  naming a master account 5
    -- 1 . ONE PAGE OF 50 -- 107 statements
       P-00043  181 Willow Bend Dr    No name recorded · AC-2026-00054
       P-00044  183 Cedar Ridge Way   No name recorded · AC-2026-00054
       P-00045  301 Mill Pond Ln      No name recorded · AC-2026-00053
    -- 2 . WHAT THE BOOKS ACTUALLY HOLD FOR THOSE ACCOUNTS --
       primary_contact_names_for(2 ids) -> 2 names in 1 statement(s)
         Mill Pond Apartments LP
         Silver Creek Duplex Holdings
    -- 3 . DOES THE COST MOVE WITH THE PAGE? --
       page of  5 -> 11 · page of 25 -> 51 · page of 50 -> 107

AFTER:

    -- 1 . ONE PAGE OF 50 -- 108 statements
       P-00043  181 Willow Bend Dr    Silver Creek Duplex Holdings · AC-2026-00054
       P-00044  183 Cedar Ridge Way   Silver Creek Duplex Holdings · AC-2026-00054
       P-00045  301 Mill Pond Ln      Mill Pond Apartments LP · AC-2026-00053
    -- 3 . DOES THE COST MOVE WITH THE PAGE? --
       page of  5 -> 11 · page of 25 -> 51 · page of 50 -> 108

**+1 STATEMENT FOR THE WHOLE PAGE, AND ZERO WHERE NO ROW NAMES AN ACCOUNT** —
the pages of 5 and 25 did not move at all, because `master_account_numbers`
returns `{}` without asking anything when the page declares no account, and
neither of those two pages holds one. Section 2 is why it costs anything:
`accounts` has NO `name` column and the name is the primary CONTACT's, in a
second table.

⚠ **SECTION 3's 107 IS NOT THIS DEFECT AND MUST NOT BE READ AS IT.** One
hundred of those statements are two `COUNT(*)` on `units` per row, from
`premises_detail_dict`'s `units` and `units_common` cells — a separate N+1 on
the same serializer, filed as `DEF-MET-6312` and left for its own lane. The
cost that belongs to THIS change is the difference: one.
"""

import os

from django.db import connection
from django.test.utils import CaptureQueriesContext

from apps.metering import selectors
from apps.tenancy import models as ten
from core import tenancy

TENANT = os.environ.get("MET6304_TENANT", "brazosbend")


def owner_cell(row: dict) -> str:
    """`PremisesListPage.tsx`'s Owner branch, in Python.

    ⚠ **IT REPRODUCES THE SCREEN'S PRECEDENCE, NOT A CONVENIENT SUMMARY OF IT.**
    `premisesOwnerContract.premisesOwnerAccount` reads the expansion first and
    the flat number third; on a LIST row only the third case can fire, and the
    third case is the one that hardcoded `name: null`. A helper here that read
    `master_account` would pass on a payload the list never serves.
    """
    expanded = row.get("master_account")
    if isinstance(expanded, dict) and expanded.get("id"):
        name, number = expanded.get("name"), expanded.get("account_no")
    else:
        number = row.get("master_account_no")
        if not number:
            return "(blank — nobody asked)" if not row.get("master_account_expanded") else "(none)"
        name = row.get("master_account_name")
    return f"{name or 'No name recorded'}" + (f" · {number}" if number else "")


def one_page(size: int) -> tuple[int, list[dict]]:
    """The three calls `api.premises` makes for one page, counted together."""
    with CaptureQueriesContext(connection) as captured:
        page = list(selectors.premises_list()[:size])
        numbers = selectors.premises_master_account_numbers(page)
        rows = [
            selectors.premises_detail_dict(
                row, with_owner_account=False, master_account_numbers=numbers
            )
            for row in page
        ]
    return len(captured.captured_queries), rows


tenant = ten.Tenant.objects.get(subdomain=TENANT)
with tenancy.tenant_context(str(tenant.id)):
    # ── 0 · what the tenant holds, BEFORE anything is measured ──────────────
    # A zero here means `app.tenant_id` never reached the connection, not that
    # the estate is empty — hard rule 1, and the reason this prints first.
    total = selectors.premises_list().count()
    declared = sum(
        1 for row in selectors.premises_list() if selectors.premises_master_account_from_row(row)[0]
    )
    print(f"FOUND  premises {total}  naming a master account {declared}")
    if total == 0:
        raise SystemExit("REFUSED: zero premises — app.tenant_id is not set (hard rule 1)")

    # ── 1 · the whole page, and what each owner cell would read ─────────────
    statements, rows = one_page(50)
    print(f"-- 1 . ONE PAGE OF 50 -- {statements} statements")
    for row in rows:
        cell = owner_cell(row)
        if "blank" not in cell and cell != "(none)":
            print(f"   {row['premise_no']}  {(row['address_line'] or '')[:26]:26}  {cell}")

    # ── 2 · the name IS recorded, which is the sentence's falsehood ─────────
    from apps.customers import selectors as cus_selectors  # noqa: E402

    ids = [row["master_account_id"] for row in rows if row.get("master_account_id")]
    print("-- 2 . WHAT THE BOOKS ACTUALLY HOLD FOR THOSE ACCOUNTS --")
    with CaptureQueriesContext(connection) as captured:
        names = cus_selectors.primary_contact_names_for(sorted(set(ids)))
    print(f"   primary_contact_names_for({len(set(ids))} ids) -> {len(names)} names "
          f"in {len(captured.captured_queries)} statement(s)")
    for key, value in sorted(names.items(), key=lambda kv: kv[1] or ""):
        print(f"     {value}")

    # ── 3 · O(1) OR O(n)? the only question the count is asked ──────────────
    print("-- 3 . DOES THE COST MOVE WITH THE PAGE? --")
    for size in (5, 25, 50):
        count, _ = one_page(size)
        print(f"   page of {size:>2} -> {count} statements")
