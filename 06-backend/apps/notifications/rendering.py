# ── Trace ──────────────────────────────────────────────
# Story:    US-NOT-005 (the rendering engine — template version + typed merge
#           context → artifact; money 2dp, dates per tenant Regional settings,
#           identity stamped at render, pinned version only) ·
#           US-NOT-016 (custom fields as template variables, rendered from the
#           stamped snapshot)
#           Screens: S8 · S91 · S92 · S94–S106
# Rules:    BR-NOT-012 (custom-field variables resolve ONLY from the stamped
#           snapshot; a missing or deactivated key renders the EMPTY STRING —
#           never None, never a leaked `{{…}}`; values are escaped) ·
#           BR-BIL-026 (every render uses the PINNED template version —
#           generalised to every designer S91+) · BR-TEN-017 (identity values
#           stamped AT RENDER; an issued document is never re-rendered) ·
#           BR-NOT-006 (the pinning tuple includes the LANGUAGE variant) ·
#           BR-CUS-039 (the reconnect fee renders a tenant charge code and is
#           never defaulted) · BR-REP-016 (dunning day numbers render from the
#           tenant's cadence config, never constants) · BR-NOT-005 (the
#           dispatcher renders from the row's pin at dispatch) ·
#           CLAUDE.md rule 2 (money is Decimal + a currency code, never float,
#           rounded only at display) · rule 3 (a consumption figure never
#           renders without its unit)
# Tests:    06-backend/tests/test_us_not_005_rendering.py ·
#           06-backend/tests/test_us_not_016_custom_field_variables.py
# Impacts:  apps/notifications/dispatcher.py (renders each row from its pin
#           before any provider sees it) · the S94–S106 designers' save and
#           test-render, which are NOT in this lane — their US-IDs are named in
#           the docstring and not here, because G10 reads a Trace-header US-ID
#           as "this file ships that story's test cases" even on an Impacts
#           line, and it caught exactly that on this header's first version.
# ───────────────────────────────────────────────────────
"""ONE rendering engine: pinned template version + typed context → artifact.

US-NOT-005 §1: *"`render(template code, pinned version, context)` → artifact —
PDF for printable classes, subject + preheader + HTML body for email, plain text
for SMS — with a typed merge-variable catalog per template type."* The catalog
is `apps/notifications/catalogs.py`; this file is the engine that enforces it.

╔══════════════════════════════════════════════════════════════════════════╗
║  THE VERSION IS AN INPUT, NEVER A LOOKUP. THERE IS NO "LATEST" PATH.     ║
╚══════════════════════════════════════════════════════════════════════════╝

BR-BIL-026, generalised to every designer S91+ by A19 addendum b: a render uses
the version PINNED on the document, the queue row or the signed contract, and
publishing affects only future renders. US-NOT-005 TC-6 states the consequence
as a negative — *"Render requested 'on latest version' for an issued document →
No such path exists"* — so this engine takes `version` as a required argument
and contains no code that reads a published-version pointer. There is nothing to
disable and no flag to get wrong: the caller must hold the pin, which means the
caller must have read the row.

WHAT IT CAN AND CANNOT RENDER TODAY, STATED RATHER THAN IMPLIED
---------------------------------------------------------------
⚠ AMENDED 2026-08-15 by the notifications CONTENT lane. This paragraph used to
read *"`notification_templates` and its version rows are US-NOT-006 and are not
built … `render_for_dispatch` therefore REFUSES every queue row"*. **The store
now exists** (`template_service.py`, migrations 0005/0006), so
`render_for_dispatch` loads the body of the version PINNED on the row and
renders it. `render()` itself is unchanged and still takes the body as an
argument, because the designers' save and test-render paths hold a draft that
is not stored yet.

What still refuses: a row with NO pin (there is no "latest" path — BR-BIL-026,
US-NOT-005 TC-6) and a pin naming a version that cannot be loaded. Both are the
ratified hold of field map N-1: *"dispatch holds safely on missing published
template; content never invented."*

⚠ **AMENDED 2026-08-18 — `CLASSES_WITHOUT_CATALOG` IS NOW EMPTY.** This
paragraph read *"Seventeen template classes additionally have NO CATALOG in any
signed spec (the six A19 r8 email bodies, four SMS bodies, three contract types,
three plan notices — OQ-206 and OQ-207)"*. Fourteen of those got palettes on
2026-08-17 (*"please define it for this product"*) and the last three — the
service agreement, the deposit agreement and the ACH authorization — on
2026-08-18 (CR-011 item 9, *"already answer - provide default and allow user to
change"*). **The refusal path is NOT deleted**: `_class_or_refuse` still quotes
`CLASSES_WITHOUT_CATALOG` by name, because the next class a ruling has not
reached must land in exactly that hole rather than in a new one.

**What refuses instead, and it is the same posture one step later:** a body that
still carries `PLACEHOLDER_MARK` cannot be RENDERED (`refuse_if_placeholder`).
Exactly one class ships one — the NACHA autopay authorization, whose wording is
a payment scheme's and not ours — and that refusal is a deliberate feature of
the PO's own ruling rather than an absence waiting to be filled.

THE FOUR RULES THIS ENGINE ENFORCES, AND WHY EACH IS HERE AND NOT IN A CALLER
-----------------------------------------------------------------------------
1. **A body may use only its class's tokens** (US-NOT-005 TC-5, Acceptance 3).
   Enforced server-side so it holds for an API caller and an import, not only
   for somebody typing in the designer. ⚠ The RULE ROW for this is marked
   **PROPOSED** in US-NOT-005 §2 (*"derived from A19 addendum 'variable palette'
   + A19 typed token lists"*) while TC-5 and the Acceptance criterion state the
   behaviour as ratified. The behaviour is implemented and the rule's status is
   named here rather than quietly upgraded — if a PO ruling ever softens it to a
   warning, this is the paragraph to come back to.
2. **Money renders at 2dp with its currency** (A19 header, CLAUDE.md rule 2).
   Through `core.money.finalize`, the frozen half-up rule, at the one place B4
   permits rounding besides finalization: display. Nothing is written back.
3. **Dates render in the tenant's Regional format** (A19 header) — never
   hardcoded, which is US-NOT-005 TC-3 (*"Tenant Regional format = DD/MM/YYYY →
   same template renders 18/08/2026"*).
4. **A consumption figure never renders alone** (CLAUDE.md rule 3). A body
   using `{usage}` must also use `{unit}`; `684` on a bill is not checkable by
   the customer who receives it and `684 kWh` is. A19 §1.4 writes them as a pair
   for the same reason.

CUSTOM FIELDS ARE A SECOND GRAMMAR, ON PURPOSE (US-NOT-016, BR-NOT-012)
------------------------------------------------------------------------
A tenant's own fields render as `{{account.custom.service_class}}` — double
braces, dotted path — and are resolved from the document's STAMPED SNAPSHOT
(`context["custom_snapshot"]`), never from live master data. Two reasons, and
both are rules rather than taste:

* **Reprint reproducibility.** BR-NOT-012 / TC-2: the account's value is edited
  to "Irrigation" after issue and the reprint still reads "Commercial". A live
  lookup would rewrite history every time somebody corrected a typo.
* **A tenant's field name can never shadow a signed A19 token.** `{balance}` is
  the platform's word; `{{account.custom.balance}}` is the tenant's. One
  grammar for both would let a custom field named `balance` replace the figure
  on a bill.

Custom variables are NOT in any class catalog and are not validated against one
— they are a per-tenant registry, not a signed vocabulary — so `validate_body`
ignores them and `tokens_in` strips them before it scans. A missing key renders
the EMPTY STRING (not `——`): a catalogued token the platform promised and could
not produce is an absence worth naming, while an optional tenant field the
account simply does not carry is not.

A MISSING VALUE IS A NAMED ABSENCE, NEVER A LEAKED `{token}`
------------------------------------------------------------
A token that is in the catalog and has no value in the context renders as
`——` and is recorded in `absences`. It never renders as the literal `{token}`,
as `None`, or as an empty space nobody can account for. That follows OQ-117's
closure (PO 2026-08-12, *"issue and report it"*): a document with a NAMED
absence goes out, because the customer needs the rest of it, and the absence is
counted where somebody can act on it. `apps/billing/documents.py` prints the
same mark for the same reason.

WHAT THIS FILE DOES NOT DO
--------------------------
* **It does not produce a PDF.** OQ-149 closed 2026-08-12 with *"our platform
  will provide standard 3 to 5 variations of printed bill"* and no page-render
  library was added to the image; `apps/billing/documents.py` holds the one
  standard-library page that exists, for bills. Printable classes here render
  their TEXT body; turning a notice into a paginated page is not this slice.
* **It does not decide which version is pinned.** That is resolution
  (US-NOT-006: account override → category default → published version) and it
  is not built.
* **It does not store anything.** No document table exists; the artifact is
  returned to the caller.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, datetime
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from typing import Any

from apps.notifications import catalogs, models, rights_footer, tenancy_seam
from core import money as core_money

try:  # CR-190-BRC10 — CLDR locale data for money (a declared dependency).
    import babel as _babel
    from babel import numbers as _babel_numbers
except ImportError:  # pragma: no cover - pyproject.toml declares it
    _babel = None
    _babel_numbers = None

#: A19 writes every merge variable as `{token}`. `{48h}` is one of them, so the
#: grammar admits a leading digit — a renderer that rejected a signed token's
#: own spelling would refuse the body the spec describes.
TOKEN_RE = re.compile(r"\{([A-Za-z0-9_]+)\}")

#: What a catalogued token with no value renders as. The same mark
#: `apps/billing/documents.py` prints, so one absence looks the same on a bill
#: and on the notice that chases it.
ABSENT_MARK = "——"

#: ⚠ ADDED 2026-09-07 · `DEF-PAY-4409` — THE TOKENS A CALLER NEVER HAS TO PASS.
#: `render` merges these UNDER the caller's context from the tenant's own
#: Settings → Company (BR-TEN-017) and `rights_footer.expand` replaces
#: `{rights_footer}` before the token pass runs, so none of the six is ever a
#: caller's omission. Named HERE, in the module that does the supplying, because
#: the guard that reports what a caller forgot
#: (`services._context_gap`) has to subtract exactly this set and a second
#: hand-kept copy of it would report the utility's own phone number as a
#: caller's mistake the first time the two drifted.
#:
#: ⚠ **`{utility_logo}` IS DELIBERATELY NOT HERE.** No palette offers it and the
#: context supplies no value for it, so it prints `——` on a customer's letter —
#: that is DEF-195 and it is a real gap, not a supplied value. Listing it would
#: hide the one thing the guard exists to find.
#:
#: ⚠ **AND IT IS DERIVED FROM THE FUNCTION THAT DOES THE MERGING RATHER THAN
#: TYPED OUT BESIDE IT.** A second hand-kept list is a list that goes stale the
#: first time somebody adds a token to `_identity_context` — the exact failure
#: `SignupWizard.tsx`'s hand-typed service list is (hard-won law 2) and the exact
#: failure this guard exists to catch, one layer up. Add a key there and this
#: set grows on its own.


def _identity_context(identity: dict[str, Any]) -> dict[str, Any]:
    """The utility's own values, stamped AT RENDER (BR-TEN-017).

    Merged UNDER the caller's context, never over it: a caller holding a
    snapshotted masthead (a reprint of an issued document) must win over today's
    Settings, which is the whole point of *"issued documents are never
    re-rendered"*.
    """
    return {
        "utility_name": identity.get("dba_name") or identity.get("legal_name"),
        "utility_address": identity.get("mailing_address"),
        "support_phone": identity.get("support_phone"),
        "support_email": identity.get("support_email"),
        # ⚠ ADDED 2026-08-17 WITH THE AUTHORED BODIES (DEF-210), AND THE REASON
        # IS DEF-195: a palette that offers a token the context cannot fill puts
        # `——` on a customer's letter. `{utility_website}` is `tenants.website`,
        # a value the tenant already enters on Settings → Company, and eleven of
        # the authored bodies want to say "pay online at …". `or None` rather
        # than the raw value on purpose — an EMPTY website must render the named
        # absence like every other missing figure, not a silent blank that reads
        # as "pay online at ." on a printed page.
        "utility_website": identity.get("website") or None,
    }


def _link_context(used: set[str]) -> dict[str, Any]:
    """`CR-199-BRC10` S7 — `{pay_link}` and `{portal_link}`, the portal's real
    addresses, built by `tenancy_seam` from `PUBLIC_APP_ORIGIN` (never a
    hand-built host). Read only when the wording uses them; None when the
    server has no public address, which prints the link's label alone."""
    values: dict[str, Any] = {}
    if "pay_link" in used:
        values["pay_link"] = tenancy_seam.portal_pay_link()
    if "portal_link" in used:
        values["portal_link"] = tenancy_seam.portal_home_link()
    return values


