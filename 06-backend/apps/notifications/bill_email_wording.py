# ── Trace ──────────────────────────────────────────────
# Defect:   DEF-BIL-10531 — the bill-ready email said "it is attached to this
#           email" and nothing was attached
# Ruling:   PO 2026-10-22, decision log *"Bill email sends a link instead of the
#           PDF"* (*"can't we sent link instead"*) and *"The bill email's link
#           opens the bill PDF directly, with no sign-in"* (*"b direct PDF
#           link"*): the sentence goes and a link line takes its place, in the
#           bill-ready AND the corrected-bill email
# Rules:    BR-NOT-006 (type × category × language variants) · BR-NOT-001 (the
#           `default` variant is mandatory) · B14 rule 35 (a language is
#           written natively, not translated word for word from English)
# Tests:    06-backend/tests/test_def_bil_10531_bill_link.py
# Impacts:  seed_templates.py (plants these; `en` is each class's `default`) ·
#           catalogs.py (`{bill_link}` / `{link_expires_on}`, optional) ·
#           migrations/0030 (republishes an unedited default, plants the rest)
# ───────────────────────────────────────────────────────
"""The SEEDED wording of the two bill emails, one variant per language.

HUMAN-OWNED · HUMAN-REVIEW-PENDING — this file decides **words a person
reads**, the authority `seed_templates.py` is guarded for. AI-authored
2026-10-22 under the PO ruling of 2026-08-09; row in
12-governance/09-human-review-ledger.md. **LANE-AUTHORED WORDING** for every
language but the English, which is the A13/A19-shaped body the product has
seeded since 2026-08-15 with one sentence replaced. They are seeded DEFAULTS
each utility edits on Settings → Templates; a later release only ADDS a missing
variant and never overwrites one a utility has published.

The SHAPE is `move_out_wording`'s, so one seeder reads all of them.

⚠ **THE LINK IS ITS OWN PARAGRAPH, AND THAT IS LOAD-BEARING.** `{bill_link}`
and `{link_expires_on}` are optional in `catalogs`: a host with no public
address cannot build the link, and the renderer then leaves out the whole
blank-line paragraph that carries them. A translation that merged the link into
a neighbouring paragraph would drop that neighbour too.

THE GREETING follows `move_out_wording`: the informal languages greet
`{first_name}`; de, it-IT, ja-JP and ko-KR address `{customer_name}` formally.
"""

from __future__ import annotations

DEFAULT_WORDING_LANGUAGE = "en"

BILL_READY = "email_bill_ready"
CORRECTED_BILL = "email_corrected_bill"

