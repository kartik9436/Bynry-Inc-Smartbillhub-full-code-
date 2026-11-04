# ── Trace ──────────────────────────────────────────────
# Change:   CR-056 W2 tasks 12, 13 and 14 — reconcile the two places identity
#           already lives, recognise a returning customer on the signed
#           criteria, and refuse a weak one BY NAME.
#           ⚠ CR-056 W2b (2026-09-01) — IDENTITY IS PER KIND. A person keeps the
#           three-part test below; a COMPANY is matched on its name and its Tax
#           ID, because a company has no date of birth and the signed rule read
#           literally made every one of them permanently unmatchable.
# Rules:    BR-CUS-1022 (identity is per kind — a person by SSN, licence or
#           phone, a company by its Tax ID; PO 2026-09-01) ·
#           BR-CUS-089 (the tier and its confirmer are STORED; money moves only
#           on `strong` — and the CRITERIA are ruled: **NAME + DATE OF BIRTH +
#           ONE GOVERNMENT ID**, PO 2026-08-25 closing OQ-364, and NARROWED
#           onto PERSONS by the decision log of 2026-09-01) ·
#           BR-CUS-092 (SSN and driving licence captured, app-layer encrypted,
#           last four only on every read path) · BR-CUS-019 (the duplicate
#           check is ADVISORY — staff decides; matches resolve by LINKING) ·
#           BR-CUS-054 (the customer entity and its N:M account link) ·
#           OQ-016 CLOSED (app-layer encryption, PO R6) · B2 §6 ·
#           CLAUDE.md hard rule 1 (tenant scoping) · hard rule 7 (every money
#           action writes audit_log) · hard-won law 1 (a comment claiming a
#           guarantee is not the guarantee)
# Tests:    06-backend/tests/test_cr056_w2_customer_identity.py
# Impacts:  apps/customers/services.link_customer (the one door that writes a
#           customer→account link) · apps/customers/discounts._stored_match
#           (the deposit carry-forward's gate) · apps/customers/models.Customer
#           (the four identity columns + three blind indexes, migration 0036)
# ───────────────────────────────────────────────────────
"""Recognising a returning customer — and refusing to, by name.

HUMAN-OWNED · HUMAN-REVIEW-PENDING — this file decides whether the person at
the counter is somebody the utility already holds money for, which is
CLAUDE.md's 🔒 *rating math* / *money rounding* neighbourhood by consequence
rather than by arithmetic: a `strong` verdict here is what lets
`discounts.carry_forward_offer` move a **$153.50** deposit (WE-7/GT-23 ❄️).
AI-authored 2026-08-31 under the PO ruling of 2026-08-09 (*"AI will do it; we
will review it later as human"*). Row in
`12-governance/09-human-review-ledger.md`.

⚠ **NOT ON THE G7 GLOB LIST (`10-scripts/gates/human_owned.txt`), AND THIS LANE
DID NOT PUT IT THERE.** `G53` names this file for exactly that and is right to:
the marker is declared, the review-ledger row is open, and no glob matches the
path, so `G7` does not watch it. **Adding one is a PROCESS EVENT and the PO's
call, not a lane's** — the gate says so in its own words, and `OQ-441` is the
ruling behind it (PO 2026-08-30, on the fifth occurrence: *"each time we've
fixed the instance, not the cause"*), closed with **the check must FAIL and name
the file, never silently append**. So the discrepancy is STATED here and
REPORTED, which is the posture `apps/customers/discounts.py` already takes for
the same gap. A marker no gate reads is hard-won law 1; this paragraph says so
rather than implying the guard exists.

════════════════════════════════════════════════════════════════════════════
A MATCHER IS A MONEY FEATURE, AND THE CODE SAID SO BEFORE THIS FILE EXISTED
════════════════════════════════════════════════════════════════════════════
Recognition was **deliberately absent** from this product, and both of the
places that refused it said why in their own words:

  * `service_request_service.suggest_customer_matches` raises rather than
    guessing: *"A matcher built now would be matching on fields that do not
    exist, and BR-CUS-089 lets a `strong` match MOVE MONEY … so a tier derived
    from weaker evidence is a money bug."* ⚠ **The first half of that sentence
    expired on 2026-09-15** — the fields exist on a service request now — and the
    stub was reworded the same day. The money half is unchanged and is the half
    that still refuses.
  * `service_request_service.link_customer`: *"`tier` is the clerk's, not
    ours … there is no automatic matcher here."*

**Neither refusal is withdrawn lightly and neither is withdrawn by this file
alone.** Two things changed:

  1. **The criteria were RULED.** `OQ-364` closed on 2026-08-25, PO verbatim:
     *"Name + date of birth + one government ID"* — the strictest of the three
     readings offered, chosen because the PO took refusing some genuine
     returners over the risk of handing a stranger somebody else's deposit.
     Signed into `BR-CUS-089`.
  2. **The evidence now exists.** That ruling was **signed and inert** — the
     rule's own row says so: *"the ruling names evidence this product never
     collects … until the request form captures a DOB, no match can be assessed
     against them."* `customers 0036` (CR-056 task 11) puts a date of birth, a
     Social Security number, a driving licence and a phone on the customer, each
     of the three identifiers encrypted with a blind index beside it.

So this file computes the ruled criteria and NOTHING ELSE. It does not invent a
threshold, it does not score, it does not fuzzy-match a name, and it emits no
tier the PO did not define.

════════════════════════════════════════════════════════════════════════════
CR-056 W2b — IDENTITY IS PER KIND, AND THE SIGNED RULE IS NARROWED NOT REVERSED
════════════════════════════════════════════════════════════════════════════
**PO ruling 2026-09-01, verbatim:** *"Customer can be person or company - in
case of person , if we have SSN, or DL or Phone number, we create the Customer
ID and attached these to custoemr ID ; if it is Company then we ask for Tax
ID"*.

⚠ **IT COLLIDED WITH `BR-CUS-089` AND THE COLLISION IS STATED RATHER THAN
SMOOTHED (law 13).** That rule is signed and verbatim — *NAME + DATE OF BIRTH +
ONE GOVERNMENT ID* — and **a company has no date of birth.** Read literally, the
signed rule made every company permanently unmatchable, which nobody intended.
The decision log of 2026-09-01 narrows it: **`BR-CUS-089` is a rule about
PERSONS and stands unchanged for them; a company is matched on its Tax ID**
(`BR-CUS-1022`).

| kind | strong when | never asked for |
|---|---|---|
| **person** | name + date of birth + (SSN or driving licence) | a Tax ID |
| **company** | name + Tax ID | a date of birth, an SSN, a driving licence |

**NEITHER KIND BORROWS THE OTHER'S CRITERIA**, and neither is asked for the
other's evidence. Asking for both and leaving one blank turns a rule into a
habit, and the blank field eventually gets filled with something.

**A PHONE IS ON BOTH LISTS AND IS A GOVERNMENT IDENTIFIER FOR NEITHER.** It is
the utility's contact handle for whoever it bills, and `customer_list`'s search
reads its blind index, but a phone hit only ever SURFACES a candidate.

**THE KIND MUST BE STATED.** Evidence naming no kind is not weak evidence, it is
unjudgeable evidence: the test to apply depends on the answer, and a guess of
`person` would judge a business by a date of birth it does not have and file its
Tax ID nowhere. `has_any()` answers False for it and the door refuses.

**TWO THINGS THIS WAVE DID NOT DECIDE, and both are stubbed rather than
chosen** (prime directive): whether a company also gets a date-of-birth
equivalent, an INCORPORATION DATE (`OQ-1241`), and whether a SOLE TRADER is a
person or a company (`OQ-1242`). A door that supplies either meets
`NotImplementedError` naming the question.

════════════════════════════════════════════════════════════════════════════
WHAT `strong` MEANS HERE, EXACTLY — AND WHY `probable` IS NEVER EMITTED
════════════════════════════════════════════════════════════════════════════
**FOR A PERSON, `strong` = the name agrees AND the date of birth agrees AND at
least one government identifier agrees.** All three. That is `BR-CUS-089`'s
sentence with nothing added to it and nothing taken away. **For a company it is
the name and the Tax ID**, which is the ruling above with nothing added either.

`BR-CUS-089`'s tier vocabulary is closed and holds three words — `strong` ·
`probable` · `weak` — and **this matcher emits only two of them.** The ruling
defines what earns `strong`; it defines nothing at all about where `probable`
begins, and a machine that started handing out `probable` would be minting a
second threshold nobody ruled. `probable` stays a HUMAN's word: a clerk may
still record it through `service_request_service.link_customer`, and it moves
no money there either.

**A `phone` match on its own is `weak`.** CR-056's ruling R3 names the phone as
identity evidence and this file indexes it, so a phone hit is what SURFACES a
candidate for a human to look at — but `BR-CUS-089` says *one government ID*,
and a telephone number is not one. Treating it as one would be reading a
reconstructed ruling as licence to loosen a signed one.

**Names are compared EXACTLY, case-folded, with whitespace collapsed — never
fuzzily.** CR-056 §4's own example is `A. Kulkarni` against `Ajinkya Kulkarni`,
and every fuzzy rule that would unite those two also unites two real strangers.
Case-folding is the posture `customers.external_ref` and
`premises_owners.name` already take (`CUST-118` and `cust-118` are one
customer in every legacy export anyone will hand us); anything beyond it is an
unruled threshold.

════════════════════════════════════════════════════════════════════════════
TASK 12 — THE TWO PLACES IDENTITY ALREADY LIVED, RECONCILED NOT DUPLICATED
════════════════════════════════════════════════════════════════════════════
Identity did exist before today, in two places that could not see each other:

| where | what it holds | whose row is it |
|---|---|---|
| `service_requests.ssn` | the full SSN, encrypted (BR-CUS-092, 2026-08-27) | ONE application |
| `contacts.dob` + `contacts.gov_id_last4` | a date of birth and FOUR DIGITS | ONE account |

Neither can answer *"is this the same person?"* across a utility:

  * A **service request** is one application. The applicant who came back three
    years later filed a different one, and nothing joins them.
  * A **contact** hangs off `accounts.account_id` (B2 §2 declares that column
    and r9 #1 flags re-homing contacts onto the customer entity as an *"Eng-Lead
    disposition"*, unresolved). So the same landlord across twelve accounts is
    twelve contact rows.
  * `gov_id_last4` is **four digits and cannot be matched on**. Four digits
    collide roughly once in ten thousand, and BR-CUS-092(c) is the reason it is
    only four: *"every read path renders last four only"*. It is a DISPLAY
    projection, not a key.

**So this file reconciles rather than duplicates, and the direction is
inward.** `reconcile_from_contact()` reads the account's own contact row and
offers its `dob` as the customer's date of birth **only where the customer has
none** — never overwriting, never inventing, and never copying `gov_id_last4`
anywhere (four digits stored as an identifier would be an identifier that
cannot identify). `evidence_from_service_request()` does the same for the
request's encrypted SSN. Both are lifts of facts a human already typed, into
the one row that spans a person's whole relationship with the utility.

⚠ **NOTHING HERE DELETES OR MOVES EITHER SOURCE.** `service_requests.ssn` is
the applicant's declaration on one application and stays an immutable part of
that record; `contacts` keeps its own columns because re-homing a live PII
table's parent is an Eng-Lead disposition and not a side effect of a matcher.

════════════════════════════════════════════════════════════════════════════
HOW A RANDOMISED COLUMN IS SEARCHED AT ALL
════════════════════════════════════════════════════════════════════════════
It is not. `core.crypto.EncryptedTextField.get_lookup` refuses every lookup but
`__isnull`, and it is right to: the scheme is randomised, so
`filter(ssn="123456789")` matches nothing and looks exactly like *"no such
customer"* — a silently wrong answer on the one path that moves somebody else's
money.

Every probe in this file therefore goes through
`core.crypto.blind_index_candidates(value, context=…)`, which returns ONE token
per configured key so rows written before a key rotation stay findable, and the
query is `filter(ssn_bidx__in=tokens)`. The tokens are keyed HMACs: they leak
equality — which is precisely what matching means — and nothing else.

════════════════════════════════════════════════════════════════════════════
WHAT THIS FILE NEVER DOES
════════════════════════════════════════════════════════════════════════════
  * **It never links.** `recognise()` returns a verdict; `services.link_customer`
    acts on it, audits it, and is the only writer (LAW 0: services is the sole
    writer, and `customer_accounts` is written in exactly one place).
  * **It never moves money.** `discounts.carry_forward_offer` still requires a
    tier that is STORED with a confirmer. What changed is that a strong tier can
    now be stored by a door other than a service request, and that it is stored
    beside a `basis` naming the three facts that agreed.
  * **It never returns a full identifier.** Every candidate carries
    `crypto.last_four()` projections and the customer's number and name —
    BR-CUS-092(c): *"the full value is never in a list response, an export, a
    log line or an audit `details` blob"*.
  * **It never widens a queryset past the tenant.** Every read filters
    `tenant_id=_tenant_id()` (CLAUDE.md hard rule 1); RLS `FORCE` is the second
    lock and neither is the excuse for skipping the other.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any

from django.db.models import Q

from apps.customers import models
from core import crypto, errors

# ═══════════════════════════════════════════════════════════════════════════
# THE VOCABULARY — BR-CUS-089's, copied deliberately rather than imported
# ═══════════════════════════════════════════════════════════════════════════
#: `service_request_service.MATCH_TIERS` and `discounts.MATCH_TIERS` already
#: hold this tuple. It is copied a third time for the reason `discounts.py`
#: gives for its own copy — so this module does not depend on the request
#: surface existing — and the three are asserted equal in the test file, which
#: is what stops them drifting.
MATCH_TIERS: tuple[str, ...] = ("strong", "probable", "weak")

#: The ONE tier that may move money (BR-CUS-089).
TIER_STRONG = "strong"
#: Everything this matcher can say that is not `strong`. See the module
#: docstring: `probable` is a human's word and is never emitted here.
TIER_WEAK = "weak"

#: The two identifiers `BR-CUS-092` names, and the two that satisfy
#: `BR-CUS-089`'s *"one government ID"* FOR A PERSON. A phone is NOT one of
#: them, and neither is a company's Tax ID — see `COMPANY_ID_FIELDS`.
GOVERNMENT_ID_FIELDS: tuple[str, ...] = ("ssn", "driving_licence")

#: The identifier a COMPANY is matched on (`BR-CUS-1022`, PO 2026-09-01).
COMPANY_ID_FIELDS: tuple[str, ...] = ("tax_id",)

#: B2 r9 #1's own two words for `customers.kind`. The column already existed;
#: what changed on 2026-09-01 is that it now DECIDES something.
KIND_PERSON = "person"
KIND_COMPANY = "company"
KINDS: tuple[str, ...] = (KIND_PERSON, KIND_COMPANY)

#: `crypto_context` binds a ciphertext AND its blind-index token to the column
#: it was written for, so a value cannot be lifted between columns. The literal
#: must match `models.Customer`'s field declarations exactly — a test asserts it
#: rather than trusting this comment (hard-won law 1).
CRYPTO_CONTEXT: dict[str, str] = {
    "ssn": "customers.ssn",
    "driving_licence": "customers.driving_licence",
    "phone": "customers.phone",
    "tax_id": "customers.tax_id",
}

#: The blind-index column beside each encrypted one.
BIDX_COLUMN: dict[str, str] = {
    "ssn": "ssn_bidx",
    "driving_licence": "driving_licence_bidx",
    "phone": "phone_bidx",
    "tax_id": "tax_id_bidx",
}

#: ══════════════════════════════════════════════════════════════════════════
#: THE SAME TWO TABLES FOR `service_requests` — BR-CUS-092(a), PO 2026-09-15
#: ══════════════════════════════════════════════════════════════════════════
#: An APPLICATION now carries an app-layer-encrypted driving licence with a
#: blind index beside it, exactly as a CUSTOMER has since `customers 0036`.
#:
#: ⚠ **THEY ARE SEPARATE TABLES BECAUSE THE AAD IS PER COLUMN AND MUST BE.**
#: `core/crypto.py` binds a ciphertext to the column it was written for, so a
#: value lifted out of `customers.driving_licence` and dropped into
#: `service_requests.drivers_licence` RAISES rather than decrypting. Reusing one
#: context literal for both would throw that away for the sake of one fewer dict.
#:
#: ⚠ **AND THE TWO COLUMNS ARE SPELLED DIFFERENTLY, WHICH IS RECORDED RATHER
#: THAN TIDIED.** `customers.driving_licence` shipped 2026-08-31;
#: `service_requests.drivers_licence` is what the PO ruling of 2026-09-15 and
#: `BR-CUS-092`'s amendment both name. Renaming either moves every citation in
#: every register, docstring and test at once, which is the mass shared-file
#: rewrite CLAUDE.md's law 11 exists to prevent. `from_payload` already reads
#: both spellings; `service_request_service.ALIASED_FIELDS` refuses the wrong one
#: BY NAME and says which to use.
#:
#: ⚠ **`ssn` IS NOT HERE, AND THE ABSENCE IS THE TRUTH RATHER THAN AN
#: OVERSIGHT.** `service_requests.ssn` has carried no blind index since it was
#: built on 2026-08-27 — its own docstring says the index *"is added by the lane
#: that builds the matcher"* — and nothing has added one. Putting it in this
#: table without the column would make `request_blind_index` write to a field
#: that does not exist.
REQUEST_CRYPTO_CONTEXT: dict[str, str] = {
    "drivers_licence": "service_requests.drivers_licence",
}

REQUEST_BIDX_COLUMN: dict[str, str] = {
    "drivers_licence": "drivers_licence_bidx",
}

#: Lane CF-1 (2026-10-18) — a service request's CO-APPLICANT card carries an
#: SSN and a driving licence (Move-in's co-owner card, decision log
#: 2026-10-18), held as `core.crypto` CIPHERTEXT inside
#: `service_requests.co_applicants`. The contexts live HERE, with every other
#: identifier context, so the capture module names none and offers no general
#: encrypt (`tests/test_br_cus_092_licence_and_dob_capture.py` proof 2d): the
#: two functions below take a CARD and touch exactly these two keys.
CO_APPLICANT_CRYPTO_CONTEXT: dict[str, str] = {
    "ssn": "service_requests.co_applicants.ssn",
    "driving_licence": "service_requests.co_applicants.driving_licence",
}


def seal_co_applicant(card: dict[str, Any]) -> dict[str, Any]:
    """The card with its SSN and licence ENCRYPTED (blank → `None`)."""
    out = dict(card)
    for field, context in CO_APPLICANT_CRYPTO_CONTEXT.items():
        value = out.get(field)
        value = None if value in (None, "") else str(value).strip()
        out[field] = crypto.encrypt(value, context=context)
    return out


def open_co_applicant(card: dict[str, Any]) -> dict[str, Any]:
    """The card with its SSN and licence DECRYPTED — for the read's last-four
    projection and the one carry into the move-in, never for a payload."""
    out = dict(card)
    for field, context in CO_APPLICANT_CRYPTO_CONTEXT.items():
        out[field] = crypto.decrypt(out.get(field), context=context)
    return out


def request_blind_index(cleaned: dict[str, Any]) -> dict[str, Any]:
    """The `*_bidx` columns derived from a cleaned service-request payload.

    Returns `{}` when the payload names no encrypted identifier, so a caller can
    always splat it. Given one, returns the token column beside it — including
    `None` when the identifier is being CLEARED, because a stale token left
    behind would go on matching a value the row no longer holds.

    ⚠ **THE CIPHERTEXT AND THE TOKEN ARE WRITTEN IN ONE ACT, WHICH IS WHY THIS
    IS A FUNCTION AND NOT TWO LINES AT THE CALL SITE** — `set_identifier` says
    the same thing for a customer. A ciphertext with no token is a value the
    matcher cannot see: the applicant would be unfindable and every test would
    pass. A token with no ciphertext is an equality oracle over a value nobody
    can read.

    ⚠ **IT IS DELIBERATELY NOT IN THE AUDIT BLOB.** The caller sets these
    columns on the instance AFTER building `before`/`after` from the cleaned
    payload, so `audit_log` records the identifier's MASK and not a keyed token
    beside it. The token is not the value, but it is not a fact a reviewer of the
    trail can use either.

    ⚠ **THE CALLER MUST STILL SAVE.** Like `set_identifier`, this is not a
    write: an identity change belongs inside the same transaction as the row it
    identifies.
    """
    out: dict[str, Any] = {}
    for field, context in REQUEST_CRYPTO_CONTEXT.items():
        if field not in cleaned:
            continue
        value = cleaned[field]
        value = None if value in (None, "") else str(value).strip()
        out[REQUEST_BIDX_COLUMN[field]] = crypto.blind_index(value, context=context)
    return out


#: ══════════════════════════════════════════════════════════════════════════
#: WHAT EACH KIND MAY BE ASKED FOR — the capture rule, in one table
#: ══════════════════════════════════════════════════════════════════════════
#: The PO's ruling of 2026-09-01 names different evidence for each kind, and the
#: decision log adds the reason the two lists may not simply be unioned:
#: *"asking for both and leaving one blank turns a rule into a habit, and the
#: blank field eventually gets filled with something."*
#:
#: A phone is on BOTH lists and is on neither government-id list. It is the
#: utility's contact handle for whoever it is billing, a company included, and
#: `customer_list`'s phone search leg reads its index — but it can never make a
#: match strong for either kind, because `BR-CUS-089` says *one government ID*
#: and a company is matched on its Tax ID.
KIND_IDENTIFIER_FIELDS: dict[str, tuple[str, ...]] = {
    KIND_PERSON: ("ssn", "driving_licence", "phone"),
    KIND_COMPANY: ("tax_id", "phone"),
}

#: The non-identifier facts each kind may present. A company has NO DATE OF
#: BIRTH — that is the whole collision this wave resolves — and whether it gets
#: the equivalent (an incorporation date) is `OQ-1241`, open.
KIND_DATED_FIELDS: dict[str, tuple[str, ...]] = {
    KIND_PERSON: ("date_of_birth",),
    KIND_COMPANY: (),
}

#: ══════════════════════════════════════════════════════════════════════════
#: WHAT IS ENOUGH TO **CREATE** A CUSTOMER NUMBER — `BR-CUS-1023`, PO 2026-09-01
#: ══════════════════════════════════════════════════════════════════════════
#: **PO verbatim:** *"Customer ID - minimum name and one ID - minimum - please
#: make this rule and apply"*.
#:
#: ⚠ **THIS IS NOT `KIND_IDENTIFIER_FIELDS` AND THE TWO MUST NOT BE MERGED.**
#: That table answers *what may this kind be ASKED for* — the CAPTURE rule. This
#: one answers *what is enough to MINT A NUMBER* — the CREATION rule. They differ
#: in exactly one cell and the difference is the PO's own words: a company is
#: asked for its Tax ID, so a business presenting **only a phone** is capturable
#: and is NOT creatable. A phone is the handle of whoever answers it; for a
#: business that is a receptionist, and a Customer # minted on it names nobody.
#:
#: ⚠ **AND NEITHER OF THEM IS THE MATCHING RULE (`tier_for`).** The decision log
#: of 2026-09-01 states the distinction and states that somebody will collapse it
#: within a week: **a phone alone CREATES and a phone alone is a WEAK match.**
#: Both are true at once. Unify them and you either refuse a customer the PO said
#: to create, or you move a **$150.00** deposit on a telephone number.
CREATE_IDENTIFIER_FIELDS: dict[str, tuple[str, ...]] = {
    KIND_PERSON: ("ssn", "driving_licence", "phone"),
    KIND_COMPANY: ("tax_id",),
}

#: ══════════════════════════════════════════════════════════════════════════
#: WHAT IS ENOUGH TO **REUSE** A NUMBER ALREADY ON FILE — `BR-CUS-1024`
#: ══════════════════════════════════════════════════════════════════════════
#: **PO verbatim (2026-09-01, `CR-058` ruling 0):** *"During regular and master
#: account creation process - we check whether we ahve mathicng customer ID, if
#: yes, we use it if no we create it, given we have identify atleast 1"*.
#:
#: ⚠ **THIS IS THE THIRD TABLE AND IT IS NOT EITHER OF THE OTHER TWO.** There are
#: now three questions and they have three different answers:
#:
#:   * `CREATE_IDENTIFIER_FIELDS` — *may a number be MINTED?* A phone counts.
#:   * **this table** — *is a number ALREADY ON FILE?* A phone does NOT count.
#:   * `tier_for` — *may MONEY follow it?* The signed `strong` test, unchanged.
#:
#: **A PHONE CREATES AND MAY NOT REUSE, AND THE ASYMMETRY IS THE POINT.** Minting
#: a spare row on a shared household line costs a merge later; REUSING somebody
#: else's row on one hands a stranger an existing customer's file, their history
#: and their deposit position. The repo has said three times over that a phone is
#: nobody's government identifier (`GOVERNMENT_ID_FIELDS`, `BR-CUS-089`,
#: `BR-CUS-1022`); this is the fourth place it decides something.
#:
#: **AND IT IS NARROWER THAN `tier_for` IN THE OTHER DIRECTION** — it does not
#: ask for a date of birth. That is deliberate and it is what `DEF-2587` cost:
#: a landlord giving a name and a Social Security number at three buildings was
#: written to the database three times over one Social Security number, because
#: every door used the MONEY test to answer a question about ROW COUNT.
REUSE_ID_FIELDS: dict[str, tuple[str, ...]] = {
    KIND_PERSON: GOVERNMENT_ID_FIELDS,
    KIND_COMPANY: COMPANY_ID_FIELDS,
}

# ── the named facts a verdict is built from, so no caller compares strings ──
FACT_NAME = "name"
FACT_DOB = "date_of_birth"
FACT_SSN = "ssn"
FACT_LICENCE = "driving_licence"
FACT_PHONE = "phone"
FACT_TAX_ID = "tax_id"

# ── the named refusals. A weak case refuses BY NAME, never silently. ────────
#: ── `BR-CUS-1023` — why no Customer # was minted. NOT an error code: the
#: account opened, and this names the one thing that was missing so a clerk can
#: supply it. The `message_key` beside each is the clerk's sentence, and it
#: carries no rule id and no internal code (B14 rule 32 clause 4).
MISSING_NAME = "customer_name_missing"
MISSING_KIND = "customer_kind_missing"
MISSING_IDENTIFIER = "customer_identifier_missing"
#: The one code a door reports for all three, so a screen has one thing to look
#: for and the detail rides underneath it.
NOT_CREATED = "customer_not_identified"

REFUSAL_NOT_STRONG = "identity_match_not_strong"
REFUSAL_NO_EVIDENCE = "no_identity_evidence_presented"
NO_CANDIDATES = "no_prior_customer_found"

# ── the two questions this wave did NOT answer (prime directive) ────────────
#: Does a company get a date-of-birth equivalent? The decision log of
#: 2026-09-01 states in as many words that this is NOT decided.
OQ_INCORPORATION_DATE = "OQ-1241"
#: Is a sole trader a person or a company? Also stated as undecided there.
OQ_SOLE_TRADER = "OQ-1242"

#: The spellings of *sole trader* a door might send. They are recognised so the
#: question is RAISED rather than silently folded into one of the two kinds —
#: folding it would be answering an open question by choosing a value.
SOLE_TRADER_SPELLINGS: frozenset[str] = frozenset(
    {"sole_trader", "sole trader", "sole-trader", "sole_proprietor", "sole proprietor"}
)


def normalise_kind(value: Any) -> str | None:
    """`'Company'` → `'company'`; an unstated kind → `None`; a sole trader → RAISES.

    ⚠ **A SOLE TRADER IS NEITHER, AND THIS FUNCTION REFUSES TO PICK ONE
    (`OQ-1242`).** They trade as a business and are a natural person, so the two
    readings ask for different evidence: a Tax ID under one, a Social Security
    number or a driving licence under the other. Choosing here would resolve an
    open question by writing a value into a customer's row, which the prime
    directive forbids. `CR-033` §4 contains the nearest thing to an answer — a
    lane's own sentence, *"a sole trader is a person on a commercial
    account"* — but that paragraph is about `service_requests.applicant_kind`,
    a DIFFERENT column that CR-033 itself insists is not the same fact, so it
    settles nothing here.
    """
    if value in (None, ""):
        return None
    text = str(value).strip().casefold()
    if text in SOLE_TRADER_SPELLINGS:
        raise NotImplementedError(OQ_SOLE_TRADER)
    # Anything else is returned as typed. Whether it is one of the two lawful
    # kinds is the VALIDATOR's question, so an unknown value reaches a clerk as
    # a named field error rather than being folded into `person` here.
    return text


def creation_minimum(evidence: IdentityEvidence) -> dict[str, Any] | None:
    """`BR-CUS-1023` — is there enough here to MINT a Customer number?

    Returns **`None` when the minimum is met**, and otherwise a dict naming the
    ONE thing that is missing, in the order a clerk would fix it:

        {"missing": <MISSING_*>, "kind": <kind or None>, "accepts": [fields]}

    **THE MINIMUM, in the PO's own words (2026-09-01):** *"Customer ID - minimum
    name and one ID - minimum"*, elaborated as *"Customer can be person or
    company - in case of person, if we have SSN, or DL or Phone number, we
    create the Customer ID and attached these to customer ID; if it is Company
    then we ask for Tax ID"*.

    | kind | enough to CREATE |
    |---|---|
    | **person** | a name **AND** (SSN **or** driving licence **or** phone) |
    | **company** | a name **AND** its Tax ID |

    ⚠ **A DATE OF BIRTH IS NOT AN IDENTIFIER AND DOES NOT CREATE.** It is one
    of `BR-CUS-089`'s three MATCHING criteria and the PO's creation list does
    not name it. A row minted on a name and a birthday is a row the matcher can
    never make strong, because it holds no government identifier to agree about.

    ⚠ **THIS FUNCTION NEVER RAISES AND MUST NEVER BE MADE TO** — that half
    stands, and it is why the answer is a value rather than an exception.

    ⛔ **BUT ITS SECOND SENTENCE IS SUPERSEDED (2026-09-01, PO ruling — see
    `BR-CUS-1024`), AND IT IS LEFT HERE QUOTED RATHER THAN DELETED SO NOBODY
    RESTORES IT BY ACCIDENT.** It read: *"it decides nothing about whether the
    ACCOUNT opens. `BR-CUS-1023`: a person standing at the counter who will not
    give an identifier still gets their water."* **PO verbatim, later the same
    day:** *"Without identifier we cannot create Customer ID or master account
    ot regular account"*. So this answer now decides BOTH — no number and no
    account — and the doors a clerk presses turn a shortfall into a refusal
    BEFORE anything is written (`services.refuse_account_without_identity`).

    **THE RAISE STAYS OUT OF THIS FUNCTION ANYWAY, AND FOR THE ORIGINAL REASON
    ONE LEVEL UP:** every in-transaction caller of `link_customer` runs inside
    the door's own `transaction.atomic()`, so an exception HERE would roll an
    account back mid-write. The counter doors check FIRST, refuse cleanly, and
    write nothing; the doors that are not gated (the bulk import, whose
    migration-blocking exemption is recorded at its call site) still take the
    skip. A pure predicate serves both; an exception serves neither.

    ⚠ **AND IT ANSWERS ONLY ABOUT CREATION.** Linking to a customer already on
    file — a clerk's explicit choice, a matching `external_ref`, a `strong`
    identity match — never consults it. Those rows exist; the rule is about
    minting a new number, and applying it to a link would refuse to recognise
    the very customers it was written to protect.
    """
    # An unlawful kind string is reported as NO kind: `_validate_customer_kind`
    # refuses it by name one level up, and a shortfall keyed on a value that is
    # not one of the two would have no sentence to show (`G32`'s exact shape).
    kind = evidence.kind if evidence.kind in KINDS else None
    if not normalise_name(evidence.name):
        return {"missing": MISSING_NAME, "kind": kind, "accepts": []}
    if kind is None:
        # Not weak evidence — UNJUDGEABLE evidence. Which identifier counts
        # depends on the answer, so there is no test to apply (`BR-CUS-1022`).
        return {"missing": MISSING_KIND, "kind": None, "accepts": []}
    accepts = CREATE_IDENTIFIER_FIELDS[kind]
    for field in accepts:
        if getattr(evidence, field, None) not in (None, ""):
            return None
    return {"missing": MISSING_IDENTIFIER, "kind": kind, "accepts": list(accepts)}


#: The clerk's sentence for each shortfall, keyed per kind where the kind
#: changes what is being asked for. `weak_match_refusal` above is the same
#: posture: **the wording follows the TEST**, because telling a business it
#: needs a driving licence sends somebody to find a document that does not
#: exist. No rule id, no internal code, no figure (B14 rule 32 clause 4).
NOT_CREATED_MESSAGE_KEY: dict[tuple[str, str | None], str] = {
    # ⚠ **THE EXISTING SENTENCE, DELIBERATELY REUSED.** This case used to be a
    # `BizError` in `services.link_customer` carrying exactly this key, and all
    # eleven catalogues already hold its translation. What changed is the
    # SHAPE — it skips the number instead of failing the whole row — and the
    # words a clerk reads are unchanged.
    (MISSING_NAME, None): "customers.customer.display_name_required",
    (MISSING_NAME, KIND_PERSON): "customers.customer.display_name_required",
    (MISSING_NAME, KIND_COMPANY): "customers.customer.display_name_required",
    (MISSING_KIND, None): "customers.customer.identity_kind_required",
    (MISSING_IDENTIFIER, KIND_PERSON): "customers.customer.identity_required_person",
    (MISSING_IDENTIFIER, KIND_COMPANY): "customers.customer.identity_required_company",
}


def not_created_payload(shortfall: dict[str, Any]) -> dict[str, Any]:
    """What a door reports when it opened an account and minted NO number.

    One `code` for every shortfall so a screen has one thing to look for, the
    named missing thing beside it, and the clerk's own sentence keyed for
    translation. **The account is NOT mentioned as a failure anywhere in here**
    — it opened, and this says only what did not happen alongside it.
    """
    key = NOT_CREATED_MESSAGE_KEY[(shortfall["missing"], shortfall["kind"])]
    return {
        "code": NOT_CREATED,
        "missing": shortfall["missing"],
        "kind": shortfall["kind"],
        "accepts": list(shortfall["accepts"]),
        "message_key": key,
    }


def _tenant_id() -> Any:
    from core import tenancy as core_tenancy

    tenant_id = core_tenancy.current_tenant_id()
    if tenant_id is None:
        raise errors.AuthError(errors.AUTH_TENANT_UNRESOLVABLE, br_ref="BR-TEN-003")
    return tenant_id


def normalise_name(value: str | None) -> str:
    """`'  Ajinkya   KULKARNI '` → `'ajinkya kulkarni'`.

    Case-folded and whitespace-collapsed, and NOTHING else — no initial
    expansion, no nickname table, no edit distance. CR-056 §4's own example is
    `A. Kulkarni` against `Ajinkya Kulkarni`, and **every rule loose enough to
    unite those two also unites two real strangers.** `casefold()` rather than
    `lower()` because it is the form that folds non-ASCII case pairs correctly,
    and a utility that bills a Straße will meet one.
    """
    if not value:
        return ""
    return " ".join(str(value).split()).casefold()


def _as_date(value: Any) -> date | None:
    """A date of birth, or None. A malformed one is None and never today's date."""
    if value is None or value == "":
        return None
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(str(value).strip()[:10])
    except (TypeError, ValueError):
        return None