#: The two links above — named beside the identity tokens so a caller's
#: omission guard (`services._context_gap`) subtracts them too.
LINK_SUPPLIED = frozenset({"pay_link", "portal_link"})

RENDERER_SUPPLIED = (
    frozenset(_identity_context({})) | frozenset({"rights_footer"}) | LINK_SUPPLIED
)

#: ── CR-048 wave I · WHAT A CLERK IS TOLD WHEN A FIELD WILL PRINT BLANK ─────
#: DEF-2478. The `detail` on a `merge_value_absent` record is drawn verbatim on
#: Settings → Configure → Templates, under *"N merge field(s) will print as an
#: absence"*. It used to read:
#:
#:     "{support_phone} is in the 'email_account_closed' palette and the render
#:      context carries no value for it, so the document shows a named absence
#:      rather than a blank or a literal brace. OQ-117's closure: a document
#:      with a NAMED absence goes out; the customer needs the rest of it."
#:
#: The PO's question on the deployed v2.83.0 was simply *"why this text"*. It
#: names a palette, a render context, a literal brace and an open question, and
#: it never tells the reader the two things they can act on: WHICH FIELD will be
#: blank, and WHERE THEY FIX IT.
#:
#: ⚠ **THE RECORD ALREADY CARRIED `br_ref`**, so DEF-335's pattern — sentence
#: for the clerk, provenance on a machine field — was applied to this record and
#: then a different id was written into the prose anyway. Half a rule.
#:
#: THE PROVENANCE, KEPT: OQ-117 closed with *a document carrying a NAMED absence
#: still goes out, because the customer needs the rest of it* — which is why the
#: renderer prints `ABSENT_MARK` instead of refusing, and why this record is a
#: WARNING rather than an error. `br_ref` carries BR-BIL-026 for support.
#:
#: The tokens a tenant fills in themselves, on Settings → Company (BR-TEN-017).
#: A blank one of these is a SETTINGS GAP the reader can close in a minute, so
#: the sentence names the screen. Everything else is a figure this document
#: simply has no value for, which is a different fact with a different fix.
IDENTITY_TOKENS = frozenset(
    {
        "utility_name",
        "utility_address",
        "utility_logo",
        "utility_website",
        "support_phone",
        "support_email",
    }
)


def token_label(token: str) -> str:
    """`support_phone` → `Support phone`. The field's name in a person's words.

    Deliberately derived from the token rather than held in a second table: a
    hand-kept label map is a list that goes stale the first time a palette gains
    a token, and a missing entry there would print a raw identifier on a
    customer-facing screen — the very fault this helper exists to end.
    """
    return token.replace("_", " ").capitalize()


def absence_detail(token: str) -> str:
    """The one sentence a clerk reads about a field that will print blank."""
    if token in IDENTITY_TOKENS:
        return f"{token_label(token)} will print blank — add it under Settings → Company."
    return f"{token_label(token)} will print blank — this document has no value for it."


