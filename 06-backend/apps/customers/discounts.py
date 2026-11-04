# ── Trace ──────────────────────────────────────────────
# Story:    US-CUS-004 / US-CUS-007 (EP-CUS-02 S19 Move-In — step 4's
#           eligibility panel and its deposit carry-forward)
#           Screens: S19 step 4
# Change:   CR-030 W5 tasks 5.4 (eligibility panel + `account_discounts`) and
#           5.5 (deposit carry-forward, `strong` match only)
# Rules:    BR-CUS-024 (deposit carry-forward from a prior CLOSED account of
#           the SAME customer; linkage = `customer_accounts`. ⚠ THIS LINE SAID
#           "mechanics still PROPOSED" UNTIL 2026-09-03 — the PO RULED the
#           mechanics on 2026-09-01, CR-059 CS-22: the deposit is OFFERED
#           FORWARD, not refunded and re-collected, moving as a liability
#           transfer between two accounts. The register row is not amended yet
#           and the amendment is OWED; see CARRY_FORWARD_NO_ACCEPT_PATH, which
#           carries the ruling, its date and what is still missing — CS-8's
#           writer, not a rule) · BR-CUS-025 (a deposit settles EVERYTHING outstanding at
#           close) · BR-CUS-050 (the ORIGINAL receipt date) · BR-CUS-054 (the
#           customer entity and its N:M account link) · BR-CUS-057 (deposit
#           interest — CONFIRMED, engine NOT BUILT) · BR-CUS-089 (the identity
#           match tier and its confirmer are STORED; money moves only on
#           `strong`) · BR-RAT-043 (eligibility is ADVISORY-WITH-AUDIT in v1) ·
#           BR-RAT-069 (available ≠ granted) · BR-RAT-076 (verification, proof
#           and recertification belong to the PROGRAMME;
#           `proof_before_first_reduction` is a stored MONEY rule) ·
#           BR-RAT-112 (eligibility stays advisory — the product does not
#           refuse) · CLAUDE.md rule 2 (money 4dp stored / 2 displayed, never
#           float) · rule 4 (corrections are new rows) · rule 7 (every money
#           action writes `audit_log`)
# Design:   04-docs/02-decisions/18-cr030-onboarding-design.md §5.3.4 (the
#           Eligibility row — *"Never blocks service — only the discount"*),
#           §5.5.3 step 4, §5.5.4 (the deposit carry-forward rule), §5.5.5
#           (tables · endpoints), §5.5.6 TC-MVI-2 / TC-MVI-3
# Tests:    06-backend/tests/test_w5_eligibility_and_deposit_carry.py
# ───────────────────────────────────────────────────────
"""W5 · move-in step 4 — the eligibility panel and the deposit carry-forward.

HUMAN-OWNED · HUMAN-REVIEW-PENDING — this file decides whether a returning
customer's own money follows them to a new account, under CLAUDE.md's 🔒 *money
rounding* path. AI-authored 2026-08-25 under the PO ruling of 2026-08-09
(*"AI will do it; we will review it later as human"*).
⚠ **THIS PARAGRAPH SAID THE FILE WAS ON NEITHER THE G7 GLOB LIST NOR THE REVIEW
LEDGER UNTIL 2026-09-03, AND IT IS ON BOTH (`DEF-2348`).** It was written on
2026-08-25 and it was TRUE then: enrolling a file in either is a process event a
lane may not take alone (B12 r2), so that lane REPORTED the gap instead of
closing it, exactly as `move_out_settlement.py`'s exception (1) still records.
**The gap was then closed by the lanes that own those two files and nobody came
back to the sentence reporting it.** What is true now: this file is
`10-scripts/gates/human_owned.txt` line 210 and it has a row in
`12-governance/09-human-review-ledger.md`, so G7 does read the marker above and
an edit here owes that row an update.
⚠ **THE DIRECTION OF THE STALENESS IS WHY NOTHING WENT RED, AND IT IS WORTH
KNOWING.** The claim UNDER-stated the protection, so it failed safe and no gate
had anything to catch: G7 asserts that a marked file is guarded and ledgered —
which it is — and has no opinion about the file's own prose. The cost was to the
next reader, who would either decline to edit a file believing it unguarded, or
re-report a gap that was already shut. Hard-won law 1 runs in both directions.

════════════════════════════════════════════════════════════════════════════
THE TABLE THIS FILE DOES NOT CREATE — AND WHY THAT IS THE FINDING
════════════════════════════════════════════════════════════════════════════
B18 §5.5.5 and §6.3 both list **`account_discounts` — NEW — W5**:

    account · programme · status (`pending verification` | `active`) ·
    evidence_ref · recertify_on · granted_by

**Every one of those six facts already has a home, built on 2026-08-19 under
CR-013 part 3, and it is `discount_enrolments`** (`apps/rating/discounts.py`,
migration `rating/0009_cr013_discounts.py`):

| B18 `account_discounts` | built column                                      |
|-------------------------|---------------------------------------------------|
| `account`               | `discount_enrolments.account_id` (cross-module FK, |
|                         | in B2 §2's REVIEWED set)                           |
| `programme`             | `discount_enrolments.discount_id` → `discounts`    |
| `status`                | `discount_enrolments.verification_status`          |
| `evidence_ref`          | `discount_enrolment_documents.reference`           |
| `recertify_on`          | `discount_enrolments.recertification_due_on`       |
| `granted_by`            | `discount_enrolments.enrolled_by_user_id`          |

So the migration this lane was allotted **was deliberately not written**, and
the reason is not tidiness. **A bill run reads `discount_enrolments` and
nothing else** — `apps/rating/discount_services.discount_rules_for_account` is
the only door, and `apps/rating/services._validate_plan_discount_rules` says so
in its own comment: *"A bill run reads `discount_enrolments` and never
`plan_discount_rules`."* A discount granted at move-in into a second table
would therefore reduce **no** bill: the screen would show the subsidy, the
enrolment count would rise, every test would pass, and the customer would be
charged in full. That is hard-won law 2 (*built is not wired*) with money on it,
and it is also two answers to *"is this account on SENIOR?"*.

Per `12-governance/13-change-process.md` step 1 — *"when it is ambiguous it is a
**DEFECT**, not a change"* — this is filed as a defect against B18 rather than
built. **This lane may not edit `12-governance/*`, so the defect row is
REPORTED, not written.** Nothing here is blocked by that: everything below runs
on the built table.

════════════════════════════════════════════════════════════════════════════
r11 STEP 0 — THE FOUR POINTS PUT TO THE PO, AND WHAT THE REPO ALREADY SAYS
════════════════════════════════════════════════════════════════════════════
**(1) WHAT MAKES AN IDENTITY MATCH `strong`? STILL UNRULED — and this file does
not decide it.** `BR-CUS-089` is signed for the CONSEQUENCE (*"the tier … and
its confirmer are stored; money moves only on `strong`"*) and says nothing about
the CRITERIA. There is no matcher anywhere in `06-backend`:
`service_request_service.link_customer` states it outright — *"`tier` is the
clerk's, not ours … there is no automatic matcher here"* — and `DEF-638(2)` is
OPEN on the one input B19 §12.3 shows the match being made ON (*"Matched on: ID
number and date of birth"*), a field `REQ-03.1` never collects.

So this file **reads a stored tier and never computes one**. Where no tier has
been stored by a human with a confirmer, the carry-forward is REFUSED with that
as its reason — the conservative direction, and the only one TC-MVI-3 permits.
⚠ **THIS PARAGRAPH SAID NO OPEN QUESTION COVERED THE CRITERIA UNTIL 2026-09-03,
AND THE QUESTION WAS MINTED AND ANSWERED THE SAME WEEK IT WAS WRITTEN
(`DEF-2348`).** What it said, and what was true on the day: *"No OQ in
`12-governance/01-open-questions.md` covers the criteria question (searched
2026-08-25; the registry runs to OQ-363 and none of them is this), so no
`NotImplementedError("OQ-###")` can honestly be raised here — G8 clause B would
refuse a minted id and minting one is not this lane's to do. The OQ is REPORTED
as owed."* **The OQ that was owed is `OQ-364` — the very next id — and the
Product Owner CLOSED it on 2026-08-25** with the strictest of the three readings
offered: **name + date of birth + one government ID**, taking the refusal of
some genuine returners over the risk of handing a stranger somebody else's
$153.50. It is signed into `BR-CUS-089`.
**What did NOT change is this file's behaviour, and that is deliberate.** The
ruling is inert on a SERVICE REQUEST while `DEF-638(2)` is open — `REQ-03.1`
collects no date of birth — so a tier typed against a request is still a human
judgement nothing machine-checks. This file therefore still reads a stored tier
and still refuses everything that is not already `strong`, which is STRICTER
than the ruling and is the safe direction. `CARRY_FORWARD_NO_MATCH_RULE` below
carries the narrowed gap and was corrected when the ruling landed; only this
paragraph was left behind.

**(2) DOES UNVERIFIED ASSISTANCE EVIDENCE GRANT THE DISCOUNT OR WITHHOLD IT?
RULED — and it was ruled twice.** It is **not one answer**; it is a stored
per-programme setting, which is why looking for a global rule found nothing:

  * `BR-RAT-076` (CONFIRMED 2026-08-19): *"`proof_before_first_reduction` is a
    MONEY rule and is stored: true means an unverified enrolment reduces
    nothing and the bill is charged in full."*
  * `BR-RAT-043` (CONFIRMED, PO closing OQ-055): *"eligibility (senior/CAP/
    low-income) is ADVISORY-WITH-AUDIT in v1 — staff attests, audit row records
    who/when; enforced verification + document uploads = v2."*

`rating.discount_services.enrol_account` already implements the landing: an
enrolment whose version demands proof lands `pending`, otherwise
`not_required`, and *"a caller cannot pass a verification status in"*. This
module therefore **claims** and lets rating decide the status.
⚠ **B18's two-value vocabulary (`pending verification` | `active`) is NARROWER
than the built five** (`not_required` · `pending` · `verified` · `expired` ·
`rejected`). The built five are served verbatim and the divergence is named on
the payload rather than collapsed — collapsing `rejected` into *"pending
verification"* would show a refused claim as one still being processed.

**(3) WHAT HAPPENS WHEN `recertify_on` LAPSES? THE RULE IS RULED; THE MECHANISM
DOES NOT EXIST.** `BR-RAT-076` names three lapse behaviours (*notify 60 days
ahead then drop · drop silently · never expires*) and `discount_versions.
lapse_behaviour` stores which. **Nothing reads the date.** Measured
2026-08-25 across `06-backend`: `recertification_due_on` appears in the model,
the migration, one index, `verify_enrolment` (which WRITES it) and
`enrolment_row` (which serialises it) — and in no runner, job, queue, timer or
management command. So a lapsed enrolment keeps reducing bills until a human
looks, and `notify_then_drop` notifies nobody.

That is exactly the shape `move_out_settlement.held_excess_has_no_release_path`
states honestly, and it is stated the same way here:
`RECERTIFICATION_HAS_NO_CHASER`. It is an absence, not a zero and not a stub —
the rule was answered, so an `OQ` stub would be a lie about which half is
missing.

**(4) WHO DEFINES THE PROGRAMMES? THE TENANT DOES, AND THE DOOR IS BUILT.**
`rating.discount_services.create_discount` / `create_discount_version` /
`activate_discount_version` are the authoring path and `POST /discounts` is
already routed (`apps/rating/api.py`). `GET /discount-programmes` is therefore
a **second name for the served `GET /discounts`**, and this module serves the
same rows through the published `rating.selectors.discount_list` rather than
building a parallel catalogue. REPORTED as a route duplication in B18 §5.5.5.

════════════════════════════════════════════════════════════════════════════
WHAT **IS** SETTLED AND IS BUILT HERE — B18 §5.3.4
════════════════════════════════════════════════════════════════════════════
    | **Eligibility** | assistance programme claimed · household size ·
      evidence | **Never blocks service** — only the discount |

`eligibility_panel()` carries `blocks_service: False` as a **constant**, not as
a computed field, and `BLOCKS_SERVICE_NEVER` carries the three signed sentences
that make it so (B18 §5.3.4, BR-RAT-043, BR-RAT-112). A computed `False` is one
refactor away from becoming `True`; a constant with the rulings beside it is
not. `test_w5_eligibility_and_deposit_carry.py` asserts it on the one input
that would tempt a gate — a claim with no evidence at all.

⚠ **`household_size` HAS NO COLUMN** anywhere in this product (measured
2026-08-25: no field on `Customer`, `Account`, `ServiceRequest`,
`DiscountEnrolment`; nothing in B2). It is named in B18 §5.3.4's field list and
in nothing else. Served as `HOUSEHOLD_SIZE_HAS_NO_COLUMN` rather than accepted
and dropped, because a clerk who types it and sees it vanish is DEF-632's shape.

════════════════════════════════════════════════════════════════════════════
THE CARRY-FORWARD — WHAT MOVES, AND WHAT THIS FILE REFUSES TO MOVE
════════════════════════════════════════════════════════════════════════════
B18 §5.5.4: *"**Deposit carry-forward** — From a prior closed account of the
**same customer**. **Requires a strong identity match, because money moves**"*,
and TC-MVI-2 wants the carry **OFFERED** with `carried $153.50`.

**AN OFFER IS ALL THAT IS BUILT, AND THAT IS A RULE-LEVEL LIMIT RATHER THAN A
DEFERRAL.** `BR-CUS-024`'s status line reads *"PROPOSED (mechanics) / linkage
CONFIRMED"*: the LINKAGE is signed (`customer_accounts`, BR-CUS-054, OQ-057
closed) and the MECHANICS — what row moves, whether the old account's deposit
is released, what the ledger posts — are not. `accounts.deposit_on_file` is
additionally a REFUSED field on every non-import door
(`services.REFUSED_FIELDS`), so accepting an offer today would need a write no
signed rule authorises. So: `carry_forward_offer()` computes and audits; there
is no `accept_carry_forward()` and the payload says why.

**THE FIGURE ITSELF IS ❄️ FROZEN AND IS NOT COMPUTED HERE.** WE-7 / GT-23:
a **$150.00** deposit held 14 months at the tenant's 2% simple rate earns
**$3.50**, total **$153.50**. The principal is read off `accounts.
deposit_on_file`; the interest is `BR-CUS-057`'s and comes from
`apps.customers.selectors.deposit_interest_accrued` **through the seam** —
never computed here, exactly as `move_out_settlement._deposit_interest` refuses
to compute it, because two modules disagreeing about a deposit is how a
customer gets two different answers to one question.

**TWO GAPS RIDE EVERY POSITION, AND THEY POINT IN OPPOSITE DIRECTIONS.**

  * `DEPOSIT_INTEREST_NOT_READABLE` (BR-CUS-057) — the accrual engine is not
    built (US-CUS-023 §7). Reading it as `0.00` would carry **$150.00** where
    **$153.50** is owed and quietly keep $3.50 of the customer's money. So a
    position holding a principal with no readable interest **has no figure at
    all**; `refundable` is `None` and the gap is named. An account holding NO
    deposit answers `0.00` without consulting the engine — there is nothing to
    accrue on — which is `move_out_settlement`'s own posture, deliberately
    identical.

  * `DEPOSIT_NOT_NET_OF_SETTLEMENT` (BR-CUS-025 · BR-CUS-031) — and this one is
    the sharper of the two because it points the OTHER way. BR-CUS-025 settles
    the deposit against *everything outstanding* at close, and **nothing in this
    repository writes that result back**: `move_out_settlement` returns
    `persisted: False` by its own docstring (*"There is no handoff table, queue
    or outbox anywhere in B2 or its addenda"*), and `deposit_on_file` is written
    only at create and by the US-CUS-023 import. So the stored column on a
    CLOSED account is the deposit as **RECEIVED**, not what survived the
    settlement. Carrying it forward without saying so would hand a customer
    money the utility already applied to their final bill.

    It is a WARNING on the payload rather than a refusal, and the direction is
    argued rather than assumed: refusing every carry-forward would delete a
    behaviour B18 §5.5.4 requires and TC-MVI-2 asserts, on a gap that belongs to
    the move-out side. It is named on every position so no screen can print a
    figure without it.

**AND THE MATCH GATE IS SEPARATE FROM BOTH.** A weak, probable, absent or
unconfirmed tier refuses the offer OUTRIGHT — no figure, no gap list, one
reason (TC-MVI-3: *"money never moves on a weak match"*). The gaps above only
ever reach a caller that already cleared BR-CUS-089.

CLAUDE.md rule 7: **both the offer and the refusal write `audit_log`.** A
refusal is a decision about money — it is the decision that a returning
customer's $153.50 stayed where it was — and B18's own KPI strip counts
`DEPOSITS TO CARRY OVER`, so a refusal that left no trace would be a figure
nobody could reconcile.

════════════════════════════════════════════════════════════════════════════
CROSS-MODULE ACCESS — NO ORM, EVER
════════════════════════════════════════════════════════════════════════════
Everything rating owns is reached through `seams.resolve(...)`, which imports
the neighbour's published module at call time and returns `None` while it is
not there (B1/B8: *"customers NEVER touches another module's ORM"*). Three
callables are consumed, and none of them is `services`/`selectors`, so the
`kind` argument names the module that publishes them:

    apps.rating.selectors.discount_list(ListParams)        kind="selectors"
    apps.rating.discount_services.discount_rules_for_account(account_id, day)
                                                    kind="discount_services"
    apps.rating.discount_services.enrol_account(actor, discount_id, account_id)
                                                    kind="discount_services"

⚠ **EXCEPTION, DECLARED: `G20` DOES NOT HARVEST THIS FILE** — it reads
`apps/*/seams.py` and `apps/*/<neighbour>_seam.py` only, so these three
contracts are invisible to it, exactly as `move_out_settlement.py`'s exception
(3) records for its own four. `apps/customers/seams.py` is not in this lane's
write scope; publishing them there is REPORTED.

⚠ **`enrol_account` WAS `@require_role(SYSTEM_ADMIN)` WHILE A MOVE-IN IS A
`BILLING_CLERK`'s JOB — RESOLVED IN RATING, 2026-10-05.** PO ruling (decision
log *"FOUR PO RULINGS IN ONE REPLY"* (2), option (b)), verbatim: *"Let billing
clerks record it themselves. - we have set the limits so clark can do it - its
a day to day work"*. Rating's decorator now admits a Billing Clerk, so the
clerk's claim through this door is enrolled. Any refusal rating still raises
passes through UNCHANGED — this module never decides another module's RBAC.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from django.db import transaction

from apps.customers import models, seams
from core import audit as core_audit
from core import errors, money
from core.pagination import ListParams
from core.permissions import BILLING_CLERK, SYSTEM_ADMIN, require_role

ZERO = Decimal("0")
FOUR_DP = Decimal("0.0001")

#: BR-CUS-089's closed tier vocabulary, copied from
#: `service_request_service.MATCH_TIERS` rather than imported so this module
#: does not depend on the request surface existing. The two are asserted equal
#: in the test file, which is what stops them drifting.
MATCH_TIERS: tuple[str, ...] = ("strong", "probable", "weak")

#: The ONE tier that may move money (BR-CUS-089). Named as a constant because
#: `== "strong"` scattered through a file is a rule nobody can grep for.
TIER_STRONG = "strong"


# ═══════════════════════════════════════════════════════════════════════════
# THE SETTLED SENTENCE — B18 §5.3.4, and it is a constant, not a computation
# ═══════════════════════════════════════════════════════════════════════════
#: B18 §5.3.4's Eligibility row, verbatim: *"**Never blocks service** — only the
#: discount."* Two CONFIRMED rating rules say the same thing about the same
#: facts from the other side, and both are quoted so a reader does not have to
#: take this module's word for it.
BLOCKS_SERVICE_NEVER: dict[str, Any] = {
    "blocks_service": False,
    "br_ref": "B18 §5.3.4 · BR-RAT-043 · BR-RAT-112",
    "detail": (
        "B18 §5.3.4: 'Never blocks service — only the discount.' BR-RAT-043 (CONFIRMED, PO "
        "closing OQ-055): eligibility is ADVISORY-WITH-AUDIT in v1 — staff attests and an audit "
        "row records who and when. BR-RAT-112 (PO 2026-08-21, closing CR-022): 'dont refuse, it "
        "is okay many times utilities are not in position to make all changes due to human "
        "factor hence we have to keep flexibility'. An assistance claim, verified or not, "
        "changes what the customer is CHARGED and never whether they are CONNECTED."
    ),
}


# ═══════════════════════════════════════════════════════════════════════════
# THE STATED ABSENCES — each names the rule it belongs to, never a zero
# ═══════════════════════════════════════════════════════════════════════════
GAP_DEPOSIT_INTEREST = "deposit_interest_not_readable"
GAP_NOT_NET_OF_SETTLEMENT = "deposit_not_net_of_settlement"
GAP_NO_MATCH_RULE = "identity_match_strength_has_no_rule"
GAP_NO_RECERT_CHASER = "recertification_has_no_chaser"
GAP_NO_HOUSEHOLD_SIZE = "household_size_has_no_column"
GAP_PROGRAMMES_UNWIRED = "discount_catalogue_not_published"
GAP_ENROLMENT_UNWIRED = "discount_enrolment_not_published"
GAP_NO_ACCEPT_PATH = "carry_forward_has_no_accept_path"
GAP_STATUS_VOCABULARY = "status_vocabulary_wider_than_b18"

DEPOSIT_INTEREST_NOT_READABLE: dict[str, Any] = {
    "code": GAP_DEPOSIT_INTEREST,
    "br_ref": "BR-CUS-057",
    "detail": (
        "BR-CUS-057's deposit interest could not be stated at this account's closing date — "
        "the deposit has no receipt date, the account has no closing date, or the utility's "
        "rate could not be read. WE-7/GT-23's frozen pair is $150.00 principal + $3.50 interest = "
        "$153.50, so reading the interest as 0.00 would carry $150.00 where $153.50 is owed "
        "and keep $3.50 of the customer's own money. No figure is served for this position."
    ),
}

DEPOSIT_NOT_NET_OF_SETTLEMENT: dict[str, Any] = {
    "code": GAP_NOT_NET_OF_SETTLEMENT,
    "br_ref": "BR-CUS-025 · BR-CUS-031",
    "detail": (
        "BR-CUS-025 settles the deposit against EVERYTHING OUTSTANDING at close, and nothing "
        "in this repository writes that result back: `apps.customers.move_out_settlement` "
        "returns `persisted: False` because no handoff table, queue or outbox exists (B2 and "
        "its addenda declare none), and `accounts.deposit_on_file` is written only at create "
        "and by the US-CUS-023 import. So this figure is the deposit as RECEIVED, not what "
        "survived the final bill. Named on every position so no screen prints it bare."
    ),
}

#: ✅ **CORRECTED 2026-08-31 (CR-056 W2 task 14) — THIS TEXT WAS STALE AND IT
#: SAID THE OPPOSITE OF THE SIGNED RULE.** It read *"nothing in this repository
#: defines what makes a match strong … No open question covers the criteria;
#: one is owed."* Both halves were true when written and both were already
#: wrong the same week: `OQ-364` was minted for exactly that question and
#: **CLOSED on 2026-08-25**, PO verbatim *"Name + date of birth + one government
#: ID"*, signed into `BR-CUS-089`. Hard-won law 1 — a comment describing the
#: product is not the product, and a stated absence that has been filled is a
#: lie with a rule id on it.
#:
#: What is TRUE now, and it is a narrower gap: the criteria are ruled AND
#: assessable. `customers 0036` gives the customer a date of birth, an SSN and
#: a driving licence, and `apps/customers/identity_match.py` computes exactly
#: those three facts. What still cannot be assessed is a SERVICE REQUEST's own
#: applicant — `REQ-03.1` collects no date of birth and `DEF-638(2)` is open on
#: precisely that — so a tier a clerk types on a request is still the clerk's
#: judgement and nothing machine-checks it.
CARRY_FORWARD_NO_MATCH_RULE: dict[str, Any] = {
    "code": GAP_NO_MATCH_RULE,
    "br_ref": "BR-CUS-089 · OQ-364 (CLOSED) · DEF-638(2)",
    "detail": (
        "BR-CUS-089's criteria are RULED and are 'name + date of birth + one government ID' "
        "(PO 2026-08-25, closing OQ-364). They are assessable on a CUSTOMER since CR-056 "
        "task 11 put those three facts on the customer row, and `apps.customers."
        "identity_match` computes them. They are still NOT assessable on a SERVICE REQUEST: "
        "REQ-03.1 collects no date of birth (DEF-638(2), open), so a tier recorded against a "
        "request remains a human judgement that nothing here checks. Nothing in this module "
        "computes a tier either way — it reads one that was stored with its confirmer."
    ),
}

RECERTIFICATION_HAS_NO_CHASER: dict[str, Any] = {
    "code": GAP_NO_RECERT_CHASER,
    "br_ref": "BR-RAT-076 (mechanism half)",
    "detail": (
        "BR-RAT-076 names three lapse behaviours — notify 60 days ahead then drop, drop "
        "silently, never expires — and `discount_versions.lapse_behaviour` stores which. "
        "NOTHING READS THE DATE: measured 2026-08-25, `discount_enrolments."
        "recertification_due_on` is written by `verify_enrolment`, serialised by "
        "`enrolment_row`, indexed once, and consumed by no runner, job, queue, timer or "
        "management command. A lapsed enrolment keeps reducing bills until a human looks, and "
        "`notify_then_drop` notifies nobody. The rule is ruled; the chaser is absent."
    ),
}

HOUSEHOLD_SIZE_HAS_NO_COLUMN: dict[str, Any] = {
    "code": GAP_NO_HOUSEHOLD_SIZE,
    "br_ref": "B18 §5.3.4",
    "detail": (
        "B18 §5.3.4's Eligibility row asks for 'assistance programme claimed · household size "
        "· evidence'. Household size has no column anywhere in this product — not on "
        "`customers`, `accounts`, `service_requests` or `discount_enrolments`, and B2 declares "
        "none. It is REFUSED by name rather than accepted and dropped: a clerk who types it "
        "and watches it vanish is DEF-632's shape."
    ),
}

#: ⚠ **THIS NOTICE SAID THE MECHANICS WERE UNRULED UNTIL 2026-09-03, AND THE
#: PRODUCT OWNER RULED THEM ON 2026-09-01 (`CR-059` CS-22, `DEF-2348`).** It read
#: *"BR-CUS-024 is 'PROPOSED (mechanics) / linkage CONFIRMED' … accepting would
#: need a write no signed rule authorises."* The second half of that sentence is
#: now FALSE and it is the half that matters: the PO ruled that **the deposit is
#: OFFERED FORWARD, not refunded and re-collected**, and that it moves as a
#: **liability transfer between two accounts**. A write IS authorised now.
#:
#: **WHAT IS STILL MISSING IS THE WRITER, NOT THE RULE, AND THE TWO ARE DIFFERENT
#: KINDS OF ABSENCE.** `CR-059` CS-8 is the ONE reviewed writer for money crossing
#: two accounts — *"build the transfer once"*, shared by this carry-forward, the
#: closing excess, the landlord residue and the payment move.
#:
#: ⚠ **CS-8 LANDED LATER ON 2026-09-03 AND THIS CARRY-FORWARD IS STILL BLOCKED,
#: WHICH IS THE OPPOSITE OF WHAT IT LOOKS LIKE.** This paragraph said the writer
#: *"does not exist in any module"*; it does now —
#: `apps/payments/transfer.transfer_credit_between_accounts`, posting one
#: balanced entry `DR 2400 customer credit (SOURCE) / CR 1200 AR (DESTINATION)`.
#: **It moves a CREDIT, and a deposit is not a credit.** The CS-8 lane says so in
#: its own file header: *"It does not carry a deposit across. A `deposit` purpose
#: payment is money the utility HOLDS (US-PAY-002 TC-1) and is not credit;
#: CS-22's carry-forward is a different change that will call this writer with
#: its own purpose."*
#:
#: **THE DISTINCTION IS ACCOUNTING, NOT PLUMBING, AND IT IS WHY WIRING THIS
#: STRAIGHT INTO CS-8 WOULD BE WORSE THAN LEAVING IT REFUSED.** A credit is the
#: customer's money against their own bills, so settling the destination's
#: receivable with it is right. A deposit is **security the utility holds and
#: owes back**: it lives on **2300 deposit liability**, and a carried deposit
#: that paid down the new account's first bill would have converted returnable
#: security into revenue — silently, on a balanced entry, with every test green —
#: and the customer would be asked for a fresh deposit later.
#:
#: **SO WHAT CS-22 NEEDS IS NOW SPECIFIC:** extend that same writer with a
#: deposit purpose (never a second writer — CS-8's own rule), and give
#: `ledger_seam.post_account_transfer` a leg pair moving **2300 SOURCE → 2300
#: DESTINATION** with the destination's AR untouched. `$150.00` of principal on
#: the repo's own fixture, or `$153.50` once `BR-CUS-057`'s interest is readable.
#: The code below is unchanged: every version of this reason refuses.
#:
#: ⚠ **AND THE REGISTER ROW HAS NOT CAUGHT UP EITHER.**
#: `04-docs/05-modules/03-customers/02-business-rules.md` BR-CUS-024 still reads
#: `PROPOSED (mechanics) / linkage CONFIRMED`. `CR-059` CS-22 says in its own
#: words that the rule *"can be CONFIRMED"* — so the amendment is OWED and is not
#: assumed here; that file is outside this lane's write scope and the amendment is
#: REPORTED. This notice states the RULING and its date, never a register state
#: nobody has written.
CARRY_FORWARD_NO_ACCEPT_PATH: dict[str, Any] = {
    "code": GAP_NO_ACCEPT_PATH,
    "br_ref": "BR-CUS-024 (mechanics half) · CR-059 CS-22 (PO ruling 2026-09-01) · CS-8",
    "detail": (
        "The MECHANICS are ruled and the WRITER is missing, which is a narrower gap than "
        "this notice used to describe. PO ruling 2026-09-01 (CR-059 CS-22): the deposit is "
        "OFFERED FORWARD rather than refunded and re-collected, and it moves as a liability "
        "transfer between two accounts. The linkage was already signed (`customer_accounts`, "
        "BR-CUS-054, OQ-057 closed). CS-8's writer now EXISTS "
        "(`apps.payments.transfer.transfer_credit_between_accounts`, landed 2026-09-03) and "
        "this carry-forward still cannot use it: that writer moves a customer CREDIT, "
        "debiting 2400 and settling the destination's receivable, and a deposit is not a "
        "credit. A deposit is security the utility HOLDS on 2300 and owes back "
        "(US-PAY-002 TC-1), so carrying it onto a bill would turn returnable security into "
        "revenue on a perfectly balanced entry. The CS-8 file says the same in its own "
        "header: a deposit purpose is a different change that will call that writer. What is "
        "owed is a deposit purpose on THAT writer, moving 2300 source to 2300 destination "
        "with AR untouched — never a second writer, because CR-059 CS-8 says build the "
        "transfer ONCE. `accounts.deposit_on_file` also remains a REFUSED field on every "
        "non-import door (`services.REFUSED_FIELDS`). So this is still an OFFER with no "
        "accept path. BR-CUS-024's register row still reads PROPOSED on the mechanics half; "
        "that amendment is owed and is not assumed here."
    ),
}

STATUS_VOCABULARY_WIDER_THAN_B18: dict[str, Any] = {
    "code": GAP_STATUS_VOCABULARY,
    "br_ref": "B18 §5.5.5 vs BR-RAT-076",
    "detail": (
        "B18 §5.5.5 gives `account_discounts.status` two values — 'pending verification' and "
        "'active'. The built column carries five: not_required, pending, verified, expired, "
        "rejected. The five are served verbatim rather than collapsed: mapping `rejected` onto "
        "'pending verification' would show a refused claim as one still being processed, and "
        "`expired` is exactly the lapse state BR-RAT-076 names."
    ),
}

PROGRAMMES_UNWIRED: dict[str, Any] = {
    "code": GAP_PROGRAMMES_UNWIRED,
    "br_ref": "BR-RAT-069",
    "detail": (
        "`apps.rating.selectors.discount_list` is not published, so the programme catalogue "
        "cannot be read. The panel serves no programmes rather than an empty list — an empty "
        "list would read as 'this utility runs no assistance programmes'."
    ),
}

ENROLMENT_UNWIRED: dict[str, Any] = {
    "code": GAP_ENROLMENT_UNWIRED,
    "br_ref": "BR-RAT-069",
    "detail": (
        "`apps.rating.discount_services` is not published, so what this account has already "
        "claimed cannot be read and no claim can be recorded. Served as an absence rather than "
        "as 'nothing claimed'."
    ),
}


# ═══════════════════════════════════════════════════════════════════════════
# MONEY — rule 2, and the same three helpers `move_out_settlement` uses
# ═══════════════════════════════════════════════════════════════════════════
def _money(value: Any, what: str) -> Decimal:
    """A money figure or a refusal — NEVER a float and never a silent zero."""
    if isinstance(value, Decimal):
        return value
    if value is None or isinstance(value, float):
        raise errors.BizError(
            errors.BIZ_COMPLETENESS,
            br_ref="BR-CUS-024",
            message_key="customers.deposit_position.money_not_a_decimal",
            params={"what": what, "value": repr(value)},
        )
    return Decimal(str(value))


def _stored(amount: Decimal) -> str:
    """CLAUDE.md rule 2 as re-signed 2026-08-22 — money is STORED to 4dp."""
    return str(amount.quantize(FOUR_DP))


def _display(amount: Decimal) -> str:
    """…and DISPLAYED to 2, rounded once, by B4's ❄️ frozen half-up rule."""
    return str(money.finalize(amount))


