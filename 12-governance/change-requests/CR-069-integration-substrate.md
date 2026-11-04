## CR-069 — The integration substrate: thirty-six specifications, ninety-four tasks, five phases, and a module that is eleven lines long

> **⚠ READ THIS FIRST IF YOU ARE A NEW SESSION.** This CR is built from an engineering design
> artifact titled *The Integration Substrate*, read at product version **2.120.1** on **2026-09-01**.
> Everything a lane needs is in this file or is cited by a path you can open. **If you need a fact
> that is not here, that is a defect in this CR — file it rather than guessing.** `CR-059` §0d
> records what guessing cost: a 50% gap between what was agreed and what was built.

### CR-069 · 0 · CAPTURE — the Product Owner's words, verbatim

> *"We create this spec document for Integtations - simialr to CR 68 - please first find out all the
> changes you will have to and show me everything on screen first and once cofnirm we can write CR"*
> — 2026-09-03

> *"Write down CR69 in detail"* — 2026-09-03, after the change list was shown and confirmed.

**Three answers to previously-unread questions arrived in the same conversation and are §6's `R-8`.**
They are recorded in `12-governance/02-decision-log.md` at commit `e5a4a17e` with their consequences;
the short form is in §6.

### CR-069 · 0b · WHY THIS DOCUMENT CAN BE BUILT FROM

**Same discipline as `CR-068`'s source, arrived at independently.** It separates *descriptions* from
*commitments*, then audits itself: **46 statements that something does not exist**, each pushed
through one of two doors — **26 specified** (17 already, 9 newly minted as `C28`–`C36`) and
**20 ruled out of scope, each with its reason and who ruled it.** Its own sentence:

> *"There is no third category and there are no blanks. An absence with neither a number nor a
> stated reason would be a defect in this table... Describing an absence honestly and then not
> scheduling it is exactly how a description gets read as a promise."*

**So §8's thirty-six specifications ARE the scope.** A lane may build from them without re-reading
the prose.

⚠ **AND IT NAMES ITS OWN WEAKEST POINT RATHER THAN HIDING IT** — see §6 `R-8`. One connector was
designed **without reading the partner's documentation**, because the network refused the host.

### CR-069 · 0c · STEP 0 — WHAT MOVED UNDER THE DOCUMENT

**The document was written against `2.109.0` on 31 August and re-read at `2.120.1` on 1 September.
We are now at `2.128.2`.** Verified 2026-09-03:

| The document says | Measured 2026-09-03 | Consequence |
|---|---|---|
| *"the integrations module is six files and eleven lines, every one a docstring"* | **TRUE.** `06-backend/apps/integrations/` — `api.py`, `models.py`, `registry.py`, `services.py`, `tests.py`, `__init__.py` + `migrations/`, **11 lines total** | **The central claim holds. There is no legacy to unpick and the substrate can be built correctly the first time** |
| *"`core/jobs.py` 1,180 lines"* | **763 lines.** Same file, same capability | A supporting figure, not a decision figure — but it means **every count in this document needs re-checking, not just its conclusions** |
| Field encryption, idempotency keys, the error envelope, the queue router already exist | **TRUE.** `core/crypto.py` 583 · `core/idempotency.py` 252 · `core/errors.py` 464 · `config/celery_routes.py` present | **Six kernels inherited rather than written. This is why the substrate is affordable** |
| *"Gateway payment webhooks are a stub — `payments/webhooks.py` is one docstring line, no handler reads the key"* | **FALSE NOW.** 577 lines, built 2026-09-03 as `CR-060` C21, **15 tests**, idempotent | **`T-9.04` may be largely done. VERIFY BEFORE BUILDING** |
| *"The canonical screen range runs to S115"* | **FALSE NOW.** `S115`–`S135` were allocated 2026-09-03 by PO ruling; `S136`–`S140` reserved | **The document's `S116`–`S121` are all taken. See §9** |
| *"highest live `CR-058`, 32 rows"* | **FALSE NOW.** 80 CRs; this is `CR-069` | Its `CR-1`–`CR-9` are grouping handles, not allocations — it says so itself |

### CR-069 · 1 · CLASSIFY

**A new capability on an empty module.** Not a defect: nothing is broken, because nothing is built.
The module is eleven lines of docstring and has been since it was created.

**One item inside it IS a re-opening, and §2 states it rather than assuming it:** the derived-fee
ruling of 2026-08-12, whose premise the Product Owner changed on 2026-09-03.

### CR-069 · 2 · WHAT SIGNED STATEMENT IS BEING REVERSED — quoted, never summarised

**(a) `OQ-160`, closed 2026-08-12, PO verbatim: *"derived from shortfall"*.** The decision-log row
reads: *"a card day takes **$5,120.40**, the bank credits **$4,972.90**, and the **$147.50**
difference becomes the fee line. It is not required to arrive stated in a settlement file — **which
is what makes card reconciliation possible at all, since most acquirers net silently.**"*

**That premise no longer holds.** PO 2026-09-03, asked whether the processor sends a daily report of
its fees per payment: ***"Yes Night ly batch"***. **This processor does not net silently.**

⚠ **AND THE CLOSURE WROTE DOWN ITS OWN COST, WHICH IS WHAT CAN NOW BE RETIRED:**

> *"If the fee is DERIVED, a day where the processor kept **$137.50** and a customer charged back
> **$10.00** produces the identical **$147.50** gap and reconciles clean — the chargeback is
> invisible, the customer's bill stays paid, and nothing ever re-opens it."*

**This CR does NOT reverse it.** A closed ruling whose premise has changed goes back to the person
who ruled it, with the figure. **It is `R-4` in §6, it is put to the PO, and `T-9.05` is blocked
until they rule.** An inline edit here would be the process failure this repository has already paid
for once.

**(b) `OQ-144`** — bank matching is exact-amount and one-to-one — is **touched but not reversed**: a
settlement file becomes a third input to reconciliation rather than a change to the matching rule.
State it in the task, do not assume it.

**(c) NOTHING IN B4 OR B5 MOVES.** The document confirms this itself: *"Nothing in any of these ten
requests changes a frozen figure. Confirm this yourself at step 2 — if you find one, the process says
stop and re-sign."* **Do that confirmation; do not inherit it.**

### CR-069 · 3 · IMPACT — the ten surfaces

| Surface | Impact |
|---|---|
| **Rules** | New module rules under `BR-INT-#####`. The six principles in §7 become the first six |
| **Schema (B2)** | **Five new tables** (§10), all tenant-scoped, all RLS FORCE. `C34` is the task that anchors them in the schema brief **before** the migration |
| **API (A11)** | The connection surface, the run surface, and one inbound door per shape-D connector |
| **Screens (A1)** | **Six new** — `S141`–`S146` (§9), plus changes to `S8` |
| **Enums (A5)** | Auth placement · completion mode · executor · idempotency mode · seven difference classes · the failure taxonomy · outcome (**including `indeterminate`, which is new**) |
| **Glossary (A16)** | *connection*, *operation*, *manifest*, *adapter*, *projection*, *codec*, *packaging*, *executor*, *indeterminate* |
| **Open questions** | **8 rulings needed** (§6); **three answered 2026-09-03**, five open |
| **Demo fixture** | One connection per shape, a failed run, an expiring credential, a settlement file |
| **Journeys (08-qa)** | One per connector class |
| **Gates** | At least three new (§13) |

### CR-069 · 4 · WHAT IS ALREADY BUILT — and it is two thirds of the machinery

**The document's opening claim, verified in §0c:** *"Ten connectors were never the problem... this
codebase already owns two thirds of the machinery."*

| Kernel | What integrations gets free | Verified |
|---|---|---|
| Job framework | Retry and resume. **No integration ever writes its own retry loop** | `core/jobs.py`, 763 lines |
| Named queues | Blast-radius isolation. **A hanging SFTP server cannot stall a bill run** | `config/celery_routes.py` |
| Field encryption | Credential storage — **the single biggest thing that was missing, and it is not missing** | `core/crypto.py`, 583 lines |
| Idempotency keys | Never twice. Extends to inbound webhooks and outbound sends | `core/idempotency.py`, 252 lines |
| Error envelope | **A failed run is greppable by a code a clerk can read down a phone** | `core/errors.py`, 464 lines |
| Artifact store | Exports and import receipts need no new storage concept | `core/jobs.py` `result_link` |

**And on the payment side specifically:** the payments table is append-only by a database trigger, a
reversal is a NEW row, a payment may be reversed exactly once by a unique constraint, and
`bank_chargeback` is already one of four recorded reversal reasons. **The hardest half of taking
cards was built for something else and fits unchanged.**

### CR-069 · 5 · SIZE

| | This CR | `CR-068` | `CR-059` |
|---|---|---|---|
| Specifications | **36** | 56 | 37 |
| Tasks | **94**, in nine groups | — | 76 |
| Rulings needed first | **8** (3 answered) | 9 open | 2 |
| New tables | **5** | ~10 | 4 |
| New screens | **6** | 75 | 12 |
| Phases | **5** | 5 | — |

⚠ **THE DOCUMENT CARRIES TWO TASK REGISTERS THAT DISAGREE AND SAYS SO.** One section ends at 70
tasks numbered `T1`–`T70`; another carries 94 numbered `T-1.01`–`T-9.10`, with no mapping between
them. **This CR uses the 94 and ignores the 70**, because the 94 carry a commitment column. Its own
finding stands and is inherited: **24 of the 94 serve no commitment.** Those 24 are not scheduled
here — a task serving nothing is either a missing specification or a task nobody needs, and both are
answered by asking, not by building.

### CR-069 · 6 · THE EIGHT RULINGS — three answered 2026-09-03, five open

**None of these is a build.** Six of the eight block code that would otherwise have to guess.

