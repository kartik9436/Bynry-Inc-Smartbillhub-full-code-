# ── Trace ──────────────────────────────────────────────
# Defect:   DEF-BIL-4454 — the corrected-bill email's *"What changed:
#           {correction_reason}"* had no customer sentence to print
#           (and DEF-BIL-10535, the corrected bill that lost its email)
# Ruling:   PO 2026-10-22, decision log *"Corrected bills: the clerk picks the
#           channels; every bill also emails whenever an email is on file;
#           'What changed' gets one sentence per reason …"*, Q3, verbatim:
#           *"A. One plain sentence per reason, written by us, which the
#           utility can edit on the templates screen, in all 11 languages"*;
#           our judgments in the entry *"Building the corrected-bill rulings
#           Q1–Q3"*, points 6–7
# Rules:    BR-NOT-006 (type × category × language variants; the utility's
#           default language, amended 2026-09-23) · BR-NOT-015 (wording is
#           notifications' to own) · B14 rule 35 (a language is written in its
#           own voice, not translated word for word)
# Tests:    06-backend/tests/test_def_bil_10535_corrected_bill_channels.py
# Impacts:  catalogs.py (one class + listing per reason) · seed_templates.py
#           (planted in every registry language) · migrations/0029 (existing
#           utilities) · apps/billing/delivery_seam.bill_render_context
# ───────────────────────────────────────────────────────
"""*What changed* — one customer sentence per seeded correction reason.

HUMAN-OWNED · HUMAN-REVIEW-PENDING — this file decides **words a person
reads**. AI-authored 2026-10-22 under the PO ruling of 2026-08-09; row in
12-governance/09-human-review-ledger.md. **LANE-AUTHORED WORDING**: the PO ruled
that we write it (Q3 option A); no signed document writes these sentences. They
are SEEDED DEFAULTS: each reason is its own template class,
`correction_reason_<code>`, filed under Billing on Configure → Templates, and a
utility edits it there. A later release only ADDS a missing language variant —
it never overwrites one a utility published (`seed_templates._seed_one` is
insert-missing).

WHY NOT `correction_reasons.MECHANISM_IN_WORDS`. That describes the MECHANISM
to a clerk (*"the original is credited in full …"*). A customer needs the FAULT
in their words: *"We corrected your meter reading."*

THE SHAPE is `move_out_wording`'s on purpose, so the one seeder reads all of
them: template code → language tag → `(subject, body)`. A sentence class has no
subject (`None`): it is printed only INSIDE the corrected-bill email, never
sent alone. It carries no token either — a sentence that needed a figure would
be a second statement of a number the email already prints.

`sentences_for` is the read billing asks by name
(`delivery_seam.bill_render_context`): one sentence per reason on the case, in
the case's order, in the utility's default language — its published variant in
that language, else the published `default` variant, else the platform wording
below. A reason this file does not know (none today; the tenant-extensible
reason list is not built) gives no sentence, and a case with none prints the
named absence `——`, never a code.
"""

from __future__ import annotations

from typing import Any

DEFAULT_WORDING_LANGUAGE = "en"

#: The class code for one reason. Spelled once.
CLASS_PREFIX = "correction_reason_"


def class_code(reason_code: str) -> str:
    return f"{CLASS_PREFIX}{reason_code}"


#: The clerk's own words for each reason, from Fix-a-bill's reason list
#: (`billing.fixBill.reason.*` in the English catalogue), so the row a System
#: Admin opens on Templates names the reason exactly as the clerk picked it.
REASON_NAMES: dict[str, str] = {
    "wrong_read": "Wrong reading",
    "wrong_rate_plan": "Wrong plan or rate",
    "wrong_tax": "Wrong tax",
    "missed_charge": "A charge was missed",
    "charge_billed_in_error": "A charge was billed in error",
    "wrong_period_or_service": "Wrong period or service",
    "theft_restated": "Theft, restated",
    "wrong_plan": "Wrong plan",
    "wrong_rate": "Wrong rate",
    "wrong_discount": "Wrong discount",
    "wrong_deposit": "Wrong deposit",
    "goodwill": "Goodwill credit",
    "customer_name": "Customer name",
    "service_or_mailing_address": "Mailing address",
    "premises_or_unit_label": "Premises or unit label",
    "meter_number_or_read_dates": "Meter number or read dates",
    "template_or_language": "Template or language",
}

