## CR-068 — The customer self-service portal: fifty-six specifications, seventy-seven screens, five releases, and the one thing this product cannot do at all

> **⚠ READ THIS FIRST IF YOU ARE A NEW SESSION.** This CR was written on 2026-09-03 in a session
> that was about to run out of context, at the Product Owner's explicit instruction: *"the toekn in
> this session are going to be over soon., we will ahve to continue the build from another log hence
> ensure you write the CR in very much detials"*. **It is therefore written to be built from without
> the conversation that produced it.** Everything a lane needs is in this section or is cited by a
> path you can open. If you find yourself needing a fact that is not here, that is a defect in this
> CR — file it (`10-scripts/file_defect.py`) rather than guessing, because guessing is exactly what
> `CR-059` §0d records as the cause of a 50% gap between what was agreed and what was built.

### CR-068 · 0 · CAPTURE — the Product Owner's words, verbatim

**The request, 2026-09-03:**

> *"please write next CR in details for Customer Web portal using this The customer self-service
> portal - ensure we dont loose any important items - prepare implmentation plan - in phases - the
> toekn in this session are going to be over soon., we will ahve to continue the build from another
> log hence ensure you write the CR in very much detials - also confirm what will be folder
> structure for this - how you will add this in current repo"*

**Four rulings arrived in the same hour and all four are already in `12-governance/02-decision-log.md`
(commit `9d766f07`), verbatim, with their reasoning. They are repeated here because a lane building
from this CR must not have to go and find them:**

1. > *"Allocate new numbers and code"* — re-opening the exhausted `S` band for the staff app's 31
>    un-numbered screens. **Not this CR's scope**, but it is the ruling that establishes the PO
>    allocates screen numbers, which is why ruling 2 exists.
2. > *"You can assign number CWP-nnn - Assig all unqie numbers"* — **the portal's screens get their
>    own series, outside the `S` namespace.** §9 below is that allocation.
3. > *"/{utility-name}/portal/....- we will use this"* — **the portal's address.** This answers the
>    blueprint's `PQ-13`.
4. > *"Inlcude all these features - A gate on the four write points."* — **the four-write-point
>    boundary is a machine check from release one, not a sentence in a design document.**

**The source document** is the artifact *The customer self-service portal* (Customer Portal
Blueprint), read at product version **2.125.4**, commit `ffa4a172`, on **2026-09-02**.

### CR-068 · 0b · WHY THIS DOCUMENT CAN BE TRUSTED WHERE `CR-059`'s COULD NOT

**`CR-059` §0d records this repository's most expensive documentation failure:** the payments source
document mixed *descriptions of absences* with *specifications*, the CR was built from the register
alone, and three of the Product Owner's four complaints on the deployed build were absences the
document had described and nobody had ever scheduled.

**The portal blueprint fixed that failure before it happened, and this is the single most important
fact about it.** It marks every statement as one of two things and says the rule out loud:

> *"Description — grey rail: a statement about what the code does today, including an honest
> statement that something is missing. **It commits nobody to anything.** Commitment — accent card: a
> change specification... **If a thing is not in a commitment card, nobody has undertaken to build
> it.**"*

**Then it audits itself.** §24 walks all twenty-two sections, finds **59 statements that something
does not exist**, and pushes every one through one of two doors: **48 become a specification** (38
new, 10 folding into one already minted) and **11 are ruled out of scope** (9 of those deliberate
design). Its own words: *"THERE IS NO THIRD DOOR. An absence with neither a specification nor a
ruling behind it is the bug this register exists to fix: it reads as a promise and nobody made one."*

**Consequence for this CR:** §8's fifty-six specifications ARE the scope. A lane may build from them
without re-reading the prose, which was not true last time.

### CR-068 · 0c · STEP 0 — WHAT MOVED UNDER THE DOCUMENT BETWEEN 2026-09-02 AND 2026-09-03

**The blueprint says of itself:** *"Every 'as built' statement in this document was true at version
2.125.4, commit `ffa4a172`, on 2 September 2026. Re-verify any of them against the code before
trusting or acting on one."* Verified on 2026-09-03 at `2.128.2`:

| The document says | Measured 2026-09-03 | Consequence |
|---|---|---|
| *"The inbound payment webhook file is a single line of description with no code under it."* | **FALSE NOW.** `06-backend/apps/payments/webhooks.py` is **577 lines**, built the same day as `CR-060` C21 with **15 tests**, idempotent, with the retry designed first | **`CP-09` may already be substantially done.** Verify before building it. The gateway half is still absent. |
| *"There is no table holding a customer's card or bank details."* | **STILL TRUE.** `payment_methods` is named in B2 §2 as the customer's stored instrument and `apps/payments/models.py:65` states in its own docstring that the TABLE NAME is taken by the staff tender lookup and this is **not** it | **`CP-08` is real, and it carries a name collision that will bite.** Resolve the name before the migration. |
| *"Autopay records a promise, not a charge."* | **STILL TRUE.** `apps/payments/autopay.py`, 337 lines | `CP-08`/`CP-09` unchanged |
| *"the portal's screens are labelled G1 to G14, P1 to P48 and B1 to B7"* (§23) | **FALSE.** `P49`–`P54` are drawn screens with cards of their own | The count is **75**, not the 79 its own headline claims. §9 allocates 75. |
| *"79 screens proposed"* (headline) | **FALSE.** 14 + 54 + 7 = **75** | Four numbers that would have named nothing |
| *"the repository had no `main`, `master` or `develop` branch"* | **TRUE** — work is on `claude/payments-cr-artifacts-k3s9j2` | The document could not check the live version and says so honestly |

**⚠ AND THE DOCUMENT NAMES ITS OWN COLLISION WITH THE LIVE SPEC SERIES.** §24: *"The repository does
have a live series... `CS-1` to `CS-38` — 37 live specifications plus the withdrawn `CS-24`. Three of
them already cover work in this document."* Those three are **`CS-1`** (the card/ACH gateway),
**`CS-3`** (the customer portal itself) and **`CS-9`** (autopay when rails exist). **All three are
carried in `CR-059` as deliberately v2 / out of scope** — task rows 68, 71 and 73. §2 below states
that supersession rather than leaving it to be inferred.

### CR-068 · 1 · CLASSIFY

**A new capability, not a defect and not a correction.** The product has one kind of user in it —
staff — and this adds a second front door. Under `12-governance/13-change-process.md` §1 an ambiguous
item is a DEFECT rather than a change; nothing here is ambiguous, because the blueprint's §1 records
that the absence was *"not an oversight; it was a deliberate scope line, and the product says so out
loud in several places."*

**Three things inside it are nevertheless defects and are marked as such in §8:** the notification
catalogue lists `portal` among channels this platform does not have (`CP-17`); the account record
already carries a **portal access switch, a paperless flag and an SMS flag** that are wired to
nothing; and account notes carry a **visible to the customer** tick that is inert. The blueprint's
own phrase for all of it is *"capture-only, wired to nothing, waiting"* — which is hard-won **law 2**
(*built is not wired*) sitting in the product for months.

### CR-068 · 2 · WHAT SIGNED STATEMENT IS BEING REVERSED — quoted, never summarised

**(a) `CR-059`'s v2 scope line.** `CR-059` §13 places `CS-1`, `CS-3` and `CS-9` out of scope, and its
task rows 68, 71 and 73 carry `v2`. Those rows were reported to the Product Owner on 2026-09-03 as
*"the five v2 items we agreed are out"*. **This CR claims all three.** They stop being out of scope
and become `CP-08`, `CP-09`, `CP-10`, `CP-38`, `CP-48` (the gateway family) and `CP-01` (the portal
session). **`CR-059`'s rows 68, 70, 71, 72 and 73 must be stamped `SUPERSEDED BY CR-068` in the same
commit that opens release five** — not before, because until then `CR-059`'s statement is still true.

**(b) Document storage's v1 scope line.** Signed with uploads staff-mediated and *"a consumer upload
portal deferred to v2"*. `CP-25` and the request surface need customer-side upload with the same
allow-list and size cap (the malware scan this sentence named is SUPERSEDED (PO 2026-09-22 / 2026-09-23 → no malware scan on upload), `DEF-SHL-6347`). **This is a re-sign, not a lane's call** — route it through
`HUMAN-GUIDE §6` before building the upload half.

**(c) The notification catalogue's own statement** that `portal` is a channel this platform does not
have, *"with the reason written in: a portal delivery flag would be a switch with nothing behind
it."* `CP-17` puts something behind it. The catalogue entry is amended, dated, not deleted.

**(d) NOTHING IN B4 OR B5 IS TOUCHED.** No billing figure moves. The portal reads money and never
computes it — `PR-28` says the bill comparison *"must never disagree with the bill it explains"*.
**If a lane finds itself computing a charge, it has left this CR's scope.**

### CR-068 · 3 · IMPACT — the ten surfaces

| Surface | Impact |
|---|---|
| **Rules** | 50 inherited rules (§7). New module rules under a new prefix — see §11 on `BR-CWP-#####` |
| **Schema (B2)** | New: portal credentials, portal sessions, delegated users, stored instruments, interruption records, help answers, tips, service centres, portal settings, customer-submitted reads. **All tenant-scoped, all RLS FORCE** |
| **API (A11)** | A whole new edge — see §11. The portal reaches the portal edge only |
| **Screens (A1)** | **None.** The portal does not enter A1's `S` series — ruling 2. §9 is its own register |
| **Enums (A5)** | Portal role set; help-answer statuses; interruption states; delegated-permission set |
| **Glossary (A16)** | *portal session*, *delegate*, *guest surface*, *quick pay*, *stored instrument* |
| **Open questions** | 9 open (§10), 4 answered by today's rulings, 9 answered on 2026-09-02 |
| **Demo fixture** | A portal customer, a landlord with a delegate, a multi-account login, published help content, one interruption |
| **Journeys (08-qa)** | 18 flows drawn in the blueprint; each becomes an e2e journey |
| **Gates** | At least four new — see §13 |

