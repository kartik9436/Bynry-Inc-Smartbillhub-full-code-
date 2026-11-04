# ── Trace ──────────────────────────────────────────────
# Defect:  DEF-MET-6304 — the Premises list's Owner cell reads "No name
#          recorded · AC-2026-00051" on every row that HAS an account. The
#          number is right; the sentence is false. The name is recorded — the
#          list never asked for it.
# Rules:   BR-MET-1181 (a premises names its master account; the batched read)
#          · B14 rule 31 (no database id is ever the visible value of a field)
#          · B14 rule 33 (a FACT on screen is six words or fewer)
#          · BR-MET-151 clause 3 (nothing is derived from a free-text name)
#          · CLAUDE.md hard-won law 1 (a sentence claiming a cause is not the
#          cause) · DEF-324 (the batched seam this must not loop over)
# Screens: S14 premises list
# ───────────────────────────────────────────────────────
"""The list can name the owner it has already read — in the SAME batched read.

⛔ **PROVED RED FIRST, IN THE HARNESS THAT RUNS IT (hard-won law 7).** Every
case below was run under `pytest` against the tip this lane started from
(`a162557c0`) before a line of the fix existed. The failures:

    test_def_met_6304__the_batched_read_carries_the_name
        KeyError: 'name'
    test_def_met_6304__a_list_row_serves_the_owner_name_flat
        KeyError: 'master_account_name'
    test_def_met_6304__the_cell_a_clerk_reads_names_the_owner
        AssertionError: assert 'No name recorded · AC-…' == 'Harrow Estates LLC · AC-…'
    test_def_met_6304__the_name_costs_a_constant_number_of_statements
        KeyError: 'name'

⚠ **THE BRIEFING FOR THIS FIX SAID THE NAME WAS *"A PLAIN COLUMN ON THE ACCOUNT
ROW THAT BATCHED QUERY ALREADY READS"*. IT IS NOT, AND THAT IS WHY THE STATEMENT
COUNT IS ASSERTED RATHER THAN ASSUMED.** `accounts` HAS NO `name` COLUMN. The
name a clerk sees is the account's PRIMARY CONTACT's `full_name`, in the
`contacts` table — `customers.selectors.account_row` has always served it that
way, which is why the DETAIL screen shows the real name and the LIST does not.
So the name cannot ride free on the existing statement; it costs **one more, for
the whole page**, through `primary_contact_names_for`, which is the batched read
`DEF-2723` already built for the accounts list.

⛔ **ONE MORE PER PAGE IS THE WHOLE CLAIM AND IT IS WHAT
`test_…_costs_a_constant_number_of_statements` PINS.** `DEF-324` measured the
alternative at *47 of 118 profiled seconds answering one question 304 times*, so
a count alone proves nothing: 51 statements is a fine number for a page of 25
and a catastrophe for a page of 1. **The case below therefore compares two page
sizes and asserts the cost did not follow the page** — the only shape of
assertion that can tell a batch from an N+1.

⚠ **THE HONEST ABSENCE IS ASSERTED TOO.** An account with no contact still reads
*"No name recorded"*, and that sentence is then TRUE. Removing it would have
been the mirror-image defect: `DEF-CUS-6295`'s shape, a correct absence that
says nothing.
"""

import json
import pathlib
import re

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext

from apps.customers import models as cus
from apps.customers import selectors as cus_selectors
from apps.metering import selectors, services

from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import tenant_ctx

#: `BR-CUS-1114` (PO 2026-10-02) — an owner's master account is raised only on
#: a building of two or more homes, so every address this file saves with an
#: owner is saved with two. The single-home refusal is tested by name in
#: `tests/test_br_cus_1114_master_only_multi_unit.py`.
TWO_HOMES = [{"label": "Unit 1"}, {"label": "Unit 2"}]

pytestmark = pytest.mark.django_db

