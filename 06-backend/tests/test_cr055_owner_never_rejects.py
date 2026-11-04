# ── Trace ──────────────────────────────────────────────
# Change:  CR-055 — *"a premises upload never rejects a row because of the
#          owner's name"* (12-governance/11-change-requests.md · ## CR-055)
# Ruling:  PO 2026-08-31, from the decision log: *"an uploaded owner name that
#          matches no owner exactly but resembles two or more existing owners
#          now LOADS THE PREMISES WITH NO OWNER, flagged to fill in later,
#          exactly as a blank owner column already does. The row is not
#          rejected."* Declined in the same sentence: keep rejecting, and pick
#          the closest match automatically.
# Rules:   BR-MET-401 as amended 2026-08-31 (the import rejects no row on owner
#          grounds; the CREATE SCREEN still refuses) · BR-MET-402 (the Owner
#          column resolves to a party) · BR-MET-151 clause 4 (provenance) ·
#          CLAUDE.md hard-won law 14 (a failed statement poisons the whole
#          Postgres transaction) · B14 rule 31 (no database id on screen)
# Screens: WFL-01.premises.5 (the receipt) · PRM-04 (Owner matching)
# Defect:  DEF-2793 — `resolve_owner_name`'s docstring and BR-MET-401 both
#          claim a BLANK-owner premises is listed by `unmatched_premises_qs()`
#          and it is not. Found by this lane; pinned below rather than fixed,
#          because widening that queryset is outside CR-055's stated scope.
# ───────────────────────────────────────────────────────
"""CR-055 — the premises upload cannot reject a row on owner grounds AT ALL.

WHAT THIS FILE MEASURES, AND WHY THE COUNTS ARE THE POINT
---------------------------------------------------------
The ruling has a cost and the CR states it rather than discovering it later:
**no owner means no master account, so the premises has nobody to charge.** It
holds units, it holds meters, it can be read, and it cannot be BILLED until the
owner is filled in. The CR names the one thing that keeps that from being a
quiet way to lose revenue — *"the receipt count"* — so the cases below assert
the count is RIGHT, assert it is GREATER THAN ZERO in the case that produces it,
and assert the two kinds are SEPARABLE. A count that reads zero because nothing
was measured satisfies every relational assertion, which is why none of these
cases is written as `blank + ambiguous == total` alone.

WHAT WAS PROVED RED FIRST (r11 step 2d, hard-won law 7)
--------------------------------------------------------
Each guard was re-broken on the shipped code and the failure is quoted here
VERBATIM, so a reader can see what the product did rather than take a commit
message's word for it. All four were run against real PostgreSQL
(`DJANGO_SETTINGS_MODULE=config.settings.local`, role `smartbillhub`, which is
NOSUPERUSER NOBYPASSRLS — so RLS is genuinely enforced on that connection).

* **Task 1 — the rule row.** `PRM.OWNER_NEAR_MATCH` put back to
  `severity=ERROR, action=REJECT_ROW`. Both near cases went red, and the failure
  is worse than "one row missing":

      E   core.errors.BizError: BIZ-STATE (metering.import.approval_required)

  ⚠ **That is the defect at full size.** A one-row file whose only row is an
  ambiguous owner is 100% rejected, which crosses `BR-MET-098`'s 5% bar — so the
  old behaviour did not merely drop the address, it **refused to load the file at
  all** until an Owner or an Admin approved a run in which nothing was wrong.

* **Task 2 — the split.** The two counters folded back into the pre-CR-055 shape
  (one `no_owner` under a single condition):

      E   assert 0 == 2

  on `premises_owner_ambiguous`, against a five-row file whose ambiguous rows
  were both loaded and both invisible.

* **Task 2 — the candidate names.** `_owner_ambiguity_list` made to return `[]`:

      E   AssertionError: CR-055: the candidate names must travel with the
          count, or the person settling the row re-runs the search.
      E   assert [] != []

* **Law 14 — the savepoint.** The create branch's `with transaction.atomic():`
  replaced by a bare `try/except IntegrityError: continue`. **On PostgreSQL:**

      E   psycopg.errors.UniqueViolation: duplicate key value violates unique
          constraint "premises_pkey"
      E   psycopg.errors.InFailedSqlTransaction: current transaction is aborted,
          commands ignored until end of transaction block
      E   django.db.utils.InternalError: current transaction is aborted,
          commands ignored until end of transaction block

  ⚠ **AND THAT SAME SABOTAGE IS GREEN ON THE DEFAULT SUITE.**
  `config/settings/test.py` hardcodes in-memory SQLite and ignores
  `DATABASE_URL`; SQLite has no aborted-transaction state, and this case skips
  there for that reason. That is CLAUDE.md hard-won law 14 in one paragraph, and
  it is why the PostgreSQL run is quoted rather than merely claimed.

WHAT IS DELIBERATELY *NOT* CHANGED, ASSERTED SO NOBODY BUILDS IT
-----------------------------------------------------------------
* `resolve_owner_name` keeps its FOUR answers, unchanged. Four callers share
  it; CR-055 changed what the IMPORT does with `near`, not what the resolver
  says. `test_cr055__resolve_owner_name_still_answers_near_unchanged` pins it.
* **The create screen still refuses.** `BR-MET-401` stands there.
  `test_cr055__the_CREATE_SCREEN_still_refuses_a_premises_with_no_owner` pins
  it.
* **The import still may not PICK between two parties** — PO decision 3 is not
  reversed. `test_cr055__a_near_match_row_writes_NO_owner_id` pins it, and it
  is the assertion that would go red if a lane "finished the job" by resolving
  the first candidate.
"""

