# EP-WRK-04 — Workforce and roles: crews, technicians and their skills; the certification watch; who may accept; a login scoped to a phone

**Module:** work · **Wave:** phase **2** of `CR-070` · **Screens:** `Work-023` · `Work-024` · `Work-007` · `Work-009` · `Work-003` · `Work-010`–`012` · **Status:** draft (`CR-070`, 2026-09-03; §15–§21 unread)

## Scope

**In:** `WM-13` crews, technicians, technician skills · `WM-21` the crews screen, technician detail and the skills wizard · `WM-26` a Work permission — who may accept · `WM-31` a Field technician role scoped to Work on mobile only.

**Out:** assignment (`EP-WRK-05`) · labour rates, which are per ROLE and live with costing (`EP-WRK-10`).

⚠ **ALL THREE QUESTIONS THIS EPIC WAS BLOCKED ON WERE RULED ON 2026-09-04, AND NOTHING HERE IS STUBBED.** `OQ-WRK-1492` (who may accept) — *"clark can do it sicne it s a day to day work"*; `OQ-WRK-1494` (one login, one surface) — option (a), a scope on the user, one `users` table; `OQ-WRK-1493` (block or warn) — option (c), per-tenant defaulting to warn. **The two live gaps the blueprint named are closed:** a technician who signs into the web app is now refused by name, and the endpoint that approves a job now asks a permission. ⚠ **`10-execution-plan.md`'s wave F still reads *"each to its boundary"* and names three `NotImplementedError` stubs** — it was written on 2026-09-03, one day before the rulings, and r11 step 0 is what caught it.

**Blueprint §4:** *"Crews & technicians — MISSING. Nothing anywhere. No crew table, no technician profile, no skills-per-person, no certifications-per-person, no availability."* `tenancy.CertificationType` exists as a lookup *"linked to nobody"*.

## Capability matrix (list screens only — B9 conformance)

| Screen | Search fields | Filters | Default sort | Sortable | Columns default/available | Row actions | Bulk actions | Export |
|---|---|---|---|---|---|---|---|---|
| `Work-023` Crews | technicians, skills | role · status | name | Technician · Role · Utilisation | Technician · Role · Skills · Certifications · Shift · Today · Utilisation · Status | 👁 · ✎ | — | — |
| `Work-024` Technician detail · Jobs tab | — | status | due | Due · Status | Order · Type · Premise · Due · Status | 👁 | — | — |

## Stories

---
id: US-WRK-020
epic: EP-WRK-04
module: work
screens: [Work-023, Work-007]
wave: 2
status: ready
blocked_by: []
depends_on: [US-WRK-009]
journeys: [J62, J63]
rules: [BR-WRK-028, BR-WRK-029]
golden_tests: []
finance_calc: none
---
### US-WRK-020 — Crews, technicians and their skills: a profile beside an identity, never a second identity (`WM-13`)

**1 · Details** — As **a supervisor**, I want **to add D. Ortiz to Crew A with the Meter-fitting skill**, so that **D. Ortiz appears in the Technician filter beside M. Chen, R. Patel and Crew B**.

`crews`, `technicians` (*"a profile beside an existing identity.User, not a second identity"*), `technician_skills`. **A crew and a contractor are rows in the same table as a person** — *"Whoever the work is offered to, the skill match is the same test."* The account itself is created in Settings → Team; Work assigns what they can do.

**2 · Business Rules**

| BR | Statement | Status |
|---|---|---|
| `BR-WRK-028` | A technician is a profile beside `identity.User`; crew and contractor rows share the table | CONFIRMED — `WM-13`, `WS-23`, `WS-24` |
| `BR-WRK-029` | Dispatch offers only a skill match | CONFIRMED — `WS-23` |
| `BR-WRK-030` | Lapsed certification: block or warn is OPEN | OPEN — `OQ-WRK-1493` |

**3 · Test Cases**

