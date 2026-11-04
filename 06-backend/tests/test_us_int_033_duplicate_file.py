# ── Trace ──────────────────────────────────────────────
# Story:    US-INT-033 (EP-INT-09) TC-1 · TC-4 · TC-6 — the same bank file
#           twice. US-INT-008 (the bank connection). Screens: S142
# Rules:    BR-INT-020 C (the content hash is computed BEFORE parse) ·
#           BR-INT-009 · BR-INT-019 · BR-INT-039 · BR-INT-054 as amended ·
#           CLAUDE.md hard rule 1 (tenant scoping) · hard rule 6 (idempotency)
# Tests:    this file. The PostgreSQL half — the phase-4 exit test — is
#           tests/test_us_int_033_duplicate_file_pg.py
# Impacts:  apps/integrations/arrivals.py · services.py (`start_run`'s
#           `input_hash`, `finish_run`'s KEEP sentinel) ·
#           adapters/bank_lockbox_file.py
# ───────────────────────────────────────────────────────
"""US-INT-033 on SQLite — a file arrives, arrives again, and is refused by name.

⚠ WHAT THIS FILE CAN AND CANNOT PROVE, SAID FIRST SO NOBODY TRUSTS IT FOR MORE
THAN IT IS WORTH (hard-won law 14). The refusal here is the SERVICE's, and the
service refuses on every vendor, so these cases are real. What SQLite cannot
express is the append-only trigger and RLS `FORCE`; the run row's immutability
and the tenant-isolation half live in the `_pg.py` companion and SKIP rather
than pass vacuously on this suite.

⚠ AND THE CONTROL CASE IS THE POINT OF TC-4. *"Nothing was written"* also
describes an endpoint that is simply broken, so proving the duplicate refusal
means proving a genuinely DIFFERENT file is still accepted in the same
breath. A test that only ever refuses cannot tell the two apart.
"""

from __future__ import annotations

import pytest

from apps.integrations import arrivals, models, services
from tests.test_us_met_helpers import *  # noqa: F401,F403 — brazos · lonestar · dana · erin
from tests.test_us_met_helpers import tenant_ctx

BANK = "bank_lockbox_file"
LOCKBOX = "import_lockbox"

#: J14's file, in the shape that matters here: BYTES, not text.
TUESDAY = b"6,121000248,0000123456,260901,0610,USD,2/\n16,175,0000004250,,A-10432/\n"
#: One byte different — a re-cut file with a new sequence number. It parses to
#: the same rows and it is NOT the same file (the surprising direction).
WEDNESDAY_RECUT = b"6,121000248,0000123456,260901,0611,USD,2/\n16,175,0000004250,,A-10432/\n"


def _bank_connection(tenant, label="Chase lockbox"):
    return models.IntegrationConnection.objects.create(
        tenant=tenant,
        provider_key=BANK,
        label=label,
        environment=models.ENVIRONMENT_PRODUCTION,
        status=models.STATUS_UNTESTED,
        cadence=models.CADENCE_MANUAL,
        config={"source": "upload"},
    )


# ═══════════════════════════════════════════════════════════════════════════
# TC-1 — the hash is computed BEFORE the parse, and the ordering is asserted
#        STRUCTURALLY rather than claimed in a comment.
# ═══════════════════════════════════════════════════════════════════════════


@pytest.mark.django_db
def test_tc1_the_hash_is_on_the_run_row_before_anything_could_parse(brazos):
    """The digest is on the row the moment the row exists.

    ⚠ HOW THIS PROVES AN ORDERING AND NOT JUST A VALUE. `record_arrival` is
    handed bytes that are NOT valid text in any encoding a parser would try —
    a lone `0x80` continuation byte, which `bytes.decode()` refuses. If any
    step between "the file arrived" and "the hash is written" had decoded,
    parsed, or sniffed the content, it would raise here rather than return.
    The run row coming back with a digest on it is therefore evidence about
    the ORDER of operations, not merely about the arithmetic.
    """
    undecodable = b"\x80\x81\x82 not text in any encoding \xff\xfe"
    with pytest.raises(UnicodeDecodeError):
        undecodable.decode("utf-8")  # the premise of the case, made explicit

    with tenant_ctx(brazos):
        connection = _bank_connection(brazos)
        arrival = arrivals.record_arrival(
            connection=connection, operation=LOCKBOX, body=undecodable
        )

    assert arrival.accepted is True
    assert arrival.input_hash, "the digest must exist"
    #: and it is ON THE ROW, not merely on the return value — the row is what
    #: the next arrival matches against.
    assert arrival.run.input_hash == arrival.input_hash
    #: sha-256 of exactly those bytes, computed independently of the module
    #: under test so a change to `content_hash` cannot make this agree with
    #: itself.
    import hashlib

    assert arrival.input_hash == hashlib.sha256(undecodable).hexdigest()


