# ── Trace ──────────────────────────────────────────────
# Story:    US-CWP-010 (EP-CWP-02) — track anything · US-CWP-002 — the bill
#           lookup (wave P). Screens: CWP-012 · CWP-002
# Rules:    BR-CWP-021 (a guest sees an amount and a status, NEVER a person) ·
#           BR-CWP-024 (a public reference lookup returns PROGRESS AND NEVER
#           DATA — the status and the dates, no name, no balance, no other
#           reference on the account) · BR-CWP-019/020 (the ONE exception: a
#           bill number plus the service postcode may show the amount owing and
#           a MASKED name) · BR-CWP-003's shape (declared as DATA so a gate can
#           read it)
# Tests:    10-scripts/gates/g92_guest_leaks_nothing.py (reads this file with
#           `ast`; selftest replays `email` added to a declared response)
# Impacts:  apps/portal/selectors.py · seams/customers_seam.py — the two files
#           that build what a stranger is allowed to see
# ───────────────────────────────────────────────────────
"""What a GUEST may be told, declared as data (`BR-CWP-021` · `BR-CWP-024`).

**Read by G92, never imported by the product.** The gate parses this file with
`ast`, finds each named function in its named file, and asserts that every key
of every dictionary that function RETURNS appears in its allow-list — and that
no key anywhere in it is one of the person-shaped names below.

WHY AN ALLOW-LIST AND NOT A DENYLIST
------------------------------------
A denylist answers *"did somebody add `email`?"*. An allow-list answers *"is
every field here one somebody decided a stranger may see?"* — which is the
question `BR-CWP-024` actually asks, because the field that leaks will be the
one nobody thought of. `request_progress_view`'s own docstring already makes
the point: *"a field that is served and merely not drawn is still served."*

⚠ **THIS DECLARES OUTPUT, NOT INPUT.** A guest form legitimately RECEIVES a
name, an email and a phone — that is somebody typing their own details into
`CWP-047`. `applications.py` is therefore not listed here and must not be: the
rule is about what the product TELLS a stranger, and adding an input path to
this file would either force `first_name` into the allow-list or turn the gate
red on a form working correctly.

`allowed` is `None` until the wave that builds that response lands — the row is
here from the start so the boundary is a machine check rather than a sentence,
which is the shape `write_points.py` established.
"""

from __future__ import annotations