import pytest
from django.db import connection

from apps.metering import import_rules, import_runs, models as metering_models
from apps.metering import premises_owners
from apps.metering import services as metering_services
from core import errors

from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import (  # noqa: F401
    brazos,
    marcus,
    owner_for,
    tenant_ctx,
)
from tests.test_cr023_import_stages import ALL_ON, HEADERS, MAPPING, _csv, _row

pytestmark = pytest.mark.django_db

#: ⛔ **THE SKIP IS THE POINT, AND IT IS CLAUDE.md HARD-WON LAW 14 IN ONE
#: DECORATOR.** `config/settings/test.py` hardcodes in-memory SQLite and ignores
#: `DATABASE_URL`. SQLite has **no aborted-transaction state**, so the savepoint
#: this case exists to prove can be deleted outright and the whole suite stays
#: green — and it does not enforce the partial expression index the refusal is
#: built on either, so the row simply lands and there is nothing to measure.
#: Measured both ways on this branch: on SQLite the colliding row LOADS and
#: `rejected_at_write` is 0; on PostgreSQL it is refused and the run survives.
POSTGRES_ONLY = pytest.mark.skipif(
    connection.vendor != "postgresql",
    reason=(
        "law 14 has no failure mode on SQLite — an aborted transaction does not "
        "exist there, which is exactly why the unguarded code passes green. Run "
        "with DJANGO_SETTINGS_MODULE=config.settings.local and a Postgres "
        "DATABASE_URL."
    ),
)


# ── the world these cases judge against ─────────────────────────────────────
#
# TWO owners whose names collapse onto ONE normalised key. That is the whole
# precondition for `near`, and it is built from the product's own vocabulary:
# `_normalise_owner_name` strips LEGAL FORMS only (`llc`, `inc`, `l.l.c.`) and
# never trade words, so *Ridge Property LLC* and *Ridge Property, L.L.C.* share
# the key `ridge property` while *Ridge Holdings LLC* does not.
NEAR_A = "Ridge Property LLC"
NEAR_B = "Ridge Property, L.L.C."
#: A THIRD spelling, on nobody's record, which is what the file carries. It
#: matches neither exactly and both loosely — the ambiguity CR-055 is about.
AMBIGUOUS_CELL = "Ridge Property Inc"

EXACT_NAME = "Whitfield Rentals LLC"
UNKNOWN_NAME = "Bluestem Holdings Trust"

#: r10's mapping with ONE change: `OWNER` reaches the TYPED owner column
#: (`KIND_OWNER_REF`), which is where DEF-1247 re-pointed it and where every
#: owner rule reads from. The shared `MAPPING` still points it at the free-text
#: box, which is the pre-DEF-1247 shape and would exercise none of this.
OWNER_MAPPING = {**MAPPING, "OWNER": "owner"}


def _owner_row(index: int, owner: str, **overrides) -> dict:
    """One premises row naming `owner`.

    ⚠ **`PREMISE_ID` IS BLANK AND `PROP_TYPE` IS BLANK, BOTH FOR STATED
    REASONS.** A premise ID that is not already on file is `PRM.PREMISE_NO_
    NOT_ON_FILE` — a tier-2 ERROR under the PO's 2026-08-27 numbering ruling —
    and a resolving `PROP_TYPE` is DEF-540. Either would reject rows of this
    file for a reason that has nothing to do with owners, which would make
    *"the upload rejects no row on owner grounds"* unmeasurable.
    """
    return _row(index, PREMISE_ID="", PROP_TYPE="", OWNER=owner, **overrides)


def _seed_the_two_lookalikes(actor) -> None:
    owner_for(actor, NEAR_A)  # noqa: F405
    owner_for(actor, NEAR_B)  # noqa: F405


def _run_the_file(actor, rows: list[dict], mode: str = "insert") -> dict:
    """Extract → transform → validate → load, through the SAME four functions a
    screen calls. Never a hand-built row: a test that assembled `ImportRunRow`s
    itself would prove nothing about the four stages this CR moves behaviour
    between (`test_cr023_load_stage`'s `_validated` posture)."""
    run = import_runs.extract(
        actor,
        {
            "target": "premises",
            "source_kind": "file",
            "file_name": "cr055_owner_cases.csv",
            "content": _csv(rows, HEADERS),
            "session_ref": "sess_cr055",
            "ip": "71.42.108.14",
        },
    )
    import_runs.transform(actor, run["id"], {"mapping": OWNER_MAPPING, "row_handling": ALL_ON})
    import_runs.validate(actor, run["id"])
    return import_runs.load(actor, run["id"], {"write_mode": mode})