@pytest.mark.django_db
def test_tc1b_the_digest_is_written_at_open_not_only_at_close(brazos):
    """`start_run` carries it — so a run still in flight already has its hash.

    This is the clause the whole refusal rests on: an arrival that is still
    being processed must already be matchable, or two uploads a second apart
    would both be accepted.
    """
    with tenant_ctx(brazos):
        connection = _bank_connection(brazos)
        arrival = arrivals.record_arrival(
            connection=connection, operation=LOCKBOX, body=TUESDAY
        )
        #: the run is OPEN — nothing has closed it, because closing it is a
        #: statement about what the rows meant and that is Runbooks'
        assert arrival.run.finished_at is None
        fresh = models.IntegrationRun.objects.get(id=arrival.run.id)
        assert fresh.input_hash == arrival.input_hash


# ═══════════════════════════════════════════════════════════════════════════
# TC-4 — the second arrival is refused NAMING THE FIRST, and a different file
#        is still accepted. Both halves, or neither means anything.
# ═══════════════════════════════════════════════════════════════════════════


@pytest.mark.django_db
def test_tc4_the_same_file_twice_is_refused_naming_the_first_by_date(brazos):
    with tenant_ctx(brazos):
        connection = _bank_connection(brazos)
        first = arrivals.record_arrival(
            connection=connection, operation=LOCKBOX, body=TUESDAY
        )
        second = arrivals.record_arrival(
            connection=connection, operation=LOCKBOX, body=TUESDAY
        )

    assert first.accepted is True
    assert second.accepted is False
    #: the SAME hash on both rows — that is what makes them the same file
    assert second.input_hash == first.input_hash
    assert second.run.input_hash == first.run.input_hash
    #: it names the FIRST, and by day and time
    assert second.duplicate_of is not None
    assert second.duplicate_of.id == first.run.id
    assert "refused duplicate" in (second.run.summary or "")
    assert first.run.started_at.strftime("%A") in (second.run.summary or "")
    #: *we did not ask* — nothing was parsed and nothing was handed on
    assert second.run.outcome == models.OUTCOME_SKIPPED
    assert second.run.attempted == 0


@pytest.mark.django_db
def test_tc4b_a_genuinely_different_file_is_still_accepted(brazos):
    """THE CONTROL. Without it, "nothing was written" also describes an
    endpoint that refuses everything — which is a broken door, not a guard."""
    with tenant_ctx(brazos):
        connection = _bank_connection(brazos)
        first = arrivals.record_arrival(
            connection=connection, operation=LOCKBOX, body=TUESDAY
        )
        different = arrivals.record_arrival(
            connection=connection, operation=LOCKBOX, body=WEDNESDAY_RECUT
        )

    assert first.accepted is True
    assert different.accepted is True, "a one-byte difference is a NEW file"
    assert different.input_hash != first.input_hash
    assert different.duplicate_of is None


@pytest.mark.django_db
def test_tc4c_a_third_arrival_still_names_the_first_and_not_the_second(brazos):
    """*The same file as Tuesday* stays Tuesday. A refusal that walked back one
    step each time would send a clerk to the wrong row."""
    with tenant_ctx(brazos):
        connection = _bank_connection(brazos)
        first = arrivals.record_arrival(connection=connection, operation=LOCKBOX, body=TUESDAY)
        second = arrivals.record_arrival(connection=connection, operation=LOCKBOX, body=TUESDAY)
        third = arrivals.record_arrival(connection=connection, operation=LOCKBOX, body=TUESDAY)

    assert second.duplicate_of.id == first.run.id
    assert third.duplicate_of.id == first.run.id


# ═══════════════════════════════════════════════════════════════════════════
# TC-6 — the refusal is scoped to ONE CONNECTION and ONE TENANT.
# ═══════════════════════════════════════════════════════════════════════════