WORDING: dict[str, dict[str, tuple[str, str]]] = {
    BILL_READY: {
        "en": (
            "Your {utility_name} bill is ready — {total_due} due {due_date}",
            """Hi {first_name},

Your bill for {service_address} is ready.

Bill {bill_no}, billed {bill_date}
Service period {period_start} to {period_end}

Previous balance {prev_balance}
Payments received {payments}
Current charges {current_charges}
Total due {total_due} by {due_date}

View or download your bill: {bill_link}
This link works until {link_expires_on}.

You can view it or pay at {utility_website}.

If anything on it looks wrong, call {support_phone} or write to {support_email}. We
would much rather explain a charge than have you wonder about it.

{utility_name}""",
        ),
        "es": (
            "Tu factura de {utility_name} ya está disponible: {total_due}, vence el {due_date}",
            """Hola, {first_name}:

Ya tienes disponible tu factura de {service_address}.

Factura {bill_no}, emitida el {bill_date}
Periodo de suministro: del {period_start} al {period_end}

Saldo anterior: {prev_balance}
Pagos recibidos: {payments}
Importe de este periodo: {current_charges}
Total a pagar: {total_due}, antes del {due_date}

Consulta o descarga tu factura: {bill_link}
Este enlace funciona hasta el {link_expires_on}.

También puedes consultarla o pagarla en {utility_website}.

Si algo no te cuadra, llámanos al {support_phone} o escríbenos a {support_email}. Preferimos explicarte un cargo antes que dejarte con la duda.

{utility_name}""",
        ),
        "es-MX": (
            "Tu recibo de {utility_name} está listo: {total_due}, a más tardar el {due_date}",
            """Hola, {first_name}:

Tu recibo de {service_address} ya está listo.

Recibo {bill_no}, emitido el {bill_date}
Periodo de servicio: del {period_start} al {period_end}

Saldo anterior: {prev_balance}
Pagos recibidos: {payments}
Cargos del periodo: {current_charges}
Total a pagar: {total_due}, a más tardar el {due_date}

Ve o descarga tu recibo: {bill_link}
Este enlace funciona hasta el {link_expires_on}.

También puedes verlo o pagarlo en {utility_website}.

Si algo no te cuadra, llámanos al {support_phone} o escríbenos a {support_email}. Preferimos explicarte un cargo a que te quedes con la duda.

{utility_name}""",
        ),
        "de": (
            "Ihre Rechnung von {utility_name} ist da – {total_due} fällig am {due_date}",
            """Guten Tag {customer_name},

Ihre Rechnung für {service_address} liegt vor.

Rechnung {bill_no} vom {bill_date}
Abrechnungszeitraum {period_start} bis {period_end}

Vorheriger Saldo: {prev_balance}
Eingegangene Zahlungen: {payments}
Aktuelle Kosten: {current_charges}
Zu zahlen: {total_due} bis zum {due_date}

Rechnung ansehen oder herunterladen: {bill_link}
Der Link ist bis zum {link_expires_on} gültig.

Sie können die Rechnung auch unter {utility_website} ansehen und bezahlen.

Wenn Ihnen etwas daran nicht stimmig erscheint, rufen Sie uns an unter {support_phone} oder schreiben Sie an {support_email}. Wir erklären eine Position lieber, als Sie im Unklaren zu lassen.

{utility_name}""",
        ),
        "hi": (
            "{utility_name} का आपका बिल तैयार है — {total_due}, {due_date} तक देय",
            """नमस्ते {first_name},

{service_address} का आपका बिल तैयार है।

बिल {bill_no}, बिल तिथि {bill_date}
सेवा अवधि {period_start} से {period_end}

पिछला बकाया: {prev_balance}
प्राप्त भुगतान: {payments}
इस अवधि के शुल्क: {current_charges}
कुल देय: {total_due}, {due_date} तक

अपना बिल देखें या डाउनलोड करें: {bill_link}
यह लिंक {link_expires_on} तक काम करेगा।

आप {utility_website} पर भी बिल देख या चुका सकते हैं।

अगर बिल में कुछ गलत लगे, तो {support_phone} पर कॉल करें या {support_email} पर लिखें। कोई भी शुल्क समझाने में हमें खुशी होगी, ताकि आपके मन में कोई सवाल न रहे।

{utility_name}""",
        ),
        "fr-FR": (
            "Votre facture {utility_name} est disponible : {total_due} à régler avant le {due_date}",
            """Bonjour {first_name},

Votre facture pour {service_address} est disponible.

Facture {bill_no} du {bill_date}
Période de service du {period_start} au {period_end}

Solde précédent : {prev_balance}
Paiements reçus : {payments}
Montant de la période : {current_charges}
Total à régler : {total_due}, avant le {due_date}

Consultez ou téléchargez votre facture : {bill_link}
Ce lien est valable jusqu'au {link_expires_on}.

Vous pouvez aussi la consulter ou la régler sur {utility_website}.

Si quelque chose vous semble anormal, appelez-nous au {support_phone} ou écrivez-nous à {support_email}. Nous préférons vous expliquer un montant plutôt que de vous laisser dans le doute.

{utility_name}""",
        ),
        "id-ID": (
            "Tagihan {utility_name} Anda sudah terbit — {total_due}, jatuh tempo {due_date}",
            """Halo {first_name},

Tagihan Anda untuk {service_address} sudah terbit.

Tagihan {bill_no}, tanggal {bill_date}
Periode layanan {period_start} sampai {period_end}

Saldo sebelumnya: {prev_balance}
Pembayaran diterima: {payments}
Biaya periode ini: {current_charges}
Total tagihan: {total_due}, paling lambat {due_date}

Lihat atau unduh tagihan Anda: {bill_link}
Tautan ini berlaku sampai {link_expires_on}.

Anda juga bisa melihat atau membayarnya di {utility_website}.

Kalau ada yang terasa keliru, hubungi kami di {support_phone} atau kirim email ke {support_email}. Kami lebih senang menjelaskan sebuah biaya daripada membiarkan Anda bertanya-tanya.

{utility_name}""",
        ),
        "it-IT": (
            "La sua bolletta {utility_name} è disponibile: {total_due} entro il {due_date}",
            """Gentile {customer_name},

la sua bolletta per {service_address} è disponibile.

Bolletta {bill_no} del {bill_date}
Periodo di fornitura dal {period_start} al {period_end}

Saldo precedente: {prev_balance}
Pagamenti ricevuti: {payments}
Importo del periodo: {current_charges}
Totale da pagare: {total_due}, entro il {due_date}

Visualizzi o scarichi la bolletta: {bill_link}
Il link è valido fino al {link_expires_on}.

Può anche consultarla o pagarla su {utility_website}.

Se qualcosa non le torna, ci chiami al {support_phone} o ci scriva a {support_email}. Preferiamo spiegarle una voce piuttosto che lasciarle un dubbio.

{utility_name}""",
        ),
        "ja-JP": (
            "{utility_name}のご請求書を発行しました（{total_due}、お支払期限 {due_date}）",
            """{customer_name} 様

{service_address}のご請求書を発行いたしました。

請求書番号 {bill_no}（発行日 {bill_date}）
ご利用期間 {period_start}〜{period_end}

前回までの残高: {prev_balance}
お支払い済み金額: {payments}
今回のご請求額: {current_charges}
お支払い合計: {total_due}（お支払期限 {due_date}）

ご請求書の表示・ダウンロード: {bill_link}
このリンクは{link_expires_on}までご利用いただけます。

{utility_website} からもご確認・お支払いいただけます。

内容にお気づきの点がございましたら、{support_phone} までお電話いただくか、{support_email} までご連絡ください。どの項目についても喜んでご説明いたします。

{utility_name}""",
        ),
        "ko-KR": (
            "{utility_name} 요금 청구서가 발행되었습니다 — {total_due}, 납부 기한 {due_date}",
            """{customer_name} 님, 안녕하세요.

{service_address}의 요금 청구서가 발행되었습니다.

청구서 {bill_no}, 발행일 {bill_date}
사용 기간 {period_start} ~ {period_end}

이전 잔액: {prev_balance}
납부하신 금액: {payments}
이번 기간 요금: {current_charges}
납부하실 금액: {total_due}, 납부 기한 {due_date}

청구서 보기 및 내려받기: {bill_link}
이 링크는 {link_expires_on}까지 사용하실 수 있습니다.

{utility_website}에서도 확인하고 납부하실 수 있습니다.

청구서에 이상한 점이 있으면 {support_phone}(으)로 전화하시거나 {support_email}(으)로 문의해 주세요. 궁금한 요금은 언제든 기꺼이 설명해 드리겠습니다.

{utility_name}""",
        ),
        "pt-BR": (
            "Sua conta da {utility_name} chegou — {total_due}, vence em {due_date}",
            """Olá, {first_name},

Sua conta de {service_address} já está disponível.

Conta {bill_no}, emitida em {bill_date}
Período de serviço de {period_start} a {period_end}

Saldo anterior: {prev_balance}
Pagamentos recebidos: {payments}
Valor deste período: {current_charges}
Total a pagar: {total_due}, até {due_date}

Veja ou baixe sua conta: {bill_link}
Este link funciona até {link_expires_on}.

Você também pode ver ou pagar em {utility_website}.

Se algo parecer errado, ligue para {support_phone} ou escreva para {support_email}. Preferimos explicar uma cobrança a deixar você na dúvida.

{utility_name}""",
        ),
    },
    CORRECTED_BILL: {
        "en": (
            "We have corrected your {utility_name} bill {bill_no}",
            """Hi {first_name},

We have corrected bill {bill_no} for {service_address}. The corrected bill
replaces the one we sent you.

View or download the corrected bill: {bill_link}
This link works until {link_expires_on}.

What changed: {correction_reason}
Original total {original_total}
Corrected total {total_due}

Your due date is still {due_date}. If you pay by autopay, we will collect the
corrected amount.

Sorry for the confusion. If the new figure still does not look right, call
{support_phone} and we will go through the reads with you.

{utility_name}""",
        ),
        "es": (
            "Hemos corregido tu factura {bill_no} de {utility_name}",
            """Hola, {first_name}:

Hemos corregido la factura {bill_no} de {service_address}. La factura corregida sustituye a la que te enviamos.

Consulta o descarga la factura corregida: {bill_link}
Este enlace funciona hasta el {link_expires_on}.

Qué ha cambiado: {correction_reason}
Total original: {original_total}
Total corregido: {total_due}

Tu fecha de vencimiento sigue siendo el {due_date}. Si pagas por domiciliación, cobraremos el importe corregido.

Perdona la confusión. Si el nuevo importe sigue sin cuadrarte, llámanos al {support_phone} y revisamos las lecturas contigo.

{utility_name}""",
        ),
        "es-MX": (
            "Corregimos tu recibo {bill_no} de {utility_name}",
            """Hola, {first_name}:

Corregimos el recibo {bill_no} de {service_address}. El recibo corregido reemplaza al que te mandamos.

Ve o descarga el recibo corregido: {bill_link}
Este enlace funciona hasta el {link_expires_on}.

Qué cambió: {correction_reason}
Total original: {original_total}
Total corregido: {total_due}

Tu fecha límite de pago sigue siendo el {due_date}. Si tienes cargo automático, cobraremos el monto corregido.

Disculpa la confusión. Si el nuevo monto todavía no te cuadra, llámanos al {support_phone} y revisamos las lecturas contigo.

{utility_name}""",
        ),
        "de": (
            "Wir haben Ihre Rechnung {bill_no} von {utility_name} korrigiert",
            """Guten Tag {customer_name},

wir haben die Rechnung {bill_no} für {service_address} korrigiert. Die korrigierte Rechnung ersetzt die Rechnung, die wir Ihnen geschickt haben.

Korrigierte Rechnung ansehen oder herunterladen: {bill_link}
Der Link ist bis zum {link_expires_on} gültig.

Was sich geändert hat: {correction_reason}
Ursprünglicher Betrag: {original_total}
Korrigierter Betrag: {total_due}

Ihr Fälligkeitsdatum bleibt der {due_date}. Wenn Sie per Lastschrift zahlen, buchen wir den korrigierten Betrag ab.

Bitte entschuldigen Sie die Unannehmlichkeiten. Wenn Ihnen auch der neue Betrag nicht stimmig erscheint, rufen Sie uns an unter {support_phone} – wir gehen die Zählerstände gern mit Ihnen durch.

{utility_name}""",
        ),
        "hi": (
            "हमने {utility_name} का आपका बिल {bill_no} ठीक कर दिया है",
            """नमस्ते {first_name},

हमने {service_address} का बिल {bill_no} ठीक कर दिया है। सुधारा गया बिल पहले भेजे गए बिल की जगह लेता है।

सुधारा गया बिल देखें या डाउनलोड करें: {bill_link}
यह लिंक {link_expires_on} तक काम करेगा।

क्या बदला: {correction_reason}
पहले की कुल राशि: {original_total}
सुधारी गई कुल राशि: {total_due}

आपकी देय तिथि अब भी {due_date} ही है। अगर आप ऑटोपे से भुगतान करते हैं, तो हम सुधारी गई राशि ही लेंगे।

असुविधा के लिए खेद है। अगर नई राशि भी सही न लगे, तो {support_phone} पर कॉल करें — हम आपके साथ रीडिंग देख लेंगे।

{utility_name}""",
        ),
        "fr-FR": (
            "Nous avons corrigé votre facture {utility_name} {bill_no}",
            """Bonjour {first_name},

Nous avons corrigé la facture {bill_no} pour {service_address}. La facture corrigée remplace celle que nous vous avions envoyée.

Consultez ou téléchargez la facture corrigée : {bill_link}
Ce lien est valable jusqu'au {link_expires_on}.

Ce qui a changé : {correction_reason}
Montant initial : {original_total}
Montant corrigé : {total_due}

Votre date d'échéance reste le {due_date}. Si vous payez par prélèvement automatique, nous prélèverons le montant corrigé.

Veuillez nous excuser pour ce désagrément. Si le nouveau montant ne vous semble toujours pas juste, appelez-nous au {support_phone} et nous reverrons les relevés avec vous.

{utility_name}""",
        ),
        "id-ID": (
            "Kami telah memperbaiki tagihan {utility_name} Anda {bill_no}",
            """Halo {first_name},

Kami telah memperbaiki tagihan {bill_no} untuk {service_address}. Tagihan yang sudah diperbaiki ini menggantikan tagihan yang kami kirim sebelumnya.

Lihat atau unduh tagihan yang sudah diperbaiki: {bill_link}
Tautan ini berlaku sampai {link_expires_on}.

Yang berubah: {correction_reason}
Total semula: {original_total}
Total setelah diperbaiki: {total_due}

Tanggal jatuh tempo Anda tetap {due_date}. Kalau Anda membayar dengan pendebetan otomatis, kami akan menagih jumlah yang sudah diperbaiki.

Mohon maaf atas kebingungannya. Kalau angka barunya masih terasa keliru, hubungi kami di {support_phone} dan kami akan memeriksa angka meternya bersama Anda.

{utility_name}""",
        ),
        "it-IT": (
            "Abbiamo corretto la sua bolletta {utility_name} {bill_no}",
            """Gentile {customer_name},

abbiamo corretto la bolletta {bill_no} per {service_address}. La bolletta corretta sostituisce quella che le avevamo inviato.

Visualizzi o scarichi la bolletta corretta: {bill_link}
Il link è valido fino al {link_expires_on}.

Che cosa è cambiato: {correction_reason}
Totale originario: {original_total}
Totale corretto: {total_due}

La scadenza resta il {due_date}. Se paga con addebito automatico, addebiteremo l'importo corretto.

Ci scusi per il disguido. Se anche il nuovo importo non le torna, ci chiami al {support_phone} e rivedremo insieme le letture.

{utility_name}""",
        ),
        "ja-JP": (
            "{utility_name}のご請求書 {bill_no} を訂正いたしました",
            """{customer_name} 様

{service_address}のご請求書 {bill_no} を訂正いたしました。訂正後の請求書は、先にお送りした請求書に代わるものです。

訂正後の請求書の表示・ダウンロード: {bill_link}
このリンクは{link_expires_on}までご利用いただけます。

変更内容: {correction_reason}
訂正前の金額: {original_total}
訂正後の金額: {total_due}

お支払期限は引き続き{due_date}です。口座振替でお支払いの場合は、訂正後の金額を引き落とします。

ご迷惑をおかけし申し訳ございません。訂正後の金額にもご不明な点がございましたら、{support_phone} までお電話ください。検針値を一緒に確認いたします。

{utility_name}""",
        ),
        "ko-KR": (
            "{utility_name} 청구서 {bill_no}을(를) 정정했습니다",
            """{customer_name} 님, 안녕하세요.

{service_address}의 청구서 {bill_no}을(를) 정정했습니다. 정정된 청구서가 앞서 보내 드린 청구서를 대신합니다.

정정된 청구서 보기 및 내려받기: {bill_link}
이 링크는 {link_expires_on}까지 사용하실 수 있습니다.

변경 내용: {correction_reason}
원래 금액: {original_total}
정정된 금액: {total_due}

납부 기한은 그대로 {due_date}입니다. 자동이체로 납부하시는 경우 정정된 금액이 출금됩니다.

혼란을 드려 죄송합니다. 정정된 금액도 맞지 않는 것 같으면 {support_phone}(으)로 전화해 주세요. 검침값을 함께 확인해 드리겠습니다.

{utility_name}""",
        ),
        "pt-BR": (
            "Corrigimos sua conta {bill_no} da {utility_name}",
            """Olá, {first_name},

Corrigimos a conta {bill_no} de {service_address}. A conta corrigida substitui a que enviamos antes.

Veja ou baixe a conta corrigida: {bill_link}
Este link funciona até {link_expires_on}.

O que mudou: {correction_reason}
Total original: {original_total}
Total corrigido: {total_due}

Seu vencimento continua sendo {due_date}. Se você paga por débito automático, vamos cobrar o valor corrigido.

Desculpe a confusão. Se o novo valor ainda não parecer certo, ligue para {support_phone} e revisamos as leituras com você.

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


__all__ = ["BILL_READY", "CORRECTED_BILL", "DEFAULT_WORDING_LANGUAGE", "WORDING", "wording_for"]