@dataclass(frozen=True)
class IdentityEvidence:
    """What is being presented about a party, at one door, on one day.

    Every field is optional because every door collects a different subset:
    the counter has a form, an import has a spreadsheet column, a service
    request has an application. **An absent field is absent — it never agrees
    with anything**, which is the whole of `agreed_facts` below and is why an
    empty evidence set can never produce a match.

    ⚠ **`kind` IS NOT ONE MORE OPTIONAL FIELD — IT DECIDES WHICH OF THE OTHERS
    MEAN ANYTHING (`BR-CUS-1022`).** A person is identified by a Social Security
    number, a driving licence or a phone; a company by its Tax ID. Evidence that
    names no kind cannot be judged at all, so `has_any` answers False for it and
    the door refuses rather than guessing `person` — see `services.link_customer`
    and the decision log of 2026-09-01.
    """

    name: str | None = None
    kind: str | None = None
    date_of_birth: Any = None
    ssn: str | None = None
    driving_licence: str | None = None
    phone: str | None = None
    tax_id: str | None = None

    @property
    def dob(self) -> date | None:
        return _as_date(self.date_of_birth)

    def has_any(self) -> bool:
        """Is there anything here to match ON, and do we know what it is ABOUT?

        Two conditions, and the second is `CR-056` W2b's addition:

          * **The NAME alone does not count.** A name is what the product
            matched on before CR-056 and §4 is a whole paragraph about why that
            is not identity: *"A. Kulkarni and Ajinkya Kulkarni are two
            landlords and nothing objects."*
          * **A KIND must be stated.** `ssn` presented against an unstated kind
            is a government identifier filed under a party nobody has classified,
            and the criteria it would be judged against depend on the answer.
        """
        if self.kind not in KINDS:
            return False
        if FACT_DOB in KIND_DATED_FIELDS[self.kind] and self.dob is not None:
            return True
        return any(bool(getattr(self, field)) for field in KIND_IDENTIFIER_FIELDS[self.kind])

    def identifiers(self) -> dict[str, str]:
        """The indexable values present AND lawful for this kind, by field name.

        ⚠ **A FIELD BELONGING TO THE OTHER KIND IS NOT RETURNED HERE**, so it
        cannot be probed, cannot agree and cannot be written. Doors refuse it by
        name one level up (`services._validate_customer_block`); this is the
        second lock, and it is here because `link_customer` can also be called
        in-process with an `IdentityEvidence` built by hand.
        """
        if self.kind not in KINDS:
            return {}
        present: dict[str, str] = {}
        for field in KIND_IDENTIFIER_FIELDS[self.kind]:
            value = getattr(self, field)
            if value not in (None, ""):
                present[field] = str(value).strip()
        return present


