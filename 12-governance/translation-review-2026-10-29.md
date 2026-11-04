# Translation review — texts added or changed on 2026-10-29

**Why this exists.** PO ruling **B5 A** (2026-10-29, decision log *"Templates, notifications and communication: twelve questions ruled in one message"*): *the ten non-English versions of the new letters and messages are reviewed by a native speaker before go-live; we list exactly which texts.* This is that list. Every non-English text below was written by an AI lane, not by a native speaker, and no person has read it yet.

**How to use it.** One section per language. Tick a row when a native speaker has read the text and either approved it or corrected it on Settings › Templates (the seeded text is a default each utility can edit). Leave `{tokens}` in braces exactly as they are — they are filled in when the message is sent.

**How it was found.** Every commit of 2026-10-29 touching `06-backend/apps/notifications/seed_templates.py` or `06-backend/apps/notifications/migrations/`: `a7c51cb35` (`DEF-NOT-10649`, service disconnected / restored), `d8c381b30` (`DEF-WRK-10652`, work order logged and the visit preparation text), `e724ff03d` (`DEF-PAY-10651`, the printed past-due reminder). The SMS commits of the day (`a22ce5942`, `a82043dda`, `CR-198-BRC10`) add no customer-facing wording — STOP is answered by Twilio at the carrier level.

⚠ **Six texts have NO translation at all** — the work-order-logged pair, the three visit messages that gained a preparation paragraph, and the default preparation sentence. They exist in English only, so a customer in any of these ten languages receives English (and, under the PO's ruling of the same day that a message follows the customer's preferred language, English is the fallback). They are listed under each language as **To translate** so the reviewer can supply the wording; nothing on the product side changes until someone does.

Languages: German (`de`), Spanish (Spain) (`es`), Spanish (Mexico) (`es-MX`), French (`fr-FR`), Hindi (`hi`), Indonesian (`id-ID`), Italian (`it-IT`), Japanese (`ja-JP`), Korean (`ko-KR`), Portuguese (Brazil) (`pt-BR`).

## German — `de`

### To review (written today, in this language)

| ✓ | Template code | Channel | From | Subject |
|---|---|---|---|---|
| [ ] | `service_disconnected_guide` | Email | `DEF-NOT-10649` (a7c51cb35, `service_state_wording.py`) | Ihre Versorgung durch {utility_name} unter {service_address} wurde gesperrt |
| [ ] | `service_restored` | Email | `DEF-NOT-10649` (a7c51cb35, `service_state_wording.py`) | Ihre Versorgung durch {utility_name} unter {service_address} ist wiederhergestellt |
| [ ] | `sms_service_disconnected` | SMS | `DEF-NOT-10649` (a7c51cb35, `service_state_wording.py`) | *(no subject)* |
| [ ] | `sms_service_restored` | SMS | `DEF-NOT-10649` (a7c51cb35, `service_state_wording.py`) | *(no subject)* |
| [ ] | `dunning` | Print (letter) | `DEF-PAY-10651` (e724ff03d, `past_due_letter_wording.py`) | *(no subject)* |

**`service_disconnected_guide` · Email · de**

Subject: Ihre Versorgung durch {utility_name} unter {service_address} wurde gesperrt

```text
Guten Tag {customer_name},

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

{utility_name}
```

**`service_restored` · Email · de**

Subject: Ihre Versorgung durch {utility_name} unter {service_address} ist wiederhergestellt

```text
Guten Tag {customer_name},

Ihre Versorgung unter {service_address} (Kundennummer {account_no}) wurde am {restored_at} wiederhergestellt.

Wenn die Versorgung wieder anläuft:
Öffnen Sie die Wasserhähne langsam und lassen Sie das Wasser laufen, bis es klar ist.
Bemerken Sie ein Leck oder riecht es nach Gas, verlassen Sie das Gebäude und rufen Sie {support_phone} an.

Fragen? Rufen Sie uns an unter {support_phone}.

{utility_name}
```

**`sms_service_disconnected` · SMS · de**

```text
{utility_name}: Versorgung am {cut_date} gesperrt. Zur Freigabe {total_to_restore} zahlen. Nicht selbst anschließen. Medizinischer Notfall: {support_phone}
```

**`sms_service_restored` · SMS · de**

```text
{utility_name}: Ihre Versorgung ist wiederhergestellt. Hähne langsam öffnen. Leck oder Gasgeruch? Rufen Sie {support_phone} an.
```

**`dunning` · Print (letter) · de**

```text
Guten Tag {customer_name}, wir möchten Sie freundlich daran erinnern, dass auf Ihrem Kundenkonto {account} noch ein Betrag von {balance} offen ist. Sie können jederzeit online bezahlen. Vielen Dank, dass Sie Kunde bei uns sind.
```

### To translate (English only today)

| ✓ | Template code | Channel | From |
|---|---|---|---|
| [ ] | `service_work_order_logged` | Email | `DEF-WRK-10652` (d8c381b30) — new |
| [ ] | `sms_work_order_logged` | SMS | `DEF-WRK-10652` (d8c381b30) — new |
| [ ] | `service_appointment` | Email | `DEF-WRK-10652` (d8c381b30) — *Before we arrive* paragraph added |
| [ ] | `service_visit_moved` | Email | `DEF-WRK-10652` (d8c381b30) — *Before we arrive* paragraph added |
| [ ] | `sms_visit_booked` | SMS | `DEF-WRK-10652` (d8c381b30) — preparation paragraph added |
| [ ] | `visit preparation default (`work_settings.visit_prep_default`)` | Fills `{prep_instructions}` | `DEF-WRK-10652` (d8c381b30) — new |

## Spanish (Spain) — `es`

### To review (written today, in this language)

| ✓ | Template code | Channel | From | Subject |
|---|---|---|---|---|
| [ ] | `service_disconnected_guide` | Email | `DEF-NOT-10649` (a7c51cb35, `service_state_wording.py`) | Tu servicio de {utility_name} en {service_address} ha sido cortado |
| [ ] | `service_restored` | Email | `DEF-NOT-10649` (a7c51cb35, `service_state_wording.py`) | Tu servicio de {utility_name} en {service_address} vuelve a funcionar |
| [ ] | `sms_service_disconnected` | SMS | `DEF-NOT-10649` (a7c51cb35, `service_state_wording.py`) | *(no subject)* |
| [ ] | `sms_service_restored` | SMS | `DEF-NOT-10649` (a7c51cb35, `service_state_wording.py`) | *(no subject)* |
| [ ] | `dunning` | Print (letter) | `DEF-PAY-10651` (e724ff03d, `past_due_letter_wording.py`) | *(no subject)* |

**`service_disconnected_guide` · Email · es**

Subject: Tu servicio de {utility_name} en {service_address} ha sido cortado

```text
Hola, {first_name}:

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

{utility_name}
```

**`service_restored` · Email · es**

Subject: Tu servicio de {utility_name} en {service_address} vuelve a funcionar

```text
Hola, {first_name}:

Tu servicio en {service_address} (cuenta {account_no}) se restableció el {restored_at}.

Ahora que vuelve el servicio:
Abre los grifos poco a poco y deja correr el agua hasta que salga limpia.
Si ves una fuga o huele a gas, sal de la vivienda y llama al {support_phone}.

¿Dudas? Llama al {support_phone}.

{utility_name}
```

**`sms_service_disconnected` · SMS · es**

```text
{utility_name}: servicio cortado el {cut_date}. Paga {total_to_restore} para recuperarlo. No lo reconectes tú. ¿Urgencia médica? {support_phone}
```

**`sms_service_restored` · SMS · es**

```text
{utility_name}: tu servicio vuelve a funcionar. Abre los grifos poco a poco. ¿Fuga u olor a gas? Llama al {support_phone}.
```

**`dunning` · Print (letter) · es**

```text
Hola, {first_name}: te recordamos amablemente que tu cuenta {account} tiene un saldo pendiente de {balance}. Puedes pagar en línea cuando quieras. Gracias por confiar en nosotros.
```

### To translate (English only today)

| ✓ | Template code | Channel | From |
|---|---|---|---|
| [ ] | `service_work_order_logged` | Email | `DEF-WRK-10652` (d8c381b30) — new |
| [ ] | `sms_work_order_logged` | SMS | `DEF-WRK-10652` (d8c381b30) — new |
| [ ] | `service_appointment` | Email | `DEF-WRK-10652` (d8c381b30) — *Before we arrive* paragraph added |
| [ ] | `service_visit_moved` | Email | `DEF-WRK-10652` (d8c381b30) — *Before we arrive* paragraph added |
| [ ] | `sms_visit_booked` | SMS | `DEF-WRK-10652` (d8c381b30) — preparation paragraph added |
| [ ] | `visit preparation default (`work_settings.visit_prep_default`)` | Fills `{prep_instructions}` | `DEF-WRK-10652` (d8c381b30) — new |

## Spanish (Mexico) — `es-MX`

### To review (written today, in this language)

| ✓ | Template code | Channel | From | Subject |
|---|---|---|---|---|
| [ ] | `service_disconnected_guide` | Email | `DEF-NOT-10649` (a7c51cb35, `service_state_wording.py`) | Se suspendió tu servicio de {utility_name} en {service_address} |
| [ ] | `service_restored` | Email | `DEF-NOT-10649` (a7c51cb35, `service_state_wording.py`) | Ya se reconectó tu servicio de {utility_name} en {service_address} |
| [ ] | `sms_service_disconnected` | SMS | `DEF-NOT-10649` (a7c51cb35, `service_state_wording.py`) | *(no subject)* |
| [ ] | `sms_service_restored` | SMS | `DEF-NOT-10649` (a7c51cb35, `service_state_wording.py`) | *(no subject)* |
| [ ] | `dunning` | Print (letter) | `DEF-PAY-10651` (e724ff03d, `past_due_letter_wording.py`) | *(no subject)* |

