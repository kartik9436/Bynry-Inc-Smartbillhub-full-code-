# ── Trace ──────────────────────────────────────────────
# Story:    US-BIL-028 (stamp the custom-field snapshot onto the invoice)
#           Screens: S30 · S31 (not displayed in R2)
# Rules:    BR-BIL-030 (the bill is LOCKED — a document instance is stamped and
#           a reprint renders it forever, joining nothing live) · BR-TEN-048
#           (a custom field can NEVER influence money) · BR-TEN-050 (deactivate
#           excludes from new snapshots; stored values survive) · BR-TEN-053
#           (the registry read) · CLAUDE.md rule 1 (tenant scoping) · rule 4
#           (financial immutability)
# Tests:    06-backend/tests/test_us_bil_028_custom_snapshot.py
# Impacts:  apps/billing/stages/assemble_document.py (its only caller) ·
#           apps/tenancy/selectors.document_safe_custom_fields ·
#           apps/customers/selectors.custom_data_for_account ·
#           apps/metering/selectors.custom_data_for_location ·
#           10-scripts/gates/g06_forbidden.py (this path is the DB-17 allowlist)
# ───────────────────────────────────────────────────────
"""The ONE module DB-17 lets touch tenant-defined data inside a money path.

HUMAN-OWNED · HUMAN-REVIEW-PENDING — this file IS the DB-17 allowlist: it is the
single path G6 permits to read tenant-defined `custom_data` inside billing, and
its `dict[str, str]` return type is what makes BR-TEN-048 ("a custom field can
NEVER influence money") structural rather than aspirational. It also enforces
tenant scoping (CLAUDE.md rule 1) and writes onto an append-only, immutable
column (rule 4), where a wrong value can never be corrected. AI-authored
2026-08-11 under the PO ruling of 2026-08-09; row in
12-governance/09-human-review-ledger.md.

MARKER ADDED 2026-08-11 by the gate lane, and what that does and does not mean.
The review-ledger row for this file already recorded the claim — *"it is the
DB-17 allowlist — a security boundary"* — and listed six pending decisions, while
the docstring carried neither marker, so nothing machine-readable said this file
was under the PO's 2026-08-09 protocol. The marker was added after reading the
code against CLAUDE.md's 🔒 list, not on the strength of a lane report. That lane
did NOT itself edit `10-scripts/gates/human_owned.txt` — editing it is a process
event, its own header says so — and REPORTED the glob for the daily PO batch
instead of self-granting it.

✔ **THAT GLOB HAS SINCE LANDED AND G7 NOW GUARDS THIS FILE**
(`human_owned.txt`: *"The DB-17 allowlist itself — decides which tenant fields
may reach a customer's bill (rule 1), and writes an append-only column"*).
⚠ **THIS PARAGRAPH PREVIOUSLY ENDED *"Until that line lands, G7 still does not
look at this file"* AND WAS TRUE WHEN WRITTEN**; it is corrected rather than
left standing, because a docstring describing the absence of a guard the repo
has since gained is hard-won law 1 pointing the other way — the same correction
`apps/billing/documents.py` carries for the same reason.

WHY THIS FILE IS ALLOWED TO EXIST, AND WHY IT IS THE ONLY ONE
-------------------------------------------------------------
BR-TEN-048 (CONFIRMED, PO 2026-08-10 — *"we may not able to use it for
calculation"*) bans `custom_data` under `apps/rating/` absolutely and under
`apps/billing/`, `apps/ledger/` and `apps/payments/`. That ban is the
load-bearing constraint that lets tenant-defined fields exist at all without
reopening the finance-signed B4/B5 math. US-BIL-028 is billing code that must
read those values, so DB-17 resolves the contradiction with ONE allowlisted
module — this one — whose only job is to COPY values into a stamp. It returns
`dict[str, str]` and there is no typed accessor anywhere that returns a number
from it. G6 enforces the allowlist; a reviewer's attention does not.

WHY IT IS BUILT IN R2 WHEN NOTHING READS ITS OUTPUT UNTIL R3
------------------------------------------------------------
B12 r7.2, verbatim, and it is the whole reason this lane exists: *"You cannot
retroactively reconstruct what an account looked like six months ago. If R2
issues real invoices with no snapshot column, every invoice from that period is
permanently unable to render custom fields — and the tempting repair is a live
join to master data, which rewrites issued documents without ever running an
UPDATE. Stamp early, render later."* The template variables that read the stamp
are US-NOT-016, in R3. Every day R2 bills without this is a day of invoices
that can never render a custom field truthfully.

The live-join failure mode deserves naming precisely, because it is subtle and
it passes every immutability check: reading a custom field at RENDER time would
show last January's bill using this March's data, satisfying the letter of DB-4
(no UPDATE was issued) while breaking it in substance. The schema already makes
this same move twice — DB-8 stamps `gl_account_id` onto `invoice_lines`, DB-9
pins `template_id` + version onto `invoices` — for exactly this reason.

WHEN IT STAMPS: AT DRAFT, WITH THE REST OF THE PAYLOAD — AND WHY
----------------------------------------------------------------
B2 r17.3 and US-BIL-028 §2 both say "at issue". This lane stamps at DRAFT
instead, from `stages/assemble_document.py`, alongside `bill_payload`, and the
deviation is deliberate and REPORTED rather than quiet:

  * BR-BIL-030 as it stands in `07-billing/02-business-rules.md` — the CANONICAL
    rules file, CONFIRMED by the PO on 2026-08-10 — is one rule covering the
    whole locked document instance, and it names `custom_snapshot` inside it.
    Stage 6 already assembles that instance at draft time under the PO's ruling
    of 2026-08-11 (*"you have to keep lock data for that bill and save the
    instance"*), for the reason its own docstring gives: assembling at issue
    would re-join whatever the customer record says by then, and a name changed
    between the run and the release would print on a bill for a period billed
    under the old one.
  * Stamping the custom half one stage later would give ONE document two
    different "as of" moments — Sarah's old name beside her new custom values.
    A document that is internally inconsistent about when it was true is worse
    than one that is simply late.
  * The one-way door the ruling exists to close is RENDER-time joining, not the
    draft/issue boundary. Both timings close it; only one of them agrees with
    the column next door.

Immutability is unaffected: `custom_snapshot` is frozen by the same trigger
that freezes the money (billing migration 0009 re-emits
`billing_invoice_immutable()` naming this column), and a re-run REPLACES its
draft (BR-BIL-023) rather than editing an issued row.

ALL SIX DATA TYPES NOW STAMP — AND THE FORMAT IS BORROWED, NOT OWNED
---------------------------------------------------------------------
⚠ **THIS SECTION PREVIOUSLY SAID FOUR OF THE SIX TYPES WERE STUBBED ON OQ-125
AND WAS TRUE WHEN WRITTEN.** Until 2026-08-12 `number`, `date`, `boolean` and
`multi_select` each raised a `NotImplementedError` stub naming that question:
BR-BIL-030 asked for a *display-format at stamp time using the tenant's
Regional settings*, there was
no server-side IS-8 formatter in this codebase, and the prime directive forbade
a lane choosing `"Yes"` over `"true"` on a string that lands in an append-only
row. **That refusal is gone.** The PO closed OQ-125 that day, verbatim: *"in
remark or note section on bill - applicationd eicde the format for time
being"*, and the eight custom-field areas do not each get a designed place on
the bill — ONE remark/note section carries them.

**Read the grant precisely, because the next reader will otherwise take it for
settled design.** What the PO decided is that the application MAY choose; what
the PO did NOT do is choose. The four formats below are this application's
defaults standing in for a design nobody has made:

  * `number` → the figure as typed, **no thousands grouping**, no forced
    decimals (`10432` → `"10432"`, `1.5` → `"1.5"`).
  * `date` → **ISO 8601** `YYYY-MM-DD`, deliberately not `date_format` —
    which still has no renderer, and of the candidates only ISO cannot be
    misread as a different day once it is frozen.
  * `boolean` → `"Yes"` / `"No"`, **in English**, on a bill that may be
    Spanish. This is the weakest part of the grant and it is named rather than
    hidden.
  * `multi_select` → the tenant's own option strings joined by `", "`, in the
    tenant's stored order.

`APPLICATION_FORMAT_GRANT_IS_TEMPORARY` is where the code carries the *"for the
time being"* half, and each constant carries its own reason. **The day a tenant
needs control of any of this, it is a NEW question for the PO** — not a lane's
edit, and not something a later reader may cite as a format the PO designed.

A value that CONTRADICTS its declared type is still refused rather than
coerced: the grant covers rendering, never invention (`_wrong_type`).

WHAT IS STILL DELIBERATELY NOT DONE HERE
-----------------------------------------
* **Five of the eight entities are not reached.** `accounts`, `units` and
  `premises` are single-valued along the invoice's own path (invoice → account
  → unit → premises) and are stamped. `contacts`, `addresses`,
  `service_agreements`, `service_points` and `assets` can each have several
  rows per account, and the snapshot's key space is FLAT (`<entity>.<key>`,
  r17.3) with nothing ruled about how two contacts share one key. Inventing
  `contacts.0.phone_note` would invent the read contract that R3's template
  variables are written against. OQ-118 was CLOSED by the same 2026-08-12
  ruling — *one remark/note section carries them* — which settles WHERE custom
  fields print and does not settle how a flat key space holds two contacts, so
  the three-entity scope is unchanged here and the key-grammar half is
  REPORTED rather than chosen. It does not raise: stamping only the
  single-valued three is a lawful reading, and refusing a bill would presume a
  ruling nobody made.
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from importlib import import_module
from typing import Any

from apps.billing.exceptions import BillingConfigError, BillingRuleError
from core import errors
from core import tenancy as core_tenancy

#: The entities this stamp reaches in R2, in the order they are written into
#: the snapshot. Single-valued along the invoice's own path, which is what
#: makes the flat `<entity>.<key>` key space of r17.3 well-defined for them.
STAMPED_ENTITIES = ("accounts", "units", "premises")

#: The three entities r17.2 covers that are NOT reached, plus the two commercial
#: multi-row ones — named as data so the gap is greppable rather than prose.
#: OQ-118.
UNREACHED_ENTITIES = (
    "contacts",
    "addresses",
    "service_agreements",
    "service_points",
    "assets",
)

#: Data types whose stored value IS already the display string. `text` is the
#: tenant's own prose; `select` is one of the tenant's own `options` strings.
#: Nothing is formatted, so nothing is decided.
STRING_DATA_TYPES = ("text", "select")

#: Data types the APPLICATION renders, under the PO's grant of 2026-08-12
#: closing OQ-125. These four used to raise a stub
#: (`NotImplementedError`) naming that question, because no rendering had been
#: ruled; the rendering below is now shipped and the four constants under this
#: one ARE the format the PO delegated.
FORMATTED_DATA_TYPES = ("number", "date", "boolean", "multi_select")

#: ⚠ THE GRANT IS TEMPORARY, AND THIS FLAG IS WHERE THE CODE SAYS SO.
#: PO 2026-08-12, verbatim: *"in remark or note section on bill - applicationd
#: eicde the format for time being"*. "For the time being" is the operative
#: half: the PO delegated the FORMAT, did not design one, and said so with an
#: end in view. So the four choices below are an application default standing
#: in until a tenant needs control of it — NOT settled design, NOT a signed
#: rule, and NOT something a later reader may cite as "the format the PO chose".
#: The day a tenant asks for `Sí`, or for `04/03/2026`, or for `1,234.00`, that
#: is a NEW question for the PO and this constant is the flag that says the
#: door was left open. Asserted by `test_us_bil_028_tc4b`.
APPLICATION_FORMAT_GRANT_IS_TEMPORARY = True

#: The words a `boolean` prints. ENGLISH, and that is the weakest part of the
#: grant rather than a hidden one: OQ-125 asked *"in which of the eleven r17.4
#: locales, given the bill may be Spanish?"* and the grant does not answer it.
#: A tenant billing in Spanish gets "Yes"/"No" today. Pinned by a test so the
#: day that is wrong it is a RED test and a new question, not a quiet drift.
BOOLEAN_TEXT = {True: "Yes", False: "No"}

#: The separator between `multi_select` values. The tenant's stored ORDER is
#: kept — sorting would be a second choice nobody asked for.
MULTI_SELECT_SEPARATOR = ", "

#: How a `date` prints: ISO 8601, `YYYY-MM-DD`, deliberately NOT the tenant's
#: `tenant_settings.date_format`. That setting still has no server-side
#: renderer (the half of OQ-125 that did not become false), and of the formats
#: available only ISO cannot be misread: `03/04/2026` is 4 March in Madrid and
#: 3 April in Houston, on a string frozen into an append-only row where no
#: reader's guess can ever be corrected.
DATE_STAMP_FORMAT = "YYYY-MM-DD"

#: How a `number` prints: the figure the tenant typed, with NO thousands
#: grouping and no forced decimal places. OQ-125 named the tension this has to
#: survive — *"a meter multiplier typed as `1.5` and a co-op member number
#: typed as `10432` want opposite answers"* — and the definition carries
#: nothing that tells the two apart, so the rule is the one that is right for
#: both: `10432` prints `10432` (grouping an identifier is wrong) and `1.5`
#: prints `1.5` (the tenant's own precision, neither padded nor truncated).
NUMBER_THOUSANDS_GROUPING = False

#: The seams. Named as constants so the contract is greppable from BOTH sides
#: of each module boundary, the way `issue.py` names its two ledger reads.
#: Resolved by name at CALL time — no import statement binds billing to another
#: module's internals (B1, G6 module boundary).
REGISTRY_MODULE = "tenancy"
REGISTRY_READ = "document_safe_custom_fields"  # (entity) -> [{key, data_type, label}]
ACCOUNT_VALUES_MODULE = "customers"
ACCOUNT_VALUES_READ = "custom_data_for_account"  # (account_id) -> {accounts, unit_id}
LOCATION_VALUES_MODULE = "metering"
LOCATION_VALUES_READ = "custom_data_for_location"  # (unit_id) -> {units, premises}


def _tenant_id() -> Any:
    """Hard rule 1: no tenant table is touched without `app.tenant_id` set.

    Refuse loudly rather than run unscoped and leave RLS as the only thing
    between one tenant's registry and another's. Same guard, same error, as
    `apps/billing/issue.py` and `apps/billing/selectors.py`.
    """
    tenant_id = core_tenancy.current_tenant_id()
    if tenant_id is None:
        raise errors.AuthError(errors.AUTH_TENANT_UNRESOLVABLE, br_ref="BR-TEN-003")
    return tenant_id


def _resolve(module: str, attribute: str) -> Any:
    """The owning module's selector, or None while it has not published one."""
    try:
        target = import_module(f"apps.{module}.selectors")
    except ImportError:
        return None
    found = getattr(target, attribute, None)
    return found if callable(found) else None


