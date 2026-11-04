"""identity 0016 — `activation_code_register`: one platform-wide list of every activation code.

`DEF-FLD-10580` (beta report MQ-006, `CR-187-BRC10`), PO 2026-10-24, verbatim:
*"A. The code from the office sets the utility (recommended) - this is correct
option , but how will you ensure the code is always unique?"* — answered by the
design in the decision log of that date (*"MQ-006: THE CODE FROM THE OFFICE SETS
THE UTILITY"*), which the PO confirmed: every code ever issued recorded in ONE
platform-wide register with a DATABASE UNIQUE constraint; a code is never reused;
only a keyed hash is stored.

HUMAN-OWNED (🔒 identity/credentials and 🔒 migration ordering — and the table
decides WHICH UTILITY a phone talks to). HUMAN-REVIEW-PENDING — AI-authored
2026-10-24 under the PO ruling of 2026-08-09 (*"AI will do it; we will review it
later as human"*); its row is in `12-governance/09-human-review-ledger.md`
(*"MQ-006 (a)"*, 2026-10-24). Not RATIFIED without a recorded sign-off.

⚠ **DELIBERATELY NO `ENABLE`/`FORCE ROW LEVEL SECURITY`.** The lookup happens
before any utility is open — the phone knows only the code — so a tenant policy
would answer zero rows for a perfectly valid code (CLAUDE.md law 7, *incapable
of passing*). This is `integration_key_directory`'s class (`integrations/0011`
carries the long form of the argument) and the exemption is DECLARED in three
places that are checked against each other: `core.rls_guard.
TENANT_TABLE_EXEMPTIONS` (the server refuses to start on PostgreSQL otherwise),
`tests/isolation_helpers.RLS_EXEMPT_TABLES` (`test_g5_the_rls_exempt_list_is_
exactly_what_b2_declares`) and B2 §3.

**What it holds is why that is safe:** an HMAC digest of the code under the
server secret, the utility's id and a timestamp — no code, no user, no name.
**And it authorises nothing:** `native.lookup_activation_code` reads the
tenant's own `activation_codes` row afterwards, under that tenant's RLS
context, and answers only for a live one.

NO BACKFILL. Codes already issued are stored per tenant as a TENANT-keyed HMAC
(`identity/0011`), which cannot be turned into this table's platform-keyed
digest without the plaintext, and the plaintext is never stored. Such a code
still works on the tenant door (`/api/{tenant}/auth/activation/check`) and is
simply not findable by the utility-free door; the office issues a new one
(Settings › Users › New app code). Codes live seven days, so the gap closes by
itself within a week.

Depends on `identity/0015` only: no FK, so nothing else is needed.
"""

from django.db import migrations, models

import core.dbfields


class Migration(migrations.Migration):

    dependencies = [
        ("identity", "0015_field_app_pins"),
    ]

    operations = [
        migrations.CreateModel(
            name="ActivationCodeRegister",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=core.dbfields.uuid7,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                ("code_digest", models.CharField(max_length=64)),
                ("tenant_id", models.UUIDField()),
                ("created_at", models.DateTimeField()),
            ],
            options={"db_table": "activation_code_register"},
        ),
        migrations.AddConstraint(
            model_name="activationcoderegister",
            constraint=models.UniqueConstraint(
                fields=["code_digest"], name="uq_activation_code_register_digest"
            ),
        ),
    ]