def _pair(amount: Decimal | None) -> dict[str, str | None]:
    if amount is None:
        return {"stored": None, "display": None}
    return {"stored": _stored(amount), "display": _display(amount)}


def _tenant_id() -> Any:
    from core import tenancy as core_tenancy

    tenant_id = core_tenancy.current_tenant_id()
    if tenant_id is None:
        raise errors.AuthError(errors.AUTH_TENANT_UNRESOLVABLE, br_ref="BR-TEN-003")
    return tenant_id


def _audit(actor: Any, action: str, entity_id: Any, *, after: dict[str, Any]) -> None:
    """CLAUDE.md rule 7 — every money action writes `audit_log`.

    BEFORE is absent because none of these actions changes a row. What they
    record is a DECISION about money — including the decision NOT to move it,
    which is the whole of TC-MVI-3 and is the only trace a refused carry-forward
    leaves anywhere. Same posture and same reasoning as
    `move_out_settlement._audit`.
    """
    core_audit.write_row(
        action=action,
        entity_type="customer",
        entity_id=entity_id,
        actor_user_id=getattr(actor, "id", None) or getattr(actor, "pk", None),
        before=None,
        after=after,
    )


# ═══════════════════════════════════════════════════════════════════════════
# GET /discount-programmes — the tenant's catalogue, served from rating
# ═══════════════════════════════════════════════════════════════════════════
@require_role(SYSTEM_ADMIN, BILLING_CLERK, br_ref="BR-SHL-025")
def discount_programmes(actor: Any, params: ListParams | None = None) -> dict[str, Any]:
    """B18 §5.5.5's `GET /discount-programmes`.

    ⚠ **THIS IS A SECOND NAME FOR A ROUTE THAT ALREADY EXISTS.** `GET
    /discounts` is served today by `apps/rating/api.discounts` over
    `rating.selectors.discount_list`, and CR-013 part 3 built the whole
    catalogue — object, dated versions, plan availability, enrolment and
    grants — on 2026-08-19. Serving the same rows through the seam keeps the
    move-in panel and the Plans & Rates screen answering from one table; a
    parallel catalogue is BR-RAT-069's *"available ≠ granted"* failure with a
    different name on it. REPORTED against B18 §5.5.5.

    Programmes are TENANT-AUTHORED — `create_discount` /
    `create_discount_version` / `activate_discount_version` — which answers the
    fourth of the four points this lane was asked to leave open: it is not
    open, and it is not a hard-coded list either.
    """
    read = seams.resolve("rating", "discount_list", kind="selectors")
    if read is None:
        return {
            "programmes": None,
            "gaps": [GAP_PROGRAMMES_UNWIRED],
            "unavailable": [PROGRAMMES_UNWIRED],
            "eligibility": BLOCKS_SERVICE_NEVER,
        }
    rows = read(params or ListParams(per=200))
    return {
        "programmes": list(rows),
        "gaps": [],
        "unavailable": [RECERTIFICATION_HAS_NO_CHASER],
        "eligibility": BLOCKS_SERVICE_NEVER,
    }