| # | The question | The figure | Status |
|---|---|---|---|
| **R-1** | A property already carries the utility's own reference and the City's parcel number arrives. **Which one wins?** They want the same column, and that column is what makes a corrected re-import update rows instead of duplicating them | A utility loads **428 premises**, re-cuts the file to fix nine postal codes, and gets **428 matches, 9 updates, 419 no-ops**. Change the key and that becomes **428 new premises** | **OPEN** |
| **R-2** | The City's address service is unreachable. **May a clerk still create a property?** Refuse, type it in, or show what we saw last time | **Two of the three are safe.** The third writes a property against a parcel the City may have split since, **and it looks identical on screen to the good case** | **OPEN** |
| **R-3** | May a parcel in the City's records and not in ours **ever become a property automatically?** The proposal is no — it goes on a list somebody reads | About **66,500 such parcels arrive every night.** Whether the utility serves one is a decision about the utility, not a fact the City can state | **OPEN** |
| **R-4** | **A signed decision whose premise has moved** (§2a) | **$5,120.40** taken, **$4,972.90** credited. A **$147.50** fee, and a **$137.50** fee plus a **$10.00** chargeback, produce the identical gap | **PREMISE CHANGED 2026-09-03 — goes back to the PO** |
| **R-5** | **Do card refunds open with the card rails, or later?** Refused by name today, with a reason recorded | A card refund recorded without rails **draws the customer's credit down and returns them nothing.** Taking cards without refunding them is a support queue | **OPEN** |
| **R-6** | Autopay records an intention and charges nobody. **When charging arrives, are the recorded intentions consumed as they stand?** | The intent stores the amount and date **as the customer was told**, so a later correction to the bill does not silently change what gets taken | **OPEN** |
| **R-7** | The map background is drawn from a public map server, accepted 22 August. **A city that runs its own map server changes the answer** | The ruling's own words: *"every pan sends your asset locations to a third party."* Pointing at the City's own server sends them to the body that already owns the data | **GENERALISED, NOT REVERSED** — `C14` gives it somewhere to live |
| **R-8** | **Not a ruling — a reading.** Four questions the payment processor's documentation must answer | — | **THREE ANSWERED 2026-09-03** |

#### R-8 in detail, because it is the one thing in this CR that cannot be resolved from the repository

**The design could not open the processor's documentation — the host is refused by the network
policy.** So that connector was designed on assumption, and every dependent task is marked
contingent. Four questions were named. **The PO answered three on 2026-09-03:**

| q | Question | Answer | What it decides |
|---|---|---|---|
| **q1** | Does a charge accept an idempotency key we supply, and does replaying it return the original result rather than charging again? | ⛔ **STILL UNREAD** | **The entire outbound guard.** If yes, a timeout is recoverable by replaying the same key. **If no, every timeout needs an outcome query and the charge operation needs a companion** — which is `C26`'s indeterminate outcome doing real work |
| **q2** | Is there a settlement report, with fee **and chargeback** broken out per transaction? | ✅ **"Yes Night ly batch"** — ⚠ **fees only were asked; the chargeback half is STILL UNREAD** | Retires the blind spot in `R-4`. **Without the chargeback breakdown the $137.50 case is only half separated** |
| **q3** | Is the card page hosted by them, or an SDK inside ours? | ✅ **"they are on Spruce page"** | **The card number never reaches our servers.** Settles `C14`'s third executor value as `browser, credentialed`, **and removes the heaviest compliance tier from scope** |
| **q4** | Are webhooks signed, and with what — the merchant secret, a separate signing key, or nothing? | ✅ **"there will be some code"** — ⚠ **answered in part** | **Rules out `nothing`**, so an outbound confirm on every callback is off the table. **But a signature over the body and a shared code in the payload are not the same thing on a money path**, and which it is decides whether `payments.webhook_key` as provisioned suffices |

⚠ **AND A FIFTH THING TO LOOK FOR WHEN THAT DOCUMENTATION IS FINALLY READ, because both have already
bitten this document once:** any request parameter whose **default is unsafe** (one specification had
four, two on the money path), and **any amount field whose units are not stated** — minor units
against decimal is *"a hundredfold error in the direction nobody notices until a customer calls."*

### CR-069 · 7 · THE SIX PRINCIPLES — each stated with what it costs to break

**These are not style preferences.** Each names a failure recoverable only by rewrite.

| | Principle | The price of breaking it |
|---|---|---|
| **P1** | **Configuration is data, not code.** A provider is a declarative manifest plus an adapter class | Adding one touches no screen, no endpoint, no migration. **Break this and every connector becomes a sprint** |
| **P2–P6** | Read them in the source §1.2 and quote them into `BR-INT-` when the module rules are written | Each carries its own price in the source; they are not restated here because a paraphrase of a principle is how it gets weakened |

⚠ **`P1` IS THE REQUESTER'S OWN SENTENCE AND IT IS THE TEST FOR THE WHOLE CR:** *"every time such
integration comes we dont want to change our integration framework."* **The exit test for phase 1 is
that a new provider is a manifest and an adapter — nothing else.**

### CR-069 · 8 · THE THIRTY-SIX SPECIFICATIONS — `C1`–`C36`

**This table is the scope.** Status is `UNVERIFIED` on every row and **not one is a guess** — the
document's own words: *"Engineering fills this column in from the code — a table that exists, a route
that is mounted, a screen that calls it. Not from a task list, not from a merged pull request, and
not from this document."*

⚠ **SCREEN IDS BELOW ARE RE-MAPPED FROM THE DOCUMENT'S `S116`–`S121` TO `S141`–`S146`.** See §9.

