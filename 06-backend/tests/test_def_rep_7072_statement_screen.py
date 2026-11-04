# ── Trace ──────────────────────────────────────────────
# Defects: DEF-REP-7072 (opening the editor cut the statement from SEVEN columns
#          to ONE) · DEF-REP-7053 (the export works and nothing offered a
#          Download button) · DEF-REP-7052 (no statement named what it is about).
# Screens: 2·1 Report viewer at /reports/statement, and 2·2 beside it.
# Rules:   B14 rule 31 (no database id is ever a visible value) · rule 33 ·
#          BR-REP-038 · BR-REP-043 · CLAUDE.md hard rule 8 (a unit refines a
#          premises by LABEL) · hard rule 2 (money 4 decimals, DISPLAY 2) ·
#          hard-won law 2 and its mirror · law 7 clause 2.
# ───────────────────────────────────────────────────────
"""THREE FAULTS ON ONE SCREEN, EACH ASSERTED WHERE IT ACTUALLY LIVED.

⚠ **THE COLUMN FAULT DID NOT LIVE IN EITHER HALF, AND THAT IS WHY IT IS FIRST.**
The editor offered the `journal_lines` dataset's five attributes because that is
what a definition chooses from; the runner honoured the dataset's five because
that is what a definition may name. Both were correct about their own
vocabulary. The statement serves seven names, the dataset declares five, and the
two lists intersect in `reference` and in nothing else — so the one thing that
sends a `columns` control, opening the editor, cut the table to ONE column. A
test of either half in isolation passes on the defect, which is how it shipped.

**So these cases are written against the SEAM** — `runner.served_columns`, the
one function the offer and the honour now both read — and the browser walk in
`10-scripts/rep_stmt_screen_walkthrough.mjs` is what proves the two halves meet.

⚠ **WHAT WOULD MAKE THESE PASS WRONGLY** (hard-won law 7 clause 2):

  * **ASSERTING SEVEN COLUMNS WITHOUT SENDING THE CONTROL.** A run with no
    `columns` parameter has always served seven; the defect only appears when
    the editor's ticks travel. Every column case below SENDS them.
  * **ASSERTING THE COUNT AND NOT THE NAMES.** `served_columns` returning seven
    of the wrong names would pass a `len()`. The names are asserted, in order.
  * **A WIDENING THAT REACHES EVERY REPORT.** The fix must be additive: a
    dataset-backed report must be refused exactly as it was, measures included.
    `ar_aging` is asserted to publish NO `column_choices` and `validate` is
    asserted still to refuse a name its dataset does not declare.
  * **A HEAD BUILT FROM THE VIEWER'S OWN KNOWLEDGE OF ACCOUNTS.** That would
    work for `account` and leave every new subject blank. The composition is
    asserted through `subject_head.compose` over a REGISTERED resolver, and the
    registry is asserted to be the only thing a new subject adds.
  * **A HEAD CARRYING AN ID.** B14 rule 31. The `subject_id` is asserted absent
    from every published value.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from apps.reports import (
    datasets,
    exports as report_exports,
    runner,
    statement as statement_module,
    subject as subject_module,
    subject_head,
)
from apps.tenancy import exports as export_kernel

from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared tenant fixtures

pytestmark = pytest.mark.django_db

SEPT_START = date(2026, 9, 1)
SEPT_END = date(2026, 9, 30)


# ═══════════════════════════════════════════════════════════════════════════
# DEF-REP-7072 · THE SEAM: WHAT THE EDITOR MAY ASK FOR AND WHAT THE RUN HONOURS
# ═══════════════════════════════════════════════════════════════════════════
def test_def_rep_7072__the_two_vocabularies_shared_exactly_one_word() -> None:
    """The arithmetic of the defect, asserted so the premise cannot rot.

    If a future dataset gains `entry_date`, this case goes red and the fix's
    whole reasoning has to be re-read — which is the point of writing the
    PREMISE down rather than only the outcome.
    """
    dataset = datasets.BY_CODE["journal_lines"]
    declared = {column.name for column in dataset.columns}
    served = set(statement_module.STATEMENT_COLUMNS)
    assert served & declared == {"reference"}, (
        "the statement's seven columns and the journal_lines dataset's "
        "attributes are supposed to intersect in `reference` alone — that one "
        f"overlap IS the defect. Got {sorted(served & declared)!r}."
    )


def test_def_rep_7072__served_columns_answers_for_the_report_not_the_dataset() -> None:
    """One function, read by the offer and by the honour."""
    dataset = datasets.BY_CODE["journal_lines"]
    served = runner.served_columns("statement", dataset)
    for name in statement_module.STATEMENT_COLUMNS:
        assert name in served, f"{name!r} is served by the statement and may be asked for"
    for name in statement_module.UNIT_STATEMENT_COLUMNS:
        assert name in served, (
            f"{name!r} is the unit subject's and belongs to the same report — a "
            "vocabulary that changed with the subject would refuse a bookmarked "
            "`columns` the moment a clerk switched grain"
        )


def test_def_rep_7072__a_dataset_backed_report_is_untouched() -> None:
    """Additive, or it is not a fix. `ar_aging` keeps the dataset's answer."""
    dataset = datasets.BY_CODE["invoices"]
    assert runner.viewer_columns("ar_aging") == ()
    served = set(runner.served_columns("ar_aging", dataset))
    assert served == (
        {column.name for column in dataset.columns}
        | {measure.name for measure in dataset.measures}
    )


