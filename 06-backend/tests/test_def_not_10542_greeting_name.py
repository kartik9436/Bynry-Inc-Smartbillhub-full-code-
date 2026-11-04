# ── Trace ──────────────────────────────────────────────
# Defect:   DEF-NOT-10542 — the bill email greeted "Hi Miller,," for a contact
#           stored surname-first ("Miller, Sarah")
# Rules:    decision log 2026-10-22 "One greeting for every letter" ·
#           BR-BIL-030 (the bill greets the name stamped at gather)
# Tests:    this file
# ───────────────────────────────────────────────────────
"""**Every letter derives `{first_name}` through ONE function.**

REPRODUCED BEFORE THE FIX (law 7): `bill_render_context` took the first word of
the stamped name, so *"Miller, Sarah"* gave `first_name == "Miller,"` and the
seeded body *"Hi {first_name},"* rendered *"Hi Miller,,"*. Every earlier fixture
wrote its contact given-name first, which is why nothing caught it.

⚠ **WHAT WOULD MAKE THESE PASS WRONGLY** (law 7, habit 2): a fixture written
given-name first, where first-word and the real rule agree. Every rendered case
here uses the surname-first spelling, and asserts the doubled comma ABSENT as
well as the right greeting present.
"""

from __future__ import annotations

import pytest

from apps.billing import delivery_seam, statement
from apps.notifications import bill_email_wording, customer_context, rendering, transfer_events
from tests.test_def_4448_every_letter_carries_its_figures import _Invoice
from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import tenant_ctx


@pytest.mark.parametrize(
    ("name", "kind", "expected"),
    [
        ("Miller, Sarah", None, "Sarah"),  # surname-first
        ("Sarah Miller", None, "Sarah"),  # given-first
        ("Sarah", None, "Sarah"),  # a single word
        ("Acme Holdings LLC", "company", "Acme Holdings LLC"),  # a company
        ("Miller,", None, "Miller"),  # no given name: the whole name, no comma
        ("  Miller ,  ", None, "Miller"),
        ("", None, None),
        (None, None, None),
    ],
)
def test_the_shared_builder_greets_the_given_name(name, kind, expected):
    assert customer_context.greeting_name(name, kind) == expected


def _invoice(**kwargs):
    invoice = _Invoice(**kwargs)
    invoice.bill_payload["customer_name"] = "Miller, Sarah"
    return invoice


def test_the_bill_context_greets_the_given_name_of_a_surname_first_contact():
    context, _ = delivery_seam.bill_render_context(_invoice())
    assert context["first_name"] == "Sarah"
    # BR-BIL-030 — the name itself is still the stamped one, untouched.
    assert context["customer_name"] == "Miller, Sarah"


@pytest.mark.django_db
@pytest.mark.parametrize("code", [bill_email_wording.BILL_READY, bill_email_wording.CORRECTED_BILL])
def test_the_bill_ready_and_corrected_bill_emails_render_hi_sarah(brazos, code):
    subject, body = bill_email_wording.WORDING[code]["en"]
    with tenant_ctx(brazos):
        context, _ = delivery_seam.bill_render_context(_invoice())
        artifact = rendering.render(
            template_code=code,
            template_version=1,
            body=body,
            subject=subject,
            context=context,
        )
    assert "Hi Sarah," in artifact.body
    assert "Miller,," not in artifact.body
    assert "Hi Miller" not in artifact.body


def test_no_writer_splits_a_name_by_itself():
    """The four writers that used to split the name now call the builder."""
    import inspect

    for module in (delivery_seam, statement, transfer_events):
        source = inspect.getsource(module)
        assert ".split()[0] if name" not in source, module.__name__
        assert '.split(",")[-1]' not in source, module.__name__
        assert "greeting_name" in source, module.__name__
