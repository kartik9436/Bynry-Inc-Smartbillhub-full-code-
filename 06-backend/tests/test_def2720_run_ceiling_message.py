# ── Trace ──────────────────────────────────────────────
# Defect:   **DEF-2720** — a clerk who trips the bill-run size ceiling is told
#           nothing about it. The count, the ceiling and the two ways out all
#           travel in `params.detail`, which BR-SHL-020 r2 keeps off the screen
#           on purpose, so what a clerk reads is the generic refusal.
#           Screens: S31 step 4 (Work out the bills)
# Rules:    BR-SHL-020 r2 (PO 2026-08-19 — server detail text never reaches a
#           customer screen) · B14 rule 32 clause 4 (no rule id or internal code
#           in clerk-facing copy) · B8 (every BIZ refusal carries its BR-ID)
# Change:   CR-051 task 30 (the ceiling itself)
# ───────────────────────────────────────────────────────
"""The ceiling refusal says the numbers, and says them through the catalogue.

**WHY THIS IS NOT "just render `detail`".** `params.detail` is a DIAGNOSTIC and
BR-SHL-020 r2 keeps it off the screen deliberately — DEF-322 is what happens
when it is not. The ceiling refusal is the one refusal whose entire content is
three facts a clerk needs (this run covers N accounts, this system bills at most
M in one pass, split the cycle), so the fix is not to relax that rule for one
message: it is to give this refusal a `message_key` of its own with the numbers
as PARAMS, which is the only route to a sentence eleven catalogues can carry.

**WHY THE NUMBERS TRAVEL AS INTEGERS AND NOT AS `"25,000"`.** The server's own
sentence groups with commas because it is written for an English log. A
pre-grouped string would print `25,000` to a German clerk whose language groups
with a full stop — wrong, not merely plain. This app has no locale-aware count
formatter on the refusal path (`api/refusalText.ts` interpolates whatever the
envelope carries), so an integer is the one form that is never WRONG in any of
the eleven. Stated rather than assumed; a formatter there is a general gap and
not this defect's.

**RED FIRST (law 7).** Against the branch before this commit, tc1 fails on:

    AssertionError: assert 'billing.run.refused' == 'billing.run.tooLarge'

which is the defect in one line — every rule refusal on the calculate route,
this one included, mapped onto the single generic catalogue entry.
"""

from types import SimpleNamespace

import pytest

from apps.billing import api as billing_api
from apps.billing import run_jobs
from apps.billing.exceptions import BillingRuleError


def _oversized(monkeypatch, settings, *, size: int, ceiling: int) -> BillingRuleError:
    """The refusal `refuse_if_oversized` raises, with no database world.

    The REAL path is already proved by `test_cr051_run_scale.py` tc14/tc15 —
    both doors refuse, before a single row is drafted. What is unproved, and
    what DEF-2720 is entirely about, is the SENTENCE that reaches the person at
    the screen, so the size seam is stubbed and the message is the subject.
    """
    settings.BILLING_MAX_ACCOUNTS_PER_RUN = ceiling
    monkeypatch.setattr(run_jobs.runs, "scope_account_count", lambda **_: size)
    run = SimpleNamespace(cycle_id="cycle-1", scope_services=None)
    with pytest.raises(BillingRuleError) as refused:
        run_jobs.refuse_if_oversized(run)
    return refused.value


def test_def2720_tc1__the_ceiling_refusal_carries_its_own_catalogue_key(
    monkeypatch, settings
):
    """One key, two numbers, and the envelope the screen actually reads."""
    refusal = _oversized(monkeypatch, settings, size=41_000, ceiling=25_000)
    envelope = billing_api._as_catalog_refusal(refusal, "BR-BIL-001")

    assert envelope.message_key == "billing.run.tooLarge"
    assert envelope.params["count"] == 41_000
    assert envelope.params["limit"] == 25_000
    # B8 — the rule id still travels, and still never reaches the sentence.
    assert envelope.br_ref == "BR-BIL-052"


def test_def2720_tc2__the_diagnostic_sentence_is_kept_and_is_still_not_rendered(
    monkeypatch, settings
):
    """`detail` is NOT deleted. It reaches the BR-AUD-018 attempt row and the
    log, where support reads it; `api/refusalText.ts` drops it before i18next
    ever sees it. Both halves are asserted here because keeping one without the
    other is how DEF-322 happened."""
    refusal = _oversized(monkeypatch, settings, size=41_000, ceiling=25_000)
    envelope = billing_api._as_catalog_refusal(refusal, "BR-BIL-001")

    assert "41,000 accounts" in envelope.params["detail"]
    assert "one billing cycle at a time" in envelope.params["detail"]


def test_def2720_tc3__every_other_run_refusal_still_gets_the_generic_key(
    monkeypatch, settings
):
    """The narrowing must not become a per-refusal key soup.

    `_as_catalog_refusal`'s uniformity is deliberate — one code and one sentence
    for every refusal whose whole content is *this cannot be done as asked* —
    and a refusal that names no key of its own is still exactly that.
    """
    envelope = billing_api._as_catalog_refusal(
        BillingRuleError("account AC-1 has no plan"), "BR-BIL-001"
    )

    assert envelope.message_key == "billing.run.refused"
    assert "count" not in envelope.params
    assert envelope.br_ref == "BR-BIL-001"
