# ── Trace ──────────────────────────────────────────────
# Story:    US-CWP-071 §4 (eight answers) · US-CWP-072 §4 · US-CWP-073 §4 (six
#           tips) · US-CWP-074 §4 (three centres, one hidden, and Thanksgiving)
# Rules:    10-execution-plan.md D4 *fixture* · CLAUDE.md prime directive
#           (every write goes through the owning module — this file IS the
#           owning module) · G4/G61 (no Brazos Bend figure moves: this content
#           is seeded onto the portal's own tenants and nowhere else)
# Tests:    06-backend/tests/test_us_cwp_071_help.py and the three beside it
#           build their tenants from these same payloads
# Impacts:  apps/portal/sample_data.py (calls `seed_published_content`) ·
#           10-scripts/render-checks/cr068-d-help-tips-centres.mjs
# ───────────────────────────────────────────────────────
"""The wave D demo content — Pine Hill's eight answers, six tips, three centres.

⚠ **THE FIGURES ARE THE STORIES', NOT THIS FILE'S.** `1,204` reads on *"Why is
my bill higher than last month?"*, `842` on *"What does estimated mean"*, three
centres of which the depot is hidden, Thanksgiving on 26 November — every one
of them is quoted from a story's §4 and none is invented here.

⚠ **THE READ COUNT IS A REAL COUNT, NOT A STORED NUMBER.** *Read this month* is
`COUNT(*)` over `help_answer_feedback` rows with `event = 'read'`, so seeding it
means writing 4,365 rows and the demo's `1,204 → 1,207` is arithmetic the
product actually does. A column holding `1204` would have made step 4 of the
demo untestable — the three opens would have had nowhere to land.

⚠ **AND THE BILL-HIGHER ANSWER IS PUBLISHED IN TEN LANGUAGES, NOT ELEVEN.**
`US-CWP-071` §4 says *"11 langs"* and `US-CWP-072` §4 says *"published in
English, Español (México), हिंदी and eight more, **not yet in Français**"*. Both
are true of the same answer: eleven language ROWS exist and ten of them carry
text, so `Français` reads `NEEDS TRANSLATING` — which is what the wave's demo
script shows on `CWP-072` and what makes the French fallback on `CWP-011`
demonstrable at all. Read *"11 langs"* as *"has all eleven rows"*.
"""

from __future__ import annotations

from datetime import date, timedelta
from types import SimpleNamespace
from typing import Any


from apps.tenancy import models as tenancy_models
from apps.tenancy import published_content
from apps.tenancy import published_content_models as content
from core.permissions import SYSTEM_ADMIN

#: The eight answers of `US-CWP-071` §4, in the order the drawing lists them —
#: which is the order on the portal, because position IS the order.
ANSWERS: tuple[dict[str, Any], ...] = (
    {
        "question": "Why is my bill higher than last month?",
        "topic": "billing",
        "status": content.ANSWER_PUBLISHED,
        "also_show_on_screen": "bill",
        "reads": 1204,
        # ⚠ Ten of eleven. `fr-FR` is deliberately absent — see the docstring.
        "translated": [c for c in content.LOCALES if c != "fr-FR"],
    },
    {
        "question": 'What does "estimated" mean on my bill?',
        "topic": "readings",
        "status": content.ANSWER_PUBLISHED,
        "reads": 842,
        "translated": list(content.LOCALES),
    },
    {
        "question": "How do I check for a leak?",
        "topic": "water",
        "status": content.ANSWER_PUBLISHED,
        "reads": 790,
        "translated": ["en", "es-MX"],
    },
    {
        "question": "When is my meter read?",
        "topic": "readings",
        "status": content.ANSWER_DRAFT,
        "reads": 0,
        "translated": ["en"],
    },
    {
        "question": "Can I pay in instalments?",
        "topic": "paying",
        "status": content.ANSWER_PUBLISHED,
        "reads": 611,
        "translated": list(content.LOCALES),
    },
    {
        "question": "What happens if I pay late?",
        "topic": "paying",
        "status": content.ANSWER_PUBLISHED,
        "reads": 508,
        "translated": list(content.LOCALES),
    },
    {
        "question": "How do I close my account?",
        "topic": "moving",
        "status": content.ANSWER_PUBLISHED,
        "reads": 410,
        "translated": ["en", "es-MX"],
    },
    {
        "question": "Who is responsible for the pipe outside?",
        "topic": "water",
        "status": content.ANSWER_NOT_SHOWN,
        "reads": 0,
        "translated": ["en"],
    },
)