def from_payload(payload: Any, *, kind: Any = None) -> IdentityEvidence:
    """Build evidence from a request body's `identity` block.

    Unknown keys are IGNORED rather than refused, and that is a deliberate
    difference from `services._reject_unknown`: this is not a write vocabulary,
    it is a set of things to compare, and a door that sends an extra field must
    not have its account creation refused over a matching hint. **The door's own
    validator refuses an unknown key before this is reached** — that is where a
    typo'd `ssn` becomes a field error rather than a silently dropped secret.

    ⚠ **`incorporation_date` IS RECOGNISED AND REFUSED, NOT IGNORED
    (`OQ-1241`).** Whether a company gets a date-of-birth equivalent is open, so
    a door that supplies one meets the question instead of having the value
    quietly dropped — a drop would look exactly like a stored fact that never
    matches anything.
    """
    data = payload if isinstance(payload, dict) else {}
    if data.get("incorporation_date") not in (None, ""):
        raise NotImplementedError(OQ_INCORPORATION_DATE)
    return IdentityEvidence(
        name=data.get("name") or data.get("display_name"),
        kind=normalise_kind(kind if kind not in (None, "") else data.get("kind")),
        date_of_birth=data.get("date_of_birth") or data.get("dob"),
        ssn=data.get("ssn"),
        driving_licence=data.get("driving_licence") or data.get("drivers_licence"),
        phone=data.get("phone"),
        tax_id=data.get("tax_id"),
    )