def test_def_rep_7072__the_editors_ticks_no_longer_collapse_the_table(
    brazos, dana
) -> None:
    """THE DEFECT ITSELF, through the runner, with the control actually sent.

    Measured on real PostgreSQL 16 before the fix:

        runner.run("statement", {...})                 -> 7 columns
        runner.run("statement", {..., "columns": <7>}) -> ['reference']
    """
    from tests.test_us_met_helpers import tenant_ctx

    params = {
        "from": SEPT_START.isoformat(),
        "to": SEPT_END.isoformat(),
        # ⚠ **NO SUBJECT ID ON PURPOSE.** This case is about the COLUMN
        # vocabulary and nothing else, and a statement with no account named
        # still declares its columns — which is the state the Product Owner
        # actually photographed when they opened the editor.
    }
    ticked = ",".join(statement_module.STATEMENT_COLUMNS)
    with tenant_ctx(brazos):
        reading = runner.run("statement", dict(params))
        editing = runner.run("statement", {**params, "columns": ticked})

    assert list(reading.columns) == list(statement_module.STATEMENT_COLUMNS)
    assert list(editing.columns) == list(statement_module.STATEMENT_COLUMNS), (
        "opening the editor sent the ticked columns as a run control and the "
        "runner narrowed them against the DATASET's declaration, which shares "
        "one name with this report. The table collapsed to that one name."
    )


def test_def_rep_7072__the_report_publishes_what_the_editor_may_offer(
    brazos, dana
) -> None:
    """The offer and the honour come from one list, or they drift again."""
    from tests.test_us_met_helpers import tenant_ctx

    with tenant_ctx(brazos):
        statement_payload = runner.run(
            "statement", {"from": SEPT_START.isoformat(), "to": SEPT_END.isoformat()}
        ).payload
        aging_payload = runner.run(
            "ar_aging", {"from": SEPT_START.isoformat(), "to": SEPT_END.isoformat()}
        ).payload

    # ⚠ **THE OFFER IS THE RUN'S SET; THE HONOUR IS THE REPORT'S UNION.** They
    # are deliberately different: `served_columns` is what may be ASKED for, so
    # a bookmarked `columns` survives a subject switch, and this is what the
    # panel DRAWS — an account statement has no `occupant`, and a tick box for
    # a column this run cannot serve is a control over nothing. Measured in a
    # browser at 1440: the section read `7 of 9` before this split.
    assert statement_payload["column_choices"] == list(
        statement_module.STATEMENT_COLUMNS
    )
    assert set(runner.served_columns("statement", datasets.BY_CODE["journal_lines"])) == (
        set(statement_module.STATEMENT_COLUMNS)
        | set(statement_module.UNIT_STATEMENT_COLUMNS)
    )
    assert "column_choices" not in aging_payload, (
        "a dataset-backed report must carry no new key: the panel goes on "
        "reading GET /reports/datasets for all forty-five of them"
    )


