# ── Trace ──────────────────────────────────────────────
# Change:   CR-085 blueprint specification CPB-10 — *"Equipment says whose it is
#           and what it costs"*. Screen 52, `/:tenant/portal/equipment`, whose
#           stated question is *"what is installed at my address, whose is it,
#           and what am I paying for it?"* — and whose table today draws
#           `Equipment · Reference · Installed · Status`, answering one third of
#           it. The drawing's table is `Equipment · Reference · Installed ·
#           Whose · Monthly`.
# Rules:    BR-AST-031 (a behaviour CLASS is the fact, the tenant's label is
#           editable — the same shape `maintained_by` takes) · BR-RAT-090 (an
#           unmetered service's quantity is a COUNT of its assets on the unit) ·
#           CLAUDE.md hard rule 2 (money stored 4, displayed 2) · B14 rule 31
#           (no database id) · rule 35 (the catalogue writes the words)
# Why the   ⚠ **NO PRICE COLUMN IS ADDED ANYWHERE.** `BR-MET-067` is explicit
# charge is  that a price on an equipment or size-class lookup would be *"a
# read from  second, unsigned rating input beside the signed one"* and that
# the bill:  size-based base charges are *"a Plans & Rates change with a finance
#            re-sign, never a column added here"*. So the monthly figure is the
#            customer's OWN LATEST BILL's line for that service — the same
#            discipline CPB-08 states in its own words: *"the figure is the
#            bill's own line, not a re-calculation."*
# ───────────────────────────────────────────────────────
"""Whose the kit is, and what the bill actually charged for it."""

from __future__ import annotations


def test_cpb10_tc1__an_asset_type_declares_who_maintains_it():
    """`maintained_by` is a COLUMN and not a shape read off `category`.

    ⚠ **THE `DEF-CWP-3765` LESSON, APPLIED BEFORE IT COSTS ANYTHING** — *"when a
    model has an exact column for a fact, read the column; a shape that implies
    it is a rule in disguise, and rules move."* `category` partitions the S49
    tabs (`meters` · `sub_meters` · `behind_the_meter`) and it is TEMPTING to
    read *behind the meter, therefore the customer's* off it. That is a rule
    wearing a taxonomy: a utility that owns the battery it installed would then
    be told it is the customer's, on the customer's own screen, with no way to
    say otherwise.
    """
    from apps.assets import models

    field = models.AssetType._meta.get_field("maintained_by")
    assert field.null is False
    # `utility` · `customer`. A CODE the catalogue turns into *Ours* / *Yours*
    # (B14 rule 35) — never English from a server.
    assert field.default == "utility"


def test_cpb10_tc2__the_seed_defaults_to_the_utility_and_behind_the_meter_to_the_customer():
    """The seeded default is derived ONCE, at migration time, from `category` —
    which is the honest use of that shape: a starting value a tenant may change,
    rather than a rule read live on every render."""
    from apps.assets import equipment_reads

    assert equipment_reads.SEEDED_MAINTAINED_BY["meters"] == "utility"
    assert equipment_reads.SEEDED_MAINTAINED_BY["sub_meters"] == "utility"
    assert equipment_reads.SEEDED_MAINTAINED_BY["behind_the_meter"] == "customer"


def test_cpb10_tc3__a_metered_services_asset_carries_no_monthly_charge_of_its_own():
    """A water meter is not charged for; the WATER is. The distinction is read
    from `tenant_services.billing_basis` — an existing column — and never
    guessed from the kind of thing the asset is."""
    from apps.portal import selectors

    assert selectors._asset_charge_basis("metered") == "usage_only"
    assert selectors._asset_charge_basis("share") == "usage_only"
    assert selectors._asset_charge_basis("capacity") == "per_item"


def test_cpb10_tc4__the_per_item_figure_is_the_bills_own_rate_and_never_amount_over_count():
    """`BR-RAT-090`: an unmetered service's quantity is a COUNT of its assets,
    so the bill line for two carts reads `2 × $12.00 = $24.00`. The per-item
    figure a customer wants is the RATE — which the bill already carries — and
    NOT `amount ÷ quantity`, which would be this screen doing arithmetic the
    bill has already done and could disagree with it by a cent."""
    from apps.portal.seams import billing_seam

    line = {"quantity": "2.000000", "unit_price": "12.0000", "amount": "24.0000"}
    assert billing_seam.per_item_monthly(line) == "12.00"
    # A line with no rate has no per-item answer — and `24.00 ÷ 2` is NOT
    # substituted, because a figure this screen computed is a second answer to a
    # question the bill already answered.
    assert billing_seam.per_item_monthly({"quantity": "2.000000", "amount": "24.0000"}) is None