**`service_disconnected_guide` · Email · es-MX**

Subject: Se suspendió tu servicio de {utility_name} en {service_address}

```text
Hola, {first_name}:

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

{utility_name}
```

**`service_restored` · Email · es-MX**

Subject: Ya se reconectó tu servicio de {utility_name} en {service_address}

```text
Hola, {first_name}:

Tu servicio en {service_address} (cuenta {account_no}) se reconectó el {restored_at}.

Ahora que regresa el servicio:
Abre las llaves despacio y deja correr el agua hasta que salga clara.
Si ves una fuga o hueles a gas, sal de la casa y llámanos al {support_phone}.

¿Dudas? Llámanos al {support_phone}.

{utility_name}
```

**`sms_service_disconnected` · SMS · es-MX**

```text
{utility_name}: servicio suspendido el {cut_date}. Paga {total_to_restore} para reconectar. No lo reconectes tú. ¿Urgencia médica? {support_phone}
```

**`sms_service_restored` · SMS · es-MX**

```text
{utility_name}: ya se reconectó tu servicio. Abre las llaves despacio. ¿Fuga u olor a gas? Llámanos al {support_phone}.
```

**`dunning` · Print (letter) · es-MX**

```text
Hola, {first_name}: te recordamos que tu cuenta {account} tiene un saldo pendiente de {balance}. Puedes pagar en línea cuando gustes. Gracias por ser nuestro cliente.
```

### To translate (English only today)

| ✓ | Template code | Channel | From |
|---|---|---|---|
| [ ] | `service_work_order_logged` | Email | `DEF-WRK-10652` (d8c381b30) — new |
| [ ] | `sms_work_order_logged` | SMS | `DEF-WRK-10652` (d8c381b30) — new |
| [ ] | `service_appointment` | Email | `DEF-WRK-10652` (d8c381b30) — *Before we arrive* paragraph added |
| [ ] | `service_visit_moved` | Email | `DEF-WRK-10652` (d8c381b30) — *Before we arrive* paragraph added |
| [ ] | `sms_visit_booked` | SMS | `DEF-WRK-10652` (d8c381b30) — preparation paragraph added |
| [ ] | `visit preparation default (`work_settings.visit_prep_default`)` | Fills `{prep_instructions}` | `DEF-WRK-10652` (d8c381b30) — new |

## French — `fr-FR`

### To review (written today, in this language)

| ✓ | Template code | Channel | From | Subject |
|---|---|---|---|---|
| [ ] | `service_disconnected_guide` | Email | `DEF-NOT-10649` (a7c51cb35, `service_state_wording.py`) | Votre service {utility_name} au {service_address} a été coupé |
| [ ] | `service_restored` | Email | `DEF-NOT-10649` (a7c51cb35, `service_state_wording.py`) | Votre service {utility_name} au {service_address} est rétabli |
| [ ] | `sms_service_disconnected` | SMS | `DEF-NOT-10649` (a7c51cb35, `service_state_wording.py`) | *(no subject)* |
| [ ] | `sms_service_restored` | SMS | `DEF-NOT-10649` (a7c51cb35, `service_state_wording.py`) | *(no subject)* |
| [ ] | `dunning` | Print (letter) | `DEF-PAY-10651` (e724ff03d, `past_due_letter_wording.py`) | *(no subject)* |

**`service_disconnected_guide` · Email · fr-FR**

Subject: Votre service {utility_name} au {service_address} a été coupé

```text
Bonjour {first_name},

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

{utility_name}
```

**`service_restored` · Email · fr-FR**

Subject: Votre service {utility_name} au {service_address} est rétabli

```text
Bonjour {first_name},

Votre service au {service_address} (compte {account_no}) a été rétabli le {restored_at}.

À la remise en service :
Ouvrez les robinets doucement et laissez couler l'eau jusqu'à ce qu'elle soit claire.
En cas de fuite ou d'odeur de gaz, quittez le logement et appelez le {support_phone}.

Une question ? Appelez-nous au {support_phone}.

{utility_name}
```

**`sms_service_disconnected` · SMS · fr-FR**

```text
{utility_name} : service coupé le {cut_date}. Réglez {total_to_restore} pour le rétablir. Ne rebranchez pas vous-même. Besoin médical ? {support_phone}
```

**`sms_service_restored` · SMS · fr-FR**

```text
{utility_name} : votre service est rétabli. Ouvrez les robinets doucement. Fuite ou odeur de gaz ? Appelez le {support_phone}.
```

**`dunning` · Print (letter) · fr-FR**

```text
Bonjour {first_name}, nous vous rappelons que votre compte {account} présente un solde de {balance}. Vous pouvez régler en ligne à tout moment. Merci de votre confiance.
```

### To translate (English only today)

| ✓ | Template code | Channel | From |
|---|---|---|---|
| [ ] | `service_work_order_logged` | Email | `DEF-WRK-10652` (d8c381b30) — new |
| [ ] | `sms_work_order_logged` | SMS | `DEF-WRK-10652` (d8c381b30) — new |
| [ ] | `service_appointment` | Email | `DEF-WRK-10652` (d8c381b30) — *Before we arrive* paragraph added |
| [ ] | `service_visit_moved` | Email | `DEF-WRK-10652` (d8c381b30) — *Before we arrive* paragraph added |
| [ ] | `sms_visit_booked` | SMS | `DEF-WRK-10652` (d8c381b30) — preparation paragraph added |
| [ ] | `visit preparation default (`work_settings.visit_prep_default`)` | Fills `{prep_instructions}` | `DEF-WRK-10652` (d8c381b30) — new |

## Hindi — `hi`

### To review (written today, in this language)

| ✓ | Template code | Channel | From | Subject |
|---|---|---|---|---|
| [ ] | `service_disconnected_guide` | Email | `DEF-NOT-10649` (a7c51cb35, `service_state_wording.py`) | {service_address} पर आपकी {utility_name} सेवा काट दी गई है |
| [ ] | `service_restored` | Email | `DEF-NOT-10649` (a7c51cb35, `service_state_wording.py`) | {service_address} पर आपकी {utility_name} सेवा फिर से शुरू हो गई है |
| [ ] | `sms_service_disconnected` | SMS | `DEF-NOT-10649` (a7c51cb35, `service_state_wording.py`) | *(no subject)* |
| [ ] | `sms_service_restored` | SMS | `DEF-NOT-10649` (a7c51cb35, `service_state_wording.py`) | *(no subject)* |
| [ ] | `dunning` | Print (letter) | `DEF-PAY-10651` (e724ff03d, `past_due_letter_wording.py`) | *(no subject)* |

**`service_disconnected_guide` · Email · hi**

Subject: {service_address} पर आपकी {utility_name} सेवा काट दी गई है

```text
नमस्ते {first_name},

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

{utility_name}
```

**`service_restored` · Email · hi**

Subject: {service_address} पर आपकी {utility_name} सेवा फिर से शुरू हो गई है

```text
नमस्ते {first_name},

{service_address} (खाता {account_no}) पर आपकी सेवा {restored_at} को फिर से शुरू कर दी गई।

सेवा दोबारा शुरू होने पर:
नल धीरे-धीरे खोलें और पानी साफ़ आने तक बहने दें।
अगर कहीं रिसाव दिखे या गैस की गंध आए, तो घर से बाहर निकलें और {support_phone} पर कॉल करें।

कोई सवाल? {support_phone} पर कॉल करें।

{utility_name}
```

**`sms_service_disconnected` · SMS · hi**

```text
{utility_name}: सेवा {cut_date} को काटी गई। दोबारा शुरू करने के लिए {total_to_restore} चुकाएँ। खुद न जोड़ें। चिकित्सा ज़रूरत? {support_phone}
```

**`sms_service_restored` · SMS · hi**

```text
{utility_name}: आपकी सेवा फिर से शुरू हो गई है। नल धीरे खोलें। रिसाव या गैस की गंध? {support_phone} पर कॉल करें।
```

**`dunning` · Print (letter) · hi**

```text
नमस्ते {first_name}, यह एक विनम्र याद-दिहानी है कि आपके खाते {account} में {balance} की राशि बकाया है। आप कभी भी ऑनलाइन भुगतान कर सकते हैं। हमारे ग्राहक होने के लिए धन्यवाद।
```

### To translate (English only today)

| ✓ | Template code | Channel | From |
|---|---|---|---|
| [ ] | `service_work_order_logged` | Email | `DEF-WRK-10652` (d8c381b30) — new |
| [ ] | `sms_work_order_logged` | SMS | `DEF-WRK-10652` (d8c381b30) — new |
| [ ] | `service_appointment` | Email | `DEF-WRK-10652` (d8c381b30) — *Before we arrive* paragraph added |
| [ ] | `service_visit_moved` | Email | `DEF-WRK-10652` (d8c381b30) — *Before we arrive* paragraph added |
| [ ] | `sms_visit_booked` | SMS | `DEF-WRK-10652` (d8c381b30) — preparation paragraph added |
| [ ] | `visit preparation default (`work_settings.visit_prep_default`)` | Fills `{prep_instructions}` | `DEF-WRK-10652` (d8c381b30) — new |

## Indonesian — `id-ID`

### To review (written today, in this language)

