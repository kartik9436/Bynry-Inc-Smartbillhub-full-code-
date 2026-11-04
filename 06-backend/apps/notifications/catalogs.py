# ── Trace ──────────────────────────────────────────────
# Story:    US-NOT-005 (the rendering engine + merge-variable catalogs per
#           template type — the CATALOG half)   Screens: S8 · S94–S106
# Rules:    BR-NOT-005 (the queue carries every message class this catalog
#           describes) · BR-NOT-007 (payment-plan notices are a template class
#           of their own) · BR-NOT-004 (S67 contract types v1 — four of them) ·
#           BR-NOT-002 (contract templates are effective-date versioned) ·
#           BR-CUS-039 (disconnect tier content is A19 §2's; the reconnect fee
#           comes from a tenant charge code and is never hardcoded)
# Tests:    06-backend/tests/test_us_not_005_rendering.py ·
#           06-backend/tests/test_cr011_contract_templates.py (the four
#           contract palettes + the ACH placeholder, CR-011 item 9)
# Impacts:  apps/notifications/rendering.py (validates every body and every
#           render context against these sets)
# ───────────────────────────────────────────────────────
"""The typed merge-variable catalog per template class — A19's palette as data.

HUMAN-OWNED · HUMAN-REVIEW-PENDING — 🔒 NOTIFICATION WORDING. This file names **which documents
a utility can send and what each one is a form for**, so adding a row here changes
what the product will put in front of a customer. Flagged 2026-08-30 by the
`DEF-2473` lane, which added ONE new class — the printed returned-payment letter,
deliberately carrying no wording (BR-NOT-015) — and moved the SET-09 arithmetic
from 37 listed / 33 published / 4 offered / **0 with no wording** to 38 / 33 / 4 /
**1**. That last figure is the one a person may want to overrule, and the review
ledger row states it in plain English. AI-authored under the PO ruling of
2026-08-09: *"AI will do it; we will review it later as human."*

US-NOT-005 §1: *"a typed merge-variable catalog per template type (A19 token
sets …) surfaced as the designers' variable palette (A19 addendum r8)"*, and
US-NOT-005 TC-5 is what it is FOR: a receipt body containing `{meter_no}` is
rejected, because `{meter_no}` is not in the receipt type's catalog. A19 rule 6
+ addendum b make the palette the catalog; this file is that palette in a form
the server can enforce, so the rule holds for an API caller and a CSV import and
not only for somebody typing into the designer.

╔══════════════════════════════════════════════════════════════════════════╗
║  EVERY TOKEN BELOW IS QUOTED FROM A SIGNED SPEC. NONE IS INVENTED.       ║
╚══════════════════════════════════════════════════════════════════════════╝

The sources are A19 §1 (bill/statement), §2 (disconnect tiers), §3 (payment-plan
agreement), the A19 2026-08-07 r8 revision (what makes each of the sixteen
classes distinct), and A13's reminder/receipt preview copy — which US-NOT-005 §1
names explicitly as a token source. Where a spec writes a token in braces it
appears here with that spelling. Where a spec names CONTENT in prose but no
token — *"balance before/after, processed-by staff name"* — the content is
ratified and only the SPELLING is engineering vocabulary; those are marked
`derived_spelling` below so a reviewer can tell the two apart at a glance.

Where a spec names NEITHER — the six email bodies and four SMS bodies of the
r8 revision, three of BR-NOT-004's four contract types, and BR-NOT-007's
payment-plan notices — **there is no catalog here and none is guessed**. Those
classes are registered in `CLASSES_WITHOUT_CATALOG` with the reason, so the
absence is a value this module returns rather than a silence a reader has to
notice. `apps/notifications/rendering.py` refuses to render them, which is the
ratified posture already: field map N-1, *"dispatch holds safely on missing
published template; content never invented."*

Two open questions were minted for those gaps rather than answered — **OQ-206**
(the email and SMS token catalogs) and **OQ-207** (the payment-plan notice class
that BR-NOT-007 creates and no spec gives a body to).

WHO OWNS WHICH DESIGNER — the catalog is here for all of them anyway
--------------------------------------------------------------------
S91–S93 (bill residential / bill commercial / statement) are BILLING's
designers (US-BIL-021), and S94–S106 are notifications'. The catalogs sit
together in one file because US-NOT-005 §1 names the bill tokens among the
engine's sets and because ONE renderer serves every class — a second copy of the
bill's token list living in billing would be exactly the drift hard-won law 1
warns about. Ownership of the SCREEN is unchanged.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from dataclasses import replace as _dataclass_replace

from apps.notifications import models

#: Channel groups, matching the designer groups on the S8 templates card
#: (EP-NOT-02 capability matrix: *"group (printable/email/SMS/contracts)"*).
GROUP_PRINTABLE = "printable"
GROUP_EMAIL = "email"
GROUP_SMS = "sms"
GROUP_CONTRACT = "contracts"
#: ⚠ A FIFTH GROUP, 2026-08-17 (CR-009 in-app lane). `group` is the CHANNEL
#: family, and the platform gained a fourth channel — `models.CHANNEL_IN_APP` —
#: on the PO's ruling that in-app is the one channel that can prove the pipeline
#: works without a third party (BR-NOT-019). Exactly one class is in it today.
GROUP_IN_APP = "in_app"

# ══════════════════════════════════════════════════════════════════════════
# CR-007's CATEGORY AXIS — A SECOND, ORTHOGONAL GROUPING, NOT A REPLACEMENT
# ══════════════════════════════════════════════════════════════════════════
# CR-007 (PO, 2026-08-16) writes the SET-09 filter chips verbatim: *"category
# filter chips (All · Billing · Collections · Payments · Service & field ·
# Account lifecycle)"*, and groups its ~19-template inventory under the same
# five headings.
#
# ⚠ THIS IS NOT `group`. `group` is the CHANNEL family (printable / email / sms
# / contracts) and answers *"what kind of artifact is this"*; `category` answers
# *"what part of the business sends it"*. The past-due reminder is `printable`
# AND `Collections`; the payment receipt is `printable` AND `Payments`. Folding
# them into one column would have made the SET-09 chips filter by channel, which
# is not what the CR draws and not what a person filtering for "everything
# collections sends" is asking.
CAT_BILLING = "billing"
CAT_COLLECTIONS = "collections"
CAT_PAYMENTS = "payments"
CAT_SERVICE_FIELD = "service_field"
CAT_ACCOUNT_LIFECYCLE = "account_lifecycle"
#: `CR-188-BRC10` (PO 2026-10-22, answer 6: *"A: a new category, 'Account
#: access'"*). A person's own sign-in: the staff invitation and reset links,
#: and the customer portal's reset link. LAST in `CR_CATEGORIES` so the CR's
#: five keep their order.
CAT_ACCOUNT_ACCESS = "account_access"

#: In the CR's own order. The "All" chip is the ABSENCE of a filter and is a
#: screen concern, so it is deliberately not a value here — a sentinel category
#: nothing can be assigned to is a value a filter has to special-case forever.
CR_CATEGORIES: tuple[str, ...] = (
    CAT_BILLING,
    CAT_COLLECTIONS,
    CAT_PAYMENTS,
    CAT_SERVICE_FIELD,
    CAT_ACCOUNT_LIFECYCLE,
    CAT_ACCOUNT_ACCESS,
)

#: Where a listing's category came from. `cr` means CR-007 names this template
#: under this heading in the PO's own inventory and the value is QUOTED; `lane`
#: means the class predates CR-007, the CR does not name it, and this file
#: classified it. The split exists for the same reason `derived_spelling` does:
#: a reviewer can see which values are quoted and which are engineering
#: judgement without diffing against the change register by hand.
SOURCE_CR = "cr_007"
SOURCE_LANE = "lane_reading"


@dataclass(frozen=True)
class TemplateClass:
    """One template type: its channel, its palette, and its mandatory content.

    `tokens` is a WHITELIST and that is the whole mechanism — a token absent
    from it is rejected rather than rendered empty, which is what makes
    US-NOT-005 TC-5 (`{meter_no}` in a receipt) a save-time refusal instead of a
    blank space on a customer's receipt.

    `mandatory_content` carries the phrases a class may never ship without:
    A19 rule 1's *"nothing is due"* on the statement classes, and the regulatory
    footer marker on the regulated disconnect class (A19 r8 + US-NOT-007 TC-6).
    They are checked as SUBSTRINGS of the body, which is a floor and not a
    proof — see the module note in `rendering.py`.
    """

    code: str
    group: str
    channel: str
    source: str
    tokens: frozenset[str]
    #: Tokens whose CONTENT a spec ratifies but whose SPELLING this file chose.
    #: Kept apart so a reviewer can see which names are quoted and which are
    #: engineering vocabulary, rather than having to diff against A19 by hand.
    derived_spelling: frozenset[str] = frozenset()
    mandatory_content: tuple[str, ...] = ()
    #: WHY this class's mandatory content is mandatory, in one sentence, quoted
    #: into the refusal `rendering.validate_body` raises. Added 2026-08-18
    #: (CR-011 item 9) because that refusal used to explain A19 rule 1 and
    #: US-NOT-007 TC-6 to EVERY class that has mandatory content — so the person
    #: who deleted `{schedule_table}` from a payment-plan agreement was told
    #: about a statement saying "nothing is due", which is a true sentence about
    #: a different document. A refusal that explains the wrong rule is the kind
    #: of check hard-won law 7 warns about: it fires correctly and teaches
    #: nothing.
    mandatory_content_reason: str = ""
    notes: tuple[str, ...] = field(default_factory=tuple)
    #: `CR-190-BRC10` — tokens whose value may legitimately NOT EXIST for one
    #: customer (the welcome's first bill date on an account with no scheduled
    #: cycle). When one of these has no value, `rendering.render` DROPS THE
    #: PARAGRAPH that carries it — the blank-line-delimited block — instead of
    #: printing `——` in it. The PO: *"give the activation date , first bill
    #: date"*; a sentence promising a bill on `——` tells the customer nothing.
    #: Every other token keeps OQ-117's named absence. A subset of `tokens`.
    optional: frozenset[str] = frozenset()
    #: `CR-188-BRC10` — tokens whose VALUE is a live credential (a one-time
    #: sign-in link, an enrolment code). The email carries the real value; the
    #: KEPT copy (`frozen_documents.redact_credentials`, BR-NOT-027) replaces it
    #: with `frozen_documents.REDACTION_MARKER`. Declared here, beside the
    #: palette, so a portal class reuses the mechanism by naming its token.
    credential_tokens: frozenset[str] = frozenset()


#: A19 §1.1 masthead + §1.8 footer — present on every printable class because
#: every printable document is a letter from the utility. Quoted: the §1 tokens
#: `{utility_logo}`, `{utility_name}`, `{utility_address}` and
#: `{support_phone/email}`, which is written as one token in A19 and is two
#: values on every screen that shows it (Settings → Company holds them
#: separately), so it is split.
_UTILITY_IDENTITY = frozenset(
    {
        "utility_logo",
        "utility_name",
        "utility_address",
        "support_phone",
        "support_email",
    }
)

#: A19 §1.2 bill-meta band, verbatim.
_BILL_META = frozenset(
    {
        "account_no",
        "customer_name",
        "service_address",
        "bill_no",
        "cycle",
        "bill_date",
        "due_date",
    }
)

#: A19 §1.3 summary box, verbatim.
_BILL_SUMMARY = frozenset({"prev_balance", "payments", "current_charges", "total_due"})

#: A19 §1.4 per-service lines + §1.6 tax lines, verbatim.
_BILL_SERVICE_LINES = frozenset(
    {"meter_no", "prior_read", "current_read", "usage", "unit", "authority", "rate", "amount"}
)

#: A19 §2 shared header, verbatim: *"{utility_name}, {customer_name},
#: {account_no}, {balance}, {service_address}"*.
_NOTICE_HEADER = frozenset(
    {"utility_name", "customer_name", "account_no", "balance", "service_address"}
)

#: ⚠ THE MASTHEAD IS ON EVERY PRINTABLE CLASS, and that is a reading of A19
#: rather than a quotation of it, so it is written down here.
#:
#: A19 §1.1 defines the masthead for the bill; the r8 revision's printable table
#: says what makes each class DIFFERENT and does not restate what they share.
#: The receipt row, for instance, lists *"amount, method, confirmation number,
#: applied-to bill, balance before/after, processed-by staff name"* — the
#: transaction, not the letterhead.
#:
#: Every one of these documents is a LETTER FROM THE UTILITY, and BR-TEN-017
#: requires the utility's identity to be stamped AT RENDER on the artifact. A
#: receipt with no utility name on it is not a receipt anybody can file, and a
#: notice with no support phone number gives a customer no way to respond to it
#: — which on the disconnect class A19 §2 tier 3 makes explicit (*"Medical/
#: critical-care customers: call {support_phone}"*).
#:
#: So the masthead is available to every printable class. It is a LETTERHEAD and
#: not content: it adds no statement about the customer's account that a spec
#: has not ratified.
_PRINTABLE_MASTHEAD = _UTILITY_IDENTITY


#: `CR-188-BRC10` — the palette of both staff sign-in emails. No password
#: token, by ruling (answer 1).
_STAFF_ACCESS_TOKENS = frozenset(
    {"staff_name", "utility_name", "username", "sign_in_link", "link_expires_on"}
)

#: `CR-189-BRC10` — the palette both portal email-change messages share.
_PORTAL_EMAIL_CHANGE_TOKENS = frozenset(
    {"customer_name", "utility_name", "support_phone", "support_email"}
)

CATALOGS: dict[str, TemplateClass] = {
    # ── printable ────────────────────────────────────────────────────────
    "bill_residential": TemplateClass(
        code="bill_residential",
        group=GROUP_PRINTABLE,
        channel=models.CHANNEL_PRINT,
        source="A19 §1 + r8 revision (printable table, row 1)",
        tokens=_UTILITY_IDENTITY | _BILL_META | _BILL_SUMMARY | _BILL_SERVICE_LINES,
        notes=(
            "Designer S91 is BILLING's (US-BIL-021); the catalog lives here because one "
            "renderer serves every class and a second copy of this list would drift.",
        ),
    ),
    "bill_commercial": TemplateClass(
        code="bill_commercial",
        group=GROUP_PRINTABLE,
        channel=models.CHANNEL_PRINT,
        source="A19 §1 + r8 revision (printable table, row 2)",
        tokens=(
            _UTILITY_IDENTITY
            | _BILL_META
            | _BILL_SUMMARY
            | _BILL_SERVICE_LINES
            | frozenset({"po_number", "tax_id", "demand_kw", "demand_rate"})
        ),
        derived_spelling=frozenset({"po_number", "tax_id", "demand_kw", "demand_rate"}),
        notes=(
            "A19 rule 4: *'PO number, tax ID, per-meter table and demand charges only "
            "exist on the commercial bill.'* The four extra names are this file's "
            "spelling of content A19 ratifies in prose.",
        ),
    ),
    "statement": TemplateClass(
        code="statement",
        group=GROUP_PRINTABLE,
        channel=models.CHANNEL_PRINT,
        source="A19 §1 statement variant + r8 revision (printable table, row 3)",
        tokens=(
            _UTILITY_IDENTITY
            | _BILL_META - frozenset({"due_date"})
            | frozenset(
                {
                    "period_start",
                    "period_end",
                    "opening_balance",
                    "closing_balance",
                    "ledger_date",
                    "description",
                    "reference",
                    "charges",
                    "payments",
                    "running_balance",
                }
            )
        ),
        derived_spelling=frozenset(
            {
                "period_start",
                "period_end",
                "opening_balance",
                "closing_balance",
                "ledger_date",
                "description",
                "reference",
                "charges",
                "payments",
                "running_balance",
            }
        ),
        mandatory_content=("nothing is due",),
        notes=(
            "A19 r8: *'a running ledger over a date range — date / description / "
            "reference / charges / payments / balance. No rates, no meter reads, no due "
            "date.'* `due_date` is REMOVED from the bill meta set for that reason, and "
            "A19 rule 1's disclaimer is mandatory: *'both the printed statement and the "
            "statement email must say nothing is due, or customers pay twice.'*",
        ),
    ),
    "disconnect_notice": TemplateClass(
        code="disconnect_notice",
        group=GROUP_PRINTABLE,
        channel=models.CHANNEL_PRINT,
        source="A19 §2 (three tiers) + r8 revision (printable table, row 4)",
        tokens=(
            _PRINTABLE_MASTHEAD
            | _NOTICE_HEADER
            | frozenset(
                {
                    "pay_by_date",
                    "cut_date",
                    "reconnect_fee",
                    "support_phone",
                    "state_puc_ref",
                    "48h",
                    "certified_no",
                }
            )
        ),
        derived_spelling=frozenset({"certified_no"}),
        mandatory_content=("{state_puc_ref}",),
        notes=(
            "`{48h}` is A19 §2 tier 3's own spelling and is kept verbatim even though it "
            "starts with a digit — a catalog that silently renamed a signed token would "
            "reject the body the spec describes. `{certified_no}` is the field map's "
            "certified-mail number block, filled from the provider response at dispatch "
            "(r10 #8). BR-CUS-039: `{reconnect_fee}` renders a tenant CHARGE CODE and is "
            "never a constant — US-NOT-009 §5 marks a missing one an error, never a "
            "default. US-NOT-007 TC-6: the regulatory footer cannot be removed from this "
            "class, which is why `{state_puc_ref}` is mandatory content.",
        ),
    ),
    # ── BR-NOT-014's THREE SLOTS, one per dunning stage ──────────────────
    # PO ruling 2026-08-16 closing OQ-243, verbatim: *"a  Give the disconnection
    # notice three separate slots — one per stage"* — option (a) over (b)
    # EXPLICITLY, so the tier is a CLASS and not a fourth column on the variant
    # key. BR-NOT-014 CONFIRMED: *"the registry holds a separate template per
    # tier and the ladder selects by tier, never by seniority of wording."*
    #
    # ⚠ EACH TIER'S TOKEN SET IS ITS OWN SIGNED SENTENCE'S, NOT THE UNION.
    # A19 §2 writes one body per tier and OQ-243 quotes all three in full. The
    # whitelist is per tier because that is the whole mechanism: a 10-day
    # warning that could carry `{48h}` and `{certified_no}` is a 10-day warning
    # that can be written as a 48-hour certified letter, which is precisely the
    # confusion the three slots exist to make impossible. Narrowing costs
    # nothing today — no tier has a body (OQ-253) — and it is free only while
    # that is true.
    #
    # ⚠ **AMENDED 2026-08-17 — THE THREE SLOTS ARE NO LONGER EMPTY.** This block
    # said *"AND ALL THREE ARE EMPTY … whose five sentences no signed document
    # writes — OQ-253"* until the PO ruled that the PLATFORM writes those five
    # sentences. Verbatim, 2026-08-17: *"we will take this option; we provide
    # default option for all 5 you ahve mentioned; if Utility wants to over ride
    # it let them do it; I can also give tick boxes if required to add 5"* and
    # *"you build default langauge and let Utility user change it as they want"*
    # (12-governance/11-change-requests.md §"CR-007 · The disconnect notices").
    #
    # So each tier gains ONE token — `{rights_footer}` — and it is MANDATORY
    # CONTENT alongside `{state_puc_ref}`. Two non-removable phrases, and the
    # pair is the rule: `{state_puc_ref}` is the regulator's reference
    # (US-NOT-007 TC-6) and `{rights_footer}` is the paragraph that tells the
    # customer what to do with it. A tier body that could ship with the reference
    # and no rights, or with rights and no reference, would be half of a
    # regulated letter.
    #
    # `{rights_footer}` is `derived_spelling`: no signed document writes that
    # name in braces. What A19 r8 ratifies is that the CONTENT is on the class;
    # the token spelling and the five-clause structure behind it are
    # `apps/notifications/rights_footer.py`'s, authored to the ruling above.
    # It expands in a PRE-PASS (see `rights_footer.expand`) so a clause's own
    # `{support_phone}` still merges.
    "disconnect_notice_10_day": TemplateClass(
        code="disconnect_notice_10_day",
        group=GROUP_PRINTABLE,
        channel=models.CHANNEL_PRINT,
        source="A19 §2 tier 1 (10-day), quoted in OQ-243 + BR-NOT-014",
        tokens=(
            _PRINTABLE_MASTHEAD
            | _NOTICE_HEADER
            | frozenset({"pay_by_date", "state_puc_ref", "rights_footer"})
        ),
        derived_spelling=frozenset({"rights_footer"}),
        mandatory_content=("{state_puc_ref}", "{rights_footer}"),
        notes=(
            "A19 §2 tier 1, verbatim: *'Your account is past due in the amount of "
            "{balance}. Please pay by {pay_by_date} (10 days) to avoid service "
            "interruption.'* `{cut_date}`, `{48h}`, `{certified_no}` and "
            "`{reconnect_fee}` are DELIBERATELY ABSENT — this is the warning, not the "
            "final letter, and a whitelist is the only thing that keeps the two from "
            "being written into each other (BR-NOT-014).",
        ),
    ),
    "disconnect_notice_5_day": TemplateClass(
        code="disconnect_notice_5_day",
        group=GROUP_PRINTABLE,
        channel=models.CHANNEL_PRINT,
        source="A19 §2 tier 2 (5-day final reminder), quoted in OQ-243 + BR-NOT-014",
        tokens=(
            _PRINTABLE_MASTHEAD
            | _NOTICE_HEADER
            | frozenset({"cut_date", "reconnect_fee", "state_puc_ref", "rights_footer"})
        ),
        derived_spelling=frozenset({"rights_footer"}),
        mandatory_content=("{state_puc_ref}", "{rights_footer}"),
        notes=(
            "A19 §2 tier 2, verbatim: *'FINAL REMINDER. Service to {service_address} is "
            "scheduled for disconnection on {cut_date} unless {balance} is received. A "
            "reconnect fee of {reconnect_fee} applies to restore service.'* BR-CUS-039: "
            "`{reconnect_fee}` renders a tenant CHARGE CODE and is never a constant — "
            "US-NOT-009 §5 marks a missing one an error, never a default.",
        ),
    ),
    "disconnect_notice_48_hour": TemplateClass(
        code="disconnect_notice_48_hour",
        group=GROUP_PRINTABLE,
        channel=models.CHANNEL_PRINT,
        source="A19 §2 tier 3 (48-hour certified), quoted in OQ-243 + BR-NOT-014",
        tokens=(
            _PRINTABLE_MASTHEAD
            | _NOTICE_HEADER
            | frozenset(
                {
                    "cut_date",
                    "48h",
                    "support_phone",
                    "certified_no",
                    "state_puc_ref",
                    "rights_footer",
                }
            )
        ),
        derived_spelling=frozenset({"certified_no", "rights_footer"}),
        mandatory_content=("{state_puc_ref}", "{rights_footer}"),
        notes=(
            "A19 §2 tier 3, verbatim: *'NOTICE OF DISCONNECTION. Service will be "
            "disconnected on {cut_date} ({48h}). To avoid disconnection pay {balance} "
            "immediately. Medical/critical-care customers: call {support_phone}.'* "
            "`{48h}` keeps A19's own spelling even though it starts with a digit — a "
            "catalog that silently renamed a signed token would reject the body the spec "
            "describes. `{certified_no}` is the field map's certified-mail number block, "
            "filled from the provider response at dispatch (r10 #8). BR-CUS-039 forces "
            "certified mail on this tier and only this one.",
        ),
    ),
    "dunning": TemplateClass(
        code="dunning",
        group=GROUP_PRINTABLE,
        channel=models.CHANNEL_PRINT,
        source="A19 r8 revision (printable table, row 5) + A13 reminder copy",
        tokens=(
            _PRINTABLE_MASTHEAD
            | frozenset({"first_name", "account", "balance"})
            | _NOTICE_HEADER
            | frozenset({"stage_day", "days_late", "late_fee", "unpaid_bills"})
        ),
        derived_spelling=frozenset({"stage_day", "days_late", "late_fee", "unpaid_bills"}),
        notes=(
            "`{first_name}`, `{account}` and `{balance}` are A13's reminder copy verbatim "
            "— US-NOT-005 §1 names A13 as a token source for exactly this class. A19 "
            "rule 2 and US-NOT-007: dunning is a REMINDER and carries NO regulatory "
            "footer, so `{state_puc_ref}` is deliberately absent from this catalog and a "
            "body using it is refused. BR-REP-016: `{stage_day}` renders the tenant's "
            "cadence config (seeded 7/14/30), never a constant.",
        ),
    ),
    "receipt": TemplateClass(
        code="receipt",
        group=GROUP_PRINTABLE,
        channel=models.CHANNEL_PRINT,
        source="A19 r8 revision (printable table, row 6) + A13 receipt copy",
        tokens=_PRINTABLE_MASTHEAD
        | frozenset(
            {
                "first_name",
                "customer_name",
                "account_no",
                "amount",
                "date",
                "balance",
                "confirmation",
                "method",
                "applied_to_bill",
                "balance_before",
                "balance_after",
                "processed_by",
            }
        ),
        derived_spelling=frozenset(
            {"method", "applied_to_bill", "balance_before", "balance_after", "processed_by"}
        ),
        notes=(
            "A19 r8: *'One transaction — amount, method, confirmation number, applied-to "
            "bill, balance before/after, processed-by staff name. No usage, no rates, no "
            "due date.'* The three absences are enforced by this being a WHITELIST: "
            "`{usage}`, `{rate}` and `{due_date}` are simply not in it, which is "
            "US-NOT-005 TC-5 (`{meter_no}` in a receipt body is refused at save).",
        ),
    ),
    # ── contracts (S67) ──────────────────────────────────────────────────
    "contract_payment_plan": TemplateClass(
        code="contract_payment_plan",
        group=GROUP_CONTRACT,
        channel=models.CHANNEL_PRINT,
        source="A19 §3 (payment-plan agreement) + BR-NOT-004 type ①",
        tokens=_PRINTABLE_MASTHEAD
        | frozenset(
            {
                "utility_name",
                "customer_name",
                "account_no",
                "today",
                "balance",
                "n",
                "down",
                "payment_method",
                "missed_count",
                "customer_signature",
                "date",
                # ⚠ THE ONE TOKEN HERE THAT A19 DOES NOT WRITE IN BRACES, AND IT
                # IS RULED RATHER THAN CHOSEN. A19 §3.2 names *"schedule table
                # (# · due date · amount · remaining)"* as CONTENT and gives it
                # no token, which is what OQ-244 was minted over. BR-NOT-016 is
                # the answer and it is CONFIRMED — PO 2026-08-16, verbatim:
                # *"a<TAB>Print the schedule inside the agreement"*, written up
                # as **"THE PAYMENT-PLAN AGREEMENT PRINTS ITS INSTALMENT
                # SCHEDULE INSIDE THE AGREEMENT, never as an attachment. The
                # contract body carries a merge token for the table itself."**
                # So the token exists because a rule says it must; only the
                # SPELLING is this file's, and it is marked `derived_spelling`
                # below with every other chosen name.
                "schedule_table",
            }
        ),
        derived_spelling=frozenset({"schedule_table"}),
        # ⚠ NON-REMOVABLE, AND THE PRECEDENT IS `staff_bulk_summary`'s FAILURE
        # COUNT. BR-NOT-016 does not say "the agreement may show a schedule"; it
        # says the schedule prints INSIDE the agreement, because *"a customer
        # who signed a total without dates agreed to a number rather than to a
        # schedule"*. A body that drops the token would be exactly that
        # document, and a utility editing this default cannot produce one: the
        # save is refused (`rendering.validate_body`).
        mandatory_content=("{schedule_table}",),
        mandatory_content_reason=(
            "BR-NOT-016 CONFIRMED (PO 2026-08-16, *'Print the schedule inside the "
            "agreement'*): the instalment schedule prints INSIDE this agreement and never "
            "as an attachment, because a customer who signs a total with no due dates has "
            "agreed to a number rather than to a schedule. Keep `{schedule_table}` in the "
            "body; edit everything around it as you like."
        ),
        notes=(
            "⚠ `{schedule_table}` TAKES A PRE-RENDERED BLOCK FROM ITS CALLER AND NOTHING "
            "IN THIS REPO BUILDS ONE YET. `rendering.render` substitutes single values; it "
            "has no repeating construct, so it cannot turn a plan's instalment rows into "
            "'# · due date · amount · remaining'. Until something does, the token renders "
            "the NAMED ABSENCE every unsupplied catalogued token renders — `——` — and the "
            "seeded body tells the reader on its face not to sign a schedule that is "
            "blank. That remainder is what OQ-244 still holds: not *whether* this class "
            "exists (ruled: it does, CR-011 item 9) and not *where* the schedule prints "
            "(ruled: inside, BR-NOT-016), but HOW the renderer prints a repeating block.",
            "Every other token is A19 §3 verbatim, with ONE deliberate omission: "
            "`{utility_rep}` "
            "is NOT here. A19's 2026-08-08 addendum SUPERSEDES the countersign block — "
            "*'the payment-plan agreement executes via the customer's e-signature alone; "
            "the utility countersign line is dropped'* (BR-CUS-044). A catalog that still "
            "offered the token would let a designer put a signature line on a contract "
            "that nobody is supposed to sign.",
        ),
    ),
    # ── in-app (CR-009, BR-NOT-019/020) ──────────────────────────────────
    "staff_bulk_summary": TemplateClass(
        code="staff_bulk_summary",
        group=GROUP_IN_APP,
        channel=models.CHANNEL_IN_APP,
        source="CR-009 PO ruling 2026-08-17 (fourth set), ruling 2 — BR-NOT-020",
        # ⚠ NO MASTHEAD TOKENS. `_PRINTABLE_MASTHEAD` is on every printable
        # class because *"every one of these documents is a LETTER FROM THE
        # UTILITY"*; this one is the PRODUCT talking to the utility's own
        # operator inside the product, so the utility's name and address are
        # not merely unnecessary — offering them would let a body be written
        # that renders `——` in a clerk's bell on any tenant that has not
        # filled in Settings → Company. The whitelist is the enforcement.
        tokens=frozenset(
            {
                "operation",
                "total_count",
                "failed_count",
                "finished_at",
            }
        ),
        derived_spelling=frozenset({"operation", "total_count", "failed_count", "finished_at"}),
        # ⚠ THE FAILURE COUNT IS NON-REMOVABLE, AND THAT IS THE POINT OF PUTTING
        # IT HERE RATHER THAN IN A COMMENT. The PO's ruling has two halves and
        # the second is the one a tidy implementation loses: *"the message states
        # COMPLETION, and where the operation had failures it must say HOW MANY —
        # a summary that hides a failure count is the same failure as sending a
        # thousand messages, in the opposite direction."* `mandatory_content` is
        # checked as a substring of the body by `rendering.validate_body`, so a
        # utility (or a lane) editing this template to read "Bulk action
        # completed." and nothing else is REFUSED AT SAVE. A clerk can never end
        # up with a reassuring summary of a run that failed 87 times.
        mandatory_content=("{failed_count}",),
        notes=(
            "PO verbatim, 2026-08-17: *'for single notification send 1 message and for "
            "bulk action also send 1 message only saying nulk action is completed'*. This "
            "is the class that ONE message renders from. Its five tokens are the smallest "
            "set that can carry the ruling: what ran (`{operation}`), over how many "
            "(`{total_count}`), how many failed (`{failed_count}`, mandatory) and when it "
            "finished (`{finished_at}`). No account, customer or money token is in the "
            "whitelist — a summary is about a RUN, and a per-account figure in it would "
            "be the first step back towards one message per account, which is the "
            "behaviour BR-NOT-020 exists to forbid. `{operation}` is a human phrase "
            "supplied by the caller ('Billing run', 'Payment import'), not an event key: "
            "the reader is a clerk, not a developer.",
        ),
    ),
    # ── in-app · the field tells the office (CR-168-BRC10 §F, FIELD-2) ──
    # TECHNICIAN SYNC DESIGN (5). No masthead and no contact tokens, for
    # `staff_bulk_summary`'s reason: the product talking to the utility's own
    # clerk. `{order_no}` is mandatory — a message that does not say WHICH job
    # closed is one a clerk cannot act on.
    "staff_field_work": TemplateClass(
        code="staff_field_work",
        group=GROUP_IN_APP,
        channel=models.CHANNEL_IN_APP,
        source="CR-168-BRC10 §F — TECHNICIAN SYNC DESIGN (5), PO 2026-10-04 (design ours)",
        tokens=frozenset({"order_no", "event", "count", "at"}),
        derived_spelling=frozenset({"order_no", "event", "count", "at"}),
        mandatory_content=("{order_no}",),
        notes=(
            "One message per field event on one job: closed (with the count of required "
            "photos still uploading), photos complete (Accept is available), or items "
            "held for review. `{event}` is a phrase the platform supplies; `{count}` is "
            "the photos uploading or the items held. Sent to the person who sent the job "
            "to the field; a Needs review also reaches every System Admin (BR-NOT-021).",
        ),
    ),
    # ── email · the scheduled report a clerk never has to remember to run ──
    #
    # `CR-142-BRC07` `P4.10` (2026-09-27). The task line is nine words —
    # *"The outbound queue carries the link, not the file"* — and this palette
    # is where that sentence stops being prose and starts being enforced.
    #
    # ⚠ **`{report_link}` IS MANDATORY CONTENT, AND IT IS THE WHOLE TASK.**
    # `rendering.validate_body` checks mandatory content as a substring at
    # SAVE, so a utility (or a lane) editing this body down to *"Your report
    # is ready."* is REFUSED. A scheduled-report email with no link is an
    # email that delivers nothing, and the person it was scheduled for has no
    # way to find the file from it — which looks exactly like the product
    # working. The precedent is `staff_bulk_summary`'s `{failed_count}`.
    #
    # ⚠ **NO ATTACHMENT TOKEN, AND THAT IS THE RULING RATHER THAN A GAP.**
    # `BR-NOT-005` is queue-only and the brief's own outcome sentence is
    # *"recipients get a link that respects their permissions"* — a file on an
    # envelope respects nobody's permissions once it has left the building,
    # and `BR-REP-018` keeps the artifact for three days behind the same
    # sign-in every other screen is behind. There is no token here that could
    # carry one.
    #
    # ⚠ **NO MASTHEAD AND NO `_CONTACT`, FOR `staff_bulk_summary`'s REASON.**
    # This is the PRODUCT writing to the utility's own clerk about a report
    # that clerk asked for. Offering `{utility_name}` would let a body be
    # authored that renders a named absence at a member of staff on any tenant
    # that has not filled in Settings -> Company.
    "email_scheduled_report": TemplateClass(
        code="email_scheduled_report",
        group=GROUP_EMAIL,
        channel=models.CHANNEL_EMAIL,
        source=(
            "CR-142-BRC07 P4.10 (05-prototype/09 Reports Build Brief.pdf p15, read as an "
            "IMAGE per B14 rule 42) - BR-REP-017 / BR-REP-007 / BR-NOT-005. LANE-AUTHORED "
            "WORDING: no signed document writes this body and no PO ruling has ratified "
            "these words; OQ-REP-12757 is where they are settled."
        ),
        tokens=frozenset(
            {
                "staff_name",
                "report_name",
                "ran_at",
                "report_link",
                "expires_on",
            }
        ),
        derived_spelling=frozenset(
            {"staff_name", "report_name", "ran_at", "report_link", "expires_on"}
        ),
        mandatory_content=("{report_link}",),
        mandatory_content_reason=(
            "CR-142-BRC07 P4.10: the outbound queue carries the LINK and never the file. "
            "A body without {report_link} is an email that tells a clerk their report ran "
            "and gives them no way to open it - which reads as the product working."
        ),
        notes=(
            "`{expires_on}` is BR-REP-018's three-day window, stated because a link that "
            "will stop working is worse than one that says when. It is the run's own "
            "`expires_at`, computed by `run_history`, never a date this module invents.",
        ),
    ),
    # ── email · a member of staff's own sign-in · CR-188-BRC10 ────────────
    #
    # PO 2026-10-22, answer 1: *"email a one-time sign-in link instead, no
    # password."* **There is no password token in either palette, so
    # `rendering.validate_body` REFUSES a body that adds one** — the ruling is
    # structural, not a convention. `{sign_in_link}` is MANDATORY content in
    # every language variant: an invitation with no link cannot be acted on.
    "staff_user_invite": TemplateClass(
        code="staff_user_invite",
        group=GROUP_EMAIL,
        channel=models.CHANNEL_EMAIL,
        source=(
            "CR-188-BRC10 (PO 2026-10-22, decision log 'Staff invitation email: a one-time "
            "sign-in link, not a password; six answers'). LANE-AUTHORED WORDING, a seeded "
            "default each utility edits."
        ),
        tokens=_STAFF_ACCESS_TOKENS,
        derived_spelling=_STAFF_ACCESS_TOKENS,
        mandatory_content=("{sign_in_link}",),
        mandatory_content_reason=(
            "CR-188-BRC10: the invitation carries a one-time sign-in link and never a "
            "password. A body without {sign_in_link} gives the new user no way in."
        ),
        credential_tokens=frozenset({"sign_in_link"}),
    ),
    "staff_password_reset_link": TemplateClass(
        code="staff_password_reset_link",
        group=GROUP_EMAIL,
        channel=models.CHANNEL_EMAIL,
        source=(
            "CR-188-BRC10 (PO 2026-10-22, answer 4: 'email it as well' - read as a one-time "
            "link, never a password). LANE-AUTHORED WORDING, a seeded default each utility "
            "edits."
        ),
        tokens=_STAFF_ACCESS_TOKENS,
        derived_spelling=_STAFF_ACCESS_TOKENS,
        mandatory_content=("{sign_in_link}",),
        mandatory_content_reason=(
            "CR-188-BRC10: a password reset email carries a one-time link and never a "
            "password. A body without {sign_in_link} gives the person no way back in."
        ),
        credential_tokens=frozenset({"sign_in_link"}),
    ),
    # ── email · a locked-out customer changing their email · CR-189-BRC10 ──
    #
    # PO 2026-10-22 (decision log *"Portal forgot-password: one message for
    # every address, plus a self-service 'update your registered email'
    # path"*): *"A new email never takes effect until a code sent to it is
    # confirmed"* and *"The OLD email, if any, is told 'Your registered email
    # was changed'"*. The code is MANDATORY in the first; the second carries no
    # link and no code, only the masked new address and the office's contacts.
    "portal_enrolment_code": TemplateClass(
        code="portal_enrolment_code",
        group=GROUP_EMAIL,
        channel=models.CHANNEL_EMAIL,
        source=(
            "CR-068 wave E queue row; wording added by CR-189-BRC10 (DEF-CWP-10402). "
            "LANE-AUTHORED WORDING, a seeded default each utility edits."
        ),
        tokens=frozenset({"utility_name", "support_phone", "support_email", "code"}),
        derived_spelling=frozenset({"utility_name", "support_phone", "support_email", "code"}),
        mandatory_content=("{code}",),
        mandatory_content_reason=(
            "The message exists to carry the one-time code. Without {code} the "
            "customer cannot prove the contact is theirs."
        ),
        credential_tokens=frozenset({"code"}),
    ),
    "portal_email_change_code": TemplateClass(
        code="portal_email_change_code",
        group=GROUP_EMAIL,
        channel=models.CHANNEL_EMAIL,
        source=(
            "CR-189-BRC10 (PO 2026-10-22). LANE-AUTHORED WORDING, a seeded default each "
            "utility edits."
        ),
        tokens=_PORTAL_EMAIL_CHANGE_TOKENS | frozenset({"code"}),
        derived_spelling=_PORTAL_EMAIL_CHANGE_TOKENS | frozenset({"code"}),
        mandatory_content=("{code}",),
        mandatory_content_reason=(
            "CR-189-BRC10: the new address is confirmed by typing this code. A body "
            "without {code} leaves the customer unable to finish the change."
        ),
        # The kept copy never holds a live code (decision log 2026-10-22).
        credential_tokens=frozenset({"code"}),
    ),
    "portal_email_changed_notice": TemplateClass(
        code="portal_email_changed_notice",
        group=GROUP_EMAIL,
        channel=models.CHANNEL_EMAIL,
        source=(
            "CR-189-BRC10 (PO 2026-10-22). LANE-AUTHORED WORDING, a seeded default each "
            "utility edits."
        ),
        tokens=_PORTAL_EMAIL_CHANGE_TOKENS | frozenset({"new_email_masked"}),
        derived_spelling=_PORTAL_EMAIL_CHANGE_TOKENS | frozenset({"new_email_masked"}),
    ),
}


#: Classes a later ruling REPLACED, and what replaced them. They stay in
#: `CATALOGS` because live code still names them; they are hidden from every
#: LISTING surface, so a person never sees two rows offering one document two
#: homes.
#:
#: `disconnect_notice` is the whole of it today. BR-NOT-014 (PO 2026-08-16)
#: gives the disconnection notice THREE slots, so the single class is no longer
#: the shape the rule describes — but `apps/notifications/notices.py` still
#: resolves it by name, and rewiring the dunning ladder is a behaviour change
#: this settings lane may not make silently. **DEF-193 is filed for that
#: wiring**, and until it lands the single class is what `generate_disconnect_
#: notice` asks for and it refuses, exactly as it did before (no body, OQ-253).
SUPERSEDED_CLASSES: dict[str, str] = {
    "disconnect_notice": (
        "BR-NOT-014 (PO 2026-08-16, closing OQ-243) replaced the single disconnect "
        "class with THREE — disconnect_notice_10_day, disconnect_notice_5_day and "
        "disconnect_notice_48_hour, one per dunning stage. This row is retained because "
        "`notices.generate_disconnect_notice` resolved it by name until CR-007 (DEF-193) and "
        "deleting it would break the ladder before its replacement is wired. It is "
        "hidden from the template catalog so nobody edits a slot nothing will select."
    ),
}


#: What a CATALOG ROW says about itself on SET-09, for EVERY class this module
#: knows — catalogued or not, seeded or not. One entry per class, so the catalog
#: cannot list a class whose category nobody chose.
#:
#: `used_by` answers the CR's *"Used by (which system event/flow consumes it)"*
#: column and is a STATEMENT OF FACT ABOUT THIS CODEBASE, not an aspiration:
#: where nothing consumes a class yet it says so, because the CR's own standalone
#: ruling (*"connecting it with actual workflow ... we will take acare later"*)
#: means several of these have no consumer by design and a column that implied
#: one would be the first thing a person trusted.
@dataclass(frozen=True)
class TemplateListing:
    """One row of the SET-09 catalog: where it files, and who consumes it."""

    code: str
    #: The tenant-facing NAME. Not customer-facing — it appears on no rendered
    #: document — and no rule governs it, which is why the seeder's own `name`
    #: values are reused verbatim where one exists.
    name: str
    category: str
    #: CR-007's *"Kind (delivery format)"* column, in the CR's own words for the
    #: templates it names.
    kind: str
    #: ⚠ CUSTOMER-FACING COPY (CR-016, 2026-08-19). This string is rendered
    #: VERBATIM in the "Used by" column of Settings → Configure → Templates, so
    #: a System Admin at a small utility reads every word of it. It used to
    #: carry the provenance — `BR-NOT-014`, `OQ-206`, `CR-007 provision`, and in
    #: one row the dotted path `apps/notifications/bulk_summary` — and the
    #: Product Owner photographed that screen: *"Youa re also adding internal
    #: content and BR codes on screen, that is not required"*.
    #:
    #: The HONESTY stays and the PROVENANCE moves here. Where nothing consumes a
    #: class the value still says so plainly ("Not in use yet — …"), because the
    #: CR's own standalone ruling (*"connecting it with actual workflow ... we
    #: will take acare later"*) means several of these have no consumer BY
    #: DESIGN, and a column that implied one would be the first thing a person
    #: trusted. What changed is only the words, never the claim.
    #:
    #: The rules behind the values, for anyone reading this file: the three
    #: disconnect tiers are BR-NOT-014; the reminder pair is BR-NOT-008; the
    #: bulk-action summary is BR-NOT-020 with BR-NOT-021's admin copy (OQ-261,
    #: closed 2026-08-17); the "no wording written" rows are OQ-206 / OQ-207;
    #: the "does not send this" rows are CR-007 provisions; Work / Field work /
    #: Broadcast are R5 scope, OQ-249.
    #:
    #: G28 (`10-scripts/gates/g28_internal_references.py`) fails the build if an
    #: id, a dotted module path or a route re-enters this field.
    used_by: str
    #: SOURCE_CR when CR-007 files this template under this category itself;
    #: SOURCE_LANE when the class predates the CR and this file classified it.
    category_source: str = SOURCE_LANE


LISTINGS: dict[str, TemplateListing] = {
    # ── Billing ──────────────────────────────────────────────────────────
    "bill_insert": TemplateListing(
        code="bill_insert",
        name="Bill insert",
        category=CAT_BILLING,
        kind="PDF page",
        used_by="Not in use yet — the bill run does not attach inserts.",
        category_source=SOURCE_CR,
    ),
    "email_corrected_bill": TemplateListing(
        code="email_corrected_bill",
        name="Corrected bill notice",
        category=CAT_BILLING,
        kind="Email",
        used_by="Sent when a bill is corrected.",
        category_source=SOURCE_CR,
    ),
    # ── Collections ──────────────────────────────────────────────────────
    "dunning": TemplateListing(
        code="dunning",
        name="Past-due reminder",
        category=CAT_COLLECTIONS,
        kind="Print",
        # DEF-PAY-10651 (PO 2026-10-29, 2A) — the past-due reminder's letter,
        # posted only when no email or consented text reaches the customer.
        used_by="Mailed when email and text can't reach them.",
        category_source=SOURCE_CR,
    ),
    "email_past_due": TemplateListing(
        code="email_past_due",
        name="Past-due reminder · Email",
        category=CAT_COLLECTIONS,
        kind="Email",
        used_by="Sent when an account falls past due.",
        category_source=SOURCE_CR,
    ),
    "sms_past_due": TemplateListing(
        code="sms_past_due",
        name="Past-due reminder · SMS",
        category=CAT_COLLECTIONS,
        kind="SMS",
        used_by="Sent when an account falls past due.",
        category_source=SOURCE_CR,
    ),
    "disconnect_notice_10_day": TemplateListing(
        code="disconnect_notice_10_day",
        name="Disconnect notice · 10-day warning",
        category=CAT_COLLECTIONS,
        kind="Print + email",
        used_by="Disconnection notice — first stage.",
        category_source=SOURCE_CR,
    ),
    "disconnect_notice_5_day": TemplateListing(
        code="disconnect_notice_5_day",
        name="Disconnect notice · 5-day final reminder",
        category=CAT_COLLECTIONS,
        kind="Print + email",
        used_by="Disconnection notice — second stage.",
        category_source=SOURCE_CR,
    ),
    "disconnect_notice_48_hour": TemplateListing(
        code="disconnect_notice_48_hour",
        name="Disconnect notice · 48-hour certified",
        category=CAT_COLLECTIONS,
        kind="Certified print + email",
        used_by="Disconnection notice — final stage, sent by certified mail.",
        category_source=SOURCE_CR,
    ),
    "sms_disconnect": TemplateListing(
        code="sms_disconnect",
        name="Disconnect notice · SMS supplement",
        category=CAT_COLLECTIONS,
        kind="SMS",
        used_by="Not in use yet. When it is, it goes out alongside the letter — never instead of it.",
    ),
    "contract_payment_plan": TemplateListing(
        code="contract_payment_plan",
        name="Payment plan agreement",
        category=CAT_COLLECTIONS,
        kind="PDF + email",
        used_by="Not in use yet — creating a payment plan does not send the agreement.",
        category_source=SOURCE_CR,
    ),
    "writeoff_notice": TemplateListing(
        code="writeoff_notice",
        name="Write-off notice",
        category=CAT_COLLECTIONS,
        kind="Letter",
        used_by="Sent when a write-off is approved.",
        category_source=SOURCE_CR,
    ),
    "plan_notice_upcoming": TemplateListing(
        code="plan_notice_upcoming",
        name="Payment plan · instalment due",
        category=CAT_COLLECTIONS,
        kind="Email",
        used_by="Sent before a payment plan instalment falls due.",
    ),
    "plan_notice_missed": TemplateListing(
        code="plan_notice_missed",
        name="Payment plan · instalment missed",
        category=CAT_COLLECTIONS,
        kind="Email",
        used_by="Sent when a payment plan instalment is missed.",
    ),
    "plan_notice_void": TemplateListing(
        code="plan_notice_void",
        name="Payment plan · plan voided",
        category=CAT_COLLECTIONS,
        kind="Email",
        used_by="Payment plans. The wording is ready; nothing voids a plan yet.",
    ),
    # ── Payments ─────────────────────────────────────────────────────────
    "receipt": TemplateListing(
        code="receipt",
        name="Payment receipt",
        category=CAT_PAYMENTS,
        kind="Print",
        used_by="Sent when a payment is recorded.",
        category_source=SOURCE_CR,
    ),
    "email_payment_receipt": TemplateListing(
        code="email_payment_receipt",
        name="Payment receipt · Email",
        category=CAT_PAYMENTS,
        kind="Email",
        used_by="Sent when a payment is recorded.",
        category_source=SOURCE_CR,
    ),
    "sms_payment_received": TemplateListing(
        code="sms_payment_received",
        name="Payment receipt · SMS",
        category=CAT_PAYMENTS,
        kind="SMS",
        used_by="Sent when a payment is recorded.",
        category_source=SOURCE_CR,
    ),
    "email_autopay": TemplateListing(
        code="email_autopay",
        name="Autopay & scheduled payment",
        category=CAT_PAYMENTS,
        kind="Email",
        used_by="Not in use yet — signing up for autopay does not send this.",
        category_source=SOURCE_CR,
    ),
    "email_payment_failed": TemplateListing(
        code="email_payment_failed",
        name="Payment failed / NSF",
        category=CAT_PAYMENTS,
        kind="Email + SMS",
        used_by="Sent when a payment comes back.",
        category_source=SOURCE_CR,
    ),
    # ⚠ ADDED 2026-08-30 · DEF-2473 — THE PRINT HALF OF THE ROW ABOVE, AND IT
    # SHIPS WITH NO WORDING ON PURPOSE.
    #
    # `email_payment_failed` is an EMAIL class and it is the only class the
    # returned-payment letter had. BR-NOT-024's print floor (PO 2026-08-29,
    # *"don't switch of print for any document it is awayls on"*) adds
    # `pdf_print` to every `payment` write, so the bounce letter was being
    # QUEUED FOR PRINT PINNED TO AN EMAIL CLASS — measured on the branch tip
    # with the email switch off: one row, channel `pdf_print`, template_code
    # `email_payment_failed`. The floor is signed law and correct; the missing
    # print class is the gap, and this is it.
    #
    # **WHY IT IS EMPTY.** Nobody has written the wording for a printed
    # returned-payment letter, and this lane will not invent it: it is a
    # document about somebody's money that tells them a payment they believed
    # had cleared did not, and a letter we improvised is a worse defect than
    # the one being fixed (BR-NOT-015). It is LISTED so a utility can find it
    # and write their own, and `seed_templates.absent_reason` says why it is
    # blank — the same posture the four contracts hold.
    #
    # ⚠ **IT IS THE FIRST CLASS TO BE LISTED WITH NO WORDING AND NO OFFERED
    # DEFAULT**, so the SET-09 arithmetic moves from *37 listed · 33 published
    # · 4 offered · 0 with no wording* to *38 · 33 · 4 · 1*.
    # `test_def_210_authored_template_bodies.py` carries those figures and the
    # reasoning; this class joins its `STILL_EMPTY` guard, so authoring a body
    # here goes RED and the lane that does it has to say which ruling let them.
    "payment_failed_letter": TemplateListing(
        code="payment_failed_letter",
        name="Payment failed / NSF · letter",
        category=CAT_PAYMENTS,
        kind="Print",
        used_by="The printed letter sent when a payment comes back.",
        category_source=SOURCE_CR,
    ),
    "email_refund_issued": TemplateListing(
        code="email_refund_issued",
        name="Refund issued",
        category=CAT_PAYMENTS,
        kind="Email",
        used_by="Sent when a refund is paid.",
        category_source=SOURCE_CR,
    ),
    "email_credit_issued": TemplateListing(
        code="email_credit_issued",
        name="Credit issued",
        category=CAT_PAYMENTS,
        kind="Email",
        used_by="Sent when a credit is issued.",
    ),
    # ── Service & field ──────────────────────────────────────────────────
    # PO 2026-08-16, verbatim: *"CR-007's 'Service & field' template category —
    # appointment, work completed, door hanger, outage — is wording, and wording
    # can exist before the flow that sends it. Those templates are catalogued
    # and editable now."* They create NO work-order table and do not touch
    # OQ-249: a template is a piece of wording, and the flow that sends it is R5.
    "service_appointment": TemplateListing(
        code="service_appointment",
        name="Appointment scheduled / reminder",
        category=CAT_SERVICE_FIELD,
        kind="Email + SMS",
        used_by="Sent when a job with a customer is first given its date.",
        category_source=SOURCE_CR,
    ),
    "service_work_completed": TemplateListing(
        code="service_work_completed",
        name="Work completed summary",
        category=CAT_SERVICE_FIELD,
        kind="Email",
        used_by="Sent when the office accepts a job that passed.",
        category_source=SOURCE_CR,
    ),
    # ── CR-168-BRC10 P6.1/P6.5 (2026-10-04, lane SRV-5) ──────────────────
    "service_visit_moved": TemplateListing(
        code="service_visit_moved",
        name="Visit moved",
        category=CAT_SERVICE_FIELD,
        kind="Email",
        used_by="Sent when a booked visit's date or window changes.",
        category_source=SOURCE_LANE,
    ),
    "sms_visit_booked": TemplateListing(
        code="sms_visit_booked",
        name="Visit booked · SMS",
        category=CAT_SERVICE_FIELD,
        kind="SMS",
        used_by="Sent when a job with a customer is first given its date.",
        category_source=SOURCE_LANE,
    ),
    "sms_visit_moved": TemplateListing(
        code="sms_visit_moved",
        name="Visit moved · SMS",
        category=CAT_SERVICE_FIELD,
        kind="SMS",
        used_by="Sent when a booked visit's date or window changes.",
        category_source=SOURCE_LANE,
    ),
    # ── DEF-WRK-10652 (PO 2026-10-29, ruling 1A) — the job raised undated ──
    "service_work_order_logged": TemplateListing(
        code="service_work_order_logged",
        name="Work order logged",
        category=CAT_SERVICE_FIELD,
        kind="Email",
        used_by="Sent when a job with a customer is raised without a date.",
        category_source=SOURCE_LANE,
    ),
    "sms_work_order_logged": TemplateListing(
        code="sms_work_order_logged",
        name="Work order logged · SMS",
        category=CAT_SERVICE_FIELD,
        kind="SMS",
        used_by="Sent when a job with a customer is raised without a date.",
        category_source=SOURCE_LANE,
    ),
    "sms_technician_on_the_way": TemplateListing(
        code="sms_technician_on_the_way",
        name="Technician on the way · SMS",
        category=CAT_SERVICE_FIELD,
        kind="SMS",
        used_by="Sent when the technician sets off for the visit.",
        category_source=SOURCE_LANE,
    ),
    "service_door_hanger": TemplateListing(
        code="service_door_hanger",
        name="Disconnect / reconnect door hanger",
        category=CAT_SERVICE_FIELD,
        kind="Door hanger print + email",
        used_by="Field work. The wording is ready; sending is not switched on yet.",
        category_source=SOURCE_CR,
    ),
    "service_outage_notice": TemplateListing(
        code="service_outage_notice",
        name="Planned outage notice",
        category=CAT_SERVICE_FIELD,
        kind="Email + SMS",
        used_by="Outage and broadcast messages. The wording is ready; sending is not switched on yet.",
        category_source=SOURCE_CR,
    ),
    # ── Account lifecycle ────────────────────────────────────────────────
    "email_welcome": TemplateListing(
        code="email_welcome",
        name="Welcome / account opened",
        category=CAT_ACCOUNT_LIFECYCLE,
        kind="Email",
        used_by="Sent when a customer moves in.",
        category_source=SOURCE_CR,
    ),
    "account_message": TemplateListing(
        code="account_message",
        name="A message from the billing team",
        category=CAT_ACCOUNT_LIFECYCLE,
        kind="Email",
        used_by="What a clerk writes to a customer from the account screen.",
        category_source=SOURCE_LANE,
    ),
    "service_request_acknowledgement": TemplateListing(
        code="service_request_acknowledgement",
        name="Service request received",
        category=CAT_ACCOUNT_LIFECYCLE,
        kind="Email",
        used_by="Sent when a request is submitted and no fee was taken.",
        category_source=SOURCE_LANE,
    ),
    "service_request_acknowledgement_fee": TemplateListing(
        code="service_request_acknowledgement_fee",
        name="Service request received · fee taken",
        category=CAT_ACCOUNT_LIFECYCLE,
        kind="Email",
        used_by="Sent when a request is submitted and a fee was taken at the counter.",
        category_source=SOURCE_LANE,
    ),
    "service_request_approved": TemplateListing(
        code="service_request_approved",
        name="Service request approved",
        category=CAT_ACCOUNT_LIFECYCLE,
        kind="Email",
        used_by="Sent when a request is approved and the applicant asked to be told.",
        category_source=SOURCE_LANE,
    ),
    "service_request_refused": TemplateListing(
        code="service_request_refused",
        name="Service request refused",
        category=CAT_ACCOUNT_LIFECYCLE,
        kind="Email",
        used_by="Sent when a clerk refuses a request.",
        category_source=SOURCE_LANE,
    ),
    "service_request_more_info": TemplateListing(
        code="service_request_more_info",
        name="Service request · more needed",
        category=CAT_ACCOUNT_LIFECYCLE,
        kind="Email",
        used_by="Sent when a clerk asks an applicant for more.",
        category_source=SOURCE_LANE,
    ),
    # ── the PROPERTY SALE · the three drawn on commit (`DEF-CUS-5949`) ───
    #: ⚠ **`used_by` SAYS *QUEUED*, NOT *SENT*, AND THAT IS NOT PEDANTRY ON
    #: THIS CARD.** Measured on the beta on 2026-09-20: 373 messages are queued
    #: in this product and NOT ONE has ever been sent — `sent_at` is null on
    #: every row and `BR-NOT-013` says why. Every other card in this catalogue
    #: reads *"Sent when …"*, which was written before anybody counted; these
    #: three are not going to be the ones that repeat it.
    "transfer_to_buyer": TemplateListing(
        code="transfer_to_buyer",
        name="Property sold · the buyer",
        category=CAT_ACCOUNT_LIFECYCLE,
        kind="Email",
        used_by="Queued when a property sale commits. Nothing sends yet.",
        category_source=SOURCE_LANE,
    ),
    "transfer_to_seller": TemplateListing(
        code="transfer_to_seller",
        name="Property sold · the seller",
        category=CAT_ACCOUNT_LIFECYCLE,
        kind="Email",
        used_by="Queued when a property sale commits. Nothing sends yet.",
        category_source=SOURCE_LANE,
    ),
    #: ⚠ **`CAT_ACCOUNT_LIFECYCLE` AND NOT `CAT_SERVICE_FIELD`, THOUGH IT IS
    #: ABOUT A VISIT, AND THE REASON IS THAT THE OTHER CATEGORY IS A RULED
    #: MEMBERSHIP RATHER THAN A THEME.** The PO named `Service & field`'s
    #: contents on 2026-08-16 — *"appointment, work completed, door hanger,
    #: outage"* — and `test_cr_007__the_service_and_field_category_ships_with_
    #: its_four_templates` asserts that set EXACTLY. Adding a fifth here would
    #: be widening a signed list by editing a dictionary, which is the `move`
    #: precedent this module already records twice. It is filed beside the two
    #: letters it is queued WITH, on one commit, which is also where a clerk
    #: looking for *what the sale sent* would go and find all three.
    "transfer_field_visit_sms": TemplateListing(
        code="transfer_field_visit_sms",
        name="Property sold · meter visit",
        category=CAT_ACCOUNT_LIFECYCLE,
        kind="SMS",
        used_by="Queued to the buyer when a sale commits. Nothing sends yet.",
        category_source=SOURCE_LANE,
    ),
    # ── new connect · step 7's three messages (PO 2026-09-16) ────────────
    #: ⚠ **TWO CLASSES HERE AND NOT THREE, AND THE MISSING ONE IS THE POINT.**
    #: The PO ruled step 7 sends three messages — the build is created, the
    #: contract, and what it costs — and then closed `OQ-MET-12360` with
    #: *"using existing template and notification"*. The contract turned out to
    #: need nothing built: **`contract_service_agreement` already exists** in
    #: `CONTRACT_CATALOGS`, in the `contracts` group, with platform wording the
    #: System Admin publishes under their own date (`BR-NOT-002`). Authoring a
    #: fourth `new_connect_contract` beside it would have been a second contract
    #: class for one bargain, which is how two documents come to state different
    #: terms for the same service.
    #: ⚠ **`CAT_ACCOUNT_LIFECYCLE` AND NOT `CAT_SERVICE_FIELD`, WHICH A GUARD
    #: DECIDED RATHER THAN A PREFERENCE.** These two were written into
    #: *Service & field* first, and `test_cr_007__the_service_and_field_category
    #: _ships_with_its_four_templates` went red naming both of them. That
    #: category is CR-007's four — appointment, work completed, door hanger,
    #: outage — fixed by a PO ruling of 2026-08-16, and it is about work a crew
    #: does. **These are correspondence with the person who OWNS the service**,
    #: which is what the five `service_request_*` classes above are and where
    #: they file.
    "new_connect_confirmed": TemplateListing(
        code="new_connect_confirmed",
        name="New connect — confirmed",
        category=CAT_ACCOUNT_LIFECYCLE,
        kind="Email",
        used_by="Sent to the owner when a build is created.",
        category_source=SOURCE_LANE,
    ),
    "new_connect_quote": TemplateListing(
        code="new_connect_quote",
        name="Connection quote",
        category=CAT_ACCOUNT_LIFECYCLE,
        kind="Email",
        used_by="Sent to the owner with what the build costs.",
        category_source=SOURCE_LANE,
    ),
    "email_move_out_final": TemplateListing(
        code="email_move_out_final",
        name="Move-out final bill",
        category=CAT_ACCOUNT_LIFECYCLE,
        kind="PDF + email",
        used_by="Sent when a customer moves out.",
        category_source=SOURCE_CR,
    ),
    "email_deposit": TemplateListing(
        code="email_deposit",
        name="Deposit received & applied",
        category=CAT_ACCOUNT_LIFECYCLE,
        kind="Email",
        used_by="Sent when a deposit is recorded.",
        category_source=SOURCE_CR,
    ),
    "email_account_closed": TemplateListing(
        code="email_account_closed",
        name="Account closed confirmation",
        category=CAT_ACCOUNT_LIFECYCLE,
        kind="Email",
        used_by="Sent when an account is closed.",
        category_source=SOURCE_CR,
    ),
    # ── DEF-NOT-10649 (PO 2026-10-29, *"1 A, 2 A, 3 A, 4 A"*) ────────────
    # The two moments after the disconnect ladder: the cut, and the
    # restoration. Collections, beside the disconnect notice they follow.
    "service_disconnected_guide": TemplateListing(
        code="service_disconnected_guide",
        name="Service disconnected",
        category=CAT_COLLECTIONS,
        kind="Email",
        used_by="Sent when a disconnection is marked as cut.",
        category_source=SOURCE_LANE,
    ),
    "sms_service_disconnected": TemplateListing(
        code="sms_service_disconnected",
        name="Service disconnected · SMS",
        category=CAT_COLLECTIONS,
        kind="SMS",
        used_by="Sent when a disconnection is marked as cut.",
        category_source=SOURCE_LANE,
    ),
    "service_restored": TemplateListing(
        code="service_restored",
        name="Service restored",
        category=CAT_COLLECTIONS,
        kind="Email",
        used_by="Sent when service is restored after a disconnection.",
        category_source=SOURCE_LANE,
    ),
    "sms_service_restored": TemplateListing(
        code="sms_service_restored",
        name="Service restored · SMS",
        category=CAT_COLLECTIONS,
        kind="SMS",
        used_by="Sent when service is restored after a disconnection.",
        category_source=SOURCE_LANE,
    ),
    "email_bill_ready": TemplateListing(
        code="email_bill_ready",
        name="Bill ready · e-bill email",
        category=CAT_BILLING,
        kind="Email",
        used_by="Sent when a bill is ready.",
    ),
    "email_statement": TemplateListing(
        code="email_statement",
        name="Statement · Email",
        category=CAT_BILLING,
        kind="Email",
        used_by="Statements. The wording is ready; nothing produces a statement yet.",
    ),
    "sms_bill_ready": TemplateListing(
        code="sms_bill_ready",
        name="Bill ready · SMS",
        category=CAT_BILLING,
        kind="SMS",
        used_by="Sent when a bill is ready.",
    ),
    "email_plan_change": TemplateListing(
        code="email_plan_change",
        name="Plan or rate change",
        category=CAT_ACCOUNT_LIFECYCLE,
        kind="Email",
        used_by="Sent when an account changes rate plan.",
    ),
    "contract_service_agreement": TemplateListing(
        code="contract_service_agreement",
        name="Service agreement",
        category=CAT_ACCOUNT_LIFECYCLE,
        kind="PDF + click-to-accept",
        used_by="Not in use yet — the wording is written and waiting for you to publish it.",
    ),
    "contract_deposit": TemplateListing(
        code="contract_deposit",
        name="Deposit agreement",
        category=CAT_ACCOUNT_LIFECYCLE,
        kind="PDF + click-to-accept",
        used_by="Not in use yet — the wording is written and waiting for you to publish it.",
    ),
    "contract_autopay_authorization": TemplateListing(
        code="contract_autopay_authorization",
        name="Autopay authorization (NACHA)",
        category=CAT_PAYMENTS,
        kind="PDF + click-to-accept",
        used_by="Not in use yet — this one is a placeholder for your bank's own wording.",
    ),
    # ── in-app (CR-009) ──────────────────────────────────────────────────
    "staff_bulk_summary": TemplateListing(
        code="staff_bulk_summary",
        name="Bulk action summary (in-app)",
        category=CAT_BILLING,
        kind="In-app message",
        # A STATEMENT OF FACT, like every other row here: this one HAS a
        # consumer, which most of the catalog does not.
        used_by=(
            "Sent in the app to the staff member who ran a bulk action. If the run "
            "had any failures, every System Admin is told as well."
        ),
        category_source=SOURCE_LANE,
    ),
    # ── in-app · CR-168-BRC10 §F (FIELD-2) ───────────────────────────────
    "staff_field_work": TemplateListing(
        code="staff_field_work",
        name="Field job update (in-app)",
        category=CAT_BILLING,
        kind="In-app message",
        used_by=(
            "Sent in the app to whoever sent a job to the field when it is closed, when "
            "its photos have all arrived, and when the field sent something that needs "
            "review. Needs review also reaches every System Admin."
        ),
        category_source=SOURCE_LANE,
    ),
    # ── the scheduled report · CR-142-BRC07 P4.10 ────────────────────────
    "email_scheduled_report": TemplateListing(
        code="email_scheduled_report",
        name="Scheduled report ready",
        category=CAT_BILLING,
        kind="Email",
        used_by=(
            "Sent to the staff a schedule names when its report has run. It carries a "
            "link to the run, never the file."
        ),
        category_source=SOURCE_LANE,
    ),
    # CR-182-BRC10 (PO A4, 2026-10-14): *"send her Email"* — the moment a
    # reading is flagged high (A5). Billing, because it is about what the
    # customer is about to be charged for; SET-12 keeps the event where CR-009
    # drew it.
    "email_high_usage_alert": TemplateListing(
        code="email_high_usage_alert",
        name="High consumption alert",
        category=CAT_BILLING,
        kind="Email",
        used_by="Sent when a meter reading is flagged as much higher than usual.",
        category_source=SOURCE_LANE,
    ),
    # ── Account access · CR-188-BRC10 (PO 2026-10-22, answer 6) ──────────
    "staff_user_invite": TemplateListing(
        code="staff_user_invite",
        name="Staff User Invitation & Welcome",
        category=CAT_ACCOUNT_ACCESS,
        kind="Email",
        used_by=(
            "Sent when a System Admin creates a user. It carries a one-time link to set "
            "a password, never the password."
        ),
        category_source=SOURCE_LANE,
    ),
    "staff_password_reset_link": TemplateListing(
        code="staff_password_reset_link",
        name="Staff password reset",
        category=CAT_ACCOUNT_ACCESS,
        kind="Email",
        used_by=(
            "Sent when a System Admin resets a password or resends an invitation. It "
            "carries a one-time link, never the password."
        ),
        category_source=SOURCE_LANE,
    ),
    # DEF-CWP-10381 (PO 2026-10-22): the customer portal's reset link. It had a
    # queue row and no wording, so it was never sent.
    "portal_password_reset": TemplateListing(
        code="portal_password_reset",
        name="Customer Portal Password Reset Link",
        category=CAT_ACCOUNT_ACCESS,
        kind="Email",
        used_by="Sent when a customer asks for a new password on the portal.",
        category_source=SOURCE_LANE,
    ),
    # ── Account access · CR-189-BRC10 (PO 2026-10-22) ────────────────────
    "portal_enrolment_code": TemplateListing(
        code="portal_enrolment_code",
        name="Customer Portal One-Time Code",
        category=CAT_ACCOUNT_ACCESS,
        kind="Email + SMS",
        used_by=(
            "Sent to a phone or email already on file when a customer signs up, adds an "
            "account, confirms a payment change or updates their email on the portal."
        ),
        category_source=SOURCE_LANE,
    ),
    "portal_email_change_code": TemplateListing(
        code="portal_email_change_code",
        name="Customer Portal Email Change Code",
        category=CAT_ACCOUNT_ACCESS,
        kind="Email",
        used_by=(
            "Sent to the new address when a customer updates their registered email "
            "on the portal. It carries the code that confirms the address."
        ),
        category_source=SOURCE_LANE,
    ),
    "portal_email_changed_notice": TemplateListing(
        code="portal_email_changed_notice",
        name="Customer Portal Email Changed Notice",
        category=CAT_ACCOUNT_ACCESS,
        kind="Email",
        used_by=(
            "Sent to the old address after a customer's registered email is changed "
            "on the portal."
        ),
        category_source=SOURCE_LANE,
    ),
}


#: CR-007's fourteen new classes: named by the PO, specified by nobody. Each is
#: LISTED, openable and versionable; none can hold a body, because
#: `rendering.validate_body` has no whitelist to check one against. OQ-251.
_CR_007_UNSPECIFIED = (
    "bill_insert",
    "email_corrected_bill",
    "writeoff_notice",
    "email_autopay",
    "email_payment_failed",
    "email_refund_issued",
    "service_appointment",
    "service_work_completed",
    "service_door_hanger",
    "service_outage_notice",
    "email_welcome",
    "email_move_out_final",
    "email_deposit",
    "email_account_closed",
)


#: Template classes that EXIST as ratified rules and whose merge-variable
#: catalog no signed document writes. The reason travels with each one, because
#: an empty catalog and an unspecified catalog are different facts: the first
#: means "this class takes no variables", the second means "nobody has said".
#: `rendering.render` refuses these rather than rendering them tokenless.
CLASSES_WITHOUT_CATALOG: dict[str, str] = {
    "email_bill_ready": (
        "A19 r8's email table gives this class DISTINCT CONTENT in prose (usage breakdown "
        "by service, year-over-year comparison, pay button + PDF link, autopay reminder) "
        "and not one token in braces. Naming them here would be inventing the variable "
        "vocabulary of a customer-facing document. OQ-206."
    ),
    "email_payment_receipt": "A19 r8 email table, row 2 — content in prose, no tokens. OQ-206.",
    "email_past_due": (
        "A19 r8 email table, row 3. The THREE TONES are ratified (BR-PAY-035, "
        "US-NOT-010's mapping) but the body tokens are not written anywhere. OQ-206."
    ),
    "email_plan_change": "A19 r8 email table, row 4 — content in prose, no tokens. OQ-206.",
    "email_credit_issued": (
        "A19 r8 email table, row 5. The clerk's memo as the customer-visible reason is "
        "ratified content; its token spelling is not written. OQ-206."
    ),
    "email_statement": (
        "A19 r8 email table, row 6. A19 rule 1's 'not a bill' line is mandatory content "
        "for this class and is known; the rest of the tokens are not. OQ-206."
    ),
    "sms_bill_ready": "A19 r8 SMS table, row 1 — 103 chars of content, no tokens. OQ-206.",
    "sms_past_due": "A19 r8 SMS table, row 2 — 138 chars of content, no tokens. OQ-206.",
    "sms_disconnect": (
        "A19 r8 SMS table, row 3. A19 rule 3 is ratified — this SMS SUPPLEMENTS the "
        "mailed notice and never replaces it — and the body tokens are not written. "
        "OQ-206."
    ),
    "sms_payment_received": "A19 r8 SMS table, row 4 — 99 chars of content, no tokens. OQ-206.",
    "contract_service_agreement": (
        "BR-NOT-004 type ② confirms the contract type exists; A19 gives blocks for the "
        "payment-plan agreement (§3) and for no other contract. OQ-206."
    ),
    "contract_deposit": "BR-NOT-004 type ③ — type confirmed, content unwritten. OQ-206.",
    "contract_autopay_authorization": (
        "BR-NOT-004 type ④ — NACHA-required for recurring ACH, so its content is a "
        "compliance document and is the last thing that should be drafted by inference. "
        "OQ-206."
    ),
    "plan_notice_upcoming": (
        "BR-NOT-007 creates the payment-plan notice class with three variants; the A19 "
        "r8 sixteen-template set contains none of them, so bodies and subjects are "
        "unspecified anywhere. This is the notifications field map's N-6-era finding N-1, "
        "flagged as a candidate OQ when the pack was authored and never minted — "
        "OQ-207 mints it."
    ),
    "plan_notice_missed": "BR-NOT-007 variant 2 — see plan_notice_upcoming. OQ-207.",
    "plan_notice_void": "BR-NOT-007 variant 3 — see plan_notice_upcoming. OQ-207.",
}


#: CR-007's fourteen, folded into the SAME dictionary the seventeen OQ-206/207
#: classes already live in — one mechanism for "this class exists and nobody has
#: written its vocabulary", not two. The sentence is per class so a screen can
#: answer per row (DEF-163's own finding: a gap nobody can see per class is a
#: gap nobody acts on).
for _code in _CR_007_UNSPECIFIED:
    CLASSES_WITHOUT_CATALOG[_code] = (
        f"CR-007 (PO, 2026-08-16) names {LISTINGS[_code].name!r} in the SET-09 inventory "
        "and no signed document writes its merge-variable catalogue or its body. A19's r8 "
        "sixteen-template set does not contain this class, and prototype r10 draws it with "
        "SAMPLE prose for a fictional utility, which is preview data and not template "
        "wording. So the class is listed, openable and versionable, and every save refuses: "
        "there is no whitelist to validate a body against, and accepting one would mean "
        "saving a customer-facing document whose variables nobody has defined. OQ-254."
    )
del _code


# ══════════════════════════════════════════════════════════════════════════
# THE AUTHORED PALETTES — PO RULING 2026-08-17, *"please define it for this
# product"* (CR-007, tracked as DEF-210)
# ══════════════════════════════════════════════════════════════════════════
# **WHAT THE PO WAS SHOWN AND WHAT THEY RULED.** The CR-007 walkthrough put this
# to them in plain English: *"34 of 36 template types have no content, so the
# email subject line and SMS counter you asked for have never rendered for
# anyone."* The reply, verbatim: **"please define it for this product"**.
#
# That is an AUTHORING DELEGATION and it answers the half of OQ-206 / OQ-207 /
# OQ-254 that was *"who writes the token catalogue"*. It is recorded in
# 12-governance/11-change-requests.md §"CR-007 — PO RULINGS 2026-08-17" and the
# closures are written into 12-governance/01-open-questions.md. **It does NOT
# answer OQ-253** (what the regulatory rights footer SAYS), which is a
# product+legal question with its own BLOCKING row — see NOT_AUTHORED below.
#
# **THE SHAPE IS OQ-206's OWN OPTION (b), TAKEN OFF ITS MENU RATHER THAN
# INVENTED.** OQ-206 offers *"(b) a smaller v1 palette is ruled — e.g. every
# email/SMS class gets the shared account/customer/money set and nothing
# class-specific — and the distinct content lands as fixed copy rather than
# variables."* That is what these palettes are: a small shared contact +
# recipient core, plus the few figures each document cannot state without a
# value from the account. Everything else is fixed copy in the body.
#
# ⚠ **EVERY TOKEN BELOW IS `derived_spelling`.** Unlike A19's printable classes,
# no signed document writes these names in braces, so ALL of them are
# engineering vocabulary chosen here — the same honesty the bill's four
# commercial tokens already carry, applied to a whole class set. A reviewer
# reading `derived_spelling` sees the full extent of what was chosen.
#
# ⚠ **`{utility_logo}` IS ABSENT FROM EVERY PALETTE HERE, ON PURPOSE — DEF-195.**
# The render context supplies no value for it, so a body using it prints `——` on
# a customer's letter. The printable classes A19 wrote still offer it (removing
# it there is DEF-195's own fix and is not this lane's); nothing authored here
# offers it, and `test_def_210_authored_template_bodies.py` proves no authored
# body references it.
#
# ⚠ **THE CHANNEL IS THE FIRST DELIVERY FORMAT IN CR-007's OWN `kind` STRING.**
# A variant holds ONE channel and several of the CR's rows name two ("Email +
# SMS", "Door hanger print + email"). Rather than pick by taste, the rule is
# mechanical and reads off `LISTINGS[code].kind`: "Email + SMS" → email,
# "Door hanger print + email" → print, "Letter"/"PDF page" → print. Stated here
# because it is a reading of the CR, not a quotation of it.

#: The utility's own contact details, MINUS the logo. `{utility_website}` is
#: `tenants.website` — a real stored value that `rendering.render` now merges
#: (added with these palettes for exactly this reason: a "pay online at …" line
#: with nothing behind it is DEF-195 again).
_CONTACT = frozenset({"utility_name", "support_phone", "support_email", "utility_website"})

#: Who the message is to. `{first_name}` is A13's own spelling (the dunning and
#: receipt bodies use it today); the rest match the A19 bill-meta names so one
#: caller's context serves every class.
_RECIPIENT = frozenset({"first_name", "customer_name", "account_no", "service_address"})


#: Who an APPLICANT is, for the three service-request classes. It is
#: `_RECIPIENT` with the two facts an applicant does not have taken OUT and the
#: one they do have put IN: there is no `{account_no}` and no `{customer_name}`
#: for somebody who has asked for service and has no account, and a palette that
#: offered them would let a tenant author a letter that renders a named absence
#: at the person on their very first contact with the utility. `{request_no}` is
#: what they are told to quote when they call, and it is the only identifier
#: either side holds.
_APPLICANT = frozenset({"applicant_name", "request_no", "service_address"})

#: ⊕ `DEF-CUS-10445` (PO 2026-10-22, decision log *"Service request
#: acknowledgement: target date, default 15 days, service type name"*). What the
#: request is FOR and WHEN it is wanted — the two facts both acknowledgement
#: classes gain, and the two a utility had already written into its own edited
#: wording (*"We received your request for {service_type} on …"*) while the
#: palette offered neither, so they printed `——`.
#:
#: * `{service_type}` — the requested services' names as Settings → Services
#:   holds them (`Water`, `Water, Sewer`), never their codes (B14 rule 31).
#: * `{target_date}` — the date the customer asked for; with none, the request
#:   date plus the utility's `service_request_default_target_days` working days
#:   (Settings, seeded 15 — *"don't do any hardcoding"*). In the Regional date
#:   format.
#:
#: Only the two ACKNOWLEDGEMENT classes carry them: the approval, refusal and
#: more-information letters were not part of the ruling.
_ACKNOWLEDGEMENT_FACTS = frozenset({"service_type", "target_date"})
_ACKNOWLEDGEMENT_FACTS_NOTE = (
    "`DEF-CUS-10445` (PO 2026-10-22) — `{service_type}` is the requested services' "
    "names from Settings → Services; `{target_date}` is the customer's preferred date, "
    "or the request date plus the utility's `service_request_default_target_days` "
    "working days (seeded 15)."
)


def _authored(
    code: str,
    *,
    extra: frozenset[str] = frozenset(),
    group: str = GROUP_EMAIL,
    channel: str = models.CHANNEL_EMAIL,
    core: frozenset[str] = _CONTACT | _RECIPIENT,
    mandatory_content: tuple[str, ...] = (),
    mandatory_content_reason: str = "",
    notes: tuple[str, ...] = (),
    optional: frozenset[str] = frozenset(),
    credential_tokens: frozenset[str] = frozenset(),
) -> TemplateClass:
    """One authored class's palette. Every token is `derived_spelling`."""
    tokens = core | extra
    if not optional <= tokens:  # pragma: no cover - a palette typo, caught at import
        raise ValueError(f"{code}: optional tokens outside the palette")
    return TemplateClass(
        credential_tokens=credential_tokens,
        code=code,
        group=group,
        channel=channel,
        source="PO ruling 2026-08-17 (CR-007, DEF-210) — *'please define it for this "
        "product'*; palette shape from OQ-206 option (b)",
        tokens=tokens,
        derived_spelling=tokens,
        mandatory_content=mandatory_content,
        mandatory_content_reason=mandatory_content_reason,
        notes=notes,
        optional=optional,
    )


