# EP-CWP-12 — Published content and the back office

**Module:** tenancy (the staff app) + portal (the reads) · **Wave:** release 1 ·
**Screens:** CWP-011 · CWP-013 · CWP-014 · CWP-059 … CWP-062 · CWP-069 … CWP-075 ·
**Status:** draft

## Scope

**In:** the portal's settings and its address, branding, the help-answer store and where
customers meet it, tips, and service centres.

**Out:** everything the portal does with a signed-in customer.

⚠ **`CWP-069`–`CWP-075` ARE STAFF SCREENS.** They live in
`07-frontend/src/features/tenancy/` under **Settings → Configure → Customer portal**, plus
one card in **Reference data**. **A lane that builds them into the portal app has put a
staff screen behind a customer login.**

⚠ **NOT A TENTH TOP-LEVEL SETTINGS TAB.** Settings already carries **nine** — Company,
Users & roles, Services & UoM, Configure, Accounting, Notifications, Integrations,
Security, Billing plan. A tenth would widen the strip past the screen for something a
utility sets up once and then leaves alone. **The blueprint's earlier draft argued for a
tenth and its own §15 records the correction: it had miscounted five because four tabs
are declared through constants.**

⚠ **AND THE GATE IS WHAT MAKES THIS SAFE TO SHIP FIRST.** A utility that has written
nothing gets **no help page, no visit page and no tip slots** — not a portal full of empty
frames. *"An empty shell reads as a broken product rather than an honest one."*

## Capability matrix

| Screen | Search | Filters | Default sort | Sortable | Columns | Row actions | Bulk | Export |
|---|---|---|---|---|---|---|---|---|
| CWP-069 | — | — | — | — | — | — | — | QR code |
| CWP-071 | Answers | All · Published · Draft · Needs translating | Position (drag) | — | Question · Topic · Status · Languages · Read this month | Edit (icon) | — | — |
| CWP-073 | Tips | All · Showing now · Seasonal | Position (drag) | — | Tip · Where · When · Status | Edit · Preview · Remove (icons) | — | — |
| CWP-074 | — | — | Position | — | Centre · Open · Takes · You can · Status | Edit · Preview · Remove (icons) | — | — |

---
id: US-CWP-069
epic: EP-CWP-12
module: tenancy
screens: [CWP-069]
wave: 1
status: ready
blocked_by: []
depends_on: []
journeys: [J30, J31, J32, J33, J34]
rules: [BR-CWP-007]
golden_tests: []
finance_calc: none
---
### US-CWP-069 — Portal settings: the address a utility could never find, the switch, and the five

**1 · Details** — As **a System Admin**, I want **to see my portal's address and control
what customers can do**, so that **I can print it on a bill and turn off what I am not
ready for**.

**Your portal address** — `smartbillhub.bynry.com/pine-hill` — with copy, open, a **QR
code for your bills** and *add it to the bill template*. **The portal is** live or off. And
**what customers can do**: five switches, each with a sentence. Then **who is using it** —
customers enrolled, signed in this month, requests from the portal, readings sent in.

⚠ **THE PORTAL ADDRESS IS THE ONE THING HERE THAT ALREADY EXISTS AND IS NEVER SHOWN.** It
is the tenant slug the utility chose at sign-up, stored on the tenant record and used as
the first path segment of every request — **and after the sign-up wizard the back office
never mentions it again. A utility cannot put its portal on a bill if it cannot find the
address.**

⚠ **DO NOT ADD A SECOND COPY OF IT.** And note the trap: the column is still called
`subdomain` and now holds a **path segment** — *"reading the field name and inferring the
URL shape is exactly the reasoning that produced"* seventy-five wrong routes.

⚠ **THE FIVE SWITCHES ARE THE RULING OF 2 SEPTEMBER MADE OPERABLE.** All on for a new
tenant **except self-read**.

**2 · Business Rules**

| BR | Statement | Status |
|---|---|---|
| `BR-CWP-007` | The address is `/{tenant}/portal/…`, the tenant first | CONFIRMED — `CR-068` `R11` |
| — | Five per-tenant switches: quick pay, self-read, plans, requests, outage. **All on for a new tenant except self-read** | CONFIRMED — `CR-068` `R8` |
| — | Turning the portal off shows a holding page; **bills and letters are unaffected** | CONFIRMED — blueprint `B1` |
| — | ⚠ Defaults fail closed: `is_live` defaults to **false** | CONFIRMED — hard-won law 3 |

