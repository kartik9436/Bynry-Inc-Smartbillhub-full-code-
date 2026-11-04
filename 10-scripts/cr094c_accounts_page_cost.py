"""CR-094-BRC01 step 2 wave C — MEASURE what one page of the accounts list COSTS.

⚠ **WHY A WALL CLOCK CANNOT ANSWER THIS, WHICH IS THE WHOLE REASON THIS FILE
EXISTS.** Step 1 measured `GET /accounts?per=1` at 0.107 s and `?per=50` at
0.102 s and concluded, correctly, that asking for one row costs the same as
asking for fifty. But at 73 accounts BOTH figures are dominated by fixed
overhead — the session, the roll-up, the template — so the same pair of numbers
comes back after the fix, and a lane reading only the clock would report no
improvement over a change that removed 98% of the work. Measured 2026-09-12
after the fix: `per=1` median 0.156 s, `per=50` median 0.157 s. Unchanged, and
meaningless.

**What actually changed is the number of ROWS BUILT, so that is what this
counts.** `account_row` is the per-row builder; every seam read on this screen
is batched over the list handed to `account_rows`, so the count of `account_row`
calls IS the size of the work the request does.

⚠ **AND A STATEMENT COUNT CANNOT ANSWER IT EITHER.** `DEF-2723` made this list
cost a CONSTANT number of statements whatever the page holds, and that guarantee
held throughout: the statements stayed flat while the rows those same statements
built grew with the tenant. `tests/test_def2723_accounts_list_statement_count.py`
was green before this fix and is green after it. Two different properties, two
different instruments, and only one of them could see `NFR-3`.

WHAT IT PRINTS, one line per page size: the rows a request returns, the rows it
BUILDS, and the tenant's total. On the fixed code those first two are equal. On
the code this replaced, the second column was the third for every row.

IT WRITES NOTHING. No seeding, no fixtures, no product code.

USAGE
    cd 06-backend && DJANGO_SETTINGS_MODULE=config.settings.local \\
      DATABASE_URL=postgres://... python3 ../10-scripts/cr094c_accounts_page_cost.py \\
      [--tenant brazosbend]
"""
import argparse
import os
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "06-backend"))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.local")

import django  # noqa: E402

django.setup()

from django.db import connection  # noqa: E402
from django.test.utils import CaptureQueriesContext  # noqa: E402

from apps.customers import selectors  # noqa: E402
from apps.tenancy import models as tenancy_models  # noqa: E402
from core.pagination import ListParams  # noqa: E402
from core.tenancy import tenant_context  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--tenant", default="brazosbend")
    parser.add_argument("--sizes", default="1,10,50")
    args = parser.parse_args()

    tenant = tenancy_models.Tenant.objects.filter(subdomain=args.tenant).first()
    if tenant is None:
        sys.exit(f"no tenant with subdomain {args.tenant!r} on this database")

    built: list = []
    real = selectors.account_row

    def counting(account, **kwargs):
        built.append(account)
        return real(account, **kwargs)

    selectors.account_row = counting  # the module-global the builder resolves
    try:
        with tenant_context(tenant.id):
            total = selectors.account_queryset().count()
            print(f"# {args.tenant}: {total} accounts")
            print(f"# default sort: {selectors.ACCOUNT_DEFAULT_SORT} {selectors.ACCOUNT_DEFAULT_DIR}")
            print()
            print(f"{'per':>5}  {'returned':>8}  {'rows built':>10}  {'statements':>10}  verdict")
            for raw in args.sizes.split(","):
                per = int(raw)
                built.clear()
                with CaptureQueriesContext(connection) as queries:
                    rows, count = selectors.account_page(ListParams(page=1, per=per))
                statements = len(queries.captured_queries)
                verdict = "O(page)" if len(built) <= per else f"O(tenant) — built all {count}"
                print(
                    f"{per:>5}  {len(rows):>8}  {len(built):>10}  {statements:>10}  {verdict}"
                )
            print()
            print("# the DERIVED path, which is O(tenant) BY CONSTRUCTION and says so:")
            for label, params in (
                ("sort=balance", ListParams(page=1, per=1, sort="balance")),
                ("f.balance_gt=1", ListParams(page=1, per=1, filters={"balance_gt": "1"})),
            ):
                built.clear()
                rows, count = selectors.account_page(params)
                print(
                    f"  {label:<16} returned {len(rows)}  built {len(built)}  of {count}"
                    "   (the figure lives in the ledger — BR-CUS-016)"
                )
    finally:
        selectors.account_row = real
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
