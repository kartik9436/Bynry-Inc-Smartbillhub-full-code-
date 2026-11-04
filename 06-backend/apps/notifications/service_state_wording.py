# ── Trace ──────────────────────────────────────────────
# Defect:   DEF-NOT-10649 — after *Mark as cut* the customer was told nothing,
#           and nothing when service was restored
# Ruling:   PO 2026-10-29, verbatim *"1 A, 2 A, 3 A, 4 A"* then *"start"* —
#           (4A) *we write a short default safety text, each utility edits it
#           in Settings › Templates* (decision log *"A cut and a restoration
#           TELL THE CUSTOMER"*)
# Rules:    BR-NOT-006 (type × category × language variants) · BR-NOT-001
#           (the `default` variant is mandatory) · B14 rule 35 (a language is
#           written natively, not translated word for word from English) ·
#           CLAUDE.md hard rule 3 (every reading carries its unit — inside
#           `{final_read}`, one line per meter) · hard rule 2 (every figure is
#           a token the renderer writes at 2 places in the utility's currency)
# Tests:    06-backend/tests/test_def_not_10649_cut_restore_notices.py ·
#           06-backend/tests/test_def_210_authored_template_bodies.py (palette,
#           the 160-character SMS counter, no unruled figure)
# Impacts:  seed_templates.py (plants these as published variants) ·
#           catalogs.py (the four classes' palettes and optional tokens)
# ───────────────────────────────────────────────────────
"""The SEEDED wording of the two post-ladder messages, one variant per language.

HUMAN-OWNED · HUMAN-REVIEW-PENDING — this file decides **words a person
reads**, the authority `seed_templates.py` is guarded for. AI-authored
2026-10-29 under the PO ruling of that date (4A: *"we write a short default
safety text, each utility edits it"*); row in
12-governance/09-human-review-ledger.md. **LANE-AUTHORED WORDING**: no signed
document writes these bodies. They are seeded DEFAULTS each utility edits on
Settings → Templates, and a later release only ADDS a missing variant — it
never overwrites one a utility has published (`seed_templates._seed_one` is
insert-missing).

The SHAPE is `move_out_wording`'s, so one seeder reads both: template code →
language tag → `(subject, body)`; an SMS class has no subject (`None`).

WHAT THE SAFETY TEXT SAYS, AND WHAT IT DELIBERATELY DOES NOT
────────────────────────────────────────────────────────────────────────────
The PO's four sentences and nothing else: keep taps and valves closed until
service is restored; do not reconnect it yourself — it is unsafe and an
offence; a medical or critical-care need → call the utility; once restored,
open taps slowly and report a leak or the smell of gas. **No fee, no figure,
no deadline and no regulator is named in prose** — every amount is a token
the renderer fills from the cut's own record (`test_def_210`'s
`UNRULED_PHRASES` is the check).

TWO PARAGRAPHS ARE OPTIONAL, AND EACH IS ITS OWN PARAGRAPH FOR THAT REASON.
`catalogs` marks `{final_read}` and `{restoration_link}` optional on the email
classes, and the renderer leaves out a whole blank-line paragraph whose
optional token has no value — a unit with no meter has no closing reading, and
a deployment with no public address has no link to print (law 3: never a
relative link). A translation that merged either into a neighbouring paragraph
would drop that neighbour too. **The SMS bodies carry no optional token**: an
SMS is one paragraph, and dropping it would drop the whole message.

THE GREETING follows `move_out_wording`: the informal languages greet
`{first_name}`; de, it-IT, ja-JP and ko-KR address the whole `{customer_name}`
in the formal register.
"""

from __future__ import annotations

DEFAULT_WORDING_LANGUAGE = "en"

SERVICE_DISCONNECTED = "service_disconnected_guide"
SERVICE_DISCONNECTED_SMS = "sms_service_disconnected"
SERVICE_RESTORED = "service_restored"
SERVICE_RESTORED_SMS = "sms_service_restored"