**3 · Test Cases**

| TC | Scenario | Expected |
|---|---|---|
| TC-1 | Open the overview | The address reads `smartbillhub.bynry.com/pine-hill`, copyable, with a QR code |
| TC-2 · **negative** | ⚠ The stored value | Read from `tenant.subdomain`. Assert **no second column** holds the address |
| TC-3 | A brand-new tenant | `is_live = false`, and quick pay, plans, requests and outage on with **self-read off** |
| TC-4 | Turn self-read off | ⚠ `CWP-035` stops being reachable **and its endpoint refuses**, while every other tab is unchanged |
| TC-5 · **negative** | Turn the portal off | The address shows a holding page. ⚠ Assert **no notification row changes** and bills still go |
| TC-6 | The counts | `412 of 1,180` enrolled, `268` signed in this month, `37` requests from the portal |
| TC-7 · **negative** | Readings off | ⚠ The readings count reads *"Readings are off, so nothing is counted"* — **not zero**, which would read as nobody using it |
| TC-8 · **tenant isolation** | The overview with an Oak Ridge admin | Oak Ridge's address, switches and counts |
| TC-9 · **negative** | A **Billing Clerk** opens it | Refused — System Admin only |
| TC-10 | *Add it to the bill template* | Routes to the template catalogue with the address available |

**4 · Test Data** — Tenant `pine-hill`, address `smartbillhub.bynry.com/pine-hill`, live.
Switches: quick pay **on**, send your own reading **off**, payment plans **on**, service
requests **on**, outage reporting **on**. Counts: enrolled `412 of 1,180`, signed in this
month `268`, requests from the portal `37`, readings sent in `—`.

**5 · Data Fields / Mapping**

| Field | Screen | Source | DB target | Type | Origin | Validation |
|---|---|---|---|---|---|---|
| Portal address | CWP-069 | prototype-extracted | `tenant.subdomain` | text | reference-data | ⚠ **Displayed only.** Already routing |
| The portal is | CWP-069 | GAP | `portal_settings.is_live` | boolean | user-input | Default **false** |
| Five switches | CWP-069 | GAP | `portal_settings.*_enabled` | boolean | user-input | Self-read default false |
| Counts | CWP-069 | GAP | derived over credentials, sessions and requests | integer | computed-display | ⚠ Absent, not zero, when a feature is off |

**6 · Acceptance** — **Given** a System Admin on a new tenant, **when** they open portal
settings, **then** they can copy the address their customers will use, the portal is off
by default, self-read is the one switch off among the five, and turning self-read off
makes the customer screen unreachable **and** its endpoint refuse.

**7 · Finance Calculation** — N/A.

**8 · Open Questions** — None.

---
id: US-CWP-070
epic: EP-CWP-12
module: tenancy
screens: [CWP-070]
wave: 1
status: ready
blocked_by: []
depends_on: [US-CWP-069]
journeys: []
rules: []
golden_tests: []
finance_calc: none
---
### US-CWP-070 — Branding: read from Company → Profile, and stored nowhere twice

**1 · Details** — As **a System Admin**, I want **to see how the portal will look and set
the few things that are portal-only**, so that **I am not maintaining two logos**.

**Shared with your bills and letters** — logo, trading name, brand colour, accent colour —
shown **read-only** with a link to Company → Profile. **Portal only** — the sentence under
your name, which services appear as chips, office hours, emergency number. And a **live
preview that updates as you type**.

⚠ **ALMOST NONE OF THIS IS NEW STORAGE, AND THE SCREEN SAYS SO.** The logo as sanitised
bytes with its content type, the two brand colours, the legal and trading names, the
mailing address and the support phone are **all already on the tenant record and already
edited on Company → Profile.**

⚠ **REPEATING THOSE FIELDS HERE WOULD GIVE A UTILITY TWO VERSIONS OF ITS OWN LOGO.**

⚠ **AND THE PREVIEW IS WHAT MAKES THE SCREEN WORTH OPENING.**

**2 · Business Rules**