REPO = pathlib.Path(__file__).resolve().parents[2]
LOCALES = REPO / "07-frontend/src/i18n/locales"

#: The form's answers for an identified company — the shape `AddPremisesWizard`
#: posts, copied from `test_br_met_1181_premises_master_account.py` so a case
#: about the NAME cannot accidentally also be a case about identification.
IDENTIFIED_COMPANY = {
    "owner_kind": "company",
    "owner_tax_id": "74-3182640",
    "owner_account_type": "commercial",
}


def _premises_with_an_owner_account(actor, address, owner):
    """One address whose master account exists and whose contact is named."""
    created = services.create_premises(
        actor, {"units": TWO_HOMES, "address_line": address, "owner_manager": owner, **IDENTIFIED_COMPANY}
    )
    account = cus.Account.objects.get(pk=created["master_account_id"])
    # ⚠ **WRITTEN HERE RATHER THAN ASSUMED OF THE DOOR.** Whether
    # `create_premises` names the contact is `customers`' business and may
    # change; what this file is about is whether the LIST can READ a name that
    # exists. Asserting on a name the door happened to write would make this
    # case go red for somebody else's reason.
    cus.Contact.objects.update_or_create(
        tenant_id=account.tenant_id,
        account=account,
        defaults={"full_name": owner, "is_primary": True},
    )
    return created, account


def owner_cell(row: dict) -> str:
    """`PremisesListPage.tsx`'s Owner branch, in Python.

    ⚠ **IT REPRODUCES THE SCREEN'S THIRD CASE, WHICH IS THE ONLY ONE A LIST ROW
    CAN REACH.** `premisesOwnerContract.premisesOwnerAccount` reads the
    expansion first and the flat number third; a helper here that read
    `master_account` would pass on a payload the list never serves — hard-won
    law 7's *looking at the wrong thing*.
    """
    number = row.get("master_account_no")
    if not number:
        return ""
    return f"{row.get('master_account_name') or 'No name recorded'} · {number}"


def test_def_met_6304__the_batched_read_carries_the_name(brazos, dana):
    """RED before the fix: `KeyError: 'name'`.

    The seam already carries the number, the status and the kind for a whole
    page. The name is the fourth fact about the same account, from the same
    page's ids, and it belongs in the same answer.
    """
    with tenant_ctx(brazos):
        _, account = _premises_with_an_owner_account(dana, "9701 Naming Way", "Harrow Estates LLC")
        served = cus_selectors.master_account_numbers([str(account.id)])

    entry = served[str(account.id)]
    assert entry["name"] == "Harrow Estates LLC"
    assert entry["account_no"] == account.account_no
    # ⛔ The seam's own prohibition, re-asserted because this commit widens it:
    # no balance, no arrears. `DEF-127`'s shape cannot be served cheaply in bulk
    # and a figure on a list is a figure somebody quotes.
    assert "balance" not in entry and "arrears" not in entry


def test_def_met_6304__an_account_with_no_contact_is_an_honest_absence(brazos, dana):
    """The mirror case, and it must keep working.

    An account that genuinely has nobody named still answers `None`, and the
    screen still says *"No name recorded"* — which is now TRUE, because the list
    asked. Serving an empty string, or omitting the key, would make a real
    absence indistinguishable from a question nobody put.
    """
    with tenant_ctx(brazos):
        created, account = _premises_with_an_owner_account(
            dana, "9703 Naming Way", "Anonymous Holdings"
        )
        cus.Contact.objects.filter(account=account).delete()
        served = cus_selectors.master_account_numbers([str(account.id)])

    assert served[str(account.id)]["name"] is None
    assert served[str(account.id)]["account_no"] == account.account_no