def _registry_read() -> Any:
    """The tenancy read, or REFUSE the whole run.

    Fail-closed, and this is the one refusal worth arguing for. An unresolvable
    registry would make every bill in the run stamp `{}` — which is
    indistinguishable, forever, from a tenant who had defined nothing (TC-5),
    on rows that can never be updated. A run that stops is a morning's delay; a
    run that stamps a plausible empty map is a permanent, invisible data loss.
    `BillingConfigError` rather than `BillingRuleError` because it is wrong for
    the WHOLE run, not for one account (see `exceptions.py`).
    """
    read = _resolve(REGISTRY_MODULE, REGISTRY_READ)
    if read is None:
        raise BillingConfigError(
            f"apps.{REGISTRY_MODULE}.selectors.{REGISTRY_READ} is not published, so no "
            "bill can know which tenant-defined fields belong on a document (B2 r17.3, "
            "US-BIL-028). Nothing is stamped empty in its place: an empty snapshot is "
            "indistinguishable from a tenant with no fields, it lands on an append-only "
            "row, and it can never be corrected afterwards."
        )
    return read


def _values_for_account(account_id: Any) -> dict[str, dict[str, Any]]:
    """`{entity: {key: raw value}}` for the three entities R2 reaches.

    Read through each OWNING module's selector, never by importing its models:
    the values live in a `custom_data` column on the owning row precisely so
    that only the owning module writes them (B2 r17.2 — a shared value table
    would have been a cross-module write, forbidden by DB-16/§2).

    A missing seam is the same fail-closed refusal as the registry, for the same
    reason: `{}` stamped in place of unknown values cannot be told apart later
    from `{}` meaning "nothing defined".
    """
    account_read = _resolve(ACCOUNT_VALUES_MODULE, ACCOUNT_VALUES_READ)
    location_read = _resolve(LOCATION_VALUES_MODULE, LOCATION_VALUES_READ)
    if account_read is None or location_read is None:
        raise BillingConfigError(
            f"apps.{ACCOUNT_VALUES_MODULE}.selectors.{ACCOUNT_VALUES_READ} / "
            f"apps.{LOCATION_VALUES_MODULE}.selectors.{LOCATION_VALUES_READ} are not both "
            "published, so a bill cannot read the tenant-defined values it must stamp "
            "(B2 r17.2). Refused rather than stamped empty — see the registry refusal."
        )
    account_side = account_read(account_id)
    location_side = location_read(account_side.get("unit_id"))
    return {
        "accounts": account_side.get("accounts") or {},
        "units": location_side.get("units") or {},
        "premises": location_side.get("premises") or {},
    }