| BR | Statement | Status |
|---|---|---|
| — | Branding **reads** the shared fields and keeps no copy | CONFIRMED — blueprint `B2`; `CR-068` §11 |
| — | Only the strapline, the front-page chips, the hours and the emergency number are editable here | CONFIRMED — blueprint `B2` |
| B14 rule 32 | The strapline is subject to the description budget | CONFIRMED — B14 |

**3 · Test Cases**

| TC | Scenario | Expected |
|---|---|---|
| TC-1 | Open branding | Logo, trading name, `#EC3013`, `#E15B47` shown **read-only** with an *edit in Company* link |
| TC-2 · **negative** | ⚠ Try to save a logo here | Refused. Assert `portal_settings` has **no logo column** |
| TC-3 | Change the strapline | The preview updates as you type, and `CWP-001` shows it |
| TC-4 | Tick Electric among the front-page services | The chip appears on `CWP-001` |
| TC-5 · **negative** | Tick a service the tenant does not sell | Not offered — the list is the tenant's own services |
| TC-6 | Change the brand colour in Company → Profile | ⚠ The portal follows **immediately**, because it reads rather than copies |
| TC-7 · **tenant isolation** | Branding with an Oak Ridge admin | Oak Ridge's brand |
| TC-8 · **negative** | *Reset to defaults* | Clears only the **portal-only** fields; the shared four are untouched |

**4 · Test Data** — Logo `pine-hill-logo.svg` on file. Trading name *Pine Hill Water &
Power*. Brand `#EC3013`, accent `#E15B47`. Strapline *"Your account, your bills and your
meter readings — any time."* Services shown: Water · Sewer · Trash · Electric. Office
*8am to 5pm, Monday to Friday*. Emergency `(512) 555-0100`.

**5 · Data Fields / Mapping**

| Field | Screen | Source | DB target | Type | Origin | Validation |
|---|---|---|---|---|---|---|
| Logo, names, colours | CWP-070 | prototype-extracted | `tenant.*` | — | reference-data | ⚠ **Read-only here** |
| Strapline | CWP-070 | GAP | `portal_settings.strapline` | text | user-input | B14 rule 32 |
| Services shown | CWP-070 | GAP | `portal_settings.front_page_service_ids` | uuid[] | user-input | Subset of the tenant's own |
| Hours, emergency number | CWP-070 | GAP | `portal_settings` | text | user-input | Shown on every guest screen |

**6 · Acceptance** — **Given** a System Admin on branding, **when** they change the
strapline, **then** the preview updates as they type and the public front page follows;
**and** the logo and colours are read-only here with a link to their one home, so a
utility can never end up with two logos.

**7 · Finance Calculation** — N/A.

**8 · Open Questions** — None.

---
id: US-CWP-071
epic: EP-CWP-12
module: tenancy
screens: [CWP-071, CWP-072]
wave: 1
status: draft            # was `blocked`; OQ-1398 ruled 2026-09-04 — we ship a starter set in all eleven languages, which the utility then owns
blocked_by: []
depends_on: []
journeys: [J33, J46]
rules: [BR-CWP-094]
golden_tests: []
finance_calc: none
---
### US-CWP-071 — Help and answers in the back office: draft, translate, publish

⚠ **BUILT 2026-09-04 (CR-068 wave D, `2.138.0`) AND STILL `status: blocked`, WHICH
IS CORRECT AND NOT AN OVERSIGHT.** The frontmatter is not amended, because
`OQ-1398` is genuinely open and the boundary it draws is genuinely honoured: the
store, the three statuses, the eleven language rows and the **visible**
`needs_translating` state ship, and **nothing anywhere assigns, chases,
schedules or promises a translation**. A test asserts that absence
(`HelpAndCentres.test.tsx`, *"no screen promises a translation workflow"*), so
the boundary cannot be crossed by a later lane without going red. The mechanism
was never what the question blocked.

**1 · Details** — As **a clerk**, I want **to write the answers customers read before they
ring**, so that **the same question stops arriving**.

A list — question, topic, status, languages, **read this month** — that **drags to
reorder**, because *the order here is the order on the portal*. Then the editor:
question, topic, **also show on** a named screen, the answer, and a language table where
a missing translation is a **visible state** rather than a silent fallback. Preview,
history, publish.

⚠ **THE READ COUNT IS WHAT TURNS THIS SCREEN INTO A TOOL RATHER THAN A CHORE.** *"A
question read 1,204 times a month is a bill design problem, not a help problem."*