### CR-068 · 4 · WHAT IS ALREADY BUILT AND IS NOW WRONG

**Nothing is wrong. A great deal is inert, and that is the difference worth naming.** The blueprint's
§1: *"this document is not a wish list. It is a map of a door that the building was framed for."*

Already there and usable by the portal without change: the customer record with its identity fields ·
the account and its balance machinery · issued bills and their rendered documents · the eleven-state
service-request lifecycle **with four customer transitions already defined** · the dispute marker and
its ageing · the three protections with their lifetimes enforced · payment plans with four statuses ·
level pay with its re-levelling and settle-up · the collections ladder with every date and figure
already a configured setting · the anonymous throttle at sixty requests a minute · eleven locale
catalogues · tenant isolation with RLS FORCE.

**The blueprint's own estimate, and it should be tested rather than trusted:** *"several are expected
to come back already done, because a large part of this blueprint is a view over machinery that is
finished and simply has no screen in front of it."*

### CR-068 · 5 · SIZE, AND THE PLAIN-ENGLISH CONFIRMATION

| | This CR | `CR-059` (payments) | `CR-060` (finance) |
|---|---|---|---|
| Specifications | **56** | 37 | 20 |
| New screens | **75** | 12 | 9 |
| Inherited rules | **50** | — | — |
| Open questions | **9** | 2 | 2 |
| Releases | **5** | — | — |

**This is the largest change request in the repository, by roughly two to one.** It is written as one
CR with five release phases (§12) rather than five CRs, because the phases share one schema, one
edge, one session model and one set of gates — splitting them would duplicate §7, §11 and §13 four
times and invite exactly the drift `CR-059` §0d.2 records when two CRs collided over a tab count.
**Each phase is independently shippable and independently useful**, which is the blueprint's own
argument and is correct.

### CR-068 · 6 · THE THIRTEEN RULINGS IN FORCE — nine from 2026-09-02, four from 2026-09-03

**The blueprint states these do not expire:** *"Descriptions go stale; rulings do not. The nine
decisions of 2 September... stay in force until another decision supersedes them — re-reading the
code cannot expire a decision a person took."*

| # | The ruling | What it changes |
|---|---|---|
| R1 | **Customer credentials get their own store** | Not a fourth staff role and not a new party — a password and a session attached to the customer record that already exists |
| R2 | **Payment gateways are a later stage** | The portal is built first. Seven screens wait; every other Pay control appears and is held |
| R3 | **The Pay control still appears, disabled** | Visible, in its normal place, carrying its reason. **Never hidden, and never live-but-inert** |
| R4 | **Post and email remain the delivery record for notices** | The portal is a convenience copy and must show what was sent, when, and by which route |
| R5 | **Paperless is a recorded consent** | Timestamp, wording version, and a way to withdraw |
| R6 | **Existing paperless customers are not asked again** | The consent is taken on the new-connection form instead, applying from the next customer onward |
| R7 | **Quick pay identifies on bill number plus postcode** | Shows the amount owing and a masked name. Nothing else about the account |
| R8 | **Per-tenant switches on the big five** | Quick pay, self-read, plans, requests, outage. **All on for a new tenant except self-read** |
| R9 | **Outage reporting ships; the public status page waits** | A report lands on the request worklist. The status page needs somebody keeping it current out of hours |
| R10 | **The portal's screens are `CWP-nnn`** (2026-09-03) | §9. Outside the `S` namespace |
| R11 | **The portal lives at `/{utility-name}/portal/…`** (2026-09-03) | Answers `PQ-13`. See §11 — and note the correction there |
| R12 | **A gate on the four write points** (2026-09-03) | `PR-17` becomes a machine check in release one, not a sentence |
| R13 | **Allocate new numbers and code** (2026-09-03) | Establishes that screen numbers are the PO's to allocate; `R10` is its consequence |

### CR-068 · 7 · THE FIFTY RULES THE PORTAL INHERITS — `PR-01`–`PR-50`

**These are the blueprint's Appendix A, and they are the acceptance criteria for every specification
in §8.** A lane that builds a `CP-` row without checking it against these has not finished it.
`PR-01`–`PR-12` restate rules this repository already holds (CLAUDE.md hard rules and B14); the rest
are portal-specific and are new law under `BR-CWP-` when written into the module (§11).

| # | The rule |
|---|---|
| **PR-01** | Money is stored to four decimals, percentages to six, and both display to two. Rounding happens at finalisation and display, never during the arithmetic. |
| **PR-02** | Consumption always carries its unit. Never assume gallons, kilowatt-hours or therms. |
| **PR-03** | Issued bills, payments and journal entries are never updated or deleted. Corrections are new rows. |
| **PR-04** | Every money action writes an audit entry. |
| **PR-05** | Payment webhooks must be idempotent — the same event arriving twice changes nothing. |
| **PR-06** | No internal reference is ever visible: no database id, no rule number, no route, no file name. |
| **PR-07** | On-screen text is capped: a label is three words, a fact or an instruction is six words a sentence, and the reason a thing works that way is zero words. |
| **PR-08** | A form that writes money or service state shows what it will do before the button that does it. |
| **PR-09** | Destructive commits use the danger button, outlined and filled on hover, never the standard primary. |
| **PR-10** | Row actions are icons; one table type; two button sizes. |
| **PR-11** | Every list has an empty state that says what is missing and what fills it. Never a blank table. |
| **PR-12** | Print is the floor on bills, receipts, notices and plan letters, whatever the customer chooses. |
| **PR-13** | A portal login is never a staff login. They share no table, no session and no permission catalogue. |
| **PR-14** | Every portal action is recorded against the person who took it — the invited bookkeeper, not the account holder. |
| **PR-15** | A guest sees an amount and a status, never a person. |
| **PR-16** | A customer never sees another customer's data, and never sees another utility's. The account boundary is enforced by the query, not by the screen. |
| **PR-17** | **The portal may write in four places only: a payment, a service request, a meter reading, and its own preferences.** (R12 makes this a gate.) |
| **PR-18** | The portal may never write on an issued bill, may never decide where a payment lands, may never grant a protection or a hold, and may never change who holds an account. |
| **PR-19** | A form a stranger can fill may create work, never change an account. |
| **PR-20** | A public reference lookup returns progress, never data. |
| **PR-21** | The invitation to create a login is the last step, never the first. |
| **PR-22** | Matching an account is not proving identity, and the two states stay separate. |
| **PR-23** | A one-time code goes only to a contact already held on the account, never to an address typed on the previous screen. |
| **PR-24** | A password-reset form gives the same answer whether or not the address has a login. |
| **PR-25** | Balances across several accounts on one login are shown separately and never merged into one invoice. |
| **PR-26** | A corrected bill and its replacement both stay in the customer's list forever, the original naming its replacement. |
| **PR-27** | The portal serves the rendered bill document pinned to the template it was issued with, and never re-renders one of its own. |
| **PR-28** | The bill comparison is arithmetic over existing reads and must never disagree with the bill it explains. |
| **PR-29** | A customer-submitted reading goes through exactly the same validation as a staff-entered one, and lands awaiting review rather than in a bill run. |
| **PR-30** | A submitted read later superseded by a real one must not leave the customer charged for both. |
| **PR-31** | A stored payment instrument is a token from the gateway with a brand and a last four. The product never holds a full card number. |
| **PR-32** | Changing or removing a payment method requires a fresh one-time code. |
| **PR-33** | The Pay control appears in its normal place, visible and disabled, carrying its reason. Never hidden, and never live-but-inert. |
| **PR-34** | A credit figure is re-read on every load and never cached. |
| **PR-35** | The uneven last instalment of a payment plan is shown, not absorbed. |
| **PR-36** | A refusal always carries a reason, and the portal shows it. |
| **PR-37** | A medical hold is stated with its expiry, in words. A hold is never implied to be permanent. |
| **PR-38** | The portal may never grant a protection itself. Every one of the three needs a person and a document. |
| **PR-39** | The portal is a channel that waits, not one that pushes, so it can never be the only channel for anything with a deadline. |
| **PR-40** | Help answers, tips and service centres appear only when published, in date and marked shown. When nothing is written, the page, the link and the slot are absent. |
| **PR-41** | An answer with no translation is shown in English, never hidden. |
| **PR-42** | One tip per screen at a time; where two match, the top of the list wins. |
| **PR-43** | Portal branding reads the logo, the colours and the names from Company → Profile and stores no copy of its own. |
| **PR-44** | A hidden service centre stays in the back-office list and off the public page. Hidden is a state, not a deletion. |
| **PR-45** | Public holidays close a service centre automatically, from the calendar the utility already keeps. Nobody types a closure. |
| **PR-46** | A guest surface sits behind the anonymous throttle the product already uses, at sixty requests a minute, plus a lockout on the two lookups that take a reference. |
| **PR-47** | Quick pay identifies on a bill number plus the postcode of the service address, and shows the amount owing and a masked name. |
| **PR-48** | Paperless is a recorded consent with a timestamp and a wording version, and a way to withdraw. Existing paperless customers are not asked again. |
| **PR-49** | Each of the big five — quick pay, self-read, plans, requests, outage — can be switched off by a utility. All on for a new tenant except self-read. |
| **PR-50** | Post and email remain the delivery record for notices; the portal is a convenience copy that must show what was sent, when, and by which route. |

