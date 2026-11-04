# ── Trace ──────────────────────────────────────────────
# Change:   CR-005 (PO 2026-08-16) — SET-08 Numbering: every system-generated
#           number gets a defined format.   Screens: S8 · r10 SET-08
# Story:    US-TEN-012 (EP-TEN-08) — extended, not replaced
# Rules:    BR-TEN-035 clauses (a)–(e) (length + pad · restart period · overflow
#           widens · duplicate prefixes warn · a plain option in every category) ·
#           BR-TEN-016 (audit before/after) · BR-LED-021 (the JE- series) ·
#           BR-TEN-043 (the issue date is an input) · CLAUDE.md rule 4
# Questions: OQ-250 (pad minimum — NOT enforced) · OQ-251 (the union of 22
#           series) · OQ-252 (restart needs its date token; a backdated
#           allocation under restart is refused)
# ───────────────────────────────────────────────────────
"""CR-005 — the SET-08 Numbering clauses, each asserted against the requirement
it comes from.

Every case here quotes the PO's own sentence, because the CR is the contract and
a test that only asserts the code's behaviour cannot tell a requirement from an
accident.
"""

import json
from datetime import date
from pathlib import Path

import pytest
from django.db import transaction

from apps.tenancy import api, models, selectors, services
from core import errors
from core import numbering as core_numbering

from tests.test_us_ten_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_ten_helpers import (
    FakeUser,
    admin_actor,
    api_call,
    provisioned_tenant,
    tenant_ctx,
)

pytestmark = pytest.mark.django_db

ISSUE_DATE = date(2026, 8, 8)


@pytest.fixture(autouse=True)
def series_sink():
    core_numbering.set_series_sink(services.allocate_series_number)
    yield
    core_numbering.set_series_sink(services.allocate_series_number)


# ── The catalog: what the screen may offer, and what a tenant is given ──────


def test_cr005_every_category_offers_a_plain_prefix_free_option():
    """*"Plain-number option is mandatory in every category (user rule): just
    `{00000}` with no prefix"* — an explicit user rule, so a series that loses
    it goes RED here rather than being noticed on a screen."""
    missing = [
        series
        for series, (_group, options) in core_numbering.SERIES_CATALOG.items()
        if not any(core_numbering.literal_prefix(option) == "" for option in options)
    ]
    assert missing == []


def test_cr005_every_ready_made_option_is_a_format_the_save_would_accept():
    """A dropdown offering a format the server refuses is a defect by
    construction. The catalog is validated with the SAME function the save
    calls, so the two cannot drift."""
    for series, (group, options) in core_numbering.SERIES_CATALOG.items():
        assert group in core_numbering.SERIES_GROUPS, series
        for option in options:
            core_numbering.validate_format(option)  # raises = RED


