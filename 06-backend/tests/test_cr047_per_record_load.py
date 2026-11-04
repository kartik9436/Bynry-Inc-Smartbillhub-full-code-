# ── Trace ──────────────────────────────────────────────
# Story:    US-CUS-019 (accounts cutover through the ONE runner)
#           Screens: S81 (Imports) · WFL-01 stages 3–5
# Change:   CR-047 — per-record load. Tasks 8 (a savepoint per record),
#           9 (a reason and a fix on every failed row), 12 (the two stage-3
#           rules those refusals needed), 13 (the two result CSVs)
#           CR-047 WIDENING (2026-08-29) — ONE assertion in this file moved: the
#           download refusal now raises its OWN key
#           (`metering.import.not_loaded_no_download`) instead of borrowing the
#           rollback door's `metering.import.not_loaded`, whose English ends
#           "…so there is nothing to reverse." Nothing else here changed.
# Rules:    BR-CUS-051 CONFIRMED, verbatim — "Import mechanics = the standard:
#           staged → per-row errors → skip-errors ON → 'N created · N failed'
#           summary → 10,000-row cap" · BR-CUS-017 (one live account per unit)
#           · BR-CUS-022 (an account being activated states its start date) ·
#           BR-MET-090/091 (a rule is a declared row) · CLAUDE.md hard rules
#           4 (immutability), 5 (the ledger writes), 7 (audit)
# Tests:    this file · defect DEF-2519 (critical)
# Impacts:  apps/metering/import_runs.py · import_rules.py · api.py · seams.py
# ───────────────────────────────────────────────────────
"""CR-047 — **one bad row costs one row, not the migration.**

DEF-2519, in its own numbers. `_load_accounts_rows` had no `try` and no
savepoint anywhere in its row loop, and stage 4 wrapped the whole file in one
`transaction.atomic()`. Four failure modes were handled row-by-row because each
was checked BEFORE the write was attempted; every refusal the customers writer
itself raises escaped the loop and took the run with it. So a 1,213-row
migration whose row 63 named a unit that already had a live account left
**ZERO** accounts on file — and the operator was shown one refusal about one
account with no way to tell which of the 1,213 it was.

PO ruling 2026-08-29, verbatim, and it is the whole specification of this file:

    "if it is success then you read next record, if it is fail - you display on
    screen shich record failed and why (dont write to dB) and continue to
    uplaod next record; at the end we need 2 CsV file 1 for success record and
    other for failed records"

    "if account is created then money is also lands"

⚠ **THE RED EVIDENCE, QUOTED (law 7 — prove a guard goes RED before trusting it
green).** `test_task8__…` was run against the pre-CR-047 loader by removing the
per-row `transaction.atomic()` and its `except`, and it failed exactly the way
the defect describes:

    core.errors.BizError: BIZ-STATE (customers.account.unit_already_occupied)
    …
    apps/metering/import_runs.py:6553: in _load_accounts_rows
        result = seams.create_account_from_import(

— the refusal escaping the loop, so `load()` raised and NOTHING was written.
With the savepoint restored the same case answers `created == 2`,
`rejected_at_write == 1`, and the two good accounts are on file.
"""

import csv
import io

import pytest
from django.test import override_settings

from apps.customers import models as customers_models
from apps.metering import import_rules, import_runs, models as metering_models, seams
from core import errors

from tests.test_us_met_helpers import *  # noqa: F401,F403
from tests.test_us_met_helpers import (  # noqa: F401
    brazos,
    dana,
    make_premises,
    make_unit,
    marcus,
    tenant_ctx,
)
from tests.test_us_cus_003_account_write import _plan  # noqa: E402

pytestmark = pytest.mark.django_db

CUTOVER = "2026-08-31"
ALL_OFF = {key: False for key in import_runs.ROW_HANDLING_KEYS}

#: The operator's OWN headers, deliberately not ours — the failures file has to
#: come back under these, in this order, or the point of task 13 is lost.
#: ⛔ **`KIND` AND `SSN` JOINED THE FIXTURE ON 2026-09-01 — `BR-CUS-1041`,
#: `CR-058` W7.** A row carrying a name and no identifier now creates NOTHING,
#: so without them every case below would be measuring an empty run rather than
#: the per-record refusals it is about. `CUST_ID` is the LEGACY key and is
#: explicitly not identity: it names a row in somebody else's database.
#: ⚠ **ONE Social Security number across every row is deliberate and lawful.**
#: A duplicate identifier refuses to LINK and never refuses to SAVE (PO
#: 2026-09-01), and a person needs a date of birth to match STRONGLY
#: (`BR-CUS-089`) — which the PO's four identifiers do not include — so each row
#: still opens under its own customer number and nothing here is joined on a
#: guess. Every account number, figure and outcome below is unchanged.
HEADERS = "UNIT_REF,ACCT,NAME,CUST_ID,TYPE,STATUS,OPENED,CURRENT,KIND,SSN"

MAPPING = {
    "UNIT_REF": "unit_ref",
    "ACCT": "account_no",
    "NAME": "customer_name",
    "CUST_ID": "customer_ref",
    # CR-058 W7 · BR-CUS-1041 — see the note above.
    "KIND": "customer_kind",
    "SSN": "customer_ssn",
    "TYPE": "account_type",
    "STATUS": "status",
    "OPENED": "opened_at",
    "CURRENT": "ob_current",
}


def _units(actor, tenant, count=3):
    """`count` units on one premises, each on a published plan and carrying an
    electric service point — everything BR-MET-040 and BR-CUS-047 need before
    an account may be opened on them."""
    from apps.metering import services as metering_services

    premises = make_premises(actor, services_available=["electric"])
    plan_id = str(_plan(tenant, service_code="electric").id)
    out = []
    for index in range(count):
        unit = make_unit(actor, premises["id"], label=f"CR047 Unit {index}")
        metering_services.assign_unit_plan(actor, unit["id"], {"tariff_id": plan_id})
        metering_services.ensure_service_point(unit["id"], "electric")
        out.append(unit)
    return out


