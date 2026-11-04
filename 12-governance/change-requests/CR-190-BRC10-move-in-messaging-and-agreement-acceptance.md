# CR-190-BRC10 · Every email sent correctly; move-in welcome details; agreement by email with click-to-accept

**Raised:** 2026-10-22 by the Product Owner, as a pasted defect report on Move-in Step 4 messaging and the welcome email, plus answers in chat.

**Rulings:** decision log 2026-10-22, *"MOVE-IN MESSAGING AND THE WELCOME EMAIL: FOUR ANSWERS…"* and *"CLICK-TO-ACCEPT AGREEMENTS: THE DESIGN CONFIRMED WITH FOUR ANSWERS"*.

## Parts

| Lane | Part |
|---|---|
| EMAIL-CORE (defect) | The provider hand-off sends the template's rendered SUBJECT and BODY, never the internal dict. The subject goes in the email header. Every email is multipart: escaped HTML paragraphs plus a plain-text part. Covers every adapter (SMTP, SendGrid, Postmark, Google, Microsoft, OAuth mailbox). |
| MOVEIN-MSG | One shared customer render-context builder (first name, customer name, account number, service address), used by the move-in welcome email. Activation date plus first bill date from the account's billing cycle, with no due date and nothing hardcoded. *Create from our default* for contract templates (fills the editor with the platform wording; BR-NOT-002 stands). Step 4: the clerk may untick a default or change its channel for one move-in. |
| AGREEMENT | Service agreement by email with the PDF attached (plus a letter if the customer wants paper). A reusable click-to-accept component: an agreement request, a single-use link with validity as a setting (seeded 7 days), a public acceptance page (tick, today's date, typed name), a stamped PDF copy stored on the account, Sent/Accepted/Expired status, Resend, audit. No in-portal acceptance. |

## Status
IN BUILD (2026-10-22).
