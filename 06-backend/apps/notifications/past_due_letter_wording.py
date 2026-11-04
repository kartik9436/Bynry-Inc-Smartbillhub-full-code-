# ── Trace ──────────────────────────────────────────────
# Defect:   DEF-PAY-10651 — the automatic past-due reminder; the printed letter
#           for a customer with no email and no SMS consent
# Ruling:   PO 2026-10-29, *"1A 2A 3A 4B, start"* — 2A: *"a printed past-due
#           reminder letter — seed one (editable, 11 languages)"*; decision log
#           judgment 1 (it is the EXISTING `dunning` class)
# Rules:    BR-NOT-006 (type × category × language variants) · BR-NOT-001 (the
#           `default` variant is mandatory) · B14 rule 35 (a language is written
#           natively, not translated word for word) · A19 rule 2 / US-NOT-007
#           (a reminder carries NO regulatory footer)
# Tests:    06-backend/tests/test_def_pay_10651_past_due_reminder.py
# ───────────────────────────────────────────────────────
"""The SEEDED wording of the printed past-due reminder letter, one variant per language.

HUMAN-OWNED · HUMAN-REVIEW-PENDING — this file decides **words a person
reads**, the authority `seed_templates.py` is guarded for. AI-authored
2026-10-29 under the PO ruling of 2026-08-09; row in
12-governance/09-human-review-ledger.md.

**THE ENGLISH IS NOT AUTHORED — IT IS A13's QUOTED REMINDER**, the same words
`seed_templates.DUNNING_BODY` has planted as the `default` variant since
2026-08-16. The ten others are LANE-AUTHORED renderings of that one sentence,
written the way a small utility in that language would say it (B14 rule 35).
Each is a seeded DEFAULT a utility edits on Settings → Templates; a later
release only ADDS a missing variant (`seed_templates._seed_one` is
insert-missing).

**NOTHING THE SENTENCE DOES NOT ALREADY SAY.** No fee, no deadline, no
regulator's rule number, no disconnection warning — a reminder is not a notice
(A19 rule 2, US-NOT-007), and `seed_templates`' constraint 4 forbids any figure
that is not ruled. Every token is in `catalogs.CATALOGS["dunning"]`.

THE GREETING follows `agreement_wording`: the informal languages greet
`{first_name}`; de, it-IT, ja-JP and ko-KR address the whole `{customer_name}`
in the formal register. A printed letter has no subject line, so the subject is
`None`.

The shape is `move_out_wording`'s, so the ONE seeder reads it: template code →
language tag → `(subject, body)`.
"""

from __future__ import annotations

DEFAULT_WORDING_LANGUAGE = "en"

PAST_DUE_LETTER = "dunning"

WORDING: dict[str, dict[str, tuple[str | None, str]]] = {
    PAST_DUE_LETTER: {
        "en": (
            None,
            "Hi {first_name}, this is a friendly reminder that your account {account} has a "
            "balance of {balance}. You can pay online at any time. Thanks for being a customer.",
        ),
        "es": (
            None,
            "Hola, {first_name}: te recordamos amablemente que tu cuenta {account} tiene un "
            "saldo pendiente de {balance}. Puedes pagar en línea cuando quieras. Gracias por "
            "confiar en nosotros.",
        ),
        "es-MX": (
            None,
            "Hola, {first_name}: te recordamos que tu cuenta {account} tiene un saldo "
            "pendiente de {balance}. Puedes pagar en línea cuando gustes. Gracias por ser "
            "nuestro cliente.",
        ),
        "de": (
            None,
            "Guten Tag {customer_name}, wir möchten Sie freundlich daran erinnern, dass auf "
            "Ihrem Kundenkonto {account} noch ein Betrag von {balance} offen ist. Sie können "
            "jederzeit online bezahlen. Vielen Dank, dass Sie Kunde bei uns sind.",
        ),
        "hi": (
            None,
            "नमस्ते {first_name}, यह एक विनम्र याद-दिहानी है कि आपके खाते {account} में "
            "{balance} की राशि बकाया है। आप कभी भी ऑनलाइन भुगतान कर सकते हैं। हमारे ग्राहक "
            "होने के लिए धन्यवाद।",
        ),
        "fr-FR": (
            None,
            "Bonjour {first_name}, nous vous rappelons que votre compte {account} présente un "
            "solde de {balance}. Vous pouvez régler en ligne à tout moment. Merci de votre "
            "confiance.",
        ),
        "id-ID": (
            None,
            "Halo {first_name}, kami ingin mengingatkan bahwa akun Anda {account} memiliki "
            "tagihan sebesar {balance}. Anda dapat membayar secara online kapan saja. Terima "
            "kasih telah menjadi pelanggan kami.",
        ),
        "it-IT": (
            None,
            "Gentile {customer_name}, Le ricordiamo cortesemente che sul Suo conto {account} "
            "risulta un saldo di {balance}. Può pagare online in qualsiasi momento. La "
            "ringraziamo per essere nostro cliente.",
        ),
        "ja-JP": (
            None,
            "{customer_name} 様\n\nお客様のアカウント {account} に {balance} の未払い残高が"
            "ございますので、お知らせいたします。お支払いはオンラインでいつでも可能です。"
            "いつもご利用いただき、ありがとうございます。",
        ),
        "ko-KR": (
            None,
            "{customer_name} 고객님, 고객님의 계정 {account}에 {balance}의 미납 잔액이 있어 "
            "안내드립니다. 온라인으로 언제든지 납부하실 수 있습니다. 항상 이용해 주셔서 "
            "감사합니다.",
        ),
        "pt-BR": (
            None,
            "Olá, {first_name}! Este é um lembrete de que a sua conta {account} tem um saldo "
            "em aberto de {balance}. Você pode pagar on-line a qualquer momento. Obrigado por "
            "ser nosso cliente.",
        ),
    },
}


def wording_for(code: str, language: str) -> tuple[str | None, str] | None:
    """`(subject, body)` for one class in one language — the exact tag, else its
    primary language (`en-US` → `en`, `es-419` → `es`), else None."""
    table = WORDING.get(code) or {}
    if language in table:
        return table[language]
    primary = language.split("-", 1)[0]
    return table.get(primary)


__all__ = ["DEFAULT_WORDING_LANGUAGE", "PAST_DUE_LETTER", "WORDING", "wording_for"]