def test_cr005_the_seeded_default_is_the_first_ready_made_option():
    """One source for both, so a tenant can never hold a format its own
    dropdown does not offer — the gap that left `SERIES_DEFAULTS` at five while
    `KNOWN_SERIES` held nine, and left every manual journal entry unnumbered
    (BR-LED-021 (i))."""
    for series, (_group, options) in core_numbering.SERIES_CATALOG.items():
        assert services.SERIES_DEFAULTS[series] == options[0]
    assert set(services.SERIES_DEFAULTS) == set(core_numbering.KNOWN_SERIES)
    # The union of the CR's sixteen and r10's fourteen (OQ-251), plus the
    # bill-run series OQ-342 added on 2026-08-23 (PO: *"A: a real series
    # (RUN-0001, like RT-001)"*) — twenty-three — plus the `customer` series
    # CR-030 W0 added the same day, which is the TWENTY-FOURTH. This assertion
    # went RED on the commit that added it, which is what it is for: `customers`
    # was the only entity in the product with no number, so every deposit
    # carry-forward rested on a clerk matching a NAME (B18 §2.5).
    # ⚠ 25, NOT 24, AND RE-MEASURED RATHER THAN INCREMENTED (DEF-807).
    # `service_request` joined the catalogue and this count was never
    # moved, so this assertion has been red since. It is the third test in
    # the numbering family to pin the catalogue by hand and be left behind
    # by it — the other two are `test_which_series_have_a_live_consumer`
    # and `test_def615_series_defaults::test_every_series_is_pinned`, both
    # corrected the same day. A catalogue pinned by hand in three places
    # goes stale in three places.
    # ⚠ 26 SINCE 2026-08-27, AND RE-MEASURED RATHER THAN INCREMENTED (the
    # DEF-807 discipline the paragraph above records). `transfer` joined on the
    # PO ruling that closed OQ-426 — *"Transfer TRF-26-0001 … follow same logic
    # that we are following for other numbers we have did in settings"* — and
    # all three hand-pinned places moved in the SAME commit as the catalogue
    # row. RED first, verbatim: `AssertionError: assert 26 == 25`.
    # ⛔ `disconnect` did NOT join: OQ-427 is explicitly still open, and the
    # transfer ruling's reason does not carry to a record that belongs to one
    # account and that r10 draws as a work order.
    # ⚠ 27 SINCE LATER THE SAME DAY, AND THE THREE LINES ABOVE ARE KEPT RATHER
    # THAN EDITED, because they were true for about an hour and read as
    # permanent. OQ-427 was ASKED and ANSWERED — PO verbatim, in full: *"it
    # needs its own series"* — so `disconnect_case` is the twenty-seventh. Its
    # format is the BUILD's DELEGATED choice (`DSC-{YY}-{0000}` → `DSC-26-0001`,
    # decision log 2026-08-27), and the `work_order` series is untouched, which
    # is the distinction the ruling drew. Re-measured rather than incremented
    # (DEF-807). RED first, verbatim: `AssertionError: assert 27 == 26`.
    # ⚠ **29 SINCE THE SAME AFTERNOON, AND THE LAST TWO ARE THE BUILD'S, NOT A
    # PO's.** `move_in` (`MVI-`) and `move_out` (`MVO-`) joined for CR-039 wave
    # D task 18. The PO ruled that a move-in and a move-out ARE records — *"you
    # cna keep them as records for audit perpuses"* — and the decision log
    # states in as many words that the ruling *"DOES NOT SETTLE D18's
    # NUMBERING"*. They are numbered as a flagged EXTENSION of the disconnect
    # ruling: a disconnect is a one-account job and got its own series, which
    # kills the argument that a one-account job needs none. **One word from the
    # PO reverses both rows.** Re-measured, not incremented. RED first,
    # verbatim: `AssertionError: assert 29 == 27`.
    # ⚠ **30 SINCE 2026-09-04 — `interruption_report` (`RP-`), CR-068 wave B.**
    # A stranger reporting a burst main is given `RP-26-0412` and it is the
    # whole record of the interaction (`BR-CWP-028`); it is deliberately NOT
    # the `SR-` number of the request the same act raises, because that is a
    # clerk's case number and `Track` must be able to tell the two apart.
    # Re-measured, not incremented. RED first, verbatim:
    # `AssertionError: assert 30 == 29`.
    # ⚠ **31 SINCE 2026-09-22 — `settlement` (`STL-`), the payments blueprint's
    # `P0.13`.** PO ruling that day, verbatim: *"(a) STL-26-0001"*. It is the ONE
    # series phase 0 adds: counter batches reuse `deposit_batch` and imports
    # reuse `import_run`, and a settlement is neither — it is what a card
    # processor or an ACH originator actually paid out, which no person carried
    # to a bank. Re-measured, not incremented (the DEF-807 discipline this test
    # records above). RED first, verbatim: `AssertionError: assert 31 == 30`.
    # ⚠ **32 SINCE 2026-10-14 — `correction_case` (`CC-`), G3.** PO ruling that
    # day: a correction case takes its number at Send from a new tenant series
    # "Correction case", default `CC-{YYYY}-{000}` (`DEF-BIL-10147`).
    # Re-measured, not incremented. RED first, verbatim:
    # `AssertionError: assert 32 == 31`.
    assert len(core_numbering.KNOWN_SERIES) == 32


#: The English catalogue, read from disk. A backend test may read the frontend's
#: copy — `tests/test_def_684_category_vocabulary.py` already does — and this is
#: the only place the two sides of DEF-880 can be compared at all.
EN_CATALOGUE = (
    Path(__file__).resolve().parents[2] / "07-frontend" / "src" / "i18n" / "locales" / "en.json"
)