def _run(actor, content, *, options=None, write_mode="insert"):
    run = import_runs.extract(
        actor,
        {
            "target": import_runs.TARGET_ACCOUNTS,
            "source_kind": "file",
            "file_name": "cr047-accounts.csv",
            "content": content,
            "session_ref": "sess_cr047",
            "write_mode": write_mode,
        },
    )
    payload = {"mapping": MAPPING, "row_handling": ALL_OFF}
    if options is not None:
        payload["options"] = options
    import_runs.transform(actor, run["id"], payload)
    import_runs.validate(actor, run["id"])
    return run["id"]


def _rows(run_id):
    return {
        row.row_no: row
        for row in metering_models.ImportRunRow.objects.filter(run_id=run_id).order_by("row_no")
    }


def _read_csv(run_id, kind):
    filename, body = import_runs.results_csv(run_id, kind)
    text = "".join(body)
    return filename, list(csv.reader(io.StringIO(text)))


# ══════════════════════════════════════════════════════════════════════════
# TASK 8 — a savepoint per record
# ══════════════════════════════════════════════════════════════════════════
def test_task8__one_refused_row_costs_one_row_and_not_the_migration(brazos, dana):
    """⛔ **DEF-2519, and the case is chosen so STAGE 3 CANNOT SEE IT.**

    Two rows of ONE file name the SAME free unit and both ask to go live. The
    world stage 3 judges against is read once, before anything is written, so
    that unit is vacant for BOTH rows — `ACC.UNIT_NOT_OCCUPIED` correctly fires
    on neither. Row 1 then takes the unit and row 2 meets `BR-CUS-017` inside
    `customers._make_occupying`, under the advisory lock, which is the only
    place a check-then-act race can be closed.

    That is exactly the refusal that used to escape the loop. Here it costs one
    row: the other two accounts are on file, and the run is `loaded`.
    """
    with tenant_ctx(brazos):
        units = _units(dana, brazos)
        shared = units[0]["unit_no"]
        content = (
            f"{HEADERS}\n"
            f"{shared},A-901,Harmon,CUST-1,residential,active,2024-02-12,84.20,person,123-45-6789\n"
            f"{shared},A-902,Alvarez,CUST-2,residential,active,2024-03-01,10.00,person,123-45-6789\n"
            f"{units[1]['unit_no']},A-903,Okafor,CUST-3,residential,active,2024-04-01,5.00,person,123-45-6789\n"
        )
        run_id = _run(dana, content, options={"cutover_on": CUTOVER})
        receipt = import_runs.load(dana, run_id, {"write_mode": "insert", "approved": True})

        assert receipt["counts"]["created"] == 2
        assert receipt["counts"]["rejected_at_write"] == 1
        assert receipt["receipt"]["rejected_at_write"] == 1

        landed = set(
            customers_models.Account.objects.filter(tenant_id=brazos.id).values_list(
                "account_no", flat=True
            )
        )
        assert {"A-901", "A-903"} <= landed
        assert "A-902" not in landed, "the refused row must have written nothing (PO: dont write to dB)"

        # ⚠ THE ROW ITSELF, because "N created · N failed" is a summary of rows.
        rows = _rows(run_id)
        assert rows[1].outcome == "loaded"
        assert rows[2].outcome == "rejected"
        assert rows[3].outcome == "loaded"
        # The refused row created nothing, so it has nothing to roll back.
        assert rows[2].created_record_id is None

        run = metering_models.ImportRun.objects.get(pk=run_id)
        assert run.status == "loaded"


def test_task8__the_refused_row_leaves_no_audit_row_behind(brazos, dana, audit_rows):
    """The audit write sits INSIDE the savepoint, so a rolled-back row cannot
    leave a record of an account that does not exist. Hard rule 7 is about
    money that MOVED, and no money moved on that row."""
    with tenant_ctx(brazos):
        units = _units(dana, brazos, count=1)
        shared = units[0]["unit_no"]
        content = (
            f"{HEADERS}\n"
            f"{shared},A-911,Harmon,CUST-1,residential,active,2024-02-12,0.00,person,123-45-6789\n"
            f"{shared},A-912,Alvarez,CUST-2,residential,active,2024-03-01,0.00,person,123-45-6789\n"
        )
        run_id = _run(dana, content, options={"cutover_on": CUTOVER})
        import_runs.load(dana, run_id, {"write_mode": "insert", "approved": True})

        created = [
            row for row in audit_rows if row.get("action") == "accounts.created_by_import"
        ]
        assert len(created) == 1, "one account was created, so exactly one audit row"


def test_task8__a_system_fault_still_takes_the_whole_run_down(brazos, dana, monkeypatch):
    """⛔ **THE OTHER HALF OF TASK 8, AND THE EASIER ONE TO GET WRONG.** The
    `except` names `BizError` and `ValidationError` — the catalog's two ways of
    saying *"this ROW's data is wrong"* — and NOT `Exception`.

    A `SysError` is the account-number series being unusable or the ledger
    being unreachable: the next row fails the same way, and a run that reported
    *"1,213 failed"* over one infrastructure fault would be a data-quality
    report about a broken server. It must still abort, with nothing written.
    """
    with tenant_ctx(brazos):
        units = _units(dana, brazos, count=2)
        content = (
            f"{HEADERS}\n"
            f"{units[0]['unit_no']},A-921,Harmon,CUST-1,residential,active,2024-02-12,0.00,person,123-45-6789\n"
            f"{units[1]['unit_no']},A-922,Alvarez,CUST-2,residential,active,2024-03-01,0.00,person,123-45-6789\n"
        )
        run_id = _run(dana, content, options={"cutover_on": CUTOVER})

        def _broken(**kwargs):
            raise errors.SysError(
                errors.SYS_INTERNAL, message_key="customers.account.numbering_unavailable"
            )

        monkeypatch.setattr(import_runs.seams, "create_account_from_import", _broken)
        with pytest.raises(errors.SysError):
            import_runs.load(dana, run_id, {"write_mode": "insert", "approved": True})

        assert not customers_models.Account.objects.filter(
            tenant_id=brazos.id, account_no__in=("A-921", "A-922")
        ).exists()