# One table per language, reason → sentence, so a translator reads a language
# whole. The informal languages address the customer as tú / você; de, it-IT,
# ja-JP and ko-KR are written in the formal register, as every other seeded
# customer email in those languages is.
_SENTENCES: dict[str, dict[str, str]] = {
    "en": {
        "wrong_read": "We corrected your meter reading.",
        "wrong_rate_plan": "We corrected the plan and rate on your bill.",
        "wrong_tax": "We corrected the tax on your bill.",
        "missed_charge": "We added a charge that was missing.",
        "charge_billed_in_error": "We removed a charge billed in error.",
        "wrong_period_or_service": "We corrected the billing period or service.",
        "theft_restated": "We recalculated the usage on your bill.",
        "wrong_plan": "We corrected the plan on your bill.",
        "wrong_rate": "We corrected the rate on your bill.",
        "wrong_discount": "We corrected a discount on your bill.",
        "wrong_deposit": "We corrected the deposit on your bill.",
        "goodwill": "We added a goodwill credit to your account.",
        "customer_name": "We corrected the name on your bill.",
        "service_or_mailing_address": "We corrected the address on your bill.",
        "premises_or_unit_label": "We corrected the property or unit on your bill.",
        "meter_number_or_read_dates": "We corrected the meter number or reading dates.",
        "template_or_language": "We corrected the layout or language of your bill.",
    },
    "es": {
        "wrong_read": "Hemos corregido la lectura de tu contador.",
        "wrong_rate_plan": "Hemos corregido el plan y la tarifa de tu factura.",
        "wrong_tax": "Hemos corregido los impuestos de tu factura.",
        "missed_charge": "Hemos añadido un cargo que faltaba.",
        "charge_billed_in_error": "Hemos quitado un cargo que se facturó por error.",
        "wrong_period_or_service": "Hemos corregido el periodo facturado o el servicio.",
        "theft_restated": "Hemos recalculado el consumo de tu factura.",
        "wrong_plan": "Hemos corregido el plan de tu factura.",
        "wrong_rate": "Hemos corregido la tarifa de tu factura.",
        "wrong_discount": "Hemos corregido un descuento de tu factura.",
        "wrong_deposit": "Hemos corregido la fianza de tu factura.",
        "goodwill": "Te hemos aplicado un abono de cortesía en tu cuenta.",
        "customer_name": "Hemos corregido el nombre que aparece en tu factura.",
        "service_or_mailing_address": "Hemos corregido la dirección de tu factura.",
        "premises_or_unit_label": "Hemos corregido el inmueble o la unidad de tu factura.",
        "meter_number_or_read_dates": "Hemos corregido el número de contador o las fechas de lectura.",
        "template_or_language": "Hemos corregido el formato o el idioma de tu factura.",
    },
    "es-MX": {
        "wrong_read": "Corregimos la lectura de tu medidor.",
        "wrong_rate_plan": "Corregimos el plan y la tarifa de tu recibo.",
        "wrong_tax": "Corregimos los impuestos de tu recibo.",
        "missed_charge": "Agregamos un cargo que faltaba.",
        "charge_billed_in_error": "Quitamos un cargo que se cobró por error.",
        "wrong_period_or_service": "Corregimos el periodo o el servicio cobrado.",
        "theft_restated": "Recalculamos el consumo de tu recibo.",
        "wrong_plan": "Corregimos el plan de tu recibo.",
        "wrong_rate": "Corregimos la tarifa de tu recibo.",
        "wrong_discount": "Corregimos un descuento de tu recibo.",
        "wrong_deposit": "Corregimos el depósito de tu recibo.",
        "goodwill": "Te aplicamos un crédito de cortesía en tu cuenta.",
        "customer_name": "Corregimos el nombre en tu recibo.",
        "service_or_mailing_address": "Corregimos la dirección de tu recibo.",
        "premises_or_unit_label": "Corregimos el inmueble o la unidad de tu recibo.",
        "meter_number_or_read_dates": "Corregimos el número de medidor o las fechas de lectura.",
        "template_or_language": "Corregimos el formato o el idioma de tu recibo.",
    },
    "de": {
        "wrong_read": "Wir haben Ihren Zählerstand korrigiert.",
        "wrong_rate_plan": "Wir haben Tarif und Preis auf Ihrer Rechnung korrigiert.",
        "wrong_tax": "Wir haben die Steuer auf Ihrer Rechnung korrigiert.",
        "missed_charge": "Wir haben eine fehlende Position ergänzt.",
        "charge_billed_in_error": "Wir haben eine irrtümlich berechnete Position entfernt.",
        "wrong_period_or_service": "Wir haben den Abrechnungszeitraum oder die Leistung korrigiert.",
        "theft_restated": "Wir haben Ihren Verbrauch neu berechnet.",
        "wrong_plan": "Wir haben den Tarif auf Ihrer Rechnung korrigiert.",
        "wrong_rate": "Wir haben den Preis auf Ihrer Rechnung korrigiert.",
        "wrong_discount": "Wir haben einen Rabatt auf Ihrer Rechnung korrigiert.",
        "wrong_deposit": "Wir haben die Kaution auf Ihrer Rechnung korrigiert.",
        "goodwill": "Wir haben Ihrem Konto eine Kulanzgutschrift gutgeschrieben.",
        "customer_name": "Wir haben den Namen auf Ihrer Rechnung korrigiert.",
        "service_or_mailing_address": "Wir haben die Anschrift auf Ihrer Rechnung korrigiert.",
        "premises_or_unit_label": (
            "Wir haben das Objekt oder die Wohneinheit auf Ihrer Rechnung korrigiert."
        ),
        "meter_number_or_read_dates": "Wir haben die Zählernummer oder die Ablesedaten korrigiert.",
        "template_or_language": "Wir haben Layout oder Sprache Ihrer Rechnung korrigiert.",
    },
    "hi": {
        "wrong_read": "हमने आपकी मीटर रीडिंग ठीक कर दी है।",
        "wrong_rate_plan": "हमने आपके बिल का प्लान और दर ठीक कर दिए हैं।",
        "wrong_tax": "हमने आपके बिल पर लगा टैक्स ठीक कर दिया है।",
        "missed_charge": "हमने छूटा हुआ एक शुल्क जोड़ दिया है।",
        "charge_billed_in_error": "हमने गलती से लगाया गया एक शुल्क हटा दिया है।",
        "wrong_period_or_service": "हमने बिल की अवधि या सेवा ठीक कर दी है।",
        "theft_restated": "हमने आपके बिल की खपत दोबारा गिनी है।",
        "wrong_plan": "हमने आपके बिल का प्लान ठीक कर दिया है।",
        "wrong_rate": "हमने आपके बिल की दर ठीक कर दी है।",
        "wrong_discount": "हमने आपके बिल पर मिली छूट ठीक कर दी है।",
        "wrong_deposit": "हमने आपके बिल पर जमा राशि ठीक कर दी है।",
        "goodwill": "हमने आपके खाते में सद्भावना क्रेडिट जोड़ दिया है।",
        "customer_name": "हमने आपके बिल पर लिखा नाम ठीक कर दिया है।",
        "service_or_mailing_address": "हमने आपके बिल पर लिखा पता ठीक कर दिया है।",
        "premises_or_unit_label": "हमने आपके बिल पर संपत्ति या यूनिट का नाम ठीक कर दिया है।",
        "meter_number_or_read_dates": "हमने मीटर नंबर या रीडिंग की तारीखें ठीक कर दी हैं।",
        "template_or_language": "हमने आपके बिल का प्रारूप या भाषा ठीक कर दी है।",
    },
    "fr-FR": {
        "wrong_read": "Nous avons corrigé le relevé de votre compteur.",
        "wrong_rate_plan": "Nous avons corrigé l'offre et le tarif de votre facture.",
        "wrong_tax": "Nous avons corrigé les taxes de votre facture.",
        "missed_charge": "Nous avons ajouté un montant qui manquait.",
        "charge_billed_in_error": "Nous avons retiré un montant facturé par erreur.",
        "wrong_period_or_service": "Nous avons corrigé la période facturée ou le service.",
        "theft_restated": "Nous avons recalculé votre consommation.",
        "wrong_plan": "Nous avons corrigé l'offre de votre facture.",
        "wrong_rate": "Nous avons corrigé le tarif de votre facture.",
        "wrong_discount": "Nous avons corrigé une remise sur votre facture.",
        "wrong_deposit": "Nous avons corrigé le dépôt de garantie de votre facture.",
        "goodwill": "Nous avons accordé un geste commercial sur votre compte.",
        "customer_name": "Nous avons corrigé le nom figurant sur votre facture.",
        "service_or_mailing_address": "Nous avons corrigé l'adresse de votre facture.",
        "premises_or_unit_label": (
            "Nous avons corrigé le logement ou le lot indiqué sur votre facture."
        ),
        "meter_number_or_read_dates": (
            "Nous avons corrigé le numéro de compteur ou les dates de relevé."
        ),
        "template_or_language": "Nous avons corrigé la mise en page ou la langue de votre facture.",
    },
    "id-ID": {
        "wrong_read": "Kami telah memperbaiki angka meter Anda.",
        "wrong_rate_plan": "Kami telah memperbaiki paket dan tarif pada tagihan Anda.",
        "wrong_tax": "Kami telah memperbaiki pajak pada tagihan Anda.",
        "missed_charge": "Kami telah menambahkan biaya yang terlewat.",
        "charge_billed_in_error": "Kami telah menghapus biaya yang salah ditagihkan.",
        "wrong_period_or_service": "Kami telah memperbaiki periode tagihan atau layanannya.",
        "theft_restated": "Kami telah menghitung ulang pemakaian pada tagihan Anda.",
        "wrong_plan": "Kami telah memperbaiki paket pada tagihan Anda.",
        "wrong_rate": "Kami telah memperbaiki tarif pada tagihan Anda.",
        "wrong_discount": "Kami telah memperbaiki potongan harga pada tagihan Anda.",
        "wrong_deposit": "Kami telah memperbaiki uang jaminan pada tagihan Anda.",
        "goodwill": "Kami telah memberikan kredit kompensasi ke akun Anda.",
        "customer_name": "Kami telah memperbaiki nama pada tagihan Anda.",
        "service_or_mailing_address": "Kami telah memperbaiki alamat pada tagihan Anda.",
        "premises_or_unit_label": "Kami telah memperbaiki nama properti atau unit pada tagihan Anda.",
        "meter_number_or_read_dates": "Kami telah memperbaiki nomor meter atau tanggal pembacaan.",
        "template_or_language": "Kami telah memperbaiki format atau bahasa tagihan Anda.",
    },
    "it-IT": {
        "wrong_read": "Abbiamo corretto la lettura del suo contatore.",
        "wrong_rate_plan": "Abbiamo corretto l'offerta e la tariffa della sua bolletta.",
        "wrong_tax": "Abbiamo corretto le imposte della sua bolletta.",
        "missed_charge": "Abbiamo aggiunto un addebito che mancava.",
        "charge_billed_in_error": "Abbiamo tolto un addebito applicato per errore.",
        "wrong_period_or_service": "Abbiamo corretto il periodo fatturato o il servizio.",
        "theft_restated": "Abbiamo ricalcolato i consumi della sua bolletta.",
        "wrong_plan": "Abbiamo corretto l'offerta della sua bolletta.",
        "wrong_rate": "Abbiamo corretto la tariffa della sua bolletta.",
        "wrong_discount": "Abbiamo corretto uno sconto della sua bolletta.",
        "wrong_deposit": "Abbiamo corretto il deposito cauzionale della sua bolletta.",
        "goodwill": "Abbiamo accreditato un bonus di cortesia sul suo conto.",
        "customer_name": "Abbiamo corretto il nome riportato in bolletta.",
        "service_or_mailing_address": "Abbiamo corretto l'indirizzo riportato in bolletta.",
        "premises_or_unit_label": "Abbiamo corretto l'immobile o l'unità riportati in bolletta.",
        "meter_number_or_read_dates": (
            "Abbiamo corretto il numero del contatore o le date di lettura."
        ),
        "template_or_language": "Abbiamo corretto il formato o la lingua della sua bolletta.",
    },
    "ja-JP": {
        "wrong_read": "メーターの検針値を訂正いたしました。",
        "wrong_rate_plan": "ご請求のプランと料金単価を訂正いたしました。",
        "wrong_tax": "ご請求の税額を訂正いたしました。",
        "missed_charge": "請求漏れの料金を追加いたしました。",
        "charge_billed_in_error": "誤って請求した料金を取り消しいたしました。",
        "wrong_period_or_service": "ご請求の対象期間またはサービスを訂正いたしました。",
        "theft_restated": "ご使用量を再計算いたしました。",
        "wrong_plan": "ご請求のプランを訂正いたしました。",
        "wrong_rate": "ご請求の料金単価を訂正いたしました。",
        "wrong_discount": "ご請求の割引を訂正いたしました。",
        "wrong_deposit": "ご請求の預り金を訂正いたしました。",
        "goodwill": "お客様のアカウントにお詫びのクレジットを付与いたしました。",
        "customer_name": "請求書のお名前を訂正いたしました。",
        "service_or_mailing_address": "請求書のご住所を訂正いたしました。",
        "premises_or_unit_label": "請求書の物件名または部屋番号を訂正いたしました。",
        "meter_number_or_read_dates": "メーター番号または検針日を訂正いたしました。",
        "template_or_language": "請求書の書式または言語を訂正いたしました。",
    },
    "ko-KR": {
        "wrong_read": "계량기 검침값을 바로잡았습니다.",
        "wrong_rate_plan": "청구서의 요금제와 단가를 바로잡았습니다.",
        "wrong_tax": "청구서의 세금을 바로잡았습니다.",
        "missed_charge": "누락된 요금을 추가했습니다.",
        "charge_billed_in_error": "잘못 청구된 요금을 삭제했습니다.",
        "wrong_period_or_service": "청구 기간 또는 서비스를 바로잡았습니다.",
        "theft_restated": "사용량을 다시 계산했습니다.",
        "wrong_plan": "청구서의 요금제를 바로잡았습니다.",
        "wrong_rate": "청구서의 단가를 바로잡았습니다.",
        "wrong_discount": "청구서의 할인을 바로잡았습니다.",
        "wrong_deposit": "청구서의 보증금을 바로잡았습니다.",
        "goodwill": "고객님 계정에 보상 크레딧을 적용했습니다.",
        "customer_name": "청구서의 성함을 바로잡았습니다.",
        "service_or_mailing_address": "청구서의 주소를 바로잡았습니다.",
        "premises_or_unit_label": "청구서의 건물 또는 호실 정보를 바로잡았습니다.",
        "meter_number_or_read_dates": "계량기 번호 또는 검침일을 바로잡았습니다.",
        "template_or_language": "청구서의 양식 또는 언어를 바로잡았습니다.",
    },
    "pt-BR": {
        "wrong_read": "Corrigimos a leitura do seu medidor.",
        "wrong_rate_plan": "Corrigimos o plano e a tarifa da sua conta.",
        "wrong_tax": "Corrigimos os impostos da sua conta.",
        "missed_charge": "Incluímos uma cobrança que estava faltando.",
        "charge_billed_in_error": "Retiramos uma cobrança feita por engano.",
        "wrong_period_or_service": "Corrigimos o período cobrado ou o serviço.",
        "theft_restated": "Recalculamos o consumo da sua conta.",
        "wrong_plan": "Corrigimos o plano da sua conta.",
        "wrong_rate": "Corrigimos a tarifa da sua conta.",
        "wrong_discount": "Corrigimos um desconto da sua conta.",
        "wrong_deposit": "Corrigimos o depósito caução da sua conta.",
        "goodwill": "Lançamos um crédito de cortesia na sua conta.",
        "customer_name": "Corrigimos o nome que aparece na sua conta.",
        "service_or_mailing_address": "Corrigimos o endereço da sua conta.",
        "premises_or_unit_label": "Corrigimos o imóvel ou a unidade da sua conta.",
        "meter_number_or_read_dates": "Corrigimos o número do medidor ou as datas de leitura.",
        "template_or_language": "Corrigimos o formato ou o idioma da sua conta.",
    },
}