| TC | Scenario | Expected |
|---|---|---|
| TC-1 | Add D. Ortiz (an existing `identity.User`) to Crew A with *Meter fitting* | A `technicians` row pointing at the user; a `technician_skills` row; D. Ortiz appears in `Work-007`'s Technician filter |
| TC-2 · **negative** | Create a technician for an email with no `identity.User` | Refused — *"Technicians are invited in Settings → Team"*; the refusal routes there |
| TC-3 | Add Crew B (3) and Apex Utility Svc (contractor) | Two rows in the same table, `kind` = crew · contractor; both offered by the same skill test |
| TC-4 · **negative** | Offer *Meter exchange — residential* (skill Meter fitting) to R. Patel (Water I · Reads) | Not offered; the picker lists D. Ortiz and M. Chen only |
| TC-5 · **negative** | Delete a technician with assigned jobs | Refused; *Set unavailable* offered |
| TC-6 · **tenant isolation** | Lone Star Ridge's Technician filter | Its own technicians; D. Ortiz absent |
| TC-7 | Shift and utilisation | *07:00–16:00 · 4 today · 82%* — utilisation is booked estimate over shift length, computed, never stored |

**4 · Test Data** — Six rows of `WS-23`: D. Ortiz Field technician · Water II · Meter I · Confined space · 07:00–16:00 · 4 · 82% · On shift · M. Chen · Electric I · Reads · HV awareness · 5 · 91% · R. Patel Senior · Water I · Reads · Backflow · First aid · 5 · 88% · J. Kaur · Water I · Confined space · 09:00–18:00 · 2 · 44% · Off today · Crew B (3) Network crew · Water III · Excavation · Traffic control · 1 · 70% · Apex Utility Svc Contractor · Water II · — · by arrangement · 2 · — . ⚠ `WM-13`'s example gives D. Ortiz *Meter-fitting*; `WS-23` gives *Water II · Meter I* — recorded in `03-field-map.md` §5; the fixture carries both skills.

**5 · Data Fields / Mapping**

| Field | Screen | Spec source | DB target (B2) | Type/unit | Origin | Validation |
|---|---|---|---|---|---|---|
| crew | `Work-023` | `WM-13` | `crews` (name · kind ∈ {crew, contractor} · headcount · shift_start · shift_end) | row | user-input | — |
| technician | `Work-023` | `WM-13` | `technicians` (user_id FK → `identity.users` · role_label · shift_start · shift_end · van · status) | row | user-input | `user_id` unique per tenant; cross-module FK, reviewed set |
| skills | `Work-024` | `WM-13` | `technician_skills` (technician_id · skill_id · proficiency ∈ {trained, certified}) | rows | user-input | skill from `work_skills` |
| utilisation | `Work-023` | `WS-23` | computed | % | computed-display | booked minutes ÷ shift minutes |

**6 · Acceptance** — **Given** D. Ortiz has a login, **when** a supervisor adds them to Crew A with Meter fitting, **then** the dispatcher's Technician filter lists them and a meter-exchange job may be offered to them — **and** a job needing a skill they lack is not.

**7 · Finance Calculation** — N/A. (Rates are per role — `US-WRK-051`.)

**8 · Open Questions** — None new; `OQ-WRK-1493` sits with `US-WRK-021`.

---
id: US-WRK-021
epic: EP-WRK-04
module: work
screens: [Work-023, Work-024]
wave: 2
status: ready       # OQ-WRK-1493 ruled 2026-09-04 — per-tenant, default warn; BOTH sides built
blocked_by: []
depends_on: [US-WRK-020]
journeys: [J62]
rules: [BR-WRK-030]
golden_tests: []
finance_calc: none
---
### US-WRK-021 — The crews screen, the technician detail and the three-step skills wizard; the certification watch shows an expiry and blocks nothing until ruled (`WM-21`)

**1 · Details** — As **a supervisor**, I want **to see who can do what and when a certification lapses**, so that **an expiry is an eligibility change I see here and not on a failed dispatch**.

