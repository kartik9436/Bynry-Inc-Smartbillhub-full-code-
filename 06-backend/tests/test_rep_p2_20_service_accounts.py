# ── Trace ──────────────────────────────────────────────
# Change:  CR-142-BRC07 — the Reports Build Brief, Phase 2 task `P2.20`
#          (*"BI tier 1 — service accounts"*, p12 and §7.8 p88–p89, read as
#          images per B14 rule 42).
# Rules:   CLAUDE.md hard rule 1 (tenant scoping) · hard rule 7 (a money action
#          writes `audit_log`) · hard-won law 7 clause 2 (*"ask what would make
#          this check pass wrongly"*) · law 14 (the suite is SQLite and cannot
#          see a policy)
# ───────────────────────────────────────────────────────
"""THE PARTS OF `P2.20` A DATABASE-FREE SUITE CAN ACTUALLY DECIDE.

⚠ **THE RLS HALF IS NOT HERE AND THAT IS DELIBERATE, NOT A GAP.** `P2.20`'s own
outcome is *"RLS applies unchanged"*, and `config/settings/test.py` hardcodes
in-memory SQLite, **which has no row-level security of any kind** — every
assertion about a policy passes there by vacuum (CLAUDE.md hard-won law 14).
Writing one here would be a check that cannot fail. The proof is
`10-scripts/rep_p2_20_service_account_rls_proof.py`, run on real PostgreSQL 16
under a NOSUPERUSER NOBYPASSRLS role with TWO tenants, and it is what redesigned
the authentication class: the first version resolved the tenant FROM the token
and the proof failed it with *"resolved to nothing"*, because a read with
`app.tenant_id` unset sees no rows at all.

What IS decidable without a database is the credential arithmetic and the allow
list, and those are what this file asserts — in both directions, every time.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from apps.reports import service_accounts as svc


def account(**kwargs):
    """A service account's shape without a database — the fields the rules read."""
    base = {"id": "svc-1", "name": "Power BI · board pack", "report_keys": [], "revoked_at": None}
    base.update(kwargs)
    return SimpleNamespace(**base)


class TestTheToken:
    def test_a_token_is_recognisable_as_ours_and_is_not_stored(self):
        plaintext, hashed, prefix = svc.mint_token()
        assert plaintext.startswith(svc.TOKEN_PREFIX), (
            "a token found in a log or a config file must be recognisable as "
            "this product's, and as a service-account token rather than a session"
        )
        # The stored form is NOT the token, in both directions: not equal, and
        # not merely a substring either — a check on inequality alone would pass
        # for a hash that embedded the secret.
        assert hashed != plaintext
        assert plaintext not in hashed
        assert prefix == plaintext[: svc.PREFIX_KEEP]
        assert plaintext not in prefix

    def test_two_tokens_are_never_the_same(self):
        # ⚠ What would make this pass wrongly: a constant token. 200 samples
        # rather than 2, because 2 equal values is the only thing a two-sample
        # test can see and a generator seeded once per process would pass it.
        minted = {svc.mint_token()[0] for _ in range(200)}
        assert len(minted) == 200

    def test_the_comparison_accepts_the_right_token_and_refuses_the_rest(self):
        plaintext, hashed, _prefix = svc.mint_token()
        assert svc.token_matches(plaintext, hashed) is True
        assert svc.token_matches(plaintext + "x", hashed) is False
        assert svc.token_matches("", hashed) is False
        other, _h, _p = svc.mint_token()
        assert svc.token_matches(other, hashed) is False


