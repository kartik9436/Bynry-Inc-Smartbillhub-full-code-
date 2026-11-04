# ── Trace ──────────────────────────────────────────────
# Story:    US-AUD-004 (GET /audit-log — the S61 viewer, which is the lookup
#           path support uses)   Screens: S61
# Rules:    BR-SHL-020 r2 clause 3 (PO 2026-08-19 — a refusal the user cannot
#           act on says it is a system error and gives them an identifier they
#           can read aloud to support) · BR-AUD-018 (the refused-attempt row,
#           whose `entity_id` IS the trace id) · BR-AUD-009/013 (the S61 filter
#           vocabulary this rides on)
# Defects:  DEF-328 (`trace_id` generated, audited and returned in every
#           envelope — and rendered to a user by nothing, anywhere)
# ───────────────────────────────────────────────────────
"""DEF-328 — the support reference is SEARCHABLE, not merely displayed.

WHY THIS FILE EXISTS AT ALL. The PO's ruling has a trap in it, stated in the
ruling's own words: *"a shortened id that support cannot look up is worse than
none, because the user reads it out and the call stalls."* The screen shows the
first eight hex characters of the trace id, uppercased and grouped — `5F2B-9C1D`
— and the audit row stores all thirty-two. Those two halves are one change, and
this is the test that they meet.

⚠ AND DEF-328 IS PRECISELY A TEST-SHAPE DEFECT, so the shape here matters. Three
tests already mentioned `trace_id` before this one and every one of them asserted
that the ENVELOPE CARRIES it — never that a person could reach anything with it.
That is why a field complete at four layers stayed invisible for months. So this
file asserts the LOOKUP, end to end: the value a user reads aloud, typed into the
S61 entity filter, returns the attempt row for the refusal they were looking at.
The browser half — that the sentence containing the reference is on the screen at
all — is `07-frontend/e2e/DEF-322-refusal-copy.spec.ts`, because a type is not a
screen.
"""

import uuid

import pytest

from apps.audit import selectors as audit_selectors
from tests.test_us_aud_004_006_viewer import write_row  # noqa: F401 (fixture plumbing)
from tests.test_us_idn_helpers import idn  # noqa: F401 (fixture import)

pytestmark = pytest.mark.django_db

# The frontend's `supportRef()` — mirrored here so the test states the contract
# rather than importing it across a language boundary.
SUPPORT_REF_HEX = 8


def support_ref(trace_id: str) -> str:
    """`5f2b9c1d3e…` → `5F2B-9C1D`, exactly as 07-frontend/src/api/client.ts."""
    head = trace_id[:SUPPORT_REF_HEX]
    return f"{head[:4]}-{head[4:]}".upper()


def _refusal_row(tenant, trace_id: str):
    """The BR-AUD-018 attempt row core/errors.py writes for a refusal: the trace
    id lands in `entity_id`, under entity_type `request`."""
    return write_row(
        tenant,
        action="refusal.attempt",
        entity_type="request",
        entity_id=uuid.UUID(trace_id),
        after={"code": "VAL-001", "br_ref": None, "method": "POST", "refused": True},
    )


def _find(tenant, reference: str):
    return list(
        audit_selectors.audit_queryset(
            tenant.id, filters={"entity_type": "request", "entity_id": reference}
        )
    )


def test_def328_the_reference_a_user_reads_aloud_finds_the_attempt_row(idn):
    """THE WHOLE POINT. Support is given eight characters over the phone and
    must reach the refusal. Dashes and case are what a person types, so both are
    tolerated; the row that comes back carries the full trace id."""
    trace_id = uuid.uuid4().hex
    row = _refusal_row(idn.silvercreek, trace_id)
    reference = support_ref(trace_id)  # e.g. "5F2B-9C1D" — what the screen shows

    for typed in (reference, reference.lower(), reference.replace("-", ""), f" {reference} "):
        found = _find(idn.silvercreek, typed.strip())
        assert [r.id for r in found] == [row.id], typed
        assert found[0].entity_id.hex == trace_id  # the FULL id, for the log grep


def test_def328_a_reference_that_matches_nothing_returns_nothing(idn):
    """A mistyped reference must answer empty, never 'everything' — a filter that
    silently falls back to no filter would hand support the whole trail."""
    _refusal_row(idn.silvercreek, uuid.uuid4().hex)
    assert _find(idn.silvercreek, "0000-0000") == []


def test_def328_the_full_trace_id_still_works_unchanged(idn):
    """The prefix path is an ADDITION. Anyone (or any script) holding the whole
    trace id from the server log keeps the exact, indexed lookup."""
    trace_id = uuid.uuid4().hex
    row = _refusal_row(idn.silvercreek, trace_id)
    assert [r.id for r in _find(idn.silvercreek, str(uuid.UUID(trace_id)))] == [row.id]
    assert [r.id for r in _find(idn.silvercreek, trace_id)] == [row.id]


def test_def328_a_prefix_shorter_than_the_reference_is_refused(idn):
    """Seven characters is not the reference. Accepting it would let a filter
    that is nearly empty sweep unrelated tenants' worth of rows into a support
    answer, and the displayed form is always eight."""
    trace_id = uuid.uuid4().hex
    _refusal_row(idn.silvercreek, trace_id)
    assert _find(idn.silvercreek, trace_id[:7]) == []
    assert len(_find(idn.silvercreek, trace_id[:8])) == 1


def test_def328_the_reference_does_not_cross_a_tenant_boundary(idn):
    """BR-AUD-007 is not weakened by a prefix match: the reference is looked up
    inside the caller's tenant, and a neighbour's identical prefix is invisible."""
    trace_id = uuid.uuid4().hex
    _refusal_row(idn.bluemesa, trace_id)
    assert _find(idn.silvercreek, support_ref(trace_id)) == []
    assert len(_find(idn.bluemesa, support_ref(trace_id))) == 1
