# ── Trace ──────────────────────────────────────────────
# Story:    US-NOT-005 (the template library — CR-009 C-14: the plan-void
#           notice's default language)   Screens: S8 (templates card) · SET-10
# Rules:    C-14 (PO 2026-08-17, verbatim: "you give default language for the
#           plan-void notice only - we wil allow utility to make the changes")
#           · BR-PAY-016 as superseded (the 'nodrop' ruling STANDS — nothing
#           voids a plan, so this is wording ahead of a flow) · BR-NOT-007
#           (the three plan-notice variants)
# ───────────────────────────────────────────────────────
"""C-14: the plan-void notice exists, says the ruled things, and claims nothing
no rule states.

The interesting assertions are the ABSENCES: no missed-instalment threshold
(the 'nodrop' ruling abolished the second-miss void and no rule set a new
figure), and no collection-agency or legal claim (the writeoff_notice
discipline). A body that gained either would be prose hardening an unruled
policy, and these go RED on it.
"""

from __future__ import annotations

from datetime import date

import pytest

from apps.notifications import catalogs, rendering, seed_templates

from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import tenant_ctx

pytestmark = pytest.mark.django_db

CODE = "plan_notice_void"
ON_DATE = date(2026, 8, 18)


def test_c14__the_class_is_catalogued_with_its_siblings_vocabulary():
    """The C-14 instruction is explicit: reuse the plan-notice vocabulary."""
    void = catalogs.catalog_for(CODE)
    missed = catalogs.catalog_for("plan_notice_missed")
    assert void is not None, "plan_notice_void has no catalogue — C-14 not honoured"
    assert void.tokens == missed.tokens, (
        "the plan-void palette drifted from its siblings'; one caller's context "
        "must serve all three plan notices"
    )
    # And it LEFT both refusal registries — a class cannot be authored and
    # refused at once (the fold in catalogs.py enforces the first half).
    assert CODE not in catalogs.CLASSES_WITHOUT_CATALOG
    assert catalogs.not_authored_reason(CODE) is None


def test_c14__the_body_validates_and_is_seeded_on_a_real_tenant(brazos, dana):
    """The default language reaches every tenant the way every other authored
    body does — planted at seed, published, resolvable."""
    with tenant_ctx(brazos):
        answer = seed_templates.seed_notice_templates(dana, on_date=ON_DATE)
    seeded = {row["code"] for row in answer["seeded"] if row["created"] or row["already_present"]}
    assert CODE in seeded
    absent = {row["code"] for row in answer["absent"]}
    assert CODE not in absent


def test_c14__the_body_states_the_ruled_content_and_nothing_unruled():
    """Voided + why + the balance now due + contact tokens — and NO figure a
    customer could hold us to that no rule states."""
    body = seed_templates.PLAN_NOTICE_VOID_BODY
    subject = seed_templates.PLAN_NOTICE_VOID_SUBJECT
    # The ruled content, in plain words.
    assert "voided" in body and "voided" in subject
    assert "missed" in body  # why — missed installments
    assert "{plan_balance}" in body and "now due" in body  # the balance now due
    for token in ("{support_phone}", "{utility_website}", "{account_no}"):
        assert token in body
    # THE ABSENCES THAT ARE THE POINT:
    # · no miss-count threshold — the 'nodrop' ruling stands and no rule sets one
    for phrase in ("2 missed", "two missed", "second miss", "2nd miss"):
        assert phrase not in body.lower()
    # · no legal/collections claim (the writeoff_notice discipline)
    for phrase in ("collection agency", "legal", "attorney"):
        assert phrase not in body.lower()
    # · and it passes the same gate a tenant's save would.
    rendering.validate_body(CODE, body, subject=subject)


def test_c14__the_seed_source_names_the_ruling_and_the_missing_writer():
    """A reviewer of the guarded seeder must see, on the row, BOTH facts: which
    ruling authorised these words, and that nothing fires the event yet."""
    entry = next(e for e in seed_templates.SEEDABLE if e.code == CODE)
    assert "C-14" in entry.source
    assert "you give default language for the plan-void notice only" in entry.source
    assert "nodrop" in entry.source  # the event's absence, stated where it bites


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-NOT-005@cr009c14 (12-governance/02-decision-log.md → 2026-08-17 C-14 verbatim · 12-governance/01-open-questions.md OQ-260(a)/OQ-207 stamps · apps/notifications/catalogs.py AUTHORED_CATALOGS + the quoted NOT_AUTHORED departure · apps/notifications/seed_templates.py)
# generated: 2026-08-18 by story-coder (CR-009 C-section lane)
# checklist: A✔ B✔ C✔ D=deferred(no new API — the existing template routes serve the class) E=deferred(SET-10 opens it like any variant; no new screen) F✔ G✔ H=deferred(PO 2026-08-09)
# gates: the threshold-absence guard was red-proved by adding "after 2 missed installments" to the body and reading the failure; the palette-parity guard by dropping {installment_no} from the void palette.
# exceptions: (1) NO TRIGGER TEST — nothing voids a plan ('nodrop' stands) and inventing a voider to prove a letter would answer a question the PO has not asked; the wording-ahead-of-flow posture is asserted on the SOURCE string instead. (2) test_def_210's 37/33 arithmetic and test_def_163's absent-list are the other half of this change and were amended dated in their own files.
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
