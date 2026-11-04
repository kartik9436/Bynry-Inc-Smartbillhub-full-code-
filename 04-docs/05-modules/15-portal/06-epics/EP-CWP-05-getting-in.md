# EP-CWP-05 — Getting in

**Module:** portal · **Wave:** release 2 · **Screens:** CWP-015 … CWP-019 ·
**Status:** draft

## Scope

**In:** the front door, enrolment on three facts off the bill, the one-time code, the
password, the reset, the credential store and the session behind all of it, and the
step-up before a stored method changes.

**Out:** the six errand cards in front of it (`EP-CWP-01`), delegated access
(`EP-CWP-06`).

⚠ **THE DESIGN PROBLEM IN ALL FIVE SCREENS IS THE SAME:** the person on the other side
has a paper bill and no memory of this website. **The account number on that bill is the
only thing they reliably have**, so it is the key the front door is built around.

⚠ **AND MOST VISITS ARE COLD.** Somebody pays four to twelve times a year; they will not
remember a password or where anything is. **Every screen has to be usable by someone who
has forgotten everything.**

## Capability matrix

| Screen | Search | Filters | Default sort | Sortable | Columns | Row actions | Bulk | Export |
|---|---|---|---|---|---|---|---|---|
| CWP-015 … CWP-019 | — | — | — | — | — | — | — | — |

---
id: US-CWP-016
epic: EP-CWP-05
module: portal
screens: [CWP-015]
wave: 2
status: ready
blocked_by: []
depends_on: [US-CWP-021]
journeys: [J35, J36]
rules: [BR-CWP-004, BR-CWP-007, BR-CWP-036]
golden_tests: []
finance_calc: none
---
### US-CWP-016 — The front door: three doors stated as three doors

**1 · Details** — As **a returning customer**, I want **to sign in**, and as **anyone
else** I want **the other two doors named on the same screen**, so that **nobody is
trapped in front of a password field they do not need**.

Email, password, *forgotten it?*, *keep me signed in*. Then three routes stated plainly:
**first time here → set up your login · just want to pay → pay with a bill number ·
moving in → start service**.

⚠ **THE PAY-WITH-A-BILL-NUMBER ROUTE MATTERS MORE THAN IT LOOKS.** A large share of
portal traffic is one payment and nothing else, and **forcing an enrolment in front of it
is how a utility ends up with a portal nobody uses.**

**2 · Business Rules**

| BR | Statement | Status |
|---|---|---|
| `BR-CWP-004` | A portal credential must never resolve into a staff role | CONFIRMED — `CR-068` `R1` |
| `BR-CWP-005` | The tenant is resolved before anyone is identified | CONFIRMED — blueprint §20 |
| `BR-CWP-036` | Lockout mirrors the staff policy | CONFIRMED — blueprint `P2` |
| Inherited | The utility's own brand, not ours | tenant record |

**3 · Test Cases**

| TC | Scenario | Expected |
|---|---|---|
| TC-1 | `m.alvarez@example.com` with the right password | Lands on `CWP-022`, avatar reads `MA` |
| TC-2 · **negative** | A **staff** user's email and password | Refused. ⚠ **The staff credential does not authenticate here at all** — assert no session row is created and the response is the ordinary failure, not a role error |
| TC-3 · **negative** | Six wrong passwords | The sixth reads *"locked for fifteen minutes"* rather than being a sixth attempt |
| TC-4 · **negative** | A correct password during the lock | Still refused |
| TC-5 · **tenant isolation** | Pine Hill's credential on `/oak-ridge` | Refused. The tenant is resolved from the path **first**, so the credential is not even looked up |
| TC-6 | *Keep me signed in*, then return eleven months later | ⚠ Session expired, and the screen is still usable cold — no stale state, no half-rendered shell |
| TC-7 | The three route links | All three present. **Pay reaches quick pay without a password** |

