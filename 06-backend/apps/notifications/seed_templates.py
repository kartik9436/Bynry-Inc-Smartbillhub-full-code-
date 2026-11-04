# ── Trace ──────────────────────────────────────────────
# Story:    US-NOT-005 (the merge-variable catalogs these bodies are validated
#           against) · US-NOT-006 (the version lifecycle these rows join) ·
#           US-NOT-009 (the disconnect notice this seeder deliberately does NOT
#           plant) · US-NOT-010 (the reminder it does)
#           Screens: S8 → Notifications (the templates card that reports it)
# Rules:    BR-NOT-001 (a `default` fallback variant is MANDATORY — this is the
#           thing that creates it) · BR-NOT-006 (type × category × language;
#           the seed writes the `(default, default)` variant and nothing else) ·
#           BR-BIL-026 (a version is append-only and a document pins the exact
#           version it rendered from) · BR-BIL-027 (publishing is the System
#           Admin's right — see WHY THIS DOES NOT CALL `publish` below) ·
#           BR-TEN-013 (tenancy reaches this module only through a named seam) ·
#           BR-TEN-043 (the business date is the caller's; no clock here) ·
#           CLAUDE.md rule 1 (tenant scoping) · rule 7 (audited)
# Tests:    06-backend/tests/test_def_163_notice_templates_seeded.py ·
#           06-backend/tests/test_cr011_contract_templates.py (the four
#           CONTRACT defaults — offered, not seeded, CR-011 item 9)
# Impacts:  apps/notifications/services.seed_notice_templates (the seam name) ·
#           apps/tenancy/seams.seed_notice_templates ·
#           apps/tenancy/services._provision_inside_context ·
#           apps/tenancy/management/commands/seed_demo.py (the repair door) ·
#           10-scripts/gates/required_rows.txt (G26)
# ───────────────────────────────────────────────────────
"""DEF-163 — **the notice templates a tenant has never had, planted at signup.**

HUMAN-OWNED · HUMAN-REVIEW-PENDING — this file decides **the words a customer
reads**, which is the same authority `template_service.py` is guarded for one
step earlier (*"decides WHICH body a customer's document renders from"*). It is
in `10-scripts/gates/human_owned.txt` and carries a row in
12-governance/09-human-review-ledger.md. AI-authored 2026-08-16 under the PO
ruling of 2026-08-09: *"AI will do it; we will review it later as human."*

⚠ **AMENDED 2026-08-17 — AND THE AMENDMENT REVERSES THIS FILE'S CENTRAL CLAIM,
SO IT IS AT THE TOP RATHER THAN IN A TRAILER.** Until today this paragraph read
*"Nothing here is authored prose — both bodies are quoted from A13"*, and the
banner below read *"THIS FILE PLANTS ONLY BODIES A SIGNED SPEC WRITES IN FULL."*
**Twenty-nine authored bodies now sit in this file** and neither sentence is true
any more. They are here because the PO ruled it TWICE on 2026-08-17, in these
words:

  > *"One gap: 34 of 36 template types have no content, so the email subject
  > line and SMS counter you asked for have never rendered for anyone. -
  > **please define it for this product**"* — PO, 2026-08-17 (CR-007, DEF-210)

and, later the same day, for the three the first ruling deliberately did not
reach — the disconnection notices, whose rights footer this file had refused to
invent under BR-NOT-015:

  > *"we will take this option; we provide default option for all 5 you ahve
  > mentioned; if Utility wants to over ride it let them do it; I can also give
  > tick boxes if required to add 5"* … *"you build default langauge and let
  > Utility user change it as they want"* — PO, 2026-08-17 (CR-007)

**BR-NOT-015 IS SATISFIED BY THAT SECOND RULING, NOT BROKEN BY IT.** Its
*"must not be invented"* fixed ownership of the five sentences and left it
unassigned; the PO has now assigned it to the platform, so the sentences are
authored to an instruction and are the PO's to approve. They live in
`apps/notifications/rights_footer.py`, are switchable and overridable per clause
by a tenant's System Admin, and every screen that shows one marks it AS a
default: **a default is a starting point and this platform warrants nothing
against anybody's regulator.**

**What that changes for the human review of this file:** it used to have ONE
question — *do the two quotes match A13* — which a test can answer mechanically.
It now has TWO, and the second is the one only a person can answer: **is this
wording right for a small utility to send to its own customers?** The quoted and
the authored bodies are kept in separate, labelled sections and carry different
`source` strings so a reviewer can see at a glance which is which.

╔══════════════════════════════════════════════════════════════════════════╗
║  TWO SECTIONS, TWO STANDARDS OF PROOF:                                   ║
║   · QUOTED  — dunning + receipt, character-for-character from A13, and a  ║
║     test asserts them against the spec FILE. Unchanged since 2026-08-16.  ║
║   · AUTHORED — twenty-nine bodies written 2026-08-17 under the ruling     ║
║     above. Every token is proved to be in its class's palette, every SMS  ║
║     is proved under 160 characters, no body may name `{utility_logo}`,    ║
║     and no body states a figure, fee, deadline or right that is not       ║
║     already ruled somewhere in this repo.                                 ║
║   · THREE OF THE TWENTY-NINE ARE THE DISCONNECT TIERS, added later the    ║
║     same day under a SECOND ruling (CR-007) and part-quoted from A19 §2.  ║
║   · FOUR CONTRACTS ARE OFFERED AND NOT PUBLISHED ([AMENDED 2026-08-18,    ║
║     CR-011 item 9]: this line read "FOUR CLASSES ARE STILL EMPTY").       ║
║     They HAVE wording now — the PO ruled "provide default and allow user  ║
║     to change" — and none of it is seeded, because BR-NOT-002 makes a     ║
║     contract version effective-dated and that date is a human's choice.   ║
║     One of the four is a PLACEHOLDER the renderer refuses on purpose.     ║
╚══════════════════════════════════════════════════════════════════════════╝

**THE DEFECT, VERBATIM (DEF-163):** *"NO TENANT HAS EVER HAD A NOTICE TEMPLATE,
so every disconnect notice and every dunning letter this product tries to
generate is REFUSED rather than queued."*

`notification_templates` / `notification_template_versions` landed on 2026-08-15
with `template_service` implementing register → save_draft → publish → archive
in full and its own tests passing — **against rows the TESTS create.** In the
product no row was ever written: there is no designer (S91–S96 were CUT by the
PO on 2026-08-16), no migration plants one, and `apps/tenancy/services.py`
seeded the chart of accounts, the number series, the holidays and billing's
fallback bill template and nothing else. So `template_service.resolve` refused
*"no published 'dunning' template resolves for category 'default' in language
'default'"* for EVERY class on EVERY tenant, and `notices.generate_reminder` /
`generate_disconnect_notice` refused rather than queueing. That is hard-won law
2 — *built is not wired* — applied to DATA, one module along from DEF-123.

────────────────────────────────────────────────────────────────────────────
WHAT IS PLANTED — THIRTY-THREE OF THIRTY-SEVEN, AND WHY NOT THIRTY-SEVEN
────────────────────────────────────────────────────────────────────────────
⚠ **REWRITTEN TWICE ON 2026-08-17, AND AGAIN 2026-08-18.** This section once
explained why the list was TWO; the *"define it for this product"* ruling raised
it to twenty-eight; CR-007's disconnect ruling to thirty-one; the in-app lane's
`staff_bulk_summary` made it thirty-two (of a catalog grown to thirty-seven);
and C-14's plan-void ruling makes it thirty-three. The four that remain are the
interesting part — because none of them is missing for want of an author.

  · **2 QUOTED** — `dunning` and `receipt`, character-for-character from A13's
    *"Reminder / notice templates (previews)"* block. US-NOT-005 §1 names A13 as
    those classes' token source, and a test asserts them against the spec file.
  · **26 AUTHORED** — 4 SMS, 19 email and 3 print, written here under the
    2026-08-17 ruling. Each carries `_PO_AUTHORED` as its `source` so nobody
    mistakes it for a quote.
  · **3 PART-QUOTED, PART-AUTHORED** — BR-NOT-014's three disconnect tiers,
    added under CR-007's later ruling the same day. Each carries A19 §2's tier
    sentence VERBATIM (a test asserts it character for character) inside a letter
    authored here, and each carries `{rights_footer}` as non-removable class
    content beside `{state_puc_ref}`. They hold `_TIER_AUTHORED` as their
    `source`, distinct from the other twenty-six, because a human review of this
    file has to be able to see which half of a regulated letter is signed.
  · **1 AUTHORED UNDER ITS OWN RULING (2026-08-18)** — `plan_notice_void`,
    C-14 verbatim: *"you give default language for the plan-void notice only -
    we wil allow utility to make the changes"*. It carries
    `_PLAN_VOID_AUTHORED` as its `source` because it is wording for an event
    NOTHING FIRES: the 'nodrop' ruling stands and no writer voids a plan —
    wording ahead of the flow, the posture the PO ratified 2026-08-16. (Until
    C-14 this class sat in the empty list below with *"there is no event left
    to announce … OQ-260 asks whether to withdraw the class"* — the PO kept it
    and gave it words instead.)
  · **4 OFFERED AND NOT PUBLISHED — rewritten 2026-08-18 (CR-011 item 9), and
    the OLD sentence is worth keeping because it is what changed.** It read:
    *"4 STILL EMPTY, and each is empty for a reason a body cannot fix … the four
    contracts → documents somebody SIGNS, not notices they read … their TYPE is
    ratified and their terms are the utility's own or a payment scheme's."* The
    PO reversed it in one sentence — *"the 4 template classes needing legal
    wording - already answer - provide default and allow user to change"* — and
    all four now have platform wording in `CONTRACT_DEFAULTS`.

    **They are still not in `SEEDABLE`, and that is BR-NOT-002 rather than a
    refusal.** A contract version is EFFECTIVE-DATED; `template_service.
    save_draft` refuses a contract draft with no `effective_from`; and the CR
    keeps that standing over its own ruling — *"a draft still needs an
    `effective_from` a human chooses; provisioning-day is not that date."* So the
    wording is OFFERED on the designer and the System Admin publishes it with
    their date. Seeding it undated would be worse than not seeding it: an undated
    published version WINS over every dated one in
    `template_service._published_version`, so the platform's body would shadow
    the utility's own forever.

    · `contract_service_agreement` · `contract_deposit` ·
      `contract_payment_plan` → real default wording, editable, stating no figure
      or period this repo has not ruled.
    · `contract_autopay_authorization` → **a PLACEHOLDER, deliberately**, which
      `rendering.render` REFUSES while its marker is in it (PO: *"Do it; put the
      details, I will handle it with user"*). Its wording is NACHA's and not
      ours; what the utility must supply is enumerated in plain English in
      `catalogs.CONTRACT_INPUT_REQUIREMENTS` and printed on the document's face.

**NOTHING HERE INVENTS A FIGURE, A FEE, A DEADLINE OR A RIGHT.** That is the
rule the authoring ran under and it is what the remaining absences are made of: a
10-day regulated disconnection notice is a legal document at real postage, and
inventing its rights paragraph would put words in a utility's mouth that look
official the moment they are written. Prototype r10's `$25 NSF fee`, `$60
reconnect fee`, `retry within 5 days`, `refunded after 12 months`, `within 14
days`, `allow 3–5 business days`, `mailed 60 days ahead` and `PUC rule 25.29`
are sample prose for a fictional utility and appear in no body in this file.

────────────────────────────────────────────────────────────────────────────
WHY IT WRITES A PUBLISHED VERSION DIRECTLY RATHER THAN save_draft + publish
────────────────────────────────────────────────────────────────────────────
Exactly billing's reasoning in `templates_service.seed_platform_default`, and
for the same rule: `publish` is BR-BIL-027's narrow right and its check is
server-side on the actor's ROLE. There is no human in a provisioning
transaction, so routing the seed through it would mean minting a synthetic actor
carrying a role nobody granted — which is the invention `publish` exists to
refuse. The seed writes its own rows and **says so in the audit trail**
(`source: provisioning_seed`), the posture `seed_chart_of_accounts` and
`seed_platform_default` already take.

**BR-BIL-026 IS NOT WEAKENED BY THAT.** The row is written `published` because
only a published version resolves; `uq_ntv_one_published_undated` still governs
one-published-per-variant; and migration 0006's trigger refuses a non-draft
DELETE the instant the row exists — a seeded version is as un-editable as any
other.

**BUT THE BODY IS STILL VALIDATED.** `rendering.validate_body` runs on every
body before it is written, which is the one check that cannot be skipped: it
proves the seeded body is one the tenant's own designer would have accepted —
same palette, same mandatory content, same `{usage}`-needs-`{unit}` rule. A
platform body that could not be re-saved through the ordinary door would be a
special case living inside a customer-facing document.

────────────────────────────────────────────────────────────────────────────
INSERT-MISSING, SO A RE-RUN IS A REPAIR RUN
────────────────────────────────────────────────────────────────────────────
A variant that already has a published version is LEFT ALONE, reported as
`already_present`. This is what makes the repair door safe: `manage.py
seed_demo --tenant <subdomain>` can be run on any tenant, at any time, without
overwriting a body somebody edited — and **a provisioning-time change reaches a
tenant when it is created and never afterwards** (hard-won law 4 in its data
form), so the repair door is not optional. Every tenant provisioned before
2026-08-16 has no notice template and stays unable to send one until it is run.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

from django.db import transaction

from apps.notifications import (
    account_access_wording,
    agreement_wording,
    bill_email_wording,
    catalogs,
    correction_reason_wording,
    move_out_wording,
    rendering,
    service_state_wording,
)
from apps.notifications import template_models as tm
from apps.notifications import past_due_letter_wording  # DEF-PAY-10651
from apps.notifications import payment_returned_wording  # DEF-PAY-10744
from core import audit, errors
from core import tenancy as core_tenancy

#: Hard rule 7 — `entity.action`, the same dotted actions `template_service`
#: writes, so a seeded row and a human-published row group together on any
#: audit read rather than needing two queries.
AUDIT_ENTITY_TEMPLATE = "notification_template"
AUDIT_ENTITY_VERSION = "notification_template_version"
AUDIT_REGISTERED = "template.registered"
AUDIT_PUBLISHED = "template.published"

#: What the audit row says instead of naming a person. There is no human in a
#: provisioning transaction and `created_by` / `published_by` are left NULL for
#: the same reason billing leaves them NULL: writing the owner's id there would
#: claim somebody authorised a page they have never seen.
SEED_SOURCE = "provisioning_seed"


# ══════════════════════════════════════════════════════════════════════════
# THE BODIES. QUOTED, NEVER COMPOSED.
# ══════════════════════════════════════════════════════════════════════════
# Both are A13 §"Reminder / notice templates (previews)", character for
# character including the punctuation. A13's own cardinal rule is *"anything not
# determinable from the UI is «UNKNOWN — <question>», never invented"*, and
# US-NOT-005 §1 names A13 as the token source for exactly these two classes.
#
# ⚠ THE TEST ASSERTS THESE STRINGS AGAINST THE SPEC FILE ITSELF, so an edit here
# that "improves" the wording goes RED rather than quietly reaching a customer.

#: A13 line 45, verbatim. `{first_name}` `{account}` `{balance}` ∈ catalogs.dunning.
DUNNING_BODY = (
    "Hi {first_name}, this is a friendly reminder that your account {account} has a "
    "balance of {balance}. You can pay online at any time. Thanks for being a customer."
)

#: A13 line 47, verbatim. Every token ∈ catalogs.receipt.
RECEIPT_BODY = (
    "Thanks {first_name}! We received your payment of {amount} on {date}. Your new "
    "balance is {balance}. Confirmation {confirmation}."
)


# ══════════════════════════════════════════════════════════════════════════
# THE AUTHORED BODIES — PO RULING 2026-08-17, *"please define it for this
# product"* (CR-007, DEF-210)
# ══════════════════════════════════════════════════════════════════════════
# **THE TWO ABOVE ARE QUOTED. THE TWENTY-SIX BELOW ARE AUTHORED, AND THE
# DIFFERENCE IS DELIBERATELY VISIBLE** — different section, different `source`
# string, and the module docstring's old claim (*"nothing here is authored
# prose"*) is amended rather than quietly broken. A human review of this file
# now has two questions instead of one: *do the quotes match the spec* (a
# mechanical check a test performs) and *is this wording right for a small
# utility to send* (a judgement only a person makes).
#
# **WHY AUTHORING IS ALLOWED HERE NOW.** The CR-007 walkthrough put the gap to
# the PO in plain English — *"34 of 36 template types have no content, so the
# email subject line and SMS counter you asked for have never rendered for
# anyone"* — and the ruling, verbatim, was **"please define it for this
# product"**. That is the delegation this section runs on. It is recorded in
# 12-governance/11-change-requests.md §"CR-007 — PO RULINGS 2026-08-17".
#
# **THE FIVE CONSTRAINTS THE RULING CAME WITH, AND HOW EACH IS ENFORCED:**
#   1. every token is in its class's own palette → `rendering.validate_body`
#      runs on every body before it is written, as it always has;
#   2. **no body may use `{utility_logo}`** (DEF-195 — the context supplies no
#      value, so it prints `——` on a customer's letter) → no authored palette
#      offers it AND a test asserts no authored body mentions it;
#   3. **every SMS body under 160 characters** → measured, not estimated, by
#      `tests/test_def_210_authored_template_bodies.py`;
#   4. **no figure, fee, deadline, notice period or legal right that is not
#      already ruled** → prototype r10's `$25 NSF fee`, `retry within 5 days`,
#      `$60 reconnect fee`, `refunded after 12 months`, `within 14 days`,
#      `3–5 business days`, `mailed 60 days ahead` and `PUC rule 25.29` are ALL
#      absent from every body here. Where a real notice needs one, the class
#      carries a token for it or the clause is left out (OQ-260);
#   5. **English only** — these are tenant-EDITABLE content, not UI strings.
#      Ten machine translations of thirty-six documents would ship worse text
#      than an English default a utility overwrites in its own words, and
#      BR-NOT-006's language variants are exactly the door for a tenant that
#      wants another one. A Spanish default is a translation job with a human
#      on it, not a seeding job.
#
# **VOICE.** Short sentences, no jargon, a small utility's voice rather than a
# bank's — the PO's product, where one or two people know their customers by
# name. Where prototype r10 covers a class its STRUCTURE and TONE are followed
# (it is the design handover and it is better than inventing); its figures,
# names and regulator references never are, because they are sample data for a
# fictional utility.

# ── SMS · four bodies, every one measured ────────────────────────────────
# No masthead, no subject, no sign-off: every character is one of 160.

SMS_BILL_READY_BODY = (
    "{utility_name}: your new bill is ready. {total_due} due {due_date}. "
    "View or pay at {utility_website}."
)

SMS_PAST_DUE_BODY = (
    "{utility_name}: your balance of {balance} is past due. Pay at {utility_website} "
    "or call {support_phone}. Already paid? Thank you."
)

SMS_PAYMENT_RECEIVED_BODY = (
    "{utility_name}: thanks, we received {amount}. Confirmation {confirmation}. "
    "Your balance is now {balance}."
)

#: A19 rule 3: this SUPPLEMENTS the mailed notice and never replaces it. It
#: therefore carries no rights footer — that belongs to the three PRINTED tiers,
#: which carry `{rights_footer}` as non-removable class content (CR-007).
SMS_DISCONNECT_BODY = (
    "{utility_name}: service is scheduled to stop on {cut_date}. Pay {balance} or "
    "call {support_phone} today. A letter is on its way."
)

# ── Email · a subject and a body each ────────────────────────────────────

# DEF-BIL-10531 (PO 2026-10-22, *"b direct PDF link"*) — "it is attached to
# this email" was false (nothing is attached) and is replaced by a link line.
# The wording lives in `bill_email_wording`, one variant per language; this is
# its `default` (`en`). `notifications/0030` republishes it wherever a utility
# had not edited the old one.
EMAIL_BILL_READY_SUBJECT, EMAIL_BILL_READY_BODY = bill_email_wording.WORDING[
    bill_email_wording.BILL_READY
][bill_email_wording.DEFAULT_WORDING_LANGUAGE]

EMAIL_STATEMENT_SUBJECT = "Your {utility_name} statement, {period_start} to {period_end}"
EMAIL_STATEMENT_BODY = """Hi {first_name},

