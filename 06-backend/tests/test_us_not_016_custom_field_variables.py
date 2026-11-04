# ── Trace ──────────────────────────────────────────────
# Story:    US-NOT-016 (custom fields as template variables — rendered from the
#           stamped snapshot)   Screens: S91 · S92
# Rules:    BR-NOT-012 (custom-field variables resolve ONLY from
#           `invoices.custom_snapshot`, or the notification's own stored render
#           context; a missing or deactivated key renders the EMPTY STRING —
#           never None, never undefined, never a leaked `{{…}}`; values are
#           escaped in HTML and PDF alike) · BR-NOT-006 (the pin is what makes a
#           reprint reproducible) · CLAUDE.md rule 4 (a rendered document is
#           evidence of what was sent)
# ───────────────────────────────────────────────────────
"""The eight US-NOT-016 cases, on the story's own fixture.

§4: Brazos Bend bill template v3 with `{{account.custom.service_class}}` in the
header block; invoice INV-2026-09-0042 snapshot `{"account.service_class":
"Commercial"}`; and the XSS fixture, an account whose `site_note` holds
`<script>alert(1)</script>`.

⚠ ONE HALF OF OQ-075'S CLOSURE IS NOT ASSERTED HERE AND IT IS NOT AN OVERSIGHT.
The PO closed OQ-075 on 2026-08-10 with *"warn, do not block — and the field may
carry a DEFAULT VALUE … new documents render the field's DEFAULT rather than an
empty variable."* A default read at RENDER time would be the live master-data
lookup BR-NOT-012 forbids — the reprint would move whenever somebody edited the
default. The default belongs in the SNAPSHOT, written at issue by
`apps/billing/custom_snapshot.py`, which is billing's file and outside this
lane. So these cases assert the empty-string rule for a key the SNAPSHOT does
not carry, which is correct either way, and the default's home is REPORTED.
"""

from __future__ import annotations

import pytest

from apps.notifications import rendering

from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import tenant_ctx

pytestmark = pytest.mark.django_db

#: The story's own §4 template body, reduced to the two tokens it names.
BODY = "Account {account_no} · class {{account.custom.service_class}} · thank you."


def render(brazos, body, snapshot, **extra):
    with tenant_ctx(brazos):
        return rendering.render(
            template_code="receipt",
            template_version=3,
            body=body,
            context={"custom_snapshot": snapshot, **extra},
        )


# ── TC-1 / TC-2 · the snapshot, and only the snapshot ───────────────────────
def test_us_not_016_tc1_tc2__a_custom_field_renders_from_the_snapshot_and_a_reprint_is_stable(
    brazos,
):
    """US-NOT-016 TC-1: snapshot "Commercial" → the document renders
    "Commercial". TC-2: *"Master data edited to 'Irrigation' after issue;
    REPRINT the same bill → Still 'Commercial' — reprint reproducibility holds."*

    The reprint is modelled the way the product does it: the SAME snapshot is
    re-rendered, because that is what a stamped snapshot IS. The case that would
    fail without BR-NOT-012 is the one below it — a live lookup would have to
    exist for "Irrigation" to leak in, and there is no code path here that can
    read master data at all. Stated rather than dressed up as a stronger proof
    than it is (hard-won law 1).
    """
    snapshot = {"account.service_class": "Commercial"}
    first = render(brazos, BODY, snapshot, account_no="A-11024")
    assert "class Commercial ·" in first.body

    # Master data moves on; the snapshot does not, so neither does the reprint.
    reprint = render(brazos, BODY, snapshot, account_no="A-11024")
    assert reprint.body == first.body
    assert "Irrigation" not in reprint.body


def test_us_not_016_nothing_in_the_renderer_can_read_live_master_data(brazos):
    """The structural half of TC-2/TC-4, asserted as a property of the module
    rather than of one call: `render_custom_fields` takes a snapshot dict and
    has no query, no model import and no selector. A future edit that added one
    would be the defect BR-NOT-012 exists to prevent, and this is what would
    have to be deleted to introduce it."""
    import inspect

    source = inspect.getsource(rendering.render_custom_fields)
    assert "objects" not in source and "import_module" not in source
    assert rendering.render_custom_fields(BODY, None).endswith("thank you.")