| ✓ | Template code | Channel | From | Subject |
|---|---|---|---|---|
| [ ] | `service_disconnected_guide` | Email | `DEF-NOT-10649` (a7c51cb35, `service_state_wording.py`) | Layanan {utility_name} Anda di {service_address} telah diputus |
| [ ] | `service_restored` | Email | `DEF-NOT-10649` (a7c51cb35, `service_state_wording.py`) | Layanan {utility_name} Anda di {service_address} sudah tersambung kembali |
| [ ] | `sms_service_disconnected` | SMS | `DEF-NOT-10649` (a7c51cb35, `service_state_wording.py`) | *(no subject)* |
| [ ] | `sms_service_restored` | SMS | `DEF-NOT-10649` (a7c51cb35, `service_state_wording.py`) | *(no subject)* |
| [ ] | `dunning` | Print (letter) | `DEF-PAY-10651` (e724ff03d, `past_due_letter_wording.py`) | *(no subject)* |

**`service_disconnected_guide` · Email · id-ID**

Subject: Layanan {utility_name} Anda di {service_address} telah diputus

```text
Halo {first_name},

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

{utility_name}
```

**`service_restored` · Email · id-ID**

Subject: Layanan {utility_name} Anda di {service_address} sudah tersambung kembali

```text
Halo {first_name},

Layanan Anda di {service_address} (rekening {account_no}) tersambung kembali pada {restored_at}.

Saat layanan kembali menyala:
Buka keran perlahan dan biarkan air mengalir sampai jernih.
Jika ada kebocoran atau tercium bau gas, tinggalkan rumah dan hubungi {support_phone}.

Ada pertanyaan? Hubungi {support_phone}.

{utility_name}
```

**`sms_service_disconnected` · SMS · id-ID**

```text
{utility_name}: layanan diputus {cut_date}. Bayar {total_to_restore} untuk menyambung kembali. Jangan sambung sendiri. Darurat medis? {support_phone}
```

**`sms_service_restored` · SMS · id-ID**

```text
{utility_name}: layanan Anda sudah tersambung kembali. Buka keran perlahan. Bocor atau bau gas? Hubungi {support_phone}.
```

**`dunning` · Print (letter) · id-ID**

```text
Halo {first_name}, kami ingin mengingatkan bahwa akun Anda {account} memiliki tagihan sebesar {balance}. Anda dapat membayar secara online kapan saja. Terima kasih telah menjadi pelanggan kami.
```

### To translate (English only today)

| ✓ | Template code | Channel | From |
|---|---|---|---|
| [ ] | `service_work_order_logged` | Email | `DEF-WRK-10652` (d8c381b30) — new |
| [ ] | `sms_work_order_logged` | SMS | `DEF-WRK-10652` (d8c381b30) — new |
| [ ] | `service_appointment` | Email | `DEF-WRK-10652` (d8c381b30) — *Before we arrive* paragraph added |
| [ ] | `service_visit_moved` | Email | `DEF-WRK-10652` (d8c381b30) — *Before we arrive* paragraph added |
| [ ] | `sms_visit_booked` | SMS | `DEF-WRK-10652` (d8c381b30) — preparation paragraph added |
| [ ] | `visit preparation default (`work_settings.visit_prep_default`)` | Fills `{prep_instructions}` | `DEF-WRK-10652` (d8c381b30) — new |

## Italian — `it-IT`

### To review (written today, in this language)

| ✓ | Template code | Channel | From | Subject |
|---|---|---|---|---|
| [ ] | `service_disconnected_guide` | Email | `DEF-NOT-10649` (a7c51cb35, `service_state_wording.py`) | La sua fornitura {utility_name} in {service_address} è stata sospesa |
| [ ] | `service_restored` | Email | `DEF-NOT-10649` (a7c51cb35, `service_state_wording.py`) | La sua fornitura {utility_name} in {service_address} è stata riattivata |
| [ ] | `sms_service_disconnected` | SMS | `DEF-NOT-10649` (a7c51cb35, `service_state_wording.py`) | *(no subject)* |
| [ ] | `sms_service_restored` | SMS | `DEF-NOT-10649` (a7c51cb35, `service_state_wording.py`) | *(no subject)* |
| [ ] | `dunning` | Print (letter) | `DEF-PAY-10651` (e724ff03d, `past_due_letter_wording.py`) | *(no subject)* |

**`service_disconnected_guide` · Email · it-IT**

Subject: La sua fornitura {utility_name} in {service_address} è stata sospesa

```text
Gentile {customer_name},

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

{utility_name}
```

**`service_restored` · Email · it-IT**

Subject: La sua fornitura {utility_name} in {service_address} è stata riattivata

```text
Gentile {customer_name},

la sua fornitura in {service_address} (codice cliente {account_no}) è stata riattivata il {restored_at}.

Alla riattivazione:
Apra i rubinetti lentamente e lasci scorrere l'acqua finché non è limpida.
Se nota una perdita o sente odore di gas, esca dall'abitazione e chiami il {support_phone}.

Domande? Ci chiami al {support_phone}.

{utility_name}
```

**`sms_service_disconnected` · SMS · it-IT**

```text
{utility_name}: fornitura sospesa il {cut_date}. Paghi {total_to_restore} per riattivarla. Non la ricolleghi da solo. Necessità mediche: {support_phone}
```

**`sms_service_restored` · SMS · it-IT**

```text
{utility_name}: la fornitura è riattivata. Apra i rubinetti lentamente. Perdite o odore di gas? Chiami il {support_phone}.
```

**`dunning` · Print (letter) · it-IT**

```text
Gentile {customer_name}, Le ricordiamo cortesemente che sul Suo conto {account} risulta un saldo di {balance}. Può pagare online in qualsiasi momento. La ringraziamo per essere nostro cliente.
```

### To translate (English only today)

| ✓ | Template code | Channel | From |
|---|---|---|---|
| [ ] | `service_work_order_logged` | Email | `DEF-WRK-10652` (d8c381b30) — new |
| [ ] | `sms_work_order_logged` | SMS | `DEF-WRK-10652` (d8c381b30) — new |
| [ ] | `service_appointment` | Email | `DEF-WRK-10652` (d8c381b30) — *Before we arrive* paragraph added |
| [ ] | `service_visit_moved` | Email | `DEF-WRK-10652` (d8c381b30) — *Before we arrive* paragraph added |
| [ ] | `sms_visit_booked` | SMS | `DEF-WRK-10652` (d8c381b30) — preparation paragraph added |
| [ ] | `visit preparation default (`work_settings.visit_prep_default`)` | Fills `{prep_instructions}` | `DEF-WRK-10652` (d8c381b30) — new |

## Japanese — `ja-JP`

### To review (written today, in this language)

| ✓ | Template code | Channel | From | Subject |
|---|---|---|---|---|
| [ ] | `service_disconnected_guide` | Email | `DEF-NOT-10649` (a7c51cb35, `service_state_wording.py`) | {service_address}の{utility_name}の供給を停止しました |
| [ ] | `service_restored` | Email | `DEF-NOT-10649` (a7c51cb35, `service_state_wording.py`) | {service_address}の{utility_name}の供給を再開しました |
| [ ] | `sms_service_disconnected` | SMS | `DEF-NOT-10649` (a7c51cb35, `service_state_wording.py`) | *(no subject)* |
| [ ] | `sms_service_restored` | SMS | `DEF-NOT-10649` (a7c51cb35, `service_state_wording.py`) | *(no subject)* |
| [ ] | `dunning` | Print (letter) | `DEF-PAY-10651` (e724ff03d, `past_due_letter_wording.py`) | *(no subject)* |

**`service_disconnected_guide` · Email · ja-JP**

Subject: {service_address}の{utility_name}の供給を停止しました

```text
{customer_name} 様

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

{utility_name}
```

**`service_restored` · Email · ja-JP**

Subject: {service_address}の{utility_name}の供給を再開しました

```text
{customer_name} 様

{service_address}(お客様番号 {account_no})への供給を{restored_at}に再開いたしました。

供給再開にあたって:
蛇口はゆっくり開け、水が澄むまで流してください。
水漏れやガスのにおいに気づいたら、建物の外に出て {support_phone} までお電話ください。

ご不明な点は {support_phone} までお電話ください。

{utility_name}
```

**`sms_service_disconnected` · SMS · ja-JP**

```text
{utility_name}:{cut_date}に供給を停止しました。再開には{total_to_restore}のお支払いが必要です。ご自身で再接続しないでください。医療上の緊急時は{support_phone}へ
```

**`sms_service_restored` · SMS · ja-JP**

```text
{utility_name}:供給を再開しました。蛇口はゆっくり開けてください。水漏れやガスのにおいがあれば{support_phone}へ
```

**`dunning` · Print (letter) · ja-JP**

```text
{customer_name} 様

お客様のアカウント {account} に {balance} の未払い残高がございますので、お知らせいたします。お支払いはオンラインでいつでも可能です。いつもご利用いただき、ありがとうございます。
```

### To translate (English only today)

| ✓ | Template code | Channel | From |
|---|---|---|---|
| [ ] | `service_work_order_logged` | Email | `DEF-WRK-10652` (d8c381b30) — new |
| [ ] | `sms_work_order_logged` | SMS | `DEF-WRK-10652` (d8c381b30) — new |
| [ ] | `service_appointment` | Email | `DEF-WRK-10652` (d8c381b30) — *Before we arrive* paragraph added |
| [ ] | `service_visit_moved` | Email | `DEF-WRK-10652` (d8c381b30) — *Before we arrive* paragraph added |
| [ ] | `sms_visit_booked` | SMS | `DEF-WRK-10652` (d8c381b30) — preparation paragraph added |
| [ ] | `visit preparation default (`work_settings.visit_prep_default`)` | Fills `{prep_instructions}` | `DEF-WRK-10652` (d8c381b30) — new |

## Korean — `ko-KR`

### To review (written today, in this language)