#: SMS carries no masthead and no subject, and every character is counted
#: (CR-007's 160-char counter), so these palettes are the smallest of any class.
_SMS_CORE = frozenset({"utility_name", "support_phone", "utility_website"})

#: `DEF-BIL-10531` (PO 2026-10-22, *"b direct PDF link"*) — the bill emails'
#: secret, expiring link to the bill's kept PDF, and the date it stops working.
#: Filled by `billing.bill_links.mint` through `bill_render_context`.
_BILL_LINK_TOKENS = frozenset({"bill_link", "link_expires_on"})

AUTHORED_CATALOGS: dict[str, TemplateClass] = {
    # ── SMS (4) ──────────────────────────────────────────────────────────
    "sms_bill_ready": _authored(
        "sms_bill_ready",
        core=_SMS_CORE,
        extra=frozenset({"total_due", "due_date"}),
        group=GROUP_SMS,
        channel=models.CHANNEL_SMS,
    ),
    "sms_past_due": _authored(
        "sms_past_due",
        core=_SMS_CORE,
        extra=frozenset({"balance"}),
        group=GROUP_SMS,
        channel=models.CHANNEL_SMS,
        notes=(
            "A19 rule 2 / US-NOT-007: a past-due REMINDER carries no regulatory footer, so "
            "`{state_puc_ref}` is deliberately absent exactly as it is from `dunning`.",
        ),
    ),
    "sms_payment_received": _authored(
        "sms_payment_received",
        core=_SMS_CORE,
        extra=frozenset({"amount", "confirmation", "balance"}),
        group=GROUP_SMS,
        channel=models.CHANNEL_SMS,
    ),
    "sms_disconnect": _authored(
        "sms_disconnect",
        core=_SMS_CORE,
        extra=frozenset({"balance", "cut_date"}),
        group=GROUP_SMS,
        channel=models.CHANNEL_SMS,
        notes=(
            "A19 rule 3, ratified: this SMS **supplements** the mailed notice and never "
            "replaces it, so it carries no rights footer and `{state_puc_ref}` is absent. "
            "The footer belongs to the three PRINT tiers, which stay unauthored (OQ-253). "
            "That is why this class could be authored while they could not.",
        ),
    ),
    # ── The clerk's own message (1) · CR-094-BRC01 wave K · `ACC-S16` ────
    #
    # ⚠ **THE PALETTE IS DELIBERATELY TINY AND `{message_body}` IS WHY.** Every
    # other authored class here turns a document's PROSE into tokens; this one
    # has no prose of its own. A clerk writing *"following our call today…"* is
    # the content, so the class carries the clerk's text as ONE token and adds
    # only the signature line beside it. Nothing about a bill, a balance, a due
    # date or a notice is in this whitelist — which is `receipt`'s argument
    # applied to a message nobody drafted in advance: a class that cannot
    # mention a figure cannot state one wrongly.
    "account_message": _authored(
        "account_message",
        extra=frozenset({"message_subject", "message_body", "signed_by"}),
        notes=(
            "`{message_body}` and `{message_subject}` are the CLERK's own words, carried "
            "in the queue row's `render_context` (BR-NOT-027 part 1 — *'keep all the "
            "underlying data — we already do'*). `{signed_by}` is who the message is from "
            "and is chosen on the dialog. The regulated tones are NOT reachable through "
            "this class: BR-PAY-035 maps a reminder's tone to a dunning TIER template and "
            "BR-NOT-008 renders the disconnect class whatever tone was picked, so a "
            "ladder step composed here would carry no tier and no notice history.",
        ),
    ),
    # ── Email · Service requests (4) ─────────────────────────────────────
    #
    # ⚠ **THESE FOUR ARE THE ONLY CLASSES IN THE LIBRARY ADDRESSED TO SOMEBODY
    # WHO IS NOT A CUSTOMER.** They go to an APPLICANT: a person who has asked
    # for service, holds no account, and — when the answer is no — never will.
    # That is why they carry `_APPLICANT` rather than `_RECIPIENT`.
    #
    # ⚠ **AND THE ACKNOWLEDGEMENT IS TWO CLASSES RATHER THAN ONE, WHICH IS
    # `BR-CUS-090` CLAUSE (3) MADE STRUCTURAL.** The ruling is emphatic: *"THE
    # ACKNOWLEDGEMENT MAY NOT SAY 'Nothing is charged' WHEN MONEY WAS TAKEN …
    # Where a fee WAS taken the sentence states the amount, the method and the
    # receipt number; where none was, it may stand. It is the FIRST thing an
    # applicant receives and it is customer-facing, so a false sentence there is
    # a money defect, not a copy nit."* A template body has no conditional, so
    # one class could only ever hold one of those two sentences. Two classes,
    # picked by whether a receipt exists, makes the wrong sentence unreachable
    # instead of merely discouraged — the same posture
    # `apps/customers/service_request_service.py` already takes when it serves
    # `nothing_is_charged_may_be_said` as a fact rather than a judgment.
    "service_request_acknowledgement": _authored(
        "service_request_acknowledgement",
        core=_CONTACT | _APPLICANT,
        extra=_ACKNOWLEDGEMENT_FACTS,
        notes=(
            _ACKNOWLEDGEMENT_FACTS_NOTE,
            "`BR-CUS-079` (CONFIRMED, PO 2026-08-24) — *'when you take and submit SR - we "
            "have to send email or text messge to customer'*. THE NO-FEE HALF: this class "
            "is pinned only when no receipt was recorded, which is the one case "
            "`BR-CUS-090` clause (3) lets the drawn *nothing is charged* sentence stand.",
        ),
    ),
    "service_request_acknowledgement_fee": _authored(
        "service_request_acknowledgement_fee",
        core=_CONTACT | _APPLICANT,
        extra=_ACKNOWLEDGEMENT_FACTS | frozenset({"fee_amount", "fee_method", "receipt_no"}),
        mandatory_content=("{fee_amount}", "{receipt_no}"),
        mandatory_content_reason="money was taken at the counter, so BR-CUS-090 clause (3) "
        "requires this letter to state the amount and the receipt number. A tenant editing "
        "them out would leave an applicant with no written proof of a payment they made in "
        "person.",
        notes=(
            _ACKNOWLEDGEMENT_FACTS_NOTE,
            "THE FEE HALF of `BR-CUS-079`. Pinned when and only when a receipt exists. The "
            "amount arrives already rounded to two decimals by the caller (hard rule 2 — "
            "stored to four, DISPLAYED as two) and carries its currency, because a "
            "template cannot round and must never be asked to.",
        ),
    ),
    "service_request_approved": _authored(
        "service_request_approved",
        core=_CONTACT | _APPLICANT,
        notes=(
            "The OTHER half of the blueprint's step-6 row five — *The decision, when it is "
            "made · On approve or refuse* (p080, read as an image). Until 2026-09-15 only "
            "the refusal half had wording, so an applicant could be approved and never "
            "hear a word.",
            "NO `{message_body}`, and that is the drawing's decision rather than an "
            "omission: the Approve modal carries no `What to tell them` box. A token for a "
            "control that does not exist would be a blank in every letter this class ever "
            "renders.",
            "NO REASON CODE, NO STATE AND NO REQUEST ID beyond `{request_no}` — the same "
            "rule the four classes beside it keep: an applicant reads these, and B14 rule "
            "32 keeps our vocabulary off a customer's screen.",
        ),
    ),
    "service_request_refused": _authored(
        "service_request_refused",
        core=_CONTACT | _APPLICANT,
        extra=frozenset({"message_body"}),
        mandatory_content=("{message_body}",),
        mandatory_content_reason="the blueprint's Refuse dialog carries a `What to tell "
        "them` box whose helper line reads *Goes into the refusal letter.* — so the clerk's "
        "own sentence is the reason this letter exists. A body without it tells an "
        "applicant no is the answer and nothing about why.",
        notes=(
            "`{message_body}` is the clerk's own words from the Refuse dialog, carried in "
            "the queue row's `render_context` — the `account_message` spelling reused on "
            "purpose so one caller's context serves both classes. The five refusal REASONS "
            "are a register vocabulary and are deliberately NOT in this palette: they are "
            "what the utility files the refusal under, not what the applicant is told.",
        ),
    ),
    "new_connect_confirmed": _authored(
        "new_connect_confirmed",
        core=_CONTACT | _RECIPIENT,
        extra=frozenset({"connection_no", "target_activation"}),
        notes=(
            "Step 7 row one — *Build confirmed · On commit* (`05-prototype/02 Accounts "
            "Menu Blueprint.pdf` p091, read as an image). The PO's own words for what it "
            "is for: *'we have to do the communication with owner that request is "
            "created'* (2026-09-16).",
            "NO COUNTS AND NO MANIFEST. The build's seven counts are step 8's screen and "
            "an owner does not read *20 meters · 7 plan assignments*; `{connection_no}` is "
            "the one handle they can quote back on the phone, and it is a utility's own "
            "reference rather than a database id (B14 rule 31).",
            "NO MONEY. What the build costs is the SEPARATE letter beside this one, and "
            "the PO drew them as two rows rather than one for that reason. A confirmation "
            "that also asked for money would have to hold the figure this product cannot "
            "yet source from a posting — see `new_connect_quote`.",
        ),
    ),
    "new_connect_quote": _authored(
        "new_connect_quote",
        core=_CONTACT | _RECIPIENT,
        extra=frozenset({"connection_no", "amount_due", "currency"}),
        mandatory_content=("{amount_due}",),
        mandatory_content_reason="the PO's third message is *'we have to send cost and ask "
        "them to pay it'* (2026-09-16). A letter asking an owner to pay, that does not say "
        "what, is the one version of this document that must not be publishable — so the "
        "figure is mandatory content rather than an optional token.",
        notes=(
            "Step 7 row two — *Quote and what is owed · On commit* (p091, read as an "
            "image), and the drawing puts it on TWO channels: *'Print is the floor here "
            "too. The quote goes by email AND on paper: an owner who never opens the "
            "address on file still gets the figure they owe.'*",
            "⚠ **THE FIGURE IS MANDATORY AND THE PRODUCT CANNOT YET SOURCE IT, AND THOSE "
            "TWO FACTS TOGETHER ARE THE DESIGN RATHER THAN A CONTRADICTION.** "
            "`connections.quote_total` is a RECORDED number, not a posted one — "
            "`commit_connection` says so itself on every build, as the "
            "`quote_recorded_not_posted` absence tracking `OQ-379`. So the caller refuses "
            "to queue this class while nothing has posted, and the letter states a figure "
            "the books hold or it does not go at all. The day the quote reaches the "
            "ledger this class needs no edit.",
            "NO `{due_date}` AND NO `{pay_by}`. Nothing in this product rules when a "
            "connection quote falls due, and a date invented in a template becomes the "
            "date a utility is held to.",
        ),
    ),
    "service_request_more_info": _authored(
        "service_request_more_info",
        core=_CONTACT | _APPLICANT,
        extra=frozenset({"message_body"}),
        mandatory_content=("{message_body}",),
        mandatory_content_reason="the blueprint's Ask-for-more dialog carries a `Message to "
        "the applicant` box whose helper line reads *Sent to them and kept on the request's "
        "history.* — the clerk's sentence IS the ask. Without it the letter says only that "
        "something is needed.",
        notes=(
            "The tick list drawn above that box (`WHAT IS NEEDED`) is NOT in this palette "
            "and is not in the letter, because the drawing attaches *Sent to them* to the "
            "message box alone. The list is the clerk's own checklist: it is stored on the "
            "request and kept on its history, and composing it into English here would put "
            "untranslated prose inside a customer-facing document that the language axis "
            "(BR-NOT-006) exists to prevent.",
        ),
    ),
    # ── The PROPERTY SALE (3) · `DEF-CUS-5949`, 2026-09-20 ───────────────
    #
    # ⚠ **TWO LETTERS AND NOT ONE, FOR THE REASON THE SERVICE REQUEST'S TWO
    # ACKNOWLEDGEMENTS CARRY: A TEMPLATE BODY HAS NO CONDITIONAL IN IT.** *"The
    # account is yours from today"* and *"the account is no longer yours"* are
    # two letters to two people, and one class could only ever carry one of the
    # two sentences.
    "transfer_to_buyer": _authored(
        "transfer_to_buyer",
        extra=frozenset({"sold_on"}),
        notes=(
            "The buyer's change-of-ownership letter, queued when a sale commits "
            "(`BR-CUS-1030`). `{account_no}` is the number the account has always had and "
            "keeps — a sale reassigns the account rather than opening one, which is the "
            "single fact this letter exists to state.",
            "⛔ **NO BALANCE, NO DEPOSIT AND NO TOTAL IN THIS PALETTE, AND THE ABSENCE IS "
            "A DECISION RATHER THAN AN OVERSIGHT.** The account's ledger is unbroken "
            "across a sale, so a figure frozen into a row queued today and delivered "
            "whenever an adapter is plugged in (`BR-NOT-013`) would be wrong by exactly "
            "the amount the account has moved since. It is the same prohibition the "
            "transfer record page carries for its `Balance as it stood` row.",
            "NO SELLER NAME. The buyer is told the account is theirs, not who it came "
            "from: who sold a property is the seller's business and naming them in a "
            "letter would publish it. The transfer RECORD says so to staff, which is "
            "where that fact belongs.",
        ),
    ),
    "transfer_to_seller": _authored(
        "transfer_to_seller",
        extra=frozenset({"sold_on"}),
        notes=(
            "The seller's half of the same commit. ⚠ **ITS QUEUE ROW CARRIES `account_id` "
            "NULL**, because after the sale the account is the BUYER's and the column "
            "would file this letter under them — `apps/notifications/transfer_events.py` "
            "holds the whole argument. `{account_no}` is still in the palette: the seller "
            "needs the number to recognise which property is meant.",
            "⛔ **NO CLOSING BALANCE AND NO REFUND FIGURE.** `BR-CUS-085` is emphatic "
            "that nothing is refunded and re-collected on a sale — the deposit and the "
            "balance travel with the property — so a token for a refund would let a "
            "tenant author a letter promising money that the rule says never moves.",
        ),
    ),
    "transfer_field_visit_sms": _authored(
        "transfer_field_visit_sms",
        core=_SMS_CORE,
        extra=frozenset({"service_address", "sold_on"}),
        group=GROUP_SMS,
        channel=models.CHANNEL_SMS,
        notes=(
            "The third drawn message, and the only one on a phone: somebody is coming to "
            "read the meter on the day the property changes hands (`BR-WRK-055`). It goes "
            "to the BUYER — they are the one who has to let a technician in.",
            "⛔ **NO APPOINTMENT WINDOW AND NO TECHNICIAN NAME IN THIS PALETTE.** The "
            "work order is raised AFTER the commit and is allowed to fail without taking "
            "the sale down, so at the moment this row is written nothing in this product "
            "knows when anybody is coming. A window token would let a tenant author a "
            "promise the product cannot keep, in 160 characters, at a customer.",
        ),
    ),
    # ── Email · Billing (4) ──────────────────────────────────────────────
    "email_bill_ready": _authored(
        "email_bill_ready",
        extra=frozenset(
            {
                "bill_no",
                "bill_date",
                "due_date",
                "total_due",
                "current_charges",
                "prev_balance",
                "payments",
                "period_start",
                "period_end",
                *_BILL_LINK_TOKENS,
            }
        ),
        # DEF-BIL-10531 — the link is optional (no public address → the
        # paragraph is left out) and a credential (the kept copy omits it).
        optional=_BILL_LINK_TOKENS,
        credential_tokens=frozenset({"bill_link"}),
        notes=(
            "The SUBJECT SHAPE is A19 r8's own example for this class — *'Your Silver Creek "
            "Water bill is ready — $247.30 due Aug 25'* — with the utility, the figure and "
            "the date turned into tokens. A19 gives the example and no tokens; this is the "
            "example's structure, which is the closest thing to a signed subject there is.",
        ),
    ),
    "email_statement": _authored(
        "email_statement",
        extra=frozenset({"period_start", "period_end", "opening_balance", "closing_balance"}),
        mandatory_content=("nothing is due",),
        notes=(
            "A19 rule 1 is MANDATORY on this class and was known before the body existed — "
            "*'both the printed statement and the statement email must say nothing is due, "
            "or customers pay twice.'* `mandatory_content` makes it non-removable here as "
            "it already is on the printed `statement`.",
        ),
    ),
    "email_corrected_bill": _authored(
        "email_corrected_bill",
        extra=frozenset({"bill_no", "original_total", "total_due", "due_date", "correction_reason"})
        | _BILL_LINK_TOKENS,
        # DEF-BIL-10531 — the same link, to the corrected bill.
        optional=_BILL_LINK_TOKENS,
        credential_tokens=frozenset({"bill_link"}),
    ),
    "email_plan_change": _authored(
        "email_plan_change",
        extra=frozenset({"effective_date", "plan_name", "old_rate", "new_rate"}),
        notes=(
            "The body states WHEN the change takes effect and never how a bill spanning the "
            "date is split — proration across a rate change is BR-RAT's and no rule states "
            "it in customer words, so the sentence is left out rather than guessed.",
        ),
    ),
    # ── Email · Collections (1) ──────────────────────────────────────────
    "email_past_due": _authored(
        "email_past_due",
        extra=frozenset({"balance", "due_date", "days_late"}),
        notes=(
            "A19 r8 ratifies THREE TONES for this class (BR-PAY-035, US-NOT-010's mapping). "
            "The seeded body is the `default` variant only — the firmer tones are variants a "
            "tenant adds, and seeding three bodies into one variant slot is the mistake "
            "OQ-243 was minted for. No regulatory footer (A19 rule 2): this is a reminder.",
        ),
    ),
    # ── Email · Payments (5) ─────────────────────────────────────────────
    "email_payment_receipt": _authored(
        "email_payment_receipt",
        extra=frozenset(
            {
                "amount",
                "date",
                "method",
                "confirmation",
                "applied_to_bill",
                "balance_before",
                "balance_after",
            }
        ),
        notes=(
            "The same seven facts A19 r8 ratifies for the PRINTED receipt — *'amount, "
            "method, confirmation number, applied-to bill, balance before/after'* — so the "
            "emailed and printed receipts of one payment say the same thing. `processed_by` "
            "is deliberately absent: a staff member's name belongs on the counter receipt "
            "they hand over, not in an email about an online payment.",
        ),
    ),
    "email_payment_failed": _authored(
        "email_payment_failed",
        extra=frozenset(
            {
                "amount",
                "date",
                "method",
                "failure_reason",
                "balance",
                "due_date",
                # DEF-PAY-10744 (2026-10-30, audit L2-04) — a RETURNED payment's
                # own facts: the cheque/reference, the bank's words, the fee.
                "confirmation",
                "bank_memo",
                "nsf_fee",
            }
        ),
        optional=frozenset({"confirmation", "bank_memo", "nsf_fee", "due_date"}),
        notes=(
            "⚠ REWRITTEN 2026-10-30 (DEF-PAY-10744). Only a payment the BANK returned sends "
            "this (`receipts.queue_failed_payment_notice`, on an `nsf` reversal), so the old "
            "*'Nothing has changed on your account'* was false: the money comes off the "
            "account, its bills are owed again and an NSF fee may be added. `{nsf_fee}` is "
            "the fee bill the reversal raised from the plan's NSF charge code (PO "
            "2026-10-30, *'Do not hardcode … Account> Unit> Plan> Charge code'*) and closes "
            "OQ-260 (b); `{bank_memo}` is LBX-04's Bank memo. The four optional tokens each "
            "sit in their own paragraph, so a bounce with no fee prints no fee line — never "
            "$0.00. `{failure_reason}` stays in the palette for utilities whose edited copy "
            "still uses it; it carries the Bank memo.",
        ),
    ),
    # DEF-PAY-10744 (2026-10-30) — the PRINTED returned-payment letter, blank
    # since DEF-2473 and now catalogued with the email's palette plus the printed
    # masthead, so the two copies of one bounce say the same thing.
    "payment_failed_letter": _authored(
        "payment_failed_letter",
        group=GROUP_PRINTABLE,
        channel=models.CHANNEL_PRINT,
        # `writeoff_notice`'s core, not the printable masthead: an authored
        # palette never offers `{utility_logo}` (test_def_210 — the renderer
        # cannot fill it from a body).
        core=_CONTACT | _RECIPIENT | frozenset({"utility_address"}),
        extra=frozenset(
            {
                "amount",
                "date",
                "method",
                "failure_reason",
                "balance",
                "due_date",
                "confirmation",
                "bank_memo",
                "nsf_fee",
            }
        ),
        optional=frozenset({"confirmation", "bank_memo", "nsf_fee", "due_date"}),
        notes=(
            "The printed half of `email_payment_failed` (BR-NOT-024's print floor queues it "
            "on every bounce). Same facts, same optional paragraphs; a letter has no "
            "subject line and greets the account holder by full name.",
        ),
    ),
    "email_autopay": _authored(
        "email_autopay",
        extra=frozenset({"method", "next_charge_date", "next_amount"}),
        notes=(
            "r10's *'we will email you 3 days before every charge'* is NOT stated: the "
            "−3-day cadence BR-PAY-016 ratifies is the PAYMENT-PLAN reminder, not autopay's, "
            "and promising a lead time nobody configured is a promise the product would "
            "break.",
        ),
    ),
    "email_refund_issued": _authored(
        "email_refund_issued",
        extra=frozenset({"amount", "date", "method", "reason"}),
        notes=(
            "No *'allow 3–5 business days'* — settlement time is the card issuer's and no "
            "rule states it.",
        ),
    ),
    "email_credit_issued": _authored(
        "email_credit_issued",
        extra=frozenset({"amount", "date", "reason", "balance"}),
        notes=(
            "A19 r8 ratifies the clerk's memo as the CUSTOMER-VISIBLE reason for this class; "
            "`{reason}` is that memo and the body prints it under a plain label.",
        ),
    ),
    "email_high_usage_alert": _authored(
        "email_high_usage_alert",
        extra=frozenset({"service_name", "read_date", "usage"}),
        notes=(
            "CR-182-BRC10 — PO 2026-10-14, *'A4 … send her Email; A5 … Tell them as soon as "
            "the reading is flagged'*. Queued by `metering.high_consumption` the moment "
            "BR-MET-020/120 flags a reading high, before any clerk decides.",
            "`{usage}` carries its unit (hard rule 3) and `{read_date}` is a date the "
            "renderer formats. NO ratio, NO 'normal' figure and NO threshold: the customer "
            "is told the fact, and how the utility judges high is rationale (B14 rule 33).",
        ),
    ),
    # ── Email · Account access ───────────────────────────────────────────
    "portal_password_reset": _authored(
        "portal_password_reset",
        core=_CONTACT,
        extra=frozenset({"customer_name", "reset_link"}),
        mandatory_content=("{reset_link}",),
        mandatory_content_reason=(
            "This email exists to carry the reset link. Without it the customer "
            "cannot choose a new password."
        ),
        credential_tokens=frozenset({"reset_link"}),
        notes=(
            "DEF-CWP-10381 — PO 2026-10-22. Queued by `portal.credentials.send_reset` "
            "for an address WITH a portal login; an address without one gets the same "
            "screen and no email (BR-CWP-038).",
            "`{reset_link}` is absolute, built from PUBLIC_APP_ORIGIN, single use; its "
            "lifetime is the utility's `password_link_valid_days`. No lifetime is printed "
            "in the body: a figure in wording goes stale the day the setting moves.",
        ),
    ),
    # ── Email · Account lifecycle (4) ────────────────────────────────────
    "email_welcome": _authored(
        "email_welcome",
        extra=frozenset({"service_start_date", "first_bill_date"}),
        # CR-190-BRC10 — PO 2026-10-22: *"give the activation date , first bill
        # date and no due date required"*. The first bill date is the account's
        # cycle default (`customer_context.first_bill_date`); an account on no
        # scheduled cycle has none, and its paragraph is dropped, never dashed.
        optional=frozenset({"first_bill_date"}),
        notes=(
            "`{first_bill_date}` is the cycle's default bill date for the period the "
            "customer moved in during (OQ-344). Where there is no single scheduled "
            "cycle it has no value and the paragraph carrying it is left out.",
        ),
    ),
    "email_move_out_final": _authored(
        "email_move_out_final",
        extra=frozenset({"service_end_date", "final_read", "unit", "total_due", "due_date"}),
        # DEF-NOT-10536 (PO 2026-10-22) — the move-out email carries the DRAFT
        # final bill's figures. A move-out with nothing left to bill has no
        # total and no due date, and a unit with no closing reading has no
        # reads: each paragraph is left out rather than dashed.
        optional=frozenset({"final_read", "total_due", "due_date"}),
        notes=(
            "CLAUDE.md rule 3 — every closing reading in `{final_read}` carries its own unit, "
            "one line per meter (`W-5043: 2645 kgal`). `{unit}` is filled only when every "
            "reading shares one unit, for wording that still prints the two side by side. "
            "`{total_due}` and `{due_date}` are the drafted final bill's; a move-out with "
            "nothing left to bill leaves their paragraph out. No *'refund within 14 days'*: "
            "no rule states a refund window.",
        ),
    ),
    "email_deposit": _authored(
        "email_deposit",
        extra=frozenset({"amount", "date", "balance"}),
        notes=(
            "⚠ NO REFUND RULE IN THE BODY. r10 draws *'refunded automatically after 12 "
            "months of on-time payments'*; the deposit-refund policy is a tenant's and no "
            "signed rule states a period, so the body says only that we will write when the "
            "deposit is applied or returned — OQ-260.",
        ),
    ),
    "email_account_closed": _authored(
        "email_account_closed",
        extra=frozenset({"service_end_date", "closing_balance"}),
    ),
    # ── Email + SMS · after the disconnect ladder — DEF-NOT-10649 ────────
    # PO 2026-10-29, *"1 A, 2 A, 3 A, 4 A"*. The figures are the cut's own
    # (`customers.disconnects.reconnection_terms`) as `rendering.Money` — 4dp
    # stored, 2dp shown in the utility's currency (hard rule 2). The words are
    # `service_state_wording`'s, one variant per language.
    "service_disconnected_guide": _authored(
        "service_disconnected_guide",
        extra=frozenset(
            {
                "cut_date",
                "final_read",
                "balance_owed",
                "reconnect_fee",
                "total_to_restore",
                "restoration_link",
            }
        ),
        # A unit with no meter has no closing reading; a deployment with no
        # public address has no link (law 3). Each paragraph is left out.
        optional=frozenset({"final_read", "restoration_link"}),
        notes=(
            "CLAUDE.md rule 3 — every closing reading in `{final_read}` carries its own unit, "
            "one line per meter (`W-5043: 2645 kgal`). `{total_to_restore}` is the account's "
            "position after the cut, the issued reconnection fee inside it; `{balance_owed}` is "
            "that position less the fee. `{restoration_link}` is the customer portal's pay page.",
            "The safety text is the PO's four sentences (2026-10-29, ruling 4A) and no more: "
            "no fee, deadline or regulator is named in prose.",
        ),
    ),
    "service_restored": _authored(
        "service_restored",
        extra=frozenset({"restored_at"}),
    ),
    "sms_service_disconnected": _authored(
        "sms_service_disconnected",
        core=_SMS_CORE,
        extra=frozenset({"cut_date", "total_to_restore"}),
        group=GROUP_SMS,
        channel=models.CHANNEL_SMS,
    ),
    "sms_service_restored": _authored(
        "sms_service_restored",
        core=_SMS_CORE,
        extra=frozenset({"restored_at"}),
        group=GROUP_SMS,
        channel=models.CHANNEL_SMS,
    ),
    # ── Email · Payment-plan notices (ALL 3 of BR-NOT-007's, as of C-14) ──
    "plan_notice_upcoming": _authored(
        "plan_notice_upcoming",
        extra=frozenset(
            {
                "installment_amount",
                "installment_due_date",
                "installment_no",
                "installments_total",
                "plan_balance",
            }
        ),
        notes=(
            "BR-PAY-016 CONFIRMED: *'reminder 3 days before installment'*. The body states "
            "no lead time — the cadence is tenant config and the notice is sent when it "
            "fires, so printing '3 days' would harden a setting into prose.",
        ),
    ),
    "plan_notice_missed": _authored(
        "plan_notice_missed",
        extra=frozenset(
            {
                "installment_amount",
                "installment_due_date",
                "installment_no",
                "installments_total",
                "plan_balance",
            }
        ),
        notes=(
            "⚠ THE PLAN IS STILL IN PLACE, AND THE BODY SAYS SO because a ruling says so. "
            "BR-PAY-016 and BR-CUS-044 are SUPERSEDED on this point by the PO, 2026-08-11, "
            "verbatim: *'nodrop we chase for payments until write off'*. r10's payment-plan "
            "prose — *'Miss an installment and the plan cancels; the full balance becomes "
            "due'* — describes the product that ruling abolished and is NOT used.",
        ),
    ),
    "plan_notice_void": _authored(
        "plan_notice_void",
        # The SAME palette as its two siblings, deliberately — the C-14
        # instruction is to reuse their vocabulary, and one caller's context
        # serves all three plan notices.
        extra=frozenset(
            {
                "installment_amount",
                "installment_due_date",
                "installment_no",
                "installments_total",
                "plan_balance",
            }
        ),
        notes=(
            "⚠ AUTHORED UNDER ITS OWN RULING, 2026-08-17 (CR-009 C-14), NOT under "
            "DEF-210's blanket delegation — PO verbatim: *'you give default language for "
            "the plan-void notice only - we wil allow utility to make the changes'*. "
            "AND THE EVENT IT ANNOUNCES STILL HAS NO WRITER: the 2026-08-11 'nodrop' "
            "ruling stands (BR-PAY-016 — no second-miss void fires anywhere), so this is "
            "wording ahead of a flow, the posture the PO ratified for the service "
            "templates (2026-08-16: *'wording can exist before the flow that sends "
            "it'*). Nothing schedules it; a plan voided by a future ruling or a staff "
            "action is what would.",
        ),
    ),
    # ── Service & field (4) ──────────────────────────────────────────────
    # PO 2026-08-16, verbatim: *"wording can exist before the flow that sends
    # it. Those templates are catalogued and editable now."* Nothing here
    # creates a work-order table and OQ-249 is untouched.
    # `DEF-WRK-10652` (PO 2026-10-29, ruling 3B) — `{prep_instructions}` is
    # the job's template's preparation text, else the utility's default. It is
    # OPTIONAL: a utility that set no default and a template with none leave
    # the paragraph out rather than printing a blank.
    "service_appointment": _authored(
        "service_appointment",
        extra=frozenset({"work_type", "appointment_date", "appointment_window", "prep_instructions"}),
        optional=frozenset({"prep_instructions"}),
    ),
    "service_work_completed": _authored(
        "service_work_completed",
        extra=frozenset({"work_type", "completed_date", "technician_name"}),
    ),
    # ── the visit, told — CR-168-BRC10 P6.1/P6.5 (2026-10-04, lane SRV-5) ──
    # Ruling 3: booked · moved · on the way · done. The two email classes
    # above serve booked and done; these four fill the channels the four
    # events offer and had no wording for. `{service_address}` is the
    # PREMISES' address, walked (hard rule 8), supplied by Work's caller.
    "service_visit_moved": _authored(
        "service_visit_moved",
        extra=frozenset({"work_type", "appointment_date", "appointment_window", "prep_instructions"}),
        optional=frozenset({"prep_instructions"}),
    ),
    "sms_visit_booked": _authored(
        "sms_visit_booked",
        core=_SMS_CORE,
        extra=frozenset({"appointment_date", "appointment_window", "prep_instructions"}),
        group=GROUP_SMS,
        channel=models.CHANNEL_SMS,
        optional=frozenset({"prep_instructions"}),
    ),
    # ── DEF-WRK-10652 (PO 2026-10-29, ruling 1A) — *Work order logged*: a job
    # with a customer raised WITHOUT a date. Order number, what, where (the
    # PREMISES' address, walked — hard rule 8), *we'll confirm a date*, the
    # support phone, and the preparation text (ruling 3B).
    "service_work_order_logged": _authored(
        "service_work_order_logged",
        extra=frozenset({"order_no", "work_type", "prep_instructions"}),
        optional=frozenset({"prep_instructions"}),
    ),
    "sms_work_order_logged": _authored(
        "sms_work_order_logged",
        core=_SMS_CORE,
        extra=frozenset({"order_no", "work_type", "service_address", "prep_instructions"}),
        group=GROUP_SMS,
        channel=models.CHANNEL_SMS,
        optional=frozenset({"prep_instructions"}),
    ),
    "sms_visit_moved": _authored(
        "sms_visit_moved",
        core=_SMS_CORE,
        extra=frozenset({"appointment_date", "appointment_window"}),
        group=GROUP_SMS,
        channel=models.CHANNEL_SMS,
    ),
    "sms_technician_on_the_way": _authored(
        "sms_technician_on_the_way",
        core=_SMS_CORE,
        extra=frozenset({"technician_name"}),
        group=GROUP_SMS,
        channel=models.CHANNEL_SMS,
    ),
    "service_outage_notice": _authored(
        "service_outage_notice",
        extra=frozenset({"area", "outage_start", "outage_end", "reason"}),
        notes=(
            "⚠ NOT A BOIL-WATER ADVISORY. r10 notes *'Boil-water variant follows TCEQ "
            "required language'* — regulator-mandated text this platform does not hold, and "
            "the same class of gap as OQ-253's rights footer. The default is a PLANNED "
            "INTERRUPTION notice; an advisory is a tenant variant with the regulator's own "
            "wording in it.",
        ),
    ),
    "service_door_hanger": _authored(
        "service_door_hanger",
        extra=frozenset({"work_type", "visit_date"}),
        group=GROUP_PRINTABLE,
        channel=models.CHANNEL_PRINT,
        core=_CONTACT | _RECIPIENT | frozenset({"utility_address"}),
    ),
    # ── Print (2) ────────────────────────────────────────────────────────
    "bill_insert": _authored(
        "bill_insert",
        group=GROUP_PRINTABLE,
        channel=models.CHANNEL_PRINT,
        core=_CONTACT,
        notes=(
            "The narrowest palette of any printable class, and deliberately: an insert is "
            "whatever the utility wants to say to everyone at once, so the DEFAULT is the "
            "one thing that is true every month — how to reach us. It states no figure, so "
            "it needs no account tokens.",
        ),
    ),
    "writeoff_notice": _authored(
        "writeoff_notice",
        group=GROUP_PRINTABLE,
        channel=models.CHANNEL_PRINT,
        core=_CONTACT | _RECIPIENT | frozenset({"utility_address"}),
        extra=frozenset({"amount", "date"}),
        notes=(
            "⚠ THE BODY MAKES NO LEGAL CLAIM ABOUT THE DEBT. r10 draws *'The debt remains "
            "owed and may be referred to a collection agency'*; whether a written-off "
            "balance is still collectable and whether this utility uses an agency are a "
            "legal question and a tenant practice, neither of them ruled. The default "
            "states the accounting fact — the balance was removed from active accounts — "
            "and invites the customer to call.",
        ),
    ),
}