**4 · Test Data** — `m.alvarez@example.com` / a valid password, customer *Maria
Alvarez*, account `ACC-10432-A`. A staff user `sarah.miller@pinehill.example` with a
System Admin role, for TC-2.

**5 · Data Fields / Mapping**

| Field | Screen | Source | DB target | Type | Origin | Validation |
|---|---|---|---|---|---|---|
| Email | CWP-015 | prototype-extracted | `portal_credential.email` | citext | user-input | Unique per tenant |
| Password | CWP-015 | prototype-extracted | `portal_credential.password_hash` | text | user-input | ⚠ Compared against the **portal** store only |
| Keep me signed in | CWP-015 | prototype-extracted | `portal_session.expires_at` | timestamptz | user-input | Longer sliding window; still expires |

**6 · Acceptance** — **Given** a customer with a portal login, **when** they sign in,
**then** they land on the portal home; **and given** a staff user's credentials, **when**
they are entered here, **then** they are refused and no portal session exists — because
the two stores are not linked at all.

**7 · Finance Calculation** — N/A.

**8 · Open Questions** — None.

---
id: US-CWP-017
epic: EP-CWP-05
module: portal
screens: [CWP-016]
wave: 2
status: ready
blocked_by: []
depends_on: [US-CWP-021]
journeys: [J35]
rules: [BR-CWP-030, BR-CWP-031, BR-CWP-032, BR-CWP-036]
golden_tests: []
finance_calc: none
---
### US-CWP-017 — Find my account, on three facts printed on the bill

**1 · Details** — As **a customer who has never signed in**, I want **to be found by
what is on my bill**, so that **I can set up a login without ringing anyone**.

Account number, service postcode, last name or company name. A panel: *no bill to hand?
Ring the office — we cannot send it by email, it identifies the account.*

⚠ **DELIBERATELY NOT THE DATE OF BIRTH OR THE LAST FOUR OF A SOCIAL SECURITY NUMBER.**
Those are held encrypted and blind-indexed for recognising a returning customer at the
counter — **not for a self-serve form anyone can hammer** (`BR-CWP-031`).

⚠ **AND MATCHING IS NOT PROVING.** After this screen the portal knows which account is
meant and **has told the visitor nothing** — no name, no balance, no address. **That gap
is the whole defence against someone enrolling with a stolen bill.**

**2 · Business Rules**

| BR | Statement | Status |
|---|---|---|
| `BR-CWP-030` | Three facts, all printed on the paper bill | CONFIRMED — blueprint `P2` |
| `BR-CWP-031` | Never the date of birth or the last four of an SSN | CONFIRMED — blueprint `P2` |
| `BR-CWP-032` | Matched and proven are two separate states, and nothing is revealed between them | CONFIRMED — blueprint §8 Figure 4 |
| `BR-CWP-036` | Three wrong tries locks fifteen minutes | CONFIRMED — blueprint `P2` |

**3 · Test Cases**

| TC | Scenario | Expected |
|---|---|---|
| TC-1 | `ACC-10432-A` + `78702` + `Alvarez` | Proceeds to `CWP-017`. ⚠ The response contains **no name, no balance, no address** — asserted on the body |
| TC-2 · **negative** | Right account, wrong surname | Refused, **identically** to an unknown account number |
| TC-3 · **negative** | Four wrong attempts | The fourth reads *"locked for fifteen minutes"* — ⚠ **three tries here, not five**, matching the staff sign-in policy for a public form |
| TC-4 · **negative** | An account that **already** has a credential | Refused with a route to *forgotten password* — ⚠ and the refusal does **not** confirm that a login exists |
| TC-5 · **tenant isolation** | Pine Hill's `ACC-10432-A` on `/oak-ridge` | Refused before any customer row is read |
| TC-6 · **negative** | A company account with a person's surname | Refused; a business matches on company name |
| TC-7 | A customer holding **four** accounts | Matches the one whose number was given. ⚠ It does **not** reveal the other three at this step |

