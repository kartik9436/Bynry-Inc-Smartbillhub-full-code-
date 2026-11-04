# ── Trace ──────────────────────────────────────────────
# Change:  CR-142-BRC07 Phase 4 · `P4.14` — BI tier 2, scheduled delivery.
#          Brief p015, §7.8 p088–p090, read as IMAGES per B14 rule 42.
# Rules:   **RULED, p090, FINAL:** *"A scheduled file may leave the product —
#          Yes — admin-set destinations, encrypted in transit, every delivery
#          logged."* · CLAUDE.md hard rule 1 (tenant scoping) · hard rule 6
#          (idempotency) · hard rule 7 (every money action writes `audit_log`)
#          · the PRIME DIRECTIVE (never resolve an open question by choosing a
#          value — `OQ-REP-12767`) · hard-won law 7 (*ask what would make this
#          check pass WRONGLY*) · law 14 (a savepoint, not a bare except)
# Open:    **OQ-REP-12767 — OPEN.** SFTP host-key trust. Asserted REFUSED here.
# ───────────────────────────────────────────────────────
"""A SIGNED LINK IS A CREDENTIAL. THIS FILE TRIES TO FORGE ONE, SIX WAYS.

⚠ **THE POINT OF THIS FILE IS THE REFUSALS, NOT THE HAPPY PATH.** A verifier
that returns the payload unconditionally passes *"a minted token verifies"*
exactly as well as a correct one does — CLAUDE.md hard-won law 7's *a check you
cannot describe a false pass for is a check you do not understand*. So the
happy case is ONE test and the tampering cases are six, and each of them takes
a token that is known-good and breaks exactly one thing about it.

THE SIX, AND WHAT EACH WOULD MEAN IF IT PASSED
──────────────────────────────────────────────
  · a flipped SIGNATURE      → anyone can mint their own link
  · a swapped JOB id         → one link reads every report this tenant has
  · a swapped TENANT id      → one link reads another utility's file
  · an extended `exp`        → the four-hour ruling is decoration
  · a token past its `exp`   → the same, by waiting
  · a foreign PREFIX         → some other feature's signature is accepted here
"""

from __future__ import annotations

import base64
import json
from datetime import UTC, datetime, timedelta

import pytest

from apps.reports import destinations, models as reports_models, signed_links
from core import errors

from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared tenant fixtures
from tests.test_us_met_helpers import tenant_ctx

pytestmark = pytest.mark.django_db

NOW = datetime(2026, 9, 27, 9, 0, tzinfo=UTC)
A_JOB = "01999999-0000-7000-8000-00000000abcd"
ANOTHER_JOB = "01999999-0000-7000-8000-00000000beef"
ANOTHER_TENANT = "01999999-0000-7000-8000-0000000ffff1"


def _parts(token: str) -> tuple[str, dict, str]:
    prefix, body, signature = token.split(".")
    payload = json.loads(base64.urlsafe_b64decode(body + "=" * (-len(body) % 4)))
    return prefix, payload, signature


def _rebuild(prefix: str, payload: dict, signature: str) -> str:
    body = base64.urlsafe_b64encode(
        json.dumps(payload, separators=(",", ":"), sort_keys=True).encode()
    ).decode("ascii").rstrip("=")
    return f"{prefix}.{body}.{signature}"


# ═══════════════════════════════════════════════════════════════════════════
# THE RULED FIGURE — four hours, and it is read from where the PO put it
# ═══════════════════════════════════════════════════════════════════════════
def test_p4_14_the_link_lives_four_hours_and_the_number_is_not_this_modules():
    """PO ruling 2026-08-30, verbatim: *"dont expire it in minutes - exprise it
    in 3 or 4 hours"*.

    ⚠ **THE ASSERTION IS THAT THE TWO AGREE, NOT THAT EITHER IS 14400.**
    Asserting the literal here would create a second copy of a ruled figure —
    exactly what `signed_links.ttl_seconds` exists to avoid — and it would go on
    passing after a finance re-sign moved the real one.
    """
    from apps.tenancy import document_storage

    assert signed_links.ttl_seconds() == document_storage.url_ttl_seconds()

    _token, expires_at = signed_links.mint(tenant_id=ANOTHER_TENANT, job_id=A_JOB, now=NOW)
    assert expires_at - NOW == timedelta(seconds=document_storage.url_ttl_seconds())


def test_p4_14_a_freshly_minted_link_verifies_to_its_own_tenant_and_job(brazos):
    token, _ = signed_links.mint(tenant_id=brazos.id, job_id=A_JOB, now=NOW)
    claim = signed_links.verify(token, now=NOW)
    assert claim == {"tenant_id": str(brazos.id), "job_id": A_JOB}


# ═══════════════════════════════════════════════════════════════════════════
# THE SIX FORGERIES
# ═══════════════════════════════════════════════════════════════════════════
def test_p4_14_a_flipped_signature_is_refused(brazos):
    token, _ = signed_links.mint(tenant_id=brazos.id, job_id=A_JOB, now=NOW)
    prefix, payload, signature = _parts(token)
    tampered = signature[:-1] + ("A" if signature[-1] != "A" else "B")
    with pytest.raises(errors.NotFoundError):
        signed_links.verify(_rebuild(prefix, payload, tampered), now=NOW)