def test_def_met_6304__a_list_row_serves_the_owner_name_flat(brazos, dana):
    """RED before the fix: `KeyError: 'master_account_name'`.

    ⚠ **FLAT, BESIDE `master_account_no`, AND NOT INSIDE AN EXPANSION.** The
    list may not expand an account (`DEF-324`), so `master_account` stays
    `None` and `master_account_expanded` stays `False` — both re-asserted here,
    because a lane that "helpfully" expanded the account would make the name
    appear and re-buy the defect in the same commit.
    """
    with tenant_ctx(brazos):
        created, _ = _premises_with_an_owner_account(dana, "9705 Naming Way", "Harrow Estates LLC")
        rows = list(selectors.premises_list().filter(pk=created["id"]))
        numbers = selectors.premises_master_account_numbers(rows)
        served = selectors.premises_detail_dict(
            rows[0], with_owner_account=False, master_account_numbers=numbers
        )

    assert served["master_account_name"] == "Harrow Estates LLC"
    assert served["master_account_no"] == created["master_account_no"]
    assert served["master_account"] is None
    assert served["master_account_expanded"] is False


def test_def_met_6304__the_cell_a_clerk_reads_names_the_owner(brazos, dana):
    """RED before the fix: the cell read `No name recorded · AC-…`.

    ⛔ **THIS IS THE ONE ASSERTION THE PO'S COMPLAINT IS ABOUT.** Every other
    case here is about a key; this one is about the sentence a clerk reads
    beside a real account number.
    """
    with tenant_ctx(brazos):
        created, _ = _premises_with_an_owner_account(dana, "9707 Naming Way", "Harrow Estates LLC")
        rows = list(selectors.premises_list().filter(pk=created["id"]))
        served = selectors.premises_detail_dict(
            rows[0],
            with_owner_account=False,
            master_account_numbers=selectors.premises_master_account_numbers(rows),
        )

    assert owner_cell(served) == f"Harrow Estates LLC · {created['master_account_no']}"
    assert "No name recorded" not in owner_cell(served)


def test_def_met_6304__an_export_row_still_asks_for_no_account_at_all(brazos, dana):
    """The opt-in batch is still opt-in, and the name did not open a back door.

    ⚠ **`exports.PREMISES` HAS NO PAGE TO BATCH OVER.** A per-row fallback would
    put one statement per property into a file that runs over the whole
    register — `DEF-324` re-created in the one place `NFR-3` cares about most.
    So a caller that passes no `master_account_numbers` gets `None` for the name
    exactly as it already gets `None` for the number.
    """
    with tenant_ctx(brazos):
        created, _ = _premises_with_an_owner_account(dana, "9709 Naming Way", "Harrow Estates LLC")
        rows = list(selectors.premises_list().filter(pk=created["id"]))
        served = selectors.premises_detail_dict(rows[0], with_owner_account=False)

    assert served["master_account_no"] is None
    assert served["master_account_name"] is None
    assert served["master_account_id"] == created["master_account_id"]
    assert served["master_account_expanded"] is False


def test_def_met_6304__the_detail_names_the_owner_from_its_own_expansion(brazos, dana):
    """The DETAIL pays for an expansion already, so the name comes out of THAT
    rather than out of a second read — *"reading it twice would be a second
    answer to one question"*, which is `_premises_master_account_cells`' own
    rule for the NUMBER and is now the rule for the name beside it.
    """
    with tenant_ctx(brazos):
        created, _ = _premises_with_an_owner_account(dana, "9711 Naming Way", "Harrow Estates LLC")
        served = selectors.premises_detail(created["id"])

    assert served["master_account_expanded"] is True
    assert served["master_account"]["name"] == "Harrow Estates LLC"
    assert served["master_account_name"] == "Harrow Estates LLC"