`Work-023` lists the people, the crew and the contractor with the **certification watch**: *30 days — J. Kaur, confined space expires Aug 20* · *60 days — M. Chen, HV awareness expires Sep 2026*. `Work-024` — Overview · Jobs · Certifications · Audit — with **SKILLS & PROFICIENCY** (*Water I · Certified · Leak investigation · service connection · disconnects* · *Reads · Trained* · ***Water II · Not held*** · Main repair) and the **skills wizard** reached from *Assign skills*: Select technician · Skills & certifications · Confirm & update. *"The Not held row matters as much as the two held ones: it tells a supervisor exactly which jobs a training course would unlock."*

⚠ **THE WIREFRAME AND THE CARD DISAGREED, THE DISAGREEMENT WAS THE QUESTION, AND THE ANSWER IS NEITHER OF THEM — RULED 2026-09-04.** `WS-23` draws *"She is blocked from 4 template types until renewed"*; `WM-21` says *"Certifications are captured here; refusing a job on a lapsed one is out of scope."* The Product Owner chose option (c): ***"(c) per-tenant, default warn"***. **So both sides are built and the utility's own setting picks one** — `work_settings.certification_lapse_policy`, Work's own table because Work writes nobody else's. A new tenant starts at *warn*, so a two-technician utility still sends J. Kaur out on 21 August; a utility with a safety officer switches blocking on and she is refused. **The sentence *blocked from N template types* is rendered ONLY where blocking is on** — a screen may not claim a guarantee the setting has switched off (hard-won law 1). **No `NotImplementedError` was ever written**: the ruling landed a day after this story was, and r11 step 0 is what caught it.

**2 · Business Rules**

| BR | Statement | Status |
|---|---|---|
| `BR-WRK-030` | Lapsed certification always SHOWN; block or warn is the tenant's setting, defaulting to warn | **CONFIRMED 2026-09-04** — `OQ-WRK-1493`, option (c) |
| `BR-WRK-028` | The account is Identity's, the capability Work's | CONFIRMED |
| B14 rules 3, 15 | The wizard uses the numbered rail; row actions are icons | CONFIRMED |

**3 · Test Cases**

| TC | Scenario | Expected |
|---|---|---|
| TC-1 | Open R. Patel, tick *Backflow* with expiry 2027-06-30, confirm | The expiry shows on their card beside the two backflow jobs already assigned |
| TC-2 | The watch on 2026-08-01 | *30 days — J. Kaur, confined space expires Aug 20*; *60 days — M. Chen, HV awareness expires Sep 2026* |
| TC-3 · **negative · stub** | Offer J. Kaur a job whose template names *Confined space* on Aug 21 | The offer is **not refused**; the eligibility check raises `NotImplementedError("OQ-WRK-1493")` in the one branch that would refuse, and the picker shows the expiry beside her name |
| TC-4 · **negative** | grep the watch's copy for *blocked from* | Zero hits until ruled — the sentence the wireframe draws is not rendered |
| TC-5 · **negative** | A certification with an expiry in the past at entry | Accepted with a warning — history is lawful; a refusal would lose the record |
| TC-6 · **tenant isolation** | Lone Star Ridge opens `/work/crews/r-patel` | `404` — the slug is per tenant |
| TC-7 | Certifications | Rows point at `tenancy.CertificationType` through the seam; Work adds the person and the date, never a second type list |

**4 · Test Data** — R. Patel: Water I Certified · Reads Trained · Water II Not held · Backflow tester exp Jan 2028 · First aid / CPR exp Sep 2027 · *Jobs closed 88 · First-visit completion 92% · Avg vs estimate −4 min* · Route 3 · North · Van Unit 12 (26 parts on board — ⚠ a stock figure; shown as a note, never a count, until `OQ-WRK-1490`). J. Kaur: Confined space expires **20 Aug 2026**.

**5 · Data Fields / Mapping**

