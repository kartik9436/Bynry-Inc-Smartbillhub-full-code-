# EP-FLD-01 — Getting in — splash, sign in, activation, the shared handset and the security underneath

**Module:** field-app (`18-field-app`, module code FLD) · **Wave:** 0, 2 · **Design tasks:** T-15 (FF-01–FF-08), T-12 · **Screens:** FF-05, FF-09, FF-53, FF-01, FF-02, FF-03, FF-04, FF-06, FF-56, FF-57, FF-51 · **Status:** draft (2026-10-21, `CR-187-BRC10`)

## Scope

**In:** the design's flow group *FF-01 to FF-08, FF-53, FF-56, FF-57* and the requirements whose screens sit in it — US-FLD-003 (requirement 3), US-FLD-032 (requirement 32), US-FLD-070 (requirement 70), US-FLD-080 (requirement 80).

**Out:** everything the design's *Scope · Out* list excludes (`01-overview.md` §5) — taking payment on site, linear assets, inspection rounds, offline maps, a dispatcher app, live crew tracking, van stock-takes, customer-facing features, a watch app.

**Source:** the *SMART360 Next Field App* design canvas, version of 2026-10-21. The screens are the images in `../wireframes/` and they are the specification (B14 rule 42; PO 2026-10-21, *"please ensure all native app screens are build using images not using text or contents"*). Figures on a board are illustrations (B14 rule 37) and are used below as test data only.

⚠ **1 of these stories is `blocked`** — US-FLD-080 — each on a collision between the design and a rule already signed in this repository, named in plain words in its §8. The open-questions lane (DOC-C) mints the `OQ-FLD-` id; until then `blocked_by` is empty and the gap is the comment beside it.

## Capability matrix (list screens only — B9 conformance)

No list screen in this group.

## Stories

---
id: US-FLD-003
epic: EP-FLD-01
module: field-app
screens: [FF-05, FF-09, FF-53]
wave: 0
status: ready
blocked_by: []
depends_on: [US-FLD-004]
journeys: []           # the E2E-nn cases cited in §3 become journeys under 08-qa/01-e2e/journeys/ (sibling lane)
rules: [BR-FLD-00025, BR-FLD-00060, BR-FLD-00064, BR-FLD-00114, BR-FLD-00132, BR-FLD-00133, BR-FLD-00134]
golden_tests: []
finance_calc: none
---
### US-FLD-003 — One handset, several technicians in turn — unsent work stays with whoever captured it

**Requirement 3, in the design's words:** *Shared device — several technicians on one handset across shifts without mixing records. Unsent work and photos survive logout and stay attached to the technician who captured them* — section A · The original brief · standing *Engine built*.

**1 · Details** — As **D. Ortiz handing the van tablet to M. Chen at 16:00**, I want **my 3 jobs and 38 photographs to stay on the handset and send under my name**, so that **neither of us is credited with, or can see, the other's work**. The drawer's *Switch technician* (also drawn on its own as `wireframes/phone/Switch.png`) and FF-53 *Sign out* both say how much is unsent and delete nothing. Every work table carries `technician_id NOT NULL` and every scoped read goes through one helper (R132, R133); the sync watermark is per technician per table (R134).

**Screens (build from the images — B14 rules 42, 44, 45):** `FF-05` Sign in — [phone](../wireframes/phone/FF-05-sign-in.png) · [tablet](../wireframes/tablet/FF-05-T-sign-in.png)<br>`FF-09` Menu — [phone](../wireframes/phone/FF-09-menu.png) · [tablet](../wireframes/tablet/FF-09-T-the-sidebar.png)<br>`FF-53` Sign out — [phone](../wireframes/phone/FF-53-sign-out.png) · [tablet](../wireframes/tablet/FF-53-T-sign-out.png)

**2 · Business Rules**