def _wrong_type(entity: str, key: Any, data_type: Any, raw: Any, expected: str) -> BillingRuleError:
    """The one refusal the PO's grant did NOT lift, worded once.

    The grant is over FORMATTING — how a number, a date or a yes/no becomes
    printable text. It is not a licence to coerce: a `number` field holding
    `"abc"` has no figure to print, and `str(raw)` would freeze `"abc"` under a
    numeric label onto a row that can never be corrected. Refused per bill
    (`BillingRuleError`, not `BillingConfigError`) because it is one account's
    bad value and the other 499 bills in the run are fine (BR-BIL-055).
    """
    return BillingRuleError(
        f"custom field {entity}.{key} is typed {data_type!r} but holds {raw!r} "
        f"({type(raw).__name__}), and {expected}. Nothing is coerced: the PO's format "
        "grant of 2026-08-12 says how a value PRINTS, not that a bill may invent one, "
        "and a coerced value would print on a customer's bill and could never be "
        "corrected once the bill is issued."
    )


def _number_text(entity: str, key: Any, raw: Any) -> str:
    """A `number` as the tenant typed it — no grouping, no forced decimals.

    `bool` is rejected before anything else because Python makes it an `int`
    subclass: without this line a `number` field holding `True` would stamp
    `"1"` onto a bill, which is the silent coercion this module exists to
    refuse. `Decimal(str(raw))` and not `float`: hard rule 2 keeps floats out of
    a money path even where the value is not money.
    """
    if isinstance(raw, bool) or not isinstance(raw, (int, float, Decimal, str)):
        raise _wrong_type(entity, key, "number", raw, "that is not a figure to print")
    try:
        figure = Decimal(str(raw))
    except InvalidOperation as bad:
        raise _wrong_type(entity, key, "number", raw, "that is not a figure to print") from bad
    if not figure.is_finite():
        raise _wrong_type(entity, key, "number", raw, "that is not a finite figure to print")
    text = format(figure, "f")
    return text