#: US-NOT-016's CUSTOM-FIELD variable — a DIFFERENT grammar from A19's, on
#: purpose. `{{account.custom.service_class}}`: double braces, dotted path,
#: because a tenant's own field names must never be able to collide with a
#: signed A19 token. `{balance}` is the platform's word; `{{account.custom.
#: balance}}` is the tenant's, and one grammar for both would let a tenant
#: shadow the figure on their own bill.
CUSTOM_TOKEN_RE = re.compile(r"\{\{\s*([a-z_]+)\.custom\.([a-z][a-z0-9_]{1,39})\s*\}\}")

#: BR-NOT-012 / US-NOT-016 TC-3: a missing or deactivated key renders the EMPTY
#: STRING — *"never `None`, never `undefined`, and never a leaked `{{…}}`: a
#: customer-facing document must not show a template artifact."*
#:
#: ⚠ THIS IS DELIBERATELY NOT `ABSENT_MARK`, and the difference is a ruling.
#: A catalogued A19 token with no value renders `——` because the platform
#: PROMISED that figure and could not produce it (OQ-117: a named absence goes
#: out). A custom field is the TENANT's own optional column: an account that
#: simply has no "service class" is normal, and printing `——` beside a label
#: would tell the customer something was missing when nothing is.
CUSTOM_ABSENT = ""

#: The seven Regional date formats a tenant can hold (`apps.tenancy.services`
#: `DATE_FORMATS`). Repeated here rather than imported because B1 forbids
#: reaching into another module's internals and these are its wire values, not
#: its implementation — the same call `apps/billing/delivery_seam.py` makes for
#: the queue's `source_type` vocabulary. An unknown format renders ISO and says
#: so rather than guessing an order.
ISO_DATE_FORMAT = "YYYY-MM-DD"


#: ⚠ THE STORED-RENDER-CONTEXT CODEC (2026-08-17, CR-009 in-app lane).
#:
#: `outbound_messages.render_context` is a JSON column and `_rendered_value`
#: formats BY TYPE — a `Decimal` is money, a `date` is a date, everything else is
#: text. JSON has neither type, so a context that made the round trip untagged
#: would arrive as a string and a due date would print `2026-08-25` on a tenant
#: whose Regional format is `DD/MM/YYYY`. Worse for money: `Decimal("12.30")`
#: would come back as the float `12.3` and hit the float refusal, or print with
#: the wrong precision.
#:
#: So the two types that MATTER are tagged on the way in and restored on the way
#: out. Deliberately only two: a codec that tried to be general would be a
#: serialization framework living in a renderer.
_CTX_DATE = "__date__"
_CTX_DATETIME = "__datetime__"
_CTX_MONEY = "__money__"
_CTX_MONEY_WITH_CURRENCY = "__money_ccy__"


def encode_context(context: dict[str, Any] | None) -> dict[str, Any] | None:
    """A render context → JSON that survives the round trip with its types.

    Called by `services.queue_document` when a writer stamps facts on a queue
    row. A float is REFUSED here rather than at render: CLAUDE.md rule 2 says
    money is never a float, and catching it at the write means the bad value
    never reaches the database instead of failing one dispatch cycle at a time.
    """
    if not context:
        return None
    encoded: dict[str, Any] = {}
    for key, value in context.items():
        if isinstance(value, Money):
            encoded[key] = {
                _CTX_MONEY_WITH_CURRENCY: {"amount": str(value.amount), "currency": value.currency}
            }
        elif isinstance(value, Decimal):
            encoded[key] = {_CTX_MONEY: str(value)}
        elif isinstance(value, datetime):
            encoded[key] = {_CTX_DATETIME: value.isoformat()}
        elif isinstance(value, date):
            encoded[key] = {_CTX_DATE: value.isoformat()}
        elif isinstance(value, float):
            raise RenderRefused(
                f"the stored render context for {{{key}}} carries a float ({value!r}). "
                "CLAUDE.md rule 2: money is Decimal and never float. Refused at the WRITE "
                "so the bad value never reaches the queue, rather than at every dispatch "
                "attempt afterwards."
            )
        else:
            encoded[key] = value
    return encoded


def decode_context(stored: Any) -> dict[str, Any]:
    """JSON from a queue row → the typed context `render` expects.

    An unrecognised shape passes through untouched: this codec restores what it
    tagged and never guesses at what it did not.
    """
    if not isinstance(stored, dict):
        return {}
    decoded: dict[str, Any] = {}
    for key, value in stored.items():
        if isinstance(value, dict) and len(value) == 1:
            if _CTX_MONEY in value:
                decoded[key] = Decimal(str(value[_CTX_MONEY]))
                continue
            if _CTX_MONEY_WITH_CURRENCY in value and isinstance(
                value[_CTX_MONEY_WITH_CURRENCY], dict
            ):
                inner = value[_CTX_MONEY_WITH_CURRENCY]
                decoded[key] = Money(Decimal(str(inner.get("amount"))), inner.get("currency"))
                continue
            if _CTX_DATETIME in value:
                decoded[key] = datetime.fromisoformat(str(value[_CTX_DATETIME]))
                continue
            if _CTX_DATE in value:
                decoded[key] = date.fromisoformat(str(value[_CTX_DATE]))
                continue
        decoded[key] = value
    return decoded


@dataclass(frozen=True)
class Money:
    """A money figure WITH its currency — `CR-190-BRC10` ruled 2: *"Callers pass
    money as a value plus currency, never a pre-formatted string."* A bare
    `Decimal` still renders in the tenant's currency; this carries its own."""

    amount: Decimal
    currency: str | None = None


_PARAGRAPH_BREAK = re.compile(r"(\n[ \t]*\n+)")


def drop_optional_paragraphs(
    body: str, optional: frozenset[str] | set[str], values: dict[str, Any]
) -> str:
    """Leave out each blank-line-delimited paragraph that carries an optional
    token with no value. Every other paragraph, and every separator between
    the paragraphs kept, is untouched byte for byte."""
    if not optional or not body:
        return body
    missing = {token for token in optional if values.get(token) is None}
    if not missing:
        return body
    pieces = _PARAGRAPH_BREAK.split(body)
    kept: list[str] = []
    for index in range(0, len(pieces), 2):
        paragraph = pieces[index]
        if missing & set(TOKEN_RE.findall(paragraph)):
            continue
        if kept:
            kept.append(pieces[index - 1] if index > 0 else "\n\n")
        kept.append(paragraph)
    return "".join(kept)


class RenderRefused(Exception):
    """This artifact cannot be produced, and here is why — in a clerk's words.

    Deliberately NOT one of the `core.errors` catalog exceptions: those carry an
    HTTP status because they answer a request, and rendering happens inside a
    dispatch cycle over thousands of rows where the right handling is to record
    the break and carry on (BR-BIL-055's shape). The designers' save path
    (US-NOT-007/008) will translate it for a screen.
    """


@dataclass(frozen=True)
class RenderedArtifact:
    """One rendered message, and everything that was wrong with it.

    `absences` and `problems` travel WITH the artifact for the reason
    `apps/billing/documents.py` states: a caller must not have to infer a gap,
    and a reviewer must not have to take a docstring's word for it (hard-won
    law 1). A document that went out missing its support phone number is a fact
    somebody needs, and it is on the artifact rather than in a log.
    """

    template_code: str
    template_version: int
    language: str | None
    channel: str
    body: str
    subject: str | None = None
    absences: tuple[dict[str, Any], ...] = ()
    problems: tuple[dict[str, Any], ...] = ()
    #: The identity values stamped into this render (BR-TEN-017). Carried so a
    #: reprint can be compared against the original rather than trusted.
    identity: dict[str, Any] | None = None
    #: `CR-199-BRC10` S4/S6 — EMAIL only: the whole branded HTML document
    #: (`email_layout.wrap`). `body` is then the plain-text alternative, with
    #: every link printed as its full address. None on every other channel.
    html: str | None = None
    body_format: str = "plain"
    #: `CR-199-BRC10` — the markup check's findings (`rich_text.check`), for
    #: the preview: `[{code, message_key, params, severity}]`.
    findings: tuple[dict[str, Any], ...] = ()
    #: The frame's facts (colours, logo, logo link) for the preview line.
    branding: dict[str, Any] | None = None


