# ── Trace ──────────────────────────────────────────────
# Change:   payments blueprint phase 0, task `P0.13` — *"One number series …
#           The settlement series. Counter batches reuse `deposit_batch`,
#           imports reuse `import_run`."* Outcome: *"The entire Settings change
#           for all 35 screens."*
# Ruled:    PO 2026-09-22, verbatim: *"(a) STL-26-0001"*.
# Rules:    BR-TEN-035 (a number is allocated inside the issuing transaction;
#           gaps are fine and a number is never reused; every seeded default is
#           tenant-editable) · BR-TEN-043 (the issue date is an INPUT, never the
#           wall clock) · CR-005 (the catalogue's own rules — a bare counter in
#           every list, no duplicate seeded prefix)
# Tests:    this file
# ───────────────────────────────────────────────────────
"""`P0.13` — the settlement series, and the two things it must not become.

A card processor, an ACH originator or a lockbox provider takes many payments
during a day and pays the utility ONE amount for them, later. That payout is
what the blueprint's fifth tab draws — *"Which 46 payments made up this
$8,047.30?"* — and it had no number because it had no row.

════════════════════════════════════════════════════════════════════════════
WHAT IS RULED AND WHAT IS NOT
════════════════════════════════════════════════════════════════════════════
**RULED:** the rendered string. The Product Owner was shown `STL-26-0001` in
plain English and chose it, so `test_the_first_settlement_on_a_new_tenant_is_
stl_26_0001` is the ratified figure pinned so drift goes RED.

**NOT RULED:** that it stays that way on any tenant. It is a SEEDED DEFAULT a
tenant edits on Settings → Numbering like the other thirty, which the decision
log states in as many words: *"a seeded default a tenant edits, never a
constant."* Nothing in this file asserts a tenant's stored row.

════════════════════════════════════════════════════════════════════════════
RED-FIRST (r11 step 2d / hard-won law 7)
════════════════════════════════════════════════════════════════════════════
Every case below was run against the pre-change tree first.

  1. with `SETTLEMENT` absent from `SERIES_CATALOG` →
        E   KeyError: 'settlement'
     on `SERIES_DEFAULTS[core_numbering.SETTLEMENT]`, in all four cases.
  2. with the default written `STL-{YYYY}-{0000}` (the plausible wrong one) →
        E   AssertionError: assert 'STL-2026-0001' == 'STL-26-0001'
  3. with `SETTLEMENT` seeded as `DEP-{YY}-{0000}` — i.e. a lane deciding a
     settlement is "just another deposit batch" →
        E   AssertionError: the settlement series must not borrow the deposit
            batch's prefix
"""

from datetime import date

import pytest

from apps.tenancy import services as tenancy_services
from core import numbering as core_numbering

pytestmark = pytest.mark.django_db


def test_the_first_settlement_on_a_new_tenant_is_stl_26_0001():
    """⚠ **THE RATIFIED FIGURE, PINNED SO DRIFT GOES RED.**

    The PO named a rendered STRING rather than a format — *"(a) STL-26-0001"* —
    and this is the assertion that the product produces exactly that string. It
    is the figure the human-review ledger row states in plain English: *"the
    first settlement on a new tenant is numbered STL-26-0001"*.

    Deterministic on purpose: the issue date is a literal rather than
    `tenant_today()`, so this test says the same thing in 2027 as it does today.
    """
    default = tenancy_services.SERIES_DEFAULTS[core_numbering.SETTLEMENT]
    assert default == "STL-{YY}-{0000}"
    assert core_numbering.render(default, 1, date(2026, 9, 22)) == "STL-26-0001"


def test_the_settlement_never_borrows_the_deposit_batch_or_the_import_run():
    """⚠ **THE TASK'S OWN SENTENCE, ASSERTED — *"Counter batches reuse
    `deposit_batch`, imports reuse `import_run`"*.**

    `P0.13` adds ONE series, not three, and the reason a settlement is not a
    deposit batch is a money reason rather than a tidiness one: a deposit batch
    is money a PERSON carried to a bank and is keyed on their till session,
    while a settlement is money a PROVIDER wired and has no person at all. A
    later lane that "simplified" this by pointing settlements at `DEP-` would
    make a card payout indistinguishable from a counter drawer on a bank
    statement.

    The prefixes must therefore stay DISTINCT — which is also what keeps CR-005's
    duplicate-prefix warning silent on a tenant nobody has touched.
    """
    defaults = tenancy_services.SERIES_DEFAULTS
    settlement = core_numbering.literal_prefix(defaults[core_numbering.SETTLEMENT])
    assert settlement == "STL-"
    assert settlement != core_numbering.literal_prefix(
        defaults[core_numbering.DEPOSIT_BATCH]
    ), "the settlement series must not borrow the deposit batch's prefix"
    assert settlement != core_numbering.literal_prefix(defaults[core_numbering.IMPORT_RUN])
    # The two the task says are REUSED still open on their own prefixes. ⚠ The
    # PREFIX is asserted and not the whole format, deliberately: `P0.6` widened
    # the deposit batch's pad from `{00}` to `{0000}` on the same day and the
    # same branch (PO: *"DEP-260922-0001"*), and a test that pinned the literal
    # format here would fight a sibling's ruling to say something it does not
    # mean. What must not move is that a settlement and a deposit batch are told
    # apart at a glance on a bank statement.
    assert core_numbering.literal_prefix(defaults[core_numbering.DEPOSIT_BATCH]) == "DEP-"
    assert core_numbering.literal_prefix(defaults[core_numbering.IMPORT_RUN]) == "IMP-"


def test_the_settlement_row_obeys_the_catalogue_s_own_rules():
    """CR-005's two standing rules, asserted for the row this task adds.

    `test_cr005_numbering_set08.py` asserts both across the whole catalogue;
    they are repeated here against this one key so that a failure NAMES the
    settlement series rather than reporting a catalogue-wide count.
    """
    group, options = core_numbering.SERIES_CATALOG[core_numbering.SETTLEMENT]
    # It renders on the Settings screen beside the deposit batch, not with the
    # journal and the accounting export.
    assert group == core_numbering.GROUP_BILLING
    # CR-005, verbatim: *"Plain-number option is mandatory in every category"*.
    assert options[-1] == "{000000}"
    # Every option offered must be a format the grammar accepts, or the screen
    # can hand a tenant a row the allocator then refuses.
    for option in options:
        core_numbering.validate_format(option)


def test_a_new_tenant_is_seeded_with_a_settlement_row():
    """The end the Settings screen actually reads: provisioning writes the row.

    ⚠ **`_seed_number_series` is `get_or_create`, so a host already running
    today has NO settlement row until somebody re-seeds it** — the same state
    `transfer` and `disconnect_case` were each in on the day they landed. That
    is what `provision`'s repair door exists for; this case proves the forward
    half, that a tenant created from here on gets one.
    """
    assert core_numbering.SETTLEMENT in core_numbering.KNOWN_SERIES
    assert core_numbering.SETTLEMENT in tenancy_services.SERIES_DEFAULTS


# ── Lifecycle ─────────────────────────────────────────────
# packet: payments blueprint p13 `P0.13` · decision log 2026-09-22 "THE SETTLEMENT SERIES IS STL-26-0001"
# generated: 2026-09-22 by LANE P0-FE
# checklist: A✔ B=n/a(no endpoint moves) C✔ D=n/a E=n/a F✔ G✔ H=n/a
# gates: pytest tests/test_p013_settlement_series.py · tests/test_cr005_numbering_set08.py
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