def _date_text(entity: str, key: Any, raw: Any) -> str:
    """A `date` as ISO 8601 — `DATE_STAMP_FORMAT`, on purpose (see the constant).

    A stored ISO string is VALIDATED and re-emitted rather than passed through:
    `"the 4th"` must not reach a bill under a date label just because it was
    already a string. A `datetime` is refused rather than truncated — dropping
    a time is a decision about the value, and this module renders, it does not
    decide.
    """
    if isinstance(raw, datetime):
        raise _wrong_type(
            entity, key, "date", raw, "a date field cannot silently drop a time of day"
        )
    if isinstance(raw, date):
        return raw.isoformat()
    if isinstance(raw, str):
        try:
            return date.fromisoformat(raw).isoformat()
        except ValueError as bad:
            raise _wrong_type(entity, key, "date", raw, "that is not a date") from bad
    raise _wrong_type(entity, key, "date", raw, "that is not a date")


def _boolean_text(entity: str, key: Any, raw: Any) -> str:
    """A `boolean` as `BOOLEAN_TEXT` — real booleans only.

    `"yes"`, `1` and `"true"` are REFUSED rather than read as true. A stored
    value that is not a boolean means the capture path wrote something the
    definition did not describe, and guessing which side of a yes/no a customer
    is on is the worst place in this module to be approximately right.
    """
    if not isinstance(raw, bool):
        raise _wrong_type(entity, key, "boolean", raw, "that is not a yes/no")
    return BOOLEAN_TEXT[raw]