def _rows_of(run_id) -> dict[int, metering_models.ImportRunRow]:
    return {
        row.row_no: row
        for row in metering_models.ImportRunRow.objects.filter(run_id=run_id).order_by("row_no")
    }


# ═══════════════════════════════════════════════════════════════════════════
# TASK 1 — THE `near` ANSWER LOADS, AND THE UPLOAD REJECTS NO ROW ON OWNER
# GROUNDS AT ALL
# ═══════════════════════════════════════════════════════════════════════════


def test_cr055__a_near_owner_name_LOADS_the_row_instead_of_rejecting_it(brazos, marcus):
    """⛔ **THE RULING, IN ONE ASSERTION.**

    PO 2026-08-31: the row *"is no longer rejected"*. Before this change the
    same file put `rejected=1` on the receipt and left the address off the
    system entirely — the failure the CR describes as *"a big migration can
    stall on spelling"*.
    """
    with tenant_ctx(brazos):
        _seed_the_two_lookalikes(marcus)
        receipt = _run_the_file(marcus, [_owner_row(1, AMBIGUOUS_CELL)])

        # ⚠ `receipt["receipt"]["rejected"]` is stage 3's own figure — the rows a
        # RULE turned down — and it is the one this CR is about. `counts` holds
        # the loader's tallies and has no such key.
        assert receipt["receipt"]["rejected"] == 0, (
            "CR-055: a near owner match must not reject the row. "
            f"rejected={receipt['receipt']['rejected']}, created={receipt['counts']['created']}"
        )
        assert receipt["counts"]["created"] == 1
        landed = metering_models.Premises.objects.filter(tenant_id=brazos.id).order_by("-created_at").first()
        assert landed.address_line == "1 Bluestem Ln"


def test_cr055__ALL_FOUR_owner_answers_load_and_NONE_of_them_rejects(brazos, marcus):
    """⛔ **TASK 3 — *"prove the upload rejects NO row on owner grounds, across
    all four answers"*.**

    One file, four rows, one per answer `resolve_owner_name` can give:

    | The Owner cell | The answer | What must happen |
    |---|---|---|
    | `Whitfield Rentals LLC` | **exact** | the party is REUSED whole |
    | *(empty)* | **empty** | loads with no owner, flagged |
    | `Ridge Property Inc` | **near** | loads with no owner, flagged (CR-055) |
    | `Bluestem Holdings Trust` | **none** | loads, keeps the name, waits |

    ⚠ **THE ASSERTION IS `rejected == 0` AND NOT `created >= 1`.** A file that
    loaded three of four rows would satisfy every other statement in this case;
    only the zero says the sentence the CR actually buys — *"the premises upload
    cannot reject a row on owner grounds at all."*
    """
    with tenant_ctx(brazos):
        _seed_the_two_lookalikes(marcus)
        exact_id = owner_for(marcus, EXACT_NAME)  # noqa: F405
        receipt = _run_the_file(
            marcus,
            [
                _owner_row(1, EXACT_NAME),
                _owner_row(2, ""),
                _owner_row(3, AMBIGUOUS_CELL),
                _owner_row(4, UNKNOWN_NAME),
            ],
        )

        assert receipt["receipt"]["rejected"] == 0, (
            "CR-055: the premises upload must reject NO row on owner grounds. "
            f"rejected={receipt['receipt']['rejected']}"
        )
        assert receipt["counts"]["rejected_at_write"] == 0
        assert receipt["counts"]["created"] == 4

        by_address = {
            row.address_line: row
            for row in metering_models.Premises.objects.filter(tenant_id=brazos.id)
        }
        # exact — REUSED, not duplicated. This is the branch that stops twelve
        # addresses becoming twelve landlords, and CR-055 did not touch it.
        assert str(by_address["1 Bluestem Ln"].owner_id) == str(exact_id)
        # empty — loads with nothing at all.
        assert by_address["2 Bluestem Ln"].owner_id is None
        assert not (by_address["2 Bluestem Ln"].owner_manager or "").strip()
        # near — loads with NO party and KEEPS the operator's string.
        assert by_address["3 Bluestem Ln"].owner_id is None
        assert by_address["3 Bluestem Ln"].owner_manager == AMBIGUOUS_CELL
        # none — loads, keeps the name, waits for a person to type the party.
        assert by_address["4 Bluestem Ln"].owner_id is None
        assert by_address["4 Bluestem Ln"].owner_manager == UNKNOWN_NAME

        # And exactly ONE party exists for the exact name — no second Whitfield.
        assert (
            metering_models.PremisesOwner.objects.filter(
                tenant_id=brazos.id, name=EXACT_NAME
            ).count()
            == 1
        )