def test_task8__the_ledger_batch_only_ever_carries_what_landed(brazos, dana):
    """❄️ **GT-16's batch line survives the savepoint, and that is the point of
    checking it.** *"Σ of all opening JEs = Σ of all imported buckets"* is a
    statement about the BATCH; a refused row is rolled back before it can join
    `opening`, so the handoff is Σ of what is actually on file — never Σ of
    what the file asked for."""
    with tenant_ctx(brazos):
        units = _units(dana, brazos, count=2)
        shared = units[0]["unit_no"]
        content = (
            f"{HEADERS}\n"
            f"{shared},A-931,Harmon,CUST-1,residential,active,2024-02-12,100.00,person,123-45-6789\n"
            f"{shared},A-932,Alvarez,CUST-2,residential,active,2024-03-01,55.00,person,123-45-6789\n"
            f"{units[1]['unit_no']},A-933,Okafor,CUST-3,residential,active,2024-04-01,25.00,person,123-45-6789\n"
        )
        run_id = _run(dana, content, options={"cutover_on": CUTOVER})
        receipt = import_runs.load(dana, run_id, {"write_mode": "insert", "approved": True})

        from decimal import Decimal

        # 100.00 + 25.00 — the refused 55.00 is NOT in the books.
        assert Decimal(receipt["counts"]["opening_ar"]) == Decimal("125.00")
        assert receipt["counts"]["with_opening_balance"] == 2


# ══════════════════════════════════════════════════════════════════════════
# TASK 9 — a reason and a fix sentence on every failed row
# ══════════════════════════════════════════════════════════════════════════
def test_task9__a_refused_row_says_why_in_english_and_what_to_do_next(brazos, dana):
    """PO: *"you display on screen shich record failed and why"*. The four
    failure modes this loader already handled write plain English with no ids
    in it; a refusal caught at the write reads exactly the same, because an
    operator cannot tell — and should not have to — which side of a module
    boundary refused their row."""
    with tenant_ctx(brazos):
        units = _units(dana, brazos, count=1)
        shared = units[0]["unit_no"]
        content = (
            f"{HEADERS}\n"
            f"{shared},A-941,Harmon,CUST-1,residential,active,2024-02-12,0.00,person,123-45-6789\n"
            f"{shared},A-942,Alvarez,CUST-2,residential,active,2024-03-01,0.00,person,123-45-6789\n"
        )
        run_id = _run(dana, content, options={"cutover_on": CUTOVER})
        import_runs.load(dana, run_id, {"write_mode": "insert", "approved": True})

        refused = _rows(run_id)[2]
        assert refused.outcome == "rejected"
        assert refused.problem, "a rejected row with no reason is a number with no explanation"
        assert refused.fix_hint, "and one with no next step is a dead end"
        # The operator's OWN reference is the noun, and it names the account
        # that is in the way — both facts they need to decide which is right.
        assert shared in refused.problem
        assert "A-941" in refused.problem
        # ⚠ NO IDS, NO CODES, NO UUIDS — CR-016's no-internal-references rule
        # reaches this screen like any other, and every one of these refusals
        # carries a `unit_id` uuid in its params that must never be printed.
        text = f"{refused.problem} {refused.fix_hint}"
        assert "BIZ-" not in text and "BR-CUS" not in text
        assert str(units[0]["id"]) not in text


def test_task9__an_unmapped_refusal_key_still_gets_an_operator_sentence(brazos, dana):
    """⚠ **A GAP IN THE SENTENCE TABLE MAY NOT PRODUCE A BLANK ROW.** A refusal
    whose `message_key` nobody has written words for falls back to its catalog
    CLASS, and never to `params.detail` — rendering that free text is exactly
    what DEF-322 ruled out. The row still says something a person can read."""
    with tenant_ctx(brazos):
        units = _units(dana, brazos, count=1)
        content = (
            f"{HEADERS}\n"
            f"{units[0]['unit_no']},A-951,Harmon,CUST-1,residential,active,2024-02-12,0.00,person,123-45-6789\n"
        )
        run_id = _run(dana, content, options={"cutover_on": CUTOVER})

        def _refuses(**kwargs):
        # This raise is the SUBJECT of the case: a refusal whose message_key
        # nobody has written words for. core/refusal_catalogue refuses exactly
        # that under the test settings, so it is turned off for this block —
        # the guard and the case are asking the same question from opposite
        # sides, and this is the one place the unresolved key is deliberate.
            with override_settings(REFUSAL_KEYS_MUST_RESOLVE=False):
                raise errors.BizError(
                    errors.BIZ_COMPLETENESS,
                    br_ref="BR-CUS-999",
                    message_key="customers.account.a_rule_nobody_wrote_words_for",
                    params={"detail": "internal diagnostic that must not be shown"},
                )

        import_runs.seams.create_account_from_import  # noqa: B018 — the seam exists
        original = import_runs.seams.create_account_from_import
        import_runs.seams.create_account_from_import = _refuses  # type: ignore[assignment]
        try:
            receipt = import_runs.load(dana, run_id, {"write_mode": "insert", "approved": True})
        finally:
            import_runs.seams.create_account_from_import = original  # type: ignore[assignment]

        assert receipt["counts"]["rejected_at_write"] == 1
        row = _rows(run_id)[1]
        assert row.problem and row.fix_hint
        assert "internal diagnostic" not in f"{row.problem} {row.fix_hint}"


