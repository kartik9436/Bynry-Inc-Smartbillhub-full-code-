# ── Trace ──────────────────────────────────────────────
# Defect:   DEF-PAY-10744 — the returned-payment (NSF) email said "Nothing has
#           changed on your account" after a bounce, and the printed letter was
#           blank (audit L2-04, PO 2026-10-30 "Rest we will fix")
# Rules:    BR-PAY-013 (the returned-payment letter) · BR-NOT-015 (a seeded
#           default the utility edits — OQ-244's precedent, *"provide default and
#           allow user to change"*) · B14 rule 35 (each language written as a
#           local person would say it)
# Tests:    tests/test_def_pay_10744_returned_payment_letter.py
# ───────────────────────────────────────────────────────
"""The SEEDED wording of the returned-payment email and letter, one variant per language.

HUMAN-OWNED · HUMAN-REVIEW-PENDING — this file decides **words a person
reads**, the authority `seed_templates.py` is guarded for. AI-authored
2026-10-30 (lane PAY-G) under the PO ruling of 2026-08-09; row in
12-governance/09-human-review-ledger.md. **LANE-AUTHORED WORDING**: no signed
document writes these bodies. They are seeded DEFAULTS a utility edits on
Settings → Templates (the posture the PO ruled for contracts on 2026-08-18,
*"provide default and allow user to change"*), and a later release only ADDS a
missing variant — it never overwrites one a utility has published.

WHY THE OLD EMAIL WENT
────────────────────────────────────────────────────────────────────────────
`email_payment_failed` read *"Nothing has changed on your account. Your balance
is {balance} and your due date is still {due_date}."* That is true of a card
DECLINED at the till and FALSE of the only thing that sends it: a payment
returned by the bank (`receipts.queue_failed_payment_notice`, called on an
`nsf` reversal alone). After a bounce the money is taken back off the account,
the bills it paid are owed again and — since 2026-10-30 — an NSF fee may be
charged. Saying nothing changed tells a customer not to pay.

WHAT EACH BODY SAYS, AND THE FOUR OPTIONAL PARAGRAPHS
────────────────────────────────────────────────────────────────────────────
The amount and the date it was paid; that the bank returned it; the cheque or
reference number; the Bank memo (the bank's own words, PO 2026-10-30 LBX-04);
the NSF fee; the new balance; the date it is due; how to pay. **No figure is
written in prose** — every amount is a token filled from the reversal's own
record, and the fee is the plan's NSF charge code, never a constant.

`{confirmation}`, `{bank_memo}`, `{nsf_fee}` and `{due_date}` are OPTIONAL in
`catalogs` and each sits in a paragraph of its own: the renderer leaves out a
blank-line paragraph whose optional token has no value. So a bounce with no
Bank memo prints no memo line, and **a bounce with no NSF fee (none set on the
plan, or the clerk unticked it) prints no fee line** — never `$0.00` and never
a guessed figure. A translation that merged one of those paragraphs into a
neighbour would drop the neighbour too; keep them apart.

THE GREETING follows `past_due_letter_wording`: the informal languages greet
`{first_name}`; de, it-IT, ja-JP and ko-KR address the whole `{customer_name}`
in the formal register. A printed letter has no subject line (`None`).
"""

from __future__ import annotations

DEFAULT_WORDING_LANGUAGE = "en"

RETURNED_EMAIL = "email_payment_failed"
RETURNED_LETTER = "payment_failed_letter"

