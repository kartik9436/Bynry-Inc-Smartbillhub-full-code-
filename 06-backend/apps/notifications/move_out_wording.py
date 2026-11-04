# ── Trace ──────────────────────────────────────────────
# Defect:   DEF-NOT-10536 — the move-out final bill email
# Ruling:   PO 2026-10-22, decision log *"Move-out final bill email: sent at
#           completion with the draft figures, at normal priority (no instant
#           email); details and PDF filled in"*; our judgments in the entry
#           after it (point 6, the wording)
# Rules:    BR-NOT-006 (type × category × language variants) · BR-NOT-001
#           (the `default` variant is mandatory) · B14 rule 35 (a language is
#           written natively, not translated word for word from English) ·
#           CLAUDE.md hard rule 3 (every reading carries its unit — inside
#           `{final_read}`, one line per meter)
# Tests:    06-backend/tests/test_def_not_10536_move_out_final_email.py
# Impacts:  seed_templates.py (plants these as published variants) ·
#           catalogs.py (`email_move_out_final`'s palette and optional tokens) ·
#           migrations/0028 (republishes an unedited default, plants the rest)
# ───────────────────────────────────────────────────────
"""The SEEDED wording of the move-out final bill email, one variant per language.

HUMAN-OWNED · HUMAN-REVIEW-PENDING — this file decides **words a person
reads**, the authority `seed_templates.py` is guarded for. AI-authored
2026-10-22 under the PO ruling of 2026-08-09; row in
12-governance/09-human-review-ledger.md. **LANE-AUTHORED WORDING**: no signed
document writes these bodies. They are seeded DEFAULTS each utility edits on
Settings → Templates, and a later release only ADDS a missing variant — it
never overwrites one a utility has published (`seed_templates._seed_one` is
insert-missing).

The SHAPE is `agreement_wording`'s on purpose, so one seeder reads both:
template code → language tag → `(subject, body)`. The languages that EXIST are
the product's registry (`tenancy_seam.platform_languages`), never a list here.

THREE PARAGRAPHS ARE OPTIONAL, AND EACH IS ITS OWN PARAGRAPH FOR THAT REASON.
`catalogs` marks `{total_due}`, `{due_date}` and `{final_read}` optional, and
the renderer leaves out a whole blank-line paragraph whose optional token has
no value. So *"your final bill is attached, total due …"* is one paragraph (a
move-out with nothing left to bill has no bill to attach), and the closing
readings are another (a unit with no meter has none). A translation that merged
either into a neighbouring paragraph would drop that neighbour too.

THE GREETING follows `agreement_wording`: the informal languages greet
`{first_name}`; de, it-IT, ja-JP and ko-KR address the whole `{customer_name}`
in the formal register.
"""

from __future__ import annotations

DEFAULT_WORDING_LANGUAGE = "en"

MOVE_OUT_FINAL = "email_move_out_final"

