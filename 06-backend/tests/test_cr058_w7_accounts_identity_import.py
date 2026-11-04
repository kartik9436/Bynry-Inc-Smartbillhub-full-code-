# ── Trace ──────────────────────────────────────────────
# Change:  CR-058 W7 — the bulk accounts import learns who the customer is,
#          the discarded `Customer #` column is read (DEF-2593), and the second
#          accounts-import door is closed (DEF-2592).
# Ruling:  PO 2026-09-01, verbatim: *"Without identifier we cannot create
#          Customer ID or master account ot regular account"*, answered on this
#          import as *give it identity columns too*.
# Rules:   BR-CUS-1041 (this rule) · BR-CUS-1042 (the Customer # column is
#          READ) · BR-CUS-1043 (one accounts-import door) · BR-CUS-1022 (which
#          identifier counts) · BR-CUS-1023 (the creation minimum, unchanged) ·
#          BR-CUS-054 (customer_ref is the LEGACY key) · BR-MET-1030 (the
#          premises import's identical shape) · CLAUDE.md law 7 (prove the
#          guard RED first)
# Screens: WFL-01.accounts.2 (the mapping) · .3 (validation) · .5 (the receipt)
# ───────────────────────────────────────────────────────
"""CR-058 W7 — a name and one identifier loads; a name alone loads nothing.

WHAT THIS FILE MEASURES
-----------------------
The ruling has two outcomes and both are COUNTS on a receipt, because that is
the whole mitigation: without them a migration that identified half its
customers looks identical to one that identified all of them, and the utility
finds out at its first bill run.

    name + at least one identifier  ->  the account loads, its customer is
                                        matched-or-created
    name alone                      ->  NOTHING loads for that row, and the
                                        receipt counts it as needing one

Every case asserts the count is RIGHT **and** non-zero in the case that produces
it. A count reading zero because nothing was measured satisfies every relational
assertion (`CR-055`'s lesson, one rule later).

WHAT WAS PROVED RED FIRST (r11 step 2d, hard-won law 7)
--------------------------------------------------------
⚠ **ALL SEVENTEEN CASES WERE RUN ON A CLEAN WORKTREE AT THE BRANCH TIP — the
product as it stood before this lane, with only this file copied in — AND ALL
SEVENTEEN FAILED.** The failures are quoted from that run rather than
reconstructed, because a suite that cannot be shown failing is a suite nobody
knows is connected to anything::

      17 failed, 4 warnings in 129.11s

Four shapes, and each names a different half of the wave:

* The identity columns did not exist, so the template could not offer them and
  the mapping step refused the file outright::

      E   AttributeError: module 'apps.metering.import_runs' has no attribute
          'ACCOUNT_IDENTITY_COLUMN_NAMES'
      E   KeyError: 'customer_ssn'
      E   core.errors.ValidationError: VAL-002
          (metering.import.unknown_mapping_target)

  ⚠ **THE `VAL-002` ONE IS THE INTERESTING FAILURE.** Eleven cases died there —
  not on an assertion about the ruling, but on stage 2 refusing a mapping target
  the product had never heard of. The rule could not even be reached to be wrong.

* The retired three-step door still staged and still committed::

      E   Failed: DID NOT RAISE BizError

* Neither stage-3 rule was declared, so a rehearsal had nothing to say about a
  row it was about to load and then refuse::

      E   AssertionError: ACC.CUSTOMER_IDENTITY_REQUIRED must be declared for
          the accounts target

**AND ONE GUARD WAS BROKEN DELIBERATELY AFTERWARDS TO SEE IT BITE**, because
absence proves less than reversal. `_identity_counts` was made to return `{}` —
the rows are still rejected and the run is still correct, and the RECEIPT simply
stops saying so. That is the exact failure the count exists to prevent, and it
is the one a green suite would otherwise have shipped::

      E   AssertionError: the receipt must be able to say how many rows need an
          identifier
      E   assert 0 == 2
      2 failed, 15 deselected

⚠ **NOTE WHICH TWO WENT RED AND WHICH FIFTEEN DID NOT.** Every assertion about
what was WRITTEN still passed with the receipt lying: no account existed, no
customer existed, the rejects carried their sentences. A migration that
identified half its customers would have looked finished on screen and been
correct in the database, which is why the figure is asserted separately from the
rows.

WHAT IS DELIBERATELY *NOT* CHANGED, ASSERTED SO NOBODY BUILDS IT
-----------------------------------------------------------------
* **`customer_ref` is not an identifier and must never become one.** It is a
  reconciliation key into the utility's OLD system: it names a row in somebody
  else's database, not a person. `test_cr058_w7__a_legacy_reference_is_not_an_
  identifier` is the assertion that goes red if a lane "helpfully" counts it.
* **`Customer #` is not an identifier either**, for the same reason one column
  along: it names a row of OURS.
* **A row whose account is already on file is exempt** — an *Insert & update*
  re-run creates nothing, so the rule has nothing to govern there, and applying
  it would refuse the corrected re-run of a file that loaded lawfully yesterday.
* **Every new column is OPTIONAL in the file.** A required one is refused at
  stage 2 for the whole upload, which would turn a rule about rows into a rule
  about files.
"""