WORDING: dict[str, dict[str, tuple[str | None, str]]] = {
    RETURNED_EMAIL: {
        "en": (
            "Your {utility_name} payment of {amount} was returned by your bank",
            "Hi {first_name},\n\n"
            "Your payment of {amount} on {date} was returned by your bank, so it has been "
            "taken off your account.\n\n"
            "Check or reference {confirmation}\n\n"
            "Bank memo {bank_memo}\n\n"
            "Returned payment fee {nsf_fee}\n\n"
            "Your balance is now {balance}.\n\n"
            "Please pay by {due_date}.\n\n"
            "You can pay at {utility_website}, or call {support_phone} to pay another way.\n\n"
            "{utility_name}",
        ),
        "es": (
            "Tu banco devolvió tu pago de {amount} a {utility_name}",
            "Hola, {first_name}:\n\n"
            "Tu banco devolvió el pago de {amount} que hiciste el {date}, así que lo hemos "
            "retirado de tu cuenta.\n\n"
            "Cheque o referencia {confirmation}\n\n"
            "Nota del banco {bank_memo}\n\n"
            "Cargo por pago devuelto {nsf_fee}\n\n"
            "Tu saldo actual es de {balance}.\n\n"
            "Por favor, págalo antes del {due_date}.\n\n"
            "Puedes pagar en {utility_website} o llamarnos al {support_phone} para pagar de "
            "otra forma.\n\n"
            "{utility_name}",
        ),
        "es-MX": (
            "Tu banco rechazó tu pago de {amount} a {utility_name}",
            "Hola, {first_name}:\n\n"
            "Tu banco nos regresó el pago de {amount} que hiciste el {date}, por lo que ya no "
            "aparece aplicado en tu cuenta.\n\n"
            "Cheque o referencia {confirmation}\n\n"
            "Nota del banco {bank_memo}\n\n"
            "Comisión por pago rechazado {nsf_fee}\n\n"
            "Tu saldo ahora es de {balance}.\n\n"
            "Te pedimos pagarlo a más tardar el {due_date}.\n\n"
            "Puedes pagar en {utility_website} o llamarnos al {support_phone} si prefieres "
            "pagar de otra manera.\n\n"
            "{utility_name}",
        ),
        "de": (
            "Ihre Zahlung über {amount} an {utility_name} wurde zurückgegeben",
            "Guten Tag {customer_name},\n\n"
            "Ihre Bank hat Ihre Zahlung über {amount} vom {date} zurückgegeben. Der Betrag "
            "wurde deshalb wieder von Ihrem Kundenkonto ausgebucht.\n\n"
            "Scheck- oder Referenznummer {confirmation}\n\n"
            "Vermerk der Bank {bank_memo}\n\n"
            "Rücklastschriftgebühr {nsf_fee}\n\n"
            "Ihr offener Betrag beträgt jetzt {balance}.\n\n"
            "Bitte begleichen Sie ihn bis zum {due_date}.\n\n"
            "Sie können unter {utility_website} bezahlen oder uns unter {support_phone} "
            "anrufen, wenn Sie anders bezahlen möchten.\n\n"
            "Mit freundlichen Grüßen\n{utility_name}",
        ),
        "hi": (
            "{utility_name} को किया गया आपका {amount} का भुगतान बैंक ने लौटा दिया है",
            "नमस्ते {first_name},\n\n"
            "{date} को किया गया आपका {amount} का भुगतान आपके बैंक ने लौटा दिया है, इसलिए "
            "इसे आपके खाते से हटा दिया गया है।\n\n"
            "चेक या संदर्भ संख्या {confirmation}\n\n"
            "बैंक की टिप्पणी {bank_memo}\n\n"
            "लौटे भुगतान का शुल्क {nsf_fee}\n\n"
            "अब आपकी बकाया राशि {balance} है।\n\n"
            "कृपया {due_date} तक भुगतान करें।\n\n"
            "आप {utility_website} पर भुगतान कर सकते हैं, या किसी और तरीके से भुगतान करने के "
            "लिए {support_phone} पर कॉल करें।\n\n"
            "{utility_name}",
        ),
        "fr-FR": (
            "Votre paiement de {amount} à {utility_name} a été rejeté par votre banque",
            "Bonjour {first_name},\n\n"
            "Votre banque a rejeté votre paiement de {amount} du {date}. Il a donc été "
            "retiré de votre compte.\n\n"
            "Chèque ou référence {confirmation}\n\n"
            "Motif indiqué par la banque {bank_memo}\n\n"
            "Frais de paiement rejeté {nsf_fee}\n\n"
            "Votre solde est maintenant de {balance}.\n\n"
            "Merci de le régler avant le {due_date}.\n\n"
            "Vous pouvez payer sur {utility_website} ou nous appeler au {support_phone} pour "
            "payer autrement.\n\n"
            "{utility_name}",
        ),
        "id-ID": (
            "Pembayaran Anda sebesar {amount} ke {utility_name} dikembalikan oleh bank",
            "Halo {first_name},\n\n"
            "Pembayaran Anda sebesar {amount} pada {date} dikembalikan oleh bank Anda, jadi "
            "pembayaran itu sudah dibatalkan dari akun Anda.\n\n"
            "Nomor cek atau referensi {confirmation}\n\n"
            "Catatan bank {bank_memo}\n\n"
            "Biaya pembayaran yang dikembalikan {nsf_fee}\n\n"
            "Saldo Anda sekarang {balance}.\n\n"
            "Mohon dibayar paling lambat {due_date}.\n\n"
            "Anda dapat membayar di {utility_website}, atau hubungi {support_phone} untuk "
            "membayar dengan cara lain.\n\n"
            "{utility_name}",
        ),
        "it-IT": (
            "Il suo pagamento di {amount} a {utility_name} è stato respinto dalla banca",
            "Gentile {customer_name},\n\n"
            "la sua banca ha respinto il pagamento di {amount} del {date}, che è stato quindi "
            "stornato dal suo conto.\n\n"
            "Assegno o riferimento {confirmation}\n\n"
            "Nota della banca {bank_memo}\n\n"
            "Commissione per pagamento respinto {nsf_fee}\n\n"
            "Il suo saldo ora è di {balance}.\n\n"
            "La preghiamo di saldarlo entro il {due_date}.\n\n"
            "Può pagare su {utility_website} oppure chiamarci al {support_phone} per pagare "
            "in un altro modo.\n\n"
            "Cordiali saluti\n{utility_name}",
        ),
        "ja-JP": (
            "{utility_name}へのお支払い（{amount}）が銀行から返却されました",
            "{customer_name} 様\n\n"
            "{date}にお支払いいただいた{amount}が、お客様の銀行から返却されました。"
            "そのため、このお支払いはお客様のアカウントから取り消されています。\n\n"
            "小切手番号・参照番号 {confirmation}\n\n"
            "銀行からのメモ {bank_memo}\n\n"
            "返却手数料 {nsf_fee}\n\n"
            "現在のご請求残高は{balance}です。\n\n"
            "{due_date}までにお支払いください。\n\n"
            "{utility_website}からお支払いいただけます。別の方法をご希望の場合は"
            "{support_phone}までお電話ください。\n\n"
            "{utility_name}",
        ),
        "ko-KR": (
            "{utility_name}에 납부하신 {amount}이(가) 은행에서 반환되었습니다",
            "{customer_name} 고객님,\n\n"
            "{date}에 납부하신 {amount}이(가) 고객님의 은행에서 반환되어, 해당 납부가 "
            "계정에서 취소되었습니다.\n\n"
            "수표 또는 참조 번호 {confirmation}\n\n"
            "은행 메모 {bank_memo}\n\n"
            "반환 수수료 {nsf_fee}\n\n"
            "현재 잔액은 {balance}입니다.\n\n"
            "{due_date}까지 납부해 주시기 바랍니다.\n\n"
            "{utility_website}에서 납부하시거나, 다른 방법으로 납부하시려면 "
            "{support_phone}으로 전화해 주세요.\n\n"
            "{utility_name}",
        ),
        "pt-BR": (
            "Seu pagamento de {amount} para {utility_name} foi devolvido pelo banco",
            "Olá, {first_name}!\n\n"
            "Seu banco devolveu o pagamento de {amount} feito em {date}, por isso ele foi "
            "retirado da sua conta.\n\n"
            "Cheque ou referência {confirmation}\n\n"
            "Observação do banco {bank_memo}\n\n"
            "Tarifa de pagamento devolvido {nsf_fee}\n\n"
            "Seu saldo agora é de {balance}.\n\n"
            "Por favor, pague até {due_date}.\n\n"
            "Você pode pagar em {utility_website} ou ligar para {support_phone} para pagar "
            "de outra forma.\n\n"
            "{utility_name}",
        ),
    },
    RETURNED_LETTER: {
        "en": (
            None,
            "Dear {customer_name},\n\n"
            "Account {account_no}\n\n"
            "Your payment of {amount} on {date} was returned by your bank, so it has been "
            "taken off your account.\n\n"
            "Check or reference {confirmation}\n\n"
            "Bank memo {bank_memo}\n\n"
            "Returned payment fee {nsf_fee}\n\n"
            "Your balance is now {balance}.\n\n"
            "Please pay by {due_date}.\n\n"
            "You can pay at {utility_website}, or call {support_phone} to pay another way.\n\n"
            "{utility_name}",
        ),
        "es": (
            None,
            "Estimado/a {customer_name}:\n\n"
            "Cuenta {account_no}\n\n"
            "Tu banco devolvió el pago de {amount} que hiciste el {date}, así que lo hemos "
            "retirado de tu cuenta.\n\n"
            "Cheque o referencia {confirmation}\n\n"
            "Nota del banco {bank_memo}\n\n"
            "Cargo por pago devuelto {nsf_fee}\n\n"
            "Tu saldo actual es de {balance}.\n\n"
            "Por favor, págalo antes del {due_date}.\n\n"
            "Puedes pagar en {utility_website} o llamarnos al {support_phone} para pagar de "
            "otra forma.\n\n"
            "{utility_name}",
        ),
        "es-MX": (
            None,
            "Estimado/a {customer_name}:\n\n"
            "Cuenta {account_no}\n\n"
            "Tu banco nos regresó el pago de {amount} que hiciste el {date}, por lo que ya no "
            "aparece aplicado en tu cuenta.\n\n"
            "Cheque o referencia {confirmation}\n\n"
            "Nota del banco {bank_memo}\n\n"
            "Comisión por pago rechazado {nsf_fee}\n\n"
            "Tu saldo ahora es de {balance}.\n\n"
            "Te pedimos pagarlo a más tardar el {due_date}.\n\n"
            "Puedes pagar en {utility_website} o llamarnos al {support_phone} si prefieres "
            "pagar de otra manera.\n\n"
            "{utility_name}",
        ),
        "de": (
            None,
            "Guten Tag {customer_name},\n\n"
            "Kundenkonto {account_no}\n\n"
            "Ihre Bank hat Ihre Zahlung über {amount} vom {date} zurückgegeben. Der Betrag "
            "wurde deshalb wieder von Ihrem Kundenkonto ausgebucht.\n\n"
            "Scheck- oder Referenznummer {confirmation}\n\n"
            "Vermerk der Bank {bank_memo}\n\n"
            "Rücklastschriftgebühr {nsf_fee}\n\n"
            "Ihr offener Betrag beträgt jetzt {balance}.\n\n"
            "Bitte begleichen Sie ihn bis zum {due_date}.\n\n"
            "Sie können unter {utility_website} bezahlen oder uns unter {support_phone} "
            "anrufen, wenn Sie anders bezahlen möchten.\n\n"
            "Mit freundlichen Grüßen\n{utility_name}",
        ),
        "hi": (
            None,
            "प्रिय {customer_name},\n\n"
            "खाता संख्या {account_no}\n\n"
            "{date} को किया गया आपका {amount} का भुगतान आपके बैंक ने लौटा दिया है, इसलिए "
            "इसे आपके खाते से हटा दिया गया है।\n\n"
            "चेक या संदर्भ संख्या {confirmation}\n\n"
            "बैंक की टिप्पणी {bank_memo}\n\n"
            "लौटे भुगतान का शुल्क {nsf_fee}\n\n"
            "अब आपकी बकाया राशि {balance} है।\n\n"
            "कृपया {due_date} तक भुगतान करें।\n\n"
            "आप {utility_website} पर भुगतान कर सकते हैं, या किसी और तरीके से भुगतान करने के "
            "लिए {support_phone} पर कॉल करें।\n\n"
            "{utility_name}",
        ),
        "fr-FR": (
            None,
            "Bonjour {customer_name},\n\n"
            "Compte {account_no}\n\n"
            "Votre banque a rejeté votre paiement de {amount} du {date}. Il a donc été "
            "retiré de votre compte.\n\n"
            "Chèque ou référence {confirmation}\n\n"
            "Motif indiqué par la banque {bank_memo}\n\n"
            "Frais de paiement rejeté {nsf_fee}\n\n"
            "Votre solde est maintenant de {balance}.\n\n"
            "Merci de le régler avant le {due_date}.\n\n"
            "Vous pouvez payer sur {utility_website} ou nous appeler au {support_phone} pour "
            "payer autrement.\n\n"
            "{utility_name}",
        ),
        "id-ID": (
            None,
            "Yth. {customer_name},\n\n"
            "Nomor akun {account_no}\n\n"
            "Pembayaran Anda sebesar {amount} pada {date} dikembalikan oleh bank Anda, jadi "
            "pembayaran itu sudah dibatalkan dari akun Anda.\n\n"
            "Nomor cek atau referensi {confirmation}\n\n"
            "Catatan bank {bank_memo}\n\n"
            "Biaya pembayaran yang dikembalikan {nsf_fee}\n\n"
            "Saldo Anda sekarang {balance}.\n\n"
            "Mohon dibayar paling lambat {due_date}.\n\n"
            "Anda dapat membayar di {utility_website}, atau hubungi {support_phone} untuk "
            "membayar dengan cara lain.\n\n"
            "{utility_name}",
        ),
        "it-IT": (
            None,
            "Gentile {customer_name},\n\n"
            "Conto {account_no}\n\n"
            "La sua banca ha respinto il pagamento di {amount} del {date}, che è stato quindi "
            "stornato dal suo conto.\n\n"
            "Assegno o riferimento {confirmation}\n\n"
            "Nota della banca {bank_memo}\n\n"
            "Commissione per pagamento respinto {nsf_fee}\n\n"
            "Il suo saldo ora è di {balance}.\n\n"
            "La preghiamo di saldarlo entro il {due_date}.\n\n"
            "Può pagare su {utility_website} oppure chiamarci al {support_phone} per pagare "
            "in un altro modo.\n\n"
            "Cordiali saluti\n{utility_name}",
        ),
        "ja-JP": (
            None,
            "{customer_name} 様\n\n"
            "お客様番号 {account_no}\n\n"
            "{date}にお支払いいただいた{amount}が、お客様の銀行から返却されました。"
            "そのため、このお支払いはお客様のアカウントから取り消されています。\n\n"
            "小切手番号・参照番号 {confirmation}\n\n"
            "銀行からのメモ {bank_memo}\n\n"
            "返却手数料 {nsf_fee}\n\n"
            "現在のご請求残高は{balance}です。\n\n"
            "{due_date}までにお支払いください。\n\n"
            "{utility_website}からお支払いいただけます。別の方法をご希望の場合は"
            "{support_phone}までお電話ください。\n\n"
            "{utility_name}",
        ),
        "ko-KR": (
            None,
            "{customer_name} 고객님께\n\n"
            "고객 번호 {account_no}\n\n"
            "{date}에 납부하신 {amount}이(가) 고객님의 은행에서 반환되어, 해당 납부가 "
            "계정에서 취소되었습니다.\n\n"
            "수표 또는 참조 번호 {confirmation}\n\n"
            "은행 메모 {bank_memo}\n\n"
            "반환 수수료 {nsf_fee}\n\n"
            "현재 잔액은 {balance}입니다.\n\n"
            "{due_date}까지 납부해 주시기 바랍니다.\n\n"
            "{utility_website}에서 납부하시거나, 다른 방법으로 납부하시려면 "
            "{support_phone}으로 전화해 주세요.\n\n"
            "{utility_name}",
        ),
        "pt-BR": (
            None,
            "Prezado(a) {customer_name},\n\n"
            "Conta {account_no}\n\n"
            "Seu banco devolveu o pagamento de {amount} feito em {date}, por isso ele foi "
            "retirado da sua conta.\n\n"
            "Cheque ou referência {confirmation}\n\n"
            "Observação do banco {bank_memo}\n\n"
            "Tarifa de pagamento devolvido {nsf_fee}\n\n"
            "Seu saldo agora é de {balance}.\n\n"
            "Por favor, pague até {due_date}.\n\n"
            "Você pode pagar em {utility_website} ou ligar para {support_phone} para pagar "
            "de outra forma.\n\n"
            "{utility_name}",
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
    "RETURNED_EMAIL",
    "RETURNED_LETTER",
    "WORDING",
    "wording_for",
]