# ── TC-3 / TC-4 · absence is an empty space, never an artifact ──────────────
def test_us_not_016_tc3_tc4__a_missing_or_deactivated_key_renders_empty(brazos):
    """US-NOT-016 TC-3, verbatim: *"Template references a key absent from the
    snapshot → Renders empty. No `{{…}}`, no 'None', no exception, and the rest
    of the document is unaffected."* TC-4 is the same rule reached by a
    different route: the field was deactivated after issue, so the historical
    snapshot is what answers.

    PROVED RED by making the substitution return `str(value)` unconditionally:
    the document then rendered the literal `None` where a customer's own
    reference number belongs, and this failed with
    `assert 'None' not in artifact.body`.
    """
    artifact = render(brazos, BODY, {}, account_no="A-11024")

    assert "class  ·" in artifact.body  # an empty space, not a mark
    assert "{{" not in artifact.body and "}}" not in artifact.body
    assert "None" not in artifact.body
    # The rest of the document is untouched — a missing custom field never
    # costs the customer the parts of the letter that DID resolve.
    assert "A-11024" in artifact.body and "thank you." in artifact.body


def test_us_not_016_an_absent_custom_field_is_not_the_platforms_named_absence(brazos):
    """The distinction that makes the empty string right rather than lazy.

    A CATALOGUED A19 token with no value renders `——` (OQ-117: a named absence
    goes out, because the platform promised that figure and could not produce
    it). A custom field is the tenant's own OPTIONAL column: an account with no
    "service class" is normal, and printing `——` beside the label would tell the
    customer something had gone wrong when nothing had.
    """
    artifact = render(brazos, "{first_name} · {{account.custom.service_class}}", {})
    assert rendering.ABSENT_MARK in artifact.body  # {first_name}: promised, absent
    assert artifact.body.endswith("· ")  # the custom field: simply not there
    assert [absence["token"] for absence in artifact.absences] == ["first_name"]


# ── TC-5 · escaping ─────────────────────────────────────────────────────────
def test_us_not_016_tc5__a_scripted_custom_value_is_escaped(brazos):
    """US-NOT-016 TC-5: *"Custom value containing `<script>alert(1)</script>` →
    Escaped in HTML and PDF output; no executable content in either."*

    PROVED RED by removing the `_escape` call: the rendered body carried the
    raw `<script>alert(1)</script>` straight through, and this failed with
    `assert '<script>' not in artifact.body` — a tenant-authored value would
    have reached an email body as executable markup.
    """
    artifact = render(
        brazos,
        "Note: {{account.custom.site_note}}",
        {"account.site_note": "<script>alert(1)</script>"},
    )
    assert "<script>" not in artifact.body
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in artifact.body


def test_us_not_016_tc6__a_key_from_another_entitys_namespace_renders_empty(brazos):
    """US-NOT-016 TC-6: *"Template author references a key from another entity's
    namespace → the picker does not offer it; a hand-typed one renders empty
    rather than reaching across."*

    The namespace is part of the LOOKUP (`"<entity>.<key>"`), not a filter
    applied afterwards, so an `account` token cannot reach a `premises` value
    even when both exist in the same snapshot.
    """
    artifact = render(
        brazos,
        "{{account.site_note}} {{account.custom.site_note}}",
        {"premises.site_note": "Behind the gate"},
    )
    assert "Behind the gate" not in artifact.body


# ── TC-7 · a non-invoice notice uses its own stored context ─────────────────
def test_us_not_016_tc7__a_notice_resolves_from_its_own_render_context(brazos):
    """US-NOT-016 TC-7: *"Non-invoice notice (e.g. a reminder) → Resolves from
    the notification's stored render context, fixed at send."*

    Same function, same rule, different snapshot source — which is BR-NOT-012's
    parenthesis in code: *"(or the notification's own stored render context for
    non-invoice notices)"*. There is no second code path to keep in step.
    """
    artifact = render(
        brazos,
        "Reminder for class {{account.custom.service_class}}.",
        {"account.service_class": "Irrigation"},
    )
    assert "class Irrigation." in artifact.body