**4 · Test Data** — `ACC-10432-A` · `78702` · `Alvarez` → customer *Maria Alvarez*, who
also holds `ACC-10432-B`, the common-areas master, and `22 Palm Ct`. Company account
`ACC-10801-A` · `Kestrel Holdings LLC`. Already-enrolled account `ACC-10519-C`.

**5 · Data Fields / Mapping**

| Field | Screen | Source | DB target | Type | Origin | Validation |
|---|---|---|---|---|---|---|
| Account number | CWP-016 | prototype-extracted | `account.number` | text | user-input | ⚠ The **human** reference (B14 rule 31) |
| Postcode | CWP-016 | prototype-extracted | `premises.postcode` | text | user-input | The **service** address |
| Last name / company | CWP-016 | prototype-extracted | `customer.last_name` \| `company_name` | text | user-input | Whichever the customer kind implies |

**6 · Acceptance** — **Given** a customer holding a paper bill, **when** they enter the
account number, the service postcode and their surname, **then** the portal proceeds to
the code step having disclosed nothing about the account; **and given** any one fact is
wrong, **then** the refusal is identical to an account that does not exist.

**7 · Finance Calculation** — N/A. ⚠ **No balance is read on this screen at all** — that
is the point of `BR-CWP-032`.

**8 · Open Questions** — None.

---
id: US-CWP-018
epic: EP-CWP-05
module: portal
screens: [CWP-017]
wave: 2
status: ready
blocked_by: []
depends_on: [US-CWP-017]
journeys: [J35]
rules: [BR-CWP-033, BR-CWP-034, BR-CWP-035]
golden_tests: []
finance_calc: none
---
### US-CWP-018 — Prove it is you: a code, to a contact already on file

**1 · Details** — As **the utility**, I want **the code to go only where we already hold
a contact**, so that **the account-number lookup cannot become an enrolment route for a
stranger**.

*"It went to the phone we already hold: ••• ••• 4218. It lasts ten minutes."* Six digits,
verify, resend, and *wrong number? Ring the office.*

⚠ **THE SECURITY OF THE WHOLE PORTAL IS THIS SCREEN.** Sending the code to a contact
already held, and masking it, is what stops `CWP-016` being an enrolment route.

⚠ **AND IF AN ACCOUNT HAS NO PHONE AND NO EMAIL ON FILE, THIS PATH MUST DEAD-END INTO
"RING THE OFFICE".** It must never fall back to something weaker.

**2 · Business Rules**

| BR | Statement | Status |
|---|---|---|
| `BR-CWP-033` | The code goes **only** to a contact already on the account, and is shown masked. **Never** to an address typed on the previous screen | CONFIRMED — blueprint `P3` |
| `BR-CWP-034` | No contact on file ⇒ dead-end into *ring the office* | CONFIRMED — blueprint `P3` |
| `BR-CWP-035` | Ten minutes. An expired code shows *"that code has expired"* with a resend, never an error page | CONFIRMED — `CP-02` |
| `BR-CWP-040` | A second factor is required at enrolment | CONFIRMED — blueprint §3 |

**3 · Test Cases**

| TC | Scenario | Expected |
|---|---|---|
| TC-1 | A matched account with a mobile on file | *"••• ••• 4218"*, a six-digit code arrives, verification proceeds |
| TC-2 · **negative** | Enter the code **eleven minutes** later | *"that code has expired"* **with a resend** — not an error page, not a restart of the whole flow |
| TC-3 · **negative** | An account with **no** phone and **no** email | Dead-ends into *ring the office*. ⚠ Assert **no code is generated and no channel is invented** |
| TC-4 · **negative** | Try to direct the code to an address supplied in the request body | Ignored. The code goes to the stored contact. ⚠ Assert the outbound row's destination |
| TC-5 · **negative** | Six wrong codes | Locked, and the code is invalidated — a lock that leaves the code live is not a lock |
| TC-6 · **tenant isolation** | A code issued on Pine Hill, submitted on `/oak-ridge` | Refused |
| TC-7 | Resend | A **new** code; the previous one stops working immediately |