| ✓ | Template code | Channel | From | Subject |
|---|---|---|---|---|
| [ ] | `service_disconnected_guide` | Email | `DEF-NOT-10649` (a7c51cb35, `service_state_wording.py`) | {service_address}의 {utility_name} 공급이 중단되었습니다 |
| [ ] | `service_restored` | Email | `DEF-NOT-10649` (a7c51cb35, `service_state_wording.py`) | {service_address}의 {utility_name} 공급이 재개되었습니다 |
| [ ] | `sms_service_disconnected` | SMS | `DEF-NOT-10649` (a7c51cb35, `service_state_wording.py`) | *(no subject)* |
| [ ] | `sms_service_restored` | SMS | `DEF-NOT-10649` (a7c51cb35, `service_state_wording.py`) | *(no subject)* |
| [ ] | `dunning` | Print (letter) | `DEF-PAY-10651` (e724ff03d, `past_due_letter_wording.py`) | *(no subject)* |

**`service_disconnected_guide` · Email · ko-KR**

Subject: {service_address}의 {utility_name} 공급이 중단되었습니다

```text
{customer_name} 님, 안녕하세요.

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

{utility_name}
```

**`service_restored` · Email · ko-KR**

Subject: {service_address}의 {utility_name} 공급이 재개되었습니다

```text
{customer_name} 님, 안녕하세요.

{service_address}(고객번호 {account_no})의 공급이 {restored_at}에 재개되었습니다.

공급이 다시 시작되면:
수도꼭지를 천천히 열고 물이 맑아질 때까지 흘려 보내세요.
누수가 보이거나 가스 냄새가 나면 집 밖으로 나간 뒤 {support_phone}(으)로 전화해 주세요.

궁금한 점은 {support_phone}(으)로 전화해 주세요.

{utility_name}
```

**`sms_service_disconnected` · SMS · ko-KR**

```text
{utility_name}: {cut_date}에 공급이 중단되었습니다. 재개하려면 {total_to_restore}을(를) 납부하세요. 직접 연결하지 마세요. 의료 긴급 시 {support_phone}
```

**`sms_service_restored` · SMS · ko-KR**

```text
{utility_name}: 공급이 재개되었습니다. 수도꼭지를 천천히 여세요. 누수나 가스 냄새가 나면 {support_phone}(으)로 전화하세요.
```

**`dunning` · Print (letter) · ko-KR**

```text
{customer_name} 고객님, 고객님의 계정 {account}에 {balance}의 미납 잔액이 있어 안내드립니다. 온라인으로 언제든지 납부하실 수 있습니다. 항상 이용해 주셔서 감사합니다.
```

### To translate (English only today)

| ✓ | Template code | Channel | From |
|---|---|---|---|
| [ ] | `service_work_order_logged` | Email | `DEF-WRK-10652` (d8c381b30) — new |
| [ ] | `sms_work_order_logged` | SMS | `DEF-WRK-10652` (d8c381b30) — new |
| [ ] | `service_appointment` | Email | `DEF-WRK-10652` (d8c381b30) — *Before we arrive* paragraph added |
| [ ] | `service_visit_moved` | Email | `DEF-WRK-10652` (d8c381b30) — *Before we arrive* paragraph added |
| [ ] | `sms_visit_booked` | SMS | `DEF-WRK-10652` (d8c381b30) — preparation paragraph added |
| [ ] | `visit preparation default (`work_settings.visit_prep_default`)` | Fills `{prep_instructions}` | `DEF-WRK-10652` (d8c381b30) — new |

## Portuguese (Brazil) — `pt-BR`

### To review (written today, in this language)

| ✓ | Template code | Channel | From | Subject |
|---|---|---|---|---|
| [ ] | `service_disconnected_guide` | Email | `DEF-NOT-10649` (a7c51cb35, `service_state_wording.py`) | Seu serviço da {utility_name} em {service_address} foi desligado |
| [ ] | `service_restored` | Email | `DEF-NOT-10649` (a7c51cb35, `service_state_wording.py`) | Seu serviço da {utility_name} em {service_address} foi religado |
| [ ] | `sms_service_disconnected` | SMS | `DEF-NOT-10649` (a7c51cb35, `service_state_wording.py`) | *(no subject)* |
| [ ] | `sms_service_restored` | SMS | `DEF-NOT-10649` (a7c51cb35, `service_state_wording.py`) | *(no subject)* |
| [ ] | `dunning` | Print (letter) | `DEF-PAY-10651` (e724ff03d, `past_due_letter_wording.py`) | *(no subject)* |

**`service_disconnected_guide` · Email · pt-BR**

Subject: Seu serviço da {utility_name} em {service_address} foi desligado

```text
Olá, {first_name},

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

{utility_name}
```

**`service_restored` · Email · pt-BR**

Subject: Seu serviço da {utility_name} em {service_address} foi religado

```text
Olá, {first_name},

Seu serviço em {service_address} (conta {account_no}) foi religado em {restored_at}.

Agora que o serviço voltou:
Abra as torneiras devagar e deixe a água correr até ficar limpa.
Se notar um vazamento ou cheiro de gás, saia do imóvel e ligue para {support_phone}.

Dúvidas? Ligue para {support_phone}.

{utility_name}
```

**`sms_service_disconnected` · SMS · pt-BR**

```text
{utility_name}: serviço desligado em {cut_date}. Pague {total_to_restore} para religar. Não religue por conta própria. Urgência médica? {support_phone}
```

**`sms_service_restored` · SMS · pt-BR**

```text
{utility_name}: seu serviço foi religado. Abra as torneiras devagar. Vazamento ou cheiro de gás? Ligue para {support_phone}.
```

**`dunning` · Print (letter) · pt-BR**

```text
Olá, {first_name}! Este é um lembrete de que a sua conta {account} tem um saldo em aberto de {balance}. Você pode pagar on-line a qualquer momento. Obrigado por ser nosso cliente.
```

### To translate (English only today)

| ✓ | Template code | Channel | From |
|---|---|---|---|
| [ ] | `service_work_order_logged` | Email | `DEF-WRK-10652` (d8c381b30) — new |
| [ ] | `sms_work_order_logged` | SMS | `DEF-WRK-10652` (d8c381b30) — new |
| [ ] | `service_appointment` | Email | `DEF-WRK-10652` (d8c381b30) — *Before we arrive* paragraph added |
| [ ] | `service_visit_moved` | Email | `DEF-WRK-10652` (d8c381b30) — *Before we arrive* paragraph added |
| [ ] | `sms_visit_booked` | SMS | `DEF-WRK-10652` (d8c381b30) — preparation paragraph added |
| [ ] | `visit preparation default (`work_settings.visit_prep_default`)` | Fills `{prep_instructions}` | `DEF-WRK-10652` (d8c381b30) — new |

## The English source of the six untranslated texts

**`service_work_order_logged` · Email** — `DEF-WRK-10652` (d8c381b30) — new

Subject: Work order {order_no} logged — {utility_name}

```text
Hi {first_name},

We have logged work at {service_address}.

Work order {order_no}
What we are doing {work_type}

We will confirm a date with you.

Before we arrive: {prep_instructions}

Questions? Call {support_phone}.

{utility_name}
```

**`sms_work_order_logged` · SMS** — `DEF-WRK-10652` (d8c381b30) — new

```text
{utility_name}: work order {order_no} ({work_type}) at {service_address} is logged. We will confirm a date. Call {support_phone}.

{prep_instructions}
```

**`service_appointment` · Email** — `DEF-WRK-10652` (d8c381b30) — *Before we arrive* paragraph added

Subject: Your {utility_name} appointment on {appointment_date}

```text
Hi {first_name},

We have booked a visit to {service_address}.

What we are doing {work_type}
Date {appointment_date}
Arrival window {appointment_window}

Before we arrive: {prep_instructions}

If that time does not work for you, call {support_phone} and we will move it.

{utility_name}
```

**`service_visit_moved` · Email** — `DEF-WRK-10652` (d8c381b30) — *Before we arrive* paragraph added

Subject: Your {utility_name} visit has moved to {appointment_date}

```text
Hi {first_name},

Your visit to {service_address} has a new time.

What we are doing {work_type}
Date {appointment_date}
Arrival window {appointment_window}

Before we arrive: {prep_instructions}

If the new time does not work for you, call {support_phone} and we will move it.

{utility_name}
```

**`sms_visit_booked` · SMS** — `DEF-WRK-10652` (d8c381b30) — preparation paragraph added

```text
{utility_name}: your visit is booked for {appointment_date}, {appointment_window}. To change it call {support_phone}.

{prep_instructions}
```

**`visit preparation default (`work_settings.visit_prep_default`)` · Fills `{prep_instructions}`** — `DEF-WRK-10652` (d8c381b30) — new

```text
Please give our technician clear access to the meter: unlock gates and keep pets inside.
```

## English source of the reviewed texts

**`service_disconnected_guide` · Email · en**

Subject: Your {utility_name} service at {service_address} has been disconnected

```text
Hi {first_name},

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

{utility_name}
```

**`service_restored` · Email · en**

Subject: Your {utility_name} service at {service_address} is back on

```text
Hi {first_name},

Your service at {service_address} (account {account_no}) was restored on {restored_at}.

As your service comes back on:
Open taps slowly and let the water run until it is clear.
If you see a leak or smell gas, leave the property and call {support_phone}.

Questions? Call {support_phone}.

{utility_name}
```

**`sms_service_disconnected` · SMS · en**

```text
{utility_name}: service cut {cut_date}. Pay {total_to_restore} to restore. Do not reconnect it yourself. Medical need? Call {support_phone}.
```

**`sms_service_restored` · SMS · en**

```text
{utility_name}: your service is back on. Open taps slowly. Leak or smell of gas? Call {support_phone}.
```

**`dunning` · Print (letter) · en**