# ═══════════════════════════════════════════════════════════════════════════
# MOVE-IN STEP 4 — THE ELIGIBILITY PANEL (task 5.4)
# ═══════════════════════════════════════════════════════════════════════════
def _account_or_refuse(account_id: Any) -> models.Account:
    account = models.Account.objects.filter(tenant_id=_tenant_id(), pk=account_id).first()
    if account is None:
        raise errors.deny_as_not_found("BR-TEN-003")
    return account


def _claimed_rows(account_id: Any) -> tuple[list[dict[str, Any]] | None, bool]:
    """What this account has already claimed, through rating's published read.

    Returns `(rows, wired)`. `rows is None` with `wired is False` is *"rating
    does not publish this"* and is NOT the same fact as an empty list, which is
    *"this account claims nothing"* — one is a wiring absence and the other is
    an answer, and a panel that printed them the same way would tell a clerk a
    customer has no subsidy when the truth is that nobody asked.
    """
    read = seams.resolve("rating", "discount_rules_for_account", kind="discount_services")
    if read is None:
        return None, False
    rows: list[dict[str, Any]] = []
    for rule in read(account_id):
        # BR-RAT-076, computed the ONE way `discount_pricing.price_discounts`
        # computes it (its own line: `if rule.proof_before_first_reduction and
        # not rule.verified`). Restated here rather than imported because
        # importing rating's pricing module from customers would be reaching
        # past the seam; asserted identical in the test file.
        withheld = bool(rule.proof_before_first_reduction) and not bool(rule.verified)
        rows.append(
            {
                "programme": rule.code,
                "type": rule.discount_type,
                "value": str(rule.value),
                "currency": rule.currency,
                "applies_to": rule.applies_to,
                "verified": bool(rule.verified),
                "proof_before_first_reduction": bool(rule.proof_before_first_reduction),
                # The money answer to unruled point (2), per programme.
                "reduces_bill_now": not withheld,
                "reduces_bill_now_reason": (
                    (
                        "BR-RAT-076: this programme requires proof before the first reduction "
                        "and the claim is not verified, so the bill is charged in full. The "
                        "claim stands; the reduction starts when the proof is recorded."
                    )
                    if withheld
                    else None
                ),
            }
        )
    return rows, True