#: Folded in, and the same codes REMOVED from `CLASSES_WITHOUT_CATALOG`: a class
#: cannot be both catalogued and uncatalogued, and `templates_api` reads that
#: dictionary to print the refusal sentence on SET-10. Leaving a stale entry
#: there would show a utility "no merge-variable catalogue exists" beside a
#: palette they can click.
CATALOGS.update(AUTHORED_CATALOGS)
for _authored_code in AUTHORED_CATALOGS:
    CLASSES_WITHOUT_CATALOG.pop(_authored_code, None)
del _authored_code


# ══════════════════════════════════════════════════════════════════════════
# THE FOUR CONTRACT PALETTES — PO RULING 2026-08-18 (CR-011 item 9),
# *"already answer - provide default and allow user to change"*
# ══════════════════════════════════════════════════════════════════════════
# **WHAT THE PO WAS SHOWN AND WHAT THEY RULED.** Ten decisions were put to the
# PO in one list; item 9 was *"the 4 template classes needing legal wording"* —
# the service agreement, the deposit agreement, the NACHA autopay authorization
# and the payment-plan agreement, all four shipping EMPTY, so a utility opening
# any of them on SET-10 found a class that refused every save. The answer,
# verbatim: **"already answer - provide default and allow user to change"**.
#
# It is a REVERSAL, and it generalises a precedent rather than inventing one:
# C-14 (2026-08-17) already delegated the plan-void notice in the same shape —
# *"you give default language for the plan-void notice only - we wil allow
# utility to make the changes"*. Two flagged classes came back the same day:
#
#   · the ACH authorization — *"Do it; put the details, I will handle it with
#     user"* → ship a LABELLED PLACEHOLDER that refuses to render, and enumerate
#     what the utility must supply (`CONTRACT_INPUT_REQUIREMENTS` below);
#   · the payment-plan agreement — this session recommended holding it and was
#     OVERRULED: *"create this dont leave it open ; once sample and defaults are
#     available we can make changes later; but without default sample
#     functionalities ill not work"*.
#
# ⚠ **THE THREE PALETTES BELOW ARE `derived_spelling` FROM END TO END**, exactly
# as the twenty-nine of 2026-08-17 are: BR-NOT-004 ratifies that these contract
# TYPES exist and no signed document writes one token of any of them in braces.
# `contract_payment_plan` is the exception in the other direction — A19 §3 writes
# its tokens verbatim and it keeps its own entry above.
#
# ⚠ **NO `{utility_logo}` (DEF-195)** and no token this platform cannot value.
# A contract is signed; a `——` in the middle of one is worse there than anywhere
# else in the product, so these palettes are the smallest set each document
# cannot be written without.
#
# ⚠ **NOTHING HERE PUBLISHES ANYTHING.** BR-NOT-002 makes every contract version
# effective-dated and `template_service.save_draft` refuses a contract draft with
# no `effective_from` — a date a human chooses, never provisioning day. So the
# bodies in `seed_templates.CONTRACT_DEFAULTS` are OFFERED to the designer and
# published by the System Admin with their own date. See that module's own note;
# the CR states the constraint in as many words and leaves it standing.