### CR-068 · 8 · THE FIFTY-SIX SPECIFICATIONS — `CP-01`–`CP-56`, IN FULL

**This table is the scope of this CR and nothing outside it is committed** (§0b). Every status reads
`UNVERIFIED` and that is deliberate — the blueprint's own words: *"Not one row has been checked
against the code. Engineering fills this column in from the repository, one row at a time — and
several are expected to come back already done... **A status guessed from a change log, or from a
memory of having written something, is worse than no status at all.**"*

⚠ **THAT SENTENCE IS THIS REPOSITORY'S OWN MOST EXPENSIVE LESSON, ARRIVING FROM OUTSIDE.** On
2026-09-03 six `CR-059` task rows read as unstarted while the code they described was on the branch,
and an earlier version of the same rows sent a lane at three defects that were already fixed. **A
`CP-` row's status changes only when a person has read the code. Screens column uses the blueprint's
own G/P/B labels; §9 maps every one to its `CWP` number.**

| Spec | Title | Screens | What done looks like |
|---|---|---|---|
| **CP-01** | Customer credential store and portal session · CS-3 | P1 · P2 · P3 · P4 | Maria types m.alvarez@example.com and her password on P1, lands on the portal home, and the top-right avatar reads MA; a sixth wrong password shows “locked for fifteen minutes” instead of a sixth attempt. |
| **CP-02** | One-time code by email or SMS | P3 · P4 · P25 | P3 reads “It went to the phone we already hold: ••• ••• 4218”, a six-digit code arrives, and typing it eleven minutes later shows “that code has expired” with a resend, not an error page. |
| **CP-03** | Customer-side password reset | P5 | Any address typed on P5 returns the same “check your email” panel; only a real customer receives a link, and the link opens P4 with the password fields empty. |
| **CP-04** | Delegated customer users, with a permission set, an expiry and their own audit actor | P7 · P12 · P19 (roles) | Maria invites accounts@kestrel.example on P12, the row appears reading “Common areas · See · Download · 30 Jun 2027 · Invited”, and after Kestrel pays a bill the audit entry names Kestrel Bookkeeping, not Maria. |
| **CP-05** | A balance read, per account and totalled across a login | P8 · P9 · phone home | P8's first tile reads $142.18 with “Due 14 Sep · in 12 days” underneath, and P9's four rows total to $872.82 without merging into one invoice. |
| **CP-06** | The portal shell: tenant branding, account switcher, six tabs | every P screen · P6 · P15 | The header shows Pine Hill Water & Power in the utility's own colours, the switcher reads “1408 Elm St · A”, and choosing 22 Palm Ct reloads every tab against that account. |
| **CP-07** | Public bill lookup: bill number plus postcode, answering amount owing and a masked name | G2 · G3 | BL-2608-0141 with 78702 opens G3 showing $142.18 owing and “Billed to M. A••••••”; a sixth wrong pair locks the form for fifteen minutes. |
| **CP-08** | Payment gateway integration and a stored-instrument table · CS-1 · CS-9 | P24 · P25 · P26 · G3 · P36 | The customer presses Pay $142.18 on P24, a receipt reference appears, and P27 gains a row reading “Cleared” the same minute; P25 lists “Visa ••••8812 · expires 11/27” and never a full card number. |
| **CP-09** | An idempotent inbound payment webhook · CS-1 | P24 · P27 | The gateway sends the same settlement twice and P27 still shows one payment of $142.18, not two. |
| **CP-10** | Refunds returned to the original method · CS-1 | P31 · P18 | P31's refund timeline reads “Sent · 21 Sep · to the card ending 8812” rather than a cheque number, when that is how the money came in. |
| **CP-11** | A public premises and service-availability read | G8 | 31 Palm Ct returns a four-row table — Water Yes $185.00, Sewer Yes Included, Trash Yes $0.00, Electric Not here — and an unknown address returns “a person will look at it”, never a refusal. |
| **CP-12** | A public price read: plans, standing charges, connection fees, deposits | G1 (What things cost) · G8 | A visitor with no account reads “$185.00 before we start” and “$150.00 deposit on your first bill” for their own address, without signing in. |
| **CP-13** | Unauthenticated service-request creation, behind the anonymous throttle | G6 · G9 · G10 · P33 | A stranger sends G6 and gets reference RP-26-0412 on screen; the same report appears on a clerk's worklist with channel “Customer portal”, and the sixty-first submission in a minute is refused. |
| **CP-14** | A public reference lookup that returns progress and never data | G12 · G7 · P37 | RP-26-0412 with 78702 returns “A leak or a burst, near 1412 Elm St · Crew on site”; no name, no balance, no other reference on the account. |
| **CP-15** | An interruption record and an affected-area rule | G5 · G6 · G7 | A clerk opens the burst on Elm St and G7's timeline moves to “Crew on site” without anyone editing the customer's page. |
| **CP-16** | A planned-outage record and an affected-premises rule | P44 | P44 lists “Water main replacement · Elm St, 1400–1500 · 4–5 Sep · Planned” and the same work appears in P39 for the accounts on that stretch and for nobody else. |
| **CP-17** | The portal as a fourth notification channel | P11 · P39 · §19 | P11 gains a fourth column headed “In the portal” with a real switch on every row, and turning it off stops the row appearing in P39 while post still goes. |
| **CP-18** | A customer message list | P39 · P8 | P39 shows five rows with two unread and a bell reading 2; opening “Your August bill is ready — $142.18” marks it read and the bell reads 1. |
| **CP-19** | A customer-submitted reading, held for review | P21 · P20 · phone reading | Maria sends 158940 on P21, sees “that is 5,900 gallons in two days — about eight times your usual”, sends it anyway, and it appears in P20 as “You sent it in · awaiting review” and on no bill until a clerk clears it. |
| **CP-20** | A customer-raised bill or reading dispute | P41 · P14 · P20 | Maria sends the query on P41 and the August bill in P13 gains “held while we look”, no late fee accrues on $142.18, and the reading of 31 August shows a dispute marker in P20. |
| **CP-21** | A customer-raised payment plan request | P28 · P29 · P42 · P43 | Maria picks six months on P28, sees five instalments of $22.03 and a final $22.05 totalling $132.20, presses Ask for this plan, and P29 opens showing instalment 1 of 6 as “To come”. |
| **CP-22** | A customer-facing view of the collections ladder and what it costs | P43 · phone overdue | P43 shows $412.60 overdue by 19 days, the notice already sent on 1 September, and “If it goes that far $657.60” beside a button that raises a plan. |
| **CP-23** | Customer routes into the three protections | P42 | P42 offers a plan, a certificate upload and level pay; the weather moratorium is stated as a fact with no button, and the certificate route says in words that the hold expires. |
| **CP-24** | The bill comparison — why this bill is different | P16 · P14 | P16 opens on “Why August cost $3.74 more” and its four lines — +$8.83, $0.00, +$4.29, −$9.38 — add to exactly the $3.74 difference between $138.44 and $142.18. |
| **CP-25** | A customer-safe request history, and the customer-visible note flag switched on | P37 · P32 · G7 | P37 shows “We picked it up · 2 Sep, 2:40pm · Sarah at the office” and the note asking for two documents, and shows no internal routing comment from the same request. |
| **CP-26** | A general-question category and its routing | P40 | A question sent from P40 against BL-2608-0141 arrives on a clerk's worklist already naming that bill, and P37 can track it by its reference. |
| **CP-27** | A customer-safe view of credits and refunds in flight | P31 · P18 | P31 shows the refund at “Approved · 19 Sep”, two credits of $25.88 each against BL-2607-0139, and re-reads the credit figure on every load rather than caching it. |
| **CP-28** | A statement, or the transaction list named as one | P17 · P27 | The customer picks 1 January to 30 June and downloads one document that opens with a brought-forward figure and closes with a carried-forward figure that matches P8's balance. |
| **CP-29** | A high-usage trigger, its baseline and its cadence | P22 · P39 | P22 opens from a message that arrived on its own, and its chart shows the change starting on 25 August against this account's own history, not against a validation threshold. |
| **CP-30** | Portal settings on the tenant: the address, the on/off, and the five switches | B1 · B2 · every guest screen | A System Admin copies smartbillhub.bynry.com/pine-hill from B1, turns Send your own reading off, and P21 stops being reachable while every other tab is unchanged. |
| **CP-31** | The help-answer store: statuses, language variants and a screen attachment | B3 · B4 · G11 · P45 · P46 · P47 | A clerk publishes “Why is my bill higher than last month?” in B4 with “Also show on: The bill screen”, and it appears within the minute on G11, on P45 and under the charges on P47. |
| **CP-32** | The tip store: a target screen, a month range and an order | B5 · P48 · P8 · P19 | The June–September watering tip shows on P48 today and is gone from it on 1 October, and the portal home shows no tip at all because the only tip aimed at it is switched off. |
| **CP-33** | The service-centre record: hours, allowed actions, payment methods, holiday closures | B6 · B7 · G13 · G14 | G13 lists two centres and not the depot, the north counter reads “Closed today · Opens Tuesday at 9:00am”, and on Thanksgiving both read closed without anyone editing the page. |
| **CP-34** | The portal's write-back: an answer read count and a did-this-help vote | P46 · B3 | Three people open the bill-higher answer and B3's read column moves from 1,204 to 1,207; pressing No on P46 is counted separately from opening it. |
| **CP-35** | A customer-scoped contact and preference write path, with an audit entry | P10 · P11 | Maria changes her mobile on P10, sees the saved value on reload, and an audit entry names her as the actor; the name field is not editable and offers a request instead. |
| **CP-36** | The public front page | G1 | smartbillhub.bynry.com/pine-hill opens on six errand cards with Sign in as one of them, and a visitor reaches Pay a bill in one click without meeting a password field. |
| **CP-37** | A lockout on the two guest lookups that take a reference | G2 · G12 | A sixth wrong bill-number-and-postcode pair, or a sixth wrong reference-and-postcode pair, returns “locked for fifteen minutes” from the same address. |
| **CP-38** | Collecting a connection fee · CS-1 | P36 | P36's Pay $335.00 takes the money, the request moves out of “fees due”, and the $150.00 deposit still shows as due on the first bill rather than being taken now. |
| **CP-39** | A plan the utility has offered, and the customer’s signature on it | P49 · P29 · P39 | Maria opens P49, reads “Pine Hill has offered you a plan” with six dated instalments, presses Accept this plan , and P29 opens with instalment 1 of 6 — and the plan row moves from agreement_sent to active with her signature date on it. |
| **CP-40** | The whole plan record on screen, not a monthly summary of it | P29 | P29 shows “$40.00 paid up front”, “monthly”, and against instalment 2 the payment that cleared it — and on a plan where the clerk left late-fee suspension off, the panel says fees still apply instead of saying they stop. |
| **CP-41** | Protections that are holding the account, each with its own lifetime | P50 · P42 · P43 | P50 reads “A doctor’s certificate is holding your supply until 30 November”; the plan hold beside it carries no date and says instead that it ends the day an instalment is missed; the moratorium shows 1 December to 1 March and offers no button. |
| **CP-42** | The customer’s own disconnection case, not a diagram of the ladder | P43 · P50 | P43 reads “a cut is scheduled for 25 September” from this account’s case rather than from a cadence setting, names the services that would go, and a customer at the five-day notice is never shown as being at the ten-day one. |
| **CP-43** | The deposit being held, while it is being held | P51 · P8 · P18 | P51 reads “We are holding $150.00, taken on 4 March 2021” and says it comes back at closing with interest — on an account that is not going anywhere. |
| **CP-44** | Adjustments posted to the account | P27 · P13 | A goodwill adjustment of −$25.88 appears in the customer’s money list with its date and its plain-English reason, on the day it is posted. |
| **CP-45** | A tax exemption and the date it lapses | P51 | P51 reads “You are exempt from state utility tax until 31 March 2027”, and thirty days before that date the customer gets a message rather than a bigger bill. |
| **CP-46** | Level pay standing: the level, the variance and the settle-up | P52 · P30 | P52 reads “You pay $125.00 · you are $47.30 ahead · June settles up”, and lists each re-levelling with what actually happened that year. |
| **CP-47** | Debt written off, without its reason | P43 · P27 | A write-off of $84.20 on 12 May appears in the money list as “written off” with no reason code, and a reversal appears as its own row rather than deleting the first. |
| **CP-48** | The reason a payment control is refused | P25 · P26 · P24 | A customer whose account is marked cash-only sees autopay disabled with “we cannot take card or bank payments on this account” on it, rather than a control that does nothing. |
| **CP-49** | Every notice sent, and every notice deliberately not sent | P54 · P17 · P39 | P17 gains a row reading “Final notice · 15 Sep · post · not sent, no forwarding address”, so the notice that never arrived is the one most visible. |
| **CP-50** | Post that came back, and a bad address | P54 · P10 · P17 | P10 shows “Two letters came back from this address” above the address field, and fixing the address clears it. |
| **CP-51** | A visit booked at the property | P53 · P37 · P23 | P53 reads “A meter exchange is booked for Tuesday 15 September, morning”, says whether anybody needs to be in, and shows the same job as done once the crew closes it. |
| **CP-52** | The connection behind an application | P37 · P36 | P37 shows the connection’s target activation date and what it is waiting on, so an applicant stops ringing to ask which of the two it is. |
| **CP-53** | Service, plan and move history | P51 · P8 | P51 reads “Water and Sewer since 4 March 2021, Trash since 1 June 2024” and “Residential Standard since 1 January 2026”, and lists the move that opened the account. |
| **CP-54** | A landlord’s common-area reconciliation | P9 | On the common-areas account the landlord sees the master meter against the sum of the sub-meters for the month, and the difference they are billed for. |
| **CP-55** | Why a reading was corrected, and by how much | P20 | The 30 June row on P20 opens to read “estimated 144,600, corrected to 144,130 when the meter was read on 3 July — you were not charged twice”. |
| **CP-56** | Service requests raised by a signed-in customer | P32 · P34 · P35 · P38 · P37 | Maria picks Move out on P32, sends it on P34, and SR-26-0056 appears on a clerk’s worklist with channel “Customer portal” — the first row in the product ever to carry that value — and she can withdraw it from P37 until it is approved. |

