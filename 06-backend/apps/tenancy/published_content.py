# ── Trace ──────────────────────────────────────────────
# Story:    US-CWP-071 (EP-CWP-12) — draft, translate, publish · US-CWP-072 —
#           help on the portal · US-CWP-073 — one tip, in season ·
#           US-CWP-074 — service centres, and *hidden* is a state.
#           Screens: CWP-071 · CWP-072 · CWP-073 · CWP-074 · CWP-075 ·
#           CWP-011 · CWP-060 · CWP-013 · CWP-014
# Rules:    BR-CWP-093 · BR-CWP-094 · BR-CWP-095 · BR-CWP-096 (quoted verbatim
#           at the function each one governs) · B14 rule 31 (no database id is
#           a visible value — every public handle here is a slug) · B14 rule 35
#           (the SERVER sends facts, never an assembled English sentence, so a
#           catalogue can be written in its own language) · CLAUDE.md hard rule
#           1 (tenant scoping) · rule 7 (every action a clerk takes writes
#           audit_log) · A4 `settings_lookups`
# Tests:    06-backend/tests/test_us_cwp_071_help.py ·
#           test_us_cwp_072_help_portal.py · test_us_cwp_073_tips.py ·
#           test_us_cwp_074_centres.py · test_us_cwp_071_pg.py
# Impacts:  apps/tenancy/published_content_api.py (the HTTP surface) ·
#           apps/portal/seams/tenancy_seam.py (the portal's read side) ·
#           apps/portal/guest_api.py (four guest reads)
# ───────────────────────────────────────────────────────
"""Help answers, tips and service centres — every read and every write.

⚠ **THE BOUNDARY THIS MODULE STOPS AT, STATED ONCE (`OQ-1398`).** Who keeps the
answers current, and in how many languages, is an OPEN question and **may not
be answered by a lane**. So this module builds the STORE, the STATUSES and the
VARIANTS, and builds no translation workflow: nothing assigns a translation,
nothing chases one, nothing notifies anybody that one is missing, and no screen
promises that any of that will happen. `needs_translating` is a VISIBLE STATE
and that is the whole of it — a utility can see what its Spanish-speaking
customers are not being shown, and decide for itself. The mechanism is not
blocked by the question; only the workflow is, and the workflow is not here.

FOUR RULES, EACH ONE IN THE PLACE IT ACTS
-----------------------------------------
* **`BR-CWP-094` is in the QUERY.** `published_answers()` filters
  `status = published` in SQL. `03-field-map.md` §2 says why in as many words:
  *"The gate is `status = published`, in the query, not in the template."* A
  template filter is one refactor away from a leak, and the leak is a draft
  answer a customer reads.
* **`BR-CWP-093` — nothing empty ever appears.** Every count this module
  publishes exists so a link can be ABSENT: `published_answer_count()` and
  `shown_centre_count()` are what the front page's `links` hang on, and
  `centres()` answers 404 rather than an empty page.
* **`BR-CWP-095` — at most one tip**, and an empty answer is a NORMAL answer.
  `tip_for_screen()` returns `None` and the caller renders nothing at all; it
  never raises, never 404s and never returns a frame to be filled.
* **`BR-CWP-096` — hidden is a state.** Every back-office read returns the
  hidden rows; every guest read filters them out. And a holiday closes a centre
  with nobody typing anything: `centre_today()` reads `HolidayCalendar`.

WHY NO SENTENCE IS ASSEMBLED HERE (B14 rule 35)
------------------------------------------------
*"Closed today · Opens Thursday at 9:00am"* is drawn by the screen, from the
facts this module returns — the weekday number, the time, the holiday label.
Assembling it on the server would ship an English sentence to eleven
catalogues, and a catalogue is written in its own language, not translated from
English. The one string that does cross is the utility's OWN word for its
holiday (*Thanksgiving*), which is data and not copy.
"""

from __future__ import annotations

import re
import unicodedata
from datetime import date, datetime, time, timedelta
from typing import Any

from django.conf import settings
from django.db import transaction
from django.db.models import Count
from django.utils import timezone as django_timezone

from apps.tenancy import models as tenancy_models
from apps.tenancy import published_content_models as content
from apps.tenancy import selectors as tenancy_selectors
from core import audit, errors
from core.permissions import SYSTEM_ADMIN, require_role

#: The five things a customer might come to a counter for (`US-CWP-074` §1).
#: ⚠ UNTICKED RENDERS AS *CANNOT*, NOT AS ABSENT — the guest screen draws all
#: five and marks the ones this centre cannot do, because *"a list that also
#: shows what it cannot do is an answer"*.
CENTRE_ACTIONS: tuple[str, ...] = (
    "pay_a_bill",
    "open_or_close_an_account",
    "report_a_problem",
    "hand_in_a_document",
    "ask_a_question",
)

#: What a counter can take. The catalogue names them; the screen shows the ones
#: ticked and says plainly which are not (`US-CWP-074` TC-6: the north counter
#: takes cash and cheque and has **no card machine**).
CENTRE_PAYMENT_METHODS: tuple[str, ...] = ("cash", "cheque", "card", "money_order")

#: Where a tip may be aimed. One screen per tip (`BR-CWP-095` — one tip per
#: screen at a time), named for the portal screen a customer is looking at.
#:
#: ⚠ **`usage` AND `usage_looks_high` ARE TWO SCREENS, AND READING THEM AS ONE
#: BREAKS THE FIXTURE.** `US-CWP-073` §4 aims *"A running toilet can use 4,000
#: gallons a month"* at *Usage looks high* and *"Watering before 10am loses
#: less to evaporation"* at *Usage*; if those were one screen the two tips
#: would compete and only one could ever show, which is not what TC-1's
#: *"four showing today"* describes. Six tips, six screens, one slot each.
TIP_SCREENS: tuple[str, ...] = (
    "portal_home",
    "usage",
    "usage_looks_high",
    "send_a_reading",
    "overdue",
    "every_reading",
)

#: The topics `CWP-011`'s chips offer. A topic outside this list is refused, so
#: the guest screen's chip row is a closed set and never grows a typo.
ANSWER_TOPICS: tuple[str, ...] = (
    "billing",
    "paying",
    "readings",
    "water",
    "moving",
)

#: Where an answer may ALSO appear (`help_answer.also_show_on_screen`). Null is
#: *the help list only*.
ALSO_SHOW_SCREENS: tuple[str, ...] = ("bill", "usage", "overdue")

