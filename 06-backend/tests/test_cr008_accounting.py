# ── Trace ──────────────────────────────────────────────
# Change:   CR-008 · SET-11 Settings → Accounting (PO RULINGS 2026-08-17)
#           Screens: SET-11 (chart · GL mapping · finance controls)
# Rules:    BR-PAY-019 (bank auto-match — CR-008 #7 adds its AMOUNT window) ·
#           BR-PAY-020 (a manual write-off needs an approver — CR-008 ruling 2
#           makes "above what amount" the tenant's) · BR-LED-015 (every chart
#           change audits) · BR-BIL-069 / B5 line 74 (the 2200 tax series is
#           allocated, never typed) · BR-TEN-013 + B1 (the ledger validates a
#           ledger row) · US-TEN-010 §5 (reason_codes.default_gl_account_id) ·
#           BR-TEN-043 (no clock in a service) · CLAUDE.md rule 1 · rule 2 ·
#           rule 7
# ───────────────────────────────────────────────────────
"""CR-008's four money-bearing promises, each asserted at its own figure.

WHY EVERY CASE HERE CARRIES A NUMBER. Three of CR-008's rulings change what
happens to money, and all three were ruled SAFE-BY-DEFAULT — which is a claim
that has to be provable rather than commented:

  * the bank-match amount tolerance seeds **0**, and `abs(a − b) <= 0` must be
    exactly the penny-exact `==` the matcher used before it existed;
  * the manual write-off approval threshold seeds **0.00**, and at 0 EVERY
    write-off of every size must still need its System-Admin approval;
  * an import must never rename an account a tenant already has.

A test that merely called each function would pass on all three even if the
defaults were wrong. So each one is driven at its default AND at a figure a
tenant might type, and the difference between the two is the assertion.
"""

import uuid
from datetime import datetime, timezone as dt_timezone
from decimal import Decimal
from types import SimpleNamespace

import pytest

from apps.ledger import chart, models, services
from apps.payments import settings_seam, writeoffs
from apps.payments.reconciliation import _amounts_tie
from apps.tenancy import selectors as tenancy_selectors
from apps.rating import services as rating_services
from apps.tenancy import services as tenancy_services
from core import errors

from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared tenant fixtures
from tests.test_us_ten_helpers import tenant_ctx

pytestmark = pytest.mark.django_db

NOW = datetime(2026, 8, 17, 12, 0, tzinfo=dt_timezone.utc)


def actor(role="system_admin"):
    return SimpleNamespace(id=uuid.uuid4(), pk=uuid.uuid4(), role=role, is_authenticated=True)


# ═══════════════════════════════════════════════════════════════════════════
# RULING 7 — the bank-match AMOUNT window, and why 0 is the whole safety case
# ═══════════════════════════════════════════════════════════════════════════
def test_cr008_the_seeded_amount_tolerance_is_zero_and_zero_means_penny_exact(brazos):
    """PO 2026-08-17: *"Okay. We can take it as threshold from user"*.

    The figure r10 draws is **$0.05**. Seeding it would auto-match — and then
    RECONCILE AND LOCK (BR-PAY-004) — a **$412.30** deposit batch against a
    **$412.27** bank line for every utility on the day this shipped. So the
    seed is 0, and this asserts both halves of that: the value, and what the
    value MEANS at the comparison site.
    """
    with tenant_ctx(brazos):
        values = tenancy_selectors.settings_family("finance-controls")
        assert values["bank_match_amount_tolerance"] == "0"
        assert settings_seam.match_amount_tolerance() == Decimal("0")

    zero = Decimal("0")
    # Penny-exact: the same comparison the matcher made before CR-008.
    assert _amounts_tie(Decimal("412.30"), Decimal("412.30"), zero) is True
    assert _amounts_tie(Decimal("412.30"), Decimal("412.27"), zero) is False
    # …and the three cents tie only once a human has typed a window that
    # covers them. Both directions, because a bank line can be either side.
    assert _amounts_tie(Decimal("412.30"), Decimal("412.27"), Decimal("0.05")) is True
    assert _amounts_tie(Decimal("412.27"), Decimal("412.30"), Decimal("0.05")) is True
    # And a window is a window: four cents out is still out at five cents.
    assert _amounts_tie(Decimal("412.30"), Decimal("412.24"), Decimal("0.05")) is False


