# ── Trace ──────────────────────────────────────────────
# Change:   CR-188-BRC10 — PO 2026-10-22, decision logs *"Staff invitation
#           email: a one-time sign-in link, not a password; six answers"* and
#           *"Account-access emails: languages via template variants, and
#           'don't do any hardcoding'"*
# Rules:    BR-NOT-006 (type × category × language variants) · BR-NOT-001
#           (the `default` variant is mandatory) · B14 rule 35 (a language is
#           written natively, not translated word for word from English)
# Tests:    06-backend/tests/test_cr188_staff_invite_email.py ·
#           06-backend/tests/test_def_cwp_10381_portal_reset_email.py ·
#           06-backend/tests/test_cr189_portal_update_email.py
# Impacts:  seed_templates.py (plants these as published variants) ·
#           catalogs.py (`account_access` category, the two classes' palettes)
# ───────────────────────────────────────────────────────
"""The SEEDED wording of the Account access emails, one variant per language.

HUMAN-OWNED · HUMAN-REVIEW-PENDING — this file decides **words a person
reads**, the authority `seed_templates.py` is guarded for. AI-authored
2026-10-22 under the PO ruling of 2026-08-09; row in
12-governance/09-human-review-ledger.md. **LANE-AUTHORED WORDING**: no signed
document writes these bodies. They are seeded DEFAULTS each utility edits on
Settings → Templates, and a later release only ADDS a missing variant — it
never overwrites one a utility has published (`seed_templates._seed_one` is
insert-missing).

────────────────────────────────────────────────────────────────────────────
WHAT IS DATA HERE, AND WHAT IS NOT (*"don't do any hardcoding"*)
────────────────────────────────────────────────────────────────────────────
* **The set of languages is NOT typed here.** `seed_templates` iterates the
  product's registry (`tenancy_seam.platform_languages`) and asks this table
  for each code by `wording_for`: exact tag first, then its primary language
  (`en-US` → `en`). A registry language with no wording here is SKIPPED AND
  REPORTED, and the utility's `default` variant serves it until one is written.
* **The `default` variant is the `en` wording** — what a utility with no
  language set, or with a language nobody has written yet, receives.
* **No password token anywhere.** Every body carries `{sign_in_link}`, which the
  catalogue makes mandatory; `rendering.validate_body` checks each variant.

Six classes live here: `staff_user_invite` and `staff_password_reset_link`
(CR-188-BRC10, link token `{sign_in_link}`); `portal_password_reset`
(DEF-CWP-10381, link token `{reset_link}`); and `portal_enrolment_code`,
`portal_email_change_code` (one-time `{code}`) and `portal_email_changed_notice`
(no credential) from CR-189-BRC10 / DEF-CWP-10402. Each class's credential
tokens are its catalogue's (`catalogs.TemplateClass.credential_tokens`), not
this file's.
"""

from __future__ import annotations