#: `<file under apps/portal/>::<function>` → the keys it may return.
#: The comment beside each row is the rule that decided it.
GUEST_RESPONSES: dict[str, tuple[str, ...] | None] = {
    # `BR-CWP-024` — progress and never data. The state and three dates: no
    # applicant name, no address, no fee, no outcome reason, no account.
    "seams/customers_seam.py::request_progress_view": (
        "series",
        "reference",
        "status",
        "reported_at",
        "submitted_at",
        "closed_at",
        # `DEF-CWP-9049` (2026-10-02) — may the applicant answer *Ask for
        # more* with a file, and how many more may they send. A yes/no and a
        # count of their OWN files; nothing the utility holds about them.
        "can_add_document",
        "documents_left",
    ),
    # ⚠ **BUILT 2026-09-04 (CR-068 wave P, screen half), AND THE LIST BELOW IS
    # THE ONE RESERVED BEFORE THE CODE EXISTED — six keys, unchanged from the
    # sentence that stood here while `allowed` was `None`: the amount, the
    # currency, the status, the due date, and `masked_name` — first initial plus
    # a masked surname, `M. A••••••` (`BR-CWP-020`). Never `name`, never the
    # address. `number` and `replaced_by` are the two the sentence did not
    # spell and both are HUMAN REFERENCES a person is holding on paper (B14
    # rule 31): the bill number they typed, echoed back, and — for a corrected
    # bill — the number that replaced it, without which `US-CWP-003` TC-7
    # cannot direct payment anywhere (`BR-CWP-042`).
    #
    # ⚠ **THE OWING FIGURE IS KEYED `amount`, AND THAT IS NOT A SYNONYM CHOSEN
    # FOR STYLE.** `owing` and `balance` are both in `NEVER_ON_A_GUEST_RESPONSE`
    # below, which is the belt-and-braces clause doing exactly its job: it does
    # not know that `BR-CWP-019` carves out this one response, and it should not
    # — widening that tuple to let one screen through would switch the check off
    # for every other. So the KEY is `amount`, the money cell `apps/portal/
    # money.py` already builds for the whole guest surface, and the WORD *owing*
    # is written by the eleven catalogues where it belongs (B14 rule 35).
    "selectors.py::bill_lookup": (
        "number",
        "amount",
        "status",
        "due_on",
        "masked_name",
        "replaced_by",
    ),
    # ⚠ **THE RECEIPT — CR-068 wave R (`US-CWP-005`), AND IT IS NARROWER THAN
    # THE LOOKUP ABOVE, NOT WIDER.** A person who has just paid is shown what
    # `BR-CWP-028` says a guest flow ends on: a reference they can keep, the
    # figure, what it went against, and how. `masked_name` is deliberately NOT
    # here — they saw it at step 2 to confirm they had the right bill, and a
    # receipt has no such job to do, so `BR-CWP-021` takes it off.
    #
    # `reference` is `PAY-26-08841` and `against` is `BL-2608-0141`: both are
    # HUMAN references somebody reads down a telephone, never a row id (B14
    # rule 31). `brand` and `last_four` are `BR-CWP-057`'s two visible facts and
    # are listed because `method` is a NESTED dict and G92 walks into it — the
    # gateway TOKEN is not among them and must never be.
    #
    # ⚠ **`receipt_sent` IS A BOOLEAN AND THERE IS NO ADDRESS BESIDE IT.**
    # `US-CWP-004` §4 makes the receipt address deliberately somebody else's —
    # *"a guest may be a neighbour"* — so echoing it would put a stranger's email
    # on a screen anybody holding the bill can reach. The screen needs to know
    # WHETHER, which is what `US-CWP-005` TC-2 turns on, and never WHERE.
    "selectors.py::guest_payment_receipt": (
        "reference",
        "amount",
        "paid_at",
        "against",
        "method",
        "brand",
        "last_four",
        "receipt_sent",
    ),
    # ⚠ **THE SAME PAYMENT, LOOKED UP A FORTNIGHT LATER — AND IT IS THE
    # NARROWEST ROW IN THIS FILE.** `US-CWP-010` TC-7 is quotable on why:
    # *"Its status and date. ⚠ **Not the amount** — the amount is account
    # data."* So there is no `amount` here, where the receipt above has one.
    # The difference is not inconsistency, it is WHO IS LOOKING: a receipt is
    # read by the person who agreed to that figure ten seconds earlier on the
    # same screen; a reference typed into `CWP-012` may be held by anybody who
    # picked up a scrap of paper.
    #
    # `status` is one of THREE words (`processing` · `cleared` · `failed`) —
    # `payments`' five states with the two ledger words folded away, because
    # `BR-CWP-024` gives progress and never the reason. `reported_at` is the
    # posting date under the name `request_progress_view` already uses for
    # *when we received it*, and `cleared_at` is `BR-PAY-021`'s other half,
    # NULL while a payment is still processing.
    #
    # ⚠ **NO `masked_name`, WHICH `bill_lookup` DOES CARRY.** The mask exists
    # so somebody can CONFIRM they have the right bill before paying
    # (`BR-CWP-020`); a payment reference was handed to one person, so there is
    # nothing left for it to do (`BR-CWP-021`). And no `account_id`: the seam
    # hands one up so the postcode can be walked to, and the view drops it.
    "selectors.py::payment_progress_view": (
        "series",
        "reference",
        "status",
        "reported_at",
        "cleared_at",
    ),
}

#: Names that may never be a key of a guest response, whatever the allow-list
#: says. Belt and braces on purpose: the allow-list is the rule, and this is the
#: check that still bites if somebody widens the allow-list without thinking.
#:
#: ⚠ `masked_name` is deliberately NOT here and `name` is — `BR-CWP-020` allows
#: exactly one masked form and the two must stay different words, so a reviewer
#: reading a response body can tell at a glance which one it is.
NEVER_ON_A_GUEST_RESPONSE: tuple[str, ...] = (
    "customer",
    "customer_id",
    "customer_no",
    "display_name",
    "name",
    "first_name",
    "last_name",
    "full_name",
    "company_name",
    "email",
    "phone",
    "mobile",
    "date_of_birth",
    "dob",
    "ssn",
    "tax_id",
    "account",
    "account_id",
    "account_no",
    "balance",
    "owing",
    "address",
    "address_line",
    "postal_code",
)


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-CWP-010@2c926ba7 (EP-CWP-02 story + BR-CWP-019/020/021/024 verbatim)
# generated: 2026-09-04 by the CR-068 wave E build lane
# checklist: A✔ B✔ C✔ D=n/a(data, read by a gate) E=n/a F✔ G✔ H=n/a
# gates: G92 (reads this file with ast; proved RED by adding `email` to a declared response)
# exceptions: `selectors.py::bill_lookup` is declared with `None` — wave P builds it; the row exists so the allow-list cannot be written by the lane that also writes the leak
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