def test_def880_every_catalogued_series_has_a_label_on_the_settings_screen():
    """DEF-880 — the S8 Numbering tab printed RAW TRANSLATION KEYS for three of
    its rows, to a System Admin, in all eleven languages.

    `SettingsNumberingTab` renders every row's entity name as
    ``t(`settings.numbering.series.${row.series}`)`` with **no defaultValue**,
    and i18next renders the key itself on a miss. The catalogue held 22 labels
    for 25 series: `connection` (CR-032), `customer` (CR-030 W0) and `bill_run`
    (OQ-342) each added a `SERIES_CATALOG` row and none added its label, so
    those three rows read `settings.numbering.series.connection` and its two
    siblings on a shipped screen — and the same string is interpolated into the
    blocked-save banner, the duplicate-prefix warning and the reset-counter
    confirmation.

    ⚠ **G18 CANNOT SEE THIS, BY DESIGN, WHICH IS WHY THE TEST IS HERE.** G18
    treats any literal that is a proper dotted PREFIX of a catalogue key as
    naming that whole family, so `settings.numbering.series.` is satisfied by
    ONE member existing; nothing compares the family's MEMBERS to the
    enumeration that generates them. G15 is no help either — eleven catalogues
    agreeing on a missing key is perfect parity.

    RED FIRST, verbatim, with `settings.numbering.series.transfer` removed from
    `en.json`:

        AssertionError: 1 catalogued number series has no label on S8 and will
        print its raw key: ['transfer']

    This test asserts the ENGLISH catalogue only; G15 is what makes the other
    ten follow, and duplicating its job here would be two checks that can
    disagree.
    """
    catalogue = json.loads(EN_CATALOGUE.read_text(encoding="utf-8"))
    missing = sorted(
        series
        for series in core_numbering.SERIES_CATALOG
        if f"settings.numbering.series.{series}" not in catalogue
    )
    assert not missing, (
        f"{len(missing)} catalogued number series has no label on S8 and will print "
        f"its raw key: {missing}"
    )


def test_cr005_default_prefixes_do_not_collide_out_of_the_box(growth_plan, identity_seam):
    """Duplicate prefixes are a WARNING, never a block — but a tenant should not
    be greeted by one on a screen nobody has touched."""
    tenant, _ = provisioned_tenant()
    with tenant_ctx(tenant):
        rows = selectors.number_series_overview()
    assert [row["series"] for row in rows if row["duplicate_prefix"]] == []


def test_cr005_provisioning_seeds_every_catalogued_series_and_the_je_series_is_one(
    growth_plan, identity_seam
):
    """BR-LED-021 (i) named the fix: *"the one-line fix is
    `SERIES_DEFAULTS[core_numbering.JOURNAL_ENTRY] = "JE-{000000}"` and belongs
    to the tenancy lane"*. It is derived rather than typed, so the next series
    cannot go missing the same way.

    ⚠ **THE SEEDED FORMAT AND ITS WORKED FIGURE BOTH MOVED ON 2026-09-24
    (`P0.13`), AND THE CLAIM THIS TEST MAKES DID NOT.** It asserted
    `JE-{000000}` and `JE-000104` from CR-005 (2026-08-17) until the PO ruled,
    verbatim, on 2026-09-23: *"you need je-MMDDYY- nnnn like this otherwise it
    will not work"*. The seeded default is now `JE-{MM}{DD}{YY}-{0000}`, and a
    tenant whose series opens at 104 posts **JE-080826-0104** on this file's
    issue date of 8 August 2026. What is being checked — *provisioning seeds
    every series the kernel knows, and the journal series is one of them* — is
    unchanged."""
    tenant, _ = provisioned_tenant()
    with tenant_ctx(tenant):
        # ⚠ Counted from the CATALOGUE, not typed: this read `== 22` and went
        # red the day OQ-342 added the twenty-third, which is the useful kind
        # of red — but the claim the test makes is *"provisioning seeds every
        # series the kernel knows"*, and a literal restates the catalogue
        # instead of checking it.
        #
        # ⚠ **IT MOVED INSIDE `tenant_ctx` ON 2026-09-24, AND IT HAD BEEN
        # IMPOSSIBLE TO PASS ON POSTGRESQL SINCE THIS FILE WAS WRITTEN
        # (2026-09-21, `67b5df437`).** `number_series` carries `ENABLE ROW
        # LEVEL SECURITY` **and `FORCE`**, so a read with no `app.tenant_id`
        # sees **no rows at all** — and `provision_tenant` clears the context
        # on its way out. Outside the block this assertion read `0 == 31`,
        # always, on the only database where the guarantee exists.
        #
        # It passed on the default suite because **SQLite has no RLS**, which
        # is hard-won law 7's *incapable of passing* in its purest form: a
        # check that is green on the tier that cannot enforce the rule and red
        # on the tier that does. Nothing about what it asserts has changed.
        assert models.NumberSeries.objects.filter(tenant=tenant).count() == len(
            core_numbering.KNOWN_SERIES
        )
        assert (
            models.NumberSeries.objects.get(
                tenant=tenant, series=core_numbering.JOURNAL_ENTRY
            ).format
            == "JE-{MM}{DD}{YY}-{0000}"
        )
        services.save_number_series(admin_actor(), core_numbering.JOURNAL_ENTRY, next_number=104)
        with transaction.atomic():
            assert core_numbering.next_number(core_numbering.JOURNAL_ENTRY, ISSUE_DATE) == (
                "JE-080826-0104"
            )


