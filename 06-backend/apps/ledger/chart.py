# ── Trace ──────────────────────────────────────────────
# Story:    US-LED-005 (chart of accounts: SEEDED AT PROVISIONING, tenant-
#           customizable — TC-1 "seeded chart present (incl. AR +
#           opening-clearing rows per r9 #3)") ·
#           US-LED-017 (cost-of-service chart section — FINANCE RE-SIGNED
#           2026-08-18, see the docstring addendum; TC-1 every tenant seeds all
#           eight cost rows per CR-010 B-9; TC-5 no surface presents an unsigned
#           code as signed)   Screens: S56 · S73
# Rules:    BR-LED-037 (the cost section is an addition to B5 line 74 ❄️ and
#           needed a finance re-sign via HUMAN-GUIDE §6 — TAKEN 2026-08-18 by
#           dated addendum; the rule's marked-unsigned posture still governs any
#           FUTURE row added without a signature) · BR-LED-038 (per-service cost narrowing —
#           SUPERSEDED 2026-08-18 with OQ-115's, see below; its own-pointer-
#           survives-a-re-seed half stands) ·
#           BR-BIL-010 (service → revenue GL with an optional usage/base split;
#           AR / deposit-liability / clearing / write-off designations) ·
#           BR-LED-014 (the GL mapping page this chart feeds) · BR-RAT-024
#           (the 10-service platform catalog these attributes hang off) ·
#           PO ruling 2026-08-11 closing OQ-115 (4160/4170 created · the seeded
#           account is a DEFAULT a tenant may override · ⚠ its third half —
#           "a tenant is seeded only the revenue accounts for the services it
#           actually sells" — is SUPERSEDED by CR-010 B-9, PO 2026-08-17: "9 -
#           A full ~40 accounts for every tenant, as you said") ·
#           CR-010 B-8 (PO 2026-08-17: 4180, the twelfth designation's home)
# Tests:    06-backend/tests/test_us_led_005_gl_designations.py ·
#           06-backend/tests/test_us_led_017_cost_chart.py
# Impacts:  apps/ledger/models.py (the CHECK on `ledger_accounts.designation`
#           reads GL_DESIGNATIONS from here) · apps/ledger/services.py (the
#           seed) · apps/ledger/selectors.py (the published reads) ·
#           apps/tenancy/services.py (points a tenant_service at its revenue
#           accounts at provisioning)
# ───────────────────────────────────────────────────────
"""The seed chart of accounts, and the ELEVEN GL designations.

HUMAN-OWNED · HUMAN-REVIEW-PENDING — this file is the machine copy of a
finance-signed table (B5 line 74, ❄️ FROZEN 2026-08-08) and of two PO rulings
(OQ-110 and OQ-115, both 2026-08-11). AI-authored 2026-08-11 under the PO ruling
of 2026-08-09; row in 12-governance/09-human-review-ledger.md.

**ALL TWENTY-FIVE ROWS OF `SEED_CHART` ARE FINANCE-SIGNED** (this line read
"twenty-four of twenty-five" for the hours between 4180 landing and its re-sign,
both on 2026-08-18; it read "all twenty-four" before 4180 existed). Twenty-two are transcribed
from B5 line 74 (❄️ FROZEN 2026-08-08); 4160 Storm water and 4170 Thermal/Heat
were added 2026-08-11 under the PO's closure of OQ-115 and **finance re-signed
the same day** by dated addendum. The twenty-fifth is **4180 Budget billing
variance**, added under the PO's CR-010 B-8 ruling of 2026-08-17 (verbatim:
*"8 - A ✅ 4180 "Budget billing variance", revenue, signed=False (the 4160/4170
precedent)"*).

⚠ **IT WAS FINANCE RE-SIGNED ON 2026-08-18, TOGETHER WITH THE EIGHT COST ROWS**
(Product Owner, working chat session; the PO is the sign-off authority per their
own ruling of 2026-08-11). 4180 now carries `signed=True` and
`PENDING_FINANCE_RE_SIGN` is `()`. **ALL TWENTY-FIVE ROWS OF `SEED_CHART` ARE
SIGNED**, and so are the eight rows of `COST_OF_SERVICE_CHART`.

⚠ **THAT COUNT MOVED AGAIN ON 2026-08-28 AND THE SENTENCE ABOVE IS NOW HISTORY
(hard-won law 1 — read it in the past tense).** The PO's discount ruling of that
day added a TWENTY-SIXTH row, **Customer discounts (contra-revenue)**,
carrying the thirteenth designation `discount_contra_revenue`. It is
`signed=False` and it is in `PENDING_FINANCE_RE_SIGN` — the same posture
4160/4170 and 4180 were declared under — so the tuple is **not** `()` any more
and the honest count is **twenty-five signed of twenty-six**. What the PO ruled
is that a discount gets a code of its own in a category of its own.

⚠ **AND ON 2026-09-01 THE PO RULED ON THAT ROW'S NUMBER AND ITS TYPE, AND BOTH
MOVED (CR-061).** This paragraph said the NUMBER and the NAME *"are this lane's
reading of the chart's own ladder and are not a finance signature"* — the second
half is still true and the first half is not. The PO was shown both open
questions and answered both:

    *"no, you cannot file discount under revenue"*
    *"if you need differnt number assign it - im okay with it"*

So the row is **4760 Customer discounts (contra-revenue)**, typed
**`contra_revenue`** — a SIXTH `LEDGER_ACCOUNT_TYPES` value, where this file
argued for five. **4760** because the reference chart the PO supplied gives
`4300` to *Electric Energy Revenue* and files revenue adjustments at
`4700`-`4750`. **The count is unchanged at twenty-five signed of twenty-six**:
one row was re-filed, none was added, and `signed=False` did not move, because a
ruling on a number and a type is not a finance re-sign of the chart. B5 line 74
is still ❄️ un-edited.

⚠ **AND THE COUNT MOVED TWICE MORE, ON ONE DAY — 2026-09-02. READ EVERY COUNT
ABOVE IN THE PAST TENSE (hard-won law 1).** `CR-063` added **4155 Fire** and
`CR-066` added **NINE**: `4600` Connection & new-service fees · `4610`
Disconnection & reconnection fees · `4630` Field-service & meter fees · `4640`
Equipment recovery & penalties · `4650` Billing & payment fees · `4700` Billing
adjustment · `4710` Leak adjustment · `4720` Rate / meter correction · `4730`
Customer credit. **`SEED_CHART` is now thirty-six rows, twenty-five of them
finance-signed and ELEVEN not** — 4155, the nine above, and 4760. Do not read
that eleven off this paragraph either: `PENDING_FINANCE_RE_SIGN` is DERIVED from
the rows, so the tuple is the answer and this sentence is a note.

**WHAT THE PO APPROVED FOR THE NINE, AND WHAT THEY DID NOT.** They were shown
CR-066's three tables in plain English, with each account's NAME and NUMBER
beside the charge codes and adjustment reasons that would point at it, and ruled
*"Table 1 — the 28 charge codes - these are all correct - you can apply them as
part of Seed data"*, *"Table 2 — the five adjustment reasons - these are all good
- please apply these"* and *"Please apply these - Table 3 — discounts."* **That
is an approval of the MAPPING.** It is not a finance signature on the chart, no
dollar figure was attached to any of the nine, and no B4/B5 figure moved — this
change says where an amount POSTS and never what it is. All nine carry
`signed=False` and every surface that offers them says so.

**WHAT WAS SHOWN TO THE PO, because a signature covers only what was shown:**
the nine codes and names, written out in plain English — **4180 Budget billing
variance (Revenue)**, and **5100 Purchased power · 5110 Purchased water · 5120
Sewer treatment & disposal · 5130 Trash hauling & disposal · 5140 Purchased gas
· 5145 Broadband transport · 5200 Operations & maintenance · 5300
Infrastructure** — together with what 4180 is FOR (where the difference lands
when a budget-billing customer has paid more or less than they used; the worked
case is a **$50.87** variance that previously refused by name and blocked the
bill) and the explicit statement that **no dollar figure is attached to any of
the nine** and that **B4/B5 stay frozen — these rows sit beside them**. The PO
ruled *"Im okay with it"* and, when the nine rows were then written out in full,
confirmed the answer already stood.

**WHAT THE SIGNATURE DOES NOT COVER:** any amount, rate or default posted to
these accounts, and any change to a B4 or B5 figure. Those need their own
ruling. Every signed code, name and
designation→code pairing comes from a signed source, named per line.

⚠ **CORRECTED 2026-08-15 (hard-won law 1).** This paragraph said in bold that
4160 and 4170 *"carry `signed=False`"* and were *"listed in
`PENDING_FINANCE_RE_SIGN`"*. Neither had been true since the re-sign four days
earlier: both rows carry `signed=True` and the tuple is `()`. A docstring
claiming a guarantee is not the guarantee — and this one claimed the ABSENCE of
one, which is the more dangerous direction, because a reader checking whether
anything in this file is unsigned would have been sent to the wrong two rows.
The rows that were unsigned when that correction was written were the eight of
`COST_OF_SERVICE_CHART` at the bottom of this file, listed in
`PENDING_FINANCE_RE_SIGN_COST`, plus **4180** in the signed chart's own tuple,
listed in `PENDING_FINANCE_RE_SIGN`. ⚠ **RE-COUNTED AGAIN 2026-08-18 AFTER THE
RE-SIGN: THERE WERE NONE.** All nine were finance re-signed that day (the
addendum above), both tuples were `()`, and every row in this file — signed
chart and cost section alike — carried `signed=True`. The count is stated as a
count, not as a list, precisely so the next reader can check it against the
tuples instead of trusting this sentence. ⚠ **AND ON 2026-08-28 IT BECAME ONE:
the discount account.** `PENDING_FINANCE_RE_SIGN` was `("4760",)` — it read
`("4300",)` until CR-061 renumbered the row on 2026-09-01 — **and on 2026-09-02
it became ELEVEN**: `4155` (CR-063's fire revenue account) and CR-066's nine
joined it the same day. `PENDING_FINANCE_RE_SIGN_COST` is still `()`. ⚠ **THE
TUPLE IS DERIVED FROM THE ROWS AND IS THE ANSWER; THIS SENTENCE IS A NOTE THAT
WILL GO STALE AGAIN.** Read `PENDING_FINANCE_RE_SIGN`, not this line.

────────────────────────────────────────────────────────────────────────────
THE ONE THING THIS FILE EXISTS TO PREVENT
────────────────────────────────────────────────────────────────────────────
**Code reads the DESIGNATION. Code never reads the NUMBER.**

`US-LED-005` makes the chart tenant-customizable: a utility may renumber
accounts receivable from 1200 to 1150, rename it "Trade debtors", or both. Any
Python that says `code == "1200"` is therefore a latent misposting, and it is
the exact defect OQ-106 was raised to prevent — the decision log records it in
those words: *"the code reads the DESIGNATION and never the number."*

The pairings below are the SEED — where each designation STARTS. After
provisioning the tenant owns the chart, `apps.ledger.selectors` resolves by
designation, and this table is never consulted again for that tenant.
`tests/test_us_led_005_gl_designations.py` renumbers AR to 1150 and asserts the
lookup still lands, which is the test that keeps this property from rotting.

The same sentence now covers the SERVICE→ACCOUNT map as well (PO 2026-08-11,
OQ-115: *"you create an account, but allow tenant user to override it"*).
`SERVICE_REVENUE_ACCOUNTS` below is where a service's revenue account STARTS;
the live answer is `tenant_services.revenue_account`, which a tenant may
re-point through `apps.tenancy.services.update_tenant_service`, and which no
re-seed may overwrite.

────────────────────────────────────────────────────────────────────────────
⚠ SUPERSEDED 2026-08-18 — EVERY TENANT NOW GETS EVERY ROW (PO, CR-010 B-9)
────────────────────────────────────────────────────────────────────────────
**The rule this section stated is REVERSED by its own author.** OQ-115's
closure (PO 2026-08-11, verbatim: *"also note every Utility may not have all
the services"*) narrowed the seed to the services a tenant sells, and this
section documented that narrowing. On 2026-08-17 the PO reversed it — CR-010
B-9, verbatim: *"9 - A full ~40 accounts for every tenant, as you said"* — and
ruled New mandate 4 the same day: *"we will provdie full list for all services
- they can always select what they want out of it; more is better ; less is
contraint"*. So `seed_chart_of_accounts` now plants the FULL chart at
provisioning — every row of `SEED_CHART` plus the whole cost section, 33
accounts — for every tenant, whatever it sells. **No figure changed; only which
rows land** (the B5 freeze is untouched), and a tenant that wants fewer lines
deactivates rows on S56, which is theirs to do (US-LED-005 rule 1).

The SHARED / per-service split below is KEPT, because two things still read it:

  * `ensure_service_revenue_accounts` stays the **lookup + top-up** path — the
    S8 toggle and signup both still call it, and for a tenant provisioned
    during the narrowing era (2026-08-11 → 2026-08-17) it is what mints the
    account the full seed never gave them. Hard-won law 4: a seed change never
    reaches a tenant that already has a chart.
  * The tests that prove all twelve designations live on SHARED rows — an
    invariant that still matters, because a tenant may deactivate the
    per-service rows it does not use and must still resolve every designation.

`4190` minimum-bill adjustment, `4200` late-fee revenue and `4210` NSF & other
fee revenue were never conditional (a fee is charged to an ACCOUNT, not to a
service) and nothing about them moves.

────────────────────────────────────────────────────────────────────────────
AND THE 2200 SERIES IS SEEDED TO NOBODY (B5 line 74 ❄️ · BR-BIL-069)
────────────────────────────────────────────────────────────────────────────
There is a third category, with exactly one member, and it is an absence rather
than a list: **tax payable per authority.** The signed chart's own words are
*"2200-series Tax payable per authority (tenant authorities mint their own)"*,
and `SEED_CHART` therefore carries NO 2200 row. That was deliberate before the
PO's ruling of 2026-08-11 and it is deliberate after it — the ruling closing
OQ-116 says the same thing in the PO's words: *"For each atheority have separate
account and tagging; but also ensure you allow Use to manage it since every
utility may not have every account."*

Seeding a `2200-01` would invent a tax authority no tenant created. Authorities
are tenant-entered (BR-TEN-037) and there is no universal list of them: a Texas
submetering operator owes State of Texas, Harris County and the City of Katy; a
utility two states away owes none of the three. So the account arrives when the
authority does — `apps.ledger.services.create_tax_authority_account`, called
because a human asked for it, never from a fixture.

`TAX_PAYABLE_SERIES` below is the ONE fact this file states about them: which
series they must live in. Not which codes exist, and not who mints them.

────────────────────────────────────────────────────────────────────────────
WHERE EACH FACT COMES FROM
────────────────────────────────────────────────────────────────────────────
* **The chart itself** — `04-docs/02-decisions/05-golden-tests.md` line 74,
  *"Seed chart of accounts"*, signed by the Product Owner in finance authority
  2026-08-08 and under the ❄️ freeze banner. Codes and names are transcribed
  verbatim; the bracketed `[AR designation]`-style notes in the source are
  annotations about designations, not part of an account NAME, and are dropped.
* **The eleven designations** — PO ruling 2026-08-11 closing OQ-110, option A
  ("add all seven now"), on top of the four BR-BIL-010 already confirmed. The
  PO named each one against its account: `accounts_receivable` 1200 ·
  `deposit_liability` 2300 · `opening_clearing` 3000 · `write_off` 6900 ·
  `minimum_bill_adjustment` 4190 · `customer_credit_balance` 2400 · `cash` 1000
  · `undeposited_funds` 1010 · `unbilled_ar` 1210 · `bank_fees` 6800 ·
  `deposit_interest_expense` 6950. **Eleven, and nothing is reserved** — a
  posting with no home is an OQ row, never a twelfth entry here.
* **The service attributes** — BR-BIL-010 (CONFIRMED): `revenue_account`
  required, `base_revenue_account` OPTIONAL. Optional because the signed chart
  splits only two services (Electric 4100/4105, Water 4110/4115); Sewer, Trash,
  Gas and Broadband carry one account each, so a second REQUIRED field would
  have four services filling it with a duplicate of the first.

────────────────────────────────────────────────────────────────────────────
TWO JUDGMENT CALLS, STATED BECAUSE THE SIGNED SOURCE DOES NOT SETTLE THEM
────────────────────────────────────────────────────────────────────────────
**1 · ACCOUNT `type` IS DERIVED, NOT TRANSCRIBED.** B5's chart gives codes and
names; it does not give the asset/liability/equity/revenue/expense value that
drives the S56 trial-balance Type column. Two anchors make the derivation safe
rather than a guess: the ledger worked examples state *"3000 Opening balance
equity"* (LE-1's trial balance), which is the only one that does NOT follow the
number range; and the chart's own numbering is the standard 1xxx asset / 2xxx
liability / 3xxx equity / 4xxx revenue / 6xxx expense ladder, which is why
`apps/ledger/models.py` already carries `LEDGER_ACCOUNT_TYPES` with equity in
it. Recorded as a judgment call in the human-review ledger row for a finance
reviewer to confirm — `type` is not a money figure and no golden test reads it.

**2 · 4160 AND 4170 ARE THE LANE'S READING OF THE LADDER, NOT A SIGNATURE.**
The platform catalog is ten services (BR-RAT-024); the frozen chart names
revenue accounts for eight. `storm_water` and `thermal_heat` appeared in no
signed line, a storm-water bill could not be stamped, and BR-BIL-010 refused the
WHOLE bill — so OQ-115 was raised rather than a code invented. The PO closed it
2026-08-11: *"A, you create an account, but allow tenant user to override it —
also note every Utility may not have all the services."* Option A as put to the
PO read *"4160, 4170 follow your ladder"*, so those are the two codes, seeded
now and billable now.

⚠ **SUPERSEDED THE SAME DAY IT WAS WRITTEN — 4160/4170 WERE FINANCE RE-SIGNED
ON 2026-08-11** (PO verbatim *"okay"*, dated addendum beside ❄️ frozen B5 line
74). The paragraph below is kept as the record of the posture the two codes
were declared under, because that posture is what every later unsigned row
follows; read it in the past tense. It is also stamped in the correction block
above, and it is stamped here because a reader who lands on this heading does
not necessarily read that one (hard-won law 1).

**They were NOT finance-signed when this was written.** B5 line 74 is ❄️ FROZEN and names eight
services; a finance re-sign goes through HUMAN-GUIDE §6 and no agent may write
one. So the distinction is carried in the data rather than in a comment: the two
rows carry `signed=False`, `PENDING_FINANCE_RE_SIGN` lists them, and
`tests/test_us_led_005_gl_designations.py` asserts that exactly those two are
unsigned and that the other twenty are. When finance signs, the change is one
word per row (`signed=False` → gone) plus the test figure, and until then anyone
reading this file can see which numbers a human in finance actually approved.
This is a real distinction, not a formality: the two accounts collect real
revenue from the day a tenant enables the service, and if finance re-signs a
DIFFERENT code the correction is a chart edit on a live tenant.
"""