**4 · Test Data** — Account `ACC-10432-A`, mobile `(512) 555-4218` → masked *"••• •••
4218"*. Code `418902`. Account `ACC-10777-A` with no phone and no email, for TC-3.
Attacker-supplied address `attacker@example.com` for TC-4.

**5 · Data Fields / Mapping**

| Field | Screen | Source | DB target | Type | Origin | Validation |
|---|---|---|---|---|---|---|
| Masked destination | CWP-017 | prototype-extracted | derived from `customer_contact` | text | computed-display | ⚠ Masked **server-side** |
| Six-digit code | CWP-017 | prototype-extracted | short-lived store, not a table | text | system-derived | 10 minutes, single use |
| Channel | CWP-017 | prototype-extracted | `portal_credential.otp_channel` | enum | system-derived | Only a channel already held |

**6 · Acceptance** — **Given** a matched account with a mobile on file, **when** the code
step opens, **then** a code goes to the masked number already held and to nowhere else;
**and given** an account with no contact at all, **then** the flow dead-ends into *ring
the office* and no code is created.

**7 · Finance Calculation** — N/A.

**8 · Open Questions** — None. ⚠ **Nothing in the identity module implements a second
factor today** — this is genuinely new, not a mirror of staff behaviour.

---
id: US-CWP-019
epic: EP-CWP-05
module: portal
screens: [CWP-018]
wave: 2
status: ready
blocked_by: []
depends_on: [US-CWP-018]
journeys: [J35]
rules: [BR-CWP-037, BR-CWP-039]
golden_tests: []
finance_calc: none
---
### US-CWP-019 — Choose a password, and see what the login will let you do

**1 · Details** — As **a new portal user**, I want **to know what this login can and
cannot do before I create it**, so that **I am not surprised later**.

Password twice, a choice of code channel, and **a consequence panel**: the account, the
service address, the services, the balance today — then *you can see and pay bills on
this account · you cannot close it or change who it belongs to · we will email you when a
bill is ready.*

⚠ **THE CONSEQUENCE PANEL IS A HOUSE RULE, NOT DECORATION.** Any form that writes money,
service state or a legal notice shows what it will do before the button that does it —
**and enrolment qualifies, because it grants standing access to somebody's billing
record.**

⚠ **THIS IS THE FIRST SCREEN IN THE FLOW THAT MAY SHOW A BALANCE.** Identity has now been
proven; on `CWP-016` and `CWP-017` it may not.

**2 · Business Rules**

| BR | Statement | Status |
|---|---|---|
| `BR-CWP-037` | Password policy is the tenant's existing settings — the portal adds no second policy | CONFIRMED — blueprint `P4` |
| `BR-CWP-039` | A consequence panel before the commit, naming what the login can and cannot do | CONFIRMED — B14 house rule |
| `BR-CWP-032` | A balance may appear **only after** identity is proven | CONFIRMED — blueprint §8 Figure 4 |

**3 · Test Cases**

| TC | Scenario | Expected |
|---|---|---|
| TC-1 | Two matching passwords meeting the tenant's policy | Credential created, session issued, lands on `CWP-022` |
| TC-2 | A tenant whose policy requires twelve characters | Eight is refused **on that tenant** and accepted on one requiring eight. ⚠ **The policy is read, not hardcoded** |
| TC-3 · **negative** | Mismatched confirmations | Refused, and neither value is echoed back |
| TC-4 · **negative** | Reach this screen without a verified code | Refused. ⚠ Assert the step cannot be called directly — the guard is on the endpoint, not the wizard |
| TC-5 | The consequence panel | Names `ACC-10432-A`, `1408 Elm St · A`, Water/Sewer/Trash and `$142.18`, and states plainly that the login **cannot** close the account or change who it belongs to |
| TC-6 · **tenant isolation** | The created credential | Scoped to Pine Hill. It does not authenticate on `/oak-ridge` even with the same email |
| TC-7 · **negative** | Enrol twice against one account | The second is refused; **one credential per email per tenant** |