#: ⚠ **THE GUEST SURFACE'S READS, DECLARED AS DATA SO A GATE CAN READ THEM
#: (`G88`).** Each row is a function in this module that a visitor can reach,
#: and the keyword its query MUST carry — `BR-CWP-094`'s *"the gate is
#: `status = published`, in the query, not in the template"*, made checkable.
#:
#: The gate asserts three things and the third is the one that matters most:
#: every one of these carries its gate inside a `filter(...)`; none of them
#: decides the same thing in Python afterwards; and **`apps/portal/seams/
#: tenancy_seam.py` may call NOTHING ELSE from this module** — so a lane cannot
#: publish `back_office_answers`, which holds all three states, onto the guest
#: surface by adding one convenient seam function.
GUEST_READS: dict[str, str] = {
    "published_answers": "status",
    "published_answer": "status",
    "published_answer_count": "status",
    "attached_answer": "status",
    "record_feedback": "status",
    "public_centres": "is_shown_to_customers",
    "public_centre": "is_shown_to_customers",
    "shown_centre_count": "is_shown_to_customers",
    "tip_for_screen": "is_on",
}


# ══ Small shared helpers ═══════════════════════════════════════════════════


def _slugify(value: str) -> str:
    """A stable, readable, id-free handle (B14 rule 31: a URL is a visible
    value, so it may not be a uuid)."""
    normalised = unicodedata.normalize("NFKD", value)
    ascii_only = normalised.encode("ascii", "ignore").decode("ascii").lower()
    slug = re.sub(r"[^a-z0-9]+", "-", ascii_only).strip("-")
    return slug[:80] or "answer"


def _unique_slug(tenant_id: Any, model: Any, base: str, *, exclude_pk: Any = None) -> str:
    slug = base
    n = 2
    while True:
        taken = model.objects.filter(tenant_id=tenant_id, slug=slug)
        if exclude_pk is not None:
            taken = taken.exclude(pk=exclude_pk)
        if not taken.exists():
            return slug
        slug = f"{base}-{n}"[:80]
        n += 1


def _field_error(field: str, code: str, message_key: str, **params: Any) -> dict[str, Any]:
    return {"field": field, "code": code, "message_key": message_key, "params": params}


def _refuse(field_errors: list[dict[str, Any]], message_key: str) -> None:
    if field_errors:
        raise errors.ValidationError(
            errors.VAL_FORMAT, message_key=message_key, field_errors=field_errors
        )


def _audit_row(
    actor: Any, action: str, entity_type: str, entity_id: Any, before: Any, after: Any
) -> None:
    audit.write_row(
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        actor_user_id=getattr(actor, "id", None),
        before=before,
        after=after,
    )


def _clock_override() -> datetime | None:
    """The demo clock, or nothing — and it is nothing on every deployed build.

    ⚠ **HONOURED ONLY UNDER `DEBUG`.** `PORTAL_CLOCK_OVERRIDE` exists so the
    wave's walkthrough can stand on a Wednesday in November and SEE the two
    sentences `BR-CWP-096` is about (*"Opens Thursday at 9:00am"* and
    *"Closed 26 November — Thanksgiving"*), which are computed from the clock
    and can therefore only be seen on the day they are true. `DEBUG` is False
    in `config/settings/base.py` and in `production.py`, so the variable can be
    set on a deployed host — or left in a `.env` by accident, which is the
    failure mode hard-won law 4 names — and a customer's opening hours still
    come from the real clock. The unsafe option is the one you have to type,
    twice.
    """
    if not getattr(settings, "DEBUG", False):
        return None
    raw = getattr(settings, "PORTAL_CLOCK_OVERRIDE", None)
    if not raw:
        return None
    try:
        parsed = datetime.fromisoformat(str(raw))
    except ValueError:
        return None
    tz = tenancy_selectors.tenant_timezone()
    return parsed.replace(tzinfo=tz) if parsed.tzinfo is None else parsed.astimezone(tz)


def _tenant_today(tenant_id: Any) -> date:
    """The utility's own today, not the server's. A centre in Austin is closed
    on the day Austin says it is."""
    return _tenant_now(tenant_id).date()


def _tenant_now(tenant_id: Any) -> datetime:
    override = _clock_override()
    if override is not None:
        return override
    return django_timezone.now().astimezone(tenancy_selectors.tenant_timezone())


def _hhmm(value: time | None) -> str | None:
    """A time as `HH:MM`, never as a formatted clock — *9:00am* against
    *09h00* is the screen's business and the catalogue's (B14 rule 35)."""
    return None if value is None else value.strftime("%H:%M")


# ══ HELP ANSWERS — reads ═══════════════════════════════════════════════════


def _variant_rows(answer: content.HelpAnswer) -> list[dict[str, Any]]:
    by_locale = {row.locale: row for row in answer.variants.all()}
    rows = []
    for locale in content.LOCALES:
        row = by_locale.get(locale)
        rows.append(
            {
                "locale": locale,
                "status": row.status if row else content.VARIANT_NEEDS_TRANSLATING,
                "has_body": bool(row and row.body.strip()),
                "last_changed_on": (
                    row.last_changed_on.isoformat() if row and row.last_changed_on else None
                ),
            }
        )
    return rows


def _read_counts(tenant_id: Any, *, since: date) -> dict[Any, int]:
    """*Read this month*, per answer — reads only, never votes (`CP-34`: a read
    and a vote are counted separately, and adding them together is a number
    that cannot be un-added)."""
    rows = (
        content.HelpAnswerFeedback.objects.filter(
            tenant_id=tenant_id, event=content.FEEDBACK_READ, occurred_on__gte=since
        )
        .values("answer_id")
        .annotate(n=Count("id"))
    )
    return {row["answer_id"]: row["n"] for row in rows}


def back_office_answers(tenant_id: Any) -> list[dict[str, Any]]:
    """`CWP-071`'s list — **every** answer, in portal order.

    ⚠ Draft and not-shown are HERE and nowhere else. This is the one list that
    holds all three states; the guest read below holds one.
    """
    since = _tenant_today(tenant_id).replace(day=1)
    counts = _read_counts(tenant_id, since=since)
    rows = (
        content.HelpAnswer.objects.filter(tenant_id=tenant_id)
        .prefetch_related("variants")
        .order_by("position", "created_at")
    )
    out = []
    for answer in rows:
        variants = _variant_rows(answer)
        published = [v for v in variants if v["status"] == content.VARIANT_PUBLISHED]
        out.append(
            {
                "slug": answer.slug,
                "question": answer.question,
                "topic": answer.topic,
                "status": answer.status,
                "position": answer.position,
                "also_show_on_screen": answer.also_show_on_screen,
                "languages_published": len(published),
                "languages_total": len(content.LOCALES),
                "needs_translating": len(variants) - len(published),
                "reads_this_month": counts.get(answer.id, 0),
                "last_changed_by": answer.last_changed_by,
                "last_changed_on": (
                    answer.last_changed_on.isoformat() if answer.last_changed_on else None
                ),
            }
        )
    return out