@pytest.mark.django_db
def test_tc6_two_banks_at_one_utility_do_not_refuse_each_other(brazos):
    """Chase and BofA are different relationships. Identical bytes on each is
    two arrivals, not a duplicate."""
    with tenant_ctx(brazos):
        chase = _bank_connection(brazos, label="Chase lockbox")
        bofa = models.IntegrationConnection.objects.create(
            tenant=brazos,
            provider_key=BANK,
            label="BofA lockbox",
            environment=models.ENVIRONMENT_SANDBOX,
            status=models.STATUS_UNTESTED,
            cadence=models.CADENCE_MANUAL,
            config={"source": "upload"},
        )
        on_chase = arrivals.record_arrival(connection=chase, operation=LOCKBOX, body=TUESDAY)
        on_bofa = arrivals.record_arrival(connection=bofa, operation=LOCKBOX, body=TUESDAY)

    assert on_chase.accepted is True
    assert on_bofa.accepted is True, "a different bank is a different relationship"
    assert on_chase.input_hash == on_bofa.input_hash, "same bytes, same digest"


@pytest.mark.django_db
def test_tc6b_another_tenants_file_is_not_a_duplicate_of_ours(brazos, lonestar):
    """Hard rule 1. The same bytes at two utilities are two unrelated files,
    and neither may learn anything about the other."""
    with tenant_ctx(brazos):
        ours = _bank_connection(brazos)
        mine = arrivals.record_arrival(connection=ours, operation=LOCKBOX, body=TUESDAY)
    with tenant_ctx(lonestar):
        theirs = _bank_connection(lonestar)
        yours = arrivals.record_arrival(connection=theirs, operation=LOCKBOX, body=TUESDAY)

    assert mine.accepted is True
    assert yours.accepted is True
    assert yours.duplicate_of is None


# ═══════════════════════════════════════════════════════════════════════════
# The regression that the KEEP sentinel exists for — and it is the one this
# wave would have shipped broken.
# ═══════════════════════════════════════════════════════════════════════════


@pytest.mark.django_db
def test_finishing_a_run_does_not_erase_the_hash_that_opened_it(brazos):
    """⚠ THE FAILURE THIS CATCHES IS SILENT AND TOTAL.

    `finish_run` took `input_hash: str | None = None` and assigned it
    unconditionally. Every runner in the module omits that argument, so
    closing an arrival's run row set the column back to NULL — and the NEXT
    arrival of the same file would have found nothing to match. The duplicate
    refusal would have been incapable of firing, with the whole suite green,
    which is exactly law 7's *what would make this check pass wrongly*.

    ⚠ SABOTAGING IT TAUGHT SOMETHING THE NEXT LANE NEEDS, AND THE FIRST
    ATTEMPT WAS NOT ENOUGH. Breaking only the ASSIGNMENT — making
    `run.input_hash = None` unconditionally — left all thirteen cases GREEN,
    because `finish_run` saves with `update_fields` and the column was not in
    the list, so the blanked value never reached the database. **There are two
    halves to this guard and `update_fields` is the one that actually
    decides.** A future edit that adds `"input_hash"` back to that list
    unconditionally re-opens the hole even with the sentinel intact.

    To re-prove it, break BOTH — an unconditional assignment AND an
    unconditional `fields.append("input_hash")`. Two cases then fail, and the
    second one is the one that matters:

        AssertionError: closing a run must not erase its file's hash
        assert None == '070671a222…'
        FAILED test_tc4_the_same_file_twice_is_refused_naming_the_first_by_date

    TC-4 failing alongside it is the proof that the duplicate REFUSAL — not
    merely the column — depends on this.
    """
    with tenant_ctx(brazos):
        connection = _bank_connection(brazos)
        arrival = arrivals.record_arrival(
            connection=connection, operation=LOCKBOX, body=TUESDAY
        )
        digest = arrival.input_hash
        #: whoever owns the processing half closes the row — here, standing in
        #: for Runbooks, with counts this module would never compute itself
        arrivals.close_arrival(
            arrival, attempted=40, succeeded=38, failed=2, skipped=0, summary="handed on"
        )
        closed = models.IntegrationRun.objects.get(id=arrival.run.id)

    assert closed.finished_at is not None
    assert closed.input_hash == digest, "closing a run must not erase its file's hash"

    #: and the refusal still works AFTER the first run is closed — the state a
    #: real second upload arrives in
    with tenant_ctx(brazos):
        again = arrivals.record_arrival(
            connection=connection, operation=LOCKBOX, body=TUESDAY
        )
    assert again.accepted is False
    assert again.duplicate_of.id == arrival.run.id