Here is your account statement for {service_address}, covering {period_start} to
{period_end}.

Opening balance {opening_balance}
Closing balance {closing_balance}

This is a summary of what has happened on your account. It is not a bill, and
nothing is due from this statement — anything you owe is on your latest bill and
keeps the due date printed there.

Questions? Call {support_phone} or write to {support_email}.

{utility_name}"""

# DEF-BIL-10531 — the same: "the corrected bill is attached" becomes a link to
# the corrected bill. `default` (`en`) of `bill_email_wording`.
EMAIL_CORRECTED_BILL_SUBJECT, EMAIL_CORRECTED_BILL_BODY = bill_email_wording.WORDING[
    bill_email_wording.CORRECTED_BILL
][bill_email_wording.DEFAULT_WORDING_LANGUAGE]

EMAIL_PLAN_CHANGE_SUBJECT = "Your {utility_name} rates change on {effective_date}"
EMAIL_PLAN_CHANGE_BODY = """Hi {first_name},

We are writing to let you know that the rates on account {account_no} are changing.

Plan {plan_name}
Now {old_rate}
From {effective_date} {new_rate}

This affects service from {effective_date} onward. You do not need to do anything —
your next bill will show the new rate where it applies.

If you would like us to talk you through what it means for how much you use, call
{support_phone}.

{utility_name}"""

EMAIL_PAST_DUE_SUBJECT = "Your {utility_name} balance of {balance} is past due"
EMAIL_PAST_DUE_BODY = """Hi {first_name},

The balance on account {account_no} for {service_address} was due on {due_date}, and
it is now {days_late} days past due.

Amount outstanding {balance}

If you have already paid, thank you — please allow a business day for it to reach
us and ignore this note.

If you have not, you can pay at {utility_website}, or call {support_phone} and we
will sort it out with you. If money is tight this month, ask us about a payment
plan. We would far rather set one up than keep sending letters.

{utility_name}"""

EMAIL_PAYMENT_RECEIPT_SUBJECT = "Your {utility_name} receipt for {amount}"
EMAIL_PAYMENT_RECEIPT_BODY = """Hi {first_name},

Thank you — we have received your payment.

Amount {amount}
Date {date}
Method {method}
Confirmation {confirmation}
Applied to {applied_to_bill}

Balance before this payment {balance_before}
Balance after this payment {balance_after}

Keep this email as your receipt. If something does not match your records, call
{support_phone} and quote the confirmation number above.

{utility_name}"""

# ⚠ REWRITTEN 2026-10-30 (`DEF-PAY-10744`, audit L2-04). This body read *"Your
# payment … did not go through … Nothing has changed on your account. Your
# balance is {balance} and your due date is still {due_date}."* — FALSE for the
# only thing that sends it, a payment the BANK returned: the money is taken back
# off the account, its bills are owed again and an NSF fee may be added. The
# words now live in `payment_returned_wording`, one variant per language, and
# this is its `default` (`en`). Migration `0038` moves a utility whose
# published copy is still the old seed; an edited copy is the utility's own.
EMAIL_PAYMENT_FAILED_SUBJECT, EMAIL_PAYMENT_FAILED_BODY = payment_returned_wording.WORDING[
    payment_returned_wording.RETURNED_EMAIL
][payment_returned_wording.DEFAULT_WORDING_LANGUAGE]

#: The printed returned-payment letter's `default` (`en`) — blank from
#: `DEF-2473` (2026-08-30) until `DEF-PAY-10744` (2026-10-30), when the PO ruled
#: the audit's L2-04 fixed (*"Rest we will fix"*): a default the utility edits.
PAYMENT_FAILED_LETTER_BODY = payment_returned_wording.WORDING[
    payment_returned_wording.RETURNED_LETTER
][payment_returned_wording.DEFAULT_WORDING_LANGUAGE][1]

EMAIL_AUTOPAY_SUBJECT = "Autopay is set up on your {utility_name} account"
EMAIL_AUTOPAY_BODY = """Hi {first_name},

Autopay is now set up for {service_address}, so you do not have to remember your
bill each month.

We will charge {method}
Next charge {next_amount} on {next_charge_date}

You will still get every bill before it is paid, so you can always see what is
coming. You can change or cancel autopay whenever you like at {utility_website}, or
by calling {support_phone}.

{utility_name}"""

EMAIL_REFUND_ISSUED_SUBJECT = "Your {utility_name} refund of {amount}"
EMAIL_REFUND_ISSUED_BODY = """Hi {first_name},

We have issued a refund of {amount} on account {account_no}.

Amount {amount}
Date issued {date}
Sent to {method}
Why {reason}

How long it takes to reach you depends on your bank or card issuer. If it has not
turned up and you are wondering, call {support_phone} and we will check where it is.

{utility_name}"""

EMAIL_CREDIT_ISSUED_SUBJECT = "A credit of {amount} on your {utility_name} account"
EMAIL_CREDIT_ISSUED_BODY = """Hi {first_name},

We have added a credit to account {account_no}.

Credit {amount}
Date {date}
Why {reason}

Your balance is now {balance}. The credit comes off your next bill automatically —
there is nothing you need to do.

If that is not what you expected, call {support_phone} and we will explain it.

{utility_name}"""

#: CR-182-BRC10 (PO A4/A5, 2026-10-14) — sent the moment a reading is flagged
#: high, BEFORE a clerk decides. Short on purpose: the fact, the figure with
#: its unit, and what the customer can do. No ratio and no threshold — how the
#: utility judges "high" is rationale, not something the customer acts on.
#: Seeded in the utility's DEFAULT variant only, like every class here: a
#: message goes in the utility's default language (`OQ-CUS-12619`), and a
#: utility publishes other languages as variants on the designer.
EMAIL_HIGH_USAGE_ALERT_SUBJECT = "High consumption alert on account {account_no}"
EMAIL_HIGH_USAGE_ALERT_BODY = """Hi {first_name},

Your {service_name} reading on {read_date} was much higher than usual.

Used {usage}

It may be a leak, or the reading may be wrong. You can see your readings in your online account. If you think the reading is wrong, call {support_phone}.

{utility_name}"""

#: ⚠ **THE BODY IS ONE TOKEN, AND THAT IS THE CLASS** (`CR-094-BRC01` wave K,
#: `ACC-S16`). Every other seeded body here is wording somebody authored in
#: advance; a message a clerk types on a collections call has no advance
#: wording, so the seeded body is the clerk's own text with the signature
#: beneath it and nothing else. A utility that wants a house style edits this
#: like any other template — a greeting line, a footer — and the clerk's words
#: still land in the middle of it.
ACCOUNT_MESSAGE_SUBJECT = "{message_subject}"
ACCOUNT_MESSAGE_BODY = """{message_body}

{signed_by}
{utility_name}
{support_phone}"""

# ── The four an APPLICANT receives (CR-094-BRC01, 2026-09-15) ───────────────
#
# ⚠ **THE BLUEPRINT DRAWS THE DIALOGS AND NOT THE LETTERS.** Entry 06 of the
# Accounts blueprint draws the Refuse dialog (p084–p085) and the Ask-for-more
# dialog (p085–p086) in full — the reason list, the `What to tell them` box with
# *Goes into the refusal letter.* under it, the tick list, the `Message to the
# applicant` box with *Sent to them and kept on the request's history.* under it
# — and it draws no letter at all. So the wording below is AUTHORED by this lane
# under the same PO ruling every other body here carries (*'please define it for
# this product'*), and the one thing it is not free to invent is the clerk's own
# sentence: `{message_body}` is theirs, and `catalogs` makes it mandatory content
# so a tenant cannot edit it out.
#
# ⚠ **NO BODY HERE NAMES A REFUSAL REASON, A STATE OR A REQUEST ID.** An
# applicant reads these; the five reason codes are what the utility files the
# refusal under. B14 rule 32 keeps our vocabulary off a customer's screen and
# the same argument is stronger in a letter, which outlives the screen.
#:
#: ⊕ **AMENDED 2026-10-22 — `DEF-CUS-10445`.** Both acknowledgements now name
#: WHAT was asked for (`{service_type}`, the services' Settings names) and the
#: TARGET DATE (`{target_date}` — the customer's preferred date, or the request
#: date plus the utility's default days, seeded 15). The sentence says *target*
#: and never *we will connect you on*: it is the date the request is aimed at,
#: not a booked visit. `notifications/0026` republishes this wording only where
#: a utility's published copy is still byte-for-byte the old seed.
SERVICE_REQUEST_ACK_SUBJECT = "We have your request {request_no}"
SERVICE_REQUEST_ACK_BODY = """Thank you, {applicant_name}.

We have your request for {service_type} at {service_address}. Its number is
{request_no} — please quote it when you call us.

Our target date for it is {target_date}.

Nothing is charged for making a request. We will look at it and come back to you,
and if we need anything more from you we will ask.

Questions? Call {support_phone} or email {support_email}.

{utility_name}"""

#: The same letter for an applicant who paid at the counter. BR-CUS-090 clause
#: (3): the *nothing is charged* sentence above is replaced by the amount, the
#: method and the receipt number, because it is the only written proof they hold
#: of money they handed over in person.
SERVICE_REQUEST_ACK_FEE_SUBJECT = "We have your request {request_no}"
SERVICE_REQUEST_ACK_FEE_BODY = """Thank you, {applicant_name}.

We have your request for {service_type} at {service_address}. Its number is
{request_no} — please quote it when you call us.

Our target date for it is {target_date}.

You paid {fee_amount} by {fee_method}. Your receipt number is {receipt_no}. Please
keep this message with it.

We will look at your request and come back to you, and if we need anything more
from you we will ask.

Questions? Call {support_phone} or email {support_email}.

{utility_name}"""

#: ⚠ **THE LETTER THAT NEVER EXISTED.** Row five of the blueprint's step-6
#: block fires *"On approve or refuse"*, and until 2026-09-15 approving a
#: request queued nothing at all — the one decision an applicant is waiting for
#: was the one this product never told them about.
#:
#: It promises NOTHING it cannot keep: no date, no meter, no next step with a
#: time on it. What happens after an approval is a WORK ORDER on a queue
#: somebody works through, and a letter that said *"we will connect you on
#: Tuesday"* would be this product inventing a fact (`BR-WRK-055` — a job is
#: raised, not scheduled, at approval).
# ── new connect · step 7 (PO 2026-09-16) ────────────────────────────────────
# Two bodies, not three. The contract is `contract_service_agreement`, which
# already existed and which BR-NOT-002 forbids seeding — a System Admin
# publishes it under a date they choose. See `catalogs` for that argument.
NEW_CONNECT_CONFIRMED_SUBJECT = "Your connection {connection_no} is booked in"
NEW_CONNECT_CONFIRMED_BODY = """{customer_name},