def _answer_or_404(tenant_id: Any, slug: str) -> content.HelpAnswer:
    answer = (
        content.HelpAnswer.objects.filter(tenant_id=tenant_id, slug=slug)
        .prefetch_related("variants")
        .first()
    )
    if answer is None:
        raise errors.deny_as_not_found("BR-CWP-005")
    return answer


def back_office_answer(tenant_id: Any, slug: str) -> dict[str, Any]:
    """`CWP-072`'s editor: the question, where it also appears, and the language
    table where a missing translation is a **visible state**."""
    answer = _answer_or_404(tenant_id, slug)
    since = _tenant_today(tenant_id).replace(day=1)
    bodies = {row.locale: row.body for row in answer.variants.all()}
    return {
        "slug": answer.slug,
        "question": answer.question,
        "topic": answer.topic,
        "status": answer.status,
        "position": answer.position,
        "also_show_on_screen": answer.also_show_on_screen,
        "body": bodies.get(content.FALLBACK_LOCALE, ""),
        "variants": _variant_rows(answer),
        "reads_this_month": _read_counts(tenant_id, since=since).get(answer.id, 0),
        "last_changed_by": answer.last_changed_by,
        "last_changed_on": answer.last_changed_on.isoformat() if answer.last_changed_on else None,
        # ⚠ US-CWP-071 TC-9: publishing takes effect immediately and the screen
        # must SAY so. The flag is here so the sentence is not a screen's own
        # invention that a later refactor can drop.
        "publish_is_immediate": True,
        "has_approval_step": False,
    }


def published_answer_count(tenant_id: Any) -> int:
    """`BR-CWP-093`: the Help card and the Help link exist only when this is
    above zero."""
    return content.HelpAnswer.objects.filter(
        tenant_id=tenant_id, status=content.ANSWER_PUBLISHED
    ).count()


def published_answers(tenant_id: Any, *, topic: str | None = None) -> list[dict[str, Any]]:
    """`GET /public/help` — `BR-CWP-094`, verbatim: *"An answer shows only when
    **Published**. Draft and Not-shown never leave the back office, and the
    customer is never told a count of what is hidden."*

    ⚠ **`status = published` IS IN THE QUERY** — the `.filter()` below, in SQL,
    not a comprehension over everything and not a template test. `US-CWP-071`
    TC-2 asserts it at that level.

    ⚠ **AND NOTHING HERE COUNTS WHAT IS HIDDEN** (TC-3). The response carries
    the six rows and no total, no `hidden`, no `of eight`.
    """
    rows = content.HelpAnswer.objects.filter(tenant_id=tenant_id, status=content.ANSWER_PUBLISHED)
    if topic:
        rows = rows.filter(topic=topic)
    return [
        {"slug": row.slug, "question": row.question, "topic": row.topic}
        for row in rows.order_by("position", "created_at")
    ]


def published_answer(tenant_id: Any, slug: str, *, locale: str | None) -> dict[str, Any]:
    """`GET /public/help/{slug}` — one answer, in the reader's language when
    there is one and **in English when there is not**.

    `BR-CWP-094`: *"A missing translation falls back to English rather than
    hiding the answer"* — *"a missing translation is better than a missing
    answer"*. The fallback is REPORTED, never silent: `shown_in` and
    `asked_for` differ and the screen says a line about it (`US-CWP-072` TC-8).
    """
    answer = (
        content.HelpAnswer.objects.filter(
            tenant_id=tenant_id, slug=slug, status=content.ANSWER_PUBLISHED
        )
        .prefetch_related("variants")
        .first()
    )
    if answer is None:
        # A draft, a not-shown, a stranger's or a typo — one shape, one status
        # (US-CWP-071 TC-2: a draft NEVER leaves the API).
        raise errors.deny_as_not_found("BR-CWP-094")
    wanted = (locale or content.FALLBACK_LOCALE).strip()
    by_locale = {
        row.locale: row
        for row in answer.variants.all()
        if row.status == content.VARIANT_PUBLISHED and row.body.strip()
    }
    chosen = by_locale.get(wanted)
    if chosen is None and "-" in wanted:  # `fr-CA` reads `fr-FR`'s French
        base = wanted.split("-")[0]
        chosen = next((row for code, row in by_locale.items() if code.split("-")[0] == base), None)
    if chosen is None:
        chosen = by_locale.get(content.FALLBACK_LOCALE)
    if chosen is None:
        # Published with no readable body in any language: the list must not
        # offer a door that opens onto nothing (BR-CWP-093).
        raise errors.deny_as_not_found("BR-CWP-093")
    related = [
        {"slug": row.slug, "question": row.question}
        for row in content.HelpAnswer.objects.filter(
            tenant_id=tenant_id, status=content.ANSWER_PUBLISHED, topic=answer.topic
        )
        .exclude(pk=answer.pk)
        .order_by("position", "created_at")[:2]
    ]
    also_written_in = sorted(by_locale.keys())
    return {
        "slug": answer.slug,
        "question": answer.question,
        "topic": answer.topic,
        "body": chosen.body,
        "asked_for": wanted,
        "shown_in": chosen.locale,
        # ⚠ The line the screen shows when these differ. A boolean, not a
        # sentence: the sentence is eleven catalogue lines (B14 rule 35).
        "is_fallback": chosen.locale != wanted,
        "updated_on": (
            answer.last_changed_on.date().isoformat() if answer.last_changed_on else None
        ),
        "also_written_in": also_written_in,
        "related": related,
    }


def attached_answer(tenant_id: Any, screen: str, *, locale: str | None) -> dict[str, Any] | None:
    """The same answer under a bill (`CWP-060`, `also_show_on_screen`).

    ⚠ **ONE FIELD, TWO PLACEMENTS** (`US-CWP-071` §1): the utility writes the
    answer once. Returns `None` when nothing is attached — an empty slot is
    not drawn (`BR-CWP-093`).
    """
    row = (
        content.HelpAnswer.objects.filter(
            tenant_id=tenant_id, status=content.ANSWER_PUBLISHED, also_show_on_screen=screen
        )
        .order_by("position", "created_at")
        .first()
    )
    if row is None:
        return None
    return published_answer(tenant_id, row.slug, locale=locale)


# ══ HELP ANSWERS — writes ══════════════════════════════════════════════════