def _multi_select_text(entity: str, key: Any, raw: Any) -> str:
    """A `multi_select` as the tenant's own option strings, joined.

    A bare string is refused rather than treated as a one-item list: `"Locked
    gate"` and `["Locked gate"]` are different stored shapes, and accepting both
    would hide a capture-path defect behind an identical bill.
    """
    if not isinstance(raw, (list, tuple)):
        raise _wrong_type(entity, key, "multi_select", raw, "that is not a list of options")
    for chosen in raw:
        if not isinstance(chosen, str):
            raise _wrong_type(
                entity,
                key,
                "multi_select",
                raw,
                "one of its options is not one of the " "tenant's own option strings",
            )
    return MULTI_SELECT_SEPARATOR.join(raw)


#: The four renderers, keyed by data type — the PO's grant, as data. Adding a
#: type to `FORMATTED_DATA_TYPES` without a renderer here is a KeyError caught
#: by `test_us_bil_028_tc4b`, not a bill that prints nothing.
FORMATTERS = {
    "number": _number_text,
    "date": _date_text,
    "boolean": _boolean_text,
    "multi_select": _multi_select_text,
}


def _display_string(entity: str, definition: dict[str, Any], raw: Any) -> str:
    """One value as the string a document will print. STRINGS ONLY (r17.3).

    `text`/`select` are stamped verbatim because they already ARE the display
    string — the tenant typed them; nothing is formatted and nothing is decided.

    THE OTHER FOUR USED TO RAISE A `NotImplementedError` STUB NAMING THE OPEN
    QUESTION, AND THEY NO LONGER
    do. Until 2026-08-12 no rendering had been ruled — B2 r17.3 asked for a
    *display-format at stamp time using the tenant's Regional settings*, no
    server-side IS-8 formatter existed, and the prime directive forbade a lane
    choosing `"Yes"` over `"true"` on a value frozen into an append-only row.
    The PO closed OQ-125 that day: *"in remark or note section on bill -
    applicationd eicde the format for time being"*. So the choice is now the
    application's — **by delegation, for the time being**, which is a different
    thing from a designed format and is kept different in
    `APPLICATION_FORMAT_GRANT_IS_TEMPORARY` and in each format constant.

    A value that CONTRADICTS its declared type is still refused rather than
    coerced. `str(raw)` on a dict would stamp `"{'a': 1}"` onto a customer's
    bill, and the strings-only rule is structural (it is what makes arithmetic
    on a snapshot impossible) — satisfying it with `str()` would satisfy the
    letter and lose the point.
    """
    data_type = definition.get("data_type")
    key = definition.get("key")
    if data_type in STRING_DATA_TYPES:
        if not isinstance(raw, str):
            raise BillingRuleError(
                f"custom field {entity}.{key} is typed {data_type!r} but holds "
                f"{type(raw).__name__}, so it has no display string to stamp "
                "(BR-BIL-030: the snapshot holds strings only). Nothing is coerced — a "
                "coerced value would print on a customer's bill and could never be "
                "corrected once the bill is issued."
            )
        return raw
    if data_type in FORMATTED_DATA_TYPES:
        return FORMATTERS[data_type](entity, key, raw)
    raise BillingRuleError(
        f"custom field {entity}.{key} has data type {data_type!r}, which is not one of "
        "the six B2 r17.1 defines. A definition the platform does not understand cannot "
        "be rendered onto a document, and this module never guesses a rendering."
    )