We have created the connection for {service_address}. Its reference is
{connection_no}, and quoting that will get you to the right people fastest.

We are aiming to have it live by {target_activation}. The work has to be
inspected and passed before anything is switched on, so we will write to you
again as each part goes live.

Questions? Call {support_phone} or email {support_email}.

{utility_name}"""

NEW_CONNECT_QUOTE_SUBJECT = "What connection {connection_no} will cost"
NEW_CONNECT_QUOTE_BODY = """{customer_name},

Here is what the connection work at {service_address} comes to.

    {amount_due} {currency}

That covers the whole of connection {connection_no}. It is charged to account
{account_no}, and it will appear on that account for payment.

If anything here looks wrong, call {support_phone} or email {support_email}
before you pay, and quote {connection_no}.

{utility_name}"""

SERVICE_REQUEST_APPROVED_SUBJECT = "Your request {request_no} is approved"
SERVICE_REQUEST_APPROVED_BODY = """{applicant_name},

Good news — we are going ahead with your request {request_no} for service at
{service_address}.

It is now with the team who will carry out the work. We will be in touch to
arrange it with you.

Questions? Call {support_phone} or email {support_email}, and please quote
{request_no}.

{utility_name}"""

SERVICE_REQUEST_REFUSED_SUBJECT = "About your request {request_no}"
SERVICE_REQUEST_REFUSED_BODY = """{applicant_name},

We are not able to go ahead with your request {request_no} for service at
{service_address}.

{message_body}

If something has changed, or you think we have this wrong, call {support_phone} or
email {support_email} and ask us to look again.

{utility_name}"""

SERVICE_REQUEST_MORE_INFO_SUBJECT = "We need more for request {request_no}"
SERVICE_REQUEST_MORE_INFO_BODY = """{applicant_name},

Before we can go on with your request {request_no} for service at {service_address},
we need something more from you.

{message_body}

Send it to {support_email}, or call {support_phone} if that is easier. Your request
stays open in the meantime.

{utility_name}"""

# ⚠ AMENDED 2026-10-22 — `CR-190-BRC10`, PO: *"give the activation date , first
# bill date and no due date required"*. The body read *"Your first bill is due
# around {first_bill_date}"* — a due date nobody computed, in a sentence that
# printed `——` because no caller passed the token. The first bill date now has
# its OWN paragraph, so where an account has no scheduled cycle the renderer
# leaves that paragraph out (`catalogs` marks the token optional) instead of
# dashing it. Utilities still on the old seeded wording are moved by
# `migrations/0023`; an edited copy is never touched.
EMAIL_WELCOME_SUBJECT = "Welcome to {utility_name}"
EMAIL_WELCOME_BODY = """Welcome, {first_name}.

Your service at {service_address} starts on {service_start_date}.

Your account number is {account_no}. It is worth keeping somewhere handy — we will
ask for it whenever you call.

We will send your first bill on {first_bill_date}.

At {utility_website} you can see your bills and your usage, go paperless, and set
up autopay.

If anything about your service or your address looks wrong, call {support_phone}
now. It is far easier to fix at the start than after the first bill.

{utility_name}"""

# DEF-NOT-10536 (PO 2026-10-22) — the move-out email's wording lives in
# `move_out_wording`, one variant per language; this is its `default` (`en`).
# The body it replaces printed ONE closing read beside ONE `{unit}` and said
# the bill was attached on a move-out that drafted none; `notifications/0028`
# republishes this wording wherever a utility had not edited that one.
EMAIL_MOVE_OUT_FINAL_SUBJECT, EMAIL_MOVE_OUT_FINAL_BODY = move_out_wording.WORDING[
    move_out_wording.MOVE_OUT_FINAL
][move_out_wording.DEFAULT_WORDING_LANGUAGE]

EMAIL_DEPOSIT_SUBJECT = "We have received your {utility_name} deposit of {amount}"
EMAIL_DEPOSIT_BODY = """Hi {first_name},

Thank you — we have received your security deposit for service at {service_address}.

Deposit {amount}
Date received {date}

A deposit is held separately from your bill payments, so it does not come off what
you owe. Your account balance is still {balance}.

We will write to you when the deposit is applied to your account or returned to you.

Questions? Call {support_phone}.

{utility_name}"""

EMAIL_ACCOUNT_CLOSED_SUBJECT = "Your {utility_name} account {account_no} is closed"
EMAIL_ACCOUNT_CLOSED_BODY = """Hi {first_name},

Account {account_no} for {service_address} was closed on {service_end_date}.

Closing balance {closing_balance}

Keep this email — it is your record that the account is closed. If you take service
with us again, tell us this account number and we will pick your history up from
here.

Anything unexpected on it? Call {support_phone} or write to {support_email}.

{utility_name}"""

# ══════════════════════════════════════════════════════════════════════════
# THE PROPERTY SALE — three bodies, `DEF-CUS-5949`, 2026-09-20
# ══════════════════════════════════════════════════════════════════════════
#: ⚠ **THESE THREE ARE SEEDED DEFAULTS A TENANT EDITS, AND NOBODY HAS RATIFIED
#: THE WORDS.** `_LANE_AUTHORED` below says so on every one of them rather than
#: borrowing the 2026-08-17 PO ruling's authority, which covers the
#: twenty-six bodies written under it and not these. `OQ-CUS-12524` is OPEN and
#: is where the PO settles the wording; until it closes, a utility that does
#: not like these edits them on Settings, which is what every other class in
#: this file already expects.
#:
#: ⛔ **NO FIGURE APPEARS IN ANY OF THE THREE, AND THAT IS THE ONE THING NOT TO
#: "IMPROVE".** `BR-CUS-1030` leaves the account's ledger unbroken across a
#: sale and `BR-NOT-013` means a row queued today is delivered whenever an
#: adapter is plugged in — so a balance written into one of these bodies is
#: wrong by exactly the amount the account has moved in between, at a customer,
#: in writing. The palettes in `catalogs.py` do not whitelist one either, so a
#: tenant cannot add one by editing the body.
#: ⚠ **THE SECOND LANE-AUTHORED SOURCE, AND IT IS A DIFFERENT LANE AND A
#: DIFFERENT QUESTION.** `CR-142-BRC07` `P4.10`, 2026-09-27 — the scheduled
#: report. Kept as its own string rather than folded into `_LANE_AUTHORED`
#: above, because a reviewer reading *"which words has nobody ratified"* needs
#: to see WHICH lane wrote each one and WHICH open question settles it; one
#: shared string would answer neither.
_REPORTS_LANE_AUTHORED = (
    "AUTHORED 2026-09-27 by lane REP-P4-REST under `CR-142-BRC07` `P4.10` - no signed "
    "spec writes this body and no PO ruling has ratified these words. `OQ-REP-12757` is "
    "the question; the row is a SEEDED DEFAULT a tenant edits on Settings until it "
    "closes."
)

#: ⚠ **THE ONLY BODY IN THIS FILE ADDRESSED TO A MEMBER OF STAFF BY EMAIL.**
#: `staff_bulk_summary` is in-app; every other row here writes to a customer or
#: an applicant. So it carries no masthead, no `{utility_name}` and no support
#: line: the product is writing to the utility's own clerk about a report that
#: clerk asked for, and a named absence where the company name should be would
#: reach a member of staff on any tenant that has not filled in Settings.
#:
#: ⚠ **`{report_link}` IS MANDATORY CONTENT** (`catalogs.email_scheduled_report`)
#: and `rendering.validate_body` refuses a saved body without it. That is
#: `P4.10`'s whole sentence made structural: the queue carries the LINK.
SCHEDULED_REPORT_SUBJECT = "{report_name} is ready"
SCHEDULED_REPORT_BODY = """Hi {staff_name},

{report_name} ran on {ran_at} and its file is ready.

Open it here: {report_link}

The file is kept until {expires_on}. After that the run stays in your history and
you can run it again from there."""

_CORRECTION_REASON_AUTHORED = (
    "AUTHORED 2026-10-22 by lane CORRECTED-BILL under `DEF-BIL-4454` - the PO ruled that "
    "we write one plain sentence per correction reason (Q3, option A); the row is a "
    "SEEDED DEFAULT a utility edits on Configure -> Templates."
)

_ACCOUNT_ACCESS_AUTHORED = (
    "AUTHORED 2026-10-22 by lane STAFF-INVITE under `CR-188-BRC10` - no signed spec "
    "writes this body; the PO ruled what it carries (a one-time link, never a password) "
    "and the row is a SEEDED DEFAULT a utility edits on Settings."
)

#: `DEF-NOT-10649` — the post-cut and restored messages.
_SERVICE_STATE_AUTHORED = (
    "AUTHORED 2026-10-29 under `DEF-NOT-10649` - the PO ruled both messages, email and "
    "SMS, on by default, and that we write a short default safety text (4A); no signed "
    "spec writes these words and the row is a SEEDED DEFAULT a utility edits on Settings."
)

#: `CR-190-BRC10` lane AGREEMENT's source string, moved here at merge
#: (2026-10-22, lane MERGE-EMAILS) when the two agreement emails joined the ONE
#: seeder — word for word what `agreement_templates` stamped on them before.
_AGREEMENT_AUTHORED = (
    "AUTHORED 2026-10-22 by lane AGREEMENT under `CR-190-BRC10` - no signed spec writes "
    "this body; the PO ruled what it carries (the agreement as a PDF, a single-use link "
    "to accept it, a confirmation once accepted) and the row is a SEEDED DEFAULT a "
    "utility edits on Settings."
)

#: The classes planted once per REGISTRY language, and the module whose words
#: each one is planted from. ⚠ MERGED 2026-10-22 (lane MERGE-EMAILS): CR-188's
#: Account access classes and CR-190's two agreement emails were each given
#: their own per-language planting by their own lane — one here, one in
#: `agreement_templates` at first use only. They are ONE mechanism now, so a
#: utility sees the agreement emails on Settings → Templates from the day it is
#: provisioned (and `0023`/`0024`'s existing-utility pass is unchanged).
LANGUAGE_WORDING = {
    **{code: account_access_wording for code in account_access_wording.WORDING},
    **{code: agreement_wording for code in agreement_wording.WORDING},
    # DEF-NOT-10536 (2026-10-22) — the move-out final bill email.
    **{code: move_out_wording for code in move_out_wording.WORDING},
    # DEF-BIL-4454 (2026-10-22) — *What changed*, one sentence per reason.
    **{code: correction_reason_wording for code in correction_reason_wording.WORDING},
    # DEF-BIL-10531 (2026-10-22) — the bill-ready and corrected-bill emails.
    **{code: bill_email_wording for code in bill_email_wording.WORDING},
    # DEF-NOT-10649 (2026-10-29) — service disconnected / restored, email + SMS.
    **{code: service_state_wording for code in service_state_wording.WORDING},
    # DEF-PAY-10651 (PO 2026-10-29, 2A) — the printed past-due reminder letter
    # (`dunning`), the fallback for a customer no email or consented text reaches.
    **{code: past_due_letter_wording for code in past_due_letter_wording.WORDING},
    # DEF-PAY-10744 (PO 2026-10-30, L2-04) — the returned-payment email + letter.
    **{code: payment_returned_wording for code in payment_returned_wording.WORDING},
}

_LANE_AUTHORED = (
    "AUTHORED 2026-09-20 by the transfer lane under `DEF-CUS-5949` — no signed spec "
    "writes this body and no PO ruling has ratified these words. `OQ-CUS-12524` is the "
    "question; the row is a SEEDED DEFAULT a tenant edits on Settings until it closes."
)

TRANSFER_TO_BUYER_SUBJECT = "Account {account_no} is yours from {sold_on}"
TRANSFER_TO_BUYER_BODY = """Hi {first_name},

Account {account_no} for {service_address} is in your name from {sold_on}.

It is the same account the property has always had, with the same number and the
same meters. Nothing was opened and nothing was closed.

We will write again when your first bill is ready.

Questions? Call {support_phone} or write to {support_email}.

{utility_name}"""

TRANSFER_TO_SELLER_SUBJECT = "Account {account_no} is no longer in your name"
TRANSFER_TO_SELLER_BODY = """Hi {first_name},

Account {account_no} for {service_address} passed to the new owner on {sold_on}.

Keep this email. Every bill and payment on that account up to {sold_on} is still
yours and still says your name.

Anything unexpected on it? Call {support_phone} or write to {support_email}.

{utility_name}"""

#: ⚠ **160 CHARACTERS IS THE BUDGET AND THIS BODY IS WRITTEN TO IT** (CR-007's
#: counter). No window and no technician name: the work order is raised AFTER
#: the sale commits and is allowed to fail, so at the moment this row is
#: written nothing in this product knows when anybody is coming.
TRANSFER_FIELD_VISIT_SMS_BODY = (
    "{utility_name}: a meter reading is being arranged at {service_address} "
    "for {sold_on}. We will call to agree a time. {support_phone}"
)

#: BR-PAY-016 CONFIRMED: *"reminder 3 days before installment"*. The body does
#: not print a lead time — the cadence is tenant config and hardening it into
#: prose is how a setting becomes a promise.
PLAN_NOTICE_UPCOMING_SUBJECT = (
    "Your {utility_name} plan payment of {installment_amount} is due {installment_due_date}"
)
PLAN_NOTICE_UPCOMING_BODY = """Hi {first_name},

This is a reminder about the next payment on your plan for account {account_no}.

Payment {installment_no} of {installments_total}
Amount {installment_amount}
Due {installment_due_date}
Left on the plan after this one {plan_balance}

Your ordinary bill still arrives separately and keeps its own due date.

If this one is going to be difficult, call {support_phone} before it is due. It is
much easier to work something out beforehand.

{utility_name}"""

#: ⚠ *"Your plan is still in place"* IS A RULING, NOT REASSURANCE. PO
#: 2026-08-11, verbatim: *"nodrop we chase for payments until write off"* —
#: nobody is dropped from a plan, at the first miss or the tenth (BR-PAY-016 and
#: BR-CUS-044 both superseded on that point). r10's *"Miss an installment and
#: the plan cancels"* describes the product that ruling abolished.
PLAN_NOTICE_MISSED_SUBJECT = "We have not received your {utility_name} plan payment"
PLAN_NOTICE_MISSED_BODY = """Hi {first_name},

We have not received payment {installment_no} of {installments_total} on your plan
for account {account_no}.

Amount {installment_amount}
Was due {installment_due_date}
Left on the plan {plan_balance}

Your plan is still in place.

If you have already paid, thank you — please allow a business day for it to reach
us. If you have not, you can pay at {utility_website}, or call {support_phone} and
we will work out what is realistic for you.

{utility_name}"""

#: ⚠ AUTHORED UNDER ITS OWN RULING (CR-009 C-14, PO 2026-08-17): *"you give
#: default language for the plan-void notice only - we wil allow utility to
#: make the changes"*. Plain and factual: the plan was voided, why (missed
#: instalments), and the balance now due — the same token vocabulary as its two
#: siblings, so one caller's context serves all three plan notices.
#:
#: **WHAT IS DELIBERATELY NOT IN IT.** No instalment count threshold ("after 2
#: missed installments") — the 'nodrop' ruling of 2026-08-11 abolished the
#: second-miss void and NO rule states a new threshold, so the body says
#: "missed installments" without a figure a customer could hold us to. No
#: collection-agency or legal claim (the writeoff_notice discipline). And no
#: promise of a new plan — an invitation to call, only.
PLAN_NOTICE_VOID_SUBJECT = "Your {utility_name} payment plan has been voided"
PLAN_NOTICE_VOID_BODY = """Hi {first_name},