def test_cr005_the_three_work_series_exist_as_formats_and_nothing_else(
    growth_plan, identity_seam
):
    """PO 2026-08-16, verbatim: *"Yes; it should work standalone in settings; we
    will link it later ith work"*. Three series with three formats — and no
    table for a work order, a crew or a part, so OQ-249 is untouched."""
    tenant, _ = provisioned_tenant()
    with tenant_ctx(tenant):
        rows = {row["series"]: row for row in selectors.number_series_overview()}
        for series in ("work_order", "service_template", "dispatch_batch"):
            assert rows[series]["group"] == core_numbering.GROUP_WORK
            assert rows[series]["preview"] is not None
        with transaction.atomic():
            assert core_numbering.next_number("work_order", ISSUE_DATE) == "WO-0001"


# ── Clause (a): length and pad ─────────────────────────────────────────────


def test_cr005_a_format_over_24_characters_is_refused_by_name():
    """*"validated: max 1 counter, only allowed tokens, ≤ 24 chars"*."""
    with pytest.raises(errors.ValidationError) as excinfo:
        core_numbering.validate_format("SUPERLONGPREFIXHERE-{00000}-X")
    assert excinfo.value.params["problem"] == "too_long"
    core_numbering.validate_format("A" * 16 + "-{00000}")  # exactly 24: allowed


def test_cr005_a_counter_wider_than_eight_digits_is_refused():
    with pytest.raises(errors.ValidationError) as excinfo:
        core_numbering.validate_format("AC-{000000000}")
    assert excinfo.value.params["problem"] == "pad_too_long"
    core_numbering.validate_format("AC-{00000000}")  # exactly 8: allowed


def test_cr005_the_pad_minimum_of_four_is_deliberately_not_enforced_oq250():
    """OQ-250, and this test is the RECORD of the decision rather than an
    endorsement of it. The CR says *"pad length 4–8"*; the shipped `ADJ-{000}`
    default and nine of r10 SET-08's own dropdown options are below four. The
    lower bound is not enforced, so nothing already stored or already drawn
    becomes unsaveable. If the PO confirms the minimum, this test is what has
    to change, and it names the question when it does."""
    core_numbering.validate_format("ADJ-{000}")
    core_numbering.validate_format("DEP-{YY}{MM}{DD}-{00}")
    assert core_numbering.render("ADJ-{000}", 41, ISSUE_DATE) == "ADJ-041"


# ── Clause (b): the restart period ─────────────────────────────────────────