WORDING: dict[str, dict[str, tuple[str | None, str]]] = {
    SERVICE_DISCONNECTED: {
        "en": (
            "Your {utility_name} service at {service_address} has been disconnected",
            """Hi {first_name},

Your service at {service_address} (account {account_no}) was disconnected on {cut_date}.

Closing meter readings:
{final_read}

To restore your service:
Balance owed {balance_owed}
Reconnection fee {reconnect_fee}
Total to restore {total_to_restore}

Pay online at {restoration_link}

For your safety:
Keep taps and valves closed until your service is restored.
Do not reconnect the service yourself. It is unsafe and an offence.
If anyone in your home relies on medical or critical-care equipment, call {support_phone} now.

Questions? Call {support_phone}.

{utility_name}""",
        ),
        "es": (
            "Tu servicio de {utility_name} en {service_address} ha sido cortado",
            """Hola, {first_name}:

Tu servicio en {service_address} (cuenta {account_no}) se cortó el {cut_date}.

Lecturas finales del contador:
{final_read}

Para recuperar el servicio:
Saldo pendiente {balance_owed}
Cargo por reconexión {reconnect_fee}
Total para restablecerlo {total_to_restore}

Puedes pagar en línea en {restoration_link}

Por tu seguridad:
Mantén cerrados los grifos y las llaves de paso hasta que se restablezca el servicio.
No vuelvas a conectar el servicio por tu cuenta. Es peligroso y constituye una infracción.
Si alguien en tu casa depende de un equipo médico o de soporte vital, llama ya al {support_phone}.

¿Dudas? Llama al {support_phone}.

{utility_name}""",
        ),
        "es-MX": (
            "Se suspendió tu servicio de {utility_name} en {service_address}",
            """Hola, {first_name}:

Tu servicio en {service_address} (cuenta {account_no}) se suspendió el {cut_date}.

Lecturas finales del medidor:
{final_read}

Para que te reconectemos:
Saldo pendiente {balance_owed}
Cargo por reconexión {reconnect_fee}
Total para reconectar {total_to_restore}

Paga en línea en {restoration_link}

Por tu seguridad:
Mantén cerradas las llaves y válvulas hasta que se restablezca el servicio.
No reconectes el servicio tú mismo. Es peligroso y es una infracción.
Si alguien en tu casa depende de un equipo médico o de soporte vital, llámanos ya al {support_phone}.

¿Dudas? Llámanos al {support_phone}.

{utility_name}""",
        ),
        "de": (
            "Ihre Versorgung durch {utility_name} unter {service_address} wurde gesperrt",
            """Guten Tag {customer_name},

Ihre Versorgung unter {service_address} (Kundennummer {account_no}) wurde am {cut_date} gesperrt.

Zählerstände bei der Sperrung:
{final_read}

So wird Ihre Versorgung wiederhergestellt:
Offener Betrag {balance_owed}
Gebühr für die Wiederinbetriebnahme {reconnect_fee}
Gesamtbetrag {total_to_restore}

Online bezahlen: {restoration_link}

Zu Ihrer Sicherheit:
Lassen Sie Wasserhähne und Ventile geschlossen, bis die Versorgung wiederhergestellt ist.
Stellen Sie den Anschluss nicht selbst wieder her. Das ist gefährlich und strafbar.
Ist jemand in Ihrem Haushalt auf medizinische oder lebenserhaltende Geräte angewiesen, rufen Sie bitte sofort {support_phone} an.

Fragen? Rufen Sie uns an unter {support_phone}.

{utility_name}""",
        ),
        "hi": (
            "{service_address} पर आपकी {utility_name} सेवा काट दी गई है",
            """नमस्ते {first_name},

{service_address} (खाता {account_no}) पर आपकी सेवा {cut_date} को काट दी गई।

मीटर की अंतिम रीडिंग:
{final_read}

सेवा फिर से शुरू करवाने के लिए:
बकाया राशि {balance_owed}
दोबारा कनेक्शन शुल्क {reconnect_fee}
कुल देय राशि {total_to_restore}

ऑनलाइन भुगतान करें: {restoration_link}

आपकी सुरक्षा के लिए:
सेवा दोबारा शुरू होने तक नल और वाल्व बंद रखें।
सेवा को खुद दोबारा न जोड़ें। यह खतरनाक है और कानूनन अपराध है।
अगर आपके घर में कोई चिकित्सा या जीवन-रक्षक उपकरण पर निर्भर है, तो तुरंत {support_phone} पर कॉल करें।

कोई सवाल? {support_phone} पर कॉल करें।

{utility_name}""",
        ),
        "fr-FR": (
            "Votre service {utility_name} au {service_address} a été coupé",
            """Bonjour {first_name},

Votre service au {service_address} (compte {account_no}) a été coupé le {cut_date}.

Relevés de compteur à la coupure :
{final_read}

Pour rétablir votre service :
Solde dû {balance_owed}
Frais de remise en service {reconnect_fee}
Total à régler {total_to_restore}

Payez en ligne sur {restoration_link}

Pour votre sécurité :
Gardez les robinets et les vannes fermés jusqu'au rétablissement du service.
Ne rétablissez pas le branchement vous-même. C'est dangereux et c'est une infraction.
Si une personne de votre foyer dépend d'un appareil médical ou vital, appelez tout de suite le {support_phone}.

Une question ? Appelez-nous au {support_phone}.

{utility_name}""",
        ),
        "id-ID": (
            "Layanan {utility_name} Anda di {service_address} telah diputus",
            """Halo {first_name},

Layanan Anda di {service_address} (rekening {account_no}) diputus pada {cut_date}.

Angka meter terakhir:
{final_read}

Untuk menyambung kembali layanan Anda:
Tunggakan {balance_owed}
Biaya penyambungan kembali {reconnect_fee}
Total yang harus dibayar {total_to_restore}

Bayar secara online di {restoration_link}

Demi keselamatan Anda:
Biarkan keran dan katup tetap tertutup sampai layanan tersambung kembali.
Jangan menyambung layanan sendiri. Itu berbahaya dan merupakan pelanggaran hukum.
Jika ada anggota keluarga yang bergantung pada alat medis atau alat penunjang hidup, segera hubungi {support_phone}.

Ada pertanyaan? Hubungi {support_phone}.

{utility_name}""",
        ),
        "it-IT": (
            "La sua fornitura {utility_name} in {service_address} è stata sospesa",
            """Gentile {customer_name},

la sua fornitura in {service_address} (codice cliente {account_no}) è stata sospesa il {cut_date}.

Letture finali del contatore:
{final_read}

Per riattivare la fornitura:
Importo da saldare {balance_owed}
Costo di riattivazione {reconnect_fee}
Totale per la riattivazione {total_to_restore}

Può pagare online su {restoration_link}

Per la sua sicurezza:
Tenga chiusi rubinetti e valvole finché la fornitura non viene riattivata.
Non ricolleghi la fornitura da solo. È pericoloso e costituisce un reato.
Se in casa qualcuno dipende da apparecchiature mediche o salvavita, chiami subito il {support_phone}.

Domande? Ci chiami al {support_phone}.

{utility_name}""",
        ),
        "ja-JP": (
            "{service_address}の{utility_name}の供給を停止しました",
            """{customer_name} 様

{service_address}(お客様番号 {account_no})への供給を{cut_date}に停止いたしました。

停止時の検針値:
{final_read}

供給再開のために必要な金額:
未払い残高 {balance_owed}
再開手数料 {reconnect_fee}
合計 {total_to_restore}

オンラインでのお支払い: {restoration_link}

安全のために:
供給が再開されるまで、蛇口やバルブは閉めたままにしてください。
ご自身で再接続しないでください。危険であり、法律違反となります。
ご家族に医療機器や生命維持装置をお使いの方がいらっしゃる場合は、すぐに {support_phone} までお電話ください。

ご不明な点は {support_phone} までお電話ください。

{utility_name}""",
        ),
        "ko-KR": (
            "{service_address}의 {utility_name} 공급이 중단되었습니다",
            """{customer_name} 님, 안녕하세요.

{service_address}(고객번호 {account_no})의 공급이 {cut_date}에 중단되었습니다.

중단 시점 계량기 검침값:
{final_read}

공급을 재개하려면:
미납 금액 {balance_owed}
재연결 수수료 {reconnect_fee}
재개에 필요한 총액 {total_to_restore}

온라인 납부: {restoration_link}

안전을 위해:
공급이 재개될 때까지 수도꼭지와 밸브를 잠가 두세요.
직접 다시 연결하지 마세요. 위험하며 법에 저촉됩니다.
가족 중 의료기기나 생명유지 장치를 사용하는 분이 있다면 즉시 {support_phone}(으)로 전화해 주세요.

궁금한 점은 {support_phone}(으)로 전화해 주세요.

{utility_name}""",
        ),
        "pt-BR": (
            "Seu serviço da {utility_name} em {service_address} foi desligado",
            """Olá, {first_name},

Seu serviço em {service_address} (conta {account_no}) foi desligado em {cut_date}.

Leituras finais do medidor:
{final_read}

Para religar o serviço:
Saldo devedor {balance_owed}
Taxa de religação {reconnect_fee}
Total para religar {total_to_restore}

Pague on-line em {restoration_link}

Para sua segurança:
Mantenha torneiras e registros fechados até o serviço ser religado.
Não religue o serviço por conta própria. É perigoso e é uma infração.
Se alguém na sua casa depende de equipamento médico ou de suporte à vida, ligue agora para {support_phone}.

Dúvidas? Ligue para {support_phone}.

{utility_name}""",
        ),
    },
    SERVICE_RESTORED: {
        "en": (
            "Your {utility_name} service at {service_address} is back on",
            """Hi {first_name},

Your service at {service_address} (account {account_no}) was restored on {restored_at}.

As your service comes back on:
Open taps slowly and let the water run until it is clear.
If you see a leak or smell gas, leave the property and call {support_phone}.

Questions? Call {support_phone}.

{utility_name}""",
        ),
        "es": (
            "Tu servicio de {utility_name} en {service_address} vuelve a funcionar",
            """Hola, {first_name}:

Tu servicio en {service_address} (cuenta {account_no}) se restableció el {restored_at}.

Ahora que vuelve el servicio:
Abre los grifos poco a poco y deja correr el agua hasta que salga limpia.
Si ves una fuga o huele a gas, sal de la vivienda y llama al {support_phone}.

¿Dudas? Llama al {support_phone}.

{utility_name}""",
        ),
        "es-MX": (
            "Ya se reconectó tu servicio de {utility_name} en {service_address}",
            """Hola, {first_name}:

Tu servicio en {service_address} (cuenta {account_no}) se reconectó el {restored_at}.

Ahora que regresa el servicio:
Abre las llaves despacio y deja correr el agua hasta que salga clara.
Si ves una fuga o hueles a gas, sal de la casa y llámanos al {support_phone}.

¿Dudas? Llámanos al {support_phone}.

{utility_name}""",
        ),
        "de": (
            "Ihre Versorgung durch {utility_name} unter {service_address} ist wiederhergestellt",
            """Guten Tag {customer_name},

Ihre Versorgung unter {service_address} (Kundennummer {account_no}) wurde am {restored_at} wiederhergestellt.

Wenn die Versorgung wieder anläuft:
Öffnen Sie die Wasserhähne langsam und lassen Sie das Wasser laufen, bis es klar ist.
Bemerken Sie ein Leck oder riecht es nach Gas, verlassen Sie das Gebäude und rufen Sie {support_phone} an.

Fragen? Rufen Sie uns an unter {support_phone}.

{utility_name}""",
        ),
        "hi": (
            "{service_address} पर आपकी {utility_name} सेवा फिर से शुरू हो गई है",
            """नमस्ते {first_name},

{service_address} (खाता {account_no}) पर आपकी सेवा {restored_at} को फिर से शुरू कर दी गई।

सेवा दोबारा शुरू होने पर:
नल धीरे-धीरे खोलें और पानी साफ़ आने तक बहने दें।
अगर कहीं रिसाव दिखे या गैस की गंध आए, तो घर से बाहर निकलें और {support_phone} पर कॉल करें।

कोई सवाल? {support_phone} पर कॉल करें।

{utility_name}""",
        ),
        "fr-FR": (
            "Votre service {utility_name} au {service_address} est rétabli",
            """Bonjour {first_name},

Votre service au {service_address} (compte {account_no}) a été rétabli le {restored_at}.

À la remise en service :
Ouvrez les robinets doucement et laissez couler l'eau jusqu'à ce qu'elle soit claire.
En cas de fuite ou d'odeur de gaz, quittez le logement et appelez le {support_phone}.

Une question ? Appelez-nous au {support_phone}.

{utility_name}""",
        ),
        "id-ID": (
            "Layanan {utility_name} Anda di {service_address} sudah tersambung kembali",
            """Halo {first_name},

Layanan Anda di {service_address} (rekening {account_no}) tersambung kembali pada {restored_at}.

Saat layanan kembali menyala:
Buka keran perlahan dan biarkan air mengalir sampai jernih.
Jika ada kebocoran atau tercium bau gas, tinggalkan rumah dan hubungi {support_phone}.

Ada pertanyaan? Hubungi {support_phone}.

{utility_name}""",
        ),
        "it-IT": (
            "La sua fornitura {utility_name} in {service_address} è stata riattivata",
            """Gentile {customer_name},

la sua fornitura in {service_address} (codice cliente {account_no}) è stata riattivata il {restored_at}.

Alla riattivazione:
Apra i rubinetti lentamente e lasci scorrere l'acqua finché non è limpida.
Se nota una perdita o sente odore di gas, esca dall'abitazione e chiami il {support_phone}.

Domande? Ci chiami al {support_phone}.

{utility_name}""",
        ),
        "ja-JP": (
            "{service_address}の{utility_name}の供給を再開しました",
            """{customer_name} 様

{service_address}(お客様番号 {account_no})への供給を{restored_at}に再開いたしました。

供給再開にあたって:
蛇口はゆっくり開け、水が澄むまで流してください。
水漏れやガスのにおいに気づいたら、建物の外に出て {support_phone} までお電話ください。

ご不明な点は {support_phone} までお電話ください。

{utility_name}""",
        ),
        "ko-KR": (
            "{service_address}의 {utility_name} 공급이 재개되었습니다",
            """{customer_name} 님, 안녕하세요.

{service_address}(고객번호 {account_no})의 공급이 {restored_at}에 재개되었습니다.

공급이 다시 시작되면:
수도꼭지를 천천히 열고 물이 맑아질 때까지 흘려 보내세요.
누수가 보이거나 가스 냄새가 나면 집 밖으로 나간 뒤 {support_phone}(으)로 전화해 주세요.

궁금한 점은 {support_phone}(으)로 전화해 주세요.

{utility_name}""",
        ),
        "pt-BR": (
            "Seu serviço da {utility_name} em {service_address} foi religado",
            """Olá, {first_name},

Seu serviço em {service_address} (conta {account_no}) foi religado em {restored_at}.

Agora que o serviço voltou:
Abra as torneiras devagar e deixe a água correr até ficar limpa.
Se notar um vazamento ou cheiro de gás, saia do imóvel e ligue para {support_phone}.

Dúvidas? Ligue para {support_phone}.

{utility_name}""",
        ),
    },
    # ── SMS — no subject, one paragraph, under CR-007's 160-character counter ──
    SERVICE_DISCONNECTED_SMS: {
        "en": (
            None,
            "{utility_name}: service cut {cut_date}. Pay {total_to_restore} to restore. "
            "Do not reconnect it yourself. Medical need? Call {support_phone}.",
        ),
        "es": (
            None,
            "{utility_name}: servicio cortado el {cut_date}. Paga {total_to_restore} para "
            "recuperarlo. No lo reconectes tú. ¿Urgencia médica? {support_phone}",
        ),
        "es-MX": (
            None,
            "{utility_name}: servicio suspendido el {cut_date}. Paga {total_to_restore} para "
            "reconectar. No lo reconectes tú. ¿Urgencia médica? {support_phone}",
        ),
        "de": (
            None,
            "{utility_name}: Versorgung am {cut_date} gesperrt. Zur Freigabe "
            "{total_to_restore} zahlen. Nicht selbst anschließen. Medizinischer Notfall: "
            "{support_phone}",
        ),
        "hi": (
            None,
            "{utility_name}: सेवा {cut_date} को काटी गई। दोबारा शुरू करने के लिए "
            "{total_to_restore} चुकाएँ। खुद न जोड़ें। चिकित्सा ज़रूरत? {support_phone}",
        ),
        "fr-FR": (
            None,
            "{utility_name} : service coupé le {cut_date}. Réglez {total_to_restore} pour "
            "le rétablir. Ne rebranchez pas vous-même. Besoin médical ? {support_phone}",
        ),
        "id-ID": (
            None,
            "{utility_name}: layanan diputus {cut_date}. Bayar {total_to_restore} untuk "
            "menyambung kembali. Jangan sambung sendiri. Darurat medis? {support_phone}",
        ),
        "it-IT": (
            None,
            "{utility_name}: fornitura sospesa il {cut_date}. Paghi {total_to_restore} "
            "per riattivarla. Non la ricolleghi da solo. Necessità mediche: {support_phone}",
        ),
        "ja-JP": (
            None,
            "{utility_name}:{cut_date}に供給を停止しました。再開には{total_to_restore}の"
            "お支払いが必要です。ご自身で再接続しないでください。医療上の緊急時は{support_phone}へ",
        ),
        "ko-KR": (
            None,
            "{utility_name}: {cut_date}에 공급이 중단되었습니다. 재개하려면 "
            "{total_to_restore}을(를) 납부하세요. 직접 연결하지 마세요. 의료 긴급 시 {support_phone}",
        ),
        "pt-BR": (
            None,
            "{utility_name}: serviço desligado em {cut_date}. Pague {total_to_restore} para "
            "religar. Não religue por conta própria. Urgência médica? {support_phone}",
        ),
    },
    SERVICE_RESTORED_SMS: {
        "en": (
            None,
            "{utility_name}: your service is back on. Open taps slowly. Leak or smell of "
            "gas? Call {support_phone}.",
        ),
        "es": (
            None,
            "{utility_name}: tu servicio vuelve a funcionar. Abre los grifos poco a poco. "
            "¿Fuga u olor a gas? Llama al {support_phone}.",
        ),
        "es-MX": (
            None,
            "{utility_name}: ya se reconectó tu servicio. Abre las llaves despacio. ¿Fuga u "
            "olor a gas? Llámanos al {support_phone}.",
        ),
        "de": (
            None,
            "{utility_name}: Ihre Versorgung ist wiederhergestellt. Hähne langsam öffnen. "
            "Leck oder Gasgeruch? Rufen Sie {support_phone} an.",
        ),
        "hi": (
            None,
            "{utility_name}: आपकी सेवा फिर से शुरू हो गई है। नल धीरे खोलें। रिसाव या "
            "गैस की गंध? {support_phone} पर कॉल करें।",
        ),
        "fr-FR": (
            None,
            "{utility_name} : votre service est rétabli. Ouvrez les robinets doucement. "
            "Fuite ou odeur de gaz ? Appelez le {support_phone}.",
        ),
        "id-ID": (
            None,
            "{utility_name}: layanan Anda sudah tersambung kembali. Buka keran perlahan. "
            "Bocor atau bau gas? Hubungi {support_phone}.",
        ),
        "it-IT": (
            None,
            "{utility_name}: la fornitura è riattivata. Apra i rubinetti lentamente. "
            "Perdite o odore di gas? Chiami il {support_phone}.",
        ),
        "ja-JP": (
            None,
            "{utility_name}:供給を再開しました。蛇口はゆっくり開けてください。"
            "水漏れやガスのにおいがあれば{support_phone}へ",
        ),
        "ko-KR": (
            None,
            "{utility_name}: 공급이 재개되었습니다. 수도꼭지를 천천히 여세요. 누수나 가스 "
            "냄새가 나면 {support_phone}(으)로 전화하세요.",
        ),
        "pt-BR": (
            None,
            "{utility_name}: seu serviço foi religado. Abra as torneiras devagar. Vazamento "
            "ou cheiro de gás? Ligue para {support_phone}.",
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


__all__ = [
    "DEFAULT_WORDING_LANGUAGE",
    "SERVICE_DISCONNECTED",
    "SERVICE_DISCONNECTED_SMS",
    "SERVICE_RESTORED",
    "SERVICE_RESTORED_SMS",
    "WORDING",
    "wording_for",
]