def test_def_rep_7072__save_still_refuses_a_name_no_declaration_offers(
    brazos, dana
) -> None:
    """§8.1's wall is unmoved — a clerk still cannot invent a column."""
    from tests.test_us_met_helpers import tenant_ctx

    with tenant_ctx(brazos):
        definition = runner.resolve("statement")
        bad = definition.__class__(
            **{
                **{
                    field: getattr(definition, field)
                    for field in definition.__dataclass_fields__
                },
                "columns": ("entry_date", "not_a_column_anybody_declares"),
            }
        )
        with pytest.raises(runner.UnknownParameter):
            runner.validate(bad)

        good = definition.__class__(
            **{
                **{
                    field: getattr(definition, field)
                    for field in definition.__dataclass_fields__
                },
                "columns": tuple(statement_module.STATEMENT_COLUMNS),
            }
        )
        # ⚠ **AND IT NO LONGER REFUSES THE REPORT'S OWN COLUMNS.** Before the
        # fix a clerk who ticked what the panel drew could not save it either:
        # `validate` checked the same dataset list.
        runner.validate(good)


# ═══════════════════════════════════════════════════════════════════════════
# DEF-REP-7053 · THE EXPORT WAS BUILT AND NOT WIRED
# ═══════════════════════════════════════════════════════════════════════════
def test_def_rep_7053__the_statement_is_a_registered_export_resource() -> None:
    """`exportable` asks this registry, so the button is drawn or it is not."""
    resource = export_kernel.export_resource("statement")
    assert resource is not None, (
        "`statement_stream` has been in MODULE_STREAMS since P2.8 and no clerk "
        "could reach it: the viewer draws Download only where `exportable` is "
        "true, and `exportable` asks this registry"
    )
    assert resource.slug == "statement"
    assert resource.money is True, "a statement is money and its file says so"
    assert resource.basis == "posting", (
        "BR-REP-001 — the ledger strikes every figure on the BOOK date and "
        "reports/0007 moved the definition's basis to match; the filename is "
        "the only thing telling a bookkeeper which of two files is which"
    )
    assert "subject_id" in resource.filters, (
        "without it the file is a statement about nobody"
    )


def test_def_rep_7053__the_file_carries_every_column_the_report_serves() -> None:
    """A file that dropped a column would disagree with the screen."""
    resource = export_kernel.export_resource("statement")
    assert set(resource.header) == set(statement_module.UNIT_STATEMENT_COLUMNS), (
        "the union of both subjects: the unit statement's `occupant` and "
        "`account` are empty on an account statement, which is a different "
        "fact from a column that was never offered"
    )


def test_def_rep_7053__the_export_reaches_the_stream_and_not_a_page() -> None:
    """§8.2 — *the right path never holds a page*."""
    assert runner.stream_for("statement", "journal_lines") is statement_module.statement_stream


# ═══════════════════════════════════════════════════════════════════════════
# DEF-REP-7052 · NO STATEMENT NAMED WHAT IT WAS ABOUT
# ═══════════════════════════════════════════════════════════════════════════
def test_def_rep_7052__a_new_subject_plugs_in_at_one_place() -> None:
    """The thing lane REP-SUBJ-2 needs, asserted rather than described.

    A subject publishes a head by declaring `head_from` (already done, `P2.14`)
    and registering ONE resolver. Nothing on a screen changes.
    """
    for name in subject_module.SUBJECTS:
        chosen = subject_module.resolve(name)
        assert chosen.head_from, f"{name!r} declares no head fields"
    assert set(subject_head.HEAD_RESOLVERS) <= set(subject_module.SUBJECTS)
    assert "account" in subject_head.HEAD_RESOLVERS
    assert "unit" in subject_head.HEAD_RESOLVERS
    # `customer` and `premises` are refused by the viewer today and so have no
    # resolver — a resolver over a query that never runs is law 2's mirror.
    assert set(statement_module.SUBJECTS_NOT_SERVED) == {"customer", "premises"}
    assert not (set(statement_module.SUBJECTS_NOT_SERVED) & set(subject_head.HEAD_RESOLVERS))


