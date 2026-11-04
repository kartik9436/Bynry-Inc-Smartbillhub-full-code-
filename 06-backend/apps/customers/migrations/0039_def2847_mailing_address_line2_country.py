# ── Trace ──────────────────────────────────────────────
# Defect:  DEF-2847 (2026-08-31) — THE ACCOUNT'S MAILING ADDRESS HAS NO LINE 2
#          AND NO COUNTRY COLUMN, SO TWO OF THE PRINT MANIFEST'S NINE ADDRESS
#          FIELDS CAN ONLY EVER BE EMPTY. `customers.addresses` declares
#          line1/city/state/postal_code and was never revisited against what a
#          mailed piece requires. DEF-2703 filed the same shape one table over
#          (premises, service_requests) and did NOT name this table — the one a
#          bill is actually posted from.
# Rules:   BR-NOT-029 clause (a) — a manifest address is written from DISCRETE
#          columns and NEVER assembled from or split out of one field ·
#          clause (b) — city, state and postal code are the mandatory three, and
#          neither of these two is among them, so neither holds a bill ·
#          BR-CUS-674 (PO 2026-08-31, *"we cannot make chnges until account
#          confirm it"*) — an address changes when the account holder says so ·
#          CLAUDE.md rule 1 (tenant scoping) · hard rule 4 (nothing issued is
#          rewritten — no invoice, line, payment or journal row is touched)
# Tests:   06-backend/tests/test_def2847_mailing_address_columns.py
# Impacts: apps/customers/models.Address · selectors.mailing_address_for_account
#          · apps/billing/customers_seam.MailingAddress · apps/billing/print_set
# ───────────────────────────────────────────────────────
"""customers 0039 — `addresses` gains `line2` and `country`, both nullable, and
NOTHING is backfilled.

⚠ **THIS WAS ALLOCATED AS `0038` AND HAD TO RENUMBER AT PUSH TIME — the same
mechanism as `DEF-1787` / `DEF-2711`, for the third recorded time on this table.**
The `CR-056` W2b lane took `0038` for `0038_cr056_w2b_company_tax_id` from its
own worktree while this one was working; both lanes computed the next free number
correctly and both got the same one, because `file_defect.py` and a directory
listing can only see the PUSHED world plus your own checkout. Re-derived from the
branch tip at push time — the content AND the ids in one act (law 11) — and moved
to `0039`, depending on `0038_cr056_w2b_company_tax_id`, the real leaf.

🔒 HUMAN-OWNED · HUMAN-REVIEW-PENDING — migration ordering is on CLAUDE.md's
sensitive-paths list. AI-authored under the PO ruling of 2026-08-09 (*"AI will
do it; we will review it later as human"*). The row in
`12-governance/09-human-review-ledger.md` states in plain English, with the
figure, what a reviewer is being asked to agree to.

════════════════════════════════════════════════════════════════════════════
THE PRODUCT ACCEPTED A PROMISE IT COULD NOT KEEP
════════════════════════════════════════════════════════════════════════════
`BR-NOT-029` ruled a fourteen-column print manifest, nine of whose columns are
the address. Two of those nine — `address_line_2` and `country` — have no column
anywhere in this product, so the hand-over file emits them EMPTY on every single
row and says so in its own README. Every layer between the table and the file
was already written to carry them: `mailing_address_for_account` returns them as
literal `None` with a comment saying they are not columns,
`billing.customers_seam.MailingAddress` declares them as fields, and
`print_set` writes `address.line2 or ""`. **The only thing missing was the two
columns**, and until CR-053 task 13 nothing had ever asked for a fifth or a
ninth address field, so no test could fail: four populated columns are a valid
address row.

════════════════════════════════════════════════════════════════════════════
NULLABLE, AND NOTHING IS BACKFILLED — THAT IS THE WHOLE OF THE CAUTION
════════════════════════════════════════════════════════════════════════════
`DEF-2847`'s own prevention names the shape: *"add line2 and country to
customers.addresses going forward, leave existing rows to a clerk rather than a
parser."*

**No value is derived for an existing row, and there are two separate reasons,
each sufficient on its own.**

**Line 2 may not be carved out of line 1.** `BR-NOT-029` clause (a) forbids it in
as many words — *"splitting an address is guessing, and a guessed address is mail
delivered to the wrong house"*. A backfill that split `"1408 Elm St Apt 3B"` on
the last token would be exactly that operation, run once, silently, over every
customer.

**Country may not be taken from `TenantSettings.country`.** That is the
UTILITY's own regional setting. Writing it onto a customer's address asserts
where a PERSON LIVES from a fact about US — and it is wrong for precisely the
customers it matters for, the ones who have moved away and still receive a bill.

So both columns arrive NULL on every existing row, and NULL here means *nobody
has told us*, which is true. The manifest keeps emitting them empty for those
rows and keeps saying why in its README; the difference is that from today a
clerk who is told a second line CAN record it, and before today there was
nowhere to put it.

════════════════════════════════════════════════════════════════════════════
WHY THIS DOES NOT HOLD A SINGLE EXTRA BILL
════════════════════════════════════════════════════════════════════════════
`BR-NOT-029` clause (b) makes city, state and postal code mandatory and a bill
missing any of them is held out of the print file. **Neither new column is on
that list**, and `selectors.REQUIRED_ADDRESS_PARTS` is untouched by this change,
so the held/printed split is byte-identical before and after: on the seeded
utility, 93 issued bills gave 93 PDFs and 0 held, and it still does.

════════════════════════════════════════════════════════════════════════════
WHAT THIS DELIBERATELY DOES NOT DO
════════════════════════════════════════════════════════════════════════════
* **It does not touch `premises` or `service_requests`.** `DEF-2703`'s half —
  a free-text `billing_address_as_given` blob and nullable premises columns —
  is a different table, a different capture path and a different decision. This
  migration closes the table a bill is POSTED from and leaves that row open
  rather than quietly widening its scope.
* **It adds no country to any other table**, and it does not make `country` a
  lookup or an enum. A two-letter code, a name and a nullable free-text column
  are three different decisions; the mail house is handed what the customer
  told us, which is what clause (a) asks for.
* **It writes nothing.** `BR-CUS-674` runs one direction: a mailer's answer
  about where somebody now lives never reaches an account. `G60` enforces that
  absence and this migration gives it nothing new to guard.
"""
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("customers", "0038_cr056_w2b_company_tax_id"),
    ]

    operations = [
        migrations.AddField(
            model_name="address",
            name="line2",
            field=models.TextField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="address",
            name="country",
            field=models.TextField(blank=True, null=True),
        ),
    ]