The payment plan on account {account_no} has been voided because of missed
installments.

The last installment we expected was {installment_amount}, due
{installment_due_date} (payment {installment_no} of {installments_total}).

Every payment you have made under the plan has been kept and applied to your
account. The remaining balance of {plan_balance} is now due.

If that is not manageable in one go, call {support_phone} or visit
{utility_website} — we would far rather work out what is realistic for you than
send the next letter.

{utility_name}"""

EMAIL_APPOINTMENT_SUBJECT = "Your {utility_name} appointment on {appointment_date}"
EMAIL_APPOINTMENT_BODY = """Hi {first_name},

We have booked a visit to {service_address}.

What we are doing {work_type}
Date {appointment_date}
Arrival window {appointment_window}

Before we arrive: {prep_instructions}

If that time does not work for you, call {support_phone} and we will move it.

{utility_name}"""

#: `CR-168-BRC10` P6.1 (2026-10-04, lane SRV-5) — ruling 3's *moved*. The
#: booked letter's shape with the one thing that changed put first.
EMAIL_VISIT_MOVED_SUBJECT = "Your {utility_name} visit has moved to {appointment_date}"
EMAIL_VISIT_MOVED_BODY = """Hi {first_name},

Your visit to {service_address} has a new time.

What we are doing {work_type}
Date {appointment_date}
Arrival window {appointment_window}

Before we arrive: {prep_instructions}

If the new time does not work for you, call {support_phone} and we will move it.

{utility_name}"""

#: The three SMS of ruling 3 (booked, moved, on the way). Each is one sentence
#: a person reads on a lock screen, under CR-007's 160-character counter.
SMS_VISIT_BOOKED_BODY = (
    "{utility_name}: your visit is booked for {appointment_date}, "
    "{appointment_window}. To change it call {support_phone}."
    # `DEF-WRK-10652` (ruling 3B) — its own paragraph, so a job with no
    # preparation text drops it (an optional token) and the text is unchanged.
    "\n\n{prep_instructions}"
)
SMS_VISIT_MOVED_BODY = (
    "{utility_name}: your visit has moved to {appointment_date}, "
    "{appointment_window}. Questions? Call {support_phone}."
)
SMS_TECHNICIAN_ON_THE_WAY_BODY = (
    "{utility_name}: {technician_name} is on the way to you now. "
    "Questions? Call {support_phone}."
)

#: `DEF-WRK-10652` (PO 2026-10-29, ruling 1A) — *Work order logged*: a job
#: with a customer raised WITHOUT a date. Order number, what, where (the
#: premises' address, walked), *we'll confirm a date*, the support phone, and
#: the preparation text (ruling 3B; its paragraph drops when there is none).
EMAIL_WORK_ORDER_LOGGED_SUBJECT = "Work order {order_no} logged — {utility_name}"
EMAIL_WORK_ORDER_LOGGED_BODY = """Hi {first_name},

We have logged work at {service_address}.

Work order {order_no}
What we are doing {work_type}

We will confirm a date with you.

Before we arrive: {prep_instructions}

Questions? Call {support_phone}.

{utility_name}"""
SMS_WORK_ORDER_LOGGED_BODY = (
    "{utility_name}: work order {order_no} ({work_type}) at {service_address} "
    "is logged. We will confirm a date. Call {support_phone}."
    "\n\n{prep_instructions}"
)

EMAIL_WORK_COMPLETED_SUBJECT = "{work_type} at {service_address} is done"
EMAIL_WORK_COMPLETED_BODY = """Hi {first_name},

The work at {service_address} is finished.

What we did {work_type}
Completed {completed_date}
Who did it {technician_name}

If you notice anything unexpected — no service, a leak, or something left open —
call {support_phone} straight away and we will come back out.

{utility_name}"""

#: ⚠ A PLANNED INTERRUPTION, NOT AN ADVISORY. r10 notes that its boil-water
#: variant *"follows TCEQ required language"* — regulator-mandated wording this
#: platform does not hold. An advisory is a tenant variant carrying its own
#: regulator's text; the platform default is the notice with no legal weight.
EMAIL_OUTAGE_SUBJECT = "Planned service interruption in {area} on {outage_start}"
EMAIL_OUTAGE_BODY = """Hi {first_name},

We need to interrupt service in {area}, and that includes {service_address}.

From {outage_start}
Until {outage_end}
Why {reason}

Those times are our best estimate. We will get service back on as soon as the work
is safely finished, and we will write again when it is.

If anyone at your address depends on our service for medical equipment, call
{support_phone} now so we can plan around you.

{utility_name}"""

#: A card left at the door. No greeting line — nobody was home to greet.
DOOR_HANGER_BODY = """{utility_name}

WE CALLED TODAY AND COULD NOT FINISH

{service_address}
{visit_date}

What we came to do: {work_type}

We could not complete it, so we will need to come back. Please call {support_phone}
and we will arrange a time that suits you.

{utility_name}
{utility_address}
{support_phone} · {support_email} · {utility_website}"""

#: The narrowest body in the library, and deliberately so: an insert is whatever
#: the utility wants to tell everyone at once, so the DEFAULT is the one thing
#: that is true every month.
BILL_INSERT_BODY = """{utility_name}

HOW TO REACH US

Report a leak, an outage or an emergency — {support_phone}
Questions about your bill — {support_email}
Pay, check your usage, or go paperless — {utility_website}

This page is not a bill. Nothing on it is due."""

# ══════════════════════════════════════════════════════════════════════════
# THE THREE DISCONNECT TIERS — PO RULING 2026-08-17, *"you build default
# langauge and let Utility user change it as they want"* (CR-007)
# ══════════════════════════════════════════════════════════════════════════
# **THESE THREE ARE THE MOST CONSEQUENTIAL BODIES IN THIS FILE AND THEY GET
# THEIR OWN SECTION FOR THAT REASON.** A 10-day regulated disconnection notice
# is a legal document at real postage. Until today all three slots were built
# and EMPTY, refusing every save by name, so no disconnection notice could be
# produced on any tenant — the honest state, and the one the PO's ruling closes.
#
# **THE RULING, VERBATIM** (12-governance/11-change-requests.md §"CR-007 · The
# disconnect notices — the platform writes the defaults"):
#
#   > *"we will take this option; we provide default option for all 5 you ahve
#   > mentioned; if Utility wants to over ride it let them do it; I can also
#   > give tick boxes if required to add 5"*
#   > *"you build default langauge and let Utility user change it as they want"*
#
# **EACH BODY IS THREE THINGS AND ONLY THE FIRST IS THIS LANE'S:**
#   1. **A19 §2's tier sentence, QUOTED CHARACTER FOR CHARACTER.** It is signed
#      and it is the paragraph with the tier's meaning in it. A test asserts each
#      one is present verbatim, so an edit that "improves" it goes RED.
#   2. **`{rights_footer}`**, which expands to the tenant's own five clauses at
#      render (`rights_footer.py`) — switched on and off with tick boxes and
#      overridable clause by clause, which is the PO's *"let them change it as
#      they want"*.
#   3. **`{state_puc_ref}`**, non-removable class content (US-NOT-007 TC-6).
#
# **WHAT IS DELIBERATELY NOT IN ANY OF THEM:**
#   · **No dollar figure.** The reconnect fee is `{reconnect_fee}` on the one
#     tier whose signed sentence carries it (BR-CUS-039: a tenant charge code,
#     never a constant), and `generate_disconnect_notice` REFUSES rather than
#     defaulting it (US-NOT-009 TC-5).
#   · **No notice period beyond the three the tiers already name.** "10 days" is
#     inside A19's own tier-1 sentence; nothing here adds a fourth deadline.
#   · **No `{certified_no}`.** It is in tier 3's palette and it is filled from
#     the provider response AT DISPATCH (field map §3, r10 #8) — and no provider
#     adapter exists on any channel, so printing it in the platform default would
#     put `——` where a tracking number goes, on the one letter that goes
#     certified. A utility whose mailer supplies one adds the line on SET-10.
#   · **No `{utility_logo}`** — DEF-195, on every body in this file.
#
# **THE THREE TOKEN SETS ARE NOT INTERCHANGEABLE AND THE BODIES PROVE IT.** Tier
# 1 has `{pay_by_date}` and no `{cut_date}`; tier 2 has `{cut_date}` and
# `{reconnect_fee}`; tier 3 has `{cut_date}`, `{48h}` and `{support_phone}`.
# `rendering.validate_body` refuses each body against its own class, so the
# 10-day warning physically cannot be written as a 48-hour certified letter
# (BR-NOT-014, and the reason the three slots exist).

DISCONNECT_10_DAY_BODY = """{utility_name}
{utility_address}

{customer_name}
{service_address}

Account {account_no}

PAST-DUE NOTICE

Your account is past due in the amount of {balance}. Please pay by {pay_by_date} \
(10 days) to avoid service interruption.

If you have already paid, thank you — please allow a business day for it to reach us
and ignore this notice.

If you cannot pay the whole amount by that date, call {support_phone} before it and
ask about a payment plan. We would far rather set one up with you than send the next
letter.

YOUR RIGHTS

{rights_footer}

Commission reference: {state_puc_ref}

{utility_name} · {support_phone} · {support_email}"""

DISCONNECT_5_DAY_BODY = """{utility_name}
{utility_address}

{customer_name}
{service_address}

Account {account_no}

FINAL REMINDER BEFORE DISCONNECTION

FINAL REMINDER. Service to {service_address} is scheduled for disconnection on \
{cut_date} unless {balance} is received. A reconnect fee of {reconnect_fee} applies to \
restore service.

If you have already paid, thank you — please allow a business day for it to reach us
and ignore this notice.

If you cannot pay it all, call {support_phone} today. There is still time to arrange
something, and it is far easier to do before the date above than after it.

YOUR RIGHTS

{rights_footer}

Commission reference: {state_puc_ref}

{utility_name} · {support_phone} · {support_email}"""

DISCONNECT_48_HOUR_BODY = """{utility_name}
{utility_address}

{customer_name}
{service_address}

Account {account_no}

NOTICE OF DISCONNECTION

NOTICE OF DISCONNECTION. Service will be disconnected on {cut_date} ({48h}). To avoid \
disconnection pay {balance} immediately. Medical/critical-care customers: call \
{support_phone}.

If you have already paid, call {support_phone} now and tell us — do not wait for the
payment to reach us.

YOUR RIGHTS

{rights_footer}

Commission reference: {state_puc_ref}

{utility_name} · {support_phone} · {support_email}"""


#: ⚠ THIS BODY MAKES NO CLAIM ABOUT WHETHER THE DEBT IS STILL OWED OR WHERE IT
#: GOES NEXT. r10 draws *"the debt remains owed and may be referred to a
#: collection agency"*; both are a legal question and a tenant practice, and
#: neither is ruled anywhere in this repo. What is stated is the accounting
#: fact.
WRITEOFF_NOTICE_BODY = """{utility_name}
{utility_address}

{customer_name}
{service_address}

Account {account_no}

This letter confirms that account {account_no} was closed on {date} with an unpaid
balance of {amount}, and that we have removed that balance from our active
accounts.

If you would like to settle it, or you would like to take service with us again,
call {support_phone} and ask for the billing office. We are happy to talk it
through.

{utility_name}"""


#: ⚠ THE ONE IN-APP BODY, AND THE ONLY ONE ANY BULK ACTION EVER RENDERS
#: (BR-NOT-020, PO 2026-08-17).
#:
#: PO verbatim: *"for single notification send 1 message and for bulk action
#: also send 1 message only saying nulk action is completed"*, and the CR's own
#: binding half: *"the message states COMPLETION, and where the operation had
#: failures it must say HOW MANY"*.
#:
#: **`{failed_count}` IS PRINTED EVEN WHEN IT IS ZERO**, deliberately. A body
#: that only mentions failures when there were some means a clerk has to notice
#: an ABSENT sentence to learn that a run was clean — and the day the count
#: renders as a named absence (`——`) because a caller forgot to pass it, the
#: message would look identical to a clean run. A printed zero cannot do that.
#: `catalogs.CATALOGS["staff_bulk_summary"].mandatory_content` refuses any
#: replacement body that drops the token.
#:
#: It is DELIBERATELY four short lines. This is read inside a bell popover by
#: somebody who is in the middle of something else; the whole point of one
#: message per bulk action is that the message is glanceable.
#: ⚠ **NO MASTHEAD, AND THAT IS THE ONE WAY THIS BODY DIFFERS IN KIND FROM
#: EVERY OTHER ONE IN THIS FILE.** `catalogs._PRINTABLE_MASTHEAD` puts the
#: utility's name, address and support details on every printable class, and its
#: reason is stated there: *"every one of these documents is a LETTER FROM THE
#: UTILITY"*. This one is not. It is the PRODUCT talking to the utility's own
#: operator, inside the product they are already signed in to — a signature line
#: reading "Brazos Bend Utilities" in their own bell would tell them something
#: they know, and on a tenant that has not filled in Settings → Company it would
#: render the named absence `——` under every run summary they ever receive
#: (measured: that is exactly what the first cut of this body did).
BULK_SUMMARY_BODY = """{operation} finished.

{total_count} processed · {failed_count} failed
{finished_at}"""

#: `staff_field_work` (CR-168-BRC10 §F, lane FIELD-2) — one field event on
#: one job. Two short lines for `BULK_SUMMARY_BODY`'s reason: it is read in a
#: bell. The bell itself shows the event in the clerk's own language from the
#: catalogues (`notifications.fieldWork.*`); this body is the utility's copy,
#: shown on the dispatch home and editable on Settings → Templates.
FIELD_WORK_BODY = """{order_no} {event}.
{at}"""

_FIELD_WORK_AUTHORED = (
    "AUTHORED 2026-10-04 to TECHNICIAN SYNC DESIGN (5) — PO 2026-10-04, design "
    "delegated: 'the office is told when a job closes, when its photos are complete "
    "(Accept unlocks), and when anything is flagged Needs review' (CR-168-BRC10 §F)"
)

#: This body's own `source` string. It is neither quoted from a spec nor
#: authored under CR-007's *"please define it for this product"* — it is written
#: to CR-009's ruling, which states the required CONTENT in the PO's own words,
#: so a reviewer can check the wording against a sentence rather than against a
#: judgement.
_BULK_SUMMARY_AUTHORED = (
    "AUTHORED 2026-08-17 to the PO ruling *'for single notification send 1 message and "
    "for bulk action also send 1 message only saying nulk action is completed'* "
    "(CR-009, fourth ruling set, ruling 2 → BR-NOT-020). The failure count is the CR's "
    "own binding clause — *'where the operation had failures it must say how many'* — "
    "and is enforced as mandatory class content, not left to this body"
)


# ══════════════════════════════════════════════════════════════════════════
# THE FOUR CONTRACT BODIES — PO RULING 2026-08-18 (CR-011 item 9),
# *"already answer - provide default and allow user to change"*
# ══════════════════════════════════════════════════════════════════════════
# **THESE FOUR ARE NOT IN `SEEDABLE` AND THAT IS NOT A REFUSAL — IT IS
# BR-NOT-002.** Every contract version is EFFECTIVE-DATED, and
# `template_service.save_draft` refuses a contract draft that carries no
# `effective_from`. The CR states the consequence in as many words and leaves it
# standing over this very ruling: *"Both are BR-NOT-002 effective-dated
# contracts, so a draft still needs an `effective_from` a human chooses;
# provisioning-day is not that date."*
#
# So the platform AUTHORS the wording and OFFERS it; the System Admin publishes
# it with the date they choose. Writing a published row at provisioning would
# have taken one of two shapes and both are worse than offering:
#
#   · `effective_from = NULL` — which `template_service._published_version`
#     resolves BEFORE any dated version, so every future version the utility
#     dates would be shadowed by ours forever. That is not seeding a default; it
#     is disabling BR-NOT-002 for the whole contracts group.
#   · `effective_from = <the day provisioning ran>` — a machine-chosen date on
#     the face of a document somebody signs, which is precisely the sentence the
#     CR keeps standing.
#
# **What the utility does instead is one screen and one date:** open the class
# on SET-10, the platform default is offered pre-filled, they edit it or not,
# they choose the date it takes effect, they publish. That is "provide default
# and allow user to change" with the human in the one decision BR-NOT-002 says
# is theirs.
#
# **THE SAME FIVE CONSTRAINTS THE 2026-08-17 AUTHORING RAN UNDER APPLY HERE**
# (every token in the class palette · no `{utility_logo}` · no invented figure,
# fee, deadline, notice period or legal right · English only · r10's structure
# where it covers a class, never its sample figures), and a sixth for contracts:
# **no clause states a term this repo has not ruled.** Where a real agreement
# needs one — when a deposit comes back, how much notice ends service — the body
# points at the utility's own published policy instead of inventing a period.
# That is the same absence `email_deposit` already keeps (OQ-260).

#: BR-NOT-004 type ②. The SHAPE of the bargain, with every figure and every
#: period deferred to the utility's own published policy.
CONTRACT_SERVICE_AGREEMENT_BODY = """{utility_name}
{utility_address}
{support_phone} · {support_email}