| BR | R | Statement (first sentence, verbatim — the whole rule is in `02-business-rules.md`) | Status |
|---|---|---|---|
| `BR-FLD-00025` | R25 | Unsent work stays with the technician who captured it, through a logout and a handover. | CONFIRMED — repo `BR-WRK-060` |
| `BR-FLD-00060` | R60 | Nothing unsent is ever purged — at any age, under any sign-in, including another technician's work. | CONFIRMED (PO) |
| `BR-FLD-00064` | R64 | A sign-out deletes nothing. | CONFIRMED (PO) |
| `BR-FLD-00114` | R114 | Every local table carries tenant_id and every query names it — the handset's equivalent of the server's forced row-level security. | CONFIRMED — repo `BR-WRK-059` |
| `BR-FLD-00132` | R132 | technician_id NOT NULL on the ten tables that hold work; ownership is stored, never inferred from who is signed in. | CONFIRMED (PO) |
| `BR-FLD-00133` | R133 | Every read of a scoped table goes through one helper, and a test fails any statement that bypasses it. | CONFIRMED (PO) |
| `BR-FLD-00134` | R134 | The sync watermark is per technician per table, and the pair is the key. | CONFIRMED (PO) |

**3 · Test Cases**

| TC | Scenario | Expected |
|---|---|---|
| TC-1 | E2E-21: Dana signs out at 15:00 with 62 items and 38 photographs unsent; Marco signs in, captures 31 items on four jobs, signs out; the handset reaches depot wi-fi signed in as nobody | All 93 items send — Dana's 62 under Dana, Marco's 31 under Marco; the office sees two timesheets, not one |
| TC-2 | Marco signs in after Dana | Today shows Marco's day only; none of Dana's jobs, customers or search results appear (R132, `search_index` is built from scoped rows) |
| TC-3 · **negative** | A query in `db/queries/` reads `work_order` without the scoping helper | The query-layer test fails naming the statement (R133) |
| TC-4 · **negative** | Marco's pull runs after Dana's and the cursor is per table only | Not possible — `sync_state` is keyed (technician, table); Dana's cursor does not move (R134) |
| TC-5 | Dana taps *Sign out anyway* on FF-53 | Nothing is deleted (R64); the sheet read *3 jobs and 38 photos to send · They stay on this phone and send under your name* |
| TC-6 · **tenant isolation** | R. Patel works for Silver Creek Water and Lone Star Water and signs in to Lone Star Water on the same handset | Only `field-lone-star-water.sqlite` is opened; not one Silver Creek row is readable (R131), and the server takes the tenant from the credential, never from the payload (R127) |

**4 · Test Data** — Silver Creek Water · D. Ortiz (Water II, employee) · M. Chen (Evening 16:00–00:30) · R. Patel (contractor, Apex Utilities) · 62 items + 38 photos unsent for Dana.

**5 · Data Fields / Mapping**

| Field | Screen | Spec source | DB target | Type/unit | Origin | Validation |
|---|---|---|---|---|---|---|
| technician_id | all | Data.txt §2 | handset `work_order` … `crew_time` (10 tables) | text, NOT NULL | system-derived | never inferred from the session (R132) |
| captured_by | all | Data.txt §2 | handset `outbox.captured_by` → server `work_sync_receipts.captured_by_technician_id` | text | system-derived | written from the capture credential (R114) |
| sync cursor | FF-50 | Data.txt §2 | handset `sync_state` (technician_id, table) | text | system-derived | the pair is the key (R134) |

**6 · Acceptance** — **Given** two technicians use one handset in turn with unsent work, **when** the handset next reaches a signal, **then** each item reaches the server under the technician who captured it, and neither saw the other's work as their own.

**7 · Finance Calculation** — N/A.

**8 · Open Questions** — None.

---

---
id: US-FLD-032
epic: EP-FLD-01
module: field-app
screens: [FF-01, FF-02, FF-03, FF-04, FF-05, FF-06, FF-53]
wave: 2
status: ready
blocked_by: []
depends_on: [US-FLD-070, US-FLD-080]
journeys: []           # the E2E-nn cases cited in §3 become journeys under 08-qa/01-e2e/journeys/ (sibling lane)
rules: [BR-FLD-00038, BR-FLD-00040, BR-FLD-00064, BR-FLD-00105]
golden_tests: []
finance_calc: none
---
### US-FLD-032 — Splash, three intro screens, sign in, forgot password and sign out

**Requirement 32, in the design's words:** *Splash and three intro screens, sign in, forgot password, sign out* — section F · Getting in, and the field conditions · standing *New*.

**1 · Details** — As **a technician opening the app for the day**, I want **a splash with the utility's name and the build, three intro screens I can skip, a sign-in, a way back in when I am locked out and a sign-out that keeps my work**, so that **getting in costs seconds and getting out loses nothing**. FF-06 *Forgot password* has no input box at all — it offers *Text me a code*, *Call the office* or *Ask the office to reset* (R38). FF-05 tells a technician when someone else's work is waiting on the handset (*R. Patel has 2 jobs to send. They send under their name.*).