@require_role(SYSTEM_ADMIN, BILLING_CLERK, br_ref="BR-SHL-025")
def eligibility_panel(actor: Any, account_id: Any = None) -> dict[str, Any]:
    """S19 step 4's eligibility panel — B18 §5.5.3 row 4, §5.3.4's field group.

    **The first thing on it is the thing that is settled**: `eligibility`
    carries `blocks_service: False` as a constant with its three rulings
    quoted. Everything after it is advisory by construction, which is why no
    branch below can refuse anything.

    `account_id=None` is the DRAFT case and is a real state, not an omission:
    B18 §5.5.2 draws two of five move-in rows with `ACCOUNT` reading *"— draft"*
    because the wizard has not created one yet. A claim cannot be recorded
    against a draft — `discount_enrolments.account_id` is NOT NULL and the row
    is the grant — so the panel serves the catalogue and says the claim lands at
    commit, rather than pretending to hold it.
    """
    unavailable: list[dict[str, Any]] = [
        RECERTIFICATION_HAS_NO_CHASER,
        HOUSEHOLD_SIZE_HAS_NO_COLUMN,
        STATUS_VOCABULARY_WIDER_THAN_B18,
    ]
    catalogue = discount_programmes(actor)
    payload: dict[str, Any] = {
        "eligibility": BLOCKS_SERVICE_NEVER,
        "account_id": None if account_id is None else str(account_id),
        "programmes": catalogue["programmes"],
        "claimed": None,
        "claim_recordable": account_id is not None,
        "gaps": list(catalogue["gaps"]),
        "unavailable": unavailable,
    }
    if GAP_PROGRAMMES_UNWIRED in catalogue["gaps"]:
        payload["unavailable"] = payload["unavailable"] + [PROGRAMMES_UNWIRED]
    if account_id is None:
        payload["draft"] = {
            "code": "claim_lands_at_commit",
            "br_ref": "BR-RAT-069 · B18 §5.5.2",
            "detail": (
                "The wizard has not created an account yet ('— draft' in the move-in list), and "
                "a claim IS the grant — `discount_enrolments.account_id` is NOT NULL. So the "
                "panel offers the programmes and the claim is recorded when the account is "
                "created, not held in the wizard."
            ),
        }
        return payload
    account = _account_or_refuse(account_id)
    claimed, wired = _claimed_rows(account.id)
    payload["claimed"] = claimed
    if not wired:
        payload["gaps"] = payload["gaps"] + [GAP_ENROLMENT_UNWIRED]
        payload["unavailable"] = payload["unavailable"] + [ENROLMENT_UNWIRED]
    return payload