#: The answer bodies, per language. Written to be READ by a customer — plain,
#: short, ending somewhere a person can go (blueprint `P46`: *"an answer that
#: describes a screen without linking to it is a help page written for a filing
#: cabinet"*). ⚠ NATIVE-REVIEW-OWED for every language but English (B14 rule
#: 35): these were not written by native speakers and say so rather than
#: implying eleven fluent authors.
BODIES: dict[str, dict[str, str]] = {
    "Why is my bill higher than last month?": {
        "en": (
            "Most of the time it is one of three things: you used more water, "
            "the bill covers more days, or the last reading was an estimate and "
            "this one is real. Compare the used figure with last month's — if "
            "the jump is large and nothing changed at home, it is worth checking "
            "for a leak before you pay."
        ),
        "es-MX": (
            "Casi siempre son tres cosas: gastaste más agua, el recibo abarca "
            "más días, o la lectura anterior fue estimada y ésta ya es real. "
            "Compara el consumo con el del mes pasado; si subió mucho y en casa "
            "nada cambió, revisa si hay una fuga antes de pagar."
        ),
        "es": (
            "Casi siempre son tres cosas: has gastado más agua, la factura "
            "abarca más días, o la lectura anterior era estimada y ésta ya es "
            "real. Compara el consumo con el del mes pasado; si ha subido mucho "
            "y en casa no ha cambiado nada, mira si hay una fuga antes de pagar."
        ),
        "de": (
            "Meistens sind es drei Dinge: mehr Verbrauch, ein längerer "
            "Abrechnungszeitraum, oder der letzte Zählerstand war geschätzt und "
            "dieser ist abgelesen. Vergleichen Sie den Verbrauch mit dem "
            "Vormonat. Ist der Sprung groß und zu Hause hat sich nichts "
            "geändert, prüfen Sie vor dem Bezahlen, ob irgendwo Wasser läuft."
        ),
        "hi": (
            "आम तौर पर तीन वजहें होती हैं: पानी ज़्यादा खर्च हुआ, बिल में दिन ज़्यादा जुड़े, "
            "या पिछली रीडिंग अनुमान की थी और यह असली है। पिछले महीने की खपत से "
            "मिलाकर देखिए। अगर फ़र्क़ बड़ा है और घर में कुछ नहीं बदला, तो बिल भरने से "
            "पहले लीकेज ज़रूर देख लें।"
        ),
        "id-ID": (
            "Biasanya karena tiga hal: pemakaian air memang naik, tagihan "
            "mencakup lebih banyak hari, atau angka meteran bulan lalu masih "
            "perkiraan sedangkan yang ini sudah dibaca. Bandingkan dulu dengan "
            "pemakaian bulan lalu. Kalau selisihnya besar padahal di rumah tidak "
            "ada yang berubah, cek dulu kebocoran sebelum membayar."
        ),
        "it-IT": (
            "Di solito dipende da tre cose: hai consumato di più, la bolletta "
            "copre più giorni, oppure la lettura precedente era stimata e questa "
            "è reale. Confronta il consumo con quello del mese scorso: se la "
            "differenza è grande e in casa non è cambiato nulla, conviene "
            "controllare se c'è una perdita prima di pagare."
        ),
        "ja-JP": (
            "原因はたいてい三つです。使用量が増えた、請求対象の日数が多い、"
            "前回が推定検針で今回が実測、のいずれかです。まず先月の使用量と"
            "見比べてください。差が大きく、暮らしぶりに変わりがなければ、"
            "お支払いの前に水漏れをご確認ください。"
        ),
        "ko-KR": (
            "보통 세 가지 중 하나입니다. 사용량이 늘었거나, 청구 기간이 길거나, "
            "지난달이 추정 검침이고 이번이 실제 검침인 경우입니다. 먼저 지난달 "
            "사용량과 비교해 보세요. 차이가 큰데 집안에 달라진 것이 없다면 납부 "
            "전에 누수부터 확인하시는 것이 좋습니다."
        ),
        "pt-BR": (
            "Quase sempre são três coisas: você gastou mais água, a conta pegou "
            "mais dias, ou a leitura passada foi estimada e esta é a real. "
            "Compare o consumo com o do mês passado. Se a diferença for grande e "
            "nada mudou em casa, vale procurar vazamento antes de pagar."
        ),
        "fr-FR": "",  # ⚠ deliberately empty — NEEDS TRANSLATING, and visible
    },
}

