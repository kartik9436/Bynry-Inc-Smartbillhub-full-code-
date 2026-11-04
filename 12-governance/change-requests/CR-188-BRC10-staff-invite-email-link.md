# CR-188-BRC10 · Staff invitation and reset emails carry a one-time sign-in link

**Raised:** 2026-10-22 by the Product Owner, as a pasted defect report plus six answers in chat.

**Requester's words (verbatim):**
- *"we will keep exsisting functionality as it is like reset password , user creation and shared password manually. we aill also develop the email automation for user invitation."*
- Answers: 1 *"B: email a one-time sign-in link instead, no password."* · 3 *"A"* · 4 *"B: email it as well."* · 5 *"A"* · 6 *"A"* · *"Start"*.

**Ruling:** decision log 2026-10-22, *"STAFF INVITATION EMAIL: A ONE-TIME SIGN-IN LINK, NOT A PASSWORD; SIX ANSWERS"*.

## Before → after

| Before | After |
|---|---|
| Create user / Reset temp password: an on-screen temporary password only; no email (BR-IDN-021) | Same on-screen password, **plus** an email with a **one-time sign-in link** (single-use, expiring, voided by a newer link or by use). The link opens a *set your password* page. |
| No staff invitation template | `staff_user_invite` (invitation) and a reset counterpart, in a new **Account access** category in Settings → Templates, editable, seeded for new and existing utilities |
| No product public address | One server setting for the public web address, used to build the link |
| No resend | **Resend invitation** on the user row: a new link (voiding the old one) and a new on-screen temporary password |
| No email provider: nothing said | The admin sees *"Invitation not emailed — no email provider is connected"*; the user is still created and the on-screen password is shown |

## Status
IN BUILD (2026-10-22).