# ── TC-8 · isolation, at the resolution level ───────────────────────────────
def test_us_not_016_tc8__a_custom_key_cannot_resolve_across_tenants(brazos, lonestar):
    """US-NOT-016 TC-8: *"Lone Star Ridge template referencing a Brazos Bend key
    → Renders empty. No cross-tenant resolution path exists."*

    And it cannot exist: resolution reads the snapshot the CALLER passes, which
    came off the caller's own tenant-scoped document. There is no registry
    lookup to scope wrongly — the RLS half of the guarantee belongs to whoever
    loaded the document, and this is the application half.
    """
    brazos_snapshot = {"account.service_class": "Commercial"}
    with tenant_ctx(lonestar):
        theirs = rendering.render(
            template_code="receipt",
            template_version=1,
            body=BODY,
            context={"custom_snapshot": {}, "account_no": "A-2201"},
        )
    assert "Commercial" not in theirs.body
    assert brazos_snapshot["account.service_class"] not in theirs.body


def test_us_not_016_a_custom_token_is_never_validated_against_a_class_catalog(brazos):
    """Custom variables are a per-tenant registry, not a signed vocabulary, so
    the palette rule (US-NOT-005 TC-5) must NOT reject them — and the A19 token
    scan must not see them either, or `{{account.custom.meter_no}}` on a receipt
    would be refused as the forbidden `{meter_no}`."""
    with tenant_ctx(brazos):
        rendering.validate_body("receipt", "Paid {amount} · {{account.custom.meter_no}}")
    assert rendering.tokens_in("{amount} {{account.custom.meter_no}}") == ("amount",)
    assert rendering.custom_tokens_in("{{account.custom.meter_no}}") == (("account", "meter_no"),)


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-NOT-016@8f31b0d (sha1[:7] of the four sources this slice was authored from, concatenated in order: 04-docs/05-modules/10-notifications/06-epics/EP-NOT-02-templates-rendering.md — US-NOT-016 §1/§3/§5 — · 10-notifications/02-business-rules.md · 12-governance/01-open-questions.md — OQ-075's closure — · 04-docs/02-decisions/02-database-design-brief.md Addendum r17.3)
# generated: 2026-08-15 by story-coder (W3 notifications CONTENT lane — custom-field variables)
# checklist: A✔ B✔ C✔ D=deferred(no-API-half — the S91/S92 variable picker is billing's designer UI, US-BIL-021) E=deferred(no-frontend-half) F✔ G✔ H=deferred(PO 2026-08-09)
# gates: ruff✔ black✔ · two guards proved RED before green (hard-won law 7): the
#         empty-string rule (`str(value)` unconditionally ⇒ the literal `None`
#         rendered onto a customer document) and the escape (`<script>` reached
#         the body raw). Transcripts in the lane report
# exceptions: (1) US-NOT-016's frontmatter still reads `blocked_by: [OQ-075]`
#         and **OQ-075 IS CLOSED** (PO 2026-08-10) — so the story is NOT blocked
#         and nothing here stubs. The stale frontmatter is REPORTED rather than
#         edited from a code lane.
#         (2) THE DEFAULT-VALUE HALF OF THAT CLOSURE IS NOT IMPLEMENTED — *"the
#         field may carry a DEFAULT VALUE … new documents render the field's
#         default"*. A default read at RENDER time would be the live master-data
#         lookup BR-NOT-012 forbids; it belongs in the SNAPSHOT WRITER
#         (`apps/billing/custom_snapshot.py`, billing's, outside this lane).
#         REPORTED.
#         (3) TC-2's "master data edited" is modelled by RE-RENDERING THE SAME
#         SNAPSHOT, because that is what the product does. The stronger claim —
#         that no live lookup is even possible — is asserted separately as a
#         property of the module, and the weaker one is not dressed up as it.
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