| Field | Screen | Spec source | DB target (B2) | Type/unit | Origin | Validation |
|---|---|---|---|---|---|---|
| certification | `Work-024` | `WM-21` | `technician_certifications` (technician_id · certification_type_id FK → `tenancy.certification_types` · expires_on · evidence_document_id NULL) | rows | user-input | cross-module FK, reviewed set |
| watch window | `Work-023` | `WS-23` | computed: expiries within 30 / 60 days | list | computed-display | dates in words |
| eligibility refusal | picker | `WS-23` vs `WM-21`, ruled | `work_settings.certification_lapse_policy ∈ {warn, block}`, default `warn`; applied in `workforce.skill_match()` | enum | reference-data | one row per tenant; a tenant with no row reads the default |

**6 · Acceptance** — **Given** J. Kaur's confined-space certification expires on 20 August, **when** a supervisor opens Crews on 1 August, **then** the watch names her and the date — **and** nothing refuses her a job until the Product Owner says whether it should.

**7 · Finance Calculation** — N/A.

**8 · Open Questions**

| OQ | Question | Blocks | Routed to | Status |
|---|---|---|---|---|
| `OQ-WRK-1493` | Does a lapsed certification block dispatch or warn? | Nothing — **CLOSED 2026-09-04, option (c): per-tenant, default warn.** Both sides built; the sentence renders only where blocking is on | PO | **CLOSED** |

---
id: US-WRK-022
epic: EP-WRK-04
module: work
screens: [Work-009, Work-003]
wave: 2
status: ready       # was `blocked`; OQ-WRK-1492 ruled 2026-09-04 — a clerk may accept
blocked_by: []
depends_on: [US-WRK-003]
journeys: [J61]
rules: [BR-WRK-044]
golden_tests: []
finance_calc: none
---
### US-WRK-022 — A Work permission in the identity module: who may accept a work order (`WM-26`)

**1 · Details** — As **the utility**, I want **accepting a work order to be a named permission**, so that **the act that puts a gas light-up live is not available to anyone who can reach the endpoint**.

The blueprint's own sentence: *"Today anyone who can reach the endpoint can approve; there is no work permission in the identity module at all."* Identity has `billing_clerk`, `executive`, `payments_record`, `adjustment_approval`, `finance_reconcile_export` — nothing for field work. **This story adds the permission `work_accept`, declared in identity's catalogue and CHECKED in `accept_field_result`.** ⚠ **WHO HOLDS IT WAS RULED ON 2026-09-04 AND IS NOT STUBBED:** PO verbatim, *"clark can do it sicne it s a day to day work"* — accepting a finished job is ordinary daily work and must not queue behind a supervisor, because a two-person utility has none sitting by the screen. So the three OFFICE roles hold it (`identity/0005`) and the `field_technician` role holds nothing at all. ⚠ **AND OPTION (b)'s SECOND HALF — *a technician must never accept their own work* — NEEDS NO RULE OF ITS OWN:** `OQ-WRK-1494`, ruled the same day, keeps a technician's login off the web app entirely and the Accept control lives there. Building a second check for it would go stale the day the phone gains an approval screen. ⚠ **`work_accept` IS DELIBERATELY NOT AN A4 ROW** — `A4_MATRIX` transcribes a SIGNED grid verbatim (`BR-IDN-014`) and a tenth row would make the transcription untrue, so the permission is a real `permissions` row read by `identity_selectors.role_holds()`, and Settings › Users & roles still draws the nine signed rows. **That gap is written down rather than papered over** — putting it on that screen is a change to a signed artefact and belongs to identity's own story.

**2 · Business Rules**

| BR | Statement | Status |
|---|---|---|
| `BR-WRK-044` | A CLERK may accept — the office roles hold *accept field work* | **CONFIRMED 2026-09-04** — `OQ-WRK-1492` |
| `BR-SHL-025` | Once ruled, the button disables with reason AND the server refuses | CONFIRMED |
| `BR-MET-110` | A person accepts | CONFIRMED |