**Status column for every row above: `UNVERIFIED`.** Track it in §12's phase tables as each is picked
up, and record the evidence — the file and the test count — not the word *done*.

### CR-068 · 9 · THE SEVENTY-SEVEN SCREENS — `CWP-001`–`CWP-077`

**PO ruling 2026-09-03: *"You can assign number CWP-nnn - Assig all unqie numbers"*.**

⚠ **THIS HEADING READ *THE SEVENTY-FIVE SCREENS — `CWP-001`–`CWP-075`* UNTIL 2026-09-11**, when `CR-085`
step 2 lane 6 allocated **`CWP-076`** and **`CWP-077`** for the two screens the PO's *"it should be 3
screens - confirmed"* ruling created out of `CWP-038`. The heading is moved **in the same commit as
the rows**, which is the lesson CLAUDE.md's B14 rule-count line has now recorded five times: ratifying
a thing and moving the pointer to it are two acts, and only the first one feels like the work.

**The count is 75 and not the 79 the blueprint's headline claims** (§0c). Allocation is **1:1 with
the document's own labels, in its own order**, and those labels are kept as the mapping key exactly
as `screenIds.ts` keeps r10's badge beside A1's id — the document is the source and re-lettering
would break every cross-reference in it.

**`CWP` is a new id family.** It obeys the five-digit ceiling ruled 2026-08-31; the search pattern is
`CWP-\d{3,5}(?!\d)` and **the lookahead is load-bearing** for the same reason it is everywhere else
(`DEF-2804`: `OQ-\d{3}` returned `OQ-119` for `OQ-1190`, a different real question). Zero-padded to
three, which is a spelling chosen **at birth** — the thing law 11 forbids is padding a series that
already carries citations, and this one has none yet.

| CWP | Blueprint | Screen |
|---|---|---|
| **CWP-001** | `G1` | The public front page |
| **CWP-002** | `G2` | Quick pay · find the bill |
| **CWP-003** | `G3` | Quick pay · check and pay |
| **CWP-004** | `G4` | Quick pay · done |
| **CWP-005** | `G5` | Check my area |
| **CWP-006** | `G6` | Report a problem |
| **CWP-007** | `G7` | Report sent |
| **CWP-008** | `G8` | Can I get service here? |
| **CWP-009** | `G9` | Apply for a connection · check and send |
| **CWP-010** | `G10` | Ask for a quick service |
| **CWP-011** | `G11` | Help and answers |
| **CWP-012** | `G12` | Track anything |
| **CWP-013** | `G13` | One centre, its hours and its limits ⚠ see the note below the table |
| **CWP-014** | `G14` | Pay in person, from Pay now ⚠ see the note below the table |
| **CWP-015** | `P1` | Front door |
| **CWP-016** | `P2` | Find my account |
| **CWP-017** | `P3` | Prove it is you |
| **CWP-018** | `P4` | Choose a password |
| **CWP-019** | `P5` | Forgotten password |
| **CWP-020** | `P6` | Add another account |
| **CWP-021** | `P7` | Accept an invitation |
| **CWP-022** | `P8` | Portal home |
| **CWP-023** | `P9` | All my accounts |
| **CWP-024** | `P10` | My details |
| **CWP-025** | `P11` | How we contact you |
| **CWP-026** | `P12` | People with access |
| **CWP-027** | `P13` | Bills |
| **CWP-028** | `P14` | One bill, line by line |
| **CWP-029** | `P15` | The bill as it was printed |
| **CWP-030** | `P16` | Why is this bill different? |
| **CWP-031** | `P17` | Documents and letters |
| **CWP-032** | `P18` | Your final bill |
| **CWP-033** | `P19` | Usage |
| **CWP-034** | `P20` | Every reading |
| **CWP-035** | `P21` | Send your own reading |
| **CWP-036** | `P22` | Your usage looks high |
| **CWP-037** | `P23` | Meters and equipment |
| **CWP-038** | `P24` | Pay now |
| **CWP-039** | `P25` | Your payment methods |
| **CWP-040** | `P26` | Autopay |
| **CWP-041** | `P27` | Payments and receipts |
| **CWP-042** | `P28` | Ask for a payment plan |
| **CWP-043** | `P29` | Your payment plan |
| **CWP-044** | `P30` | Level pay |
| **CWP-045** | `P31` | Credits and refunds |
| **CWP-046** | `P32` | What do you need? |
| **CWP-047** | `P33` | Start service — for someone with no account |
| **CWP-048** | `P34` | Moving out or moving on |
| **CWP-049** | `P35` | Documents we need from you |
| **CWP-050** | `P36` | Fees to pay |
| **CWP-051** | `P37` | Track your request |
| **CWP-052** | `P38` | Stop or restart service |
| **CWP-053** | `P39` | Messages |
| **CWP-054** | `P40` | Ask a question |
| **CWP-055** | `P41` | Dispute a bill or a reading |
| **CWP-056** | `P42` | Help paying |
| **CWP-057** | `P43` | What happens if this is not paid |
| **CWP-058** | `P44` | Outages and planned work |
| **CWP-059** | `P45` | Help and answers — signed in |
| **CWP-060** | `P46` | Under a bill, when it is attached ⚠ see the note below the table |
| **CWP-061** | `P47` | Tips ⚠ see the note below the table |
| **CWP-062** | `P48` | Nothing at all when none is live ⚠ see the note below the table |
| **CWP-063** | `P49` | A plan the utility has offered you |
| **CWP-064** | `P50` | What is protecting your supply |
| **CWP-065** | `P51` | Your account |