**Screens (build from the images — B14 rules 42, 44, 45):** `FF-01` Splash — [phone](../wireframes/phone/FF-01-splash.png) · [tablet](../wireframes/tablet/FF-01-T-splash.png)<br>`FF-02` Intro 1 — [phone](../wireframes/phone/FF-02-intro-1.png) · [tablet](../wireframes/tablet/FF-02-T-intro-1.png)<br>`FF-03` Intro 2 — [phone](../wireframes/phone/FF-03-intro-2.png) · [tablet](../wireframes/tablet/FF-03-T-intro-2.png)<br>`FF-04` Intro 3 — [phone](../wireframes/phone/FF-04-intro-3.png) · [tablet](../wireframes/tablet/FF-04-T-intro-3.png)<br>`FF-05` Sign in — [phone](../wireframes/phone/FF-05-sign-in.png) · [tablet](../wireframes/tablet/FF-05-T-sign-in.png)<br>`FF-06` Forgot password — [phone](../wireframes/phone/FF-06-forgot-password.png) · [tablet](../wireframes/tablet/FF-06-T-forgot-password.png)<br>`FF-53` Sign out — [phone](../wireframes/phone/FF-53-sign-out.png) · [tablet](../wireframes/tablet/FF-53-T-sign-out.png)

**2 · Business Rules**

| BR | R | Statement (first sentence, verbatim — the whole rule is in `02-business-rules.md`) | Status |
|---|---|---|---|
| `BR-FLD-00038` | R38 | A technician taps, never types. | CONFIRMED (PO) |
| `BR-FLD-00040` | R40 | The app version is on screen, so a defect report can name a build | CONFIRMED (PO) |
| `BR-FLD-00064` | R64 | A sign-out deletes nothing. | CONFIRMED (PO) |
| `BR-FLD-00105` | R105 | A technician never self-registers. | CONFIRMED (PO) |

**3 · Test Cases**

| TC | Scenario | Expected |
|---|---|---|
| TC-1 | Open the app cold | FF-01 shows *Silver Creek Water* and *2.587.0 · build 412* (R40); the intro screens follow, each with *Skip* |
| TC-2 | FF-06, the technician is locked out | Three choices on screen and no keyboard; the masked number reads *(512) 555-••42* |
| TC-3 | FF-05 with R. Patel's 2 jobs unsent on the handset | The banner names R. Patel and says they send under his name (R25, R64) |
| TC-4 · **negative** | A technician with no account on the server tries to sign up from FF-05 | There is no sign-up; the only way in for a new person is *Activate your account* (FF-56) with an office code (R105) |
| TC-5 | FF-53 sign out with 3 jobs and 38 photos unsent | The sheet states both numbers; *Sign out anyway* deletes nothing (R64) |
| TC-6 · **tenant isolation** | R. Patel works for Silver Creek Water and Lone Star Water and signs in to Lone Star Water on the same handset | Only `field-lone-star-water.sqlite` is opened; not one Silver Creek row is readable (R131), and the server takes the tenant from the credential, never from the payload (R127) |

**4 · Test Data** — Silver Creek Water · technician ID for D. Ortiz · office (512) 555-0100 · build 2.587.0 · 412.

**5 · Data Fields / Mapping**

| Field | Screen | Spec source | DB target | Type/unit | Origin | Validation |
|---|---|---|---|---|---|---|
| version and build | FF-01, FF-05 | R40 | app bundle (one product version, own store build number) | text | system-derived | always visible |
| technician id + password | FF-05 | FF-05 board | `POST` device sign-in (server, identity) | text | user-input | server decides; never stored in plain text |

**6 · Acceptance** — **Given** a technician with an account, **when** they open the app, sign in and later sign out, **then** they reach their day without typing more than their credentials, and signing out deletes nothing.

**7 · Finance Calculation** — N/A.

**8 · Open Questions** — None.

---

---
id: US-FLD-070
epic: EP-FLD-01
module: field-app
screens: [FF-56, FF-57]
wave: 2
status: ready
blocked_by: []
depends_on: [US-FLD-080]
journeys: []           # the E2E-nn cases cited in §3 become journeys under 08-qa/01-e2e/journeys/ (sibling lane)
rules: [BR-FLD-00105, BR-FLD-00037]
golden_tests: []
finance_calc: none
---
### US-FLD-070 — Activate an account the office created — a six-character code, my own password, this device by name