def test_task9__rejected_at_write_is_a_counter_of_its_own(brazos, dana):
    """It is NOT folded into `rejected_existing`. Those rows were judged before
    anything was attempted; these were attempted and turned down, and an
    operator fixes the two in different ways. A run whose `rejected_at_write`
    is not zero is also the signal that stage 3 has a rule to grow."""
    with tenant_ctx(brazos):
        units = _units(dana, brazos, count=1)
        shared = units[0]["unit_no"]
        content = (
            f"{HEADERS}\n"
            f"{shared},A-961,Harmon,CUST-1,residential,active,2024-02-12,0.00,person,123-45-6789\n"
            f"{shared},A-962,Alvarez,CUST-2,residential,active,2024-03-01,0.00,person,123-45-6789\n"
        )
        run_id = _run(dana, content, options={"cutover_on": CUTOVER})
        receipt = import_runs.load(dana, run_id, {"write_mode": "insert", "approved": True})
        counts = receipt["counts"]
        assert counts["rejected_at_write"] == 1
        assert counts["rejected_existing"] == 0
        assert counts["rejected_no_number"] == 0
        assert counts["skipped_existing"] == 0


# ══════════════════════════════════════════════════════════════════════════
# THE CROSS-LANE CONTRACT — `services_linked` → `run.counts["with_services"]`
# ══════════════════════════════════════════════════════════════════════════
def test_contract__services_linked_is_accumulated_and_published(brazos, dana, monkeypatch):
    """PO 2026-08-29: *"if account is created then money is also lands"*.
    `customers.create_from_import` returns `services_linked` per account; this
    is their sum, on the run and on the receipt, for the frontend to render."""
    with tenant_ctx(brazos):
        units = _units(dana, brazos, count=2)
        content = (
            f"{HEADERS}\n"
            f"{units[0]['unit_no']},A-971,Harmon,CUST-1,residential,active,2024-02-12,0.00,person,123-45-6789\n"
            f"{units[1]['unit_no']},A-972,Alvarez,CUST-2,residential,active,2024-03-01,0.00,person,123-45-6789\n"
        )
        run_id = _run(dana, content, options={"cutover_on": CUTOVER})
        original = seams.create_account_from_import

        def _with_services(**kwargs):
            result = original(**kwargs)
            return {**result, "services_linked": 3}

        monkeypatch.setattr(import_runs.seams, "create_account_from_import", _with_services)
        receipt = import_runs.load(dana, run_id, {"write_mode": "insert", "approved": True})
        assert receipt["counts"]["with_services"] == 6
        assert receipt["receipt"]["with_services"] == 6


def test_contract__an_absent_services_linked_is_zero_and_never_a_crash(
    brazos, dana, monkeypatch
):
    """A writer that does not report `services_linked` must read as 0, never as a
    crash — a `KeyError` would take a whole migration down over a dictionary key.

    ⚠ **THIS TEST USED TO PROVE ITSELF BY ACCIDENT AND NO LONGER CAN.** It was
    written while the customers lane was unmerged, so the key was genuinely
    absent and the assertion held for free. `BR-CUS-672` has since landed and the
    writer always reports a count, so the absence must now be MANUFACTURED — the
    same monkeypatch shape the sibling test above uses to inject 3.

    That is the durable form: a fallback proved by a real absence rather than by
    a transitional state of the branch. The old version would have gone quietly
    green again the day someone broke the writer.
    """
    from apps.metering import seams

    real = seams.create_account_from_import

    def without_the_key(**kwargs):
        result = real(**kwargs)
        return {k: v for k, v in result.items() if k != "services_linked"}

    monkeypatch.setattr(seams, "create_account_from_import", without_the_key)
    with tenant_ctx(brazos):
        units = _units(dana, brazos, count=1)
        content = (
            f"{HEADERS}\n"
            f"{units[0]['unit_no']},A-981,Harmon,CUST-1,residential,active,2024-02-12,0.00,person,123-45-6789\n"
        )
        run_id = _run(dana, content, options={"cutover_on": CUTOVER})
        receipt = import_runs.load(dana, run_id, {"write_mode": "insert", "approved": True})
        assert receipt["counts"]["created"] == 1
        assert receipt["counts"]["with_services"] == 0
        assert receipt["receipt"]["with_services"] == 0


# ══════════════════════════════════════════════════════════════════════════
# TASK 12 — the two stage-3 rules
# ══════════════════════════════════════════════════════════════════════════
def test_task12__both_rules_are_declared_for_the_accounts_target_only(brazos):
    """BR-MET-090/091 — a rule is a DECLARED ROW, and both are registered with
    an evaluator this product actually has (a kind absent from `EVALUATORS` is
    reported unavailable and measures nothing)."""
    codes = {rule.code: rule for rule in import_rules.ACCOUNTS_RULES}
    assert "ACC.UNIT_NOT_OCCUPIED" in codes
    assert "ACC.START_DATE_REQUIRED" in codes
    for code in ("ACC.UNIT_NOT_OCCUPIED", "ACC.START_DATE_REQUIRED"):
        rule = codes[code]
        assert rule.target == "accounts"
        assert rule.severity == import_rules.ERROR
        assert rule.action == import_rules.REJECT_ROW
        assert rule.blocks is True
        assert rule.rule_kind in import_rules.EVALUATORS
    assert codes["ACC.UNIT_NOT_OCCUPIED"].sentence == "The unit this account names is free."
    assert (
        codes["ACC.START_DATE_REQUIRED"].sentence
        == "An account you are activating has the date its service started."
    )
    # Neither belongs to any other target's catalogue.
    for target, catalog in import_rules.PLATFORM_CATALOG.items():
        if target == "accounts":
            continue
        assert not {rule.code for rule in catalog} & set(codes) & {
            "ACC.UNIT_NOT_OCCUPIED",
            "ACC.START_DATE_REQUIRED",
        }