def test_def_rep_7052__compose_walks_the_subjects_own_declaration() -> None:
    """Order and membership are the SUBJECT's, never the resolver's."""
    unit = subject_module.resolve("unit")
    head = subject_head.compose(
        unit,
        "any-id",
        {
            "premises_label": "1408 Elm Street",
            "unit_label": "Apt 3B",
            # An extra key a resolver happened to return is IGNORED: the head
            # is what the subject declares, in its order.
            "nonsense": "ignored",
        },
    )
    assert head == {
        "subject": "unit",
        "fields": [
            {"field": "premises_address", "value": "1408 Elm Street"},
            {"field": "unit_label", "value": "Apt 3B"},
        ],
    }, "hard rule 8 — the BUILDING's address plus the unit's LABEL, in that order"


def test_def_rep_7052__an_unresolvable_part_is_dropped_and_never_guessed() -> None:
    unit = subject_module.resolve("unit")
    head = subject_head.compose(
        unit, "any-id", {"premises_label": "1408 Elm Street", "unit_label": None}
    )
    assert head["fields"] == [
        {"field": "premises_address", "value": "1408 Elm Street"}
    ]
    assert subject_head.compose(unit, "any-id", {}) is None, (
        "a head with no parts is None, so the screen renders nothing rather "
        "than an empty separator"
    )
    assert subject_head.compose(unit, None, {"unit_label": "Apt 3B"}) is None, (
        "no record named, nothing to say"
    )


def test_def_rep_7052__the_statement_publishes_a_head_and_never_an_id(
    brazos, dana
) -> None:
    """THE DEFECT: a page of somebody's money with nothing saying whose."""
    from tests.ledger_le_fixtures import make_accounts
    from tests.test_us_met_helpers import tenant_ctx

    with tenant_ctx(brazos):
        account = make_accounts(dana, brazos, {})["ACC-1042"]
        payload = runner.run(
            "statement",
            {
                "from": SEPT_START.isoformat(),
                "to": SEPT_END.isoformat(),
                "subject_id": str(account.id),
            },
        ).payload

    head = payload.get("head")
    assert head is not None, (
        "the statement has never named the account it is about — not this one "
        "and not the CustomerStatementPage it replaced"
    )
    assert head["subject"] == "account"
    values = [field["value"] for field in head["fields"]]
    assert values, "a head with no parts must be published as None, not as empty"
    # B14 rule 31 — the id selects the record and is never a visible value.
    assert str(account.id) not in " ".join(values)
    assert account.account_no in values, (
        "the account NUMBER is what the clerk typed into the chooser and what "
        "the customer reads on their bill"
    )


def test_def_rep_7052__a_statement_about_nobody_publishes_no_head(brazos, dana) -> None:
    from tests.test_us_met_helpers import tenant_ctx

    with tenant_ctx(brazos):
        payload = runner.run(
            "statement", {"from": SEPT_START.isoformat(), "to": SEPT_END.isoformat()}
        ).payload
    assert "head" not in payload


def test_def_rep_7052__no_other_report_grew_a_head(brazos, dana) -> None:
    """Additive: the forty-five reports about no particular record are unmoved."""
    from tests.test_us_met_helpers import tenant_ctx

    with tenant_ctx(brazos):
        payload = runner.run(
            "ar_aging", {"from": SEPT_START.isoformat(), "to": SEPT_END.isoformat()}
        ).payload
    assert "head" not in payload
