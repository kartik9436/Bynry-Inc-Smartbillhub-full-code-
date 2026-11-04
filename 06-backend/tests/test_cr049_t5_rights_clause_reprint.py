# ── Trace ──────────────────────────────────────────────
# Change:   CR-049 task 5 — DEF-2504. Editing a rights clause must not change
#           what an already-served disconnection notice says.
# Rules:    BR-NOT-027 (a sent legal document is frozen AS THE DOCUMENT — PO
#           2026-08-30) · BR-NOT-015 (the five rights clauses are a per-tenant,
#           System-Admin-editable, audited override) · BR-NOT-014 (three
#           disconnect tiers) · BR-BIL-026 / BR-NOT-025 (the pin — PROVENANCE,
#           still required) · CLAUDE.md rule 1 · hard-won law 7 (prove a guard
#           RED first)
# ───────────────────────────────────────────────────────
"""The sharpest case in CR-049, and the one that should be proved first.

**THE DEFECT, IN ONE SENTENCE (DEF-2504).** The five regulatory clauses a
disconnection notice carries — dispute rights, medical hold, weather
suppression, the weekend/holiday rule and the commission complaint line — live
in `notification_settings.disconnect_rights_clauses`, a per-tenant map a System
Admin edits, and `rights_footer.expand` merges them into the letter **at render
time**. Because no notice was stored as it was sent, reproducing one re-rendered
it with TODAY's clauses. So correcting a clause silently changed what a notice
served last year appears to have said — and the 48-hour certified notice is the
legal instrument in a disconnection, whose footer is the part with statutory
weight.

**WHAT MADE IT INVISIBLE:** every layer was correct on its own. The edit is
audited before-and-after. The clause map is the right home for the content. The
renderer is right to expand the token. `notice_history` records THAT a notice was
sent and the proof-of-service columns record HOW — and neither records WHAT WAS
SERVED. Three correct records and no copy of the letter.

⚠ **PROVED RED FIRST (hard-won law 7), against the behaviour that shipped before
`CR-049` task 2.** Reproducing it takes no edit to a shipped file: patching
`frozen_documents.freeze_for_dispatch` to answer *"exempt, may send"* IS the old
dispatcher — the row reaches `sent`, nothing is stored, and every reproduction is
a fresh render. Verbatim, on 2026-08-30:

    E   AssertionError: the letter that was served was never stored, so the only
    E   thing a reprint can produce is a fresh render
    E   assert 'document_not_stored' is None
    E    +  where 'document_not_stored' = Reproduction(message_id='01a0524a-…',
    E       provenance='re_rendered_from_data_not_the_original', …).unavailable_reason

    E   AssertionError: a row reached `sent` with no frozen artefact behind it
    E   assert False
    E    +  where False = Reproduction(…, provenance=
    E       're_rendered_from_data_not_the_original', …).is_original

The HAZARD — that a fresh render really does pick up an edited clause — is
asserted PERMANENTLY, in
`test_..._the_hazard_is_real__a_fresh_render_carries_todays_clause`, because the
re-render's behaviour has not changed and must not be allowed to look safe: what
changed is that nothing serves it in place of the letter any more.

WHERE THIS RUNS
-----------------
Everything here is app-level, so it runs on the default suite as well as on live
PostgreSQL. The database half of the store's guarantees (RLS, the write-once
trigger) is `test_cr049_t1_document_store.py`'s subject and is not re-proved.
"""

from __future__ import annotations

from datetime import date, datetime, timezone as dt_timezone

import pytest

from apps.notifications import (
    dispatcher,
    frozen_documents,
    models,
    notices,
    rendering,
    rights_footer,
)
from apps.tenancy import document_store

from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import make_premises, make_unit, tenant_ctx
from tests.test_cr049_t2_dispatch_freeze import provider_connected  # noqa: F401 — shared fixture

pytestmark = pytest.mark.django_db

#: Inside Brazos Bend's seeded 08:00–21:00 send window (10:00 America/Chicago).
#: Print is quiet-hours exempt anyway; the moment is named rather than read from
#: a clock because BR-TEN-043 requires it and G6 greps for it.
SERVED_AT = datetime(2026, 8, 30, 15, 0, tzinfo=dt_timezone.utc)

#: The correction a System Admin makes AFTER the notice has gone out. It is the
#: kind of edit a utility genuinely makes — a regulator changes a rule and the
#: clause is brought up to date — which is exactly why it must not travel
#: backwards onto letters already served.
CORRECTED_DISPUTE_CLAUSE = (
    "Call us within 10 days of the date on this notice if you believe this bill is "
    "wrong. We will not disconnect while a dispute is open."
)

