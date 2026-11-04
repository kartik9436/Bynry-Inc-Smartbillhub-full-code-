# ── Trace ──────────────────────────────────────────────
# Change:   `06 Payments Page Blueprint.pdf` phase 1 — `P1.1` (the eighth
#           ImportTarget) · `P1.2` (the writer seam) · `P1.3` (the target
#           constraint) · `P1.4` (the staging tables are KEPT) · `P1.12` (the
#           ambiguous match stays for a person) · `P1.20` (the sample CSV) ·
#           `P1.22` (the rollback sentence is a REFUSAL).
# Rules:    CLAUDE.md hard rule 4 (no UPDATE/DELETE on a payment — which is
#           why this target has no upsert and no rollback) · hard rule 2
#           (money is Decimal) · hard rule 6 (idempotency) · BR-MET-096 (ONE
#           runner, `target` parameterised) · BR-PAY-023 (per-row errors skip
#           WITH A REPORT) · B1/B2 §2 (no cross-module write) · hard-won law 2
#           (built is not wired) · law 7 (a check must be able to fail)
# Impacts:  apps/metering/import_runs.py · import_rules.py · seams.py ·
#           apps/payments/import_writer.py
# ───────────────────────────────────────────────────────
"""The payments import target, asserted where it can be asserted without a database.

⚠ **THE END-TO-END LIVES SOMEWHERE ELSE AND HAS TO** (`P1.11`). Everything in
this file is a statement about SHAPE — which dicts hold the target, which
branches exist, which sentence a refusal carries — and shape is exactly what
SQLite can prove. **The savepoint cannot be proved here at all**: CLAUDE.md law
14, `config/settings/test.py` hardcodes in-memory SQLite, and SQLite has no
aborted-transaction state, so the broken version of `_load_payments_rows`
passes every case below. `10-scripts/pay_p1_11_postgres_proof.py` is the other
half and it runs on a real PostgreSQL 16.
"""

from __future__ import annotations

import inspect
from decimal import Decimal

import pytest

from apps.metering import import_rules, import_runs, seams
from apps.payments import import_writer
from core import errors


def _world(**kwargs):
    return import_rules.World(
        enabled_services=set(),
        premises_type_codes=set(),
        area_names=set(),
        existing_premise_nos=set(),
        existing_addresses=set(),
        **kwargs,
    )


#: One account as `customers.selectors.account_import_index` keys it, plus the
#: `ext:` half. The legacy reference is a NAME, because that is the real shape
#: the payer-name rung was written for — a utility whose old system used the
#: household's name as its "number".
INDEX = {
    "ac-2026-00042": {
        "id": "11111111-1111-1111-1111-111111111111",
        "account_no": "AC-2026-00042",
        "external_ref": "J RIVERA",
    },
    "ext:j rivera": {
        "id": "11111111-1111-1111-1111-111111111111",
        "account_no": "AC-2026-00042",
        "external_ref": "J RIVERA",
    },
}


# ══ P1.1 — the target is REGISTERED, in every table that makes it behave ════


def test_payments_is_the_eighth_target_of_the_one_runner():
    """`BR-MET-096`, PO 2026-08-21. A second staging/validation/commit engine
    would be two sources of truth for one screen — which is precisely what
    `payment_import.py` was, and why `P1.9` retires it."""
    assert import_runs.TARGET_PAYMENTS == "payments"
    assert import_runs.TARGET_PAYMENTS in import_runs.TARGETS
    assert len(import_runs.TARGETS) == 8


def test_the_target_is_declared_in_every_by_target_table():
    """⚠ **THE CHECK THAT STOPS A TARGET BEHAVING LIKE A DIFFERENT ONE.** A
    target in `TARGETS` and missing from one of these dicts starts a run and
    then silently borrows premises' columns, premises' aliases or premises'
    dedupe key. It fails here rather than at a clerk's commit."""
    target = import_runs.TARGET_PAYMENTS
    assert target in import_runs.EXPLICIT_COLUMNS_BY_TARGET
    assert target in import_runs.ALIASES_BY_TARGET
    assert target in import_runs.DEFAULT_MAPPING_TEMPLATES
    assert target in import_runs.DEDUPE_KEY_BY_TARGET
    assert target in import_runs.SKIP_REQUIRED_BY_TARGET
    assert target in import_rules.PLATFORM_CATALOG