def test_cr005_a_yearly_restart_rolls_the_counter_on_the_first_number_of_the_year(
    growth_plan, identity_seam
):
    """*"Restart counter each year/month — Yes/No per entity"*. Worked: a bill
    series `BL-{YYYY}-{000000}` standing at 18,411 on 31 December issues
    **BL-2026-018411**, and the first bill of the new year is
    **BL-2027-000001** — not 018412."""
    tenant, _ = provisioned_tenant()
    with tenant_ctx(tenant):
        services.save_number_series(
            admin_actor(),
            "bill",
            format_string="BL-{YYYY}-{000000}",
            next_number=18411,
            restart_period=core_numbering.RESTART_YEARLY,
        )
        with transaction.atomic():
            last_of_2026 = core_numbering.next_number("bill", date(2026, 12, 31))
        with transaction.atomic():
            first_of_2027 = core_numbering.next_number("bill", date(2027, 1, 1))
            second_of_2027 = core_numbering.next_number("bill", date(2027, 1, 2))
    assert last_of_2026 == "BL-2026-018411"
    assert first_of_2027 == "BL-2027-000001"
    assert second_of_2027 == "BL-2027-000002"


def test_cr005_a_monthly_restart_rolls_on_the_month(growth_plan, identity_seam):
    tenant, _ = provisioned_tenant()
    with tenant_ctx(tenant):
        services.save_number_series(
            admin_actor(), "bill", restart_period=core_numbering.RESTART_MONTHLY
        )
        with transaction.atomic():
            core_numbering.next_number("bill", date(2026, 8, 8))
            august_second = core_numbering.next_number("bill", date(2026, 8, 9))
        with transaction.atomic():
            september = core_numbering.next_number("bill", date(2026, 9, 1))
    assert august_second == "BL-2608-000002"
    assert september == "BL-2609-000001"


def test_cr005_a_restart_without_its_date_token_is_refused_oq252(growth_plan, identity_seam):
    """OQ-252 — the guard that stops a restart re-minting a number a customer
    already has. Yearly restart on `AC-{YYYY}-{00000}` is fine; on a plain
    counter it would hand out AC-00001 twice, one year apart, and the first is
    on a row hard rule 4 forbids anyone to correct."""
    tenant, _ = provisioned_tenant()
    with tenant_ctx(tenant):
        services.save_number_series(
            admin_actor(), "account", restart_period=core_numbering.RESTART_YEARLY
        )  # AC-{YYYY}-{00000} carries its year token — allowed
        with pytest.raises(errors.ValidationError) as excinfo:
            services.save_number_series(
                admin_actor(),
                "account",
                format_string="AC-{00000}",
                restart_period=core_numbering.RESTART_YEARLY,
            )
        assert excinfo.value.params["problem"] == "needs_year_token"
        # Monthly needs BOTH tokens: {MM} alone repeats every January.
        with pytest.raises(errors.ValidationError) as excinfo:
            services.save_number_series(
                admin_actor(),
                "adjustment",
                format_string="A-{MM}-{0000}",
                restart_period=core_numbering.RESTART_MONTHLY,
            )
        assert excinfo.value.params["problem"] == "needs_year_and_month_tokens"
        # And the pair is re-checked when only the FORMAT moves afterwards.
        with pytest.raises(errors.ValidationError):
            services.save_number_series(
                admin_actor(), "account", format_string="ACCT-{00000}"
            )


def test_cr005_a_backdated_number_under_a_restart_is_refused_not_minted(
    growth_plan, identity_seam
):
    """BR-TEN-043 lets a caller number under a past date, and under a restart
    that cannot be done safely: a monthly series that issued **BL-2607-000001**
    in July and stands at 2 in August would hand a July-dated bill
    **BL-2607-000002** — which July's counter will also hand out. Refused by
    name, so a human decides, rather than minted."""
    tenant, _ = provisioned_tenant()
    with tenant_ctx(tenant):
        services.save_number_series(
            admin_actor(), "bill", restart_period=core_numbering.RESTART_MONTHLY
        )
        with transaction.atomic():
            core_numbering.next_number("bill", date(2026, 8, 8))
        with transaction.atomic():
            with pytest.raises(core_numbering.NumberingError) as excinfo:
                core_numbering.next_number("bill", date(2026, 7, 31))
    assert "numbering_restart_backdated" in str(excinfo.value)