⚠ **AN ANSWER CAN BE WRITTEN AND DELIBERATELY NOT SHOWN**, and that is a third state
beside draft and published.

⚠ **THE *ALSO SHOW ON* FIELD IS THE HIGHEST-VALUE FIELD IN THIS EPIC.** One field makes
the same answer appear **under a bill** as well as in the list — and the utility does not
write it twice.

⚠ **PUBLISHING CHANGES WHAT CUSTOMERS READ STRAIGHT AWAY. THERE IS NO APPROVAL STEP**, and
the screen must say so.

⚠ **BLOCKED ON `OQ-1398`:** who keeps the answers current, and in how many languages.
**Eleven catalogues already ship and someone at the utility has to write them — an ongoing
job, not a build.** Build the store, the statuses and the variants; **stub nothing in the
mechanism, but do not promise a translation workflow.**

**2 · Business Rules**

| BR | Statement | Status |
|---|---|---|
| `BR-CWP-094` | Only `published` leaves the back office. Draft and not-shown never do, and the customer is never told a count of what is hidden | CONFIRMED — `CP-31`; blueprint §16 |
| `BR-CWP-094` | ⚠ A missing translation **falls back to English rather than hiding the answer** | CONFIRMED — blueprint `B4` |
| — | The list order **is** the portal order | CONFIRMED — blueprint `B3` |
| — | ⚠ Publishing is immediate; **there is no approval step** | CONFIRMED — blueprint `B4` |
| — | Who keeps them current, in how many languages | **OPEN — `OQ-1398`** |

**3 · Test Cases**

| TC | Scenario | Expected |
|---|---|---|
| TC-1 | Eight answers written | Six `published`, one `draft`, one `not shown` |
| TC-2 · **negative** | ⚠ The public help page | Shows **six**. Assert `draft` and `not shown` are excluded **in the query**, not in the template |
| TC-3 · **negative** | ⚠ The customer is never told two are hidden | Assert no count of hidden answers appears anywhere in the response |
| TC-4 | Publish *"Why is my bill higher than last month?"* with *also show on: the bill screen* | It appears within the minute on `CWP-011`, `CWP-059` and **under the charges on `CWP-061`** |
| TC-5 | Drag row three to the top | The portal's order changes to match |
| TC-6 · **negative** | A French reader with no `fr` variant | ⚠ Gets the **English** answer, not a blank. *"A missing translation is better than a missing answer"* |
| TC-7 | The language table | `English PUBLISHED`, `Español (México) PUBLISHED`, `Français NEEDS TRANSLATING`, `हिंदी PUBLISHED` — ⚠ so a utility can **see** what its Spanish-speaking customers are not being shown |
| TC-8 | The read count | Moves `1,204` → `1,207` after three opens (`US-CWP-072`) |
| TC-9 · **negative** | Publish | ⚠ Takes effect immediately, and the screen warns there is no approval step |
| TC-10 · **tenant isolation** | Answers with an Oak Ridge admin | Oak Ridge's answers only |
| TC-11 · **negative** | A Billing Clerk | May edit content; ⚠ assert the role gate matches the tenant's own permission model rather than inventing one |

**4 · Test Data** — Eight answers. *Why is my bill higher than last month?* BILLING,
PUBLISHED, 11 langs, `1,204` reads. *What does "estimated" mean on my bill?* READINGS,
PUBLISHED, 11 langs, `842`. *How do I check for a leak?* WATER, PUBLISHED, 2 langs, `790`.
*When is my meter read?* READINGS, **DRAFT**, English, `—`. *Can I pay in instalments?*
PAYING, PUBLISHED, 11 langs, `611`. *What happens if I pay late?* PAYING, PUBLISHED, 11
langs, `508`. *How do I close my account?* MOVING, PUBLISHED, 2 langs, `410`. *Who is
responsible for the pipe outside?* WATER, **NOT SHOWN**, English, `—`.

**5 · Data Fields / Mapping**