⚠ **SIX OF THESE TITLES NAME A DIFFERENT SCREEN FROM `08-screen-layouts.md`, AND
THE CODE WAS BUILT TO THE LAYOUT DOCUMENT — `DEF-CWP-3728`, stamped 2026-09-05.**
**NOTHING IS RENUMBERED and no code changes for this**; the ids and their
blueprint labels are exactly as allocated here, which is why `G82` — which checks
an id against its blueprint LABEL — passes over the whole thing. What diverges is
the human TITLE, which no gate compares and none could without being told which
document is the authority.

| Screen | This table (§9) | `08-screen-layouts.md` |
|---|---|---|
| `CWP-013` | One centre, its hours and its limits | **Where you can walk in** — the LIST |
| `CWP-014` | Pay in person, from Pay now | **One service centre** |
| `CWP-059` | Help and answers — signed in | same ✔ |
| `CWP-060` | Under a bill, when it is attached | **One answer** |
| `CWP-061` | Tips | **An answer where the question is asked** |
| `CWP-062` | Nothing at all when none is live | **A tip where it lands** |

`08-screen-layouts.md` was written while looking at the wireframes, and the waves
built to it and to their own demo scripts, which agree with each other. The
routes bear that out: `/visit` is the list and `/visit/:slug` is one centre.
**Read a title here as the change request's allocation, not as a description of
the screen that shipped** — `07-frontend/src/portal/routing/screenIds.ts` carries
the same note beside the rows it affects, so the next reader meets it in the file
rather than in a bug report.
| **CWP-066** | `P52` | Where your level pay stands |
| **CWP-067** | `P53` | A visit is booked |
| **CWP-068** | `P54` | Everything we sent you, and what came back |
| **CWP-069** | `B1` | Overview |
| **CWP-070** | `B2` | Branding |
| **CWP-071** | `B3` | Help and answers |
| **CWP-072** | `B4` | Edit an answer |
| **CWP-073** | `B5` | Tips |
| **CWP-074** | `B6` | Service centres |
| **CWP-075** | `B7` | Edit a centre |
| **CWP-076** | `P55` | Check before you pay |
| **CWP-077** | `P56` | Payment made |
| **CWP-078** | `R24c` | Property statement |
| **CWP-079** | `P5u` | Update your registered email |

**Next free ground: `CWP-080`.**

⚠ **`CWP-079` WAS ALLOCATED ON 2026-10-22 BY `CR-189-BRC10`** (lane PORTAL-EMAIL), for the
locked-out customer's *update your registered email* wizard the PO ruled that day. The blueprint
draws no such screen; `P5u` names it as the sibling of `P5` (*Forgotten password*, `CWP-019`),
whose page links to it, rather than inventing a plate number.

⚠ **`CWP-078` WAS ALLOCATED ON 2026-09-27 BY `CR-142-BRC07` `P4.15`, AND ITS LABEL COLUMN GOES ONE
STEP FURTHER THAN `CWP-076`/`CWP-077` DID.** Those two named a plate of the *Customer Portal
Blueprint* rather than an r10 frame, for the reason recorded below. **`CWP-078` names neither**: it
is `R24c`, a REPORT in the *Reports Build Brief* (p070–p071, *Statement · by premises*). The
customer-portal blueprint draws **no property statement at all** — grepped on 2026-09-27, its 129
pages mention a landlord's PROPERTIES (p52) and never a statement for one — and the screen exists
because the PO ruled on what a landlord may see of that report in the portal: *"a landlord sees
**their own master account only**: the $69.60, never Unit 3's $100.00 (`P4.15`)"*. Naming a portal
page the blueprint does not have would be a cross-reference to nothing, which is the failure this
column exists to prevent; naming the report says truthfully where the shape came from.

⚠ **AND THE ROW IS WRITTEN HERE IN THE SAME COMMIT AS `portal/routing/screenIds.ts`.** `G82`
refuses a route whose id §9 does not allocate, and an id allocated in code but not here is an id
nobody can look up in a bug report — the same two-acts-and-only-the-first-feels-like-work shape
CLAUDE.md records for every pointer that went stale.

⚠ **`CWP-076` AND `CWP-077` WERE ALLOCATED ON 2026-09-11 AND THE LABEL COLUMN IS DOING SOMETHING
SLIGHTLY DIFFERENT FOR THEM, SAID HERE RATHER THAN LEFT TO BE INFERRED.** Every label above is an
r10 prototype frame (`G1`…`G14`, `P1`…`P54`, `B1`…`B7`). **The portal has no r10 prototype**, and
these two screens come from a LATER drawing — *SMARTBillHub Customer Portal Blueprint.pdf* of
2026-09-08, its **screen 36 `Check before you pay` (p66)** and **screen 37 `Payment made` (p67)**.
`P55` and `P56` continue the portal series so the register stays one vocabulary and `G82` can go on
checking the pairing; they name no prototype frame and nobody should go looking for one.

**Why they exist at all:** PO 2026-09-11, verbatim — ***"it should be 3 screens - confirmed"***, and
then ***"ii). Your ruling was about the shape, not the addresses."*** The signed-in pay journey was
ONE screen with a stepper inside it (`CWP-038`, `PayNow.tsx`, 763 lines); it is now three screens at
three addresses **under the one it already occupies** — `/pay-now`, `/pay-now/check`, `/pay-now/done`
— and **no guest address moved**. ⚠ The blueprint draws screens 35–37 at `/pay`, `/pay/check` and
`/pay/done`, which is where the GUEST flow lives in this product; that crossing is deliberate and
ruled, and the decision log of 2026-09-11 is what stops a later lane "correcting" the router from the
drawing.

⚠ **THESE ARE TICKET NUMBERS, NOT BADGES.** The staff app's visible tag renders r10's module id and
never an `S`-id (PO ruling 2026-08-19). **The portal has no r10 prototype**, so its visible tag — if
one is wanted — is a separate decision nobody has taken. `g29_screen_ids.py` reads the staff app's
route table and **must not be pointed at the portal without a ruling**; §13 proposes its own gate
instead.

### CR-068 · 10 · THE NINE OPEN QUESTIONS — none may be answered by a lane

**The prime directive applies: implement to the boundary and stub the gap as
`raise NotImplementedError("PQ-##")`.** Four of the blueprint's thirteen are now answered (`PQ-05`,
`PQ-09`, `PQ-10` on 2026-09-02; `PQ-13` on 2026-09-03). Nine remain.

| # | The question | Why a lane cannot answer it | Blocks |
|---|---|---|---|
| **PQ-01** | Can a customer give themselves a payment plan, or must a person approve it? | It is a credit decision. Self-serve cuts phone calls and raises the number of plans that fail. The utility's appetite, not ours | `CP-21`, `CP-23` |
| **PQ-02** | Can a customer close their own account, or only ask to? | A move-out settles a deposit and issues a final bill. Self-serve means a mistaken click has a refund at the end of it | request surface |
| **PQ-03** | Does a customer-submitted reading go straight onto a bill, or wait for review? | Straight through is faster; review is what stops a misread dial becoming a bill. **The blueprint assumes review** | `CP-19` |
| **PQ-04** | Who pays the card fee — absorbed, surcharged or bank-only? | It changes the pay screen and in some states is regulated | `CP-08` |
| **PQ-06** | What does the portal count as a statement? | There is no statement document in this product. Either the transaction list becomes one, or a statement gets built | `CP-28` |
| **PQ-07** | How long may a delegate hold access, and who may revoke it? | A bookkeeper who leaves a firm should lose access. Expiry, review or manual removal is the utility's policy | `CP-04` |
| **PQ-08** | Does a landlord see a tenant's bill? | They pay for common areas and may hold the tenancy — but the tenant's usage is the tenant's. A privacy question with a legal answer that varies | `CP-54`, the account-link model |
| **PQ-11** | Who keeps the help answers current, and in how many languages? | Eleven catalogues already ship. Help content is per tenant and someone at the utility has to write it — an ongoing job, not a build | `CP-31`, `CP-34` |
| **PQ-12** | **Is the portal a channel a notice can be delivered on?** | **The blueprint names this the one to answer first**, and it is right: a disconnection notice has legal delivery requirements, a portal message is not proof of delivery, and *"treating it as one would be the most consequential mistake available here."* It determines whether the portal is a convenience layer or a system of record — changing the audit, the retention and the legal review of nearly every screen in the paying and requesting sections | `CP-17`, `CP-49`, `CP-50`, and the shape of release three |

