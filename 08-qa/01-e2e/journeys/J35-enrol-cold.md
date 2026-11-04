# J35 — A billed customer who has never signed in, enrols cold (three facts off the bill, a code to `••• ••• 4218` and nowhere else, and nothing revealed in between)

---
id: J35
tier: 2
rules: [BR-CWP-004, BR-CWP-005, BR-CWP-008, BR-CWP-009, BR-CWP-010, BR-CWP-011, BR-CWP-029, BR-CWP-030, BR-CWP-031, BR-CWP-032, BR-CWP-033, BR-CWP-034, BR-CWP-035, BR-CWP-036, BR-CWP-037, BR-CWP-038, BR-CWP-039, BR-CWP-040]
stories: [US-CWP-005, US-CWP-016, US-CWP-017, US-CWP-018, US-CWP-019, US-CWP-020, US-CWP-021]
# Wiring: every story above cites `J35` in its own `journeys:` frontmatter.
# Activation authority = the GENERATED index (10-scripts/07-e2e-wiring-index.py);
# NOT ACTIVATED — no `07-frontend/e2e/J35.spec.ts`. Release 2.
# 🔒 `US-CWP-021` (credential store, session, RLS) is a SENSITIVE PATH: the
# files carry HUMAN-REVIEW-PENDING and a row in 09-human-review-ledger.md in
# plain English with a figure. Step 8 (RLS with no tenant set) is proved on
# real PostgreSQL — the SQLite suite has no row-level security (law 14).
---

**Intent.** The security journey. Between *account matched* and *identity proven* the
portal **knows which account is meant and has told the visitor nothing** — no name, no
balance, no address — and that gap is the whole defence against somebody enrolling with a
stolen bill. The code goes **only** to a contact already held on the account and is shown
masked; an account with no phone and no email **dead-ends into "ring the office"** rather
than falling back to something weaker. Enrolment **attaches a password to a person already
on file; it never creates one** — and the credential it creates lives in its own table, in
its own session, and **can never resolve into a staff role**.

**Upstream leaves (handoff in).** Tenant `pine-hill` live, password policy *≥ 8 characters
with a capital and a number*. Customer **Maria Alvarez**, account `ACC-10432-A` at `1408
Elm St · A`, postcode `78702`, services Water · Sewer · Trash, mobile `(512) 555-4218`,
email `m.alvarez@example.com`, balance today `$142.18` (`BL-2608-0141`). She also holds
`ACC-10432-B`, the common-areas master and `22 Palm Ct` (J37). Company account
`ACC-10801-A` · *Kestrel Holdings LLC*. Already-enrolled account `ACC-10519-C`. Account
`ACC-10777-A` with **no phone and no email**. Staff user `sarah.miller@pinehill.example`
(System Admin) in `identity.user`. Tenant `oak-ridge`, account `ACC-20001-A`. **No
`portal_credential` row exists for Maria.**

**This journey leaves (handoff out).** ONE `portal_credential` row (`customer_id` = Maria's
existing row, `email = m.alvarez@example.com`, Argon2id hash, `otp_channel = sms`,
`enrolled_on` now, `status = active`) with **no foreign key to `identity.user`**; ONE
`portal_session` row whose `account_set` is **one flat entry** `(ACC-10432-A, holder)`,
re-derived on read; audit rows for enrolment and sign-in. **Zero** new `customer` rows;
**zero** changes to the balance. J36 and J37 start from this credential.

**Fixture.** Code `418902`, ten minutes. Attacker-supplied address `attacker@example.com`.
Source addresses `198.51.100.10` / `203.0.113.7`. Reset addresses `m.alvarez@example.com`
(has a login after step 6) · `nobody@example.com` · `sarah.miller@pinehill.example`. Screens
`CWP-015` → `CWP-016` → `CWP-017` → `CWP-018` → `CWP-022`; `CWP-019` for the reset.