def test_cr008_the_amount_tolerance_is_a_tenant_setting_the_matcher_actually_reads(brazos):
    """Hard-won law 2 — a setting nothing reads is not a setting.

    Saved through the tenant's own rule-page write, then read back through the
    seam the matcher calls. If either half is unwired this goes red.
    """
    with tenant_ctx(brazos):
        tenancy_services.save_settings_family(
            actor(), "finance-controls", {"bank_match_amount_tolerance": "0.05"}
        )
        assert settings_seam.match_amount_tolerance() == Decimal("0.05")


def test_cr008_a_tolerance_nobody_can_read_refuses_rather_than_defaulting(brazos):
    """Hard-won law 3, at the seam: an unreadable window is not "±0"."""
    with tenant_ctx(brazos):
        tenancy_services.save_settings_family(
            actor(), "finance-controls", {"bank_match_amount_tolerance": "0.02"}
        )
    with tenant_ctx(brazos):
        # A stored value that is not money at all — the shape a hand-edited
        # settings document can take.
        row = tenancy_selectors._settings_row()
        row.finance_controls["bank_match_amount_tolerance"] = "five cents"
        row.save(update_fields=["finance_controls"])
        with pytest.raises(Exception) as refusal:
            settings_seam.match_amount_tolerance()
        assert "not a money figure" in str(refusal.value)


def test_cr008_the_amount_tolerance_is_bounded(brazos):
    """A tolerance is for a rounding or a bank's cent. $50 is a payment."""
    with tenant_ctx(brazos):
        with pytest.raises(errors.ValidationError):
            tenancy_services.save_settings_family(
                actor(), "finance-controls", {"bank_match_amount_tolerance": "50"}
            )
        with pytest.raises(errors.ValidationError):
            tenancy_services.save_settings_family(
                actor(), "finance-controls", {"bank_match_amount_tolerance": "-1"}
            )


# ═══════════════════════════════════════════════════════════════════════════
# RULING 2 — the manual write-off approval threshold, seeded 0.00
# ═══════════════════════════════════════════════════════════════════════════
def test_cr008_at_the_seeded_zero_every_write_off_still_needs_an_approver(brazos):
    """**The assertion this whole ruling turns on.**

    Shipping r10's $5,000 would have meant every write-off under $5,000 stopped
    needing approval the moment CR-008 landed. At 0.00 nothing qualifies —
    `request_write_off` refuses an amount that is not > 0, so no amount can be
    at or below the threshold. Driven at $0.01 and at $4,999.99, because "every
    size" is the claim.
    """
    with tenant_ctx(brazos):
        assert (
            tenancy_selectors.settings_family("finance-controls")[
                "write_off_approval_threshold_amount"
            ]
            == "0"
        )
        assert settings_seam.write_off_approval_threshold() == Decimal("0")
        assert writeoffs.approval_is_required(Decimal("0.01")) is True
        assert writeoffs.approval_is_required(Decimal("4999.99")) is True
        assert writeoffs.approval_is_required(Decimal("250000")) is True


def test_cr008_a_tenant_who_types_a_threshold_gets_exactly_what_it_says(brazos):
    """$50.00 typed by a utility: $49.99 needs nobody, $50.01 needs an approver.

    The boundary is asserted on BOTH sides and ON it, because "above this
    amount" is the label and an off-by-one here is a write-off posted by
    somebody who was not allowed to post it.
    """
    with tenant_ctx(brazos):
        tenancy_services.save_settings_family(
            actor(), "finance-controls", {"write_off_approval_threshold_amount": "50.00"}
        )
        assert writeoffs.approval_is_required(Decimal("49.99")) is False
        assert writeoffs.approval_is_required(Decimal("50.00")) is False  # AT it, not above
        assert writeoffs.approval_is_required(Decimal("50.01")) is True