def _validate_answer(
    tenant_id: Any, payload: dict[str, Any], *, partial: bool
) -> list[dict[str, Any]]:
    field_errors: list[dict[str, Any]] = []
    if not partial or "question" in payload:
        question = (payload.get("question") or "").strip()
        if not question:
            field_errors.append(
                _field_error("question", errors.VAL_REQUIRED, "help.answer.question_required")
            )
    if not partial or "topic" in payload:
        if payload.get("topic") not in ANSWER_TOPICS:
            field_errors.append(
                _field_error("topic", errors.VAL_UNKNOWN_LOOKUP, "help.answer.topic_unknown")
            )
    if "status" in payload and payload["status"] not in content.ANSWER_STATUSES:
        field_errors.append(
            _field_error("status", errors.VAL_UNKNOWN_LOOKUP, "help.answer.status_unknown")
        )
    also = payload.get("also_show_on_screen")
    if "also_show_on_screen" in payload and also not in (None, "", *ALSO_SHOW_SCREENS):
        field_errors.append(
            _field_error(
                "also_show_on_screen", errors.VAL_UNKNOWN_LOOKUP, "help.answer.screen_unknown"
            )
        )
    variants = payload.get("variants")
    if variants is not None:
        if not isinstance(variants, dict):
            field_errors.append(
                _field_error("variants", errors.VAL_FORMAT, "help.answer.variants_not_object")
            )
        else:
            for locale in variants:
                if locale not in content.LOCALES:
                    field_errors.append(
                        _field_error(
                            "variants",
                            errors.VAL_UNKNOWN_LOOKUP,
                            "help.answer.locale_unknown",
                            locale=locale,
                        )
                    )
    return field_errors


def _save_variants(answer: content.HelpAnswer, variants: dict[str, Any], *, now: datetime) -> None:
    """Write the bodies a clerk typed, and leave every other language exactly
    as it was. ⚠ A body that arrives non-empty becomes `published`; emptying one
    puts the language back to `needs_translating` — the state is derived from
    the text, so a utility can never have a language marked published with
    nothing in it."""
    for locale, body in variants.items():
        text = (body or "").strip()
        row, _created = content.HelpAnswerVariant.objects.get_or_create(
            answer=answer,
            locale=locale,
            defaults={
                "tenant_id": answer.tenant_id,
                "body": "",
                "status": content.VARIANT_NEEDS_TRANSLATING,
            },
        )
        row.body = text
        row.status = content.VARIANT_PUBLISHED if text else content.VARIANT_NEEDS_TRANSLATING
        row.last_changed_on = now
        row.save(update_fields=["body", "status", "last_changed_on", "updated_at"])


@require_role(SYSTEM_ADMIN)
def create_answer(actor: Any, tenant_id: Any, payload: dict[str, Any]) -> dict[str, Any]:
    """A new answer, **draft** until somebody publishes it (law 3: the state
    that shows a customer something is the one you have to type)."""
    _refuse(_validate_answer(tenant_id, payload, partial=False), "help.answer.refused")
    now = django_timezone.now()
    with transaction.atomic():
        last = (
            content.HelpAnswer.objects.filter(tenant_id=tenant_id)
            .order_by("-position")
            .values_list("position", flat=True)
            .first()
        )
        answer = content.HelpAnswer.objects.create(
            tenant_id=tenant_id,
            slug=_unique_slug(tenant_id, content.HelpAnswer, _slugify(payload["question"])),
            question=payload["question"].strip(),
            topic=payload["topic"],
            status=content.ANSWER_DRAFT,
            position=(last or 0) + 1,
            also_show_on_screen=payload.get("also_show_on_screen") or None,
            last_changed_by=getattr(actor, "name", None),
            last_changed_on=now,
        )
        # Eleven rows from birth, so the language table is a real picture of
        # what is missing rather than a list that grows as somebody translates.
        content.HelpAnswerVariant.objects.bulk_create(
            [
                content.HelpAnswerVariant(
                    tenant_id=tenant_id,
                    answer=answer,
                    locale=locale,
                    body="",
                    status=content.VARIANT_NEEDS_TRANSLATING,
                )
                for locale in content.LOCALES
            ]
        )
        if payload.get("variants"):
            _save_variants(answer, payload["variants"], now=now)
        _audit_row(
            actor, "help_answer.create", "help_answer", answer.id, None, {"slug": answer.slug}
        )
    return back_office_answer(tenant_id, answer.slug)


@require_role(SYSTEM_ADMIN)
def update_answer(actor: Any, tenant_id: Any, slug: str, payload: dict[str, Any]) -> dict[str, Any]:
    _refuse(_validate_answer(tenant_id, payload, partial=True), "help.answer.refused")
    now = django_timezone.now()
    with transaction.atomic():
        answer = _answer_or_404(tenant_id, slug)
        before = {
            "question": answer.question,
            "topic": answer.topic,
            "status": answer.status,
            "also_show_on_screen": answer.also_show_on_screen,
        }
        for field in ("question", "topic", "status"):
            if field in payload:
                setattr(
                    answer,
                    field,
                    (payload[field] or "").strip() if field == "question" else payload[field],
                )
        if "also_show_on_screen" in payload:
            answer.also_show_on_screen = payload["also_show_on_screen"] or None
        answer.last_changed_by = getattr(actor, "name", None) or answer.last_changed_by
        answer.last_changed_on = now
        answer.save()
        if payload.get("variants"):
            _save_variants(answer, payload["variants"], now=now)
        after = {
            "question": answer.question,
            "topic": answer.topic,
            "status": answer.status,
            "also_show_on_screen": answer.also_show_on_screen,
        }
        _audit_row(actor, "help_answer.update", "help_answer", answer.id, before, after)
    return back_office_answer(tenant_id, answer.slug)


@require_role(SYSTEM_ADMIN)
def publish_answer(actor: Any, tenant_id: Any, slug: str, *, status: str) -> dict[str, Any]:
    """⚠ **PUBLISHING CHANGES WHAT CUSTOMERS READ STRAIGHT AWAY. THERE IS NO
    APPROVAL STEP** (`US-CWP-071` §1, TC-9), and the screen says so. This
    function is the whole of it: one column, one audit row, live.
    """
    if status not in content.ANSWER_STATUSES:
        _refuse(
            [_field_error("status", errors.VAL_UNKNOWN_LOOKUP, "help.answer.status_unknown")],
            "help.answer.refused",
        )
    with transaction.atomic():
        answer = _answer_or_404(tenant_id, slug)
        before = answer.status
        answer.status = status
        answer.last_changed_by = getattr(actor, "name", None) or answer.last_changed_by
        answer.last_changed_on = django_timezone.now()
        answer.save(update_fields=["status", "last_changed_by", "last_changed_on", "updated_at"])
        _audit_row(
            actor,
            "help_answer.publish",
            "help_answer",
            answer.id,
            {"status": before},
            {"status": status},
        )
    return back_office_answer(tenant_id, slug)