def test_every_offered_column_is_one_the_writer_will_actually_take():
    """⚠ **THE CHECK THAT SAVED AN HOUR ON THE PARTS TARGET, RUN BEFORE THE
    FILE THIS TIME.** The column set is the owning module's WRITER's signature,
    not the table's — `payments` has thirty-odd columns and six are reachable
    through this door. A seventh would rehearse clean and reject every row at
    the write.

    The check runs over the ADAPTER's output rather than over the column names,
    because `_payment_payload_from` is where a column becomes a payload key —
    `paid_on` arrives as `paid_at`, converted to an instant — and asserting the
    column names directly would test the wrong join."""
    source = inspect.getsource(import_writer.create_payment_from_import)
    mapped = {column["target"]: f"sample {column['target']}" for column in
              import_runs.PAYMENTS_COLUMNS}

    class _Run:
        id = "00000000-0000-0000-0000-000000000000"
        file_name = "lockbox.csv"

    payload = import_runs._payment_payload_from(
        mapped, run=_Run(), row_no=1, recorded_at=None
    )
    for name in payload:
        if name in ("index", "match"):
            continue
        assert f'data.get("{name}")' in source, (
            f"the loader sends {name!r}, which the writer never reads"
        )


def test_every_column_reaches_the_payload_and_none_is_dropped_in_the_adapter():
    """The mirror of the test above, and the one that catches the OTHER failure:
    a column offered on the template, filled in by a utility, and silently
    dropped between the row and the writer. `paid_on` is the one that changes
    name; everything else travels under its own."""
    mapped = {column["target"]: f"x-{column['target']}" for column in
              import_runs.PAYMENTS_COLUMNS}

    class _Run:
        id = "00000000-0000-0000-0000-000000000000"
        file_name = "lockbox.csv"

    payload = import_runs._payment_payload_from(
        mapped, run=_Run(), row_no=1, recorded_at=None
    )
    for column in import_runs.PAYMENTS_COLUMNS:
        name = column["target"]
        key = "paid_at" if name == "paid_on" else name
        assert key in payload, f"the template offers {name!r} and the loader drops it"


def test_the_dedupe_key_is_the_instrument_and_never_the_account():
    """Two rows naming one account are ordinarily two real payments. Keying the
    *keep the latest row* option on the account would silently drop money the
    utility actually banked."""
    field, _label = import_runs.DEDUPE_KEY_BY_TARGET[import_runs.TARGET_PAYMENTS]
    assert field == "reference"


def test_the_skip_required_field_is_the_amount_and_never_the_account():
    """A row with no amount is not a payment. A row with no account is a
    payment that needs a person, which is a different outcome owned by
    `PAY.PAYER_NAMED` — skipping on the account would throw money away."""
    field, _sentence = import_runs.SKIP_REQUIRED_BY_TARGET[import_runs.TARGET_PAYMENTS]
    assert field == "amount"


def test_a_payments_row_has_no_match_key_and_says_so():
    """`_key_of` answers `None` for this target BY LAW, not by omission: a
    payment may never be updated (hard rule 4), so there is no record on file
    for a row to be *about*."""

    class _Run:
        target = import_runs.TARGET_PAYMENTS

    assert import_runs._key_of(_Run(), {"reference": "CHK-1", "account_ref": "AC-1"}) is None


# ══ P1.3 — the constraint was READ, not assumed ═════════════════════════════