from decimal import Decimal

import pytest

from apps.customers import models as customers_models
from apps.customers import services as customers_services
from apps.metering import import_rules, import_runs
from core import errors

from tests.test_us_met_helpers import *  # noqa: F401,F403
from tests.test_us_met_helpers import (  # noqa: F401
    brazos,
    # ⚠ **DANA AND NOT MARCUS, AND IT IS THE RULE UNDER TEST THAT DECIDES IT.**
    # A file whose rows are ALL rejected is over `BR-MET-098`'s approval bar
    # (5% of rows, or ten of them), and only an owner or an admin may approve a
    # load past it. A billing clerk would meet `metering.import.approver_role`
    # on every negative case here — a refusal about a ROLE standing in front of
    # every assertion about IDENTITY.
    dana,
    make_premises,
    make_unit,
    tenant_ctx,
)
from tests.test_us_cus_003_account_write import _plan  # noqa: E402

pytestmark = pytest.mark.django_db

ALL_OFF = {key: False for key in import_runs.ROW_HANDLING_KEYS}

#: ⚠ **THE HEADERS ARE THE OPERATOR'S SPELLING, NOT OURS**, the same posture the
#: premises suite takes: a change to `ACCOUNTS_ALIASES` that stopped recognising
#: `SSN` goes red here rather than silently offering the column unmapped.
HEADERS = (
    "UNIT_REF,ACCT,NAME,CUST_ID,CUSTOMER #,TYPE,PERSON OR COMPANY,"
    "SSN,DRIVING LICENCE,TAX ID,PHONE"
)

MAPPING = {
    "UNIT_REF": "unit_ref",
    "ACCT": "account_no",
    "NAME": "customer_name",
    "CUST_ID": "customer_ref",
    "CUSTOMER #": "customer_no",
    "TYPE": "account_type",
    "PERSON OR COMPANY": "customer_kind",
    "SSN": "customer_ssn",
    "DRIVING LICENCE": "customer_driving_licence",
    "TAX ID": "customer_tax_id",
    "PHONE": "phone",
}


def _units(actor, tenant, count=2):
    """Units that can actually take an account.

    A plan and a service point, because `BR-MET-040` and `BR-CUS-022` would
    otherwise refuse rows for a reason that has nothing to do with identity —
    which is how a suite comes to not exercise its own subject (the premises
    suite's first RED, one target along).
    """
    from apps.metering import services as metering_services

    premises = make_premises(actor, services_available=["electric"])
    out = []
    for index in range(count):
        unit = make_unit(actor, premises["id"], label=f"W7 Unit {index}")
        metering_services.assign_unit_plan(
            actor,
            unit["id"],
            {"tariff_id": str(_plan(tenant, service_code="electric").id)},
        )
        metering_services.ensure_service_point(unit["id"], "electric")
        out.append(unit)
    return out


def _row(
    unit_no,
    account_no,
    name,
    *,
    ref="",
    customer_no="",
    kind="",
    ssn="",
    licence="",
    tax_id="",
    phone="",
    account_type="residential",
):
    return (
        f'{unit_no},{account_no},"{name}",{ref},{customer_no},{account_type},'
        f"{kind},{ssn},{licence},{tax_id},{phone}"
    )


def _run(actor, rows, *, mode="insert", mapping=None):
    """Extract → transform → validate → load, through the SAME four functions a
    screen calls. Never a hand-built `ImportRunRow`: a test that assembled one
    would prove nothing about the four stages this wave moves behaviour between.
    """
    run = import_runs.extract(
        actor,
        {
            "target": import_runs.TARGET_ACCOUNTS,
            "source_kind": "file",
            "file_name": "cr058_w7_accounts_identity.csv",
            "content": "\n".join([HEADERS, *rows]) + "\n",
            "session_ref": "sess_cr058_w7",
        },
    )
    import_runs.transform(
        actor, run["id"], {"mapping": mapping or MAPPING, "row_handling": ALL_OFF}
    )
    validated = import_runs.validate(actor, run["id"])
    receipt = import_runs.load(actor, run["id"], {"write_mode": mode, "approved": True})
    return validated, receipt