@require_role(SYSTEM_ADMIN)
def reorder_answers(actor: Any, tenant_id: Any, slugs: list[str]) -> list[dict[str, Any]]:
    """*The order here is the order on the portal* (`US-CWP-071` TC-5)."""
    if not isinstance(slugs, list) or not all(isinstance(one, str) for one in slugs):
        _refuse(
            [_field_error("order", errors.VAL_FORMAT, "help.answer.order_not_list")],
            "help.answer.refused",
        )
    with transaction.atomic():
        rows = {row.slug: row for row in content.HelpAnswer.objects.filter(tenant_id=tenant_id)}
        unknown = [one for one in slugs if one not in rows]
        if unknown:
            raise errors.deny_as_not_found("BR-CWP-005")
        for index, slug in enumerate(slugs, start=1):
            row = rows[slug]
            if row.position != index:
                row.position = index
                row.save(update_fields=["position", "updated_at"])
        _audit_row(actor, "help_answer.reorder", "help_answer", tenant_id, None, {"order": slugs})
    return back_office_answers(tenant_id)


@require_role(SYSTEM_ADMIN)
def delete_answer(actor: Any, tenant_id: Any, slug: str) -> None:
    with transaction.atomic():
        answer = _answer_or_404(tenant_id, slug)
        _audit_row(
            actor,
            "help_answer.delete",
            "help_answer",
            answer.id,
            {"slug": slug, "question": answer.question},
            None,
        )
        answer.delete()


def record_feedback(tenant_id: Any, slug: str, *, event: str, locale: str | None) -> dict[str, Any]:
    """`POST /public/help/{slug}/feedback` — a read, or a vote.

    ⚠ **A READ AND A VOTE ARE COUNTED SEPARATELY** (`CP-34`, `US-CWP-072`
    TC-4): pressing *No* is not the same event as opening the page, and the
    schema keeps them apart so the two can never be added together by accident.

    ⚠ **NO PERSON IS RECORDED** (`BR-CWP-021`): the row carries the answer, the
    language it was read in, the event and the day — no customer, no account,
    no session, no address.

    ⚠ **AND THIS WRITE IS NOT ONE OF `BR-CWP-001`'S FOUR, WHICH IS WHY IT LIVES
    HERE AND NOT IN `apps/portal`.** `help_answer_feedback` is a **tenancy**
    table (`03-field-map.md` §2) and B2 §2 forbids a cross-module write, so the
    portal could never write it wherever the endpoint was mounted; `G81` holds
    that line file by file. The four kinds `BR-CWP-001` names are all rows
    about a customer's account — a payment, a request, a reading, a preference
    — and this row is about a published paragraph. See the decision log,
    2026-09-04, and `DEF-CWP-3646` for the two documents that disagreed.
    """
    if event not in content.FEEDBACK_EVENTS:
        _refuse(
            [_field_error("event", errors.VAL_UNKNOWN_LOOKUP, "help.feedback.event_unknown")],
            "help.feedback.refused",
        )
    answer = content.HelpAnswer.objects.filter(
        tenant_id=tenant_id, slug=slug, status=content.ANSWER_PUBLISHED
    ).first()
    if answer is None:
        raise errors.deny_as_not_found("BR-CWP-094")
    content.HelpAnswerFeedback.objects.create(
        tenant_id=tenant_id,
        answer=answer,
        locale=(locale or content.FALLBACK_LOCALE),
        event=event,
        occurred_on=_tenant_today(tenant_id),
    )
    return {"recorded": True}


# ══ TIPS ═══════════════════════════════════════════════════════════════════


def _in_season(row: content.Tip, month: int) -> bool:
    """Null months mean all year. A range that wraps the new year (Dec–Feb) is
    inside-out on purpose and is read that way."""
    if row.month_from is None or row.month_to is None:
        return True
    if row.month_from <= row.month_to:
        return row.month_from <= month <= row.month_to
    return month >= row.month_from or month <= row.month_to


def back_office_tips(tenant_id: Any) -> list[dict[str, Any]]:
    """`CWP-073`'s list — every tip, showing or not, with **why** each one is
    not showing. `US-CWP-073` TC-3: the freeze tip is off **and** out of season,
    *"for two independent reasons"*, and the screen shows both."""
    today = _tenant_today(tenant_id)
    rows = content.Tip.objects.filter(tenant_id=tenant_id).order_by("position", "created_at")
    out = []
    for row in rows:
        in_season = _in_season(row, today.month)
        out.append(
            {
                "id": str(row.id),
                "text": row.text,
                "target_screen": row.target_screen,
                "month_from": row.month_from,
                "month_to": row.month_to,
                "is_on": row.is_on,
                "position": row.position,
                "in_season": in_season,
                "showing_today": bool(row.is_on and in_season),
                "word_count": len(row.text.split()),
                "word_guidance": content.TIP_WORD_GUIDANCE,
            }
        )
    return out


def tip_for_screen(tenant_id: Any, screen: str) -> dict[str, Any] | None:
    """`GET /public/tips?screen=` — `BR-CWP-095`, verbatim: *"A tip shows only
    when it is **On and today falls inside its month range**. **One tip per
    screen**; where two match, the top of the list wins."*

    ⚠ **AND AN EMPTY ANSWER IS A NORMAL ANSWER.** `None` here is not an error,
    not a 404 and not a frame to fill: the slot closes up and nobody can tell it
    was there (`BR-CWP-093`, `US-CWP-073` TC-3).

    The season test is done in Python and not in SQL for one reason worth
    naming: a Dec–Feb range wraps the year, and `month_from <= m <= month_to`
    is FALSE for every month in that case. The set is a handful of rows per
    tenant, so the filter that matters — tenant, screen, `is_on` — is in the
    query and the wrap is read afterwards.
    """
    rows = content.Tip.objects.filter(
        tenant_id=tenant_id, target_screen=screen, is_on=True
    ).order_by("position", "created_at")
    month = _tenant_today(tenant_id).month
    for row in rows:
        if _in_season(row, month):
            return {"text": row.text, "target_screen": row.target_screen}
    return None


def _validate_tip(payload: dict[str, Any], *, partial: bool) -> list[dict[str, Any]]:
    field_errors: list[dict[str, Any]] = []
    if not partial or "text" in payload:
        if not (payload.get("text") or "").strip():
            field_errors.append(_field_error("text", errors.VAL_REQUIRED, "tip.text_required"))
    if not partial or "target_screen" in payload:
        if payload.get("target_screen") not in TIP_SCREENS:
            field_errors.append(
                _field_error("target_screen", errors.VAL_UNKNOWN_LOOKUP, "tip.screen_unknown")
            )
    for key in ("month_from", "month_to"):
        if key in payload and payload[key] is not None:
            value = payload[key]
            if not isinstance(value, int) or not 1 <= value <= 12:
                field_errors.append(_field_error(key, errors.VAL_RANGE, "tip.month_out_of_range"))
    return field_errors


