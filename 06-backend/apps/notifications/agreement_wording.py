# ── Trace ──────────────────────────────────────────────
# Change:   CR-190-BRC10 lane AGREEMENT — PO 2026-10-22, decision logs
#           *"Click-to-accept agreements: the design confirmed with four
#           answers"* and *"Account-access emails: languages via template
#           variants, and 'don't do any hardcoding'"*
# Rules:    BR-NOT-006 (type × category × language variants) · BR-NOT-001
#           (the `default` variant is mandatory) · B14 rule 35 (a language is
#           written natively, not translated word for word from English)
# Tests:    06-backend/tests/test_cr190_agreements.py
# Impacts:  agreement_templates.py (plants these as published variants) ·
#           catalogs.py (`email_agreement_request`, `email_agreement_accepted`)
# ───────────────────────────────────────────────────────
"""The SEEDED wording of the two agreement emails, one variant per language.

HUMAN-OWNED · HUMAN-REVIEW-PENDING — this file decides **words a person
reads**, the authority `seed_templates.py` is guarded for. AI-authored
2026-10-22 under the PO ruling of 2026-08-09; row in
12-governance/09-human-review-ledger.md. **LANE-AUTHORED WORDING**: no signed
document writes these bodies. They are seeded DEFAULTS each utility edits on
Settings → Templates, and a later release only ADDS a missing variant — it
never overwrites one a utility has published (`seed_templates._seed_one` is
insert-missing).

The SHAPE is `account_access_wording`'s (lane STAFF-INVITE, `CR-188-BRC10`),
on purpose, so the two tables can be read by one seeder: template code →
language tag → `(subject, body)`. The KEYS of the inner dict are the languages
that have been WRITTEN, not the languages that exist — the set that exists is
the product's registry (`tenancy_seam.platform_languages`), never a list here.

THE GREETING (lane MERGE-MOVEIN, 2026-10-22): the languages whose greeting is
informal — en, es, es-MX, hi, fr-FR, id-ID, pt-BR — greet `{first_name}`, as
every other seeded customer email does (`customer_context.greeting_name`: the
first word of the name, `Smith, Pat` → `Pat`, a company by its whole name).
`{customer_name}` here printed *"Hi Okafor, Ade,"* on the browser walk. de,
it-IT, ja-JP and ko-KR keep the full name: their greeting is the formal
register (*Guten Tag*, *Gentile*, *様*, *님*), which addresses the whole name.

`{agreement_link}` is mandatory in every variant of the request
(`catalogs.AGREEMENT_EMAIL_CATALOGS`); `rendering.validate_body` refuses a
variant that drops it, so a language written without the link cannot be seeded.
"""

from __future__ import annotations

DEFAULT_WORDING_LANGUAGE = "en"

REQUEST = "email_agreement_request"
ACCEPTED = "email_agreement_accepted"