| Field | Screen | Source | DB target | Type | Origin | Validation |
|---|---|---|---|---|---|---|
| Question, topic | CWP-072 | prototype-extracted | `help_answer.question`, `topic` | text | user-input | — |
| Status | CWP-071 | prototype-extracted | `help_answer.status` | enum | user-input | ⚠ Three states |
| Also show on | CWP-072 | GAP | `help_answer.also_show_on_screen` | text | user-input | ⚠ **One field, two placements** |
| Position | CWP-071 | GAP | `help_answer.position` | integer | user-input | Drag; **is** the portal order |
| Language variants | CWP-072 | GAP | `help_answer_variant` | — | user-input | ⚠ `needs_translating` is visible |
| Read this month | CWP-071 | GAP | `help_answer_feedback` | integer | computed-display | Written by the portal |

**6 · Acceptance** — **Given** eight answers of which one is draft and one is not shown,
**when** a clerk publishes the bill-higher answer with *also show on: the bill screen*,
**then** the public page lists six answers, the same answer appears under the charges on a
bill, dragging reorders the portal, and a French reader with no translation gets English
rather than nothing.

**7 · Finance Calculation** — N/A.

**8 · Open Questions**

| OQ | Question | Blocks | Routed to | Status |
|---|---|---|---|---|
| `OQ-1398` | Who keeps the help answers current, and in how many languages? | `CP-31`, `CP-34`, the translation workflow | Product Owner | OPEN — ⚠ **an ongoing job, not a build** |

---
id: US-CWP-072
epic: EP-CWP-12
module: portal
screens: [CWP-011, CWP-059, CWP-060, CWP-061]
wave: 1
status: ready
blocked_by: []
depends_on: [US-CWP-071]
journeys: [J33, J46]
rules: [BR-CWP-093, BR-CWP-094]
golden_tests: []
finance_calc: none
---
### US-CWP-072 — Help on the portal: the list, one answer, and the same answer under a bill

**1 · Details** — As **a customer**, I want **an answer where I am already looking**, so
that **I never go hunting for it**.

Four surfaces from one store. **The public list** (`CWP-011`) and **the signed-in list**
(`CWP-059`) — the signed-in one adds only that *"we already know which account you are
asking about"*. **One answer** (`CWP-060`) with in-text links that go and do what the
answer describes, a *did this help?* vote, related answers, and **three** ways to reach a
person. **And the same answer under a bill** (`CWP-061`).

⚠ **`CWP-061` IS THE HIGHEST-VALUE LINE IN THE WHOLE BLUEPRINT.** *"Why is my bill higher
than last month?"* was read **1,204 times in a month** from the help page — **which means
1,204 people went looking. Put the same answer under the bill and most of them never have
to look.**

⚠ **EVERY ANSWER ENDS IN A PERSON.** *"An answer that describes a screen without linking to
it is a help page written for a filing cabinet."*

⚠ **AND THE PORTAL WRITES BACK.** A read count and a *did this help* vote — **the smallest
write in the portal and the one that makes the help screens improvable rather than merely
present.** Without it the back office's read column is a column of zeroes.

**2 · Business Rules**

| BR | Statement | Status |
|---|---|---|
| `BR-CWP-094` | Only published; English fallback for a missing translation | CONFIRMED — `CP-31` |
| `BR-CWP-093` | No published answers ⇒ **no page and no link** | CONFIRMED — blueprint §16 Figure 11 |
| — | A read and a vote are **counted separately** | CONFIRMED — `CP-34` |
| — | Every answer ends in a route to a person | CONFIRMED — blueprint `P46` |

**3 · Test Cases**

| TC | Scenario | Expected |
|---|---|---|
| TC-1 | Six published answers | The public list shows six, each opening its own page |
| TC-2 | The signed-in list | ⚠ Adds *"we already know which account you are asking about"* and an *ask a question* route that needs no address retyped |
| TC-3 | Open one answer three times | ⚠ The back office's read column moves `1,204` → `1,207` |
| TC-4 · **negative** | Press *No* on *did this help* | ⚠ Counted **separately** from opening it. Assert two distinct events |
| TC-5 | The answer's in-text controls | *See my bill* and *Compare in Usage* actually go there — ⚠ the answer says *"compare the used figure with last month's"* and the screen offers to do it |
| TC-6 | An answer with *also show on: the bill screen* | ⚠ Appears **under the charges** on `CWP-061`, and the utility wrote it **once** |
| TC-7 · **negative** | No published answers at all | ⚠ The help page, its header link and the suggestion panels are **all absent** |
| TC-8 · **negative** | A locale with no variant | English, with a line saying so — never hidden |
| TC-9 · **tenant isolation** | Help with a Pine Hill session | Pine Hill's answers |
| TC-10 | The three routes at the foot | Ask a question, call, and where you can walk in — ⚠ the last one absent if no centre is shown |