class PlaceholderUnknown(RenderRefused):
    """`A2 A` (PO 2026-10-29): a placeholder outside the allowed list blocks
    saving. A subclass, so every caller that already catches `RenderRefused`
    still does; the API reads `.tokens` to name the first one on screen."""

    def __init__(self, sentence: str, tokens: list[str]) -> None:
        super().__init__(sentence)
        self.tokens = tokens


class MarkupRefused(RenderRefused):
    """`CR-199-BRC10` S4 — raw HTML, or a link to anywhere but `https://` or a
    link placeholder. Carries the finding the screen renders."""

    def __init__(self, sentence: str, finding: dict[str, Any]) -> None:
        super().__init__(sentence)
        self.finding = finding


def tokens_in(text: str) -> tuple[str, ...]:
    """Every `{token}` the text uses, in first-appearance order.

    CUSTOM-FIELD variables (`{{entity.custom.key}}`) are deliberately NOT
    returned: they are not catalogued and must not be validated against a
    palette — see `custom_tokens_in` and the module docstring's US-NOT-016
    section. The double-brace form is stripped before this scan so its inner
    text can never be mistaken for an A19 token.
    """
    seen: list[str] = []
    for match in TOKEN_RE.finditer(CUSTOM_TOKEN_RE.sub("", text or "")):
        name = match.group(1)
        if name not in seen:
            seen.append(name)
    return tuple(seen)


def custom_tokens_in(text: str) -> tuple[tuple[str, str], ...]:
    """Every `{{entity.custom.key}}` the text uses, as `(entity, key)` pairs."""
    seen: list[tuple[str, str]] = []
    for match in CUSTOM_TOKEN_RE.finditer(text or ""):
        pair = (match.group(1), match.group(2))
        if pair not in seen:
            seen.append(pair)
    return tuple(seen)


def _escape(value: str) -> str:
    """BR-NOT-012: tenant-authored values are escaped on render, HTML and PDF
    alike (US-NOT-016 TC-5: `<script>alert(1)</script>` must not be executable
    in either output).

    `html.escape` with `quote=True`, so an attribute context is covered too. The
    printable classes render TEXT today (no page-render library — OQ-149), and
    escaping there costs nothing while the day the PDF path lands it is already
    right — the alternative is a security fix that has to be remembered later.
    """
    from html import escape

    return escape(value, quote=True)


def render_custom_fields(
    text: str, snapshot: dict[str, Any] | None, *, escape: bool = True
) -> str:
    """Resolve `{{entity.custom.key}}` against a STAMPED SNAPSHOT (US-NOT-016).

    BR-NOT-012, verbatim: *"Custom-field variables resolve ONLY from
    `invoices.custom_snapshot` (or the notification's own stored render context
    for non-invoice notices)."* Never from live master data — that is what makes
    TC-2 true: master data edited to "Irrigation" after issue, and the REPRINT
    still reads "Commercial".

    A missing, deactivated or cross-namespace key renders the EMPTY STRING
    (TC-3, TC-6, TC-8) — never `None`, never a leaked `{{…}}`, never an
    exception, and the rest of the document is unaffected. Values are escaped
    (TC-5).

    Snapshot keys are `"<entity>.<key>"` — the shape `apps/billing/
    custom_snapshot.py` writes and B2 r17.3 stores — so an `account` token can
    never reach a `premises` value: the namespace is part of the lookup, not a
    filter applied afterwards (TC-6).

    ⚠ THE DEFAULT-VALUE HALF OF OQ-075'S CLOSURE IS NOT IMPLEMENTED HERE, and it
    is named rather than silently skipped. The PO closed OQ-075 on 2026-08-10
    with *"warn, do not block — and the field may carry a DEFAULT VALUE …  new
    documents render the field's DEFAULT rather than an empty variable."* That
    default lives on the tenancy `custom_field` definition row, and a
    definition read here would be exactly the LIVE master-data lookup BR-NOT-012
    forbids — the reprint would change when somebody edited the default. The
    correct home is the SNAPSHOT WRITER (`apps/billing/custom_snapshot.py`,
    billing's, which this lane may not edit): a field's default belongs in the
    snapshot at issue, where it is frozen like every other value. REPORTED.
    """
    values = snapshot or {}

    def substitute(match: re.Match[str]) -> str:
        entity, key = match.group(1), match.group(2)
        value = values.get(f"{entity}.{key}")
        if value is None:
            return CUSTOM_ABSENT
        # `escape=False` is the EMAIL path's (CR-199-BRC10): it substitutes
        # inside the parsed markup and escapes the HTML itself, once.
        return _escape(str(value)) if escape else str(value)

    return CUSTOM_TOKEN_RE.sub(substitute, text or "")


def _class_or_refuse(template_code: str) -> catalogs.TemplateClass:
    """The class's catalog, or the refusal that names precisely which gap it is."""
    catalog = catalogs.catalog_for(template_code)
    if catalog is not None:
        return catalog
    unspecified = catalogs.CLASSES_WITHOUT_CATALOG.get(template_code)
    if unspecified is not None:
        raise RenderRefused(
            f"{template_code!r} is a ratified template class with NO merge-variable "
            f"catalog in any signed spec, so nothing here can validate or render it. "
            f"{unspecified} Rendering it anyway would mean inventing the variable "
            "vocabulary of a customer-facing document — field map N-1's posture is the "
            "ratified one: dispatch holds, content is never invented."
        )
    raise RenderRefused(
        f"{template_code!r} is not a template class this platform knows. The known set is "
        f"{', '.join(catalogs.known_template_codes())} (A19 r8's sixteen + BR-NOT-004's "
        "four contracts + BR-NOT-007's three plan notices). A row pinned to an unknown "
        "class is a row nothing will ever render."
    )


def validate_body(
    template_code: str,
    body: str,
    *,
    subject: str | None = None,
    allow_unknown: bool = False,
) -> None:
    """The designer's save-time and test-render-time gate (US-NOT-005 TC-5).

    Refuses:
      * a token outside the class's catalog — the palette IS the catalog
        (A19 addendum r8; the rule row is PROPOSED, see the module docstring);
      * a class whose mandatory content is missing — A19 rule 1's *"nothing is
        due"* on the statement, the regulatory footer marker on the regulated
        disconnect class (US-NOT-007 TC-6);
      * `{usage}` without `{unit}` — CLAUDE.md rule 3, made structural.

    Raises rather than returning a list, because every one of these is a body a
    human must fix before it can be saved: a receipt carrying `{meter_no}` has
    no correct rendering to fall back to.
    """
    catalog = _class_or_refuse(template_code)
    used = set(tokens_in(body)) | set(tokens_in(subject or ""))

    unknown = sorted(used - catalog.tokens)
    # `allow_unknown` is the PREVIEW's: image 17 renders the wording with
    # `{bogus}` shown as typed beside the error. A save never passes it.
    if unknown and not allow_unknown:
        raise PlaceholderUnknown(
            f"{', '.join('{' + name + '}' for name in unknown)} "
            f"{'is' if len(unknown) == 1 else 'are'} not in the {template_code!r} "
            f"catalog. Its palette is: {', '.join(sorted(catalog.tokens))} "
            f"({catalog.source}). The palette IS the catalog (A19 addendum r8) — a token "
            "outside it has no value to merge, so it would reach the customer as an empty "
            "space or as a literal brace, and neither is something they can act on.",
            unknown,
        )

    for phrase in catalog.mandatory_content:
        if phrase.lower() not in (body or "").lower():
            # ⚠ THE CLASS'S OWN REASON WHEN IT HAS ONE (CR-011 item 9). Until
            # 2026-08-18 this refusal explained A19 rule 1 and US-NOT-007 TC-6
            # to every class with mandatory content, so a person who deleted
            # `{schedule_table}` from a payment-plan agreement was told about a
            # statement that must say "nothing is due" — a true sentence about a
            # different document. `mandatory_content_reason` is quoted when the
            # class carries one; the two originals are the fallback, because
            # they are still the reason for the classes that have no reason of
            # their own.
            why = catalog.mandatory_content_reason or (
                "A19 rule 1 requires the statement classes to say nothing is due *'or "
                "customers pay twice'*, and US-NOT-007 TC-6 makes the regulatory footer "
                "non-removable from the regulated disconnect notice."
            )
            raise RenderRefused(
                f"the {template_code!r} class must carry {phrase!r} and this body does "
                f"not. It is mandatory class content, not a default: {why}"
            )

    if "usage" in used and "unit" in catalog.tokens and "unit" not in used:
        raise RenderRefused(
            "this body renders {usage} without {unit}. CLAUDE.md rule 3: a consumption "
            "figure always carries its unit — '684' is not checkable by the customer who "
            "receives it and '684 kWh' is. A19 §1.4 writes the pair together for the same "
            "reason."
        )