#: DEF-RAT-9792 — the move-in's own sentence (DEF-CUS-9779), *"This discount
#: is applied automatically."*, already in all eleven catalogues. One fact,
#: one key, whichever door a person used.
DISCOUNT_AUTOMATIC = "customers.moveIn.discountAutomatic"


def _is_uuid(value: Any) -> bool:
    """A malformed id is `enrol_account`'s to refuse on its own terms; the
    automatic check only asks about an id a discount could have."""
    from uuid import UUID

    try:
        UUID(str(value))
    except (TypeError, ValueError):
        return False
    return True


#: `DEF-RAT-9833` — a hand Autopay add on an account under the NSF cash-only
#: sanction. The sync's check excludes that sanction, so the add would be ended
#: that night — the one thing ruling 4 forbids — and it is refused by name with
#: the portal's own sentence, *"This account is cash only."* (eleven catalogues).
DISCOUNT_CASH_ONLY = "customers.discounts.cashOnly"

#: The account column each setting-paired check mirrors (rating's check keys).
SETTING_COLUMNS: dict[str, str] = {"autopay": "autopay", "paperless": "paperless"}


def switch_setting_on(actor: Any, account: models.Account, check: str) -> bool:
    """Switch the account's Autopay or Paperless setting ON because a person
    added the matching discount. Returns True when it changed.

    ⚖️ PO ruling 4, 2026-10-06, as the coordinator read it ((b), `DEF-RAT-9833`):
    the discount and the setting are kept matched — *"ticking the discount also
    switches the setting On"*. Customers owns the column, so customers writes
    it; one `account.updated` audit row names the reason (hard rule 7). Called
    INSIDE the claim's transaction. Autopay on a cash-only account is refused
    (`DISCOUNT_CASH_ONLY`).
    """
    column = SETTING_COLUMNS.get(check)
    if column is None:
        return False
    if column == "autopay" and account.cash_only_no_autopay:
        raise errors.ValidationError(
            errors.VAL_RANGE,
            message_key=DISCOUNT_CASH_ONLY,
            field_errors=[
                {
                    "field": "programme_id",
                    "code": errors.VAL_RANGE,
                    "message_key": DISCOUNT_CASH_ONLY,
                    "params": {},
                }
            ],
        )
    if getattr(account, column):
        return False
    setattr(account, column, True)
    account.save(update_fields=[column, "updated_at"])
    core_audit.write_row(
        action="account.updated",
        entity_type="account",
        entity_id=account.pk,
        actor_user_id=getattr(actor, "id", None) or getattr(actor, "pk", None),
        before={column: False},
        after={column: True, "reason": "discount_added"},
    )
    return True