```text
Hi {first_name}, this is a friendly reminder that your account {account} has a balance of {balance}. You can pay online at any time. Thanks for being a customer.
```

---

# Added 2026-10-30 — the returned-payment email and letter, and the Print receipt labels

**Same rule as above (PO B5 A).** Written by lane PAY-G for `DEF-PAY-10744` (audit L2-04 — the
returned-payment / NSF email said *"Nothing has changed on your account"*; the printed letter was
blank) and `DEF-PAY-10743` (Q3 = A — Print receipt). Source files:
`06-backend/apps/notifications/payment_returned_wording.py` and the `payments.printReceipt.*` keys of
`07-frontend/src/i18n/locales/*.json`. No native speaker has read any of them.

⚠ **The four lines that hold `{confirmation}`, `{bank_memo}`, `{nsf_fee}` and `{due_date}` must each stay a
paragraph of its own** — the product leaves out a paragraph whose value is missing (no Bank memo, no fee),
so merging one into its neighbour would drop the neighbour too.

## German — `de` (2026-10-30)

| ✓ | Text | Channel | From |
|---|---|---|---|
| [ ] | `email_payment_failed` | Email | `DEF-PAY-10744` |
| [ ] | `payment_failed_letter` | Print (letter) | `DEF-PAY-10744` |
| [ ] | `payments.printReceipt.*` (20 labels) | Screen | `DEF-PAY-10743` |

**`email_payment_failed` · Email · de**

Subject: Ihre Zahlung über {amount} an {utility_name} wurde zurückgegeben

```text
Guten Tag {customer_name},

Ihre Bank hat Ihre Zahlung über {amount} vom {date} zurückgegeben. Der Betrag wurde deshalb wieder von Ihrem Kundenkonto ausgebucht.

Scheck- oder Referenznummer {confirmation}

Vermerk der Bank {bank_memo}

Rücklastschriftgebühr {nsf_fee}

Ihr offener Betrag beträgt jetzt {balance}.

Bitte begleichen Sie ihn bis zum {due_date}.

Sie können unter {utility_website} bezahlen oder uns unter {support_phone} anrufen, wenn Sie anders bezahlen möchten.

Mit freundlichen Grüßen
{utility_name}
```

**`payment_failed_letter` · Print (letter) · de**

```text
Guten Tag {customer_name},

Kundenkonto {account_no}

Ihre Bank hat Ihre Zahlung über {amount} vom {date} zurückgegeben. Der Betrag wurde deshalb wieder von Ihrem Kundenkonto ausgebucht.

Scheck- oder Referenznummer {confirmation}

Vermerk der Bank {bank_memo}

Rücklastschriftgebühr {nsf_fee}

Ihr offener Betrag beträgt jetzt {balance}.

Bitte begleichen Sie ihn bis zum {due_date}.

Sie können unter {utility_website} bezahlen oder uns unter {support_phone} anrufen, wenn Sie anders bezahlen möchten.

Mit freundlichen Grüßen
{utility_name}
```

**`payments.printReceipt.*` · Screen · de**

| Key | English | This language |
|---|---|---|
| `payments.printReceipt.action` | Print receipt | Beleg drucken |
| `payments.printReceipt.title` | Payment receipt | Zahlungsbeleg |
| `payments.printReceipt.number` | Receipt no. | Belegnummer |
| `payments.printReceipt.date` | Date | Datum |
| `payments.printReceipt.account` | Account | Kundenkonto |
| `payments.printReceipt.customer` | Received from | Erhalten von |
| `payments.printReceipt.amount` | Amount paid | Gezahlter Betrag |
| `payments.printReceipt.method` | Paid by | Zahlungsart |
| `payments.printReceipt.reference` | Reference | Referenz |
| `payments.printReceipt.bills` | Bills paid | Bezahlte Rechnungen |
| `payments.printReceipt.noBill` | Held as credit | Als Guthaben verbucht |
| `payments.printReceipt.balance` | Balance remaining | Offener Betrag |
| `payments.printReceipt.takenBy` | Served by | Bedient von |
| `payments.printReceipt.counter` | Counter | Kasse |
| `payments.printReceipt.notRecorded` | Not recorded | Nicht erfasst |
| `payments.printReceipt.print` | Print | Drucken |
| `payments.printReceipt.loading` | Preparing the receipt. | Beleg wird vorbereitet. |
| `payments.printReceipt.failed` | The receipt did not load. | Der Beleg konnte nicht laden. |
| `payments.printReceipt.blocked` | Allow pop-ups, then try again. | Pop-ups erlauben, dann erneut versuchen. |
| `payments.printReceipt.thanks` | Thank you. | Vielen Dank. |

## Spanish (Spain) — `es` (2026-10-30)

| ✓ | Text | Channel | From |
|---|---|---|---|
| [ ] | `email_payment_failed` | Email | `DEF-PAY-10744` |
| [ ] | `payment_failed_letter` | Print (letter) | `DEF-PAY-10744` |
| [ ] | `payments.printReceipt.*` (20 labels) | Screen | `DEF-PAY-10743` |

**`email_payment_failed` · Email · es**

Subject: Tu banco devolvió tu pago de {amount} a {utility_name}

```text
Hola, {first_name}:

Tu banco devolvió el pago de {amount} que hiciste el {date}, así que lo hemos retirado de tu cuenta.

Cheque o referencia {confirmation}

Nota del banco {bank_memo}

Cargo por pago devuelto {nsf_fee}

Tu saldo actual es de {balance}.

Por favor, págalo antes del {due_date}.

Puedes pagar en {utility_website} o llamarnos al {support_phone} para pagar de otra forma.

{utility_name}
```

**`payment_failed_letter` · Print (letter) · es**

```text
Estimado/a {customer_name}:

Cuenta {account_no}

Tu banco devolvió el pago de {amount} que hiciste el {date}, así que lo hemos retirado de tu cuenta.

Cheque o referencia {confirmation}

Nota del banco {bank_memo}

Cargo por pago devuelto {nsf_fee}

Tu saldo actual es de {balance}.

Por favor, págalo antes del {due_date}.

Puedes pagar en {utility_website} o llamarnos al {support_phone} para pagar de otra forma.

{utility_name}
```

**`payments.printReceipt.*` · Screen · es**

| Key | English | This language |
|---|---|---|
| `payments.printReceipt.action` | Print receipt | Imprimir recibo |
| `payments.printReceipt.title` | Payment receipt | Recibo de pago |
| `payments.printReceipt.number` | Receipt no. | N.º de recibo |
| `payments.printReceipt.date` | Date | Fecha |
| `payments.printReceipt.account` | Account | Cuenta |
| `payments.printReceipt.customer` | Received from | Recibido de |
| `payments.printReceipt.amount` | Amount paid | Importe pagado |
| `payments.printReceipt.method` | Paid by | Forma de pago |
| `payments.printReceipt.reference` | Reference | Referencia |
| `payments.printReceipt.bills` | Bills paid | Facturas pagadas |
| `payments.printReceipt.noBill` | Held as credit | Queda como saldo a favor |
| `payments.printReceipt.balance` | Balance remaining | Saldo pendiente |
| `payments.printReceipt.takenBy` | Served by | Atendido por |
| `payments.printReceipt.counter` | Counter | Caja |
| `payments.printReceipt.notRecorded` | Not recorded | Sin registrar |
| `payments.printReceipt.print` | Print | Imprimir |
| `payments.printReceipt.loading` | Preparing the receipt. | Preparando el recibo. |
| `payments.printReceipt.failed` | The receipt did not load. | No se pudo cargar el recibo. |
| `payments.printReceipt.blocked` | Allow pop-ups, then try again. | Permite ventanas emergentes y reintenta. |
| `payments.printReceipt.thanks` | Thank you. | Gracias. |

## Spanish (Mexico) — `es-MX` (2026-10-30)

| ✓ | Text | Channel | From |
|---|---|---|---|
| [ ] | `email_payment_failed` | Email | `DEF-PAY-10744` |
| [ ] | `payment_failed_letter` | Print (letter) | `DEF-PAY-10744` |
| [ ] | `payments.printReceipt.*` (20 labels) | Screen | `DEF-PAY-10743` |

**`email_payment_failed` · Email · es-MX**

Subject: Tu banco rechazó tu pago de {amount} a {utility_name}

```text
Hola, {first_name}:

Tu banco nos regresó el pago de {amount} que hiciste el {date}, por lo que ya no aparece aplicado en tu cuenta.

Cheque o referencia {confirmation}

Nota del banco {bank_memo}

Comisión por pago rechazado {nsf_fee}

Tu saldo ahora es de {balance}.

Te pedimos pagarlo a más tardar el {due_date}.

Puedes pagar en {utility_website} o llamarnos al {support_phone} si prefieres pagar de otra manera.

{utility_name}
```

**`payment_failed_letter` · Print (letter) · es-MX**

```text
Estimado/a {customer_name}:

Cuenta {account_no}

Tu banco nos regresó el pago de {amount} que hiciste el {date}, por lo que ya no aparece aplicado en tu cuenta.

Cheque o referencia {confirmation}

Nota del banco {bank_memo}

Comisión por pago rechazado {nsf_fee}

Tu saldo ahora es de {balance}.

Te pedimos pagarlo a más tardar el {due_date}.

Puedes pagar en {utility_website} o llamarnos al {support_phone} si prefieres pagar de otra manera.

{utility_name}
```

**`payments.printReceipt.*` · Screen · es-MX**