def test_task12__a_row_activating_onto_an_occupied_unit_is_rejected_at_stage_3(brazos, dana):
    """BR-CUS-017 asked BEFORE the write instead of underneath it. The unit
    already carries a live account created through the ordinary door, so the
    world stage 3 reads knows it is taken."""
    from apps.customers import services as customers_services

    with tenant_ctx(brazos):
        units = _units(dana, brazos, count=2)
        customers_services.create_account(
            dana,
            {
                "unit_id": str(units[0]["id"]),
                "account_type": "residential",
                "status": "active",
                "opened_at": "2024-01-01",
                "contact": {"full_name": "Sitting Tenant"},
                # ⛔ **`BR-CUS-1024` (PO 2026-09-01) — the counter door refuses
                # an account whose customer identifies nobody, so the SITTING
                # TENANT is identified** (`DEF-2585`, fixed in 450af92b — one
                # of the three tests that went red when BR-CUS-1024 landed and
                # the lane that landed it updated neither suite). These cases
                # are about what a staged
                # row does when it lands on an OCCUPIED unit; without this the
                # refusal fires in the setup and the case never reaches its own
                # subject. A phone is enough for a person and makes no match
                # strong, so nothing else in this file moves.
                "customer": {
                    "display_name": "Sitting Tenant",
                    "kind": "person",
                    "identity": {"phone": "+1 (512) 555-0161"},
                },
            },
        )
        content = (
            f"{HEADERS}\n"
            f"{units[0]['unit_no']},A-991,Harmon,CUST-1,residential,active,2024-02-12,0.00,person,123-45-6789\n"
            f"{units[1]['unit_no']},A-992,Alvarez,CUST-2,residential,active,2024-03-01,0.00,person,123-45-6789\n"
        )
        run_id = _run(dana, content, options={"cutover_on": CUTOVER})

        rows = _rows(run_id)
        assert rows[1].outcome == "rejected"
        assert "already has a live account" in rows[1].problem
        assert rows[2].outcome == "staged", "the free unit's row is untouched"

        # And the rehearsal's verdict is the commit's: the rejected row never
        # reaches the writer, so nothing is refused twice.
        receipt = import_runs.load(dana, run_id, {"write_mode": "insert", "approved": True})
        assert receipt["counts"]["created"] == 1
        assert receipt["counts"]["rejected_at_write"] == 0


def test_task12__a_DRAFT_row_on_an_occupied_unit_is_left_alone(brazos, dana):
    """⚠ **THE HALF THAT MATTERS MOST, BECAUSE OVER-REJECTING IS THE EASIER
    MISTAKE.** BR-CUS-018 starts an account in `pending_activation` unless the
    caller names another status, and a draft never reaches `_make_occupying`:
    it does not occupy the unit and is not billed. A rule that fired on every
    row would reject rows the loader writes without complaint."""
    from apps.customers import services as customers_services

    with tenant_ctx(brazos):
        units = _units(dana, brazos, count=1)
        customers_services.create_account(
            dana,
            {
                "unit_id": str(units[0]["id"]),
                "account_type": "residential",
                "status": "active",
                "opened_at": "2024-01-01",
                "contact": {"full_name": "Sitting Tenant"},
                # ⛔ **`BR-CUS-1024` (PO 2026-09-01) — the counter door refuses
                # an account whose customer identifies nobody, so the SITTING
                # TENANT is identified** (`DEF-2585`, fixed in 450af92b — one
                # of the three tests that went red when BR-CUS-1024 landed and
                # the lane that landed it updated neither suite). These cases
                # are about what a staged
                # row does when it lands on an OCCUPIED unit; without this the
                # refusal fires in the setup and the case never reaches its own
                # subject. A phone is enough for a person and makes no match
                # strong, so nothing else in this file moves.
                "customer": {
                    "display_name": "Sitting Tenant",
                    "kind": "person",
                    "identity": {"phone": "+1 (512) 555-0161"},
                },
            },
        )
        content = (
            f"{HEADERS}\n"
            f"{units[0]['unit_no']},A-993,Harmon,CUST-1,residential,"
            f"pending_activation,2024-02-12,0.00,person,123-45-6789\n"
        )
        run_id = _run(dana, content, options={"cutover_on": CUTOVER})
        assert _rows(run_id)[1].outcome == "staged"
        receipt = import_runs.load(dana, run_id, {"write_mode": "insert", "approved": True})
        assert receipt["counts"]["created"] == 1


def test_task12__a_row_going_live_with_no_start_date_is_rejected_at_stage_3(brazos, dana):
    """BR-CUS-022 — the first bill is counted from `opened_at`, so an account
    being ACTIVATED without one could never be billed. A blank date on a DRAFT
    row is lawful and is left alone in the same file."""
    with tenant_ctx(brazos):
        units = _units(dana, brazos, count=2)
        content = (
            f"{HEADERS}\n"
            f"{units[0]['unit_no']},A-994,Harmon,CUST-1,residential,active,,0.00,person,123-45-6789\n"
            f"{units[1]['unit_no']},A-995,Alvarez,CUST-2,residential,pending_activation,,0.00,person,123-45-6789\n"
        )
        run_id = _run(dana, content, options={"cutover_on": CUTOVER})

        rows = _rows(run_id)
        assert rows[1].outcome == "rejected"
        assert "no date its service started" in rows[1].problem
        assert rows[1].fix_hint and "pending activation" in rows[1].fix_hint
        assert rows[2].outcome == "staged", "a draft needs no start date"

        receipt = import_runs.load(dana, run_id, {"write_mode": "insert", "approved": True})
        assert receipt["counts"]["created"] == 1
        assert receipt["counts"]["rejected_at_write"] == 0