from __future__ import annotations

from typing import Any, NamedTuple

# ── the eleven designations (PO ruling 2026-08-11, OQ-110 option A) ─────────
# Named constants rather than bare strings so a typo is an ImportError at the
# call site instead of a silent None at posting time. Order below is the PO's
# own order in the ruling, deliberately: a reader comparing this file against
# the decision log reads the two lists side by side.
AR = "accounts_receivable"
DEPOSIT_LIABILITY = "deposit_liability"
OPENING_CLEARING = "opening_clearing"
WRITE_OFF = "write_off"
MINIMUM_BILL_ADJUSTMENT = "minimum_bill_adjustment"
CUSTOMER_CREDIT_BALANCE = "customer_credit_balance"
CASH = "cash"
UNDEPOSITED_FUNDS = "undeposited_funds"
UNBILLED_AR = "unbilled_ar"
BANK_FEES = "bank_fees"
DEPOSIT_INTEREST_EXPENSE = "deposit_interest_expense"

# ── the TWELFTH designation (PO ruling 2026-08-15, OQ-142) ──────────────────
# PO verbatim: *"Create seperate account"*. Added out of the PO's-order block
# above because it is a later ruling, not part of the OQ-110 eleven — a reader
# diffing this file against the 2026-08-11 decision-log row must still find that
# list intact.
#
# **WHAT IT IS FOR, with the ❄️ frozen WE-8 figures.** A budget-billing month
# recognises **292.87** of revenue and asks the customer for **242.00**, leaving
# **50.87** standing. It is not revenue (counted), not tax (taken) and not an
# arrear — the customer paid exactly what we asked. But with nowhere of its own
# to sit it landed in the **1–30 ageing bucket**, indistinguishable from a
# delinquency on every ageing report. Across a year the balance runs
# **−50.87 → −40.27 → +2.98**, so it can end as money the utility OWES while
# filed as money it is owed.
#
# ⚠ **AMENDED 2026-08-18 — THE ACCOUNT NOW EXISTS, UNDER THE PO's CR-010 B-8
# RULING OF 2026-08-17.** This block used to say *"THE DESIGNATION EXISTS; THE
# ACCOUNT DOES NOT"*, which was true from 2026-08-15 to 2026-08-17. The PO then
# ruled, verbatim: *"8 - A ✅ 4180 "Budget billing variance", revenue,
# signed=False (the 4160/4170 precedent)"* — so `SEED_CHART` below carries
# **4180 Budget billing variance**, revenue, carrying THIS designation, with
# `signed=False` exactly as 4160/4170 were declared on the day OQ-115 closed.
# The 50.87 has a home; the CODE awaited its finance re-sign via HUMAN-GUIDE §6
# (B5 line 74 is ❄️ FROZEN and was NOT edited), and while that was owed 4180 sat
# in `PENDING_FINANCE_RE_SIGN` and every surface that offered it said so.
# ⚠ **THE SIGNATURE LANDED THE SAME DAY: 2026-08-18.** The PO re-signed 4180
# with the eight cost rows, shown the nine codes and names in plain English and
# told explicitly that no dollar figure was attached to any of them. So
# `signed=True`, the tuple is `()`, and no surface marks it. **The 50.87 itself
# was NOT re-signed** — it was explained as WHY this account exists, and it
# stays where ❄️ frozen B4/B5 put it. Receivables and `unbilled_ar` were offered
# to the PO on 2026-08-15 and DECLINED — that half of the record is unchanged.
BUDGET_VARIANCE = "budget_variance"

# ── the THIRTEENTH designation (PO ruling 2026-08-28, closing DEF-536) ──────
# PO verbatim: *"you will need differnt GL code for these - dont keep them in
# same, create differnt category as required and keep them in it"*, answering
# the question a discounted bill had been blocked on since 2026-08-22.
#
# **WHAT IT IS FOR.** A discount reduces what the customer is asked for; it does
# NOT reduce what the utility charged. Netted against the service's own revenue
# account the two become one figure and the utility reports revenue it never
# earned at that price. Worked, on the frozen GT-1 bill with a 10.00 goodwill
# reduction:
#
#     old (netted)                       ruled (its own GL)
#     CR 4100 electric usage   72.08     CR 4100 electric usage    82.08
#     CR 4105 electric base    18.50     CR 4105 electric base     18.50
#                                        DR 4300 customer discounts 10.00
#     DR 1200 AR               90.58     DR 1200 AR                90.58
#
# Both balance at 100.58. The ruled form states the 10.00 as its own figure and
# leaves 4100 saying what electricity actually sold for.
#
# ⚠ **AND IT REMOVES OQ-152's FAILURE MODE RATHER THAN ONLY NAMING AN ACCOUNT.**
# OQ-152 closed 2026-08-12 — *"a bill whose GL bucket sums below zero REFUSES to
# issue"* — and `billing/posting_seam.posting_buckets` refuses by that name. A
# discount netted into the service's own account is what drives a bucket below
# zero. Posted as a DEBIT to THIS account no bucket goes negative, so the
# refusal cannot fire on a discount at all. Both rulings stand; neither is
# superseded, and the negative-bucket refusal still fires for anything else.
DISCOUNT_CONTRA_REVENUE = "discount_contra_revenue"

# ── the FOURTEENTH, FIFTEENTH and SIXTEENTH (CR-060 T7b / T7f, 2026-09-02) ──
# **THREE POINTERS FOR TWO POSTINGS THE PRODUCT COULD NOT MAKE BEFORE TODAY**,
# and not one of them is a finance ruling: they name accounts the PO's own
# reference chart already contains, or — for `5700` — the one account that
# chart forgot.
#
# **`accrued_expenses` — CR-060 C17 / task T7b.** At month end the utility owes
# its suppliers for commodity it has already sold. The accrual DEBITS each
# purchase's own cost account and CREDITS this one, and the day-1 mirror
# (BR-LED-005) drains it again — so it is a liability that is never carried,
# which is the whole reason BR-LED-028's objection does not reach it. Worked, on
# LE-11's CI-1: **DR 5110 purchased water 1,240.00 / CR 2100 accrued supplier
# costs 1,240.00** on 31 July, reversed 1 August, and the cost stays in July
# where the water was sold.
#
# **`depreciation_expense` and `accumulated_depreciation` — CR-060 C20 / task
# T7f.** *"Depreciation is computed and shown on screen and posts nowhere"*
# (CR-060 §4). It posts now: DR the expense, CR the accumulated. The pair is
# resolved BY DESIGNATION and never by number, for the reason this file states
# at length — `1730` is where the seeded chart puts accumulated depreciation on
# meters and a utility with water plant moves the pointer to `1700` in one
# click, without a line of code changing.
#
# ⚠ **NO ACCOUNT IS RENAMED, RETYPED OR RE-SIGNED BY THIS.** `2100 Accrued
# expenses` and `1730 Accumulated depreciation — meters` are CR-061's rows,
# ruled into existence by the PO on 2026-09-01/02 and carrying `signed=False`
# there; a designation is a POINTER AT an account and changes nothing about it.
# `5700 Depreciation expense` is the one row the 111-row reference chart has no
# entry for at all — the reference gives four accumulated-depreciation accounts
# (rows 70-73) and no expense to charge, which is half a double entry. It is
# minted here `signed=False`, in `PERIOD_MATCHING_CHART` below, and it is on
# `PENDING_FINANCE_RE_SIGN_MATCHING` until HUMAN-GUIDE §6 says otherwise.
ACCRUED_EXPENSES = "accrued_expenses"
DEPRECIATION_EXPENSE = "depreciation_expense"
#: ⚠ The VALUE is deliberately the same string as `CAT_ACCUM_DEPRECIATION`
#: below, and they are different columns: this is a POINTER (which account
#: the depreciation entry credits) and that is a HEADING (which section of
#: the chart an account is printed under). One concept, two jobs, and a
#: caller that passed the wrong constant would get the right account — so
#: the collision is harmless where every other designation typo is not.
ACCUMULATED_DEPRECIATION = "accumulated_depreciation"

# ── the SEVENTEENTH designation (PO ruling 2026-09-03, CR-060 T15) ─────────
# PO verbatim: *"Why I recommended deferring it. Three reasons: let's do this"*
# — the heading of a recommendation to DEFER, quoted back and chosen against.
# The three reasons are in `12-governance/02-decision-log.md` so the trade is on
# file rather than in a chat log.
#
# **THIS IS THE POINTER JUDGMENT 3 BELOW WITHHELD.** That paragraph refused to
# seed `1290 Allowance for doubtful accounts` because *"seeding an allowance
# account offers a utility an accounting policy this product does not
# implement"*. The product implements it now — `apps/ledger/allowance.py` — so
# the refusal is spent and the paragraph is stamped rather than deleted.
#
# **WHAT IT POINTS AT AND WHAT CREDITS IT.** A contra-asset sitting beside
# `1200 Accounts receivable`: the balance sheet reads *owed $15,333.30,
# realistically expect $14,109.65*. Each close adjusts it to the computed
# target — `DR 6900 Bad debt / CR 1290` to top it up, and the SAME PAIR the
# other way round to release it when collectability improves.
#
# ⚠ **AND THE WRITE-OFF STOPS TOUCHING `6900` WHILE THE POLICY IS ON.** With an
# allowance in force a write-off CONSUMES it — `DR 1290 / CR 1200` — because
# the expense was already taken when the estimate was posted. A write-off that
# kept hitting `6900` beside a monthly estimate that also does would expense bad
# debt TWICE, which is `DEF-3380`'s shape one module over.
ALLOWANCE_DOUBTFUL_ACCOUNTS = "allowance_doubtful_accounts"

# ── the EIGHTEENTH designation (PO ruling 2026-09-23, CR-136-BRC07 §3.3) ────
# PO verbatim: *"(b) Post it. A short writes a balanced pair to a cash
# over/short account the day it is declared. Needs one new account added to the
# chart"*. It supersedes the payments blueprint's own sentence — *"The ledger:
# Nothing — counting is not a posting"* — which `P2.15` had committed as a test.
#
# **ONE ACCOUNT SERVES BOTH DIRECTIONS, AND THAT IS WHAT THE NAME MEANS.** A
# drawer counted SHORT debits it; a drawer counted OVER credits it. There is no
# second `cash_over` designation and there must not be one: an over on Monday
# and a short on Tuesday net against each other in the account a utility reads
# as *"how far out are my drawers"*, and split across two accounts neither
# figure answers that question.
#
# **WORKED, both directions, on the case put to the PO.** Dana's till expects
# **$1,240.0000** and the bag counts **$1,228.0000**:
#
#     $12.0000 SHORT                        $12.0000 OVER (a $1,252.0000 bag)
#     DR 6850 cash over and short 12.0000   DR 1010 undeposited funds 12.0000
#     CR 1010 undeposited funds   12.0000   CR 6850 cash over and short 12.0000
#
# **AGAINST `1010`, NOT `1000`.** Taking money already debits `1010 Undeposited
# funds`; the bank will only ever receive what was actually in the drawer, so
# the difference has to leave `1010` BEFORE the deposit clears it, or the
# reconciliation carries a permanent $12.0000 stub (`reporting.py`:
# *"reconciliation moves it to 1000 Cash"*).
#
# ⚠ **A ZERO DIFFERENCE POSTS NOTHING.** A balanced pair for $0.0000 is noise
# in the journal, and the accountant's question is *what is missing*, not *was
# a drawer counted*. That is `P2.22`'s rule, stated here because this
# designation is what it resolves through.
#
# ⚠ **THE POSTING IS NOT BUILT BY THE CHANGE THAT ADDS THIS CONSTANT.**
# `P2.22` owns it, in payments, through the ledger posting service (hard rule
# 5). What lands here is the POINTER and the account it starts on, which is the
# half that must exist before any posting site can resolve anything.
#
# ⚠ **IT IS A SEEDED DEFAULT AND NEVER A CONSTANT AT A POSTING SITE.** `6850`
# is where this account STARTS; a tenant renumbers or renames it on Settings →
# Accounting → Chart of accounts (US-LED-005 rule 1, BR-LED-040), and every
# posting resolves the DESIGNATION. `BR-LED-796`.
CASH_OVER_SHORT = "cash_over_short"

# ── CR-197-BRC10, PO ruling 2026-10-29 · BR-LED-803 ──────────────────────────
# *"Refunds: A — their own row (refund account)"*. A refund's CREDIT leg has
# always been `cash` (BR-PAY-014: *"DR customer-credit / CR cash"*). When an
# account carries THIS designation the credit goes to it instead — a refunds
# payable liability cleared when the cheque is paid, or a refund bank account.
# When none does, the posting is byte-for-byte what it was.
#
# ⚠ **NOT SEEDED, AND THAT IS THE RULE RATHER THAN A GAP.** Seeding one would
# move every existing tenant's refunds off cash the day this lands, which is a
# posting change nobody asked for. The tenant chooses it on Settings ›
# Accounting › GL mapping (the Refund row). Worked: refund $57.13 — today
# DR 2400 / CR 1000; with 2450 designated, DR 2400 / CR 2450.
REFUNDS_PAYABLE = "refunds_payable"

#: The closed set. ⚠ **COUNT THE TUPLE; DO NOT READ A NUMBER OUT OF THIS
#: COMMENT.** The PO ruled eleven on 2026-08-11 (OQ-110, reserving nothing), a
#: twelfth on 2026-08-15 (OQ-142) and a thirteenth on 2026-08-28 (the discount
#: ruling that closed DEF-536); CR-060's T7b and T7f added three on 2026-09-02,
#: T15 a seventeenth on 2026-09-03, and CR-136-BRC07 §3.3 an eighteenth on
#: 2026-09-23, and CR-197-BRC10 `refunds_payable` on 2026-10-29. ⚠ **THIS LINE HAS NOW BEEN WRONG TWICE, THE SAME WAY BOTH
#: TIMES** — it read *THIRTEEN* while the tuple held sixteen, and *SIXTEEN*
#: from 2026-09-03 until 2026-09-23 while the tuple held seventeen
#: (`DEF-LED-6222`). Ratifying a designation and amending the sentence that
#: counts them are two acts, and only the first one feels like the work; it is
#: CLAUDE.md's own rule-count rot in a smaller register. **The tuple below is
#: the answer**, and `tests/test_us_led_005_gl_designations.py` asserts its
#: exact contents, which is why the DATA has never been wrong.
#: `ledger_accounts.designation` carries a CHECK against exactly this tuple, so
#: a typo'd designation cannot reach the table: an account designated
#: `accounts_recievable` would be findable by nothing, which is the same class
#: of hole `ck_journal_lines_side` closes for `side`.
#:
#: ⚠ **CHANGING THIS TUPLE REQUIRES A MIGRATION.** Django's serializer INLINES
#: these values into the CHECK constraint, so the database does not follow this
#: file — `ledger/0003` said so in its own exceptions block and `ledger/0006` is
#: the migration that paid the price for this twelfth entry. Add a constant here
#: without a migration and the constant is accepted by Python and refused by
#: Postgres.
GL_DESIGNATIONS: tuple[str, ...] = (
    AR,
    DEPOSIT_LIABILITY,
    OPENING_CLEARING,
    WRITE_OFF,
    MINIMUM_BILL_ADJUSTMENT,
    CUSTOMER_CREDIT_BALANCE,
    CASH,
    UNDEPOSITED_FUNDS,
    UNBILLED_AR,
    BANK_FEES,
    DEPOSIT_INTEREST_EXPENSE,
    BUDGET_VARIANCE,
    DISCOUNT_CONTRA_REVENUE,
    ACCRUED_EXPENSES,
    DEPRECIATION_EXPENSE,
    ACCUMULATED_DEPRECIATION,
    ALLOWANCE_DOUBTFUL_ACCOUNTS,
    CASH_OVER_SHORT,
    REFUNDS_PAYABLE,
)


# ── the SEVENTEEN CHART CATEGORIES (CR-061, PO ruling 2026-09-01) ───────────
# PO verbatim, reporting a FIELD FINDING rather than a preference: *"actually
# you need more GL code s and categories, I tried to assigned using existing
# code, they are not sufficiencnt"*. The second noun is this block. Statement
# (2) of that ruling — the discount — was built on 2026-09-01; statement (1) is
# built here, and its two halves are **more codes** (`UTILITY_BOOKS_CHART`
# below) and **more categories** (this tuple).
#
# **WHAT A CATEGORY IS, AND WHAT IT IS NOT.** It is the GROUPING a chart of
# accounts is read in — the heading a human scans to find where a cost belongs.
# It is NOT the account `type`, which is the accounting kind that decides how a
# figure behaves, and it is NOT `chart.COST_CATEGORY_SPECS`, which is the
# supplier-invoice cost taxonomy on the S73 capture tab. Three different words
# for three different things, named here because two of them are called
# "category" in ordinary speech and a reader who conflates them will file a
# purchased-power INVOICE against a chart heading.
#
# **THE NAMES ARE THE PO's OWN**, taken verbatim from the Category column of the
# 111-row reference chart they supplied on 2026-09-01 (`CR-061` §5), so a
# utility comparing our chart against the one they sent reads the same headings.
# Two are ours and are marked as such below.
#
# ⚠ **NO DATABASE `CHECK` CONSTRAINT, AND THAT IS A DECISION.** `GL_DESIGNATIONS`
# above carries one, and its own warning says what that costs: *"Django's
# serializer INLINES these values into the CHECK constraint, so the database
# does not follow this file"* — adding a designation needs a migration, and
# `ledger/0006` is the one that paid for the twelfth. A category is a GROUPING
# and not a posting pointer: nothing resolves an account by it, no money lands
# because of it, and a utility that wants an eighteenth heading is doing chart
# work rather than posting work. So it is validated in Python, exactly as
# `LEDGER_ACCOUNT_TYPES` is (verified across every `ledger/migrations/*` for
# `CR-061` on 2026-09-01 and again on 2026-09-02), and an eighteenth category is
# a one-line code change with no migration behind it.
CAT_CASH = "cash_investments"
CAT_RECEIVABLE = "accounts_receivable"
CAT_INVENTORY = "inventory"
CAT_FIXED_ASSETS = "fixed_assets"
CAT_CIP = "construction_cip"
CAT_ACCUM_DEPRECIATION = "accumulated_depreciation"
CAT_PAYABLE = "accounts_payable"
CAT_TAXES_PAYABLE = "taxes_payable"
CAT_CUSTOMER_DEPOSITS = "customer_deposits"
CAT_DEBT = "debt"
CAT_GRANTS = "grants_contributions"
CAT_CUSTOMER_REVENUE = "customer_revenue"
CAT_REVENUE_ADJUSTMENTS = "revenue_adjustments"
CAT_COST_OF_SERVICE = "cost_of_service"
CAT_OPERATING_EXPENSES = "operating_expenses"
CAT_NON_OPERATING = "non_operating"
CAT_TRANSFERS = "transfers"
CAT_NET_POSITION = "net_position"