SERVICE AGREEMENT

Prepared {today} for {customer_name}, account {account_no}.
Service address: {service_address}
Service starts: {service_start_date}

1. What we do. {utility_name} supplies service to the address above from the date
   shown, and looks after the meter and the equipment we own.

2. What you do. You pay for the service you use, at the rates and charges in our
   published rate schedule, and you keep the contact details on your account up to
   date so that bills and notices reach you.

3. Your bills. We read your meter and bill you for the period shown on the bill.
   Every bill states what is due and the date it is due. If something on it looks
   wrong, call {support_phone} before the due date and we will go through it with
   you.

4. If a bill is not paid. We write to you before service is interrupted. The
   notices we send, and the time each one gives you, are set out in our published
   collection and disconnection policy.

5. Access. You give us safe access to the meter so we can read, test, maintain,
   disconnect and reconnect it.

6. Deposits. If we ask for a deposit it is covered by a separate deposit
   agreement, not by this one.

7. Ending service. Tell us when you are leaving and we will take a closing read
   and send a final bill. We may end service ourselves under our published policy.

8. Changes. Rates, charges and policies change from time to time. A change takes
   effect on the date stated in the notice we send you.

By signing, you agree to the terms above.

Customer signature: {customer_signature}          Date: {date}"""


#: BR-NOT-004 type ③. States what a deposit IS and what it is not; states no
#: period and no interest rate, because no rule in this repo states either.
CONTRACT_DEPOSIT_BODY = """{utility_name}
{utility_address}
{support_phone} · {support_email}

DEPOSIT AGREEMENT

Prepared {today} for {customer_name}, account {account_no}.
Service address: {service_address}

1. The deposit. You agree to pay a deposit of {amount} on this account.

2. What it is for. The deposit is security against unpaid charges on this account.
   It is not a payment towards your bills and it does not reduce what you owe.

3. While we hold it. {utility_name} holds the deposit for as long as this
   agreement is in force. Whether interest is paid on it, and at what rate, is set
   out in our published deposit policy.

4. Getting it back. The deposit is returned to you, or applied to what you owe,
   when the conditions in our published deposit policy are met. Those conditions
   and their timing are in that policy; this agreement does not set a period of its
   own. Ask us for a copy at any time on {support_phone}.

5. If the account closes owing money. We may apply the deposit to the balance and
   bill or refund you the difference.

Customer signature: {customer_signature}          Date: {date}"""


#: BR-NOT-004 type ① + A19 §3's four labelled sections, with BR-NOT-016's
#: `{schedule_table}` where §3.2's schedule belongs.
#:
#: ⚠ **THE SCHEDULE IS A NAMED, VISIBLE ABSENCE AND THE DOCUMENT SAYS SO ON ITS
#: OWN FACE.** Nothing in this repo builds the repeating block yet (that is all
#: OQ-244 still holds), so `{schedule_table}` renders `——` today, exactly as
#: every unsupplied catalogued token renders. Clause 4's last line is what makes
#: that safe: it tells the reader not to sign a blank schedule. The failure the
#: original refusal was written about — *"a customer e-signs an agreement stating
#: a total and not one due date"* — needs the reader to be unaware, and this
#: reader is told.
#:
#: ⚠ **CLAUSE 7 IS THE 'NODROP' RULING (PO 2026-08-11, *"nodrop we chase for
#: payments until write off"*)**, which SUPERSEDED the cancel-on-miss default
#: clause A19 §3.3 and prototype r10 both describe. `{missed_count}` stays in the
#: palette and is deliberately unused: there is no ruled threshold to count to.
CONTRACT_PAYMENT_PLAN_BODY = """{utility_name}
{utility_address}
{support_phone} · {support_email}

PAYMENT PLAN AGREEMENT

Prepared {today} for {customer_name}, account {account_no}.

1. What this plan covers. {balance} owed on account {account_no}.

2. Down payment. {down} is due when you sign this agreement.

3. Instalments. The rest is paid in {n} instalments, on the dates and in the
   amounts set out in the schedule below.

4. The schedule. Each instalment, when it is due, how much it is, and what is left
   after it:

{schedule_table}

   This schedule is part of the agreement you are signing. Do not sign this
   agreement if the schedule above is blank or shows ——: it means the schedule has
   not been produced, and there would be nothing here for you to agree to.

5. How you pay. Instalments are paid by {payment_method}.

6. While the plan runs. Paying each instalment by its due date keeps the plan in
   place.

7. If you miss one. Call us on {support_phone}. Missing an instalment does not by
   itself cancel this plan — the balance stays owed and we will work out with you
   how it gets paid.

Customer signature: {customer_signature}          Date: {date}"""


def _numbered(items: tuple[str, ...]) -> str:
    """The requirement list as document text — ONE source, three consumers.

    `catalogs.CONTRACT_INPUT_REQUIREMENTS` is the source; this renders it onto
    the placeholder's own face, `rendering.refuse_if_placeholder` quotes it in
    the refusal, and `GET /template-catalog/{code}` serves it to the screen. A
    second copy of this list is the drift hard-won law 1 warns about.
    """
    return "\n\n".join(f"{index}. {item}" for index, item in enumerate(items, start=1))


#: BR-NOT-004 type ④ — **the one body in this product built to be REFUSED.**
#: PO, 2026-08-18: *"Do it; put the details, I will handle it with user"*. Both
#: halves of that sentence are here: the placeholder, and the details.
CONTRACT_AUTOPAY_PLACEHOLDER_BODY = f"""{rendering.PLACEHOLDER_MARK}

{{utility_name}}
{{utility_address}}
{{support_phone}} · {{support_email}}

AUTOMATIC PAYMENT (ACH) AUTHORIZATION — PLACEHOLDER. DO NOT SEND THIS TO A
CUSTOMER AND DO NOT ASK ANYONE TO SIGN IT.

SMART360 Next gives you default wording for every other document in this product.
It does not give you wording for this one, and that is deliberate. What an
authorization for recurring ACH debits has to say is prescribed by the NACHA
Operating Rules, which this platform does not hold. Wording we wrote by
inference would look official and could be wrong, and this is the document where
that costs you rather than us.

While this text is still here the product REFUSES to render this document, so it
cannot reach a customer by accident.

WHAT TO TAKE TO YOUR BANK. Ask your bank (your ODFI) and your own counsel for
wording that settles each of these, then replace everything on this page with it:

{_numbered(catalogs.required_from_utility("contract_autopay_authorization"))}

WHEN YOU HAVE THE WORDING: paste it here, delete the marker line at the top of
this page, choose the date it takes effect, and publish. The tokens available to
you are {{customer_name}}, {{account_no}}, {{service_address}},
{{payment_method}}, {{today}}, {{customer_signature}} and {{date}}, plus your own
utility details. Bank routing and account numbers are written in by the customer
on the form and are never merged from this platform.