def test_cr005_changing_the_restart_policy_clears_the_recorded_period(
    growth_plan, identity_seam
):
    """The counter's POSITION only means something under the policy in force
    when it was recorded — "2026-08" against a series that now restarts yearly
    would read as a rolled year."""
    tenant, _ = provisioned_tenant()
    with tenant_ctx(tenant):
        services.save_number_series(
            admin_actor(),
            "bill",
            format_string="BL-{YYYY}{MM}-{000000}",
            restart_period=core_numbering.RESTART_MONTHLY,
        )
        with transaction.atomic():
            core_numbering.next_number("bill", ISSUE_DATE)
        assert models.NumberSeries.objects.get(tenant=tenant, series="bill").period_counted == (
            "2026-08"
        )
        services.save_number_series(
            admin_actor(), "bill", restart_period=core_numbering.RESTART_YEARLY
        )
        assert models.NumberSeries.objects.get(tenant=tenant, series="bill").period_counted == ""


# ── Clause (c): overflow widens and warns ──────────────────────────────────


def test_cr005_an_overflowing_counter_keeps_issuing_and_is_flagged(growth_plan, identity_seam):
    """*"Counter overflow (counter exceeds pad length) → keep issuing, widen
    number, surface a warning banner"*. Worked: `ADJ-{000}` at 1,000 issues
    **ADJ-1000** — four digits in a three-digit pad, nothing truncated and
    nothing refused, with `overflow` true so the screen can say so."""
    tenant, _ = provisioned_tenant()
    with tenant_ctx(tenant):
        services.save_number_series(admin_actor(), "adjustment", next_number=1000)
        row = selectors.number_series_row("adjustment")
        assert row["overflow"] is True
        assert row["preview"] == "ADJ-1000"
        with transaction.atomic():
            assert core_numbering.next_number("adjustment", ISSUE_DATE) == "ADJ-1000"
        assert selectors.number_series_row("bill")["overflow"] is False


# ── Clause (d): duplicate prefixes warn, never block ───────────────────────


def test_cr005_a_duplicate_prefix_saves_and_warns(growth_plan, identity_seam):
    """*"duplicate prefixes across entities → warning (not blocking)"*. Two
    series on `AC-` is a house-style problem, not a uniqueness one — uniqueness
    is per series per tenant."""
    tenant, _ = provisioned_tenant()
    with tenant_ctx(tenant):
        services.save_number_series(admin_actor(), "bill", format_string="AC-{YY}-{00000}")
        rows = {row["series"]: row for row in selectors.number_series_overview()}
    assert rows["bill"]["duplicate_prefix"] is True
    assert rows["account"]["duplicate_prefix"] is True
    assert rows["payment"]["duplicate_prefix"] is False


def test_cr005_plain_prefix_free_formats_never_count_as_duplicates(growth_plan, identity_seam):
    """The plain option is MANDATORY in every category, so twenty-two tenants
    of the empty prefix must not be twenty-two collisions."""
    tenant, _ = provisioned_tenant()
    with tenant_ctx(tenant):
        services.save_number_series(admin_actor(), "bill", format_string="{00000000}")
        services.save_number_series(admin_actor(), "receipt", format_string="{000000}")
        rows = {row["series"]: row for row in selectors.number_series_overview()}
    assert rows["bill"]["duplicate_prefix"] is False
    assert rows["receipt"]["duplicate_prefix"] is False


# ── The screen's contract: grouping, options, and the whole-tab save ────────


def test_cr005_the_tab_read_carries_group_options_and_restart(growth_plan, identity_seam):
    """The screen composes NO option list of its own — a dropdown that offered
    a format the save refuses would be a defect by construction."""
    tenant, _ = provisioned_tenant()
    response = api_call(api.number_series, "get", user=FakeUser(), role="system_admin", tenant=tenant)
    assert response.status_code == 200
    rows = {row["series"]: row for row in response.data}
    account = rows["account"]
    assert account["group"] == core_numbering.GROUP_CUSTOMERS
    assert account["options"][0] == "AC-{YYYY}-{00000}"
    assert "{0000000}" in account["options"]
    assert account["restart_period"] == core_numbering.RESTART_NEVER
    assert account["prefix"] == "AC-"
    # Grouped in the order the screen prints, never alphabetically by key.
    assert [row["series"] for row in response.data][:4] == [
        "account",
        "premises",
        "unit",
        "service_request",
    ]