#: template code → language tag → `(subject, body)`. The subject is `None`: a
#: sentence class is printed inside the corrected-bill email, never sent alone.
WORDING: dict[str, dict[str, tuple[str | None, str]]] = {
    class_code(reason): {language: (None, table[reason]) for language, table in _SENTENCES.items()}
    for reason in REASON_NAMES
}


def wording_for(code: str, language: str) -> tuple[str | None, str] | None:
    """`(subject, body)` for one class in one language — the exact tag, else its
    primary language (`en-US` → `en`, `es-419` → `es`), else None."""
    table = WORDING.get(code) or {}
    if language in table:
        return table[language]
    primary = language.split("-", 1)[0]
    return table.get(primary)


def _published_sentence(code: str, language: str | None) -> str | None:
    """The utility's PUBLISHED sentence for one class, or None when nothing
    resolves. `template_service.resolve` walks (default, language) → (default,
    default), which is BR-NOT-006's fallback; a utility's edit is a published
    version and wins over the platform wording below."""
    from apps.notifications import template_service
    from apps.notifications import template_models as tm

    try:
        resolved = template_service.resolve(code=code, language=language)
    except template_service.TemplateRefused:
        return None
    body = (
        tm.NotificationTemplateVersion.objects.filter(
            template_id=resolved.template_id, version=resolved.version
        )
        .values_list("body", flat=True)
        .first()
    )
    return (body or "").strip() or None