**4 · Test Data** — Six published answers as in `US-CWP-071`. The bill-higher answer at
`1,204` reads, position 1 of 8, also shown on the bill screen, published in English,
`Español (México)`, `हिंदी` **and eight more**, *not yet in Français*. Bill
`BL-2608-0141` for the under-a-bill placement.

**5 · Data Fields / Mapping**

| Field | Screen | Source | DB target | Type | Origin | Validation |
|---|---|---|---|---|---|---|
| Answers | CWP-011, CWP-059 | GAP | `help_answer` where published | — | reference-data | ⚠ Gate in the query |
| Body | CWP-060 | GAP | `help_answer_variant.body` | text | reference-data | English fallback |
| Read, vote | — | GAP | `help_answer_feedback` | row | user-input | ⚠ Two distinct events |
| Under a bill | CWP-061 | GAP | `help_answer.also_show_on_screen` | text | reference-data | One field |

**6 · Acceptance** — **Given** a utility that has published six answers with the
bill-higher one attached to the bill screen, **when** a customer opens their August bill,
**then** that answer appears under the charges; **and** opening it three times moves the
back office's read count to `1,207`, while pressing *No* is counted as its own event.

**7 · Finance Calculation** — N/A.

**8 · Open Questions** — None. ⚠ `OQ-1398` blocks who **maintains** the content, not the
reads.

---
id: US-CWP-073
epic: EP-CWP-12
module: tenancy
screens: [CWP-073, CWP-062]
wave: 1
status: ready
blocked_by: []
depends_on: []
journeys: [J46]
rules: [BR-CWP-095, BR-CWP-093]
golden_tests: []
finance_calc: none
---
### US-CWP-073 — Tips: one slot, in season, and the page closes up when there is none

**1 · Details** — As **a clerk**, I want **one short line of advice on the screen where it
helps**, so that **a customer avoids a problem without reading a help page**.

A list — tip, where it shows, when, status — that drags to reorder, because *top of the
list wins where two match*. And on the customer side, **one slot on the screen the tip
names**, dismissible.

⚠ **THE CHEAPEST CUSTOMER-SERVICE TOOL IN THE PRODUCT AND THE EASIEST TO GET WRONG.** The
rules that keep tips useful are **drawn into the screen** rather than left to a policy
nobody reads: **one tip per screen at a time**, a length the reader will finish — *"keep
tips under fifteen words or nobody reads them"* — and a **month range** so a freeze
warning does not sit on the page in July.

⚠ **A TIP IS NOT AN ANSWER.** *"A tip is one sentence a customer did not ask for, on a
screen where it is useful. An answer is a paragraph they went looking for."* **There is no
page of tips and no way to browse them** — a tip the customer went looking for would be an
answer.

⚠ **AND WHEN NONE IS LIVE THE SLOT IS NOT THERE.** Today the only tip aimed at the portal
home is switched off **and** runs December to February — *"the home page does not show a
placeholder, an older tip, or a frame with nothing in it. It closes up, and nobody can
tell a slot was ever there."*

**2 · Business Rules**

| BR | Statement | Status |
|---|---|---|
| `BR-CWP-095` | On **and** in season; **one per screen**; top of the list breaks the tie | CONFIRMED — `CP-32` |
| `BR-CWP-095` | ⚠ No page of tips, no browsing | CONFIRMED — blueprint §16 |
| `BR-CWP-093` | No live tip ⇒ **no slot in the DOM** | CONFIRMED — blueprint `P48` |
| — | A seasonal tip appears and disappears **on its own** | CONFIRMED — blueprint `B5` |

**3 · Test Cases**