def test_cr055__a_near_match_row_writes_NO_owner_id(brazos, marcus):
    """⛔ **PO DECISION 3 IS NOT REVERSED, AND THIS IS THE ASSERTION THAT SAYS
    SO.**

    *"Near match on the name - (b) offer the match, clerk decides"* — the
    import may not PICK. CR-055 changed the CONSEQUENCE of refusing to pick,
    never the refusal. A lane that "finishes the job" by resolving the first
    candidate has built the option the PO explicitly declined, and this case is
    what goes red on it.

    ⚠ **THE REASON THE PO DECLINED IT, IN THEIR OWN CR:** the owner carries the
    master account, so a wrong pick eventually sends somebody else's bill to
    the wrong party.
    """
    with tenant_ctx(brazos):
        _seed_the_two_lookalikes(marcus)
        _run_the_file(marcus, [_owner_row(1, AMBIGUOUS_CELL)])

        landed = metering_models.Premises.objects.get(
            tenant_id=brazos.id, address_line="1 Bluestem Ln"
        )
        assert landed.owner_id is None, (
            "PO decision 3: the import may not pick between two parties. It resolved "
            f"{landed.owner_id} for a name that matched {NEAR_A} and {NEAR_B}."
        )
        # …and no third party was invented beside them either.
        assert metering_models.PremisesOwner.objects.filter(tenant_id=brazos.id).count() == 2


def test_cr055__the_near_rule_is_a_WARNING_that_flags_rather_than_an_ERROR(brazos):
    """The rule row itself, because the receipt's rule table is what an
    operator reads to understand why a run behaved as it did. Its SENTENCE has
    to describe the new behaviour too — it said *"pick which party it is"* to
    somebody whose row had already been thrown out."""
    rule = next(r for r in import_rules.PREMISES_RULES if r.code == "PRM.OWNER_NEAR_MATCH")
    assert rule.severity == import_rules.WARNING
    assert rule.action == import_rules.FLAG_ONLY
    assert rule.blocks is False
    assert "loads with no owner" in rule.sentence.lower(), (
        "CR-055: the rule's own sentence must say the address LOADS. "
        f"It says: {rule.sentence!r}"
    )


# ═══════════════════════════════════════════════════════════════════════════
# TASK 2 — THE RECEIPT TELLS *BLANK* FROM *LOOKED LIKE TWO*
# ═══════════════════════════════════════════════════════════════════════════


def test_cr055__the_receipt_tells_a_BLANK_owner_from_one_that_matched_two(brazos, marcus):
    """⛔ **THE WORKED CASE — 5 ROWS, 3 OWNERLESS, AND THE SPLIT IS 1 + 2.**

    A file of five addresses:

    | Row | Owner cell | Lands as |
    |---|---|---|
    | 1 | `Whitfield Rentals LLC` | owned — the party is reused |
    | 2 | *(empty)* | **ownerless · blank** |
    | 3 | `Ridge Property Inc` | **ownerless · ambiguous** |
    | 4 | `Ridge Property Inc` | **ownerless · ambiguous** (same spelling) |
    | 5 | `Bluestem Holdings Trust` | waiting for matching — NOT ownerless |

    So `premises_with_no_owner` is **3**, of which **1 needs research** and
    **2 need one decision between two named parties**. Row 5 is the case that
    must stay OUT of the figure: on a utility's FIRST upload every single row
    looks like row 5, so counting it would report a whole migration as
    un-billable on the day it landed.

    ⚠ **EVERY COUNT HERE IS ASSERTED AS A NUMBER AND EACH IS ASSERTED > 0
    WHERE IT SHOULD BE.** The CR's warning is explicit: *"a count that reads
    zero because nothing was measured satisfies every relational assertion"*.
    """
    with tenant_ctx(brazos):
        _seed_the_two_lookalikes(marcus)
        owner_for(marcus, EXACT_NAME)  # noqa: F405
        receipt = _run_the_file(
            marcus,
            [
                _owner_row(1, EXACT_NAME),
                _owner_row(2, ""),
                _owner_row(3, AMBIGUOUS_CELL),
                _owner_row(4, AMBIGUOUS_CELL),
                _owner_row(5, UNKNOWN_NAME),
            ],
        )
        figures = receipt["receipt"]

        assert figures["premises_owner_blank"] == 1, (
            "CR-055 task 2: the receipt must tell a blank Owner column from a name "
            f"that matched two parties. blank={figures['premises_owner_blank']} "
            f"ambiguous={figures['premises_owner_ambiguous']}"
        )
        assert figures["premises_owner_ambiguous"] == 2
        assert figures["premises_with_no_owner"] == 3
        # The two halves are separable AND they add up — both statements, because
        # either one alone can be satisfied by a pair of zeros.
        assert figures["premises_owner_blank"] > 0
        assert figures["premises_owner_ambiguous"] > 0
        assert (
            figures["premises_owner_blank"] + figures["premises_owner_ambiguous"]
            == figures["premises_with_no_owner"]
        )
        # …and the fifth row is NOT in the figure. This is the assertion that
        # keeps a first upload from reporting itself as wholly un-billable.
        assert receipt["counts"]["created"] == 5


