# ── Trace ──────────────────────────────────────────────
# Change:  CR-046 C4/C5 — the account keeps the utility's OWN number as its
#          `account_no` (the one target of six that does not call Settings ›
#          Numbering) and gains a column for the legacy reference the file also
#          carries.   Screens: WFL-01 accounts import (stages 1–5),
#          S17 Accounts, S21 account detail
#          ⚠ THIS LINE SAID "issued from the tenant's `account` series" UNTIL
#          2026-08-27 (CR-046 wave H, DEF-1781). The PO REVERSED that clause
#          eleven hours after it was built — "we use utility provdied account
#          number here - we dont create our own number" — and the reversal
#          reached the rule row's body, this file's own docstring and the built
#          rule (ACC.NUMBER_REQUIRED) while three HEADLINES kept the old claim.
# Rules:   BR-CUS-172 (new — the utility's own ACCOUNT reference, unique per
#          tenant, case-insensitive, partial; ⚠ RENUMBERED FROM BR-CUS-171 on
#          2026-08-27, CR-046 wave H3 / DEF-1780 — that id was minted twice in
#          one day, for this rule and for the master/child link, and G17 was RED
#          on it. The master/child rule keeps 171) · BR-CUS-054 (the CUSTOMER's
#          legacy id — a DIFFERENT fact on a DIFFERENT table; see below) ·
#          BR-CUS-017 (one live account per unit — why a duplicate load is a
#          pile of refusals rather than a pile of duplicates) · GT-16 ❄️
#          (the opening batch, posted once; hard rule 4 forbids re-posting it)
# Tests:   06-backend/tests/test_cr046_identifiers.py
# Impacts: apps/customers/services.py (`create_from_import` ·
#          `update_from_import` · IMPORT_ACCOUNT_FIELDS) · selectors
#          (`account_import_index`) · apps/metering/import_runs.py (the accounts
#          target's match key and template column) · import_rules.py
# ───────────────────────────────────────────────────────
"""customers 0033 — `accounts.external_ref` (BR-CUS-172), and DEF-1660 with it.

HUMAN-OWNED (migration ordering 🔒). HUMAN-REVIEW-PENDING — AI-authored
2026-08-27 under the PO ruling of 2026-08-09 ("AI will do it; we will review it
later as human"). Row in 12-governance/09-human-review-ledger.md.

⚠ **READ THIS FIRST, BECAUSE CR-046 SAYS THE OPPOSITE.** The change request's
C4 task carries a warning: *"Read `BR-CUS-054`'s `external_ref` first — accounts
already have the legacy-reference column this change gives the other three"*,
and its C5 task adds *"so C5 may be a no-op there"*. **It is not a no-op. The
warning is a misreading and the check CR-046 itself asked for is what found it.**

`BR-CUS-054`'s `external_ref` is a column on **`customers`** — the PERSON. This
is the **`accounts`** table. They are different rows and different facts:

    one landlord            → 1 customer row  → 1 `customers.external_ref`
    fourteen of their units → 14 account rows → 14 legacy ACCOUNT numbers

Fourteen values do not fit in one column, so under the ruling that takes
`account_no` off the file, thirteen of them would simply be lost.

**AND THE COLUMN WAS ALREADY BEING ASKED FOR (`DEF-1660`).** The accounts import
template has offered `External reference` since CR-030 W1, with the aliases
`legacy_key`, `external_ref`, `external reference`, `legacy id`. It auto-mapped,
stage 2 reported `Matched` — and `_account_payload_from` dropped the value
deliberately, with a comment saying it belongs to the customer. Nothing wrote it
anywhere. Hard-won law 2, exactly: mapped, wired to nothing, every test green.

**THE UNIQUE IS PARTIAL AND CASE-INSENSITIVE** for `customers.external_ref`'s
stated reasons: an account opened by the S18 wizard has no legacy reference and
N NULLs must coexist, and `CIVIC-9931` / `civic-9931` are one account in every
legacy export.

One nullable TEXT column plus one partial unique index. **No backfill** — every
existing row keeps NULL. Rollback is a clean drop of both, and nothing reads the
column until the import writes it.
"""

from django.db import migrations, models
from django.db.models import F, Q
from django.db.models.functions import Lower


class Migration(migrations.Migration):
    dependencies = [
        ("customers", "0032_def724_close_out"),
    ]

    operations = [
        migrations.AddField(
            model_name="account",
            name="external_ref",
            field=models.TextField(blank=True, null=True),
        ),
        migrations.AddConstraint(
            model_name="account",
            constraint=models.UniqueConstraint(
                F("tenant"),
                Lower("external_ref"),
                condition=Q(external_ref__isnull=False),
                name="uq_accounts_tenant_external_ref_ci",
            ),
        ),
    ]