def test_the_target_column_is_constrained_in_python_and_nowhere_else():
    """⛔ **`P1.3`. The blueprint marks this a hazard: *"if `import_runs.target`
    carries a CHECK, an eighth value is a migration. If it is validated in
    Python only, it is not."*

    Read off a live PostgreSQL 16 database on 2026-09-22: `import_runs.target`
    is `text NOT NULL`, **zero** CHECK constraints, no enum type, and an INSERT
    carrying `target = 'utter_nonsense_zzz'` was ACCEPTED (and rolled back). So
    the eighth value needed no migration, and **this test is what keeps that
    true** — a lane adding `choices` or a `CheckConstraint` here later turns
    every future target into a migration, and would find out at deploy time."""
    field = import_runs.models.ImportRun._meta.get_field("target")
    assert not field.choices, "a `choices` list would become a database CHECK"
    names = {c.name for c in import_runs.models.ImportRun._meta.constraints}
    assert names == {"uq_import_runs_no", "uq_import_runs_idempotency"}


# ══ P1.2 — the writer seam, and the module boundary it makes structural ═════


def test_nothing_in_metering_names_a_payments_table():
    """`B1`/`B2` §2, and `G78`'s law generalised. The boundary is kept BY
    CONSTRUCTION — there is no ORM statement in the runner to review — and this
    asserts it rather than trusting the reading."""
    for module in (import_runs, import_rules, seams):
        body = inspect.getsource(module)
        for forbidden in (
            "from apps.payments import models",
            "payments_models.Payment",
            "import apps.payments.models",
        ):
            assert forbidden not in body, f"{module.__name__} reaches into payments' models"


def test_the_writer_is_undecorated_because_a_worker_carries_no_role():
    """`DEF-1108`: a deferred load runs under `_JobActor` — an id and no role,
    by design — so a `@require_role` writer would refuse every row of a
    four-hundred-line morning file. The role is checked once at `load()`."""
    for fn in (
        import_writer.create_payment_from_import,
        import_writer.payments_import_index,
        import_writer.match_account,
    ):
        assert not hasattr(fn, "__wrapped__"), f"{fn.__name__} is decorated"


def test_the_seam_publishes_create_and_an_index_and_deliberately_nothing_else():
    """⚠ **THE TWO MISSING NAMES ARE THE RULE.** Every other `import_writer`
    seam publishes create · update · rollback. Hard rule 4 forbids both of the
    others here: a payment may not be UPDATEd and a posted one may not be
    un-written. A lane adding either is reversing a hard rule, not filling a
    gap — so this test names them."""
    assert callable(seams.create_payment_from_import)
    assert callable(seams.payments_import_index)
    assert callable(seams.payments_match_account)
    assert not hasattr(seams, "update_payment_from_import")
    assert not hasattr(seams, "rollback_payment_from_import")
    assert not hasattr(import_writer, "update_payment_from_import")
    assert not hasattr(import_writer, "rollback_payment_from_import")


def test_the_load_has_a_payments_branch():
    """⚠ **`rollback()`'s OWN DOCSTRING DEMANDS A BRANCH OF A NEW TARGET, AND A
    MISSING ONE IS SILENT** — the run falls through to the premises/units path,
    keys every row as `premises|label`, skips all of them, spends the rollback
    point and reports success. That is the accounts escape, recorded."""
    body = inspect.getsource(import_runs)
    assert "_load_payments_rows(actor, run, write_mode, data, reporter)" in body


def test_the_loader_keeps_its_savepoint_and_says_why():
    """CLAUDE.md law 14. SQLite cannot show you this, so the only thing
    standing between the next lane and a lost batch is the comment — and a
    comment nothing asserts is a comment that gets tidied away."""
    body = inspect.getsource(import_runs._load_payments_rows)
    assert "with transaction.atomic():  # ← SAVEPOINT. Law 14. Do not remove." in body