| # | Actor · action | Expected outcome (contract) | Downstream assertions (record · outbound queue · session · audit) | Rule |
|---|---|---|---|---|
| 1 | Maria opens `/pine-hill` → *Sign in* card → `CWP-015` | Left: utility name, strapline, services, office and emergency lines. Right: Email / Password / *Forgotten it?* / *Sign in* / *Keep me signed in*, then **three routes stated as three routes**: *Set up your login →* · *Pay with a bill number →* · *Start service →*. **Not the front page** — it sits behind `CWP-001`'s card | *Pay with a bill number* reaches quick pay **without a password** (J30). No session row yet | BR-CWP-004 · BR-CWP-007 |
| 2 | `CWP-016` — `ACC-10432-A` + `78702` + `Alvarez`, *Continue →* | Proceeds to `CWP-017`. **The response contains no name, no balance, no address** — asserted on the body. Rail **NO BILL TO HAND?** *Ring the office … We cannot send it by email — it identifies the account.* | Three facts, **all printed on the paper bill**. **Not** the date of birth or the last four of an SSN — those are encrypted and blind-indexed for counter recognition, not a form anyone can hammer. A customer holding **four** accounts matches only the one whose number was given; the other three are **not revealed** at this step | BR-CWP-030 · BR-CWP-031 · BR-CWP-032 |
| 3 | **negative** — right account, wrong surname; then an unknown account number; then `ACC-10801-A` + `Alvarez` (a company); then `ACC-10519-C` (already enrolled) | The first two refusals are **identical**. The company refuses — a business matches on company name. The already-enrolled account refuses with a route to *forgotten password* **and the refusal does not confirm a login exists** | Four wrong attempts from `198.51.100.10`: the fourth reads *"locked for fifteen minutes"* — ⚠ **three tries here, not five**: the staff sign-in policy applied to a public form. `203.0.113.7` unaffected. The lockout is a cache entry, not a table | BR-CWP-036 · BR-CWP-032 |
| 4 | `CWP-017` — *We sent you a code. It went to the phone we already hold: **••• ••• 4218**. It lasts ten minutes.* | ONE outbound row with destination **`(512) 555-4218`** — the contact **already on the account**. The mask is applied server-side. `DialInput`-style six-digit field, *Verify ✓*, *Send it again*, *Wrong number? Ring the office.* | **negative:** a request body naming `attacker@example.com` as the destination is **ignored** — assert the outbound row's destination is the stored contact. *Send it again* → a **new** code and the previous stops working immediately. Six wrong codes → locked **and the code invalidated** — a lock that leaves the code live is not a lock | BR-CWP-033 · BR-CWP-035 |
| 5 | **negative · the dead end** — the same flow for `ACC-10777-A` (no phone, no email) | Dead-ends into **"ring the office"**. Assert **no code is generated and no channel is invented** — zero outbound rows, zero short-lived store entries | It must never fall back to something weaker. **negative · expiry:** the code entered at **eleven minutes** reads *"that code has expired"* **with a resend** — not an error page, not a restart of the whole flow | BR-CWP-034 · BR-CWP-035 |
| 6 | `CWP-018` — two matching passwords meeting the policy; code channel *Text to ••• ••• 4218*; the rail **WHAT YOU ARE ABOUT TO GET ACCESS TO**: Account `ACC-10432-A` / Service address `1408 Elm St · A` / Services *Water, Sewer, Trash* / **Balance today `$142.18`** — then **WHEN YOU FINISH**: *You can see and pay bills on this account · **You cannot close it or change who it belongs to** · We will email you when a bill is ready.* *Create my login ✓* | ONE `portal_credential` row attached to the **existing** customer; ONE `portal_session`; lands on `CWP-022`, avatar `MA`. **This is the first screen in the flow allowed to show a balance** — identity is now proven. The `$142.18` is `US-CWP-024`'s read, not a second computation | The policy is **read from the tenant**, not hardcoded: eight characters is refused on a tenant requiring twelve and accepted on one requiring eight. Mismatched confirmations are refused and **neither value is echoed back**. Reaching `POST enrol/set-password` **without a verified code is refused at the endpoint** — the guard is not the wizard. Enrolling twice against one account → the second is refused; **one credential per email per tenant** | BR-CWP-037 · BR-CWP-039 · BR-CWP-029 · BR-CWP-032 |
| 7 | **the session** — read it back | Tenant, person, and a **set** of one entry `(ACC-10432-A, holder permissions)` — never a customer id on its own. Built from **exactly two sources**: customer-to-account links and delegate grants | **negative:** a crafted session whose `account_set` names another customer's account is **refused, because the set is re-derived from the two sources on read**, not trusted from the token. A direct request for an account **not in the set** is refused **without revealing whether it exists**. A portal session calling any **staff** route is refused **at the edge** — asserted on the endpoint | BR-CWP-008 · BR-CWP-009 · BR-CWP-011 |
| 8 | **🔒 PostgreSQL** — a query on `portal_credential` / `portal_session` with **no `app.tenant_id`** set | **Refused by RLS `FORCE`** — proved on real PostgreSQL, because the SQLite suite has no row-level security | The tenant is resolved from the **path**, `app.tenant_id` set, RLS forced, and **only then** is *who is this* asked. The order is the safety | BR-CWP-005 · BR-CWP-010 · hard rule 1 · law 14 |
| 9 | **negative · the staff store** — Sarah's `sarah.miller@pinehill.example` + her password on `CWP-015` | **Refused as an ordinary failure**, not a role error. **No session row is created.** The staff credential does not authenticate here at all — two stores, **no link**: `portal_credential` has **no foreign key to `identity.user`** and is not one table with a flag on it | Six wrong passwords on sign-in → the sixth reads *locked for fifteen minutes*; a correct password inside the lock is still refused | BR-CWP-004 · BR-CWP-036 |
| 10 | `CWP-019` — forgotten password: `m.alvarez@example.com`, then `nobody@example.com`, then `sarah.miller@pinehill.example` | **The same *"check your email"* panel every time — byte-identical response and identical timing.** Only Maria's address receives a link; the staff store is **not consulted** | The link opens `CWP-018` **with the password fields empty**; a link on day eight is refused with a route to request another; a used link is dead on second use. Seven-day lifetime — the existing staff temporary-password machinery. Depends on the outbound email queue, activated in the email wave | BR-CWP-038 |
| 11 | **release 5 · boundary** (`US-CWP-005`) — a guest who has just paid takes *Set up a login →* on `CWP-004` | Routes to `CWP-017` — *prove it is you* — and **does not skip the one-time code** because a payment succeeded. The receipt was downloadable **before** the offer and stays reachable whether or not it is taken; **no credential row is created silently** | Rails are release 5; the routing and the refusal to skip the code are the contract | BR-CWP-029 · BR-CWP-040 |
| 12 | **tenant isolation** | `ACC-10432-A` + `78702` + `Alvarez` on `/oak-ridge` → refused **before any customer row is read**. A code issued on Pine Hill submitted on `/oak-ridge` → refused. The created credential does **not** authenticate on `/oak-ridge` even with the same email. A Pine Hill reset link opened under `/oak-ridge` → refused | `app.tenant_id` is set from the **path**, never from the session or the token | BR-CWP-005 · hard rule 1 |
| 13 | **INVARIANCE** | Between step 2 and step 6 the portal knew which account was meant and disclosed **nothing** about it. No `customer` row was created — the password attached to a person already on file. The balance shown on `CWP-018` equals `CWP-022`'s tile to the cent. *Keep me signed in*, then a return **eleven months later** (J36): the session has expired and `CWP-015` is still usable cold — no stale state, no half-rendered shell | *Sign out everywhere* revokes every session for the credential; the current request's next call is refused | BR-CWP-032 · BR-CWP-029 · `US-CWP-021` TC-8 |