def settings_switched_on(actor: Any, account_id: Any, *, source: str) -> list[dict[str, Any]]:
    """The account's Autopay or Paperless setting has just been written ON —
    enrol it NOW in the matching Automatic discount its plan carries, so the
    next bill picks it up rather than waiting for tonight's sync.

    ⚖️ PO ruling 4, 2026-10-06 (reading (b), `DEF-RAT-9833`), verbatim: *"so
    when clark make it on or adds it you ahve to set it up so that next billing
    cycle pick it"*. Rating's writer (`enrol_for_settings`) decides and audits;
    this is the one call every door that writes the column makes (the account
    edit, the portal's email choice, the move-in). `[]` while rating does not
    publish it. Switching OFF calls nothing: the sync ends it that night.
    """
    enrol = seams.resolve("rating", "enrol_for_settings", kind="discount_services")
    if enrol is None:
        return []
    return enrol(actor, account_id, source=source)


@require_role(SYSTEM_ADMIN, BILLING_CLERK, br_ref="BR-SHL-025")
def claim_assistance(
    actor: Any,
    account_id: Any,
    programme_id: Any,
    *,
    household_size: Any = None,
) -> dict[str, Any]:
    """Record an assistance claim made at move-in step 4.

    **THE STATUS IS RATING'S TO DECIDE AND THIS FUNCTION CANNOT PASS ONE.**
    `enrol_account`'s own words: *"a discount whose version demands proof enrols
    as `pending`, not `verified` … a caller cannot pass a verification status
    in — verification is its own recorded act with its own audit row."* That is
    BR-RAT-076 and it is the answer to *"does unverified evidence grant the
    discount or withhold it"*: the PROGRAMME decides, per programme, and the
    decision is already stored.

    ⚠ `household_size` is REFUSED by name — see `HOUSEHOLD_SIZE_HAS_NO_COLUMN`.
    Accepting and dropping it would be a clerk's input disappearing silently.
    """
    if household_size is not None:
        raise errors.ValidationError(
            errors.VAL_UNKNOWN_LOOKUP,
            message_key="customers.eligibility.householdSizeHasNoColumn",
            params={"br_ref": "B18 §5.3.4"},
        )
    account = _account_or_refuse(account_id)
    # DEF-RAT-9792 — this is the door a PERSON uses (Plans & Rates' + Enroll an
    # account, `POST /accounts/{id}/discounts`, the move-in). An AUTOMATIC
    # discount is the nightly sync's to grant and end (PO 2026-10-03 ruling
    # (3)), so a hand enrolment was ended the next night. Refused by name, read
    # from the stored `enrolment_mode` through rating's ONE reader
    # (`automatic_discount_ids`, DEF-CUS-9779's) with the move-in's own
    # sentence. The sync and the sample data call rating's `enrol_account`
    # directly and never pass through here.
    #
    # ⚖️ AMENDED 2026-10-06 (`DEF-RAT-9833`) — PO D2 (b), verbatim: *"Clark has
    # to add those discounts. clark can add it later also on account"*. The
    # refusal now reads `hand_refused_discount_ids`: Municipal account and an
    # *Everyone on the plan* discount stay refused; Autopay and Paperless are
    # added by hand and switch their setting On in the same transaction
    # (`switch_setting_on`, ruling 4 reading (b)).
    refused_fn = seams.resolve("rating", "hand_refused_discount_ids", kind="discount_services")
    if (
        refused_fn is not None
        and _is_uuid(programme_id)
        and str(programme_id) in refused_fn([str(programme_id)], seams.tenant_today())
    ):
        raise errors.ValidationError(
            errors.VAL_RANGE,
            message_key=DISCOUNT_AUTOMATIC,
            field_errors=[
                {
                    "field": "programme_id",
                    "code": errors.VAL_RANGE,
                    "message_key": DISCOUNT_AUTOMATIC,
                    "params": {},
                }
            ],
        )
    enrol = seams.resolve("rating", "enrol_account", kind="discount_services")
    if enrol is None:
        return {
            "claimed": False,
            "account_id": str(account.id),
            "gaps": [GAP_ENROLMENT_UNWIRED],
            "unavailable": [ENROLMENT_UNWIRED],
            "eligibility": BLOCKS_SERVICE_NEVER,
        }
    # Rating owns the write, the audit row and the RBAC on it (System Admin and,
    # since the PO's ruling of 2026-10-05, Billing Clerk). Any refusal from
    # inside it reaches the caller UNCHANGED — never caught, never softened.
    #
    # ⚖️ `DEF-RAT-9833` (PO ruling 4, reading (b)) — an Autopay or Paperless
    # add switches its setting On FIRST, in ONE transaction with the
    # enrolment, so a refusal from rating (a plan that does not carry it)
    # rolls the setting back too and the two never disagree.
    paired_fn = seams.resolve("rating", "setting_paired_discount_ids", kind="discount_services")
    check = (
        (paired_fn([str(programme_id)], seams.tenant_today()) or {}).get(str(programme_id))
        if paired_fn is not None and _is_uuid(programme_id)
        else None
    )
    with transaction.atomic():
        if check is not None:
            switch_setting_on(actor, account, check)
        row = enrol(actor, programme_id, account.id)
    return {
        "claimed": True,
        "account_id": str(account.id),
        "enrolment": row,
        "status": row.get("verification_status"),
        "recertify_on": row.get("recertification_due_on"),
        "gaps": [],
        "unavailable": [RECERTIFICATION_HAS_NO_CHASER, STATUS_VOCABULARY_WIDER_THAN_B18],
        "eligibility": BLOCKS_SERVICE_NEVER,
    }


# ═══════════════════════════════════════════════════════════════════════════
# GET /customers/{id}/deposit-position — task 5.5's read half
# ═══════════════════════════════════════════════════════════════════════════
@dataclass(frozen=True)
class DepositPosition:
    """One CLOSED account of one customer, and what it holds.

    `interest is None` means BR-CUS-057 could not answer, NOT that it is zero,
    and `refundable` is `None` with it — the two are computed together so no
    caller can serialise a total that silently dropped a term.
    """

    account_id: str
    account_no: str | None
    closed_at: str | None
    currency: str
    principal: Decimal
    interest: Decimal | None

    @property
    def refundable(self) -> Decimal | None:
        return None if self.interest is None else self.principal + self.interest

    @property
    def gaps(self) -> list[str]:
        out: list[str] = []
        if self.interest is None:
            out.append(GAP_DEPOSIT_INTEREST)
        if self.principal > ZERO:
            out.append(GAP_NOT_NET_OF_SETTLEMENT)
        return out

    def serialize(self) -> dict[str, Any]:
        return {
            "account_id": self.account_id,
            "account_no": self.account_no,
            "closed_at": self.closed_at,
            "currency": self.currency,
            "principal": _pair(self.principal),
            "interest": _pair(self.interest),
            "refundable": _pair(self.refundable),
            "gaps": self.gaps,
        }