def test_the_loader_creates_no_rollback_point():
    """⛔ **`P1.22`, the half that makes the refusal true rather than drawn.**
    Every other loader ends with `if create_rollback_point: RollbackPoint(...)`.
    This one must not: a point would put a live *Roll back this run* button
    over a run `rollback()` refuses — a promise nothing can keep."""
    # ⚠ **CODE ONLY — the comment in that function NAMES the call it must not
    # make**, and a check that reads prose would be satisfied by deleting the
    # explanation and keeping the call. Comments stripped, first draft
    # deliberately recorded: it failed on its own docstring (law 7's *what
    # would make this pass, or fail, wrongly*).
    def _code(fn):
        return "\n".join(
            line for line in inspect.getsource(fn).split("\n")
            if not line.strip().startswith("#")
        )

    body = _code(import_runs._load_payments_rows)
    assert "RollbackPoint.objects.create" not in body
    assert 'data.get("create_rollback_point"' not in body
    # …and every other loader DOES create one, so this test can actually fail.
    # A check that would pass over any function at all is not a check (law 7).
    assert "RollbackPoint.objects.create" in _code(import_runs._load_parts_rows)


# ══ P1.22 — the rollback sentence is a REFUSAL ══════════════════════════════


def test_rollback_refuses_the_payments_target_by_name():
    """A posted payment cannot be unwritten (hard rule 4). It is REVERSED,
    which is a new row and a different act with different books."""
    body = inspect.getsource(import_runs.rollback)
    assert "TARGET_PAYMENTS" in body
    assert "metering.import.payments_no_rollback" in body


def test_the_refusal_comes_before_the_point_is_read_or_the_status_checked():
    """⚠ **THE ORDER IS THE RULE.** The accounts escape this function records
    is a run that SPENT its one rollback point and reversed nothing; refusing
    before anything is read means there is nothing to spend. And a refusal that
    depended on `status` would tell an operator *"this run is not loaded"*
    about a run that is — sending them to look for a state that cannot exist."""
    body = inspect.getsource(import_runs.rollback)
    refusal = body.index("payments_no_rollback")
    assert refusal < body.index('run.status != "loaded"')
    assert refusal < body.index("RollbackPoint.objects.filter")


def test_insert_and_update_is_refused_for_payments_by_name():
    """Hard rule 4 again, on the other door. *Insert & update* would overwrite
    money on file, and mapping it onto `insert` would tell a caller that four
    hundred payments were updated when nothing was — a wrong belief about
    money, which is worse than an error."""
    with pytest.raises(errors.BizError) as caught:
        import_runs._refuse_withdrawn_mode("upsert", target=import_runs.TARGET_PAYMENTS)
    assert caught.value.message_key == "metering.import.payments_insert_only"
    # And it does NOT fire for another target, or the whole product loses upsert.
    import_runs._refuse_withdrawn_mode("upsert", target=import_runs.TARGET_PARTS)


# ══ P1.12 — the ambiguous match stays for a person ══════════════════════════


def test_an_account_number_on_file_is_the_only_clean_match():
    verdict = import_writer.match_account(account_ref="AC-2026-00042", index=INDEX)
    assert verdict["state"] == import_writer.MATCH_CLEAN
    assert verdict["method"] == import_writer.BY_ACCOUNT_NO


def test_a_payer_name_match_is_a_suggestion_and_never_clean():
    """⛔ **CS-2 RULE 2, WHICH IS THE WHOLE OF `P1.12`.** *A name-and-amount
    guess never commits on its own.* A name is not an identifier; posting to
    the wrong customer breaks two accounts silently and can only be undone by a
    reversal on one and a new payment on the other."""
    verdict = import_writer.match_account(payer_name="J Rivera", index=INDEX)
    assert verdict["method"] == import_writer.BY_NAME_ONLY
    assert verdict["state"] == import_writer.MATCH_REVIEW
    assert verdict["account_id"] is not None, "the suggestion is shown, it is just not acted on"
    assert "SUGGESTION" in verdict["detail"]


def test_a_name_only_match_is_REFUSED_at_the_write_and_not_skipped():
    """⚠ **REFUSED, NOT SKIPPED, AND THE DISTINCTION IS `BR-PAY-023`'s.** A row
    that disappears is money nobody chased. This row carries its reason onto
    the receipt and into the failures download."""
    with pytest.raises(errors.BizError) as caught:
        import_writer.create_payment_from_import(
            actor=None,
            payload={"amount": Decimal("247.30"), "payer_name": "J Rivera", "index": INDEX},
        )
    assert caught.value.message_key == import_writer.REFUSAL_NAME_ONLY