**3 · Test Cases**

| TC | Scenario | Expected |
|---|---|---|
| TC-1 | `accept_field_result` as a Billing Clerk | **Succeeds, and now because a RULE says so** rather than because nothing checks: `billing_clerk` holds `work_accept` |
| TC-2 | The catalogue | `work_accept` is declared in identity's permission catalogue with a plain-English label — *Accept field work* — and held by `system_admin`, `billing_clerk` and `executive` |
| TC-3 · **negative** | ⚠ **INVERTED BY THE RULING.** A test asserting a Billing Clerk is refused would now assert the OPPOSITE of the rule | Not written. What IS asserted is that `field_technician` holds ZERO permissions and that `may()` denies by default for an absent or unknown role |
| TC-4 · **negative** | grep `Work-003`'s copy for a permission sentence | Zero — no screen promises a restriction that does not exist |
| TC-5 · **tenant isolation** | A permission granted on Lone Star Ridge | Unseen by Brazos Bend — roles are per tenant already |

**4 · Test Data** — Actors: M. Torres (supervisor), Priya Menon (Billing Clerk). `WO-4906` awaiting approval.

**5 · Data Fields / Mapping**

| Field | Screen | Spec source | DB target (B2) | Type/unit | Origin | Validation |
|---|---|---|---|---|---|---|
| `work_accept` | — | `WM-26` | identity permission catalogue + `role_permissions` for the three office roles (`apps/identity` owns the write — Work asks, never writes) | code | reference-data | not an A4 row; read by `identity_selectors.role_holds()` |
| the check | `Work-003`, `Work-009` | `WM-26` | `accept_field_result` refuses with `AUTH-002` / `BR-WRK-044` when the role does not hold it | — | — | server-enforced whatever the screen disables (`BR-SHL-025`) |

**6 · Acceptance** — **Given** the permission is declared and held by the office roles, **when** a billing clerk accepts an order, **then** it succeeds because a rule says so — **and** a login that does not hold it is refused by the SERVER, not merely by a greyed-out button.

**7 · Finance Calculation** — N/A.

**8 · Open Questions**

| OQ | Question | Blocks | Routed to | Status |
|---|---|---|---|---|
| `OQ-WRK-1492` | Who may accept a work order? | Nothing — **CLOSED 2026-09-04:** *"clark can do it sicne it s a day to day work"*. The three office roles hold `work_accept`; a field technician is excluded by `BR-WRK-043`'s surface scope rather than by a second check | PO | **CLOSED** |

---
id: US-WRK-023
epic: EP-WRK-04
module: work
screens: [Work-010, Work-011, Work-012]
wave: 2
status: draft            # was `blocked`; OQ-WRK-1494 ruled 2026-09-04 — a surface scope on the user; one users table
blocked_by: []
depends_on: [US-WRK-020]
journeys: [J61, J62, J65]
rules: [BR-WRK-043]
golden_tests: []
finance_calc: none
---
### US-WRK-023 — A Field technician role, scoped to Work on mobile only — the first thing to build in stage A, and it waits on the access model (`WM-31`)

**1 · Details** — As **an admin**, I want **to invite T. Osei as a Field technician who signs into the phone and is refused on the web with *"This account is for the field app only"***, so that **a technician cannot reach everything a clerk can**.