#: Every other answer gets one short body per language it is translated into.
#: Kept deliberately plain: the wave is about the MECHANISM — publish, fall
#: back, count — and a fixture is not the place to invent a utility's voice.
GENERIC_BODY: dict[str, str] = {
    "en": "Ask us and we will explain it — the office is open weekdays, and this page can send us the question.",
    "es-MX": "Pregúntanos y te lo explicamos: la oficina abre entre semana y desde aquí puedes mandarnos la duda.",
    "es": "Pregúntanos y te lo explicamos: la oficina abre entre semana y desde aquí puedes enviarnos la duda.",
    "de": "Fragen Sie uns — das Büro ist werktags geöffnet, und über diese Seite erreicht uns Ihre Frage.",
    "fr-FR": "Posez-nous la question : le bureau est ouvert en semaine, et cette page nous transmet votre message.",
    "hi": "हमसे पूछ लीजिए — दफ़्तर सोमवार से शुक्रवार खुला रहता है, और यहीं से आप सवाल भेज सकते हैं।",
    "id-ID": "Tanyakan saja kepada kami. Kantor buka hari kerja, dan pertanyaan bisa dikirim langsung dari halaman ini.",
    "it-IT": "Chiedicelo pure: l'ufficio è aperto nei giorni feriali e da questa pagina puoi mandarci la domanda.",
    "ja-JP": "お気軽にお尋ねください。窓口は平日に開いており、このページからご質問をお送りいただけます。",
    "ko-KR": "편하게 문의해 주세요. 사무실은 평일에 열며, 이 페이지에서 바로 질문을 보내실 수 있습니다.",
    "pt-BR": "Pode perguntar: o escritório abre nos dias úteis e por esta página dá para mandar a dúvida.",
}

#: `US-CWP-073` §4, in the order the drawing lists them. ⚠ SIX TIPS ON SIX
#: SCREENS: *"Usage looks high"* and *"Usage"* are two different screens, which
#: is why both an all-year tip and a seasonal one can be ON without either
#: hiding the other (`BR-CWP-095` is one tip per SCREEN).
TIPS: tuple[dict[str, Any], ...] = (
    {
        "text": "A running toilet can use 4,000 gallons a month.",
        "target_screen": "usage_looks_high",
        "is_on": True,
    },
    {
        "text": "Read the dials left to right, and ignore the red ones.",
        "target_screen": "send_a_reading",
        "is_on": True,
    },
    {
        "text": "Ask for a plan before the due date and late fees stop.",
        "target_screen": "overdue",
        "is_on": True,
    },
    {
        "text": "Watering before 10am loses less to evaporation.",
        "target_screen": "usage",
        "month_from": 6,
        "month_to": 9,
        "is_on": True,
    },
    {
        # ⚠ OFF **and** out of season — two independent reasons (TC-3), and the
        # portal home shows no tip container at all.
        "text": "Leave a tap dripping overnight when it freezes.",
        "target_screen": "portal_home",
        "month_from": 12,
        "month_to": 2,
        "is_on": False,
    },
    {
        "text": "Your meter is yours to read any time — it is not locked.",
        "target_screen": "every_reading",
        "is_on": True,
    },
)