#: A TOKEN-FREE sentence from the platform's default dispute-rights clause.
#: ⚠ Token-free deliberately: `footer_text()` returns the clause with
#: `{support_phone}` and `{account_no}` still in it, and the rendered letter has
#: them substituted (as named absences here, because a dispatch-time render holds
#: no merge context). Comparing the raw clause against the rendered letter would
#: fail for a reason that has nothing to do with this defect.
SERVED_DISPUTE_SENTENCE = (
    "If you believe the amount on this notice is wrong, contact us before the date "
    "shown above — not after it."
)


class StubPrintVendor:
    """The print vendor US-NOT-003 has not integrated, published for one test."""

    def __init__(self):
        self.calls = []

    def __call__(self, channel, messages):
        self.calls.append((channel, messages))
        return {
            m["id"]: {"provider_reference": f"prt-{m['id'][:8]}", "status": "sent"}
            for m in messages
        }


@pytest.fixture()
def print_vendor(monkeypatch, provider_connected):
    """The print vendor, stubbed — AND a tenant that HAS connected it.

    ⚠ `provider_connected` ADDED 2026-09-30. From 2026-09-04 (`d471e8680`,
    `CR-069` wave E) the route asks, separately from *is there an adapter?*,
    *has THIS tenant connected a provider?* A stubbed adapter alone answers only
    the first, so every notice this file serves rested `queued` on
    `provider_not_connected` and was never frozen — correct for a real utility
    with no connection (A15 addendum), and fatal to every case here that needs
    a kept document to reprint. The product did not move; the double did not
    keep up.
    """
    from apps.integrations import services as integrations_services

    vendor = StubPrintVendor()
    monkeypatch.setattr(integrations_services, "dispatch_outbound_batch", vendor, raising=False)
    return vendor


@pytest.fixture()
def docs_dir(tmp_path, settings):
    """A per-test document directory, so no case can read another's bytes."""
    settings.DOCUMENT_STORAGE_BACKEND = "filesystem"
    settings.DOCUMENT_STORAGE_ALLOW_FILESYSTEM = True
    settings.DOCUMENT_STORAGE_DIR = str(tmp_path / "documents")
    return tmp_path / "documents"


def _an_account(actor, tenant, account_no):
    from apps.customers import models as customer_models

    premises = make_premises(actor, address_line=f"{account_no} Ridge Rd")
    unit = make_unit(actor, premises["id"], label=account_no, services=["electric"])
    return customer_models.Account.objects.create(
        tenant=tenant,
        unit_id=unit["id"],
        status=customer_models.AccountStatus.objects.filter(tenant=tenant).first(),
        account_type=customer_models.AccountType.objects.first(),
        account_no=account_no,
    )


def _serve_a_48_hour_notice(actor, tenant, account_no="A-49001"):
    """Generate the 48-hour certified notice and actually DISPATCH it.

    Returns `(queue row, the clause wording that was in force)`. Nothing is
    faked: the tenant is provisioned through the real service, the notice
    resolves the seeded `disconnect_notice_48_hour` template, and the dispatcher
    runs its ordinary cycle.
    """
    account = _an_account(actor, tenant, account_no)
    notices.generate_disconnect_notice(
        account_id=account.pk,
        tier=notices.TIER_FINAL_48_HOUR,
        balance=__import__("decimal").Decimal("1842.100000"),
        cut_date=date(2026, 9, 3),
        reconnect_fee=__import__("decimal").Decimal("45.000000"),
        state_puc_ref="TX PUC Substantive Rule 25.29",
        on_date=date(2026, 8, 30),
        actor=actor,
    )
    row = models.OutboundMessage.objects.get(
        source_type="notice", source_id=account.pk, channel=models.CHANNEL_PRINT
    )
    # ⚠ THE ADDRESS IS STAMPED HERE BECAUSE NOTHING PUBLISHES A RECIPIENT READ.
    # `services.py` names the missing read (`RECIPIENT_READ`) and records the
    # absence as `recipient_not_resolvable` — *"a fact about the PLATFORM, not
    # about the customer"* — and the dispatcher never selects an unaddressed row
    # (OQ-208). Supplying the envelope is standing in for that unbuilt read and
    # for nothing else: everything downstream of it is the shipping path.
    models.OutboundMessage.objects.filter(pk=row.pk).update(
        recipient_address=f"{account_no} Ridge Rd, Katy TX 77494",
        recipient_snapshot={"account_no": account_no},
        unavailable_reason=None,
    )
    row.refresh_from_db()
    served_wording = rights_footer.footer_text()
    result = dispatcher.dispatch_cycle(
        now=SERVED_AT, channels=(models.CHANNEL_PRINT,), actor=actor, job="test"
    )
    row.refresh_from_db()
    return row, served_wording, result