#: A contract's letterhead and the two parties, minus the logo. `{today}` is the
#: preparation date A19 §3.1 uses; `{customer_signature}` and `{date}` are its
#: signature block — the same two names, so one caller's context serves all four
#: contracts rather than four spellings of "who signed and when".
_CONTRACT_CORE = frozenset(
    {
        "utility_name",
        "utility_address",
        "support_phone",
        "support_email",
        "customer_name",
        "account_no",
        "service_address",
        "today",
        "customer_signature",
        "date",
    }
)


def _contract(
    code: str,
    *,
    extra: frozenset[str] = frozenset(),
    mandatory_content: tuple[str, ...] = (),
    mandatory_content_reason: str = "",
    notes: tuple[str, ...] = (),
) -> TemplateClass:
    """One contract class's palette. Every token is `derived_spelling`."""
    tokens = _CONTRACT_CORE | extra
    return TemplateClass(
        code=code,
        group=GROUP_CONTRACT,
        channel=models.CHANNEL_PRINT,
        source="PO ruling 2026-08-18 (CR-011 item 9) — *'already answer - provide default "
        "and allow user to change'*; palette shape from OQ-206 option (b)",
        tokens=tokens,
        derived_spelling=tokens,
        mandatory_content=mandatory_content,
        mandatory_content_reason=mandatory_content_reason,
        notes=notes,
    )