def _deposit_interest(account: models.Account) -> Decimal | None:
    """BR-CUS-057's accrual, or None. NEVER computed here.

    An account holding NO deposit answers ZERO without consulting the engine —
    there is nothing to accrue on, and gapping those would refuse a
    carry-forward for an account with nothing to carry. This is
    `move_out_settlement._deposit_interest`'s posture, deliberately identical:
    two modules disagreeing about when a deposit may be read is how a customer
    gets two different answers to one question.

    ⛔ **THE DAY IS THE ACCOUNT'S CLOSING DATE, AND FOR FOUR WEEKS NO DAY WAS
    PASSED AT ALL — `DEF-CUS-8711`.** The published read has REQUIRED `as_of`
    since `fbe971d14` (2026-09-03, `CR-059` task 30), and this call was not
    moved with it, so every CLOSED account holding a deposit raised
    ``TypeError: deposit_interest_accrued() missing 1 required positional
    argument: 'as_of'`` — a 500 on the deposit-position screen and on the
    carry-forward offer. `transfers._deposit_interest` was the same defect one
    file along (`DEF-CUS-5940`).

    **Why the closing date and not today.** Every account read here is CLOSED,
    and `BR-CUS-057` says the interest *"pays out at refund/closure"*;
    `BR-CUS-030` makes ``closed_at`` the move-out date, and the move-out
    settlement already states the interest at that same day
    (`services.move_out` passes ``moved_out_on``). So the figure here is the one
    the final bill settled on. Stated at today it would go on growing on an
    account that stopped taking service — WE-7's $150.00 at 2%, received
    2025-06-15 and closed 2026-08-15, is **$3.50** at the close and would read
    **$3.75** on 2026-10-01. Decision log 2026-10-01, `DEF-CUS-8711`.

    A closed account with no ``closed_at`` has no day to state it at, so it
    GAPS (None) — never today's date, which gate G6 keeps out of a money path.
    """
    if account.deposit_on_file == ZERO:
        return ZERO
    read = seams.resolve("customers", "deposit_interest_accrued", kind="selectors")
    if read is None or account.closed_at is None:
        return None
    answered = read(account.id, account.closed_at)
    return None if answered is None else _money(answered, "the accrued deposit interest")


def _customer_or_refuse(customer_id: Any) -> models.Customer:
    customer = models.Customer.objects.filter(tenant_id=_tenant_id(), pk=customer_id).first()
    if customer is None:
        raise errors.deny_as_not_found("BR-TEN-003")
    return customer


def _closed_positions(customer: models.Customer) -> list[DepositPosition]:
    """Every CLOSED account this customer is linked to, in account-number order.

    The linkage is `customer_accounts` and nothing else — BR-CUS-024's own
    words, *"linkage = the customer entity (`customer_accounts`)"*, and
    BR-CUS-054 closed OQ-057 onto exactly that. Matching on a NAME is what
    B18 §2.5 records as the failure this table exists to end.
    """
    tenant_id = _tenant_id()
    account_ids = list(
        models.CustomerAccount.objects.filter(tenant_id=tenant_id, customer=customer).values_list(
            "account_id", flat=True
        )
    )
    rows = (
        models.Account.objects.filter(tenant_id=tenant_id, id__in=account_ids)
        .select_related("status")
        .order_by("account_no", "id")
    )
    out: list[DepositPosition] = []
    for account in rows:
        if getattr(account.status, "code", None) != "closed":
            continue
        out.append(
            DepositPosition(
                account_id=str(account.id),
                account_no=account.account_no,
                closed_at=account.closed_at.isoformat() if account.closed_at else None,
                currency=account.currency,
                principal=_money(account.deposit_on_file, f"the deposit on {account.account_no}"),
                interest=_deposit_interest(account),
            )
        )
    return out


@require_role(SYSTEM_ADMIN, BILLING_CLERK, br_ref="BR-SHL-025")
def deposit_position(actor: Any, customer_id: Any) -> dict[str, Any]:
    """B18 §5.5.5's `GET /customers/{id}/deposit-position` — *"refundable
    deposit on any closed account"*.

    A pure read: it moves nothing and writes no `audit_log` row, because
    nothing here is a decision about money. `carry_forward_offer` below is the
    decision, and it audits.

    `total_refundable` is `None` the moment ANY position gaps. A total that
    quietly summed the readable half would be the exact understatement
    BR-CUS-057's absence causes — $150.00 presented as the answer when $153.50
    is owed — and it would foot.
    """
    customer = _customer_or_refuse(customer_id)
    positions = _closed_positions(customer)
    gaps = sorted({gap for position in positions for gap in position.gaps})
    total: Decimal | None = ZERO
    for position in positions:
        if position.refundable is None:
            total = None
            break
        total = total + position.refundable
    unavailable: list[dict[str, Any]] = []
    if GAP_DEPOSIT_INTEREST in gaps:
        unavailable.append(DEPOSIT_INTEREST_NOT_READABLE)
    if GAP_NOT_NET_OF_SETTLEMENT in gaps:
        unavailable.append(DEPOSIT_NOT_NET_OF_SETTLEMENT)
    return {
        "customer_id": str(customer.id),
        "customer_no": customer.customer_no,
        "currency": positions[0].currency if positions else None,
        "positions": [position.serialize() for position in positions],
        "total_refundable": _pair(total),
        "readable": total is not None,
        "gaps": gaps,
        "unavailable": unavailable,
    }


# ═══════════════════════════════════════════════════════════════════════════
# MOVE-IN STEP 4 — THE CARRY-FORWARD OFFER (task 5.5), `strong` MATCH ONLY
# ═══════════════════════════════════════════════════════════════════════════
REFUSAL_NO_STORED_MATCH = "no_identity_match_recorded"
REFUSAL_TIER_NOT_STRONG = "identity_match_not_strong"


def _stored_match(customer: models.Customer) -> dict[str, Any] | None:
    """The tier a HUMAN recorded against this customer, or None.

    **BR-CUS-089 says the tier is STORED, so it is READ — never taken as a
    parameter and never computed.** A `tier=` argument on this function would
    let a caller assert `strong` and move money, which is the rule inverted.

    `service_requests` is the only store: `match_tier` + `match_basis` +
    `match_confirmed_by` + `match_confirmed_at`, written by
    `service_request_service.link_customer` and by nothing else. The most
    recently CONFIRMED one wins — a later confirmation is a human looking again,
    which is what BR-CUS-089's confirmer column is for.

    ✅ **A SECOND STORE JOINED IT ON 2026-08-31 — CR-056 W3, migration 0036.**
    This docstring used to end *"a move-in that did not come from a service
    request has no stored tier at all, and is refused rather than defaulted"*,
    and that sentence described a real hole: **an account opened at the counter
    could never carry a returning customer's deposit**, however well the clerk
    had identified them, because the only place a tier could be stored was an
    application form. `customer_accounts` now carries the same four columns, and
    `services.link_customer` writes them when the ruled criteria are met with a
    human at the door.

    ⛔ **AND THE GATE IS NOT WEAKENED BY THAT — IT IS BETTER EVIDENCED.** A tier
    on a service request is a human's typed judgement that nothing checks (the
    request form still collects no date of birth — `DEF-638(2)`). A tier on a
    `customer_accounts` row was COMPUTED from `BR-CUS-089`'s three signed facts
    and then committed by a named person. Both are read; neither is defaulted;
    an absent tier still refuses.

    The most recent CONFIRMED tier across BOTH stores wins — a later
    confirmation is a human looking again, which is what BR-CUS-089's confirmer
    column is for.
    """
    tenant_id = _tenant_id()
    found: list[dict[str, Any]] = []

    row = (
        models.ServiceRequest.objects.filter(
            tenant_id=tenant_id,
            matched_customer=customer,
            match_tier__isnull=False,
            match_confirmed_at__isnull=False,
        )
        .order_by("-match_confirmed_at", "-id")
        .first()
    )
    if row is not None:
        found.append(
            {
                "tier": row.match_tier,
                "basis": row.match_basis,
                "confirmed_at": row.match_confirmed_at,
                "confirmed_by": (
                    str(row.match_confirmed_by_id) if row.match_confirmed_by_id else None
                ),
                "source": "service_request",
                "source_no": row.request_no,
            }
        )

    link = (
        models.CustomerAccount.objects.filter(
            tenant_id=tenant_id,
            customer=customer,
            match_tier__isnull=False,
            match_confirmed_at__isnull=False,
        )
        .select_related("account")
        .order_by("-match_confirmed_at", "-id")
        .first()
    )
    if link is not None:
        found.append(
            {
                "tier": link.match_tier,
                "basis": link.match_basis,
                "confirmed_at": link.match_confirmed_at,
                "confirmed_by": (
                    str(link.match_confirmed_by_id) if link.match_confirmed_by_id else None
                ),
                "source": "account_link",
                # B14 rule 31 — the ACCOUNT NUMBER, never the row id. This
                # string reaches a screen through the carry-forward payload.
                "source_no": link.account.account_no,
            }
        )

    if not found:
        return None
    best = max(found, key=lambda entry: entry["confirmed_at"])
    return {**best, "confirmed_at": best["confirmed_at"].isoformat()}


