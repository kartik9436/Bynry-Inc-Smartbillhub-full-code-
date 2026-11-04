# ── Trace ──────────────────────────────────────────────
# Story:    US-CUS-019 (EP-CUS-07 S68 — bulk account upload). ⚠ **THE STORY IS
#           NOT RETIRED; ITS DOOR IS.** The five-stage ETL runner has served
#           US-CUS-019 since CR-030 W1, and the suite that measures it is
#           `test_cr030_w1_accounts_import.py`.
# Change:   CR-058 W7 · DEF-2592 — the three-step importer this file was
#           written for is CLOSED (BR-CUS-1043).
# Rules:    BR-CUS-1043 (one accounts-import door) · BR-CUS-1041 (a name and
#           one identifier, or nothing loads) · BR-CUS-046 (the published
#           template, still the rollback's artifact) · BR-CUS-051 (import
#           mechanics = the platform standard) · PO ruling 2026-08-27 (the
#           account number comes off the file) · CLAUDE.md law 7
# ───────────────────────────────────────────────────────
"""US-CUS-019's OLD door — closed, and the parser behind it, still readable.

WHY THIS FILE IS A QUARTER OF ITS FORMER SIZE
---------------------------------------------
`POST /accounts/imports` and its commit route were the product's first accounts
importer. **Their screen was deleted when the five-stage runner replaced it**
(`DEF-611` — the shipped wizard had three of A1's five steps), **and the
endpoints stayed mounted and working.** Nothing in the frontend has called them
since; a script pointed at them worked until today.

They also served rules the PO has since reversed, which is why leaving them was
not an option (`DEF-2592`):

  * **a blank account-number cell was allocated from the series** — PO
    2026-08-27, verbatim: *"we use utility provdied account number here - we
    dont create our own number … if row dont have account number reject it"*;
  * **no customer name was required**, and after `BR-CUS-1041` this would have
    been the ONE door in the product creating accounts with no identity at all.

**Sixteen cases used to run here and twelve of them measured that door.** They
are not deleted quietly — each one's SUBJECT is still tested, on the door that
now does the job:

| what it measured | where it lives now |
|---|---|
| staged, nothing written until commit | the runner's stage 1/2 — `test_cr023_import_stages.py` |
| one `customer_ref` = one customer, many links | `test_cr030_w1_accounts_import.py` |
| "N created · N failed" with per-row reasons | `test_cr047_per_record_load.py` |
| a blank account # | **REVERSED** — `ACC.NUMBER_REQUIRED` rejects it (`test_cr046_identifiers.py`) |
| a missing unit errors, never auto-creates | `ACC.UNIT_ON_FILE` — `test_cr030_w1_accounts_import.py` |
| the same file twice creates no duplicates | the runner's own file-hash unique — `test_cr023_import_stages.py` |
| the bulk path goes through `_open_account` | `test_cr030_w1_accounts_import.py` |
| `BR-CUS-017` refuses an occupied unit | `test_cr047_per_record_load.py` |
| the customer reaches the account detail | `test_cr030_w1_accounts_import.py` · `test_cr056_w2_customer_identity.py` |
| an account with no customer says so | **REVERSED** — no identifier now means no account (`test_cr058_w7_accounts_identity_import.py`) |
| cross-tenant resolution | `test_tenant_isolation.py` and the runner's own world |

**WHAT STAYS HERE, AND WHY IT IS NOT DEAD WEIGHT.** The parser and the published
template are the ROLLBACK: `BR-CUS-1043` refuses the door rather than deleting
it, so the module behind it must keep working, and a template whose own example
row cannot be parsed by its own parser is a rollback nobody can take.

PROVED RED FIRST (hard-won law 7)
---------------------------------
Both refusal cases were run against the branch tip before the guard existed::

      E   Failed: DID NOT RAISE <class 'core.errors.BizError'>

and the parser cases were run after the guard landed, to prove the refusal is at
the DOOR and not in the module — a guard that took the parser down with it would
have made the rollback unusable and every test here would still have passed.
"""

import pytest

from apps.customers import account_import, models, services
from core import errors

from tests.test_us_met_helpers import *  # noqa: F401,F403 — W1/W2 shared fixtures
from tests.test_us_met_helpers import (  # noqa: F401
    brazos,
    dana,
    tenant_ctx,
)

pytestmark = pytest.mark.django_db

HEADER = ",".join(account_import.PUBLISHED_HEADERS) + "\n"

#: One well-formed row of the old template. It is deliberately VALID: the point
#: of the cases below is that a good file is refused too, because the door is
#: closed and not because the file is wrong.
GOOD_ROW = (
    'CUST-091,person,"Harmon, Luis",luis.harmon@example.com,+1 (281) 555-0177,'
    "same-as-service,,2205 Cedar Ln · Unit B,residential,,,active,"
    "150.00,2019-03-14,N,Y,84.20,62.10,0.00,121.00,2019-03-14\n"
)