# ═══════════════════════════════════════════════════════════════════════════
# THE COLUMNS EXIST, AND EVERY ONE OF THEM IS OPTIONAL
# ═══════════════════════════════════════════════════════════════════════════


def test_cr058_w7__the_accounts_template_offers_the_customers_identity(brazos, dana):
    """`BR-CUS-1041` — the ruling cannot fire on a single row without them."""
    with tenant_ctx(brazos):
        offered = {entry["target"] for entry in import_runs.target_columns("accounts")}
        for column in import_runs.ACCOUNT_IDENTITY_COLUMN_NAMES:
            assert column in offered, (
                "CR-058 W7: the accounts template must offer the customer's "
                f"identity columns, or the ruling cannot fire on a single row "
                f"— {column} missing"
            )
        assert "phone" in offered, (
            "the phone identifier is the template's EXISTING phone column and "
            "there is no customer_phone beside it — decision log 2026-09-01, "
            "judgment 1"
        )
        assert "customer_phone" not in offered, (
            "two columns for one fact is a file where a utility fills one and "
            "the matcher reads the other"
        )


def test_cr058_w7__every_new_column_is_optional_so_yesterdays_file_still_loads(brazos, dana):
    """A required column is refused at stage 2 for the WHOLE file, which would
    turn a rule about rows into a rule about uploads. A spreadsheet saved
    yesterday must still map and still load."""
    with tenant_ctx(brazos):
        offered = {entry["target"]: entry for entry in import_runs.target_columns("accounts")}
        for column in import_runs.ACCOUNT_IDENTITY_COLUMN_NAMES:
            assert offered[column]["required"] is False, (
                f"CR-058 W7: {column} must be optional — a required one would "
                "refuse every accounts file every utility already holds"
            )


def test_cr058_w7__no_identifier_column_ships_a_worked_cell(brazos, dana):
    """`DEF-962` on the columns `DEF-962` could not have reached: a worked cell
    here is an invented Social Security number in a file a utility hands its
    staff. The KIND is the one exception and it is not somebody's data."""
    with tenant_ctx(brazos):
        offered = {entry["target"]: entry for entry in import_runs.target_columns("accounts")}
        for column in ("customer_ssn", "customer_driving_licence", "customer_tax_id"):
            assert offered[column].get("sample", "") == "", (
                f"{column} must ship its worked cell EMPTY — DEF-962"
            )
        assert offered["customer_kind"]["sample"] == "person"


# ═══════════════════════════════════════════════════════════════════════════
# THE RULING ITSELF — TWO OUTCOMES, BOTH COUNTED
# ═══════════════════════════════════════════════════════════════════════════


def test_cr058_w7__a_name_and_one_identifier_loads_and_creates_the_customer(brazos, dana):
    """`BR-CUS-1041` first line. A person identified by a phone alone is enough
    — the PO named it in the creation minimum (`BR-CUS-1023`)."""
    with tenant_ctx(brazos):
        units = _units(dana, brazos, 2)
        _validated, receipt = _run(
            dana,
            [
                _row(
                    units[0]["unit_no"],
                    "A-70001",
                    "Harmon, Luis",
                    kind="person",
                    ssn="123-45-6789",
                ),
                _row(
                    units[1]["unit_no"],
                    "A-70002",
                    "Cedar Holdings LLC",
                    kind="company",
                    tax_id="74-1234567",
                ),
            ],
        )
        assert receipt["counts"]["created"] == 2
        assert receipt["receipt"]["customers_created"] == 2, (
            "a row with a name and an identifier must get its customer created"
        )
        assert receipt["receipt"]["accounts_awaiting_identity"] == 0

        for number in ("A-70001", "A-70002"):
            account = customers_models.Account.objects.get(
                tenant_id=brazos.id, account_no=number
            )
            link = customers_models.CustomerAccount.objects.get(account=account)
            assert link.customer.customer_no, (
                "BR-CUS-1041: the account loads AND its customer is created"
            )


