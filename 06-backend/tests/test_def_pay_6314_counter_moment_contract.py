# ── Trace ──────────────────────────────────────────────
# Defect:  DEF-PAY-6314 — the Start-counter form posted `service_centre` where
#          `POST /counters` reads `service_centre_id`, and never sent the
#          REQUIRED `opened_at` at all, so a clerk could not open a till.
#          DEF-PAY-6315 — the same break on close, force-close and declare.
# Rules:   BR-PAY-1191 (backdate within the same day — PO ruling 2026-09-23,
#          *"(b) Backdate within the same day"*) · BR-TEN-043 + gate G6 (no
#          wall clock under apps/payments/) · BR-TEN-081 / OQ-153 (a naive
#          moment is anchored in the TENANT's zone) · B14 rule 33 (a refusal
#          sentence is six words per sentence; RATIONALE is zero words)
# Tests:   this file · 07-frontend/src/features/payments/
#          counterWriteContract.def6314.dom.test.tsx (the client half)
# ───────────────────────────────────────────────────────
"""The server half of the counter-moment contract.

The FRONT END half asserts that the body a screen posts carries the keys this
endpoint reads. That cannot prove the bound is a RULE — a screen's `min`/`max`
is a suggestion, and `curl` is not a screen. This is the half that proves the
refusal exists on the money path.

⚠ **WHY THE CLOCK IS NOT MOCKED HERE.** `_refuse_a_moment_off_today` compares
against `settings_seam.tenant_now()`, which resolves `apps.tenancy.selectors
.tenant_now` BY NAME — one clock, one zone, one place. The cases below build
their moments FROM that same read, so they are true at any instant of any day
and in any server timezone. A frozen clock would have to be frozen in the
tenant's zone to mean anything, which is the very thing under test.
"""

from __future__ import annotations

import json
import re
from datetime import timedelta
from pathlib import Path

import pytest

from apps.payments import counters_api, settings_seam
from core import errors

from tests.test_us_met_helpers import *  # noqa: F401,F403 — brazos · dana · marcus
from tests.test_us_met_helpers import tenant_ctx  # noqa: F401 — a fixture

#: G6's own strip, by the same expression, so the two agree by construction.
INLINE_CODE_RE = re.compile(r"`[^`]*`")

MOMENT_FIELDS = ("opened_at", "closed_at", "declared_at")
NOT_TODAY_KEY = "payments.counter.moment_not_today"


def _refusal(moment, field="opened_at"):
    """Run the bound and hand back the refusal, or None when it allowed it."""
    try:
        counters_api._refuse_a_moment_off_today(moment, field)
    except errors.ValidationError as refused:
        return refused
    return None


# ════════════════════════════════════════════════════════════════════════════
# BR-PAY-1191 — backward within today, and no further
# ════════════════════════════════════════════════════════════════════════════
@pytest.mark.django_db()
def test_br_pay_1191_this_moment_is_allowed(brazos):
    """The green case. A rule that refuses everything is not a rule."""
    with tenant_ctx(brazos):
        assert _refusal(settings_seam.tenant_now()) is None


@pytest.mark.django_db()
def test_br_pay_1191_earlier_today_is_allowed(brazos):
    """**THE WHOLE POINT OF THE PICKER**, and the PO's own worked case.

    *Dana opens the counter at 09:00, forgets to start it, notices at 11:00 and
    sets it back to 09:00.* That correction is what option (b) chose.
    """
    with tenant_ctx(brazos):
        now = settings_seam.tenant_now()
        start_of_day = now.replace(hour=0, minute=1, second=0, microsecond=0)
        assert _refusal(start_of_day) is None


@pytest.mark.django_db()
def test_br_pay_1191_yesterday_is_refused(brazos):
    """Yesterday moves a shift's takings into a day that is already reported."""
    with tenant_ctx(brazos):
        refused = _refusal(settings_seam.tenant_now() - timedelta(days=1))
    assert refused is not None, "a till could be backdated into a reported day"
    assert refused.message_key == NOT_TODAY_KEY
    assert refused.code == errors.VAL_RANGE
    assert [f["field"] for f in refused.field_errors] == ["opened_at"]


@pytest.mark.django_db()
def test_br_pay_1191_a_future_moment_is_refused(brazos):
    """*"The ruling is about correcting a forgotten start, not scheduling one."*

    Both shapes: later TODAY, which a day-equality check alone would allow, and
    tomorrow. The first is the one that needs the instant rather than the date,
    and it is why `tenant_now()` exists beside `tenant_today()`.
    """
    with tenant_ctx(brazos):
        now = settings_seam.tenant_now()
        later_today = _refusal(now + timedelta(minutes=5))
        tomorrow = _refusal(now + timedelta(days=1))
    assert later_today is not None, "a till could be opened in the future"
    assert later_today.message_key == NOT_TODAY_KEY
    assert tomorrow is not None
    assert tomorrow.message_key == NOT_TODAY_KEY