**Requirement 70, in the design's words:** *A technician activates an account the office created — a six-character code good for seven days, their own password, and the device registered by name. Technicians never self-register; this claims an account that already exists* — section K · The seven asks of 2026-10-20 · standing *Ruled*.

**1 · Details** — As **Dana on her first morning**, I want **to claim the account the office made for me with the code they sent**, so that **I never self-register and the office knows which device I use**. FF-56 takes a six-character code good for seven days and the work email; FF-57 sets the password and registers the device by name (*Van 14 tablet*), which the office can sign out remotely (R105).

⚠ **THE CODE NAMES THE UTILITY — AS BUILT 2026-10-24 (`DEF-FLD-10580`, beta report MQ-006).** PO, verbatim: *"A. The code from the office sets the utility (recommended) - this is correct option , but how will you ensure the code is always unique?"* The field app is **one build for every utility**; nothing in a build names one (until that day the preview build carried `EXPO_PUBLIC_TENANT=brookfield-municipal-utilities`, so a second utility's technician could not get in). The flow:

1. **Where the office gets the code.** Staff portal **Settings › Users**: adding a person with the *Field technician* role shows the *Phone app code* once; **New app code** on the person's row issues a fresh one and voids the old (`POST /api/{tenant}/users/{id}/activation-code`, System Admin only). The code is shown once and never again.
2. **FF-56, the code.** As soon as six characters are typed the phone calls `POST /api/auth/activation/lookup {code}` — **no utility in the path**, the device id in an `X-Device-Id` header — and the server answers `{tenant, utility_name}` for a live code. The utility's name appears under the code box (*For City of Houston*), so a technician holding another utility's code sees it before going on.
3. **FF-56, the person.** *Check the code* runs the existing check (`POST /api/{tenant}/auth/activation/check`, code + work email or phone) at THAT utility.
4. **FF-57.** The password is set at that utility (`…/auth/activation/complete`), and the handset **remembers the utility and the email** (encrypted preferences, `field-app/src/security/handsetUtility.ts`).
5. **FF-05 from then on** says *Signing in to City of Houston · Change*, with the email pre-filled. *Change* goes back to FF-56 for another utility's code. A handset that knows no utility says *Activate this phone first.* and *Sign in* stays off.

**Uniqueness** (the PO's question, answered in the decision log of 2026-10-24 and confirmed): codes are drawn at random from 31 unambiguous characters (31⁶ ≈ 887 million); every code ever issued is recorded in ONE platform register (`identity.activation_code_register`) with a **database UNIQUE constraint** on a keyed hash of the code, so a draw that lands on a code any utility has ever held is refused by the database and redrawn — neither office sees the clash. A code is never reused, even after it expires or is used. **Guessing** is held off by the seven-day life, single use, a **platform-wide** limit on the utility-free door per network address and per device (`ACTIVATION_LOOKUP_MAX_TRIES` per `ACTIVATION_LOOKUP_WINDOW_S`, seed 10 per 15 minutes — no utility's setting can apply before the code names the utility), and, once it has, that utility's own Settings › Security lockout count on wrong emails against the code.

**Screens (build from the images — B14 rules 42, 44, 45):** `FF-56` Activate — [phone](../wireframes/phone/FF-56-activate.png) · [tablet](../wireframes/tablet/FF-56-T-activate.png)<br>`FF-57` Your password — [phone](../wireframes/phone/FF-57-your-password.png) · [tablet](../wireframes/tablet/FF-57-T-your-password.png)

**2 · Business Rules**

| BR | R | Statement (first sentence, verbatim — the whole rule is in `02-business-rules.md`) | Status |
|---|---|---|---|
| `BR-FLD-00105` | R105 | A technician never self-registers. | CONFIRMED (PO) |
| `BR-FLD-00037` | R37 | On-screen text is capped by what it is for — a label at 3 words, a fact at 6, a consequence at 6 per sentence and at most two. | CONFIRMED — repo rule |

**3 · Test Cases**

| TC | Scenario | Expected |
|---|---|---|
| TC-1 | Dana enters `K7M2••` and her work email within seven days | FF-57 opens with *Code accepted* and her name, role and utility |
| TC-2 · **negative** | The code is eight days old | Refused; FF-56 offers *Ring dispatch* for a new one — no account is created from the handset |
| TC-3 · **negative** | A person with no office-created account enters any code | Refused — the screen claims an account that exists, it never creates one (R105) |
| TC-4 | Dana chooses a 12-character password and types it twice | Signed in; the device is registered as *Van 14 tablet* and the office can see it |
| TC-5 · **negative** | The two password entries differ | Not saved; the second field says so |
| TC-6 · **tenant isolation** | R. Patel works for Silver Creek Water and Lone Star Water and signs in to Lone Star Water on the same handset | Only `field-lone-star-water.sqlite` is opened; not one Silver Creek row is readable (R131), and the server takes the tenant from the credential, never from the payload (R127) |
| TC-7 · `DEF-FLD-10580` | Houston and Brookfield technicians install the SAME build; each types their office's code | Each lands at their own utility; FF-05 then says *Signing in to <utility> · Change* with their email pre-filled |
| TC-8 · **negative** · `DEF-FLD-10580` | Brookfield's random draw lands on `K7QM2P`, which Houston already holds | The database refuses it and Brookfield's admin is shown another code (`P3XW9A`); a code is never issued twice, even after it is void |
| TC-9 · **negative** · `DEF-FLD-10580` | A Houston handset is given a Brookfield code | FF-56 shows *For Brookfield Municipal Utilities* before anything is claimed; nothing moves until the password is set |
| TC-10 · **negative** · `DEF-FLD-10580` | A wrong, expired or used code; then eleven tries in fifteen minutes from one phone or one address | The one refusal, naming no utility; then refused for the window (`429`) |
| TC-11 · `DEF-FLD-10580` | A fresh handset, nobody activated | FF-05 says *Activate this phone first.*; *Sign in* stays off |

Tests: `06-backend/tests/test_def_fld_10580_activation_lookup.py` (+ `_pg.py`, PostgreSQL 16) · `field-app/tests/screens/gettingIn/utilityFromCode.test.tsx`.

**4 · Test Data** — Code `K7M2••` (six characters, seven days) · Dana Ortiz · Field Technician · device name *Van 14 tablet*. `DEF-FLD-10580`: `K7QM2P` (City of Houston) · `P3XW9A` (Brookfield Municipal Utilities).

**5 · Data Fields / Mapping**

| Field | Screen | Spec source | DB target | Type/unit | Origin | Validation |
|---|---|---|---|---|---|---|
| activation code | FF-56 | requirement 70 | server identity (office-issued, expiring) | 6 chars | user-input | expires after 7 days |
| device name | FF-57 | requirement 70 | server device register | text | user-input | listed in the back office; remote sign-out (R105) |

**6 · Acceptance** — **Given** the office created Dana's account and sent a code, **when** she enters it and sets a password on her handset, **then** her account is claimed, the device is registered by name, and nothing was self-registered.

**7 · Finance Calculation** — N/A.

**8 · Open Questions** — None.

---

---
id: US-FLD-080
epic: EP-FLD-01
module: field-app
screens: [FF-05, FF-56, FF-57, FF-53, FF-51]
wave: 0
status: blocked
blocked_by: []          # the gap is named in §8; its OQ-FLD id is minted by the open-questions lane (DOC-C) and filled in here
depends_on: [US-FLD-003]
journeys: []           # the E2E-nn cases cited in §3 become journeys under 08-qa/01-e2e/journeys/ (sibling lane)
rules: [BR-FLD-00113, BR-FLD-00114, BR-FLD-00115, BR-FLD-00127, BR-FLD-00131]
golden_tests: []
finance_calc: none
---
### US-FLD-080 — Security that never stops capture — two credentials, encryption at rest, scoping on the handset, device registration, auto-lock

**Requirement 80, in the design's words:** *Security as a first-class concern — and the one that decides whether the app works: a token expiring mid-shift must never stop a technician capturing. Two credentials, encryption at rest, tenant scoping on the handset, device registration, auto-lock* — section L · The nine of 2026-10-21 · standing *New*.

**1 · Details** — As **Dana, signed in at 07:30 and driving into a valley**, I want **my token expiring at 08:30 not to stop me capturing nine more hours of work**, so that **an auth problem can never cost a day**. Two credentials: a one-hour access token for the server and a device-bound 36-hour capture credential for the local store; expiry blocks SENDING only (R113). A remote sign-out drops the mirror and keeps the outbox (R115). The tenant is the database file (R131) and is resolved on the server from the credential (R127).

**Screens (build from the images — B14 rules 42, 44, 45):** `FF-05` Sign in — [phone](../wireframes/phone/FF-05-sign-in.png) · [tablet](../wireframes/tablet/FF-05-T-sign-in.png)<br>`FF-56` Activate — [phone](../wireframes/phone/FF-56-activate.png) · [tablet](../wireframes/tablet/FF-56-T-activate.png)<br>`FF-57` Your password — [phone](../wireframes/phone/FF-57-your-password.png) · [tablet](../wireframes/tablet/FF-57-T-your-password.png)<br>`FF-53` Sign out — [phone](../wireframes/phone/FF-53-sign-out.png) · [tablet](../wireframes/tablet/FF-53-T-sign-out.png)<br>`FF-51` Settings — [phone](../wireframes/phone/FF-51-settings.png) · [tablet](../wireframes/tablet/FF-51-T-settings.png)

**2 · Business Rules**

| BR | R | Statement (first sentence, verbatim — the whole rule is in `02-business-rules.md`) | Status |
|---|---|---|---|
| `BR-FLD-00113` | R113 | A token that expires mid-shift never stops a technician capturing. | DERIVED (decision log T-05) |
| `BR-FLD-00114` | R114 | Every local table carries tenant_id and every query names it — the handset's equivalent of the server's forced row-level security. | CONFIRMED — repo `BR-WRK-059` |
| `BR-FLD-00115` | R115 | A remote sign-out drops the mirror and keeps the outbox. | DERIVED (decision log T-05) |
| `BR-FLD-00127` | R127 | The tenant is resolved from the credential and never read from the payload. | DERIVED (decision log T-05) |
| `BR-FLD-00131` | R131 | On the handset the tenant is the database FILE, never a column. | CONFIRMED (PO) |

**3 · Test Cases**

| TC | Scenario | Expected |
|---|---|---|
| TC-1 | Access token expires at 08:30, no signal | Capture continues; the outbox fills; sending waits — no state discards captured work (R113) |
| TC-2 | Signal returns, access token expired, capture credential valid | The app re-authenticates and sends; items carry `captured_by` from the capture credential (R114) |
| TC-3 | The office signs the device out remotely while 40 items are unsent | The mirror is dropped; the 40 outbox items send on next contact and then go (R115) |
| TC-4 · **negative** | A request body carries a `tenant_id` for another utility | Ignored — the tenant comes from the credential (R127) |
| TC-5 · **negative** | The capture credential's lifetime | **Blocked:** the design says 36 hours (R113) and the signed `BR-WRK-060` says the capture token outlives sign-out by seven days — see §8 |
| TC-6 · **tenant isolation** | R. Patel works for Silver Creek Water and Lone Star Water and signs in to Lone Star Water on the same handset | Only `field-lone-star-water.sqlite` is opened; not one Silver Creek row is readable (R131), and the server takes the tenant from the credential, never from the payload (R127) |

**4 · Test Data** — Dana signs in 07:30; access token 1 hour; capture credential 36 hours (design) / seven days (signed); 40 unsent items at remote sign-out.

**5 · Data Fields / Mapping**

| Field | Screen | Spec source | DB target | Type/unit | Origin | Validation |
|---|---|---|---|---|---|---|
| access token | — | R113 | secure store (expo-secure-store) | token, 1 h | integration | server only |
| capture credential | — | R113 | secure store; stamped on every outbox row | token | integration | device-bound; see §8 |
| database file | — | R131 | `field-<tenant>.sqlite` | file | system-derived | chosen at sign-in |

**6 · Acceptance** — **Given** a technician whose server token expires mid-shift, **when** they keep working offline, **then** every capture is stored and later sent under their name, and nothing is discarded to resolve authentication.

**7 · Finance Calculation** — N/A.

**8 · Open Questions**

| OQ-ID | Question | Blocks | Routed to | Status |
|---|---|---|---|---|
| *to be minted by DOC-C* | The capture credential's lifetime: the design's R113 says 36 hours; the signed rule `BR-WRK-060` (PO 2026-10-04) says the capture token outlives sign-out by seven days. Which one the native app uses is a collision with a signed rule, so it goes to the PO. | the test case marked **Blocked** in §3 | Product Owner (a collision with a signed rule — law 13) | OPEN — not yet in the register |