#: The closed set, in the order a chart of accounts is READ — assets, then
#: liabilities, then equity, then revenue, then cost. A screen groups by this
#: order and not alphabetically, which is why it is a tuple and not a set.
#:
#: ⚠ **EIGHTEEN, NOT THE REFERENCE'S SIXTEEN, AND THE TWO EXTRA ARE OURS.**
#: `cost_of_service` is this product's own eight-account purchased-cost ladder
#: (`COST_OF_SERVICE_CHART`), which the reference has no heading for because the
#: reference files purchased power under Operating Expenses; keeping it separate
#: preserves the distinction `US-LED-017` is built on. `taxes_payable` is the
#: 2200 series, which is seeded to NOBODY and minted per tax authority
#: (`BR-BIL-069`) — it needs a heading precisely BECAUSE no seed row carries it,
#: or a minted authority account would be the one row on the screen with no home.
CHART_CATEGORIES: tuple[str, ...] = (
    CAT_CASH,
    CAT_RECEIVABLE,
    CAT_INVENTORY,
    CAT_FIXED_ASSETS,
    CAT_CIP,
    CAT_ACCUM_DEPRECIATION,
    CAT_PAYABLE,
    CAT_TAXES_PAYABLE,
    CAT_CUSTOMER_DEPOSITS,
    CAT_DEBT,
    CAT_GRANTS,
    CAT_NET_POSITION,
    CAT_CUSTOMER_REVENUE,
    CAT_REVENUE_ADJUSTMENTS,
    CAT_NON_OPERATING,
    CAT_TRANSFERS,
    CAT_COST_OF_SERVICE,
    CAT_OPERATING_EXPENSES,
)


def is_chart_category(value: Any) -> bool:
    """Is `value` one of the eighteen? Python-validated, no database CHECK."""
    return isinstance(value, str) and value in CHART_CATEGORIES


class SeedAccount(NamedTuple):
    """One line of the seed chart — twenty from B5 line 74, two pending.

    `designation` is the seed pairing and NOTHING MORE — see the module
    docstring. `type` is derived from the number range (judgment call 1).

    `signed` is the finance signature, carried as DATA so a reader and a test
    can both see it (judgment call 2). True = transcribed from B5 line 74,
    ❄️ finance-signed 2026-08-08. False = added under a PO ruling that the
    account should exist, with a code this lane read off the chart's own ladder
    and finance has not yet re-signed via HUMAN-GUIDE §6. It is deliberately
    NOT a comment: a comment claiming a guarantee is not the guarantee
    (hard-won law 1), and this field claims the opposite of a guarantee.
    """

    code: str
    name: str
    type: str
    designation: str | None = None
    signed: bool = True
    #: The chart HEADING this row is read under — one of `CHART_CATEGORIES`,
    #: added 2026-09-02 for `CR-061` statement (1) (*"you need more GL codes and
    #: categories"*). It is a GROUPING and never a pointer: no posting resolves
    #: an account by it and no figure changes because of it, which is why it
    #: needs no database CHECK and no migration to extend.
    #:
    #: `None` is lawful and means *uncategorised*, which is what a tenant's own
    #: hand-added account carries until somebody files it. A screen renders that
    #: as its own group rather than hiding the row — an account missing from the
    #: chart screen is worse than one under the wrong heading.
    category: str | None = None


#: B5 line 74 in its own order, transcribed, PLUS the two rows the PO ruled into
#: existence on 2026-08-11 (OQ-115) and the one ruled in on 2026-08-17 (CR-010
#: B-8) — all three finance re-signed by dated addendum, 4160/4170 on 2026-08-11
#: and 4180 on 2026-08-18, so every row here carries `signed=True`. The "2200-series
#: Tax payable per authority" line of the signed chart is deliberately ABSENT:
#: the source says *"tenant authorities mint their own"*, so seeding a 2200 would
#: invent a tax authority no tenant created (BR-TEN-037). It arrives when an
#: authority does.
SEED_CHART: tuple[SeedAccount, ...] = (
    SeedAccount("1000", "Cash", "asset", CASH, category=CAT_CASH),
    SeedAccount("1010", "Undeposited funds", "asset", UNDEPOSITED_FUNDS, category=CAT_CASH),
    SeedAccount("1200", "Accounts receivable", "asset", AR, category=CAT_RECEIVABLE),
    SeedAccount("1210", "Unbilled AR (accruals)", "asset", UNBILLED_AR, category=CAT_RECEIVABLE),
    SeedAccount(
        "2300",
        "Customer deposit liability",
        "liability",
        DEPOSIT_LIABILITY,
        category=CAT_CUSTOMER_DEPOSITS,
    ),
    SeedAccount(
        "2400",
        "Customer credit balances",
        "liability",
        CUSTOMER_CREDIT_BALANCE,
        category=CAT_CUSTOMER_DEPOSITS,
    ),
    SeedAccount(
        "3000", "Opening balance clearing", "equity", OPENING_CLEARING, category=CAT_NET_POSITION
    ),
    SeedAccount("4100", "Electric usage", "revenue", category=CAT_CUSTOMER_REVENUE),
    SeedAccount("4105", "Electric base", "revenue", category=CAT_CUSTOMER_REVENUE),
    SeedAccount("4110", "Water usage", "revenue", category=CAT_CUSTOMER_REVENUE),
    SeedAccount("4115", "Water base", "revenue", category=CAT_CUSTOMER_REVENUE),
    SeedAccount("4120", "Sewer", "revenue", category=CAT_CUSTOMER_REVENUE),
    SeedAccount("4130", "Trash", "revenue", category=CAT_CUSTOMER_REVENUE),
    SeedAccount("4140", "Gas", "revenue", category=CAT_CUSTOMER_REVENUE),
    SeedAccount("4145", "Broadband", "revenue", category=CAT_CUSTOMER_REVENUE),
    # ⚠ **THIS ROW READ "Capacity (solar/battery)" AND WAS SIGNED, AND IT IS
    # NOW "Solar" AND IS NOT — PO ruling 2026-09-03, verbatim: *"We need
    # seperate code for Solar 4150 and Battery 4150"*.
    #
    # B5 line 74 names ONE account for the pair — *"4150 Capacity
    # (solar/battery)"* — so a utility selling both could not tell them apart in
    # its own books: 40 kW of solar and 40 kW of battery arrived as one number.
    # The PO has now said that is not good enough, which supersedes that half of
    # the signed line.
    #
    # **THE NUMBER DOES NOT MOVE AND SOLAR KEEPS IT.** Battery is the service
    # leaving, so nothing already posted to 4150 changes account; only battery's
    # FUTURE postings go elsewhere. `signed=False` is about the NAME, not the
    # number: what finance signed was an account covering the pair, and this row
    # no longer says that, so it goes back on the pending list until they see it.
    SeedAccount("4150", "Solar", "revenue", None, False, category=CAT_CUSTOMER_REVENUE),
    # ── CR-063 · FIRE, THE ELEVENTH SERVICE (PO 2026-09-02) ──────────────────
    # ⚠ **`signed=False`, AND THAT IS THE `4160`/`4170`/`4180` POSTURE RATHER
    # THAN AN OVERSIGHT.** B5 line 74 is ❄️ FROZEN and names eight services;
    # every code added since has arrived unsigned, been listed in
    # `PENDING_FINANCE_RE_SIGN`, and reached `signed=True` only by a DATED
    # ADDENDUM through HUMAN-GUIDE §6 — never by an inline edit here. This row
    # is at that first stage. A human-review row states, in plain English with
    # the figure, exactly what a reviewer is being asked to sign.
    #
    # **WHAT IS THE LANE'S READING AND NOT A SIGNATURE:** the NUMBER and the
    # NAME. `4155` was FREE and sits correctly in this chart's own ladder —
    # `4150` Capacity, `4155` Fire, `4160` Storm water — so fire's revenue lands
    # between the two services it is nearest to rather than at the end. What is
    # RULED is that fire exists and is billed (`BR-RAT-024`, amended
    # 2026-09-02); which GL code carries it is ours until finance says.
    #
    # ⚠ **FIRE DOES NOT SHARE `4150` WITH SOLAR AND BATTERY, DELIBERATELY.**
    # Those two share one account because the signed line names ONE account for
    # the pair — *"4150 Capacity (solar/battery)"* — and that is the chart's own
    # choice, quoted rather than extended. Fire is not named in it, and adding a
    # third service to an account whose NAME lists two would make the ledger say
    # something the frozen line does not.
    SeedAccount("4155", "Fire", "revenue", None, False, category=CAT_CUSTOMER_REVENUE),
    # ── FINANCE RE-SIGNED 2026-08-11 (PO verbatim: "okay") — B5 ADDENDUM ──────
    # Added under the PO's closure of OQ-115 and signed the same day. The
    # signature is an ADDENDUM to B5, dated, with the ruling — the frozen line
    # of 2026-08-08 still says what finance signed then, because CLAUDE.md
    # changes a signed figure by re-sign and "never an inline edit".
    SeedAccount("4160", "Storm water", "revenue", category=CAT_CUSTOMER_REVENUE),
    # ⚠ **BATTERY'S OWN REVENUE ACCOUNT (PO ruling 2026-09-03).** UNSIGNED, on
    # the 4155 / 4160 / 4170 precedent: the PO ruled the SPLIT into existence
    # and that is not a finance signature on a number, so this sits in
    # `PENDING_FINANCE_RE_SIGN` until finance sees it.
    #
    # **WHY 4165 AND NOT SOMETHING NEXT TO SOLAR, WHICH WOULD READ BETTER.**
    # This chart moves in FIVES — 4100, 4105, 4110, 4115, 4120, 4130, 4140,
    # 4145, 4150, 4155, 4160, 4170 — and there is no free multiple of five
    # between solar's 4150 and storm water's 4160, because `CR-063` put fire on
    # 4155 four days ago. So battery sits at the next free five rather than at
    # 4152, which would be adjacent and would be the first row in this chart to
    # break its own step. Adjacency is a nicety; a chart that stops being
    # predictable is a chart somebody misreads.
    SeedAccount("4165", "Battery", "revenue", None, False, category=CAT_CUSTOMER_REVENUE),
    SeedAccount("4170", "Thermal/Heat", "revenue", category=CAT_CUSTOMER_REVENUE),
    # ── PO RULED 2026-08-17 (CR-010 B-8) · FINANCE RE-SIGNED 2026-08-18 ──────
    # Verbatim: *"8 - A ✅ 4180 "Budget billing variance", revenue, signed=False
    # (the 4160/4170 precedent)"*. The twelfth designation's account (OQ-142's
    # WE-8 figures: 292.87 recognised, 242.00 asked, 50.87 standing) finally has
    # a seeded home, declared exactly as 4160/4170 were the day they arrived:
    # `signed=False`, listed in PENDING_FINANCE_RE_SIGN, awaiting the
    # HUMAN-GUIDE §6 re-sign. B5 line 74 stays ❄️ un-edited.
    # FINANCE RE-SIGNED 2026-08-18 (PO, working chat session) — see the dated
    # addendum in this module's docstring. `signed=True` since that ruling, and
    # PENDING_FINANCE_RE_SIGN is `()` again. The code and the name are what was
    # ratified; the 50.87 is not — no figure was put to the PO with this row.
    SeedAccount(
        "4180",
        "Budget billing variance",
        "revenue",
        BUDGET_VARIANCE,
        True,
        category=CAT_REVENUE_ADJUSTMENTS,
    ),
    # ── back to B5 line 74, transcribed ──────────────────────────────────────
    SeedAccount(
        "4190",
        "Minimum-bill adjustment",
        "revenue",
        MINIMUM_BILL_ADJUSTMENT,
        category=CAT_REVENUE_ADJUSTMENTS,
    ),
    SeedAccount("4200", "Late-fee revenue", "revenue", category=CAT_CUSTOMER_REVENUE),
    SeedAccount("4210", "NSF & other fee revenue", "revenue", category=CAT_CUSTOMER_REVENUE),
    # ── PO RULED 2026-09-02 (CR-066, tables 1 and 2) — NINE NEW ROWS ────────
    # **THE PO APPROVED THE MAPPING, NOT THE CHART.** They were shown the two
    # tables in plain English with these account names and numbers beside the
    # charge codes and adjustment reasons that would point at them, and ruled
    # *"these are all correct - you can apply them as part of Seed data"* and
    # *"these are all good - please apply these"*. That is a ruling that these
    # accounts should EXIST and what should post to them. **It is not a finance
    # signature on the chart**, which is why all nine carry `signed=False` and
    # land in `PENDING_FINANCE_RE_SIGN` — the posture 4160/4170 were declared
    # under and 4155 and 4760 still stand in. B5 line 74 is ❄️ FROZEN and is
    # NOT edited inline; the re-sign route is HUMAN-GUIDE §6 and nothing else.
    #
    # ⚠ **WHY THEY EXIST AT ALL, IN ONE SENTENCE: WITHOUT THEM A FRESH TENANT
    # CANNOT ISSUE A BILL THAT CARRIES A FEE** (`DEF-2386`). `apps/billing/
    # issue.py` resolves a USAGE or BASE line from the service's designation and
    # a FEE line from `rating.charges.gl_account_id`, and refuses the whole bill
    # when that column is null. The platform seed has never written it, so every
    # tenant provisioned to date holds 28 charge codes pointing nowhere — and
    # two of them (`PAPER`, `HYDRANT`) are `recurring`, which `BR-RAT-117` puts
    # on every ordinary bill. There was no account in this chart to point the
    # other twenty-one at: 4200 is late fees and 4210 is NSF, and filing a
    # backflow inspection under either would make the ledger say something
    # untrue.
    #
    # **THE NUMBERS ARE THE PO's OWN REFERENCE CHART's**, reproduced in CR-061
    # §5 — 4600/4610/4630 and the whole 4700–4730 *Revenue Adjustments* block —
    # so adopting that chart later finds these rows already in the right place
    # and renumbers nothing. 4640 and 4650 are the two this lane read off the
    # same ladder because that chart names no slot for them.
    SeedAccount(
        "4600",
        "Connection & new-service fees",
        "revenue",
        None,
        False,
        category=CAT_CUSTOMER_REVENUE,
    ),
    SeedAccount(
        "4610",
        "Disconnection & reconnection fees",
        "revenue",
        None,
        False,
        category=CAT_CUSTOMER_REVENUE,
    ),
    SeedAccount(
        "4630", "Field-service & meter fees", "revenue", None, False, category=CAT_CUSTOMER_REVENUE
    ),
    SeedAccount(
        "4640",
        "Equipment recovery & penalties",
        "revenue",
        None,
        False,
        category=CAT_CUSTOMER_REVENUE,
    ),
    SeedAccount(
        "4650", "Billing & payment fees", "revenue", None, False, category=CAT_CUSTOMER_REVENUE
    ),
    # ⚠ **THE FOUR ADJUSTMENT ROWS ARE `contra_revenue`, AND THAT IS JUDGMENT
    # CALL 1 (`type` IS DERIVED, NEVER TRANSCRIBED), NOT SOMETHING THE PO WAS
    # SHOWN.** Two anchors decide it rather than taste. The PO's own reference
    # chart gives every row of its *Revenue Adjustments* block **Normal Balance
    # = Debit**, and CR-061's ruling on the discount row — *"no, you cannot file
    # discount under revenue"* — settles that a debit-normal reduction of
    # revenue is not revenue in this product; `contra_revenue` is the type that
    # ruling minted for exactly that shape. Nothing else moves: the trial
    # balance and `gl_totals` take a row's side from its own net debit and never
    # from its type, and `reporting.revenue_by_service` reads
    # `models.REVENUE_REPORTING_TYPES`, which already contains `contra_revenue`.
    #
    # ⚠ **AND THE PO WAS TOLD, IN THE SAME MESSAGE THAT CARRIED TABLE 2, THAT
    # IT CHANGES NOTHING TODAY.** No adjustment posts through a reason code: a
    # credit reverses whatever account the original bill credited. These four
    # rows and their mapping are correct to HAVE; they are not what unblocks a
    # bill, and no docstring, screen or test in this repo may say they are.
    SeedAccount(
        "4700",
        "Billing adjustment",
        "contra_revenue",
        None,
        False,
        category=CAT_REVENUE_ADJUSTMENTS,
    ),
    SeedAccount(
        "4710", "Leak adjustment", "contra_revenue", None, False, category=CAT_REVENUE_ADJUSTMENTS
    ),
    SeedAccount(
        "4720",
        "Rate / meter correction",
        "contra_revenue",
        None,
        False,
        category=CAT_REVENUE_ADJUSTMENTS,
    ),
    SeedAccount(
        "4730", "Customer credit", "contra_revenue", None, False, category=CAT_REVENUE_ADJUSTMENTS
    ),
    # ── PO RULED 2026-08-28 (the discount designation, closing DEF-536) ──────
    # Verbatim: *"you will need differnt GL code for these - dont keep them in
    # same, create differnt category as required and keep them in it"*.
    #
    # ⚠ **BOTH OF THIS ROW'S TWO LANE JUDGMENTS WERE OVERTURNED BY THE PO ON
    # 2026-09-01 (CR-061), AND THE ROW BELOW IS THE RULING, NOT THE ORIGINAL.**
    # It read `SeedAccount("4300", …, "revenue", …)` from 2026-08-28 until then.
    # The two questions its review-ledger row had been holding open since that
    # day were both answered in the working chat session:
    #
    #   ledger row asked: *"is filing it under Revenue acceptable?"*
    #   PO verbatim:      *"no, you cannot file discount under revenue"*
    #
    #   ledger row asked: *"is 4300 … the right code and the right words?"*
    #   PO verbatim:      *"if you need differnt number assign it - im okay
    #                      with it; actually you need more GL code s and
    #                      categories, I tried to assigned using existing code,
    #                      they are not sufficiencnt"*
    #
    # **SO THE TYPE IS `contra_revenue`, A SIXTH `LEDGER_ACCOUNT_TYPES` VALUE.**
    # The old comment here argued a sixth type "would change how every account
    # in the product is grouped and signed on the trial-balance screen". That
    # was measured for CR-061 and it was WRONG: the trial balance and `gl_totals`
    # take a row's side from its own net debit and never from its type, and the
    # ONE place in the product that filters on a type rather than printing it is
    # `reporting.revenue_by_service`. That one place now reads
    # `models.REVENUE_REPORTING_TYPES`, which is the whole cost the objection
    # was sizing.
    #
    # **AND THE NUMBER IS 4760, NOT 4300.** Three reasons, none of them tidiness:
    #   * **4300 collides with the PO's own chart**, which gives 4300 to
    #     *Electric Energy Revenue* (CR-061 §5 finding 1). Keeping it here
    #     guarantees a fight the day that chart is adopted.
    #   * **47xx is where that chart puts this kind of account.** Its *Revenue
    #     Adjustments* block is 4700 billing adjustment · 4710 leak adjustment ·
    #     4720 rate correction · 4730 customer credit · 4740 refunds · 4750
    #     bad-debt write-off, every row **Normal Balance = Debit**. 4760 is the
    #     first slot past every row that chart names, so adopting the block in
    #     full later adds its six rows and moves this one nowhere.
    #   * **A discount is none of those six.** It is not a correction, not a
    #     credit note and not a refund; it is a reduction granted at pricing
    #     time under a programme (BR-RAT-068, *"subsidy granted is reportable"*).
    #     Taking 4700 or 4730 for it would mis-name it and collide later.
    #
    # ⚠ **THE MOVE COST NOTHING BECAUSE OF A WINDOW THAT IS ALREADY CLOSING.**
    # PO, 2026-09-01, verbatim: *"we are in beta stage - so no real utility is
    # actually onboarded yet - so there is no real data yet - hence you can fix
    # it; I will delete the DB and relaunch"*. Hard rule 4 is NOT waived by that
    # and nothing about it changed — journal lines are still append-only — but
    # an append-only table with no rows in it can be reshaped for nothing. **The
    # first bill a real utility issues against this account ends the window**,
    # and after that a renumbering is a mapping-and-migration programme.
    #
    # ⚠ **NO MIGRATION IS WRITTEN FOR THIS AND THAT IS DELIBERATE.** Seeding
    # runs at PROVISIONING and `_create_missing_accounts` skips any code the
    # tenant already has (*"rule 1: the tenant's chart is the tenant's"*), so a
    # database that already holds `4300 … revenue` KEEPS it — hard-won law 4,
    # *"a template change never reaches a host that already has a `.env`"*. The
    # PO's own answer to that is the sentence above: the database is being
    # deleted. Any deployment that is NOT deleted needs `OQ-1280` answered
    # first, because re-typing an account that has been posted against restates
    # the Type column of a trial balance somebody has already read.
    #
    # `signed=False` and listed in `PENDING_FINANCE_RE_SIGN`, unchanged and for
    # the same reason as before: B5 line 74 is ❄️ FROZEN and is NOT edited
    # inline, so the code and the name await a finance re-sign via HUMAN-GUIDE
    # §6 and every surface that offers the account says so. **The PO's "assign a
    # different number" is a ruling on the NUMBER, not a finance signature on
    # the chart** — its own review row says a signature on the name is not one.
    SeedAccount(
        "4760",
        "Customer discounts (contra-revenue)",
        "contra_revenue",
        DISCOUNT_CONTRA_REVENUE,
        False,
        CAT_REVENUE_ADJUSTMENTS,
    ),
    SeedAccount("6800", "Bank fees", "expense", BANK_FEES, category=CAT_OPERATING_EXPENSES),
    # ── CR-136-BRC07 §3.3, PO ruling 2026-09-23 · task `P2.21` ─────────────
    # *"A short writes a balanced pair to a cash over/short account the day it
    # is declared. Needs one new account added to the chart"*. The block above
    # `CASH_OVER_SHORT` carries both worked directions.
    #
    # **`signed=False`, on the 4160/4170/4180/4760 precedent.** B5 line 74 is
    # ❄️ FROZEN and names two expense accounts, `6800` and `6900`; the PO ruled
    # that an account should EXIST and did not state its number, its name or
    # its type, so those three are this lane's reading of the chart's own
    # ladder and await a finance re-sign via HUMAN-GUIDE §6. **A ruling that a
    # posting needs a home is not a finance signature on a chart row** — the
    # same reading `4760` carries, in its own words one screen up.
    #
    # **`6850` because it is the only slot between the two signed expense
    # codes.** The PO's 111-row reference chart (CR-061 §5) files bank charges
    # and bad debt in the same Operating Expenses block and leaves 68xx free
    # above `6800`; seating it there puts a drawer difference beside the two
    # other costs that arise from meter-to-cash itself rather than from buying
    # commodity, which is what `CAT_OPERATING_EXPENSES` means here.
    SeedAccount(
        "6850",
        "Cash over and short",
        "expense",
        CASH_OVER_SHORT,
        False,
        CAT_OPERATING_EXPENSES,
    ),
    SeedAccount("6900", "Bad debt", "expense", WRITE_OFF, category=CAT_OPERATING_EXPENSES),
    SeedAccount(
        "6950",
        "Deposit interest expense",
        "expense",
        DEPOSIT_INTEREST_EXPENSE,
        category=CAT_OPERATING_EXPENSES,
    ),
)