| TC | Scenario | Expected |
|---|---|---|
| TC-1 | Six tips written | Four showing today, two not — and neither omission is a fault |
| TC-2 | The June–September watering tip, today 2 Sep | Shows on `CWP-033`; ⚠ **gone on 1 October** with no edit |
| TC-3 · **negative** | ⚠ The freeze tip — off, and Dec–Feb | Not showing, **for two independent reasons**, and the home page has **no tip container at all** |
| TC-4 · **negative** | Two tips matching one screen | ⚠ **One** renders — the top of the list. Assert exactly one |
| TC-5 · **negative** | Try to browse tips as a customer | ⚠ No such page and no such route |
| TC-6 | Dismiss a tip | It closes for that viewer and the page reflows |
| TC-7 · **negative** | A tip of thirty words | ⚠ Accepted but flagged in the editor against the fifteen-word guidance — the rule is on the screen, not in a policy document |
| TC-8 · **tenant isolation** | Tips with a Pine Hill session | Pine Hill's tips |
| TC-9 | Reorder by dragging | The tie-break on a shared screen follows the new order |

**4 · Test Data** — *A running toilet can use 4,000 gallons a month.* — Usage looks high,
all year, ON. *Read the dials left to right, and ignore the red ones.* — Send a reading,
all year, ON. *Ask for a plan before the due date and late fees stop.* — Overdue, all
year, ON. *Watering before 10am loses less to evaporation.* — Usage, **Jun–Sep**, ON.
*Leave a tap dripping overnight when it freezes.* — Portal home, **Dec–Feb**, **OFF**.
*Your meter is yours to read any time — it is not locked.* — Every reading, all year, ON.

**5 · Data Fields / Mapping**

| Field | Screen | Source | DB target | Type | Origin | Validation |
|---|---|---|---|---|---|---|
| Tip text | CWP-073 | GAP | `tip.text` | text | user-input | ⚠ Flagged over fifteen words |
| Where it shows | CWP-073 | GAP | `tip.target_screen` | text | user-input | One named screen |
| When | CWP-073 | GAP | `tip.month_from`, `month_to` | smallint NULL | user-input | Null = all year |
| Status | CWP-073 | GAP | `tip.is_on` | boolean | user-input | — |
| Position | CWP-073 | GAP | `tip.position` | integer | user-input | ⚠ Breaks the tie |

**6 · Acceptance** — **Given** six tips of which one is off and out of season, **when** a
customer opens the portal home, **then** there is no tip container in the page at all;
**and when** they open usage in September, **then** exactly one tip shows — the watering
one — and it disappears by itself on 1 October.

**7 · Finance Calculation** — N/A.

**8 · Open Questions** — None.

---
id: US-CWP-074
epic: EP-CWP-12
module: tenancy
screens: [CWP-074, CWP-075, CWP-013, CWP-014]
wave: 1
status: ready
blocked_by: []
depends_on: []
journeys: [J34]
rules: [BR-CWP-096, BR-CWP-093]
golden_tests: []
finance_calc: none
---
### US-CWP-074 — Service centres, and *hidden* is a state, not a deletion

**1 · Details** — As **a clerk**, I want **to publish where a customer can walk in and what
each place can actually do**, so that **nobody drives over for something we cannot do
there**.

Back office (`CWP-074`, `CWP-075`): name, address, phone, getting there, **what a customer
can do here** as tick boxes, **takes payment by**, opening hours per day, and *shown to
customers* with a position. Customer side (`CWP-013`, `CWP-014`): the centres shown, each
with hours, what you can do, what you **cannot**, and what it takes.

⚠ **NOTHING IN THIS PRODUCT MODELS A PHYSICAL PLACE.** No office, branch, counter or
location record exists anywhere in the schema — **so the record is genuinely new. The
screen is not:** it arrives as a card in **Configure → Reference data**, and a card with a
list and an editor behind it is a shape this product already repeats nine times.

⚠ **THE LIST OF WHAT A CUSTOMER CAN DO HERE IS THE REASON THIS SCREEN EXISTS.** An address
and opening hours are on every utility's contact page already; **what nobody publishes is
that the north counter takes payments and cannot open an account.** *"Ticking report a
problem off is a real answer, not an omission, and it saves somebody a wasted journey."*

⚠ **AND FOUR OF THE FIVE ROWS SAYING NO IS THE SCREEN DOING ITS JOB.** *"A list of what a
place can do is a brochure; a list that also shows what it cannot do is an answer, and it
is the difference between one journey and two."*

⚠ **HOLIDAY CLOSURES ARE TYPED BY NOBODY.** They come from the holiday calendar the utility
**already keeps** in Reference data — *"which is what stops a portal telling someone to
walk to a closed door on Thanksgiving."*