# ═══════════════════════════════════════════════════════════════════════════
# TASK 12 — RECONCILING THE TWO PLACES IDENTITY ALREADY LIVED
# ═══════════════════════════════════════════════════════════════════════════
def evidence_from_service_request(request: Any) -> IdentityEvidence:
    """Lift what an APPLICATION already holds, without moving or copying it.

    `service_requests` carries the applicant's name, phone, an
    app-layer-encrypted SSN (2026-08-27) and — **since 2026-09-15** — a DATE OF
    BIRTH and an app-layer-encrypted DRIVING LICENCE (`BR-CUS-092`(a) finished,
    PO ruling of that date).

    ✅ **THAT IS WHY THIS FUNCTION CHANGED, AND IT IS THE WHOLE POINT OF THE
    RULING.** It used to read, in this docstring: *"It carries no date of birth
    ... So a request alone can surface a candidate and can never, by itself, make
    a match `strong`."* `BR-CUS-1020` recorded the same cost verbatim — *"until
    the request form captures a DOB, no match can be assessed against them"* —
    and `BR-CUS-089`'s signed criteria (**name + date of birth + one government
    ID**) were therefore inert on this surface for three weeks, with nothing
    red, because an absence is invisible to every check this repo has. A request
    can now present all three facts.

    ⚠ **WHAT IS STILL TRUE: NOTHING HERE DECIDES A TIER.** This function lifts
    evidence; `tier_for` weighs it and a human commits it. `BR-CUS-089` lets a
    `strong` match move a **$150.00** deposit (**$153.50** with `BR-CUS-057`'s
    interest), so nothing in this module may loosen what counts as strong — the
    criteria are signed and are read, never widened.

    ⚠ **AND IT STILL CARRIES NO KIND MOST OF THE TIME, SINCE `CR-033` TOOK THE
    CONTROL OFF THE FORM.** `service_requests.applicant_kind` exists, is
    validated, and is lifted here where a request holds one — but the capture
    screen stopped sending it on 2026-08-27, so the column takes its `person`
    default. Under `BR-CUS-1022` an unstated kind can never be strong, which is
    the safe direction and is stated here rather than patched by defaulting.

    ⚠ **THE KIND VOCABULARIES DIFFER AND THAT IS NOT FIXED HERE.**
    `service_requests.applicant_kind` is `person | business`; `customers.kind` is
    `person | company`. `normalise_kind` returns `business` unchanged, so a
    business request stays below `strong` — again the safe direction, and
    changing it would be minting a mapping nobody has ruled.
    """
    return IdentityEvidence(
        name=getattr(request, "applicant_name", None),
        kind=normalise_kind(getattr(request, "applicant_kind", None)),
        date_of_birth=getattr(request, "date_of_birth", None),
        ssn=getattr(request, "ssn", None),
        driving_licence=getattr(request, "drivers_licence", None),
        phone=getattr(request, "applicant_phone", None),
    )


