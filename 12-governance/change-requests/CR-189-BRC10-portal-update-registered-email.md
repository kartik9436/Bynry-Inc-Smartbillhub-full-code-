# CR-189-BRC10 · Customer portal: self-service "update your registered email" when locked out

**Raised:** 2026-10-22 by the Product Owner, in chat, while fixing the portal forgot-password defect.

**Requester's words (verbatim):** *"We have to send reset email to registered user only if email address is not registered then we need to show the message that submit the request to change or update register email address, How will you handle update register email address using self service customer portal"*, then *"B: keep the same message for everyone, but always include the link …"* and *"this is correct"*.

**Ruling:** decision log 2026-10-22, *"PORTAL FORGOT-PASSWORD: ONE MESSAGE FOR EVERY ADDRESS, PLUS A SELF-SERVICE 'UPDATE YOUR REGISTERED EMAIL' PATH"*. BR-CWP-038 stands.

## What gets built
1. **The link.** "Not getting the email? Update your registered email" on the forgot-password page and its check-your-inbox panel. Rides the PORTAL-RESET fix.
2. **The update-email flow.** Account check (account number, service ZIP, last name), then a code to the phone or email on file, then the new email, then a confirmation code to the new email. The registered email is updated, the old email is notified, and a reset link is sent.
3. **The dead end.** When nothing on file is reachable: *"We can't verify you online. Call the office"*, with the utility's phone number (and hours) from Settings. No guest service request. PO 2026-10-22: *"call the office"*.
4. **Limits and records.** The guest lookup lock (5 tries, 15 minutes); audit rows; instant account-access emails from Settings templates in 11 languages; no hardcoding.

## Status
OPEN: item 1 in build with the PORTAL-RESET fix; items 2–4 to be built after it merges.
