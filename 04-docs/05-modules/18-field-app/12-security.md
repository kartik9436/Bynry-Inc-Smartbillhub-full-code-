# 18 · Field app — security

**Source:** the design canvas's *Security* page (version `2.587.0`), in full, with `AD-21` and `AD-24` and rules
`R113`–`R115`, `R127` from the decision log of 2026-10-21. The design's opening line: *"A handset carrying a day of a
utility's customer data, used by several people, left in a van, offline for eight hours at a time. Most of what
follows exists because of that last clause."* The decision log of 2026-10-21 also puts an addendum for this page into
`04-docs/02-decisions/03-tenancy-and-security.md` — that addendum is another lane's.

Where the server already does part of a rule, or the design's sentence has since been superseded, the note says so
in place. Nothing here is a new ruling.

---

## 1 · The one that decides whether the app works at all

**A token that expires mid-shift must never stop a technician working** (`AD-21`, `R113`).

Dana signs in at 07:30 on depot wi-fi and drives into a valley. Her access token expires at 08:30. She has nine hours
of work left and no signal. An app that treats expiry as *"you are signed out"* loses the day. One that extends the
token to cover the shift has a credential sitting on a handset for twelve hours. Neither is acceptable, so **there are
two credentials doing two different jobs.**

| | |
|---|---|
| **Access token** | Short-lived, **one hour**, refreshed whenever there is a signal. It authorises talking to the server and nothing else. Expiring is normal and uneventful |
| **Capture credential** | Device-bound, **36 hours**, renewed on every successful contact. It authorises writing to the local store and signs each captured item. It never reaches the server as an authorisation — the server checks the signature against the device registration |
| **So expiry blocks** | Sending, which is already asynchronous. **Not capture.** The outbox fills exactly as it would have; it goes up after the next sign-in |
| **If both expire** | A handset off for days still keeps every unsent item. It asks for a password before anything more is captured, and the queue is untouched |
| **Never** | A silent sign-out that discards work. **There is no state in which captured work is thrown away to resolve an auth problem** |

**Server today, measured 2026-10-21:** sign-in is a **session cookie** (`POST /api/{tenant}/auth/session`), not a
token pair, and there is no refresh route. The capture credential exists in part: `POST work/mobile/capture-token`
issues a signed token carrying tenant, user, technician and device label, which *"outlives sign-out on purpose"*
(`BR-WRK-060`) and is checked item by item in the sync. **But it lives 7 days** (`apps/work/mobile.py:660`,
`CAPTURE_TOKEN_MAX_AGE_S = 7 * 24 * 3600`), not 36 hours, and it is signed with the server's key rather than checked
against a device registration. **The design's split needs a server endpoint that does not exist yet** (§7 item 1;
`07-endpoints.md` N24). Which life the capture credential has — 36 hours or 7 days — is a difference between a design
figure and built code, recorded here and not decided.

---

## 2 · The data at rest

| What | Protection | Why that, and not more |
|---|---|---|
| The SQLite database | **SQLCipher** | Page-level AES, key in the platform keystore, released on device unlock. A pulled flash chip reads as noise |
| Photo files | Encrypted | They carry a customer's property, position and time. Same keystore key; deleted on confirmed receipt anyway, which is the better protection |
| Documents and SOPs | App container | Not customer data. Platform sandboxing is proportionate |
| MMKV preferences | Encrypted | Cheap, and it holds the active technician |
| The capture credential | Keystore / Secure Enclave | Hardware-backed, non-exportable. **It never touches the database** |
| Map tiles | Plain | Public geography. Encrypting it buys nothing and costs battery |

*Note:* the scaffold carries `expo-sqlite` and `expo-secure-store`; SQLCipher is not yet installed (`11-technology.md`
§1).

---

## 3 · Several people, one handset