#: Every designation the seed chart places, for the assertion that this file is
#: internally consistent (`tests/test_us_led_005_gl_designations.py` fails if a
#: designation is added to GL_DESIGNATIONS with no seeded home, which is how a
#: twelfth designation smuggled in past the OQ discipline would go RED).
SEEDED_DESIGNATIONS: tuple[str, ...] = tuple(
    row.designation for row in SEED_CHART if row.designation is not None
)

#: ⚠ **THE DESIGNATIONS THAT ARE *NOT* CLAIMED AT PROVISIONING, AND ARE CLAIMED
#: ON FIRST USE INSTEAD — `DEF-3441`.**
#:
#: `tests/test_us_led_005_gl_designations.py` asserted for a month that EVERY
#: designation resolves the moment a tenant is provisioned, and that was true
#: until 2026-09-02. Two things happened that day and neither lane ran the file:
#:
#:   * `CR-060` T7b moved `accrued_expenses` and `accumulated_depreciation` onto
#:     accounts the seed already creates (`2100` and `1730`), and the PLACEMENT
#:     is `services.ensure_period_matching_accounts` rather than the seed — for
#:     hard-won law 4's reason, because a seed edit reaches no host that already
#:     exists;
#:   * `CR-060` T15 (2026-09-03) added `allowance_doubtful_accounts`, which is
#:     claimed when a tenant SWITCHES THE POLICY ON and never before —
#:     `chart.py` judgment 3's surviving half.
#:
#: So the guard now asks the question that is true: **a designation resolves at
#: provisioning UNLESS it is one of these**, and adding a fourth is a deliberate
#: one-line edit here rather than a red test somebody deletes. A designation
#: that stops resolving and is NOT named here still goes RED, which is the
#: property the original guard had and the reason it was worth keeping.
#:
#: `depreciation_expense` is deliberately ABSENT: `5700` is minted by the seed
#: itself (`PERIOD_MATCHING_CHART` is inside `services._wanted_rows`), so it
#: resolves on day one like the other thirteen.
#: ⚠ **CR-197-BRC10 adds `refunds_payable`, which is never claimed by code at
#: all: the TENANT picks its account on the GL mapping list, and until one does
#: a refund posts exactly as it always has (BR-LED-803).** It is enumerated in
#: `CHOSEN_BY_TENANT` as well, so a guard that asks "where is this designation's
#: home" can name the answer rather than miss it.
CHOSEN_BY_TENANT: tuple[str, ...] = (REFUNDS_PAYABLE,)

DESIGNATED_ON_FIRST_USE: tuple[str, ...] = (
    ACCRUED_EXPENSES,
    ACCUMULATED_DEPRECIATION,
    ALLOWANCE_DOUBTFUL_ACCOUNTS,
    *CHOSEN_BY_TENANT,
)

#: ⚠ **EMPTY SINCE 2026-08-18, AND EMPTINESS IS THE GOAL STATE IT REACHED.**
#:
#: The invariant *every designation has a seeded account* is a real guard and it
#: stays; this tuple names the exceptions, and the test asserts its exact
#: contents so an unseeded designation cannot arrive quietly.
#:
#: From 2026-08-15 it held `budget_variance`: the PO had ruled the DESIGNATION
#: into existence (*"Create seperate account"*, OQ-142) while its ACCOUNT was an
#: addition to ❄️ frozen B5 line 74 that no agent could seed. The PO closed that
#: gap on 2026-08-17 (CR-010 B-8, verbatim: *"8 - A ✅ 4180 "Budget billing
#: variance", revenue, signed=False (the 4160/4170 precedent)"*), so `SEED_CHART`
#: now carries 4180 with the designation and this tuple is `()`. Note the two
#: pending states are DIFFERENT and both are still tracked: an unseeded
#: DESIGNATION lives here; an unsigned CODE lives in `PENDING_FINANCE_RE_SIGN`
#: below — 4180 is in the second, not the first.
PENDING_FINANCE_RESIGN: tuple[str, ...] = ()

#: The codes finance has NOT signed — judgment call 2. Derived from the rows
#: themselves so it can never disagree with them, and asserted by the test suite
#: so that adding an unsigned row silently, or dropping a flag without a finance
#: re-sign, goes RED. Empty is the goal state; it is reached by a finance
#: re-sign through HUMAN-GUIDE §6, never by an inline edit here. It was empty
#: from 2026-08-11 (the 4160/4170 addendum) until 2026-08-18, when **4180**
#: entered under the PO's CR-010 B-8 ruling of 2026-08-17 with `signed=False` —
#: the exact declaration 4160/4170 carried while THEY waited.
#:
#: ⚠ **IT IS EMPTY AGAIN SINCE LATER THE SAME DAY.** The PO finance re-signed
#: 4180 on 2026-08-18 together with the eight cost rows, having been shown the
#: nine codes and names in plain English with no dollar figure attached to any
#: of them (see this module's docstring addendum for exactly what was shown).
#: So `()` is once more the live value, and the guard is unchanged: the next row
#: added without a signature lands here and every surface says so.
PENDING_FINANCE_RE_SIGN: tuple[str, ...] = tuple(row.code for row in SEED_CHART if not row.signed)

#: Where the re-sign has to come from, named once so it is greppable from the
#: code as well as from the governance files.
PENDING_FINANCE_RE_SIGN_SOURCE = (
    "B5 line 74 (04-docs/02-decisions/05-golden-tests.md) — ❄️ FROZEN, finance-signed "
    "2026-08-08, names eight services. 4160/4170 were added under the PO's closure of "
    "OQ-115 (2026-08-11) and finance re-signed by dated addendum the same day. 4180 "
    "Budget billing variance was added under the PO's CR-010 B-8 ruling (2026-08-17, "
    "'8 - A') and was finance re-signed on 2026-08-18 by the same kind of dated addendum "
    "— the codes and names only, no figure. 4300 Customer discounts (contra-revenue) "
    "was added under the PO's discount ruling of 2026-08-28 ('you will need differnt GL "
    "code for these ... create differnt category as required') and is NOT yet re-signed: "
    "the ruling settles that a discount gets its own code in its own category, and the "
    "NUMBER and the NAME are the lane's reading of this chart's ladder. 4155 Fire was "
    "added under the PO's CR-063 ruling of 2026-09-02 ('We will need Fire as utility "
    "Service') and is NOT yet re-signed either, on exactly the same terms: the RULING is "
    "that fire exists and is billed, and the CODE and the NAME are this lane's reading of "
    "the ladder -- 4155 was free and sits between 4150 Capacity and 4160 Storm water. "
    "4600 Connection & new-service fees, 4610 Disconnection & reconnection fees, 4630 "
    "Field-service & meter fees, 4640 Equipment recovery & penalties, 4650 Billing & "
    "payment fees, 4700 Billing adjustment, 4710 Leak adjustment, 4720 Rate / meter "
    "correction and 4730 Customer credit were added under the PO's CR-066 ruling of "
    "2026-09-02 ('these are all correct - you can apply them as part of Seed data' and "
    "'these are all good - please apply these') and are NOT re-signed either. The PO "
    "approved the MAPPING -- which charge code and which adjustment reason posts where -- "
    "having been shown every account name and number in plain English; a finance signature "
    "on the chart is a separate act, no dollar figure was attached to any of the nine, and "
    "no B4/B5 figure moved. 6850 Cash over and short was added under the PO's "
    "CR-136-BRC07 ruling of 2026-09-23 ('A short writes a balanced pair to a cash "
    "over/short account the day it is declared. Needs one new account added to the "
    "chart') and is NOT re-signed either, on the same terms again: the RULING is that "
    "a counted drawer difference reaches the books, and the CODE, the NAME and the "
    "TYPE are this lane's reading of the ladder -- 6850 was free and is the only slot "
    "between the two signed expense codes 6800 Bank fees and 6900 Bad debt. The "
    "$12.0000 in that ruling is the worked CASE and not a figure attached to this "
    "account: the amount a drawer is out by is counted by a clerk, never seeded. Any "
    "FUTURE row "
    "added to this chart without a "
    "signature awaits a finance re-sign via HUMAN-GUIDE §6, which is the only route."
)


#: Service code → (usage revenue code, base revenue code or None). B5 line 74:
#: *"4100/4105 Electric usage/base · 4110/4115 Water usage/base · 4120 Sewer ·
#: 4130 Trash · 4140 Gas · 4145 Broadband · 4150 Capacity (solar/battery)"*, plus
#: `storm_water` → 4160 and `thermal_heat` → 4170 from the PO's OQ-115 closure
#: (2026-08-11) — those two codes were finance re-signed by dated addendum on
#: 2026-08-11 (this line said they are NOT signed until 2026-08-18); see
#: judgment call 2 for the posture they were declared under.
#: ⚠ **`solar` AND `battery` BOTH POINTED AT 4150 UNTIL 2026-09-03 — read that
#: in the past tense (hard-won law 1).** The signed line names one account for
#: the pair, and the PO ruled the pair apart: *"We need seperate code for Solar
#: 4150 and Battery 4150"*. Solar keeps 4150; battery is 4165, and neither row
#: is signed any more — see both `SeedAccount` rows for why.
#: A `None` base means "no split in the chart": the base line then falls back to
#: the usage account, which is BR-BIL-010's reason for making the split optional
#: rather than a second required field.
#:
#: **THIS IS A DEFAULT, NOT A FIXTURE** (PO 2026-08-11). It says which account a
#: service STARTS pointing at, on the day the tenant enables it. The tenant may
#: re-point it afterwards, and nothing here overwrites that — the live answer is
#: always `tenant_services.revenue_account`.
#: **ALL ELEVEN CATALOG SERVICES ARE MAPPED** (BR-RAT-024, amended 2026-09-02 —
#: `fire` joined as the eleventh under `CR-063`). A service missing from
#: this dict would reach provisioning with a NULL revenue account and fail its
#: whole bill at issue under BR-BIL-010, so a test asserts the ten.
SERVICE_REVENUE_ACCOUNTS: dict[str, tuple[str, str | None]] = {
    "electric": ("4100", "4105"),
    "water": ("4110", "4115"),
    "gas": ("4140", None),
    "sewer": ("4120", None),
    "trash": ("4130", None),
    "broadband": ("4145", None),
    "solar": ("4150", None),
    # ⚠ **BATTERY LEFT 4150 ON 2026-09-03 (PO: *"We need seperate code for Solar
    # 4150 and Battery 4150"*).** Both pointed here because the signed line
    # names one account for the pair; a utility selling both then saw one
    # number in its books and could not tell them apart. See the `SeedAccount`
    # rows above for why 4165 and why neither row is signed.
    "battery": ("4165", None),
    "storm_water": ("4160", None),  # re-signed 2026-08-11 — judgment call 2
    "thermal_heat": ("4170", None),  # re-signed 2026-08-11 — judgment call 2
    # CR-063 — the ELEVENTH service. `4155` is UNSIGNED and is in
    # `PENDING_FINANCE_RE_SIGN`; see the `SeedAccount` row above for why the
    # code and the name are the lane's reading of this ladder and not a
    # signature, and why fire does not share solar and battery's `4150`.
    #
    # ⚠ **A SERVICE MISSING FROM THIS DICT REACHES PROVISIONING WITH A NULL
    # REVENUE ACCOUNT AND FAILS ITS WHOLE BILL AT ISSUE (BR-BIL-010)** — which
    # is why the sentence above this map says the count is asserted by a test.
    # That test is what makes adding a catalogue row without an account here a
    # RED run rather than a tenant that signs up fine and cannot be invoiced.
    "fire": ("4155", None),
}

#: The codes that are CONDITIONAL on a tenant selling the service (PO ruling
#: 2026-08-11, OQ-115). Derived from the map above rather than listed, so a new
#: service cannot be added without its account becoming conditional too. Every
#: OTHER row of SEED_CHART is shared and every tenant gets it — see the module
#: docstring for why 4190/4200/4210 are shared despite being revenue accounts.
SERVICE_REVENUE_CODES: frozenset[str] = frozenset(
    code for pair in SERVICE_REVENUE_ACCOUNTS.values() for code in pair if code is not None
)

#: The rows every tenant is seeded, whatever it sells. All eleven designations
#: are in here, which is what lets a one-service tenant still resolve every
#: designation a posting entry asks for.
SHARED_CHART: tuple[SeedAccount, ...] = tuple(
    row for row in SEED_CHART if row.code not in SERVICE_REVENUE_CODES
)


# ══════════════════════════════════════════════════════════════════════════
# CR-066 — WHERE A CHARGE CODE, AN ADJUSTMENT REASON AND A DISCOUNT START
# ══════════════════════════════════════════════════════════════════════════
#
# ⚠ **READ `SERVICE_REVENUE_ACCOUNTS`'s OWN SENTENCE FIRST: THIS IS A DEFAULT,
# NOT A FIXTURE.** Every map below says where a row STARTS pointing on the day
# it is seeded. The live answer is the tenant's own column —
# `charges.gl_account_id`, `reason_codes.default_gl_account_id`,
# `discounts.gl_account_id` — edited on S8 → Accounting, and nothing here ever
# overwrites one a tenant has set (`BR-TEN-012`).
#
# **WHY THEY EXIST:** `DEF-2386`. A fee line resolves its account from the
# charge code and refuses the whole bill when the column is null, so a fresh
# tenant with 28 unmapped codes could not issue a bill carrying a fee. The PO
# approved the three tables on 2026-09-02 (CR-066 §5) and these are those
# tables, transcribed.