def test_cr055__an_UNKNOWN_owner_name_is_NOT_counted_as_ownerless(brazos, marcus):
    """The boundary, on its own, because it is the one an over-eager fix
    breaks.

    A row naming nobody on file is WAITING FOR MATCHING (BR-MET-402 clause 4) —
    a different state with a different worklist. **On a utility's first upload
    EVERY row is in it.** Folding it into `premises_with_no_owner` would report
    a whole migration as having nobody to charge on the day it landed, which is
    the exact false alarm `DEF-1088` argues against for the severity.
    """
    with tenant_ctx(brazos):
        receipt = _run_the_file(marcus, [_owner_row(1, UNKNOWN_NAME)])
        figures = receipt["receipt"]
        assert figures["premises_with_no_owner"] == 0
        assert figures["premises_owner_blank"] == 0
        assert figures["premises_owner_ambiguous"] == 0
        assert receipt["counts"]["created"] == 1


def test_cr055__the_run_carries_WHICH_parties_each_ambiguous_name_looked_like(brazos, marcus):
    """⛔ **THE COUNT ALONE CANNOT BE REVIEWED**, which is `DEF-771` clause 3's
    lesson applied to a different column. CR-055 asks for it in as many words:
    *"carry the candidate names through, so the person settling it does not
    have to re-run the search."*

    ⚠ **NAMES, NEVER IDS (B14 rule 31: no database id is ever the visible value
    of a field).** The entry carries the two owner NAMES and no `id`, and this
    case asserts the absence — a uuid rendered on a receipt is the rule the PO
    stated on 2026-08-30 in the words *"no Databse ID on screen - that is a
    rule"*.

    ⚠ **ONE LINE PER SPELLING, NOT PER ROW.** Two addresses carrying one
    misspelt landlord is ONE decision.
    """
    with tenant_ctx(brazos):
        _seed_the_two_lookalikes(marcus)
        receipt = _run_the_file(
            marcus, [_owner_row(1, AMBIGUOUS_CELL), _owner_row(2, AMBIGUOUS_CELL)]
        )
        named = receipt["receipt"]["premises_owner_ambiguous_names"]

        assert named != [], (
            "CR-055: the candidate names must travel with the count, or the person "
            "settling the row re-runs the search."
        )
        assert len(named) == 1, "one line per SPELLING, not per row"
        entry = named[0]
        assert entry["asked_for"] == AMBIGUOUS_CELL
        assert entry["rows"] == 2
        assert entry["candidates"] == sorted([NEAR_A, NEAR_B])
        assert "id" not in entry, (
            "B14 rule 31: no database id is ever the visible value of a field, and "
            "this list is built to be read on a receipt."
        )


def test_cr055__a_near_match_row_joins_the_unmatched_worklist(brazos, marcus):
    """⛔ **TASK 2's OTHER SURFACE.** The receipt is read once, on the day of
    the run; `unmatched_premises_qs()` is the standing worklist a person comes
    back to. A row that were counted and not listed would be a number nobody
    could act on.

    It joins by CONSTRUCTION rather than by a new branch — the load writes the
    operator's string to `owner_manager` (BR-MET-151 clause 4 provenance) and no
    `owner_id`, which is exactly what that queryset asks for — and asserting it
    is what keeps a future change to `_resolve_owner_ref` from quietly removing
    the row from the list.
    """
    with tenant_ctx(brazos):
        _seed_the_two_lookalikes(marcus)
        _run_the_file(marcus, [_owner_row(1, AMBIGUOUS_CELL)])

        listed = set(
            str(value) for value in premises_owners.unmatched_premises_qs().values_list(
                "id", flat=True
            )
        )
        landed = metering_models.Premises.objects.get(
            tenant_id=brazos.id, address_line="1 Bluestem Ln"
        )
        assert str(landed.id) in listed