@require_role(SYSTEM_ADMIN)
def create_tip(actor: Any, tenant_id: Any, payload: dict[str, Any]) -> list[dict[str, Any]]:
    """⚠ A THIRTY-WORD TIP IS ACCEPTED AND FLAGGED, never refused
    (`US-CWP-073` TC-7) — *"the rule is on the screen, not in a policy
    document"*. `back_office_tips` returns the word count beside the guidance
    and `CWP-073` draws the flag."""
    _refuse(_validate_tip(payload, partial=False), "tip.refused")
    with transaction.atomic():
        last = (
            content.Tip.objects.filter(tenant_id=tenant_id)
            .order_by("-position")
            .values_list("position", flat=True)
            .first()
        )
        row = content.Tip.objects.create(
            tenant_id=tenant_id,
            text=payload["text"].strip(),
            target_screen=payload["target_screen"],
            month_from=payload.get("month_from"),
            month_to=payload.get("month_to"),
            is_on=bool(payload.get("is_on", True)),
            position=(last or 0) + 1,
        )
        _audit_row(actor, "tip.create", "tip", row.id, None, {"text": row.text})
    return back_office_tips(tenant_id)


@require_role(SYSTEM_ADMIN)
def update_tip(
    actor: Any, tenant_id: Any, tip_id: str, payload: dict[str, Any]
) -> list[dict[str, Any]]:
    _refuse(_validate_tip(payload, partial=True), "tip.refused")
    with transaction.atomic():
        row = content.Tip.objects.filter(tenant_id=tenant_id, pk=tip_id).first()
        if row is None:
            raise errors.deny_as_not_found("BR-CWP-005")
        before = {
            "text": row.text,
            "is_on": row.is_on,
            "month_from": row.month_from,
            "month_to": row.month_to,
        }
        if "text" in payload:
            row.text = (payload["text"] or "").strip()
        if "target_screen" in payload:
            row.target_screen = payload["target_screen"]
        for key in ("month_from", "month_to"):
            if key in payload:
                setattr(row, key, payload[key])
        if "is_on" in payload:
            row.is_on = bool(payload["is_on"])
        row.save()
        after = {
            "text": row.text,
            "is_on": row.is_on,
            "month_from": row.month_from,
            "month_to": row.month_to,
        }
        _audit_row(actor, "tip.update", "tip", row.id, before, after)
    return back_office_tips(tenant_id)


@require_role(SYSTEM_ADMIN)
def reorder_tips(actor: Any, tenant_id: Any, ids: list[str]) -> list[dict[str, Any]]:
    """*Top of the list wins where two match* (`US-CWP-073` TC-9)."""
    with transaction.atomic():
        rows = {str(row.id): row for row in content.Tip.objects.filter(tenant_id=tenant_id)}
        if any(one not in rows for one in ids):
            raise errors.deny_as_not_found("BR-CWP-005")
        for index, one in enumerate(ids, start=1):
            row = rows[one]
            if row.position != index:
                row.position = index
                row.save(update_fields=["position", "updated_at"])
        _audit_row(actor, "tip.reorder", "tip", tenant_id, None, {"order": ids})
    return back_office_tips(tenant_id)


@require_role(SYSTEM_ADMIN)
def delete_tip(actor: Any, tenant_id: Any, tip_id: str) -> list[dict[str, Any]]:
    with transaction.atomic():
        row = content.Tip.objects.filter(tenant_id=tenant_id, pk=tip_id).first()
        if row is None:
            raise errors.deny_as_not_found("BR-CWP-005")
        _audit_row(actor, "tip.delete", "tip", row.id, {"text": row.text}, None)
        row.delete()
    return back_office_tips(tenant_id)


# ══ SERVICE CENTRES ════════════════════════════════════════════════════════


def _hours_rows(centre: content.ServiceCentre) -> list[dict[str, Any]]:
    by_day = {row.day_of_week: row for row in centre.hours.all()}
    rows = []
    for day in range(7):
        row = by_day.get(day)
        rows.append(
            {
                "day_of_week": day,
                "is_closed": True if row is None else row.is_closed,
                "opens_at": _hhmm(row.opens_at) if row else None,
                "closes_at": _hhmm(row.closes_at) if row else None,
            }
        )
    return rows


def _holidays(tenant_id: Any, *, frm: date, to: date) -> list[tenancy_models.HolidayCalendar]:
    """`BR-CWP-096`, verbatim: *"Holiday closures come from the tenant's
    existing holiday calendar, typed by nobody."* This is that read — the same
    `holiday_calendars` rows Reference data already keeps, and there is no
    second list anywhere in this module."""
    return list(
        tenancy_models.HolidayCalendar.objects.filter(
            tenant_id=tenant_id, holiday_date__gte=frm, holiday_date__lte=to
        ).order_by("holiday_date")
    )


def centre_today(tenant_id: Any, centre: content.ServiceCentre, *, now: datetime) -> dict[str, Any]:
    """Is it open, and if not, when does it open next — **computed from the
    clock and the hours**, never typed.

    `US-CWP-074` TC-2: the north counter opens Tuesday and Thursday; on a
    Wednesday the screen must read *"Closed today · Opens **Thursday** at
    9:00am"*. ⚠ **The wireframe `CWP-014.png` says *Tuesday*, and a screen
    showing Tuesday on a Wednesday has typed the day** — `DEF-CWP-3604`.

    ⚠ **AND A HOLIDAY CLOSES IT WITH NOBODY EDITING ANYTHING** (TC-3): the
    walk forward skips every date in the tenant's holiday calendar, so on 26
    November both centres read closed and the next opening is the day after.

    RETURNS FACTS, NOT A SENTENCE (B14 rule 35): a weekday number, an `HH:MM`,
    a holiday label. The screen writes the sentence, in its own language.
    """
    today = now.date()
    clock = now.time()
    hours = {row.day_of_week: row for row in centre.hours.all()}
    holidays = {
        row.holiday_date: row.label
        for row in _holidays(tenant_id, frm=today, to=today + timedelta(days=14))
    }

    def open_row(day: date):
        row = hours.get(day.weekday())
        if row is None or row.is_closed or row.opens_at is None or row.closes_at is None:
            return None
        if day in holidays:
            return None
        return row

    todays = open_row(today)
    is_open_now = bool(todays and todays.opens_at <= clock < todays.closes_at)
    opens_later_today = bool(todays and clock < todays.opens_at)

    next_day: date | None = None
    next_row = None
    start = today if opens_later_today else today + timedelta(days=1)
    for offset in range(0, 14):
        day = start + timedelta(days=offset)
        row = open_row(day)
        if row is not None:
            next_day, next_row = day, row
            break

    upcoming = _holidays(tenant_id, frm=today, to=today + timedelta(days=120))
    return {
        "is_open_now": is_open_now,
        "closes_at": _hhmm(todays.closes_at) if is_open_now and todays else None,
        "opens_later_today": opens_later_today,
        "next_open_date": next_day.isoformat() if next_day else None,
        "next_open_weekday": next_day.weekday() if next_day else None,
        "next_open_is_today": bool(next_day and next_day == today),
        "next_open_at": _hhmm(next_row.opens_at) if next_row else None,
        # ⚠ Why it is shut, when the reason is the calendar and not the week.
        "closed_for_holiday": (
            {"date": today.isoformat(), "label": holidays[today]} if today in holidays else None
        ),
        "next_holiday": (
            {"date": upcoming[0].holiday_date.isoformat(), "label": upcoming[0].label}
            if upcoming
            else None
        ),
    }