def reconcile_from_contact(customer: models.Customer, contact: Any) -> list[str]:
    """Fill the customer's EMPTY identity fields from an account contact.

    **Fills, never overwrites.** The customer row spans a person's whole
    relationship with the utility and a contact row belongs to one account; a
    contact captured last week must not silently restate a date of birth
    somebody confirmed against a passport two years ago. Where the two
    DISAGREE, the customer's value stands and the disagreement is returned for
    the caller to record — it is a fact a human should look at, not a conflict
    to resolve by precedence.

    ⚠ **`gov_id_last4` IS NOT COPIED ANYWHERE, EVER.** It is four digits, and
    four digits collide about once in ten thousand — as an identifier it is one
    that cannot identify. BR-CUS-092(c) is the reason it is only four: the last
    four is a DISPLAY projection. Storing it as `customers.ssn` would put a
    matchable-looking value in a column the matcher trusts.

    Returns the list of field names it filled, so the caller can audit what
    moved (CLAUDE.md rule 7) rather than reporting that "reconciliation ran".

    ⚠ **A COMPANY GETS NEITHER FACT FROM HERE.** `contacts.dob` is a natural
    person's date of birth, and a company has none (`OQ-1241` is open on whether
    it gets the equivalent); its phone is a person's handle on that one account
    rather than the company's own identifier. So this fills a PERSON's row only,
    and a company's stays empty rather than acquiring a fact from the wrong kind
    of party.
    """
    filled: list[str] = []
    if contact is None or getattr(customer, "kind", None) != KIND_PERSON:
        return filled
    contact_dob = _as_date(getattr(contact, "dob", None))
    if contact_dob is not None and customer.date_of_birth is None:
        customer.date_of_birth = contact_dob
        filled.append(FACT_DOB)
    contact_phone = getattr(contact, "phone", None)
    if contact_phone and not customer.phone:
        set_identifier(customer, "phone", contact_phone)
        filled.append(FACT_PHONE)
    return filled