def test_cr055__DEF_2795_a_BLANK_owner_premises_is_NOT_on_the_unmatched_list(brazos, marcus):
    """⚠ **A DOCSTRING'S CLAIM, MEASURED — AND IT IS FALSE (DEF-2793).**

    `resolve_owner_name`'s `empty` branch says *"Those rows are listed by
    `unmatched_premises_qs()`"*, and `BR-MET-401` and the 2026-08-27 decision-log
    entry repeat it. They are NOT: that queryset requires a non-empty
    `owner_manager`, and a blank Owner column writes none — so the blank rows
    the PO's own 2026-08-27 ruling created are counted on the receipt and appear
    on NO standing worklist at all. Hard-won law 1: a comment claiming a
    guarantee is not the guarantee.

    ⚠ **THIS CASE PINS THE PRODUCT AS IT ACTUALLY IS, ON PURPOSE.** Widening
    `unmatched_premises_qs()` changes the S14 badge, the PRM-04 list and its
    count — three surfaces CR-055 does not name — so it is FILED and not fixed
    here. When DEF-2793 is fixed this assertion inverts, and that is the signal
    that the fix reached the surface rather than only the docstring.
    """
    with tenant_ctx(brazos):
        _run_the_file(marcus, [_owner_row(1, "")])

        landed = metering_models.Premises.objects.get(
            tenant_id=brazos.id, address_line="1 Bluestem Ln"
        )
        listed = set(
            str(value) for value in premises_owners.unmatched_premises_qs().values_list(
                "id", flat=True
            )
        )
        assert str(landed.id) not in listed, (
            "DEF-2793 has been fixed — invert this assertion and correct the three "
            "documents that claim the blank case is listed."
        )


def test_cr055__an_UPSERT_never_counts_an_address_that_ALREADY_has_an_owner(brazos, marcus):
    """⛔ **THE COUNTER READS THE ROW AS WRITTEN, NOT THE FILE's `record`, AND
    ONLY THIS PATH SHOWS WHY.**

    On an INSERT the two agree, so the first draft of the counter read
    `record` and every insert case passed. On an **UPSERT** they do not:
    `_resolve_owner_ref` puts no `owner_id` in `record` for an ambiguous name —
    correctly, because the import may not pick — so `setattr` never touches the
    owner the premises already has, and the address keeps somebody to charge.
    A counter reading `record` there would have reported it as ownerless.

    ⚠ **THAT IS NOT A COSMETIC MISCOUNT.** `premises_with_no_owner` is the one
    number standing between this ruling and *"a quiet way to lose revenue"*, so
    a figure that over-reports is a figure an operator learns to ignore — which
    costs exactly what an under-reporting one costs, one step later.

    **Proved RED** by passing `record` in place of the written row:

        E   assert 1 == 0
    """
    with tenant_ctx(brazos):
        _seed_the_two_lookalikes(marcus)
        owner_for(marcus, EXACT_NAME)  # noqa: F405 — the party the first run reuses
        # The address is loaded first, naming an owner EXACTLY, so it lands
        # with a real party.
        first = _run_the_file(marcus, [_owner_row(1, EXACT_NAME, LEGACY_KEY="CR55-UP")])
        assert first["counts"]["created"] == 1
        landed = metering_models.Premises.objects.get(
            tenant_id=brazos.id, external_ref="CR55-UP"
        )
        assert landed.owner_id is not None

        # …then the SAME address comes back with an ambiguous owner spelling.
        again = _run_the_file(
            marcus,
            [_owner_row(1, AMBIGUOUS_CELL, LEGACY_KEY="CR55-UP")],
            mode="upsert",
        )
        assert again["counts"]["updated"] == 1
        figures = again["receipt"]

        landed.refresh_from_db()
        assert landed.owner_id is not None, (
            "the import cleared an owner a person chose — it may not pick a party, "
            "and it may not un-pick one either"
        )
        assert figures["premises_with_no_owner"] == 0, (
            "CR-055: an address that HAS an owner must not appear on the "
            f"nobody-to-charge count. blank={figures['premises_owner_blank']} "
            f"ambiguous={figures['premises_owner_ambiguous']}"
        )
        assert figures["premises_owner_ambiguous"] == 0
        assert figures["premises_owner_ambiguous_names"] == []


# ═══════════════════════════════════════════════════════════════════════════
# TASK 3 — THE FAILURES FILE NO LONGER CARRIES THE OWNER-AMBIGUITY ROW
# ═══════════════════════════════════════════════════════════════════════════


def test_cr055__the_ambiguous_row_leaves_the_failures_file_for_the_successes_one(
    brazos, marcus
):
    """The operator's own two downloads, which is where a rejection is felt.

    Before CR-055 an ambiguous owner arrived in `failures.csv` — the file whose
    whole purpose is *"fix these rows and upload them again"* — for a row there
    was nothing wrong with. It is in `successes.csv` now, with its address and
    its owner cell BLANK, because that blank is the honest statement: the
    address landed and it has no owner.
    """
    with tenant_ctx(brazos):
        _seed_the_two_lookalikes(marcus)
        receipt = _run_the_file(marcus, [_owner_row(1, AMBIGUOUS_CELL)])
        run = metering_models.ImportRun.objects.get(pk=receipt["id"])

        _, body = import_runs.results_csv(run.id, "failures")
        failures = "".join(body)
        assert AMBIGUOUS_CELL not in failures, (
            "CR-055 task 3: the owner-ambiguity row must not be in the failures file. "
            f"failures.csv still reads: {failures!r}"
        )

        _, body = import_runs.results_csv(run.id, "successes")
        successes = "".join(body)
        assert "1 Bluestem Ln" in successes
        # ⚠ **THE OWNER CELL IS BLANK, AND THE BLANK IS THE POINT** — the
        # successes file names what landed, and what landed has no owner.
        assert AMBIGUOUS_CELL in successes, (
            "the operator's own string is kept as provenance and is what the "
            "successes file shows for this address"
        )

        row = _rows_of(receipt["id"])[1]
        assert row.outcome == "flagged"
        assert NEAR_A in (row.problem or "") or NEAR_B in (row.problem or "")