def validate_for_save(
    template_code: str,
    body: str,
    *,
    subject: str | None = None,
    body_format: str = "plain",
) -> list[dict[str, Any]]:
    """The SAVE gate: `validate_body`, plus — on an EMAIL class — the closed
    markup's own rules (`rich_text.check`): no raw HTML, a link or button only
    to `https://` or a link placeholder (`CR-199-BRC10` S4).

    Deliberately NOT part of `render`: a body already stored keeps rendering
    (its raw HTML is removed, never sent) rather than failing a dispatch that
    no clerk is watching. Returns the WARNINGS, which never block a save.
    """
    from apps.notifications import rich_text  # local: rich_text imports catalogs only

    catalog = _class_or_refuse(template_code)
    if body_format not in ("plain", "rich"):
        raise RenderRefused(f"{body_format!r} is not an email format; it is plain or rich.")
    if body_format == "rich" and catalog.channel != models.CHANNEL_EMAIL:
        raise RenderRefused(
            f"{template_code!r} is not an email, so it has no rich format; only email "
            "wording carries bold, links, buttons and lists."
        )
    validate_body(template_code, body, subject=subject)
    if catalog.channel != models.CHANNEL_EMAIL:
        return []
    found = rich_text.check(body, palette=catalog.tokens, rich=body_format == "rich")
    if found.errors:
        first = found.errors[0]
        raise MarkupRefused(
            f"the wording breaks the email markup rule {first['code']!r} "
            f"({first['params']}). Only bold, links, buttons and lists are allowed, and "
            "a link goes to an https:// address or a link placeholder.",
            first,
        )
    return found.warnings


#: ⚠ **THE ONE BODY IN THIS PRODUCT THAT IS BUILT TO BE REFUSED** — PO ruling
#: 2026-08-18 (CR-011 item 9), verbatim: *"Do it; put the details, I will handle
#: it with user"*.
#:
#: The autopay (ACH) authorization's wording is prescribed by the NACHA
#: Operating Rules, a scheme this repository does not hold. Every other class in
#: this product ships a default a utility edits; this one ships a PLACEHOLDER,
#: because it is the single document here where a plausible wrong answer creates
#: real liability rather than an awkward sentence. **The refusal is the
#: feature**: the placeholder can be saved, versioned, read and edited like any
#: other body — and it cannot be RENDERED, so it can never reach a customer for
#: signature while it is still ours.
#:
#: A marker rather than a class list, deliberately: a utility that pastes half
#: their bank's wording over half of ours still holds a document with the marker
#: in it, and that document is still refused. The utility clears the refusal by
#: deleting the marker line, which is one visible act they can see themselves
#: doing.
PLACEHOLDER_MARK = "[[PLACEHOLDER — NOT VALID UNTIL YOUR UTILITY REPLACES THIS TEXT]]"


def refuse_if_placeholder(template_code: str, body: str) -> None:
    """Refuse to RENDER a body that is still the platform's placeholder.

    Deliberately NOT part of `validate_body`: saving, versioning and publishing
    a placeholder are all legitimate — that is how a utility keeps the text in
    front of themselves while their bank answers — and the line it must never
    cross is the one where a customer is asked to sign it.
    """
    if PLACEHOLDER_MARK not in (body or ""):
        return
    required = catalogs.required_from_utility(template_code)
    detail = "\n".join(f"  {index}. {item}" for index, item in enumerate(required, start=1))
    raise RenderRefused(
        f"{template_code!r} still carries the platform PLACEHOLDER and cannot be "
        "rendered. This is the one document in SMART360 Next with no default wording, and "
        "that is on purpose: the wording of an authorization for recurring ACH debits is "
        "prescribed by the NACHA Operating Rules, which this platform does not hold. A "
        "default written by inference would look official and could be wrong.\n"
        "Replace the placeholder with the wording your own bank and counsel give you. "
        "What that wording has to settle:\n" + detail + "\n"
        "Delete the marker line to clear this refusal."
    )


#: The two number formats a tenant can hold (`apps.tenancy.services
#: .NUMBER_FORMATS`), as (decimal mark, group mark). Wire values restated rather
#: than imported, for the reason `format_date`'s seven formats are (B1).
_NUMBER_MARKS = {"1,234.56": (".", ","), "1.234,56": (",", ".")}


def money_locale(language: str | None, country: str | None) -> str | None:
    """The CLDR locale an amount is written in: the message's LANGUAGE in the
    utility's COUNTRY (Settings → Regional). `CR-190-BRC10`, PO 2026-10-22.

    `en` + `United States` → `en_US`; `fr-FR` + `Canada` → `fr_CA`. The country is
    stored as its English name, and is matched against CLDR's own territory
    names — the standard data, never a table typed here — or taken as a
    two-letter code. A pair CLDR does not know falls back to the language alone,
    then to None (the caller then prints the figure with its code).
    """
    if _babel is None:  # pragma: no cover - babel is a declared dependency
        return None
    lang = (language or "").replace("-", "_").split("_")[0].strip().lower()
    if not lang or lang == "default":
        lang = ""
    territory = None
    name = (country or "").strip()
    if name:
        if len(name) == 2 and name.isalpha():
            territory = name.upper()
        else:
            territories = _babel.Locale("en").territories
            wanted = name.casefold()
            territory = next(
                (code for code, label in territories.items() if label.casefold() == wanted),
                None,
            )
    for candidate in (
        f"{lang}_{territory}" if lang and territory else None,
        lang or None,
        f"en_{territory}" if territory else None,
    ):
        if not candidate:
            continue
        try:
            _babel.Locale.parse(candidate)
        except (ValueError, _babel.UnknownLocaleError):
            continue
        return candidate
    return None


def format_money(
    value: Any,
    currency: str | None,
    *,
    locale: str | None = None,
    number_format: str | None = None,
) -> str:
    """A money figure at 2dp, written the way the utility's region writes it.

    ⚠ **AMENDED 2026-10-22 — `CR-190-BRC10`, PO verbatim:** *"Option A — '$45.00':
    the symbol comes from the utility's currency and region settings (so a
    Canadian utility shows CA$ or $, a euro utility €). Nothing is hardcoded.
    Applies to every email."* It printed `45.00 USD` (the code after) until then.

    The symbol and where it goes come from CLDR through `babel` — the standard
    locale data, not a table in this file: `USD` in `en_US` is `$45.00`, `CAD` in
    `en_CA` is `$45.00` and in `en_US` is `CA$45.00`, `EUR` in `fr_FR` is
    `45,00 €`. Where the tenant's own number format (Settings → Regional)
    disagrees with the locale's marks, the tenant's marks win — the utility chose
    them. Always TWO places (`currency_digits=False`): the ruling says 2dp.

    `core.money.finalize` is the frozen half-up-to-2dp rule (B4 ❄), applied first
    and unchanged; babel only writes the already-rounded figure. Nothing rounded
    here is written back — the stored value keeps its four decimals.

    A missing currency, or no locale babel can place, renders the figure with the
    code after (or bare) and the caller NAMES the gap — never a typed `$`.
    """
    try:
        amount = value if isinstance(value, Decimal) else Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError) as bad:
        raise RenderRefused(
            f"a figure on this document ({value!r}) is not a number, so it cannot be "
            "rendered as money. Nothing here substitutes a zero: a notice that prints "
            "0.00 for a balance it could not read is worse than one that refuses."
        ) from bad
    rounded = core_money.finalize(amount)
    if currency and locale and _babel is not None:
        try:
            text = _babel_numbers.format_currency(
                rounded, currency, locale=locale, currency_digits=False
            )
        except (ValueError, _babel.UnknownLocaleError):
            text = None
        if text is not None:
            return _apply_marks(text, locale, number_format)
    plain = format(rounded, "f")
    return f"{plain} {currency}" if currency else plain