Customer: {{customer_name}} · account {{account_no}}
Signature: {{customer_signature}}          Date: {{date}}"""


class SeedBody:
    """One class this platform can plant, with the document that authorises it.

    `source` is not decoration: it is what a reviewer reads to check the body
    against the spec — or, for the twenty-six authored on 2026-08-17, to see at
    a glance that there IS no spec behind it and that a PO ruling is what
    authorises the wording instead.
    """

    __slots__ = ("code", "name", "body", "source", "subject")

    def __init__(
        self, code: str, name: str, body: str, source: str, subject: str | None = None
    ) -> None:
        self.code = code
        self.name = name
        self.body = body
        self.source = source
        #: Email classes only. `None` means "this class has no subject", which
        #: is a different row from an empty string somebody saved (see
        #: `template_models.NotificationTemplateVersion.subject`).
        self.subject = subject


#: What every authored entry's `source` says, so a reviewer never has to guess
#: which side of the 2026-08-17 line a body came from.
_PO_AUTHORED = (
    "AUTHORED 2026-08-17 under the PO ruling *'please define it for this product'* "
    "(CR-007, DEF-210) — no signed spec writes this body"
)

#: The three disconnect tiers carry their OWN source string, because they are the
#: only bodies in this file that are half quoted and half authored — and because
#: they are the ones a human review must look hardest at.
_TIER_AUTHORED = (
    "PART QUOTED, PART AUTHORED. The tier sentence is A19 §2's, character for "
    "character (a test asserts it). The letter around it and the five rights clauses "
    "behind {rights_footer} were AUTHORED 2026-08-17 under the PO ruling *'you build "
    "default langauge and let Utility user change it as they want'* (CR-007) — the "
    "ruling that reversed BR-NOT-015's *'must not be invented'* by naming who writes "
    "them. The clauses themselves live in apps/notifications/rights_footer.py and are "
    "overridable and switchable per clause by the tenant's System Admin"
)


#: The plan-void notice's own source string (CR-009 C-14) — the one body
#: authored under a ruling that names it alone, for an event nothing fires.
_PLAN_VOID_AUTHORED = (
    "AUTHORED 2026-08-18 to the PO ruling of 2026-08-17 (CR-009 C-14), verbatim: *'you "
    "give default language for the plan-void notice only - we wil allow utility to make "
    "the changes'*. ⚠ The 'nodrop' ruling (2026-08-11) still stands: NOTHING in this "
    "product voids a plan, so no writer schedules this notice — wording ahead of the "
    "flow, the posture the PO ratified 2026-08-16 (*'wording can exist before the flow "
    "that sends it'*). The body states no missed-instalment threshold, because no rule "
    "sets one"
)


#: The three contract defaults' `source` — a THIRD authoring ruling, distinct
#: from 2026-08-17's blanket delegation and from C-14's single class, because a
#: human reviewing this file has to see which sentence authorised which body.
_CONTRACT_AUTHORED = (
    "AUTHORED 2026-08-18 to the PO ruling of the same day (CR-011 item 9), verbatim: "
    "*'the 4 template classes needing legal wording - already answer - provide default "
    "and allow user to change'*. It REVERSES this file's standing refusal to write a "
    "document somebody signs, and generalises C-14's precedent. ⚠ OFFERED, NOT SEEDED: "
    "BR-NOT-002 makes a contract version effective-dated and that date is the utility's "
    "choice, so nothing here is published at provisioning. Every figure and every period "
    "is deferred to the utility's own published policy — no body states a notice period, "
    "a deposit-refund window, an interest rate or a fee, because no rule in this repo "
    "states one"
)

#: The payment-plan agreement's own string: same ruling, and it OVERRULES a
#: recommendation this session made, which is worth a reviewer's eye.
_CONTRACT_AUTHORED_PAYMENT_PLAN = (
    "AUTHORED 2026-08-18 under CR-011 item 9, and specifically under the PO's OVERRULING "
    "of this session's recommendation to hold this class, verbatim: *'create this dont "
    "leave it open ; once sample and defaults are available we can make changes later; "
    "but without default sample functionalities ill not work'*. ⚠ The objection was not "
    "withdrawn, it was overruled, and its substance is carried inside the document: "
    "`{schedule_table}` is BR-NOT-016's ruled token, it is MANDATORY class content so no "
    "edit can drop it, nothing in this repo builds the repeating block yet (OQ-244's "
    "remainder) so it renders `——`, and clause 4 tells the reader not to sign a blank "
    "schedule. Clause 7 states the 'nodrop' ruling (2026-08-11) and not A19 §3.3's "
    "superseded cancel-on-miss clause"
)

#: The ACH authorization's own string. It is not a default at all — it is a
#: refusal with instructions, shipped under a ruling that asked for exactly that.
_CONTRACT_PLACEHOLDER = (
    "PLACEHOLDER, NOT WORDING, under the PO ruling of 2026-08-18 (CR-011 item 9), "
    "verbatim: *'Do it; put the details, I will handle it with user'*. The wording of an "
    "authorization for recurring ACH debits is prescribed by the NACHA Operating Rules, a "
    "scheme this repository does not hold, so this is the ONE document in the product "
    "where a plausible wrong answer creates real liability. The body carries "
    "`rendering.PLACEHOLDER_MARK`; `rendering.render` REFUSES it while the marker is "
    "there, so it cannot reach a customer by accident. The second half of the ruling is a "
    "DELIVERABLE and lives in `catalogs.CONTRACT_INPUT_REQUIREMENTS`: eight plain-English "
    "items the utility takes to their bank, printed on the document's own face, quoted in "
    "the renderer's refusal and served to the screen"
)


def _e(code: str, name: str, subject: str, body: str) -> SeedBody:
    """An authored EMAIL class: subject + body."""
    return SeedBody(code=code, name=name, body=body, subject=subject, source=_PO_AUTHORED)


def _p(code: str, name: str, body: str) -> SeedBody:
    """An authored PRINT or SMS class: body only, no subject."""
    return SeedBody(code=code, name=name, body=body, source=_PO_AUTHORED)


#: THE WHOLE LIBRARY — thirty-three of the thirty-seven classes SET-09 lists
#: ([AMENDED 2026-08-18]: the plan-void notice joined under C-14; the counts
#: here had also gone stale by one when `staff_bulk_summary` joined on
#: 2026-08-17 — 37/33 is the measured pair and `test_def_210` pins it).
#: `name` is the S8/SET-09 card's label; for every authored class it is
#: `catalogs.LISTINGS[code].name` verbatim, so one class has one name on the
#: catalog and in the seeder rather than two that can drift.
#:
#: **THE FOUR THAT ARE NOT HERE ARE NOT AN OVERSIGHT** — the four CONTRACTS,
#: each with its reason in `catalogs.NOT_AUTHORED_BY_PO_RULING` and reported
#: per class by `seed_notice_templates`. See the module docstring.
SEEDABLE: tuple[SeedBody, ...] = (
    # ── the two QUOTED bodies, unchanged since 2026-08-16 ────────────────
    SeedBody(
        code="dunning",
        name="Dunning",
        body=DUNNING_BODY,
        source="A13 §'Reminder / notice templates (previews)' — Reminder, verbatim",
    ),
    SeedBody(
        code="receipt",
        name="Receipt",
        body=RECEIPT_BODY,
        source="A13 §'Reminder / notice templates (previews)' — Receipt, verbatim",
    ),
    # ── SMS ──────────────────────────────────────────────────────────────
    _p("sms_bill_ready", "Bill ready · SMS", SMS_BILL_READY_BODY),
    _p("sms_past_due", "Past-due reminder · SMS", SMS_PAST_DUE_BODY),
    _p("sms_payment_received", "Payment receipt · SMS", SMS_PAYMENT_RECEIVED_BODY),
    _p("sms_disconnect", "Disconnect notice · SMS supplement", SMS_DISCONNECT_BODY),
    # ── Email ────────────────────────────────────────────────────────────
    _e(
        "email_bill_ready",
        "Bill ready · e-bill email",
        EMAIL_BILL_READY_SUBJECT,
        EMAIL_BILL_READY_BODY,
    ),
    _e("email_statement", "Statement · Email", EMAIL_STATEMENT_SUBJECT, EMAIL_STATEMENT_BODY),
    _e(
        "email_corrected_bill",
        "Corrected bill notice",
        EMAIL_CORRECTED_BILL_SUBJECT,
        EMAIL_CORRECTED_BILL_BODY,
    ),
    _e(
        "email_plan_change",
        "Plan or rate change",
        EMAIL_PLAN_CHANGE_SUBJECT,
        EMAIL_PLAN_CHANGE_BODY,
    ),
    _e("email_past_due", "Past-due reminder · Email", EMAIL_PAST_DUE_SUBJECT, EMAIL_PAST_DUE_BODY),
    _e(
        "email_payment_receipt",
        "Payment receipt · Email",
        EMAIL_PAYMENT_RECEIPT_SUBJECT,
        EMAIL_PAYMENT_RECEIPT_BODY,
    ),
    _e(
        "email_payment_failed",
        "Payment failed / NSF",
        EMAIL_PAYMENT_FAILED_SUBJECT,
        EMAIL_PAYMENT_FAILED_BODY,
    ),
    # DEF-PAY-10744 (2026-10-30) — the printed returned-payment letter, blank
    # since DEF-2473 and now a default the utility edits.
    _p("payment_failed_letter", "Payment failed / NSF · letter", PAYMENT_FAILED_LETTER_BODY),
    _e("email_autopay", "Autopay & scheduled payment", EMAIL_AUTOPAY_SUBJECT, EMAIL_AUTOPAY_BODY),
    _e(
        "email_refund_issued",
        "Refund issued",
        EMAIL_REFUND_ISSUED_SUBJECT,
        EMAIL_REFUND_ISSUED_BODY,
    ),
    _e(
        "email_credit_issued",
        "Credit issued",
        EMAIL_CREDIT_ISSUED_SUBJECT,
        EMAIL_CREDIT_ISSUED_BODY,
    ),
    _e(
        "email_high_usage_alert",
        "High consumption alert",
        EMAIL_HIGH_USAGE_ALERT_SUBJECT,
        EMAIL_HIGH_USAGE_ALERT_BODY,
    ),
    _e(
        "account_message",
        "A message from the billing team",
        ACCOUNT_MESSAGE_SUBJECT,
        ACCOUNT_MESSAGE_BODY,
    ),
    _e(
        "service_request_acknowledgement",
        "Service request received",
        SERVICE_REQUEST_ACK_SUBJECT,
        SERVICE_REQUEST_ACK_BODY,
    ),
    _e(
        "service_request_acknowledgement_fee",
        "Service request received · fee taken",
        SERVICE_REQUEST_ACK_FEE_SUBJECT,
        SERVICE_REQUEST_ACK_FEE_BODY,
    ),
    _e(
        "service_request_approved",
        "Service request approved",
        SERVICE_REQUEST_APPROVED_SUBJECT,
        SERVICE_REQUEST_APPROVED_BODY,
    ),
    _e(
        "new_connect_confirmed",
        "New connect — confirmed",
        NEW_CONNECT_CONFIRMED_SUBJECT,
        NEW_CONNECT_CONFIRMED_BODY,
    ),
    _e(
        "new_connect_quote",
        "Connection quote",
        NEW_CONNECT_QUOTE_SUBJECT,
        NEW_CONNECT_QUOTE_BODY,
    ),
    _e(
        "service_request_refused",
        "Service request refused",
        SERVICE_REQUEST_REFUSED_SUBJECT,
        SERVICE_REQUEST_REFUSED_BODY,
    ),
    _e(
        "service_request_more_info",
        "Service request · more needed",
        SERVICE_REQUEST_MORE_INFO_SUBJECT,
        SERVICE_REQUEST_MORE_INFO_BODY,
    ),
    _e("email_welcome", "Welcome / account opened", EMAIL_WELCOME_SUBJECT, EMAIL_WELCOME_BODY),
    _e(
        "email_move_out_final",
        "Move-out final bill",
        EMAIL_MOVE_OUT_FINAL_SUBJECT,
        EMAIL_MOVE_OUT_FINAL_BODY,
    ),
    _e("email_deposit", "Deposit received & applied", EMAIL_DEPOSIT_SUBJECT, EMAIL_DEPOSIT_BODY),
    _e(
        "email_account_closed",
        "Account closed confirmation",
        EMAIL_ACCOUNT_CLOSED_SUBJECT,
        EMAIL_ACCOUNT_CLOSED_BODY,
    ),
    # ── the PROPERTY SALE · `DEF-CUS-5949`, 2026-09-20 ───────────────────
    # Their OWN source string (`_LANE_AUTHORED`), like the disconnect tiers,
    # because they are the only bodies in this file authored by a LANE rather
    # than under the PO's 2026-08-17 ruling — and a reviewer must be able to
    # see which three those are without diffing.
    SeedBody(
        code="transfer_to_buyer",
        name="Property sold · the buyer",
        body=TRANSFER_TO_BUYER_BODY,
        subject=TRANSFER_TO_BUYER_SUBJECT,
        source=_LANE_AUTHORED,
    ),
    SeedBody(
        code="transfer_to_seller",
        name="Property sold · the seller",
        body=TRANSFER_TO_SELLER_BODY,
        subject=TRANSFER_TO_SELLER_SUBJECT,
        source=_LANE_AUTHORED,
    ),
    SeedBody(
        code="transfer_field_visit_sms",
        name="Property sold · meter visit",
        body=TRANSFER_FIELD_VISIT_SMS_BODY,
        source=_LANE_AUTHORED,
    ),
    # ── ACCOUNT ACCESS · `CR-188-BRC10`, 2026-10-22 ──────────────────────
    # The `default` variant; every other language is planted beside it by
    # `seed_language_variants` from `account_access_wording.WORDING`.
    *(
        SeedBody(
            code=code,
            name=catalogs.LISTINGS[code].name,
            subject=languages[account_access_wording.DEFAULT_WORDING_LANGUAGE][0],
            body=languages[account_access_wording.DEFAULT_WORDING_LANGUAGE][1],
            source=_ACCOUNT_ACCESS_AUTHORED,
        )
        for code, languages in account_access_wording.WORDING.items()
    ),
    # ── AGREEMENT EMAILS · `CR-190-BRC10`, 2026-10-22 ────────────────────
    # The `default` variant; the languages beside it come from
    # `agreement_wording.WORDING`, the same way (`LANGUAGE_WORDING`).
    *(
        SeedBody(
            code=code,
            name=catalogs.LISTINGS[code].name,
            subject=languages[agreement_wording.DEFAULT_WORDING_LANGUAGE][0],
            body=languages[agreement_wording.DEFAULT_WORDING_LANGUAGE][1],
            source=_AGREEMENT_AUTHORED,
        )
        for code, languages in agreement_wording.WORDING.items()
    ),
    # ── WHAT CHANGED · `DEF-BIL-4454`, 2026-10-22 ────────────────────────
    # One sentence per correction reason, printed inside the corrected-bill
    # email. The `default` variant here; every language beside it from
    # `correction_reason_wording.WORDING` (`LANGUAGE_WORDING`).
    *(
        SeedBody(
            code=code,
            name=catalogs.LISTINGS[code].name,
            subject=None,
            body=languages[correction_reason_wording.DEFAULT_WORDING_LANGUAGE][1],
            source=_CORRECTION_REASON_AUTHORED,
        )
        for code, languages in correction_reason_wording.WORDING.items()
    ),
    # ── SERVICE DISCONNECTED / RESTORED · `DEF-NOT-10649`, 2026-10-29 ────
    # The `default` variant; every language beside it from
    # `service_state_wording.WORDING` (`LANGUAGE_WORDING`).
    *(
        SeedBody(
            code=code,
            name=catalogs.LISTINGS[code].name,
            subject=languages[service_state_wording.DEFAULT_WORDING_LANGUAGE][0],
            body=languages[service_state_wording.DEFAULT_WORDING_LANGUAGE][1],
            source=_SERVICE_STATE_AUTHORED,
        )
        for code, languages in service_state_wording.WORDING.items()
    ),
    # ── the SCHEDULED REPORT · `CR-142-BRC07` `P4.10`, 2026-09-27 ────────
    # Its own source string, for the reason the three above have one.
    SeedBody(
        code="email_scheduled_report",
        name="Scheduled report ready",
        body=SCHEDULED_REPORT_BODY,
        subject=SCHEDULED_REPORT_SUBJECT,
        source=_REPORTS_LANE_AUTHORED,
    ),
    _e(
        "plan_notice_upcoming",
        "Payment plan · instalment due",
        PLAN_NOTICE_UPCOMING_SUBJECT,
        PLAN_NOTICE_UPCOMING_BODY,
    ),
    _e(
        "plan_notice_missed",
        "Payment plan · instalment missed",
        PLAN_NOTICE_MISSED_SUBJECT,
        PLAN_NOTICE_MISSED_BODY,
    ),
    # ── BR-NOT-007's third variant, added 2026-08-18 (CR-009 C-14) ───────
    # Its OWN source string, like the disconnect tiers, because it is the one
    # body authored under a ruling that names it ALONE — and because the event
    # it announces still has no writer, which a reviewer must see here.
    SeedBody(
        code="plan_notice_void",
        name="Payment plan · plan voided",
        body=PLAN_NOTICE_VOID_BODY,
        subject=PLAN_NOTICE_VOID_SUBJECT,
        source=_PLAN_VOID_AUTHORED,
    ),
    _e(
        "service_appointment",
        "Appointment scheduled / reminder",
        EMAIL_APPOINTMENT_SUBJECT,
        EMAIL_APPOINTMENT_BODY,
    ),
    _e(
        "service_work_completed",
        "Work completed summary",
        EMAIL_WORK_COMPLETED_SUBJECT,
        EMAIL_WORK_COMPLETED_BODY,
    ),
    # ── the visit, told — CR-168-BRC10 P6.1 (2026-10-04, lane SRV-5) ────
    _e(
        "service_visit_moved",
        "Visit moved",
        EMAIL_VISIT_MOVED_SUBJECT,
        EMAIL_VISIT_MOVED_BODY,
    ),
    _p("sms_visit_booked", "Visit booked · SMS", SMS_VISIT_BOOKED_BODY),
    # ── DEF-WRK-10652 (PO 2026-10-29, ruling 1A) ────────────────────────
    _e(
        "service_work_order_logged",
        "Work order logged",
        EMAIL_WORK_ORDER_LOGGED_SUBJECT,
        EMAIL_WORK_ORDER_LOGGED_BODY,
    ),
    _p("sms_work_order_logged", "Work order logged · SMS", SMS_WORK_ORDER_LOGGED_BODY),
    _p("sms_visit_moved", "Visit moved · SMS", SMS_VISIT_MOVED_BODY),
    _p("sms_technician_on_the_way", "Technician on the way · SMS", SMS_TECHNICIAN_ON_THE_WAY_BODY),
    _e("service_outage_notice", "Planned outage notice", EMAIL_OUTAGE_SUBJECT, EMAIL_OUTAGE_BODY),
    # ── Print ────────────────────────────────────────────────────────────
    _p("service_door_hanger", "Disconnect / reconnect door hanger", DOOR_HANGER_BODY),
    _p("bill_insert", "Bill insert", BILL_INSERT_BODY),
    _p("writeoff_notice", "Write-off notice", WRITEOFF_NOTICE_BODY),
    # ── BR-NOT-014's three tiers, added 2026-08-17 (CR-007) ──────────────
    # A DIFFERENT `source` from the other twenty-six on purpose: these three
    # are part QUOTE (A19 §2's tier sentence, verbatim) and part AUTHORED (the
    # letter around it and the rights footer behind `{rights_footer}`), and a
    # human reviewing this file has to be able to tell which half is which
    # without diffing against the spec.
    SeedBody(
        code="disconnect_notice_10_day",
        name="Disconnect notice · 10-day warning",
        body=DISCONNECT_10_DAY_BODY,
        source=_TIER_AUTHORED,
    ),
    SeedBody(
        code="disconnect_notice_5_day",
        name="Disconnect notice · 5-day final reminder",
        body=DISCONNECT_5_DAY_BODY,
        source=_TIER_AUTHORED,
    ),
    SeedBody(
        code="disconnect_notice_48_hour",
        name="Disconnect notice · 48-hour certified",
        body=DISCONNECT_48_HOUR_BODY,
        source=_TIER_AUTHORED,
    ),
    # ── in-app (CR-009, 2026-08-17) ──────────────────────────────────────
    SeedBody(
        code="staff_bulk_summary",
        name="Bulk action summary (in-app)",
        body=BULK_SUMMARY_BODY,
        source=_BULK_SUMMARY_AUTHORED,
    ),
    # ── in-app (CR-168-BRC10 §F, 2026-10-04) ─────────────────────────────
    SeedBody(
        code="staff_field_work",
        name="Field job update (in-app)",
        body=FIELD_WORK_BODY,
        source=_FIELD_WORK_AUTHORED,
    ),
)

#: **THE FOUR CONTRACT DEFAULTS — OFFERED, NOT PUBLISHED (CR-011 item 9).**
#:
#: Not a second `SEEDABLE`, and the difference is the whole design: nothing here
#: is written to any tenant at provisioning. BR-NOT-002 makes a contract version
#: effective-dated, `template_service.save_draft` refuses one without an
#: `effective_from`, and the CR keeps that constraint standing over this very
#: ruling — *"a draft still needs an `effective_from` a human chooses;
#: provisioning-day is not that date."* So the platform's wording is OFFERED to
#: the designer (`GET /template-catalog/{code}` serves it as `platform_default`)
#: and the System Admin publishes it with their own date, through the ordinary
#: door: draft → publish, both audited, both theirs.
#:
#: **What that buys, and it is the PO's own objection answered:** the wording
#: EXISTS, on screen, editable, one date away from live — rather than four
#: classes that refuse every save, which is what *"without default sample
#: functionalities ill not work"* was about.
#:
#: ⚠ **ONE OF THE FOUR IS A PLACEHOLDER AND IS MEANT TO BE.** The ACH
#: authorization carries `rendering.PLACEHOLDER_MARK`; it can be saved, versioned
#: and edited like any other body and it CANNOT be rendered until the utility
#: takes the marker out. PO, 2026-08-18: *"Do it; put the details, I will handle
#: it with user"*.
CONTRACT_DEFAULTS: dict[str, SeedBody] = {
    "contract_service_agreement": SeedBody(
        code="contract_service_agreement",
        name=catalogs.LISTINGS["contract_service_agreement"].name,
        body=CONTRACT_SERVICE_AGREEMENT_BODY,
        source=_CONTRACT_AUTHORED,
    ),
    "contract_deposit": SeedBody(
        code="contract_deposit",
        name=catalogs.LISTINGS["contract_deposit"].name,
        body=CONTRACT_DEPOSIT_BODY,
        source=_CONTRACT_AUTHORED,
    ),
    "contract_payment_plan": SeedBody(
        code="contract_payment_plan",
        name=catalogs.LISTINGS["contract_payment_plan"].name,
        body=CONTRACT_PAYMENT_PLAN_BODY,
        source=_CONTRACT_AUTHORED_PAYMENT_PLAN,
    ),
    "contract_autopay_authorization": SeedBody(
        code="contract_autopay_authorization",
        name=catalogs.LISTINGS["contract_autopay_authorization"].name,
        body=CONTRACT_AUTOPAY_PLACEHOLDER_BODY,
        source=_CONTRACT_PLACEHOLDER,
    ),
}


#: The paragraph a screen shows above an offered contract default, and the
#: pattern is `rights_footer.PLATFORM_DEFAULT_NOTICE`'s, deliberately: the
#: platform wrote it, the utility owns it, and the product warrants nothing.
#:
#: ⚠ **THIS IS STAFF-FACING AND IT IS NOT ON THE CUSTOMER'S DOCUMENT.** Whether a
#: default body carrying legal weight also carries a visible *"reviewed with your
#: own counsel"* line ON THE SIGNED PAGE is flagged in CR-011 as a yes/no for the
#: PO with an exact sentence attached, *not assumed* — so it is not assumed here.
#: No authored contract body contains such a line; the question is on the agenda
#: with the sentence written out.
CONTRACT_DEFAULT_NOTICE = (
    "This is wording SMART360 Next provides as a starting point. It is not legal advice "
    "and it is not your lawyer's words: what a service, deposit or payment-plan agreement "
    "has to say differs by state, by regulator and by utility. Read it against your own "
    "policies, edit anything that does not match them, and choose the date it takes "
    "effect — a contract version is effective-dated, so nothing is live until you publish "
    'it with a date. A version you have not edited is shown as "platform default".'
)

#: The badge on an untouched contract default, beside the row — the same two
#: lengths `rights_footer` keeps: the badge marks a row, the notice states the
#: rule.
CONTRACT_DEFAULT_LABEL = "Platform default — review before you publish it"


def default_body_for(code: str) -> SeedBody | None:
    """The platform's offered wording for a contract class, or None.

    None for every non-contract class, because those are PUBLISHED at
    provisioning and the published row is the answer — an offer beside a live
    body would be two sources for one document.
    """
    return CONTRACT_DEFAULTS.get(code)


def is_placeholder(code: str) -> bool:
    """True when this class's platform default refuses to render as shipped."""
    offered = CONTRACT_DEFAULTS.get(code)
    return offered is not None and rendering.PLACEHOLDER_MARK in offered.body