@pytest.mark.django_db()
def test_br_pay_1191_binds_all_four_writes_through_one_helper(brazos):
    """One definition, four routes — B14 rule 43's reason, as an assertion.

    `_required_moment` is the ONLY way a moment enters this module, and all
    four endpoints go through it. A fifth route added without it would be a
    fifth route with no bound, so this reads the SOURCE rather than trusting
    that the four call sites still look the way they did.
    """
    source = Path(counters_api.__file__).read_text(encoding="utf-8")
    assert source.count("_required_moment(") == 5, (
        "four call sites plus one definition — a route was added or removed, "
        "and BR-PAY-1191 is enforced through this helper alone"
    )
    for field in MOMENT_FIELDS:
        assert f'"{field}"' in source
    # The bound is inside the helper, so no endpoint can opt out of it.
    helper = source.split("def _required_moment(")[1].split("\ndef ")[0]
    assert "_refuse_a_moment_off_today(moment, name)" in helper

    with tenant_ctx(brazos):
        stale = (settings_seam.tenant_now() - timedelta(days=2)).isoformat()
        for field in MOMENT_FIELDS:
            with pytest.raises(errors.ValidationError) as refused:
                counters_api._required_moment(
                    {field: stale}, field, message_key=f"payments.counter.{field}_required"
                )
            assert refused.value.message_key == NOT_TODAY_KEY


# ════════════════════════════════════════════════════════════════════════════
# THE REFUSAL REACHES A CLERK AS WORDS, IN ELEVEN LANGUAGES
# ════════════════════════════════════════════════════════════════════════════
def test_br_pay_1191_refusal_renders_in_every_catalogue():
    """`G32`'s blind spot, closed at the raise site rather than trusted.

    G32 resolves a `message_key` only where the helper is defined in the same
    file and reported **0 unresolved** truthfully over 21 live refusals that
    reached a clerk as SILENCE. So this reads the catalogues directly.

    It also holds B14 rule 33's cap: an INSTRUCTION is six words per sentence,
    and the refusal says what to do rather than why the rule exists — RATIONALE
    is zero words on screen.
    """
    locales = Path(__file__).resolve().parents[2] / "07-frontend" / "src" / "i18n" / "locales"
    catalogues = sorted(locales.glob("*.json"))
    assert len(catalogues) == 11, f"expected eleven catalogues, found {len(catalogues)}"
    for path in catalogues:
        catalogue = json.loads(path.read_text(encoding="utf-8"))
        sentence = catalogue.get(NOT_TODAY_KEY)
        assert sentence, f"{path.name}: {NOT_TODAY_KEY} renders as nothing at all"
        for clause in str(sentence).replace("।", ".").split("."):
            assert len(clause.split()) <= 6, f"{path.name}: {clause!r} is over rule 33's cap"


# ════════════════════════════════════════════════════════════════════════════
# THE CLOCK IS TENANCY'S, AND NOTHING UNDER apps/payments/ READS ONE
# ════════════════════════════════════════════════════════════════════════════
def test_the_bound_reads_no_wall_clock_in_the_money_path():
    """Gate G6 bans `timezone.now()` under `/payments/` (BR-TEN-043).

    This is the assertion that stops the obvious "simplification": a lane that
    replaced the seam with `timezone.now()` would make every case above pass on
    a server in the tenant's own zone and fail silently everywhere else.
    """
    for module in (counters_api, settings_seam):
        source = Path(module.__file__).read_text(encoding="utf-8")
        for banned in ("timezone.now()", "datetime.now()"):
            for line in source.splitlines():
                # ⚠ **STRIP BACKTICKED INLINE CODE FIRST, EXACTLY AS G6 DOES**
                # (`INLINE_CODE_RE`). This assertion was written without it and
                # failed on its own subject: `settings_seam.tenant_now`'s
                # docstring says *"GATE G6 BANS `timezone.now()` under
                # /payments/"*, which is PROSE QUOTING THE RULE and is the one
                # thing the rule must not fire on. A check stricter than the
                # gate it mirrors reports a violation the gate would pass, and
                # then the next lane "fixes" correct code to satisfy it.
                judged = INLINE_CODE_RE.sub("", line.split("#")[0])
                assert banned not in judged, f"{module.__name__}: {line.strip()}"


@pytest.mark.django_db()
def test_tenant_now_is_offset_bearing_and_in_the_tenants_zone(brazos):
    """A naive instant compared against an anchored one compares two days."""
    with tenant_ctx(brazos):
        now = settings_seam.tenant_now()
        assert now.tzinfo is not None
        assert now.utcoffset() == settings_seam.tenant_timezone().utcoffset(now.replace(tzinfo=None))


# ── Lifecycle ─────────────────────────────────────────────
# packet: DEF-PAY-6314 · DEF-PAY-6315 · BR-PAY-1191 (PO ruling 2026-09-23) ·
#         CR-136-BRC07 §3.1–§3.3 · CLAUDE.md hard-won law 7 · BR-TEN-043 · BR-TEN-081
# generated: 2026-09-23 by LANE COUNTER-OPEN
# checklist: A✔ B✔ C✔ D✔ E=n/a(the client half is its own file) F✔ G✔ H=deferred(PO 2026-08-09)
# gates: pytest tests/test_def_pay_6314_counter_moment_contract.py · G6 · G32
# exceptions: none
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