class TestTheNamedList:
    def test_a_granted_report_is_allowed_and_an_ungranted_one_is_not(self):
        """§7.8: *"granted Revenue Analysis and Trial Balance can read those two
        and nothing else; AR Ageing later means somebody grants it."*"""
        acc = account(report_keys=["revenue_by_service_rate", "trial_balance"])
        assert svc.may_read(acc, "revenue_by_service_rate") is True
        assert svc.may_read(acc, "trial_balance") is True
        assert svc.may_read(acc, "ar_aging") is False
        assert svc.may_read(acc, "billing_register") is False

    def test_an_empty_grant_denies_everything(self):
        """⚠ **THE DIRECTION AN ALLOW LIST FAILS IN IS THE WHOLE OF ITS VALUE.**
        An empty list meaning *all* would turn a half-finished create into a key
        to the building, silently. Both spellings of empty are asserted, because
        `not keys` and `keys == []` are one keystroke apart and a `None` from a
        JSON column takes the other branch."""
        for empty in ([], None):
            acc = account(report_keys=empty)
            assert svc.may_read(acc, "ar_aging") is False
            assert svc.may_read(acc, "trial_balance") is False

    def test_the_refusal_names_what_is_granted_and_never_the_catalogue(self):
        """A refusal enumerating every key would hand an integration — and
        anybody holding a leaked token — the shape of a utility's reporting."""
        error = svc.refuse_report("ar_aging", ["trial_balance"])
        params = getattr(error, "params", {}) or {}
        assert params.get("granted") == ["trial_balance"]
        assert "keys" not in params, (
            "the clerk-facing route answers an unknown key with the served "
            "vocabulary; this principal must not get that list"
        )


class TestRevocation:
    def test_a_live_credential_is_live_and_a_revoked_one_is_dead_forever(self):
        assert svc.is_live(account()) is True
        assert svc.is_live(account(revoked_at=svc.now())) is False

    def test_revocation_does_not_depend_on_the_clock(self):
        """⚠ A revoked credential is dead, not expired. Asserting it with a
        timestamp far in the past AND far in the future catches an
        implementation that compared `revoked_at` with `now` — which would make
        a credential revoked *tomorrow* usable today."""
        from datetime import UTC, datetime, timedelta

        past = datetime(2020, 1, 1, tzinfo=UTC)
        future = svc.now() + timedelta(days=365)
        assert svc.is_live(account(revoked_at=past)) is False
        assert svc.is_live(account(revoked_at=future)) is False


class TestTheWire:
    def test_the_token_is_in_the_create_answer_and_in_no_other(self):
        acc = account(report_keys=["ar_aging"], token_prefix="sbh_rpt_abc123")
        without = svc.wire(acc)
        assert "token" not in without, (
            "there is no read that can return the token — only the hash is "
            "stored, so this is a property of the design and not of this dict"
        )
        withit = svc.wire(acc, token="sbh_rpt_plaintext")
        assert withit["token"] == "sbh_rpt_plaintext"
        assert withit["token_shown_once"] is True

    def test_no_hash_reaches_the_wire_in_either_shape(self):
        acc = account(report_keys=["ar_aging"], token_prefix="sbh_rpt_abc123")
        acc.token_hash = "the-secret-digest"
        for payload in (svc.wire(acc), svc.wire(acc, token="t")):
            assert "token_hash" not in payload
            assert "the-secret-digest" not in str(payload)


class TestHowItAppearsInStartedBy:
    def test_it_names_itself_and_never_borrows_a_person(self):
        """§7.8: *"it appears in Started by on History like anyone else."*

        ⚠ BR-AUD-019 / BR-RBS-015 — an automation actor never borrows a user
        identity. `AutomationActor` refuses at construction, so this asserts the
        kind and the label rather than the absence of a user id."""
        actor = svc.actor_for(account(name="Power BI · board pack"))
        assert actor.kind == "integration"
        assert actor.name == "Power BI · board pack"
        assert "actor_user_id" not in actor.as_row_fields(), (
            "an automation actor's stored columns are kind, label and version — "
            "a user id among them would be the borrowed identity BR-RBS-015 bans"
        )

    def test_an_unnamed_account_still_produces_a_drawable_actor(self):
        """A blank name would raise inside `AutomationActor` and take down the
        report request. The fallback is a word, never an id (B14 rule 31)."""
        actor = svc.actor_for(account(name=""))
        assert actor.name.strip() != ""
        assert str(getattr(account(), "id", "")) not in actor.name