r10's Users screen draws it: *D. Ortiz · FIELD TECHNICIAN · Work (mobile only) · Active* · *T. Osei · FIELD TECHNICIAN · Work (mobile only) · Invited*. *"'WORK (MOBILE ONLY)' IS A SCOPE NOTHING IN THE PRODUCT CAN EXPRESS"* — identity has no field role and *"no concept of a login that may use one surface and not another."* **This story adds the role value `field_technician`, the `users.surface_scope` column, and the WEB REFUSAL ITSELF — `OQ-WRK-1494` was ruled option (a) on 2026-09-04** and no stub was ever written. PO verbatim: *"Yes; Field technicians will not logn to web app; they will login to mobile app only; will you keep them in user table?"* ⚠ **THE QUESTION BACK IS ANSWERED BY US AND RECORDED RATHER THAN RE-ASKED (law 13): one `users` table, with a scope column** — a technician is invited, deactivated, password-reset and audited exactly like a clerk, and a second table would fork all four flows for one role. ⚠ **THE SENTENCE IS SIX WORDS, NOT r10's SEVEN:** *"This login is for the field app"* breaches B14 rule 33's five-or-six cap, so it ships as **“Sign in on the field app.”**

**2 · Business Rules**

| BR | Statement | Status |
|---|---|---|
| `BR-WRK-043` | Login scoped to Work on mobile only; the web sign-in is refused by name | **CONFIRMED 2026-09-04** — `OQ-WRK-1494`, option (a) |
| `BR-WRK-028` | The account is Identity's | CONFIRMED |
| B14 rule 33 | *"This account is for the field app only"* is seven words — **cut to six** when built: *"This login is for the field app"* | CONFIRMED |

**3 · Test Cases**

| TC | Scenario | Expected |
|---|---|---|
| TC-1 | Invite T. Osei as Field technician | A user with role `field_technician`, `surface_scope = mobile`, status Invited, shown on Settings → Users as *Work (mobile only)* |
| TC-2 | T. Osei signs into the web | **REFUSED** — `AUTH-002`, `BR-WRK-043`, *"Sign in on the field app."*; the attempt is audited as `auth.sign_in_wrong_surface`. ⚠ Named where every other sign-in failure is generic: the credentials were CORRECT, so `BR-IDN-002`'s no-oracle reason does not apply and a generic failure would send her to reset a password that works |
| TC-3 | The same credentials on the phone | **Accepted** — a refusal that also refused the phone would be a lockout, not a scope. And an existing `both` login is unaffected on either surface |
| TC-4 · **negative** | A Field technician calls `POST /payments` | `403` — the ordinary role catalogue already refuses; the new role holds no staff permission |
| TC-5 · **tenant isolation** | T. Osei's phone login on Lone Star Ridge | Refused — the user belongs to Brazos Bend |
| TC-6 | The phone's identity | `GET /work/mobile/today` resolves the technician profile from the user (`US-WRK-020`); a user with no profile gets an empty day and a sentence, never an error |

**4 · Test Data** — `dortiz@silvercreekwater.org` Active · `tosei@silvercreekwater.org` Invited (r10's own addresses; the fixture maps them onto Brazos Bend).

**5 · Data Fields / Mapping**

| Field | Screen | Spec source | DB target (B2) | Type/unit | Origin | Validation |
|---|---|---|---|---|---|---|
| role | Settings › Users | `WM-31` | identity role catalogue gains `field_technician` (identity owns the write) | enum | reference-data | holds no staff permission |
| surface scope | Settings › Users | `WM-31` | `users.surface_scope ∈ {web, mobile, both}` `[our column; §16 unread — the card names the scope, not the column]` | enum | user-input | default `both` for existing users |
| web refusal | sign-in | `WM-31` | `identity.services.sign_in(surface=…)` — the one place that knows which app a request came from | — | — | `AUTH-002` / `BR-WRK-043`, audited |

**6 · Acceptance** — **Given** T. Osei is invited as a Field technician, **when** they sign into the phone, **then** they see today's jobs — **and** the web refusal turns from xfail to green the day the access model is ruled.

**7 · Finance Calculation** — N/A.

**8 · Open Questions**

| OQ | Question | Blocks | Routed to | Status |
|---|---|---|---|---|
| `OQ-WRK-1494` | Is a Field technician's login web-blocked, and by what mechanism? | Nothing — **CLOSED 2026-09-04, option (a): a `surface_scope` column on `users`.** One table, not two; the refusal is six words | PO | **CLOSED** |
