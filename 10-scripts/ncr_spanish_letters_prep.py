"""ncr_spanish_letters_prep — publish a Spanish (`es`) variant of the New
Connection *build confirmed* letter, for the letter-language walk.

PO ruling 2026-10-02 (decision log *"SEVEN PO ANSWERS IN ONE MESSAGE"*, item 2):
*"A with the English fallback. She asked for Spanish. Today her choice is saved
but never used."* A New Connection letter goes in the language chosen on step 1,
and falls back to the utility's language where no template exists in it.

The discriminating fixture is a PUBLISHED SPANISH VARIANT (the same argument
`tests/test_cr199_messages_follow_the_customers_language.py` makes): without
one every letter lands on the default wording whatever language is asked for,
and a walk that reads "English" passes over the old code and the new alike.
Only `new_connect_confirmed` gets one, so the *quote* letter is the fallback
case in the same walk.

Walk database only — never a shared or demo database:

    DATABASE_URL=postgres://…/ncr_e2e python 10-scripts/ncr_spanish_letters_prep.py

Idempotent: a tenant that already has an `es` variant of the class is left alone.
"""

from __future__ import annotations

import importlib.util
import os
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "06-backend"))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.local")

_spec = importlib.util.spec_from_file_location(
    "seed_journey_fixture", REPO / "08-qa/01-e2e/stack/seed_journey_fixture.py"
)
sjf = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(sjf)  # type: ignore[union-attr]

CLASS = "new_connect_confirmed"
SPANISH = "Hola."


def main() -> int:
    sjf.django_setup()
    from apps.notifications import template_models as tm
    from apps.notifications import template_service
    from core import tenancy as core_tenancy

    tenant, actor = sjf.tenant_and_actor()
    with core_tenancy.tenant_context(tenant.id):
        if tm.NotificationTemplate.objects.filter(
            tenant_id=tenant.id, code=CLASS, language="es"
        ).exists():
            print(f"{CLASS}: an es variant already exists - nothing written")
            return 0
        default = template_service.resolve(code=CLASS)
        pinned = template_service.load_pinned(
            template_id=default.template_id, version=default.version
        )
        row, _created = template_service.register(
            code=CLASS, name="Confirmación (español)", actor=actor, language="es"
        )
        draft = template_service.save_draft(
            template=row,
            body=f"{SPANISH} {pinned.body}",
            subject=f"{SPANISH} {pinned.subject or ''}".strip(),
            actor=actor,
        )
        template_service.publish(version_row=draft, actor=actor)
        print(f"{CLASS}: es variant published (v{draft.version})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