def test_cr008_the_two_write_off_figures_are_different_settings(brazos):
    """The collision ruling 2 exists to prevent, asserted rather than commented.

    `write_off_threshold_amount` is BR-BIL-013's automatic small-balance
    clear-out at a FINAL bill: $5, capped $50. The approval threshold is a
    different key, a different rule and a different default, and moving one
    must not move the other.
    """
    with tenant_ctx(brazos):
        values = tenancy_selectors.settings_family("finance-controls")
        assert values["write_off_threshold_amount"] == "5"
        assert values["write_off_approval_threshold_amount"] == "0"
        tenancy_services.save_settings_family(
            actor(), "finance-controls", {"write_off_approval_threshold_amount": "100"}
        )
        after = tenancy_selectors.settings_family("finance-controls")
        assert after["write_off_threshold_amount"] == "5", "the AUTOMATIC figure moved"
        assert after["write_off_approval_threshold_amount"] == "100"
        # And the automatic one keeps its own $50 ceiling (BR-BIL-013), which
        # the approval threshold does not share.
        with pytest.raises(errors.ValidationError):
            tenancy_services.save_settings_family(
                actor(), "finance-controls", {"write_off_threshold_amount": "5000"}
            )


# ═══════════════════════════════════════════════════════════════════════════
# RULING 9 — reason_codes.default_gl_account_id, the fifth mapping section
# ═══════════════════════════════════════════════════════════════════════════
def test_cr008_an_adjustment_reason_carries_its_own_gl_account(brazos):
    """*"9 make it separate"* — a billing-error credit and a goodwill credit
    post to different accounts, which means the pointer is per REASON."""
    with tenant_ctx(brazos):
        services.seed_chart_of_accounts(actor())
        account = models.LedgerAccount.objects.filter(designation=chart.WRITE_OFF).first()
        assert account is not None
        created = tenancy_services.create_lookup_entry(
            actor(), "reason_codes", {"code": "GOODWILL-CR8", "name": "Goodwill"}
        )
        # Unmapped is the state a new reason starts in, and it is served.
        assert created["default_gl_account_id"] is None
        updated = tenancy_services.update_lookup_entry(
            actor(),
            "reason_codes",
            created["id"],
            {"default_gl_account_id": str(account.pk)},
        )
        assert updated["default_gl_account_id"] == str(account.pk)
        # …and CLEARING it is a real act the server accepts by name.
        cleared = tenancy_services.update_lookup_entry(
            actor(), "reason_codes", created["id"], {"default_gl_account_id": None}
        )
        assert cleared["default_gl_account_id"] is None


def test_cr008_the_reason_gl_account_is_validated_by_the_ledger(brazos):
    """B1 — the row is the ledger's, so the ledger says whether it is usable.

    An FK would prove the row EXISTS and never that it is THIS tenant's, which
    in a money path is the only question. A random uuid is refused, and so is
    a string that is not an account id at all.
    """
    with tenant_ctx(brazos):
        created = tenancy_services.create_lookup_entry(
            actor(), "reason_codes", {"code": "CR8-BAD", "name": "Bad pointer"}
        )
        with pytest.raises(errors.ValidationError):
            tenancy_services.update_lookup_entry(
                actor(),
                "reason_codes",
                created["id"],
                {"default_gl_account_id": str(uuid.uuid4())},
            )
        with pytest.raises(errors.ValidationError):
            tenancy_services.update_lookup_entry(
                actor(), "reason_codes", created["id"], {"default_gl_account_id": "4110"}
            )


# ═══════════════════════════════════════════════════════════════════════════
# RULING 3 — the file import, which is the WHOLE of how a chart arrives now
# ═══════════════════════════════════════════════════════════════════════════
def rows(*triples):
    return [{"code": c, "name": n, "type": t} for c, n, t in triples]