#: `US-CWP-074` §4. ⚠ Hours are Monday=0 … Sunday=6 (`date.weekday()`).
CENTRES: tuple[dict[str, Any], ...] = (
    {
        "name": "Main office",
        "address": "214 Cedar St, Austin TX 78702",
        "phone": "(512) 555-0148",
        "directions_note": "Parking behind the building, off the alley.",
        "allowed_actions": list(published_content.CENTRE_ACTIONS),
        "payment_methods_accepted": ["cash", "cheque", "card", "money_order"],
        "is_shown_to_customers": True,
        "hours": [
            {"day_of_week": day, "opens_at": "08:00", "closes_at": "17:00", "is_closed": False}
            for day in range(0, 5)
        ]
        + [{"day_of_week": 5, "is_closed": True}, {"day_of_week": 6, "is_closed": True}],
    },
    {
        "name": "North counter",
        "address": "1190 Palm Ct, Austin TX 78758",
        "phone": "(512) 555-0148",
        "directions_note": "Inside the community centre, first door on the right.",
        # ⚠ ONE of five. Four rows say NO, and that is the screen doing its job.
        "allowed_actions": ["pay_a_bill"],
        "payment_methods_accepted": ["cash", "cheque"],  # no card machine
        "is_shown_to_customers": True,
        "hours": [
            {"day_of_week": 1, "opens_at": "09:00", "closes_at": "13:00", "is_closed": False},
            {"day_of_week": 3, "opens_at": "09:00", "closes_at": "13:00", "is_closed": False},
        ]
        + [{"day_of_week": day, "is_closed": True} for day in (0, 2, 4, 5, 6)],
    },
    {
        # ⚠ HIDDEN, not deleted (`BR-CWP-096`). It stays in the clerk's list.
        "name": "Depot",
        "address": "44 Works Rd, Austin TX 78721",
        "phone": None,
        "directions_note": None,
        "allowed_actions": [],
        "payment_methods_accepted": [],
        "is_shown_to_customers": False,
        "hours": [{"day_of_week": day, "is_closed": True} for day in range(7)],
    },
)

#: `US-CWP-074` §4 and TC-3 — the closure the demo shows.
#:
#: ⚠ **THE FIXTURE DID NOT HAVE TO WRITE THIS ROW, AND FINDING THAT OUT IS THE
#: BEST PROOF OF `BR-CWP-096` IN THE WAVE.** Provisioning already seeds the
#: eleven US federal holidays for the year (`apps/tenancy/us_holidays.py`, PO
#: ruling 2026-08-11), and the fourth Thursday of November 2026 is 26 November.
#: So a brand-new Pine Hill closes both counters on Thanksgiving with nobody
#: having typed anything anywhere — which is the rule's own promise, met by the
#: product and not by this file. `seed_holiday` is kept as a belt-and-braces
#: `get_or_create` for a tenant provisioned without the seed.
#:
#: ⚠ **AND THE LABEL IS `Thanksgiving Day`, NOT `Thanksgiving`.** `US-CWP-074`
#: §4 writes *"Holiday: 26 November, Thanksgiving"*; the calendar the product
#: actually keeps spells it `Thanksgiving Day` (`us_holidays.py:78`). The
#: screen shows the UTILITY'S OWN WORD — the label is data, not copy — so the
#: figure that ships is the calendar's. Recorded rather than quietly reconciled.
HOLIDAY = {"date": date(2026, 11, 26), "label": "Thanksgiving Day"}