def stamp_for_account(account_id: Any) -> dict[str, str]:
    """The `invoices.custom_snapshot` value for one bill. `dict[str, str]`, always.

    Keys are `<entity>.<key>` (r17.3). `{}` when the tenant has defined nothing,
    or has marked nothing document-safe — never `None` (US-BIL-028 TC-5), and
    the bill run is unaffected either way.

    THE RETURN TYPE IS THE GUARANTEE. `dict[str, str]` is what makes BR-TEN-048
    structural instead of aspirational: no caller can take a number out of this,
    so no tenant-defined value can reach an amount, a tax base, a ledger posting
    or a payment allocation without an explicit parse that G6 can find.

    Three filters live in `tenancy.document_safe_custom_fields` and not here,
    because they are the REGISTRY's rules: tenant scoping (rule 1), `is_active`
    (BR-TEN-050 — TC-6: a field deactivated before issue is excluded from new
    snapshots while issued invoices keep theirs) and `is_document_safe`
    (OQ-076, PO 2026-08-10, fail-closed).

    A defined field with no stored value contributes NO KEY, rather than an
    empty string. "The tenant never filled this in" and "the tenant filled it in
    as blank" are different facts about a document, and nothing ruled that they
    collapse; the absent key keeps them apart for whatever R3 decides.
    """
    _tenant_id()
    registry_read = _registry_read()
    values = _values_for_account(account_id)

    snapshot: dict[str, str] = {}
    for entity in STAMPED_ENTITIES:
        entity_values = values.get(entity) or {}
        for definition in registry_read(entity):
            key = definition.get("key")
            if key not in entity_values:
                continue
            raw = entity_values[key]
            if raw is None:
                continue
            snapshot[f"{entity}.{key}"] = _display_string(entity, definition, raw)
    return snapshot


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-BIL-028@f61575a (sha256[:7], 2026-08-11, over B12 12-engineering-plan.md + B2
#         02-database-design-brief.md + EP-BIL-02 + EP-TEN-09 +
#         07-billing/02-business-rules.md + 01-tenancy/02-business-rules.md.
#         This file's own sources: B12 addendum r7 · B2 addendum r17 ·
#         EP-BIL-02-invoice-gl.md US-BIL-028 · EP-TEN-09-custom-fields.md ·
#         07-billing/02-business-rules.md BR-BIL-030 ·
#         01-tenancy/02-business-rules.md BR-TEN-046..053)
# generated: 2026-08-11 by story-coder (tenant custom-fields lane — the R2
#         one-way door of B12 r7.2) · AMENDED 2026-08-12 by story-coder (the
#         PO's category-B ruling on OQ-125: the four formatted data types now
#         STAMP under a temporary application-format grant; the
#         `NotImplementedError` stub that named that question is gone)
# checklist: A✔ B✔ C✔ D✔(2026-08-16 — the snapshot is READ and SERVED: apps/billing/documents._remarks prints it in the one remark/note section the PO ruled on 2026-08-12, and GET /invoices/{id}/document + /document.pdf carry it. ⚠ THIS ROW READ `D=deferred(no-API-half — nothing reads the snapshot until US-NOT-016 in R3)` AND WAS TRUE WHEN WRITTEN — the PO's OQ-125/OQ-118 closure of 2026-08-12 superseded it three days before this correction, and `10-scripts/gates/surface_debt.txt` repeated the stale sentence across FIVE module lines. Hard-won law 1) E✔(the Remarks & notes band on 07-frontend/src/features/billing/BillDocumentPage.tsx) F✔ G✔ H=deferred(PO 2026-08-09)
# gates: ruff✔ black✔ · tests/test_us_bil_028_custom_snapshot.py 24 passed, 2
#         skipped (sqlite; the two isolation cases skip with a vendor reason) ·
#         the OQ-125 lane's six cases were PROVED RED against the old stub
#         first, verbatim `NotImplementedError` raised at
#         custom_snapshot.py:271 naming that question,
#         before any green was trusted (hard-won law 7) · G6 gains the DB-17
#         rule naming THIS path as its only allowlist entry, and that rule was
#         proved RED first — on apps/rating/engine.py and on
#         apps/billing/documents.py — before it was trusted green
# exceptions: (1) STAMPS AT DRAFT, where B2 r17.3 and US-BIL-028 §2 write "at
#         issue". Reported, not quiet: the canonical BR-BIL-030 in
#         07-billing/02-business-rules.md is ONE rule over the whole locked
#         document instance and names custom_snapshot inside it, stage 6 already
#         assembles that instance at draft under the PO's 2026-08-11 ruling, and
#         splitting the two timings would give one document two different "as
#         of" moments. See the docstring · (2) THE FOUR NON-STRING DATA TYPES
#         ARE FORMATTED BY THIS APPLICATION, NOT BY A RULE. This item previously
#         read "FOUR OF SIX DATA TYPES STUB ON OQ-125" and was TRUE WHEN
#         WRITTEN; the PO closed OQ-125 on 2026-08-12 (*"applicationd eicde the
#         format for time being"*) and the stub is gone. What replaced it is a
#         TEMPORARY GRANT, not a design: ungrouped numbers, ISO-8601 dates,
#         English "Yes"/"No" on a bill that may be Spanish, and ", " between
#         multi-select values — each named in its own constant, flagged by
#         `APPLICATION_FORMAT_GRANT_IS_TEMPORARY`, and each a NEW question for
#         the PO the day a tenant wants control of it. There is still no
#         server-side IS-8 formatter and `tenant_settings.date_format` still has
#         nothing behind it · (3) FIVE OF EIGHT ENTITIES ARE NOT REACHED — a
#         flat `<entity>.<key>` map has no ruled way to hold two contacts.
#         OQ-118 is CLOSED by the same 2026-08-12 ruling, which settles WHERE
#         custom fields print (one remark/note section) and does not settle the
#         key grammar, so the scope is unchanged and the gap is REPORTED · (4) this
#         file sits in a money path and implements NO money rule. This item
#         previously read "it is not in 10-scripts/gates/human_owned.txt and this
#         lane did not add it … FLAGGED for the PO batch" and was TRUE WHEN
#         WRITTEN; the glob has since landed and ✔ G7 GUARDS THIS FILE (155
#         guarded files conforming). The flag it asked for was granted, so the
#         marker above is now enforced rather than decorative
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