| Spec | Lives in | Specification, and what it waits on | Screens | What done looks like on screen |
|---|---|---|---|---|
| **C1** | 2.15.2 | Operations, not providers, are the unit waits on: — do it before the first connector | S142 | A clerk opens the payment kiosk card and sees one card with three things listed under it — Account lookup, Payments, Returns — each with its own state and its own last-run time. Not three cards, and not one word averaging them. |
| **C2** | 2.15.2 | Auth gains a placement — header, bearer, query, redirect waits on: C1 | S141 | Connecting the kiosk asks for a key and nothing about bearer tokens; connecting the GL partner asks for a client id. Neither modal has a field the other needs, and no code branched to make that true. |
| **C3** | 2.15.2 | The envelope carries a status map waits on: C1 | — | A duplicate payment notification is answered 409 ; the same duplicate on a generic webhook is answered 200 . Both come from a declared value, and the adapter contains neither number. |
| **C4** | 2.15.2 | A per-operation policy for an unrecognised value waits on: C1 | S143 | A kiosk payment arrives naming CASHAPP , which nobody has mapped. The payment is accepted and recorded as Other ; the mapping screen shows that row in red. An outbound file naming an unregistered format is refused by name , with the list of what exists. |
| **C5** | 2.15.2 | A network allowlist on the connection waits on: — | S141 | The GL connection lists 198.51.100.0/24, 203.0.113.7 . A read from any other address is refused without revealing whether the account exists . |
| **C6** | 2.15.2 | respond_after — where the reply sits waits on: C1 | — | Replaying a captured kiosk payment returns 409 before anything is posted, and the payment is applied exactly once. A configuration that puts the reply before authenticate is refused at load, not at runtime. |
| **C7** | 2.16.2 | A conformance profile — claim, evidence, status waits on: — | S141 | A connection declaring MultiSpeak shows self-declared , not a badge; declaring certified with no certificate id is refused. The conformance report is regenerated from the registry and nobody maintains it by hand. |
| **C8** | 2.17.3 | Format is a parameter: projection × codec × packaging waits on: C1 | S141 | The same payment is emitted as JSON to one partner and XML to another from one projection , proved in a test. An unregistered codec name is refused by name with the list of what exists. A format picker appears only where more than one codec is registered. |
| **C9** | 2.17.3 | A customer-delegated consent record, revocable waits on: T-B4 · Product Owner | S145 · S146 | A customer allows an installer twelve months of usage; a clerk revokes it two months later and the installer’s very next request is refused — not their next nightly collection — and the run record says why. The ended row stays on the record. |
| **C10** | 2.18.2 | Completion: immediate, or submit–poll–collect waits on: C1 | S142 | A billing export shows They are building the file. We will collect it when it is ready · asked them 4 times · checking again in 30 seconds , and the clerk can leave the page. The run is not finished until the file is collected. |
| **C11** | 2.18.4 | A token-exchange auth mode waits on: C1 | — | A two-hour collection completes across a ten-minute token, and no credential row is written for the short-lived token — the credential table still shows one version, not 144 a day. |
| **C12** | 2.18.4 | A fetch plan — a window and a page, per operation waits on: C1 | — | One vendor collects with page sizes of 100, 150 and 5,000 on three different services, and a two-year backfill runs as about 105 seven-day windows. None of those numbers is in code. |
| **C13** | 2.18.3 | Idempotency mode: refuse, or reconcile waits on: C1 · 🔒 | S142 | Monday collects three days. Tuesday collects the same three days after the supplier filled four gaps and revised two values: the run reads 1,240 read · 6 revised , 1,238 rows are untouched, and a reading already billed does not move — the difference is raised as a correction. Proved on PostgreSQL. |
| **C14** | 2.24.3 | Executor — our server, or the viewer’s browser waits on: — the one new dimension | S141 | The map draws tiles and the connection card shows the call is made by the browser ; the test modal tests the page’s reach separately from the server’s. A browser-executed operation carries no tenant secret , and a page-security policy is generated from the registered browser operations. |
| **C15** | 2.24.4 | Inline completion — a latency budget, not a job waits on: C14 | S8 · address search | A clerk types an address and sees candidates in under a second . Nothing is queued, no progress row appears, and when the city is slow the breaker opens and the screen says so rather than spinning. |
| **C16** | 2.24.4 | Result disposition: load it, or offer it waits on: C15 | address search | The candidate list is shown and nothing is written . A premise appears only after a person picks a row — and the parcel is re-checked against live GIS at the moment of the write , not on every keystroke. |
| **C17** | 2.24.4 | A measurement frame on every numeric waits on: — 🔒 | — | A coordinate arriving in a projected system is refused by name rather than written; the one that fits the column and puts the pin about 700 km from the South Pole is refused too, because the frame is declared and checked. A match score of 0.8 against a 0–100 scale is refused rather than accepting everything. |
| **C18** | 2.25.9 | Safety-relevant parameters stated explicitly waits on: C1 · 🔒 | — | A collection whose request omits actual_consumption does not run , and the run says which parameter was unset. No vendor default is inherited on a money path — one supplier has four that fail open. |
| **C19** | 2.25.9 | mutates_partner_state — a fetch that changes their world waits on: C1 | — | An export request carrying CloseOnExport is recorded with an idempotency key and a receipt, and a retry is refused as a duplicate rather than closing billing routes twice. |
| **C20** | 2.25.9 | Result delivery: a link, or a handle to collect waits on: C10 | S142 | The working export flow mixes two of the vendor’s versions — one returns a link and the other an identifier — and both are collected by one runner reading a declared value. |
| **C21** | 2.25.9 | Ephemeral facts — an operation may be must-not-skip waits on: C13 | S142 | A missed night on the readings collection raises rather than quietly catching up, because one field it carries is published for a single day and a refetch a week later honestly returns zero. |
| **C22** | 2.26.8 | Scope of authority — auto / queue / never, per field waits on: 🔒 | S143 · approval queue | The nightly GIS check updates a postal code by itself, queues a district change for a person, and never writes the three columns that decide tax — and the per-field grant is visible on screen rather than implied by code. |
| **C23** | 2.26.8 | Membership authority — content, or which rows exist waits on: C22 | run report | A night takes 69,000 parcels, updates the ones we have, creates none , and reports 66,500 not ours as its own count. A night where 2,914 matches becomes 300 is visible because that second number is on the report. |
| **C24** | 2.26.8 | Seven difference classes, with a disposition each waits on: C22 · 🔒 | approval queue | Two of our premises legitimately sharing one parcel key is caught and queued before the database refuses the write at two in the morning with an error naming neither row. |
| **C25** | 2.26.8 | Money-path columns named in one place waits on: C22 · 🔒 | — | A feed granted every other permission still cannot write inside_city_limits , city or state . The refusal names the column and the reason, and the jurisdiction flag keeps having no default. |
| **C26** | 2.27.9 | Indeterminate — a third outcome waits on: 🔒 | S142 · charge detail | A charge that times out reads we do not know — not failed — with a button to go and ask the processor, and a blind retry is refused . A zero would be a claim nobody can make. |
| **C27** | 2.27.9 | Partner-issued idempotency — our key, before the call waits on: C26 · 🔒 | — | The key for a charge is generated and stored before the request leaves, and the same one is sent on every retry, so a debit that already left an account is never taken twice. |
| **C28** | new | Email feedback — delivery and bounce waits on: C1 · phase 2 | S142 · delivery dashboard | A bill emailed on the 1st shows delivered on the connection’s run, and a bad address shows bounced with the provider’s own sentence — and the delivery dashboard stops reading not reported for bounces. Until then it keeps saying not reported and never zero. |
| **C29** | new | The first beat schedule this product has ever had waits on: C1 · T-1.15 | S142 | A connection set to nightly in America/Chicago runs at their midnight on both sides of a daylight-saving change; 300 such connections start spread across the window rather than together; a run still going when the next is due is skipped and the skip is recorded ; and six missed windows produce one run for a file fetch and none for anything that moves money. |
| **C30** | new | Machine authentication for a partner waits on: identity module · 🔒 | S141 · S144 | A finance system with no human at the keyboard authenticates with a credential we issued, scoped to one tenant, and the key is shown once and never again — only replaced. Revoking it refuses their very next call. |
| **C31** | new | Channel and kiosk reference on a payment waits on: C1 · T-6.05 | payment detail | A payment taken at a machine records KIOSK and the kiosk’s own reference, and a report can separate counter takings from kiosk takings. An unrecognised channel records as Other and stops nothing. |
| **C32** | new | What a Nacha R02 maps to waits on: Product Owner · 🔒 | S143 | A bounced payment returned R01 shows the clerk not enough money . One returned R02 shows the reason the ruling chose, the raw code is kept on the payload, and the four signed reversal reasons are not widened to hold a third party’s vocabulary. |
| **C33** | new | The subprocessor register, in the inbound direction waits on: C30 · T-B2 | register view | A partner reading from us appears on the subprocessor register as a relationship pointing inward , with the tenant’s explicit authorisation against it — and the register is still derived from live connections rather than maintained by hand. |
| **C34** | new | Anchor the five tables in the schema brief waits on: — before the migration | — | The field map’s discrepancy I-2 is closed: the module’s claim to own these tables and the DDL registers agree, and the migration is written against a brief that names them. |
| **C35** | new | Fold the email sender card into the connection model waits on: C1 · phase 2 | S8 Notifications | A system administrator types a mail password into the product and connecting email no longer requires a deployment. smtp_secret_ref stops naming an environment variable, and existing holders are migrated to a real encrypted credential. |
| **C36** | new | Nacha codes and camt.053 — the two nearly-free standards waits on: C8 · T-1.16 | S143 | A bank statement arrives as camt.053 and imports through the same connector as BAI2, with the codec named rather than coded. Nacha return codes are mapping rows a clerk can see. MultiSpeak and Green Button are not claimed. |

🔒 **Eleven of the thirty-six are marked sensitive-path in the source** (they carry 🔒 in the
waits-on column above). Each needs a `HUMAN-REVIEW-PENDING` flag and a row in
`12-governance/09-human-review-ledger.md` **in plain English with a concrete worked figure** — never
an ID to look up. `g07` enforces the row's existence.

### CR-069 · 9 · SCREENS — `S141`–`S146`, and why they are not the numbers the document uses

**The document proposes `S116`–`S121` and marks them *"indicative and not allocated in any
register — allocate real ones at step 0."* It was right to, and the numbers moved underneath it.**

On **2026-09-03**, hours before this CR was written, the PO re-opened the exhausted screen band and
`S115`–`S135` were allocated to the staff app's thirty-one un-numbered screens, with `S136`–`S140`
reserved. **Every number this document proposes is now taken by something else:**

| The document wants | That number is now | This CR uses |
|---|---|---|
| `S116` · the connection screen | Service-request document settings | **`S141`** |
| `S117` · the operations card | Data-retention run ledger | **`S142`** |
| `S118` · value mapping | Charge-code detail | **`S143`** |
| `S119` · machine credentials | Discount create/edit | **`S144`** |
| `S120` · consent | Discount detail | **`S145`** |
| `S121` · consent | Tax and fee detail | **`S146`** |

**Next free ground after this CR: `S147`.** Nothing is renumbered and nothing is zero-padded.

⚠ **THE VISIBLE BADGE IS A SEPARATE THING AND IS NOT DECIDED HERE.** The staff app's on-screen tag
renders r10's module id, never an `S`-id (PO ruling 2026-08-19), and r10 draws none of these six.
**Six new badges must be allocated into `10-scripts/gates/g29_allocated_badges.txt`** — that register
exists as of 2026-09-03 and `g29` reads it as a third authority.

### CR-069 · 10 · THE FIVE TABLES

`integration_connection` · `integration_credential` · `integration_run` ·
`integration_consent` · `integration_target_reference`

**All tenant-scoped. All RLS FORCE. `C34` is the task that anchors them in the schema brief BEFORE
the migration is written**, not after — the document names that ordering itself.

⚠ **THE CREDENTIAL TABLE IS SEPARATE FROM THE CONNECTION TABLE ON PURPOSE.** The source: *"The
instinct is a single `integration_connections` table. It is wrong for a reason"* — and *"Audit is a
consumer of the connection table, never of the credential table."* **A lane that merges them has
made every audit read touch encrypted secrets.**

### CR-069 · 11 · FOLDER STRUCTURE AND HOW THIS ENTERS THE REPOSITORY

**The module already exists and is empty.** `06-backend/apps/integrations/` — six files, eleven
lines, all docstrings. **Nothing needs creating; it needs filling.**

```
06-backend/apps/integrations/
  models.py            the five tables of §10
  migrations/          0001_initial onward; RLS FORCE in its own migration
  registry.py          THE MANIFEST REGISTRY — provider manifests as data (P1)
  adapters/            one file per provider. A new connector is a manifest + one class
  runners/             the four runtime quadrants (§12 phase 1), all built up front
  codecs.py            the codec registry — projection × codec × packaging (C8)
  api.py               connections, runs, the operation surface
  inbound.py           the shape-D door: verify, persist raw, 200, process async
  selectors.py         reads
  services.py          writes
  seams/               one file per module it hands to or reads from
  conformance.py       C7 — claim, evidence, status
```

**Frontend:** `07-frontend/src/features/integrations/` — the staff app's existing furniture, **not** a
second root. This is a Settings surface for clerks, unlike `CR-068`'s portal.

⚠ **B14 RULE 21.** `features/integrations/` is new code. **Add it to
`07-frontend/src/styles/route-b-migrated.txt` in its first commit** so utilities are legal there;
otherwise a Tailwind class renders as **nothing at all** while `tsc` and every test pass.

**Identifiers:** `BR-INT-#####` for rules · `EP-INT-##` / `US-INT-#####` for stories · `C1`–`C36` are
kept as the document's own handles and are **not** minted into any product series, exactly as
`CR-068` keeps `CP-`. Docs module `04-docs/05-modules/16-integrations/`.

### CR-069 · 12 · THE IMPLEMENTATION PLAN — five phases, each one launchable

**Per the PO's ruling of 2026-09-03 — *"at the end of each pahse we should abl to luanch some
funtionlaity"* — every phase below ends with something a utility can be shown.** The document's own
five phases already had exit tests that are demonstrations rather than opinions; they are kept and
the launch sentence is added.

#### PHASE 1 — **LAUNCH: the Settings screen lists every integration we will ever offer, and honestly says none is set up**

**What a utility sees:** the integration grid, every provider card rendered from the registry, each
reading *Not set up* — **and a connect attempt on a coming-soon provider refused by the API, not just
by a greyed-out button.**

**Twenty tasks (`T-1.01`–`T-1.20`).** Five tables, the manifest registry with **operations** as its
unit, the adapter protocol, the codec registry, **all four runners including the one with no
connector behind it**, the job kinds and the dedicated queue.