def test_cr008_a_validate_run_writes_nothing_and_reports_every_row(brazos):
    with tenant_ctx(brazos):
        services.seed_chart_of_accounts(actor())
        before = models.LedgerAccount.objects.count()
        report = services.import_accounts(
            actor(),
            rows=rows(
                ("9100", "Meter deposit clearing", "liability"),
                ("9100", "Typed twice", "liability"),
                ("9200", "", "asset"),
                ("9300", "Grant income", "sausage"),
            ),
            commit=False,
        )
        assert report["committed"] is False
        assert models.LedgerAccount.objects.count() == before, "a VALIDATE wrote rows"
        assert report["counts"] == {
            "new": 1,
            "existing": 0,
            "duplicate_in_file": 1,
            "invalid": 2,
        }
        # Every refusal names its row and its reason — a report saying "2 bad
        # rows" and not which is a report nobody can act on.
        assert [row["outcome"] for row in report["rows"]] == [
            "new",
            "duplicate_in_file",
            "invalid",
            "invalid",
        ]
        assert report["rows"][2]["reason"] == "name_required"
        assert report["rows"][3]["reason"] == "type_unknown"


def test_cr008_a_commit_refuses_a_file_with_any_bad_row(brazos):
    """All-or-nothing, and the refusal counts what is wrong out of what there is."""
    with tenant_ctx(brazos):
        services.seed_chart_of_accounts(actor())
        before = models.LedgerAccount.objects.count()
        with pytest.raises(errors.BizError) as refusal:
            services.import_accounts(
                actor(),
                rows=rows(("9100", "Fine", "liability"), ("9200", "No type", "")),
                commit=True,
            )
        assert refusal.value.message_key == "ledger.chart.import_has_bad_rows"
        assert models.LedgerAccount.objects.count() == before


def test_cr008_a_clean_commit_creates_the_new_rows_and_leaves_the_rest_alone(brazos):
    """The dedupe, in the direction that matters: an EXISTING code is skipped.

    `1200 Accounts receivable` carries the AR designation the posting service
    resolves every journal entry through. A file whose B-column reads *"Trade
    debtors"* must not rename it — the name after the import is the name before
    it, and this is the assertion that says so.
    """
    with tenant_ctx(brazos):
        services.seed_chart_of_accounts(actor())
        ar = models.LedgerAccount.objects.get(designation=chart.AR)
        original_name = ar.name
        report = services.import_accounts(
            actor(),
            rows=rows(
                (ar.code, "Trade debtors", "asset"),
                ("9100", "Meter deposit clearing", "liability"),
            ),
            commit=True,
        )
        assert report["committed"] is True
        assert report["counts"]["existing"] == 1
        assert report["created"] == ["9100"]
        ar.refresh_from_db()
        assert ar.name == original_name, "the import renamed an account it should have skipped"
        assert ar.designation == chart.AR
        assert models.LedgerAccount.objects.filter(code="9100").exists()


def test_cr008_the_import_refuses_a_hand_typed_tax_series_code(brazos):
    """B5 line 74: *"tenant authorities mint their own"*, and OQ-147 made the
    2200-nn code GENERATED. A spreadsheet row would take a number the allocator
    is about to hand out."""
    with tenant_ctx(brazos):
        services.seed_chart_of_accounts(actor())
        report = services.import_accounts(
            actor(), rows=rows(("2200-07", "Tax payable — PUC", "liability")), commit=False
        )
        assert report["rows"][0]["outcome"] == "invalid"
        assert report["rows"][0]["reason"] == "tax_series_reserved"


def test_cr008_the_import_is_system_admin_only(brazos):
    """CR-008 #4 — the whole Accounting screen is System Admin. This is TIGHTER
    than `create_account`, which a Billing Clerk may call: one typed account is
    an act somebody reviews, 180 from a spreadsheet is a chart of accounts."""
    with tenant_ctx(brazos):
        with pytest.raises(errors.AuthError):
            services.import_accounts(
                actor(role="billing_clerk"),
                rows=rows(("9400", "Something", "asset")),
                commit=False,
            )
        with pytest.raises(errors.AuthError):
            services.import_accounts(
                actor(role="executive"), rows=rows(("9400", "Something", "asset")), commit=False
            )