#: Charge code → seed account CODE. CR-066 table 1, as approved: *"these are
#: all correct - you can apply them as part of Seed data"*.
#:
#: ⚠ **THIS LINE READ *"for the codes the platform fixture ships"* UNTIL
#: 2026-09-16 AND IS NOW ONE ENTRY TOO NARROW.** `CC-REQFEE` is seeded by the
#: SAMPLE-data button rather than by `lookup_defaults.json` (see its own note
#: below), so the map answers *every code any seeder in this repo creates* and
#: not only the platform 25. `G70` walks the platform fixture toward this map
#: and is unaffected — it asks that every SHIPPED code is answered here, never
#: that every entry here is shipped.
#:
#: ⚠ **THE `BASE-*` FAMILY IS DELIBERATELY ABSENT FROM THIS MAP.** A base
#: charge code posts to ITS OWN SERVICE's revenue account, and that is a RULE
#: rather than a list — the CR says so in as many words, because the five base
#: codes a water/sewer/trash/fire tenant happens to hold are not the family:
#: `BASE-E`, `BASE-G`, `BASE-TH`, `BASE-SOL`, `BASE-BAT`, `BASE-BB`, `BASE-SW`
#: and `BASE-FIRE` are seeded per service sold. Listing the five would give the
#: next utility the identical unmapped-code wall this defect is about.
#: `default_gl_account_id_for_charge_code` applies the rule through
#: `revenue_account_id_for_service`, which is the SAME map
#: `SERVICE_REVENUE_ACCOUNTS` above holds and which answers wherever the tenant
#: has re-pointed the service TODAY.
CHARGE_CODE_ACCOUNTS: dict[str, str] = {
    # It is water SOLD, not a fee — the PO's own note on the table row.
    "BULK-WATER": "4110",
    "LATE": "4200",
    "NSF": "4210",
    # 4600 · Connection & new-service fees
    "CONN": "4600",
    "TAP": "4600",
    "TEMP-SVC": "4600",
    "TRANSFER": "4600",
    # ── `CC-REQFEE`, ADDED 2026-09-16 · `DEF-RAT-5424` ──────────────────────
    # ⚠ **THE FIRST CODE IN THIS MAP THAT THE PLATFORM FIXTURE DOES NOT SHIP,
    # SO THE COMMENT ABOVE IT IS NOW TOO NARROW AND IS AMENDED WHERE IT
    # STANDS.** `apps/rating/sample_data.seed_sample_request_fee_charge_code`
    # creates it on the SAMPLE-data button, beside the service requests that
    # quote it; `lookup_defaults.json` is untouched, because widening that list
    # changes what every utility in the world is provisioned with and CR-066's
    # table is the PO's.
    #
    # **WHY IT IS HERE AND NOT IN THAT SEEDER:** one home for the mapping. A
    # charge code's account is `charges.gl_account_id`, a tenant's own column;
    # this table only says where it STARTS, and a second table saying the same
    # thing somewhere else is how two answers come to disagree.
    #
    # **WHY 4600.** An application to take service is a new-service fee, so it
    # sits with `CONN`, `TAP`, `TEMP-SVC` and `TRANSFER` — the category the
    # chart already has. Nothing was numbered and nothing was invented.
    # Worked, and it is the ruling of 2026-09-15 end to end: `$25.00` cash
    # taken at the counter posts `DR 1010 25.0000 · CR 2400 25.0000`, and
    # approving or refusing the application posts `DR 2400 25.0000 · CR 4600
    # 25.0000` — debits equal credits at both moments, and the `$25.00` ends up
    # earned instead of held for ever. Without this line the release posts
    # nothing and `release_error` names the setting to fix; a clerk is never
    # blocked either way, which is why nothing surfaced it for a day.
    "CC-REQFEE": "4600",
    # ⚠ `OQ-1343` IS OPEN ON THIS ONE ROW. An impact fee is a capacity charge
    # many utilities treat as a contribution toward CONSTRUCTION rather than as
    # revenue, in which case it belongs in equity or in a deferred-contribution
    # liability and not at 4600 at all. The PO was told so in the same message
    # that carried the table and approved the table; finance has not signed the
    # treatment. It posts here until they do, and the question says so.
    "IMPACT": "4600",
    # 4610 · Disconnection & reconnection fees
    "DISC": "4610",
    "RECON": "4610",
    "SEASONAL": "4610",
    # 4630 · Field-service & meter fees
    "AFTER-HRS": "4630",
    "RETURN-TRIP": "4630",
    "SAME-DAY": "4630",
    "METER-TEST": "4630",
    "RE-READ": "4630",
    "MOVE-OUT": "4630",
    "INSPECT": "4630",
    "HYDRANT": "4630",
    # 4640 · Equipment recovery & penalties
    "DAMAGE": "4640",
    "TAMPER": "4640",
    # 4650 · Billing & payment fees
    "PAPER": "4650",
    "CC-CONV": "4650",
}

#: The fixture charge codes this map deliberately does NOT answer for, and why —
#: the same posture `apps.rating.services.CHARGE_CODES_NOT_SEEDED` takes about
#: the rows themselves, stated here so `G51` can tell a RULING apart from a GAP.
#: A gate that could not make that distinction would either go red forever or
#: wave the next unmapped code through.
CHARGE_CODE_ACCOUNTS_NOT_MAPPED: dict[str, str] = {
    "DEPO-R": (
        "NO ROW EXISTS TO MAP. `apps.rating.services.CHARGE_CODES_NOT_SEEDED` refuses to "
        "create this code at all — BR-RAT-020/BR-RAT-023 put deposit amounts on the PLAN's "
        "deposit rules and explicitly supersede a flat deposit charge — so there is no "
        "`charges` row and nothing for a bill line to resolve. A deposit is also not "
        "revenue: it is a liability at 2300, taken and owed back, and mapping this code to "
        "a 46xx fee account would say the opposite. Absent from CR-066 table 1 for the same "
        "reason: the PO was shown the 28 codes a tenant actually has."
    ),
    "DEPO-C": (
        "NO ROW EXISTS TO MAP — the same ruling as DEPO-R, for the commercial category "
        "(CR-010 A2, PO 2026-08-17)."
    ),
}

#: Adjustment reason → seed account CODE. CR-066 table 2, as approved: *"these
#: are all good - please apply these"*.
#:
#: ⚠ **THIS CHANGES NOTHING TODAY AND THE PO WAS TOLD SO BEFORE THEY APPROVED
#: IT.** Nothing in the backend posts an adjustment through a reason code — a
#: credit reverses whatever account the original bill credited — so these four
#: accounts collect nothing until something reads the column. The mapping is
#: correct to have and it is NOT what unblocks a bill.
#:
#: ⚠ **IT SUPERSEDES A DECISION OF OUR OWN.** `CR-040` task A1 was closed *"not
#: to be seeded"* in the decision log on 2026-08-27, on the reasoning that the
#: signed chart had no general adjustments account to point at. That reasoning
#: was sound and is now spent: the PO has ruled the accounts into existence and
#: named which reason goes to which. The screen note that told a clerk the
#: column was blank by decision moves with it.
REASON_CODE_ACCOUNTS: dict[str, str] = {
    "BILLERR": "4700",
    "LEAK": "4710",
    "METERR": "4720",
    "GOODWILL": "4730",
    # The PO put `DISPUTE` on 4700 with `BILLERR` — a dispute resolved in the
    # customer's favour IS a billing adjustment, and the table says so.
    "DISPUTE": "4700",
}

#: Every discount starts at the contra-revenue account CR-061 already ruled
#: into existence. CR-066 table 3, as approved: *"Please apply these"*.
#:
#: `CR-061`'s ruling of 2026-09-01 — *"no, you cannot file discount under
#: revenue"* — is HONOURED here rather than revisited. Discount LINES already
#: resolve to this account by designation at issue (`issue.py`, `kind ==
#: "discount"`); what CR-066 adds is the tenant-editable COLUMN and the row on
#: screen, so a utility that files its low-income programme somewhere else can
#: say so.
DISCOUNT_DEFAULT_ACCOUNT: str = "4760"


#: The tax-payable series, and the ONLY thing this module states about a tax
#: authority's account. B5 line 74 (❄️ finance-signed 2026-08-08) verbatim:
#: *"2200-series Tax payable per authority (tenant authorities mint their own)"*.
#: The series is signed; the SUFFIX is not — whether a tenant types `2200-01` or
#: the product generates it was **OQ-147**, CLOSED 2026-08-12 (PO: *"Generated"*) —
#: the allocator lives in `services._next_tax_payable_code`, so nothing
#: here builds a code.
TAX_PAYABLE_SERIES = "2200"

#: The account TYPE a tax-payable account carries. `2xxx` is the liability rung
#: of the chart's own ladder (judgment call 1 in this module's docstring), and
#: 2300 / 2400 — the two signed 2xxx rows — are both liabilities. Tax collected
#: and not yet remitted is money the utility holds for someone else, so nothing
#: here is stretching the ladder to reach the answer.
TAX_PAYABLE_TYPE = "liability"


def is_tax_payable_code(code: str) -> bool:
    """Is `code` in the signed 2200 series? Used to REFUSE anything else.

    Deliberately a prefix test and nothing more. `2200`, `2200-01`, `2200.TX`
    and `220017` all pass; `2300` (the signed deposit-liability row) and `4100`
    do not. It is not this module's place to rule on the shape of the suffix —
    that is OQ-147 — only to keep a tax authority out of the deposit liability
    and out of revenue, which is the half B5 does sign.
    """
    return bool(code) and str(code).startswith(TAX_PAYABLE_SERIES)


def is_tax_payable_account(code: str | None, seed_key: str | None = None) -> bool:
    """Is this EXISTING account a tax liability? — `CR-196-BRC10`, judgment 5b.

    `is_tax_payable_code` above judges a code being TYPED, and stays the test for
    a new account. This one judges an account that already exists, and since the
    PO's ruling of 2026-10-29 a System Admin may renumber a tax account out of
    the prefix entirely: a utility renames `2200-01` to `0117-080-1000-0000-7126`
    because that is ITS number for the State liability. Read by code alone, that
    account stops being tax the moment it is renamed — a remittance against it
    is refused and it drops off the tax report while still holding the money.

    So the account is tax when its code is in the series (exactly as before) OR
    when the code it was minted under (`ledger_accounts.seed_key`, internal and
    never changed by a code edit) is.
    """
    return is_tax_payable_code(code or "") or (
        bool(seed_key) and is_tax_payable_code(str(seed_key))
    )


def seed_codes() -> frozenset[str]:
    """Every code ANY seed path in this file plants — `CR-196-BRC10`.

    `ledger/0021` back-fills `ledger_accounts.seed_key` from it for accounts
    that existed before the column did. Derived, never re-listed, so a row
    added to a tuple below cannot be missed by the back-fill's reader.
    """
    return frozenset(
        row.code
        for row in (
            SEED_CHART
            + COST_OF_SERVICE_CHART
            + WIDENED_COST_CHART
            + UTILITY_BOOKS_CHART
            + PERIOD_MATCHING_CHART
            + ALLOWANCE_CHART
            + CASH_OVER_SHORT_CHART
        )
    )


def seed_rows_for_service(service_code: str) -> tuple[SeedAccount, ...]:
    """The seed rows a service needs — () for a code no service names.

    One place answers "which accounts does enabling Gas require", so the
    provisioning path and the S8 toggle path cannot drift apart on it.
    """
    pairing = SERVICE_REVENUE_ACCOUNTS.get(service_code)
    if pairing is None:
        return ()
    wanted = {code for code in pairing if code is not None}
    return tuple(row for row in SEED_CHART if row.code in wanted)


# ═══════════════════════════════════════════════════════════════════════════
# THE COST-OF-SERVICE SECTION (US-LED-017 · BR-LED-037 · BR-LED-038)
# ✅ FINANCE RE-SIGNED 2026-08-18 — every row below carries signed=True
# ═══════════════════════════════════════════════════════════════════════════
#
# ⚠ **THIS BANNER READ "PROPOSED AND NOT FINANCE-SIGNED — every row below
# carries signed=False" UNTIL 2026-08-18.** The Product Owner re-signed all
# eight codes and names that day in the working chat session (see the module
# docstring's addendum for exactly what was shown, and for what the signature
# does NOT cover — no amount, rate or default is ratified by it). The prose
# below is the record of WHY the section was built as a separate tuple; every
# sentence in it that speaks in the present tense about the absence of a
# signature is stamped in place, because the reasoning still governs the NEXT
# row somebody adds without one.
#
# **WHY IT IS A SEPARATE TUPLE AND NOT EIGHT MORE ROWS IN `SEED_CHART`.**
# `SEED_CHART` is the machine copy of **B5 line 74 — ❄️ FROZEN, finance-signed
# 2026-08-08**, plus the two rows finance re-signed by dated addendum on
# 2026-08-11. Every row in it has a signature behind it, and
# `PENDING_FINANCE_RE_SIGN` is empty because that is the goal state the existing
# test asserts. **These eight rows had no signature at all when they were
# written (2026-08-15 → 2026-08-18).** Mixing them in
# would make one tuple mean two different things — "what finance signed" and
# "what a lane proposed" — and the first surface to iterate `SEED_CHART` would
# present a proposal as law, which is exactly the failure US-LED-017 TC-5 exists
# to catch and hard-won law 1 in one sentence.
#
# So the distinction is carried in the DATA, in two places at once: `signed`
# (the field `SeedAccount` already has, for exactly this — it was False on every
# row of this section until the 2026-08-18 re-sign flipped all eight to True) and
# the section lives in its own tuple that no signed-chart reader touches.
# `PENDING_FINANCE_RE_SIGN_COST` is derived from the rows rather than listed, so
# it can never disagree with them.
#
# **THE ROUTE OUT, AND IT WAS TAKEN.** B5 line 74 is ❄️ FROZEN and CLAUDE.md is
# explicit: *"Changing a signed rule or figure needs a finance re-sign via
# HUMAN-GUIDE §6, never an inline edit."* B5 WAS NOT EDITED, then or on
# 2026-08-18, and no agent wrote a signature. The re-sign came from the Product
# Owner — the sign-off authority per their own ruling of 2026-08-11 — and landed
# as a DATED ADDENDUM BESIDE the frozen chart, the same shape the 4160/4170
# addendum took on 2026-08-11 and the concession account before it. The change
# was exactly what this paragraph predicted: one word per row (`False` → `True`)
# plus the test figure. **The route is unchanged for the next row**: an account
# nobody signed seeds marked-unsigned and no surface may present it as signed.
#
# **WHAT THE CHART HOLDS TODAY, FOR CONTRAST** (decision log 2026-08-12 and
# 2026-08-15): exactly **two** expense accounts — **6800 Bank fees** and **6900
# Bad debt** — plus 6950 Deposit interest expense, every one of them arising
# from meter-to-cash itself. Purchased power, purchased water, purchased gas,
# O&M and infrastructure have **no accounts at all**, which is why a captured
# supplier invoice had nowhere to point.
#
# **WHY 51xx MIRRORS 41xx DIGIT FOR DIGIT** (BR-LED-037): a reviewer checks the
# whole section in one pass against a ladder finance already signed, and a
# tenant reading a trial balance finds 4110 and 5110 side by side for the same
# service.
#
# ⚠ **THE LIABILITY SIDE IS DELIBERATELY ABSENT.** If a capture POSTS
# (OQ-200 reading (a)) the credit needs an `Accounts payable` account in the
# 2xxx series that **nothing in this product ever drains**, because BR-LED-028
# forbids payment runs. Proposing it here would smuggle the answer to an OPEN
# question into the chart. See `apps/ledger/cost_capture.post_capture_to_journal`,
# which raises `NotImplementedError("OQ-200")` at that boundary.

#: The two non-commodity categories, in the PO's own words from OQ-188:
#: *"electric purchases   Water purchase   O&M cost, infra cost"*. They are
#: CATEGORIES rather than services — they belong to the tenant's service list in
#: no sense at all, they are seeded to every tenant, and **they carry no volume
#: denominator**, which is why one pipe invoice does not suppress the water
#: unaccounted-for figure (BR-LED-031's per-service scope).
COST_CATEGORY_OM = "operations_maintenance"
COST_CATEGORY_INFRASTRUCTURE = "infrastructure"


class CostCategory(NamedTuple):
    """One non-service cost category — the vocabulary, in ONE place.

    ⚠ **ADDED 2026-09-01 (CR-060 C15 · task T5).** Until today the non-service
    half of the vocabulary was the two constants above and nothing else, and a
    tenant could not record payroll, insurance, a legal bill, postage, fuel or
    rent anywhere in this product — so the promise of *"everything in one
    place"* was not true. BR-LED-029 is AMENDED with the widened list and its
    capital refusal.

    `enters_recovery_denominator` **HAS NO DEFAULT, DELIBERATELY, AND THAT IS
    THE WHOLE OF TASK T7c.** Until the vocabulary widened, *"is this code not a
    service"* and *"does it have no volume denominator"* had the same answer,
    because the only two categories that existed were O&M and Infrastructure —
    and `cost_reconciliation.py` asked the first question to answer the second.
    **With sixteen categories that coupling is the defect waiting to happen:** a
    category added here and forgotten in an excluded set elsewhere would be read
    as a commodity and sent to the billed-volume read, which is how payroll ends
    up inside a water ratio. Making the field required means a new category
    cannot be added without someone answering it.

    **It is False on all sixteen today.** Payroll and insurance have no
    delivered quantity and must NEVER enter bought-versus-billed (BR-LED-031, as
    amended) — a payroll figure in that denominator is not a smaller error than
    the −13.75% the all-or-nothing rule exists to suppress, it is the same
    error. A constant-False flag is a check that cannot fail, so
    `tests/test_cr060_t5_cost_categories.py` drives it from a SYNTHETIC category
    whose flag is True, the same way `test_us_led_017_cost_chart` drives the
    unsigned-account mechanism from a synthetic unsigned code.

    `group` is the operating-statement bucket the category rolls up to, so the
    accounting export lands in recognisable buckets rather than one flat
    "costs" total, and so the reconciliation's ABSENT reason is per GROUP —
    the single sentence about *"pipe, valves and meters"* was true of
    Infrastructure and would have been wrong on fourteen of sixteen rows.

    `caution` is a sentence a surface prints beside the category or `None`. Only
    payroll carries one today, and CR-060 §6 is explicit about why: *"a single
    figure is fine as a record of what left the bank … but it is not payroll
    accounting: the withholdings a utility holds back for the employee and
    remits to the government are a liability, and a one-line record does not
    carry them."*
    """

    code: str
    account_code: str
    account_name: str
    group: str
    group_label: str
    enters_recovery_denominator: bool
    caution: str | None = None


#: The five operating-statement groups, in the order a US utility statement
#: prints them. `cost_of_service` is the SERVICE half and belongs to no row
#: below: those categories ARE the tenant's live service codes (BR-REP-006).
COST_GROUP_OM = "operations_maintenance"
COST_GROUP_INFRASTRUCTURE = "infrastructure"
COST_GROUP_CUSTOMER_ACCOUNTS = "customer_accounts"
COST_GROUP_ADMIN = "administrative_general"
COST_GROUP_TAXES = "taxes_other_than_income"