def _apply_marks(text: str, locale: str, number_format: str | None) -> str:
    """Swap the locale's decimal/group marks for the tenant's, where they differ."""
    marks = _NUMBER_MARKS.get(number_format or "")
    if marks is None:
        return text
    loc_decimal = _babel_numbers.get_decimal_symbol(locale)
    loc_group = _babel_numbers.get_group_symbol(locale)
    want_decimal, want_group = marks
    if (loc_decimal, loc_group) == (want_decimal, want_group):
        return text
    swap = {loc_decimal: "\x00", loc_group: "\x01"}
    out = "".join(swap.get(ch, ch) for ch in text)
    return out.replace("\x00", want_decimal).replace("\x01", want_group)


def format_unit_price(
    value: Any,
    currency: str | None,
    *,
    locale: str | None = None,
    number_format: str | None = None,
) -> str:
    """A UNIT price — a rate, a tier price — with as many places as it carries,
    up to 4 (CLAUDE.md hard rule 2, PO 2026-10-02: *"Show unit prices with up to
    4 decimals and keep every total at 2."*), and never fewer than 2.

    `$0.0425`, `$8.9375`, `$0.10`. Display only: nothing is rounded beyond the
    four places the value is stored at, and nothing is written back.
    """
    amount = value if isinstance(value, Decimal) else Decimal(str(value))
    quantised = amount.quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)
    places = 4
    while places > 2 and quantised == quantised.quantize(Decimal(1).scaleb(-(places - 1))):
        places -= 1
    if currency and locale and _babel is not None:
        try:
            pattern = _babel.Locale.parse(locale).currency_formats["standard"].pattern
            pattern = pattern.split(";")[0]
            # The locale's own pattern, widened to `places` decimals.
            widened = pattern.replace(
                "." + "0" * 2, "." + "0" * places, 1
            ) if "." in pattern else pattern
            text = _babel_numbers.format_currency(
                quantised, currency, format=widened, locale=locale, currency_digits=False
            )
            return _apply_marks(text, locale, number_format)
        except (ValueError, KeyError, _babel.UnknownLocaleError):
            pass
    plain = format(quantised.quantize(Decimal(1).scaleb(-places)), "f")
    return f"{plain} {currency}" if currency else plain


def format_date(value: date | datetime, date_format: str | None) -> str:
    """A date in the tenant's Regional format (A19 header, US-NOT-005 TC-3).

    The seven formats are `apps.tenancy.services.DATE_FORMATS`. An unknown or
    unset format renders ISO-8601 — unambiguous in every locale — rather than
    guessing an order, because `03/04/2026` read the wrong way round is wrong
    in a way nobody can see.

    `DD-MMM-YY` renders an ENGLISH month abbreviation. The frontend's `DateCell`
    localises it through `Intl`; there is no equivalent on the server, so the
    limitation is named by the caller (`month_name_not_localized`) rather than
    silently shipped as correct. A document in Spanish reading `25-Aug-26` is a
    real defect for a real customer and it is recorded as one.
    """
    day = value.date() if isinstance(value, datetime) else value
    y, m, d = f"{day.year:04d}", f"{day.month:02d}", f"{day.day:02d}"
    if date_format == "MM/DD/YYYY":
        return f"{m}/{d}/{y}"
    if date_format == "DD/MM/YYYY":
        return f"{d}/{m}/{y}"
    if date_format == "DD.MM.YYYY":
        return f"{d}.{m}.{y}"
    if date_format == "DD-MM-YYYY":
        return f"{d}-{m}-{y}"
    if date_format == "YYYY/MM/DD":
        return f"{y}/{m}/{d}"
    if date_format == "DD-MMM-YY":
        month = "Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec".split()[
            day.month - 1
        ]  # noqa: SIM905
        return f"{d}-{month}-{y[-2:]}"
    return f"{y}-{m}-{d}"


def _rendered_value(
    name: str,
    value: Any,
    *,
    currency: str | None,
    date_format: str | None,
    locale: str | None = None,
    number_format: str | None = None,
) -> tuple[str, dict[str, Any] | None]:
    """One context value → the string that goes on the document, plus a problem.

    Formatting is TYPE-driven and not name-driven: a `Decimal` is money, a
    `date` is a date, everything else is text. Deciding by token NAME would mean
    keeping a second list of which tokens are money — and the day somebody added
    `{deposit_amount}` to a catalog and forgot the other list, a figure would
    print with six decimal places on a customer's bill.
    """
    if value is None:
        return ABSENT_MARK, None
    if isinstance(value, Money):
        # CR-190-BRC10 — a figure that carries its OWN currency is written in it.
        return (
            format_money(
                value.amount,
                value.currency or currency,
                locale=locale,
                number_format=number_format,
            ),
            None,
        )
    if isinstance(value, Decimal):
        return format_money(value, currency, locale=locale, number_format=number_format), None
    if isinstance(value, (date, datetime)):
        rendered = format_date(value, date_format)
        if date_format == "DD-MMM-YY":
            return rendered, {
                "code": "month_name_not_localized",
                "br_ref": "BR-SHL-041",
                "token": name,
                "detail": "the tenant's date format carries a month NAME and this "
                "renderer has no localized month names, so it printed the English "
                "abbreviation. The frontend localizes the same format through Intl; the "
                "server does not, and a document in another language reading '25-Aug-26' "
                "is a real defect rather than an acceptable approximation.",
            }
        return rendered, None
    if isinstance(value, float):
        raise RenderRefused(
            f"the value for {{{name}}} arrived as a float ({value!r}). CLAUDE.md rule 2: "
            "money is Decimal and never float, and a float that reaches a document has "
            "already lost the precision that made it correct. Pass a Decimal."
        )
    return str(value), None