def shown_centre_count(tenant_id: Any) -> int:
    """`BR-CWP-093`: *Visit us* exists only when this is above zero."""
    return content.ServiceCentre.objects.filter(
        tenant_id=tenant_id, is_shown_to_customers=True
    ).count()


def public_centres(tenant_id: Any) -> list[dict[str, Any]]:
    """`GET /public/service-centres` — `BR-CWP-096`: only the ones marked
    *shown to customers*. The depot is absent here and **still in the
    back-office list below**.

    ⚠ Raises 404 when none is shown, so the page cannot exist empty
    (`BR-CWP-093`, `US-CWP-074` TC-5). An empty list rendered as a page with a
    heading and nothing under it is precisely what that rule forbids.
    """
    now = _tenant_now(tenant_id)
    rows = (
        content.ServiceCentre.objects.filter(tenant_id=tenant_id, is_shown_to_customers=True)
        .prefetch_related("hours")
        .order_by("position", "created_at")
    )
    centres = list(rows)
    if not centres:
        raise errors.deny_as_not_found("BR-CWP-093")
    return [
        {
            "slug": row.slug,
            "name": row.name,
            "address": row.address,
            "phone": row.phone,
            "directions_note": row.directions_note,
            "allowed_actions": list(row.allowed_actions or []),
            "cannot_do": [one for one in CENTRE_ACTIONS if one not in (row.allowed_actions or [])],
            "payment_methods_accepted": list(row.payment_methods_accepted or []),
            "hours": _hours_rows(row),
            "today": centre_today(tenant_id, row, now=now),
        }
        for row in centres
    ]


def public_centre(tenant_id: Any, slug: str) -> dict[str, Any]:
    """`GET /public/service-centres/{slug}` — `CWP-014`.

    ⚠ **FOUR OF FIVE ROWS SAYING NO IS THE SCREEN DOING ITS JOB**
    (`US-CWP-074` TC-4) — so `cannot_do` is computed here and travels, rather
    than being left for a screen to infer from an absence.
    """
    row = (
        content.ServiceCentre.objects.filter(
            tenant_id=tenant_id, slug=slug, is_shown_to_customers=True
        )
        .prefetch_related("hours")
        .first()
    )
    if row is None:
        raise errors.deny_as_not_found("BR-CWP-096")
    now = _tenant_now(tenant_id)
    return {
        "slug": row.slug,
        "name": row.name,
        "address": row.address,
        "phone": row.phone,
        "directions_note": row.directions_note,
        "allowed_actions": list(row.allowed_actions or []),
        "cannot_do": [one for one in CENTRE_ACTIONS if one not in (row.allowed_actions or [])],
        "all_actions": list(CENTRE_ACTIONS),
        "payment_methods_accepted": list(row.payment_methods_accepted or []),
        "hours": _hours_rows(row),
        "today": centre_today(tenant_id, row, now=now),
    }


def back_office_centres(tenant_id: Any) -> list[dict[str, Any]]:
    """`CWP-074` — **every** centre, the hidden ones included. That is the
    whole of `BR-CWP-096`: hidden is a state, not a deletion, and the depot is
    still here."""
    now = _tenant_now(tenant_id)
    rows = (
        content.ServiceCentre.objects.filter(tenant_id=tenant_id)
        .prefetch_related("hours")
        .order_by("position", "created_at")
    )
    return [
        {
            "slug": row.slug,
            "name": row.name,
            "address": row.address,
            "phone": row.phone,
            "directions_note": row.directions_note,
            "allowed_actions": list(row.allowed_actions or []),
            "payment_methods_accepted": list(row.payment_methods_accepted or []),
            "is_shown_to_customers": row.is_shown_to_customers,
            "position": row.position,
            "hours": _hours_rows(row),
            "today": centre_today(tenant_id, row, now=now),
            "last_changed_on": row.last_changed_on.isoformat() if row.last_changed_on else None,
        }
        for row in rows
    ]


def back_office_centre(tenant_id: Any, slug: str) -> dict[str, Any]:
    """`CWP-075`'s editor."""
    row = (
        content.ServiceCentre.objects.filter(tenant_id=tenant_id, slug=slug)
        .prefetch_related("hours")
        .first()
    )
    if row is None:
        raise errors.deny_as_not_found("BR-CWP-005")
    return {
        "slug": row.slug,
        "name": row.name,
        "address": row.address,
        "phone": row.phone,
        "directions_note": row.directions_note,
        "allowed_actions": list(row.allowed_actions or []),
        "all_actions": list(CENTRE_ACTIONS),
        "payment_methods_accepted": list(row.payment_methods_accepted or []),
        "all_payment_methods": list(CENTRE_PAYMENT_METHODS),
        "is_shown_to_customers": row.is_shown_to_customers,
        "position": row.position,
        "hours": _hours_rows(row),
        "last_changed_on": row.last_changed_on.isoformat() if row.last_changed_on else None,
    }