**4 · Test Data** — Account `ACC-10432-A`, `1408 Elm St · A`, Water/Sewer/Trash, balance
today `$142.18`. Code channel choices: text to `••• ••• 4218`, or email to
`m.alvarez@example.com`. Tenant policy: ≥ 8 characters with a capital and a number.

**5 · Data Fields / Mapping**

| Field | Screen | Source | DB target | Type | Origin | Validation |
|---|---|---|---|---|---|---|
| New password | CWP-018 | prototype-extracted | `portal_credential.password_hash` | text | user-input | Argon2id; **tenant policy** |
| Code channel | CWP-018 | prototype-extracted | `portal_credential.otp_channel` | enum | user-input | Only channels held |
| Balance today | CWP-018 panel | prototype-extracted | the balance read | numeric(18,4) → 2 | computed-display | ⚠ Live, not cached |

**6 · Acceptance** — **Given** a visitor who has proven identity, **when** the password
screen opens, **then** it names the account, its services and its `$142.18` balance and
states that the login cannot close the account; **and when** they set a password meeting
the tenant's own policy, **then** the credential is created and they land on the portal
home.

**7 · Finance Calculation** — The balance shown is `US-CWP-024`'s read, not a second
computation. **A figure here that disagrees with `CWP-022` is the defect this test
exists to catch.**

**8 · Open Questions** — None.

---
id: US-CWP-020
epic: EP-CWP-05
module: portal
screens: [CWP-019]
wave: 2
status: ready
blocked_by: []
depends_on: [US-CWP-021]
journeys: [J35]
rules: [BR-CWP-038]
golden_tests: []
finance_calc: none
---
### US-CWP-020 — Forgotten password, answered the same way either way

**1 · Details** — As **the utility**, I want **the reset form to answer identically
whether or not the address has a login**, so that **it cannot be used to test which
addresses are our customers**.

One email field. Always *"check your email"*. **The message itself is the only place the
difference shows.**

⚠ **A RESET FORM THAT SAYS "NO SUCH USER" TURNS ITSELF INTO A CUSTOMER LIST.**

**2 · Business Rules**

| BR | Statement | Status |
|---|---|---|
| `BR-CWP-038` | The same panel either way; only the message differs | CONFIRMED — `CP-03` |
| — | The link expires the way the staff temporary password does — **seven days** | CONFIRMED — the existing staff machinery |

**3 · Test Cases**

| TC | Scenario | Expected |
|---|---|---|
| TC-1 | A real customer's address | *"check your email"*, and a link arrives |
| TC-2 · **negative** | An address with no login | *"check your email"* — ⚠ **byte-identical response and identical timing**, and **no** email is sent |
| TC-3 · **negative** | A **staff** user's address | Same panel, no portal link. ⚠ The staff store is not consulted |
| TC-4 | Follow the link | `CWP-018` opens **with the password fields empty** |
| TC-5 · **negative** | Follow the link on day eight | Refused with a route to request another |
| TC-6 · **negative** | Follow a used link twice | The second use is refused |
| TC-7 · **tenant isolation** | A Pine Hill link opened under `/oak-ridge` | Refused |

**4 · Test Data** — `m.alvarez@example.com` (has a login) · `nobody@example.com` (does
not) · `sarah.miller@pinehill.example` (staff). Link lifetime seven days from 2 Sep 2026.

**5 · Data Fields / Mapping**

| Field | Screen | Source | DB target | Type | Origin | Validation |
|---|---|---|---|---|---|---|
| Email | CWP-019 | prototype-extracted | `portal_credential.email` | citext | user-input | Never echoed as found-or-not |
| Reset token | — | prototype-extracted | short-lived store | text | system-derived | Seven days, single use |

**6 · Acceptance** — **Given** any address typed into the reset form, **when** it is
submitted, **then** the same *"check your email"* panel appears with the same timing —
and only a real customer receives a link, which opens the password screen with the fields
empty.