def test_the_rate_limit_is_a_credential_property_and_not_an_nfr5_cap():
    """⚠ `NFR-5` forbids a ceiling that would have to be REMOVED when T4 arrives
    — a per-tenant account maximum, a row cap, an unpaginated list. A request
    RATE on ONE credential is none of those: a larger utility gets a larger
    number in settings, or a second account, and neither is a migration."""
    assert svc.RATE_PER_MINUTE > 0
    from django.conf import settings

    from apps.reports.service_account_auth import ServiceAccountThrottle

    throttle = ServiceAccountThrottle()
    assert throttle.get_rate().endswith("/min")
    # It is settable without touching code — the property that makes it not a cap.
    settings.REPORT_SERVICE_ACCOUNT_RATE = "6000/min"
    try:
        assert ServiceAccountThrottle().get_rate() == "6000/min"
    finally:
        del settings.REPORT_SERVICE_ACCOUNT_RATE


def test_a_browser_request_is_not_counted_against_any_credential():
    """The throttle sits on a route people use. `get_cache_key` returning `None`
    is DRF's *not throttled here*, so a person's session is unaffected."""
    from apps.reports.service_account_auth import ServiceAccountThrottle

    request = SimpleNamespace(user=SimpleNamespace(id="u1", role="system_admin"))
    assert ServiceAccountThrottle().get_cache_key(request, None) is None


def test_a_bearer_scheme_that_is_not_ours_is_left_alone():
    """⚠ **IT RETURNS `None`, NOT A REFUSAL.** The class sits in front of the
    session authentication on a shared route; refusing somebody else's bearer
    token here would break a request that the class behind it would have
    authenticated perfectly."""
    from apps.reports.service_account_auth import ReportServiceAccountAuthentication

    auth = ReportServiceAccountAuthentication()
    for header in ("", "Basic abc", "Bearer some.jwt.token", "Bearer"):
        request = SimpleNamespace(META={"HTTP_AUTHORIZATION": header}, tenant_id="t1")
        assert auth.authenticate(request) is None, header


def test_a_request_that_named_no_tenant_is_refused_before_any_lookup():
    """⚠ **DENY BY DEFAULT, AND THE PROOF SHOWED WHY IT MATTERS.** A read with
    `app.tenant_id` unset sees zero rows under RLS, so without this the class
    would refuse with *"unknown token"* for a perfectly good token presented on
    a path that named no tenant — a wiring fault reported as a credential fault,
    which is the hardest kind to diagnose."""
    from rest_framework import exceptions as drf_exceptions

    from apps.reports.service_account_auth import ReportServiceAccountAuthentication

    plaintext, _hashed, _prefix = svc.mint_token()
    request = SimpleNamespace(
        META={"HTTP_AUTHORIZATION": f"Bearer {plaintext}"}, tenant_id=None
    )
    with pytest.raises(drf_exceptions.AuthenticationFailed):
        ReportServiceAccountAuthentication().authenticate(request)


# ── Lifecycle ─────────────────────────────────────────────
# packet: CR-142-BRC07 P2.20 (05-prototype/09 Reports Build Brief.pdf p12, p88, p89, read as images per B14 rule 42)
# screens: none — §7.8 tier 1 is *"the report API itself"*
# generated: 2026-09-27 by lane REP-P2-TAIL
# checklist: A✔ B=n/a C✔ D✔ E=n/a F✔ G✔ H=deferred(PO 2026-08-09)
# gates: RED PROVED FIRST — every case run before apps/reports/service_accounts.py existed, failing on ModuleNotFoundError; the empty-grant case was then run against a `not keys or key in keys` implementation and failed, which is the one-keystroke inversion it exists for
# exceptions: (1) the RLS half is NOT asserted here and says so — the suite is SQLite (law 14) and the proof is 10-scripts/rep_p2_20_service_account_rls_proof.py, ALL PASS on PostgreSQL 16 with two tenants on 2026-09-27
# status: VERIFIED-UNRATIFIED · HUMAN-REVIEW-PENDING (🔒 a credential + RLS path)
# ──────────────────────────────────────────────────────────