# ═══════════════════════════════════════════════════════════════════════════
# WRITING AN IDENTIFIER — the ciphertext and its blind index, together
# ═══════════════════════════════════════════════════════════════════════════
def set_identifier(customer: models.Customer, field: str, value: str | None) -> None:
    """Write one encrypted identifier AND its blind-index token, in one act.

    They are set together and only together. A ciphertext with no token is a
    value the matcher cannot see — the account would be unfindable and every
    test would pass — and a token with no ciphertext is an equality oracle over
    a value nobody can read. `EncryptedTextField` encrypts on the way to the
    database; the token is computed here because it is an ordinary text column.

    ⚠ The caller must still SAVE. This is deliberately not a save: an identity
    write belongs inside the same transaction as the row it identifies.
    """
    if field not in CRYPTO_CONTEXT:
        raise ValueError(f"{field} is not an encrypted identity column")
    # ⚠ CR-056 W2b — NEITHER KIND MAY BORROW THE OTHER'S. A driving licence
    # written onto a company, or a Tax ID onto a person, is a column the
    # matcher for that kind never reads: it would be stored, invisible and
    # permanently unmatchable, which is worse than being refused.
    allowed = KIND_IDENTIFIER_FIELDS.get(getattr(customer, "kind", None) or "", ())
    if field not in allowed:
        raise ValueError(f"{field} is not an identifier a {customer.kind} is asked for")
    context = CRYPTO_CONTEXT[field]
    cleaned = None if value in (None, "") else str(value).strip()
    setattr(customer, field, cleaned)
    setattr(customer, BIDX_COLUMN[field], crypto.blind_index(cleaned, context=context))


def apply_evidence(customer: models.Customer, evidence: IdentityEvidence) -> list[str]:
    """Put presented evidence onto a customer's EMPTY identity columns.

    Same posture as `reconcile_from_contact`: **fills, never overwrites.**
    Correcting an identifier already on file is a different act with a different
    audit story — somebody is saying the stored value is wrong — and it is not
    something an account-opening door should do as a side effect. Returns what
    it filled.

    ⚠ **NOTHING IS WRITTEN WHERE THE EVIDENCE AND THE ROW DISAGREE ABOUT THE
    KIND.** A person's evidence must not land on a company's row, whichever way
    round the mismatch arose; the caller is linking to the wrong party and a
    filled column would make that wrong link look confirmed.
    """
    filled: list[str] = []
    if evidence.kind not in KINDS or evidence.kind != getattr(customer, "kind", None):
        return filled
    if (
        FACT_DOB in KIND_DATED_FIELDS[evidence.kind]
        and evidence.dob is not None
        and customer.date_of_birth is None
    ):
        customer.date_of_birth = evidence.dob
        filled.append(FACT_DOB)
    for field, value in evidence.identifiers().items():
        if not getattr(customer, field):
            set_identifier(customer, field, value)
            filled.append(field)
    return filled


# ═══════════════════════════════════════════════════════════════════════════
# THE VERDICT — BR-CUS-089's criteria, and not one clause more
# ═══════════════════════════════════════════════════════════════════════════
def agreed_facts(evidence: IdentityEvidence, customer: models.Customer) -> list[str]:
    """Which comparable facts AGREE. Absent never agrees, and neither does a
    fact belonging to the other kind of party.

    ⚠ **THE ABSENT-NEVER-AGREES RULE IS THE WHOLE SAFETY PROPERTY.** Two
    customers with no date of birth on file must not be found to "agree" about
    it — that is how `None == None` turns an empty database into a room full of
    perfect matches. Every comparison below tests presence on BOTH sides first.

    ⚠ **AND A PERSON AND A COMPANY ARE NEVER THE SAME PARTY (`BR-CUS-1022`).**
    Where the presented kind and the row's kind disagree, NOTHING agrees — not
    even the name. A name agreeing across two kinds is exactly the fact that
    would make a human think they had found somebody.
    """
    agreed: list[str] = []

    if evidence.kind not in KINDS or evidence.kind != customer.kind:
        return agreed

    presented_name = normalise_name(evidence.name)
    if presented_name and presented_name == normalise_name(customer.display_name):
        agreed.append(FACT_NAME)

    if (
        FACT_DOB in KIND_DATED_FIELDS[evidence.kind]
        and evidence.dob is not None
        and customer.date_of_birth == evidence.dob
    ):
        agreed.append(FACT_DOB)

    for field, value in evidence.identifiers().items():
        stored = getattr(customer, BIDX_COLUMN[field], None)
        if not stored:
            continue
        tokens = crypto.blind_index_candidates(value, context=CRYPTO_CONTEXT[field])
        if stored in tokens:
            agreed.append(field)

    return agreed


def tier_for(agreed: list[str], kind: str | None) -> str:
    """`strong` on the criteria for THAT KIND, and on nothing else.

    **A PERSON** — `strong` iff NAME **and** DATE OF BIRTH **and** one
    GOVERNMENT ID agree. `BR-CUS-089`, PO 2026-08-25 closing `OQ-364`, verbatim:
    *"Name + date of birth + one government ID"*. Unchanged by CR-056 W2b.

    **A COMPANY** — `strong` iff NAME **and** TAX ID agree. PO 2026-09-01,
    verbatim: *"if it is Company then we ask for Tax ID"*, narrowed onto this
    test by the decision log of the same day (`BR-CUS-1022`).

    ⚠ **THE DATE-OF-BIRTH CLAUSE IS NOT DROPPED FOR COMPANIES — IT NEVER
    APPLIED TO THEM.** `BR-CUS-089` is a rule about persons and stands unchanged
    for them; a company has no date of birth to agree about, which is why the
    signed rule read literally made every company permanently unmatchable.
    Whether a company gets the equivalent is `OQ-1241`, open.

    ⚠ **NEITHER KIND BORROWS THE OTHER'S CRITERIA, AND AN UNSTATED KIND EARNS
    NOTHING.** Two explicit booleans over named constants rather than a score,
    so the rule is greppable and a later edit that drops a clause is visible in
    a diff rather than hidden in arithmetic.
    """
    facts = set(agreed)
    if FACT_NAME not in facts:
        return TIER_WEAK
    if kind == KIND_PERSON:
        has_government_id = any(field in facts for field in GOVERNMENT_ID_FIELDS)
        if FACT_DOB in facts and has_government_id:
            return TIER_STRONG
    elif kind == KIND_COMPANY and any(field in facts for field in COMPANY_ID_FIELDS):
        return TIER_STRONG
    return TIER_WEAK


def basis_sentence(agreed: list[str]) -> str:
    """What agreed, in words a person can read, for `match_basis`.

    Plain English and no rule ids: this string reaches a clerk-facing screen
    and B14 rule 32 keeps rule ids and internal codes out of clerk copy.
    """
    words = {
        FACT_NAME: "name",
        FACT_DOB: "date of birth",
        FACT_SSN: "Social Security number",
        FACT_LICENCE: "driving licence",
        FACT_PHONE: "phone",
        FACT_TAX_ID: "Tax ID",
    }
    named = [words[fact] for fact in agreed if fact in words]
    if not named:
        return "nothing presented matched this customer"
    if len(named) == 1:
        return f"matched on {named[0]}"
    return f"matched on {', '.join(named[:-1])} and {named[-1]}"