#: EVERY class this module owns that is NOT planted, and the sentence a screen
#: shows in its place. Keyed by class code so `GET /notification-templates` can
#: answer per row rather than as one banner — DEF-163's own finding was that a
#: gap nobody can see per class is a gap nobody acts on.
#:
#: The two OQ-243/OQ-244 entries are written out here; the other sixteen take
#: `catalogs.CLASSES_WITHOUT_CATALOG`'s own reason, which already names OQ-206
#: or OQ-207, because two copies of that sentence is the drift hard-won law 1
#: warns about.
#: A19 §2's three tier sentences, quoted in OQ-243 in full.
#:
#: ⚠ **THEIR JOB CHANGED ON 2026-08-17 AND THE OLD JOB IS WORTH RECORDING.**
#: Until today this dictionary existed ONLY to explain why each slot was empty —
#: *"they are signed and they are still unplantable … what remains is the rights
#: footer, whose five sentences no signed document writes (OQ-253)"* — and it was
#: never a body. The PO then ruled that the platform writes those five sentences
#: (*"you build default langauge and let Utility user change it as they want"*),
#: so each tier now HAS a body and each body carries its sentence verbatim.
#:
#: The dictionary stays, and is now the CONTRACT the test checks: every tier body
#: in `SEEDABLE` must contain its sentence character for character, so an edit
#: that rewords a signed paragraph goes RED instead of quietly reaching a
#: customer. It is the same mechanism the two A13 quotes have, applied to the
#: three paragraphs where it matters most.
_TIER_SENTENCES: dict[str, str] = {
    "disconnect_notice_10_day": (
        "Your account is past due in the amount of {balance}. Please pay by "
        "{pay_by_date} (10 days) to avoid service interruption."
    ),
    "disconnect_notice_5_day": (
        "FINAL REMINDER. Service to {service_address} is scheduled for disconnection on "
        "{cut_date} unless {balance} is received. A reconnect fee of {reconnect_fee} "
        "applies to restore service."
    ),
    "disconnect_notice_48_hour": (
        "NOTICE OF DISCONNECTION. Service will be disconnected on {cut_date} ({48h}). To "
        "avoid disconnection pay {balance} immediately. Medical/critical-care customers: "
        "call {support_phone}."
    ),
}


NOT_SEEDED: dict[str, str] = {
    # ── BR-NOT-014's three slots: SEEDED as of 2026-08-17 ─────────────────
    # ⚠ THE THREE TIER ENTRIES THAT USED TO BE HERE ARE GONE, and their absence
    # is the CR-007 change: each said *"no body validates without a footer nobody
    # has written. OQ-253 — nothing is invented, so no disconnection notice can
    # be generated at this tier yet."* That was true for one day. The PO ruled
    # that the platform writes the footer (*"we provide default option for all 5
    # … if Utility wants to over ride it let them do it"*), the five clauses live
    # in `rights_footer.py`, the three bodies are in `SEEDABLE` above, and a
    # disconnection notice can now be produced.
    #
    # The LEGACY single class below stays unplantable, and for a reason that has
    # nothing to do with wording — see its own entry.
    # Provenance for support: A19 §2 · BR-NOT-014 · superseded by the three
    # tier classes, CR-007 2026-08-17, hidden through
    # `catalogs.SUPERSEDED_CLASSES`. A variant holds ONE body per (class,
    # consumer category, language) and there is no tier column, so a body here
    # would go out as the wrong stage's letter. That is why it stays empty.
    "disconnect_notice": (
        "This single disconnection notice has been replaced by three separate "
        "notices, one for each stage of the disconnection process. Use those "
        "instead — they are in this list. This one is kept only so older records "
        "still read correctly, and it is deliberately left with no wording."
    ),
    # ── THE PRINTED RETURNED-PAYMENT LETTER — its blank entry LEFT 2026-10-30 ─
    # It stood here from DEF-2473 (2026-08-30) saying *"Nobody has written the
    # wording for a printed returned-payment letter yet, so this one is
    # deliberately blank."* The PO ruled the audit's L2-04 fixed on 2026-10-30
    # (*"Rest we will fix"* — a proper NSF email and letter), so the class is
    # SEEDED from `payment_returned_wording` as a default the utility edits
    # (`DEF-PAY-10744`), the posture OQ-244's ruling set for the contracts.
    # ── THE FOUR CONTRACTS, REWRITTEN 2026-08-18 (CR-011 item 9) ──────────
    # ⚠ **THE SENTENCE THAT USED TO BE HERE SAID THERE WAS NO BODY. THERE IS A
    # BODY.** The old entry read *"A19 §3 catalogues every token of the
    # payment-plan agreement verbatim EXCEPT the instalment schedule table …
    # so a seeded agreement would be e-signed stating the total and not one due
    # date or instalment amount. BR-NOT-002 also makes every contract version
    # effective-dated … OQ-244."* The PO ruled the wording written anyway
    # (*"already answer - provide default and allow user to change"*), so what
    # these four rows now report is a DIFFERENT and much narrower fact: the
    # platform has wording, it is offered on the designer, and it is not
    # PUBLISHED because only a human can date it.
    #
    # The distinction matters on screen. "Nobody has written this" tells a
    # utility to go and write a contract; "here is our wording, pick the date it
    # takes effect" tells them to click twice. Same empty version table, two
    # completely different jobs to do.
    # Provenance for support: PO ruling 2026-08-18 (*"provide default and allow
    # user to change"*, and for this class *"create this dont leave it open"*).
    # Unpublished at provisioning because BR-NOT-002 effective-dates every
    # contract version. `{schedule_table}` is BR-NOT-016 and the repeating-block
    # renderer is the remainder of OQ-244.
    "contract_payment_plan": (
        "Wording for this agreement is ready and waiting for you on the designer. "
        "It is not in use yet because only you can choose the date it takes "
        "effect: open it, change the wording if you want to, pick that date, then "
        "publish. One thing to know first — the agreement prints the instalment "
        "schedule inside itself, and that table is not built yet, so it prints as "
        "\u2014\u2014 and the agreement says on its face not to sign a blank "
        "schedule."
    ),
    # Provenance for support: PO ruling 2026-08-18 (*"already answer - provide
    # default and allow user to change"*), which closed the authoring half of
    # OQ-206 for the contracts. Unpublished per BR-NOT-002 effective-dating.
    "contract_service_agreement": (
        "Wording for this agreement is ready and waiting for you on the designer. "
        "It is not in use yet because only you can choose the date it takes "
        "effect. The wording sets out the shape of the agreement and leaves every "
        "figure and every period to your own published policy."
    ),
    # Provenance for support: PO ruling 2026-08-18, the same one that reached
    # OQ-206's other two contracts. Unpublished per BR-NOT-002. No refund period
    # and no interest rate are ruled anywhere — the same absence `email_deposit`
    # carries, OQ-260.
    "contract_deposit": (
        "Wording for this agreement is ready and waiting for you on the designer. "
        "It is not in use yet because only you can choose the date it takes "
        "effect. The wording states what a deposit is and is not. It names no "
        "refund period and no interest rate, so both point at your own deposit "
        "policy — check it says what you want before you publish."
    ),
    # Provenance for support: PO ruling 2026-08-18 (*"Do it; put the details, I
    # will handle it with user"*). The eight items are
    # `catalogs.CONTRACT_INPUT_REQUIREMENTS`. Unpublished per BR-NOT-002. This is
    # the one document where wording written by inference would look official and
    # could be wrong, so the scheme text was never ours to write.
    "contract_autopay_authorization": (
        "This is a placeholder, not finished wording, and the product will not "
        "print it until you replace it. An authorization for recurring bank "
        "debits has to follow the NACHA Operating Rules, and getting that wording "
        "right is a matter for your bank and your legal adviser rather than "
        "something this platform should write for you. The placeholder lists, in "
        "plain English, the eight things they need to settle. Paste their wording "
        "over it, delete the marker line, pick the date it takes effect, then "
        "publish."
    ),
}


def _tenant_id() -> Any:
    """Hard rule 1: no tenant table is touched without `app.tenant_id` set."""
    tenant_id = core_tenancy.current_tenant_id()
    if tenant_id is None:
        raise errors.AuthError(errors.AUTH_TENANT_UNRESOLVABLE, br_ref="BR-TEN-003")
    return tenant_id


def absent_reason(code: str) -> str | None:
    """Why this class has no platform body — or None when it has one.

    ONE answer for the seeder, the API row and the test, so a screen can never
    show a reason the seeder does not hold. The three dictionaries are
    CONSULTED rather than copied — a second copy of any of these sentences is
    the drift hard-won law 1 warns about:

      * `NOT_SEEDED` — this file's own two structural refusals;
      * `catalogs.NOT_AUTHORED_BY_PO_RULING` — the classes the authoring
        rulings did not reach and why ([AMENDED 2026-08-18] down to the four
        contracts: the plan-void notice left under C-14's own ruling);
      * `catalogs.CLASSES_WITHOUT_CATALOG` — a class with no palette, which
        after 2026-08-17 means only the four contracts.
    """
    if any(entry.code == code for entry in SEEDABLE):
        return None
    explicit = NOT_SEEDED.get(code)
    if explicit is not None:
        return explicit
    ruled = catalogs.not_authored_reason(code)
    if ruled is not None:
        return ruled
    return catalogs.CLASSES_WITHOUT_CATALOG.get(code)


#: WHY EACH ABSENCE HOLDS — as CITATIONS, beside the English rather than inside it.
#:
#: ⚠ ADDED 2026-08-24 (DEF-630), AND THE DEFECT IT CLOSES IS HARD-WON LAW 1.
#: These reasons used to name their rule INSIDE the sentence — *"BR-NOT-014
#: replaced the single disconnect notice"*, *"OQ-244 still holds"* — and they
#: were rewritten into a clerk's English, correctly: an operator reading *"no
#: body: OQ-244"* learns nothing, and an internal reference in served prose is
#: the class G28 exists to stop. But the rewrite carried the citation nowhere.
#: It survived only in the COMMENTS above each entry, and a comment claiming a
#: guarantee is not the guarantee — nothing served it, no caller could reach it,
#: and the tests that still asserted it went red for the right change.
#:
#: So the citation travels as DATA on the row, the way `br_ref=` already travels
#: on `core.errors` refusals and `data-br-ref` travels to the frontend (DEF-322).
#: The human reads the sentence; support reads the reference; neither is inside
#: the other. A class added to `NOT_SEEDED` with no entry here is a class whose
#: absence nobody can trace, so `absent_refs` returns an EMPTY tuple rather than
#: guessing, and the seeder reports it as untraced instead of inventing a rule.
ABSENT_REFS: dict[str, tuple[str, ...]] = {
    # The legacy single class, superseded by the three tier classes.
    "disconnect_notice": ("BR-NOT-014", "A19 §2", "CR-007"),
    # The four contracts: BR-NOT-002 makes a contract version effective-dated,
    # and that date is a human's choice rather than provisioning day's — which
    # is why platform wording exists and is not published.
    "contract_service_agreement": ("BR-NOT-002",),
    "contract_deposit": ("BR-NOT-002",),
    # …plus the one remainder that is genuinely unbuilt: A19 §3 catalogues every
    # token except the instalment SCHEDULE block, so `{schedule_table}` renders
    # `——` and OQ-244 is what still holds it.
    "contract_payment_plan": ("BR-NOT-002", "OQ-244"),
    # …plus the reason this one is a deliberate PLACEHOLDER the renderer
    # refuses: BR-NOT-004 type ④ is NACHA-required for recurring ACH, and its
    # wording is prescribed by a scheme this repo does not hold.
    "contract_autopay_authorization": ("BR-NOT-002", "BR-NOT-004"),
}


def absent_refs(code: str) -> tuple[str, ...]:
    """The citations behind `absent_reason(code)` — never inside the sentence.

    Empty when the class HAS a body (there is no absence to explain) and empty
    when an absence is untraced, which is a real state and is reported as one.
    """
    if absent_reason(code) is None:
        return ()
    return ABSENT_REFS.get(code, ())


def _published(template: tm.NotificationTemplate) -> tm.NotificationTemplateVersion | None:
    """This variant's live undated version, if it has one.

    Undated only, and deliberately: the effective-dated half belongs to the
    CONTRACT classes (BR-NOT-002) and this seeder plants none of them, so a row
    with an `effective_from` here would be something no path in this file wrote.
    """
    return tm.NotificationTemplateVersion.objects.filter(
        tenant_id=template.tenant_id,
        template=template,
        status=tm.VERSION_PUBLISHED,
        effective_from__isnull=True,
    ).first()