| Key | English | This language |
|---|---|---|
| `payments.printReceipt.action` | Print receipt | Imprimir recibo |
| `payments.printReceipt.title` | Payment receipt | Recibo de pago |
| `payments.printReceipt.number` | Receipt no. | Núm. de recibo |
| `payments.printReceipt.date` | Date | Fecha |
| `payments.printReceipt.account` | Account | Cuenta |
| `payments.printReceipt.customer` | Received from | Recibido de |
| `payments.printReceipt.amount` | Amount paid | Monto pagado |
| `payments.printReceipt.method` | Paid by | Forma de pago |
| `payments.printReceipt.reference` | Reference | Referencia |
| `payments.printReceipt.bills` | Bills paid | Recibos pagados |
| `payments.printReceipt.noBill` | Held as credit | Queda como saldo a favor |
| `payments.printReceipt.balance` | Balance remaining | Saldo pendiente |
| `payments.printReceipt.takenBy` | Served by | Atendido por |
| `payments.printReceipt.counter` | Counter | Caja |
| `payments.printReceipt.notRecorded` | Not recorded | Sin registrar |
| `payments.printReceipt.print` | Print | Imprimir |
| `payments.printReceipt.loading` | Preparing the receipt. | Preparando el recibo. |
| `payments.printReceipt.failed` | The receipt did not load. | No se pudo cargar el recibo. |
| `payments.printReceipt.blocked` | Allow pop-ups, then try again. | Permite ventanas emergentes y vuelve a intentar. |
| `payments.printReceipt.thanks` | Thank you. | Gracias. |

## French — `fr-FR` (2026-10-30)

| ✓ | Text | Channel | From |
|---|---|---|---|
| [ ] | `email_payment_failed` | Email | `DEF-PAY-10744` |
| [ ] | `payment_failed_letter` | Print (letter) | `DEF-PAY-10744` |
| [ ] | `payments.printReceipt.*` (20 labels) | Screen | `DEF-PAY-10743` |

**`email_payment_failed` · Email · fr-FR**

Subject: Votre paiement de {amount} à {utility_name} a été rejeté par votre banque

```text
Bonjour {first_name},

Votre banque a rejeté votre paiement de {amount} du {date}. Il a donc été retiré de votre compte.

Chèque ou référence {confirmation}

Motif indiqué par la banque {bank_memo}

Frais de paiement rejeté {nsf_fee}

Votre solde est maintenant de {balance}.

Merci de le régler avant le {due_date}.

Vous pouvez payer sur {utility_website} ou nous appeler au {support_phone} pour payer autrement.

{utility_name}
```

**`payment_failed_letter` · Print (letter) · fr-FR**

```text
Bonjour {customer_name},

Compte {account_no}

Votre banque a rejeté votre paiement de {amount} du {date}. Il a donc été retiré de votre compte.

Chèque ou référence {confirmation}

Motif indiqué par la banque {bank_memo}

Frais de paiement rejeté {nsf_fee}

Votre solde est maintenant de {balance}.

Merci de le régler avant le {due_date}.

Vous pouvez payer sur {utility_website} ou nous appeler au {support_phone} pour payer autrement.

{utility_name}
```

**`payments.printReceipt.*` · Screen · fr-FR**

| Key | English | This language |
|---|---|---|
| `payments.printReceipt.action` | Print receipt | Imprimer le reçu |
| `payments.printReceipt.title` | Payment receipt | Reçu de paiement |
| `payments.printReceipt.number` | Receipt no. | N° de reçu |
| `payments.printReceipt.date` | Date | Date |
| `payments.printReceipt.account` | Account | Compte |
| `payments.printReceipt.customer` | Received from | Reçu de |
| `payments.printReceipt.amount` | Amount paid | Montant payé |
| `payments.printReceipt.method` | Paid by | Moyen de paiement |
| `payments.printReceipt.reference` | Reference | Référence |
| `payments.printReceipt.bills` | Bills paid | Factures réglées |
| `payments.printReceipt.noBill` | Held as credit | Conservé en avoir |
| `payments.printReceipt.balance` | Balance remaining | Solde restant |
| `payments.printReceipt.takenBy` | Served by | Servi par |
| `payments.printReceipt.counter` | Counter | Guichet |
| `payments.printReceipt.notRecorded` | Not recorded | Non enregistré |
| `payments.printReceipt.print` | Print | Imprimer |
| `payments.printReceipt.loading` | Preparing the receipt. | Préparation du reçu. |
| `payments.printReceipt.failed` | The receipt did not load. | Le reçu n'a pas pu se charger. |
| `payments.printReceipt.blocked` | Allow pop-ups, then try again. | Autorisez les fenêtres pop-up, puis réessayez. |
| `payments.printReceipt.thanks` | Thank you. | Merci. |

## Hindi — `hi` (2026-10-30)

| ✓ | Text | Channel | From |
|---|---|---|---|
| [ ] | `email_payment_failed` | Email | `DEF-PAY-10744` |
| [ ] | `payment_failed_letter` | Print (letter) | `DEF-PAY-10744` |
| [ ] | `payments.printReceipt.*` (20 labels) | Screen | `DEF-PAY-10743` |

**`email_payment_failed` · Email · hi**

Subject: {utility_name} को किया गया आपका {amount} का भुगतान बैंक ने लौटा दिया है

```text
नमस्ते {first_name},

{date} को किया गया आपका {amount} का भुगतान आपके बैंक ने लौटा दिया है, इसलिए इसे आपके खाते से हटा दिया गया है।

चेक या संदर्भ संख्या {confirmation}

बैंक की टिप्पणी {bank_memo}

लौटे भुगतान का शुल्क {nsf_fee}

अब आपकी बकाया राशि {balance} है।

कृपया {due_date} तक भुगतान करें।

आप {utility_website} पर भुगतान कर सकते हैं, या किसी और तरीके से भुगतान करने के लिए {support_phone} पर कॉल करें।

{utility_name}
```

**`payment_failed_letter` · Print (letter) · hi**

```text
प्रिय {customer_name},

खाता संख्या {account_no}

{date} को किया गया आपका {amount} का भुगतान आपके बैंक ने लौटा दिया है, इसलिए इसे आपके खाते से हटा दिया गया है।

चेक या संदर्भ संख्या {confirmation}

बैंक की टिप्पणी {bank_memo}

लौटे भुगतान का शुल्क {nsf_fee}

अब आपकी बकाया राशि {balance} है।

कृपया {due_date} तक भुगतान करें।

आप {utility_website} पर भुगतान कर सकते हैं, या किसी और तरीके से भुगतान करने के लिए {support_phone} पर कॉल करें।

{utility_name}
```

**`payments.printReceipt.*` · Screen · hi**

| Key | English | This language |
|---|---|---|
| `payments.printReceipt.action` | Print receipt | रसीद प्रिंट करें |
| `payments.printReceipt.title` | Payment receipt | भुगतान रसीद |
| `payments.printReceipt.number` | Receipt no. | रसीद संख्या |
| `payments.printReceipt.date` | Date | तारीख |
| `payments.printReceipt.account` | Account | खाता |
| `payments.printReceipt.customer` | Received from | भुगतानकर्ता |
| `payments.printReceipt.amount` | Amount paid | भुगतान राशि |
| `payments.printReceipt.method` | Paid by | भुगतान का तरीका |
| `payments.printReceipt.reference` | Reference | संदर्भ |
| `payments.printReceipt.bills` | Bills paid | भुगतान किए गए बिल |
| `payments.printReceipt.noBill` | Held as credit | जमा राशि के रूप में रखा गया |
| `payments.printReceipt.balance` | Balance remaining | शेष राशि |
| `payments.printReceipt.takenBy` | Served by | सेवा दी |
| `payments.printReceipt.counter` | Counter | काउंटर |
| `payments.printReceipt.notRecorded` | Not recorded | दर्ज नहीं |
| `payments.printReceipt.print` | Print | प्रिंट करें |
| `payments.printReceipt.loading` | Preparing the receipt. | रसीद तैयार हो रही है। |
| `payments.printReceipt.failed` | The receipt did not load. | रसीद लोड नहीं हुई। |
| `payments.printReceipt.blocked` | Allow pop-ups, then try again. | पॉप-अप की अनुमति दें, फिर दोबारा कोशिश करें। |
| `payments.printReceipt.thanks` | Thank you. | धन्यवाद। |

## Indonesian — `id-ID` (2026-10-30)

| ✓ | Text | Channel | From |
|---|---|---|---|
| [ ] | `email_payment_failed` | Email | `DEF-PAY-10744` |
| [ ] | `payment_failed_letter` | Print (letter) | `DEF-PAY-10744` |
| [ ] | `payments.printReceipt.*` (20 labels) | Screen | `DEF-PAY-10743` |

**`email_payment_failed` · Email · id-ID**

Subject: Pembayaran Anda sebesar {amount} ke {utility_name} dikembalikan oleh bank

```text
Halo {first_name},

Pembayaran Anda sebesar {amount} pada {date} dikembalikan oleh bank Anda, jadi pembayaran itu sudah dibatalkan dari akun Anda.

Nomor cek atau referensi {confirmation}

Catatan bank {bank_memo}

Biaya pembayaran yang dikembalikan {nsf_fee}

Saldo Anda sekarang {balance}.

Mohon dibayar paling lambat {due_date}.

Anda dapat membayar di {utility_website}, atau hubungi {support_phone} untuk membayar dengan cara lain.

{utility_name}
```

**`payment_failed_letter` · Print (letter) · id-ID**

```text
Yth. {customer_name},

Nomor akun {account_no}

Pembayaran Anda sebesar {amount} pada {date} dikembalikan oleh bank Anda, jadi pembayaran itu sudah dibatalkan dari akun Anda.

Nomor cek atau referensi {confirmation}

Catatan bank {bank_memo}

Biaya pembayaran yang dikembalikan {nsf_fee}

Saldo Anda sekarang {balance}.

Mohon dibayar paling lambat {due_date}.

Anda dapat membayar di {utility_website}, atau hubungi {support_phone} untuk membayar dengan cara lain.

{utility_name}
```