def test_cr058_w7__a_name_alone_loads_nothing_and_is_counted(brazos, dana):
    """`BR-CUS-1041` second line, and the count is the whole mitigation.

    ⚠ **THE ROW IS NOT SILENTLY DROPPED.** It carries the operator's own
    sentence, so the rejects file says which rows and why."""
    with tenant_ctx(brazos):
        units = _units(dana, brazos, 2)
        validated, receipt = _run(
            dana,
            [
                _row(units[0]["unit_no"], "A-70003", "Alvarez, Rosa"),
                _row(units[1]["unit_no"], "A-70004", "Nguyen, Bao"),
            ],
        )
        assert receipt["counts"]["created"] == 0, (
            "BR-CUS-1041: a row with a name and no identifier must create NOTHING"
        )
        assert not customers_models.Account.objects.filter(
            tenant_id=brazos.id, account_no__in=["A-70003", "A-70004"]
        ).exists()
        assert not customers_models.Customer.objects.filter(
            tenant_id=brazos.id, display_name="Alvarez, Rosa"
        ).exists()
        assert receipt["receipt"]["accounts_awaiting_identity"] == 2, (
            "the receipt must be able to say how many rows need an identifier"
        )
        codes = {row["code"] for row in validated.get("rules", []) if row.get("hits")}
        assert "ACC.CUSTOMER_IDENTITY_REQUIRED" in codes, (
            "stage 3 must say it on the operator's own file — a rehearsal that "
            "promises rows the commit refuses is DEF-544's defect"
        )


def test_cr058_w7__the_rejected_row_says_why_in_the_operators_words(brazos, dana):
    """`DEF-2519`'s posture: no rule id, no internal code, and the operator's
    own cell rather than a uuid (B14 rules 31 and 32)."""
    with tenant_ctx(brazos):
        units = _units(dana, brazos, 1)
        _validated, receipt = _run(
            dana, [_row(units[0]["unit_no"], "A-70005", "Alvarez, Rosa")]
        )
        assert receipt["counts"]["created"] == 0
        rejects = [row for row in receipt.get("rejects", []) if row.get("problem")]
        assert rejects, "a rejected row leaves this run NAMED, never silently dropped"
        sentence = " ".join(f"{row['problem']} {row.get('fix_hint') or ''}" for row in rejects)
        assert "Alvarez, Rosa" in sentence
        for forbidden in ("BR-CUS", "ACC.", "verdict", "None"):
            assert forbidden not in sentence, (
                f"B14 rule 32: no rule id or internal code in clerk-facing copy — {forbidden}"
            )


def test_cr058_w7__an_identifier_under_the_wrong_kind_is_refused_by_name(brazos, dana):
    """`BR-CUS-1022` — a Social Security number under a company is stored where
    the company matcher never looks, so it is refused rather than filed."""
    with tenant_ctx(brazos):
        units = _units(dana, brazos, 1)
        _validated, receipt = _run(
            dana,
            [
                _row(
                    units[0]["unit_no"],
                    "A-70006",
                    "Cedar Holdings LLC",
                    kind="company",
                    ssn="123-45-6789",
                )
            ],
        )
        assert receipt["counts"]["created"] == 0
        assert receipt["receipt"]["accounts_identity_mismatch"] == 1
        assert receipt["receipt"]["accounts_awaiting_identity"] == 0, (
            "two counters and not one: *find an identifier* and *say which kind* "
            "are different jobs for the person fixing the file (DEF-771 clause 3)"
        )


def test_cr058_w7__an_identifier_with_no_stated_kind_cannot_be_judged(brazos, dana):
    """`identity_match.creation_minimum` returns MISSING_KIND for exactly this,
    and has since it was signed. Which identifier counts depends on the answer,
    so there is no test to apply."""
    with tenant_ctx(brazos):
        units = _units(dana, brazos, 1)
        _validated, receipt = _run(
            dana,
            [_row(units[0]["unit_no"], "A-70007", "Harmon, Luis", phone="+1 512 555 0184")],
        )
        assert receipt["counts"]["created"] == 0
        assert receipt["receipt"]["accounts_identity_mismatch"] == 1