**7 · Finance Calculation** — N/A.

**8 · Open Questions** — None. ⚠ **Depends on the outbound email queue**, which exists
and is activated in the email wave — state that in the task rather than assuming it.

---
id: US-CWP-021
epic: EP-CWP-05
module: portal
screens: []
wave: 2
status: ready
blocked_by: []
depends_on: []
journeys: [J35, J36, J37]
rules: [BR-CWP-004, BR-CWP-005, BR-CWP-008, BR-CWP-009, BR-CWP-010, BR-CWP-011]
golden_tests: []
finance_calc: none
---
### US-CWP-021 — The customer credential store and the portal session

**1 · Details** — As **the platform**, I want **a credential store and a session that
cannot become a staff session**, so that **a defeated portal login costs one customer's
data and never the utility's whole book**.

Two tables, `portal_credential` and `portal_session`, and the ordering that makes them
safe: **resolve the tenant from the path → set `app.tenant_id` → force RLS → only then
ask who this is.**

The session carries a tenant, the person, and a **set** of `(account, what they may do)`
— built from exactly two sources and nothing else.

⚠ **🔒 SENSITIVE PATH.** RLS policies and session scoping. Flag the files
`HUMAN-REVIEW-PENDING` and add a row to `12-governance/09-human-review-ledger.md` **in
plain English with a concrete figure** — never an ID to look up. `g07` enforces the
row's existence.

**2 · Business Rules**

| BR | Statement | Status |
|---|---|---|
| `BR-CWP-004` | Separate table, separate session, separate permission catalogue — **not one table with a flag on it** | CONFIRMED — `CR-068` `R1`; blueprint §20 red band |
| `BR-CWP-005` | Tenant resolved before anyone is identified | CONFIRMED — blueprint §20 Figure 15 |
| `BR-CWP-008` | The session holds a **set**, never a customer id on its own | CONFIRMED — blueprint §20 Figure 16 |
| `BR-CWP-009` | The set is built from the customer-to-account links plus delegate grants. **Nothing else may add an entry** | CONFIRMED — blueprint §20 Figure 16 |
| `BR-CWP-010` | Every query is filtered on **both** halves, **in the query** | CONFIRMED — blueprint §20 rule 4 |
| `BR-CWP-011` | A portal session may not call a staff route | CONFIRMED — `CR-068` §11e.3 |

**3 · Test Cases**

| TC | Scenario | Expected |
|---|---|---|
| TC-1 | Sign in and read the session | Tenant, person, and a set of one entry for a householder |
| TC-2 | A landlord's session | **Four flat entries**, one of them the common-areas master — ⚠ **not a parent, and the tenants' own accounts are not in the set** |
| TC-3 · **negative** | Call a **staff** endpoint with a portal session | Refused at the edge. ⚠ Assert on the endpoint, not on a screen |
| TC-4 · **negative** | Request an account **not in the set**, by id, directly | Refused, and the refusal does not reveal whether the account exists |
| TC-5 · **negative** | Craft a session whose `account_set` names another customer's account | ⚠ Refused, because the set is **re-derived from the two sources on read**, not trusted from the token |
| TC-6 · **tenant isolation** | A valid Pine Hill session against `/oak-ridge` | Refused. Assert `app.tenant_id` is set from the **path**, never from the session |
| TC-7 · **negative** · **PostgreSQL** | A query issued with no `app.tenant_id` set | Refused by RLS `FORCE`. ⚠ **Prove this on real PostgreSQL** — the SQLite suite has no row-level security |
| TC-8 | *Sign out everywhere* | Every session for that credential is revoked; the current request's next call is refused |

**4 · Test Data** — Householder: *Maria Alvarez* → `ACC-10432-A`. Landlord: the same
customer → `1408 Elm St · A`, `· B`, `· Common areas` (master), `22 Palm Ct`. A tenant's
own account `ACC-10432-B-TENANT` that must **not** appear. Second tenant `oak-ridge` with
account `ACC-20001-A`.