# ══════════════════════════════════════════════════════════════════════════
# 1 · THE ACCEPTANCE CASE — DEF-2504
# ══════════════════════════════════════════════════════════════════════════
def test_cr049_t5__editing_a_rights_clause_cannot_change_a_served_notice(
    brazos, dana, print_vendor, docs_dir
):
    """**Serve a notice, edit a clause, reproduce the notice — the reproduction
    carries the ORIGINAL wording.**

    This is `DEF-2504` closed. Before `CR-049` task 2 there was nothing to
    reproduce FROM: `reproduce()` answered `document_not_stored`, and every
    reprint route in the product re-rendered from the pin plus the data, which
    picks up whatever the clause map says today.

    Note what is asserted and what is not. The letter's OTHER content — the
    balance, the cut date — is not compared, because a dispatch-time render
    carries named absences for facts the queue row does not hold
    (`rendering.render_for_dispatch`'s own docstring). The FOOTER is the part
    with statutory weight and the part a System Admin can move, and it is the
    part this case is about.
    """
    with tenant_ctx(brazos):
        row, served_wording, result = _serve_a_48_hour_notice(dana, brazos)

        # It really went out, through the real cycle and the real seam.
        assert row.status == models.STATUS_SENT, result.problems
        assert print_vendor.calls, "the print vendor was never handed the batch"
        assert SERVED_DISPUTE_SENTENCE in served_wording

        # THE EDIT. A System Admin corrects the dispute-rights clause the day
        # after the notice was served — audited, legitimate, and forward-looking.
        rights_footer.update_clauses(actor=dana, dispute_rights={"text": CORRECTED_DISPUTE_CLAUSE})
        assert CORRECTED_DISPUTE_CLAUSE in rights_footer.footer_text()

        # THE REPRODUCTION. It is the ORIGINAL, and it is served as such.
        reproduction = frozen_documents.reproduce(row)
        assert reproduction.is_original, reproduction.detail
        assert reproduction.unavailable_reason is None
        assert reproduction.provenance == frozen_documents.PROVENANCE_ORIGINAL

        served = document_store.fetch(reproduction.document.id).decode("utf-8")

    # THE WHOLE POINT, in two lines: the corrected wording is NOT in the letter
    # that was served, and the wording that WAS in force still is.
    assert CORRECTED_DISPUTE_CLAUSE not in served
    assert SERVED_DISPUTE_SENTENCE in served


def test_cr049_t5__the_hazard_is_real__a_fresh_render_carries_todays_clause(
    brazos, dana, print_vendor, docs_dir
):
    """The re-render still changes — which is why nothing may serve it as the letter.

    ⚠ **THIS CASE ASSERTS THE DEFECT, DELIBERATELY AND PERMANENTLY.**
    `CR-049` did not make `rights_footer.expand` stop reading the current clause
    map, and it must not: a notice generated TOMORROW has to carry tomorrow's
    wording. What changed is that a served notice now has a frozen original, so
    the re-render is never what a reprint hands over.

    Keeping this assertion is what stops a later lane concluding the re-render is
    safe and quietly wiring a reprint back onto it — the exact shape of the
    defect, one layer up (`BR-NOT-027`'s honest half).
    """
    with tenant_ctx(brazos):
        row, served_wording, _result = _serve_a_48_hour_notice(dana, brazos, "A-49002")
        rights_footer.update_clauses(actor=dana, dispute_rights={"text": CORRECTED_DISPUTE_CLAUSE})

        re_rendered = rendering.render_for_dispatch(row).body

        assert CORRECTED_DISPUTE_CLAUSE in re_rendered, (
            "a fresh render was expected to pick up the edited clause — if it no longer "
            "does, this test's premise has changed and DEF-2504 needs re-examining"
        )
        assert SERVED_DISPUTE_SENTENCE not in re_rendered