def test_an_account_the_utility_does_not_have_is_refused_with_its_own_reason():
    """Not the same refusal as a name guess, and not the same fix: one is a
    number to correct in the file, the other is a judgement to make."""
    with pytest.raises(errors.BizError) as caught:
        import_writer.create_payment_from_import(
            actor=None,
            payload={"amount": Decimal("10.00"), "account_ref": "AC-NOPE", "index": INDEX},
        )
    assert caught.value.message_key == import_writer.REFUSAL_ACCOUNT_NOT_ON_FILE


def test_a_row_naming_nothing_is_refused_with_its_own_reason():
    with pytest.raises(errors.BizError) as caught:
        import_writer.create_payment_from_import(
            actor=None, payload={"amount": Decimal("10.00"), "index": INDEX}
        )
    assert caught.value.message_key == import_writer.REFUSAL_NO_IDENTIFIER


@pytest.mark.parametrize(
    "amount,key",
    [
        (None, import_writer.REFUSAL_AMOUNT_MISSING),
        ("", import_writer.REFUSAL_AMOUNT_MISSING),
        ("not a number", import_writer.REFUSAL_AMOUNT_MISSING),
        (Decimal("0"), import_writer.REFUSAL_AMOUNT_NOT_POSITIVE),
        (Decimal("-5.00"), import_writer.REFUSAL_AMOUNT_NOT_POSITIVE),
    ],
)
def test_the_amount_is_refused_rather_than_coerced(amount, key):
    """CLAUDE.md hard rule 2 — money is a `Decimal`, never a float and never a
    silent zero. A negative is a REFUND, which is a different act with
    different books and a different door."""
    with pytest.raises(errors.BizError) as caught:
        import_writer.create_payment_from_import(
            actor=None,
            payload={"amount": amount, "account_ref": "AC-2026-00042", "index": INDEX},
        )
    assert caught.value.message_key == key


def test_the_stage_3_rules_and_the_writer_use_ONE_ladder():
    """`DEF-544`'s law: a load that resolves against a different world than the
    one the operator was shown is a defect in its own right, not a race. Both
    call `payments.import_writer.match_account`, and this is the assertion that
    stops a second matcher appearing in metering."""
    assert "seams.payments_match_account" in inspect.getsource(import_rules._payment_verdict_of)
    assert "match_account" in inspect.getsource(import_writer.create_payment_from_import)


def test_the_rules_report_nothing_when_payments_cannot_answer():
    """⚠ **AN UNWIRED MATCHER MUST NEVER LOOK LIKE A FILE WITH NO PROBLEMS IN
    IT** — hard-won law 7's *incapable of failing* shape, refused by
    construction. `None` is *payments cannot answer*; `{}` is a utility with no
    accounts, where every row correctly reports an account not on file."""
    rows = [{"row_no": 1, "mapped": {"account_ref": "AC-NOPE", "amount": "10.00"}}]
    unanswerable = _world(payments_account_index=None)
    rule = next(r for r in import_rules.PAYMENTS_RULES if r.code == "PAY.ACCOUNT_ON_FILE")
    assert import_rules.EVALUATORS[rule.rule_kind](rows, unanswerable, rule) == []
    # …and an EMPTY index is a real verdict, not silence.
    empty = _world(payments_account_index={})
    assert len(import_rules.EVALUATORS[rule.rule_kind](rows, empty, rule)) == 1


def test_every_payments_rule_has_an_evaluator():
    """A declared rule whose `rule_kind` nothing implements is a rule that never
    fires and a rehearsal that promises more than it delivers — hard-won law 2
    one layer below the UI, on a money path."""
    for rule in import_rules.PAYMENTS_RULES:
        assert rule.rule_kind, f"{rule.code} declares no rule_kind"
        assert rule.rule_kind in import_rules.EVALUATORS, (
            f"{rule.code}: no evaluator for {rule.rule_kind}"
        )