def test_cr008_a_committed_import_writes_its_own_audit_row(brazos, audit_rows):
    """CLAUDE.md rule 7. TWO kinds of row, deliberately: one per account
    (`create_account`'s own) and one for the RUN, because a utility asking
    *"who loaded these 180 accounts"* is asking about the act, not about
    account 9500. Read off the SINK, which is how every audit assertion in this
    suite reads."""
    with tenant_ctx(brazos):
        services.seed_chart_of_accounts(actor())
        who = actor()
        services.import_accounts(who, rows=rows(("9500", "Grant income", "revenue")), commit=True)

    runs = [row for row in audit_rows if row["action"] == services.AUDIT_CHART_IMPORTED]
    assert len(runs) == 1, "the import RUN wrote no audit row"
    assert runs[0]["after"]["created"] == ["9500"]
    assert runs[0]["after"]["source"] == "csv_import"
    assert runs[0]["actor_user_id"] == who.id
    per_account = [
        row
        for row in audit_rows
        if row["action"] == services.AUDIT_ACCOUNT_CREATED and row["after"]["code"] == "9500"
    ]
    assert len(per_account) == 1, "the account created by the import wrote no row of its own"


# ═══════════════════════════════════════════════════════════════════════════
# RULING 1 — the accrual/cash column stays; the CONTROL is gone
# ═══════════════════════════════════════════════════════════════════════════
def test_cr008_nothing_in_the_engine_reads_accounting_method(brazos):
    """*"take it off"* — the PO's ruling, and the measurement behind it.

    The column stays (dropping it is a migration with no caller). What must
    stay true is the reason the control went: **no engine reads it**. This
    sweeps the two modules that would care.
    """
    import pathlib

    root = pathlib.Path(__file__).resolve().parent.parent
    readers = [
        path
        for folder in ("apps/billing", "apps/ledger")
        for path in (root / folder).rglob("*.py")
        if "accounting_method" in path.read_text()
    ]
    assert readers == [], f"accounting_method is read by {[str(p) for p in readers]}"


# ═══════════════════════════════════════════════════════════════════════════
# SECOND-SET RULING 1 — the tender's own cash/clearing account
#
# The PO was shown the gap in plain English and ruled *"Im good with all"*:
# *"a utility taking card, cheque, cash and IVR has nowhere to say that card
# lands in a merchant clearing account and cheques in the bank."*
# ═══════════════════════════════════════════════════════════════════════════
def test_cr008_a_tender_can_name_the_account_its_money_lands_in(brazos):
    with tenant_ctx(brazos):
        services.seed_chart_of_accounts(actor())
        account = models.LedgerAccount.objects.filter(designation=chart.CASH).first()
        assert account is not None
        created = tenancy_services.create_lookup_entry(
            actor(), "payment_methods", {"code": "CR8-CARD", "name": "Card — Stripe"}
        )
        # UNMAPPED is where every tender starts, and it is TODAY'S BEHAVIOUR
        # for all of them: the receipt leg resolves undeposited funds anyway.
        assert created["clearing_gl_account_id"] is None
        updated = tenancy_services.update_lookup_entry(
            actor(),
            "payment_methods",
            created["id"],
            {"clearing_gl_account_id": str(account.pk)},
        )
        assert updated["clearing_gl_account_id"] == str(account.pk)
        # …and CLEARING it is a real act the server accepts by name.
        cleared = tenancy_services.update_lookup_entry(
            actor(), "payment_methods", created["id"], {"clearing_gl_account_id": None}
        )
        assert cleared["clearing_gl_account_id"] is None


def test_cr008_the_tender_account_is_validated_by_the_ledger(brazos):
    """Same refusal the adjustment reason gets, and deliberately the SAME CODE
    PATH — `GlPointerLookupMixin`. An FK would prove the row exists and never
    that it is THIS tenant's, which in a money path is the whole question."""
    with tenant_ctx(brazos):
        created = tenancy_services.create_lookup_entry(
            actor(), "payment_methods", {"code": "CR8-BADT", "name": "Bad tender"}
        )
        with pytest.raises(errors.ValidationError):
            tenancy_services.update_lookup_entry(
                actor(),
                "payment_methods",
                created["id"],
                {"clearing_gl_account_id": str(uuid.uuid4())},
            )
        with pytest.raises(errors.ValidationError):
            tenancy_services.update_lookup_entry(
                actor(),
                "payment_methods",
                created["id"],
                {"clearing_gl_account_id": "1010"},
            )