⚠ **PHASE 1 GOT BIGGER ON PURPOSE — about a week — and the reason is worth keeping:** all four
runners, the codec registry and the target-reference table were each added because a real
specification needed them, and **finding out later costs a migration rather than a field.**

Ground tasks folded in here, because a phase must ship: create the docs module, register the
identifier families, add `features/integrations/` to the migrated list, and **anchor the five tables
in the schema brief (`C34`) before the migration.**

#### PHASE 2 — **LAUNCH: a utility connects its own mail server and sends real email through it**

**Deliberately the least glamorous provider first.** No OAuth, no vendor SDK — **it isolates the
substrate's own bugs from a provider's.** Real credential storage, real test send, real failure in
plain words.

**Exit test:** a wrong password produces ***"the mail server rejected the password"*** on screen, and
**the credential is provably absent from the database, the logs and the audit trail.**

#### PHASE 3 — **LAUNCH: a utility connects Google or Microsoft, and the token renews itself**

Where `expires_at`, the renewal path and credential-version rollback earn their keep. **Nothing about
the substrate should change to accommodate them — if it does, phase 1 got the abstraction wrong, and
this is the cheapest possible place to find out.**

**Exit test:** an expiring token raises a **dated** warning before it lapses, and re-authorising
**keeps the connection's entire run history.**

#### PHASE 4 — **LAUNCH: files out and files in — the accounting export, then bank and lockbox import**

**Highest business value and highest risk, deliberately after the pattern has been proved twice.**
The content-hash guard and the per-item savepoint both land here.

**Exit test:** the same bank file uploaded twice records the second as a **refused duplicate naming
the first** — ⚠ **proved against real PostgreSQL, because the SQLite suite cannot see this class of
bug** (hard-won law 14).

Groups `T-5` (Aclarian ERP, 6), `T-7` (Neptune 360, 16 — the largest single vendor) and `T-8` (GIS,
16) land across this phase and the next. **`T-8` is blocked on `R-1`, `R-2` and `R-3`** — do not
start those tasks before the rulings.

#### PHASE 5 — **LAUNCH: a payment taken at a kiosk appears on the customer's account by itself**

**The inbound door.** Its condition — *"only when payment rails are actually being built"* — **has
been met**: a kiosk network's specification has arrived with its duplicate semantics and return
handling.

**Exit test:** a replayed notification is recognised and **applied exactly once**, answered with the
conflict status that provider expects — and **a reversal carrying the same identifier as the payment
it reverses is not mistaken for a duplicate of it.** Demonstrated by replaying a real captured
payload.

⚠ **THE CARD-PROCESSOR HALF OF PHASE 5 (`T-9`, ten tasks) IS CONTINGENT AND MUST NOT START UNTIL
`R-8 q1` IS READ.** Three of four questions are answered (§6); **q1 decides whether a timed-out
charge can ever be retried**, which is the difference between a charge operation and a charge
operation plus a companion outcome query. `T-9.05` additionally waits on `R-4`, `T-9.06` on `R-5`,
`T-9.08` on `R-6`.

**The kiosk half of phase 5 is NOT contingent** — that specification was read, six of its seven
declared axes held, and the one requirement it flags as CRITICAL **turned out to be already satisfied
by our code, because a defect in August taught this product the lesson it depends on.**

### CR-069 · 13 · GATES

| Gate | What it asserts |
|---|---|
| **A new connector adds no code outside `adapters/`** | `P1`, and it is the requester's own sentence. Prove it RED by adding a provider that touches a screen |
| **A credential never reaches a log, an audit row or an error body** | Phase 2's exit test as a permanent check rather than a one-off demonstration |
| **Every declared operation names its idempotency mode and its completion mode** | `C1`, `C10`, `C13`. A manifest missing either is refused at registration, not at run time |

**Existing gates that will bite:** `g07` (eleven 🔒 specs) · `g32` refusal keys, **baseline 0** ·
`g33` five-or-six words · `g31` declared classes · `g13` built-is-not-wired · `g15` i18n parity.

### CR-069 · 14 · WHAT IS DELIBERATELY NOT IN SCOPE

**Twenty of the forty-six stated absences are ruled out of scope, each with its reason and who ruled
it** — read §3.1 of the source before proposing any of them. **The 24 tasks that serve no commitment
are also out**: a task serving nothing is either a missing specification or a task nobody needs.

### CR-069 · 15 · VERSION

Scheme `<release>.<change>.<fix>`. This CR is change **69**. **Each phase gets its own version and
changelog entry**; the CR closes when phase 5 lands.

### CR-069 · 16 · ROLLBACK

**Phases 1–3 roll back cleanly** — no partner holds anything of ours and no money has moved.
**Phase 4 onward does not**: a file handed to an accounting system has left the building, and an
imported bank file has created payments. From phase 4, rollback is *disable the connection and keep
the runs*, never *drop the tables*. **Phase 5 cannot be rolled back at all in the direction that
matters** — a charge that reached a customer's bank is not undone by a migration.

### CR-069 · 17 · HANDOVER

**What this CR does not contain and you will need:** the source artifact itself — 84 figures, 24
wireframes with 61 detail cards, and the per-connector field maps live only there. §8 carries every
specification and §6 every ruling, but **read the source before phase 1.**

**What is already true and you can rely on:** the module is genuinely empty · the six kernels are
verified present · three of `R-8`'s four questions are answered and recorded at commit `e5a4a17e` ·
the screen collision is resolved in §9 · `S147` is the next free number.

**The first hour of phase 1 is verifying §8's statuses against the code.** The module is eleven
lines, so **most will not come back already done** — but that is a measurement, not an assumption.

### CR-069 · 18 · DOCUMENTATION STATUS — written 2026-09-03

**Where it is:** `04-docs/05-modules/13-integrations/` — ⚠ **not `16-integrations/` as §11 says.** The
integrations module already exists there with `BR-INT-001`–`017`, `US-INT-001`–`012` and `EP-INT-01`–`04`,
and the new material continues those series; a second folder for one module would split a money-path
module's rules across two places. Lane judgment, recorded in the decision log 2026-09-03. **`16-` is
therefore free and `CR-070` takes it as `16-work/`.**

**What was written:** `02-business-rules.md` Part 2 — `BR-INT-018`–`053`, 36 rules, every one of `C1`–`C36`
mapped · `06-epics/EP-INT-05`…`13` — 9 epics, 34 stories `US-INT-013`–`046` · `03-field-map.md` Part 2 — the
five tables' DDL, fields, seams, discrepancies I-9…I-16 · `04-flows.md` Part 2 — 12 journeys `J48`–`J59` and
legs on `J14`/`J17`/`J19` · `07-endpoints.md` — 31 endpoints · `05-user-stories.md` and `01-overview.md`
extended. Nineteen questions `OQ-INT-1470`–`1488` in the register.

**On the numbering, an addendum to the decision log's morning row:** read in full, the document's own new
rules are `BR-INT-018`–`036` and its new stories `US-INT-013`–`034` — above the frontier, colliding with
nothing — so no offset was applied to them; the approved bands `018`–`053` and `013`–`046` are filled as the
overview describes. `C1`–`C36` stay as handles, exactly as §11 says.

**Deltas from the confirmation table, stated rather than implied:** endpoints 31 (was *provisional*);
journeys 12 (was 9). **Not done:** journey files in `08-qa/`; B2 anchoring (`C34`, the build lane's first
task); the wireframe pass — the document's 24 wireframes and 61 detail cards live in the unread half of a
32.8 MB file.

### CR-069 · 19 · EXECUTION PLAN — written 2026-09-03