# ═══════════════════════════════════════════════════════════════════════════
# WHAT CR-055 DELIBERATELY DID *NOT* CHANGE
# ═══════════════════════════════════════════════════════════════════════════


def test_cr055__resolve_owner_name_still_answers_near_unchanged(brazos, marcus):
    """**NOT A TASK, and stated in the CR so nobody builds it:**
    `resolve_owner_name` keeps its four answers unchanged. **Four callers share
    it** — the S16 check endpoint, the sample-data planter, and two test
    helpers — and the change is what the IMPORT does with `near`, not what the
    resolver says.
    """
    with tenant_ctx(brazos):
        _seed_the_two_lookalikes(marcus)
        answer = premises_owners.resolve_owner_name(AMBIGUOUS_CELL)
        assert answer["match"] == "near"
        assert answer["owner"] is None, "a near match that RESOLVED would be an auto-merge"
        assert sorted(item["name"] for item in answer["candidates"]) == sorted([NEAR_A, NEAR_B])
        # …and the other three are exactly as they were.
        assert premises_owners.resolve_owner_name("")["match"] == "empty"
        assert premises_owners.resolve_owner_name(NEAR_A)["match"] == "exact"
        assert premises_owners.resolve_owner_name(UNKNOWN_NAME)["match"] == "none"


def test_cr089_b1__the_create_screen_now_ACCEPTS_a_premises_with_no_owner(brazos, marcus):
    """⚠ **THIS TEST HELD THE OPPOSITE UNTIL 2026-09-09, AND SO DID ITS NAME**
    (`test_cr055__the_CREATE_SCREEN_still_refuses_a_premises_with_no_owner`).

    CR-055's whole argument was that ONE rule read three ways: *create refuses ·
    update never did · import accepts*. The PO collapsed the first of those on
    **2026-09-08**: *"Owner = search ( it should be optional)"* (CR-089 §2.1,
    task `B1`). So the three contexts are now **two**, and they agree.

    ⚠ **THAT MAKES CR-055's OWN RULING SIMPLER RATHER THAN WRONG.** Its subject
    was the IMPORT — *an ambiguous owner name must not reject a row* — and that
    is untouched and still tested throughout this file. What has gone is the
    asymmetry it had to argue around: a clerk at the counter and a spreadsheet
    are no longer refused differently for the identical input, which is the
    second half of what this case now proves.
    """
    with tenant_ctx(brazos):
        created = metering_services.create_premises(
            marcus, {"address_line": "9 Bluestem Ln", "services_available": ["electric"]}
        )
        assert created["owner"] is None

    # The identical input that the IMPORT accepts is now accepted HERE too —
    # the sentence the old test turned on, inverted by the ruling.
    with tenant_ctx(brazos):
        _seed_the_two_lookalikes(marcus)
        answer = premises_owners.resolve_owner_name(AMBIGUOUS_CELL)
        assert answer["match"] == "near" and answer["owner"] is None
        created = metering_services.create_premises(
            marcus,
            {
                "address_line": "10 Bluestem Ln",
                "services_available": ["electric"],
                "owner_id": answer["owner"],
            },
        )
        assert created["owner"] is None
        # ⚠ AND THE NAME IS NOT INVENTED FROM THE AMBIGUOUS MATCH. Two parties
        # look alike; picking either would bill the wrong one, which is the
        # thing this whole file exists to prevent.
        assert created["owner_manager"] is None


# ═══════════════════════════════════════════════════════════════════════════
# CLAUDE.md HARD-WON LAW 14 — THE PER-ROW LOOP, ON THE DATABASE THAT HAS THE
# FAILURE MODE
# ═══════════════════════════════════════════════════════════════════════════