CONTRACT_CATALOGS: dict[str, TemplateClass] = {
    "contract_service_agreement": _contract(
        "contract_service_agreement",
        extra=frozenset({"service_start_date"}),
        notes=(
            "BR-NOT-004 type ②. The old refusal argued that *'the terms a customer agrees "
            "to when they take service are the utility's own and are not a product "
            "default'* — which is why the seeded body states the SHAPE of the bargain "
            "(we supply, you pay at our published rates, we bill, you give us access) and "
            "defers every figure and every period to the utility's own published policy. "
            "It sets no notice period, no deadline and no fee, because none is ruled.",
        ),
    ),
    "contract_deposit": _contract(
        "contract_deposit",
        extra=frozenset({"amount"}),
        notes=(
            "BR-NOT-004 type ③. `{amount}` is spelled as `email_deposit` spells it, so the "
            "deposit a customer signs for and the deposit email they receive carry one "
            "vocabulary. The old refusal's point stands inside the body rather than "
            "against it: *'it would have to state when a deposit is returned and on what "
            "condition, and no rule states either'* — so the default states neither and "
            "points at the tenant's own deposit policy, the same absence "
            "`email_deposit` already keeps (OQ-260).",
        ),
    ),
    "contract_autopay_authorization": _contract(
        "contract_autopay_authorization",
        extra=frozenset({"payment_method"}),
        notes=(
            "BR-NOT-004 type ④, and the ONE class in this product that ships a body "
            "designed to be refused. The palette exists so the utility's OWN wording has "
            "the parties and the signature block available to it; the platform's own body "
            "is a placeholder (`seed_templates.CONTRACT_AUTOPAY_PLACEHOLDER_BODY`) that "
            "`rendering.render` refuses while the marker is still in it. NO BANK DETAIL "
            "IS A TOKEN — a routing or account number is collected on the form the "
            "customer fills in and is never merged from this platform.",
        ),
    ),
}

