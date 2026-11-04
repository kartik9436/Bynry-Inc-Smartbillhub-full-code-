#!/usr/bin/env python
"""Delete the move-in DRAFTS that `po20260919_move_in_wizard_walkthrough.mjs` wrote.

`CR-122-BRC06`. The walk drives a real browser against a real beta, and a
move-in draft is a real `wizard_parks` row — so every run leaves rows on the
Move-ins tab. **Run this after the walk, or the next person's beta lies to
them**: a tester opening Accounts → Move-ins would find a dozen half-finished
move-ins on unit SCW-U-042 that no clerk ever started.

═══════════════════════════════════════════════════════════════════════════
WHAT IT DELETES, AND WHY THAT SET AND NOT A WIDER ONE
═══════════════════════════════════════════════════════════════════════════
A row is the walk's if **all three** hold:

  1. `waiting_on = ''` — a DRAFT, never a PARK. A park is something a person
     chose to do, with a reason, a note and often a reminder attached; the
     walk never parks and this script must never delete one.
  2. `flow = 'move_in'`.
  3. its `values` carry the walk's own run marker, `MIW-<six digits>`, which
     the walk types into the customer's name and the deposit's receipt number.

⚠ **THE MARKER IS THE POINT.** Deleting "every move-in draft created today"
would be correct on a quiet beta and catastrophic on a busy one — a clerk's
half-finished move-in looks exactly like the walk's. The marker is the only
thing that distinguishes them, so it is required rather than assumed.

⚠ **AND IT PRINTS WHAT IT WILL DELETE BEFORE DELETING IT.** A purge that is
silent about its scope is a purge nobody can check.

⚠ **A DRAFT HOLDS NOTHING, SO DELETING ONE COSTS NOTHING** — `BR-SHL-048`,
PO ruling 2026-08-26: *"Option A - Unitl move in executed, no records
updates."* No account, no payment, no journal entry, no reading and no message
is behind any of these rows, which is why this file may delete them at all.
CLAUDE.md hard rule 4 does not reach here; a form is not a financial record.

Usage, from `06-backend/`:

    DATABASE_URL=… DJANGO_SETTINGS_MODULE=config.settings.local \\
      python ../10-scripts/po20260919_move_in_walk_purge.py --tenant brazosbend

    --dry-run       list and delete nothing
    --marker MIW-123456   only that run
"""

from __future__ import annotations

import argparse
import os
import sys


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tenant", default="brazosbend", help="tenant subdomain")
    parser.add_argument(
        "--marker",
        default="MIW-",
        help="the walk's run marker; the default matches every run of it",
    )
    parser.add_argument(
        "--reference",
        action="append",
        default=[],
        help=(
            "an extra `MVI-…` to delete by name, for a run that died before it "
            "typed its marker anywhere. Still refuses anything with a reason on "
            "it — a park is never this script's to remove."
        ),
    )
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "06-backend"))
    import django

    django.setup()

    from core import tenancy as core_tenancy

    from apps.tenancy.models import Tenant, WizardPark

    tenant = Tenant.objects.get(subdomain=args.tenant)
    with core_tenancy.tenant_context(tenant.id):
        # The three conditions, in the order the docstring argues them. The
        # marker test is done in Python rather than as a JSON query so it reads
        # the same on every backend the suite runs on.
        drafts = WizardPark.objects.filter(flow="move_in", waiting_on="")
        # ⚠ **THE `waiting_on=""` FILTER IS WHAT MAKES `--reference` SAFE.** A
        # named reference that turns out to belong to a PARK is simply not in
        # this queryset, so it cannot be deleted by naming it.
        named = set(args.reference)
        candidates = [
            row
            for row in drafts
            if args.marker in str(row.values) or (row.reference or "") in named
        ]
        missed = named - {row.reference or "" for row in candidates}
        for reference in sorted(missed):
            print(f"! {reference} is not an unparked move-in draft — left alone")
        if not candidates:
            print(f"nothing to purge (marker {args.marker!r})")
            return 0

        print(f"{len(candidates)} draft(s) written by the walk:")
        for row in candidates:
            print(f"  {row.reference or '(no reference)':<14} step {row.step}  {row.subject_label}")
        if args.dry_run:
            print("\n--dry-run: nothing deleted")
            return 0

        removed = 0
        for row in candidates:
            row.delete()
            removed += 1
        remaining = WizardPark.objects.count()
        print(f"\ndeleted {removed}; {remaining} wizard_parks row(s) remain")
        print("⚠ the remaining rows are NOT this walk's — leave them alone.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