def test_the_name_only_rule_and_the_wrong_number_rule_both_hold_the_row():
    """Neither posts money. ⚠ The name-only rule FLAGGED until `DEF-PAY-10756`
    (L2-08): a flagged row counts in the dry run's *will create*, and the
    writer then refuses it, so the rehearsal promised a payment the commit
    never made. The rehearsal now says what the writer does."""
    by_code = {r.code: r for r in import_rules.PAYMENTS_RULES}
    assert by_code["PAY.ACCOUNT_ON_FILE"].severity == import_rules.ERROR
    assert by_code["PAY.ACCOUNT_ON_FILE"].action == import_rules.REJECT_ROW
    assert by_code["PAY.NAME_ONLY_MATCH"].severity == import_rules.ERROR
    assert by_code["PAY.NAME_ONLY_MATCH"].action == import_rules.REJECT_ROW


def test_the_name_only_rule_fires_on_a_guess_and_not_on_a_clean_row():
    world = _world(payments_account_index=INDEX)
    rule = next(r for r in import_rules.PAYMENTS_RULES if r.code == "PAY.NAME_ONLY_MATCH")
    rows = [
        {"row_no": 1, "mapped": {"account_ref": "AC-2026-00042", "amount": "10"}},
        {"row_no": 2, "mapped": {"payer_name": "J Rivera", "amount": "10"}},
        {"row_no": 3, "mapped": {"payer_name": "Nobody At All", "amount": "10"}},
    ]
    hits = import_rules.EVALUATORS[rule.rule_kind](rows, world, rule)
    assert [h.row_no for h in hits] == [2]


def test_a_row_naming_neither_an_account_nor_a_payer_is_rejected():
    world = _world(payments_account_index=INDEX)
    rule = next(r for r in import_rules.PAYMENTS_RULES if r.code == "PAY.PAYER_NAMED")
    rows = [
        {"row_no": 1, "mapped": {"amount": "10"}},
        {"row_no": 2, "mapped": {"payer_name": "Someone", "amount": "10"}},
    ]
    hits = import_rules.EVALUATORS[rule.rule_kind](rows, world, rule)
    assert [h.row_no for h in hits] == [1]


def test_no_refusal_sentence_carries_an_id():
    """CR-016's ruling, gate G28, B14 rule 32: an id in the words a clerk reads
    is provenance rather than help."""
    for problem, fix_hint in import_runs._PAYMENT_REFUSAL_SENTENCES.values():
        for sentence in (problem, fix_hint):
            for token in ("BR-", "OQ-", "DEF-", "payments.import.", "_id"):
                assert token not in sentence, f"{sentence!r} shows an internal code"


def test_every_writer_refusal_key_has_an_operator_sentence():
    """⚠ **A REFUSAL WITH NO SENTENCE REACHES A CLERK AS SILENCE** — `G32`'s
    own blind spot, met here by asserting the join rather than trusting it."""
    published = {
        getattr(import_writer, name)
        for name in dir(import_writer)
        if name.startswith("REFUSAL_")
    }
    assert published <= set(import_runs._PAYMENT_REFUSAL_SENTENCES), (
        f"no sentence for {sorted(published - set(import_runs._PAYMENT_REFUSAL_SENTENCES))}"
    )


# ══ P1.20 — the sample CSV comes WITH the column set ════════════════════════


def test_every_column_carries_a_worked_sample_cell():
    """`CR-025`, PO 2026-08-21: *"we will need sample CSV files to be downloaded
    at every import at step 1"*. `DEF-962` is what a column with no sample
    ships as — a blank cell in the file a utility builds from."""
    for column in import_runs.PAYMENTS_COLUMNS:
        assert column.get("sample"), f"{column['target']} ships a blank template cell"