def test_cr008_the_two_gl_lists_share_ONE_validation(brazos):
    """The mixin is the point, not decoration: `reason_codes` and
    `payment_methods` must answer the same question the same way, or the day
    somebody tightens one a utility gets two different meanings of "a usable
    account" on one screen."""
    assert (
        tenancy_services.PaymentMethodLookupHandler._validate
        is tenancy_services.ReasonCodeLookupHandler._validate
    ), "one implementation, not two copies"
    assert tenancy_services.PaymentMethodLookupHandler.GL_FIELD == "clearing_gl_account_id"
    assert tenancy_services.ReasonCodeLookupHandler.GL_FIELD == "default_gl_account_id"
    # ⚠ AND THE NAMES MUST DIFFER. One is the CASH side, the other REVENUE;
    # a shared name would let a tender be mapped onto an income account with
    # nothing objecting.
    assert (
        tenancy_services.PaymentMethodLookupHandler.GL_FIELD
        != tenancy_services.ReasonCodeLookupHandler.GL_FIELD
    )


def test_cr008_the_tender_account_wiring_moved_BOTH_legs_together(brazos):
    """⚠ THE HONESTY TEST, INVERTED ON SCHEDULE — read its history before
    "fixing" it.

    Until 2026-08-18 this test asserted ZERO readers of
    `clearing_gl_account_id` under `apps/payments`, because the screen told a
    utility nothing posts differently yet and a receipt leg moving without the
    reconciliation leg puts the trial balance out by the amount of every card
    payment. Its own docstring said: *"THE DAY SOMEBODY WIRES IT, THIS TEST
    GOES RED — which is the arrival signal OQ-264 needs."*

    It went RED on 2026-08-18: the PO ruled the wiring IN (*"10 - A inside
    CR-008 now"*, 2026-08-17) and the CR-008 B-10 slice moved BOTH legs in one
    change. So the assertion inverts, still guarding the same sentence from
    the other side: the receipt reader (`ledger_seam.tender_clearing_account_
    id`) and the reconciliation split (`reconciliation._member_credit_split`
    over the ledger's `entry_debit_totals`) must BOTH exist — one without the
    other is the half-change the old test existed to block. The behaviour
    itself is proved in `tests/test_cr008_tender_gl_posting.py`, receipts to
    trial balance.
    """
    from apps.payments import ledger_seam as seam
    from apps.payments import reconciliation as rec

    # The RECEIPT half reads the column…
    assert callable(getattr(seam, "tender_clearing_account_id", None))
    assert "clearing_account_id" in seam.post_payment_cleared.__kwdefaults__
    # …and the RECONCILIATION half moves with it, in the same tree state.
    assert callable(getattr(rec, "_member_credit_split", None))
    assert "undeposited_credits" in seam.post_batch_reconciled.__kwdefaults__


# ═══════════════════════════════════════════════════════════════════════════
# SECOND-SET RULING 3 — the account is refused WHEN IT IS PICKED
#
# PO: *"a mapping can look correct on screen for weeks and fail on the day a
# bill runs, which is when a utility can least afford it."*
# ═══════════════════════════════════════════════════════════════════════════
def _live_income_account():
    # 4200 in the seeded chart. Any live account of the tenant's own chart
    # would do — the guard asks about OWNERSHIP and LIVENESS, never type.
    return models.LedgerAccount.objects.filter(code="4200").first()