WORDING: dict[str, dict[str, tuple[str, str]]] = {
    MOVE_OUT_FINAL: {
        "en": (
            "Your final {utility_name} bill for {service_address}",
            """Hi {first_name},

Your service at {service_address} ended on {service_end_date}.

Your final bill is attached. Total due {total_due} by {due_date}.

Closing meter readings:
{final_read}

Please make sure we have an address that reaches you, in case anything needs to come back to you after you have gone.

Questions about your final bill? Call {support_phone}. It is much easier to go through it with you now than in a few months.

{utility_name}""",
        ),
        "es": (
            "Tu última factura de {utility_name} para {service_address}",
            """Hola, {first_name}:

Tu servicio en {service_address} terminó el {service_end_date}.

Te adjuntamos tu última factura. Importe a pagar: {total_due}, antes del {due_date}.

Lecturas finales del contador:
{final_read}

Asegúrate de que tenemos una dirección donde localizarte, por si tenemos que enviarte algo cuando ya no estés.

¿Tienes alguna duda sobre la factura? Llámanos al {support_phone}. Es mucho más fácil revisarla contigo ahora que dentro de unos meses.

{utility_name}""",
        ),
        "es-MX": (
            "Tu último recibo de {utility_name} para {service_address}",
            """Hola, {first_name}:

Tu servicio en {service_address} terminó el {service_end_date}.

Te mandamos adjunto tu último recibo. Total a pagar: {total_due}, a más tardar el {due_date}.

Lecturas finales del medidor:
{final_read}

Confirma que tenemos una dirección donde encontrarte, por si necesitamos mandarte algo después de que te mudes.

¿Dudas sobre tu recibo? Llámanos al {support_phone}. Es mucho más fácil revisarlo contigo ahora que en unos meses.

{utility_name}""",
        ),
        "de": (
            "Ihre Schlussrechnung von {utility_name} für {service_address}",
            """Guten Tag {customer_name},

Ihre Versorgung unter {service_address} endete am {service_end_date}.

Im Anhang finden Sie Ihre Schlussrechnung. Zu zahlen sind {total_due} bis zum {due_date}.

Zählerstände bei Auszug:
{final_read}

Bitte stellen Sie sicher, dass uns eine Anschrift vorliegt, unter der wir Sie auch nach Ihrem Auszug erreichen.

Fragen zur Schlussrechnung? Rufen Sie uns an unter {support_phone}. Jetzt lässt sich alles viel leichter klären als in ein paar Monaten.

{utility_name}""",
        ),
        "hi": (
            "{service_address} के लिए {utility_name} का आपका अंतिम बिल",
            """नमस्ते {first_name},

{service_address} पर आपकी सेवा {service_end_date} को समाप्त हो गई।

आपका अंतिम बिल इस ईमेल के साथ संलग्न है। कुल देय राशि {total_due} है, जिसे {due_date} तक चुकाना है।

मीटर की अंतिम रीडिंग:
{final_read}

कृपया हमें ऐसा पता ज़रूर दें जिस पर आप जाने के बाद भी मिल सकें, ताकि कुछ भेजना हो तो आप तक पहुँच सके।

अंतिम बिल के बारे में कोई सवाल? {support_phone} पर कॉल करें। अभी आपके साथ इसे देख लेना कुछ महीनों बाद की तुलना में कहीं आसान है।

{utility_name}""",
        ),
        "fr-FR": (
            "Votre facture de clôture {utility_name} pour {service_address}",
            """Bonjour {first_name},

Votre service au {service_address} a pris fin le {service_end_date}.

Vous trouverez ci-joint votre facture de clôture. Montant à régler : {total_due}, avant le {due_date}.

Relevés de compteur au départ :
{final_read}

Assurez-vous que nous avons une adresse où vous joindre, au cas où nous devrions vous envoyer quelque chose après votre départ.

Une question sur cette facture ? Appelez-nous au {support_phone}. C'est bien plus simple d'en parler maintenant que dans quelques mois.

{utility_name}""",
        ),
        "id-ID": (
            "Tagihan terakhir {utility_name} Anda untuk {service_address}",
            """Halo {first_name},

Layanan Anda di {service_address} berakhir pada {service_end_date}.

Tagihan terakhir Anda terlampir. Total yang harus dibayar {total_due}, paling lambat {due_date}.

Angka meter terakhir:
{final_read}

Pastikan kami memiliki alamat yang bisa menjangkau Anda, kalau-kalau ada yang perlu kami kirimkan setelah Anda pindah.

Ada pertanyaan tentang tagihan terakhir ini? Hubungi kami di {support_phone}. Jauh lebih mudah membahasnya sekarang daripada beberapa bulan lagi.

{utility_name}""",
        ),
        "it-IT": (
            "La sua bolletta di chiusura {utility_name} per {service_address}",
            """Gentile {customer_name},

la sua fornitura in {service_address} è terminata il {service_end_date}.

In allegato trova la bolletta di chiusura. Importo da pagare: {total_due}, entro il {due_date}.

Letture finali del contatore:
{final_read}

Si assicuri che abbiamo un indirizzo a cui raggiungerla, nel caso dovessimo inviarle qualcosa dopo il trasloco.

Domande sulla bolletta di chiusura? Ci chiami al {support_phone}. È molto più semplice vederla insieme adesso che tra qualche mese.

{utility_name}""",
        ),
        "ja-JP": (
            "{service_address}の{utility_name}最終請求書",
            """{customer_name} 様

{service_address}でのご利用は{service_end_date}に終了いたしました。

最終請求書を添付しております。ご請求額は{total_due}、お支払期限は{due_date}です。

最終検針値:
{final_read}

お引っ越し後もご連絡が届く住所を、念のためお知らせください。

最終請求書についてご不明な点は、{support_phone} までお電話ください。数か月後よりも今のうちにご確認いただくほうが、ずっとスムーズです。

{utility_name}""",
        ),
        "ko-KR": (
            "{service_address}의 {utility_name} 최종 요금 청구서",
            """{customer_name} 님, 안녕하세요.

{service_address}의 서비스가 {service_end_date}에 종료되었습니다.

최종 청구서를 첨부해 드립니다. 납부하실 금액은 {total_due}이며, 납부 기한은 {due_date}입니다.

최종 계량기 검침값:
{final_read}

이사 후에도 연락드릴 수 있는 주소를 꼭 알려 주세요. 보내 드릴 것이 생길 수도 있습니다.

최종 청구서에 대해 궁금한 점은 {support_phone}(으)로 전화해 주세요. 몇 달 뒤보다 지금 함께 확인하는 편이 훨씬 수월합니다.

{utility_name}""",
        ),
        "pt-BR": (
            "Sua última conta da {utility_name} para {service_address}",
            """Olá, {first_name},

Seu serviço em {service_address} foi encerrado em {service_end_date}.

Segue em anexo a sua última conta. Total a pagar: {total_due}, até {due_date}.

Leituras finais do medidor:
{final_read}

Confirme se temos um endereço onde possamos encontrar você, caso precisemos enviar algo depois da sua mudança.

Dúvidas sobre a última conta? Ligue para {support_phone}. É muito mais fácil ver isso com você agora do que daqui a alguns meses.

{utility_name}""",
        ),
    },
}


def wording_for(code: str, language: str) -> tuple[str, str] | None:
    """`(subject, body)` for one class in one language — the exact tag, else its
    primary language (`en-US` → `en`, `es-419` → `es`), else None."""
    table = WORDING.get(code) or {}
    if language in table:
        return table[language]
    primary = language.split("-", 1)[0]
    return table.get(primary)


__all__ = ["DEFAULT_WORDING_LANGUAGE", "MOVE_OUT_FINAL", "WORDING", "wording_for"]