def test_def_met_6304__the_name_costs_a_constant_number_of_statements(brazos, dana):
    """⛔ **THE ASSERTION THAT STOPS THIS BECOMING `DEF-324` AGAIN.**

    A statement COUNT proves nothing on its own — 51 is fine for a page of 25
    and a catastrophe for a page of 1. What proves a batch is that **the cost
    did not follow the page**, so this builds two pages of different sizes with
    a DIFFERENT owner account on every row and asserts the seam spent the same
    number of statements on both.

    ⚠ **A DIFFERENT ACCOUNT PER ROW IS LOAD-BEARING.** A per-row implementation
    that memoised by account id would spend one statement on a page of six rows
    sharing one owner and would still be an N+1 on a real estate. `DEF-MET-6312`
    is the other N+1 on this same serializer, which is why this case measures
    `premises_master_account_numbers` rather than the whole page.
    """
    with tenant_ctx(brazos):
        ids = []
        for index in range(6):
            created, _ = _premises_with_an_owner_account(
                dana, f"98{index:02d} Counting Way", f"Counting Holdings {index} LLC"
            )
            ids.append(created["id"])

        def cost(how_many):
            rows = list(selectors.premises_list().filter(pk__in=ids[:how_many]))
            assert len(rows) == how_many
            with CaptureQueriesContext(connection) as captured:
                numbers = selectors.premises_master_account_numbers(rows)
            return len(captured.captured_queries), numbers

        small, small_numbers = cost(2)
        large, large_numbers = cost(6)

    # Six DISTINCT accounts, six DISTINCT names — so a memoising per-row read
    # could not have produced this in a constant number of statements.
    assert len({entry["name"] for entry in large_numbers.values()}) == 6
    assert small == large, (
        f"the page's cost followed the page: {small} statements for 2 rows, "
        f"{large} for 6 — that is DEF-324's shape, not a batch"
    )


def test_def_met_6304__the_absence_sentence_obeys_rule_33_in_all_eleven_catalogues():
    """⛔ **THE WORD-COUNT ASSERTION, WRITTEN BEFORE THE WORDS.**

    B14 rule 33 caps ON-SCREEN TEXT BY WHAT IT IS FOR, and *"No name recorded"*
    is a FACT: **six words or fewer, no rationale.** This case exists because
    the first draft of a fallback sentence for this very cell broke the cap on
    the day the defect was filed, and was caught only because the check was
    written first.

    ⚠ **AND IT ASSERTS THE KEY IS PRESENT IN ALL ELEVEN, WHICH IS THE OTHER
    HALF.** A value the catalogues do not hold renders as its own raw key on
    screen while every other assertion in this file passes — a clerk reads
    `metering.premises.owner.unnamed` and nothing goes red.
    """
    key = "metering.premises.owner.unnamed"
    catalogues = sorted(LOCALES.glob("*.json"))
    assert len(catalogues) == 11, f"expected eleven catalogues, found {len(catalogues)}"
    missing, too_long = [], []
    for path in catalogues:
        rows = json.loads(path.read_text(encoding="utf-8"))
        value = rows.get(key)
        if not value:
            missing.append(path.name)
            continue
        # CJK catalogues are not word-delimited, so a word count is meaningless
        # there; the cap is applied as characters, at the same order of size.
        if re.search(r"[぀-ヿ㐀-鿿가-힯]", value):
            if len(value) > 12:
                too_long.append(f"{path.name}: {value!r} ({len(value)} chars > 12)")
        elif len(value.split()) > 6:
            too_long.append(f"{path.name}: {value!r} ({len(value.split())} words > 6)")
    assert not missing, f"the key renders as itself in: {missing}"
    assert not too_long, f"B14 rule 33 — a FACT is six words or fewer: {too_long}"


# ── Lifecycle ─────────────────────────────────────────────
# defect: DEF-MET-6304
# generated: 2026-09-23 by lane OWNER-NAME
# checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=n/a
# exceptions:
#   E3 the statement-count case runs on SQLite like the rest of this suite. It
#      counts statements, which SQLite reports the same way PostgreSQL does, so
#      it is sound here — but the WALL CLOCK it stands for is not, and
#      `10-scripts/def_met_6304_owner_name_readback.py` is the PostgreSQL run
#      that measured the real page (CLAUDE.md hard-won law 14's discipline).
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