def _actor(actor: Any = None) -> Any:
    """The fixture writes as a System Admin with a name, because
    `last_changed_by` is what `CWP-072` shows a clerk.

    ⚠ **AN ARGUMENT SINCE 2026-09-07, AND THE DEFAULT IS UNCHANGED.** The two
    hand-built demo tenants keep `Sarah Miller` — she is this repository's
    demo staff person and every wave D figure was signed with her name on it.
    The SAMPLE SET passes its own actor instead, because *Sarah Miller* on a
    real utility's Help & answers screen invents a colleague who does not work
    there. See `apps/tenancy/portal_sample.py` for what it passes and why.
    """
    if actor is not None:
        return actor
    return SimpleNamespace(id=None, role=SYSTEM_ADMIN, name="Sarah Miller")


def _seed_answers(tenant_id: Any, who: Any = None) -> None:
    actor = _actor(who)
    for spec in ANSWERS:
        bodies = BODIES.get(spec["question"], GENERIC_BODY)
        variants = {
            locale: (bodies.get(locale) or GENERIC_BODY.get(locale, ""))
            for locale in spec["translated"]
        }
        answer_view = published_content.create_answer(
            actor,
            tenant_id,
            {
                "question": spec["question"],
                "topic": spec["topic"],
                "also_show_on_screen": spec.get("also_show_on_screen"),
                "variants": variants,
            },
        )
        if spec["status"] != content.ANSWER_DRAFT:
            published_content.publish_answer(
                actor, tenant_id, answer_view["slug"], status=spec["status"]
            )
        if spec["reads"]:
            _seed_reads(tenant_id, answer_view["slug"], spec["reads"])


def _seed_reads(tenant_id: Any, slug: str, how_many: int) -> None:
    """*Read this month* is a COUNT, so the fixture writes the rows.

    Spread over the month so far rather than stacked on one day: a column of
    identical dates would make the chart the back office may grow one day look
    like a spike that never happened.
    """
    answer = content.HelpAnswer.objects.get(tenant_id=tenant_id, slug=slug)
    today = published_content._tenant_today(tenant_id)
    first = today.replace(day=1)
    span = max(1, (today - first).days + 1)
    content.HelpAnswerFeedback.objects.bulk_create(
        [
            content.HelpAnswerFeedback(
                tenant_id=tenant_id,
                answer=answer,
                locale="en",
                event=content.FEEDBACK_READ,
                occurred_on=first + timedelta(days=index % span),
            )
            for index in range(how_many)
        ],
        batch_size=1000,
    )


def _seed_tips(tenant_id: Any, who: Any = None) -> None:
    actor = _actor(who)
    for spec in TIPS:
        published_content.create_tip(actor, tenant_id, dict(spec))


def _seed_centres(tenant_id: Any, who: Any = None) -> None:
    actor = _actor(who)
    for spec in CENTRES:
        published_content.create_centre(actor, tenant_id, dict(spec))


def _seed_holiday(tenant_id: Any) -> None:
    """⚠ Into `holiday_calendars`, the list Reference data already keeps — NOT
    into a service centre's hours (`BR-CWP-096`). One row closes every centre
    the utility has, on a day nobody typed into any of them.

    On a tenant provisioned the normal way this writes NOTHING: the row is
    already there from the federal-holiday seed. See the note on `HOLIDAY`.
    """
    tenancy_models.HolidayCalendar.objects.get_or_create(
        tenant_id=tenant_id,
        holiday_date=HOLIDAY["date"],
        defaults={"label": HOLIDAY["label"]},
    )