def test_cr008_a_charge_cannot_be_pointed_at_an_account_that_is_not_yours(brazos):
    """Until 2026-08-17 this was `_uuid_value` and nothing else, so ANY
    well-formed uuid was stored — measured, not assumed: with the guard
    monkeypatched back to `_uuid_value` the stranger's id is accepted and this
    assertion is the only thing that catches it."""
    with tenant_ctx(brazos):
        services.seed_chart_of_accounts(actor())
        with pytest.raises(errors.ValidationError) as refused:
            rating_services.create_charge(
                actor(),
                {
                    "code": "CR8-STRANGER",
                    "name": "Points at nothing",
                    "charge_type": "one_time",
                    "amount_rule": "flat",
                    "amount": "25.00",
                    "gl_account_id": str(uuid.uuid4()),
                 "effective_from": "2000-01-01"},
            )
        # Refused BY NAME — a utility is told which field, not handed a 500.
        assert refused.value.field_errors[0]["field"] == "gl_account_id"

        # …and a real account of this tenant's own chart is accepted, so the
        # guard refuses the wrong thing rather than everything.
        account = _live_income_account()
        assert account is not None
        row = rating_services.create_charge(
            actor(),
            {
                "code": "CR8-GOOD",
                "name": "Points at 4200",
                "charge_type": "one_time",
                "amount_rule": "flat",
                "amount": "25.00",
                "gl_account_id": str(account.pk),
             "effective_from": "2000-01-01"},
        )
        assert row["gl_account_id"] == str(account.pk)


def test_cr008_a_deactivated_account_is_refused_too(brazos):
    """IS-1. The account EXISTS and is this tenant's, and it is still wrong —
    which is exactly the case a foreign key could never catch, and the reason
    the LEDGER answers rather than a constraint."""
    with tenant_ctx(brazos):
        services.seed_chart_of_accounts(actor())
        account = _live_income_account()
        assert account is not None
        charge = rating_services.create_charge(
            actor(),
            {
                "code": "CR8-DEACT",
                "name": "Mapped, then retired",
                "charge_type": "one_time",
                "amount_rule": "flat",
                "amount": "5.00",
                "gl_account_id": str(account.pk),
             "effective_from": "2000-01-01"},
        )
        services.set_account_active(actor(), account_id=account.pk, active=False, at=NOW)
        with pytest.raises(errors.ValidationError):
            rating_services.update_charge(actor(), charge["id"], {"gl_account_id": str(account.pk), "effective_from": "2000-01-01"})


def test_cr008_clearing_a_charge_account_is_still_allowed(brazos):
    """Validation at the pick must not make RETIRING a mapping impossible.
    An unmapped charge is a real state — it shows in the GAP banner and
    refuses at issue by name (BR-BIL-010) — so `null` is accepted."""
    with tenant_ctx(brazos):
        services.seed_chart_of_accounts(actor())
        account = _live_income_account()
        charge = rating_services.create_charge(
            actor(),
            {
                "code": "CR8-CLEAR",
                "name": "Clearable",
                "charge_type": "one_time",
                "amount_rule": "flat",
                "amount": "5.00",
                "gl_account_id": str(account.pk),
             "effective_from": "2000-01-01"},
        )
        cleared = rating_services.update_charge(actor(), charge["id"], {"gl_account_id": None, "effective_from": "2000-01-01"})
        assert cleared["gl_account_id"] is None


def test_cr008_a_plan_service_cannot_be_pointed_at_a_stranger_either(brazos):
    """The fifth pointer, and the second of the two that genuinely had no
    check. It is refused with its ROW PREFIX, because a plan carries many
    services and "which one" is the whole usefulness of the message."""
    with tenant_ctx(brazos):
        services.seed_chart_of_accounts(actor())
        with pytest.raises(errors.ValidationError) as refused:
            rating_services.create_plan(
                actor(),
                {
                    "name": "CR-008 stranger plan",
                    "code": "CR8-STRANGER-PLAN",
                    "services": [
                        {
                            "service": "electric",
                            "base_charge": "10.00",
                            "gl_account_id": str(uuid.uuid4()),
                        }
                    ],
                },
            )
        fields = [error["field"] for error in refused.value.field_errors]
        gl = [field for field in fields if field.endswith("gl_account_id")]
        assert gl, f"the plan saved or refused for another reason: {fields}"
        assert (
            gl[0] != "gl_account_id"
        ), f"expected a row-prefixed field so the utility knows WHICH service, got {gl[0]!r}"