def test_cr049_t5__the_pin_is_still_there_and_answers_a_different_question(
    brazos, dana, print_vendor, docs_dir
):
    """BR-BIL-026 / BR-NOT-025 are UNCHANGED and both records are kept.

    ⚠ **A READER WHO COLLAPSES THESE TWO WILL DELETE ONE.** The frozen artefact
    answers *"what did the customer read?"*. The pin answers *"which authored
    version of the wording was in force when they read it?"* — which is why
    `BR-NOT-025` still forbids deleting a template version any sent document
    points at. A frozen letter with no pin cannot name the approved wording it
    came from; a pin with no letter cannot say what the letter said.
    """
    with tenant_ctx(brazos):
        row, _served, _result = _serve_a_48_hour_notice(dana, brazos, "A-49003")

        assert row.template_code == "disconnect_notice_48_hour"
        assert row.template_id is not None
        assert row.template_version is not None

        reproduction = frozen_documents.reproduce(row)
        assert reproduction.is_original
        assert reproduction.document.kind == "disconnect_notice"
        assert reproduction.document.channel == models.CHANNEL_PRINT


# ══════════════════════════════════════════════════════════════════════════
# 2 · THE FREEZE CATCHES THE DRIFT IN FLIGHT
# ══════════════════════════════════════════════════════════════════════════
def test_cr049_t5__a_clause_edited_between_two_dispatch_attempts_holds_the_row(
    brazos, dana, monkeypatch, docs_dir, provider_connected
):
    """A retry whose render no longer matches the frozen copy HOLDS. It does not
    pick one.

    The first attempt freezes the letter and then the vendor fails, so the row
    backs off. A System Admin edits a rights clause in between. On the retry the
    fresh render disagrees with the frozen artefact — and there is no safe
    silent answer: sending the fresh render breaks `BR-NOT-027`, and sending the
    frozen bytes hides a wording change from the person who made it. The row
    holds and says which of the two it is.
    """
    from apps.integrations import services as integrations_services

    class FailingVendor:
        def __init__(self):
            self.calls = 0

        def __call__(self, channel, messages):
            self.calls += 1
            return {
                m["id"]: {"status": "failed", "error": "vendor timeout", "retryable": True}
                for m in messages
            }

    vendor = FailingVendor()
    monkeypatch.setattr(integrations_services, "dispatch_outbound_batch", vendor, raising=False)

    with tenant_ctx(brazos):
        row, _served, _result = _serve_a_48_hour_notice(dana, brazos, "A-49004")
        row.refresh_from_db()
        assert row.status == models.STATUS_QUEUED  # the vendor refused it
        assert frozen_documents.reproduce(row).is_original  # but it WAS frozen

        rights_footer.update_clauses(actor=dana, dispute_rights={"text": CORRECTED_DISPUTE_CLAUSE})

        # The backoff has elapsed; the retry re-renders and finds the drift.
        models.OutboundMessage.objects.filter(pk=row.pk).update(next_attempt_at=SERVED_AT)
        retry = dispatcher.dispatch_cycle(
            now=SERVED_AT, channels=(models.CHANNEL_PRINT,), actor=dana, job="test"
        )

    codes = [problem["code"] for problem in retry.problems]
    assert frozen_documents.FREEZE_ARTEFACT_DIFFERS in codes, retry.problems
    assert vendor.calls == 1, "the drifted row must never reach the vendor a second time"
    row.refresh_from_db()
    assert row.status == models.STATUS_QUEUED


# ── Lifecycle ─────────────────────────────────────────────
# packet: CR-049 task 5 (sources: 12-governance/10-defect-log.csv DEF-2504 · 12-governance/11-change-requests.md CR-049 step 5c task 5 · 04-docs/05-modules/10-notifications/02-business-rules.md BR-NOT-027 + BR-NOT-015)
# generated: 2026-08-30 by the CR-049 tasks 2/5/7 lane
# checklist: A✔ B✔ C✔ D=n/a E=n/a F✔ G✔ H=deferred(PO 2026-08-09)
# gates: RED PROVED FIRST — with the freeze call removed from dispatcher._dispatch_channel the acceptance case failed on `assert 'document_not_stored' is None`; the hazard case passed in both worlds, which is the point of keeping it.
# exceptions: (1) THE HAZARD CASE ASSERTS THE DEFECT ON PURPOSE — a fresh render still picks up an edited clause and always will; what changed is that nothing serves it as the letter. (2) The letter's non-footer content is not compared: a dispatch-time render carries named absences for facts the queue row does not hold.
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