## What this journey CANNOT yet assert, and why

| # | Not asserted | Blocked on |
|---|---|---|
| a | The enrolment offer after a **real** guest payment (step 11) | Rails — release 5 |
| b | A second factor **exists** in the product today | It does not — *"Nothing in the identity module implements a second factor today"* (`US-CWP-018` §8). This is genuinely new, not a mirror of staff behaviour; the contract above is what it must do |
| c | The `HUMAN-REVIEW-PENDING` sign-off on the RLS policies | A ratification in the working chat, written into `09-human-review-ledger.md` with the figure shown — never a lane's own approval |


---

## Built and walked in a browser — 2026-09-04, `CR-068` wave E

**What a customer can now do that they could not this morning:** open
`/pine-hill/portal/sign-in`, take *first time here*, type the three facts off
their paper bill, receive a six-digit code addressed **only** to the phone
already on the account, choose a password against **their utility's own** length
rule, and land in a portal shell showing what they owe.

**What was built to the letter of this journey**

| Step | Built as written | Where |
|---|---|---|
| 1–2 | The three facts; the response carries `matched`, a code-row reference, the masked contact and nothing else | `apps/portal/api.py::find_account` |
| 2 negative | A wrong surname and an unknown number are compared **as bytes** in the test, not as parsed dicts | `tests/test_us_cwp_016_getting_in.py` TC-3 |
| 3 | Three wrong tries lock the FORM for fifteen minutes, and a correct set inside the window is still refused | `credentials.record_enrolment_miss` (`lockout.max_attempts`) |
| 4 | The code goes to the contact on file; the test asserts the **outbound row's destination**, not the screen | TC-5 |
| 4 negative | An account with neither phone nor email dead-ends and carries **no reference to go on with** | `US-CWP-017` TC-4 |
| 5 | Ten minutes; single use; a resend supersedes the live code in the same transaction; six wrong tries lock it | `credentials.issue_code` · `verify_code` |
| 6 | The tenant's own `pw_min_length` is read and stated in the helper line; eight characters refused where it is twelve | `seams/identity_seam.py` |
| 7 | The set is **re-derived on every request** from `BR-CWP-009`'s two sources; the stored column authorises nothing | `session.py::account_set` |
| 8 | 🔒 RLS `FORCE` on all three tables, proved on **PostgreSQL 16** under a non-superuser probe role, reading `relrowsecurity` **and** `relforcerowsecurity` | `tests/test_us_cwp_021_pg.py` |
| 9 | The staff email and password get the ordinary failure and **write no session row** | TC-1 of `US-CWP-020` |
| 10 | One shared response object, returned by both branches; the test compares the two bodies as **bytes** and asserts the queue holds **one** reset row | TC-2 |
| 12 | A Pine Hill session on `/oak-ridge` answers **404** — never 403, which would confirm Oak Ridge exists | TC-3 |