def test_cr005_a_custom_format_stays_in_its_own_option_list(growth_plan, identity_seam):
    """A picker that silently drops the value it is showing reads as "your
    format was reset"."""
    tenant, _ = provisioned_tenant()
    with tenant_ctx(tenant):
        services.save_number_series(admin_actor(), "account", format_string="BRAZOS-{YYYY}-{0000}")
        row = selectors.number_series_row("account")
    assert row["format"] in row["options"]


def test_cr005_save_persists_every_row_in_one_transaction_with_one_audit_row(
    growth_plan, identity_seam, audit_rows
):
    """*"Save (primary, bottom-left) — persists all rows in one transaction,
    toast + audit log entry (who, when, old → new format per entity)"*."""
    tenant, _ = provisioned_tenant()
    with tenant_ctx(tenant):
        audit_rows.clear()
        saved = services.save_number_series_bulk(
            admin_actor(),
            [
                {"series": "account", "format": "ACCT-{00000}"},
                {"series": "bill", "next_number": 20000},
                {"series": "receipt", "format": "REC-{000000}", "next_number": 8842},
            ],
        )
    rows = {row["series"]: row for row in saved}
    assert rows["account"]["format"] == "ACCT-{00000}"
    assert rows["bill"]["next_number"] == 20000
    assert rows["receipt"]["preview"] == "REC-008842"
    entries = [row for row in audit_rows if row["action"] == "settings.numbering.bulk_updated"]
    assert len(entries) == 1  # ONE row for the whole tab, keyed by entity
    assert entries[0]["before"]["account"]["format"] == "AC-{YYYY}-{00000}"
    assert entries[0]["after"]["account"]["format"] == "ACCT-{00000}"
    assert entries[0]["before"]["bill"]["next_number"] == 1
    assert set(entries[0]["after"]) == {"account", "bill", "receipt"}


def test_cr005_one_bad_row_saves_none_of_them(growth_plan, identity_seam):
    """The transaction is what makes a screen-wide Save honest: an admin who
    changed three formats together believes they took effect together."""
    tenant, _ = provisioned_tenant()
    with tenant_ctx(tenant):
        with pytest.raises(errors.ValidationError):
            services.save_number_series_bulk(
                admin_actor(),
                [
                    {"series": "account", "format": "ACCT-{00000}"},
                    {"series": "bill", "format": "BL-{QQ}-{000}"},  # unknown token
                ],
            )
        assert selectors.number_series_row("account")["format"] == "AC-{YYYY}-{00000}"


def test_cr005_a_backward_counter_is_refused_in_bulk_too(growth_plan, identity_seam):
    """*"Counter reset: allowed only forward (can't set lower than current —
    prevents duplicate IDs)"*, whichever door the edit arrives through."""
    tenant, _ = provisioned_tenant()
    with tenant_ctx(tenant):
        services.save_number_series(admin_actor(), "bill", next_number=18411)
        with pytest.raises(errors.ValidationError) as excinfo:
            services.save_number_series_bulk(admin_actor(), [{"series": "bill", "next_number": 500}])
        assert excinfo.value.params == {"min": 18411}
        assert selectors.number_series_row("bill")["next_number"] == 18411