#: template code → language tag → (subject, body). The KEYS of the inner dict
#: are the languages that have been WRITTEN, not the languages that exist.
WORDING: dict[str, dict[str, tuple[str, str]]] = {
    "staff_user_invite": {
        "en": (
            "Your {utility_name} account is ready",
            """Hi {staff_name},

{utility_name} has created an account for you.

Your username is {username}.

Set your password here: {sign_in_link}

This link works once and expires on {link_expires_on}. If it has expired, ask your System Admin to send a new one.""",
        ),
        "es": (
            "Tu cuenta de {utility_name} ya está lista",
            """Hola, {staff_name}:

{utility_name} te ha creado una cuenta.

Tu nombre de usuario es {username}.

Crea tu contraseña aquí: {sign_in_link}

El enlace solo se puede usar una vez y caduca el {link_expires_on}. Si ha caducado, pide a tu administrador del sistema que te envíe otro.""",
        ),
        "es-MX": (
            "Tu cuenta de {utility_name} ya está lista",
            """Hola, {staff_name}:

{utility_name} creó una cuenta para ti.

Tu nombre de usuario es {username}.

Crea tu contraseña aquí: {sign_in_link}

El enlace solo funciona una vez y vence el {link_expires_on}. Si ya venció, pídele a tu administrador del sistema que te mande uno nuevo.""",
        ),
        "de": (
            "Ihr Konto bei {utility_name} ist eingerichtet",
            """Hallo {staff_name},

{utility_name} hat ein Konto für Sie angelegt.

Ihr Benutzername lautet {username}.

Legen Sie hier Ihr Passwort fest: {sign_in_link}

Der Link ist nur einmal gültig und läuft am {link_expires_on} ab. Ist er abgelaufen, bitten Sie Ihre Systemverwaltung um einen neuen.""",
        ),
        "hi": (
            "{utility_name} पर आपका खाता तैयार है",
            """नमस्ते {staff_name},

{utility_name} ने आपके लिए एक खाता बनाया है।

आपका यूज़रनेम {username} है।

अपना पासवर्ड यहाँ सेट करें: {sign_in_link}

यह लिंक केवल एक बार काम करता है और {link_expires_on} को समाप्त हो जाएगा। अगर इसकी अवधि खत्म हो गई है, तो अपने सिस्टम एडमिन से नया लिंक भेजने को कहें।""",
        ),
        "fr-FR": (
            "Votre compte {utility_name} est prêt",
            """Bonjour {staff_name},

{utility_name} vous a créé un compte.

Votre identifiant est {username}.

Choisissez votre mot de passe ici : {sign_in_link}

Ce lien ne fonctionne qu'une fois et expire le {link_expires_on}. S'il a expiré, demandez-en un nouveau à votre administrateur système.""",
        ),
        "id-ID": (
            "Akun {utility_name} Anda sudah siap",
            """Halo {staff_name},

{utility_name} telah membuatkan akun untuk Anda.

Nama pengguna Anda adalah {username}.

Buat kata sandi Anda di sini: {sign_in_link}

Tautan ini hanya bisa dipakai sekali dan berlaku hingga {link_expires_on}. Jika sudah kedaluwarsa, minta Admin Sistem Anda untuk mengirim tautan baru.""",
        ),
        "it-IT": (
            "Il tuo account {utility_name} è pronto",
            """Ciao {staff_name},

{utility_name} ha creato un account per te.

Il tuo nome utente è {username}.

Imposta la tua password qui: {sign_in_link}

Il link si può usare una sola volta e scade il {link_expires_on}. Se è scaduto, chiedi al tuo amministratore di sistema di inviartene uno nuovo.""",
        ),
        "ja-JP": (
            "{utility_name} のアカウントをご用意しました",
            """{staff_name} 様

{utility_name} であなたのアカウントを作成しました。

ユーザー名は {username} です。

こちらからパスワードを設定してください: {sign_in_link}

このリンクは一度だけ使用でき、{link_expires_on} に有効期限が切れます。期限が切れている場合は、システム管理者に新しいリンクの送付を依頼してください。""",
        ),
        "ko-KR": (
            "{utility_name} 계정이 준비되었습니다",
            """{staff_name}님, 안녕하세요.

{utility_name}에서 회원님의 계정을 만들었습니다.

사용자 이름은 {username}입니다.

여기에서 비밀번호를 설정하세요: {sign_in_link}

이 링크는 한 번만 사용할 수 있으며 {link_expires_on}에 만료됩니다. 만료되었다면 시스템 관리자에게 새 링크를 요청하세요.""",
        ),
        "pt-BR": (
            "Sua conta na {utility_name} está pronta",
            """Olá, {staff_name}!

A {utility_name} criou uma conta para você.

Seu nome de usuário é {username}.

Crie sua senha aqui: {sign_in_link}

O link só pode ser usado uma vez e expira em {link_expires_on}. Se ele já expirou, peça ao administrador do sistema para enviar um novo.""",
        ),
    },
    "staff_password_reset_link": {
        "en": (
            "Set a new password for {utility_name}",
            """Hi {staff_name},

A System Admin at {utility_name} has reset your password.

Your username is {username}.

Set a new password here: {sign_in_link}

This link works once and expires on {link_expires_on}. If you did not expect this email, tell your System Admin.""",
        ),
        "es": (
            "Crea una nueva contraseña para {utility_name}",
            """Hola, {staff_name}:

Un administrador del sistema de {utility_name} ha restablecido tu contraseña.

Tu nombre de usuario es {username}.

Crea una contraseña nueva aquí: {sign_in_link}

El enlace solo se puede usar una vez y caduca el {link_expires_on}. Si no esperabas este correo, avisa a tu administrador del sistema.""",
        ),
        "es-MX": (
            "Crea una nueva contraseña para {utility_name}",
            """Hola, {staff_name}:

Un administrador del sistema de {utility_name} restableció tu contraseña.

Tu nombre de usuario es {username}.

Crea una contraseña nueva aquí: {sign_in_link}

El enlace solo funciona una vez y vence el {link_expires_on}. Si no esperabas este correo, avísale a tu administrador del sistema.""",
        ),
        "de": (
            "Neues Passwort für {utility_name} festlegen",
            """Hallo {staff_name},

Die Systemverwaltung von {utility_name} hat Ihr Passwort zurückgesetzt.

Ihr Benutzername lautet {username}.

Legen Sie hier ein neues Passwort fest: {sign_in_link}

Der Link ist nur einmal gültig und läuft am {link_expires_on} ab. Wenn Sie diese E-Mail nicht erwartet haben, wenden Sie sich an Ihre Systemverwaltung.""",
        ),
        "hi": (
            "{utility_name} के लिए नया पासवर्ड सेट करें",
            """नमस्ते {staff_name},

{utility_name} के एक सिस्टम एडमिन ने आपका पासवर्ड रीसेट किया है।

आपका यूज़रनेम {username} है।

नया पासवर्ड यहाँ सेट करें: {sign_in_link}

यह लिंक केवल एक बार काम करता है और {link_expires_on} को समाप्त हो जाएगा। अगर आपको इस ईमेल की उम्मीद नहीं थी, तो अपने सिस्टम एडमिन को बताएँ।""",
        ),
        "fr-FR": (
            "Choisissez un nouveau mot de passe pour {utility_name}",
            """Bonjour {staff_name},

Un administrateur système de {utility_name} a réinitialisé votre mot de passe.

Votre identifiant est {username}.

Choisissez un nouveau mot de passe ici : {sign_in_link}

Ce lien ne fonctionne qu'une fois et expire le {link_expires_on}. Si vous n'attendiez pas ce message, prévenez votre administrateur système.""",
        ),
        "id-ID": (
            "Buat kata sandi baru untuk {utility_name}",
            """Halo {staff_name},

Admin Sistem di {utility_name} telah mengatur ulang kata sandi Anda.

Nama pengguna Anda adalah {username}.

Buat kata sandi baru di sini: {sign_in_link}

Tautan ini hanya bisa dipakai sekali dan berlaku hingga {link_expires_on}. Jika Anda tidak merasa meminta email ini, beri tahu Admin Sistem Anda.""",
        ),
        "it-IT": (
            "Imposta una nuova password per {utility_name}",
            """Ciao {staff_name},

Un amministratore di sistema di {utility_name} ha reimpostato la tua password.

Il tuo nome utente è {username}.

Imposta una nuova password qui: {sign_in_link}

Il link si può usare una sola volta e scade il {link_expires_on}. Se non ti aspettavi questa email, avvisa il tuo amministratore di sistema.""",
        ),
        "ja-JP": (
            "{utility_name} の新しいパスワードを設定してください",
            """{staff_name} 様

{utility_name} のシステム管理者があなたのパスワードをリセットしました。

ユーザー名は {username} です。

こちらから新しいパスワードを設定してください: {sign_in_link}

このリンクは一度だけ使用でき、{link_expires_on} に有効期限が切れます。心当たりがない場合は、システム管理者にお知らせください。""",
        ),
        "ko-KR": (
            "{utility_name} 새 비밀번호를 설정하세요",
            """{staff_name}님, 안녕하세요.

{utility_name}의 시스템 관리자가 회원님의 비밀번호를 재설정했습니다.

사용자 이름은 {username}입니다.

여기에서 새 비밀번호를 설정하세요: {sign_in_link}

이 링크는 한 번만 사용할 수 있으며 {link_expires_on}에 만료됩니다. 요청하지 않은 메일이라면 시스템 관리자에게 알려 주세요.""",
        ),
        "pt-BR": (
            "Crie uma nova senha para a {utility_name}",
            """Olá, {staff_name}!

Um administrador do sistema da {utility_name} redefiniu sua senha.

Seu nome de usuário é {username}.

Crie uma nova senha aqui: {sign_in_link}

O link só pode ser usado uma vez e expira em {link_expires_on}. Se você não esperava este e-mail, avise o administrador do sistema.""",
        ),
    },
    # ── DEF-CWP-10381 · the customer portal's reset link (PO 2026-10-22) ──
    # Lane PORTAL-RESET. Its link token is `{reset_link}` (mandatory in its
    # catalogue), not `{sign_in_link}`. No lifetime is printed: it is the
    # utility's `password_link_valid_days` setting, and a figure would drift.
    "portal_password_reset": {
        "en": (
            "Reset your {utility_name} portal password",
            """Hi {customer_name},

We received a request to reset the password for your {utility_name} customer portal login.

Choose a new password here:
{reset_link}

The link works once. If you did not ask for this, ignore this email and your password stays the same.

Questions? Call {support_phone} or email {support_email}.

{utility_name}""",
        ),
        "de": (
            "Passwort für das {utility_name}-Kundenportal zurücksetzen",
            """Hallo {customer_name},

wir haben eine Anfrage erhalten, das Passwort für Ihren Zugang zum Kundenportal von {utility_name} zurückzusetzen.

Hier wählen Sie ein neues Passwort:
{reset_link}

Der Link funktioniert nur einmal. Wenn Sie das nicht angefordert haben, ignorieren Sie diese E-Mail – Ihr Passwort bleibt unverändert.

Fragen? Rufen Sie uns an unter {support_phone} oder schreiben Sie an {support_email}.

{utility_name}""",
        ),
        "es": (
            "Restablezca su contraseña del portal de clientes de {utility_name}",
            """Hola, {customer_name}:

Hemos recibido una solicitud para restablecer la contraseña de su acceso al portal de clientes de {utility_name}.

Elija una nueva contraseña aquí:
{reset_link}

El enlace solo funciona una vez. Si no ha sido usted, ignore este correo; su contraseña no cambiará.

¿Dudas? Llame al {support_phone} o escriba a {support_email}.

{utility_name}""",
        ),
        "es-MX": (
            "Restablece tu contraseña del portal de clientes de {utility_name}",
            """Hola, {customer_name}:

Recibimos una solicitud para restablecer la contraseña de tu cuenta en el portal de clientes de {utility_name}.

Elige una nueva contraseña aquí:
{reset_link}

El enlace funciona una sola vez. Si tú no lo pediste, ignora este correo y tu contraseña seguirá igual.

¿Tienes dudas? Llámanos al {support_phone} o escríbenos a {support_email}.

{utility_name}""",
        ),
        "fr-FR": (
            "Réinitialisez le mot de passe de votre espace client {utility_name}",
            """Bonjour {customer_name},

Nous avons reçu une demande de réinitialisation du mot de passe de votre espace client {utility_name}.

Choisissez un nouveau mot de passe ici :
{reset_link}

Ce lien ne fonctionne qu’une seule fois. Si vous n’êtes pas à l’origine de cette demande, ignorez ce message : votre mot de passe reste inchangé.

Des questions ? Appelez le {support_phone} ou écrivez à {support_email}.

{utility_name}""",
        ),
        "hi": (
            "{utility_name} ग्राहक पोर्टल का पासवर्ड रीसेट करें",
            """नमस्ते {customer_name},

हमें आपके {utility_name} ग्राहक पोर्टल लॉगिन का पासवर्ड रीसेट करने का अनुरोध मिला है।

नया पासवर्ड यहाँ चुनें:
{reset_link}

यह लिंक केवल एक बार काम करता है। अगर आपने यह अनुरोध नहीं किया है, तो इस ईमेल को अनदेखा करें — आपका पासवर्ड नहीं बदलेगा।

कोई सवाल? {support_phone} पर कॉल करें या {support_email} पर लिखें।

{utility_name}""",
        ),
        "id-ID": (
            "Atur ulang kata sandi portal pelanggan {utility_name}",
            """Halo {customer_name},

Kami menerima permintaan untuk mengatur ulang kata sandi akun portal pelanggan {utility_name} Anda.

Pilih kata sandi baru di sini:
{reset_link}

Tautan ini hanya bisa dipakai sekali. Jika Anda tidak memintanya, abaikan email ini; kata sandi Anda tidak berubah.

Ada pertanyaan? Hubungi {support_phone} atau kirim email ke {support_email}.

{utility_name}""",
        ),
        "it-IT": (
            "Reimposta la password dell’area clienti {utility_name}",
            """Gentile {customer_name},

abbiamo ricevuto una richiesta di reimpostazione della password del suo accesso all’area clienti {utility_name}.

Scelga una nuova password qui:
{reset_link}

Il link funziona una sola volta. Se non ha fatto lei la richiesta, ignori questa email: la sua password resta invariata.

Domande? Chiami il {support_phone} o scriva a {support_email}.

{utility_name}""",
        ),
        "ja-JP": (
            "{utility_name} お客さまポータルのパスワード再設定",
            """{customer_name} 様

{utility_name} お客さまポータルのパスワード再設定のご依頼を受け付けました。

以下のリンクから新しいパスワードを設定してください。
{reset_link}

このリンクは一度だけご利用いただけます。お心当たりがない場合は、このメールを破棄してください。パスワードは変更されません。

ご不明な点は {support_phone} までお電話いただくか、{support_email} までご連絡ください。

{utility_name}""",
        ),
        "ko-KR": (
            "{utility_name} 고객 포털 비밀번호 재설정",
            """{customer_name} 님, 안녕하세요.

{utility_name} 고객 포털 계정의 비밀번호 재설정 요청이 접수되었습니다.

아래 링크에서 새 비밀번호를 설정해 주세요.
{reset_link}

이 링크는 한 번만 사용할 수 있습니다. 요청하신 적이 없다면 이 메일을 무시하셔도 되며, 비밀번호는 바뀌지 않습니다.

문의 사항은 {support_phone}로 전화하시거나 {support_email}로 메일을 보내 주세요.

{utility_name}""",
        ),
        "pt-BR": (
            "Redefina sua senha do portal do cliente {utility_name}",
            """Olá, {customer_name},

Recebemos um pedido para redefinir a senha do seu acesso ao portal do cliente {utility_name}.

Escolha uma nova senha aqui:
{reset_link}

O link funciona uma única vez. Se não foi você quem pediu, ignore este e-mail; sua senha continua a mesma.

Dúvidas? Ligue para {support_phone} ou escreva para {support_email}.

{utility_name}""",
        ),
    },
    # ── CR-189-BRC10 · the portal's registered-email change (PO 2026-10-22) ──
    # Lane PORTAL-EMAIL. `{code}` is mandatory in the first class; the second
    # carries no link and no code. No lifetime is printed: the code's ten
    # minutes are the product's figure and wording would be a second copy.
    # The one-time code to a contact ALREADY ON FILE — portal sign-up, adding
    # an account, the step-up before a payment-method change, and step 2 of the
    # email change all queue it (`credentials.queue_code`). It had a queue row
    # since CR-068 wave E and no wording, so on email it never went out
    # (`DEF-CWP-10402`). Its render context carries only `{code}`.
    "portal_enrolment_code": {
        "en": (
            "Your {utility_name} code",
            """Your {utility_name} code is {code}

Type it on the screen to continue. Do not share it with anyone.

If you did not ask for it, ignore this email.

{utility_name}""",
        ),
        "es": (
            "Su código de {utility_name}",
            """Su código de {utility_name} es {code}

Escríbalo en la pantalla para continuar. No lo comparta con nadie.

Si no lo ha pedido, ignore este correo.

{utility_name}""",
        ),
        "es-MX": (
            "Tu código de {utility_name}",
            """Tu código de {utility_name} es {code}

Escríbelo en la pantalla para continuar. No se lo compartas a nadie.

Si no lo pediste, ignora este correo.

{utility_name}""",
        ),
        "de": (
            "Ihr Code von {utility_name}",
            """Ihr Code von {utility_name} lautet {code}

Geben Sie ihn auf dem Bildschirm ein, um fortzufahren. Geben Sie ihn an niemanden weiter.

Wenn Sie ihn nicht angefordert haben, ignorieren Sie diese E-Mail.

{utility_name}""",
        ),
        "hi": (
            "आपका {utility_name} कोड",
            """आपका {utility_name} कोड है {code}

आगे बढ़ने के लिए इसे स्क्रीन पर दर्ज करें। इसे किसी के साथ साझा न करें।

अगर आपने इसका अनुरोध नहीं किया है, तो इस ईमेल को अनदेखा करें।

{utility_name}""",
        ),
        "fr-FR": (
            "Votre code {utility_name}",
            """Votre code {utility_name} est {code}

Saisissez-le à l’écran pour continuer. Ne le communiquez à personne.

Si vous ne l’avez pas demandé, ignorez ce message.

{utility_name}""",
        ),
        "id-ID": (
            "Kode {utility_name} Anda",
            """Kode {utility_name} Anda adalah {code}

Masukkan di layar untuk melanjutkan. Jangan berikan kode ini kepada siapa pun.

Jika Anda tidak memintanya, abaikan email ini.

{utility_name}""",
        ),
        "it-IT": (
            "Il suo codice {utility_name}",
            """Il suo codice {utility_name} è {code}

Lo inserisca sullo schermo per continuare. Non lo comunichi a nessuno.

Se non l’ha richiesto, ignori questa email.

{utility_name}""",
        ),
        "ja-JP": (
            "{utility_name} 確認コード",
            """{utility_name} の確認コードは {code} です。

画面に入力して続けてください。このコードは誰にも教えないでください。

お心当たりがない場合は、このメールを破棄してください。

{utility_name}""",
        ),
        "ko-KR": (
            "{utility_name} 인증 코드",
            """{utility_name} 인증 코드는 {code} 입니다.

화면에 입력하여 계속하세요. 이 코드는 누구에게도 알려 주지 마세요.

요청하신 적이 없다면 이 메일을 무시하세요.

{utility_name}""",
        ),
        "pt-BR": (
            "Seu código da {utility_name}",
            """Seu código da {utility_name} é {code}

Digite-o na tela para continuar. Não compartilhe com ninguém.

Se você não pediu, ignore este e-mail.

{utility_name}""",
        ),
    },
    "portal_email_change_code": {
        "en": (
            "Confirm your new email for {utility_name}",
            """Hi {customer_name},

Someone asked to make this the registered email for your {utility_name} customer portal.

Your confirmation code is {code}

Enter it on the screen to finish. If you did not ask for this, ignore this email and nothing changes.

Questions? Call {support_phone} or email {support_email}.

{utility_name}""",
        ),
        "es": (
            "Confirme su nuevo correo para {utility_name}",
            """Hola, {customer_name}:

Se ha pedido que esta sea la dirección de correo registrada de su portal de clientes de {utility_name}.

Su código de confirmación es {code}

Introdúzcalo en la pantalla para terminar. Si no lo ha pedido usted, ignore este correo y no cambiará nada.

¿Dudas? Llame al {support_phone} o escriba a {support_email}.

{utility_name}""",
        ),
        "es-MX": (
            "Confirma tu nuevo correo para {utility_name}",
            """Hola, {customer_name}:

Alguien pidió que este sea el correo registrado de tu portal de clientes de {utility_name}.

Tu código de confirmación es {code}

Escríbelo en la pantalla para terminar. Si tú no lo pediste, ignora este correo y no cambiará nada.

¿Tienes dudas? Llámanos al {support_phone} o escríbenos a {support_email}.

{utility_name}""",
        ),
        "de": (
            "Bestätigen Sie Ihre neue E-Mail-Adresse bei {utility_name}",
            """Hallo {customer_name},

es wurde beantragt, diese Adresse als hinterlegte E-Mail-Adresse für Ihr Kundenportal von {utility_name} zu verwenden.

Ihr Bestätigungscode lautet {code}

Geben Sie ihn auf dem Bildschirm ein, um den Vorgang abzuschließen. Wenn Sie das nicht beantragt haben, ignorieren Sie diese E-Mail – es ändert sich nichts.

Fragen? Rufen Sie uns an unter {support_phone} oder schreiben Sie an {support_email}.

{utility_name}""",
        ),
        "hi": (
            "{utility_name} के लिए अपना नया ईमेल पुष्टि करें",
            """नमस्ते {customer_name},

किसी ने अनुरोध किया है कि यह पता आपके {utility_name} ग्राहक पोर्टल का पंजीकृत ईमेल बने।

आपका पुष्टि कोड है {code}

पूरा करने के लिए इसे स्क्रीन पर दर्ज करें। अगर आपने यह अनुरोध नहीं किया है, तो इस ईमेल को अनदेखा करें — कुछ नहीं बदलेगा।

कोई सवाल? {support_phone} पर कॉल करें या {support_email} पर लिखें।

{utility_name}""",
        ),
        "fr-FR": (
            "Confirmez votre nouvelle adresse e-mail pour {utility_name}",
            """Bonjour {customer_name},

Une demande a été faite pour que cette adresse devienne l’e-mail enregistré de votre espace client {utility_name}.

Votre code de confirmation est {code}

Saisissez-le à l’écran pour terminer. Si vous n’êtes pas à l’origine de cette demande, ignorez ce message : rien ne changera.

Des questions ? Appelez le {support_phone} ou écrivez à {support_email}.

{utility_name}""",
        ),
        "id-ID": (
            "Konfirmasi email baru Anda untuk {utility_name}",
            """Halo {customer_name},

Ada permintaan agar alamat ini menjadi email terdaftar untuk portal pelanggan {utility_name} Anda.

Kode konfirmasi Anda adalah {code}

Masukkan kode ini di layar untuk menyelesaikannya. Jika Anda tidak memintanya, abaikan email ini dan tidak ada yang berubah.

Ada pertanyaan? Hubungi {support_phone} atau kirim email ke {support_email}.

{utility_name}""",
        ),
        "it-IT": (
            "Conferma il nuovo indirizzo email per {utility_name}",
            """Gentile {customer_name},

è stato chiesto di registrare questo indirizzo come email della sua area clienti {utility_name}.

Il suo codice di conferma è {code}

Lo inserisca sullo schermo per completare. Se non ha fatto lei la richiesta, ignori questa email: non cambierà nulla.

Domande? Chiami il {support_phone} o scriva a {support_email}.

{utility_name}""",
        ),
        "ja-JP": (
            "{utility_name} 新しいメールアドレスの確認",
            """{customer_name} 様

{utility_name} お客さまポータルの登録メールアドレスを、このアドレスに変更するご依頼を受け付けました。

確認コード: {code}

画面にこのコードを入力して手続きを完了してください。お心当たりがない場合は、このメールを破棄してください。何も変更されません。

ご不明な点は {support_phone} までお電話いただくか、{support_email} までご連絡ください。

{utility_name}""",
        ),
        "ko-KR": (
            "{utility_name} 새 이메일 주소 확인",
            """{customer_name} 님, 안녕하세요.

이 주소를 {utility_name} 고객 포털의 등록 이메일로 사용하겠다는 요청이 접수되었습니다.

확인 코드는 {code} 입니다.

화면에 이 코드를 입력하면 변경이 완료됩니다. 요청하신 적이 없다면 이 메일을 무시하셔도 되며, 아무것도 바뀌지 않습니다.

문의 사항은 {support_phone}로 전화하시거나 {support_email}로 메일을 보내 주세요.

{utility_name}""",
        ),
        "pt-BR": (
            "Confirme seu novo e-mail na {utility_name}",
            """Olá, {customer_name},

Recebemos um pedido para que este seja o e-mail cadastrado do seu portal do cliente {utility_name}.

Seu código de confirmação é {code}

Digite-o na tela para concluir. Se não foi você quem pediu, ignore este e-mail e nada vai mudar.

Dúvidas? Ligue para {support_phone} ou escreva para {support_email}.

{utility_name}""",
        ),
    },
    "portal_email_changed_notice": {
        "en": (
            "Your {utility_name} registered email was changed",
            """Hi {customer_name},

The registered email for your {utility_name} customer portal was changed to {new_email_masked}.

If you made this change, there is nothing more to do.

If you did not, call us now on {support_phone} or email {support_email}.

{utility_name}""",
        ),
        "es": (
            "Se ha cambiado su correo registrado en {utility_name}",
            """Hola, {customer_name}:

El correo registrado de su portal de clientes de {utility_name} se ha cambiado a {new_email_masked}.

Si ha hecho usted el cambio, no tiene que hacer nada más.

Si no ha sido usted, llámenos ahora al {support_phone} o escriba a {support_email}.

{utility_name}""",
        ),
        "es-MX": (
            "Se cambió tu correo registrado en {utility_name}",
            """Hola, {customer_name}:

El correo registrado de tu portal de clientes de {utility_name} se cambió a {new_email_masked}.

Si tú hiciste el cambio, no tienes que hacer nada más.

Si no fuiste tú, llámanos ya al {support_phone} o escríbenos a {support_email}.

{utility_name}""",
        ),
        "de": (
            "Ihre bei {utility_name} hinterlegte E-Mail-Adresse wurde geändert",
            """Hallo {customer_name},

die hinterlegte E-Mail-Adresse für Ihr Kundenportal von {utility_name} wurde in {new_email_masked} geändert.

Wenn Sie das selbst waren, müssen Sie nichts weiter tun.

Wenn nicht, rufen Sie uns bitte sofort an unter {support_phone} oder schreiben Sie an {support_email}.

{utility_name}""",
        ),
        "hi": (
            "{utility_name} में आपका पंजीकृत ईमेल बदल दिया गया है",
            """नमस्ते {customer_name},

आपके {utility_name} ग्राहक पोर्टल का पंजीकृत ईमेल बदलकर {new_email_masked} कर दिया गया है।

अगर यह बदलाव आपने किया है, तो आपको कुछ और करने की ज़रूरत नहीं है।

अगर आपने नहीं किया, तो तुरंत {support_phone} पर कॉल करें या {support_email} पर लिखें।

{utility_name}""",
        ),
        "fr-FR": (
            "Votre adresse e-mail enregistrée chez {utility_name} a été modifiée",
            """Bonjour {customer_name},

L’adresse e-mail enregistrée de votre espace client {utility_name} a été remplacée par {new_email_masked}.

Si c’est vous qui avez fait ce changement, vous n’avez rien d’autre à faire.

Sinon, appelez-nous sans attendre au {support_phone} ou écrivez à {support_email}.

{utility_name}""",
        ),
        "id-ID": (
            "Email terdaftar Anda di {utility_name} telah diubah",
            """Halo {customer_name},

Email terdaftar untuk portal pelanggan {utility_name} Anda telah diubah menjadi {new_email_masked}.

Jika Anda yang mengubahnya, tidak ada lagi yang perlu dilakukan.

Jika bukan Anda, segera hubungi {support_phone} atau kirim email ke {support_email}.

{utility_name}""",
        ),
        "it-IT": (
            "L’email registrata presso {utility_name} è stata modificata",
            """Gentile {customer_name},

l’email registrata della sua area clienti {utility_name} è stata cambiata in {new_email_masked}.

Se la modifica l’ha fatta lei, non deve fare altro.

In caso contrario, ci chiami subito al {support_phone} o scriva a {support_email}.

{utility_name}""",
        ),
        "ja-JP": (
            "{utility_name} 登録メールアドレスが変更されました",
            """{customer_name} 様

{utility_name} お客さまポータルの登録メールアドレスが {new_email_masked} に変更されました。

ご本人による変更であれば、これ以上の手続きは不要です。

お心当たりがない場合は、至急 {support_phone} までお電話いただくか、{support_email} までご連絡ください。

{utility_name}""",
        ),
        "ko-KR": (
            "{utility_name} 등록 이메일이 변경되었습니다",
            """{customer_name} 님, 안녕하세요.

{utility_name} 고객 포털의 등록 이메일이 {new_email_masked}(으)로 변경되었습니다.

직접 변경하셨다면 더 하실 일은 없습니다.

변경하신 적이 없다면 지금 바로 {support_phone}로 전화하시거나 {support_email}로 메일을 보내 주세요.

{utility_name}""",
        ),
        "pt-BR": (
            "Seu e-mail cadastrado na {utility_name} foi alterado",
            """Olá, {customer_name},

O e-mail cadastrado do seu portal do cliente {utility_name} foi alterado para {new_email_masked}.

Se foi você quem fez a alteração, não precisa fazer mais nada.

Se não foi você, ligue agora para {support_phone} ou escreva para {support_email}.

{utility_name}""",
        ),
    },
}

#: The written language a `default` variant carries.
DEFAULT_WORDING_LANGUAGE = "en"


def wording_for(code: str, language: str) -> tuple[str, str] | None:
    """`(subject, body)` for one class in one language — the exact tag, else its
    primary language (`en-US` → `en`, `es-419` → `es`), else None."""
    table = WORDING.get(code) or {}
    if language in table:
        return table[language]
    primary = language.split("-", 1)[0]
    return table.get(primary)