def _candidate(customer: models.Customer, agreed: list[str]) -> dict[str, Any]:
    """One candidate, as a screen and an audit row may hold it.

    ⚠ **NO FULL IDENTIFIER LEAVES THIS FUNCTION** — BR-CUS-092(c): *"every read
    path renders last four only and the full value is never in a list response,
    an export, a log line or an audit `details` blob"*. And no database id is
    the VALUE of anything a clerk reads (B14 rule 31): `customer_no` is the
    number a person quotes down a phone, `id` rides only as a machine handle.
    """
    return {
        "id": str(customer.id),
        "customer_no": customer.customer_no,
        "display_name": customer.display_name,
        # CR-056 W2b — the KIND rides with the candidate, because it is what
        # decided the tier beside it. A screen that shows `weak` without saying
        # which test was applied cannot tell a clerk what is missing.
        "kind": customer.kind,
        "tier": tier_for(agreed, customer.kind),
        "agreed": agreed,
        "basis": basis_sentence(agreed),
        "ssn_last4": crypto.last_four(customer.ssn) if customer.ssn else None,
        "driving_licence_last4": (
            crypto.last_four(customer.driving_licence) if customer.driving_licence else None
        ),
        "tax_id_last4": crypto.last_four(customer.tax_id) if customer.tax_id else None,
    }


def find_candidates(evidence: IdentityEvidence) -> list[models.Customer]:
    """Every customer this evidence could conceivably be about — tenant-scoped.

    Two probes, unioned, and each is an EQUALITY test:

      * the blind indexes this KIND is asked for — `ssn_bidx`,
        `driving_licence_bidx` and `phone_bidx` for a person, `tax_id_bidx` and
        `phone_bidx` for a company — against `blind_index_candidates(...)`,
        which asks about one token per configured key so rows written before a
        rotation stay findable without being rewritten;
      * `display_name` case-insensitively, which is how a returning customer who
        has changed neither their name nor anything else is still surfaced.

    ⚠ **THE SEARCH IS NARROWED TO THE PRESENTED KIND (`BR-CUS-1022`).** A
    company is never a candidate for a person's evidence and the reverse, so a
    landlord and the limited company he trades through stay two rows however
    alike their names read. Without this, `display_name__iexact` alone would
    surface the other kind and put a row on a clerk's screen that no test could
    ever confirm.

    ⚠ **SURFACING IS NOT MATCHING.** A name-only hit is a candidate a human may
    look at; it can never be `strong`, because `tier_for` needs the whole test
    for that kind.

    ⚠ **AN EMPTY EVIDENCE SET RETURNS NOTHING**, and that is `blind_index_
    candidates`' own design: it answers `[]` for an absent value, so
    `col__in=[]` matches nothing. The alternative — a bare name probe on no
    other evidence — is exactly the pre-CR-056 behaviour CR-056 exists to end.
    """
    if not evidence.has_any():
        return []

    tenant_id = _tenant_id()
    query = Q(pk__in=[])
    for field, value in evidence.identifiers().items():
        tokens = crypto.blind_index_candidates(value, context=CRYPTO_CONTEXT[field])
        if tokens:
            query |= Q(**{f"{BIDX_COLUMN[field]}__in": tokens})
    if evidence.name:
        query |= Q(display_name__iexact=str(evidence.name).strip())

    return list(
        models.Customer.objects.filter(query, tenant_id=tenant_id, kind=evidence.kind).order_by(
            "created_at"
        )
    )


def recognise(evidence: IdentityEvidence) -> dict[str, Any]:
    """The verdict. **It links nothing and moves nothing.**

    Three shapes come back, and the caller must handle all three:

      * **`matched` is a customer id and `tier` is `strong`** — the three signed
        facts agreed with exactly one customer. `services.link_customer` links
        to them, records the tier with the acting human as its confirmer, and
        that is what lets `discounts.carry_forward_offer` carry the deposit.

      * **`matched` is None, `tier` is `weak`, and `candidates` is not empty** —
        somebody on file looks related and the criteria are NOT met.
        `refusal` is `identity_match_not_strong` and the caller **refuses to
        link**, showing the candidates instead. This is `BR-CUS-019` (*the
        duplicate check is ADVISORY — staff decides*) and `BR-CUS-089` (*money
        moves only on strong*) agreeing: nothing is blocked, and nothing is
        merged behind a clerk's back.

      * **`matched` is None and `candidates` is empty** — a genuine first-timer,
        or the first time this utility has held enough about them to tell.
        `refusal` is `no_prior_customer_found`, which is a real ANSWER and not
        an error: it is what makes the arrears condition clearable for a genuine
        first-time applicant, the same reading `service_request_service.
        link_customer` already takes of a search that found nothing.

    ⚠ **TWO OR MORE STRONG MATCHES IS A REFUSAL, NOT A PICK.** If the evidence
    is strong against two different customers the database is telling us two
    parties share a government identifier and a name. Choosing the older row
    would move a deposit onto a coin toss, so `tier` is `weak`, `refusal` is
    `identity_match_not_strong`, and both candidates are returned for a human.
    ⚠ **AND IT IS NOT THEORETICAL FOR A COMPANY.** The PO ruled on 2026-09-01
    that *a duplicate identifier refuses to LINK and never refuses to SAVE*, so
    two customers CAN carry the same Tax ID — a clerk who mistypes a digit must
    still be able to open the account. This branch is where that ruling is
    honoured: nothing is blocked at the counter, and nothing is merged behind
    anybody's back. There is no unique index on `tax_id_bidx`, deliberately
    (migration `customers 0038` says why).

    ⚠ **AND A KIND IS PART OF THE EVIDENCE (`BR-CUS-1022`).** Evidence that
    names none answers `no_identity_evidence_presented`, because the criteria a
    match would be judged against depend on the answer. Guessing `person` would
    judge a company by a test it can never pass and file its Tax ID nowhere.
    """
    if not evidence.has_any():
        return {
            "matched": None,
            "tier": None,
            "basis": None,
            "agreed": [],
            "refusal": REFUSAL_NO_EVIDENCE,
            "candidates": [],
        }

    rows = find_candidates(evidence)
    assessed = [(row, agreed_facts(evidence, row)) for row in rows]
    candidates = [_candidate(row, agreed) for row, agreed in assessed]
    strong = [entry for entry in candidates if entry["tier"] == TIER_STRONG]

    if len(strong) == 1:
        winner = strong[0]
        return {
            "matched": winner["id"],
            "tier": TIER_STRONG,
            "basis": winner["basis"],
            "agreed": winner["agreed"],
            "refusal": None,
            "candidates": candidates,
        }

    return {
        "matched": None,
        "tier": TIER_WEAK if candidates else None,
        "basis": None,
        "agreed": [],
        "refusal": REFUSAL_NOT_STRONG if candidates else NO_CANDIDATES,
        "candidates": candidates,
    }


def reuse_candidate(evidence: IdentityEvidence) -> dict[str, Any]:
    """`BR-CUS-1024` — **is this customer number already on file?**

    A third question, asked between *may a number be minted* (`creation_minimum`)
    and *may money follow it* (`tier_for`), and it is the one nothing asked until
    `DEF-2587` was measured.

    Answers a dict, always the same four keys::

        {"customer": <Customer|None>, "agreed": [facts], "candidates": [...],
         "ambiguous": <bool>}

    **THE TEST: the NAME agrees, and at least one GOVERNMENT-GRADE identifier for
    this kind agrees** — a Social Security number or a driving licence for a
    person, the Tax ID for a company (`REUSE_ID_FIELDS`). Both halves are
    required and both are exact: names case-folded and whitespace-collapsed,
    never fuzzy (`normalise_name`); identifiers compared through their keyed
    blind indexes, which leak equality and nothing else.

    ⚠ **EXACTLY ONE HIT REUSES. ZERO CREATES. TWO OR MORE REFUSES AND STILL
    SAVES.** Where two customers both agree, the database is telling us two
    parties share a name and a government identifier — which the PO explicitly
    allowed on 2026-09-01 (*a duplicate identifier refuses to LINK and never
    refuses to SAVE*, and there is deliberately no unique index on `tax_id_bidx`
    or `ssn_bidx`). Picking the older row would be a coin toss over somebody's
    file, so nothing is reused, the caller mints its own number, and both
    candidates ride back for a human. `ambiguous` says which of the two empty
    answers this is, because *"nobody matched"* and *"two people matched"* need
    different words on a screen.

    ⚠ **A PHONE CANNOT REUSE, THOUGH IT CAN CREATE.** See `REUSE_ID_FIELDS` —
    minting a spare row on a shared household line costs a merge; reusing one
    hands a stranger an existing customer's file.

    ⚠ **IT RECORDS NO TIER AND MOVES NO MONEY.** A reuse is a statement about how
    many rows exist, never about what they may do: `BR-CUS-089` still governs the
    deposit and still needs its full signed test, date of birth included, so the
    **$153.50** of `WE-7`/`GT-23` does not follow a reuse. `services.link_customer`
    stores `match_tier` only from `recognise`'s verdict, never from this.

    ⚠ **AND IT NEVER CORRECTS A STORED IDENTIFIER.** The caller's
    `apply_evidence` fills EMPTY columns on the reused row and overwrites
    nothing — asserting that a stored value is wrong is a different act with a
    different audit story and is not a side effect of opening an account.
    """
    empty: dict[str, Any] = {
        "customer": None,
        "agreed": [],
        "candidates": [],
        "ambiguous": False,
    }
    # An unstated kind cannot be judged at all (`BR-CUS-1022`) and a name alone
    # was never identity (`CR-056` §4: *A. Kulkarni and Ajinkya Kulkarni are two
    # landlords and nothing objects*). Both are refusals, not weak answers.
    if evidence.kind not in KINDS or not normalise_name(evidence.name):
        return empty
    fields = REUSE_ID_FIELDS[evidence.kind]
    # `identifiers()` already drops anything unlawful for this kind; this narrows
    # again to the GOVERNMENT-grade subset, which is what leaves the phone out.
    if not any(field in fields for field in evidence.identifiers()):
        return empty

    hits: list[tuple[models.Customer, list[str]]] = []
    for row in find_candidates(evidence):
        agreed = agreed_facts(evidence, row)
        if FACT_NAME in agreed and any(field in agreed for field in fields):
            hits.append((row, agreed))

    candidates = [_candidate(row, agreed) for row, agreed in hits]
    if len(hits) != 1:
        return {
            "customer": None,
            "agreed": [],
            "candidates": candidates,
            "ambiguous": len(hits) > 1,
        }
    row, agreed = hits[0]
    return {"customer": row, "agreed": agreed, "candidates": candidates, "ambiguous": False}