**⚠ `PQ-12` SHOULD BE PUT TO THE PRODUCT OWNER BEFORE RELEASE THREE STARTS, not before release one.**
Releases one and two contain no notice delivery, so the question does not block the first two phases
— but a lane that reaches release three without it will guess, and guessing here is the mistake the
blueprint singles out by name. **Raise all nine in `12-governance/01-open-questions.md` with real
numbers from the live register at the moment of writing** (`PQ-` is a document-local series; it is
NOT the repository's `OQ-` series, and the two must not be confused — see §11).

### CR-068 · 11 · FOLDER STRUCTURE AND HOW THIS ENTERS THE REPOSITORY

**The Product Owner asked this explicitly: *"also confirm what will be folder structure for this -
how you will add this in current repo"*. This section is the answer.**

#### 11a · The address — and a correction to what was said about it

**PO ruling: `/{utility-name}/portal/…`.**

⚠ **I told the Product Owner this question *"has a deadline rather than a backlog slot"* because a
reserved word had to be claimed before somebody registered a utility called `portal`. That is true of
the OTHER option and FALSE of the one chosen, and the correction is recorded here so no lane acts on
the wrong urgency.** Tenancy has been path-based since the PO's ruling of 2026-08-10 and **the tenant
is the FIRST path segment**; `portal` under this ruling is the **SECOND**, which makes it an ordinary
tenant-level route beside `billing`, `payments` and `reports`.

**Therefore:**
* `RESERVED_SUBDOMAINS` in `06-backend/apps/tenancy/selectors.py:78` **does NOT need to grow.**
* A utility may still be named `portal`; its address reads `/portal/portal/bills`, which is ugly and
  is not broken.
* **What WAS owed and is verified:** `portal` collides with no existing tenant-level segment. No
  route named `portal` exists in `07-frontend/src/routing` or `06-backend/config/urls.py`, and it is
  not in `core.tenancy.NON_TENANT_SEGMENTS` (`public`, `tenants`, `jobs`, `exports`, `health`) —
  the list that would silently resolve a segment to *"no tenant"* before the resolver ran.
* **What IS real:** this is the address a utility prints on a bill. It is a customer-visible
  commitment from the first tenant onward.

#### 11b · Backend — a new Django app, `06-backend/apps/portal/`

**A new module, not a widening of an existing one.** The module map in CLAUDE.md is nine code modules
and cross-module writes are forbidden; the portal is a **tenth**. It owns its own tables and reaches
everything else through the published seams that already exist.

```
06-backend/apps/portal/
  __init__.py
  apps.py
  models.py              portal_credentials · portal_sessions · portal_delegates
                         · portal_settings · portal_consents
  migrations/            0001_initial.py onward. RLS FORCE in its own migration,
                         the way every other module does it
  api.py                 THE PORTAL EDGE — every authenticated portal route
  guest_api.py           THE GUEST EDGE — every unauthenticated route, behind
                         the anonymous throttle
  session.py             resolve tenant → resolve portal identity → the account set
  credentials.py         password hashing, lockout, one-time codes
  delegates.py           invited users, permission set, expiry, own audit actor
  selectors.py           reads. NOTHING here writes
  services.py            the four write paths and nothing else (PR-17)
  seams/                 one file per module it reads FROM — billing_seam.py,
                         payments_seam.py, metering_seam.py, customers_seam.py,
                         notifications_seam.py, ledger_seam.py
  write_points.py        the four write points, declared as data so G75 can read
                         them (§13)
  sample_data.py         the demo fixture (§12 phase 0)
  tests.py
```

**Three more modules gain tables rather than the portal owning them**, because the owning module owns
its data (B2 §2):

| Table | Owned by | Why not `portal` |
|---|---|---|
| `payment_methods` (stored instrument) | `apps/payments` | It is a payment concept and the money rules live there. ⚠ **NAME COLLISION** — `apps/payments/models.py:65` records that `payment_methods` as B2 §2 spells it is the CUSTOMER's stored instrument, and the name is currently taken by the staff tender lookup. **Resolve the name before the migration** |
| `interruptions`, `planned_outages` | `apps/metering` | They are network facts, not portal facts. **`CP-15` is the largest genuinely new record in the blueprint** |
| `help_answers`, `tips`, `service_centres` | `apps/tenancy` | They are per-tenant published content, and Settings already owns that shape |
| `customer_readings` (submitted, awaiting review) | `apps/metering` | `PR-29`: identical validation to a staff-entered read |

#### 11c · Frontend — a second application root, `07-frontend/src/portal/`

**Not a `features/` folder.** `features/` is the staff app's furniture and the portal shares neither
its shell, its navigation, its role model nor its density. Sharing that directory would guarantee a
staff component drifts into a customer screen.

```
07-frontend/src/portal/
  PortalApp.tsx          the portal's own root, mounted at /:tenant/portal/*
  routing/
    portalRoutes.tsx     every CWP screen, one route each
    screenIds.ts         the CWP register — the portal's own, NOT the staff map
  shell/                 header, account switcher, six tabs, tenant branding
  guest/                 CWP-001..CWP-014 — the whole no-login surface
  screens/               CWP-015..CWP-068
  backoffice/            CWP-069..CWP-075 — these live in the STAFF app's
                         Settings, not the portal; see the note below
  api/                   the portal edge client. It may call NOTHING else
  components/            portal-only primitives
  styles/                portal.css — and see the Tailwind note below
```

⚠ **`CWP-069`–`CWP-075` (B1–B7) ARE STAFF SCREENS.** They are the back office FOR the portal — the
overview, branding, help answers, tips and service centres a clerk edits. They belong in
`07-frontend/src/features/tenancy/` under Settings, and they carry `CWP` numbers only because the
blueprint drew them. **A lane that builds them into the portal app has put a staff screen behind a
customer login.**

⚠ **B14 RULE 21 AND THE SILENT FAILURE.** A Tailwind utility is emitted **only** for a file listed in
`07-frontend/src/styles/route-b-migrated.txt`. Write one in a file that is not on that list and it is
a class no stylesheet declares: **it renders as nothing at all, and `tsc`, eslint and every
`toContain("flex")` assertion pass, because the class IS in the DOM.** The portal is new code and
should be **added to that list in its first commit** so it can use utilities throughout — that is the
one decision that makes B14 rule 21 cheap here instead of a permanent tax. **Do it in phase 0 and
verify with `g31_declared_classes.py`.**

#### 11d · Identifiers — four new families, and what each is for

| Family | For | Pattern | Where the register lives |
|---|---|---|---|
| `CWP-###` | **Portal screens** | `CWP-\d{3,5}(?!\d)` | §9 of this CR, mirrored into `07-frontend/src/portal/routing/screenIds.ts` |
| `CP-##` | **The blueprint's specifications** | document-local | §8. **Kept as-is** so every reference back to the source document resolves. Not minted into any product series |
| `PQ-##` | **The blueprint's questions** | document-local | §10. ⚠ **These are NOT `OQ-` numbers.** Each open one gets a real `OQ-` from the live register when raised; the `PQ-` stays as the cross-reference |
| `BR-CWP-#####` | **Portal business rules** | five digits, no padding | `04-docs/05-modules/15-portal/02-business-rules.md`. §7's `PR-13`–`PR-50` become these |

**Docs module:** `04-docs/05-modules/15-portal/` — the fifteenth doc module, following the fourteen
that exist. Epics `EP-CWP-##`, stories `US-CWP-#####`, numbered from the live register at write time.

#### 11e · What must NOT happen — stated as prohibitions because they are the expensive mistakes

1. **A portal credential must never resolve into a staff role.** Separate table, separate session,
   separate permission catalogue — **not one table with a flag on it.** The blueprint's own
   reasoning: *"A defeated portal login then costs a customer's own data. A defeated shared login
   costs the utility's whole book."*
2. **The tenant is resolved before anybody is identified.** That ordering is the whole isolation
   story and it is already how the staff app works. Do not invert it for convenience.
3. **The portal reaches the portal edge only.** A portal session must not be able to call a staff
   route, and the guest surface must not be able to call the portal edge.
4. **No second copy of anything.** One set of services — billing, payments, ledger, metering, rating,
   customers, notifications, documents, audit. The portal reads what the staff app writes.
5. **The four write points and nothing else** (`PR-17`, R12, and `G75` in §13).

### CR-068 · 12 · THE IMPLEMENTATION PLAN — five phases, each one launchable

⚠ **AMENDED 2026-09-03, SAME DAY IT WAS WRITTEN, BY PO RULING.** This section first proposed **six**
phases, the first of which was repository groundwork — a new module, the gate, the questions raised,
the Tailwind list. **The PO refused it**, verbatim: ***"Phases should be in agile way - at the end of
each pahse we should abl to luanch some funtionlaity - The phased plan is six phases, not five."***

**They are right and the correction is worth stating rather than quietly applying.** A phase that
ships nothing is not a phase; it is a task list wearing a phase's name, and calling it phase zero
hides the fact that nobody could show it to anybody. **The groundwork did not disappear — it is the
first four tasks of phase 1**, where it belongs, because phase 1 cannot start without it and phase 1
ends with a utility putting a page in front of the public. **Every phase below now ends with
something a utility can announce**, and each phase names that thing in one sentence before its task
table. If a future phase cannot name one, it is not a phase.

#### PHASE 1 — **LAUNCH: a utility puts its public page live**

**What a utility can announce at the end of it:** *"Our website can now tell you whether we serve
your address, what it costs, where our office is and when it is open, answer your common questions,
let you report a burst main or ask for a small service, and let you check on anything you have
already asked us — without you signing in to anything."*

**Why this is first:** it is the front of the funnel, it is the cheapest work in the whole blueprint,
**most people who reach a utility's website never sign in**, and a utility can put it live while
every decision below is still open. Not one of these screens needs a customer login or a payment
gateway.

Screens: `CWP-001`–`CWP-014` (G1–G14) plus the back-office screens that fill them.
Specifications: **`CP-11`, `CP-12`, `CP-13`, `CP-14`, `CP-15`, `CP-30`, `CP-31`, `CP-32`, `CP-33`,
`CP-36`, `CP-37`**.

| # | Task | Kind | Waits on |
|---|---|---|---|
| 1.1 | Create `06-backend/apps/portal/` and `04-docs/05-modules/15-portal/`; register `CWP-`, `EP-CWP-`, `US-CWP-`, `BR-CWP-` in the id grammar and open a `DEF-` reservation block | Ground | — |
| 1.2 | **Raise all nine `PQ-` questions in `12-governance/01-open-questions.md` with real `OQ-` numbers from the live register** | Ground | — |
| 1.3 | Add `07-frontend/src/portal/**` to `07-frontend/src/styles/route-b-migrated.txt` | Ground | — |
| 1.4 | **Build `G75`, the four-write-point gate, and prove it RED by adding a fifth write** (R12) | Gate | 1.1 |
| 1.5 | `guest_api.py` behind the anonymous throttle at sixty a minute (`PR-46`) | Back | 1.1 |
| 1.6 | Public premises and service-availability read (`CP-11`) | Back | 1.5 |
| 1.7 | Public price read — plans, standing charges, connection fees, deposits (`CP-12`) | Back | 1.5 |
| 1.8 | Unauthenticated service-request creation (`CP-13`) — **`PR-19`: may create work, never change an account** | Back | 1.5 |
| 1.9 | Public reference lookup returning **progress, never data** (`CP-14`, `PR-20`) | Back | 1.5 |
| 1.10 | **The interruption record and affected-area rule (`CP-15`)** — the largest genuinely new record in the blueprint | Back | 1.5 |
| 1.11 | Help-answer store: statuses, language variants, screen attachment (`CP-31`) | Back | 1.5 |
| 1.12 | Tip store: target screen, month range, order (`CP-32`) | Back | 1.5 |
| 1.13 | Service-centre record: hours, allowed actions, payment methods, **holiday closures from the calendar the utility already keeps** (`CP-33`, `PR-45`) | Back | 1.5 |
| 1.14 | Portal settings on the tenant: the address, the on/off, the five switches (`CP-30`, R8) | Back | 1.5 |
| 1.15 | Lockout on the two guest lookups that take a reference (`CP-37`) | Back | 1.9 |
| 1.16 | Screens `CWP-001`–`CWP-014` | Front | 1.3, all above |
| 1.17 | **Back-office screens `CWP-069`–`CWP-075`, in the STAFF app's Settings** (§11c) — without these the utility has nothing to publish and the launch above is an empty page | Front | 1.11, 1.12, 1.13 |
| 1.18 | Demo fixture: published help content, one interruption, one service centre | Test data | 1.11, 1.13 |
| 1.19 | Version, changelog, and **the launch proved by clicking it**, not by a green suite | Doc | all |

⚠ **`CP-16` (planned outages) waits on the field-work module, whose scope the blueprint records as
unresolved.** It is specified rather than shelved because shelving needs a person's decision and
nobody has taken one. **Not in this phase; not silently dropped either.**

#### PHASE 2 — **LAUNCH: customers can sign in and see everything they have**

**What a utility can announce:** *"Sign in and see what you owe, every bill you have ever had and
the PDF of each one, your meter readings and how this bill compares with last, your payment plan,
your deposit, anything we are holding for you, and change how we contact you."*

**Paying is visible and held.** The Pay control appears in its normal place, disabled, carrying its
reason (R3, `PR-33`) — never hidden, never live-but-inert. **That is a deliberate launch state**, not
an unfinished one, and the announcement should say when paying arrives.

Screens: `CWP-015`–`CWP-068` (the ones that do not need a gateway).
Specifications: **`CP-01`, `CP-02`, `CP-03`, `CP-05`, `CP-06`, `CP-24`, `CP-27`, `CP-35`,
`CP-39`–`CP-47`, `CP-52`, `CP-53`, `CP-55`**.

| # | Task | Waits on |
|---|---|---|
| 2.1 | **Customer credential store and portal session (`CP-01`)** — separate table, separate session, separate permission catalogue (`PR-13`, §11e) | 1.1 |
| 2.2 | One-time code by email or SMS (`CP-02`) — **to a contact already held, never one typed on the previous screen** (`PR-23`) | 2.1 |
| 2.3 | Password reset (`CP-03`) — **the same answer whether or not the address has a login** (`PR-24`) | 2.1 |
| 2.4 | **The balance read (`CP-05`)** — *"the single most-requested number in the whole product"*. **Re-read on every load, never cached** (`PR-34`) | 1.1 |
| 2.5 | The portal shell: branding read from Company → Profile with no copy of its own (`CP-06`, `PR-43`) | 2.1, 2.4 |
| 2.6 | Bills; the bill document served **pinned to the template it was issued with** (`PR-27`); the corrected-bill pair, both kept forever (`PR-26`) | 2.5 |
| 2.7 | The bill comparison (`CP-24`) — **arithmetic over existing reads that must never disagree with the bill it explains** (`PR-28`) | 2.6 |
| 2.8 | Credits and refunds in flight (`CP-27`), adjustments (`CP-44`), debt written off without its reason (`CP-47`) | 2.4 |
| 2.9 | Deposit held (`CP-43`), tax exemption and its lapse date (`CP-45`), level pay standing with its variance and settle-up (`CP-46`) | 2.4 |
| 2.10 | Plans (`CP-39`, `CP-40`) — **the uneven last instalment is shown, not absorbed** (`PR-35`) | 2.5 |
| 2.11 | Protections with their own lifetimes (`CP-41`) — **a medical hold states its expiry in words** (`PR-37`) | 2.5 |
| 2.12 | The customer's own disconnection case (`CP-42`); service, plan and move history (`CP-53`); the connection behind an application (`CP-52`); why a reading was corrected (`CP-55`) | 2.5 |
| 2.13 | Contact and preference write path with an audit entry (`CP-35`) — **write point four, the first one to go live** | 2.1, 1.4 |
| 2.14 | Screens `CWP-015`–`CWP-068` for the above | 2.5 |
| 2.15 | Demo fixture: a portal customer, a multi-account login | 2.1 |
| 2.16 | Version, changelog, **and the launch proved by signing in as the fixture customer** | all |

#### PHASE 3 — **LAUNCH: customers can ask us for things, and see what we sent them**

**What a utility can announce:** *"Raise a request, send us your own meter reading, question a bill
or a reading, and see every notice we have sent you and when."*

⚠ **`PQ-12` MUST BE ANSWERED BEFORE THIS PHASE STARTS** — whether the portal is a place a legal
notice counts as delivered. It changes the audit, the retention and the legal review of most of this
phase, and the blueprint names it *"the most consequential mistake available here."* Phases 1 and 2
contain no notice delivery, which is exactly why it does not block them.

Specifications: **`CP-17`, `CP-18`, `CP-19`, `CP-20`, `CP-25`, `CP-26`, `CP-49`, `CP-50`, `CP-56`**.

| # | Task | Waits on |
|---|---|---|
| 3.1 | **The portal as a fourth notification channel (`CP-17`)** — amends the catalogue entry that says this platform has no such channel | `PQ-12` |
| 3.2 | Customer message list (`CP-18`) | 3.1 |
| 3.3 | Every notice sent **and every notice deliberately not sent** (`CP-49`); post that came back and a bad address (`CP-50`) | 3.1 |
| 3.4 | Customer-submitted reading, held for review (`CP-19`) — **write point three**, same validation as a staff read (`PR-29`), and **a superseded read must not leave the customer charged for both** (`PR-30`) | `PQ-03`, 1.4 |
| 3.5 | Customer-raised bill or reading dispute (`CP-20`) — the marker and its ageing already exist | 2.5 |
| 3.6 | Service requests raised by a signed-in customer (`CP-56`) — **write point two**; the eleven-state lifecycle and its four customer transitions already exist | 1.4 |
| 3.7 | Customer-safe request history and **the customer-visible note flag switched on** (`CP-25`) — the flag exists and is inert | 3.6 |
| 3.8 | A general-question category and its routing (`CP-26`) | 3.6 |
| 3.9 | Version, changelog, **and the launch proved by raising a request and a reading as the fixture customer** | all |

#### PHASE 4 — **LAUNCH: customers in difficulty can help themselves before it gets worse**

**What a utility can announce:** *"See exactly where you stand if you are behind, what happens next
and what it will cost, ask for a payment plan, apply for the protections you may qualify for, and let
your bookkeeper or a family member see your account without giving them your password."*

**This deliberately sits ahead of paying**, and the blueprint's reason is right: each of these is
useful on its own, and a customer who can see the ladder and ask for a plan is helped even on a day
they cannot pay.

Specifications: **`CP-04`, `CP-21`, `CP-22`, `CP-23`, `CP-28`, `CP-29`, `CP-34`, `CP-51`, `CP-54`**.

| # | Task | Waits on |
|---|---|---|
| 4.1 | Delegated customer users with a permission set, an expiry and **their own audit actor** (`CP-04`, `PR-14`) | `PQ-07`, 2.1 |
| 4.2 | Customer-raised payment plan request (`CP-21`) | `PQ-01` |
| 4.3 | Customer-facing view of the collections ladder and what it costs (`CP-22`) — **every date and figure on it is already a configured setting** | 2.5 |
| 4.4 | Customer routes into the three protections (`CP-23`) — **the portal may never grant one; each needs a person and a document** (`PR-38`) | 4.2 |
| 4.5 | A statement, or the transaction list named as one (`CP-28`) | `PQ-06` |
| 4.6 | High-usage trigger, its baseline and cadence (`CP-29`) — **on monthly reads it can only fire at billing time** | cadence decision |
| 4.7 | Help write-back: an answer read count and a did-this-help vote (`CP-34`) | 1.11 |
| 4.8 | A landlord's common-area reconciliation (`CP-54`) | `PQ-08` |
| 4.9 | A visit booked at the property (`CP-51`) — **same field-work dependency as `CP-16`** | field-work scope |
| 4.10 | Demo fixture: a landlord with a delegate, an account on the ladder | 4.1 |
| 4.11 | Version, changelog, **and the launch proved by inviting a delegate and requesting a plan** | all |

#### PHASE 5 — **LAUNCH: customers can pay**

**What a utility can announce:** *"Pay your bill online, with a card or your bank, save the method
for next time, set up automatic payment, and pay without signing in if you have your bill to hand."*

**Ruled 2026-09-02 as a later stage, after the rest of the portal is built** (R2). Until it lands
every Pay control has been visible and disabled since phase 2, carrying its reason — so this phase
turns on a control people have already seen rather than adding one they have not.

Specifications: **`CP-07`, `CP-08`, `CP-09`, `CP-10`, `CP-38`, `CP-48`**.

| # | Task | Waits on |
|---|---|---|
| 5.1 | **Payment gateway integration and the stored-instrument table (`CP-08`)** — a token, a brand and a last four; **the product never holds a full card number** (`PR-31`). ⚠ Resolve the `payment_methods` name collision first (§11b) | `PQ-04` |
| 5.2 | Idempotent inbound payment webhook (`CP-09`) — ⚠ **`webhooks.py` was 577 lines with 15 tests as of 2026-09-03. VERIFY WHAT IS ALREADY THERE BEFORE BUILDING** (§0c) | 5.1 |
| 5.3 | Pay now, from the portal — **write point one, the last of the four to go live** | 5.1, 1.4 |
| 5.4 | Public bill lookup / quick pay (`CP-07`) — **bill number plus postcode, amount owing and a masked name, nothing else** (R7, `PR-47`) | 5.1 |
| 5.5 | Refunds returned to the original method (`CP-10`) | 5.1 |
| 5.6 | Collecting a connection fee (`CP-38`) | 5.1 |
| 5.7 | The reason a payment control is refused (`CP-48`, `PR-36`) | 5.1 |
| 5.8 | **Changing or removing a payment method requires a fresh one-time code** (`PR-32`) | 5.1, 2.2 |
| 5.9 | **Stamp `CR-059` rows 68, 70, 71, 72, 73 `SUPERSEDED BY CR-068`** (§2a) | 5.1 |
| 5.10 | Version, changelog, **and the launch proved by taking a real payment in the sandbox and watching the webhook not double-count it** | all |

#### The launch test, stated once so it is not negotiated per phase

**A phase is done when a person outside this team can be shown the thing in the sentence above its
task table, on a deployed build, and use it.** Not when the suite is green — `CR-059` §0d records
what happens when those two are confused, and hard-won law 6 says *"diff the running app against the
prototype; no gate looks at rendered output."* **Every phase's last task is the click-through, and it
is not optional.**

### CR-068 · 13 · GATES — what a machine must check

**Law 7 applies to every one: prove it RED on the thing it is written for before trusting it green.**

| Gate | What it asserts | Why a person cannot hold it |
|---|---|---|
| **`G75` four write points** (R12, `PR-17`) | The portal's surface can reach exactly four writes: a payment, a service request, a meter reading, its own preferences | It erodes one reasonable-looking commit at a time. Nobody ever decides to allow a fifth; a lane just needs one more field. ⚠ **Must not be a grep for four table names** — that passes on a write reached through a service that writes something else. Read what the portal's surface can reach, from `write_points.py` |
| **`G76` portal/staff separation** (`PR-13`) | No portal credential resolves into a staff role; the two share no table, no session, no permission catalogue | *"A defeated shared login costs the utility's whole book"* |
| **`G77` guest surface leaks nothing** (`PR-15`, `PR-20`) | A guest response carries an amount and a status and never a person; a reference lookup returns progress and never data | One field added to a serialiser is all it takes |
| **`G78` CWP screen register** | Every portal route carries a `CWP` number from §9's register, and no route invents one | The staff app's `g29` cannot be pointed here without a ruling (§9) |

**Existing gates that will bite and must not be silenced:** `g13_unwired` (built is not wired) ·
`g31_declared_classes` (B14 rule 21, §11c) · `g32_refusal_keys` (**baseline 0** — every refusal needs
its sentence in all eleven catalogues at five or six words or it renders as SILENCE) ·
`g33_refusal_copy_length` · `g07_human_owned` (portal credentials and the payment path are 🔒
sensitive) · `g15_i18n_parity` · `g17_duplicate_ids`.

### CR-068 · 14 · WHAT IS DELIBERATELY NOT IN SCOPE

**The blueprint rules 11 absences out of scope, 9 of them deliberate design rather than gaps.** The
one this CR restates because a lane will ask: **the public status page.** Ruled 2026-09-02 — *"the
public status page waits until somebody owns keeping it current out of hours."* It is drawn in the
blueprint because it is the other half of the interruption record, and the blueprint says in terms:
***"Do not put it in a build plan."***

Also out: anything that computes a charge (§2d) · a second copy of any service (§11e) · the
field-work module itself (`CP-16`, `CP-51` wait on it) · staff-facing changes beyond `CWP-069`–`075`.

### CR-068 · 15 · VERSION (change-process §7)

Scheme `<release>.<change>.<fix>`. This CR is change **68**. **Each phase gets its own version and
its own `CHANGELOG.md` entry**; the CR is not closed until phase 5 lands. A gate refuses a CR marked
done with no version — that step exists because it is the one usually skipped.

### CR-068 · 16 · ROLLBACK

**Phases 0–1 roll back cleanly:** the guest surface is additive, behind a per-tenant switch (R8), and
turning the switch off removes it with no data loss. **Phase 2 onward does not roll back by a
switch** — a customer who has set a password and a paperless consent has state that matters. From
phase 2, rollback is *turn the portal off for the tenant and keep the data*, never *drop the tables*.
`PR-48`'s consent record in particular is legal evidence and is never deleted.

### CR-068 · 17 · THE HANDOVER NOTE — for whoever picks this up

**What this CR does NOT contain and you will need:**

1. **The blueprint itself.** It is an artifact titled *Customer Portal Blueprint*. §8 carries every
   specification and §9 every screen, but the eighteen flow diagrams, the eight-row gap table and the
   per-screen wireframes are only in the document. **Read it before phase 1.**
2. **Verification of §8's statuses.** Every row reads `UNVERIFIED` and several are expected to come
   back already done. **That verification is the first hour of phase 1, and it is done by reading
   code, not a changelog.**
3. **The nine `PQ-` questions as real `OQ-` rows.** Task **1.2**. Until that is done, a lane reading
   `12-governance/01-open-questions.md` will not find them and will guess.

**What is already true and you can rely on:** the four rulings of 2026-09-03 are in the decision log
at commit `9d766f07`, verbatim, with their reasoning. The `CWP` allocation in §9 is complete and
collision-checked. The folder structure in §11 is decided. The correction in §11a — that the address
ruling carries no deadline — is recorded so nobody re-raises it as urgent.

### CR-068 · 18 · THE EXECUTION PLAN — where §12's phases became waves and tasks (2026-09-03)

**§12's five phases are unchanged and their launch sentences are kept.** Their tasks (`1.1`…`5.10`) are
completed against the 74 stories, split into sprint-sized WAVES and verified against the code, in
**`04-docs/05-modules/15-portal/10-execution-plan.md`** — the PO's rule of the same day applied:
*"we ahve to execute in agile way - each phase/wave should produce tangila eoutcome"*. Eighteen waves
(`A`–`R`), 105 tasks in the r11 four parts, every story in exactly one wave, every wave ending in a
5–8 step demonstration clicked in a browser (`10-scripts/render-checks/cr068-<wave>-<slug>.mjs`)
and a version bump. **Two things in it a lane must read before touching this CR:** its §0 — where
the documents disagree with the code at `b29edecd` and the code wins (the brand column names, the
guest root under `/portal`, `MeterRead.source`, the read-state split, the consumer-upload re-sign) —
and its §8, what is blocked and what still demonstrates. `12-governance/20-wave-tasks.tsv` carries
one row per task, all `open`. **§12's task numbers stay the cross-reference**; the plan's §11 lists
what it added and what it moved (`US-CWP-011` to phase 3, `US-CWP-044` to phase 4).