#: ⚠ **THE VOCABULARY, AND THE ORDER IS THE PICKER'S ORDER.**
#:
#: `operations_maintenance` (5200) and `infrastructure` (5300) come FIRST and
#: are unchanged — they are the PO's own *"O&M cost, infra cost"* from OQ-188,
#: rows already point at them, and CI-8's $1,845.50 of pipe and CI-9's
#: $12,500.00 of meters are captured against them in the live fixture. **Nothing
#: is re-categorised by this change**; the flat O&M bucket is KEPT beside its
#: three splits rather than replaced, because replacing it would orphan every
#: row already filed there.
COST_CATEGORY_SPECS: tuple[CostCategory, ...] = (
    # ── Operations & maintenance — the flat bucket, plus CR-060 §6's split ──
    CostCategory(
        COST_CATEGORY_OM,
        "5200",
        "Operations & maintenance",
        COST_GROUP_OM,
        "Operations & maintenance",
        False,
    ),
    CostCategory(
        "om_labour",
        "5210",
        "O&M — labour",
        COST_GROUP_OM,
        "Operations & maintenance",
        False,
    ),
    CostCategory(
        "om_materials",
        "5220",
        "O&M — materials & supplies",
        COST_GROUP_OM,
        "Operations & maintenance",
        False,
    ),
    CostCategory(
        "om_contract_services",
        "5230",
        "O&M — contract services",
        COST_GROUP_OM,
        "Operations & maintenance",
        False,
    ),
    # ── Infrastructure — unchanged ──────────────────────────────────────────
    CostCategory(
        COST_CATEGORY_INFRASTRUCTURE,
        "5300",
        "Infrastructure",
        COST_GROUP_INFRASTRUCTURE,
        "Infrastructure",
        False,
    ),
    # ── Customer accounts — billing and collection costs ────────────────────
    CostCategory(
        "customer_billing_collection",
        "5400",
        "Customer accounts — billing & collection",
        COST_GROUP_CUSTOMER_ACCOUNTS,
        "Customer accounts",
        False,
    ),
    CostCategory(
        "customer_postage_printing",
        "5410",
        "Customer accounts — postage & printing",
        COST_GROUP_CUSTOMER_ACCOUNTS,
        "Customer accounts",
        False,
    ),
    CostCategory(
        "customer_meter_reading",
        "5420",
        "Customer accounts — meter reading",
        COST_GROUP_CUSTOMER_ACCOUNTS,
        "Customer accounts",
        False,
    ),
    # ── Administrative & general ────────────────────────────────────────────
    CostCategory(
        "admin_payroll_benefits",
        "5500",
        "Payroll & benefits",
        COST_GROUP_ADMIN,
        "Administrative & general",
        False,
        # CR-060 §6's ONE caution on payroll specifically, carried as data so a
        # form, an export header and a test print one sentence rather than
        # three paraphrases.
        "A record of what left the bank, and nothing more. This is not payroll "
        "accounting: the withholdings a utility holds back for an employee and remits to "
        "the government are a liability this product does not carry.",
    ),
    CostCategory(
        "admin_insurance",
        "5510",
        "Insurance",
        COST_GROUP_ADMIN,
        "Administrative & general",
        False,
    ),
    CostCategory(
        "admin_professional_fees",
        "5520",
        "Professional fees",
        COST_GROUP_ADMIN,
        "Administrative & general",
        False,
    ),
    CostCategory(
        "admin_office_rent",
        "5530",
        "Office & rent",
        COST_GROUP_ADMIN,
        "Administrative & general",
        False,
    ),
    # ⚠ RUNNING a vehicle, never BUYING one — `vehicle_purchase` is refused
    # below and the two are separate names for exactly that reason.
    CostCategory(
        "admin_vehicles_fuel",
        "5540",
        "Vehicles & fuel",
        COST_GROUP_ADMIN,
        "Administrative & general",
        False,
    ),
    # ── Taxes other than income — the UTILITY's own taxes ───────────────────
    # Distinct from the customer taxes the Taxes tab remits (BR-BIL-069's 2200
    # series is a LIABILITY collected on a customer's behalf; these are the
    # utility's own EXPENSE and are on the other side of the books entirely).
    CostCategory(
        "tax_property",
        "5600",
        "Property tax",
        COST_GROUP_TAXES,
        "Taxes other than income",
        False,
    ),
    CostCategory(
        "tax_franchise",
        "5610",
        "Franchise tax",
        COST_GROUP_TAXES,
        "Taxes other than income",
        False,
    ),
    CostCategory(
        "tax_payroll",
        "5620",
        "Payroll taxes",
        COST_GROUP_TAXES,
        "Taxes other than income",
        False,
    ),
)

#: Derived, never listed — `COST_CATEGORY_SPECS` is the one place, so this
#: cannot disagree with it. It read `(COST_CATEGORY_OM,
#: COST_CATEGORY_INFRASTRUCTURE)` until 2026-09-01 and the first two entries are
#: still those two, in that order.
COST_CATEGORIES: tuple[str, ...] = tuple(spec.code for spec in COST_CATEGORY_SPECS)

#: By code, for the O(1) lookups the capture and the reconciliation both make.
COST_CATEGORY_BY_CODE: dict[str, CostCategory] = {spec.code: spec for spec in COST_CATEGORY_SPECS}


def enters_recovery_denominator(code: str) -> bool:
    """**Does this cost code enter the bought-versus-billed denominator?**

    ⚠ **THIS IS TASK T7c IN ONE FUNCTION, AND IT REPLACES A MEMBERSHIP TEST.**
    `cost_reconciliation.py` asked `code in COST_CATEGORIES` — *"is this not a
    service"* — to answer *"has this no volume denominator"*. The two questions
    had the same answer while exactly two categories existed. **They do not with
    sixteen**, and the failure mode is silent: a category the vocabulary gains
    and an excluded set does not is read as a commodity, its amount is summed
    into a denominator, and payroll lands in a water ratio.

    **A DECLARED CATEGORY ANSWERS FROM ITS OWN FLAG. False on all sixteen
    today** — payroll, insurance, postage, rent, fuel, the utility's own taxes,
    pipe and valves are none of them a commodity with a delivered quantity.

    **ANYTHING ELSE IS A SERVICE CODE and answers True**, which is exactly
    today's behaviour for the tenant's live service list and changes nothing for
    water, electric or gas. It is not a fail-open hole: the vocabulary refuses
    an unknown code at capture (`cost_capture._refuse_unknown_category`), so the
    only codes that reach here are a declared category or a service — and a
    service whose billed volume cannot be read is already reported ABSENT with
    its reason rather than treated as zero (US-LED-020 TC-9).
    """
    spec = COST_CATEGORY_BY_CODE.get(code)
    if spec is None:
        return True
    return spec.enters_recovery_denominator


#: The categories that enter NO ratio — derived, so it cannot drift from the
#: flags. Named for the reconciliation and for the test that asserts payroll and
#: insurance are in it.
RECOVERY_DENOMINATOR_EXCLUDED: tuple[str, ...] = tuple(
    spec.code for spec in COST_CATEGORY_SPECS if not spec.enters_recovery_denominator
)


# ═══════════════════════════════════════════════════════════════════════════
# CAPITAL SPENDING — REFUSED BY NAME, POINTING AT THE ASSET (CR-060 C15)
# ═══════════════════════════════════════════════════════════════════════════
#: ⚠ **THE ONE THING THE WIDENED VOCABULARY MUST NOT ACCEPT.**
#:
#: CR-060 §6, in as many words: **a $40,000 truck is not an expense.** Recorded
#: as one it overstates this year's costs by $40,000, understates the next five
#: years' by the depreciation that never happens, **and leaves the asset off the
#: balance sheet entirely** — the most common bookkeeping error at this size of
#: utility. **And it does not need solving, because it is solved elsewhere:**
#: the assets module already carries `purchase_cost`, `depreciation_method`,
#: `expected_life_years` and a computed `book_value_amount`.
#:
#: **A NAMED REFUSAL, NEVER A SILENT ABSENCE** — the same posture BR-LED-028
#: takes for the forbidden payable workflows. A missing option reads as a
#: feature nobody thought of; a refusal that says where the money goes instead
#: reads as law, and is the *"this looks like equipment: record it on the asset
#: instead"* the CR asks for.
#:
#: ⚠ **AND IT LANDS BEFORE THE SETTLEMENT POSTING, DELIBERATELY (T5 before T6).**
#: While capture posts nothing a miscategorised row is a tidy-up. Once costs
#: post on settlement it is a wrong number in a signed month, and a correction
#: through reversing entries rather than an edit.
#:
#: ⚠ **`infrastructure` IS NOT ON THIS LIST AND IS NOT BEING ADDED.** CI-9 is
#: $12,500.00 of meters from Katy Meter Works filed there, and re-categorising
#: money a tenant has already captured is not this change's to do.
CAPITAL_CATEGORIES: dict[str, str] = {
    "capital_assets": (
        "a capitalised asset is not a cost of this period. Record it on the asset itself, "
        "where `purchase_cost`, `depreciation_method` and `expected_life_years` already live "
        "and produce a book value — recording it here would overstate this year by the whole "
        "purchase price, understate the next years by the depreciation that never happens, and "
        "leave the asset off the balance sheet entirely"
    ),
    "vehicle_purchase": (
        "buying a vehicle is capital spending and belongs on the asset, not on this tab. "
        "RUNNING one is an operating cost and has a category here — 'Vehicles & fuel' "
        "(`admin_vehicles_fuel`) — which is fuel, servicing and licensing, never the purchase"
    ),
    "equipment_purchase": (
        "equipment is capitalised on the asset, which already carries its cost, its "
        "depreciation method and its expected life. This looks like equipment: record it on "
        "the asset instead"
    ),
    "plant_and_buildings": (
        "plant and buildings are capital assets with a life measured in decades. They belong "
        "on the asset, where the book value is computed; a single expense line here would "
        "misstate both this year's costs and the balance sheet"
    ),
    "depreciation": (
        "depreciation is COMPUTED from the asset's own cost, method and expected life — it is "
        "never invoiced by anybody, so there is no supplier invoice to capture. The asset "
        "module already computes `book_value_amount`; posting depreciation from those figures "
        "is a separate piece of work (CR-060 T7f) and is not a capture"
    ),
}

#: The section, in ladder order — `signed=True` on every row since the
#: 2026-08-18 finance re-sign (it read "The PROPOSED section … `signed=False` on
#: every row" until then), and no
#: `designation` on any of them: a designation is resolved BY NAME by the
#: posting service, and these accounts are pointed at by a captured supplier
#: invoice's own FK, never by a designation lookup. Adding one would also need a
#: migration (see `GL_DESIGNATIONS`' warning), and the signature of 2026-08-18
#: covers these eight CODES AND NAMES only — it does not ratify giving one of
#: them a designation.
# ⚠ **ALL EIGHT FINANCE RE-SIGNED 2026-08-18** (Product Owner, working chat
# session — the sign-off authority per the PO ruling of 2026-08-11). They had
# carried `signed=False` since 2026-08-15, when the AP-capture lane created them
# and correctly refused to mark rows signed that no signed document contained —
# **B5 line 74 ❄️ carries no cost accounts at all.**
#
# The re-sign is a DATED ADDENDUM BESIDE the frozen chart, exactly as 4160/4170
# were re-signed on 2026-08-11. **B5 ITSELF WAS NOT EDITED AND STAYS FROZEN.**
#
# WHAT WAS RATIFIED IS THE EIGHT CODES AND NAMES BELOW AND NOTHING ELSE. No
# amount is attached to any of them; none carries a rate, a rule or a default
# figure. A later lane reading this as cover for a figure is reading it wrong.
COST_OF_SERVICE_CHART: tuple[SeedAccount, ...] = (
    SeedAccount("5100", "Purchased power", "expense", None, True, category=CAT_COST_OF_SERVICE),
    SeedAccount("5110", "Purchased water", "expense", None, True, category=CAT_COST_OF_SERVICE),
    SeedAccount(
        "5120", "Sewer treatment & disposal", "expense", None, True, category=CAT_COST_OF_SERVICE
    ),
    SeedAccount(
        "5130", "Trash hauling & disposal", "expense", None, True, category=CAT_COST_OF_SERVICE
    ),
    SeedAccount("5140", "Purchased gas", "expense", None, True, category=CAT_COST_OF_SERVICE),
    SeedAccount("5145", "Broadband transport", "expense", None, True, category=CAT_COST_OF_SERVICE),
    SeedAccount(
        "5200", "Operations & maintenance", "expense", None, True, category=CAT_COST_OF_SERVICE
    ),
    SeedAccount("5300", "Infrastructure", "expense", None, True, category=CAT_COST_OF_SERVICE),
)

#: Service code → its cost account code. **SIX SERVICES, NOT TEN, AND THAT IS
#: THE PROPOSAL AS WRITTEN.** `SERVICE_REVENUE_ACCOUNTS` maps all ten catalog
#: services because BR-BIL-010 refuses a whole bill over a missing revenue
#: account; BR-LED-037's proposal names cost mirrors for six. `solar`,
#: `battery`, `storm_water` and `thermal_heat` therefore get NO cost account,
#: and a capture against one of them has no DEFAULT to offer — the clerk picks
#: an account, which is lawful (BR-LED-038 makes the seeded pointer a default a
#: tenant may override). **Inventing 5150/5160/5170 to round the ladder out
#: would be minting an unsigned account nobody proposed**, so the gap is
#: REPORTED by `cost_account_code_for_service` returning None rather than
#: filled. Same posture as the 2200 series: the account arrives when a human
#: asks for it.
SERVICE_COST_ACCOUNTS: dict[str, str] = {
    "electric": "5100",
    "water": "5110",
    "sewer": "5120",
    "trash": "5130",
    "gas": "5140",
    "broadband": "5145",
}

#: Cost codes CONDITIONAL on a tenant selling the service (BR-LED-038, the
#: BR-BIL-067 shape extended to the mirror ladder). Derived from the map so a
#: service added there cannot forget to become conditional here.
SERVICE_COST_CODES: frozenset[str] = frozenset(SERVICE_COST_ACCOUNTS.values())

#: ⚠ **THE FOURTEEN WIDENED COST ACCOUNTS (CR-060 C15 · task T5), EVERY ROW
#: `signed=False`.**
#:
#: They are in their OWN tuple and not appended to `COST_OF_SERVICE_CHART` for
#: exactly the reason that tuple is separate from `SEED_CHART`: **one tuple must
#: not come to mean two things.** `COST_OF_SERVICE_CHART` is *"the eight codes
#: and names the Product Owner finance re-signed on 2026-08-18"* and its test
#: asserts that set exactly; appending here would quietly enlarge what that
#: signature is read to cover.
#:
#: **THE ROUTE IS THE ONE 4160/4170, 4180 AND 4300 EACH TOOK.** B5 line 74 is
#: ❄️ FROZEN and is NOT edited inline, so a row nobody has signed seeds
#: `signed=False`, lands in `PENDING_FINANCE_RE_SIGN_COST` (derived below from
#: both tuples), and **no surface may present it as finance-signed**
#: (US-LED-017 TC-5). A finance re-sign through HUMAN-GUIDE §6 is what empties
#: it — never an edit here.
#:
#: The ladder mirrors a US utility operating statement so the export lands in
#: recognisable buckets: **52xx** operations & maintenance, **53xx**
#: infrastructure, **54xx** customer accounts, **55xx** administrative &
#: general, **56xx** the utility's own taxes. `5200` and `5300` are already in
#: `COST_OF_SERVICE_CHART` and are NOT repeated.
WIDENED_COST_CHART: tuple[SeedAccount, ...] = tuple(
    SeedAccount(
        spec.account_code, spec.account_name, "expense", None, False, CAT_OPERATING_EXPENSES
    )
    for spec in COST_CATEGORY_SPECS
    if spec.account_code not in {row.code for row in COST_OF_SERVICE_CHART}
)


#: The cost rows EVERY tenant is seeded — 5200 and 5300. Derived, not listed:
#: a code is shared if and only if no service names it, exactly as `SHARED_CHART`
#: is derived for the revenue ladder.
SHARED_COST_CHART: tuple[SeedAccount, ...] = tuple(
    row for row in COST_OF_SERVICE_CHART if row.code not in SERVICE_COST_CODES
)

#: The category a shared cost row is FOR, so nothing has to parse a code. The
#: mapping is stated once here and read by `apps/ledger/cost_capture.py`.
#: ⚠ DERIVED from `COST_CATEGORY_SPECS` since 2026-09-01 (it listed 5200 and
#: 5300 by hand until then). One place declares a category and its account, so a
#: category can never be added to the vocabulary with no account to point at.
COST_CATEGORY_ACCOUNTS: dict[str, str] = {
    spec.code: spec.account_code for spec in COST_CATEGORY_SPECS
}

#: The codes finance has NOT signed in this section — derived from the rows, so
#: it cannot disagree with them, and asserted by
#: `tests/test_us_led_017_cost_chart.py`. It read **ALL EIGHT** from 2026-08-15
#: until the PO's finance re-sign of **2026-08-18**; it is `()` now, which is the
#: goal state. Empty is reached by a re-sign through HUMAN-GUIDE §6 and never by
#: an inline edit here — and a future cost row added without one lands here and
#: is marked on every surface that offers it (US-LED-017 TC-5, which is kept
#: under test on a synthetic unsigned row now that no real one remains).
#: ⚠ **AMENDED 2026-09-01 — IT NOW SPANS BOTH COST TUPLES.** It read only
#: `COST_OF_SERVICE_CHART` and was `()` after the 2026-08-18 re-sign. CR-060's
#: T5 adds fourteen accounts nobody has signed, and the whole purpose of this
#: tuple is *"codes no surface may present as finance-signed"* — so it has to
#: carry them, or the fourteen would be served as signed on the day they
#: arrived, which is precisely the defect US-LED-017 TC-5 exists to catch.
#: **The eight cost-of-service codes stay OUT of it because they are signed**,
#: and `tests/test_us_led_017_cost_chart.py` still asserts that, rewritten
#: rather than deleted so the record of the 2026-08-18 re-sign survives.
PENDING_FINANCE_RE_SIGN_COST: tuple[str, ...] = tuple(
    row.code for row in COST_OF_SERVICE_CHART + WIDENED_COST_CHART if not row.signed
)