# ══════════════════════════════════════════════════════════════════════════
# BR-CUS-1043 / DEF-2592 — THE DOOR IS CLOSED
# ══════════════════════════════════════════════════════════════════════════
def test_us_cus_019__the_retired_door_refuses_a_perfectly_good_file(brazos, dana):
    """⚠ **THE FILE IS FINE.** A refusal that only fired on a malformed upload
    would leave the door open to every script that already sends a good one,
    which is the whole population this closure is about."""
    with tenant_ctx(brazos):
        with pytest.raises(errors.BizError) as caught:
            services.stage_account_import(dana, {"content": HEADER + GOOD_ROW})
    assert caught.value.message_key == "customers.import.retired_use_import_runs"
    assert caught.value.br_ref == "BR-CUS-1043"


def test_us_cus_019__the_commit_route_refuses_too(brazos, dana):
    """Both halves, because they are two mounted routes and a script may hold a
    batch id from last week. The commit is the one that WROTE accounts under
    the reversed rules, so a closure that stopped only the staging half would
    have left the writing half reachable."""
    with tenant_ctx(brazos):
        with pytest.raises(errors.BizError) as caught:
            services.commit_account_import(
                dana, "00000000-0000-0000-0000-000000000000", {}
            )
    assert caught.value.message_key == "customers.import.retired_use_import_runs"


def test_us_cus_019__the_refusal_is_the_first_statement_and_stages_nothing(brazos, dana):
    """A door that staged two thousand people's names, emails and mailing
    addresses and THEN refused would leave `BR-CUS-045` PII behind for a batch
    nobody can ever commit. The guard runs before the batch row exists."""
    with tenant_ctx(brazos):
        before = models.AccountImportBatch.objects.count()
        rows_before = models.AccountImportRow.objects.count()
        with pytest.raises(errors.BizError):
            services.stage_account_import(dana, {"content": HEADER + GOOD_ROW * 20})
        assert models.AccountImportBatch.objects.count() == before
        assert models.AccountImportRow.objects.count() == rows_before


# ══════════════════════════════════════════════════════════════════════════
# THE ROLLBACK'S OWN ARTIFACTS — the parser and the published template
# ══════════════════════════════════════════════════════════════════════════
def test_us_cus_019_tc13__the_published_template_carries_every_ac1_column():
    """`BR-CUS-046`'s AC-1 enumeration, unchanged.

    ⚠ **KEPT BECAUSE `BR-CUS-1043` REFUSES THE DOOR RATHER THAN DELETING IT.**
    The refusal is two guard clauses; the rollback is removing them, and a
    rollback whose template cannot be read by its own parser is not a rollback.
    """
    body = account_import.template_csv()
    lines = body.splitlines()
    # The template opens with a COMMENT BLOCK: the import order (BR-CUS-047),
    # the row cap, what a blank account # does. The rule travels with the file
    # instead of arriving after the first failed run.
    assert lines[0].startswith("#")
    assert any("BR-CUS-047" in line for line in lines if line.startswith("#"))
    header = next(line for line in lines if not line.startswith("#")).split(",")
    assert header == list(account_import.PUBLISHED_HEADERS)
    for column in (
        "customer_ref",
        "customer_name",
        "account_no",
        "unit_ref",
        "category",
        "subtype",
        "plan_override",
        "status",
        "deposit_amount",
        "deposit_received_on",
        "tax_exempt",
        "autopay",
        "ob_current",
        "ob_31_60",
        "ob_61_90",
        "ob_90_plus",
        "since",
    ):
        assert column in header, f"BR-CUS-046 column missing from the template: {column}"
    # BR-CUS-060: the bill-delivery-day preference was DROPPED. If a future
    # edit re-adds it, this goes red and the ruling gets re-read.
    assert not [h for h in header if "delivery" in h or "bill_day" in h]
    # The template must still be the file this parser reads best.
    parsed = account_import.parse(body)
    assert len(parsed.rows) == 1
    assert parsed.rows[0].errors == []
    assert set(account_import.PUBLISHED_HEADERS) <= set(parsed.mapping)


def test_us_cus_019_tc6__the_row_cap_still_lives_in_the_parser():
    """`BR-CUS-051`'s 10,000-row cap.

    ⚠ **ASSERTED AGAINST `parse` RATHER THAN THE DOOR, AND THE MOVE IS THE
    POINT.** It used to be asserted through `stage_account_import`, which now
    refuses first — so the case would have passed for the wrong reason, on a
    refusal about the door instead of one about the file. A test that cannot
    tell those two apart is worse than no test, because it is trusted
    (`DEF-182`'s lesson, in a suite instead of in a git check).
    """
    content = HEADER + GOOD_ROW * (account_import.ROW_CAP + 1)
    with pytest.raises(ValueError) as caught:
        account_import.parse(content)
    assert account_import.ERR_ROW_CAP in str(caught.value)