def test_task12__the_status_vocabulary_comes_from_customers(brazos):
    """The seam answers with `customers`' OWN reading of which statuses take a
    unit — `OCCUPYING_BEHAVIOR_CLASSES` over the seeded vocabulary — and never
    with a list this module keeps. A hard-coded copy here would be a second,
    drifting enforcement of BR-CUS-055."""
    from apps.customers import services as customers_services

    with tenant_ctx(brazos):
        codes = seams.occupying_account_status_codes()
        assert codes is not None, "customers ships in-tree, so the seam must answer"
        expected = {
            code.lower()
            for code, _name, behavior in customers_services.SEED_ACCOUNT_STATUSES
            if behavior in customers_services.OCCUPYING_BEHAVIOR_CLASSES
        }
        assert codes == expected
        assert "active" in codes
        assert "pending_activation" not in codes
        assert "closed" not in codes


# ══════════════════════════════════════════════════════════════════════════
# TASK 13 — the two result files
# ══════════════════════════════════════════════════════════════════════════
def test_task13__the_failures_file_is_the_original_row_plus_exactly_two_columns(brazos, dana):
    """⛔ **THE WHOLE POINT OF THE FILE.** The operator's next act is to fix the
    rows and upload again, so the rejects come back under the FILE'S OWN
    headers, in the FILE'S OWN order, carrying the ROW'S OWN cells — with
    `why_it_failed` and `how_to_fix_it` appended and nothing else changed."""
    with tenant_ctx(brazos):
        units = _units(dana, brazos, count=2)
        content = (
            f"{HEADERS}\n"
            f"{units[0]['unit_no']},A-A01,\"Harmon, Luis\",CUST-1,residential,active,2024-02-12,84.20,person,123-45-6789\n"
            f"{units[1]['unit_no']},A-A02,Alvarez,CUST-2,residential,active,,10.00,person,123-45-6789\n"
        )
        run_id = _run(dana, content, options={"cutover_on": CUTOVER})
        import_runs.load(dana, run_id, {"write_mode": "insert", "approved": True})

        filename, rows = _read_csv(run_id, "failures")
        assert filename.endswith("-failures.csv")

        # 1 — the header row: the file's own, in the file's own order, plus two.
        assert rows[0] == [*HEADERS.split(","), "why_it_failed", "how_to_fix_it"]

        # 2 — the row: the operator's own cells, unchanged and unreordered.
        assert len(rows) == 2, "one row failed (blank OPENED on an active account)"
        failed = rows[1]
        assert failed[: len(HEADERS.split(","))] == [
            units[1]["unit_no"],
            "A-A02",
            "Alvarez",
            "CUST-2",
            "residential",
            "active",
            "",
            "10.00",
            # CR-058 W7 — the two identity cells the file carries. They are in
            # the failures file for the same reason every other cell is: it is
            # the operator's OWN row, unchanged and unreordered, so they can fix
            # one column and upload it again.
            "person",
            "123-45-6789",
        ]
        # 3 — and the two appended columns carry the row's own sentences.
        assert "no date its service started" in failed[-2]
        assert failed[-1]


def test_task13__a_comma_in_a_cell_survives_the_round_trip(brazos, dana):
    """`"Harmon, Luis"` is the first row of the CR-030 fixture. A file joined
    with commas instead of written through `csv` would split that account
    across two columns in the file the operator re-uploads."""
    with tenant_ctx(brazos):
        units = _units(dana, brazos, count=1)
        content = (
            f"{HEADERS}\n"
            f'{units[0]["unit_no"]},A-A11,"Harmon, Luis",CUST-1,residential,active,,0.00\n'
        )
        run_id = _run(dana, content, options={"cutover_on": CUTOVER})
        import_runs.load(dana, run_id, {"write_mode": "insert", "approved": True})
        _filename, rows = _read_csv(run_id, "failures")
        assert rows[1][2] == "Harmon, Luis"


def test_task13__the_successes_file_names_what_landed(brazos, dana):
    """Account number, customer name, unit reference, opening total, and how
    many services it inherited. The opening total is the WRITER'S figure,
    carried — never re-summed from the four bucket cells, because
    `import_writer` splits a negative bucket into a carried credit and a second
    sum would disagree with the ledger on exactly the rows that matter."""
    with tenant_ctx(brazos):
        units = _units(dana, brazos, count=2)
        content = (
            f"{HEADERS}\n"
            f"{units[0]['unit_no']},A-A21,Harmon,CUST-1,residential,active,2024-02-12,84.20,person,123-45-6789\n"
            f"{units[1]['unit_no']},A-A22,Alvarez,CUST-2,residential,active,,10.00,person,123-45-6789\n"
        )
        run_id = _run(dana, content, options={"cutover_on": CUTOVER})
        import_runs.load(dana, run_id, {"write_mode": "insert", "approved": True})

        filename, rows = _read_csv(run_id, "successes")
        assert filename.endswith("-successes.csv")
        assert rows[0] == [
            "account_number",
            "customer_name",
            "unit_reference",
            "opening_balance_total",
            "services_inherited",
        ]
        assert len(rows) == 2, "one account landed; the other row failed"
        assert rows[1][0] == "A-A21"
        assert rows[1][1] == "Harmon"
        assert rows[1][2] == units[0]["unit_no"]
        assert rows[1][3].startswith("84.20")
        # ⚠ **WAS `"0"`, AND THE REASON IS A MERGE, NOT A REGRESSION.** This
        # asserted 0 because when it was written the customers lane had not
        # landed, so the writer returned no `services_linked` and the
        # `or 0` fallback answered. `BR-CUS-672` is now merged: an imported
        # account ALWAYS inherits its unit's services, so a one-service unit
        # yields 1. The fallback is still proved — by the test above, which
        # now creates the absence deliberately instead of relying on an
        # unmerged sibling.
        assert rows[1][4] == "1", "one service on the unit, inherited (BR-CUS-672)"