CATALOGS.update(CONTRACT_CATALOGS)
for _contract_code in CONTRACT_CATALOGS:
    CLASSES_WITHOUT_CATALOG.pop(_contract_code, None)
del _contract_code


# ── CLICK-TO-ACCEPT AGREEMENTS · CR-190-BRC10 (PO 2026-10-22) ────────────────
#
# Decision log 2026-10-22, *"Click-to-accept agreements: the design confirmed
# with four answers"*. Two EMAIL classes beside the four contracts: the request
# (any Contracts-group agreement, the PDF attached, a single-use link) and the
# confirmation sent once the customer accepts. Their wording is SEEDED in every
# registry language by `agreement_wording` and edited per utility on Settings
# (PO, *"don't do any hardcoding"*). `{agreement_link}` is MANDATORY on the
# request: an agreement email with no link cannot be accepted, and the link is
# the ONLY way to accept (answer 4, *"No"* to accepting inside the portal).
_AGREEMENT_EMAIL_CORE = frozenset(
    {"utility_name", "support_phone", "first_name", "customer_name", "account_no", "agreement_name"}
)
AGREEMENT_REQUEST_EMAIL = "email_agreement_request"
AGREEMENT_ACCEPTED_EMAIL = "email_agreement_accepted"
AGREEMENT_EMAIL_CATALOGS: dict[str, TemplateClass] = {
    AGREEMENT_REQUEST_EMAIL: TemplateClass(
        code=AGREEMENT_REQUEST_EMAIL,
        group=GROUP_EMAIL,
        channel=models.CHANNEL_EMAIL,
        source=(
            "CR-190-BRC10 (PO 2026-10-22, decision log 'Click-to-accept agreements'). "
            "LANE-AUTHORED WORDING, a seeded default each utility edits."
        ),
        tokens=_AGREEMENT_EMAIL_CORE | {"agreement_link", "link_expires_on"},
        derived_spelling=_AGREEMENT_EMAIL_CORE | {"agreement_link", "link_expires_on"},
        mandatory_content=("{agreement_link}",),
        mandatory_content_reason=(
            "CR-190-BRC10: the customer accepts the agreement only through this link. "
            "A body without {agreement_link} gives them no way to accept it."
        ),
    ),
    AGREEMENT_ACCEPTED_EMAIL: TemplateClass(
        code=AGREEMENT_ACCEPTED_EMAIL,
        group=GROUP_EMAIL,
        channel=models.CHANNEL_EMAIL,
        source=(
            "CR-190-BRC10 (PO 2026-10-22: 'they then see a confirmation and receive a "
            "confirmation email'). LANE-AUTHORED WORDING, a seeded default each utility edits."
        ),
        tokens=_AGREEMENT_EMAIL_CORE | {"accepted_on", "accepted_name"},
        derived_spelling=_AGREEMENT_EMAIL_CORE | {"accepted_on", "accepted_name"},
    ),
}
CATALOGS.update(AGREEMENT_EMAIL_CATALOGS)
LISTINGS.update(
    {
        AGREEMENT_REQUEST_EMAIL: TemplateListing(
            code=AGREEMENT_REQUEST_EMAIL,
            name="Agreement to accept",
            category=CAT_ACCOUNT_LIFECYCLE,
            kind="Email",
            used_by=(
                "Sent with an agreement attached as a PDF. Its link lets the customer "
                "accept the agreement online."
            ),
            category_source=SOURCE_LANE,
        ),
        AGREEMENT_ACCEPTED_EMAIL: TemplateListing(
            code=AGREEMENT_ACCEPTED_EMAIL,
            name="Agreement accepted",
            category=CAT_ACCOUNT_LIFECYCLE,
            kind="Email",
            used_by="Sent when the customer accepts an agreement online.",
            category_source=SOURCE_LANE,
        ),
    }
)