# ═══════════════════════════════════════════════════════════════════════════
# THE UTILITY'S OWN BOOKS — CR-061 STATEMENT (1), BUILT 2026-09-02
# ═══════════════════════════════════════════════════════════════════════════
#: **PO ruling 2026-09-01, verbatim, and it is a FIELD FINDING rather than a
#: preference:** *"if you need differnt number assign it - im okay with it;
#: actually you need more GL code s and categories, I tried to assigned using
#: existing code, they are not sufficiencnt"*. The PO sat down to assign GL
#: codes with the chart this product ships and RAN OUT. Statement (2) of that
#: ruling — the discount — landed 2026-09-01. This tuple is statement (1), and
#: the PO closed it on 2026-09-02 with *"complete 61 based on actual code"*.
#:
#: ─────────────────────────────────────────────────────────────────────────
#: WHAT THESE ACCOUNTS ARE FOR, AND THE ONE SENTENCE THAT DECIDES THE SET
#: ─────────────────────────────────────────────────────────────────────────
#: **This product posts meter-to-cash. A utility's books are wider than that.**
#: Every row below is somewhere a utility records a fact THIS PRODUCT NEVER
#: POSTS — plant, construction, depreciation, payables, debt, grants, transfers,
#: net position, petty cash, investments. They are reachable: `S57` serves
#: `POST /ledger/journal-entries/drafts` and `/post`, so a clerk writes a
#: balanced manual entry against any of them, which is exactly what the PO was
#: doing when they ran out of codes.
#:
#: ⚠ **AND THE SET IS DECIDED BY ONE RULE, WHICH IS WHY IT IS 67 ROWS AND NOT
#: THE REFERENCE'S 111.** *A reference row is seeded when it names a place the
#: product does not already have. It is NOT seeded when the product already
#: posts that fact somewhere.* The second half is the load-bearing half and it
#: is hard-won law 2 applied to DATA: `1220 Customer AR – Electric` would look
#: like the account electric receivables land in, and they would not — every
#: receivable in this product posts through the ONE `accounts_receivable`
#: designation, which the database makes unique per tenant. A chart row that
#: will always read zero while a human reconciles against it is worse than an
#: absent one. The eleven reference rows refused by that rule are listed in
#: `UTILITY_BOOKS_NOT_SEEDED` below, each with its reason, so a later reader
#: finds a ruling rather than a gap.
#:
#: ─────────────────────────────────────────────────────────────────────────
#: THE NUMBERS ARE THE PO's OWN, AND THE FOUR THAT ARE NOT SAY SO
#: ─────────────────────────────────────────────────────────────────────────
#: Every code below is the code the PO's 111-row reference chart gives that
#: account (`CR-061` §5), which is the precedent `CR-066` set for 4600/4610/4630
#: and the whole 4700-4730 block: adopting more of that chart later then finds
#: these rows already in the right place and renumbers nothing. **Four diverge,
#: and each diverges because the reference's number is already taken by a
#: FINANCE-SIGNED row of B5 line 74 ❄️, which no lane may move:**
#:
#:   * `1060 Restricted cash` — the reference says `1010`, which is
#:     `1010 Undeposited funds` (signed, designation `undeposited_funds`).
#:   * `3040 Capital grants & contributions` — the reference says `3000`, which
#:     is `3000 Opening balance clearing` (signed, designation
#:     `opening_clearing`). Its three siblings keep 3010/3020/3030.
#:   * `5260 Inventory consumption` — the reference says `6100`, which it ALSO
#:     gives to *Electricity Purchased* (row 54 and row 77 collide in the PO's
#:     own chart) and which this product spends at `5100 Purchased power`.
#:   * `5240/5250/5430/5550/5560` — the reference files operating expenses in
#:     `6xxx`; this product's expense ladder is `5xxx` (CR-060 T5's fourteen
#:     categories) and `6800/6900/6950` are signed rows in the middle of the
#:     reference's `6xxx` block. Putting chemicals at `6200` would interleave
#:     two ladders.
#:
#: ─────────────────────────────────────────────────────────────────────────
#: FOUR JUDGMENTS RECORDED HERE RATHER THAN PUT BACK TO THE PO (law 13)
#: ─────────────────────────────────────────────────────────────────────────
#: **1 · ACCUMULATED DEPRECIATION IS TYPED `asset`, NOT A SEVENTH TYPE.** The
#: reference marks `1700`-`1730` Normal Balance = **Credit**, which makes them
#: contra-assets, and `CR-061` minted `contra_revenue` for exactly that shape on
#: the revenue side. It is NOT repeated here, for a measured reason:
#: `reporting.revenue_by_service` is *"THE ONLY PLACE IN THE PRODUCT THAT
#: FILTERS ON AN ACCOUNT TYPE RATHER THAN PRINTING ONE"* (its own comment,
#: measured across `apps/` for CR-061), and it filters on REVENUE. A discount
#: typed wrongly put **10.00 of revenue the utility never earned** into three
#: surfaces; an accumulated-depreciation row typed `asset` changes no figure
#: anywhere — the trial balance takes each row's side from its own **net
#: debit**, so a credit balance foots in the credit column with no help from the
#: type. Accumulated depreciation is also presented WITHIN the asset section of
#: a balance sheet, as a deduction, so `asset` is not even a mis-statement. **If
#: a utility wants the Type column to read "Contra-asset", that is a new ruling
#: and a seventh type; it is not this one.**
#:
#: **2 · NO `normal_balance` COLUMN.** `CR-061` §5 finding 3 names it as a
#: column the product does not store. It stays unstored: for every type in
#: `LEDGER_ACCOUNT_TYPES` the normal side is decided by the type
#: (asset/expense/contra_revenue debit, liability/equity/revenue credit), so a
#: column would be a second source of truth for a fact the type already states —
#: and the trial balance never asks either of them, it asks the net debit. The
#: only rows where the derivation would be wrong are the four accumulated-
#: depreciation accounts, and judgment 1 covers those.
#:
#: **3 · `1290 Allowance for doubtful accounts` IS DELIBERATELY NOT SEEDED**,
#: and it is the one reference row left to a named owner rather than refused.
#: `CR-060` **T15** is an open finance decision whose own words are *"only if
#: IFRS or Ind AS markets are in scope"*, and today write-off is DIRECT —
#: `DR 6900 / CR 1200`. Seeding an allowance account offers a utility an
#: accounting policy this product does not implement, on a signed write-off
#: path. T15 owns it.
#:
#: ⚠ **RULED AND SPENT — PO 2026-09-03, `CR-060` T15.** The judgment above is
#: kept because it is the record of WHY the row was withheld for two days, and
#: it is no longer the behaviour. The PO overrode a recommendation to defer
#: (*"Why I recommended deferring it. Three reasons: let's do this"*), so the
#: policy IS implemented — `apps/ledger/allowance.py` — and `1290` is minted by
#: `services.ensure_allowance_account` from `ALLOWANCE_CHART` below.
#: **IT IS STILL NOT IN THE PROVISIONING SEED, and that is this clause
#: surviving rather than being reversed:** the account appears on a tenant's
#: chart when that tenant SWITCHES THE POLICY ON, never before, so a utility
#: that never books an allowance is still not offered one. The chart stays at
#: 125 accounts for everybody else.
#:
#: **4 · SEEDING A PAYABLE ACCOUNT IS NOT ACCOUNTS PAYABLE, AND SEEDING A
#: TRANSFER ACCOUNT IS NOT FUND ACCOUNTING.** Two recorded rulings look like
#: they refuse rows 43-48 and 104-111, and neither does. `OQ-200` (PO
#: 2026-08-16, *"(b) for R2, (a) once supplier payments exist"*) rules that
#: capturing a supplier invoice **posts nothing**, because `CR accounts payable`
#: would leave **$37,200.00** of settled-elsewhere liability standing after
#: twelve months at $3,100.00 of purchased water. **That objection is about
#: POSTING and it is untouched here:** `post_capture_to_journal` is still a
#: no-op, `CR-060` T6 settles `DR cost / CR cash`, and nothing in this product
#: credits `2000`. An account nothing posts to accrues no false balance — it
#: reads $0.00 until a human writes a manual entry, which is the whole point.
#: `CR-060` T1b's fund ruling is the same shape: it ruled on a fund TAG, a
#: DIMENSION on a journal line, and a chart heading is not a dimension. **The
#: sentence in `CR-060` that IS superseded is the derived one — *"no `2500
#: Accounts payable` is proposed in the chart"* — and it is superseded by the
#: PO's own reference chart, which contains the block, plus their instruction to
#: complete this CR.** Recorded in `12-governance/02-decision-log.md`, dated.
#:
#: ─────────────────────────────────────────────────────────────────────────
#: EVERY ROW IS `signed=False`. THE PO APPROVED THE CHART, NOT THE SIGNATURE
#: ─────────────────────────────────────────────────────────────────────────
#: The PO ruled that these codes should EXIST. That is not a finance signature,
#: no dollar figure is attached to any row, and **no B4/B5 figure moved** —
#: `G61` reads 130 frozen money figures unchanged before and after. All 67 land
#: in `PENDING_FINANCE_RE_SIGN_BOOKS`, every surface that offers one says
#: `finance_signed: false`, and the review-ledger row states in plain English
#: what a finance reviewer is being asked to check. Same posture as 4160/4170
#: (2026-08-11), 4180 (2026-08-17) and CR-066's nine (2026-09-02).
UTILITY_BOOKS_CHART: tuple[SeedAccount, ...] = (
    # ── Cash & investments (reference rows 2-8) ─────────────────────────────
    SeedAccount("1020", "Petty cash", "asset", None, False, CAT_CASH),
    SeedAccount("1030", "Bank clearing", "asset", None, False, CAT_CASH),
    SeedAccount("1040", "ACH clearing", "asset", None, False, CAT_CASH),
    SeedAccount("1050", "Card clearing", "asset", None, False, CAT_CASH),
    SeedAccount("1060", "Restricted cash", "asset", None, False, CAT_CASH),
    SeedAccount("1100", "Investments", "asset", None, False, CAT_CASH),
    SeedAccount("1110", "Interest receivable", "asset", None, False, CAT_CASH),
    # ── Receivables (reference row 14) ──────────────────────────────────────
    SeedAccount("1250", "Non-customer receivables", "asset", None, False, CAT_RECEIVABLE),
    # ── Inventory (reference rows 49-53) ────────────────────────────────────
    SeedAccount("1300", "Meter inventory", "asset", None, False, CAT_INVENTORY),
    SeedAccount("1310", "Pipe & fittings inventory", "asset", None, False, CAT_INVENTORY),
    SeedAccount("1320", "Electrical equipment inventory", "asset", None, False, CAT_INVENTORY),
    SeedAccount("1330", "Chemicals inventory", "asset", None, False, CAT_INVENTORY),
    SeedAccount("1340", "General materials inventory", "asset", None, False, CAT_INVENTORY),
    # ── Fixed assets / utility plant (reference rows 55-64) ─────────────────
    SeedAccount("1500", "Land", "asset", None, False, CAT_FIXED_ASSETS),
    SeedAccount("1510", "Water source & supply", "asset", None, False, CAT_FIXED_ASSETS),
    SeedAccount("1520", "Water treatment plant", "asset", None, False, CAT_FIXED_ASSETS),
    SeedAccount("1530", "Water distribution system", "asset", None, False, CAT_FIXED_ASSETS),
    SeedAccount("1540", "Sewer collection system", "asset", None, False, CAT_FIXED_ASSETS),
    SeedAccount("1550", "Wastewater treatment plant", "asset", None, False, CAT_FIXED_ASSETS),
    SeedAccount("1560", "Electric generation plant", "asset", None, False, CAT_FIXED_ASSETS),
    SeedAccount("1570", "Electric distribution system", "asset", None, False, CAT_FIXED_ASSETS),
    SeedAccount("1580", "Gas distribution system", "asset", None, False, CAT_FIXED_ASSETS),
    SeedAccount("1590", "Meters in service", "asset", None, False, CAT_FIXED_ASSETS),
    # ── Construction in progress (reference rows 65-69) ─────────────────────
    SeedAccount("1600", "Construction in progress", "asset", None, False, CAT_CIP),
    SeedAccount("1610", "Engineering costs (CIP)", "asset", None, False, CAT_CIP),
    SeedAccount("1620", "Capitalised labour (CIP)", "asset", None, False, CAT_CIP),
    SeedAccount("1630", "Capitalised overhead (CIP)", "asset", None, False, CAT_CIP),
    SeedAccount("1640", "Developer-funded CIP", "asset", None, False, CAT_CIP),
    # ── Accumulated depreciation (reference rows 70-73; judgment 1 above) ───
    SeedAccount(
        "1700",
        "Accumulated depreciation — water plant",
        "asset",
        None,
        False,
        CAT_ACCUM_DEPRECIATION,
    ),
    SeedAccount(
        "1710",
        "Accumulated depreciation — sewer plant",
        "asset",
        None,
        False,
        CAT_ACCUM_DEPRECIATION,
    ),
    SeedAccount(
        "1720",
        "Accumulated depreciation — electric plant",
        "asset",
        None,
        False,
        CAT_ACCUM_DEPRECIATION,
    ),
    SeedAccount(
        "1730",
        "Accumulated depreciation — meters",
        "asset",
        None,
        False,
        CAT_ACCUM_DEPRECIATION,
    ),
    # ── Accounts payable (reference rows 43-48; judgment 4 above) ───────────
    SeedAccount("2000", "Vendor accounts payable", "liability", None, False, CAT_PAYABLE),
    SeedAccount("2010", "Contractor accounts payable", "liability", None, False, CAT_PAYABLE),
    SeedAccount("2020", "Retainage payable", "liability", None, False, CAT_PAYABLE),
    SeedAccount("2100", "Accrued expenses", "liability", None, False, CAT_PAYABLE),
    SeedAccount("2110", "Accrued payroll", "liability", None, False, CAT_PAYABLE),
    SeedAccount("2120", "Accrued interest", "liability", None, False, CAT_PAYABLE),
    # ── Debt (reference rows 90-94; 2200-2299 is the tax series, untouched) ─
    SeedAccount("2500", "Revenue bonds payable", "liability", None, False, CAT_DEBT),
    SeedAccount("2510", "Bank loans payable", "liability", None, False, CAT_DEBT),
    SeedAccount("2520", "Current portion of long-term debt", "liability", None, False, CAT_DEBT),
    SeedAccount("2530", "Lease liability", "liability", None, False, CAT_DEBT),
    SeedAccount("2540", "Interest payable", "liability", None, False, CAT_DEBT),
    # ── Grants & contributions (reference rows 96-99) ───────────────────────
    SeedAccount("3010", "Operating grants", "revenue", None, False, CAT_GRANTS),
    SeedAccount("3020", "Developer contributions", "equity", None, False, CAT_GRANTS),
    SeedAccount("3030", "Customer contributions", "equity", None, False, CAT_GRANTS),
    SeedAccount("3040", "Capital grants & contributions", "equity", None, False, CAT_GRANTS),
    # ── Net position (reference rows 108-111) ───────────────────────────────
    SeedAccount(
        "9000", "Net investment in capital assets", "equity", None, False, CAT_NET_POSITION
    ),
    SeedAccount("9010", "Restricted net position", "equity", None, False, CAT_NET_POSITION),
    SeedAccount("9020", "Unrestricted net position", "equity", None, False, CAT_NET_POSITION),
    SeedAccount("9030", "Prior period adjustment", "equity", None, False, CAT_NET_POSITION),
    # ── Revenue adjustments (reference row 36) ──────────────────────────────
    SeedAccount("4740", "Customer refunds", "contra_revenue", None, False, CAT_REVENUE_ADJUSTMENTS),
    # ── Operating expenses the 5xxx ladder has no home for ──────────────────
    SeedAccount(
        "5240", "Chemicals & treatment supplies", "expense", None, False, CAT_OPERATING_EXPENSES
    ),
    SeedAccount(
        "5250", "Meter maintenance & testing", "expense", None, False, CAT_OPERATING_EXPENSES
    ),
    SeedAccount("5260", "Inventory consumption", "expense", None, False, CAT_OPERATING_EXPENSES),
    SeedAccount("5430", "Payment processing fees", "expense", None, False, CAT_OPERATING_EXPENSES),
    SeedAccount(
        "5550", "IT & software subscriptions", "expense", None, False, CAT_OPERATING_EXPENSES
    ),
    SeedAccount("5560", "Cloud & hosting services", "expense", None, False, CAT_OPERATING_EXPENSES),
    # ── Non-operating (reference rows 95, 100-103) ──────────────────────────
    SeedAccount("7000", "Interest expense", "expense", None, False, CAT_NON_OPERATING),
    SeedAccount("7100", "Interest income", "revenue", None, False, CAT_NON_OPERATING),
    SeedAccount("7110", "Investment income", "revenue", None, False, CAT_NON_OPERATING),
    SeedAccount("7120", "Gain on asset disposal", "revenue", None, False, CAT_NON_OPERATING),
    SeedAccount("7130", "Loss on asset disposal", "expense", None, False, CAT_NON_OPERATING),
    # ── Transfers (reference rows 104-107; judgment 4 above) ────────────────
    SeedAccount("8000", "Transfer in — general fund", "equity", None, False, CAT_TRANSFERS),
    SeedAccount("8010", "Transfer out — utility", "equity", None, False, CAT_TRANSFERS),
    SeedAccount(
        "8020", "Interfund transfer — water to sewer", "equity", None, False, CAT_TRANSFERS
    ),
    SeedAccount(
        "8030", "Transfer out — utility to general fund", "equity", None, False, CAT_TRANSFERS
    ),
)

#: The reference rows this lane deliberately did NOT seed, and why — stated as
#: DATA so `CR-061`'s reconciliation can be recomputed from the code rather than
#: read off a change-request table that will rot (the PO's own instruction on
#: 2026-09-02 was *"complete 61 based on actual code"*).
#:
#: Keyed by the reference chart's own row number in `CR-061` §5.
UTILITY_BOOKS_NOT_SEEDED: dict[int, str] = {
    9: "1200 Customer AR – Water: every receivable posts through the ONE "
    "`accounts_receivable` designation, which the database makes unique per tenant. A "
    "per-service AR row would always read zero while a human reconciled against it.",
    10: "1210 Customer AR – Sewer: same — one AR account per tenant — and 1210 is "
    "already `1210 Unbilled AR (accruals)` in this product.",
    11: "1220 Customer AR – Electric: same — every receivable posts through the one "
    "`accounts_receivable` designation.",
    12: "1230 Customer AR – Gas: same — every receivable posts through the one "
    "`accounts_receivable` designation.",
    13: "1240 Customer AR – Submeter: same — and every account in this product is a "
    "submetered one, so it names no distinct fact.",
    15: "1260 Unbilled Revenue: the product already has it, at 1210 Unbilled AR "
    "(accruals), carrying the `unbilled_ar` designation.",
    16: "1290 Allowance for doubtful accounts: RULED AND BUILT 2026-09-03 (CR-060 T15). "
    "It is NOT in the provisioning seed and that is deliberate — apps/ledger/allowance.py "
    "mints it through services.ensure_allowance_account when a tenant switches the policy "
    "on, so a utility that never books an allowance is never offered one.",
    19: "4020 Water Service Charge: 4630 Field-service & meter fees is where a service "
    "call is charged (CR-066, PO-approved mapping).",
    21: "4110 Sewer Base Charge: B5 line 74 ❄️ splits base from usage for Electric and "
    "Water only. Giving sewer a base account means re-pointing a signed service map, "
    "which is a finance re-sign via HUMAN-GUIDE §6 and never a seed edit.",
    24: "4310 Electric Demand Revenue: demand charges post to 4100 Electric usage today; "
    "splitting them is a rating-engine change, not a chart row.",
    27: "4500 Submeter Consumption: this product IS submetering — every service revenue "
    "account already is this row.",
    30: "4620 Late Payment Fee: the product has it at 4200 Late-fee revenue (signed).",
    37: "4750 Bad Debt Write-off: the product has it at 6900 Bad debt, carrying the "
    "`write_off` designation. The reference files it as a revenue adjustment and we "
    "file it as an expense; re-typing a signed row is a finance re-sign.",
    39: "2310 Commercial Deposit: every deposit posts to the ONE `deposit_liability` "
    "designation. See row 9.",
    40: "2320 Developer Deposit: same — every deposit posts to the one "
    "`deposit_liability` designation, so a second row would always read zero.",
    41: "2330 Meter Deposit: same — every deposit posts to the one `deposit_liability` "
    "designation, so a second row would always read zero.",
    42: "2340 Advance Customer Payment: the product has it at 2400 Customer credit "
    "balances, carrying the `customer_credit_balance` designation.",
    # ⚠ ROW 54 IS NOT LISTED HERE AND THAT IS DELIBERATE: it IS seeded, at
    # 5260 Inventory consumption. It only LOOKS like a gap because its number
    # moved — the reference gives 6100 to TWO different rows (54 Inventory
    # Consumption and 77 Electricity Purchased) and this product already spends
    # 6100's other meaning at 5100. The divergence is recorded in this module's
    # own list of the four renumbered rows; a tuple named NOT_SEEDED must
    # contain only rows that are not seeded, or the next reader counts it and
    # gets the wrong answer.
    76: "6020 Overtime: 5500 Payroll & benefits (CR-060 T5) is where wages are recorded.",
    81: "6210 Fuel: 5540 Vehicles & fuel (CR-060 T5).",
    82: "6300 Repairs & Maintenance: 5200 Operations & maintenance and its three splits "
    "5210/5220/5230 (CR-060 T5).",
    84: "6320 Vehicle Maintenance: 5540 Vehicles & fuel (CR-060 T5).",
    85: "6400 Billing Operations: 5400 Customer accounts — billing & collection.",
    87: "6420 Bank Fees: the product has it at 6800 Bank fees, carrying the `bank_fees` "
    "designation.",
}