def test_task13__the_two_files_partition_the_run(brazos, dana):
    """Every row a run holds comes out of exactly one of the two files. A row
    that appeared in neither would be DEF-016's silently-dropped row, and one
    that appeared in both would double-count a migration."""
    with tenant_ctx(brazos):
        units = _units(dana, brazos, count=3)
        content = (
            f"{HEADERS}\n"
            f"{units[0]['unit_no']},A-A31,Harmon,CUST-1,residential,active,2024-02-12,1.00,person,123-45-6789\n"
            f"{units[1]['unit_no']},A-A32,Alvarez,CUST-2,residential,active,,2.00,person,123-45-6789\n"
            f"{units[2]['unit_no']},A-A33,Okafor,CUST-3,residential,active,2024-04-01,3.00,person,123-45-6789\n"
        )
        run_id = _run(dana, content, options={"cutover_on": CUTOVER})
        import_runs.load(dana, run_id, {"write_mode": "insert", "approved": True})

        _f1, successes = _read_csv(run_id, "successes")
        _f2, failures = _read_csv(run_id, "failures")
        assert (len(successes) - 1) + (len(failures) - 1) == 3
        assert metering_models.ImportRunRow.objects.filter(run_id=run_id).count() == 3


def test_task13__a_run_that_has_not_loaded_is_refused_by_name(brazos, dana):
    """⚠ **A ZERO-ROW CSV WOULD BE THE WORSE ANSWER.** An operator who clicks
    *Rows that loaded* on a run that has not loaded and gets a header with
    nothing under it reads it as an answer — DEF-320's *"a path that looks
    handled and communicates nothing"*.

    ⛔ **AMENDED BY `DEF-2487` (2026-08-30): THE TWO HALVES NO LONGER SHARE A
    PREDICATE.** This case named `failures` until today, because both halves
    asked `run.status != "loaded"`. That is exactly what left an operator whose
    commit fell over sitting on stage 4 with a reject COUNT and no way to see
    which rows — the failures file is a WORKLIST, its content is written by
    stage 3, and it is the one thing that lets them fix the sheet. So the
    failures half is served from `validated` onward (the case below), and only
    the SUCCESSES half still requires a load, for the reason above — which is
    true only of that half.
    """
    with tenant_ctx(brazos):
        units = _units(dana, brazos, count=1)
        content = (
            f"{HEADERS}\n"
            f"{units[0]['unit_no']},A-A41,Harmon,CUST-1,residential,active,2024-02-12,0.00,person,123-45-6789\n"
        )
        run_id = _run(dana, content, options={"cutover_on": CUTOVER})
        with pytest.raises(errors.BizError) as caught:
            import_runs.results_csv(run_id, "successes")
        # ⛔ **THE DOWNLOAD DOOR HAS ITS OWN KEY SINCE THE CR-047 WIDENING
        # LANE (2026-08-29).** It shared `metering.import.not_loaded` with the
        # rollback door, whose English ends *"…so there is nothing to
        # reverse."* — right there, wrong here. Same predicate, same
        # `br_ref`, different sentence.
        assert caught.value.message_key == "metering.import.not_loaded_no_download"
        assert caught.value.br_ref == "BR-MET-090"


def test_def2487__the_failures_file_is_reachable_before_the_commit(brazos, dana):
    """⛔ **`DEF-2487` — THE LIST OF WHAT FAILED, AT THE MOMENT IT IS NEEDED.**

    A commit that falls over leaves the operator on stage 4, and both result
    files used to hang off the stage-5 Result screen that a failed commit never
    reaches. The rows have already been judged by then — stage 3 writes
    `outcome`, `problem` and `fix_hint` on every row it refuses — so the file
    has real content and is the only thing that lets somebody correct the
    spreadsheet and upload it again.
    """
    with tenant_ctx(brazos):
        units = _units(dana, brazos, count=2)
        content = (
            f"{HEADERS}\n"
            f"{units[0]['unit_no']},A-A45,Harmon,CUST-1,residential,active,2024-02-12,0.00,person,123-45-6789\n"
            f"NO-SUCH-UNIT,A-A46,Alvarez,CUST-2,residential,active,2024-03-01,0.00,person,123-45-6789\n"
        )
        run_id = _run(dana, content, options={"cutover_on": CUTOVER})
        assert metering_models.ImportRun.objects.get(pk=run_id).status == "validated"

        _filename, rows = _read_csv(run_id, "failures")
        assert rows[0][-2:] == ["why_it_failed", "how_to_fix_it"]
        assert len(rows) > 1, "the row stage 3 refused must be in the file"


def test_def2487__a_run_whose_rows_are_undecided_is_still_refused(brazos, dana):
    """The half that keeps the change honest. Before the check nothing carries
    an outcome, so the file would be a header with nothing under it — the very
    reading the sibling case exists to prevent. Its own sentence, because *"has
    not been loaded"* is not what is wrong with an unchecked run."""
    with tenant_ctx(brazos):
        units = _units(dana, brazos, count=1)
        content = (
            f"{HEADERS}\n"
            f"{units[0]['unit_no']},A-A47,Harmon,CUST-1,residential,active,2024-02-12,0.00,person,123-45-6789\n"
        )
        staged = import_runs.extract(
            dana,
            {
                "target": import_runs.TARGET_ACCOUNTS,
                "source_kind": "file",
                "file_name": "cr047-undecided.csv",
                "content": content,
                "session_ref": "sess_cr047_undecided",
                "write_mode": "insert",
            },
        )
        with pytest.raises(errors.BizError) as caught:
            import_runs.results_csv(staged["id"], "failures")
        assert caught.value.message_key == "metering.import.not_checked_no_download"
        assert caught.value.br_ref == "BR-MET-090"


