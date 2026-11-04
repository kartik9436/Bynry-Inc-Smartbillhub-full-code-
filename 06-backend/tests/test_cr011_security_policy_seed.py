# ── Trace ──────────────────────────────────────────────
# Change:   CR-011 item 8 (12-governance/11-change-requests.md) — the security-
#           policy row-at-provisioning question, which the PO DELEGATED in one
#           word on 2026-08-18: *"you decide"*.
#           Screens: S8 (Settings → Security)
# Rules:    BR-IDN-025 (password seed defaults) · BR-IDN-026 (session timeout
#           defaults) · BR-IDN-019 (one tenant-wide record, audited on save) ·
#           BR-TEN-063 (a replay writes nothing)
# Tests:    this file
# Impacts:  apps/identity/services.py (seed_security_policy) ·
#           apps/tenancy/seams.py · apps/tenancy/services.py
# ───────────────────────────────────────────────────────
"""The decision taken under CR-011's delegation, and its two guarantees.

**The decision:** provisioning WRITES the row. The full argument lives on
`apps.identity.services.seed_security_policy`; the short version is that an
unwritten row makes a tenant's password rule a Python class constant, so moving
BR-IDN-025's ratified minimum would change the effective policy of every tenant
that never opened the Security tab — with no author, no before/after and no
`audit_log` row, because nothing was ever saved.

**The two guarantees this file exists to hold, and the second is the one that
makes the decision safe:**

  1. a freshly provisioned tenant HAS the row, and the repair door works for a
     tenant that already exists (hard-won law 4 in its data form);
  2. **NOBODY'S EFFECTIVE POLICY MOVES.** The written row must carry exactly the
     figures `selectors.security_policy_values` served from an unsaved instance
     before it existed. If those two ever diverge, this decision silently
     re-policies every tenant on the host, which is the very failure it was
     taken to prevent — so the test compares the two directly rather than
     restating the numbers.
"""

import pytest

from tests.test_us_ten_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_ten_helpers import tenant_ctx
from tests.test_us_met_helpers import (  # noqa: F401 — brazos/dana are fixtures
    brazos,
    dana,
)

pytestmark = pytest.mark.django_db


def test_cr011_provisioning_writes_the_security_policy_row(brazos):
    """RED BEFORE THE DECISION LANDED: `assert 0 == 1`.

    The live database held ZERO `security_policies` rows for the only tenant on
    the system, so *"which tenants have configured security?"* could not be
    answered at all: no row meant "never looked", indistinguishable from
    nothing.
    """
    from apps.identity import models as identity_models

    with tenant_ctx(brazos):
        assert (
            identity_models.SecurityPolicy.objects.filter(tenant_id=brazos.id).count() == 1
        ), (
            "CR-011 item 8: provisioning writes the security-policy row so a "
            "tenant's password rule is DATA, not a Python constant a deploy can move"
        )


def test_cr011_the_written_row_serves_exactly_the_old_fallback_figures(brazos):
    """**The guarantee that makes the decision reversible and safe.**

    Before this, `security_policy_values` built an UNSAVED
    `SecurityPolicy(tenant_id=…)` and returned its column defaults. After it,
    the same function reads a real row. The two must be indistinguishable, so
    this asserts the written row against a fresh unsaved instance rather than
    against six numbers typed here — a restated figure is a figure that can
    drift from the rule it copies.
    """
    from apps.identity import models as identity_models
    from apps.identity import selectors as identity_selectors

    with tenant_ctx(brazos):
        served = identity_selectors.security_policy_values(brazos.id)
        # `limits` is what an admin may CHOOSE, not what this utility HAS
        # (CR-145-BRC08); it is the same for every utility and is not a value.
        served.pop("limits")
        # What the read side would have returned with no row at all.
        fallback = identity_models.SecurityPolicy(tenant_id=brazos.id)
        assert served == {
            "pw_min_length": fallback.pw_min_length,
            "pw_require_mixed": fallback.pw_require_mixed,
            "pw_require_symbol": fallback.pw_require_symbol,
            "pw_expiry_days": fallback.pw_expiry_days,
            "session_timeout_minutes": fallback.session_timeout_minutes,
            # CR-145-BRC08 — the five that were platform constants.
            "absolute_session_hours": fallback.absolute_session_hours,
            "keep_signed_in_offered": fallback.keep_signed_in_offered,
            "keep_signed_in_days": fallback.keep_signed_in_days,
            "lockout_max_failed": fallback.lockout_max_failed,
            "lockout_minutes": fallback.lockout_minutes,
            "ip_allowlist": [],
            # PO 2026-10-21 — the field app's capture life, seeded 7 days.
            "field_capture_hours": fallback.field_capture_hours,
            # CR-188-BRC10 — an emailed sign-in link's life, seeded 7 days.
            "password_link_valid_days": fallback.password_link_valid_days,
        }
        # And the ratified figures themselves, in the plain English the PO would
        # be shown (BR-IDN-025/026): minimum length 8, upper+lower+number
        # required, symbol optional, expiry never, idle timeout 60 minutes, no
        # IP restriction. Stated ONCE, here, so a change to any of them fails a
        # test that names the rule rather than passing quietly.
        assert served["pw_min_length"] == 8
        assert served["pw_require_mixed"] is True
        assert served["pw_require_symbol"] is False
        assert served["pw_expiry_days"] is None
        assert served["session_timeout_minutes"] == 60
        assert served["ip_allowlist"] == []


def test_cr011_the_seam_is_wired_idempotent_and_reports_what_it_did(brazos):
    """The repair door. RED BEFORE THE FIX: `AttributeError: module
    'apps.tenancy.seams' has no attribute 'seed_security_policy'`.

    A provisioning change reaches a tenant on the day it is created and never
    afterwards, and the only tenant on the live host predates this by a day. So
    the seam has to be callable a second time, has to create nothing when the
    row is there (BR-TEN-063), and has to SAY which of the two it did.
    """
    from apps.identity import models as identity_models
    from apps.tenancy import seams

    with tenant_ctx(brazos):
        replay = seams.seed_security_policy()
        assert replay is not None and replay["created"] is False

        # Delete it the way a tenant on an older build has it — absent — and
        # prove the door repairs.
        identity_models.SecurityPolicy.objects.filter(tenant_id=brazos.id).delete()
        repaired = seams.seed_security_policy()
        assert repaired is not None and repaired["created"] is True
        assert identity_models.SecurityPolicy.objects.filter(tenant_id=brazos.id).count() == 1


def test_cr011_seeding_never_overwrites_a_policy_an_admin_set(brazos, dana):
    """BR-TEN-012's posture on a table that is not a reference list.

    A System Admin who tightened the minimum to 12 must not have it put back to
    8 by a repair run — which is precisely what `manage.py seed_demo --tenant`
    does on a live host, on purpose, for other reasons.
    """
    from apps.identity import selectors as identity_selectors
    from apps.identity import services as identity_services
    from apps.tenancy import seams

    with tenant_ctx(brazos):
        identity_services.save_security_policy(
            actor=dana,
            tenant_id=brazos.id,
            values={"pw_min_length": 12, "session_timeout_minutes": 30},
            actor_ip=None,
        )
        assert seams.seed_security_policy() == {
            "created": False,
            "pw_min_length": 12,
            "session_timeout_minutes": 30,
        }
        served = identity_selectors.security_policy_values(brazos.id)
        assert served["pw_min_length"] == 12
        assert served["session_timeout_minutes"] == 30