#: The codes finance has NOT signed in this section — DERIVED from the rows, the
#: same construction as the other two registers, so the tuple and the rows can
#: never disagree. It is every row of `UTILITY_BOOKS_CHART` today and that is
#: correct: the PO ruled the codes into existence and a finance signature is a
#: separate act through HUMAN-GUIDE §6.
PENDING_FINANCE_RE_SIGN_BOOKS: tuple[str, ...] = tuple(
    row.code for row in UTILITY_BOOKS_CHART if not row.signed
)

#: Where THAT signature has to come from — the twin of
#: `PENDING_FINANCE_RE_SIGN_SOURCE` and `COST_SECTION_RE_SIGN_SOURCE`.
UTILITY_BOOKS_RE_SIGN_SOURCE = (
    "B5 line 74 (04-docs/02-decisions/05-golden-tests.md) — ❄️ FROZEN, finance-signed "
    "2026-08-08 — is a meter-to-cash chart and names none of these accounts. The 67 rows "
    "were ruled into existence by the Product Owner on 2026-09-01 ('actually you need more "
    "GL code s and categories, I tried to assigned using existing code, they are not "
    "sufficiencnt') and completed on 2026-09-02 ('complete 61 based on actual code'), with "
    "the numbers taken from the 111-row reference chart the PO supplied. THAT IS A RULING "
    "ON THE CODES AND NAMES AND NOT A FINANCE SIGNATURE: no amount, rate or default is "
    "attached to any of them, no B4/B5 figure moved, and none may be presented as "
    "finance-signed (US-LED-017 TC-5) until a re-sign comes through HUMAN-GUIDE §6 as a "
    "dated addendum beside the frozen chart — the route 4160/4170, 4180 and the eight "
    "cost-of-service rows all took."
)


# ═══════════════════════════════════════════════════════════════════════════
# PERIOD MATCHING — where the two new month-end postings land (CR-060 T7b/T7f)
# ═══════════════════════════════════════════════════════════════════════════
#: **ONE NEW ACCOUNT AND TWO POINTERS AT ACCOUNTS THAT ALREADY EXIST.**
#:
#: CR-060 C17 and C20 each need a counter-account the product could not name
#: before today, and the two cases are DIFFERENT and are treated differently
#: rather than uniformly:
#:
#:   * **C17's credit and C20's credit already exist in the chart.** `2100
#:     Accrued expenses` and `1730 Accumulated depreciation — meters` are
#:     `UTILITY_BOOKS_CHART` rows, ruled into existence by the PO on
#:     2026-09-01/02 from their own 111-row reference. Minting a SECOND accrued-
#:     expenses account beside `2100` would be the *"a live account nothing
#:     consumes"* smell CR-060 §4 opens with, one row later. So nothing is
#:     minted for them: `services.ensure_period_matching_accounts` places the
#:     DESIGNATION on the row the tenant already has.
#:   * **C20's debit does not exist anywhere.** The reference chart carries four
#:     accumulated-depreciation accounts (rows 70-73) and NO depreciation
#:     expense to charge against them, which is half of a double entry. `5700`
#:     is that half, minted here, `signed=False`, and listed below.
#:
#: ⚠ **`preferred_code` IS A SEED DEFAULT AND NEVER A POSTING LOOKUP.** This
#: file's own law is that *"any Python that says `code == '1200'` is a latent
#: misposting"*, and nothing here breaks it: the posting services resolve their
#: accounts through `selectors.gl_account_for_designation` and never see a
#: number. A code appears here for exactly one purpose — deciding WHERE a
#: designation goes on a chart nobody has customised yet — which is the same
#: job every `SeedAccount.code` above already does.
PERIOD_MATCHING_CHART: tuple[SeedAccount, ...] = (
    SeedAccount(
        "5700",
        "Depreciation expense",
        "expense",
        DEPRECIATION_EXPENSE,
        False,
        CAT_OPERATING_EXPENSES,
    ),
)

#: Which existing account each of the OTHER two designations is placed on when a
#: tenant has not already claimed it. **The name is checked, not just the code**
#: — see `services.ensure_period_matching_accounts`, which refuses to designate
#: a row a tenant has renumbered into something else.
PERIOD_MATCHING_PLACEMENTS: tuple[tuple[str, str], ...] = (
    (ACCRUED_EXPENSES, "2100"),
    (ACCUMULATED_DEPRECIATION, "1730"),
)

#: DERIVED, like its three siblings, so the tuple and the rows cannot disagree.
PENDING_FINANCE_RE_SIGN_MATCHING: tuple[str, ...] = tuple(
    row.code for row in PERIOD_MATCHING_CHART if not row.signed
)

# ── CR-060 T15 · the allowance for doubtful accounts (PO 2026-09-03) ────────
#: ONE row, and it is deliberately NOT in `services._wanted_rows`.
#:
#: **WHY IT IS NOT SEEDED WITH THE OTHER 125.** Judgment 3 above refused to
#: offer every utility an accounting policy the product did not implement. The
#: product implements it now, and the narrower half of that refusal still
#: stands: **most utilities under 3,000 connections are not audited and never
#: book an allowance** — the PO was told exactly that and chose to build it
#: anyway, for the ones that do. So the row lands when a tenant switches the
#: policy on (`services.ensure_allowance_account`, hard-won law 4's top-up
#: shape), and a tenant who never does keeps a chart of 125.
#:
#: **`asset`, NOT a sixth type.** It is a CONTRA-asset — it carries a credit
#: balance and nets against `1200` — and this product stores no
#: `normal_balance` column (judgment 2 above). `1730 Accumulated depreciation —
#: meters` is the precedent and it is typed `asset` for the same reason.
ALLOWANCE_CHART: tuple[SeedAccount, ...] = (
    SeedAccount(
        "1290",
        "Allowance for doubtful accounts",
        "asset",
        ALLOWANCE_DOUBTFUL_ACCOUNTS,
        False,
        CAT_RECEIVABLE,
    ),
)

#: DERIVED, like its siblings.
PENDING_FINANCE_RE_SIGN_ALLOWANCE: tuple[str, ...] = tuple(
    row.code for row in ALLOWANCE_CHART if not row.signed
)

#: Where THAT signature has to come from.
ALLOWANCE_RE_SIGN_SOURCE = (
    "B5 line 74 (04-docs/02-decisions/05-golden-tests.md) — the finance-signed chart of "
    "2026-08-08 — has no allowance account, and the PO's 111-row reference chart carries "
    "1290 at row 16 as a CODE they supplied rather than a figure finance signed. The PO "
    "ruled the POLICY into existence on 2026-09-03 (CR-060 T15) and that is not a finance "
    "signature on a chart row, which is exactly the reading UTILITY_BOOKS_CHART's 67 rows "
    "already carry. So 1290 is signed=False until a re-sign comes through HUMAN-GUIDE §6 "
    "as a dated addendum beside the frozen chart. NO PERCENTAGE IS ATTACHED TO IT: the "
    "four rates are TENANT SETTINGS (1%, 5%, 20%, 50% as defaults) because a rate is a "
    "judgment about that utility's own customers, and hardcoding one would be this "
    "product asserting something about somebody else's book of debts."
)

#: Where THAT signature has to come from.
PERIOD_MATCHING_RE_SIGN_SOURCE = (
    "B5 line 74 (04-docs/02-decisions/05-golden-tests.md) — the finance-signed chart of "
    "2026-08-08 — has no depreciation account of any kind, and neither does the 111-row "
    "reference chart the PO supplied on 2026-09-01: that one carries four accumulated-"
    "depreciation accounts (rows 70-73) and nothing to charge against them. 5700 is "
    "therefore a code NOBODY has ruled on, minted by the CR-060 T7f lane because C20 "
    "('post depreciation') cannot be built without one, and it carries signed=False until "
    "a re-sign comes through HUMAN-GUIDE §6 as a dated addendum beside the frozen chart. "
    "NO AMOUNT IS ATTACHED TO IT: the figure a depreciation entry carries comes from the "
    "asset's own purchase cost, method and expected life, which the assets module has "
    "computed since CR-028 and which this change does not touch."
)

# ── CR-136-BRC07 §3.3 · the drawer difference (PO 2026-09-23) ──────────────
#: The ONE seed row `cash_over_short` starts on, DERIVED from `SEED_CHART` so
#: the two cannot disagree — unlike `ALLOWANCE_CHART` and
#: `PERIOD_MATCHING_CHART`, this row IS in `services._wanted_rows`, because
#: every utility that takes cash at a counter has drawers and every one of them
#: will be out by something eventually. A tenant that takes no cash simply
#: never posts to it, which costs one unused line on a 128-row chart.
#:
#: **IT EXISTS AS A TUPLE ANYWAY, FOR THE TENANTS THAT ALREADY EXIST.** A seed
#: edit reaches no host that already has a chart (hard-won law 4), so
#: `services.ensure_cash_over_short_account` tops it up on the day the posting
#: first needs it — the shape `ensure_allowance_account` and
#: `ensure_period_matching_accounts` already take, and the thing that stops
#: `P2.22` refusing a beta tenant's very first counted close.
CASH_OVER_SHORT_CHART: tuple[SeedAccount, ...] = tuple(
    row for row in SEED_CHART if row.designation == CASH_OVER_SHORT
)


#: Where the signature has to come from, named once so it is greppable from the
#: code as well as from the governance files — the twin of
#: `PENDING_FINANCE_RE_SIGN_SOURCE`.
COST_SECTION_RE_SIGN_SOURCE = (
    "B5 line 74 (04-docs/02-decisions/05-golden-tests.md) — ❄️ FROZEN, finance-signed "
    "2026-08-08 — carries NO cost-of-service accounts at all. The 5100/5110/5120/5130/5140/"
    "5145/5200/5300 section was BR-LED-037's PROPOSAL (EP-LED-06, US-LED-017, 2026-08-15) "
    "and was FINANCE RE-SIGNED on 2026-08-18 by the Product Owner via HUMAN-GUIDE §6 — a "
    "dated addendum BESIDE the frozen chart, the route the 4160/4170 revenue codes "
    "(BR-BIL-067) and the concession account (BR-LED-022) took. The eight CODES AND NAMES "
    "are what was ratified; no amount, rate or default is. Any cost account added from here "
    "without its own re-sign seeds marked-unsigned and NO surface may present it as "
    "finance-signed (US-LED-017 TC-5), and this sentence is the reason it carries."
)


def cost_account_code_for_service(service_code: str) -> str | None:
    """The cost account a service's purchases START pointing at, or None.

    None is a real answer and not a failure: four catalog services carry no
    proposed cost mirror (see `SERVICE_COST_ACCOUNTS`), and the caller reports
    the absence rather than inventing a code.

    **This is a DEFAULT, exactly as `SERVICE_REVENUE_ACCOUNTS` is** (BR-LED-038,
    from BR-BIL-067 verbatim: *"you create an account, but allow tenant user to
    override it"*). It says where a service's purchases START. A tenant that
    points purchased water at its own `5115 Raw water purchases` keeps that
    pointer through every re-seed.
    """
    return SERVICE_COST_ACCOUNTS.get(service_code)


def cost_rows_for_service(service_code: str) -> tuple[SeedAccount, ...]:
    """The cost seed rows enabling this service requires — () for a service the
    proposal names no mirror for.

    The twin of `seed_rows_for_service`, and it exists for the same reason: one
    place answers *"which accounts does enabling Gas require"*, so the
    provisioning path and the S8 toggle path cannot drift apart on it.
    """
    code = SERVICE_COST_ACCOUNTS.get(service_code)
    if code is None:
        return ()
    return tuple(row for row in COST_OF_SERVICE_CHART if row.code == code)


def is_cost_of_service_code(code: str) -> bool:
    """Is this one of the eight SEEDED cost-of-service codes?

    ⚠ **AMENDED 2026-08-18 — IT USED TO SAY "PROPOSED, UNSIGNED", AND THAT WAS
    A DEFECT WAITING TO HAPPEN.** Membership of this section and absence of a
    signature are two different questions, and they stopped having the same
    answer the moment the PO finance re-signed all eight rows on 2026-08-18.
    A caller that wants the SIGNATURE must read `PENDING_FINANCE_RE_SIGN_COST`
    (derived from the rows themselves); this function answers only *"is this
    code one the product seeded"*. `apps/ledger/services._chart_row` was reading
    it for the signature and served eight ratified rows as `finance_signed:
    false` until this was fixed.

    It answers about the SEEDED codes only — a tenant's own `5115 Raw water
    purchases` is theirs and was never marked, because nobody proposed it on
    finance's behalf.
    """
    return str(code) in {row.code for row in COST_OF_SERVICE_CHART}


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-LED-005@663369d (sources this file transcribes, in order: 04-docs/02-decisions/05-golden-tests.md §"Seed chart of accounts" line 74 (❄️ finance-signed 2026-08-08) · 12-governance/02-decision-log.md rows "OQ-106 IS CLOSED", "OQ-110 CLOSED" and "STORM WATER AND THERMAL HEAT GET REVENUE ACCOUNTS" (PO 2026-08-11) · 12-governance/01-open-questions.md OQ-106/OQ-110/OQ-115 closed rows · 04-docs/05-modules/07-billing/02-business-rules.md BR-BIL-010 · 04-docs/05-modules/09-ledger/06-epics/EP-LED-02-chart-mapping.md §Scope as superseded 2026-08-11)
# generated: 2026-08-11 by Eng-Lead (W5 ledger GL-designation lane) · AMENDED 2026-08-11 by Eng-Lead (OQ-115 lane: 4160/4170 created marked unsigned · the service map is a tenant-overridable default · per-service revenue accounts seeded only for services the tenant sells) · AMENDED 2026-08-11 by Eng-Lead (OQ-116 tax-authority GL lane — BR-BIL-069: `TAX_PAYABLE_SERIES`/`is_tax_payable_code`; the 2200 series stays seeded to NOBODY, per B5 line 74) · AMENDED 2026-08-15 by the AP-capture lane (US-LED-017 / BR-LED-037/038: the cost-of-service section 5100·5110·5120·5130·5140·5145·5200·5300 in its OWN tuple, every row `signed=False`, seeded per service sold; the liability side deliberately absent under OQ-200) · AMENDED 2026-08-18 by the CR-008 ledger lane (CR-010 B-8, PO 2026-08-17 "8 - A": 4180 Budget billing variance seeds carrying the `budget_variance` designation, `signed=False` per the 4160/4170 precedent; PENDING_FINANCE_RESIGN empties, PENDING_FINANCE_RE_SIGN = ("4180",)) · AMENDED 2026-08-18 by the finance re-sign lane (PO re-signed nine rows in the working chat session — 4180 plus all eight of COST_OF_SERVICE_CHART — shown their codes and names in plain English with NO dollar figure attached; both pending tuples are now `()`, every row carries `signed=True`, B4/B5 were NOT edited and stay ❄️ FROZEN, and the addendum recording exactly what was shown is in this module's docstring)
# checklist: A✔ B✔ C✔ D=deferred(no-API-half) E=deferred(no-frontend-half — the GL mapping page is a Settings story, another lane) F✔ G✔ H=deferred(PO 2026-08-09)
# gates: see 06-backend/tests/test_us_led_005_gl_designations.py and the migrations' trailers
# exceptions: account `type` is DERIVED from the number range, not transcribed —
#         B5 signs codes and names only; LE-1's trial balance anchors the one
#         value the ladder would get wrong (3000 = equity). REPORTED, judgment
#         call 1 in the docstring · 4160 Storm water and 4170 Thermal/Heat were
#         NOT finance-signed when written: the PO ruled the accounts into
#         existence (OQ-115, 2026-08-11) and the two codes are this lane's
#         reading of the chart's own 41xx ladder. They were finance re-signed by
#         dated addendum the same day and carry `signed=True` — judgment call 2
#         (this clause said "are NOT finance-signed" until 2026-08-18) · the 2200-series tax payable line of
#         the signed chart is NOT seeded: tenant authorities mint their own
#         (BR-TEN-037), so seeding one would invent an authority ·
#         ⚠ A STALE CLAIM IN THIS FILE'S OWN DOCSTRING WAS CORRECTED 2026-08-15:
#         it stated in bold that 4160/4170 carry `signed=False` and are listed
#         in PENDING_FINANCE_RE_SIGN, and neither had been true since finance
#         re-signed them on 2026-08-11. Hard-won law 1, inside the file that
#         exists to keep signatures honest — found and corrected by the
#         AP-capture lane, REPORTED rather than quietly patched ·
#         **THE WHOLE COST-OF-SERVICE SECTION WAS UNSIGNED FROM 2026-08-15 TO
#         2026-08-18, AND IS NOW FINANCE RE-SIGNED** — all eight rows of
#         `COST_OF_SERVICE_CHART` carried `signed=False` and were listed in
#         `PENDING_FINANCE_RE_SIGN_COST`; the PO re-signed the eight codes and
#         names on 2026-08-18 (no figure attached to any of them) and that tuple
#         is `()`. They are still kept OUT of `SEED_CHART`, because the two
#         tuples answer two different questions and the day one of them holds an
#         unsigned row again is the day that separation earns its keep
#         (US-LED-017 TC-5, now driven from a synthetic unsigned row). B5 line 74
#         is ❄️ FROZEN and was NOT edited, then or at the re-sign; the route is
#         HUMAN-GUIDE §6 and is named in `COST_SECTION_RE_SIGN_SOURCE` ·
#         FOUR CATALOG SERVICES GET NO COST ACCOUNT — solar, battery,
#         storm_water and thermal_heat are absent from `SERVICE_COST_ACCOUNTS`
#         because BR-LED-037's proposal names six commodity mirrors and not ten.
#         `cost_account_code_for_service` returns None for them and the capture
#         offers no default; inventing 5150/5160/5170 would be minting an
#         unsigned account nobody proposed. REPORTED · NO LIABILITY ACCOUNT is
#         proposed: it is needed only under OQ-200 reading (a), which is OPEN
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