def test_task13__an_unknown_kind_is_refused_rather_than_defaulted(brazos, dana):
    """A typo that quietly served the successes file would tell an operator
    that nothing failed. The refusal names what IS allowed."""
    with tenant_ctx(brazos):
        units = _units(dana, brazos, count=1)
        content = (
            f"{HEADERS}\n"
            f"{units[0]['unit_no']},A-A51,Harmon,CUST-1,residential,active,2024-02-12,0.00,person,123-45-6789\n"
        )
        run_id = _run(dana, content, options={"cutover_on": CUTOVER})
        import_runs.load(dana, run_id, {"write_mode": "insert", "approved": True})
        with pytest.raises(errors.ValidationError) as caught:
            import_runs.results_csv(run_id, "sucesses")
        assert caught.value.params["allowed"] == ["failures", "successes"]


def test_task13__the_body_is_a_generator_and_is_never_a_list(brazos, dana):
    """A 100,000-row file must not be built in memory — the sizes the PO named
    for this runner are *"50,000 or 100,000 … at a time"*, and DEF-766 measured
    what a materialised payload of that shape costs."""
    import types

    with tenant_ctx(brazos):
        units = _units(dana, brazos, count=1)
        content = (
            f"{HEADERS}\n"
            f"{units[0]['unit_no']},A-A61,Harmon,CUST-1,residential,active,2024-02-12,0.00,person,123-45-6789\n"
        )
        run_id = _run(dana, content, options={"cutover_on": CUTOVER})
        import_runs.load(dana, run_id, {"write_mode": "insert", "approved": True})
        _filename, body = import_runs.results_csv(run_id, "successes")
        assert isinstance(body, types.GeneratorType)


def test_task13__the_endpoint_answers_an_ACCEPT_TEXT_CSV_REQUEST(brazos, dana):
    """⛔⛔ **`DEF-553` REPEATING, AND IT IS THE ONE FAILURE NO OTHER TEST IN
    THIS FILE CAN SEE.**

    `@api_view`'s default renderer set satisfies JSON only, so DRF's content
    NEGOTIATION runs before the view body and answers **400** to a client that
    asks for `text/csv` — whatever the view would have produced. That is how
    S28's template button shipped having never downloaded anything: the view
    was correct, the endpoint was not, and the fix is one decorator
    (`@renderer_classes([CsvRenderer, JSONRenderer])`).

    ⚠ **WHY THIS TEST EXISTS BESIDE THE ONE BELOW, WHICH LOOKS LIKE IT.** The
    one below sends NO `Accept` header, so negotiation takes the first renderer
    in the list and would pass over a broken endpoint. Nothing on the frontend
    can see it either — every frontend test stubs the HTTP client, so the
    negotiation layer is exercised nowhere else in this repo. The header is the
    whole test.

    ⚠ **PROVED RED FIRST (law 7).** With `@renderer_classes` removed from
    `import_results_csv` this case failed on the negotiation, before the view
    body ran; with the decorator restored it answers 200 and
    `text/csv; charset=utf-8`. Both outputs are quoted in the build report.
    """
    from apps.metering import api as metering_api

    from tests.test_us_ten_helpers import FakeUser, api_call

    with tenant_ctx(brazos):
        units = _units(dana, brazos, count=1)
        content = (
            f"{HEADERS}\n"
            f"{units[0]['unit_no']},A-A81,Harmon,CUST-1,residential,active,2024-02-12,0.00,person,123-45-6789\n"
        )
        run_id = _run(dana, content, options={"cutover_on": CUTOVER})
        import_runs.load(dana, run_id, {"write_mode": "insert", "approved": True})

        for kind in ("successes", "failures"):
            response = api_call(
                metering_api.import_results_csv,
                "get",
                user=FakeUser(),
                role="system_admin",
                tenant=brazos,
                query={"kind": kind},
                headers={"Accept": "text/csv"},
                run_id=run_id,
            )
            assert response.status_code == 200, (
                f"kind={kind} answered {response.status_code} to Accept: text/csv — "
                "that is DEF-553: negotiation refused the request before the view ran"
            )
            assert response["Content-Type"] == "text/csv; charset=utf-8"
            assert b"".join(response.streaming_content)


def test_task13__the_endpoint_streams_csv_with_a_filename(brazos, dana):
    """The route, end to end: `GET /imports/{id}/results.csv?kind=…` answers
    `text/csv; charset=utf-8` as an attachment, through
    `StreamingHttpResponse`."""
    from apps.metering import api as metering_api
    from django.http import StreamingHttpResponse

    from tests.test_us_ten_helpers import FakeUser, api_call

    with tenant_ctx(brazos):
        units = _units(dana, brazos, count=1)
        content = (
            f"{HEADERS}\n"
            f"{units[0]['unit_no']},A-A71,Harmon,CUST-1,residential,active,2024-02-12,0.00,person,123-45-6789\n"
        )
        run_id = _run(dana, content, options={"cutover_on": CUTOVER})
        import_runs.load(dana, run_id, {"write_mode": "insert", "approved": True})

        response = api_call(
            metering_api.import_results_csv,
            "get",
            user=FakeUser(),
            role="system_admin",
            tenant=brazos,
            query={"kind": "successes"},
            run_id=run_id,
        )
        assert isinstance(response, StreamingHttpResponse)
        assert response["Content-Type"] == "text/csv; charset=utf-8"
        assert "attachment; filename=" in response["Content-Disposition"]
        assert b"account_number" in b"".join(response.streaming_content)