# ═══════════════════════════════════════════════════════════════════════════
# The boundary — what this module refuses to do (BR-INT-054 as amended).
# ═══════════════════════════════════════════════════════════════════════════


@pytest.mark.django_db
def test_the_arrival_path_writes_no_payment_and_imports_no_parser(brazos):
    """Integrations records that a batch arrived — AND STOPS.

    Two assertions, and the second is the durable one: `arrivals.py` must not
    reach a codec, a parser or the payments module, so a later lane cannot
    quietly grow matching logic into it without this going red.

    ⚠ IT READS THE IMPORTS, NOT THE TEXT — AND THE FIRST DRAFT DID THE OTHER
    THING AND WAS WRONG (found by running it, 2026-09-06). A `grep` for
    `stage_import` over the source cannot tell a CALL from a DOCSTRING, and
    `arrivals.py`'s docstring names `stage_import` and `payment_import.py`
    precisely because explaining where the boundary falls is what that
    docstring is for. So the grep went red over prose that was doing its job
    — law 7's *looking at the wrong thing*, in a check written half an hour
    earlier. Walking the AST asks the question actually worth asking: does
    this module IMPORT the processing half? Prose cannot trip it, and an
    import cannot hide from it whatever it is spelled.
    """
    import ast

    import apps.integrations.arrivals as module

    tree = ast.parse(open(module.__file__, encoding="utf-8").read())
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module)
            imported.update(f"{node.module}.{alias.name}" for alias in node.names)

    for forbidden in ("apps.payments", "apps.integrations.codecs", "apps.integrations.mappings"):
        offending = sorted(one for one in imported if one.startswith(forbidden))
        assert not offending, (
            f"arrivals.py imports {offending} — the processing half is Runbooks' "
            "under BR-INT-054 as amended 2026-09-06"
        )

    #: and no call names the processing half, however it was reached
    called = {
        node.func.attr
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
    }
    assert not ({"stage_import", "commit_batch"} & called), sorted(called)

    from apps.payments import models as payment_models

    with tenant_ctx(brazos):
        connection = _bank_connection(brazos)
        before = payment_models.Payment.objects.count()
        arrivals.record_arrival(connection=connection, operation=LOCKBOX, body=TUESDAY)
        assert payment_models.Payment.objects.count() == before


@pytest.mark.django_db
def test_a_str_body_is_refused_because_something_already_chose_an_encoding(brazos):
    with tenant_ctx(brazos):
        connection = _bank_connection(brazos)
        with pytest.raises(TypeError):
            arrivals.record_arrival(
                connection=connection, operation=LOCKBOX, body="already text"  # type: ignore[arg-type]
            )


@pytest.mark.django_db
def test_an_operation_that_is_not_a_file_is_refused(brazos):
    with tenant_ctx(brazos):
        connection = _bank_connection(brazos)
        with pytest.raises(ValueError):
            arrivals.record_arrival(
                connection=connection, operation="not_a_declared_operation", body=TUESDAY
            )


# ═══════════════════════════════════════════════════════════════════════════
# US-INT-008 — the adapter is BOUND, so the card can actually be connected.
# ═══════════════════════════════════════════════════════════════════════════


def test_the_bank_adapter_is_bound_so_the_card_is_connectable():
    """Hard-won law 2: built is not wired. Until this line existed the bank
    card was live, the manifest was registered, and every connect was refused
    *Cannot be connected yet.*"""
    from apps.integrations.adapters import ADAPTERS
    from apps.integrations.adapters.bank_lockbox_file import BankLockboxFileAdapter

    assert ADAPTERS[BANK] is BankLockboxFileAdapter
    assert BankLockboxFileAdapter.key == BANK


def test_the_service_receive_file_is_reachable_from_a_url():
    """The other half of law 2 — a service nothing routes to is dead code."""
    from apps.integrations import api

    routes = {str(one.pattern) for one in api.urlpatterns}
    assert any("arrival" in one for one in routes), routes
    assert hasattr(services, "receive_file")


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-INT-033 · US-INT-008 (EP-INT-09) + BR-INT-020 C + BR-INT-054
# generated: 2026-09-06 by the CR-069 wave I build lane
# gates: pytest tests/test_us_int_033_duplicate_file.py
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