WORDING: dict[str, dict[str, tuple[str, str]]] = {
    REQUEST: {
        "en": (
            "Please review and accept your {agreement_name}",
            """Hi {first_name},

Your {agreement_name} with {utility_name} for account {account_no} is attached.

Please read it, then accept it here: {agreement_link}

The link works once and expires on {link_expires_on}. Questions? Call us on {support_phone}.""",
        ),
        "es": (
            "Revisa y acepta tu {agreement_name}",
            """Hola, {first_name}:

Te adjuntamos tu {agreement_name} con {utility_name} para la cuenta {account_no}.

Léelo y, después, acéptalo aquí: {agreement_link}

El enlace solo se puede usar una vez y caduca el {link_expires_on}. ¿Tienes alguna duda? Llámanos al {support_phone}.""",
        ),
        "es-MX": (
            "Revisa y acepta tu {agreement_name}",
            """Hola, {first_name}:

Te mandamos adjunto tu {agreement_name} con {utility_name} para la cuenta {account_no}.

Léelo y luego acéptalo aquí: {agreement_link}

El enlace solo funciona una vez y vence el {link_expires_on}. ¿Dudas? Llámanos al {support_phone}.""",
        ),
        "de": (
            "Bitte prüfen und bestätigen Sie Ihren {agreement_name}",
            """Guten Tag {customer_name},

im Anhang finden Sie Ihren {agreement_name} mit {utility_name} für das Kundenkonto {account_no}.

Bitte lesen Sie ihn und bestätigen Sie ihn dann hier: {agreement_link}

Der Link ist nur einmal gültig und läuft am {link_expires_on} ab. Bei Fragen erreichen Sie uns unter {support_phone}.""",
        ),
        "hi": (
            "कृपया अपना {agreement_name} देखें और स्वीकार करें",
            """नमस्ते {first_name},

खाता {account_no} के लिए {utility_name} के साथ आपका {agreement_name} इस ईमेल के साथ संलग्न है।

कृपया इसे पढ़ें और फिर यहाँ स्वीकार करें: {agreement_link}

यह लिंक केवल एक बार काम करता है और {link_expires_on} को समाप्त हो जाएगा। कोई सवाल हो तो हमें {support_phone} पर कॉल करें।""",
        ),
        "fr-FR": (
            "Merci de lire et d'accepter votre {agreement_name}",
            """Bonjour {first_name},

Vous trouverez ci-joint votre {agreement_name} avec {utility_name} pour le compte {account_no}.

Lisez-le, puis acceptez-le ici : {agreement_link}

Ce lien ne fonctionne qu'une fois et expire le {link_expires_on}. Une question ? Appelez-nous au {support_phone}.""",
        ),
        "id-ID": (
            "Mohon baca dan setujui {agreement_name} Anda",
            """Halo {first_name},

Terlampir {agreement_name} Anda dengan {utility_name} untuk akun {account_no}.

Silakan baca, lalu setujui di sini: {agreement_link}

Tautan ini hanya bisa dipakai sekali dan berlaku sampai {link_expires_on}. Ada pertanyaan? Hubungi kami di {support_phone}.""",
        ),
        "it-IT": (
            "Legga e accetti il suo {agreement_name}",
            """Gentile {customer_name},

in allegato trova il suo {agreement_name} con {utility_name} per il conto {account_no}.

Lo legga e poi lo accetti qui: {agreement_link}

Il link si può usare una sola volta e scade il {link_expires_on}. Per qualsiasi domanda ci chiami al {support_phone}.""",
        ),
        "ja-JP": (
            "{agreement_name}のご確認と同意のお願い",
            """{customer_name} 様

お客様番号 {account_no} の{utility_name}との{agreement_name}を添付しております。

内容をご確認のうえ、こちらから同意してください: {agreement_link}

このリンクは一度だけ有効で、{link_expires_on}に期限が切れます。ご不明な点は {support_phone} までお電話ください。""",
        ),
        "ko-KR": (
            "{agreement_name} 확인 및 동의 요청",
            """{customer_name} 님, 안녕하세요.

계정 {account_no}에 대한 {utility_name}의 {agreement_name}을(를) 첨부해 드립니다.

내용을 읽어 보신 뒤 여기에서 동의해 주세요: {agreement_link}

이 링크는 한 번만 사용할 수 있으며 {link_expires_on}에 만료됩니다. 궁금한 점은 {support_phone}(으)로 전화해 주세요.""",
        ),
        "pt-BR": (
            "Leia e aceite o seu {agreement_name}",
            """Olá, {first_name},

Segue em anexo o seu {agreement_name} com a {utility_name} para a conta {account_no}.

Leia com atenção e depois aceite aqui: {agreement_link}

O link só pode ser usado uma vez e vence em {link_expires_on}. Dúvidas? Ligue para {support_phone}.""",
        ),
    },
    ACCEPTED: {
        "en": (
            "Thank you, your {agreement_name} is accepted",
            """Hi {first_name},

Thank you. {utility_name} has your acceptance of the {agreement_name} for account {account_no}.

Accepted on {accepted_on} by {accepted_name}.

Questions? Call us on {support_phone}.""",
        ),
        "es": (
            "Gracias, hemos recibido tu aceptación del {agreement_name}",
            """Hola, {first_name}:

Gracias. {utility_name} ha recibido tu aceptación del {agreement_name} de la cuenta {account_no}.

Aceptado el {accepted_on} por {accepted_name}.

¿Tienes alguna duda? Llámanos al {support_phone}.""",
        ),
        "es-MX": (
            "Gracias, ya recibimos tu aceptación del {agreement_name}",
            """Hola, {first_name}:

Gracias. {utility_name} ya tiene registrada tu aceptación del {agreement_name} de la cuenta {account_no}.

Aceptado el {accepted_on} por {accepted_name}.

¿Dudas? Llámanos al {support_phone}.""",
        ),
        "de": (
            "Vielen Dank, Ihr {agreement_name} ist bestätigt",
            """Guten Tag {customer_name},

vielen Dank. {utility_name} hat Ihre Zustimmung zum {agreement_name} für das Kundenkonto {account_no} erhalten.

Bestätigt am {accepted_on} von {accepted_name}.

Bei Fragen erreichen Sie uns unter {support_phone}.""",
        ),
        "hi": (
            "धन्यवाद, आपका {agreement_name} स्वीकार हो गया है",
            """नमस्ते {first_name},

धन्यवाद। खाता {account_no} के {agreement_name} के लिए आपकी स्वीकृति {utility_name} को मिल गई है।

{accepted_on} को {accepted_name} द्वारा स्वीकार किया गया।

कोई सवाल हो तो हमें {support_phone} पर कॉल करें।""",
        ),
        "fr-FR": (
            "Merci, votre {agreement_name} est accepté",
            """Bonjour {first_name},

Merci. {utility_name} a bien reçu votre acceptation du {agreement_name} pour le compte {account_no}.

Accepté le {accepted_on} par {accepted_name}.

Une question ? Appelez-nous au {support_phone}.""",
        ),
        "id-ID": (
            "Terima kasih, {agreement_name} Anda sudah disetujui",
            """Halo {first_name},

Terima kasih. {utility_name} sudah menerima persetujuan Anda atas {agreement_name} untuk akun {account_no}.

Disetujui pada {accepted_on} oleh {accepted_name}.

Ada pertanyaan? Hubungi kami di {support_phone}.""",
        ),
        "it-IT": (
            "Grazie, il suo {agreement_name} è stato accettato",
            """Gentile {customer_name},

grazie. {utility_name} ha ricevuto la sua accettazione del {agreement_name} per il conto {account_no}.

Accettato il {accepted_on} da {accepted_name}.

Per qualsiasi domanda ci chiami al {support_phone}.""",
        ),
        "ja-JP": (
            "{agreement_name}へのご同意ありがとうございます",
            """{customer_name} 様

お客様番号 {account_no} の{agreement_name}について、{utility_name}はお客様のご同意を確かに受け付けました。

同意日: {accepted_on}　同意者: {accepted_name}

ご不明な点は {support_phone} までお電話ください。""",
        ),
        "ko-KR": (
            "{agreement_name} 동의가 완료되었습니다",
            """{customer_name} 님, 안녕하세요.

감사합니다. 계정 {account_no}의 {agreement_name}에 대한 동의가 {utility_name}에 접수되었습니다.

동의일: {accepted_on} · 동의자: {accepted_name}

궁금한 점은 {support_phone}(으)로 전화해 주세요.""",
        ),
        "pt-BR": (
            "Obrigado, o seu {agreement_name} foi aceito",
            """Olá, {first_name},

Obrigado. A {utility_name} recebeu o seu aceite do {agreement_name} da conta {account_no}.

Aceito em {accepted_on} por {accepted_name}.

Dúvidas? Ligue para {support_phone}.""",
        ),
    },
}


def wording_for(code: str, language: str) -> tuple[str, str] | None:
    """`(subject, body)` for one class in one language — the exact tag, else its
    primary language (`en-US` → `en`), else None. `account_access_wording`'s
    rule, so the two tables answer one question one way."""
    table = WORDING.get(code) or {}
    if language in table:
        return table[language]
    return table.get(language.split("-", 1)[0])


__all__ = ["ACCEPTED", "DEFAULT_WORDING_LANGUAGE", "REQUEST", "WORDING", "wording_for"]