**`payments.printReceipt.*` · Screen · id-ID**

| Key | English | This language |
|---|---|---|
| `payments.printReceipt.action` | Print receipt | Cetak kuitansi |
| `payments.printReceipt.title` | Payment receipt | Kuitansi pembayaran |
| `payments.printReceipt.number` | Receipt no. | No. kuitansi |
| `payments.printReceipt.date` | Date | Tanggal |
| `payments.printReceipt.account` | Account | Akun |
| `payments.printReceipt.customer` | Received from | Diterima dari |
| `payments.printReceipt.amount` | Amount paid | Jumlah dibayar |
| `payments.printReceipt.method` | Paid by | Cara bayar |
| `payments.printReceipt.reference` | Reference | Referensi |
| `payments.printReceipt.bills` | Bills paid | Tagihan dibayar |
| `payments.printReceipt.noBill` | Held as credit | Disimpan sebagai saldo kredit |
| `payments.printReceipt.balance` | Balance remaining | Sisa tagihan |
| `payments.printReceipt.takenBy` | Served by | Dilayani oleh |
| `payments.printReceipt.counter` | Counter | Loket |
| `payments.printReceipt.notRecorded` | Not recorded | Tidak tercatat |
| `payments.printReceipt.print` | Print | Cetak |
| `payments.printReceipt.loading` | Preparing the receipt. | Kuitansi sedang disiapkan. |
| `payments.printReceipt.failed` | The receipt did not load. | Kuitansi gagal dimuat. |
| `payments.printReceipt.blocked` | Allow pop-ups, then try again. | Izinkan pop-up, lalu coba lagi. |
| `payments.printReceipt.thanks` | Thank you. | Terima kasih. |

## Italian — `it-IT` (2026-10-30)

| ✓ | Text | Channel | From |
|---|---|---|---|
| [ ] | `email_payment_failed` | Email | `DEF-PAY-10744` |
| [ ] | `payment_failed_letter` | Print (letter) | `DEF-PAY-10744` |
| [ ] | `payments.printReceipt.*` (20 labels) | Screen | `DEF-PAY-10743` |

**`email_payment_failed` · Email · it-IT**

Subject: Il suo pagamento di {amount} a {utility_name} è stato respinto dalla banca

```text
Gentile {customer_name},

la sua banca ha respinto il pagamento di {amount} del {date}, che è stato quindi stornato dal suo conto.

Assegno o riferimento {confirmation}

Nota della banca {bank_memo}

Commissione per pagamento respinto {nsf_fee}

Il suo saldo ora è di {balance}.

La preghiamo di saldarlo entro il {due_date}.

Può pagare su {utility_website} oppure chiamarci al {support_phone} per pagare in un altro modo.

Cordiali saluti
{utility_name}
```

**`payment_failed_letter` · Print (letter) · it-IT**

```text
Gentile {customer_name},

Conto {account_no}

La sua banca ha respinto il pagamento di {amount} del {date}, che è stato quindi stornato dal suo conto.

Assegno o riferimento {confirmation}

Nota della banca {bank_memo}

Commissione per pagamento respinto {nsf_fee}

Il suo saldo ora è di {balance}.

La preghiamo di saldarlo entro il {due_date}.

Può pagare su {utility_website} oppure chiamarci al {support_phone} per pagare in un altro modo.

Cordiali saluti
{utility_name}
```

**`payments.printReceipt.*` · Screen · it-IT**

| Key | English | This language |
|---|---|---|
| `payments.printReceipt.action` | Print receipt | Stampa ricevuta |
| `payments.printReceipt.title` | Payment receipt | Ricevuta di pagamento |
| `payments.printReceipt.number` | Receipt no. | N. ricevuta |
| `payments.printReceipt.date` | Date | Data |
| `payments.printReceipt.account` | Account | Conto |
| `payments.printReceipt.customer` | Received from | Ricevuto da |
| `payments.printReceipt.amount` | Amount paid | Importo pagato |
| `payments.printReceipt.method` | Paid by | Metodo di pagamento |
| `payments.printReceipt.reference` | Reference | Riferimento |
| `payments.printReceipt.bills` | Bills paid | Bollette pagate |
| `payments.printReceipt.noBill` | Held as credit | Tenuto come credito |
| `payments.printReceipt.balance` | Balance remaining | Saldo residuo |
| `payments.printReceipt.takenBy` | Served by | Servito da |
| `payments.printReceipt.counter` | Counter | Sportello |
| `payments.printReceipt.notRecorded` | Not recorded | Non registrato |
| `payments.printReceipt.print` | Print | Stampa |
| `payments.printReceipt.loading` | Preparing the receipt. | Preparazione della ricevuta. |
| `payments.printReceipt.failed` | The receipt did not load. | La ricevuta non si è caricata. |
| `payments.printReceipt.blocked` | Allow pop-ups, then try again. | Consenti i pop-up, poi riprova. |
| `payments.printReceipt.thanks` | Thank you. | Grazie. |

## Japanese — `ja-JP` (2026-10-30)

| ✓ | Text | Channel | From |
|---|---|---|---|
| [ ] | `email_payment_failed` | Email | `DEF-PAY-10744` |
| [ ] | `payment_failed_letter` | Print (letter) | `DEF-PAY-10744` |
| [ ] | `payments.printReceipt.*` (20 labels) | Screen | `DEF-PAY-10743` |

**`email_payment_failed` · Email · ja-JP**

Subject: {utility_name}へのお支払い（{amount}）が銀行から返却されました

```text
{customer_name} 様

{date}にお支払いいただいた{amount}が、お客様の銀行から返却されました。そのため、このお支払いはお客様のアカウントから取り消されています。

小切手番号・参照番号 {confirmation}

銀行からのメモ {bank_memo}

返却手数料 {nsf_fee}

現在のご請求残高は{balance}です。

{due_date}までにお支払いください。

{utility_website}からお支払いいただけます。別の方法をご希望の場合は{support_phone}までお電話ください。

{utility_name}
```

**`payment_failed_letter` · Print (letter) · ja-JP**

```text
{customer_name} 様

お客様番号 {account_no}

{date}にお支払いいただいた{amount}が、お客様の銀行から返却されました。そのため、このお支払いはお客様のアカウントから取り消されています。

小切手番号・参照番号 {confirmation}

銀行からのメモ {bank_memo}

返却手数料 {nsf_fee}

現在のご請求残高は{balance}です。

{due_date}までにお支払いください。

{utility_website}からお支払いいただけます。別の方法をご希望の場合は{support_phone}までお電話ください。

{utility_name}
```

**`payments.printReceipt.*` · Screen · ja-JP**

| Key | English | This language |
|---|---|---|
| `payments.printReceipt.action` | Print receipt | 領収書を印刷 |
| `payments.printReceipt.title` | Payment receipt | お支払い領収書 |
| `payments.printReceipt.number` | Receipt no. | 領収書番号 |
| `payments.printReceipt.date` | Date | 日付 |
| `payments.printReceipt.account` | Account | お客様番号 |
| `payments.printReceipt.customer` | Received from | お支払い者 |
| `payments.printReceipt.amount` | Amount paid | お支払い金額 |
| `payments.printReceipt.method` | Paid by | お支払い方法 |
| `payments.printReceipt.reference` | Reference | 参照番号 |
| `payments.printReceipt.bills` | Bills paid | お支払い済みの請求 |
| `payments.printReceipt.noBill` | Held as credit | 前受金として保管 |
| `payments.printReceipt.balance` | Balance remaining | 残りのご請求額 |
| `payments.printReceipt.takenBy` | Served by | 担当者 |
| `payments.printReceipt.counter` | Counter | 窓口 |
| `payments.printReceipt.notRecorded` | Not recorded | 記録なし |
| `payments.printReceipt.print` | Print | 印刷 |
| `payments.printReceipt.loading` | Preparing the receipt. | 領収書を準備しています。 |
| `payments.printReceipt.failed` | The receipt did not load. | 領収書を読み込めませんでした。 |
| `payments.printReceipt.blocked` | Allow pop-ups, then try again. | ポップアップを許可して、もう一度お試しください。 |
| `payments.printReceipt.thanks` | Thank you. | ありがとうございました。 |

## Korean — `ko-KR` (2026-10-30)

| ✓ | Text | Channel | From |
|---|---|---|---|
| [ ] | `email_payment_failed` | Email | `DEF-PAY-10744` |
| [ ] | `payment_failed_letter` | Print (letter) | `DEF-PAY-10744` |
| [ ] | `payments.printReceipt.*` (20 labels) | Screen | `DEF-PAY-10743` |

**`email_payment_failed` · Email · ko-KR**

Subject: {utility_name}에 납부하신 {amount}이(가) 은행에서 반환되었습니다

```text
{customer_name} 고객님,

{date}에 납부하신 {amount}이(가) 고객님의 은행에서 반환되어, 해당 납부가 계정에서 취소되었습니다.

수표 또는 참조 번호 {confirmation}

은행 메모 {bank_memo}

반환 수수료 {nsf_fee}

현재 잔액은 {balance}입니다.

{due_date}까지 납부해 주시기 바랍니다.

{utility_website}에서 납부하시거나, 다른 방법으로 납부하시려면 {support_phone}으로 전화해 주세요.

{utility_name}
```

**`payment_failed_letter` · Print (letter) · ko-KR**

```text
{customer_name} 고객님께

고객 번호 {account_no}

{date}에 납부하신 {amount}이(가) 고객님의 은행에서 반환되어, 해당 납부가 계정에서 취소되었습니다.

수표 또는 참조 번호 {confirmation}

은행 메모 {bank_memo}

반환 수수료 {nsf_fee}

현재 잔액은 {balance}입니다.

{due_date}까지 납부해 주시기 바랍니다.

{utility_website}에서 납부하시거나, 다른 방법으로 납부하시려면 {support_phone}으로 전화해 주세요.

{utility_name}
```