def _validate_centre(payload: dict[str, Any], *, partial: bool) -> list[dict[str, Any]]:
    field_errors: list[dict[str, Any]] = []
    for field, key in (("name", "centre.name_required"), ("address", "centre.address_required")):
        if (not partial or field in payload) and not (payload.get(field) or "").strip():
            field_errors.append(_field_error(field, errors.VAL_REQUIRED, key))
    for field, allowed, key in (
        ("allowed_actions", CENTRE_ACTIONS, "centre.action_unknown"),
        ("payment_methods_accepted", CENTRE_PAYMENT_METHODS, "centre.method_unknown"),
    ):
        if field in payload:
            value = payload[field]
            if not isinstance(value, list) or any(one not in allowed for one in value):
                field_errors.append(_field_error(field, errors.VAL_UNKNOWN_LOOKUP, key))
    hours = payload.get("hours")
    if hours is not None:
        if not isinstance(hours, list):
            field_errors.append(_field_error("hours", errors.VAL_FORMAT, "centre.hours_not_list"))
        else:
            for row in hours:
                if not isinstance(row, dict) or not isinstance(row.get("day_of_week"), int):
                    field_errors.append(
                        _field_error("hours", errors.VAL_FORMAT, "centre.hours_not_list")
                    )
                    break
                if not 0 <= row["day_of_week"] <= 6:
                    field_errors.append(
                        _field_error("hours", errors.VAL_RANGE, "centre.day_out_of_range")
                    )
                    break
    return field_errors


def _parse_time(value: Any) -> time | None:
    if not value:
        return None
    try:
        hour, minute = str(value).split(":")[:2]
        return time(int(hour), int(minute))
    except (ValueError, TypeError):
        raise errors.ValidationError(
            errors.VAL_FORMAT,
            message_key="centre.refused",
            field_errors=[_field_error("hours", errors.VAL_FORMAT, "centre.time_not_readable")],
        )


def _save_hours(centre: content.ServiceCentre, hours: list[dict[str, Any]]) -> None:
    for row in hours:
        opens = _parse_time(row.get("opens_at"))
        closes = _parse_time(row.get("closes_at"))
        closed = bool(row.get("is_closed", opens is None or closes is None))
        obj, _created = content.ServiceCentreHour.objects.get_or_create(
            centre=centre,
            day_of_week=row["day_of_week"],
            defaults={"tenant_id": centre.tenant_id, "is_closed": True},
        )
        obj.opens_at = None if closed else opens
        obj.closes_at = None if closed else closes
        obj.is_closed = closed
        obj.save(update_fields=["opens_at", "closes_at", "is_closed", "updated_at"])


@require_role(SYSTEM_ADMIN)
def create_centre(actor: Any, tenant_id: Any, payload: dict[str, Any]) -> dict[str, Any]:
    """A new centre, **hidden** until somebody shows it (law 3: the unsafe
    option — publishing an address customers will drive to — is the one you
    have to type)."""
    _refuse(_validate_centre(payload, partial=False), "centre.refused")
    with transaction.atomic():
        last = (
            content.ServiceCentre.objects.filter(tenant_id=tenant_id)
            .order_by("-position")
            .values_list("position", flat=True)
            .first()
        )
        centre = content.ServiceCentre.objects.create(
            tenant_id=tenant_id,
            slug=_unique_slug(tenant_id, content.ServiceCentre, _slugify(payload["name"])),
            name=payload["name"].strip(),
            address=payload["address"].strip(),
            phone=(payload.get("phone") or None),
            directions_note=(payload.get("directions_note") or None),
            allowed_actions=list(payload.get("allowed_actions") or []),
            payment_methods_accepted=list(payload.get("payment_methods_accepted") or []),
            is_shown_to_customers=bool(payload.get("is_shown_to_customers", False)),
            position=(last or 0) + 1,
            last_changed_on=django_timezone.now(),
        )
        if payload.get("hours"):
            _save_hours(centre, payload["hours"])
        _audit_row(
            actor, "service_centre.create", "service_centre", centre.id, None, {"slug": centre.slug}
        )
    return back_office_centre(tenant_id, centre.slug)


@require_role(SYSTEM_ADMIN)
def update_centre(actor: Any, tenant_id: Any, slug: str, payload: dict[str, Any]) -> dict[str, Any]:
    _refuse(_validate_centre(payload, partial=True), "centre.refused")
    with transaction.atomic():
        centre = content.ServiceCentre.objects.filter(tenant_id=tenant_id, slug=slug).first()
        if centre is None:
            raise errors.deny_as_not_found("BR-CWP-005")
        before = {
            "name": centre.name,
            "is_shown_to_customers": centre.is_shown_to_customers,
            "allowed_actions": list(centre.allowed_actions or []),
        }
        for field in ("name", "address"):
            if field in payload:
                setattr(centre, field, (payload[field] or "").strip())
        for field in ("phone", "directions_note"):
            if field in payload:
                setattr(centre, field, payload[field] or None)
        for field in ("allowed_actions", "payment_methods_accepted"):
            if field in payload:
                setattr(centre, field, list(payload[field] or []))
        if "is_shown_to_customers" in payload:
            centre.is_shown_to_customers = bool(payload["is_shown_to_customers"])
        if "position" in payload and isinstance(payload["position"], int):
            centre.position = payload["position"]
        centre.last_changed_on = django_timezone.now()
        centre.save()
        if payload.get("hours"):
            _save_hours(centre, payload["hours"])
        after = {
            "name": centre.name,
            "is_shown_to_customers": centre.is_shown_to_customers,
            "allowed_actions": list(centre.allowed_actions or []),
        }
        _audit_row(actor, "service_centre.update", "service_centre", centre.id, before, after)
    return back_office_centre(tenant_id, centre.slug)


@require_role(SYSTEM_ADMIN)
def delete_centre(actor: Any, tenant_id: Any, slug: str) -> None:
    """⚠ **PREFER HIDING** (`US-CWP-074` TC-9). Removal is the danger tier on
    the screen and warns that a printed address may still be in circulation;
    this function is what that button calls, and it is deliberately the only
    way a centre leaves the list."""
    with transaction.atomic():
        centre = content.ServiceCentre.objects.filter(tenant_id=tenant_id, slug=slug).first()
        if centre is None:
            raise errors.deny_as_not_found("BR-CWP-005")
        _audit_row(
            actor,
            "service_centre.delete",
            "service_centre",
            centre.id,
            {"slug": slug, "name": centre.name, "address": centre.address},
            None,
        )
        centre.delete()


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-CWP-071 · US-CWP-072 · US-CWP-073 · US-CWP-074 (EP-CWP-12 + BR-CWP-093..096 verbatim)
# generated: 2026-09-04 by the CR-068 wave D build lane
# checklist: A✔ B✔ C✔ D✔(published_content_api.py) E✔(CWP-071..075 · CWP-011/060/013/014) F✔ G✔ H=n/a(no 🔒 path in this file)
# gates: pytest tests/test_us_cwp_071_help.py tests/test_us_cwp_072_help_portal.py tests/test_us_cwp_073_tips.py tests/test_us_cwp_074_centres.py · G88 · G9 error envelope
# exceptions: OQ-1398 bounds the WORKFLOW and not the mechanism — stated at the top of this module and on no screen
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