@require_role(SYSTEM_ADMIN, BILLING_CLERK, br_ref="BR-SHL-025")
def carry_forward_offer(actor: Any, customer_id: Any) -> dict[str, Any]:
    """S19 step 4's deposit carry-forward — TC-MVI-2 and TC-MVI-3, one function.

    B18 §5.5.4: *"From a prior closed account of the **same customer**.
    **Requires a strong identity match, because money moves**."*

    **TC-MVI-2** — a returning customer with $153.50 on a closed account and a
    `strong` stored tier: the carry is **OFFERED**, the DEPOSIT cell reads
    `carried $153.50`, and both gaps ride the payload.
    **TC-MVI-3** — a weak (or probable, or absent, or unconfirmed) tier: the
    carry is **REFUSED with its reason**, `amount` is `None`, and no figure is
    served at all. *"Money never moves on a weak match"* — and a refused offer
    that still printed the figure would be an invitation to type it in by hand.

    The gate runs BEFORE the position is read, deliberately: a weak match must
    not even learn what the customer holds.

    CLAUDE.md rule 7 — both branches write `audit_log`. A refusal is the
    decision that $153.50 stayed where it was, and B18's KPI strip counts
    `DEPOSITS TO CARRY OVER`; a refusal leaving no trace is a figure nobody can
    reconcile.
    """
    customer = _customer_or_refuse(customer_id)
    match = _stored_match(customer)

    if match is None or match["tier"] != TIER_STRONG:
        refusal = {
            "code": (REFUSAL_NO_STORED_MATCH if match is None else REFUSAL_TIER_NOT_STRONG),
            "br_ref": "BR-CUS-089",
            "tier": None if match is None else match["tier"],
            "detail": (
                (
                    "No identity match has been recorded against this customer by anybody. "
                    "BR-CUS-089 moves money only on a STORED `strong` tier with a confirmer, "
                    "and this module never computes one, so there is nothing to act on."
                )
                if match is None
                else (
                    f"The recorded identity match is `{match['tier']}`, not `strong`. "
                    "BR-CUS-089: money moves only on a strong match. Nothing is carried and no "
                    "figure is shown — a refused offer that still printed the amount would "
                    "invite it being typed in by hand."
                )
            ),
        }
        decision = {
            "customer_id": str(customer.id),
            "offered": False,
            "amount": _pair(None),
            "refused": refusal,
            "match": match,
            "positions": [],
            "gaps": [GAP_NO_MATCH_RULE],
            "unavailable": [CARRY_FORWARD_NO_MATCH_RULE],
        }
        _audit(actor, "customer.deposit_carry_forward.refused", customer.id, after=decision)
        return decision

    positions = [position for position in _closed_positions(customer) if position.principal > ZERO]
    gaps = sorted({gap for position in positions for gap in position.gaps})
    amount: Decimal | None = ZERO
    for position in positions:
        if position.refundable is None:
            amount = None
            break
        amount = amount + position.refundable

    unavailable: list[dict[str, Any]] = [CARRY_FORWARD_NO_ACCEPT_PATH, CARRY_FORWARD_NO_MATCH_RULE]
    if GAP_DEPOSIT_INTEREST in gaps:
        unavailable.append(DEPOSIT_INTEREST_NOT_READABLE)
    if GAP_NOT_NET_OF_SETTLEMENT in gaps:
        unavailable.append(DEPOSIT_NOT_NET_OF_SETTLEMENT)

    decision = {
        "customer_id": str(customer.id),
        # An offer exists whenever a strong match found a closed account holding
        # a deposit — even where the FIGURE gaps. Collapsing "offered with no
        # readable figure" into "not offered" would hide a returning customer's
        # money behind an engine that is somebody else's to build.
        "offered": bool(positions),
        "amount": _pair(amount),
        "currency": positions[0].currency if positions else None,
        "refused": None,
        "match": match,
        "positions": [position.serialize() for position in positions],
        # B18 §5.5.2's DEPOSIT cell, in the accent: `carried $153.50`.
        "deposit_cell": (None if amount is None else f"carried ${_display(amount)}"),
        "gaps": gaps + [GAP_NO_ACCEPT_PATH],
        "unavailable": unavailable,
    }
    _audit(actor, "customer.deposit_carry_forward.offered", customer.id, after=decision)
    return decision


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-CUS-004@0dfe1a88 · US-CUS-007@0dfe1a88
#         (04-docs/02-decisions/18-cr030-onboarding-design.md §5.3.4 · §5.5.3 ·
#          §5.5.4 · §5.5.5 · §5.5.6 · W5 tasks 5.4/5.5 ·
#          04-docs/05-modules/03-customers/02-business-rules.md BR-CUS-023/024/
#          025/050/054/057/089 · 04-docs/05-modules/06-rating/02-business-rules.md
#          BR-RAT-043/069/076/112 · 12-governance/01-open-questions.md OQ-055
#          (CLOSED) · 12-governance/02-decision-log.md 2026-08-21 CR-022)
# generated: 2026-08-25 by the CR-030 W5 eligibility + deposit-carry lane (R2)
# checklist: A✔ B✔ C✔ D=deferred(no-API-half) E=deferred(no-frontend-half) F✔ G✔ H=deferred(PO 2026-08-09)
#         ⚠ ONE LINE, and it has to be: G3 reads `checklist:(.*)` with a
#         SINGLE-line regex, so a wrapped list reports "missing letters
#         D,E,F,G,H" — which is what this trailer did on its first run.
#         D: ⚠ **CLOSED SINCE, AND THE MARK IS LEFT AT `deferred` DELIBERATELY
#         — SEE E (`DEF-2348`, 2026-09-03).** This read *"`GET /discount-
#         programmes` and `GET /customers/{id}/deposit-position` have no
#         route"*. Both are mounted now: `apps/customers/api.py:1407` serves
#         `deposit-position` and `:1408` serves `deposit-carry-forward`, each
#         `@permission_classes([AdminOrClerk])`.
#         E: **STILL TRUE, AND IT IS NOW THE WHOLE GAP (`DEF-2351`).** Measured
#         2026-09-03: NO file under `07-frontend/src` calls either route —
#         `deposit-position`, `deposit-carry-forward`, `carryForward` and
#         `depositPosition` all return zero hits outside the locale
#         catalogues. So the API half landed and the product still cannot
#         offer a returning customer the money it is holding: hard-won law 2,
#         which is why D stays `deferred` rather than ticking on a route
#         nothing reaches.
# gates: ruff✔ black✔ · tests/test_w5_eligibility_and_deposit_carry.py
#        (22 passed, 1 skipped — the RLS case needs live Postgres)
# exceptions: (1) ⚠ **CLOSED — AND IT READ AS OPEN FOR DAYS AFTER IT SHUT
#         (`DEF-2348`, corrected 2026-09-03).** This said *"NOT ON THE G7 GLOB
#         LIST and NO ROW IN 12-governance/09-human-review-ledger.md … REPORTED
#         for the daily PO batch"*, which was true when written on 2026-08-25:
#         enrolling a file in either is a process event a lane may not take
#         alone (B12 r2). The lanes that own those files then took it. This
#         file is `10-scripts/gates/human_owned.txt` line 210 and it has a row
#         in `12-governance/09-human-review-ledger.md`, so G7 reads the marker
#         and an edit here owes that row an update — which this correction
#         makes. The staleness failed SAFE, which is exactly why no gate could
#         see it: G7 asks whether a marked file is guarded, never whether the
#         file's own prose agrees.
#         (2) NO MIGRATION WAS WRITTEN. `account_discounts` (B18 §5.5.5, §6.3)
#         duplicates the built `discount_enrolments`, and a bill run reads only
#         the latter — see the module docstring. Filed as a DEFECT against B18
#         (change process §1) and REPORTED, because 12-governance/* is outside
#         this lane's write scope.
#         (3) THREE CROSS-MODULE READS/WRITES ARE MADE THROUGH `seams.resolve`
#         FROM A FILE G20 DOES NOT HARVEST (it reads apps/*/seams.py and
#         apps/*/<neighbour>_seam.py only): `apps.rating.selectors.
#         discount_list`, `apps.rating.discount_services.
#         discount_rules_for_account` and `apps.rating.discount_services.
#         enrol_account`. Publishing them in apps/customers/seams.py is
#         REPORTED — that file is outside this lane's write scope.
#         (4) `enrol_account` WAS `@require_role(SYSTEM_ADMIN)` AND A MOVE-IN IS
#         A BILLING_CLERK's JOB. The refusal passed through unchanged; rating
#         owned that rule. RESOLVED 2026-10-05 by PO ruling (decision log
#         "FOUR PO RULINGS IN ONE REPLY" (2), option (b)): rating admits a
#         Billing Clerk on `enrol_account` (lane RULINGS, 2.539.0).
#         (5) THE SURFACE-DEBT COUNT. `10-scripts/gates/surface_debt.txt` has no
#         `customers` line, i.e. the module is at zero, and this file's
#         D=deferred/E=deferred marks are the first two on it. G23 attributes
#         them to US-CUS-004/US-CUS-007, both of which other files already mark
#         reached — so the count does not move today. REPORTED anyway, because
#         the sentence beside a number is where the judgement lives and this
#         lane cannot write it.