**`payments.printReceipt.*` · Screen · ko-KR**

| Key | English | This language |
|---|---|---|
| `payments.printReceipt.action` | Print receipt | 영수증 인쇄 |
| `payments.printReceipt.title` | Payment receipt | 납부 영수증 |
| `payments.printReceipt.number` | Receipt no. | 영수증 번호 |
| `payments.printReceipt.date` | Date | 날짜 |
| `payments.printReceipt.account` | Account | 고객 번호 |
| `payments.printReceipt.customer` | Received from | 납부자 |
| `payments.printReceipt.amount` | Amount paid | 납부 금액 |
| `payments.printReceipt.method` | Paid by | 납부 방법 |
| `payments.printReceipt.reference` | Reference | 참조 번호 |
| `payments.printReceipt.bills` | Bills paid | 납부한 청구서 |
| `payments.printReceipt.noBill` | Held as credit | 선납금으로 보관 |
| `payments.printReceipt.balance` | Balance remaining | 남은 잔액 |
| `payments.printReceipt.takenBy` | Served by | 담당자 |
| `payments.printReceipt.counter` | Counter | 창구 |
| `payments.printReceipt.notRecorded` | Not recorded | 기록 없음 |
| `payments.printReceipt.print` | Print | 인쇄 |
| `payments.printReceipt.loading` | Preparing the receipt. | 영수증을 준비하고 있습니다. |
| `payments.printReceipt.failed` | The receipt did not load. | 영수증을 불러오지 못했습니다. |
| `payments.printReceipt.blocked` | Allow pop-ups, then try again. | 팝업을 허용한 뒤 다시 시도하세요. |
| `payments.printReceipt.thanks` | Thank you. | 감사합니다. |

## Portuguese (Brazil) — `pt-BR` (2026-10-30)

| ✓ | Text | Channel | From |
|---|---|---|---|
| [ ] | `email_payment_failed` | Email | `DEF-PAY-10744` |
| [ ] | `payment_failed_letter` | Print (letter) | `DEF-PAY-10744` |
| [ ] | `payments.printReceipt.*` (20 labels) | Screen | `DEF-PAY-10743` |

**`email_payment_failed` · Email · pt-BR**

Subject: Seu pagamento de {amount} para {utility_name} foi devolvido pelo banco

```text
Olá, {first_name}!

Seu banco devolveu o pagamento de {amount} feito em {date}, por isso ele foi retirado da sua conta.

Cheque ou referência {confirmation}

Observação do banco {bank_memo}

Tarifa de pagamento devolvido {nsf_fee}

Seu saldo agora é de {balance}.

Por favor, pague até {due_date}.

Você pode pagar em {utility_website} ou ligar para {support_phone} para pagar de outra forma.

{utility_name}
```

**`payment_failed_letter` · Print (letter) · pt-BR**

```text
Prezado(a) {customer_name},

Conta {account_no}

Seu banco devolveu o pagamento de {amount} feito em {date}, por isso ele foi retirado da sua conta.

Cheque ou referência {confirmation}

Observação do banco {bank_memo}

Tarifa de pagamento devolvido {nsf_fee}

Seu saldo agora é de {balance}.

Por favor, pague até {due_date}.

Você pode pagar em {utility_website} ou ligar para {support_phone} para pagar de outra forma.

{utility_name}
```

**`payments.printReceipt.*` · Screen · pt-BR**

| Key | English | This language |
|---|---|---|
| `payments.printReceipt.action` | Print receipt | Imprimir recibo |
| `payments.printReceipt.title` | Payment receipt | Recibo de pagamento |
| `payments.printReceipt.number` | Receipt no. | Nº do recibo |
| `payments.printReceipt.date` | Date | Data |
| `payments.printReceipt.account` | Account | Conta |
| `payments.printReceipt.customer` | Received from | Recebido de |
| `payments.printReceipt.amount` | Amount paid | Valor pago |
| `payments.printReceipt.method` | Paid by | Forma de pagamento |
| `payments.printReceipt.reference` | Reference | Referência |
| `payments.printReceipt.bills` | Bills paid | Contas pagas |
| `payments.printReceipt.noBill` | Held as credit | Mantido como crédito |
| `payments.printReceipt.balance` | Balance remaining | Saldo restante |
| `payments.printReceipt.takenBy` | Served by | Atendido por |
| `payments.printReceipt.counter` | Counter | Caixa |
| `payments.printReceipt.notRecorded` | Not recorded | Não registrado |
| `payments.printReceipt.print` | Print | Imprimir |
| `payments.printReceipt.loading` | Preparing the receipt. | Preparando o recibo. |
| `payments.printReceipt.failed` | The receipt did not load. | O recibo não carregou. |
| `payments.printReceipt.blocked` | Allow pop-ups, then try again. | Permita pop-ups e tente de novo. |
| `payments.printReceipt.thanks` | Thank you. | Obrigado. |

## Screen strings added or changed 2026-10-30 by lane FINAL-WALK-2 (`DEF-BIL-10773`, `DEF-PAY-10774`)

Two on-screen sentences, written by an AI lane in every language below; no person has read them yet.

### German — `de`

| ✓ | Key | English | This language |
|---|---|---|---|
| [ ] | `billing.run.recheckLateFees` | Paid after drafting: {{count}}. Work those bills out again. | Nach dem Entwurf bezahlt: {{count}}. Berechnen Sie diese Rechnungen neu. |
| [ ] | `payments.duplicate.body` | Same amount, same day. The bill is paid. | Gleicher Betrag, gleicher Tag. Die Rechnung ist bezahlt. |

### Spanish (Spain) — `es`

| ✓ | Key | English | This language |
|---|---|---|---|
| [ ] | `billing.run.recheckLateFees` | Paid after drafting: {{count}}. Work those bills out again. | Pagadas tras el borrador: {{count}}. Vuelva a calcular esas facturas. |
| [ ] | `payments.duplicate.body` | Same amount, same day. The bill is paid. | Mismo importe, mismo día. La factura está pagada. |

### Spanish (Mexico) — `es-MX`

| ✓ | Key | English | This language |
|---|---|---|---|
| [ ] | `billing.run.recheckLateFees` | Paid after drafting: {{count}}. Work those bills out again. | Pagadas después del borrador: {{count}}. Vuelva a calcular esas facturas. |
| [ ] | `payments.duplicate.body` | Same amount, same day. The bill is paid. | Mismo monto, mismo día. La factura ya está pagada. |

### French — `fr-FR`

| ✓ | Key | English | This language |
|---|---|---|---|
| [ ] | `billing.run.recheckLateFees` | Paid after drafting: {{count}}. Work those bills out again. | Payé après le brouillon : {{count}}. Recalculez ces factures. |
| [ ] | `payments.duplicate.body` | Same amount, same day. The bill is paid. | Même montant, même jour. La facture est payée. |

### Hindi — `hi`

| ✓ | Key | English | This language |
|---|---|---|---|
| [ ] | `billing.run.recheckLateFees` | Paid after drafting: {{count}}. Work those bills out again. | मसौदे के बाद भुगतान: {{count}}। उन बिलों को फिर से बनाएँ। |
| [ ] | `payments.duplicate.body` | Same amount, same day. The bill is paid. | वही राशि, वही दिन। बिल चुका दिया गया है। |

### Indonesian — `id-ID`

| ✓ | Key | English | This language |
|---|---|---|---|
| [ ] | `billing.run.recheckLateFees` | Paid after drafting: {{count}}. Work those bills out again. | Dibayar setelah draf: {{count}}. Hitung ulang tagihan tersebut. |
| [ ] | `payments.duplicate.body` | Same amount, same day. The bill is paid. | Jumlah sama, hari sama. Tagihannya sudah lunas. |

### Italian — `it-IT`

| ✓ | Key | English | This language |
|---|---|---|---|
| [ ] | `billing.run.recheckLateFees` | Paid after drafting: {{count}}. Work those bills out again. | Pagate dopo la bozza: {{count}}. Ricalcola quelle bollette. |
| [ ] | `payments.duplicate.body` | Same amount, same day. The bill is paid. | Stesso importo, stesso giorno. La bolletta è pagata. |

### Japanese — `ja-JP`

| ✓ | Key | English | This language |
|---|---|---|---|
| [ ] | `billing.run.recheckLateFees` | Paid after drafting: {{count}}. Work those bills out again. | 下書き後の支払い: {{count}}件。請求書を計算し直してください。 |
| [ ] | `payments.duplicate.body` | Same amount, same day. The bill is paid. | 同じ金額、同じ日です。請求書は支払済みです。 |

### Korean — `ko-KR`

| ✓ | Key | English | This language |
|---|---|---|---|
| [ ] | `billing.run.recheckLateFees` | Paid after drafting: {{count}}. Work those bills out again. | 초안 작성 후 결제: {{count}}건. 해당 청구서를 다시 계산하세요. |
| [ ] | `payments.duplicate.body` | Same amount, same day. The bill is paid. | 같은 금액, 같은 날입니다. 청구서는 이미 납부되었습니다. |

### Portuguese (Brazil) — `pt-BR`

| ✓ | Key | English | This language |
|---|---|---|---|
| [ ] | `billing.run.recheckLateFees` | Paid after drafting: {{count}}. Work those bills out again. | Pagas após o rascunho: {{count}}. Recalcule essas faturas. |
| [ ] | `payments.duplicate.body` | Same amount, same day. The bill is paid. | Mesmo valor, mesmo dia. A fatura já está paga. |