def render(
    *,
    template_code: str,
    template_version: int,
    body: str,
    context: dict[str, Any],
    subject: str | None = None,
    language: str | None = None,
    body_format: str = "plain",
    lenient: bool = False,
) -> RenderedArtifact:
    """Render ONE message from a PINNED version and a typed context.

    `CR-199-BRC10`: an EMAIL renders through `rich_text` (the closed markup)
    into a plain-text `body` AND a branded HTML document (`html`,
    `email_layout.wrap`); `body_format` decides whether the HTML carries the
    bold, links, buttons and lists or only the plain words. `lenient` is the
    PREVIEW's: a placeholder outside the palette is shown as typed and reported
    in `findings` instead of refusing (image 17). Dispatch never passes it.

    `template_version` is REQUIRED and is never looked up. There is no "latest"
    path in this module (BR-BIL-026, US-NOT-005 TC-6) — a caller that does not
    hold the pin has not read the row it is rendering.

    The tenant's formats and identity are read at render (BR-TEN-017): dates in
    the tenant's Regional format, money at 2dp with the tenant's currency, and
    the utility's own name, address and support details stamped into the
    artifact. An issued document is never re-rendered, which is what keeps a
    later identity edit off a bill that already went out.

    Returns the artifact WITH its absences and problems. Raises `RenderRefused`
    only for what a human must fix: an unknown or uncatalogued class, a token
    outside the palette, missing mandatory content, a float where money belongs.
    """
    validate_body(template_code, body, subject=subject, allow_unknown=lenient)
    refuse_if_placeholder(template_code, body)
    catalog = _class_or_refuse(template_code)
    is_email = catalog.channel == models.CHANNEL_EMAIL

    formats, format_problems = tenancy_seam.regional_formats()
    identity, identity_problems = tenancy_seam.company_identity()
    currency = formats.get("currency")
    date_format = formats.get("date_format") or ISO_DATE_FORMAT
    # CR-190-BRC10 — money is written in the MESSAGE's language and the utility's
    # country (Settings → Regional), from CLDR. A `default` variant has no
    # language of its own, so the utility's language stands in.
    message_language = language if language and language != "default" else None
    locale = money_locale(message_language or formats.get("language"), formats.get("country"))
    number_format = formats.get("number_format")

    # BR-TEN-017 — the utility's own values are stamped AT RENDER, by
    # `_identity_context` near the top of this module (which is also what
    # `RENDERER_SUPPLIED` is derived from, so the guard that reports a caller's
    # omissions and the code that fills them in cannot drift apart).
    used_tokens = set(tokens_in(body)) | set(tokens_in(subject or ""))
    merged: dict[str, Any] = {
        **_identity_context(identity),
        # CR-199-BRC10 S7 — under the caller's context, like identity.
        **_link_context(used_tokens & catalog.tokens),
        **{key: value for key, value in context.items() if value is not None},
    }

    absences: list[dict[str, Any]] = []
    problems: list[dict[str, Any]] = [*format_problems, *identity_problems]
    findings: list[dict[str, Any]] = []

    def substitute(match: re.Match[str]) -> str:
        name = match.group(1)
        if lenient and name not in catalog.tokens:
            # The preview's half of A2 A: shown as typed, never filled.
            from apps.notifications import rich_text

            entry = {**rich_text.finding(rich_text.ERR_UNKNOWN_PLACEHOLDER, token=name)}
            entry["severity"] = "error"
            if entry not in findings:
                findings.append(entry)
            return match.group(0)
        value = merged.get(name)
        if value is None:
            absences.append(
                {
                    "code": "merge_value_absent",
                    # A MACHINE field — the screen puts it on `data-br-ref`,
                    # where support reaches it and a clerk never does. The
                    # sentence beside it carries no id, by DEF-2478.
                    "br_ref": "BR-BIL-026 · OQ-117",
                    "token": name,
                    "detail": absence_detail(name),
                }
            )
            return ABSENT_MARK
        rendered, problem = _rendered_value(
            name,
            value,
            currency=currency,
            date_format=date_format,
            locale=locale,
            number_format=number_format,
        )
        if problem is not None:
            problems.append(problem)
        return rendered

    # US-NOT-016 — custom fields FIRST, and from the SNAPSHOT only. Doing it
    # first means a resolved custom value can never be re-scanned as an A19
    # token: a tenant whose field value happened to contain `{balance}` would
    # otherwise have it merged, which is a tenant-authored string reaching into
    # the platform's own vocabulary.
    snapshot = context.get("custom_snapshot")
    snapshot = snapshot if isinstance(snapshot, dict) else None
    if not is_email:
        body = render_custom_fields(body, snapshot)
    if subject:
        subject = render_custom_fields(subject, snapshot, escape=not is_email)

    # BR-NOT-015 — the disconnection notice's rights footer, expanded from THIS
    # tenant's five clauses (CR-007, PO 2026-08-17). A no-op on every class that
    # does not carry `{rights_footer}`, which is every class but BR-NOT-014's
    # three tiers.
    #
    # ⚠ THE ORDER OF THESE THREE LINES IS LOAD-BEARING AND EACH POSITION IS A
    # DECISION. It runs AFTER custom fields, so a tenant's clause override cannot
    # reach into `{{account.custom.…}}` — that is tenant-authored data resolved
    # from a stamped snapshot, and platform prose reaching into it is the same
    # crossing the custom-field pass is ordered first to prevent, in the other
    # direction. It runs BEFORE the token pass, because `re.sub` inserts a
    # replacement literally and never re-scans it: a footer merged in during that
    # pass would print `{support_phone}` on a customer's letter as characters.
    body = rights_footer.expand(body)

    # CR-190-BRC10 — a paragraph built around an OPTIONAL token with no value is
    # left out whole (`catalogs.TemplateClass.optional`), before the token pass,
    # so it neither prints `——` nor counts as an absence.
    body = drop_optional_paragraphs(body, catalog.optional, merged)

    rendered_subject = TOKEN_RE.sub(substitute, subject) if subject else None

    if not is_email:
        return RenderedArtifact(
            template_code=template_code,
            template_version=int(template_version),
            language=language,
            channel=catalog.channel,
            body=TOKEN_RE.sub(substitute, body),
            subject=rendered_subject,
            absences=tuple(absences),
            problems=tuple(problems),
            identity=identity or None,
            findings=tuple(findings),
        )

    # ── CR-199-BRC10 · THE EMAIL PATH ────────────────────────────────────
    # The body is PARSED first and every value is substituted inside the
    # parsed pieces, so no customer value can become markup (T2). Custom
    # fields first within each piece, for the reason the non-email path runs
    # them first: a resolved custom value is never re-scanned as an A19 token.
    from apps.notifications import email_layout, rich_text

    rich = body_format == "rich"
    for entry in rich_text.check(body, palette=catalog.tokens, rich=rich).warnings:
        findings.append({**entry, "severity": "warning"})

    def resolve_text(segment: str) -> str:
        return TOKEN_RE.sub(substitute, render_custom_fields(segment, snapshot, escape=False))

    def resolve_link(target: str) -> str | None:
        token = TOKEN_RE.fullmatch(target)
        if token is None:
            # A typed address: `https://` only, else the label stands alone.
            return target if rich_text.safe_https(target) else None
        if token.group(1) not in catalog.tokens or not catalogs.is_link_token(token.group(1)):
            return None
        value = substitute(token)
        return value if rich_text.safe_resolved_link(value) else None

    stamped = identity or {}
    logo_url = tenancy_seam.logo_image_url(stamped)
    band_hex, ink_hex = email_layout.band_colours(stamped.get("brand_primary_hex"))
    rendered = rich_text.render(
        body,
        resolve_text=resolve_text,
        resolve_link=resolve_link,
        rich=rich,
        brand_hex=band_hex,
        ink_hex=ink_hex,
    )
    document = email_layout.wrap(
        subject=rendered_subject or "",
        body_html=rendered.html,
        identity=stamped,
        logo_url=logo_url,
        language=message_language or formats.get("language"),
    )
    return RenderedArtifact(
        template_code=template_code,
        template_version=int(template_version),
        language=language,
        channel=catalog.channel,
        body=rendered.text,
        subject=rendered_subject,
        absences=tuple(absences),
        problems=tuple(problems),
        identity=identity or None,
        html=document,
        body_format="rich" if rich else "plain",
        findings=tuple(findings),
        branding=email_layout.branding(stamped, logo_url),
    )