**Three things this journey says that the build reads differently, recorded
rather than quietly reconciled**

1. **Step 9 says *"six wrong passwords → the sixth reads locked"*; the field map
   says *"Lock at 5 for 15 minutes"*.** The build follows the field map: the
   **fifth** wrong password is the one that crosses the threshold and is
   answered `locked`. Both sentences describe five failures; they differ only on
   which response says so, and the field map is the contract.
2. **Step 11 (the enrolment offer after a guest payment) is not built and is not
   this wave's.** Rails are release 5. Nothing about it is stubbed, because
   there is no screen to stub it on.
3. **A second factor at *step-up before a stored payment method changes*
   (`BR-CWP-040`) is not built**, for the reason `US-CWP-018` §8 already
   states: there is no stored payment method in this product yet. The code at
   ENROLMENT — the half `BR-CWP-040` also names — is built and is what this
   journey walks.

**Not activated.** There is still no `07-frontend/e2e/J35.spec.ts`; the
browser-side proof is `10-scripts/render-checks/cr068-e-getting-in.mjs`, which
walks the eight steps, asserts the masked phone on screen and the real number
**absent from the DOM**, reads the consequence panel's `$142.18`, checks the
switcher is a **label** and that no `<select>` exists at all for one account,
reads the active tab's **computed** border width and colour, and compares the
two reset panels as strings.