**2 · Business Rules**

| BR | Statement | Status |
|---|---|---|
| `BR-CWP-096` | ⚠ `is_shown_to_customers = false` is a **real state, not a deletion** — how a depot stays off the public page | CONFIRMED — `CP-33` |
| `BR-CWP-096` | Holiday closures come from the tenant's existing calendar | CONFIRMED — `CP-33` |
| `BR-CWP-093` | No centre shown ⇒ ⚠ **no visit page and no header link** | CONFIRMED — blueprint §16 |
| — | What a centre **cannot** do is shown, not omitted | CONFIRMED — blueprint `G14` |

**3 · Test Cases**

| TC | Scenario | Expected |
|---|---|---|
| TC-1 | Three centres, one hidden | ⚠ The public page shows **two**. The depot is absent but **still in the back-office list** |
| TC-2 | The north counter on a Wednesday | *"Closed today · Opens **Thursday** at 9:00am"* — ⚠ from the clock and the Tue & Thu hours, not from a typed field. The drawing (`CWP-014.png`) says *Tuesday*, and a screen showing *Tuesday* on a Wednesday has typed the day — the wrong answer (`DEF-CWP-3604`, 2026-09-03) |
| TC-3 | Thanksgiving, 26 November | ⚠ **Both** centres read closed, and **nobody edited the page**. Assert it comes from the holiday calendar |
| TC-4 · **negative** | The north counter's action list | ⚠ **Four of five rows say no**, including *"you cannot open or close an account here"* |
| TC-5 · **negative** | Hide every centre | ⚠ The visit page, its header link and the *where you can walk in* routes are **all absent** |
| TC-6 | Payment methods per centre | Main office: cash, cheque, card, money order. North counter: cash, cheque, **no card machine** — and the screen says so |
| TC-7 · **tenant isolation** | Centres with an Oak Ridge admin | Oak Ridge's centres |
| TC-8 | Reorder | The public page follows the back-office position |
| TC-9 · **negative** | Remove a centre that customers have seen | ⚠ Prefer hiding; removal is the danger tier and warns that a printed address may still be in circulation |
| TC-10 | *Pay in person* on `CWP-038` | Names only the centres that **take money**, and what they take |

**4 · Test Data** — **Main office**, `214 Cedar St, Austin TX 78702`, `(512) 555-0148`,
Mon–Fri 8:00am–5:00pm, takes cash · cheque · card · money order, can do everything, **on
the portal**, parking behind the building. **North counter**, `1190 Palm Ct, Austin TX
78758`, Tue & Thu 9:00am–1:00pm, takes cash · cheque, **payments only**, on the portal.
**Depot — not public**, `44 Works Rd`, no hours, **HIDDEN**. Holiday: 26 November,
Thanksgiving.

**5 · Data Fields / Mapping**

| Field | Screen | Source | DB target | Type | Origin | Validation |
|---|---|---|---|---|---|---|
| Name, address, phone, getting there | CWP-075 | GAP | `service_centre.*` | text | user-input | — |
| What a customer can do | CWP-075 | GAP | `service_centre.allowed_actions` | text[] | user-input | ⚠ Unticked renders as **cannot**, not as absent |
| Takes payment by | CWP-075 | GAP | `service_centre.payment_methods_accepted` | text[] | user-input | Named on `CWP-014` |
| Opening hours | CWP-075 | GAP | `service_centre_hour` | — | user-input | ⚠ Holidays are **not** rows here |
| Shown to customers | CWP-075 | GAP | `service_centre.is_shown_to_customers` | boolean | user-input | ⚠ A state, not a deletion |
| Holiday closures | CWP-013, CWP-014 | prototype-extracted | the tenant holiday calendar | — | reference-data | ⚠ Reused, never retyped |

**6 · Acceptance** — **Given** a utility with three centres of which one is hidden,
**when** a customer opens the visit page on a Wednesday, **then** two centres show, the
north counter reads *closed today, opens Thursday at 9:00am*, and its list says plainly
that an account cannot be opened there — and on Thanksgiving both read closed with nobody
having edited anything.

**7 · Finance Calculation** — N/A. ⚠ Which centres take money feeds *pay in person* on
`CWP-038`.

**8 · Open Questions** — None.