#: The sentence a screen or a payload shows when a weak case refuses. Plain
#: English with no rule id in it (B14 rule 32) — the rule id rides in `br_ref`
#: beside it, which is where a payload's machinery belongs.
#:
#: ⚠ **THIS IS THE PERSON'S WORDING. A COMPANY GETS ITS OWN** — see
#: `weak_match_refusal` below. It stays a module constant because it is what a
#: caller holding no kind can still say truthfully.
WEAK_MATCH_REFUSAL: dict[str, Any] = {
    "code": REFUSAL_NOT_STRONG,
    "br_ref": "BR-CUS-089 · BR-CUS-019",
    "detail": (
        "Somebody already on file looks related to the details entered, but not enough of "
        "them agree to say it is the same person: a returning customer is recognised only "
        "when the name, the date of birth and one government identifier all agree. The new "
        "account has been opened under its own customer number and nothing has been merged. "
        "If it is the same person, link them and the deposit they are owed can follow."
    ),
}

#: The same refusal for a COMPANY, and the sentence differs because the TEST
#: differs. `BR-CUS-1022` (PO 2026-09-01): a company is recognised on its name
#: and its Tax ID. Telling a clerk that a business failed a date-of-birth test
#: would be sending them to find a fact that does not exist.
COMPANY_WEAK_MATCH_REFUSAL: dict[str, Any] = {
    "code": REFUSAL_NOT_STRONG,
    "br_ref": "BR-CUS-1022 · BR-CUS-019",
    "detail": (
        "A business already on file looks related to the details entered, but not enough of "
        "them agree to say it is the same one: a returning business is recognised only when "
        "the name and the Tax ID both agree. The new account has been opened under its own "
        "customer number and nothing has been merged. If it is the same business, link them "
        "and the deposit they are owed can follow."
    ),
}


def weak_match_refusal(kind: str | None) -> dict[str, Any]:
    """The refusal wording for THAT kind, and never a figure.

    ⚠ **NO AMOUNT APPEARS IN EITHER SENTENCE, FOR EITHER KIND.** `BR-CUS-089`'s
    own worked case is the reason: a refused offer that prints **$150.00** is an
    invitation to type it in by hand. The rule was written for persons and the
    hazard is identical for a business, so the company wording carries none
    either.
    """
    return COMPANY_WEAK_MATCH_REFUSAL if kind == KIND_COMPANY else WEAK_MATCH_REFUSAL


# ── Lifecycle ─────────────────────────────────────────────
# packet: CR-056 W2 tasks 12/13/14 (12-governance/11-change-requests.md §CR-056)
#         + BR-CUS-089 (PO 2026-08-25, closing OQ-364) + BR-CUS-092 (PO 2026-08-24)
#         + BR-CUS-019 + BR-CUS-054 + OQ-016 (CLOSED, PO R6) + B2 §6
#         ⚠ NO `US-XXX-###@<hex>` STAMP AND NONE IS INVENTED — `CR-056` allocates no story ids, and minting one to satisfy `G01`'s regex would put a citation in the tree that resolves to nothing. Same posture as `apps/customers/close_out.py`, which writes its DEF id instead
# generated: 2026-08-31 by the CR-056 W2/W3/W5 lane
#            · AMENDED 2026-09-01 by the CR-056 W6 lane (`BR-CUS-1023`, PO: *"Customer ID - minimum name and one ID - minimum - please make this rule and apply"*): `creation_minimum`, `not_created_payload`, `CREATE_IDENTIFIER_FIELDS`, the three `MISSING_*` reasons and `NOT_CREATED`. ⚠ `CREATE_IDENTIFIER_FIELDS` is NOT `KIND_IDENTIFIER_FIELDS` and the two must never be merged — they differ in one cell (a company's phone captures and does not CREATE) — and NEITHER is `tier_for`: a phone alone CREATES and a phone alone is a WEAK match, both true at once
# checklist: A✔ B✔ C✔ D✔(GET /customers, GET /customers/{id}) E✔(CustomersListPage.tsx) F✔ G✔ H=OWED(🔒 human-review-ledger row is OPEN; the G7 glob is not this lane's to add)
# gates: (W6, 2026-09-01) tests/test_cr056_w6_minimum_identity.py 14 passed · with the neighbours it touches 98 passed · golden-verify 33 PASS / 0 FAIL and G61 PASS (130 frozen figures), unchanged · G32 0 unresolved · G35 PASS at 2.113.0 · PROVED RED FIRST on a clean detached worktree at the tip: the counter minted C-00001 from a name, the master door minted a customer for `Ruiz, Marisol`, the import minted C-00001 from a legacy ref · browser-proved end to end on live PostgreSQL (PO 2026-08-30): four accounts opened with a name and no identifier carry no customer row, one with a phone carries C-00066
# gates: (CR-058 W1, 2026-09-01) tests/test_cr058_w1_one_customer_every_door.py 10 passed — tc1 is the landlord (three buildings, ONE number: DEF-2587 measured C-00001/C-00002/C-00003 before it), tc7 is the deposit that does NOT move on a reuse, tc8 is the account that does not open · with the neighbours it touches 154 passed · golden-verify 33 PASS / 0 FAIL and G61 PASS (130 frozen figures), unchanged · G64 engine-verified 14 of 61, unchanged · G35 PASS at 2.121.0 · browser-proved against a live server (PO 2026-08-30), 4 Chromium cases, PROVED RED FIRST by rendering the refusal empty and rebuilding the SPA
# gates: ruff✔ black✔ · tests/test_cr056_w2_customer_identity.py 21 passed · with the neighbours it touches (deposit carry-forward, customer numbering, premises owner) 64 passed / 2 skipped · golden-verify 33 PASS / 0 FAIL unchanged · G61 frozen figures PASS (130 unchanged)
# exceptions: (1) NOT ON THE G7 GLOB LIST — `G53` names this file for it and is right to; adding a file to `10-scripts/gates/human_owned.txt` is a PROCESS EVENT and the PO's call (`OQ-441`, closed 2026-08-30: the check *must FAIL and name the file, never silently append*). STATED in the module docstring and REPORTED · (2) the matcher emits `strong` and `weak` and NEVER `probable` — BR-CUS-089 defines what earns `strong` and nothing at all about where `probable` begins · (3) a phone match alone is `weak`: CR-056's R3 is RECONSTRUCTED and calls the phone identity evidence, BR-CUS-089 is VERBATIM and says *one government ID* · (4) names compare EXACTLY, case-folded — every rule loose enough to unite `A. Kulkarni` with `Ajinkya Kulkarni` also unites two strangers · (5) NO unique constraint on `ssn_bidx`: R3 is reconstructed and a unique index is a one-way door, so the behaviour is built in the service layer where it is reversible. Named in the review-ledger row as the ONE thing that needs the PO
# status: VERIFIED-UNRATIFIED · HUMAN-REVIEW-PENDING
# ──────────────────────────────────────────────────────────