**Where it is:** `04-docs/05-modules/13-integrations/10-execution-plan.md`. The five phases of §12 are kept with their
launch sentences and exit tests; the GL track is a sixth, parallel, blocked track. **19 waves · 122 tasks**, each task
one r11 part (`2a` backend · `2b` frontend · `2c` tests + data · `2d` prove it, plus ground / gate / doc / review /
version), each wave ending in a **five-to-eight-step demonstration clicked in the running product** and a version bump
(PO 2026-09-03: *"each phase/wave should produce tangila eoutcome"*). Every one of the 34 stories `US-INT-013`–`046`
is placed in exactly one wave; Part 1's `001 · 002 · 003 · 004 · 005 · 008 · 009 · 010` are placed and `006 · 007 ·
011 · 012` stay deferred. **Definition of done (PO 2026-09-03, *"based on actual code, and rules that we place …
web walkthorugh before you sign off"*):** every task's *touches* was verified against the code at HEAD `b29edecd`
(the plan's §1 lists where the documentation and the code disagreed — the code won); every wave's exit test asserts
a rule; every wave's `2d` task is a Playwright walkthrough `10-scripts/render-checks/cr069-<wave>-<slug>.mjs`.
**Critical path:** waves A → B reach the phase-1 launch (about four weeks, two people); A → B → C → E → N reach the
phase-5 launch. **Blocked to a boundary and still demonstrated:** `036 · 040 · 041 · 042 · 043 · 045 · 046`; only four
tasks (`O6`, `P3`, `Q6`, `S5`) wait for a ruling before they can start. The TSV rows for `20-wave-tasks.tsv` were
generated from the plan file and are handed to the merging lane; the plan is not yet reflected in `19-execution-sequence.md`.


---

## Rulings — 2026-09-04 · shipped in `2.144.0`

**Thirteen closed, one routed outside this team, two held back.** The register rows
`OQ-INT-1470`–`1488` carry each ruling verbatim; the decision log of 2026-09-04 carries
the batch and its two supersessions. Only the parts that change what a lane does:

* **Four tasks stop waiting.** `Q6` (the GIS night's writes), `S5` and wave `R` (a partner
  reading from us) are unblocked. `P3` is **cancelled**, not unblocked — `OQ-INT-1482` was
  answered *no*, so `US-INT-046`, `S145`, `S146`, `J58` and the two consent endpoints come
  out of this change request. `P1` stays, because a table nothing writes needs something
  that fails when somebody starts writing it.
* **Two signed statements are reversed.** `OQ-INT-1473` supersedes `OQ-160` — the card fee
  comes from the settlement file, so a **$147.50** gap becomes **$137.50** of fee plus a
  **$10.00** chargeback that used to be invisible. `OQ-INT-1479` narrows *Settings is
  System Admin only* to let a clerk press **Test it now** and nothing else.
* **One figure moves in a rule that is cited elsewhere.** `BR-INT-006`'s bulk-email
  threshold is **2,000 bills a cycle**, not 6,000–10,000.
* **`OQ-INT-1470` was answered outside its own options:** the parcel match key comes from
  **new GIS parameters on premises AND units**, which is where `BR-MET-1161` already keeps a
  location. **Which of those identifiers is the key is ours to choose and record** — that is
  now wave `M`/`Q`'s first design task rather than a question.
* **Still open: `1475`, `1476`, `1478`, `1485`, `1486`, and `1477` is routed to the card
  processor.** Two of those five carry a ruling whose number did not match its text; the
  register rows say which and why nothing was read across. **`T-9` does not start.**

**Rollback:** the ruled behaviour is confined to `apps/integrations/mappings.py`,
`runners/serve.py`, one API field name (`decision_pending` → `stays_other`) and eleven
catalogue lines. Reverting `2.144.0` restores the previous copy and the previous refusals;
nothing was migrated and no data was written.

---

## Boundary ruling, 2026-09-05 — where integrations stops and Runbooks starts

⚠ **SHARPENED 2026-09-06 — READ §20 WITH THIS SECTION, NEVER INSTEAD OF IT.** The PO named
the three things integrations keeps, positively, and added **scheduling** to the Runbooks
side: *"We want integration scope about building a conn crore , managing keys/secret,
managing lifecycle of connect - while business logic , scheduling , processing we will take
it in run book."* Nothing below is reversed; **§20 applies it to all nineteen waves** and is
where a reader should go for a per-wave verdict. `BR-INT-054` is amended, not superseded.

**PO, verbatim:**

> "I want integration to just make the conenction nad manage the conenction, Runbooks
> will handle the logic , ETL and record udaptes, and we will abel to keep record,
> audit of it as part of runbooks."

> "right now notng to be done; you just write this rule in the CR69 - and leave it
> there we will handle CR 69 and Runbook together once CR70 is completed"

**What it settles.** Integrations connects, authenticates, holds and watches a
connection, and lands what arrives. It does not transform what it lands, does not write
business records from it, and does not own the record of what was done with it.
Runbooks does the logic, the ETL and the record updates, and keeps the run record and
the audit. Recorded as `BR-INT-054` (**amended 2026-09-06** — see §20).

**Why it was asked, and it was not a hypothetical.** Reading the Runbooks specification
against this change request found five places the two meet:

1. **The scheduler.** Runbooks states it plainly — *"Both integration fetches and
   runbook runs are job kinds on the one existing runner — one scheduler, not two."*
   Wave `G` is that scheduler.
2. **Two events Runbooks subscribes to and integrations does not emit:**
   `batch.landed(connection, batch_id, subject_type)` and
   `feedback.landed(provider, batch_id)`. Six runbooks trigger off them. ⚠ The
   `emit()` that exists in `apps/integrations/codecs.py` is a DIFFERENT thing — it
   writes records out through a codec — and must not be mistaken for this.
3. **The run record.** `IntegrationRun` exists and wave `C` built the language around
   it; Runbooks defines its own run with dry/live mode, trigger and counts. **The
   ruling settles this: they are not the same record and neither absorbs the other.**
4. **The queue**, built by wave `B`.
5. **Outage isolation**, wave `F`, in flight when the ruling was made.

**Effect on wave `F`, which was running at the time: NONE, and the ruling is why.**
Before it, an open question was whether `F`'s isolation should cover *the runner* (so a
slow runbook cannot block an integration fetch) or only *connections*. Under this
ruling connections are integrations' own responsibility and the runner is not, so `F`
stays scoped to connections exactly as briefed. **No lane was redirected and no work
was wasted.**

**Sequencing.** CR-069 and Runbooks are taken together **after CR-070 completes**.
Nothing in this ruling commissions work now. It exists so that no integrations wave
built between now and then puts transformation logic on the wrong side of the line.

---

## CR-069 · 20 · THE BOUNDARY, SHARPENED — 2026-09-06, and applied wave by wave

**PO, verbatim, 2026-09-06:**

> "We want integration scope about building a conn crore , managing keys/secret,
> managing lifecycle of connect - while business logic , scheduling , processing we
> will take it in run book."

⚠ ***"conn crore"* is read as *connection*.** The words are recorded as they were said,
and the reading is written down here rather than the sentence quietly corrected — the
same discipline the register applies to every other verbatim quote.

### 20.1 · What this sentence does to the one before it

**It sharpens `BR-INT-054`; it does not reverse it.** The chain, in order:

| Date | The words | What they settled |
|---|---|---|
| **2026-09-05** | *"I want integration to just make the conenction nad manage the conenction, Runbooks will handle the logic , ETL and record udaptes, and we will abel to keep record, audit of it as part of runbooks."* | What integrations does NOT do. Three things named for Runbooks: **logic · ETL · record updates**. Recorded as `BR-INT-054`. |
| **2026-09-06** | the sentence above | What integrations DOES, as **three items**. And a **fourth** thing named for Runbooks: **SCHEDULING** — a word the 09-05 sentence never used. |

**So integrations keeps exactly three things, and this is now the test every wave below
is put through:**

1. **Building a connection.**
2. **Holding keys and secrets.**
3. **The lifecycle of a connection.**

Everything else the PO named — **business logic, scheduling, processing** — is Runbooks'.

**The one word that moves real work is *scheduling*.** Nothing else in the 09-06
sentence changes a verdict that the 09-05 sentence had not already reached. Scheduling
was unallocated until this ruling, and it is a whole wave.

### 20.2 · The worked case that makes the line concrete

Written into the decision log when the boundary was first ruled, and it is wave `I`
exactly:

> A bank file lands. Integrations connects to the bank, authenticates, pulls the file,
> and records that a batch arrived on that connection — **and stops**. Runbooks reads the
> batch, decides which payment matches which account, writes the payments, and keeps the
> run record and the audit of what it decided.

⚠ **This worked case is the repository's, not the PO's own words** — it was written to
make the ruling concrete and it has not been put back to them for confirmation. It is
quoted here because every verdict below leans on it, and a reader should know its
standing.

⚠ **AND §20.3 NOW CARRIES A BETTER ONE — INVOICECLOUD**, a partner who holds our key *and*
whose key we hold. Read that one if you read only one: with two credentials pointing in
opposite directions the connection half and the meaning half cannot be mistaken for each
other, which is the confusion this example has to work to avoid.

**Read it once more for the half people skip: *records that a batch arrived* is on the
INTEGRATIONS side.** Recognising that a file is one we have already taken is a fact about
the connection, not about the payments inside it. That is why waves `I`, `J` and `N` are
splits rather than clean moves — each of them has a duplicate-recognition half that stays.

### 20.3 · How many connector types there are — and the answer we first gave was WRONG

⚠ **THIS SECTION WAS REWRITTEN THE DAY IT WAS WRITTEN, BECAUSE THE PRODUCT OWNER
CORRECTED IT AND THEY WERE RIGHT.** The first draft presented four authorisation modes as
though each connector had exactly one. **It does not.** The correction is kept here rather
than tidied away, because a taxonomy that the first real partner breaks is worth showing
alongside what broke it.

**PO, verbatim, 2026-09-06:**

> "In integration - for invoicecloud we have both. Cases together they hold ours and we
> hold theirs. They will call our invoice and account APIs and we will call their payment
> APIs for payment records . I hope we are handing both things together and for one
> integration there can be multiple endpoints/ spit to integrate or connect"

**What that says, in our words.** InvoiceCloud is **one commercial relationship with two
credentials pointing in opposite directions**:

* **they hold ours** — we issue InvoiceCloud a key, and **they call our invoice and account
  APIs**;
* **we hold theirs** — we keep a credential of InvoiceCloud's, and **we call their payment
  APIs** to collect payment records.

**Both at once, and one integration may have many endpoints.**

#### The four modes are a property of a CREDENTIAL, not of a CONNECTOR

That is the correction, and it is the whole of it. A connector holds **one or more
credentials**, and **each credential has a mode**. Counting connectors by mode is only
meaningful while every connector happens to have exactly one — which is true of all
eighteen we have today and is **not** true of the first real partner we were asked about.

The counts below are therefore **a census of the eighteen manifests as they stand, not a
taxonomy of what a connector can be**:

| `Auth(mode=…)` | In plain words | Manifests today |
|---|---|---|
| `we_hold_theirs` | the utility gives us a secret for someone else's system and we keep it | **8** |
| `token_exchange` | we swap a credential for a short-lived token, over and over | **4** |
| `they_hold_ours` | **we issue the key**, show it once, and someone else calls us | **2** |
| `none` | public, no credential at all | **4** |

**By SUBJECT there are nine categories** — email 4 · payments 3 · maps 3 · meters 2 ·
accounting 2 · print 1 · messaging 1 · identity 1 · banking 1. That is the catalogue, and
it is not the axis the boundary ruling carves along either.

#### The model cannot express InvoiceCloud today, and it is refused in TWO places

Verified in the code, not assumed:

| Where | What it says | Effect |
|---|---|---|
| `apps/integrations/registry.py:293` | `auth: Auth` — **a single `Auth`**, while `:294` `operations: tuple[Operation, ...]` is a collection | A manifest **cannot declare two modes**. Multiple endpoints per integration already work; multiple credentials do not. |
| `apps/integrations/migrations/0001`, and it is **already shipped** | `EXCLUDE USING btree (connection_id WITH =) WHERE (is_active)` on PostgreSQL, a partial unique index on SQLite | **At most ONE active credential per connection, enforced by the database.** A second one is refused by the engine, not by application code. |

**Why nobody noticed.** Mixed direction is already real — `email_bulk`,
`meters_neptune360`, `payments_sandbox` and `sms_twilio` each carry operations **in both
directions** — but all four ride on **one** credential, so the single `auth` was never
strained. And the two `they_hold_ours` connectors are each one-way: `gl_partner` is all
outbound, `payments_kiosk` all inbound. **No connector we have needs two credentials.
InvoiceCloud is the first.**

⚠ **THE RULE UNDERNEATH IS `BR-INT-025`, AND IT IS `PROPOSED`, NOT CONFIRMED** — *"exactly
one is active per connection, enforced by the database"*. So this is **ours to correct and
not a PO re-sign**: no signed statement is being reversed. But it is built and shipped, so
correcting it costs a migration on a live constraint, which is why it is filed as a defect
(`DEF-INT-4118`) rather than left as a note. **The fix is not designed here** — whether
InvoiceCloud is one connection with two credentials or two connections under one partner is
the fixing lane's decision, and both shapes still need `Manifest.auth` to stop being
singular.

#### InvoiceCloud is the best worked example of the boundary in this document

**And this is why the correction sharpens the ruling rather than muddying it.** Put the
bidirectional case through the three things integrations keeps:

| | Integrations | Runbooks |
|---|---|---|
| **The key we ISSUE to InvoiceCloud** | issue it, show it once, mask it, revoke it, log who used it and when | — |
| **The credential of THEIRS we hold** | store it encrypted, version it, rotate it, warn before it lapses | — |
| **Both connections' health** | reachable · not working · the breaker, per direction | — |
| **They call our invoice and account APIs** | authenticate the caller, refuse one not on the list, record that a read happened | **which** invoices and accounts, in what shape, and what may be seen |
| **We call their payment APIs** | make the call, land the response | **which** payment record matches **which** account, and **when** to go and look |

**Integrations owns both credentials and both connections. Runbooks owns what flows across
them.** That is the same line as the bank-file case in §20.2, drawn through a partner that
points both ways at once — and it is the cleaner illustration of the two, because here the
connection half and the meaning half cannot be confused for one another.

### 20.4 · All nineteen waves

**A + means integrations keeps it whole · a → means it moves to Runbooks whole · a ÷ means
it splits.** Sizes are the plan's own, in people-weeks.

| Wave | What it is | Verdict | Why, against the ruling's own words |
|---|---|---|---|
| **A** | the grid that tells the truth — registry, the five tables, the read API | **+ integrations** | A catalogue of what can be connected, and the tables a connection lives in. **Building a connection**, item (1). Nothing is transformed. **BUILT.** |
| **B** | the modal, the gate, the queue — adapter protocol, worker, server-side gating | **+ integrations** | Item (1) and item (3). ⚠ **The queue is NOT the scheduler.** A queue is how a connection's work runs; deciding WHEN it runs is scheduling. Runbooks runs on this queue — *"one scheduler, not two"* — and does not get a second one. **BUILT.** |
| **C** | the run record, and the word for not knowing | **÷ split — and part of it is BUILT on the Runbooks side** | `BR-INT-054`(3) already settles the principle: a run row saying *this connection authenticated, pulled a file, took three seconds* is **lifecycle**, item (3), and stays. But wave C shipped **per-item results** — the `items` column, `runs.py`, the `RunCard`, and summaries like *86 of 93 · 7 bad addresses*. A record of what happened to row 412 **inside** the file is a record of **processing**, and the ruling puts that in Runbooks. **`OQ-INT-1727`.** |
| **D** | their words, and format as a parameter | **÷ split — and the heavier half is BUILT on the Runbooks side** | Deciding that the kiosk's `ACHCHECK` means our *Bank transfer* is **the ETL lookup**, named in the 09-05 sentence. `mappings.py` (537 lines), `mappings_api.py` (100), `ValueMappingPage.tsx` (18,760 bytes) and **screen S143** all shipped at `2.131.0`. The **codecs** half (`codecs.py`, 820 lines) is different and stays: a codec is how bytes are shaped on the wire, which is landing what arrives — **except its `projections`** (`gl_payment_v1`, `bill_message_v1`), which build a business record out of our data and are ETL. **`OQ-INT-1727`.** |
| **E** | connect day — credential versions, offboarding, the fold | **+ integrations** | The purest wave in the change request: **holding keys and secrets**, item (2), and the lifecycle of a connection, item (3). Nothing here is touched by the ruling. **BUILT (8 of 9 tasks; one review owed).** |
| **F** | one tenant's outage stays one tenant's | **÷ split — and it is the LIVE LANE** | `F1` (timeout, concurrency cap, breaker, backoff, *Not working*) is **item (3)** end to end and is **BUILT**. `F2` is two halves and they fall on opposite sides: the **feedback door** (authenticate → dedupe → reply → persist raw) is landing what arrives and stays; **marking notification rows `delivered`/`bounced` and feeding the suppression list is a record update** and is Runbooks'. That second half is **not started**, and the lane is running now. **`OQ-INT-1729`.** ⚠ **RULED 2026-09-06 — option (a): THE LANE STOPS AT THE DOOR.** The feedback door stays with integrations and is **finished here**; marking the rows `delivered` / `bounced` and feeding the suppression list **wait for Runbooks and are not built now**. Nothing was wasted, because that half had never been started. `F3`, `F5` and `F6` are buildable today — each checked against the line rather than assumed; see the execution plan's wave `F`. |
| **G** | the first beat schedule this product has ever had | **→ Runbooks** (one clause retained) | **This is the wave the 09-06 sentence moves, and it is the whole point of the amendment.** *Nightly means the utility's own midnight*, spreading three hundred utilities so they do not fire together, skipping a run still going, DST, the catch-up policy — every word of it is **scheduling**. Runbooks already asks for it: *"one scheduler, not two."* ⚠ **Integrations keeps one clause: the request-budget COUNTER** — an allowance of 10,000 a week is a fact about our relationship with that provider, item (1). What the scheduler does with the count is Runbooks'. |
| **H** | token lapse averted | **+ integrations** | A credential expiring, a dated warning, re-authorising, credential v(n+1) on the same connection: **items (2) and (3)**, with nothing else in it. ⚠ Its sweep body is *triggered* by Runbooks' scheduler once `G` moves — that is integrations work running on a shared clock, not a split of ownership. |
| **I** | the same bank file twice | **÷ split — and it is the worked case above** | Integrations keeps: the bank connection, the manifest, SFTP-or-upload, `test()`, and **`input_hash` computed before the parse with the duplicate refused naming the first by date** — *records that a batch arrived*. Runbooks takes: `stage_import` / `commit_batch`, the per-row savepoint, **which payment matches which account**, the counts `899 / 1 / 0`, the receipt naming row 412. ⚠ Most of the Runbooks half **already exists in `apps/payments`** (`payment_import.py`); the ruling decides who WRAPS it, not who wrote it. |
| **J** | a remembered destination | **÷ split** | ⚠ **Not a clean integrations wave.** Keeps: the `accounting_file` connection (`destination × codec`), `test()`, the `camt053` codec, and **period + target giving the same file or a refusal naming 5 August** — outbound duplicate-recognition, the same argument as `I`. Moves: **readiness** (*3 accounts still need an export code* is a business judgment about the chart of accounts) and the **Nacha return-code mapping** (`R01 → nsf`, `R02 → other`), which is `D`'s ETL table one module along. |
| **K** | the walk — token exchange, the fetch plan, the file they build ✅ **BUILT 2026-09-06 · `2.204.0`** | **÷ split, mostly integrations** | Keeps: **token exchange in memory, re-minted mid-walk, one credential row after two hours** — item (2), and the sharpest illustration of it in the change request; the fetch plan and paging (how you talk to *this* provider); submit–poll–collect; the safety parameters and `mutates_partner_state`, which govern the request we send over the connection. Moves: the **readings projection** — turning what was collected into our measurement frame is ETL. |
| **L** | readings that arrive late | **→ Runbooks** | Reconcile by natural key, insert four, supersede two, **never touch a reading already billed and raise a correction naming the bill**, list the register differences. That is **record updates and business logic** from the first line to the last, and it is the second of the two things the 09-05 sentence named. Nothing in it is a connection. |
| **M** | the address search and the map | **÷ split, mostly integrations** | Keeps: the `gis_city` connection, the `executor` declaration (`server` · `browser` · `browser_credentialed`), the generated page-security policy, connection records for the two live calls that have none, the breaker, the search endpoint. Moves: **the write** — a picked candidate becoming a premises. ⚠ **But that write is a person pressing Create on a screen, not an unattended run, and the ruling does not say whether it means that kind of write too. `OQ-INT-1728`.** ⚠ **RULED 2026-09-06 — option (a): IT DOES NOT MOVE.** A person's synchronous write stays with the module that owns the screen, so **the write stays here too and nothing of wave `M` moves**. ⚠ **But the PO added a requirement in the same sentence:** the same job must ALSO exist as a batch in two forms — **scheduled** (Runbooks) and **run once on demand** (the trigger is the screen's, the running is Runbooks'). Three ways to do one job, all three built. |
| **N** | the kiosk payment, twice | **÷ split — and the line falls where the manifest already draws one** | Keeps: **authenticate** (the `X-Kiosk-Key` and the source allowlist, *before the body is read*), **dedupe** on the composite key, **reply** `200`/`409`, **persist raw**. Moves: `record_payment` with channel `KIOSK`, the reversal row for a return, `DRIVEUP → OTHER`, showing the risk flag to a clerk. ⚠ **The split lands exactly at `respond_after = dedupe`, which is a boundary the manifest format already has** — the PO's line and the file format's line are the same line. `N1` is payments' own migration and is on neither book. |
| **O** | we do not know | **÷ split, mostly Runbooks — and it stays BLOCKED** | Keeps: **the idempotency key generated and stored before the request leaves**, the same key on every retry, `executor = browser_credentialed`. Moves: what `indeterminate` MEANS, the refused blind Retry, the `charge_status` companion, recording the payment once — deciding what a result means and what to write is business logic. ⚠ **The split does not unblock it.** `OQ-INT-1476` is **ROUTED to the card processor and unread**; `OQ-INT-1478` is **OPEN — answered in part**. Neither is ours to answer: they are facts the processor holds. |
| **P** | allowed, then stopped | **CANCELLED — untouched** | `OQ-INT-1482` was ruled **(c), no** on 2026-09-04. The wave does not ship and **its letter is not reused.** What remains is `P1` and only `P1` — the test proving every write path to `integration_consent` refuses. That guard is on an integrations table and stays here. **The boundary ruling changes nothing about `P`.** |
| **Q** | the night report | **→ Runbooks** | 69,000 parcels sorted into seven classes, per-field authority `auto` · `queue` · `never`, the money-path refusal, the decision queue a clerk works through. **Business logic and record updates**, entirely. Integrations keeps only the `gis_city` connection, which is `M`'s. ⚠ Two things travel with it: it is a **🔒 sensitive path** with a `HUMAN-REVIEW-PENDING` file, so the review obligation moves too; and `OQ-INT-1470`'s ruling handed us a **design job** — *which* of the new GIS identifiers on `premises` and `units` is the match key — which is now Runbooks' to make and record. |
| **R** | a key we issue | **+ integrations** | `they_hold_ours`: we mint the key, show it once, and revoke refuses the partner's very next call. **This is item (2) in its purest form** — the two-manifest corner of the four-way table above. ⚠ **No longer blocked**: `OQ-INT-1481` was ruled (a) on 2026-09-04, so the enable path is a build. `R1` mints identity's companion story and is identity's work either way. |
| **S** | the partner's morning | **÷ split** | Keeps: machine authentication, the allowlist refusal that reveals nothing, the rate limit, **every page is a run with the key's hint as *who***, and the subprocessor register row pointing inward — that is the access log of a connection, item (3), and it is exactly what a manager reads. Moves: **what is in the payload** — `tenderType` through the mapping rows, `projectType`, `accountString` from the ledger codes. Building a business record for someone else is outbound ETL. ⚠ **No longer blocked**: `OQ-INT-1481` closed, `OQ-INT-1480` HELD (out of scope permanently). |

### 20.5 · The three questions this raises, and none of them is a lane's to answer

| Question | Why it is the PO's |
|---|---|
| **`OQ-INT-1727`** — waves `C` and `D` shipped work that now sits on the Runbooks side. Does it move when Runbooks is built, stay here as a named exception, or does Runbooks read it where it is? | A ruling that collides with something already signed and shipped. The supersession has to be **stated, never assumed** — and about **three people-weeks** are already spent (`C` 1.5 + `D` 1.5), with screen **S143** live. |
| **`OQ-INT-1728`** — ✔ **RULED 2026-09-06, option (a)** — does *"record updates go to Runbooks"* cover a write a **person** makes synchronously on a screen (wave `M`: Priya picks an address and presses Create), or only unattended runs? | **ANSWERED: only unattended runs.** The synchronous write stays with the module that owns the screen. ⚠ **And the PO added a second requirement:** the same job must ALSO be available as a batch, **scheduled** and **run once on demand** — three ways to one job, and the last two are not the same thing. |
| **`OQ-INT-1729`** — ✔ **RULED 2026-09-06, option (a)** — wave `F` is **running now** and the unbuilt half of `F2` is on the Runbooks side. Does it stop, or land here and move later? | **ANSWERED: it stops at the door.** The feedback door is integrations' and is finished here; the record-marking and the suppression list wait for Runbooks. ⚠ **The collision was with a plan, not with code** — that half had never been started, which is why the answer cost nothing. |

### 20.6 · What this does to the size — the honest number

**The plan's own sizing, added up.** `A`–`E` are built: **15 people-weeks**. What is left,
`F`–`S` with `P` cancelled, is **about 40 people-weeks** (39.5 at the low end of the two
waves the plan sizes as *"one or two people"*, 43.5 at the high end).

⚠ **THE FIGURE OFTEN QUOTED AS *"about ten weeks"* IS A DIFFERENT MEASUREMENT AND IS BEING
READ AS THIS ONE.** §4 of the execution plan says *"About nine and a half weeks along the
spine"* — that is the **calendar length of the critical path** `A → B → C → E → N` **with
two people on it**, not the total effort, and it deliberately excludes everything running
in parallel beside it. Ten calendar weeks and forty people-weeks are both true and they
answer different questions.

**Splitting the remaining ~40:**

| | People-weeks | Which |
|---|---|---|
| **Integrations retains** | **≈ 20** | `H` and `R` whole (≈ 6), plus its share of the eight split waves (≈ 14) — the doors, the keys, the duplicate-recognition halves, the access log |
| **Runbooks inherits** | **≈ 21** | `G`, `L` and `Q` whole (**10**), plus its share of the splits (≈ 11) — the mappings, the matching, the reconcile, the night, the record writes |

⚠ **The share of each split wave is an ESTIMATE and is marked as one.** The whole-wave
figures are the plan's own; the split shares are this document's judgment and no more.

**The planning fact, stated plainly: this is not a small trim. CR-069 stops being one
project of about forty people-weeks and becomes two of about twenty.** Runbooks does not
end up carrying *most* of it, but it carries **as much as integrations does** — and it
carries it with **no module folder, no stories, no epics and no home in this repository**.

### 20.7 · What Runbooks inherits — a list, not a plan

**Runbooks has no module folder here and one is NOT invented by this document.** Where it
lives is undecided. This is the list the Runbooks work picks up when it starts:

1. **The scheduler, whole** — the beat schedule, the due sweep, the tenant-midnight and DST arithmetic, the three-hundred-utility spread, the skip row, the catch-up policy (`G`).
2. **The reconcile of late readings** — natural key, supersede, the billed-reading refusal and its correction (`L`).
3. **The GIS night** — seven classes, per-field authority, the decision queue, and its 🔒 review obligation (`Q`).
4. **The value mappings** — their words to ours, and the Nacha return codes with them (`D`, `J`).
5. **The matching and writing of imported payments** — which payment belongs to which account (`I`, `N`).
6. **The record of what was decided** — per-item run results and the audit of a transformation (`C`).
7. **The readings projection** and the outbound business payload (`K`, `S`).
8. **The record updates that follow a landing** — notification rows marked delivered or bounced, and the suppression list (`F`). ⚠ **CORRECTED 2026-09-06 — the premises written from a picked address is NO LONGER ON THIS LIST.** `OQ-INT-1728` was ruled option (a): a person's synchronous write on a screen stays with the module that owns the screen, so wave `M`'s Create **stays with integrations**. What Runbooks inherits from `M` instead is the **batch forms of that same job** the PO asked for in the same sentence — the **scheduled** run, and the **running** half of the run-once-on-demand button whose trigger stays on the screen. `OQ-INT-1729` was ruled option (a), which leaves item 8's `F` half exactly as written and confirms it is not built now.

**Sequencing is unchanged and was not put back to the PO.** `CR-069` and Runbooks are
taken together **after CR-070 completes** — PO, 2026-09-05: *"we will handle CR 69 and
Runbook together once CR70 is completed."* **Nothing here commissions work now.**

### 20.8 · Every pending wave re-checked against a two-credential partner (2026-09-06)

**The question asked of each wave: does it assume one credential per connector, and does
that change its verdict?** Checked against the code, not the plan text.

| Wave | Assumes one credential? | Does the verdict move? |
|---|---|---|
| **`E`** (BUILT) | ⚠ **YES, and it is the wave the defect lands in.** `record_credential`, the version chain and the shipped `EXCLUDE … WHERE is_active` are all *per connection*, not per credential. | **No — `E` stays integrations**, and more firmly than before: holding two credentials for one partner is item (2) twice over. But `E`'s model is what `DEF-INT-4118` changes. |
| **`R`** (a key we issue) | No — `gl_partner` is one-way outbound and needs one key. | **No — stays integrations.** ⚠ But for a bidirectional partner `R` is **half the job**: `R` builds the key we ISSUE, `E` holds the key we KEEP, and InvoiceCloud needs both on one relationship. `R` is not wrong; it is incomplete, and the incompleteness is the defect rather than the wave. |
| **`K`** (token exchange over a two-hour walk) | No. `meters_neptune360` is **already bidirectional** — operations in and out — and rides one credential, which is exactly why nobody hit the limit. | **No — stays integrations.** ⚠ One wording consequence: `K`'s exit test *"one credential row before and after"* is true **per credential**; if credentials become plural per connection it must say so, or it will read as a claim about the connection and quietly become wrong. |
| **`S`** (the partner's morning) | No — one-way served. | **No — stays a split.** ⚠ Worth recording: `runners/serve.py`, built here for a finance partner reading payments and bills, **is the same door InvoiceCloud needs to call our invoice and account APIs.** The inbound half of a bidirectional partner is `S`'s shape, not a new one. |
| **`N`** (kiosk) · **`O`** (card charge) | No — each one-way. | **No.** ⚠ *"We call their payment APIs for payment records"* is a **collection**, closer to `K`'s fetch than to `O`'s charge; `O` is about taking money, not reading records. |
| **`G`** · **`L`** · **`Q`** (the three that MOVE) | **No — none of them touches a credential at all.** | **No.** |
| **`I`** · **`J`** · **`M`** · **`C`** · **`D`** · **`F`** | No. | **No.** |

⚠ **THE RESULT IS ITSELF EVIDENCE THE LINE IS DRAWN IN THE RIGHT PLACE.** Every wave that
assumes one credential is on the **integrations** side, and **not one of the three waves
moving to Runbooks knows what a credential is.** A modelling limit about credentials
therefore lands entirely inside integrations' own scope and changes nothing about the
split. **No verdict in §20.4 moves.**

**What it does change is a size, slightly and honestly:** `DEF-INT-4118` is repair work on
**built** wave `E`, not on the pending backlog, so it does not come out of the ≈ 20
people-weeks integrations retains — **it is added to them**, and it is not sized here
because the fixing lane has to choose its shape first.

## CR-069 · 20.9 · THE FOUR DIRECTIONS — 2026-09-06, and every wave tagged with its own

**PO, 2026-09-06, confirming the model and commissioning this section, verbatim:**
> *"1 · The split, all four directions - this is good; please update CR and execution plan
> accordingly for Cr 69"*

**The model whole is `04-docs/05-modules/13-integrations/11-the-runbooks-boundary.md`; the rules
are `BR-INT-055`–`065`; the batch and its states are that module's `04-flows.md` Part 3; the
infrastructure requirement is its `10-execution-plan.md` §9.** ⏸ **This commissions nothing** —
`BR-INT-054` still says *"NOTHING IS TO BE BUILT AGAINST THIS RULE YET"*.

### 20.9.1 · Why this section exists at all

**§20.4's nineteen verdicts were drawn BEFORE the four directions were named.** Every verdict
still stands and **not one is re-drawn here** — what is added is the **direction**, because the
direction is what decides the SHAPE of the work, and a lane that knows only *`÷ split`* does not
yet know whether it is building a batch, a door or a read.

| Direction | Who starts it | The shape it takes |
|---|---|---|
| **We pull** | **Us** — schedule or one-off | **The batch**: schedule or one-off · chunk size · walk records · the nine states · the two failure buckets |
| **We push** | **Us** — schedule or one-off | **The batch, mirrored** — same states, same failure handling, records travelling the other way |
| **They push** | **Them**, whenever | **The door**: authenticate → dedupe → reply fast → persist raw — **and it STOPS THERE** |
| **They pull** | **Them**, whenever | **A read**: their key · where they may call from · how often · on/off · who read what and when. ⚠ **NO BATCH AND NO SCHEDULE** |

⚠ **THIS IS NOT NEW SCHEMA.** These four are exactly the quadrants the module already runs on —
`runners/__init__.py`: *"direction × initiative picks the runner, and there is no fifth cell"* —
and `BR-INT-028` already declares both axes **per operation**. **Nobody should add a `direction`
field.** ⚠ **And a provider is a set of OPERATIONS, so classify an operation and never a
provider:** the email provider is *we push* for the messages we hand it and *they push* for the
bounce it reports back, which is why wave `F` below carries two directions.

⚠ **THE THIRD TRIGGER IS THE THING MOST LIKELY TO BE MISSED. WHEN THEY START IT, THERE IS NO
SCHEDULE** — the trigger is **their call**, a third trigger beside *scheduled* and *one-off*
(`BR-INT-057`). *They push* and *they pull* have **no cadence, no due time, no next run and no
catch-up policy**. **Nobody should build a scheduler for a doorbell**, and **every word of
`BR-INT-024` applies to the two directions WE start and to no others.**

⚠ **AND SAY WHY THE DOOR IS WHERE THE LINE FALLS, BECAUSE THE REASON IS OPERATIONAL RATHER THAN
ARCHITECTURAL — this is the sentence that stops someone "simplifying" the two halves back
together:**

> **The vendor is waiting on our reply and will re-send if we are slow, so answering the door
> must never wait on processing.**

Fold the processing into the door and a slow runbook becomes a **duplicate delivery from every
vendor at once** — not a slow screen, but a correctness failure on a money path arriving as a
retry storm exactly when the system can least absorb it.

### 20.9.2 · All nineteen waves, by direction

**The verdict column is §20.4's, unchanged and repeated only so the two can be read together.**

| Wave | What it is | §20.4 verdict | **Direction** | What the direction decides |
|---|---|---|---|---|
| **A** | the grid that tells the truth | `+ integrations` | **substrate — all four** | The catalogue and the five tables every direction lives in. No direction of its own. |
| **B** | the modal, the gate, the queue | `+ integrations` | **substrate — all four** | The queue and worker all four run on. ⚠ The queue is **not** the scheduler. |
| **C** | the run record, and the word for not knowing | `÷ split` | **substrate — all four** | Every quadrant writes a run row. ⚠ Its per-item results are the **batch's** record, not the connection's — which is the whole of `OQ-INT-1727`. |
| **D** | their words, and format as a parameter | `÷ split` | **inbound interpretation** (*we pull* · *they push*); **codecs serve all four** | The mappings are the ETL lookup for what ARRIVES. ⚠ They are **also read outbound** by `S`'s projection, so they are Runbooks' in both directions. |
| **E** | connect day — credential versions, offboarding | `+ integrations` | **substrate — all four** | Keys and lifecycle. The purest `BR-INT-054`(b)+(c) wave. |
| **F** | one tenant's outage stays one tenant's | `÷ split` — **LIVE LANE** | ⚠ **TWO DIRECTIONS.** `F1` + the send half: ***we push*** · `F2`'s feedback door: ***they push*** | The clearest case that a wave is not one direction. `F1`'s breaker guards **our calls out**; `F2` is **the door** — and `OQ-INT-1729` (a) says it **stops there**: marking rows `delivered`/`bounced` and the suppression list wait for Runbooks. |
| **G** | the first beat schedule | `→ Runbooks` (one clause kept) | ***we pull* + *we push* ONLY** | ⚠ **There is nothing for a scheduler to do in the other two directions.** A lane must not read `G` as giving *they push* or *they pull* a cadence — they have none (`BR-INT-057`). |
| **H** | token lapse averted | `+ integrations` | ***we pull*** | We go to the provider for a new token; the sweep is ours-initiated. Its body is *triggered* by Runbooks' clock — triggering is not owning. |
| **I** | the same bank file twice | `÷ split` | ***we pull*** | **The batch, in full**: schedule or one-off, chunk size, walk records, the nine states, the two buckets. The worked case of §20.2. |
| **J** | a remembered destination | `÷ split` | ***we push*** | The mirror of `I` — a file out. Same batch, same states, same failure handling. |
| **K** | the walk — token exchange, the fetch plan | `÷ split` | ***we pull*** | submit–poll–collect is we-initiated end to end. |
| **L** | readings that arrive late | `→ Runbooks` | ***we pull* — with NO integrations half of its own** | ⚠ **Worth stating, because it looks like an exception and is not:** every *we pull* wave has an integrations half, and `L`'s is **wave `K`'s** connection (`L` depends on `K`). That is why *"nothing in it is a connection"* is true and `→ Runbooks` whole is right **here** — and would be **wrong** for a *we pull* wave that owned its own connection. |
| **M** | the address search and the map | `÷ split, mostly integrations` | ***we pull*** | Including `executor = browser`: the viewer's browser is still **us** initiating, so the direction does not change. ⚠ `OQ-INT-1728` (a) keeps the synchronous Create here; the **batch forms** of that same job are Runbooks'. |
| **N** | the kiosk payment, twice | `÷ split` | ***they push*** | **The door.** Authenticate (the `X-Kiosk-Key` and the source allowlist, before the body is read) → dedupe → reply → persist raw. **And it stops there** (`BR-INT-058`). |
| **O** | we do not know | `÷ split, mostly Runbooks` — **BLOCKED** | ***we push***, with a ***we pull*** follow-up | The charge goes out; *"go and ask the processor"* comes back. ⚠ Two directions in one story, which is why `indeterminate` needs a word of its own. |
| **P** | allowed, then stopped | **CANCELLED** | **none** | `OQ-INT-1482` ruled (c) on 2026-09-04. The wave does not ship and **its letter is not reused.** |
| **Q** | the night report | `→ Runbooks` | ***we pull*** | The fetch is `M`'s `gis_city` connection; the sorting of 69,000 parcels into seven classes is the ETL. Same shape as `L`. |
| **R** | a key we issue | `+ integrations` | ***they pull*** | ⚠ **NO BATCH AND NO SCHEDULE — a reader must not go looking for one.** We mint the key, show it once, revoke it. **There is no payload at all**, which is exactly why it is `+ integrations` **whole**. |
| **S** | the partner's morning | `÷ split` | ***they pull*** | ⚠ **NO BATCH AND NO SCHEDULE.** Nothing arrives, so nothing needs mapping — **but that removes INBOUND interpretation, not the OUTBOUND projection.** It splits *only* because it composes a payload (`tenderType` through the mapping rows, `accountString` from the ledger codes), and building a business record for someone else is outbound ETL. |

**Nineteen waves; `P` is cancelled, so eighteen carry a direction. By direction:** *we pull* —
`H` `I` `K` `L` `M` `Q` (six, plus `O`'s follow-up leg) · *we push* — `J` `O` (two, plus `F`'s
send half) · *they push* — `N`, `F2`'s door (two) · *they pull* — `R` `S` (two) · **substrate,
serving all four** — `A` `B` `C` `E` (four), with `D` inbound-facing and `G` serving only the two
we start.

### 20.9.3 · What the direction changes for a lane picking up a wave

1. ***We pull* or *we push* → you are building a BATCH.** Read `04-flows.md` Part 3: nine steps,
   nine states, the mode chosen at the start, failure sorted into *retry* and *needs a person*.
   `BR-INT-024`'s cadence rules apply to you.
2. ***They push* → you are building a DOOR, and you stop at it.** Authenticate, dedupe, reply
   fast, persist raw. **No cadence, no next run.** The `apply` half is Runbooks' — and the reason
   is that the vendor is waiting and will re-send.
3. ***They pull* → you are building a READ.** Their key, where they may call from, how often,
   on/off, and a record of who read what and when. **No batch, no schedule, no next run.** If
   there is a payload you compose, that projection is Runbooks' — which is the whole of the
   difference between `R` and `S`.
4. **A wave can carry two directions** (`F`, `O`). **Classify the OPERATION, never the provider.**

### 20.9.4 · The one place the model and a ruled verdict needed reconciling, stated rather than re-drawn

The model's summary sentence for *they pull* — *"integration settings do the whole job"* — **read
literally would make wave `S` `+ integrations` whole**, contradicting a verdict the PO ruled the
same day. **The verdict stands.** The reconciliation is that *"no vendor data to interpret"* is a
statement about **what arrives**, and in this direction nothing arrives; it is **not** a claim
that the direction is free of business logic, because there is still a payload we compose and
composing one is a **projection**, which §20.4 already puts on the Runbooks side. **Recorded here
because a lane reading only the summary sentence would draw the wrong line** — and per law 13's
first case, a ruled verdict colliding with signed work is not a lane's to re-draw.