def test_cr005_the_bulk_save_endpoint_is_system_admin_only(growth_plan, identity_seam):
    """PO 2026-08-16: *"all settingsa re Admin only I believ; follow same rule
    that we folowed for settings related permission"* — the same
    `SystemAdminOnly` gate `/lookups/*` carries, on the new verb as well as the
    old one. A Billing Clerk cannot change how bills are numbered.

    ⚠ **THIS CASE ASSERTS THE GATE TWICE ON PURPOSE, AND THE SECOND ASSERTION
    EXISTS BECAUSE THE FIRST ONE COULD NOT FAIL.** Proving it RED (law 7) by
    swapping the endpoint's `SystemAdminOnly` for `AnyTenantRole` left the test
    GREEN — the clerk was still refused, by `@require_role(SYSTEM_ADMIN)` on the
    service underneath. Two gates is the right posture and neither is removed;
    what is wrong is a test that reports on a guard it cannot see. So the
    permission class is asserted directly as well, and the behavioural
    assertion keeps covering the service gate.

    ⚠ **AMENDED 2026-08-17 (DEF-196), AND THE AMENDMENT IS THE POINT.** This
    case asserted `SystemAdminOnly` on a view serving **GET and PUT from one
    function**, so it locked in a gate that refused the READ too — and the PO
    had separately ruled that a Billing Clerk and an Executive **may LOOK at
    numbering formats and may not change them**. Both halves of this docstring
    were true and together they cancelled the ruling out. A real Executive got
    403 on the read and saw *"You don't have access to this"*, never the
    read-only screen; every `readOnly` branch in the tab was dead code.

    **The test could not have caught it, because it only ever tried to WRITE.**
    So the read is asserted here now, per role, which is the assertion whose
    absence let this ship.
    """
    from core.permissions import SettingsReadAnyWriteSystemAdmin

    assert api.number_series.cls.permission_classes == [SettingsReadAnyWriteSystemAdmin]
    tenant, _ = provisioned_tenant()

    # The WRITE is still refused, by both gates. Unchanged.
    for role in ("billing_clerk", "executive"):
        response = api_call(
            api.number_series,
            "put",
            user=FakeUser(),
            role=role,
            tenant=tenant,
            data={"rows": [{"series": "bill", "next_number": 999}]},
        )
        assert response.status_code == 403, role
    with tenant_ctx(tenant):
        assert selectors.number_series_row("bill")["next_number"] == 1

    # DEF-196: the EXECUTIVE's read is now ALLOWED, which is the ruling. Without
    # it the tab renders the no-access page and its read-only state is
    # unreachable code.
    #
    # ⚠ THE BILLING CLERK IS NOT IN THIS LIST, and the first cut of the fix put
    # them in it. A4's `settings_lookups` row is
    # {"system_admin": "Full", "executive": "View"} — the clerk has NO CELL,
    # which is no access rather than read-only access. US-TEN-009 TC-5 has
    # asserted that since the surface was built and is what caught it.
    denied = api_call(
        api.number_series, "get", user=FakeUser(), role="billing_clerk", tenant=tenant
    )
    assert denied.status_code == 403, "a Billing Clerk has no settings_lookups cell in A4"

    for role in ("executive",):
        response = api_call(
            api.number_series, "get", user=FakeUser(), role=role, tenant=tenant
        )
        assert response.status_code == 200, (
            f"{role} must be able to READ the numbering tab — a role A4 grants "
            "'View' that is denied the read never sees the read-only screen"
        )
        assert response.data, "the read must carry the table, not an empty shell"
        assert any(row["series"] == "bill" for row in response.data), (
            "the numbering rows themselves must be readable, not just a 200"
        )


def test_cr005_the_format_change_applies_to_future_numbers_only(growth_plan, identity_seam):
    """*"Changes apply to numbers issued from now on; already-issued numbers are
    never renumbered (immutable, stated on screen)"* — CLAUDE.md rule 4's shape,
    and the reason no renumber API exists at any layer."""
    tenant, _ = provisioned_tenant()
    with tenant_ctx(tenant):
        with transaction.atomic():
            before = core_numbering.next_number("account", ISSUE_DATE)
        services.save_number_series_bulk(
            admin_actor(), [{"series": "account", "format": "CUST-{000000}"}]
        )
        with transaction.atomic():
            after = core_numbering.next_number("account", ISSUE_DATE)
    assert before == "AC-2026-00001"  # the number already stamped, unchanged
    assert after == "CUST-000002"  # the next one, in the new format
    assert not hasattr(services, "renumber_series")


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-TEN-012@80cdedf (the story this extends; the CHANGE is CR-005 — 12-governance/11-change-requests.md, PO 2026-08-16)
# generated: 2026-08-17 by the CR-005 SET-08 Numbering lane
# checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-09)
# gates: pytest tests/test_cr005_numbering_set08.py · every guard proved RED before it was trusted green (hard-won law 7 — quoted in the lane's report)
# exceptions: none stubbed
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