def test_p4_14_a_link_cannot_be_moved_to_another_job(brazos):
    """The job id is INSIDE the signature, so changing it breaks it. Without
    this, one delivered link would read every report this tenant ever ran."""
    token, _ = signed_links.mint(tenant_id=brazos.id, job_id=A_JOB, now=NOW)
    prefix, payload, signature = _parts(token)
    assert payload["j"] == A_JOB, "the job must be in the payload at all"
    payload["j"] = ANOTHER_JOB
    with pytest.raises(errors.NotFoundError):
        signed_links.verify(_rebuild(prefix, payload, signature), now=NOW)


def test_p4_14_a_link_cannot_be_moved_to_another_tenant(brazos):
    """Hard rule 1 at the edge of the product: this token is the ONLY thing
    that says which utility is asking, so it is the only place that can leak."""
    token, _ = signed_links.mint(tenant_id=brazos.id, job_id=A_JOB, now=NOW)
    prefix, payload, signature = _parts(token)
    assert payload["t"] == str(brazos.id)
    payload["t"] = ANOTHER_TENANT
    with pytest.raises(errors.NotFoundError):
        signed_links.verify(_rebuild(prefix, payload, signature), now=NOW)


def test_p4_14_a_holder_cannot_extend_their_own_expiry(brazos):
    """The four hours are only a rule if the holder cannot edit them."""
    token, _ = signed_links.mint(tenant_id=brazos.id, job_id=A_JOB, now=NOW)
    prefix, payload, signature = _parts(token)
    payload["exp"] = int(payload["exp"]) + 86_400
    with pytest.raises(errors.NotFoundError):
        signed_links.verify(_rebuild(prefix, payload, signature), now=NOW)


def test_p4_14_the_link_stops_working_when_it_expires(brazos):
    """An untampered, correctly-signed token, read four hours and a second on.

    ⚠ **THIS IS THE ONE CASE THAT PROVES THE TTL DOES ANYTHING.** Every other
    case here would pass on a verifier that ignored `exp` entirely.
    """
    token, expires_at = signed_links.mint(tenant_id=brazos.id, job_id=A_JOB, now=NOW)
    just_alive = expires_at - timedelta(seconds=1)
    assert signed_links.verify(token, now=just_alive)["job_id"] == A_JOB

    with pytest.raises(errors.NotFoundError):
        signed_links.verify(token, now=expires_at + timedelta(seconds=1))


def test_p4_14_a_token_from_another_family_is_refused(brazos):
    """Domain separation, at the prefix. A signature minted by any other
    feature that ever signs with `SECRET_KEY` must not verify here."""
    token, _ = signed_links.mint(tenant_id=brazos.id, job_id=A_JOB, now=NOW)
    prefix, payload, signature = _parts(token)
    assert prefix == signed_links.TOKEN_PREFIX
    with pytest.raises(errors.NotFoundError):
        signed_links.verify(_rebuild("sbh_rpt_", payload, signature), now=NOW)


@pytest.mark.parametrize(
    "junk", ["", "nonsense", "a.b", "sbhrd1..", "sbhrd1.@@@.@@@", "sbhrd1.a.b.c"]
)
def test_p4_14_malformed_tokens_are_the_same_no(brazos, junk):
    """One refusal for every no — it must not be possible to tell a malformed
    token from a forged one from an expired one."""
    with pytest.raises(errors.NotFoundError):
        signed_links.verify(junk, now=NOW)


# ═══════════════════════════════════════════════════════════════════════════
# THE RULING'S THREE CONDITIONS
# ═══════════════════════════════════════════════════════════════════════════
def test_p4_14_sftp_is_refused_at_create_and_names_the_open_question(brazos, dana):
    """`OQ-REP-12767`, OPEN. The prime directive: a lane implements up to the
    boundary and stubs the gap with the question's id IN THE CODE.

    ⚠ **REFUSED AT *CREATE*, WHICH IS LAW 2's MIRROR.** A destination that
    could be created and then failed every night would be a live control over a
    dead transport — an administrator sees it in the picker, a clerk chooses it,
    and the failure surfaces weeks later as an operational mystery.
    """
    with tenant_ctx(brazos):
        with pytest.raises(errors.BizError) as refused:
            destinations.create(
                brazos.id,
                name="Finance drop",
                kind=reports_models.DESTINATION_SFTP,
                actor_user_id=None,
            )
    assert refused.value.params["question"] == "OQ-REP-12767"
    assert reports_models.ReportDestination.objects.count() == 0, "nothing was written"


def test_p4_14_a_destination_records_the_administrator_who_set_it_up(brazos, dana):
    """Condition 1: *"destinations are set up by an administrator and never by
    whoever creates the schedule"*. `created_by_user_id` is what makes that
    auditable afterwards rather than merely true at the moment it was typed."""
    who = "01999999-0000-7000-8000-00000000a0a0"
    with tenant_ctx(brazos):
        row = destinations.create(
            brazos.id,
            name="Board pack collector",
            kind=reports_models.DESTINATION_LINK,
            actor_user_id=who,
        )
    assert str(row.created_by_user_id) == who
    assert row.kind == reports_models.DESTINATION_LINK


def test_p4_14_an_unknown_kind_is_refused_by_name(brazos):
    with tenant_ctx(brazos):
        with pytest.raises(errors.ValidationError):
            destinations.create(
                brazos.id, name="x", kind="carrier_pigeon", actor_user_id=None
            )