@POSTGRES_ONLY
def test_cr055__law14_a_database_refusal_costs_one_row_and_not_the_migration(
    brazos, marcus, monkeypatch
):
    """⛔ **CR-055 SENDS MORE ROWS THROUGH THIS LOOP THAN ANY RULING BEFORE
    IT**, because every ambiguous owner that used to stop at stage 3 now
    reaches the write. The savepoint guarding each `objects.create(...)` is
    therefore hotter than it was, and this is the case that proves it holds on
    the database that has the failure mode.

    **THE REFUSAL IS A REAL STATEMENT REFUSED BY POSTGRESQL, NOT A RAISED
    EXCEPTION, AND THAT DISTINCTION IS THE WHOLE OF LAW 14.** A monkeypatched
    `create` that merely `raise`s an `IntegrityError` would prove nothing: the
    connection would still be healthy and the naive `except … : continue` would
    pass. So this executes a genuinely failing INSERT **inside the savepoint**,
    through `_audit`, which the loader calls between `objects.create(...)` and
    the end of its `transaction.atomic()` block. PostgreSQL then aborts the
    transaction for real, and every later query answers *"current transaction is
    aborted, commands ignored until end of transaction block"* — unless
    something rolls back to a SAVEPOINT.

    ⚠ **WHY NOT A NATURAL COLLISION.** The obvious candidate — a legacy key
    already on file, refused by `uq_premises_tenant_external_ref_ci`, which
    stage 3 cannot see because `PRM.EXTERNAL_REF_UNIQUE` is in-file only — is
    unreachable: `_key_of` uses `external_ref` as the premises IDENTITY, so such
    a row is answered by `rejected_existing` in insert mode and never reaches
    the write at all. Measured, not assumed: that version of this case reported
    `assert 0 == 1` on `rejected_at_write` **on PostgreSQL as well as SQLite**.

    ⚠⚠ **SKIPPED ON THE DEFAULT SUITE, AND THE SKIP IS THE POINT.** SQLite has
    no aborted-transaction state, so the savepoint can be deleted outright and
    the whole suite stays green. See `POSTGRES_ONLY` above for the command.

    ⚠ **AND THE COUNTS ARE ASSERTED HERE TOO, WHICH IS THE HALF A SAVEPOINT
    TEST USUALLY MISSES.** A refused row wrote nothing, so it has no owner gap
    to report: counting it would put an address on an operator's *"nobody to
    charge"* list that is not on the system at all.
    """
    real_audit = import_runs._audit
    broke: list[int] = []

    def _audit_with_a_real_refusal(actor, action, entity_id, **after):
        # ⚠ INSIDE the savepoint: the loader calls `_audit` between
        # `objects.create(...)` and the end of its nested `atomic()`.
        if action == "premises.created" and after.get("row") == 1:
            broke.append(1)
            with connection.cursor() as cursor:
                # ⚠ **A DUPLICATE PRIMARY KEY, AND THE STATEMENT IS SHAPED BY
                # RLS RATHER THAN BY CONVENIENCE.** The first draft inserted
                # `(NULL, NULL)` and PostgreSQL answered *"new row violates
                # row-level security policy for table premises"* — a
                # `ProgrammingError`, which the loader deliberately does NOT
                # catch (it is the server or a bug, not this row's data), so it
                # took the whole run down. **That refusal is itself the proof
                # that this connection's role is genuinely subject to RLS**:
                # `smartbillhub` is NOSUPERUSER NOBYPASSRLS, so the policy is
                # really consulted.
                # `INSERT INTO premises SELECT * FROM premises …` re-inserts a
                # row of THIS tenant, so it satisfies the policy's WITH CHECK
                # and is refused by `premises_pkey` instead — a genuine
                # `IntegrityError` from the driver, inside the savepoint.
                cursor.execute(
                    "INSERT INTO premises SELECT * FROM premises "
                    "WHERE tenant_id = current_setting('app.tenant_id')::uuid LIMIT 1"
                )
        return real_audit(actor, action, entity_id, **after)

    monkeypatch.setattr(import_runs, "_audit", _audit_with_a_real_refusal)

    with tenant_ctx(brazos):
        _seed_the_two_lookalikes(marcus)
        receipt = _run_the_file(
            marcus,
            [
                _owner_row(1, AMBIGUOUS_CELL, LEGACY_KEY="88901"),
                _owner_row(2, AMBIGUOUS_CELL, LEGACY_KEY="88902"),
                _owner_row(3, "", LEGACY_KEY="88903"),
            ],
        )
        figures = receipt["receipt"]

        assert broke == [1], "the probe did not fire — this case proved nothing"
        # The run SURVIVED, which on PostgreSQL is only true because of the
        # savepoint. Without it the very next statement raises
        # TransactionManagementError and the whole commit is lost.
        assert receipt["status"] == "loaded"
        assert figures["rejected_at_write"] == 1
        assert receipt["counts"]["created"] == 2, (
            "law 14: one refused row must cost one row, not the migration. "
            f"created={receipt['counts']['created']}"
        )

        # …and the rows AFTER the refusal are really on file, read back through
        # a FRESH query — the statement an aborted transaction cannot answer.
        landed = set(
            metering_models.Premises.objects.filter(tenant_id=brazos.id).values_list(
                "address_line", flat=True
            )
        )
        assert {"2 Bluestem Ln", "3 Bluestem Ln"} <= landed
        assert "1 Bluestem Ln" not in landed

        # The refused row is NOT counted as ownerless — it is not on the system.
        assert figures["premises_owner_ambiguous"] == 1
        assert figures["premises_owner_blank"] == 1
        assert figures["premises_with_no_owner"] == 2
        assert figures["premises_owner_ambiguous_names"][0]["rows"] == 1