def test_the_sample_is_derived_from_the_column_set_and_not_a_second_list():
    """The drawing's own words: *"it comes with the column set, not as a
    separate build — but a target registered without it shows a button that
    fetches nothing."* `sample_columns` reads `target_columns`, which reads
    `EXPLICIT_COLUMNS_BY_TARGET`, so there is one list and it cannot drift
    (`DEF-521`'s shape, prevented by construction).

    ⚠ Asserted by IDENTITY rather than by calling `sample_columns`, which needs
    a tenant for the custom-field half. Identity is the stronger claim anyway:
    it is not *"these two lists agree today"*, it is *"there is one list"*."""
    assert (
        import_runs.EXPLICIT_COLUMNS_BY_TARGET[import_runs.TARGET_PAYMENTS]
        is import_runs.PAYMENTS_COLUMNS
    )
    # …and the sample really does read that table rather than its own copy.
    assert "target_columns(target)" in inspect.getsource(import_runs.sample_columns)
    assert "EXPLICIT_COLUMNS_BY_TARGET" in inspect.getsource(import_runs.target_columns)


def test_the_amount_column_samples_stored_money_precision():
    """CLAUDE.md hard rule 2: money is stored to FOUR decimals and shown at
    two. The file is what a utility types into, so the template shows the
    stored precision — the same posture `purchase_cost` and `unit_cost` take."""
    amount = next(c for c in import_runs.PAYMENTS_COLUMNS if c["target"] == "amount")
    assert amount["sample"] == "247.3000"
    assert amount["required"] is True


def test_the_date_help_says_which_date_it_means():
    """`BR-PAY-033` + `OQ-131`'s ruling: lateness is judged on the day the money
    ARRIVED. A clerk who puts the import date in this column charges a late fee
    on money that was in the bank two days early — so the column has to say so
    where it is filled in, not on a screen two stages later."""
    paid_on = next(c for c in import_runs.PAYMENTS_COLUMNS if c["target"] == "paid_on")
    assert "not the day you are importing it" in paid_on["help"]


# ══ P1.4 — the two old staging tables are KEPT ══════════════════════════════


def test_the_old_staging_tables_are_untouched():
    """⛔ **`P1.4` IS A TASK TO NOT DO SOMETHING, AND THIS IS THE CHECK THAT
    MAKES IT SURVIVE THE NEXT LANE.**

    `payment_import_batches` and `payment_import_rows` *"hold the provenance of
    every payment they created"*, and phase 0's `payments.origin` backfill
    still reads `payment_import_rows` to derive `origin = import`. **Retiring
    the pipeline (`P1.9`) is not deleting the history** — a lane reading `P1.9`
    as licence to drop these tables has misread it, and this test is where that
    misreading is caught rather than in a customer's audit.

    They are dropped in a LATER phase, with that stated, and not before."""
    from apps.payments import models as payments_models

    assert payments_models.PaymentImportBatch._meta.db_table == "payment_import_batches"
    assert payments_models.PaymentImportRow._meta.db_table == "payment_import_rows"
    # The provenance column that makes them worth keeping.
    assert payments_models.PaymentImportRow._meta.get_field("payment_id")


def test_the_new_target_writes_none_of_the_old_staging_tables():
    """The new path is not a second writer of the old tables: it stages in
    `import_runs`/`import_run_rows` like every other target. If it wrote both,
    dropping the old pair later would silently take the new path with it."""
    body = inspect.getsource(import_writer)
    for forbidden in ("PaymentImportBatch", "PaymentImportRow"):
        assert forbidden not in body


# ── Lifecycle ─────────────────────────────────────────────
# packet: 05-prototype/06 Payments Page Blueprint.pdf phase 1
# generated: 2026-09-22 by lane P1-A
# checklist: A✔ B=n/a C✔ D=n/a E=n/a F✔ G✔ H✔
# gates: pytest tests/test_pay_import_target.py
# exceptions: the savepoint and the aborted-transaction behaviour CANNOT be
#   proved here — SQLite has no such state (law 14). `P1.11`'s PostgreSQL proof
#   is `10-scripts/pay_p1_11_postgres_proof.py`.
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
