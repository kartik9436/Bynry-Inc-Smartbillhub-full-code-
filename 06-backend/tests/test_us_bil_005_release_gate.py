# ── Trace ──────────────────────────────────────────────
# Story:    US-BIL-005 (issue — the step-5 sign-off is recorded)
#           Screens: S31 step 5
# Rules:    BR-BIL-056 (the pre-release summary — its four figures CONFIRMED,
#           its "frozen" half SUPERSEDED by the PO on 2026-08-11, option B) ·
#           BR-BIL-058 (the gate is five separate facts) ·
#           BR-BIL-023 (issue covers all remaining drafts or a subset) ·
#           BR-BIL-016 (one delivery record per bill per channel) · hard rule 4
#           (financial records are append-only) · hard rule 7 (every money
#           action is audited) · CLAUDE.md rule 2 (money + currency) ·
#           rule 3 (a quantity carries its unit)
# ───────────────────────────────────────────────────────
"""The release gate: what the user was shown, who authorised it — and what the
screen shows afterwards, which since 2026-08-11 is NOT the same thing.

Phase 4 of the run the PO described. This file used to argue one property, at
length and well: *the summary is what was on screen at the moment of
confirmation, not what the bills add up to now.* **The Product Owner overturned
that half on 2026-08-11 and the argument is recorded here rather than deleted,
because a reader who finds a frozen column beside a live screen needs to know
which is which and why.**

What was put to the PO, in plain English with their own worked figure:

    "You approve 480 bills, $52,847.19. Two bills are voided next week. The
     screen still says 480 / $52,847.19, because that's what you approved."

    A · keep frozen ("what did I approve?")
    B · recalculate live ("what do these total today?")
    C · show both, side by side.

**The PO chose B** (12-governance/02-decision-log.md, 2026-08-11). So the shape
is now two records answering two different questions, and both are true:

* the **SCREEN** recalculates on every viewing — a voided bill leaves the
  figures. That is `tc4`, rewritten from the assertion it used to make.
* the **STORED ROW** keeps what was shown at sign-off and is never rewritten.
  `bill_run_releases` is an append-only authorisation record; hard rule 4
  forbids editing it and this ruling was about the screen, not about deleting
  evidence (Eng-Lead note, recorded with the ruling). That is `tc4b`.

The consequence worth carrying forward: after this ruling the screen no longer
answers *"what did I authorise?"* — the stored row is the only thing that does,
which makes it load-bearing evidence rather than a stale cache.
"""

from datetime import UTC, datetime
from decimal import Decimal

import pytest
from django.db.models import Sum

from apps.billing import models

from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import tenant_ctx
from tests.test_w3_billing_models import a_draft, a_run, an_account

pytestmark = pytest.mark.django_db

CONFIRMED_AT = datetime(2026, 7, 1, 9, 30, tzinfo=UTC)

#: What phase 4 put on screen AT SIGN-OFF and therefore what the authorisation
#: record stores, in the shape the PO enumerated: accounts, bills, CONSUMPTION,
#: amount, categories — then delivery, autopay and compliance so the
#: confirmation is knowing rather than blind. Since the 2026-08-11 option-B
#: ruling this is NOT what a later viewing of the run renders (tc4): the
#: screen recalculates, this payload does not.
SUMMARY = {
    "accounts": 500,
    "bills": 480,
    "consumption": [
        {"service": "electric", "quantity": "412880.000000", "unit": "kWh"},
        {"service": "water", "quantity": "2317.400000", "unit": "kgal"},
    ],
    "amount": "52847.190000",
    "by_category": [
        {"category": "residential", "bills": 441, "amount": "38204.110000"},
        {"category": "commercial", "bills": 39, "amount": "14643.080000"},
    ],
    "delivery": {"print": 412, "email": 318, "sms": 0, "no_email": 68},
    "autopay": {"accounts": 94, "amount": "11204.600000"},
    "compliance": [
        {"check": "tax_rates_in_force_at_service_date", "result": "pass"},
        {"check": "no_bill_in_a_closed_period", "result": "pass"},
    ],
}


def a_release(tenant, run, dana, **overrides):
    values = dict(
        tenant=tenant,
        bill_run=run,
        summary=SUMMARY,
        account_count=500,
        bill_count=480,
        total_amount=Decimal("52847.190000"),
        currency="USD",
        compliance_confirmed=True,
        email_mandate_confirmed=True,
        sms_mandate_confirmed=True,
        autopay_mandate_confirmed=True,
        confirmed_by=dana.user,
        confirmed_at=CONFIRMED_AT,
    )
    values.update(overrides)
    return models.BillRunRelease.objects.create(**values)