| | |
|---|---|
| **Tenant scoping** | ⚠ **The design's Security page reads: *"Every table carries tenant_id and every query names it — the local equivalent of the server's forced row-level security. A handset only ever holds one tenant, and the check exists so that stays true rather than being assumed."* That sentence is SUPERSEDED by `AD-24` / `R131`** — *"Supersedes a sentence of mine that said 'every local table carries tenant_id'. No table in the inventory carried it — it was a claim, not a design."* **The rule is: the tenant is the database FILE** (`field-<tenant>.sqlite`, chosen at sign-in; a contractor for two utilities gets two files), **no local table carries `tenant_id`**, and a cross-tenant read is impossible rather than unlikely (`03-field-map.md` §2.7). The intent the old sentence carried — that one-tenant-per-store is checked rather than assumed — survives as T-50 |
| **Between technicians** | Mirror data is scoped to the signed-in technician. Captured work is not deleted and not shown — **Marco cannot see Dana's 62 unsent items, and they still send under her name** (`R132`, `R133`; `BR-WRK-060`, PO 2026-10-04: *"Chen can't see or change it"*) |
| **Signed by whom** | **`captured_by` is written at capture from the capture credential, never read from the current session.** That one line is what makes a shared handset honest. (The server already reads the captor from each item's token, not from whoever is signed in — `sync.py`, `BR-WRK-059`) |
| **Biometric unlock** | Offered for returning to your own session. **Switching technician always takes a password** — a thumb on a shared tablet is not an identity claim |
| **Auto-lock** | Five minutes idle, and five minutes away. Sharper now that a stop shows the customer's name (`R79`). ⚠ **AMENDED 2026-10-26 (`MQ-019`, decision log; PO: *"A. Lock only after 5 minutes away"*; `DEF-FLD-10614`) — it read *"Five minutes idle, and immediately on backgrounding"* until then.** Leaving the app (Maps for Navigate, the phone for Call, the home screen) locks it only if the technician is away five minutes or more; a cold start still opens locked. **A "background" report caused by the app's OWN system pop-up never counts as leaving** — a permission dialog (camera, location, notifications, microphone), a settings screen the app opened, the fingerprint prompt, the file picker — because Android reports its own permission dialog as backgrounding and answering it locked the app mid-job. Trade-off accepted by the PO: a phone stolen while the app is backgrounded stays unlocked up to five minutes, the limit already accepted for idle. Built: `field-app/src/session/sessionManager.ts` (`onBackground` / `onForeground`, one constant), `field-app/src/session/systemInteraction.ts` |
| **Screenshots** | Blocked on screens showing a name, an account or a balance; allowed everywhere else, because technicians legitimately photograph their own screen to show a supervisor |

---

## 4 · The device itself

| | |
|---|---|
| **Registration** | Named at activation (*Van 14 tablet*) and bound to the capture credential. The office sees every device a technician uses. (Server: `technician_devices` — tenant, technician, token, platform, label, active, registered and last-seen; activation itself is NEW, `R105`) |
| **Remote sign-out** | From the back office. Mirror tables are dropped on next contact. **The outbox and its photo files are not — they send, then go.** A remote wipe that discards unsent work is a remote wipe that loses a day (`R115`) |
| **A lost handset exposes** | At most one day's jobs for one tenant, behind the device passcode and an encrypted store. No card details, no payment instrument, no customer portal credentials — **the app reads money and never takes it, which is a security property as much as a product one** (`R16`) |
| **Rooted or jailbroken** | Detected and reported in telemetry. **Warned, not blocked** — consistent with everything else, and a false positive that strands a technician costs more than the risk |
| **Transport** | TLS 1.3, **certificate pinning with two pins and a documented rotation**, because a pinned app with one expired pin is a fleet that cannot sync. **BUILT 2026-10-24 (`OQ-FLD-12797`, PO: *"dont hardcode it use settings - security values set in staff portal"*):** the keys live on the staff portal's Settings › Security, *Field app certificates* (per utility; a utility that never edits it is served the platform default, `SBH_FIELD_APP_DEFAULT_PINS`); the build starts from `extra.pins` in its config; the phone adopts the server's list only over an already-pinned connection (`field-app/src/security/pinning.ts`). Rotation: §7 item 2. ⚠ **BETA EXCEPTION, 2026-10-26 (`DEF-FLD-10617`; decision log 2026-10-26 *"Certificate pinning is OFF in the beta (preview) build, ON for go-live"*, PO: *"B. Switch the check off for the beta"*).** 2.603.0 refused the live server's certificate — the starting pins named ISRG/GTS and the real issuer had never been confirmed — and every failure read *"No signal"*. So the build carries a switch, `FIELD_APP_PINNING` (`on` \| `off`, **default ON**; `app.config.ts` → `extra.pinning`): the **EAS `preview` profile (the beta APK) sets `off`**, the phone then never starts pinning and never adopts a server list, and Settings › About says *Beta build — certificate check off*; **`production` stays ON**, and a production build with `off` is refused by `app.config.ts` and by `field-app/tests/release/pinningSwitch.test.ts`. **Risk accepted by the PO for the beta:** no protection against a fake server on public Wi-Fi. **Go-live step:** confirm the real issuer from the browser padlock on the production host, put it and one backup issuer in the build (`FIELD_APP_PINS` or `app.json` `extra.pins`) and in Settings › Security, and ship the store build with pinning on. Built with it, regardless of the switch: a refused certificate says *Can't verify the server. Contact the office.* and a missing door or non-JSON answer says *The server needs an update.* — only a real dropped connection says *No signal*. ⚠⚠ **AMENDED 2026-10-28 — PINNING IS DROPPED AS A GO-LIVE REQUIREMENT AND IS DORMANT IN EVERY BUILD (`CR-195-BRC10`; decision log 2026-10-28, PO: *"start A1"*). EVERYTHING ABOVE ABOUT *production stays ON*, *refused*, *default ON* AND THE *Go-live step* IS SUPERSEDED.** Both EAS profiles, `preview` and `production`, set `FIELD_APP_PINNING=off`, and unset now means OFF; only the exact word `on` switches it on, and a production build with it off is allowed. The phone relies on **Android's standard certificate validation**: system certificate authorities only (from API 24 an authority a user installs is ignored), cleartext blocked (API 28+), target SDK 35, no `network_security_config`, no TLS bypass anywhere in the code (no `rejectUnauthorized`/`trustAll`/`allowInvalid` — verified 2026-10-28), and the build's server must be `https://` (`src/release/serverAddress.ts`). **The pinning code is kept, dormant** (`pinning.ts` never initialises the library; `pinningState()` reads `off_by_config`), so it returns as configuration only: `FIELD_APP_PINNING=on` plus the server's confirmed issuer and a backup. **Nothing of it is shown to a user:** the Settings › About line is removed, and the staff portal's *Field app certificates* card is hidden by the platform setting `SBH_FIELD_APP_PINNING_ENABLED` (default false; the stored lists and the endpoint stay). **The 2026-10-26 risk sentence above is CORRECTED:** with pinning off a fake server on public Wi-Fi is still refused by the standard check; pinning adds protection only against a wrongly issued genuine certificate for our domain, or a rooted phone. **Two verifications PENDING:** (1) DevOps to confirm the real issuer of smartbillhub.bynry.com (needed only if pinning is switched back on); (2) one test-phone run with a mitmproxy certificate authority installed, expecting *"Can't verify the server"*. The honest connection errors are unchanged. |
| **Store builds** | Signing keys in CI, never on a laptop. Over-the-air JavaScript updates signed and version-pinned |

---

## 5 · What leaves the handset

**Three channels, and only one carries customer data.**

1. **The sync** — carries everything, over TLS (pinned until 2026-10-28; pinning dormant since, `CR-195-BRC10`), to one server. This is the only one. The tenant is resolved
   from the credential, never from the payload (`R127`).
2. **Telemetry** — crash reports and events, through a scrubber built as an **allow list of fields**. No name,
   address, account, balance, reading, photograph or outbox payload. Session replay off. Rules `R66` to `R72`. (The
   crash reporter is **Crashlytics**, ruled 2026-10-21 — `11-technology.md` §5; the scrubber sits in front of it as it
   would have in front of Sentry.)
3. **Deep links out** — navigation hands an address to Apple or Google Maps. That is a street address and nothing
   else; no name, no account number.

---

## 6 · What we deliberately do not do

| | |
|---|---|
| **No MDM requirement** | A ten-person utility does not run mobile device management. The app secures itself on an unmanaged device, and works better on a managed one |
| **No app-level PIN on top of the device passcode** | Two passcodes means one written on the van dashboard. Device passcode plus a five-minute auto-lock is the honest control |
| **No blocking on a weak signal** | Degrading to read-only when auth cannot refresh is how a day is lost. Capture never depends on the network |
| **Analytics identity per person — RULED 2026-10-21: ALLOWED** | The design read *"No analytics identity per person — tenant, role and an anonymous device id. Pending your word, and the build assumes not."* **The PO gave that word on 2026-10-21 (decision log, *"Field app: crash reporter, technician identity…"*): analytics MAY name the individual technician.** What does not move: **customer facts still never leave the handset** — no customer name, address, account number, balance, reading, photograph, signature or outbox payload in any event or breadcrumb (§5 channel 2, `R66`); session replay stays off (`R68`); and telemetry is still never the audit trail. The technician's own landing screen still scores nobody (`R120`) |

---

## 7 · Before code starts

1. **The two-credential model agreed with whoever owns authentication on the server** — it needs a server endpoint
   that does not exist yet (`07-endpoints.md` N24; identity owns the access token, work owns `technician_devices` and
   the capture credential). The 36-hour vs 7-day difference (§1) belongs in that agreement.
2. **Certificate pin rotation written down before the first pin ships.** ⚠ **DONE 2026-10-24 (`OQ-FLD-12797`).** The rotation, as the ruling's worked example: *the issuer renews in 2027; in December 2026 the office adds the new issuer's key on Settings › Security; every phone picks it up at its next sync; then the old key is deactivated.* The card warns 60 days before any key expires. The server refuses a list with fewer than two active, unexpired keys, and one that keeps NONE of today's active keys (a phone could never fetch the correction over it); the phone refuses the same and keeps its last good set. Default pair: ISRG Root X1 (current issuer) + GTS Root R1 (backup issuer) — confirm the deployed host's chain ends in one of them before the first store build. ⚠ **2026-10-28 (`CR-195-BRC10`, PO *"start A1"*): pinning is dormant and no longer a go-live requirement, so this confirmation is needed only on the day pinning is switched back on** (§4 *Transport*).
3. **A decision on whether the utility's own policy requires MDM**, which is a customer question rather than ours.
4. **The retention figures here reconciled with the utility's data policy** — 14 days of closed jobs on a handset is
   our number, not theirs (`03-field-map.md` §7).
5. **A test that proves the scrubber by breaking it:** force a crash on FF-25 Customer with a real account on screen,
   assert the report carries no name, address, account or balance (T-76). *Our addition, after the 2026-10-21
   identity ruling:* with technicians now nameable, the same test should also prove the technician's name is the ONLY person-identifying field that leaves — an allow list
   admitting it, and nothing of the customer beside it.

None of the five was done as of 2026-10-21; item 2 is done as of 2026-10-24 (and item 3 was answered the same day: no MDM).