def test_cr058_w7__a_legacy_reference_is_not_an_identifier(brazos, dana):
    """⛔ **THE TRAP THE RULING NAMES BY NAME.** `customer_ref` is a
    reconciliation key into the utility's OLD system — it identifies a ROW in
    somebody else's database, not a PERSON — and satisfying the minimum with it
    is the invented value the ruling forbids. The matcher would then read a
    foreign primary key as identity evidence."""
    with tenant_ctx(brazos):
        units = _units(dana, brazos, 1)
        _validated, receipt = _run(
            dana,
            [_row(units[0]["unit_no"], "A-70008", "Alvarez, Rosa", ref="CUST-119")],
        )
        assert receipt["counts"]["created"] == 0, (
            "customer_ref is a key into somebody else's database, never identity"
        )
        assert receipt["receipt"]["accounts_awaiting_identity"] == 1


def test_cr058_w7__our_own_customer_number_is_not_an_identifier_either(brazos, dana):
    """`BR-CUS-1042` — a quoted `Customer #` LINKS or names a new row's number.
    It names a ROW of ours, so it evidences nobody and creates nothing on its
    own. The same line `customer_ref` sits on, one column along."""
    with tenant_ctx(brazos):
        units = _units(dana, brazos, 1)
        _validated, receipt = _run(
            dana,
            [_row(units[0]["unit_no"], "A-70009", "Alvarez, Rosa", customer_no="C-90411")],
        )
        assert receipt["counts"]["created"] == 0
        assert receipt["receipt"]["accounts_awaiting_identity"] == 1


def test_cr058_w7__an_account_already_on_file_is_exempt(brazos, dana):
    """⚠ **THE EXEMPTION, AND IT IS WHY A CORRECTED RE-RUN STILL WORKS.** An
    *Insert & update* row creates no account and no customer, so `BR-CUS-1041`
    has nothing to govern — and applying it would refuse the re-upload of a file
    that loaded lawfully yesterday."""
    with tenant_ctx(brazos):
        units = _units(dana, brazos, 1)
        _run(
            dana,
            [
                _row(
                    units[0]["unit_no"],
                    "A-70010",
                    "Harmon, Luis",
                    kind="person",
                    ssn="123-45-6789",
                )
            ],
        )
        # The corrected re-run: the same account, and the operator has dropped
        # the identity columns from their second file.
        _validated, receipt = _run(
            dana,
            [_row(units[0]["unit_no"], "A-70010", "Harmon, Luis")],
            mode="upsert",
        )
        assert receipt["counts"]["updated"] == 1, (
            "a row already on file updates and creates nothing, so the identity "
            "rule has nothing to govern there"
        )
        assert receipt["receipt"]["accounts_awaiting_identity"] == 0


# ═══════════════════════════════════════════════════════════════════════════
# DEF-2593 — THE `Customer #` COLUMN IS READ
# ═══════════════════════════════════════════════════════════════════════════


def test_cr058_w7__a_quoted_customer_number_is_kept(brazos, dana):
    """`BR-CUS-1042` / `DEF-2593`. The column was offered, auto-mapped, reported
    `Matched` at stage 2 and dropped on the floor: a utility migrating with its
    own customer numbers lost every one."""
    with tenant_ctx(brazos):
        units = _units(dana, brazos, 1)
        _run(
            dana,
            [
                _row(
                    units[0]["unit_no"],
                    "A-70011",
                    "Harmon, Luis",
                    customer_no="C-90411",
                    kind="person",
                    ssn="123-45-6789",
                )
            ],
        )
        account = customers_models.Account.objects.get(
            tenant_id=brazos.id, account_no="A-70011"
        )
        link = customers_models.CustomerAccount.objects.get(account=account)
        assert link.customer.customer_no == "C-90411", (
            "DEF-2593: the file said C-90411 and the product must keep it"
        )


def test_cr058_w7__a_quoted_number_already_on_file_links_instead_of_duplicating(
    brazos, dana
):
    """The reconciliation the column exists for: one number, one customer, many
    accounts — `BR-CUS-054`'s landlord case reached by OUR key."""
    with tenant_ctx(brazos):
        units = _units(dana, brazos, 2)
        _run(
            dana,
            [
                _row(
                    units[0]["unit_no"],
                    "A-70012",
                    "Cedar Holdings LLC",
                    customer_no="C-90422",
                    kind="company",
                    tax_id="74-1234567",
                ),
                _row(
                    units[1]["unit_no"],
                    "A-70013",
                    "Cedar Holdings LLC",
                    customer_no="C-90422",
                    kind="company",
                    tax_id="74-1234567",
                ),
            ],
        )
        holders = customers_models.Customer.objects.filter(
            tenant_id=brazos.id, customer_no="C-90422"
        )
        assert holders.count() == 1, "one quoted number is ONE customer row"
        assert (
            customers_models.CustomerAccount.objects.filter(customer=holders.first()).count()
            == 2
        ), "two accounts, one customer — that is what the column is for"