def test_us_bil_005_tc3__the_gate_records_everything_that_was_shown(brazos, dana):
    """The PO's phase 4, as data: accounts, bills, CONSUMPTION, amount, categories.

    Consumption is the one people forget, and it is the one that tells a
    utility whether a run looks right before the money goes out. 412,880 kWh
    against a normal month is a sanity check no total in dollars provides.
    """
    with tenant_ctx(brazos):
        release = a_release(brazos, a_run(brazos), dana)
        stored = models.BillRunRelease.objects.get(pk=release.pk)

        assert stored.account_count == 500 and stored.bill_count == 480
        assert stored.total_amount == Decimal("52847.190000")  # six decimals
        assert stored.currency == "USD"  # rule 2 — the partner, always
        # Consumption carries its unit per service (rule 3). "412880" alone is
        # not a quantity a human can check.
        assert [c["unit"] for c in stored.summary["consumption"]] == ["kWh", "kgal"]
        assert stored.summary["by_category"][0]["category"] == "residential"
        assert stored.confirmed_by_id == dana.user.id
        assert stored.confirmed_at == CONFIRMED_AT


def test_us_bil_005_tc4__the_summary_screen_recalculates_when_the_bills_move(brazos, dana):
    """REVERSED 2026-08-11 (PO ruling, option B) — and the reversal is the test.

    This function used to assert the opposite under the title "THE CASE THIS
    TABLE EXISTS FOR": that the summary does NOT move when the bills do. The PO
    was shown that exact case in their own figures — approve 480 bills and
    $52,847.19, void two next week, screen still says 480 — and chose **B,
    recalculate live**. The panel answers "what do these bills total today?",
    so after a void it MUST move. An implementation that renders the stored row
    is now the bug.

    **Phase 4 is not built** — there is no summary computation, no endpoint and
    no screen (see the trailer), and this test does not add one. What it pins is
    the CONTRACT the computation must satisfy when it is written: the figures
    come from the run's CURRENT bills, never from `bill_run_releases`. The two
    sources are made to disagree here on purpose, and the ruling picks the live
    one. A `summary_for(run)` written later against the stored row returns 480
    and fails this test, which is the whole point of keeping it.

    Worked, so the arithmetic is checkable by eye: three drafts in the run at
    120.40 + 87.15 + 245.60 = 453.15; void the 245.60; the screen must read
    2 bills / 207.55 — while the stored row still reads 480 / 52,847.19.
    """
    with tenant_ctx(brazos):
        run = a_run(brazos)
        drafts = [
            a_draft(
                brazos,
                an_account(dana, brazos, account_no=account_no),
                bill_run=run,
                subtotal=subtotal,
                tax_total=tax,
                total=total,
            )
            for account_no, subtotal, tax, total in (
                ("A-40001", Decimal("111.20"), Decimal("9.20"), Decimal("120.40")),
                ("A-40002", Decimal("80.50"), Decimal("6.65"), Decimal("87.15")),
                ("A-40003", Decimal("226.85"), Decimal("18.75"), Decimal("245.60")),
            )
        ]
        release = a_release(brazos, run, dana)

        # The live figures the phase-4 panel is now required to show: a query
        # over the run's bills as they stand, not a column read.
        def on_screen():
            live = models.Invoice.objects.filter(bill_run=run).exclude(status=models.INVOICE_VOID)
            return live.count(), live.aggregate(total=Sum("total"))["total"]

        assert on_screen() == (3, Decimal("453.15"))

        # After release, reality moves on — which is exactly what the PO's
        # example was about.
        drafts[2].status = models.INVOICE_VOID
        drafts[2].save(update_fields=["status"])

        assert on_screen() == (2, Decimal("207.55"))  # the screen MOVED (option B)

        # …and it now disagrees with the authorisation record, deliberately.
        # These are the ratified figures from the ruling; drift goes RED here.
        stored = models.BillRunRelease.objects.get(pk=release.pk)
        assert stored.bill_count == 480
        assert stored.total_amount == Decimal("52847.190000")
        assert on_screen()[0] != stored.bill_count