# ── *What changed* · one sentence per correction reason · DEF-BIL-4454 ──────
# PO 2026-10-22, Q3 (decision log *"Corrected bills: … 'What changed' gets one
# sentence per reason"*): *"A. One plain sentence per reason, written by us,
# which the utility can edit on the templates screen, in all 11 languages"*.
# One class per seeded reason, `correction_reason_<code>`, filed under Billing
# and named by the clerk's own reason words. The sentence carries NO token and
# NO subject: it is printed inside `email_corrected_bill`'s
# `{correction_reason}` (`delivery_seam.bill_render_context`), never sent
# alone — which is also why its *in use* state follows that email's
# (`PRINTED_INSIDE`, read by `used_by_state`).
from apps.notifications import correction_reason_wording as _reason_wording  # noqa: E402

CORRECTION_REASON_CATALOGS: dict[str, TemplateClass] = {
    code: TemplateClass(
        code=code,
        group=GROUP_EMAIL,
        channel=models.CHANNEL_EMAIL,
        source=(
            "DEF-BIL-4454 (PO 2026-10-22, Q3). LANE-AUTHORED WORDING, a seeded default "
            "each utility edits."
        ),
        tokens=frozenset(),
        derived_spelling=frozenset(),
    )
    for code in _reason_wording.WORDING
}
CATALOGS.update(CORRECTION_REASON_CATALOGS)

# ══ CR-199-BRC10 S7 · LINK PLACEHOLDERS ═══════════════════════════════════════
#: A token whose VALUE is an address — `{pay_link}`, `{bill_link}`,
#: `{portal_link}`, `{reset_link}` … — is a LINK placeholder: in a rich email it
#: is written as a link or a button, and the placeholder picker tags it *link*.
#: Decided by the `_link` SUFFIX every such token already carries, rather than by
#: a hand-kept list that would go stale the first time a palette gains one
#: (hard-won law 2's shape). `{link_expires_on}` is a date, and is excluded by
#: the same rule: it does not END in `_link`.
LINK_TOKEN_SUFFIX = "_link"


def is_link_token(token: str) -> bool:
    return token.endswith(LINK_TOKEN_SUFFIX)


#: The two links the RENDERER supplies for any customer (`rendering._link_context`):
#: the portal's quick-pay page and the portal's front door, both built from
#: `PUBLIC_APP_ORIGIN` and the utility's address (`tenancy_seam`). Offered on
#: every EMAIL class addressed to an account holder — the classes whose palette
#: carries `{account_no}` — because those are the emails a "Pay now" button
#: belongs in (image 02). `{bill_link}` is NOT here: it is a per-bill credential
#: minted by billing, and stays on the two bill emails that already carry it.
CUSTOMER_LINK_TOKENS = frozenset({"pay_link", "portal_link"})

for _code, _klass in list(CATALOGS.items()):
    if _klass.channel == models.CHANNEL_EMAIL and "account_no" in _klass.tokens:
        CATALOGS[_code] = _dataclass_replace(
            _klass,
            tokens=_klass.tokens | CUSTOMER_LINK_TOKENS,
            derived_spelling=_klass.derived_spelling | CUSTOMER_LINK_TOKENS,
        )
del _code, _klass
LISTINGS.update(
    {
        _reason_wording.class_code(reason): TemplateListing(
            code=_reason_wording.class_code(reason),
            name=f"What changed · {label}",
            category=CAT_BILLING,
            kind="Email",
            used_by="Printed in the corrected bill email under What changed.",
            category_source=SOURCE_LANE,
        )
        for reason, label in _reason_wording.REASON_NAMES.items()
    }
)
#: A class printed only INSIDE another class's email, and that class. Its *in
#: use* state is its host's (`used_by_state`); the SET-12 gap count does not
#: list it as wording with no rule (`rule_catalog.seeded_wording_without_rule`),
#: because the host's rule is what sends it.
PRINTED_INSIDE: dict[str, str] = {
    code: "email_corrected_bill" for code in CORRECTION_REASON_CATALOGS
}


#: **WHAT THE UTILITY MUST SUPPLY, IN PLAIN ENGLISH — the second half of the
#: PO's ACH ruling, and a DELIVERABLE rather than a courtesy.** PO, 2026-08-18:
#: *"Do it; put the details, I will handle it with user"* — the PO is taking
#: this to a real customer, so "paste your own wording" is not an answer. This
#: is the list they can hand over.
#:
#: It is held as DATA, in one place, because three consumers need the same
#: words: the placeholder body prints it on the document's own face, the
#: renderer's refusal quotes it when somebody tries to use the placeholder, and
#: `GET /template-catalog/{code}` serves it to the screen. Three copies of a
#: list like this is the drift hard-won law 1 warns about.
#:
#: ⚠ **IT ENUMERATES WHAT MUST BE DECIDED, NOT WHAT IT MUST SAY.** This repo
#: does not hold the NACHA Operating Rules and nothing here is legal advice —
#: every line names a decision the utility's own bank (its ODFI) and counsel
#: make. In particular NO PERIOD, FEE OR DEADLINE IS STATED, which is the rule
#: every authored body in this product runs under: r10's *"$25 NSF fee"* and
#: *"retry within 5 days"* are sample prose for a fictional utility and appear
#: nowhere.
CONTRACT_INPUT_REQUIREMENTS: dict[str, tuple[str, ...]] = {
    "contract_autopay_authorization": (
        "Your utility's legal name exactly as it will appear on the customer's bank "
        "statement, and the company identification number your bank issued you for "
        "collecting payments.",
        "The sentence that says the customer authorises you to take recurring electronic "
        "(ACH) debits from the bank account they name, and that the amount VARIES because "
        "a utility bill varies — including how you tell them each amount before you take "
        "it, and how long before.",
        "When the debit is taken: the day of the month, or the number of days after the "
        "bill date, and what you do when that day falls on a weekend or a bank holiday.",
        "How the customer cancels: what they have to send you, where they send it, and "
        "how far ahead of a debit it has to reach you for that debit to stop.",
        "What happens when a debit is returned unpaid: whether you charge for it (that "
        "amount is your own charge code, not ours) and whether you try again.",
        "The customer's rights if a debit was not authorised, in the wording your bank or "
        "your counsel gives you.",
        "That the customer gets a copy of what they signed, and how long you keep the "
        "signed authorisation after it ends — your bank will tell you the period they "
        "require.",
        "The signature block: the customer's name, their signature, the date, the bank "
        "account type (checking or savings), and the account and routing numbers they "
        "write in themselves. Never merge a bank number from this platform.",
    ),
}


def required_from_utility(template_code: str) -> tuple[str, ...]:
    """What the utility has to supply before this class can be used — plain English.

    Empty for every class that ships a usable default, which is all of them but
    one: the ACH authorization is the single document in this product whose
    wording is prescribed by a scheme (NACHA) this repo does not hold.
    """
    return CONTRACT_INPUT_REQUIREMENTS.get(template_code, ())


#: ⚠ **[AMENDED 2026-08-18 — THIS DICTIONARY IS NOW EMPTY, AND EVERY ARGUMENT
#: IT HELD IS QUOTED BELOW RATHER THAN DELETED.]** The PO ruled on all four
#: contracts in one sentence (CR-011 item 9), verbatim:
#:
#:   > *"the 4 template classes needing legal wording - already answer -
#:   > provide default and allow user to change"*
#:
#: and, the same day, on the two this session flagged back at them:
#:
#:   > *"Do it; put the details, I will handle it with user"* — the ACH
#:   > authorization: build the labelled placeholder AND write down what the
#:   > utility must supply, because the PO is taking it to a real customer;
#:   > *"create this dont leave it open ; once sample and defaults are available
#:   > we can make changes later; but without default sample functionalities ill
#:   > not work"* — the payment-plan agreement, OVERRULING this session's
#:   > recommendation to hold it.
#:
#: **The general principle in the PO's reasoning is why the entries below are
#: kept in full:** a class held empty makes the FEATURE not work at all, and an
#: imperfect default that is present can be changed later, while an absent one
#: leaves a utility with nothing to demonstrate and nothing to edit. Two of the
#: four arguments below are STILL TRUE as engineering facts and are answered
#: inside the bodies rather than by the bodies existing — the schedule table is
#: still a repeating block this renderer cannot express, and the ACH wording is
#: still prescribed by a scheme this repo does not hold. What changed is who
#: decides what happens next, and the PO has decided.
#:
#: THE FOUR ENTRIES, AS THEY READ THE MOMENT BEFORE THEY LEFT:
#:
#:   > **contract_payment_plan** — *"A CONTRACT SOMEBODY SIGNS, not a notice
#:   > they read. Three reasons stack and any one of them alone would be enough.
#:   > (1) OQ-244: A19 §3 catalogues every token except the instalment SCHEDULE
#:   > TABLE (# · due date · amount · remaining), a repeating block this
#:   > renderer cannot express — so a seeded agreement would be e-signed stating
#:   > a total and not one due date or instalment amount. (2) BR-NOT-002 makes
#:   > every contract version EFFECTIVE-DATED and `template_service.save_draft`
#:   > refuses a contract draft without an `effective_from`; that date is a
#:   > human's choice, not the day provisioning ran. (3) r10's payment-plan
#:   > prose describes a product that no longer exists — 'Miss an installment
#:   > and the plan cancels' was superseded by the PO on 2026-08-11 ('nodrop we
#:   > chase for payments until write off'), so the one drawn source for this
#:   > document is actively wrong."*
#:   >
#:   > **Answered, point by point, rather than overridden.** (1) survives and is
#:   > carried ON THE FACE of the document: `{schedule_table}` is BR-NOT-016's
#:   > ruled token, it is MANDATORY content so no edit can drop it, and while
#:   > nothing builds the block it renders `——` under a line telling the reader
#:   > not to sign a blank schedule. (2) survives untouched and is the reason
#:   > nothing here is published — see `seed_templates.CONTRACT_DEFAULTS`.
#:   > (3) is met by authoring the clause the 2026-08-11 ruling leaves true: a
#:   > missed instalment does not cancel the plan.
#:
#:   > **contract_service_agreement** — *"A CONTRACT SOMEBODY SIGNS. BR-NOT-004
#:   > type ② confirms the type exists and A19 gives content blocks for the
#:   > payment-plan agreement and for no other contract, so there is nothing to
#:   > author from. The terms a customer agrees to when they take service are
#:   > the utility's own and are not a product default. BR-NOT-002's
#:   > effective-dating applies as above. OQ-206 stays open for the three
#:   > contracts."*
#:   >
#:   > **Overtaken by the ruling.** "Not a product default" is precisely the
#:   > judgement the PO reversed — the default is a starting point the utility
#:   > edits, marked as one. What survives is that the terms carry no figure and
#:   > no period this repo has not ruled, so the body defers each to the
#:   > utility's own published policy.
#:
#:   > **contract_deposit** — *"A CONTRACT SOMEBODY SIGNS — BR-NOT-004 type ③,
#:   > content unwritten. It would have to state when a deposit is returned and
#:   > on what condition, and no rule states either (the same gap that kept the
#:   > period out of `email_deposit`). OQ-206."*
#:   >
#:   > **Answered inside the body:** it states neither, exactly as
#:   > `email_deposit` states neither, and points at the tenant's deposit
#:   > policy. r10's *"refunded automatically after 12 months of on-time
#:   > payments"* appears nowhere.
#:
#:   > **contract_autopay_authorization** — *"A COMPLIANCE DOCUMENT. BR-NOT-004
#:   > type ④ is NACHA-required for recurring ACH: its wording is prescribed by
#:   > a scheme this repo does not hold, and it is the last document in the
#:   > product that should be drafted by inference. OQ-206."*
#:   >
#:   > **ACCEPTED BY THE PO, NOT OVERRULED** — *"Do it; put the details, I will
#:   > handle it with user"*. This is the one class whose "default" is a
#:   > PLACEHOLDER: it is visibly labelled, it states this reason on its own
#:   > face, `rendering.render` REFUSES it while the marker is in it, and
#:   > `CONTRACT_INPUT_REQUIREMENTS` enumerates in plain English what the
#:   > utility's bank and counsel must supply. The refusal is the feature.
#:
#: The dictionary itself stays — as an EMPTY dict with its accessor intact —
#: because the mechanism is the useful part: the next class a ruling cannot
#: reach goes in here with its argument, and every reader of `absent_reason`
#: keeps working unchanged.
NOT_AUTHORED_BY_PO_RULING: dict[str, str] = {
    # ⚠ **THE `plan_notice_void` ENTRY LEFT THIS DICTIONARY ON 2026-08-18, AND
    # WHAT IT SAID IS QUOTED RATHER THAN DELETED** — the same discipline the
    # three disconnect tiers' departure keeps above, because the entry argued,
    # correctly for its day, that the class should probably be WITHDRAWN:
    #
    #   > *"THERE IS NO EVENT LEFT TO ANNOUNCE … the PO superseded [the 2nd-miss
    #   > void] on 2026-08-11, verbatim 'nodrop we chase for payments until
    #   > write off' … A plan ends by being PAID or by having its arrears
    #   > written off — neither is a void. Authoring a body would mean writing a
    #   > notice for an event the product cannot produce. OQ-260 asks whether to
    #   > withdraw the class."*
    #
    # **What changed is a ruling on the WORDING, not on the event.** The PO
    # answered OQ-260(a)'s withdraw-or-keep with a third option — keep it and
    # give it default language (C-14, 2026-08-17, verbatim: *"you give default
    # language for the plan-void notice only - we wil allow utility to make the
    # changes"*). The 'nodrop' ruling is UNTOUCHED: nothing in this product
    # voids a plan and nothing schedules this notice, and the class's own note
    # in AUTHORED_CATALOGS says so. Wording ahead of a flow is the posture the
    # PO ratified for the service templates on 2026-08-16.
}


