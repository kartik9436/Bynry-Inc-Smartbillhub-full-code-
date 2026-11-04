# ── Trace ──────────────────────────────────────────────
# Story:    CR-007 (SET-09 template catalog · SET-10 template detail/preview —
#           the PREVIEW half)   Screens: SET-09 · SET-10
# Rules:    BR-NOT-006 (variants per type × category × language) · BR-BIL-026
#           (an edit is a new version; a render uses the PINNED version) ·
#           BR-NOT-005 (the queue is the only sender; NOTHING here sends) ·
#           BR-TEN-017 (the utility's identity is stamped at render) ·
#           BR-TEN-043 (a business date is an INPUT, never a clock read) ·
#           CLAUDE.md rule 2 (money is Decimal at NUMERIC(18,6), never float)
# Tests:    06-backend/tests/test_cr_007_template_catalog.py
# Impacts:  apps/notifications/templates_api.py (the only caller)
# ───────────────────────────────────────────────────────
"""SET-10's live preview: a real render, from sample data that says it is sample.

CR-007, verbatim: *"Live preview pane showing the actual rendered artifact with
sample data (bill PDF layout, email with subject line, SMS 160-char body, door-
hanger print)"*.

╔══════════════════════════════════════════════════════════════════════════╗
║  THE PREVIEW IS THE REAL RENDERER. IT IS NOT A SECOND ONE.               ║
╚══════════════════════════════════════════════════════════════════════════╝
`rendering.render` does the work — the same function every queued message goes
through, with the same palette validation, the same BR-TEN-017 identity stamp,
the same named-absence handling and the same money and date formatting. A
preview that formatted its own output would be a second renderer, and two
renderers that can disagree WILL: a System Admin would sign off wording that
looks right in the pane and prints differently, which is the one thing a preview
exists to prevent.

So the only thing this module contributes is the CONTEXT, and it contributes it
under one rule.

────────────────────────────────────────────────────────────────────────────
THE SAMPLE CUSTOMER IS A PERSON; THE SAMPLE IDENTIFIERS ARE UNMISTAKABLE
────────────────────────────────────────────────────────────────────────────
⚠ **THIS SECTION SAID THE OPPOSITE UNTIL 2026-09-07 AND THE SUPERSESSION IS
WRITTEN OUT RATHER THAN LEFT TO BE INFERRED.** It read:

    *"a sample that reads like a real utility's real customer is a sample
     somebody screenshots into a ticket"*

and on that basis the preview rendered `Sample Customer` at `1 Sample Street,
Sample City` on account `SAMPLE-ACCOUNT`. **The worry was real and it is now
answered rather than dismissed.** What answers it is `AC-000000` — an account
number of the right SHAPE whose digits are all zero, which no live account can
ever hold, so a screenshot of this pane cannot be mistaken for a customer's
record even by someone who has never seen the product.

What the old wording COST is what moved the ruling. Counted on the running
screens, the word *"sample"* appeared **twelve times on the Past-due reminder,
thirteen on the Payment receipt and twenty-one on Welcome** — and most of those
were the DATA, not the captions, so a screen reading *"Hi Sample, your bill for
1 Sample Street, Sample City is ready"* could not be fixed by tidying captions.
The Product Owner could not read past it. Their ruling, 2026-09-07: the preview
should read *"Hi Pat, your bill for 12 Oak Street is ready… Account AC-000000 …
Total due 123.45 USD by 22 Aug 2026"*.

⚠ **THE OTHER HALF OF THE OLD PARAGRAPH STANDS UNCHANGED.** Prototype r10 draws
this pane with prose for a fictional utility — *"Silver Creek Water"*,
*"Jordan Alvarez"*, *"1408 Elm St"*, *"Required by PUC rule 25.29"*. That demo
data is still NOT reused here: *"Required by PUC rule 25.29"* is a regulatory
claim this platform has no business asserting on any screen, and a made-up
UTILITY name would sit beside the tenant's real one (`{utility_name}` is stamped
from Settings → Company at render, BR-TEN-017) and read as a second company.

⚠ **AND THE RULING NAMED FOUR VALUES, SO FOUR MOVED.** `customer_name`,
`first_name`, `service_address` and `account`/`account_no` are what a rendered
letter puts in front of a reader. Every other `SAMPLE-…` identifier below —
`SAMPLE-BILL`, `SAMPLE-CYCLE`, `SAMPLE-COMMISSION-REF` and the rest — is
deliberately UNCHANGED: they appear in the merge-field rail rather than in the
sentence a person reads, and extending the ruling to them is a decision nobody
has taken. A lane that wants to move them should put the list to the Product
Owner, not infer it from here.

The samples here are shaped like the data, and every response carries
`sample_data: true` with the sentence a screen prints above the pane. A value
this module cannot type correctly is left OUT of the context rather than
guessed, which makes `rendering.render` do exactly what it does in production:
render the named absence `——` and report it, so a System Admin sees which
tokens will be blank if a caller does not supply them.

⚠ **NOTHING HERE SENDS, AND THERE IS NO PATH FROM HERE TO A SEND.** BR-NOT-005:
the dispatcher is the only sender and A11 Addendum r2 §4 makes a synchronous
send endpoint a gate failure. This module returns a string.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any

from apps.notifications import catalogs, rendering

#: The sentence a screen prints above the pane. Served rather than hardcoded in
#: the client for the reason every other ruling in this module is served: a
#: screen that remembered it could stop saying it, and a preview that stops
#: announcing it is a preview is a preview somebody reads as a real document.
#: ⚠ **CR-048 wave I — THE PREVIEW AREA SAID "NOTHING IS SENT" THREE TIMES.**
#: This 269-character paragraph sat a few hundred pixels from the panel hint
#: *"Rendered through the real engine from sample data. Nothing here is sent,
#: queued or charged for."* and from the test-send note, which says it a third
#: time. The pane now announces itself in ONE short line; the full sentence is
#: `SAMPLE_DATA_DETAIL` below and reaches the reader as this line's tooltip, so
#: nothing is lost and the claim is made once.
SAMPLE_DATA_NOTICE = "Preview only — sample data, nothing is sent."

#: The whole of it, on hover. The pane must never STOP saying it is a preview —
#: a preview that stops announcing itself is a preview somebody reads as a real
#: customer's letter — and this is the sentence that says why the layout, the
#: formatting and any missing merge field are nonetheless the real ones.
SAMPLE_DATA_DETAIL = (
    "Rendered from SAMPLE data — no customer, no account and no balance on this page "
    "is real. It uses the same renderer a queued message goes through, so the layout, "
    "the formatting and any missing merge field are the real ones. Nothing is sent by "
    "opening this."
)

#: Tokens whose value is MONEY. Decimal, never float and never a string —
#: `rendering._rendered_value` formats money at the tenant's currency and 2dp
#: and REPORTS a float as a problem (CLAUDE.md rule 2), so typing these wrongly
#: here would show a System Admin a preview that reports a defect in itself.
_MONEY_TOKENS = frozenset(
    {
        "amount",
        "balance",
        "balance_after",
        "balance_before",
        # DEF-NOT-10649 — the post-cut notice's three figures.
        "balance_owed",
        "total_to_restore",
        "charges",
        "closing_balance",
        "current_charges",
        "down",
        "late_fee",
        "opening_balance",
        "payments",
        "prev_balance",
        "rate",
        "reconnect_fee",
        "running_balance",
        "total_due",
    }
)

#: Tokens whose value is a DATE. `rendering.format_date` renders them in the
#: TENANT's Regional format, which is half of what a preview is for: a utility
#: on DD/MM/YYYY needs to see its own format, not this file's.
_DATE_TOKENS = frozenset(
    {
        "bill_date",
        "cut_date",
        "date",
        "due_date",
        "ledger_date",
        "pay_by_date",
        "period_end",
        "period_start",
        # DEF-NOT-10649 — when service came back on.
        "restored_at",
        "today",
    }
)

#: Tokens whose sample value is a specific SHAPE — an identifier, a count, a
#: unit — where a generic string would misrepresent what the field holds. Every
#: value is visibly a sample.
_SHAPED_SAMPLES: dict[str, Any] = {
    "48h": "48 hours",
    # ⚠ ALL ZEROES ON PURPOSE (PO ruling 2026-09-07). The SHAPE is a real
    # account number so a System Admin sees what will print; the VALUE cannot
    # collide with a live account, which is what makes a plausible-looking
    # sample safe. See this module's header for the sentence it supersedes.
    "account": "AC-000000",
    "account_no": "AC-000000",
    "applied_to_bill": "SAMPLE-BILL",
    "authority": "Sample tax authority",
    "bill_no": "SAMPLE-BILL",
    "certified_no": "SAMPLE-CERTIFIED-NO",
    "confirmation": "SAMPLE-CONFIRMATION",
    "current_read": "1,250",
    "customer_name": "Pat Rivera",
    "customer_signature": "(signed electronically)",
    "cycle": "SAMPLE-CYCLE",
    "days_late": "14",
    "demand_kw": "12.5",
    "description": "Sample ledger line",
    # `Pat`, so a greeting reads *"Hi Pat,"* — the PO's own example sentence.
    "first_name": "Pat",
    "missed_count": "2",
    "n": "4",
    "payment_method": "Sample payment method",
    "po_number": "SAMPLE-PO",
    "prior_read": "1,000",
    "processed_by": "Sample Staff",
    "reference": "SAMPLE-REF",
    "service_address": "12 Oak Street",
    "stage_day": "14",
    "state_puc_ref": "SAMPLE-COMMISSION-REF",
    "tax_id": "SAMPLE-TAX-ID",
    "unit": "kgal",
    "unpaid_bills": "2",
    "usage": "250",
}

#: Tokens this module deliberately supplies NO sample for, and why. They are
#: left absent so `rendering.render` does what it does in production: prints the
#: named absence and reports it, which tells a System Admin exactly which fields
#: will be blank if the sending path does not populate them.
#:
#: `{meter_no}` is here because it identifies a physical asset and a plausible
#: fake meter number in a preview is the kind of string that gets copied into a
#: ticket. `{utility_*}` and `{support_*}` are here for a stronger reason: they
#: are stamped AT RENDER from the tenant's own Settings → Company (BR-TEN-017),
#: so overwriting them with a sample would hide the one thing this preview
#: genuinely proves — whether THIS utility has filled its identity in.
#: ── CR-048 wave I · SHORT LINES, AND THE IDENTICAL ONES SAY IT ONCE ────────
#: DEF-2478. These are drawn verbatim under *"Fields the preview deliberately
#: does not sample"*. The four identity entries used to be the SAME sentence
#: repeated four times — *"the utility's own, stamped at render (BR-TEN-017) —
#: never sampled."* — so a template using three of them printed one internal
#: rule id three times, in three consecutive rows, on a water clerk's screen.
#:
#: They are now the same STRING object by construction, which is what lets the
#: screen group the tokens that share a reason and print the reason once. Keep
#: them identical: `SETTINGS_STAMPED` is the grouping key, not a coincidence.
#:
#: THE PROVENANCE, KEPT HERE: BR-TEN-017 stamps the utility's own identity AT
#: RENDER from Settings → Company, so overwriting these with a sample would hide
#: the one thing this preview genuinely proves — whether THIS utility has filled
#: its identity in. BR-NOT-015 is why `rights_footer` expands to the tenant's
#: own live clauses rather than to sample text.
#: ⚠ **THESE ARE ALSO TABLE CELLS, WHICH IS WHY THEY ARE THIS SHORT.** The same
#: dict feeds the preview's "does not sample" list AND the `sample_unavailable`
#: column of the merge-fields table, which is rendered in a **344px rail**.
#: Measured on the deployed v2.83.0, the 67-character version wrapped to three
#: lines and made those rows **143px tall** against 52px for a row with a value
#: — so the four identity tokens were the tallest thing in the panel. A cell
#: holds a VALUE; the list's own heading already says these are deliberately
#: not sampled, so the cell only has to answer *where does it come from*.
SETTINGS_STAMPED = "From Settings → Company"

UNSAMPLED: dict[str, str] = {
    "meter_no": "No invented meter number",
    "utility_logo": SETTINGS_STAMPED,
    "rights_footer": "Your own rights clauses",
    "utility_name": SETTINGS_STAMPED,
    "utility_address": SETTINGS_STAMPED,
    "support_phone": SETTINGS_STAMPED,
    "support_email": SETTINGS_STAMPED,
}


#: `CR-199-BRC10` S7 — the cell beside `{pay_link}` / `{portal_link}` when the
#: server has no `PUBLIC_APP_ORIGIN`: a fact, B14 rule 33.
NO_PUBLIC_ADDRESS = "No public address on this server"


def sample_context(template_code: str) -> dict[str, Any]:
    """A typed sample value for every token of this class that has one.

    Keyed off the class's OWN catalogue, so a preview can never offer a token
    the palette does not allow — the sample set and the whitelist cannot drift
    because one is derived from the other.
    """
    klass = catalogs.catalog_for(template_code)
    if klass is None:
        return {}
    context: dict[str, Any] = {}
    for token in sorted(klass.tokens):
        if token in UNSAMPLED or token in rendering.LINK_SUPPLIED:
            # `{pay_link}` / `{portal_link}` are the utility's REAL portal
            # addresses, supplied by the renderer (CR-199-BRC10 S7) — a preview
            # that sampled them would hide a server with no public address.
            continue
        if catalogs.is_link_token(token):
            # A per-message link (a bill's own address, a sign-in link) has no
            # real value in a preview. `.invalid` is reserved (RFC 2606), so
            # the sample is a working-shaped address that can never resolve.
            context[token] = f"https://example.invalid/{token.replace('_', '-')}"
            continue
        if token in _MONEY_TOKENS:
            context[token] = Decimal("123.45")
        elif token in _DATE_TOKENS:
            # BR-TEN-043 — a fixed sample date, never `date.today()`. A preview
            # that read a clock would render differently every day and a
            # screenshot of it could never be reproduced.
            context[token] = date(2026, 1, 31)
        elif token in _SHAPED_SAMPLES:
            context[token] = _SHAPED_SAMPLES[token]
        else:
            context[token] = f"Sample {token.replace('_', ' ')}"
    return context


def sample_field_rows(template_code: str, *, language: str | None = None) -> list[dict[str, Any]]:
    """Every merge field of this class with its RESOLVED SAMPLE VALUE.

    **The right rail of SET-10 is a two-column panel, not a token list** — the
    PO showed it on 2026-08-17 and it is the difference between a palette and an
    explanation: `{bill_no}` beside `SAMPLE-BILL` tells a System Admin what will
    appear where, and a bare `{bill_no}` does not.

    The value is resolved through **`rendering._rendered_value`, the renderer's
    own formatter** — so money carries the tenant's currency at 2dp and a date
    carries the tenant's Regional format, exactly as the pane below will print
    them. Formatting them here a second time is the drift hard-won law 1 warns
    about, and on money it would also be a second place that could round.

    ⚠ **NOTHING HERE COMPUTES AN AMOUNT.** `Decimal("123.45")` is a constant
    sample and `format_money` only renders it; no rate is read, no total is
    summed, and nothing is stored. A template is WORDING — B4's money math is
    not on this screen and must never be.
    """
    klass = catalogs.catalog_for(template_code)
    if klass is None:
        return []
    formats, _problems = rendering.tenancy_seam.regional_formats()
    currency = formats.get("currency")
    date_format = formats.get("date_format") or rendering.ISO_DATE_FORMAT
    context = sample_context(template_code)

    rows: list[dict[str, Any]] = []
    for token in sorted(klass.tokens):
        if token in context:
            rendered, _problem = rendering._rendered_value(
                token,
                context[token],
                currency=currency,
                date_format=date_format,
                # CR-190-BRC10 — money in the utility's region, as the email.
                locale=rendering.money_locale(formats.get("language"), formats.get("country")),
                number_format=formats.get("number_format"),
            )
            value, unavailable = rendered, None
        else:
            # BR-TEN-017's five identity tokens and `{meter_no}`. The ABSENCE is
            # the useful answer here: the pane shows what the renderer would do,
            # and a made-up value would hide an unfilled company profile.
            value, unavailable = None, UNSAMPLED.get(token, "no sample for this field")
        if token in rendering.LINK_SUPPLIED:
            # CR-199-BRC10 S7 — the renderer's own value: the real address.
            value, unavailable = rendering._link_context({token}).get(token), None
            if value is None:
                unavailable = NO_PUBLIC_ADDRESS
        rows.append(
            {
                # CR-199-BRC10 S7 — the placeholder picker (image 03): the
                # field's name in a person's words and whether it is a LINK,
                # which the editor inserts as a button and tags *link*.
                "label": rendering.token_label(token),
                "kind": "link" if catalogs.is_link_token(token) else "text",
                "token": token,
                # The spelling insert-on-click writes, so the panel and the
                # editor cannot disagree about what a token looks like.
                "insert": f"{{{token}}}",
                "sample_value": value,
                "sample_unavailable": unavailable,
                "derived_spelling": token in klass.derived_spelling,
            }
        )
    return rows


def sample_identity(template_code: str) -> dict[str, Any]:
    """Who the preview strip says it is previewing as.

    The PO's SET-10 header reads *"Previewing as · <kind> · sample data:
    <customer> · <account>"*. Both values come from the SAME sample context the
    pane renders from, so the strip can never name an identity the body does not
    use.
    """
    context = sample_context(template_code)
    return {
        "customer_name": context.get("customer_name") or context.get("first_name"),
        "account_no": context.get("account_no") or context.get("account"),
    }


def preview(
    *,
    template_code: str,
    body: str,
    version: int,
    subject: str | None = None,
    language: str | None = None,
    body_format: str = "plain",
) -> dict[str, Any]:
    """Render `body` with sample data and report everything the render found.

    Raises nothing of its own: a `rendering.RenderRefused` is the caller's to
    translate, because a refusal here is the SAME refusal a save would give and
    the screen must show one message for both — an editor whose preview accepts
    a body its save rejects is an editor that teaches the wrong lesson.

    ⚠ **ONE EXCEPTION, AND IT IS THE DRAWING'S (`CR-199-BRC10`, image 17).** A
    placeholder outside the palette no longer stops the preview: the wording
    renders with `{bogus}` shown as typed, and `errors` carries the same
    finding the save refuses with (`placeholder_unknown`, A2 A). So the editor
    still cannot SAVE what the preview flags; it can simply see the rest of the
    message while it fixes it. Every other refusal still raises.
    """
    from apps.notifications import rich_text

    artifact = rendering.render(
        template_code=template_code,
        template_version=version,
        body=body,
        subject=subject,
        language=language,
        context=sample_context(template_code),
        body_format=body_format,
        lenient=True,
    )
    errors: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    for entry in artifact.findings:
        bucket = warnings if entry.get("severity") == "warning" else errors
        clean = {key: value for key, value in entry.items() if key != "severity"}
        if clean not in bucket:
            bucket.append(clean)
    klass = catalogs.catalog_for(template_code)
    if artifact.channel == "email" and klass is not None:
        # The markup's own errors (raw HTML, an unsafe link target) — the save
        # refuses on exactly these, so the preview names them first.
        for entry in rich_text.check(body, palette=klass.tokens, rich=body_format == "rich").errors:
            if entry not in errors:
                errors.append(entry)
    return {
        "body": artifact.body,
        # CR-199-BRC10 S6 — the email exactly as it is sent: `text` is the
        # plain-text part (links as full addresses) and `html` the whole
        # branded document. A screen draws `html` ONLY inside a sandboxed
        # iframe (`sandbox=""`, `srcdoc`) — it is ours, escaped and script-free,
        # and the sandbox is the second lock. Both None off email.
        "text": artifact.body if artifact.html is not None else None,
        "html": artifact.html,
        "body_format": artifact.body_format,
        "branding": artifact.branding,
        "errors": errors,
        "warnings": warnings,
        # What the Rich → Plain switch can offer: the markup as plain wording,
        # placeholders kept (`[[Pay now|{pay_link}]]` → `Pay now: {pay_link}`).
        "plain_source": rich_text.plain_source(body) if artifact.html is not None else None,
        "subject": artifact.subject,
        "channel": artifact.channel,
        "sample_data": True,
        # CR-048 wave I — the short line the pane draws, and the whole sentence
        # it carries as its tooltip. Both served, for the reason every refusal
        # on this screen is served: a screen that worded either itself would
        # drift from the ruling the moment either changed.
        "sample_data_notice": SAMPLE_DATA_NOTICE,
        "sample_data_detail": SAMPLE_DATA_DETAIL,
        # The renderer's own findings, not a re-derivation. `absences` is the
        # list of palette tokens the context could not fill — which on a
        # preview is the useful half: it names every field that will print
        # `——` unless the sending path supplies it.
        "absences": [dict(entry) for entry in artifact.absences],
        "problems": [dict(entry) for entry in artifact.problems],
        "unsampled": [
            {"token": token, "reason": reason}
            for token, reason in sorted(UNSAMPLED.items())
            if f"{{{token}}}" in body or (subject is not None and f"{{{token}}}" in subject)
        ],
        # SMS is the one channel with a hard length rule on the RENDERED text
        # rather than on the source, so it is measured after substitution.
        "rendered_length": len(artifact.body),
    }


# ── Lifecycle ─────────────────────────────────────────────
# packet: CR-007@set0910 (12-governance/11-change-requests.md CR-007 · 04-docs/01-spec/19-document-templates.md §1/§2/§3 + r8 · 05-prototype/r10-2026-08-16/SMARTBillHub.dc.html SET-09/SET-10 · 04-docs/05-modules/10-notifications/02-business-rules.md BR-NOT-001/002/006/014/015)
# generated: 2026-08-17 by story-coder (CR-007 SET-09/10 templates lane)
# checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-09)
# gates: ruff✔ black✔ · tests/test_cr_007_template_catalog.py — the sample
#         context was proved RED by typing `{balance}` as a str, at which point
#         the money assertion failed on the unformatted value
# exceptions: (1) r10's OWN PREVIEW PROSE IS NOT REUSED. The prototype draws
#         this pane with a fictional utility's letters including regulatory
#         claims ("Required by PUC rule 25.29", "follows TCEQ required
#         language"). That is r10 demo data, not signed template wording, and a
#         platform screen has no business asserting a regulator's rule number.
#         (2) SIX TOKENS ARE DELIBERATELY UNSAMPLED and the response says which
#         and why — the five identity tokens because BR-TEN-017 stamps them from
#         the tenant's own Settings and sampling them would hide an unfilled
#         profile, and `{meter_no}` because a plausible fake asset id belongs in
#         no screenshot.
#         (3) THE SAMPLE DATE IS FIXED (2026-01-31), never `date.today()` —
#         BR-TEN-043, and a preview that read a clock could never be reproduced
#         from a screenshot.
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