def test_cr058_w7__the_customer_series_moves_past_the_numbers_the_file_quoted(
    brazos, dana
):
    """`DEF-577`'s arithmetic on the second series `DEF-2593` opened: a file
    quoting a high number against a counter standing at 12 would otherwise
    collide the first time a clerk adds a customer by hand.

    ⚠ **THE QUOTED NUMBER IS RENDERED FROM THE TENANT'S OWN FORMAT, NOT TYPED.**
    A literal here would be this test inventing a numbering scheme, and on a
    tenant whose series is spelled differently the catch-up would correctly move
    nothing and the assertion would fail for the wrong reason.
    """
    from apps.metering import seams as metering_seams
    from core import numbering as core_numbering

    with tenant_ctx(brazos):
        today = metering_seams.tenant_today()
        fmt = metering_seams.number_series_format(core_numbering.CUSTOMER)
        assert fmt, "the customer series is seeded at provisioning (CR-030 W0)"
        quoted = core_numbering.render(fmt, 90433, today)

        units = _units(dana, brazos, 1)
        _run(
            dana,
            [
                _row(
                    units[0]["unit_no"],
                    "A-70014",
                    "Harmon, Luis",
                    customer_no=quoted,
                    kind="person",
                    ssn="123-45-6789",
                )
            ],
        )
        nxt = core_numbering.next_number(core_numbering.CUSTOMER, today)
        assert nxt != quoted, "the series must not re-issue a number the file brought in"
        assert core_numbering.sequence_of(fmt, nxt, today) > 90433, (
            "forward-only, past the file's own highest number (DEF-577)"
        )


# ═══════════════════════════════════════════════════════════════════════════
# DEF-2592 — THERE IS ONE ACCOUNTS-IMPORT DOOR
# ═══════════════════════════════════════════════════════════════════════════


def test_cr058_w7__the_retired_three_step_import_refuses(brazos, dana):
    """`BR-CUS-1043`. Its screen was deleted (`DEF-611`), its endpoints stayed
    mounted, and it served rules the PO reversed: it allocated an account number
    for a blank cell and required no customer name. After `BR-CUS-1041` it would
    additionally have been the one door that creates accounts with no identity."""
    with tenant_ctx(brazos):
        with pytest.raises(errors.BizError) as staged:
            customers_services.stage_account_import(dana, {"content": "unit_ref\nU-1\n"})
        assert staged.value.message_key == "customers.import.retired_use_import_runs"

        with pytest.raises(errors.BizError) as committed:
            customers_services.commit_account_import(
                dana, "00000000-0000-0000-0000-000000000000", {}
            )
        assert committed.value.message_key == "customers.import.retired_use_import_runs"


def test_cr058_w7__the_retired_door_wrote_nothing_on_its_way_out(brazos, dana):
    """The refusal is the FIRST statement, before the batch row: a door that
    staged 2,000 people's names and then refused would leave PII behind for a
    door nobody can commit."""
    with tenant_ctx(brazos):
        before = customers_models.AccountImportBatch.objects.count()
        with pytest.raises(errors.BizError):
            customers_services.stage_account_import(dana, {"content": "unit_ref\nU-1\n"})
        assert customers_models.AccountImportBatch.objects.count() == before


# ═══════════════════════════════════════════════════════════════════════════
# THE RULES ARE DECLARED, AND THEY REJECT RATHER THAN FLAG
# ═══════════════════════════════════════════════════════════════════════════


def test_cr058_w7__both_rules_reject_rather_than_flag():
    """⚠ **WHERE THE PREMISES TWINS WARN, THESE REJECT, AND IT IS NOT SEVERITY
    TASTE.** On premises the ADDRESS still loads and only the owner account is
    skipped. Here nothing loads at all, so a warning would let the rehearsal
    print *"will create 1,213"* over rows the commit refuses — `DEF-965`'s
    complaint and `DEF-544`'s law."""
    declared = {rule.code: rule for rule in import_rules.PLATFORM_CATALOG["accounts"]}
    for code in ("ACC.CUSTOMER_IDENTITY_REQUIRED", "ACC.CUSTOMER_IDENTITY_MISMATCH"):
        assert code in declared, f"{code} must be declared for the accounts target"
        assert declared[code].severity == import_rules.ERROR
        assert declared[code].action == import_rules.REJECT_ROW