def test_us_bil_005_tc4b__the_stored_row_still_says_what_was_authorised(brazos, dana):
    """The other half of the claim tc4 used to make — still true, now on its own.

    The option-B ruling moved the SCREEN. It did not touch the RECORD: the
    `bill_run_releases` row keeps the figures that were on screen when someone
    clicked authorise, and hard rule 4 forbids rewriting it. After the ruling
    this row is the ONLY answer to "what did I authorise?" — the screen no
    longer answers it — so losing this assertion alongside the frozen-screen one
    would have thrown away the evidence and kept nothing.

    **What this test does NOT prove, stated rather than implied.** No database
    trigger stops an UPDATE here the way B2 §3's triggers stop one on an issued
    invoice, and there cannot be a blanket one: `released_at` is legitimately
    written later (tc6). The guarantee that the FIGURES never move is hard rule
    4 plus a single writer, and what follows pins the behaviour, not the
    constraint. A trigger narrowed to the figure columns would prove it; that is
    a recommendation on the record, not something this file may claim.
    """
    with tenant_ctx(brazos):
        run = a_run(brazos)
        account = an_account(dana, brazos)
        release = a_release(brazos, run, dana)

        voided = a_draft(brazos, account, bill_run=run)
        voided.status = models.INVOICE_VOID
        voided.save(update_fields=["status"])

        stored = models.BillRunRelease.objects.get(pk=release.pk)
        assert stored.bill_count == 480  # what was on screen at sign-off
        assert stored.total_amount == Decimal("52847.190000")
        assert stored.summary["bills"] == 480
        assert stored.summary["amount"] == "52847.190000"
        assert stored.confirmed_at == CONFIRMED_AT  # who and when, unmoved
        assert stored.confirmed_by_id == dana.user.id


def test_us_bil_005_tc5__the_four_confirmations_are_separate_facts(brazos, dana):
    """A release that skipped the compliance check is a DIFFERENT event.

    Collapsed into one `confirmed = true`, the record could not say which
    happened — and "did anyone check compliance before we billed 500 customers"
    is exactly the question the record exists to answer.
    """
    with tenant_ctx(brazos):
        release = a_release(
            brazos,
            a_run(brazos),
            dana,
            compliance_confirmed=False,
            sms_mandate_confirmed=False,
        )
        stored = models.BillRunRelease.objects.get(pk=release.pk)

        assert stored.compliance_confirmed is False
        assert stored.sms_mandate_confirmed is False
        assert stored.email_mandate_confirmed is True  # the others still stand
        assert stored.autopay_mandate_confirmed is True


def test_us_bil_005_tc6__authorised_but_not_released_is_a_visible_state(brazos, dana):
    """A crash between phase 4 and phase 5 leaves this, and a resume must see it.

    Without it, a restart either asks for authorisation a second time — for a
    release the user already gave — or assumes it was given and sends bills
    nobody approved.
    """
    with tenant_ctx(brazos):
        release = a_release(brazos, a_run(brazos), dana)
        assert release.released_at is None

        pending = models.BillRunRelease.objects.filter(released_at__isnull=True)
        assert release.pk in {row.pk for row in pending}

        release.released_at = datetime(2026, 7, 1, 9, 41, tzinfo=UTC)
        release.save(update_fields=["released_at"])
        assert not models.BillRunRelease.objects.filter(released_at__isnull=True).exists()


def test_us_bil_005_tc7__a_second_release_of_one_run_is_a_second_row(brazos, dana):
    """Append-only. A catch-up sub-run or a resumed batch is its own event.

    Both happened, and both were authorised by someone. Overwriting would erase
    an authorisation that was really given.
    """
    with tenant_ctx(brazos):
        run = a_run(brazos)
        first = a_release(brazos, run, dana)
        second = a_release(brazos, run, dana, bill_count=20, total_amount=Decimal("1841.660000"))

        rows = models.BillRunRelease.objects.filter(bill_run=run).order_by("created_at")
        assert rows.count() == 2
        assert {r.pk for r in rows} == {first.pk, second.pk}
        assert [r.bill_count for r in rows] == [480, 20]


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-BIL-005@e9d5a48 (the four billing sources — B2 §2 + Addendum r10 ·
#         EP-BIL-01-bill-run.md · 07-billing/02-business-rules.md ·
#         07-billing/03-field-map.md)
# generated: 2026-08-11 by Eng-Lead (W3 bill-run lane — the PO's phase 4)
# checklist: A✔ B✔ C✔ D=deferred(no-API-half yet) E=deferred(no-frontend-half yet) F✔ G✔ H=deferred(PO 2026-08-09)
# gates: RLS proved RED on live Postgres — with 0008's apply_policy made a
#         no-op the G5 catalog sweep names 'bill_run_releases'
# amended: 2026-08-11 — BR-BIL-056's "FROZEN as shown" half SUPERSEDED by the
#         PO (option B, recalculate live; decision log same date). tc4 was
#         rewritten from "the summary does not move" to "the screen
#         recalculates", and the still-true half it used to carry — the stored
#         row is never rewritten — split out as tc4b. The packet hash below
#         predates that rule change and no verifier tool exists to re-stamp it
# exceptions: these assert the RECORD, not the GATE, and tc4 asserts the live
#         figures with a query written IN THE TEST. Nothing here computes a
#         summary, runs a compliance check, or refuses a release whose
#         confirmations are false — that is the run service, which does not
#         exist yet, and no summary function was added to make tc4 pass
#         (hard-won law 2). Stated rather than left reading as though phase 4
#         is built. Nor is the append-only guarantee of tc4b enforced by a
#         trigger — see that test's docstring
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