**5 · Data Fields / Mapping** — See `03-field-map.md` §1. The two fields worth repeating:
`portal_session.account_set` `jsonb`, **re-derived on read**; and the deliberate absence
of any foreign key from `portal_credential` to `identity.user`.

**6 · Acceptance** — **Given** a signed-in portal session, **when** it calls any staff
route or requests an account outside its set, **then** it is refused at the edge; **and
given** a query issued without `app.tenant_id`, **then** PostgreSQL refuses it — proved
against real PostgreSQL, not the suite's SQLite.

**7 · Finance Calculation** — N/A.

**8 · Open Questions** — None. ⚠ **`OQ-1397` (does a landlord see a tenant's bill) does
NOT block this story** — the flat set is the safe default and is what this story builds.
The question blocks only widening it.

---
id: US-CWP-022
epic: EP-CWP-05
module: portal
screens: [CWP-039]
wave: 5
status: blocked
blocked_by: []
depends_on: [US-CWP-018, US-CWP-046]
journeys: [J30]
rules: [BR-CWP-040]
golden_tests: []
finance_calc: none
---
### US-CWP-022 — Step-up before a stored payment method changes

**1 · Details** — As **the utility**, I want **a fresh code before a stored method is
added, changed or removed**, so that **a hijacked session cannot redirect a customer's
money**.

⚠ **THIS IS THE ONE ACTION THAT REDIRECTS MONEY**, and it is the reason the blueprint
requires step-up as well as enrolment-time verification.

**Held until rails** — there are no stored methods to change yet — but the step-up
mechanism is the same one `CWP-017` uses and is built with it.

**2 · Business Rules**

| BR | Statement | Status |
|---|---|---|
| `BR-CWP-040` | A second factor at enrolment, **and step-up before a payment method is changed** | CONFIRMED — blueprint §3; `CP-02` |
| `BR-CWP-057` | The method is a token; there is no card number to protect, but the destination of money is | CONFIRMED — blueprint `P25` |
| `BR-CWP-035` | Ten-minute code, single use | CONFIRMED — `CP-02` |

**3 · Test Cases**

| TC | Scenario | Expected |
|---|---|---|
| TC-1 | Add a method with a fresh code | Accepted, and an audit entry names the actor |
| TC-2 · **negative** | Add a method **without** a code | Refused at the endpoint |
| TC-3 · **negative** | Reuse the code from sign-in ten minutes earlier | Refused. ⚠ **Step-up needs its own code**, not the session's |
| TC-4 · **negative** | Remove a method with an expired code | Refused |
| TC-5 · **negative** | An **invited helper** adds a method | Permitted only for **their own** method, never the holder's — assert on `portal_delegate.permissions` |
| TC-6 · **tenant isolation** | A code issued on Pine Hill used on `/oak-ridge` | Refused |
| TC-7 | The audit entry after a delegate acts | Names the **delegate**, not the account holder |

**4 · Test Data** — Existing methods `Chase ••••4021` (bank, verified) and `Visa
••••8812` (card, expires 11/27). Delegate *Kestrel Bookkeeping*,
`accounts@kestrel.example`, permissions `see`, `download`.

**5 · Data Fields / Mapping**

| Field | Screen | Source | DB target | Type | Origin | Validation |
|---|---|---|---|---|---|---|
| Step-up code | CWP-039 | prototype-extracted | short-lived store | text | system-derived | Own code, ten minutes, single use |
| Actor | — | hard rule 7 | `audit_log.portal_actor_id`, `portal_actor_label` | uuid, text | system-derived | ⚠ The delegate's name where one acted |

**6 · Acceptance** — **Given** a signed-in customer, **when** they add or remove a stored
payment method, **then** a fresh code is required, the session's own code will not do,
and the audit entry names whoever actually acted.

**7 · Finance Calculation** — N/A.

**8 · Open Questions** — None. ⚠ Blocked only by rails: there is nothing to store until
`CP-08` lands.