# ── Lifecycle ─────────────────────────────────────────────
# packet: CR-008@12-governance/11-change-requests.md §CR-008 + its PO RULINGS 2026-08-17 (all nine, verbatim) · B5 line 74 ❄️ · BR-PAY-019 · BR-PAY-020 · BR-BIL-013 · US-TEN-010 §5
# generated: 2026-08-17 by story-coder (CR-008 SET-11 lane)
# checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-09 — 🔒 HUMAN-REVIEW-PENDING, row in 12-governance/09-human-review-ledger.md)
# gates: PROVED RED FIRST (law 7), by re-introducing the two mistakes these rulings were made to avoid and quoting what came back.
#        (1) SEEDING r10's FIGURES — `bank_match_amount_tolerance` "0" → "0.05" and `write_off_approval_threshold_amount` "0" → "5000" — turned three tests red:
#            `AssertionError: assert '0.05' == '0'` · `AssertionError: assert '5000' == '0'` (twice, one of them inside the two-figures-are-different case).
#        (2) MAKING THE IMPORT UPDATE AN EXISTING ACCOUNT instead of skipping it — the `existing` outcome replaced by `new` — turned the dedupe case red with
#            `core.errors.BizError: BIZ-STATE (ledger.chart.code_taken)`, which is the honest failure: with the skip removed the import tries to CREATE 1200 again and the chart's own uniqueness refuses it.
#        Green after restoring both: 16 passed. ruff✔ black✔
# amended:  2026-08-17 by story-coder (CR-008 SECOND-SET rulings 1 and 3 — the tender's cash/clearing account and validation at the pick).
#        PROVED RED FIRST AGAIN (law 7), and NOT by editing the tree, because six other lanes are reading it: each guard was disabled IN MEMORY with monkeypatch in a
#        throwaway file, run, and the file deleted.
#        (1) `_validated_gl_account` monkeypatched back to the pre-CR-008 line — plain `_uuid_value` — and `create_charge` with `gl_account_id` = a random uuid
#            RETURNED `{'gl_account_id': '<the stranger>'}` and stored it. That is the whole defect in one line: any well-formed uuid, another utility's chart included.
#            With the guard restored the same call raises `core.errors.ValidationError` with `field_errors[0]['field'] == 'gl_account_id'`.
#        (2) The tender column: before it existed `clearing_gl_account_id` was not a field at all and `HostedFlatLookupHandler` refused it by name as unknown.
#            The proof asserts the key is now PRESENT in the serialized row (`None`, which is the unmapped state every tender starts in).
#        (3) `test_cr008_setting_a_tender_account_changes_NO_posting` asserts an ABSENCE and is the arrival signal OQ-264 needs: it greps every .py under apps/payments
#            for `clearing_gl_account_id` and requires ZERO readers. It goes RED the day somebody wires the receipt leg — which must not happen without the
#            reconciliation leg in the same change, or every card payment puts the trial balance out.
#        Green: 24 passed (16 before this amendment). ruff✔ black✔
# amended:  2026-08-18 by the CR-008 ledger lane (B-10 landed — PO 2026-08-17, "10 - A inside CR-008 now").
#        The arrival signal FIRED exactly as designed: `test_cr008_setting_a_tender_account_changes_NO_posting` went RED the moment the receipt leg read the
#        column, and it is INVERTED (not deleted) as `test_cr008_the_tender_account_wiring_moved_BOTH_legs_together` — the same sentence guarded from the
#        other side: both legs must exist in one tree state. Behaviour is proved end to end in tests/test_cr008_tender_gl_posting.py (RED-first, quoted there).
# exceptions: E4 the auto-posting branch of `request_write_off` (a write-off at or below a tenant's threshold, by a System Admin, with a posting instant) is NOT exercised here — it needs an account with a real outstanding balance and the billing seam behind it, which is `tests/test_us_pay_012_write_offs.py`'s fixture territory. What IS asserted is the decision function at its boundary ($49.99 / $50.00 / $50.01) and the seeded 0.00 that makes the branch unreachable today · E4 `test_cr008_nothing_in_the_engine_reads_accounting_method` greps two app folders for a string, which is a coarse instrument — it is here because the PO's ruling rests on that measurement, and a grep that goes red the day somebody starts reading the column is worth more than a comment saying nobody does
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