def seed_published_content(tenant_id: Any, *, who: Any = None) -> dict[str, int]:
    """Everything wave D's demo clicks. Idempotent by refusal, not by replay:
    a second call would mint a second set of slugs, so it returns early when
    the content is already there.

    ⚠ **IT IS THE SAMPLE SET'S CONTENT TOO SINCE 2026-09-07, AND THAT IS WHY
    IT TAKES AN ACTOR.** It was reached only by `apps/portal/sample_data.py`,
    which seeds the two hand-built demo tenants — so `brazosbend` and every
    tenant provisioned through the real sign-up path had **zero** help
    answers, **zero** tips and **zero** service centres. It is now also the
    body of the `tenancy:seed_sample_portal_content` block in `SAMPLE_MODULES`
    (PO ruling 2026-09-07). `who` is that block's actor; the demo tenants pass
    nothing and keep the name they were signed with.

    ⚠ **THE ADDRESSES ARE AUSTIN AND THAT IS DELIBERATE, NOT AN OVERSIGHT.**
    Every seeded premises in this repository sits in the same Austin box
    (`apps/metering/sample_data.py` STREET_GEO), so a counter at `214 Cedar St,
    Austin TX` is in the same invented town as the customers who would walk
    into it. A second, differently-placed set of centres for the sample estate
    would be two sources of truth for one fixture — CLAUDE.md hard-won law 5.
    """
    if content.HelpAnswer.objects.filter(tenant_id=tenant_id).exists():
        return {
            "answers": content.HelpAnswer.objects.filter(tenant_id=tenant_id).count(),
            "tips": content.Tip.objects.filter(tenant_id=tenant_id).count(),
            "centres": content.ServiceCentre.objects.filter(tenant_id=tenant_id).count(),
        }
    _seed_answers(tenant_id, who)
    _seed_tips(tenant_id, who)
    _seed_centres(tenant_id, who)
    _seed_holiday(tenant_id)
    return {
        "answers": len(ANSWERS),
        "tips": len(TIPS),
        "centres": len(CENTRES),
    }


def seed_oak_ridge_content(tenant_id: Any) -> dict[str, int]:
    """Oak Ridge gets its OWN one answer and its OWN one centre — enough for
    every isolation case to have something to find on the wrong side, and not
    one string of Pine Hill's (`US-CWP-071` TC-10, `US-CWP-074` TC-7)."""
    if content.HelpAnswer.objects.filter(tenant_id=tenant_id).exists():
        return {"answers": 1, "tips": 1, "centres": 1}
    actor = _actor()
    view = published_content.create_answer(
        actor,
        tenant_id,
        {
            "question": "Where does Oak Ridge water come from?",
            "topic": "water",
            "variants": {"en": "From the ridge wells, tested every week and treated on site."},
        },
    )
    published_content.publish_answer(
        actor, tenant_id, view["slug"], status=content.ANSWER_PUBLISHED
    )
    published_content.create_tip(
        actor,
        tenant_id,
        {"text": "Check the outside tap before the first frost.", "target_screen": "portal_home"},
    )
    published_content.create_centre(
        actor,
        tenant_id,
        {
            "name": "Ridge office",
            "address": "3 Ridge Rd, Oak Ridge TX 78015",
            "phone": "(830) 555-0170",
            "allowed_actions": ["pay_a_bill", "ask_a_question"],
            "payment_methods_accepted": ["cash", "cheque"],
            "is_shown_to_customers": True,
            "hours": [
                {"day_of_week": day, "opens_at": "09:00", "closes_at": "16:00", "is_closed": False}
                for day in range(0, 4)
            ],
        },
    )
    return {"answers": 1, "tips": 1, "centres": 1}


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-CWP-071..074@d6d31c46 §4 test data, quoted
# generated: 2026-09-04 by the CR-068 wave D build lane
# checklist: A✔ B✔ C✔ D=n/a E=n/a F✔ G✔ H=n/a
# gates: pytest tests/test_us_cwp_07*.py (the same payloads build the test tenants) · G4/G61 untouched — no Brazos Bend figure moves
# exceptions: the eleven catalogue bodies are NATIVE-REVIEW-OWED (B14 rule 35) — said here rather than implied
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