@transaction.atomic
def _seed_one(
    entry: SeedBody,
    *,
    actor: Any,
    at: datetime | None,
    language: str = tm.VARIANT_DEFAULT,
) -> dict[str, Any]:
    """Plant ONE class's `(default, <language>)` variant. Insert-missing.

    `language` is `default` for every class but the Account access ones
    (`CR-188-BRC10`), which also plant one variant per registry language —
    `seed_language_variants`. Never overwrites a published variant."""
    tenant_id = _tenant_id()
    klass = catalogs.catalog_for(entry.code)
    if klass is None:  # pragma: no cover — SEEDABLE is checked by the test suite
        raise errors.ValidationError(
            f"{entry.code!r} has no merge-variable catalogue, so no body can be validated "
            "against it. A class in SEEDABLE without a catalogue is a body nothing checks."
        )
    # ⚠ **A CONTRACT CAN NEVER BE PLANTED HERE (BR-NOT-002), AND THIS IS A
    # STRUCTURAL REFUSAL RATHER THAN A CONVENTION (CR-011 item 9).** Every
    # contract version is effective-dated and this seeder has no date to give:
    # `on_date` is provisioning's business date, which the CR rules out in as
    # many words — *"a draft still needs an `effective_from` a human chooses;
    # provisioning-day is not that date."* The alternative is worse still: a row
    # written with `effective_from = NULL` is returned by
    # `template_service._published_version` BEFORE any dated version, so the
    # platform's body would shadow every version the utility ever dates.
    # A lane adding a contract to SEEDABLE would break neither the palette check
    # nor `validate_body`; it would simply publish one. So it stops here.
    if klass.group == catalogs.GROUP_CONTRACT:
        raise errors.BizError(
            errors.BIZ_STATE,
            br_ref="BR-NOT-002",
            message_key="notifications.templates.contractCannotBeSeeded",
            params={
                "code": entry.code,
                "detail": (
                    f"{entry.code!r} is a CONTRACT class and cannot be seeded. BR-NOT-002 "
                    "makes every contract version effective-dated and there is no human in "
                    "a provisioning transaction to choose that date. The platform's wording "
                    "for the four contracts is OFFERED instead — `CONTRACT_DEFAULTS`, "
                    "served on the designer — and the System Admin publishes it with their "
                    "own date."
                ),
            },
        )

    template, created = tm.NotificationTemplate.objects.get_or_create(
        tenant_id=tenant_id,
        code=entry.code,
        category=tm.VARIANT_DEFAULT,
        language=language,
        defaults={"group": klass.group, "channel": klass.channel, "name": entry.name},
    )
    # ⚠ REPAIR THE CHANNEL ON A ROW THAT PREDATES THE CATALOG (DEF-210).
    # `template_service._group_channel` GUESSES group and channel from the code
    # PREFIX for a class with no catalog — so `plan_notice_upcoming`, registered
    # by anyone who opened it on SET-10 before today, is sitting on
    # `printable`/`pdf_print` because its code does not start with `email_`. Now
    # that the class HAS a catalog, the guess is wrong, and a wrong channel is
    # not cosmetic: it is what the subject-line field and the SMS character
    # counter are gated on, and it is what the dispatcher matches a queue row
    # against. The version rows are append-only and untouched; this is the
    # PARENT row, which carries no body and no pin.
    if not created and (template.group != klass.group or template.channel != klass.channel):
        before = {"group": template.group, "channel": template.channel}
        template.group, template.channel = klass.group, klass.channel
        template.save(update_fields=["group", "channel", "updated_at"])
        audit.money_action(
            actor,
            AUDIT_REGISTERED,
            AUDIT_ENTITY_TEMPLATE,
            str(template.pk),
            before=before,
            after={
                "code": entry.code,
                "group": klass.group,
                "channel": klass.channel,
                "source": SEED_SOURCE,
                # DEF-210 (the class gained a catalog on 2026-08-17) and the
                # guessing code path are named HERE and not in the value: S61
                # renders this sentence to a clerk (DEF-2377).
                "reason": "this wording was registered before its class had a "
                "catalogue, so its group and delivery channel were worked out from "
                "the code and turned out to disagree with the catalogue.",
            },
        )
    if created:
        audit.money_action(
            actor,
            AUDIT_REGISTERED,
            AUDIT_ENTITY_TEMPLATE,
            str(template.pk),
            after={
                "code": entry.code,
                "category": tm.VARIANT_DEFAULT,
                "language": language,
                "group": klass.group,
                "channel": klass.channel,
                "source": SEED_SOURCE,
            },
        )

    live = _published(template)
    if live is not None:
        return {
            "code": entry.code,
            "created": False,
            "already_present": True,
            "template_id": str(template.pk),
            "version": live.version,
            "reason": (
                f"this tenant already publishes {entry.code!r} v{live.version} — "
                "insert-missing left it untouched"
            ),
        }

    # THE ONE CHECK THAT IS NEVER SKIPPED: the body has to pass the same palette
    # and mandatory-content rules a human's save would (US-NOT-005 TC-5). The
    # SUBJECT goes through it too — an email subject is merged text on the same
    # palette, and `{meter_no}` in a subject line reaches the customer's inbox
    # exactly as surely as one in a body reaches the page.
    rendering.validate_body(entry.code, entry.body, subject=entry.subject)

    highest = (
        tm.NotificationTemplateVersion.objects.filter(tenant_id=tenant_id, template=template)
        .order_by("-version")
        .values_list("version", flat=True)
        .first()
        or 0
    )
    version = tm.NotificationTemplateVersion.objects.create(
        tenant_id=tenant_id,
        template=template,
        version=highest + 1,
        status=tm.VERSION_PUBLISHED,
        # Email classes carry a subject; printable and SMS classes carry NULL,
        # which is "this class has no subject" rather than "somebody saved an
        # empty one" (template_models). The subject is what CR-007's acceptance
        # item asks the designer to show, and it could never render while every
        # seeded row was a print class.
        subject=entry.subject,
        # No preheader on any authored body. A preheader is the grey line an
        # inbox shows after the subject, and writing one means writing a second
        # subject for every email — real work with its own review, not a field
        # to fill because the column exists.
        preheader=None,
        body=entry.body,
        effective_from=None,
        # NULL on purpose, and the null is the TRUE answer rather than a missing
        # one: no person published this. WHO did it is the audit row's
        # `source: provisioning_seed`.
        created_by=None,
        published_by=None,
        published_at=at,
    )
    audit.money_action(
        actor,
        AUDIT_PUBLISHED,
        AUDIT_ENTITY_VERSION,
        str(version.pk),
        after={
            "code": entry.code,
            "category": tm.VARIANT_DEFAULT,
            "language": language,
            "version": version.version,
            "status": tm.VERSION_PUBLISHED,
            "spec_source": entry.source,
            "source": SEED_SOURCE,
            "affects": "future renders only — queued documents carry their own pin",
        },
    )
    return {
        "code": entry.code,
        "created": True,
        "already_present": False,
        "template_id": str(template.pk),
        "version": version.version,
        "reason": f"published {entry.code!r} v{version.version} from {entry.source}",
    }


def seed_language_variants(
    code: str, *, actor: Any = None, at: datetime | None = None
) -> dict[str, Any]:
    """`CR-188-BRC10` — plant one published variant per REGISTRY language.

    The languages come from the product's registry
    (`tenancy_seam.platform_languages`), never from a list here (PO 2026-10-22,
    *"don't do any hardcoding"*); the words from `account_access_wording`.
    Insert-missing: a variant a utility has published is never touched, so a
    later release only ADDS. A registry language with no written wording is
    reported in `unwritten` and served by the `default` variant.
    """
    from apps.notifications import tenancy_seam

    entry = next((e for e in SEEDABLE if e.code == code), None)
    wording = LANGUAGE_WORDING.get(code)
    if entry is None or wording is None:
        return {"code": code, "seeded": [], "unwritten": [], "reason": "not a language-seeded class"}
    seeded: list[dict[str, Any]] = []
    unwritten: list[str] = []
    for language in tenancy_seam.platform_languages():
        words = wording.wording_for(code, language)
        if words is None:
            unwritten.append(language)
            continue
        subject, body = words
        variant = SeedBody(
            code=code, name=entry.name, subject=subject, body=body, source=entry.source
        )
        seeded.append(_seed_one(variant, actor=actor, at=at, language=language))
    return {"code": code, "seeded": seeded, "unwritten": unwritten}


def ensure_seeded(code: str, *, actor: Any = None) -> None:
    """The `default` variant and every language variant of one Account access
    class, for the tenant in context — insert-missing, so cheap when present.

    Called at QUEUE time (`staff_access_events`) so a utility provisioned before
    `CR-188-BRC10` is never queued a message pinned to nothing, and by
    `notifications/0023` for every existing utility."""
    entry = next((e for e in SEEDABLE if e.code == code), None)
    if entry is None:
        return
    _seed_one(entry, actor=actor, at=None)
    seed_language_variants(code, actor=actor)


def seed_notice_templates(
    actor: Any = None, *, on_date: date, at: datetime | None = None
) -> dict[str, Any]:
    """DEF-163 — the tenant's notice templates, planted at provisioning.

    Called through `apps.tenancy.seams.seed_notice_templates` inside the
    provisioning transaction, and again by `manage.py seed_demo --tenant
    <subdomain>` for a tenant that already exists. Idempotent both ways.

    `on_date` is BR-TEN-043's business date and is the CALLER's — there is no
    clock in this module. It is carried on the RESULT rather than written to a
    column: `notification_template_versions` dates a publish with `published_at`
    (a timestamp), and `at` is the optional stamp for it; a version with neither
    is still published, exactly as one published by a human at an unknown hour
    would be.

    Returns `{"seeded": [...], "absent": [...], "reason": "..."}` so a caller can
    REPORT what landed rather than infer it — the shape `seed_bill_templates`
    established, widened because this seeder plants some classes and refuses
    others in the same run and both halves have to be visible.
    """
    _tenant_id()
    seeded = [_seed_one(entry, actor=actor, at=at) for entry in SEEDABLE]
    # CR-188-BRC10 — the Account access classes in every registry language;
    # CR-190-BRC10's two agreement emails beside them (merge 2026-10-22).
    language_variants = [
        seed_language_variants(code, actor=actor, at=at) for code in LANGUAGE_WORDING
    ]
    absent = [
        # `refs` is DEF-630's addition: the citation beside the English, never
        # inside it. See `ABSENT_REFS`.
        {"code": code, "reason": reason, "refs": list(absent_refs(code))}
        for code in sorted({*catalogs.CATALOGS, *catalogs.CLASSES_WITHOUT_CATALOG})
        if (reason := absent_reason(code)) is not None
        # Bills and statements are BILLING's registry (B2 r10 #4) and are
        # seeded by `apps.billing.services.seed_bill_templates`. Reporting them
        # absent here would offer one document two homes.
        and code not in ("bill_residential", "bill_commercial", "statement")
    ]
    created = [row["code"] for row in seeded if row["created"]]
    # ⚠ A THIRD LIST, ADDED 2026-08-18 (CR-011 item 9), AND IT EXISTS BECAUSE
    # "seeded" AND "absent" COULD NOT TELL THE TRUTH BETWEEN THEM. The four
    # contracts are not seeded, and they are no longer absent in the sense the
    # word had here — the platform HAS their wording and a human's date is the
    # only thing between it and live. Reporting them as absences would tell an
    # operator to go and write four contracts.
    offered = [
        {
            "code": code,
            "name": entry.name,
            "is_placeholder": is_placeholder(code),
            "reason": (
                f"{code!r} has platform wording offered on the designer and NO published "
                "version: BR-NOT-002 makes a contract version effective-dated and that "
                "date is a human's choice, not provisioning day's"
            ),
        }
        for code, entry in sorted(CONTRACT_DEFAULTS.items())
    ]
    return {
        "on_date": on_date.isoformat(),
        "seeded": seeded,
        "absent": absent,
        "offered": offered,
        "language_variants": language_variants,
        "reason": (
            (
                f"published {', '.join(created)}"
                if created
                else "every platform-authored notice body was already published"
            )
            + f"; {len(offered)} CONTRACT class(es) carry platform wording that is OFFERED "
            "rather than published, because BR-NOT-002 makes a contract version "
            "effective-dated and only a human can choose that date (CR-011 item 9, PO "
            "2026-08-18: *'already answer - provide default and allow user to change'*) — "
            "one of the four is a deliberate PLACEHOLDER the renderer refuses, the NACHA "
            "autopay authorization. "
            f"{len(absent)} class(es) have no platform body at all and each carries its "
            "reason. The published bodies were authored under four PO rulings: "
            "twenty-eight on 2026-08-17 (*'please define it for this product'*), "
            "BR-NOT-014's three disconnect tiers the same day (*'you build default "
            "langauge and let Utility user change it as they want'*), the plan-void "
            "notice on 2026-08-18 under C-14 (*'you give default language for the "
            "plan-void notice only'*) — wording ahead of a flow nothing fires yet — and "
            "the four contracts the same day under CR-011 item 9"
        ),
    }


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-NOT-005@0f31c8a (sha1[:7] of the four sources this slice was authored from, concatenated in order: 04-docs/05-modules/10-notifications/06-epics/EP-NOT-02-templates-rendering.md — US-NOT-005 §1/§3, US-NOT-006 §1 — · 10-notifications/02-business-rules.md — BR-NOT-001/002/006 — · 04-docs/01-spec/13-copy-and-microcopy.md §"Reminder / notice templates (previews)" + 04-docs/01-spec/19-document-templates.md §2/§3 + r8 revision · 12-governance/10-defect-log.csv DEF-163)
# generated: 2026-08-16 by story-coder (DEF-163 notice-template seeding lane)
# checklist: A✔ B✔ C✔ D=deferred(no new API surface — GET /notification-templates already reports per class and now reports this seeder's own answer) E✔(the S8 templates card renders the per-class reason) F✔ G✔ H=deferred(PO 2026-08-09)
# gates: ruff✔ black✔ · G7 (this file is enrolled as a guarded path — it decides the words a customer reads) · G26 required-rows carries `notification_templates` TWICE (the resolver and the generation path) and its discovery clause was widened to the second phrase family DEF-163 named ("no published … resolves") AND to match the JOINED raise text, red-proved three ways · tests/test_def_163_notice_templates_seeded.py provisions a tenant through the REAL service and then asks the REAL resolver, with nothing in between (the shape test_def_123 established, and the only shape that can catch this class) · PROVED IN A BOOTED BROWSER, red first: with the two seeded rows removed from the E2E database — the exact state of every tenant before this lane — `e2e/DEF-163-notice-templates.spec.ts` FAILED on `expect(dunningRow).toContainText(/Version 1/)`, receiving *"dunningno published 'dunning' template resolves for category 'default' in language 'default' …"*; `manage.py seed_demo --tenant brazosbend` repaired it through the operator's own door and the same spec passed, census "app-server 10 assertions · 1 ran · 0 skipped"
# exceptions: (1) TWO BODIES, NOT FOUR. DEF-163 reports A19 as giving sentences
#         for the three disconnect tiers and the payment-plan agreement as well;
#         building it showed both are unplantable for STRUCTURAL reasons rather
#         than missing prose — one body slot for three tiers (OQ-243) and a
#         repeating schedule block the renderer cannot express (OQ-244) — and
#         both are minted rather than guessed. The defect row is amended to say
#         so.
#         (2) NO DISPATCH. Planting a template lets a notice be RENDERED and
#         QUEUED; nothing sends (BR-NOT-013, PO 2026-08-16: *"I already confirm
#         it before it Queue them"*).
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