def not_authored_reason(template_code: str) -> str | None:
    """Why this catalogued class still has no platform body, or None."""
    return NOT_AUTHORED_BY_PO_RULING.get(template_code)


def listing_for(template_code: str) -> TemplateListing | None:
    """This class's SET-09 row, or None when it is not a listable class.

    None means one of two things and BOTH are correct absences: the code is
    billing's (`bill_residential`, `bill_commercial`, `statement` — B2 r10 #4
    gives them their own registry and their own chooser), or it is
    SUPERSEDED_CLASSES' legacy `disconnect_notice`. Neither belongs on a catalog
    a person edits.
    """
    return LISTINGS.get(template_code)


def listable_codes() -> tuple[str, ...]:
    """Every class SET-09 lists, in category order then name.

    Sorted HERE rather than in the API so the catalog's order is a fact about
    the vocabulary and not about whichever endpoint asked. CR-007 puts the
    chips in a fixed order and the inventory is grouped by category, so the
    default sort follows the chips.
    """
    return tuple(
        sorted(
            LISTINGS,
            key=lambda code: (
                CR_CATEGORIES.index(LISTINGS[code].category),
                LISTINGS[code].name.lower(),
            ),
        )
    )


# ══════════════════════════════════════════════════════════════════════════
# `used_by` — THE SENTENCE, AND THE TWO FACTS BEHIND IT (DEF-NOT-4531)
# ══════════════════════════════════════════════════════════════════════════
#
# The Product Owner opened *Bill ready · e-bill email* on the live product and
# read, under a heading with the wording printed beneath it:
#
#     "Email · Not in use yet — no wording has been written for it."
#
# Verbatim: *"in templates why are you saying this tempalte not in use"*. The
# wording for that class is authored, seeded and published; a live notification
# rule had the class selected and switched on. The sentence was wrong on both
# halves at once.
#
# ⚠ **IT WAS NOT ONE ROW. THE SWEEP FOUND 23 OF 38.** Fifteen said *no wording
# has been written for it* and **every one of the fifteen had wording**; eight
# more said *not in use yet* while a live writer fires them (ten rows were
# wrong on both counts, which is why the two numbers do not add to 23).
#
# ⚠ **AND THE CAUSE IS NOT CARELESSNESS — IT IS THE FIELD'S SHAPE.** `used_by`
# is a hand-written string describing two MACHINE-KNOWABLE facts:
#
#   1. *is the wording written* — `seed_templates.SEEDABLE` /
#      `seed_templates.CONTRACT_DEFAULTS` answer it exactly;
#   2. *does anything send it* — `rule_catalog.EVENTS` answers it exactly, and
#      an event's `trigger_blocked_by` says whether the writer exists TODAY.
#
# Every one of the 23 sentences was TRUE the day it was typed. Wave after wave
# then authored a body or wired a writer — and authoring the wording and
# updating the sentence that says there is none are two acts, only the first of
# which feels like the work. That is hard-won law 2's mirror, and CLAUDE.md's
# instruction for it is exact: *"WHEN YOU WRITE A HOLD, WRITE THE TEST THAT
# FIRES WHEN THE HOLD EXPIRES."*
#
# So the two facts are DERIVED here and never typed, and
# `tests/test_def_not_4531_used_by_truth.py` fails the build when a sentence
# contradicts them. The sentence itself stays hand-written, because what it adds
# over the two booleans — *"Sent when a payment comes back"* — is the half a
# clerk actually reads and no derivation can write.


def has_wording(template_code: str) -> bool:
    """Is there a body for this class — planted, or offered on the designer?

    The one place this question is answered, so a screen, a sentence and a test
    cannot each answer it differently. `SEEDABLE` is what provisioning plants;
    `CONTRACT_DEFAULTS` is what the designer offers for the four agreements a
    human must date before they publish. Either is wording that EXISTS, which is
    what *"no wording has been written for it"* denies.

    Imported inside the function: `seed_templates` imports THIS module at load
    time, so a module-level import either way is a cycle — the same idiom
    `services.channel_decision` uses on `rule_service`.
    """
    from apps.notifications import seed_templates

    if template_code in seed_templates.CONTRACT_DEFAULTS:
        return True
    return any(entry.code == template_code for entry in seed_templates.SEEDABLE)


def firing_events(template_code: str) -> tuple[tuple[str, str], ...]:
    """Every `(event, channel)` whose LIVE writer sends this class today.

    Three conditions, and all three matter:

      * the event's catalogue names this class for that channel;
      * that channel is one the event OFFERS (`sms_disconnect` is named for a
        channel `disconnect_notice` does not offer, so nothing can send it);
      * the event's trigger is not blocked — `trigger_blocked_by is None` is the
        catalogue's own statement that a real writer exists today.

    Empty means nothing sends it, which is what *"Not in use yet"* asserts.
    """
    from apps.notifications import rule_catalog

    found: list[tuple[str, str]] = []
    for event in rule_catalog.EVENTS:
        if event.trigger_blocked_by is not None:
            continue
        for channel, code in event.template_classes.items():
            if code == template_code and channel in event.channels:
                found.append((event.key, channel))
    return tuple(found)


#: The four states the catalog column draws. THE SERVER'S ANSWER, and it is the
#: durable fix `TemplateCatalog.tsx` asked for in as many words: *"THE DURABLE
#: FIX IS A SERVER FIELD — a `used_by_state` on the catalog row, beside the
#: sentence — and this lane does not mint it, because `apps/notifications/`
#: belongs to another lane this hour."* Until today the screen derived it by
#: regular expression over the prose, so a sentence that drifted took the status
#: pill with it.
USED_BY_IN_USE = "in-use"
USED_BY_NOT_IN_USE = "not-in-use"
USED_BY_NO_WORDING = "no-wording"
USED_BY_PLACEHOLDER = "placeholder"
USED_BY_STATES = (
    USED_BY_IN_USE,
    USED_BY_NOT_IN_USE,
    USED_BY_NO_WORDING,
    USED_BY_PLACEHOLDER,
)


#: ⚠ **WHAT THE DERIVATION CANNOT SEE, WITH THE NUMBER BESIDE IT.** The PO's
#: ruling of 2026-09-07 is explicit about this and quotes the repository's own
#: worst case back at it: `G32` truthfully reported **0 unresolved** over **21
#: live refusals it could not see**, because it resolved a key only where the
#: helper was defined in the same file. *"A derived sentence that cannot see
#: some path by which a template gets used must PRINT WHAT IT SKIPPED BESIDE
#: WHAT IT CHECKED — a declared blind spot with no number attached is
#: indistinguishable from an empty one."*
#:
#: So these are the paths by which a template can be used that this derivation
#: does NOT look at, written in a clerk's words because they travel to the
#: screen. Two, and both are real:
USED_BY_UNCHECKED: tuple[str, ...] = (
    "Whether anything has actually been sent on it. Nothing is reporting sends back "
    "on this product yet, so a template waiting on a switch nobody has turned on "
    "would read as unused, which it is not.",
    "Wording picked by a job that names it directly rather than through a "
    "notification rule — the reminder and receipt letters do that.",
)


#: Classes a writer sends BY NAME on every request, with no SET-12 rule behind
#: them, because a utility switching them off would lock people out: a reset
#: link is asked for by the person who then waits for it (PO 2026-10-22,
#: *"instant email"*). In use whenever their wording exists. Every member is
#: also a key of `rule_catalog.WRITER_REACHED_CLASSES` (the gap count's side of
#: the same fact); the staff sign-in classes are NOT here because SET-12 events
#: (`staff_user_invited`, `staff_password_reset`) name them.
SENT_DIRECTLY: frozenset[str] = frozenset(
    {
        "portal_password_reset",
        # CR-189-BRC10 / DEF-CWP-10402 — added at merge (2026-10-22).
        "portal_enrolment_code",
        "portal_email_change_code",
        "portal_email_changed_notice",
    }
)


def used_by_state(template_code: str, *, rule_usage: dict[str, bool] | None = None) -> str:
    """Which of the four states this class is in, from FACTS only.

    Order is the rule and it is the screen's own: a class with no wording is
    reported as such whatever else is true of it, because a person opening the
    row has to write the wording before anything else matters. `placeholder` is
    narrower than `no-wording` — there IS a body and the product refuses to
    print it — so it is asked first.

    ⚠ **`rule_usage` IS THE TENANT'S OWN ANSWER AND IT WINS WHERE IT HAS ONE
    (PO ruling 2026-09-07 — *"based on actual usage by notifications"*).**
    `rule_service.template_usage()` builds it: `code → True` where a rule this
    utility has ENABLED carries the template on a channel they have ENABLED.
    A code the map does not mention is a code no rule of theirs names, and the
    PLATFORM answer below decides — which is what a tenant who has never opened
    the settings screen must see, since they have no rows at all.

    ⚠ **AND IT DOES NOT ASK WHETHER ANYTHING WAS EVER SENT.** That is fact 4 of
    the ruling's four and it is a trap on this deployment: the notification
    screen already says *"Nobody is reporting these back to us yet, because
    sending is not switched on"*, so reading silence as absence would ship the
    same lie in a new coat. `USED_BY_UNCHECKED` says so out loud, on the wire.
    """
    from apps.notifications import seed_templates

    if seed_templates.is_placeholder(template_code):
        return USED_BY_PLACEHOLDER
    if not has_wording(template_code):
        return USED_BY_NO_WORDING
    if template_code in SENT_DIRECTLY:
        return USED_BY_IN_USE
    if template_code in PRINTED_INSIDE:
        # DEF-BIL-4454 — a sentence printed inside another email is in use
        # exactly when that email is.
        return used_by_state(PRINTED_INSIDE[template_code], rule_usage=rule_usage)
    if rule_usage is not None and template_code in rule_usage:
        return USED_BY_IN_USE if rule_usage[template_code] else USED_BY_NOT_IN_USE
    return USED_BY_IN_USE if firing_events(template_code) else USED_BY_NOT_IN_USE


def superseded_reason(template_code: str) -> str | None:
    """Why this class is retained but hidden, or None when it is current."""
    return SUPERSEDED_CLASSES.get(template_code)


#: ⚠ ADDED 2026-08-30 · DEF-2473. WHICH CHANNELS EACH `kind` STRING IS A FORM
#: FOR — the fact that had never been written down anywhere, and whose absence
#: is the whole defect.
#:
#: A queue write carries ONE template pin for every channel it names, and
#: BR-NOT-024's print floor ADDS a channel to writes the caller never asked to
#: widen. Put those two together and a caller asking for email on a floored
#: source kind silently queues a PRINT row pinned to an EMAIL class. That is what
#: happened to the returned-payment letter, and nothing could see it: `kind` was
#: prose on a catalog row that only ever reached a screen, so no code could ask
#: *"is this class a form for this channel?"* — the one question that catches it.
#:
#: **Keyed on the EXACT strings `LISTINGS` uses, and it FAILS CLOSED.** Parsing
#: the prose (*"does it contain the word print"*) would quietly answer for a kind
#: nobody had thought about; an unknown kind raises instead, so a lane inventing
#: a new one has to come here and say which channels it serves. Hard-won law 3:
#: the unsafe option must be the one you type.
CHANNELS_BY_KIND: dict[str, tuple[str, ...]] = {
    "Print": ("pdf_print",),
    "Letter": ("pdf_print",),
    "PDF page": ("pdf_print",),
    # CR-190-BRC10 — was "PDF + e-signature", which named a provider nobody
    # connected. What exists is the PDF and the click-to-accept link
    # (`apps/customers/agreements.py`); the link rides the request EMAIL, a
    # class of its own, so this form is still a print form only (DEF-2473).
    "PDF + click-to-accept": ("pdf_print",),
    "PDF + email": ("pdf_print", "email"),
    "Print + email": ("pdf_print", "email"),
    "Certified print + email": ("pdf_print", "email"),
    "Door hanger print + email": ("pdf_print", "email"),
    "Email": ("email",),
    "Email + SMS": ("email", "sms"),
    "SMS": ("sms",),
    "In-app message": ("in_app",),
}


class UnknownTemplateKind(Exception):
    """A `LISTINGS` row names a `kind` no channel mapping covers.

    Raised rather than guessed: a class whose channels nobody has stated is
    exactly the state `payment_failed_letter` was created to end, and answering
    it by inference is how the email class came to be printed in the first place.
    """


def channels_for_kind(kind: str) -> tuple[str, ...]:
    """The channels a class of this `kind` is a form for. Never guesses."""
    try:
        return CHANNELS_BY_KIND[kind]
    except KeyError:
        raise UnknownTemplateKind(
            f"{kind!r} is a template kind with no stated channels, so nothing can say "
            "whether a class of this kind may be queued for print, email or SMS. Add it "
            "to `CHANNELS_BY_KIND` — the answer is a decision, not something to infer "
            "from the words in the name."
        ) from None


def class_serves_channel(template_code: str, channel: str) -> bool | None:
    """Is this class a form for this channel? None when the class is not listed.

    `None` is a real and correct third answer, never a soft "no": billing's own
    classes (`bill_residential`, `bill_commercial`, `statement`) have their own
    registry and never appear in `LISTINGS`, and so does the superseded legacy
    `disconnect_notice`. A caller that must not proceed on an unknown should test
    `is True`, and one auditing the catalog should skip the `None`s rather than
    report them as violations.
    """
    listing = LISTINGS.get(template_code)
    if listing is None:
        return None
    return channel in channels_for_kind(listing.kind)


#: ⚠ ADDED 2026-09-07 · CR-076 item 1. WHICH DESIGNER SURFACE EACH CHANNEL IS
#: DRAWN AS — the fact SET-10's preview tabs are derived from, so that nothing
#: on a screen has to type the list out.
#:
#: The designer draws five surfaces (`printable`, `email`, `sms`, `in_app`,
#: `contract`) and the platform queues four CHANNELS. They are not the same
#: axis and the difference is exactly one entry: a contract is printed like any
#: other printable and it is a DIFFERENT DOCUMENT to look at, so `pdf_print`
#: resolves through the class's own `group`.
SURFACE_BY_CHANNEL: dict[str, str] = {
    models.CHANNEL_PRINT: GROUP_PRINTABLE,
    models.CHANNEL_EMAIL: GROUP_EMAIL,
    models.CHANNEL_SMS: GROUP_SMS,
    models.CHANNEL_IN_APP: GROUP_IN_APP,
}

#: The designer's name for a contract page. NOT `GROUP_CONTRACT` — that is
#: `"contracts"`, plural, and the screen's `DesignerKind` union has always been
#: singular. Written here rather than fixed on either side, because renaming a
#: served enum value is a contract change and this is not one.
SURFACE_CONTRACT = "contract"


def designer_surfaces(kind: str, group: str | None) -> tuple[str, ...]:
    """Every surface ONE template class is a form for, in channel order.

    ⚠ **THIS IS THE ANSWER TO "WHAT DOES THIS TEMPLATE ACTUALLY HAVE", AND IT
    IS DERIVED FROM `CHANNELS_BY_KIND` RATHER THAN LISTED AGAIN.** The screen
    that asks it — SET-10's preview tabs — must not carry a hardcoded list of
    five: this repo has already paid for that once, when the service list was
    typed out by hand in two front-end files and an eleventh service silently
    never appeared on the sign-up screen (CLAUDE.md hard-won law 2). A tab bar
    built from a constant would offer an empty SMS tab on a letter, and would go
    on offering exactly five surfaces on the day a sixth is added here.

    `"Print + email"` gives `("printable", "email")`; `"SMS"` gives `("sms",)`,
    which is one surface and therefore no switcher at all.

    **It never guesses and it never widens.** `channels_for_kind` raises on a
    kind nobody has stated channels for, and that raise travels — a class whose
    surfaces are unknown must not quietly acquire the five the screen used to
    assume. The caller decides what to serve for an unknown kind; see
    `templates_api._surfaces_for`.

    Order is `CHANNELS_BY_KIND`'s own, which reads print-first, so a letter that
    is also emailed opens on the tab a person expects to read first.
    """
    seen: list[str] = []
    for channel in channels_for_kind(kind):
        surface = SURFACE_BY_CHANNEL.get(channel)
        if surface is None:
            # A channel with no drawing is not drawn. Inventing one would be
            # the "comment claiming a guarantee" shape: a tab that opens onto a
            # pane nobody has designed.
            continue
        if surface == GROUP_PRINTABLE and group == GROUP_CONTRACT:
            surface = SURFACE_CONTRACT
        if surface not in seen:
            seen.append(surface)
    return tuple(seen)


def catalog_for(template_code: str) -> TemplateClass | None:
    """The class's palette, or None when this platform has no catalog for it.

    None is never "no tokens allowed" — `CLASSES_WITHOUT_CATALOG` says which
    unspecified class it was and why, and the renderer quotes that reason
    verbatim in its refusal.
    """
    return CATALOGS.get(template_code)


def known_template_codes() -> tuple[str, ...]:
    """Every template class this platform knows of, catalogued or not.

    Both dictionaries, because a class with no catalog still EXISTS: a queue row
    pinned to `email_bill_ready` is a real row for a real ratified template, and
    reporting it as an unknown code would send whoever reads the dashboard
    looking for a typo instead of for OQ-206.
    """
    return tuple(sorted({*CATALOGS, *CLASSES_WITHOUT_CATALOG}))


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-NOT-005@5e8c33f (sha1[:7] of the four sources this slice was authored from, concatenated in order: 04-docs/01-spec/19-document-templates.md — §1/§2/§3 + the 2026-08-07 r8 revision + the three 2026-08-08 addenda — · 04-docs/01-spec/13-copy-and-microcopy.md — the reminder/receipt preview copy US-NOT-005 §1 names — · 04-docs/05-modules/10-notifications/06-epics/EP-NOT-02-templates-rendering.md · 10-notifications/03-field-map.md §2)
# generated: 2026-08-15 by story-coder (W3 notifications delivery-core lane — the rendering slice)
# checklist: A✔ B✔ C✔ D=deferred(not an API surface — reference data consumed by the renderer; the designers' palette ENDPOINT is US-NOT-007/008 and is not in this lane) E=deferred(no-frontend-half — the S94–S106 designers are US-NOT-007/008) F✔ G✔ H=deferred(PO 2026-08-09)
# gates: ruff✔ black✔ · pytest tests/test_us_not_005_rendering.py — the whitelist
#         was proved RED by adding `meter_no` to the receipt catalog, at which
#         point US-NOT-005 TC-5 stopped refusing and failed (transcript in the
#         lane report)
# exceptions: (1) SEVENTEEN CLASSES HAVE NO CATALOG AND NONE IS GUESSED —
#         the six A19 r8 email bodies, the four SMS bodies, three of
#         BR-NOT-004's four contract types and BR-NOT-007's three plan notices.
#         Each is registered in `CLASSES_WITHOUT_CATALOG` with its reason;
#         OQ-206 and OQ-207 were minted rather than answered, and the renderer
#         REFUSES them (field map N-1: *"dispatch holds safely on missing
#         published template; content never invented"*).
#         (2) `derived_spelling` MARKS THE NAMES THIS FILE CHOSE. Their CONTENT
#         is ratified by A19 in prose ("balance before/after, processed-by staff
#         name"); only the token spelling is engineering vocabulary. Kept as a
#         separate set so a reviewer never has to diff against A19 to tell a
#         quoted token from a chosen one.
#         (3) `{utility_rep}` IS DELIBERATELY ABSENT from the payment-plan
#         contract even though A19 §3 lists it — the 2026-08-08 addendum
#         SUPERSEDES the countersign block (BR-CUS-044).
#         (4) THE BILL AND STATEMENT CATALOGS LIVE HERE while their DESIGNERS
#         (S91–S93) are billing's (US-BIL-021). One renderer serves every class;
#         a second copy of the bill token list in billing is the drift hard-won
#         law 1 warns about. Screen ownership is unchanged and is stated on each
#         entry.
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