def sentences_for(reason_codes: Any, *, account_id: Any = None) -> str | None:
    """*What changed* for one case: one sentence per reason, in the case's
    order, separated by a space — or None when no reason has a sentence.

    In the ACCOUNT's language where the utility published that sentence in
    it, the utility's default otherwise (PO option B, 2026-10-29 —
    `BR-NOT-006` as amended that day; `message_language.language_for`), so a
    corrected-bill email to Rosa is not Spanish around an English sentence.
    Worked: Daniel's case `["wrong_read"]` on an English utility →
    *"We corrected your meter reading."*; `["wrong_read", "wrong_tax"]` →
    *"We corrected your meter reading. We corrected the tax on your bill."*

    Reads the tenant in context. The caller (`delivery_seam`) runs this inside
    its own savepoint, so a refused read never aborts the issue transaction
    (hard-won law 14).
    """
    from apps.notifications import message_language, tenancy_seam

    utility = tenancy_seam.tenant_default_language()
    stated = message_language.account_language(account_id)
    sentences: list[str] = []
    for reason in [str(one) for one in (reason_codes or ())]:
        code = class_code(reason)
        if code not in WORDING:
            continue
        language = message_language.language_for(code, stated=stated, utility=utility)
        sentence = _published_sentence(code, language)
        if sentence is None:
            words = (
                wording_for(code, language or DEFAULT_WORDING_LANGUAGE)
                or WORDING[code][DEFAULT_WORDING_LANGUAGE]
            )
            sentence = words[1]
        sentences.append(sentence)
    return " ".join(sentences) or None


__all__ = [
    "CLASS_PREFIX",
    "DEFAULT_WORDING_LANGUAGE",
    "REASON_NAMES",
    "WORDING",
    "class_code",
    "sentences_for",
    "wording_for",
]