def render_for_dispatch(
    row: models.OutboundMessage, *, context: dict[str, Any] | None = None
) -> RenderedArtifact:
    """Render ONE queue row from the version PINNED on it — or refuse, loudly.

    ⚠ AMENDED 2026-08-15 (notifications CONTENT lane). This function used to
    refuse EVERY row, and the refusal was correct at the time: the store did not
    exist. `apps/notifications/template_service.py` and migration 0005 are that
    store, so a row carrying a real pin now renders. The refusal remains for the
    two cases that are still true, and both are stated rather than implied:

      * **The row carries NO pin.** There is no "latest" path in this module
        (BR-BIL-026, US-NOT-005 TC-6): the pin is stamped at QUEUE time by
        `services.queue_document`, which resolves it once through
        `template_service.resolve`. A row with no pin is a row queued before a
        published template existed, and rendering it against today's published
        version would be exactly the re-render BR-BIL-026 forbids.
      * **The pinned version cannot be loaded** — an unknown template id, a
        version that is not there. Reported, never approximated with the
        nearest match.

    Refusing is the ratified hold, not a placeholder: field map N-1 — *"dispatch
    holds safely on missing published template; content never invented."* The row
    stays `queued`, the dispatcher records the refusal, nothing reaches a
    provider. The alternative is a blank letter posted to a customer.

    ⚠ **AMENDED 2026-10-22 (`DEF-BIL-10530`, PO: *"mark them failed"*).** *"The
    row stays `queued`"* is now true only on print and the portal. On email,
    text and in-app the dispatcher marks the row `failed` with
    `template_not_resolved` and its try counted: a pin is frozen at queue time,
    so a version that cannot be loaded today never will be, and holding it was
    a silent loop. Nothing is invented either way — no body is sent.

    ⚠ THE MERGE CONTEXT IS STILL EMPTY ON THIS DEPLOYMENT UNLESS A CALLER
    SUPPLIES ONE. The queue row holds the recipient snapshot and the pin; it
    does NOT hold the balance, the due date or the cut date, because no signed
    document puts a rendered merge context on the queue row and inventing one
    would mean this module deciding what a bill says. So a dispatch-time render
    produces the template's text with its catalogued tokens marked as NAMED
    ABSENCES (`——`, counted in `absences`) rather than fabricated values.
    `apps/notifications/notices.py` renders WITH a context at generation time,
    which is where the facts actually are. REPORTED.
    """
    from apps.notifications import template_service  # local: avoids an import cycle

    if row.template_id is None or row.template_version is None:
        raise RenderRefused(
            f"queue row {row.pk} carries no pinned template version "
            f"(code={row.template_code!r}, id={row.template_id}, "
            f"version={row.template_version}). There is no path in this module that renders "
            "'the latest published version' instead — BR-BIL-026 pins at queue time and "
            "US-NOT-005 TC-6 states the consequence as a negative. Dispatch HOLDS: the row "
            "keeps its place and nothing is sent (field map N-1). A row reaches this state "
            "when it was queued while its template had no published version; re-queueing it "
            "after publishing one will not help either, because the pin is stamped at "
            "queue-write — the document must be queued again."
        )
    try:
        pinned = template_service.load_pinned(
            template_id=row.template_id, version=row.template_version
        )
    except template_service.TemplateRefused as missing:
        raise RenderRefused(
            f"queue row {row.pk} is pinned to template {row.template_id} "
            f"v{row.template_version} and that version could not be loaded: {missing} "
            "Dispatch HOLDS rather than rendering the nearest available body."
        ) from missing

    # ⚠ THE ROW'S OWN STORED CONTEXT, ADDED 2026-08-17 (CR-009 in-app lane).
    # The docstring above says the merge context is empty *"unless a caller
    # supplies one"*; `outbound_messages.render_context` is how a caller supplies
    # one when there is no other caller left — the dispatcher, which holds only
    # the row. BR-NOT-012 names that store: *"the notification's own stored
    # render context for non-invoice notices"*.
    #
    # The EXPLICIT argument still wins, and the order matters: a caller that has
    # the facts in hand (notice generation) is more current than a snapshot, and
    # a NULL column leaves today's behaviour — named absences — untouched. So
    # nothing that rendered before this line existed renders differently now.
    stored = decode_context(row.render_context)
    merged_context = {**stored, **dict(context or {})}
    return render(
        template_code=pinned.code,
        template_version=pinned.version,
        body=pinned.body,
        context=merged_context,
        subject=pinned.subject,
        language=row.template_language or pinned.language,
        # CR-199-BRC10 — the PINNED version's own layout, frozen with its body.
        body_format=pinned.body_format,
    )


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-NOT-005@5e8c33f (sha1[:7] of the four sources this slice was authored from, concatenated in order: 04-docs/01-spec/19-document-templates.md — §1/§2/§3 + the 2026-08-07 r8 revision + the three 2026-08-08 addenda — · 04-docs/01-spec/13-copy-and-microcopy.md · 04-docs/05-modules/10-notifications/06-epics/EP-NOT-02-templates-rendering.md · 10-notifications/03-field-map.md §2)
# generated: 2026-08-15 by story-coder (W3 notifications delivery-core lane — the rendering slice)
# checklist: A✔ B✔ C✔ D=deferred(no-API-half — the designers' save/test-render endpoints are US-NOT-007/008) E=deferred(no-frontend-half — S94–S106 are US-NOT-007/008) F✔ G✔ H=deferred(PO 2026-08-09)
# gates: ruff✔ black✔ · pytest tests/test_us_not_005_rendering.py 17 passed ·
#         two guards proved RED before being trusted green (hard-won law 7):
#         · the out-of-catalog refusal — `meter_no` ADDED to the receipt catalog
#           ⇒ `Failed: DID NOT RAISE RenderRefused` on US-NOT-005 TC-5
#         · the float refusal — isinstance check removed ⇒ same failure, and the
#           MEASURED render was `247.3` (one decimal, no currency) rather than
#           the `247.30` this trailer first guessed: a float does not reach the
#           money path at all, it reaches `str()`. Corrected here rather than
#           left as a plausible sentence.
#         The pinned-version-only claim has NOTHING to break — this module reads
#         no published-version pointer — so its test asserts the SIGNATURE
#         instead, and that limitation is stated rather than dressed up as a
#         proof. Verbatim transcripts in the lane report
# amended:   2026-08-15 by story-coder (notifications CONTENT lane) —
#         `render_for_dispatch` no longer refuses every row. Exception (1) below
#         said the store was the next story; it is now `template_service.py` +
#         migrations 0005/0006, and this function loads the PINNED version's
#         body from it. `render()` is untouched. What still refuses is a row with
#         no pin (no "latest" path exists) and a pin that cannot be loaded. A
#         `context` argument was added so a caller with the facts (notice
#         generation) can supply them; a dispatch-time render with no context
#         produces NAMED ABSENCES rather than fabricated figures, and says so.
# exceptions: (1) `render()`'S BODY IS AN ARGUMENT, NOT A LOOKUP — deliberately,
#         because the designers' save and test-render paths hold a DRAFT that is
#         not stored yet (BR-BIL-027's Clerk right). `render_for_dispatch` is the
#         stored-body path and takes the pin.
#         (1b) A DISPATCH-TIME RENDER HAS NO MERGE CONTEXT. The queue row carries
#         the recipient snapshot and the pin and no figures; no signed document
#         puts a merge context on the row, and inventing one would make this
#         module decide what a bill says. Catalogued tokens render as named
#         absences. REPORTED.
#         (2) NO PDF. OQ-149 closed 2026-08-12 (*"standard 3 to 5 variations of
#         printed bill"*) and no page-rendering library is in the image;
#         `apps/billing/documents.py` holds the one standard-library page there
#         is, for bills. Printable classes render their TEXT body here.
#         (3) THE TOKEN-CATALOG RULE ROW IS **PROPOSED** in US-NOT-005 §2 while
#         TC-5 and Acceptance 3 state the behaviour as ratified. The behaviour is
#         implemented and the status is named in the docstring rather than
#         quietly upgraded — REPORTED.
#         (4) `DD-MMM-YY` RENDERS AN ENGLISH MONTH NAME. The frontend localises
#         the same format through `Intl`; the server has no equivalent, so every
#         render in that format carries a `month_name_not_localized` problem
#         rather than shipping a Spanish document that reads `25-Aug-26` as if it
#         were right. REPORTED.
#         (5) THE SEVEN DATE FORMATS ARE RE-STATED HERE rather than imported from
#         `apps.tenancy.services` (B1: no module reaches into another's
#         internals). They are wire values, not implementation — the same call
#         `apps/billing/delivery_seam.py` makes for the queue's source_type
#         vocabulary. An unknown format renders ISO and never guesses an order.
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
